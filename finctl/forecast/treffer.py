"""Wie gut haette die Prognose getroffen?

Nachgerechnet aus dem Ledger, ohne gespeicherte Stände: fuer jeden der
letzten vollstaendigen Monate wird die Prognose so gebaut, wie sie am Ende des
Vormonats ausgesehen haette -- mit Daten nur bis dahin --, und gegen das Ist
dieses Monats gehalten.

Zwei Pruefungen, weil es zwei Rechnungen gibt:

* JAHRESBASIS: die laufenden Bloecke so, wie die Basis der Hochrechnung sie vor
  dem Monat fortgeschrieben haette (Reihen mit Takt plus Rest, durch zwoelf),
  das Gehalt als Untergrenze, die Kreditraten aus dem Tilgungsplan. Das ist,
  womit die Jahresrechnung jedes Jahr fortschreibt.
* KONTEN: je Konto die abgeleiteten Posten mit Fenster bis zum Vormonat, dazu
  Kreditraten, Vertraege mit Termin und die Objekte mit Prognose, gegen die
  Buchungen des Monats.

Beide messen, was die Modelle messen, und zaehlen, was sie zaehlen: Eine
Buchung, die ein Vertrag oder eine erwartete Einnahme ersetzt, steht in keinem
Block. Vertraege und Objekte stehen als eigene Posten da, Soll aus ihren
Tatsachen (Termin, Betrag, Anteil der Mitzahler; Prognose des Objekts), Ist aus
den Buchungen, die sie ersetzen.

Was niemand vorhersagen kann -- Kaufnebenkosten, eine Anzahlung -- steht in
einer eigenen Spalte, statt als Fehler der Prognose zu zaehlen. Umbuchungen
und Investments zaehlen auf keiner Seite.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from finctl.forecast import abgleich as ag
from finctl.forecast import messung
from finctl.forecast import vertraege as _vt
from finctl.forecast import zinsen as _zn
from finctl.forecast.messung import Monatssumme

#: Die Vertraege, die ueber ihre Tatsachen zaehlen, als eigener Posten neben den Bloecken.
VERTRAEGE = "vertraege"

#: Diese Bloecke vergleicht die Jahresbasis. `einmalig` ist nicht
#: vorhersehbar, `investment` keine Ausgabe, das Objekt steht als Annahme
#: daneben. Die Vertraege sind kein Block des Ledgers: Sie nehmen ihre Buchungen aus den
#: Bloecken, in denen ihre Kategorien stehen.
BLOECKE = ("gehalt", "miete", "einkommen_sonst", "kredit", "immobilie",
           "fixkosten", "steuern", "konsum", ag.OBJEKT, VERTRAEGE)

#: Wie ein Posten heisst, der kein Block des Ledgers ist.
NAMEN = {VERTRAEGE: "Verträge"}


@dataclass(slots=True)
class Monat:
    monat: date
    soll: dict[str, int] = field(default_factory=dict)
    ist: dict[str, int] = field(default_factory=dict)
    #: Was im Monat gebucht und von keiner Prognose erwartet war.
    unvorhersehbar_cents: int = 0
    #: Bloecke, fuer die es in diesem Monat keine Prognose gibt, gegen die man
    #: halten koennte -- ein Tilgungsplan, der erst spaeter beginnt.
    nicht_vergleichbar: set[str] = field(default_factory=set)

    def _zaehlt(self, block: str) -> bool:
        return block not in self.nicht_vergleichbar

    @property
    def sparrate_soll(self) -> int:
        return sum(v for b, v in self.soll.items() if self._zaehlt(b))

    @property
    def sparrate_ist(self) -> int:
        return sum(self.ist.get(b, 0) for b in self.soll if self._zaehlt(b))

    def delta(self, block: str) -> int | None:
        if not self._zaehlt(block):
            return None
        return self.ist.get(block, 0) - self.soll.get(block, 0)


@dataclass(slots=True)
class KontoMonat:
    monat: date
    konto: str
    soll_cents: int
    ist_cents: int
    ohne_kredit: bool = False
    #: Die Vertraege und die Objekte mit Prognose auf diesem Konto: Soll und Ist stecken in den
    #: Summen oben und stehen hier noch einmal fuer sich.
    vertrag_soll_cents: int = 0
    vertrag_ist_cents: int = 0
    objekt_soll_cents: int = 0
    objekt_ist_cents: int = 0

    @property
    def delta_cents(self) -> int:
        return self.ist_cents - self.soll_cents


def letzte_monate(conn: sqlite3.Connection, anzahl: int = 6) -> list[date]:
    ende = ag.letzter_vollstaendiger_monat(conn)
    if ende is None:
        return []
    letzter = date(ende.year, ende.month, 1)
    return [ag._plus_monate(letzter, -i) for i in range(anzahl - 1, -1, -1)]


def fenster_vor(conn: sqlite3.Connection, monat: date, monate: int = 12):
    """Die `monate` vollstaendigen Monate VOR `monat` -- ohne ihn selbst."""
    bis = ag._month_end(ag._plus_monate(monat, -1))
    von = ag._plus_monate(monat, -monate)
    erster = conn.execute(
        "SELECT MIN(period_start) FROM statements WHERE status = 'imported'"
    ).fetchone()[0]
    if erster:
        e = date.fromisoformat(erster)
        voll = e if e.day == 1 else ag._plus_monate(e.replace(day=1), 1)
        von = max(von, voll)
    if von > bis:
        return None
    anzahl = (bis.year * 12 + bis.month) - (von.year * 12 + von.month) + 1
    return ag.Fenster(von=von, bis=bis, monate=anzahl)


def _soll_je_block(conn: sqlite3.Connection, f,
                   ohne: frozenset[str] = frozenset()) -> dict[str, int]:
    """Was die Hochrechnung zum Ende des Fensters je Monat erwartet hat: der
    Jahreswert je Block aus ihrer Basis, durch zwoelf.

    Dieselbe Rechnung wie die Basis -- Reihen mit Takt plus Rest, ohne die Buchungen in `ohne`
    (was ein Vertrag oder eine erwartete Einnahme ersetzt) --, sonst pruefte der Check eine
    Rechnung, die die Hochrechnung nicht mehr macht. Zwei Dinge zaehlen hier wie gebucht, nicht
    wie die Hochrechnung sie fortschreibt: Zinsen und Kapitalertragsteuer (`GERECHNET`), und
    eine abgewaehlte Kategorie. Das Ist ist, was gebucht wurde.
    """
    from finctl.forecast import jahre as jm

    basis = jm._basis(conn, f, ohne, auch_abgewaehlte=True, ausser=frozenset())[0]
    return {b: round(sum(basis.get(b, {}).values()) / 12) for b in jm.FROM_BASE}


def jahresbasis(conn: sqlite3.Connection, monate: list[date], *,
                plaene: list | None = None, objekt_cents=None) -> list[Monat]:
    """Die Jahresbasis gegen das Ist, Monat fuer Monat.

    `plaene` sind die Tilgungsplaene (siehe jahre._tilgungsplaene); ohne
    Angabe die wirksamen aus loans.yaml. `objekt_cents(monat)` liefert die
    Annahme fuer das Objekt; ohne Angabe rechnet sie das Objekt wie die Jahresrechnung
    (`objektposten.netto`).

    Soll und Ist messen ohne die Buchungen, die ein Vertrag oder eine erwartete Einnahme
    ersetzt, so wie die Jahresrechnung selbst (`jahre._eingaben`). Die Vertraege stehen
    dafuer als eigener Posten da: Soll ihre Termine und der erwartete Anteil der Mitzahler,
    Ist die Buchungen, die sie ersetzen. Die erwarteten Einnahmen stehen in keinem von
    beiden; sie sind eine Eingabe und keine Messung.
    """
    from finctl import assumptions as ann
    from finctl.forecast import jahre as jm
    from finctl.forecast import szenarien as sz

    if plaene is None:
        plaene = jm._tilgungsplaene(sz.aktive_ids())
    if objekt_cents is None:
        objekt_cents = _objekt_annahme(conn)
    abos = [a for a, _block in jm.gezaehlte_vertraege(conn, _vt.police_vertraege())]
    vertrags_hashes = frozenset(_vt.aus_der_messung(conn, abos))
    erwartet = frozenset(sz.erwartet_zugeordnet(conn, jm._szenarien_laden()))
    ohne = erwartet | vertrags_hashes
    out = []
    for m in monate:
        f = fenster_vor(conn, m)
        eintrag = Monat(monat=m)
        if f is not None:
            eintrag.soll.update(_soll_je_block(conn, f, ohne))
        # Das Gehalt der Jahresrechnung ist die Untergrenze, wie sie heute steht.
        eintrag.soll["gehalt"] = ann.salary_floor_cents()
        eintrag.soll["kredit"] = -sum(
            p.payment_cents for _loan, sched in plaene for p in sched.payments
            if (p.month.year, p.month.month) == (m.year, m.month))
        # Die Tilgungsplaene sind am zuletzt beobachteten Saldo verankert und
        # koennen fruehere Monate nicht nachbilden. Beginnt einer spaeter, ist
        # die Kreditzeile in diesem Monat kein Treffer und kein Fehler.
        if any(sched.payments and sched.payments[0].month > ag._month_end(m)
               for _loan, sched in plaene):
            eintrag.nicht_vergleichbar.add("kredit")
        eintrag.soll[ag.OBJEKT] = objekt_cents(m)
        eintrag.soll[VERTRAEGE] = sum(_vertragssoll(conn, abos, m, {}, ()).values())

        im_monat = ag.Fenster(von=m, bis=ag._month_end(m), monate=1)
        ist = ag.measure(conn, im_monat, ohne)
        eintrag.ist = {b: ist.get(b, 0) for b in BLOECKE}
        # Was die Vertraege ersetzen, ist der Unterschied zur Messung ohne sie.
        mit_vertraegen = ag.measure(conn, im_monat, erwartet) if vertrags_hashes else ist
        eintrag.ist[VERTRAEGE] = sum(mit_vertraegen.get(b, 0) - ist.get(b, 0)
                                     for b in BLOECKE if b != VERTRAEGE)
        eintrag.unvorhersehbar_cents = ist.get(ag.EINMALIG, 0)
        out.append(eintrag)
    return out


def _objekt_annahme(conn: sqlite3.Connection):
    """Was die Objekte mit Prognose in einem Monat abwerfen sollten, wie die Jahresrechnung es
    rechnet: Prognose, Saison, Ende und Verkauf (`objektposten.netto`)."""
    from finctl import objekte
    from finctl.forecast import jahre as jm
    from finctl.forecast import konten as ops
    from finctl.forecast import objektposten as ob

    prognosen = objekte.prognosen()
    rate = ops.steigerung(None)
    verkauf = ({v.property_id: v.ab for v in jm.verkaeufe(conn, date.today().year)}
               if prognosen else {})

    def netto(m: date) -> int:
        return sum(ob.netto(p, m, m.year, rate, verkauf.get(p.id)) for p in prognosen)

    return netto


def _zeitraumanteil(abo: dict, termin: date) -> int:
    """Der vereinbarte Anteil der Mitzahler an diesem Termin, wo ein angelegter Zeitraum ihn deckt.

    Die Modelle zaehlen dort nur den offenen Rest (`abos.rueckzahlungen`), im Einsammel-Monat.
    Das Ist des Checks enthaelt aber ihre Zahlungen, also gehoert der vereinbarte Anteil ins
    Soll: der Anteil aller Personen des Zeitraums, auf dessen Termine verteilt. Den offenen
    Rest nimmt das Soll nicht."""
    from finctl import abos as _ab

    zeitraum = _ab.zeitraum_am(abo, termin)
    if zeitraum is None:
        return 0
    von = _ab._monat_erster(zeitraum["von"])
    bis = max(_ab._monat_erster(zeitraum["bis"]), _ab.plus_monate(von, 1))
    termine = [t for t in _vt.termine(abo, (), ab=von,
                                      bis=ag._month_end(_ab.plus_monate(bis, -1)))
               if _ab.zeitraum_am(abo, t) is zeitraum]
    if not termine:
        return 0
    return round(sum(p["anteil_cents"] for p in zeitraum["personen"]) / len(termine))


def _vertragssoll(conn: sqlite3.Connection, abos: list[dict], monat: date,
                  deckung: dict[str, str], police) -> dict[str, int]:
    """Was die Vertraege in diesem Monat kosten und die Mitzahler erwartet zahlen, je Konto.

    Wie beide Modelle es rechnen: der Betrag am Vertrag, mit der Inflation seit der Mitte des
    Messfensters (`vertraege.vertragsbetrag`), und der Anteil laut Besetzung
    (`vertraege.anteil_am_termin`) dort, wo die Mitzahler zuletzt gezahlt haben. Ein
    durchlaufendes Konto zaehlt auf dem, das es deckt (`deckung`).
    """
    from finctl import abos as _ab
    from finctl.forecast import konten as ops

    fenster = ops.messfenster(conn, monat)
    mitte, rate = (fenster.mitte if fenster else None), ops.steigerung(None)
    out: dict[str, int] = {}
    for abo in abos:
        konto = deckung.get(abo["konto"], abo["konto"])
        for termin in _vt.termine(abo, (), ab=monat, bis=ag._month_end(monat)):
            out[konto] = out.get(konto, 0) + _vt.vertragsbetrag(
                abo, termin, mitte=mitte, rate=rate, police=police)
            anteil = (_vt.anteil_am_termin(abo, termin, mitte=mitte, rate=rate, police=police)
                      + _zeitraumanteil(abo, termin))
            if anteil:
                eingang = _ab.eingangskonto(conn, abo) or abo["konto"]
                eingang = deckung.get(eingang, eingang)
                out[eingang] = out.get(eingang, 0) + anteil
    return out


def _ist_je_konto(conn: sqlite3.Connection, monat: date, konten_ids: list[str],
                  deckung: dict[str, str],
                  ohne: frozenset[str] = frozenset()) -> dict[str, list[Monatssumme]]:
    """Die Monatssummen des Monats je Konto, Umbuchungen nach Praefix UND Art
    draussen -- die dritte Regel der Messung, weil das Ist hier genau das
    beschreibt, was die abgeleiteten Posten beschreiben. Ein durchlaufendes Konto
    zaehlt auf dem Konto, das es deckt (`deckung`). Was eine erwartete Einnahme ersetzt,
    schreibt das Soll nicht fort und zaehlt hier deshalb nicht; `ohne` nimmt weitere
    Buchungen heraus (was ein Vertrag ersetzt)."""
    from finctl.forecast import konten as ops

    je_konto: dict[str, list[Monatssumme]] = {}
    for z in messung.monatssummen(
            conn, von=monat, bis=ag._month_end(monat), konten=frozenset(konten_ids),
            ausschluss=messung.Ausschluss(umbuchung="beide",
                                          deckung=tuple(sorted(deckung.items())),
                                          hashes=ops.erwartete_hashes(conn) | ohne),
            je_block=True):
        je_konto.setdefault(z.konto, []).append(z)
    return je_konto


def _ist_zaehlt(z: Monatssumme, ohne_kredit: bool) -> bool:
    """Was das Ist ausser Umbuchungen nicht zaehlt: Investments, Einmaliges
    (der Block `einmalig`) und ein Objekt mit Prognose (der Block `objekt`: sein Ertrag
    ist Annahme, nicht Fortschreibung -- es steht als eigener Posten daneben, `_objekt_ist`)
    kann keine Fortschreibung beschreiben, ebenso wenig
    Zinsen und Kapitalertragsteuer (`GERECHNET`: aus dem Stand des Kontos, nicht aus der
    Messung); Kreditbuchungen nur dort, wo auch der Tilgungsplan sie dem Soll nicht gibt."""
    if (z.kategorie.startswith("investment/") or z.block in (ag.EINMALIG, ag.OBJEKT)
            or z.kategorie in _zn.GERECHNET):
        return False
    return not (ohne_kredit and z.kategorie.startswith("kredit/"))


def _objekt_ist(zeilen: list[Monatssumme]) -> int:
    """Was die Objekte mit Prognose auf einem Konto gebucht haben: auch in Monaten, in denen
    die Prognose nichts annimmt (vor `ab`, nach `bis`)."""
    return sum(z.cents for z in zeilen if z.block == ag.OBJEKT)


class _Konten:
    """Das, was fuer alle Monate des Konten-Checks gleich bleibt, einmal gelesen."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        from finctl import abos as _ab
        from finctl.forecast import konten as ops
        from finctl.realestate.loan import (
            amortise,
            lade_kredite,
            opening_balance_cents,
            segments_from,
        )

        self.conn = conn
        self.ops = ops
        self.fcfg = ops.forecast_config()
        self.abos = _ab.alle_vertraege()
        self.overrides = ops._income_overrides(self.fcfg, ops._erster_offener_monat(conn).year)
        self.kredite = []
        for loan in lade_kredite(ops.CONFIG_DIR):
            if not loan.get("segments") or not loan.get("servicing_account_id"):
                continue
            try:
                self.kredite.append((loan["servicing_account_id"], amortise(
                    str(loan["id"]), opening_balance_cents(loan), segments_from(loan))))
            except Exception:
                continue
        durchlaufend = ops.durchlaufende_konten(self.fcfg)
        self.konten_ids = [r["id"] for r in conn.execute(
            "SELECT id FROM accounts WHERE ingest_mode='parsed' AND active=1 ORDER BY id")
            if r["id"] not in durchlaufend]
        self.police = ops.police_vertraege()
        self.betrieb = ops._operating_account(self.fcfg)
        # Was die Vertraege in der Kontoprognose ersetzen: ihre Reihen und die Zahlungen ihrer
        # Mitzahler.
        self.vertrags_hashes = frozenset(_vt.aus_der_messung(conn, self.abos))

    def _soll_abgeleitet(self, konto: str, m: date, reihen) -> int:
        """Die abgeleiteten Posten des Kontos, die im Monat faellig sind."""
        from finctl.forecast import engine as fc

        soll = 0
        for item in self.ops.abgeleitete_posten(self.conn, konto, self.fcfg, self.abos,
                                                stichtag=m, reihen=reihen):
            if not item.due_in(m):
                continue
            soll += fc.override_in(self.overrides, item.label, m) \
                if item.label in self.overrides else item.amount_in(m)
        return soll

    def _soll_kredit(self, konto: str, m: date) -> tuple[int, bool]:
        """Die Raten des Kontos im Monat -- und ob ein Tilgungsplan erst spaeter beginnt.

        Wie in der Jahresbasis kann der diesen Monat nicht nachbilden. Dann bleiben die
        Kreditbuchungen auf BEIDEN Seiten draussen."""
        eigene = [sched for servicing, sched in self.kredite if servicing == konto]
        ohne_kredit = any(sched.payments and sched.payments[0].month > ag._month_end(m)
                          for sched in eigene)
        if ohne_kredit:
            return 0, True
        return -sum(p.payment_cents for sched in eigene for p in sched.payments
                    if (p.month.year, p.month.month) == (m.year, m.month)), False

    def _soll_objekt(self, konto: str, m: date) -> int:
        """Miete und Kosten der Objekte mit Prognose auf diesem Konto, wie `/konten` sie bucht."""
        stichtag = m - timedelta(days=1)
        return sum(p.amount_cents for p in self.ops._objektposten(
            self.conn, konto, self.fcfg, stichtag, 1, self.betrieb))

    def monat(self, m: date) -> list[KontoMonat]:
        """Der Konten-Check eines Monats, Konto fuer Konto."""
        deckung = self.ops.deckung_zum(self.conn, self.fcfg, m - timedelta(days=1))
        ist_alle = _ist_je_konto(self.conn, m, self.konten_ids, deckung)
        # Ohne die Buchungen der Vertraege: der Unterschied ist ihr Ist.
        ist_rest = _ist_je_konto(self.conn, m, self.konten_ids, deckung, self.vertrags_hashes)
        vertraege = _vertragssoll(self.conn, self.abos, m, deckung, self.police)
        # Die Reihen, wie sie am Ende des Vormonats standen: einmal je Monat.
        reihen = self.ops.reihen_vor(self.conn, m, self.abos, fcfg=self.fcfg)
        out = []
        for konto in self.konten_ids:
            soll_kredit, ohne_kredit = self._soll_kredit(konto, m)
            soll = self._soll_abgeleitet(konto, m, reihen) + soll_kredit
            ist = sum(z.cents for z in ist_rest.get(konto, ()) if _ist_zaehlt(z, ohne_kredit))
            vertrag_ist = sum(z.cents for z in ist_alle.get(konto, ())
                              if _ist_zaehlt(z, ohne_kredit)) - ist
            objekt_soll = self._soll_objekt(konto, m)
            objekt_ist = _objekt_ist(ist_alle.get(konto, []))
            gesamt_soll = soll + vertraege.get(konto, 0) + objekt_soll
            gesamt_ist = ist + vertrag_ist + objekt_ist
            if gesamt_soll or gesamt_ist:
                out.append(KontoMonat(
                    monat=m, konto=konto, soll_cents=gesamt_soll, ist_cents=gesamt_ist,
                    ohne_kredit=ohne_kredit, vertrag_soll_cents=vertraege.get(konto, 0),
                    vertrag_ist_cents=vertrag_ist, objekt_soll_cents=objekt_soll,
                    objekt_ist_cents=objekt_ist))
        return out


