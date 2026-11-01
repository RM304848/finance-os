"""Ruhestand in der Hochrechnung: Gehalt endet, Renten kommen, Policen zahlen
aus, das Depot deckt die Luecke. Alle Zahlen hier sind erfunden."""

from __future__ import annotations

from datetime import date

from finctl.forecast import jahre as jm
from finctl.renten import Quelle


def _rente(**kw) -> Quelle:
    werte = {"id": "drv", "name": "Gesetzliche Rente", "art": "rente", "cents": 100000,
             "kaufkraft": "heute", "ab": date(2050, 4, 1), "stand": date(2026, 1, 1)}
    werte.update(kw)
    return Quelle(**werte)


def test_salary_stops_the_month_before_retirement():
    assert jm._arbeitsmonate(2050, 0, date(2050, 4, 1)) == 3
    assert jm._arbeitsmonate(2051, 0, date(2050, 4, 1)) == 0
    assert jm._arbeitsmonate(2049, 0, None) == 12


def test_a_pension_grows_with_inflation_and_loses_the_deduction():
    [p] = jm._rentenposten([_rente()], 2050, 0, 0.02, 0.25)
    je_monat = round(100000 * 1.02 ** 24)
    assert p.cents == round(je_monat * 0.75) * 9          # April bis Dezember
    assert p.quelle == "vertrag" and p.verweis == "rente:drv"
    assert jm._rentenposten([_rente()], 2049, 0, 0.02, 0.25) == []


def test_a_policy_paid_as_capital_moves_its_share_to_the_depot():
    """Umschichtung, kein Geldfluss: das Vermoegen bleibt gleich."""
    anteile = {"police": 50_000_00, "andere": 20_000_00}
    q = _rente(id="p", art="kapital", konto="police", ab=date(2045, 6, 1))
    w = jm._policenwechsel([q], 2045, anteile)
    assert (w.verrentet, w.zum_depot, w.zum_tagesgeld, w.abzug) == ([], 50_000_00, 0, 0)
    assert w.umgeschichtet[0].cents == 50_000_00 and len(w.umgeschichtet) == 1
    assert anteile == {"police": 0, "andere": 20_000_00}


def test_a_capital_payout_loses_the_pension_deduction_to_the_insurer():
    """Bewusst vorsichtig: derselbe Abzug wie auf eine Rente, ohne Schichten. Er geht von
    der Auszahlung selbst ab, wie der Versicherer die Steuer einbehaelt: ins Depot kommt
    der Rest, das Tagesgeld zahlt nichts, und in keinem Block steht eine Ausgabe."""
    anteile = {"police": 50_000_00}
    q = _rente(id="p", art="kapital", konto="police", ab=date(2045, 6, 1))
    w = jm._policenwechsel([q], 2045, anteile, 0.25)
    assert w.verrentet == [] and w.zum_tagesgeld == 0
    assert (w.zum_depot, w.abzug) == (37_500_00, 12_500_00)
    brutto, abzug = w.umgeschichtet
    assert (brutto.cents, abzug.cents) == (50_000_00, -12_500_00) and abzug.einmalig
    assert sum(p.cents for p in w.umgeschichtet) == w.zum_depot
    assert ("brutto 50.000,00 € − 25 % Abzug 12.500,00 € = netto 37.500,00 € ins Depot"
            in brutto.herleitung)


def test_a_capital_without_a_policy_arrives_after_the_deduction():
    q = _rente(id="k", art="kapital", ab=date(2045, 6, 1))
    [p] = jm._rentenposten([q], 2045, 0, 0.0, 0.25)
    assert p.cents == round(q.cents * 0.75)


def test_a_policy_paid_as_pension_leaves_the_capital():
    anteile = {"police": 50_000_00}
    q = _rente(id="p", konto="police", ab=date(2045, 6, 1))
    w = jm._policenwechsel([q], 2045, anteile)
    assert w.verrentet[0].cents == -50_000_00 and w.verrentet[0].einmalig
    assert (w.zum_depot, w.zum_tagesgeld, w.abzug) == (0, 50_000_00, 0)


