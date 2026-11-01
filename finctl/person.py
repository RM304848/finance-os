"""Wer plant: Geburtstag, Krankenversicherung, Rentenbeginn.

Drei Angaben, aus denen jede Altersschwelle eine Jahreszahl wird. Sie stehen in
`config/lebensplan.yaml` (`person.birth_date`, `person.krankenversicherung`,
`schwellen.grv_ab_alter`, mit ihrer Notiz unter `notizen:`) und lassen sich auf
/einrichtung setzen; die Seite schreibt die Datei ganz (Schritt 5, N.3e; vorher stand, was
sie setzte, in einer zweiten Datei unter anderen Namen). Wer das Werkzeug uebernimmt,
traegt hier seine eigenen ein.

Die Fristen sind Gesetz, keine Annahme, und stehen deshalb hier und nicht in
einer Datei: wer 55 ist und die letzten fuenf Jahre nicht gesetzlich
versichert war, kommt nicht mehr in die GKV zurueck (§6 Abs. 3a SGB V). Die
Frist gibt es nur fuer Privatversicherte -- wer gesetzlich versichert ist,
bekommt keine.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from finctl.dateien import yaml_lesen, yaml_schreiben
from finctl.pfade import CONFIG_DIR

DATEI = "lebensplan.yaml"

#: Wie die Seite die Arten nennt. Leer heisst: nicht angegeben.
KRANKENVERSICHERUNG = {"gesetzlich": "gesetzlich", "privat": "privat"}
#: Regelaltersgrenze ab Jahrgang 1964.
RENTE_AB_ALTER = 67
#: §6 Abs. 3a SGB V.
GKV_SPERRE_ALTER = 55

#: Wo die drei Angaben in der Datei stehen: (Abschnitt, Schluessel).
ORTE = {"geburtsdatum": ("person", "birth_date"),
        "krankenversicherung": ("person", "krankenversicherung"),
        "rente_ab_alter": ("schwellen", "grv_ab_alter")}


def _yaml(pfad: Path) -> dict:
    if not pfad.exists():
        return {}
    gelesen = yaml_lesen(pfad)
    return gelesen if isinstance(gelesen, dict) else {}


def _datum(wert) -> date | None:
    if not wert:
        return None
    return wert if isinstance(wert, date) else date.fromisoformat(str(wert)[:10])


def aus_spec(roh: dict) -> dict:
    """Die drei Angaben aus dem Inhalt der Datei."""
    person = roh.get("person") or {}
    return {"geburtsdatum": _datum(person.get("birth_date")),
            "krankenversicherung": str(person.get("krankenversicherung") or ""),
            "rente_ab_alter": int((roh.get("schwellen") or {}).get("grv_ab_alter")
                                  or RENTE_AB_ALTER)}


def angaben(config_dir: Path | None = None) -> dict:
    """Die drei Angaben aus `lebensplan.yaml`."""
    return aus_spec(_yaml((config_dir or CONFIG_DIR) / DATEI))


def geburtstag(config_dir: Path | None = None) -> date | None:
    return angaben(config_dir)["geburtsdatum"]


def _mit_alter(g: date, alter: int) -> date:
    # Am 29. Februar Geborene werden im Nicht-Schaltjahr am 28. aelter.
    try:
        return g.replace(year=g.year + alter)
    except ValueError:
        return g.replace(year=g.year + alter, day=28)


def rentenbeginn(config_dir: Path | None = None) -> date | None:
    """Der Monat NACH dem Geburtstag, an dem das Rentenalter erreicht ist --
    so legt die Rentenversicherung den Beginn fest."""
    return rentenbeginn_aus(angaben(config_dir))


def rentenbeginn_aus(a: dict) -> date | None:
    """Dasselbe aus Angaben, die schon gelesen sind: wer Geburtstag und
    Rentenbeginn braucht, liest die zwei Dateien einmal."""
    if a["geburtsdatum"] is None:
        return None
    tag = _mit_alter(a["geburtsdatum"], a["rente_ab_alter"])
    return date(tag.year + tag.month // 12, tag.month % 12 + 1, 1)


def pkv_sperre(config_dir: Path | None = None) -> date | None:
    """Ab wann die Rueckkehr in die GKV ausgeschlossen ist -- nur bei PKV."""
    a = angaben(config_dir)
    if a["krankenversicherung"] != "privat" or a["geburtsdatum"] is None:
        return None
    return _mit_alter(a["geburtsdatum"], GKV_SPERRE_ALTER)


def pkv_stichtag(config_dir: Path | None = None) -> date | None:
    """Ein Jahr davor. Eine Frist, die man am Tag ihres Ablaufs bemerkt, ist
    verpasst -- ein Kassenwechsel braucht Antrag, Fristen und Vorlauf."""
    sperre = pkv_sperre(config_dir)
    return _mit_alter(sperre, -1) if sperre else None


def setzen(felder: dict, config_dir: Path | None = None) -> dict:
    """Von /einrichtung: die Angaben in `lebensplan.yaml`; ein leerer Wert nimmt sie heraus.

    Geschrieben wird nur, was die Datei danach anders sagt: Speichern ohne Aenderung schreibt
    kein Byte, auch wenn das Datum dort als Datum und hier als Text steht.
    """
    config_dir = config_dir or CONFIG_DIR
    pfad = config_dir / DATEI
    spec = _yaml(pfad)
    jetzt = aus_spec(spec)
    if "geburtsdatum" in felder:
        wert = _datum(felder["geburtsdatum"]) if felder["geburtsdatum"] else None
        if wert and not date(1900, 1, 1) <= wert <= date.today():
            raise ValueError("Geburtsdatum als JJJJ-MM-TT, in der Vergangenheit")
        _setzen(spec, "geburtsdatum", wert, jetzt["geburtsdatum"])
    if "krankenversicherung" in felder:
        wert = str(felder["krankenversicherung"] or "")
        if wert and wert not in KRANKENVERSICHERUNG:
            raise ValueError("Krankenversicherung: gesetzlich oder privat")
        _setzen(spec, "krankenversicherung", wert, jetzt["krankenversicherung"])
    if "rente_ab_alter" in felder:
        wert = int(felder["rente_ab_alter"]) if felder["rente_ab_alter"] else None
        if wert is not None and not 50 <= wert <= 75:
            raise ValueError("Rentenalter zwischen 50 und 75")
        _setzen(spec, "rente_ab_alter", wert, jetzt["rente_ab_alter"])
    if pfad.exists() or spec:
        yaml_schreiben(pfad, spec)
    return angaben(config_dir)


def _setzen(spec: dict, feld: str, wert, jetzt) -> None:
    """Den Wert an seinen Ort in der Datei, oder ihn herausnehmen. Dasselbe wie jetzt: nichts."""
    abschnitt, schluessel = ORTE[feld]
    if wert in (None, ""):
        if isinstance(spec.get(abschnitt), dict):
            spec[abschnitt].pop(schluessel, None)
        return
    if wert == jetzt:
        return
    if not isinstance(spec.get(abschnitt), dict):
        spec[abschnitt] = {}
    spec[abschnitt][schluessel] = wert
