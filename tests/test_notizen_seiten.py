"""Die Seiten, die einen Eintrag ueber eine Route schreiben, behalten seine Notiz.

Ergaenzt `tests/test_notizen_eintraege.py` um die Eintragsarten, die nur die Oberflaeche
schreibt: Bestaende und Verpflichtungen (`/api/bestand`, `/api/verpflichtung`), Ziele
(`/api/ziel`), Klammern (`/api/szenario`), den Anschluss eines Kredits und Renten
(`/api/rente`). Jeder Test lenkt die Module in einen Wegwerfordner mit erfundenen
Dateien; `config/` bleibt unberuehrt.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from finctl import bestaende, kontenregeln, kredite, module, objekte, renten, zinssaetze
from finctl.forecast import prognosebasis
from finctl.web.routen import konten as konten_seite
from finctl.web.routen import kredite as kredite_seite
from finctl.web.routen import planung as planung_seite
from finctl.web.routen import ziele as ziele_seite
from finctl.web.server import app

HEUTE = date.today().isoformat()
BEREICH = {"bereich": {"notiz": "Fuer die ganze Datei", "notiz_vom": "2026-01-01"}}
client = TestClient(app)


def _datei(pfad: Path, inhalt: dict) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(yaml.safe_dump(inhalt, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return pfad


def _gelesen(pfad: Path) -> dict:
    return yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}


@pytest.fixture
def config(tmp_path, monkeypatch) -> Path:
    ordner = tmp_path / "config"
    ordner.mkdir()
    for modul in (bestaende, kontenregeln, module, zinssaetze, prognosebasis, renten,
                  konten_seite, kredite_seite, ziele_seite, kredite, objekte):
        monkeypatch.setattr(modul, "CONFIG_DIR", ordner)
    monkeypatch.setattr(planung_seite, "SZENARIEN_PATH", ordner / "szenarien.yaml")
    return ordner


# ------------------------------------------------------------ Bestaende


def _bestaende(config: Path) -> Path:
    _datei(config / "balances.yaml", {
        "as_of": "2026-09-30",
        "balances": [
            {"name": "Depot A", "kind": "depot", "cents": 1_000_000, "note": "Alter Name"},
            {"name": "Depot B", "kind": "depot", "cents": 500_000,
             "notiz": "Neuer Name", "notiz_vom": "2026-02-01", "note": "Alter Name"}],
        "obligations": [{"name": "Darlehen X", "cents": 200_000, "note": "Alt"}]})
    return config / "balances.yaml"


def _stand(name: str) -> dict:
    from finctl.web.basis import conn

    c = conn()
    try:
        zeile = next(z for z in bestaende.zusammenfuehren(c, bestaende.lesen())["balances"]
                     if z["name"] == name)
    finally:
        c.close()
    return zeile


def _position(datei: Path, name: str) -> dict:
    return next(e for e in _gelesen(datei)["balances"] if e["name"] == name)


def test_a_position_shows_the_note_before_the_old_name(config):
    _bestaende(config)
    assert _stand("Depot A")["note"] == "Alter Name"
    b = _stand("Depot B")
    assert (b["note"], b["notiz"], b["notiz_vom"]) == ("Neuer Name", "Neuer Name", "2026-02-01")


def test_saving_a_position_keeps_its_note_its_date_and_the_block(config):
    datei = _bestaende(config)
    _datei(datei, {"as_of": "2026-09-30",
                   "balances": [{"name": "Depot A", "kind": "depot", "cents": 1_100_000,
                                 "as_of": "2026-09-30", "notiz": "Ohne Datum"}],
                   "notizen": BEREICH})
    assert client.post("/api/bestand", json={"key": "Depot A", "cents": 1_200_000,
                                             "as_of": "2026-10-01"}).json()["ok"]
    a = _position(datei, "Depot A")
    assert (a["notiz"], "notiz_vom" in a, a["cents"]) == ("Ohne Datum", False, 1_200_000)
    assert _gelesen(datei)["notizen"] == BEREICH

    # Derselbe Text: Der Eintrag bleibt, wie er ist.
    client.post("/api/bestand", json={"key": "Depot A", "note": "Ohne Datum"})
    client.post("/api/bestand", json={"key": "Depot A", "note": " Ohne Datum "})
    assert _position(datei, "Depot A") == a


def test_a_changed_position_note_gets_a_date_and_the_old_name_goes(config):
    datei = _bestaende(config)
    assert client.post("/api/bestand", json={"key": "Depot A", "note": "Neu"}).json()["ok"]
    a = _position(datei, "Depot A")
    assert (a["notiz"], a["notiz_vom"], "note" in a) == ("Neu", HEUTE, False)
    assert _stand("Depot A")["note"] == "Neu"

    # Leer loescht die Notiz samt Datum: Es gibt keine zweite Datei, in der eine andere stuende.
    client.post("/api/bestand", json={"key": "Depot A", "note": " "})
    assert "notiz" not in _position(datei, "Depot A")
    assert _stand("Depot A").get("note", "") == ""

    # Derselbe Text wie der der Notiz ist keine Aenderung, auch nicht fuers Datum.
    vorher = _position(datei, "Depot B")
    client.post("/api/bestand", json={"key": "Depot B", "note": "Neuer Name"})
    assert _position(datei, "Depot B") == vorher


def test_a_position_the_file_does_not_know_is_refused_and_writes_nothing(config):
    datei = _bestaende(config)
    vorher = datei.read_bytes()
    antwort = client.post("/api/bestand", json={"key": "Erfunden", "cents": 1})
    assert antwort.status_code == 404 and "unbekannte Position" in antwort.json()["error"]
    assert datei.read_bytes() == vorher


# ------------------------------------------------------------ Verpflichtung


def test_a_liability_keeps_its_note_and_dates_a_new_one(config):
    datei = _bestaende(config)
    _datei(datei, {"as_of": "2026-09-30", "balances": [],
                   "obligations": [{"name": "Darlehen X", "cents": 190_000,
                                    "notiz": "Ohne Datum"}],
                   "notizen": BEREICH})
    assert {v["kennung"]: v["note"] for v in bestaende.verpflichtungen(
        bestaende.lesen())} == {"darlehen-x": "Ohne Datum"}

    client.post("/api/verpflichtung", json={"name": "Darlehen X", "cents": 180_000})
    client.post("/api/verpflichtung", json={"name": "Darlehen X", "note": "Ohne Datum"})
    [x] = _gelesen(datei)["obligations"]
    assert (x["notiz"], "notiz_vom" in x, x["cents"]) == ("Ohne Datum", False, 180_000)
    assert _gelesen(datei)["notizen"] == BEREICH

    client.post("/api/verpflichtung", json={"name": "Darlehen X", "note": "Neu"})
    [x] = _gelesen(datei)["obligations"]
    assert (x["notiz"], x["notiz_vom"], "note" in x) == ("Neu", HEUTE, False)


def test_striking_a_liability_takes_the_entry_with_its_note_out_of_the_file(config):
    datei = _bestaende(config)
    assert client.post("/api/verpflichtung", json={"kennung": "darlehen-x",
                                                   "remove": True}).json()["ok"]
    assert _gelesen(datei)["obligations"] == []
    assert bestaende.verpflichtungen(bestaende.lesen()) == []


def test_a_liability_cannot_be_called_like_a_field_of_a_note(config):
    _bestaende(config)
    antwort = client.post("/api/verpflichtung", json={"name": "Notiz", "cents": 1})
    assert antwort.status_code == 400 and "reserviert" in antwort.json()["error"]


# ------------------------------------------------------------------- Ziel


def _ziele(config: Path) -> Path:
    return _datei(config / "goals.yaml", {"ziele": [
        {"id": "reserve", "name": "Reserve", "cents": 1_000_000, "stichtag": "2030-12-31",
         "notiz": "Aus der Datei", "notiz_vom": "2026-02-01"}]})


def test_saving_a_goal_without_a_change_changes_nothing(config):
    datei = _ziele(config)
    # Die Seite schickt Name, Betrag, Termin und Notiz so, wie sie sie zeigt.
    body = {"id": "reserve", "name": "Reserve", "cents": 1_000_000, "stichtag": "2030-12-31",
            "notiz": "Aus der Datei", "basis": []}
    vorher = datei.read_bytes()
    assert client.post("/api/ziel", json=body).json()["ok"]
    assert datei.read_bytes() == vorher


def test_a_goal_note_follows_the_date_rule_and_the_block_survives(config):
    datei = _ziele(config)
    _datei(datei, {"ziele": [{"id": "reserve", "notiz": "Ohne Datum", "cents": 900_000}],
                   "reihenfolge": ["reserve"], "notizen": BEREICH})
    body = {"id": "reserve", "cents": 950_000, "notiz": "Ohne Datum"}
    assert client.post("/api/ziel", json=body).json()["ok"]
    [r] = _gelesen(datei)["ziele"]
    assert (r["notiz"], "notiz_vom" in r, r["cents"]) == ("Ohne Datum", False, 950_000)
    assert _gelesen(datei)["notizen"] == BEREICH and _gelesen(datei)["reihenfolge"] == ["reserve"]

    client.post("/api/ziel", json={**body, "notiz": "Neu"})
    [r] = _gelesen(datei)["ziele"]
    assert (r["notiz"], r["notiz_vom"]) == ("Neu", HEUTE)

    # Leer loescht die Notiz samt Datum.
    client.post("/api/ziel", json={**body, "notiz": ""})
    assert "notiz" not in _gelesen(datei)["ziele"][0]


def test_a_new_goal_keeps_the_note_it_is_created_with(config):
    datei = _ziele(config)
    assert client.post("/api/ziel", json={"neu": True, "name": "Reise", "cents": 100_000,
                                          "notiz": "Eingetragen"}).json()["ok"]
    reise = next(g for g in _gelesen(datei)["ziele"] if g["id"] == "reise")
    assert (reise["name"], reise["notiz"], reise["notiz_vom"]) == ("Reise", "Eingetragen", HEUTE)
    assert next(iter(reise)) == "id"            # Kennung und Name stehen vorn


def test_a_goal_without_a_name_shows_its_id_and_saving_writes_no_name(config):
    datei = _datei(config / "goals.yaml", {"ziele": [{"id": "ohne-name", "cents": 5_000}]})
    vorher = datei.read_bytes()
    assert client.post("/api/ziel", json={"id": "ohne-name", "name": "ohne-name",
                                          "cents": 5_000}).json()["ok"]
    assert datei.read_bytes() == vorher
    # Ein anderer Name wird geschrieben.
    client.post("/api/ziel", json={"id": "ohne-name", "name": "Mit Namen"})
    assert _gelesen(datei)["ziele"][0]["name"] == "Mit Namen"


def test_the_default_of_an_emergency_fund_is_never_written_by_a_save(config, monkeypatch):
    """Der Betrag und der Satz, die die Seite aus der Vorgabe zeigt, kommen nicht in die Datei,
    solange niemand sie aendert."""
    from finctl import assumptions as ann
    from finctl.forecast import ziele as zl

    monkeypatch.setattr(ann, "salary_floor_cents", lambda *a, **k: 250_000)
    datei = _datei(config / "goals.yaml",
                   {"ziele": [{"id": zl.PUFFER_ZIEL, "name": "Notgroschen"}]})
    vorher = datei.read_bytes()
    [angezeigt] = zl.aus_spec(_gelesen(datei))["ziele"]
    assert client.post("/api/ziel", json={
        "id": zl.PUFFER_ZIEL, "name": "Notgroschen", "cents": angezeigt["cents"],
        "notiz": angezeigt["notiz"], "basis": []}).json()["ok"]
    assert datei.read_bytes() == vorher
    client.post("/api/ziel", json={"id": zl.PUFFER_ZIEL, "cents": 1_000_000})
    assert _gelesen(datei)["ziele"][0]["cents"] == 1_000_000


def test_the_order_dragged_on_the_page_is_a_key_of_the_goals_file(config):
    datei = _ziele(config)
    antwort = client.post("/api/ziele/reihenfolge", json={"ids": ["reserve", "reise"]})
    assert antwort.json()["ok"]
    spec = _gelesen(datei)
    assert spec["reihenfolge"] == ["reserve", "reise"] and spec["ziele"][0]["id"] == "reserve"
    assert not (config / "ziele_custom.yaml").exists()


def test_a_goal_the_file_does_not_know_is_refused_and_deleting_removes_it_with_its_note(config):
    datei = _ziele(config)
    assert client.post("/api/ziel", json={"id": "erfunden", "cents": 1}).status_code == 404
    assert client.post("/api/ziel", json={"id": "reserve", "loeschen": True}).json()["ok"]
    assert _gelesen(datei)["ziele"] == []


# ----------------------------------------------------------------- Klammer


def test_a_bracket_keeps_its_note_when_it_is_switched(config):
    pfad = _datei(config / "szenarien.yaml", {
        "szenarien": [{"id": "auto", "name": "Auto", "aktiv": True, "zeilen": [],
                       "notiz": "Ohne Datum"}],
        "notizen": BEREICH})
    assert client.post("/api/szenario", json={"id": "auto", "aktiv": False}).json()["ok"]
    gespeichert = _gelesen(pfad)
    auto = next(s for s in gespeichert["szenarien"] if s["id"] == "auto")
    assert (auto["aktiv"], auto["notiz"], "notiz_vom" in auto) == (False, "Ohne Datum", False)
    assert gespeichert["notizen"] == BEREICH


# -------------------------------------------------------- Kredit-Anschluss


def test_the_follow_up_terms_of_a_loan_do_not_cost_the_other_entries(config):
    """Der Anschluss schrieb `loans_custom.yaml` nur mit sich selbst: Die Kredite der
    Seite, die Vorlagen und die Notizen waren danach weg. Seit N.3c schreibt er den
    Kredit in `loans.yaml`, und alles andere bleibt."""
    datei = _datei(config / "loans.yaml", {
        "loans": [{"id": "kredit-a", "name": "Kredit A", "notiz": "Mit Datum",
                   "notiz_vom": "2026-02-01"},
                  {"id": "kredit-b", "name": "Kredit B", "notiz": "Ohne Datum",
                   "anschluss": {"zins_pct": 3.0, "tilgung_pct": 1.0}},
                  {"id": "kredit-c", "name": "Kredit C", "szenario": "kauf",
                   "vorlage": {"principal_cents": 100_000}}],
        "notizen": BEREICH})
    antwort = client.post("/api/kredit-anschluss", json={
        "id": "kredit-a", "zins_pct": 4.0, "tilgung_pct": 2.0})
    assert antwort.json()["ok"]
    gespeichert = _gelesen(datei)
    je_id = {k["id"]: k for k in gespeichert["loans"]}
    assert (je_id["kredit-a"]["notiz"], je_id["kredit-a"]["notiz_vom"]) == (
        "Mit Datum", "2026-02-01")
    assert je_id["kredit-a"]["anschluss_eingegeben"]["zins_pct"] == 4.0
    # Das `anschluss` der Datei, das die Prognose liest, bleibt, wie es war.
    assert je_id["kredit-b"]["anschluss"] == {"zins_pct": 3.0, "tilgung_pct": 1.0}
    assert "anschluss_eingegeben" not in je_id["kredit-b"]
    assert "anschluss" not in je_id["kredit-a"]
    assert je_id["kredit-c"]["vorlage"] == {"principal_cents": 100_000}
    assert gespeichert["notizen"] == BEREICH
    assert not (config / "loans_custom.yaml").exists()

    # Entfernen nimmt die Kondition wieder heraus; die Notiz bleibt.
    weg = client.post("/api/kredit-anschluss", json={"id": "kredit-a", "entfernen": True})
    assert weg.json()["ok"]
    assert "anschluss_eingegeben" not in _gelesen(datei)["loans"][0]
    assert _gelesen(datei)["loans"][0]["notiz"] == "Mit Datum"


def test_a_follow_up_for_a_loan_that_does_not_exist_is_refused(config):
    datei = _datei(config / "loans.yaml", {"loans": [{"id": "kredit-a", "name": "Kredit A"}]})
    vorher = datei.read_bytes()
    antwort = client.post("/api/kredit-anschluss", json={
        "id": "erfunden", "zins_pct": 4.0, "tilgung_pct": 2.0})
    assert antwort.status_code == 404 and "Kein Kredit" in antwort.json()["error"]
    assert datei.read_bytes() == vorher


# ------------------------------------------------------------------ Rente


def test_the_pension_page_saves_a_note_with_a_date_and_keeps_an_undated_one(config):
    datei = _datei(config / "renten.yaml", {"renten": [
        {"id": "gesetzlich", "name": "Gesetzliche Rente", "art": "rente", "cents": 150_000,
         "stand": "2026-01-01", "notiz": "Aus der Renteninformation"}]})
    assert client.post("/api/rente", json={"key": "gesetzlich", "note": "Eigene"}).json()["ok"]
    r = _gelesen(datei)["renten"][0]
    assert (r["notiz"], str(r["notiz_vom"])) == ("Eigene", HEUTE)

    _datei(datei, {"renten": [{"id": "gesetzlich", "name": "Gesetzliche Rente", "art": "rente",
                               "cents": 150_000, "notiz": "Ohne Datum"}], "notizen": BEREICH})
    vorher = datei.read_bytes()
    client.post("/api/rente", json={"key": "gesetzlich", "note": "Ohne Datum"})
    assert datei.read_bytes() == vorher
    assert not (config / "renten_custom.yaml").exists()


# ------------------------------------------------- Laenge und Umbrueche der Notizen

#: Mehrere Absaetze, rund 4.800 Zeichen: laenger als jede Grenze, die eine Seite je hatte.
LANG = "\n\n".join(f"Absatz {i}: " + "Begruendung. " * 30 for i in range(12)).strip()


def test_a_long_multi_line_note_is_kept_whole_by_every_page_that_saves_one(config):
    assert len(LANG) > 4_000
    datei = _bestaende(config)
    # Bestand
    assert client.post("/api/bestand", json={"key": "Depot A", "note": LANG}).json()["ok"]
    assert _position(datei, "Depot A")["notiz"] == LANG
    # Verpflichtung
    assert client.post("/api/verpflichtung", json={"name": "Darlehen X", "note": LANG}).json()["ok"]
    assert _gelesen(datei)["obligations"][0]["notiz"] == LANG
    # Konto-Regel
    from finctl.web.basis import conn

    c = conn()
    try:
        konto = c.execute("SELECT id FROM accounts ORDER BY id LIMIT 1").fetchone()[0]
    finally:
        c.close()
    assert client.post(f"/api/konto/{konto}", json={"note": LANG}).json()["ok"]
    assert _gelesen(config / "forecast.yaml")["account_roles"][konto]["notiz"] == LANG
    # Rente
    _datei(config / "renten.yaml", {"renten": [
        {"id": "gesetzlich", "name": "Gesetzliche Rente", "art": "rente", "cents": 150_000}]})
    assert client.post("/api/rente", json={"key": "gesetzlich", "note": LANG}).json()["ok"]
    assert _gelesen(config / "renten.yaml")["renten"][0]["notiz"] == LANG


def test_a_note_sent_with_windows_line_breaks_is_the_same_note(config):
    """Ein Browser schickt `\\n`; wer `\\r\\n` schickt, aendert damit nichts an der Notiz."""
    datei = _bestaende(config)
    client.post("/api/bestand", json={"key": "Depot A", "note": "Eins.\n\nZwei."})
    vorher = datei.read_bytes()
    client.post("/api/bestand", json={"key": "Depot A", "note": "Eins.\r\n\r\nZwei."})
    assert datei.read_bytes() == vorher
