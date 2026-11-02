"""Ziele: anlegen, messen, umbenennen, sortieren."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from finctl import bestaende
from finctl import notizen as _notizen
from finctl import person as _person
from finctl.dateien import yaml_lesen, yaml_schreiben
from finctl.forecast import jahre as _jm
from finctl.forecast import rentenluecke as _rl
from finctl.forecast import ziel_monat as _zm
from finctl.forecast import ziele as _ziele
from finctl.web.basis import (
    CONFIG_DIR,
    TEMPLATES,
    _slug,
    conn,
    notiz_felder,
)

router = APIRouter()


#: Die Datei der Ziele: eine, die die Seite ganz schreibt.
DATEI = "goals.yaml"


def _lesen(name: str) -> dict:
    """Eine Datei aus `config/`, leer wenn es sie nicht gibt."""
    pfad = CONFIG_DIR / name
    return (yaml_lesen(pfad) or {}) if pfad.exists() else {}


@router.get("/ziele", response_class=HTMLResponse)
def ziele(request: Request):
    """Declared targets and what is actually saved against them.

    The editable limits that used to sit below are gone. Every one of them was
    either a second way to say something a goal already says, or an editor
    that wrote to the wrong place:

    * Tagesgeld target and money owed to others are goals now, with a
      progress bar each. Keeping a second numeric field for them meant two
      sources for one figure and a silent drift between them.
    * The two percentage targets drove a SECOND Barista FIRE definition that
      never touched the bar.
    * The Dispo fields wrote accounts.dispo_threshold_cents, which
      `_floor_for` consults LAST and `finctl init` overwrites. Typing a number
      there did nothing visible and was gone by the next import. Konten writes
      the same limit to `forecast.yaml`, where it survives, and shows it back.
    * The salary floor is a planning input, not a target, and now lives with
      the scenarios.
    """
    return TEMPLATES.TemplateResponse(request, "ziele.html", ziele_kontext())


def ziele_kontext() -> dict:
    """Was die Seite Ziele zeigt: Karten, Kreuzung, Tempi. Auch der MCP-Zugang liest es."""
    goals = _ziele.aus_spec(_lesen(DATEI))
    today = date.today()
    c = conn()
    try:
        merged = bestaende.zusammenfuehren(c, _lesen("balances.yaml"))
        # Der Horizont folgt dem spaetesten Stichtag, statt die Ziele auf ihn
        # zurechtzustutzen -- und reicht bis ins erste volle Rentenjahr, aus
        # dem die Rentenluecke ihren Bedarf nimmt.
        #
        # Beide Tempi aus EINEM Einlesen: sie unterscheiden sich nur in der
        # Basis, und jedes weitere Lesen kostete ein Vielfaches einer Rechnung.
        je_tempo = _jm.eingaben_je_tempo(
            c, opening_cents=_ziele.liquid_cents(merged),
            toepfe=_ziele.toepfe(merged),
            depot_gewinn_cents=_ziele.depot_gewinn(merged),
            puffer_cents=_ziele.puffer_cents(goals),
            policen_je_konto=_ziele.policen_je_konto(merged),
            tagesgeld_je_konto=_ziele.tagesgeld_je_konto(merged))
        ende = max([2045, *_ziel_jahre(goals), *_rentenjahr()])
        lauf = _jm.rechnen(je_tempo["schnitt"], end_year=ende)
        lauf_juengst = _jm.rechnen(je_tempo["juengst"], end_year=ende)
        goals, luecke = _rl.mit_ziel(goals, lauf, je_tempo["schnitt"])
        fortschritt = _ziele.progress(goals, merged, today=today)
        schnitt = je_tempo["schnitt"]
        saetze = _ziele.saetze_aus(schnitt.annahmen, schnitt.policen)
        targets = [_karte(prog, goals, luecke, today,
                          _ziele.rate_mit_rendite(prog, merged, saetze, today))
                   for prog in fortschritt]
        _hochrechnung_anhaengen(targets, fortschritt, lauf, lauf_juengst,
                                merged, _ziele.puffer_cents(goals), _zm.Lauf(c))
        # Der Crossing Point: ab wann laufendes Einkommen OHNE Gehalt den
        # laufenden Bedarf deckt.
        #
        # Eine andere Frage als die Ziele darueber, und keine ersetzt die
        # andere: ein Zielbetrag sagt, ob man aufhoeren KANN -- Kapital, das
        # sich verzehren laesst --, der Crossing Point sagt, ab wann man nicht
        # mehr MUSS. Man kann das eine erreichen und das andere nie.
        naechstes = lauf.years[1].year if len(lauf.years) > 1 else lauf.base_year
        kreuzung = {
            "jahr": lauf.crossing_year,
            "jetzt": lauf.coverage_pct(naechstes),
            "jetzt_jahr": naechstes,
            "ende": lauf.coverage_pct(lauf.years[-1].year),
            "endjahr": lauf.years[-1].year,
            # Ohne Ausgaben deckt jedes Einkommen den Bedarf, und "ab 2026" waere eine
            # Behauptung ohne Grundlage.
            "bedarf": -sum(lauf.year(naechstes).blocks.get(b, 0) for b in _jm.BEDARF),
        }
        kontenamen = {r["id"]: (r["display_name"] or r["id"]) for r in c.execute(
            "SELECT id, display_name FROM accounts")}
    finally:
        c.close()
    arten = _basis_arten(merged)
    _basis_beschriften(targets, merged, arten, kontenamen)
    fenster = je_tempo["schnitt"].monat.fenster
    return {"targets": targets, "kreuzung": kreuzung,
            "horizont_jahr": lauf.years[-1].year,
            "basis_arten": arten,
            "tempo_schnitt": _jm.tempo_text("schnitt", fenster),
            "tempo_juengst": _jm.tempo_text("juengst", fenster),
            # Die Rentenluecke ist immer ein Ziel;
            # ohne Geburtsdatum sagt die Seite, was fehlt.
            "rentenluecke_fehlt": luecke is None}


def _karte(prog, goals: dict, luecke, today: date, zweite) -> dict:
    """Die Zeile eines Ziels: was es ist und wie weit der Balken ist.

    `zweite` ist die Rate mit Rendite oder None. Ihre Herleitung bleibt leer,
    wo es keine zweite Rate gibt -- daran erkennt die Vorlage, dass sie fehlt,
    und von "der Bestand reicht" (Rate None, Herleitung da) unterscheidet sie sich.
    """
    declared = next((g for g in (goals.get("ziele") or [])
                     if g.get("id") == prog.goal_id), {})
    return {
        "id": prog.goal_id, **notiz_felder(declared),
        "fest": bool(declared.get("fest")),
        "rechenweg": luecke.rechenweg if declared.get("fest") and luecke else [],
        "name": prog.name, "have": prog.have_cents,
        "basis": prog.basis, "basis_text": prog.basis_text,
        "ohne_wert": list(prog.ohne_wert), "abzug": prog.abzug_cents,
        "covered": prog.covered_cents, "uncovered": prog.uncovered_cents,
        "target": prog.target_cents, "pct": prog.pct,
        "due": prog.due.isoformat() if prog.due else None,
        "monthly": prog.monthly_needed_cents(today),
        "mit_rendite": zweite.cents if zweite else None,
        "mit_rendite_satz": zweite.satz if zweite else None,
        "mit_rendite_herleitung": list(zweite.herleitung) if zweite else [],
    }


def _hochrechnung_anhaengen(targets: list[dict], fortschritt: list, lauf, lauf_juengst,
                            merged: dict, puffer: int | None, monat) -> None:
    """Die Hochrechnung neben den Fortschritt. ZWEI Fragen, zwei Zahlen:
    der Balken sagt, was heute da ist, die Hochrechnung, wo es am
    Stichtag steht, wenn die Regeln halten.

    Beide zu zeigen ist der Punkt. Nur der Balken beantwortet nicht, ob
    man ankommt -- 11,6 % bei neunzehn Jahren Laufzeit sagt fuer sich
    genommen nichts. Nur die Hochrechnung verleitet dazu, ein kaum
    begonnenes Depot fuer halb fertig zu halten. Welches Ziel eine
    Hochrechnung bekommt und wie sie gemessen wird, steht bei
    `ziele.hochgerechnet`.

    Ein Ziel, dessen Stichtag im Horizont von `/konten` liegt, misst das Monatsmodell
    (`ziel_monat`): Seine Klammern wirken am Termin, nicht erst im Jahresmittel. Die Karte
    sagt unter `modell`, welches Modell sie misst. Das Tempo "Juengst" kennt nur die
    Jahresrechnung.
    """
    for t, prog in zip(targets, fortschritt, strict=True):
        h, modell = _zm.messen(prog, lauf, merged, puffer, monat)
        t["modell"] = modell
        if h is None:
            t["projiziert"] = t["projiziert_jahr"] = t["juengst"] = None
            t["projiziert_pct"] = 0.0
            continue
        t["projiziert"], t["projiziert_jahr"], t["projiziert_pct"] = h.cents, h.jahr, h.pct
        # Gegen denselben Zielbetrag: auch der der Rentenluecke, die ihr
        # Kapital aus dem Bedarf der Schnitt-Rechnung nimmt.
        hj = (_ziele.hochgerechnet(lauf_juengst, prog)
              if modell == _zm.JAHRESRECHNUNG else None)
        t["juengst"] = {"projiziert": hj.cents, "pct": hj.pct} if hj else None


def _basis_arten(merged: dict) -> list[dict]:
    """Woraus eine Basis bestehen KANN: die Arten, die der Haushalt hat."""
    arten, gesehen = [], set()
    for row in merged["balances"]:
        art = _ziele.art(row.get("kind"))
        if art and art not in gesehen:
            gesehen.add(art)
            arten.append({"id": art,
                          "label": "alle " + _ziele.BASIS_LABEL.get(art, art)})
    return arten


def _basis_beschriften(targets: list[dict], merged: dict, arten: list[dict],
                       kontenamen: dict[str, str]) -> None:
    """Statt der Kennungen die Namen, die die Seite sonst zeigt.

    Die Konten heissen im Dashboard anders als in balances.yaml -- dort
    steht die Kennung, hier soll der Anzeigename stehen. Ein Haken, den man
    setzt, muss so heissen wie das, was man meint.

    Einzelne Positionen bleiben in goals.yaml moeglich und werden richtig
    gerechnet -- die SEITE bietet sie nur nicht an. Zwoelf Haken fuer eine
    Frage, die mit fuenf beantwortet ist, sind keine bessere Bedienung.
    Und ein Notgroschen ist oft "diese vier Konten" und nicht "alles
    Tagesgeld": die Basis darf aus beidem bestehen.
    """
    beschriftung = {
        str(row.get("account_id") or row.get("name") or "").lower():
        (kontenamen.get(str(row.get("account_id") or "").lower())
         or row.get("name") or row.get("account_id"))
        for row in merged["balances"] if row.get("account_id") or row.get("name")}
    beschriftung.update({a["id"]: a["label"].removeprefix("alle ") for a in arten})
    for t in targets:
        if t["basis"]:
            t["basis_text"] = " + ".join(beschriftung.get(k, k) for k in t["basis"])


#: Kennungen, die /api/ziel nicht bearbeitet: keine -- oder die gerechnete
#: Rentenluecke, die sonst als eigenes Ziel ein zweites Mal entstuende.
_ID_FEHLER = {"": "id fehlt",
              "rentenluecke": "Die Rentenlücke wird gerechnet, nicht eingetragen"}


def _ziel_jahre(goals: dict) -> list[int]:
    return [int(str(g["stichtag"])[:4]) for g in goals.get("ziele") or []
            if g.get("stichtag")]


def _rentenjahr() -> list[int]:
    """Das erste volle Rentenjahr -- bis dorthin muss die Rechnung reichen."""
    beginn = _person.rentenbeginn()
    return [beginn.year + 1] if beginn else []


@router.post("/api/ziel")
async def api_ziel(request: Request):
    """Ein Ziel anlegen, aendern oder loeschen: Betrag, Stichtag und die Notiz daneben.

    Die Begruendung ist ein eigenes Feld des Ziels (`notiz`) und kein Kommentar in der
    Datei, denn sie ist das, was am schnellsten verfaellt. Ein Ziel ohne Notiz ist nach
    einem Jahr nicht mehr nachzuvollziehen: Niemand weiss, dass die Zahl aus den
    Jahresausgaben mal 25 kam, und jemand "korrigiert" sie.

    Gespeichert wird das ganze Ziel in `goals.yaml`. Gleiche Eingaben aendern nichts: Was
    die Seite zeigt, ohne dass es in der Datei steht (der Name, der Betrag eines
    Notgroschens ohne Betrag), wird erst dann geschrieben, wenn jemand es aendert.
    """
    body = await request.json()
    path = CONFIG_DIR / DATEI
    spec = _lesen(DATEI)
    ziele = [g for g in spec.get("ziele") or [] if isinstance(g, dict)]
    ids = {str(g.get("id")) for g in ziele}

    neu = bool(body.get("neu"))
    name = str(body.get("name") or "").strip()
    if neu:
        if not name:
            return JSONResponse({"error": "Name fehlt"}, status_code=400)
        if body.get("cents") in (None, ""):
            return JSONResponse({"error": "Betrag fehlt"}, status_code=400)
        gid = _slug(name)
        if gid in ids or gid in _notizen.RESERVIERT:
            return JSONResponse({"error": f"„{gid}“ ist schon vergeben oder für Notizen "
                                          "reserviert"}, status_code=400)
    else:
        gid = (body.get("id") or "").strip()
        fehler = _ID_FEHLER.get(gid)
        if fehler:
            return JSONResponse({"error": fehler}, status_code=400)
        if gid not in ids:
            return JSONResponse({"error": f"unbekanntes Ziel {gid}"}, status_code=404)
    when = str(body.get("stichtag") or "").strip()
    if when:
        try:
            date.fromisoformat(when)
        except ValueError:
            return JSONResponse({"error": f"Stichtag {when}: bitte als 2035-12-31"},
                                status_code=400)

    if body.get("loeschen"):
        # Das Ziel faellt samt seiner Notiz aus der Datei.
        ziele = [g for g in ziele if str(g.get("id")) != gid]
    else:
        eintrag = next((g for g in ziele if str(g.get("id")) == gid), None)
        if eintrag is None:
            eintrag = {"id": gid, "name": name[:80]}
            ziele.append(eintrag)
        angezeigt = next((g for g in _ziele.aus_spec({"ziele": ziele})["ziele"]
                          if str(g.get("id")) == gid), eintrag)
        _ziel_aendern(eintrag, angezeigt, body)
    yaml_schreiben(path, {**spec, "ziele": ziele})
    return {"ok": True, "id": gid}


def _tag(wert) -> str:
    """Ein Stichtag als JJJJ-MM-TT, ob die Datei ihn als Datum oder als Text haelt."""
    return str(wert or "").strip()[:10]


def _ziel_aendern(eintrag: dict, angezeigt: dict, body: dict) -> None:
    """Die Felder aus `body` ins Ziel. `angezeigt` ist, was die Seite vorher zeigte.

    Nur was sich gegenueber der Anzeige aendert, wird geschrieben: Die Seite schickt jedes Feld
    mit, auch die, die sie aus einer Vorgabe zeigt.
    """
    if body.get("cents") not in (None, "") and int(body["cents"]) != angezeigt.get("cents"):
        eintrag["cents"] = int(body["cents"])
    _ziel_messen(eintrag, body)
    if "notiz" in body:
        text = _notizen.eingabe(body.get("notiz"))
        # Die Vorgabe eines Notgroschens ist keine Notiz des Haushalts.
        if text != _notizen.eingabe(angezeigt.get("notiz")):
            _notizen.setzen(eintrag, text)
    # Umbenennen aendert die Beschriftung, nicht die Kennung: an der haengen die Reihenfolge
    # und die Stellen, die ein Ziel im Code suchen. Ein leeres Feld loescht den Namen nicht --
    # sonst stuende ein Ziel ohne Bezeichnung in der Liste. Der Name, der nur die Kennung ist,
    # wird nicht in die Datei geschrieben.
    neuer = str(body.get("name") or "").strip()[:80]
    if neuer and neuer != str(angezeigt.get("name") or angezeigt.get("id")):
        eintrag["name"] = neuer


def _ziel_messen(eintrag: dict, body: dict) -> None:
    """Gegen was und bis wann ein Ziel misst: `basis` und `stichtag`."""
    if "basis" in body:
        # Leere Auswahl heisst "gegen alles Liquide", also faellt der Eintrag weg, statt als
        # leere Liste stehenzubleiben -- sonst zaehlte das Ziel gegen nichts. Dieselben Arten
        # in anderer Reihenfolge sind dieselbe Basis.
        gewaehlt = [str(x).strip().lower() for x in body.get("basis") or [] if str(x).strip()]
        bisher = [str(x).strip().lower() for x in eintrag.get("basis") or []]
        if sorted(gewaehlt) != sorted(bisher):
            if gewaehlt:
                eintrag["basis"] = gewaehlt
            else:
                eintrag.pop("basis", None)
    if "stichtag" in body:
        wann = str(body.get("stichtag") or "").strip()
        if _tag(wann) != _tag(eintrag.get("stichtag")):
            if wann:
                eintrag["stichtag"] = wann
            else:
                eintrag.pop("stichtag", None)


@router.post("/api/ziele/reihenfolge")
async def api_ziele_reihenfolge(request: Request):
    """Die auf /ziele gezogene Reihenfolge: `reihenfolge` in `goals.yaml`."""
    body = await request.json()
    ids = [str(x).strip() for x in (body.get("ids") or []) if str(x).strip()]
    if not ids or len(ids) != len(set(ids)):
        return JSONResponse({"error": "Reihenfolge ohne Ziele oder mit Doppelten"},
                            status_code=400)
    spec = _lesen(DATEI)
    yaml_schreiben(CONFIG_DIR / DATEI, {**spec, "reihenfolge": ids})
    return {"ok": True}
