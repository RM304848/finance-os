"""Der Stichtag als Eingabe und der Verlauf der getippten Staende (Schritt 3.4).

Zwei Dinge, die die Wirkung gegenueber dem Vormonat braucht: `eingaben(bis=...)`
liest das Hauptbuch so, wie es am Monatsende `bis` aussah, und
`bestaende.zum` liefert die Staende von damals -- belegte aus dem Auszug,
getippte aus dem Verlauf. Alles erfunden, mit runden Zahlen.
"""

from __future__ import annotations

import copy
import dataclasses
from datetime import date
from pathlib import Path

import pytest
import yaml

from finctl import bestaende as best
from finctl.forecast import abgleich as ag
from finctl.forecast import jahre as jm
from finctl.forecast import ziele as zl
from finctl.ledger.db import connect, init_db

_BESTAND = {"toepfe": {"tagesgeld": 20_000_00, "depot": 100_000_00, "policen": 50_000_00}}

# ----------------------------------------------------------------- Hauptbuch


def _hauptbuch(tmp_path, monate: dict[str, dict[str, int]], *, konto: str = "a"):
    """Ein Konto mit einem Auszug je Monat. `monate`: "2025-03" -> {Kategorie: Cent}."""
    c = connect(init_db(tmp_path / "t.db"))
    c.execute("INSERT INTO accounts (id, display_name, institution, account_type, "
              "ingest_mode, parser_profile) VALUES (?,?,?,?,?,?)",
              (konto, "A", "X", "giro", "parsed", "p"))
    for kid, kind in (("wohnen", "expense"), ("wohnen/miete", "expense"),
                      ("konsum", "expense"), ("konsum/sonstiges", "expense"),
                      ("einkommen", "income"), ("einkommen/gehalt", "income")):
        c.execute("INSERT INTO mgmt_categories (id, parent_id, name, kind, fixkosten) "
                  "VALUES (?,?,?,?,?)", (kid, kid.split("/")[0] if "/" in kid else None,
                                         kid, kind, int(kid == "wohnen/miete")))
    saldo, n = 0, 0
    for i, (monat, buchungen) in enumerate(sorted(monate.items())):
        erster = date.fromisoformat(monat + "-01")
        summe = sum(buchungen.values())
        sid = c.execute(
            "INSERT INTO statements (account_id, source_path, source_name, file_sha256, "
            "period_start, period_end, balance_start_cents, balance_end_cents, "
            "parser_profile, parser_version, status, imported_at) "
            "VALUES (?,?,?,?,?,?,?,?,'p','1','imported','now')",
            (konto, "x", "x", f"sha{i}", erster.isoformat(),
             ag._month_end(erster).isoformat(), saldo, saldo + summe)).lastrowid
        saldo += summe
        for tag, (kategorie, cents) in enumerate(sorted(buchungen.items()), start=1):
            n += 1
            tid = c.execute(
                "INSERT INTO transactions (account_id, statement_id, booking_date, "
                "amount_cents, raw_text, seq_in_statement, dedup_hash, created_at) "
                "VALUES (?,?,?,?,'x',?,?,'now')",
                (konto, sid, erster.replace(day=tag).isoformat(), cents, n,
                 f"h{n}")).lastrowid
            c.execute("INSERT INTO splits (transaction_id, amount_cents, mgmt_category_id, "
                      "source, created_at, updated_at) VALUES (?,?,?,'rule','now','now')",
                      (tid, cents, kategorie))
    c.commit()
    return c


def _monate(von: str, bis: str, buchungen) -> dict[str, dict[str, int]]:
    out, m = {}, date.fromisoformat(von + "-01")
    while m <= date.fromisoformat(bis + "-01"):
        out[f"{m:%Y-%m}"] = dict(buchungen)
        m = ag._plus_monate(m, 1)
    return out


