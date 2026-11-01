"""Paritaet: Monatsmodell und Jahresrechnung rechnen aus denselben Eingaben.

Das Monatsmodell (`/konten`) und die Jahresrechnung (`/hochrechnung`, `/ziele`)
sollen denselben Haushalt fortschreiben. Schritt 5b gleicht ihre Eingaben an, eine
je Teilschritt; dieser Test macht messbar, wie weit sie sind.

WAS VERGLICHEN WIRD. Je vollem Kalenderjahr im Horizont von `/konten` und je Block
der Jahresrechnung (vor der Kaskade) die externen Fluesse des Monatsmodells, ueber
alle Konten summiert. Ein Posten kommt in den Block seiner Kategorie
(`abgleich.bloecke`), ein Vertrag in den seines Vertrags, eine Kreditrate in
`kredit`, eine Planzeile in `einmalig` und eine erwartete Einnahme in den Block ihrer
Kategorie. Geld zwischen den Konten (Dauerauftrag,
Zuweisung, Auffuellung, Abraeumen) hebt sich im Haushalt auf; der Posten sagt es
selbst (`Posten.umbuchung`), sein Etikett gilt nichts.

WAS DIE TOLERANZ DECKT: Rundung, mehr nicht. Ueber ein volles Kalenderjahr gleichen
sich Termine aus, ein Betrag, der im Monatsmodell am 15. und in der Jahresrechnung
als Zwoelftel faellt, ist nach zwoelf Monaten derselbe. Eine prozentuale Toleranz
deckte Fehler zu.

DIE LISTE BEKANNTER UNTERSCHIEDE (`BEKANNT`) darf nur kuerzer werden, wie
`ZU_VERZWEIGT` in `tests/test_lint.py`. Ein Block, der abweicht und nicht in ihr
steht, laesst den Test fehlschlagen -- und einer, der in ihr steht und nicht mehr
abweicht, ebenso. So muss jeder Teilschritt von 5b seinen Eintrag streichen.
Vier Unterschiede stehen nicht in der Liste, weil sie bleiben (`DAUERHAFT`).
"""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from unittest import mock

import pytest

from finctl import abos as _abos
from finctl import bestaende, ops
from finctl.dateien import yaml_lesen
from finctl.forecast import abgleich as ag
from finctl.forecast import engine, wachstum
from finctl.forecast import jahre as jm
from finctl.forecast import prognosebasis as pb
from finctl.forecast import szenarien as sz
from finctl.forecast import ziele as zl
from finctl.ledger import db as ledger
from finctl.pfade import CONFIG_DIR, DB_PATH

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="kein Hauptbuch")

#: Rundung: jeder Posten des Monatsmodells ist auf den Cent gerundet, ebenso die
#: Jahresrechnung. Ueber ein Jahr, einen Block und mehrere Posten summiert sich das
#: auf wenige Cent. Ein Euro ist die Obergrenze, nicht der Normalfall.
RUNDUNG_CENTS = 100

#: Die Bloecke der Jahresrechnung vor der Kaskade.
BLOECKE = ("gehalt", "miete", "einkommen_sonst", "objekt", "fixkosten", "immobilie",
           "konsum", "steuern", "kredit", "einmalig", "rente")

#: Die Liste bekannter Unterschiede: je Block die Gruende, jeder mit dem Teilschritt
#: von Schritt 5b (`docs/schritt5b_zeitachsen.md`), der ihn beseitigt. DARF NUR
#: KUERZER WERDEN. Hat ein Teilschritt seine Eingabe angeglichen, streicht er seinen
#: Grund; weicht der Block danach nicht mehr ab, faellt er ganz aus der Liste, und
#: der Test verlangt das.
BEKANNT: dict[str, list[tuple[str, str]]] = {}

