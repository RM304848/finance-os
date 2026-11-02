"""Konten und Bestaende: Untergrenzen, Rollen, getippte Staende."""

from __future__ import annotations

import datetime as _dtm

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from finctl import konten as _kn
from finctl import notizen as _notizen
from finctl.bestaende import NOTIZ_ALT, RUECKKAUF_FELDER
from finctl.dateien import yaml_schreiben
from finctl.ledger import kontostand as _ks
from finctl.web import diagramm as _dg
from finctl.web.basis import (
    CONFIG_DIR,
    TEMPLATES,
    conn,
    lies_texte,
    umleiten,
)
from finctl.web.verkauf import _verkaeufe_aus_plan

router = APIRouter()

#: Geld, das am selben Tag verfuegbar ist. Ein Depot zaehlt in der Summe aller
#: Konten nicht mit: was dort liegt, muss erst verkauft werden.
LIQUIDE = ("giro", "tagesgeld")
#: Die Wahl "alle Konten zusammen" im Verlauf.
ZUSAMMEN = "zusammen"


def _monat(text: str) -> _dtm.date:
    return _dtm.date.fromisoformat(text[:7] + "-01")


def _diagramm_ohne_objekt(ob: dict):
    """Gemessen und vorausgerechnet in einem Bild: der Bruch zwischen beiden bleibt sichtbar."""
    ziel = ob["ziel_cents"]
    monate = ob["monate"]
    balken = [_dg.Balken(m.cents, "--muted" if not m.gemessen
                         else ("--bad" if m.cents < ziel else "--accent"),
                         "gemessen" if m.gemessen else "vorausgerechnet") for m in monate]
    legende = [("gemessen", "--accent"), ("vorausgerechnet", "--muted")]
    if any(b.farbe == "--bad" for b in balken):
        legende.append(("gemessen, unter Ziel", "--bad"))
    return _dg.saeulen(
        f"Cashflow ohne {ob['label']}", [m.monat for m in monate], "Cashflow", balken,
        legende=legende, grenzen=[_dg.Grenze("Ziel", ziel, "--ink")] if ziel else [],
        zusatz=[_dg.Linie(ob["daneben"]["label"], "--muted",
                          [m.daneben_cents for m in monate])]
        if ob["daneben"] and any(m.daneben_cents for m in monate) else [],
        untertitel="je Monat, in €")


def _diagramm_konto(v: dict):
    """Tiefpunkt und Endstand eines Kontos gegen seine Grenzen."""
    rows = v.get("rows") or []
    titel = f"Verlauf {v['id']}"
    if v.get("error") or not rows:
        return _dg.leer(titel, "Keine Daten für dieses Konto.")
    grenzen = [_dg.Grenze("Untergrenze", v.get("dispo_threshold_cents") or 0, "--bad",
                          flaeche=True)]
    if v.get("ceiling_cents"):
        grenzen.append(_dg.Grenze("Deckel", v["ceiling_cents"], "--warn"))
    unter = frozenset(i for i, r in enumerate(rows) if r["breaches_dispo"])
    return _dg.linien(
        titel, [_monat(r["month"]) for r in rows],
        [_dg.Linie("nach Kosten", "--accent", [r["trough_cents"] for r in rows],
                   art="beides", auffaellig=unter),
         _dg.Linie("nach Gehalt", "--muted", [r["closing_cents"] for r in rows])],
        grenzen=grenzen, mit_null=True, auffaellig_name="unter Grenze",
        untertitel="Tiefpunkt im Monat und Stand am Monatsende, in €")


def _diagramm_zusammen(views: list[dict]):
    """Reicht das liquide Geld fuer alle Untergrenzen?

    Die Linie ist die Summe der Tiefpunkte aller Giro- und Tagesgeldkonten; die
    Grenze die Summe der Untergrenzen ALLER Konten -- gedeckt sein muessen auch
    die uebrigen.
    """
    mit = [v for v in views if not v.get("error") and v.get("rows")]
    grenze = sum(v.get("dispo_threshold_cents") or 0 for v in mit)
    summen: dict[str, int] = {}
    for v in mit:
        if v.get("account_type") in LIQUIDE:
            for r in v["rows"]:
                summen[r["month"]] = summen.get(r["month"], 0) + r["trough_cents"]
    monate = sorted(summen)
    werte = [summen[m] for m in monate]
    return _dg.linien(
        "Giro + Tagesgeld zusammen", [_monat(m) for m in monate],
        [_dg.Linie("Giro + Tagesgeld", "--accent", werte, art="beides",
                   auffaellig=frozenset(i for i, w in enumerate(werte) if w < grenze))],
        grenzen=[_dg.Grenze("alle Untergrenzen", grenze, "--bad", flaeche=True)],
        kappen=True, auffaellig_name="unter den Untergrenzen",
        untertitel="Summe der Tiefpunkte, in €")


