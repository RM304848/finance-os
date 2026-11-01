"""Die Jahresrechnung: wie viel Prozent von Barista FIRE stehen 2045?

Getestet wird die Struktur, nicht eine Eurozahl. Vier Eigenschaften
unterscheiden sie von einer Hochrechnung auf einem Bierdeckel, und jede davon
wurde beim Bauen einmal falsch gemacht:

* Das Basisjahr laeuft nur ueber seine RESTmonate. Die vergangenen stecken
  schon im Anfangsbestand, und sie ein zweites Mal zu projizieren zaehlte bei
  acht von zwoelf Monaten zwei Drittel eines Jahres doppelt.
* Kreditraten kommen aus dem Tilgungsplan und werden NICHT inflationiert.
  Eine Annuitaet ist nominal fest und wird real jedes Jahr billiger.
* Das Ziel skaliert mit der Inflation des Szenarios. Ohne das lieferte das
  pessimistische Szenario mehr Endkapital als die Basis -- oekonomisch
  richtig, weil Inflation Schuldner beguenstigt, und als Vergleich unsinnig.
* Sie benutzt dieselben Bloecke wie die Abstimmzeile, sonst prueft die
  Abstimmzeile etwas anderes als das, was gerechnet wird.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from pathlib import Path

import pytest
import yaml

from finctl.forecast import abgleich as ag
from finctl.forecast import jahre as jm
from finctl.forecast import verfahren as vf

DB = Path("data/finance.db")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="no ledger present")


@pytest.fixture
def conn():
    from finctl.ledger.db import connect

    c = connect()
    yield c
    c.close()


def test_the_base_year_runs_only_over_its_remaining_months(conn):
    """The elapsed months are already in the opening balance."""
    result = jm.project(conn, base_year=2026, end_year=2030, opening_cents=0)
    ende = ag.letzter_vollstaendiger_monat(conn)
    elapsed = ende.month if ende.year == 2026 else 0
    base = result.year(2026)
    later = result.year(2027)
    share = (12 - elapsed) / 12
    assert base.blocks["konsum"] == pytest.approx(
        later.blocks["konsum"] / (1 + 0.02) * share, rel=0.02)


def test_loan_payments_are_not_inflated(conn, ohne_plaene):
    """An annuity is fixed in nominal terms.

    Inflating it would erase the borrower's quiet advantage -- the payment
    that gets cheaper in real terms every year.
    """
    result = jm.project(conn, base_year=2026, end_year=2035, opening_cents=0,
                        szenarien=ohne_plaene)
    payments =[abs(result.year(y).blocks["kredit"]) for y in (2028, 2029, 2030)]
    # Constant while all three schedules run, never rising with prices.
    assert payments[0] == payments[1] == payments[2]


def test_costs_are_inflated(conn):
    result = jm.project(conn, base_year=2026, end_year=2035, opening_cents=0)
    a, b = (abs(result.year(y).blocks["konsum"]) for y in (2028, 2029))
    assert b > a
    assert b / a == pytest.approx(1.02, rel=0.001)


def test_investment_flows_are_left_out(conn):
    """A purchase moves money from the account into the depot, and both count
    towards the goal. Booking it as a cost would subtract it twice."""
    result = jm.project(conn, base_year=2026, end_year=2027, opening_cents=0)
    assert "investment" not in result.year(2027).blocks


def test_the_target_scales_with_the_scenario_inflation(tmp_path):
    """Otherwise the pessimistic scenario wins.

    Higher inflation lifts income and costs together while the loan payment
    stays fixed, so a net saver with a fixed-rate mortgage ends up nominally
    better off. That is economically right; leaving a target that was set in
    today's prices as a fixed nominal figure is what made the comparison
    nonsense.
    """
    other = tmp_path / "assumptions.hoch.yaml"
    other.write_text(yaml.safe_dump({"inflation_pa": 0.03}), encoding="utf-8")
    base = jm.target_under("config/assumptions.yaml", declared_cents=83_100_000,
                           declared_inflation=0.02, years=19)
    higher = jm.target_under(other, declared_cents=83_100_000,
                             declared_inflation=0.02, years=19)
    assert base == 83_100_000
    assert higher > base


def test_a_scenario_is_a_different_file(conn):
    """No feature, no table -- a copy of assumptions.yaml with other values."""
    optimistic = Path("config/assumptions.optimistisch.yaml")
    if not optimistic.exists():
        pytest.skip("kein Szenario abgelegt")
    base = jm.project(conn, end_year=2045, opening_cents=9_618_113)
    other = jm.project(conn, end_year=2045, opening_cents=9_618_113,
                       assumptions=optimistic)
    assert other.final_cents > base.final_cents


def test_the_projection_and_the_reconciliation_share_their_blocks():
    """Two partitions would make the reconciliation line check the wrong thing.

    Its zero differences would then earn trust they had not paid for.
    """
    known = {b.id for b in ag.bloecke()}
    assert set(jm.FROM_BASE) | set(jm.SPECIAL) | set(jm.IGNORED) == known


def _netto() -> int:
    """Was die Objekte mit Prognose zusammen im Monat abwerfen."""
    from finctl import objekte

    liste = objekte.prognosen()
    if not liste:
        pytest.skip("kein Objekt mit Prognose")
    return sum(p.netto_cents for p in liste)


def test_the_object_comes_from_the_assumption_not_one_measured_month(conn):
    """Genau ein Mietmonat steht im Ledger.

    Ueber acht vollstaendige Monate gemittelt sind das 163 statt 1.420. Diese
    Verwaesserung zwanzig Jahre fortzuschreiben waere der groesste stille
    Fehler im Modell gewesen -- sie kostete 445.000 im Endkapital, also mehr
    als Gehalt und Rendite zusammen.
    """
    result = jm.project(conn, base_year=2026, end_year=2030, opening_cents=0)
    voll = result.year(2028).blocks[ag.OBJEKT]
    # Ein voller Jahrgang liegt nahe am Zwoelffachen der Annahme, nicht beim
    # gemessenen Achtel.
    assert voll > _netto() * 11
    assert voll < _netto() * 13


def test_the_leasehold_stops_producing_at_its_end_date(conn):
    """Kein Eigentum: am Ende der Laufzeit null Einnahme und null Restwert.

    Genau das unterscheidet ein Leasehold vom Eigentum, und es ist der
    Grund, warum der Stichtag der Jahresrechnung dort liegt.
    """
    from finctl import objekte

    enden = [p.bis for p in objekte.prognosen()]
    if not enden or None in enden:
        pytest.skip("kein Objekt mit Ende der Vermietung")
    ende = max(enden).year
    result = jm.project(conn, base_year=2026, end_year=ende + 2, opening_cents=0)
    assert result.year(ende).blocks[ag.OBJEKT] > 0
    assert result.year(ende + 1).blocks[ag.OBJEKT] == 0
    assert result.year(ende + 2).blocks[ag.OBJEKT] == 0


def test_the_base_year_counts_only_the_months_still_to_come(conn):
    """Der August steht schon im Ledger und im Anfangsbestand."""
    jahr = date.today().year
    result = jm.project(conn, base_year=jahr, end_year=jahr + 1, opening_cents=0)
    ende = ag.letzter_vollstaendiger_monat(conn)
    elapsed = ende.month if ende.year == jahr else 0
    assert result.year(jahr).blocks[ag.OBJEKT] == _netto() * (12 - elapsed)


# ---------------------------------------------------- Crossing Point, Schritt 9

def test_the_crossing_point_ignores_salary(conn):
    """Das ist der ganze Punkt der Kennzahl.

    Ein Zielbetrag sagt, ob man aufhören KANN -- Kapital, das sich verzehren
    lässt. Der Wendepunkt sagt, ab wann man nicht mehr MUSS. Man kann das eine
    erreichen und das andere nie, und genau das ist hier der Fall: 103 %
    Kapitaldeckung 2045 bei 59 % laufender Deckung.
    """
    assert "gehalt" not in jm.PASSIV
    assert "einmalig" not in jm.PASSIV


def test_a_one_off_does_not_count_as_coverage(conn):
    """Eine grosse Erstattung liesse ein Jahr wie erreichte Unabhängigkeit
    aussehen. Sie deckt keinen laufenden Bedarf."""
    assert "einmalig" not in jm.PASSIV
    assert "einmalig" not in jm.BEDARF


def test_loan_payments_count_as_ongoing_need(conn):
    """Sie laufen weiter, ob gearbeitet wird oder nicht -- und sie enden von
    selbst, was der Wendepunkt sichtbar machen soll."""
    assert "kredit" in jm.BEDARF


def test_the_crossing_year_must_hold_to_the_end(conn):
    """Ein einzelnes gutes Jahr zwischen zwei schlechten ist kein Wendepunkt.

    Ohne diese Bedingung meldete ein Jahr mit hoher Objektauslastung
    Unabhängigkeit, die im Folgejahr wieder weg ist.
    """
    result = jm.project(conn, base_year=2026, end_year=2045, opening_cents=0)
    jahr = result.crossing_year
    if jahr is None:
        pytest.skip("auf den aktuellen Annahmen nicht erreicht")
    spaeter = [y for y in result.years if y.year >= jahr]
    assert all(jm._covers(y) for y in spaeter)


def test_coverage_is_a_percentage_of_the_ongoing_need(conn):
    result = jm.project(conn, base_year=2026, end_year=2030, opening_cents=0)
    pct = result.coverage_pct(2028)
    assert 0 < pct < 200


# ------------------------------------------------------------ die Kaskade

_SAETZE = dict(satz_tagesgeld=0.0, satz_depot=0.07,
               vorab_satz=0.0253 * 0.7, steuer_quote=0.7 * 0.26375)


def test_the_cascade_fills_the_buffer_before_the_depot():
    k = jm.kaskade(10_000_00, 0, 0, sparrate=30_000_00, grenze=35_000_00, **_SAETZE)
    assert (k["tagesgeld"], k["depot"], k["ins_depot"]) == (35_000_00, 5_000_00, 5_000_00)


def test_below_the_buffer_nothing_moves_and_the_depot_is_not_sold():
    k = jm.kaskade(10_000_00, 50_000_00, 0, sparrate=5_000_00, grenze=35_000_00, **_SAETZE)
    assert k["tagesgeld"] == 15_000_00
    assert k["ins_depot"] == 0


def test_a_negative_tagesgeld_is_not_quietly_covered_from_the_depot():
    """Fruher deckte sich ein Minus von selbst aus dem Depot.

    Beim Eigenheim leerte das unbemerkt das ganze Depot -- eine Entnahme von
    74.259, die niemand eingetragen hatte. Jetzt bleibt das Minus stehen und
    sagt damit, was es sagen soll: so ist der Plan nicht finanziert. Wer
    verkaufen will, schreibt eine Zeile auf ein Depotkonto.
    """
    k = jm.kaskade(10_000_00, 50_000_00, 0, sparrate=-30_000_00, grenze=35_000_00,
                   **_SAETZE)
    assert k["tagesgeld"] == -20_000_00
    assert k["ins_depot"] == 0
    assert k["depot"] > 50_000_00, "das Depot waechst weiter, statt geleert zu werden"


def test_an_entered_withdrawal_takes_from_the_depot_and_not_from_the_tagesgeld():
    """Die eingetragene Entnahme ist der Ersatz fuer die stille Deckung."""
    ohne = jm.kaskade(10_000_00, 50_000_00, 0, sparrate=0, grenze=35_000_00, **_SAETZE)
    mit = jm.kaskade(10_000_00, 50_000_00, 0, sparrate=0, grenze=35_000_00,
                     depot_abfluss=-20_000_00, **_SAETZE)
    assert mit["tagesgeld"] == ohne["tagesgeld"], "das Tagesgeld bleibt unberuehrt"
    # Dazu die Steuer auf den Gewinnanteil des Verkaufs, ebenfalls aus dem Depot.
    assert mit["verkaufsteuer"] > 0
    assert mit["depot"] == ohne["depot"] - 20_000_00 - mit["verkaufsteuer"]


def test_a_sale_is_taxed_on_its_gain_share_only():
    """Einstand 60.000, Wert 100.000: 40 % jedes verkauften Euros sind Gewinn."""
    satz = dict(satz_tagesgeld=0.0, satz_depot=0.0, vorab_satz=0.0, steuer_quote=0.26375)
    k = jm.kaskade(0, 100_000_00, 0, sparrate=0, grenze=0, depot_abfluss=-10_000_00,
                   einstand=60_000_00, **satz)
    assert k["verkaufsteuer"] == round(10_000_00 * 0.4 * 0.26375)
    assert k["einstand"] == 54_000_00, "der Verkauf nimmt seinen Anteil am Einstand mit"
    # Ohne Gewinn keine Steuer; ein Kauf legt seinen Betrag zum Einstand.
    ohne = jm.kaskade(0, 100_000_00, 0, sparrate=0, grenze=0, depot_abfluss=-10_000_00,
                      **satz)
    assert ohne["verkaufsteuer"] == 0
    kauf = jm.kaskade(50_000_00, 100_000_00, 0, sparrate=0, grenze=10_000_00,
                      einstand=60_000_00, **satz)
    assert kauf["einstand"] == 100_000_00


def test_the_advance_lump_sum_counts_towards_the_cost_basis():
    """Schon versteuerte Vorabpauschale wird beim Verkauf nicht noch einmal versteuert."""
    satz = dict(satz_tagesgeld=0.0, satz_depot=0.05, vorab_satz=0.02, steuer_quote=0.26375)
    k = jm.kaskade(0, 100_000_00, 0, sparrate=0, grenze=0, **satz)
    assert k["einstand"] == 100_000_00 + 2_000_00


def test_the_depot_pays_the_advance_lump_sum_tax_without_selling():
    """Die Vorabpauschale faellt jedes Jahr an, und nur auf das Depot."""
    k = jm.kaskade(0, 100_000_00, 0, sparrate=0, grenze=0, **_SAETZE)
    vorab = round(100_000_00 * _SAETZE["vorab_satz"])
    assert k["steuer"] == round(vorab * _SAETZE["steuer_quote"])
    assert k["depot"] == 100_000_00 + 7_000_00 - k["steuer"]
    assert k["rendite"] == 7_000_00 - k["steuer"]


def test_nothing_is_created_or_lost_between_the_pots():
    k = jm.kaskade(40_000_00, 20_000_00, 30_000_00, sparrate=12_345_00, grenze=45_000_00,
                   satz_tagesgeld=0.025, satz_depot=0.07,
                   vorab_satz=_SAETZE["vorab_satz"], steuer_quote=_SAETZE["steuer_quote"])
    vorher = 40_000_00 + 20_000_00 + 30_000_00
    assert k["tagesgeld"] + k["depot"] + k["policen"] == vorher + k["rendite"] + 12_345_00


def test_the_pots_add_up_and_the_tagesgeld_stays_under_its_limit(conn):
    result = jm.project(conn, base_year=2026, end_year=2035, puffer_cents=33_000_00,
                        toepfe={"tagesgeld": 50_000_00, "depot": 7_000_00, "policen": 36_000_00})
    vorher = None
    for y in result.years:
        assert y.tagesgeld_cents + y.depot_cents + y.policen_cents == y.closing_cents
        assert y.tagesgeld_cents <= y.puffer_grenze_cents
        if vorher is not None:
            assert y.opening_cents == vorher.closing_cents
        vorher = y


def test_the_pots_split_the_liquid_total():
    from finctl.forecast import ziele as zm

    bestand = {"balances": [
        {"kind": "giro", "cents": 1000}, {"kind": "tagesgeld", "cents": 5000},
        {"kind": "depot", "cents": 700}, {"kind": "krypto", "cents": None},
        {"kind": "rentenversicherung", "cents": 300}],
        "obligations": [{"cents": 2000}]}
    assert zm.toepfe(bestand) == {"tagesgeld": 6000, "depot": 700, "policen": 300}
    # Die Verbindlichkeit bleibt im Tagesgeld; sie geht mit dem Notgroschen ab.
    assert sum(zm.toepfe(bestand).values()) == zm.liquid_cents(bestand) + 2000


def test_a_goal_extrapolates_the_pots_of_what_is_ticked():
    from finctl.forecast import ziele as zm

    assert zm.toepfe_fuer_basis(("depot", "krypto")) == ("depot",)
    assert zm.toepfe_fuer_basis(("depot", "rentenversicherung")) == ("depot", "policen")
    assert zm.toepfe_fuer_basis(("dkb-giro",)) is None
    assert zm.toepfe_fuer_basis(None) is None


def test_the_policies_grow_by_the_interest_they_are_given_without_the_advance_tax():
    """Die Kaskade kennt keinen Satz der Policen: Zins und Beitraege kommen als Zahl,
    und eine Vorabpauschale faellt auf sie nicht an."""
    k = jm.kaskade(0, 0, 100_000_00, sparrate=0, grenze=0, zins_policen=6_000_00,
                   einzahlung_policen=3_600_00, **_SAETZE)
    assert k["policen"] == 109_600_00
    assert k["rendite"] == 6_000_00
    assert k["steuer"] == 0
    # Ohne Zins und Beitrag bleibt der Topf, wie er ist.
    assert jm.kaskade(0, 0, 100_000_00, sparrate=0, grenze=0, **_SAETZE)["policen"] == 100_000_00


def test_the_cascade_limit_is_the_tagesgeld_goal_typed_by_hand():
    from finctl.forecast import ziele as zm

    ziele = {"ziele": [{"id": "tagesgeld-puffer", "cents": 3_300_000},
                       {"id": "barista-fire", "cents": 1}]}
    assert zm.puffer_cents(ziele) == 3_300_000
    assert zm.puffer_cents({"ziele": []}) is None


def test_without_a_tagesgeld_goal_nothing_moves_to_the_depot(conn):
    result = jm.project(conn, base_year=2026, end_year=2032,
                        toepfe={"tagesgeld": 200_000_00, "depot": 0, "policen": 0})
    assert all(y.ins_depot_cents == 0 for y in result.years)
    assert all(y.depot_cents == 0 for y in result.years)


def test_the_depot_goal_now_gets_an_extrapolation():
    from fastapi.testclient import TestClient

    from finctl.web.server import app

    html = TestClient(app).get("/ziele").text
    if 'data-ziel="depot-2027"' not in html:
        pytest.skip("Depotziel auf der Seite geloescht")
    karte = html[html.index('data-ziel="depot-2027"'):]
    karte = karte[:karte.index("</details>")]
    assert "extrapoliert" in karte
    assert "daher ohne Extrapolation" not in karte


# --------------------------------------------------------- der Notgroschen

def test_every_goal_ignores_the_emergency_fund_except_the_fund_itself():
    from finctl.forecast import ziele as zm

    ziele = {"ziele": [
        {"id": "tagesgeld-puffer", "cents": 33_000_00, "basis": ["tagesgeld", "giro"]},
        {"id": "barista", "cents": 800_000_00},
        {"id": "depot", "cents": 30_000_00, "basis": ["depot"]}]}
    bestand = {"balances": [{"kind": "tagesgeld", "cents": 65_000_00},
                            {"kind": "depot", "cents": 7_000_00}], "obligations": []}
    p = {x.goal_id: x for x in zm.progress(ziele, bestand)}
    assert p["tagesgeld-puffer"].have_cents == 65_000_00
    assert p["barista"].have_cents == 72_000_00 - 33_000_00
    assert p["barista"].abzug_cents == 33_000_00
    assert (p["depot"].have_cents, p["depot"].abzug_cents) == (7_000_00, 0)


def test_a_thin_tagesgeld_gives_up_only_what_it_holds():
    from finctl.forecast import ziele as zm

    ziele = {"ziele": [{"id": "tagesgeld-puffer", "cents": 33_000_00},
                       {"id": "barista", "cents": 800_000_00}]}
    bestand = {"balances": [{"kind": "tagesgeld", "cents": 10_000_00},
                            {"kind": "depot", "cents": 50_000_00}], "obligations": []}
    barista = next(x for x in zm.progress(ziele, bestand) if x.goal_id == "barista")
    assert barista.abzug_cents == 10_000_00
    assert barista.have_cents == 50_000_00


def test_a_goal_is_measured_on_its_date_not_at_the_end_of_its_year():
    """Ein Ziel zum 01.01.2027 sieht das Ende von 2026 -- samt Kaufraten."""
    from datetime import date

    lauf = jm.Projection(years=[jm.Year(year=2026, opening_cents=10_000_00),
                                jm.Year(year=2027, opening_cents=40_000_00),
                                jm.Year(year=2028, opening_cents=50_000_00)])
    def wert(zeile):
        return zeile.closing_cents

    assert lauf.zum(date(2027, 1, 1), wert) == 10_000_00
    assert lauf.zum(date(2027, 7, 2), wert) == pytest.approx(25_000_00, rel=0.01)
    assert lauf.zum(date(2028, 1, 1), wert) == 40_000_00
    assert lauf.zum(date(2031, 1, 1), wert) == 50_000_00


def test_the_sisters_money_is_part_of_the_emergency_fund_and_leaves_with_it():
    """Geld, das im eigenen Konto liegt aber jemand anderem gehoert, zaehlt zum
    Notgroschen -- und geht mit ihm ab, nicht noch einmal obendrauf."""
    from finctl.forecast import ziele as zm

    ziele = {"ziele": [
        {"id": "tagesgeld-puffer", "cents": 33_000_00, "basis": ["tagesgeld", "giro"]},
        {"id": "alles", "cents": 800_000_00}]}
    bestand = {"balances": [{"kind": "tagesgeld", "cents": 82_000_00},
                            {"kind": "depot", "cents": 7_000_00}],
               "obligations": [{"cents": 17_000_00}]}
    p = {x.goal_id: x for x in zm.progress(ziele, bestand)}
    assert p["tagesgeld-puffer"].have_cents == 82_000_00
    assert p["alles"].have_cents == 89_000_00 - 33_000_00
    assert zm.toepfe(bestand)["tagesgeld"] == 82_000_00


def test_the_free_capital_leaves_out_the_buffer():
    zeile = jm.Year(year=2030, opening_cents=133_000_00, tagesgeld_cents=33_000_00,
                    depot_cents=100_000_00, puffer_grenze_cents=33_000_00)
    assert zeile.closing_cents == 133_000_00
    assert zeile.frei_cents == 100_000_00


def _mit_einer_zeile(tmp_path, konto: str):
    """Eine Klammer mit genau einer Einmalzahlung auf `konto`."""
    import yaml

    spec = {"szenarien": [{
        "id": "pytest-entnahme", "name": "Pytest Entnahme", "aktiv": True,
        "zeilen": [{"label": "Abhebung", "art": "betrag",
                    "amount_cents": -20_000_00, "frequenz": "einmalig",
                    "start": "2029-06", "kategorie": "wohnen/miete",
                    "konto": konto}]}]}
    pfad = tmp_path / f"szen_{konto}.yaml"
    pfad.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    return pfad


def test_a_plan_line_on_a_depot_account_takes_from_the_depot(conn, tmp_path):
    """Das Konto einer Planzeile war in dieser Rechnung ohne jede Wirkung.

    Eine Zeile auf einem Depot minderte stillschweigend das Tagesgeld. Wer
    fuer den Hauskauf Anteile verkauft, belastet aber das Depot -- und genau
    das ist der Ersatz fuer die frueher automatische Deckung.
    """
    depot = [r[0] for r in conn.execute(
        "SELECT id FROM accounts WHERE active = 1 AND account_type = 'depot'")]
    assert depot, "kein Depotkonto in accounts.yaml"

    # Ein Puffer ausserhalb jeder Reichweite schaltet den Sweep ab. Sonst
    # raeumt er den entnommenen Betrag im selben Jahr aus dem Ueberschuss
    # wieder ins Depot und die Bewegung, um die es geht, ist unsichtbar.
    gemeinsam = dict(base_year=2026, end_year=2030,
                     toepfe={"tagesgeld": 100_000_00, "depot": 100_000_00},
                     puffer_cents=10_000_000_00)
    auf_depot = jm.project(conn, szenarien=_mit_einer_zeile(tmp_path, depot[0]),
                           **gemeinsam).year(2029)
    auf_giro = jm.project(conn, szenarien=_mit_einer_zeile(tmp_path, "dkb-giro"),
                          **gemeinsam).year(2029)

    # Weniger um die 20.000 und die Steuer auf ihren Gewinnanteil.
    steuer = -sum(p.cents for p in auf_depot.posten["rendite"]
                  if p.label == "Steuer auf Depotverkauf")
    assert 0 < steuer < 20_000_00 * 0.26375
    unterschied = auf_giro.depot_cents - auf_depot.depot_cents
    assert 20_000_00 + steuer <= unterschied < 20_000_00 + 2 * steuer, (unterschied, steuer)
    # Das Tagesgeld liegt um dieselben 20.000 hoeher -- und um ein paar Euro
    # mehr: das Geld ist dort nicht abgeflossen, also hat es das Jahr ueber
    # mitverzinst. Genau deshalb zaehlt eine Depotzeile nicht in den
    # gewichteten Abfluss, der nur die Tagesgeldzinsen betrifft.
    mehr = auf_depot.tagesgeld_cents - auf_giro.tagesgeld_cents
    assert 20_000_00 <= mehr < 21_000_00, mehr
    # Die Zeile steht im Rechenweg, nur in ihrem eigenen Block.
    entnahme = auf_depot.posten["depotentnahme"]
    assert [p.label for p in entnahme] == ["Pytest Entnahme: Abhebung"]
    # Die Herleitung sagt, WOHER das Geld kommt -- sonst stuende die Zeile im
    # Rechenweg wie jede andere Ausgabe (Konvention rechenweg-zu-jeder-prognose).
    assert f"vom Depot ({depot[0]})" in entnahme[0].herleitung
    assert entnahme[0].quelle == "plan"
    assert not any("Abhebung" in p.label for p in auf_depot.posten["einmalig"])
    assert not auf_giro.posten.get("depotentnahme")


def test_a_broker_account_is_not_a_depot(conn, tmp_path):
    """Aus Trade Republic wird laufend bezahlt -- ein stiller Umweg aufs
    Depot waere genau die unsichtbare Logik, die hier nicht sein soll."""
    broker = conn.execute(
        "SELECT id FROM accounts WHERE active = 1 AND account_type = 'broker' "
        "LIMIT 1").fetchone()
    if broker is None:
        pytest.skip("kein Brokerkonto konfiguriert")
    jahr = jm.project(conn, base_year=2026, end_year=2030,
                      szenarien=_mit_einer_zeile(tmp_path, broker[0]),
                      toepfe={"tagesgeld": 100_000_00, "depot": 100_000_00},
                      puffer_cents=33_000_00).year(2029)
    assert not jahr.posten.get("depotentnahme")


# ------------------------------------------------------- Gewinn im Depot

def test_the_stated_gain_lowers_the_cost_basis_of_the_depot(conn, monkeypatch):
    """"davon Gewinn" aus dem Monatsabschluss: Einstand ist Wert minus Gewinn.
    Ohne Angabe gilt der ganze Wert als Einstand."""
    gesehen = []
    echt = jm.kaskade

    def mitschreiben(*a, **k):
        gesehen.append(k.get("einstand"))
        return echt(*a, **k)

    monkeypatch.setattr(jm, "kaskade", mitschreiben)
    jm.project(conn, base_year=2026, end_year=2026,
               toepfe={"tagesgeld": 0, "depot": 100_000_00}, depot_gewinn_cents=30_000_00)
    jm.project(conn, base_year=2026, end_year=2026, toepfe={"tagesgeld": 0, "depot": 100_000_00})
    assert gesehen == [70_000_00, 100_000_00]


def test_only_a_depot_contributes_its_gain():
    from finctl.forecast import ziele as z

    bestand = {"balances": [
        {"kind": "depot", "cents": 50_000_00, "gewinn_cents": 10_000_00},
        {"kind": "krypto", "cents": 5_000_00, "gewinn_cents": -1_000_00},
        {"kind": "rentenversicherung", "cents": 20_000_00, "gewinn_cents": 9_000_00},
        {"kind": "depot", "cents": 10_000_00}]}
    assert z.toepfe(bestand)["depot"] == 65_000_00
    assert z.depot_gewinn(bestand) == 9_000_00


# ------------------------------------------- Eingaben lesen, Rechnung rechnet

_BESTAND = {"toepfe": {"tagesgeld": 20_000_00, "depot": 100_000_00, "policen": 50_000_00},
            "depot_gewinn_cents": 30_000_00, "puffer_cents": 15_000_00,
            "policen_je_konto": {"police-a": 30_000_00, "police-b": 20_000_00}}


def test_project_is_reading_followed_by_calculating(conn):
    """`project` liest mit `eingaben` und rechnet mit `rechnen`, mehr nicht."""
    direkt = jm.project(conn, base_year=2026, end_year=2040, target_cents=500_000_00,
                        **_BESTAND)
    geteilt = jm.rechnen(jm.eingaben(conn, base_year=2026, **_BESTAND),
                         end_year=2040, target_cents=500_000_00)
    assert direkt == geteilt


def test_the_calculation_touches_neither_the_ledger_nor_config(conn, monkeypatch):
    """Wer `rechnen` mehrfach braucht, soll nicht mehrfach lesen: ohne Datei,
    ohne Datenbank kommt dieselbe Projektion heraus.

    Die Datenbank sperrt `sqlite3.connect`: Es oeffnet die Datei in C, ohne
    ein Python-`open`, und die Sperre der Dateien sah es deshalb nicht.
    """
    import builtins
    import sqlite3

    e = jm.eingaben(conn, base_year=2026, **_BESTAND)
    erwartet = jm.rechnen(e, end_year=2040)

    def verboten(*_a, **_k):
        raise AssertionError("rechnen liest eine Datei")

    with monkeypatch.context() as mp:
        for name in ("read_text", "read_bytes", "exists", "is_file", "open"):
            mp.setattr(Path, name, verboten)
        mp.setattr(builtins, "open", verboten)
        mp.setattr(sqlite3, "connect", verboten)
        assert jm.rechnen(e, end_year=2040) == erwartet


def test_the_sqlite_guard_would_notice_a_connection(monkeypatch):
    """Die Sperre oben haelt nur, wenn `sqlite3.connect` auch dort ankommt, wo
    die Anwendung es ruft: `ledger.db.connect` geht durch das Modul."""
    import sqlite3

    from finctl.ledger.db import connect

    def verboten(*_a, **_k):
        raise AssertionError("verbunden")

    monkeypatch.setattr(sqlite3, "connect", verboten)
    with pytest.raises(AssertionError, match="verbunden"):
        connect()


def test_the_pension_gap_takes_what_it_needs_from_the_inputs(conn, monkeypatch):
    """Geburtsdatum, Rentenbeginn, Lebenserwartung und Anteil zum Aufbrauchen
    stehen in den Eingaben: die Luecke oeffnet weder Datei noch Datenbank, und
    ihr Kapital folgt aus genau diesen Werten (erfundene, runde Zahlen)."""
    import builtins
    import sqlite3

    from finctl.forecast import rentenluecke as rl

    e = jm.eingaben(conn, base_year=2026, **_BESTAND)
    e = dataclasses.replace(
        e, geburtsdatum=date(1980, 5, 15), rentenbeginn=date(2047, 6, 1),
        annahmen=dataclasses.replace(e.annahmen, lebenserwartung=90, aufbrauchen=0.5,
                                     rendite_depot=0.05, inflation=0.02))
    lauf = jm.rechnen(e, end_year=2050)

    def verboten(*_a, **_k):
        raise AssertionError("die Rentenluecke liest eine Datei")

    with monkeypatch.context() as mp:
        for name in ("read_text", "read_bytes", "exists", "is_file", "open"):
            mp.setattr(Path, name, verboten)
        mp.setattr(builtins, "open", verboten)
        mp.setattr(sqlite3, "connect", verboten)
        luecke = rl.rechnen(lauf, e)

    assert (luecke.beginn, luecke.jahr, luecke.bis_jahr) == (date(2047, 6, 1), 2048, 2070)
    assert (luecke.rendite, luecke.inflation, luecke.aufbrauchen) == (0.05, 0.02, 0.5)
    assert luecke.kapital_cents == rl.kapitalbedarf(luecke.luecke_cents, 23, 0.05, 0.02, 0.5)
    # Ohne Geburtsdatum laesst sie sich nicht rechnen, und das sagt sie, statt zu raten.
    assert rl.rechnen(lauf, dataclasses.replace(e, geburtsdatum=None)) is None
    assert rl.rechnen(lauf, dataclasses.replace(e, rentenbeginn=None)) is None


def test_person_and_pension_start_come_from_one_reading(conn, monkeypatch):
    """`eingaben` liest die Datei der Person einmal, nicht je Angabe."""
    from finctl import person

    gelesen = []
    echt = person._yaml
    monkeypatch.setattr(person, "_yaml", lambda pfad: gelesen.append(pfad) or echt(pfad))
    e = jm.eingaben(conn, base_year=2026, **_BESTAND)
    assert len(gelesen) == 1, gelesen
    assert e.rentenbeginn == person.rentenbeginn()
    assert e.geburtsdatum == person.geburtstag()


def test_the_calculation_leaves_its_inputs_as_they_were(conn):
    """Die Policen eines Jahres zahlen aus und werden dabei auf null gesetzt;
    das darf die Eingaben nicht erreichen, sonst rechnete der zweite Lauf
    mit anderem Bestand."""
    e = jm.eingaben(conn, base_year=2026, **_BESTAND)
    zuerst = jm.rechnen(e, end_year=2060)
    assert dict(e.monat.policen_je_konto) == _BESTAND["policen_je_konto"]
    assert jm.rechnen(e, end_year=2060) == zuerst


def test_inputs_are_frozen_and_swap_by_group(conn):
    """Eine Gruppe lässt sich als Ganzes tauschen, die übrigen bleiben."""
    import dataclasses

    e = jm.eingaben(conn, base_year=2026, **_BESTAND)
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.base = {}                              # type: ignore[misc]

    basis = jm.rechnen(e, end_year=2035)
    reicher = dataclasses.replace(
        e, monat=dataclasses.replace(e.monat, tagesgeld=e.monat.tagesgeld + 50_000_00))
    assert jm.rechnen(reicher, end_year=2035).final_cents > basis.final_cents
    mehr_gehalt = dataclasses.replace(e, annahmen=dataclasses.replace(
        e.annahmen, gehalt_untergrenze_cents=e.annahmen.gehalt_untergrenze_cents + 100_00))
    assert jm.rechnen(mehr_gehalt, end_year=2035).final_cents > basis.final_cents
    # Ein Block allein: seine Jahreswerte tauschen, die anderen bleiben.
    block = next(b for b in jm.FROM_BASE if e.base.get(b))
    doppelt = dataclasses.replace(
        e, base={**e.base, block: {k: 2 * v for k, v in e.base[block].items()}})
    jetzt, davor = jm.rechnen(doppelt, end_year=2035), basis
    assert jetzt.year(2030).blocks[block] != davor.year(2030).blocks[block]
    anderer = next(b for b in jm.FROM_BASE if b != block)
    assert jetzt.year(2030).blocks[anderer] == davor.year(2030).blocks[anderer]


def test_juengst_changes_only_the_konsum_costs_of_the_base(conn):
    """Das Tempo betrifft nur Kosten im Block `konsum`; die Menge der Posten ist
    in beiden Tempi dieselbe, und ohne Angabe gilt der Schnitt."""
    schnitt = jm.eingaben(conn, base_year=2026, **_BESTAND)
    assert jm.eingaben(conn, base_year=2026, tempo="schnitt", **_BESTAND).base == (
        schnitt.base)
    juengst = jm.eingaben(conn, base_year=2026, tempo="juengst", **_BESTAND)
    assert {b: set(k) for b, k in juengst.base.items()} == {
        b: set(k) for b, k in schnitt.base.items()}
    for block, kategorien in schnitt.base.items():
        for kategorie, cents in kategorien.items():
            if block != "konsum" or cents >= 0:
                assert juengst.base[block][kategorie] == cents, (block, kategorie)
    # Alles andere, was gelesen wird, haengt nicht am Tempo.
    assert dataclasses.replace(juengst, base=schnitt.base, base_monate=schnitt.base_monate,
                               base_reihen=schnitt.base_reihen) == schnitt


def test_both_tempi_are_read_once_and_equal_two_separate_reads(conn):
    je_tempo = jm.eingaben_je_tempo(conn, base_year=2026, **_BESTAND)
    for tempo in jm.TEMPI:
        assert je_tempo[tempo] == jm.eingaben(conn, base_year=2026, tempo=tempo, **_BESTAND)
    assert je_tempo["schnitt"].base_monate == {}


def test_every_category_of_the_base_has_its_line_in_both_tempi_even_with_zero(conn):
    for tempo in jm.TEMPI:
        e = jm.eingaben(conn, base_year=2026, tempo=tempo, **_BESTAND)
        lauf = jm.rechnen(e, end_year=2028)
        for block in jm.FROM_BASE:
            zeilen = {p.verweis for p in lauf.year(2027).posten[block] if p.verweis}
            assert set(e.base.get(block, {})) - {""} <= zeilen, (tempo, block)


def test_the_rechenweg_names_the_last_months_for_a_category_measured_by_juengst(conn):
    e = jm.eingaben(conn, base_year=2026, tempo="juengst", **_BESTAND)
    if not e.base_monate:
        pytest.skip("keine Kostenkategorie im Konsum")
    block, kategorie = next((b, k) for b, ks in e.base_monate.items() for k in ks)
    n = e.base_monate[block][kategorie]
    lauf = jm.rechnen(e, end_year=2028)
    posten = next(p for p in lauf.year(2027).posten[block] if p.verweis == (kategorie or None))
    assert jm._letzte_monate_text(e.monat.fenster, n) in posten.herleitung
    assert f"aus {n} Monaten aufs Jahr" in posten.herleitung


def test_the_tempo_text_takes_its_months_from_the_window():
    f = ag.Fenster(von=date(2025, 10, 1), bis=date(2026, 9, 1), monate=12)
    assert jm.tempo_text("schnitt", f) == "im Schnitt der letzten 12 Monate"
    assert jm.tempo_text("juengst", f) == "im Tempo der letzten 3 Monate"
    kurz = ag.Fenster(von=date(2026, 8, 1), bis=date(2026, 9, 1), monate=2)
    assert jm.tempo_text("juengst", kurz) == "im Tempo der letzten 2 Monate"
    eins = ag.Fenster(von=date(2026, 9, 1), bis=date(2026, 9, 1), monate=1)
    assert jm.tempo_text("schnitt", eins) == "im Schnitt des letzten Monats"


def test_the_juengst_preset_applies_to_the_konsum_block_only():
    f = ag.Fenster(von=date(2025, 10, 1), bis=date(2026, 9, 1), monate=12)
    assert jm._hochrechnung(f, None).regeln_je_block == {}
    assert jm._hochrechnung(f, None, "juengst").regeln_je_block == {
        "konsum": vf.HOCHRECHNUNG_JUENGST}


# ------------------------------- Zinsen auf dem Tagesgeld und die Steuer darauf

def _frei(**anders) -> dict:
    """Ein Jahr ohne Sparrate, mit runden Saetzen: 1 % auf dem Tagesgeld, 25 % Steuer."""
    return {"sparrate": 0, "grenze": 2**62, "satz_tagesgeld": 0.01, "satz_depot": 0.0,
            "vorab_satz": 0.0, "steuer_quote": 0.25, **anders}


def test_interest_below_the_allowance_is_not_taxed():
    k = jm.kaskade(100_000_00, 0, 0, pauschbetrag=2_000_00, **_frei())
    assert k["zins_tagesgeld"] == 1_000_00
    assert k["zinssteuer"] == 0
    assert k["pauschbetrag"] == {"zinsen": 1_000_00, "vorab": 0, "verkauf": 0}
    assert k["tagesgeld"] == 101_000_00 and k["rendite"] == 1_000_00


def test_interest_above_the_allowance_is_taxed_on_the_rest_only():
    k = jm.kaskade(300_000_00, 0, 0, pauschbetrag=1_000_00, **_frei())
    assert k["zins_tagesgeld"] == 3_000_00
    assert k["zinssteuer"] == round(2_000_00 * 0.25)
    # Das Tagesgeld zahlt die Steuer auf seine eigenen Zinsen.
    assert k["tagesgeld"] == 300_000_00 + 3_000_00 - k["zinssteuer"]
    assert k["rendite"] == 3_000_00 - k["zinssteuer"]


def test_without_an_allowance_interest_is_taxed_in_full():
    """Vorher blieb die Steuer auf Zinsen ganz aus der Rechnung."""
    k = jm.kaskade(100_000_00, 0, 0, **_frei())
    assert k["zinssteuer"] == round(1_000_00 * 0.25)


def test_interest_and_advance_lump_sum_share_the_allowance_in_that_order():
    """600 Zinsen und 2.000 Vorabpauschale gegen 1.000 frei: die Zinsen nehmen
    ihre 600, der Rest geht an die Vorabpauschale."""
    k = jm.kaskade(60_000_00, 100_000_00, 0, pauschbetrag=1_000_00,
                   **_frei(satz_depot=0.05, vorab_satz=0.02))
    assert k["zinssteuer"] == 0
    assert k["steuer"] == round((2_000_00 - 400_00) * 0.25)
    assert k["pauschbetrag"] == {"zinsen": 600_00, "vorab": 400_00, "verkauf": 0}
    # Die Reihenfolge verschiebt nur, in welcher Zeile der Abzug steht: zusammen
    # ist es eine Steuer auf den Rest.
    assert k["zinssteuer"] + k["steuer"] == round(0.25 * (600_00 + 2_000_00 - 1_000_00))


def test_what_is_left_of_the_allowance_goes_to_the_gain_of_a_sale():
    """Einstand 60.000 bei Wert 100.000: von 10.000 verkauft sind 4.000 Gewinn."""
    k = jm.kaskade(60_000_00, 100_000_00, 0, pauschbetrag=1_000_00, depot_abfluss=-10_000_00,
                   einstand=60_000_00, **_frei())
    assert k["pauschbetrag"] == {"zinsen": 600_00, "vorab": 0, "verkauf": 400_00}
    assert k["verkaufsteuer"] == round((4_000_00 - 400_00) * 0.25)
    assert k["zinssteuer"] + k["steuer"] + k["verkaufsteuer"] == round(
        0.25 * (600_00 + 4_000_00 - 1_000_00))


def test_an_allowance_larger_than_every_income_leaves_everything_untaxed():
    k = jm.kaskade(60_000_00, 100_000_00, 0, pauschbetrag=50_000_00,
                   depot_abfluss=-10_000_00, einstand=60_000_00,
                   **_frei(satz_depot=0.05, vorab_satz=0.02))
    assert (k["zinssteuer"], k["steuer"], k["verkaufsteuer"]) == (0, 0, 0)
    assert sum(k["pauschbetrag"].values()) < 50_000_00, "er wird nicht aufgebraucht"


def test_in_the_base_year_the_allowance_counts_in_proportion_to_the_months_left():
    """Auch die Zinsen sind nur die der Restmonate: Ein Viertel der Zinsen
    bekommt ein Viertel des Freibetrags, nicht den ganzen."""
    k = jm.kaskade(1_000_000_00, 0, 0, pauschbetrag=1_000_00, anteil=0.25, **_frei())
    assert k["zins_tagesgeld"] == 2_500_00
    assert k["zinssteuer"] == round((2_500_00 - 250_00) * 0.25)


@pytest.mark.parametrize("pauschbetrag", [0, 500_00, 5_000_00])
def test_nothing_is_created_or_lost_when_the_allowance_applies(pauschbetrag):
    k = jm.kaskade(40_000_00, 20_000_00, 30_000_00, sparrate=12_345_00, grenze=45_000_00,
                   satz_tagesgeld=0.025, satz_depot=0.07, vorab_satz=0.02,
                   steuer_quote=0.25, pauschbetrag=pauschbetrag)
    vorher = 40_000_00 + 20_000_00 + 30_000_00
    assert k["tagesgeld"] + k["depot"] + k["policen"] == vorher + k["rendite"] + 12_345_00
    assert k["rendite"] == (k["zins_tagesgeld"] + k["zins_policen"] + k["gewinn_depot"]
                            - k["zinssteuer"] - k["steuer"] - k["verkaufsteuer"])


def _reich(conn, konten=None, saetze=None):
    """Mit so viel Tagesgeld, dass es in keinem Jahr der Tests ins Minus rutscht,
    wie auch immer das Hauptbuch aussieht -- sonst gaebe es keine Zinsen zu lesen."""
    from finctl.forecast.zinsen import Konto

    e = jm.eingaben(conn, base_year=2026, **_BESTAND)
    return dataclasses.replace(
        e, grenze=None,
        monat=dataclasses.replace(
            e.monat, tagesgeld=10_000_000_00,
            tagesgeld_je_konto={k: Konto(*v) for k, v in (konten or {}).items()}),
        zinssaetze=saetze or {})


def test_the_tagesgeld_row_names_each_account_with_its_share_and_rate(conn):
    from finctl.forecast.zinsen import Zinssatz

    e = _reich(conn, {"tg-a": ("tagesgeld", 12_000_00), "giro-b": ("giro", 8_000_00)},
               {"tg-a": (Zinssatz(date(2020, 1, 1), None, 0.03),)})
    zeile = next(p for p in jm.rechnen(e, end_year=2030).year(2028).posten["rendite"]
                 if p.label == "Tagesgeld")
    assert "× 1,80 %" in zeile.herleitung, "60 % mit 3 % und 40 % mit 0 %"
    assert "tg-a 3,00 % auf 60 %" in zeile.herleitung
    assert "giro-b 0,00 % auf 40 %" in zeile.herleitung
    assert "derselben Mischung" in zeile.herleitung


def test_without_stands_per_account_the_pot_earns_the_long_term_rate(conn):
    from finctl.forecast.herkunft import prozent

    e = _reich(conn)
    assert not e.monat.tagesgeld_je_konto
    zeile = next(p for p in jm.rechnen(e, end_year=2030).year(2028).posten["rendite"]
                 if p.label == "Tagesgeld")
    assert f"× {prozent(e.annahmen.rendite_tagesgeld)}" in zeile.herleitung
    assert "langfristiger Satz" in zeile.herleitung


def _mit_pauschbetrag(e, cents: int):
    return dataclasses.replace(
        e, annahmen=dataclasses.replace(e.annahmen, pauschbetrag=cents))


@pytest.mark.parametrize("pauschbetrag", [0, 1_000_00, 1_000_000_00])
def test_the_rows_of_the_return_add_up_to_it_with_any_allowance(conn, pauschbetrag):
    lauf = jm.rechnen(_mit_pauschbetrag(_reich(conn), pauschbetrag), end_year=2040)
    for y in lauf.years:
        assert sum(p.cents for p in y.posten["rendite"]) == y.return_cents, y.year


def test_a_tax_the_allowance_covers_stays_as_a_row_with_zero(conn):
    """Sonst saehe man den Pauschbetrag nicht wirken."""
    def zeile(pauschbetrag):
        lauf = jm.rechnen(_mit_pauschbetrag(_reich(conn), pauschbetrag), end_year=2030)
        return next(p for p in lauf.year(2028).posten["rendite"]
                    if p.label == "Kapitalertragsteuer auf Zinsen")

    gedeckt, offen = zeile(1_000_000_00), zeile(0)
    assert gedeckt.cents == 0 and "Sparerpauschbetrag" in gedeckt.herleitung
    assert offen.cents < 0 and "Sparerpauschbetrag" not in offen.herleitung


def test_a_larger_allowance_never_leaves_less_capital(conn):
    e = jm.eingaben(conn, base_year=2026, **_BESTAND)

    def endkapital(p: int) -> int:
        return jm.rechnen(_mit_pauschbetrag(e, p), end_year=2040).final_cents

    assert endkapital(0) <= endkapital(1_000_00) <= endkapital(2_000_00)
    assert endkapital(1_000_00) < endkapital(1_000_000_00)


def test_the_allowance_is_nominal_and_does_not_grow_with_inflation(conn):
    """Bei so viel Zinsen, dass er ausgeschoepft wird, verbraucht jedes volle
    Jahr genau denselben Betrag; das Basisjahr nur seinen Anteil."""
    lauf = jm.rechnen(_mit_pauschbetrag(_reich(conn), 1_000_00), end_year=2045)
    for y in lauf.years:
        zeilen = [p for p in y.posten["rendite"] if "Sparerpauschbetrag" in p.herleitung]
        verbraucht = sum(int(p.herleitung.split("Sparerpauschbetrag ")[1]
                             .split(" €")[0].replace(".", "")) for p in zeilen)
        erwartet = 1_000 * (3 / 12 if y.year == 2026 else 1)
        assert verbraucht == pytest.approx(erwartet, abs=250), y.year


def test_the_tagesgeld_pot_is_split_per_account_with_its_kind():
    from finctl.forecast import ziele as zm
    from finctl.forecast.zinsen import Konto

    bestand = {"balances": [
        {"kind": "giro", "account_id": "g", "cents": 1000},
        {"kind": "tagesgeld", "account_id": "t", "cents": 5000},
        {"kind": "tagesgeld", "name": "Nur Name", "cents": 700},
        {"kind": "tagesgeld", "account_id": "offen", "cents": None},
        {"kind": "depot", "account_id": "d", "cents": 9000}]}
    assert zm.tagesgeld_je_konto(bestand) == {
        "g": Konto("giro", 1000), "t": Konto("tagesgeld", 5000),
        "Nur Name": Konto("tagesgeld", 700)}


# -------------------- Planzeilen auf Kategorien, die die Hochrechnung rechnet

def _zeile_auf(kategorie: str, art: str = "betrag", **zeile) -> list:
    """Eine eingeschaltete Klammer mit genau einer Zeile auf `kategorie`."""
    from finctl.forecast import szenarien as sz

    roh = {"label": "Zeile", "art": art, "frequenz": "monatlich", "start": "2027-01",
           "kategorie": kategorie, "konto": "tg-a", **zeile}
    if art == "betrag":
        roh.setdefault("amount_cents", -50_00)
    return sz.load({"szenarien": [
        {"id": "k", "name": "Klammer", "aktiv": True, "zeilen": [roh]}]})


def _abzug(geladen: list, jahr: int, messung: dict | None = None) -> int:
    """Was die Planzeilen in `jahr` in der Hochrechnung beitragen (`_planposten`)."""
    messungen = {("k", 0): messung} if messung else {}
    posten, _, aus_depot = jm._planposten(geladen, messungen, jahr, 0)
    return sum(p.cents for p in [*posten, *aus_depot])


@pytest.mark.parametrize("kategorie", sorted(jm.GERECHNET))
def test_a_betrag_line_on_a_calculated_category_does_not_apply(kategorie):
    """Seit die Zinsen gerechnet werden, steht in der Basis nichts mehr, was die
    Zeile korrigieren koennte; sie zoege einen Betrag ab, der nirgends steht."""
    assert _abzug(_zeile_auf(kategorie), 2028) == 0
    assert _abzug(_zeile_auf(kategorie, frequenz="einmalig"), 2027) == 0
    # Mit anderer Kategorie gilt dieselbe Zeile.
    assert _abzug(_zeile_auf("konsum/sonstiges"), 2028) == -600_00
    assert _abzug(_zeile_auf("konsum/sonstiges", frequenz="einmalig"), 2027) == -50_00


@pytest.mark.parametrize("kategorie", sorted(jm.GERECHNET))
def test_a_wegfall_on_a_calculated_category_does_not_apply(kategorie):
    gemessen = {"cents": -600_00, "monate": 12, "buchungen": [], "quelle": "zugeordnet"}
    assert _abzug(_zeile_auf(kategorie, "wegfall"), 2028, gemessen) == 0
    assert _abzug(_zeile_auf("konsum/sonstiges", "wegfall"), 2028, gemessen) == 600_00


def test_a_line_on_interest_counts_in_neither_model(conn, tmp_path, monkeypatch):
    """Dieselbe Zeile, zwei Rechnungen: Beide rechnen Zinsen aus Stand und Satz des Kontos
    (E.6). Die Zeile korrigierte die gemessenen Zinsen; die zaehlen nirgends mehr."""
    from finctl.forecast import konten

    def schreiben(name: str, kategorie: str | None) -> Path:
        zeilen = [] if kategorie is None else [{
            "label": "Zeile", "art": "betrag", "amount_cents": -500_00,
            "frequenz": "monatlich", "start": "2027-01", "kategorie": kategorie,
            "konto": "tg-a"}]
        pfad = tmp_path / name
        pfad.write_text(yaml.safe_dump({"szenarien": [
            {"id": "k", "name": "Klammer", "aktiv": True, "zeilen": zeilen}]}),
            encoding="utf-8")
        return pfad

    def hochrechnung(pfad: Path):
        e = jm.eingaben(conn, base_year=2026, szenarien=pfad, **_BESTAND)
        return jm.rechnen(e, end_year=2035)

    ohne = hochrechnung(schreiben("leer.yaml", None))
    auf_zinsen = schreiben("zinsen.yaml", jm.ZINSEN)
    assert hochrechnung(auf_zinsen) == ohne, "die Zeile auf Zinsen aendert nichts"
    assert hochrechnung(schreiben("konsum.yaml", "konsum/sonstiges")) != ohne

    monkeypatch.setattr(konten, "CONFIG_DIR", tmp_path)
    (tmp_path / "szenarien.yaml").write_text(auf_zinsen.read_text(encoding="utf-8"),
                                             encoding="utf-8")
    assert konten._planposten(conn, "tg-a", {}, "2026-10-01", 18) == []
    (tmp_path / "szenarien.yaml").write_text(
        schreiben("konsum.yaml", "konsum/sonstiges").read_text(encoding="utf-8"),
        encoding="utf-8")
    posten = konten._planposten(conn, "tg-a", {}, "2026-10-01", 18)
    assert [(p.month, p.amount_cents, p.category) for p in posten][:2] == [
        (date(2027, 1, 1), -500_00, "konsum/sonstiges"),
        (date(2027, 2, 1), -500_00, "konsum/sonstiges")]


def test_the_pages_list_lines_of_every_klammer_even_a_switched_off_one():
    ausgeschaltet = _zeile_auf(jm.ZINSEN)
    ausgeschaltet[0].active = False
    [(klammer, nr, line)] = jm.ohne_wirkung_in_prognose(ausgeschaltet)
    assert (klammer.id, nr, line.category_id) == ("k", 0, jm.ZINSEN)
    assert jm.ohne_wirkung_in_prognose(_zeile_auf("konsum/sonstiges")) == []


def test_a_goal_is_measured_at_its_own_date_with_the_pot_and_without_the_buffer(conn):
    from finctl.forecast import ziele as zm

    e = jm.eingaben(conn, base_year=2026, **_BESTAND)
    lauf = jm.rechnen(e, end_year=2035)
    stich = date(2030, 7, 1)

    def ziel(**an):
        return zm.Progress(goal_id="eigen", name="x", target_cents=100_000_00,
                           have_cents=0, due=stich, **an)

    depot = zm.hochgerechnet(lauf, ziel(basis=("depot",)))
    assert depot.cents == lauf.zum(stich, lambda z: z.depot_cents)
    assert depot.jahr == 2030 and depot.pct == 100.0 * depot.cents / 100_000_00
    alles = zm.hochgerechnet(lauf, ziel())
    assert alles.cents == lauf.zum(
        stich, lambda z: z.closing_cents - min(max(z.tagesgeld_cents, 0), z.puffer_grenze_cents))
    puffer = zm.hochgerechnet(lauf, zm.Progress(
        goal_id=zm.PUFFER_ZIEL, name="p", target_cents=1, have_cents=0, due=stich))
    assert puffer.cents == lauf.zum(stich, lambda z: z.closing_cents)
    # Ohne Stichtag, ohne Zielbetrag oder quer zu den Toepfen: keine Hochrechnung.
    assert zm.hochgerechnet(lauf, ziel(basis=("giro-1",))) is None
    assert zm.hochgerechnet(lauf, zm.Progress("e", "x", 1, 0, due=None)) is None
    assert zm.hochgerechnet(lauf, zm.Progress("e", "x", 0, 0, due=stich)) is None
    # Ein Stichtag nach dem Horizont wird auf dessen letztes Jahr begrenzt.
    spaet = zm.Progress("e", "x", 1, 0, due=date(2099, 1, 1))
    assert zm.hochgerechnet(lauf, spaet).jahr == lauf.years[-1].year
