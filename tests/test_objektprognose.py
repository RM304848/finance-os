"""Was ein Objekt kuenftig abwirft, steht am Objekt -- nicht in den Annahmen.

Bis zum 27.09.2026 stand die Prognose fuer genau ein Objekt in
assumptions.yaml, und der Code kannte seine Kennung. Wer zwei Objekte hat,
konnte nur eines prognostizieren; wer keines hat, sah trotzdem Felder dafuer.

Alle Objekte hier sind erfunden.
"""

from __future__ import annotations

from datetime import date

import pytest
import yaml

from finctl import objekte

BASIS = """properties:
  - id: altbau
    name: Altbau Musterstadt
    status: rented
    notiz: Die Begruendung, die kein Klick loeschen darf.
    notiz_vom: 2026-02-01
    prognose:
      miete_monatlich_cents: 120000
      kosten_monatlich_cents: 30000
      ab: 2026-01
      bis: 2030-06
  - id: inselhaus
    name: Inselhaus
    status: construction
    prognose:
      miete_monatlich_cents: 200000
      kosten_monatlich_cents: 80000
  - id: gemessen
    name: Ohne Prognose
    status: rented
  - id: verkauft
    name: Verkauft
    status: sold
    prognose:
      miete_monatlich_cents: 50000
"""


def _config(tmp_path):
    (tmp_path / "properties.yaml").write_text(BASIS, encoding="utf-8")
    return tmp_path


def test_every_object_with_a_forecast_has_its_own(tmp_path):
    """Zwei Objekte, zwei Prognosen. Ohne `prognose:` bleibt eines gemessen,
    und ein verkauftes wirft nichts mehr ab."""
    liste = objekte.prognosen(config_dir=_config(tmp_path))
    assert [p.id for p in liste] == ["altbau", "inselhaus"]
    altbau = liste[0]
    assert altbau.netto_cents == 90000
    assert (altbau.ab, altbau.bis) == (date(2026, 1, 1), date(2030, 6, 1))


def test_open_ends_mean_no_limit(tmp_path):
    """Ohne Beginn und Ende laeuft die Vermietung -- ein Leasehold traegt ein
    Ende, ein Haus keines."""
    altbau, inselhaus = objekte.prognosen(config_dir=_config(tmp_path))
    assert not altbau.laeuft(date(2025, 12, 1))
    assert altbau.laeuft(date(2030, 6, 1))
    assert not altbau.laeuft(date(2030, 7, 1))
    assert inselhaus.laeuft(date(2080, 1, 1))


def test_a_scenario_changes_amounts_per_object_not_the_dates(tmp_path):
    """Ein Szenario ist eine andere Annahmedatei. Beginn und Ende sind
    Fakten des Objekts und bleiben, wo sie stehen."""
    szenario = tmp_path / "pessimistisch.yaml"
    szenario.write_text(yaml.safe_dump({"immobilien": {"objekte": {
        "altbau": {"miete_monatlich_cents": 100000}}}}), encoding="utf-8")
    altbau = objekte.prognosen(szenario, config_dir=_config(tmp_path))[0]
    assert altbau.miete_cents == 100000
    assert altbau.kosten_cents == 30000
    assert altbau.bis == date(2030, 6, 1)


def test_the_page_writes_the_whole_entry_and_leaves_the_rest_of_it_alone(tmp_path):
    """Eine Datei: Die Seite schreibt die Prognose in den Eintrag. Was sie nicht nennt
    (die Saison, die Notiz), bleibt; ein leeres Feld nimmt die Angabe heraus."""
    cfg = _config(tmp_path)
    objekte.prognose_setzen("altbau", {"miete_monatlich_cents": 110000,
                                       "kosten_monatlich_cents": 30000,
                                       "ab": "2026-01", "bis": "2031-12"}, cfg)
    roh = yaml.safe_load((cfg / "properties.yaml").read_text(encoding="utf-8"))
    altbau_roh = roh["properties"][0]
    assert altbau_roh["prognose"] == {"miete_monatlich_cents": 110000,
                                      "kosten_monatlich_cents": 30000,
                                      "ab": "2026-01", "bis": "2031-12"}
    assert altbau_roh["notiz"] == "Die Begruendung, die kein Klick loeschen darf."
    assert str(altbau_roh["notiz_vom"]) == "2026-02-01"
    altbau = objekte.prognosen(config_dir=cfg)[0]
    assert (altbau.miete_cents, altbau.kosten_cents) == (110000, 30000)
    assert altbau.bis == date(2031, 12, 1)
    # Ein leeres Feld: Die Angabe ist weg, nicht auf eine Vorgabe zurueck.
    objekte.prognose_setzen("altbau", {"miete_monatlich_cents": 120000, "bis": ""}, cfg)
    altbau = objekte.prognosen(config_dir=cfg)[0]
    assert altbau.miete_cents == 120000 and altbau.bis is None
    assert not (cfg / "properties_custom.yaml").exists()


def test_saving_the_forecast_unchanged_changes_no_byte(tmp_path):
    """Ein Monat steht als `2026-01` oder als Datum; die Seite zeigt `2026-01` und
    schickt es zurueck. Das ist keine Aenderung."""
    cfg = _config(tmp_path)
    text = (cfg / "properties.yaml").read_text(encoding="utf-8")
    (cfg / "properties.yaml").write_text(text.replace("ab: 2026-01", "ab: 2026-01-01"),
                                         encoding="utf-8")
    vorher = (cfg / "properties.yaml").read_bytes()
    objekte.prognose_setzen("altbau", {"miete_monatlich_cents": 120000,
                                       "kosten_monatlich_cents": 30000,
                                       "ab": "2026-01", "bis": "2030-06"}, cfg)
    assert (cfg / "properties.yaml").read_bytes() == vorher


def test_a_forecast_can_be_started_from_the_page(tmp_path):
    """Wer ein Objekt hat, aber keine Prognose, legt sie auf der Seite an."""
    cfg = _config(tmp_path)
    objekte.prognose_setzen("gemessen", {"miete_monatlich_cents": 70000}, cfg)
    assert "gemessen" in [p.id for p in objekte.prognosen(config_dir=cfg)]


@pytest.mark.parametrize("felder", [{"ab": "2026"}, {"bis": "12/2030"},
                                    {"miete_monatlich_cents": -100}])
def test_wrong_input_is_refused(tmp_path, felder):
    with pytest.raises(ValueError):
        objekte.prognose_setzen("altbau", felder, _config(tmp_path))


def test_seasonality_must_sum_to_twelve():
    """Saisonalitaet verschiebt Geld zwischen Monaten, sie erfindet keines.

    Eine Kurve, die sich nebenbei auf 13 summiert, waere eine verdeckte
    Ertragsannahme -- und zwar eine, die niemand als solche liest, weil sie
    als Verteilung daherkommt.
    """
    kurve = [0.6, 0.6, 0.7, 0.8, 1.0, 1.2, 1.6, 1.6, 1.2, 0.8, 0.9, 1.0]
    assert abs(sum(objekte.saison(kurve)) - 12.0) < 0.01
    with pytest.raises(ValueError, match="summiert sich"):
        objekte.saison([1.1] * 12)
    with pytest.raises(ValueError, match="12"):
        objekte.saison([1.0] * 11)
    assert objekte.saison(None) == (1.0,) * 12
