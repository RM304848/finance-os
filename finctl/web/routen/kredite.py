"""Tilgungsplaene und Anschlussfinanzierung.

Jede Kreditentscheidung wurde bisher gegen `finctl loans` im Terminal
getroffen -- ob sich ein Forward-Darlehen lohnt, welcher Zins fuer die
Anschlussfinanzierung angesetzt wird, wie hoch der Stand bei Faelligkeit einer
Tilgungsaussetzung ist. Genau die Zahlen gehoeren auf eine Seite.
"""

from __future__ import annotations

import datetime as _dtm

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from finctl.web.basis import (
    CONFIG_DIR,
    TEMPLATES,
    conn,
    lies_texte,
    notiz_felder,
)
from finctl.web.verkauf import _verkaeufe_aus_plan

router = APIRouter()

def _als_datum(wert):
    """Ein Datum aus der YAML kommt als Text oder schon als date an.

    Stand sechsmal ausgeschrieben in `kredite`, jedes Mal als drei Zeilen
    `if isinstance(...)`. Sechs Stellen, an denen eine vergessen werden kann.
    """
    return _dtm.date.fromisoformat(wert) if isinstance(wert, str) else wert


def _bindung_von(loan: dict):
    """Die Zinsbindung, unter beiden Schreibweisen, die in den Daten stehen."""
    return _als_datum(loan.get("zinsbindung_ende") or loan.get("zinsbindung_end"))


def _mit_eingetragener_kondition(loan: dict, entered: dict) -> tuple[dict, dict]:
    """Dieselbe Kappung wie für die Anschlussrechnung.

    Damit die Zahlen LINKS die eingegebene Kondition auch wirklich enthalten.
    Ohne sie meldete die linke Spalte bei einem Darlehen Volltilgung ein Jahr
    frueher als die rechte -- zwei Antworten auf dieselbe Frage, nebeneinander.

    Nur kappen, wenn die Bindung INNERHALB des letzten Segments liegt. Liegt
    ein dokumentiertes Forward-Angebot vor, gehoert `zinsbindung_end` zum
    ERSTEN Segment -- dort zu kappen wuerde genau dieses Angebot wegwerfen,
    also die Zahl, die man behalten will.
    """
    segs = loan.get("segments") or []
    ende = _als_datum(segs[-1]["end"]) if segs else None
    bindung = _bindung_von(loan)
    start = _als_datum(segs[-1]["start"]) if segs else None
    if not (bindung and ende and start and start <= bindung < ende):
        return {**loan, "anschluss": entered}, entered

    gekappt = [dict(x) for x in segs]
    gekappt[-1]["end"] = bindung
    kondition = {**entered}
    kondition.setdefault("ab", (bindung + _dtm.timedelta(days=1)).isoformat())
    return {**loan, "segments": gekappt, "anschluss": kondition}, kondition


def _jahressummen(sched) -> dict[int, dict]:
    """Zins, Tilgung und Restschuld je Kalenderjahr."""
    by_year: dict[int, dict] = {}
    for p in sched.payments:
        row = by_year.setdefault(p.month.year, {"zins": 0, "tilgung": 0})
        row["zins"] += p.interest_cents
        row["tilgung"] += p.principal_cents
        row["rest"] = p.balance_cents
    return by_year


