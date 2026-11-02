"""Vertraege mit Termin -- Abos und Versicherungen -- und ihre Buchungen."""

from __future__ import annotations

import copy as _copy
import datetime as _dtm

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from finctl.dateien import yaml_lesen
from finctl.web.basis import (
    CONFIG_DIR,
    TEMPLATES,
    _jsonfaehig,
    adresse,
    conn,
    notiz_felder,
    stueck,
    umleiten,
)

router = APIRouter()


# Eine Seite, zwei Reiter: dieselbe Tabelle, dieselben Masken, dieselbe
# Rechnung -- nur aus verschiedenen Dateien. Getrennt bleiben die DATEN, weil
# eine Versicherung anders gepflegt wird als ein Abo (kein Vorrat, anderer
# Rhythmus der Unterlagen).
REITER = {"abos": ("abo", "Abos"), "versicherungen": ("versicherung", "Versicherungen")}


def abo_zustand(a: dict) -> dict:
    """Der Entwurf eines Editors: eine Kopie des Vertrags.

    Gespeichert wird immer der ganze Vertrag; der Server legt davon nur ab, was
    von abos.yaml abweicht. Der Browser haelt den Entwurf, aendert ihn und
    schickt ihn an `/api/abos/editor` zurueck, wenn der Editor neu gezeichnet
    werden muss.
    """
    feste = ("id", "name", "kategorie", "konto", "betrag_cents", "takt", "faellig",
             "vorrat_bis", "gekuendigt_zum", "weg", "notiz")
    return _copy.deepcopy({
        **{f: a.get(f) for f in feste},
        "buchungen": a.get("buchungen") or [], "ignoriert": a.get("ignoriert") or [],
        "geteilt": a.get("geteilt") or {"besetzung": [], "zeitraeume": []}})


def _ableitung(st: dict, info: dict) -> dict:
    """Was der Editor aus Entwurf und Wissen des Servers ordnet, bevor er zeichnet.

    Fruehere Buchungen nach Betrag gruppiert, die haeufigste Gruppe zuerst;
    Zeitraeume mit ihrer Stelle im Entwurf, der juengste oben.
    """
    gruppen: dict[int, int] = {}
    for b in info.get("fruehere") or []:
        gruppen[b["amount_cents"]] = gruppen.get(b["amount_cents"], 0) + 1
    return {
        "gruppen": [{"cents": c, "n": n} for c, n in
                    sorted(gruppen.items(), key=lambda kv: -kv[1])],
        "zeitraeume": sorted(enumerate(st["geteilt"]["zeitraeume"]),
                             key=lambda t: t[1]["von"], reverse=True)}


TEMPLATES.env.globals["abo_ableitung"] = _ableitung


def _auswahl(c) -> tuple[list[dict], list[dict]]:
    """Konten und Kategorien, aus denen der Editor auswaehlen laesst."""
    konten = [dict(r) for r in c.execute(
        "SELECT id, display_name FROM accounts "
        "WHERE ingest_mode = 'parsed' AND active = 1 ORDER BY display_name")]
    kategorien = [
        {"id": r["id"], "label": f"{r['oberbegriff']} / {r['name']}"
         if r["oberbegriff"] else r["name"]}
        for r in c.execute(
            "SELECT k.id, k.name, o.name AS oberbegriff FROM mgmt_categories k "
            "LEFT JOIN mgmt_categories o ON o.id = k.parent_id "
            "WHERE k.parent_id IS NOT NULL ORDER BY k.id")]
    return konten, kategorien


@router.get("/vertraege", response_class=HTMLResponse)
def vertraege(request: Request, ansicht: str = "abos"):
    ansicht = ansicht if ansicht in REITER else "abos"
    reiter = [{"id": k, "label": name, "href": adresse(request, ansicht=k)}
              for k, (_, name) in REITER.items()]
    return _vertragsseite(request, REITER[ansicht][0], ansicht, reiter)


@router.get("/abos")
def abos_seite(request: Request):
    return umleiten(request, "/vertraege", ansicht="abos")


@router.get("/versicherungen")
def versicherungen_seite(request: Request):
    return umleiten(request, "/vertraege", ansicht="versicherungen")


