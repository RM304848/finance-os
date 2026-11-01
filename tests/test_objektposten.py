"""Die Prognose eines Objekts im Monatsmodell (Schritt 5b, E.4).

Beide Modelle rechnen sie aus derselben Funktion (`objektposten.betraege`): die
Jahresrechnung summiert die Monate eines Jahres zu einem Block, das Monatsmodell bucht
sie je Monat auf ein Konto. Alles hier ist erfunden und rund.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from finctl import assumptions as ann
from finctl import objekte
from finctl.forecast import abgleich as ag
from finctl.forecast import jahre as jm
from finctl.forecast import konten as ops
from finctl.forecast import objektposten as ob
from finctl.ledger import db as ledger
from finctl.pfade import DB_PATH

INFLATION = 0.02
SOMMER = (0.6, 0.6, 0.7, 0.8, 1.0, 1.2, 1.6, 1.6, 1.2, 0.8, 0.9, 1.0)
STICHTAG = date(2026, 12, 31)       # das Basisjahr beider Modelle ist 2027


def _objekt(**felder) -> objekte.Prognose:
    return objekte.Prognose(**{"id": "haus", "name": "Haus", "miete_cents": 200_000,
                               "kosten_cents": 80_000, **felder})


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE accounts (id TEXT PRIMARY KEY, ingest_mode TEXT, active INTEGER);
        CREATE TABLE transactions (id INTEGER PRIMARY KEY, account_id TEXT, booking_date TEXT);
        CREATE TABLE splits (transaction_id INTEGER, mgmt_category_id TEXT,
                             transfer_account_id TEXT, property_id TEXT,
                             amount_cents INTEGER);
        INSERT INTO accounts VALUES ('giro', 'parsed', 1), ('zweit', 'parsed', 1),
                                    ('karte', 'parsed', 1), ('alt', 'parsed', 0);
    """)
    yield c
    c.close()


def _buchung(c, tag, konto, betrag, kategorie, objekt):
    n = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] + 1
    c.execute("INSERT INTO transactions VALUES (?, ?, ?)", (n, konto, tag))
    c.execute("INSERT INTO splits (transaction_id, mgmt_category_id, property_id, amount_cents)"
              " VALUES (?, ?, ?, ?)", (n, kategorie, objekt, betrag))


def _miete(c, tag, konto, objekt="haus", kategorie="immobilie/mieteinnahme"):
    _buchung(c, tag, konto, 200_000, kategorie, objekt)


def _kosten(c, tag, konto, betrag=-40_000, objekt="haus"):
    _buchung(c, tag, konto, betrag, "konsum/essen", objekt)


def _monatsmodell(monkeypatch, conn, p, months, *, verkauf=None, fcfg=None, konto="giro"):
    """Die Posten von `p` auf `konto`, wie `account_forecast` sie bucht."""
    monkeypatch.setattr(objekte, "prognosen", lambda *a, **k: [p])
    monkeypatch.setattr(jm, "verkaeufe", lambda *a, **k: [
        SimpleNamespace(property_id=k_, ab=ab) for k_, ab in (verkauf or {}).items()])
    monkeypatch.setattr(ops, "steigerung", lambda _=None: INFLATION)
    return ops._objektposten(conn, konto, fcfg or {}, STICHTAG, months, "giro")


def _jahr_der_posten(posten, jahr) -> int:
    return sum(o.amount_cents for o in posten if o.month.year == jahr)


# ------------------------------------------------------------------ die Rechnung

def test_a_flat_curve_changes_nothing():
    """Eine Kurve aus lauter 1,0: Miete minus Kosten ist die gesteigerte Prognose."""
    p = _objekt()
    for monat in (date(2027, 1, 1), date(2028, 6, 1), date(2030, 12, 1)):
        miete, kosten = ob.betraege(p, monat, 2027, INFLATION)
        assert miete - kosten == ann.grow(p.netto_cents, monat.year - 2027, INFLATION)
        assert kosten == ann.grow(p.kosten_cents, monat.year - 2027, INFLATION)


