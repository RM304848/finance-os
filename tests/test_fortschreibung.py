"""Die Fortschreibung: dieselbe Messung und dieselben Verfahren, nur Reihe,
Tabelle und Ausschluss wechseln. Ein Hauptbuch im Speicher, alles erfunden."""

from __future__ import annotations

import ast
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from finctl.forecast import fortschreibung as kern
from finctl.forecast import takt as tk
from finctl.forecast import verfahren as vf
from finctl.forecast.fortschreibung import Vorschau, fortschreibung
from finctl.forecast.konten import vorschau_konto
from finctl.forecast.messung import Ausschluss


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE mgmt_categories (id TEXT PRIMARY KEY, kind TEXT,
                                      fixkosten INTEGER DEFAULT 0, einmalig INTEGER DEFAULT 0);
        CREATE TABLE transactions (id INTEGER PRIMARY KEY, account_id TEXT,
                                   booking_date TEXT, dedup_hash TEXT NOT NULL);
        CREATE TABLE splits (transaction_id INTEGER, mgmt_category_id TEXT,
                             amount_cents INTEGER, transfer_account_id TEXT,
                             property_id TEXT);
        INSERT INTO mgmt_categories (id, kind, fixkosten) VALUES
            ('einkommen/gehalt', 'income', 0),
            ('konsum/essen', 'expense', 0),
            ('konsum/kleidung', 'expense', 0),
            ('konsum/erstattung', 'income', 0),
            ('steuern/nachzahlung', 'expense', 0),
            ('versicherung/haftpflicht', 'expense', 1);
    """)
    yield c
    c.close()


def _buche(c, tag, konto, kategorie, cents):
    n = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] + 1
    c.execute("INSERT INTO transactions VALUES (?, ?, ?, ?)", (n, konto, tag, f"h{n}"))
    c.execute("INSERT INTO splits VALUES (?, ?, ?, NULL, NULL)", (n, kategorie, cents))


def _haushalt(**anders) -> Vorschau:
    werte = dict(reihe="haushalt", regeln=vf.HOCHRECHNUNG, ausschluss=Ausschluss(),
                 je_block=False, since="2026-01-01", until="2026-07-31",
                 fenster_monate=7)
    werte.update(anders)
    return Vorschau(**werte)


def test_the_household_series_adds_the_accounts_before_it_rounds(conn):
    """Zwei Konten mit je 50 Cent: je Konto gerundet waeren es 2 x 86, auf der
    Haushaltssumme 171."""
    _buche(conn, "2026-03-05", "a", "konsum/essen", -50)
    _buche(conn, "2026-03-06", "b", "konsum/essen", -50)
    posten = fortschreibung(conn, _haushalt())
    assert [(p.konto, p.kategorie, p.block, p.ergebnis.cents) for p in posten] == [
        ("", "konsum/essen", None, -171)]
    assert vf.summe_aufs_jahr(-50, 7) * 2 == -172


def test_the_account_series_keeps_one_item_per_account(conn):
    _buche(conn, "2026-03-05", "a", "konsum/essen", -50)
    _buche(conn, "2026-03-06", "b", "konsum/essen", -70)
    posten = fortschreibung(conn, _haushalt(reihe="konto"))
    assert [(p.konto, p.ergebnis.cents) for p in posten] == [("a", -86), ("b", -120)]


def test_the_account_series_can_be_limited_to_one_account(conn):
    _buche(conn, "2026-03-05", "a", "konsum/essen", -50)
    _buche(conn, "2026-03-06", "b", "konsum/essen", -70)
    posten = fortschreibung(conn, _haushalt(reihe="konto"), konten=frozenset({"b"}))
    assert [p.konto for p in posten] == ["b"]


def test_the_block_belongs_to_the_key_when_asked_for(conn):
    _buche(conn, "2026-03-05", "a", "einkommen/gehalt", 5000)
    _buche(conn, "2026-03-06", "a", "konsum/essen", -100)
    posten = fortschreibung(conn, _haushalt(je_block=True))
    assert {p.kategorie: p.block for p in posten} == {
        "einkommen/gehalt": "gehalt", "konsum/essen": "konsum"}


def test_a_preview_without_its_window_is_refused(conn):
    _buche(conn, "2026-03-05", "a", "konsum/essen", -50)
    with pytest.raises(ValueError, match="fenster_monate"):
        fortschreibung(conn, _haushalt(fenster_monate=None))


def test_categories_to_leave_out_fall_away_after_the_measurement(conn):
    _buche(conn, "2026-03-05", "a", "konsum/essen", -50)
    _buche(conn, "2026-03-06", "a", "konsum/kleidung", -70)
    posten = fortschreibung(conn, _haushalt(ausser=frozenset({"konsum/essen"})))
    assert [p.kategorie for p in posten] == ["konsum/kleidung"]


def test_the_end_of_a_category_rides_along(conn):
    _buche(conn, "2026-03-05", "a", "konsum/essen", -50)
    ende = date(2027, 3, 1)
    posten = fortschreibung(conn, _haushalt(enden={"konsum/essen": ende}))
    assert posten[0].ende == ende


def test_the_last_measured_month_is_the_last_one_with_a_booking(conn):
    _buche(conn, "2026-03-05", "a", "konsum/essen", -50)
    _buche(conn, "2026-05-06", "a", "konsum/kleidung", -70)
    posten = fortschreibung(conn, _haushalt(ausser=frozenset({"konsum/kleidung"})))
    assert posten[0].gemessen_bis == date(2026, 5, 1)


def test_the_kontoprognose_preset_counts_uncategorised_parts_and_names_its_table():
    v = vorschau_konto(
        since="2026-04-01", until="2026-09-30",
        fenster_monate=6, exclude={"kredit/zinsen"}, include_transfers=False,
        deckung={"pp": "a"}, escalation_pa=0.0, ends=None,
        ohne=[{"dedup_hashes": ["x", "y"]}, {"dedup_hashes": ["y", "z"]}])
    assert v.reihe == "konto" and not v.je_block and v.fenster_monate == 6
    assert v.regeln == vf.KONTOPROGNOSE
    assert v.ausschluss == Ausschluss(
        umbuchung="art", deckung=(("pp", "a"),), ohne_kategorie=True,
        hashes=frozenset({"x", "y", "z"}))
    assert v.ausser == {"kredit/zinsen"} and v.steigerung == 0.0


def test_every_account_divides_by_the_months_of_the_household_window(conn):
    """Das Fenster ist das des Haushalts. Ein Konto, das juenger ist, traegt nur, was es
    gemessen hat; ueber die Konten summiert ergibt sich die Zahl der Hochrechnung."""
    conn.execute("CREATE TABLE statements (account_id TEXT, period_start TEXT, status TEXT)")
    conn.execute("INSERT INTO statements VALUES ('a', '2026-01-01', 'imported')")
    conn.execute("INSERT INTO statements VALUES ('b', '2026-06-01', 'imported')")
    _buche(conn, "2026-06-05", "a", "konsum/essen", -1200)
    _buche(conn, "2026-06-06", "b", "konsum/essen", -1200)
    abfragen: list[str] = []
    conn.set_trace_callback(lambda sql: abfragen.append(sql) if "statements" in sql else None)
    v = Vorschau(reihe="konto", regeln=vf.KONTOPROGNOSE, ausschluss=Ausschluss(),
                 je_block=False, since="2026-01-01", until="2026-07-31", fenster_monate=7)
    posten = fortschreibung(conn, v)
    assert [(p.konto, p.ergebnis.cents) for p in posten] == [("a", -171), ("b", -171)]
    assert not abfragen
    jahr = fortschreibung(conn, _haushalt())
    assert abs(jahr[0].ergebnis.cents - 12 * sum(p.ergebnis.cents for p in posten)) <= 12


def _importe(pfad: Path) -> set[str]:
    """Jedes Modul aus `finctl`, das eine Datei importiert -- auch in Funktionen."""
    out: set[str] = set()
    for knoten in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
        if isinstance(knoten, ast.Import):
            out |= {a.name for a in knoten.names}
        elif isinstance(knoten, ast.ImportFrom) and knoten.module:
            if knoten.module in ("finctl", "finctl.forecast"):
                out |= {f"{knoten.module}.{a.name}" for a in knoten.names}
            else:
                out.add(knoten.module)
    return {m for m in out if m == "finctl" or m.startswith("finctl.")}


def _juengst(**anders) -> Vorschau:
    """Vorschau im Tempo der letzten drei Monate fuer den Konsum."""
    return _haushalt(je_block=True, regeln_je_block={"konsum": vf.HOCHRECHNUNG_JUENGST},
                     **anders)


def test_the_juengst_table_of_a_block_replaces_the_default_for_that_block(conn):
    """Sieben Monate im Fenster: Schnitt durch sieben, Jüngst nur die letzten drei."""
    _buche(conn, "2026-01-05", "a", "konsum/essen", -7000)
    _buche(conn, "2026-06-05", "a", "konsum/essen", -1000)
    _buche(conn, "2026-07-05", "a", "konsum/essen", -2000)
    schnitt = fortschreibung(conn, _haushalt(je_block=True))
    juengst = fortschreibung(conn, _juengst())
    assert [p.ergebnis.cents for p in schnitt] == [vf.summe_aufs_jahr(-10000, 7)]
    assert [p.ergebnis.cents for p in juengst] == [vf.summe_aufs_jahr(-3000, 3)]
    assert "über die letzten 3 Monate (05/2026–07/2026)" in (
        juengst[0].ergebnis.herkunft.herleitung)


def test_a_category_without_booking_in_the_last_three_months_stays_with_zero(conn):
    _buche(conn, "2026-01-05", "a", "konsum/essen", -7000)
    _buche(conn, "2026-07-05", "a", "konsum/kleidung", -2000)
    juengst = fortschreibung(conn, _juengst())
    assert {p.kategorie: p.ergebnis.cents for p in juengst} == {
        "konsum/essen": 0, "konsum/kleidung": vf.summe_aufs_jahr(-2000, 3)}
    schnitt = fortschreibung(conn, _haushalt(je_block=True))
    assert {p.kategorie for p in schnitt} == {p.kategorie for p in juengst}


def test_an_income_in_the_konsum_block_stays_with_the_whole_window(conn):
    """Netto positiv ist Einnahme, und die zaehlt Jüngst nicht: eine Erstattung,
    die einmal im Jahr kommt, waere in drei Monaten null oder das Vierfache."""
    _buche(conn, "2026-01-05", "a", "konsum/erstattung", 7000)
    juengst = fortschreibung(conn, _juengst())
    assert [p.block for p in juengst] == ["konsum"]
    assert [p.ergebnis.cents for p in juengst] == [vf.summe_aufs_jahr(7000, 7)]


def test_a_cost_outside_the_konsum_block_stays_with_the_whole_window(conn):
    """Eine Steuernachzahlung ist ein Klumpen, keine Gewohnheit."""
    _buche(conn, "2026-01-05", "a", "steuern/nachzahlung", -7000)
    _buche(conn, "2026-07-05", "a", "steuern/nachzahlung", -7000)
    juengst = fortschreibung(conn, _juengst())
    assert [p.block for p in juengst] == ["steuern"]
    assert juengst[0].ergebnis.cents == vf.summe_aufs_jahr(-14000, 7)


def test_a_window_of_two_months_divides_by_two(conn):
    _buche(conn, "2026-06-05", "a", "konsum/essen", -1000)
    _buche(conn, "2026-07-05", "a", "konsum/essen", -3000)
    juengst = fortschreibung(conn, _juengst(since="2026-06-01", fenster_monate=2))
    assert juengst[0].ergebnis.cents == vf.summe_aufs_jahr(-4000, 2)


def test_two_tables_share_one_measurement(conn):
    _buche(conn, "2026-01-05", "a", "konsum/essen", -7000)
    _buche(conn, "2026-07-05", "a", "konsum/essen", -2000)
    schnitt, juengst = _haushalt(je_block=True), _juengst()
    gemessen = kern.messen(conn, schnitt)
    assert kern.fortschreiben(conn, schnitt, gemessen) == fortschreibung(conn, schnitt)
    assert kern.fortschreiben(conn, juengst, gemessen) == fortschreibung(conn, juengst)
    assert kern.fortschreiben(conn, juengst, gemessen)[0].ergebnis.letzte_monate == 3
    assert kern.fortschreiben(conn, schnitt, gemessen)[0].ergebnis.letzte_monate == 0


def test_a_measurement_does_not_serve_a_preview_that_measures_differently(conn):
    gemessen = kern.messen(conn, _haushalt(je_block=True))
    with pytest.raises(ValueError, match="misst anders"):
        kern.fortschreiben(conn, _haushalt(je_block=True, since="2026-03-01"), gemessen)


def test_tables_per_block_need_the_block_in_the_key():
    with pytest.raises(ValueError, match="je_block"):
        _haushalt(je_block=False, regeln_je_block={"konsum": vf.HOCHRECHNUNG_JUENGST})


# ------------------------------------------------------- Reihen mit Takt

STICHTAG = date(2026, 9, 30)


@pytest.fixture
def konn():
    """Ein Hauptbuch im Speicher mit Gegenpartei, wie `takt.reihen` es liest."""
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
            ('konsum/essen', 'expense', 0),
            ('einkommen/gutschrift', 'income', 0);
    """)
    yield c
    c.close()


