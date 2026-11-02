"""Ziele im Dashboard anlegen und loeschen.

Der Betrag wird eingetragen, nicht berechnet. Die Seite schreibt das ganze Ziel in
goals.yaml, mit seiner Notiz; ein geloeschtes Ziel faellt samt Notiz aus der Datei.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from finctl.web.server import app

client = TestClient(app)
PFAD = Path("config/goals.yaml")


def _gesichert(lauf) -> None:
    vorher = PFAD.read_bytes()
    try:
        lauf()
    finally:
        PFAD.write_bytes(vorher)


def test_a_goal_can_be_added_and_removed_from_the_page():
    def lauf():
        r = client.post("/api/ziel", json={
            "neu": True, "name": "Pytest Hebel", "cents": 12_345_600,
            "stichtag": "2035-12-31", "basis": ["depot"], "notiz": "eingetragen"})
        assert r.status_code == 200, r.text
        html = client.get("/ziele").text
        assert "Pytest Hebel" in html and "123.456,00" in html
        assert 'id="z-cents-pytest-hebel"' in html

        doppelt = client.post("/api/ziel", json={"neu": True, "name": "Pytest Hebel",
                                                 "cents": 100})
        assert doppelt.status_code == 400

        assert client.post("/api/ziel", json={"id": "pytest-hebel",
                                              "loeschen": True}).status_code == 200
        assert "Pytest Hebel" not in client.get("/ziele").text
    _gesichert(lauf)


def _erstes_basisziel() -> str:
    """Irgendein Ziel aus goals.yaml -- welche dort stehen, aendert sich."""
    import yaml

    spec = yaml.safe_load(Path("config/goals.yaml").read_text(encoding="utf-8")) or {}
    ziele = [g["id"] for g in (spec.get("ziele") or []) if g.get("id")]
    assert ziele, "goals.yaml ohne Ziel"
    return ziele[0]


def test_a_deleted_goal_is_gone_from_goals_yaml_with_its_note():
    import yaml

    def lauf():
        gid = _erstes_basisziel()
        assert client.post("/api/ziel", json={"id": gid, "loeschen": True}).status_code == 200
        spec = yaml.safe_load(PFAD.read_text(encoding="utf-8")) or {}
        assert gid not in [g.get("id") for g in spec.get("ziele") or []]
        assert f'id="z-cents-{gid}"' not in client.get("/ziele").text
    _gesichert(lauf)


def test_a_new_goal_needs_a_name_an_amount_and_a_real_date():
    def lauf():
        vorher = PFAD.read_bytes()
        for body in ({"neu": True, "cents": 100},
                     {"neu": True, "name": "Pytest ohne Betrag"},
                     {"neu": True, "name": "Pytest Datum", "cents": 100,
                      "stichtag": "2035-13-01"}):
            assert client.post("/api/ziel", json=body).status_code == 400, body
        assert PFAD.read_bytes() == vorher, "eine abgelehnte Eingabe schreibt nichts"
    _gesichert(lauf)


def test_a_dragged_order_is_kept_and_survives_saving_a_goal():
    import re

    def lauf():
        # Ziehen braucht zwei Ziele. Wie viele konfiguriert sind, entscheidet
        # die Seite -- bis auf den Puffer wird jedes dort angelegt.
        if len(re.findall(r'data-ziel="([^"]+)"', client.get("/ziele").text)) < 2:
            r = client.post("/api/ziel", json={"neu": True, "name": "Pytest Zweitziel",
                                               "cents": 100})
            assert r.status_code == 200, r.text
        vorher = re.findall(r'data-ziel="([^"]+)"', client.get("/ziele").text)
        assert len(vorher) >= 2
        neu = list(reversed(vorher))
        assert client.post("/api/ziele/reihenfolge", json={"ids": neu}).status_code == 200
        assert re.findall(r'data-ziel="([^"]+)"', client.get("/ziele").text) == neu

        # Ein gespeichertes Ziel wirft die gezogene Reihenfolge nicht weg.
        # Die Rentenluecke ist gerechnet und hat nichts zu speichern.
        bearbeitbar = next(z for z in neu if z != "rentenluecke")
        assert client.post("/api/ziel", json={"id": bearbeitbar,
                                              "notiz": "pytest"}).status_code == 200
        assert re.findall(r'data-ziel="([^"]+)"', client.get("/ziele").text) == neu

        # Ein spaeter angelegtes Ziel kommt ans Ende, statt die Ordnung zu stoeren.
        client.post("/api/ziel", json={"neu": True, "name": "Pytest Spaet", "cents": 100})
        danach = re.findall(r'data-ziel="([^"]+)"', client.get("/ziele").text)
        assert danach[:len(neu)] == neu and danach[-1] == "pytest-spaet"
    _gesichert(lauf)


def test_a_goal_over_all_liquid_assets_says_that_the_emergency_fund_is_left_out():
    import re

    def lauf():
        client.post("/api/ziel", json={"neu": True, "name": "Pytest Alles",
                                       "cents": 1_000_000_00})
        html = client.get("/ziele").text
        karte = html[html.index('data-ziel="pytest-alles"'):]
        karte = karte[:karte.index("</details>")]
        assert "ohne Notgroschen" in karte
        assert re.search(r"ohne Notgroschen [\d.]+,\d\d", karte)
    _gesichert(lauf)


def _karte_von(html: str, gid: str) -> str:
    """Der HTML-Ausschnitt einer Karte, bis die naechste beginnt."""
    karte = html.split(f'data-ziel="{gid}"', 1)[1]
    return karte.split('data-ziel="', 1)[0].split("<style>", 1)[0]


def test_a_goal_with_a_date_and_a_depot_shows_both_monthly_rates_and_the_way_to_the_second():
    import re

    def lauf():
        # Ein Zielbetrag, den kein Bestand allein erreicht, damit es eine Rate gibt.
        client.post("/api/ziel", json={"neu": True, "name": "Pytest Raten",
                                       "cents": 1_000_000_000_00, "stichtag": "2060-12-31",
                                       "basis": ["depot"]})
        karte = _karte_von(client.get("/ziele").text, "pytest-raten")
        assert re.search(r"[\d.]+,\d\d\s*€/Monat ohne Rendite\s*·\s*[\d.]+,\d\d\s*€ mit \d+,\d\d %",
                         karte)
        assert "nötig" not in karte
        # Die Herleitung steht im aufklappbaren Rechenweg, auch bei einem Ziel, das nicht
        # gerechnet ist.
        rechenweg = karte.split('<details class="rechenweg-ziel">', 1)[1].split("</details>")[0]
        assert "Lücke:" in rechenweg and "Rate:" in rechenweg
        assert "Rentenbeginn" not in rechenweg
    _gesichert(lauf)


def test_a_goal_without_a_date_shows_no_second_rate_and_no_rechenweg():
    def lauf():
        client.post("/api/ziel", json={"neu": True, "name": "Pytest Offen",
                                       "cents": 1_000_000_00, "basis": ["depot"]})
        karte = _karte_von(client.get("/ziele").text, "pytest-offen")
        assert "ohne Rendite" not in karte and "mit Rendite" not in karte
        assert 'class="rechenweg-ziel"' not in karte
    _gesichert(lauf)


def test_a_goal_can_be_renamed_without_changing_its_identity():
    """Der Name war nur Ueberschrift: angelegt hiess getauft.

    Die Kennung bleibt, was sie beim Anlegen wurde -- an ihr haengen das
    Overlay, die gezogene Reihenfolge und die Stellen, die ein Ziel im Code
    suchen. Ein Umbenennen, das die Kennung mitzieht, waere ein Loeschen mit
    anschliessendem Neuanlegen.
    """
    def lauf():
        r = client.post("/api/ziel", json={"neu": True, "name": "Pytest Taufe",
                                           "cents": 500_00})
        assert r.status_code == 200, r.text
        gid = r.json()["id"]

        html = client.get("/ziele").text
        assert f'id="z-name-{gid}"' in html, "kein Namensfeld an der Karte"

        assert client.post("/api/ziel", json={"id": gid,
                                              "name": "Pytest Umbenannt"}).status_code == 200
        html = client.get("/ziele").text
        assert "Pytest Umbenannt" in html and "Pytest Taufe" not in html
        assert f'data-ziel="{gid}"' in html, "die Kennung darf sich nicht aendern"

        # Leer laesst den Namen stehen, statt ein Ziel ohne Bezeichnung zu hinterlassen.
        assert client.post("/api/ziel", json={"id": gid, "name": "  ",
                                              "notiz": "x"}).status_code == 200
        assert "Pytest Umbenannt" in client.get("/ziele").text
    _gesichert(lauf)


def test_the_pension_gap_is_a_goal_even_before_it_can_be_computed(monkeypatch):
    """Ohne Geburtsdatum laesst sie sich nicht rechnen -- die Seite zeigt sie
    trotzdem und sagt, was fehlt."""
    from finctl.forecast import rentenluecke as rl

    monkeypatch.setattr(rl, "rechnen", lambda lauf, e: None)
    html = client.get("/ziele").text
    karte = html.split('data-ziel="rentenluecke"')[1].split("</div>\n</div>")[0]
    assert "Rentenlücke" in karte and 'href="/einrichtung#person"' in karte


def test_a_goal_with_an_extrapolation_shows_both_tempi_side_by_side():
    html = client.get("/ziele").text
    if "extrapoliert zum" not in html:
        return  # kein Ziel mit Stichtag in diesen Daten
    assert "im Schnitt der letzten" in html and "im Tempo der letzten" in html
    assert html.count("extrapoliert zum") % 2 == 0
    assert "/hochrechnung?tempo=juengst#jahr-" in html


def test_the_hochrechnung_page_offers_the_tempo_as_links_and_keeps_it_in_the_flow_form():
    schnitt = client.get("/hochrechnung").text
    assert 'href="/hochrechnung?tempo=juengst"' in schnitt
    assert 'name="tempo"' not in schnitt
    juengst = client.get("/hochrechnung?tempo=juengst").text
    assert 'name="tempo" value="juengst"' in juengst
    assert 'href="/hochrechnung"' in juengst
    # Ein unbekannter Wert gilt als Schnitt.
    assert client.get("/hochrechnung?tempo=x").text == schnitt


def _ziel_im_monatsabschluss() -> dict:
    from finctl.forecast import ziele as zm

    spec = (yaml.safe_load(PFAD.read_text(encoding="utf-8")) or {}) if PFAD.exists() else {}
    ziel = zm.monatsabschluss_ziel(spec)
    if ziel is None:
        pytest.skip("kein Ziel mit im_monatsabschluss in dieser Konfiguration")
    return ziel


def test_the_progress_line_shows_the_same_projection_as_the_goal_on_ziele():
    """Eine Rechnung, zwei Stellen: die Zeile "<Ziel> ... hochgerechnet" auf dem
    Monatsabschluss und das Ziel auf /ziele messen zum selben Stichtag gegen dieselbe Basis.
    Fruehr nahm die Zeile das ganze Endkapital am Jahresende, samt Policen."""
    import re

    ziel = _ziel_im_monatsabschluss()
    html = client.get("/ziele").text
    karte = html.split(f'data-ziel="{ziel["id"]}"', 1)
    assert len(karte) == 2, "das gewaehlte Ziel steht nicht auf /ziele"
    stichtag = re.search(r"extrapoliert zum\s*<a[^>]*>(\d{4})-\d\d-\d\d</a>.*?— (\d+) %",
                         karte[1].split('data-ziel="', 1)[0], re.S)
    assert stichtag, "keine Hochrechnung am Ziel"
    zeile = re.search(re.escape(ziel.get("name") or ziel["id"])
                      + r" heute [\d,]+ %, hochgerechnet (\d{4}) (\d+) %",
                      client.get("/monatsabschluss").text)
    assert zeile, "keine Fortschrittszeile im Monatsabschluss"
    assert zeile.groups() == stichtag.groups()


def test_the_progress_line_needs_the_merkmal(monkeypatch):
    """Ohne `im_monatsabschluss` am Ziel zeigt der Monatsabschluss keine Fortschrittszeile --
    kein Ziel wird stillschweigend gewaehlt."""
    from finctl.forecast import ziele as zm

    ziel = _ziel_im_monatsabschluss()
    html = client.get("/monatsabschluss").text
    assert (ziel.get("name") or ziel["id"]) + " heute" in html
    monkeypatch.setattr(zm, "monatsabschluss_ziel", lambda goals: None)
    assert (ziel.get("name") or ziel["id"]) + " heute" not in client.get("/monatsabschluss").text


def test_monatsabschluss_ziel_takes_the_first_marked_goal():
    from finctl.forecast import ziele as zm

    ziele = {"ziele": [{"id": "a"}, {"id": "b", "im_monatsabschluss": True},
                       {"id": "c", "im_monatsabschluss": True}]}
    assert zm.monatsabschluss_ziel(ziele)["id"] == "b"
    assert zm.monatsabschluss_ziel({"ziele": [{"id": "a"}]}) is None
    assert zm.monatsabschluss_ziel({}) is None
