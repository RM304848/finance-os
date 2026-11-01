"""Die Police in der Hochrechnung: mit ihrem Beitrag und nach ihren Kosten.

Eine Police waechst so, wie ihre Mitteilung es rechnet: Monat fuer Monat der
Anteil mal dem Monatssatz, dann der Beitrag dazu. Der Satz ist der Depotsatz
minus die Effektivkosten (`kosten_pa`) der Police -- der Depotsatz ist eine
Marktrendite, die Kosten von Vertrag und Fonds zusammen nimmt die Police davon.
Der Monatssatz ist der effektive: zwoelf Monate ergeben genau den Jahressatz,
wie in der Mitteilung (nachgerechnet: alle vier Spalten einer Mitteilung treffen
auf unter 0,1 Prozentpunkte).

Der Beitrag kommt vom Vertrag (`Beitrag`), nominal fest -- ohne Inflation. Er
bleibt eine Ausgabe in ihrem Block; hier kommt dasselbe Geld in der Police an.
Er fliesst, solange er als Ausgabe laeuft: bis zum Monat vor der Auszahlung, bis
zur Kuendigung am Vertrag und nicht in den Monaten einer Wegfall-Zeile
(Beitragsfreistellung). Danach waechst die Police ohne ihn weiter.

Rein: ohne Datenbank, ohne Dateien. Gelesen wird in `jahre._policen_lesen`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from finctl.forecast.verfahren import add_months
from finctl.renten import Pruefwert


def monate_von_bis(von: date, bis: date) -> int:
    """Wie viele Monatsanfaenge von `von` bis `bis` (ohne `bis`) liegen."""
    return (bis.year - von.year) * 12 + bis.month - von.month


def monatssatz(satz: float) -> float:
    """Der effektive Monatssatz zu einem Jahressatz: zwoelf Monate ergeben ihn."""
    return (1.0 + max(satz, -0.99)) ** (1 / 12) - 1


@dataclass(frozen=True, slots=True)
class Beitrag:
    """Was ein Vertrag in die Police einzahlt, wie der Vertrag es sagt."""

    vertrag: str
    name: str
    #: Je Termin, positiv. Nominal fest.
    cents: int
    #: Monate zwischen zwei Terminen (1 monatlich, 12 jaehrlich).
    takt: int
    #: Ein Termin des Vertrags (`faellig`); der Takt legt die anderen fest.
    termin: date
    #: Letzter Monat mit Beitrag laut Kuendigung am Vertrag (`gekuendigt_zum`).
    ende: date | None = None
    #: Eingeschaltete Wegfall-Zeilen ueber die Buchungen des Vertrags: ab
    #: `von` bis `bis` (offen: bis `None`) zahlt der Haushalt nicht mehr.
    pausen: tuple[tuple[date, date | None], ...] = ()

    def unterbrochen(self, tag: date) -> bool:
        """Ob der Vertrag in diesem Monat nicht mehr laeuft: gekuendigt oder frei."""
        if self.ende is not None and tag > self.ende:
            return True
        return any(von <= tag and (bis is None or tag <= bis) for von, bis in self.pausen)

    def zahlt(self, tag: date) -> bool:
        """Ob in diesem Monat (Monatserster) ein Termin des Vertrags faellt."""
        return (not self.unterbrochen(tag)
                and monate_von_bis(self.termin, tag) % self.takt == 0)

    def unterbrechung(self, von: date, bis: date) -> date | None:
        """Der letzte Monat mit Beitrag, wenn der Vertrag zwischen `von` und `bis`
        (ohne `bis`) endet oder aussetzt; sonst None."""
        for n in range(max(monate_von_bis(von, bis), 0)):
            tag = add_months(von, n)
            if self.unterbrochen(tag):
                return add_months(tag, -1)
        return None


@dataclass(frozen=True, slots=True)
class Police:
    """Eine Police der Rentenquellen: ihr Satz nach Kosten, ihr Beitrag, ihre Auszahlung."""

    konto: str
    #: Die Rentenquelle, zu der sie gehoert (`renten.Quelle.id`).
    quelle: str
    name: str
    #: Effektivkosten je Jahr; 0, wo die Mitteilung keine nennt.
    kosten_pa: float = 0.0
    kosten_bekannt: bool = False
    #: Ab wann sie auszahlt (`renten.beginn`); None: gar nicht.
    beginn: date | None = None
    beitrag: Beitrag | None = None
    #: Eine Spalte der Mitteilung (`renten.Pruefwert`), nur bei Kapital.
    pruefwert: Pruefwert | None = None

    def satz(self, depotsatz: float) -> float:
        return depotsatz - self.kosten_pa

    def zahlt_aus(self, tag: date) -> bool:
        """Ob die Police in diesem Monat (Monatserster) schon ausgezahlt ist."""
        return self.beginn is not None and tag >= self.beginn

    def beitrag_im_monat(self, tag: date) -> int:
        """Was in diesem Monat (Monatserster) in die Police fliesst."""
        if self.beitrag is None or self.zahlt_aus(tag):
            return 0
        return self.beitrag.cents if self.beitrag.zahlt(tag) else 0

    def letzter_beitragsmonat(self) -> date | None:
        """Der letzte Monat, in dem ihr Beitrag fliesst, bis zur Auszahlung."""
        if self.beginn is None:
            return None
        return add_months(self.beginn, -1) if self.beginn.day == 1 else self.beginn.replace(day=1)


@dataclass(frozen=True, slots=True)
class Fortschritt:
    """Die Policen eines Jahres, je Konto. Cent."""

    #: Stand am Jahresende; bei einer Police, die in diesem Jahr auszahlt, der
    #: Stand im Monat vor der Auszahlung.
    ende: Mapping[str, int]
    #: Der Ertrag der Monate, ohne den Beitrag.
    zins: Mapping[str, int]
    #: Was als Beitrag hineinfloss.
    beitrag: Mapping[str, int]


def fortschreiben(anteile: Mapping[str, int], policen: Mapping[str, Police],
                  depotsatz: float, year: int, nach: int) -> Fortschritt:
    """Jede Police mit Anteil durch die Monate `nach + 1` bis 12 dieses Jahres.

    Eine Police, die auszahlt, rechnet nur bis zum Monat davor: ihr Wert zur
    Auszahlung ist der Stand dann, nicht der vom Jahresanfang. Ein Konto ohne
    Police bleibt draussen; seinen Teil des Topfs verzinst die Kaskade.
    """
    ende, zins, beitrag = {}, {}, {}
    for konto, stand in anteile.items():
        police = policen.get(konto)
        if police is None:
            continue
        monat_satz = monatssatz(police.satz(depotsatz))
        wert, einzahlung = float(stand), 0
        for mm in range(nach + 1, 13):
            tag = date(year, mm, 1)
            if police.zahlt_aus(tag):
                break
            wert *= 1.0 + monat_satz
            b = police.beitrag_im_monat(tag)
            wert, einzahlung = wert + b, einzahlung + b
        ende[konto] = round(wert)
        beitrag[konto] = einzahlung
        zins[konto] = ende[konto] - stand - einzahlung
    return Fortschritt(ende=ende, zins=zins, beitrag=beitrag)


@dataclass(frozen=True, slots=True)
class Vergleich:
    """Das Modell neben der Spalte der Mitteilung (`renten.Pruefwert`)."""

    #: Der Satz nach Kosten; None, wenn der Pruefwert keinen Satz nennt.
    satz: float | None
    #: Der Wert des Modells zum Datum des Pruefwerts; None, wenn der Vergleich
    #: nicht geht.
    modell_cents: int | None
    #: Modell gegen Pruefwert, 0,05 fuer 5 % darueber.
    abweichung: float | None
    #: Der letzte Monat mit Beitrag, wenn er vor dem Datum des Pruefwerts endet:
    #: die Mitteilung setzt Beitraege bis dahin voraus.
    endet: date | None


def vergleichen(stand: int, police: Police, pruefwert: Pruefwert,
                start: date) -> Vergleich:
    """Was das Modell zum Datum des Pruefwerts ergibt, beim Satz des Pruefwerts.

    Wie die Mitteilung: der Beitrag laeuft bis dahin weiter, auch ueber die
    Auszahlung der Police hinaus -- die Spalte beantwortet, ob der Satz stimmt,
    nicht, was ausgezahlt wird. Bricht der Beitrag vorher ab (Kuendigung,
    Wegfall), sind beide nicht vergleichbar. Ohne Satz im Pruefwert gibt es keinen
    Vergleich.
    """
    if pruefwert.satz is None:
        return Vergleich(satz=None, modell_cents=None, abweichung=None, endet=None)
    satz = pruefwert.satz - police.kosten_pa
    if police.beitrag is not None:
        endet = police.beitrag.unterbrechung(start, pruefwert.zum)
        if endet is not None:
            return Vergleich(satz=satz, modell_cents=None, abweichung=None, endet=endet)
    if pruefwert.zum <= start or pruefwert.cents <= 0:
        return Vergleich(satz=satz, modell_cents=None, abweichung=None, endet=None)
    monat_satz = monatssatz(satz)
    wert = float(stand)
    for n in range(monate_von_bis(start, pruefwert.zum)):
        wert *= 1.0 + monat_satz
        if police.beitrag is not None and police.beitrag.zahlt(add_months(start, n)):
            wert += police.beitrag.cents
    modell = round(wert)
    return Vergleich(satz=satz, modell_cents=modell,
                     abweichung=modell / pruefwert.cents - 1, endet=None)
