"""Zinssaetze je Konto, datiert -- aus `config/zinssaetze_custom.yaml`.

Ein Konto hat eine Liste von Saetzen mit `ab` und optional `bis` (ein
Aktionszins), beide als Monat `JJJJ-MM`, einschliesslich. Welcher Satz in einem
Monat gilt, steht in `finctl/forecast/zinsen.py`: Das hier liest und schreibt
nur. Die Datei traegt nur Zahlen, die niemand in einem Auszug nachlesen kann;
bearbeitet wird sie auf /annahmen.
"""

from __future__ import annotations

from datetime import date

from finctl import dateien
from finctl import notizen as _notizen
from finctl.forecast.zinsen import Zinssatz
from finctl.pfade import CONFIG_DIR

DATEI = "zinssaetze_custom.yaml"
SCHLUESSEL = "zinssaetze"
#: Hoechster Satz, den die Seite annimmt: 25 %. Darueber ist es ein Tippfehler.
HOECHSTSATZ = 0.25

KOPF = """# Im Dashboard eingetragen: Zinssaetze je Konto, datiert.
#
# Je Konto eine Liste mit `ab` und optional `bis` (beide JJJJ-MM, einschliesslich)
# und `satz` als Anteil (0.03 fuer 3 %). Ohne Eintrag zahlt ein Tagesgeld den
# langfristigen Satz aus den Annahmen, ein Girokonto nichts; nach dem letzten
# Eintrag zahlt das Konto den langfristigen Satz weiter.

"""


def monat(wert, *, feld: str = "Monat") -> date | None:
    """Ein Monat aus `JJJJ-MM` (oder einem Datum, das YAML schon gelesen hat)."""
    if wert in (None, ""):
        return None
    if isinstance(wert, date):
        return wert.replace(day=1)
    try:
        return date.fromisoformat(str(wert).strip()[:7] + "-01")
    except ValueError:
        raise ValueError(f"{feld}: „{wert}“ ist kein Monat, erwartet JJJJ-MM.") from None


def _satz(konto: str, roh) -> Zinssatz:
    try:
        ab = monat(roh.get("ab"), feld="ab")
        bis = monat(roh.get("bis"), feld="bis")
        satz = float(roh["satz"])
    except (AttributeError, KeyError, TypeError, ValueError) as fehler:
        raise ValueError(f"Zinssatz von {konto}: {roh!r} unlesbar ({fehler}).") from None
    if ab is None:
        raise ValueError(f"Zinssatz von {konto}: ab fehlt.")
    return Zinssatz(ab=ab, bis=bis, satz=satz)


def lesen() -> dict[str, tuple[Zinssatz, ...]]:
    """Je Konto die Saetze, nach `ab` sortiert."""
    roh = _notizen.ohne(dateien.zuordnung_lesen(CONFIG_DIR / DATEI, SCHLUESSEL))
    return {str(konto): tuple(sorted((_satz(str(konto), z) for z in zeilen or ()),
                                     key=lambda z: z.ab))
            for konto, zeilen in roh.items() if zeilen}


def zeilen() -> list[dict]:
    """Fuer die Seite: Konto, laufende Nummer im Konto, ab, bis, Satz."""
    return [{"konto": konto, "nr": nr, "ab": z.ab.strftime("%Y-%m"),
             "bis": z.bis.strftime("%Y-%m") if z.bis else "", "satz": z.satz}
            for konto, saetze in sorted(lesen().items())
            for nr, z in enumerate(saetze)]


def _schreiben(daten: dict[str, tuple[Zinssatz, ...]]) -> None:
    dateien.zuordnung_schreiben(CONFIG_DIR / DATEI, SCHLUESSEL, {
        konto: [{"ab": z.ab.strftime("%Y-%m"),
                 **({"bis": z.bis.strftime("%Y-%m")} if z.bis else {}),
                 "satz": z.satz} for z in saetze]
        for konto, saetze in daten.items() if saetze}, KOPF)


def _ueberschneidet(a: Zinssatz, b: Zinssatz) -> bool:
    return (a.bis is None or b.ab <= a.bis) and (b.bis is None or a.ab <= b.bis)


def anlegen(konto: str, ab, bis, satz: float) -> None:
    """Einen Satz eintragen. `ValueError` mit der Meldung, wenn er nicht passt."""
    konto = (konto or "").strip()
    if not konto:
        raise ValueError("Konto fehlt.")
    erster = monat(ab, feld="ab")
    if erster is None:
        raise ValueError("ab fehlt.")
    neu = Zinssatz(ab=erster, bis=monat(bis, feld="bis"), satz=float(satz))
    if neu.bis is not None and neu.bis < neu.ab:
        raise ValueError("bis liegt vor ab.")
    if not 0 <= neu.satz <= HOECHSTSATZ:
        raise ValueError(f"Zinssatz zwischen 0 und {HOECHSTSATZ * 100:.0f} %.")
    daten = lesen()
    for z in daten.get(konto, ()):
        if _ueberschneidet(z, neu):
            raise ValueError(f"Der Zeitraum überschneidet sich mit dem ab {z.ab:%Y-%m}.")
    daten[konto] = tuple(sorted((*daten.get(konto, ()), neu), key=lambda z: z.ab))
    _schreiben(daten)


def loeschen(konto: str, nr: int) -> None:
    """Den Satz mit dieser Nummer im Konto entfernen (Nummer wie in `zeilen`)."""
    daten = lesen()
    saetze = list(daten.get(konto, ()))
    if not 0 <= nr < len(saetze):
        raise ValueError("Den Zinssatz gibt es nicht mehr.")
    del saetze[nr]
    daten[konto] = tuple(saetze)
    _schreiben(daten)
