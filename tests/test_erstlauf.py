"""Der erste Start: ein leerer Datenordner, und die App laeuft.

Gemessen statt angenommen: `finctl init` lief gegen einen leeren Ordner
sauber durch, und danach warf die STARTSEITE einen 500er, weil
`balances.yaml` fehlte -- ebenso /ziele, /planung, /annahmen und /regeln.
Sechs von zwoelf Seiten kamen durch. Wer das Werkzeug uebernimmt, sieht als
Erstes einen Absturz.

Zweiter Befund, 24.09.2026: Laufen ist nicht dasselbe wie BENUTZBAR. Alle
Seiten antworteten, aber ohne Kategoriebaum liess sich keine einzige Buchung
zuordnen. Deshalb prueft dieser Test seither beides.

Die Pruefung laeuft in einem eigenen Prozess: `FINCTL_DATEN` wird beim
Import gelesen, im laufenden Prozess ist finctl laengst geladen.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent

_PROBE = r"""
import json, pathlib, re, tempfile, sys
from finctl.web import auth
auth.PFAD = pathlib.Path(tempfile.mkdtemp()) / "server.yaml"
from fastapi.testclient import TestClient
from finctl import module
from finctl.web.server import app

# Ein Neuling beginnt mit der Basis und schaltet Module nach und nach dazu.
# Keine Seite darf dann abstuerzen -- also alle einmal eingeschaltet.
module.setzen({m.id: True for m in module.MODULE})
cl = TestClient(app, raise_server_exceptions=False)
# Aus der VORLAGE, nicht aus der laufenden Startseite: genau wenn die Seite
# abstuerzt, gibt es keinen Kopf mehr, aus dem sich die Ziele lesen liessen.
vorlage = pathlib.Path("finctl/web/templates/base.html").read_text(encoding="utf-8")
kopf = vorlage[vorlage.index("<header>"):vorlage.index("</header>")]
ziele = ["/"] + re.findall(r'href="(/[^"{]*)"', kopf)

ergebnis = {}
for ziel in dict.fromkeys(ziele):
    try:
        ergebnis[ziel] = cl.get(ziel).status_code
    except Exception as fehler:
        ergebnis[ziel] = f"{type(fehler).__name__}: {fehler}"
print("###" + json.dumps(ergebnis))
"""


@pytest.fixture(scope="module")
def frisch(tmp_path_factory):
    """Ein leerer Datenordner, einmal eingerichtet -- wie bei einem Neuling."""
    daten = tmp_path_factory.mktemp("fos-daten")
    # So wenig wie moeglich -- aber was Windows selbst zum Starten braucht,
    # bleibt: ohne SYSTEMROOT laedt Python dort nicht einmal asyncio.
    system = {k: v for k, v in os.environ.items()
              if k.upper() in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT")}
    umgebung = {**system, "PATH": "/usr/bin:/bin", "HOME": str(daten),
                "USERPROFILE": str(daten), "APPDATA": str(daten / "appdata"),
                "FINCTL_DATEN": str(daten)}
    fertig = subprocess.run([sys.executable, "-m", "finctl.cli", "init"],
                            cwd=WURZEL, env=umgebung, capture_output=True,
                            text=True, check=False)
    assert fertig.returncode == 0, fertig.stderr
    return daten, umgebung


def test_init_creates_a_ledger_from_nothing(frisch):
    daten, _ = frisch
    assert (daten / "data" / "finance.db").exists()


def test_a_fresh_install_starts_with_the_base_alone(frisch):
    """Dreissig Seiten am ersten Tag sind keine Hilfe (finctl/module.py)."""
    import yaml

    daten, _ = frisch
    schalter = yaml.safe_load((daten / "config" / "module_custom.yaml").read_text(
        encoding="utf-8"))["module"]
    assert schalter and not any(schalter.values()), schalter


def test_a_fresh_install_can_actually_categorise(frisch):
    """Starten reicht nicht -- ohne Kategoriebaum laesst sich nichts zuordnen.

    Bis zum 24.09.2026 legte `init` vier Startdateien an, und die Taxonomie
    war keine davon: Die App lief, zeigte aber leere Auswahllisten, und wer
    sie uebernahm, konnte als Erstes gar nichts tun. Seither liegt der
    gewachsene Kategoriebaum als Vorlage bei.

    Geprueft wird die DATENBANK, nicht die Datei: eine Vorlage, die zwar
    kopiert wird, aber beim Laden durchfaellt, waere genauso nutzlos.
    """
    import sqlite3

    daten, _ = frisch
    assert (daten / "config" / "taxonomy.yaml").exists()

    conn = sqlite3.connect(daten / "data" / "finance.db")
    try:
        mgmt = conn.execute("SELECT COUNT(*) FROM mgmt_categories").fetchone()[0]
        steuer = conn.execute("SELECT COUNT(*) FROM tax_categories").fetchone()[0]
        # Und ein Teil der Kategorien traegt seine Steuerposition schon mit:
        # ein Baum ohne jede Zuordnung liesse die Anlage V von Hand fuellen.
        # Die Schranken unten sind bewusst weit unter dem Ist-Stand (110 / 46
        # / 19) -- sie sollen "die Vorlage kam leer an" fangen, nicht jede
        # Kategorie festnageln, die jemand spaeter streicht.
        verknuepft = conn.execute(
            "SELECT COUNT(*) FROM mgmt_categories "
            "WHERE default_tax_id IS NOT NULL").fetchone()[0]
    finally:
        conn.close()
    assert mgmt > 50, mgmt
    assert steuer > 20, steuer
    assert verknuepft > 10, verknuepft


def test_every_page_in_the_navigation_answers(frisch):
    """Keine Seite, die aus der Navigation erreichbar ist, darf beim ersten
    Start abstuerzen. Eine leere Seite ist eine Antwort, ein 500er nicht."""
    _, umgebung = frisch
    fertig = subprocess.run([sys.executable, "-c", _PROBE], cwd=WURZEL,
                            env=umgebung, capture_output=True, text=True,
                            check=False)
    assert "###" in fertig.stdout, fertig.stderr[-2000:]
    ergebnis = json.loads(fertig.stdout.split("###", 1)[1].splitlines()[0])

    assert len(ergebnis) > 10, f"zu wenige Seiten geprüft: {sorted(ergebnis)}"
    kaputt = {ziel: stand for ziel, stand in ergebnis.items() if stand != 200}
    assert not kaputt, (
        "Diese Seiten überleben den ersten Start nicht:\n  "
        + "\n  ".join(f"{ziel}: {stand}" for ziel, stand in sorted(kaputt.items())))


_PROBE_ERSTER_MONAT = r"""
import json, pathlib, re, shutil, tempfile
from finctl.web import auth
auth.PFAD = pathlib.Path(tempfile.mkdtemp()) / "server.yaml"
from fastapi.testclient import TestClient
from finctl import konten, module
from finctl.web.server import app

