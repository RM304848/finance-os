"""Was ins Paket muss -- gebaut und nachgezaehlt, nicht gelesen.

Am 25.09.2026 gemessen: ein Rad aus diesem Projekt enthielt genau EINE
Nicht-Python-Datei, `schema.sql`. Keine der vierzig Vorlagen, keine der sieben
Startdateien, kein Handbuch. Eine installierte App waere auf jeder Seite mit
`TemplateNotFound` abgestuerzt, `init` haette keine Startdateien angelegt, und
das Handbuch waere leer geblieben.

In `pyproject.toml` stand nichts Falsches -- es stand nur nichts da. Genau
deshalb prueft dieser Test das ERGEBNIS und nicht die Deklaration: Wer einen
Ordner mit Vorlagen dazunimmt und die Zeile vergisst, merkt es sonst erst,
wenn jemand anders die App installiert.

Der Bau dauert ein paar Sekunden. Das ist der Preis dafuer, dass die Frage
"ist das Paket vollstaendig" eine Antwort hat statt einer Vermutung.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent

#: Was zur Laufzeit gebraucht wird, und wo es im Quellbaum liegt.
MITZULIEFERN = {
    "Vorlagen": ("finctl/web/templates", "*.html"),
    "Startdateien": ("finctl/vorgaben", "*.yaml"),
    "Schema": ("finctl/ledger", "*.sql"),
}


# Ein Rad fuer alle drei Tests, in EINEM Prozess: parallel gebaut stiessen
# sich drei Laeufe am selben `build/` im Projekt.
pytestmark = pytest.mark.xdist_group("paket")


@pytest.fixture(scope="module")
def rad(tmp_path_factory) -> list[str]:
    """Die Dateiliste eines frisch gebauten Rads."""
    try:
        import build  # noqa: F401
    except ImportError:
        pytest.skip("`build` nicht installiert")

    ziel = tmp_path_factory.mktemp("rad")
    # Gebaut wird in einer Kopie, nicht im Projekt: setuptools legt `build/` und
    # `finctl.egg-info` dort an, wo es baut. Im Projekt fand ruff danach eine
    # zweite Kopie jeder Datei, und neben einer Installation mit `pip install -e`
    # (GitHub Actions) stiess der Bau auf deren `egg-info` und brach ab.
    quelle = tmp_path_factory.mktemp("quelle")
    for name in ("pyproject.toml", "README.md", "LICENSE.md", "HANDBUCH.md"):
        if (WURZEL / name).exists():
            shutil.copy2(WURZEL / name, quelle / name)
    shutil.copytree(WURZEL / "finctl", quelle / "finctl",
                    ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    fertig = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(ziel)],
        cwd=quelle, capture_output=True, text=True, check=False)
    assert fertig.returncode == 0, fertig.stderr[-2000:]

    [datei] = sorted(ziel.glob("*.whl"))
    with zipfile.ZipFile(datei) as z:
        return z.namelist()


def test_the_wheel_carries_every_file_the_app_reads_at_runtime(rad):
    """Jede einzelne Datei, nicht nur eine je Ordner.

    Eine Stichprobe haette genuegt, um den Fehler von damals zu finden -- aber
    nicht den naechsten: ein Rad, das neunundreissig von vierzig Vorlagen
    enthaelt, stuerzt auf genau einer Seite ab.
    """
    fehlt = []
    for was, (ordner, muster) in MITZULIEFERN.items():
        quellen = sorted((WURZEL / ordner).glob(muster))
        assert quellen, f"{was}: im Quellbaum ist nichts zu finden"
        for quelle in quellen:
            pfad = quelle.relative_to(WURZEL).as_posix()
            if pfad not in rad:
                fehlt.append(f"{was}: {pfad}")
    assert not fehlt, (
        "Diese Dateien landen NICHT im Paket:\n  " + "\n  ".join(fehlt)
        + "\n\nIn pyproject.toml unter `[tool.setuptools.package-data]` "
          "eintragen -- ein Paket nimmt nur mit, was dort steht.")


def test_the_wheel_carries_the_handbook(rad):
    """Ohne Handbuch zeigt jede Fusszeile der App ins Leere."""
    assert "finctl/HANDBUCH.md" in rad


def test_the_shipped_handbook_is_the_one_that_is_maintained():
    """Zwei Orte, eine Datei.

    Im Repository liegt das Handbuch an der Wurzel, wo man es bearbeitet; ein
    Rad nimmt aber nur mit, was INNERHALB eines Pakets liegt. Die Kopie unter
    `finctl/` ist deshalb noetig -- und ohne diesen Test waere sie nach der
    ersten Aenderung eine zweite, falsche Wahrheit.
    """
    wurzel = (WURZEL / "HANDBUCH.md").read_bytes()
    paket = (WURZEL / "finctl" / "HANDBUCH.md").read_bytes()
    assert wurzel == paket, (
        "Die Kopie im Paket ist nicht mehr die gepflegte Fassung.\n"
        "  cp HANDBUCH.md finctl/HANDBUCH.md")


def test_the_wheel_carries_the_glossary(rad):
    """Ohne Glossar hat keine Vorlage Begriffe, und die Seite /vorlagen stuerzt ab."""
    assert "finctl/CONTEXT.md" in rad


def test_the_shipped_glossary_is_the_one_that_is_maintained():
    """Zwei Orte, eine Datei -- wie das Handbuch."""
    wurzel = (WURZEL / "CONTEXT.md").read_bytes()
    paket = (WURZEL / "finctl" / "CONTEXT.md").read_bytes()
    assert wurzel == paket, (
        "Die Kopie im Paket ist nicht mehr die gepflegte Fassung.\n"
        "  cp CONTEXT.md finctl/CONTEXT.md")


def test_the_entry_point_is_declared(rad):
    """Ohne Eintragspunkt gibt es nach der Installation kein `finctl`."""
    [eintraege] = [n for n in rad if n.endswith(".dist-info/entry_points.txt")]
    assert eintraege


def test_the_wheel_carries_the_mcp_command(rad):
    """`finctl mcp` laeuft im Rad wie im Paket: eigene Module, keine zusaetzliche Bibliothek."""
    for name in ("__init__", "protokoll", "werkzeuge"):
        assert f"finctl/mcp/{name}.py" in rad


def test_the_mcp_command_brings_no_dependency_and_the_bundle_collects_it():
    """Das Protokoll ist JSON ueber stdio. Der Bau nimmt `finctl.mcp` ueber `collect_submodules`."""
    import ast
    import sys

    erlaubt = set(sys.stdlib_module_names) | {"finctl", "__future__"}
    fremd = []
    for datei in sorted((WURZEL / "finctl" / "mcp").glob("*.py")):
        for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            module = ([a.name for a in knoten.names] if isinstance(knoten, ast.Import)
                      else [knoten.module or ""] if isinstance(knoten, ast.ImportFrom)
                      and not knoten.level else [])
            fremd += [f"{datei.name}: {m}" for m in module if m.split(".")[0] not in erlaubt]
    assert not fremd, fremd
    spec = (WURZEL / "werkzeuge" / "paket" / "finance_os.spec").read_text(encoding="utf-8")
    assert 'collect_submodules("finctl")' in spec
