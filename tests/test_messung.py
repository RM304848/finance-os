"""Die eine Messung: je Feld des Ausschlusses ein Fall, der genau eine Buchung
hinein- oder herausnimmt. Ein Hauptbuch im Speicher, alles erfunden."""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from finctl.forecast.messung import Ausschluss, Monatssumme, Teil, monatssummen, summiere, teile


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
            ('einkommen/gehalt', 'income', 0),
            ('konsum/essen', 'expense', 0),
            ('transfer/eigenkonto', 'transfer', 0),
            ('konsum/umschichtung', 'transfer', 0);
    """)
    yield c
    c.close()


def _buche(c, tag, konto, kategorie, cents, *, hash_=None, ziel=None, gegenpartei=None,
           objekt=None):
    n = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] + 1
    c.execute("INSERT INTO transactions VALUES (?, ?, ?, ?, ?)",
              (n, konto, tag, hash_ or f"h{n}", gegenpartei))
    c.execute("INSERT INTO splits VALUES (?, ?, ?, ?, ?)",
              (n, kategorie, cents, ziel, objekt))


def _summen(zeilen):
    return {(z.konto, z.kategorie, z.monat): z.cents for z in zeilen}


def test_sums_per_account_category_and_month_sorted(conn):
    _buche(conn, "2026-02-03", "b", "konsum/essen", -300)
    _buche(conn, "2026-01-05", "a", "konsum/essen", -100)
    _buche(conn, "2026-01-20", "a", "konsum/essen", -50)
    _buche(conn, "2026-01-21", "a", "einkommen/gehalt", 5000)
    zeilen = monatssummen(conn, von="2026-01-01")
    assert zeilen == [
        Monatssumme("a", "einkommen/gehalt", None, "2026-01", 5000),
        Monatssumme("a", "konsum/essen", None, "2026-01", -150),
        Monatssumme("b", "konsum/essen", None, "2026-02", -300),
    ]


def test_von_and_bis_are_inclusive_and_bis_may_be_open(conn):
    for tag in ("2025-12-31", "2026-01-01", "2026-01-31", "2026-02-01"):
        _buche(conn, tag, "a", "konsum/essen", -100)
    assert _summen(monatssummen(conn, von=date(2026, 1, 1), bis=date(2026, 1, 31))) == {
        ("a", "konsum/essen", "2026-01"): -200}
    assert _summen(monatssummen(conn, von="2026-01-01")) == {
        ("a", "konsum/essen", "2026-01"): -200, ("a", "konsum/essen", "2026-02"): -100}


def test_konten_limits_the_accounts_and_none_takes_all(conn):
    _buche(conn, "2026-01-05", "a", "konsum/essen", -100)
    _buche(conn, "2026-01-05", "b", "konsum/essen", -200)
    assert {z.konto for z in monatssummen(conn, von="2026-01-01")} == {"a", "b"}
    assert {z.konto for z in monatssummen(
        conn, von="2026-01-01", konten=frozenset({"b"}))} == {"b"}


def test_praefix_drops_by_category_prefix_not_by_kind(conn):
    _buche(conn, "2026-01-05", "a", "konsum/essen", -100)
    _buche(conn, "2026-01-05", "a", "transfer/eigenkonto", -700)
    _buche(conn, "2026-01-05", "a", "konsum/umschichtung", -900)
    assert _summen(monatssummen(conn, von="2026-01-01")) == {
        ("a", "konsum/essen", "2026-01"): -100,
        ("a", "konsum/umschichtung", "2026-01"): -900}


def test_art_drops_by_kind_not_by_prefix(conn):
    """Eine Kategorie mit Art `transfer` ausserhalb von `transfer/` faellt hier
    heraus, eine mit dem Praefix und anderer Art nicht."""
    _buche(conn, "2026-01-05", "a", "konsum/essen", -100)
    _buche(conn, "2026-01-05", "a", "transfer/eigenkonto", -700)
    _buche(conn, "2026-01-05", "a", "konsum/umschichtung", -900)
    conn.execute("UPDATE mgmt_categories SET kind = 'expense' "
                 "WHERE id = 'transfer/eigenkonto'")
    assert _summen(monatssummen(
        conn, von="2026-01-01", ausschluss=Ausschluss(umbuchung="art"))) == {
        ("a", "konsum/essen", "2026-01"): -100,
        ("a", "transfer/eigenkonto", "2026-01"): -700}


def test_beide_drops_by_prefix_and_by_kind(conn):
    """Die dritte Regel: Praefix UND Art. Eine Kategorie faellt heraus, wenn eine
    der beiden Regeln sie erkennt."""
    _buche(conn, "2026-01-05", "a", "konsum/essen", -100)
    _buche(conn, "2026-01-05", "a", "transfer/eigenkonto", -700, ziel="paypal")
    _buche(conn, "2026-01-05", "a", "konsum/umschichtung", -900)
    conn.execute("UPDATE mgmt_categories SET kind = 'expense' "
                 "WHERE id = 'transfer/eigenkonto'")
    beide = Ausschluss(umbuchung="beide")
    assert _summen(monatssummen(conn, von="2026-01-01", ausschluss=beide)) == {
        ("a", "konsum/essen", "2026-01"): -100}


def test_umbuchungen_zaehlen_takes_the_transfers_back_in(conn):
    _buche(conn, "2026-01-05", "a", "konsum/essen", -100)
    _buche(conn, "2026-01-05", "a", "transfer/eigenkonto", 400)
    art = Ausschluss(umbuchung="art")
    assert ("a", "transfer/eigenkonto", "2026-01") not in _summen(
        monatssummen(conn, von="2026-01-01", ausschluss=art))
    zaehlen = Ausschluss(umbuchung="art", umbuchungen_zaehlen=True)
    assert _summen(monatssummen(conn, von="2026-01-01", ausschluss=zaehlen))[
        ("a", "transfer/eigenkonto", "2026-01")] == 400


def test_a_pass_through_account_is_booked_on_the_account_that_covers_it(conn):
    """Das durchlaufende Konto gibt es danach nicht mehr: Seine Buchungen stehen auf dem
    deckenden Konto, und die Umbuchung, die es ausgleicht, zaehlt auf keinem von beiden."""
    _buche(conn, "2026-01-05", "a", "konsum/essen", -100)
    _buche(conn, "2026-01-06", "paypal", "konsum/essen", -4000)
    _buche(conn, "2026-01-06", "a", "transfer/eigenkonto", -4000, ziel="paypal")
    _buche(conn, "2026-01-06", "paypal", "transfer/eigenkonto", 4000, ziel="a")
    _buche(conn, "2026-01-07", "a", "transfer/eigenkonto", -50000, ziel="sparbuch")
    ohne = Ausschluss(umbuchung="art")
    mit = Ausschluss(umbuchung="art", deckung=(("paypal", "a"),))
    assert _summen(monatssummen(conn, von="2026-01-01", ausschluss=ohne)) == {
        ("a", "konsum/essen", "2026-01"): -100, ("paypal", "konsum/essen", "2026-01"): -4000}
    assert _summen(monatssummen(conn, von="2026-01-01", ausschluss=mit)) == {
        ("a", "konsum/essen", "2026-01"): -4100}
    assert _summen(monatssummen(conn, von="2026-01-01", ausschluss=mit,
                                konten=frozenset({"a"}))) == {
        ("a", "konsum/essen", "2026-01"): -4100}
    assert monatssummen(conn, von="2026-01-01", ausschluss=mit,
                        konten=frozenset({"paypal"})) == []
    assert [t.konto for t in teile(conn, von="2026-01-01", ausschluss=mit)] == ["a", "a"]


def test_ohne_kategorie_decides_where_uncategorised_parts_go(conn):
    _buche(conn, "2026-01-05", "a", "konsum/essen", -100)
    _buche(conn, "2026-01-06", "a", None, -250)
    assert _summen(monatssummen(conn, von="2026-01-01")) == {
        ("a", "", "2026-01"): -250, ("a", "konsum/essen", "2026-01"): -100}
    streng = Ausschluss(umbuchung="art", ohne_kategorie=False)
    assert _summen(monatssummen(conn, von="2026-01-01", ausschluss=streng)) == {
        ("a", "konsum/essen", "2026-01"): -100}


def test_hashes_take_single_bookings_out(conn):
    _buche(conn, "2026-01-05", "a", "konsum/essen", -100, hash_="weg")
    _buche(conn, "2026-01-06", "a", "konsum/essen", -40, hash_="bleibt")
    ausschluss = Ausschluss(hashes=frozenset({"weg", "gibt-es-nicht"}))
    assert _summen(monatssummen(conn, von="2026-01-01", ausschluss=ausschluss)) == {
        ("a", "konsum/essen", "2026-01"): -40}


def test_je_block_adds_the_block_and_otherwise_it_stays_none(conn):
    _buche(conn, "2026-01-05", "a", "einkommen/gehalt", 5000)
    _buche(conn, "2026-01-06", "a", "konsum/essen", -100)
    assert {z.block for z in monatssummen(conn, von="2026-01-01")} == {None}
    blocks = {z.kategorie: z.block
              for z in monatssummen(conn, von="2026-01-01", je_block=True)}
    assert blocks == {"einkommen/gehalt": "gehalt", "konsum/essen": "konsum"}


def test_summiere_keeps_zero_sums(conn):
    _buche(conn, "2026-01-05", "a", "konsum/essen", -100)
    _buche(conn, "2026-01-06", "a", "konsum/essen", 100)
    zeilen = monatssummen(conn, von="2026-01-01")
    assert summiere(zeilen, lambda z: z.kategorie) == {"konsum/essen": 0}
    assert summiere(zeilen, lambda z: z.monat) == {"2026-01": 0}


# ----------------------------------------------------------------- teile


def _alle_faelle(c) -> None:
    """Je Umbuchungsregel und Ausschlussfeld eine Buchung, die hinein- oder
    herausfaellt, und eine Buchung mit zwei Teilen derselben Kategorie."""
    _buche(c, "2026-01-05", "a", "konsum/essen", -100, gegenpartei="markt")
    _buche(c, "2026-01-20", "a", "konsum/essen", -250, gegenpartei="markt")
    _buche(c, "2026-02-03", "b", "einkommen/gehalt", 5000, gegenpartei="firma")
    _buche(c, "2026-02-04", "a", "transfer/eigenkonto", -700, ziel="paypal")
    _buche(c, "2026-02-05", "a", "transfer/eigenkonto", -9000, ziel="sparbuch")
    _buche(c, "2026-02-06", "a", "konsum/umschichtung", -900)
    _buche(c, "2026-02-07", "a", None, -40, gegenpartei="kiosk")
    _buche(c, "2026-03-01", "b", "konsum/essen", -75, hash_="roh", gegenpartei="markt")
    _buche(c, "2026-03-02", "paypal", "konsum/essen", -60, gegenpartei="markt")
    c.execute("INSERT INTO splits VALUES (1, 'konsum/essen', -5, NULL, NULL)")
    c.execute("UPDATE mgmt_categories SET kind = 'expense' "
              "WHERE id = 'transfer/eigenkonto'")


FAELLE = {
    "praefix": Ausschluss(),
    "art": Ausschluss(umbuchung="art"),
    "art_zaehlen": Ausschluss(umbuchung="art", umbuchungen_zaehlen=True),
    "art_deckung": Ausschluss(umbuchung="art", deckung=(("paypal", "b"),)),
    "beide": Ausschluss(umbuchung="beide", deckung=(("paypal", "b"),)),
    "ohne_kategorie": Ausschluss(ohne_kategorie=False),
    "hashes": Ausschluss(hashes=frozenset({"roh"})),
}


@pytest.mark.parametrize("name", sorted(FAELLE))
@pytest.mark.parametrize("konten", [None, frozenset({"b"})])
def test_the_parts_add_up_to_the_monthly_sums_for_every_rule(conn, name, konten):
    """Eine Abfrage, zwei Formen: `summiere` ueber die Teile je Monat ergibt
    genau `monatssummen`."""
    _alle_faelle(conn)
    ausschluss = FAELLE[name]
    gemessen = {(z.konto, z.kategorie, z.monat): z.cents for z in monatssummen(
        conn, von="2026-01-01", ausschluss=ausschluss, konten=konten)}
    aus_teilen = summiere(
        teile(conn, von="2026-01-01", ausschluss=ausschluss, konten=konten),
        lambda t: (t.konto, t.kategorie, t.monat))
    assert aus_teilen == gemessen
    assert gemessen


def test_the_parts_respect_von_and_bis_and_the_block(conn):
    _alle_faelle(conn)
    alle = teile(conn, von=date(2026, 1, 20), bis=date(2026, 2, 3))
    assert [t.tag for t in alle] == [date(2026, 1, 20), date(2026, 2, 3)]
    assert all(t.block is None for t in alle)


def test_a_part_carries_account_category_day_amount_counterparty_and_hash(conn):
    _buche(conn, "2026-01-05", "a", "konsum/essen", -100, hash_="eins", gegenpartei="markt")
    _buche(conn, "2026-01-06", "a", None, -40)
    assert teile(conn, von="2026-01-01") == [
        Teil("a", "konsum/essen", None, date(2026, 1, 5), -100, "markt", "eins"),
        Teil("a", "", None, date(2026, 1, 6), -40, "", "h2")]
    assert teile(conn, von="2026-01-01")[0].monat == "2026-01"


def test_a_booking_with_two_parts_gives_two_parts(conn):
    """Die Buchung zaehlt in `monatssummen` einmal, ihre Teile in `teile` je Teil."""
    _buche(conn, "2026-01-05", "a", "konsum/essen", -100, gegenpartei="markt")
    conn.execute("INSERT INTO splits VALUES (1, 'konsum/essen', -20, NULL, NULL)")
    assert sorted(t.cents for t in teile(conn, von="2026-01-01")) == [-100, -20]
    [summe] = monatssummen(conn, von="2026-01-01")
    assert (summe.cents, summe.buchungen) == (-120, 1)


def test_the_parts_come_in_a_fixed_order(conn):
    _buche(conn, "2026-02-03", "b", "konsum/essen", -300)
    _buche(conn, "2026-01-05", "a", "konsum/essen", -100)
    _buche(conn, "2026-01-05", "a", "konsum/essen", -50)
    assert [(t.tag.isoformat(), t.cents) for t in teile(conn, von="2026-01-01")] == [
        ("2026-01-05", -100), ("2026-01-05", -50), ("2026-02-03", -300)]


def test_objekte_drops_every_part_of_those_objects_in_every_category(conn):
    """Ein Objekt mit Prognose misst die Kontoprognose nicht, in keiner Kategorie; ein Teil
    ohne Objekt und eines eines anderen Objekts bleiben."""
    _buche(conn, "2026-01-05", "a", "immobilie/mieteinnahme", 90_000, objekt="haus")
    _buche(conn, "2026-01-06", "a", "konsum/essen", -2_000, objekt="haus")
    _buche(conn, "2026-01-07", "a", "immobilie/mieteinnahme", 50_000, objekt="anderes")
    _buche(conn, "2026-01-08", "a", "konsum/essen", -1_000)
    gemessen = _summen(monatssummen(
        conn, von="2026-01-01", ausschluss=Ausschluss(objekte=frozenset({"haus"}))))
    assert gemessen == {("a", "immobilie/mieteinnahme", "2026-01"): 50_000,
                        ("a", "konsum/essen", "2026-01"): -1_000}
    ohne = teile(conn, von="2026-01-01", ausschluss=Ausschluss(objekte=frozenset({"haus"})))
    assert sorted(t.cents for t in ohne) == [-1_000, 50_000]
    assert sum(z.cents for z in monatssummen(conn, von="2026-01-01")) == 137_000
