"""Der Kontostand eines Kontos, dessen Export keinen Saldo traegt.

Die Sparkasse-CSV hat keine Saldenspalte. Der Import schreibt `0` und die Summe
der Datei in den Auszug; als Kontostand las das jeder Leser (Stichtag, Konten-
Kacheln, Prognose-Start) -- und zeigte die Summe der letzten Datei. Seither
rechnet `finctl/ledger/kontostand.py` von einem Stand, den der Nutzer einmal aus
dem Online-Banking abschreibt.

Die Umsaetze sind die der erfundenen Datei sparkasse_camt_v2.csv, in Cent:
02.09. +120000, 10.09. -5350, 15.09. -150000, 28.09. -8500, 29.09. +240000.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from finctl.forecast.stichtag import saldo_zum as stichtag_saldo
from finctl.ingest.importer import import_statement
from finctl.ledger import kontostand
from finctl.ledger.db import connect, init_db

WURZEL = Path(__file__).resolve().parent.parent
BEISPIEL = WURZEL / "tests" / "beispiele" / "banken" / "sparkasse_camt_v2.csv"


def _tag(text: str) -> date:
    return date.fromisoformat(text)


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "ledger.db"
    init_db(db)
    c = connect(db)
    c.execute(
        "INSERT INTO accounts (id, display_name, institution, account_type,"
        " ingest_mode, parser_profile) VALUES ('giro', 'Giro', 'Sparkasse', 'giro',"
        " 'parsed', 'sparkasse_csv')")
    assert import_statement(c, BEISPIEL, "giro").transactions == 5
    return c


def _anker(conn, tag: str, cents: int):
    conn.execute("INSERT INTO balance_snapshots (account_id, as_of, balance_cents, source)"
                 " VALUES ('giro', ?, ?, 'manual')", (tag, cents))


def test_the_import_marks_the_statement_as_without_balance(conn):
    assert kontostand.ohne_saldo(conn, "giro")
    assert kontostand.konten_ohne_saldo(conn) == {"giro"}


def test_without_an_anchor_the_balance_is_unknown_not_the_sum_of_the_file(conn):
    """Der Auszug sagt 196150 Cent -- aber das ist nur die Summe, kein Kontostand."""
    assert conn.execute("SELECT balance_end_cents FROM statements").fetchone()[0] == 196150
    assert kontostand.saldo_zum(conn, "giro", _tag("2026-09-30")) is None
    assert stichtag_saldo(conn, "giro", _tag("2026-09-30")) is None
    assert kontostand.braucht_anker(conn, "giro")


def test_an_anchor_before_the_bookings_counts_them_forward(conn):
    _anker(conn, "2026-09-01", 100000)
    assert kontostand.saldo_zum(conn, "giro", _tag("2026-09-01")) == 100000
    assert kontostand.saldo_zum(conn, "giro", _tag("2026-09-15")) == 100000 + 120000 - 5350 - 150000
    assert kontostand.saldo_zum(conn, "giro", _tag("2026-09-30")) == 100000 + 196150
    assert not kontostand.braucht_anker(conn, "giro")


def test_an_anchor_after_the_bookings_counts_them_back(conn):
    _anker(conn, "2026-10-05", 500000)
    assert kontostand.saldo_zum(conn, "giro", _tag("2026-10-05")) == 500000
    # Was nach dem 15.09. gebucht wurde (-85 und +2.400), geht vom Stand ab.
    assert kontostand.saldo_zum(conn, "giro", _tag("2026-09-15")) == 500000 - (-8500 + 240000)
    assert kontostand.saldo_zum(conn, "giro", _tag("2026-08-31")) == 500000 - 196150


def test_an_anchor_in_the_middle_works_in_both_directions(conn):
    """Der Stand gilt am Ende seines Tages: die Buchung vom 10.09. steckt schon in ihm."""
    _anker(conn, "2026-09-10", 300000)
    assert kontostand.saldo_zum(conn, "giro", _tag("2026-09-10")) == 300000
    assert kontostand.saldo_zum(conn, "giro", _tag("2026-09-28")) == 300000 - 150000 - 8500
    assert kontostand.saldo_zum(conn, "giro", _tag("2026-09-02")) == 300000 + 5350


def test_of_two_anchors_the_youngest_before_the_day_counts_else_the_next_after(conn):
    _anker(conn, "2026-09-01", 100000)
    _anker(conn, "2026-09-20", 111111)
    assert kontostand.saldo_zum(conn, "giro", _tag("2026-09-28")) == 111111 - 8500
    assert kontostand.saldo_zum(conn, "giro", _tag("2026-09-10")) == 100000 + 120000 - 5350
    # Vor beiden Staenden gilt der naechste danach.
    assert kontostand.saldo_zum(conn, "giro", _tag("2026-08-20")) == 100000


def test_the_stichtag_reads_the_balance_from_the_anchor(conn):
    _anker(conn, "2026-09-01", 100000)
    assert stichtag_saldo(conn, "giro", _tag("2026-09-30")) == 296150


def test_an_account_with_a_balance_is_not_touched(conn):
    """Ein Auszug mit Saldo gilt, auch wenn daneben ein Stand eingetragen ist."""
    conn.execute(
        "INSERT INTO accounts (id, display_name, institution, account_type, ingest_mode,"
        " parser_profile) VALUES ('mit', 'Mit Saldo', 'Bank', 'giro', 'parsed', 'dkb_giro')")
    conn.execute(
        "INSERT INTO statements (account_id, source_path, source_name, file_sha256,"
        " period_start, period_end, balance_start_cents, balance_end_cents, parser_profile,"
        " parser_version, status, imported_at) VALUES ('mit', 'x', 'x', 'x', '2026-09-01',"
        " '2026-09-30', 1000, 2000, 'dkb_giro', '1', 'imported', 'x')")
    conn.execute("INSERT INTO balance_snapshots (account_id, as_of, balance_cents, source)"
                 " VALUES ('mit', '2026-09-01', 999999, 'manual')")
    assert not kontostand.ohne_saldo(conn, "mit")
    assert stichtag_saldo(conn, "mit", _tag("2026-09-30")) == 2000
    assert not kontostand.braucht_anker(conn, "mit")


def test_the_monthly_close_keeps_the_row_open_until_a_balance_is_entered(conn):
    from finctl import monatsabschluss

    heute = date(2026, 10, 5)
    zeile = next(p for p in monatsabschluss.konten(conn, heute, "2026-10") if p.id == "konto:giro")
    assert not zeile.erledigt
    assert zeile.hinweis == "Stand fehlt: einmal eintragen"

    _anker(conn, "2026-09-30", 296150)
    zeile = next(p for p in monatsabschluss.konten(conn, heute, "2026-10") if p.id == "konto:giro")
    assert "Stand fehlt" not in zeile.hinweis


# ------------------------------------------------------------- Ende zu Ende

_PROBE = r"""
import json, pathlib, re, shutil, tempfile
from finctl.web import auth
auth.PFAD = pathlib.Path(tempfile.mkdtemp()) / "server.yaml"
from fastapi.testclient import TestClient
from finctl.web.server import app
from finctl import bestaende
from finctl.ledger import db as ledger
from finctl.web.basis import conn as verbindung
from finctl.web.routen.start import _kacheln

