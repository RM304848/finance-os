"""Die Notiz: Form, Lesen, Datumsregel (Schritt 5, N.1).

`finctl/notizen.py` ist die einzige Stelle, die die Form einer Notiz kennt. Hier
steht, was es verspricht; dass die Leser und Schreiber der Dateien es einhalten,
pruefen `tests/test_notizen_eintraege.py` und `tests/test_notizen_zuordnungen.py`.

Alle Texte sind erfunden.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from finctl import notizen
from finctl.notizen import Notiz

HEUTE = date(2026, 10, 7)


# ------------------------------------------------------------------ Form


def test_a_note_has_text_and_a_date_and_writes_both_as_fields():
    assert Notiz("Warum", "2026-10-05").als_dict() == {
        "notiz": "Warum", "notiz_vom": "2026-10-05"}
    # Ohne Datum steht nur der Text; ohne Text steht nichts, auch kein Datum.
    assert Notiz("Warum").als_dict() == {"notiz": "Warum"}
    assert Notiz("", "2026-10-05").als_dict() == {}
    assert not Notiz() and Notiz("x")


def test_a_note_is_read_from_the_entry_and_the_date_comes_as_text():
    # YAML liest `notiz_vom: 2026-10-05` schon als Datum.
    eintrag = yaml.safe_load("id: a\nnotiz: |\n  Zwei Zeilen\n  Text\nnotiz_vom: 2026-10-05\n")
    assert notizen.lesen(eintrag) == Notiz("Zwei Zeilen\nText", "2026-10-05")
    assert notizen.lesen({"notiz": "Text", "notiz_vom": "2026-10-05"}).vom == "2026-10-05"
    assert notizen.lesen({}) == Notiz() and notizen.lesen(None) == Notiz()
    # Ein Datum ohne Text sagt nichts.
    assert notizen.lesen({"notiz_vom": "2026-10-05"}) == Notiz()


def test_a_date_that_is_no_date_is_an_error_that_names_the_field():
    with pytest.raises(ValueError, match="notiz_vom"):
        notizen.lesen({"notiz": "Text", "notiz_vom": "gestern"})


def test_a_missing_date_stays_missing_when_reading():
    assert notizen.lesen({"notiz": "alt"}) == Notiz("alt", "")


# ------------------------------------------------------------- alte Namen


def test_the_note_comes_first_under_its_name_then_under_the_old_one():
    alt = ("warum",)
    assert notizen.lesen({"warum": "alt"}, alt=alt) == Notiz("alt", "")
    # `notiz` gilt vor jedem alten Namen, und nur ihr Datum zaehlt.
    assert notizen.lesen({"warum": "alt", "notiz": "neu", "notiz_vom": "2026-10-05"},
                         alt=alt) == Notiz("neu", "2026-10-05")
    # Ein alter Name ohne `alt` ist keine Notiz.
    assert notizen.lesen({"warum": "alt"}) == Notiz()


def test_an_empty_text_is_no_note_and_a_field_without_value_lets_the_old_name_speak():
    assert notizen.lesen({"notiz": ""}) == Notiz()
    # `notiz:` ohne Wert (None) sagt nichts, ein alter Name gilt dann.
    assert notizen.lesen({"notiz": None, "note": "alt"}, alt=("note",)).text == "alt"


# ----------------------------------------------------------- Datumsregel


def test_an_unchanged_note_keeps_its_date_even_a_missing_one():
    mit = Notiz("Text", "2026-01-01")
    ohne = Notiz("Text")
    for bisher in (mit, ohne):
        assert notizen.fortschreiben(bisher, "Text", heute=HEUTE) == bisher
        assert notizen.fortschreiben(bisher, "  Text \n", heute=HEUTE) == bisher
        assert notizen.fortschreiben(bisher, None, heute=HEUTE) == bisher


def test_a_changed_note_gets_todays_date_and_an_empty_one_is_gone():
    bisher = Notiz("Text", "2026-01-01")
    assert notizen.fortschreiben(bisher, "Neu", heute=HEUTE) == Notiz("Neu", "2026-10-07")
    assert notizen.fortschreiben(Notiz(), "Neu", heute=HEUTE) == Notiz("Neu", "2026-10-07")
    assert notizen.fortschreiben(bisher, "  ", heute=HEUTE) == Notiz()


# ---------------------------------------------------------------- setzen


def test_setting_the_same_text_leaves_the_entry_untouched():
    eintrag = {"id": "a", "notiz": "Text\n"}            # wie ein Blockabsatz endet
    assert not notizen.setzen(eintrag, "Text", heute=HEUTE)
    assert eintrag == {"id": "a", "notiz": "Text\n"}
    # Auch ein alter Name wird nicht umbenannt, solange der Text derselbe ist.
    alt = {"id": "a", "warum": "Text"}
    assert not notizen.setzen(alt, "Text", alt=("warum",), heute=HEUTE)
    assert alt == {"id": "a", "warum": "Text"}


def test_a_new_text_is_written_under_the_new_name_with_a_date():
    eintrag = {"id": "a", "warum": "alt", "notiz": "mittel", "notiz_vom": "2026-01-01"}
    assert notizen.setzen(eintrag, "neu", alt=("warum",), heute=HEUTE)
    assert eintrag == {"id": "a", "notiz": "neu", "notiz_vom": "2026-10-07"}


def test_an_empty_text_removes_the_note_of_the_entry():
    eintrag = {"id": "a", "notiz": "Text", "notiz_vom": "2026-01-01"}
    assert notizen.setzen(eintrag, "", heute=HEUTE)
    assert eintrag == {"id": "a"}
    assert not notizen.setzen(eintrag, "", heute=HEUTE)


def test_a_text_is_never_set_when_none_is_given():
    eintrag = {"notiz": "Text"}
    assert not notizen.setzen(eintrag, None, heute=HEUTE)
    assert eintrag == {"notiz": "Text"}


# --------------------------------------------------------------- Bereiche


def test_notes_without_an_entry_are_read_from_the_block_at_the_top():
    spec = yaml.safe_load(
        "notizen:\n  kapital.rendite_depot:\n    notiz: Begruendung\n    notiz_vom: 2026-10-05\n"
        "  bereich:\n    notiz: Fuer die ganze Datei\n")
    assert notizen.bereiche(spec) == {
        "kapital.rendite_depot": Notiz("Begruendung", "2026-10-05"),
        "bereich": Notiz("Fuer die ganze Datei", "")}
    assert notizen.bereiche({}) == {} and notizen.bereiche(None) == {}


def test_a_block_in_another_shape_is_an_error_that_names_the_file():
    with pytest.raises(ValueError, match=r"x\.yaml: notizen"):
        notizen.bereiche({"notizen": {"ort": "nur Text"}}, "x.yaml")
    with pytest.raises(ValueError, match=r"x\.yaml"):
        notizen.bereiche({"notizen": ["a"]}, "x.yaml")


def test_a_note_of_a_place_follows_the_same_date_rule():
    spec: dict = {"werte": {"a": 1}}
    assert notizen.bereich_setzen(spec, "a.b", "Text", heute=HEUTE)
    assert spec["notizen"] == {"a.b": {"notiz": "Text", "notiz_vom": "2026-10-07"}}
    assert not notizen.bereich_setzen(spec, "a.b", "Text", heute=date(2027, 1, 1))
    spec["notizen"]["a.b"].pop("notiz_vom")             # aus der Zeit vor den Notizen
    assert not notizen.bereich_setzen(spec, "a.b", "Text", heute=HEUTE)
    assert "notiz_vom" not in spec["notizen"]["a.b"]
    # Leer nimmt den Ort heraus, und ein leerer Block faellt aus der Datei.
    assert notizen.bereich_setzen(spec, "a.b", "", heute=HEUTE)
    assert "notizen" not in spec and spec == {"werte": {"a": 1}}


def test_a_writer_that_builds_the_file_anew_keeps_the_block(tmp_path):
    pfad = tmp_path / "x.yaml"
    assert notizen.mit_bereichen({"a": 1}, pfad) == {"a": 1}          # keine Datei
    pfad.write_text("a: 0\n", encoding="utf-8")
    assert notizen.mit_bereichen({"a": 1}, pfad) == {"a": 1}          # kein Block
    pfad.write_text("a: 0\nnotizen:\n  bereich:\n    notiz: Text\n", encoding="utf-8")
    assert notizen.mit_bereichen({"a": 1}, pfad) == {
        "a": 1, "notizen": {"bereich": {"notiz": "Text"}}}


# ---------------------------------------------------- Zuordnungen, Namen


def test_a_mapping_whose_keys_are_data_loses_the_keys_of_a_note():
    assert notizen.ohne({"konto": 1, "notiz": "x", "notiz_vom": "2026-10-05",
                         "notizen": {"a": 1}}) == {"konto": 1}
    assert notizen.ohne(None) == {} and notizen.ohne({}) == {}


@pytest.mark.parametrize("name", ["notiz", "notiz_vom", "notizen"])
def test_the_words_of_a_note_are_not_an_identifier(name):
    with pytest.raises(ValueError, match="reserviert"):
        notizen.kennung_pruefen(name)
    notizen.kennung_pruefen("notizbuch")


def test_a_row_for_a_page_carries_the_note_that_applies_under_both_names():
    zeile = {"name": "A", "notiz": "veraltet", "notiz_vom": "2026-01-01", "note": "veraltet"}
    notizen.in_zeile(zeile, Notiz("gilt", "2026-10-05"), ("note",))
    assert zeile == {"name": "A", "notiz": "gilt", "notiz_vom": "2026-10-05", "note": "gilt"}
    # Ohne Notiz bleibt eine Zeile ohne die Felder; der alte Name bleibt, wo er stand.
    leer = {"name": "A", "note": "x"}
    notizen.in_zeile(leer, Notiz(), ("note",))
    assert leer == {"name": "A", "note": ""}
    frei = {"name": "A"}
    notizen.in_zeile(frei, Notiz(), ("note",))
    assert frei == {"name": "A"}


# ------------------------------------------------------------ eingabe: was eine Seite schickt


def test_a_note_from_a_page_keeps_every_line_break_and_loses_only_its_border():
    assert notizen.eingabe("  Eins.\n\nZwei.\n  Drei.\n ") == "Eins.\n\nZwei.\n  Drei."
    assert notizen.eingabe("Eins.\r\n\r\nZwei.\rDrei.") == "Eins.\n\nZwei.\nDrei."
    assert notizen.eingabe(None) == "" and notizen.eingabe("  ") == ""


def test_a_note_is_cut_only_at_the_one_limit_against_input_without_end():
    assert notizen.eingabe("x" * (notizen.MAX + 50)) == "x" * notizen.MAX
    assert notizen.eingabe("x" * notizen.MAX) == "x" * notizen.MAX


def test_the_limit_is_far_above_the_longest_note_a_household_has():
    """Die Grenze schnitte sonst beim Speichern eine Begruendung ab, auch ohne Aenderung."""
    laengste = 0

    def gehe(wert):
        nonlocal laengste
        if isinstance(wert, dict):
            if isinstance(wert.get(notizen.NOTIZ), str):
                laengste = max(laengste, len(wert[notizen.NOTIZ]))
            for v in wert.values():
                gehe(v)
        elif isinstance(wert, list):
            for v in wert:
                gehe(v)

    for pfad in Path("config").glob("*.yaml"):
        if pfad.name != "overrides.yaml":
            gehe(yaml.safe_load(pfad.read_text(encoding="utf-8")))
    assert 2 * max(laengste, 1_000) <= notizen.MAX