cl = TestClient(app, raise_server_exceptions=False)
ergebnis = {}
neu = cl.post("/api/konto-neu", json={
    "id": "giro-neu", "display_name": "Giro", "institution": "Sparkasse",
    "account_type": "giro", "ingest_mode": "parsed", "parser_profile": "sparkasse_csv"})
ergebnis["konto"] = neu.status_code
konto = next(k for k in konten.laden() if k["id"] == "giro-neu")
ordner = konten.auszugsordner(konto)
ordner.mkdir(parents=True, exist_ok=True)
shutil.copy("tests/beispiele/banken/sparkasse_csv.csv", ordner / "export.csv")

# Das ist der erste Klick jedes Neulings auf "Update": einlesen, Regeln anwenden, pruefen.
antwort = cl.post("/api/update")
ergebnis["update"] = antwort.status_code
ergebnis["update_text"] = antwort.text[:300]
if antwort.status_code == 200:
    ergebnis["importiert"] = antwort.json()["ingest"]["imported"]

# Und danach, mit Daten statt mit nichts: Basis allein, dann alles.
vorlage = pathlib.Path("finctl/web/templates/base.html").read_text(encoding="utf-8")
kopf = vorlage[vorlage.index("<header>"):vorlage.index("</header>")]
ziele = list(dict.fromkeys(["/"] + re.findall(r'href="(/[^"{]*)"', kopf)))
seiten, texte = {}, {}
for name, wahl in (("basis", {m.id: False for m in module.MODULE}),
                   ("alles", {m.id: True for m in module.MODULE})):
    module.setzen(wahl)
    for ziel in ziele:
        # Eine Seite eines ausgeschalteten Moduls gibt es nicht: 404 ist dort die richtige Antwort.
        erwartet = 200 if module.seite_an(ziel) else 404
        antwort_seite = cl.get(ziel)
        seiten[f"{name} {ziel}"] = [antwort_seite.status_code, erwartet]
        texte[f"{name} {ziel}"] = antwort_seite.text
ergebnis["seiten"] = seiten
# Was ein Neuling NICHT lesen soll: Urteile und Namen ohne Grundlage in seinen Daten.
ohne_grundlage = {
    "basis /monatsabschluss": ["keine eingeschaltet", "zwoelf", "Barista", "Cashflow ohne",
                               "PDFs", "note bad\">Die Einrichtung"],
    "alles /monatsabschluss": ["zwoelf", "Barista", "kein Barista", "note bad\">Die Einrichtung"],
    "alles /ziele": ["Wendepunkt"],
    "alles /konten": ["Gemeinschaftskonto"],
}
ergebnis["zu_viel"] = {k: [w for w in worte if w in texte.get(k, "")]
                       for k, worte in ohne_grundlage.items()}
print("###" + json.dumps(ergebnis))
"""


def test_the_first_update_and_every_page_afterwards_work(frisch):
    """Der erste Monat eines Neulings: Konto anlegen, Auszug einlesen, Update.

    Gemessen am 01.11.2026 in der App mit leerem Ordner: Das Konto liess sich
    anlegen, die Datei wurde erkannt -- und der erste Klick auf "Update" endete
    mit einem Datenbankfehler. Die mitgelieferte Grundschicht der Regeln trug
    eine Herkunft, die die Tabelle `rules` nicht kennt; wer sie an hat (die
    Voreinstellung), kam nie ueber das erste Update hinaus. Alle anderen Tests
    liefen ohne Grundschicht oder ohne Update und merkten nichts.
    """
    _, umgebung = frisch
    fertig = subprocess.run([sys.executable, "-c", _PROBE_ERSTER_MONAT], cwd=WURZEL,
                            env=umgebung, capture_output=True, text=True, check=False)
    assert "###" in fertig.stdout, fertig.stderr[-2000:]
    ergebnis = json.loads(fertig.stdout.split("###", 1)[1].splitlines()[0])

    assert ergebnis["konto"] == 200, ergebnis
    assert ergebnis["update"] == 200, ergebnis["update_text"]
    assert ergebnis["importiert"] == 1, ergebnis
    kaputt = {z: s[0] for z, s in ergebnis["seiten"].items() if s[0] != s[1]}
    assert not kaputt, "Mit Daten antworten diese Seiten nicht:\n  " + "\n  ".join(
        f"{z}: {s}" for z, s in sorted(kaputt.items()))
    zu_viel = {k: w for k, w in ergebnis["zu_viel"].items() if w}
    assert not zu_viel, f"Das gehoert nicht in die ersten Tage eines Neulings: {zu_viel}"
