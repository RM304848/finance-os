"""Kommentare werden Notizen: `finctl umstellen` (Schritt 5, N.2).

Alle Dateien hier sind erfunden. Gezaehlt wird, was Entscheidung 2 und 3 und N.0 (Nummern 8
bis 10) sagen: In welcher Lage steht ein Kommentar, in welche Notiz geht er, was faellt weg.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from finctl import umstellen
from finctl.umstellen_form import KOEPFE
from finctl.umstellen_lagen import lesen


def _gelesen(u) -> dict:
    assert not u.fehler, u.fehler
    assert u.neu is not None
    return yaml.safe_load(u.neu)


def _lagen(u) -> list[tuple[str, int]]:
    return [(s.lage, s.zeilen) for s in u.stuecke]


# ------------------------------------------------------------------ die Lagen

#: Eine Liste von Zielen: Kopf, Abschnitt, Block ueber einem Eintrag, ein Block zwischen
#: zwei Feldern, ein Kommentar hinter dem Wert.
ZIELE = """\
# Die Ziele des Haushalts.
#
# Jedes nennt Betrag und Datum.

ziele:

  # ------------------------------------------------------------ Rücklagen
  # Gilt fuer die folgenden Ziele.

  # Das Polster, bevor etwas anderes zaehlt.
  - id: polster
    name: Polster
    cents: 1000000          # 10.000,00
    stichtag: 2030-01-01    # spaetestens, nicht frueher
    # Zwischen zwei Feldern.
    basis: [giro]

  - id: urlaub
    name: Urlaub
    cents: 200000