@pytest.fixture
def umschwung(tmp_path):
    """Sechs ruhige Monate (2025-01 bis 06), dann acht mit mehr Konsum, hoeherer
    Miete und mehr Gehalt (bis 2026-02)."""
    ruhig = {"konsum/sonstiges": -250_00, "wohnen/miete": -900_00,
             "einkommen/gehalt": 3_000_00}
    laut = {"konsum/sonstiges": -900_00, "wohnen/miete": -1_100_00,
            "einkommen/gehalt": 5_000_00}
    c = _hauptbuch(tmp_path, {**_monate("2025-01", "2025-06", ruhig),
                              **_monate("2025-07", "2026-02", laut)})
    yield c
    c.close()


# ------------------------------------------------------------------- Fenster

def test_the_window_with_bis_ends_at_that_month_and_without_it_at_the_last_full_one(umschwung):
    assert ag.letzter_vollstaendiger_monat(umschwung) == date(2026, 2, 28)
    assert ag.letzter_vollstaendiger_monat(umschwung, date(2025, 6, 30)) == date(2025, 6, 30)
    # Ein Tag mitten im Monat gilt als dessen Ende, und ein `bis` hinter dem
    # Hauptbuch macht den Monat nicht vollstaendiger, als er ist.
    assert ag.letzter_vollstaendiger_monat(umschwung, date(2025, 6, 5)) == date(2025, 6, 30)
    assert ag.letzter_vollstaendiger_monat(umschwung, date(2027, 1, 31)) == date(2026, 2, 28)
    f = ag.fenster(umschwung, bis=date(2025, 6, 30))
    assert (f.von, f.bis, f.monate) == (date(2025, 1, 1), date(2025, 6, 30), 6)
    f = ag.fenster(umschwung)
    assert (f.von, f.bis, f.monate) == (date(2025, 3, 1), date(2026, 2, 28), 12)


def test_the_day_after_a_month():
    assert ag.folgetag(date(2025, 10, 31)) == date(2025, 11, 1)
    assert ag.folgetag(date(2025, 12, 31)) == date(2026, 1, 1)
    assert ag.folgetag(date(2024, 2, 10)) == date(2024, 3, 1)


# ------------------------------------------------------------------- Eingaben

def _eingaben(c, **kw):
    return jm.eingaben(c, base_year=2026, **_BESTAND, **kw)


def test_eingaben_with_bis_do_not_see_what_was_booked_after(umschwung):
    spaet = _eingaben(umschwung)
    frueh = _eingaben(umschwung, bis=date(2025, 6, 30))
    assert frueh.monat.fenster.bis == date(2025, 6, 30)
    # Sechs Monate Konsum zu 250 Euro, aufs Jahr: der laute Sommer ist nicht da.
    assert frueh.base["konsum"]["konsum/sonstiges"] == -250_00 * 12
    assert spaet.base["konsum"]["konsum/sonstiges"] < frueh.base["konsum"]["konsum/sonstiges"]
    # Dieselbe Miete mit anderem Fenster: vier Monate zu 900 und acht zu 1.100.
    assert frueh.base["fixkosten"]["wohnen/miete"] == -900_00 * 12
    assert spaet.base["fixkosten"]["wohnen/miete"] == -(4 * 900_00 + 8 * 1_100_00)
    # Das Gehalt ist die Untergrenze aus den Annahmen und haengt nicht am Hauptbuch.
    assert frueh.annahmen.gehalt_untergrenze_cents == spaet.annahmen.gehalt_untergrenze_cents


def test_the_base_year_and_the_elapsed_months_follow_bis(umschwung):
    # Ohne Angabe gilt das Jahr des Tages nach `bis`; vergangen sind die Monate
    # dieses Jahres bis `bis`.
    e = jm.eingaben(umschwung, bis=date(2025, 6, 30), **_BESTAND)
    assert (e.monat.base_year, e.monat.vergangen) == (2025, 6)
    e = jm.eingaben(umschwung, bis=date(2025, 12, 31), **_BESTAND)
    assert (e.monat.base_year, e.monat.vergangen) == (2026, 0)
    # Ein ausdruecklich angegebenes Jahr gewinnt.
    assert _eingaben(umschwung, bis=date(2025, 12, 31)).monat.base_year == 2026


