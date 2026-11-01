"""Der Abschnitt "Wirkung auf deine Ziele" auf /monatsabschluss (Schritt 3.6).

Gerechnet ist alles in `forecast/wirkung.py` und dort getestet; hier steht, was die Seite
daraus zeigt: die Zahlen des Moduls, die Kategorien der Tempo-Ursachen, die Hinweise zum
Monat, den Satz statt der Zahlen, wenn Staende von damals fehlen. Die Seite liest keine
Namen und Betraege aus dem Test: Der Haushalt kommt aus `config/` der Testkopie, und der
Verlauf wird aus seinen heutigen Staenden gebaut.
"""

from __future__ import annotations

import dataclasses
import html as _html
from datetime import date, timedelta

import pytest
import yaml
from fastapi.testclient import TestClient

from finctl import bestaende as best
from finctl import dateien, module
from finctl import monatsabschluss as ma
from finctl.forecast import abgleich as ag
from finctl.pfade import CONFIG_DIR
from finctl.web.basis import conn, euro
from finctl.web.server import app

client = TestClient(app)
DATEI = CONFIG_DIR / "balances.yaml"


def _stichtage() -> tuple[date, date]:
    c = conn()
    try:
        stichtag = ag.letzter_vollstaendiger_monat(c)
    finally:
        c.close()
    return stichtag, stichtag.replace(day=1) - timedelta(days=1)


def _stand_von_damals(abweichung: int = 0) -> dict:
    """Ein Verlauf mit dem Stand jeder getippten Position zum Stichtag davor: der heutige,
    um `abweichung` verschoben."""
    _, davor = _stichtage()
    c = conn()
    try:
        jetzt = best.zusammenfuehren(c, best.lesen())
    finally:
        c.close()
    out: dict = {}
    for z in jetzt["balances"]:
        if z.get("aus_auszug") or z.get("cents") is None:
            continue
        periode = best.periode(z.get("kind"), ag.folgetag(davor))
        out.setdefault(best.schluessel(z), {})[periode] = {
            "cents": int(z["cents"]) + abweichung, "as_of": davor.isoformat()}
    return out


@pytest.fixture
def verlauf():
    """Setzt `verlauf` in der Testkopie von balances.yaml; danach wieder zurueck."""
    vorher = DATEI.read_bytes()

    def setzen(eintraege: dict | None) -> None:
        spec = dict(yaml.safe_load(vorher.decode("utf-8")) or {})
        spec.pop("verlauf", None)
        if eintraege is not None:
            spec["verlauf"] = eintraege
        DATEI.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")

    yield setzen
    DATEI.write_bytes(vorher)


def _abschnitt(heute: date | None = None):
    c = conn()
    try:
        return ma.wirkung(c, heute or date.today())
    finally:
        c.close()


def test_without_a_history_the_section_says_what_is_missing(verlauf):
    verlauf(None)
    c = conn()
    try:
        fehlt = best.zum(c, _stichtage()[1], best.lesen())["fehlt"]
    finally:
        c.close()
    if not fehlt:
        pytest.skip("keine getippte Position: es fehlt nichts")
    seite = client.get("/monatsabschluss").text
    assert 'id="wirkung"' in seite
    assert "kein Stand zum Stichtag" in seite
    assert all(_html.escape(name) in seite for name in fehlt)
    assert '<table class="wirkung"' not in seite
    w = _abschnitt()
    assert w.satz and not w.hinweis_zeilen and w.hinweise is None


def test_with_a_history_the_page_shows_the_numbers_of_the_module(verlauf):
    verlauf(_stand_von_damals(abweichung=-1_000_00))
    seite = client.get("/monatsabschluss").text
    w = _abschnitt()
    assert w.satz is None and w.zeilen
    assert '<table class="wirkung"' in seite
    assert "kein Stand zum Stichtag" not in seite
    stichtag, davor = _stichtage()
    assert f"Stichtag {stichtag} gegen {davor}, unter den heutigen Annahmen" in seite
    for z in w.zeilen:
        assert _html.escape(z.schnitt.ziel.name) in seite
        for zw in (z.schnitt, z.juengst):
            if zw.aenderung is not None:
                assert euro(zw.aenderung) in seite
    assert w.tempo["schnitt"] in seite and w.tempo["juengst"] in seite