def test_in_retirement_the_depot_refills_the_buffer():
    """Vor der Rente deckt sich ein Minus nicht von selbst -- danach ist genau
    das der Plan."""
    args = {"sparrate": -30_000_00, "grenze": 10_000_00, "satz_tagesgeld": 0.0,
            "satz_depot": 0.0, "vorab_satz": 0.0, "steuer_quote": 0.0}
    davor = jm.kaskade(10_000_00, 100_000_00, 0, **args)
    assert davor["tagesgeld"] == -20_000_00 and davor["ins_depot"] == 0
    danach = jm.kaskade(10_000_00, 100_000_00, 0, entnahme=True, **args)
    assert danach["tagesgeld"] == 10_000_00
    assert danach["depot"] == 70_000_00 and danach["ins_depot"] == -30_000_00
    leer = jm.kaskade(10_000_00, 5_000_00, 0, entnahme=True, **args)
    assert leer["tagesgeld"] == -15_000_00 and leer["depot"] == 0


def test_the_capital_lasts_until_the_buffer_goes_negative():
    lauf = jm.Projection(years=[jm.Year(year=y, tagesgeld_cents=t) for y, t in
                                ((2080, 5), (2081, 1), (2082, -1))])
    assert lauf.reicht_bis == 2081
    assert jm.Projection(years=[jm.Year(year=2080, tagesgeld_cents=1)]).reicht_bis is None


# ----------------------------- betriebliche Altersvorsorge bei Teilzeit
#
# 40.000 Stand zum 01.01.2026, 2.400 Beitrag je Jahr, 300.000 zum 01.01.2056.

def _bav(**kw) -> Quelle:
    return _rente(id="bav", name="Betriebsrente", art="kapital", kaufkraft="nominal",
                  cents=30_000_000, ab=date(2056, 1, 1), stand_cents=4_000_000,
                  stand_wert=date(2026, 1, 1), beitrag_ag_cents=240_000, **kw)


def _teilzeitzeilen(anteil: float, start: date, ende: date | None = None) -> tuple:
    from finctl.forecast import szenarien as sz

    klammer = sz.Scenario(id="teilzeit", name="Teilzeit", active=True, lines=[
        sz.Line(label="Teilzeit", amount_cents=0, kind="teilzeit", anteil=anteil,
                start=start, end=ende)])
    return tuple(sz.teilzeitzeilen([klammer]))


def _prozent(satz: float) -> str:
    return f"{satz * 100:.2f}".replace(".", ",") + " %"


def _satz_text(q) -> str:
    from finctl import renten

    return _prozent(renten.satz(q, q.ab))


def test_without_part_time_the_model_pays_the_amount_of_the_letter():
    [p] = jm._rentenposten([_bav()], 2056, 0, 0.02, 0.25)
    assert p.cents == round(30_000_000 * 0.75)
    # Der Satz steht immer in der Herleitung, nicht erst bei Teilzeit.
    assert p.herleitung == (f"Kapital laut Schreiben 300.000 € (Satz {_satz_text(_bav())} aus "
                            "Stand 40.000 € zum 01/2026 und 2.400 € Beitrag je Jahr), "
                            "01/2056 − 25 % Steuer und KV")
    # Eine Teilzeit, die erst nach dem Bezug beginnt, kuerzt nichts.
    [spaeter] = jm._rentenposten([_bav()], 2056, 0, 0.02, 0.25, teilzeit=_teilzeitzeilen(
        0.5, date(2060, 1, 1)))
    assert spaeter.cents == p.cents


def test_part_time_lowers_the_payout_by_the_contribution_it_cuts():
    from finctl import renten

    q = _bav()
    zeilen = _teilzeitzeilen(0.5, date(2041, 1, 1))
    [p] = jm._rentenposten([q], 2056, 0, 0.02, 0.25, teilzeit=zeilen)
    brutto = renten.auszahlung_cents(q, date(2056, 1, 1), jm._anteil_im_monat(list(zeilen)))
    assert p.cents == round(brutto * 0.75) and brutto < 30_000_000
    assert "statt 300.000 € laut Schreiben" in p.herleitung
    assert "Satz" in p.herleitung and "Teilzeit" in p.herleitung


def test_part_time_ends_with_its_own_end_month():
    q = _bav()
    dauer = _teilzeitzeilen(0.5, date(2041, 1, 1), date(2045, 12, 1))
    dauerhaft = _teilzeitzeilen(0.5, date(2041, 1, 1))
    [kurz] = jm._rentenposten([q], 2056, 0, 0.0, 0.0, teilzeit=dauer)
    [lang] = jm._rentenposten([q], 2056, 0, 0.0, 0.0, teilzeit=dauerhaft)
    assert lang.cents < kurz.cents < 30_000_000


