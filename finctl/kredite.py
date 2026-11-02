"""Kredite anlegen und entfernen -- ohne YAML von Hand.

`config/loans.yaml` traegt vier Immobiliendarlehen mit Zinsbindung,
Anschlussfinanzierung und beobachteten Restschulden: dreissig Felder je
Eintrag. Das ist die Form, die diese vier Vertraege brauchen, und die Form,
die ein Ratenkredit nicht braucht.

ZWEI ARTEN, EIN SPEICHER. Ein RATENKREDIT ist mit neun Feldern beschrieben
-- Restschuld, Zins, Rate, Laufzeit --, und daraus baut `segments_from` den
Tilgungsplan, den die Prognose ohnehin rechnet. Ein IMMOBILIENDARLEHEN
bleibt vorerst Handarbeit in der Datei: sein Modell in ein Formular zu
pressen machte die Seite unbrauchbar, und bearbeiten laesst es sich auf
/kredite schon.

EINE DATEI. Seit Schritt 5 (N.3c) steht jeder Kredit nur in `loans.yaml`, samt
seiner Notiz. Die Seite liest die Datei ganz und schreibt sie ganz
(`dateien.yaml_schreiben`); was sie auf /kredite eintraegt, steht am Eintrag:
`vorlage` (die Grundkonditionen eines Kredits an einer Klammer) und
`anschluss_eingegeben` (die Anschlusskondition, die die Seite durchrechnet, ohne
dass die Prognose sie nimmt).

ENTFERNEN IST DER WICHTIGERE TEIL. Wer dieses Werkzeug uebernimmt, erbt
sonst fremde Vertraege in seiner Prognose.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from finctl import notizen as _notizen
from finctl.dateien import yaml_lesen, yaml_schreiben
from finctl.pfade import CONFIG_DIR

DATEI = "loans.yaml"

#: Was die Seite /kredite an einem Kredit ablegt. Beides liest die Prognose nicht
#: als Kondition des Vertrags: `vorlage` ersetzt nur die Grundkonditionen eines Kredits an
#: einer Klammer (`realestate.loan.mit_vorlage`), `anschluss_eingegeben` steht neben dem
#: `anschluss` des Eintrags und wird von keiner Prognose gelesen.
VORLAGE = "vorlage"
ANSCHLUSS = "anschluss_eingegeben"

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


def _tag(wert) -> date | None:
    if isinstance(wert, date):
        return wert
    try:
        return date.fromisoformat(str(wert))
    except (TypeError, ValueError):
        return None


def ratenkredit(felder: dict) -> dict:
    """Aus neun Angaben ein Kredit, den `segments_from` rechnen kann.

    Ein Segment, fester Zins, feste Rate. Genau das ist ein Ratenkredit --
    und mehr anzubieten hiesse, nach Zahlen zu fragen, die im Vertrag nicht
    stehen.
    """
    beginn, ende = _tag(felder.get("start")), _tag(felder.get("ende"))
    return {
        "id": str(felder.get("id") or "").strip(),
        "name": str(felder.get("name") or "").strip(),
        "lender": str(felder.get("lender") or "").strip(),
        "servicing_account_id": felder.get("servicing_account_id") or None,
        "status": "active",
        "opening_balance_cents": felder.get("opening_balance_cents"),
        "opening_balance_as_of": beginn.isoformat() if beginn else None,
        "payment_cents": felder.get("annuity_cents"),
        "segments": [{
            "start": beginn.isoformat() if beginn else None,
            "end": ende.isoformat() if ende else None,
            "annual_rate_pct": felder.get("annual_rate_pct"),
            "annuity_cents": felder.get("annuity_cents"),
            "opening_balance_cents": felder.get("opening_balance_cents"),
            # Getippt, nicht aus einem Auszug gelesen -- dieselbe Kennzeichnung
            # wie bei den uebrigen Konditionen, die jemand von Hand eintraegt.
            "basis": "assumption",
        }],
    }


def _stammdaten_fehler(kredit: dict, vergeben: set[str]) -> list[str]:
    """Wer, wie er heisst und von welchem Konto die Rate abgeht."""
    fehler = []
    kennung = str(kredit.get("id") or "").strip()
    if kennung in _notizen.RESERVIERT:
        fehler.append(f"Kennung „{kennung}“ ist für Notizen reserviert")
    elif not _ID.match(kennung):
        fehler.append("Kennung: klein, Ziffern und Bindestriche, "
                      "höchstens 41 Zeichen")
    elif kennung in vergeben:
        fehler.append(f"Kennung „{kennung}“ ist schon vergeben")
    if not str(kredit.get("name") or "").strip():
        fehler.append("Name fehlt")
    if not str(kredit.get("lender") or "").strip():
        fehler.append("Gläubiger fehlt")
    if not kredit.get("servicing_account_id"):
        fehler.append("Konto fehlt: ohne es weiß die Prognose nicht, "
                      "wo die Rate abgeht")
    return fehler


def _kondition_fehler(seg: dict) -> list[str]:
    """Restschuld, Rate, Zins und Laufzeit -- woraus der Plan gerechnet wird."""
    fehler = []
    rest, rate = seg.get("opening_balance_cents"), seg.get("annuity_cents")
    satz = seg.get("annual_rate_pct")
    if not isinstance(rest, int) or rest <= 0:
        fehler.append("Restschuld: ein Betrag größer null")
    if not isinstance(rate, int) or rate <= 0:
        fehler.append("Monatsrate: ein Betrag größer null")
    if not isinstance(satz, (int, float)) or not 0 <= satz < 100:
        fehler.append("Zinssatz: zwischen 0 und 100 Prozent")
    beginn, ende = _tag(seg.get("start")), _tag(seg.get("end"))
    if beginn is None:
        fehler.append("Beginn: ein Datum als JJJJ-MM-TT")
    if ende is None:
        fehler.append("Ende: ein Datum als JJJJ-MM-TT")
    elif beginn and ende <= beginn:
        fehler.append("Das Ende liegt vor dem Beginn")
    # Eine Rate unter dem Monatszins tilgt nie: der Kredit liefe unendlich,
    # und der Tilgungsplan zeigte eine wachsende Restschuld als Prognose.
    if not fehler and rate <= rest * satz / 100 / 12:
        fehler.append("Die Rate deckt nicht einmal den Monatszins — "
                      "so tilgt der Kredit nie")
    return fehler


def pruefen(kredit: dict, vergeben: set[str]) -> list[str]:
    """Was an diesem Kredit nicht stimmt, in Worten. Leer heisst: in Ordnung."""
    [seg] = kredit.get("segments") or [{}]
    return _stammdaten_fehler(kredit, vergeben) + _kondition_fehler(seg)


# ------------------------------------------------------------------ schreiben

def lesen(config_dir: Path | None = None) -> dict:
    """Die ganze `loans.yaml` als Zuordnung; leer, wo es sie nicht gibt."""
    pfad = (config_dir or CONFIG_DIR) / DATEI
    return (yaml_lesen(pfad) or {}) if pfad.exists() else {}


def speichern(spec: dict, config_dir: Path | None = None) -> bool:
    """Die ganze Datei schreiben, samt Notizen. `True`, wenn sie sich aenderte."""
    config_dir = config_dir or CONFIG_DIR
    config_dir.mkdir(parents=True, exist_ok=True)
    return yaml_schreiben(config_dir / DATEI, spec)


def eintrag(spec: dict, kennung: str) -> dict | None:
    """Der Eintrag eines Kredits in der gelesenen Datei (dieselbe Zuordnung, nicht eine Kopie)."""
    return next((k for k in spec.get("loans") or []
                 if isinstance(k, dict) and str(k.get("id")) == kennung), None)


def neuer_kredit(felder: dict, spec: dict) -> dict:
    """Der Ratenkredit aus den Feldern, gegen die vorhandenen geprueft.

    `ValueError` sagt, was fehlt. Die Pruefung von `anlegen` ohne das Schreiben: ein
    Vorschlag fragt sie, bevor jemand zusagt.
    """
    kredit = ratenkredit(felder)
    fehler = pruefen(kredit, {str(k.get("id")) for k in spec.get("loans") or []})
    if fehler:
        raise ValueError("; ".join(fehler))
    return kredit


def anlegen(felder: dict, config_dir: Path | None = None) -> dict:
    """Einen Ratenkredit anlegen: ein neuer Eintrag hinter den vorhandenen."""
    config_dir = config_dir or CONFIG_DIR
    spec = lesen(config_dir)
    kredit = neuer_kredit(felder, spec)

    spec.setdefault("loans", []).append({f: v for f, v in kredit.items() if v is not None})
    speichern(spec, config_dir)
    return kredit


def entfernen(kennung: str, config_dir: Path | None = None) -> None:
    """Einen Kredit aus der Datei nehmen -- mit seiner Notiz."""
    config_dir = config_dir or CONFIG_DIR
    spec = lesen(config_dir)
    if eintrag(spec, kennung) is None:
        raise ValueError(f"Kein Kredit „{kennung}“")
    spec["loans"] = [k for k in spec["loans"]
                     if not (isinstance(k, dict) and str(k.get("id")) == kennung)]
    speichern(spec, config_dir)


def an_kredit_setzen(kennung: str, feld: str, wert: dict | None,
                     config_dir: Path | None = None) -> bool:
    """`vorlage` oder `anschluss_eingegeben` am Kredit setzen; `None` nimmt das Feld heraus.

    `True`, wenn sich die Datei aenderte. Ein Kredit, den es nicht gibt, ist ein Fehler.
    """
    config_dir = config_dir or CONFIG_DIR
    spec = lesen(config_dir)
    kredit = eintrag(spec, kennung)
    if kredit is None:
        raise ValueError(f"Kein Kredit „{kennung}“")
    if wert is None:
        kredit.pop(feld, None)
    else:
        kredit[feld] = wert
    return speichern(spec, config_dir)


# ------------------------------------------------------------ Tilgungsplan

def tilgungsplan(loan_id: str) -> dict[str, tuple[int, int, str]]:
    """Monat -> (Zinsen, Tilgung, Grundlage) eines Kredits aus loans.yaml.

    Fuer die Aufteilung einer Rate, deren Bank Zins und Tilgung nicht
    druckt (finctl/rules/categorize.py). Gelesen wird die Datei, wie die
    Aufteilung es immer tat -- ohne die Konditionen einer Vorlage.
    """
    from finctl.realestate.loan import amortise, opening_balance_cents, segments_from

    table: dict[str, tuple[int, int, str]] = {}
    for loan in lesen().get("loans", []) or []:
        if str(loan.get("id")) != loan_id or not loan.get("segments"):
            continue
        sched = amortise(loan_id, opening_balance_cents(loan), segments_from(loan))
        for pay in sched.payments:
            table[pay.month.strftime("%Y-%m")] = (
                pay.interest_cents, pay.principal_cents, pay.basis)
    return table


def anmelden() -> None:
    """Den Tilgungsplan bei den Regeln anmelden -- aufgerufen von der App."""
    from finctl.rules import categorize as _cz

    _cz.tilgungsplan_anmelden(tilgungsplan)
