"""Bestehende Datenordner nachfuehren (Schritt 4.6).

Seit 4.3 kennt der Code das Merkmal `einmalig` und die Spalte
`mgmt_categories.einmalig`. Ein Datenordner, der davor entstand, hat beides
nicht, und die Startvorlage erreicht ihn nicht (sie wird nur kopiert, wo eine
Datei fehlt). Ohne Nachfuehren scheitert ein Lauf an "no such column", und
laeuft er, bleibt der Block `einmalig` leer.

Alles hier ist erfunden und rund; die Tests schreiben in Wegwerfordner.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest
import yaml
from typer.testing import CliRunner

from finctl import nachfuehren as nf
from finctl.forecast import messung
from finctl.ledger import db as ledger
from finctl.ledger.db import connect, init_db
from finctl.tax import taxonomy as tx

# Eine Taxonomie, wie sie vor 4.3 aussah: die Kaufnebenkosten ohne das Merkmal, ein Wort
# `einmalig` in einer Notiz. Seit Schritt 5 stehen die Begruendungen als Notizen in den
# Daten (ein Neuschreiben der Datei verliert nichts); `ALT_MIT_KOMMENTAR` ist die Form davor.
ALT = """\
management:
  wohnen:
    name: Wohnen
    kind: expense
    children:
      miete: {name: Miete, fix: true}
  immobilie:
    name: Immobilie
    kind: expense
    children:
      kaufnebenkosten: {name: Kaufnebenkosten}
      sonstiges: {name: Sonstiges}
    notiz: "`kaufnebenkosten`: Eine Anschaffung ist einmalig, aber das Wort ist kein Merkmal."
notizen:
  bereich:
    notiz: Der Kategoriebaum.
"""
ALT_MIT_KOMMENTAR = """\
# Der Kategoriebaum.
management:
  wohnen:
    name: Wohnen
    kind: expense
    children:
      miete: {name: Miete, fix: true}
  immobilie:
    name: Immobilie
    kind: expense
    children:
      # Eine Anschaffung ist einmalig, aber das Wort im Kommentar ist kein Merkmal.
      kaufnebenkosten: {name: Kaufnebenkosten}
      sonstiges: {name: Sonstiges}