def _verlauf(views: list[dict], konto: str) -> tuple[str, object]:
    """Das gewaehlte Konto und sein Diagramm.

    Ohne Wahl das Konto mit dem tiefsten Punkt: die Seite soll mit dem Problem
    aufmachen, nicht mit dem alphabetisch ersten Konto.
    """
    ids = [v["id"] for v in views]
    if konto not in ids and konto != ZUSAMMEN:
        mit_tief = [v for v in views
                    if not v.get("error") and v.get("worst_trough_cents") is not None]
        tiefstes = min(mit_tief, key=lambda v: v["worst_trough_cents"], default=None)
        konto = tiefstes["id"] if tiefstes else (ids[0] if ids else ZUSAMMEN)
    if konto == ZUSAMMEN:
        return konto, _diagramm_zusammen(views)
    return konto, _diagramm_konto(next(v for v in views if v["id"] == konto))


def _lade_kredite() -> list[dict]:
    """Die Kredite aus `loans.yaml`: Auswahl der Untergrenze aus einem Kredit."""
    from finctl.realestate.loan import lade_kredite

    return [k for k in lade_kredite(CONFIG_DIR) if k.get("id")]


@router.get("/konten", response_class=HTMLResponse)
# 12 als Literal, weil `ops` hier bewusst erst in den Funktionen importiert
# wird. Die Begruendung fuer die beiden Horizonte steht bei ops.HORIZON_LONG.
def konten(request: Request, months: int = 12, konto: str = ""):
    """Will any account dip below its floor, and in which month.

    The household view says whether there is enough money in total. It cannot
    say whether it is in the right account on the right day, and that is what
    a Dispo actually costs you. This is the per-account intra-month trough --
    "nach Kosten", not the month-end balance, because costs land at the start
    of a month and salary at the end.
    """
    from finctl import ops
    from finctl.forecast.stichtag import stichtag as _stichtag

    c = conn()
    try:
        views = ops.household_accounts(c, months=months)
        # Ab wann gerechnet statt gemessen wird.
        #
        # Derselbe Stichtag, an dem die Prognose beginnt: das Ende des letzten
        # Monats, den alle Konten ganz abdecken. Spaetere Buchungen zaehlen
        # nicht, auch wenn schon ein Auszug bis zum 4. da ist.
        gemessen_bis = _stichtag(c).isoformat()
        # Ob sich der Haushalt ohne das Objekt traegt -- gemessen und aus denselben
        # Posten vorausgerechnet, die unten je Konto stehen.
        from finctl import kontenregeln as _krk
        from finctl.forecast import ohne_objekt as _ob

        ohne_objekt = _ob.kennzahl(c, views, _krk.wirksam())
    finally:
        c.close()

    # Je Konto, was gilt.
    from finctl import kontenregeln as _kr

    regeln = _kr.wirksam()
    for v in views:
        rolle = dict((regeln.get("account_roles") or {}).get(v["id"]) or {})
        rolle["budget_cents"] = (regeln.get("account_budgets") or {}).get(v["id"])
        v["regel"] = rolle
    kredit_optionen = [(str(k["id"]), str(k.get("name") or k["id"])) for k in _lade_kredite()]
    rollen_namen = ["operating", "consumption", "budget", "servicing", "savings",
                    "durchlaufend"]

    order = {"operating": 0, "consumption": 1, "budget": 2,
             "servicing": 3, "savings": 4}
    views.sort(key=lambda v: (order.get(v.get("role"), 9), v["id"]))
    # Die Regel je Konto: den Bearbeitungsbereich der Tabelle gibt es nur
    # einmal, und er wird beim Oeffnen aus diesen Werten gefuellt. Die Monate
    # gehen nicht mit -- das Diagramm zeichnet der Server.
    konten_daten = [{"id": v["id"],
                     "dispo_threshold_cents": v.get("dispo_threshold_cents"),
                     "regel_untergrenze_cents": v.get("regel_untergrenze_cents"),
                     "notgroschen_cents": v.get("notgroschen_cents"),
                     "ceiling_cents": v.get("ceiling_cents"),
                     "regel": v.get("regel") or {},
                     "breach_months": v.get("breach_months") or [],
                     "over_ceiling_months": v.get("over_ceiling_months") or [],
                     "idle_cents": v.get("idle_cents") or 0}
                    for v in views]
    konto, verlauf = _verlauf(views, konto)
    # Ein geplanter Verkauf im Horizont ist hier NICHT eingerechnet -- er wirkt
    # nur in der Jahresrechnung. Das muss dastehen, sonst laeuft die Rate auf
    # dieser Seite weiter, ohne dass jemand weiss, warum.
    c = conn()
    try:
        _grenze = _dtm.date.today().replace(day=1)
        _bis = _dtm.date(_grenze.year + (_grenze.month - 1 + months) // 12,
                         (_grenze.month - 1 + months) % 12 + 1, 1)
        verkauf_hinweis = [v for v in _verkaeufe_aus_plan(c).values()
                           if v.ab < _bis]
        from finctl.forecast import konten as _fk

        objekt_hinweis = _fk.objekte_ohne_konto(c)
    finally:
        c.close()
    return TEMPLATES.TemplateResponse(request, "konten.html", {
        "verkauf_hinweis": verkauf_hinweis, "objekt_hinweis": objekt_hinweis,
        "ohne_objekt": ohne_objekt,
        "policen": policen_im_notfall(),
        "rollen_namen": rollen_namen, "rollen_text": ROLLEN_TEXT,
        "kredit_optionen": kredit_optionen,
        "views": views, "konten_daten": konten_daten, "gemessen_bis": gemessen_bis,
        "konto": konto, "verlauf": verlauf,
        "konto_optionen": [(ZUSAMMEN, "Giro + Tagesgeld zusammen")]
        + [(v["id"], v["id"]) for v in views],
        "ohne_objekt_diagramm": _diagramm_ohne_objekt(ohne_objekt),
        # Das Endjahr wird gerechnet, nicht getippt: im Text stand "2026 +
        # horizon_long // 12", und die 2026 darin waere im Januar falsch
        # gewesen, ohne dass jemand die Datei anfasst.
        "horizont_jahr": _dtm.date.today().year + ops.HORIZON_LONG // 12,
        "horizon_long": ops.HORIZON_LONG, "horizon_default": ops.HORIZON_DEFAULT,
        "months": months})


