"""Die Seite /regeln und ihre eine Datei rules.yaml.

Die Seite schreibt `rules.yaml` ganz: den Eintrag der Regel samt Notiz. Ein Speichern ohne
Aenderung schreibt kein Byte, und was die Seite nicht zeigt (any_of, transfer_account,
Aufteilungen), bleibt am Eintrag stehen.
"""

from __future__ import annotations

import pytest
import yaml
from fastapi.testclient import TestClient

from finctl.ledger.db import connect
from finctl.rules import engine
from finctl.rules import regelwerk as rw
from finctl.web.server import app

client = TestClient(app)

BASIS = """allgemeine_regeln: false

rules:
  - id: alpha
    priority: 10
    name: Alpha
    match:
      text: [Bundeskasse]
      any_of:
      - {account: c24}
      - {account: dkb-giro}
    set: {mgmt: steuern/kfz, tax: privat/nicht-abzugsfaehig, transfer_account: c24}
    notiz: warum alpha
    notiz_vom: 2026-02-01
  - id: beta
    priority: 20
    name: Beta
    match: {text: [Beta], amount_abs_between: [0, 50]}
    set: {mgmt: konsum/x}
    notiz: warum beta
"""


@pytest.fixture
def dateien(tmp_path):
    basis = tmp_path / "rules.yaml"
    basis.write_text(BASIS, encoding="utf-8")
    return basis


def _gelesen(pfad) -> dict:
    return yaml.safe_load(pfad.read_text(encoding="utf-8"))


def _form(**kw) -> dict:
    f = {"name": "", "priority": "", "text": "", "text_all": "", "counterparty": "",
         "account": "", "sign": "", "betrag_von_cents": None, "betrag_bis_cents": None,
         "datum_von": "", "datum_bis": "", "mgmt": "", "tax": "", "property": "",
         "note": ""}
    f.update(kw)
    return f


def _wie_geladen(regel_id, basis, **aenderung) -> dict:
    """Was die Seite fuer eine Regel ins Formular schreibt, mit Aenderungen."""
    e = next(r for r in rw.laden(basis) if r["id"] == regel_id)
    return {**rw.formwerte(e), **aenderung, "id": regel_id}


def _eine_kategorie() -> str:
    c = connect()
    try:
        return c.execute("SELECT id FROM mgmt_categories WHERE parent_id IS NOT NULL "
                         "AND active = 1 ORDER BY id LIMIT 1").fetchone()["id"]
    finally:
        c.close()


# ------------------------------------------------------------- eine Datei

def test_saving_an_unchanged_rule_writes_nothing(dateien):
    basis = dateien
    for regel in ("alpha", "beta"):
        e, _ = rw.entwurf(_wie_geladen(regel, basis), basis)
        rw.speichern(e, basis)
    assert basis.read_text(encoding="utf-8") == BASIS


def test_an_edit_changes_only_its_field_and_keeps_what_the_page_cannot_show(dateien):
    basis = dateien
    e, _ = rw.entwurf(_wie_geladen("alpha", basis, text="Bundeskasse, Zoll"), basis)
    rw.speichern(e, basis)

    datei = _gelesen(basis)
    alpha, beta = datei["rules"]
    assert alpha["match"]["text"] == ["Bundeskasse", "Zoll"]
    assert alpha["match"]["any_of"] == [{"account": "c24"}, {"account": "dkb-giro"}]
    assert alpha["set"]["transfer_account"] == "c24"
    assert (alpha["notiz"], str(alpha["notiz_vom"])) == ("warum alpha", "2026-02-01")
    assert beta == yaml.safe_load(BASIS)["rules"][1]
    alpha_regel = next(r for r in engine.load_rules(basis) if r.id == "alpha")
    assert alpha_regel.match["text"] == ["Bundeskasse", "Zoll"]


def test_a_new_rule_gets_an_id_and_removal_takes_a_rule_from_the_file(dateien):
    basis = dateien
    e, _ = rw.entwurf({**_form(name="Kfz-Steuer Zoll", text="Zoll", mgmt="steuern/kfz"),
                       "neu": True}, basis)
    assert e["id"] == "kfz-steuer-zoll"
    rw.speichern(e, basis)
    rw.entfernen("beta", basis)

    assert [r["id"] for r in _gelesen(basis)["rules"]] == ["alpha", "kfz-steuer-zoll"]
    assert {r["id"]: r["herkunft"] for r in rw.laden(basis)} == {
        "alpha": "basis", "kfz-steuer-zoll": "basis"}
    rw.entfernen("kfz-steuer-zoll", basis)
    assert [r["id"] for r in _gelesen(basis)["rules"]] == ["alpha"]
    with pytest.raises(ValueError, match="unbekannte Regel"):
        rw.entfernen("kfz-steuer-zoll", basis)