def test_bis_changes_only_what_comes_from_the_ledger(umschwung):
    """Alles andere -- Annahmen, Zinssaetze, Kredite, Renten -- liest `eingaben`
    unabhaengig davon, wie weit das Hauptbuch gelesen wird."""
    spaet = _eingaben(umschwung)
    frueh = _eingaben(umschwung, bis=date(2025, 6, 30))
    gleich = dataclasses.replace(
        frueh, monat=spaet.monat, base=spaet.base, base_monate=spaet.base_monate,
        base_reihen=spaet.base_reihen, planzeilen=spaet.planzeilen)
    assert gleich == spaet


def test_eingaben_with_bis_of_the_last_full_month_equal_those_without(umschwung, monkeypatch):
    """Steht heute im Folgemonat, ist `bis` der letzte vollstaendige Monat und
    ergibt dasselbe wie keine Angabe."""
    _heute_ist(monkeypatch, date(2026, 3, 1))
    ohne = jm.eingaben(umschwung, **_BESTAND)
    mit = jm.eingaben(umschwung, bis=date(2026, 2, 28), **_BESTAND)
    assert ohne.monat.base_year == 2026
    assert mit == ohne


@pytest.mark.skipif(not Path("data/finance.db").exists(), reason="kein Hauptbuch")
def test_the_same_holds_on_the_ledger_of_the_household(monkeypatch):
    c = connect()
    try:
        ende = ag.letzter_vollstaendiger_monat(c)
        if ende is None:
            pytest.skip("keine Auszuege")
        for tempo in jm.TEMPI:
            _heute_ist(monkeypatch, ag.folgetag(ende))
            assert jm.eingaben(c, bis=ende, tempo=tempo, **_BESTAND) == jm.eingaben(
                c, tempo=tempo, **_BESTAND)
    finally:
        c.close()


def _heute_ist(monkeypatch, tag: date) -> None:
    """`date.today()` in `jahre` liefert `tag`; alles andere bleibt ein echtes `date`."""
    class Wie(type):
        def __instancecheck__(cls, obj):
            return isinstance(obj, date)

        def __subclasscheck__(cls, sub):
            return issubclass(sub, date)

    class Fest(date, metaclass=Wie):
        def __new__(cls, *a, **k):
            return date(*a, **k)

        @classmethod
        def today(cls):
            return tag

    monkeypatch.setattr(jm, "date", Fest)


def test_the_salary_median_asks_the_calendar_not_the_clock_of_sqlite(umschwung, monkeypatch):
    """Ohne `vor` gilt heute -- und das laesst sich festnageln. Frueher fragte
    dieser Zweig `date('now')` in SQL, und ein festgenagelter Tag erreichte ihn nicht."""
    _heute_ist(monkeypatch, date(2025, 5, 15))
    assert jm.gehalt_median_cents(umschwung) == 3_000_00
    assert jm.gehalt_median_cents(umschwung) == jm.gehalt_median_cents(
        umschwung, vor=date(2025, 5, 15))
    # Heute wie am Ende des Ledgers: die acht hoeheren Monate stellen den Median.
    _heute_ist(monkeypatch, date(2026, 3, 1))
    assert jm.gehalt_median_cents(umschwung) == 5_000_00
    # Vor dem ersten Gehalt gibt es nichts zu messen, und der laufende Monat
    # zaehlt nicht, auch am Monatsersten.
    _heute_ist(monkeypatch, date(2025, 1, 20))
    assert jm.gehalt_median_cents(umschwung) is None
    _heute_ist(monkeypatch, date(2025, 2, 1))
    assert jm.gehalt_median_cents(umschwung) == 3_000_00