def policen_im_notfall() -> list[dict]:
    """Je Position der Bestandsart Rentenversicherung: Policenwert und Notfallwert.

    Der Notfallwert (`bestaende.notfallwert`) ist nur eine Anzeige. Er zaehlt
    weder zum Notgroschen noch zum liquiden Vermoegen: die Zeile traegt ihn, sonst
    nichts. Eine Police ohne Rueckkaufswert steht mit leerem Notfallwert da, damit
    sichtbar bleibt, dass er fehlt.
    """
    from finctl import assumptions as _ann
    from finctl import bestaende as _best
    from finctl.forecast.ziele import art as _art

    steuersatz = _ann.vorabpauschale()[1]
    c = conn()
    try:
        merged = _best.zusammenfuehren(c, _best.lesen(CONFIG_DIR / _best.DATEI))
    finally:
        c.close()
    out = []
    for z in merged["balances"]:
        if _art(z.get("kind")) != "rentenversicherung":
            continue
        n = _best.notfallwert(z, steuersatz)
        out.append({"key": _best.schluessel(z), "name": z.get("name") or z.get("account_id"),
                    "cents": z.get("cents"), "as_of": str(z.get("as_of") or ""),
                    "notfall": n, "herleitung": notfall_herleitung(n, z, steuersatz) if n else ""})
    return out


