"""Wo die Seite /reihen vorschlaegt, zwei Schreibweisen zusammenzufuehren.

Ein Vorschlag ist eng: Beide Reihen haben einen festen Takt, liegen in derselben
Kategorie, zahlen denselben Betrag, und die eine beginnt etwa einen Takt nach dem
letzten Termin der anderen. Alles hier ist erfunden und rund; gelesen wird ein
Hauptbuch im Speicher.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from finctl.forecast import takt as tk
from finctl.forecast import zusammenfuehren as zf

STICHTAG = date(2026, 9, 30)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE mgmt_categories (id TEXT PRIMARY KEY, kind TEXT,
                                      fixkosten INTEGER DEFAULT 0, einmalig INTEGER DEFAULT 0);
        CREATE TABLE transactions (id INTEGER PRIMARY KEY, account_id TEXT,
                                   booking_date TEXT, dedup_hash TEXT NOT NULL,
                                   counterparty_norm TEXT);
        CREATE TABLE splits (transaction_id INTEGER, mgmt_category_id TEXT,
                             amount_cents INTEGER, transfer_account_id TEXT,
                             property_id TEXT);
        INSERT INTO mgmt_categories (id, kind, fixkosten) VALUES
            ('wohnen/miete', 'expense', 1),
            ('versicherung/auto', 'expense', 1),
            ('wohnen/rundfunk', 'expense', 1),
            ('abo/sport', 'expense', 1),
            ('einkommen/gehalt', 'income', 0),
            ('konsum/essen', 'expense', 0);
    """)
    yield c
    c.close()


def _buche(c, tag, kategorie, cents, gegenpartei, konto="a"):
    n = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] + 1
    c.execute("INSERT INTO transactions VALUES (?, ?, ?, ?, ?)",
              (n, konto, tag.isoformat(), f"h{n}", gegenpartei))
    c.execute("INSERT INTO splits VALUES (?, ?, ?, NULL, NULL)", (n, kategorie, cents))