def _kreditkennzahlen(loan: dict, laufend) -> tuple[float, float | None, float | None]:
    """Zins, anfängliche Tilgung und Tilgung nach heutigem Stand.

    ANFÄNGLICHE Tilgung, and the word matters: the repayment share of an
    annuity grows every month, so measuring it against today's balance gives
    the CURRENT share, not the quoted one. On a loan running for some years
    the two differ by a factor of two. A bank quotes the figure at the start
    of the fixed-rate period, so that is what is derived here, from the first
    payment of the segment today falls into.

    Die dritte Zahl ist, was dieselbe Rate HEUTE als Tilgungssatz wäre. Sie
    steht in der Anschlussmaske vor, nicht die anfängliche: die laufende Rate
    fortzuführen ist der natürliche Ausgangspunkt, und der Anfangssatz stimmt
    seit Jahren nicht mehr.
    """
    if not laufend:
        return 0.0, None, None

    basis_seg = laufend.balance_cents + laufend.principal_cents
    zins_pa = (laufend.interest_cents * 12.0 / basis_seg * 100.0) if basis_seg else 0.0

    # The figure a bank actually quotes: repayment in the FIRST year, on the
    # ORIGINAL principal -- typically the classic 2,00 %. Deriving it from the
    # modelled segment instead gives a visibly higher number, because that
    # segment starts today and years of repayment have already happened.
    #
    # Die Summe der LAUFENDEN Finanzierung, wo sie bekannt ist. Ein zweimal
    # abgelöster Kredit hat keine einzelne Ursprungssumme mehr.
    principal = loan.get("current_principal_cents") or loan.get("principal_cents")
    tilgung_pct = None
    if principal and zins_pa:
        tilgung_pct = round(laufend.payment_cents * 12.0 / principal * 100.0 - zins_pa, 3)

    tilgung_heute_pct = None
    if laufend.balance_cents and basis_seg:
        tilgung_heute_pct = round((laufend.payment_cents - laufend.interest_cents)
                                  * 12.0 / basis_seg * 100.0, 3)
    return zins_pa, tilgung_pct, tilgung_heute_pct


def _anschlussrechnung(loan: dict, sched, entered: dict | None,
                       dokumentiert: list, rate_pa: float,
                       tilgung_heute_pct: float | None, letztes_ende) -> dict:
    """Die Anschlussfinanzierung in drei Stufen, von belegt zu geraten:

    1. eine eingegebene Kondition, wenn es eine gibt;
    2. sonst ein bereits DOKUMENTIERTES Folgesegment -- liegt ein schriftliches
       Forward-Angebot der Bank vor, wäre eine Vorschau mit heutigen Werten
       danebenzustellen eine erfundene Zahl neben einer bekannten;
    3. sonst eine Vorschau mit den heutigen Konditionen, also die Antwort auf
       "was passiert, wenn nichts verhandelt wird". Das ist der
       Vergleichsmassstab für alles, was man aushandeln könnte.
    """
    from finctl.realestate.loan import amortise, opening_balance_cents, segments_from

    # Ein Segment, das über die Zinsbindung hinausreicht, schreibt den Zins nur
    # vereinfachend fort: es läuft mit konstantem Satz bis zur Volltilgung,
    # während die Bindung Jahre früher endet. Für JEDE Anschlussrechnung wird
    # es an der Bindung gekappt -- sonst hängt die neue Kondition hinter einem
    # Kredit, der zu alten Konditionen bereits getilgt ist, und die Tabelle
    # verschwindet wortlos.
    #
    # Das galt zuerst nur für die Vorschau, nicht für eine eingegebene
    # Kondition, und genau daran scheiterte jeder Versuch, für ein solches
    # Darlehen etwas einzutragen.
    segs = loan.get("segments") or []
    bindung = _bindung_von(loan)
    erstes_des_letzten = _als_datum(segs[-1]["start"]) if segs else None
    kappen = bool(bindung and letztes_ende and erstes_des_letzten
                  and erstes_des_letzten <= bindung < letztes_ende)

    def _probe(kondition: dict):
        """Schedule with a follow-up applied, clipped where it belongs."""
        probe_loan = {**loan}
        k = dict(kondition)
        if kappen:
            gekappt = [dict(x) for x in segs]
            gekappt[-1]["end"] = bindung
            probe_loan["segments"] = gekappt
            k.setdefault("ab", (bindung + _dtm.timedelta(days=1)).isoformat())
        probe_segs = segments_from({**probe_loan, "anschluss": k})
        sch = amortise(loan["id"], opening_balance_cents(loan), probe_segs)
        rows = [x for x in sch.payments if x.segment_index == len(probe_segs) - 1]
        return rows, sch.payoff_month()

    def _versuch(kondition):
        try:
            return _probe(kondition)
        except Exception:
            return [], None

    if entered:
        quelle = "eingegeben"
        after, payoff = _versuch(entered)
    elif dokumentiert:
        quelle = "dokumentiert"
        nxt = dokumentiert[0].segment_index
        after = [p for p in sched.payments if p.segment_index == nxt]
        payoff = sched.payoff_month()
    else:
        quelle = "vorschau"
        after, payoff = _versuch({"zins_pct": round(rate_pa, 3),
                                  "tilgung_pct": tilgung_heute_pct or 2.0})

    if not after:
        return {"leer": True, "quelle": quelle,
                "ab": (entered or {}).get("ab") or letztes_ende}

    basis = after[0].balance_cents + after[0].principal_cents
    zins_pa = after[0].interest_cents * 12.0 / basis * 100.0 if basis else 0.0
    annuity_pa = after[0].payment_cents * 12.0 / basis * 100.0 if basis else 0.0
    return {
        "quelle": quelle, "ab": after[0].month,
        "zins_pct": round(zins_pa, 3),
        "tilgung_pct": round(annuity_pa - zins_pa, 3),
        "rate_cents": after[0].payment_cents,
        "start_balance_cents": basis,
        "zins_gesamt_cents": sum(p.interest_cents for p in after),
        "tilgung_gesamt_cents": sum(p.principal_cents for p in after),
        "monate": len(after), "payoff": payoff,
    }


