"""Jede Datei einmal lesen: `yaml_lesen` und der Zwischenspeicher dahinter.

Die Dateien hier sind erfunden. Ihre Dateizeit steht in der Vergangenheit, denn
eine Datei, die gerade erst geaendert wurde, kommt mit Absicht nicht in den
Speicher (`dateien.FRIST_NS`).
"""

from __future__ import annotations

import builtins
import io
import os
import time
from collections import Counter
from pathlib import Path

import pytest

pytest.importorskip("httpx")

from finctl import dateien
from finctl.dateien import schreiben_wenn_geaendert, yaml_lesen

ALT = 10 * 24 * 3600  # Sekunden: weit ausserhalb der Frist


def _datei(pfad: Path, text: str, *, alt: bool = True) -> Path:
    pfad.write_text(text, encoding="utf-8")
    if alt:
        _altern(pfad)
    return pfad


def _altern(pfad: Path) -> None:
    jetzt = time.time()
    os.utime(pfad, (jetzt - ALT, jetzt - ALT))


@pytest.fixture(autouse=True)
def leerer_speicher():
    dateien._SPEICHER.clear()
    yield
    dateien._SPEICHER.clear()


@pytest.fixture
def lesevorgaenge(monkeypatch):
    """Zaehlt, wie oft je YAML-Datei zum Lesen geoeffnet wird."""
    gezaehlt: Counter[str] = Counter()
    echt = builtins.open

    def zaehlend(datei, *args, **kwargs):
        modus = args[0] if args else kwargs.get("mode", "r")
        if "r" in modus and str(datei).endswith((".yaml", ".yml")):
            gezaehlt[str(datei)] += 1
        return echt(datei, *args, **kwargs)

    # `Path.read_text` oeffnet ueber `io.open`, `open` ist dasselbe Ding unter
    # einem zweiten Namen: beide Wege zaehlen.
    monkeypatch.setattr(builtins, "open", zaehlend)
    monkeypatch.setattr(io, "open", zaehlend)
    return gezaehlt


def test_liest_den_inhalt(tmp_path):
    pfad = _datei(tmp_path / "a.yaml", "eins: 1\nzwei: [a, b]\n")
    assert yaml_lesen(pfad) == {"eins": 1, "zwei": ["a", "b"]}
    assert yaml_lesen(str(pfad)) == {"eins": 1, "zwei": ["a", "b"]}


def test_eine_leere_datei_ist_none_wie_bei_safe_load(tmp_path):
    assert yaml_lesen(_datei(tmp_path / "leer.yaml", "")) is None


def test_eine_unveraenderte_datei_wird_einmal_gelesen(tmp_path, lesevorgaenge):
    pfad = _datei(tmp_path / "a.yaml", "x: 1\n")
    for _ in range(5):
        assert yaml_lesen(pfad) == {"x": 1}
    assert lesevorgaenge[str(pfad)] == 1


def test_eine_geaenderte_datei_wird_neu_gelesen(tmp_path):
    pfad = _datei(tmp_path / "a.yaml", "x: 1\n")
    assert yaml_lesen(pfad) == {"x": 1}
    # Gleiche Laenge, andere Zeit: nur die Dateizeit unterscheidet.
    _datei(pfad, "x: 2\n", alt=False)
    jetzt = time.time()
    os.utime(pfad, (jetzt - ALT + 60, jetzt - ALT + 60))
    assert yaml_lesen(pfad) == {"x": 2}
    # Gleiche Zeit, andere Laenge: nur die Groesse unterscheidet.
    stand = pfad.stat().st_mtime_ns
    pfad.write_text("x: 22\n", encoding="utf-8")
    os.utime(pfad, ns=(stand, stand))
    assert yaml_lesen(pfad) == {"x": 22}


def test_schreiben_wenn_geaendert_laesst_den_naechsten_aufruf_neu_lesen(tmp_path):
    pfad = _datei(tmp_path / "a.yaml", "x: 1\n")
    assert yaml_lesen(pfad) == {"x": 1}
    assert schreiben_wenn_geaendert(pfad, "x: 2\n") is True
    assert yaml_lesen(pfad) == {"x": 2}


def test_schreiben_ohne_aenderung_laesst_den_speicher_stehen(tmp_path, lesevorgaenge):
    pfad = _datei(tmp_path / "a.yaml", "x: 1\n")
    assert yaml_lesen(pfad) == {"x": 1}
    gelesen = lesevorgaenge[str(pfad)]
    assert schreiben_wenn_geaendert(pfad, "# anderer Kopf\nx: 1\n") is False
    assert yaml_lesen(pfad) == {"x": 1}
    # `gleicher_inhalt` vergleicht aus der Datei selbst, einmal; gelesen wird
    # sonst nichts, und der Speicher bleibt.
    assert lesevorgaenge[str(pfad)] == gelesen + 1


