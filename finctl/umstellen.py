"""Einen Datenordner umstellen: aus Kommentaren werden Notizen.

`finctl umstellen` (Schritt 5, `docs/schritt5_notizen.md`, N.2). Bis jetzt trugen die
Dateien in `config/` die Begruendungen als Kommentare. Danach steht jede als Notiz am
Eintrag oder unter `notizen:` (`finctl/notizen.py`), und die Oberflaeche darf die ganze
Datei schreiben (`finctl/dateien.py`), ohne etwas zu verlieren.

WAS GESCHIEHT, in dieser Reihenfolge:

1. Jede Datei wird im Speicher umgewandelt und geprueft (`umwandeln`). Scheitert eine
   Pruefung, wird NICHTS geschrieben.
2. Die Paare aus Basis- und Seitendatei werden zusammengelegt (`umstellen_paare`, N.3),
   ebenfalls im Speicher und geprueft.
3. `config/` wird nach `archiv/vor_umstellung_<Datum>/` gesichert.
4. Die umgewandelten Dateien werden geschrieben, die Seitendateien der Paare entfernt.
5. Der Bericht kommt nach `notizen/umstellung_<Datum>.md`: jeder Kommentar und wo er jetzt
   steht, dazu was weggefallen ist und was beim Zusammenlegen geschah.

`--probe <Ordner>` macht nur 1, 2 und 5 und legt die umgewandelte Kopie in den Ordner. Der
Datenordner bleibt unberuehrt.

EINE ERKENNUNG. `Plan.zu_tun` sagt, ob es etwas zu tun gibt: Kommentare, alte Namen oder die
Seitendatei eines Paars. Nach ihr meldet der Befehl „Nichts umzustellen“, und nach ihr haelt
die App an (`halt_wenn_offen`), weil sie die alte Form nicht mehr liest. Der Kopf, den die App
selbst schreibt, ist kein Anlass: Sie schreibt ihn mit jedem Speichern wieder.

Ein zweiter Lauf aendert nichts: Eine Datei ohne Kommentar und ohne Notiz unter einem alten
Namen ist schon umgestellt, und eine Seitendatei gibt es nicht mehr.

DIE PRUEFUNGEN, jede einzeln und vor dem Schreiben:

* Jede Kommentarzeile steht in genau einem Stueck, und jedes Stueck in der Notiz, in die es
  gehoert -- oder im Bericht unter "weggefallen".
* Die Datei hat danach keinen Kommentar mehr.
* Ohne ihre Notizen liefert die Datei dieselben Werte wie vorher (geparst verglichen).
* Eine zweite Umwandlung der neuen Datei findet nichts mehr zu tun.

WAS WEGFALLEN DARF (Entscheidung 3): der Kopf, den die App selbst schrieb, wenn er
wortlich stimmt (`umstellen_form.KOEPFE`), und ein Feldkommentar, der nur den Wert des
Feldes in Euro wiederholt.
"""

from __future__ import annotations

import copy
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from finctl import dateien as _dateien
from finctl import umstellen_paare as _paare
from finctl.notizen import BEREICH, BEREICHE, NOTIZ, VOM
from finctl.umstellen_form import OHNE_SEITE, Behaelter, Datei, datei
from finctl.umstellen_lagen import (
    LAGEN,
    Geruest,
    NichtUmwandelbarError,
    Stueck,
    einordnen,
    lesen,
)
from finctl.umstellen_paare import PAARE, Zusammenlegung

NOTIZEN_ORDNER = "notizen"
ARCHIV_ORDNER = "archiv"


class AlteFormError(RuntimeError):
    """Eine Datei traegt noch Kommentare statt Notizen, und etwas wollte sie neu schreiben."""


# ----------------------------------------------------------------- Ergebnis


@dataclass(slots=True)
class Umwandlung:
    """Das Ergebnis fuer eine Datei. `neu` ist `None`, wenn nichts zu tun ist."""

    name: str
    neu: str | None = None
    #: Der Text der Datei, wie sie war.
    text: str = ""
    stuecke: list[Stueck] = field(default_factory=list)
    #: Alte Namen, die `notiz` wurden, und wie oft.
    umbenannt: dict[str, int] = field(default_factory=dict)
    #: Fehler der Pruefungen. Mit Fehlern wird nichts geschrieben.
    fehler: list[str] = field(default_factory=list)
    zeilen_vorher: int = 0
    #: Die Seitendatei eines Paars: Sie ist zusammengelegt und wird entfernt.
    loeschen: bool = False
    #: Die Basisdatei eines Paars: was beim Zusammenlegen geschah. Eine Basisdatei kann in
    #: mehreren Paaren stehen (`forecast.yaml` mit `forecast_custom.yaml` und mit
    #: `settings_custom.yaml`), in der Reihenfolge von `PAARE`.
    zusammengelegt: list[Zusammenlegung] = field(default_factory=list)
    #: Die Seitendatei eines Paars, wie sie ins Zusammenlegen ging (Notizen statt Kommentare).
    #: Eine Seitendatei, die zwei Basisdateien bedient, geht in beide Paare so ein.
    seitentext: str | None = None

    @property
    def anlass(self) -> bool:
        """Gibt es hier etwas, das nur `finctl umstellen` tun darf?

        Der Kopf, den die App selbst schrieb, ist keines: Sie schreibt ihn mit jedem
        Speichern wieder. Eine Datei, die nur ihn loswuerde, hielte die App an, kaum dass
        sie selbst geschrieben hat.
        """
        if self.loeschen or (bool(self.zusammengelegt) and self.neu is not None):
            return True
        return self.neu is not None and (bool(self.umbenannt)
                                         or any(not s.weg for s in self.stuecke))

    @property
    def weggefallen(self) -> list[Stueck]:
        return [s for s in self.stuecke if s.weg]

    def zaehlung(self) -> dict[str, int]:
        """Kommentarzeilen je Lage, ohne die weggefallenen."""
        z = dict.fromkeys(LAGEN, 0)
        for s in self.stuecke:
            if not s.weg:
                z[s.lage] += s.zeilen
        return z


