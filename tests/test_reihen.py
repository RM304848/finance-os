"""Reihen von Hand: der Takt einer Reihe und Einmaliges (Schritt 4.3).

Die Datei `reihen_custom.yaml` hat zwei Gesichter. Ein fester Takt (oder
`unregelmaessig`) gilt fuer die ganze Reihe der genannten Buchung; `einmalig`
gilt nur fuer die genannten Buchungen und nimmt sie aus jeder Fortschreibung:
Sie landen im Block `einmalig`, nicht in der Basis der Hochrechnung und nicht in
einer Reihe. Dasselbe tut das Merkmal `einmalig` einer Kategorie.

Alle Reihen hier sind erfunden und rund; die Tests schreiben in einen
Wegwerfordner, nie in `config/`.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

import pytest
import yaml

from finctl import reihen
from finctl.forecast import abgleich as ag
from finctl.forecast import jahre as jm
from finctl.forecast import messung
from finctl.forecast import takt as tk
from finctl.ledger.db import connect, init_db

STICHTAG = date(2026, 9, 30)


def _monat(i: int) -> date:
    """Der i-te Monat ab Januar 2025."""
    index = 2025 * 12 + i
    return date(index // 12, index % 12 + 1, 1)


@pytest.fixture
def haushalt(tmp_path, monkeypatch):
    """Zwanzig Monate Hauptbuch auf einem Konto; `reihen_custom.yaml` im Wegwerfordner."""
    (tmp_path / "config").mkdir()
    monkeypatch.setattr(reihen, "CONFIG_DIR", tmp_path / "config")
    c = connect(init_db(tmp_path / "t.db"))
    c.execute("INSERT INTO accounts (id, display_name, institution, account_type, "
              "ingest_mode, parser_profile) VALUES ('a','A','X','giro','parsed','p')")
    for kennung, kind, fix, einmalig in (
            ("wohnen", "expense", 0, 0), ("wohnen/miete", "expense", 1, 0),
            ("konsum", "expense", 0, 0), ("konsum/essen", "expense", 0, 0),
            ("immobilie", "expense", 0, 0), ("immobilie/kaufnebenkosten", "expense", 0, 1),
            ("einkommen", "income", 0, 0), ("einkommen/gehalt", "income", 0, 0)):
        c.execute("INSERT INTO mgmt_categories (id, parent_id, name, kind, fixkosten, einmalig) "
                  "VALUES (?,?,?,?,?,?)",
                  (kennung, kennung.split("/")[0] if "/" in kennung else None,
                   kennung, kind, fix, einmalig))
    for i in range(20):
        erster = _monat(i)
        ende = _monat(i + 1) - (date(2026, 1, 2) - date(2026, 1, 1))
        c.execute(
            "INSERT INTO statements (id, account_id, source_path, source_name, file_sha256, "
            "period_start, period_end, balance_start_cents, balance_end_cents, "
            "parser_profile, parser_version, status, imported_at) "
            "VALUES (?, 'a','x','x',?,?,?,0,0,'p','1','imported','now')",
            (i + 1, f"sha{i}", erster.isoformat(), ende.isoformat()))
    c.commit()
    yield c
    c.close()


def _buche(c, tag: date, cents: int, kategorie: str, gegenpartei: str) -> str:
    """Eine Buchung mit einem Teil; zurueck kommt ihre Kennung."""
    n = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] + 1
    kennung = hashlib.sha256(f"buchung{n}".encode()).hexdigest()
    sid = c.execute("SELECT id FROM statements WHERE period_start <= ? AND period_end >= ?",
                    (tag.isoformat(), tag.isoformat())).fetchone()[0]
    tid = c.execute(
        "INSERT INTO transactions (account_id, statement_id, booking_date, amount_cents, "
        "counterparty_norm, raw_text, seq_in_statement, dedup_hash, created_at) "
        "VALUES ('a',?,?,?,?,'x',?,?,'now')",
        (sid, tag.isoformat(), cents, gegenpartei, n, kennung)).lastrowid
    c.execute("INSERT INTO splits (transaction_id, amount_cents, mgmt_category_id, "
              "source, created_at, updated_at) VALUES (?,?,?,'rule','now','now')",
              (tid, cents, kategorie))
    c.commit()
    return kennung


def _miete(c, monate: int = 12, ab: int = 8) -> list[str]:
    """Eine Monatsmiete von 900 Euro, je Monat am 3., die letzten `monate` bis September 2026."""
    return [_buche(c, _monat(i).replace(day=3), -90_000, "wohnen/miete", "hausverwaltung")
            for i in range(ab, ab + monate)]


def _datei(tmp_path) -> dict:
    return yaml.safe_load((tmp_path / "config" / reihen.DATEI).read_text(encoding="utf-8"))


# ----------------------------------------------------------- Taxonomie


def test_the_flag_einmalig_comes_from_the_taxonomy_like_fix(tmp_path):
    from finctl.tax import taxonomy as tx
    from finctl.vorgaben import ORDNER

    c = connect(init_db(tmp_path / "t.db"))
    tx.load_into_db(c, ORDNER / "taxonomy.yaml")
    markiert = {r[0] for r in c.execute("SELECT id FROM mgmt_categories WHERE einmalig = 1")}
    assert markiert == {"immobilie/kaufnebenkosten"}

    spec = tmp_path / "taxonomie.yaml"
    spec.write_text(yaml.safe_dump({"management": {
        "anschaffung": {"name": "Anschaffung", "kind": "expense", "einmalig": True,
                        "children": {"gerät": "Gerät", "möbel": {"name": "Möbel"}}},
        "alltag": {"name": "Alltag", "kind": "expense",
                   "children": {"essen": "Essen", "reise": {"name": "Reise", "einmalig": True}}}}},
        allow_unicode=True), encoding="utf-8")
    tx.load_into_db(c, spec)
    markiert = {r[0] for r in c.execute("SELECT id FROM mgmt_categories WHERE einmalig = 1")}
    assert markiert == {"immobilie/kaufnebenkosten", "anschaffung", "anschaffung/gerät",
                        "anschaffung/möbel", "alltag/reise"}
    c.close()


# --------------------------------------------------------- Die Datei


def test_a_decision_is_written_read_back_and_beats_the_detection(haushalt, tmp_path):
    kennungen = _miete(haushalt)
    assert reihen.festlegen(haushalt, kennungen[0], 3, "Dauerauftrag alle drei Monate")
    eintrag = _datei(tmp_path)["reihen"]
    assert [(e["buchungen"], e["takt"], e["notiz"]) for e in eintrag] == [
        ([kennungen[0]], 3, "Dauerauftrag alle drei Monate")]
    assert eintrag[0]["notiz_vom"] == date.today().isoformat()

    assert reihen.festgelegt(haushalt) == {("hausverwaltung", "wohnen/miete"): 3}
    reihe = reihen.laden(haushalt, STICHTAG).nach_schluessel("hausverwaltung", "wohnen/miete")
    assert reihe.festgelegt and reihe.takt == 3
    # Eine Buchung der Reihe genuegt: auch eine andere zeigt auf dieselbe.
    assert reihen.notizen(haushalt)[("hausverwaltung", "wohnen/miete")].notiz.startswith("Dauer")


def test_a_series_that_is_already_set_that_way_is_left_alone(haushalt, tmp_path):
    kennungen = _miete(haushalt)
    # Ohne Festlegung gibt es nichts zurueckzunehmen, und die Datei entsteht nicht.
    assert not reihen.festlegen(haushalt, kennungen[0], None)
    assert not (tmp_path / "config" / reihen.DATEI).exists()

    assert reihen.festlegen(haushalt, kennungen[0], 1, "monatlich")
    gesehen = (tmp_path / "config" / reihen.DATEI).read_bytes()
    # Speichern ohne Aenderung, auch ueber eine andere Buchung der Reihe.
    assert not reihen.festlegen(haushalt, kennungen[5], 1, "monatlich")
    assert not reihen.festlegen(haushalt, kennungen[5], 1)
    assert (tmp_path / "config" / reihen.DATEI).read_bytes() == gesehen


def test_a_new_decision_replaces_the_old_one_and_can_be_taken_back(haushalt, tmp_path):
    kennungen = _miete(haushalt)
    reihen.festlegen(haushalt, kennungen[0], 3, "erst")
    vom = _datei(tmp_path)["reihen"][0]["notiz_vom"]
    # Anderer Takt, dieselbe Notiz: das Datum der Notiz bleibt.
    assert reihen.festlegen(haushalt, kennungen[4], 6)
    [e] = _datei(tmp_path)["reihen"]
    assert (e["takt"], e["notiz"], e["notiz_vom"]) == (6, "erst", vom)
    assert e["buchungen"] == [kennungen[4]]
    # Neue Notiz: neues Datum und neuer Text.
    reihen.festlegen(haushalt, kennungen[4], 6, "zweit")
    assert _datei(tmp_path)["reihen"][0]["notiz"] == "zweit"

    assert reihen.festlegen(haushalt, kennungen[2], None)
    assert _datei(tmp_path)["reihen"] == []
    assert reihen.festgelegt(haushalt) == {}
    assert not reihen.laden(haushalt, STICHTAG).nach_schluessel(
        "hausverwaltung", "wohnen/miete").festgelegt


def test_a_hand_written_entry_for_two_series_keeps_the_other_one(haushalt, tmp_path):
    miete = _miete(haushalt)
    essen = [_buche(haushalt, _monat(i).replace(day=9), -4_000, "konsum/essen", "markt")
             for i in range(8, 20)]
    (tmp_path / "config" / reihen.DATEI).write_text(yaml.safe_dump({"reihen": [
        {"buchungen": [miete[0], essen[0]], "takt": 2}]}), encoding="utf-8")
    assert reihen.festgelegt(haushalt) == {("hausverwaltung", "wohnen/miete"): 2,
                                           ("markt", "konsum/essen"): 2}
    reihen.festlegen(haushalt, miete[1], 12)
    assert reihen.festgelegt(haushalt) == {("hausverwaltung", "wohnen/miete"): 12,
                                           ("markt", "konsum/essen"): 2}


def test_einmalig_is_for_bookings_and_never_a_takt_of_a_series(haushalt, tmp_path):
    kennungen = _miete(haushalt)
    with pytest.raises(ValueError, match="einmalig"):
        reihen.festlegen(haushalt, kennungen[0], reihen.EINMALIG)
    assert reihen.einmalig_setzen(haushalt, kennungen[3], True)
    assert not reihen.einmalig_setzen(haushalt, kennungen[3], True)
    assert reihen.einmalige_hashes() == {kennungen[3]}
    assert reihen.festgelegt(haushalt) == {}
    [z] = reihen.einmalige_buchungen(haushalt)
    assert (z["buchung"], z["cents"], z["gegenpartei"], z["bekannt"]) == (
        kennungen[3], -90_000, "hausverwaltung", True)
    assert reihen.einmalig_setzen(haushalt, kennungen[3], False)
    assert not reihen.einmalig_setzen(haushalt, kennungen[3], False)
    assert reihen.einmalige_hashes() == frozenset()


def test_what_is_wrong_is_refused_with_a_reason(haushalt, tmp_path):
    kennungen = _miete(haushalt, 3)
    for falsch in ("x'); DROP TABLE splits; --", "", "ABC", 5):
        with pytest.raises(ValueError):
            reihen.hash_pruefen(falsch)
    with pytest.raises(ValueError, match="nicht bekannt"):
        reihen.festlegen(haushalt, "0" * 64, 1)
    with pytest.raises(ValueError, match="Takt"):
        reihen.festlegen(haushalt, kennungen[0], 5)
    with pytest.raises(ValueError, match="Takt"):
        reihen.takt_lesen("monatlich")
    # Eine Buchung ohne Gegenpartei hat keine Reihe.
    ohne = _buche(haushalt, date(2026, 8, 5), -100, "konsum/essen", "")
    with pytest.raises(ValueError, match="Reihe"):
        reihen.festlegen(haushalt, ohne, 1)
    # Eine kaputte Datei nennt den Eintrag, statt Kennungen ins SQL zu lassen.
    (tmp_path / "config" / reihen.DATEI).write_text(yaml.safe_dump({"reihen": [
        {"buchungen": ["x' OR '1'='1"], "takt": "einmalig"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Eintrag 1"):
        ag.bloecke()


# ------------------------------------------------- Der Block einmalig


def _bloecke(c) -> dict[tuple[str, str], int]:
    """Cent je (Block, Kategorie) ueber die ganze Zeit."""
    return messung.summiere(
        messung.monatssummen(c, von=date(2025, 1, 1), je_block=True),
        lambda z: (z.block, z.kategorie))


def test_a_booking_the_household_marked_lands_in_the_block_einmalig(haushalt):
    kennungen = _miete(haushalt)
    vorher = _bloecke(haushalt)
    assert vorher == {("fixkosten", "wohnen/miete"): -12 * 90_000}
    reihen.einmalig_setzen(haushalt, kennungen[0], True)
    assert _bloecke(haushalt) == {("fixkosten", "wohnen/miete"): -11 * 90_000,
                                  ("einmalig", "wohnen/miete"): -90_000}


def test_a_category_with_the_flag_lands_in_the_block_einmalig_before_every_other(haushalt):
    _buche(haushalt, date(2026, 3, 3), -2_000_000, "immobilie/kaufnebenkosten", "notar")
    gehalt = _buche(haushalt, date(2026, 3, 28), 500_000, "einkommen/gehalt", "firma")
    assert _bloecke(haushalt) == {("einmalig", "immobilie/kaufnebenkosten"): -2_000_000,
                                  ("gehalt", "einkommen/gehalt"): 500_000}
    # Der Block steht an erster Stelle: Was einmalig ist, gehoert in keinen anderen,
    # auch nicht ins Gehalt.
    reihen.einmalig_setzen(haushalt, gehalt, True)
    assert _bloecke(haushalt) == {("einmalig", "immobilie/kaufnebenkosten"): -2_000_000,
                                  ("einmalig", "einkommen/gehalt"): 500_000}
    assert ag.EINMALIG == "einmalig"
    assert next(b for b in ag.bloecke() if b.id == ag.EINMALIG).label == "Einmalig"


def test_the_block_is_evaluated_first_but_shown_where_the_sondereffekte_stood(haushalt):
    """Auswertung und Anzeige sind zwei Reihenfolgen: Eine einmalig gesetzte Buchung in einer
    Gehaltskategorie gehoert in `einmalig`, und die Seiten zeigen die Bloecke weiter
    in der alten Folge (Gehalt, dann Einmalig)."""
    ids = [b.id for b in ag.bloecke()]
    assert ids[:2] == ["gehalt", "einmalig"]
    assert ids.index("einmalig") < ids.index("miete")
    sql = ag._case_expression()
    assert sql.index("'einmalig'") < sql.index("'gehalt'")
    gehalt = _buche(haushalt, date(2026, 3, 28), 500_000, "einkommen/gehalt", "firma")
    assert _bloecke(haushalt) == {("gehalt", "einkommen/gehalt"): 500_000}
    reihen.einmalig_setzen(haushalt, gehalt, True)
    assert _bloecke(haushalt) == {("einmalig", "einkommen/gehalt"): 500_000}


def test_a_marked_booking_leaves_the_base_of_the_projection(haushalt):
    """Aus der Basis der Hochrechnung faellt, was einmalig ist: Eine Buchung, einmalig
    gesetzt, zaehlt weder im Jahreswert der Kategorie noch irgendwo sonst."""
    # Zwei Einkaeufe ohne Takt: ihre Summe zaehlt im Rest, aufs Jahr.
    gross = _buche(haushalt, date(2026, 3, 3), -120_000, "konsum/essen", "markt")
    _buche(haushalt, date(2026, 5, 20), -12_000, "konsum/essen", "markt")
    f = ag.fenster(haushalt, bis=STICHTAG)
    assert f is not None and f.monate == 12
    assert jm._base_kategorien(haushalt, f)["konsum"]["konsum/essen"] == -132_000

    reihen.einmalig_setzen(haushalt, gross, True)
    basis = jm._base_kategorien(haushalt, f)
    assert basis["konsum"]["konsum/essen"] == -12_000
    assert ag.EINMALIG not in jm.FROM_BASE
    assert not any(ag.EINMALIG in b for k, b in basis.items() if k in jm.FROM_BASE)
    # Gemessen steht es weiter, im eigenen Block: nichts verschwindet aus dem Hauptbuch.
    assert ag.measure(haushalt, f)[ag.EINMALIG] == -120_000


def test_a_marked_month_of_a_series_does_not_shorten_its_year(haushalt):
    """Eine Miete, deren einer Monat einmalig gesetzt ist, bleibt eine Reihe mit Takt:
    Ihr Jahreswert sind zwoelf Termine, nicht elf. Die gesetzte Buchung steht im Block
    `einmalig` und zaehlt dort."""
    kennungen = _miete(haushalt)
    f = ag.fenster(haushalt, bis=STICHTAG)
    assert jm._base_kategorien(haushalt, f)["fixkosten"]["wohnen/miete"] == -12 * 90_000
    reihen.einmalig_setzen(haushalt, kennungen[5], True)
    assert jm._base_kategorien(haushalt, f)["fixkosten"]["wohnen/miete"] == -12 * 90_000
    assert ag.measure(haushalt, f)[ag.EINMALIG] == -90_000


def test_the_block_of_a_category_without_bookings_is_found_too(haushalt):
    from finctl.forecast import prognosebasis as pb

    assert pb._block_fuer(haushalt, "immobilie/kaufnebenkosten") == ag.EINMALIG
    assert pb._block_fuer(haushalt, "konsum/essen") == "konsum"
    # Auch mit einer markierten Buchung im SQL: die Abfrage kennt die Buchung nicht,
    # und das darf sie nicht stoeren.
    reihen.einmalig_setzen(haushalt, _miete(haushalt, 2)[0], True)
    assert pb._block_fuer(haushalt, "wohnen/miete") == "fixkosten"


# ------------------------------------------------------- Die Reihe


def test_what_is_einmalig_is_no_part_of_a_series(haushalt):
    """Ein Termin aus einer einmaligen Buchung schriebe sie fort."""
    kennungen = _miete(haushalt)
    reihe = reihen.laden(haushalt, STICHTAG).nach_schluessel("hausverwaltung", "wohnen/miete")
    assert reihe.takt == 1 and len(reihe.teile) == 12
    # Die vorletzte Buchung ist einmalig; die Reihe sieht elf und laeuft weiter.
    reihen.einmalig_setzen(haushalt, kennungen[-2], True)
    reihe = reihen.laden(haushalt, STICHTAG).nach_schluessel("hausverwaltung", "wohnen/miete")
    assert len(reihe.teile) == 11 and kennungen[-2] not in {t.dedup_hash for t in reihe.teile}
    # Eine Kaufnebenkosten-Buchung bildet gar keine Reihe.
    _buche(haushalt, date(2026, 3, 3), -2_000_000, "immobilie/kaufnebenkosten", "notar")
    assert reihen.laden(haushalt, STICHTAG).nach_schluessel(
        "notar", "immobilie/kaufnebenkosten") is None


def test_the_series_is_found_again_in_the_ledger_as_the_decision_names_it(haushalt):
    kennungen = _miete(haushalt)
    assert tk.takt_name(1) == "monatlich"
    reihen.festlegen(haushalt, kennungen[0], tk.UNREGELMAESSIG)
    reihe = reihen.laden(haushalt, STICHTAG).nach_schluessel("hausverwaltung", "wohnen/miete")
    assert reihe.festgelegt and reihe.takt == tk.UNREGELMAESSIG and reihe.beitrag is None


# ------------------------------------------------ Schreibweisen zusammenfuehren


def _schreibweisen(c, ab: int = 8) -> tuple[list[str], list[str]]:
    """Dieselbe Miete unter zwei Schreibweisen, je ein halbes Jahr hintereinander."""
    alt = [_buche(c, _monat(i).replace(day=3), -90_000, "wohnen/miete", "verwaltung alt")
           for i in range(ab, ab + 6)]
    neu = [_buche(c, _monat(i).replace(day=3), -90_000, "wohnen/miete", "verwaltung neu")
           for i in range(ab + 6, ab + 12)]
    return alt, neu


def test_a_merge_is_written_read_back_and_makes_one_series_of_twelve_terms(haushalt, tmp_path):
    _schreibweisen(haushalt)
    assert reihen.zusammen() == {} and not (tmp_path / "config" / reihen.DATEI).exists()
    assert reihen.zusammenfuehren(haushalt, "verwaltung alt", "verwaltung neu")
    assert _datei(tmp_path) == {"reihen": [], "zusammen": {"verwaltung alt": "verwaltung neu"}}
    assert reihen.zusammen() == {"verwaltung alt": "verwaltung neu"}

    reihe = reihen.laden(haushalt, STICHTAG).nach_schluessel("verwaltung neu", "wohnen/miete")
    assert (reihe.takt, len(reihe.termine), reihe.beitrag.laeuft) == (1, 12, True)
    assert reihe.beitrag.jahreswert == -1_080_000 and reihe.schreibweisen == ("verwaltung alt",)
    # Die Reihe heisst nach ihrem Ziel; die alte Schreibweise ist keine eigene mehr.
    alle = reihen.laden(haushalt, STICHTAG).reihen
    assert [r.gegenpartei for r in alle] == ["verwaltung neu"]


def test_the_same_merge_again_changes_nothing_and_can_be_taken_back(haushalt, tmp_path):
    _schreibweisen(haushalt)
    reihen.zusammenfuehren(haushalt, "verwaltung alt", "verwaltung neu")
    gesehen = (tmp_path / "config" / reihen.DATEI).read_bytes()
    assert not reihen.zusammenfuehren(haushalt, "verwaltung alt", "verwaltung neu")
    assert (tmp_path / "config" / reihen.DATEI).read_bytes() == gesehen

    assert reihen.zusammenfuehren(haushalt, "verwaltung alt", None)
    assert reihen.zusammen() == {}
    assert not reihen.zusammenfuehren(haushalt, "verwaltung alt", None)
    assert sorted(r.gegenpartei for r in reihen.laden(haushalt, STICHTAG).reihen) == [
        "verwaltung alt", "verwaltung neu"]


def test_without_a_merge_the_file_is_never_created(haushalt, tmp_path):
    _schreibweisen(haushalt)
    assert not reihen.zusammenfuehren(haushalt, "verwaltung alt", None)
    assert not (tmp_path / "config" / reihen.DATEI).exists()


def test_a_merge_that_makes_no_sense_is_refused_with_a_reason(haushalt, tmp_path):
    _schreibweisen(haushalt)
    _buche(haushalt, date(2026, 3, 9), -2_000, "konsum/essen", "markt")
    for schreibweise, ziel, text in (
            ("verwaltung alt", "verwaltung alt", "nicht zu sich selbst"),
            ("", "verwaltung neu", "nicht zu sich selbst"),
            ("verwaltung alt", "", "nicht zu sich selbst"),
            ("verwaltung alt", "unbekannt", "Kategorie teilen"),
            ("unbekannt", "verwaltung neu", "Kategorie teilen"),
            ("verwaltung alt", "markt", "Kategorie teilen")):
        with pytest.raises(ValueError, match=text):
            reihen.zusammenfuehren(haushalt, schreibweise, ziel)
    assert not (tmp_path / "config" / reihen.DATEI).exists()
    reihen.zusammenfuehren(haushalt, "verwaltung alt", "verwaltung neu")
    with pytest.raises(ValueError, match="Kreis"):
        reihen.zusammenfuehren(haushalt, "verwaltung neu", "verwaltung alt")
    assert reihen.zusammen() == {"verwaltung alt": "verwaltung neu"}


def test_a_file_with_a_circle_or_a_broken_entry_names_the_file(haushalt, tmp_path):
    for inhalt, text in (
            ({"zusammen": {"a": "b", "b": "a"}}, "reihen_custom.yaml: .*Kreis"),
            ({"zusammen": {"a": "a"}}, "zeigt auf sich selbst"),
            ({"zusammen": {"a": 3}}, "keine Gegenpartei"),
            ({"zusammen": ["a"]}, "keine Zuordnung")):
        (tmp_path / "config" / reihen.DATEI).write_text(yaml.safe_dump(inhalt), encoding="utf-8")
        with pytest.raises(ValueError, match=text):
            reihen.zusammen()


def test_a_decision_made_through_either_spelling_is_one_decision_for_the_merged_series(
        haushalt, tmp_path):
    alt, neu = _schreibweisen(haushalt)
    reihen.zusammenfuehren(haushalt, "verwaltung alt", "verwaltung neu")
    # Eine Buchung der alten Schreibweise spricht die Reihe an, wie sie die Vorschauen bilden.
    assert reihen.festlegen(haushalt, alt[0], 2, "alle zwei Monate")
    assert reihen.festgelegt(haushalt) == {("verwaltung neu", "wohnen/miete"): 2}
    assert reihen.notizen(haushalt)[("verwaltung neu", "wohnen/miete")].notiz.startswith("alle")
    # Dieselbe Festlegung ueber eine Buchung der neuen aendert nichts.
    assert not reihen.festlegen(haushalt, neu[0], 2, "alle zwei Monate")
    # Eine andere ersetzt sie; die Zusammenfuehrung bleibt in der Datei stehen.
    assert reihen.festlegen(haushalt, neu[0], 1)
    assert _datei(tmp_path)["zusammen"] == {"verwaltung alt": "verwaltung neu"}
    assert [e["takt"] for e in _datei(tmp_path)["reihen"]] == [1]
    assert reihen.festlegen(haushalt, alt[1], None)
    assert _datei(tmp_path) == {"reihen": [], "zusammen": {"verwaltung alt": "verwaltung neu"}}


def test_marking_a_booking_einmalig_keeps_the_merge(haushalt, tmp_path):
    alt, _ = _schreibweisen(haushalt)
    reihen.zusammenfuehren(haushalt, "verwaltung alt", "verwaltung neu")
    assert reihen.einmalig_setzen(haushalt, alt[2], True)
    assert _datei(tmp_path)["zusammen"] == {"verwaltung alt": "verwaltung neu"}
    assert reihen.einmalig_setzen(haushalt, alt[2], False)
    assert _datei(tmp_path) == {"reihen": [], "zusammen": {"verwaltung alt": "verwaltung neu"}}


def test_a_merge_reaches_the_base_of_the_projection(haushalt):
    """Eine Jahreszahlung unter zwei Schreibweisen, ein Jahr auseinander: Beide laufen
    anderthalb Jahre und zaehlten doppelt. Als eine Reihe zaehlt sie einmal."""
    _buche(haushalt, date(2025, 7, 24), -7_200, "wohnen/miete", "steuer alt")
    _buche(haushalt, date(2026, 7, 24), -7_200, "wohnen/miete", "steuer neu")
    f = ag.fenster(haushalt, bis=STICHTAG)
    assert jm._base_kategorien(haushalt, f)["fixkosten"]["wohnen/miete"] == -14_400
    reihen.zusammenfuehren(haushalt, "steuer alt", "steuer neu")
    assert jm._base_kategorien(haushalt, f)["fixkosten"]["wohnen/miete"] == -7_200


# ------------------------------------------------------ Die Seite /reihen

DB = Path("data/finance.db")
kein_hauptbuch = pytest.mark.skipif(not DB.exists(), reason="kein Hauptbuch")


@pytest.fixture
def seite():
    """Der Client der App; `reihen_custom.yaml` wird danach zurueckgestellt, denn die
    Tests eines Prozesses teilen sich die Kopie von `config/`."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from finctl.web.server import app

    pfad = reihen.CONFIG_DIR / reihen.DATEI
    vorher = pfad.read_bytes() if pfad.exists() else None
    yield TestClient(app)
    if vorher is None:
        pfad.unlink(missing_ok=True)
    else:
        pfad.write_bytes(vorher)