def notfall_herleitung(n, zeile: dict, steuersatz: float) -> str:
    """Die Rechnung hinter einem Notfallwert, als Satz fuer den Tooltip der Zeile."""
    from finctl.forecast.herkunft import eur_genau as eur

    def prozent(satz: float) -> str:
        # Drei Stellen, ohne Nullen am Ende: zwei Stellen rundeten den Satz.
        return f"{satz * 100:.3f}".rstrip("0").rstrip(".").replace(".", ",") + " %"

    teile = []
    if n.quote is not None:
        teile.append(f"Rückkaufswert der Mitteilung {eur(n.mitteilung_cents)} (Stand {n.stand}) "
                     f"× Policenwert {eur(int(zeile['cents']))} ÷ Policenwert der Mitteilung "
                     f"{eur(n.basis_cents)} = {eur(n.rueckkauf_cents)}")
    else:
        teile.append(f"Rückkaufswert {eur(n.rueckkauf_cents)} (Stand {n.stand})")
    if n.ertrag_cents is None:
        teile.append(f"eingezahlt unbekannt: {prozent(steuersatz)} Steuer auf den ganzen "
                     f"Rückkaufswert, der Notfallwert ist eine Untergrenze")
    else:
        teile.append(f"{prozent(steuersatz)} Steuer auf den Ertrag {eur(n.ertrag_cents)} "
                     f"(Rückkaufswert − eingezahlt {eur(n.eingezahlt_cents)}, nicht unter 0) "
                     f"= {eur(n.steuer_cents)}")
    if n.verhaeltnis_fehlt:
        teile.append("der Policenwert ist neuer als die Mitteilung, ihr Policenwert fehlt: "
                     "der Rückkaufswert steht auf seinem Stand")
    return "; ".join(teile) + f"; Notfallwert {eur(n.cents)}"


@router.get("/kontenregister")
def kontenregister(request: Request):
    """Das Register steht in der Einrichtung, Schritt 3 -- dort, wo man ein
    Konto zum ersten Mal anlegt, und nicht auf einer zweiten Seite daneben."""
    return umleiten(request, "/einrichtung", anker="konten")


@router.post("/api/floor/{account_id}")
async def api_floor(account_id: str, request: Request):
    """Set an account's warning floor.

    Die Untergrenze steht in `forecast.yaml`, am Eintrag des Kontos (`account_roles.<konto>`),
    wie jede andere Kontenregel. Fruehere Stationen waren die Tabelle `settings` und
    eine zweite Datei; seit Schritt 5 (N.3f) gibt es nur noch die eine Datei, denn die
    Datenbank ist aus ihr ableitbar und die Zahl steht in keinem Auszug.
    """
    from finctl import kontenregeln as _kr

    body = await request.json()
    try:
        cents = int(round(float(body["cents"])))
    except (KeyError, TypeError, ValueError):
        return JSONResponse({"error": "cents required"}, status_code=400)
    c = conn()
    try:
        if not c.execute("SELECT 1 FROM accounts WHERE id = ?", (account_id,)).fetchone():
            return JSONResponse({"error": "unknown account"}, status_code=404)
    finally:
        c.close()
    _kr.setzen(account_id, {"floor_cents": cents})
    return {"ok": True, "cents": cents}


#: Die Felder einer Konto-Regel, die keine Notiz sind (Rolle, Konto zum Abraeumen), sind
#: Kennungen und bleiben kurz. Die Notiz hat ihre Grenze in `notizen.MAX`.
FELD_MAX = 200


@router.post("/api/konto/{account_id}")
async def api_konto(account_id: str, request: Request):
    """Die Kontenregeln eines Kontos setzen: Zweck, Rolle, Grenzen, Budget.

    Sie sind keine Prognoseannahme, sondern die Regel, wie Geld zwischen den
    eigenen Konten wandert -- deshalb stehen sie hier und nicht auf
    /annahmen. Alles geht nach forecast.yaml, die Untergrenze eingeschlossen.
    """
    from finctl import kontenregeln as _kr

    body = await request.json()
    c = conn()
    try:
        konto = c.execute("SELECT dispo_threshold_cents FROM accounts WHERE id = ?",
                          (account_id,)).fetchone()
    finally:
        c.close()
    if konto is None:
        return JSONResponse({"error": "unknown account"}, status_code=404)

    felder: dict = {}
    for feld, art in _kr.FELDER.items():
        if feld not in body:
            continue
        wert = body[feld]
        if art == "cents":
            felder[feld] = None if wert in (None, "") else int(wert)
        elif art == "schalter":
            felder[feld] = None if wert is None else bool(wert)
        elif art == "kredit":
            # Die Kennung eines Kredits; `True` kommt nur von einem alten Aufruf (kein Kredit).
            felder[feld] = wert if wert is True else (str(wert).strip()[:FELD_MAX] or None
                                                      if isinstance(wert, str) else None)
        else:
            text = _notizen.eingabe(wert) if feld == "note" else str(wert).strip()[:FELD_MAX]
            felder[feld] = text or None
    if "budget_cents" in body:
        felder["budget_cents"] = (None if body["budget_cents"] in (None, "")
                                  else int(body["budget_cents"]))
    # Ein Kredit, der in loans.yaml nicht steht, ist keine Untergrenze. Die Kennung, die schon
    # an der Regel steht, darf bleiben: Speichern ohne Aenderung schreibt nichts, auch wenn
    # der Kredit inzwischen fehlt.
    gewaehlt = felder.get("floor_from_loan")
    if isinstance(gewaehlt, str) and gewaehlt != str(
            _kr.wirksam()["account_roles"].get(account_id, {}).get("floor_from_loan")) \
            and gewaehlt not in {str(k.get("id")) for k in _lade_kredite()}:
        return JSONResponse({"error": f"Kein Kredit „{gewaehlt}“ in loans.yaml"},
                            status_code=400)
    # Die Karte schickt die Untergrenze, die sie zeigt. Zeigt sie die Vorgabe (die Schwelle
    # des Kontos), weil die Datei keine nennt, ist das Speichern ohne Aenderung kein Anlass,
    # sie einzutragen.
    if felder.get("floor_cents") == (konto["dispo_threshold_cents"] or 0) \
            and _kr.wirksam()["account_roles"].get(account_id, {}).get("floor_cents") is None:
        felder.pop("floor_cents")
    return {"ok": True, "regel": _kr.setzen(account_id, felder)}