# ------------------------------------------------------------- anwenden


def _stuecke_nach_ziel(stuecke: list[Stueck]) -> dict[tuple, list[Stueck]]:
    aus: dict[tuple, list[Stueck]] = {}
    for s in sorted(stuecke, key=lambda s: s.von):
        if not s.weg:
            aus.setdefault(s.ziel, []).append(s)
    return aus


def _stueck_text(s: Stueck) -> str:
    if s.ziel[0] == "bereich" and s.hinweis:
        return f"{s.hinweis}:\n{s.text}"
    return f"{s.mit}{s.text}"


def _text_von(wert: Any) -> str:
    return "" if wert is None else str(wert).strip()


def _eintrag_umbauen(eintrag: dict, teile: list[tuple[int, str]], zeilen: dict[str, int],
                     b: Behaelter) -> dict:
    """Der Eintrag mit seiner Notiz: Kommentare, Freitext und alte Namen in einem Text.

    Die Reihenfolge ist die der Datei. Die Notiz steht dort, wo das erste Feld stand, das
    sie ersetzt (`notiz` oder ein alter Name), sonst am Ende; ein Datum bleibt, wo es war.
    """
    namen = (NOTIZ, *b.alt)
    vorhanden = [n for n in namen if n in eintrag]
    teile = list(teile)
    for n in vorhanden:
        text = _text_von(eintrag[n])
        if text and not any(t == text for _, t in teile):
            teile.append((zeilen.get(n, 0), text))
    text = "\n\n".join(t for _, t in sorted(teile, key=lambda p: p[0]))
    neu: dict = {}
    gesetzt = False
    for schluessel, wert in eintrag.items():
        if schluessel in namen:
            if not gesetzt:
                neu[NOTIZ] = text
                if VOM in eintrag:
                    neu[VOM] = eintrag[VOM]
                gesetzt = True
        elif schluessel != VOM:
            neu[schluessel] = wert
    if not gesetzt and text:
        neu[NOTIZ] = text
        if VOM in eintrag:
            neu[VOM] = eintrag[VOM]
    return neu


def _element_teile(eintrag: dict, geruest: Geruest, b: Behaelter,
                   pos: int) -> list[tuple[int, str]]:
    """Die Freitexte der Listen im Eintrag, mit Einleitung; sie werden dem Element genommen."""
    teile: list[tuple[int, str]] = []
    for e in _elemente(geruest, b, pos):
        liste = eintrag.get(e.liste)
        if not isinstance(liste, list) or e.index >= len(liste):
            continue
        element = liste[e.index]
        if not isinstance(element, dict) or e.feld not in element:
            continue
        text = _text_von(element.pop(e.feld))
        if text:
            teile.append((e.zeile, f"{e.wort} {e.name}: {text}"))
    return teile


def _elemente(geruest: Geruest, b: Behaelter, pos: int) -> list:
    for bereich in geruest.bereiche:
        if bereich.behaelter is b:
            return bereich.eintraege[pos].elemente if pos < len(bereich.eintraege) else []
    return []


def _eintrag_paare(inhalt: Any) -> list[tuple[int, Any, Any]]:
    """(Position, Platz, Eintrag) eines Behaelters; der Platz ist Index oder Schluessel."""
    if isinstance(inhalt, list):
        return [(i, i, e) for i, e in enumerate(inhalt)]
    if isinstance(inhalt, dict):
        return [(i, k, v) for i, (k, v) in enumerate(inhalt.items())]
    return []


def _zeilen_der_felder(geruest: Geruest, b: Behaelter, pos: int) -> dict[str, int]:
    for bereich in geruest.bereiche:
        if bereich.behaelter is b and pos < len(bereich.eintraege):
            return {f.name: f.zeile for f in bereich.eintraege[pos].felder}
    return {}


