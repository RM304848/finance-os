"""Wohin gesichert wird, fragt die App -- sie raet es nicht.

Hier stand ein fester Pfad in die Cloud des Autors. Auf einem fremden Rechner
waere das ein Ordner, den niemand kennt; auf Windows ein sinnloses
`C:\\Users\\...\\Library\\CloudStorage\\...`. Das Schlimme daran ist nicht der
Pfad, sondern dass die Sicherung SCHEINBAR liefe.

Geprueft wird deshalb beides: dass ohne Ziel nichts geschrieben wird, und dass
ein eingetragenes Ziel vor dem Speichern wirklich beschrieben wurde.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from finctl import ops


def test_an_unwritable_target_is_refused_before_it_is_saved(tmp_path):
    """Durch SCHREIBEN geprueft, nicht durch Nachdenken ueber Rechte.

    Ein Cloud-Ordner, der gerade nicht eingehaengt ist, sieht vorhanden aus
    und nimmt trotzdem nichts an. `os.access` sagt dazu das Falsche.
    """
    if os.name == "nt":
        pytest.skip("chmod setzt unter Windows kein Schreibverbot; geprueft auf macOS")
    gesperrt = tmp_path / "gesperrt"
    gesperrt.mkdir()
    gesperrt.chmod(0o500)                      # lesen ja, schreiben nein
    try:
        assert ops.ziel_pruefen(gesperrt)      # nicht leer = Grund genannt
    finally:
        gesperrt.chmod(0o700)


def test_a_relative_target_is_refused(tmp_path):
    """Ein relativer Pfad haengt am Arbeitsverzeichnis und zeigt nach dem
    naechsten Start woanders hin -- die Sicherung waere dann verstreut."""
    assert "vollstaendiger Pfad" in ops.ziel_pruefen("backups")


def test_a_writable_target_passes(tmp_path):
    assert ops.ziel_pruefen(tmp_path / "neu") == ""
    assert (tmp_path / "neu").is_dir()         # wird angelegt, nicht verlangt


def test_the_status_says_what_is_missing_instead_of_failing(tmp_path, monkeypatch):
    """Eine frische Installation hat kein Ziel. Das ist kein Fehler."""
    monkeypatch.setattr(ops, "CONFIG_DIR", tmp_path)

    stand = ops.sicherungsstand()
    assert stand["ziel"] is None
    assert not stand["erreichbar"]
    assert "backup.yaml" in stand["grund"]     # sagt, WO einzutragen ist


def test_the_target_is_written_into_the_one_file_with_its_notes(tmp_path, monkeypatch):
    """backup.yaml traegt Ziel und Anzahl und die Notiz, warum zwoelf Staende bleiben. Die Seite
    schreibt die Datei ganz, und die Notiz bleibt."""
    import yaml

    monkeypatch.setattr(ops, "CONFIG_DIR", tmp_path)
    datei = tmp_path / "backup.yaml"
    datei.write_text("directory: ~/alt\nkeep: 12\nnotizen:\n  keep:\n"
                     "    notiz: Die Begruendung, die bleiben muss.\n", encoding="utf-8")

    ops.backup_setzen({"directory": str(tmp_path / "neu"), "keep": 3})

    roh = yaml.safe_load(datei.read_text(encoding="utf-8"))
    assert roh["directory"] == str(tmp_path / "neu") and roh["keep"] == 3
    assert roh["notizen"]["keep"]["notiz"] == "Die Begruendung, die bleiben muss."
    ziel, anzahl = ops.backup_settings()
    assert ziel == tmp_path / "neu" and anzahl == 3
    assert not (tmp_path / "backup_custom.yaml").exists()


def test_saving_the_same_target_again_writes_no_byte(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "CONFIG_DIR", tmp_path)
    datei = tmp_path / "backup.yaml"
    ops.backup_setzen({"directory": str(tmp_path / "ziel"), "keep": 5})
    vorher = datei.read_bytes()
    ops.backup_setzen({"directory": str(tmp_path / "ziel"), "keep": 5})
    assert datei.read_bytes() == vorher


def test_the_expanded_path_of_a_tilde_target_is_no_change(tmp_path, monkeypatch):
    """Die Seite zeigt das Ziel ausgeschrieben; Speichern ohne Aenderung schickt es zurueck."""
    monkeypatch.setattr(ops, "CONFIG_DIR", tmp_path)
    datei = tmp_path / "backup.yaml"
    datei.write_text("directory: ~/finctl-sicherung\nkeep: 12\n", encoding="utf-8")
    vorher = datei.read_bytes()
    ausgeschrieben = str(Path("~/finctl-sicherung").expanduser())
    ops.backup_setzen({"directory": ausgeschrieben, "keep": 12})
    assert datei.read_bytes() == vorher
    ops.backup_setzen({"directory": str(tmp_path / "anders"), "keep": 12})
    assert str(tmp_path / "anders") in datei.read_text(encoding="utf-8")


def test_an_empty_value_takes_the_angabe_out_and_a_missing_file_stays_missing(
        tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "CONFIG_DIR", tmp_path)
    ops.backup_setzen({})
    assert not (tmp_path / "backup.yaml").exists()
    ops.backup_setzen({"directory": str(tmp_path / "ziel"), "keep": 5})
    ops.backup_setzen({"keep": ""})
    assert "keep" not in (tmp_path / "backup.yaml").read_text(encoding="utf-8")
    assert ops.backup_settings()[1] == ops.STAENDE


@pytest.mark.parametrize("koerper,teil", [
    ({}, "Kein Ordner"),
    ({"directory": "relativ"}, "vollstaendiger Pfad"),
])
def test_the_api_refuses_what_it_cannot_write_to(koerper, teil):
    from starlette.testclient import TestClient

    from finctl.web.server import app

    with TestClient(app) as client:
        res = client.post("/api/backup/ziel", json=koerper)
    assert res.status_code == 400
    assert teil in res.json()["error"]
