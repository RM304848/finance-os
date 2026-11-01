"""Wer plant: Geburtstag, Krankenversicherung, Rentenalter.

Alle Personen hier sind erfunden.
"""

from __future__ import annotations

from datetime import date

import pytest
import yaml

from finctl import person

BASIS = """person:
  birth_date: 1980-07-15
  krankenversicherung: gesetzlich
schwellen:
  grv_ab_alter: 67
notizen:
  person.birth_date:
    notiz: Die Herleitung, die kein Klick loeschen darf.
    notiz_vom: 2026-02-01
"""


def _config(tmp_path):
    (tmp_path / "lebensplan.yaml").write_text(BASIS, encoding="utf-8")
    return tmp_path


def test_the_pension_starts_the_month_after_the_birthday(tmp_path):
    assert person.rentenbeginn(_config(tmp_path)) == date(2047, 8, 1)


def test_only_the_privately_insured_have_a_deadline(tmp_path):
    """§6 Abs. 3a SGB V gilt nur fuer den Weg zurueck in die GKV."""
    cfg = _config(tmp_path)
    assert person.pkv_stichtag(cfg) is None
    person.setzen({"krankenversicherung": "privat"}, cfg)
    assert person.pkv_sperre(cfg) == date(2035, 7, 15)
    assert person.pkv_stichtag(cfg) == date(2034, 7, 15)


def test_the_deadline_follows_the_birthday(tmp_path):
    """Dynamisch: ein anderes Geburtsdatum, eine andere Frist."""
    cfg = _config(tmp_path)
    person.setzen({"krankenversicherung": "privat", "geburtsdatum": "1990-03-01"}, cfg)
    assert person.pkv_stichtag(cfg) == date(2044, 3, 1)


def test_the_setup_writes_the_one_file_whole_and_keeps_its_notes(tmp_path):
    cfg = _config(tmp_path)
    person.setzen({"geburtsdatum": "1981-08-16", "krankenversicherung": "privat",
                   "rente_ab_alter": "65"}, cfg)
    roh = yaml.safe_load((cfg / "lebensplan.yaml").read_text(encoding="utf-8"))
    assert roh["person"] == {"birth_date": date(1981, 8, 16), "krankenversicherung": "privat"}
    assert roh["schwellen"] == {"grv_ab_alter": 65}
    assert roh["notizen"]["person.birth_date"]["notiz"].startswith("Die Herleitung")
    assert person.angaben(cfg) == {"geburtsdatum": date(1981, 8, 16),
                                   "krankenversicherung": "privat", "rente_ab_alter": 65}
    assert not (cfg / "lebensplan_custom.yaml").exists()


def test_saving_without_a_change_writes_no_byte_even_for_a_date_written_as_text(tmp_path):
    cfg = _config(tmp_path)
    datei = cfg / "lebensplan.yaml"
    vorher = datei.read_text(encoding="utf-8")
    person.setzen({"geburtsdatum": "1980-07-15", "krankenversicherung": "gesetzlich",
                   "rente_ab_alter": "67"}, cfg)
    assert datei.read_text(encoding="utf-8") == vorher
    datei.write_text(vorher.replace("1980-07-15", "'1980-07-15'"), encoding="utf-8")
    vorher = datei.read_text(encoding="utf-8")
    person.setzen({"geburtsdatum": "1980-07-15"}, cfg)
    assert datei.read_text(encoding="utf-8") == vorher


def test_an_empty_value_takes_the_angabe_out_of_the_file(tmp_path):
    cfg = _config(tmp_path)
    person.setzen({"krankenversicherung": "", "geburtsdatum": ""}, cfg)
    roh = yaml.safe_load((cfg / "lebensplan.yaml").read_text(encoding="utf-8"))
    assert roh["person"] == {}
    assert person.angaben(cfg) == {"geburtsdatum": None, "krankenversicherung": "",
                                   "rente_ab_alter": 67}


def test_a_folder_without_the_file_gets_none_from_saving_nothing(tmp_path):
    person.setzen({}, tmp_path)
    assert not (tmp_path / "lebensplan.yaml").exists()


def test_without_a_birthday_nothing_is_dated(tmp_path):
    (tmp_path / "lebensplan.yaml").write_text("person: {}\n", encoding="utf-8")
    assert person.rentenbeginn(tmp_path) is None
    assert person.pkv_stichtag(tmp_path) is None


@pytest.mark.parametrize("felder", [{"geburtsdatum": "2999-01-01"},
                                    {"krankenversicherung": "beides"},
                                    {"rente_ab_alter": "30"}])
def test_wrong_input_is_refused(tmp_path, felder):
    with pytest.raises(ValueError):
        person.setzen(felder, _config(tmp_path))
