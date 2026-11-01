"""Objekte anlegen und entfernen, ohne YAML von Hand.

Der Grund fuers Entfernen steht in `docs/Generalization_plan.md`: Wer dieses
Werkzeug uebernimmt, erbt sonst fremde Wohnungen in seiner
Vermoegensrechnung. Seit Schritt 5 (N.3c) steht jedes Objekt mit seiner
Herleitung als Notiz in `properties.yaml` -- eine Datei, die die Seite ganz liest
und ganz schreibt.

Alle Objekte hier sind erfunden.
"""

from __future__ import annotations

import yaml

from finctl import objekte

ALTBAU = {
    "id": "altbau", "name": "Altbau Musterstadt", "address": "Musterweg 1",
    "acquired_on": "2019-03-01", "status": "rented", "afa_base_cents": 20000000,
    "notiz": "Herleitung, die kein Klick loeschen darf.\n\nZweiter Absatz.",
    "notiz_vom": "2026-03-01",
}
BEREICH = {"bereich": {"notiz": "Alle Objekte des Haushalts."}}


def _config(tmp_path):
    (tmp_path / "properties.yaml").write_text(
        yaml.safe_dump({"properties": [dict(ALTBAU)], "notizen": BEREICH}, allow_unicode=True),
        encoding="utf-8")
    return tmp_path


def _datei(tmp_path) -> dict:
    return yaml.safe_load((tmp_path / "properties.yaml").read_text(encoding="utf-8"))


# ------------------------------------------------------------------- anlegen

def test_a_new_property_stands_behind_the_others_and_keeps_every_note(tmp_path):
    cfg = _config(tmp_path)
    objekte.anlegen({"id": "neubau", "name": "Neubau Beispiel",
                     "status": "rented"}, cfg)

    datei = _datei(cfg)
    assert [p["id"] for p in datei["properties"]] == ["altbau", "neubau"]
    assert datei["properties"][0] == ALTBAU
    assert datei["properties"][1]["name"] == "Neubau Beispiel"
    assert datei["notizen"] == BEREICH
    assert set(objekte.vorhandene(cfg)) == {"altbau", "neubau"}
    assert not (cfg / "properties_custom.yaml").exists()


def test_a_field_set_on_the_page_lands_on_the_property_and_nothing_else_changes(tmp_path):
    """Eine Zahl von /immobilie steht am Eintrag, neben der AfA-Basis und der Notiz."""
    cfg = _config(tmp_path)
    assert objekte.felder_setzen("altbau", {"purchase_price_cents": 25000000,
                                            "afa_start": "2019-04-01"}, cfg)
    altbau = objekte.vorhandene(cfg)["altbau"]
    assert altbau["purchase_price_cents"] == 25000000
    assert altbau["afa_base_cents"] == 20000000
    assert (altbau["notiz"], altbau["notiz_vom"]) == (ALTBAU["notiz"], ALTBAU["notiz_vom"])
    # Ein leeres Feld nimmt die Angabe heraus; dasselbe noch einmal aendert nichts.
    assert objekte.felder_setzen("altbau", {"purchase_price_cents": ""}, cfg)
    assert "purchase_price_cents" not in objekte.vorhandene(cfg)["altbau"]
    assert not objekte.felder_setzen("altbau", {"purchase_price_cents": ""}, cfg)


def test_a_field_for_a_property_that_is_not_in_the_file_is_refused(tmp_path):
    """Sonst entstuende ein Eintrag ohne Namen, an dem `init` scheitert."""
    import pytest

    cfg = _config(tmp_path)
    vorher = (cfg / "properties.yaml").read_bytes()
    with pytest.raises(ValueError, match="Kein Objekt"):
        objekte.felder_setzen("erfunden", {"equity_cents": 100}, cfg)
    assert (cfg / "properties.yaml").read_bytes() == vorher


# ------------------------------------------------------------------- pruefen

def test_a_duplicate_key_is_refused(tmp_path):
    cfg = _config(tmp_path)
    fehler = objekte.pruefen(objekte.objekt(
        {"id": "altbau", "name": "X", "status": "rented"}),
        set(objekte.vorhandene(cfg)))
    assert any("schon vergeben" in f for f in fehler)


