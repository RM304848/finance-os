"""Die Fortschreibung: Messung, Reihe bilden, Verfahren waehlen.

Kontoprognose und Hochrechnung schreiben dasselbe fort und unterscheiden sich
nur darin, was sie dafuer waehlen: welche Reihe (die eines Kontos oder die des
Haushalts, ueber alle Konten addiert), welches Verfahren je Art Kategorie,
welche Buchungen die Messung nicht sieht. Genau das steht in einer `Vorschau`,
als Wert. Das Wissen, wie aus Monatssummen ein Posten wird, steht in
`messung.py` und `verfahren.py`, nicht hier.

Welche Reihe es ist, entscheidet die Vorschau, nicht das Verfahren: Ein
Verfahren rechnet auf einer Monatsreihe und weiss nicht, ob sie von einem Konto
oder vom Haushalt stammt. Bei `reihe="haushalt"` rundet es deshalb von selbst
einmal auf der Haushaltssumme, nicht je Konto.

Hat eine Vorschau `reihen`, teilt jeder Schluessel sich in die Reihen mit festem
Takt (`takt.py`) und den Rest: Eine Reihe zaehlt mit ihrem Betrag je Termin mal
Termine je Jahr (die Hochrechnung) oder als Posten mit ihrem Termin (die
Kontoprognose), nicht mit der Summe ihrer Monate; was in keiner Reihe mit Takt
steht, rechnet das Verfahren wie bisher. Die Reihen kommen als Wert herein.

Wer eine `Vorschau` baut, steht bei seiner Vorschau (`konten.kontoprognose`,
`jahre._hochrechnung`), nicht hier: Der Kern nimmt Werte und liest keine
Konfiguration. `tests/test_fortschreibung.py` haelt seine Importe fest.
"""

from __future__ import annotations

import itertools
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from finctl.forecast import messung, takt, verfahren
from finctl.forecast.herkunft import Posten
from finctl.forecast.messung import Monatssumme, Teil
from finctl.forecast.verfahren import add_months


@dataclass(frozen=True, slots=True)
class Vorschau:
    """Wie eine Vorschau fortschreibt. Ein Wert, kein Wissen im Code."""

    reihe: Literal["konto", "haushalt"]
    regeln: verfahren.Regeln
    ausschluss: messung.Ausschluss
    #: Hochrechnung: ja, die Kategorie steht je Block fuer sich. Kontoprognose: nein.
    je_block: bool
    #: Beginn des Fensters, einschliesslich.
    since: str
    #: Ende des Fensters, einschliesslich. None: kein Ende.
    until: str | None = None
    #: Jaehrliche Steigerung. Die Kontoprognose bucht damit (`escalation_pa`
    #: jedes Postens, stetig ab der Mitte des Fensters); im Verfahren erscheint sie
    #: nur im Text des Rechenwegs.
    steigerung: float = 0.0
    #: Kategorien, die NACH der Messung herausfallen (Kredite, Abwahl).
    ausser: frozenset[str] = frozenset()
    #: Bekannte Enden je Kategorie.
    enden: Mapping[str, date] = field(default_factory=dict)
    #: Die Monate des Fensters, durch die jede Summe geteilt wird: die des Haushalts
    #: (`abgleich.Fenster.monate`), fuer jedes Konto gleich. Ein Konto, das juenger
    #: ist, traegt nur, was es gemessen hat; ueber die Konten ergibt sich die Zahl
    #: der Hochrechnung. Null: nichts gemessen, nichts zu teilen. Eine Vorschau
    #: muss sie nennen.
    fenster_monate: int | None = None
    #: Eine eigene Tabelle fuer einzelne Bloecke; ein Block, der hier fehlt,
    #: nimmt `regeln`. Nur mit `je_block=True`: ohne Block gibt es keinen Schluessel.
    regeln_je_block: Mapping[str, verfahren.Regeln] = field(default_factory=dict)
    #: Die Reihen mit ihrem Takt (`takt.reihen`, ein Stichtag, einmal gelesen).
    #: Gesetzt: Reihen mit festem Takt zaehlen mit ihrem Jahreswert (Haushalt, je
    #: Block) oder als Posten mit Termin (Konto, `Reihen.fuer_konto`), der Rest
    #: rechnet nach `regeln`.
    reihen: takt.Reihen | None = None

    def __post_init__(self) -> None:
        if self.regeln_je_block and not self.je_block:
            raise ValueError("regeln_je_block braucht je_block=True")
        if self.reihen is not None and self.reihe == "haushalt" and not self.je_block:
            raise ValueError("Reihen mit Takt gelten für den Haushalt je Block")
        if self.reihen is not None and (self.reihe == "konto") != bool(self.reihen.konto):
            raise ValueError("die Reihen eines Kontos gehören zur Kontoprognose, "
                             "die des Haushalts zur Hochrechnung")


