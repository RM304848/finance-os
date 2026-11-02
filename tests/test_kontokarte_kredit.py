"""Die Kontokarte fragt nach dem Kredit: „Untergrenze aus einem Kredit“ ist eine Auswahl.

Vorher war es ein Haken, und ohne Kredit schrieb er `true`, was nichts bewirkt. Welche
Kredite und Konten es gibt, liest der Test zur Laufzeit aus `config/`.
"""

from __future__ import annotations

import pytest
import yaml
from fastapi.testclient import TestClient

from finctl import kontenregeln
from finctl.pfade import CONFIG_DIR
from finctl.realestate.loan import lade_kredite
from finctl.web.server import app

client = TestClient(app)


def _kredit_und_konto() -> tuple[str, str]:
    kredite = [k for k in lade_kredite(CONFIG_DIR) if k.get("id")]
    if not kredite:
        pytest.skip("kein Kredit in loans.yaml")
    rollen = kontenregeln.wirksam().get("account_roles") or {}
    if not rollen:
        pytest.skip("kein Konto mit Regel")
    return str(kredite[0]["id"]), next(iter(rollen))


@pytest.fixture
def forecast_datei():
    """`forecast.yaml` der Testkopie, nach dem Test wie vorher."""
    pfad = CONFIG_DIR / kontenregeln.DATEI
    vorher = pfad.read_bytes() if pfad.exists() else None
    yield pfad
    if vorher is None:
        pfad.unlink(missing_ok=True)
    else:
        pfad.write_bytes(vorher)


def test_the_card_offers_the_loans_instead_of_a_tick():
    html = client.get("/konten").text
    assert 'id="f-loan"' in html and 'id="f-loanfloor"' not in html
    assert "kein Kredit gewählt" in html
    for kredit in lade_kredite(CONFIG_DIR):
        if kredit.get("id"):
            assert f'<option value="{kredit["id"]}">' in html


def test_a_loan_that_loans_yaml_does_not_know_is_refused(forecast_datei):
    _, konto = _kredit_und_konto()
    vorher = forecast_datei.read_bytes()
    res = client.post(f"/api/konto/{konto}", json={"floor_from_loan": "gibt-es-nicht"})
    assert res.status_code == 400
    assert forecast_datei.read_bytes() == vorher


def test_choosing_a_loan_writes_its_id_and_clearing_it_takes_the_field_out(forecast_datei):
    kredit, konto = _kredit_und_konto()
    res = client.post(f"/api/konto/{konto}", json={"floor_from_loan": kredit})
    assert res.status_code == 200, res.text
    regel = yaml.safe_load(forecast_datei.read_text(encoding="utf-8"))["account_roles"][konto]
    assert regel["floor_from_loan"] == kredit
    vorher = forecast_datei.read_bytes()
    client.post(f"/api/konto/{konto}", json={"floor_from_loan": kredit})
    assert forecast_datei.read_bytes() == vorher
    client.post(f"/api/konto/{konto}", json={"floor_from_loan": ""})
    regel = yaml.safe_load(forecast_datei.read_text(encoding="utf-8"))["account_roles"][konto]
    assert "floor_from_loan" not in regel


def test_a_stored_id_without_a_loan_may_stay_when_nothing_changes(forecast_datei):
    """Der Kredit ist weg, die Kennung steht noch: Speichern ohne Aenderung schreibt nichts."""
    _, konto = _kredit_und_konto()
    spec = yaml.safe_load(forecast_datei.read_text(encoding="utf-8")) or {}
    spec.setdefault("account_roles", {}).setdefault(konto, {})["floor_from_loan"] = "weg"
    forecast_datei.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False),
                              encoding="utf-8")
    vorher = forecast_datei.read_bytes()
    res = client.post(f"/api/konto/{konto}", json={"floor_from_loan": "weg"})
    assert res.status_code == 200
    assert forecast_datei.read_bytes() == vorher