def test_the_form_asks_for_three_things_and_no_more(tmp_path):
    """Kennung, Name, Zustand -- mehr braucht ein Objekt hier nicht.

    Der erste Entwurf verlangte zusaetzlich das Anschaffungsdatum, mit der
    Zehnjahresfrist des §23 EStG als Begruendung. Was ein Objekt gekostet
    hat, steht aber laengst als einmaliger Betrag in der Planung, und wer ein
    Objekt anlegt, hat den Notarvertrag nicht neben sich liegen.
    """
    assert objekte.FELDER == ("id", "name", "status")
    assert objekte.pruefen(
        objekte.objekt({"id": "schlicht", "name": "Schlicht",
                        "status": "rented"}), set()) == []


def test_an_unknown_status_is_refused(tmp_path):
    """Die deutsche Beschriftung ist nicht die Kennung.

    Geprueft wird auf das VORHANDENSEIN eines Fehlers, nicht auf seinen Text:
    „vermietet" steht auch in der Aufzaehlung der gueltigen Zustaende, ein
    Test darauf koennte also gar nicht durchfallen.
    """
    assert objekte.pruefen(
        objekte.objekt({"id": "x", "name": "X", "status": "vermietet"}), set())
    assert objekte.pruefen(
        objekte.objekt({"id": "x", "name": "X", "status": ""}), set())
    # Und die Kennung selbst geht durch.
    assert objekte.pruefen(
        objekte.objekt({"id": "x", "name": "X", "status": "rented"}), set()) == []


# ------------------------------------------------------------------ entfernen

def test_removing_a_property_takes_it_out_of_the_file_with_its_note(tmp_path):
    cfg = _config(tmp_path)
    objekte.entfernen("altbau", cfg)

    assert "altbau" not in objekte.vorhandene(cfg)
    assert _datei(cfg)["properties"] == []
    assert _datei(cfg)["notizen"] == BEREICH


def test_removing_an_own_property_leaves_no_trace(tmp_path):
    cfg = _config(tmp_path)
    objekte.anlegen({"id": "neubau", "name": "Neubau", "status": "construction"}, cfg)
    objekte.entfernen("neubau", cfg)

    assert [p["id"] for p in _datei(cfg)["properties"]] == ["altbau"]
    assert set(objekte.vorhandene(cfg)) == {"altbau"}


def test_removing_something_that_does_not_exist_says_so(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="Kein Objekt"):
        objekte.entfernen("gibtsnicht", _config(tmp_path))


# ---------------------------------------------------------------- Seite

from fastapi.testclient import TestClient  # noqa: E402

from finctl.web.server import app  # noqa: E402

client = TestClient(app)


def test_the_page_offers_the_form_and_a_way_out():
    html = client.get("/immobilien").text
    assert 'id="o-id"' in html and 'id="o-status"' in html
    # Je Objekt ein Weg, es loszuwerden -- das ist der Teil, den ein neuer
    # Nutzer zuerst braucht.
    assert html.count("objektEntfernen(") >= 1


def test_the_status_list_offers_exactly_the_known_states():
    import re

    html = client.get("/immobilien").text
    block = html[html.index('id="o-status"'):]
    angeboten = set(re.findall(r'<option value="([^"]+)"',
                               block[:block.index("</select>")]))
    assert angeboten == set(objekte.ZUSTAENDE)


def test_the_endpoints_refuse_before_they_write():
    """Beide Ablehnungen kommen vor dem Schreiben, brauchen also keine
    Konfiguration -- und fassen die echte nicht an."""
    antwort = client.post("/api/objekt-neu", json={"id": "", "name": ""})
    assert antwort.status_code == 400 and "Kennung" in antwort.json()["error"]

    antwort = client.post("/api/objekt-entfernen", json={"id": "gibtsnicht"})
    assert antwort.status_code == 400 and "Kein Objekt" in antwort.json()["error"]
