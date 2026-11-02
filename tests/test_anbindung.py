"""Die Anbindung an ein Modell: ausgeschaltet, gezeigt, jedes Mal bestaetigt (ADR 0002).

Der Weg ist neu und der einzige, auf dem Text die App verlaesst. Deshalb pruefen die
Tests, was ihn gefaehrlich machte: dass etwas hinausgeht, ohne dass jemand es sah, dass
etwas anderes hinausgeht als das Gezeigte, dass der Schluessel irgendwo landet und dass
ein Fehler ihn oder die Antwort des fremden Servers ausplaudert.

Der "fremde" Server ist ein erfundener auf 127.0.0.1 im Test selbst. Ausserhalb dieses
Rechners wird nie verbunden.
"""

from __future__ import annotations

import html
import logging
import os
import re
import socket
from pathlib import Path

import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient
from modellattrappe import ANTWORT, SCHLUESSEL
from modellattrappe import Server as _Server

from finctl.pfade import CONFIG_DIR
from finctl.web import anbindung as an
from finctl.web.server import app

DB = Path("data/finance.db")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="kein Hauptbuch")
client = TestClient(app)

VORLAGE = {"art": "monat", "monat": "2026-03"}


# ------------------------------------------------------------ erfundener Server

@pytest.fixture
def server():
    s = _Server()
    yield s
    s.schliessen()


@pytest.fixture(autouse=True)
def _eigene_dateien(tmp_path, monkeypatch):
    """Eintrag und Schluessel im Wegwerfordner; eine liegengebliebene Freigabe gilt nicht."""
    monkeypatch.setattr(an, "PFAD", tmp_path / "anbindung.yaml")
    monkeypatch.setattr(an, "SCHLUESSEL_PATH", tmp_path / "anbindung.schluessel")
    an._FREIGABEN.clear()
    yield
    an._FREIGABEN.clear()