@router.post("/api/konto-neu")
async def api_konto_neu(request: Request):
    """Ein Konto anlegen -- der erste Schritt, den es bisher nur im Editor gab.

    Ohne Konto kein Import, ohne Import kein Hauptbuch und keine Warnung vor
    dem Tiefpunkt. Das war die Stelle, an der ein neuer Nutzer eine YAML-Datei
    von Hand schreiben musste, bevor die App ihm irgendetwas zeigen konnte.
    """

    body = await request.json()
    konto = {f: body.get(f) for f in _kn.FELDER if body.get(f) not in (None, "")}
    for feld in ("id", "display_name", "institution", "statement_folder"):
        if konto.get(feld):
            konto[feld] = str(konto[feld]).strip()
    if body.get("dispo_threshold_cents") not in (None, ""):
        try:
            konto["dispo_threshold_cents"] = int(body["dispo_threshold_cents"])
        except (TypeError, ValueError):
            return JSONResponse({"error": "Schwelle: keine Zahl"}, status_code=400)

    c = conn()
    try:
        angelegt = _kn.anlegen(c, konto)
    except ValueError as fehler:
        return JSONResponse({"error": str(fehler)}, status_code=400)
    finally:
        c.close()
    return {"ok": True, "konto": angelegt,
            "ordner": str(_kn.auszugsordner(angelegt)),
            "ohne_backup": _kn.eigener_pfad(angelegt)}


@router.post("/api/konto-stammdaten/{account_id}")
async def api_konto_stammdaten(account_id: str, request: Request):
    """Die Angaben eines bestehenden Kontos aendern: Namen, Einlesen, Schwelle, Schliessen, Notiz.

    Die Kennung bleibt. Bisher legte die Einrichtung ein Konto an und liess es danach in
    Ruhe; ein Tippfehler im Namen oder ein gekuendigtes Konto ging nur im Texteditor.
    """
    body = lies_texte(await request.json(), {"dispo_threshold_cents": "betrag"})
    felder = {k: body[k] for k in (*_kn.AENDERBAR, "notiz") if k in body}
    c = conn()
    try:
        try:
            eintrag = _kn.aendern(c, account_id, felder)
        except ValueError as fehler:
            return JSONResponse({"error": str(fehler)}, status_code=400)
    finally:
        c.close()
    return {"ok": True, "konto": eintrag, "ordner": str(_kn.auszugsordner(eintrag)),
            "ohne_backup": _kn.eigener_pfad(eintrag)}


#: Die Rollen heissen in accounts- und forecast-Konfiguration englisch; auf der
#: Seite stehen sie deutsch (oberflaeche-auf-deutsch). Gespeichert wird weiter
#: der Schluessel.
ROLLEN_TEXT = {"operating": "Betrieb", "consumption": "Konsum", "budget": "Budget",
               "servicing": "Kreditbedienung", "savings": "Sparen",
               "durchlaufend": "durchlaufend"}


@router.get("/bestaende")
def bestaende(request: Request):
    """Die Bestaende sind Zeilen des Monatsabschlusses: dort wird geprueft,
    welcher Stand veraltet ist, und in derselben Zeile wird er abgelegt."""
    return umleiten(request, "/monatsabschluss", anker="konten")