def _eintraege_anwenden(daten: dict, geruest: Geruest, datei_: Datei,
                        nach_ziel: dict[tuple, list[Stueck]]) -> dict[str, int]:
    """Notizen in die Eintraege. Gibt zurueck, wie oft ein alter Name `notiz` wurde."""
    umbenannt: dict[str, int] = {}
    for b in datei_.behaelter:
        if b.form == "budgets":
            continue
        for pos, platz, eintrag in _eintrag_paare(daten.get(b.schluessel)):
            if not isinstance(eintrag, dict):
                continue
            stuecke = nach_ziel.get(("eintrag", b.schluessel, pos), [])
            teile = [(s.von, _stueck_text(s)) for s in stuecke]
            teile += _element_teile(eintrag, geruest, b, pos)
            alt = [n for n in b.alt if n in eintrag]
            if not (teile or alt):
                continue
            for n in alt:
                umbenannt[n] = umbenannt.get(n, 0) + 1
            zeilen = _zeilen_der_felder(geruest, b, pos)
            neu = _eintrag_umbauen(eintrag, teile, zeilen, b)
            daten[b.schluessel][platz] = neu
    return umbenannt


def _bereiche_anwenden(daten: dict, nach_ziel: dict[tuple, list[Stueck]], datei_: Datei) -> None:
    """Die Notizen ohne Eintrag: unter `notizen:`, der Ort ist `bereich` oder ein Pfad."""
    orte = {z: s for z, s in nach_ziel.items() if z[0] in ("bereich", "einstellung")}
    if not orte:
        return
    bisher = daten.get(BEREICHE)
    if bisher is not None and not isinstance(bisher, dict):
        raise NichtUmwandelbarError(f"`{BEREICHE}` ist keine Zuordnung")
    block = dict(bisher or {})
    for ziel, stuecke in sorted(orte.items(), key=lambda p: p[1][0].von):
        ort = BEREICH if ziel[0] == "bereich" else ziel[1]
        vorher = block.get(ort)
        if vorher is not None and not isinstance(vorher, dict):
            raise NichtUmwandelbarError(f"{BEREICHE}.{ort} ist keine Zuordnung")
        alt = dict(vorher or {})
        texte = [t for t in (_text_von(alt.get(NOTIZ)),) if t]
        texte += [_stueck_text(s) for s in stuecke]
        neu = {NOTIZ: "\n\n".join(texte)}
        if alt.get(VOM):
            neu[VOM] = alt[VOM]
        block[ort] = neu
    if datei_.notizen_zuerst:
        daten_neu = {BEREICHE: block, **{k: v for k, v in daten.items() if k != BEREICHE}}
    else:
        daten_neu = {**{k: v for k, v in daten.items() if k != BEREICHE}, BEREICHE: block}
    daten.clear()
    daten.update(daten_neu)


def anwenden(daten: dict, geruest: Geruest, datei_: Datei,
             stuecke: list[Stueck]) -> tuple[dict, dict[str, int]]:
    """Die Daten mit den Notizen. Die Eingabe bleibt unveraendert."""
    neu = copy.deepcopy(daten)
    nach_ziel = _stuecke_nach_ziel(stuecke)
    umbenannt = _eintraege_anwenden(neu, geruest, datei_, nach_ziel)
    _bereiche_anwenden(neu, nach_ziel, datei_)
    return neu, umbenannt


# --------------------------------------------------------------- pruefen


def ohne_notizen(daten: Any, datei_: Datei) -> Any:
    """Die Daten ohne alles, was eine Notiz ist -- auch unter einem alten Namen.

    Damit vergleicht die Pruefung vorher und nachher: Alles andere muss gleich sein.
    """
    kopie = copy.deepcopy(daten) if isinstance(daten, dict) else daten
    if not isinstance(kopie, dict):
        return kopie
    kopie.pop(BEREICHE, None)
    for b in datei_.behaelter:
        inhalt = kopie.get(b.schluessel)
        eintraege = list(inhalt.values()) if isinstance(inhalt, dict) else inhalt
        for eintrag in eintraege if isinstance(eintraege, list) else []:
            if isinstance(eintrag, dict):
                for n in (NOTIZ, VOM, *b.alt):
                    eintrag.pop(n, None)
                _elemente_leeren(eintrag, b)
    return kopie


def _elemente_leeren(eintrag: dict, b: Behaelter) -> None:
    for liste, feld, _name, _wort in b.elemente:
        for element in eintrag.get(liste) or []:
            if isinstance(element, dict):
                element.pop(feld, None)


def _pruefen(name: str, text: str, neu: str, daten: dict, neu_daten: Any,
             stuecke: list[Stueck], datei_: Datei) -> list[str]:
    fehler = []
    if neu_daten is None:
        neu_daten = {}
    vorher = lesen(text)
    gezaehlt = sum(s.zeilen for s in stuecke)
    if gezaehlt != len(vorher):
        fehler.append(f"{name}: {len(vorher)} Kommentarzeilen, aber {gezaehlt} in Stuecken")
    belegt = [z for s in stuecke for z in range(s.von, s.bis + 1)]
    if sorted(belegt) != sorted(k.zeile for k in vorher):
        fehler.append(f"{name}: nicht jede Kommentarzeile steht in genau einem Stueck")
    if lesen(neu):
        fehler.append(f"{name}: die neue Datei hat noch Kommentare")
    if ohne_notizen(daten, datei_) != ohne_notizen(neu_daten, datei_):
        fehler.append(f"{name}: ohne ihre Notizen hat die Datei nicht dieselben Werte")
    fehler += _notizen_pruefen(name, neu_daten, stuecke)
    return fehler