#: Die Teilschritte von 5b, die einen Grund beseitigen koennen. E.8 ist kein Angleichen,
#: sondern die Entscheidung, die ein Grund noch braucht, weil kein Teilschritt ihn
#: beseitigt (Plan, "Gefundene Abweichungen").
_SCHRITTE = ("E.2", "E.2b", "E.3", "E.4", "E.5", "E.6", "E.7", "E.8")

#: Was auf Dauer anders bleibt und deshalb nicht in `BEKANNT` steht:
#:
#: * die KASKADE der Jahresrechnung (Tagesgeld ueber der Grenze ins Depot): der Test
#:   vergleicht die Bloecke davor;
#: * Planzeilen "nur Kontoprognose": die Reihe wechselt das Konto, ausgegeben wird
#:   weiter, und die Jahresrechnung sieht sie nie (Abnahme E.0, Nummer 10);
#: * Anlagen (`investment/`): die Jahresrechnung nimmt sie aus der Basis, weil Konto
#:   und Depot beide zum Vermoegen zaehlen;
#: * Reihen mit Takt steigen an ihrem Termin (gewollt, Abnahme E.2b, Nummer 3): Ein
#:   Jahresposten im Januar steigt im Monatsmodell weniger als einer im Dezember, die
#:   Jahresrechnung rechnet beide zur Jahresmitte. Der Test rechnet das Monatsmodell dafuer
#:   zur Jahresmitte (`_zur_jahresmitte`) und fuehrt den Unterschied zu ihrem Termin hier;
#: * Zinsen und die Steuer darauf (`zinsen`): die Jahresrechnung verzinst den Topf nach der
#:   Kaskade; der Stand ist ihr Ergebnis, keine Eingabe. Das Monatsmodell verzinst den
#:   Stand, den es selbst vorausrechnet. Beide rechnen mit derselben Regel (Abnahme E.1,
#:   Nummer 1); dass sie bei gleichem Stand und gleichem Satz dasselbe ergeben, belegt
#:   `tests/test_zinsen_paritaet.py`.
DAUERHAFT = ("nur_kontoprognose", "investment", "reihen_mit_takt", "zinsen")


@dataclass
class Bilanz:
    """Anfang, Fluesse und Ende ueber alle Konten, im Detail der Monate."""

    anfang: int = 0
    ende: int = 0
    extern: int = 0
    umbuchung: int = 0
    abgeraeumt: int = 0
    #: Monate, in denen die Summe des Details nicht Kosten plus Einnahmen ist.
    luecken: list[str] = field(default_factory=list)


@dataclass
class Lauf:
    jahre: list[int]
    monat: dict[tuple[int, str], int]
    jahr: dict[tuple[int, str], int]
    #: Was das Monatsmodell bucht und die Jahresrechnung nie sieht (`DAUERHAFT`).
    ausgenommen: dict[tuple[int, str], int]
    bilanz: Bilanz
    #: Was erwartete Einnahmen in beiden Modellen zaehlen: je Jahr die Summe der Zeile
    #: (Schluessel `Klammer:Nummer`) und die der Messung ihrer Kategorie
    #: (`kategorie:<Kennung>`), im Monatsmodell und in der Jahresrechnung.
    erwartet_monat: dict[tuple[int, str], int] = field(default_factory=dict)
    erwartet_jahr: dict[tuple[int, str], int] = field(default_factory=dict)

    def abweichung(self, jahr: int, block: str) -> int:
        return self.monat.get((jahr, block), 0) - self.jahr.get((jahr, block), 0)

    def belegt(self) -> set[str]:
        """Die Bloecke, in denen dieser Haushalt irgendetwas hat. Ein Block ohne
        Zahl auf beiden Seiten kann nicht abweichen -- und nicht gleich sein."""
        return {b for b in BLOECKE for j in self.jahre
                if self.monat.get((j, b)) or self.jahr.get((j, b))}

    def abweichende(self) -> dict[str, dict[int, int]]:
        """Je Block die Jahre, in denen er ueber die Rundung hinaus abweicht."""
        out: dict[str, dict[int, int]] = {}
        for block in BLOECKE:
            for jahr in self.jahre:
                d = self.abweichung(jahr, block)
                if abs(d) > RUNDUNG_CENTS:
                    out.setdefault(block, {})[jahr] = d
        return out


