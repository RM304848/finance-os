"""Die Steigerung: Monatsmodell und Jahresrechnung rechnen sie gleich.

Gemessen ist ein Betrag zur Mitte des Messfensters. Die Jahresrechnung schreibt ihn
zur Mitte des Jahres fort, das Monatsmodell zur Mitte jedes Monats, beide mit
derselben Rechnung (`wachstum`). Policenbeitraege, Kreditraten und feste Betraege
bleiben flach.
"""

from __future__ import annotations

from datetime import date

import pytest

from finctl.forecast import konten as ops
from finctl.forecast import wachstum
from finctl.forecast.engine import RecurringItem
from finctl.ledger import db as ledger
from finctl.pfade import DB_PATH

RATE = 0.02
MITTE = wachstum.fenstermitte(date(2025, 10, 1), 12)


def test_the_middle_of_a_window_is_the_middle_of_its_months():
    assert wachstum.fenstermitte(date(2025, 10, 1), 12) == pytest.approx(2026.25)
    assert wachstum.fenstermitte(date(2026, 1, 1), 12) == pytest.approx(2026.5)


def test_the_twelve_months_of_a_year_have_the_middle_of_the_year_on_average():
    """Darum kommen beide Modelle ueber ein volles Jahr auf dieselbe Zahl."""
    mitten = [wachstum.monatsmitte(date(2028, m, 1)) for m in range(1, 13)]
    assert sum(mitten) / 12 == pytest.approx(wachstum.jahresmitte(2028))


@pytest.mark.parametrize("jahr", [2027, 2028, 2031])
def test_a_year_of_monthly_amounts_is_the_yearly_amount_of_the_hochrechnung(jahr):
    """Zwoelf Monate, je zur Monatsmitte fortgeschrieben, ergeben den Jahresbetrag, den die
    Jahresrechnung zur Jahresmitte fortschreibt -- bis auf die Rundung."""
    monat = -10_000
    item = RecurringItem(label="x", account_id="x", amount_cents=monat,
                         escalation_pa=RATE, mitte=MITTE)
    im_monatsmodell = sum(item.amount_in(date(jahr, m, 1)) for m in range(1, 13))
    in_der_jahresrechnung = wachstum.fortschreiben(
        12 * monat, MITTE, wachstum.jahresmitte(jahr), RATE)
    assert abs(im_monatsmodell - in_der_jahresrechnung) <= 12


def test_a_contract_rises_like_a_measured_series():
    abo = {"id": "strom", "betrag_cents": -5_000}
    erster = ops.vertragsbetrag(abo, date(2027, 1, 14), mitte=MITTE, rate=RATE,
                                police=frozenset())
    ein_jahr_spaeter = ops.vertragsbetrag(abo, date(2028, 1, 14), mitte=MITTE, rate=RATE,
                                          police=frozenset())
    assert erster == round(-5_000 * 1.02 ** (0.75 + 1 / 24))
    assert ein_jahr_spaeter == round(-5_000 * 1.02 ** (1.75 + 1 / 24))


def test_a_contract_that_feeds_a_police_stays_flat():
    abo = {"id": "rente", "betrag_cents": -30_000}
    assert ops.vertragsbetrag(abo, date(2031, 1, 14), mitte=MITTE, rate=RATE,
                              police=frozenset({"rente"})) == -30_000


def test_a_contract_without_a_measured_window_stays_as_the_contract_says():
    abo = {"id": "strom", "betrag_cents": -5_000}
    assert ops.vertragsbetrag(abo, date(2031, 1, 14), mitte=None, rate=RATE,
                              police=frozenset()) == -5_000


# ------------------------------------------------------------------ der Haushalt

kein_hauptbuch = pytest.mark.skipif(not DB_PATH.exists(), reason="kein Hauptbuch")


@pytest.fixture(scope="module")
def haushalt():
    conn = ledger.connect(DB_PATH)
    try:
        from finctl import ops as _ops

        yield conn, _ops.household_accounts(conn, months=_ops.HORIZON_LONG)
    finally:
        conn.close()


def _vertrag_je_monat(views: list[dict]) -> dict[str, dict[str, int]]:
    """Je Vertrag und Monat, was das Monatsmodell bucht."""
    out: dict[str, dict[str, int]] = {}
    for v in views:
        if v.get("error"):
            continue
        for row in v["rows"]:
            for label, cents in row["detail"].items():
                if label.startswith("abo:"):
                    out.setdefault(label, {})[row["month"]] = cents
    return out


@kein_hauptbuch
def test_a_monthly_contract_rises_by_the_inflation_in_a_year(haushalt):
    _, views = haushalt
    police = ops.police_vertraege()
    rate = ops.steigerung(None)
    monatlich = {k: m for k, m in _vertrag_je_monat(views).items()
                 if k.split(":", 1)[1] not in police and len(m) >= 48}
    if not monatlich:
        pytest.skip("kein Vertrag mit Zahlung in jedem Monat")
    for label, monate in monatlich.items():
        folge = sorted(monate)
        anfang, ein_jahr = monate[folge[0]], monate[folge[12]]
        # Gerundet auf den Cent: bei kleinen Betraegen zaehlt der halbe Cent mit.
        assert abs(ein_jahr - anfang * (1 + rate)) <= 1 + abs(anfang) * 1e-3, label


@kein_hauptbuch
def test_a_contract_that_feeds_a_police_stays_flat_in_the_forecast(haushalt):
    _, views = haushalt
    police = ops.police_vertraege()
    if not police:
        pytest.skip("keine Police mit Beitrag")
    beitraege = {label: monate for label, monate in _vertrag_je_monat(views).items()
                 if label.split(":", 1)[1] in police}
    if not beitraege:
        pytest.skip("kein Policenbeitrag im Horizont")
    for label, monate in beitraege.items():
        assert len(set(monate.values())) == 1, label
