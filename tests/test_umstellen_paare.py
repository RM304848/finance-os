"""Basis- und Seitendatei werden eine Datei (Schritt 5, N.3a: `forecast` und `taxonomy`).

Alle Dateien hier sind erfunden. Gezaehlt wird, was N.0 (Nummer 7) und N.3 sagen: Es gilt
danach genau, was vorher galt; trafen zwei Notizen zusammen, steht die der Basis zuerst; ein
Wert der Basis, den die Seite ueberschrieben hatte, steht in einer Notiz; nach dem Lauf gibt
es die Seitendatei nicht mehr.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

from finctl import kontenregeln, umstellen
from finctl import umstellen_paare as paare
from finctl.dateien import yaml_text
from finctl.ledger.db import connect, init_db
from finctl.tax import taxonomy as tx

HEUTE = date(2026, 10, 8)

FORECAST = {
    "min_occurrences": 5,
    "account_budgets": {"karte": 40_000, "spar": 10_000},
    "account_roles": {
        "giro": {"role": "operating", "floor_cents": 150_000, "ceiling_cents": 700_000,
                 "sweep_to": "tag", "notiz": "Betriebskonto.", "notiz_vom": "2026-09-01"},
        "karte": {"role": "consumption", "auffuellen": False, "notiz": "Alltag."},
        "tag": {"role": "savings", "floor_cents": 0},
    },
}
SEITE = {
    "account_roles": {
        "karte": {"role": "budget", "ceiling_cents": 5_000, "notiz": "Auf der Seite geaendert."},
        "tag": {"auffuellen": False},
        "neu": {"role": "savings", "notiz": "Nur auf der Seite."},
    },
    "account_budgets": {"karte": 55_000, "spar": None, "extra": 20_000},
}

TAXONOMIE = {
    "management": {
        "wohnen": {"name": "Wohnen", "kind": "expense", "fix": True, "notiz": "Mieten.",
                   "children": {"miete": {"name": "Miete", "fix": True},
                                "strom": "Strom"}},
        "versicherung": {"name": "Versicherung", "kind": "expense",
                         "children": {"bu": "Berufsunfaehigkeit", "phv": "Haftpflicht"}},
    },
    "tax": {"anlage_n": {"name": "Anlage N", "children": {"arbeit": {"name": "Arbeit"}}}},
}
TAX_SEITE = {
    "management": {
        "wohnen": {"name": "Wohnen und Co",
                   "children": {"miete": "Miete neu", "telefon": "Telefon"}},
        "versicherung": {"children": {"bu": "BU", "phv": "Haftpflicht"}, "notiz": "Gekuerzt."},
        "neu": {"children": {"x": "Ex"}},
    },
}


def _config(tmp_path: Path, **dateien) -> Path:
    config = tmp_path / "Daten" / "config"
    config.mkdir(parents=True)
    for name, inhalt in dateien.items():
        (config / name).write_text(
            inhalt if isinstance(inhalt, str) else yaml_text(inhalt), encoding="utf-8")
    return config


def _gelesen(config: Path, name: str) -> dict:
    return yaml.safe_load((config / name).read_text(encoding="utf-8"))


def _legen(paar: paare.Paar, basis: dict, seite: dict) -> tuple[dict, paare.Zusammenlegung]:
    gelegt = paare.zusammenlegen(paar, basis, seite)
    assert not gelegt.fehler, gelegt.fehler
    return yaml.safe_load(gelegt.neu), gelegt


FORECAST_PAAR = paare.PAARE[0]
TAXONOMIE_PAAR = paare.PAARE[1]


# ------------------------------------------------------------- forecast


def test_what_the_page_set_wins_field_by_field_as_before():
    neu, _ = _legen(FORECAST_PAAR, FORECAST, SEITE)
    rollen = neu["account_roles"]
    # Die Seite gewinnt, wo sie ein Feld nennt; was sie nicht nennt, bleibt.
    assert (rollen["karte"]["role"], rollen["karte"]["auffuellen"]) == ("budget", False)
    assert rollen["karte"]["ceiling_cents"] == 5_000
    assert rollen["giro"]["sweep_to"] == "tag"
    # Ein Feld, das nur in der Seite stand, gilt, und ein Konto nur in der Seite ebenso.
    assert rollen["tag"]["auffuellen"] is False
    assert rollen["neu"]["role"] == "savings"
    # Der Rest der Datei bleibt.
    assert neu["min_occurrences"] == 5


def test_the_merged_file_reads_like_both_files_did():
    basis, seite = FORECAST, SEITE
    neu, _ = _legen(FORECAST_PAAR, basis, seite)
    assert FORECAST_PAAR.alt(basis, seite) == FORECAST_PAAR.neu(neu)


def test_a_budget_is_replaced_or_removed_and_one_only_the_page_had_is_kept():
    neu, gelegt = _legen(FORECAST_PAAR, FORECAST, SEITE)
    assert neu["account_budgets"] == {"karte": 55_000, "extra": 20_000}
    assert sorted(gelegt.budgets) == ["extra", "karte", "spar"]


def test_a_base_value_the_page_overrode_stays_in_the_note_of_the_entry():
    neu, gelegt = _legen(FORECAST_PAAR, FORECAST, SEITE)
    notiz = neu["account_roles"]["karte"]["notiz"]
    assert "`role`: consumption" in notiz
    assert notiz.startswith("Alltag.\n\nAuf der Seite geaendert.\n\n")
    # Das Budget nennt seinen alten Wert in der Notiz der Konto-Regel, mit „Budget:“ davor.
    assert "Budget: Bis zur Umstellung stand in der Datei: 40000." in notiz
    assert ("karte.role", "consumption") in gelegt.ueberschrieben
    assert ("karte.budget", "40000") in gelegt.ueberschrieben
    assert ("spar.budget", "10000") in gelegt.ueberschrieben
    # Ein Konto nur mit Budget hat keine Regel: Der Satz geht in die Notiz des Bereichs.
    assert "Zu `account_budgets.spar`: Budget: " in neu["notizen"]["bereich"]["notiz"]
    assert "die Seite hatte es entfernt" in neu["notizen"]["bereich"]["notiz"]


def test_two_notes_become_one_with_the_base_first_and_the_later_date():
    seite = {"account_roles": {"giro": {"notiz": "Von der Seite.", "notiz_vom": "2026-10-02"}}}
    neu, gelegt = _legen(FORECAST_PAAR, FORECAST, seite)
    giro = neu["account_roles"]["giro"]
    assert giro["notiz"] == "Betriebskonto.\n\nVon der Seite."
    assert str(giro["notiz_vom"]) == "2026-10-02"
    assert gelegt.notizen == ["giro"]

    # Gleicher Text oder nur eine Notiz: nichts doppelt, das Datum bleibt.
    gleich = {"account_roles": {"giro": {"notiz": "Betriebskonto."}}}
    neu, gelegt = _legen(FORECAST_PAAR, FORECAST, gleich)
    assert neu["account_roles"]["giro"]["notiz"] == "Betriebskonto."
    assert str(neu["account_roles"]["giro"]["notiz_vom"]) == "2026-09-01"
    assert gelegt.notizen == []


def test_a_field_the_reader_never_read_is_reported_and_not_taken_over():
    seite = {"account_roles": {"giro": {"unbekannt": 1, "ceiling_cents": 800_000}}}
    neu, gelegt = _legen(FORECAST_PAAR, FORECAST, seite)
    assert "unbekannt" not in neu["account_roles"]["giro"]
    assert gelegt.ungelesen == ["account_roles.giro.unbekannt"]


def test_a_page_file_with_nothing_to_say_changes_nothing_in_the_base():
    gelegt = paare.zusammenlegen(FORECAST_PAAR, FORECAST, {},
                                 basis_text=yaml_text(FORECAST))
    assert gelegt.neu is None and not gelegt.fehler


def test_an_account_the_page_listed_without_fields_still_counts_as_an_account_rule():
    """Der alte Leser legte das Konto an, auch ohne Felder."""
    neu, _ = _legen(FORECAST_PAAR, FORECAST, {"account_roles": {"leer": None}})
    assert neu["account_roles"]["leer"] == {}


def test_the_floor_comes_from_the_account_rule_and_then_from_the_threshold_of_the_account():
    """Seit N.3f gibt es keine zweite Quelle: Die Untergrenze steht in `forecast.yaml`."""
    from finctl.forecast import konten as fk

    neu, _ = _legen(FORECAST_PAAR, FORECAST,
                    {"account_roles": {"giro": {"floor_cents": 120_000}}})
    acct = {"dispo_threshold_cents": 5_000}
    fcfg = kontenregeln.aus_spec(neu)
    assert fk._floor_for("giro", fcfg, acct) == 120_000          # die Seite, jetzt in der Datei
    assert fk._floor_for("tag", fcfg, acct) == 0                 # die Regel nennt 0, und 0 gilt
    assert fk._floor_for("karte", fcfg, acct) == 5_000           # keine Untergrenze: die Schwelle
    assert fk._floor_for("ohne-regel", fcfg, acct) == 5_000


# ------------------------------------------------------------- taxonomy


def test_a_leaf_of_the_page_replaces_the_leaf_of_the_base_and_the_parent_name_too():
    neu, gelegt = _legen(TAXONOMIE_PAAR, TAXONOMIE, TAX_SEITE)
    wohnen = neu["management"]["wohnen"]
    assert wohnen["name"] == "Wohnen und Co"
    assert wohnen["children"] == {"miete": "Miete neu", "strom": "Strom", "telefon": "Telefon"}
    # Die Merkmale des Oberbegriffs bleiben, wo die Seite sie nicht nennt.
    assert wohnen["fix"] is True
    assert neu["management"]["versicherung"]["children"]["bu"] == "BU"
    assert TAXONOMIE_PAAR.alt(TAXONOMIE, TAX_SEITE) == TAXONOMIE_PAAR.neu(neu)
    assert ("management.wohnen/miete", "{fix: true, name: Miete}") in gelegt.ueberschrieben


def test_a_parent_only_the_page_had_comes_with_name_kind_and_leaves():
    neu, gelegt = _legen(TAXONOMIE_PAAR, TAXONOMIE, TAX_SEITE)
    assert neu["management"]["neu"] == {"name": "neu", "kind": "expense",
                                        "children": {"x": "Ex"}}
    assert "management.neu (Oberbegriff, neu)" in gelegt.aus_seite
    assert "management.wohnen/telefon (Blatt, neu)" in gelegt.aus_seite
    assert "management.wohnen/miete (Blatt, ersetzt)" in gelegt.aus_seite
    assert "management.versicherung/phv (Blatt, gleich der Basis)" in gelegt.aus_seite


def test_what_the_page_replaced_in_the_taxonomy_stays_in_the_note_of_the_parent():
    neu, _ = _legen(TAXONOMIE_PAAR, TAXONOMIE, TAX_SEITE)
    wohnen = neu["management"]["wohnen"]["notiz"]
    assert wohnen.startswith("Mieten.\n\n" + paare.STAND_VORHER + ": ")
    assert "`name`: Wohnen" in wohnen and "Blatt `miete`: {fix: true, name: Miete}" in wohnen
    # Zwei Notizen am Oberbegriff: die der Basis zuerst; ohne Notiz in der Basis nur die der Seite.
    assert neu["management"]["versicherung"]["notiz"].startswith("Gekuerzt.\n\n")


def test_a_trait_the_old_reader_never_took_from_the_page_is_reported():
    seite = {"management": {"wohnen": {"kind": "income", "children": {}},
                            "neu": {"fix": True, "children": {"x": "Ex"}}}}
    neu, gelegt = _legen(TAXONOMIE_PAAR, TAXONOMIE, seite)
    assert neu["management"]["wohnen"]["kind"] == "expense"
    assert "fix" not in neu["management"]["neu"]
    assert sorted(gelegt.ungelesen) == ["management.neu.fix", "management.wohnen.kind"]


def test_a_missing_base_is_the_template_the_app_would_have_copied(tmp_path):
    config = _config(tmp_path, **{"taxonomy_custom.yaml": TAX_SEITE})
    plan = umstellen.planen(config)
    [gelegt] = plan.zusammenlegungen
    assert gelegt.neu is not None
    neu = yaml.safe_load(gelegt.neu)
    assert "einkommen" in neu["management"]                       # aus der Startvorlage
    assert neu["management"]["wohnen"]["children"]["telefon"] == "Telefon"


# --------------------------------------------- im Datenordner: der Lauf


def _pruefsumme(ordner: Path) -> str:
    h = hashlib.sha256()
    for pfad in sorted(p for p in ordner.rglob("*") if p.is_file()):
        h.update(str(pfad.relative_to(ordner)).encode())
        h.update(pfad.read_bytes())
    return h.hexdigest()


def _beide(tmp_path: Path) -> Path:
    config = _config(tmp_path, **{
        "forecast.yaml": FORECAST, "forecast_custom.yaml": SEITE,
        "taxonomy.yaml": TAXONOMIE, "taxonomy_custom.yaml": TAX_SEITE})
    return config.parent


def test_the_run_merges_both_pairs_removes_the_page_files_and_keeps_them_in_the_backup(tmp_path):
    wurzel = _beide(tmp_path)
    vorher = {n: (wurzel / "config" / n).read_bytes()
              for n in ("forecast_custom.yaml", "taxonomy_custom.yaml")}
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)

    assert not plan.fehler
    assert sorted(p.name for p in (wurzel / "config").iterdir()) == [
        "forecast.yaml", "taxonomy.yaml"]
    assert {n: (sicherung / "config" / n).read_bytes() for n in vorher} == vorher
    text = bericht.read_text(encoding="utf-8")
    assert "Zusammengelegt: `forecast_custom.yaml` in `forecast.yaml`" in text
    assert "Zusammengelegt: `taxonomy_custom.yaml` in `taxonomy.yaml`" in text
    assert "`karte.role`: consumption" in text

    # Zweiter Lauf: nichts, keine neue Sicherung, Prueffsumme gleich.
    summe = _pruefsumme(wurzel)
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert not plan.zu_tun and sicherung is None and bericht is None
    assert _pruefsumme(wurzel) == summe


def test_a_data_folder_with_only_the_base_file_has_nothing_to_do(tmp_path):
    config = _config(tmp_path, **{"forecast.yaml": FORECAST, "taxonomy.yaml": TAXONOMIE})
    assert not umstellen.planen(config).offen


def test_only_the_page_file_becomes_the_base_file(tmp_path):
    config = _config(tmp_path, **{"forecast_custom.yaml": SEITE})
    umstellen.ausfuehren(config.parent, heute=HEUTE)
    assert sorted(p.name for p in config.iterdir()) == ["forecast.yaml"]
    spec = _gelesen(config, "forecast.yaml")
    assert spec["account_roles"]["neu"]["role"] == "savings"
    assert spec["account_budgets"] == {"karte": 55_000, "extra": 20_000}


def test_the_probe_leaves_the_data_folder_alone_and_the_copy_has_no_page_file(tmp_path):
    wurzel = _beide(tmp_path)
    vorher = _pruefsumme(wurzel)
    probe = tmp_path / "Probe"
    plan, _ = umstellen.probieren(wurzel, probe, heute=HEUTE)
    assert _pruefsumme(wurzel) == vorher
    assert sorted(p.name for p in (probe / "config").iterdir()) == [
        "forecast.yaml", "taxonomy.yaml"]

    # Byte fuer Byte das, was der echte Lauf schreibt.
    umstellen.ausfuehren(wurzel, heute=HEUTE)
    for name in ("forecast.yaml", "taxonomy.yaml"):
        assert (probe / "config" / name).read_bytes() == (wurzel / "config" / name).read_bytes()
    assert plan.zusammenlegungen


def test_a_failed_check_writes_nothing(tmp_path, monkeypatch):
    """Verliert das Zusammenlegen ein Feld, hat der neue Leser andere Werte: Es bleibt alles."""
    def verliert(basis, seite, bericht):
        gelegt = paare._forecast_legen(basis, seite, bericht)
        gelegt["account_roles"]["giro"].pop("ceiling_cents")
        return gelegt

    kaputt = paare.Paar(FORECAST_PAAR.basis, FORECAST_PAAR.seite, verliert, FORECAST_PAAR.alt,
                        FORECAST_PAAR.neu, wurzeln=FORECAST_PAAR.wurzeln)
    monkeypatch.setattr(umstellen, "PAARE", (kaputt,))
    wurzel = _beide(tmp_path)
    vorher = _pruefsumme(wurzel)
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert plan.fehler and "liest sich nicht" in plan.fehler[0]
    assert sicherung is None and bericht is None and _pruefsumme(wurzel) == vorher
    assert plan.offen                                      # und die App bleibt angehalten


def test_a_lost_note_is_a_failed_check_too(monkeypatch):
    def verliert(basis, seite, bericht):
        gelegt = paare._forecast_legen(basis, seite, bericht)
        gelegt["account_roles"]["giro"]["notiz"] = "Etwas anderes."
        return gelegt

    kaputt = paare.Paar(FORECAST_PAAR.basis, FORECAST_PAAR.seite, verliert, FORECAST_PAAR.alt,
                        FORECAST_PAAR.neu, wurzeln=FORECAST_PAAR.wurzeln)
    gelegt = paare.zusammenlegen(kaputt, FORECAST,
                                 {"account_roles": {"giro": {"notiz": "Von der Seite."}}})
    assert any("steht nicht in der zusammengelegten" in f for f in gelegt.fehler)


def test_comments_of_both_files_become_notes_before_the_two_are_merged(tmp_path):
    config = _config(tmp_path, **{
        "forecast.yaml": "# Kopf der Basis.\naccount_roles:\n  giro:\n    role: operating\n"
                         "    # Warum.\n    floor_cents: 1000\n",
        "forecast_custom.yaml": "# Auf /konten gesetzt.\naccount_roles:\n  giro:\n"
                                "    # Aus der Seite.\n    ceiling_cents: 5000\n"})
    umstellen.ausfuehren(config.parent, heute=HEUTE)
    spec = _gelesen(config, "forecast.yaml")
    assert spec["account_roles"]["giro"]["notiz"] == "Warum.\n\nAus der Seite."
    assert spec["account_roles"]["giro"]["ceiling_cents"] == 5000
    assert "Kopf der Basis." in spec["notizen"]["bereich"]["notiz"]
    assert "Auf /konten gesetzt." in spec["notizen"]["bereich"]["notiz"]


# ----------------------------------------- Leser und Schreiber: nur noch eine Datei


def test_the_readers_and_writers_know_only_the_one_file(tmp_path, monkeypatch):
    """`kontenregeln` und `tax.taxonomy` lesen und schreiben `forecast.yaml` und `taxonomy.yaml`."""
    monkeypatch.setattr(kontenregeln, "CONFIG_DIR", tmp_path)
    (tmp_path / "forecast_custom.yaml").write_text(yaml_text(SEITE), encoding="utf-8")
    (tmp_path / "forecast.yaml").write_text(yaml_text(FORECAST), encoding="utf-8")
    assert kontenregeln.wirksam()["account_roles"]["karte"]["role"] == "consumption"
    kontenregeln.setzen("karte", {"role": "budget"})
    assert (tmp_path / "forecast_custom.yaml").read_text(encoding="utf-8") == yaml_text(SEITE)
    assert _gelesen(tmp_path, "forecast.yaml")["account_roles"]["karte"]["role"] == "budget"

    datei = tmp_path / "taxonomy.yaml"
    datei.write_text(yaml_text(TAXONOMIE), encoding="utf-8")
    (tmp_path / "taxonomy_custom.yaml").write_text(yaml_text(TAX_SEITE), encoding="utf-8")
    assert tx.load_spec(datei)["management"]["wohnen"]["name"] == "Wohnen"
    tx.save("management", "wohnen", "telefon", "Telefon", path=datei)
    assert _gelesen(tmp_path, "taxonomy.yaml")["management"]["wohnen"]["children"]["telefon"]
    assert (tmp_path / "taxonomy_custom.yaml").read_text(encoding="utf-8") == yaml_text(TAX_SEITE)


@pytest.mark.parametrize("fehlt", ["forecast.yaml", "taxonomy.yaml"])
def test_the_readers_need_no_second_file(tmp_path, monkeypatch, fehlt):
    monkeypatch.setattr(kontenregeln, "CONFIG_DIR", tmp_path)
    if fehlt == "taxonomy.yaml":
        (tmp_path / "forecast.yaml").write_text(yaml_text(FORECAST), encoding="utf-8")
        assert kontenregeln.wirksam()["account_budgets"] == {"karte": 40_000, "spar": 10_000}
    else:
        assert kontenregeln.wirksam()["account_roles"] == {}


def test_a_second_run_on_the_same_day_keeps_the_first_report(tmp_path):
    wurzel = _beide(tmp_path)
    _, _, erster = umstellen.ausfuehren(wurzel, heute=HEUTE)
    text = erster.read_text(encoding="utf-8")
    (wurzel / "config" / "forecast_custom.yaml").write_text(
        yaml_text({"account_roles": {"giro": {"ceiling_cents": 1}}}), encoding="utf-8")
    _, sicherung, zweiter = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert zweiter != erster and zweiter.name == "umstellung_2026-10-08_2.md"
    assert erster.read_text(encoding="utf-8") == text
    assert sicherung.name == "vor_umstellung_2026-10-08_2"


# =============================================================== N.3b: renten, abos, versicherungen


def _paar(basis: str) -> paare.Paar:
    return next(p for p in paare.PAARE if p.basis == basis)


RENTEN_PAAR = _paar("renten.yaml")
ABOS_PAAR = _paar("abos.yaml")
VERSICHERUNGEN_PAAR = _paar("versicherungen.yaml")

RENTEN = {
    "renten": [
        {"id": "gesetzlich", "name": "Gesetzliche Rente", "art": "rente", "kaufkraft": "heute",
         "cents": 150_000, "stand": None, "notiz": "Renteninformation.",
         "notiz_vom": "2026-09-01"},
        {"id": "police-a", "name": "Police A", "art": "kapital", "kaufkraft": "heute",
         "cents": 9_000_000, "ab": "2050-08", "konto": "police-a", "stand": None,
         "notiz": "Herleitung der Basis."},
        {"id": "police-b", "name": "Police B", "art": "kapital", "kaufkraft": "heute",
         "cents": 2_500_000, "ab": "2040-06", "stand": None},
    ],
    "notizen": {"bereich": {"notiz": "Was im Ruhestand hereinkommt."}},
}
RENTEN_SEITE = {
    "renten": {
        "gesetzlich": {"cents": 160_000, "stand": "2026-09-30"},
        "police-a": {"kosten_pa": 0.01, "ab": "2051-01", "notiz": "Im Monatsabschluss gesetzt.",
                     "notiz_vom": "2026-10-02"},
        "police-b": {"name": "Anderer Name"},
        "ohne-quelle": {"cents": 1},
    },
    "neu": [{"id": "bav", "name": "Betriebliche AV", "art": "kapital", "kaufkraft": "nominal",
             "ab": "2055-08", "cents": 20_000_000, "stand_cents": 2_000_000,
             "stand_wert": "2026-09-01", "beitrag_ag_cents": 240_000,
             "notiz": "Nur der Arbeitgeber zahlt."}],
    "notizen": {"bereich": {"notiz": "Im Monatsabschluss eingetragen."}},
}


def test_the_page_wins_per_pension_field_and_what_it_created_joins_the_list():
    neu, gelegt = _legen(RENTEN_PAAR, RENTEN, RENTEN_SEITE)
    je = {e["id"]: e for e in neu["renten"]}
    assert [e["id"] for e in neu["renten"]] == ["gesetzlich", "police-a", "police-b", "bav"]
    assert (je["gesetzlich"]["cents"], je["gesetzlich"]["stand"]) == (160_000, "2026-09-30")
    assert (je["police-a"]["ab"], je["police-a"]["kosten_pa"]) == ("2051-01", 0.01)
    assert je["bav"]["stand_cents"] == 2_000_000 and "neu" not in neu
    assert gelegt.aus_seite == ["bav (Quelle, in der Seite angelegt)"]


def test_the_merged_pension_file_reads_like_both_files_did():
    neu, _ = _legen(RENTEN_PAAR, RENTEN, RENTEN_SEITE)
    assert RENTEN_PAAR.alt(RENTEN, RENTEN_SEITE) == RENTEN_PAAR.neu(neu)


def test_only_a_base_value_that_was_really_replaced_counts_as_overridden():
    """Ein leerer Wert der Basis (`stand: null`) ist kein Wert, den die Seite ueberschrieb."""
    neu, gelegt = _legen(RENTEN_PAAR, RENTEN, RENTEN_SEITE)
    assert gelegt.ueberschrieben == [("gesetzlich.cents", "150000"), ("police-a.ab", "2050-08")]
    je = {e["id"]: e for e in neu["renten"]}
    assert "`cents`: 150000" in je["gesetzlich"]["notiz"]
    assert "stand" not in je["gesetzlich"]["notiz"].replace("Bis zur Umstellung stand", "")


def test_the_note_of_the_base_comes_first_then_the_one_of_the_page():
    neu, gelegt = _legen(RENTEN_PAAR, RENTEN, RENTEN_SEITE)
    police = {e["id"]: e for e in neu["renten"]}["police-a"]
    assert police["notiz"] == ("Herleitung der Basis.\n\nIm Monatsabschluss gesetzt.\n\n"
                               "Bis zur Umstellung stand in der Datei: `ab`: 2050-08.")
    assert str(police["notiz_vom"]) == "2026-10-02"
    assert "police-a" in gelegt.notizen and "notizen.bereich" in gelegt.notizen
    assert neu["notizen"]["bereich"]["notiz"] == (
        "Was im Ruhestand hereinkommt.\n\nIm Monatsabschluss eingetragen.")


def test_a_pension_field_or_entry_no_reader_ever_took_is_reported():
    neu, gelegt = _legen(RENTEN_PAAR, RENTEN, RENTEN_SEITE)
    assert sorted(gelegt.ungelesen) == ["renten.ohne-quelle (keine Quelle dazu)",
                                        "renten.police-b.name"]
    assert {e["id"]: e for e in neu["renten"]}["police-b"]["name"] == "Police B"


def test_a_created_pension_with_the_id_of_a_base_one_is_a_failed_check():
    gelegt = paare.zusammenlegen(RENTEN_PAAR, RENTEN, {"neu": [{"id": "gesetzlich"}]})
    assert gelegt.fehler and "steht schon in" in gelegt.fehler[0]


def test_a_pension_setting_of_the_page_can_empty_a_value_of_the_base():
    seite = {"renten": {"police-a": {"ab": None}}}
    neu, _ = _legen(RENTEN_PAAR, RENTEN, seite)
    assert RENTEN_PAAR.alt(RENTEN, seite) == RENTEN_PAAR.neu(neu)
    assert RENTEN_PAAR.neu(neu)[1]["ab"] is None


# ---------------------------------------------------------------- abos und versicherungen

ABOS = {
    "abos": [
        {"id": "video", "name": "Videodienst", "kategorie": "abo/video", "konto": "alltag",
         "betrag": -99.99, "takt": 12, "faellig": date(2027, 3, 10), "weg": "direkt",
         "notiz": "Ein Jahresabo."},
        {"id": "office", "name": "Office", "kategorie": "abo/office", "konto": "alltag",
         "betrag": -69.0, "takt": 12, "faellig": date(2027, 11, 1),
         "vorrat_bis": date(2027, 11, 1), "notiz": "Beim Haendler gekauft."},
        {"id": "altes", "name": "Altes Abo", "kategorie": "abo/x", "konto": "alltag",
         "betrag": -5.0, "takt": 1, "faellig": date(2026, 12, 1), "notiz": "Gekuendigt."},
    ],
    "notizen": {"bereich": {"notiz": "Abos mit Termin."}},
}
ABOS_SEITE = {
    "abos": {
        "video": {"betrag_cents": -12_000, "buchungen": ["h1", "h2"], "notiz": "Preis erhoeht.",
                  "notiz_vom": "2026-10-01"},
        "office": {"geteilt": {"besetzung": [{"name": "Mitnutzer", "anteil_cents": 1500}],
                               "zeitraeume": []}},
        "altes": {"entfernt": True},
        "streaming": {"name": "Streaming", "kategorie": "abo/y", "konto": "alltag",
                      "betrag_cents": -500, "takt": 1, "faellig": "2026-12-15",
                      "buchungen": [], "ignoriert": [], "geteilt": None,
                      "unbekannt": 1},
        "weg-damit": {"entfernt": True},
    },
}


def test_the_page_wins_per_contract_field_and_a_hidden_entry_is_gone():
    neu, gelegt = _legen(ABOS_PAAR, ABOS, ABOS_SEITE)
    je = {e["id"]: e for e in neu["abos"]}
    assert list(je) == ["video", "office", "streaming"]
    assert "betrag" not in je["video"] and je["video"]["betrag_cents"] == -12_000
    assert je["video"]["buchungen"] == ["h1", "h2"]
    assert je["office"]["geteilt"]["besetzung"][0]["name"] == "Mitnutzer"
    assert gelegt.ausgeblendet == ["weg-damit", "altes"]
    # Ein Eintrag, der nur in der Seite stand und ausgeblendet war, kommt gar nicht erst vor.
    assert "weg-damit" not in je and gelegt.aus_seite == [
        "streaming (Vertrag, in der Seite angelegt)"]
    # Die Begruendung des ausgeblendeten steht danach bei der Notiz des Bereichs.
    assert neu["notizen"]["bereich"]["notiz"] == (
        "Abos mit Termin.\n\nAusgeblendet bis zur Umstellung: `altes` (Altes Abo). Gekuendigt.")
    # Leere Felder der Seite stehen nicht in der Datei.
    assert set(je["streaming"]) == {"id", "name", "kategorie", "konto", "betrag_cents", "takt",
                                    "faellig", "notiz"} - {"notiz"}


def test_the_merged_contract_file_reads_like_both_files_did():
    neu, _ = _legen(ABOS_PAAR, ABOS, ABOS_SEITE)
    assert ABOS_PAAR.alt(ABOS, ABOS_SEITE) == ABOS_PAAR.neu(neu)
    assert [a["id"] for a in ABOS_PAAR.neu(neu)] == ["video", "office", "streaming"]


def test_a_contract_value_the_page_replaced_stays_in_the_note_of_the_base_first():
    neu, gelegt = _legen(ABOS_PAAR, ABOS, ABOS_SEITE)
    video = {e["id"]: e for e in neu["abos"]}["video"]
    assert video["notiz"] == ("Ein Jahresabo.\n\nPreis erhoeht.\n\nBis zur Umstellung stand "
                              "in der Datei: `betrag_cents`: -9999.")
    assert str(video["notiz_vom"]) == "2026-10-01"
    assert ("video.betrag_cents", "-9999") in gelegt.ueberschrieben
    assert gelegt.notizen == ["video"]
    assert gelegt.ungelesen == ["streaming.unbekannt"]


def test_insurances_are_merged_by_the_same_machine():
    basis = {"versicherungen": [
        {"id": "haftpflicht", "name": "Haftpflicht", "kategorie": "versicherung/phv",
         "konto": "alltag", "betrag": -6.0, "takt": 12, "faellig": date(2027, 1, 15)}]}
    seite = {"versicherungen": {"haftpflicht": {"faellig": "2028-01-15", "buchungen": ["x"]}}}
    neu, _ = _legen(VERSICHERUNGEN_PAAR, basis, seite)
    [eintrag] = neu["versicherungen"]
    assert (str(eintrag["faellig"]), eintrag["buchungen"]) == ("2028-01-15", ["x"])
    assert VERSICHERUNGEN_PAAR.alt(basis, seite) == VERSICHERUNGEN_PAAR.neu(neu)
    assert [a["id"] for a in VERSICHERUNGEN_PAAR.neu(neu)] == ["haftpflicht"]


# ---------------------------------------------------------- im Datenordner: der Lauf

def _drei_paare(tmp_path: Path) -> Path:
    config = _config(tmp_path, **{
        "renten.yaml": RENTEN, "renten_custom.yaml": RENTEN_SEITE,
        "abos.yaml": ABOS, "abos_custom.yaml": ABOS_SEITE,
        "versicherungen.yaml": {"versicherungen": []},
        "versicherungen_custom.yaml": {"versicherungen": {"phv": {
            "name": "Haftpflicht", "kategorie": "versicherung/phv", "konto": "alltag",
            "betrag_cents": -600, "takt": 12, "faellig": "2027-01-15"}}}})
    return config.parent


def test_the_run_merges_pensions_contracts_and_insurances_and_a_second_run_does_nothing(tmp_path):
    wurzel = _drei_paare(tmp_path)
    seiten = ("renten_custom.yaml", "abos_custom.yaml", "versicherungen_custom.yaml")
    vorher = {n: (wurzel / "config" / n).read_bytes() for n in seiten}
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)

    assert not plan.fehler, plan.fehler
    assert sorted(p.name for p in (wurzel / "config").iterdir()) == [
        "abos.yaml", "renten.yaml", "versicherungen.yaml"]
    assert {n: (sicherung / "config" / n).read_bytes() for n in vorher} == vorher
    text = bericht.read_text(encoding="utf-8")
    for seite, basis in zip(seiten, ("renten", "abos", "versicherungen"), strict=True):
        assert f"Zusammengelegt: `{seite}` in `{basis}.yaml`" in text
    assert "Ausgeblendet" in text and "`altes`" in text

    summe = _pruefsumme(wurzel)
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert not plan.zu_tun and sicherung is None and bericht is None
    assert _pruefsumme(wurzel) == summe


@pytest.mark.parametrize("name", ["renten", "abos", "versicherungen"])
def test_a_data_folder_with_only_the_page_file_gets_it_as_the_base_file(tmp_path, name):
    inhalt = {"renten": RENTEN_SEITE, "abos": {"abos": {
                  "video": {"name": "Videodienst", "kategorie": "abo/video", "konto": "alltag",
                            "betrag_cents": -12_000, "takt": 12, "faellig": "2027-03-10",
                            "notiz": "Preis erhoeht."},
                  "altes": {"entfernt": True}}},
              "versicherungen": {"versicherungen": {"phv": {
                  "name": "Haftpflicht", "kategorie": "versicherung/phv", "konto": "alltag",
                  "betrag_cents": -600, "takt": 12, "faellig": "2027-01-15"}}}}[name]
    config = _config(tmp_path, **{f"{name}_custom.yaml": inhalt})
    plan, _, _ = umstellen.ausfuehren(config.parent, heute=HEUTE)
    assert not plan.fehler, plan.fehler
    assert sorted(p.name for p in config.iterdir()) == [f"{name}.yaml"]
    assert not umstellen.planen(config).offen


@pytest.mark.parametrize("name", ["renten", "abos", "versicherungen"])
def test_a_data_folder_with_only_the_base_file_has_nothing_to_do_for_these_either(tmp_path, name):
    inhalt = {"renten": RENTEN, "abos": ABOS, "versicherungen": {"versicherungen": []}}[name]
    config = _config(tmp_path, **{f"{name}.yaml": inhalt})
    assert not umstellen.planen(config).offen


def test_comments_of_a_pension_pair_become_notes_before_the_two_are_merged(tmp_path):
    config = _config(tmp_path, **{
        "renten.yaml": "renten:\n  - id: gesetzlich\n    name: Rente\n    cents: 100\n"
                       "    # Aus dem Schreiben.\n    stand: null\n",
        "renten_custom.yaml": "renten:\n  gesetzlich:\n    # Im Abschluss.\n    cents: 200\n"})
    umstellen.ausfuehren(config.parent, heute=HEUTE)
    [rente] = _gelesen(config, "renten.yaml")["renten"]
    assert rente["notiz"].startswith("Aus dem Schreiben.\n\nIm Abschluss.")
    assert rente["cents"] == 200


# ================================================= N.3c: loans und properties (Kredite, Objekte)


KREDITE_PAAR = _paar("loans.yaml")
OBJEKTE_PAAR = _paar("properties.yaml")


def _segment(von: date, bis: date, satz: float, rate: int, art: str = "actual") -> dict:
    return {"start": von, "end": bis, "annual_rate_pct": satz, "annuity_cents": rate,
            "basis": art}


KREDITE = {
    "loans": [
        {"id": "alt-a", "name": "Darlehen A", "lender": "Bank A", "property_id": "haus-a",
         "servicing_account_id": "giro", "principal_cents": 10_000_000,
         "start_date": date(2020, 1, 1), "payment_cents": 50_000,
         "opening_balance_cents": 8_000_000, "opening_balance_as_of": date(2024, 1, 1),
         "segments": [_segment(date(2024, 1, 1), date(2030, 12, 31), 2.0, 50_000)],
         "zinsbindung_end": date(2030, 12, 31),
         # Das `anschluss` der Datei liest die Prognose.
         "anschluss": {"zins_pct": 3.5, "tilgung_pct": 2.0, "basis": "assumption"},
         "notiz": "Vertrag der Bank A.", "notiz_vom": "2026-05-01",
         "open": ["Anschluss klaeren"]},
        {"id": "alt-b", "name": "Darlehen B", "lender": "Bank B", "property_id": "haus-b",
         "servicing_account_id": "giro", "principal_cents": 6_000_000,
         "start_date": date(2021, 1, 1), "payment_cents": 30_000,
         "opening_balance_cents": 5_000_000, "opening_balance_as_of": date(2024, 1, 1),
         "segments": [_segment(date(2024, 1, 1), date(2040, 12, 31), 3.0, 30_000)],
         "zinsbindung_ende": date(2032, 6, 30)},
        {"id": "vorlage-c", "name": "Neubau (Vorlage)", "szenario": "kauf", "status": "geplant",
         "servicing_account_id": "giro", "principal_cents": 30_000_000,
         "start_date": date(2031, 1, 1), "payment_cents": 140_000,
         "opening_balance_cents": 30_000_000, "opening_balance_as_of": date(2031, 1, 1),
         "segments": [_segment(date(2031, 1, 1), date(2061, 1, 1), 3.8, 140_000, "annahme")]},
        {"id": "weg-d", "name": "Wird ausgeblendet", "lender": "Bank D",
         "servicing_account_id": "giro", "principal_cents": 1_000_000,
         "start_date": date(2022, 1, 1), "payment_cents": 10_000,
         "opening_balance_cents": 900_000, "opening_balance_as_of": date(2024, 1, 1),
         "segments": [_segment(date(2024, 1, 1), date(2030, 1, 1), 1.0, 10_000)],
         "notiz": "Warum der Kredit da war."},
    ],
    "notizen": {"bereich": {"notiz": "Die Kredite des Haushalts."}},
}
KREDITE_SEITE = {
    "kredite": {
        "alt-a": {"payment_cents": 55_000, "notiz": "Auf der Seite geaendert."},
        "weg-d": {"entfernt": True},
        "neu-e": {"name": "Ratenkredit E", "lender": "Bank E", "status": "active",
                  "servicing_account_id": "giro", "opening_balance_cents": 480_000,
                  "opening_balance_as_of": "2026-01-01", "payment_cents": 15_000,
                  "segments": [{"start": "2026-01-01", "end": "2029-01-01",
                                "annual_rate_pct": 6.0, "annuity_cents": 15_000,
                                "opening_balance_cents": 480_000, "basis": "assumption"}],
                  "notiz": "Auf der Seite angelegt.", "notiz_vom": "2026-09-09"},
        "nie-da": {"entfernt": True, "notiz": "Stand nur in der Seite."},
    },
    "vorlagen": {
        "vorlage-c": {"principal_cents": 32_000_000, "annual_rate_pct": 4.4,
                      "start": "2031-07-01", "ende": "2061-07-01"},
        "alt-a": {"principal_cents": 1},
        "kein-kredit": {"principal_cents": 2},
    },
    "anschluss": {
        "alt-a": {"zins_pct": 4.0, "tilgung_pct": 2.5, "basis": "assumption",
                  "ab": "2031-01-01"},
        "neu-e": {"zins_pct": 5.0, "tilgung_pct": 3.0, "basis": "assumption"},
        "weg-d": {"zins_pct": 9.0, "tilgung_pct": 9.0, "basis": "assumption"},
    },
    "notizen": {"bereich": {"notiz": "Von der Seite eingetragen."}},
}


def _kredit(neu: dict, kennung: str) -> dict:
    return next(k for k in neu["loans"] if k["id"] == kennung)


def test_the_page_wins_per_loan_field_and_what_it_created_joins_the_list():
    neu, gelegt = _legen(KREDITE_PAAR, KREDITE, KREDITE_SEITE)
    assert [k["id"] for k in neu["loans"]] == ["alt-a", "alt-b", "vorlage-c", "neu-e"]
    alt_a = _kredit(neu, "alt-a")
    assert alt_a["payment_cents"] == 55_000
    # Was die Seite nicht nennt, bleibt, auch die offenen Punkte.
    assert alt_a["open"] == ["Anschluss klaeren"] and alt_a["principal_cents"] == 10_000_000
    assert _kredit(neu, "neu-e")["segments"][0]["annual_rate_pct"] == 6.0
    assert "neu-e (Kredit, in der Seite angelegt)" in gelegt.aus_seite
    assert neu["notizen"]["bereich"]["notiz"].startswith("Die Kredite des Haushalts.")


def test_the_merged_loan_file_reads_like_both_files_did():
    neu, _ = _legen(KREDITE_PAAR, KREDITE, KREDITE_SEITE)
    assert KREDITE_PAAR.alt(KREDITE, KREDITE_SEITE) == KREDITE_PAAR.neu(neu)


def test_a_template_stays_a_template_on_the_loan_and_only_a_base_loan_gets_one():
    """`vorlagen.<id>` steht danach am Kredit unter `vorlage` und gilt wie vorher."""
    neu, gelegt = _legen(KREDITE_PAAR, KREDITE, KREDITE_SEITE)
    assert _kredit(neu, "vorlage-c")["vorlage"]["principal_cents"] == 32_000_000
    # Die Konditionen des Eintrags bleiben darunter stehen.
    assert _kredit(neu, "vorlage-c")["principal_cents"] == 30_000_000
    assert "vorlage-c (Vorlage, jetzt am Kredit)" in gelegt.aus_seite
    # Ein Kredit ohne Klammer las der alte Leser nie mit einer Vorlage; sie geht trotzdem mit.
    assert _kredit(neu, "alt-a")["vorlage"] == {"principal_cents": 1}
    assert "vorlagen.kein-kredit (kein Kredit der Basis dazu)" in gelegt.ungelesen
    assert not any("vorlage" in k for k in _kredit(neu, "neu-e"))


def test_a_follow_up_of_the_page_gets_its_own_key_and_never_replaces_the_one_of_the_file():
    neu, gelegt = _legen(KREDITE_PAAR, KREDITE, KREDITE_SEITE)
    alt_a = _kredit(neu, "alt-a")
    assert alt_a["anschluss"] == KREDITE["loans"][0]["anschluss"]
    assert alt_a["anschluss_eingegeben"]["zins_pct"] == 4.0
    assert _kredit(neu, "neu-e")["anschluss_eingegeben"]["zins_pct"] == 5.0
    assert "anschluss" not in _kredit(neu, "neu-e")
    # Von einem Kredit, der ausgeblendet war, sah die Seite nichts.
    assert "anschluss.weg-d (kein Kredit dazu)" in gelegt.ungelesen


def test_a_hidden_loan_is_gone_and_its_note_stays_with_the_area():
    neu, gelegt = _legen(KREDITE_PAAR, KREDITE, KREDITE_SEITE)
    assert "weg-d" not in [k["id"] for k in neu["loans"]]
    assert sorted(gelegt.ausgeblendet) == ["nie-da", "weg-d"]
    bereich = neu["notizen"]["bereich"]["notiz"]
    assert "Warum der Kredit da war." in bereich and "Stand nur in der Seite." in bereich
    assert "Von der Seite eingetragen." in bereich


def test_a_loan_value_the_page_replaced_stays_in_the_note_and_the_notes_meet_base_first():
    neu, gelegt = _legen(KREDITE_PAAR, KREDITE, KREDITE_SEITE)
    notiz = _kredit(neu, "alt-a")["notiz"]
    assert notiz.startswith("Vertrag der Bank A.\n\nAuf der Seite geaendert.")
    assert "Bis zur Umstellung stand in der Datei: `payment_cents`: 50000." in notiz
    assert ("alt-a.payment_cents", "50000") in gelegt.ueberschrieben
    assert "alt-a" in gelegt.notizen
    # Der Vorlagenkredit behielt seine Konditionen: nichts ueberschrieben.
    assert not any(k.startswith("vorlage-c") for k, _ in gelegt.ueberschrieben)


def test_what_the_old_reader_ignored_of_the_page_is_reported():
    _, gelegt = _legen(KREDITE_PAAR, KREDITE, {**KREDITE_SEITE, "erfunden": {"x": 1}})
    assert "erfunden (Schlüssel der Seite, den kein Leser kannte)" in gelegt.ungelesen


def test_a_loan_the_page_has_and_the_base_lacks_may_carry_its_own_follow_up_and_no_template():
    seite = {"kredite": {"neu-f": {"name": "F", "szenario": "kauf"}},
             "vorlagen": {"neu-f": {"principal_cents": 5}},
             "anschluss": {"neu-f": {"zins_pct": 3.0, "tilgung_pct": 2.0}}}
    neu, gelegt = _legen(KREDITE_PAAR, KREDITE, seite)
    f = _kredit(neu, "neu-f")
    assert "vorlage" not in f and f["anschluss_eingegeben"]["zins_pct"] == 3.0
    assert "vorlagen.neu-f (kein Kredit der Basis dazu)" in gelegt.ungelesen


def test_a_follow_up_the_page_entered_changes_no_number_the_forecast_reads(tmp_path, monkeypatch):
    """Das `anschluss` der Datei geht in die Prognose, `anschluss_eingegeben` nie."""
    from finctl.forecast import jahre
    from finctl.realestate.loan import lade_kredite, segments_from

    monkeypatch.setattr(jahre, "CONFIG_DIR", tmp_path)

    def plaene(spec: dict) -> dict:
        (tmp_path / "loans.yaml").write_text(yaml_text(spec), encoding="utf-8")
        return {str(k["id"]): [(p.month, p.payment_cents, p.interest_cents)
                               for p in s.payments]
                for k, s in jahre._tilgungsplaene(None)}

    neu, _ = _legen(KREDITE_PAAR, KREDITE, KREDITE_SEITE)
    ohne_eingabe = copy_ohne(neu, "anschluss_eingegeben")
    mit = plaene(neu)
    assert mit == plaene(ohne_eingabe)
    # Das Gegenstueck: nimmt man das `anschluss` der Datei, aendert sich die Prognose.
    ohne_anschluss = copy_ohne(neu, "anschluss")
    assert plaene(ohne_anschluss)["alt-a"] != mit["alt-a"]
    # Und die Zeilen der Kredite tragen die Eingabe der Seite, damit /kredite sie findet.
    (tmp_path / "loans.yaml").write_text(yaml_text(neu), encoding="utf-8")
    [a] = [k for k in lade_kredite(tmp_path) if k["id"] == "alt-a"]
    assert a["anschluss_eingegeben"]["zins_pct"] == 4.0
    assert segments_from(a)[-1].annual_rate_pct == 3.5


def copy_ohne(spec: dict, feld: str) -> dict:
    """Die Kreditdatei ohne dieses Feld an den Krediten."""
    import copy

    kopie = copy.deepcopy(spec)
    for kredit in kopie["loans"]:
        kredit.pop(feld, None)
    return kopie


def test_the_deadline_list_sees_a_follow_up_entered_on_the_page(tmp_path, monkeypatch):
    """`fristen` fragte `anschluss.<id>` der Seitendatei; jetzt fragt es den Kredit."""
    from finctl import fristen, module
    from finctl import kredite as kr

    monkeypatch.setattr(module, "seite_an", lambda pfad: pfad == "/kredite")
    monkeypatch.setattr("finctl.pfade.CONFIG_DIR", tmp_path)
    spiel = {"loans": [{"id": "k1", "name": "K1", "status": "active",
                        "zinsbindung_end": date(2027, 6, 30),
                        "segments": [_segment(date(2024, 1, 1), date(2027, 6, 30), 2.0, 500)]},
                       {"id": "k2", "name": "K2", "status": "active",
                        "zinsbindung_end": date(2028, 6, 30),
                        "segments": [_segment(date(2024, 1, 1), date(2028, 6, 30), 2.0, 500)],
                        kr.ANSCHLUSS: {"zins_pct": 4.0, "tilgung_pct": 2.0}}]}
    (tmp_path / "loans.yaml").write_text(yaml_text(spiel), encoding="utf-8")
    tun = {f.uid: f.tun for f in fristen.alle(date(2026, 10, 9))}
    assert tun["zinsbindung-k1"].startswith("Angebote")
    assert tun["zinsbindung-k2"].startswith("Anschluss steht")


# --------------------------------------------------------------------------- Objekte


def _objekt(neu: dict, kennung: str) -> dict:
    return next(o for o in neu["properties"] if o["id"] == kennung)


OBJEKTE = {
    "properties": [
        {"id": "haus-a", "name": "Haus A", "status": "rented", "acquired_on": date(2019, 3, 1),
         "afa_rate_pct": 2.0, "equity_cents": 5_000_000,
         "notiz": "Kaufvertrag.", "notiz_vom": "2026-04-01", "open": ["Dach pruefen"],
         "prognose": {"miete_monatlich_cents": 100_000, "kosten_monatlich_cents": 30_000,
                      "ab": "2026-01", "bis": "2030-06", "saison": [1.0] * 12}},
        {"id": "haus-b", "name": "Haus B", "status": "construction",
         "notiz": "Im Bau."},
        {"id": "haus-c", "name": "Wird ausgeblendet", "status": "rented",
         "notiz": "Warum das Objekt da war."},
    ],
    "notizen": {"bereich": {"notiz": "Die Objekte des Haushalts."}},
}
OBJEKTE_SEITE = {
    "objekte": {
        "haus-a": {"equity_cents": 6_000_000, "purchase_price_cents": 40_000_000,
                   "afa_start": "2019-04-01",
                   "prognose": {"miete_monatlich_cents": 110_000, "bis": "2031-12"},
                   "notiz": "Auf der Seite geaendert."},
        "haus-b": {"prognose": {"miete_monatlich_cents": 70_000}},
        "haus-c": {"entfernt": True},
        "haus-d": {"name": "Haus D", "status": "construction", "notiz": "Auf der Seite angelegt."},
        "nie-da": {"entfernt": True, "notiz": "Stand nur in der Seite."},
    },
    "notizen": {"bereich": {"notiz": "Von der Seite eingetragen."}},
}


def test_the_page_wins_per_property_field_and_the_forecast_per_subfield():
    neu, gelegt = _legen(OBJEKTE_PAAR, OBJEKTE, OBJEKTE_SEITE)
    assert [o["id"] for o in neu["properties"]] == ["haus-a", "haus-b", "haus-d"]
    a = _objekt(neu, "haus-a")
    assert (a["equity_cents"], a["purchase_price_cents"], a["afa_start"]) == (
        6_000_000, 40_000_000, "2019-04-01")
    assert a["open"] == ["Dach pruefen"] and a["afa_rate_pct"] == 2.0
    # Wer nur die Miete tippte, behielt Kosten, Beginn, Ende und Saison der Basis.
    assert a["prognose"] == {"miete_monatlich_cents": 110_000, "kosten_monatlich_cents": 30_000,
                             "ab": "2026-01", "bis": "2031-12", "saison": [1.0] * 12}
    # Ein Objekt ohne Prognose bekommt die der Seite.
    assert _objekt(neu, "haus-b")["prognose"] == {"miete_monatlich_cents": 70_000}
    assert "haus-d (Objekt, in der Seite angelegt)" in gelegt.aus_seite
    assert "haus-a.purchase_price_cents (Feld, nur in der Seite)" in gelegt.aus_seite
    assert "haus-b.prognose.miete_monatlich_cents (Feld, nur in der Seite)" in gelegt.aus_seite


def test_the_merged_property_file_reads_like_both_files_did():
    neu, _ = _legen(OBJEKTE_PAAR, OBJEKTE, OBJEKTE_SEITE)
    assert OBJEKTE_PAAR.alt(OBJEKTE, OBJEKTE_SEITE) == OBJEKTE_PAAR.neu(neu)


def test_a_property_value_the_page_replaced_stays_in_the_note_with_the_forecast_subfield():
    neu, gelegt = _legen(OBJEKTE_PAAR, OBJEKTE, OBJEKTE_SEITE)
    notiz = _objekt(neu, "haus-a")["notiz"]
    assert notiz.startswith("Kaufvertrag.\n\nAuf der Seite geaendert.")
    assert "`equity_cents`: 5000000" in notiz
    assert "`prognose.miete_monatlich_cents`: 100000" in notiz
    # Eine einzige Aufzaehlung, nicht zwei Saetze.
    assert notiz.count("Bis zur Umstellung stand in der Datei") == 1
    assert {"haus-a.equity_cents", "haus-a.prognose.miete_monatlich_cents",
            "haus-a.prognose.bis"} == {o for o, _ in gelegt.ueberschrieben}


def test_a_hidden_property_is_gone_and_its_note_stays_with_the_area():
    neu, gelegt = _legen(OBJEKTE_PAAR, OBJEKTE, OBJEKTE_SEITE)
    assert "haus-c" not in [o["id"] for o in neu["properties"]]
    assert sorted(gelegt.ausgeblendet) == ["haus-c", "nie-da"]
    bereich = neu["notizen"]["bereich"]["notiz"]
    assert "Warum das Objekt da war." in bereich and "Stand nur in der Seite." in bereich


def test_the_property_numbers_reach_the_table_as_before(tmp_path):
    """`init` spiegelt die Zahlen der Datei; vorher kamen sie aus dem Overlay."""
    from finctl import objekte
    from finctl.ledger.db import connect, init_db

    neu, _ = _legen(OBJEKTE_PAAR, OBJEKTE, OBJEKTE_SEITE)
    neu["properties"][0]["sold_on"] = date(2031, 1, 1)
    neu["properties"][1]["equity_cents"] = None
    (tmp_path / "properties.yaml").write_text(yaml_text(neu), encoding="utf-8")
    db = tmp_path / "t.db"
    init_db(db)
    c = connect(db)
    try:
        for kennung in ("haus-a", "haus-b"):
            c.execute("INSERT INTO properties (id, name, equity_cents, status) "
                      "VALUES (?, ?, 77, 'rented')", (kennung, kennung))
        objekte.in_db(c, tmp_path)
        a = dict(c.execute("SELECT * FROM properties WHERE id = 'haus-a'").fetchone())
        b = dict(c.execute("SELECT * FROM properties WHERE id = 'haus-b'").fetchone())
    finally:
        c.close()
    assert (a["purchase_price_cents"], a["equity_cents"], a["afa_start"], a["afa_rate_pct"]) == (
        40_000_000, 6_000_000, "2019-04-01", 2.0)
    assert (a["acquired_on"], a["sold_on"]) == ("2019-03-01", "2031-01-01")
    # Was die Datei nicht sagt (`null`), laesst die Zeile, wie sie ist.
    assert b["equity_cents"] == 77


# ------------------------------------------------------------- der Lauf


def _kredite_und_objekte(tmp_path: Path) -> Path:
    config = _config(tmp_path, **{
        "loans.yaml": KREDITE, "loans_custom.yaml": KREDITE_SEITE,
        "properties.yaml": OBJEKTE, "properties_custom.yaml": OBJEKTE_SEITE})
    return config.parent


def test_the_run_merges_loans_and_properties_and_a_second_run_does_nothing(tmp_path):
    wurzel = _kredite_und_objekte(tmp_path)
    seiten = ("loans_custom.yaml", "properties_custom.yaml")
    vorher = {n: (wurzel / "config" / n).read_bytes() for n in seiten}
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)

    assert not plan.fehler, plan.fehler
    assert sorted(p.name for p in (wurzel / "config").iterdir()) == [
        "loans.yaml", "properties.yaml"]
    assert {n: (sicherung / "config" / n).read_bytes() for n in vorher} == vorher
    text = bericht.read_text(encoding="utf-8")
    assert "Zusammengelegt: `loans_custom.yaml` in `loans.yaml`" in text
    assert "Zusammengelegt: `properties_custom.yaml` in `properties.yaml`" in text
    assert "`weg-d`" in text and "`haus-c`" in text

    summe = _pruefsumme(wurzel)
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert not plan.zu_tun and sicherung is None and bericht is None
    assert _pruefsumme(wurzel) == summe


def test_the_app_stops_while_a_loan_or_property_page_file_is_still_there(tmp_path):
    config = _config(tmp_path, **{"loans.yaml": KREDITE, "loans_custom.yaml": KREDITE_SEITE})
    assert umstellen.planen(config).offen
    with pytest.raises(umstellen.AlteFormError, match=r"loans_custom\.yaml"):
        umstellen.halt_wenn_offen(config)


@pytest.mark.parametrize("name", ["loans", "properties"])
def test_a_data_folder_with_only_the_page_file_gets_it_as_the_base_file_for_these_too(
        tmp_path, name):
    seite = {"loans": {"kredite": {"k1": {"name": "K1", "notiz": "Nur die Seite."}},
                       "anschluss": {"k1": {"zins_pct": 3.0, "tilgung_pct": 2.0}}},
             "properties": {"objekte": {"o1": {"name": "O1", "status": "rented"}}}}[name]
    config = _config(tmp_path, **{f"{name}_custom.yaml": seite})
    plan, _, _ = umstellen.ausfuehren(config.parent, heute=HEUTE)
    assert not plan.fehler, plan.fehler
    assert sorted(p.name for p in config.iterdir()) == [f"{name}.yaml"]
    assert not umstellen.planen(config).offen
    if name == "loans":
        [k] = _gelesen(config, "loans.yaml")["loans"]
        assert k["id"] == "k1" and k["anschluss_eingegeben"]["zins_pct"] == 3.0


@pytest.mark.parametrize("name", ["loans", "properties"])
def test_a_data_folder_with_only_the_base_file_has_nothing_to_do_for_these_too(tmp_path, name):
    config = _config(tmp_path, **{f"{name}.yaml": {"loans": KREDITE, "properties": OBJEKTE}[name]})
    assert not umstellen.planen(config).offen


def test_comments_of_a_loan_pair_become_notes_before_the_two_are_merged(tmp_path):
    config = _config(tmp_path, **{
        "loans.yaml": "loans:\n  - id: k1\n    name: K1\n    # Aus dem Vertrag.\n"
                      "    payment_cents: 100\n",
        "loans_custom.yaml": "kredite:\n  k1:\n    # Auf der Seite.\n    payment_cents: 200\n"})
    umstellen.ausfuehren(config.parent, heute=HEUTE)
    [kredit] = _gelesen(config, "loans.yaml")["loans"]
    assert kredit["notiz"].startswith("Aus dem Vertrag.\n\nAuf der Seite.")
    assert kredit["payment_cents"] == 200


# ------------------------------------ Leser und Schreiber: nur noch eine Datei


def test_the_loan_and_property_readers_and_writers_know_only_the_one_file(tmp_path):
    from finctl import kredite, objekte
    from finctl.realestate.loan import lade_kredite

    (tmp_path / "loans.yaml").write_text(yaml_text(KREDITE), encoding="utf-8")
    (tmp_path / "loans_custom.yaml").write_text(yaml_text(KREDITE_SEITE), encoding="utf-8")
    (tmp_path / "properties.yaml").write_text(yaml_text(OBJEKTE), encoding="utf-8")
    (tmp_path / "properties_custom.yaml").write_text(yaml_text(OBJEKTE_SEITE), encoding="utf-8")
    seite_k = (tmp_path / "loans_custom.yaml").read_bytes()
    seite_o = (tmp_path / "properties_custom.yaml").read_bytes()

    kredite_ids = [k["id"] for k in lade_kredite(tmp_path)]
    assert kredite_ids == ["alt-a", "alt-b", "vorlage-c", "weg-d"]
    assert next(k["payment_cents"] for k in lade_kredite(tmp_path)) == 50_000
    assert sorted(objekte.vorhandene(tmp_path)) == ["haus-a", "haus-b", "haus-c"]

    kredite.an_kredit_setzen("alt-b", kredite.ANSCHLUSS, {"zins_pct": 3.0}, tmp_path)
    objekte.felder_setzen("haus-b", {"equity_cents": 1}, tmp_path)
    objekte.prognose_setzen("haus-a", {"miete_monatlich_cents": 1}, tmp_path)
    assert (tmp_path / "loans_custom.yaml").read_bytes() == seite_k
    assert (tmp_path / "properties_custom.yaml").read_bytes() == seite_o
    assert _gelesen(tmp_path, "loans.yaml")["loans"][1]["anschluss_eingegeben"] == {"zins_pct": 3.0}


# ============================================================ N.3d: ziele und balances

ZIELE_PAAR = _paar("goals.yaml")
BESTAENDE_PAAR = _paar("balances.yaml")

ZIELE = {
    "ziele": [
        {"id": "puffer", "name": "Notgroschen", "cents": 1_000_000, "stichtag": None,
         "basis": ["tagesgeld", "giro"], "notiz": "Drei Monate.", "notiz_vom": "2026-03-01"},
        {"id": "alt", "name": "Altes Ziel", "cents": 500_000, "stichtag": date(2030, 1, 1),
         "notiz": "Wird ausgeblendet."},
        {"id": "frei", "name": "Frei", "cents": 200_000}],
    "notizen": {"bereich": {"notiz": "Fuer die Datei der Ziele."}}}
ZIELE_SEITE = {
    "ziele": {
        "puffer": {"cents": 1_200_000, "stichtag": "2027-06-01", "basis": ["giro", "tagesgeld"],
                   "notiz": "Auf der Seite.", "notiz_vom": "2026-09-01"},
        "alt": {"entfernt": True},
        "neu-a": {"cents": 700_000, "basis": ["depot"], "stichtag": "2040-10-01",
                  "notiz": "Nur die Seite."},
        "neu-b": {"name": "Zweites", "cents": 1_000, "entfernt": True}},
    "reihenfolge": ["neu-a", "puffer"]}


def _ziel(neu: dict, kennung: str) -> dict:
    return next(z for z in neu["ziele"] if z["id"] == kennung)


# ---------------------------------------------------------------------- ziele


def test_the_page_wins_per_goal_field_and_a_goal_only_the_page_had_joins_the_list():
    neu, gelegt = _legen(ZIELE_PAAR, ZIELE, ZIELE_SEITE)
    assert [z["id"] for z in neu["ziele"]] == ["puffer", "frei", "neu-a"]
    puffer = _ziel(neu, "puffer")
    assert (puffer["cents"], puffer["stichtag"], puffer["basis"], puffer["name"]) == (
        1_200_000, "2027-06-01", ["giro", "tagesgeld"], "Notgroschen")
    assert _ziel(neu, "frei") == ZIELE["ziele"][2]            # die Seite sagte dazu nichts
    assert gelegt.aus_seite[0] == "neu-a (Ziel, in der Seite angelegt)"


def test_a_goal_only_the_page_had_and_without_a_name_gets_its_id_as_the_name_up_front():
    neu, _ = _legen(ZIELE_PAAR, ZIELE, ZIELE_SEITE)
    neu_a = _ziel(neu, "neu-a")
    assert list(neu_a)[:3] == ["id", "name", "cents"]
    assert neu_a["name"] == "neu-a"
    # Mit einem Namen auf der Seite bleibt es der Name der Seite.
    benannt, _ = _legen(ZIELE_PAAR, ZIELE, {"ziele": {"neu-c": {"name": "Zeitkapsel",
                                                               "cents": 5}}})
    assert _ziel(benannt, "neu-c")["name"] == "Zeitkapsel"


def test_the_merged_goals_file_reads_like_both_files_did():
    neu, gelegt = _legen(ZIELE_PAAR, ZIELE, ZIELE_SEITE)
    assert not gelegt.fehler
    assert paare._ziele_alt(ZIELE, ZIELE_SEITE) == paare._ziele_neu(neu)


def test_a_goal_value_the_page_replaced_stays_in_the_note_and_the_notes_meet_base_first():
    neu, gelegt = _legen(ZIELE_PAAR, ZIELE, ZIELE_SEITE)
    puffer = _ziel(neu, "puffer")
    assert puffer["notiz"].startswith("Drei Monate.\n\nAuf der Seite.")
    assert "Bis zur Umstellung stand in der Datei: `cents`: 1000000; `basis`: [tagesgeld, giro]." \
        in puffer["notiz"]
    assert puffer["notiz_vom"] == "2026-09-01"              # das spaetere der beiden Daten
    assert [o for o, _ in gelegt.ueberschrieben] == ["puffer.cents", "puffer.basis"]
    assert gelegt.notizen == ["puffer"]


def test_the_order_dragged_on_the_page_becomes_a_key_and_holds_for_goals_it_does_not_name():
    from finctl.forecast import ziele as zl

    neu, _ = _legen(ZIELE_PAAR, ZIELE, ZIELE_SEITE)
    assert neu["reihenfolge"] == ["neu-a", "puffer"]
    bestand = {"balances": [{"kind": "giro", "cents": 100}], "obligations": []}
    heute = date(2026, 10, 1)
    jetzt = [p.goal_id for p in zl.progress(zl.aus_spec(neu), bestand, today=heute)]
    damals = [p.goal_id for p in zl.progress(paare.ziele_alt_gelesen(ZIELE, ZIELE_SEITE),
                                             bestand, today=heute)]
    # Das dritte Ziel steht nicht in der Anordnung und folgt dahinter, wie vorher.
    assert jetzt == damals == ["neu-a", "puffer", "frei"]


def test_an_order_the_page_dragged_replaces_the_one_in_the_file_and_the_old_one_stays_in_a_note():
    basis = {"ziele": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
             "reihenfolge": ["a", "b"]}
    neu, gelegt = _legen(ZIELE_PAAR, basis, {"reihenfolge": ["b", "a"]})
    assert neu["reihenfolge"] == ["b", "a"]
    assert ("reihenfolge", "[a, b]") in gelegt.ueberschrieben
    assert "`reihenfolge`: [a, b]" in neu["notizen"]["bereich"]["notiz"]
    # Ohne Anordnung der Seite bleibt die der Datei.
    gleich, _ = _legen(ZIELE_PAAR, basis, {"ziele": {"a": {"cents": 1}}})
    assert gleich["reihenfolge"] == ["a", "b"]


def test_a_hidden_goal_is_gone_and_its_note_stays_with_the_area():
    neu, gelegt = _legen(ZIELE_PAAR, ZIELE, ZIELE_SEITE)
    assert "alt" not in [z["id"] for z in neu["ziele"]]
    assert gelegt.ausgeblendet == ["alt", "neu-b"]
    bereich = neu["notizen"]["bereich"]["notiz"]
    assert bereich.startswith("Fuer die Datei der Ziele.")
    assert "Ausgeblendet bis zur Umstellung: `alt` (Altes Ziel). Wird ausgeblendet." in bereich


def test_an_emergency_fund_without_an_amount_keeps_its_default_a_reading_and_not_a_value(
        monkeypatch):
    from finctl import assumptions as ann
    from finctl.forecast import ziele as zl

    monkeypatch.setattr(ann, "salary_floor_cents", lambda *a, **k: 250_000)
    basis = {"ziele": [{"id": zl.PUFFER_ZIEL, "name": "Notgroschen"}]}
    neu, _ = _legen(ZIELE_PAAR, basis, {"ziele": {zl.PUFFER_ZIEL: {"stichtag": "2027-06-01"}}})
    assert "cents" not in _ziel(neu, zl.PUFFER_ZIEL)
    assert zl.puffer_cents(zl.aus_spec(neu)) == 3 * 250_000


def test_a_goal_with_the_same_day_as_text_and_as_date_is_no_replacement():
    basis = {"ziele": [{"id": "a", "name": "A", "stichtag": date(2030, 1, 1)}]}
    _, gelegt = _legen(ZIELE_PAAR, basis, {"ziele": {"a": {"stichtag": "2030-01-01"}}})
    assert gelegt.ueberschrieben == []


def test_a_page_key_no_reader_knew_is_reported():
    _, gelegt = _legen(ZIELE_PAAR, ZIELE, {"ziele": {}, "erfunden": {"x": 1}})
    assert any("erfunden" in u for u in gelegt.ungelesen)


def test_a_missing_goals_file_is_the_template_the_app_would_have_copied(tmp_path):
    from finctl.forecast import ziele as zl

    config = _config(tmp_path, **{"ziele_custom.yaml": {"ziele": {"neu": {"name": "N",
                                                                         "cents": 1}}}})
    plan, _, _ = umstellen.ausfuehren(config.parent, heute=HEUTE)
    assert not plan.fehler, plan.fehler
    ids = [z["id"] for z in _gelesen(config, "goals.yaml")["ziele"]]
    assert ids == [zl.PUFFER_ZIEL, "neu"]


# -------------------------------------------------------------------- balances


def _konten(tmp_path: Path, *auszug: str) -> Path:
    return _config(tmp_path, **{"accounts.yaml": {"accounts": [
        {"id": k, "ingest_mode": "parsed"} for k in auszug] + [
        {"id": "depot-a", "ingest_mode": "summary"}]}})


BESTAENDE = {
    "as_of": date(2026, 9, 11),
    "balances": [
        {"account_id": "giro-a", "kind": "giro", "notiz": "Betriebskonto."},
        {"account_id": "depot-a", "name": "Depot A", "cents": 1_000_000,
         "as_of": date(2026, 9, 11), "kind": "depot", "notiz": "Alles im ETF.",
         "notiz_vom": "2026-02-01"},
        {"account_id": "krypto-b", "name": "Krypto B", "cents": None,
         "as_of": date(2026, 9, 11), "kind": "krypto"},
        {"account_id": "police-c", "name": "Police C", "cents": 3_000_000,
         "as_of": date(2026, 4, 1), "kind": "rentenversicherung", "notiz": "Aus der Mitteilung."},
        {"name": "Ohne Konto", "cents": 100, "kind": "depot"}],
    "obligations": [
        {"name": "Treuhand A", "cents": 300_000, "notiz": "Gehoert jemand anderem."},
        {"name": "Treuhand B", "cents": 50_000},
        {"name": "Treuhand C", "cents": 20_000, "notiz": "Wird getilgt."}],
    "notizen": {"bereich": {"notiz": "Fuer die Bestaende."}}}
BESTAENDE_SEITE = {
    "overrides": {
        "depot-a": {"cents": 1_100_000, "as_of": "2026-10-01", "gewinn_cents": 100_000,
                    "notiz": "Im Oktober getippt."},
        "krypto-b": {"cents": 200_000, "as_of": "2026-09-11"},
        "police-c": {"rueckkauf_cents": 2_900_000, "rueckkauf_as_of": "2026-04-01",
                     "eingezahlt_cents": 2_800_000},
        "giro-a": {"cents": 999, "as_of": "2026-10-01", "notiz": "Hier stand ein Betrag."},
        "erfunden": {"cents": 1, "notiz": "Zu keiner Position."},
        "Ohne Konto": {"cents": 150}},
    "verpflichtungen": {
        "treuhand-a": {"cents": 250_000, "notiz": "Zurueckgezahlt, Rest offen."},
        "treuhand-c": {"geloescht": True},
        "neu-d": {"name": "Neu D", "cents": 10_000, "notiz": "Nur die Seite."}},
    "verlauf": {"depot-a": {"2026-09": {"cents": 1_000_000, "as_of": "2026-09-11"}}}}


def _legen_b(basis: dict, seite: dict, tmp_path: Path | None = None, *auszug: str):
    """Die Bestaende zusammenlegen; `auszug` sind die Konten mit einem Auszug."""
    config = _konten(tmp_path or Path("/nonexistent-ordner"), *auszug) if tmp_path else None
    gelegt = paare.zusammenlegen(BESTAENDE_PAAR, basis, seite, config=config)
    assert not gelegt.fehler, gelegt.fehler
    return yaml.safe_load(gelegt.neu), gelegt


def _position(neu: dict, kennung: str) -> dict:
    return next(b for b in neu["balances"] if (b.get("account_id") or b["name"]) == kennung)


def test_the_page_wins_per_position_field_except_for_an_account_with_a_statement(tmp_path):
    neu, _ = _legen_b(BESTAENDE, BESTAENDE_SEITE, tmp_path, "giro-a")
    depot = _position(neu, "depot-a")
    assert (depot["cents"], str(depot["as_of"]), depot["gewinn_cents"]) == (
        1_100_000, "2026-10-01", 100_000)
    assert _position(neu, "krypto-b")["cents"] == 200_000
    police = _position(neu, "police-c")
    assert (police["rueckkauf_cents"], police["eingezahlt_cents"]) == (2_900_000, 2_800_000)
    assert _position(neu, "Ohne Konto")["cents"] == 150           # Schluessel ist der Name
    giro = _position(neu, "giro-a")
    assert "cents" not in giro and "as_of" not in giro


def test_a_value_the_page_carried_for_an_account_with_a_statement_stays_in_the_note(tmp_path):
    neu, gelegt = _legen_b(BESTAENDE, BESTAENDE_SEITE, tmp_path, "giro-a")
    giro = _position(neu, "giro-a")
    assert giro["notiz"].startswith("Betriebskonto.\n\nHier stand ein Betrag.")
    assert f"{paare.AUSZUG_STAND}: `cents`: 999; `as_of`: 2026-10-01." in giro["notiz"]
    assert "overrides.giro-a.cents (Konto mit Auszug: galt nicht)" in gelegt.ungelesen
    # Was der Auszug nicht kennt, gilt wie vorher: ohne die Konten weiss die Datei nichts davon.
    ohne, _ = _legen_b(BESTAENDE, BESTAENDE_SEITE)
    assert _position(ohne, "giro-a")["cents"] == 999


def test_the_number_of_an_account_with_a_statement_stays_the_statement_whatever_the_page_carried(
        tmp_path):
    from finctl import bestaende as best
    from finctl.ledger.db import connect, init_db

    c = connect(init_db(tmp_path / "t.db"))
    try:
        c.execute("INSERT INTO accounts (id, display_name, institution, account_type, "
                  "ingest_mode, parser_profile) VALUES ('giro-a', 'G', 'X', 'giro', 'parsed', 'p')")
        c.execute("INSERT INTO statements (account_id, source_path, source_name, file_sha256, "
                  "period_start, period_end, balance_start_cents, balance_end_cents, "
                  "parser_profile, parser_version, status, imported_at) "
                  "VALUES ('giro-a', 'x', 'x', 's', '2026-08-01', '2026-08-31', 0, 400000, "
                  "'p', '1', 'imported', 'now')")
        c.commit()
        nur_basis = best.zusammenfuehren(c, BESTAENDE)
        neu, _ = _legen_b(BESTAENDE, BESTAENDE_SEITE, tmp_path, "giro-a")
        zusammen = best.zusammenfuehren(c, neu)
    finally:
        c.close()
    vorher = next(b for b in nur_basis["balances"] if b["account_id"] == "giro-a")
    nachher = next(b for b in zusammen["balances"] if b["account_id"] == "giro-a")
    assert (vorher["cents"], vorher["as_of"]) == (nachher["cents"], nachher["as_of"]) == (
        400_000, "2026-08-31")
    assert nachher["aus_auszug"]


def test_the_merged_balances_file_reads_like_both_files_did(tmp_path):
    neu, gelegt = _legen_b(BESTAENDE, BESTAENDE_SEITE, tmp_path, "giro-a")
    assert not gelegt.fehler
    kontext = paare._konto_modi(tmp_path / "Daten" / "config")
    assert kontext == {"giro-a"}
    assert paare._balances_alt(BESTAENDE, BESTAENDE_SEITE, kontext) == paare._balances_neu(neu)


def test_a_base_value_the_page_replaced_stays_in_the_note_and_the_notes_meet_base_first(tmp_path):
    neu, gelegt = _legen_b(BESTAENDE, BESTAENDE_SEITE, tmp_path, "giro-a")
    depot = _position(neu, "depot-a")
    assert depot["notiz"].startswith("Alles im ETF.\n\nIm Oktober getippt.")
    assert ("Bis zur Umstellung stand in der Datei: `cents`: 1000000; `as_of`: 2026-09-11."
            in depot["notiz"])
    # Ein Wert der Basis, den es nicht gab (`cents: null`), und derselbe Tag zaehlen nicht.
    assert "Bis zur Umstellung" not in (_position(neu, "krypto-b").get("notiz") or "")
    orte = [o for o, _ in gelegt.ueberschrieben]
    assert orte == ["depot-a.cents", "depot-a.as_of", "Ohne Konto.cents",
                    "verpflichtung treuhand-a.cents"]
    assert "depot-a" in gelegt.notizen and "treuhand-a" in gelegt.notizen


def test_a_position_the_page_had_and_the_file_lacks_goes_to_the_note_of_the_area(tmp_path):
    neu, gelegt = _legen_b(BESTAENDE, BESTAENDE_SEITE, tmp_path, "giro-a")
    assert "overrides.erfunden (keine Position dazu)" in gelegt.ungelesen
    assert "Zu `overrides.erfunden` (keine Position dazu): Zu keiner Position." in \
        neu["notizen"]["bereich"]["notiz"]


def test_a_liability_keeps_the_page_amount_a_struck_one_is_gone_and_a_new_one_joins(tmp_path):
    neu, gelegt = _legen_b(BESTAENDE, BESTAENDE_SEITE, tmp_path, "giro-a")
    namen = [o["name"] for o in neu["obligations"]]
    assert namen == ["Treuhand A", "Treuhand B", "Neu D"]
    a = neu["obligations"][0]
    assert a["cents"] == 250_000
    assert a["notiz"].startswith("Gehoert jemand anderem.\n\nZurueckgezahlt, Rest offen.")
    assert "`cents`: 300000" in a["notiz"]
    assert gelegt.ausgeblendet == ["treuhand-c"]
    assert "Ausgeblendet bis zur Umstellung: Verpflichtung `treuhand-c`. Wird getilgt." in \
        neu["notizen"]["bereich"]["notiz"]
    assert neu["obligations"][2] == {"name": "Neu D", "cents": 10_000, "notiz": "Nur die Seite."}


def test_renaming_a_liability_on_the_page_changes_its_key_and_the_check_follows(tmp_path):
    seite = {"verpflichtungen": {"treuhand-b": {"name": "Treuhand Zwei", "notiz": "Umbenannt."}}}
    neu, gelegt = _legen_b(BESTAENDE, seite, tmp_path)
    assert gelegt.umbenannt == {"treuhand-b": "treuhand-zwei"}
    assert [o["name"] for o in neu["obligations"]][1] == "Treuhand Zwei"
    # Zwei, die danach gleich heissen, sind ein Fehler.
    doppelt = paare.zusammenlegen(BESTAENDE_PAAR, BESTAENDE, {"verpflichtungen": {
        "treuhand-b": {"name": "Treuhand A"}}})
    assert any("gleich" in f for f in doppelt.fehler)


def test_the_verlauf_the_page_wrote_becomes_a_key_of_the_file_and_a_base_one_is_reported(tmp_path):
    neu, _ = _legen_b(BESTAENDE, BESTAENDE_SEITE, tmp_path, "giro-a")
    assert neu["verlauf"] == {"depot-a": {"2026-09": {"cents": 1_000_000,
                                                      "as_of": "2026-09-11"}}}
    assert list(neu)[-2:] == ["verlauf", "notizen"]
    from finctl import bestaende as best

    assert best.verlauf(neu) == neu["verlauf"]
    mit_basis, bericht = _legen_b({**BESTAENDE, "verlauf": {"x": {}}}, {})
    assert "verlauf" not in mit_basis
    assert any("verlauf (der Basis" in u for u in bericht.ungelesen)


def test_the_two_notes_of_the_area_meet_base_first_and_the_page_key_nobody_read_is_reported(
        tmp_path):
    seite = {**BESTAENDE_SEITE, "notizen": {"bereich": {"notiz": "Aus der Seite."}},
             "erfunden": 1}
    neu, gelegt = _legen_b(BESTAENDE, seite, tmp_path, "giro-a")
    assert neu["notizen"]["bereich"]["notiz"].startswith("Fuer die Bestaende.\n\nAus der Seite.")
    assert any("erfunden (Schlüssel" in u for u in gelegt.ungelesen)


def test_the_init_mirror_takes_every_stand_under_its_own_date(tmp_path):
    """Jede Position mit Betrag steht unter ihrem eigenen Datum, sonst unter dem der Datei
    (Schritt 5b, E.7). Was aus der Datei verschwand, verschwindet auch aus der Tabelle."""
    from finctl import cli
    from finctl.ledger.db import connect, init_db

    neu, _ = _legen_b(BESTAENDE, BESTAENDE_SEITE, tmp_path, "giro-a")
    neu["balances"][2]["cents"] = 200_000
    neu["balances"].append({"account_id": "ohne-datum", "cents": 7})
    c = connect(init_db(tmp_path / "t.db"))
    try:
        for kennung in ("depot-a", "krypto-b", "police-c", "ohne-datum"):
            c.execute("INSERT INTO accounts (id, display_name, institution, account_type, "
                      "ingest_mode) VALUES (?, ?, 'X', 'depot', 'summary')", (kennung, kennung))
        c.execute("INSERT INTO balance_snapshots (account_id, as_of, balance_cents, source) "
                  "VALUES ('depot-a', '2026-09-11', 1, 'manual')")
        cli._bestaende_spiegeln(c, neu)
        zeilen = {(r[0], r[1]): r[2] for r in c.execute(
            "SELECT account_id, as_of, balance_cents FROM balance_snapshots")}
    finally:
        c.close()
    # `depot-a` und `police-c` tragen ein anderes Datum und stehen darunter; die alte Zeile,
    # die die Datei nicht mehr nennt, ist weg.
    assert zeilen == {("depot-a", "2026-10-01"): 1_100_000, ("krypto-b", "2026-09-11"): 200_000,
                      ("police-c", "2026-04-01"): 3_000_000, ("ohne-datum", "2026-09-11"): 7}


# ------------------------------------------------------------- der Lauf, ziele und balances


def _beide_neu(tmp_path: Path) -> Path:
    config = _config(tmp_path, **{
        "goals.yaml": ZIELE, "ziele_custom.yaml": ZIELE_SEITE,
        "balances.yaml": BESTAENDE, "balances_custom.yaml": BESTAENDE_SEITE,
        "accounts.yaml": {"accounts": [{"id": "giro-a", "ingest_mode": "parsed"}]}})
    return config.parent


def test_the_run_merges_goals_and_balances_and_a_second_run_does_nothing(tmp_path):
    wurzel = _beide_neu(tmp_path)
    seiten = ("ziele_custom.yaml", "balances_custom.yaml")
    vorher = {n: (wurzel / "config" / n).read_bytes() for n in seiten}
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)

    assert not plan.fehler, plan.fehler
    assert sorted(p.name for p in (wurzel / "config").iterdir()) == [
        "accounts.yaml", "balances.yaml", "goals.yaml"]
    assert {n: (sicherung / "config" / n).read_bytes() for n in vorher} == vorher
    text = bericht.read_text(encoding="utf-8")
    assert "Zusammengelegt: `ziele_custom.yaml` in `goals.yaml`" in text
    assert "Zusammengelegt: `balances_custom.yaml` in `balances.yaml`" in text
    assert "`puffer.cents`: 1000000" in text and "`depot-a.cents`: 1000000" in text
    # Das Konto mit Auszug kommt aus accounts.yaml: Der Wert der Seite steht nur in der Notiz.
    giro = _gelesen(wurzel / "config", "balances.yaml")["balances"][0]
    assert "cents" not in giro and "`cents`: 999" in giro["notiz"]

    summe = _pruefsumme(wurzel)
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert not plan.zu_tun and sicherung is None and bericht is None
    assert _pruefsumme(wurzel) == summe


def test_the_app_stops_while_a_goals_or_balances_page_file_is_still_there(tmp_path):
    config = _config(tmp_path, **{"goals.yaml": ZIELE, "ziele_custom.yaml": ZIELE_SEITE})
    assert umstellen.planen(config).offen
    with pytest.raises(umstellen.AlteFormError, match=r"ziele_custom\.yaml"):
        umstellen.halt_wenn_offen(config)
    config = _config(tmp_path / "zwei", **{"balances.yaml": BESTAENDE,
                                           "balances_custom.yaml": BESTAENDE_SEITE})
    with pytest.raises(umstellen.AlteFormError, match=r"balances_custom\.yaml"):
        umstellen.halt_wenn_offen(config)


@pytest.mark.parametrize("name", ["goals", "balances"])
def test_a_data_folder_with_only_the_page_file_gets_it_as_the_base_file_here_too(tmp_path, name):
    seite = {"goals": {"ziele": {"n": {"name": "N", "cents": 5, "notiz": "Nur die Seite."}}},
             "balances": {"overrides": {"depot-a": {"cents": 1}},
                          "verpflichtungen": {"neu": {"name": "Neu", "cents": 3}}}}[name]
    ziel = "ziele_custom.yaml" if name == "goals" else "balances_custom.yaml"
    config = _config(tmp_path, **{ziel: seite})
    plan, _, _ = umstellen.ausfuehren(config.parent, heute=HEUTE)
    assert not plan.fehler, plan.fehler
    assert sorted(p.name for p in config.iterdir()) == [f"{name}.yaml"]
    assert not umstellen.planen(config).offen
    if name == "goals":
        assert [z["id"] for z in _gelesen(config, "goals.yaml")["ziele"]][-1] == "n"
    else:
        assert _gelesen(config, "balances.yaml")["obligations"][-1]["name"] == "Neu"


@pytest.mark.parametrize("name", ["goals", "balances"])
def test_only_the_base_file_of_goals_or_balances_has_nothing_to_do(tmp_path, name):
    config = _config(tmp_path, **{f"{name}.yaml": {"goals": ZIELE, "balances": BESTAENDE}[name]})
    assert not umstellen.planen(config).offen


def test_comments_of_a_goals_pair_become_notes_before_the_two_are_merged(tmp_path):
    config = _config(tmp_path, **{
        "goals.yaml": "# Kopf der Ziele.\nziele:\n  - id: a\n    # Warum.\n    cents: 100\n",
        "ziele_custom.yaml": "ziele:\n  a:\n    # Aus der Seite.\n    cents: 200\n"})
    umstellen.ausfuehren(config.parent, heute=HEUTE)
    [a] = _gelesen(config, "goals.yaml")["ziele"]
    assert a["notiz"].startswith("Warum.\n\nAus der Seite.") and a["cents"] == 200


def test_the_odd_head_of_the_goals_page_file_goes_into_the_note_of_the_area(tmp_path):
    """`ziele_custom.yaml` trug eine aeltere Fassung des Kopfs der App: Sie weicht in einer
    Zahl ab, faellt deshalb nicht weg, und steht danach in der Notiz des Bereichs."""
    from finctl.umstellen_form import KOEPFE

    kopf = KOEPFE["ziele_custom.yaml"][0].replace("1.100.000", "1.092.608")
    config = _config(tmp_path, **{
        "goals.yaml": {"ziele": [{"id": "a", "name": "A"}]},
        "ziele_custom.yaml": kopf + "\n\nziele:\n  a:\n    cents: 5\n"})
    umstellen.ausfuehren(config.parent, heute=HEUTE)
    bereich = _gelesen(config, "goals.yaml")["notizen"]["bereich"]["notiz"]
    assert "Im Dashboard bearbeitete Ziele." in bereich and "1.092.608" in bereich


def test_the_goals_and_balances_readers_and_writers_know_only_the_one_file(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from finctl import bestaende
    from finctl.forecast import ziele as zl
    from finctl.web.routen import konten as konten_seite
    from finctl.web.routen import ziele as ziele_seite
    from finctl.web.server import app

    for modul in (bestaende, konten_seite, ziele_seite):
        monkeypatch.setattr(modul, "CONFIG_DIR", tmp_path)
    for name, inhalt in (("goals.yaml", ZIELE), ("ziele_custom.yaml", ZIELE_SEITE),
                         ("balances.yaml", BESTAENDE), ("balances_custom.yaml", BESTAENDE_SEITE)):
        (tmp_path / name).write_text(yaml_text(inhalt), encoding="utf-8")
    seiten = {n: (tmp_path / n).read_bytes() for n in ("ziele_custom.yaml",
                                                      "balances_custom.yaml")}
    # Gelesen wird allein die eine Datei: der Betrag der Basis, nicht der der Seite.
    assert next(g for g in zl.aus_spec(bestaende.lesen(tmp_path / "goals.yaml"))["ziele"]
                if g["id"] == "puffer")["cents"] == 1_000_000
    assert bestaende.position(bestaende.lesen(tmp_path / "balances.yaml"), "depot-a")[
        "cents"] == 1_000_000

    client = TestClient(app)
    assert client.post("/api/ziel", json={"id": "frei", "cents": 7}).json()["ok"]
    assert client.post("/api/bestand", json={"key": "depot-a", "cents": 5,
                                             "as_of": "2026-10-02"}).json()["ok"]
    assert client.post("/api/verpflichtung", json={"name": "Treuhand B", "cents": 9}).json()["ok"]
    assert client.post("/api/ziele/reihenfolge", json={"ids": ["frei", "puffer"]}).json()["ok"]
    assert {n: (tmp_path / n).read_bytes() for n in seiten} == seiten
    assert _gelesen(tmp_path, "goals.yaml")["reihenfolge"] == ["frei", "puffer"]
    assert _gelesen(tmp_path, "balances.yaml")["obligations"][1]["cents"] == 9


def test_saving_a_migrated_goal_without_a_name_and_a_migrated_position_changes_no_byte(
        tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from finctl.web.routen import konten as konten_seite
    from finctl.web.routen import ziele as ziele_seite
    from finctl.web.server import app

    for modul in (konten_seite, ziele_seite):
        monkeypatch.setattr(modul, "CONFIG_DIR", tmp_path)
    ziele, _ = _legen(ZIELE_PAAR, ZIELE, ZIELE_SEITE)
    (tmp_path / "goals.yaml").write_text(yaml_text(ziele), encoding="utf-8")
    bestaende, _ = _legen_b(BESTAENDE, BESTAENDE_SEITE, tmp_path, "giro-a")
    (tmp_path / "balances.yaml").write_text(yaml_text(bestaende), encoding="utf-8")
    client = TestClient(app)
    for kennung in ("neu-a", "puffer", "frei"):
        g = _ziel(ziele, kennung)
        vorher = (tmp_path / "goals.yaml").read_bytes()
        assert client.post("/api/ziel", json={
            "id": kennung, "name": g["name"], "cents": g["cents"],
            "stichtag": str(g.get("stichtag") or ""), "basis": g.get("basis", []),
            "notiz": g.get("notiz", "")}).json()["ok"]
        assert (tmp_path / "goals.yaml").read_bytes() == vorher, kennung
    depot = _position(bestaende, "depot-a")
    vorher = (tmp_path / "balances.yaml").read_bytes()
    assert client.post("/api/bestand", json={
        "key": "depot-a", "cents": depot["cents"], "as_of": str(depot["as_of"]),
        "gewinn_cents": depot["gewinn_cents"], "note": depot["notiz"]}).json()["ok"]
    assert (tmp_path / "balances.yaml").read_bytes() == vorher


def test_a_goals_or_balances_merge_that_loses_something_is_a_failed_check_too():
    def ohne_reihenfolge(basis, seite, bericht):
        gelegt = paare._ziele_legen(basis, seite, bericht)
        gelegt.pop("reihenfolge", None)
        return gelegt

    def ohne_gewinn(basis, seite, bericht, kontext=None):
        gelegt = paare._balances_legen(basis, seite, bericht, kontext)
        _position(gelegt, "depot-a").pop("gewinn_cents")
        return gelegt

    for paar, legen, basis, seite in (
            (ZIELE_PAAR, ohne_reihenfolge, ZIELE, ZIELE_SEITE),
            (BESTAENDE_PAAR, ohne_gewinn, BESTAENDE, BESTAENDE_SEITE)):
        kaputt = paare.Paar(paar.basis, paar.seite, legen, paar.alt, paar.neu,
                            wurzeln=paar.wurzeln, seitenwurzel=paar.seitenwurzel,
                            kontext=paar.kontext, kennung_von=paar.kennung_von)
        gelegt = paare.zusammenlegen(kaputt, basis, seite)
        assert any("liest sich nicht" in f for f in gelegt.fehler), paar.basis
        assert gelegt.neu is None


# ==================================================================== N.3e
#
# rules, accounts, lebensplan und backup. Keine dieser Seitendateien gibt es in der
# Entwicklungskopie; geprueft wird an erfundenen Ordnern, die in allen Teilen Eintraege haben:
# ueberschriebene Werte, Eintraege nur in der Seite, ausgeblendete, Notizen und Kommentare in
# beiden Dateien.

REGELN_PAAR = next(p for p in paare.PAARE if p.basis == "rules.yaml")
KONTEN_PAAR = next(p for p in paare.PAARE if p.basis == "accounts.yaml")
LEBEN_PAAR = next(p for p in paare.PAARE if p.basis == "lebensplan.yaml")
SICHERUNG_PAAR = next(p for p in paare.PAARE if p.basis == "backup.yaml")

REGELN = {
    "allgemeine_regeln": True,
    "rules": [
        {"id": "alpha", "name": "Alpha", "priority": 10,
         "match": {"text": ["Alpha"], "sign": "-"},
         "set": {"mgmt": "konsum/a", "note": "Text an der Buchung"},
         "notiz": "Warum alpha.", "notiz_vom": "2026-02-01"},
        {"id": "beta", "name": "Beta", "priority": 20, "match": {"text": ["Beta"]},
         "set": {"mgmt": "konsum/b"}, "notiz": "Warum beta."},
        # Eine eigene Regel mit der Kennung einer mitgelieferten verdeckt diese.
        {"id": "allg-finanzamt", "name": "Eigenes Finanzamt", "priority": 5,
         "match": {"text": ["Fiskus"]}, "set": {"mgmt": "steuern/einkommensteuer"}},
    ],
    "notizen": {"bereich": {"notiz": "Regeln des Haushalts."}},
}
REGELN_SEITE = {
    "regeln": {
        # `match` ersetzt die Seite als Ganzes, den Namen und alles andere Feld fuer Feld.
        "alpha": {"match": {"text": ["Alpha", "Alfa"]}, "notiz": "Von der Seite."},
        "beta": {"entfernt": True, "notiz": "Beta war falsch."},
        "delta": {"name": "Delta", "priority": 40, "match": {"text": ["Delta"]},
                  "set": {"mgmt": "konsum/d"}, "notiz": "Nur auf der Seite."},
        "allg-supermarkt": {"name": "Meine Laeden", "set": {"mgmt": "konsum/laeden"}},
        "allg-gehalt": {"entfernt": True, "notiz": "Zahlt anders."},
        "allg-finanzamt": {"entfernt": True},
    },
    "notizen": {"bereich": {"notiz": "Von der Seite, fuer alle."}},
}


def _regel_ids(spec: dict) -> list[str]:
    return [r["id"] for r in spec["rules"]]


def test_rules_the_page_replaces_match_and_set_whole_and_every_other_field_alone():
    neu, _ = _legen(REGELN_PAAR, REGELN, REGELN_SEITE)
    alpha = next(r for r in neu["rules"] if r["id"] == "alpha")
    assert alpha["match"] == {"text": ["Alpha", "Alfa"]}           # `sign` ist weg: als Ganzes
    assert alpha["set"] == REGELN["rules"][0]["set"]               # die Seite sagte nichts dazu
    assert (alpha["name"], alpha["priority"]) == ("Alpha", 10)
    # Die Regel nur der Seite steht hinter denen der Basis, in der Reihenfolge der Datei.
    delta = next(r for r in neu["rules"] if r["id"] == "delta")
    assert list(delta) == ["id", "name", "priority", "match", "set", "notiz"]
    assert _regel_ids(neu)[:2] == ["alpha", "delta"]


def test_rules_the_merged_file_reads_like_both_files_did():
    for an in (True, False):
        basis = {**REGELN, "allgemeine_regeln": an}
        neu, _ = _legen(REGELN_PAAR, basis, REGELN_SEITE)
        assert REGELN_PAAR.alt(basis, REGELN_SEITE) == REGELN_PAAR.neu(neu), an


def test_rules_a_hidden_rule_is_gone_and_its_note_stays_with_the_area():
    neu, gelegt = _legen(REGELN_PAAR, REGELN, REGELN_SEITE)
    assert "beta" not in _regel_ids(neu)
    bereich = neu["notizen"]["bereich"]["notiz"]
    assert "Regeln des Haushalts." in bereich and "Von der Seite, fuer alle." in bereich
    assert "Ausgeblendet bis zur Umstellung: `beta` (Beta). Warum beta." in bereich
    assert "Beta war falsch." in bereich
    assert "beta" in gelegt.ausgeblendet


def test_rules_a_general_rule_the_page_changed_stands_whole_and_holds_instead_of_the_shipped_one():
    from finctl.rules import engine

    neu, gelegt = _legen(REGELN_PAAR, REGELN, REGELN_SEITE)
    [regel] = [r for r in neu["rules"] if r["id"] == "allg-supermarkt"]
    mitgeliefert = next(r for r in engine.grundschicht() if r["id"] == "allg-supermarkt")
    assert regel["name"] == "Meine Laeden" and regel["set"] == {"mgmt": "konsum/laeden"}
    # Was die Seite nicht nannte, kommt aus der mitgelieferten Regel, auch die Prioritaet, die galt.
    assert regel["match"] == mitgeliefert["match"] and regel["priority"] == mitgeliefert["priority"]
    assert regel["provenance"] == "allgemein"
    assert "Bis zur Umstellung stand in den mitgelieferten Regeln: `name`: Supermarkt" in regel[
        "notiz"]
    gilt = [r for r in engine.rohe_aus_spec(neu) if r["id"] == "allg-supermarkt"]
    assert [(r["name"], r["herkunft"]) for r in gilt] == [("Meine Laeden", "basis")]
    assert ("allg-supermarkt.set", "{mgmt: lebensmittel/supermarkt}") in gelegt.ueberschrieben


def test_rules_a_general_rule_the_page_hid_stays_hidden_even_behind_an_own_rule_with_its_id():
    from finctl.rules import engine

    neu, _ = _legen(REGELN_PAAR, REGELN, REGELN_SEITE)
    assert neu["allgemeine_regeln_aus"] == ["allg-finanzamt", "allg-gehalt"]
    ids = {r["id"] for r in engine.rohe_aus_spec(neu)}
    # Die eigene Regel "allg-finanzamt" fiel weg, die mitgelieferte kommt nicht zurueck.
    assert not ids & {"allg-finanzamt", "allg-gehalt", "beta"}
    # Und die Schluessel stehen hinter `allgemeine_regeln`, vor den Regeln.
    assert list(neu)[:3] == ["allgemeine_regeln", "allgemeine_regeln_aus", "rules"]


def test_rules_a_hidden_general_rule_stays_hidden_when_the_layer_is_switched_on_later():
    from finctl.rules import engine

    basis = {**REGELN, "allgemeine_regeln": False}
    neu, _ = _legen(REGELN_PAAR, basis, REGELN_SEITE)
    assert "allg-gehalt" in neu["allgemeine_regeln_aus"]
    an = engine.rohe_aus_spec({**neu, "allgemeine_regeln": True})
    assert "allg-gehalt" not in {r["id"] for r in an}


def test_rules_two_notes_become_one_with_the_base_first_and_the_old_value_at_the_end():
    neu, _ = _legen(REGELN_PAAR, REGELN, REGELN_SEITE)
    alpha = next(r for r in neu["rules"] if r["id"] == "alpha")
    assert alpha["notiz"] == ("Warum alpha.\n\nVon der Seite.\n\nBis zur Umstellung stand in der "
                              "Datei: `match`: {sign: '-', text: [Alpha]}.")
    assert alpha["notiz_vom"] == "2026-02-01"          # das spaetere; die Seite hatte keins


def test_rules_a_page_field_the_old_reader_never_read_is_reported():
    _, gelegt = _legen(REGELN_PAAR, REGELN, {"regeln": {}, "version": 3})
    assert any("version" in u for u in gelegt.ungelesen)


def test_rules_a_missing_base_is_the_template_the_app_would_have_copied(tmp_path):
    config = _config(tmp_path, **{"rules_custom.yaml": REGELN_SEITE})
    umstellen.ausfuehren(config.parent, heute=HEUTE)
    spec = _gelesen(config, "rules.yaml")
    assert spec["allgemeine_regeln"] is True
    assert "delta" in _regel_ids(spec) and "beta" not in _regel_ids(spec)


def test_rules_the_two_writers_that_change_the_file_as_text_before_write_only_rules_yaml(tmp_path):
    from finctl.rules import engine

    config = _config(tmp_path, **{"rules.yaml": REGELN, "rules_custom.yaml": REGELN_SEITE})
    umstellen.ausfuehren(config.parent, heute=HEUTE)
    pfad = config / "rules.yaml"
    assert engine.repoint_rule("delta", "mgmt", "konsum/e", pfad)
    assert not engine.repoint_rule("gibt-es-nicht", "mgmt", "konsum/e", pfad)
    assert not engine.repoint_rule("delta", "tax", "x/y", pfad)       # kein solches Feld
    engine.grundschicht_setzen(False, pfad)
    spec = _gelesen(config, "rules.yaml")
    assert spec["allgemeine_regeln"] is False
    assert spec["allgemeine_regeln_aus"] == ["allg-finanzamt", "allg-gehalt"]
    assert next(r for r in spec["rules"] if r["id"] == "delta")["set"] == {"mgmt": "konsum/e"}
    assert next(r for r in spec["rules"] if r["id"] == "delta")["notiz"] == "Nur auf der Seite."
    assert sorted(p.name for p in config.iterdir()) == ["rules.yaml"]


# ---------------------------------------------------------------- accounts

KONTEN = {"accounts": [
    {"id": "giro-a", "display_name": "Giro A", "institution": "Bank A", "account_type": "giro",
     "ingest_mode": "parsed", "parser_profile": "profil-a", "notiz": "Betriebskonto.",
     "notiz_vom": "2026-03-01"},
    {"id": "tag-a", "display_name": "Tagesgeld A", "institution": "Bank A",
     "account_type": "tagesgeld", "ingest_mode": "summary", "notiz": "Ruecklage."},
    {"id": "alt-a", "display_name": "Altes Konto", "institution": "Bank C", "account_type": "giro",
     "ingest_mode": "summary", "notiz": "Aufgeloest."},
], "notizen": {"bereich": {"notiz": "Konten des Haushalts."}}}
KONTEN_SEITE = {"accounts": {
    "tag-a": {"display_name": "Tagesgeld A neu", "dispo_threshold_cents": 0,
              "notiz": "Von der Seite."},
    "alt-a": {"entfernt": True, "notiz": "Und gekuendigt."},
    "neu-a": {"statement_folder": "neu-a", "institution": "Bank B", "id": "neu-a",
              "display_name": "Neu A", "account_type": "tagesgeld", "ingest_mode": "summary",
              "notiz": "Nur auf der Seite."},
    "giro-a": {"ingest_mode": "summary"},
}, "notizen": {"bereich": {"notiz": "Seite."}}}


def test_accounts_the_page_replaces_field_by_field_and_an_account_only_it_had_stands_behind():
    neu, _ = _legen(KONTEN_PAAR, KONTEN, KONTEN_SEITE)
    je_id = {k["id"]: k for k in neu["accounts"]}
    assert [k["id"] for k in neu["accounts"]] == ["giro-a", "tag-a", "neu-a"]
    assert (je_id["tag-a"]["display_name"], je_id["tag-a"]["institution"]) == (
        "Tagesgeld A neu", "Bank A")
    assert je_id["tag-a"]["dispo_threshold_cents"] == 0
    assert je_id["giro-a"]["ingest_mode"] == "summary"
    assert je_id["giro-a"]["parser_profile"] == "profil-a"        # was die Seite nicht nannte
    # Die Felder eines Kontos der Seite stehen in der Reihenfolge, in der die App sie schreibt.
    from finctl import konten

    assert [k for k in je_id["neu-a"] if k != "notiz"] == [
        f for f in konten.FELDER if f in je_id["neu-a"]]


def test_accounts_the_merged_file_reads_like_both_files_did():
    neu, _ = _legen(KONTEN_PAAR, KONTEN, KONTEN_SEITE)
    assert KONTEN_PAAR.alt(KONTEN, KONTEN_SEITE) == KONTEN_PAAR.neu(neu)
    assert [k["id"] for k in KONTEN_PAAR.neu(neu)] == ["giro-a", "tag-a", "neu-a"]


def test_accounts_a_hidden_account_is_gone_and_its_note_stays_with_the_area():
    neu, gelegt = _legen(KONTEN_PAAR, KONTEN, KONTEN_SEITE)
    assert "alt-a" not in [k["id"] for k in neu["accounts"]]
    bereich = neu["notizen"]["bereich"]["notiz"]
    assert "Ausgeblendet bis zur Umstellung: `alt-a` (Altes Konto). Aufgeloest." in bereich
    assert "Und gekuendigt." in bereich and "Konten des Haushalts." in bereich
    assert gelegt.ausgeblendet == ["alt-a"]


def test_accounts_two_notes_meet_base_first_and_the_replaced_value_stays_in_the_note():
    neu, gelegt = _legen(KONTEN_PAAR, KONTEN, KONTEN_SEITE)
    je_id = {k["id"]: k for k in neu["accounts"]}
    assert je_id["tag-a"]["notiz"] == (
        "Ruecklage.\n\nVon der Seite.\n\nBis zur Umstellung stand in der Datei: "
        "`display_name`: Tagesgeld A.")
    assert je_id["giro-a"]["notiz"].startswith("Betriebskonto.")
    assert "`ingest_mode`: parsed" in je_id["giro-a"]["notiz"]
    assert je_id["giro-a"]["notiz_vom"] == "2026-03-01"
    assert ("giro-a.ingest_mode", "parsed") in gelegt.ueberschrieben


def test_accounts_a_page_only_account_without_a_base_file_gives_the_base_file(tmp_path):
    config = _config(tmp_path, **{"accounts_custom.yaml": KONTEN_SEITE})
    plan, _, _ = umstellen.ausfuehren(config.parent, heute=HEUTE)
    assert not plan.fehler, plan.fehler
    assert [k["id"] for k in _gelesen(config, "accounts.yaml")["accounts"]] == ["tag-a", "neu-a",
                                                                                "giro-a"]
    assert sorted(p.name for p in config.iterdir()) == ["accounts.yaml"]


def test_accounts_the_account_modes_the_balances_merge_asks_for_survive_the_merge(tmp_path):
    """`Paar.kontext` liest vor und nach dem Lauf dasselbe: wer einen Auszug hat."""
    config = _config(tmp_path, **{
        "accounts.yaml": KONTEN, "accounts_custom.yaml": KONTEN_SEITE,
        "balances.yaml": {"balances": [
            {"account_id": "giro-a", "cents": 1_000_000, "as_of": "2026-09-30"},
            {"account_id": "tag-a", "cents": 2_000_000, "as_of": "2026-09-30"}]},
        "balances_custom.yaml": {"overrides": {"giro-a": {"cents": 1_100_000},
                                               "tag-a": {"cents": 2_100_000}}}})
    # Die Seite machte aus dem Konto mit Auszug eines ohne: Davor las es `parsed`, danach nicht.
    assert paare._konto_modi(config) == set()
    config2 = _config(tmp_path / "zwei", **{
        "accounts.yaml": {"accounts": [dict(KONTEN["accounts"][1], ingest_mode="parsed"),
                                       dict(KONTEN["accounts"][0], ingest_mode="summary")]},
        "accounts_custom.yaml": {"accounts": {"tag-a": {"ingest_mode": "parsed"}}},
        "balances.yaml": {"balances": [
            {"account_id": "giro-a", "cents": 1_000_000, "as_of": "2026-09-30"},
            {"account_id": "tag-a", "cents": 2_000_000, "as_of": "2026-09-30"}]},
        "balances_custom.yaml": {"overrides": {"giro-a": {"cents": 1_100_000},
                                               "tag-a": {"cents": 2_100_000, "notiz": "x"}}}})
    vorher = paare._konto_modi(config2)
    assert vorher == {"tag-a"}
    plan, _, _ = umstellen.ausfuehren(config2.parent, heute=HEUTE)
    assert not plan.fehler, plan.fehler
    # Das Konto mit Auszug behielt seinen Wert aus der Datei, den der Seite nur in der Notiz.
    positionen = {p["account_id"]: p for p in _gelesen(config2, "balances.yaml")["balances"]}
    assert positionen["giro-a"]["cents"] == 1_100_000
    assert positionen["tag-a"]["cents"] == 2_000_000 and "2100000" in positionen["tag-a"]["notiz"]
    # Nach dem Lauf gibt es nur noch eine Datei, und sie sagt dasselbe.
    assert paare._konto_modi(config2) == vorher
    assert not (config2 / "accounts_custom.yaml").exists()


def test_accounts_what_the_page_creates_goes_into_the_one_file_and_reads_back(tmp_path):
    from finctl import konten

    config = _config(tmp_path, **{"accounts.yaml": KONTEN, "accounts_custom.yaml": KONTEN_SEITE})
    umstellen.ausfuehren(config.parent, heute=HEUTE)
    db = sqlite3.connect(":memory:")
    db.executescript(Path("finctl/ledger/schema.sql").read_text(encoding="utf-8"))
    konten.anlegen(db, {"id": "extra", "display_name": "Extra", "institution": "Bank D",
                        "account_type": "giro", "ingest_mode": "summary"}, config,
                   tmp_path / "statements")
    spec = _gelesen(config, "accounts.yaml")
    assert [k["id"] for k in spec["accounts"]] == ["giro-a", "tag-a", "neu-a", "extra"]
    assert spec["accounts"][0]["notiz"].startswith("Betriebskonto.")
    assert [k["id"] for k in konten.laden(config)] == ["giro-a", "tag-a", "neu-a", "extra"]


# ---------------------------------------------------------------- lebensplan

LEBEN = {
    "person": {"birth_date": date(1980, 7, 15), "krankenversicherung": "gesetzlich",
               "birth_year": 1980},
    "schwellen": {"grv_ab_alter": 67, "private_rente_ab_alter": 62},
    "erwerbseinkommen": {"netto_100_monatlich_cents": 300_000},
    "notizen": {"person.birth_date": {"notiz": "Aus der Urkunde.", "notiz_vom": "2026-01-01"},
                "bereich": {"notiz": "Wer plant."}},
}
LEBEN_SEITE = {
    "person": {"geburtsdatum": "1981-08-16", "krankenversicherung": "privat",
               "rente_ab_alter": 65},
    "notizen": {"person.geburtsdatum": {"notiz": "Korrigiert.", "notiz_vom": "2026-09-01"},
                "person.rente_ab_alter": {"notiz": "Teilrente moeglich."},
                "bereich": {"notiz": "Auf /einrichtung gesetzt."}},
}


def test_lebensplan_the_names_of_the_page_become_the_names_of_the_file():
    neu, gelegt = _legen(LEBEN_PAAR, LEBEN, LEBEN_SEITE)
    assert neu["person"]["birth_date"] == date(1981, 8, 16)
    assert neu["person"]["krankenversicherung"] == "privat"
    assert neu["schwellen"]["grv_ab_alter"] == 65
    # Alles andere der Datei bleibt, wie es war.
    assert neu["person"]["birth_year"] == 1980
    assert neu["schwellen"]["private_rente_ab_alter"] == 62
    assert neu["erwerbseinkommen"] == LEBEN["erwerbseinkommen"]
    assert "geburtsdatum" not in neu["person"] and "rente_ab_alter" not in neu.get("person", {})
    assert sorted(o for o, _ in gelegt.ueberschrieben) == [
        "person.birth_date", "person.krankenversicherung", "schwellen.grv_ab_alter"]


def test_lebensplan_every_reader_of_person_angaben_reads_what_it_read_before():
    leer = {"person": {"geburtsdatum": "", "krankenversicherung": None, "rente_ab_alter": 0}}
    for seite in (LEBEN_SEITE, {}, {"person": {"rente_ab_alter": 60}}, leer):
        neu, _ = _legen(LEBEN_PAAR, LEBEN, seite)
        assert LEBEN_PAAR.alt(LEBEN, seite) == LEBEN_PAAR.neu(neu), seite
    from finctl import person

    neu, _ = _legen(LEBEN_PAAR, LEBEN, LEBEN_SEITE)
    assert person.aus_spec(neu) == {"geburtsdatum": date(1981, 8, 16),
                                    "krankenversicherung": "privat", "rente_ab_alter": 65}
    assert person.rentenbeginn_aus(person.aus_spec(neu)) == date(2046, 9, 1)


def test_lebensplan_an_empty_value_of_the_page_does_not_override_as_before():
    neu, gelegt = _legen(LEBEN_PAAR, LEBEN, {"person": {"geburtsdatum": "", "rente_ab_alter": 0}})
    assert neu["person"]["birth_date"] == date(1980, 7, 15) and neu["schwellen"][
        "grv_ab_alter"] == 67
    assert gelegt.ueberschrieben == []


def test_lebensplan_the_notes_follow_the_names_and_the_replaced_values_stand_in_them():
    neu, _ = _legen(LEBEN_PAAR, LEBEN, LEBEN_SEITE)
    n = neu["notizen"]
    assert n["person.birth_date"]["notiz"] == (
        "Aus der Urkunde.\n\nKorrigiert.\n\nBis zur Umstellung stand in der Datei: "
        "`person.birth_date`: 1980-07-15.")
    assert n["person.birth_date"]["notiz_vom"] == "2026-09-01"
    assert n["schwellen.grv_ab_alter"]["notiz"] == (
        "Teilrente moeglich.\n\nBis zur Umstellung stand in der Datei: "
        "`schwellen.grv_ab_alter`: 67.")
    assert n["person.krankenversicherung"]["notiz"] == (
        "Bis zur Umstellung stand in der Datei: `person.krankenversicherung`: gesetzlich.")
    assert n["bereich"]["notiz"] == "Wer plant.\n\nAuf /einrichtung gesetzt."
    assert not any(ort.startswith("person.geburts") or ort.endswith("rente_ab_alter")
                   for ort in n)


def test_lebensplan_a_lost_note_is_a_failed_check_too(monkeypatch):
    def verliert(basis, seite, bericht):
        gelegt = paare._lebensplan_legen(basis, seite, bericht)
        gelegt["notizen"].pop("schwellen.grv_ab_alter")
        return gelegt

    kaputt = paare.Paar(LEBEN_PAAR.basis, LEBEN_PAAR.seite, verliert, LEBEN_PAAR.alt,
                        LEBEN_PAAR.neu, ort_neu=LEBEN_PAAR.ort_neu)
    gelegt = paare.zusammenlegen(kaputt, LEBEN, LEBEN_SEITE)
    assert any("steht nicht in der zusammengelegten" in f for f in gelegt.fehler)
    assert gelegt.neu is None


def test_lebensplan_without_a_base_file_the_template_is_the_base(tmp_path):
    config = _config(tmp_path, **{"lebensplan_custom.yaml": LEBEN_SEITE})
    plan, _, _ = umstellen.ausfuehren(config.parent, heute=HEUTE)
    assert not plan.fehler, plan.fehler
    spec = _gelesen(config, "lebensplan.yaml")
    assert spec["person"]["birth_date"] == date(1981, 8, 16) and spec["schwellen"][
        "grv_ab_alter"] == 65
    assert "kapital" in spec                                  # aus der Vorlage
    assert sorted(p.name for p in config.iterdir()) == ["lebensplan.yaml"]


def test_lebensplan_the_page_writes_the_file_whole_after_the_merge(tmp_path):
    from finctl import person

    config = _config(tmp_path, **{"lebensplan.yaml": LEBEN, "lebensplan_custom.yaml": LEBEN_SEITE})
    umstellen.ausfuehren(config.parent, heute=HEUTE)
    vorher = (config / "lebensplan.yaml").read_bytes()
    person.setzen({"geburtsdatum": "1981-08-16", "krankenversicherung": "privat",
                   "rente_ab_alter": "65"}, config)
    assert (config / "lebensplan.yaml").read_bytes() == vorher           # kein Byte
    person.setzen({"rente_ab_alter": "63"}, config)
    spec = _gelesen(config, "lebensplan.yaml")
    assert spec["schwellen"]["grv_ab_alter"] == 63 and "person.birth_date" in spec["notizen"]
    assert not (config / "lebensplan_custom.yaml").exists()


# ------------------------------------------------------------------ backup

SICHERUNG = {"directory": "~/alt", "keep": 12, "notizen": {
    "keep": {"notiz": "Zwoelf Staende, weil ein Jahr reicht."}, "bereich": {"notiz": "Sicherung."}}}
SICHERUNG_SEITE = {"backup": {"directory": "/ziel/neu", "keep": 3, "extra": "x"},
                   "notizen": {"directory": {"notiz": "Neues Ziel."},
                               "keep": {"notiz": "Auf drei gesetzt."}}}


def test_backup_the_target_and_the_number_of_the_page_replace_those_of_the_file():
    neu, gelegt = _legen(SICHERUNG_PAAR, SICHERUNG, SICHERUNG_SEITE)
    assert (neu["directory"], neu["keep"]) == ("/ziel/neu", 3)
    assert "extra" not in neu                      # der alte Leser las nur `directory` und `keep`
    assert any("backup.extra" in u for u in gelegt.ungelesen)
    assert SICHERUNG_PAAR.alt(SICHERUNG, SICHERUNG_SEITE) == SICHERUNG_PAAR.neu(neu)


def test_backup_the_old_values_stand_in_the_notes_under_their_keys_and_the_notes_meet():
    neu, _ = _legen(SICHERUNG_PAAR, SICHERUNG, SICHERUNG_SEITE)
    n = neu["notizen"]
    assert n["keep"]["notiz"] == ("Zwoelf Staende, weil ein Jahr reicht.\n\nAuf drei gesetzt.\n\n"
                                  "Bis zur Umstellung stand in der Datei: `keep`: 12.")
    assert n["directory"]["notiz"] == ("Neues Ziel.\n\nBis zur Umstellung stand in der Datei: "
                                       "`directory`: ~/alt.")
    assert n["bereich"]["notiz"] == "Sicherung."


def test_backup_the_page_file_alone_becomes_the_file_and_the_base_alone_has_nothing_to_do(
        tmp_path):
    config = _config(tmp_path, **{"backup_custom.yaml": SICHERUNG_SEITE})
    umstellen.ausfuehren(config.parent, heute=HEUTE)
    spec = _gelesen(config, "backup.yaml")
    assert (spec["directory"], spec["keep"]) == ("/ziel/neu", 3)
    assert sorted(p.name for p in config.iterdir()) == ["backup.yaml"]
    assert not umstellen.planen(_config(tmp_path / "x", **{"backup.yaml": SICHERUNG})).offen


def test_backup_the_reader_and_the_writer_know_only_the_one_file(tmp_path, monkeypatch):
    from finctl import ops

    config = _config(tmp_path, **{"backup.yaml": SICHERUNG, "backup_custom.yaml": SICHERUNG_SEITE})
    monkeypatch.setattr(ops, "CONFIG_DIR", config)
    umstellen.ausfuehren(config.parent, heute=HEUTE)
    assert ops.backup_settings() == (Path("/ziel/neu"), 3)
    ops.backup_setzen({"directory": "/ziel/dritter"})
    spec = _gelesen(config, "backup.yaml")
    assert spec["directory"] == "/ziel/dritter" and spec["keep"] == 3
    assert spec["notizen"]["keep"]["notiz"].startswith("Zwoelf Staende")
    # Eine stehengebliebene Seitendatei aendert nichts mehr.
    (config / "backup_custom.yaml").write_text("backup: {directory: /anders}\n", encoding="utf-8")
    assert ops.backup_settings()[0] == Path("/ziel/dritter")


# ------------------------------------------------------------- der Lauf, vier Paare


def _alle_vier(tmp_path: Path) -> Path:
    config = _config(tmp_path, **{
        "rules.yaml": REGELN, "rules_custom.yaml": REGELN_SEITE,
        "accounts.yaml": KONTEN, "accounts_custom.yaml": KONTEN_SEITE,
        "lebensplan.yaml": LEBEN, "lebensplan_custom.yaml": LEBEN_SEITE,
        "backup.yaml": SICHERUNG, "backup_custom.yaml": SICHERUNG_SEITE})
    return config.parent


SEITEN_E = ("rules_custom.yaml", "accounts_custom.yaml", "lebensplan_custom.yaml",
            "backup_custom.yaml")


def test_the_run_merges_the_four_pairs_and_a_second_run_does_nothing(tmp_path):
    wurzel = _alle_vier(tmp_path)
    vorher = {n: (wurzel / "config" / n).read_bytes() for n in SEITEN_E}
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)

    assert not plan.fehler, plan.fehler
    assert sorted(p.name for p in (wurzel / "config").iterdir()) == [
        "accounts.yaml", "backup.yaml", "lebensplan.yaml", "rules.yaml"]
    assert {n: (sicherung / "config" / n).read_bytes() for n in vorher} == vorher
    text = bericht.read_text(encoding="utf-8")
    for seite, basis in zip(SEITEN_E, ("rules", "accounts", "lebensplan", "backup"), strict=True):
        assert f"Zusammengelegt: `{seite}` in `{basis}.yaml`" in text
    assert "`alpha.match`" in text and "`person.birth_date`: 1980-07-15" in text

    summe = _pruefsumme(wurzel)
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert not plan.zu_tun and sicherung is None and bericht is None
    assert _pruefsumme(wurzel) == summe


def test_the_app_stops_while_a_page_file_of_one_of_the_four_is_still_there(tmp_path):
    for name, basis, seite in (("a", "rules.yaml", "rules_custom.yaml"),
                               ("b", "accounts.yaml", "accounts_custom.yaml"),
                               ("c", "lebensplan.yaml", "lebensplan_custom.yaml"),
                               ("d", "backup.yaml", "backup_custom.yaml")):
        config = _config(tmp_path / name, **{basis: {"x": 1}, seite: {"x": 2}})
        assert umstellen.planen(config).offen, seite
        with pytest.raises(umstellen.AlteFormError, match=seite.replace(".", r"\.")):
            umstellen.halt_wenn_offen(config)


def test_the_probe_of_the_four_leaves_the_data_folder_alone_and_equals_the_real_run(tmp_path):
    wurzel = _alle_vier(tmp_path)
    vorher = _pruefsumme(wurzel)
    probe = tmp_path / "Probe"
    umstellen.probieren(wurzel, probe, heute=HEUTE)
    assert _pruefsumme(wurzel) == vorher
    assert sorted(p.name for p in (probe / "config").iterdir()) == [
        "accounts.yaml", "backup.yaml", "lebensplan.yaml", "rules.yaml"]
    umstellen.ausfuehren(wurzel, heute=HEUTE)
    for name in ("rules.yaml", "accounts.yaml", "lebensplan.yaml", "backup.yaml"):
        assert (probe / "config" / name).read_bytes() == (wurzel / "config" / name).read_bytes()


def test_comments_of_both_files_of_the_four_become_notes_before_the_two_are_merged(tmp_path):
    config = _config(tmp_path, **{
        "rules.yaml": "# Kopf.\nrules:\n  # Warum alpha.\n  - id: alpha\n    name: A\n"
                      "    match: {text: [A]}\n    set: {mgmt: a/b}\n",
        "rules_custom.yaml": "# Von /regeln.\nregeln:\n  # Aus der Seite.\n  alpha: "
                             "{priority: 5}\n",
        "accounts.yaml": "# Kopf.\naccounts:\n  # Warum.\n  - id: g\n    display_name: G\n",
        "accounts_custom.yaml": "# Von /konten.\naccounts:\n  # Aus der Seite.\n  g: "
                                "{institution: B}\n",
        "lebensplan.yaml": "# Kopf.\nperson:\n  # Aus der Urkunde.\n  birth_date: 1980-07-15\n",
        "lebensplan_custom.yaml": "# Von /einrichtung.\n\nperson:\n  # Korrigiert.\n"
                                  "  geburtsdatum: '1981-08-16'\n",
        "backup.yaml": "# Kopf.\n# Warum zwoelf.\nkeep: 12\ndirectory: /alt\n",
        "backup_custom.yaml": "# Von /system.\nbackup:\n  directory: /neu\n"})
    plan, _, _ = umstellen.ausfuehren(config.parent, heute=HEUTE)
    assert not plan.fehler, plan.fehler
    alpha = _gelesen(config, "rules.yaml")["rules"][0]
    assert alpha["notiz"].startswith("Warum alpha.\n\nAus der Seite.")
    assert alpha["priority"] == 5
    assert _gelesen(config, "accounts.yaml")["accounts"][0]["notiz"] == "Warum.\n\nAus der Seite."
    leben = _gelesen(config, "lebensplan.yaml")
    assert leben["person"]["birth_date"] == date(1981, 8, 16)
    assert leben["notizen"]["person.birth_date"]["notiz"].startswith(
        "Aus der Urkunde.\n\nKorrigiert.")
    assert "Von /einrichtung." in leben["notizen"]["bereich"]["notiz"]
    assert _gelesen(config, "backup.yaml")["directory"] == "/neu"
    for name in ("rules.yaml", "accounts.yaml", "lebensplan.yaml", "backup.yaml"):
        assert "# " not in (config / name).read_text(encoding="utf-8"), name


def test_a_merge_of_the_four_that_loses_something_is_a_failed_check_and_writes_nothing(
        tmp_path, monkeypatch):
    def ohne_match(basis, seite, bericht):
        gelegt = paare._regeln_legen(basis, seite, bericht)
        gelegt["rules"][0].pop("match")
        return gelegt

    def ohne_ziel(basis, seite, bericht):
        gelegt = paare._backup_legen(basis, seite, bericht)
        gelegt.pop("directory")
        return gelegt

    def ohne_konto(basis, seite, bericht):
        gelegt = paare._konten_legen(basis, seite, bericht)
        gelegt["accounts"].pop()
        return gelegt

    def ohne_alter(basis, seite, bericht):
        gelegt = paare._lebensplan_legen(basis, seite, bericht)
        gelegt["schwellen"].pop("grv_ab_alter")
        return gelegt

    for paar, legen in ((REGELN_PAAR, ohne_match), (SICHERUNG_PAAR, ohne_ziel),
                        (KONTEN_PAAR, ohne_konto), (LEBEN_PAAR, ohne_alter)):
        kaputt = paare.Paar(paar.basis, paar.seite, legen, paar.alt, paar.neu,
                            wurzeln=paar.wurzeln, seitenwurzel=paar.seitenwurzel,
                            vorlage=paar.vorlage, ort_neu=paar.ort_neu)
        monkeypatch.setattr(umstellen, "PAARE", (kaputt,))
        wurzel = _alle_vier(tmp_path / paar.basis)
        vorher = _pruefsumme(wurzel)
        plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)
        assert plan.fehler and "liest sich nicht" in plan.fehler[0], paar.basis
        assert sicherung is None and bericht is None and _pruefsumme(wurzel) == vorher


def test_the_readers_and_writers_of_rules_accounts_and_lebensplan_know_only_the_one_file(
        tmp_path):
    """Eine Seitendatei, die nach der Umstellung stehen bliebe, gilt nicht mehr."""
    from finctl import konten, person
    from finctl.rules import engine
    from finctl.rules import regelwerk as rw

    config = _config(tmp_path, **{
        "rules.yaml": REGELN, "rules_custom.yaml": REGELN_SEITE,
        "accounts.yaml": KONTEN, "accounts_custom.yaml": KONTEN_SEITE,
        "lebensplan.yaml": LEBEN, "lebensplan_custom.yaml": LEBEN_SEITE})
    seiten = {n: (config / n).read_bytes() for n in SEITEN_E[:3]}

    assert [r["id"] for r in engine.rohe_regeln(config / "rules.yaml")
            if r["herkunft"] == "basis"] == ["alpha", "beta", "allg-finanzamt"]
    assert [k["id"] for k in konten.laden(config)] == ["giro-a", "tag-a", "alt-a"]
    assert person.angaben(config) == {"geburtsdatum": date(1980, 7, 15),
                                      "krankenversicherung": "gesetzlich",
                                      "rente_ab_alter": 67}

    # Die Schreiber lassen die Seitendateien liegen.
    e, _ = rw.entwurf({**rw.formwerte(rw.laden(config / "rules.yaml")[0]), "id": "alpha",
                       "name": "Alpha 2"}, config / "rules.yaml")
    rw.speichern(e, config / "rules.yaml")
    person.setzen({"rente_ab_alter": "64"}, config)
    db = sqlite3.connect(":memory:")
    db.executescript(Path("finctl/ledger/schema.sql").read_text(encoding="utf-8"))
    konten.anlegen(db, {"id": "extra", "display_name": "Extra", "institution": "Bank D",
                        "account_type": "giro", "ingest_mode": "summary"}, config,
                   tmp_path / "statements")
    assert {n: (config / n).read_bytes() for n in SEITEN_E[:3]} == seiten


# ------------------------------------------------------------------ settings (N.3f)
#
# `settings_custom.yaml` hatte keine Basis, sondern zwei: Die zwoelf Stellschrauben
# ueberschrieben `assumptions.yaml`, die Untergrenzen `floor_cents:<konto>` die Konto-Regeln in
# `forecast.yaml`. Es gibt deshalb zwei Paare mit derselben Seitendatei; jedes sieht nur seinen
# Teil (`Paar.ansicht`).

ANNAHMEN_PAAR, UNTERGRENZEN_PAAR = (p for p in paare.PAARE if p.seite == "settings_custom.yaml")

ANNAHMEN = {
    "inflation_pa": 0.02,
    "kapital": {"rendite_nominal_pa": 0.025, "rendite_depot_pa": 0.06},
    "erwerbseinkommen": {"netto_floor_monatlich_cents": 360_000, "netto_median_monatlich_cents":
                         380_000, "gehalt_steigerung_pa": 0.02},
    "ruhestand": {"lebenserwartung": 90, "abzug_renten": 0.25, "aufbrauchen": 1.0},
    "notizen": {"kapital.rendite_depot_pa": {"notiz": "Breiter Fonds.", "notiz_vom": "2026-03-01"},
                "bereich": {"notiz": "Annahmen."}},
}
EINSTELLUNGEN = {
    "einstellungen": {
        "rendite_depot_pa": 0.05, "salary_floor_cents": 360_000,        # gleich der Basis
        "teilzeit_anteil": 0.8, "teilzeit_ab": "2040-01", "sparerpauschbetrag_cents": 200_000,
        "floor_cents:giro": 90_000, "floor_cents:karte": 5_000, "floor_cents:neu": 7_000,
        "floor_cents:tag": 0, "floor_cents:kaputt": "viel", "unbekannt": 1},
    "notizen": {"einstellungen.teilzeit_ab": {"notiz": "Ab dort kuerzer.",
                                              "notiz_vom": "2026-09-30"},
                "einstellungen.rendite_depot_pa": {"notiz": "Vorsichtiger."},
                "einstellungen.floor_cents:giro": {"notiz": "Wegen der Miete.",
                                                   "notiz_vom": "2026-08-01"},
                "bereich": {"notiz": "Von /annahmen gesetzt."}},
}
FORECAST_UNTERGRENZE = {"account_roles": {"giro": {"floor_cents": 130_000},
                                          "tag": {"floor_cents": 1_000}}}


def _ansicht(paar: paare.Paar, seite: dict) -> dict:
    return paar.ansicht(seite)[0]


def test_settings_the_twelve_values_go_to_the_path_the_loader_gave_them():
    from finctl import assumptions as ann

    werte = {"inflation_pa": 0.03, "rendite_nominal_pa": 0.02, "rendite_depot_pa": 0.05,
             "sparerpauschbetrag_cents": 200_000, "kostenschwelle_pa": 0.01,
             "gehalt_steigerung_pa": 0.03, "salary_floor_cents": 400_000, "teilzeit_anteil": 0.8,
             "teilzeit_ab": "2040-01", "lebenserwartung": 92, "abzug_renten": 0.3,
             "aufbrauchen": 0.9}
    # Die zwei Annahmen seit 8c1 (Steuersatz, Basiszins) gab es in der alten Tabelle nie.
    alt = {k: p for k, p in ann.UEBERSCHREIBBAR.items()
           if k not in ("steuersatz_kapital", "basiszins_pa")}
    assert set(werte) == set(alt)
    neu, _ = _legen(ANNAHMEN_PAAR, ANNAHMEN, {"einstellungen": werte})
    for schluessel, pfad in alt.items():
        knoten = neu
        for teil in pfad:
            knoten = knoten[teil]
        assert knoten == werte[schluessel], schluessel
    assert neu["erwerbseinkommen"]["netto_median_monatlich_cents"] == 380_000      # der Rest bleibt


def test_settings_the_part_time_values_the_base_lacked_land_where_the_loader_put_them():
    neu, gelegt = _legen(ANNAHMEN_PAAR, ANNAHMEN, EINSTELLUNGEN)
    erwerb = neu["erwerbseinkommen"]
    assert (erwerb["teilzeit_anteil"], str(erwerb["teilzeit_ab"])) == (0.8, "2040-01")
    assert "erwerbseinkommen.teilzeit_anteil (Angabe, nur in der Seite)" in gelegt.aus_seite
    # Fehlt der Abschnitt ganz, legt ihn der Zusammenleger an, wie `load` es tat.
    ohne = {k: v for k, v in ANNAHMEN.items() if k != "erwerbseinkommen"}
    neu, _ = _legen(ANNAHMEN_PAAR, ohne, {"einstellungen": {"teilzeit_ab": "2041-02"}})
    assert neu["erwerbseinkommen"] == {"teilzeit_ab": "2041-02"}


def test_settings_the_merged_assumptions_read_like_the_file_and_the_page_did():
    neu, _ = _legen(ANNAHMEN_PAAR, ANNAHMEN, EINSTELLUNGEN)
    sicht = _ansicht(ANNAHMEN_PAAR, EINSTELLUNGEN)
    assert ANNAHMEN_PAAR.alt(ANNAHMEN, sicht) == ANNAHMEN_PAAR.neu(neu)
    # Die Untergrenzen und der Schluessel, den kein Leser kannte, sind nicht seine.
    assert set(sicht["einstellungen"]) == {"rendite_depot_pa", "salary_floor_cents",
                                           "teilzeit_anteil", "teilzeit_ab",
                                           "sparerpauschbetrag_cents"}


def test_settings_a_value_the_page_replaced_stays_in_the_note_under_its_path():
    neu, gelegt = _legen(ANNAHMEN_PAAR, ANNAHMEN, EINSTELLUNGEN)
    assert neu["kapital"]["rendite_depot_pa"] == 0.05
    notiz = neu["notizen"]["kapital.rendite_depot_pa"]
    assert notiz["notiz"] == ("Breiter Fonds.\n\nVorsichtiger.\n\nBis zur Umstellung stand in "
                              "der Datei: `kapital.rendite_depot_pa`: 0.06.")
    assert str(notiz["notiz_vom"]) == "2026-03-01"
    assert [o for o, _ in gelegt.ueberschrieben] == ["kapital.rendite_depot_pa"]
    # Ein Wert gleich dem der Basis ersetzt nichts, und die Notiz des Bereichs wird eine.
    assert "salary_floor_cents" not in str(gelegt.ueberschrieben)
    assert neu["notizen"]["bereich"]["notiz"] == "Annahmen.\n\nVon /annahmen gesetzt."
    assert "notizen.kapital.rendite_depot_pa" in gelegt.notizen


def test_settings_a_note_on_a_setting_goes_to_the_path_of_that_setting_in_the_file():
    neu, _ = _legen(ANNAHMEN_PAAR, ANNAHMEN, EINSTELLUNGEN)
    teilzeit = neu["notizen"]["erwerbseinkommen.teilzeit_ab"]
    assert teilzeit["notiz"] == "Ab dort kuerzer." and str(teilzeit["notiz_vom"]) == "2026-09-30"
    assert not any(ort.startswith("einstellungen") for ort in neu["notizen"])


def test_settings_what_no_reader_knew_is_reported_and_not_carried_over():
    neu, gelegt = _legen(ANNAHMEN_PAAR, ANNAHMEN, EINSTELLUNGEN)
    assert any("einstellungen.unbekannt" in u for u in gelegt.ungelesen)
    assert "unbekannt" not in neu and "einstellungen" not in neu
    _, unter = _legen(UNTERGRENZEN_PAAR, FORECAST, EINSTELLUNGEN)
    assert any("floor_cents:kaputt" in u for u in unter.ungelesen)


def test_settings_a_floor_goes_to_the_rule_of_its_account_and_wins_over_the_declared_one():
    neu, gelegt = _legen(UNTERGRENZEN_PAAR, FORECAST, EINSTELLUNGEN)
    rollen = neu["account_roles"]
    assert (rollen["giro"]["floor_cents"], rollen["karte"]["floor_cents"]) == (90_000, 5_000)
    assert rollen["giro"]["role"] == "operating" and rollen["giro"]["ceiling_cents"] == 700_000
    # Der ersetzte Wert steht in der Notiz, hinter beiden Notizen.
    assert rollen["giro"]["notiz"] == (
        "Betriebskonto.\n\n`floor_cents`: Wegen der Miete.\n\n"
        "Bis zur Umstellung stand in der Datei: `floor_cents`: 150000.")
    assert str(rollen["giro"]["notiz_vom"]) == "2026-09-01"        # das spaetere der beiden
    assert ("giro.floor_cents", "150000") in gelegt.ueberschrieben
    # Gleich dem, was die Datei sagte: keine Notiz, nichts ersetzt.
    assert rollen["tag"]["floor_cents"] == 0 and "notiz" not in rollen["tag"]
    # Der Rest der Datei bleibt.
    assert neu["min_occurrences"] == 5 and neu["account_budgets"] == FORECAST["account_budgets"]


def test_settings_an_account_forecast_does_not_know_gets_a_rule_with_only_the_floor():
    neu, gelegt = _legen(UNTERGRENZEN_PAAR, FORECAST, EINSTELLUNGEN)
    assert neu["account_roles"]["neu"] == {"floor_cents": 7_000}
    assert "account_roles.neu (Konto, neu)" in gelegt.aus_seite
    # Das Konto ohne Regel liest sich wie eines, das nie eine hatte.
    regel = kontenregeln.aus_spec(neu)["account_roles"]["neu"]
    assert regel.get("role") is None and regel["floor_cents"] == 7_000


def test_settings_the_merged_floors_read_like_the_file_and_the_page_did():
    neu, _ = _legen(UNTERGRENZEN_PAAR, FORECAST, EINSTELLUNGEN)
    sicht = _ansicht(UNTERGRENZEN_PAAR, EINSTELLUNGEN)
    assert UNTERGRENZEN_PAAR.alt(FORECAST, sicht) == UNTERGRENZEN_PAAR.neu(neu)
    assert set(sicht["account_roles"]) == {"giro", "karte", "neu", "tag"}      # nicht "kaputt"


def test_settings_a_floor_set_next_to_floor_from_loan_stays_behind_the_rate(monkeypatch):
    from finctl.forecast import konten as fk

    basis = {"account_roles": {"rate": {"role": "servicing", "floor_from_loan": "k1"}}}
    neu, _ = _legen(UNTERGRENZEN_PAAR, basis, {"einstellungen": {"floor_cents:rate": 3_000}})
    regel = neu["account_roles"]["rate"]
    assert (regel["floor_from_loan"], regel["floor_cents"]) == ("k1", 3_000)
    fcfg = kontenregeln.aus_spec(neu)
    acct = {"dispo_threshold_cents": 100}
    monkeypatch.setattr(fk, "_rate_floor", lambda loan, month=None: 2_222)
    assert fk._floor_for("rate", fcfg, acct) == 2_222            # die Rate steht ganz vorn
    monkeypatch.setattr(fk, "_rate_floor", lambda loan, month=None: None)
    assert fk._floor_for("rate", fcfg, acct) == 3_000


def test_settings_a_floor_that_is_text_of_a_whole_number_counts_as_before():
    """`_floor_for` las `int(value)`: Text mit einer ganzen Zahl galt, alles andere nicht."""
    neu, _ = _legen(UNTERGRENZEN_PAAR, FORECAST,
                    {"einstellungen": {"floor_cents:giro": "80000", "floor_cents:tag": 12.5,
                                       "floor_cents:karte": ""}})
    assert neu["account_roles"]["giro"]["floor_cents"] == 80_000
    assert neu["account_roles"]["tag"]["floor_cents"] == 0              # unveraendert
    assert "floor_cents" not in neu["account_roles"]["karte"]


def _settings_ordner(tmp_path: Path, **zusatz) -> Path:
    config = _config(tmp_path, **{"assumptions.yaml": ANNAHMEN, "forecast.yaml": FORECAST,
                                  "settings_custom.yaml": EINSTELLUNGEN, **zusatz})
    return config.parent


def test_settings_the_run_merges_both_pairs_and_a_second_run_does_nothing(tmp_path):
    wurzel = _settings_ordner(tmp_path)
    seite = (wurzel / "config" / "settings_custom.yaml").read_bytes()
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert not plan.fehler, plan.fehler
    assert sorted(p.name for p in (wurzel / "config").iterdir()) == [
        "assumptions.yaml", "forecast.yaml"]
    assert (sicherung / "config" / "settings_custom.yaml").read_bytes() == seite
    text = bericht.read_text(encoding="utf-8")
    assert "Zusammengelegt: `settings_custom.yaml` in `assumptions.yaml`" in text
    assert "Zusammengelegt: `settings_custom.yaml` in `forecast.yaml`" in text
    assert "`giro.floor_cents`: 150000" in text and "teilzeit_anteil" in text
    summe = _pruefsumme(wurzel)
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert not plan.zu_tun and sicherung is None and bericht is None
    assert _pruefsumme(wurzel) == summe


def test_settings_the_probe_leaves_the_data_folder_alone_and_equals_the_real_run(tmp_path):
    wurzel = _settings_ordner(tmp_path)
    vorher = _pruefsumme(wurzel)
    probe = tmp_path / "Probe"
    umstellen.probieren(wurzel, probe, heute=HEUTE)
    assert _pruefsumme(wurzel) == vorher
    assert sorted(p.name for p in (probe / "config").iterdir()) == [
        "assumptions.yaml", "forecast.yaml"]
    umstellen.ausfuehren(wurzel, heute=HEUTE)
    for name in ("assumptions.yaml", "forecast.yaml"):
        assert (probe / "config" / name).read_bytes() == (wurzel / "config" / name).read_bytes()


def test_settings_next_to_forecast_custom_the_order_of_the_mergers_leaves_the_same_value(
        tmp_path):
    """Der alte Leser: Einstellungen vor der Seite der Konten vor der Basis."""
    wurzel = _settings_ordner(tmp_path, **{"forecast_custom.yaml": FORECAST_UNTERGRENZE})
    basis = {k: v.get("floor_cents") for k, v in FORECAST["account_roles"].items()}
    seite = {k: v["floor_cents"] for k, v in FORECAST_UNTERGRENZE["account_roles"].items()}
    einst = {_untergrenze_konto(k): v for k, v in EINSTELLUNGEN["einstellungen"].items()
             if k.startswith("floor_cents:") and isinstance(v, int)}
    alt = {**{k: v for k, v in basis.items() if v is not None}, **seite, **einst}

    plan, _, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert not plan.fehler, plan.fehler
    rollen = _gelesen(wurzel / "config", "forecast.yaml")["account_roles"]
    neu = {k: v["floor_cents"] for k, v in rollen.items() if "floor_cents" in v}
    assert neu == alt
    assert sorted(p.name for p in (wurzel / "config").iterdir()) == [
        "assumptions.yaml", "forecast.yaml"]
    # Keiner der ersetzten Werte ist verloren: der der Basis und der der Seite der Konten.
    notiz = rollen["giro"]["notiz"]
    assert "`floor_cents`: 150000." in notiz and "`floor_cents`: 130000." in notiz
    text = bericht.read_text(encoding="utf-8")
    assert "Zusammengelegt: `forecast_custom.yaml` in `forecast.yaml`" in text
    assert "Zusammengelegt: `settings_custom.yaml` in `forecast.yaml`" in text


def _untergrenze_konto(schluessel: str) -> str:
    return schluessel.partition(":")[2]


def test_settings_the_forecast_pair_comes_before_the_settings_pair_in_the_list():
    namen = [(p.basis, p.seite) for p in paare.PAARE]
    assert namen.index(("forecast.yaml", "forecast_custom.yaml")) < namen.index(
        ("forecast.yaml", "settings_custom.yaml"))


def test_settings_comments_of_the_page_file_reach_both_files_as_notes(tmp_path):
    config = _config(tmp_path, **{
        "assumptions.yaml": "inflation_pa: 0.02\nerwerbseinkommen: {gehalt_steigerung_pa: 0.02}\n",
        "forecast.yaml": "account_roles:\n  giro: {role: operating}\n",
        "settings_custom.yaml": "# Mein eigener Kopf.\n\neinstellungen:\n  # Wegen der Miete.\n"
                                "  floor_cents:giro: 90000\n  # Ab dort kuerzer.\n"
                                "  teilzeit_ab: 2040-01\n"})
    plan, _, _ = umstellen.ausfuehren(config.parent, heute=HEUTE)
    assert not plan.fehler, plan.fehler
    ann = _gelesen(config, "assumptions.yaml")
    assert ann["notizen"]["erwerbseinkommen.teilzeit_ab"]["notiz"] == "Ab dort kuerzer."
    assert "Mein eigener Kopf." in ann["notizen"]["bereich"]["notiz"]
    giro = _gelesen(config, "forecast.yaml")["account_roles"]["giro"]
    assert giro["notiz"] == "`floor_cents`: Wegen der Miete." and giro["floor_cents"] == 90_000
    for name in ("assumptions.yaml", "forecast.yaml"):
        assert "# " not in (config / name).read_text(encoding="utf-8")


def test_settings_only_floors_leave_assumptions_alone_and_only_values_leave_forecast_alone(
        tmp_path):
    nur_unter = _config(tmp_path / "a", **{
        "assumptions.yaml": ANNAHMEN, "forecast.yaml": FORECAST,
        "settings_custom.yaml": {"einstellungen": {"floor_cents:giro": 80_000}}})
    vorher = (nur_unter / "assumptions.yaml").read_bytes()
    umstellen.ausfuehren(nur_unter.parent, heute=HEUTE)
    assert (nur_unter / "assumptions.yaml").read_bytes() == vorher
    assert _gelesen(nur_unter, "forecast.yaml")["account_roles"]["giro"]["floor_cents"] == 80_000

    nur_werte = _config(tmp_path / "b", **{
        "assumptions.yaml": ANNAHMEN, "forecast.yaml": FORECAST,
        "settings_custom.yaml": {"einstellungen": {"inflation_pa": 0.04}}})
    vorher = (nur_werte / "forecast.yaml").read_bytes()
    umstellen.ausfuehren(nur_werte.parent, heute=HEUTE)
    assert (nur_werte / "forecast.yaml").read_bytes() == vorher
    assert _gelesen(nur_werte, "assumptions.yaml")["inflation_pa"] == 0.04
    assert not (nur_werte / "settings_custom.yaml").exists()


def test_settings_a_data_folder_with_only_the_page_file_gets_both_files(tmp_path):
    config = _config(tmp_path, **{"settings_custom.yaml": EINSTELLUNGEN})
    plan, _, _ = umstellen.ausfuehren(config.parent, heute=HEUTE)
    assert not plan.fehler, plan.fehler
    assert sorted(p.name for p in config.iterdir()) == ["assumptions.yaml", "forecast.yaml"]
    ann = _gelesen(config, "assumptions.yaml")
    assert ann["kapital"]["rendite_depot_pa"] == 0.05 and "inflation_pa" in ann    # die Vorlage
    giro = _gelesen(config, "forecast.yaml")["account_roles"]["giro"]
    assert giro["floor_cents"] == 90_000 and giro["notiz"] == "`floor_cents`: Wegen der Miete."


def test_settings_only_the_base_files_have_nothing_to_do(tmp_path):
    config = _config(tmp_path, **{"assumptions.yaml": ANNAHMEN, "forecast.yaml": FORECAST})
    assert not umstellen.planen(config).offen


def test_settings_a_merge_that_loses_a_value_a_floor_or_a_note_writes_nothing(
        tmp_path, monkeypatch):
    def ohne_teilzeit(basis, seite, bericht):
        gelegt = paare._stellschrauben_legen(basis, seite, bericht)
        gelegt["erwerbseinkommen"].pop("teilzeit_ab")
        return gelegt

    def ohne_untergrenze(basis, seite, bericht):
        gelegt = paare._forecast_legen(basis, seite, bericht)
        gelegt["account_roles"]["karte"].pop("floor_cents")
        return gelegt

    def ohne_notiz(basis, seite, bericht):
        gelegt = paare._stellschrauben_legen(basis, seite, bericht)
        gelegt["notizen"].pop("erwerbseinkommen.teilzeit_ab")
        return gelegt

    def ohne_notiz_der_regel(basis, seite, bericht):
        gelegt = paare._forecast_legen(basis, seite, bericht)
        gelegt["account_roles"]["giro"].pop("notiz")
        return gelegt

    for paar, legen, was in ((ANNAHMEN_PAAR, ohne_teilzeit, "liest sich nicht"),
                             (UNTERGRENZEN_PAAR, ohne_untergrenze, "liest sich nicht"),
                             (ANNAHMEN_PAAR, ohne_notiz, "steht nicht in der zusammengelegten"),
                             (UNTERGRENZEN_PAAR, ohne_notiz_der_regel,
                              "steht nicht in der zusammengelegten")):
        kaputt = paare.Paar(paar.basis, paar.seite, legen, paar.alt, paar.neu,
                            wurzeln=paar.wurzeln, vorlage=paar.vorlage, ansicht=paar.ansicht)
        monkeypatch.setattr(umstellen, "PAARE", (kaputt,))
        wurzel = _settings_ordner(tmp_path / f"{paar.basis}-{legen.__name__}")
        vorher = _pruefsumme(wurzel)
        plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)
        assert plan.fehler and was in plan.fehler[0], (legen.__name__, plan.fehler)
        assert sicherung is None and bericht is None and _pruefsumme(wurzel) == vorher


def test_settings_a_scenario_file_reads_the_same_values_after_the_run_as_before(tmp_path):
    """Eine Szenariodatei bekam nie ein Overlay und erbt nichts aus `assumptions.yaml`."""
    from finctl import assumptions as ann

    pessimistisch = {**ANNAHMEN, "inflation_pa": 0.04}
    config = _config(tmp_path, **{"assumptions.pessimistisch.yaml": pessimistisch,
                                  "assumptions.yaml": ANNAHMEN, "forecast.yaml": FORECAST,
                                  "settings_custom.yaml": EINSTELLUNGEN})
    szenario = config / "assumptions.pessimistisch.yaml"
    basis = config / "assumptions.yaml"
    ann.reset_cache()
    def gelesen() -> dict:
        return {"datei": ann.load(szenario), "teilzeit": ann.teilzeit_anteil(szenario),
                "ab": ann.teilzeit_ab(szenario), "rendite": ann.rendite_depot_pa(szenario),
                "boden": ann.salary_floor_cents(szenario),
                "schwelle": ann.kostenschwelle_pa(szenario)}

    vorher = gelesen()
    roh = szenario.read_bytes()
    assert vorher["teilzeit"] is None and vorher["rendite"] == 0.06     # nichts von der Seite

    plan, _, _ = umstellen.ausfuehren(config.parent, heute=HEUTE)
    assert not plan.fehler, plan.fehler
    ann.reset_cache()
    assert szenario.read_bytes() == roh
    assert gelesen() == vorher
    # Die Basis liest, was die Seite gesetzt hatte, jetzt aus der Datei selbst.
    assert ann.rendite_depot_pa(basis) == 0.05 and ann.teilzeit_anteil(basis) == 0.8
    assert ann.teilzeit_ab(basis) == date(2040, 1, 1)
    ann.reset_cache()


def test_settings_the_readers_and_writers_know_only_the_two_files(tmp_path, monkeypatch):
    from finctl import assumptions as ann

    config = _settings_ordner(tmp_path) / "config"
    umstellen.ausfuehren(config.parent, heute=HEUTE)
    pfad = config / "assumptions.yaml"
    ann.reset_cache()
    # Eine stehengebliebene Seitendatei aendert nichts mehr, weder beim Lesen noch beim Schreiben.
    (config / "settings_custom.yaml").write_text(
        "einstellungen: {inflation_pa: 0.5, floor_cents:giro: 1}\n", encoding="utf-8")
    assert ann.load(pfad)["inflation_pa"] == 0.02
    assert ann.get("kapital", "rendite_depot_pa", path=pfad) == 0.05

    vorher = pfad.read_bytes()
    assert ann.setzen("rendite_depot_pa", 0.05, pfad) is False        # kein Byte
    assert pfad.read_bytes() == vorher
    assert ann.setzen("sparerpauschbetrag_cents", 200_000, pfad) is False
    assert ann.setzen("teilzeit_ab", "2041-06", pfad) is True
    spec = _gelesen(config, "assumptions.yaml")
    assert str(spec["erwerbseinkommen"]["teilzeit_ab"]) == "2041-06"
    assert spec["notizen"]["kapital.rendite_depot_pa"]["notiz"].startswith("Breiter Fonds.")
    assert ann.setzen("teilzeit_ab", "", pfad) is True                # leer nimmt es heraus
    assert "teilzeit_ab" not in _gelesen(config, "assumptions.yaml")["erwerbseinkommen"]
    with pytest.raises(ValueError):
        ann.setzen("inflation_pa", "", pfad)                          # ohne sie rechnet nichts
    assert _gelesen(config, "assumptions.yaml")["inflation_pa"] == 0.02
    # Ein Wert im Code, den die Datei nicht nennt, traegt die Seite nicht ein.
    ann.setzen("kostenschwelle_pa", ann.KOSTENSCHWELLE_VORGABE, pfad)
    assert "kostenschwelle_pa" not in _gelesen(config, "assumptions.yaml")["kapital"]

    # Die Untergrenze schreibt die Seite in `forecast.yaml`, ganz, mit der Notiz.
    monkeypatch.setattr(kontenregeln, "CONFIG_DIR", config)
    kontenregeln.setzen("giro", {"floor_cents": 90_000})
    forecast = (config / "forecast.yaml").read_bytes()
    kontenregeln.setzen("giro", {"floor_cents": 90_000})
    assert (config / "forecast.yaml").read_bytes() == forecast
    kontenregeln.setzen("giro", {"floor_cents": 95_000})
    giro = _gelesen(config, "forecast.yaml")["account_roles"]["giro"]
    assert giro["floor_cents"] == 95_000 and "Wegen der Miete." in giro["notiz"]
    assert (config / "settings_custom.yaml").read_text(encoding="utf-8").startswith("einstellungen")


def test_settings_init_writes_nothing_into_the_settings_table(tmp_path, monkeypatch):
    """Nach dem Zusammenlegen liest niemand die Tabelle mehr, und `init` fuellt sie nicht."""
    from typer.testing import CliRunner

    from finctl import cli, module, nachfuehren

    wurzel = _settings_ordner(tmp_path / "w")
    config = wurzel / "config"
    (config / "accounts.yaml").write_text(
        yaml_text({"accounts": [{"id": "giro", "display_name": "Giro", "institution": "Bank A",
                                 "account_type": "giro", "ingest_mode": "summary"}]}),
        encoding="utf-8")
    umstellen.ausfuehren(wurzel, heute=HEUTE)
    db = tmp_path / "t.db"
    monkeypatch.setattr(cli, "DB_PATH", db)
    monkeypatch.setattr(cli, "CONFIG_DIR", config)
    monkeypatch.setattr(module, "CONFIG_DIR", config)
    monkeypatch.setattr(nachfuehren, "CONFIG_DIR", config)
    lauf = CliRunner().invoke(cli.app, ["init", "--json"])
    assert lauf.exit_code == 0, lauf.output
    assert _tabellen(db) == set(), "das Schema legt die Tabelle settings nicht mehr an"


def test_settings_the_app_stops_for_every_page_file_of_every_pair_in_a_migrated_folder(tmp_path):
    """Nacheinander jede Seitendatei, die `finctl umstellen` zusammenlegen wuerde."""
    import importlib.util

    muster = Path(__file__).parent / "musterhaushalt"
    spec = importlib.util.spec_from_file_location("muster_bauen", muster / "bauen.py")
    bauen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bauen)
    datieren = bauen.datieren

    config = tmp_path / "config"
    config.mkdir()
    for datei in (muster / "config").iterdir():
        (config / datei.name).write_text(
            datieren(datei.read_text(encoding="utf-8"), HEUTE), encoding="utf-8")
    assert not umstellen.planen(config).offen
    umstellen.halt_wenn_offen(config)
    seiten = sorted({p.seite for p in paare.PAARE})
    assert "settings_custom.yaml" in seiten and len(seiten) == 14
    for seite in seiten:
        assert not (config / seite).exists(), seite
        (config / seite).write_text("{}\n", encoding="utf-8")
        assert umstellen.planen(config).offen, seite
        with pytest.raises(umstellen.AlteFormError, match=seite.replace(".", r"\.")):
            umstellen.halt_wenn_offen(config)
        (config / seite).unlink()
    umstellen.halt_wenn_offen(config)


# ------------------------------------- settings: die Tabelle gegen die Datei (vor dem Lauf)


ALT = "2026-10-01"         # der Tag der Zeilen in der Tabelle
VORHER = (2026, 9, 1)      # die Datei ist aelter als die Zeilen
LEGACY = ("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, note TEXT, "
          "updated_at TEXT NOT NULL)")


def _tabelle(wurzel: Path, *zeilen: tuple, datei_aelter: bool = False) -> Path:
    """Eine `finance.db` aelteren Standes mit Zeilen in `settings`: (Schluessel, Wert[, Notiz]).

    Das Schema legt die Tabelle nicht mehr an, also legt der Test sie wie frueher an. Mit
    `datei_aelter` ist `settings_custom.yaml` vor den Zeilen geaendert worden, sonst danach.
    """
    db = wurzel / "data" / "finance.db"
    db.parent.mkdir(exist_ok=True)
    c = connect(init_db(db))
    c.execute(LEGACY)
    for key, wert, *notiz in zeilen:
        c.execute("INSERT INTO settings (key, value, note, updated_at) VALUES (?,?,?,?)",
                  (key, wert, notiz[0] if notiz else None, ALT))
    c.commit()
    c.close()
    if datei_aelter:
        stand = datetime(*VORHER).timestamp()
        os.utime(wurzel / "config" / "settings_custom.yaml", (stand, stand))
    return db


def _tabellen(db: Path) -> set[str]:
    """Die Tabellen `settings` in dieser Datenbank (leer oder mit einem Namen)."""
    c = sqlite3.connect(db)
    try:
        return {r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")}
    finally:
        c.close()


GLEICH = (("floor_cents:giro", "90000"), ("floor_cents:karte", "5000"),
          ("floor_cents:neu", "7000"), ("floor_cents:tag", "0"),
          ("floor_cents:kaputt", "viel"), ("teilzeit_anteil", "0.8"), ("teilzeit_ab", "2040-01"))


def test_settings_a_table_that_says_what_the_file_says_lets_the_run_through(tmp_path):
    wurzel = _settings_ordner(tmp_path)
    _tabelle(wurzel, *GLEICH)
    plan, sicherung, _ = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert not plan.fehler and sicherung is not None
    assert not (wurzel / "config" / "settings_custom.yaml").exists()


def test_settings_a_row_only_in_the_table_stops_the_run_and_nothing_is_written(tmp_path):
    wurzel = _settings_ordner(tmp_path)
    _tabelle(wurzel, *GLEICH, ("floor_cents:alt", "1234"))
    vorher = _pruefsumme(wurzel)
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert sicherung is None and bericht is None and _pruefsumme(wurzel) == vorher
    assert any("`floor_cents:alt` = 1234" in f and "steht nicht in" in f for f in plan.fehler)
    assert len(plan.fehler) == 1
    # Die App haelt ebenfalls an und nennt die Zeile.
    with pytest.raises(umstellen.AlteFormError, match="floor_cents:alt"):
        umstellen.halt_wenn_offen(wurzel / "config")


def test_settings_another_value_in_the_table_stops_the_run(tmp_path):
    wurzel = _settings_ordner(tmp_path)
    _tabelle(wurzel, *(z if z[0] != "floor_cents:giro" else (z[0], "80000") for z in GLEICH),
             datei_aelter=True)
    vorher = _pruefsumme(wurzel)
    plan, sicherung, _ = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert sicherung is None and _pruefsumme(wurzel) == vorher
    assert any("`floor_cents:giro`: 80000, in settings_custom.yaml 90000" in f
               for f in plan.fehler)


def test_settings_a_note_in_the_table_stops_the_run(tmp_path):
    wurzel = _settings_ordner(tmp_path)
    _tabelle(wurzel, *GLEICH[:-1], ("teilzeit_ab", "2040-01", "Nur hier begruendet."))
    vorher = _pruefsumme(wurzel)
    plan, sicherung, _ = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert sicherung is None and _pruefsumme(wurzel) == vorher
    assert any("`teilzeit_ab` trägt eine Notiz" in f and "Nur hier begruendet." in f
               for f in plan.fehler)


def test_settings_the_probe_stops_for_the_same_rows_and_writes_no_report(tmp_path):
    wurzel = _settings_ordner(tmp_path)
    _tabelle(wurzel, ("floor_cents:alt", "1"))
    vorher = _pruefsumme(wurzel)
    plan, bericht = umstellen.probieren(wurzel, tmp_path / "Probe", heute=HEUTE)
    assert bericht is None and plan.fehler and _pruefsumme(wurzel) == vorher
    assert not (tmp_path / "Probe").exists()           # auch keine Kopie von config/


def test_settings_without_a_ledger_or_a_page_file_there_is_nothing_to_compare(tmp_path):
    ohne_db = _settings_ordner(tmp_path / "a")
    assert not umstellen.planen(ohne_db / "config").fehler
    # Nach der Umstellung gibt es keine Seitendatei mehr: alte Zeilen in der Tabelle stoeren nicht.
    mit_db = _settings_ordner(tmp_path / "b")
    _tabelle(mit_db, *GLEICH, ("floor_cents:alt", "1"))
    (mit_db / "config" / "settings_custom.yaml").unlink()
    assert not umstellen.planen(mit_db / "config").fehler
    # Und eine Zeile nur in der Datei ist kein Fund.
    nur_datei = _settings_ordner(tmp_path / "c")
    _tabelle(nur_datei, ("teilzeit_ab", "2040-01"))
    assert not umstellen.planen(nur_datei / "config").fehler


def test_settings_a_value_that_differs_only_because_the_file_is_newer_does_not_stop_the_run(
        tmp_path):
    wurzel = _settings_ordner(tmp_path)
    db = _tabelle(wurzel, *(z if z[0] != "floor_cents:giro" else (z[0], "80000") for z in GLEICH))
    plan = umstellen.planen(wurzel / "config")
    assert not plan.fehler
    assert any("`floor_cents:giro`: 80000, in settings_custom.yaml 90000" in h
               and "Datei ist neuer" in h for h in plan.tabelle_hinweise)
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert sicherung is not None and not plan.fehler
    assert "Datei gilt: Tabelle settings, Zeile `floor_cents:giro`" in bericht.read_text(
        encoding="utf-8")
    # Es gilt der Wert der Datei.
    gelesen = yaml.safe_load((wurzel / "config" / "forecast.yaml").read_text(encoding="utf-8"))
    assert gelesen["account_roles"]["giro"]["floor_cents"] == 90_000
    assert _tabellen(db) == set()


def test_settings_a_row_missing_in_the_file_stops_the_run_even_when_the_file_is_newer(tmp_path):
    wurzel = _settings_ordner(tmp_path)
    _tabelle(wurzel, *GLEICH, ("floor_cents:alt", "1234"))
    plan = umstellen.planen(wurzel / "config")
    assert any("`floor_cents:alt`" in f for f in plan.fehler)


def test_settings_a_note_the_file_carries_does_not_stop_the_run(tmp_path):
    wurzel = _settings_ordner(tmp_path)
    # EINSTELLUNGEN traegt "Ab dort kuerzer." in der Notiz von `teilzeit_ab`.
    _tabelle(wurzel, *GLEICH[:-1], ("teilzeit_ab", "2040-01", "Ab dort  kuerzer."))
    assert not umstellen.planen(wurzel / "config").fehler
    # Eine andere Notiz haelt den Lauf an, bis sie in die Datei uebernommen ist.
    anders = _settings_ordner(tmp_path / "anders")
    _tabelle(anders, *GLEICH[:-1], ("teilzeit_ab", "2040-01", "Nur hier begruendet."))
    assert umstellen.planen(anders / "config").fehler
    seite = anders / "config" / "settings_custom.yaml"
    daten = yaml.safe_load(seite.read_text(encoding="utf-8"))
    daten["notizen"]["einstellungen.teilzeit_ab"]["notiz"] += "\nNur hier begruendet."
    seite.write_text(yaml_text(daten), encoding="utf-8")
    assert not umstellen.planen(anders / "config").fehler


def test_settings_after_a_run_the_table_is_gone_from_the_database(tmp_path):
    wurzel = _settings_ordner(tmp_path)
    db = _tabelle(wurzel, *GLEICH)
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert sicherung is not None and plan.tabelle_entfernt
    assert _tabellen(db) == set()
    assert "Die Tabelle ist aus der Datenbank entfernt." in bericht.read_text(encoding="utf-8")
    # Der Rest der Datenbank ist noch da.
    c = sqlite3.connect(db)
    try:
        assert c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0
    finally:
        c.close()


def test_settings_a_stopped_run_and_the_probe_leave_the_table_alone(tmp_path):
    wurzel = _settings_ordner(tmp_path)
    db = _tabelle(wurzel, *GLEICH, ("floor_cents:alt", "1234"))
    umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert _tabellen(db) == {"settings"}
    ok = _settings_ordner(tmp_path / "ok")
    db = _tabelle(ok, *GLEICH)
    plan, bericht = umstellen.probieren(ok, tmp_path / "Probe", heute=HEUTE)
    assert bericht is not None and not plan.tabelle_entfernt
    assert _tabellen(db) == {"settings"}
    assert "würde beim Umstellen" in bericht.read_text(encoding="utf-8")


def test_settings_discarding_lets_the_run_through_and_names_what_goes(tmp_path):
    wurzel = _settings_ordner(tmp_path)
    db = _tabelle(wurzel, *GLEICH[:-1], ("teilzeit_ab", "2040-01", "Nur hier begruendet."),
                  ("floor_cents:alt", "1234"))
    plan, sicherung, _ = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert sicherung is None and plan.fehler                       # ohne Wunsch: anhalten
    plan, sicherung, bericht = umstellen.ausfuehren(wurzel, heute=HEUTE, tabelle_verwerfen=True)
    assert sicherung is not None and not plan.fehler
    text = bericht.read_text(encoding="utf-8")
    assert "Verworfen (auf Wunsch): Tabelle settings, Zeile `floor_cents:alt` = 1234" in text
    assert "Nur hier begruendet." in text
    assert _tabellen(db) == set()


def test_settings_without_a_page_file_the_table_is_not_touched(tmp_path):
    """Kein Abgleich, also auch kein Entfernen: Zeilen ohne Vergleich werden nie verworfen."""
    wurzel = _settings_ordner(tmp_path, **{"abos.yaml": "abos:\n  # Kommentar\n  - id: a\n"})
    db = _tabelle(wurzel, *GLEICH, ("floor_cents:alt", "1"))
    (wurzel / "config" / "settings_custom.yaml").unlink()
    plan, sicherung, _ = umstellen.ausfuehren(wurzel, heute=HEUTE)
    assert sicherung is not None and not plan.tabelle_geprueft and not plan.tabelle_entfernt
    assert _tabellen(db) == {"settings"}


def test_settings_a_fresh_ledger_has_no_settings_table(tmp_path):
    db = init_db(tmp_path / "neu.db")
    assert _tabellen(db) == set()


def test_settings_the_command_names_the_way_out_and_discards_on_request(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from finctl import cli

    wurzel = _settings_ordner(tmp_path)
    db = _tabelle(wurzel, *GLEICH, ("floor_cents:alt", "1234"))
    monkeypatch.setattr(cli, "CONFIG_DIR", wurzel / "config")
    lauf = CliRunner().invoke(cli.app, ["umstellen", "--probe", str(tmp_path / "Probe")])
    assert lauf.exit_code == 1, lauf.output
    assert "floor_cents:alt" in lauf.output and "--tabelle-verwerfen" in lauf.output
    assert "keine Kopie geschrieben" in lauf.output and not (tmp_path / "Probe").exists()
    lauf = CliRunner().invoke(cli.app, ["umstellen", "--tabelle-verwerfen"])
    assert lauf.exit_code == 0, lauf.output
    assert "Verworfen: Tabelle settings, Zeile `floor_cents:alt`" in lauf.output
    assert "Die Tabelle settings ist aus der Datenbank entfernt." in lauf.output
    assert _tabellen(db) == set()
