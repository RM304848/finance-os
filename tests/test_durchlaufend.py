"""Durchlaufende Konten im Monatsmodell (Schritt 5b, E.2c).

Ein durchlaufendes Konto haelt kein Geld: Jede Zahlung deckt im selben Moment ein
anderes Konto. Seine Buchungen zaehlen im Monatsmodell auf dem Konto, das es deckt, mit
Fenster, Verfahren und Steigerung wie jeder andere Posten; die Umbuchung, die es
ausgleicht, zaehlt nicht noch einmal. Die Jahresrechnung misst sie seit jeher mit.

Alles hier ist erfunden und rund: drei Konten, Stichtag 31.08.2026. Die Tests schreiben
in einen Wegwerfordner, nie in `config/`.
"""

from __future__ import annotations

import hashlib
from datetime import date

import pytest

from finctl import reihen
from finctl.forecast import abgleich as ag
from finctl.forecast import jahre as jm
from finctl.forecast import konten as ops
from finctl.ledger.db import connect, init_db

HEUTE = date(2026, 9, 1)
FCFG = {"account_roles": {"pp": {"role": "durchlaufend"}}}

#: Was das durchlaufende Konto zahlt: unregelmaessig, damit es keine Reihe mit Takt wird,
#: und rund, damit die Monatsrate (Summe durch zwoelf) auf den Cent aufgeht.
ZAHLUNGEN = ((8, 9, -1_000), (9, 14, -2_000), (11, 3, -3_000), (12, 21, -1_500),
             (2, 8, -500), (4, 12, +900), (6, 30, -4_800), (7, 5, -100))


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Drei Konten (`a`, `b`, das durchlaufende `pp`), Auszuege von 07/2025 bis 08/2026."""
    (tmp_path / "config").mkdir()
    monkeypatch.setattr(reihen, "CONFIG_DIR", tmp_path / "config")
    c = connect(init_db(tmp_path / "t.db"))
    for konto in ("a", "b", "pp"):
        c.execute("INSERT INTO accounts (id, display_name, institution, account_type, "
                  "ingest_mode, parser_profile) VALUES (?,?,'X','giro','parsed','p')",
                  (konto, konto))
        for j, m in [(2025, k) for k in range(7, 13)] + [(2026, k) for k in range(1, 9)]:
            c.execute(
                "INSERT INTO statements (account_id, source_path, source_name, file_sha256, "
                "period_start, period_end, balance_start_cents, balance_end_cents, "
                "parser_profile, parser_version, status, imported_at) "
                "VALUES (?,'x','x',?,?,?,0,0,'p','1','imported','now')",
                (konto, f"{konto}{j}{m}", date(j, m, 1).isoformat(),
                 date(j, m, 28).isoformat()))
    for kennung, kind in (("konsum", "expense"), ("konsum/essen", "expense"),
                          ("konsum/kleidung", "expense"), ("transfer", "transfer"),
                          ("transfer/eigenkonto", "transfer")):
        c.execute("INSERT INTO mgmt_categories (id, parent_id, name, kind, fixkosten, "
                  "einmalig) VALUES (?,?,?,?,0,0)",
                  (kennung, kennung.split("/")[0] if "/" in kennung else None, kennung, kind))
    c.commit()
    yield c
    c.close()


def _buche(c, konto: str, tag: str, cents: int, kategorie: str, gegenpartei: str,
           gegenkonto: str | None = None) -> None:
    n = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] + 1
    sid = c.execute("SELECT id FROM statements WHERE account_id = ? AND period_start <= ? "
                    "ORDER BY period_start DESC", (konto, tag)).fetchone()[0]
    tid = c.execute(
        "INSERT INTO transactions (account_id, statement_id, booking_date, amount_cents, "
        "counterparty_norm, raw_text, seq_in_statement, dedup_hash, created_at) "
        "VALUES (?,?,?,?,?,'x',?,?,'now')",
        (konto, sid, tag, cents, gegenpartei, n,
         hashlib.sha256(f"buchung{n}".encode()).hexdigest())).lastrowid
    c.execute("INSERT INTO splits (transaction_id, amount_cents, mgmt_category_id, "
              "transfer_account_id, source, created_at, updated_at) "
              "VALUES (?,?,?,?,'rule','now','now')", (tid, cents, kategorie, gegenkonto))
    c.commit()


def _haushalt(c, deckendes: str = "a") -> None:
    """`a` zahlt 600 € im Monat fuer Essen und 240 € im Jahr fuer Kleidung; `pp` zahlt
    `ZAHLUNGEN` in Essen, und `deckendes` gleicht jede Zahlung am selben Tag aus."""
    for n, monat in enumerate([(2025, k) for k in range(8, 13)]
                              + [(2026, k) for k in range(1, 8)]):
        _buche(c, "a", f"{monat[0]}-{monat[1]:02d}-05", -60_000, "konsum/essen", "markt")
        if n == 4:
            _buche(c, "a", f"{monat[0]}-{monat[1]:02d}-20", -24_000, "konsum/kleidung", "laden")
    for monat, tag, cents in ZAHLUNGEN:
        jahr = 2025 if monat >= 8 else 2026
        datum = f"{jahr}-{monat:02d}-{tag:02d}"
        _buche(c, "pp", datum, cents, "konsum/essen", "dienst")
        # Die Deckung: auf beiden Seiten dieselbe Umbuchung, das Gegenkonto dazu.
        _buche(c, deckendes, datum, cents, "transfer/eigenkonto", "pp", "pp")
        _buche(c, "pp", datum, -cents, "transfer/eigenkonto", deckendes, deckendes)


def _jahreswert(c, kategorie: str) -> int:
    """Was die Jahresrechnung fuer die Kategorie misst: die Summe ihres Fensters."""
    basis = jm._base_kategorien(c, ag.fenster(c, bis=date(2026, 8, 31)), None)
    return sum(kat.get(kategorie, 0) for kat in basis.values())


def _im_jahr(posten: list, kategorie: str) -> int:
    return sum(p.amount_cents * 12 // p.every_months for p in posten
               if p.category == kategorie)


def test_the_covering_account_is_the_one_of_the_last_transfer(db):
    _haushalt(db, deckendes="a")
    assert ops.deckung_zum(db, FCFG, date(2026, 7, 31)) == {"pp": "a"}
    # Eine spaetere Umbuchung mit einem anderen Konto gewinnt, eine spaetere Erstattung auch.
    _buche(db, "b", "2026-07-20", -700, "transfer/eigenkonto", "pp", "pp")
    _buche(db, "pp", "2026-07-20", 700, "transfer/eigenkonto", "b", "b")
    assert ops.deckung_zum(db, FCFG, date(2026, 7, 31)) == {"pp": "b"}
    # Zum Stichtag davor galt noch das alte.
    assert ops.deckung_zum(db, FCFG, date(2026, 7, 19)) == {"pp": "a"}


def test_a_pass_through_account_without_a_transfer_covers_nothing(db):
    _buche(db, "pp", "2026-07-03", -500, "konsum/essen", "dienst")
    assert ops.deckung_zum(db, FCFG, date(2026, 7, 31)) == {}
    assert ops.deckung_zum(db, {}, date(2026, 7, 31)) == {}


def test_its_bookings_count_on_the_covering_account_and_not_on_its_own(db):
    _haushalt(db)
    assert ops.abgeleitete_posten(db, "pp", FCFG, [], stichtag=HEUTE) == []
    nachher = ops.abgeleitete_posten(db, "a", FCFG, [], stichtag=HEUTE)
    # Die Reihe von `a` (600 € im Monat) und, daneben im Rest, die Zahlungen des Dienstes
    # (ihre Summe durch zwoelf).
    assert sorted(p.amount_cents for p in nachher if p.category == "konsum/essen") == [
        -60_000, sum(c for _, _, c in ZAHLUNGEN) // 12]
    # Die Deckung zaehlt nicht: weder als Ausgabe von `a` noch als Einnahme von `pp`.
    assert not [p for p in nachher if p.category.startswith("transfer/")]
    assert ops.abgeleitete_posten(db, "b", FCFG, [], stichtag=HEUTE) == []


def test_the_sum_over_all_accounts_is_what_the_jahresrechnung_measures(db):
    """Dieselben Buchungen, dasselbe Fenster, dieselbe Summe: Das Monatsmodell zaehlt die
    Zahlungen des durchlaufenden Kontos weder doppelt (Ausgabe und Deckung) noch gar nicht."""
    _haushalt(db)
    # Die Konten, die `household_accounts` projiziert: das durchlaufende fehlt.
    posten = [p for konto in ("a", "b")
              for p in ops.abgeleitete_posten(db, konto, FCFG, [], stichtag=HEUTE)]
    for kategorie in ("konsum/essen", "konsum/kleidung"):
        assert _im_jahr(posten, kategorie) == _jahreswert(db, kategorie) != 0, kategorie
    # Ohne die Zuordnung fehlten die Zahlungen des Dienstes: die Rechnung vor E.2c.
    ohne = [p for konto in ("a", "b")
            for p in ops.abgeleitete_posten(db, konto, {}, [], stichtag=HEUTE)]
    assert _im_jahr(ohne, "konsum/essen") != _jahreswert(db, "konsum/essen")


def test_the_treffer_check_and_the_forecast_see_the_same_account(db):
    """`Ist` und `Soll` des Treffer-Checks messen beide mit der Zuordnung."""
    from finctl.forecast import messung, treffer

    _haushalt(db)
    ist = treffer._ist_je_konto(db, date(2026, 7, 1), ["a", "b"], {"pp": "a"})
    assert sum(z.cents for z in ist["a"] if z.kategorie == "konsum/essen") == -60_000 - 100
    assert "pp" not in ist
    ohne = messung.monatssummen(
        db, von=date(2026, 7, 1), bis=date(2026, 7, 31), konten=frozenset({"a", "b"}),
        ausschluss=messung.Ausschluss(umbuchung="beide"))
    assert sum(z.cents for z in ohne if z.kategorie == "konsum/essen") == -60_000
