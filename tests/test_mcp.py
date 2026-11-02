"""Der MCP-Zugang: ein Modell liest wie die Seiten und schreibt nie selbst (ADR 0002).

Das Protokoll laeuft hier ueber eine echte Pipe zu `finctl mcp`, so wie ein Modell es
einbindet. Gesichert wird, was ein Modell nie bekommen und nie tun darf: eine IBAN oder
lange Nummer in einer Antwort, ein Schreibzugriff auf `config/`, ein Rest nach dem
Verwerfen.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from finctl.mcp import werkzeuge
from finctl.pfade import CONFIG_DIR, VORSCHLAEGE_DIR
from finctl.web import vorschlaege as vs
from finctl.web.server import app

DB = Path("data/finance.db")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="kein Hauptbuch")
client = TestClient(app)

IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,4})?\b")


@pytest.fixture(autouse=True)
def _ohne_vorschlaege():
    for v in vs.alle():
        vs.verwerfen(v.id)
    yield
    for v in vs.alle():
        vs.verwerfen(v.id)


def _config() -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(CONFIG_DIR.glob("*.yaml"))}


def _sql(abfrage: str, *args):
    import sqlite3

    c = sqlite3.connect(DB)
    try:
        return c.execute(abfrage, args).fetchone()
    finally:
        c.close()


class Pipe:
    """Ein laufender `finctl mcp`, an dem man Zeile fuer Zeile spricht."""

    def __init__(self, start: str = "from finctl.cli import app; app()"):
        self.p = subprocess.Popen(
            [sys.executable, "-c", start, "mcp"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8")
        self.n = 0

    def senden(self, methode: str, params: dict | None = None) -> dict:
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": methode,
                                       "params": params or {}}) + "\n")
        self.p.stdin.flush()
        return self.lesen()

    def lesen(self) -> dict:
        zeile = self.p.stdout.readline()
        assert zeile, self.p.stderr.read()
        return json.loads(zeile)

    def werkzeug(self, name: str, **args) -> dict:
        return self.senden("tools/call", {"name": name, "arguments": args})["result"]

    def schliessen(self) -> int:
        self.p.stdin.close()
        return self.p.wait(30)


@pytest.fixture
def pipe():
    p = Pipe()
    yield p
    if p.p.poll() is None:
        p.schliessen()


# ------------------------------------------------------------------ Protokoll

def test_handshake_list_and_call_over_a_real_pipe(pipe):
    antwort = pipe.senden("initialize", {"protocolVersion": "2025-06-18"})["result"]
    assert antwort["protocolVersion"] == "2025-06-18"
    assert antwort["serverInfo"]["name"] == "finctl"
    assert "tools" in antwort["capabilities"] and "resources" in antwort["capabilities"]
    # Eine Benachrichtigung bekommt keine Antwort: die naechste Zeile gehoert dem naechsten Aufruf.
    pipe.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    namen = {t["name"] for t in pipe.senden("tools/list")["result"]["tools"]}
    assert {"konten", "buchungen_suchen", "vorschlagen", "klammern", "ziele"} <= namen
    ergebnis = pipe.werkzeug("kategorien")
    assert ergebnis["isError"] is False
    assert ergebnis["content"][0]["text"].startswith("Kategorien")
    assert pipe.senden("ping")["result"] == {}
    assert pipe.schliessen() == 0


def test_the_packaged_app_speaks_the_same_protocol_with_the_argument_mcp():
    """Im Paket gibt es nur den Starter: derselbe Zugang, kein Server, kein Browser."""
    p = Pipe("from finctl.starter import main; main()")
    try:
        assert p.senden("initialize", {})["result"]["serverInfo"]["name"] == "finctl"
        assert p.werkzeug("kategorien")["isError"] is False
    finally:
        p.schliessen()


def test_an_unknown_protocol_version_gets_the_newest_the_server_knows(pipe):
    assert pipe.senden("initialize", {"protocolVersion": "1999-01-01"})["result"][
        "protocolVersion"] == "2025-06-18"


def test_errors_are_answers_not_crashes(pipe):
    assert pipe.senden("gibt/es/nicht")["error"]["code"] == -32601
    assert pipe.senden("tools/call", {"name": "gibt-es-nicht"})["error"]["code"] == -32602
    pipe.p.stdin.write("das ist kein json\n")
    pipe.p.stdin.flush()
    assert pipe.lesen()["error"]["code"] == -32700
    assert pipe.senden("ping")["result"] == {}          # der Strom lebt weiter


def test_the_glossary_is_a_resource(pipe):
    uris = [r["uri"] for r in pipe.senden("resources/list")["result"]["resources"]]
    assert "finctl://glossar" in uris
    text = pipe.senden("resources/read", {"uri": "finctl://glossar"})["result"][
        "contents"][0]["text"]
    assert "**Klammer**" in text and "**Handentscheidung**" in text
    assert "error" in pipe.senden("resources/read", {"uri": "finctl://nein"})


def test_no_stdout_noise_breaks_the_stream(pipe, monkeypatch):
    """Was ein Werkzeug druckt, geht nach stderr und nicht in den Strom."""
    pipe.senden("initialize", {})
    assert pipe.werkzeug("annahmen")["isError"] is False
    assert pipe.senden("ping")["result"] == {}


# ----------------------------------------------------------------------- Lesen

LESEN = [n for n in werkzeuge.WERKZEUGE if n not in ("vorschlagen", "buchungen_suchen")]


def _nummern() -> set[str]:
    nummern: set[str] = set()
    for datei in CONFIG_DIR.glob("*.yaml"):
        if datei.name != "overrides.yaml":
            nummern |= set(re.findall(r"(?<!\d)\d{7,}(?!\d)", datei.read_text(encoding="utf-8")))
    ibans: set[str] = set()
    for datei in CONFIG_DIR.glob("*.yaml"):
        ibans |= set(IBAN.findall(datei.read_text(encoding="utf-8")))
    return {n for n in nummern if not n.endswith("00000")} | ibans


@pytest.mark.parametrize("name", LESEN)
def test_every_reading_tool_answers_without_a_number_or_an_iban(name):
    text = werkzeuge.aufrufen(name, {})
    assert text.strip()
    assert not IBAN.findall(text)
    assert not re.findall(r"\d{9,}", text)
    assert not [n for n in _nummern() if n in text]


def test_a_search_is_limited_and_carries_no_raw_text(pipe):
    pipe.senden("initialize", {})
    kategorie = _sql("SELECT mgmt_category_id FROM splits GROUP BY 1 ORDER BY COUNT(*) DESC")[0]
    text = pipe.werkzeug("buchungen_suchen", kategorie=kategorie, limit=100000)[
        "content"][0]["text"]
    zeilen = [z for z in text.splitlines() if z.startswith("- ")]
    assert 0 < len(zeilen) <= 200
    assert not IBAN.findall(text) and not re.findall(r"\d{9,}", text)


def test_a_search_without_anything_to_search_for_is_refused(pipe):
    pipe.senden("initialize", {})
    r = pipe.werkzeug("buchungen_suchen")
    assert r["isError"] is True and "Suchtext" in r["content"][0]["text"]


def test_a_search_does_not_give_out_the_internal_hash_or_a_number_of_the_statement():
    import sqlite3

    from finctl.rules import vorschlaege as vsr

    c = sqlite3.connect(DB)
    roh = [r[0] for r in c.execute("SELECT raw_text FROM transactions WHERE raw_text IS NOT NULL")]
    hashes = {r[0] for r in c.execute("SELECT dedup_hash FROM transactions LIMIT 500")}
    kategorie = c.execute("SELECT mgmt_category_id FROM splits GROUP BY 1 "
                          "ORDER BY COUNT(*) DESC").fetchone()[0]
    c.close()
    # Jedes Wort eines Auszugstexts, das eine Nummer ist (IBAN, Referenz, Mandat). Ein Betrag
    # steht in der Spalte "Betrag" und ist keine Nummer dieser Art.
    nummern = {w for t in roh for w in t.split() if vsr._nummer(w) and re.search(r"\d{6,}", w)}
    text = werkzeuge.aufrufen("buchungen_suchen", {"kategorie": kategorie})
    assert not [h for h in hashes if h in text]
    assert not [n for n in nummern if n in text]


def _alle_notizen(wert) -> set[str]:
    gefunden: set[str] = set()
    if isinstance(wert, dict):
        for k, v in wert.items():
            if k in ("notiz", "note") and isinstance(v, str) and len(v) >= 25:
                gefunden.add(" ".join(v.split()))
            gefunden |= _alle_notizen(v)
    elif isinstance(wert, list):
        for v in wert:
            gefunden |= _alle_notizen(v)
    return gefunden


def test_no_tool_gives_out_a_note():
    """Notizen tragen alles Persoenliche; ob ein Modell sie lesen darf, ist nicht entschieden."""
    import yaml

    notizen: set[str] = set()
    for datei in CONFIG_DIR.glob("*.yaml"):
        if datei.name != "overrides.yaml":
            notizen |= _alle_notizen(yaml.safe_load(datei.read_text(encoding="utf-8")))
    for name in LESEN:
        text = " ".join(werkzeuge.aufrufen(name, {}).split())
        assert not [n for n in notizen if n[:25] in text], name


# ------------------------------------------------------------------ Vorschlagen

def _felder() -> dict[str, dict]:
    """Je Art ein gueltiger Vorschlag, aus dem Haushalt gelesen und nicht erfunden."""
    kategorie = _sql("SELECT id FROM mgmt_categories WHERE active = 1 AND parent_id IS NOT NULL "
                     "ORDER BY id")[0]
    konto = _sql("SELECT id FROM accounts WHERE active = 1 ORDER BY id")[0]
    return {
        "regel": {"name": "Probe-Regel", "text": ["zzzz probe suchtext"], "mgmt": kategorie},
        "planzeile": {"szenario": "Probe-Klammer", "label": "Probe-Zeile", "start": "2031-01-01",
                      "kategorie": kategorie, "amount_cents": -12300},
        "kredit": {"id": "probe-kredit", "name": "Probe-Kredit", "lender": "Probebank",
                   "servicing_account_id": konto, "start": "2031-01-01", "ende": "2036-01-01",
                   "opening_balance_cents": 1_000_000, "annuity_cents": 20_000,
                   "annual_rate_pct": 4.0},
        "notiz": {"ort": "konto", "id": konto, "notiz": "Probe: warum das Konto so ist."},
    }


@pytest.mark.parametrize("art", ["regel", "planzeile", "kredit", "notiz"])
def test_proposing_writes_a_file_in_the_proposals_folder_and_nothing_in_config(pipe, art):
    pipe.senden("initialize", {})
    vorher = _config()
    ergebnis = pipe.werkzeug("vorschlagen", art=art, felder=_felder()[art], warum="Probe")
    assert ergebnis["isError"] is False, ergebnis
    assert "noch keine Entscheidung" in ergebnis["content"][0]["text"]
    assert _config() == vorher                       # byteweise gleich
    dateien = list(VORSCHLAEGE_DIR.glob("*.json"))
    assert len(dateien) == 1
    abgelegt = json.loads(dateien[0].read_text(encoding="utf-8"))
    assert abgelegt["art"] == art and abgelegt["felder"] == _felder()[art]
    assert abgelegt["warum"] == "Probe"
    assert vs.anzahl() == 1


@pytest.mark.parametrize("art,fehler,route", [
    ("regel", {"mgmt": "gibt/es-nicht"}, "/api/regeln"),
    ("planzeile", {"kategorie": ""}, "/api/szenario-zeile"),
    ("planzeile", {"start": ""}, "/api/szenario-zeile"),
    ("planzeile", {"frequenz": "sonntags"}, "/api/szenario-zeile"),
    ("kredit", {"annuity_cents": 1}, "/api/kredit-neu"),
    ("kredit", {"servicing_account_id": None}, "/api/kredit-neu"),
])
def test_an_invalid_proposal_comes_back_with_the_message_of_the_route(pipe, art, fehler, route):
    """Dieselbe Pruefung wie die Route: dieselbe Meldung, und nichts wird abgelegt."""
    pipe.senden("initialize", {})
    felder = {**_felder()[art], **fehler}
    r = pipe.werkzeug("vorschlagen", art=art, felder=felder)
    assert r["isError"] is True
    meldung = r["content"][0]["text"]
    body = {**felder, "neu": True} if art == "regel" else felder
    vorher = _config()
    antwort = client.post(route, json=body)
    assert antwort.status_code == 400
    assert meldung == antwort.json()["error"]
    assert _config() == vorher
    assert vs.anzahl() == 0


def test_unknown_art_unknown_fields_and_empty_fields_are_refused(pipe):
    pipe.senden("initialize", {})
    for argumente in ({"art": "erfunden", "felder": {"a": 1}},
                      {"art": "regel", "felder": {"name": "x", "gefaehrlich": 1}},
                      {"art": "regel", "felder": {}},
                      {"art": "notiz", "felder": {"ort": "ziel", "id": "gibt-es-nicht",
                                                  "notiz": "x"}},
                      {"art": "notiz", "felder": {"ort": "buchung", "id": "1", "notiz": "x"}}):
        assert pipe.werkzeug("vorschlagen", **argumente)["isError"] is True, argumente
    assert vs.anzahl() == 0


def test_an_amount_must_be_cents_as_a_whole_number(pipe):
    pipe.senden("initialize", {})
    felder = {**_felder()["planzeile"], "amount_cents": "-123,00"}
    assert pipe.werkzeug("vorschlagen", art="planzeile", felder=felder)["isError"] is True


def test_a_note_that_already_stands_there_is_no_proposal(pipe):
    pipe.senden("initialize", {})
    felder = _felder()["notiz"]
    vorher = _config_bytes()
    client.post(f"/api/konto/{felder['id']}", json={"note": felder["notiz"]})
    try:
        assert pipe.werkzeug("vorschlagen", art="notiz", felder=felder)["isError"] is True
    finally:
        _zuruecksetzen(vorher)


def test_the_reason_is_cut_and_the_proposal_id_cannot_leave_the_folder():
    v = vs.ablegen("regel", _felder()["regel"], "x" * 5000, _verbindung())
    assert len(v.warum) == vs.WARUM_MAX
    for boese in ("../config/rules", "..%2fx", "x/../../y", ""):
        with pytest.raises(ValueError):
            vs.verwerfen(boese)
        assert client.post(f"/api/vorschlaege/{boese}/verwerfen").status_code in (404, 405)


def _verbindung():
    from finctl.ledger.db import connect

    return connect()


# ---------------------------------------------------------- Uebernehmen, Verwerfen

def _senden(vorschlag_id: str) -> dict:
    """Was die Seite an die Route schickt: aus ihrem eigenen Quelltext gelesen."""
    html = client.get("/vorschlaege").text
    roh = re.search(r'<script type="application/json" id="vs-senden">(.*?)</script>', html, re.S)
    return json.loads(roh.group(1).replace("\\u0026", "&").replace("\\u003c", "<")
                      .replace("\\u003e", ">").replace("\\u0027", "'"))[vorschlag_id]


def _config_bytes() -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(CONFIG_DIR.glob("*.yaml"))}


def _zuruecksetzen(vorher: dict[str, bytes]) -> None:
    for p in CONFIG_DIR.glob("*.yaml"):
        if p.name not in vorher:
            p.unlink()
    for name, inhalt in vorher.items():
        (CONFIG_DIR / name).write_bytes(inhalt)


@pytest.mark.parametrize("art", ["regel", "planzeile", "kredit", "notiz"])
def test_taking_a_proposal_gives_the_same_files_as_the_same_entry_over_the_page(art):
    felder = _felder()[art]
    vorher = _config_bytes()

    # Der Weg des Vorschlags: wie die Seite ihn schickt.
    v = vs.ablegen(art, felder, "Probe", _verbindung())
    senden = _senden(v.id)
    assert client.post(senden["route"], json=senden["body"]).status_code == 200
    nach_vorschlag = _config_bytes()
    assert nach_vorschlag != vorher, "der Vorschlag aenderte nichts"
    _zuruecksetzen(vorher)

    # Der Weg der Seite: derselbe Eintrag, wie das Formular ihn schickt.
    if art == "notiz":
        route, body = f"/api/konto/{felder['id']}", {"note": felder["notiz"]}
    else:
        route, body = {"regel": ("/api/regeln", {**felder, "neu": True}),
                       "planzeile": ("/api/szenario-zeile", felder),
                       "kredit": ("/api/kredit-neu", felder)}[art]
    assert senden["route"] == route
    assert client.post(route, json=body).status_code == 200
    assert _config_bytes() == nach_vorschlag
    _zuruecksetzen(vorher)


def test_taking_a_goal_note_equals_the_page():
    import yaml

    pfad = CONFIG_DIR / "goals.yaml"
    if not pfad.exists():
        pytest.skip("keine Ziele")
    ziele = (yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}).get("ziele") or []
    ziel = next((g["id"] for g in ziele if g.get("id") != "rentenluecke"), None)
    if ziel is None:
        pytest.skip("keine Ziele")
    felder = {"ort": "ziel", "id": str(ziel), "notiz": "Probe: warum das Ziel so ist."}
    vorher = _config_bytes()
    v = vs.ablegen("notiz", felder, "", _verbindung())
    senden = _senden(v.id)
    assert senden["route"] == "/api/ziel"
    assert client.post(senden["route"], json=senden["body"]).status_code == 200
    danach = _config_bytes()
    _zuruecksetzen(vorher)
    assert client.post("/api/ziel", json={"id": str(ziel), "notiz": felder["notiz"]}
                       ).status_code == 200
    assert _config_bytes() == danach
    _zuruecksetzen(vorher)


def test_the_route_and_body_come_from_the_check_not_from_the_file():
    """Eine von Hand veraenderte Datei kann die Seite nicht an eine andere Route schicken."""
    v = vs.ablegen("notiz", _felder()["notiz"], "", _verbindung())
    datei = VORSCHLAEGE_DIR / f"{v.id}.json"
    roh = json.loads(datei.read_text(encoding="utf-8"))
    roh["route"] = "/api/regeln/x/entfernen"          # wird nie gelesen
    datei.write_text(json.dumps(roh), encoding="utf-8")
    senden = _senden(v.id)
    assert senden["route"] == f"/api/konto/{_felder()['notiz']['id']}"
    assert "entfernen" not in json.dumps(senden)


def test_discarding_leaves_nothing_behind():
    vorher = _config()
    v = vs.ablegen("regel", _felder()["regel"], "Probe", _verbindung())
    assert vs.anzahl() == 1
    r = client.post(f"/api/vorschlaege/{v.id}/verwerfen")
    assert r.status_code == 200 and r.json()["offen"] == 0
    assert not list(VORSCHLAEGE_DIR.iterdir())              # auch keine halbe Datei
    assert _config() == vorher
    assert vs.alle() == []
    # Ein zweites Mal ist kein Fehler: es gibt nichts mehr, und das ist das Ziel.
    assert client.post(f"/api/vorschlaege/{v.id}/verwerfen").json()["gab_es"] is False


def test_the_navigation_shows_the_number_of_open_proposals():
    assert "<span class=\"zahl\">" not in _navigation(client.get("/vorschlaege").text)
    vs.ablegen("regel", _felder()["regel"], "", _verbindung())
    vs.ablegen("notiz", _felder()["notiz"], "", _verbindung())
    nav = _navigation(client.get("/monatsabschluss").text)
    assert re.search(r'href="/vorschlaege">Vorschläge\s*<span class="zahl">2</span>', nav)


def _navigation(html: str) -> str:
    m = re.search(r'href="/vorschlaege">Vorschläge.*?</a>', html, re.S)
    assert m
    return m.group(0)


def test_the_page_shows_what_would_change_and_says_when_a_proposal_no_longer_fits():
    ok = vs.ablegen("regel", _felder()["regel"], "Weil Probe.", _verbindung())
    seite = client.get("/vorschlaege").text
    assert "Weil Probe." in seite and "Probe-Regel" in seite and "Übernehmen" in seite
    # Die Kategorie verschwindet nach der Ablage: die Seite prueft neu und sagt es.
    datei = VORSCHLAEGE_DIR / f"{ok.id}.json"
    roh = json.loads(datei.read_text(encoding="utf-8"))
    roh["felder"]["mgmt"] = "gibt/es-nicht"
    datei.write_text(json.dumps(roh), encoding="utf-8")
    seite = client.get("/vorschlaege").text
    assert "Geht nicht mehr" in seite and "unbekannte Kategorie" in seite
    assert "vsUebernehmen(this, '" + ok.id not in seite


def test_a_broken_file_in_the_folder_does_not_break_the_page():
    VORSCHLAEGE_DIR.mkdir(parents=True, exist_ok=True)
    (VORSCHLAEGE_DIR / "20260101-000000-abcdef.json").write_text("{kaputt", encoding="utf-8")
    assert client.get("/vorschlaege").status_code == 200
    assert vs.anzahl() == 0