cl = TestClient(app, raise_server_exceptions=False)
datei = pathlib.Path("tests/beispiele/banken/sparkasse_camt_v2.csv").read_bytes()
aus = {}
r = cl.post("/api/konto-neu", json={
    "id": "sparkasse-giro", "display_name": "Sparkasse Giro", "institution": "Sparkasse",
    "account_type": "giro", "iban": "DE89370400440532013000", "ingest_mode": "parsed",
    "parser_profile": "sparkasse_csv", "statement_folder": "sparkasse-giro"})
aus["konto"] = r.status_code
r = cl.post("/api/einlesen/ablegen", files={"datei": ("umsaetze.csv", datei, "text/csv")},
            data={"konto": "sparkasse-giro"})
aus["ablegen"] = r.status_code
aus["update"] = cl.post("/api/update").status_code


def seite():
    t = re.sub(r"<[^>]+>", " ", cl.get("/monatsabschluss").text)
    return re.sub(r"\s+", " ", t)


def kachel():
    c = verbindung()
    try:
        return [k for k in _kacheln(c, "2026")["konten"] if k["id"] == "sparkasse-giro"][0]
    finally:
        c.close()


aus["vorher_hinweis"] = "Stand fehlt: einmal eintragen" in seite()
aus["vorher_kachel"] = kachel()["balance_cents"]
# Auch mit nur der Basis (Modul Bestaende aus) laesst sich der Stand eintragen.
html = cl.get("/monatsabschluss").text
aus["feld"] = 'placeholder="Stand laut Online-Banking"' in html
aus["vorher_gap"] = len(ledger.statement_chain_gaps(ledger.connect()))

