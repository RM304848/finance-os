"""Die Kontoprognose mit Takt: Reihen als Posten mit Termin (Schritt 4.5).

Eine Zahlung, die regelmaessig kommt, ist ein eigener Posten mit ihrem Betrag je
Termin und ihrem Takt (`RecurringItem.every_months`, `starts`); ihre Buchungen
zaehlen nicht noch einmal im Rest ihrer Kategorie. Den Rest rechnet die Tabelle
der Kontoprognose im kurzen Fenster. Das ersetzt das lange Fenster der Fixkosten.

Alles hier ist erfunden und rund: ein Haushalt mit zwei Konten, Stichtag
31.08.2026, `heute` also der 01.09.2026. Die Tests schreiben in einen
Wegwerfordner, nie in `config/`.
"""

from __future__ import annotations

import hashlib
from datetime import date

import pytest

from finctl import reihen
from finctl.forecast import abgleich as ag
from finctl.forecast import engine as fc
from finctl.forecast import fortschreibung as fs
from finctl.forecast import jahre as jm
from finctl.forecast import konten as ops
from finctl.forecast import takt as tk
from finctl.forecast import verfahren as vf
from finctl.forecast.herkunft import Posten
from finctl.forecast.messung import Ausschluss
from finctl.ledger.db import connect, init_db

HEUTE = date(2026, 9, 1)
FCFG: dict = {}


