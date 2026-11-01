"""Der Takt einer Reihe: wie oft sie zahlt, und was sie je Termin zahlt.

Eine Zahlung, die regelmaessig kommt, ist kein Haufen von Monatssummen,
sondern eine Folge von Terminen. Eine Miete, deren Buchungstag ueber das
Monatsende rutscht, hat in einem Fenster von zwoelf Monaten dreizehn
Buchungen, und zwoelf Termine. Wer die Summe des Fensters aufs Jahr nimmt,
zaehlt den dreizehnten mit; wer den Betrag je Termin mal die Termine je Jahr
nimmt, nicht.

Eine Reihe ist Gegenpartei und Kategorie, ueber alle Konten (`ledger/reihe.py`).
Ihr Takt ist eine Zahl von Monaten (1, 2, 3, 4, 6, 12 -- die Teiler des Jahres)
oder ein Wort: `einmalig` oder `unregelmaessig`. DIE ERKENNUNG LIEFERT NIE
`einmalig`: Was einmal vorkam, kann wiederkommen, und eine Erkennung, die es
herausnaehme, verschwiege Ausgaben. `einmalig` kommt aus einer
Handentscheidung oder einem Merkmal der Kategorie, nicht von hier.

`erkennen` und `fortschreiben` sind reine Funktionen auf Listen von Buchungen
und Terminen: sie lesen weder die Datenbank noch Dateien. Nur `reihen` liest
(die Teile der letzten 24 Monate) und ruft beide je Reihe.
"""

from __future__ import annotations

import itertools
import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from finctl.forecast import abgleich, messung
from finctl.forecast.herkunft import eur_genau
from finctl.forecast.herkunft import monat as _mm
from finctl.forecast.verfahren import add_months
from finctl.ledger.reihe import TOLERANZ

EINMALIG = "einmalig"
UNREGELMAESSIG = "unregelmaessig"
Takt = int | Literal["einmalig", "unregelmaessig"]

#: Die festen Takte in Monaten: die Teiler des Jahres, wie `abos.yaml`.
FESTE_TAKTE = (1, 2, 3, 4, 6, 12)

#: Wie weit zurueck erkannt wird, ein Fenster fuer beide Vorschauen.
FENSTER_MONATE = 24
#: Wie weit ein Abstand von `takt` Monaten abweichen darf, als Anteil.
ABSTAND_TOLERANZ = 0.25
#: Wie viele der Abstaende (und, getrennt, der Betraege) passen muessen.
ANTEIL_REGELMAESSIG = 0.75
#: Eine Reihe ist beendet, wenn ihr naechster Termin um mehr als einen halben
#: Takt ueberfaellig ist, mindestens aber um einen ganzen Monat: Ein einzelner
#: fehlender Monatstermin (eine Lastschrift, die erst nach dem Stichtag kommt)
#: beendet keinen Vertrag; zwei tun es. Ab Takt 2 ist der halbe Takt groesser.
UEBERFAELLIG_TAKTE = 0.5
UEBERFAELLIG_MIN_MONATE = 1
#: Aus wie vielen der letzten Termine der Betrag je Termin der Median ist.
LETZTE_TERMINE = 3
#: Ueber wie viele Monate zurueck Termine fuer den Betrag zaehlen.
BETRAGSFENSTER_MONATE = 12
#: Mindestzahl Termine; bei `jaehrlich` genuegen zwei.
MIN_TERMINE = 3
MIN_TERMINE_JAEHRLICH = 2
#: Wie viele Termine ab der geltenden Hoehe zum Betrag passen muessen: Eine
#: Erhoehung ist nach zwei Terminen eine Reihe. Bei `jaehrlich` genuegt einer
#: nur in einer Kategorie mit Fixkosten-Merkmal, wo ein Vertrag den Preis
#: aendert; sonst waeren zwei Einkaeufe beim selben Haendler, ein Jahr
#: auseinander und verschieden teuer, eine Jahreszahlung.
MIN_TERMINE_HOEHE = 2
MIN_TERMINE_HOEHE_JAEHRLICH_FIX = 1
#: Ab Takt 2 legt ein Termin hoechstens so viele Buchungstage zusammen: Raten
#: einer Praemie sind zwei oder drei, ein Halbjahr Tanken ist keine.
MAX_TAGE_JE_TERMIN = 3
#: Ein Jahr durch zwoelf, in Tagen.
TAGE_JE_MONAT = 365.2425 / 12

