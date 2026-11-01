"""Zinsen und Steuer darauf: beide Modelle rechnen dasselbe (Schritt 5b, E.6).

Der Paritaetstest (`test_paritaet.py`) vergleicht `zinsen` nicht: Die Jahresrechnung
verzinst den Topf nach der Kaskade, der Stand ist ihr Ergebnis und keine Eingabe, das
Monatsmodell verzinst den Stand, den es selbst vorausrechnet. Beide Staende laufen
auseinander, auch wenn die Regel dieselbe ist.

Hier steht, dass sie dieselbe ist: Bei gleichem Stand und gleichem Satz ergeben ein volles
Jahr des Monatsmodells (`engine.project` mit `zinsen.steuerplan`) und die Jahresrechnung
(`jahre.kaskade` mit `zinsen.mischung`) denselben Zins und dieselbe Steuer, bis auf
Rundung. Der Stand bleibt dafuer das ganze Jahr gleich: Ein Konto, dessen Deckel auf dem
Anfangsstand liegt, raeumt jeden Monat ab, was dazukommt.

Dazu: Der Freibetrag gilt fuer den Haushalt und nicht je Konto, die Steuer faellt erst,
wenn die Zinsen des Jahres ihn uebersteigen, und im Lauf ueber den Haushalt der Daten
steht der Zins eines Monats auf dem Stand zu seinem Beginn -- gemessene Zinsen zaehlen
nicht.

Alles Rechnen hier ist mit erfundenen, runden Staenden.
"""

from __future__ import annotations

from datetime import date

import pytest

from finctl import assumptions as ann
from finctl import bestaende, ops
from finctl import zinssaetze as zs
from finctl.forecast import engine
from finctl.forecast import jahre as jm
from finctl.forecast import zinsen as zn
from finctl.forecast.verfahren import add_months
from finctl.ledger import db as ledger
from finctl.pfade import DB_PATH

#: Bis auf Rundung: Jeder Monat rundet seinen Zins auf den Cent, zwoelf Monate also hoechstens
#: sechs Cent gegen die eine Rundung der Jahresrechnung; die Steuer darauf hoechstens zwei.
RUNDUNG_ZINS = 6
RUNDUNG_STEUER = 2

PAUSCHBETRAG = 1_000_00
QUOTE = 0.26375
LANGFRISTIG = 0.02


def _monatsmodell(konten: dict[str, tuple[int, list[zn.Zinssatz]]], erster: date,
                  monate: int) -> tuple[dict, dict]:
    """(Zinsen, Steuer) je Konto und Monat: jedes Konto auf gleichem Stand gehalten, die Steuer
    aus den Zinsen aller Konten."""
    def lauf(konto: str, plan: dict) -> engine.Projection:
        stand, saetze = konten[konto]
        return engine.project(
            account_id=konto, opening_cents=stand, start=erster, months=monate,
            recurring=[], sweep_above_cents=stand,
            satz=lambda wann: zn.satz_im_monat(saetze, "tagesgeld", wann, LANGFRISTIG),
            steuer={m: c for (k, m), c in plan.items() if k == konto})

    ohne = {k: lauf(k, {}) for k in konten}
    zinsen = {(k, r.month): r.detail[zn.ZINSEN] for k, p in ohne.items()
              for r in p.rows if zn.ZINSEN in r.detail}
    plan = zn.steuerplan(zinsen, pauschbetrag=PAUSCHBETRAG, steuer_quote=QUOTE,
                         erster_monat=erster)
    mit = {k: lauf(k, plan) for k in konten}
    # Der Stand bleibt gleich, also aendert die Steuer den Zins nicht.
    assert {(k, r.month): r.detail.get(zn.ZINSEN) for k, p in mit.items()
            for r in p.rows if zn.ZINSEN in r.detail} == zinsen
    return zinsen, {(k, r.month): -r.detail[zn.KAPITALERTRAGSTEUER]
                    for k, p in mit.items() for r in p.rows
                    if zn.KAPITALERTRAGSTEUER in r.detail}


def _jahresrechnung(konten: dict[str, tuple[int, list[zn.Zinssatz]]], erster: date,
                    monate: int) -> dict[str, int]:
    """Die Kaskade des Jahres mit dem Satz, den der Topf aus seinen Konten mischt."""
    liste = [add_months(erster, i) for i in range(monate)]
    mix = zn.mischung({k: zn.Konto("tagesgeld", stand) for k, (stand, _) in konten.items()},
                      {k: saetze for k, (_, saetze) in konten.items()}, liste, LANGFRISTIG)
    return jm.kaskade(
        sum(stand for stand, _ in konten.values()), 0, 0, sparrate=0, grenze=2**62,
        satz_tagesgeld=mix.satz, satz_depot=0.0, vorab_satz=0.0, steuer_quote=QUOTE,
        pauschbetrag=PAUSCHBETRAG, anteil=monate / 12)


