"""Das Betriebskonto ist das aktive Konto mit der Rolle -- keine feste Kennung.

Prognose und Planung kennen Rollen, nie eine Bank (`docs/Neufassung_plan.md`,
Schritt 1). Wechselt der Anbieter, wird das alte Konto archiviert und das neue
bekommt die Rolle; nichts anderes darf sich bewegen.
"""

from __future__ import annotations

import pytest
import yaml
from typer.testing import CliRunner

from finctl import konten, ops
from finctl.cli import app
from finctl.forecast import konten as fk


def _register(tmp_path, monkeypatch, konten_liste: list[dict]) -> None:
    (tmp_path / "accounts.yaml").write_text(
        yaml.safe_dump({"accounts": konten_liste}, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(konten, "CONFIG_DIR", tmp_path)


def _giro(kennung: str, **mehr) -> dict:
    return {"id": kennung, "display_name": kennung, "institution": "Bank",
            "account_type": "giro", "ingest_mode": "parsed", **mehr}


def _rollen(*betrieb: str) -> dict:
    return {"account_roles": {k: {"role": "operating"} for k in betrieb}}


def test_das_konto_mit_der_rolle_ist_das_betriebskonto(tmp_path, monkeypatch):
    _register(tmp_path, monkeypatch, [_giro("a-konto"), _giro("b-konto")])
    assert fk._operating_account(_rollen("b-konto")) == "b-konto"


@pytest.mark.parametrize("archiviert", [{"active": False}, {"closed_on": "2026-03-31"}])
def test_ein_archiviertes_konto_ist_es_nicht_mehr(tmp_path, monkeypatch, archiviert):
    """Der Anbieter wechselt: das alte Konto behaelt seinen Eintrag, steht in der
    Datei aber vorn."""
    _register(tmp_path, monkeypatch, [_giro("alt", **archiviert), _giro("neu")])
    assert fk._operating_account(_rollen("alt", "neu")) == "neu"


def test_ohne_rolle_das_erste_aktive_giro_mit_auszuegen(tmp_path, monkeypatch):
    _register(tmp_path, monkeypatch, [
        _giro("z-konto"), _giro("alt", active=False), _giro("m-konto"),
        {**_giro("karte"), "account_type": "karte"},
        {**_giro("summe"), "ingest_mode": "summary"}])
    assert fk._operating_account({}) == "m-konto"


def test_ohne_giro_gibt_es_kein_betriebskonto(tmp_path, monkeypatch):
    _register(tmp_path, monkeypatch, [{**_giro("depot"), "account_type": "depot"}])
    assert fk._operating_account({}) is None


def test_forecast_ohne_konto_nimmt_das_betriebskonto(monkeypatch):
    gefragt = []

    class _Verbindung:
        def close(self):
            pass

    monkeypatch.setattr("finctl.cli._require_db", lambda: _Verbindung())
    monkeypatch.setattr(ops, "betriebskonto", lambda: "giro-x")
    monkeypatch.setattr(ops, "account_forecast",
                        lambda conn, konto, **kw: gefragt.append(konto) or {"account": konto})
    lauf = CliRunner().invoke(app, ["forecast", "--json"])
    assert lauf.exit_code == 0, lauf.output
    assert gefragt == ["giro-x"]


def test_forecast_ohne_betriebskonto_sagt_warum(monkeypatch):
    monkeypatch.setattr(ops, "betriebskonto", lambda: None)
    lauf = CliRunner().invoke(app, ["forecast"])
    assert lauf.exit_code == 2
    assert "Betriebskonto" in lauf.output
