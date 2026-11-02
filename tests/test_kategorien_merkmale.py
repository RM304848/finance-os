"""Fixkosten und einmalig an einer Kategorie setzen, und eine Oberkategorie anlegen.

Das Handbuch versprach das `fix`-Flag auf der Seite, die Seite kannte es nicht: Es ging nur im
Texteditor. Eine neue Oberkategorie ging auch nur dort.

Testdaten sind erfunden.
"""

from __future__ import annotations

import pytest
import yaml
from fastapi.testclient import TestClient

from finctl.tax import taxonomy as tx
from finctl.web.server import app

BAUM = {"management": {
    "wohnen": {"name": "Wohnen", "kind": "expense", "children": {
        "miete": {"name": "Miete", "fix": True}, "umzug": "Umzug"}},
    "abo": {"name": "Abos", "kind": "expense", "fix": True, "children": {
        "musik": "Musik", "kurs": {"name": "Kurs", "fix": False}}},
    "einkommen": {"name": "Einkommen", "kind": "income", "children": {"gehalt": "Gehalt"}}}}


@pytest.fixture
def datei(tmp_path):
    pfad = tmp_path / "taxonomy.yaml"
    pfad.write_text(yaml.safe_dump(BAUM, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return pfad


def _kinder(datei, ast):
    return yaml.safe_load(datei.read_text(encoding="utf-8"))["management"][ast]["children"]


def test_a_flag_is_set_on_a_plain_label_and_taken_off_again(datei):
    assert tx.merkmale_setzen("wohnen", "umzug", {"fix": True}, path=datei)
    assert _kinder(datei, "wohnen")["umzug"] == {"name": "Umzug", "fix": True}
    assert tx.merkmale_setzen("wohnen", "umzug", {"fix": False}, path=datei)
    # Ohne Merkmal ist es wieder ein blosser Name.
    assert _kinder(datei, "wohnen")["umzug"] == "Umzug"


def test_both_flags_go_together_and_only_the_given_ones_change(datei):
    tx.merkmale_setzen("wohnen", "miete", {"einmalig": True}, path=datei)
    assert _kinder(datei, "wohnen")["miete"] == {"name": "Miete", "fix": True, "einmalig": True}
    tx.merkmale_setzen("wohnen", "miete", {"einmalig": False}, path=datei)
    assert _kinder(datei, "wohnen")["miete"] == {"name": "Miete", "fix": True}


def test_a_child_inherits_the_flag_of_its_branch_and_only_a_difference_is_written(datei):
    # Der Ast sagt fix; "musik" erbt es. Dasselbe zu verlangen aendert nichts.
    vorher = datei.read_bytes()
    assert not tx.merkmale_setzen("abo", "musik", {"fix": True}, path=datei)
    assert datei.read_bytes() == vorher
    # Gegen den Ast: ein eigener Eintrag. Und wieder wie der Ast: der Eintrag faellt weg.
    tx.merkmale_setzen("abo", "musik", {"fix": False}, path=datei)
    assert _kinder(datei, "abo")["musik"] == {"name": "Musik", "fix": False}
    tx.merkmale_setzen("abo", "musik", {"fix": True}, path=datei)
    assert _kinder(datei, "abo")["musik"] == "Musik"


def test_saving_the_flags_a_category_already_has_writes_no_byte(datei):
    vorher = datei.read_bytes()
    assert not tx.merkmale_setzen("wohnen", "miete", {"fix": True, "einmalig": False}, path=datei)
    assert not tx.merkmale_setzen("wohnen", "umzug", {"fix": False, "einmalig": False}, path=datei)
    assert not tx.merkmale_setzen("abo", "kurs", {"fix": False}, path=datei)
    assert datei.read_bytes() == vorher


def test_a_flag_on_a_category_that_is_not_there_is_refused(datei):
    with pytest.raises(ValueError, match="Keine Kategorie"):
        tx.merkmale_setzen("wohnen", "gibtsnicht", {"fix": True}, path=datei)
    with pytest.raises(ValueError, match="Keine Kategorie"):
        tx.merkmale_setzen("gibtsnicht", "x", {"fix": True}, path=datei)


def test_a_new_branch_stands_behind_the_others_without_children(datei):
    tx.oberkategorie_anlegen("haustier", "Haustier", "expense", path=datei)
    baum = yaml.safe_load(datei.read_text(encoding="utf-8"))["management"]
    assert list(baum) == ["wohnen", "abo", "einkommen", "haustier"]
    assert baum["haustier"] == {"name": "Haustier", "kind": "expense", "children": {}}
    # Und die Datenbank kennt sie: eine Oberkategorie ohne Kinder ist wahlbar fuer eine neue.
    import sqlite3

    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(open("finctl/ledger/schema.sql", encoding="utf-8").read())
    tx.load_into_db(c, datei)
    assert c.execute("SELECT kind, active FROM mgmt_categories WHERE id = 'haustier'"
                     ).fetchone()[:] == ("expense", 1)


@pytest.mark.parametrize("kennung, art, wort", [
    ("wohnen", "expense", "schon"),
    ("neu", "transfer", "Einnahme oder Ausgabe"),
    ("notiz", "expense", "reserviert"),
])
def test_a_wrong_branch_is_refused_and_changes_nothing(datei, kennung, art, wort):
    vorher = datei.read_bytes()
    with pytest.raises(ValueError, match=wort):
        tx.oberkategorie_anlegen(kennung, "Name", art, path=datei)
    assert datei.read_bytes() == vorher


def test_the_page_offers_both_and_the_endpoint_refuses_before_it_writes():
    client = TestClient(app)
    html = client.get("/kategorien").text
    assert "Neue Oberkategorie" in html and 'id="k-fix"' in html and 'id="k-einmalig"' in html
    assert client.post("/api/category", json={"action": "add_parent", "name": ""}
                       ).status_code == 400
    antwort = client.post("/api/category", json={"action": "merkmale", "id": "gibtsnicht/x",
                                                 "fix": True})
    assert antwort.status_code == 400 and "Keine Kategorie" in antwort.json()["error"]