def _monate(erster: tuple[int, int], n: int, tag: int = 3) -> list[date]:
    index = erster[0] * 12 + erster[1] - 1
    return [date((index + i) // 12, (index + i) % 12 + 1, tag) for i in range(n)]


def _vorschlaege(conn, **kw):
    return zf.vorschlaege(tk.reihen(conn, bis=STICHTAG, **kw))


def _namen(vorschlaege) -> list[tuple[str, str]]:
    return [(v.alt.gegenpartei, v.neu.gegenpartei) for v in vorschlaege]


def test_a_series_that_ends_where_the_same_amount_begins_under_another_name_is_proposed(conn):
    for tag in _monate((2025, 9), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "verwaltung alt")
    for tag in _monate((2026, 3), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "verwaltung neu")
    [v] = _vorschlaege(conn)
    assert (v.alt.gegenpartei, v.neu.gegenpartei) == ("verwaltung alt", "verwaltung neu")
    assert v.abstand == (date(2026, 3, 3) - date(2026, 2, 3)).days


def test_one_booking_a_year_later_continues_a_yearly_payment(conn):
    _buche(conn, date(2025, 7, 24), "versicherung/auto", -7_200, "steuer alt")
    _buche(conn, date(2026, 7, 24), "versicherung/auto", -7_200, "steuer neu")
    assert _namen(_vorschlaege(conn)) == [("steuer alt", "steuer neu")]


def test_a_single_booking_continues_a_quarterly_series_whatever_its_own_takt_is(conn):
    """Die neue Reihe hat eine Buchung und gilt als jaehrlich, die alte zahlt alle drei
    Monate: Fuer den Abstand zaehlt der Takt der alten, die sich fortsetzt."""
    # Jeden dritten Monat bis Juni 2026, dann ein Termin im September unter dem neuen Namen.
    quartale = [date(2025, 3, 15), date(2025, 6, 15), date(2025, 9, 15), date(2025, 12, 15),
                date(2026, 3, 15), date(2026, 6, 15)]
    for tag in quartale:
        _buche(conn, tag, "wohnen/rundfunk", -5_500, "sender alt")
    _buche(conn, date(2026, 9, 15), "wohnen/rundfunk", -5_500, "sender neu")
    r = tk.reihen(conn, bis=STICHTAG)
    assert r.nach_schluessel("sender alt", "wohnen/rundfunk").takt == 3
    assert r.nach_schluessel("sender neu", "wohnen/rundfunk").takt == 12
    assert _namen(zf.vorschlaege(r)) == [("sender alt", "sender neu")]


def test_two_series_that_run_at_the_same_time_are_never_one_payment(conn):
    for tag in _monate((2025, 9), 12):
        _buche(conn, tag, "wohnen/miete", -90_000, "erste")
        _buche(conn, tag, "wohnen/miete", -90_000, "zweite")
    assert _vorschlaege(conn) == []


def test_another_amount_is_no_proposal(conn):
    for tag in _monate((2025, 9), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "verwaltung alt")
    for tag in _monate((2026, 3), 6):
        _buche(conn, tag, "wohnen/miete", -40_000, "verwaltung neu")
    assert _vorschlaege(conn) == []


def test_another_category_or_another_sign_is_no_proposal(conn):
    for tag in _monate((2025, 9), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "verwaltung alt")
    for tag in _monate((2026, 3), 6):
        _buche(conn, tag, "abo/sport", -90_000, "verwaltung neu")
    assert _vorschlaege(conn) == []
    conn.execute("DELETE FROM splits WHERE mgmt_category_id = 'abo/sport'")
    for tag in _monate((2026, 3), 6):
        _buche(conn, tag, "wohnen/miete", 90_000, "verwaltung neu")
    assert _vorschlaege(conn) == []


def test_a_gap_of_half_a_year_between_two_monthly_series_is_no_proposal(conn):
    for tag in _monate((2024, 11), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "verwaltung alt")
    for tag in _monate((2026, 1), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "verwaltung neu")
    assert _vorschlaege(conn) == []


def test_a_salary_with_the_month_in_its_name_is_not_flooded_with_proposals(conn):
    """Das Gehalt, dessen Name den Monat und das Jahr traegt: eine Schreibweise je
    Zahlung, jede mit einer Buchung. Keine hat einen festen Takt, also gibt es keinen
    Vorschlag, auch wenn die Betraege gleich sind."""
    for jahr in (2025, 2026):
        for monat in range(1, 10 if jahr == 2026 else 13):
            _buche(conn, date(jahr, monat, 28), "einkommen/gehalt", 450_000,
                   f"arbeitgeber gehalt {monat}{jahr}")
    r = tk.reihen(conn, bis=STICHTAG)
    assert len(r.reihen) == 21 and not any(x.fest for x in r.reihen)
    assert zf.vorschlaege(r) == []


def test_a_salary_with_the_month_in_its_name_and_two_years_is_not_flooded_either(conn):
    """Je Monat eine Schreibweise, in zwei Jahren je zwei Buchungen: Das sind zwoelf
    jaehrliche Reihen mit gleichem Betrag. Ihre Zeitraeume liegen ineinander, keine
    beginnt, wo eine andere aufhoert."""
    for monat in range(1, 10):
        for jahr in (2025, 2026):
            _buche(conn, date(jahr, monat, 28), "einkommen/gehalt", 450_000,
                   f"arbeitgeber gehalt {monat}")
    r = tk.reihen(conn, bis=STICHTAG)
    assert sum(1 for x in r.reihen if x.fest) == 9
    assert zf.vorschlaege(r) == []


def test_a_series_is_the_old_one_of_at_most_one_proposal_and_the_new_one_of_at_most_one(conn):
    """Zwei alte Schreibweisen laufen aus, eine neue beginnt: nur die naechste wird
    vorgeschlagen. Der Haushalt fuehrt die andere danach von Hand zu."""
    for tag in _monate((2025, 9), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "alt eins")
    for tag in _monate((2025, 9), 5):
        _buche(conn, tag, "wohnen/miete", -90_000, "alt zwei")
    for tag in _monate((2026, 3), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "neu")
    assert _namen(_vorschlaege(conn)) == [("alt eins", "neu")]


def test_a_chain_of_three_spellings_gives_two_proposals(conn):
    for tag in _monate((2025, 1), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "erste")
    for tag in _monate((2025, 7), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "zweite")
    for tag in _monate((2026, 1), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "dritte")
    assert _namen(_vorschlaege(conn)) == [("erste", "zweite"), ("zweite", "dritte")]


def test_a_merged_series_is_no_proposal_any_more(conn):
    for tag in _monate((2025, 9), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "verwaltung alt")
    for tag in _monate((2026, 3), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "verwaltung neu")
    assert _vorschlaege(conn, zusammen={"verwaltung alt": "verwaltung neu"}) == []


def test_a_series_the_household_set_to_irregular_has_nothing_to_propose(conn):
    """Ohne festen Takt kein Betrag je Termin, also nichts, was sich vergleichen liesse."""
    for tag in _monate((2025, 9), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "verwaltung alt")
    for tag in _monate((2026, 3), 6):
        _buche(conn, tag, "wohnen/miete", -90_000, "verwaltung neu")
    festgelegt = {("verwaltung neu", "wohnen/miete"): tk.UNREGELMAESSIG}
    assert _vorschlaege(conn, festgelegt=festgelegt) == []
