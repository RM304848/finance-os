"""Eine Datei nur dann schreiben, wenn sich ihr Inhalt aendert.

Jede Seite, die Handentscheidungen in `config/*.yaml` ablegt, schrieb die ganze
Datei neu -- auch dann, wenn jemand auf Speichern drueckte, ohne etwas zu
aendern. Meist kam derselbe Inhalt heraus; mal war es ein neuerer Kopfkommentar,
mal ein Rundungsrest, mal ein Eintrag, der dem Vorgabewert gleicht und eine
zweite Datei danach uebertoent (`tests/test_browser.py`, "Speichern ohne
Aenderung aendert keine Datei").

Verglichen wird, was in der Datei STEHT, nicht der Text: ein anderer Kopf
macht keine Aenderung, eine andere Zahl schon.

Und eine Datei nur dann LESEN, wenn sie sich geaendert hat: `yaml_lesen`.

Seit Schritt 5 (Notiz statt Kommentar) gibt es nichts mehr, was ein YAML-Schreiber
verwerfen koennte: Die Begruendungen stehen als Notizen in den Daten. Wer eine
Datei aendert, liest sie ganz, aendert seinen Teil und schreibt sie ganz zurueck
(`yaml_schreiben`), statt in ihren Text zu schneiden.
Eine Seite wie `/konten` rechnet je Konto und fragte dieselben Dateien dabei
hundertfach neu ab (rund 90 % ihrer Zeit); der Zwischenspeicher liegt hier,
damit keine der Stellen, die lesen, es selbst koennen muss.
"""

from __future__ import annotations

import copy
import os
import time
from pathlib import Path
from typing import Any

import yaml

from finctl import notizen as _notizen

#: Eine Zuordnung oder Liste aus lauter einfachen Werten steht in einer Zeile,
#: solange sie nicht laenger ist als das.
FLUSS_BREITE = 72

#: Eine Datei, die juengst geaendert wurde, kommt nicht in den Speicher: Zwei
#: Schreibvorgaenge innerhalb der Aufloesung der Dateizeit (je nach System
#: Millisekunden) sehen gleich aus, wenn auch die Groesse gleich blieb. Erst
#: nach dieser Frist ist `st_mtime_ns` ein Beweis, kein Zufall.
FRIST_NS = 2_000_000_000

# (absoluter Pfad) -> ((st_mtime_ns, st_size), Gelesenes)
_SPEICHER: dict[str, tuple[tuple[int, int], Any]] = {}


def yaml_lesen(pfad: Path | str) -> Any:
    """Der Inhalt der YAML-Datei, einmal gelesen, solange sie sich nicht aendert.

    Zurueck kommt eine tiefe Kopie: Wer das Gelesene aendert, aendert nicht den
    naechsten Aufruf. Wie `Path.read_text` wirft die Funktion bei einer
    fehlenden Datei; wer sie als leer behandelt, prueft das vorher selbst.
    """
    schluessel = os.path.abspath(pfad)
    stat = os.stat(schluessel)
    marke = (stat.st_mtime_ns, stat.st_size)
    treffer = _SPEICHER.get(schluessel)
    if treffer is not None and treffer[0] == marke:
        return copy.deepcopy(treffer[1])
    with open(schluessel, encoding="utf-8") as f:
        gelesen = yaml.safe_load(f)
    if time.time_ns() - stat.st_mtime_ns > FRIST_NS:
        _SPEICHER[schluessel] = (marke, gelesen)
        return copy.deepcopy(gelesen)
    _SPEICHER.pop(schluessel, None)
    return gelesen


def vergessen(pfad: Path | str) -> None:
    """Den Zwischenspeicher fuer diese Datei leeren: Sie wurde von aussen geschrieben."""
    _SPEICHER.pop(os.path.abspath(pfad), None)


def gleicher_inhalt(pfad: Path, text: str) -> bool:
    """Steht in der Datei schon, was `text` als YAML sagt?"""
    if not pfad.exists():
        return False
    try:
        return yaml.safe_load(pfad.read_text(encoding="utf-8")) == yaml.safe_load(text)
    except yaml.YAMLError:
        return False


def schreiben_wenn_geaendert(pfad: Path, text: str) -> bool:
    """Schreibt `text`, wenn er etwas anderes sagt als die Datei. `True`, wenn geschrieben."""
    if gleicher_inhalt(pfad, text):
        return False
    pfad.write_text(text, encoding="utf-8")
    vergessen(pfad)
    return True


