"""Eine Position im Monatsabschluss anlegen und wieder entfernen.

`/api/bestand` aendert nur, was `balances.yaml` schon traegt. Wer ein Depot oder
eine Police neu hat, kam ohne Texteditor nicht weiter: Das Konto liess sich
anlegen, sein Stand nicht.

Testdaten sind erfunden.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest
import yaml
from fastapi.testclient import TestClient

from finctl import bestaende
from finctl.dateien import yaml_schreiben
from finctl.forecast import ziele
from finctl.ledger import db as ledger
from finctl.web.routen import konten as konten_seite
from finctl.web.server import app

ANGABEN = {"konto": "depot-neu", "art": "depot", "cents": 1_250_000, "as_of": "2026-10-01",
           "note": "Gehört zur Hälfte der Mitzahlerin."}

KONTEN = [("giro-a", "Giro A", "giro", "parsed", 1),
          ("depot-neu", "Neues Depot", "depot", "summary", 1),
          ("depot-alt", "Altes Depot", "depot", "summary", 1),
          ("zu", "Geschlossen", "depot", "summary", 0)]


def _konto_einfuegen(c, kennung, name, art, modus, aktiv):
    c.execute("INSERT INTO accounts (id, display_name, institution, account_type, ingest_mode, "
              "parser_profile, active) VALUES (?, ?, 'X', ?, ?, ?, ?)",
              (kennung, name, art, modus, "profil" if modus == "parsed" else None, aktiv))


@pytest.fixture
def db():
    c = sqlite3.connect(":memory:")
    c.executescript(open("finctl/ledger/schema.sql", encoding="utf-8").read())
    for kennung, name, art, modus, aktiv in KONTEN:
        _konto_einfuegen(c, kennung, name, art, modus, aktiv)
    return c


def _spec():
    return {"as_of": "2026-09-11", "balances": [
        {"account_id": "giro-a", "kind": "giro", "notiz": "Betriebskonto."},
        {"account_id": "depot-alt", "name": "Altes Depot", "cents": 500_000,
         "as_of": "2026-09-01", "kind": "depot", "notiz": "Alt.\n\nZweiter Absatz."}],
        "verlauf": {"depot-alt": {"2026-09": {"cents": 500_000, "as_of": "2026-09-01"}}},
        "obligations": []}


def test_only_open_accounts_without_statements_or_position_are_offered(db):
    assert [k["id"] for k in bestaende.freie_konten(db, _spec())] == ["depot-neu"]


def test_a_new_position_stands_behind_the_others_with_its_note(db):
    spec = _spec()
    assert bestaende.position_anlegen(db, spec, dict(ANGABEN)) == "depot-neu"
    neu = spec["balances"][-1]
    assert [e.get("account_id") for e in spec["balances"]] == ["giro-a", "depot-alt", "depot-neu"]
    assert (neu["name"], neu["cents"], neu["as_of"], neu["kind"]) == (
        "Neues Depot", 1_250_000, "2026-10-01", "depot")
    assert neu["notiz"] == ANGABEN["note"] and neu["notiz_vom"]
    # Die anderen Positionen bleiben, wie sie sind.
    assert spec["balances"][1]["notiz"] == "Alt.\n\nZweiter Absatz."


def test_a_new_depot_counts_in_the_depot_pot_and_in_the_history(db):
    spec = _spec()
    vorher = bestaende.zusammenfuehren(db, spec)
    bestaende.position_anlegen(db, spec, dict(ANGABEN))
    nachher = bestaende.zusammenfuehren(db, spec)
    assert ziele.toepfe(nachher)["depot"] - ziele.toepfe(vorher)["depot"] == 1_250_000
    assert bestaende.verlauf_fortschreiben(spec, vorher, nachher, "depot-neu", date(2026, 10, 5))
    assert spec["verlauf"]["depot-neu"]["2026-10"]["cents"] == 1_250_000


@pytest.mark.parametrize("aenderung, wort", [
    ({"konto": ""}, "Konto fehlt"),
    ({"konto": "gibtsnicht"}, "Kein offenes Konto"),
    ({"konto": "giro-a"}, "liest Auszüge"),
    ({"konto": "depot-alt"}, "schon eine Position"),
    ({"konto": "zu"}, "Kein offenes Konto"),
    ({"art": "sparbuch"}, "Art:"),
    ({"cents": None}, "Stand fehlt"),
    ({"as_of": "gestern"}, "Stichtag"),
    ({"as_of": ""}, "Stichtag"),
])
def test_a_wrong_position_is_refused_with_a_reason_and_changes_nothing(db, aenderung, wort):
    spec = _spec()
    vorher = yaml.safe_dump(spec)
    with pytest.raises(ValueError, match=wort):
        bestaende.position_anlegen(db, spec, {**ANGABEN, **aenderung})
    assert yaml.safe_dump(spec) == vorher


def test_every_offered_kind_has_a_pot(db):
    assert set(bestaende.POSITIONSARTEN) <= set(ziele.TOPF)


def test_removing_a_position_takes_note_and_history_with_it(db):
    spec = _spec()
    eintrag = bestaende.position_entfernen(db, spec, "depot-alt")
    assert eintrag["notiz"].startswith("Alt.")
    assert [e["account_id"] for e in spec["balances"]] == ["giro-a"]
    assert "depot-alt" not in spec["verlauf"]


def test_a_position_a_statement_proves_is_not_removed(db):
    spec = _spec()
    with pytest.raises(ValueError, match="liest Auszüge"):
        bestaende.position_entfernen(db, spec, "giro-a")
    with pytest.raises(ValueError, match="Keine Position"):
        bestaende.position_entfernen(db, spec, "gibtsnicht")
    assert len(spec["balances"]) == 2


# ---------------------------------------------------------------- Seite

@pytest.fixture
def seite(tmp_path, monkeypatch):
    """Die Routen auf einer eigenen Datei und einem eigenen Hauptbuch."""
    config = tmp_path / "config"
    config.mkdir()
    yaml_schreiben(config / bestaende.DATEI, _spec())
    pfad = tmp_path / "x.db"
    fertig = ledger.connect(pfad)
    fertig.executescript(open("finctl/ledger/schema.sql", encoding="utf-8").read())
    for kennung, name, art, modus, aktiv in KONTEN:
        _konto_einfuegen(fertig, kennung, name, art, modus, aktiv)
    fertig.commit()
    fertig.close()
    monkeypatch.setattr(konten_seite, "CONFIG_DIR", config)
    monkeypatch.setattr(konten_seite, "conn", lambda: ledger.connect(pfad))
    return TestClient(app), config / bestaende.DATEI, pfad


def _koerper(**aenderung):
    koerper = {"konto": "depot-neu", "art": "depot", "cents_text": "12.500,00",
               "as_of": "2026-10-01", "note": "Gehört zur Hälfte der Mitzahlerin."}
    return {**koerper, **aenderung}


def test_the_page_writes_the_position_and_the_stand_counts_at_once(seite):
    client, datei, pfad = seite
    antwort = client.post("/api/bestand-neu", json=_koerper())
    assert antwort.status_code == 200 and antwort.json() == {"ok": True, "key": "depot-neu"}
    gelesen = yaml.safe_load(datei.read_text(encoding="utf-8"))
    neu = gelesen["balances"][-1]
    assert (neu["account_id"], neu["cents"], neu["kind"]) == ("depot-neu", 1_250_000, "depot")
    assert gelesen["verlauf"]["depot-neu"]
    # Die Prognose findet den Stand ohne `finctl init`.
    c = ledger.connect(pfad)
    try:
        [stand] = c.execute("SELECT balance_cents FROM balance_snapshots WHERE "
                            "account_id = 'depot-neu' AND source = 'manual'").fetchone()
        assert stand == 1_250_000
    finally:
        c.close()


def test_a_bad_amount_or_a_taken_account_is_a_400_and_writes_nothing(seite):
    client, datei, _ = seite
    vorher = datei.read_bytes()
    assert client.post("/api/bestand-neu", json=_koerper(cents_text="1,234.56")).status_code == 400
    assert client.post("/api/bestand-neu", json=_koerper(cents_text="")).status_code == 400
    assert client.post("/api/bestand-neu", json=_koerper(konto="depot-alt")).status_code == 400
    assert client.post("/api/bestand-neu", json=_koerper(konto="giro-a")).status_code == 400
    assert datei.read_bytes() == vorher


def test_removing_through_the_page_leaves_no_trace_in_file_or_snapshots(seite):
    client, datei, pfad = seite
    assert client.post("/api/bestand-neu", json=_koerper()).status_code == 200
    antwort = client.post("/api/bestand-entfernen", json={"key": "depot-neu"})
    assert antwort.status_code == 200
    gelesen = yaml.safe_load(datei.read_text(encoding="utf-8"))
    assert [e["account_id"] for e in gelesen["balances"]] == ["giro-a", "depot-alt"]
    assert "depot-neu" not in gelesen["verlauf"]
    c = ledger.connect(pfad)
    try:
        assert not c.execute("SELECT 1 FROM balance_snapshots WHERE account_id = 'depot-neu'"
                             ).fetchall()
    finally:
        c.close()
    assert client.post("/api/bestand-entfernen", json={"key": "giro-a"}).status_code == 400
    assert client.post("/api/bestand-entfernen", json={"key": "depot-neu"}).status_code == 400


def test_the_monthly_close_offers_the_form_and_a_way_out():
    html = TestClient(app).get("/monatsabschluss").text
    assert 'id="position-neu"' in html and "Position anlegen" in html
    assert "positionAnlegen(this)" in html
    # Das Entfernen gibt es nur an einer Zeile, die die Datei traegt.
    assert html.count("positionEntfernen(this)") >= 1
