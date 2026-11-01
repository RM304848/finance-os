"""Je Eintragsart: Die Notiz uebersteht Lesen und Schreiben (Schritt 5, N.1).

Fuer jede Art von Eintrag, die eine Seite schreibt:

- LESEN: `notiz` gilt vor dem alten Namen (`herleitung`, `note`, `warum`), und das
  Datum gehoert zu dem Text, der gilt.
- SCHREIBEN: Die Seite behaelt die Notiz des Eintrags und den Block `notizen:` der
  Datei. Speichern ohne Aenderung aendert nichts, auch das Datum nicht, auch ein
  fehlendes. Ein neuer Text steht unter `notiz`, mit dem heutigen Datum.

Die Seiten, die ueber eine Route schreiben (Bestaende, Verpflichtungen, Ziele,
Klammern, Kredit-Anschluss), stehen in `tests/test_notizen_seiten.py`. Alle Dateien
hier sind erfunden und liegen in einem Wegwerfordner, nie in `config/`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from finctl import abos, geteilt, kontenregeln, module, objekte, renten, strom, zinssaetze
from finctl import konten as konten_register
from finctl.forecast import prognosebasis
from finctl.forecast import ziele as ziele_mod
from finctl.ledger.db import connect, init_db
from finctl.rules import engine, regelwerk
from finctl.tax import taxonomy as tx

HEUTE = date.today().isoformat()
BEREICH = {"bereich": {"notiz": "Fuer die ganze Datei", "notiz_vom": "2026-01-01"}}


def _datei(pfad: Path, inhalt: dict | str) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(inhalt if isinstance(inhalt, str) else
                    yaml.safe_dump(inhalt, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")
    return pfad


def _gelesen(pfad: Path) -> dict:
    return yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}


@pytest.fixture
def config(tmp_path, monkeypatch) -> Path:
    """Ein leerer `config/`-Ordner, auf den die Module zeigen, die ihn selbst suchen."""
    ordner = tmp_path / "config"
    ordner.mkdir()
    for modul in (kontenregeln, module, zinssaetze, prognosebasis):
        monkeypatch.setattr(modul, "CONFIG_DIR", ordner)
    return ordner


# ------------------------------------------------------------------ Rente


def _renten(config: Path) -> Path:
    return _datei(config / "renten.yaml", {"renten": [
        {"id": "gesetzlich", "name": "Gesetzliche Rente", "art": "rente",
         "cents": 150_000, "stand": "2026-01-01", "notiz": "Aus der Renteninformation"},
        {"id": "police", "name": "Police", "art": "kapital", "kaufkraft": "nominal",
         "cents": 4_000_000, "notiz": "Aus der Datei", "notiz_vom": "2026-02-01"}],
        "notizen": BEREICH})


def test_a_pension_reads_its_note_and_the_date_that_belongs_to_the_text(config):
    _renten(config)
    q = {x.id: x for x in renten.quellen(config)}
    assert (q["gesetzlich"].notiz, q["gesetzlich"].notiz_vom) == ("Aus der Renteninformation", "")
    assert (q["police"].notiz, q["police"].notiz_vom) == ("Aus der Datei", "2026-02-01")


def test_saving_a_pension_keeps_its_note_its_date_and_the_block(config):
    datei = _renten(config)
    renten.setzen("police", {"cents": 4_100_000}, config)
    police = _gelesen(datei)["renten"][1]
    assert (police["notiz"], str(police["notiz_vom"]), police["cents"]) == (
        "Aus der Datei", "2026-02-01", 4_100_000)
    assert _gelesen(datei)["notizen"] == BEREICH

    # Derselbe Text noch einmal: nichts aendert sich, auch kein Datum, auch kein fehlendes.
    vorher = datei.read_bytes()
    renten.setzen("police", {"notiz": "Aus der Datei"}, config)
    renten.setzen("police", {"notiz": "  Aus der Datei \n"}, config)
    renten.setzen("gesetzlich", {"notiz": "Aus der Renteninformation"}, config)
    assert datei.read_bytes() == vorher
    assert "notiz_vom" not in _gelesen(datei)["renten"][0]


def test_a_changed_pension_note_gets_todays_date_and_empty_removes_it(config):
    datei = _renten(config)
    renten.setzen("police", {"notiz": "Neu"}, config)
    police = _gelesen(datei)["renten"][1]
    assert (police["notiz"], str(police["notiz_vom"])) == ("Neu", HEUTE)
    assert {q.id: q.notiz_vom for q in renten.quellen(config)}["police"] == HEUTE

    renten.setzen("police", {"notiz": ""}, config)
    police = _gelesen(datei)["renten"][1]
    assert "notiz" not in police and "notiz_vom" not in police


def test_a_multi_line_pension_note_survives_with_every_line_break(config):
    datei = _renten(config)
    text = "Eins.\n\nZwei, nach einer Leerzeile.\n  Drei, eingerueckt."
    renten.setzen("police", {"notiz": text}, config)
    assert _gelesen(datei)["renten"][1]["notiz"] == text
    assert {q.id: q.notiz for q in renten.quellen(config)}["police"] == text
    vorher = datei.read_bytes()
    renten.setzen("police", {"notiz": text}, config)
    assert datei.read_bytes() == vorher


def test_a_pension_note_is_not_cut_at_the_old_limits(config):
    _renten(config)
    lang = "Ein Absatz. " * 400                     # rund 4.800 Zeichen
    renten.setzen("police", {"notiz": lang}, config)
    assert {q.id: q.notiz for q in renten.quellen(config)}["police"] == lang.strip()


# ------------------------------------------------------------ Konto-Regel


def test_an_account_rule_shows_its_note_under_both_names(config):
    _datei(config / "forecast.yaml", {"account_roles": {
        "a": {"role": "operating", "notiz": "Neuer Name", "notiz_vom": "2026-02-01"},
        "b": {"role": "puffer"}}})
    regeln = kontenregeln.wirksam()["account_roles"]
    assert (regeln["a"]["note"], regeln["a"]["notiz"], regeln["a"]["notiz_vom"]) == (
        "Neuer Name", "Neuer Name", "2026-02-01")
    assert "note" not in regeln["b"]


def test_saving_an_account_rule_keeps_the_note_and_the_block(config):
    datei = _datei(config / "forecast.yaml", {
        "account_roles": {"a": {"role": "operating", "floor_cents": 100, "notiz": "Ohne Datum"}},
        "notizen": BEREICH})
    kontenregeln.setzen("a", {"ceiling_cents": 500_000})
    regel = _gelesen(datei)["account_roles"]["a"]
    assert (regel["notiz"], "notiz_vom" in regel, regel["floor_cents"], regel["role"]) == (
        "Ohne Datum", False, 100, "operating")
    assert _gelesen(datei)["notizen"] == BEREICH

    # Derselbe Text, auch mit Rand: keine Aenderung, kein Datum.
    vorher = datei.read_bytes()
    kontenregeln.setzen("a", {"note": "Ohne Datum"})
    kontenregeln.setzen("a", {"note": " Ohne Datum"})
    assert datei.read_bytes() == vorher

    # Ein neuer Text bekommt das heutige Datum; der alte Name kommt nicht in die Datei.
    kontenregeln.setzen("a", {"note": "Neu"})
    regel = _gelesen(datei)["account_roles"]["a"]
    assert (regel["notiz"], regel["notiz_vom"], "note" in regel) == ("Neu", HEUTE, False)
    assert kontenregeln.wirksam()["account_roles"]["a"]["note"] == "Neu"

    # Leer loescht die Notiz samt Datum -- es gibt keine Basis mehr, die dann wieder gilt.
    kontenregeln.setzen("a", {"note": ""})
    regel = _gelesen(datei)["account_roles"]["a"]
    assert "notiz" not in regel and "notiz_vom" not in regel


def test_saving_an_account_rule_without_a_change_changes_nothing(config):
    """Was die Seite beim Speichern sendet, ist jedes Feld -- auch der Standard eines Schalters."""
    datei = _datei(config / "forecast.yaml", {
        "account_roles": {"a": {"role": "operating", "ceiling_cents": 500_000,
                                "notiz": "Warum"}},
        "account_budgets": {"a": 40_000}})
    vorher = datei.read_bytes()
    kontenregeln.setzen("a", {"note": "Warum", "role": "operating", "auffuellen": True,
                              "floor_from_loan": False, "ceiling_cents": 500_000,
                              "sweep_to": None, "budget_cents": 40_000})
    assert datei.read_bytes() == vorher


def test_the_loan_behind_a_floor_survives_a_save_that_sends_the_tick_as_true(config):
    """`floor_from_loan` heisst die Kennung des Kredits; die Karte schickt nur den Haken."""
    datei = _datei(config / "forecast.yaml", {
        "account_roles": {"rate": {"role": "servicing", "floor_from_loan": "k1"}}})
    vorher = datei.read_bytes()
    kontenregeln.setzen("rate", {"floor_from_loan": True, "auffuellen": True})
    assert datei.read_bytes() == vorher
    # Ausschalten nimmt den Kredit heraus, und ein Haken ohne Kredit bleibt, wie er war.
    kontenregeln.setzen("rate", {"floor_from_loan": False})
    assert _gelesen(datei)["account_roles"]["rate"]["floor_from_loan"] is False


def test_an_account_rule_is_written_as_a_whole_entry_and_a_cleared_field_is_gone(config):
    datei = _datei(config / "forecast.yaml", {
        "min_occurrences": 5,
        "account_roles": {"a": {"role": "operating", "ceiling_cents": 500_000,
                                "sweep_to": "b", "notiz": "Warum"}}})
    kontenregeln.setzen("a", {"ceiling_cents": None, "auffuellen": False, "budget_cents": 100})
    spec = _gelesen(datei)
    assert spec["account_roles"]["a"] == {"role": "operating", "sweep_to": "b",
                                          "notiz": "Warum", "auffuellen": False}
    assert (spec["min_occurrences"], spec["account_budgets"]) == (5, {"a": 100})
    # Ohne Betriebskonto-Rolle rechnet das Abraeumziel nichts: es faellt weg.
    kontenregeln.setzen("a", {"role": "savings"})
    assert "sweep_to" not in _gelesen(datei)["account_roles"]["a"]


def test_a_new_account_rule_creates_the_file_and_the_block_survives(config):
    kontenregeln.setzen("a", {"role": "savings", "note": "Neu angelegt"})
    spec = _gelesen(config / "forecast.yaml")
    assert spec["account_roles"]["a"]["role"] == "savings"
    assert (spec["account_roles"]["a"]["notiz"], spec["account_roles"]["a"]["notiz_vom"]) == (
        "Neu angelegt", HEUTE)


# ------------------------------------------------------------------- Abo


def _abo(kennung: str, **mehr) -> dict:
    return {"id": kennung, "name": kennung.capitalize(), "kategorie": "freizeit/abo",
            "konto": "giro", "betrag_cents": -1_000, "takt": 1, "faellig": "2026-01-05", **mehr}


def _abodatei(config: Path) -> Path:
    return _datei(config / "abos.yaml", {"abos": [
        _abo("alt", notiz="Alter Text"),
        _abo("neu", notiz="Neuer Text", notiz_vom="2026-02-01")], "notizen": BEREICH})


def test_a_contract_reads_its_note_and_the_page_still_calls_it_warum(config):
    datei = _abodatei(config)
    a = {x["id"]: x for x in abos.laden(datei)}
    assert (a["alt"]["warum"], a["neu"]["warum"]) == ("Alter Text", "Neuer Text")


def test_saving_a_contract_keeps_the_note_the_date_and_the_block(config):
    datei = _abodatei(config)
    # Wie die Seite speichert: das ganze Abo, so wie sie es geladen hat.
    seite = next(x for x in abos.laden(datei) if x["id"] == "alt")
    abos.speichern({**seite, "takt": 3}, datei)
    gespeichert = _gelesen(datei)
    alt = next(e for e in gespeichert["abos"] if e["id"] == "alt")
    assert (alt["notiz"], alt["takt"]) == ("Alter Text", 3)
    assert "notiz_vom" not in alt
    assert gespeichert["notizen"] == BEREICH
    # Der andere Eintrag bleibt, wie er war.
    assert next(e for e in gespeichert["abos"] if e["id"] == "neu")["notiz_vom"] == "2026-02-01"

    # Speichern ohne Aenderung aendert nichts.
    vorher = datei.read_bytes()
    seite = next(x for x in abos.laden(datei) if x["id"] == "alt")
    abos.speichern(seite, datei)
    assert datei.read_bytes() == vorher


def test_a_changed_contract_note_gets_todays_date(config):
    datei = _abodatei(config)
    seite = next(x for x in abos.laden(datei) if x["id"] == "alt")
    abos.speichern({**seite, "warum": "Neu"}, datei)
    eintrag = next(e for e in _gelesen(datei)["abos"] if e["id"] == "alt")
    assert (eintrag["notiz"], str(eintrag["notiz_vom"])) == ("Neu", HEUTE)
    assert "warum" not in eintrag
    assert next(x for x in abos.laden(datei) if x["id"] == "alt")["warum"] == "Neu"


def test_a_multi_line_contract_note_survives_with_every_line_break(config):
    datei = _abodatei(config)
    text = "Eins.\n\nZwei, nach einer Leerzeile.\n  Drei, eingerueckt."
    seite = next(x for x in abos.laden(datei) if x["id"] == "alt")
    abos.speichern({**seite, "warum": text}, datei)
    assert next(x for x in abos.laden(datei) if x["id"] == "alt")["warum"] == text
    vorher = datei.read_bytes()
    abos.speichern({**seite, "warum": text}, datei)
    assert datei.read_bytes() == vorher


def test_an_insurance_is_the_same_machine(config):
    datei = _datei(config / "versicherungen.yaml", {"versicherungen": [_abo("haus", notiz="Alt")]})
    seite = abos.laden(datei, "versicherung")[0]
    abos.speichern({**seite, "warum": "Neu"}, datei, "versicherung")
    assert _gelesen(datei)["versicherungen"][0]["notiz"] == "Neu"
    assert abos.laden(datei, "versicherung")[0]["warum"] == "Neu"


# ------------------------------------------------------------------ Konto


def test_an_account_keeps_its_note_when_another_is_created(config, tmp_path):
    datei = _datei(config / "accounts.yaml", {"accounts": [
        {"id": "giro", "display_name": "Giro", "institution": "Bank A", "account_type": "giro",
         "ingest_mode": "summary", "notiz": "Aus der Datei", "notiz_vom": "2026-02-01"},
        {"id": "tag", "display_name": "Tag", "institution": "Bank A",
         "account_type": "tagesgeld", "ingest_mode": "summary", "notiz": "Ohne Datum"}],
        "notizen": BEREICH})
    konten = {k["id"]: k for k in konten_register.laden(config)}
    assert (konten["giro"]["notiz"], konten["giro"]["notiz_vom"]) == ("Aus der Datei",
                                                                      "2026-02-01")
    assert (konten["tag"]["notiz"], "notiz_vom" in konten["tag"]) == ("Ohne Datum", False)

    c = connect(init_db(tmp_path / "t.db"))
    konten_register.anlegen(c, {"id": "neu", "display_name": "Neu", "institution": "Bank B",
                                "account_type": "tagesgeld", "ingest_mode": "summary"},
                            config, tmp_path / "auszuege")
    c.close()
    gespeichert = _gelesen(datei)
    je_id = {k["id"]: k for k in gespeichert["accounts"]}
    assert (je_id["giro"]["notiz"], str(je_id["giro"]["notiz_vom"])) == ("Aus der Datei",
                                                                         "2026-02-01")
    assert je_id["tag"]["notiz"] == "Ohne Datum" and "notiz_vom" not in je_id["tag"]
    assert gespeichert["notizen"] == BEREICH
    assert "neu" in je_id


def test_an_account_cannot_be_called_like_a_field_of_a_note(config):
    for wort in ("notiz", "notiz_vom", "notizen"):
        fehler = konten_register.pruefen(
            {"id": wort, "display_name": "X", "institution": "Y", "account_type": "giro",
             "ingest_mode": "summary"}, set())
        assert any("reserviert" in f for f in fehler), wort


# ----------------------------------------------------------------- Kredit


def _kredite(config: Path):
    return _datei(config / "loans.yaml", {
        "loans": [{"id": "kredit-a", "name": "Kredit A", "notiz": "Mit Datum",
                   "notiz_vom": "2026-02-01"},
                  {"id": "kredit-b", "name": "Kredit B", "notiz": "Ohne Datum"}],
        "notizen": BEREICH})


def test_a_loan_reads_its_note_from_the_one_file(config):
    from finctl.realestate.loan import lade_kredite

    _kredite(config)
    k = {x["id"]: x for x in lade_kredite(config)}
    assert (k["kredit-a"]["notiz"], k["kredit-a"]["notiz_vom"]) == ("Mit Datum", "2026-02-01")
    assert (k["kredit-b"]["notiz"], "notiz_vom" in k["kredit-b"]) == ("Ohne Datum", False)


def test_creating_and_removing_a_loan_keeps_the_notes_of_the_others(config):
    from finctl import kredite

    datei = _kredite(config)
    kredite.anlegen({
        "id": "kredit-c", "name": "Kredit C", "lender": "Bank", "servicing_account_id": "giro",
        "start": "2026-01-01", "ende": "2028-01-01", "opening_balance_cents": 1_000_000,
        "annual_rate_pct": 4.0, "annuity_cents": 50_000}, config)
    gespeichert = _gelesen(datei)
    je_id = {k["id"]: k for k in gespeichert["loans"]}
    assert (je_id["kredit-a"]["notiz"], je_id["kredit-a"]["notiz_vom"]) == (
        "Mit Datum", "2026-02-01")
    assert "notiz_vom" not in je_id["kredit-b"]
    assert gespeichert["notizen"] == BEREICH
    kredite.entfernen("kredit-c", config)
    assert _gelesen(datei)["loans"][0]["notiz_vom"] == "2026-02-01"


def test_the_conditions_a_page_sets_keep_the_note_of_the_loan(config):
    from finctl import kredite

    datei = _kredite(config)
    kredite.an_kredit_setzen("kredit-b", kredite.ANSCHLUSS,
                             {"zins_pct": 4.0, "tilgung_pct": 2.0}, config)
    gespeichert = _gelesen(datei)
    kredit_b = gespeichert["loans"][1]
    assert kredit_b["notiz"] == "Ohne Datum" and "notiz_vom" not in kredit_b
    assert kredit_b["anschluss_eingegeben"] == {"zins_pct": 4.0, "tilgung_pct": 2.0}
    assert gespeichert["notizen"] == BEREICH


# ----------------------------------------------------------------- Objekt


def test_a_property_keeps_its_note_through_every_page_that_writes_it(config):
    datei = _datei(config / "properties.yaml", {
        "properties": [{"id": "haus-a", "name": "Haus A", "status": "vermietet",
                        "notiz": "Mit Datum", "notiz_vom": "2026-02-01"},
                       {"id": "haus-c", "name": "Haus C", "status": "vermietet",
                        "notiz": "Ohne Datum"}],
        "notizen": BEREICH})
    haus = objekte.vorhandene(config)["haus-a"]
    assert (haus["notiz"], haus["notiz_vom"]) == ("Mit Datum", "2026-02-01")

    objekte.prognose_setzen("haus-a", {"miete_monatlich_cents": 100_000}, config)
    objekte.anlegen({"id": "haus-b", "name": "Haus B", "status": "rented"}, config)
    objekte.felder_setzen("haus-a", {"purchase_price_cents": 5_000_000}, config)
    objekte.felder_setzen("haus-c", {"equity_cents": 1_000_000}, config)
    gespeichert = _gelesen(datei)
    je_id = {p["id"]: p for p in gespeichert["properties"]}
    assert (je_id["haus-a"]["notiz"], je_id["haus-a"]["notiz_vom"]) == ("Mit Datum", "2026-02-01")
    assert je_id["haus-a"]["purchase_price_cents"] == 5_000_000
    assert je_id["haus-a"]["prognose"] == {"miete_monatlich_cents": 100_000}
    assert je_id["haus-c"]["notiz"] == "Ohne Datum" and "notiz_vom" not in je_id["haus-c"]
    assert gespeichert["notizen"] == BEREICH


# ------------------------------------------------------------------ Regel


def test_a_rule_keeps_its_note_when_the_page_saves_it(tmp_path):
    basis = _datei(tmp_path / "rules.yaml", {"rules": [
        {"id": "r-a", "name": "Regel A", "match": {"text": ["alpha"]},
         "set": {"mgmt": "konsum/essen"}, "notiz": "Mit Datum", "notiz_vom": "2026-02-01"},
        {"id": "r-b", "name": "Regel B", "match": {"text": ["beta"]},
         "set": {"mgmt": "konsum/essen"}, "notiz": "Ohne Datum"}], "notizen": BEREICH})
    regeln = {r["id"]: r for r in regelwerk.laden(basis)}
    assert (regeln["r-b"]["notiz"], "notiz_vom" in regeln["r-b"]) == ("Ohne Datum", False)
    assert regeln["r-a"]["notiz_vom"] == "2026-02-01"

    # Die Seite reicht die Regel durch, wie sie sie geladen hat.
    vorher = basis.read_bytes()
    regelwerk.speichern(regeln["r-a"], basis)
    regelwerk.speichern(regeln["r-b"], basis)
    assert basis.read_bytes() == vorher

    regelwerk.speichern({**regeln["r-b"], "priority": 50}, basis)
    gespeichert = _gelesen(basis)
    je_id = {r["id"]: r for r in gespeichert["rules"]}
    assert je_id["r-b"]["notiz"] == "Ohne Datum" and "notiz_vom" not in je_id["r-b"]
    assert je_id["r-b"]["priority"] == 50
    assert (je_id["r-a"]["notiz"], str(je_id["r-a"]["notiz_vom"])) == ("Mit Datum", "2026-02-01")
    assert gespeichert["notizen"] == BEREICH
    assert [r["notiz"] for r in engine.rohe_regeln(basis)] == ["Mit Datum", "Ohne Datum"]


# -------------------------------------------------------------- Kategorie


def test_a_category_keeps_its_note_when_a_leaf_is_added_or_removed(tmp_path):
    datei = _datei(tmp_path / "taxonomy.yaml", {
        "management": {"alltag": {"name": "Alltag", "kind": "expense",
                                  "children": {"markt": "Markt", "essen": "Essen"},
                                  "notiz": "Warum der Oberbegriff so ist",
                                  "notiz_vom": "2026-01-01"}},
        "notizen": BEREICH})

    tx.save("management", "alltag", "reise", "Reise", path=datei)
    tx.save("management", "alltag", "essen", None, remove=True, path=datei)
    tx.save("management", "alltag", "reise", None, remove=True, path=datei)
    gespeichert = _gelesen(datei)
    knoten = gespeichert["management"]["alltag"]
    assert (knoten["notiz"], knoten["notiz_vom"], knoten["name"]) == (
        "Warum der Oberbegriff so ist", "2026-01-01", "Alltag")
    assert gespeichert["notizen"] == BEREICH
    assert set(tx.load_spec(datei)["management"]["alltag"]["children"]) == {"markt"}


def test_renaming_a_leaf_keeps_what_else_it_says(tmp_path):
    datei = _datei(tmp_path / "taxonomy.yaml", {"management": {
        "alltag": {"name": "Alltag", "kind": "expense", "children": {
            "markt": {"name": "Markt", "fix": True, "tax": "privat/x"}, "essen": "Essen"}}}})
    tx.save("management", "alltag", "markt", "Wochenmarkt", path=datei)
    tx.save("management", "alltag", "essen", "Mittagessen", path=datei)
    blaetter = _gelesen(datei)["management"]["alltag"]["children"]
    assert blaetter == {"markt": {"name": "Wochenmarkt", "fix": True, "tax": "privat/x"},
                        "essen": "Mittagessen"}


def test_saving_a_category_without_a_change_changes_nothing(tmp_path):
    datei = _datei(tmp_path / "taxonomy.yaml", {"management": {
        "alltag": {"name": "Alltag", "kind": "expense", "children": {"markt": "Markt"}}}})
    vorher = datei.read_bytes()
    tx.save("management", "alltag", "markt", "Markt", path=datei)
    assert datei.read_bytes() == vorher


def test_a_category_note_does_not_become_a_category(tmp_path):
    datei = _datei(tmp_path / "taxonomy.yaml", {"management": {
        "alltag": {"name": "Alltag", "kind": "expense",
                   "children": {"markt": "Markt", "notiz_vom": "2026-01-01"}}}})
    assert set(tx.load_spec(datei)["management"]["alltag"]["children"]) == {"markt"}
    with pytest.raises(ValueError, match="reserviert"):
        tx.save("management", "alltag", "notiz", "Notiz", path=datei)


# ----------------------------------------------------------------- Projekt


def test_a_shared_project_keeps_its_note_and_the_block(tmp_path):
    pfad = _datei(tmp_path / "geteilt_custom.yaml", {
        "personen": [{"id": "p", "name": "P"}],
        "projekte": [{"id": "reise", "name": "Reise", "personen": ["p"],
                      "notiz": "Ohne Datum"}],
        "buchungen": [], "notizen": BEREICH})
    daten = geteilt.laden(pfad)
    assert daten.projekte["reise"].notiz.text == "Ohne Datum"
    vorher = pfad.read_bytes()
    geteilt.schreiben(daten, pfad)
    gespeichert = _gelesen(pfad)
    assert gespeichert["projekte"][0]["notiz"] == "Ohne Datum"
    assert "notiz_vom" not in gespeichert["projekte"][0]
    assert gespeichert["notizen"] == BEREICH
    assert yaml.safe_load(vorher) == gespeichert


# ------------------------------------------- Einstellungen, Dateien ohne Eintrag


def test_a_setting_written_to_the_assumptions_keeps_its_notes(config):
    from finctl import assumptions as ann

    datei = _datei(config / "assumptions.yaml", {
        "inflation_pa": 0.02, "kapital": {"rendite_depot_pa": 0.04},
        "notizen": {"inflation_pa": {"notiz": "Warum 2 %", "notiz_vom": "2026-02-01"},
                    "bereich": {"notiz": "Was die Plaene annehmen."}}})
    assert ann.setzen("rendite_depot_pa", 0.05, datei)
    gespeichert = _gelesen(datei)
    assert gespeichert["notizen"]["inflation_pa"]["notiz"] == "Warum 2 %"
    assert gespeichert["notizen"]["bereich"]["notiz"] == "Was die Plaene annehmen."
    assert gespeichert["kapital"] == {"rendite_depot_pa": 0.05}
    assert gespeichert["inflation_pa"] == 0.02


def test_files_without_entries_keep_their_block_when_a_page_writes_them(config, tmp_path):
    # Zinssaetze und die Prognosebasis.
    zins = _datei(config / "zinssaetze_custom.yaml", {
        "zinssaetze": {"tag": [{"ab": "2026-01", "bis": "2026-06", "satz": 0.02}]},
        "notizen": BEREICH})
    zinssaetze.anlegen("tag", "2026-07", None, 0.03)
    assert _gelesen(zins)["notizen"] == BEREICH
    assert len(_gelesen(zins)["zinssaetze"]["tag"]) == 2

    basis = _datei(config / prognosebasis.DATEI, {
        "nicht_fortschreiben": ["a"], "notizen": BEREICH})
    prognosebasis.setzen("b", False)
    assert _gelesen(basis)["notizen"] == BEREICH
    # Auch ohne Abweichung bleibt die Datei, solange sie Notizen traegt.
    prognosebasis.setzen("a", True)
    prognosebasis.setzen("b", True)
    assert _gelesen(basis) == {"notizen": BEREICH}

    # Strom (eigene Datei, eigener Pfad).
    s = _datei(tmp_path / "strom.yaml", {"zeitraeume": [], "ablesungen": [], "notizen": BEREICH})
    zeitraeume, ablesungen = strom.laden(s)
    strom.schreiben(zeitraeume, ablesungen, s)
    assert _gelesen(s)["notizen"] == BEREICH


def test_the_goals_machine_keeps_the_note_pair_of_the_file(config):
    spec = {"ziele": [{"id": "z", "name": "Z", "cents": 100_000, "notiz": "Aus der Datei",
                       "notiz_vom": "2026-02-01"}, {"id": "y", "name": "Y", "cents": 5,
                                                    "notiz": "Ohne Datum"}]}
    z, y = ziele_mod.aus_spec(spec)["ziele"]
    assert (z["notiz"], z["notiz_vom"]) == ("Aus der Datei", "2026-02-01")
    assert (y["notiz"], "notiz_vom" in y) == ("Ohne Datum", False)


# ------------------------------------------------------------------ Reihe


def test_a_series_note_without_a_date_stays_without_one(tmp_path, monkeypatch):
    from finctl import reihen

    ordner = tmp_path / "config"
    monkeypatch.setattr(reihen, "CONFIG_DIR", ordner)
    h1, h2 = "a" * 64, "b" * 64
    pfad = _datei(ordner / reihen.DATEI, {
        "reihen": [{"buchungen": [h1], "takt": 1, "notiz": "Ohne Datum"}],
        "zusammen": {"x gmbh": "x", "notiz": "falsch gesetzt"}, "notizen": BEREICH})
    assert [(e.notiz, e.notiz_vom) for e in reihen.lesen()] == [("Ohne Datum", "")]
    assert reihen.zusammen() == {"x gmbh": "x"}
    reihen._schreiben([reihen.Eintrag((h1,), 1, "Ohne Datum"),
                       reihen.Eintrag((h2,), 3, "Neu", "2026-05-05")])
    gespeichert = _gelesen(pfad)
    assert gespeichert["notizen"] == BEREICH
    assert "notiz_vom" not in gespeichert["reihen"][0]
    assert gespeichert["reihen"][1]["notiz_vom"] == "2026-05-05"
    assert reihen._notiz(reihen.lesen()[0], "Ohne Datum") == ("Ohne Datum", "")
    assert reihen._notiz(reihen.lesen()[0], "Anders") == ("Anders", HEUTE)