# ------------------------------------------------------------------ Monatsmodell

class _Zuordnung:
    """In welchen Block ein Posten des Monatsmodells gehoert."""

    def __init__(self, conn) -> None:
        self.conn = conn
        self.vertraege = {a["id"]: a["kategorie"] for a in _abos.alle_vertraege()}
        self.zeilen = {s.id: s for s in jm._szenarien_laden()}
        self._bloecke: dict[str, str | None] = {}

    def _block_der_kategorie(self, kategorie: str) -> str | None:
        if kategorie not in self._bloecke:
            self._bloecke[kategorie] = pb._block_fuer(self.conn, kategorie)
        return self._bloecke[kategorie]

    def _planzeile(self, verweis: str):
        klammer, index = str(verweis).rsplit(":", 1)
        return self.zeilen[klammer].lines[int(index)]

    def _von_planzeile(self, herkunft: dict) -> str:
        """Eine Planzeile zaehlt in `einmalig`, eine erwartete Einnahme im Block ihrer Kategorie."""
        zeile = self._planzeile(herkunft["verweis"])
        if zeile.nur_kontoprognose:
            return "nur_kontoprognose"
        if herkunft.get("kategorie") in jm.GERECHNET:
            return "zinsen"
        if zeile.kind == "erwartet":
            block = self._block_der_kategorie(zeile.category_id)
            return block if block in jm._BLOECKE_ERWARTET else ag.EINMALIG
        return ag.EINMALIG

    def erwartet(self, herkunft: dict) -> bool:
        return (herkunft.get("quelle") == "plan"
                and self._planzeile(herkunft["verweis"]).kind == "erwartet")

    def von(self, label: str, herkunft: dict) -> str:
        if herkunft.get("umbuchung"):
            return "umbuchung"
        if herkunft.get("objekt"):
            return "objekt"
        if herkunft.get("quelle") == "plan":
            return self._von_planzeile(herkunft)
        if label.startswith("loan:"):
            return "kredit"
        for vorsatz in ("abo-zurueck:", "abo-anteil:", "abo:"):
            if label.startswith(vorsatz):
                return self._block_der_kategorie(self.vertraege[label[len(vorsatz):]])
        if label in jm.GERECHNET:
            return "zinsen"
        block = self._block_der_kategorie(label)
        return "investment" if block == "investment" else block


@contextmanager
def _zur_jahresmitte():
    """Reihen mit Takt steigen im Monatsmodell zur Jahresmitte, wie in der Jahresrechnung,
    statt an ihrem Termin. Die monatlichen bleiben, wie sie sind: Ihre zwoelf Monatsmitten
    mitteln sich auf die Jahresmitte (`wachstum`)."""
    alt = engine.RecurringItem.amount_in

    def betrag(self, month):
        if self.every_months == 1 or not self.escalation_pa:
            return alt(self, month)
        return wachstum.fortschreiben(self.amount_cents, self.mitte,
                                      wachstum.jahresmitte(month.year), self.escalation_pa)

    with mock.patch.object(engine.RecurringItem, "amount_in", betrag):
        yield


def _erwartete_zeilen() -> dict[str, sz.Line]:
    """Die erwarteten Einnahmen eingeschalteter Klammern, nach `Klammer:Nummer`."""
    return {f"{s.id}:{i}": line for s in sz.active(jm._szenarien_laden())
            for i, line in enumerate(s.lines) if line.kind == "erwartet"}


