"""Wie viel Prozent von Barista FIRE stehen 2045?

Eine Tragfaehigkeitsrechnung, und sie braucht keine einzige Zeile -- zwanzig
Jahreszeilen genuegen. Das unterscheidet sie von der Liquiditaetsprognose in
ops.py, die Zeilen je Konto und die Intramonatssenke braucht, um "passt die
Rate in den Monat" zu beantworten.

Sie benutzt DIESELBEN Bloecke wie die Abstimmzeile. Das ist der Grund, warum
die Abstimmzeile zuerst gebaut wurde: waere hier eine zweite Einteilung, dann
prueft die Abstimmzeile etwas anderes als das, was gerechnet wird, und ihre
Null-Differenzen saeaen Vertrauen, das sie nicht gedeckt haben.

Reine Funktion. Keine Tabelle, kein Cache, nichts zu regenerieren -- die
Rechnung ist billig genug, um sie bei jedem Aufruf zu wiederholen, und was
nicht gespeichert wird, kann nicht veralten.

ALLES NOMINAL. Kosten und Einnahmen werden mit der Inflationsrate aus
assumptions.yaml fortgeschrieben; Kreditraten NICHT, denn eine Annuitaet ist
nominal fest und wird real jedes Jahr billiger. Das ist der stille Vorteil des
Kreditnehmers und darf nicht weginflationiert werden.

DREI TOEPFE statt eines Kapitalstocks. Tagesgeld, Depot und Policen wachsen
verschieden schnell, und ein Satz fuer alles haette entweder das Depot mit
Tagesgeldzinsen gerechnet oder das Tagesgeld mit Aktienrendite. Die Sparrate
fuellt das Tagesgeld bis zum Tagesgeld-Ziel, alles darueber geht ins Depot --
siehe `kaskade` und den Abschnitt kapital in assumptions.yaml.

ZINSEN UND STEUER DARAUF WERDEN GERECHNET, nicht fortgeschrieben. Das Tagesgeld
verdient den Satz seiner Konten (`zinsen.py`), und auf Zinsen, Vorabpauschale
und Verkaufsgewinne faellt eine Steuer nach dem Sparerpauschbetrag an. Die
gebuchten Zinsen und die gebuchte Kapitalertragsteuer bleiben aus der Basis
(`GERECHNET`); beides fortzuschreiben zaehlte die Zinsen doppelt.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Literal

from finctl import assumptions as ann
from finctl import objekte as _objekte
from finctl import person as _person
from finctl import reihen as _reihen
from finctl import renten as _renten
from finctl import zinssaetze as _zs
from finctl.dateien import yaml_lesen
from finctl.forecast import abgleich as ag
from finctl.forecast import fortschreibung as _fs
from finctl.forecast import messung as _ms
from finctl.forecast import objektposten as _ob
from finctl.forecast import policen as _pol
from finctl.forecast import szenarien as _sz
from finctl.forecast import takt as _tk
from finctl.forecast import verfahren as _vf
from finctl.forecast import vertraege as _vt
from finctl.forecast import wachstum
from finctl.forecast import zinsen as _zn
from finctl.forecast.herkunft import Posten, eur, eur_genau, faktor, monat, prozent, summe
from finctl.pfade import CONFIG_DIR

#: Bloecke, deren Jahreswert aus dem gemessenen Basisjahr kommt und dann mit
#: der Inflation mitlaeuft.
FROM_BASE = ("miete", "einkommen_sonst", "fixkosten", "immobilie",
             "konsum", "steuern")

#: Bloecke mit eigener Quelle. Der Basiswert waere hier falsch.
#:
#: `kredit` kommt aus den Tilgungsplaenen -- exakt bis zur Tilgung, und eine
#: fortgeschriebene Durchschnittsrate wuerde das Auslaufen eines Kredits
#: verschweigen.
#:
#: `einmalig` sind datierte Einmalvorgaenge. Sie fortzuschreiben hiesse,
#: einmalige Kaufraten jedes Jahr erneut zu zahlen.
#:
#: `investment` faellt ganz heraus: ein Kauf verschiebt Geld vom Konto ins
#: Depot, und beide zaehlen zum Ziel. Ihn als Ausgabe zu fuehren zoege
#: dasselbe Geld zweimal ab.
#: Der Objektblock haette aus dem Basisjahr einen einzelnen Mietmonat auf
#: acht verteilt und diese Verwaesserung zwanzig Jahre fortgeschrieben --
#: ein Achtel der Miete im Monat statt der ganzen.
SPECIAL = ("gehalt", "kredit", ag.EINMALIG, ag.OBJEKT)
IGNORED = ("investment",)

#: Bloecke, deren laufender Saldo als "rein" zaehlt.
_EINNAHMEBLOECKE = ("gehalt", "miete", "einkommen_sonst", ag.OBJEKT, "rente")

#: Was im Ruhestand hereinkommt. Kein Block des Ledgers -- gebucht ist noch
#: keine Rente --, sondern aus config/renten.yaml.
RENTE = "rente"

#: Was beide Modelle rechnen, statt es fortzuschreiben (`zinsen.GERECHNET`): die Konten
#: verdienen ihre Zinsen mit dem Satz je Konto, und auf sie faellt die Steuer nur nach
#: dem Sparerpauschbetrag an. Beides fortzuschreiben zaehlte die Zinsen doppelt und die
#: Steuer ohne den Freibetrag.
ZINSEN = _zn.ZINSEN
KAPITALERTRAGSTEUER = _zn.KAPITALERTRAGSTEUER
GERECHNET = _zn.GERECHNET


def zaehlt_in_prognose(line: _sz.Line) -> bool:
    """Ob eine Prognose eine Planzeile auswertet -- die Jahresrechnung wie das Monatsmodell.

    Eine Zeile auf einer gerechneten Kategorie (`GERECHNET`) korrigierte, solange
    die gebuchten Zinsen fortgeschrieben wurden, genau diese. Seit sie nicht mehr
    in der Basis stehen, zoege sie einen Betrag ab, der nirgends steht; ihre
    Aufgabe uebernimmt der Zinssatz des Kontos. Seit E.6 rechnet auch die
    Kontoprognose die Zinsen aus Stand und Satz (`konten._planposten` wertet die Zeile
    aus demselben Grund nicht aus), die Zeile gilt also in keiner Prognose mehr.
    """
    return line.category_id not in GERECHNET


def ohne_wirkung_in_prognose(
        geladen: list) -> list[tuple[_sz.Scenario, int, _sz.Line]]:
    """Die Planzeilen aller Klammern, die in keiner Prognose zaehlen.

    Auch die einer ausgeschalteten Klammer: die Seiten sagen es an der Zeile,
    nicht erst, wenn sie wirkt.
    """
    return [(s, i, line) for s in geladen for i, line in enumerate(s.lines)
            if not zaehlt_in_prognose(line)]


@dataclass(slots=True)
class Year:
    year: int
    blocks: dict[str, int] = field(default_factory=dict)
    opening_cents: int = 0
    #: Rendite aller Toepfe, die Vorabpauschale schon abgezogen.
    return_cents: int = 0
    #: Die Toepfe am Jahresende. Ihre Summe ist closing_cents.
    tagesgeld_cents: int = 0
    depot_cents: int = 0
    policen_cents: int = 0
    #: Bis wohin das Tagesgeld gefuellt wird: eine Jahresausgabe.
    puffer_grenze_cents: int = 0
    #: Was vom Tagesgeld ins Depot ging. Negativ: aus dem Depot gedeckt.
    ins_depot_cents: int = 0
    #: Die Vorabpauschale dieses Jahres.
    steuer_cents: int = 0
    #: Was als Beitrag in die Policen floss. Eine Umschichtung: die Ausgabe
    #: steht in ihrem Block und in der Sparrate, hier kommt sie im Vermoegen an.
    in_policen_cents: int = 0
    #: Was der Versicherer bei einer Kapitalauszahlung einbehielt (positiv): Geld,
    #: das das Vermoegen verlaesst, ohne Ausgabe in einem Block zu sein.
    abzug_cents: int = 0
    #: Der Rechenweg: je Block die Posten, aus denen er summiert ist, dazu
    #: `rendite` (ergibt return_cents) und `kaskade` (ergibt ins_depot_cents).
    posten: dict[str, list[Posten]] = field(default_factory=dict)

    @property
    def saving_cents(self) -> int:
        """Einnahmen minus Ausgaben. Vorzeichen wie im Ledger."""
        return sum(self.blocks.values())

    @property
    def closing_cents(self) -> int:
        return (self.opening_cents + self.return_cents + self.saving_cents
                + self.in_policen_cents - self.abzug_cents)

    def cashflow(self) -> dict[str, int]:
        """Rein und raus in Summe, laufend und einmalig getrennt.

        Die vier Zahlen ergeben zusammen die Sparrate. Laufend wird je Block
        verrechnet: eine Erstattung in den Fixkosten mindert die Kosten und
        ist keine Einnahme, ein wegfallender Tankposten ebenso. Einmalig heisst
        eine Planzeile mit Frequenz einmalig oder ein Verkaufserloes.
        """
        out = {"laufend_rein": 0, "laufend_raus": 0,
               "einmalig_rein": 0, "einmalig_raus": 0}
        for block, liste in self.posten.items():
            if block not in self.blocks:
                continue
            netto = sum(p.cents for p in liste if not p.einmalig)
            if block in _EINNAHMEBLOECKE:
                out["laufend_rein"] += netto
            elif block == ag.EINMALIG:
                out["laufend_rein" if netto > 0 else "laufend_raus"] += netto
            else:
                out["laufend_raus"] += netto
            for p in liste:
                if p.einmalig:
                    out["einmalig_rein" if p.cents > 0 else "einmalig_raus"] += p.cents
        return out

    @property
    def frei_cents(self) -> int:
        """Endkapital ohne den Notgroschen -- was davon Zielkapital ist.

        Der Notgroschen liegt im Tagesgeld-Topf, bis zur Grenze der Kaskade.
        """
        return self.closing_cents - min(max(self.tagesgeld_cents, 0),
                                        self.puffer_grenze_cents)


#: Was auch ohne Erwerbsarbeit weiterfliesst.
#:
#: `gehalt` fehlt hier, und das ist der ganze Punkt. `einmalig` ebenfalls:
#: eine einmalige Zahlung deckt keinen laufenden Bedarf, und sie
#: mitzuzaehlen liesse ein Jahr mit einer grossen Erstattung wie erreichte
#: Unabhaengigkeit aussehen.
PASSIV = ("miete", ag.OBJEKT, "einkommen_sonst", "rente")

#: Was laufend zu decken ist. Kreditraten gehoeren dazu -- sie laufen weiter,
#: ob gearbeitet wird oder nicht, und sie enden von selbst.
BEDARF = ("fixkosten", "immobilie", "konsum", "steuern", "kredit")


@dataclass(slots=True)
class Projection:
    years: list[Year] = field(default_factory=list)
    base_year: int = 0

    @property
    def reicht_bis(self) -> int | None:
        """Das letzte Jahr, bevor das Tagesgeld ins Minus faellt -- oder None,
        wenn das Kapital bis zum Ende der Rechnung reicht.

        Im Ruhestand fuellt das Depot das Tagesgeld auf; faellt es trotzdem
        ins Minus, ist das Depot leer.
        """
        for y in self.years:
            if y.tagesgeld_cents < 0:
                return y.year - 1
        return None
    target_cents: int = 0

    @property
    def final_cents(self) -> int:
        return self.years[-1].closing_cents if self.years else 0

    @property
    def pct_of_target(self) -> float:
        if not self.target_cents:
            return 0.0
        # Gegen das Ziel zaehlt, was ohne den Notgroschen da ist.
        frei = self.years[-1].frei_cents if self.years else 0
        return 100.0 * frei / self.target_cents

    def year(self, which: int) -> Year:
        return next(y for y in self.years if y.year == which)

    def zum(self, stichtag: date, wert) -> int:
        """Ein Wert zum Stichtag, zwischen zwei Jahresenden anteilig.

        Die Jahresrechnung kennt nur Jahresenden. Ein Ziel zum 01.01.2027 gegen
        das Ende von 2027 zu halten, zaehlte ein ganzes Jahr mit, das am
        Stichtag noch nicht war: die Kaufraten vom Oktober 2026 waeren darin
        laengst wieder aufgefuellt, und der Balken stuende gruen, wo er rot
        sein muss. Also der Stand am Ende des Vorjahres, plus der Teil des
        Stichtagsjahres, der bis dahin vergangen ist.

        `wert` macht aus einer Jahreszeile die Zahl, um die es geht -- ein
        Topf, eine Summe von Toepfen, das Kapital ohne Notgroschen.
        """
        erstes, letztes = self.years[0].year, self.years[-1].year
        if stichtag.year > letztes:
            return wert(self.years[-1])
        if stichtag.year <= erstes:
            return wert(self.years[0])
        vorher = wert(self.year(stichtag.year - 1))
        dann = wert(self.year(stichtag.year))
        beginn = date(stichtag.year, 1, 1)
        anteil = (stichtag - beginn).days / (date(stichtag.year + 1, 1, 1) - beginn).days
        return round(vorher + (dann - vorher) * anteil)

    @property
    def crossing_year(self) -> int | None:
        """Ab wann laufendes Einkommen ohne Gehalt den Bedarf deckt.

        Die Zahl, um die es eigentlich geht -- und eine andere als "wie viel
        steht 2045". Ein Endkapital beantwortet, ob man aufhoeren KANN; das
        hier beantwortet, ab wann man nicht mehr MUSS.

        Das erste Jahr, ab dem es dauerhaft gilt, nicht das erste, in dem es
        zufaellig gilt: ein einzelnes gutes Jahr zwischen zwei schlechten ist
        kein Wendepunkt. Deshalb muss die Deckung bis zum Ende der Projektion
        halten.
        """
        for i, row in enumerate(self.years):
            if all(_covers(spaeter) for spaeter in self.years[i:]):
                return row.year
        return None

    def coverage_pct(self, which: int) -> float:
        row = self.year(which)
        bedarf = -sum(row.blocks.get(b, 0) for b in BEDARF)
        if bedarf <= 0:
            return 100.0
        return 100.0 * sum(row.blocks.get(p, 0) for p in PASSIV) / bedarf


def kaskade(tagesgeld: int, depot: int, policen: int, *, sparrate: int,
            grenze: int, satz_tagesgeld: float, satz_depot: float,
            vorab_satz: float, steuer_quote: float, pauschbetrag: int = 0,
            anteil: float = 1.0,
            abfluss_gewichtet: int = 0,
            depot_abfluss: int = 0, entnahme: bool = False,
            einstand: int | None = None,
            zins_policen: int = 0, einzahlung_policen: int = 0) -> dict[str, int]:
    """Ein Jahr der Kapitalkaskade. Rein, damit sie ohne Ledger pruefbar ist.

    Rendite auf den Anfangsbestand. Bewusst nicht auf den Zufluss des Jahres:
    der kommt ueber das Jahr verteilt, und ihn voll zu verzinsen schmeichelt
    der Rechnung.

    Die Sparrate landet auf dem Tagesgeld. Liegt dort danach mehr als die
    Grenze, geht der Rest ins Depot. Liegt weniger, bleibt alles liegen -- der
    Puffer fuellt sich zuerst wieder auf, und das Depot wird dafuer nicht
    verkauft.

    AUCH EIN MINUS im Tagesgeld deckt sich nicht von selbst aus dem Depot.
    Frueher tat es das, und beim Eigenheim leerte es unbemerkt das ganze
    Depot -- eine Entnahme, die niemand eingetragen hatte. Wer Anteile
    verkaufen will, schreibt eine Planzeile auf ein Depotkonto; die kommt als
    `depot_abfluss` hier an. Bleibt das Tagesgeld negativ, steht es negativ
    da: das ist die Aussage, dass der Plan so nicht finanziert ist.

    IM RUHESTAND IST DAS ANDERS (`entnahme`): dort ist die Entnahme aus dem
    Depot der Plan und nichts, was jemand eintragen muss. Ab Rentenbeginn
    fuellt das Depot das Tagesgeld bis zur Grenze wieder auf, solange es
    reicht.

    JEDER VERKAUF KOSTET STEUER auf seinen Gewinnanteil: Wert minus
    `einstand` (was eingezahlt und schon als Vorabpauschale versteuert ist),
    im Verhaeltnis zum Depotwert. Gezahlt wird sie zusaetzlich aus dem Depot.
    Ohne `einstand` gilt der Anfangsbestand als Einstand: was bis heute
    gewachsen ist, kennt die Rechnung nicht.

    Die Vorabpauschale faellt jedes Jahr an, auch ohne Verkauf, und hoechstens
    auf den tatsaechlichen Wertzuwachs.

    EINE STEUER AUF ALLE KAPITALERTRAEGE des Jahres: Zinsen des Tagesgelds,
    Vorabpauschale und der Gewinnanteil der Verkaeufe, abzueglich des
    `pauschbetrag` (Sparerpauschbetrag), nicht unter null. Der Pauschbetrag
    wird in dieser Reihenfolge verbraucht, und die Reihenfolge entscheidet nur,
    in welcher Zeile er steht: Die drei Steuern ergeben dieselbe Summe wie eine
    einzige auf den Rest. Jede Steuer zahlt der Topf, in dem der Ertrag
    entstand -- die auf Zinsen das Tagesgeld, die beiden anderen das Depot.
    Im Basisjahr gilt der Pauschbetrag nur anteilig, denn auch die Zinsen sind
    nur die der Restmonate. `satz_tagesgeld` ist der Satz dieses Jahres, vom
    Aufrufer aus den Konten gemischt (`zinsen.mischung`).

    Die Policen sind fondsgebunden, aber ohne Vorabpauschale: der
    Versicherungsmantel schuetzt sie davor. Ihr Zins kommt als Zahl herein
    (`zins_policen`), je Police mit ihrem Satz nach Kosten gerechnet
    (`policen.fortschreiben`); die Kaskade kennt ihre Saetze nicht.
    `einzahlung_policen` sind die Beitraege des Jahres: Geld, das als Ausgabe
    schon in der Sparrate steht und hier in der Police ankommt -- eine
    Umschichtung, kein neues Geld. Aus der Sparrate gespeist werden sie nicht.

    `anteil` ist der Teil des Jahres, der noch projiziert wird. Im Basisjahr
    liefen nur die Restmonate, verzinst wurde aber der Anfangsbestand ein
    ganzes Jahr -- im September gerechnet vier Monate Rendite als zwoelf,
    rund 3.000 zu viel.

    `abfluss_gewichtet` sind datierte Einmalzahlungen des Jahres, jede mit
    dem Teil des Jahres gewichtet, in dem sie schon weg ist. Die Kaufraten
    im Oktober nahmen dem Tagesgeld 66.000, und verzinst wurde trotzdem der
    Stand davor. Einnahmen werden nicht umgekehrt gewichtet: sie kommen wie
    die Sparrate uebers Jahr und bleiben unverzinst.
    """
    basis_tagesgeld = max(round(max(tagesgeld, 0) * anteil) - abfluss_gewichtet, 0)
    zins_tagesgeld = round(basis_tagesgeld * satz_tagesgeld)
    gewinn = round(depot * satz_depot * anteil)
    vorab = (round(depot * min(vorab_satz, max(satz_depot, 0.0)) * anteil)
             if depot > 0 else 0)
    frei = round(max(pauschbetrag, 0) * anteil)
    zinssteuer, frei_zinsen, frei = _steuer_auf(zins_tagesgeld, frei, steuer_quote)
    steuer, frei_vorab, frei = _steuer_auf(vorab, frei, steuer_quote)

    tg = tagesgeld + zins_tagesgeld - zinssteuer + sparrate
    wert = depot + gewinn - steuer
    # Die eingetragene Entnahme wirkt VOR der Kaskade: was heute vom Depot
    # genommen wird, kann heute nicht mehr aus dem Tagesgeld dorthin fliessen.
    dp = wert + depot_abfluss
    ins_depot = 0
    if tg > grenze:
        ins_depot = tg - max(grenze, 0)
    elif entnahme and tg < grenze and dp > 0:
        ins_depot = -min(grenze - tg, dp)
    verkauf, verkaufsteuer, einstand_neu, frei_verkauf = _verkaufsteuer(
        wert, depot if einstand is None else einstand, vorab, depot_abfluss,
        ins_depot, steuer_quote, frei)
    verkaufsteuer = min(verkaufsteuer, max(dp + ins_depot, 0))
    return {"tagesgeld": tg - ins_depot, "depot": dp + ins_depot - verkaufsteuer,
            "policen": policen + zins_policen + einzahlung_policen,
            "einzahlung_policen": einzahlung_policen,
            "rendite": (zins_tagesgeld + zins_policen + gewinn - zinssteuer - steuer
                        - verkaufsteuer),
            "steuer": steuer, "zinssteuer": zinssteuer, "ins_depot": ins_depot,
            "pauschbetrag": {"zinsen": frei_zinsen, "vorab": frei_vorab,
                             "verkauf": frei_verkauf},
            "zins_tagesgeld": zins_tagesgeld, "zins_policen": zins_policen,
            "gewinn_depot": gewinn, "basis_tagesgeld": basis_tagesgeld,
            "tagesgeld_vor_kaskade": tg, "verkauf": verkauf,
            "verkaufsteuer": verkaufsteuer, "einstand": einstand_neu}


#: Eine Funktion fuer beide Modelle: erst der Freibetrag, dann der Satz.
_steuer_auf = _zn.steuer_auf


def _verkaufsteuer(wert: int, einstand: int, vorab: int, depot_abfluss: int,
                   ins_depot: int, steuer_quote: float,
                   frei: int = 0) -> tuple[int, int, int, int]:
    """(verkauft, Steuer darauf, Einstand danach, verbrauchter Pauschbetrag).

    Der Gewinnanteil ist, was am Depotwert nicht Einstand ist; die schon
    gezahlte Vorabpauschale zaehlt zum Einstand, sie wird nicht zweimal
    versteuert. Ein Verkauf nimmt seinen Anteil am Einstand mit, ein Kauf
    legt seinen Betrag dazu. `frei` ist, was vom Pauschbetrag nach Zinsen und
    Vorabpauschale noch uebrig ist.
    """
    einstand = max(einstand, 0) + vorab
    verkauf = max(-depot_abfluss, 0) + max(-ins_depot, 0)
    kauf = max(depot_abfluss, 0) + max(ins_depot, 0)
    if wert <= 0:
        return verkauf, 0, kauf, 0
    gewinn = verkauf * max(0.0, 1.0 - einstand / wert)
    verbraucht = min(frei, gewinn)
    steuer = round((gewinn - verbraucht) * steuer_quote)
    rest = einstand * max(0.0, 1.0 - verkauf / wert)
    return verkauf, steuer, round(rest) + kauf, round(verbraucht)


def _covers(row: Year) -> bool:
    """Deckt das laufende Einkommen dieses Jahres den laufenden Bedarf?"""
    passiv = sum(row.blocks.get(p, 0) for p in PASSIV)
    bedarf = -sum(row.blocks.get(b, 0) for b in BEDARF)
    return passiv >= bedarf


#: Wie die Hochrechnung ihre Basis misst: ueber das ganze Fenster oder, fuer
#: den Konsum, ueber die letzten drei Monate (Jüngst).
Tempo = Literal["schnitt", "juengst"]
TEMPI: tuple[Tempo, ...] = ("schnitt", "juengst")

#: Die Bloecke, in denen Jüngst gilt: nur der Konsum. In `steuern` und
#: `immobilie` sind die meisten Buchungen Klumpen (eine Nachzahlung, eine
#: Reparatur), keine Gewohnheit, und mit vier malgenommen waeren sie falsch.
JUENGST_BLOECKE = ("konsum",)


def _hochrechnung(f, ohne: set[str] | None, tempo: Tempo = "schnitt",
                  reihen: _tk.Reihen | None = None,
                  ausser: frozenset[str] = GERECHNET) -> _fs.Vorschau:
    """Die Vorschau der Hochrechnung: ein Fenster fuer den Haushalt.

    Die Reihe ist die des Haushalts, ueber alle Konten addiert, und die
    Kategorie steht je Block fuer sich. Umbuchungen erkennt die Messung am
    Praefix, Teile ohne Kategorie zaehlen unter dem leeren Schluessel, und die
    einmaligen Planzeilen (`ohne`) sieht sie nicht. Das Fenster hat `f.monate`
    Monate, auch wenn ein Konto spaeter beginnt.

    `tempo="juengst"` rechnet die Kosten in `JUENGST_BLOECKE` nach den letzten
    drei Monaten des Fensters statt nach dem ganzen; alles andere bleibt beim
    Schnitt des Fensters. Zinsen und Kapitalertragsteuer (`GERECHNET`, oder was
    `ausser` nennt) schreibt sie nicht fort.

    `reihen` sind die Reihen mit ihrem Takt zum Stichtag (`_reihen_laden`): Eine
    Reihe mit festem Takt zaehlt mit ihrem Betrag je Termin mal Termine je Jahr,
    das Tempo gilt nur fuer den Rest. Ohne sie zaehlt jede Kategorie mit der
    Summe ihres Fensters.
    """
    je_block = (dict.fromkeys(JUENGST_BLOECKE, _vf.HOCHRECHNUNG_JUENGST)
                if tempo == "juengst" else {})
    return _fs.Vorschau(
        reihe="haushalt", regeln=_vf.HOCHRECHNUNG, regeln_je_block=je_block,
        ausschluss=_ms.Ausschluss(hashes=frozenset(ohne or ())), je_block=True,
        ausser=ausser, since=f.von.isoformat(), until=f.bis.isoformat(), fenster_monate=f.monate,
        reihen=reihen)


def _reihen_laden(conn: sqlite3.Connection, f, ohne: set[str] | None) -> _tk.Reihen | None:
    """Die Reihen zum Stichtag der Hochrechnung (das Ende ihres Fensters), mit den
    Handentscheidungen des Haushalts. Einmalige Planzeilen (`ohne`) sieht die
    Messung nicht und bilden auch keinen Termin."""
    if f is None:
        return None
    return _reihen.laden(conn, f.bis, ausschluss=_ms.Ausschluss(hashes=frozenset(ohne or ())))


def tempo_text(tempo: Tempo, f) -> str:
    """Wie ein Tempo auf den Seiten heisst. Die Zahl der Monate kommt aus dem
    Fenster: ein junges Hauptbuch hat weniger als zwoelf."""
    n = f.monate if f else 0
    if tempo == "juengst":
        n = min(_vf.JUENGST_MONATE, n) if n else _vf.JUENGST_MONATE
        wie = "im Tempo"
    else:
        wie = "im Schnitt"
    if n == 1:
        return f"{wie} des letzten Monats"
    return f"{wie} der letzten {n} Monate" if n else f"{wie} der letzten Monate"


def _basis(conn: sqlite3.Connection, f, ohne: set[str] | None = None, *,
           auch_abgewaehlte: bool = False, tempo: Tempo = "schnitt",
           gemessen: _fs.Gemessen | None = None,
           reihen: _tk.Reihen | None = None,
           ausser: frozenset[str] = GERECHNET,
           ) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]],
                      dict[str, dict[str, _fs.Zerlegung]]]:
    """Die Basis der Hochrechnung, die Monate, wo ein Tempo sie anders misst, und
    woraus sie besteht.

    Das Zweite sind die Kategorien, deren Jahreswert nur die letzten Monate des
    Fensters zaehlt (Jüngst): Block, Kategorie, Monate. Der Rechenweg sagt es.
    Das Dritte zerlegt jede Kategorie in ihre Reihen mit festem Takt und den Rest
    (`fortschreibung.Zerlegung`): Der Rechenweg nennt die Reihen, die Wirkung
    sagt, welche sich bewegt haben.

    Eine fertige Messung (`_fs.messen` mit derselben Vorschau, also auch mit denselben
    `reihen`) spart die Abfrage, wenn beide Tempi gebraucht werden. Ohne `reihen`
    werden sie zum Ende des Fensters geladen.
    """
    from finctl.forecast import prognosebasis as _pb

    if f is None:
        return {}, {}, {}
    if reihen is None:
        reihen = _reihen_laden(conn, f, ohne)
    vorschau = _hochrechnung(f, ohne, tempo, reihen, ausser)
    aus = set() if auch_abgewaehlte else _pb.nicht_fortschreiben()
    out: dict[str, dict[str, int]] = {}
    letzte: dict[str, dict[str, int]] = {}
    teile: dict[tuple[str, str], list[_fs.Fortgeschrieben]] = {}
    for p in _fs.fortschreiben(conn, vorschau, gemessen or _fs.messen(conn, vorschau)):
        kategorien = out.setdefault(p.block, {})
        if not (p.block in FROM_BASE and p.kategorie in aus):
            kategorien[p.kategorie] = kategorien.get(p.kategorie, 0) + p.ergebnis.cents
            teile.setdefault((p.block, p.kategorie), []).append(p)
            if not p.reihe and p.ergebnis.letzte_monate:
                letzte.setdefault(p.block, {})[p.kategorie] = p.ergebnis.letzte_monate
    zerlegt: dict[str, dict[str, _fs.Zerlegung]] = {}
    for (block, kategorie), posten in teile.items():
        rest = next((p for p in posten if not p.reihe), None)
        zerlegt.setdefault(block, {})[kategorie] = _fs.Zerlegung(
            tuple(p for p in posten if p.reihe), rest.ergebnis.cents if rest else 0,
            rest.monate if rest else ())
    # Nach Block und Kategorie, wie die Messung sie vor der Fortschreibung
    # lieferte: Anzeige und Rechenweg lesen in dieser Reihenfolge.
    return ({block: dict(sorted(kat.items())) for block, kat in sorted(out.items())},
            {block: dict(sorted(kat.items())) for block, kat in sorted(letzte.items())},
            {block: dict(sorted(kat.items())) for block, kat in sorted(zerlegt.items())})


def _base_kategorien(conn: sqlite3.Connection, f,
                     ohne: set[str] | None = None, *,
                     auch_abgewaehlte: bool = False,
                     tempo: Tempo = "schnitt",
                     ) -> dict[str, dict[str, int]]:
    """Der gemessene Jahreswert je Block und Kategorie.

    Der Blockwert ist die Summe seiner Kategorien. Rundungsdifferenzen zum
    frueheren Blockwert sind Cent je Kategorie und der Preis dafuer, dass der
    Rechenweg exakt aufgeht.

    Was unter Fortschreibung (/prognosebasis) abgewaehlt ist, faellt heraus -- in den laufenden
    Bloecken. Gehalt, Kredit und Einmaliges haben ihre eigene Quelle. Das
    gilt nur dort, deshalb faellt es erst hier heraus und nicht in der
    Fortschreibung, die eine Kategorie in allen Bloecken streichen wuerde.
    """
    return _basis(conn, f, ohne, auch_abgewaehlte=auch_abgewaehlte, tempo=tempo)[0]


def _tilgungsplaene(aktive_klammern: set[str] | None) -> list[tuple[dict, object]]:
    """Die wirksamen Kredite mit ihrem Tilgungsplan -- einmal gerechnet."""
    from finctl.realestate.loan import (
        amortise,
        lade_kredite,
        nur_wirksame,
        opening_balance_cents,
        segments_from,
    )

    out = []
    for loan in nur_wirksame(lade_kredite(CONFIG_DIR), aktive_klammern or set()):
        try:
            sched = amortise(loan["id"], opening_balance_cents(loan),
                             segments_from(loan))
        except Exception:
            continue
        out.append((loan, sched))
    return out


def _kreditposten(plaene: list[tuple[dict, object]], year: int,
                  after_month: int = 0,
                  endet: dict[str, date] | None = None) -> list[Posten]:
    """Je Kredit die Raten dieses Jahres, mit Anzahl, Rate und Ende."""
    out = []
    for loan, sched in plaene:
        schluss = (endet or {}).get(loan["id"])
        raten = [p for p in sched.payments
                 if p.month.year == year and p.month.month > after_month
                 and not (schluss and p.month >= schluss)]
        if not raten:
            continue
        cents = -sum(p.payment_cents for p in raten)
        betraege = sorted({p.payment_cents for p in raten})
        rate = (eur(betraege[0]) if len(betraege) == 1
                else f"{eur(betraege[0])}–{eur(betraege[-1])}")
        text = (f"{len(raten)} Raten × {rate} laut Tilgungsplan "
                f"({monat(raten[0].month)}–{monat(raten[-1].month)})")
        if schluss and schluss.year == year:
            text += f"; endet {monat(schluss)} durch Verkauf"
        elif raten[-1].month == sched.payments[-1].month:
            text += "; letzte Rate des Plans"
        name = str(loan.get("name") or loan["id"]).split(" --")[0]
        out.append(Posten(label=name, cents=cents, quelle="vertrag",
                          herleitung=text, verweis=str(loan["id"])))
    return out


@dataclass(slots=True)
class Verkauf:
    """Ein geplanter Verkauf, so wie er in der Jahresrechnung ankommt."""

    property_id: str
    name: str
    ab: date                      # erster Monat OHNE das Objekt
    erloes_cents: int = 0         # was der Verkauf einbringt, brutto
    restschuld_cents: int = 0     # was davon die Bank bekommt
    loan_id: str | None = None
    miete_jahr_cents: int = 0     # gemessen, Vorzeichen wie im Ledger
    kosten_jahr_cents: int = 0
    #: Was vom Preis vorher abgeht: Makler, Vorfaelligkeitsentschaedigung.
    verkaufskosten_cents: int = 0
    #: Aus welcher Planklammer, wenn der Verkauf dort steht; None heisst
    #: aus den Objektdaten auf /immobilien.
    klammer: str | None = None
    klammer_id: str | None = None
    #: Auf welchen Monat sich die Restschuld bezieht, wenn der Tilgungsplan
    #: nicht bis zum Verkauf reicht.
    restschuld_stand: date | None = None

    @property
    def netto_cents(self) -> int:
        return self.erloes_cents - self.verkaufskosten_cents - self.restschuld_cents


def restschuld(loan: dict, zum: date) -> tuple[int, date]:
    """Was von einem Kredit offen ist, und auf welchen Monat sich das bezieht.

    Aus dem Tilgungsplan, nicht geschaetzt: die Zahl entscheidet, wie viel von
    einem Verkaufserloes tatsaechlich beim Verkaeufer ankommt, und bei einem
    Objekt mit anfangs unter 1 % Tilgung im Jahr ist der Unterschied zwischen
    Kaufpreis und Nettozufluss der halbe Preis.

    Reicht der Plan nicht bis zum gefragten Monat, kommt der letzte bekannte
    Stand zurueck, zusammen mit seinem Datum. Ein geplanter Verkauf nach dem
    Ende der Zinsbindung ist genau dieser Fall: der Plan endet dort, der
    Verkauf liegt spaeter, und was die Anschlusskondition bis dahin tilgt, weiss
    niemand. Null zurueckzugeben waere die gefaehrliche Luege -- sie machte
    aus einem Verkauf mit 115.000 Restschuld einen ohne.
    """
    from finctl.realestate.loan import amortise, opening_balance_cents, segments_from

    sched = amortise(loan["id"], opening_balance_cents(loan), segments_from(loan))
    if not sched.payments:
        return 0, zum
    offen = [p for p in sched.payments if p.month >= zum]
    if offen:
        return offen[0].balance_cents + offen[0].principal_cents, offen[0].month
    letzte = sched.payments[-1]
    return letzte.balance_cents, letzte.month


def restschuld_cents(loan: dict, zum: date) -> int:
    """Nur die Zahl. Siehe `restschuld` fuer den Stichtag dazu."""
    return restschuld(loan, zum)[0]


def verkaeufe(conn: sqlite3.Connection, base_year: int,
              szenarien: Path | str | None = None, *,
              bis: date | None = None) -> list[Verkauf]:
    """Geplante Verkaeufe: aus Planklammern und aus den Objektdaten.

    EINE Quelle fuer die Rechnung. Eine Verkaufszeile in einer
    eingeschalteten Klammer gewinnt ueber Termin und Preis auf /immobilien --
    dort sind sie ein Vorschlag, in der Klammer eine schaltbare Entscheidung,
    und zwei Verkaeufe desselben Objekts gibt es nicht.

    Aus den Objektdaten wird ohne Preis nichts modelliert. Das ist die
    vorsichtige Richtung: den Kredit enden zu lassen, ohne den Erloes zu
    kennen, hiesse eine Rate streichen und nichts dafuer zahlen -- die
    Rechnung saehe besser aus, weil eine Zahl FEHLT.

    Mit `bis` messen Miete und Kosten des Objekts nur, was bis dahin gebucht
    war (`eingaben`). Termin, Preis und Kredit bleiben, wie sie heute stehen.

    Ein Objekt mit Prognose misst nichts: Seine Miete und seine Kosten kommen aus der
    Prognose (`objektposten`), und `rechnen` zieht dort nichts ab.
    """
    from finctl.realestate.loan import lade_kredite

    namen = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM properties")}
    out: dict[str, Verkauf] = {}
    for s, _i, line in _sz.verkaufszeilen(_szenarien_laden(szenarien)):
        if line.property_id in out or line.property_id not in namen:
            continue
        out[line.property_id] = Verkauf(
            property_id=line.property_id, name=namen[line.property_id],
            ab=date(line.start.year, line.start.month, 1),
            erloes_cents=int(line.amount_cents),
            verkaufskosten_cents=int(line.kosten_cents or 0),
            klammer=s.name, klammer_id=s.id)

    for r in conn.execute(
            "SELECT id, name, planned_sale_on, sale_price_cents FROM properties "
            "WHERE planned_sale_on IS NOT NULL AND sold_on IS NULL "
            "AND sale_price_cents IS NOT NULL AND sale_price_cents > 0"):
        if r["id"] in out:
            continue
        ab = date.fromisoformat(str(r["planned_sale_on"]))
        out[r["id"]] = Verkauf(property_id=r["id"], name=r["name"],
                               ab=date(ab.year, ab.month, 1),
                               erloes_cents=int(r["sale_price_cents"] or 0))
    if not out:
        return []

    kredite = {k.get("property_id"): k for k in lade_kredite(CONFIG_DIR)}
    f = ag.fenster(conn, bis=bis)
    mit_prognose = _kennungen_mit_prognose()
    for v in out.values():
        loan = kredite.get(v.property_id)
        if loan:
            v.loan_id = loan["id"]
            try:
                v.restschuld_cents, stand = restschuld(loan, v.ab)
                if (stand.year, stand.month) != (v.ab.year, v.ab.month):
                    v.restschuld_stand = stand
            except Exception:
                v.restschuld_cents = 0
        _miete_und_kosten_messen(conn, v, f, mit_prognose)
    return sorted(out.values(), key=lambda v: v.ab)


def _kennungen_mit_prognose() -> frozenset[str]:
    """Die Objekte, deren Miete und Kosten die Prognose liefert (`objektposten`)."""
    return frozenset(p.id for p in _objekte.prognosen())


def _miete_und_kosten_messen(conn: sqlite3.Connection, v: Verkauf, f,
                             mit_prognose: frozenset[str]) -> None:
    """Miete und laufende Kosten des Objekts im Fenster, aufs Jahr, in den Verkauf.

    Ein Objekt mit Prognose (`mit_prognose`) misst nichts."""
    if v.property_id in mit_prognose:
        return
    # Aus DEMSELBEN Fenster wie die Basisbloecke, sonst subtrahiert man eine anders
    # gemessene Groesse von ihnen.
    gemessen = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN s.mgmt_category_id IN "
        "  ('immobilie/mieteinnahme','einkommen/mieteinnahmen') "
        "  THEN s.amount_cents END), 0) AS miete, "
        " COALESCE(SUM(CASE WHEN s.mgmt_category_id LIKE 'immobilie/%' "
        "  AND s.mgmt_category_id NOT IN "
        "  ('immobilie/mieteinnahme','einkommen/mieteinnahmen') "
        "  THEN s.amount_cents END), 0) AS kosten "
        "FROM splits s JOIN transactions t ON t.id = s.transaction_id "
        "WHERE s.property_id = ? AND t.booking_date BETWEEN ? AND ?",
        (v.property_id, f.von.isoformat() if f else "",
         f.bis.isoformat() if f else "")).fetchone()
    monate = f.monate if f else 12
    v.miete_jahr_cents = _vf.summe_aufs_jahr(gemessen["miete"] or 0, monate)
    v.kosten_jahr_cents = _vf.summe_aufs_jahr(gemessen["kosten"] or 0, monate)


def _monate_ohne(v: Verkauf, year: int, after_month: int) -> int:
    """Wie viele der noch zu projizierenden Monate dieses Jahres ohne Objekt."""
    return sum(1 for m in range(after_month + 1, 13) if date(year, m, 1) >= v.ab)


def _szenarien_laden(spec_path: Path | str | None = None) -> list:

    path = Path(spec_path) if spec_path else CONFIG_DIR / "szenarien.yaml"
    if not path.exists():
        return []
    return _sz.load(yaml_lesen(path) or {})


_STEIGT_TEXT = (", das Gemessene mit der Inflation seit der Mitte des Messfensters "
                "fortgeschrieben")
_FREQ_TEXT = {"monatlich": "monatlich", "quartalsweise": "quartalsweise",
              "jaehrlich": "jährlich"}


def _planposten(geladen: list, messungen: dict, year: int, after_month: int,
                depotkonten: frozenset[str] = frozenset(),
                steigerung: float = 1.0,
                nominal: frozenset[tuple[str, int]] = frozenset()) -> tuple[
                    list[Posten], int, list[Posten]]:
    """Je Planzeile ein Posten -- und die Einmalabfluesse, fuer die Rendite.

    Der Betrag kommt aus `szenarien.jahreswirkung`, die Herleitung wird
    daneben nur beschrieben. So bleibt es EINE Rechnung.

    `steigerung` ist der Faktor des Jahres seit der Mitte des Messfensters, derselbe
    wie fuer die Reihen der Basis: Was eine Zeile von der Messung abzieht, steigt mit
    ihr. Der geplante Betrag steigt nicht. Eine Wegfall-Zeile ueber den Beitrag in eine
    Police (`nominal`) zieht ihn nominal ab, denn die Ausgabe dafuer ist nominal fest
    (`_beitragsposten`).

    Die zweite Zahl sind die einmaligen Auszahlungen des Jahres, jede mit dem
    Teil des Jahres gewichtet, in dem das Geld schon weg ist -- siehe
    `kaskade`.

    Die dritte Liste sind die Zeilen, die auf einem DEPOTKONTO stehen. Sie
    gehoeren nicht aufs Tagesgeld: wer fuer den Hauskauf Anteile verkauft,
    belastet das Depot, und bis hierher war das Konto einer Planzeile in
    dieser Rechnung ohne jede Wirkung -- eine Zeile auf dem Depot minderte
    stillschweigend das Tagesgeld. Sie zaehlen deshalb auch nicht in den
    gewichteten Abfluss, der nur die Tagesgeldzinsen betrifft.
    """
    horizon = date(year, 12, 1)
    leer = {"cents": 0, "monate": 0, "buchungen": [], "quelle": "keine"}
    out: list[Posten] = []
    aus_depot: list[Posten] = []
    abfluss = 0.0
    for s in _sz.active(geladen):
        for i, line in enumerate(s.lines):
            # Eine erwartete Einnahme zaehlt im Block ihrer Kategorie (`_erwartete_posten`).
            if line.kind == "erwartet" or not zaehlt_in_prognose(line):
                continue
            m = messungen.get((s.id, i), leer)
            steigt = 1.0 if (s.id, i) in nominal else steigerung
            cents = _sz.jahreswirkung(line, m, year, after_month, horizon, steigt)
            if not cents:
                continue
            n = m.get("monate") or 0
            termine = [w for w in line.months(horizon)
                       if w.year == year and w.month > after_month]
            aufs_depot = line.account_id in depotkonten
            if line.frequency == "einmalig":
                text = f"einmalig {monat(line.start)}"
                if cents < 0 and not aufs_depot:
                    abfluss += -cents * sum(13 - w.month for w in termine) / 12
            elif line.kind == "wegfall":
                aktiv = sum(1 for mm in range(after_month + 1, 13)
                            if line.start and date(year, mm, 1) >= line.start
                            and (line.end is None or date(year, mm, 1) <= line.end))
                text = (f"entfällt: {_gemessen_text(m)} "
                        f"({len(m.get('buchungen') or [])} zugeordnete Buchungen) "
                        f"× {aktiv}/{12 if 'takt_jahr' in m else n}"
                        + _STEIGT_TEXT * (steigt != 1.0))
            else:
                text = (f"{len(termine)} × {eur(line.amount_cents)} "
                        f"{_FREQ_TEXT.get(line.frequency, line.frequency)}")
                if n and _sz.gemessen_je_monat(m):
                    text += (f", abzüglich des schon gemessenen Teils "
                             f"({_gemessen_text(m, mit_fenster=True)})"
                             + _STEIGT_TEXT * (steigt != 1.0))
            if aufs_depot:
                text += f", vom Depot ({line.account_id})"
            (aus_depot if aufs_depot else out).append(
                Posten(label=f"{s.name}: {line.label}", cents=cents,
                       quelle="plan", herleitung=text,
                       verweis=f"{s.id}:{i}",
                       einmalig=line.frequency == "einmalig"))
    return out, round(abfluss), aus_depot


#: Die Bloecke, in denen eine erwartete Einnahme zaehlen kann; sonst steht sie in `einmalig`.
_BLOECKE_ERWARTET = (*FROM_BASE, "gehalt", ag.EINMALIG)


def _erwartete_posten(geladen: list, bloecke: Mapping[tuple[str, int], str], year: int,
                      after_month: int) -> dict[str, list[Posten]]:
    """Die erwarteten Einnahmen eines Jahres, je im Block ihrer Kategorie.

    Die Zeile ersetzt die Messung ihrer Kategorie (`szenarien.erwartet_zugeordnet`) und
    zaehlt voll: fester Betrag, keine Steigerung. Im Block ihrer Kategorie steht sie
    neben dem, was dort gemessen bleibt, und nicht in `einmalig` -- nur so kann der
    Paritaetstest beide Modelle Block fuer Block vergleichen. Eine Kategorie, deren
    Block die Rechnung nicht fortschreibt, faellt auf `einmalig` zurueck.
    """
    horizon = date(year, 12, 1)
    out: dict[str, list[Posten]] = {}
    for s in _sz.active(geladen):
        for i, line in enumerate(s.lines):
            if line.kind != "erwartet" or not zaehlt_in_prognose(line):
                continue
            cents = _sz.jahreswirkung(line, {}, year, after_month, horizon)
            if not cents:
                continue
            termine = [w for w in line.months(horizon)
                       if w.year == year and w.month > after_month]
            block = bloecke.get((s.id, i))
            text = (f"erwartete Einnahme: {len(termine)} × {eur(line.amount_cents)} "
                    f"{_FREQ_TEXT.get(line.frequency, line.frequency)}, fester Betrag; "
                    f"{len(line.buchungen)} zugeordnete Buchungen und ihre Reihe zählen "
                    "nicht mehr in der Messung")
            out.setdefault(block if block in _BLOECKE_ERWARTET else ag.EINMALIG, []).append(
                Posten(label=f"{s.name}: {line.label}", cents=cents, quelle="plan",
                       herleitung=text, verweis=f"{s.id}:{i}", kategorie=line.category_id,
                       einmalig=False))
    return out


def _gemessen_text(m: dict, *, mit_fenster: bool = False) -> str:
    """Was die zugeordneten Buchungen in der Basis zaehlen, fuer den Rechenweg einer
    Planzeile: mit Reihen ihr Jahreswert nach Takt, sonst die Summe des Fensters."""
    n = m.get("monate") or 0
    if "takt_jahr" not in m:
        return (f"{eur(m['cents'])} in {n} Monaten" if mit_fenster
                else f"{eur(m['cents'])} gemessen über {n} Monate")
    teile = list(m["takt_reihen"])
    if m["rest_cents"]:
        teile.append(f"Rest {eur(m['rest_cents'])} gemessen über {n} Monate")
    jahr = m["takt_jahr"] + (_vf.summe_aufs_jahr(m["rest_cents"], n) if n else 0)
    return f"{eur(jahr)} im Jahr: " + "; ".join(teile)


def gezaehlte_vertraege(conn: sqlite3.Connection, police: frozenset[str],
                        ) -> list[tuple[dict, str]]:
    """Die Vertraege, die die Jahresrechnung ueber ihre Tatsachen zaehlt, mit dem Block ihrer
    Kategorie: alle, deren Kategorie in einem Block der Basis steht, ausser dem Beitrag in
    eine Police (`police`)."""
    from finctl import abos as _ab

    return [(a, block) for a in _ab.alle_vertraege() if a["id"] not in police
            if (block := ag.block_der_kategorie(conn, a["kategorie"])) in FROM_BASE]


def _vertraege_lesen(conn: sqlite3.Connection, geladen: list, police: frozenset[str],
                     erster: date) -> tuple[tuple[Vertrag, ...], set[str]]:
    """Die Vertraege, die die Jahresrechnung ueber ihre Tatsachen zaehlt, und die Buchungen,
    die sie aus der Messung nehmen.

    Alle, deren Kategorie in einem Block der Basis steht -- ausser dem Beitrag in eine Police
    (`police`): Der bleibt gemessen, nominal fest und mit dem Ende seiner Police
    (`_vertragsenden`). `erster` ist der erste offene Monat; dorthin rueckt eine verstrichene
    Rueckzahlung.
    """
    gezaehlt = gezaehlte_vertraege(conn, police)
    abos = [a for a, _ in gezaehlt]
    pausen = _vt.pausen(conn, geladen, abos)
    return (tuple(Vertrag(abo=a, block=block, pausen=pausen.get(a["id"], ()),
                          rueckzahlungen=tuple(_vt.rueckzahlungen(conn, a, ab=erster)))
                  for a, block in gezaehlt),
            _vt.aus_der_messung(conn, abos))


def ohne_messung(conn: sqlite3.Connection, geladen: list) -> set[str]:
    """Die Buchungen, die die Basis der Hochrechnung nicht misst: die einmaliger Planzeilen,
    die erwarteter Einnahmen samt ihrer Reihe und die der Vertraege, die ueber ihre
    Tatsachen zaehlen."""
    return (_sz.einmalig_zugeordnet(geladen) | _sz.erwartet_zugeordnet(conn, geladen)
            | _vertraege_lesen(conn, geladen, _vt.police_vertraege(), date.today())[1])


def _vertragsenden(conn: sqlite3.Connection, f, geladen: list,
                   base: dict, reihen: _tk.Reihen | None = None,
                   auszahlungen: Mapping[str, _pol.Police] | None = None,
                   police_vertraege: Collection[str] | None = None) -> list[dict]:
    """Gekuendigte Vertraege, gemessen -- ohne dass jemand eine Zeile schreibt.

    Nur fuer den Vertrag, der eine Police speist (`police_vertraege`, ohne Angabe
    `vertraege.police_vertraege`): Alle anderen zaehlt die Rechnung ueber den Vertrag selbst
    (`_vertragsposten`), und der endet mit seinen Terminen. Ihre Reihe zu messen kostete
    Arbeit fuer nichts.

    EIN SACHVERHALT, EINE ANTWORT. Das Ende eines Vertrags steht schon am
    Vertrag. Die Kontoprognose las es und hoerte am Stichtag auf zu buchen;
    diese Rechnung kannte das Feld nicht und sah die Kuendigung erst, wenn die
    alten Buchungen aus dem Messfenster gelaufen waren -- zwoelf Monate lang
    eine Ersparnis, die es laengst gab. Wer sie frueher sehen wollte, musste
    dieselbe Kuendigung ein zweites Mal als Wegfall-Zeile eintragen.

    Gemessen wird wie bei einer Wegfall-Zeile: die Reihe des Vertrags, so wie
    die Basis sie zaehlt (`_vertrag_gemessen`). Damit schrumpft der Abzug von
    selbst, sobald das Fenster ueber das Ende hinweglaeuft -- der Betrag steckt
    dann ja nicht mehr in der Basis, die er kuerzt -- und ein Vertrag, dessen
    Reihe beendet ist, kuerzt nichts: er steckt dort schon nicht mehr.

    Wer beides angelegt hat -- Kuendigung am Vertrag UND Wegfall-Zeile --,
    bekommt den Abzug einmal: was eine eingeschaltete Zeile schon zaehlt,
    bleibt hier draussen. Ausgenommen ist der Vertrag einer Police: seine
    Ausgabe ist nominal fest, die Zeile zieht sie in ihren Monaten genau ab, und
    das Ende zaehlt nur die Monate ausserhalb davon (`pausen`).

    Der Vertrag, der eine Police speist (`auszahlungen`, je Konto die Police),
    endet mit ihrer Auszahlung -- ohne dass jemand `gekuendigt_zum` schreibt: Eine
    Police ist kein gekuendigter Vertrag, sie laeuft aus. Eine frueher
    eingetragene Kuendigung gilt weiter. Seine Ausgabe in der Basis ist nominal
    fest (`_beitragsposten`), also zieht sein Ende auch nominal ab (`nominal`).
    """
    from finctl import abos as _ab

    if f is None:
        return []
    gemessene = [b for s in _sz.active(geladen) for line in s.lines
                 if line.kind == "wegfall" and not line.nur_kontoprognose
                 and zaehlt_in_prognose(line)
                 for b in (_sz.messung(conn, line, f).get("buchungen") or [])]
    schon = {b["dedup_hash"] for b in gemessene}
    # Eine Reihe, die eine Wegfall-Zeile schon abzieht, zaehlt hier nicht noch einmal,
    # auch nicht mit einem Termin vor dem Fenster.
    schon_reihen = (set() if reihen is None else
                    {k for b in gemessene
                     if (r := reihen.nach_teil(b["dedup_hash"], b["kategorie"] or ""))
                     for k in [(r.gegenpartei, r.kategorie)]})
    block_je_kategorie = {k: block for block, kats in base.items() for k in kats}
    police_je_vertrag = {p.beitrag.vertrag: p for p in (auszahlungen or {}).values()
                         if p.beitrag is not None and p.letzter_beitragsmonat()}
    beitraege = {p.beitrag.vertrag: p.beitrag for p in (auszahlungen or {}).values()
                 if p.beitrag is not None}
    if police_vertraege is None:
        police_vertraege = _vt.police_vertraege()
    out = []
    for a in _ab.alle_vertraege():
        if a["id"] not in police_vertraege:
            continue
        block = block_je_kategorie.get(a.get("kategorie"))
        ende, police = _ende_des_vertrags(a, police_je_vertrag.get(a["id"]))
        if not ende or not a["buchungen"] or block not in FROM_BASE:
            continue
        # Der Vertrag einer Police: seine Ausgabe in der Basis ist nominal fest, also
        # zieht auch sein Ende nominal ab. Eine Wegfall-Zeile schliesst ihn hier nicht
        # aus -- sie zieht ihn nur in ihren Monaten ab (`pausen`), und endet sie vor
        # der Auszahlung, bliebe sonst die Ausgabe nach ihr stehen.
        beitrag = beitraege.get(a["id"])
        m = (_vertragsjahr(conn, f, a, reihen, set(), frozenset()) if beitrag
             else _vertragsjahr(conn, f, a, reihen, schon, schon_reihen))
        if m is None:
            continue
        out.append({"id": a["id"], "name": a["name"], "block": block,
                    "ende": ende, "cents": m["cents"],
                    "police": police.name if police else None,
                    "auszahlung": police.beginn if police else None,
                    "nominal": beitrag is not None,
                    "pausen": beitrag.pausen if beitrag else (),
                    "jahr": m["jahr"], "gedeckelt": m["gedeckelt"], "monate": f.monate,
                    "buchungen": m["buchungen"], "rest": m["rest"], "takt": m["takt"]})
    return out


def _vertragsjahr(conn: sqlite3.Connection, f, a: dict, reihen: _tk.Reihen | None,
                  schon: set, schon_reihen: set | frozenset) -> dict | None:
    """Was die Basis von der Reihe eines Vertrags im Jahr zaehlt -- oder None, wenn sie
    nichts zaehlt. `schon` und `schon_reihen` sind, was eine Wegfall-Zeile abzieht."""
    from finctl.ledger import reihe as _reihe

    treffer = [h for h in _reihe.hashes(conn, a["buchungen"], a["betrag_cents"])
               if h not in schon]
    if not treffer:
        return None
    # Nur die Teile in den Kategorien der Reihe: eine aufgeteilte Buchung
    # traegt auch Teile, die den Vertrag nichts angehen, und die faellt
    # eine Kuendigung nicht weg.
    kategorien = {k for _, k in _reihe.paare(conn, a["buchungen"])}
    cents, beitrag = _vertrag_gemessen(conn, f, treffer, kategorien, reihen, schon_reihen)
    gemessen = -beitrag.im_jahr(f.monate)
    if not gemessen:
        return None
    # NIE MEHR VERSPRECHEN, ALS DER VERTRAG KOSTET. Gemessen wird, was in
    # der Basis steckt -- aber eine angehakte Einmalzahlung (ein Geraet
    # zum Tarif) hebt den Monatsschnitt weit ueber die Rate. Die Ersparnis
    # sieht dann doppelt so gross aus wie sie ist, und das ist die
    # gefaehrliche Richtung. Der Rest bleibt in der Basis stehen, wo er
    # als unregelmaessiger Posten hingehoert.
    laut_vertrag = -a["betrag_cents"] * 12 // (a["takt"] or 1)
    gedeckelt = bool(laut_vertrag) and abs(gemessen) > abs(laut_vertrag)
    # Die Buchungen der Reihe, die es am Ende des Fensters gab: was danach
    # kam, kennt die Messung nicht.
    bekannt = conn.execute(
        f"SELECT COUNT(*) FROM transactions "
        f"WHERE dedup_hash IN ({','.join('?' * len(treffer))}) "
        f"  AND booking_date <= ?", (*treffer, f.bis.isoformat())).fetchone()[0]
    return {"cents": cents, "jahr": laut_vertrag if gedeckelt else gemessen,
            "gedeckelt": gedeckelt, "buchungen": bekannt, "rest": beitrag.rest_cents,
            "takt": [f"{r.gegenpartei}: {r.beitrag.text}"
                     for r in beitrag.reihen if r.beitrag]}


def _beitragsausgaben(conn: sqlite3.Connection, f, base: dict, reihen: _tk.Reihen | None,
                      policen: Mapping[str, _pol.Police]) -> list[dict]:
    """Die Ausgabe je Vertrag, der eine Police speist: was die Basis davon im Jahr zaehlt.

    In die Police fliesst nominal der Betrag am Vertrag, und die Ausgabe dafuer soll
    genau so gross sein (`_beitragsposten`). Gemessen wird wie beim Ende des Vertrags,
    aber ohne den Abzug einer Wegfall-Zeile: die zieht ihn nominal ab und liesse sonst
    den Inflationsanteil als wachsenden Rest stehen.
    """
    from finctl import abos as _ab

    if f is None:
        return []
    ids = {p.beitrag.vertrag: p.name for p in policen.values() if p.beitrag is not None}
    if not ids:
        return []
    block_je_kategorie = {k: block for block, kats in base.items() for k in kats}
    out = []
    for a in _ab.alle_vertraege():
        block = block_je_kategorie.get(a.get("kategorie"))
        if a["id"] not in ids or not a["buchungen"] or block not in FROM_BASE:
            continue
        m = _vertragsjahr(conn, f, a, reihen, set(), frozenset())
        if m is not None:
            out.append({"id": a["id"], "name": a["name"], "police": ids[a["id"]],
                        "block": block, "jahr": m["jahr"]})
    return out


def _ende_des_vertrags(a: dict, police: _pol.Police | None,
                       ) -> tuple[date | None, _pol.Police | None]:
    """Der letzte Monat des Vertrags und, wenn es die Auszahlung seiner Police ist,
    diese Police. Was frueher endet -- eine Kuendigung am Vertrag --, gilt."""
    ende = a.get("gekuendigt_zum")
    letzter = police.letzter_beitragsmonat() if police else None
    if letzter is not None and (ende is None or letzter < ende):
        return letzter, police
    return ende, None


def _vertrag_gemessen(conn: sqlite3.Connection, f, treffer: list[str], kategorien: set,
                      reihen: _tk.Reihen | None, schon_reihen: set | frozenset = frozenset(),
                      ) -> tuple[int, _tk.BeitragInBasis]:
    """Die Summe der Teile des Vertrags im Fenster und was die Basis davon zaehlt.

    Mit `reihen` zaehlt eine laufende Reihe mit festem Takt mit ihrem Jahreswert
    (`takt.beitrag_in_basis`), sonst die Summe im Fenster aufs Jahr. Reihen in
    `schon_reihen` zieht schon eine Wegfall-Zeile ab.
    """
    zeilen = conn.execute(
        "SELECT t.dedup_hash, COALESCE(s.mgmt_category_id, ''), t.booking_date, "
        "       s.amount_cents FROM transactions t "
        "JOIN splits s ON s.transaction_id = t.id "
        f"WHERE t.dedup_hash IN ({','.join('?' * len(treffer))}) "
        f"  AND s.mgmt_category_id IN ({','.join('?' * len(kategorien))})",
        (*treffer, *sorted(kategorien))).fetchall()
    alle = [(h, k, date.fromisoformat(tag), int(c)) for h, k, tag, c in zeilen]
    cents = sum(c for _, _, tag, c in alle if f.von <= tag <= f.bis)
    if reihen is None:
        return cents, _tk.BeitragInBasis(0, cents, ())
    if schon_reihen:
        alle = [z for z in alle if not (
            (r := reihen.nach_teil(z[0], z[1])) and (r.gegenpartei, r.kategorie) in schon_reihen)]
    return cents, _tk.beitrag_in_basis(alle, reihen, von=f.von, bis=f.bis)


def _gemessen_vertrag_text(e: dict) -> str:
    """Was die Basis von der Reihe eines gekuendigten Vertrags zaehlt, wie der
    Rechenweg es nennt."""
    if not e["takt"]:
        return (f"{eur(e['cents'])} gemessen über {e['monate']} Monate "
                f"({e['buchungen']} Buchungen der Reihe)")
    teile = list(e["takt"])
    if e["rest"]:
        teile.append(f"Rest {eur(e['rest'])} gemessen über {e['monate']} Monate")
    return f"{eur(-e['jahr'])} im Jahr: " + "; ".join(teile)


def _vertragsposten(vertraege: tuple[Vertrag, ...], year: int, nach: int, mitte: float | None,
                    rate: float) -> dict[str, list[Posten]]:
    """Je Block die Vertraege dieses Jahres: ihre Termine mit dem Betrag am Vertrag, wie
    das Monatsmodell sie bucht (`konten._vertragsposten`), dazu was die Mitzahler erwartet
    zahlen (`vertraege.anteil_am_termin`) und was sie noch schulden.

    Im Basisjahr zaehlen nur die Monate nach `nach`. Kein Termin vor einem Vorrat, keiner nach
    der Kuendigung, keiner in einer Pause.
    """
    out: dict[str, list[Posten]] = {}
    if nach >= 12:
        return out
    for v in vertraege:
        a = v.abo
        termine = _vt.termine(a, v.pausen, ab=date(year, nach + 1, 1), bis=date(year, 12, 31))
        betraege = [_vt.vertragsbetrag(a, termin, mitte=mitte, rate=rate, police=())
                    for termin in termine]
        anteile = [_vt.anteil_am_termin(a, termin, mitte=mitte, rate=rate, police=())
                   for termin in termine]
        if betraege:
            wachst = (f", steigt mit {prozent(rate)} Inflation im Jahr, stetig ab der Mitte des "
                      "Messfensters" if mitte is not None and rate else "")
            out.setdefault(v.block, []).append(Posten(
                label=f"{a['name']} (Vertrag)", cents=sum(betraege), quelle="vertrag",
                verweis=f"abo:{a['id']}",
                herleitung=(f"{len(betraege)} Termine laut Vertrag zu je {eur(a['betrag_cents'])}"
                            f"{wachst}; die zugeordneten Buchungen zählen dafür nicht mehr "
                            "in der Messung" + _vertrag_zusatz(v))))
        if any(anteile):
            out.setdefault(v.block, []).append(Posten(
                label=f"{a['name']}: Anteil der Mitzahler", cents=sum(anteile), quelle="regel",
                verweis=f"abo:{a['id']}",
                herleitung=(f"{sum(1 for c in anteile if c)} Termine ohne angelegten Zeitraum, "
                            "der Anteil der Mitzahler laut Besetzung, am Termin"
                            + (", steigt wie der Betrag am Vertrag" if mitte is not None and rate
                               else ""))))
        zurueck = sum(c for monat_, c in v.rueckzahlungen
                      if monat_.year == year and monat_.month > nach)
        if zurueck:
            out.setdefault(v.block, []).append(Posten(
                label=f"{a['name']}: Rückzahlungen offen", cents=zurueck, quelle="regel",
                verweis=f"abo:{a['id']}",
                herleitung="offener Anteil der Mitzahler laut Vertrag, im Einsammel-Monat"))
    return out


def _vertrag_zusatz(v: Vertrag) -> str:
    """Was am Vertrag Termine ausfallen laesst, fuer den Rechenweg."""
    a, teile = v.abo, []
    if a["vorrat_bis"]:
        teile.append(f"bezahlt bis {monat(a['vorrat_bis'])}")
    if a["gekuendigt_zum"]:
        teile.append(f"gekündigt zum {monat(a['gekuendigt_zum'])}")
    if v.pausen:
        teile.append("ausgesetzt durch eine Wegfall-Zeile")
    return f" ({', '.join(teile)})" if teile else ""


def _beitragsposten(beitraege: tuple[dict, ...] | list[dict], share: float, fakt: float,
                    anteil_text: str) -> dict[str, list[Posten]]:
    """Je Block die Ausgabe fuer eine Police ohne Inflation.

    Die Basis waechst mit der Inflation, der Beitrag in die Police nicht: es
    fliesst nominal, was der Vertrag sagt. Damit gilt, was `policen` verspricht --
    in die Police geht genau, was die Hochrechnung als Beitrag abzieht --, und
    eine Wegfall-Zeile ueber den Beitrag (nominal) laesst keinen wachsenden Rest
    stehen. Der Posten gibt den Inflationsanteil der gemessenen Ausgabe zurueck.
    """
    out: dict[str, list[Posten]] = {}
    for b in beitraege:
        cents = round(b["jahr"] * (fakt - 1.0) * share)
        if not cents:
            continue
        out.setdefault(b["block"], []).append(Posten(
            label=f"{b['name']}: Beitrag bleibt nominal", cents=cents, quelle="regel",
            verweis=f"abo:{b['id']}",
            herleitung=(f"{b['name']} zahlt in {b['police']} ein, nominal fest: "
                        f"{eur(b['jahr'])} im Jahr bleiben {eur(b['jahr'])}; die Inflation "
                        f"der gemessenen Ausgabe oben ({faktor(fakt)}) fällt hier "
                        f"zurück{anteil_text}")))
    return out


def _pausiert(pausen: tuple[tuple[date, date | None], ...], tag: date) -> bool:
    """Ob eine Wegfall-Zeile den Vertrag in diesem Monat schon abzieht."""
    return any(von <= tag and (bis is None or tag <= bis) for von, bis in pausen)


def _vertragsende_posten(enden: list[dict], year: int, after_month: int,
                         seit: float, inflation: float) -> dict[str, list[Posten]]:
    """Je Block die Abzuege dieses Jahres aus gekuendigten Vertraegen."""
    out: dict[str, list[Posten]] = {}
    for e in enden:
        aktiv = [mm for mm in range(after_month + 1, 13)
                 if date(year, mm, 1) > e["ende"]
                 and not _pausiert(e.get("pausen", ()), date(year, mm, 1))]
        if not aktiv:
            continue
        # Mit derselben Inflation wie die Basis, die er kuerzt. Sonst bliebe
        # nach einer Kuendigung ein wachsender Rest einer Zahlung stehen, die
        # es nicht mehr gibt. Die Ausgabe fuer eine Police wachst nicht (sie steht
        # nominal in der Basis), also faellt sie auch ohne Inflation weg.
        jahr = e["jahr"] if e.get("nominal") else ann.grow(e["jahr"], seit, inflation)
        cents = round(jahr * len(aktiv) / 12)
        if not cents:
            continue
        woher = (f"auf die Vertragsrate begrenzt; gemessen waren {eur(e['cents'])} "
                 f"in {e['monate']} Monaten, darin steckt Einmaliges"
                 if e["gedeckelt"] else _gemessen_vertrag_text(e))
        if e.get("police"):
            label = f"{e['name']} endet mit der Auszahlung"
            grund = (f"letzter Beitrag {monat(e['ende'])}, {e['police']} zahlt "
                     f"{monat(e['auszahlung'])} aus")
        else:
            label, grund = f"{e['name']} gekündigt", f"gekündigt zum {monat(e['ende'])}"
        out.setdefault(e["block"], []).append(Posten(
            label=label, cents=cents, quelle="vertrag",
            verweis=f"abo:{e['id']}",
            herleitung=f"{grund}: {woher} × {len(aktiv)}/12 Monate ohne Vertrag"))
    return out


def gehalt_median_cents(conn: sqlite3.Connection, monate: int = 24,
                        vor: date | None = None) -> int | None:
    """Der Median der Gehaltsmonate, aus dem Ledger -- NUR ALS VERGLEICH.

    Keine Rechnung nimmt ihn: beide Modelle rechnen mit der Untergrenze aus den Annahmen
    (Schritt 5b, E.3). Die Seite `/annahmen` zeigt ihn neben ihr, damit man sieht, wie
    vorsichtig die Untergrenze ist.

    GEMESSEN und nicht eingetragen: eine Zahl, die von Hand nachgefuehrt werden muss,
    wird nicht nachgefuehrt.

    Je MONAT, nicht je Buchung: ein Monat mit zwei Zahlungen ergaebe sonst
    zwei kleine statt einer richtigen Zahl. Der laufende Monat bleibt
    draussen, solange er unvollstaendig ist.

    Gibt None zurueck, wenn nichts zu messen ist -- eine frische Installation
    hat keine Gehaltsmonate, und dann gilt die Vorgabe aus der Datei.

    `vor` ist der Tag, an dem gemessen wird; ohne Angabe heute. Gezaehlt
    werden die `monate` vollen Monate davor, gerechnet ab dem Monatsersten.
    Ein Zweig fragte frueher die Uhr von SQLite (`date('now')`) und liess sich
    deshalb nicht auf einen Tag festnageln.
    """
    import statistics

    vor = vor or date.today()
    erster = date(vor.year, vor.month, 1)
    von = ag._plus_monate(erster, -int(monate))
    werte = [r[0] for r in conn.execute(
        "SELECT SUM(s.amount_cents) FROM splits s "
        "JOIN transactions t ON t.id = s.transaction_id "
        "WHERE s.mgmt_category_id = 'einkommen/gehalt' "
        "  AND t.booking_date >= ? AND t.booking_date < ? "
        "GROUP BY substr(t.booking_date, 1, 7)",
        (von.isoformat(), erster.isoformat())) if r[0]]
    return int(round(statistics.median(werte))) if werte else None


def _salary(year: int, base_year: int, a: Annahmen) -> int:
    """Das volle Monatsgehalt dieses Jahres: die Untergrenze, fortgeschrieben.

    Die UNTERGRENZE aus den Annahmen, in beiden Modellen (Schritt 5b, E.3). "Zu
    vorsichtig" ist gewollt: ein Haushalt, der mit dem schlechtesten Monat rechnet, wird
    von einem besseren nicht enttaeuscht. Der Median steht auf `/annahmen` daneben, als
    Vergleich, und geht in keine Rechnung ein.

    Fortgeschrieben mit der GEHALTSsteigerung, nicht mit der Inflation. Beide
    auf denselben Wert zu setzen unterstellt, dass die Inflation dauerhaft
    eingeholt wird -- moeglich, aber eine Annahme, die sichtbar sein soll. Die
    Steigerung kommt zum 1. Januar; das Monatsmodell nimmt dieselbe Regel
    (`assumptions.gehalt_im_jahr`).

    Teilzeit zieht davon ab, als eigener Posten aus der Planung
    (`_teilzeitposten`).
    """
    return ann.gehalt_im_jahr(_gehalt_basis(a), year, base_year, a.gehalt_steigerung)


def _gehalt_basis(a: Annahmen) -> int:
    """Der Monatswert, von dem das Gehalt ausgeht: die Untergrenze aus den Annahmen.

    Fehlt sie, ist das derselbe Fehler wie beim Lesen der Annahmen -- eine
    Rechnung ohne Gehalt waere eine sichere, falsche Zahl.
    """
    if a.gehalt_untergrenze_cents is None:
        raise KeyError("erwerbseinkommen.netto_floor_monatlich_cents fehlt in den "
                       "Annahmen. Die Untergrenze ist das Gehalt, mit dem gerechnet wird.")
    return a.gehalt_untergrenze_cents


def _teilzeitposten(zeilen: list, year: int, after_month: int,
                    monatlich: int, rente_ab: date | None = None) -> list[Posten]:
    """Was die Teilzeit dieses Jahr vom Gehalt wegnimmt, je Planzeile.

    Monatsgenau: ein Wechsel im Juli laesst sechs Monate voll. Negativ und im
    Block `gehalt`, damit das Gehalt im Rechenweg voll dasteht und die
    Entscheidung daneben -- mit ihrem Preis.
    """
    je: dict[tuple[str, int], list] = {}
    for mm in range(after_month + 1, 13):
        if rente_ab is not None and date(year, mm, 1) >= rente_ab:
            break                       # ab der Rente gibt es kein Gehalt mehr
        z = _sz.teilzeit_im_monat(zeilen, date(year, mm, 1))
        if z is not None:
            je.setdefault((z[0].id, z[1]), [z, 0])[1] += 1
    out = []
    for (sid, i), ((s, _i, line), n) in je.items():
        weniger = monatlich - round(monatlich * line.anteil)
        if not weniger:
            continue
        out.append(Posten(
            label=f"{s.name}: {line.label}", cents=-weniger * n, quelle="plan",
            verweis=f"{sid}:{i}",
            herleitung=(f"{eur(monatlich)} je Monat × {round(100 - line.anteil * 100)} % "
                        f"weniger × {n} Monate ({round(line.anteil * 100)} % "
                        f"ab {monat(line.start)})")))
    return out


def _gehaltsposten(year: int, base_year: int, nach: int, share: float,
                   a: Annahmen, rente_ab: date | None) -> list[Posten]:
    """Das volle Gehalt des Jahres -- bis zum Monat vor dem Rentenbeginn."""
    monatlich = _salary(year, base_year, a)
    arbeit = _arbeitsmonate(year, nach, rente_ab)
    voll = arbeit == 12 - nach
    gehalt = round(monatlich * 12 * share) if voll else monatlich * arbeit
    if not gehalt:
        return []
    wachstum = a.gehalt_steigerung
    text = (f"Untergrenze {eur(_gehalt_basis(a))} je Monat aus den Annahmen"
             f" × {faktor((1 + wachstum) ** max(year - base_year, 0))} Gehaltssteigerung"
            + (" × 12" + (f" × {12 - nach}/12 Restmonate" if share < 1 else "") if voll
               else f" × {arbeit} Monate bis zum Rentenbeginn {monat(rente_ab)}"))
    return [Posten(label="Gehalt", cents=gehalt, quelle="annahme",
                   herleitung=text, verweis="einkommen/gehalt")]


@dataclass(frozen=True, slots=True)
class _Policenjahr:
    """Was die Policen in einem Jahr tun, damit `rechnen` es nur einsetzt."""

    #: Die Anteile am Jahresende; eine auszahlende Police steht auf null.
    anteile: dict[str, int]
    #: Zu Jahresbeginn: der Stand der Policen, die auszahlen. Er verlaesst den Topf.
    abgang: int
    #: Der Zins der Policen, die im Topf bleiben, samt dem Rest des Topfs.
    zins: int
    #: Der Zins der Policen, die in diesem Jahr auszahlen, bis zur Auszahlung.
    zins_aus: int
    #: Beitraege der Policen, die bleiben, und derer, die auszahlen.
    einzahlung: int
    einzahlung_aus: int
    verrentet: list[Posten]
    umgeschichtet: list[Posten]
    zum_depot: int
    zum_tagesgeld: int
    #: Was der Versicherer von den Kapitalauszahlungen einbehielt.
    abzug: int
    rendite: list[Posten]
    beitraege: list[Posten]


def _takt_text(takt: int) -> str:
    return {1: "im Monat", 12: "im Jahr"}.get(takt, f"alle {takt} Monate")


def _satz_text(p: _pol.Police, depotsatz: float) -> str:
    if not p.kosten_bekannt:
        return f"{prozent(depotsatz)} (Kosten nicht bekannt, 0 angesetzt)"
    return (f"{prozent(p.satz(depotsatz))} nach Kosten "
            f"(Depot {prozent(depotsatz)} − Kosten {prozent(p.kosten_pa)})")


def _vergleichstext(v: _pol.Vergleich, pw) -> str:
    if pw.satz is None:
        return "Prüfwert ohne Satz, nicht vergleichbar"
    if v.modell_cents is None:
        return ("Prüfwert nicht vergleichbar"
                + (f", Beitrag endet {monat(v.endet)}" if v.endet else ""))
    abweichung = f"{abs(v.abweichung) * 100:.1f}".replace(".", ",")
    return (f"Prüfwert der Mitteilung {eur_genau(pw.cents)} zum {monat(pw.zum)} bei "
            f"{prozent(pw.satz)}; Modell bei {prozent(v.satz)} zum selben Datum "
            f"{eur_genau(v.modell_cents)}, {'+' if v.abweichung >= 0 else '−'}"
            f"{abweichung} % gegen den Prüfwert")


def rechenbeginn(m: Monat) -> date:
    """Der Monat, ab dem die Hochrechnung rechnet: die vergangenen Monate des Basisjahrs
    stecken im Anfangsbestand."""
    return _vf.add_months(date(m.base_year, 1, 1), m.vergangen)


def pruefvergleiche(e: Eingaben) -> dict[str, str]:
    """Je Rentenquelle mit Pruefwert der Vergleichstext, den auch die Herleitung der
    Auszahlung nennt (`_auszahlungstext`): eine Stelle, damit /renten und
    /hochrechnung nicht auseinanderlaufen. Eine Quelle ohne Police, Stand oder
    Pruefwert fehlt."""
    start = rechenbeginn(e.monat)
    return {q.id: _vergleichstext(
                _pol.vergleichen(e.monat.policen_je_konto[q.konto], e.policen[q.konto],
                                 e.policen[q.konto].pruefwert, start),
                e.policen[q.konto].pruefwert)
            for q in e.rentenquellen
            if q.konto in e.policen and e.policen[q.konto].pruefwert is not None
            and e.monat.policen_je_konto.get(q.konto)}


def _pruefsatztext(q, pw) -> str:
    """Der Pruefwert einer Quelle ohne Police, und welcher Satz von Stand und Beitrag
    zu ihm fuehrt -- der, den die Mitteilung unterstellt, auch wenn sie ihn nicht nennt."""
    genannt = f" bei {prozent(pw.satz)} laut Mitteilung" if pw.satz is not None else ", ohne Satz"
    unterstellt = _renten.satz_zu(q, pw.zum, pw.cents)
    fuehrt = (f"von Stand und Beitrag führt ein Satz von {prozent(unterstellt)} zu ihm"
              if unterstellt is not None else "kein Satz von Stand und Beitrag führt zu ihm")
    return f"Prüfwert der Mitteilung {eur_genau(pw.cents)} zum {monat(pw.zum)}{genannt}; {fuehrt}"


def _teilzeittext(q, beginn: date, teilzeit: tuple[float, date] | None,
                  rente_ab: date | None) -> str:
    """Die Auszahlung vor Abzug ohne und mit der Teilzeit aus den Annahmen."""
    text = f"Auszahlung ohne Teilzeit {eur_genau(q.cents)}"
    if teilzeit is None:
        return text
    anteil, ab = teilzeit
    mit = _renten.auszahlung_cents(q, beginn, _renten.teilzeit_ab(anteil, ab), rente_ab)
    return (f"{text}, mit Teilzeit ({prozent(anteil)} ab {monat(ab)} laut Annahmen) "
            f"{eur_genau(mit)} ({eur_genau(mit - q.cents)})")


def modellzeile(q, beginn: date, teilzeit: tuple[float, date] | None,
                rente_ab: date | None) -> str:
    """Was /renten zu einer betrieblichen Altersvorsorge mit Modell zeigt: Stand,
    Beitrag, Satz, Pruefwert und die Auszahlung mit und ohne Teilzeit. Die Satzrechnung
    ist dieselbe wie in der Herleitung der Hochrechnung (`_modelltext`)."""
    s = _renten.satz(q, beginn)
    teile = [(f"Stand {eur_genau(q.stand_cents)} zum {monat(q.stand_wert)}, Beitrag des "
              f"Arbeitgebers {eur_genau(q.beitrag_ag_cents)} im Jahr (nominal fest)")]
    if s is not None:
        teile.append(f"Satz {prozent(s)}, der von beidem zu {eur_genau(q.cents)} "
                     f"zum {monat(beginn)} führt")
    if q.pruefwert is not None:
        teile.append(_pruefsatztext(q, q.pruefwert))
    teile.append(_teilzeittext(q, beginn, teilzeit, rente_ab))
    return "; ".join(teile)


def _auszahlungstext(q, p: _pol.Police, stand: int, start: date, depotsatz: float) -> str:
    """Woraus die Auszahlung einer Police besteht: Stand, Beitrag, Satz nach Kosten
    -- und der Pruefwert der Mitteilung daneben, oder ohne ihn ihr Betrag."""
    beitrag = "ohne Beitrag"
    if p.beitrag is not None:
        endet = p.beitrag.unterbrechung(start, p.beginn)
        beitrag = (f"+ Beitrag {eur_genau(p.beitrag.cents)} {_takt_text(p.beitrag.takt)} "
                   f"({p.beitrag.name}, nominal fest) bis "
                   f"{monat(endet or p.letzter_beitragsmonat())}"
                   + (", danach ohne" if endet else ""))
    text = (f"Policenwert {eur_genau(stand)} {beitrag}, Rendite {_satz_text(p, depotsatz)}, "
            f"monatlich fortgeschrieben bis {monat(p.beginn)}")
    if p.pruefwert is not None:
        return f"{text}; " + _vergleichstext(
            _pol.vergleichen(stand, p, p.pruefwert, start), p.pruefwert)
    return (f"{text}; laut Schreiben {eur(q.cents)}"
            + (" in heutiger Kaufkraft" if q.kaufkraft == "heute" else ""))


def _restmonate(share: float) -> str:
    """Die Monate, die das Basisjahr noch rechnet; ein volles Jahr nennt keine."""
    n = round(share * 12)
    return f" in den {n} Restmonaten" if share < 1 else ""


def _policenrendite(e: Eingaben, fort: _pol.Fortschritt, anteile: dict[str, int],
                    rest: int, zins_rest: int, anteil_text: str,
                    share: float) -> list[Posten]:
    """Der Zins je Police mit ihrem Satz nach Kosten, dazu der Rest des Topfs mit
    dem Depotsatz. Ihre Summe ist der Zins der Policen.

    Eine Police wird monatlich fortgeschrieben, in den Restmonaten des Basisjahrs
    also nur ueber diese Monate -- nicht als Jahreszins mal Bruchteil. Der Rest
    des Topfs ohne Police rechnet noch so.
    """
    a = e.annahmen
    out = []
    for konto, zins in fort.zins.items():
        p = e.policen[konto]
        dazu = (f", Beiträge {eur_genau(fort.beitrag[konto])} dazu"
                if fort.beitrag[konto] else "")
        out.append(Posten(
            label=p.name, cents=zins, quelle="rendite", verweis="policen",
            herleitung=(f"{eur_genau(anteile[konto])}{_restmonate(share)} zu "
                        f"{_satz_text(p, a.rendite_depot)}, monatlich{dazu}")))
    out.append(Posten(label="Policen", cents=zins_rest, quelle="rendite", verweis="policen",
                      herleitung=f"{eur(rest)} × {prozent(a.rendite_depot)}{anteil_text}"))
    return [p for p in out if p.cents]


def _policenbeitraege(e: Eingaben, fort: _pol.Fortschritt, share: float) -> list[Posten]:
    out = []
    for konto, cents in fort.beitrag.items():
        p = e.policen[konto]
        if cents:
            n = cents // p.beitrag.cents
            out.append(Posten(
                label=f"Beitrag in {p.name}", cents=cents, quelle="regel",
                verweis=f"rente:{p.quelle}",
                herleitung=(f"{n} × {eur_genau(p.beitrag.cents)}{_restmonate(share)} laut "
                            f"Vertrag {p.beitrag.name}, nominal fest: die Ausgabe steht in "
                            "ihrem Block, hier kommt sie in der Police an "
                            "(Umschichtung, kein neues Geld)")))
    return out


def _policenjahr(e: Eingaben, year: int, nach: int, share: float, anteile: dict[str, int],
                 po: int, start: date, beginn_von, anteil_text: str) -> _Policenjahr:
    """Die Policen durch dieses Jahr: wachsen mit Beitrag und Kosten, zahlen aus.

    Eine auszahlende Police rechnet bis zum Monat vor ihrer Auszahlung; ihr Stand
    dann geht ins Depot (oder wird verrentet). `po` ist der Topf zu Jahresbeginn.
    """
    a = e.annahmen
    fort = _pol.fortschreiben(anteile, e.policen, a.rendite_depot, year, nach)
    nachher = {**anteile, **fort.ende}
    texte = {q.konto: _auszahlungstext(q, e.policen[q.konto], e.monat.policen_je_konto[q.konto],
                                       start, a.rendite_depot)
             for q in e.rentenquellen
             if q.konto in e.policen and e.monat.policen_je_konto.get(q.konto)
             and (b := beginn_von(q)) is not None and b.year == year}
    w = _policenwechsel(e.rentenquellen, year, nachher, a.rentenabzug, beginn_von, texte)
    aus = {k for k, v in fort.ende.items() if v and not nachher[k]}
    # Was kein Eintrag in den Renten fuehrt, verzinst der Depotsatz wie bisher.
    rest = max(po - sum(anteile[k] for k in fort.ende), 0)
    zins_rest = round(rest * a.rendite_depot * share)
    return _Policenjahr(
        anteile=nachher, abgang=sum(anteile[k] for k in aus),
        zins=sum(z for k, z in fort.zins.items() if k not in aus) + zins_rest,
        zins_aus=sum(fort.zins[k] for k in aus),
        einzahlung=sum(b for k, b in fort.beitrag.items() if k not in aus),
        einzahlung_aus=sum(fort.beitrag[k] for k in aus),
        verrentet=w.verrentet, umgeschichtet=w.umgeschichtet, zum_depot=w.zum_depot,
        zum_tagesgeld=w.zum_tagesgeld, abzug=w.abzug,
        rendite=_policenrendite(e, fort, anteile, rest, zins_rest, anteil_text, share),
        beitraege=_policenbeitraege(e, fort, share))


def _im_ruhestand(rente_ab: date | None, year: int) -> bool:
    return rente_ab is not None and year >= rente_ab.year


def _arbeitsmonate(year: int, after_month: int, rente_ab: date | None) -> int:
    """Monate dieses Jahres mit Gehalt: nach den gebuchten, vor der Rente."""
    return sum(1 for mm in range(after_month + 1, 13)
               if rente_ab is None or date(year, mm, 1) < rente_ab)


def _anteil_im_monat(zeilen: list):
    """Der Anteil am Gehalt je Monat, wie die Teilzeitzeilen ihn sagen; None: voll."""
    def anteil(monat_: date) -> float | None:
        z = _sz.teilzeit_im_monat(zeilen, monat_)
        return z[2].anteil if z is not None else None
    return anteil


def _modelltext(q, beginn: date) -> str:
    """Woraus der Satz einer betrieblichen Altersvorsorge besteht: Stand und Beitrag."""
    return (f"Satz {prozent(_renten.satz(q, beginn))} aus Stand {eur(q.stand_cents)} zum "
            f"{monat(q.stand_wert)} und {eur(q.beitrag_ag_cents)} Beitrag je Jahr")


def _kapitalposten(q, beginn: date, year: int, inflation: float, abzug: float,
                   teilzeit: tuple, rente_ab: date | None) -> Posten:
    """Ein Kapital ohne Police, einmal ausgezahlt, ohne Abzug versteuert.

    Eine betriebliche Altersvorsorge mit Modell nennt ihren Satz immer. Bei
    Teilzeit zahlt sie weniger als im Schreiben: ihr Beitrag haengt am Gehalt
    (`renten.auszahlung_cents`).
    """
    schreiben = _renten.nominal_cents(q, year, inflation)
    cents = (_renten.auszahlung_cents(q, beginn, _anteil_im_monat(teilzeit), rente_ab)
             if q.hat_modell and teilzeit else schreiben)
    netto = round(cents * (1 - abzug))
    abzug_text = f"{monat(beginn)} − {round(abzug * 100)} % Steuer und KV"
    modell = q.hat_modell and _renten.satz(q, beginn) is not None
    if cents != schreiben:
        herleitung = (f"Kapital {eur(cents)} statt {eur(schreiben)} laut Schreiben: der "
                      "Beitrag des Arbeitgebers sinkt mit der Teilzeit "
                      f"({_modelltext(q, beginn)}), {abzug_text}")
    elif modell:
        herleitung = (f"Kapital laut Schreiben {eur(cents)} ({_modelltext(q, beginn)}), "
                      f"{abzug_text}")
    else:
        herleitung = f"Kapital laut Schreiben {eur(cents)}, {abzug_text}"
    return Posten(label=q.name, cents=netto, quelle="vertrag", verweis=f"rente:{q.id}",
                  einmalig=True, herleitung=herleitung)


def _rentenposten(quellen: list, year: int, after_month: int, inflation: float,
                  abzug: float, beginn_von=_renten.beginn, teilzeit: tuple = (),
                  rente_ab: date | None = None) -> list[Posten]:
    """Je Rente ein Posten: der Betrag des Schreibens, nominal und nach Abzug.

    Heutige Kaufkraft waechst mit der Inflation -- Rentenanpassungen sind
    hier die Inflation, nicht mehr. Ein Kapital ohne Police im Bestand kommt
    einmal, ohne Abzug: versteuert wird nur sein Ertrag.

    `beginn_von` sagt, ab wann eine Quelle zahlt. Ohne eigenes Datum fragt
    `renten.beginn` die Einrichtung, und das darf `rechnen` nicht je Jahr tun.
    `teilzeit` sind die Teilzeitzeilen eingeschalteter Klammern, `rente_ab` das
    Ende des Gehalts: beides trifft nur eine betriebliche Altersvorsorge mit Modell.
    """
    out = []
    for q in quellen:
        beginn = beginn_von(q)
        if beginn is None:
            continue
        verweis = f"rente:{q.id}"
        if q.art == "kapital":
            if q.konto is None and beginn.year == year and beginn.month > after_month:
                out.append(_kapitalposten(q, beginn, year, inflation, abzug, teilzeit,
                                          rente_ab))
            continue
        n = sum(1 for mm in range(after_month + 1, 13) if date(year, mm, 1) >= beginn)
        if not n:
            continue
        je_monat = _renten.nominal_cents(q, year, inflation)
        netto = round(je_monat * (1 - abzug))
        out.append(Posten(
            label=q.name, cents=netto * n, quelle="vertrag", verweis=verweis,
            herleitung=(f"{eur(q.cents)} laut Schreiben"
                        + (f" × {faktor(je_monat / q.cents)} Inflation" if q.cents
                           and q.kaufkraft == "heute" else "")
                        + f" − {round(abzug * 100)} % Steuer und KV = {eur(netto)}"
                        f" je Monat × {n} Monate ab {monat(beginn)}")))
    return out


@dataclass(slots=True)
class _Wechsel:
    """Was die Policen tun, die in diesem Jahr auszahlen."""

    #: Posten fuer den Block `rente`: das verrentete Guthaben.
    verrentet: list[Posten] = field(default_factory=list)
    #: Posten zum Lesen: je Kapitalauszahlung brutto ins Depot und ihr Abzug;
    #: die Summe ist, was ins Depot kommt.
    umgeschichtet: list[Posten] = field(default_factory=list)
    zum_depot: int = 0
    zum_tagesgeld: int = 0
    #: Was der Versicherer von einer Kapitalauszahlung einbehielt.
    abzug: int = 0


def _kapital_auszahlen(w: _Wechsel, q, wert: int, abzug: float, beginn: date,
                       text: str | None) -> None:
    """Eine Kapitalauszahlung ins Depot, nach dem Abzug des Versicherers."""
    einbehalten = round(wert * abzug)
    netto = wert - einbehalten
    w.zum_depot += netto
    w.abzug += einbehalten
    verweis = f"rente:{q.id}"
    rechnung = (f"brutto {eur_genau(wert)} − {round(abzug * 100)} % Abzug "
                f"{eur_genau(einbehalten)} = netto {eur_genau(netto)} ins Depot; "
                if einbehalten else "")
    w.umgeschichtet.append(Posten(
        label=f"{q.name} ausgezahlt ins Depot", cents=wert, quelle="regel", verweis=verweis,
        herleitung=rechnung + (text or (
            f"Policenwert fortgeschrieben mit dem Depotsatz, "
            f"{monat(beginn)}; laut Schreiben {eur(q.cents)}"
            + (" in heutiger Kaufkraft" if q.kaufkraft == "heute" else "")))))
    if einbehalten:
        w.umgeschichtet.append(Posten(
            label=f"{q.name}: Steuer und KV auf die Auszahlung", cents=-einbehalten,
            quelle="annahme", verweis=verweis, einmalig=True,
            herleitung=(f"{eur_genau(wert)} × {round(abzug * 100)} %, vom Versicherer "
                        "einbehalten: das Tagesgeld zahlt ihn nicht, ins Depot kommt der Rest")))


def _policenwechsel(quellen: list, year: int, anteile: dict[str, int],
                    abzug: float = 0.0, beginn_von=_renten.beginn,
                    texte: Mapping[str, str] | None = None) -> _Wechsel:
    """Policen, die dieses Jahr auszahlen: ihr Anteil verlaesst den Topf.

    Als Kapital geht er ins Depot -- eine Umschichtung, kein Geldfluss. Als
    Rente wird er verrentet: er verlaesst das Vermoegen, und die Rente kommt
    dafuer als Einnahme. Der Anteil ist der Stand zur Auszahlung
    (`policen.fortschreiben`); `texte` sagt je Konto, wie er entstand. Ohne Text
    steht der Betrag des Schreibens daneben.

    Auf ein ausgezahltes Kapital geht derselbe Abzug wie auf eine Rente --
    bewusst vorsichtig, ohne die Schichten und Altvertraege zu unterscheiden.
    Er geht von der Auszahlung selbst ab, wie der Versicherer die Steuer
    einbehaelt: ins Depot kommt der Rest, und das Tagesgeld zahlt nichts. Der
    Abzug steht neben der Auszahlung und in keinem Block.
    """
    w = _Wechsel()
    for q in quellen:
        beginn = beginn_von(q)
        wert = anteile.get(q.konto or "")
        if not wert or beginn is None or beginn.year != year:
            continue
        anteile[q.konto] = 0
        if q.art == "kapital":
            _kapital_auszahlen(w, q, wert, abzug, beginn, (texte or {}).get(q.konto))
        else:
            w.zum_tagesgeld += wert
            w.verrentet.append(Posten(
                label=f"{q.name}: Guthaben verrentet", cents=-wert, quelle="regel",
                verweis=f"rente:{q.id}", einmalig=True,
                herleitung=((texte or {}).get(q.konto) or
                            f"Policenwert zum Rentenbeginn {monat(beginn)}")
                           + "; dafuer kommt die Monatsrente"))
    return w


def target_under(assumptions: Path | str, *, declared_cents: int,
                 declared_inflation: float, years: int) -> int:
    """Das Ziel unter den Annahmen DIESES Laufs.

    Ohne diese Umrechnung ist der Szenarienvergleich unstimmig, und zwar auf
    eine Art, die wie ein Rechenfehler aussieht: bei 3 % statt 2 % Inflation
    steigen Einnahmen UND Kosten schneller, die Kreditrate bleibt nominal
    fest, und als Nettosparer mit Festzinsdarlehen kommt er nominal besser
    heraus. Das pessimistische Szenario lieferte damit mehr Endkapital als die
    Basis.

    Oekonomisch stimmt das -- Inflation begünstigt Schuldner. Falsch war, dass
    ein in heutigen Preisen gedachtes Ziel als feste nominale Zahl stehen
    blieb: 831.000 kaufen bei 3 % Inflation weniger als bei 2 %. Das Ziel wird
    deshalb mit der Inflationsdifferenz skaliert, und dann faellt der Vergleich
    wieder richtig herum aus.
    """
    scenario = ann.inflation_pa(assumptions)
    if declared_inflation <= -1:
        return declared_cents
    factor = ((1.0 + scenario) / (1.0 + declared_inflation)) ** years
    return int(round(declared_cents * factor))


def _objektposten(prognosen, year: int, base_year: int, after_month: int,
                  inflation: float, verkauf: Mapping[str, date] | None = None) -> list[Posten]:
    """Je Objekt mit Prognose ein Posten, samt Rechenweg.

    Eine eigene Quelle statt des gemessenen Basisjahrs: dort steht genau ein
    Mietmonat, und ueber acht vollstaendige Monate gemittelt waere das ein
    Bruchteil des Ertrags. Diese Verwaesserung zwanzig Jahre fortzuschreiben
    waere der groesste stille Fehler im ganzen Modell gewesen.

    Die Summe der Monate, die zaehlen, aus `objektposten.netto` -- derselben Rechnung, mit
    der das Monatsmodell das Objekt je Monat bucht. Endet die Vermietung zu einem festen
    Datum (ein Leasehold) oder wird das Objekt verkauft (`verkauf`: Monat je Objekt), ist
    danach null -- kein Restwert, keine Einnahme. Mit der Inflation fortgeschrieben wie
    die uebrigen laufenden Posten: beide in heutigen Euro einzufrieren waere eine
    stillere Annahme als sie mitlaufen zu lassen.
    """
    aus = []
    for p in prognosen:
        ab = (verkauf or {}).get(p.id)
        cents = sum(_ob.netto(p, date(year, m, 1), base_year, inflation, ab)
                    for m in range(after_month + 1, 13))
        if not cents:
            continue
        aus.append(Posten(
            label=f"{p.name} netto", cents=cents, quelle="annahme",
            verweis=p.id,
            herleitung=(f"{eur(p.netto_cents)} je Monat "
                        f"(Miete {eur(p.miete_cents)} − Kosten {eur(p.kosten_cents)})"
                        f" × {faktor((1 + inflation) ** (year - base_year))} Inflation"
                        + (", die Miete nach der Saison des Objekts" if _ob.hat_saison(p)
                           else "")
                        + (f", bis {monat(p.bis)}" if p.bis else "")
                        + (f", bis zum Verkauf {monat(ab)}" if ab else ""))))
    return aus


@dataclass(frozen=True, slots=True)
class Annahmen:
    """Die Saetze, mit denen gerechnet wird -- einmal gelesen.

    `ann.inflate` und `ann.salary_*` lesen die Datei bei jedem
    Aufruf. In der Jahresschleife waren das hunderte Lesevorgaenge; als Wert
    liest sie `eingaben` ein einziges Mal, und `rechnen` muss die Datei nicht
    kennen.
    """

    inflation: float
    rendite_tagesgeld: float
    rendite_depot: float
    vorab_satz: float
    steuer_quote: float
    gehalt_steigerung: float
    #: Die Gehaltsuntergrenze aus den Annahmen: das Gehalt, mit dem beide Modelle rechnen.
    #: None, wenn dort keine steht (die Rechnung bricht dann ab).
    gehalt_untergrenze_cents: int | None
    rentenabzug: float
    #: Der Sparerpauschbetrag in Cent je Jahr: nominal fest, kein Wachstum.
    pauschbetrag: int
    #: Bis zu welchem Alter gerechnet wird, und wie viel des Kapitals dahin
    #: aufgebraucht werden darf. Die Hochrechnung braucht beides nicht; die
    #: Rentenluecke liest sie hier, statt die Datei selbst zu oeffnen.
    lebenserwartung: int
    aufbrauchen: float


@dataclass(frozen=True, slots=True)
class Monat:
    """Was am Stichtag haengt: Bestand, Zeit und Fenster, zusammen.

    EINE Gruppe, weil sie sich nur zusammen verschiebt. Ein Monat weiter heisst:
    das Geld liegt jetzt auf dem Konto (Bestand), ein Monat ist vergangen
    (Basisjahr, vergangene Monate) und das Fenster ist um einen Monat gerueckt
    (Mitte). Einzeln getauscht zeigte die Zeit ein grosses Minus, der Bestand
    ein grosses Plus, und beide hoben sich fast auf.
    """

    base_year: int
    #: Die Monate des Basisjahrs, die schon gebucht sind. Sie stecken im
    #: Bestand und werden nicht noch einmal projiziert.
    vergangen: int
    fenster: ag.Fenster | None
    tagesgeld: int
    depot: int
    policen: int
    #: Was im Depot als eingezahlt gilt; nur der Rest wird beim Verkauf versteuert.
    einstand: int
    policen_je_konto: Mapping[str, int]
    #: Die Konten im Topf Tagesgeld mit ihrem Stand: daraus mischt sich der
    #: Zinssatz des Topfs (`zinsen.mischung`).
    tagesgeld_je_konto: Mapping[str, _zn.Konto]


@dataclass(frozen=True, slots=True)
class Vertrag:
    """Ein Vertrag, den die Jahresrechnung ueber seine Tatsachen zaehlt, wie das
    Monatsmodell (`forecast.vertraege`): Betrag, Takt, Vorrat, Kuendigung, Pausen, offene
    Rueckzahlungen der Mitzahler. Seine Buchungen messen beide nicht."""

    abo: dict
    #: Der Block seiner Kategorie, immer einer aus `FROM_BASE`.
    block: str
    #: Die Monate, in denen eine Wegfall-Zeile ihn aussetzt.
    pausen: _vt.Pausen = ()
    #: Was die Mitzahler noch schulden: (Monat, Betrag).
    rueckzahlungen: tuple[tuple[date, int], ...] = ()


@dataclass(frozen=True, slots=True)
class Planzeilen:
    """Was die Planzeilen und Vertraege aus dem Hauptbuch messen.

    Die Zeilen selbst (`Eingaben.szenarien`) gelten fuer beide Stichtage, wie
    sie heute stehen. Gemessen werden sie je Stichtag neu: eine Wegfall-Zeile
    kuerzt um das, was die Reihe im Fenster gekostet hat.
    """

    #: Je Planzeile (Klammer, Nummer) ihre Messung.
    messungen: Mapping[tuple[str, int], dict]
    #: Gekuendigte Vertraege, gemessen im Fenster.
    enden: tuple[dict, ...]
    verkaeufe: tuple[Verkauf, ...]
    #: Die Ausgabe je Vertrag, der eine Police speist (`_beitragsausgaben`).
    beitraege: tuple[dict, ...] = ()
    #: Die Wegfall-Zeilen (Klammer, Nummer) ueber den Beitrag in eine Police: sie ziehen
    #: ihn nominal ab (`_beitragsposten`).
    nominal: frozenset[tuple[str, int]] = frozenset()
    #: Die Vertraege, die ueber ihre Tatsachen zaehlen (`Vertrag`), statt gemessen.
    vertraege: tuple[Vertrag, ...] = ()
    #: Der Block jeder erwarteten Einnahme (Klammer, Nummer): der ihrer Kategorie.
    erwartet_block: Mapping[tuple[str, int], str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Eingaben:
    """Alles, was die Hochrechnung aus Hauptbuch und Dateien braucht.

    GELESEN wird in `eingaben`, GERECHNET in `rechnen`. Die Rechnung kennt
    weder die Datenbank noch `config/`; wer sie mehrfach laufen laesst
    (Jüngst neben Schnitt, die Wirkung gegenueber dem Monat davor), liest die
    Eingaben einmal und tauscht, was sich unterscheidet.

    Die Felder sind nach dem gruppiert, was sich als Ganzes tauschen laesst:

    * `monat`      Bestand, vergangene Monate, Basisjahr und Fenster
    * `base`       je Block und Kategorie der gemessene Jahreswert; ein Block
                   laesst sich einzeln tauschen, samt `base_monate` und
                   `base_reihen`
    * `planzeilen` Messungen der Planzeilen, Vertragsenden, Verkaeufe

    Alles darunter gilt in jeder Rechnung gleich: die Annahmen samt den
    Zinssaetzen, die Planzeilen selbst, Tilgungsplaene, Renten, Objekte und das
    Tagesgeld-Ziel. Das sind keine Daten aus dem Hauptbuch, sondern
    Entscheidungen, wie sie heute stehen.

    `frozen` schuetzt die Felder, nicht ihren Inhalt: Mappings und Listen
    darin liest `rechnen` nur.
    """

    monat: Monat
    base: Mapping[str, Mapping[str, int]]
    planzeilen: Planzeilen

    annahmen: Annahmen
    #: Je Konto die datierten Zinssaetze aus `zinssaetze_custom.yaml`.
    zinssaetze: Mapping[str, tuple[_zn.Zinssatz, ...]]
    #: Das Tagesgeld-Ziel; None heisst: alles bleibt auf dem Tagesgeld.
    grenze: int | None
    depotkonten: frozenset[str]
    #: Die Klammern mit ihren Zeilen, wie sie heute stehen.
    szenarien: tuple
    teilzeit: tuple
    #: Die wirksamen Kredite mit Tilgungsplan.
    tilgungsplaene: tuple
    rentenquellen: tuple
    #: Ab wann jede Rentenquelle zahlt (Kennung -> Datum). Eine Quelle ohne
    #: eigenes Datum zahlt ab dem Rentenbeginn der Einrichtung.
    rentenbeginne: Mapping[str, date | None]
    rentenbeginn: date | None
    #: Das Geburtsdatum der planenden Person; mit `rentenbeginn` und der
    #: Lebenserwartung rechnet die Rentenluecke.
    geburtsdatum: date | None
    objektprognosen: tuple
    #: Je Block und Kategorie, ueber wie viele der letzten Monate des Fensters
    #: `base` gemessen ist, wo das weniger als das ganze Fenster sind (Jüngst).
    #: Gehoert zu `base`: wer einen Block von `base` tauscht, tauscht diesen
    #: mit.
    base_monate: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    #: Je Block und Kategorie, woraus `base` besteht: ihre Reihen mit festem Takt
    #: und der Rest. Gehoert zu `base` und wird mit ihr getauscht: Die Reihen sind
    #: Teil der Messung, keine eigene Ursache.
    base_reihen: Mapping[str, Mapping[str, _fs.Zerlegung]] = field(default_factory=dict)
    #: Je Position (Kennung des Kontos) die Police aus den Rentenquellen: ihre
    #: Kosten, ihr Beitrag vom Vertrag, ihre Auszahlung. Eine Position ohne
    #: Quelle fehlt hier; ihr Teil des Topfs waechst mit dem Depotsatz.
    policen: Mapping[str, _pol.Police] = field(default_factory=dict)


def eingaben(conn: sqlite3.Connection, *, base_year: int | None = None,
             opening_cents: int = 0,
             assumptions: Path | str = ann.PATH,
             szenarien: Path | str | None = None,
             toepfe: dict[str, int] | None = None,
             puffer_cents: int | None = None,
             policen_je_konto: dict[str, int] | None = None,
             tagesgeld_je_konto: Mapping[str, _zn.Konto] | None = None,
             depot_gewinn_cents: int = 0,
             tempo: Tempo = "schnitt",
             bis: date | None = None) -> Eingaben:
    """Liest, was `rechnen` braucht. Die Bedeutung der Argumente: siehe `project`.

    `tempo` waehlt, wie die Basis gemessen wird: "schnitt" ueber das ganze
    Fenster, "juengst" fuer den Konsum ueber die letzten drei Monate.

    `bis` liest alles, was aus dem Hauptbuch kommt, nur bis zum Monatsende von
    `bis`, als waere heute der erste Tag danach: das Fenster, den letzten
    vollstaendigen Monat, die Messungen der Planzeilen, die
    Vertragsenden und die Verkaeufe. Das Basisjahr ist das Jahr dieses Tages,
    wenn keines angegeben ist. Alles andere -- Annahmen, Planzeilen, Kredite,
    Renten, Objekte -- und die Staende, die der Aufrufer hereinreicht
    (`bestaende.zum`), bleiben, wie sie sind. Ohne `bis`: wie heute.
    """
    return _eingaben(conn, (tempo,), base_year=base_year, opening_cents=opening_cents,
                     assumptions=assumptions, szenarien=szenarien, toepfe=toepfe,
                     puffer_cents=puffer_cents, policen_je_konto=policen_je_konto,
                     tagesgeld_je_konto=tagesgeld_je_konto,
                     depot_gewinn_cents=depot_gewinn_cents, bis=bis)[tempo]


def eingaben_je_tempo(conn: sqlite3.Connection, *, base_year: int | None = None,
                      opening_cents: int = 0,
                      assumptions: Path | str = ann.PATH,
                      szenarien: Path | str | None = None,
                      toepfe: dict[str, int] | None = None,
                      puffer_cents: int | None = None,
                      policen_je_konto: dict[str, int] | None = None,
                      tagesgeld_je_konto: Mapping[str, _zn.Konto] | None = None,
                      depot_gewinn_cents: int = 0,
                      bis: date | None = None) -> dict[Tempo, Eingaben]:
    """Die Eingaben beider Tempi, einmal gelesen.

    Sie unterscheiden sich nur in der Basis (`base`, `base_monate`), und die
    teilen sich eine Messung. Jedes weitere Lesen kostete ein Vielfaches einer
    Rechnung (`rechnen`); wer beide Tempi zeigt, ruft diese Funktion statt
    `eingaben` zweimal.
    """
    return _eingaben(conn, TEMPI, base_year=base_year, opening_cents=opening_cents,
                     assumptions=assumptions, szenarien=szenarien, toepfe=toepfe,
                     puffer_cents=puffer_cents, policen_je_konto=policen_je_konto,
                     tagesgeld_je_konto=tagesgeld_je_konto,
                     depot_gewinn_cents=depot_gewinn_cents, bis=bis)


def _eingaben(conn: sqlite3.Connection, tempi: tuple[Tempo, ...], *,
              base_year: int | None, opening_cents: int,
              assumptions: Path | str, szenarien: Path | str | None,
              toepfe: dict[str, int] | None, puffer_cents: int | None,
              policen_je_konto: dict[str, int] | None,
              tagesgeld_je_konto: Mapping[str, _zn.Konto] | None,
              depot_gewinn_cents: int, bis: date | None = None) -> dict[Tempo, Eingaben]:
    if toepfe is None:
        toepfe = {"tagesgeld": opening_cents}
    tg, dp, po = (int(toepfe.get(k, 0)) for k in ("tagesgeld", "depot", "policen"))
    # Einstand ist, was heute im Depot steht, abzueglich des Gewinns, den der
    # Monatsabschluss nennt ("davon Gewinn"). Ohne Angabe gilt der ganze Wert
    # als Einstand: dann wird nur versteuert, was ab heute dazukommt.
    einstand = max(dp - int(depot_gewinn_cents or 0), 0)
    # Gemessen wird ueber die letzten zwoelf vollstaendigen Monate, projiziert
    # ab heute. Einmalige Planpositionen, die schon gebucht sind, gehoeren
    # nicht in die Basis -- sonst kaeme die Anzahlung jedes Jahr wieder.
    # Welche Konten ein Depot sind. Dieselbe Sprache wie die Toepfe der
    # Bestaende (ziele.TOPF): `depot` ist eines, `broker` NICHT -- von
    # einem Verrechnungskonto wird laufend bezahlt, das waere ein stiller Umweg.
    depotkonten = frozenset(r[0] for r in conn.execute(
        "SELECT id FROM accounts WHERE active = 1 AND account_type = 'depot'"))
    f = ag.fenster(conn, bis=bis)
    geladen = _szenarien_laden(szenarien)
    ende = ag.letzter_vollstaendiger_monat(conn, bis)
    police = _vt.police_vertraege()
    erster = ag.folgetag(ende) if ende else date(base_year or date.today().year, 1, 1)
    vertraege, vertrags_hashes = _vertraege_lesen(conn, geladen, police, erster)
    # Was ein Vertrag ersetzt, misst die Rechnung nicht: weder seine Reihe noch die
    # Zahlungen seiner Mitzahler.
    ohne = (_sz.einmalig_zugeordnet(geladen) | _sz.erwartet_zugeordnet(conn, geladen)
            | vertrags_hashes)
    # Eine Messung fuer alle Tempi: sie unterscheiden sich nur darin, wie aus
    # den Monatssummen ein Jahreswert wird.
    # Die Reihen einmal je Stichtag: Messung, Planzeilen und Vertragsenden rechnen
    # mit denselben.
    reihen = _reihen_laden(conn, f, ohne)
    gemessen = (_fs.messen(conn, _hochrechnung(f, ohne, tempi[0], reihen))
                if f else None)
    basen = {t: _basis(conn, f, ohne, tempo=t, gemessen=gemessen, reihen=reihen)
             for t in tempi}
    messungen = {(s.id, i): _sz.messung(conn, line, f, reihen, vertrags_hashes)
                 for s in geladen for i, line in enumerate(s.lines)}
    inflation = ann.inflation_pa(assumptions)
    # Vom Basisjahr sind Monate bereits vergangen, und sie stecken schon im
    # Anfangsbestand. Nur was im LAUFENDEN Jahr schon gebucht ist, zaehlt als
    # vergangen. Liegt die Messung in einem frueheren Jahr, ist vom laufenden
    # noch nichts abgedeckt und es zaehlt voll.
    heute = ag.folgetag(bis) if bis is not None else None
    base_year = base_year or (heute or date.today()).year
    try:
        untergrenze = ann.salary_floor_cents(assumptions)
    except KeyError:
        untergrenze = None
    quellen = tuple(_renten.quellen())
    # Die zwei Dateien der Person einmal: Rentenbeginn und Geburtsdatum
    # kommen aus denselben Angaben.
    person = _person.angaben()
    rentenbeginn = _person.rentenbeginn_aus(person)
    rentenbeginne = {q.id: _renten.beginn(q, rentenbeginn) for q in quellen}
    policen = _policen_lesen(conn, quellen, rentenbeginne, geladen)
    vorab_satz, steuer_quote = ann.vorabpauschale(assumptions)
    erste, erste_monate, erste_reihen = basen[tempi[0]]
    e = Eingaben(
        monat=Monat(
            base_year=base_year,
            vergangen=ende.month if ende and ende.year == base_year else 0,
            fenster=f, tagesgeld=tg, depot=dp, policen=po, einstand=einstand,
            policen_je_konto=dict(policen_je_konto or {}),
            tagesgeld_je_konto=dict(tagesgeld_je_konto or {})),
        base=erste, base_monate=erste_monate, base_reihen=erste_reihen,
        planzeilen=Planzeilen(
            messungen=messungen,
            # Aus der Basis nimmt es nur, in welchem Block eine Kategorie steht,
            # und das ist in jedem Tempo gleich.
            # Ein Vertrag, der ueber seine Tatsachen zaehlt, endet mit ihnen: nur die Vertraege,
            # die gemessen bleiben (Policen), brauchen den Abzug.
            enden=tuple(_vertragsenden(conn, f, geladen, erste, reihen, policen, police)),
            verkaeufe=tuple(verkaeufe(conn, base_year, szenarien, bis=bis)),
            beitraege=tuple(_beitragsausgaben(conn, f, erste, reihen, policen)),
            nominal=_beitrags_wegfaelle(conn, quellen, geladen),
            vertraege=vertraege,
            erwartet_block={(s.id, i): ag.block_der_kategorie(conn, line.category_id) or ""
                            for s in _sz.active(geladen) for i, line in enumerate(s.lines)
                            if line.kind == "erwartet" and line.category_id}),
        annahmen=Annahmen(
            inflation=inflation,
            rendite_tagesgeld=ann.rendite_nominal_pa(assumptions),
            rendite_depot=ann.rendite_depot_pa(assumptions),
            vorab_satz=vorab_satz, steuer_quote=steuer_quote,
            gehalt_steigerung=ann.salary_growth_pa(assumptions),
            gehalt_untergrenze_cents=untergrenze,
            rentenabzug=ann.abzug_renten(assumptions),
            pauschbetrag=ann.sparerpauschbetrag_cents(assumptions),
            lebenserwartung=ann.lebenserwartung(assumptions),
            aufbrauchen=ann.aufbrauchen(assumptions)),
        zinssaetze=_zs.lesen(),
        grenze=max(int(puffer_cents), 0) if puffer_cents is not None else None,
        depotkonten=depotkonten,
        szenarien=tuple(geladen),
        teilzeit=tuple(_sz.teilzeitzeilen(geladen)),
        # Ein geplanter Kredit zaehlt nur, solange seine Klammer an ist. Dieselbe
        # Klammer traegt die Anzahlung und den Wegfall der Miete, also bewegt EIN
        # Schalter die ganze Entscheidung statt dreier Stellen in zwei Dateien.
        tilgungsplaene=tuple(_tilgungsplaene(_sz.aktive_ids(szenarien))),
        rentenquellen=quellen,
        rentenbeginne=rentenbeginne,
        rentenbeginn=rentenbeginn,
        geburtsdatum=person["geburtsdatum"],
        # Ein Szenario ist eine andere Annahmedatei; was es je Objekt anders
        # annimmt, steht dort unter immobilien.objekte.
        objektprognosen=tuple(_objekte.prognosen(
            None if str(assumptions) == str(ann.PATH) else assumptions)))
    return {t: replace(e, base=basis, base_monate=letzte, base_reihen=zerlegt,
                       policen=policen)
            for t, (basis, letzte, zerlegt) in basen.items()}


def _wegfall_zeilen(conn: sqlite3.Connection, geladen: list, vertraege: Mapping,
                    ) -> list[tuple[tuple[str, int], _sz.Line, set[str]]]:
    """Die eingeschalteten Wegfall-Zeilen der Jahresrechnung mit ihren Buchungen der Reihe,
    wenn es Vertraege gibt, die eine Police speisen."""
    from finctl.ledger import reihe as _reihe

    return [((s.id, i), line, set(_reihe.hashes(conn, line.buchungen)))
            for s in _sz.active(geladen) for i, line in enumerate(s.lines)
            if vertraege and line.kind == "wegfall" and line.start
            and line.frequency != "einmalig" and not line.nur_kontoprognose
            and zaehlt_in_prognose(line)]


def _beitrags_wegfaelle(conn: sqlite3.Connection, quellen: tuple, geladen: list,
                        ) -> frozenset[tuple[str, int]]:
    """Die Wegfall-Zeilen, die den Beitrag in eine Police abziehen: (Klammer, Nummer)."""
    from finctl import abos as _ab
    from finctl.ledger import reihe as _reihe

    vertraege = ({a["id"]: a for a in _ab.alle_vertraege()}
                 if any(q.beitrag for q in quellen) else {})
    treffer: set[str] = set()
    for q in quellen:
        a = vertraege.get(q.beitrag or "")
        if q.konto and a is not None:
            treffer |= set(_reihe.hashes(conn, a["buchungen"], a["betrag_cents"]))
    return frozenset(schluessel for schluessel, _, hashes
                     in _wegfall_zeilen(conn, geladen, vertraege) if hashes & treffer)


def _policen_lesen(conn: sqlite3.Connection, quellen: tuple, beginne: Mapping[str, date | None],
                   geladen: list) -> dict[str, _pol.Police]:
    """Je Rentenquelle mit Position eine Police -- samt dem Beitrag ihres Vertrags.

    Betrag, Takt, Termin und Kuendigung stehen am Vertrag (`beitrag` der Quelle)
    und werden nicht ein zweites Mal getippt. Zahlt der Haushalt ihn nicht mehr,
    weil eine eingeschaltete Wegfall-Zeile ihn abzieht (Beitragsfreistellung),
    fliesst er auch nicht mehr in die Police: Zeile und Vertrag teilen Buchungen.
    """
    from finctl import abos as _ab
    from finctl.ledger import reihe as _reihe

    vertraege = ({a["id"]: a for a in _ab.alle_vertraege()}
                 if any(q.beitrag for q in quellen) else {})
    wegfaelle = [(line, hashes) for _, line, hashes in _wegfall_zeilen(conn, geladen, vertraege)]
    out = {}
    for q in quellen:
        if not q.konto:
            continue
        a = vertraege.get(q.beitrag or "")
        beitrag = None
        if a is not None:
            treffer = set(_reihe.hashes(conn, a["buchungen"], a["betrag_cents"]))
            pausen = tuple((line.start, line.end) for line, hashes in wegfaelle
                           if hashes & treffer)
            beitrag = _pol.Beitrag(
                vertrag=a["id"], name=a["name"], cents=-a["betrag_cents"], takt=a["takt"],
                termin=a["faellig"], ende=a["gekuendigt_zum"], pausen=pausen)
        out[q.konto] = _pol.Police(
            konto=q.konto, quelle=q.id, name=q.name, kosten_pa=q.kosten_pa or 0.0,
            kosten_bekannt=q.kosten_pa is not None, beginn=beginne.get(q.id),
            beitrag=beitrag, pruefwert=q.pruefwert if q.art == "kapital" else None)
    return out


def _jahresposten_gemessen(e: Eingaben, year: int, share: float, anteil_text: str,
                           nach: int, seit: float) -> dict[str, list[Posten]]:
    """Die laufenden Bloecke aus der Basis, samt den Abzuegen gekuendigter Vertraege."""
    f, a = e.monat.fenster, e.annahmen
    fenster_text = f"{monat(f.von)}–{monat(f.bis)}" if f else "ohne Messung"
    fakt = (1.0 + a.inflation) ** seit
    # Was gekuendigt ist, kuerzt den Block, in dem es gemessen wurde.
    gekuendigt = _vertragsende_posten(e.planzeilen.enden, year, nach, seit,
                                      a.inflation)
    nominal = _beitragsposten(e.planzeilen.beitraege, share, fakt, anteil_text)
    vertrag = _vertragsposten(e.planzeilen.vertraege, year, nach, f.mitte if f else None,
                              a.inflation)
    posten: dict[str, list[Posten]] = {}
    for block_id in FROM_BASE:
        liste = posten.setdefault(block_id, [])
        liste.extend(gekuendigt.get(block_id, ()))
        liste.extend(nominal.get(block_id, ()))
        liste.extend(vertrag.get(block_id, ()))
        for kategorie, jahr_cents in sorted(e.base.get(block_id, {}).items()):
            grown = ann.grow(jahr_cents, seit, a.inflation)
            # Auch ein Posten mit null bekommt seine Zeile: im Tempo der letzten
            # Monate ist gerade die Null die Nachricht ("zuletzt nichts gebucht"),
            # und beide Tempi zeigen dieselbe Menge Posten.
            cents = round(grown * share)
            letzte = e.base_monate.get(block_id, {}).get(kategorie)
            if letzte:
                zeitraum = _letzte_monate_text(f, letzte)
                hoch = f" (aus {_monate_aufs_jahr(letzte)} aufs Jahr)"
            else:
                zeitraum = fenster_text
                hoch = (f" (aus {f.monate} Monaten aufs Jahr)"
                        if f and f.monate != 12 else "")
            zerlegt = e.base_reihen.get(block_id, {}).get(kategorie)
            gemessen = (_reihen_herleitung(zerlegt, jahr_cents, f"gemessen {zeitraum}{hoch}")
                        if zerlegt and zerlegt.reihen
                        else f"{eur(jahr_cents)} gemessen {zeitraum}{hoch}")
            liste.append(Posten(
                label=kategorie or "(ohne Kategorie)", cents=cents,
                quelle="gemessen", verweis=kategorie or None,
                herleitung=f"{gemessen} × {faktor(fakt)} Inflation{anteil_text}"))
    return posten


def _reihen_herleitung(zerlegt: _fs.Zerlegung, jahr_cents: int, rest_text: str) -> str:
    """Der Rechenweg einer Kategorie mit Reihen: jede Reihe mit Gegenpartei, Takt und
    Betrag je Termin, dann der Rest mit seinem bisherigen Text. Die Summe ist der
    Jahreswert der Kategorie."""
    teile = [r.ergebnis.herkunft.herleitung for r in zerlegt.reihen]
    if zerlegt.rest_monate:
        teile.append(f"Rest {eur(zerlegt.rest_cents)} {rest_text}")
    return f"{eur(jahr_cents)} aus " + "; ".join(teile)


def _letzte_monate_text(f, n: int) -> str:
    """Das Fenster der letzten `n` Monate, wie der Rechenweg es nennt."""
    erster = _vf.add_months(f.bis.replace(day=1), -(n - 1))
    return monat(f.bis) if n == 1 else f"{monat(erster)}–{monat(f.bis)}"


def _monate_aufs_jahr(n: int) -> str:
    return "einem Monat" if n == 1 else f"{n} Monaten"


def _zinsmonate(year: int, nach: int) -> list[date]:
    """Die Monate, deren Saetze der Topf in diesem Jahr mittelt: die noch
    kommenden, im Basisjahr also die Restmonate. Sind keine mehr uebrig, alle."""
    return [date(year, mm, 1) for mm in range(nach + 1, 13)] or [
        date(year, mm, 1) for mm in range(1, 13)]


def _mischung_text(mix: _zn.Mischung) -> str:
    """Woraus der Satz des Topfs besteht -- und dass er auch fuer Neues gilt."""
    if not mix.teile:
        return " (langfristiger Satz: im Topf liegt heute nichts)"
    teile = ", ".join(
        f"{konto} {prozent(satz)} auf "
        f"{f'{round(anteil * 100)} %' if anteil >= 0.005 else 'unter 1 %'}"
        for konto, anteil, satz in mix.teile)
    return f" ({teile}; was dazukommt, verzinst sich mit derselben Mischung)"


def _renditeposten(k: dict, stand: tuple[int, int, int], a: Annahmen,
                   mix: _zn.Mischung, anteil_text: str, abfluss: int,
                   policen: list[Posten]) -> list[Posten]:
    """Die Rendite des Jahres je Topf und die Steuern darauf, samt Rechenweg.

    Ihre Summe ist die Rendite des Jahres: `k["rendite"]` und, was die Policen
    bis zu ihrer Auszahlung verdienten (`policen`, je Police ein Posten). Eine
    Steuer, die der Sparerpauschbetrag ganz deckt, bleibt als Zeile mit null
    stehen: sonst saehe man ihn nicht wirken.
    """
    tg, dp, _po = stand
    frei = k["pauschbetrag"]
    anteilig = " (anteilig, Restmonate)" if anteil_text else ""

    def verbraucht(was: str) -> str:
        return (f"; Sparerpauschbetrag {eur(frei[was])} verbraucht{anteilig}"
                if frei[was] else "")

    abzug = (f" − {eur(abfluss)} Einmalzahlungen, anteilig nach Monaten ohne das Geld"
             if abfluss else "")
    zeilen = [
        Posten(label="Tagesgeld", cents=k["zins_tagesgeld"], quelle="rendite",
               verweis="tagesgeld",
               herleitung=(f"({eur(max(tg, 0))}{anteil_text}{abzug}) "
                           f"= {eur(k['basis_tagesgeld'])} × {prozent(mix.satz)}"
                           f"{_mischung_text(mix)}")),
        Posten(label="Depot", cents=k["gewinn_depot"], quelle="rendite",
               verweis="depot",
               herleitung=f"{eur(dp)} × {prozent(a.rendite_depot)}{anteil_text}"),
    ]
    steuern = [
        Posten(label="Kapitalertragsteuer auf Zinsen", cents=-k["zinssteuer"],
               quelle="regel", verweis="tagesgeld",
               herleitung=(f"{eur(k['zins_tagesgeld'])} Zinsen × "
                           f"{prozent(a.steuer_quote)} Steuer{verbraucht('zinsen')}")),
        Posten(label="Vorabpauschale", cents=-k["steuer"], quelle="regel",
               verweis="depot",
               herleitung=(f"{eur(dp)} × "
                           f"{prozent(min(a.vorab_satz, max(a.rendite_depot, 0.0)))}"
                           f"{anteil_text} × {prozent(a.steuer_quote)} Steuer"
                           f", ohne Teilfreistellung{verbraucht('vorab')}")),
        Posten(label="Steuer auf Depotverkauf", cents=-k["verkaufsteuer"],
               quelle="regel", verweis="depot",
               herleitung=(f"{eur(k['verkauf'])} verkauft, davon Gewinnanteil laut "
                           f"Einstand × {prozent(a.steuer_quote)}, ohne Teilfreistellung"
                           f"{verbraucht('verkauf')}")),
    ]
    steuern = [p for p, was in zip(steuern, ("zinsen", "vorab", "verkauf"), strict=True)
               if p.cents or frei[was]]
    return [p for p in zeilen if p.cents] + policen + steuern


def _kaskadeposten(k: dict, grenze: int | None) -> list[Posten]:
    """Was die Kaskade zwischen Tagesgeld und Depot bewegt."""
    if not k["ins_depot"]:
        return []
    return [Posten(
        label=("Tagesgeld über dem Ziel ins Depot" if k["ins_depot"] > 0
               else "Im Ruhestand aus dem Depot entnommen"),
        cents=k["ins_depot"], quelle="regel", verweis="tagesgeld-puffer",
        herleitung=(f"Tagesgeld nach Sparrate und Zinsen {eur(k['tagesgeld_vor_kaskade'])}, "
                    f"Grenze {eur(grenze or 0)}"))]


def rechnen(e: Eingaben, *, end_year: int = 2045,
            target_cents: int = 0) -> Projection:
    """Jahr fuer Jahr bis zum Stichtag, aus fertig gelesenen Eingaben.

    Fasst weder die Datenbank noch `config/` an (`tests/test_jahre.py` haelt das
    fest): Wer die Rechnung mehrfach braucht, soll sie nicht mehrfach lesen.
    """
    m, a = e.monat, e.annahmen
    f, base_year = m.fenster, m.base_year
    tg, dp, po, einstand = m.tagesgeld, m.depot, m.policen, m.einstand
    grenze = e.grenze
    elapsed = m.vergangen
    remaining = max(0, 12 - elapsed)
    verkauft = e.planzeilen.verkaeufe
    kredit_endet = {v.loan_id: v.ab for v in verkauft if v.loan_id}
    rente_ab = e.rentenbeginn

    def beginn_von(q) -> date | None:
        return e.rentenbeginne[q.id]

    anteile = dict(m.policen_je_konto)
    start = rechenbeginn(m)
    fenster_text = (f"{monat(f.von)}–{monat(f.bis)}" if f else "ohne Messung")

    def seit_messung(year: int) -> float:
        # Die Messung ist im Mittel ein halbes Jahr alt. Fortgeschrieben wird
        # von der Mitte des Fensters zur Mitte des Jahres; ab heute gerechnet
        # laege jede laufende Position rund ein Prozent zu niedrig.
        return (wachstum.seit_messung(f.mitte, wachstum.jahresmitte(year)) if f
                else float(year - base_year))

    # Vom Basisjahr sind Monate bereits vergangen, und sie stecken schon im
    # Anfangsbestand. Sie ein zweites Mal zu projizieren zaehlt sie doppelt --
    # bei acht von zwoelf Monaten ist das kein Rundungsfehler, sondern zwei
    # Drittel eines Jahres. Das Basisjahr laeuft deshalb nur ueber seine
    # RESTmonate, jedes weitere voll.
    out = Projection(base_year=base_year, target_cents=target_cents)
    for year in range(base_year, end_year + 1):
        share = (remaining / 12) if year == base_year else 1.0
        anteil_text = f" × {remaining}/12 Restmonate" if share < 1 else ""
        nach = elapsed if year == base_year else 0
        fakt = (1.0 + a.inflation) ** seit_messung(year)
        posten = _jahresposten_gemessen(e, year, share, anteil_text, nach,
                                        seit_messung(year))

        posten["gehalt"] = _gehaltsposten(
            year, base_year, nach, share, a, rente_ab) + _teilzeitposten(
                e.teilzeit, year, nach, _salary(year, base_year, a),
                rente_ab)
        pj = _policenjahr(e, year, nach, share, anteile, po, start, beginn_von, anteil_text)
        posten["policen"], posten["policen_beitrag"] = pj.umgeschichtet, pj.beitraege
        posten[RENTE] = _rentenposten(e.rentenquellen, year, nach, a.inflation,
                                      a.rentenabzug, beginn_von, e.teilzeit,
                                      rente_ab) + pj.verrentet

        # Kredite und datierte Posten tragen ihr eigenes Datum, sie brauchen
        # keinen Anteil -- aber im Basisjahr zaehlen nur die Monate, die noch
        # kommen, denn die frueheren stehen schon im Ledger.
        posten["kredit"] = _kreditposten(e.tilgungsplaene, year, nach, kredit_endet)
        (posten[ag.EINMALIG], abfluss,
         posten["depotentnahme"]) = _planposten(e.szenarien, e.planzeilen.messungen,
                                                year, nach, e.depotkonten, fakt,
                                                e.planzeilen.nominal)

        for block_id, liste in _erwartete_posten(
                e.szenarien, e.planzeilen.erwartet_block, year, nach).items():
            posten[block_id].extend(liste)

        mit_prognose = {p.id for p in e.objektprognosen}
        posten[ag.OBJEKT] = _objektposten(
            e.objektprognosen, year, base_year, nach, a.inflation,
            {v.property_id: v.ab for v in verkauft})

        # Ein verkauftes Objekt hoert auf, Miete zu bringen und Kosten zu
        # machen, und sein Erloes kommt einmal. Die Rate verschwindet schon in
        # _kreditposten. Alle drei gehoeren zusammen: nur die Rate zu
        # streichen liesse den Verkauf wie einen Gewinn aussehen, nur die
        # Miete zu streichen wie einen Verlust. Ein Objekt mit Prognose steht nicht
        # in `miete` und `immobilie`, seine Posten enden mit dem Verkauf
        # (`_objektposten`): Dort ist nichts abzuziehen.
        for v in verkauft:
            weg = _monate_ohne(v, year, nach)
            if weg and v.property_id not in mit_prognose:
                for block_id, jahr_cents, was in (
                        ("miete", v.miete_jahr_cents, "Miete"),
                        ("immobilie", v.kosten_jahr_cents, "Kosten")):
                    cents = -round(ann.grow(jahr_cents, seit_messung(year),
                                            a.inflation) * weg / 12)
                    if cents:
                        posten[block_id].append(Posten(
                            label=f"Verkauf {v.name}: {was} entfällt", cents=cents,
                            quelle="plan", verweis=v.property_id,
                            herleitung=(f"{eur(jahr_cents)} gemessen {fenster_text}"
                                        f" × {faktor(fakt)} Inflation × {weg}/12"
                                        f", verkauft ab {monat(v.ab)}")))
            if year == v.ab.year and v.ab.month > nach:
                posten[ag.EINMALIG].append(Posten(
                    label=f"Verkauf {v.name}: Nettoerlös", cents=v.netto_cents,
                    quelle="plan", einmalig=True,
                    verweis=(f"{v.klammer_id}" if v.klammer_id else v.property_id),
                    herleitung=(f"Preis {eur(v.erloes_cents)}"
                                + (f" − Verkaufskosten {eur(v.verkaufskosten_cents)}"
                                   if v.verkaufskosten_cents else "")
                                + f" − Restschuld {eur(v.restschuld_cents)}"
                                + (f" (Stand {monat(v.restschuld_stand)}, "
                                   f"Tilgungsplan endet vorher)"
                                   if v.restschuld_stand else f" ({monat(v.ab)})")
                                + (f"; Klammer {v.klammer}" if v.klammer
                                   else "; Termin und Preis aus /immobilien"))))

        # Die Blocksummen AUS den Posten, nicht daneben gerechnet.
        blocks = {b: summe(posten[b]) for b in
                  (*FROM_BASE, "gehalt", "kredit", ag.EINMALIG, ag.OBJEKT, RENTE)}

        # Auszahlende Policen verlassen den Topf, bevor verzinst wird: mit ihrem Stand
        # zur Auszahlung, ihr Zins bis dahin steht in der Rendite des Jahres.
        anfang = tg + dp + po
        po -= pj.abgang
        dp += pj.zum_depot
        einstand += pj.zum_depot
        tg += pj.zum_tagesgeld
        mix = _zn.mischung(m.tagesgeld_je_konto, e.zinssaetze,
                           _zinsmonate(year, nach), a.rendite_tagesgeld)
        k = kaskade(tg, dp, po, sparrate=sum(blocks.values()),
                    depot_abfluss=summe(posten["depotentnahme"]),
                    grenze=grenze if grenze is not None else 2**62,
                    satz_tagesgeld=mix.satz, satz_depot=a.rendite_depot,
                    vorab_satz=a.vorab_satz, steuer_quote=a.steuer_quote,
                    pauschbetrag=a.pauschbetrag, anteil=share,
                    abfluss_gewichtet=abfluss,
                    entnahme=_im_ruhestand(rente_ab, year), einstand=einstand,
                    zins_policen=pj.zins, einzahlung_policen=pj.einzahlung)
        posten["rendite"] = _renditeposten(k, (tg, dp, po), a, mix, anteil_text, abfluss,
                                           pj.rendite)
        posten["kaskade"] = _kaskadeposten(k, grenze)

        out.years.append(Year(
            year=year, blocks=blocks, opening_cents=anfang,
            return_cents=k["rendite"] + pj.zins_aus, tagesgeld_cents=k["tagesgeld"],
            depot_cents=k["depot"], policen_cents=k["policen"],
            puffer_grenze_cents=grenze or 0, ins_depot_cents=k["ins_depot"],
            steuer_cents=k["steuer"], in_policen_cents=pj.einzahlung + pj.einzahlung_aus,
            abzug_cents=pj.abzug, posten=posten))
        anteile = pj.anteile
        tg, dp, po, einstand = k["tagesgeld"], k["depot"], k["policen"], k["einstand"]
    return out


def project(conn: sqlite3.Connection, *, base_year: int | None = None,
            end_year: int = 2045, opening_cents: int = 0,
            target_cents: int = 0,
            assumptions: Path | str = ann.PATH,
            szenarien: Path | str | None = None,
            toepfe: dict[str, int] | None = None,
            puffer_cents: int | None = None,
            policen_je_konto: dict[str, int] | None = None,
            tagesgeld_je_konto: Mapping[str, _zn.Konto] | None = None,
            depot_gewinn_cents: int = 0) -> Projection:
    """Jahr fuer Jahr bis zum Stichtag. Ein Szenario ist ein anderer Pfad.

    Liest mit `eingaben` und rechnet mit `rechnen`; wer dieselben Eingaben
    mehrfach braucht, ruft die beiden selbst.

    `toepfe` teilt den Anfangsbestand auf (siehe `ziele.toepfe`). Ohne sie
    liegt `opening_cents` ganz auf dem Tagesgeld.

    `policen_je_konto` teilt den Topf `policen` auf (siehe
    `ziele.policen_je_konto`): ohne ihn bleibt eine auszahlende Police im Topf.

    `tagesgeld_je_konto` teilt den Topf `tagesgeld` auf (siehe
    `ziele.tagesgeld_je_konto`): daraus mischt sich sein Zinssatz. Ohne sie
    verdient der Topf den langfristigen Satz aus den Annahmen.

    `puffer_cents` ist das Tagesgeld-Ziel, von Hand gesetzt (siehe
    `ziele.puffer_cents`). Was darueber liegt, geht ins Depot. Ohne Ziel
    bleibt alles auf dem Tagesgeld -- lieber zu wenig Rendite als eine, fuer
    die niemand eine Grenze gezogen hat.
    """
    return rechnen(
        eingaben(conn, base_year=base_year, opening_cents=opening_cents,
                 assumptions=assumptions, szenarien=szenarien, toepfe=toepfe,
                 puffer_cents=puffer_cents, policen_je_konto=policen_je_konto,
                 tagesgeld_je_konto=tagesgeld_je_konto,
                 depot_gewinn_cents=depot_gewinn_cents),
        end_year=end_year, target_cents=target_cents)
