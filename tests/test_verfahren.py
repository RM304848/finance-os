"""Die Verfahren als reine Funktionen: erfundene Monatsreihen, keine Datenbank.

Jeder Fall nimmt eine Reihe, die genau den Randfall zeigt, an dem ein
Verfahren in der Vergangenheit falsch lag. Die Zahlen sind rund und erfunden.
"""

from __future__ import annotations

import pytest

from finctl.forecast import verfahren as vf


def _cfg(**anders) -> vf.Einstellung:
    werte = dict(rate=0.0, since="2026-04-01",
                 ende_monat="2026-09", fenster_monate=6, is_fixed=set())
    werte.update(anders)
    return vf.Einstellung(**werte)


def _reihe(*paare: tuple[str, int]) -> tuple[list[str], list[int]]:
    return [m for m, _ in paare], [c for _, c in paare]


# --- Jüngst ----------------------------------------------------------------


def test_juengst_sums_only_the_last_three_months_of_the_window():
    """Sechs Monate im Fenster, aber nur 07 bis 09 zaehlen: 3 x 100 aufs Jahr."""
    monate, betraege = _reihe(("2026-04", -9000), ("2026-05", -9000),
                              ("2026-07", -10000), ("2026-08", -10000),
                              ("2026-09", -10000))
    erg = vf.juengst("x", monate, betraege, _cfg())
    assert erg.cents == -120000
    assert erg.herkunft.herleitung == (
        "Summe −300,00 € über die letzten 3 Monate (07/2026–09/2026), "
        "aufs Jahr −1.200,00 €")
    assert erg.herkunft.verweis == "x"


def test_juengst_keeps_a_category_without_booking_in_those_months_at_zero():
    """Ein Posten mit null, kein fehlender: beide Tempi zeigen dieselbe Menge."""
    monate, betraege = _reihe(("2026-04", -9000), ("2026-05", -9000))
    erg = vf.juengst("x", monate, betraege, _cfg())
    assert erg is not None
    assert erg.cents == 0
    assert "Summe 0,00 € über die letzten 3 Monate (07/2026–09/2026)" in (
        erg.herkunft.herleitung)


def test_juengst_with_a_two_month_window_divides_by_two():
    monate, betraege = _reihe(("2026-08", -1000), ("2026-09", -3000))
    erg = vf.juengst("x", monate, betraege, _cfg(fenster_monate=2))
    assert erg.cents == vf.summe_aufs_jahr(-4000, 2) == -24000
    assert "über die letzten 2 Monate (08/2026–09/2026)" in erg.herkunft.herleitung


def test_juengst_with_a_one_month_window_names_that_month():
    monate, betraege = _reihe(("2026-09", -1000))
    erg = vf.juengst("x", monate, betraege, _cfg(fenster_monate=1))
    assert erg.cents == -12000
    assert "über den letzten Monat (09/2026)" in erg.herkunft.herleitung


def test_juengst_without_months_in_the_window_is_no_item():
    assert vf.juengst("x", [], [], _cfg(fenster_monate=0)) is None


def test_juengst_counts_a_cost_that_was_net_positive_in_the_window_as_income():
    """Kosten oder Einnahme entscheidet die Summe des ganzen Fensters, nicht die
    der drei Monate: Eine Erstattung im Fenster bleibt beim Schnitt."""
    tabelle = vf.HOCHRECHNUNG_JUENGST
    monate, betraege = _reihe(("2026-04", 9000), ("2026-08", -1000))
    erg = vf.wahl("x", monate, betraege, _cfg(), tabelle)
    assert erg.cents == vf.summe_aufs_jahr(8000, 6)
    assert "über 6 Monate" in erg.herkunft.herleitung


def test_the_juengst_table_changes_only_the_costs():
    assert vf.HOCHRECHNUNG_JUENGST[vf.KOSTEN] == vf.Regel("summe", fenster="juengst")
    assert vf.HOCHRECHNUNG_JUENGST[vf.FIXKOSTEN] == vf.HOCHRECHNUNG[vf.FIXKOSTEN]
    assert vf.HOCHRECHNUNG_JUENGST[vf.EINNAHME] == vf.HOCHRECHNUNG[vf.EINNAHME]


