"""Wo ein `*_custom.yaml`-Name im Code stehen darf.

Schritt 5 (`docs/schritt5_notizen.md`) hat jedes Paar aus Basisdatei und `*_custom.yaml` zu
einer Datei unter dem Namen der Basisdatei zusammengelegt. Ein `_custom`-Name im Code sagt
seither nur noch eins von zwei Dingen:

* Er steht in einem der `finctl/umstellen*.py`: Der Umwandler erkennt die alten Dateien.
* Er gehoert einer Datei, die es nur als `_custom` gibt und die ihren Namen behaelt
  (Entscheidung 5). Die Dateinamen raeumt Schritt 8 in einem Zug auf.

Alles andere ist ein Rest des Paars: ein Docstring, der die zweite Datei als heutigen Ort
nennt, oder ein Leser, der sie noch kennt.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from finctl import umstellen_paare

WURZEL = Path(__file__).resolve().parent.parent
CODE = WURZEL / "finctl"

# Die Dateien, die es nur als `_custom` gibt. Die Liste darf kuerzer werden -- Schritt 8
# benennt sie um -- und nichts dazubekommen: Eine neue Datei, die eine Seite schreibt,
# bekommt ihren Namen ohne `_custom` (oder ist ein Paar, und dann steht es im Umwandler).
#
# Warum die Namen mitstehen: faellt einer aus dem Code, verlangt der Test, ihn hier
# auszutragen.
OHNE_BASIS = {
    "csv_profile_custom": "Selbst zugeordnete CSV-Exporte (ingest/zuordnung.py)",
    "geteilt_custom": "Projekte, Personen und geteilte Buchungen (geteilt.py)",
    "module_custom": "Welche Module eingeschaltet sind (module.py)",
    "prognosebasis_custom": "Was unter Fortschreibung abgewaehlt ist (forecast/prognosebasis.py)",
    "reihen_custom": "Was der Haushalt ueber Reihen festlegt (reihen.py)",
    "zinssaetze_custom": "Die datierten Zinssaetze je Konto (zinssaetze.py)",
}

_NAME = re.compile(r"(?<![A-Za-z0-9_])([a-z][a-z0-9]*(?:_[a-z0-9]+)*_custom)(?![A-Za-z0-9_])")
_ENDUNGEN = {".py", ".html", ".sql", ".md", ".yaml", ".txt"}


def _umwandler(pfad: Path) -> bool:
    return pfad.parent == CODE and pfad.name.startswith("umstellen")


def _dateien() -> list[Path]:
    return sorted(p for p in CODE.rglob("*")
                  if p.is_file() and p.suffix in _ENDUNGEN and "__pycache__" not in p.parts
                  and not _umwandler(p))


def _fundstellen() -> dict[str, list[str]]:
    """Welcher `_custom`-Name steht wo (ohne den Umwandler)."""
    gefunden: dict[str, list[str]] = {}
    for pfad in _dateien():
        text = pfad.read_text(encoding="utf-8")
        for zeilennr, zeile in enumerate(text.splitlines(), 1):
            for name in _NAME.findall(zeile):
                gefunden.setdefault(name, []).append(f"{pfad.relative_to(WURZEL)}:{zeilennr}")
    return gefunden


def test_no_custom_name_stands_in_the_code_but_the_files_without_a_base():
    fremd = {name: orte for name, orte in _fundstellen().items() if name not in OHNE_BASIS}
    assert not fremd, (
        "Diese `_custom`-Namen gehoeren einem Paar, das zusammengelegt ist. Der Name der "
        "Datei ist der der Basisdatei; wer die alte Datei erkennen will, tut es im Umwandler:\n  "
        + "\n  ".join(f"{name}: {', '.join(orte[:4])}" for name, orte in sorted(fremd.items())))


@pytest.mark.parametrize("name", sorted(OHNE_BASIS))
def test_a_name_that_no_longer_stands_in_the_code_leaves_the_list(name):
    assert name in _fundstellen(), (
        f"{name} steht nirgends mehr im Code (ohne den Umwandler): aus OHNE_BASIS austragen.")


@pytest.mark.parametrize("name", sorted(OHNE_BASIS))
def test_a_file_without_a_base_has_none(name):
    """Keine Basisdatei im Code, in den Startvorlagen und im Musterhaushalt, und kein Paar."""
    basis = name.removesuffix("_custom") + ".yaml"
    namen = {n for paar in umstellen_paare.PAARE for n in (paar.basis, paar.seite)}
    assert name + ".yaml" not in namen and basis not in namen, (
        f"{name}.yaml ist im Umwandler ein Paar: dann hat sie eine Basis.")
    assert not (CODE / "vorgaben" / basis).exists()
    assert not (WURZEL / "tests" / "musterhaushalt" / "config" / basis).exists()
    nennt = [str(p.relative_to(WURZEL)) for p in _dateien()
             if re.search(r"(?<![A-Za-z0-9_])" + re.escape(basis) + r"(?![A-Za-z0-9_])",
                          p.read_text(encoding="utf-8"))]
    assert not nennt, f"{basis} steht im Code: {nennt}. Dann hat {name} eine Basis."