"""


def test_the_five_layers_land_where_the_plan_says():
    u = umstellen.umwandeln("goals.yaml", ZIELE)
    assert [(s.lage, s.von + 1) for s in u.stuecke] == [
        ("K", 1), ("A", 7), ("E", 10), ("F", 13), ("F", 14), ("E", 15)]
    spec = _gelesen(u)

    # Der Kopf und der Abschnitt gehen in die Notiz des Bereichs; der Abschnitt nennt,
    # vor welchem Eintrag er stand, und ist nicht in jeden Eintrag kopiert.
    bereich = spec["notizen"]["bereich"]["notiz"]
    assert bereich.startswith("Die Ziele des Haushalts.\n\nJedes nennt Betrag und Datum.")
    assert "Stand vor `polster`:\n" + "-" * 60 + " Rücklagen" in bereich
    assert "Gilt fuer die folgenden Ziele." in bereich
    assert "Gilt fuer" not in spec["ziele"][1].get("notiz", "")

    # Ein Block am Eintrag, ein Feldkommentar mit dem Feldnamen, ein Block im Eintrag:
    # in der Reihenfolge der Datei.
    polster = spec["ziele"][0]
    assert polster["notiz"] == (
        "Das Polster, bevor etwas anderes zaehlt.\n\n"
        "`stichtag`: spaetestens, nicht frueher\n\n"
        "Zwischen zwei Feldern.")
    assert "notiz_vom" not in polster          # kein Datum: aus der Zeit vor den Notizen
    assert "notiz" not in spec["ziele"][1]


def test_a_comment_that_only_repeats_the_value_in_euro_falls_away():
    u = umstellen.umwandeln("goals.yaml", ZIELE)
    weg = [s for s in u.stuecke if s.weg]
    assert [s.text for s in weg] == ["10.000,00"]
    assert weg[0].weg == "wiederholt den Wert in Euro"
    assert "10.000,00" not in u.neu


@pytest.mark.parametrize("kommentar, bleibt", [
    ("10.000,00", False),              # nur der Wert
    ("10.000,00 €", False),
    ("10.000,00 EUR", False),
    ("10.000,00 Euro", False),
    ("10.000", False),                 # ohne Cent, derselbe Wert
    ("~10.000,00", True),              # kein ~ davor
    ("10.000,00 -- vereinbart", True),  # sagt mehr als den Wert
    ("12.000,00", True),               # eine andere Zahl
    ("zehntausend", True),
])
def test_the_four_conditions_for_a_euro_repeat(kommentar, bleibt):
    text = f"ziele:\n  - id: a\n    name: A\n    cents: 1000000   # {kommentar}\n"
    u = umstellen.umwandeln("goals.yaml", text)
    assert [bool(s.weg) for s in u.stuecke] == [not bleibt]


def test_a_euro_repeat_needs_a_cents_field_and_one_line():
    # Feld ohne `_cents`
    u = umstellen.umwandeln("goals.yaml", "ziele:\n  - id: a\n    betrag: 100   # 1,00\n")
    assert not u.weggefallen
    # Fortsetzungszeile in derselben Spalte
    u = umstellen.umwandeln(
        "goals.yaml", "ziele:\n  - id: a\n    cents: 100   # 1,00\n"
                      "                 # und mehr\n")
    assert not u.weggefallen
    assert _gelesen(u)["ziele"][0]["notiz"] == "`cents`: 1,00\nund mehr"
    # Keine ganze Zahl
    u = umstellen.umwandeln("goals.yaml", "ziele:\n  - id: a\n    cents: '100'   # 1,00\n")
    assert not u.weggefallen


def test_a_field_comment_continues_in_the_same_column():
    text = ("ziele:\n"
            "  - id: a\n"
            "    name: A            # erste Zeile\n"
            "                       # zweite Zeile\n"
            "    cents: 100\n")
    u = umstellen.umwandeln("goals.yaml", text)
    assert _lagen(u) == [("F", 2)]
    assert _gelesen(u)["ziele"][0]["notiz"] == "`name`: erste Zeile\nzweite Zeile"


def test_a_block_over_several_lines_keeps_its_lines_and_its_gaps():
    text = ("ziele:\n"
            "  - id: a\n"
            "    # Erste Zeile.\n"
            "    #\n"
            "    #   eingerueckt\n"
            "    #\n"
            "    # Letzte Zeile.\n"
            "    cents: 100\n")
    u = umstellen.umwandeln("goals.yaml", text)
    assert _gelesen(u)["ziele"][0]["notiz"] == "Erste Zeile.\n\n  eingerueckt\n\nLetzte Zeile."


def test_a_file_without_comments_is_left_alone_and_a_second_run_changes_nothing():
    u = umstellen.umwandeln("goals.yaml", "ziele:\n  - id: a\n    cents: 100\n")
    assert u.neu is None and not u.stuecke
    erste = umstellen.umwandeln("goals.yaml", ZIELE)
    zweite = umstellen.umwandeln("goals.yaml", erste.neu)
    assert zweite.neu is None and not zweite.fehler and not zweite.stuecke


# ----------------------------------------------------------- Grenzfaelle (Nr. 10)


def _ort_des_blocks(name: str, text: str) -> list[tuple[str, str, str]]:
    u = umstellen.umwandeln(name, text)
    assert not u.fehler, u.fehler
    return [(s.lage, s.ziel[0], s.hinweis or s.ort) for s in u.stuecke if not s.weg]


def test_a_dash_line_always_starts_a_section_even_right_above_an_entry():
    text = "ziele:\n  # ---- Rücklagen\n  - id: a\n    cents: 100\n"
    assert _ort_des_blocks("goals.yaml", text) == [("A", "bereich", "Stand vor `a`")]


def test_a_block_without_a_gap_belongs_to_the_key_below_it_even_at_the_start():
    text = "# Eine Rate fuer alles.\ninflation_pa: 0.02\n"
    assert _ort_des_blocks("assumptions.yaml", text) == [("S", "einstellung", "inflation_pa")]


def test_a_block_above_the_key_of_the_entry_list_is_the_head():
    text = "# Was das hier ist.\nziele:\n  - id: a\n    cents: 100\n"
    assert _ort_des_blocks("goals.yaml", text) == [("K", "bereich", "")]


def test_a_block_with_a_gap_between_settings_is_a_section():
    text = "a: 1\n\n# Gilt fuer b und c.\n\nb: 2\nc: 3\n"
    assert _ort_des_blocks("assumptions.yaml", text) == [("A", "bereich", "Stand vor `b`")]


def test_a_block_above_a_mapping_by_account_and_at_the_end_go_to_the_area():
    text = ("account_budgets:\n  dkb: 100\n\n# Wozu jedes Konto da ist.\n\naccount_roles:\n"
            "  dkb:\n    role: operating\n\n# Am Schluss.\n")
    u = umstellen.umwandeln("forecast_custom.yaml", text)
    assert [(s.lage, s.hinweis) for s in u.stuecke] == [
        ("A", "Stand vor `account_roles`"), ("–", "Am Ende der Datei")]
    notiz = _gelesen(u)["notizen"]["bereich"]["notiz"]
    assert "Wozu jedes Konto da ist." in notiz and "Am Schluss." in notiz


def test_a_block_directly_above_a_mapping_by_account_is_marked_with_its_key():
    text = ("account_budgets:\n  dkb: 100\naccount_roles:\n  dkb:\n    role: operating\n")
    text = text.replace("account_roles:\n", "# Wozu jedes Konto da ist.\naccount_roles:\n")
    u = umstellen.umwandeln("forecast.yaml", text)
    assert [(s.lage, s.hinweis) for s in u.stuecke] == [("–", "Zu `account_roles`")]


# ------------------------------------- Block unter einem Eintrag (N.2b, Abnahme N.2, Nr. 3)

#: Zwei Ziele; der Block unter dem ersten steht mit Leerzeile danach, damit nichts unter ihm
#: haengt. Die Spalte des Blocks ist der Platzhalter `{s}`.
UNTER_LISTE = ("ziele:\n  - id: a\n    cents: 100\n{s}# Zu a.\n\n  - id: b\n    cents: 200\n")


def test_a_block_without_a_gap_before_it_at_the_depth_of_the_fields_belongs_to_the_entry_above():
    u = umstellen.umwandeln("goals.yaml", UNTER_LISTE.format(s="    "))
    assert [(s.lage, s.ziel, s.hinweis) for s in u.stuecke] == [("E", ("eintrag", "ziele", 0), "")]
    assert _gelesen(u)["ziele"][0]["notiz"] == "Zu a."
    assert "notizen" not in _gelesen(u)


@pytest.mark.parametrize("spalte", ["", "  ", "      "])
def test_a_block_at_another_depth_than_the_fields_stays_a_section_that_says_what_it_follows(spalte):
    u = umstellen.umwandeln("goals.yaml", UNTER_LISTE.format(s=spalte))
    assert [(s.lage, s.ziel, s.hinweis) for s in u.stuecke] == [
        ("A", ("bereich",), "Stand nach `a`")]
    assert _gelesen(u)["notizen"]["bereich"]["notiz"] == "Stand nach `a`:\nZu a."
    assert "notiz" not in _gelesen(u)["ziele"][0]


def test_a_block_with_a_gap_before_it_stays_as_it_was_whatever_its_depth():
    text = UNTER_LISTE.format(s="    ").replace("cents: 100\n", "cents: 100\n\n")
    u = umstellen.umwandeln("goals.yaml", text)
    assert [(s.lage, s.hinweis) for s in u.stuecke] == [("A", "Stand vor `b`")]


def test_a_dash_line_under_an_entry_is_still_a_section_for_what_follows():
    text = UNTER_LISTE.format(s="    ").replace("# Zu a.", "# ---- Rücklagen")
    u = umstellen.umwandeln("goals.yaml", text)
    assert [(s.lage, s.hinweis) for s in u.stuecke] == [("A", "Stand vor `b`")]


def test_a_block_with_something_directly_below_it_still_belongs_to_what_is_below():
    text = "ziele:\n  - id: a\n    cents: 100\n    # Zu b?\n  - id: b\n    cents: 200\n"
    u = umstellen.umwandeln("goals.yaml", text)
    assert [(s.lage, s.ziel) for s in u.stuecke] == [("E", ("eintrag", "ziele", 1))]


def test_a_block_under_the_last_entry_of_the_file_follows_the_same_two_rules():
    feld = umstellen.umwandeln("goals.yaml", "ziele:\n  - id: a\n    cents: 1\n    # Zu a.\n")
    assert [(s.lage, s.ziel) for s in feld.stuecke] == [("E", ("eintrag", "ziele", 0))]
    eintrag = umstellen.umwandeln("goals.yaml", "ziele:\n  - id: a\n    cents: 1\n  # Ende.\n")
    assert [(s.lage, s.hinweis) for s in eintrag.stuecke] == [("A", "Stand nach `a`")]
    luecke = umstellen.umwandeln("goals.yaml", "ziele:\n  - id: a\n    cents: 1\n\n  # Ende.\n")
    assert [(s.lage, s.hinweis) for s in luecke.stuecke] == [("–", "Am Ende der Datei")]


def test_a_block_at_the_depth_of_the_entry_at_the_end_of_a_mapping_is_a_section():
    text = ("renten:\n  grv:\n    betrag: 100\n  # Zu allen.\n\nandere: 1\n")
    u = umstellen.umwandeln("renten_custom.yaml", text)
    assert [(s.lage, s.ziel, s.hinweis) for s in u.stuecke] == [
        ("A", ("bereich",), "Stand nach `grv`")]
    text = text.replace("  # Zu allen.", "    # Zu grv.")
    u = umstellen.umwandeln("renten_custom.yaml", text)
    assert [(s.lage, s.ziel) for s in u.stuecke] == [("E", ("eintrag", "renten", 0))]
    assert _gelesen(u)["renten"]["grv"]["notiz"] == "Zu grv."


def test_the_depth_of_an_entry_that_is_only_a_value_is_its_own():
    # `dkb: 100` hat keine Felder; unter ihm steht nichts tiefer als sein Schluessel.
    text = ("account_budgets:\n  dkb: 100\n  # Warnung zu dkb.\n\naccount_roles:\n  dkb:\n"
            "    role: operating\n")
    u = umstellen.umwandeln("forecast.yaml", text)
    assert [(s.lage, s.ziel) for s in u.stuecke] == [("E", ("eintrag", "account_roles", 0))]
    assert _gelesen(u)["account_roles"]["dkb"]["notiz"] == "Budget: Warnung zu dkb."
    tiefer = umstellen.umwandeln("forecast.yaml", text.replace("  # Warnung", "    # Warnung"))
    assert [(s.lage, s.hinweis) for s in tiefer.stuecke] == [("A", "Stand nach `dkb`")]


def test_the_depth_of_a_list_entry_is_that_of_its_fields_or_of_its_dash_if_it_is_a_value():
    text = ("ziele:\n  - {id: a, cents: 100}\n  # Zu a.\n\n  - id: b\n    cents: 200\n")
    u = umstellen.umwandeln("goals.yaml", text)
    assert [(s.lage, s.ziel) for s in u.stuecke] == [("E", ("eintrag", "ziele", 0))]
    gelesen = _gelesen(u)["ziele"]
    assert gelesen[0]["notiz"] == "Zu a." and "notiz" not in gelesen[1]


def test_a_block_under_a_setting_with_nothing_below_it_is_a_section_after_that_setting():
    text = "kapital:\n  rendite: 0.02\n  # Gilt fuer alles Folgende.\n\nziel:\n  rate: 0.04\n"
    u = umstellen.umwandeln("assumptions.yaml", text)
    assert [(s.lage, s.hinweis) for s in u.stuecke] == [("A", "Stand nach `kapital.rendite`")]


def test_a_comment_in_a_list_without_ids_goes_to_the_area():
    text = "zeitraeume:\n  # Der erste.\n  - von: 2026-01-01\n    bis: 2026-12-31\n"
    u = umstellen.umwandeln("strom.yaml", text)
    assert [(s.lage, s.ziel) for s in u.stuecke] == [("–", ("bereich",))]
    assert "Zu `zeitraeume`:\nDer erste." in _gelesen(u)["notizen"]["bereich"]["notiz"]


# ---------------------------------------------------------- Einstellungen


def test_a_comment_at_a_setting_lands_under_notizen_with_the_path_as_place():
    text = ("kapital:\n"
            "  # Gemessen, nicht angenommen.\n"
            "  rendite_nominal_pa: 0.025\n"
            "  steuersatz: 0.26     # mit Soli\n")
    u = umstellen.umwandeln("assumptions.yaml", text)
    assert _lagen(u) == [("S", 1), ("S", 1)]
    spec = _gelesen(u)
    # keine Notiz in der Zuordnung selbst
    assert spec["kapital"] == {"rendite_nominal_pa": 0.025, "steuersatz": 0.26}
    assert spec["notizen"] == {
        "kapital.rendite_nominal_pa": {"notiz": "Gemessen, nicht angenommen."},
        "kapital.steuersatz": {"notiz": "mit Soli"},
    }


def test_a_euro_repeat_falls_away_at_a_setting_too():
    u = umstellen.umwandeln("assumptions.yaml", "sparerpauschbetrag_cents: 100000   # 1.000,00\n")
    assert [s.weg for s in u.stuecke] == ["wiederholt den Wert in Euro"]
    assert "#" not in u.neu


def test_a_note_never_lands_inside_a_mapping_whose_keys_are_data():
    text = ("einstellungen:\n"
            "  # Mehr Inflation.\n"
            "  inflation_pa: 0.03\n")
    u = umstellen.umwandeln("settings_custom.yaml", text)
    spec = _gelesen(u)
    assert spec["einstellungen"] == {"inflation_pa": 0.03}
    assert spec["notizen"]["einstellungen.inflation_pa"]["notiz"] == "Mehr Inflation."


# ----------------------------------------------------- Koepfe, die die App schrieb


def _kopf(name: str, variante: int = 0) -> str:
    return "\n".join(KOEPFE[name][variante].splitlines()) + "\n\n"


def test_the_head_the_app_wrote_falls_away_only_if_it_matches_word_for_word():
    inhalt = "einstellungen:\n  inflation_pa: 0.03\n"
    u = umstellen.umwandeln("settings_custom.yaml", _kopf("settings_custom.yaml") + inhalt)
    assert u.neu == inhalt
    assert {s.weg for s in u.stuecke} == {"Kopf der App"}

    geaendert = (_kopf("settings_custom.yaml").replace("Stellschrauben", "Stellrädchen")
                 + inhalt)
    u = umstellen.umwandeln("settings_custom.yaml", geaendert)
    assert not u.weggefallen
    assert "Stellrädchen" in _gelesen(u)["notizen"]["bereich"]["notiz"]


def test_a_head_is_compared_against_every_text_the_app_writes_to_that_file():
    assert len(KOEPFE["loans_custom.yaml"]) == 3
    for i in range(3):
        u = umstellen.umwandeln("loans_custom.yaml",
                                _kopf("loans_custom.yaml", i) + "kredite: {}\n")
        assert {s.weg for s in u.stuecke} == {"Kopf der App"}, i


def test_the_head_alone_is_cut_out_of_the_text_so_a_long_file_stays_as_it_is():
    """Eine Datei mit tausend Handentscheidungen wird nicht neu gesetzt, nur weil ein Kopf geht."""
    koerper = "overrides:\n- {dedup_hash: abc,   when: 2026-01-02}\n- {dedup_hash: def}\n"
    u = umstellen.umwandeln("overrides.yaml", _kopf("overrides.yaml") + koerper)
    assert u.neu == koerper                       # Byte fuer Byte


def test_a_head_that_is_part_of_a_longer_head_is_kept_apart():
    """Steht unter dem Kopf der App ein Block des Haushalts, faellt nur der Kopf weg."""
    text = _kopf("settings_custom.yaml") + "# Mein eigener Gedanke.\n\neinstellungen: {}\n"
    u = umstellen.umwandeln("settings_custom.yaml", text)
    assert [s.weg for s in u.stuecke] == ["Kopf der App", ""]
    assert _gelesen(u)["notizen"]["bereich"]["notiz"] == "Mein eigener Gedanke."


# ------------------------------------------------- alte Namen und Freitext


def test_the_old_names_become_notiz_and_stay_where_the_field_was():
    text = ("renten:\n"
            "  - id: gesetzlich\n"
            "    name: Gesetzliche Rente\n"
            "    herleitung: Aus dem Schreiben vom Januar.\n"
            "    cents: 100000\n")
    u = umstellen.umwandeln("renten.yaml", text)
    eintrag = _gelesen(u)["renten"][0]
    assert list(eintrag) == ["id", "name", "notiz", "cents"]
    assert eintrag["notiz"] == "Aus dem Schreiben vom Januar."
    assert u.umbenannt == {"herleitung": 1}


@pytest.mark.parametrize("name, kopf, alt", [
    ("abos.yaml", "abos", "warum"),
    ("balances.yaml", "balances", "note"),
    ("goals.yaml", "ziele", "quelle"),
    ("loans.yaml", "loans", "note"),
])
def test_every_free_text_field_the_plan_names_becomes_a_note(name, kopf, alt):
    kennung = "account_id" if kopf == "balances" else "id"
    u = umstellen.umwandeln(name, f"{kopf}:\n  - {kennung}: a\n    {alt}: Weil so.\n")
    eintrag = _gelesen(u)[kopf][0]
    assert eintrag["notiz"] == "Weil so." and alt not in eintrag


def test_a_pension_source_that_exists_only_in_the_page_file_is_renamed_too():
    """`neu:` in renten_custom.yaml: Der Leser nimmt dort `herleitung`; nach dem Umbenennen
    darf ein Kommentar sie nicht verdecken, weil `notiz` zuerst gilt."""
    text = ("neu:\n"
            "  # Nur hier angelegt.\n"
            "  - id: bav\n"
            "    herleitung: Aus der Mitteilung.\n"
            "    cents: 100\n")
    u = umstellen.umwandeln("renten_custom.yaml", text)
    assert _gelesen(u)["neu"][0]["notiz"] == "Nur hier angelegt.\n\nAus der Mitteilung."
    assert "herleitung" not in u.neu


def test_the_zuordnung_forms_rename_too():
    for name, kopf, alt in (("abos_custom.yaml", "abos", "warum"),
                            ("balances_custom.yaml", "overrides", "note"),
                            ("forecast_custom.yaml", "account_roles", "note")):
        u = umstellen.umwandeln(name, f"{kopf}:\n  a:\n    {alt}: Weil so.\n")
        assert _gelesen(u)[kopf]["a"] == {"notiz": "Weil so."}, name


def test_a_note_and_a_comment_and_an_old_name_become_one_note_in_the_order_of_the_file():
    text = ("renten:\n"
            "  # Zuerst der Block.\n"
            "  - id: a\n"
            "    herleitung: Dann die Herleitung.\n"
            "    cents: 100   # und der Feldkommentar\n")
    u = umstellen.umwandeln("renten.yaml", text)
    assert _gelesen(u)["renten"][0]["notiz"] == (
        "Zuerst der Block.\n\nDann die Herleitung.\n\n`cents`: und der Feldkommentar")


def test_an_existing_note_keeps_its_date_and_its_empty_text():
    text = ("ziele:\n"
            "  a:\n"
            "    notiz: Schon da.\n"
            "    notiz_vom: 2026-09-01\n"
            "    # Neu dazu.\n"
            "    cents: 100\n")
    u = umstellen.umwandeln("ziele_custom.yaml", text)
    eintrag = _gelesen(u)["ziele"]["a"]
    assert eintrag["notiz"] == "Schon da.\n\nNeu dazu."
    assert str(eintrag["notiz_vom"]) == "2026-09-01"
    # `notiz: ""` blendet die Notiz der Basis aus: Das bleibt so.
    u = umstellen.umwandeln("ziele_custom.yaml", "ziele:\n  a:\n    # x\n    notiz: ''\n")
    assert _gelesen(u)["ziele"]["a"]["notiz"] == "x"
    u = umstellen.umwandeln("ziele_custom.yaml", "ziele:\n  a:\n    notiz: ''\n    cents: 1\n")
    assert u.neu is None                       # nichts umzustellen


def test_loan_free_text_goes_into_the_note_and_open_stays():
    text = ("loans:\n"
            "  - id: '001'\n"
            "    note: Vom Vertrag.\n"
            "    open:\n"
            "      - Anschluss klaeren\n"
            "    segments_observed:\n"
            "      - period: 2026-01 .. 2026-04\n"
            "        payment_cents: 50000\n"
            "      - period: 2026-06 .. 2026-08\n"
            "        note: Zwischenzins\n")
    u = umstellen.umwandeln("loans.yaml", text)
    kredit = _gelesen(u)["loans"][0]
    assert kredit["notiz"] == "Vom Vertrag.\n\nTeilstück 2026-06 .. 2026-08: Zwischenzins"
    assert kredit["open"] == ["Anschluss klaeren"]
    assert all("note" not in s for s in kredit["segments_observed"])
    assert "note" not in kredit


# --------------------------------------- Budget, Blatt, Klammer, Eintrag ohne Platz


def test_a_comment_on_a_budget_goes_to_the_note_of_the_account_rule_with_budget_first():
    text = ("account_budgets:\n"
            "  # Dauerauftrag eingestellt.\n"
            "  giro: 0\n"
            "  tages: 30000     # 300,00 -- seit September\n"
            "account_roles:\n"
            "  giro:\n"
            "    role: operating\n"
            "  tages:\n"
            "    role: budget\n")
    spec = _gelesen(umstellen.umwandeln("forecast.yaml", text))
    assert spec["account_budgets"] == {"giro": 0, "tages": 30000}
    rollen = spec["account_roles"]
    assert rollen["giro"]["notiz"] == "Budget: Dauerauftrag eingestellt."
    assert rollen["tages"]["notiz"] == "Budget: 300,00 -- seit September"


def test_a_budget_comment_without_a_rule_for_that_account_goes_to_the_area():
    text = ("account_budgets:\n  # Nur das Budget.\n  giro: 0\n"
            "account_roles:\n  tages:\n    role: budget\n")
    u = umstellen.umwandeln("forecast.yaml", text)
    assert [(s.lage, s.ziel) for s in u.stuecke] == [("E", ("bereich",))]
    assert _gelesen(u)["notizen"]["bereich"]["notiz"] == "Budget von `giro`:\nNur das Budget."


def test_a_comment_on_a_category_leaf_goes_to_the_note_of_the_parent_with_the_leafs_name():
    text = ("management:\n"
            "  wohnen:\n"
            "    name: Wohnen\n"
            "    children:\n"
            "      # Gilt fuer die Miete.\n"
            "      miete: {name: Miete, fix: true}\n"
            "      strom: {name: Strom}   # nach Abschlag\n")
    spec = _gelesen(umstellen.umwandeln("taxonomy.yaml", text))
    wohnen = spec["management"]["wohnen"]
    assert wohnen["children"] == {"miete": {"name": "Miete", "fix": True},
                                  "strom": {"name": "Strom"}}          # kein `notiz` unter children
    assert wohnen["notiz"] == "`miete`: Gilt fuer die Miete.\n\n`strom`: nach Abschlag"


def test_a_comment_in_an_entry_that_is_only_a_value_goes_to_the_area():
    text = "ziele:\n  # Ohne Felder.\n  a:\n  b:\n    cents: 1\n"
    u = umstellen.umwandeln("ziele_custom.yaml", text)
    assert [s.ziel for s in u.stuecke] == [("bereich",)]
    assert _gelesen(u)["ziele"]["a"] is None


def test_a_file_the_converter_does_not_know_puts_everything_in_the_note_of_the_area():
    text = "# Kopf.\n\nbuchungen:\n  # Eine Zeile.\n  - betrag: 1\n"
    u = umstellen.umwandeln("irgendwas.yaml", text)
    spec = _gelesen(u)
    assert spec["buchungen"] == [{"betrag": 1}]
    assert spec["notizen"]["bereich"]["notiz"] == "Kopf.\n\nZu `buchungen`:\nEine Zeile."


def test_files_without_a_page_are_not_touched():
    for name in ("server.yaml", "verbotene_namen.yaml", "taxonomy_migrations.yaml",
                 "accounts.example.yaml"):
        u = umstellen.umwandeln(name, "# Kommentar\nhost: x\n")
        assert u.neu is None and not u.stuecke, name


def test_a_file_that_is_not_a_mapping_is_reported_and_not_written():
    u = umstellen.umwandeln("abos.yaml", "# Eine Liste statt Eintraege.\n- eins\n- zwei\n")
    assert u.neu is None and u.fehler


# --------------------------------------------------------------- Selbstpruefung


MISCH = ZIELE + """\