def test_the_count_of_a_cancelled_contracts_bookings_stops_at_the_end_of_the_window(
        umschwung, monkeypatch):
    """Die Zahl im Rechenweg ("N Buchungen der Reihe") nennt nur, was am Stichtag
    gebucht war."""
    from finctl import abos

    # Die Reihe erkennt sich an der Gegenpartei.
    umschwung.execute("UPDATE transactions SET counterparty_norm = 'vermieter' "
                      "WHERE id IN (SELECT transaction_id FROM splits "
                      "WHERE mgmt_category_id = 'wohnen/miete')")
    hashes = [r[0] for r in umschwung.execute(
        "SELECT t.dedup_hash FROM transactions t JOIN splits s ON s.transaction_id = t.id "
        "WHERE s.mgmt_category_id = 'wohnen/miete' ORDER BY t.booking_date")]
    assert len(hashes) == 14
    vertrag = {"id": "v", "name": "Vertrag", "kategorie": "wohnen/miete", "konto": "a",
               "betrag_cents": -900_00, "takt": 1, "gekuendigt_zum": date(2025, 12, 31),
               "buchungen": hashes}
    monkeypatch.setattr(abos, "alle_vertraege", lambda: [vertrag])
    base = {"fixkosten": {"wohnen/miete": -900_00 * 12}}
    for bis, erwartet in ((None, 14), (date(2025, 6, 30), 6)):
        f = ag.fenster(umschwung, bis=bis)
        [ende] = jm._vertragsenden(umschwung, f, [], base, police_vertraege={"v"})
        assert ende["buchungen"] == erwartet, bis


def test_the_sales_measure_a_propertys_costs_in_the_window_up_to_bis(umschwung):
    umschwung.execute("INSERT INTO properties (id, name, planned_sale_on, sale_price_cents) "
                      "VALUES ('o', 'Objekt', '2027-01-01', 10000000)")
    umschwung.execute("INSERT INTO mgmt_categories (id, name, kind) "
                      "VALUES ('immobilie/kosten', 'kosten', 'expense')")
    umschwung.execute("UPDATE splits SET mgmt_category_id = 'immobilie/kosten', "
                      "property_id = 'o' WHERE mgmt_category_id = 'wohnen/miete'")
    [spaet] = jm.verkaeufe(umschwung, 2026)
    [frueh] = jm.verkaeufe(umschwung, 2026, bis=date(2025, 6, 30))
    assert frueh.kosten_jahr_cents == -900_00 * 12
    assert spaet.kosten_jahr_cents == -(4 * 900_00 + 8 * 1_100_00)


# ---------------------------------------------------------------- der Verlauf

BASIS = {"as_of": date(2026, 9, 11), "balances": [
    {"account_id": "giro", "kind": "giro"},
    {"account_id": "depot-a", "name": "Depot A", "cents": 10_000_00,
     "as_of": date(2026, 9, 11), "kind": "depot"},
    {"account_id": "krypto-b", "name": "Krypto B", "cents": 2_000_00, "kind": "krypto"},
    {"account_id": "police", "name": "Police", "cents": 30_000_00,
     "as_of": date(2026, 4, 1), "kind": "rentenversicherung"},
    {"account_id": "leer", "name": "Ohne Wert", "kind": "depot"}],
    "obligations": []}


def _zeilen(spec, *, auszug=None):
    """Was `zusammenfuehren` liefert, ohne Datenbank: das Konto `giro` kommt aus dem Auszug."""
    out = []
    for item in spec["balances"]:
        row = dict(item)
        if row["account_id"] == "giro":
            row.update(cents=auszug, as_of="2026-09-30", aus_auszug=True)
        out.append(row)
    return {**spec, "balances": out}


def _speichern(spec, key, neu, heute):
    """Ein Speichern wie `/api/bestand`: die Position aendern, den Verlauf nachfuehren."""
    vorher = _zeilen(spec)
    position = best.position(spec, key)
    position.update(neu)
    return best.verlauf_fortschreiben(spec, vorher, _zeilen(spec), key, heute)


def test_the_period_is_the_month_of_the_closing_and_the_year_for_a_policy():
    assert best.periode("depot", date(2026, 10, 4)) == "2026-10"
    assert best.periode("krypto", date(2026, 1, 31)) == "2026-01"
    assert best.periode("rentenversicherung", date(2026, 10, 4)) == "2026"
    assert best.periode(None, date(2026, 10, 4)) == "2026-10"