def _kennung_der_ersten_reihe(html: str) -> tuple[str, str]:
    """(Kennung im Markup, Kennung einer Buchung der Reihe) der ersten Reihe der Seite, die
    noch keinen Takt festgelegt hat: Auf eine festgelegte schriebe der Test ueber."""
    for zeile in re.finditer(r'<tr id="(r[0-9a-f]+)" class="klappbar".*?</tr>', html, re.S):
        if "festgelegt</span>" in zeile.group(0):
            continue
        treffer = re.search(
            rf'data-id="{zeile.group(1)}" data-buchung="([0-9a-f]+)"\s+onclick="festlegen', html)
        if treffer:
            return zeile.group(1), treffer.group(1)
    pytest.skip("keine Reihe ohne festgelegten Takt in diesem Haushalt")


@kein_hauptbuch
def test_the_page_lists_fixed_series_and_all_shows_more(seite):
    antwort = seite.get("/reihen")
    assert antwort.status_code == 200 and "<h1>Reihen</h1>" in antwort.text
    # Die rote Pill ist harten Grenzverletzungen vorbehalten: eine beendete Reihe ist keine.
    assert "pill solid" not in antwort.text
    assert 'href="/reihen"' in antwort.text                       # in der Navigation
    fest = antwort.text.count('class="klappbar"')
    alle = seite.get("/reihen?zeige=alle").text.count('class="klappbar"')
    if not fest:
        pytest.skip("keine Reihe mit festem Takt")
    assert alle >= fest
    # Die Auswahl traegt je Option die Zahl, die sie zeigt.
    assert f'Feste Takte <span class="zahl">{fest}</span>' in antwort.text.replace("\n", " ")