@dataclass(frozen=True, slots=True)
class Fortgeschrieben:
    """Ein fortgeschriebener Posten mit seinem Schluessel.

    `konto` ist bei `reihe="haushalt"` leer, `block` bei `je_block=False`.
    `gemessen_bis` ist der letzte Monat, aus dem die Reihen dieses Schluessels
    (Konto) etwas gemessen haben.
    """

    konto: str
    kategorie: str
    block: str | None
    ergebnis: verfahren.Ergebnis
    ende: date | None
    gemessen_bis: date | None
    #: Nur mit `Vorschau.reihen`: bei einer Reihe mit festem Takt ihre Gegenpartei,
    #: ihr Takt und was sie beitraegt, beim Rest einer Kategorie `reihe=""` und
    #: seine Monate (`monate`), damit die Wirkung sie nennen kann. `ergebnis.cents`
    #: ist bei der Hochrechnung der Jahreswert der Reihe, bei der Kontoprognose
    #: ihr Betrag je Termin.
    reihe: str = ""
    takt: int | None = None
    beitrag: takt.Beitrag | None = None
    monate: tuple[Monatsbetrag, ...] = ()


@dataclass(frozen=True, slots=True)
class Monatsbetrag:
    """Was ein Monat zum Rest einer Kategorie beitrug: Cent und Zahl der Buchungen."""

    monat: str              # 'JJJJ-MM'
    cents: int
    buchungen: int


@dataclass(frozen=True, slots=True)
class Zerlegung:
    """Woraus der Jahreswert einer Kategorie besteht: ihre Reihen mit festem Takt
    (auch beendete, mit null) und der Rest. Ihre Summe ist der Jahreswert."""

    reihen: tuple[Fortgeschrieben, ...]
    rest_cents: int
    rest_monate: tuple[Monatsbetrag, ...]

    @property
    def cents(self) -> int:
        return sum(r.ergebnis.cents for r in self.reihen) + self.rest_cents


@dataclass(frozen=True, slots=True)
class Gemessen:
    """Was die Messung aus dem Hauptbuch liest: Monatssummen je Reihe.

    Sie haengt nur an dem, was eine `Vorschau` misst (Fenster, Ausschluss,
    Blockschluessel), nicht an dem, wie sie daraus rechnet. Zwei Vorschauen, die
    sich nur in ihrer Tabelle unterscheiden (Schnitt und Juengst der Hochrechnung),
    teilen sich deshalb eine Messung statt zweier Abfragen.
    """

    #: Was die Messung bestimmt hat; `fortschreiben` prueft, dass die Vorschau
    #: dazu passt.
    messt: tuple
    is_fixed: frozenset[str]
    summen: Mapping[tuple[str, str, str | None, str], int]
    letzter: Mapping[str, date]
    #: Die Teile des Fensters; nur gelesen, wo die Vorschau Reihen hat.
    teile: tuple[Teil, ...] | None = None


def _messt(v: Vorschau) -> tuple:
    return (v.reihe, v.ausschluss, v.je_block, v.since, v.until)


def messen(conn: sqlite3.Connection, vorschau: Vorschau, *,
           konten: frozenset[str] | None = None) -> Gemessen:
    """Die Monatssummen im Fenster der Vorschau, je Konto, Kategorie und Block."""
    # Welche Kategorien vertraglich wiederkehren. Entscheidet, ob eine
    # Position mit zwei Buchungen eine Jahreszahlung ist oder ein Zufall --
    # und welches Fenster fuer sie gilt.
    is_fixed = {r[0] for r in conn.execute(
        "SELECT id FROM mgmt_categories WHERE fixkosten = 1")}
    zeilen = messung.monatssummen(
        conn, von=vorschau.since, bis=vorschau.until, konten=konten,
        ausschluss=vorschau.ausschluss, je_block=vorschau.je_block)

    konto_von = _konto_von(vorschau)
    summen = messung.summiere(zeilen, lambda z: (konto_von(z), z.kategorie, z.block, z.monat))
    teile = None if vorschau.reihen is None else tuple(messung.teile(
        conn, von=vorschau.since, bis=vorschau.until, konten=konten,
        ausschluss=vorschau.ausschluss, je_block=vorschau.je_block))
    return Gemessen(_messt(vorschau), frozenset(is_fixed), summen,
                    _letzte_monate(zeilen, konto_von), teile)