def test_the_first_change_seeds_every_typed_position_under_the_period_of_its_date():
    spec = copy.deepcopy(BASIS)
    assert _speichern(spec, "depot-a", {"cents": 12_000_00, "as_of": "2026-10-04"},
                      date(2026, 10, 4))
    verlauf = spec["verlauf"]
    # Der Stand von vorher steht unter der Periode seines Datums ...
    assert verlauf["depot-a"]["2026-09"] == {"cents": 10_000_00, "as_of": "2026-09-11"}
    # ... einer ohne eigenes Datum unter dem der Datei ...
    assert verlauf["krypto-b"] == {"2026-09": {"cents": 2_000_00, "as_of": "2026-09-11"}}
    # ... eine Police unter ihrem Jahr ...
    assert verlauf["police"] == {"2026": {"cents": 30_000_00, "as_of": "2026-04-01"}}
    # ... und das Gespeicherte unter der Periode von heute.
    assert verlauf["depot-a"]["2026-10"] == {"cents": 12_000_00, "as_of": "2026-10-04"}
    # Ein Konto aus dem Auszug und eines ohne Betrag haben keinen Eintrag.
    assert "giro" not in verlauf
    assert "leer" not in verlauf


def test_saving_twice_in_a_period_keeps_the_later_one_and_never_loses_an_earlier_period():
    spec = copy.deepcopy(BASIS)
    _speichern(spec, "depot-a", {"cents": 12_000_00, "as_of": "2026-10-04"},
               date(2026, 10, 4))
    _speichern(spec, "depot-a",
               {"cents": 13_000_00, "as_of": "2026-10-20", "gewinn_cents": 3_000_00},
               date(2026, 10, 20))
    assert spec["verlauf"]["depot-a"]["2026-10"] == {
        "cents": 13_000_00, "as_of": "2026-10-20", "gewinn_cents": 3_000_00}
    assert spec["verlauf"]["depot-a"]["2026-09"]["cents"] == 10_000_00
    # Ein Monat spaeter: ein dritter Eintrag, die beiden anderen bleiben.
    _speichern(spec, "depot-a", {"cents": 14_000_00, "as_of": "2026-11-03"},
               date(2026, 11, 3))
    assert sorted(spec["verlauf"]["depot-a"]) == ["2026-09", "2026-10", "2026-11"]
    assert spec["verlauf"]["depot-a"]["2026-10"]["cents"] == 13_000_00


def test_a_save_that_changes_no_stand_writes_nothing():
    spec = copy.deepcopy(BASIS)
    _speichern(spec, "depot-a", {"cents": 12_000_00, "as_of": "2026-10-04"}, date(2026, 10, 4))
    vorher = copy.deepcopy(spec)
    # Derselbe Wert mit demselben Datum noch einmal, und nur die Notiz.
    assert not _speichern(spec, "depot-a", {"cents": 12_000_00, "as_of": "2026-10-04"},
                          date(2026, 10, 20))
    assert not _speichern(spec, "depot-a", {"notiz": "nur eine Notiz"}, date(2026, 10, 20))
    assert spec["verlauf"] == vorher["verlauf"]
    # Und ganz ohne vorhandenen Verlauf: ein Speichern ohne Aenderung legt keinen an.
    leer = copy.deepcopy(BASIS)
    assert not _speichern(leer, "depot-a", {"cents": 10_000_00, "as_of": "2026-09-11"},
                          date(2026, 10, 4))
    assert "verlauf" not in leer


def test_the_gain_belongs_to_the_stand():
    spec = copy.deepcopy(BASIS)
    _speichern(spec, "depot-a", {"cents": 12_000_00, "as_of": "2026-10-04",
                                 "gewinn_cents": 2_000_00}, date(2026, 10, 4))
    assert spec["verlauf"]["depot-a"]["2026-10"]["gewinn_cents"] == 2_000_00
    assert "gewinn_cents" not in spec["verlauf"]["depot-a"]["2026-09"]
    # Nur der Gewinn aendert sich: auch das ist ein neuer Stand.
    assert _speichern(spec, "depot-a", {"gewinn_cents": 2_500_00}, date(2026, 10, 9))
    assert spec["verlauf"]["depot-a"]["2026-10"] == {
        "cents": 12_000_00, "as_of": "2026-10-04", "gewinn_cents": 2_500_00}