@kein_hauptbuch
def test_a_decision_through_the_page_is_written_once_and_taken_back(seite):
    _kennung, buchung = _kennung_der_ersten_reihe(seite.get("/reihen").text)
    pfad = reihen.CONFIG_DIR / reihen.DATEI
    vorher = reihen.lesen()
    antwort = seite.post("/api/reihen/takt", json={"buchung": buchung, "takt": "12",
                                                   "notiz": "von Hand"})
    assert antwort.status_code == 200 and antwort.json() == {"ok": True, "geschrieben": True}
    assert "von Hand" in pfad.read_text(encoding="utf-8")
    [neu] = [e for e in reihen.lesen() if e not in vorher]
    assert (neu.buchungen, neu.takt, neu.notiz) == ((buchung,), 12, "von Hand")
    html = seite.get("/reihen").text
    assert "festgelegt" in html and "Festlegung zurücknehmen" in html and "von Hand" in html

    gesehen = pfad.read_bytes()
    nochmal = seite.post("/api/reihen/takt", json={"buchung": buchung, "takt": "12",
                                                   "notiz": "von Hand"})
    assert nochmal.json()["geschrieben"] is False and pfad.read_bytes() == gesehen

    zurueck = seite.post("/api/reihen/takt", json={"buchung": buchung, "takt": ""})
    assert zurueck.json()["geschrieben"] is True
    assert reihen.lesen() == vorher


