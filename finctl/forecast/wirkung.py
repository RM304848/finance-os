"""Die Wirkung: wie weit sich ein Ziel gegenueber dem Monat davor bewegt hat, und warum.

Verglichen werden zwei Hochrechnungen: die von heute und die zum Stichtag davor,
jede mit dem Hauptbuch nur bis zu ihrem Stichtag. Gespeichert wird keine; was
nicht gespeichert wird, kann nicht veralten.

DIE URSACHEN WERDEN NACHEINANDER AUSGETAUSCHT. Die Eingaben der Rechnung von
damals werden Gruppe fuer Gruppe durch die von heute ersetzt, in fester
Reihenfolge, und nach jedem Tausch wird neu gerechnet. Die Differenz zur
Rechnung davor ist die Wirkung dieser Ursache. Nach dem letzten Tausch stehen
genau die Eingaben von heute da, also summieren sich die Ursachen exakt zur
Bewegung des Ziels -- es gibt keinen Rest, der "Sonstiges" hiesse. Die Reihenfolge
ist festgelegt (`_folge`); eine andere Reihenfolge verteilte dieselbe Summe
anders, weil sich die Gruppen ueberlagern (das Tempo eines Blocks wirkt in jedem Jahr der
Rechnung mit dem Bestand zusammen).

ANNAHMEN, ZIELE, PLANZEILEN, KREDITE UND VERPFLICHTUNGEN GELTEN FUER BEIDE
RECHNUNGEN SO, WIE SIE HEUTE STEHEN. Die Wirkung zeigt, was die Buchungen bewegt
haben, nicht was der Haushalt umgestellt hat. Ein Feld von `jahre.Eingaben`, das
in keiner Gruppe getauscht wird und sich trotzdem unterscheidet, waere eine
Wirkung ohne Ursache; `wirkung` wirft dann einen Fehler, der das Feld nennt.

JEDE TEMPO-URSACHE NENNT IHRE KATEGORIEN (`KategorieWandel`): den Jahreswert
vorher und nachher, geteilt in die Reihen mit festem Takt, die sich bewegt haben
(begonnen, beendet, anderer Betrag je Termin), und den Rest: den Monat, der aus
dem Fenster fiel, und den, der dazukam, je mit Betrag und Zahl der Buchungen. Ein
Zahlungstag, der ueber das Monatsende rutscht, bewegt keine Reihe mehr: sie zaehlt
ihre Termine, nicht die Monate des Fensters.

FEHLT EIN STAND VON DAMALS, GIBT ES KEINE ZAHLEN. Ein getippter Stand, den
niemand zum Stichtag davor eingetragen hat, zaehlt nicht als null
(`bestaende.zum`); ebenso ein Konto, das erst spaeter eingelesen wurde. Dann
bleibt `fehlt` mit den Namen und `ab` mit dem Stichtag, ab dem es den Vergleich gibt.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, fields, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, NamedTuple

from finctl import assumptions as ann
from finctl import bestaende as best
from finctl.forecast import abgleich as ag
from finctl.forecast import jahre as jm
from finctl.forecast import messung
from finctl.forecast import rentenluecke as rl
from finctl.forecast import treffer as tr
from finctl.forecast import ziel_monat as zm
from finctl.forecast import ziele as zl
from finctl.forecast.fortschreibung import Fortgeschrieben, Zerlegung
from finctl.forecast.herkunft import Posten, eur_genau, monat
from finctl.forecast.takt import Beitrag, takt_name
from finctl.forecast.verfahren import add_months

Tempo = jm.Tempo

#: Welche Felder von `jahre.Eingaben` eine Ursache tauscht. Alle anderen gelten
#: in beiden Rechnungen gleich (`_gleiche_felder`).
GETAUSCHT = frozenset({"monat", "base", "base_monate", "base_reihen", "planzeilen"})


@dataclass(frozen=True, slots=True)
class MonatBetrag:
    """Was ein Monat zum Jahreswert einer Kategorie beitrug."""

    monat: date
    #: Vorzeichen wie im Ledger.
    cents: int
    buchungen: int


@dataclass(frozen=True, slots=True)
class ReiheWandel:
    """Eine Reihe mit festem Takt, deren Jahreswert sich zwischen den Stichtagen geaendert hat.

    `grund` sagt, warum: `begonnen` (damals nicht dabei oder beendet, heute laeuft sie),
    `beendet`, `betrag` (anderer Betrag je Termin) oder `takt` (anderer Takt, derselbe
    Betrag). Wo die Reihe damals oder heute nicht zaehlt, steht null und kein Betrag.
    """

    gegenpartei: str
    #: Der Jahreswert der Reihe in `Eingaben.base`, damals und heute (null, wo beendet).
    vorher: int
    nachher: int
    grund: Literal["begonnen", "beendet", "betrag", "takt"]
    #: Takt und Betrag je Termin, damals und heute; None, wo die Reihe nicht zaehlt.
    takt_vorher: int | None
    takt_nachher: int | None
    betrag_vorher: int | None
    betrag_nachher: int | None

    @property
    def aenderung(self) -> int:
        return self.nachher - self.vorher

    @property
    def beschreibung(self) -> str:
        name = takt_name(self.takt_nachher or self.takt_vorher or 1)
        if self.grund == "begonnen":
            return f"begonnen, {name}, je Termin {eur_genau(self.betrag_nachher or 0)}"
        if self.grund == "beendet":
            return f"beendet, {name}, bisher je Termin {eur_genau(self.betrag_vorher or 0)}"
        if self.grund == "takt":
            return (f"{takt_name(self.takt_vorher or 1)} → {name}, "
                    f"je Termin {eur_genau(self.betrag_nachher or 0)}")
        return (f"{name}, je Termin {eur_genau(self.betrag_vorher or 0)} → "
                f"{eur_genau(self.betrag_nachher or 0)}")


@dataclass(frozen=True, slots=True)
class KategorieWandel:
    """Wie sich der Jahreswert einer Kategorie zwischen den Stichtagen geaendert hat.

    Er teilt sich in die `reihen` mit festem Takt, die sich bewegt haben, und den
    Rest: `rest_vorher` und `rest_nachher`, mit den Monaten, die aus dem Fenster fielen
    (`heraus`) und dazukamen (`dazu`), bei einem Fenster, das um einen Monat rueckt je
    einer. Ein Monat ohne Buchung im Rest steht mit null und null Buchungen da. Die
    Summe der Reihen und des Rests ist die Aenderung der Kategorie.
    """

    kategorie: str
    #: Der Jahreswert in `Eingaben.base`, damals und heute.
    vorher: int
    nachher: int
    heraus: tuple[MonatBetrag, ...]
    dazu: tuple[MonatBetrag, ...]
    reihen: tuple[ReiheWandel, ...] = ()
    rest_vorher: int = 0
    rest_nachher: int = 0

    @property
    def aenderung(self) -> int:
        return self.nachher - self.vorher


@dataclass(frozen=True, slots=True)
class ZielWirkung:
    """Wie sich ein Ziel gegenueber dem Stichtag davor bewegt hat."""

    ziel: zl.Progress
    #: Der Stichtag, bis zu dem heute gerechnet ist, und der davor.
    stichtag: date
    davor: date
    #: Der Wert an seinem Stichdatum, wie `/ziele` ihn als Hochrechnung zeigt:
    #: vor einem Monat und heute. None bei einem Ziel ohne Hochrechnung, und
    #: `vorher` auch, wenn Staende von damals fehlen.
    vorher: int | None
    heute: int | None
    #: Summanden im Sinne von `herkunft.Posten`: ihre Summe ist `heute - vorher`.
    ursachen: list[Posten] = field(default_factory=list)
    #: Der Balken des Ziels (Bestand gegen Zielbetrag) zum Stichtag davor und
    #: heute. Auch ein Ziel ohne Hochrechnung hat ihn.
    balken_vorher: int | None = None
    balken_heute: int = 0
    #: Welche Staende zum Stichtag davor nicht bekannt sind, woran es liegt
    #: ("stand", "konto", "hauptbuch") und ab welchem Stichtag es den Vergleich gibt.
    fehlt: tuple[str, ...] = ()
    fehlt_grund: Mapping[str, str] = field(default_factory=dict)
    ab: date | None = None
    #: Je Block, dessen Tempo eine Ursache sein kann, die Kategorien, deren Jahreswert
    #: sich geaendert hat -- nach der Groesse der Aenderung. Fuer alle Ziele dieselben.
    kategorien: Mapping[str, tuple[KategorieWandel, ...]] = field(default_factory=dict)
    #: Das Modell, das den Wert des Ziels misst (`ziel_monat`). Misst das Monatsmodell, gibt es
    #: hier keinen Vergleich und keine Ursachen: Die Zerlegung ist die der Jahresrechnung.
    modell: str = zm.JAHRESRECHNUNG

    @property
    def im_monatsmodell(self) -> bool:
        return self.modell == zm.MONATSMODELL

    @property
    def pct_vorher(self) -> float | None:
        """Der Wert von damals in Prozent vom Zielbetrag (nicht gedeckelt, wie auf /ziele)."""
        return self._pct(self.vorher)

    @property
    def pct_heute(self) -> float | None:
        return self._pct(self.heute)

    def _pct(self, wert: int | None) -> float | None:
        if wert is None or not self.ziel.target_cents:
            return None
        return 100.0 * wert / self.ziel.target_cents

    @property
    def aenderung(self) -> int | None:
        """Wie weit sich der Wert bewegt hat; None, wo es keinen Vergleich gibt."""
        if self.vorher is None or self.heute is None:
            return None
        return self.heute - self.vorher

    @property
    def balken_aenderung(self) -> int | None:
        return None if self.balken_vorher is None else self.balken_heute - self.balken_vorher

    @property
    def satz(self) -> str | None:
        """Was statt der Zahlen auf der Seite steht, wenn Staende fehlen."""
        return fehlt_satz(self.davor, self.fehlt, self.fehlt_grund, self.ab) \
            if self.fehlt else None


def _liste(namen: list[str]) -> str:
    return namen[0] if len(namen) == 1 else f"{', '.join(namen[:-1])} und {namen[-1]}"


def fehlt_satz(davor: date, fehlt: tuple[str, ...], grund: Mapping[str, str],
               ab: date | None) -> str:
    """Der Satz, der sagt, warum es keinen Vergleich gibt und ab wann es einen gibt."""
    stichtag = monat(davor)
    teile = []
    staende = [n for n in fehlt if grund.get(n) == "stand"]
    konten = [n for n in fehlt if grund.get(n) == "konto"]
    if staende:
        teile.append(f"Von {_liste(staende)} liegt kein Stand zum Stichtag {stichtag} vor "
                     "(im Monatsabschluss eintragen).")
    if konten:
        teile.append(f"Für {_liste(konten)} gibt es zum Stichtag {stichtag} noch keinen Auszug.")
    if "hauptbuch" in grund.values():
        teile.append(f"Das Hauptbuch beginnt erst nach dem Stichtag {stichtag}.")
    if ab:
        teile.append(f"Ein Vergleich ist ab dem Stichtag {monat(ab)} möglich.")
    return " ".join(teile)


class _Tausch(NamedTuple):
    """Eine Ursache: was sie heisst, woran man sie nachschlaegt, was sie tauscht."""

    label: str
    verweis: str | None
    quelle: str
    was: str
    tausche: Callable[[jm.Eingaben], jm.Eingaben]


def _block(alt: Mapping, neu: Mapping, block: str) -> dict:
    """`alt`, in dem nur der Eintrag `block` der von `neu` ist (oder fehlt, wo er dort fehlt)."""
    out = dict(alt)
    if block in neu:
        out[block] = neu[block]
    else:
        out.pop(block, None)
    return out


def _folge(heute: jm.Eingaben, davor: date, stichtag: date) -> list[_Tausch]:
    """Die Ursachen in der festen Reihenfolge: der Monat, das Tempo je Block, die Planzeilen.
    Das Gehalt ist keine Ursache mehr: es ist die Untergrenze aus den Annahmen und wird nicht
    gemessen (Schritt 5b, E.3).

    Bestand und Zeit stehen in EINER Gruppe (`jahre.Monat`): getrennt zeigte die
    Zeit ein grosses Minus (ein Monat Sparen fehlt in der Rechnung) und der
    Bestand ein grosses Plus (er liegt jetzt auf dem Konto), und beide hoben sich
    fast auf. Zusammen bleibt, was der Monat anders brachte als erwartet.

    `base`, `base_monate` und `base_reihen` gehoeren zusammen und werden je Block
    gemeinsam getauscht, sonst nennte der Rechenweg das Fenster oder die Reihen des
    anderen Stichtags.
    """
    von, bis = monat(davor), monat(stichtag)
    namen = {b.id: b.label for b in ag.bloecke()}
    folge = [_Tausch(
        "Der Monat", None, "gemessen",
        f"Bestand, vergangene Monate und Messfenster von Ende {von} auf Ende {bis}",
        lambda e: replace(e, monat=heute.monat))]
    for block in jm.FROM_BASE:
        folge.append(_Tausch(
            f"Tempo: {namen.get(block, block)}", block, "gemessen",
            f"gemessene Jahreswerte im Block {namen.get(block, block)} "
            f"von Ende {von} auf Ende {bis}",
            lambda e, b=block: replace(
                e, base=_block(e.base, heute.base, b),
                base_monate=_block(e.base_monate, heute.base_monate, b),
                base_reihen=_block(e.base_reihen, heute.base_reihen, b))))
    folge.append(_Tausch(
        "Planzeilen", None, "plan",
        f"Messungen der Planzeilen, Vertragsenden und Verkäufe von Ende {von} auf Ende {bis}",
        lambda e: replace(e, planzeilen=heute.planzeilen)))
    return folge


def _gleiche_felder(davor: jm.Eingaben, heute: jm.Eingaben) -> None:
    """Jedes Feld, das keine Ursache tauscht, muss in beiden Rechnungen gleich sein."""
    for f in fields(jm.Eingaben):
        if f.name not in GETAUSCHT and getattr(davor, f.name) != getattr(heute, f.name):
            raise ValueError(
                f"Eingaben.{f.name} ist in den Rechnungen zu beiden Stichtagen verschieden, "
                "gehört aber zu keiner Ursache: die Wirkung hätte keinen Grund.")


def _lesen(conn: sqlite3.Connection, tempi: tuple[Tempo, ...], bestand: dict,
           ziele: dict, bis: date | None, assumptions: Path | str,
           szenarien: Path | str | None) -> dict[Tempo, jm.Eingaben]:
    """Die Eingaben beider Stichtage lesen sich gleich: nur `bis` und die Staende unterscheiden
    sie."""
    kw = {"opening_cents": zl.liquid_cents(bestand), "toepfe": zl.toepfe(bestand),
          "depot_gewinn_cents": zl.depot_gewinn(bestand),
          "puffer_cents": zl.puffer_cents(ziele),
          "policen_je_konto": zl.policen_je_konto(bestand),
          "tagesgeld_je_konto": zl.tagesgeld_je_konto(bestand),
          "assumptions": assumptions, "szenarien": szenarien, "bis": bis}
    if len(tempi) == 1:
        return {tempi[0]: jm.eingaben(conn, tempo=tempi[0], **kw)}
    gelesen = jm.eingaben_je_tempo(conn, **kw)
    return {t: gelesen[t] for t in tempi}


def _hauptbuch_ab(conn: sqlite3.Connection) -> date | None:
    """Ab welchem Stichtag das Hauptbuch ein Fenster hat (`abgleich.fenster`)."""
    erster = conn.execute(
        "SELECT MIN(period_start) FROM statements WHERE status = 'imported'").fetchone()[0]
    if not erster:
        return None
    e = date.fromisoformat(erster)
    voll = e if e.day == 1 else ag.folgetag(e)
    return ag.folgetag(ag.folgetag(voll)) - timedelta(days=1)


class Messung:
    """Der Wert jedes Ziels aus einer Rechnung. Der Horizont reicht bis zum spaetesten Stichdatum.

    `/ziele` rechnet bis ins erste volle Rentenjahr, weil die Rentenluecke ihren
    Bedarf von dort nimmt; fuer den Wert eines Ziels an seinem Stichdatum zaehlt
    nur, dass die Rechnung bis dahin reicht (spaetere Jahre aendern frueheren
    nichts).

    Ein Ziel, das das Monatsmodell misst (`monatsmodell`, die Kennungen), misst die Jahresrechnung
    nicht: sein Wert ist hier null, und es hat keine Ursachen.
    """

    def __init__(self, progs: list[zl.Progress],
                 monatsmodell: frozenset[str] = frozenset()) -> None:
        self.progs = progs
        self.monatsmodell = monatsmodell
        self.ende = max([2045, *(p.due.year for p in progs if p.due)])

    def __call__(self, e: jm.Eingaben) -> dict[str, int | None]:
        lauf = jm.rechnen(e, end_year=self.ende)
        out = {}
        for p in self.progs:
            h = None if p.goal_id in self.monatsmodell else zl.hochgerechnet(lauf, p)
            out[p.goal_id] = h.cents if h else None
        return out


@dataclass(frozen=True, slots=True)
class Kurs:
    """Was die Depots im Monat bewegt haben, getrennt von dem, was eingezahlt wurde."""

    stand_vorher: int
    stand_heute: int
    #: Die Buchungen unter `investment/` im Monat, Vorzeichen wie im Ledger:
    #: negativ heisst, Geld ging ins Depot.
    buchungen_cents: int

    @property
    def aenderung(self) -> int:
        return self.stand_heute - self.stand_vorher

    @property
    def kursbewegung(self) -> int:
        """Die Aenderung des getippten Stands minus das, was ueber Buchungen hineinging."""
        return self.aenderung + self.buchungen_cents


@dataclass(frozen=True, slots=True)
class Hinweise:
    """Warum der Monat anders kam, in Euro des Monats -- neben der Wirkung, nicht in ihr.

    Ihre Summe ist nicht die Wirkung: Die wirkt bis zum Stichdatum eines Ziels
    mit und wird von Inflation und Rendite weitergetragen.
    """

    #: Der Monat, der mit dem Stichtag schliesst.
    monat: date
    #: Prognose gegen Ist je Block (`treffer.jahresbasis`).
    treffer: tr.Monat
    #: Fehlt, wenn es weder heute noch damals ein Depot gab.
    kurs: Kurs | None
    #: Ob im Monat Zinsen oder Kapitalertragsteuer gebucht sind. Der Treffer-Check
    #: zaehlt sie als Gebuchtes, die Hochrechnung rechnet sie (`jahre.GERECHNET`).
    gerechnet_gebucht: bool


@dataclass(frozen=True, slots=True)
class Vergleich:
    """Der Vergleich der zwei Stichtage: die Wirkung je Tempo und die Hinweise zum Monat."""

    stichtag: date | None
    davor: date | None
    je_tempo: dict[Tempo, list[ZielWirkung]]
    hinweise: Hinweise | None = None


def wirkung(conn: sqlite3.Connection, ziele: dict, *, tempo: Tempo,
            assumptions: Path | str = ann.PATH, szenarien: Path | str | None = None,
            basis: dict | None = None) -> list[ZielWirkung]:
    """Die Wirkung jedes Ziels im Tempo `tempo`. `wirkung_je_tempo` liest nur einmal."""
    return wirkung_je_tempo(conn, ziele, tempi=(tempo,), assumptions=assumptions,
                            szenarien=szenarien, basis=basis)[tempo]


def wirkung_je_tempo(conn: sqlite3.Connection, ziele: dict, *,
                     tempi: tuple[Tempo, ...] = jm.TEMPI,
                     assumptions: Path | str = ann.PATH,
                     szenarien: Path | str | None = None,
                     basis: dict | None = None) -> dict[Tempo, list[ZielWirkung]]:
    """Die Wirkung jedes Ziels gegenueber dem Stichtag davor, je Tempo.

    `ziele` ist das Ziel-Dokument, wie es `ziele.progress` nimmt und wie die
    Seite es nach `rentenluecke.mit_ziel` hat: der Zielbetrag steht darin fest
    und gilt zu beiden Stichtagen und in beiden Tempi. `basis` ist
    der Inhalt von `balances.yaml` (ohne ihn wird er gelesen).

    Ohne Hauptbuch gibt es nichts zu vergleichen (leere Listen).
    """
    return vergleichen(conn, ziele, tempi=tempi, assumptions=assumptions,
                       szenarien=szenarien, basis=basis).je_tempo


def vergleichen(conn: sqlite3.Connection, ziele: dict, *,
                tempi: tuple[Tempo, ...] = jm.TEMPI,
                assumptions: Path | str = ann.PATH,
                szenarien: Path | str | None = None,
                basis: dict | None = None,
                mit_luecke: bool = False,
                mit_hinweisen: bool = False) -> Vergleich:
    """Wie `wirkung_je_tempo`, dazu auf Wunsch die Hinweise zum Monat.

    `mit_luecke` haengt die Rentenluecke an die Ziele, gerechnet aus der
    Hochrechnung von heute im Schnitt -- derselbe Zielbetrag, den `/ziele`
    nimmt, fuer beide Stichtage und beide Tempi. Es braucht den Schnitt
    unter `tempi`.
    """
    stichtag = ag.letzter_vollstaendiger_monat(conn)
    if stichtag is None:
        return Vergleich(None, None, {t: [] for t in tempi})
    if mit_luecke and "schnitt" not in tempi:
        raise ValueError("die Rentenlücke rechnet sich aus dem Schnitt")
    davor = stichtag.replace(day=1) - timedelta(days=1)
    basis = best.lesen() if basis is None else basis
    jetzt = best.zusammenfuehren(conn, basis)
    damals = best.zum(conn, davor, basis)

    fehlt = list(damals["fehlt"])
    grund = dict(damals["fehlt_grund"])
    ab = damals["fehlt_ab"]
    if ag.fenster(conn, bis=davor) is None:
        fehlt.append("Hauptbuch")
        grund["Hauptbuch"] = "hauptbuch"
        ab = max(filter(None, [ab, _hauptbuch_ab(conn)]), default=None)

    heute = _lesen(conn, tempi, jetzt, ziele, None, assumptions, szenarien)
    if mit_luecke:
        ziele = _mit_luecke(ziele, heute["schnitt"])
    progs = zl.progress(ziele, jetzt)
    lauf = zm.Lauf(conn)
    monatsmodell = frozenset(p.goal_id for p in progs
                             if zm.misst_das_monatsmodell(p, jetzt, lauf))
    messen = Messung(progs, monatsmodell)
    vorher = None if fehlt else _lesen(
        conn, tempi, damals, ziele, davor, assumptions, szenarien)
    balken = None if fehlt else {p.goal_id: p.have_cents
                                 for p in zl.progress(ziele, damals)}

    aus: dict[Tempo, list[ZielWirkung]] = {}
    for t in tempi:
        if vorher is None:
            werte = messen(heute[t])
            aus[t] = [ZielWirkung(
                p, stichtag, davor, None, werte[p.goal_id], balken_heute=p.have_cents,
                fehlt=tuple(fehlt), fehlt_grund=grund, ab=ab,
                modell=_modell(p, monatsmodell)) for p in progs]
            continue
        w0, w1, ursachen = tauschen(vorher[t], heute[t], messen, davor, stichtag)
        wandel = kategorien(vorher[t], heute[t])
        aus[t] = [ZielWirkung(
            p, stichtag, davor, w0[p.goal_id], w1[p.goal_id], ursachen[p.goal_id],
            balken_vorher=balken[p.goal_id], balken_heute=p.have_cents, kategorien=wandel,
            modell=_modell(p, monatsmodell)) for p in progs]
    hinweise = None
    if mit_hinweisen and vorher is not None:
        hinweise = _hinweise(conn, stichtag, jetzt, damals, list(heute[tempi[0]].tilgungsplaene))
    return Vergleich(stichtag, davor, aus, hinweise)


def _modell(ziel: zl.Progress, monatsmodell: frozenset[str]) -> str:
    return zm.MONATSMODELL if ziel.goal_id in monatsmodell else zm.JAHRESRECHNUNG


def _mit_luecke(ziele: dict, heute: jm.Eingaben) -> dict:
    """Die Ziele samt Rentenluecke, wie `/ziele` sie rechnet: aus der Hochrechnung im
    Schnitt, bis ins erste volle Rentenjahr."""
    stichjahre = [int(str(g["stichtag"])[:4]) for g in ziele.get("ziele") or []
                  if g.get("stichtag")]
    rentenjahr = [heute.rentenbeginn.year + 1] if heute.rentenbeginn else []
    lauf = jm.rechnen(heute, end_year=max([2045, *stichjahre, *rentenjahr]))
    return rl.mit_ziel(ziele, lauf, heute)[0]


def _fenstermonate(e: jm.Eingaben, block: str, kategorie: str) -> frozenset[date]:
    """Die Monate, aus denen `Eingaben.base` diese Kategorie misst: das Fenster, oder
    bei Juengst nur dessen letzte Monate."""
    f = e.monat.fenster
    if f is None:
        return frozenset()
    n = e.base_monate.get(block, {}).get(kategorie) or f.monate
    ende = f.bis.replace(day=1)
    return frozenset(add_months(ende, -i) for i in range(n))


def _monate(zerlegt: Zerlegung | None, monate: frozenset[date]) -> tuple[MonatBetrag, ...]:
    """Die Monate `monate` im Rest einer Kategorie: was gebucht ist und wie viele
    Buchungen; ein Monat, den der Rest nicht kennt, steht mit null."""
    je_monat = {m.monat: m for m in (zerlegt.rest_monate if zerlegt else ())}
    out = []
    for m in sorted(monate):
        gebucht = je_monat.get(f"{m.year}-{m.month:02d}")
        out.append(MonatBetrag(m, gebucht.cents, gebucht.buchungen) if gebucht
                   else MonatBetrag(m, 0, 0))
    return tuple(out)


def _zaehlt(posten: Fortgeschrieben | None) -> Beitrag | None:
    """Der Beitrag einer Reihe, wo sie laeuft; None, wo sie fehlt oder beendet ist."""
    beitrag = posten.beitrag if posten else None
    return beitrag if beitrag and beitrag.laeuft else None


def _reihe_wandel(gegenpartei: str, vorher: Fortgeschrieben | None,
                  nachher: Fortgeschrieben | None) -> ReiheWandel | None:
    """Wie sich eine Reihe zwischen den Stichtagen bewegt hat; None, wo nicht."""
    v0 = vorher.ergebnis.cents if vorher else 0
    v1 = nachher.ergebnis.cents if nachher else 0
    if v0 == v1:
        return None
    b0, b1 = _zaehlt(vorher), _zaehlt(nachher)
    grund = ("begonnen" if not b0 else "beendet" if not b1
             else "betrag" if b0.betrag_je_termin != b1.betrag_je_termin else "takt")
    return ReiheWandel(
        gegenpartei, v0, v1, grund,
        b0.takt if b0 else None, b1.takt if b1 else None,
        b0.betrag_je_termin if b0 else None, b1.betrag_je_termin if b1 else None)


def _reihen_wandel(vorher: Zerlegung | None, nachher: Zerlegung | None,
                   ) -> tuple[ReiheWandel, ...]:
    """Die Reihen mit festem Takt einer Kategorie, die sich bewegt haben, nach der
    Groesse der Aenderung."""
    alt = {r.reihe: r for r in vorher.reihen} if vorher else {}
    neu = {r.reihe: r for r in nachher.reihen} if nachher else {}
    liste = [w for g in sorted(set(alt) | set(neu))
             if (w := _reihe_wandel(g, alt.get(g), neu.get(g)))]
    return tuple(sorted(liste, key=lambda w: (-abs(w.aenderung), w.gegenpartei)))


def kategorien(davor: jm.Eingaben, heute: jm.Eingaben,
               ) -> dict[str, tuple[KategorieWandel, ...]]:
    """Je Block die Kategorien, deren Jahreswert sich zwischen den Eingaben geaendert hat.

    Rein, wie `tauschen`: Die Reihen und die Monate des Rests stehen in
    `Eingaben.base_reihen`. Ein Monat, den der Rest nicht kennt, steht mit null.
    """
    out: dict[str, tuple[KategorieWandel, ...]] = {}
    for block in jm.FROM_BASE:
        alt, neu = davor.base.get(block, {}), heute.base.get(block, {})
        liste = []
        for kat in set(alt) | set(neu):
            v0, v1 = alt.get(kat, 0), neu.get(kat, 0)
            if v0 == v1:
                continue
            z0 = davor.base_reihen.get(block, {}).get(kat)
            z1 = heute.base_reihen.get(block, {}).get(kat)
            im_alt, im_neu = _fenstermonate(davor, block, kat), _fenstermonate(heute, block, kat)
            liste.append(KategorieWandel(
                kat, v0, v1, _monate(z0, im_alt - im_neu), _monate(z1, im_neu - im_alt),
                _reihen_wandel(z0, z1), z0.rest_cents if z0 else 0,
                z1.rest_cents if z1 else 0))
        if liste:
            out[block] = tuple(sorted(liste, key=lambda k: (-abs(k.aenderung), k.kategorie)))
    return out


def _hinweise(conn: sqlite3.Connection, stichtag: date, jetzt: dict, damals: dict,
              plaene: list) -> Hinweise:
    """Die Zeile des Treffer-Checks fuer den Monat und die Kursbewegung der Depots."""
    monat_ = stichtag.replace(day=1)
    zeile = tr.jahresbasis(conn, [monat_], plaene=plaene)[0]
    gebucht = messung.monatssummen(conn, von=monat_, bis=stichtag, je_block=True)
    depot0, depot1 = zl.toepfe(damals)["depot"], zl.toepfe(jetzt)["depot"]
    kurs = Kurs(depot0, depot1, sum(z.cents for z in gebucht if z.block == "investment")) \
        if depot0 or depot1 else None
    return Hinweise(monat_, zeile, kurs,
                    any(z.cents and z.kategorie in jm.GERECHNET for z in gebucht))


def tauschen(davor: jm.Eingaben, heute: jm.Eingaben, messen: Messung,
             von: date, bis: date,
             ) -> tuple[dict, dict, dict[str, list[Posten]]]:
    """Die Eingaben von damals in die von heute tauschen.

    Liefert den Wert je Ziel vor dem ersten Tausch (damals) und nach dem letzten
    (heute), und je Ziel die Ursachen. Rein: liest weder Datenbank noch Dateien,
    deshalb rechnen die Tests an dieser Stelle mit Eingaben von Hand.
    """
    _gleiche_felder(davor, heute)
    e = davor
    werte = messen(e)
    erste = werte
    ursachen: dict[str, list[Posten]] = {p.goal_id: [] for p in messen.progs}
    for tausch in _folge(heute, von, bis):
        neu = tausch.tausche(e)
        # Ein Tausch, der nichts aendert, kostet keine Rechnung und ist keine Ursache.
        if neu == e:
            continue
        e = neu
        jetzt = messen(e)
        for ziel, wert in jetzt.items():
            if wert is None or werte[ziel] is None or wert == werte[ziel]:
                continue
            ursachen[ziel].append(Posten(
                label=tausch.label, cents=wert - werte[ziel], quelle=tausch.quelle,
                verweis=tausch.verweis,
                herleitung=(f"{eur_genau(werte[ziel])} → {eur_genau(wert)}, wenn "
                            f"{tausch.was} gelten")))
        werte = jetzt
    # Was `rechnen` nicht liest (Bloecke ausserhalb von FROM_BASE in `base`), ist
    # kein Wert der Rechnung; es zu tauschen aendert kein Ergebnis.
    e = replace(e, base=heute.base, base_monate=heute.base_monate,
                base_reihen=heute.base_reihen)
    if e != heute:
        raise AssertionError("nach dem letzten Tausch sind es nicht die Eingaben von heute")
    return erste, werte, ursachen