# ----------------------------------------------------------------- Bestaende zum Stichtag

def _datei_mit_verlauf() -> dict:
    """`BASIS`, nachdem im Oktober ein neuer Stand getippt wurde, mit dem Verlauf davor."""
    spec = copy.deepcopy(BASIS)
    spec["balances"][1].update(cents=12_000_00, as_of="2026-10-04", gewinn_cents=2_000_00)
    spec["verlauf"] = {
        "depot-a": {"2026-09": {"cents": 10_000_00, "as_of": "2026-09-11",
                                "gewinn_cents": 1_000_00},
                    "2026-10": {"cents": 12_000_00, "as_of": "2026-10-04",
                                "gewinn_cents": 2_000_00}},
        "police": {"2026": {"cents": 30_000_00, "as_of": "2026-04-01"}}}
    return spec


@pytest.fixture
def staende(tmp_path):
    """Ein Haushalt mit einem Girokonto im Auszug (Saldo je Monat gleich viel mehr)."""
    c = _hauptbuch(tmp_path, _monate("2026-05", "2026-09", {"einkommen/gehalt": 1_000_00}),
                   konto="giro")
    yield c
    c.close()


def test_zum_takes_proven_stands_from_the_ledger_and_typed_ones_from_the_verlauf(staende):
    z = best.zum(staende, date(2026, 8, 31), _datei_mit_verlauf())
    zeile = {r["account_id"]: r for r in z["balances"]}
    # Der Auszug: Mai bis August, je 1.000 Euro mehr.
    assert zeile["giro"]["cents"] == 4_000_00
    assert zeile["giro"]["as_of"] == "2026-08-31"
    assert zeile["giro"]["aus_auszug"]
    # Das Depot von damals: der Eintrag des Abschlusses im September.
    assert zeile["depot-a"]["cents"] == 10_000_00
    assert zeile["depot-a"]["gewinn_cents"] == 1_000_00
    assert zeile["depot-a"]["as_of"] == "2026-09-11"
    # Eine Police gilt das ganze Jahr; ihr Eintrag haengt nicht am Monat.
    assert zeile["police"]["cents"] == 30_000_00


def test_zum_names_what_is_missing_instead_of_counting_it_as_zero(staende):
    z = best.zum(staende, date(2026, 8, 31), _datei_mit_verlauf())
    # Fuer `krypto-b` gibt es keinen Eintrag; `leer` hat auch heute keinen Betrag.
    assert z["fehlt"] == ["Krypto B"]
    assert "krypto-b" not in {r["account_id"] for r in z["balances"]}
    assert "leer" in {r["account_id"] for r in z["balances"]}
    # Zu einem Stichtag ohne jeden Eintrag fehlen alle getippten Staende.
    fruehe = best.zum(staende, date(2026, 6, 30), _datei_mit_verlauf())
    assert fruehe["fehlt"] == ["Depot A", "Krypto B"]
    assert {r["account_id"] for r in fruehe["balances"]} == {"giro", "police", "leer"}


def test_zum_has_the_shape_the_goals_read(staende):
    """`ziele.toepfe` und die anderen lesen die Staende von damals wie die von heute."""
    z = best.zum(staende, date(2026, 8, 31), _datei_mit_verlauf())
    assert zl.toepfe(z) == {"tagesgeld": 4_000_00, "depot": 10_000_00, "policen": 30_000_00}
    assert zl.depot_gewinn(z) == 1_000_00
    assert zl.policen_je_konto(z) == {"police": 30_000_00}
    assert zl.tagesgeld_je_konto(z)["giro"].cents == 4_000_00
    # Heute dagegen: das Depot von heute, mit dem Gewinn von heute.
    jetzt = best.zusammenfuehren(staende, _datei_mit_verlauf())
    assert zl.depot_gewinn(jetzt) == 2_000_00