def test_wahl_follows_the_juengst_window_of_the_rule_for_costs():
    monate, betraege = _reihe(("2026-04", -9000), ("2026-08", -1000),
                              ("2026-09", -1000))
    schnitt_ = vf.wahl("x", monate, betraege, _cfg(), vf.HOCHRECHNUNG)
    juengst_ = vf.wahl("x", monate, betraege, _cfg(), vf.HOCHRECHNUNG_JUENGST)
    assert schnitt_.cents == vf.summe_aufs_jahr(-11000, 6)
    assert juengst_.cents == vf.summe_aufs_jahr(-2000, 3)


def test_the_juengst_window_is_only_for_the_sum():
    with pytest.raises(ValueError, match="juengst"):
        vf.Regel("schnitt", fenster="juengst")


# --- Schnitt ---------------------------------------------------------------


def test_schnitt_counts_months_without_booking_as_zero():
    """Zwei Buchungen in sechs Monaten: durch sechs, nicht durch zwei."""
    monate, betraege = _reihe(("2026-05", -3000), ("2026-08", -3000))
    erg = vf.schnitt("x", monate, betraege, _cfg())
    assert erg.cents == -1000
    assert erg.herkunft.herleitung.startswith(
        "Summe −60,00 € über 6 vollständige Monate, im Monat −10,00 € (2 mit Buchung)")


def test_schnitt_rounds_half_to_even():
    monate, betraege = _reihe(("2026-05", -5), ("2026-08", -5))
    assert vf.schnitt("x", monate, betraege, _cfg(fenster_monate=4)).cents == -2


def test_schnitt_of_a_vanishing_amount_is_no_item():
    monate, betraege = _reihe(("2026-05", -1), ("2026-08", 1))
    assert vf.schnitt("x", monate, betraege, _cfg()) is None


FIX = {"vers"}


# --- Summe aufs Jahr -------------------------------------------------------


def test_summe_aufs_jahr_scales_the_window_to_twelve_months():
    assert vf.summe_aufs_jahr(-60000, 6) == -120000


def test_summe_aufs_jahr_rounds_once_on_the_summed_cents():
    """Je Konto gerundet und dann addiert wäre ein Cent anders."""
    assert vf.summe_aufs_jahr(-100, 7) == -171
    assert 2 * vf.summe_aufs_jahr(-50, 7) == -172


# --- die Tabellen ----------------------------------------------------------


def _wahl(kategorie, paare, regeln, **anders):
    monate, betraege = _reihe(*paare)
    return vf.wahl(kategorie, monate, betraege, _cfg(**anders), regeln)


def test_the_kontoprognose_table_works_out_costs_and_income_alike():
    """Kosten wie Einnahmen: die Summe des Fensters durch seine Monate, auch eine
    Kategorie, die nur zweimal vorkam. Es gibt keine Mindestzahl."""
    erg = _wahl("laden", [("2026-05", -3000), ("2026-08", -3000)], vf.KONTOPROGNOSE)
    assert erg.cents == -1000
    lohn = _wahl("lohn", [("2026-05", 3000), ("2026-08", 3000)], vf.KONTOPROGNOSE)
    assert lohn.cents == 1000


def test_the_kontoprognose_table_is_the_hochrechnung_sum_per_month():
    """Dieselbe Rechnung wie `HOCHRECHNUNG`, nur nicht aufs Jahr: Ueber die Konten
    summiert ergibt sie die Zahl der Hochrechnung bis auf die Rundung eines Cents."""
    reihen = [
        [("2026-04", -1000), ("2026-05", -2000), ("2026-06", -3000)],
        [("2026-05", -3000), ("2026-08", -3000)],
        [("2026-07", 7000)],
        [("2026-04", -7), ("2026-09", -8)],
    ]
    for paare in reihen:
        monat = _wahl("x", paare, vf.KONTOPROGNOSE)
        jahr = _wahl("x", paare, vf.HOCHRECHNUNG)
        assert monat is not None and jahr is not None
        assert abs(monat.cents * 12 - jahr.cents) <= 6


def test_the_kontoprognose_table_without_months_in_the_window_is_no_item():
    paare = [("2026-04", -1000), ("2026-05", -2000), ("2026-06", -3000)]
    assert _wahl("laden", paare, vf.KONTOPROGNOSE, fenster_monate=0) is None