# Und am Ende.
"""


def test_every_comment_line_lands_exactly_once_and_the_new_file_has_none():
    u = umstellen.umwandeln("goals.yaml", MISCH)
    belegt = sorted(z for s in u.stuecke for z in range(s.von, s.bis + 1))
    assert belegt == sorted(k.zeile for k in lesen(MISCH))
    assert lesen(u.neu) == []
    # Und im Bericht steht jede Zeile: in einer Notiz oder unter "weggefallen".
    spec = yaml.safe_load(u.neu)
    alles = json.dumps(spec, ensure_ascii=False, default=str)
    for s in u.stuecke:
        assert s.weg or s.text.splitlines()[0] in alles


def test_the_values_are_the_same_without_the_notes():
    u = umstellen.umwandeln("goals.yaml", MISCH)
    alt = yaml.safe_load(MISCH)
    neu = yaml.safe_load(u.neu)
    neu.pop("notizen")
    for eintrag in neu["ziele"]:
        eintrag.pop("notiz", None)
    assert neu == alt


def test_a_failing_check_writes_nothing(tmp_path, monkeypatch):
    """Geht eine Notiz verloren, meldet die Pruefung es -- und kein Byte wird geschrieben."""
    wurzel = _datenordner(tmp_path)
    vorher = _pruefsumme(wurzel)

    echt = umstellen.anwenden

    def verlustreich(daten, geruest, spec, stuecke):
        neu, umbenannt = echt(daten, geruest, spec, stuecke)
        neu.pop("notizen", None)           # der Kopf verschwindet
        return neu, umbenannt

    monkeypatch.setattr(umstellen, "anwenden", verlustreich)
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=date(2026, 10, 8))
    assert plan.fehler and "stehen nicht in ihrer Notiz" in plan.fehler[0]
    assert sicherung is None and bericht is None
    assert _pruefsumme(wurzel) == vorher                # config/ und alles andere
    assert not (wurzel / "archiv").exists() and not (wurzel / "notizen").exists()


def test_a_failing_check_in_the_values_writes_nothing(tmp_path, monkeypatch):
    wurzel = _datenordner(tmp_path)
    vorher = _pruefsumme(wurzel)
    echt = umstellen.anwenden

    def veraendernd(daten, geruest, spec, stuecke):
        neu, umbenannt = echt(daten, geruest, spec, stuecke)
        if "ziele" in neu:
            neu["ziele"][0]["cents"] = 1                # ein Wert aendert sich
        return neu, umbenannt

    monkeypatch.setattr(umstellen, "anwenden", veraendernd)
    plan, sicherung, _ = umstellen.ausfuehren(wurzel)
    assert any("nicht dieselben Werte" in f for f in plan.fehler)
    assert sicherung is None and _pruefsumme(wurzel) == vorher


# ----------------------------------------------------------------- der Lauf


def _datenordner(tmp_path: Path) -> Path:
    wurzel = tmp_path / "Daten"
    (wurzel / "config").mkdir(parents=True)
    (wurzel / "data").mkdir()
    (wurzel / "data" / "finance.db").write_bytes(b"nicht anfassen")
    (wurzel / "config" / "goals.yaml").write_text(ZIELE, encoding="utf-8")
    (wurzel / "config" / "strom.yaml").write_text(
        _kopf("strom.yaml") + "zeitraeume: []\nablesungen: []\n", encoding="utf-8")
    (wurzel / "config" / "abos.yaml").write_text(
        "abos:\n  - id: a\n    warum: Weil.\n", encoding="utf-8")
    (wurzel / "config" / "server.yaml").write_text("# Form der Datei\nhost: x\n", encoding="utf-8")
    return wurzel


def _pruefsumme(ordner: Path) -> str:
    h = hashlib.sha256()
    for pfad in sorted(p for p in ordner.rglob("*") if p.is_file()):
        h.update(str(pfad.relative_to(ordner)).encode())
        h.update(pfad.read_bytes())
    return h.hexdigest()


def test_the_run_backs_up_config_writes_the_files_and_the_report(tmp_path):
    wurzel = _datenordner(tmp_path)
    vorher = {p.name: p.read_bytes() for p in (wurzel / "config").iterdir()}
    _, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=date(2026, 10, 8))

    assert sicherung == wurzel / "archiv" / "vor_umstellung_2026-10-08"
    assert {p.name: p.read_bytes() for p in (sicherung / "config").iterdir()} == vorher
    assert bericht == wurzel / "notizen" / "umstellung_2026-10-08.md"
    text = bericht.read_text(encoding="utf-8")
    assert "Die Ziele des Haushalts." in text            # jeder Kommentar steht im Bericht
    assert "Kopf der App" in text and "10.000,00" in text   # und was weggefallen ist
    assert "`goals.yaml`" in text and "`warum` 1" in text

    nach = {p.name: p.read_text(encoding="utf-8") for p in (wurzel / "config").iterdir()}
    assert nach["server.yaml"] == "# Form der Datei\nhost: x\n"           # ohne Seite: unberuehrt
    assert nach["strom.yaml"] == "zeitraeume: []\nablesungen: []\n"
    assert yaml.safe_load(nach["abos.yaml"])["abos"][0]["notiz"] == "Weil."
    assert not any(lesen(t) for n, t in nach.items() if n != "server.yaml")


def test_a_second_run_changes_nothing(tmp_path):
    wurzel = _datenordner(tmp_path)
    umstellen.ausfuehren(wurzel, heute=date(2026, 10, 8))
    nachher = _pruefsumme(wurzel)
    stande = {p: p.stat().st_mtime_ns for p in (wurzel / "config").iterdir()}

    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=date(2026, 10, 9))
    assert not plan.zu_tun and sicherung is None and bericht is None
    assert _pruefsumme(wurzel) == nachher               # auch kein neuer Ordner in archiv/
    assert {p: p.stat().st_mtime_ns for p in (wurzel / "config").iterdir()} == stande


def test_the_backup_of_the_same_day_is_not_overwritten(tmp_path):
    wurzel = _datenordner(tmp_path)
    (wurzel / "archiv" / "vor_umstellung_2026-10-08").mkdir(parents=True)
    _, sicherung, _ = umstellen.ausfuehren(wurzel, heute=date(2026, 10, 8))
    assert sicherung.name == "vor_umstellung_2026-10-08_2"


def test_the_probe_leaves_the_data_folder_untouched_and_writes_a_converted_copy(tmp_path):
    wurzel = _datenordner(tmp_path)
    vorher = _pruefsumme(wurzel)
    probe = tmp_path / "Probe"
    _, bericht = umstellen.probieren(wurzel, probe, heute=date(2026, 10, 8))
    assert _pruefsumme(wurzel) == vorher               # Pruefsumme vorher und nachher
    assert bericht == probe / "umstellung_2026-10-08.md"
    abos = yaml.safe_load((probe / "config" / "abos.yaml").read_text(encoding="utf-8"))
    assert abos["abos"][0]["notiz"]
    assert (probe / "config" / "server.yaml").read_text(encoding="utf-8") == (
        "# Form der Datei\nhost: x\n")
    # Die Kopie ist ein Datenordner: eine zweite Umwandlung findet dort nichts mehr.
    assert not umstellen.planen(probe / "config").zu_tun


@pytest.mark.parametrize("wo", ["config", "."])
def test_the_probe_folder_must_lie_outside_the_data_folder(tmp_path, wo):
    wurzel = _datenordner(tmp_path)
    with pytest.raises(ValueError, match="außerhalb"):
        umstellen.probieren(wurzel, wurzel / wo)
    assert not (wurzel / "umstellung_2026-10-08.md").exists()


def test_the_command_reports_and_the_probe_flag_writes_nothing_in_the_data_folder(
        tmp_path, monkeypatch):
    from finctl import cli

    wurzel = _datenordner(tmp_path)
    monkeypatch.setattr(cli, "CONFIG_DIR", wurzel / "config")
    vorher = _pruefsumme(wurzel)
    probe = tmp_path / "Probe"
    lauf = CliRunner().invoke(cli.app, ["umstellen", "--probe", str(probe), "--json"])
    assert lauf.exit_code == 0, lauf.output
    antwort = json.loads(lauf.output)
    assert {d["name"] for d in antwort["dateien"]} == {"goals.yaml", "strom.yaml",
                                                       "abos.yaml"}
    assert _pruefsumme(wurzel) == vorher

    lauf = CliRunner().invoke(cli.app, ["umstellen"])
    assert lauf.exit_code == 0, lauf.output
    assert "Gesichert nach" in lauf.output and "Bericht:" in lauf.output
    lauf = CliRunner().invoke(cli.app, ["umstellen"])
    assert lauf.exit_code == 0 and "Nichts umzustellen" in lauf.output


def test_the_probe_writes_no_copy_when_there_is_nothing_to_convert(tmp_path, monkeypatch):
    from finctl import cli

    wurzel = _datenordner(tmp_path)
    umstellen.ausfuehren(wurzel, heute=date(2026, 10, 8))
    monkeypatch.setattr(cli, "CONFIG_DIR", wurzel / "config")
    vorher = _pruefsumme(wurzel)
    probe = tmp_path / "Probe"
    _, bericht = umstellen.probieren(wurzel, probe, heute=date(2026, 10, 9))
    assert bericht is None and not probe.exists()
    lauf = CliRunner().invoke(cli.app, ["umstellen", "--probe", str(probe)])
    assert lauf.exit_code == 0, lauf.output
    assert "Nichts umzustellen" in lauf.output and "keine Kopie geschrieben" in lauf.output
    assert not probe.exists() and _pruefsumme(wurzel) == vorher


def test_the_probe_writes_no_copy_when_a_check_fails(tmp_path, monkeypatch):
    from finctl import cli

    wurzel = _datenordner(tmp_path)
    echt = umstellen.anwenden

    def verlustreich(daten, geruest, spec, stuecke):
        neu, umbenannt = echt(daten, geruest, spec, stuecke)
        neu.pop("notizen", None)           # eine Notiz geht verloren: die Pruefung scheitert
        return neu, umbenannt

    monkeypatch.setattr(umstellen, "anwenden", verlustreich)
    monkeypatch.setattr(cli, "CONFIG_DIR", wurzel / "config")
    vorher = _pruefsumme(wurzel)
    probe = tmp_path / "Probe"
    plan, bericht = umstellen.probieren(wurzel, probe, heute=date(2026, 10, 8))
    assert plan.fehler and bericht is None and not probe.exists()
    lauf = CliRunner().invoke(cli.app, ["umstellen", "--probe", str(probe)])
    assert lauf.exit_code == 1, lauf.output
    assert "keine Kopie geschrieben" in lauf.output
    assert not probe.exists() and _pruefsumme(wurzel) == vorher


def test_the_command_refuses_a_probe_folder_inside_the_data_folder(tmp_path, monkeypatch):
    from finctl import cli

    wurzel = _datenordner(tmp_path)
    monkeypatch.setattr(cli, "CONFIG_DIR", wurzel / "config")
    lauf = CliRunner().invoke(cli.app, ["umstellen", "--probe", str(wurzel / "probe")])
    assert lauf.exit_code == 1 and "außerhalb" in lauf.output
    assert not (wurzel / "probe").exists()


# ------------------------------------------------- alte Form: die App haelt an
#
# Unter Windows nennt der Hinweis `finctl.exe`, mit dem Pfad davor.
BEFEHL = r"finctl(\.exe)? umstellen"


# Eine Erkennung: Was `finctl umstellen` finden wuerde, haelt die App an, und nur das.

#: Die Form, in der die App nichts mehr zu melden hat.
_ABO = ("  - id: a\n    name: A\n    kategorie: abo/x\n    konto: k\n    betrag_cents: -100\n"
        "    takt: 12\n    faellig: 2027-01-01\n")

UMGESTELLT = {
    "taxonomy.yaml": ("management:\n  immobilie:\n    name: Immobilie\n    kind: expense\n"
                      "    children:\n      kaufnebenkosten: {name: Kaufnebenkosten, "
                      "einmalig: true}\n"),
    "forecast.yaml": "account_roles:\n  giro: {role: operating}\n",
    "abos.yaml": "abos:\n" + _ABO + "    notiz: Weil.\n",
    "renten.yaml": "renten:\n  - id: r\n    name: R\n    cents: 100\n    notiz: Weil.\n",
    "server.yaml": "# Form der Datei: bleibt stehen.\nhost: x\n",
}

#: Was daraus eine Datei in alter Form macht: Datei -> neuer Inhalt.
ALTE_FORM = {
    "ein Kommentar": ("abos.yaml", "# Begruendung\nabos:\n" + _ABO + "    notiz: Weil.\n"),
    "ein alter Name": ("abos.yaml", "abos:\n" + _ABO + "    warum: Weil.\n"),
    "forecast_custom.yaml": ("forecast_custom.yaml",
                             "account_roles:\n  giro: {ceiling_cents: 100000}\n"),
    "taxonomy_custom.yaml": ("taxonomy_custom.yaml",
                             "management:\n  immobilie:\n    children: {neu: Neu}\n"),
    "renten_custom.yaml": ("renten_custom.yaml", "renten:\n  r: {cents: 200}\n"),
    "abos_custom.yaml": ("abos_custom.yaml", "abos:\n  a: {takt: 3}\n"),
    "versicherungen_custom.yaml": (
        "versicherungen_custom.yaml",
        ("versicherungen:\n  v:\n    name: V\n    kategorie: versicherung/x\n    konto: k\n"
         "    betrag_cents: -100\n    takt: 12\n    faellig: 2027-01-01\n")),
}


def _halteordner(tmp_path: Path, zustand: str | None) -> Path:
    """Ein Datenordner mit Hauptbuch; `zustand` ist einer aus `ALTE_FORM` oder `None`."""
    from finctl.ledger.db import init_db

    wurzel = tmp_path / "Halten"
    (wurzel / "config").mkdir(parents=True)
    (wurzel / "data").mkdir()
    init_db(wurzel / "data" / "finance.db")
    for name, inhalt in UMGESTELLT.items():
        (wurzel / "config" / name).write_text(inhalt, encoding="utf-8")
    if zustand is not None:
        name, inhalt = ALTE_FORM[zustand]
        (wurzel / "config" / name).write_text(inhalt, encoding="utf-8")
    return wurzel


def _einrichten(monkeypatch, wurzel: Path) -> None:
    from finctl import cli, pfade
    from finctl import nachfuehren as nf

    config = wurzel / "config"
    monkeypatch.setattr(cli, "CONFIG_DIR", config)
    monkeypatch.setattr(cli, "DB_PATH", wurzel / "data" / "finance.db")
    monkeypatch.setattr(nf, "CONFIG_DIR", config)
    monkeypatch.setattr(pfade, "DB_PATH", wurzel / "data" / "finance.db")
    monkeypatch.setattr(pfade, "CONFIG_DIR", config)


def _stand(wurzel: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in (wurzel / "config").iterdir()}


@pytest.mark.parametrize("zustand", ALTE_FORM)
def test_the_app_start_stops_when_umstellen_would_find_something(tmp_path, monkeypatch, zustand):
    from finctl import nachfuehren as nf

    wurzel = _halteordner(tmp_path, zustand)
    _einrichten(monkeypatch, wurzel)
    vorher = _stand(wurzel)
    with pytest.raises(umstellen.AlteFormError, match=BEFEHL) as halt:
        nf.beim_start()
    assert ALTE_FORM[zustand][0] in str(halt.value)
    assert _stand(wurzel) == vorher


@pytest.mark.parametrize("zustand", ALTE_FORM)
@pytest.mark.parametrize("befehl", [["init"], ["status"]])
def test_init_and_the_commands_with_the_ledger_stop_too(tmp_path, monkeypatch, zustand, befehl):
    from finctl import cli

    wurzel = _halteordner(tmp_path, zustand)
    _einrichten(monkeypatch, wurzel)
    vorher = _stand(wurzel)
    lauf = CliRunner().invoke(cli.app, befehl)
    assert lauf.exit_code == 1, lauf.output
    assert re.search(BEFEHL, lauf.output) and ALTE_FORM[zustand][0] in lauf.output
    assert _stand(wurzel) == vorher


def test_the_starter_stops_before_it_sets_anything_up(tmp_path, monkeypatch):
    from finctl import starter

    wurzel = _halteordner(tmp_path, "forecast_custom.yaml")
    _einrichten(monkeypatch, wurzel)
    monkeypatch.setattr(starter, "port_waehlen", lambda *_a: (8777, False))
    with pytest.raises(SystemExit, match=BEFEHL):
        starter.main()


def test_a_converted_household_does_not_stop(tmp_path, monkeypatch):
    from finctl import cli
    from finctl import nachfuehren as nf

    wurzel = _halteordner(tmp_path, None)
    _einrichten(monkeypatch, wurzel)
    umstellen.halt_wenn_offen(wurzel / "config")
    nf.beim_start()
    lauf = CliRunner().invoke(cli.app, ["status", "--json"])
    assert lauf.exit_code == 0, lauf.output


@pytest.mark.parametrize("zustand", [None, *ALTE_FORM])
def test_the_stop_and_nothing_to_convert_are_one_question(tmp_path, zustand):
    """Wo der Befehl etwas faende, haelt die App an -- und sonst meldet er „Nichts umzustellen“."""
    wurzel = _halteordner(tmp_path, zustand)
    config = wurzel / "config"
    plan = umstellen.planen(config)
    if zustand is None:
        umstellen.halt_wenn_offen(config)
    else:
        with pytest.raises(umstellen.AlteFormError):
            umstellen.halt_wenn_offen(config)
    assert plan.offen == (zustand is not None)

    _, sicherung, _ = umstellen.ausfuehren(wurzel, heute=date(2026, 10, 8))
    assert (sicherung is not None) == plan.offen
    umstellen.halt_wenn_offen(config)               # danach haelt nichts mehr an


def test_files_without_a_page_and_the_head_of_the_app_are_no_reason_to_stop(tmp_path):
    wurzel = _halteordner(tmp_path, None)
    config = wurzel / "config"
    (config / "taxonomy_migrations.yaml").write_text("# Form\nremap: {}\n", encoding="utf-8")
    (config / "verbotene_namen.yaml").write_text("# Namen\n- x\n", encoding="utf-8")
    (config / "strom.yaml").write_text(
        _kopf("strom.yaml") + "zeitraeume: []\nablesungen: []\n", encoding="utf-8")
    umstellen.halt_wenn_offen(config)
    assert not umstellen.planen(config).zu_tun


# ------------------------------------------- die Koepfe der App gegen den Code


def _konstanten() -> dict[str, list[str]]:
    from finctl import (
        geteilt,
        module,
        reihen,
        strom,
        zinssaetze,
    )
    from finctl.energie import speicher
    from finctl.forecast import prognosebasis
    from finctl.ingest import zuordnung
    from finctl.rules import categorize
    from finctl.web.routen import planung

    return {
        "reihen_custom.yaml": [reihen.KOPF],
        "zinssaetze_custom.yaml": [zinssaetze.KOPF],
        "module_custom.yaml": [module.KOPF],
        "geteilt_custom.yaml": [geteilt.KOPF],
        "prognosebasis_custom.yaml": [prognosebasis.KOPF],
        "csv_profile_custom.yaml": [zuordnung.KOPF],
        "strom.yaml": [strom.KOPF],
        "szenarien.yaml": [planung.SZENARIEN_HEADER],
        "energie.yaml": [speicher.KOPF],
        "overrides.yaml": [categorize.OVERRIDES_KOPF],
    }


def test_the_heads_the_converter_knows_are_the_ones_the_code_writes():
    """Solange es die Schreiber gibt: kein Kopf im Umwandler, der vom Code abweicht.

    Mit Schritt 5 verschwinden die Schreiber der `_custom`-Dateien; dann bleibt der Text
    im Umwandler, und dieser Test verliert die Zeile des Schreibers (N.3, N.4).
    """
    konstanten = _konstanten()
    # Die Schreiber dieser Dateien gibt es nicht mehr (N.3a bis N.3f); der Umwandler erkennt
    # ihren Kopf weiter, denn eine Seitendatei in alter Form traegt ihn noch.
    assert set(KOEPFE) - set(konstanten) == {
        "forecast_custom.yaml", "taxonomy_custom.yaml", "renten_custom.yaml", "abos_custom.yaml",
        "versicherungen_custom.yaml", "loans_custom.yaml", "properties_custom.yaml",
        "balances_custom.yaml", "ziele_custom.yaml", "rules_custom.yaml", "accounts_custom.yaml",
        "lebensplan_custom.yaml", "backup_custom.yaml", "settings_custom.yaml"}
    assert set(konstanten) <= set(KOEPFE)
    for datei, texte in konstanten.items():
        assert [t.strip("\n") for t in texte] == [t.strip("\n") for t in KOEPFE[datei]], datei