# ------------------------------------------------------------------ schreiben


class _Schreiber(yaml.SafeDumper):
    """So sieht eine Datei aus, die dieses Werkzeug schreibt.

    * Kurze Sammlungen aus einfachen Werten in einer Zeile (`match: {regex: x}`),
      alles andere Block. Ohne das wuerde aus jeder Regel ein Dutzend Zeilen.
    * Ein Text mit Zeilenumbruechen als Block (`|`), damit eine Notiz in der
      Datei lesbar bleibt. Wo der Block nicht darstellbar ist (Leerzeichen am
      Zeilenende), wechselt PyYAML selbst auf Anfuehrungszeichen.
    * Listen unter ihrem Schluessel eingerueckt, wie die Dateien von Hand stehen.
    * Keine Anker: dieselbe Zeichenkette zweimal ist zweimal geschrieben.
    """

    def ignore_aliases(self, data):
        return True

    def increase_indent(self, flow=False, indentless=False):
        # Listenelemente eingerueckt unter ihrem Schluessel, wie die Dateien von Hand stehen.
        return super().increase_indent(flow, False)

    def represent_mapping(self, tag, mapping, flow_style=None):
        if flow_style is None and _kurz(mapping):
            flow_style = True
        return super().represent_mapping(tag, mapping, flow_style)

    def represent_sequence(self, tag, sequence, flow_style=None):
        if flow_style is None and _kurz(sequence):
            flow_style = True
        return super().represent_sequence(tag, sequence, flow_style)


def _einfach(wert: Any) -> bool:
    return wert is None or isinstance(wert, (str, int, float, bool)) or (
        hasattr(wert, "isoformat") and not isinstance(wert, (dict, list)))


def _kurz(sammlung: Any) -> bool:
    """Nur einfache Werte, keiner mit Zeilenumbruch, und in einer kurzen Zeile."""
    werte = list(sammlung.items()) if isinstance(sammlung, dict) else [(None, w) for w in sammlung]
    if not werte:
        return True
    teile = []
    for schluessel, wert in werte:
        if not _einfach(wert) or not _einfach(schluessel):
            return False
        if isinstance(wert, str) and "\n" in wert:
            return False
        teile.append(f"{schluessel}: {wert}")
    return sum(len(t) + 2 for t in teile) <= FLUSS_BREITE


def _text(dumper: yaml.SafeDumper, wert: str):
    stil = "|" if "\n" in wert else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", wert, style=stil)


_Schreiber.add_representer(str, _text)


def yaml_text(daten: Any) -> str:
    """Die Daten als YAML-Text, in der Form, in der dieses Werkzeug Dateien schreibt."""
    return yaml.dump(daten, Dumper=_Schreiber, allow_unicode=True, sort_keys=False,
                     default_flow_style=False, width=100)


def yaml_schreiben(pfad: Path, daten: Any) -> bool:
    """Die ganze Datei schreiben. `True`, wenn sich etwas geaendert hat."""
    return schreiben_wenn_geaendert(pfad, yaml_text(daten))


def zuordnung_lesen(pfad: Path, schluessel: str) -> dict[str, Any]:
    """Die Zuordnung unter `schluessel` in der Datei; ohne Datei oder ohne Schluessel leer.

    Fuer Dateien, die nur ein Dashboard-Schreiber kennt: eine Zuordnung unter einem
    Schluessel, dazu die Notizen des Bereichs.
    """
    if not pfad.exists():
        return {}
    spec = yaml_lesen(pfad) or {}
    return spec.get(schluessel) or {}


def zuordnung_schreiben(pfad: Path, schluessel: str, daten: dict[str, Any], kopf: str) -> None:
    """Die Zuordnung unter `schluessel` mit dem Kopf der App schreiben, wenn sie etwas aendert.

    Mit Kopf, damit die Datei erklaert, was sie ist: Wer sie in einem Jahr im Editor
    oeffnet, soll nicht raten muessen, wer sie schreibt. Leere Werte fallen aus der
    Datei, der Block `notizen:` bleibt, wie er ist.
    """
    sauber = {k: v for k, v in daten.items() if v not in (None, {}, "")}
    schreiben_wenn_geaendert(
        pfad, kopf + yaml.safe_dump(_notizen.mit_bereichen({schluessel: sauber}, pfad),
                                    allow_unicode=True, sort_keys=True))