def test_the_curve_moves_the_rent_and_not_the_costs():
    p = _objekt(saison=SOMMER)
    juli, januar = (ob.betraege(p, date(2027, m, 1), 2027, INFLATION) for m in (7, 1))
    assert juli[0] > januar[0]
    assert juli[1] == januar[1] == 80_000


@pytest.mark.parametrize("saison", [(1.0,) * 12, SOMMER])
@pytest.mark.parametrize("ab", [None, date(2027, 4, 1)])
def test_both_models_sum_to_the_same_year(monkeypatch, conn, saison, ab):
    """Die Jahresrechnung und das Monatsmodell zaehlen ueber ein Jahr dasselbe, auch mit einer
    Kurve und in einem Jahr, in dem die Vermietung erst beginnt."""
    p = _objekt(saison=saison, ab=ab, bis=date(2028, 8, 1))
    posten = _monatsmodell(monkeypatch, conn, p, 24)
    for jahr in (2027, 2028):
        [zeile] = jm._objektposten([p], jahr, 2027, 0, INFLATION)
        assert _jahr_der_posten(posten, jahr) == zeile.cents


def test_a_curve_over_a_full_year_keeps_the_sum_and_over_part_of_it_does_not():
    """Saisonalitaet verschiebt Geld zwischen Monaten, sie erfindet keines -- ueber ein volles
    Jahr. Beginnt die Vermietung im April, fehlen die schwachen Monate davor."""
    voll, flach = _objekt(saison=SOMMER), _objekt()
    assert jm._objektposten([voll], 2027, 2027, 0, 0.0)[0].cents == \
        jm._objektposten([flach], 2027, 2027, 0, 0.0)[0].cents
    ab_april = _objekt(saison=SOMMER, ab=date(2027, 4, 1))
    assert jm._objektposten([ab_april], 2027, 2027, 0, 0.0)[0].cents != \
        jm._objektposten([_objekt(ab=date(2027, 4, 1))], 2027, 2027, 0, 0.0)[0].cents


def test_the_sale_ends_the_posts_in_both_models(monkeypatch, conn):
    """Ab dem Monat des Verkaufs kein Posten mehr, und die Jahresrechnung zieht fuer das
    Objekt nichts aus `miete` und `immobilie` ab."""
    p = _objekt()
    verkauf = {"haus": date(2028, 7, 1)}
    posten = _monatsmodell(monkeypatch, conn, p, 24, verkauf=verkauf)
    assert max(o.month for o in posten) == date(2028, 6, 1)
    [zeile] = jm._objektposten([p], 2028, 2027, 0, INFLATION, verkauf)
    assert _jahr_der_posten(posten, 2028) == zeile.cents
    assert jm._objektposten([p], 2029, 2027, 0, INFLATION, verkauf) == []


# ------------------------------------------------------------------ das Konto

def test_the_posts_land_where_the_rent_arrived_last(monkeypatch, conn):
    _miete(conn, "2026-06-30", "giro")
    _miete(conn, "2026-09-30", "zweit")
    p = _objekt()
    assert _monatsmodell(monkeypatch, conn, p, 3, konto="giro") == []
    posten = _monatsmodell(monkeypatch, conn, p, 3, konto="zweit")
    assert {o.label for o in posten} == {"objekt-miete:haus", "objekt-kosten:haus"}
    assert all(o.account_id == "zweit" and o.herkunft.objekt for o in posten)


def test_without_a_rent_the_operating_account_takes_them(monkeypatch, conn):
    posten = _monatsmodell(monkeypatch, conn, _objekt(), 3, konto="giro")
    assert len(posten) == 6
    assert "Betriebskonto" in posten[0].herkunft.herleitung


def test_a_rent_on_a_closed_account_goes_to_the_operating_account(monkeypatch, conn):
    _miete(conn, "2026-09-30", "alt")
    assert _monatsmodell(monkeypatch, conn, _objekt(), 3, konto="giro")