#: Wo ein Teil einer Reihe mit festem Takt in der Hochrechnung zaehlt: als Termin
#: des Takts (sein Betrag steckt im Jahreswert der Reihe), im Rest seiner
#: Kategorie (ein Ausreisser) oder nirgends (der Verlauf der Reihe, oder die Reihe
#: ist beendet).
IM_TAKT, IM_REST, NIRGENDS = "takt", "rest", "nirgends"


@dataclass(frozen=True, slots=True)
class Termin:
    """Ein Zahlungstermin: eine oder, bei Raten, mehrere benachbarte Buchungen.

    `tag` ist der der ersten Buchung, `cents` die Summe aller.
    """

    tag: date
    cents: int
    buchungen: tuple[tuple[date, int], ...]

    @property
    def tage(self) -> int:
        """Auf wie vielen verschiedenen Tagen die Buchungen liegen."""
        return len({tag for tag, _ in self.buchungen})


@dataclass(frozen=True, slots=True)
class Erkannt:
    """Der erkannte Takt und die Termine, aus denen er folgt (leer, wo
    `unregelmaessig`)."""

    takt: Takt
    termine: tuple[Termin, ...]


@dataclass(frozen=True, slots=True)
class Beitrag:
    """Was eine Reihe mit festem Takt fortgeschrieben beitraegt.

    `ausreisser` sind die Termine der letzten zwoelf Monate ab der geltenden
    Hoehe, deren Betrag zu weit vom Betrag je Termin liegt und die ausserdem
    weniger als einen halben Takt neben einem passenden Termin liegen: Sie
    kommen zusaetzlich, gehoeren nicht zum Takt, sondern zum Rest ihrer
    Kategorie. Ein abweichender Termin auf seinem eigenen Platz ist ein Termin
    des Takts mit anderem Betrag. `verlauf` sind die Termine vor
    der geltenden Hoehe, der Weg der Reihe bis zu ihrem heutigen Betrag: Sie
    zaehlen weder im Takt noch im Rest. `jahreswert` ist null, wo die Reihe
    beendet ist.
    """

    takt: int
    betrag_je_termin: int
    laeuft: bool
    letzter_termin: date
    ausreisser: tuple[Termin, ...]
    verlauf: tuple[Termin, ...]
    jahreswert: int
    text: str


def takt_name(takt: Takt) -> str:
    """Der Takt, wie ihn die Seiten nennen."""
    if takt == 1:
        return "monatlich"
    if takt == 12:
        return "jährlich"
    if isinstance(takt, int):
        return f"alle {takt} Monate"
    return "einmalig" if takt == EINMALIG else "unregelmäßig"


