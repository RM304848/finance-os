"""Zinsen auf dem Tagesgeld: ein Satz je Konto, datiert, zum Topf gemischt.

Die Hochrechnung kennt nur den Topf Tagesgeld, keine einzelnen Konten. Welchen
Satz er in einem Jahr verdient, folgt aus den Konten darin: jedes mit seinem
Satz, gewichtet mit dem Stand von heute. Das Monatsmodell verzinst jedes Konto
Monat fuer Monat aus seinem Stand (`zins_im_monat`) und rechnet die Steuer darauf
mit demselben Pauschbetrag fuer den ganzen Haushalt (`steuerplan`). Rein: nichts
hier liest eine Datei oder die Datenbank, damit `jahre.rechnen` ohne beides
laeuft. Gelesen werden die Saetze in `finctl/zinssaetze.py`, die Staende reicht
der Aufrufer herein (`ziele.tagesgeld_je_konto`).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import NamedTuple

#: Feste Kennungen der mitgelieferten Taxonomie, wie `einkommen/gehalt`.
ZINSEN = "einkommen/zinsen"
KAPITALERTRAGSTEUER = "steuern/kapitalertragsteuer"

#: Was beide Modelle rechnen, statt es fortzuschreiben: jedes Konto verdient seine
#: Zinsen mit dem Satz aus den Zinssaetzen, und auf sie faellt die Steuer nur nach
#: dem Sparerpauschbetrag an. Beides gemessen mitzuzaehlen zaehlte die Zinsen doppelt
#: und die Steuer ohne den Freibetrag.
GERECHNET = frozenset({ZINSEN, KAPITALERTRAGSTEUER})

#: Die Bestandsart, die den langfristigen Satz bekommt, wenn nichts eingetragen
#: ist. Jede andere Art im Topf (das Girokonto) verdient dann nichts.
VERZINST = "tagesgeld"


@dataclass(frozen=True, slots=True)
class Zinssatz:
    """Ein Satz fuer einen Zeitraum, einschliesslich beider Monate."""

    ab: date                       # erster Monat, Tag 1
    bis: date | None               # letzter Monat, Tag 1; None: ohne Ende
    satz: float                    # 0,03 fuer 3 %

    def gilt(self, monat: date) -> bool:
        return self.ab <= monat and (self.bis is None or monat <= self.bis)


class Konto(NamedTuple):
    """Ein Konto im Topf Tagesgeld, so wie es heute dasteht."""

    art: str                       # Bestandsart: "tagesgeld" oder "giro"
    cents: int


@dataclass(frozen=True, slots=True)
class Mischung:
    """Der Satz des Topfs in einem Jahr und woraus er besteht."""

    satz: float
    #: (Konto, Anteil am Topf, Satz des Kontos in diesem Jahr), nach Anteil.
    teile: tuple[tuple[str, float, float], ...] = ()


def satz_im_monat(saetze: Sequence[Zinssatz], art: str, monat: date,
                  langfristig: float) -> float:
    """Welcher Satz fuer ein Konto in einem Monat gilt.

    1. Der Eintrag, in dessen Zeitraum der Monat faellt; ueberschneiden sich
       zwei, der mit dem spaeteren `ab`.
    2. Sonst, wenn das Konto ueberhaupt Eintraege hat, der langfristige Satz:
       ein Aktionszins endet, das Konto zahlt danach weiter etwas.
    3. Sonst nach Art: ein Tagesgeld bekommt den langfristigen Satz, alles
       andere (ein Girokonto) nichts. Ein Verrechnungskonto mit Zinsen hat die
       Art `giro` und bekommt seinen Satz deshalb nur ueber einen Eintrag.
    """
    treffer = [z for z in saetze if z.gilt(monat)]
    if treffer:
        return max(treffer, key=lambda z: z.ab).satz
    if saetze:
        return langfristig
    return langfristig if art == VERZINST else 0.0


def _mittel(werte: Sequence[float]) -> float:
    """Das Mittel; gleiche Werte bleiben exakt, damit nichts davon abdriftet."""
    if len(set(werte)) == 1:
        return werte[0]
    return math.fsum(werte) / len(werte)


def mischung(konten: Mapping[str, Konto], saetze: Mapping[str, Sequence[Zinssatz]],
             monate: Iterable[date], langfristig: float) -> Mischung:
    """Der Satz des Topfs fuer die Monate eines Jahres.

    Satz = Summe ueber die Konten mit positivem Stand von Stand mal Satz des
    Kontos, geteilt durch die Summe der Staende. Der Satz eines Kontos ist das
    Mittel seiner Monatssaetze. Ein leerer Topf verdient den langfristigen
    Satz. Was kuenftig dazukommt, verzinst sich mit derselben Mischung: eine
    Vereinfachung, die der Rechenweg ausspricht.
    """
    monate = list(monate)
    positiv = {k: v for k, v in konten.items() if v.cents > 0}
    gesamt = sum(v.cents for v in positiv.values())
    if not positiv or not monate:
        return Mischung(langfristig)
    je_konto = {
        k: _mittel([satz_im_monat(saetze.get(k, ()), v.art, m, langfristig)
                    for m in monate])
        for k, v in positiv.items()}
    verschieden = set(je_konto.values())
    satz = (next(iter(verschieden)) if len(verschieden) == 1
            else math.fsum(positiv[k].cents * je_konto[k] for k in positiv) / gesamt)
    teile = tuple(sorted(((k, positiv[k].cents / gesamt, je_konto[k]) for k in positiv),
                         key=lambda t: (-t[1], t[0])))
    return Mischung(satz, teile)


def zins_im_monat(stand_cents: int, satz: float) -> int:
    """Der Zins eines Monats: Stand zu Monatsbeginn mal Satz durch zwoelf.

    Ein Konto im Minus verdient nichts (und zahlt hier auch nichts: Dispozinsen
    kennt keine der beiden Rechnungen). Die Jahresrechnung verzinst den Stand zu
    Jahresbeginn mit dem Mittel der Monatssaetze; bei gleichem Stand und gleichem
    Satz ist die Summe der zwoelf Monate dieselbe Zahl.
    """
    return round(max(stand_cents, 0) * satz / 12)


def steuer_auf(ertrag: int, frei: int, steuer_quote: float) -> tuple[int, int, int]:
    """(Steuer, verbrauchter Pauschbetrag, Pauschbetrag danach) auf einen Ertrag.

    Erst der Freibetrag, dann der Satz. Beide Modelle rechnen mit dieser einen Funktion.
    """
    ertrag = max(ertrag, 0)
    verbraucht = min(frei, ertrag)
    return round((ertrag - verbraucht) * steuer_quote), verbraucht, frei - verbraucht


def freibetrag_im_jahr(pauschbetrag: int, restmonate: int) -> int:
    """Was vom Sparerpauschbetrag in einem Jahr gilt, von dem noch `restmonate` kommen.

    Das erste Jahr der Projektion hat nur seine Restmonate: Die Zinsen davor stehen im
    Bestand, und der Pauschbetrag gilt nur anteilig, wie in der Jahresrechnung.
    """
    return round(max(pauschbetrag, 0) * restmonate / 12)


def steuerplan(zinsen: Mapping[tuple[str, date], int], *, pauschbetrag: int,
               steuer_quote: float, erster_monat: date) -> dict[tuple[str, date], int]:
    """Die Steuer auf Zinsen je Konto und Monat, aus den Zinsen aller Konten.

    Der Freibetrag gilt fuer den Haushalt und das Kalenderjahr, ueber alle Konten.
    Die Zinsen laufen Monat fuer Monat in einen Zaehler; die Steuer ist die auf den
    Stand des Zaehlers (`steuer_auf`: erst der Pauschbetrag, dann der Satz) minus die
    schon gezahlte. Sie faellt also erst, wenn die Zinsen des Jahres den Pauschbetrag
    uebersteigen -- im Monat, in dem das geschieht, und danach mit jedem Monat --, und
    ueber ein volles Jahr ist sie genau die Steuer, die die Jahresrechnung auf die
    Jahressumme rechnet. Jedes Konto zahlt seinen Anteil an den Zinsen des Monats
    (der Topf, in dem der Ertrag entstand); was beim Teilen uebrig bleibt, bekommt das
    Konto mit dem groessten Rest, bei Gleichstand das mit dem kleineren Namen.

    `zinsen` sind positive Cent je (Konto, Monatserster); `erster_monat` ist der erste
    Monat der Projektion.
    """
    plan: dict[tuple[str, date], int] = {}
    monate = sorted({m for _, m in zinsen})
    zaehler = 0
    gezahlt = 0
    jahr = None
    frei = 0
    for monat in monate:
        if monat.year != jahr:
            jahr, zaehler, gezahlt = monat.year, 0, 0
            rest = 13 - erster_monat.month if jahr == erster_monat.year else 12
            frei = freibetrag_im_jahr(pauschbetrag, rest)
        je_konto = {k: c for (k, m), c in zinsen.items() if m == monat and c > 0}
        zaehler += sum(je_konto.values())
        steuer = steuer_auf(zaehler, frei, steuer_quote)[0] - gezahlt
        gezahlt += steuer
        if steuer > 0:
            plan.update({(k, monat): c for k, c in _teilen(steuer, je_konto).items() if c})
    return plan


def _teilen(betrag: int, anteile: Mapping[str, int]) -> dict[str, int]:
    """`betrag` im Verhaeltnis der Anteile, auf den Cent, ohne dass etwas verloren geht."""
    gesamt = sum(anteile.values())
    unten = {k: betrag * a // gesamt for k, a in anteile.items()}
    reihenfolge = sorted(anteile, key=lambda k: (-(betrag * anteile[k] % gesamt), k))
    for k in reihenfolge[:betrag - sum(unten.values())]:
        unten[k] += 1
    return unten
