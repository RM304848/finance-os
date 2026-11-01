"""Welche zwei Reihen wohl dieselbe Zahlung unter zwei Schreibweisen sind.

Der Importer schreibt manchen Zahler mal so, mal so (Referenznummern, ein Stichwort
aus dem Verwendungszweck, ein Jahr im Namen), und jede Schreibweise ist eine Reihe
fuer sich: Die alte ist nach zwei Terminen beendet, die neue braucht drei, und
dazwischen zaehlt die Zahlung im Rest oder doppelt. Der Haushalt fuehrt
Schreibweisen zusammen (`zusammen` in `reihen_custom.yaml`); hier steht, wo die Seite
es vorschlaegt. Zusammengefuehrt wird nie von selbst.

EIN VORSCHLAG IST ENG. Beide Reihen haben einen festen Takt und einen Betrag je
Termin, liegen in derselben Kategorie, zahlen denselben Betrag, und die eine beginnt,
wo die andere aufhoert: ihr erster Termin liegt etwa einen Takt (wie bei der
Erkennung, ein Viertel Spielraum) nach dem letzten der anderen, hoechstens so weit,
wie die andere noch als laufend gilt. Zwei Reihen, die zugleich laufen, sind nie
dieselbe Zahlung. Darum schlaegt die Seite fuer ein Gehalt, dessen
Monatskuerzel im Namen stehen, nichts vor: jede Schreibweise hat nur einen Termin,
und ihre Zeitraeume liegen ineinander.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from finctl.forecast.takt import (
    ABSTAND_TOLERANZ,
    TAGE_JE_MONAT,
    UEBERFAELLIG_MIN_MONATE,
    UEBERFAELLIG_TAKTE,
    Reihe,
    Reihen,
)
from finctl.ledger.reihe import TOLERANZ


@dataclass(frozen=True, slots=True)
class Vorschlag:
    """`alt` hoert auf, `neu` beginnt: Dieselbe Zahlung, eine neue Schreibweise."""

    alt: Reihe
    neu: Reihe
    #: Tage vom letzten Termin der alten zum ersten der neuen Reihe.
    abstand: int


def _gleicher_betrag(a: int, b: int) -> bool:
    """Gleiches Vorzeichen und, von beiden Seiten gemessen, hoechstens `TOLERANZ` entfernt."""
    return a * b > 0 and abs(a - b) <= TOLERANZ * min(abs(a), abs(b))


def _abstand(alt: Reihe, neu: Reihe) -> int | None:
    """Tage vom letzten Termin von `alt` zum ersten von `neu`, wo das ein Wechsel sein
    kann; sonst `None`."""
    a, n = alt.beitrag, neu.beitrag
    if a is None or n is None or not neu.termine or not isinstance(alt.takt, int):
        return None
    if not _gleicher_betrag(a.betrag_je_termin, n.betrag_je_termin):
        return None
    tage = (neu.termine[0].tag - a.letzter_termin).days
    fruehestens = (1 - ABSTAND_TOLERANZ) * alt.takt * TAGE_JE_MONAT
    spaetestens = (alt.takt + max(UEBERFAELLIG_TAKTE * alt.takt,
                                  UEBERFAELLIG_MIN_MONATE)) * TAGE_JE_MONAT
    return tage if fruehestens <= tage <= spaetestens else None


def vorschlaege(reihen: Reihen) -> list[Vorschlag]:
    """Die Paare, die der Haushalt wohl zusammenfuehren will.

    Je Kategorie in der Reihenfolge des kleinsten Abstands; eine Reihe ist in hoechstens
    einem Vorschlag die alte und in hoechstens einem die neue (eine Kette A, B, C
    bleibt moeglich)."""
    je_kategorie: dict[str, list[Reihe]] = {}
    for r in reihen.reihen:
        if r.fest and r.beitrag is not None:
            je_kategorie.setdefault(r.kategorie, []).append(r)
    kandidaten = []
    for gruppe in je_kategorie.values():
        for alt, neu in itertools.permutations(gruppe, 2):
            abstand = _abstand(alt, neu)
            if abstand is not None:
                kandidaten.append(Vorschlag(alt, neu, abstand))
    kandidaten.sort(key=lambda v: (v.abstand, v.alt.kategorie, v.alt.gegenpartei,
                                   v.neu.gegenpartei))
    alte: set[tuple[str, str]] = set()
    neue: set[tuple[str, str]] = set()
    aus = []
    for v in kandidaten:
        a, n = (v.alt.gegenpartei, v.alt.kategorie), (v.neu.gegenpartei, v.neu.kategorie)
        if a not in alte and n not in neue:
            alte.add(a)
            neue.add(n)
            aus.append(v)
    return sorted(aus, key=lambda v: (v.alt.kategorie, v.alt.gegenpartei, v.neu.gegenpartei))