"""


#: `ALT`, in der das Merkmal schon steht -- ein Haushalt auf dem Stand.
NEU = ALT.replace("{name: Kaufnebenkosten}", "{name: Kaufnebenkosten, einmalig: true}")


def _mit_merkmal(text: str) -> dict:
    """Die Taxonomie `text` so, wie sie nach dem Nachfuehren gelesen wird."""
    spec = yaml.safe_load(text)
    spec["management"]["immobilie"]["children"]["kaufnebenkosten"] = {
        "name": "Kaufnebenkosten", "einmalig": True}
    return spec


def _gelesen(tmp_path) -> dict:
    return yaml.safe_load((tmp_path / "config" / "taxonomy.yaml").read_text(encoding="utf-8"))


def _taxonomie(tmp_path, text: str):
    (tmp_path / "config").mkdir(exist_ok=True)
    pfad = tmp_path / "config" / "taxonomy.yaml"
    pfad.write_text(text, encoding="utf-8")
    return pfad


# ------------------------------------------------------------ taxonomy.yaml


def test_a_taxonomy_without_the_flag_gets_it_on_kaufnebenkosten_only(tmp_path):
    pfad = _taxonomie(tmp_path, ALT)
    meldung = nf.taxonomie(tmp_path / "config")
    assert len(meldung) == 1 and "immobilie/kaufnebenkosten" in meldung[0]
    # Nur dieses Merkmal ist neu; die Notizen stehen noch da.
    assert yaml.safe_load(pfad.read_text(encoding="utf-8")) == _mit_merkmal(ALT)


def test_the_second_run_changes_nothing(tmp_path):
    pfad = _taxonomie(tmp_path, ALT)
    nf.taxonomie(tmp_path / "config")
    stand = pfad.stat().st_mtime_ns, pfad.read_bytes()
    assert nf.taxonomie(tmp_path / "config") == []
    assert (pfad.stat().st_mtime_ns, pfad.read_bytes()) == stand


def test_a_word_in_a_note_is_not_the_flag(tmp_path):
    """`ALT` sagt `einmalig` in einer Notiz; trotzdem fehlt das Merkmal."""
    _taxonomie(tmp_path, ALT)
    assert "einmalig" in ALT
    assert nf.taxonomie(tmp_path / "config")


def test_a_bare_name_is_wrapped_in_a_mapping(tmp_path):
    pfad = _taxonomie(tmp_path, ALT.replace("{name: Kaufnebenkosten}", "Kaufnebenkosten"))
    assert nf.taxonomie(tmp_path / "config")
    assert yaml.safe_load(pfad.read_text(encoding="utf-8")) == _mit_merkmal(ALT)


@pytest.mark.parametrize("text", [
    # der Haushalt hat entschieden: nein
    ALT.replace("{name: Kaufnebenkosten}", "{name: Kaufnebenkosten, einmalig: false}"),
    # ... oder kennt das Merkmal an anderer Stelle
    ALT.replace("{name: Sonstiges}", "{name: Sonstiges, einmalig: true}"),
])
def test_a_household_that_knows_the_flag_is_left_alone(tmp_path, text):
    pfad = _taxonomie(tmp_path, text)
    assert nf.taxonomie(tmp_path / "config") == []
    assert pfad.read_text(encoding="utf-8") == text


def test_a_flag_on_the_parent_counts_too(tmp_path):
    text = ALT.replace("  immobilie:\n    name: Immobilie\n",
                       "  immobilie:\n    name: Immobilie\n    einmalig: true\n")
    pfad = _taxonomie(tmp_path, text)
    assert nf.taxonomie(tmp_path / "config") == []
    assert pfad.read_text(encoding="utf-8") == text


def test_a_form_it_cannot_edit_is_reported_and_not_guessed(tmp_path):
    text = ALT.replace("kaufnebenkosten: {name: Kaufnebenkosten}",
                       "kaufnebenkosten: [Kaufnebenkosten]")
    pfad = _taxonomie(tmp_path, text)
    [meldung] = nf.taxonomie(tmp_path / "config")
    assert "von Hand" in meldung and "immobilie/kaufnebenkosten" in meldung
    assert pfad.read_text(encoding="utf-8") == text


def test_a_block_style_category_is_edited_too(tmp_path):
    pfad = _taxonomie(tmp_path, ALT.replace("kaufnebenkosten: {name: Kaufnebenkosten}",
                                            "kaufnebenkosten:\n        name: Kaufnebenkosten"))
    assert nf.taxonomie(tmp_path / "config")
    assert yaml.safe_load(pfad.read_text(encoding="utf-8")) == _mit_merkmal(ALT)


def test_a_file_with_comments_that_needs_nothing_is_left_alone(tmp_path):
    """Hat die Datei das Merkmal, gibt es nichts zu schreiben.

    Angehalten wird an den Stellen, die es rufen, nicht hier (`test_umstellen.py`).
    """
    text = ALT_MIT_KOMMENTAR.replace("{name: Kaufnebenkosten}",
                                     "{name: Kaufnebenkosten, einmalig: true}")
    pfad = _taxonomie(tmp_path, text)
    assert nf.taxonomie(tmp_path / "config") == []
    assert pfad.read_text(encoding="utf-8") == text


def test_the_app_start_stops_on_a_file_with_comments(tmp_path, monkeypatch):
    """`beim_start` ist der Weg der App: Die Anwendung kommt gar nicht hoch."""
    from finctl import pfade
    from finctl.umstellen import AlteFormError

    pfad = _taxonomie(tmp_path, ALT_MIT_KOMMENTAR)
    init_db(tmp_path / "t.db")
    monkeypatch.setattr(nf, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(pfade, "DB_PATH", tmp_path / "t.db")
    with pytest.raises(AlteFormError, match=r"taxonomy\.yaml"):
        nf.beim_start()
    assert pfad.read_text(encoding="utf-8") == ALT_MIT_KOMMENTAR

    pfad.write_text(ALT, encoding="utf-8")     # umgestellt: die App fuehrt nach
    assert nf.beim_start()


def test_nothing_happens_without_the_file_or_the_category(tmp_path):
    assert nf.taxonomie(tmp_path / "config") == []
    pfad = _taxonomie(tmp_path, ALT.replace("kaufnebenkosten", "nebenkosten"))
    assert nf.taxonomie(tmp_path / "config") == []
    assert "einmalig: true" not in pfad.read_text(encoding="utf-8")


# ------------------------------------------------------------------ Spalte


def _alt(tmp_path, taxonomie_text: str = ALT):
    """Ein Haushalt, wie er vor 4.3 war: Kategorien geladen, Spalte noch nicht da."""
    pfad = init_db(tmp_path / "alt.db")
    c = connect(pfad)
    spec = _taxonomie(tmp_path, taxonomie_text)
    tx.load_into_db(c, spec)
    c.execute("INSERT INTO accounts (id, display_name, institution, account_type, "
              "ingest_mode, parser_profile) VALUES ('a','A','X','giro','parsed','p')")
    c.execute("INSERT INTO statements (id, account_id, source_path, source_name, file_sha256, "
              "period_start, period_end, balance_start_cents, balance_end_cents, "
              "parser_profile, parser_version, status, imported_at) "
              "VALUES (1,'a','x','x','sha','2026-03-01','2026-03-31',0,0,'p','1','imported','now')")
    c.execute("INSERT INTO transactions (account_id, statement_id, booking_date, amount_cents, "
              "counterparty_norm, raw_text, seq_in_statement, dedup_hash, created_at) "
              "VALUES ('a',1,'2026-03-03',-2000000,'notar','x',1,'h1','now')")
    c.execute("INSERT INTO splits (transaction_id, amount_cents, mgmt_category_id, source, "
              "created_at, updated_at) VALUES (1,-2000000,'immobilie/kaufnebenkosten',"
              "'rule','now','now')")
    c.commit()
    c.execute("ALTER TABLE mgmt_categories DROP COLUMN einmalig")
    c.commit()
    c.close()
    return pfad


def _spalten(pfad) -> set[str]:
    c = sqlite3.connect(pfad)
    try:
        return {r[1] for r in c.execute("PRAGMA table_info(mgmt_categories)")}
    finally:
        c.close()


def test_connect_adds_a_column_an_older_ledger_does_not_have(tmp_path):
    pfad = _alt(tmp_path)
    assert "einmalig" not in _spalten(pfad)
    c = connect(pfad)
    assert c.execute("SELECT COUNT(*) FROM mgmt_categories WHERE einmalig = 1").fetchone()[0] == 0
    c.close()
    assert "einmalig" in _spalten(pfad)
    connect(pfad).close()  # ein zweites Mal ist nichts mehr zu tun


def test_a_second_process_adding_the_column_first_is_no_error(tmp_path):
    """Zwischen dem Nachsehen und dem ALTER war ein anderer Prozess schneller."""
    pfad = init_db(tmp_path / "t.db")

    class Veraltet(sqlite3.Connection):
        def execute(self, sql, *args):
            if sql.startswith("PRAGMA table_info(mgmt_categories)"):
                zeilen = list(super().execute(sql, *args))
                return iter([z for z in zeilen if z[1] != "einmalig"])
            return super().execute(sql, *args)

    c = sqlite3.connect(pfad, factory=Veraltet)
    ledger._add_missing_columns(c)  # sah die Spalte nicht, ALTER meldet "duplicate column"
    c.close()


def test_connect_still_raises_what_is_not_a_race(tmp_path):
    pfad = init_db(tmp_path / "t.db")
    c = sqlite3.connect(pfad)
    c.execute("ALTER TABLE mgmt_categories DROP COLUMN einmalig")
    c.commit()
    c.execute("PRAGMA query_only = ON")
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        ledger._add_missing_columns(c)
    c.close()


# ------------------------------------------------------------- Ende zu Ende


def _block(c) -> dict[tuple[str, str], int]:
    return messung.summiere(messung.monatssummen(c, von=date(2026, 1, 1), je_block=True),
                            lambda z: (z.block, z.kategorie))


def test_an_old_household_is_brought_forward_and_counts_the_same(tmp_path, monkeypatch):
    """Eine Anschaffung zaehlt im Block `einmalig`, wie vor der Nachfuehrung nicht."""
    pfad = _alt(tmp_path)
    c = connect(pfad)

    # Gemessen wie vorher: ohne das Merkmal steht die Anschaffung in einem Block der Kosten.
    assert ("einmalig", "immobilie/kaufnebenkosten") not in _block(c)

    meldungen = nf.daten(c, tmp_path / "config")
    assert len(meldungen) == 2
    assert "taxonomy.yaml" in meldungen[0] and "neu geladen" in meldungen[1]
    assert _block(c) == {("einmalig", "immobilie/kaufnebenkosten"): -2_000_000}
    assert c.execute("SELECT id FROM mgmt_categories WHERE einmalig = 1").fetchall()[0][0] \
        == "immobilie/kaufnebenkosten"

    # Ein Haushalt auf dem Stand: nichts mehr zu melden, nichts neu zu laden.
    assert nf.daten(c, tmp_path / "config") == []
    c.close()


def test_a_ledger_that_already_has_the_rows_is_not_reloaded(tmp_path, monkeypatch):
    pfad = init_db(tmp_path / "t.db")
    c = connect(pfad)
    spec = _taxonomie(tmp_path, NEU)
    tx.load_into_db(c, spec)

    def nie(*_a, **_k):
        raise AssertionError("die Kategorien sind schon geladen")

    monkeypatch.setattr(tx, "load_into_db", nie)
    assert nf.daten(c, tmp_path / "config") == []
    c.close()


def test_a_ledger_without_schema_is_left_to_init(tmp_path):
    _taxonomie(tmp_path, NEU)
    c = sqlite3.connect(tmp_path / "leer.db")
    assert nf.daten(c, tmp_path / "config") == []
    c.close()


# ------------------------------------------------- Die Stellen, die es rufen


def test_a_command_that_needs_the_ledger_brings_the_household_forward(tmp_path, monkeypatch):
    from finctl import cli

    pfad = _alt(tmp_path)
    monkeypatch.setattr(cli, "DB_PATH", pfad)
    monkeypatch.setattr(cli, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(nf, "CONFIG_DIR", tmp_path / "config")
    lauf = CliRunner().invoke(cli.app, ["status", "--json"])
    assert lauf.exit_code == 0, lauf.output
    assert "Nachgefuehrt: config/taxonomy.yaml" in lauf.output
    assert _gelesen(tmp_path) == _mit_merkmal(ALT)


def test_init_reports_what_it_brought_forward(tmp_path, monkeypatch):
    from finctl import cli, module

    pfad = _alt(tmp_path)
    monkeypatch.setattr(cli, "DB_PATH", pfad)
    monkeypatch.setattr(cli, "CONFIG_DIR", tmp_path / "config")
    # `init` schreibt die Schalterdatei der Module an `module.CONFIG_DIR`, nicht in den
    # Ordner, den es bekommt (`module.erststart`): ohne das stuende sie in der Testkopie.
    monkeypatch.setattr(module, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(nf, "CONFIG_DIR", tmp_path / "config")
    lauf = CliRunner().invoke(cli.app, ["init", "--json"])
    assert lauf.exit_code == 0, lauf.output
    assert "nachgefuehrt" in lauf.output and "immobilie/kaufnebenkosten" in lauf.output
    assert (tmp_path / "config" / "module_custom.yaml").exists()  # und nicht in der Testkopie
    assert _gelesen(tmp_path) == _mit_merkmal(ALT)


def test_the_app_brings_the_household_forward_when_it_starts_and_not_when_it_is_imported(
        tmp_path, monkeypatch, capsys):
    from fastapi.testclient import TestClient

    from finctl import pfade
    from finctl.web import server

    pfad = _alt(tmp_path)
    monkeypatch.setattr(pfade, "DB_PATH", pfad)
    monkeypatch.setattr(nf, "CONFIG_DIR", tmp_path / "config")

    TestClient(server.app)  # ohne `with` laeuft kein Start
    assert (tmp_path / "config" / "taxonomy.yaml").read_text(encoding="utf-8") == ALT

    with TestClient(server.app):
        pass
    assert _gelesen(tmp_path) == _mit_merkmal(ALT)
    assert "Nachgefuehrt" in capsys.readouterr().out


def test_starting_without_a_ledger_does_nothing(tmp_path, monkeypatch):
    from finctl import pfade

    monkeypatch.setattr(pfade, "DB_PATH", tmp_path / "gibt_es_nicht.db")
    assert nf.beim_start() == []
    assert not (tmp_path / "gibt_es_nicht.db").exists()
