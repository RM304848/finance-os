"""Vorlagen: ein Text zum Kopieren fuer ein Modell nach Wahl, und die Antwort zurueck.

Ohne Anbindung schickt die Seite nichts. Sie baut die Vorlage (`web/vorlagen.py`),
der Haushalt kopiert sie selbst, und die eingefuegte Antwort wird gelesen und
geprueft. Sie schreibt nichts: Eine Regel aus einem Vorschlag legt erst
`/api/regeln/vorschlaege/uebernehmen` an, nachdem jemand angehakt hat.

Mit einer Anbindung (`web/anbindung.py`, ADR 0002) kann der Haushalt die Vorlage
auch selbst senden lassen: erst zeigt die Seite den Text und das Ziel
(`/api/vorlagen/hinaus`), dann sendet ein Knopf genau diesen Text
(`/api/vorlagen/senden`). Die Antwort laeuft durch dieselbe Pruefung wie eine
eingefuegte. Dies sind die einzigen Routen, die die Schnittstelle rufen.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse

from finctl.rules import vorschlaege as vs
from finctl.web import anbindung as _an
from finctl.web import vorlagen as _vl
from finctl.web.basis import TEMPLATES, conn, stueck

router = APIRouter()


def _vorlage(c, body: dict) -> _vl.Vorlage:
    texte = body.get("texte")
    return _vl.bauen(str(body.get("art") or ""), c, monat=str(body.get("monat") or ""),
                     frage=str(body.get("frage") or ""),
                     texte=[str(t) for t in texte] if isinstance(texte, list) else None)


@router.get("/vorlagen", response_class=HTMLResponse)
def vorlagen(request: Request, art: str = "einordnen", monat: str = "", frage: str = ""):
    """Die gewaehlte Vorlage samt Eingaben; ohne Angabe Einordnen."""
    from finctl import module

    arten = [a for a in _vl.ARTEN
             if a != "prognose" or module.seite_an("/konten", "/hochrechnung")]
    art = art if art in arten else "einordnen"
    c = conn()
    try:
        texte = _vl.einordnen_texte(c) if art == "einordnen" else []
        try:
            vorlage, fehler = _vl.bauen(art, c, monat=monat, frage=frage), ""
        except ValueError as e:
            vorlage, fehler = None, str(e)
    finally:
        c.close()
    return TEMPLATES.TemplateResponse(request, "vorlagen.html", {
        "reiter": [{"id": a, "label": _vl.ARTEN[a][0], "href": f"/vorlagen?art={a}"}
                   for a in arten],
        "art": art, "titel": _vl.ARTEN[art][0], "vorlage": vorlage, "fehler": fehler,
        "texte": texte, "monat": monat or _vl.vormonat(date.today()), "frage": frage,
        "frage_max": _vl.FRAGE_MAX, "anbindung": _an.laden()})


@router.post("/api/vorlagen/vorlage")
async def api_vorlage(request: Request):
    """Die Vorlage neu bauen, mit den angehakten Texten, dem Monat oder der Frage."""
    body = await request.json()
    c = conn()
    try:
        return {"text": _vorlage(c, body).text}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        c.close()


@router.post("/api/vorlagen/pruefen")
async def api_pruefen(request: Request):
    """Die eingefuegte Antwort lesen und als Vorschlag zeigen. Schreibt nichts."""
    body = await request.json()
    antwort = str(body.get("antwort") or "")
    c = conn()
    try:
        if body.get("art") == "einordnen":
            zeilen = vs.antwort_lesen(antwort)
            if not zeilen:
                return JSONResponse(
                    {"error": "Keine Zeile der Form „Suchtext ; Kategorie“ gefunden."},
                    status_code=400)
            return {"html": stueck("_vorlage_antwort.html", art="einordnen",
                                   zeilen=vs.pruefen(c, zeilen))}
        v = _vorlage(c, body)
        return {"html": stueck("_vorlage_antwort.html", art=v.art,
                               erklaerung=_vl.erklaerung_lesen(antwort, v))}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        c.close()


# ------------------------------------------------------------------ Senden

@router.post("/api/vorlagen/hinaus")
async def api_hinaus(request: Request):
    """Zeigen, was hinausgeht und wohin. Sendet nichts; das Stichwort gilt fuer ein Senden."""
    body = await request.json()
    c = conn()
    try:
        text = _vorlage(c, body).text
        stichwort, a = _an.freigeben(text)
    except _an.AnbindungError as e:
        return JSONResponse({"error": str(e)}, status_code=e.status)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        c.close()
    return {"html": stueck("_hinaus.html", anbindung=a, text=text, stichwort=stichwort)}


@router.post("/api/vorlagen/senden")
async def api_senden(request: Request):
    """Den freigegebenen Text senden. Die Antwort wird NICHT geprueft oder uebernommen."""
    body = await request.json()
    try:
        antwort = await run_in_threadpool(_an.senden, str(body.get("stichwort") or ""))
    except _an.AnbindungError as e:
        return JSONResponse({"error": str(e)}, status_code=e.status)
    return {"antwort": antwort}


# --------------------------------------------------------------- Anbindung

def _stand() -> dict:
    """Der Stand als Stueck und als zwei Wahrheitswerte fuer die Knoepfe der Seite."""
    a, schluessel = _an.laden(), _an.schluessel_da()
    return {"ok": True, "anbindung": a is not None, "schluessel": schluessel,
            "html": stueck("_anbindung_stand.html", anbindung=a, schluessel=schluessel)}


@router.get("/vorlagen/anbindung", response_class=HTMLResponse)
def anbindung_seite(request: Request):
    return TEMPLATES.TemplateResponse(request, "anbindung.html", {
        "anbindung": _an.laden(), "schluessel": _an.schluessel_da(), "stand": _stand()["html"]})


@router.post("/api/vorlagen/anbindung")
async def api_anbindung(request: Request):
    """Adresse und Modell eintragen, auf Wunsch den Schluessel. Verbindet sich nicht."""
    body = await request.json()
    try:
        _an.speichern(body.get("adresse"), body.get("modell"))
        if str(body.get("schluessel") or "").strip():
            _an.schluessel_setzen(body.get("schluessel"))
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return _stand()


@router.post("/api/vorlagen/anbindung/schluessel-entfernen")
def api_schluessel_entfernen():
    _an.schluessel_entfernen()
    return _stand()


@router.post("/api/vorlagen/anbindung/entfernen")
def api_anbindung_entfernen():
    """Zurueck auf ausgeschaltet: Eintrag und Schluessel weg."""
    _an.entfernen()
    return _stand()
