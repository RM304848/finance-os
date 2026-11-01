"""Der Kontostand eines Kontos, dessen Export keinen Saldo traegt.

Sparkasse, Commerzbank und N26 liefern Umsaetze ohne Saldenspalte. Der Import
schreibt dann `0` als Anfang und die Summe der Datei als Ende in den Auszug
(`reconcile_basis = 'ohne_saldo'`) -- das sind keine Salden der Bank, und
niemand darf sie als Kontostand lesen.

Der Kontostand kommt stattdessen aus einem ANKER: ein Stand S am Tag A, den
der Nutzer einmal aus dem Online-Banking abschreibt (`balances.yaml`, von
`finctl init` und beim Speichern nach `balance_snapshots` gespiegelt). Von dort
rechnet diese Datei mit den gebuchten Umsaetzen vor und zurueck. Eine Stelle,
damit jeder Leser dieselbe Zahl sieht.

Ein Stand gilt am ENDE seines Tages: Umsaetze vom Tag A selbst stecken in S.
"""

from __future__ import annotations

import sqlite3
from datetime import date


def ohne_saldo(conn: sqlite3.Connection, konto: str) -> bool:
    """Liest dieses Konto Exporte ohne Saldo? Nach dem juengsten Auszug entschieden."""
    r = conn.execute(
        "SELECT reconcile_basis FROM statements WHERE account_id = ? AND status = 'imported' "
        "ORDER BY period_end DESC, rowid DESC LIMIT 1", (konto,)).fetchone()
    return bool(r and r[0] == "ohne_saldo")


def konten_ohne_saldo(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT account_id FROM statements WHERE status = 'imported'")
        if ohne_saldo(conn, r[0])}


def anker(conn: sqlite3.Connection, konto: str, tag: date) -> tuple[date, int] | None:
    """Der Stand, von dem aus `tag` gerechnet wird: der juengste bis `tag`, sonst der
    naechste danach. None, solange nichts eingetragen ist."""
    t = tag.isoformat()
    r = (conn.execute(
        "SELECT as_of, balance_cents FROM balance_snapshots WHERE account_id = ? AND as_of <= ? "
        "ORDER BY as_of DESC LIMIT 1", (konto, t)).fetchone()
        or conn.execute(
        "SELECT as_of, balance_cents FROM balance_snapshots WHERE account_id = ? AND as_of > ? "
        "ORDER BY as_of ASC LIMIT 1", (konto, t)).fetchone())
    return (date.fromisoformat(r[0][:10]), int(r[1])) if r else None


def braucht_anker(conn: sqlite3.Connection, konto: str) -> bool:
    """Ohne Saldo im Export und noch kein Stand eingetragen."""
    return ohne_saldo(conn, konto) and conn.execute(
        "SELECT 1 FROM balance_snapshots WHERE account_id = ?", (konto,)).fetchone() is None


def saldo_zum(conn: sqlite3.Connection, konto: str, tag: date) -> int | None:
    """Der Kontostand am Ende von `tag` -- None, solange kein Stand eingetragen ist.

    Liegt `tag` nach dem Anker, kommen die Umsaetze in (A, tag] dazu, liegt er davor,
    gehen die in (tag, A] ab.
    """
    a = anker(conn, konto, tag)
    if a is None:
        return None
    stand_am, cents = a
    von, bis, vorzeichen = ((stand_am, tag, 1) if tag >= stand_am else (tag, stand_am, -1))
    summe = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM transactions "
        "WHERE account_id = ? AND booking_date > ? AND booking_date <= ?",
        (konto, von.isoformat(), bis.isoformat())).fetchone()[0]
    return cents + vorzeichen * int(summe)