def test_zum_without_any_verlauf_misses_every_typed_stand(staende):
    z = best.zum(staende, date(2026, 8, 31), BASIS)
    assert z["fehlt"] == ["Depot A", "Krypto B", "Police"]
    assert best.verlauf(BASIS) == {}


# ----------------------------------------------------- Speichern auf der Seite

@pytest.fixture
def seite(tmp_path):
    """Der Server auf der Kopie der Daten; `balances.yaml` wird danach zurueckgelegt."""
    from fastapi.testclient import TestClient

    from finctl.web.server import app

    pfad = Path("config/balances.yaml")
    vorher = pfad.read_bytes()
    yield TestClient(app), pfad
    pfad.write_bytes(vorher)


def _basis() -> dict:
    return yaml.safe_load(Path("config/balances.yaml").read_text(encoding="utf-8"))


def _getippt() -> dict:
    """Eine getippte Position der Haushaltsdatei mit Betrag."""
    c = connect()
    try:
        geparst = best.geparste_konten(c)
    finally:
        c.close()
    for item in _basis()["balances"]:
        if not best.aus_auszug(item, geparst) and item.get("cents") is not None:
            return item
    pytest.skip("keine getippte Position")


def _heutiger_stand(key: str) -> dict | None:
    c = connect()
    try:
        zeilen = best.zusammenfuehren(c, _basis())["balances"]
    finally:
        c.close()
    return best.stand_von(next(z for z in zeilen if best.schluessel(z) == key),
                          _basis().get("as_of"))


@pytest.mark.skipif(not Path("data/finance.db").exists(), reason="kein Hauptbuch")
def test_saving_a_stand_writes_the_verlauf_and_saving_it_again_changes_nothing(seite):
    client, pfad = seite
    item = _getippt()
    key = item.get("account_id") or item["name"]
    heute = date.today()
    davor = _heutiger_stand(key)
    ein = {"key": key, "cents": 123_400_00, "as_of": heute.isoformat()}

    assert client.post("/api/bestand", json=ein).json()["ok"]
    spec = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    periode = best.periode(item.get("kind"), heute)
    assert spec["verlauf"][key][periode] == {"cents": 123_400_00, "as_of": heute.isoformat()}
    # Der alte Stand ist nicht verloren: einmalig dazugekommen, unter der
    # Periode seines Datums.
    alt = best.periode(item.get("kind"), date.fromisoformat(davor["as_of"]))
    if alt != periode:
        assert spec["verlauf"][key][alt] == davor

    gesehen = pfad.read_bytes()
    assert client.post("/api/bestand", json=ein).json()["ok"]
    assert pfad.read_bytes() == gesehen
    # Nur die Notiz: kein neuer Eintrag.
    assert client.post("/api/bestand", json={"key": key, "note": "nur eine Notiz"}).json()["ok"]
    assert yaml.safe_load(pfad.read_text(encoding="utf-8"))["verlauf"] == spec["verlauf"]


@pytest.mark.skipif(not Path("data/finance.db").exists(), reason="kein Hauptbuch")
def test_a_note_or_an_unknown_key_creates_no_verlauf(seite):
    client, pfad = seite
    verlauf = _basis().get("verlauf")
    item = _getippt()
    key = item.get("account_id") or item["name"]
    assert client.post("/api/bestand", json={"key": key, "note": "nur eine Notiz"}).json()["ok"]
    assert _basis().get("verlauf") == verlauf
    # Eine Position, die es nicht gibt, ist keine Position: nichts wird geschrieben.
    gesehen = pfad.read_bytes()
    antwort = client.post("/api/bestand", json={
        "key": "pytest-position", "cents": 12345, "as_of": "2026-09-12"})
    assert antwort.status_code == 404
    assert "pytest-position" not in pfad.read_text(encoding="utf-8")
    assert _basis().get("verlauf") == verlauf
    assert pfad.read_bytes() == gesehen