def _satz(prozent: float, ab: date = date(2029, 1, 1), bis: date | None = None) -> zn.Zinssatz:
    return zn.Zinssatz(ab=ab, bis=bis, satz=prozent)


#: (Name, Konten mit Stand und Saetzen, erster Monat, Monate). Ein volles Jahr rechnet zwoelf
#: Monate ab Januar; das erste Jahr der Projektion nur seine Restmonate.
FAELLE = {
    "unter dem Freibetrag": ({"a": (20_000_00, [_satz(0.02)])}, date(2030, 1, 1), 12),
    "ueber dem Freibetrag": ({"a": (100_000_00, [_satz(0.03)])}, date(2030, 1, 1), 12),
    "Satz wechselt im Jahr": (
        {"a": (100_000_00, [_satz(0.02, bis=date(2030, 6, 1)),
                            _satz(0.04, ab=date(2030, 7, 1))])}, date(2030, 1, 1), 12),
    "zwei Konten teilen den Freibetrag": (
        {"a": (60_000_00, [_satz(0.03)]), "b": (40_000_00, [_satz(0.03)])},
        date(2030, 1, 1), 12),
    "zwei Konten mit verschiedenem Satz": (
        {"a": (60_000_00, [_satz(0.04)]), "b": (40_000_00, [_satz(0.02)])},
        date(2030, 1, 1), 12),
    "erstes Jahr nur die Restmonate": (
        {"a": (400_000_00, [_satz(0.03)])}, date(2030, 10, 1), 3),
}


@pytest.mark.parametrize("fall", sorted(FAELLE))
def test_both_models_charge_the_same_interest_and_tax_over_a_year(fall):
    konten, erster, monate = FAELLE[fall]
    zinsen, steuer = _monatsmodell(konten, erster, monate)
    kaskade = _jahresrechnung(konten, erster, monate)
    assert abs(sum(zinsen.values()) - kaskade["zins_tagesgeld"]) <= RUNDUNG_ZINS, fall
    assert abs(sum(steuer.values()) - kaskade["zinssteuer"]) <= RUNDUNG_STEUER, fall


def test_the_tax_falls_when_the_interest_of_the_year_pass_the_allowance():
    """100.000 € zu 3 % sind 250 € im Monat; der Freibetrag von 1.000 € ist nach vier Monaten
    verbraucht. Die Steuer faellt vom fuenften Monat an, mit dem vollen Satz auf den Zins."""
    konten = {"a": (100_000_00, [_satz(0.03)])}
    zinsen, steuer = _monatsmodell(konten, date(2030, 1, 1), 12)
    assert {m.month for _, m in steuer} == set(range(5, 13))
    assert steuer[("a", date(2030, 5, 1))] == round(250_00 * QUOTE)
    assert steuer[("a", date(2030, 12, 1))] == round(250_00 * QUOTE)
    assert sum(zinsen.values()) == 3_000_00


def test_the_allowance_is_one_for_the_household_and_not_one_per_account():
    """Zwei Konten mit je 30.000 € zu 3 % tragen je 900 € Zinsen im Jahr, zusammen 1.800 €. Mit
    einem Freibetrag je Konto waere die Steuer null, mit einem fuer den Haushalt faellt sie auf
    die 800 € darueber."""
    konten = {"a": (30_000_00, [_satz(0.03)]), "b": (30_000_00, [_satz(0.03)])}
    zinsen, steuer = _monatsmodell(konten, date(2030, 1, 1), 12)
    assert sum(zinsen.values()) == 1_800_00
    assert abs(sum(steuer.values()) - round(800_00 * QUOTE)) <= RUNDUNG_STEUER
    assert not _monatsmodell({"a": konten["a"]}, date(2030, 1, 1), 12)[1], (
        "ein Konto allein bleibt unter dem Freibetrag")
    # Beide zahlen im selben Monat gleich viel, bis auf den einen Cent, der beim Teilen bleibt.
    for (konto, wann), cents in steuer.items():
        assert abs(cents - steuer[("b" if konto == "a" else "a", wann)]) <= 1, wann


def test_the_split_between_accounts_loses_no_cent():
    teil = zn._teilen(1_001, {"a": 1, "b": 1, "c": 1})
    assert sum(teil.values()) == 1_001
    assert sorted(teil.values()) == [333, 334, 334]
    assert zn._teilen(2, {"b": 1, "a": 1}) == {"a": 1, "b": 1}


