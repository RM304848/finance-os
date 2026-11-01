"""Der Rueckkaufswert einer Police: wie `balances` ihn liest. Alles erfunden.

Gerechnet wird damit noch nichts; hier steht nur, dass die drei Felder
ankommen, wo sie hingehoeren, und ein falsches Feld beim Lesen auffaellt.
"""

from __future__ import annotations

from datetime import date

import pytest

from finctl import bestaende as best
from finctl.ledger.db import connect, init_db

FELDER = {"rueckkauf_cents": 20_000_00, "rueckkauf_as_of": "2026-04-01",
          "eingezahlt_cents": 18_000_00}


def _police(**felder):
    return {"account_id": "police", "name": "Police", "kind": "rentenversicherung",
            "cents": 22_000_00, "as_of": "2026-04-01", **felder}


def test_a_policy_with_the_three_fields_has_a_surrender_value():
    assert best.rueckkauf(_police(**FELDER)) == best.Rueckkauf(
        cents=20_000_00, as_of=date(2026, 4, 1), eingezahlt_cents=18_000_00)


def test_a_yaml_date_reads_like_its_text():
    zeile = _police(**{**FELDER, "rueckkauf_as_of": date(2026, 4, 1)})
    assert best.rueckkauf(zeile).as_of == date(2026, 4, 1)


def test_a_policy_without_the_fields_has_none():
    assert best.rueckkauf(_police()) is None


def test_the_paid_in_sum_may_be_unknown():
    zeile = _police(**{**FELDER, "eingezahlt_cents": None})
    assert best.rueckkauf(zeile).eingezahlt_cents is None


def test_other_kinds_of_position_ignore_the_fields():
    assert best.rueckkauf({"kind": "depot", **FELDER}) is None


@pytest.mark.parametrize("felder", [
    {"rueckkauf_cents": None},                    # Datum und Summe ohne Betrag
    {"rueckkauf_as_of": None},                    # Betrag ohne Datum
    {"rueckkauf_cents": -1},
    {"eingezahlt_cents": -1},
    {"rueckkauf_cents": "viel"}])
def test_a_wrong_field_is_an_error_when_reading(felder):
    with pytest.raises(ValueError, match="Police"):
        best.rueckkauf(_police(**{**FELDER, **felder}))


@pytest.fixture
def conn(tmp_path):
    c = connect(init_db(tmp_path / "t.db"))
    yield c
    c.close()


def _zusammen(conn, felder):
    spec = {"as_of": date(2026, 9, 1), "balances": [
        {"account_id": "police", "name": "Police", "kind": "rentenversicherung",
         "cents": 22_000_00, "as_of": date(2026, 4, 1), **felder}]}
    [zeile] = best.zusammenfuehren(conn, spec)["balances"]
    return zeile


def test_the_file_carries_the_fields_through(conn):
    assert best.rueckkauf(_zusammen(conn, FELDER)).cents == 20_000_00


def test_a_new_surrender_value_replaces_the_fields_of_the_old_one(conn):
    zeile = _zusammen(conn, {**FELDER, "rueckkauf_cents": 21_000_00,
                             "rueckkauf_as_of": "2026-10-01"})
    r = best.rueckkauf(zeile)
    assert (r.cents, r.as_of, r.eingezahlt_cents) == (21_000_00, date(2026, 10, 1), 18_000_00)


def test_a_wrong_field_fails_while_merging(conn):
    with pytest.raises(ValueError, match="rueckkauf_as_of"):
        _zusammen(conn, {"rueckkauf_cents": 1})


def test_an_earlier_stichtag_does_not_borrow_todays_surrender_value(conn):
    """Der Rueckkaufswert galt zu seinem Datum, der Verlauf kennt nur den Stand."""
    spec = {"as_of": date(2026, 9, 1), "balances": [
        {"account_id": "police", "name": "Police", "kind": "rentenversicherung",
         "cents": 22_000_00, "as_of": date(2026, 4, 1), **FELDER}],
        "verlauf": {"police": {"2026": {"cents": 3_000_000, "as_of": "2026-04-01"}}}}
    [zeile] = best.zum(conn, date(2026, 8, 31), spec)["balances"]
    assert zeile["cents"] == 30_000_00
    assert best.rueckkauf(zeile) is None
