"""MCP ueber stdio: JSON-RPC 2.0, eine Nachricht je Zeile.

Gebaut wird nur, was ein Modell zum Lesen und Vorschlagen braucht: `initialize`,
`ping`, `tools/list`, `tools/call`, `resources/list`, `resources/read`. Ein
Werkzeug, das scheitert, ist eine Antwort mit `isError` (das Modell soll die Meldung
lesen), ein Fehler im Protokoll ein JSON-RPC-Fehler.

STDOUT GEHOERT DEM PROTOKOLL. Alles, was beim Rechnen auf stdout gedruckt wird, waere
eine Zeile, die kein Modell versteht und die den Strom bricht; waehrend eines Aufrufs
geht stdout deshalb nach stderr.
"""

from __future__ import annotations

import contextlib
import json
import sys
from typing import IO

import finctl
from finctl.mcp import werkzeuge

#: Die Fassungen des Protokolls, die diese Umsetzung versteht (neueste zuerst).
FASSUNGEN = ("2025-06-18", "2025-03-26", "2024-11-05")

ANLEITUNG = (
    "Finance OS: ein lokales Finanzwerkzeug. Lies mit den Werkzeugen; sie rechnen so, wie die "
    "Seiten der App rechnen. Rechne keine angezeigte Zahl selbst. Die Begriffe stehen in der "
    "Ressource finctl://glossar. Du schreibst nie selbst: `vorschlagen` legt einen Vorschlag "
    "ab, den der Haushalt in der App bestaetigt.")

PARSE, UNGUELTIG, UNBEKANNT, PARAMETER, INTERN = -32700, -32600, -32601, -32602, -32603


def _fehler(kennung, code: int, text: str) -> dict:
    return {"jsonrpc": "2.0", "id": kennung, "error": {"code": code, "message": text}}


def _antwort(kennung, ergebnis: dict) -> dict:
    return {"jsonrpc": "2.0", "id": kennung, "result": ergebnis}


def behandeln(nachricht: object) -> dict | None:
    """Die Antwort auf eine Nachricht; `None` bei einer Benachrichtigung (ohne `id`)."""
    if not isinstance(nachricht, dict) or nachricht.get("jsonrpc") != "2.0" \
            or not isinstance(nachricht.get("method"), str):
        return _fehler(nachricht.get("id") if isinstance(nachricht, dict) else None,
                       UNGUELTIG, "Keine JSON-RPC-Nachricht.")
    methode, kennung = nachricht["method"], nachricht.get("id")
    params = nachricht.get("params") or {}
    if "id" not in nachricht:
        return None                      # notifications/initialized & Co.: keine Antwort
    if not isinstance(params, dict):
        return _fehler(kennung, PARAMETER, "params ist ein Objekt.")
    try:
        return _antwort(kennung, _methode(methode, params))
    except LookupError as fehler:
        return _fehler(kennung, UNBEKANNT if methode not in _METHODEN else PARAMETER,
                       str(fehler.args[0]))
    except Exception as fehler:
        return _fehler(kennung, INTERN, f"{type(fehler).__name__}: {fehler}")


def _initialize(params: dict) -> dict:
    gewuenscht = str(params.get("protocolVersion") or "")
    return {"protocolVersion": gewuenscht if gewuenscht in FASSUNGEN else FASSUNGEN[0],
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": "finctl", "version": finctl.__version__},
            "instructions": ANLEITUNG}


def _tools_call(params: dict) -> dict:
    name, args = params.get("name"), params.get("arguments") or {}
    if name not in werkzeuge.WERKZEUGE:
        raise LookupError(f"Unbekanntes Werkzeug: {name}")
    if not isinstance(args, dict):
        raise LookupError("arguments ist ein Objekt.")
    try:
        with contextlib.redirect_stdout(sys.stderr):
            text, fehler = werkzeuge.aufrufen(name, args), False
    except ValueError as meldung:
        text, fehler = str(meldung), True
    return {"content": [{"type": "text", "text": text}], "isError": fehler}


def _resources_read(params: dict) -> dict:
    uri = str(params.get("uri") or "")
    if uri not in werkzeuge.RESSOURCEN:
        raise LookupError(f"Unbekannte Ressource: {uri}")
    with contextlib.redirect_stdout(sys.stderr):
        text = werkzeuge.RESSOURCEN[uri].lesen()
    return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}]}


_METHODEN = {
    "initialize": _initialize,
    "ping": lambda params: {},
    "tools/list": lambda params: {"tools": [w.als_dict() for w in werkzeuge.WERKZEUGE.values()]},
    "tools/call": _tools_call,
    "resources/list": lambda params: {"resources": [r.als_dict()
                                                    for r in werkzeuge.RESSOURCEN.values()]},
    "resources/read": _resources_read,
}


def _methode(methode: str, params: dict) -> dict:
    if methode not in _METHODEN:
        raise LookupError(f"Unbekannte Methode: {methode}")
    return _METHODEN[methode](params)


def laufen(ein: IO[str] | None = None, aus: IO[str] | None = None) -> None:
    """Lesen, bis der Strom endet. Eine Zeile ist eine Nachricht."""
    ein, aus = ein or sys.stdin, aus or sys.stdout
    for zeile in ein:
        if not zeile.strip():
            continue
        try:
            antwort = behandeln(json.loads(zeile))
        except json.JSONDecodeError:
            antwort = _fehler(None, PARSE, "Kein JSON.")
        if antwort is not None:
            aus.write(json.dumps(antwort, ensure_ascii=False) + "\n")
            aus.flush()
