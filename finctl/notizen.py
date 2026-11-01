"""Die Notiz: ein datierter Freitext, der sagt, warum etwas so ist.

Begriff: `CONTEXT.md`. Entscheidung: `docs/adr/0001-notiz-statt-kommentar.md`,
Plan: `docs/schritt5_notizen.md`. Dieses Modul ist die einzige Stelle, die die Form
einer Notiz kennt; Leser und Schreiber fragen hier.

FORM. Ein Eintrag mit Kennung traegt seine Notiz an sich:

    - id: ...
      notiz: Warum der Eintrag so ist.
      notiz_vom: 2026-10-05          # wann der Text zuletzt geaendert wurde

Eine Einstellung ohne Kennung und ein ganzer Bereich einer Datei haben keinen
Eintrag, an dem eine Notiz stehen koennte. Ihre Notizen stehen oben in der Datei
unter `notizen:`, mit dem Ort als Schluessel (der Pfad der Einstellung, etwa
`kapital.rendite_depot`, oder `bereich` fuer die ganze Datei), in derselben Form:

    notizen:
      kapital.rendite_depot:
        notiz: ...
        notiz_vom: 2026-10-05

DATUM. Ein Text bekommt sein Datum, wenn der Haushalt ihn aendert (Entscheidung 4).
Ein unveraenderter Text behaelt es, auch ein fehlendes: Ein Datum fehlt, wenn die
Notiz aus der Zeit vor den Notizen stammt, und ein Speichern ohne Aenderung macht
sie nicht jung. `fortschreiben` ist die Regel, alles andere ruft sie.

WO KEINE NOTIZ STEHT. In einer Zuordnung, deren Schluessel selbst die Daten sind
(das Budget je Konto, die Blaetter einer Kategorie, `remap`, die Zeilen der
Zinssaetze, die Schreibweisen der Reihen, `overrides` und `enden` der Prognose): ein
Schluessel `notiz` dort waere ein Konto, eine Kategorie, eine Einstellung. Die Leser
dieser Zuordnungen rufen deshalb `ohne` auf.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

NOTIZ = "notiz"
VOM = "notiz_vom"
#: Der Schluessel oben in der Datei fuer Notizen ohne Eintrag.
BEREICHE = "notizen"
#: Der Ort der Notiz, die fuer die ganze Datei gilt.
BEREICH = "bereich"

#: Was in keiner Kennung und in keinem Schluessel einer Datenzuordnung stehen darf.
RESERVIERT = frozenset({NOTIZ, VOM, BEREICHE})

#: Wie lang die Notiz eines Eintrags werden darf. Eine Notiz aus Kommentaren ist mehrere
#: Absaetze lang, und `finctl umstellen` haengt zusammen, was zwei Dateien sagten. Die
#: Grenze schuetzt nur vor einer Eingabe ohne Ende; jede Kuerzung darunter schnitte beim
#: Speichern, auch ohne Aenderung, eine Begruendung ab.
MAX = 20_000


@dataclass(frozen=True, slots=True)
class Notiz:
    """Text und Datum einer Notiz. Ohne Datum: aus der Zeit vor den Notizen."""

    text: str = ""
    vom: str = ""

    def __bool__(self) -> bool:
        return bool(self.text)

    def als_dict(self) -> dict[str, str]:
        """Die Felder, wie sie am Eintrag stehen; ohne Text keine."""
        if not self.text:
            return {}
        return {NOTIZ: self.text, **({VOM: self.vom} if self.vom else {})}


# --------------------------------------------------------------------- lesen


def _datum(wert: Any) -> str:
    """Das Datum als JJJJ-MM-TT. YAML liest `2026-10-05` schon als Datum."""
    if wert in (None, ""):
        return ""
    if isinstance(wert, datetime):
        return wert.date().isoformat()
    if isinstance(wert, date):
        return wert.isoformat()
    try:
        return date.fromisoformat(str(wert).strip()).isoformat()
    except ValueError:
        raise ValueError(f"`{VOM}`: „{wert}“ ist kein Datum, erwartet JJJJ-MM-TT") from None


def _text(wert: Any) -> str:
    return "" if wert is None else str(wert).strip()


def eingabe(wert: Any) -> str:
    """Der Text einer Notiz, wie eine Seite ihn schickt: Zeilenumbrueche als `\\n`, ohne Rand.

    Die Zeilenumbrueche bleiben, denn `fortschreiben` haelt einen Text, in dem einer
    fehlt, fuer einen anderen. Laenger als `MAX` wird er nicht.
    """
    return _text(wert).replace("\r\n", "\n").replace("\r", "\n")[:MAX]


def lesen(eintrag: Mapping | None, alt: Sequence[str] = ()) -> Notiz:
    """Die Notiz eines Eintrags, wie die Datei sie haelt; ohne Notiz eine leere.

    `notiz` gilt vor jedem alten Namen, und nur ihr Datum zaehlt. `alt` sind die
    Namen, unter denen dieselbe Sache bisher stand (`herleitung`, `note`, `warum`):
    Sie gelten, wo `notiz` fehlt, und ohne Datum.
    """
    if not isinstance(eintrag, Mapping):
        return Notiz()
    for name in (NOTIZ, *alt):
        wert = eintrag.get(name)
        if wert is None:
            continue
        text = _text(wert)
        return Notiz(text, _datum(eintrag.get(VOM)) if name == NOTIZ and text else "")
    return Notiz()


def bereiche(spec: Mapping | None, datei: str = "") -> dict[str, Notiz]:
    """Die Notizen unter `notizen:`, je Ort; ohne den Block keine.

    Ein Eintrag, der keine Zuordnung mit Text ist, ist ein Fehler, der die Datei nennt:
    Es gibt nur diese eine Form.
    """
    roh = (spec or {}).get(BEREICHE)
    if roh is None:
        return {}
    wo = f"{datei}: " if datei else ""
    if not isinstance(roh, Mapping):
        raise ValueError(f"{wo}`{BEREICHE}` ist keine Zuordnung")
    aus: dict[str, Notiz] = {}
    for ort, eintrag in roh.items():
        if not isinstance(eintrag, Mapping):
            raise ValueError(f"{wo}{BEREICHE}.{ort}: erwartet `{NOTIZ}` und `{VOM}`")
        gelesen = lesen(eintrag)
        if gelesen:
            aus[str(ort)] = gelesen
    return aus


def ohne(zuordnung: Mapping | None) -> dict:
    """Die Zuordnung ohne die Schluessel einer Notiz.

    Fuer Leser einer Zuordnung, deren Schluessel Daten sind: Eine Notiz, die dort
    steht, ist keine Daten und aendert keine Zahl.
    """
    return {k: v for k, v in (zuordnung or {}).items() if k not in RESERVIERT}


def in_zeile(zeile: dict, notiz: Notiz, alt: Sequence[str] = ()) -> dict:
    """Die Notiz in eine Zeile fuer eine Seite schreiben, und die Zeile zurueck.

    Wo die Seite die Notiz noch unter ihrem alten Namen liest (`note`), steht sie auch
    dort -- mit dem Text, den die Seite heute sieht. Bis Schritt 6 aendert sich keine
    Beschriftung.
    """
    for name in (NOTIZ, VOM):
        zeile.pop(name, None)
    zeile.update(notiz.als_dict())
    for name in alt:
        if notiz.text or name in zeile:
            zeile[name] = notiz.text
    return zeile


def kennung_pruefen(name: str, was: str = "Kennung") -> None:
    """`ValueError`, wenn `name` ein Wort ist, das eine Notiz traegt.

    Eine Kennung, die als Schluessel einer Datenzuordnung steht, darf nicht so
    heissen wie ein Feld der Notiz: Sonst liest `ohne` sie als Notiz.
    """
    if str(name) in RESERVIERT:
        raise ValueError(f"{was} „{name}“ ist fuer Notizen reserviert")


# ------------------------------------------------------------------ schreiben


def _heute(heute: date | None) -> str:
    return (heute or date.today()).isoformat()


def fortschreiben(bisher: Notiz, text: str | None, *, heute: date | None = None) -> Notiz:
    """Die Notiz nach einer Eingabe -- die Datumsregel.

    `None` laesst sie, wie sie ist. Derselbe Text (ohne Rand verglichen) laesst sie
    ebenfalls, mit ihrem Datum oder ohne. Ein anderer Text bekommt das heutige
    Datum, ein leerer Text loescht die Notiz samt Datum.
    """
    if text is None:
        return bisher
    neu = _text(text)
    if neu == bisher.text:
        return bisher
    return Notiz(neu, _heute(heute)) if neu else Notiz()


def setzen(eintrag: dict, text: str | None, *, alt: Sequence[str] = (),
           heute: date | None = None) -> bool:
    """Den Text der Notiz am Eintrag setzen. `True`, wenn der Eintrag sich aenderte.

    Gilt der Text schon, bleibt der Eintrag unberuehrt: kein Datum, keine
    Umbenennung eines alten Namens. Ein neuer Text steht danach unter `notiz`, mit
    Datum, und die alten Namen sind aus dem Eintrag.
    """
    if text is None:
        return False
    namen = (NOTIZ, VOM, *alt)
    bisher = lesen(eintrag, alt=alt)
    neu = fortschreiben(bisher, text, heute=heute)
    if neu == bisher:
        return False
    for name in namen:
        eintrag.pop(name, None)
    if neu:
        eintrag.update(neu.als_dict())
    return True


def bereich_setzen(spec: dict, ort: str, text: str | None, *,
                   heute: date | None = None) -> bool:
    """Die Notiz eines Ortes (Einstellung oder `bereich`) unter `notizen:` setzen.

    Dieselbe Regel wie `setzen`. Ein leerer Block faellt aus der Datei.
    """
    block = spec.get(BEREICHE)
    if not isinstance(block, dict):
        block = {}
    eintrag = block.get(ort)
    eintrag = dict(eintrag) if isinstance(eintrag, Mapping) else {}
    if not setzen(eintrag, text, heute=heute):
        return False
    if eintrag:
        block[ort] = eintrag
    else:
        block.pop(ort, None)
    if block:
        spec[BEREICHE] = block
    else:
        spec.pop(BEREICHE, None)
    return True


def mit_bereichen(neu: dict, pfad: Path) -> dict:
    """`neu` samt dem Block `notizen:`, den die Datei `pfad` heute traegt.

    Fuer Schreiber, die den Inhalt der Datei aus ihren eigenen Daten aufbauen und
    die Datei dann ganz neu schreiben: Der Block gehoert ihnen nicht, er soll das
    Schreiben ueberstehen. Ohne Datei oder ohne Block ist es `neu`.
    """
    from finctl.dateien import yaml_lesen

    if not pfad.exists():
        return neu
    alt = yaml_lesen(pfad)
    block = alt.get(BEREICHE) if isinstance(alt, dict) else None
    return {**neu, BEREICHE: block} if block else neu