def _kauf(c, tag, kategorie, cents, gegenpartei, konto="a"):
    n = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] + 1
    c.execute("INSERT INTO transactions VALUES (?, ?, ?, ?, ?)",
              (n, konto, tag.isoformat(), f"h{n}", gegenpartei))
    c.execute("INSERT INTO splits VALUES (?, ?, ?, NULL, NULL)", (n, kategorie, cents))


def _monate_bis_stichtag(n: int, tag: int = 1) -> list[date]:
    """Die letzten n Monate bis September 2026, je ein Tag."""
    index = 2026 * 12 + 8 - (n - 1)
    return [date((index + i) // 12, (index + i) % 12 + 1, tag) for i in range(n)]


def _mit_reihen(c, **anders) -> Vorschau:
    """Die Hochrechnung zum Stichtag, mit den Reihen aus dem Hauptbuch."""
    return _haushalt(
        je_block=True, since="2025-10-01", until=STICHTAG.isoformat(), fenster_monate=12,
        reihen=tk.reihen(c, bis=STICHTAG), **anders)


def _je_reihe(posten) -> dict[tuple[str, str], int]:
    return {(p.kategorie, p.reihe): p.ergebnis.cents for p in posten}


def test_a_payment_that_slid_over_the_month_end_counts_twelve_terms_not_thirteen(konn):
    """Dreizehn Buchungen im Fenster: die Miete des Oktobers kam am 30.9. Ohne Reihen
    zaehlt die Summe, mit Reihen der Betrag je Termin mal zwoelf."""
    for tag in _monate_bis_stichtag(12):
        _kauf(konn, tag, "wohnen/miete", -100_000, "vermieter")
    _kauf(konn, date(2026, 9, 30), "wohnen/miete", -100_000, "vermieter")
    ohne = _haushalt(je_block=True, since="2025-10-01", until=STICHTAG.isoformat(),
                     fenster_monate=12)
    assert [p.ergebnis.cents for p in fortschreibung(konn, ohne)] == [-1_300_000]
    mit = fortschreibung(konn, _mit_reihen(konn))
    [p] = mit
    assert (p.kategorie, p.block, p.reihe, p.takt, p.ergebnis.cents) == (
        "wohnen/miete", "fixkosten", "vermieter", 1, -1_200_000)
    assert p.beitrag.laeuft and p.monate == ()
    assert "vermieter: monatlich, je Termin" in p.ergebnis.herkunft.herleitung


def test_a_series_that_is_over_is_listed_with_zero_and_its_parts_count_nowhere(konn):
    for tag in _monate_bis_stichtag(12)[:6]:
        _kauf(konn, tag, "wohnen/miete", -100_000, "vermieter")
    [p] = fortschreibung(konn, _mit_reihen(konn))
    assert (p.reihe, p.ergebnis.cents, p.beitrag.laeuft) == ("vermieter", 0, False)
    assert p.ergebnis.herkunft.herleitung == (
        "vermieter: monatlich, beendet, zuletzt 03/2026, 0,00 € im Jahr")


def test_a_series_that_ended_before_the_window_is_not_listed(konn):
    for tag in _monate_bis_stichtag(22)[:6]:
        _kauf(konn, tag, "wohnen/miete", -100_000, "vermieter")
    assert fortschreibung(konn, _mit_reihen(konn)) == []


def test_a_new_series_counts_in_full_from_its_third_term(konn):
    for tag in _monate_bis_stichtag(3):
        _kauf(konn, tag, "wohnen/miete", -200_000, "vermieter")
    ohne = _haushalt(je_block=True, since="2025-10-01", until=STICHTAG.isoformat(),
                     fenster_monate=12)
    assert [p.ergebnis.cents for p in fortschreibung(konn, ohne)] == [-600_000]
    [p] = fortschreibung(konn, _mit_reihen(konn))
    assert p.ergebnis.cents == -2_400_000


def test_a_back_payment_next_to_an_advance_stays_in_the_rest_of_its_category(konn):
    for tag in _monate_bis_stichtag(12, tag=2):
        _kauf(konn, tag, "wohnen/miete", -100_000, "vermieter")
    _kauf(konn, date(2026, 3, 9), "wohnen/miete", -300_000, "vermieter")
    posten = fortschreibung(konn, _mit_reihen(konn))
    assert [(p.reihe, p.ergebnis.cents) for p in posten] == [
        ("vermieter", -1_200_000), ("", -300_000)]
    rest = posten[1]
    assert [(m.monat, m.cents, m.buchungen) for m in rest.monate] == [("2026-03", -300_000, 1)]


def test_the_rest_keeps_what_belongs_to_no_series(konn):
    """Ein Teil ohne Gegenpartei und eine Reihe ohne festen Takt rechnen wie bisher."""
    for tag in _monate_bis_stichtag(12, tag=2):
        _kauf(konn, tag, "konsum/essen", -5_000, "abo")
    _kauf(konn, date(2026, 1, 5), "konsum/essen", -12_000, "")
    _kauf(konn, date(2026, 2, 20), "konsum/essen", -7_000, "markt")
    _kauf(konn, date(2026, 6, 11), "konsum/essen", -9_000, "markt")
    posten = fortschreibung(konn, _mit_reihen(konn))
    assert [(p.reihe, p.ergebnis.cents) for p in posten] == [
        ("abo", -60_000), ("", vf.summe_aufs_jahr(-12_000 - 7_000 - 9_000, 12))]


def test_the_history_of_a_series_counts_nowhere(konn):
    """Zehn Termine zu 1.000, dann zwei zu 1.500: Die Reihe zaehlt die neue Hoehe, und
    die alten Termine stehen weder in der Reihe noch im Rest."""
    for i, tag in enumerate(_monate_bis_stichtag(12, tag=2)):
        _kauf(konn, tag, "wohnen/miete", -100_000 if i < 10 else -150_000, "vermieter")
    posten = fortschreibung(konn, _mit_reihen(konn))
    assert [(p.reihe, p.ergebnis.cents) for p in posten] == [("vermieter", -1_800_000)]


def test_a_running_series_counts_with_a_term_before_the_window(konn):
    """Die Versicherung kam im August 2025, vor dem Fenster, und laeuft noch."""
    _kauf(konn, date(2025, 8, 15), "versicherung/auto", -60_000, "versicherer")
    ohne = _haushalt(je_block=True, since="2025-10-01", until=STICHTAG.isoformat(),
                     fenster_monate=12)
    assert fortschreibung(konn, ohne) == []
    [p] = fortschreibung(konn, _mit_reihen(konn))
    assert (p.reihe, p.takt, p.ergebnis.cents) == ("versicherer", 12, -60_000)


def test_a_series_with_a_known_end_or_left_out_is_handled_like_a_category(konn):
    for tag in _monate_bis_stichtag(12):
        _kauf(konn, tag, "wohnen/miete", -100_000, "vermieter")
    assert fortschreibung(konn, _mit_reihen(konn, ausser=frozenset({"wohnen/miete"}))) == []
    ende = date(2027, 3, 1)
    [p] = fortschreibung(konn, _mit_reihen(konn, enden={"wohnen/miete": ende}))
    assert p.ende == ende


def test_juengst_counts_only_the_rest_and_the_series_count_the_same(konn):
    for tag in _monate_bis_stichtag(12, tag=2):
        _kauf(konn, tag, "konsum/essen", -10_000, "abo")
    _kauf(konn, date(2026, 1, 8), "konsum/essen", -3_000, "markt")
    _kauf(konn, date(2026, 8, 20), "konsum/essen", -9_000, "")
    schnitt = _mit_reihen(konn)
    juengst = _mit_reihen(konn, regeln_je_block={"konsum": vf.HOCHRECHNUNG_JUENGST})
    gemessen = kern.messen(konn, schnitt)
    a = _je_reihe(kern.fortschreiben(konn, schnitt, gemessen))
    b = _je_reihe(kern.fortschreiben(konn, juengst, gemessen))
    assert a[("konsum/essen", "abo")] == b[("konsum/essen", "abo")] == -120_000
    assert a[("konsum/essen", "")] == vf.summe_aufs_jahr(-12_000, 12)
    assert b[("konsum/essen", "")] == vf.summe_aufs_jahr(-9_000, 3)
    rest = next(p for p in kern.fortschreiben(konn, juengst, gemessen) if not p.reihe)
    assert rest.ergebnis.letzte_monate == 3
    assert next(p for p in kern.fortschreiben(konn, juengst, gemessen)
                if p.reihe).ergebnis.letzte_monate == 0


def test_the_order_of_the_series_does_not_depend_on_their_names(konn):
    """Der Rechenweg zeigt Namen, die der Haushalt aendern kann: gross vor klein, nicht
    alphabetisch."""
    for tag in _monate_bis_stichtag(12):
        _kauf(konn, tag, "konsum/essen", -1_000, "zzz")
        _kauf(konn, tag, "konsum/essen", -9_000, "aaa")
    assert [p.reihe for p in fortschreibung(konn, _mit_reihen(konn))] == ["aaa", "zzz"]


def test_series_in_the_account_preview_are_refused_until_it_takes_them(konn):
    with pytest.raises(ValueError, match="Haushalt"):
        _haushalt(reihe="konto", je_block=True, reihen=tk.reihen(konn, bis=STICHTAG))
    with pytest.raises(ValueError, match="je Block"):
        _haushalt(je_block=False, reihen=tk.reihen(konn, bis=STICHTAG))


def test_a_measurement_without_parts_does_not_serve_a_preview_with_series(konn):
    _kauf(konn, date(2026, 3, 3), "wohnen/miete", -100_000, "vermieter")
    gemessen = kern.messen(konn, _haushalt(
        je_block=True, since="2025-10-01", until=STICHTAG.isoformat(), fenster_monate=12))
    assert gemessen.teile is None
    with pytest.raises(ValueError, match="Teile"):
        kern.fortschreiben(konn, _mit_reihen(konn), gemessen)


def test_the_core_knows_only_the_measurement_the_methods_and_the_series():
    """Wer eine Vorschau baut, steht bei seiner Vorschau. Importiert der Kern
    Konfiguration, Vertraege oder `konten`, kennt er wieder, wer ihn ruft. Die
    Reihen mit Takt kommen als Wert herein (`Vorschau.reihen`); der Kern kennt ihre
    Typen, nicht ihre Quelle."""
    assert _importe(Path(kern.__file__)) == {
        "finctl.forecast.messung", "finctl.forecast.verfahren",
        "finctl.forecast.takt", "finctl.forecast.herkunft"}