def test_the_kontoprognose_table_has_no_row_for_fixkosten():
    """Der Takt der Fixkosten steckt in den Reihen (`takt.py`); was davon im Rest
    bleibt, rechnet wie jede Kategorie."""
    assert set(vf.KONTOPROGNOSE) == {vf.KOSTEN, vf.EINNAHME}
    assert {r.verfahren for r in vf.KONTOPROGNOSE.values()} == {"schnitt"}


def test_the_rest_of_a_fixkosten_category_is_worked_out_like_any_cost_or_income():
    kosten = _wahl("vers", [("2026-05", -3000), ("2026-08", -3000)], vf.KONTOPROGNOSE,
                   is_fixed=FIX)
    assert kosten.cents == -1000 and kosten.every_months == 1 and kosten.starts is None
    erstattung = [("2026-04", 600), ("2026-05", 600), ("2026-06", 600)]
    assert _wahl("vers", erstattung, vf.KONTOPROGNOSE, is_fixed=FIX).cents == 300


def test_the_hochrechnung_table_knows_one_verfahren_for_every_kind():
    assert {r.verfahren for r in vf.HOCHRECHNUNG.values()} == {"summe"}
    assert set(vf.HOCHRECHNUNG) == {vf.FIXKOSTEN, vf.KOSTEN, vf.EINNAHME}


def test_the_kind_of_a_category_follows_the_flag_and_the_sign():
    assert vf.art_der_kategorie("v", [100], {"v"}) == vf.FIXKOSTEN
    assert vf.art_der_kategorie("l", [-100, 40], set()) == vf.KOSTEN
    assert vf.art_der_kategorie("l", [-100, 100], set()) == vf.EINNAHME


def test_wahl_with_the_hochrechnung_table_sums_every_kind_onto_the_year():
    """Ohne Mindestzahl: jede Art Kategorie wird zur Summe des Fensters aufs Jahr,
    auch eine, die nur einmal vorkam."""
    kosten = _wahl("laden", [("2026-05", -3000)], vf.HOCHRECHNUNG)
    assert kosten.cents == vf.summe_aufs_jahr(-3000, 6) == -6000
    einnahme = _wahl("lohn", [("2026-04", 100), ("2026-05", 100), ("2026-06", 100),
                              ("2026-07", 100), ("2026-08", 100), ("2026-09", 700)],
                     vf.HOCHRECHNUNG)
    assert einnahme.cents == vf.summe_aufs_jahr(1200, 6) == 2400
    fix = _wahl("vers", [("2026-01", -60000)], vf.HOCHRECHNUNG, is_fixed=FIX)
    assert fix.cents == -120000 and fix.every_months == 1 and fix.starts is None


def test_wahl_with_the_hochrechnung_table_keeps_a_sum_of_zero():
    erg = _wahl("laden", [("2026-04", -100), ("2026-05", 100)], vf.HOCHRECHNUNG)
    assert erg is not None and erg.cents == 0


def test_summe_without_months_in_the_window_is_no_item():
    assert _wahl("laden", [("2026-05", -3000)], vf.HOCHRECHNUNG,
                 fenster_monate=0) is None


def test_herkunft_summe_is_only_used_where_posten_are_summands():
    """`Posten.cents` ist in der Hochrechnung ein Summand, in der Kontoprognose
    der Betrag je Termin (siehe `herkunft.Posten`). Die Summe ueber Posten der
    Kontoprognose waere eine Zahl ohne Sinn; `summe` kommt deshalb nur in der
    Jahresrechnung vor."""
    import ast
    from pathlib import Path

    wurzel = Path(vf.__file__).resolve().parents[1]
    nutzer = set()
    for datei in wurzel.rglob("*.py"):
        for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            holt = (isinstance(knoten, ast.ImportFrom)
                    and knoten.module == "finctl.forecast.herkunft"
                    and any(a.name == "summe" for a in knoten.names))
            ruft = (isinstance(knoten, ast.Attribute) and knoten.attr == "summe"
                    and isinstance(knoten.value, ast.Name) and knoten.value.id == "herkunft")
            if holt or ruft:
                nutzer.add(datei.relative_to(wurzel).as_posix())
    assert nutzer == {"forecast/jahre.py"}
