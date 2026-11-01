"""Einen bestehenden Datenordner auf den Stand dieses Codes bringen.

Die Startvorlagen (`vorgaben/`) kommen nur dorthin, wo eine Datei fehlt, und
eine vorhandene wird nie angefasst. Was der Code spaeter neu kennt, erreicht
einen Datenordner, der schon besteht, damit nicht. Gefunden bei 4.3: Das
Merkmal `einmalig` steht in der mitgelieferten Taxonomie, nicht in der eines
bestehenden Haushalts; der Block `einmalig` bliebe leer, und Hochrechnung,
Ziele und Treffer-Check zaehlten die Kaufnebenkosten wieder mit, ohne Hinweis.

Zwei Teile, beide ohne Folge fuer eine Zahl, wo der Datenordner schon auf dem
Stand ist:

* `taxonomie` -- `config/taxonomy.yaml` bekommt das Merkmal, wenn sie es
  nirgends kennt. Die Datei wird gelesen, ergaenzt und ganz geschrieben
  (`dateien.yaml_schreiben`); ihre Begruendungen stehen seit Schritt 5 als Notizen
  in den Daten.
* `daten` -- ruft `taxonomie` und laedt die Kategorien in die Datenbank, wenn
  die Taxonomie ein Merkmal nennt, das dort keine Zeile hat. (Die Spalte
  `mgmt_categories.einmalig` selbst legt `ledger.db.connect` an.)

Aufgerufen wird es an den Stellen, an denen ein Datenordner zum ersten Mal mit
neuem Code zusammentrifft: `finctl init`, jeder Befehl, der das Hauptbuch
braucht, und der Start der App. An denselben Stellen haelt die App vorher an, wenn
`finctl umstellen` in `config/` etwas faende (`umstellen.halt_wenn_offen`): Ein Neuschreiben
verwuerfe sonst Kommentare, die noch nicht Notizen sind, und eine Seitendatei, die niemand
mehr liest, wuerde still ueberstimmt.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from finctl import dateien
from finctl.pfade import CONFIG_DIR

#: Die Kategorie, die das Merkmal bekommt: eine Anschaffung geschieht einmal,
#: und was dort gebucht ist, kommt nicht wieder. Dieselbe wie in der
#: mitgelieferten Taxonomie (`vorgaben/taxonomy.yaml`).
ELTERN = "immobilie"
KIND = "kaufnebenkosten"
MERKMAL = "einmalig"


def _merkmale(spec: dict) -> list:
    """Die Werte, die das Merkmal in den Verwaltungskategorien hat (am Ast oder am Kind).

    Leer heisst: nirgends genannt. Auch `einmalig: false` ist eine Nennung: Dann
    hat der Haushalt es gesehen und entschieden. Ein Wort in einer Notiz zaehlt
    nicht, darum die gelesene Struktur.
    """
    werte = []
    for node in (spec.get("management") or {}).values():
        werte += [node[MERKMAL]] if MERKMAL in node else []
        for kind in (node.get("children") or {}).values():
            werte += [kind[MERKMAL]] if isinstance(kind, dict) and MERKMAL in kind else []
    return werte


def _mit_merkmal(kinder: dict) -> bool:
    """Das Merkmal an die Kategorie `KIND` setzen. `False`, wenn ihre Form fremd ist.

    Gekonnt sind die zwei Formen, die die Taxonomie benutzt: `{name: X, ...}`
    und der nackte Name. Alles andere ist von Hand zu setzen.
    """
    kind = kinder[KIND]
    if isinstance(kind, dict):
        kinder[KIND] = {**kind, MERKMAL: True}
    elif isinstance(kind, str):
        kinder[KIND] = {"name": kind, MERKMAL: True}
    else:
        return False
    return True


def taxonomie(config_dir: Path | None = None) -> list[str]:
    """`taxonomy.yaml` das Merkmal geben, wenn sie es nirgends kennt.

    Gibt zurueck, was zu melden ist: eine Zeile, wenn die Datei geaendert
    wurde, oder eine Zeile mit der Bitte, es von Hand zu tun. Leer, wenn
    nichts zu tun ist.
    """
    pfad = (config_dir or CONFIG_DIR) / "taxonomy.yaml"
    if not pfad.exists():
        return []
    spec = dateien.yaml_lesen(pfad) or {}
    if _merkmale(spec):
        return []
    kinder = (((spec.get("management") or {}).get(ELTERN) or {}).get("children"))
    if not isinstance(kinder, dict) or KIND not in kinder:
        return []  # die Kategorie gibt es in diesem Haushalt nicht
    if not _mit_merkmal(kinder):
        von_hand = (f"config/taxonomy.yaml: {ELTERN}/{KIND} braucht `{MERKMAL}: true`, "
                    "und die Zeile ist nicht in einer Form, die sich selbst aendern laesst. "
                    "Bitte von Hand eintragen.")
        return [von_hand]
    dateien.yaml_schreiben(pfad, spec)
    return [f"config/taxonomy.yaml: {ELTERN}/{KIND} traegt jetzt `{MERKMAL}: true`"]


def daten(conn: sqlite3.Connection, config_dir: Path | None = None) -> list[str]:
    """Taxonomie nachfuehren und, wo noetig, in die Datenbank laden."""
    from finctl.tax import taxonomy as tx

    config_dir = config_dir or CONFIG_DIR
    meldungen = taxonomie(config_dir)
    pfad = config_dir / "taxonomy.yaml"
    if not pfad.exists():
        return meldungen
    try:
        ohne_zeile = conn.execute(
            f"SELECT COUNT(*) FROM mgmt_categories WHERE {MERKMAL} = 1").fetchone()[0] == 0
    except sqlite3.OperationalError:  # noch kein Schema: `finctl init` legt es an
        return meldungen
    if ohne_zeile and any(_merkmale(tx.load_spec(pfad))):
        tx.load_into_db(conn, pfad)
        conn.commit()
        meldungen.append("Kategorien neu geladen: das Merkmal "
                         f"`{MERKMAL}` steht jetzt auch in der Datenbank")
    return meldungen


def beim_start() -> list[str]:
    """Der Start der App: nachfuehren, wenn es ein Hauptbuch gibt, und melden."""
    from finctl import umstellen
    from finctl.ledger import db as ledger
    from finctl.pfade import DB_PATH

    umstellen.halt_wenn_offen(CONFIG_DIR)
    if not DB_PATH.exists():
        return []
    conn = ledger.connect(DB_PATH)
    try:
        meldungen = daten(conn)
    finally:
        conn.close()
    for zeile in meldungen:
        print(f"Nachgefuehrt: {zeile}", flush=True)
    return meldungen
