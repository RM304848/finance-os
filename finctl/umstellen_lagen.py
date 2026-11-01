"""Wo ein Kommentar steht -- und wohin seine Notiz gehoert.

Die Umwandlung der Kommentare in Notizen (`finctl umstellen`, Schritt 5, N.2) fragt
hier: Welche Kommentare hat die Datei, in welcher LAGE steht jeder, und an welchem Ort
wird er Notiz. Gelesen wird der Text, nicht die Daten: Kommentare kennt YAML nicht.

DIE LAGEN (Entscheidung 2 und N.0, Nummer 10):

    K  Kopf         vor dem ersten Inhalt der Datei                  -> Notiz des Bereichs
    A  Abschnitt    ein Block, der eine Gruppe von Eintraegen einleitet:
                    mit Leerzeile danach, oder mit einer Strichlinie     -> Notiz des Bereichs,
                    am Anfang (`# ---- Titel`); er gilt bis zum naechsten  "Stand vor <Eintrag>"
                    -- oder, ohne Leerzeile davor und nicht tief genug    "Stand nach <Eintrag>"
                    fuer die Felder des Eintrags darueber (N.2b)
    E  Eintrag      ein Block direkt ueber einem Eintrag oder zwischen
                    zwei Feldern in ihm, oder unter seinem letzten Feld
                    ohne Leerzeile davor und in der Spalte seiner Felder  -> Notiz des Eintrags
    F  Feld         ein Kommentar hinter dem Wert, samt Fortsetzung
                    in derselben Spalte                              -> Notiz des Eintrags,
                                                                       "`feld`: ..."
    S  Einstellung  ein Kommentar an einem Schluessel ohne Kennung   -> `notizen:` unter dem Pfad
    -  keine Lage   ein Block ueber einer Zuordnung nach Konto, am Ende der Datei, in
                    einem Behaelter ohne Kennungen                   -> Notiz des Bereichs,
                                                                       "Zu <Schluessel>"

Nichts geht verloren: Jede Kommentarzeile bekommt genau ein Stueck, und jedes Stueck
einen Ort. Wegfallen darf nur (`Stueck.weg`), was Entscheidung 3 nennt: der Kopf, den die
App selbst schrieb, und ein Feldkommentar, der nur den Wert in Euro wiederholt.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

import yaml

from finctl.umstellen_form import (
    BUDGETS,
    LISTE,
    ZUORDNUNG,
    Behaelter,
    Datei,
    ist_kopf_der_app,
    kopf_zeilen,
)

#: Lagen, wie die Tabelle unter N.0 sie nennt.
LAGEN = ("K", "A", "E", "F", "S", "–")

WEG_KOPF = "Kopf der App"
WEG_EURO = "wiederholt den Wert in Euro"

_STRICH = re.compile(r"^\s*[-=_*~]{3,}")
_EURO = re.compile(r"^-?\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?(?:\s*(?:€|EUR|Euro))?$|"
                   r"^-?\d+(?:,\d{1,2})?(?:\s*(?:€|EUR|Euro))?$")


class NichtUmwandelbarError(ValueError):
    """Die Datei hat eine Form, die der Umwandler nicht kennt (etwa eine Liste an der Wurzel)."""


# --------------------------------------------------------------------- lesen


@dataclass(frozen=True, slots=True)
class Kommentar:
    """Eine Kommentarzeile."""

    zeile: int       # 0-basiert
    spalte: int
    text: str        # nach dem `#`, ohne den einen Leerraum dahinter
    eigene: bool     # steht allein in der Zeile


def _anfaenge(text: str) -> list[int]:
    return [0] + [m.end() for m in re.finditer("\n", text)]


def lesen(text: str) -> list[Kommentar]:
    """Alle Kommentare der Datei, in der Reihenfolge der Datei.

    Ein Kommentar ist, was zwischen zwei Tokens des YAML-Scanners steht und mit `#`
    beginnt. Ein `#` in einem Text oder in einem Block (`|`) ist kein Token-Zwischenraum.
    """
    anfaenge = _anfaenge(text)
    belegt = sorted((t.start_mark.index, t.end_mark.index)
                    for t in yaml.scan(text, Loader=yaml.SafeLoader))
    luecken: list[tuple[int, int]] = []
    pos = 0
    for start, ende in belegt:
        if start > pos:
            luecken.append((pos, start))
        pos = max(pos, ende)
    luecken.append((pos, len(text)))

    aus: list[Kommentar] = []
    for von, bis in luecken:
        for treffer in re.finditer(r"#[^\n]*", text[von:bis]):
            index = von + treffer.start()
            zeile = bisect.bisect_right(anfaenge, index) - 1
            spalte = index - anfaenge[zeile]
            rest = treffer.group()[1:].rstrip()
            aus.append(Kommentar(zeile, spalte, rest.removeprefix(" "),
                                 not text[anfaenge[zeile]:index].strip()))
    return aus


# -------------------------------------------------------------------- Geruest


@dataclass(slots=True)
class Feld:
    name: str
    zeile: int
    knoten: yaml.Node


@dataclass(frozen=True, slots=True)
class Element:
    """Ein Freitext in einer Liste im Eintrag, etwa das `note` eines Teilstuecks."""

    liste: str
    feld: str
    zeile: int
    index: int
    name: str       # was das Element benennt, fuer die Einleitung
    wort: str       # das Wort davor ("Teilstück")


@dataclass(slots=True)
class Eintrag:
    behaelter: Behaelter
    pos: int
    kennung: str
    start: int
    #: Die Spalte, in der seine Felder stehen; hat er keine, die seines Schluessels (N.2b).
    spalte: int = 0
    felder: list[Feld] = field(default_factory=list)
    blaetter: list[Feld] = field(default_factory=list)
    elemente: list[Element] = field(default_factory=list)


@dataclass(slots=True)
class Bereich:
    """Ein Schluessel oben in der Datei und die Zeilen, die zu ihm gehoeren."""

    schluessel: str
    zeile: int
    behaelter: Behaelter | None = None
    eintraege: list[Eintrag] = field(default_factory=list)


@dataclass(slots=True)
class Schluessel:
    zeile: int
    tiefe: int
    pfad: str
    name: str
    knoten: yaml.Node


def _text(knoten: yaml.Node) -> str:
    return str(getattr(knoten, "value", ""))


def _paare(knoten: yaml.Node) -> list[tuple[yaml.Node, yaml.Node]]:
    return list(knoten.value) if isinstance(knoten, yaml.MappingNode) else []


def _felder(knoten: yaml.Node) -> list[Feld]:
    return [Feld(_text(k), k.start_mark.line, v) for k, v in _paare(knoten)]


def _element_felder(eintrag: Eintrag, knoten: yaml.Node, spec: tuple) -> None:
    """Die Freitexte in den Listen eines Eintrags (zum Beispiel `segments_observed[].note`)."""
    for liste, feld, namensfeld, wort in spec:
        for k, v in _paare(knoten):
            if _text(k) != liste or not isinstance(v, yaml.SequenceNode):
                continue
            for i, element in enumerate(v.value):
                zeilen = {_text(ek): (ek.start_mark.line, ev) for ek, ev in _paare(element)}
                if feld in zeilen:
                    name = _text(zeilen[namensfeld][1]) if namensfeld in zeilen else str(i + 1)
                    eintrag.elemente.append(Element(liste, feld, zeilen[feld][0], i, name, wort))


def _ist_block(knoten: yaml.Node) -> bool:
    """Eine Zuordnung oder Liste, die ueber mehrere Zeilen laeuft und nicht leer ist."""
    return (isinstance(knoten, (yaml.MappingNode, yaml.SequenceNode))
            and not knoten.flow_style and bool(knoten.value))


def _strichspalte(zeilen: list[str], knoten: yaml.Node) -> int:
    """Die Spalte des `-` vor einem Listeneintrag."""
    treffer = re.match(r"(\s*)-(?:\s|$)", zeilen[knoten.start_mark.line])
    return len(treffer.group(1)) if treffer else knoten.start_mark.column


def _feldspalte(behaelter: Behaelter, zeilen: list[str], schluessel: yaml.Node | None,
                knoten: yaml.Node) -> int:
    """In welcher Spalte stehen die Felder des Eintrags -- und wo, wenn er keine hat?

    Ein Eintrag mit Feldern in Blockform (`- id: a` samt den Zeilen darunter, `a:` mit
    eingerueckten Feldern): die Spalte des ersten Feldes. Ein Eintrag, der nur ein Wert ist
    (`a: 100`, `a:`, `- {id: a, ...}`, `- a`): die Spalte, in der er selbst beginnt, bei einer
    Liste die des `-`. Tiefer kann unter ihm nichts mehr stehen.
    """
    if _ist_block(knoten) and (behaelter.form != LISTE or isinstance(knoten, yaml.MappingNode)):
        return knoten.start_mark.column
    if behaelter.form == LISTE:
        return _strichspalte(zeilen, knoten)
    return schluessel.start_mark.column if schluessel is not None else 0


def _eintraege(behaelter: Behaelter, wert: yaml.Node, zeilen: list[str]) -> list[Eintrag]:
    if behaelter.form == LISTE and isinstance(wert, yaml.SequenceNode):
        rohe = [(i, _kennung(behaelter, n, i), n.start_mark.line, None, n)
                for i, n in enumerate(wert.value)]
    elif behaelter.form in (ZUORDNUNG, BUDGETS) and isinstance(wert, yaml.MappingNode):
        rohe = [(i, _text(k), k.start_mark.line, k, v) for i, (k, v) in enumerate(wert.value)]
    else:
        return []
    aus = []
    for i, kennung, start, schluessel, knoten in rohe:
        eintrag = Eintrag(behaelter, i, kennung, start,
                          _feldspalte(behaelter, zeilen, schluessel, knoten), _felder(knoten))
        if behaelter.blaetter:
            for f in eintrag.felder:
                if f.name == behaelter.blaetter:
                    eintrag.blaetter = _felder(f.knoten)
        _element_felder(eintrag, knoten, behaelter.elemente)
        aus.append(eintrag)
    return aus


def _kennung(behaelter: Behaelter, knoten: yaml.Node, i: int) -> str:
    for k, v in _paare(knoten):
        if _text(k) == behaelter.kennung:
            return _text(v)
    return str(i + 1)


def _schluessel(knoten: yaml.Node, pfad: str, tiefe: int, aus: list[Schluessel]) -> None:
    """Jeder Schluessel der Datei mit seinem Pfad. Listen zaehlen nicht in den Pfad."""
    if isinstance(knoten, yaml.SequenceNode):
        for element in knoten.value:
            _schluessel(element, pfad, tiefe, aus)
    for k, v in _paare(knoten):
        unter = f"{pfad}.{_text(k)}" if pfad else _text(k)
        aus.append(Schluessel(k.start_mark.line, tiefe, unter, _text(k), v))
        _schluessel(v, unter, tiefe + 1, aus)


def _inhaltszeilen(text: str) -> list[int]:
    """Die Zeilen, auf denen etwas anderes als Leerraum und Kommentar steht."""
    zeilen: set[int] = set()
    for t in yaml.scan(text, Loader=yaml.SafeLoader):
        von, bis = t.start_mark, t.end_mark
        if bis.index == von.index:
            continue    # Anfang/Ende einer Struktur, kein Text
        if isinstance(t, yaml.ScalarToken) and t.style in ("|", ">"):
            ende = von.line + len(str(t.value).rstrip("\n").split("\n")) if t.value else von.line
        else:
            ende = bis.line if bis.column > 0 else bis.line - 1
        zeilen.update(range(von.line, max(von.line, ende) + 1))
    return sorted(zeilen)


class Geruest:
    """Was in der Datei steht, geordnet nach Zeilen: Bereiche, Eintraege, Schluessel."""

    def __init__(self, text: str, datei: Datei) -> None:
        wurzel = yaml.compose(text)
        if wurzel is None:
            wurzel = yaml.MappingNode("tag:yaml.org,2002:map", [])
        if not isinstance(wurzel, yaml.MappingNode):
            raise NichtUmwandelbarError("an der Wurzel steht keine Zuordnung")
        self.datei = datei
        self.zeilen = text.split("\n")
        self.inhalt = _inhaltszeilen(text)
        self.bereiche: list[Bereich] = []
        self.schluessel: list[Schluessel] = []
        spec = {b.schluessel: b for b in datei.behaelter}
        for k, v in wurzel.value:
            behaelter = spec.get(_text(k))
            bereich = Bereich(_text(k), k.start_mark.line, behaelter)
            if behaelter is not None:
                bereich.eintraege = _eintraege(behaelter, v, self.zeilen)
            self.bereiche.append(bereich)
        _schluessel(wurzel, "", 0, self.schluessel)

    # -- Zeilen

    def vorher(self, zeile: int) -> int | None:
        i = bisect.bisect_left(self.inhalt, zeile)
        return self.inhalt[i - 1] if i else None

    def nachher(self, zeile: int) -> int | None:
        i = bisect.bisect_right(self.inhalt, zeile)
        return self.inhalt[i] if i < len(self.inhalt) else None

    def leer(self, zeile: int) -> bool:
        return 0 <= zeile < len(self.zeilen) and not self.zeilen[zeile].strip()

    # -- Orte

    def bereich_bei(self, zeile: int) -> Bereich | None:
        vorher = [b for b in self.bereiche if b.zeile <= zeile]
        return vorher[-1] if vorher else None

    def eintrag_bei(self, zeile: int) -> Eintrag | None:
        bereich = self.bereich_bei(zeile)
        if bereich is None:
            return None
        davor = [e for e in bereich.eintraege if e.start <= zeile]
        return davor[-1] if davor else None

    def schluesselpfad(self, zeile: int) -> Schluessel | None:
        """Der Schluessel dieser Zeile, sonst der letzte davor.

        Beginnen mehrere auf der Zeile (`match: {regex: x}`), gilt der aeusserste: der, dem
        der Rest der Zeile gehoert.
        """
        auf_zeile = [s for s in self.schluessel if s.zeile == zeile]
        if not auf_zeile:
            davor = [s for s in self.schluessel if s.zeile < zeile]
            if not davor:
                return None
            letzte = max(s.zeile for s in davor)
            auf_zeile = [s for s in davor if s.zeile == letzte]
        return min(auf_zeile, key=lambda s: s.tiefe)

    def feld_bei(self, eintrag: Eintrag, zeile: int) -> Feld | None:
        """Das Feld des Eintrags, zu dem die Zeile gehoert; bei einer Kategorie das Blatt."""
        feld = _letztes(eintrag.felder, zeile)
        if feld is not None and eintrag.blaetter and feld.name == eintrag.behaelter.blaetter:
            blatt = _letztes(eintrag.blaetter, zeile)
            return blatt or feld
        return feld


def _letztes(felder: list[Feld], zeile: int) -> Feld | None:
    davor = [f for f in felder if f.zeile <= zeile]
    return davor[-1] if davor else None


# --------------------------------------------------------------- einordnen


@dataclass(slots=True)
class Stueck:
    """Ein Kommentar (ein Block oder ein Feldkommentar mit Fortsetzung) und sein Ziel."""

    von: int                    # erste Zeile, 0-basiert
    bis: int                    # letzte Zeile
    lage: str                   # eine von LAGEN
    text: str                   # die Zeilen ohne `#`, mit Zeilenumbruechen
    #: ("eintrag", Schluessel des Behaelters, Position) | ("bereich",) | ("einstellung", Pfad)
    ziel: tuple
    #: Was vor dem Text steht: "`feld`: ", "Budget: ".
    mit: str = ""
    #: Nur beim Bereich: was die Stelle nennt ("Stand vor `x`", "Zu `y`").
    hinweis: str = ""
    weg: str = ""               # sonst der Grund, warum der Kommentar wegfaellt
    #: Auf welche Kennung sich der Hinweis bezieht (fuer den Bericht).
    ort: str = ""

    @property
    def zeilen(self) -> int:
        return self.bis - self.von + 1


def _strichlinie(zeile: str) -> bool:
    return bool(_STRICH.match(zeile))


def _block_text(gruppe: list[Kommentar]) -> str:
    zeilen = [k.text for k in gruppe]
    while zeilen and not zeilen[-1].strip():
        zeilen.pop()
    while zeilen and not zeilen[0].strip():
        zeilen.pop(0)
    return "\n".join(zeilen)


def _gruppen(kommentare: list[Kommentar]) -> list[tuple[str, list[Kommentar]]]:
    """Feldkommentare samt Fortsetzung und Bloecke aus aufeinanderfolgenden Zeilen."""
    aus: list[tuple[str, list[Kommentar]]] = []
    i = 0
    while i < len(kommentare):
        k = kommentare[i]
        gruppe = [k]
        i += 1
        while (i < len(kommentare) and kommentare[i].eigene
               and kommentare[i].zeile == gruppe[-1].zeile + 1
               and (k.eigene or kommentare[i].spalte == k.spalte)):
            gruppe.append(kommentare[i])
            i += 1
        aus.append(("block" if k.eigene else "feld", gruppe))
    return aus


class Ordner:
    """Ordnet die Kommentare einer Datei ihren Orten zu."""

    def __init__(self, name: str, text: str, datei: Datei) -> None:
        self.name = name
        self.datei = datei
        self.g = Geruest(text, datei)
        self.kommentare = lesen(text)

    def stuecke(self) -> list[Stueck]:
        aus = []
        for art, gruppe in _gruppen(self.kommentare):
            stueck = self._feld(gruppe) if art == "feld" else self._block(gruppe)
            aus.append(stueck)
        self._koepfe_der_app(aus)
        return aus

    # -- Feldkommentare

    def _feld(self, gruppe: list[Kommentar]) -> Stueck:
        zeile = gruppe[0].zeile
        text = _block_text(gruppe)
        von, bis = zeile, gruppe[-1].zeile
        eintrag = self.g.eintrag_bei(zeile)
        if eintrag is not None:
            return self._feld_im_eintrag(eintrag, zeile, von, bis, text, len(gruppe) == 1)
        bereich = self.g.bereich_bei(zeile)
        pfad = self.g.schluesselpfad(zeile)
        if (self.datei.einstellungen and bereich is not None and bereich.behaelter is None
                and pfad is not None):
            stueck = Stueck(von, bis, "S", text, ("einstellung", pfad.pfad), ort=pfad.pfad)
            if len(gruppe) == 1 and _wiederholt_euro(pfad.name, pfad.knoten, text):
                stueck.weg = WEG_EURO
            return stueck
        return self._ohne_lage(von, bis, text, bereich.schluessel if bereich else "")

    def _feld_im_eintrag(self, eintrag: Eintrag, zeile: int, von: int, bis: int, text: str,
                         einzeilig: bool) -> Stueck:
        if eintrag.behaelter.form == BUDGETS:
            return Stueck(von, bis, "F", text, self._rolle(eintrag), mit="Budget: ",
                          hinweis=f"Budget von `{eintrag.kennung}`", ort=eintrag.kennung)
        name, knoten = self._feldname(eintrag, zeile)
        stueck = Stueck(von, bis, "F", text, ("eintrag", eintrag.behaelter.schluessel, eintrag.pos),
                        mit=f"`{name}`: " if name else "", ort=eintrag.kennung)
        if name and einzeilig and _wiederholt_euro(name, knoten, text):
            stueck.weg = WEG_EURO
        return stueck

    def _feldname(self, eintrag: Eintrag, zeile: int) -> tuple[str, yaml.Node | None]:
        """Der Schluessel, hinter dessen Wert der Kommentar steht -- auch tief im Eintrag."""
        schluessel = self.g.schluesselpfad(zeile)
        if schluessel is not None and schluessel.zeile >= eintrag.start:
            return schluessel.name, schluessel.knoten
        feld = self.g.feld_bei(eintrag, zeile)
        return (feld.name, feld.knoten) if feld else ("", None)

    def _rolle(self, eintrag: Eintrag) -> tuple:
        """Das Ziel eines Budget-Kommentars: die Konto-Regel desselben Kontos, sonst der Bereich."""
        for bereich in self.g.bereiche:
            if bereich.schluessel == eintrag.behaelter.regeln:
                for e in bereich.eintraege:
                    if e.kennung == eintrag.kennung:
                        return ("eintrag", e.behaelter.schluessel, e.pos)
        return ("bereich",)

    def _ohne_lage(self, von: int, bis: int, text: str, schluessel: str) -> Stueck:
        return Stueck(von, bis, "–", text, ("bereich",),
                      hinweis=f"Zu `{schluessel}`" if schluessel else "", ort=schluessel)

    # -- Bloecke

    def _block(self, gruppe: list[Kommentar]) -> Stueck:
        von, bis = gruppe[0].zeile, gruppe[-1].zeile
        text = _block_text(gruppe)
        g = self.g
        p, n = g.vorher(von), g.nachher(bis)
        leer_danach = g.leer(bis + 1)
        strich = _strichlinie(gruppe[0].text)

        # N.2b: Ein Block, der unmittelbar unter einer Zeile haengt und nach unten nichts
        # hat, woran er haengen koennte, sagt etwas zu dem, was darueber steht.
        unter = not strich and von > 0 and not g.leer(von - 1) and p is not None
        if n is None:
            if p is None:
                return Stueck(von, bis, "K", text, ("bereich",))
            if unter:
                return self._unter(von, bis, text, p, gruppe[0].spalte)
            return Stueck(von, bis, "–", text, ("bereich",), hinweis="Am Ende der Datei")
        if p is None:
            if leer_danach:
                return Stueck(von, bis, "K", text, ("bereich",))
            if strich:
                return self._abschnitt(von, bis, text, n)
            return self._ueber(von, bis, text, n, kopf=True)
        e_p, e_n = g.eintrag_bei(p), g.eintrag_bei(n)
        if e_p is not None and e_p is e_n:
            return self._im_eintrag(e_n, von, bis, text, n)
        if unter and leer_danach:
            return self._unter(von, bis, text, p, gruppe[0].spalte)
        if strich or leer_danach:
            return self._abschnitt(von, bis, text, n)
        return self._ueber(von, bis, text, n)

    def _name_bei(self, zeile: int) -> str:
        """Wovor ein Abschnitt stand: der Eintrag, sonst der Schluessel."""
        eintrag = self.g.eintrag_bei(zeile)
        if eintrag is not None:
            return eintrag.kennung
        pfad = self.g.schluesselpfad(zeile)
        return pfad.pfad if pfad else ""

    def _abschnitt(self, von: int, bis: int, text: str, n: int) -> Stueck:
        name = self._name_bei(n)
        return Stueck(von, bis, "A", text, ("bereich",),
                      hinweis=f"Stand vor `{name}`" if name else "", ort=name)

    def _unter(self, von: int, bis: int, text: str, p: int, spalte: int) -> Stueck:
        """Ein Block ohne Leerzeile davor, dem nichts folgt, woran er haengt (N.2b).

        In der Spalte der Felder des Eintrags darueber gehoert er in dessen Notiz. Steht er
        tiefer oder flacher, oder steht darueber kein Eintrag, ist er ein Abschnitt, der
        sagt, wonach er stand. Ein Block mit Leerzeile davor kommt nie hierher.
        """
        eintrag = self.g.eintrag_bei(p)
        if eintrag is not None and eintrag.spalte == spalte:
            return self._im_eintrag(eintrag, von, bis, text, eintrag.start)
        name = self._name_bei(p)
        return Stueck(von, bis, "A", text, ("bereich",),
                      hinweis=f"Stand nach `{name}`" if name else "", ort=name)

    def _im_eintrag(self, eintrag: Eintrag, von: int, bis: int, text: str, n: int) -> Stueck:
        if eintrag.behaelter.form == BUDGETS:
            return Stueck(von, bis, "E", text, self._rolle(eintrag), mit="Budget: ",
                          hinweis=f"Budget von `{eintrag.kennung}`", ort=eintrag.kennung)
        feld = self.g.feld_bei(eintrag, n)
        blatt = feld is not None and any(feld is b for b in eintrag.blaetter)
        return Stueck(von, bis, "E", text, ("eintrag", eintrag.behaelter.schluessel, eintrag.pos),
                      mit=f"`{feld.name}`: " if blatt else "", ort=eintrag.kennung)

    def _ueber(self, von: int, bis: int, text: str, n: int, *, kopf: bool = False) -> Stueck:
        """Ein Block direkt ueber der Zeile `n`, ohne Leerzeile: er gehoert zu ihr."""
        g = self.g
        eintrag = g.eintrag_bei(n)
        if eintrag is not None:
            return self._im_eintrag(eintrag, von, bis, text, n)
        bereich = g.bereich_bei(n)
        if bereich is not None and bereich.behaelter is not None:
            # Ueber dem Schluessel der Eintragsliste selbst: der Kopf der Datei, wenn nichts
            # davor steht -- sonst eine Zuordnung, deren Kommentar dem Bereich gehoert.
            if kopf:
                return Stueck(von, bis, "K", text, ("bereich",))
            return self._ohne_lage(von, bis, text, bereich.schluessel)
        pfad = g.schluesselpfad(n)
        if self.datei.einstellungen and pfad is not None:
            return Stueck(von, bis, "S", text, ("einstellung", pfad.pfad), ort=pfad.pfad)
        return self._ohne_lage(von, bis, text, bereich.schluessel if bereich else "")

    # -- Koepfe der App

    def _koepfe_der_app(self, stuecke: list[Stueck]) -> None:
        """Der Kopf, den die App selbst schrieb, faellt weg -- nur wenn er wortlich stimmt."""
        kopf = [s for s in stuecke if s.lage == "K" and not s.weg]
        if not kopf:
            return
        alle = tuple(z for s in kopf for z in kopf_zeilen(s.text))
        if ist_kopf_der_app(self.name, alle):
            for s in kopf:
                s.weg = WEG_KOPF
        elif ist_kopf_der_app(self.name, kopf_zeilen(kopf[0].text)):
            kopf[0].weg = WEG_KOPF


def _wiederholt_euro(feldname: str, knoten: yaml.Node, kommentar: str) -> bool:
    """Sagt der Kommentar nur, was der Wert in Euro ist?

    Sicher erkannt, wenn alle vier gelten: Das Feld heisst `cents` oder endet auf `_cents`
    und hat eine ganze Zahl; der Kommentar ist nichts als eine Zahl in deutscher
    Schreibweise, hoechstens mit `€`, `EUR` oder `Euro`; Zahl mal 100 ist der Wert; er
    steht in einer Zeile (die Lage prueft der Aufrufer).
    """
    if feldname != "cents" and not feldname.endswith("_cents"):
        return False
    if not isinstance(knoten, yaml.ScalarNode) or knoten.tag != "tag:yaml.org,2002:int":
        return False
    zahl = kommentar.strip()
    if not _EURO.match(zahl):
        return False
    rein = re.sub(r"\s*(?:€|EUR|Euro)$", "", zahl).replace(".", "").replace(",", ".")
    try:
        euro = Decimal(rein)
        wert = int(yaml.safe_load(knoten.value))
    except (InvalidOperation, ValueError, TypeError):
        return False
    return euro * 100 == wert


def einordnen(name: str, text: str, datei: Datei) -> list[Stueck]:
    """Alle Kommentare der Datei als Stuecke, in der Reihenfolge der Datei."""
    return Ordner(name, text, datei).stuecke()


def wert(daten: Any, eintrag: Eintrag) -> Any:
    """Der Eintrag in den geladenen Daten."""
    behaelter = daten.get(eintrag.behaelter.schluessel)
    if isinstance(behaelter, list):
        return behaelter[eintrag.pos] if eintrag.pos < len(behaelter) else None
    if isinstance(behaelter, dict):
        schluessel = list(behaelter)
        return behaelter[schluessel[eintrag.pos]] if eintrag.pos < len(schluessel) else None
    return None