@kein_hauptbuch
def test_einmalig_through_the_page_lists_the_booking_and_takes_it_back(seite):
    vorher = reihen.einmalige_hashes()
    html = seite.get("/reihen").text
    knopf = r'data-buchung="([0-9a-f]+)"\s+onclick="einmalig\(this, true\)"'
    treffer = [b for b in re.findall(knopf, html) if b not in vorher]
    if not treffer:
        pytest.skip("keine Buchung in einer Reihe, die noch nicht einmalig gesetzt ist")
    buchung = treffer[0]
    assert not re.search(rf'data-buchung="{buchung}"\s+onclick="einmalig\(this, false\)"', html)
    assert seite.post("/api/reihen/einmalig",
                      json={"buchung": buchung, "einmalig": True}).json()["geschrieben"]
    assert reihen.einmalige_hashes() == vorher | {buchung}
    nach = seite.get("/reihen").text
    assert re.search(rf'data-buchung="{buchung}"\s+onclick="einmalig\(this, false\)"', nach)
    assert seite.post("/api/reihen/einmalig",
                      json={"buchung": buchung, "einmalig": False}).json()["geschrieben"]
    assert reihen.einmalige_hashes() == vorher


@pytest.fixture
def haushalt_seite(haushalt, tmp_path, monkeypatch):
    """Die Seite auf dem erfundenen Haushalt: Datenbank und Stichtag sind die der Tests.

    Die Seite oeffnet je Aufruf eine eigene Verbindung (in einem anderen Thread)."""
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from finctl.web.routen import reihen as seite_reihen
    from finctl.web.server import app

    monkeypatch.setattr(seite_reihen, "conn", lambda: connect(tmp_path / "t.db"))
    monkeypatch.setattr(seite_reihen._stichtag, "stichtag", lambda c: STICHTAG)
    return TestClient(app)


