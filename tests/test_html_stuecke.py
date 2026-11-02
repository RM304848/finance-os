"""Stuecke vom Server: die Seite und die Schnittstelle zeigen dasselbe.

Seit Schritt 6a setzen die Skripte von /vertraege und /planung kein HTML mehr
zusammen (docs/design_conventions.yaml, html-vom-server). Die Seite bindet eine
Teilvorlage beim Laden ein, die Schnittstelle liefert dasselbe Stueck als
`html`. Hier wird verglichen, ob es dasselbe ist -- Zeile fuer Zeile, mit denselben
Klassen und Daten-Attributen.
"""

from __future__ import annotations

import json
import re
import sqlite3
from html.parser import HTMLParser
from pathlib import Path

import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from finctl.web.server import app

DB = Path("data/finance.db")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="no ledger present")
client = TestClient(app)

_LEER = {"area", "base", "br", "col", "hr", "img", "input", "link", "meta", "source", "wbr"}


class _Kanon(HTMLParser):
    """HTML als Liste von Ereignissen: Tags mit sortierten Attributen, Text ohne Leerraum-Streit.

    Ein Stueck der Seite steht eingerueckt in anderem Leerraum als dasselbe
    Stueck in der Antwort; verglichen wird, was ein Browser daraus macht.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ereignisse: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = " ".join(f'{k}="{v}"' for k, v in sorted(attrs))
        self.ereignisse.append(f"<{tag} {a}>" if a else f"<{tag}>")

    def handle_endtag(self, tag):
        if tag not in _LEER:
            self.ereignisse.append(f"</{tag}>")

    def handle_data(self, data):
        text = " ".join(data.split())
        if text:
            self.ereignisse.append(text)


def _kanon(html: str) -> list[str]:
    p = _Kanon()
    p.feed(html)
    p.close()
    return p.ereignisse


def _innen(seite: str, kennung: str) -> list[str]:
    """Die Ereignisse im Element mit dieser id, ohne das Element selbst."""
    alle = _kanon(seite)
    start = next((i for i, e in enumerate(alle)
                  if e.startswith("<") and f'id="{kennung}"' in e), None)
    assert start is not None, f"kein Element {kennung} auf der Seite"
    tag = alle[start][1:].split()[0].rstrip(">")
    tiefe, ende = 0, None
    for i in range(start, len(alle)):
        if alle[i].startswith(f"<{tag}") and alle[i][len(tag) + 1] in " >":
            tiefe += 1
        elif alle[i] == f"</{tag}>":
            tiefe -= 1
            if tiefe == 0:
                ende = i
                break
    assert ende is not None
    return alle[start + 1:ende]


def _skript_wert(seite: str, name: str):
    treffer = re.search(rf"const {name} = (.*);\n", seite)
    assert treffer, f"{name} steht nicht im Skript"
    return json.loads(treffer.group(1))


# ---------------------------------------------------------------- Planung

def _planzeile_mit_vorschlaegen():
    """Eine Planzeile der Seite, die Vorschlaege zeigt, samt ihrer Kategorie."""
    seite = client.get("/planung").text
    for treffer in re.finditer(r'<table class="detail" id="bt-([^"]+)">(.*?)</table>', seite, re.S):
        zeilen = re.findall(r"<tr>.*?</tr>", treffer.group(2), re.S)
        kategorie = re.search(
            rf'<select id="bk-{re.escape(treffer.group(1))}".*?'
            r'<option value="([^"]*)"\s+selected', seite, re.S)
        if zeilen and kategorie and kategorie.group(1):
            return treffer.group(1), zeilen, kategorie.group(1)
    pytest.skip("keine Planzeile mit Vorschlaegen")


def test_planung_vorschlaege_der_suche_sind_die_zeilen_der_seite():
    zid, zeilen, kategorie = _planzeile_mit_vorschlaegen()
    antwort = client.get("/api/buchungen/suche", params={
        "kategorie": kategorie, "zid": zid, "limit": 200}).json()
    if len(antwort["rows"]) >= 200:
        pytest.skip("zu viele Buchungen in der Kategorie, die Seite zeigt nur das Messfenster")
    api = {z: _kanon(z) for z in re.findall(r"<tr>.*?</tr>", antwort["html"], re.S)}
    gesucht = [_kanon(z) for z in zeilen]
    # Jede Zeile der Seite steht in der Antwort, gleich bis auf Leerraum.
    assert all(z in api.values() for z in gesucht), \
        "die Antwort zeigt eine Zeile anders als die Seite"
    assert antwort["html"].count("<tr>") == len(antwort["rows"])


def test_planung_suche_laesst_zugeordnetes_weg_und_sagt_es():
    zid, _, kategorie = _planzeile_mit_vorschlaegen()
    alle = client.get("/api/buchungen/suche", params={
        "kategorie": kategorie, "zid": zid}).json()
    assert alle["rows"], "die Kategorie hat Buchungen"
    erste = alle["rows"][0]["dedup_hash"]
    ohne = client.get("/api/buchungen/suche", params={
        "kategorie": kategorie, "zid": zid, "ausser": [erste]}).json()
    assert erste not in {b["dedup_hash"] for b in ohne["rows"]}
    assert f"buchungZu('{zid}', '{erste}')" not in ohne["html"]
    assert "(1 bereits zugeordnet, siehe oben)" in ohne["kopf"]
    assert ohne["alle"] is bool(ohne["rows"])


def test_planung_suche_ohne_angabe_meldet_es_im_stueck():
    antwort = client.get("/api/buchungen/suche", params={"zid": "x-0"}).json()
    assert antwort["kopf"] is None and antwort["rows"] == []
    assert "Text oder Kategorie angeben." in antwort["html"]
    assert 'id="bt-x-0"' in antwort["html"]


def test_planung_suche_ohne_zeile_bleibt_wie_sie_war():
    """Wer kein `zid` nennt, bekommt weiter nur die Zeilen der Datenbank."""
    antwort = client.get("/api/buchungen/suche", params={"q": "x"}).json()
    assert antwort == {"rows": []}


def test_planung_suchtreffer_tragen_die_vorzeichenfarbe_der_seite():
    zid, zeilen, kategorie = _planzeile_mit_vorschlaegen()
    assert any('class="num neg"' in z or 'class="num pos"' in z for z in zeilen)
    antwort = client.get("/api/buchungen/suche", params={"kategorie": kategorie, "zid": zid}).json()
    assert 'class="num neg"' in antwort["html"] or 'class="num pos"' in antwort["html"]


# ---------------------------------------------------------------- Vertraege

ANSICHTEN = ["abos", "versicherungen"]


def _vertraege(ansicht: str):
    seite = client.get("/vertraege", params={"ansicht": ansicht}).text
    abos = _skript_wert(seite, "ABOS")
    if not abos:
        pytest.skip(f"{ansicht}: kein Vertrag")
    art = _skript_wert(seite, "ART")
    return seite, abos, _skript_wert(seite, "ENTWUERFE"), art


@pytest.mark.parametrize("ansicht", ANSICHTEN)
def test_vertragseditor_der_antwort_ist_der_editor_der_seite(ansicht):
    seite, abos, entwuerfe, art = _vertraege(ansicht)
    for abo in abos:
        antwort = client.post(f"/api/abos/editor?art={art}", json={
            "st": entwuerfe[abo["id"]], "info": abo, "neu": False}).json()
        assert _kanon(antwort["html"]) == _innen(seite, f"editor-{abo['id']}"), abo["id"]


@pytest.mark.parametrize("ansicht", ANSICHTEN)
def test_vertragseditor_zeigt_den_entwurf_und_nicht_den_stand_der_datei(ansicht):
    """Der Browser schickt, was getippt wurde; der Server zeichnet genau das."""
    _, abos, entwuerfe, art = _vertraege(ansicht)
    abo = abos[0]
    st = json.loads(json.dumps(entwuerfe[abo["id"]]))
    st["name"] = "Entwurf mit <Tags> & Co"
    st["betrag_text"] = "12,34"
    st["geteilt"]["besetzung"].append(
        {"name": "", "anteil_cents": 0, "aliase": [], "zahlungen": []})
    html = client.post(f"/api/abos/editor?art={art}", json={
        "st": st, "info": abo, "neu": False}).json()["html"]
    assert 'value="Entwurf mit &lt;Tags&gt; &amp; Co"' in html
    assert 'data-f="betrag" value="12,34"' in html
    assert f'data-b="{len(st["geteilt"]["besetzung"]) - 1}" data-k="name"' in html
    assert 'data-a="entfernen"' in html and 'data-f="id"' not in html


def test_vertragseditor_eines_neuen_vertrags_traegt_kennung_und_anlegen():
    antwort = client.post("/api/abos/neu", params={"art": "abo"}).json()
    assert 'id="neu-editor"' in antwort["html"] and "Neues Abo" in antwort["html"]
    assert 'data-f="id"' in antwort["html"] and 'data-a="speichern">Anlegen<' in antwort["html"]
    assert antwort["st"]["buchungen"] == [] and antwort["st"]["takt"] == 12
    neu = client.post("/api/abos/neu", params={"art": "versicherung"}).json()["html"]
    assert "Neue Versicherung" in neu and 'data-f="vorrat_bis"' not in neu
    assert client.post("/api/abos/neu", params={"art": "gibt-es-nicht"}).status_code == 400


def _suchwort() -> str:
    """Ein Wort aus einer echten Abbuchung, damit die Suche etwas findet."""
    db = sqlite3.connect(DB)
    try:
        for (text,) in db.execute(
                "SELECT raw_text FROM transactions WHERE amount_cents < 0 ORDER BY id LIMIT 50"):
            for wort in re.findall(r"[A-Za-zÄÖÜäöüß]{4,}", text or ""):
                return wort
    finally:
        db.close()
    pytest.skip("keine Abbuchung mit einem Wort")


def test_vertrag_suchtreffer_kommen_als_liste_und_ohne_zugeordnetes():
    wort = _suchwort()
    alle = client.get("/api/abos/buchungen", params={"q": wort}).json()
    assert alle["rows"], "die Suche findet die Abbuchung, aus der das Wort stammt"
    assert alle["html"].count('data-a="treffer"') == len(alle["rows"])
    assert [int(i) for i in re.findall(r'data-a="treffer" data-i="(\d+)"', alle["html"])] \
        == list(range(len(alle["rows"])))
    hashes = [b["dedup_hash"] for b in alle["rows"]]
    leer = client.get("/api/abos/buchungen", params={"q": wort, "ausser": hashes}).json()
    assert leer["rows"] == [] and "Keine Abbuchung gefunden." in leer["html"]
    kurz = client.get("/api/abos/buchungen", params={"q": "x"}).json()
    assert kurz == {"rows": []}
