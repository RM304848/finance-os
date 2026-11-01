"""Die Steigerung, in der Monatsmodell und Jahresrechnung dieselbe Rechnung benutzen.

Eine Messung ist im Mittel ein halbes Fenster alt. Fortgeschrieben wird deshalb von
der MITTE DES MESSFENSTERS zum Zeitpunkt, an dem der Betrag faellt, stetig mit der
Rate im Jahr. Ab heute gerechnet laege jede laufende Position rund ein Prozent zu
niedrig.

Die Jahresrechnung nimmt als Zeitpunkt die Mitte des Jahres (`jahresmitte`), das
Monatsmodell die Mitte des Monats (`monatsmitte`). Die zwoelf Monatsmitten eines
Jahres mitteln sich auf die Jahresmitte; ueber ein volles Kalenderjahr kommen beide
auf dieselbe Zahl, bis auf die Rundung.

Zeitpunkte sind Jahreszahlen: der 1. Juli 2027 ist 2027,5.
"""

from __future__ import annotations

from datetime import date

from finctl import assumptions as ann


def fenstermitte(von: date, monate: int) -> float:
    """Die Mitte eines Fensters, das am Ersten von `von` beginnt und `monate` Monate lang ist."""
    return von.year + (von.month - 1) / 12 + monate / 24


def jahresmitte(jahr: int) -> float:
    return jahr + 0.5


def monatsmitte(monat: date) -> float:
    return monat.year + (monat.month - 1) / 12 + 1 / 24


def seit_messung(mitte: float, zeitpunkt: float) -> float:
    """Die Jahre von der Mitte des Fensters bis zum Zeitpunkt."""
    return zeitpunkt - mitte


def faktor(mitte: float, zeitpunkt: float, rate: float) -> float:
    """Um wie viel ein gemessener Betrag bis zum Zeitpunkt steigt, als Faktor."""
    return (1.0 + rate) ** seit_messung(mitte, zeitpunkt)


def fortschreiben(cents: int, mitte: float, zeitpunkt: float, rate: float) -> int:
    """Ein gemessener Betrag zum Zeitpunkt, mit der Rate seit der Mitte des Fensters."""
    return ann.grow(cents, seit_messung(mitte, zeitpunkt), rate)