@pytest.mark.parametrize("aenderung, meldung", [
    ({"text": "", "betrag_bis_cents": None}, "Bedingung"),
    ({"mgmt": ""}, "setzt nichts"),
    ({"datum_von": "2026-1"}, "Datum"),
    ({"priority": "zehn"}, "Priorität"),
    ({"name": ""}, "Name"),
], ids=["ohne-bedingung", "setzt-nichts", "datum", "prioritaet", "name"])
def test_an_invalid_rule_is_refused_before_anything_is_written(dateien, aenderung, meldung):
    basis = dateien
    with pytest.raises(ValueError, match=meldung):
        e, _ = rw.entwurf(_wie_geladen("beta", basis, **aenderung), basis)
        rw.speichern(e, basis)
    assert basis.read_text(encoding="utf-8") == BASIS


def test_a_rulebook_that_would_not_load_is_refused_and_not_written(dateien):
    basis = dateien
    # Dieselbe Kennung zweimal macht das Regelwerk unlesbar; nichts, was die Seite danach
    # speichert, darf das noch schlimmer machen.
    spec = _gelesen(basis)
    spec["rules"].append(dict(spec["rules"][0]))
    basis.write_text(yaml.safe_dump(spec), encoding="utf-8")
    kaputt = basis.read_text(encoding="utf-8")
    e = {"id": "gamma", "name": "Gamma", "match": {"text": ["Gamma"]},
         "set": {"mgmt": "konsum/x"}}
    with pytest.raises(ValueError, match="duplicate"):
        rw.speichern(e, basis)
    assert basis.read_text(encoding="utf-8") == kaputt


def test_a_note_set_through_the_page_keeps_its_date_until_the_text_changes(dateien):
    basis = dateien
    e, _ = rw.entwurf(_wie_geladen("alpha", basis), basis)
    assert e["notiz"] == "warum alpha"
    rw.speichern(e, basis)
    assert str(_gelesen(basis)["rules"][0]["notiz_vom"]) == "2026-02-01"
    rw.speichern({**e, "notiz": "Neu begruendet"}, basis)
    alpha = _gelesen(basis)["rules"][0]
    assert alpha["notiz"] == "Neu begruendet"
    assert str(alpha["notiz_vom"]) != "2026-02-01"


def test_the_amount_window_survives_the_form_unchanged(dateien):
    basis = dateien
    w = _wie_geladen("beta", basis)
    assert (w["betrag_von_cents"], w["betrag_bis_cents"]) == (None, 5000)
    e, _ = rw.entwurf(w, basis)
    assert e["match"]["amount_abs_between"] == [0, 50]


# ------------------------------------------------------------------- Seite

def test_the_rules_page_lists_rules_and_prefills_a_new_one_from_a_booking():
    from finctl.rules.engine import load_rules

    html = client.get("/regeln").text
    assert load_rules()[0].id in html
    assert "const VORLAGE = null" in html

    c = connect()
    try:
        tx = c.execute("SELECT id FROM transactions ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        c.close()
    html = client.get(f"/regeln?aus={tx['id']}").text
    assert "const VORLAGE = null" not in html


def test_review_and_transactions_offer_a_rule_from_the_booking():
    assert "/regeln?aus=" in client.get("/transactions").text


def test_the_preview_shows_what_a_draft_would_catch_without_writing():
    vorher = engine.RULES_PATH.read_text(encoding="utf-8")
    r = client.post("/api/regeln/vorschau", json={
        **_form(name="pytest", text="Bundeskasse", mgmt=_eine_kategorie()), "neu": True})
    assert r.status_code == 200, r.text
    assert {"treffer", "aendert", "verdeckt", "eigen", "verliert", "zeilen"} <= set(r.json())
    assert engine.RULES_PATH.read_text(encoding="utf-8") == vorher


def test_a_rule_pointing_at_an_unknown_category_is_refused():
    r = client.post("/api/regeln/vorschau", json={
        **_form(name="pytest", text="Bundeskasse", mgmt="gibt/es-nicht"), "neu": True})
    assert r.status_code == 400
    assert "unbekannte Kategorie" in r.json()["error"]


def test_saving_and_removing_through_the_page():
    vorher = [r["id"] for r in rw.laden()]
    r = client.post("/api/regeln", json={
        **_form(name="pytest nie gesehen", text="pytest-nie-gesehen-4711",
                mgmt=_eine_kategorie()), "neu": True})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    assert rid in {e["id"] for e in _gelesen(engine.RULES_PATH)["rules"]}
    assert f"r-{rid}" in client.get("/regeln").text

    assert client.post(f"/api/regeln/{rid}/entfernen").status_code == 200
    assert rid not in {e["id"] for e in _gelesen(engine.RULES_PATH)["rules"]}
    assert [r["id"] for r in rw.laden()] == vorher