# Kontostand laut Online-Banking am 30.09.: 5.000 Euro. Die Seite fuehrt den Eintrag an.
r = cl.post("/api/bestand", json={"key": "sparkasse-giro", "cents": 500000, "as_of": "2026-09-30"})
aus["speichern"] = [r.status_code, r.json()]
aus["nachher_hinweis"] = "Stand fehlt: einmal eintragen" in seite()
aus["nachher_kachel"] = kachel()["balance_cents"]
c = verbindung()
aus["staende"] = bestaende.auszugsstaende(c, ["sparkasse-giro"])["sparkasse-giro"]
c.close()
aus["yaml"] = [b for b in bestaende.lesen()["balances"] if b.get("account_id") == "sparkasse-giro"]
print("###" + json.dumps(aus, default=str))
"""


def test_a_new_user_enters_the_balance_once_and_every_reader_follows(tmp_path):
    daten = tmp_path / "daten"
    daten.mkdir()
    system = {k: v for k, v in os.environ.items()
              if k.upper() in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT")}
    umgebung = {**system, "PATH": "/usr/bin:/bin", "HOME": str(daten),
                "USERPROFILE": str(daten), "APPDATA": str(daten / "appdata"),
                "FINCTL_DATEN": str(daten)}
    init = subprocess.run([sys.executable, "-m", "finctl.cli", "init"], cwd=WURZEL,
                          env=umgebung, capture_output=True, text=True, check=False)
    assert init.returncode == 0, init.stderr
    lauf = subprocess.run([sys.executable, "-c", _PROBE], cwd=WURZEL, env=umgebung,
                          capture_output=True, text=True, check=False)
    assert "###" in lauf.stdout, lauf.stderr[-2000:]
    aus = json.loads(lauf.stdout.split("###", 1)[1].splitlines()[0])

    assert (aus["konto"], aus["ablegen"], aus["update"]) == (200, 200, 200)
    # Ohne Eintrag: ein Hinweis, kein falscher Stand, keine Luecke.
    assert aus["vorher_hinweis"] and aus["feld"]
    assert aus["vorher_kachel"] is None
    assert aus["vorher_gap"] == 0
    # Mit Eintrag: der Stand ist der eingetragene plus die Umsaetze danach (keine).
    assert aus["speichern"][0] == 200, aus["speichern"]
    assert not aus["nachher_hinweis"]
    assert aus["nachher_kachel"] == 500000 + 0
    assert aus["staende"]["ohne_saldo"] is True
    assert aus["staende"]["anker_cents"] == 500000 and aus["staende"]["anker_as_of"] == "2026-09-30"
    assert [b["cents"] for b in aus["yaml"]] == [500000]