def _gebuchte_zinsen() -> dict[tuple[str, int], int]:
    """Was TATSÄCHLICH gebucht wurde, neben dem, was der Plan sagt.

    Die Jahreszahl aus dem Tilgungsplan umfasst auch die Monate, die noch
    nicht stattgefunden haben, und weiss nichts davon, wie eine Rate im Ledger
    aufgeteilt wurde. Eine Abweichung bedeutet eins von beidem: der Plan ist
    falsch oder die Buchung ist es. Genau so wurde gefunden, dass bei einem
    Objekt neun Monatsraten zu 100 % als Tilgung gebucht waren -- ohne diesen
    Vergleich wäre das nie aufgefallen.
    """
    gebucht: dict[tuple[str, int], int] = {}
    c = conn()
    try:
        for row in c.execute("""
            SELECT s.property_id AS pid,
                   CAST(substr(t.booking_date, 1, 4) AS INTEGER) AS jahr,
                   SUM(-s.amount_cents) AS cents
            FROM   splits s JOIN transactions t ON t.id = s.transaction_id
            WHERE  s.mgmt_category_id = 'kredit/zinsen' AND s.property_id IS NOT NULL
            GROUP  BY pid, jahr
        """):
            gebucht[(row["pid"], row["jahr"])] = int(row["cents"])
    finally:
        c.close()
    return gebucht


