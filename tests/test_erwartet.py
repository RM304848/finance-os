"""Die erwartete Einnahme: eine Planzeile, die die Messung ersetzt.

Schenkung und Nebentaetigkeit haben kein Muster, aus dem eine Messung sie fortschreiben
koennte. Der Haushalt sagt, was er erwartet; die Buchungen, die dazu gehoeren, sind der
Zeile zugeordnet und zaehlen in keiner Messung. Die Zeile zaehlt voll, mit festem Betrag.

Alles hier ist erfunden: ein Konto, zwei Gegenparteien, runde Betraege.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from finctl.forecast import abgleich as ag
from finctl.forecast import engine as fc
from finctl.forecast import szenarien as sz
from finctl.forecast.konten import reihen_vor
from finctl.web.server import app

client = TestClient(app)
HORIZONT = date(2030, 12, 1)


def _zeile(**kw) -> sz.Line:
    basis = dict(label="Schenkung", amount_cents=20000, frequency="monatlich", kind="erwartet",
                 start=date(2026, 10, 1), category_id="einkommen/schenkung")
    return sz.Line(**{**basis, **kw})


#: Eine Messung, die der Zeile widerspraeche, wenn sie etwas abzoege.
GEMESSEN = {"cents": 480000, "monate": 12, "buchungen": [], "quelle": "zugeordnet"}


def test_the_art_is_known_and_survives_loading():
    assert "erwartet" in sz.KINDS
    klammer = next(k for k in sz.load({"szenarien": [
        {"id": "k", "name": "K", "aktiv": True, "zeilen": [
            {"label": "Schenkung", "art": "erwartet", "amount_cents": 20000,
             "frequenz": "monatlich", "start": "2026-10",
             "kategorie": "einkommen/schenkung"}]}]}) if k.id == "k")
    assert [(z.kind, z.amount_cents, z.frequency) for z in klammer.lines] == [
        ("erwartet", 20000, "monatlich")]


def test_it_counts_in_full_whatever_the_ledger_holds():
    """Eine laufende Planzeile zieht sonst ab, was schon gemessen ist; diese nicht."""
    zeile = _zeile()
    assert sz.restbetrag_je_termin(zeile, GEMESSEN) == 20000
    assert sz.restbetrag_je_termin(zeile, GEMESSEN, steigerung=1.5) == 20000, "kein Wachstum"
    betrag = _zeile(kind="betrag")
    assert sz.restbetrag_je_termin(betrag, GEMESSEN) == 0, "der Vergleich: eine Betragszeile kuerzt"


def test_a_year_counts_the_months_that_are_left():
    zeile = _zeile()
    assert sz.jahreswirkung(zeile, GEMESSEN, 2026, 9, HORIZONT) == 3 * 20000
    assert sz.jahreswirkung(zeile, GEMESSEN, 2027, 0, HORIZONT) == 12 * 20000


@pytest.mark.parametrize("takt, jahr, soll", [
    ("quartalsweise", 2027, 4 * 60000),
    ("jaehrlich", 2028, 60000),
    ("einmalig", 2026, 60000),
])
def test_every_frequency_counts_its_dates(takt, jahr, soll):
    zeile = _zeile(amount_cents=60000, frequency=takt)
    assert sz.jahreswirkung(zeile, GEMESSEN, jahr, 0, HORIZONT) == soll


def test_it_ends_with_its_end():
    zeile = _zeile(end=date(2027, 3, 1))
    assert sz.jahreswirkung(zeile, GEMESSEN, 2027, 0, HORIZONT) == 3 * 20000
    assert sz.jahreswirkung(zeile, GEMESSEN, 2028, 0, HORIZONT) == 0


def test_a_one_off_with_bookings_still_counts():
    """Eine einmalige Betragszeile mit Buchungen gilt als gebucht und zaehlt null; die
    erwartete Einnahme ist keine Anzahlung, die bezahlt wurde."""
    erwartet = _zeile(frequency="einmalig", amount_cents=60000, buchungen=["a"])
    betrag = _zeile(frequency="einmalig", amount_cents=60000, buchungen=["a"], kind="betrag")
    assert sz.jahreswirkung(erwartet, GEMESSEN, 2026, 0, HORIZONT) == 60000
    assert sz.jahreswirkung(betrag, GEMESSEN, 2026, 0, HORIZONT) == 0


def test_the_page_shows_a_month_for_a_yearly_line():
    assert sz.restwirkung_monatlich(_zeile(frequency="jaehrlich", amount_cents=120000),
                                    GEMESSEN) == 10000


# ----------------------------------------------------------------- Hauptbuch

@pytest.fixture
def db():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(open("finctl/ledger/schema.sql", encoding="utf-8").read())
    c.execute("INSERT INTO accounts (id, display_name, institution, account_type, "
              "ingest_mode, parser_profile) VALUES ('giro', 'giro', 'X', 'giro', 'parsed', 'p')")
    c.execute("INSERT INTO statements (account_id, source_path, source_name, file_sha256, "
              "period_start, period_end, balance_start_cents, balance_end_cents, "
              "parser_profile, parser_version, status, imported_at) VALUES ('giro', 'p', 'n', "
              "'s', '2025-01-01', '2026-09-30', 0, 0, 'p', '1', 'imported', 't')")
    for kat, eltern, art in (("einkommen", None, "income"),
                             ("einkommen/gehalt", "einkommen", "income"),
                             ("einkommen/gehalt-nebentaetig", "einkommen", "income"),
                             ("einkommen/schenkung", "einkommen", "income")):
        c.execute("INSERT INTO mgmt_categories (id, parent_id, name, kind) VALUES (?, ?, ?, ?)",
                  (kat, eltern, kat, art))
    buchungen = [
        # Vier Zuwendungen desselben Gebers, davon eine nicht angehakt.
        ("g1", "2026-03-10", 60000, "geber-a", "einkommen/schenkung"),
        ("g2", "2026-06-10", 60000, "geber-a", "einkommen/schenkung"),
        ("g3", "2026-09-10", 60000, "geber-a", "einkommen/schenkung"),
        # Eine Einnahme eines anderen Gebers in derselben Kategorie.
        ("f1", "2026-05-10", 30000, "geber-b", "einkommen/schenkung"),
        ("n1", "2026-07-20", 120000, "hochschule", "einkommen/gehalt-nebentaetig"),
        ("l1", "2026-08-28", 400000, "firma", "einkommen/gehalt"),
    ]
    for n, (h, tag, cents, gegen, kat) in enumerate(buchungen, start=1):
        c.execute("INSERT INTO transactions (id, account_id, statement_id, booking_date, "
                  "amount_cents, counterparty_norm, raw_text, seq_in_statement, dedup_hash, "
                  "created_at) VALUES (?, 'giro', 1, ?, ?, ?, 'x', ?, ?, 't')",
                  (n, tag, cents, gegen, n, h))
        c.execute("INSERT INTO splits (transaction_id, seq, amount_cents, mgmt_category_id, "
                  "source, created_at, updated_at) VALUES (?, 0, ?, ?, 'rule', 't', 't')",
                  (n, cents, kat))
    return c


def _klammer(*zeilen, aktiv=True):
    return [sz.Scenario(id="k", name="Erwartet", active=aktiv, lines=list(zeilen))]


def test_the_bookings_and_their_series_leave_the_measurement(db):
    """Angehakt ist eine Zuwendung; die Reihe (derselbe Geber, dieselbe Kategorie) geht mit.
    Die Einnahme des anderen Gebers ist eine andere Reihe und bleibt gemessen."""
    klammern = _klammer(_zeile(buchungen=["g1"]))
    assert sz.erwartet_zugeordnet(db, klammern) == {"g1", "g2", "g3"}


def test_a_switched_off_plan_gives_the_measurement_back(db):
    assert sz.erwartet_zugeordnet(db, _klammer(_zeile(buchungen=["g1"]), aktiv=False)) == set()


def test_only_an_expected_income_replaces_the_measurement(db):
    """Eine Betragszeile mit Buchungen kuerzt, ersetzt aber nichts."""
    assert sz.erwartet_zugeordnet(db, _klammer(_zeile(kind="betrag", buchungen=["g1"]))) == set()


def test_the_account_forecast_does_not_measure_what_the_line_replaces(db):
    """Der Weg der Kontoprognose: ohne die Hashes steht die Schenkung als Reihe da, mit ihnen
    nicht mehr -- die Zeile bucht sie, die Messung nicht."""
    stichtag = date(2026, 10, 1)

    def kategorien(ohne):
        reihen = reihen_vor(db, stichtag, [], ohne_reihen=frozenset(ohne), fcfg={})
        return {p.label for p in fc.derive_recurring(
            db, "giro", since="2025-10-01", until="2026-09-30",
            ohne=[{"dedup_hashes": sorted(ohne)}] if ohne else None,
            reihen=reihen.fuer_konto("giro"))}

    assert "einkommen/schenkung" in kategorien(set())
    ersetzt = sz.erwartet_zugeordnet(db, _klammer(_zeile(buchungen=["g1", "f1"])))
    assert "einkommen/schenkung" not in kategorien(ersetzt)


def test_a_plan_of_expected_incomes_is_no_variant_of_another_plan():
    """Zwei eingeschaltete Plaene sind meist zwei Varianten einer Entscheidung; die
    Schenkung ist keine, sie gilt neben jedem Plan."""
    erwartet = _klammer(_zeile())[0]
    assert erwartet.nur_erwartet
    assert not _klammer(_zeile(), _zeile(kind="betrag"))[0].nur_erwartet
    assert not sz.Scenario(id="leer", name="Leer").nur_erwartet


def test_the_block_gehalt_is_only_the_salary(db):
    """Eine Unterkategorie ist ein anderes Einkommen: sie zaehlt unter `einkommen_sonst`,
    nicht im Block `gehalt`, den die Jahresrechnung durch die Untergrenze ersetzt."""
    assert ag.block_der_kategorie(db, "einkommen/gehalt") == "gehalt"
    assert ag.block_der_kategorie(db, "einkommen/gehalt-nebentaetig") == "einkommen_sonst"
    assert ag.block_der_kategorie(db, "einkommen/schenkung") == "einkommen_sonst"


# ----------------------------------------------------------------- die Seite

def _yaml() -> dict:
    import yaml

    return yaml.safe_load(Path("config/szenarien.yaml").read_text(encoding="utf-8")) or {}


def _aufraeumen(sid):
    ziel = next((x for x in _yaml().get("szenarien") or [] if x.get("id") == sid), None)
    for i in reversed(range(len(ziel.get("zeilen") or []))) if ziel else ():
        client.post("/api/szenario-zeile", json={"szenario": sid, "index": i, "loeschen": True})
    client.post("/api/szenario", json={"id": sid, "loeschen": True})


def test_the_page_creates_shows_and_edits_an_expected_income():
    sid = "pytest-erwartet"
    _aufraeumen(sid)
    zeile = {"szenario": sid, "label": "Zuschuss", "art": "erwartet", "frequenz": "jaehrlich",
             "amount_cents": 120000, "start": "2027-06", "kategorie": "einkommen/schenkung"}
    try:
        assert client.post("/api/szenario", json={"neu": True, "name": "Pytest Erwartet"}
                           ).json()["id"] == sid
        assert client.post("/api/szenario", json={"id": sid, "aktiv": True}).status_code == 200
        assert client.post("/api/szenario-zeile", json=zeile).status_code == 200
        [gespeichert] = next(x for x in _yaml()["szenarien"] if x["id"] == sid)["zeilen"]
        assert (gespeichert["art"], gespeichert["amount_cents"]) == ("erwartet", 120000)
        assert "Erwartete Einnahme" in client.get("/planung").text

        assert client.post("/api/szenario-zeile-buchungen", json={
            "szenario": sid, "index": 0, "buchungen": ["abc"]}).status_code == 200
        assert client.post("/api/szenario-zeile", json={
            **zeile, "index": 0, "ersetzen": True, "amount_cents": 150000}).status_code == 200
        [geaendert] = next(x for x in _yaml()["szenarien"] if x["id"] == sid)["zeilen"]
        assert geaendert["amount_cents"] == 150000
        assert geaendert["buchungen"] == ["abc"], "die Zuordnung gehoert zur Zeile"
    finally:
        _aufraeumen(sid)


@pytest.mark.parametrize("cents", [-120000, 0])
def test_an_expected_income_is_positive(cents):
    sid = "pytest-erwartet-negativ"
    _aufraeumen(sid)
    try:
        antwort = client.post("/api/szenario-zeile", json={
            "szenario": sid, "label": "Zuschuss", "art": "erwartet", "frequenz": "monatlich",
            "amount_cents": cents, "start": "2027-06", "kategorie": "einkommen/schenkung"})
        assert antwort.status_code == 400
        assert "positiv" in antwort.json()["error"]
    finally:
        _aufraeumen(sid)


def test_the_salary_card_counts_exactly_the_salary_category(db):
    """Die Nebentaetigkeit ist eine erwartete Einnahme und gehoert nicht ins Gehalt."""
    from finctl.web.routen.start import _kacheln

    karte = _kacheln(db, "2026")
    assert karte["gehalt"] == 400000
    assert karte["einnahmen"] > karte["gehalt"]
