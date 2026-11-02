"""Vorschlaege einer KI: ansehen, uebernehmen, verwerfen (ADR 0002).

Die Seite zeigt, was sich aendern wuerde. "Uebernehmen" macht das Skript der Seite:
Es schickt die Felder an die Route, die die Seiten selbst benutzen (`route` und
`body` kommen aus der Pruefung des Servers, nicht aus der Datei), und loescht den
Vorschlag, sobald die Route angenommen hat. Die Seite schreibt selbst nichts.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from finctl.web import vorschlaege as _vs
from finctl.web.basis import TEMPLATES, conn

router = APIRouter()


@router.get("/vorschlaege", response_class=HTMLResponse)
def vorschlaege(request: Request):
    c = conn()
    try:
        liste = _vs.fuer_seite(c)
    finally:
        c.close()
    # Was das Skript an die Routen schickt: je Vorschlag Route und Koerper aus der Pruefung.
    senden = {v["id"]: {"route": v["pruefung"].route, "body": v["pruefung"].body}
              for v in liste if v["pruefung"]}
    return TEMPLATES.TemplateResponse(request, "vorschlaege.html",
                                      {"liste": liste, "senden": senden})


@router.post("/api/vorschlaege/{kennung}/verwerfen")
def api_verwerfen(kennung: str):
    """Den Vorschlag loeschen, ob verworfen oder uebernommen. Mehr bleibt nicht zurueck."""
    try:
        gab_es = _vs.verwerfen(kennung)
    except ValueError as fehler:
        return JSONResponse({"error": str(fehler)}, status_code=404)
    return {"ok": True, "gab_es": gab_es, "offen": _vs.anzahl()}
