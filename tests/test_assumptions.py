"""The one place a guess is allowed to live.

The file exists to draw one line: an ANNAHME is something somebody chose, a
FAKT is something a document says. Loan rates, AfA bases and policy values stay
where their derivation sits; only the choices move here.

What it replaces is worth naming. Three figures were written down in three
places each -- the Tagesgeld target in a waterfall description, in a goal and
in the settings table; the salary floor in forecast.yaml, in lebensplan.yaml
and in settings. A module existed whose only job was to notice when they had
already drifted apart. Noticing afterwards is the weaker guarantee: these tests
stop the copy being made.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from finctl import assumptions as ann

CONFIG = Path("config")


def test_the_documented_values_load():
    """Was in assumptions.yaml steht, kommt so an. Die Werte selbst stehen
    dort und nicht hier: ein Test, der sie wiederholt, prueft eine Abschrift."""
    import yaml

    datei = yaml.safe_load(ann.PATH.read_text(encoding="utf-8"))
    assert ann.inflation_pa() == pytest.approx(datei["inflation_pa"])
    assert ann.rendite_nominal_pa() == pytest.approx(datei["kapital"]["rendite_nominal_pa"])
    assert ann.salary_floor_cents() == \
        datei["erwerbseinkommen"]["netto_floor_monatlich_cents"]


def test_the_salary_steps_up_on_the_first_of_january_after_the_base_year():
    """Eine Regel fuer beide Modelle: im Basisjahr die Untergrenze, wie sie ist, danach
    zum 1. Januar ein Mal die Steigerung; vor dem Basisjahr steigt nichts."""
    floor = 400_000
    assert ann.gehalt_im_jahr(floor, 2026, 2026, 0.02) == floor
    assert ann.gehalt_im_jahr(floor, 2027, 2026, 0.02) == 408_000
    assert ann.gehalt_im_jahr(floor, 2028, 2026, 0.02) == ann.grow(floor, 2, 0.02)
    assert ann.gehalt_im_jahr(floor, 2025, 2026, 0.02) == floor


def test_salary_growth_is_its_own_assumption():
    """Sie mit der Inflation gleichzusetzen unterstellt, dass die Inflation
    dauerhaft eingeholt wird -- möglich, aber eine Annahme, die sichtbar
    gehört."""
    assert ann.salary_growth_pa() == 0.02
    assert ann.grow(100000, 10, 0.01) < ann.grow(100000, 10, 0.02)


def test_a_missing_key_raises_rather_than_returning_zero():
    """A projection that silently falls back to zero inflation produces a
    confident, wrong answer, and nothing in the output would say so."""
    with pytest.raises(KeyError, match=r"gibt.es.nicht|fehlt"):
        ann.get("gibt", "es", "nicht")
    assert ann.get("gibt", "es", "nicht", default=7) == 7


def test_inflation_carries_an_amount_forward():
    # 4.000 a month, nineteen years at 2 %.
    assert ann.inflate(400000, 19) == pytest.approx(582700, abs=50)


def test_a_scenario_is_a_different_file(tmp_path):
    """No feature, no table, no screen -- a copy with different values."""
    other = tmp_path / "pessimistisch.yaml"
    other.write_text(yaml.safe_dump({
        "inflation_pa": 0.035,
        "kapital": {"rendite_nominal_pa": 0.02},
        "erwerbseinkommen": {"netto_floor_monatlich_cents": 400000},
    }), encoding="utf-8")
    assert ann.inflation_pa(other) == 0.035
    assert ann.salary_floor_cents(other) == 400000
    # The default file is untouched by reading another one.
    assert ann.inflation_pa() == 0.02


# ------------------------------------------------- the single-source rule

def _other_configs() -> list[Path]:
    """Everything that is not an assumptions file.

    Scenario files are named assumptions.<name>.yaml and are SUPPOSED to
    restate the same keys with different values -- that is what a scenario
    is. Excluding them by name rather than by guessing keeps the rule sharp
    for the files where a repeated value really is a second source.
    """
    skip = {"overrides.yaml", "rules.yaml", "taxonomy.yaml",
            "taxonomy_custom.yaml", "taxonomy_migrations.yaml",
            "accounts.example.yaml"}
    return [p for p in sorted(CONFIG.glob("*.yaml"))
            if p.name not in skip and not p.name.startswith("assumptions.")
            and p.name != "assumptions.yaml"]


@pytest.mark.parametrize("value,label", [
    (467100, "Gehalts-Untergrenze"),
    (0.0404, "nominale Rendite"),
    (0.07, "Depotrendite"),
])
def test_an_assumption_is_not_restated_elsewhere(value, label):
    """Restating it is how the three-way drift happened in the first place.

    A config file may EXPLAIN a figure at length -- that is what makes these
    files worth reading. It may not state it as a value a loader could pick up,
    because then there are two answers to one question and nothing decides
    between them.
    """
    pattern = re.compile(rf"^\s*[a-z_]+:\s*{re.escape(str(value))}\s*(?:#.*)?$",
                         re.M)
    guilty = [p.name for p in _other_configs()
              if pattern.search(p.read_text(encoding="utf-8"))]
    assert guilty == [], (
        f"{label} steht ausser in assumptions.yaml auch in {guilty}. "
        f"Erklären ja, zweitens hinschreiben nein.")


def test_facts_stay_out_of_the_assumptions_file():
    """Loan rates, AfA bases and policy values belong to their documents.

    Moving them here would strip them of the derivation that makes them
    checkable -- and would quietly turn a contractual figure into something
    that looks adjustable.
    """
    text = (CONFIG / "assumptions.yaml").read_text(encoding="utf-8")
    spec = yaml.safe_load(text)
    flat = yaml.safe_dump(spec)
    for forbidden in ("annual_rate_pct", "afa_base_cents", "policenwert",
                      "annuity_cents", "opening_balance_cents"):
        assert forbidden not in flat, f"{forbidden} ist ein Fakt, keine Annahme"


def test_the_shipped_seasonality_is_flat():
    """Ein gemessener Mietmonat gibt keine Jahreskurve her.

    Eine erfundene wäre schlechter als keine: sie erzeugte Liquiditätslöcher
    in Monaten, die nie gemessen wurden, und Entwarnung in anderen. Die
    Kurve steht je Objekt unter `prognose.saison` (tests/test_objektprognose.py).
    """
    from finctl import objekte

    for p in objekte.prognosen():
        assert p.saison == (1.0,) * 12, p.id


def test_the_allowance_falls_back_to_the_statutory_amount(tmp_path):
    """Eine Datei ohne den Eintrag rechnet mit dem gesetzlichen Betrag fuer eine
    Person -- nicht mit null, das waere eine Steuer, die niemand gewaehlt hat."""
    ohne = tmp_path / "ohne.yaml"
    ohne.write_text(yaml.safe_dump({"kapital": {"rendite_nominal_pa": 0.02}}),
                    encoding="utf-8")
    assert ann.sparerpauschbetrag_cents(ohne) == ann.SPARERPAUSCHBETRAG_VORGABE
    mit = tmp_path / "mit.yaml"
    mit.write_text(yaml.safe_dump({"kapital": {"sparerpauschbetrag_cents": 200_000}}),
                   encoding="utf-8")
    assert ann.sparerpauschbetrag_cents(mit) == 200_000
    null = tmp_path / "null.yaml"
    null.write_text(yaml.safe_dump({"kapital": {"sparerpauschbetrag_cents": 0}}),
                    encoding="utf-8")
    assert ann.sparerpauschbetrag_cents(null) == 0, "null ist eine Antwort, kein Fehlen"


def test_the_shipped_allowance_equals_the_fallback_in_the_code():
    vorgabe = Path(ann.__file__).parent / "vorgaben" / "assumptions.yaml"
    wert = yaml.safe_load(vorgabe.read_text(encoding="utf-8"))["kapital"][
        "sparerpauschbetrag_cents"]
    assert wert == ann.SPARERPAUSCHBETRAG_VORGABE
    assert ann.wert("sparerpauschbetrag_cents") in (
        ann.in_datei("sparerpauschbetrag_cents"), ann.SPARERPAUSCHBETRAG_VORGABE)