def _monatsmodell(conn, views: list[dict]) -> tuple[dict, dict, Bilanz, list[int], dict]:
    zuordnung = _Zuordnung(conn)
    kategorien = {line.category_id for line in _erwartete_zeilen().values()}
    erwartet: dict[tuple[int, str], int] = defaultdict(int)
    summe: dict[tuple[int, str], int] = defaultdict(int)
    daneben: dict[tuple[int, str], int] = defaultdict(int)
    bilanz = Bilanz()
    monate: dict[int, set[int]] = defaultdict(set)
    for v in views:
        if v.get("error"):
            continue
        rows = v["rows"]
        bilanz.anfang += rows[0]["opening_cents"]
        bilanz.ende += rows[-1]["closing_cents"]
        for row in rows:
            jahr = int(row["month"][:4])
            monate[jahr].add(int(row["month"][5:7]))
            bilanz.abgeraeumt += row["swept_cents"]
            if sum(row["detail"].values()) != row["costs_cents"] + row["income_cents"]:
                bilanz.luecken.append(f"{v['id']} {row['month']}")
            for label, cents in row["detail"].items():
                if zuordnung.erwartet(v["herkunft"][label]):
                    erwartet[(jahr, v["herkunft"][label]["verweis"])] += cents
                elif label in kategorien:
                    erwartet[(jahr, f"kategorie:{label}")] += cents
                block = zuordnung.von(label, v["herkunft"][label])
                if block == "umbuchung":
                    bilanz.umbuchung += cents
                    continue
                bilanz.extern += cents
                ziel = daneben if block in DAUERHAFT else summe
                ziel[(jahr, block)] += cents
    vollstaendig = sorted(j for j, m in monate.items() if len(m) == 12)
    return dict(summe), dict(daneben), bilanz, vollstaendig, dict(erwartet)


# ------------------------------------------------------------------ Jahresrechnung

def _lesen(name: str) -> dict:
    pfad = CONFIG_DIR / name
    return (yaml_lesen(pfad) or {}) if pfad.exists() else {}


def _jahresrechnung(conn, bis_jahr: int) -> jm.Projection:
    """Die Jahresrechnung, wie die Seite `/ziele` sie rechnet."""
    goals = zl.aus_spec(_lesen("goals.yaml"))
    merged = bestaende.zusammenfuehren(conn, _lesen("balances.yaml"))
    je_tempo = jm.eingaben_je_tempo(
        conn, opening_cents=zl.liquid_cents(merged), toepfe=zl.toepfe(merged),
        depot_gewinn_cents=zl.depot_gewinn(merged),
        puffer_cents=zl.puffer_cents(goals),
        policen_je_konto=zl.policen_je_konto(merged),
        tagesgeld_je_konto=zl.tagesgeld_je_konto(merged))
    return jm.rechnen(je_tempo["schnitt"], end_year=bis_jahr)


def _vergleichbar(lauf: jm.Projection, jahre: list[int], vergangen: int) -> list[int]:
    """Die Jahre, die die Jahresrechnung ganz projiziert: das Basisjahr nur, wenn
    von ihm nichts im Bestand steckt."""
    return [j for j in jahre if j > lauf.base_year or (j == lauf.base_year and not vergangen)]


def _erwartet_jahresrechnung(projektion: jm.Projection) -> dict[tuple[int, str], int]:
    """Was die Jahresrechnung je Jahr fuer die erwarteten Einnahmen zaehlt: die Zeile, und
    was in der Basis noch gemessen in ihrer Kategorie steht."""
    zeilen = _erwartete_zeilen()
    kategorien = {line.category_id for line in zeilen.values()}
    out: dict[tuple[int, str], int] = defaultdict(int)
    for y in projektion.years:
        for posten in y.posten.values():
            for p in posten:
                if p.verweis in zeilen:
                    out[(y.year, p.verweis)] += p.cents
                elif p.quelle == "gemessen" and p.verweis in kategorien:
                    out[(y.year, f"kategorie:{p.verweis}")] += p.cents
    return dict(out)


