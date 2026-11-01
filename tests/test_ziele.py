"""Goal progress.

Three rules decide whether the bar tells the truth, and each of them was
learned the hard way:

* An obligation is subtracted. Money held for someone else sits in the same
  account as the buffer, and counting it made the portfolio look larger.

* Every goal measures against the SAME liquid assets. Letting each goal name
  its own list produced two comparable targets measured against different
  pots -- and one of the lists named kinds that no longer existed, so it
  counted nothing at all while looking precise.

* The gap and the first rate assume no return. The gap is the target minus
  what exists, the rate is that gap over the months left. Compounding would
  shrink both, and being told to save less than necessary is the expensive
  direction to be wrong in. The second rate, with the rates of the
  Hochrechnung, stands beside it and never replaces it.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from finctl.forecast import ziele as z
from finctl.forecast.herkunft import eur
from finctl.forecast.policen import Police
from finctl.forecast.ziele import Progress, Saetze, progress

GOALS = {"ziele": [
    {"id": "puffer", "name": "Puffer", "cents": 2_700_000},
    {"id": "fire", "name": "FIRE", "cents": 100_000_000,
     "stichtag": date(2045, 12, 31)},
]}


def _balances(scalable=2_000_000, depot=500_000, rente=2_000_000, owed=1_500_000):
    return {
        "balances": [
            {"account_id": "scalable", "kind": "tagesgeld", "cents": scalable},
            {"name": "Depot", "kind": "depot", "cents": depot},
            {"name": "Krypto-Boerse", "kind": "krypto", "cents": None},
            {"name": "Rentenpolice", "kind": "rentenversicherung", "cents": rente},
        ],
        "obligations": [{"name": "Treuhand", "cents": owed}],
    }


# ------------------------------------------------------------ what counts

def test_an_obligation_is_subtracted():
    """Money held for someone else sits in the same account as the buffer."""
    assert z.liquid_cents(_balances()) == \
        2_000_000 + 500_000 + 2_000_000 - 1_500_000


def test_pensions_count_towards_what_has_been_built():
    """Counted by the owner's decision, and the caveat lives elsewhere.

    This page answers "what have I built". That a policy cannot be drawn
    before a given age or before its maturity is true and material, but it is
    the question the phase model answers -- mixing the two here would mean
    neither is answered cleanly.
    """
    assert z.liquid_cents(_balances(rente=2_000_000)) - \
           z.liquid_cents(_balances(rente=0)) == 2_000_000


def test_a_holding_with_no_value_is_skipped_not_counted_as_zero():
    """Staked ETH is worth something. Showing it as nothing would look like a
    measurement rather than a gap in the data."""
    assert z.liquid_cents(_balances()) == z.liquid_cents(_balances())


def test_every_goal_measures_against_the_same_pot():
    rows = progress(GOALS, _balances())
    assert len({r.have_cents for r in rows}) == 1
    assert rows[0].have_cents == z.liquid_cents(_balances())


# ------------------------------------------------------------ the due date

def test_a_date_written_as_a_string_survives():
    """The dashboard overlay writes ISO strings; goals.yaml yields date
    objects. Accepting only the latter is why a date typed into the page
    vanished the moment it was saved.
    """
    goals = {"ziele": [{"id": "x", "name": "X", "cents": 1000,
                        "stichtag": "2046-01-01"}]}
    assert progress(goals, _balances())[0].due == date(2046, 1, 1)


def test_an_unparseable_date_is_dropped_rather_than_crashing():
    goals = {"ziele": [{"id": "x", "name": "X", "cents": 1000,
                        "stichtag": "irgendwann"}]}
    assert progress(goals, _balances())[0].due is None


# ------------------------------------------------------- the required rate

def test_the_rate_is_straight_division_with_no_compounding():
    p = Progress("x", "X", target_cents=1_200_000, have_cents=0,
                 due=date(2027, 9, 1))
    assert p.monthly_needed_cents(date(2026, 9, 1)) == 1_200_000 // 12


def test_a_goal_with_no_date_has_no_rate():
    """"Per month until never" has no answer, so it must not invent one."""
    assert Progress("x", "X", 1000, 0).monthly_needed_cents(date(2026, 9, 1)) is None


def test_a_goal_already_due_needs_the_whole_remainder_now():
    p = Progress("x", "X", 1000, 200, due=date(2026, 9, 1))
    assert p.monthly_needed_cents(date(2026, 9, 1)) == 800


# ---------------------------------------------------------------- coverage

def test_promised_money_removes_the_rate_without_faking_the_balance():
    """A maturing endowment covers a goal, but it is not saved yet.

    Folding it into the balance would show the goal as met years before any
    money exists -- the one thing a progress bar must never do.
    """
    p = Progress("t", "T", 1_000_000, 0, due=date(2030, 1, 1),
                 covered_cents=900_000)
    assert p.pct == 0.0
    assert p.uncovered_cents == 100_000
    full = Progress("t", "T", 1_000_000, 0, due=date(2030, 1, 1))
    assert p.monthly_needed_cents(date(2026, 9, 1)) < \
           full.monthly_needed_cents(date(2026, 9, 1))


def test_progress_never_exceeds_one_hundred_percent():
    assert Progress("x", "X", 1000, 5000).pct == 100.0


def test_a_liability_is_not_a_goal():
    goals = {"ziele": [{"id": "s", "name": "S", "cents": 1, "art": "verbindlichkeit"}]}
    assert progress(goals, _balances()) == []


def test_crypto_counts_as_a_depot():
    """Ein Ziel ueber "alle Depots" zaehlt die Coins mit, und eine Basis, die
    beide nennt, zaehlt sie nicht doppelt."""
    from finctl.forecast import ziele as z

    bestand = {"balances": [{"name": "etf", "kind": "depot", "cents": 1000},
                            {"name": "coins", "kind": "krypto", "cents": 500},
                            {"name": "giro", "kind": "giro", "cents": 7}]}
    assert z.liquid_cents(bestand, ("depot",)) == 1500
    assert z.basis_von({"basis": ["depot", "krypto"]}) == ("depot",)
    assert z.liquid_cents(bestand, z.basis_von({"basis": ["depot", "krypto"]})) == 1500


# ------------------------------------------------------------ Notgroschen

def test_an_emergency_fund_without_an_amount_is_three_salary_floors(monkeypatch):
    """Die Startvorlage bringt den Notgroschen ohne Betrag mit; dann gilt das
    Dreifache der Gehalts-Untergrenze -- und die Seite ist nicht leer."""
    from finctl import assumptions as ann

    monkeypatch.setattr(ann, "salary_floor_cents", lambda *a, **k: 250_000)
    ohne = {"ziele": [{"id": z.PUFFER_ZIEL, "name": "Notgroschen"}]}
    [ziel] = z.aus_spec(ohne)["ziele"]
    assert ziel["cents"] == 3 * 250_000 and "Gehalts-Untergrenze" in ziel["notiz"]
    assert z.puffer_cents(z.aus_spec(ohne)) == 750_000
    assert "cents" not in ohne["ziele"][0]          # die Vorgabe steht nie in der Datei


def test_an_own_amount_beats_the_default(monkeypatch):
    from finctl import assumptions as ann

    monkeypatch.setattr(ann, "salary_floor_cents", lambda *a, **k: 250_000)
    eigen = {"ziele": [{"id": z.PUFFER_ZIEL, "name": "Notgroschen", "cents": 1_000_000}]}
    [ziel] = z.aus_spec(eigen)["ziele"]
    assert ziel["cents"] == 1_000_000 and not ziel.get("notiz")


def test_the_starting_template_brings_the_emergency_fund():
    import yaml

    from finctl.vorgaben import ORDNER

    vorlage = yaml.safe_load((ORDNER / "goals.yaml").read_text(encoding="utf-8"))
    [ziel] = vorlage["ziele"]
    assert ziel["id"] == z.PUFFER_ZIEL and "cents" not in ziel


# ------------------------------------------------- die Rate mit Rendite

HEUTE = date(2026, 9, 1)
NULL = Saetze(tagesgeld=0.0, depot=0.0, police=0.0)


def _bestand(*, giro=400_000, tagesgeld=3_000_000, depot=1_000_000, krypto=200_000,
             policen=(("p1", 2_000_000),), verbindlichkeit=0):
    """Ein erfundener Haushalt, mit allem, was eine Karte zaehlen kann."""
    zeilen = [{"account_id": "g1", "name": "Giro", "kind": "giro", "cents": giro},
              {"account_id": "t1", "name": "Tagesgeld", "kind": "tagesgeld", "cents": tagesgeld},
              {"account_id": "d1", "name": "Depot", "kind": "depot", "cents": depot},
              {"account_id": "k1", "name": "Coins", "kind": "krypto", "cents": krypto}]
    zeilen += [{"account_id": konto, "name": konto, "kind": "rentenversicherung", "cents": c}
               for konto, c in policen]
    return {"balances": zeilen,
            "obligations": [{"name": "Treuhand", "cents": verbindlichkeit}] if verbindlichkeit
            else []}


def _karte(bestand, *, basis=None, puffer=None, ziel=9_800_000, stichtag=date(2027, 9, 1),
           gedeckt=0):
    """Das Progress eines Ziels, so wie `progress` es baut -- samt Abzug."""
    ziele = [{"id": "z", "name": "Z", "cents": ziel, "stichtag": stichtag}]
    if basis:
        ziele[0]["basis"] = list(basis)
    if gedeckt:
        ziele[0]["gedeckt_durch"] = [{"cents": gedeckt}]
    if puffer:
        ziele.append({"id": z.PUFFER_ZIEL, "name": "Notgroschen", "cents": puffer})
    return next(p for p in progress({"ziele": ziele}, bestand, today=HEUTE)
                if p.goal_id == "z")


def _ansparen(start: int, rate: int, satz: float, monate: int) -> float:
    """Dieselbe Frage monatsweise gerechnet: Zins auf den Stand, dann die Rate."""
    m = (1 + satz) ** (1 / 12) - 1
    stand = float(start)
    for _ in range(monate):
        stand = stand * (1 + m) + rate
    return stand


SZENARIEN = {
    "alles, Verbindlichkeit": dict(bestand=_bestand(verbindlichkeit=500_000)),
    "alles, Notgroschen": dict(bestand=_bestand(verbindlichkeit=500_000), puffer=1_000_000),
    "Verbindlichkeit uebersteigt Tagesgeld": dict(
        bestand=_bestand(giro=100_000, tagesgeld=300_000, verbindlichkeit=1_000_000)),
    "Tagesgeld ohne Giro": dict(bestand=_bestand(), basis=("tagesgeld",), puffer=1_000_000),
    "Tagesgeld und Giro": dict(bestand=_bestand(), basis=("tagesgeld", "giro"),
                               puffer=1_000_000),
    "Depot und Krypto": dict(bestand=_bestand(), basis=("depot", "krypto"), puffer=1_000_000),
    "Police allein": dict(bestand=_bestand(), basis=("rentenversicherung",)),
}


@pytest.mark.parametrize("name", sorted(SZENARIEN))
def test_the_holdings_per_kind_add_up_to_what_the_card_shows(name):
    prog = _karte(**SZENARIEN[name])
    teile = z.bestand_der_basis(SZENARIEN[name]["bestand"], prog)
    assert sum(t.cents for t in teile) == prog.have_cents


def test_a_basis_with_savings_but_no_current_account_counts_no_current_account():
    prog = _karte(_bestand(), basis=("tagesgeld",), puffer=1_000_000)
    assert {(t.art, t.cents) for t in z.bestand_der_basis(_bestand(), prog)} == \
        {("tagesgeld", 2_000_000)}


def test_a_debt_beyond_the_savings_comes_out_of_the_depot():
    bestand = _bestand(giro=100_000, tagesgeld=300_000, verbindlichkeit=1_000_000)
    prog = _karte(bestand)
    je_art = {t.art: t.cents for t in z.bestand_der_basis(bestand, prog)}
    assert "tagesgeld" not in je_art and "giro" not in je_art
    # Depot und Krypto zusammen 1.200.000, davon 600.000 Rest der Schuld.
    assert je_art["depot"] == 1_200_000 - (1_000_000 - 400_000)


def test_a_rate_at_zero_percent_is_the_first_rate_to_the_cent():
    for name, szenario in SZENARIEN.items():
        for ziel, stichtag in ((9_800_000, date(2027, 9, 1)), (7_654_300, date(2027, 4, 1))):
            prog = _karte(**{**szenario, "ziel": ziel, "stichtag": stichtag})
            zweite = z.rate_mit_rendite(prog, szenario["bestand"], NULL, HEUTE)
            if name == "Police allein":      # waechst nichts, in das gespart wird
                assert zweite is None
            else:
                assert zweite.cents == prog.monthly_needed_cents(HEUTE), name


def test_two_kinds_with_different_rates_match_a_hand_calculation():
    """Das Tagesgeld verdoppelt sich in zwoelf Monaten, das Giro bleibt stehen.

    Die Basis ist Tagesgeld und Giro, also waechst auch die Rate mit dem
    Tagesgeldsatz, und nichts wird ins Depot geschoben. Tagesgeld 3.000.000
    minus Notgroschen 1.000.000 wird zu 4.000.000, das Giro 400.000 bleibt:
    Bestand 4.400.000. Zwoelf Monate mit einem Satz, der den Bestand
    verdoppelt, machen aus dem Nenner der Rate eins -- die Rate ist die Luecke
    mal dem Monatssatz.
    """
    bestand = _bestand()
    prog = _karte(bestand, basis=("tagesgeld", "giro"), ziel=5_000_000, puffer=1_000_000)
    saetze = Saetze(tagesgeld=1.0, depot=0.0, police=0.0)
    zweite = z.rate_mit_rendite(prog, bestand, saetze, HEUTE)
    assert zweite.cents == round((5_000_000 - 4_400_000) * (2 ** (1 / 12) - 1))


def test_the_rate_with_return_pays_the_goal_when_saved_month_by_month():
    bestand = _bestand(giro=0, krypto=0, policen=())
    prog = _karte(bestand, ziel=20_000_000, puffer=1_000_000)
    saetze = Saetze(tagesgeld=0.03, depot=0.05, police=0.05)
    zweite = z.rate_mit_rendite(prog, bestand, saetze, HEUTE)
    assert zweite.satz == 0.05 and zweite.cents < prog.monthly_needed_cents(HEUTE)
    # Das Tagesgeld nach Notgroschen geht ueber die Kaskade ins Depot und waechst
    # wie das Depot und wie die Rate mit 5 %.
    stand = (_ansparen(2_000_000, 0, 0.05, 12) + _ansparen(1_000_000, 0, 0.05, 12)
             + _ansparen(0, zweite.cents, 0.05, 12))
    assert stand == pytest.approx(20_000_000, abs=100)


def test_a_holding_that_grows_to_the_goal_alone_needs_no_rate():
    bestand = _bestand(giro=0, tagesgeld=0, krypto=0, policen=())
    prog = _karte(bestand, ziel=1_100_000)          # Depot 1.000.000
    zweite = z.rate_mit_rendite(prog, bestand, Saetze(0.0, 0.2, 0.0), HEUTE)
    assert prog.monthly_needed_cents(HEUTE) > 0
    assert zweite.cents is None and "allein" in zweite.herleitung[-1]


def test_current_account_does_not_grow_and_a_policy_grows_with_its_own_rate():
    giro = _bestand(tagesgeld=0, depot=0, krypto=0, policen=(), giro=1_000_000)
    prog = _karte(giro, ziel=5_000_000)
    zweite = z.rate_mit_rendite(prog, giro, Saetze(0.5, 0.0, 0.5), HEUTE)
    assert zweite.cents == prog.monthly_needed_cents(HEUTE)

    police = _bestand(tagesgeld=0, depot=0, krypto=0, giro=0,
                      policen=(("p1", 1_000_000), ("p2", 1_000_000)))
    prog = _karte(police, ziel=5_000_000)
    saetze = Saetze(tagesgeld=0.0, depot=0.0, police=0.0, policen={"p1": 1.0})
    zweite = z.rate_mit_rendite(prog, police, saetze, HEUTE)
    # p1 verdoppelt sich, p2 bleibt: 2.000.000 + 1.000.000 gegen 5.000.000.
    assert zweite.cents == round((5_000_000 - 3_000_000) / 12)


def test_promised_money_lowers_the_second_rate_like_the_first():
    bestand = _bestand()
    ohne = _karte(bestand, ziel=15_000_000)
    mit = _karte(bestand, ziel=15_000_000, gedeckt=1_200_000)
    saetze = Saetze(0.02, 0.04, 0.04)
    assert z.rate_mit_rendite(mit, bestand, NULL, HEUTE).cents == \
        mit.monthly_needed_cents(HEUTE)
    assert z.rate_mit_rendite(mit, bestand, saetze, HEUTE).cents < \
        z.rate_mit_rendite(ohne, bestand, saetze, HEUTE).cents


def test_the_rate_grows_with_the_rate_of_where_it_is_saved():
    bestand = _bestand()
    saetze = Saetze(tagesgeld=0.02, depot=0.06, police=0.06)
    assert z.rate_mit_rendite(_karte(bestand, ziel=20_000_000), bestand,
                              saetze, HEUTE).satz == 0.06
    assert z.rate_mit_rendite(_karte(bestand, basis=("tagesgeld",), ziel=20_000_000),
                              bestand, saetze, HEUTE).satz == 0.02
    assert z.rate_mit_rendite(_karte(bestand, basis=("giro", "tagesgeld", "depot"),
                                     ziel=20_000_000), bestand, saetze, HEUTE).satz == 0.06


@pytest.mark.parametrize("fall", [
    "ohne Stichtag", "Stichtag erreicht", "erste Rate schon null", "Basis quer zu den Toepfen",
    "nur Giro", "nur Policen"])
def test_where_there_is_no_second_rate_there_is_none(fall):
    bestand = _bestand()
    karte = {
        "ohne Stichtag": dict(stichtag=None),
        "Stichtag erreicht": dict(stichtag=date(2026, 9, 30)),
        "erste Rate schon null": dict(ziel=1_000_000),
        "Basis quer zu den Toepfen": dict(basis=("t1", "depot")),
        "nur Giro": dict(basis=("giro",)),
        "nur Policen": dict(basis=("rentenversicherung",)),
    }[fall]
    prog = _karte(bestand, ziel=karte.pop("ziel", 20_000_000), **karte)
    assert z.rate_mit_rendite(prog, bestand, Saetze(0.02, 0.04, 0.04), HEUTE) is None


def test_the_rates_come_from_the_assumptions_less_taxes_and_costs():
    annahmen = SimpleNamespace(rendite_tagesgeld=0.02, rendite_depot=0.05,
                               vorab_satz=0.02, steuer_quote=0.25)
    police = Police(konto="p1", quelle="q", name="P", kosten_pa=0.01)
    saetze = z.saetze_aus(annahmen, {"p1": police})
    assert saetze.tagesgeld == 0.02
    assert saetze.depot == pytest.approx(0.05 - 0.02 * 0.25)
    assert saetze.police == 0.05 and saetze.policen == {"p1": pytest.approx(0.04)}
    # Die Vorabpauschale kann nicht mehr kosten, als das Depot bringt.
    mager = SimpleNamespace(**{**vars(annahmen), "rendite_depot": 0.01})
    assert z.saetze_aus(mager).depot == pytest.approx(0.01 - 0.01 * 0.25)


def test_the_derivation_names_every_kind_its_rate_and_the_gap():
    bestand = _bestand()
    prog = _karte(bestand, ziel=20_000_000, gedeckt=500_000)
    zweite = z.rate_mit_rendite(prog, bestand, Saetze(0.02, 0.045, 0.045), HEUTE)
    text = "\n".join(zweite.herleitung)
    for erwartet in ("Tagesgeld", "Depots", "Rentenversicherungen", "4,50 %", "2,00 %",
                     "zugesagt", "Lücke", "Rate:"):
        assert erwartet in text
    assert "Girokonten" in text and "0,00 %" in text
    assert "Kaskade" not in text


# ------------------------------------- die Kaskade schiebt den Rest ins Depot

def _je_art(zweite) -> dict[str, str]:
    """Die Zeilen der Herleitung, je Bestandsart."""
    return {zeile.split(":")[0]: zeile for zeile in zweite.herleitung if " heute, mit " in zeile}


def test_with_a_buffer_goal_the_rest_of_savings_and_current_account_grows_like_the_depot():
    bestand = _bestand()
    prog = _karte(bestand, ziel=20_000_000, puffer=1_000_000)
    saetze = Saetze(tagesgeld=0.02, depot=0.05, police=0.05)
    zweite = z.rate_mit_rendite(prog, bestand, saetze, HEUTE)
    assert zweite.satz == 0.05
    # Was nach dem Notgroschen auf Tagesgeld und Giro liegt, waechst wie das Depot.
    gewachsen = round(2_000_000 * (1 + 0.05) ** (1 / 12 * 12))
    assert f"{eur(2_000_000)} heute, mit 5,00 % im Jahr {eur(gewachsen)}" in \
        _je_art(zweite)["Tagesgeld"]
    assert "mit 5,00 % im Jahr" in _je_art(zweite)["Girokonten"]
    assert "Kaskade" in _je_art(zweite)["Tagesgeld"] and "Kaskade" in _je_art(zweite)["Girokonten"]
    assert "Kaskade" not in _je_art(zweite)["Depots"]


def test_the_rate_with_a_buffer_goal_matches_the_all_depot_hand_calculation():
    """Tagesgeld 3.000.000 und Giro 400.000 minus Notgroschen 1.000.000: der Rest
    ist 2.400.000 und waechst, als laege er im Depot."""
    bestand = _bestand(depot=0, krypto=0, policen=())
    saetze = Saetze(tagesgeld=0.01, depot=0.06, police=0.06)
    mit = z.rate_mit_rendite(_karte(bestand, ziel=20_000_000, puffer=1_000_000),
                             bestand, saetze, HEUTE)
    ins_depot = _bestand(giro=0, tagesgeld=0, depot=2_400_000, krypto=0, policen=())
    wie_depot = z.rate_mit_rendite(_karte(ins_depot, ziel=20_000_000), ins_depot, saetze, HEUTE)
    assert mit.cents == wie_depot.cents


def test_without_a_buffer_goal_nothing_moves_to_the_depot():
    bestand = _bestand()
    prog = _karte(bestand, ziel=20_000_000)
    zweite = z.rate_mit_rendite(prog, bestand, Saetze(0.02, 0.05, 0.05), HEUTE)
    zeilen = _je_art(zweite)
    assert "mit 2,00 % im Jahr" in zeilen["Tagesgeld"]
    assert "mit 0,00 % im Jahr" in zeilen["Girokonten"]
    assert "Kaskade" not in "\n".join(zweite.herleitung)


def test_a_basis_without_the_depot_keeps_the_rest_where_it_lies():
    bestand = _bestand()
    prog = _karte(bestand, basis=("tagesgeld", "giro"), ziel=20_000_000, puffer=1_000_000)
    zweite = z.rate_mit_rendite(prog, bestand, Saetze(0.02, 0.05, 0.05), HEUTE)
    assert zweite.satz == 0.02
    zeilen = _je_art(zweite)
    assert "mit 2,00 % im Jahr" in zeilen["Tagesgeld"]
    assert "mit 0,00 % im Jahr" in zeilen["Girokonten"]
    assert "Kaskade" not in "\n".join(zweite.herleitung)


def test_the_buffer_goal_itself_is_measured_where_it_lies():
    bestand = _bestand()
    ziele = {"ziele": [{"id": z.PUFFER_ZIEL, "name": "Notgroschen", "cents": 20_000_000,
                        "stichtag": date(2027, 9, 1), "basis": ["tagesgeld", "giro"]}]}
    [prog] = progress(ziele, bestand, today=HEUTE)
    assert not prog.mit_puffer
    zweite = z.rate_mit_rendite(prog, bestand, Saetze(0.02, 0.05, 0.05), HEUTE)
    assert "Kaskade" not in "\n".join(zweite.herleitung)