def _notizen_pruefen(name: str, neu_daten: Any, stuecke: list[Stueck]) -> list[str]:
    """Steht der Text jedes Stuecks in der Notiz, in die er gehoert?"""
    fehler = []
    for s in stuecke:
        if s.weg:
            continue
        gefunden = _notiz_zu(neu_daten, s.ziel)
        if _stueck_text(s) not in gefunden:
            fehler.append(f"{name}: Zeilen {s.von + 1}-{s.bis + 1} stehen nicht in ihrer Notiz")
    return fehler


def _notiz_zu(daten: Any, ziel: tuple) -> str:
    if ziel[0] == "eintrag":
        inhalt = daten.get(ziel[1])
        if isinstance(inhalt, list):
            eintrag = inhalt[ziel[2]] if ziel[2] < len(inhalt) else {}
        elif isinstance(inhalt, dict):
            schluessel = list(inhalt)
            eintrag = inhalt[schluessel[ziel[2]]] if ziel[2] < len(schluessel) else {}
        else:
            eintrag = {}
        return _text_von(eintrag.get(NOTIZ)) if isinstance(eintrag, dict) else ""
    ort = BEREICH if ziel[0] == "bereich" else ziel[1]
    block = (daten.get(BEREICHE) or {}).get(ort) or {}
    return _text_von(block.get(NOTIZ))


# ----------------------------------------------------------- umwandeln


def _umleiten(stuecke: list[Stueck], daten: dict, spec: Datei) -> None:
    """Ein Kommentar an einem Eintrag, der keine Zuordnung ist, geht in die Notiz des Bereichs.

    Ein Eintrag, der nur ein Wert ist (`id:` ohne Felder), hat keinen Platz fuer eine Notiz.
    """
    for s in stuecke:
        if s.ziel[0] != "eintrag":
            continue
        b = next(b for b in spec.behaelter if b.schluessel == s.ziel[1])
        paare = _eintrag_paare(daten.get(b.schluessel))
        if s.ziel[2] < len(paare) and isinstance(paare[s.ziel[2]][2], dict):
            continue
        s.ziel = ("bereich",)
        s.hinweis = s.hinweis or f"Zu `{s.ort or b.schluessel}`"
        s.mit = ""


def _ohne_kommentarzeilen(text: str, stuecke: list[Stueck]) -> str | None:
    """Der Text ohne die ganzen Kommentarzeilen, wenn das alles ist, was zu tun ist.

    Fuer Dateien, die nur den Kopf der App tragen: Sie bleiben, wie sie sind (eine
    Datei mit tausend Handentscheidungen wird nicht neu gesetzt, um einen Kopf
    loszuwerden). `None`, wenn mehr zu tun ist.
    """
    if not stuecke or any(not s.weg or s.lage in ("F", "S") for s in stuecke):
        return None
    weg = {z for s in stuecke for z in range(s.von, s.bis + 1)}
    zeilen = text.split("\n")
    rest = [z for i, z in enumerate(zeilen) if i not in weg]
    while rest and not rest[0].strip():
        rest.pop(0)
    return "\n".join(rest)


def umwandeln(name: str, text: str, *, nochmal: bool = True) -> Umwandlung:
    """Eine Datei umwandeln, im Speicher. Geschrieben wird hier nichts.

    `nochmal` laesst die Pruefung zu, dass eine zweite Umwandlung der neuen Datei nichts
    mehr findet.
    """
    ergebnis = Umwandlung(name, text=text)
    if name in OHNE_SEITE:
        return ergebnis
    spec = datei(name)
    # Ohne ein einziges `#` und ohne einen der alten Namen gibt es nichts zu finden. Der
    # Weg ist der schnelle: Die App fragt bei jedem Start, und `overrides.yaml` hat
    # zwoelftausend Zeilen. Eine Datei, die sich nicht lesen laesst, faellt hier nicht auf;
    # sie scheitert dort, wo sie gelesen wird.
    if "#" not in text and not any(n in text for n in spec.alte_namen):
        return ergebnis
    try:
        daten = yaml.safe_load(text)
        if daten is None:
            daten = {}
        if not isinstance(daten, dict):
            raise NichtUmwandelbarError("an der Wurzel steht keine Zuordnung")
        ergebnis.stuecke = einordnen(name, text, spec)
        _umleiten(ergebnis.stuecke, daten, spec)
        geruest = Geruest(text, spec)
        neu_daten, ergebnis.umbenannt = anwenden(daten, geruest, spec, ergebnis.stuecke)
    except (NichtUmwandelbarError, yaml.YAMLError) as fehler:
        ergebnis.fehler.append(f"{name}: {fehler}")
        return ergebnis
    ergebnis.zeilen_vorher = len(lesen(text))
    if not ergebnis.stuecke and not ergebnis.umbenannt:
        return ergebnis
    neu = _ohne_kommentarzeilen(text, ergebnis.stuecke) if neu_daten == daten else None
    if neu is None:
        neu = _dateien.yaml_text(neu_daten)
    ergebnis.neu = neu
    ergebnis.fehler += _pruefen(name, text, neu, daten, yaml.safe_load(neu), ergebnis.stuecke, spec)
    if nochmal and not ergebnis.fehler:
        zweite = umwandeln(name, neu, nochmal=False)
        if zweite.neu is not None or zweite.fehler:
            ergebnis.fehler.append(f"{name}: eine zweite Umwandlung fand noch etwas zu tun")
    return ergebnis