def _median(werte: list[int]) -> int:
    """Bei gerader Anzahl das obere mittlere Element:
    ein Betrag, der wirklich gebucht wurde."""
    return sorted(werte)[len(werte) // 2]


def _nah(cents: int, betrag: int) -> bool:
    """Gleiches Vorzeichen und hoechstens `TOLERANZ` vom Betrag entfernt."""
    return cents * betrag > 0 and abs(cents - betrag) <= TOLERANZ * abs(betrag)


# ------------------------------------------------------------- Erkennen


def termine_bilden(buchungen: Iterable[tuple[date, int]], takt: int) -> tuple[Termin, ...]:
    """Buchungen zu Terminen zusammenlegen.

    Buchungen am selben Tag sind bei jedem Takt ein Termin: Abschlag und
    Gebuehr beim selben Empfaenger. Ab Takt 2 gehoert eine Buchung zum Termin
    davor, wenn sie weniger als einen halben Takt nach dessen erster Buchung
    liegt: eine Jahrespraemie in zwei Raten im Januar und Februar ist ein
    Termin.
    """
    grenze = takt * TAGE_JE_MONAT / 2 if takt > 1 else 1
    gruppen: list[list[tuple[date, int]]] = []
    for buchung in sorted(buchungen):
        if gruppen and (buchung[0] - gruppen[-1][0][0]).days < grenze:
            gruppen[-1].append(buchung)
        else:
            gruppen.append([buchung])
    return tuple(Termin(g[0][0], sum(c for _, c in g), tuple(g)) for g in gruppen)


def _abstaende_regelmaessig(termine: tuple[Termin, ...], takt: int) -> bool:
    soll = takt * TAGE_JE_MONAT
    abstaende = [(b.tag - a.tag).days for a, b in itertools.pairwise(termine)]
    passend = sum(1 for d in abstaende if abs(d - soll) <= ABSTAND_TOLERANZ * soll)
    return bool(abstaende) and passend >= ANTEIL_REGELMAESSIG * len(abstaende)


def _ohne_luecke(termine: tuple[Termin, ...], takt: int) -> bool:
    """Die Zahl der Abstaende ist mindestens drei Viertel der Spanne vom ersten
    zum letzten Termin, gemessen in Takten: Drei Raten einer Jahrespraemie in
    drei Folgemonaten sind kein monatlicher Takt, auch wenn vier von fuenf
    Abstaenden einen Monat lang sind."""
    spanne = (termine[-1].tag - termine[0].tag).days / (takt * TAGE_JE_MONAT)
    return len(termine) - 1 >= ANTEIL_REGELMAESSIG * spanne


def _traegt(termine: tuple[Termin, ...], takt: int, stichtag: date | None,
            fixkosten: bool) -> bool:
    """Genug Termine, nicht zu viele Tage je Termin, regelmaessiger Abstand ohne
    Luecke, und ab der geltenden Hoehe genug Termine."""
    mindest = MIN_TERMINE_JAEHRLICH if takt == 12 else MIN_TERMINE
    if len(termine) < mindest or not _abstaende_regelmaessig(termine, takt):
        return False
    if not _ohne_luecke(termine, takt):
        return False
    if takt > 1 and any(t.tage > MAX_TAGE_JE_TERMIN for t in termine):
        return False
    betrag, _ = _betrag_je_termin(termine, takt, stichtag or termine[-1].tag)
    beginn = beginn_der_hoehe(termine, betrag)
    hoehe = (MIN_TERMINE_HOEHE_JAEHRLICH_FIX if takt == 12 and fixkosten
             else MIN_TERMINE_HOEHE)
    return beginn is not None and len(termine) - beginn >= hoehe


def erkennen(buchungen: list[tuple[date, int]], *, fixkosten: bool,
             stichtag: date | None = None) -> Erkannt:
    """Der Takt einer Reihe aus ihren Buchungen `(Tag, Cent)`.

    Der erste Takt in der Reihenfolge 1, 2, 3, 4, 6, 12, dessen Termine genug
    sind, regelmaessig und ohne Luecke liegen und ab der geltenden Hoehe (zwei
    Termine, jaehrlich einer) gleich viel zahlen.
    Keiner: `unregelmaessig`, ausser bei einer Kategorie mit Fixkosten-Merkmal,
    die im Fenster genau einen Termin (als Jahrestermin gebildet, mit hoechstens
    `MAX_TAGE_JE_TERMIN` Buchungstagen) hat: Die gilt als jaehrlich, damit die
    Kontoprognose nicht verliert, was ihr Jahresposten heute findet.

    `stichtag` bestimmt, welche Termine zum Betrag je Termin zaehlen (die der
    letzten zwoelf Monate); ohne ihn der Tag der letzten Buchung.
    """
    for takt in FESTE_TAKTE:
        termine = termine_bilden(buchungen, takt)
        if _traegt(termine, takt, stichtag, fixkosten):
            return Erkannt(takt, termine)
    if fixkosten:
        jaehrlich = termine_bilden(buchungen, 12)
        if len(jaehrlich) == 1 and jaehrlich[0].tage <= MAX_TAGE_JE_TERMIN:
            return Erkannt(12, jaehrlich)
    return Erkannt(UNREGELMAESSIG, ())


# --------------------------------------------------------- Fortschreiben


def _monatsende(tag: date) -> date:
    return add_months(tag.replace(day=1), 1) - timedelta(days=1)


def _betragsfenster(termine: tuple[Termin, ...], stichtag: date) -> list[Termin]:
    """Die Termine der letzten zwoelf Monate; haette keiner dort Platz, der
    letzte, damit eine seltene Reihe einen Betrag behaelt."""
    von = add_months(stichtag.replace(day=1), -(BETRAGSFENSTER_MONATE - 1))
    return [t for t in termine if t.tag >= von] or [termine[-1]]


def _betrag_je_termin(termine: tuple[Termin, ...], takt: int,
                      stichtag: date) -> tuple[int, list[Termin]]:
    """Der Betrag je Termin und die Termine, aus deren Median er folgt: die
    letzten drei des Betragsfensters (jaehrlich: der letzte)."""
    gewaehlt = _betragsfenster(termine, stichtag)[-(1 if takt == 12 else LETZTE_TERMINE):]
    return _median([t.cents for t in gewaehlt]), gewaehlt


def beginn_der_hoehe(termine: tuple[Termin, ...], betrag: int) -> int | None:
    """Der Index des fruehesten Termins, ab dem der Betrag je Termin gilt.

    Das ist der fruehste Termin, der zum Betrag passt (gleiches Vorzeichen,
    hoechstens `TOLERANZ` entfernt) und ab dem mindestens drei Viertel der
    Termine bis zum letzten passen. Was davor liegt, ist der Verlauf der Reihe:
    Sie schreibt ihre neue Hoehe fort, die alte ist vorbei. Passt keine Stelle,
    zahlt die Reihe keinen gleichen Betrag: `None`.
    """
    beginn, passend = None, 0
    for i in range(len(termine) - 1, -1, -1):
        nah = _nah(termine[i].cents, betrag)
        passend += nah
        if nah and passend >= ANTEIL_REGELMAESSIG * (len(termine) - i):
            beginn = i
    return beginn


def _ausreisser(geltend: tuple[Termin, ...], betrag: int, takt: int,
                stichtag: date) -> tuple[Termin, ...]:
    """Die Termine der letzten zwoelf Monate, die zusaetzlich kommen: Der Betrag
    weicht ab, und weniger als einen halben Takt daneben liegt ein passender
    Termin. Ein abweichender Termin allein auf seinem Platz im Takt ist keiner.

    Ein Termin mit anderem Vorzeichen ist immer einer: Eine Erstattung ist
    keine Rate mit anderem Betrag, auch wenn der naechste passende Termin
    noch nicht gebucht ist und keiner neben ihr steht."""
    halb = takt * TAGE_JE_MONAT / 2
    passend = [t for t in geltend if _nah(t.cents, betrag)]
    return tuple(t for t in _betragsfenster(geltend, stichtag)
                 if t.cents * betrag < 0 or (
                     not _nah(t.cents, betrag)
                     and any(abs((t.tag - p.tag).days) < halb for p in passend)))


def _text(takt: int, betrag: int, jahr: int, gewaehlt: list[Termin],
          ausreisser: tuple[Termin, ...]) -> str:
    wo = (f"Median der letzten {len(gewaehlt)} Termine" if len(gewaehlt) > 1
          else f"letzter Termin {_mm(gewaehlt[-1].tag)}")
    text = (f"{takt_name(takt)}, je Termin {eur_genau(betrag)} ({wo}), "
            f"× {12 // takt} = {eur_genau(jahr)} im Jahr")
    if ausreisser:
        text += ("; 1 abweichender Termin zählt" if len(ausreisser) == 1 else
                 f"; {len(ausreisser)} abweichende Termine zählen") + " im Rest der Kategorie"
    return text


def fortschreiben(termine: tuple[Termin, ...], takt: int, *, stichtag: date) -> Beitrag:
    """Betrag je Termin, ob die Reihe noch laeuft, und ihr Jahreswert.

    Der Betrag je Termin ist der Median der Termine der letzten zwoelf Monate,
    hoechstens der letzten drei (jaehrlich: der letzte): So kommt eine
    Erhoehung nach zwei Terminen an und wird nicht von einem Jahr alter
    Beitraege ueberstimmt. Die Termine vor der geltenden Hoehe
    (`beginn_der_hoehe`) sind der Verlauf; hat die Reihe keine, etwa bei einem
    festgelegten Takt ueber streuende Betraege, gibt es keinen. Ein Termin ab der
    geltenden Hoehe, der mehr als `reihe.TOLERANZ` vom Betrag abweicht und
    weniger als einen halben Takt neben einem passenden Termin liegt, ist ein
    Ausreisser: Er kommt zusaetzlich. Ein abweichender Termin allein auf seinem
    Platz ist ein Termin des Takts; sein Monat steckt im Betrag je Termin mal
    12/t. Der Preis: Eine Schlussabrechnung, die mehr als einen halben Takt nach
    dem letzten Abschlag kommt, haelt eine gekuendigte Reihe laenger am Laufen.

    Eine Reihe laeuft, bis ihr naechster Termin um mehr als einen halben Takt
    ueberfaellig ist, mindestens aber um einen ganzen Monat
    (`UEBERFAELLIG_MIN_MONATE`): Liegt ihr letzter Termin des Takts (ohne
    Verlauf und Ausreisser) weiter vor dem Ende des Stichtagsmonats, ist sie
    beendet und hat den Jahreswert null. Monatlich heisst das: Ein fehlender
    Termin beendet sie nicht, zwei schon.
    """
    if takt not in FESTE_TAKTE or not termine:
        raise ValueError(f"kein fester Takt oder keine Termine: {takt!r}")
    betrag, gewaehlt = _betrag_je_termin(termine, takt, stichtag)
    beginn = beginn_der_hoehe(termine, betrag) or 0
    verlauf, geltend = termine[:beginn], termine[beginn:]
    ausreisser = _ausreisser(geltend, betrag, takt, stichtag)
    im_takt = [t for t in geltend if t not in ausreisser] or list(geltend)
    letzter = im_takt[-1].tag
    laeuft = (_monatsende(stichtag) - letzter).days <= (
        (takt + max(UEBERFAELLIG_TAKTE * takt, UEBERFAELLIG_MIN_MONATE)) * TAGE_JE_MONAT)
    if not laeuft:
        return Beitrag(takt, betrag, False, letzter, ausreisser, verlauf, 0,
                       f"{takt_name(takt)}, beendet, zuletzt {_mm(letzter)}")
    jahr = betrag * (12 // takt)
    return Beitrag(takt, betrag, True, letzter, ausreisser, verlauf, jahr,
                   _text(takt, betrag, jahr, gewaehlt, ausreisser))


# ----------------------------------------------------------------- Lesen


@dataclass(frozen=True, slots=True)
class Reihe:
    """Eine Reihe mit ihrem Takt. `beitrag` fehlt bei `unregelmaessig`.

    `block` ist der Block, in dem ihr letzter Termin liegt: dort steht ihr
    Jahreswert in der Hochrechnung, auch wenn ein Teil von ihr in einem anderen
    Block gemessen ist. Er fehlt bei einer Reihe ohne festen Takt.
    """

    gegenpartei: str
    kategorie: str
    takt: Takt
    #: True: der Haushalt hat den Takt festgelegt, False: erkannt.
    festgelegt: bool
    termine: tuple[Termin, ...]
    teile: tuple[messung.Teil, ...]
    beitrag: Beitrag | None
    block: str | None = field(init=False, default=None, compare=False)
    _einordnung: dict[date, str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_einordnung", _einordnen(self.termine, self.beitrag))
        if self.beitrag is not None:
            letzter = self.beitrag.letzter_termin
            object.__setattr__(self, "block", next(
                (t.block for t in self.teile if t.tag == letzter), None))

    @property
    def fest(self) -> bool:
        return isinstance(self.takt, int)

    @property
    def schreibweisen(self) -> tuple[str, ...]:
        """Die Gegenparteien, die der Haushalt in diese Reihe zusammengefuehrt hat
        (`zusammen`): die Schreibweisen ihrer Teile ausser dem Namen der Reihe."""
        return tuple(sorted({t.gegenpartei for t in self.teile} - {self.gegenpartei}))

    def auf_konto(self, teile: tuple[messung.Teil, ...], stichtag: date) -> Reihe:
        """Dieselbe Reihe, wie sie auf einem Konto aussieht: Den Takt hat die ganze
        Reihe, Termine, Betrag je Termin und ob sie laeuft folgen den Teilen dieses
        Kontos (Entscheidung 5). Ein Dauerauftrag, der das Konto gewechselt hat, ist
        auf dem alten beendet und laeuft auf dem neuen."""
        assert isinstance(self.takt, int) and teile
        termine = termine_bilden([(t.tag, t.cents) for t in teile], self.takt)
        return Reihe(self.gegenpartei, self.kategorie, self.takt, self.festgelegt, termine,
                     teile, fortschreiben(termine, self.takt, stichtag=stichtag))

    def einordnen(self, tag: date) -> str:
        """Wo ein Teil dieser Reihe am Buchungstag `tag` in der Hochrechnung zaehlt:
        `IM_TAKT`, `IM_REST` oder `NIRGENDS`. Eine Reihe ohne festen Takt hat
        keinen Termin: ihre Teile zaehlen im Rest."""
        return self._einordnung.get(tag, IM_REST)


def _einordnen(termine: tuple[Termin, ...], beitrag: Beitrag | None) -> dict[date, str]:
    """Je Buchungstag, wo sein Teil zaehlt (siehe `Reihe.einordnen`).

    Termine im Verlauf zaehlen nirgends, ebenso alles an einer beendeten Reihe,
    auch ein Ausreisser: eine beendete Reihe wird nicht fortgeschrieben, auch nicht
    im Rest. Ein Ausreisser einer laufenden Reihe kommt zusaetzlich, im Rest, und
    jeder andere Termin steckt im Jahreswert.
    """
    if beitrag is None:
        return {}
    verlauf = {t.tag for t in beitrag.verlauf}
    ausreisser = {t.tag for t in beitrag.ausreisser}
    aus: dict[date, str] = {}
    for termin in termine:
        if termin.tag in verlauf or not beitrag.laeuft:
            wo = NIRGENDS
        else:
            wo = IM_REST if termin.tag in ausreisser else IM_TAKT
        for tag, _ in termin.buchungen:
            aus[tag] = wo
    return aus


@dataclass(frozen=True, slots=True)
class Quelle:
    """Womit die Reihen erkannt wurden: was `ohne_buchungen` braucht, um die Reihen
    zu ersetzen, deren Buchungen herausfallen, ohne das Hauptbuch noch einmal zu lesen."""

    fixkosten: frozenset[str]
    festgelegt: Mapping[tuple[str, str], Takt]


@dataclass(frozen=True, slots=True)
class Reihen:
    """Die Reihen der 24 Monate bis zum Stichtag, sortiert nach Kategorie und
    Gegenpartei."""

    stichtag: date
    von: date
    reihen: tuple[Reihe, ...]
    #: Leer: die Reihen des Haushalts, ueber alle Konten. Sonst die Reihen mit festem
    #: Takt, wie sie auf diesem Konto aussehen (`fuer_konto`).
    konto: str = ""
    quelle: Quelle | None = field(default=None, repr=False, compare=False)
    _index: dict[tuple[str, str], Reihe] = field(init=False, repr=False, compare=False)
    _je_teil: dict[tuple[str, str], Reihe] = field(init=False, repr=False, compare=False)
    _konten: dict[str, Reihen] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Auch unter den zusammengefuehrten Schreibweisen: ein Teil sucht seine Reihe
        # mit der Gegenpartei, die die Buchung traegt.
        index = {(t.gegenpartei, t.kategorie): r for r in self.reihen for t in r.teile}
        index.update({(r.gegenpartei, r.kategorie): r for r in self.reihen})
        object.__setattr__(self, "_index", index)
        object.__setattr__(self, "_je_teil", {(t.dedup_hash, t.kategorie): r
                                              for r in self.reihen for t in r.teile})
        object.__setattr__(self, "_konten", {})

    def fuer_konto(self, konto: str) -> Reihen:
        """Die Reihen mit festem Takt, aus den Teilen eines Kontos gerechnet.

        Eine Reihe ohne Teil auf dem Konto fehlt; eine ohne festen Takt auch: Ihre
        Teile zaehlen dort im Rest, wie ohne Reihe. Einmal je Konto gerechnet.
        """
        if konto not in self._konten:
            aus = []
            for r in self.reihen:
                teile = tuple(t for t in r.teile if t.konto == konto)
                if r.fest and teile:
                    aus.append(r.auf_konto(teile, self.stichtag))
            self._konten[konto] = Reihen(self.stichtag, self.von, tuple(aus), konto)
        return self._konten[konto]

    def ohne(self, kategorien: Iterable[str]) -> Reihen:
        """Dieselben Reihen ohne die der genannten Kategorien: Ihre Teile zaehlen im Rest."""
        weg = frozenset(kategorien)
        if not weg:
            return self
        return Reihen(self.stichtag, self.von,
                      tuple(r for r in self.reihen if r.kategorie not in weg), self.konto,
                      self.quelle)

    def ohne_buchungen(self, hashes: Iterable[str]) -> Reihen:
        """Die Reihen des Haushalts, als haetten die Buchungen nie dagestanden.

        Nur die Reihen, die eine der Buchungen trugen, werden neu erkannt; ihr
        Takt kann sich aendern, und eine Reihe ohne Teil faellt weg. So rechnet ein
        Wegfall, was die Prognose fuer seine Reihe bucht, ohne das Hauptbuch noch
        einmal zu lesen. Nur fuer die Reihen des Haushalts (`fuer_konto` danach)."""
        weg = frozenset(hashes)
        if not weg or self.quelle is None or self.konto:
            return self
        aus = []
        for r in self.reihen:
            teile = [t for t in r.teile if t.dedup_hash not in weg]
            if len(teile) == len(r.teile):
                aus.append(r)
            elif teile:
                aus.append(_reihe(r.gegenpartei, r.kategorie, teile,
                                  fixkosten=r.kategorie in self.quelle.fixkosten,
                                  festgelegt=self.quelle.festgelegt.get(
                                      (r.gegenpartei, r.kategorie)),
                                  stichtag=self.stichtag))
        return Reihen(self.stichtag, self.von, tuple(aus), "", self.quelle)

    def nach_schluessel(self, gegenpartei: str, kategorie: str) -> Reihe | None:
        """Die Reihe zu einer Gegenpartei und Kategorie; die Gegenpartei darf eine
        zusammengefuehrte Schreibweise sein."""
        return self._index.get((gegenpartei, kategorie))

    def nach_teil(self, dedup_hash: str, kategorie: str) -> Reihe | None:
        """Die Reihe, zu der ein Teil gehoert (Kennung der Buchung und Kategorie
        des Teils); keine fuer einen Teil ohne Gegenpartei oder einen einmaligen."""
        return self._je_teil.get((dedup_hash, kategorie))


def _pruefe_festgelegt(festgelegt: Mapping[tuple[str, str], Takt]) -> None:
    for schluessel, takt in festgelegt.items():
        if takt not in (*FESTE_TAKTE, UNREGELMAESSIG):
            raise ValueError(
                f"{schluessel}: {takt!r} gilt nicht fuer eine ganze Reihe "
                f"(einmalig gilt fuer Buchungen)")


def zusammen_aufloesen(zusammen: Mapping[str, str]) -> dict[str, str]:
    """Je Schreibweise die Gegenpartei, unter der ihre Reihe steht: Zeigt ein Ziel selbst
    auf ein anderes, gilt das letzte der Kette. Ein Kreis (a auf b, b auf a) ist ein Fehler."""
    aus: dict[str, str] = {}
    for schreibweise in zusammen:
        gesehen = [schreibweise]
        ziel = zusammen[schreibweise]
        while ziel in zusammen:
            if ziel in gesehen:
                raise ValueError("zusammen: " + " -> ".join([*gesehen, ziel]) + " ist ein Kreis")
            gesehen.append(ziel)
            ziel = zusammen[ziel]
        aus[schreibweise] = ziel
    return aus


def _reihe(gegenpartei: str, kategorie: str, teile: list[messung.Teil], *,
           fixkosten: bool, festgelegt: Takt | None, stichtag: date) -> Reihe:
    buchungen = [(t.tag, t.cents) for t in teile]
    if festgelegt is None:
        erkannt = erkennen(buchungen, fixkosten=fixkosten, stichtag=stichtag)
    elif isinstance(festgelegt, int):
        erkannt = Erkannt(festgelegt, termine_bilden(buchungen, festgelegt))
    else:
        erkannt = Erkannt(festgelegt, ())
    beitrag = (fortschreiben(erkannt.termine, erkannt.takt, stichtag=stichtag)
               if isinstance(erkannt.takt, int) else None)
    return Reihe(gegenpartei, kategorie, erkannt.takt, festgelegt is not None,
                 erkannt.termine, tuple(teile), beitrag)


def _kann_reihe_sein(teil: messung.Teil) -> bool:
    """Ein Teil ohne Gegenpartei gehoert zu keiner Reihe, ein einmaliger
    (Block `einmalig`) auch nicht: Er kommt nicht wieder."""
    return bool(teil.gegenpartei) and teil.block != abgleich.EINMALIG


def reihe_des_teils(reihen: Reihen, teil: messung.Teil) -> Reihe | None:
    """Die Reihe, zu der ein gemessener Teil gehoert; keine, wo er zu keiner gehoeren kann."""
    return (reihen.nach_schluessel(teil.gegenpartei, teil.kategorie)
            if _kann_reihe_sein(teil) else None)


def reihen(conn: sqlite3.Connection, *, bis: date,
           festgelegt: Mapping[tuple[str, str], Takt] | None = None,
           zusammen: Mapping[str, str] | None = None,
           ausschluss: messung.Ausschluss = messung.KEIN_AUSSCHLUSS) -> Reihen:
    """Die Reihen mit ihrem Takt, aus den Teilen der 24 Monate bis `bis`.

    Gelesen werden alle Teile aller Konten, Umbuchungen nach dem Praefix
    heraus (die Regel "praefix" der Messung). Teile ohne Gegenpartei gehoeren
    zu keiner Reihe. Einmaliges -- Teile im Block `einmalig`, also einer Buchung,
    die der Haushalt einmalig gesetzt hat, oder einer Kategorie mit dem Merkmal --
    ist nie Teil einer Reihe: Es kommt nicht wieder, und ein Termin daraus
    schriebe es fort. `festgelegt` sind die Handentscheidungen je (Gegenpartei,
    Kategorie): Sie schlagen die Erkennung. `zusammen` fuehrt Schreibweisen derselben
    Gegenpartei zu einer Reihe zusammen (`{schreibweise: gegenpartei}`): Der
    Importer schreibt manchen Zahler mal so, mal so, und jede Schreibweise waere
    sonst eine Reihe fuer sich. Die Reihe heisst nach der Gegenpartei, auf die sie
    zeigen; nur die Vorschauen sehen das, nicht Regeln oder Vertraege.
    `ausschluss` nennt Buchungen, die die Messung der Vorschau nicht sieht
    (einmalige Planzeilen): Sie bilden auch keinen Termin.
    """
    festgelegt = festgelegt or {}
    _pruefe_festgelegt(festgelegt)
    ziel = zusammen_aufloesen(zusammen or {})
    von = add_months(bis.replace(day=1), -(FENSTER_MONATE - 1))
    fixkosten = {r[0] for r in conn.execute(
        "SELECT id FROM mgmt_categories WHERE fixkosten = 1")}
    gruppen: dict[tuple[str, str], list[messung.Teil]] = defaultdict(list)
    for teil in messung.teile(conn, von=von, bis=bis, ausschluss=ausschluss, je_block=True):
        if _kann_reihe_sein(teil):
            gruppen[(ziel.get(teil.gegenpartei, teil.gegenpartei), teil.kategorie)].append(teil)
    for teile in gruppen.values():
        if len({t.gegenpartei for t in teile}) > 1:
            teile.sort(key=lambda t: (t.tag, t.dedup_hash))
    return Reihen(bis, von, tuple(
        _reihe(g, k, teile, fixkosten=k in fixkosten,
               festgelegt=festgelegt.get((g, k)), stichtag=bis)
        for (g, k), teile in sorted(gruppen.items(), key=lambda e: (e[0][1], e[0][0]))),
        quelle=Quelle(frozenset(fixkosten), dict(festgelegt)))


# ------------------------------------------------- Was eine Reihe beitraegt


@dataclass(frozen=True, slots=True)
class BeitragInBasis:
    """Was zugeordnete Teile in der Basis der Hochrechnung zaehlen.

    `takt_jahr` ist die Summe der Jahreswerte der laufenden Reihen mit festem
    Takt, an deren Terminen die Teile liegen (jede Reihe einmal); `rest_cents`
    die Summe der Teile, die im Rest zaehlen, ueber das Messfenster. Teile im
    Verlauf einer Reihe und an einer beendeten Reihe zaehlen nirgends.
    """

    takt_jahr: int
    rest_cents: int
    reihen: tuple[Reihe, ...]

    def je_monat(self, monate: int) -> float:
        """Der Beitrag je Monat; `monate` ist das Messfenster des Rests."""
        return self.takt_jahr / 12 + (self.rest_cents / monate if monate else 0)

    def im_jahr(self, monate: int) -> int:
        return round(self.je_monat(monate) * 12)


def beitrag_in_basis(teile: Iterable[tuple[str, str, date, int]], reihen: Reihen, *,
                     von: date, bis: date) -> BeitragInBasis:
    """Was Teile `(Kennung der Buchung, Kategorie, Tag, Cent)` in der Basis der
    Hochrechnung zaehlen: derselbe Beitrag, den die Fortschreibung rechnet.

    Die Basis, ein Wegfall und ein Vertragsende rechnen ihn gleich. Hat ein Teil
    eine Reihe mit festem Takt, zaehlt die Reihe mit ihrem Jahreswert (Betrag je
    Termin mal 12/t, bei einer beendeten null), nicht der Teil mit seinem Betrag:
    schriebe die Basis zwoelf Termine fort und der Wegfall naehme dreizehn ab,
    zoege er einen Termin zu viel ab. Die Reihe zaehlt, auch wenn ihr Termin vor
    dem Messfenster liegt (die Basis schreibt sie fort, solange sie laeuft);
    `teile` sind deshalb alle Teile, nicht nur die im Fenster `von` bis `bis`.
    Alles andere zaehlt im Rest, mit der Summe seiner Teile im Fenster.
    """
    takt: dict[tuple[str, str], Reihe] = {}
    rest = 0
    for kennung, kategorie, tag, cents in teile:
        reihe = reihen.nach_teil(kennung, kategorie)
        wo = IM_REST if reihe is None else reihe.einordnen(tag)
        if wo == IM_REST and von <= tag <= bis:
            rest += cents
        elif reihe is not None and wo == IM_TAKT:
            takt[(reihe.gegenpartei, reihe.kategorie)] = reihe
    return BeitragInBasis(
        sum(r.beitrag.jahreswert if r.beitrag else 0 for r in takt.values()),
        rest, tuple(sorted(takt.values(), key=groesse)))


def groesse(reihe: Reihe) -> tuple:
    """Die Reihenfolge, in der Rechenwege Reihen nennen: die groesste zuerst, dann nach
    Takt und letztem Termin, erst zuletzt nach dem Namen. Der Rechenweg zeigt Namen, die
    der Haushalt aendern kann; seine Reihenfolge haengt nicht daran."""
    b = reihe.beitrag
    return (-abs(b.jahreswert) if b else 0, int(reihe.takt) if reihe.fest else 0,
            b.letzter_termin if b else date.min, reihe.gegenpartei)
