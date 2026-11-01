"""Reihen: wie oft eine Zahlung kommt, erkannt oder vom Haushalt festgelegt.

Die Seite rechnet nichts selbst. Takt, Betrag je Termin und Jahreswert kommen
aus `forecast/takt.py`, die Handentscheidungen aus `finctl/reihen.py`; was der
Haushalt hier festlegt, steht danach in `config/reihen_custom.yaml`.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from finctl import notizen as _notizen
from finctl import reihen as _reihen
from finctl.forecast import stichtag as _stichtag
from finctl.forecast import takt as _takt
from finctl.forecast import zusammenfuehren as _zusammen
from finctl.web.basis import TEMPLATES, categories, conn

router = APIRouter()

#: Mit "alle" zeigt die Seite auch die unregelmaessigen Reihen, aber keine
#: einzelne Buchung: erst ab zwei Buchungen ist es eine Reihe.
MIN_BUCHUNGEN_ALLE = 2

#: Was die Auswahl je Reihe anbietet: der Wert im Formular und sein Text.
TAKT_WAHL = [(str(t), _takt.takt_name(t)) for t in _takt.FESTE_TAKTE] + [
    (_takt.UNREGELMAESSIG, _takt.takt_name(_takt.UNREGELMAESSIG))]


def _buchungen_je_termin(reihe: _takt.Reihe) -> list[dict]:
    """Die Termine der Reihe mit den Buchungen darin, jede mit ihrer Kennung.

    Ein Termin kennt nur Tag und Betrag seiner Buchungen; die Kennung steht an
    den Teilen. Zwei Buchungen mit gleichem Tag und Betrag tauschen dabei nur
    die Kennung, nicht das, was die Seite zeigt.
    """
    kennungen: dict[tuple, list[str]] = defaultdict(list)
    for teil in reihe.teile:
        kennungen[(teil.tag, teil.cents)].append(teil.dedup_hash)
    beitrag = reihe.beitrag
    ausreisser = set(beitrag.ausreisser) if beitrag else set()
    verlauf = set(beitrag.verlauf) if beitrag else set()
    termine = reihe.termine or tuple(
        _takt.Termin(t.tag, t.cents, ((t.tag, t.cents),)) for t in reihe.teile)
    zeilen = []
    for termin in termine:
        hinweis = ("Ausreißer" if termin in ausreisser
                   else "Verlauf" if termin in verlauf else "")
        buchungen = []
        for tag, cents in termin.buchungen:
            frei = kennungen[(tag, cents)]
            buchungen.append({"tag": tag.isoformat(), "cents": cents,
                              "buchung": frei.pop(0) if frei else ""})
        zeilen.append({"tag": termin.tag.isoformat(), "cents": termin.cents,
                       "hinweis": hinweis, "buchungen": buchungen})
    return zeilen


def _kennung(reihe: _takt.Reihe) -> str:
    """Eine Kennung fuer das Markup, die an der Reihe haengt und nicht an ihrer
    Stelle in der Liste: nach dem Speichern oeffnet die Seite dieselbe Zeile."""
    roh = f"{reihe.gegenpartei}|{reihe.kategorie}".encode()
    return "r" + hashlib.sha1(roh, usedforsecurity=False).hexdigest()[:10]


def _kandidaten(alle: tuple[_takt.Reihe, ...]) -> dict[str, list[dict]]:
    """Je Kategorie die Reihen, zu denen eine Schreibweise gehoeren kann: jede Reihe der
    Kategorie, auch eine ohne festen Takt oder mit einer einzigen Buchung, denn eine neue
    Schreibweise faengt so an."""
    je_kategorie: dict[str, list[dict]] = defaultdict(list)
    for r in alle:
        je_kategorie[r.kategorie].append({
            "gegenpartei": r.gegenpartei,
            "zuletzt": max(t.tag for t in r.teile).isoformat()})
    for liste in je_kategorie.values():
        liste.sort(key=lambda k: k["gegenpartei"])
    return je_kategorie


def _zeile(reihe: _takt.Reihe, namen: dict[str, str],
           eintrag: _reihen.Eintrag | None, kandidaten: dict[str, list[dict]]) -> dict:
    b = reihe.beitrag
    return {
        "id": _kennung(reihe), "gegenpartei": reihe.gegenpartei, "kategorie": reihe.kategorie,
        "kategorie_name": namen.get(reihe.kategorie) or reihe.kategorie or "ohne Kategorie",
        "takt": str(reihe.takt) if reihe.festgelegt else "",
        "takt_name": _takt.takt_name(reihe.takt), "festgelegt": reihe.festgelegt,
        "fest": reihe.fest, "buchungen": len(reihe.teile),
        # Eine Buchung der Reihe genuegt, um sie anzusprechen.
        "buchung": reihe.teile[-1].dedup_hash,
        "betrag_cents": b.betrag_je_termin if b else None,
        "letzter": b.letzter_termin.isoformat() if b else "",
        "laeuft": b.laeuft if b else None,
        "jahreswert_cents": b.jahreswert if b else None,
        "notiz": eintrag.notiz if eintrag else "",
        "notiz_vom": eintrag.notiz_vom if eintrag else "",
        "termine": _buchungen_je_termin(reihe),
        "schreibweisen": list(reihe.schreibweisen),
        "kandidaten": [k for k in kandidaten.get(reihe.kategorie, ())
                       if k["gegenpartei"] != reihe.gegenpartei],
    }


def _vorschlaege(gefunden: _takt.Reihen, namen: dict[str, str]) -> list[dict]:
    """Die Vorschlaege der Seite, ein Paar von Schreibweisen je Zeile: Dieselbe Zahlung
    steht oft in mehreren Kategorien, und eine Zusammenfuehrung gilt fuer alle."""
    je_paar: dict[tuple[str, str], dict] = {}
    for v in _zusammen.vorschlaege(gefunden):
        zeile = je_paar.setdefault((v.alt.gegenpartei, v.neu.gegenpartei), {
            "alt": v.alt.gegenpartei, "neu": v.neu.gegenpartei, "kategorien": [],
            "bis": v.alt.beitrag.letzter_termin.isoformat(),
            "ab": v.neu.termine[0].tag.isoformat(),
            "betrag_cents": v.neu.beitrag.betrag_je_termin})
        zeile["kategorien"].append(namen.get(v.alt.kategorie) or v.alt.kategorie)
    return sorted(je_paar.values(), key=lambda z: (z["kategorien"][0], z["alt"]))


def _sichtbar(reihe: _takt.Reihe, alle: bool) -> bool:
    if reihe.fest or reihe.festgelegt:
        return True
    return alle and len(reihe.teile) >= MIN_BUCHUNGEN_ALLE


@router.get("/reihen", response_class=HTMLResponse)
def reihen_seite(request: Request, zeige: str = ""):
    alle = zeige == "alle"
    c = conn()
    try:
        gefunden = _reihen.laden(c, _stichtag.stichtag(c))
        eintraege = _reihen.notizen(c)
        namen = {k["id"]: k["label"] for k in categories(c)}
        einmalig = [{**z, "kategorie_name": namen.get(z["kategorie"]) or z["kategorie"]}
                    for z in _reihen.einmalige_buchungen(c)]
    finally:
        c.close()
    zahl = {"": sum(1 for r in gefunden.reihen if _sichtbar(r, False)),
            "alle": sum(1 for r in gefunden.reihen if _sichtbar(r, True))}
    kandidaten = _kandidaten(gefunden.reihen)
    zeilen = [_zeile(r, namen, eintraege.get((r.gegenpartei, r.kategorie)), kandidaten)
              for r in gefunden.reihen if _sichtbar(r, alle)]
    return TEMPLATES.TemplateResponse(request, "reihen.html", {
        "zeilen": zeilen, "einmalig": einmalig,
        "vorschlaege": _vorschlaege(gefunden, namen), "takt_wahl": TAKT_WAHL, "zeige": zeige,
        "anzeigen": [("", "Feste Takte", zahl[""]), ("alle", "Alle", zahl["alle"])],
        "von": gefunden.von.isoformat(), "stichtag": gefunden.stichtag.isoformat(),
    })


def _fehler(text: str) -> JSONResponse:
    return JSONResponse({"error": text}, status_code=400)


@router.post("/api/reihen/takt")
async def api_reihen_takt(request: Request):
    """Den Takt einer Reihe festlegen, oder die Festlegung zuruecknehmen (leerer Takt)."""
    body = await request.json()
    roh = body.get("takt")
    notiz = body.get("notiz")
    c = conn()
    try:
        geschrieben = _reihen.festlegen(
            c, str(body.get("buchung") or ""),
            None if roh in (None, "") else _reihen.takt_lesen(roh),
            None if notiz is None else _notizen.eingabe(notiz))
    except ValueError as fehler:
        return _fehler(str(fehler))
    finally:
        c.close()
    return {"ok": True, "geschrieben": geschrieben}


@router.post("/api/reihen/zusammen")
async def api_reihen_zusammen(request: Request):
    """Eine Schreibweise einer anderen Gegenpartei zuordnen, oder die Zuordnung
    zuruecknehmen (leeres Ziel)."""
    body = await request.json()
    ziel = str(body.get("ziel") or "")
    c = conn()
    try:
        geschrieben = _reihen.zusammenfuehren(
            c, str(body.get("schreibweise") or ""), ziel or None)
    except ValueError as fehler:
        return _fehler(str(fehler))
    finally:
        c.close()
    return {"ok": True, "geschrieben": geschrieben}


@router.post("/api/reihen/einmalig")
async def api_reihen_einmalig(request: Request):
    """Eine Buchung einmalig setzen oder die Markierung zuruecknehmen."""
    body = await request.json()
    c = conn()
    try:
        geschrieben = _reihen.einmalig_setzen(
            c, str(body.get("buchung") or ""), bool(body.get("einmalig")))
    except ValueError as fehler:
        return _fehler(str(fehler))
    finally:
        c.close()
    return {"ok": True, "geschrieben": geschrieben}
