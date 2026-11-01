"""Verfahren: wie aus gemessenen Monaten ein Betrag wird.

Die Messung (`messung.py`) sagt, was je Monat gebucht wurde. Ein Verfahren
macht daraus den Betrag, der fortgeschrieben wird. Es sind reine Funktionen:
Eingabe ist eine Monatsreihe und die Einstellung des Fensters, nie eine
Datenbankverbindung, und was herauskommt ist ein `Ergebnis` mit seinem
Rechenweg. Wer ein Verfahren aendern will, aendert es an einer Stelle und kann
es mit einer erfundenen Reihe pruefen.

Welches Verfahren fuer welche Art Kategorie gilt, steht NICHT in den Funktionen,
sondern in einer Tabelle je Vorschau (`KONTOPROGNOSE`, `HOCHRECHNUNG`).
Die Vorschau reicht ihre Tabelle herein; die Verfahren wissen nichts davon,
wer sie ruft.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from finctl.forecast.herkunft import Posten, eur_genau, prozent

#: Die Arten, in die eine Kategorie fuer die Tabelle faellt.
FIXKOSTEN, KOSTEN, EINNAHME = "fixkosten", "kosten", "einnahme"


def add_months(d: date, months: int) -> date:
    index = d.month - 1 + months
    return date(d.year + index // 12, index % 12 + 1, 1)


def _mm(monat: str) -> str:
    return f"{monat[5:7]}/{monat[:4]}"


@dataclass(frozen=True, slots=True)
class Einstellung:
    """Das Fenster, unter dem eine Kategorie verrechnet wird.

    Sie stehen zusammen, weil sie zusammen gelten: die Wege, auf denen aus
    gemessenen Monaten ein Betrag wird, brauchen fast dieselben Werte, und
    jeder Weg als Funktion mit zehn Parametern waere eine Liste, die man beim
    Aufruf abzaehlen muss.
    """

    #: Jaehrliche Steigerung, nur fuer den Text des Rechenwegs.
    rate: float
    since: str
    ende_monat: str
    fenster_monate: int
    is_fixed: set[str]


@dataclass(frozen=True, slots=True)
class Ergebnis:
    """Ein Betrag mit dem Weg, auf dem er entstand.

    `every_months` und `starts` sind nur bei einer Reihe mit festem Takt
    gesetzt (`fortschreibung._reihen_posten`): Ihr Betrag je Termin wird an
    seinem Termin gebucht, nicht auf ein Zwoelftel geglaettet. `letzte_monate`
    ist nur bei Juengst gesetzt: ueber wie viele der letzten Monate des Fensters
    die Summe zaehlt; 0 heisst das ganze Fenster.
    """

    cents: int
    herkunft: Posten
    every_months: int = 1
    starts: date | None = None
    letzte_monate: int = 0


@dataclass(frozen=True, slots=True)
class Regel:
    """Was fuer eine Art Kategorie gilt.

    `verfahren`: "schnitt" oder "summe". `fenster`: "juengst" zaehlt von der
    Summe nur die letzten drei Monate des Fensters (`JUENGST_MONATE`) und gilt
    deshalb nur fuer `verfahren="summe"`.
    """

    verfahren: Literal["schnitt", "summe"]
    fenster: Literal["kurz", "juengst"] = "kurz"

    def __post_init__(self) -> None:
        if self.fenster == "juengst" and self.verfahren != "summe":
            raise ValueError("das Fenster \"juengst\" gilt nur fuer die Summe")


Regeln = dict[str, Regel]

#: Die Hochrechnung rechnet jede Kategorie gleich: Summe des Fensters aufs Jahr.
HOCHRECHNUNG: Regeln = {
    FIXKOSTEN: Regel("summe"),
    KOSTEN: Regel("summe"),
    EINNAHME: Regel("summe"),
}

#: Wie `HOCHRECHNUNG`, nur zaehlen Kosten die letzten drei Monate. Einnahmen und
#: Fixkosten bleiben beim ganzen Fenster: Ein Nebenjob, der einmal im Jahr zahlt,
#: waere in drei Monaten null oder das Vierfache. Welche Bloecke diese Tabelle
#: bekommen, sagt die Vorschau (`Vorschau.regeln_je_block`).
HOCHRECHNUNG_JUENGST: Regeln = {
    **HOCHRECHNUNG,
    KOSTEN: Regel("summe", fenster="juengst"),
}

#: Wie viele der letzten Monate Jüngst zaehlt.
JUENGST_MONATE = 3

#: Die Kontoprognose rechnet dieselbe Summe des Fensters wie `HOCHRECHNUNG`, nur als
#: Monatsrate (`schnitt`) statt aufs Jahr: Summe durch die Monate des Fensters, fuer
#: Kosten wie Einnahmen, und gilt fuer das, was in keiner Reihe mit festem Takt
#: steht. Eine Zeile fuer Fixkosten gibt es nicht: Ihr Takt steckt in den Reihen,
#: und was davon uebrig bleibt, rechnet wie jede Kategorie (`wahl`).
KONTOPROGNOSE: Regeln = {
    KOSTEN: Regel("schnitt"),
    EINNAHME: Regel("schnitt"),
}


def art_der_kategorie(kategorie: str, betraege: list[int], is_fixed: set[str]) -> str:
    if kategorie in is_fixed:
        return FIXKOSTEN
    return KOSTEN if sum(betraege) < 0 else EINNAHME


def summe_aufs_jahr(cents: int, monate: int) -> int:
    """Die Summe eines Fensters als Jahresbetrag, auf Haushaltsebene gerundet."""
    return round(cents / monate * 12)


def summe(kategorie: str, betraege: list[int], cfg: Einstellung) -> Ergebnis | None:
    """Die Hochrechnung: Summe des Fensters aufs Jahr, ohne Mindestzahl.

    Auch eine Nullsumme bleibt ein Ergebnis: die Hochrechnung fuehrt eine
    Kategorie, die sich im Fenster aufhebt, weiter mit null, und ihre Bloecke
    sind die Summe ihrer Kategorien. Ohne Monate im Fenster gibt es nichts,
    wodurch die Summe zu teilen waere.
    """
    if not cfg.fenster_monate:
        return None
    gesamt = sum(betraege)
    jahr = summe_aufs_jahr(gesamt, cfg.fenster_monate)
    text = (f"Summe {eur_genau(gesamt)} über {cfg.fenster_monate} Monate, "
            f"aufs Jahr {eur_genau(jahr)}")
    return Ergebnis(jahr, _gemessen(kategorie, jahr, text))


def juengst(kategorie: str, monate: list[str], betraege: list[int],
            cfg: Einstellung) -> Ergebnis | None:
    """Die Summe der letzten drei Monate des Fensters aufs Jahr.

    Gemessen wird weiter das ganze Fenster: Eine Kategorie ohne Buchung in
    diesen Monaten ergibt null und bleibt als Posten mit null stehen, damit
    beide Tempi dieselbe Menge Posten zeigen. Ist das Fenster juenger als drei
    Monate, zaehlt es ganz und die Summe wird durch seine Monate geteilt.
    """
    if not cfg.fenster_monate or not cfg.ende_monat:
        return None
    n = min(JUENGST_MONATE, cfg.fenster_monate)
    ende = date(int(cfg.ende_monat[:4]), int(cfg.ende_monat[5:7]), 1)
    erster = add_months(ende, -(n - 1))
    von = f"{erster.year}-{erster.month:02d}"
    gesamt = sum(c for m, c in zip(monate, betraege, strict=True) if m >= von)
    jahr = summe_aufs_jahr(gesamt, n)
    zeitraum = (f"den letzten Monat ({_mm(cfg.ende_monat)})" if n == 1 else
                f"die letzten {n} Monate ({_mm(von)}–{_mm(cfg.ende_monat)})")
    text = (f"Summe {eur_genau(gesamt)} über {zeitraum}, "
            f"aufs Jahr {eur_genau(jahr)}")
    return Ergebnis(jahr, _gemessen(kategorie, jahr, text), letzte_monate=n)


def schnitt(kategorie: str, monate: list[str], betraege: list[int],
            cfg: Einstellung) -> Ergebnis | None:
    """Die Monatsrate: Summe des Fensters durch seine Monate, Monate ohne Buchung als null.

    Dasselbe wie `summe`, nur nicht aufs Jahr: Ueber die Konten summiert ergibt sie
    die Zahl des Haushalts. Ohne Monate im Fenster gibt es nichts zu teilen.
    """
    if not cfg.fenster_monate:
        return None
    durchschnitt = round(sum(betraege) / cfg.fenster_monate)
    if not durchschnitt:
        return None
    verlauf = sorted(zip(monate, betraege, strict=True))
    text = (f"Summe {eur_genau(sum(betraege))} über {cfg.fenster_monate} vollständige "
            f"Monate, im Monat {eur_genau(durchschnitt)} ({len(verlauf)} mit Buchung): "
            + ", ".join(f"{_mm(m)} {eur_genau(c)}" for m, c in verlauf)
            + (f"; steigt mit {prozent(cfg.rate)} im Jahr, stetig ab der Mitte des Fensters"
               if cfg.rate else ""))
    return Ergebnis(durchschnitt, _gemessen(kategorie, durchschnitt, text))


def wahl(kategorie: str, monate: list[str], betraege: list[int],
         cfg: Einstellung, regeln: Regeln) -> Ergebnis | None:
    """Welcher Weg fuer diese Kategorie gilt -- nach der Tabelle der Vorschau.

    Eine Tabelle ohne Zeile fuer Fixkosten (die Kontoprognose) rechnet sie nach
    dem Vorzeichen wie jede Kategorie.
    """
    art = art_der_kategorie(kategorie, betraege, cfg.is_fixed)
    regel = regeln.get(art) or regeln[KOSTEN if sum(betraege) < 0 else EINNAHME]
    if regel.verfahren == "summe":
        if regel.fenster == "juengst":
            return juengst(kategorie, monate, betraege, cfg)
        return summe(kategorie, betraege, cfg)
    return schnitt(kategorie, monate, betraege, cfg)


def _gemessen(kategorie: str, cents: int, herleitung: str) -> Posten:
    """Der Rechenweg einer aus Monatssummen gemessenen Kategorie."""
    return Posten(label=kategorie, cents=cents, quelle="gemessen",
                  herleitung=herleitung, verweis=kategorie)
