"""Steuersatz auf Kapitalertraege und Basiszins: zwei Annahmen, die die Seite dreht.

Beide standen nur in der Datei. Der Steuersatz haengt am persoenlichen Satz (Kirchensteuer
ja oder nein), der Basiszins aendert sich jedes Jahr: Beides ist eine Eingabe, die ein
Haushalt im ersten Jahr braucht.

Testdaten sind erfunden.
"""

from __future__ import annotations

import pytest
import yaml
from fastapi.testclient import TestClient

from finctl import assumptions as ann
from finctl.ledger import db as ledger
from finctl.web.routen import annahmen as seite
from finctl.web.server import app

START = {"inflation_pa": 0.02,
         "kapital": {"rendite_nominal_pa": 0.025, "rendite_depot_pa": 0.05,
                     "vorabpauschale": {"basiszins_pa": 0.0253, "teilfreistellung": 0.3,
                                        "steuersatz": 0.26375}}}


@pytest.fixture
def datei(tmp_path):
    pfad = tmp_path / "assumptions.yaml"
    pfad.write_text(yaml.safe_dump(START), encoding="utf-8")
    ann.reset_cache()
    yield pfad
    ann.reset_cache()


def test_both_are_assumptions_the_page_may_turn():
    assert ann.UEBERSCHREIBBAR["steuersatz_kapital"] == ("kapital", "vorabpauschale", "steuersatz")
    assert ann.UEBERSCHREIBBAR["basiszins_pa"] == ("kapital", "vorabpauschale", "basiszins_pa")
    gezeigt = {k for k, *_ in seite.STELLSCHRAUBEN}
    assert {"steuersatz_kapital", "basiszins_pa"} <= gezeigt


def test_a_new_rate_reaches_the_calculation_and_keeps_the_rest_of_the_block(datei):
    assert ann.setzen("steuersatz_kapital", 0.25, datei)
    assert ann.setzen("basiszins_pa", 0.031, datei)
    basis, steuer = ann.vorabpauschale(datei)
    assert basis == pytest.approx(0.031 * 0.7) and steuer == 0.25
    # Die Teilfreistellung steht weiter im Block und bleibt, wie sie war.
    assert yaml.safe_load(datei.read_text(encoding="utf-8"))["kapital"]["vorabpauschale"][
        "teilfreistellung"] == 0.3


@pytest.mark.parametrize("key, wert", [("steuersatz_kapital", 0.26375), ("basiszins_pa", 0.0253)])
def test_the_field_shows_the_rate_whole_and_saving_it_again_writes_no_byte(datei, key, wert):
    """26,375 % stuende sonst gerundet im Feld, und Speichern schriebe einen anderen Satz."""
    text = seite._feldtext("prozent", wert)
    assert ledger.prozent_als_anteil(text) == pytest.approx(wert, abs=1e-12)
    vorher = datei.read_bytes()
    assert ann.setzen(key, ledger.prozent_als_anteil(text), datei) is False
    assert datei.read_bytes() == vorher


def test_a_percentage_keeps_two_places_unless_it_needs_more():
    assert seite._feldtext("prozent", 0.02) == "2,00"
    assert seite._feldtext("prozent", 0.0253) == "2,53"
    assert seite._feldtext("prozent", 0.26375) == "26,375"
    assert seite._feldtext("euro", 100_000) == "1.000,00"


def test_the_page_offers_both_fields_and_no_rate_stands_in_fixed_text():
    client = TestClient(app)
    html = client.get("/annahmen").text
    assert 'id="a-steuersatz_kapital"' in html and 'id="a-basiszins_pa"' in html
    # Der Satz steht im Feld, nicht in einem festen Satz daneben: Er ist drehbar.
    assert "26,375 %" not in html
    assert "26,375 %" not in client.get("/hochrechnung").text