def _vertragsseite(request: Request, art: str, ansicht: str, reiter: list[dict]):
    """Abos mit Termin: anlegen, aendern, teilen, einsammeln.

    Alles, was sich nicht aus den Buchungen ablesen laesst, wird hier
    eingetragen -- Vorrat, Kuendigung, wer mitzahlt. Was sich ablesen laesst,
    schlaegt die Seite vor.
    """
    from finctl import abos as _ab

    heute = _dtm.date.today()
    c = conn()
    try:
        try:
            liste, fehler = _ab.laden(art=art), None
        except ValueError as exc:
            liste, fehler = [], str(exc)
        konten, kategorien = _auswahl(c)
        datei, schluessel = CONFIG_DIR / _ab.ARTEN[art][0], _ab.ARTEN[art][1]
        roh = {str(e.get("id")): e for e in
               ((yaml_lesen(datei) or {}).get(schluessel) or [] if datei.exists() else [])}
        daten = []
        for a in liste:
            termine = _ab.posten([a], a["konto"], ab=heute,
                                 bis=_ab.plus_monate(heute, 37))
            abrechnung = _ab.abrechnung(c, a, heute=heute)
            daten.append(_jsonfaehig({
                **a,
                "naechster": termine[0]["faellig"] if termine else None,
                "abrechnung": abrechnung,
                "offen_cents": sum(z["offen"] for z in abrechnung),
                "faellig_offen": any(z["status"] == "faellig" for z in abrechnung),
                "preis": _ab.preisabweichung(c, a),
                "belege": _ab.belege(c, a),
                "vorschlaege": _ab.vorschlaege(c, a),
                "fruehere": _ab.fruehere(c, a),
                "laufend": _ab.laufend(c, a, heute=heute),
                "notiz_vom": notiz_felder(roh.get(a["id"]))["notiz_vom"],
            }))
    finally:
        c.close()
    return TEMPLATES.TemplateResponse(request, "abos.html", {
        "abos": daten, "fehler": fehler, "konten": konten,
        "zustaende": {a["id"]: abo_zustand(a) for a in daten},
        "kategorien": kategorien, "heute": heute.isoformat(),
        "art": art, "ansicht": ansicht, "reiter": reiter,
        "dateien": [f"config/{_ab.ARTEN[art][0]}"]})


@router.get("/api/abos/buchungen")
def api_abo_buchungen(q: str = "", ausser: list[str] = Query(default=[])):
    """Abbuchungen, aus denen ein Abo angelegt werden kann.

    `html` ist die Trefferliste, gerendert wie jedes Stueck des Editors;
    Buchungen in `ausser` (die dem Vertrag schon zugeordneten) fehlen darin.
    """
    from finctl import abos as _ab

    if len(q.strip()) < 2:
        return {"rows": []}
    c = conn()
    try:
        rows = [b for b in _ab.buchungen(c, q) if b["dedup_hash"] not in set(ausser)]
    finally:
        c.close()
    return {"rows": rows, "html": stueck("_abo_treffer.html", rows=rows)}


def _editor_html(art: str, st: dict, info: dict, neu: bool) -> str:
    c = conn()
    try:
        konten, kategorien = _auswahl(c)
    finally:
        c.close()
    return stueck("_abo_editor.html", art=art, st=st, info=info, neu=neu,
                  konten=konten, kategorien=kategorien)


@router.post("/api/abos/editor")
async def api_abo_editor(request: Request, art: str = "abo"):
    """Der Editor eines Vertrags als fertiges Stueck.

    Der Browser schickt den Entwurf (`st`) und was er dazu weiss (`info`), der
    Server zeichnet. Dieselbe Vorlage, die /vertraege beim Laden einbindet.
    """
    from finctl import abos as _ab

    if art not in _ab.ARTEN:
        return JSONResponse({"error": f"unbekannte Art {art}"}, status_code=400)
    body = await request.json()
    return {"html": _editor_html(art, body["st"], body.get("info") or {}, bool(body.get("neu")))}