def bestaende_daten() -> dict:
    """Holdings the statements cannot see: depots, equities, crypto, pensions.

    Everything here is stated rather than parsed, which is exactly why it
    needs a screen. A depot value that is only editable in YAML gets updated
    once, at the moment it is written down, and is then quietly wrong for a
    year -- while the goal progress that depends on it keeps looking precise.

    The as-of date is shown per row and deliberately not defaulted to today:
    a stale figure that says when it went stale is usable, one that claims to
    be current is not.
    """
    from datetime import date as _date

    from finctl import bestaende as _best

    spec = _best.lesen(CONFIG_DIR / _best.DATEI)

    # Grouped by kind, because that is how they are maintained: a depot has one
    # statement with one total, a policy has its own Standmitteilung with its
    # own maturity. Listing depot holdings individually and lumping the two
    # policies into one line had it exactly backwards.
    # Krypto steht bei den Depots (finctl/forecast/ziele.py, GLEICHE_ART).
    from finctl.forecast.ziele import art as _art

    labels = {"giro": "Girokonten", "tagesgeld": "Tagesgeld", "depot": "Depots",
              "rentenversicherung": "Rentenversicherungen", "": "Sonstiges"}
    order = ["giro", "tagesgeld", "depot", "rentenversicherung", ""]

    c = conn()
    try:
        merged = _best.zusammenfuehren(c, spec)
    finally:
        c.close()
    rows = []
    for item in merged["balances"]:
        key = item.get("account_id") or item.get("name") or ""
        aus_auszug = bool(item.get("aus_auszug"))
        rows.append({
            "key": key,
            "label": item.get("name") or item.get("account_id"),
            "account_id": item.get("account_id") or "",
            "kind": _art(item.get("kind")),
            "cents": item.get("cents"),
            "gewinn_cents": item.get("gewinn_cents"),
            "rueckkauf": _best.rueckkauf(item),
            "as_of": str(item.get("as_of") or ("" if aus_auszug else spec.get("as_of"))
                         or ""),
            # Konten mit Auszug: Wert und Stichtag belegt, nicht aenderbar.
            "aus_auszug": aus_auszug,
            "auszug_bis": item.get("auszug_bis") or "",
            "note": (item.get("note") or "").strip(),
        })

    groups = []
    for kind in order:
        members = [r for r in rows if r["kind"] == kind]
        if not members:
            continue
        stated = [r["cents"] for r in members if r["cents"] is not None]
        groups.append({"kind": kind, "label": labels.get(kind, kind),
                       "rows": members, "total": sum(stated),
                       "unknown": len(members) - len(stated)})

    today = _date.today().isoformat()
    stale = [r for r in rows if not r["aus_auszug"] and r["as_of"] and r["as_of"] < today[:8] + "01"
             and r["as_of"][:7] < today[:7]]
    return {"rows": rows, "groups": groups, "today": today, "stale": len(stale),
            # Verbindlichkeiten werden nicht mehr hier gepflegt, sondern als
            # Verpflichtung in der Planung. Was noch in balances.yaml steht,
            # zieht weiter ab -- der Abschnitt sagt das, bis es gestrichen ist.
            "obligations": merged["obligations"]}


def _leer_heisst_weg(entry: dict, feld: str, wert) -> None:
    """Ein leerer Wert nimmt das Feld aus dem Eintrag, statt ihn leer zu speichern."""
    if wert in (None, ""):
        entry.pop(feld, None)
    else:
        entry[feld] = wert


def _tag(wert) -> str:
    """Ein Datum als JJJJ-MM-TT, ob die Datei es als Datum oder als Text haelt."""
    return str(wert or "").strip()[:10]


def _bestand_aendern(entry: dict, body: dict) -> bool:
    """Die Felder aus `body` in den Eintrag der Position. `False`, wenn der Betrag fehlt.

    Ein leerer Gewinn heisst "nicht bekannt": dann gilt der Wert als Einstand. Ein Datum, das
    dasselbe sagt wie das in der Datei, aendert nichts.
    """
    if "note" in body:
        _notizen.setzen(entry, _notizen.eingabe(body.get("note")), alt=NOTIZ_ALT)
    if "cents" in body:
        if body.get("cents") in (None, ""):
            return False
        entry["cents"] = int(body["cents"])
    elif not any(f in body for f in ("note", "gewinn_cents", *RUECKKAUF_FELDER)):
        return False
    if body.get("as_of") and _tag(body["as_of"]) != _tag(entry.get("as_of")):
        entry["as_of"] = str(body["as_of"])
    if "gewinn_cents" in body:
        wert = body["gewinn_cents"]
        _leer_heisst_weg(entry, "gewinn_cents", None if wert in (None, "") else int(wert))
    _rueckkauf_eintragen(entry, body)
    return True