def konten(conn: sqlite3.Connection, monate: list[date]) -> list[KontoMonat]:
    """Die Kontoprognose je Konto gegen die Buchungen des Monats.

    Verglichen wird der Saldo aus Kosten und Einnahmen ohne Umbuchungen und
    ohne Investments -- das, was die abgeleiteten Posten beschreiben.
    Deklarierte Zuweisungen zwischen eigenen Konten zaehlen deshalb auf
    keiner Seite. Vertraege und Objekte mit Prognose stehen zusaetzlich einzeln da.
    """
    rechnung = _Konten(conn)
    return [zeile for m in monate for zeile in rechnung.monat(m)]


def pruefen(conn: sqlite3.Connection, anzahl: int = 6) -> dict:
    """Beide Pruefungen, fertig fuer Seite und CLI."""
    monate = letzte_monate(conn, anzahl)
    if not monate:
        return {"monate": [], "jahres": [], "konten": [], "bloecke": BLOECKE, "namen": NAMEN}
    jahres = jahresbasis(conn, monate)
    kontozeilen = konten(conn, monate)
    n = len(jahres)
    mittel = {}
    for b in BLOECKE:
        werte = [abs(j.delta(b)) for j in jahres if j.delta(b) is not None]
        mittel[b] = round(sum(werte) / len(werte)) if werte else None
    mittel["sparrate"] = round(sum(abs(j.sparrate_ist - j.sparrate_soll)
                                   for j in jahres) / n)
    je_konto: dict[str, list[int]] = {}
    for k in kontozeilen:
        je_konto.setdefault(k.konto, []).append(abs(k.delta_cents))
    return {
        "monate": monate, "jahres": jahres, "konten": kontozeilen,
        "bloecke": BLOECKE, "namen": NAMEN, "mittel": mittel,
        "konten_mittel": {k: round(sum(v) / len(v)) for k, v in je_konto.items()},
        "konten_ids": sorted(je_konto),
    }