@router.post("/api/abos/neu")
def api_abo_neu(art: str = "abo"):
    """Der Kasten fuer einen neuen Vertrag samt leerem Entwurf.

    POST, obwohl nichts geaendert wird: die Antwort haengt nur von `art` ab und
    ist keine Seite, die sich lesen laesst.
    """
    from finctl import abos as _ab

    if art not in _ab.ARTEN:
        return JSONResponse({"error": f"unbekannte Art {art}"}, status_code=400)
    c = conn()
    try:
        konten, kategorien = _auswahl(c)
    finally:
        c.close()
    st = abo_zustand({"id": "", "name": "", "kategorie": "", "weg": "", "notiz": "",
                      "konto": konten[0]["id"] if konten else "", "takt": 12, "faellig": ""})
    info = {"belege": [], "vorschlaege": [], "fruehere": [], "quelle": {}}
    return {"st": st, "info": info, "html": stueck(
        "_abo_neu.html", art=art, st=st, info=info, neu=True,
        konten=konten, kategorien=kategorien)}


@router.get("/api/abos/eingaenge")
def api_abo_eingaenge(q: str = ""):
    """Eingaenge, die als Rueckzahlung zugeordnet werden koennen."""
    from finctl import abos as _ab

    if len(q.strip()) < 2:
        return {"rows": []}
    c = conn()
    try:
        return {"rows": _ab.eingaenge(c, q)}
    finally:
        c.close()


@router.post("/api/abos/fruehere")
async def api_abo_fruehere(request: Request):
    """Fruehere Buchungen zu einem Entwurf, der noch nicht gespeichert ist.

    Beim Anlegen gibt es noch keinen abgelegten Beleg, aus dem die Seite die
    Gegenpartei kennen koennte -- die Liste kaeme sonst erst nach dem
    Speichern, also genau dann nicht, wenn sie beim Zuordnen hilft.
    """
    from finctl import abos as _ab

    body = await request.json()
    entwurf = {"kategorie": str(body.get("kategorie") or ""),
               "buchungen": [str(h) for h in body.get("buchungen") or []],
               "ignoriert": [str(h) for h in body.get("ignoriert") or []]}
    if not entwurf["kategorie"] or not entwurf["buchungen"]:
        return {"rows": []}
    c = conn()
    try:
        return {"rows": _ab.fruehere(c, entwurf)}
    finally:
        c.close()


@router.post("/api/abos")
async def api_abo_speichern(request: Request, art: str = "abo"):
    """Ein Vertrag anlegen oder ersetzen -- geprueft, bevor es geschrieben wird.

    Die Kennung gilt ueber beide Arten: die Prognose fuehrt Abos und
    Versicherungen in einer Liste.
    """
    from finctl import abos as _ab

    if art not in _ab.ARTEN:
        return JSONResponse({"error": f"unbekannte Art {art}"}, status_code=400)
    body = _ab.texte_lesen(await request.json())
    if not body.get("id") and body.get("name"):
        body["id"] = _ab.kennung_aus(body["name"])      # leer gelassen: aus dem Namen
    try:
        fremd = {a["id"] for andere in _ab.ARTEN if andere != art
                 for a in _ab.laden(art=andere)}
        if body.get("id") in fremd:
            raise ValueError(f"Kennung {body.get('id')} ist schon vergeben")
        _ab.speichern(body, art=art)
    except (ValueError, TypeError, KeyError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return {"ok": True, "id": body.get("id")}


@router.post("/api/abos/vorschau")
async def api_abo_vorschau(request: Request):
    """Termine und Kennung eines Entwurfs -- gerechnet vom Server, nichts gespeichert.

    `{"monat": "2026-05", "plus": 12}` gibt den Monat danach, `{"datum": ..., "plus": ...}`
    den Tag, `{"name": ...}` die Kennung, die beim Speichern entstuende.
    """
    from finctl import abos as _ab

    body = await request.json()
    try:
        out: dict = {}
        if body.get("monat"):
            out["monat"] = _ab.monat_plus(body["monat"], body.get("plus") or 0)
        if body.get("datum"):
            out["datum"] = _ab.datum_plus(body["datum"], body.get("plus") or 0)
        if body.get("name"):
            out["kennung"] = _ab.kennung_aus(body["name"])
    except ValueError as fehler:
        return JSONResponse({"error": str(fehler)}, status_code=400)
    return out


@router.post("/api/abos/{abo_id}/entfernen")
async def api_abo_entfernen(abo_id: str, art: str = "abo"):
    from finctl import abos as _ab

    if art not in _ab.ARTEN:
        return JSONResponse({"error": f"unbekannte Art {art}"}, status_code=400)
    _ab.entfernen(abo_id, art=art)
    return {"ok": True}
