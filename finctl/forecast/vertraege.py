"""Verträge in Monatsmodell und Jahresrechnung: eine Rechnung für beide.

Ein Vertrag ist eine Tatsache, kein Messwert: Betrag, Takt, Termin, ein Vorrat (bezahlt
bis zu einem Datum), eine Kündigung, Mitzahler. Beide Modelle zählen ihn über diese
Tatsachen -- `abos.termine` sagt, wann er zahlt, `vertragsbetrag`, was ein Termin kostet --
und messen seine Buchungen nicht: weder die eigene Reihe des Vertrags noch die Zahlungen
der Mitzahler (`abos.ausschluesse`). Was am Vertrag vorbeigebucht wird (eine Erstattung,
ein zweiter Anbieter), bleibt gemessen.

Die Mitzahler zaehlen als Eingang, nie zweimal: Hat ein Termin einen angelegten Zeitraum,
gilt dessen offener Anteil (`rueckzahlungen`, im Einsammel-Monat); sonst der Anteil, den
die Besetzung ihnen zuordnet (`anteil_am_termin`, am Termin). Er steigt wie der Betrag.

Eine Wegfall-Zeile auf der Reihe eines Vertrags setzt ihn in ihren Monaten aus
(`pausen`), statt ein zweites Mal abzuziehen, was keiner der beiden mehr misst.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Collection, Iterable
from datetime import date

from finctl import abos as _ab
from finctl.forecast import szenarien as _sz
from finctl.forecast import wachstum
from finctl.ledger import reihe as _reihe

#: Die Pausen eines Vertrags: von Monat (erster Tag) bis Monat, offen nach oben.
Pausen = tuple[tuple[date, date | None], ...]


def police_vertraege() -> frozenset[str]:
    """Die Vertraege, die eine Police speisen. Ihr Beitrag bleibt nominal fest, in
    beiden Modellen (`jahre._beitragsposten`), und ihr Ende regelt die Police."""
    from finctl import renten as _renten

    return frozenset(q.beitrag for q in _renten.quellen() if q.beitrag and q.konto)


def vertragsbetrag(abo: dict, faellig: date, *, mitte: float | None, rate: float,
                   police: Collection[str]) -> int:
    """Was ein Vertrag an seinem Termin kostet: der Betrag am Vertrag, mit der Inflation
    seit der Mitte des Messfensters fortgeschrieben wie eine gemessene Reihe
    (`wachstum`). Ein Policenbeitrag bleibt flach. Ohne Fenster (`mitte` None) gibt es
    nichts, wovon aus zu steigern."""
    if mitte is None or abo["id"] in police:
        return abo["betrag_cents"]
    return wachstum.fortschreiben(abo["betrag_cents"], mitte,
                                  wachstum.monatsmitte(faellig), rate)


def anteil_am_termin(abo: dict, faellig: date, *, mitte: float | None, rate: float,
                     police: Collection[str]) -> int:
    """Was die Mitzahler an diesem Termin erwartet zahlen: ihr Anteil laut Besetzung, wo es
    keinen angelegten Zeitraum gibt (`abos.erwartete_anteile`), positiv. Er steigt wie der
    Betrag am Vertrag (`vertragsbetrag`)."""
    anteil = _ab.erwartete_anteile(abo, faellig)
    if not anteil or mitte is None or abo["id"] in police:
        return anteil
    return wachstum.fortschreiben(anteil, mitte, wachstum.monatsmitte(faellig), rate)


def termine(abo: dict, pausen: Pausen, *, ab: date, bis: date) -> list[date]:
    """Die Termine im Fenster: ohne Kündigung, ohne Vorrat, ohne die Monate einer Pause."""
    return [t for t in _ab.termine(abo, ab=ab, bis=bis) if not _ab.ausgesetzt(pausen, t)]


def pausen(conn: sqlite3.Connection, klammern: Iterable, abos: Iterable[dict],
           ) -> dict[str, Pausen]:
    """Je Vertrag die Monate, in denen eine Wegfall-Zeile ihn aussetzt.

    Nennt eine eingeschaltete Wegfall-Zeile die Reihe eines Vertrags, setzt sie ihn aus: von
    ihrem Start bis zu ihrem Ende, bei einer einmaligen Zeile in dem einen Monat. Die
    Kuendigung am Vertrag gilt daneben; ein Termin faellt weg, wenn eines von beiden ihn
    trifft, und zaehlt so nie zweimal. Was die Zeile ausserdem nennt und der Vertrag nicht
    ersetzt (der Eingang eines Mitnutzers, der weiter gemessen wird), zieht sie selbst ab.
    Zeilen "nur Kontoprognose" lassen die Reihe weiter zahlen und gelten hier nicht.
    """
    zeilen = [line for s in _sz.active(list(klammern)) for line in s.lines
              if line.kind == "wegfall" and line.start and line.buchungen
              and not line.nur_kontoprognose]
    if not zeilen:
        return {}
    serien = {a["id"]: set(_reihe.hashes(conn, a["buchungen"], a["betrag_cents"]))
              for a in abos if a["buchungen"]}
    out: dict[str, list[tuple[date, date | None]]] = {}
    for line in zeilen:
        hashes = set(_reihe.hashes(conn, line.buchungen))
        for vertrag, serie in serien.items():
            if hashes & serie:
                bis = line.start if line.frequency == "einmalig" else line.end
                out.setdefault(vertrag, []).append((line.start.replace(day=1), bis))
    return {k: tuple(v) for k, v in out.items()}


def aus_der_messung(conn: sqlite3.Connection, abos: Iterable[dict]) -> set[str]:
    """Die Buchungen, die diese Verträge in der Messung ersetzen: ihre Reihen und die
    Zahlungen ihrer Mitzahler."""
    out: set[str] = set()
    for gruppe in _ab.ausschluesse(conn, list(abos)):
        out |= set(gruppe["dedup_hashes"])
    return out


def rueckzahlungen(conn: sqlite3.Connection, abo: dict, *, ab: date) -> list[tuple[date, int]]:
    """Was die Mitzahler des Vertrags noch schulden: (Monat, Betrag), im Einsammel-Monat.

    `ab` ist der erste offene Monat: ein verstrichener Einsammel-Monat rückt dorthin, das
    Geld wird ja weiter erwartet."""
    return [(r["monat"], r["cents"]) for r in _ab.rueckzahlungen(
        conn, [abo], abo["konto"], ab=ab, bis=date(9000, 1, 1))]