def _kreditzeile(loan: dict, entered: dict | None, sched, *, want: str,
                 gebucht: dict, verkauft: dict, aktive_klammern) -> dict:
    """Eine Zeile der Kreditübersicht, fertig für das Template."""
    from finctl.realestate.loan import opening_balance_cents

    # Where the loan stands TODAY, not where its schedule began. The opening
    # balance is a starting point that gets further from the truth every
    # month; what a decision is made against is the balance now.
    heute = _dtm.date.today()
    past = [p for p in sched.payments if p.month <= heute]
    aktuell = past[-1] if past else None
    laufend = aktuell or (sched.payments[0] if sched.payments else None)

    rate_pa, tilgung_pct, tilgung_heute_pct = _kreditkennzahlen(loan, laufend)

    segs = loan.get("segments") or []
    letztes_ende = _als_datum(segs[-1]["end"]) if segs else None
    laufender_index = laufend.segment_index if laufend else 0
    # Gezählt werden die KONFIGURIERTEN Segmente, nicht die Zahlungen: der
    # Plan enthält bei einer eigenen Kondition bereits das angehängte
    # Segment, und dann hielte sich jeder Kredit für dokumentiert.
    hat_angebot = len(segs) > laufender_index + 1
    dokumentiert = [p for p in sched.payments
                    if p.segment_index > laufender_index] if hat_angebot else []

    payments = [p for p in sched.payments
                if str(p.month.year) == want] if want else sched.payments

    return {
        "folge": _anschlussrechnung(loan, sched, entered, dokumentiert,
                                    rate_pa, tilgung_heute_pct, letztes_ende),
        "id": loan["id"], "name": loan.get("name"), **notiz_felder(loan),
        # Ein Kredit, der an einer Klammer haengt, gehoert auf diese Seite
        # -- dort werden Konditionen eingetragen --, aber er muss sich vom
        # Rest unterscheiden: die drei oberen sind Vertraege, dieser ist
        # eine Rechnung, die nur laeuft, solange jemand sie eingeschaltet
        # hat.
        "szenario": loan.get("szenario"),
        "szenario_an": loan.get("szenario") in aktive_klammern,
        # Endet der Kredit durch einen geplanten Verkauf, steht das hier:
        # in der Jahresrechnung laeuft die Rate ab dem Monat nicht weiter.
        "verkauf": verkauft.get(loan.get("property_id")),
        "vorlage_start": (str(segs[0]["start"])[:10] if segs else None),
        "vorlage_ende": (str(segs[-1]["end"])[:10] if segs else None),
        "property_id": loan.get("property_id"),
        "lender": loan.get("lender"),
        "opening_cents": opening_balance_cents(loan),
        "rest_cents": aktuell.balance_cents if aktuell else
                      opening_balance_cents(loan),
        "rate_cents": laufend.payment_cents if laufend else 0,
        "zins_pct": round(rate_pa, 3),
        "tilgung_pct": tilgung_pct,
        "tilgung_heute_pct": tilgung_heute_pct,
        "zins_jahr_cents": sum(p.interest_cents for p in sched.payments
                               if p.month.year == heute.year),
        "zins_jahr_gebucht_cents": gebucht.get(
            (loan.get("property_id"), heute.year)),
        "jahr_heute": heute.year,
        "total_interest_cents": sched.total_interest_cents(),
        "payoff": sched.payoff_month(),
        "zinsbindung_ende": loan.get("zinsbindung_ende")
                            or loan.get("zinsbindung_end"),
        "anschluss": entered or loan.get("anschluss"),
        "folge_ab_default": letztes_ende.isoformat() if letztes_ende else "",
        # Ob ein dokumentiertes Folgesegment existiert -- unabhängig davon,
        # ob gerade eine eigene Kondition darüberliegt. Ohne das sagt der
        # Zurücksetzen-Hinweis "die Vorschau", obwohl bei einem Darlehen mit
        # Forward-Angebot genau dieses Angebot zurückkäme.
        "hat_angebot": hat_angebot,
        "open": loan.get("open") or [],
        "years": sorted(_jahressummen(sched).items()),
        "payments": payments[:180],
        "error": None,
    }


