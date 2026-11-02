"""Renten: gesetzliche Rente und Policen anlegen und pflegen.

Die eine Stelle dafuer. Der Monatsabschluss prueft nur, ob ein Schreiben aus
diesem Jahr vorliegt, und fuehrt hierher -- zwei Felder fuer denselben Betrag
laufen auseinander. Gespeichert wird ueber /api/rente und /api/rente-neu
(routen/annahmen.py) nach renten.yaml.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from finctl.web.basis import TEMPLATES

router = APIRouter()


def _modellzeilen(quellen, rentenbeginn: date | None, jm) -> dict[str, str]:
    """Je betrieblicher Altersvorsorge mit Modell, was sie auszahlt und woraus.

    Die Teilzeit kommt aus den Annahmen, ob die Klammer an ist oder nicht: Die
    Seite zeigt beide Auszahlungen nebeneinander. Ein Betrag, den das Modell nicht
    tragen kann, steht als Meldung da und laesst die Seite stehen, auf der man ihn
    korrigiert.
    """
    from finctl import assumptions as _ann
    from finctl import renten as _renten

    anteil, ab = _ann.teilzeit_anteil(), _ann.teilzeit_ab()
    teilzeit = (anteil, ab) if anteil is not None and ab is not None else None
    aus = {}
    for q in quellen:
        beginn = _renten.beginn(q, rentenbeginn) if q.hat_modell else None
        if beginn is None:
            continue
        try:
            aus[q.id] = jm.modellzeile(q, beginn, teilzeit, rentenbeginn)
        except ValueError as fehler:
            aus[q.id] = str(fehler)
    return aus


@router.get("/renten", response_class=HTMLResponse)
def renten(request: Request):
    from finctl import assumptions as _ann
    from finctl import module as _module
    from finctl import person as _person
    from finctl import renten as _renten
    from finctl.forecast import jahre as _jm
    from finctl.web.routen.annahmen import eingaben_der_hochrechnung

    heute = date.today()
    schwelle = _ann.kostenschwelle_pa()
    beginn = _person.rentenbeginn()
    quellen = _renten.quellen()
    # Der Vergleich rechnet die Hochrechnung; ohne sie und ohne Pruefwert gibt es keinen.
    pruef = (_jm.pruefvergleiche(eingaben_der_hochrechnung())
             if _module.seite_an("/hochrechnung") and any(q.pruefwert for q in quellen) else {})
    modell = _modellzeilen(quellen, beginn, _jm)
    zeilen = [{
        "pruefung": pruef.get(q.id, ""), "modell": modell.get(q.id, ""),
        "q": q, "aktuell": q.aktuell(heute),
        "art": _renten.ARTEN[q.art],
        "kaufkraft": "heutige Kaufkraft" if q.kaufkraft == "heute" else "nominal",
        "ab": q.ab.strftime("%Y-%m") if q.ab else "",
        "stand": q.stand.isoformat() if q.stand else "",
        "kosten_hoch": q.kosten_pa is not None and q.kosten_pa > schwelle,
        "notiz": q.notiz, "notiz_vom": q.notiz_vom,
    } for q in quellen]
    return TEMPLATES.TemplateResponse(request, "renten.html", {
        "zeilen": zeilen, "schwelle": schwelle, "jahr": heute.year,
        "rentenbeginn": beginn.strftime("%Y-%m") if beginn else ""})