def test_a_goal_the_monthly_model_measures_says_so_and_points_to_konten(verlauf):
    verlauf(_stand_von_damals())
    w = _abschnitt()
    monat = [z for z in w.zeilen if z.schnitt.im_monatsmodell]
    if not monat:
        pytest.skip("kein Ziel mit Stichtag im Horizont von /konten")
    assert all(z.juengst.im_monatsmodell for z in monat)
    for z in monat:
        for zw in (z.schnitt, z.juengst):
            assert (zw.vorher, zw.heute, zw.ursachen) == (None, None, [])
    seite = client.get("/monatsabschluss").text
    assert seite.count("Das Monatsmodell misst dieses Ziel") == len(monat)
    assert 'class="plain" href="/konten"' in seite
    for z in monat:
        assert _html.escape(z.schnitt.ziel.name) in seite


def test_a_tempo_cause_lists_its_categories_with_the_months_and_their_bookings(verlauf):
    verlauf(_stand_von_damals())
    w = _abschnitt()
    tempo = [(zw, u) for z in w.zeilen for zw in (z.schnitt, z.juengst) for u in zw.ursachen
             if u.label.startswith("Tempo: ")]
    if not tempo:
        pytest.skip("im Testhaushalt bewegt kein Tempo ein Ziel")
    seite = client.get("/monatsabschluss").text
    assert "Jahreswert vorher" in seite and "aus dem Fenster gefallen" in seite
    zw, u = tempo[0]
    k = zw.kategorien[u.verweis][0]
    assert _html.escape(k.kategorie or "(ohne Kategorie)") in seite
    for m in (*k.heraus, *k.dazu):
        assert f"{m.monat:%Y-%m}" in seite
    assert euro(k.vorher) in seite and euro(k.nachher) in seite
    # Die Seite deutet nichts: kein Wort darueber, ob sich ein Betrag oder ein Tag geaendert hat.
    assert "gerutscht" not in seite and "Zahlungstag" not in seite


def test_the_hints_for_the_month_stand_apart_from_the_cause(verlauf):
    verlauf(_stand_von_damals(abweichung=-1_000_00))
    seite = client.get("/monatsabschluss").text
    w = _abschnitt()
    assert 'id="wirkung-monat"' in seite
    assert w.hinweise.monat == _stichtage()[0].replace(day=1)
    assert [h.label for h in w.hinweis_zeilen]
    assert "keine Teile der Wirkung" in seite
    # Die Summe der Zeilen ist die Sparrate des Treffer-Checks.
    assert w.hinweis_summe.soll == w.hinweise.treffer.sparrate_soll
    assert w.hinweis_summe.ist == w.hinweise.treffer.sparrate_ist
    if w.hinweise.kurs is not None:
        k = w.hinweise.kurs
        assert euro(k.kursbewegung) in seite
        assert k.kursbewegung == k.aenderung + k.buchungen_cents
    assert ("rechnet beide selbst" in seite) == w.hinweise.gerechnet_gebucht


def test_the_page_names_the_stichtag_when_statements_are_still_missing(verlauf, monkeypatch):
    verlauf(_stand_von_damals())
    echt = ma.wirkung

    def verspaetet(c, heute):
        w = echt(c, heute)
        return dataclasses.replace(
            w, erwartet=ag.folgetag(ag.folgetag(w.stichtag)) - timedelta(days=1))

    # Heute ist der Tag nach dem Stichtag der Daten, nicht das Datum des Laufs:
    # am Ersten eines Monats erwartet der Abschluss sonst schon den naechsten.
    stichtag, _ = _stichtage()
    assert not _abschnitt(ag.folgetag(stichtag)).abweichend
    monkeypatch.setattr(ma, "wirkung", verspaetet)
    seite = client.get("/monatsabschluss").text
    assert "die Auszüge reichen erst bis" in seite


def test_the_stichtag_the_closing_expects_is_the_end_of_the_month_before(verlauf):
    verlauf(_stand_von_damals())
    stichtag, _ = _stichtage()
    assert _abschnitt(ag.folgetag(stichtag)).erwartet == stichtag
    assert _abschnitt(ag.folgetag(ag.folgetag(stichtag))).abweichend


def test_without_the_goals_module_there_is_no_section(verlauf):
    verlauf(_stand_von_damals())
    datei = module.CONFIG_DIR / module.DATEI
    vorher = datei.read_text(encoding="utf-8") if datei.exists() else None
    dateien.zuordnung_schreiben(
        datei, module.SCHLUESSEL, {m.id: m.id != "ziele" for m in module.MODULE
                                   if not m.basis}, "")
    try:
        assert _abschnitt() is None
        assert 'id="wirkung"' not in client.get("/monatsabschluss").text
    finally:
        if vorher is None:
            datei.unlink()
        else:
            datei.write_text(vorher, encoding="utf-8")