# --------------------------------------------------------------- Lauf


@dataclass(slots=True)
class Plan:
    """Was `finctl umstellen` in einem Datenordner tun wuerde."""

    config: Path
    umwandlungen: list[Umwandlung] = field(default_factory=list)
    unberuehrt: list[str] = field(default_factory=list)

    @property
    def zu_tun(self) -> list[Umwandlung]:
        """Die Dateien mit einem Anlass: Kommentare, alte Namen, eine Seitendatei zum Zusammenlegen.

        Das ist die eine Erkennung: Nach ihr meldet `finctl umstellen` „Nichts umzustellen“,
        und nach ihr haelt die App an (`halt_wenn_offen`).
        """
        return [u for u in self.umwandlungen if u.anlass]

    @property
    def zu_schreiben(self) -> list[Umwandlung]:
        """Alles, was ein Lauf anfasst, wenn er etwas zu tun hat: auch die Koepfe der App."""
        return [u for u in self.umwandlungen if u.neu is not None or u.loeschen]

    @property
    def zusammenlegungen(self) -> list[Zusammenlegung]:
        return [z for u in self.umwandlungen for z in u.zusammengelegt]

    @property
    def fehler(self) -> list[str]:
        return [f for u in self.umwandlungen for f in u.fehler]

    @property
    def offen(self) -> bool:
        """Fuehrt dieser Datenordner noch eine Form, die die App nicht mehr liest?"""
        return bool(self.zu_tun or self.fehler)

    def beschreibung(self) -> list[str]:
        """Je Datei mit Anlass ein Satz, woran es liegt."""
        saetze = []
        for u in self.zu_tun:
            if u.loeschen:
                basen = [z.basis for z in self.zusammenlegungen if z.seite == u.name]
                saetze.append(f"{u.name} (mit {' und '.join(basen) or 'der Basisdatei'} "
                              "zusammenlegen)")
            elif u.umbenannt and not any(not s.weg for s in u.stuecke):
                saetze.append(f"{u.name} (alte Feldnamen)")
            elif u.neu is not None:
                saetze.append(f"{u.name} (Kommentare)")
        return saetze + list(self.fehler)


def _zusammenlegen(plan: Plan) -> None:
    """Phase 2: Basis- und Seitendatei der Paare zu einer Datei. Die Seite wird entfernt.

    Die Paare gehen in der Reihenfolge von `PAARE`; ein spaeteres sieht die Basisdatei so, wie
    das fruehere sie hinterliess. Eine Seitendatei in zwei Paaren (`settings_custom.yaml`) geht
    in beide so ein, wie sie nach dem Umwandeln der Kommentare war.
    """
    nach_name = {u.name: u for u in plan.umwandlungen}
    for paar in PAARE:
        seite = nach_name.get(paar.seite)
        if seite is None or seite.fehler:
            continue
        basis = nach_name.get(paar.basis)
        if basis is None:
            basis = Umwandlung(paar.basis)
            plan.umwandlungen.append(basis)
            nach_name[paar.basis] = basis
        if basis.fehler:
            continue
        pfad = plan.config / paar.basis
        basis_da = pfad.exists()
        if seite.seitentext is None:
            seite.seitentext = seite.neu if seite.neu is not None else seite.text
        basis_text = basis.neu if basis.neu is not None else basis.text
        try:
            b_daten = yaml.safe_load(basis_text)
            s_daten = yaml.safe_load(seite.seitentext)
        except yaml.YAMLError as fehler:
            seite.fehler.append(f"{paar.seite}: {fehler}")
            continue
        b_daten = b_daten if isinstance(b_daten, dict) else {}
        schon_gelegt = bool(basis.zusammengelegt)
        if not basis_da and not schon_gelegt:
            b_daten = _paare.vorlage_lesen(paar)
        gelegt = _paare.zusammenlegen(
            paar, b_daten, s_daten if isinstance(s_daten, dict) else {},
            basis_text=basis_text if basis_da or schon_gelegt else None,
            config=plan.config)
        basis.zusammengelegt.append(gelegt)
        seite.loeschen = True
        seite.neu = None
        basis.fehler += gelegt.fehler
        if gelegt.neu is not None:
            basis.neu = gelegt.neu


