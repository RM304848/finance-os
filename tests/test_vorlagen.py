"""Die Kopiervorlage: hinaus geht nur Bereinigtes, herein nur Geprueftes, geschrieben wird nie.

Die App ruft kein Modell auf. Sie baut einen Text und liest die eingefuegte Antwort.
Was dabei schiefgehen kann, ist dasselbe wie bei `test_vorschlaege.py`, nur breiter:
Die Lage der Monats- und Prognosevorlage traegt Zahlen und Namen aus dem Haushalt,
und ein Schreibzugriff darf erst nach einer Bestaetigung geschehen.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from finctl.pfade import CONFIG_DIR
from finctl.web import vorlagen as vl
from finctl.web.server import app

DB = Path("data/finance.db")
pytestmark = pytest.mark.skipif(not DB.exists(), reason="kein Hauptbuch")
client = TestClient(app)

IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,4})?\b")


@pytest.fixture
def conn():
    from finctl.ledger.db import connect

    c = connect()
    yield c
    c.close()


def _config() -> dict[str, str]:
    """Eine Quersumme je Datei von config/: jede Aenderung faellt auf."""
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(CONFIG_DIR.glob("*.yaml"))}


def _vorlagen(conn) -> list[vl.Vorlage]:
    out = []
    for art in vl.ARTEN:
        try:
            out.append(vl.bauen(art, conn))
        except ValueError:          # Einordnen ohne offene Buchungen
            assert art == "einordnen"
    return out


# --------------------------------------------------------------------- Begriffe

def test_every_term_of_a_template_is_an_entry_of_the_glossary():
    g = vl.glossar()
    for art, (_titel, namen) in vl.ARTEN.items():
        assert not [n for n in namen if n not in g], art


def test_a_template_carries_exactly_the_terms_its_situation_uses(conn):
    for v in _vorlagen(conn):
        genannt = [z.split(":")[0].removeprefix("- ") for z in v.begriffe[1:]]
        assert genannt == list(vl.ARTEN[v.art][1])


def test_a_template_has_three_parts_in_order(conn):
    for v in _vorlagen(conn):
        teile = [z for z in v.text.splitlines() if z.startswith("# ")]
        assert teile == ["# Begriffe", "# Lage", "# Frage"]


# ------------------------------------------------------------------------ Leck

def test_a_template_has_no_iban_and_no_long_number_from_the_config(conn):
    nummern = set()
    for datei in CONFIG_DIR.glob("*.yaml"):
        if datei.name != "overrides.yaml":      # Hashes, keine Nummern
            nummern |= set(re.findall(r"(?<!\d)\d{7,}(?!\d)", datei.read_text(encoding="utf-8")))
    nummern = {n for n in nummern if not n.endswith("00000")}
    for v in _vorlagen(conn):
        assert not IBAN.findall(v.text), v.art
        assert not [n for n in nummern if n in v.text], v.art


def test_a_template_has_no_raw_text_of_a_statement(conn):
    roh = {r[0].strip() for r in conn.execute(
        "SELECT raw_text FROM transactions WHERE raw_text IS NOT NULL")}
    roh = {t for t in roh if len(t) >= 20}
    for v in _vorlagen(conn):
        assert not [t for t in roh if t in v.text], v.art


def test_only_the_template_that_needs_them_names_counterparties(conn):
    gegen = {r[0].strip() for r in conn.execute(
        "SELECT DISTINCT counterparty FROM transactions WHERE counterparty IS NOT NULL")}
    # Eine Bank heisst auch das Konto, das sie fuehrt; das Konto gehoert in die Lage.
    konten = {r[0] for r in conn.execute("SELECT display_name FROM accounts")}
    gegen = {n for n in gegen if len(n) >= 6 and n not in konten}
    for art in ("monat", "prognose"):
        text = vl.bauen(art, conn).text
        assert not [n for n in gegen if n in text], art


def test_an_offered_text_is_cleaned_and_a_foreign_text_is_dropped(conn, monkeypatch):
    """Nur, was die Seite bereinigt angeboten hat, kommt in die Lage."""
    monkeypatch.setattr(vl.vs, "offene_texte",
                        lambda c: [{"text": "Erfundener Laden", "anzahl": 2}])
    v = vl.bauen("einordnen", conn, texte=["Erfundener Laden", "DE12500105170648489890"])
    assert "- Erfundener Laden" in v.lage
    assert "DE12500105170648489890" not in v.text
    with pytest.raises(ValueError, match="Kein Text"):
        vl.bauen("einordnen", conn, texte=["DE12500105170648489890"])


def test_a_last_guard_removes_an_iban_from_any_line():
    assert vl._ohne_nummern(["Konto DE12500105170648489890 Stand", "Nr 1234567890123"]) \
        == ["Konto … Stand", "Nr …"]


# ----------------------------------------------------------------------- Eingabe

def test_a_month_must_be_a_month(conn):
    with pytest.raises(ValueError, match="JJJJ-MM"):
        vl.bauen("monat", conn, monat="Oktober")
    assert "Monat: 2026-03" in vl.bauen("monat", conn, monat="2026-03").lage


def test_an_unknown_template_is_refused(conn):
    with pytest.raises(ValueError):
        vl.bauen("erfunden", conn)


def test_the_own_question_is_cut_and_whitespace_is_squashed(conn):
    v = vl.bauen("prognose", conn, frage="  Reicht\n\n das  Geld? " + "x" * 1000)
    assert v.frage[0].startswith("Reicht das Geld? x")
    assert len(v.frage[0]) <= vl.FRAGE_MAX


# ------------------------------------------------------------------------ Antwort

def _erklaerung(art: str, conn):
    v = vl.bauen(art, conn)
    return v, sorted(v.kennungen)


@pytest.mark.parametrize("art", ["monat", "prognose"])
def test_a_wrong_answer_gets_a_message_and_writes_nothing(art):
    vorher = _config()
    for antwort in ("", "Das sieht gut aus.", "AUFFÄLLIG: x ; y"):
        r = client.post("/api/vorlagen/pruefen", json={"art": art, "antwort": antwort})
        assert r.status_code == 400
        assert "ZUSAMMENFASSUNG" in r.json()["error"]
    assert _config() == vorher


def test_a_wrong_answer_for_rules_gets_a_message_and_writes_nothing():
    vorher = _config()
    r = client.post("/api/vorlagen/pruefen",
                    json={"art": "einordnen", "antwort": "Das sind meine Vorschläge."})
    assert r.status_code == 400
    assert "Suchtext ; Kategorie" in r.json()["error"]
    assert _config() == vorher


def test_an_unknown_template_or_month_gets_a_message_too():
    unbekannt = client.post("/api/vorlagen/pruefen", json={"art": "x", "antwort": "a"})
    assert unbekannt.status_code == 400
    r = client.post("/api/vorlagen/vorlage", json={"art": "monat", "monat": "bald"})
    assert r.status_code == 400 and "JJJJ-MM" in r.json()["error"]


@pytest.mark.parametrize("art", ["monat", "prognose"])
def test_a_valid_answer_becomes_a_proposal_and_checks_names_and_amounts(art, conn):
    _v, kennungen = _erklaerung(art, conn)
    if not kennungen:
        pytest.skip("keine Kennung in der Lage")
    vorher = _config()
    antwort = (f"ZUSAMMENFASSUNG: Alles im Rahmen, aber 123.400,00 € sind neu.\n"
               f"AUFFÄLLIG: {kennungen[0]} ; Hier lohnt ein Blick.\n"
               f"AUFFÄLLIG: gibt-es-nicht ; Erfunden.")
    r = client.post("/api/vorlagen/pruefen", json={"art": art, "antwort": antwort})
    assert r.status_code == 200
    html = r.json()["html"]
    assert "Hier lohnt ein Blick." in html and "Alles im Rahmen" in html
    assert html.lower().count("nicht in der lage") >= 2      # die erfundene Kennung und der Betrag
    assert "123.400,00" in html
    assert _config() == vorher


def test_the_reader_flags_only_what_the_situation_does_not_hold(conn):
    v = vl.bauen("prognose", conn)
    betrag = next(iter(vl._BETRAG.findall("\n".join(v.lage))), None)
    if betrag is None:
        pytest.skip("kein Betrag in der Lage")
    e = vl.erklaerung_lesen(f"**ZUSAMMENFASSUNG:** Stand {betrag}, nicht 9.999.900,00.", v)
    assert e.fremde_betraege == ["9.999.900,00"]


def test_a_valid_answer_for_rules_is_a_proposal_until_somebody_confirms(conn):
    """Prüfen schreibt nichts; erst „übernehmen“ legt eine gewöhnliche Regel an."""
    from finctl.rules import vorschlaege as vs
    from finctl.web.basis import categories

    kategorie = categories(conn)[0]["id"]
    suchtext = "zzzz erfundener suchtext"
    regeln = CONFIG_DIR / "rules.yaml"
    vorher, davor = _config(), regeln.read_bytes() if regeln.exists() else None
    try:
        r = client.post("/api/vorlagen/pruefen", json={
            "art": "einordnen", "antwort": f"{suchtext} ; {kategorie}"})
        assert r.status_code == 200
        assert suchtext in r.json()["html"] and 'class="vl-nehmen"' in r.json()["html"]
        assert _config() == vorher                          # noch nichts geschrieben
        ok = client.post("/api/regeln/vorschlaege/uebernehmen",
                         json={"zeilen": [{"text": suchtext, "kategorie": kategorie}]})
        assert ok.status_code == 200 and ok.json()["ids"]
        assert _config() != vorher                          # erst jetzt
        assert vs.PRIORITAET == 80
    finally:
        if davor is None:
            regeln.unlink(missing_ok=True)
        else:
            regeln.write_bytes(davor)
        from finctl.rules.categorize import categorize

        categorize(conn, recompute=True)
    assert _config() == vorher


# --------------------------------------------------------------------- Die Seite

@pytest.mark.parametrize("art", ["einordnen", "monat", "prognose"])
def test_the_page_shows_the_template_and_says_it_sends_nothing(art):
    r = client.get(f"/vorlagen?art={art}")
    assert r.status_code == 200
    assert "Die App sendet nichts" in r.text
    assert 'id="vl-text"' in r.text and "Kopieren" in r.text
    if art != "einordnen":
        assert "# Begriffe" in r.text and "# Lage" in r.text and "# Frage" in r.text


def test_the_rules_page_points_to_the_template_instead_of_offering_its_own():
    r = client.get("/regeln")
    assert 'href="/vorlagen?art=einordnen"' in r.text
    assert 'id="vs-prompt"' not in r.text


def test_the_old_prompt_route_is_gone():
    alt = client.post("/api/regeln/vorschlaege/prompt", json={"texte": ["x"]})
    assert alt.status_code in (404, 405)
