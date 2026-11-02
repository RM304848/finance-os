"""Eine Buchung, die zu einer einmaligen Zeile passt und ihr nicht gehoert, zaehlt doppelt.

Gemessen steckt sie in der Basis, geplant steht sie in der Zeile. Der Hinweis steht an der
Planzeile auf /planung (mit „zuordnen“ ueber die vorhandene Buchungssuche) und als Punkt im
Monatsabschluss. Die Daten der Einheitstests sind erfunden; die Seitenprobe liest ihre
Buchung zur Laufzeit aus dem Hauptbuch.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest
import yaml
from fastapi.testclient import TestClient

from finctl import monatsabschluss as ma
from finctl.forecast import abgleich as ag
from finctl.forecast import szenarien as sz
from finctl.web.routen import planung as planung_seite
from finctl.web.server import app

client = TestClient(app)
KAT = "wohnen/reparatur"
FENSTER = ag.Fenster(von=date(2025, 10, 1), bis=date(2026, 9, 30), monate=12)


@pytest.fixture
def db():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(open("finctl/ledger/schema.sql", encoding="utf-8").read())
    for konto in ("giro", "karte"):
        c.execute("INSERT INTO accounts (id, display_name, institution, account_type, "
                  "ingest_mode, parser_profile) VALUES (?, ?, 'X', 'giro', 'parsed', 'p')",
                  (konto, konto))
        c.execute("INSERT INTO statements (account_id, source_path, source_name, file_sha256, "
                  "period_start, period_end, balance_start_cents, balance_end_cents, "
                  "parser_profile, parser_version, status, imported_at) VALUES (?, 'p', 'n', "
                  "?, '2025-01-01', '2026-09-30', 0, 0, 'p', '1', 'imported', 't')",
                  (konto, konto))
    for kat, eltern in (("wohnen", None), (KAT, "wohnen"), ("wohnen/miete", "wohnen"),
                        ("freizeit", None)):
        c.execute("INSERT INTO mgmt_categories (id, parent_id, name, kind) VALUES (?, ?, ?, "
                  "'expense')", (kat, eltern, kat))
    return c


def _buchen(c, kennung, tag, cents, kat=KAT, konto="giro", gegen="handwerker"):
    n = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] + 1
    c.execute("INSERT INTO transactions (id, account_id, statement_id, booking_date, "
              "amount_cents, counterparty_norm, raw_text, seq_in_statement, dedup_hash, "
              "created_at) VALUES (?, ?, 1, ?, ?, ?, 'x', ?, ?, 't')",
              (n, konto, tag, cents, gegen, n, kennung))
    c.execute("INSERT INTO splits (transaction_id, seq, amount_cents, mgmt_category_id, "
              "source, created_at, updated_at) VALUES (?, 0, ?, ?, 'rule', 't', 't')",
              (n, cents, kat))


def _zeile(**kw) -> sz.Line:
    basis = dict(label="Dachrinne", amount_cents=-100_000, frequency="einmalig", kind="betrag",
                 start=date(2026, 10, 1), category_id=KAT)
    return sz.Line(**{**basis, **kw})


def _gefunden(c, zeile, **kw):
    return [b["dedup_hash"] for b in sz.doppelt_gezaehlt(c, zeile, FENSTER, **kw)]


# ------------------------------------------------------------ was passt

def test_a_booking_of_the_same_kind_near_the_amount_in_the_month_is_found(db):
    _buchen(db, "b1", "2026-10-12", -98_000)
    assert _gefunden(db, _zeile()) == ["b1"]


def test_the_amount_may_differ_by_a_tenth(db):
    _buchen(db, "knapp", "2026-10-05", -110_000)
    _buchen(db, "zu_viel", "2026-10-06", -110_001)
    _buchen(db, "unten", "2026-10-07", -90_000)
    _buchen(db, "zu_wenig", "2026-10-08", -89_999)
    assert _gefunden(db, _zeile()) == ["knapp", "unten"]


def test_a_small_amount_gets_at_least_five_euros_of_room(db):
    """Zehn Prozent von 20 Euro waeren zwei Euro; eine Rechnung mit Versand traefe nicht."""
    _buchen(db, "versand", "2026-10-05", -2_450)
    _buchen(db, "anderes", "2026-10-06", -2_501)
    assert _gefunden(db, _zeile(amount_cents=-2_000)) == ["versand"]


def test_the_date_may_lie_two_weeks_beside_the_month(db):
    _buchen(db, "vor_dem_monat", "2026-09-17", -100_000)
    _buchen(db, "zu_frueh", "2026-09-16", -100_000)
    _buchen(db, "nach_dem_monat", "2026-11-14", -100_000)
    _buchen(db, "zu_spaet", "2026-11-15", -100_000)
    # Vor dem Messfenster zaehlt keine Messung etwas: die Zeile im Oktober sieht es nicht.
    assert _gefunden(db, _zeile()) == ["vor_dem_monat", "nach_dem_monat"]
    assert _gefunden(db, _zeile(start=date(2025, 10, 1))) == []


def test_a_booking_before_the_measuring_window_cannot_double_count(db):
    _buchen(db, "alt", "2025-09-20", -100_000)
    assert _gefunden(db, _zeile(start=date(2025, 10, 1))) == []


@pytest.mark.parametrize("buchung", [
    dict(kat="freizeit"),
    dict(cents=100_000),
], ids=["andere Kategorie", "anderes Vorzeichen"])
def test_what_does_not_match_is_not_found(db, buchung):
    _buchen(db, "b1", "2026-10-12", **{"cents": -100_000, **buchung})
    assert _gefunden(db, _zeile()) == []


def test_a_line_with_an_account_only_counts_that_account(db):
    _buchen(db, "b1", "2026-10-12", -100_000, konto="karte")
    assert _gefunden(db, _zeile(account_id="giro")) == []
    assert _gefunden(db, _zeile(account_id="karte")) == ["b1"]


def test_without_an_account_every_account_counts(db):
    _buchen(db, "b1", "2026-10-12", -100_000, konto="karte")
    assert _gefunden(db, _zeile()) == ["b1"]


def test_an_assigned_booking_is_not_double_counted(db):
    _buchen(db, "b1", "2026-10-12", -100_000)
    _buchen(db, "b2", "2026-10-13", -100_000)
    assert _gefunden(db, _zeile(buchungen=["b1"])) == ["b2"]


def test_only_a_one_off_money_line_can_double_count(db):
    _buchen(db, "b1", "2026-10-12", -100_000)
    assert _gefunden(db, _zeile(frequency="monatlich")) == []
    assert _gefunden(db, _zeile(kind="wegfall")) == []
    assert _gefunden(db, _zeile(kind="verkauf")) == []
    assert _gefunden(db, _zeile(start=None)) == []
    assert _gefunden(db, _zeile(category_id=None)) == []
    # Eine erwartete Einnahme findet keine Ausgabe.
    assert _gefunden(db, _zeile(kind="erwartet", amount_cents=100_000)) == []


def test_nothing_is_found_without_a_measuring_window(db):
    _buchen(db, "b1", "2026-10-12", -100_000)
    assert sz.doppelt_gezaehlt(db, _zeile(), None) == []


def test_the_hint_shows_at_most_twenty_bookings(db):
    for n in range(30):
        _buchen(db, f"b{n:02d}", "2026-10-12", -100_000)
    assert len(sz.doppelt_gezaehlt(db, _zeile(), FENSTER)) == sz.DOPPELT_GRENZE


# ------------------------------------------------------------ je Klammer

def _klammer(*zeilen, aktiv=True, kennung="k"):
    return sz.Scenario(id=kennung, name="Haus", active=aktiv, lines=list(zeilen))


def test_every_switched_on_line_is_checked(db):
    _buchen(db, "b1", "2026-10-12", -100_000)
    gefunden = sz.doppelt_je_zeile(db, [_klammer(_zeile(label="x", start=date(2027, 3, 1)),
                                                 _zeile())], FENSTER)
    assert list(gefunden) == [("k", 1)]


def test_a_switched_off_plan_counts_nothing_twice(db):
    _buchen(db, "b1", "2026-10-12", -100_000)
    assert sz.doppelt_je_zeile(db, [_klammer(_zeile(), aktiv=False)], FENSTER) == {}


def test_a_booking_another_line_carries_is_not_double_counted(db):
    _buchen(db, "b1", "2026-10-12", -100_000)
    klammern = [_klammer(_zeile()), _klammer(_zeile(buchungen=["b1"]), kennung="andere")]
    assert sz.doppelt_je_zeile(db, klammern, FENSTER) == {}


def test_the_series_of_a_recurring_line_is_carried_too(db):
    """Eine Zeile mit Takt nimmt die ganze Reihe: dieselbe Gegenpartei in derselben Kategorie."""
    _buchen(db, "b1", "2026-10-12", -100_000)
    _buchen(db, "b2", "2026-04-12", -100_000)
    reihe = _zeile(frequency="monatlich", buchungen=["b2"], kind="wegfall")
    assert sz.doppelt_je_zeile(db, [_klammer(_zeile(), reihe)], FENSTER) == {}


# ------------------------------------------------------------ Monatsabschluss

def test_the_month_end_lists_the_line_with_its_count(db, tmp_path, monkeypatch):
    _buchen(db, "b1", "2026-10-12", -99_000)
    _buchen(db, "b2", "2026-10-20", -101_000)
    (tmp_path / "szenarien.yaml").write_text(yaml.safe_dump({"szenarien": [
        {"id": "haus", "name": "Haus", "aktiv": True, "zeilen": [
            {"label": "Dachrinne", "art": "betrag", "amount_cents": -100_000,
             "frequenz": "einmalig", "start": "2026-10", "kategorie": KAT}]}]}),
        encoding="utf-8")
    monkeypatch.setattr(ma, "CONFIG_DIR", tmp_path)
    [posten] = ma.planung_doppelt(db, "2026-10")
    assert posten.gruppe == "planung" and posten.ziel == "/planung#klammer-haus"
    assert posten.name == "Haus · Dachrinne"
    assert posten.hinweis == "2 passende Buchungen, nicht zugeordnet: zählt doppelt"
    assert not posten.erledigt


def test_the_month_end_says_nothing_without_a_plan_file(db, tmp_path, monkeypatch):
    monkeypatch.setattr(ma, "CONFIG_DIR", tmp_path)
    assert ma.planung_doppelt(db, "2026-10") == []


# ------------------------------------------------------------ die Seite

@pytest.fixture
def klammer_datei(tmp_path, monkeypatch):
    """`szenarien.yaml` der Seite in einem Wegwerfordner, damit die Probe keine Datei anfasst."""
    pfad = tmp_path / "szenarien.yaml"
    monkeypatch.setattr(planung_seite, "SZENARIEN_PATH", pfad)

    def schreiben(zeilen):
        pfad.write_text(yaml.safe_dump({"szenarien": [
            {"id": "probe", "name": "Probe", "aktiv": True, "zeilen": zeilen}]}), encoding="utf-8")
    return schreiben


def _eine_buchung():
    """Eine Buchung im Messfenster mit Kategorie und Betrag, aus dem Hauptbuch."""
    from finctl.web.basis import conn

    c = conn()
    try:
        f = ag.fenster(c)
        if f is None:
            pytest.skip("kein Messfenster")
        r = c.execute(
            """SELECT t.dedup_hash, t.booking_date, s.amount_cents, s.mgmt_category_id
               FROM transactions t JOIN splits s ON s.transaction_id = t.id
               WHERE t.booking_date BETWEEN ? AND ? AND s.amount_cents != 0
                 AND COALESCE(s.mgmt_category_id, '') != ''
                 AND s.mgmt_category_id NOT LIKE 'transfer/%'
               ORDER BY t.booking_date DESC LIMIT 1""",
            (f.von.isoformat(), f.bis.isoformat())).fetchone()
    finally:
        c.close()
    if r is None:
        pytest.skip("keine Buchung mit Kategorie im Messfenster")
    return dict(r)


def test_the_page_names_the_booking_and_offers_to_assign_it(klammer_datei):
    b = _eine_buchung()
    klammer_datei([{"label": "Probezeile", "art": "betrag", "amount_cents": b["amount_cents"],
                    "frequenz": "einmalig", "start": b["booking_date"][:7],
                    "kategorie": b["mgmt_category_id"]}])
    seite = client.get("/planung").text
    assert "nicht zugeordnet — zählt doppelt" in seite
    assert "Zählt doppelt: gemessen und geplant" in seite
    assert f"buchungZu('probe-0', '{b['dedup_hash']}')" in seite


def test_the_page_is_quiet_once_the_booking_is_assigned(klammer_datei):
    b = _eine_buchung()
    klammer_datei([{"label": "Probezeile", "art": "betrag", "amount_cents": b["amount_cents"],
                    "frequenz": "einmalig", "start": b["booking_date"][:7],
                    "kategorie": b["mgmt_category_id"], "buchungen": [b["dedup_hash"]]}])
    seite = client.get("/planung").text
    assert f"buchungZu('probe-0', '{b['dedup_hash']}')" not in seite