def tabelle_gegen_datei(config: Path, text: str) -> list[str]:
    """Steht in der Tabelle `settings` etwas, das `settings_custom.yaml` nicht sagt?

    Bis N.3f las `_floor_for` die Untergrenze aus der Tabelle, und `/api/setting` legte eine
    Notiz nur dort ab. Beides ginge beim Zusammenlegen verloren, das nur die Datei sieht. Der
    Lauf haelt deshalb an, wenn die Tabelle eine Zeile hat, die die Datei nicht hat, einen
    anderen Wert oder eine Notiz. Eine Zeile nur in der Datei ist kein Fund: `init` hat sie
    nur noch nicht gespiegelt. Ohne `finance.db` (oder ohne die Tabelle) gibt es nichts zu
    vergleichen.
    """
    import sqlite3
    import tempfile

    db = config.parent / "data" / "finance.db"
    if not db.exists():
        return []
    # Eine Kopie lesen: Eine Datenbank im WAL-Betrieb legt beim Lesen `-shm` und `-wal` neben
    # sich an, und der Datenordner soll unberuehrt bleiben (auch bei `--probe`).
    with tempfile.TemporaryDirectory(prefix="finctl-settings-") as tmp:
        for suffix in ("", "-wal"):
            quelle = db.with_name(db.name + suffix)
            if quelle.exists():
                shutil.copyfile(quelle, Path(tmp) / quelle.name)
        try:
            c = sqlite3.connect(Path(tmp) / db.name)
            try:
                zeilen = c.execute("SELECT key, value, note FROM settings").fetchall()
            finally:
                c.close()
        except sqlite3.Error:
            return []
    gelesen = yaml.safe_load(text)
    datei = gelesen.get("einstellungen") if isinstance(gelesen, dict) else None
    datei = {str(k): v for k, v in _notizen_ohne(datei).items()}
    fehler = []
    for key, wert, notiz in sorted(zeilen):
        if key not in datei:
            fehler.append(f"Tabelle settings, Zeile `{key}` = {wert}: steht nicht in "
                          "settings_custom.yaml")
        elif str(datei[key]) != str(wert):
            fehler.append(f"Tabelle settings, Zeile `{key}`: {wert}, in settings_custom.yaml "
                          f"{datei[key]}")
        if notiz:
            fehler.append(f"Tabelle settings, Zeile `{key}` traegt eine Notiz, die in keiner "
                          f"Datei steht: {notiz}")
    return fehler


def _notizen_ohne(zuordnung: Any) -> dict:
    from finctl.notizen import ohne

    return ohne(zuordnung if isinstance(zuordnung, dict) else {})


def planen(config: Path) -> Plan:
    """Jede Datei in `config/` umwandeln, im Speicher; dann die Paare zusammenlegen."""
    plan = Plan(config)
    for pfad in sorted(config.glob("*.y*ml")):
        if pfad.suffix not in (".yaml", ".yml"):
            continue
        if pfad.name in OHNE_SEITE:
            plan.unberuehrt.append(pfad.name)
            continue
        plan.umwandlungen.append(umwandeln(pfad.name, pfad.read_text(encoding="utf-8")))
    _zusammenlegen(plan)
    seite = next((u for u in plan.umwandlungen if u.name == "settings_custom.yaml"), None)
    if seite is not None and not seite.fehler:
        seite.fehler += tabelle_gegen_datei(
            config, seite.seitentext if seite.seitentext is not None else seite.text)
    return plan


def halt_wenn_offen(config: Path | None = None) -> None:
    """`AlteFormError`, wenn `finctl umstellen` in `config/` etwas faende.

    Dieselbe Frage, die `finctl umstellen` mit „Nichts umzustellen“ beantwortet
    (`Plan.offen`). Die App liest eine Datei in alter Form nicht mehr -- nach dem
    Zusammenlegen eines Paars die Seitendatei nicht, nach dem Umwandeln einen
    Kommentar nicht als Notiz --, und sie liest nicht still nur die halben Werte. Sie
    haelt an und nennt den Befehl. Gerufen wird es beim Start der App, bei `finctl init`
    und bei jedem Befehl mit Hauptbuch. Dateien ohne Seite (`OHNE_SEITE`) zaehlen nicht.
    """
    from finctl import pfade

    config = config or pfade.CONFIG_DIR
    plan = planen(config)
    if not plan.offen:
        return
    befehl = pfade.aus_umgebung("finctl")
    raise AlteFormError(
        f"Der Datenordner {config.parent} ist noch nicht umgestellt: "
        f"{'; '.join(plan.beschreibung())}.\n"
        "Die App liest diese Form nicht mehr und aendert nichts, bis es soweit ist.\n"
        f"  Ansehen:   {befehl} umstellen --probe <ordner ausserhalb>\n"
        f"  Umstellen: {befehl} umstellen")