def fortschreiben(conn: sqlite3.Connection, vorschau: Vorschau,
                  gemessen: Gemessen) -> list[Fortgeschrieben]:
    """Je Reihe `verfahren.wahl`, auf einer fertigen Messung.

    Sortiert nach Konto, Kategorie, Block. Eine Reihe, fuer die kein Verfahren
    einen Posten liefert, fehlt.
    """
    if _messt(vorschau) != gemessen.messt:
        raise ValueError("die Vorschau misst anders als die Messung, auf der sie rechnet")
    summen, letzter = gemessen.summen, gemessen.letzter
    is_fixed = set(gemessen.is_fixed)
    reihen_posten: list[Fortgeschrieben] = []
    rest_monate: dict[tuple[str, str, str | None], tuple[Monatsbetrag, ...]] = {}
    if vorschau.reihen is not None:
        if gemessen.teile is None:
            raise ValueError("die Messung hat keine Teile: Reihen mit Takt brauchen sie")
        summen, rest_monate, im_fenster = _rest(vorschau, gemessen.teile)
        reihen_posten = _reihen_posten(vorschau, im_fenster, letzter)

    # Das Fenster haengt am Konto (sein letzter Monat), nicht an der Kategorie: einmal rechnen.
    einstellungen: dict[str, verfahren.Einstellung] = {}
    ergebnis: list[Fortgeschrieben] = []
    for (konto, kategorie, block), gruppe in itertools.groupby(
            sorted(summen), key=lambda k: k[:3]):
        if kategorie in vorschau.ausser:
            continue
        monate_und_cents = [(k[3], summen[k]) for k in gruppe]
        ende = vorschau.enden.get(kategorie)
        if konto not in einstellungen:
            einstellungen[konto] = _einstellung(
                vorschau, letzter.get(konto), is_fixed)
        erg = verfahren.wahl(
            kategorie, [m for m, _ in monate_und_cents],
            [c for _, c in monate_und_cents], einstellungen[konto],
            vorschau.regeln_je_block.get(block, vorschau.regeln))
        if erg is not None:
            ergebnis.append(Fortgeschrieben(
                konto, kategorie, block, erg, ende, letzter.get(konto),
                monate=rest_monate.get((konto, kategorie, block), ())))
    return sorted([*reihen_posten, *ergebnis], key=_reihenfolge)


def fortschreibung(conn: sqlite3.Connection, vorschau: Vorschau, *,
                   konten: frozenset[str] | None = None) -> list[Fortgeschrieben]:
    """Messung, Reihe bilden, je Reihe `verfahren.wahl`."""
    return fortschreiben(conn, vorschau, messen(conn, vorschau, konten=konten))


def _reihenfolge(p: Fortgeschrieben) -> tuple:
    """Konto, Kategorie, Block; darin die Reihen vor dem Rest, die groesste zuerst.

    Nach Groesse, Takt und letztem Termin statt nach der Gegenpartei: Der Rechenweg
    zeigt Namen, die der Haushalt aendern kann, und seine Reihenfolge haengt nicht
    daran. Erst bei gleicher Groesse, gleichem Takt und gleichem letzten Termin
    entscheidet der Name."""
    letzter = p.beitrag.letzter_termin if p.beitrag else date.min
    return (p.konto, p.kategorie, p.block or "", p.reihe == "", -abs(p.ergebnis.cents),
            p.takt or 0, letzter, p.reihe)


def _rest(vorschau: Vorschau, teile: tuple[Teil, ...],
          ) -> tuple[dict[tuple[str, str, str | None, str], int],
                     dict[tuple[str, str, str | None], tuple[Monatsbetrag, ...]],
                     set[tuple[str, str]]]:
    """Die Teile, die nach den Reihen mit festem Takt im Rest bleiben.

    Zurueck kommen ihre Monatssummen je Schluessel (wie `Gemessen.summen`), je
    Schluessel die Monate mit Buchungen, und die Reihen, von denen ein Teil im
    Fenster liegt. Ein Teil im Termin einer Reihe steckt in deren Jahreswert; ein
    Teil im Verlauf oder an einer beendeten Reihe zaehlt nirgends; ein Ausreisser,
    ein Teil ohne Gegenpartei und einer einer Reihe ohne festen Takt bleiben im
    Rest. Ein einmaliger Teil gehoert zu keiner Reihe.
    """
    assert vorschau.reihen is not None
    konto_von = _konto_von(vorschau)
    summen: dict[tuple[str, str, str | None, str], int] = {}
    kennungen: dict[tuple[str, str, str | None, str], set[str]] = {}
    gesehen: set[tuple[str, str]] = set()
    for teil in teile:
        reihe = takt.reihe_des_teils(vorschau.reihen, teil)
        if reihe is not None and reihe.fest:
            gesehen.add((reihe.gegenpartei, reihe.kategorie))
            if reihe.einordnen(teil.tag) != takt.IM_REST:
                continue
        k = (konto_von(teil), teil.kategorie, teil.block, teil.monat)
        summen[k] = summen.get(k, 0) + teil.cents
        kennungen.setdefault(k, set()).add(teil.dedup_hash)
    monate: dict[tuple[str, str, str | None], list[Monatsbetrag]] = {}
    for (konto, kategorie, block, monat), cents in sorted(summen.items()):
        monate.setdefault((konto, kategorie, block), []).append(
            Monatsbetrag(monat, cents, len(kennungen[(konto, kategorie, block, monat)])))
    return summen, {k: tuple(v) for k, v in monate.items()}, gesehen


