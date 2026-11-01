"""Zinsen auf dem Tagesgeld: der Satz je Konto und Monat, die Mischung zum Topf
und die Datei, in der die Saetze stehen. Alles erfunden und rund."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from finctl import zinssaetze
from finctl.forecast import fortschreibung as fs
from finctl.forecast import jahre as jm
from finctl.forecast import messung, zinsen
from finctl.forecast import verfahren as vf
from finctl.forecast.zinsen import Konto, Zinssatz, mischung, satz_im_monat

LANG = 0.02


def _m(text: str) -> date:
    return date.fromisoformat(text + "-01")


def _satz(ab: str, bis: str | None, satz: float) -> Zinssatz:
    return Zinssatz(ab=_m(ab), bis=_m(bis) if bis else None, satz=satz)


# ------------------------------------------------------- der Satz eines Monats

def test_an_entry_applies_inside_its_period_and_both_ends_count():
    aktion = (_satz("2026-03", "2026-08", 0.04),)
    assert satz_im_monat(aktion, "tagesgeld", _m("2026-03"), LANG) == 0.04
    assert satz_im_monat(aktion, "tagesgeld", _m("2026-08"), LANG) == 0.04


def test_after_a_promotional_rate_ends_the_account_pays_the_long_term_rate():
    """Ein Aktionszins endet, das Konto zahlt danach weiter etwas."""
    aktion = (_satz("2026-03", "2026-08", 0.04),)
    assert satz_im_monat(aktion, "tagesgeld", _m("2026-09"), LANG) == LANG
    # Auch ein Girokonto: wer Eintraege hat, verdient ausserhalb weiter.
    assert satz_im_monat(aktion, "giro", _m("2026-09"), LANG) == LANG


def test_a_month_before_the_first_entry_pays_the_long_term_rate():
    aktion = (_satz("2026-03", "2026-08", 0.04),)
    assert satz_im_monat(aktion, "tagesgeld", _m("2026-02"), LANG) == LANG
    assert satz_im_monat(aktion, "giro", _m("2026-02"), LANG) == LANG


def test_without_any_entry_the_kind_decides():
    assert satz_im_monat((), "tagesgeld", _m("2026-05"), LANG) == LANG
    assert satz_im_monat((), "giro", _m("2026-05"), 0.03) == 0.0


def test_a_clearing_account_with_interest_earns_only_through_an_entry():
    """Ein Verrechnungskonto hat die Art giro."""
    assert satz_im_monat((), "giro", _m("2026-05"), LANG) == 0.0
    assert satz_im_monat((_satz("2026-01", None, 0.01),), "giro",
                         _m("2030-05"), LANG) == 0.01


def test_of_two_overlapping_entries_the_later_start_wins():
    zwei = (_satz("2026-01", None, 0.01), _satz("2026-06", "2026-12", 0.05))
    assert satz_im_monat(zwei, "tagesgeld", _m("2026-05"), LANG) == 0.01
    assert satz_im_monat(zwei, "tagesgeld", _m("2026-07"), LANG) == 0.05


# ------------------------------------------------------- die Mischung zum Topf

def _jahr(jahr: int, ab: int = 1) -> list[date]:
    return [date(jahr, m, 1) for m in range(ab, 13)]


def test_the_pot_pays_the_rates_of_its_accounts_weighted_by_their_stands():
    konten = {"a": Konto("tagesgeld", 60_000_00), "b": Konto("giro", 40_000_00)}
    saetze = {"a": (_satz("2026-01", None, 0.02),)}
    m = mischung(konten, saetze, _jahr(2027), 0.03)
    assert m.satz == pytest.approx(0.6 * 0.02)
    assert m.teile == (("a", 0.6, 0.02), ("b", 0.4, 0.0))


def test_an_account_rate_is_the_mean_of_its_twelve_months():
    konten = {"a": Konto("tagesgeld", 50_000_00)}
    saetze = {"a": (_satz("2027-01", "2027-06", 0.04),)}
    m = mischung(konten, saetze, _jahr(2027), 0.02)
    assert m.satz == pytest.approx(0.03)


def test_in_the_base_year_only_the_remaining_months_count():
    konten = {"a": Konto("tagesgeld", 50_000_00)}
    saetze = {"a": (_satz("2026-01", "2026-09", 0.04),)}
    # Oktober bis Dezember: der Aktionszins ist vorbei.
    assert mischung(konten, saetze, _jahr(2026, ab=10), 0.02).satz == 0.02
    assert mischung(konten, saetze, _jahr(2026), 0.02).satz == pytest.approx(0.035)


def test_an_empty_pot_pays_the_long_term_rate():
    leer = mischung({}, {}, _jahr(2027), LANG)
    assert (leer.satz, leer.teile) == (LANG, ())
    nur_minus = mischung({"a": Konto("giro", -500_00)}, {}, _jahr(2027), LANG)
    assert (nur_minus.satz, nur_minus.teile) == (LANG, ())


def test_only_positive_stands_weigh_in():
    konten = {"a": Konto("tagesgeld", 10_000_00), "b": Konto("giro", -90_000_00)}
    m = mischung(konten, {}, _jahr(2027), LANG)
    assert m.satz == LANG and [t[0] for t in m.teile] == ["a"]


def test_a_pot_of_plain_tagesgeld_accounts_earns_exactly_the_long_term_rate():
    """Ohne jeden Eintrag rechnet ein Haushalt wie vorher: kein Rundungsrest."""
    konten = {"a": Konto("tagesgeld", 33_300_00), "b": Konto("tagesgeld", 77_700_00),
              "c": Konto("tagesgeld", 1_00)}
    assert mischung(konten, {}, _jahr(2027), 0.025).satz == 0.025


def test_a_giro_account_in_the_pot_lowers_its_rate():
    konten = {"t": Konto("tagesgeld", 80_000_00), "g": Konto("giro", 20_000_00)}
    assert mischung(konten, {}, _jahr(2027), 0.025).satz == pytest.approx(0.02)


# ------------------------------------------------------- die Datei

@pytest.fixture
def ordner(tmp_path, monkeypatch):
    monkeypatch.setattr(zinssaetze, "CONFIG_DIR", tmp_path)
    return tmp_path


def test_an_entry_is_written_and_read_back_sorted(ordner):
    zinssaetze.anlegen("tagesgeld", "2026-09", None, 0.01)
    zinssaetze.anlegen("tagesgeld", "2026-01", "2026-06", 0.035)
    lies = zinssaetze.lesen()["tagesgeld"]
    assert lies == (_satz("2026-01", "2026-06", 0.035), _satz("2026-09", None, 0.01))
    assert [(z["nr"], z["ab"], z["bis"]) for z in zinssaetze.zeilen()] == [
        (0, "2026-01", "2026-06"), (1, "2026-09", "")]


def test_a_date_typed_as_a_day_counts_as_its_month(ordner):
    zinssaetze.anlegen("tagesgeld", "2026-03-17", "2026-05-02", 0.02)
    assert zinssaetze.lesen()["tagesgeld"] == (_satz("2026-03", "2026-05", 0.02),)


@pytest.mark.parametrize("konto, ab, bis, satz, meldung", [
    ("", "2026-01", None, 0.02, "Konto fehlt"),
    ("t", "", None, 0.02, "ab fehlt"),
    ("t", "Januar", None, 0.02, "kein Monat"),
    ("t", "2026-05", "2026-04", 0.02, "bis liegt vor ab"),
    ("t", "2026-01", None, -0.01, "zwischen 0 und 25"),
    ("t", "2026-01", None, 2.5, "zwischen 0 und 25"),
])
def test_an_entry_that_does_not_fit_is_refused_with_a_message(
        ordner, konto, ab, bis, satz, meldung):
    with pytest.raises(ValueError, match=meldung):
        zinssaetze.anlegen(konto, ab, bis, satz)
    assert zinssaetze.lesen() == {}


def test_two_entries_of_one_account_may_not_overlap(ordner):
    zinssaetze.anlegen("t", "2026-01", "2026-06", 0.03)
    with pytest.raises(ValueError, match="überschneidet"):
        zinssaetze.anlegen("t", "2026-06", "2026-09", 0.02)
    with pytest.raises(ValueError, match="überschneidet"):
        zinssaetze.anlegen("t", "2025-01", None, 0.02)
    zinssaetze.anlegen("t", "2026-07", None, 0.02)
    zinssaetze.anlegen("u", "2026-01", None, 0.01)       # ein anderes Konto
    assert len(zinssaetze.lesen()["t"]) == 2


def test_an_entry_can_be_deleted_by_its_number(ordner):
    zinssaetze.anlegen("t", "2026-01", "2026-06", 0.03)
    zinssaetze.anlegen("t", "2026-07", None, 0.02)
    zinssaetze.loeschen("t", 0)
    assert zinssaetze.lesen()["t"] == (_satz("2026-07", None, 0.02),)
    with pytest.raises(ValueError, match="nicht mehr"):
        zinssaetze.loeschen("t", 5)
    zinssaetze.loeschen("t", 0)
    assert zinssaetze.lesen() == {}


def test_writing_what_is_already_there_leaves_the_file_alone(ordner):
    zinssaetze.anlegen("t", "2026-01", "2026-06", 0.03)
    datei = ordner / zinssaetze.DATEI
    alt = datei.stat().st_mtime_ns
    zinssaetze._schreiben(zinssaetze.lesen())
    assert datei.stat().st_mtime_ns == alt


def test_a_broken_entry_in_the_file_is_an_error_not_a_silent_zero(ordner):
    (ordner / zinssaetze.DATEI).write_text(
        "zinssaetze:\n  t:\n    - {ab: '2026-01', satz: viel}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unlesbar"):
        zinssaetze.lesen()


# ------------------------------------------------ Hochrechnung rechnet, schreibt nicht fort

@pytest.fixture
def hauptbuch():
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
            ('einkommen/zinsen', 'income', 0),
            ('steuern/kapitalertragsteuer', 'expense', 0),
            ('einkommen/dividende', 'income', 0),
            ('steuern/nachzahlung', 'expense', 0);
    """)
    for monat in range(1, 8):
        for kategorie, cents in (("einkommen/zinsen", 10_000),
                                 ("steuern/kapitalertragsteuer", -2_500),
                                 ("einkommen/dividende", 5_000),
                                 ("steuern/nachzahlung", -4_000)):
            n = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] + 1
            c.execute("INSERT INTO transactions VALUES (?, 'a', ?, ?)",
                      (n, f"2026-{monat:02d}-05", f"h{n}"))
            c.execute("INSERT INTO splits VALUES (?, ?, ?, NULL, NULL)",
                      (n, kategorie, cents))
    yield c
    c.close()