@router.get("/kredite", response_class=HTMLResponse)
def kredite(request: Request):
    """Amortisation schedules -- the only major figure that had no screen.

    Every loan decision so far has been made against `finctl loans` output in
    a terminal: whether a forward loan pays off, what rate to assume for the
    follow-up, what the balance will be when an endowment policy matures.
    Those are exactly the numbers that need to be visible without remembering
    a command.
    """

    from finctl import kredite as _kr
    from finctl.forecast import szenarien as _szm
    from finctl.realestate.loan import amortise, opening_balance_cents, segments_from
    from finctl.realestate.loan import lade_kredite as _lade

    want = request.query_params.get("jahr") or ""

    c = conn()
    try:
        verkauft = _verkaeufe_aus_plan(c)
    finally:
        c.close()
    umfeld = {"want": want, "gebucht": _gebuchte_zinsen(), "verkauft": verkauft,
              "aktive_klammern": _szm.aktive_ids()}

    loans = []
    for roh in _lade(CONFIG_DIR):
        entered = roh.get(_kr.ANSCHLUSS)
        loan, entered = (_mit_eingetragener_kondition(roh, entered) if entered
                         else (roh, None))
        try:
            sched = amortise(loan["id"], opening_balance_cents(loan),
                             segments_from(loan))
        except Exception as exc:
            loans.append({"id": loan.get("id"), "name": loan.get("name"),
                          "error": str(exc), "payments": []})
            continue
        loans.append(_kreditzeile(loan, entered, sched, **umfeld))

    years = sorted({y for kredit in loans for y, _ in kredit.get("years", [])})
    c = conn()
    try:
        konten = [r[0] for r in c.execute(
            "SELECT id FROM accounts WHERE active = 1 ORDER BY id")]
    finally:
        c.close()
    return TEMPLATES.TemplateResponse(request, "kredite.html", {
        "loans": loans, "years": years, "jahr": want, "konten": konten})


@router.post("/api/kredit-neu")
async def api_kredit_neu(request: Request):
    """Einen Ratenkredit anlegen.

    Ein Immobiliendarlehen entsteht hier nicht: dreissig Felder in ein
    Formular zu pressen machte die Seite unbrauchbar, und geaendert werden
    sie auf dieser Seite ohnehin schon.
    """
    from finctl import kredite as _kr

    body = lies_texte(await request.json(), {
        "opening_balance_cents": "betrag", "annuity_cents": "betrag",
        "annual_rate_pct": "zahl"})
    try:
        return {"ok": True, "kredit": _kr.anlegen(body)}
    except ValueError as fehler:
        return JSONResponse({"error": str(fehler)}, status_code=400)


@router.post("/api/kredit-entfernen")
async def api_kredit_entfernen(request: Request):
    """Einen Kredit ausblenden -- der Weg, den ein neuer Nutzer zuerst braucht.

    Wer dieses Werkzeug uebernimmt, erbt sonst fremde Vertraege, und eine
    Rate, die er nie zahlt, drueckt den Tiefpunkt jedes Monats.
    """
    from finctl import kredite as _kr

    body = await request.json()
    try:
        _kr.entfernen(str(body.get("id") or ""))
    except ValueError as fehler:
        return JSONResponse({"error": str(fehler)}, status_code=400)
    return {"ok": True}


@router.post("/api/kredit-anschluss")
async def api_kredit_anschluss(request: Request):
    """Define what happens after the Zinsbindung: a rate and a repayment.

    Quoted the German way, because that is how the bank quotes it: "3,8 %
    Zins, 2 % Tilgung". The monthly payment follows from the two,
    (Zins + Tilgung) x Restschuld / 12.

    No end date is asked for, and that is deliberate rather than an omission.
    The term is a RESULT of those two percentages -- on the same balance, 4,5
    plus 2,0 repays roughly eight years later than 5,5 plus 3,0. Asking for
    the date as well would let someone enter a combination that cannot repay
    by the date they typed, and the schedule would then quietly disagree with
    the form.

    Gespeichert wird am Kredit unter `anschluss_eingegeben`, nicht unter
    `anschluss`: Das eine rechnet die Seite durch, das andere die Prognose.
    """
    from finctl import kredite as _kr

    body = lies_texte(await request.json(), {"zins_pct": "zahl", "tilgung_pct": "zahl"})
    loan_id = str(body.get("id") or "").strip()
    if not loan_id:
        return JSONResponse({"error": "Kredit fehlt"}, status_code=400)

    if body.get("entfernen"):
        eintrag = None
    else:
        try:
            zins = float(body["zins_pct"])
            tilgung = float(body["tilgung_pct"])
        except (KeyError, TypeError, ValueError):
            return JSONResponse({"error": "Zins und Tilgung in Prozent angeben"},
                                status_code=400)
        if zins < 0 or tilgung <= 0:
            return JSONResponse(
                {"error": "Tilgung muss über null liegen, sonst wird der Kredit nie "
                          "getilgt und der Plan läuft ins Leere."}, status_code=400)
        eintrag = {"zins_pct": zins, "tilgung_pct": tilgung, "basis": "assumption"}
        if (body.get("ab") or "").strip():
            eintrag["ab"] = str(body["ab"]).strip()

    try:
        _kr.an_kredit_setzen(loan_id, _kr.ANSCHLUSS, eintrag)
    except ValueError as fehler:
        return JSONResponse({"error": str(fehler)}, status_code=404)
    return {"ok": True}


