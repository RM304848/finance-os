"""Die mitgelieferten allgemeinen Regeln: eine Grundschicht unter den eigenen.

Wer bei null anfaengt, hat sonst einen leeren Regelsatz und ordnet jede
Buchung von Hand zu. Die Grundschicht kennt oeffentliche Haendler, Dienste
und Behoerden -- und tritt hinter jede eigene Regel zurueck.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from finctl.rules import engine
from finctl.rules.engine import TxContext
from finctl.vorgaben import ORDNER


def _tx(text: str, cents: int = -1_000) -> TxContext:
    return TxContext(id=1, account_id="giro", booking_date="2026-01-15", amount_cents=cents,
                     raw_text=text, counterparty_norm="", counterparty_iban=None,
                     tx_type="")


def _regeln(tmp_path: Path, an: bool, eigene: str = "[]", aus: str | None = None):
    basis = tmp_path / "rules.yaml"
    ausgeblendet = f"allgemeine_regeln_aus: {aus}\n" if aus else ""
    basis.write_text(f"allgemeine_regeln: {'true' if an else 'false'}\n{ausgeblendet}\n"
                     f"rules: {eigene}\n", encoding="utf-8")
    return engine.load_rules(basis)


def test_the_layer_is_off_unless_the_rulebook_switches_it_on(tmp_path):
    """Ein aelterer Regelsatz ohne den Schalter bleibt, wie er war."""
    assert _regeln(tmp_path, an=False) == []
    an = _regeln(tmp_path, an=True)
    assert an and all(r.provenance == "allgemein" for r in an)
    assert min(r.priority for r in an) >= engine.GRUNDSCHICHT_ABSTAND


def test_every_own_rule_wins_whatever_its_priority(tmp_path):
    eigene = ('[{id: mein-laden, priority: 900, name: Mein Laden, '
              'match: {text: [REWE]}, set: {mgmt: konsum/sonstiges}}]')
    regeln = _regeln(tmp_path, an=True, eigene=eigene)
    treffer = engine.first_match(regeln, _tx("REWE Markt GmbH"), {})
    assert treffer.id == "mein-laden"


def test_an_own_rule_with_the_same_id_replaces_the_general_one(tmp_path):
    eigene = ('[{id: allg-supermarkt, priority: 60, name: Eigener Supermarkt, '
              'match: {text: [Hofladen]}, set: {mgmt: lebensmittel/supermarkt}}]')
    regeln = _regeln(tmp_path, an=True, eigene=eigene)
    [supermarkt] = [r for r in regeln if r.id == "allg-supermarkt"]
    assert supermarkt.provenance != "allgemein"


def test_a_general_rule_can_be_switched_off_on_its_own(tmp_path):
    regeln = _regeln(tmp_path, an=True, aus="[allg-supermarkt]")
    assert "allg-supermarkt" not in {r.id for r in regeln}
    assert "allg-supermarkt" in {r.id for r in _regeln(tmp_path, an=True)}


def test_the_page_changes_and_hides_general_rules_in_the_one_file(tmp_path):
    """Geaenderte mitgelieferte Regeln stehen ganz in der Datei, ausgeblendete in der Liste."""
    from finctl.rules import regelwerk as rw

    pfad = tmp_path / "rules.yaml"
    pfad.write_text("allgemeine_regeln: true\n\nrules: []\n", encoding="utf-8")
    vorher = {r["id"]: r for r in rw.laden(pfad)}
    assert "allg-supermarkt" in vorher

    # Ohne Aenderung bleibt die Datei, wie sie ist.
    e = {**rw.formwerte(vorher["allg-supermarkt"]), "id": "allg-supermarkt"}
    e, _ = rw.entwurf(e, pfad)
    rw.speichern(e, pfad)
    assert yaml.safe_load(pfad.read_text(encoding="utf-8"))["rules"] == []

    # Eine Aenderung macht sie zu einer Regel der Datei -- mit der Prioritaet, die galt.
    e = {**rw.formwerte(vorher["allg-supermarkt"]), "id": "allg-supermarkt", "name": "Meine Laeden"}
    e, _ = rw.entwurf(e, pfad)
    rw.speichern(e, pfad)
    [regel] = yaml.safe_load(pfad.read_text(encoding="utf-8"))["rules"]
    assert regel["name"] == "Meine Laeden"
    assert regel["priority"] == vorher["allg-supermarkt"]["priority"]
    assert regel["provenance"] == "allgemein"
    gilt = {r["id"]: r for r in rw.laden(pfad)}
    assert gilt["allg-supermarkt"]["name"] == "Meine Laeden"
    assert gilt["allg-supermarkt"]["herkunft"] == "basis"
    assert len([r for r in rw.laden(pfad) if r["id"] == "allg-supermarkt"]) == 1

    # Entfernen blendet sie aus, auch wenn eine Regel der Datei sie verdeckte.
    rw.entfernen("allg-supermarkt", pfad)
    spec = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    assert spec["rules"] == [] and spec["allgemeine_regeln_aus"] == ["allg-supermarkt"]
    assert "allg-supermarkt" not in {r["id"] for r in rw.laden(pfad)}
    assert "allg-gehalt" in {r["id"] for r in rw.laden(pfad)}


def test_every_general_rule_points_at_a_category_of_the_starting_tree():
    baum = yaml.safe_load((ORDNER / "taxonomy.yaml").read_text(encoding="utf-8"))["management"]
    bekannt = {f"{k}/{c}" for k, v in baum.items() for c in (v.get("children") or {})}
    regeln = engine.regeln_aus(engine.grundschicht())
    assert len({r.id for r in regeln}) == len(regeln)
    fremd = [r.id for r in regeln if r.actions.get("mgmt") not in bekannt]
    assert not fremd, fremd


def test_typical_statement_lines_land_where_expected():
    regeln = engine.regeln_aus(engine.grundschicht())

    def kategorie(text, cents=-1_000):
        r = engine.first_match(regeln, _tx(text, cents), {})
        return r.actions["mgmt"] if r else None

    assert kategorie("REWE Markt GmbH Filiale 1234") == "lebensmittel/supermarkt"
    assert kategorie("NETFLIX.COM") == "abo/video-streaming"
    assert kategorie("Lohn/Gehalt 01.2026", 300_000) == "einkommen/gehalt"
    assert kategorie("Kapitalertragsteuer", -1_234) == "steuern/kapitalertragsteuer"
    # Kurze Woerter, die in anderen stecken, stehen nicht in der Grundschicht.
    assert kategorie("Espresso Bar am Markt") is None
    assert kategorie("Normalpreis Kartenzahlung") is None


def test_switching_the_layer_keeps_the_notes_of_the_rulebook(tmp_path):
    pfad = tmp_path / "rules.yaml"
    pfad.write_text("rules:\n  - id: alpha\n    notiz: Warum diese Regel\n"
                    "    match: {text: [X]}\n    set: {mgmt: a/b}\n"
                    "notizen:\n  bereich:\n    notiz: Warum diese Regeln\n", encoding="utf-8")
    engine.grundschicht_setzen(True, pfad)
    assert engine.grundschicht_an(pfad)
    spec = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    assert spec["rules"][0]["notiz"] == "Warum diese Regel"
    assert spec["notizen"]["bereich"]["notiz"] == "Warum diese Regeln"
    assert next(iter(spec)) == "allgemeine_regeln"        # vor den Regeln, wie die Vorlage
    engine.grundschicht_setzen(False, pfad)
    assert not engine.grundschicht_an(pfad)
    assert pfad.read_text(encoding="utf-8").count("allgemeine_regeln") == 1
    assert yaml.safe_load(pfad.read_text(encoding="utf-8"))["rules"][0]["notiz"] == (
        "Warum diese Regel")


def test_the_layer_can_be_switched_on_in_a_file_that_does_not_exist_yet(tmp_path):
    pfad = tmp_path / "rules.yaml"
    engine.grundschicht_setzen(True, pfad)
    assert yaml.safe_load(pfad.read_text(encoding="utf-8")) == {
        "allgemeine_regeln": True, "rules": []}


def test_a_new_install_starts_with_the_layer_switched_on():
    assert yaml.safe_load((ORDNER / "rules.yaml").read_text(encoding="utf-8"))[
        "allgemeine_regeln"] is True


def test_a_general_rule_whose_category_was_deleted_is_left_out():
    """Wer eine Kategorie der Startvorlage loescht, bekommt keine Buchungen darauf."""
    import sqlite3

    from finctl.rules.categorize import ohne_fremde_kategorien

    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE mgmt_categories (id TEXT, active INTEGER)")
    c.execute("INSERT INTO mgmt_categories VALUES ('lebensmittel/supermarkt', 1)")
    rest = ohne_fremde_kategorien(c, engine.regeln_aus(engine.grundschicht()))
    assert {r.actions["mgmt"] for r in rest} == {"lebensmittel/supermarkt"}