def test_a_pass_through_account_counts_on_the_account_that_covers_it(monkeypatch, conn):
    """Ein durchlaufendes Konto hat keine Prognose; sein Posten zaehlt auf dem deckenden."""
    _miete(conn, "2026-09-30", "karte")
    conn.execute("INSERT INTO transactions VALUES (99, 'karte', '2026-09-01')")
    conn.execute("INSERT INTO splits VALUES (99, 'transfer/eigenkonto', 'zweit', NULL, -50000)")
    fcfg = {"account_roles": {"karte": {"role": "durchlaufend"}}}
    assert _monatsmodell(monkeypatch, conn, _objekt(), 3, fcfg=fcfg, konto="zweit")
    assert _monatsmodell(monkeypatch, conn, _objekt(), 3, fcfg=fcfg, konto="giro") == []


# ------------------------------------------------------------------ ein Objekt ohne Konto

def _ohne_konto(monkeypatch, conn, betrieb):
    monkeypatch.setattr(objekte, "prognosen", lambda *a, **k: [_objekt()])
    monkeypatch.setattr(ops, "_stichtag", lambda _c: STICHTAG)
    monkeypatch.setattr(ops, "_operating_account", lambda _f: betrieb)
    return ops.objekte_ohne_konto(conn, {})


def test_an_object_that_finds_no_account_is_listed(monkeypatch, conn):
    """Keine gebuchte Miete und kein Betriebskonto: Miete und Kosten stuenden nirgends."""
    assert [p.id for p in _ohne_konto(monkeypatch, conn, None)] == ["haus"]


def test_an_object_with_an_operating_account_or_a_rent_is_not_listed(monkeypatch, conn):
    assert _ohne_konto(monkeypatch, conn, "giro") == []
    _miete(conn, "2026-09-30", "zweit")
    assert _ohne_konto(monkeypatch, conn, None) == []


def test_a_rent_on_a_closed_account_does_not_count_as_an_account(monkeypatch, conn):
    _miete(conn, "2026-09-30", "alt")
    assert [p.id for p in _ohne_konto(monkeypatch, conn, None)] == ["haus"]


# ------------------------------------------------------------------ der Tag (E.4-N)

def test_the_rent_keeps_its_day_and_the_costs_take_the_median(conn):
    """Miete am 27., Kosten am 3., 10. und 20.: Tag 27 fuer die Miete, Tag 10 fuer die Kosten."""
    _miete(conn, "2026-11-27", "giro")
    for tag in ("2026-10-03", "2026-11-10", "2026-12-20"):
        _kosten(conn, tag, "giro")
    assert ops.tage_des_objekts(conn, "haus", STICHTAG) == (27, 10)


def test_without_bookings_both_fall_on_the_fifteenth(conn):
    assert ops.tage_des_objekts(conn, "haus", STICHTAG) == (15, 15)


def test_only_the_twelve_months_before_the_stichtag_count_for_the_costs(conn):
    """Eine Kostenbuchung von vor dem Zwoelfmonatsfenster zaehlt nicht: mit ihr waere der
    Median 6,5, abgerundet 6."""
    _miete(conn, "2026-11-27", "giro")
    _kosten(conn, "2025-06-03", "giro")
    for tag in ("2026-10-03", "2026-11-10", "2026-12-20"):
        _kosten(conn, tag, "giro")
    assert ops.tage_des_objekts(conn, "haus", STICHTAG) == (27, 10)


def test_the_posts_carry_their_days_and_the_31st_is_cut_to_the_month_end(monkeypatch, conn):
    """Eine Miete am 31. Dezember: im Februar faellt sie auf den 28., in den Monaten mit 31
    Tagen bleibt sie am 31."""
    _miete(conn, "2026-12-31", "giro")
    _kosten(conn, "2026-10-10", "giro")
    tage = {(o.label, o.month.month): o.day for o in _monatsmodell(monkeypatch, conn, _objekt(), 3)}
    assert tage == {("objekt-miete:haus", 1): 31, ("objekt-miete:haus", 2): 28,
                    ("objekt-miete:haus", 3): 31, ("objekt-kosten:haus", 1): 10,
                    ("objekt-kosten:haus", 2): 10, ("objekt-kosten:haus", 3): 10}