def _reihen_posten(vorschau: Vorschau, im_fenster: set[tuple[str, str]],
                   letzter: Mapping[str, date]) -> list[Fortgeschrieben]:
    """Je Reihe mit festem Takt ein Posten.

    Hochrechnung: ihr Jahreswert, bei einer beendeten null. Eine beendete steht nur
    da, wenn ein Teil von ihr im Fenster liegt; eine laufende immer, auch wenn ihr
    letzter Termin vor dem Fenster liegt.

    Kontoprognose: ihr Betrag je Termin, gebucht an ihrem Termin (`every_months`
    und `starts`). Eine beendete Reihe bucht nichts und steht nicht da."""
    assert vorschau.reihen is not None
    konto = vorschau.reihen.konto
    aus = []
    for r in vorschau.reihen.reihen:
        b = r.beitrag
        if b is None or not r.fest or r.kategorie in vorschau.ausser:
            continue
        if konto:
            if not b.laeuft:
                continue
            ergebnis = _termin_posten(r, b, vorschau.reihen.stichtag)
        else:
            if r.block is None or not (b.laeuft or (r.gegenpartei, r.kategorie) in im_fenster):
                continue
            text = f"{r.gegenpartei}: {b.text}" + ("" if b.laeuft else ", 0,00 € im Jahr")
            ergebnis = verfahren.Ergebnis(b.jahreswert, Posten(
                label=r.kategorie, cents=b.jahreswert, quelle="gemessen",
                herleitung=text, verweis=r.kategorie))
        aus.append(Fortgeschrieben(
            konto, r.kategorie, None if konto else r.block, ergebnis,
            vorschau.enden.get(r.kategorie), letzter.get(konto),
            reihe=r.gegenpartei, takt=int(r.takt), beitrag=b))
    return aus


def _termin_posten(r: takt.Reihe, b: takt.Beitrag, stichtag: date) -> verfahren.Ergebnis:
    """Die Reihe eines Kontos als Posten mit Termin: ihr Betrag je Termin, der naechste
    Termin nach dem letzten. Ein ueberfaelliger, aber laufender Termin kommt im ersten
    offenen Monat, nicht in der Vergangenheit."""
    erster_offener = add_months(stichtag.replace(day=1), 1)
    naechster = max(add_months(b.letzter_termin.replace(day=1), int(r.takt)), erster_offener)
    text = (f"{r.gegenpartei}: {b.text}; nächster Termin "
            f"{naechster.month:02d}/{naechster.year}")
    return verfahren.Ergebnis(
        b.betrag_je_termin,
        Posten(label=r.kategorie, cents=b.betrag_je_termin, quelle="gemessen",
               herleitung=text, verweis=r.kategorie),
        every_months=int(r.takt), starts=naechster)


def _konto_von(vorschau: Vorschau) -> Callable[[Monatssumme | Teil], str]:
    """Zu welcher Reihe eine Zeile oder ein Teil gehoert: ihrem Konto, oder dem
    Haushalt ('')."""
    if vorschau.reihe == "konto":
        return lambda z: z.konto
    return lambda z: ""


def _letzte_monate(zeilen: list[Monatssumme],
                   konto_von: Callable[[Monatssumme | Teil], str]) -> dict[str, date]:
    """Der letzte gemessene Monat je Konto (bei der Haushaltsreihe: je '')."""
    letzter: dict[str, date] = {}
    for z in zeilen:
        monat = date(int(z.monat[:4]), int(z.monat[5:7]), 1)
        k = konto_von(z)
        letzter[k] = max(monat, letzter.get(k, monat))
    return letzter


def _einstellung(v: Vorschau, letzter: date | None, is_fixed: set[str]) -> verfahren.Einstellung:
    if v.fenster_monate is None:
        raise ValueError("eine Vorschau braucht fenster_monate")
    return verfahren.Einstellung(
        rate=v.steigerung, since=v.since,
        ende_monat=(v.until[:7] if v.until else
                    (f"{letzter.year}-{letzter.month:02d}" if letzter else "")),
        fenster_monate=v.fenster_monate, is_fixed=is_fixed)