def test_the_page_proposes_two_spellings_and_merges_them_on_a_click(haushalt_seite, haushalt,
                                                                   tmp_path):
    _schreibweisen(haushalt)
    html = haushalt_seite.get("/reihen").text
    assert 'id="vorschlaege"' in html
    assert re.search(r'data-schreibweise="verwaltung alt"\s+data-ziel="verwaltung neu"', html)
    # Ein Vorschlag steht nur da; geschrieben wird erst auf den Klick.
    assert not (tmp_path / "config" / reihen.DATEI).exists()

    antwort = haushalt_seite.post("/api/reihen/zusammen", json={
        "schreibweise": "verwaltung alt", "ziel": "verwaltung neu"})
    assert antwort.status_code == 200 and antwort.json() == {"ok": True, "geschrieben": True}
    assert reihen.zusammen() == {"verwaltung alt": "verwaltung neu"}

    nach = haushalt_seite.get("/reihen").text
    assert 'id="vorschlaege"' not in nach
    assert "zusammengeführt" in nach
    # Die Reihe heisst nach dem Ziel, und die alte Schreibweise steht mit Knopf zum Trennen da.
    assert nach.count('class="klappbar"') == 1
    assert re.search(
        r'data-schreibweise="verwaltung alt"\s+onclick="zusammenfuehren\(this\)">Trennen', nach)

    gesehen = (tmp_path / "config" / reihen.DATEI).read_bytes()
    nochmal = haushalt_seite.post("/api/reihen/zusammen", json={
        "schreibweise": "verwaltung alt", "ziel": "verwaltung neu"})
    assert nochmal.json()["geschrieben"] is False
    assert (tmp_path / "config" / reihen.DATEI).read_bytes() == gesehen

    zurueck = haushalt_seite.post("/api/reihen/zusammen", json={
        "schreibweise": "verwaltung alt", "ziel": ""})
    assert zurueck.json()["geschrieben"] is True and reihen.zusammen() == {}