def test_the_base_of_the_projection_carries_neither_interest_nor_its_tax(hauptbuch):
    """Beides fortzuschreiben zaehlte die Zinsen doppelt: der Topf wuchse mit
    seinem Satz, und die gebuchten Zinsen kaemen als Einnahme dazu."""
    class _F:                           # was `jahre._hochrechnung` vom Fenster liest
        von, bis, monate = date(2026, 1, 1), date(2026, 7, 31), 7

    vorschau = jm._hochrechnung(_F, None)
    kategorien = {p.kategorie for p in fs.fortschreibung(hauptbuch, vorschau)}
    assert kategorien == {"einkommen/dividende", "steuern/nachzahlung"}
    # Dieselbe Vorschau ohne die Auswahl haette sie fortgeschrieben.
    ohne = fs.Vorschau(reihe="haushalt", regeln=vf.HOCHRECHNUNG,
                       ausschluss=messung.Ausschluss(), je_block=True,
                       since="2026-01-01", until="2026-07-31", fenster_monate=7)
    assert {jm.ZINSEN, jm.KAPITALERTRAGSTEUER} <= {
        p.kategorie for p in fs.fortschreibung(hauptbuch, ohne)}
    assert zinsen.VERZINST == "tagesgeld"


def test_the_fixed_identifiers_exist_in_the_shipped_taxonomy():
    import yaml

    datei = Path(__file__).resolve().parent.parent / "finctl" / "vorgaben" / "taxonomy.yaml"
    baum = yaml.safe_load(datei.read_text(encoding="utf-8"))["management"]
    for kennung in (jm.ZINSEN, jm.KAPITALERTRAGSTEUER):
        ober, kind = kennung.split("/")
        assert kind in baum[ober]["children"], kennung