def _monate(erster: tuple[int, int], letzter: tuple[int, int]):
    j, m = erster
    while (j, m) <= letzter:
        yield j, m
        j, m = (j + 1, 1) if m == 12 else (j, m + 1)


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Zwei Konten, Auszuege von 09/2024 bis 08/2026, ein paar Kategorien."""
    (tmp_path / "config").mkdir()
    monkeypatch.setattr(reihen, "CONFIG_DIR", tmp_path / "config")
    c = connect(init_db(tmp_path / "t.db"))
    for konto in ("a", "b"):
        c.execute("INSERT INTO accounts (id, display_name, institution, account_type, "
                  "ingest_mode, parser_profile) VALUES (?,?,'X','giro','parsed','p')",
                  (konto, konto))
        for j, m in _monate((2024, 9), (2026, 8)):
            c.execute(
                "INSERT INTO statements (account_id, source_path, source_name, file_sha256, "
                "period_start, period_end, balance_start_cents, balance_end_cents, "
                "parser_profile, parser_version, status, imported_at) "
                "VALUES (?,'x','x',?,?,?,0,0,'p','1','imported','now')",
                (konto, f"{konto}{j}{m}", date(j, m, 1).isoformat(),
                 date(j, m, 28).isoformat()))
    for kennung, kind, fix, einmalig in (
            ("wohnen", "expense", 0, 0), ("wohnen/miete", "expense", 1, 0),
            ("wohnen/strom", "expense", 1, 0), ("konsum", "expense", 0, 0),
            ("konsum/essen", "expense", 0, 0), ("einkommen", "income", 0, 0),
            ("einkommen/gehalt", "income", 0, 0), ("einkommen/zulage", "income", 0, 0),
            ("immobilie", "expense", 0, 0),
            ("immobilie/kaufnebenkosten", "expense", 0, 1)):
        c.execute("INSERT INTO mgmt_categories (id, parent_id, name, kind, fixkosten, einmalig) "
                  "VALUES (?,?,?,?,?,?)",
                  (kennung, kennung.split("/")[0] if "/" in kennung else None,
                   kennung, kind, fix, einmalig))
    c.commit()
    yield c
    c.close()


def _buche(c, konto: str, tag: str, cents: int, kategorie: str, gegenpartei: str) -> str:
    """Eine Buchung mit einem Teil; zurueck kommt ihre Kennung."""
    n = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] + 1
    kennung = hashlib.sha256(f"buchung{n}".encode()).hexdigest()
    sid = c.execute("SELECT id FROM statements WHERE account_id = ? AND period_start <= ? "
                    "ORDER BY period_start DESC", (konto, tag)).fetchone()[0]
    tid = c.execute(
        "INSERT INTO transactions (account_id, statement_id, booking_date, amount_cents, "
        "counterparty_norm, raw_text, seq_in_statement, dedup_hash, created_at) "
        "VALUES (?,?,?,?,?,'x',?,?,'now')",
        (konto, sid, tag, cents, gegenpartei, n, kennung)).lastrowid
    c.execute("INSERT INTO splits (transaction_id, amount_cents, mgmt_category_id, "
              "source, created_at, updated_at) VALUES (?,?,?,'rule','now','now')",
              (tid, cents, kategorie))
    c.commit()
    return kennung


def _jeden_monat(c, konto, von, bis, tag, cents, kategorie, gegenpartei) -> list[str]:
    return [_buche(c, konto, f"{j}-{m:02d}-{tag:02d}", cents, kategorie, gegenpartei)
            for j, m in _monate(von, bis)]


def _posten(c, konto="a", **anders):
    """Die abgeleiteten Posten eines Kontos mit Reihen, wie die Kontoprognose sie baut."""
    return ops.abgeleitete_posten(c, konto, FCFG, [], stichtag=HEUTE, **anders)


def _von(items, kategorie):
    return [i for i in items if i.label == kategorie]


# ---------------------------------------------------------- Reihe als Posten


def test_a_booking_day_that_slips_is_one_item_with_the_amount_per_termin(db):
    """Mal am Letzten, mal am Ersten, in vier Monaten zweimal: zwoelf Termine in
    zwoelf Monaten, ein Posten. Ihre Buchungen stehen nicht noch einmal im Rest."""
    for tag in ("2025-09-30", "2025-10-31", "2025-12-01", "2025-12-31", "2026-01-31",
                "2026-03-01", "2026-03-31", "2026-05-01", "2026-05-31", "2026-07-01",
                "2026-07-31", "2026-08-31"):
        _buche(db, "a", tag, -90_000, "wohnen/miete", "hausverwaltung")
    [miete] = _von(_posten(db), "wohnen/miete")
    assert (miete.amount_cents, miete.every_months) == (-90_000, 1)
    # Der letzte Termin ist der 31.08., der naechste also im ersten offenen Monat.
    assert miete.starts == date(2026, 9, 1)
    assert "monatlich, je Termin −900,00 €" in miete.herkunft.herleitung
    assert "nächster Termin 09/2026" in miete.herkunft.herleitung


def test_a_running_series_that_is_overdue_comes_in_the_first_open_month(db):
    """Der letzte Termin war der 15.07.: der naechste (15.08.) liegt vor dem ersten
    offenen Monat, die Reihe laeuft aber noch -- er kommt im September, nicht gar nicht."""
    _jeden_monat(db, "a", (2025, 10), (2026, 7), 15, -4_000, "wohnen/strom", "versorger")
    [strom] = _von(_posten(db), "wohnen/strom")
    assert strom.starts == date(2026, 9, 1)


def test_the_kontoprognose_measures_over_the_window_of_the_hochrechnung(db):
    """Dasselbe Fenster und dieselben Monate zum Teilen: beide Bauer nehmen
    `abgleich.fenster` und damit dieselbe Konstante."""
    _jeden_monat(db, "a", (2025, 9), (2026, 8), 5, -3_000, "konsum/essen", "markt")
    kontoprognose = ops.kontoprognose(db, "a", FCFG, [], abwahl=False, heute=HEUTE,
                                      ohne_reihen=frozenset())
    hochrechnung = jm._hochrechnung(ag.fenster(db, bis=date(2026, 8, 31)), None)
    assert ag.FENSTER_MONATE == 12
    # Die Auszuege enden am 28.: Juli ist der letzte volle Monat.
    assert ((kontoprognose.since, kontoprognose.until, kontoprognose.fenster_monate)
            == (hochrechnung.since, hochrechnung.until, hochrechnung.fenster_monate)
            == ("2025-08-01", "2026-07-31", 12))


def test_the_old_window_keys_of_forecast_yaml_are_tolerated_and_change_nothing(db):
    """`window_months`, `min_occurrences`, `variable_kosten` und `window_months_fixkosten`
    liest kein Code mehr. Steht einer in der Datei eines Haushalts, bleibt die Rechnung
    dieselbe: zwoelf Monate, Summe durch zwoelf."""
    _jeden_monat(db, "a", (2025, 9), (2026, 8), 5, -3_000, "konsum/essen", "markt")
    _buche(db, "a", "2026-07-20", -60_000, "konsum/essen", "moebelhaus")
    alt = {"window_months": 3, "min_occurrences": 12, "variable_kosten": "median",
           "window_months_fixkosten": 6}
    neu = ops.abgeleitete_posten(db, "a", FCFG, [], stichtag=HEUTE)
    mit_alten = ops.abgeleitete_posten(db, "a", alt, [], stichtag=HEUTE)
    assert ([(i.label, i.amount_cents) for i in mit_alten]
            == [(i.label, i.amount_cents) for i in neu])
    # Der Abschlag ist eine Reihe mit Termin, der Moebelkauf der Rest: ein Zwoelftel.
    assert sorted(i.amount_cents for i in _von(neu, "konsum/essen")) == [-5_000, -3_000]


def test_a_series_whose_next_termin_is_long_overdue_is_over(db):
    """Zuletzt am 15.05.: mehr als einen Takt plus einen Monat her. Sie hat keinen
    Posten, und ihre Buchungen im Fenster zaehlen auch nicht im Rest -- ohne Reihen
    stuende hier ein Schnitt."""
    _jeden_monat(db, "a", (2025, 10), (2026, 5), 15, -4_000, "wohnen/strom", "versorger")
    assert _von(_posten(db), "wohnen/strom") == []
    ohne = ops.abgeleitete_posten(db, "a", FCFG, [], stichtag=HEUTE,
                                  reihen=tk.Reihen(date(2026, 8, 31), date(2024, 9, 1), (), "a"))
    assert [i.amount_cents for i in _von(ohne, "wohnen/strom")] == [round(-32_000 / 12)]


def test_a_deviating_booking_next_to_a_termin_stays_in_the_rest(db):
    """Abschlag monatlich, im Juni eine Nachzahlung beim selben Empfaenger: Sie
    kommt zusaetzlich und zaehlt im Rest ihrer Kategorie (Summe durch zwoelf)."""
    _jeden_monat(db, "a", (2025, 11), (2026, 8), 15, -10_000, "wohnen/strom", "versorger")
    _buche(db, "a", "2026-06-20", -30_000, "wohnen/strom", "versorger")
    posten = _von(_posten(db), "wohnen/strom")
    assert sorted((i.amount_cents, i.every_months) for i in posten) == [
        (-10_000, 1), (round(-30_000 / 12), 1)]


def test_a_payment_that_moved_to_another_account_is_over_on_the_old_one(db):
    """Der Takt gehoert der ganzen Reihe, ob sie laeuft dem Konto: Auf dem alten ist
    sie beendet, auf dem neuen laeuft sie."""
    _jeden_monat(db, "a", (2025, 10), (2026, 5), 1, -50_000, "wohnen/miete", "vermieter")
    _jeden_monat(db, "b", (2026, 6), (2026, 8), 1, -50_000, "wohnen/miete", "vermieter")
    assert _von(_posten(db, "a"), "wohnen/miete") == []
    [neu] = _von(_posten(db, "b"), "wohnen/miete")
    assert (neu.amount_cents, neu.every_months, neu.starts) == (-50_000, 1, date(2026, 9, 1))


def test_a_yearly_premium_is_found_in_september_though_it_was_booked_in_january(db):
    """Das kurze Fenster sieht sie nicht mehr; die Reihe liest 24 Monate."""
    _buche(db, "a", "2025-01-15", -60_000, "wohnen/strom", "versicherer")
    _buche(db, "a", "2026-01-15", -62_000, "wohnen/strom", "versicherer")
    [praemie] = _von(_posten(db), "wohnen/strom")
    assert (praemie.amount_cents, praemie.every_months) == (-62_000, 12)
    assert praemie.starts == date(2027, 1, 1)


# ------------------------------------------------- Schreibweisen zusammengefuehrt


def test_a_yearly_payment_in_two_spellings_is_one_item_once_the_household_merged_them(db):
    """Die alte Schreibweise laeuft noch, ihr Termin ist ueberfaellig: Sie kommt im ersten
    offenen Monat, und die neue noch einmal zu ihrem Termin. Zusammengefuehrt ist es ein
    Posten im Jahr, ein Jahr nach dem letzten Termin."""
    _buche(db, "a", "2025-07-24", -7_200, "wohnen/strom", "steuer alt")
    _buche(db, "a", "2026-07-24", -7_200, "wohnen/strom", "steuer neu")
    getrennt = sorted((i.amount_cents, i.starts) for i in _von(_posten(db), "wohnen/strom"))
    assert getrennt == [(-7_200, date(2026, 9, 1)), (-7_200, date(2027, 7, 1))]

    reihen.zusammenfuehren(db, "steuer alt", "steuer neu")
    [steuer] = _von(_posten(db), "wohnen/strom")
    assert (steuer.amount_cents, steuer.every_months, steuer.starts) == (
        -7_200, 12, date(2027, 7, 1))
    assert steuer.herkunft.herleitung.startswith("steuer neu: jährlich")


# ------------------------------------------------------------------- Einmalig


def test_a_booking_the_household_set_to_einmalig_is_not_measured(db):
    kennung = _buche(db, "a", "2026-07-10", -60_000, "konsum/essen", "moebelhaus")
    assert [i.amount_cents for i in _von(_posten(db), "konsum/essen")] == [-5_000]
    reihen.einmalig_setzen(db, kennung, True)
    assert _von(_posten(db), "konsum/essen") == []


def test_a_category_with_the_flag_einmalig_is_neither_measured_nor_a_series(db):
    _jeden_monat(db, "a", (2025, 10), (2026, 8), 5, -90_000,
                 "immobilie/kaufnebenkosten", "bank")
    assert _posten(db) == []


# -------------------------------------------------- Gehalt: eine Quelle, kein Doppel


def _gehalt_mit_quartalszahlung(db, kategorie_zulage: str):
    """Gehalt jeden Monat; dazu im Oktober (beide Jahre) drei Zahlungen innerhalb von
    drei Tagen bei einem zweiten Zahler: eine jaehrliche Reihe."""
    _jeden_monat(db, "a", (2026, 2), (2026, 8), 28, 400_000, "einkommen/gehalt", "arbeitgeber")
    for jahr in (2024, 2025):
        for tag, cents in ((28, 100_000), (29, 100_000), (30, 100_000)):
            _buche(db, "a", f"{jahr}-10-{tag}", cents, kategorie_zulage, "zulagenkasse")


def test_the_gehalt_is_measured_once_and_the_floor_replaces_it_once(db):
    """Das Gehalt hat eine eigene Quelle (den Floor der Annahmen). Eine jaehrliche Reihe
    in derselben Kategorie, etwa Zahlungen des Arbeitgebers, die im Oktober zusammenfallen,
    stuende als zweiter Posten unter demselben Etikett, und der Floor ersetzte BEIDE:
    im Oktober zweimal das Gehalt."""
    _gehalt_mit_quartalszahlung(db, "einkommen/gehalt")
    items = _von(_posten(db), "einkommen/gehalt")
    assert [(i.every_months, i.starts) for i in items] == [(1, None)]
    assert items[0].herkunft.herleitung.startswith("Summe ")

    floor = 450_000
    projektion = fc.project(account_id="a", opening_cents=0, start=HEUTE, months=3,
                            recurring=items, income_overrides={"einkommen/gehalt": floor})
    assert [r.detail["einkommen/gehalt"] for r in projektion.rows] == [floor] * 3


def test_a_category_without_a_fixed_figure_does_get_its_yearly_series(db):
    """Dieselben Zahlungen in einer Kategorie ohne Floor sind eine Reihe mit Termin."""
    _gehalt_mit_quartalszahlung(db, "einkommen/zulage")
    [zulage] = _von(_posten(db), "einkommen/zulage")
    assert (zulage.amount_cents, zulage.every_months) == (300_000, 12)
    assert zulage.starts == date(2026, 10, 1)


# --------------------------------------------------------------- Zusammenhaenge


def test_the_series_of_an_account_come_from_its_own_bookings(db):
    _jeden_monat(db, "a", (2025, 10), (2026, 8), 1, -50_000, "wohnen/miete", "vermieter")
    _jeden_monat(db, "b", (2026, 6), (2026, 8), 1, -20_000, "wohnen/miete", "vermieter")
    haushalt = ops.reihen_vor(db, HEUTE, [], fcfg=FCFG)
    [auf_a] = haushalt.fuer_konto("a").reihen
    [auf_b] = haushalt.fuer_konto("b").reihen
    assert auf_a.beitrag.betrag_je_termin == -50_000
    assert auf_b.beitrag.betrag_je_termin == -20_000
    assert haushalt.fuer_konto("a") is haushalt.fuer_konto("a")
    assert haushalt.fuer_konto("a").konto == "a" and haushalt.konto == ""
    assert haushalt.fuer_konto("a").ohne(["wohnen/miete"]).reihen == ()
    assert haushalt.fuer_konto("a").ohne([]) is haushalt.fuer_konto("a")


def test_taking_bookings_out_gives_the_series_that_never_read_them(db):
    """Ein Wegfall rechnet die Reihen ohne die Buchungen seiner Reihe. Sie neu aus dem
    Hauptbuch zu lesen kostete je Konto und Zeile eine Abfrage ueber 24 Monate; die
    Reihen des Haushalts nehmen die Buchungen selbst heraus und erkennen nur neu, was
    sie trug."""
    miete = _jeden_monat(db, "a", (2025, 10), (2026, 8), 1, -50_000, "wohnen/miete", "vermieter")
    strom = _jeden_monat(db, "a", (2025, 10), (2026, 8), 15, -4_000, "wohnen/strom", "versorger")
    voll = ops.reihen_vor(db, HEUTE, [], fcfg=FCFG)
    for weg in (frozenset(miete), frozenset(miete[2:4]), frozenset(miete[:2] + strom[:1]),
                frozenset()):
        assert voll.ohne_buchungen(weg).reihen == ops.reihen_vor(
            db, HEUTE, [], ohne_reihen=weg, fcfg=FCFG).reihen
    assert [r.kategorie for r in voll.ohne_buchungen(miete).reihen] == ["wohnen/strom"]
    # Zwei Monate fehlen mitten in der Reihe: ihr Takt ist ein anderer Befund.
    assert voll.ohne_buchungen(miete[2:4]).reihen != voll.reihen
    assert voll.ohne_buchungen([]) is voll
    # Ein Konto, das schon seine Sicht hat, bleibt, wie es ist.
    assert voll.fuer_konto("a").ohne_buchungen(miete) is voll.fuer_konto("a")


def test_a_preview_checks_that_the_series_belong_to_its_kind(db):
    _jeden_monat(db, "a", (2025, 10), (2026, 8), 1, -50_000, "wohnen/miete", "vermieter")
    haushalt = ops.reihen_vor(db, HEUTE, [], fcfg=FCFG)
    with pytest.raises(ValueError, match="Kontoprognose"):
        ops.vorschau_konto(
            since="2025-09-01", until="2026-08-31", fenster_monate=12, exclude=None,
            include_transfers=False, deckung=None, escalation_pa=0.0, ends=None,
            ohne=None, reihen=haushalt)
    with pytest.raises(ValueError, match="Kontoprognose"):
        fs.Vorschau(reihe="konto", regeln=vf.KONTOPROGNOSE,
                    ausschluss=Ausschluss(), je_block=False, since="2025-09-01",
                    fenster_monate=12, reihen=haushalt)


def test_two_items_under_one_label_are_described_together():
    reihe = Posten(label="x", cents=-100, quelle="gemessen", herleitung="A: monatlich",
                   verweis="x")
    rest = Posten(label="x", cents=-50, quelle="gemessen", herleitung="Schnitt −0,50 €",
                  verweis="x")
    assert ops._zusammen(None, reihe) is reihe
    beide = ops._zusammen(reihe, rest)
    assert beide.herleitung == "A: monatlich | Schnitt −0,50 €"
    assert (beide.label, beide.quelle, beide.verweis) == ("x", "gemessen", "x")


def test_the_kontoprognose_table_has_no_long_window_left():
    assert not hasattr(vf, "langes_fenster") and not hasattr(vf, "jahresposten")
    assert "since_fixkosten" not in vf.Einstellung.__dataclass_fields__
    assert "since_fixkosten" not in fs.Vorschau.__dataclass_fields__