def test_a_series_offers_the_other_series_of_its_category_to_belong_to(haushalt_seite,
                                                                      haushalt):
    _schreibweisen(haushalt)
    _buche(haushalt, date(2026, 3, 9), -2_000, "konsum/essen", "markt")
    html = haushalt_seite.get("/reihen?zeige=alle").text
    # Je Reihe die Reihen derselben Kategorie, nicht die einer anderen und nicht sie selbst.
    auswahl = re.findall(r'<select id="z-r[0-9a-f]+" data-no-combo>(.*?)</select>', html, re.S)
    assert len(auswahl) == 2
    for optionen in auswahl:
        assert "markt" not in optionen
    assert sorted("verwaltung alt" in o for o in auswahl) == [False, True]
    assert "zuletzt 2026-08-03" in html


def test_the_page_proposes_nothing_for_a_salary_with_the_month_in_its_name(haushalt_seite,
                                                                          haushalt):
    for jahr in (2025, 2026):
        for monat in range(1, 9 if jahr == 2026 else 13):
            _buche(haushalt, date(jahr, monat, 28), 450_000, "einkommen/gehalt",
                   f"arbeitgeber gehalt {monat}{jahr}")
    html = haushalt_seite.get("/reihen?zeige=alle").text
    assert 'id="vorschlaege"' not in html