def test_the_posts_have_names_on_the_page():
    namen = ob.anzeigenamen([_objekt()], {"objekt-miete:haus", "konsum/essen"})
    assert namen == {"objekt-miete:haus": "Haus: Miete (Prognose)"}


@pytest.mark.langsam
@pytest.mark.skipif(not DB_PATH.exists(), reason="kein Hauptbuch")
def test_a_curve_keeps_both_models_equal_on_the_household(monkeypatch):
    """Der ganze Haushalt, beide Modelle, mit einer Kurve ungleich 1 und einer Vermietung, die
    mitten im Jahr 2028 beginnt: Der Block `objekt` ist in jedem vollen Jahr des Horizonts
    gleich (Rundung ausgenommen), und die Kurve wirkt -- 2028 ist nicht, was die flache
    Kurve ergaebe."""
    from test_paritaet import RUNDUNG_CENTS, rechnen

    echte = objekte.prognosen()
    if not echte:
        pytest.skip("kein Objekt mit Prognose")
    ab = date(2028, 4, 1)
    kurven = [replace(p, saison=SOMMER, ab=ab) for p in echte]
    monkeypatch.setattr(objekte, "prognosen", lambda *a, **k: kurven)
    conn = ledger.connect(DB_PATH)
    try:
        lauf = rechnen(conn)
        basisjahr = (ops._stichtag(conn) + timedelta(days=1)).year
    finally:
        conn.close()
    assert 2028 in lauf.jahre
    for jahr in lauf.jahre:
        assert abs(lauf.abweichung(jahr, "objekt")) <= RUNDUNG_CENTS, jahr
    flach = sum(ob.netto(replace(p, saison=(1.0,) * 12), date(2028, m, 1), basisjahr,
                         ann.inflation_pa())
                for p in kurven for m in range(1, 13))
    assert lauf.jahr[(2028, "objekt")] not in (0, flach)


@pytest.fixture
def kopie():
    """Das Hauptbuch im Speicher: der Verkauf aendert Objektdaten."""
    echt = ledger.connect(DB_PATH)
    k = sqlite3.connect(":memory:")
    echt.backup(k)
    echt.close()
    k.row_factory = sqlite3.Row
    yield k
    k.close()


@pytest.mark.langsam
@pytest.mark.skipif(not DB_PATH.exists(), reason="kein Hauptbuch")
def test_selling_an_object_with_a_forecast_ends_its_block_and_takes_nothing_from_the_others(
        kopie):
    """Der Verkauf beendet den Block `objekt` im Monat des Verkaufs; `miete` und `immobilie`
    ziehen fuer das Objekt nichts ab, denn es steht nicht in ihnen."""
    echt = objekte.prognosen()
    if not echt:
        pytest.skip("kein Objekt mit Prognose")
    p = echt[0]
    jahr = max(date.today().year, p.ab.year if p.ab else 0) + 2
    if p.bis and p.bis < date(jahr + 1, 1, 1):
        pytest.skip("die Vermietung endet vor dem Verkauf")
    vorher = jm.project(kopie, end_year=jahr + 1, opening_cents=0)
    kopie.execute("UPDATE properties SET planned_sale_on = ?, sale_price_cents = 10000000, "
                  "sold_on = NULL WHERE id = ?", (f"{jahr}-07-01", p.id))
    nachher = jm.project(kopie, end_year=jahr + 1, opening_cents=0)
    assert nachher.year(jahr).blocks[ag.OBJEKT] < vorher.year(jahr).blocks[ag.OBJEKT]
    assert nachher.year(jahr + 1).blocks[ag.OBJEKT] == 0
    for block in ("miete", "immobilie"):
        assert nachher.year(jahr).blocks[block] == vorher.year(jahr).blocks[block], block
        assert not [z for z in nachher.year(jahr).posten[block]
                    if z.verweis == p.id and z.label.startswith("Verkauf")]