@router.post("/api/kredit-vorlage")
async def api_kredit_vorlage(request: Request):
    """Grundkonditionen eines Vorlagenkredits setzen.

    NUR fuer Kredite, die an einer Klammer haengen. Die echten Vertraege sind
    aus Unterlagen rekonstruiert, teils rueckwaerts aus beobachteten Zahlungen
    -- sie hier ueberschreibbar zu machen hiesse, eine Tatsache durch eine
    Eingabe ersetzen zu koennen.

    Gespeichert wird am Kredit unter `vorlage`; die Konditionen des Eintrags
    bleiben darunter stehen, und `entfernen` stellt sie wieder her.
    """
    from finctl import kredite as _kr
    from finctl.realestate.loan import an_szenario_gebunden, annuitaet_fuer_monate, monate_zwischen

    body = lies_texte(await request.json(), {
        "principal_cents": "betrag", "annual_rate_pct": "zahl", "annuitaet_cents": "betrag"})
    lid = str(body.get("id") or "").strip()
    loan = _kr.eintrag(_kr.lesen(), lid)
    if loan is None:
        return JSONResponse({"error": "unbekannter Kredit"}, status_code=404)
    if not an_szenario_gebunden(loan):
        return JSONResponse(
            {"error": "Nur Vorlagen sind änderbar. Die Verträge stehen in "
                      "loans.yaml mit ihrer Notiz -- was dort steht, ist "
                      "aus Unterlagen belegt und keine Eingabe."},
            status_code=400)

    if body.get("entfernen"):
        eintrag = None
    else:
        try:
            betrag = int(body["principal_cents"])
            zins = float(body["annual_rate_pct"])
            start = str(body["start"])[:7] + "-01"
            ende = str(body["ende"])[:7] + "-01"
            von, bis = _dtm.date.fromisoformat(start), _dtm.date.fromisoformat(ende)
        except (KeyError, TypeError, ValueError):
            return JSONResponse({"error": "Summe, Zins, Beginn und Ende nötig"},
                                status_code=400)
        if betrag <= 0 or zins < 0 or bis <= von:
            return JSONResponse({"error": "Das Ende muss nach dem Beginn liegen"},
                                status_code=400)
        eintrag = {"principal_cents": betrag, "annual_rate_pct": zins,
                   "start": start, "ende": ende}
        # Die Rate ist ein Ergebnis, keine dritte Eingabe -- ausser sie wird
        # ausdruecklich gesetzt. Dann gilt sie, und das Ende verschiebt sich
        # eben: wer eine Rate kennt, kennt sie aus einem Angebot. Steht im Feld die
        # Rate, die aus den vier Angaben folgt, ist sie keine Angabe: sonst friert
        # jedes Speichern ohne Aenderung ein Ergebnis zur Eingabe ein.
        if body.get("annuitaet_cents") and int(body["annuitaet_cents"]) != annuitaet_fuer_monate(
                betrag, zins, monate_zwischen(von, bis)):
            eintrag["annuitaet_cents"] = int(body["annuitaet_cents"])

    _kr.an_kredit_setzen(lid, _kr.VORLAGE, eintrag)
    gerechnet = (annuitaet_fuer_monate(int(body["principal_cents"]),
                                       float(body["annual_rate_pct"]),
                                       monate_zwischen(von, bis))
                 if not body.get("entfernen") else None)
    return {"ok": True, "annuitaet_cents": gerechnet}