def test_a_balance_that_a_clause_empties_earns_less_from_that_month_on():
    """Leert eine Klammer das Konto, sinkt der Zins von selbst: Er steht auf dem Stand zu
    Monatsbeginn, nicht auf einem Wert, der einmal gemessen wurde."""
    saetze = [_satz(0.03)]
    abgang = engine.OneOff(label="Autokauf", account_id="a", month=date(2030, 4, 1),
                           amount_cents=-60_000_00, day=10)

    def zinsen(einmal: list) -> list[int]:
        projektion = engine.project(
            account_id="a", opening_cents=100_000_00, start=date(2030, 1, 1), months=8,
            recurring=[], one_offs=einmal,
            satz=lambda wann: zn.satz_im_monat(saetze, "tagesgeld", wann, LANGFRISTIG))
        return [r.detail.get(zn.ZINSEN, 0) for r in projektion.rows]

    ohne, mit = zinsen([]), zinsen([abgang])
    assert mit[:4] == ohne[:4], "bis zum Abgang gleich: Der Stand zu Monatsbeginn zaehlt"
    assert mit[4] < 0.5 * ohne[4], "ab dem Folgemonat auf dem kleineren Stand"
    assert mit[3] == ohne[3], "der Abgang im April mindert den April nicht"


def test_a_balance_below_zero_earns_nothing():
    assert zn.zins_im_monat(-5_000_00, 0.03) == 0
    assert zn.zins_im_monat(0, 0.03) == 0


def test_interest_is_stand_times_rate_over_twelve():
    assert zn.zins_im_monat(120_000_00, 0.03) == 300_00
    assert zn.zins_im_monat(100_00, 0.0) == 0


# ------------------------------------------------------------------ der Haushalt der Daten

braucht_daten = pytest.mark.skipif(not DB_PATH.exists(), reason="kein Hauptbuch")


@pytest.fixture(scope="module")
def haushalt():
    conn = ledger.connect(DB_PATH)
    try:
        return ops.household_accounts(conn, months=ops.HORIZON_LONG)
    finally:
        conn.close()


@braucht_daten
def test_the_interest_of_a_month_is_the_balance_at_its_start_times_the_rate(haushalt):
    """Jedes Konto der Daten: Zins = round(Stand zu Monatsbeginn x Satz / 12), mit dem Satz aus
    den Zinssaetzen und der Art des Kontos aus `kind` in balances.yaml -- nichts gemessen."""
    saetze = zs.lesen()
    art = {str(p.get("account_id") or p.get("name") or ""): (p.get("kind") or "").lower()
           for p in bestaende.lesen().get("balances") or []}
    langfristig = ann.rendite_nominal_pa()
    geprueft = 0
    for view in haushalt:
        if view.get("error"):
            continue
        konto = view["id"]
        verzinst = bool(saetze.get(konto)) or art.get(konto) == zn.VERZINST
        for row in view["rows"]:
            wann = date.fromisoformat(row["month"])
            soll = (zn.zins_im_monat(row["opening_cents"],
                                     zn.satz_im_monat(saetze.get(konto, ()), art.get(konto, ""),
                                                      wann, langfristig))
                    if verzinst else 0)
            assert row["detail"].get(zn.ZINSEN, 0) == soll, (konto, row["month"])
            geprueft += soll > 0
    if not geprueft:
        pytest.skip("kein Konto der Daten verdient Zinsen")


@braucht_daten
def test_the_tax_of_a_year_is_the_tax_of_the_annual_interest(haushalt):
    """Ueber alle Konten eines vollen Kalenderjahrs: Steuer = (Zinsen - Freibetrag) x Satz, wie
    die Jahresrechnung sie auf die Jahressumme rechnet -- bis auf die Cent, die der Lauf der
    Steuer in den Zinsen des Folgemonats laesst."""
    _, quote = ann.vorabpauschale()
    freibetrag = ann.sparerpauschbetrag_cents()
    zinsen: dict[int, int] = {}
    steuer: dict[int, int] = {}
    monate: dict[int, set[int]] = {}
    for view in haushalt:
        if view.get("error"):
            continue
        for row in view["rows"]:
            jahr = int(row["month"][:4])
            monate.setdefault(jahr, set()).add(int(row["month"][5:7]))
            zinsen[jahr] = zinsen.get(jahr, 0) + row["detail"].get(zn.ZINSEN, 0)
            steuer[jahr] = steuer.get(jahr, 0) - row["detail"].get(zn.KAPITALERTRAGSTEUER, 0)
    voll = [j for j, m in monate.items() if len(m) == 12]
    assert voll, "kein volles Jahr im Horizont"
    if not any(zinsen[j] for j in voll):
        pytest.skip("kein Konto der Daten verdient Zinsen")
    for jahr in voll:
        soll = zn.steuer_auf(zinsen[jahr], freibetrag, quote)[0]
        assert abs(steuer[jahr] - soll) <= 10 * RUNDUNG_STEUER, jahr