def _rueckkauf_eintragen(entry: dict, body: dict) -> None:
    """Rueckkaufswert, eingezahlte Beitraege und die Policenwerte der Mitteilung.

    Ein leerer Rueckkaufswert nimmt alle vier Felder aus dem Eintrag: ohne ihn
    sind die anderen Angaben nichts wert. Ein leeres anderes Feld heisst "nicht
    bekannt".
    """
    if "rueckkauf_cents" in body and body["rueckkauf_cents"] in (None, ""):
        for feld in RUECKKAUF_FELDER:
            entry.pop(feld, None)
        return
    # Ein anderer Rueckkaufswert ist eine neue Mitteilung; der Policenwert der alten gilt nicht.
    if ("rueckkauf_cents" in body and "rueckkauf_policenwert_cents" not in body
            and body["rueckkauf_cents"] != entry.get("rueckkauf_cents")):
        entry.pop("rueckkauf_policenwert_cents", None)
    for feld in RUECKKAUF_FELDER:
        if feld in body:
            wert = body[feld]
            if feld == "rueckkauf_as_of":
                if _tag(wert) != _tag(entry.get(feld)):
                    _leer_heisst_weg(entry, feld, str(wert).strip())
            else:
                _leer_heisst_weg(entry, feld, None if wert in (None, "") else int(wert))


@router.post("/api/bestand")
async def api_bestand(request: Request):
    """Einen getippten Stand ablegen: Wert, Datum, Gewinn, Rueckkaufswert und die Notiz.

    Gespeichert wird die ganze Position in `balances.yaml`, mit ihrer Notiz -- die Begruendung,
    warum die ETFs null sind und wessen Geld ein Teil des Kontos ist, steht im Eintrag und geht
    beim Speichern nicht verloren. Speichern ohne Aenderung aendert die Datei nicht.
    """

    body = lies_texte(await request.json(), dict.fromkeys(
        ("rueckkauf_cents", "eingezahlt_cents", "rueckkauf_policenwert_cents"), "betrag"))
    key = (body.get("key") or "").strip()
    if not key:
        return JSONResponse({"error": "key required"}, status_code=400)

    # Konten mit Auszug -- Girokonten, Tagesgeld -- kommen aus dem Auszug. Ein
    # getippter Stand daneben waere eine zweite Wahrheit.
    from finctl import bestaende as _best

    spec = _best.lesen(CONFIG_DIR / _best.DATEI)
    eintrag = _best.position(spec, key)
    c = conn()
    try:
        geparst = _best.geparste_konten(c)
        # Ein Konto, dessen Export keinen Saldo traegt, hat keinen Auszugsstand: Hier steht der
        # Kontostand laut Online-Banking, von dem aus die App vor- und zurueckrechnet.
        ohne_saldo = _ks.ohne_saldo(c, key)
        if eintrag is None and ohne_saldo:
            eintrag = _best.anker_eintrag(c, spec, key)
        if eintrag is None:
            return JSONResponse({"error": f"unbekannte Position {key}"}, status_code=404)
        # Gesperrt ist der WERT, nicht die Notiz: was ein Konto wert ist, sagt der
        # Auszug; was von dem Geld jemand anderem gehoert, sagt nur der Besitzer.
        if key in geparst and not ohne_saldo and ("cents" in body or body.get("as_of")):
            return JSONResponse({"error": f"Stand und Stichtag von {key} kommen aus dem "
                                          "Auszug"}, status_code=400)
        vorher = _best.zusammenfuehren(c, spec)
        alt = next((z for z in vorher["balances"] if _best.schluessel(z) == key), None)
        if not _bestand_aendern(eintrag, body):
            return JSONResponse({"error": "amount required"}, status_code=400)
        try:
            if alt is not None:
                _best.policenwert_festhalten(alt, eintrag)
            nachher = _best.zusammenfuehren(c, spec)
        except ValueError as fehler:        # ein falsches Rueckkaufs-Feld, wie beim Lesen
            return JSONResponse({"error": str(fehler)}, status_code=400)
    finally:
        c.close()

    _best.verlauf_fortschreiben(spec, vorher, nachher, key, _dtm.date.today())
    yaml_schreiben(CONFIG_DIR / _best.DATEI, spec)
    if ohne_saldo:
        # Der Anker gilt sofort, nicht erst beim naechsten `finctl init`.
        c = conn()
        try:
            _best.spiegeln(c, spec)
            c.commit()
        finally:
            c.close()
    return {"ok": True, "count": len(spec.get("balances") or [])}