def _nummeriert(basis: Path) -> Path:
    if not basis.exists():
        return basis
    n = 2
    while (ziel := basis.with_name(f"{basis.stem}_{n}{basis.suffix}")).exists():
        n += 1
    return ziel


def _kopieren(quelle: Path, ziel: Path) -> None:
    shutil.copytree(quelle, ziel, ignore=shutil.ignore_patterns("*.lock", ".DS_Store"))


def _schreiben(pfad: Path, text: str) -> None:
    neu = pfad.with_name(pfad.name + ".neu")
    neu.write_text(text, encoding="utf-8")
    neu.replace(pfad)


def ausfuehren(wurzel: Path, *, heute: date | None = None) -> tuple[Plan, Path | None, Path | None]:
    """Den Datenordner umstellen. Gibt Plan, Sicherung und Bericht zurueck.

    Mit Fehlern in einer Pruefung geschieht nichts: Der Plan kommt zurueck, alles andere ist
    `None`. Ohne etwas zu tun ebenso.
    """
    heute = heute or date.today()
    config = wurzel / "config"
    plan = planen(config)
    if plan.fehler or not plan.zu_tun:
        return plan, None, None
    sicherung = _nummeriert(wurzel / ARCHIV_ORDNER / f"vor_umstellung_{heute.isoformat()}")
    sicherung.parent.mkdir(parents=True, exist_ok=True)
    _kopieren(config, sicherung / "config")
    for u in plan.zu_schreiben:
        if u.loeschen:
            (config / u.name).unlink()
        else:
            _schreiben(config / u.name, u.neu)
        _dateien.vergessen(config / u.name)
    bericht = _bericht_schreiben(plan, wurzel / NOTIZEN_ORDNER, heute, sicherung)
    return plan, sicherung, bericht


def probieren(wurzel: Path, ziel: Path, *, heute: date | None = None) -> tuple[Plan, Path | None]:
    """Nur ansehen: die umgewandelte Kopie und der Bericht kommen nach `ziel`.

    `ziel` darf nicht im Datenordner liegen. Der Datenordner wird nicht geschrieben.
    """
    heute = heute or date.today()
    if wurzel.resolve() in (ziel.resolve(), *ziel.resolve().parents):
        raise ValueError("Der Probeordner muss ausserhalb des Datenordners liegen.")
    plan = planen(wurzel / "config")
    ziel.mkdir(parents=True, exist_ok=True)
    kopie = ziel / "config"
    if kopie.exists():
        shutil.rmtree(kopie)
    _kopieren(wurzel / "config", kopie)
    if plan.fehler:
        return plan, None
    for u in plan.zu_schreiben:
        if u.loeschen:
            (kopie / u.name).unlink()
        else:
            _schreiben(kopie / u.name, u.neu)
    return plan, _bericht_schreiben(plan, ziel, heute, None)


def zusammenfassung(plan: Plan, sicherung: Path | None, bericht: Path | None,
                    probe: Path | None = None) -> dict:
    """Was ein Lauf ergab, als Daten: fuer die Ausgabe von `finctl umstellen`."""
    dateien = []
    for u in plan.zu_schreiben:
        if u.loeschen:
            continue
        weg = sum(s.zeilen for s in u.weggefallen)
        dateien.append({"name": u.name, "kommentare": u.zeilen_vorher, "weggefallen": weg,
                        "in_notizen": u.zeilen_vorher - weg, "umbenannt": u.umbenannt,
                        "lagen": u.zaehlung()})
    paare = [{"basis": z.basis, "seite": z.seite, "ueberschrieben": len(z.ueberschrieben),
              "notizen_zusammen": z.notizen, "budgets": z.budgets, "aus_seite": z.aus_seite,
              "ungelesen": z.ungelesen, "ausgeblendet": z.ausgeblendet}
             for z in plan.zusammenlegungen]
    return {"dateien": dateien, "paare": paare, "zu_tun": bool(plan.zu_tun),
            "fehler": plan.fehler, "probe": str(probe) if probe else None,
            "sicherung": str(sicherung) if sicherung else None,
            "bericht": str(bericht) if bericht else None,
            "unberuehrt": plan.unberuehrt}


# ------------------------------------------------------------- Bericht


def _zitat(text: str) -> list[str]:
    return ["    " + z if z else "" for z in text.split("\n")]


def _ort(s: Stueck) -> str:
    if s.weg:
        return f"weggefallen ({s.weg})"
    if s.ziel[0] == "eintrag":
        return f"Notiz von `{s.ort or s.ziel[1]}`"
    if s.ziel[0] == "einstellung":
        return f"Notiz der Einstellung `{s.ziel[1]}`"
    return "Notiz des Bereichs" + (f" ({s.hinweis})" if s.hinweis else "")