def test_zurueck_kommt_eine_kopie(tmp_path):
    pfad = _datei(tmp_path / "a.yaml", "liste: [1, 2]\nkarte: {a: {b: 1}}\n")
    erste = yaml_lesen(pfad)
    erste["liste"].append(3)
    erste["karte"]["a"]["b"] = 99
    erste["neu"] = True
    assert yaml_lesen(pfad) == {"liste": [1, 2], "karte": {"a": {"b": 1}}}


def test_auch_die_erste_antwort_ist_eine_kopie(tmp_path):
    pfad = _datei(tmp_path / "a.yaml", "liste: [1]\n")
    yaml_lesen(pfad)["liste"].append(2)
    assert yaml_lesen(pfad) == {"liste": [1]}


def test_eine_juengst_geaenderte_datei_kommt_nicht_in_den_speicher(tmp_path):
    """Zwei Schreibvorgaenge gleicher Laenge kurz hintereinander sehen sich
    gleich, wenn die Dateizeit grob ist; deshalb zaehlt erst Altes."""
    pfad = _datei(tmp_path / "a.yaml", "x: 1\n", alt=False)
    assert yaml_lesen(pfad) == {"x": 1}
    stand = pfad.stat().st_mtime_ns
    pfad.write_text("x: 2\n", encoding="utf-8")
    os.utime(pfad, ns=(stand, stand))  # dieselbe Zeit, dieselbe Groesse
    assert yaml_lesen(pfad) == {"x": 2}
    assert os.path.abspath(pfad) not in dateien._SPEICHER


def test_eine_fehlende_datei_wirft_wie_read_text(tmp_path):
    with pytest.raises(FileNotFoundError):
        yaml_lesen(tmp_path / "gibt_es_nicht.yaml")


def test_ein_fehler_im_yaml_wird_nicht_gemerkt(tmp_path):
    import yaml

    pfad = _datei(tmp_path / "kaputt.yaml", "x: [1, 2\n")
    for _ in range(2):
        with pytest.raises(yaml.YAMLError):
            yaml_lesen(pfad)
    _datei(pfad, "x: [1, 2]\n")
    assert yaml_lesen(pfad) == {"x": [1, 2]}


def test_der_schluessel_ist_der_absolute_pfad(tmp_path, monkeypatch, lesevorgaenge):
    """Die Suite laeuft in Kopien der Daten: Ein relativer Pfad darf nicht
    zwischen zwei Arbeitsverzeichnissen dieselbe Datei meinen."""
    for name in ("eins", "zwei"):
        (tmp_path / name).mkdir()
        _datei(tmp_path / name / "a.yaml", f"wer: {name}\n")
    monkeypatch.chdir(tmp_path / "eins")
    assert yaml_lesen("a.yaml") == {"wer": "eins"}
    monkeypatch.chdir(tmp_path / "zwei")
    assert yaml_lesen("a.yaml") == {"wer": "zwei"}
    assert yaml_lesen(tmp_path / "zwei" / "a.yaml") == {"wer": "zwei"}
    assert sum(lesevorgaenge.values()) == 2


# ----------------------------------------------------------------- die Seiten


@pytest.mark.parametrize("seite", ["/konten", "/monatsabschluss"])
def test_eine_seite_liest_jede_datei_hoechstens_einmal(seite, lesevorgaenge):
    """Vorher oeffnete `/konten` rund 280 Mal eine YAML-Datei, `/monatsabschluss`
    rund 360 Mal, aus 13 und 21 Dateien: je Konto neu."""
    from fastapi.testclient import TestClient

    from finctl.pfade import CONFIG_DIR
    from finctl.web.server import app

    if not Path("data/finance.db").exists():
        pytest.skip("kein Hauptbuch")
    for pfad in CONFIG_DIR.glob("*.yaml"):  # eine Kopie: siehe tests/conftest.py
        _altern(pfad)
    antwort = TestClient(app).get(seite)
    assert antwort.status_code == 200
    mehrfach = {Path(p).name: n for p, n in lesevorgaenge.items() if n > 1}
    assert not mehrfach, f"{seite} liest mehrfach: {mehrfach}"
    assert lesevorgaenge, "die Zaehlung sieht nichts: Sperre pruefen"