@router.post("/api/bestand-neu")
async def api_bestand_neu(request: Request):
    """Eine Position anlegen: ein Depot, Krypto, Tagesgeld oder eine Rentenversicherung.

    Sie haengt an einem Konto ohne Auszug und beginnt mit einem Stand. Ohne diesen Weg ging
    eine Position nur im Texteditor: `/api/bestand` aendert nur, was die Datei schon traegt.
    """
    from finctl import bestaende as _best

    body = lies_texte(await request.json(), {"cents": "betrag"})
    spec = _best.lesen(CONFIG_DIR / _best.DATEI)
    c = conn()
    try:
        vorher = _best.zusammenfuehren(c, spec)
        try:
            key = _best.position_anlegen(c, spec, body)
            nachher = _best.zusammenfuehren(c, spec)
        except ValueError as fehler:
            return JSONResponse({"error": str(fehler)}, status_code=400)
        _best.verlauf_fortschreiben(spec, vorher, nachher, key, _dtm.date.today())
        yaml_schreiben(CONFIG_DIR / _best.DATEI, spec)
        # Der Stand gilt sofort, nicht erst beim naechsten `finctl init`.
        _best.spiegeln(c, spec)
        c.commit()
    finally:
        c.close()
    return {"ok": True, "key": key}


@router.post("/api/bestand-entfernen")
async def api_bestand_entfernen(request: Request):
    """Eine Position samt Notiz und Verlauf aus `balances.yaml` nehmen. Das Konto bleibt."""
    from finctl import bestaende as _best

    body = await request.json()
    spec = _best.lesen(CONFIG_DIR / _best.DATEI)
    c = conn()
    try:
        try:
            _best.position_entfernen(c, spec, str(body.get("key") or "").strip())
        except ValueError as fehler:
            return JSONResponse({"error": str(fehler)}, status_code=400)
        yaml_schreiben(CONFIG_DIR / _best.DATEI, spec)
        _best.spiegeln(c, spec)
        c.commit()
    finally:
        c.close()
    return {"ok": True}


@router.post("/api/verpflichtung")
async def api_verpflichtung(request: Request):
    """Eine Verbindlichkeit anlegen, ändern oder streichen.

    Sie zieht vom liquiden Vermögen ab und liegt im selben Topf wie eigenes
    Geld -- genau deshalb muss sie sich pflegen lassen, ohne eine Datei zu
    öffnen. Getilgt wird sie gestrichen: Sie fällt samt ihrer Notiz aus
    `balances.yaml`.
    """

    from finctl import bestaende as _best

    body = await request.json()
    name = (body.get("name") or "").strip()
    kennung = _best.kennung(body.get("kennung") or name)
    if not kennung:
        return JSONResponse({"error": "Name fehlt"}, status_code=400)
    if kennung in _notizen.RESERVIERT:
        return JSONResponse({"error": f"„{kennung}“ ist für Notizen reserviert"},
                            status_code=400)

    spec = _best.lesen(CONFIG_DIR / _best.DATEI)
    eintrag = _best.verpflichtung(spec, kennung)
    liste = [e for e in spec.get("obligations") or [] if isinstance(e, dict)]
    if body.get("remove"):
        liste = [e for e in liste if e is not eintrag]
    else:
        if eintrag is None:
            eintrag = {"name": name or kennung}
            liste.append(eintrag)
        if name and name != eintrag.get("name"):
            eintrag["name"] = name
        if "cents" in body:
            if body.get("cents") in (None, ""):
                return JSONResponse({"error": "Betrag fehlt"}, status_code=400)
            eintrag["cents"] = int(body["cents"])
        if "note" in body:
            _notizen.setzen(eintrag, _notizen.eingabe(body.get("note")), alt=NOTIZ_ALT)
    yaml_schreiben(CONFIG_DIR / _best.DATEI, {**spec, "obligations": liste})
    return {"ok": True}
