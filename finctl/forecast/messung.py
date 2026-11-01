"""Die eine Messung: was das Hauptbuch je Konto, Kategorie und Monat sagt.

Jede Vorschau misst dasselbe und entscheidet nur, was sie nicht sehen will.
Frueher stand die Abfrage fuenfmal da, jedes Mal mit ihrer eigenen Umbuchungs-
regel und ihrem eigenen Ausschluss, und jede Kopie konnte sich um eine Buchung
von den anderen unterscheiden. Hier steht sie einmal; wer misst, ruft
`monatssummen` und fasst in Python mit `summiere` zusammen; wer die einzelnen
Teile braucht (die Reihe und ihr Takt), ruft `teile`. Summen ueber ganze Cent
sind exakt, egal in welcher Reihenfolge addiert wird.

Was HIER entschieden wird, ist nur, was je Buchung entschieden werden muss
(`Ausschluss`). Was je Kategorie entschieden wird -- Kredite, `exclude_from_
recurring`, die Abwahl auf /annahmen --, geschieht NACH der Messung und bleibt
Sache jeder Vorschau.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Protocol

#: Das Praefix, an dem die Umbuchungsregel "praefix" eine Umbuchung erkennt.
UMBUCHUNG_PRAEFIX = "transfer/"


@dataclass(frozen=True, slots=True)
class Ausschluss:
    """Welche Teile eine Messung nicht sieht, VOR dem Summieren.

    Nur was je Buchung entschieden werden muss. Kategorien fallen NACH der
    Messung heraus (Kredite, `exclude_from_recurring`, Abwahl auf /annahmen),
    wie heute auch: dort entscheidet jede Vorschau selbst.
    """

    #: "praefix": COALESCE(s.mgmt_category_id, '') NOT LIKE 'transfer/%'
    #:            (Hochrechnung, Abgleich, Prognosebasis)
    #: "art":     c.kind IS NULL OR c.kind <> 'transfer' (Kontoprognose)
    #: "beide":   Praefix UND Art (Treffer-Check: was die abgeleiteten Posten
    #:            beschreiben)
    umbuchung: Literal["praefix", "art", "beide"] = "praefix"
    #: Nur bei "art": das Konto fuehrt Umbuchungen als Buchungen, sie zaehlen.
    umbuchungen_zaehlen: bool = False
    #: Wer ein durchlaufendes Konto deckt, als Paare (durchlaufend, deckend). Die Teile
    #: eines durchlaufenden Kontos stehen in der Messung auf dem deckenden Konto, mit
    #: Fenster und Verfahren wie jeder andere Teil; das durchlaufende Konto selbst gibt
    #: es danach nicht mehr. Die Umbuchung, die es ausgleicht, ist eine Umbuchung wie
    #: jede andere und zaehlt nicht noch einmal.
    deckung: tuple[tuple[str, str], ...] = ()
    #: False: Teile ohne Kategorie fallen heraus (Kontoprognose).
    #: True:  sie zaehlen unter der Kategorie '' (alle anderen).
    ohne_kategorie: bool = True
    #: Einzelne Buchungen raus: erklaerte Vertraege samt Reihe, Wegfall-Reihen,
    #: einmalige Planzeilen.
    hashes: frozenset[str] = frozenset()
    #: Objekte, deren Ertrag angenommen statt gemessen wird (`objekte.prognosen`): Ihre
    #: Teile fallen in jeder Kategorie heraus. Die Jahresrechnung tut das ueber den Block
    #: `objekt` (`abgleich`), die Kontoprognose misst ohne Bloecke und nennt sie hier.
    objekte: frozenset[str] = frozenset()


#: Kein Ausschluss ausser der Umbuchungsregel "praefix": die Vorgabe der Messung.
KEIN_AUSSCHLUSS = Ausschluss()


@dataclass(frozen=True, slots=True)
class Monatssumme:
    konto: str
    kategorie: str          # '' fuer Teile ohne Kategorie
    block: str | None       # nur mit je_block=True, sonst None
    monat: str              # 'JJJJ-MM'
    cents: int
    #: Wie viele Buchungen in der Summe stecken (eine Buchung mit zwei Teilen
    #: derselben Kategorie zaehlt einmal). Gehoert nicht zum Wert der Zeile.
    buchungen: int = field(default=0, compare=False)


@dataclass(frozen=True, slots=True)
class Teil:
    """Ein Teil einer Buchung, so wie ihn die Messung sieht.

    Die Reihe (`reihe.py`) ist Gegenpartei und Kategorie; `gegenpartei` ist
    leer, wo die Buchung keine hat.
    """

    konto: str
    kategorie: str          # '' fuer Teile ohne Kategorie
    block: str | None       # nur mit je_block=True, sonst None
    tag: date
    cents: int
    gegenpartei: str        # counterparty_norm, '' ohne
    dedup_hash: str

    @property
    def monat(self) -> str:
        return self.tag.isoformat()[:7]


class _MitCent(Protocol):
    @property
    def cents(self) -> int: ...


def _tag(tag: date | str) -> str:
    return tag.isoformat() if isinstance(tag, date) else tag


def _umbuchung(ausschluss: Ausschluss) -> tuple[str, list[str]]:
    """Die Bedingung, die Umbuchungen nach der gewaehlten Regel behandelt."""
    praefix = ("COALESCE(s.mgmt_category_id, '') NOT LIKE "
               f"'{UMBUCHUNG_PRAEFIX}%'")
    if ausschluss.umbuchung == "praefix":
        return praefix, []
    if ausschluss.umbuchung == "beide":
        return f"{praefix} AND (m.kind IS NULL OR m.kind <> 'transfer')", []
    if ausschluss.umbuchungen_zaehlen:
        return "", []
    return "(m.kind IS NULL OR m.kind <> 'transfer')", []


def _konto_ausdruck(ausschluss: Ausschluss) -> tuple[str, list[str]]:
    """Auf welchem Konto ein Teil steht: auf seinem, ausser ein durchlaufendes Konto
    hat ein deckendes (`Ausschluss.deckung`). Ohne Deckung bleibt die Abfrage so
    schmal, wie sie war."""
    if not ausschluss.deckung:
        return "t.account_id", []
    faelle = " ".join("WHEN ? THEN ?" for _ in ausschluss.deckung)
    return (f"CASE t.account_id {faelle} ELSE t.account_id END",
            [k for paar in ausschluss.deckung for k in paar])


def _roh_konten(konten: frozenset[str], ausschluss: Ausschluss) -> list[str]:
    """Die Konten, auf denen der Ledger die Teile fuehrt, die auf `konten` stehen: ein
    durchlaufendes Konto steht nicht mehr fuer sich, sondern bei seinem deckenden."""
    durchlaufend = {d for d, _ in ausschluss.deckung}
    gedeckt = {d for d, deckend in ausschluss.deckung if deckend in konten}
    return sorted((set(konten) - durchlaufend) | gedeckt)


def _bedingungen(*, von: date | str, bis: date | str | None,
                 ausschluss: Ausschluss,
                 konten: frozenset[str] | None) -> tuple[str, list[str]]:
    """Die WHERE-Klausel der Messung, fuer Monatssummen und Teile gleich.

    `von` und `bis` gelten einschliesslich, auf dem Buchungstag. `bis=None`
    heisst: kein Ende. `konten=None`: jede Buchung im Hauptbuch.
    """
    bedingungen = ["t.booking_date >= ?"]
    args: list[str] = [_tag(von)]
    if bis is not None:
        bedingungen.append("t.booking_date <= ?")
        args.append(_tag(bis))
    if konten is not None:
        roh = _roh_konten(konten, ausschluss)
        bedingungen.append(f"t.account_id IN ({','.join('?' * len(roh))})")
        args.extend(roh)
    if not ausschluss.ohne_kategorie:
        bedingungen.append("s.mgmt_category_id IS NOT NULL")
    umbuchung, umbuchung_args = _umbuchung(ausschluss)
    if umbuchung:
        bedingungen.append(umbuchung)
        args.extend(umbuchung_args)
    if ausschluss.hashes:
        bedingungen.append(
            f"t.dedup_hash NOT IN ({','.join('?' * len(ausschluss.hashes))})")
        args.extend(sorted(ausschluss.hashes))
    if ausschluss.objekte:
        bedingungen.append(
            "(s.property_id IS NULL OR s.property_id NOT IN "
            f"({','.join('?' * len(ausschluss.objekte))}))")
        args.extend(sorted(ausschluss.objekte))
    return "\n          AND  ".join(bedingungen), args


def _block_ausdruck(je_block: bool) -> str:
    """Den Block rechnet nur, wer ihn braucht: die Zuordnung liest die
    Konfiguration der Objekte, und `abgleich` importiert dieses Modul."""
    if not je_block:
        return "NULL"
    from finctl.forecast import abgleich as _ag

    return _ag._case_expression()


def monatssummen(conn: sqlite3.Connection, *, von: date | str,
                 bis: date | str | None = None,
                 ausschluss: Ausschluss = KEIN_AUSSCHLUSS,
                 konten: frozenset[str] | None = None,
                 je_block: bool = False) -> list[Monatssumme]:
    """Monatssummen der Teile je Konto, Kategorie, (optional) Block und Monat.

    `von` und `bis` gelten einschliesslich, auf dem Buchungstag. `bis=None`
    heisst: kein Ende. `konten=None`: jede Buchung im Hauptbuch. Sortiert nach
    (konto, kategorie, block, monat) -- fest, damit niemand von der Reihenfolge
    abhaengt, die `GROUP BY` zufaellig liefert.

    Den Block rechnet nur, wer ihn braucht (`_block_ausdruck`).
    """
    wo, args = _bedingungen(von=von, bis=bis, ausschluss=ausschluss, konten=konten)
    konto, konto_args = _konto_ausdruck(ausschluss)
    block = _block_ausdruck(je_block)
    zeilen = conn.execute(f"""
        SELECT {konto} AS konto,
               COALESCE(s.mgmt_category_id, '') AS kategorie,
               {block} AS block,
               substr(t.booking_date, 1, 7) AS monat,
               SUM(s.amount_cents) AS cents,
               COUNT(DISTINCT t.id) AS buchungen
        FROM   splits s
        JOIN   transactions t ON t.id = s.transaction_id
        LEFT   JOIN mgmt_categories m ON m.id = s.mgmt_category_id
        WHERE  {wo}
        GROUP  BY konto, kategorie, block, monat
        ORDER  BY konto, kategorie, block, monat
    """, [*konto_args, *args]).fetchall()
    return [Monatssumme(konto, kategorie, blk, monat, int(cents or 0), int(anzahl))
            for konto, kategorie, blk, monat, cents, anzahl in zeilen]


def teile(conn: sqlite3.Connection, *, von: date | str,
          bis: date | str | None = None,
          ausschluss: Ausschluss = KEIN_AUSSCHLUSS,
          konten: frozenset[str] | None = None,
          je_block: bool = False) -> list[Teil]:
    """Dieselbe Messung wie `monatssummen`, aber je Teil statt je Monat.

    Die Bedingungen stehen in `_bedingungen`, damit beide Fragen dieselben
    Buchungen sehen: `summiere` ueber die Teile je Monat ergibt genau
    `monatssummen`. Sortiert nach Tag, dann nach Kennung des Teils, damit die
    Reihenfolge nicht vom Zufall der Abfrage abhaengt.
    """
    wo, args = _bedingungen(von=von, bis=bis, ausschluss=ausschluss, konten=konten)
    konto, konto_args = _konto_ausdruck(ausschluss)
    block = _block_ausdruck(je_block)
    zeilen = conn.execute(f"""
        SELECT {konto} AS konto,
               COALESCE(s.mgmt_category_id, '') AS kategorie,
               {block} AS block,
               t.booking_date AS tag,
               s.amount_cents AS cents,
               COALESCE(t.counterparty_norm, '') AS gegenpartei,
               t.dedup_hash AS dedup_hash
        FROM   splits s
        JOIN   transactions t ON t.id = s.transaction_id
        LEFT   JOIN mgmt_categories m ON m.id = s.mgmt_category_id
        WHERE  {wo}
        ORDER  BY t.booking_date, t.id, s.rowid
    """, [*konto_args, *args]).fetchall()
    return [Teil(konto, kategorie, blk, date.fromisoformat(tag), int(cents or 0),
                 gegenpartei, dedup_hash)
            for konto, kategorie, blk, tag, cents, gegenpartei, dedup_hash in zeilen]


def summiere[K, Z: _MitCent](zeilen: Iterable[Z],
                             schluessel: Callable[[Z], K]) -> dict[K, int]:
    """Cent je Schluessel. Nullsummen bleiben drin, wie bei SQL-GROUP BY."""
    summen: dict[K, int] = {}
    for zeile in zeilen:
        k = schluessel(zeile)
        summen[k] = summen.get(k, 0) + zeile.cents
    return summen
