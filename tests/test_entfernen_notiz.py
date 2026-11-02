"""Entfernen nennt die Notiz: Wer einen Eintrag samt Notiz aus der Datei nimmt, wird gewarnt.

Die Rueckfrage laeuft im Browser (`rueckfrage` in base.html); der Server liefert den Satz
an den Knopf (`data-notiz-geht`). Hier: der Satz, das Makro, und dass jede Seite, die einen
Eintrag mit Notiz entfernt, beides benutzt. Die Eintraege liest der Test zur Laufzeit.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from finctl.web.basis import NOTIZ_ANFANG, TEMPLATES, notiz_geht_mit

VORLAGEN = Path("finctl/web/templates")


def test_the_sentence_names_the_start_of_the_note():
    assert notiz_geht_mit("Warum es so ist.") == "Die Notiz geht mit: „Warum es so ist.“"


def test_a_long_note_is_cut_at_a_word_and_says_so():
    text = "Gekauft nach dem Umzug, weil der alte Anschluss nicht mehr passte " * 3
    satz = notiz_geht_mit(text)
    anfang = satz.removeprefix("Die Notiz geht mit: „").removesuffix("“")
    assert anfang.endswith(" …") and len(anfang) <= NOTIZ_ANFANG + 2
    assert text.startswith(anfang.removesuffix(" …")), "der Anfang ist wirklich der Anfang"
    assert not anfang.removesuffix(" …").endswith(("passte ", "Gekauft nach dem U"))


def test_line_breaks_become_spaces_so_the_dialog_shows_one_line():
    assert notiz_geht_mit("Erste Zeile\n\nzweite  Zeile") == \
        "Die Notiz geht mit: „Erste Zeile zweite Zeile“"


@pytest.mark.parametrize("text", [None, "", "  \n "])
def test_no_note_means_no_sentence(text):
    assert notiz_geht_mit(text) == ""


def test_the_button_carries_the_sentence_only_with_a_note():
    geht = TEMPLATES.env.get_template("_notiz.html").module.geht_mit
    assert 'data-notiz-geht="Die Notiz geht mit: „Grund“"' in str(geht("Grund"))
    assert str(geht("")).strip() == "" and str(geht(None)).strip() == ""


def test_a_note_with_quotes_cannot_break_out_of_the_attribute():
    geht = TEMPLATES.env.get_template("_notiz.html").module.geht_mit
    html = str(geht('Er sagte "Hallo" <b>'))
    assert html.count('"') == 2 and "<b>" not in html


#: Seiten, auf denen ein Knopf einen Eintrag samt Notiz aus einer Datei nimmt, mit der Vorlage
#: des Knopfes. Jede weitere Stelle gehoert hierher.
ENTFERNER = [
    ("kredite.html", "kreditEntfernen"),
    ("immobilien.html", "objektEntfernen"),
    ("renten.html", "renteLoeschen"),
    ("ziele.html", "loeschen"),
    ("regeln.html", "loeschen"),
    ("projekte.html", "projektEntfernen"),
    ("_abo_editor.html", None),
]


@pytest.mark.parametrize(("datei", "funktion"), ENTFERNER, ids=[e[0] for e in ENTFERNER])
def test_every_remover_asks_through_the_shared_question_and_carries_the_note(datei, funktion):
    text = (VORLAGEN / datei).read_text(encoding="utf-8")
    assert "geht_mit(" in text, f"{datei}: der Knopf traegt die Notiz nicht"
    if funktion:
        rumpf = re.search(rf"function {funktion}\(.*?\n}}", text, re.S)
        assert rumpf, f"{datei}: {funktion} fehlt"
        assert "rueckfrage(" in rumpf.group(0) and "confirm(" not in rumpf.group(0)


def test_the_vertraege_ask_through_the_shared_question():
    assert "rueckfrage('Löschen?'" in (VORLAGEN / "abos.html").read_text(encoding="utf-8")


def test_the_shared_question_adds_the_sentence_to_the_question():
    base = (VORLAGEN / "base.html").read_text(encoding="utf-8")
    assert "function rueckfrage(frage, knopf)" in base
    assert "knopf.dataset.notizGeht" in base
