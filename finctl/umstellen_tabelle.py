"""Die Tabelle `settings` beim Umstellen: gegen die Datei halten, danach entfernen.

Bis Schritt 5 (N.3f) lasen die Annahmen und die Untergrenzen der Konten ihre Werte aus der
Tabelle `settings` der Datenbank, und `/api/setting` legte eine Notiz nur dort ab. Heute
liest sie niemand mehr, und nichts schreibt hinein; das Schema legt sie nicht mehr an. Eine
Datenbank aus der Zeit davor kann sie noch haben, mit Zeilen, die in `settings_custom.yaml`
nicht stehen. Zusammenlegen sieht nur die Datei, also vergleicht `finctl umstellen` vorher.

Was haelt den Lauf an (`Abgleich.fehler`):

* eine Zeile nur in der Tabelle,
* ein anderer Wert, wenn die Tabelle der jungere Stand ist,
* eine Notiz, die in keiner Notiz der Datei steht.

Was nicht (`Abgleich.hinweise`, im Bericht): ein anderer Wert, wenn die Datei neuer ist als
die Zeile. Dann hat jemand die Datei danach von Hand geaendert, und sie gilt. Eine Zeile nur
in der Datei ist kein Fund: `init` hat sie nur noch nicht gespiegelt.

Nach einem Lauf, der den Abgleich bestanden hat, wird die Tabelle entfernt: Jede Zeile ist
dann in der Datei, im Bericht oder bewusst verworfen (`--tabelle-verwerfen`).
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

from finctl.notizen import ohne

SEITE = "settings_custom.yaml"


@dataclass(slots=True)
class Abgleich:
    """Was der Vergleich der Tabelle mit der Datei ergab."""

    geprueft: bool = False          # es gab eine Tabelle, und sie wurde gelesen
    fehler: list[str] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)


def _zeilen(db: Path) -> list[tuple] | None:
    """Alle Zeilen der Tabelle, oder `None` ohne Datenbank oder ohne Tabelle.

    Gelesen wird eine Kopie: Eine Datenbank im WAL-Betrieb legt beim Lesen `-shm` und `-wal`
    neben sich an, und der Datenordner soll unberuehrt bleiben (auch bei `--probe`).
    """
    if not db.exists():
        return None
    with tempfile.TemporaryDirectory(prefix="finctl-settings-") as tmp:
        for suffix in ("", "-wal"):
            quelle = db.with_name(db.name + suffix)
            if quelle.exists():
                shutil.copyfile(quelle, Path(tmp) / quelle.name)
        try:
            c = sqlite3.connect(Path(tmp) / db.name)
            try:
                return c.execute("SELECT key, value, note, updated_at FROM settings").fetchall()
            finally:
                c.close()
        except sqlite3.Error:
            return None


def _stand(updated_at: str | None) -> datetime | None:
    try:
        stand = datetime.fromisoformat(str(updated_at))
    except ValueError:
        return None
    return stand if stand.tzinfo else stand.replace(tzinfo=UTC)


def _datei_neuer(pfad: Path, updated_at: str | None) -> bool:
    """Wurde die Datei nach der Zeile geaendert? Ohne lesbares Datum: nein (anhalten)."""
    stand = _stand(updated_at)
    if stand is None or not pfad.exists():
        return False
    return datetime.fromtimestamp(pfad.stat().st_mtime, UTC) > stand


def _notizen(gelesen: object) -> list[str]:
    """Der Text jeder Notiz der Datei, ohne Zeilenumbrueche und Einrueckung."""
    zuordnung = gelesen.get("notizen") if isinstance(gelesen, dict) else None
    if not isinstance(zuordnung, dict):
        return []
    return [" ".join(str(eintrag["notiz"]).split()) for eintrag in zuordnung.values()
            if isinstance(eintrag, dict) and eintrag.get("notiz")]


def abgleichen(config: Path, text: str) -> Abgleich:
    """Die Tabelle gegen `settings_custom.yaml` halten. `text` ist die Seite nach dem Umwandeln."""
    ergebnis = Abgleich()
    zeilen = _zeilen(config.parent / "data" / "finance.db")
    if zeilen is None:
        return ergebnis
    ergebnis.geprueft = True
    gelesen = yaml.safe_load(text)
    datei = gelesen.get("einstellungen") if isinstance(gelesen, dict) else None
    datei = {str(k): v for k, v in ohne(datei if isinstance(datei, dict) else {}).items()}
    notizen = _notizen(gelesen)
    for key, wert, notiz, updated_at in sorted(zeilen):
        if key not in datei:
            ergebnis.fehler.append(f"Tabelle settings, Zeile `{key}` = {wert}: steht nicht in "
                                   f"{SEITE}")
        elif str(datei[key]) != str(wert):
            zeile = f"Tabelle settings, Zeile `{key}`: {wert}, in {SEITE} {datei[key]}"
            if _datei_neuer(config / SEITE, updated_at):
                ergebnis.hinweise.append(f"{zeile}; die Datei ist neuer und gilt")
            else:
                ergebnis.fehler.append(zeile)
        if notiz and " ".join(str(notiz).split()) not in " ".join(notizen):
            ergebnis.fehler.append(f"Tabelle settings, Zeile `{key}` trägt eine Notiz, die in "
                                   f"keiner Datei steht: {notiz}")
    return ergebnis


def entfernen(db: Path) -> bool:
    """Die Tabelle aus der Datenbank nehmen. `True`, wenn sie da war und jetzt weg ist."""
    if not db.exists():
        return False
    try:
        c = sqlite3.connect(db, timeout=5)
        try:
            da = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='settings'"
                           ).fetchone()
            c.execute("DROP TABLE IF EXISTS settings")
            c.commit()
        finally:
            c.close()
    except sqlite3.Error:
        return False
    return bool(da)
