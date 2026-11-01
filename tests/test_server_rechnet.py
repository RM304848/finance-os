"""Der Server liest getippte Zahlen und rechnet Vorschauen (Neufassung, Schritt 0).

Der Browser nimmt auf, was im Feld steht, und schickt es als Text (`<feld>_text`).
Gelesen wird mit `parse_eingabe_betrag`, derselben Pruefung wie bei den
Auszuegen. Vorher las jede Seite selbst, und auf /split wurde "1.234,56" als
1,23 EUR gelesen.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import yaml

pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from finctl.ledger import db as ledger
from finctl.ledger.db import (
    EingabeError,
    parse_eingabe_betrag,
    parse_eingabe_zahl,
    prozent_als_anteil,
)
from finctl.web.server import app

client = TestClient(app)
DB = Path("data/finance.db")


# ------------------------------------------------------------------ Parser

@pytest.mark.parametrize(("text", "cents"), [
    ("1.234,56", 123456), ("1234.56", 123456), ("72.0", 7200), ("5.000", 500000),
    ("12", 1200), ("-12,5", -1250), ("  4 671,00 €", 467100), ("12.345.678", 1234567800),
    ("0,05", 5), ("1.234,5", 123450),
])
def test_betraege_werden_wie_in_den_auszuegen_gelesen(text, cents):
    assert parse_eingabe_betrag(text) == cents


@pytest.mark.parametrize("text", [
    "1,234.56",      # englisch: der Punkt kommt nach dem Komma
    "1,234",         # drei Nachkommastellen: gemeint waere 1.234 oder 1,23?
    "1.2345", "1.23.45", "1,2,3", "abc", "", "  ",
])
def test_mehrdeutiges_wird_abgelehnt_statt_geraten(text):
    with pytest.raises(EingabeError):
        parse_eingabe_betrag(text)


def test_die_meldung_nennt_die_eingabe():
    with pytest.raises(EingabeError) as fehler:
        parse_eingabe_betrag("1,234.56")
    assert "1,234.56" in str(fehler.value)


def test_prozent_und_anteil():
    assert parse_eingabe_zahl("2,5 %") == 2.5
    assert parse_eingabe_zahl("2.35") == 2.35
    assert prozent_als_anteil("2,35") == 0.0235          # nicht 0.023500000000000004
    assert prozent_als_anteil("70 %") == 0.7
    for text in ("2,5.1", "x", ""):
        with pytest.raises(EingabeError):
            parse_eingabe_zahl(text)


# ------------------------------------------------------------------- /split

@pytest.fixture
def buchung():
    if not DB.exists():
        pytest.skip("kein Hauptbuch")
    db = sqlite3.connect(DB)
    zeile = db.execute("SELECT id, amount_cents FROM transactions WHERE amount_cents < -100 "
                       "ORDER BY id LIMIT 1").fetchone()
    db.close()
    if zeile is None:
        pytest.skip("keine Buchung")
    return zeile


def test_vorschau_liest_tausenderpunkte_richtig(buchung):
    tid, gesamt = buchung
    text = f"{abs(gesamt) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    antwort = client.post(f"/api/split/{tid}/vorschau", json={"parts": [{"amount": text}]})
    assert antwort.status_code == 200
    assert antwort.json()["summe_cents"] == abs(gesamt)   # "1.234,56" ist nicht 1,23


def test_vorschau_sagt_ob_es_aufgeht(buchung):
    tid, gesamt = buchung
    auf = client.post(f"/api/split/{tid}/vorschau",
                      json={"parts": [{"amount": str(gesamt / 100).replace(".", ",")}]}).json()
    assert auf["geht_auf"] and auf["differenz_cents"] == 0 and "geht genau auf" in auf["meldung"]
    nicht = client.post(f"/api/split/{tid}/vorschau", json={"parts": [{"amount": "0,01"}]}).json()
    assert not nicht["geht_auf"] and nicht["differenz_cents"] == 1 - gesamt
    assert "Differenz" in nicht["meldung"]


def test_vorschau_verteilt_gleichmaessig_ohne_einen_cent_zu_verlieren(buchung):
    tid, gesamt = buchung
    for anzahl in (2, 3, 7):
        antwort = client.post(f"/api/split/{tid}/vorschau", json={
            "parts": [{"amount": ""}] * anzahl, "gleichmaessig": True}).json()
        assert antwort["geht_auf"] and antwort["summe_cents"] == gesamt
        assert len(antwort["betraege"]) == anzahl
        teile = [ledger.parse_eingabe_betrag(t) for t in antwort["betraege"]]
        assert sum(teile) == gesamt and max(teile) - min(teile) <= 1


def test_vorschau_benennt_die_unlesbare_zeile(buchung):
    tid, _ = buchung
    antwort = client.post(f"/api/split/{tid}/vorschau",
                          json={"parts": [{"amount": "1,00"}, {"amount": "1,234.56"}]})
    assert antwort.status_code == 400
    assert antwort.json()["error"].startswith("Teil 2:") and antwort.json()["feld"] == "amount"


def test_speichern_lehnt_eine_mehrdeutige_summe_ab_und_schreibt_nichts(buchung):
    tid, _ = buchung
    db = sqlite3.connect(DB)
    vorher = db.execute("SELECT amount_cents, source FROM splits WHERE transaction_id=? "
                        "ORDER BY seq", (tid,)).fetchall()
    db.close()
    antwort = client.post(f"/api/split/{tid}", json={"parts": [{"amount": "1,234.56"}]})
    assert antwort.status_code == 400
    db = sqlite3.connect(DB)
    assert db.execute("SELECT amount_cents, source FROM splits WHERE transaction_id=? "
                      "ORDER BY seq", (tid,)).fetchall() == vorher
    db.close()


# --------------------------------------------------------- Einstellungen

def test_einstellung_als_text_je_nach_einheit(monkeypatch):
    from finctl import assumptions

    gesetzt = {}
    monkeypatch.setattr(assumptions, "setzen", lambda k, v, path=None: gesetzt.update({k: v}))
    for key, text, erwartet in (("inflation_pa", "2,5 %", 0.025),
                                ("salary_floor_cents", "1.234,56", 123456),
                                ("lebenserwartung", "90", 90),
                                ("teilzeit_ab", "2027-04", "2027-04")):
        gesetzt.clear()
        antwort = client.post("/api/setting", json={"key": key, "text": text})
        assert antwort.status_code == 200, (key, antwort.json())
        assert gesetzt[key] == erwartet


def test_einstellung_mit_mehrdeutigem_text_wird_abgelehnt(monkeypatch):
    from finctl import assumptions

    monkeypatch.setattr(assumptions, "setzen", lambda *a, **k: pytest.fail("geschrieben"))
    antwort = client.post("/api/setting", json={"key": "salary_floor_cents", "text": "1,234.56"})
    assert antwort.status_code == 400 and antwort.json()["feld"] == "value"
    halbes_jahr = client.post("/api/setting", json={"key": "lebenserwartung", "text": "88,5"})
    assert halbes_jahr.status_code == 400


# ------------------------------------------------------------------ Renten

def test_rente_nimmt_betrag_und_kosten_als_text(monkeypatch):
    from finctl import renten

    erhalten = {}
    monkeypatch.setattr(renten, "setzen", lambda key, felder: erhalten.update(felder))
    antwort = client.post("/api/rente", json={"key": "x", "cents_text": "1.234,56",
                                             "kosten_pa_text": "0,95 %"})
    assert antwort.status_code == 200
    assert erhalten["cents"] == 123456 and erhalten["kosten_pa"] == 0.0095
    erhalten.clear()
    client.post("/api/rente", json={"key": "x", "kosten_pa_text": ""})
    assert erhalten["kosten_pa"] == ""          # leer heisst "nicht bekannt"
    assert client.post("/api/rente", json={"key": "x", "cents_text": ""}).status_code == 400


# ----------------------------------------------------------------- Kredite

def test_kredit_anschluss_liest_prozent_als_text(tmp_path, monkeypatch):
    from finctl import kredite

    monkeypatch.setattr(kredite, "CONFIG_DIR", tmp_path)
    (tmp_path / "loans.yaml").write_text(
        yaml.safe_dump({"loans": [{"id": "k1", "name": "K1"}]}), encoding="utf-8")
    antwort = client.post("/api/kredit-anschluss", json={
        "id": "k1", "zins_pct_text": "3,8", "tilgung_pct_text": "2"})
    assert antwort.status_code == 200
    datei = (tmp_path / "loans.yaml").read_text(encoding="utf-8")
    eintrag = yaml.safe_load(datei)["loans"][0]["anschluss_eingegeben"]
    assert eintrag["zins_pct"] == 3.8 and eintrag["tilgung_pct"] == 2.0
    assert client.post("/api/kredit-anschluss", json={
        "id": "k1", "zins_pct_text": "3,8", "tilgung_pct_text": ""}).status_code == 400


# ------------------------------------------------------------- Immobilien

def test_objekt_nimmt_betraege_und_prozent_als_text(monkeypatch):
    from finctl import objekte

    erhalten = {}
    monkeypatch.setattr(objekte, "felder_setzen",
                        lambda pid, felder, *a, **k: erhalten.update(felder))
    antwort = client.post("/api/property/unbekannt", json={
        "purchase_price_cents_text": "250.000", "equity_cents_text": "",
        "land_share_pct_text": "22,5", "afa_rate_pct_text": "2"})
    assert antwort.status_code == 200
    assert erhalten == {"purchase_price_cents": 25000000, "equity_cents": None,
                        "land_share_pct": 22.5, "afa_rate_pct": 2.0}
    assert client.post("/api/property/unbekannt",
                       json={"purchase_price_cents_text": "250,000.5"}).status_code == 400


def test_objekt_prognose_nimmt_betraege_als_text(monkeypatch):
    from finctl import objekte

    erhalten = {}
    monkeypatch.setattr(objekte, "prognose_setzen", lambda pid, felder: erhalten.update(felder))
    client.post("/api/objekt-prognose/x", json={"miete_monatlich_cents_text": "1.250,50",
                                               "kosten_monatlich_cents_text": ""})
    assert erhalten == {"miete_monatlich_cents": 125050, "kosten_monatlich_cents": None}


# -------------------------------------------------------------------- Abos

def test_abo_hilfen_rechnen_termine_und_kennungen():
    from finctl import abos

    assert abos.kennung_aus("Süßer Streaming-Dienst (Plus)!") == "susser-streaming-dienst-plus"
    assert abos.monat_plus("2026-11", 3) == "2027-02"
    assert abos.datum_plus("2026-01-31", 1) == "2026-02-28"      # der 31. bleibt Monatsende
    assert client.post("/api/abos/vorschau", json={"monat": "2026-05", "plus": 12,
                                                   "name": "Mein Abo"}).json() == {
        "monat": "2027-05", "kennung": "mein-abo"}
    assert client.post("/api/abos/vorschau", json={"monat": "kaputt"}).status_code == 400


def test_abo_betrag_und_anteil_kommen_als_text():
    from finctl import abos

    abo = abos.texte_lesen({"betrag_text": "39,90", "geteilt": {
        "besetzung": [{"name": "A", "anteil_text": "10,00"}],
        "zeitraeume": [{"personen": [{"name": "A", "anteil_text": ""}]}]}})
    assert abo["betrag_cents"] == -3990            # ein Vertrag mit Termin ist immer Ausgabe
    assert abo["geteilt"]["besetzung"][0]["anteil_cents"] == 1000
    assert abo["geteilt"]["zeitraeume"][0]["personen"][0]["anteil_cents"] == 0
    with pytest.raises(EingabeError) as fehler:
        abos.texte_lesen({"betrag_text": "39,900"})
    assert fehler.value.feld == "betrag"


# ----------------------------------------------------------------- Planung

def test_teilzeit_anteil_kommt_als_prozent_text(monkeypatch):
    from finctl.web.routen import planung

    spec = {"szenarien": [{"id": "t", "name": "T", "aktiv": True, "zeilen": []}]}
    geschrieben = []
    monkeypatch.setattr(planung, "_read_szenarien", lambda: spec)
    monkeypatch.setattr(planung, "_write_szenarien", lambda s: geschrieben.append(s))
    antwort = client.post("/api/szenario-zeile", json={
        "szenario": "t", "art": "teilzeit", "label": "halbe Stelle", "anteil_text": "70 %"})
    assert antwort.status_code == 200, antwort.json()
    assert spec["szenarien"][0]["zeilen"][0]["anteil"] == 0.7
    zu_viel = client.post("/api/szenario-zeile", json={
        "szenario": "t", "art": "teilzeit", "label": "x", "anteil_text": "120"})
    assert zu_viel.status_code == 400