@pytest.fixture
def netz_gesperrt(monkeypatch):
    """Jeder Versuch, eine Verbindung aufzubauen oder einen Namen aufzuloesen, faellt auf."""
    versuche: list[str] = []

    def sperre(name):
        def _(*args, **kwargs):
            versuche.append(name)
            raise AssertionError(f"Netzzugriff versucht: {name}")
        return _

    monkeypatch.setattr(socket.socket, "connect", sperre("connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", sperre("connect_ex"))
    monkeypatch.setattr(socket, "create_connection", sperre("create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", sperre("getaddrinfo"))
    return versuche


def _eintragen(adresse: str, schluessel: str = SCHLUESSEL, modell: str = "test-modell"):
    r = client.post("/api/vorlagen/anbindung",
                    json={"adresse": adresse, "modell": modell, "schluessel": schluessel})
    assert r.status_code == 200, r.text
    return r


def _hinaus(**vorlage) -> tuple[str, str, str]:
    """Der Text, den die Seite zeigt, sein Stichwort und das ganze Stueck."""
    r = client.post("/api/vorlagen/hinaus", json=vorlage or VORLAGE)
    assert r.status_code == 200, r.text
    stueck = r.json()["html"]
    text = html.unescape(re.search(r'<textarea[^>]*id="vl-hinaus-text"[^>]*>(.*?)</textarea>',
                                   stueck, re.S).group(1))
    return text, re.search(r'data-stichwort="([^"]+)"', stueck).group(1), stueck


# ----------------------------------------------------------- ausgeschaltet

def test_without_a_connection_there_is_no_send_button_and_no_connection_attempt(netz_gesperrt):
    for art in ("monat", "prognose"):
        seite = client.get(f"/vorlagen?art={art}").text
        assert "Die App sendet nichts" in seite
        assert "vlHinaus" not in seite and "vlAbsenden" not in seite
        assert "Senden …" not in seite
    assert client.get("/vorlagen/anbindung").status_code == 200
    # Ohne Eintrag zeigt die Route nichts und sendet nichts, auch nicht mit erfundenem Stichwort.
    assert client.post("/api/vorlagen/hinaus", json=VORLAGE).status_code == 409
    assert client.post("/api/vorlagen/senden", json={"stichwort": "erfunden"}).status_code == 409
    assert an.laden() is None
    assert netz_gesperrt == []


def test_entering_a_connection_does_not_connect(netz_gesperrt):
    _eintragen("https://api.example.test/v1")
    assert client.get("/vorlagen?art=monat").status_code == 200
    _text, _stichwort, stueck = _hinaus(**VORLAGE)        # zeigen ist nicht senden
    assert netz_gesperrt == []
    assert "api.example.test" in stueck


# --------------------------------------------------------------- senden

def test_exactly_the_shown_text_goes_out_and_the_answer_becomes_a_proposal(server):
    _eintragen(server.adresse)
    seite = client.get("/vorlagen?art=monat").text
    assert "vlHinaus" in seite
    text, stichwort, stueck = _hinaus(**VORLAGE)
    # Das Gezeigte ist die Vorlage, die auch zum Kopieren dasteht.
    assert text == client.post("/api/vorlagen/vorlage", json=VORLAGE).json()["text"]
    assert "Der Text bleibt auf diesem Rechner" in stueck
    assert "Das verlässt den Rechner" not in stueck
    assert server.anfragen == []                          # gezeigt, nichts gesendet

    # Was der Browser sonst noch mitschickt, geht nicht hinaus.
    r = client.post("/api/vorlagen/senden", json={"stichwort": stichwort, "text": "FREMDER TEXT"})
    assert r.status_code == 200, r.text
    [anfrage] = server.anfragen
    assert anfrage["pfad"] == "/v1/chat/completions"
    assert anfrage["koerper"]["model"] == "test-modell"
    assert anfrage["koerper"]["messages"] == [{"role": "user", "content": text}]
    assert anfrage["kopf"]["Authorization"] == f"Bearer {SCHLUESSEL}"
    antwort = r.json()["antwort"]
    assert antwort == ANTWORT

    # Dieselbe Pruefung wie bei einer eingefuegten Antwort; geschrieben wird nichts.
    vorher = _config()
    geprueft = client.post("/api/vorlagen/pruefen", json={**VORLAGE, "antwort": antwort})
    assert geprueft.status_code == 200
    assert "Nichts fällt auf." in geprueft.json()["html"]
    assert _config() == vorher


def test_every_sending_needs_a_new_look_at_the_text(server):
    _eintragen(server.adresse)
    _text, stichwort, _stueck = _hinaus(**VORLAGE)
    assert client.post("/api/vorlagen/senden", json={"stichwort": stichwort}).status_code == 200
    # Dasselbe Stichwort ein zweites Mal: nichts geht hinaus.
    zweites = client.post("/api/vorlagen/senden", json={"stichwort": stichwort})
    assert zweites.status_code == 409
    assert len(server.anfragen) == 1
    # Auch ein Text ohne Blick darauf: kein Stichwort, nichts geht hinaus.
    assert client.post("/api/vorlagen/senden", json={}).status_code == 409
    assert len(server.anfragen) == 1


def test_a_look_that_is_too_old_or_a_changed_connection_sends_nothing(server, monkeypatch):
    _eintragen(server.adresse)
    monkeypatch.setattr(an, "FREIGABE_SEKUNDEN", -1)       # schon beim Zeigen abgelaufen
    _text, stichwort, _stueck = _hinaus(**VORLAGE)
    assert client.post("/api/vorlagen/senden", json={"stichwort": stichwort}).status_code == 409
    monkeypatch.setattr(an, "FREIGABE_SEKUNDEN", 600)

    _eintragen(server.adresse)
    _text, stichwort, _stueck = _hinaus(**VORLAGE)
    _eintragen(server.adresse, schluessel="", modell="anderes-modell")
    antwort = client.post("/api/vorlagen/senden", json={"stichwort": stichwort})
    assert antwort.status_code == 409 and "geändert" in antwort.json()["error"]
    assert server.anfragen == []


def test_a_remote_target_says_the_text_leaves_the_computer():
    _eintragen("https://api.example.test/v1")
    text, _stichwort, stueck = _hinaus(**VORLAGE)
    assert "Das verlässt den Rechner" in stueck
    assert "Der Text bleibt auf diesem Rechner" not in stueck
    assert "api.example.test" in stueck
    assert html.escape(text, quote=False) in stueck or text in html.unescape(stueck)


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_a_local_address_says_the_text_stays(host):
    _eintragen(f"http://{host}:9/v1")
    _text, _stichwort, stueck = _hinaus(**VORLAGE)
    assert "Der Text bleibt auf diesem Rechner" in stueck
    assert "Das verlässt den Rechner" not in stueck


# ------------------------------------------------------------- Eintrag

def test_the_address_is_checked_and_completed():
    ok = {"modell": "m"}
    for falsch in ("", "ftp://host/v1", "host/v1", "http://example.test/v1",
                   "https://name:geheim@example.test/v1", "https://example.test/v1?x=1",
                   "https://example.test:abc/v1"):
        r = client.post("/api/vorlagen/anbindung", json={**ok, "adresse": falsch})
        assert r.status_code == 400, falsch
        assert r.json()["error"]
    assert an.laden() is None
    for eingabe, soll in (
            ("https://example.test/v1", "https://example.test/v1/chat/completions"),
            ("https://example.test/v1/", "https://example.test/v1/chat/completions"),
            ("https://example.test/v1/chat/completions", "https://example.test/v1/chat/completions"),
            ("http://localhost:11434", "http://localhost:11434/chat/completions"),
            ("http://[::1]:8080/v1", "http://[::1]:8080/v1/chat/completions")):
        assert an.adresse_pruefen(eingabe) == soll
    kein_modell = {"adresse": "https://example.test/v1", "modell": " "}
    assert client.post("/api/vorlagen/anbindung", json=kein_modell).status_code == 400


def test_the_key_is_not_in_config_not_in_a_reply_and_not_in_a_log(server, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    antworten = [_eintragen(server.adresse).text]
    antworten.append(client.get("/vorlagen/anbindung").text)
    antworten.append(client.get("/vorlagen?art=monat").text)
    _text, stichwort, stueck = _hinaus(**VORLAGE)
    antworten.append(stueck)
    antworten.append(client.post("/api/vorlagen/senden", json={"stichwort": stichwort}).text)
    # Auch Fehler, die den Koerper des fremden Servers zitieren koennten.
    for modus in ("401", "404", "500", "weiter", "form"):
        server.modus = modus
        _t, st, _s = _hinaus(**VORLAGE)
        antworten.append(client.post("/api/vorlagen/senden", json={"stichwort": st}).text)
    antworten.append(client.post("/api/vorlagen/anbindung/schluessel-entfernen").text)
    for a in antworten:
        assert SCHLUESSEL not in a
        assert SCHLUESSEL[:8] not in a                    # auch nicht der Anfang
    assert SCHLUESSEL not in caplog.text
    ausgabe = capsys.readouterr()
    assert SCHLUESSEL not in ausgabe.out + ausgabe.err
    for datei in CONFIG_DIR.rglob("*"):
        if datei.is_file():
            assert SCHLUESSEL.encode() not in datei.read_bytes(), datei
    assert SCHLUESSEL not in an.PFAD.read_text(encoding="utf-8")


def test_the_key_file_is_for_the_user_only_and_lies_outside_config():
    _eintragen("https://example.test/v1")
    schluessel_datei = an.SCHLUESSEL_PATH
    assert schluessel_datei.read_text(encoding="utf-8").strip() == SCHLUESSEL
    assert CONFIG_DIR.resolve() not in schluessel_datei.resolve().parents
    assert not (an.SCHLUESSEL_PATH.parent / (an.SCHLUESSEL_PATH.name + ".neu")).exists()
    if os.name != "nt":
        assert (schluessel_datei.stat().st_mode & 0o777) == 0o600
    # Die Seite sagt "eingetragen", zeigt ihn nie und hat ein leeres Feld.
    seite = client.get("/vorlagen/anbindung").text
    assert "eingetragen" in seite and SCHLUESSEL not in seite
    assert re.search(r'type="password"[^>]*value=""', seite)
    # Eine Anbindung neu speichern, ohne den Schluessel neu zu tippen, laesst ihn stehen.
    client.post("/api/vorlagen/anbindung", json={"adresse": "https://example.test/v2",
                                                 "modell": "x", "schluessel": ""})
    assert schluessel_datei.read_text(encoding="utf-8").strip() == SCHLUESSEL
    # Ein Schluessel, der eine Kopfzeile sprengen koennte, wird abgelehnt, ohne ihn zu nennen.
    boese = "abc\r\nX-Evil: 1"
    r = client.post("/api/vorlagen/anbindung", json={"adresse": "https://example.test/v2",
                                                     "modell": "x", "schluessel": boese})
    assert r.status_code == 400 and "abc" not in r.json()["error"]


def test_removing_the_key_and_the_connection_switches_everything_off(server):
    _eintragen(server.adresse)
    assert an.schluessel_da()
    r = client.post("/api/vorlagen/anbindung/schluessel-entfernen").json()
    assert r["schluessel"] is False and r["anbindung"] is True
    assert not an.SCHLUESSEL_PATH.exists()
    _text, stichwort, _s = _hinaus(**VORLAGE)
    # Entfernen nimmt auch die gezeigte Freigabe mit: Danach geht nichts mehr hinaus.
    r = client.post("/api/vorlagen/anbindung/entfernen").json()
    assert r["anbindung"] is False and r["schluessel"] is False
    assert not an.PFAD.exists() and not an.SCHLUESSEL_PATH.exists()
    assert client.post("/api/vorlagen/senden", json={"stichwort": stichwort}).status_code == 409
    assert "Senden …" not in client.get("/vorlagen?art=monat").text
    assert server.anfragen == []


def test_a_connection_without_a_key_sends_no_authorization_header(server):
    _eintragen(server.adresse, schluessel="")
    _text, stichwort, _s = _hinaus(**VORLAGE)
    assert client.post("/api/vorlagen/senden", json={"stichwort": stichwort}).status_code == 200
    assert "Authorization" not in server.anfragen[0]["kopf"]


# ------------------------------------------------------------ Fehler

def _senden_mit_fehler(adresse: str) -> str:
    _eintragen(adresse)
    _text, stichwort, _s = _hinaus(**VORLAGE)
    r = client.post("/api/vorlagen/senden", json={"stichwort": stichwort})
    assert r.status_code >= 400
    return r.json()["error"]


def test_a_wrong_address_gives_a_readable_message():
    frei = socket.socket()
    frei.bind(("127.0.0.1", 0))
    port = frei.getsockname()[1]
    frei.close()                                          # nichts hoert mehr dort zu
    meldung = _senden_mit_fehler(f"http://127.0.0.1:{port}/v1")
    assert "Keine Verbindung zu 127.0.0.1" in meldung
    assert SCHLUESSEL not in meldung


def test_a_timeout_gives_a_readable_message(server, monkeypatch):
    monkeypatch.setattr(an, "ZEIT", 0.3)
    server.wartezeit = 1.5
    meldung = _senden_mit_fehler(server.adresse)
    assert "nicht geantwortet" in meldung and "127.0.0.1" in meldung


@pytest.mark.parametrize("modus, wort", [("401", "abgelehnt"), ("404", "404"),
                                         ("500", "500"), ("form", "chat completions")])
def test_an_error_from_the_server_gives_a_readable_message(server, modus, wort):
    server.modus = modus
    meldung = _senden_mit_fehler(server.adresse)
    assert wort in meldung and "127.0.0.1" in meldung
    if modus == "401":
        assert "401" in meldung
    # Der Koerper der Antwort wird nicht zitiert: Mancher Dienst wiederholt darin den Schluessel.
    assert SCHLUESSEL not in meldung and SCHLUESSEL[:8] not in meldung


def test_a_redirect_is_not_followed(server):
    zweit = _Server()
    try:
        server.modus = "weiter"
        server.zweit_port = zweit.port
        meldung = _senden_mit_fehler(server.adresse)
        assert "verweist auf eine andere Adresse" in meldung
        assert zweit.anfragen == []                       # Text und Schluessel gingen nicht weiter
    finally:
        zweit.schliessen()


def _config() -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(CONFIG_DIR.glob("*.yaml"))
            if p.name != "anbindung.yaml"}