def test_a_merge_the_server_cannot_accept_is_refused_and_writes_nothing(haushalt_seite, haushalt,
                                                                       tmp_path):
    _schreibweisen(haushalt)
    for body in ({"schreibweise": "verwaltung alt", "ziel": "verwaltung alt"},
                 {"schreibweise": "verwaltung alt", "ziel": "gibt es nicht"},
                 {"schreibweise": "", "ziel": "verwaltung neu"},
                 {"ziel": "verwaltung neu"}):
        antwort = haushalt_seite.post("/api/reihen/zusammen", json=body)
        assert antwort.status_code == 400 and antwort.json()["error"], body
    assert not (tmp_path / "config" / reihen.DATEI).exists()


@kein_hauptbuch
def test_a_request_the_server_cannot_read_is_refused_and_writes_nothing(seite):
    pfad = reihen.CONFIG_DIR / reihen.DATEI
    existierte = pfad.exists()
    for pfad_api, body in (
            ("/api/reihen/takt", {"buchung": "0" * 64, "takt": "1"}),
            ("/api/reihen/takt", {"buchung": "x' OR 1=1 --", "takt": "1"}),
            ("/api/reihen/takt", {"buchung": "", "takt": "1"}),
            ("/api/reihen/takt", {"buchung": "0" * 64, "takt": "einmalig"}),
            ("/api/reihen/einmalig", {"buchung": "0" * 64, "einmalig": True}),
            ("/api/reihen/einmalig", {"buchung": "'; --", "einmalig": True})):
        antwort = seite.post(pfad_api, json=body)
        assert antwort.status_code == 400 and antwort.json()["error"], body
    assert pfad.exists() == existierte
