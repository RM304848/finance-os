"""Eine Notiz am falschen Ort aendert keine Zahl (Schritt 5, N.1).

Eine Notiz gehoert an einen Eintrag mit Kennung oder unter `notizen:`. Es gibt
Zuordnungen, deren Schluessel selbst die Daten sind -- das Budget je Konto, die Blaetter einer
Kategorie, `remap`, die Zeilen der Zinssaetze, die Schreibweisen der Reihen, `overrides` und
`enden` der Prognose. (Die Einstellungen von `settings_custom.yaml` waren eine, bis N.3f sie in
`assumptions.yaml` legte; dort sind die Pfade benannt.) Ein Schluessel `notiz`
dort waere ein Konto, eine Kategorie, eine Einstellung. Die Leser dieser Zuordnungen
lassen die Schluessel einer Notiz weg (`notizen.ohne`); hier steht fuer jede, dass es so ist.

Die Tabelle "Leser" in `docs/schritt5_notizen.md` (N.0) ist die Vorlage. Jede Zeile hat hier
einen Test, in dem derselbe Inhalt mit und ohne `notiz` dasselbe liefert.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from finctl import kontenregeln, notizen, reihen, zinssaetze
from finctl.forecast import konten as prognose_konten
from finctl.ledger.db import connect, init_db
from finctl.tax import taxonomy as tx

#: Was nirgends als Wert gelesen werden darf.
FALSCH = {"notiz": "gehoert nicht hierher", "notiz_vom": "2026-10-05",
          "notizen": {"bereich": {"notiz": "auch nicht"}}}


def _datei(pfad: Path, inhalt: dict) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(yaml.safe_dump(inhalt, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return pfad


def test_forecast_overrides_and_ends_ignore_a_note():
    # `int("gehoert nicht hierher")` und `date.fromisoformat(...)` scheiterten.
    sauber = {"overrides": {"wohnen/miete": 100_000}, "enden": {"abo/alt": "2027-03"}}
    falsch = {"overrides": {**sauber["overrides"], **FALSCH},
              "enden": {**sauber["enden"], **FALSCH}}
    assert (prognose_konten._income_overrides(falsch, 2026)
            == prognose_konten._income_overrides(sauber, 2026))
    assert prognose_konten._enden(falsch) == prognose_konten._enden(sauber)
    assert set(prognose_konten._enden(falsch)) == {"abo/alt"}


def test_a_budget_per_account_is_not_an_account_called_note():
    spec = {"account_roles": {"giro": {"role": "operating", "notiz": "Warum"}, **FALSCH},
            "account_budgets": {"tag": 50_000, **FALSCH}}
    gelesen = kontenregeln.aus_spec(spec)
    assert gelesen["account_budgets"] == {"tag": 50_000}
    assert set(gelesen["account_roles"]) == {"giro"}


def test_the_account_rules_drop_a_note_in_their_mappings(tmp_path, monkeypatch):
    monkeypatch.setattr(kontenregeln, "CONFIG_DIR", tmp_path)
    _datei(tmp_path / "forecast.yaml", {
        "account_roles": {"giro": {"floor_cents": 1}, **FALSCH},
        "account_budgets": {"tag": 5, **FALSCH}})
    gelesen = kontenregeln.wirksam()
    assert gelesen["account_roles"] == {"giro": {"floor_cents": 1}}
    assert gelesen["account_budgets"] == {"tag": 5}


def test_a_category_leaf_called_note_is_no_category(tmp_path):
    basis = _datei(tmp_path / "taxonomy.yaml", {"management": {
        "alltag": {"name": "Alltag", "kind": "expense",
                   "children": {"markt": "Markt", "essen": "Essen", **FALSCH}}}})
    c = connect(init_db(tmp_path / "t.db"))
    tx.load_into_db(c, basis)
    ids = {r[0] for r in c.execute("SELECT id FROM mgmt_categories")}
    c.close()
    assert ids == {"alltag", "alltag/markt", "alltag/essen"}


def test_a_note_in_remap_is_no_renaming(tmp_path, monkeypatch):
    migrationen = _datei(tmp_path / "taxonomy_migrations.yaml", {
        "remap": {"alt/a": "neu/a", **FALSCH}, "retire": []})
    gesehen: list[dict] = []
    monkeypatch.setattr(tx, "remap_overrides", lambda remap, path=None: gesehen.append(remap) or 0)
    c = connect(init_db(tmp_path / "t.db"))
    tx.apply_migrations(c, migrationen)
    c.close()
    assert gesehen == [{"alt/a": "neu/a"}]


def test_a_note_in_the_interest_rates_is_no_account(tmp_path, monkeypatch):
    # `_satz` scheiterte an einem Text, wo eine Liste von Saetzen steht.
    monkeypatch.setattr(zinssaetze, "CONFIG_DIR", tmp_path)
    _datei(tmp_path / "zinssaetze_custom.yaml", {
        "zinssaetze": {"tag": [{"ab": "2026-01", "satz": 0.02}], **FALSCH}})
    assert set(zinssaetze.lesen()) == {"tag"}


def test_a_note_in_the_series_spellings_is_no_spelling(tmp_path, monkeypatch):
    monkeypatch.setattr(reihen, "CONFIG_DIR", tmp_path)
    _datei(tmp_path / reihen.DATEI, {"reihen": [], "zusammen": {"x gmbh": "x", **FALSCH}})
    assert reihen.zusammen() == {"x gmbh": "x"}


@pytest.mark.parametrize("wort", sorted(notizen.RESERVIERT))
def test_the_places_where_a_user_names_a_key_refuse_the_words_of_a_note(wort):
    """Wer einen Schluessel dieser Zuordnungen benennen kann, kann ihn nicht `notiz` nennen."""
    from finctl import konten

    fehler = konten.pruefen({"id": wort, "display_name": "A", "institution": "B",
                             "account_type": "giro", "ingest_mode": "summary"}, set())
    assert any("reserviert" in f for f in fehler)
    with pytest.raises(ValueError, match="reserviert"):
        tx.save("management", "alltag", wort, "Name", path=Path("/nicht/geschrieben"))
    from finctl import abos, kredite

    with pytest.raises(ValueError, match="Kennung"):
        abos.speichern({"id": wort, "name": "A"}, Path("/nicht/da"), Path("/nicht/da"))
    assert any("reserviert" in f for f in kredite.pruefen(
        {"id": wort, "name": "K", "lender": "B", "servicing_account_id": "giro",
         "segments": [{}]}, set()))