def rechnen(conn) -> Lauf:
    views = ops.household_accounts(conn, months=ops.HORIZON_LONG)
    termin, daneben, bilanz, vollstaendig, erwartet = _monatsmodell(conn, views)
    with _zur_jahresmitte():
        monat, _, _, _, _ = _monatsmodell(
            conn, ops.household_accounts(conn, months=ops.HORIZON_LONG))
    for (jahr_, block_), cents in termin.items():
        schluessel = (jahr_, "reihen_mit_takt")
        daneben[schluessel] = daneben.get(schluessel, 0) + cents - monat.get((jahr_, block_), 0)
    projektion = _jahresrechnung(conn, max(vollstaendig))
    vergangen = ag.letzter_vollstaendiger_monat(conn)
    stand = vergangen.month if vergangen and vergangen.year == projektion.base_year else 0
    jahre = _vergleichbar(projektion, vollstaendig, stand)
    jahr = {(y.year, block): y.blocks.get(block, 0)
            for y in projektion.years for block in BLOECKE}
    return Lauf(jahre=jahre, monat=monat, jahr=jahr, ausgenommen=daneben, bilanz=bilanz,
                erwartet_monat=erwartet, erwartet_jahr=_erwartet_jahresrechnung(projektion))


# ------------------------------------------------------------------ Tests

@pytest.fixture(scope="module")
def lauf():
    conn = ledger.connect(DB_PATH)
    try:
        return rechnen(conn)
    finally:
        conn.close()


def _eur(cents: int) -> str:
    return f"{cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def test_the_horizon_holds_full_years(lauf):
    """Ohne ein volles Kalenderjahr vergliche der Test nichts."""
    assert lauf.jahre, "kein volles Kalenderjahr im Horizont von /konten"


def test_nothing_is_counted_twice_or_not_at_all(lauf):
    """Bilanzprobe ueber alle Konten.

    Anfang plus Fluesse plus Umbuchungen minus Abgeraeumtes ergibt das Ende, und
    die Umbuchungen heben sich auf: Was als Uebertrag auf dem Zielkonto steht, hat
    das Betriebskonto abgegeben, und Zuweisung und Auffuellung stehen auf beiden
    Seiten. Fehlt ein Posten im Detail oder steht einer doppelt, geht eine der
    beiden Gleichungen nicht auf.
    """
    b = lauf.bilanz
    assert not b.luecken, f"Detail ohne Summe in: {b.luecken[:5]}"
    assert b.anfang + b.extern + b.umbuchung - b.abgeraeumt == b.ende
    assert b.umbuchung == b.abgeraeumt, (
        f"Umbuchungen {_eur(b.umbuchung)} gegen Abgeraeumtes {_eur(b.abgeraeumt)}")


def test_the_known_differences_name_a_reason_and_a_step():
    for block, gruende in BEKANNT.items():
        assert block in BLOECKE, block
        assert gruende, f"{block}: ohne Grund"
        for grund, schritt in gruende:
            assert grund and schritt in _SCHRITTE, (block, grund, schritt)


def test_every_difference_is_known(lauf):
    """Die Ratsche: dazukommen darf nichts."""
    neu = {b: d for b, d in lauf.abweichende().items() if b not in BEKANNT}
    assert not neu, "Neue Unterschiede, in keinem Teilschritt vorgesehen:\n  " + "\n  ".join(
        f"{b}: " + ", ".join(f"{j} {_eur(c)}" for j, c in sorted(d.items()))
        for b, d in sorted(neu.items()))