def test_the_contribution_ends_with_the_salary_while_part_time_runs():
    q = _bav()
    zeilen = _teilzeitzeilen(0.5, date(2041, 1, 1))
    [bis_zum_bezug] = jm._rentenposten([q], 2056, 0, 0.0, 0.0, teilzeit=zeilen,
                                       rente_ab=date(2056, 1, 1))
    [fruehes_ende] = jm._rentenposten([q], 2056, 0, 0.0, 0.0, teilzeit=zeilen,
                                      rente_ab=date(2050, 1, 1))
    assert fruehes_ende.cents < bis_zum_bezug.cents


def test_part_time_does_not_touch_a_source_without_the_model():
    plain = _rente(id="k", art="kapital", kaufkraft="nominal", cents=30_000_000,
                   ab=date(2056, 1, 1))
    [p] = jm._rentenposten([plain], 2056, 0, 0.0, 0.25,
                           teilzeit=_teilzeitzeilen(0.5, date(2041, 1, 1)))
    assert p.cents == round(30_000_000 * 0.75)


def test_a_capital_without_the_model_names_no_rate():
    plain = _rente(id="k", art="kapital", kaufkraft="nominal", cents=30_000_000,
                   ab=date(2056, 1, 1))
    [p] = jm._rentenposten([plain], 2056, 0, 0.0, 0.25)
    assert p.herleitung == "Kapital laut Schreiben 300.000 €, 01/2056 − 25 % Steuer und KV"


# ----------------------------- /renten: Stand, Beitrag, Satz, Pruefwert, Auszahlung

def _zeile(q=None, teilzeit=(0.5, date(2041, 1, 1)), rente_ab=date(2056, 1, 1)) -> str:
    q = q or _bav()
    return jm.modellzeile(q, q.ab, teilzeit, rente_ab)


def test_the_line_names_stand_contribution_rate_and_the_payout_with_and_without_part_time():
    from finctl import renten

    q = _bav()
    mit = renten.auszahlung_cents(q, q.ab, renten.teilzeit_ab(0.5, date(2041, 1, 1)),
                                  date(2056, 1, 1))
    zeile = _zeile(q)
    assert "Stand 40.000,00 € zum 01/2026" in zeile
    assert "Beitrag des Arbeitgebers 2.400,00 € im Jahr" in zeile
    assert f"Satz {_satz_text(q)}, der von beidem zu 300.000,00 € zum 01/2056 führt" in zeile
    assert "Auszahlung ohne Teilzeit 300.000,00 €" in zeile
    assert f"mit Teilzeit (50,00 % ab 01/2041 laut Annahmen) {jm.eur_genau(mit)}" in zeile
    assert mit < 30_000_000


def test_without_part_time_in_the_assumptions_only_the_payout_without_it_stands():
    zeile = _zeile(teilzeit=None)
    assert "Auszahlung ohne Teilzeit 300.000,00 €" in zeile and "mit Teilzeit" not in zeile


def test_a_check_value_without_a_rate_gets_the_rate_that_leads_to_it():
    from finctl import renten
    from finctl.renten import Pruefwert

    q = _bav(pruefwert=Pruefwert(satz=None, cents=40_000_000, zum=date(2056, 1, 1)))
    s = renten.satz_zu(q, date(2056, 1, 1), 40_000_000)
    assert s > renten.satz(q, q.ab)
    zeile = _zeile(q)
    assert ("Prüfwert der Mitteilung 400.000,00 € zum 01/2056, ohne Satz; von Stand und "
            f"Beitrag führt ein Satz von {_prozent(s)} zu ihm") in zeile


def test_a_check_value_with_a_rate_keeps_it_and_still_names_the_rate_that_leads_to_it():
    from finctl.renten import Pruefwert

    q = _bav(pruefwert=Pruefwert(satz=0.06, cents=40_000_000, zum=date(2056, 1, 1)))
    zeile = _zeile(q)
    assert "zum 01/2056 bei 6,00 % laut Mitteilung; von Stand und Beitrag führt ein Satz" in zeile


def test_a_check_value_no_rate_can_reach_is_said_not_guessed():
    from finctl.renten import Pruefwert

    q = _bav(pruefwert=Pruefwert(satz=None, cents=10 ** 15, zum=date(2056, 1, 1)))
    assert "kein Satz von Stand und Beitrag führt zu ihm" in _zeile(q)


def test_without_a_check_value_the_line_has_none():
    assert "Prüfwert" not in _zeile()