def bericht_text(plan: Plan, heute: date, sicherung: Path | None) -> str:
    """Der Bericht als Markdown: jeder Kommentar und wo er jetzt steht."""
    z = ["# Umstellung: Kommentare werden Notizen", "",
         f"Stand {heute.isoformat()}. Datenordner: `{plan.config.parent}`.", ""]
    if sicherung is not None:
        z += [f"Gesichert vor der Umstellung: `{sicherung}`.", ""]
    zu_tun = [u for u in plan.zu_schreiben if u.stuecke or u.umbenannt]
    paare = plan.zusammenlegungen
    z += [f"- umgewandelt: {len(zu_tun)} Dateien",
          f"- zusammengelegt: {len(paare)} Paare, die Seitendatei ist entfernt",
          f"- unveraendert: {len(plan.umwandlungen) - len(plan.zu_schreiben)} Dateien",
          f"- ohne Seite, nicht angefasst: {', '.join(plan.unberuehrt) or '–'}", ""]
    z += _paare_text(paare)
    z += ["## Kommentarzeilen je Datei und Lage", "",
          "| Datei | Zeilen | " + " | ".join(LAGEN) + " | in Notizen | weggefallen | umbenannt |",
          "|---|---:|" + "---:|" * len(LAGEN) + "---:|---:|---|"]
    summe = dict.fromkeys(LAGEN, 0)
    weg_gesamt = 0
    for u in zu_tun:
        zaehl = u.zaehlung()
        weg = sum(s.zeilen for s in u.weggefallen)
        weg_gesamt += weg
        for lage in LAGEN:
            summe[lage] += zaehl[lage]
        umb = ", ".join(f"`{n}` {c}" for n, c in sorted(u.umbenannt.items())) or ""
        z.append(f"| `{u.name}` | {u.zeilen_vorher} | "
                 + " | ".join(str(zaehl[lage] or "") for lage in LAGEN)
                 + f" | {sum(zaehl.values())} | {weg or ''} | {umb} |")
    z.append(f"| **Summe** | {sum(u.zeilen_vorher for u in zu_tun)} | "
             + " | ".join(str(summe[lage]) for lage in LAGEN)
             + f" | {sum(summe.values())} | {weg_gesamt} | |")
    z += ["", "## Weggefallen", ""]
    z += _weggefallen_text(zu_tun)
    z += ["", "## Jeder Kommentar und wo er jetzt steht", ""]
    for u in zu_tun:
        z += [f"### `{u.name}`", ""]
        for s in u.stuecke:
            bis = f"–{s.bis + 1}" if s.bis != s.von else ""
            z.append(f"- Zeile {s.von + 1}{bis} · Lage {s.lage} · {_ort(s)}")
            z += _zitat(s.text)
        z.append("")
    return "\n".join(z).rstrip() + "\n"


def _liste(titel: str, posten: list[str]) -> list[str]:
    return [f"- {titel}: " + ", ".join(f"`{p}`" for p in posten)] if posten else []


def _paare_text(paare: list[Zusammenlegung]) -> list[str]:
    """Was beim Zusammenlegen geschah, je Paar."""
    z: list[str] = []
    for p in paare:
        z += [f"## Zusammengelegt: `{p.seite}` in `{p.basis}`", ""]
        z.append(f"- Basiswerte, die die Seite ueberschrieben hatte und die jetzt in einer "
                 f"Notiz stehen: {len(p.ueberschrieben)}")
        z += [f"  - `{ort}`: {wert}" for ort, wert in p.ueberschrieben]
        z += _liste("Notizen, die zusammentrafen (Basis zuerst)", p.notizen)
        z += _liste("Budgets aus der Seite", p.budgets)
        z += _liste("Was die Seite brachte", p.aus_seite)
        z += _liste("Felder der Seite, die kein Leser je las (nicht uebernommen, in der "
                    "Sicherung)", p.ungelesen)
        z += _liste("Ausgeblendet gewesen, jetzt nicht mehr in der Datei (nur in der Sicherung; "
                    "die Notiz steht beim Bereich)", p.ausgeblendet)
        z.append("")
    return z


def _weggefallen_text(zu_tun: list[Umwandlung]) -> list[str]:
    z = []
    for u in zu_tun:
        weg = u.weggefallen
        if not weg:
            continue
        je_grund: dict[str, int] = {}
        for s in weg:
            je_grund[s.weg] = je_grund.get(s.weg, 0) + s.zeilen
        grund = ", ".join(f"{n} Zeilen: {g}" for g, n in sorted(je_grund.items()))
        z.append(f"- `{u.name}`: {grund}")
    return z or ["Nichts."]


def _bericht_schreiben(plan: Plan, ordner: Path, heute: date, sicherung: Path | None) -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / f"umstellung_{heute.isoformat()}.md"
    if sicherung is not None:
        # Ein echter Lauf ueberschreibt nie den Bericht eines frueheren am selben Tag.
        pfad = _nummeriert(pfad)
    pfad.write_text(bericht_text(plan, heute, sicherung), encoding="utf-8")
    return pfad


__all__ = ["AlteFormError", "Plan", "Umwandlung", "ausfuehren", "halt_wenn_offen", "planen",
           "probieren", "umwandeln", "zusammenfassung"]
