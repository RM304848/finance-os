"""Nur eine Datei der App spricht ein Netz an (ADR 0002).

Daten verlassen den Rechner nur auf ausdrueckliche Wahl des Haushalts. Das haelt kein
Test aus, der einen Weg prueft; es haelt nur eine Sperre, die jeden NEUEN Weg faellt:
Kein Modul des Pakets darf `urllib.request`, `http.client` oder `socket` (und die
ueblichen Netzbibliotheken) einbinden -- ausser `finctl/web/anbindung.py`, hinter dem
Knopf, den die Seite erst nach dem Zeigen des Textes anbietet. Wie `test_pfade.py`:
Die Liste der Erlaubten darf kuerzer werden und nie laenger.
"""

from __future__ import annotations

import ast
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
PAKET = WURZEL / "finctl"

#: Was ein Netz ansprechen kann. `urllib.parse` und `uvicorn` (der Server) stehen nicht hier.
NETZ = ("urllib.request", "urllib2", "urllib3", "http.client", "socket", "requests", "httpx",
        "aiohttp", "smtplib", "ftplib", "telnetlib", "websocket", "websockets", "xmlrpc.client")

#: Die eine Datei, die ein Modell ansprechen darf.
ANBINDUNG = "finctl/web/anbindung.py"

#: Wer sonst Netz einbindet, mit Grund. Der Starter fragt nur den eigenen Rechner, ob die
#: App schon laeuft, und sucht einen freien Port; er verbindet sich mit nichts anderem.
NUR_DIESER_RECHNER = {"finctl/starter.py": "Gesundheitsprobe und freier Port auf 127.0.0.1"}


def _quellen() -> list[tuple[str, ast.Module]]:
    out = []
    for pfad in sorted(PAKET.rglob("*.py")):
        rel = pfad.relative_to(WURZEL).as_posix()
        out.append((rel, ast.parse(pfad.read_text(encoding="utf-8"), filename=rel)))
    return out


def _netz(name: str) -> bool:
    return any(name == n or name.startswith(n + ".") for n in NETZ)


def _eingebunden(baum: ast.Module) -> set[str]:
    """Jedes Netzmodul, das ein Modul einbindet: `import x`, `from x import y`, `import_module`."""
    gefunden = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            gefunden |= {a.name for a in knoten.names if _netz(a.name)}
        elif isinstance(knoten, ast.ImportFrom) and knoten.module:
            if _netz(knoten.module):
                gefunden.add(knoten.module)
            # `from urllib import request` und `from http import client`
            gefunden |= {f"{knoten.module}.{a.name}" for a in knoten.names
                         if _netz(f"{knoten.module}.{a.name}")}
        elif isinstance(knoten, ast.Call):
            name = getattr(knoten.func, "attr", None) or getattr(knoten.func, "id", None)
            if name in ("import_module", "__import__") and knoten.args:
                arg = knoten.args[0]
                if isinstance(arg, ast.Constant) and _netz(str(arg.value)):
                    gefunden.add(str(arg.value))
    return gefunden


def test_only_the_connection_module_may_use_the_network():
    fremd = {rel: sorted(_eingebunden(baum)) for rel, baum in _quellen()
             if rel != ANBINDUNG and rel not in NUR_DIESER_RECHNER and _eingebunden(baum)}
    assert not fremd, (f"Netz ausserhalb von {ANBINDUNG}: {fremd}. Wer Daten senden will, "
                       "geht ueber die Anbindung (ADR 0002): Zeigen, bestaetigen, senden.")


def test_the_connection_module_is_the_one_that_does():
    """Sonst prueft der Test nichts: Er muss die Datei finden, vor der er warnt."""
    baeume = dict(_quellen())
    assert "urllib.request" in _eingebunden(baeume[ANBINDUNG])


def test_the_exceptions_stay_few_and_local():
    """Der Starter fragt `127.0.0.1` und nichts sonst."""
    baeume = dict(_quellen())
    mit_netz = {r for r in baeume if r != ANBINDUNG and _eingebunden(baeume[r])}
    assert set(NUR_DIESER_RECHNER) == mit_netz
    starter = (WURZEL / "finctl/starter.py").read_text(encoding="utf-8")
    assert 'HOST = "127.0.0.1"' in starter
    # Jede Adresse, die er aufruft, beginnt mit dem eigenen Rechner.
    for knoten in ast.walk(baeume["finctl/starter.py"]):
        if isinstance(knoten, ast.Call) and getattr(knoten.func, "attr", "") == "urlopen":
            adresse = ast.unparse(knoten.args[0])
            assert adresse.startswith("f'http://{HOST}:"), adresse


def test_nothing_but_the_page_routes_calls_the_connection():
    """Weder die Einrichtung noch ein Hintergrundlauf noch der MCP-Zugang rufen die Anbindung."""
    rufer = set()
    for rel, baum in _quellen():
        if rel == ANBINDUNG:
            continue
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.ImportFrom) and knoten.module:
                namen = {a.name for a in knoten.names}
                if (knoten.module == "finctl.web.anbindung"
                        or (knoten.module == "finctl.web" and "anbindung" in namen)):
                    rufer.add(rel)
            elif isinstance(knoten, ast.Import):
                if any(a.name == "finctl.web.anbindung" for a in knoten.names):
                    rufer.add(rel)
    assert rufer == {"finctl/web/routen/vorlagen.py"}, rufer
    # Und dort nur in den Routen, die erst zeigen und dann senden.
    quelle = (WURZEL / "finctl/web/routen/vorlagen.py").read_text(encoding="utf-8")
    assert quelle.count("_an.senden") == 1
    assert "/api/vorlagen/senden" in quelle