def test_a_listed_block_that_no_longer_differs_leaves_the_list(lauf):
    """Wer eine Eingabe angeglichen hat, streicht seinen Eintrag -- sonst waere die
    Liste in einem Jahr eine Sammlung von Gruenden, die nichts mehr bedeuten.

    Nur Bloecke, die der Haushalt hat: Die Liste gilt fuer jeden Datensatz, und
    ein Haushalt ohne Objekt mit Prognose hat keinen Block `objekt`, der abweichen
    koennte."""
    abweichend, belegt = lauf.abweichende(), lauf.belegt()
    gleich = sorted(b for b in BEKANNT if b in belegt and b not in abweichend)
    assert not gleich, ("Diese Bloecke weichen nicht mehr ab: aus BEKANNT streichen, mit dem "
                        "Teilschritt, der sie angeglichen hat:\n  " + "\n  ".join(
                            f"{b} ({', '.join(s for _, s in BEKANNT[b])})" for b in gleich))


def test_an_expected_income_counts_once_in_both_models(lauf):
    """Eine erwartete Einnahme ersetzt die Messung ihrer Kategorie, statt neben ihr zu stehen.

    Je volles Jahr zaehlt die Zeile in beiden Modellen genau ihren Betrag -- ohne Steigerung,
    ohne Rundung, im Monatsmodell wie in der Jahresrechnung --, und die Kategorie, deren
    Buchungen ihr zugeordnet sind, steht in keinem der beiden noch einmal gemessen da.
    """
    zeilen = _erwartete_zeilen()
    if not zeilen:
        pytest.skip("keine erwartete Einnahme in Planung")
    conn = ledger.connect(DB_PATH)
    try:
        zugeordnet = sz.erwartet_zugeordnet(conn, jm._szenarien_laden())
        # Die Messung ist nur dann weg, wenn alles zugeordnet ist: Eine Buchung der
        # Kategorie ausserhalb der Reihe bliebe gemessen, und das waere richtig.
        voll = {v: line for v, line in zeilen.items() if line.category_id and not {
            h for (h,) in conn.execute(
                "SELECT t.dedup_hash FROM transactions t JOIN splits s "
                "ON s.transaction_id = t.id WHERE s.mgmt_category_id = ?",
                (line.category_id,))} - zugeordnet}
    finally:
        conn.close()
    for verweis, line in zeilen.items():
        for jahr in lauf.jahre:
            soll = sum(line.amount_cents for w in line.months(date(jahr, 12, 1))
                       if w.year == jahr)
            assert soll, f"{verweis}: {jahr} ohne Termin, der Test belegt nichts"
            assert lauf.erwartet_monat.get((jahr, verweis), 0) == soll, (verweis, jahr)
            assert lauf.erwartet_jahr.get((jahr, verweis), 0) == soll, (verweis, jahr)
            if verweis in voll:
                kategorie = f"kategorie:{line.category_id}"
                assert lauf.erwartet_monat.get((jahr, kategorie), 0) == 0, (verweis, jahr)
                assert lauf.erwartet_jahr.get((jahr, kategorie), 0) == 0, (verweis, jahr)


# ------------------------------------------------------------------ der Test selbst

def _lauf(monat: dict, jahr: dict) -> Lauf:
    return Lauf(jahre=[2030], monat=monat, jahr=jahr, ausgenommen={}, bilanz=Bilanz())


def test_rounding_is_tolerated_and_a_euro_more_is_not():
    """Die Toleranz deckt Rundung: bis zu einem Euro je Block und Jahr, nicht mehr."""
    lauf = _lauf({(2030, "konsum"): -100_000, (2030, "miete"): 50_000},
                 {(2030, "konsum"): -100_000 - RUNDUNG_CENTS,
                  (2030, "miete"): 50_000 - RUNDUNG_CENTS - 1})
    assert lauf.abweichende() == {"miete": {2030: RUNDUNG_CENTS + 1}}


def test_a_block_without_figures_is_neither_equal_nor_different():
    lauf = _lauf({(2030, "gehalt"): 1}, {(2030, "gehalt"): 1})
    assert lauf.belegt() == {"gehalt"}
    assert lauf.abweichende() == {}

