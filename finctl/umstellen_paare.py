"""Basisdatei und Seitendatei zu einer Datei zusammenlegen -- fuer `finctl umstellen`.

Schritt 5, N.3 (`docs/schritt5_notizen.md`). Bis hierhin hatte jede Sache zwei Dateien: die
Basisdatei von Hand und eine `_custom`-Datei, die die Oberflaeche schrieb und die beim
Lesen gewann. Danach gibt es eine Datei je Sache, und die Oberflaeche darf sie ganz
schreiben (Entscheidung 5). Hier steht, wie ein Paar zusammengelegt wird.

Das Zusammenlegen ist ein Schritt hinter dem Umwandeln der Kommentare: Beide Dateien
liegen schon in Notizform vor, wenn sie hier ankommen (`umstellen.planen`).

WAS DAS ERGEBNIS TRAEGT, fuer jedes Paar:

* Es gilt genau, was vorher galt. `ALT_LESER` ist der Leser, wie er vor dem
  Zusammenlegen las; das Ergebnis wird mit dem neuen Leser gelesen, und beide muessen
  dieselben Werte liefern. Scheitert das, wird nichts geschrieben.
* Trafen zwei Notizen zusammen, steht die der Basis zuerst, dann die der Seite.
* Ein Wert der Basis, den die Seite ueberschrieben hatte, geht nicht verloren: Der alte
  Wert steht in der Notiz des Eintrags (N.0, Nummer 7).
* Was die alten Leser nie lasen (ein Feld, das es nicht gibt), wird nicht in die neue
  Datei uebernommen, aber im Bericht genannt. Die Sicherung haelt die alte Datei.

Die alten Leser leben nur hier. Sie duerfen aus den Modulen verschwinden, in denen sie
standen (N.4).
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from finctl import notizen as _n

#: Der Text, mit dem eine Notiz einen ueberschriebenen Wert der Basis festhaelt.
STAND_VORHER = "Bis zur Umstellung stand in der Datei"
#: Und der, wenn der Wert nicht in der Datei stand, sondern in den mitgelieferten Regeln.
STAND_MITGELIEFERT = "Bis zur Umstellung stand in den mitgelieferten Regeln"

#: Die Namen einer Notiz in einer Zeile fuer eine Seite; die Pruefung vergleicht ohne sie.
_NOTIZ_NAMEN = (_n.NOTIZ, _n.VOM, "note")


@dataclass(slots=True)
class Zusammenlegung:
    """Was beim Zusammenlegen eines Paars geschah -- fuer den Bericht."""

    basis: str
    seite: str
    #: Der Text der neuen Basisdatei, oder `None`, wenn die Seite nichts anderes sagt.
    neu: str | None = None
    #: Orte, an denen die Seite einen Wert der Basis ueberschrieb; der alte Wert steht in
    #: einer Notiz. `(Ort, alter Wert)`.
    ueberschrieben: list[tuple[str, str]] = field(default_factory=list)
    #: Orte, an denen zwei Notizen zusammentrafen.
    notizen: list[str] = field(default_factory=list)
    #: Budgets, die aus der Seite kamen oder von ihr entfernt wurden.
    budgets: list[str] = field(default_factory=list)
    #: Was die Seitendatei brachte, mit der Art: Oberbegriffe, Blaetter, Konten.
    aus_seite: list[str] = field(default_factory=list)
    #: Felder der Seitendatei, die kein Leser je las; sie kommen nicht in die neue Datei.
    ungelesen: list[str] = field(default_factory=list)
    #: Eintraege der Basis, die die Seite mit `entfernt: true` ausgeblendet hatte. Sie stehen
    #: nicht in der neuen Datei, nur in der Sicherung.
    ausgeblendet: list[str] = field(default_factory=list)
    #: Eintraege, deren Kennung sich beim Zusammenlegen aendert, weil die Seite den Namen
    #: aenderte, aus dem sie sich ergibt: alte Kennung zu neuer.
    umbenannt: dict[str, str] = field(default_factory=dict)
    fehler: list[str] = field(default_factory=list)


Legen = Callable[[dict, dict, Zusammenlegung], dict]
Lesen = Callable[[dict], Any]


@dataclass(frozen=True, slots=True)
class Paar:
    """Eine Basisdatei und ihre Seitendatei, und wie beide zu einer werden."""

    basis: str
    seite: str
    legen: Legen
    #: Der Leser, wie er vor dem Zusammenlegen las: (Basis, Seite) -> Werte ohne Notizen.
    alt: Callable[[dict, dict], Any]
    #: Der Leser, der nur die eine Datei liest: Datei -> Werte ohne Notizen.
    neu: Lesen
    #: Die Schluessel oben in der Datei, unter denen Eintraege mit Notiz stehen.
    wurzeln: tuple[str, ...] = ()
    #: Der Schluessel der Seitendatei, unter dem sie Eintraege der ersten Wurzel aenderte, wenn
    #: er anders heisst als die Wurzel (`kredite` zu `loans`, `objekte` zu `properties`).
    #: Ein Tupel nennt ihn je Wurzel, in derselben Reihenfolge.
    seitenwurzel: str | tuple[str, ...] = ""
    #: Der Schluessel der Seitendatei, unter dem sie Eintraege der ersten Wurzel anlegte, die
    #: es in der Basisdatei nicht gab (`neu:` bei den Renten). Sie stehen danach in der Wurzel.
    angelegt: str = ""
    #: Wo die Basisdatei fehlt, gilt diese Datei der Startvorlagen (`finctl/vorgaben/`) als
    #: Basis, denn so liest es die App: `init` legt sie an, wenn sie fehlt.
    vorlage: str = ""
    #: Was ein Paar ueber die Datei hinaus wissen muss: wird mit dem Ordner `config/` gerufen
    #: (oder `None`) und kommt als `kontext` an `legen` und `alt`. Die Bestaende fragen so,
    #: welche Konten ihren Stand aus einem Auszug lesen.
    kontext: Callable[[Path | None], Any] | None = None
    #: Die Kennung eines Eintrags einer Wurzel, wo sie nicht das Feld `id` ist:
    #: (Wurzel, Eintrag) -> Kennung.
    kennung_von: Callable[[str, dict], str] | None = None
    #: Wo die Notiz eines Ortes der Seite (unter `notizen:`) nach dem Zusammenlegen steht, wenn
    #: die Datei die Angabe anders nennt (`person.geburtsdatum` zu `person.birth_date`).
    ort_neu: Callable[[str], str] | None = None
    #: Teilt eine Seitendatei sich auf zwei Basisdateien auf (`settings_custom.yaml` auf
    #: `assumptions.yaml` und `forecast.yaml`), sagt dieses Paar, was ihm von der Seite
    #: gehoert: Seite -> (die Sicht dieses Paars, was kein Leser kannte). Jede Notiz und jeder
    #: Wert der Seite gehoert in genau eine Sicht; legen, alt und die Pruefungen sehen nur ihre.
    ansicht: Callable[[dict], tuple[dict, list[str]]] | None = None


# ------------------------------------------------------------------ Notizen legen


def _wert(wert: Any) -> str:
    """Ein Wert als Text fuer eine Notiz: Skalare, wie sie in der Datei stuenden."""
    if isinstance(wert, (dict, list)):
        return yaml.safe_dump(wert, default_flow_style=True, allow_unicode=True,
                              width=1000).strip()
    return "" if wert is None else str(wert)


def _stand_vorher(posten: list[tuple[str, Any]], wo: str = STAND_VORHER) -> str:
    """Der Satz, der festhaelt, was bis zur Umstellung in der Basisdatei stand."""
    return f"{wo}: " + "; ".join(f"{ort}: {_wert(w)}" for ort, w in posten) + "."


def _notizen_legen(basis: dict, seite: Mapping | None, ort: str, bericht: Zusammenlegung,
                   danach: list[str] | None = None) -> None:
    """Die Notiz in `basis` ist danach die beider Eintraege: Basis zuerst, dann die Seite.

    Das Datum ist das spaetere der beiden, denn der Text enthaelt auch den juengeren. Fehlt
    es beiden, fehlt es. `danach` sind Saetze, die der Umwandler selbst anfuegt.
    """
    n_basis = _n.lesen(basis)
    n_seite = _n.lesen(seite)
    texte = [n_basis.text]
    if n_seite.text and n_seite.text != n_basis.text:
        texte.append(n_seite.text)
        if n_basis.text:
            bericht.notizen.append(ort)
    texte += danach or []
    texte = [t for t in texte if t]
    if not texte:
        return
    daten = [d for d in (n_basis.vom if n_basis.text else "",
                         n_seite.vom if n_seite.text else "") if d]
    neu = _n.Notiz("\n\n".join(texte), max(daten) if daten else "")
    for name in (_n.NOTIZ, _n.VOM):
        basis.pop(name, None)
    basis.update(neu.als_dict())


def _bereiche_legen(neu: dict, seite: Mapping, bericht: Zusammenlegung,
                    zusatz: dict[str, list[str]] | None = None) -> None:
    """Die Bloecke `notizen:` beider Dateien. `zusatz` sind Saetze fuer die Notiz des Bereichs."""
    zusatz = zusatz or {}
    block = seite.get(_n.BEREICHE)
    block = block if isinstance(block, Mapping) else {}
    orte = [*block, *(o for o in zusatz if o not in block)]
    if not orte:
        return
    ziel = neu.get(_n.BEREICHE)
    ziel = dict(ziel) if isinstance(ziel, Mapping) else {}
    for ort in orte:
        stelle = dict(ziel.get(ort) or {})
        eintrag = block.get(ort)
        _notizen_legen(stelle, eintrag if isinstance(eintrag, Mapping) else None,
                       f"{_n.BEREICHE}.{ort}", bericht, zusatz.get(ort))
        if stelle:
            ziel[ort] = stelle
    if ziel:
        neu[_n.BEREICHE] = ziel


# ------------------------------------------------------------ forecast <-> forecast_custom


def _feld_namen() -> tuple[str, ...]:
    """Die Felder einer Kontenregel, die der alte Leser aus der Seite nahm -- ohne die Notiz."""
    from finctl import kontenregeln

    return tuple(f for f in kontenregeln.FELDER if f != "note")


def _ohne_notiz(zeile: Any) -> Any:
    if not isinstance(zeile, dict):
        return zeile
    return {k: v for k, v in zeile.items() if k not in _NOTIZ_NAMEN}


def _rollen_legen(neu: dict, seite: dict, bericht: Zusammenlegung) -> dict:
    """Die Konto-Regeln: Konto fuer Konto, Feld fuer Feld ersetzt die Seite, was sie nennt."""
    from finctl import kontenregeln

    felder = _feld_namen()
    rollen = dict(neu.get("account_roles") or {})
    for konto, s_rolle in _n.ohne(seite.get("account_roles")).items():
        s_rolle = s_rolle if isinstance(s_rolle, dict) else {}
        rolle = dict(rollen.get(konto) or {})
        alt: list[tuple[str, Any]] = []
        for feld in felder:
            if feld not in s_rolle:
                continue
            if feld in rolle and rolle[feld] != s_rolle[feld]:
                alt.append((f"`{feld}`", rolle[feld]))
                bericht.ueberschrieben.append((f"{konto}.{feld}", _wert(rolle[feld])))
            rolle[feld] = s_rolle[feld]
        bericht.ungelesen += [f"account_roles.{konto}.{feld}" for feld in s_rolle
                              if feld not in kontenregeln.FELDER and feld not in _NOTIZ_NAMEN]
        if konto not in rollen:
            bericht.aus_seite.append(f"account_roles.{konto} (Konto, neu)")
        _notizen_legen(rolle, s_rolle, konto, bericht, [_stand_vorher(alt)] if alt else None)
        rollen[konto] = rolle
    return rollen


def _budgets_legen(neu: dict, seite: dict, bericht: Zusammenlegung) -> tuple[dict, dict]:
    """Das Budget je Konto: die Seite ersetzt, ein leeres entfernt es.

    Gibt die Budgets zurueck und je Konto, dessen Budget die Seite aenderte, den Satz fuer
    die Notiz.
    """
    budgets = dict(neu.get("account_budgets") or {})
    hinweise: dict[str, str] = {}
    for konto, cents in _n.ohne(seite.get("account_budgets")).items():
        wert = None if cents in (None, "") else int(cents)
        if konto in budgets and budgets[konto] != wert:
            entfernt = "; die Seite hatte es entfernt" if wert is None else ""
            hinweise[konto] = f"Budget: {STAND_VORHER}: {_wert(budgets[konto])}{entfernt}."
            bericht.ueberschrieben.append((f"{konto}.budget", _wert(budgets[konto])))
        if wert is None:
            budgets.pop(konto, None)
        else:
            budgets[konto] = wert
        bericht.budgets.append(konto)
    return budgets, hinweise


def _forecast_legen(basis: dict, seite: dict, bericht: Zusammenlegung) -> dict:
    """Konto-Regeln und Budgets; die Notiz zum Budget geht in die Notiz der Konto-Regel."""
    neu = copy.deepcopy(basis)
    rollen = _rollen_legen(neu, seite, bericht)
    budgets, hinweise = _budgets_legen(neu, seite, bericht)
    zusatz: dict[str, list[str]] = {}
    for konto, satz in hinweise.items():
        if isinstance(rollen.get(konto), dict) and rollen[konto]:
            _notizen_legen(rollen[konto], None, konto, bericht, [satz])
        else:
            # Ein Konto nur mit Budget hat keine Regel, an der eine Notiz stehen koennte.
            zusatz.setdefault(_n.BEREICH, []).append(f"Zu `account_budgets.{konto}`: {satz}")
    if rollen or "account_roles" in neu:
        neu["account_roles"] = rollen
    if budgets or "account_budgets" in neu:
        neu["account_budgets"] = budgets
    _bereiche_legen(neu, seite, bericht, zusatz)
    return neu


def _forecast_alt(basis: dict, seite: dict) -> dict:
    """`kontenregeln.zusammenfuehren`, wie es vor dem Zusammenlegen las, ohne Notizen."""
    felder = _feld_namen()
    rollen = {k: dict(v or {}) for k, v in _n.ohne(basis.get("account_roles")).items()}
    for konto, s_rolle in _n.ohne(seite.get("account_roles")).items():
        rolle = rollen.setdefault(konto, {})
        rolle.update({k: v for k, v in (s_rolle or {}).items() if k in felder})
    budgets = dict(_n.ohne(basis.get("account_budgets")))
    for konto, cents in _n.ohne(seite.get("account_budgets")).items():
        if cents in (None, ""):
            budgets.pop(konto, None)
        else:
            budgets[konto] = int(cents)
    rest = {k: v for k, v in basis.items() if k not in (_n.BEREICHE, "account_roles",
                                                        "account_budgets")}
    return {**rest, "account_roles": {k: _ohne_notiz(v) for k, v in rollen.items()},
            "account_budgets": budgets}


def _forecast_neu(spec: dict) -> dict:
    from finctl import kontenregeln

    gelesen = kontenregeln.aus_spec(spec)
    rest = {k: v for k, v in gelesen.items() if k not in (_n.BEREICHE, "account_roles",
                                                          "account_budgets")}
    return {**rest, "account_roles": {k: _ohne_notiz(v)
                                      for k, v in gelesen["account_roles"].items()},
            "account_budgets": gelesen["account_budgets"]}


# --------------------------------------------------------- taxonomy <-> taxonomy_custom

ACHSEN = ("management", "tax")


def _taxonomie_legen(basis: dict, seite: dict, bericht: Zusammenlegung) -> dict:
    """Je Blatt: das Blatt der Seite ersetzt das der Basis; der Name des Oberbegriffs ebenso.

    Ein Oberbegriff, den es in der Basis nicht gibt, bringt Name, Art und Blaetter mit;
    seine uebrigen Merkmale las der alte Leser nie.
    """
    neu = copy.deepcopy(basis)
    for achse in ACHSEN:
        for ober, s_knoten in (seite.get(achse) or {}).items():
            s_knoten = s_knoten if isinstance(s_knoten, dict) else {}
            ort = f"{achse}.{ober}"
            baum = neu.setdefault(achse, {})
            alt: list[tuple[str, Any]] = []
            if ober not in baum:
                baum[ober] = {"name": s_knoten.get("name", ober),
                              "kind": s_knoten.get("kind", "expense"), "children": {}}
                bericht.aus_seite.append(f"{ort} (Oberbegriff, neu)")
                gelesen = {"name", "kind", "children"}
            else:
                bericht.aus_seite.append(f"{ort} (Oberbegriff, schon in der Basis)")
                gelesen = {"name", "children"}
            knoten = baum[ober]
            if s_knoten.get("name"):
                if knoten.get("name") != s_knoten["name"]:
                    alt.append(("`name`", knoten.get("name")))
                    bericht.ueberschrieben.append((f"{ort}.name", _wert(knoten.get("name"))))
                knoten["name"] = s_knoten["name"]
            bericht.ungelesen += [f"{ort}.{feld}" for feld in s_knoten
                                  if feld not in gelesen and feld not in _NOTIZ_NAMEN]
            blaetter = knoten.get("children")
            if not isinstance(blaetter, dict):
                blaetter = knoten["children"] = {}
            for blatt, wert in _n.ohne(s_knoten.get("children")).items():
                if blatt in blaetter and blaetter[blatt] != wert:
                    alt.append((f"Blatt `{blatt}`", blaetter[blatt]))
                    bericht.ueberschrieben.append((f"{ort}/{blatt}", _wert(blaetter[blatt])))
                    bericht.aus_seite.append(f"{ort}/{blatt} (Blatt, ersetzt)")
                elif blatt not in blaetter:
                    bericht.aus_seite.append(f"{ort}/{blatt} (Blatt, neu)")
                else:
                    bericht.aus_seite.append(f"{ort}/{blatt} (Blatt, gleich der Basis)")
                blaetter[blatt] = wert
            _notizen_legen(knoten, s_knoten, ort, bericht, [_stand_vorher(alt)] if alt else None)
    _bereiche_legen(neu, seite, bericht)
    return neu


def _taxonomie_ohne_notizen(spec: dict) -> dict:
    """Die Taxonomie ohne Notizen: an den Oberbegriffen und in den Blaettern."""
    kopie = {k: v for k, v in copy.deepcopy(spec).items() if k != _n.BEREICHE}
    for achse in ACHSEN:
        for knoten in (kopie.get(achse) or {}).values():
            if isinstance(knoten, dict):
                for name in _NOTIZ_NAMEN:
                    knoten.pop(name, None)
                if isinstance(knoten.get("children"), dict):
                    knoten["children"] = _n.ohne(knoten["children"])
    return kopie


def _taxonomie_alt(basis: dict, seite: dict) -> dict:
    """`tax.taxonomy.load_spec`, wie es vor dem Zusammenlegen las, ohne Notizen."""
    spec = copy.deepcopy(basis)
    for achse in ACHSEN:
        for ober, knoten in (seite.get(achse) or {}).items():
            knoten = knoten if isinstance(knoten, dict) else {}
            ziel = spec.setdefault(achse, {}).setdefault(
                ober, {"name": knoten.get("name", ober), "kind": knoten.get("kind", "expense"),
                       "children": {}})
            if knoten.get("name"):
                ziel["name"] = knoten["name"]
            ziel.setdefault("children", {}).update(knoten.get("children") or {})
    return _taxonomie_ohne_notizen(spec)


def _taxonomie_neu(spec: dict) -> dict:
    from finctl.tax import taxonomy

    return _taxonomie_ohne_notizen(taxonomy.aus_spec(spec))


# ----------------------------------------------------- Eintraege nach Kennung


def _je_kennung(wert: Any) -> dict[str, Any]:
    """Die Eintraege eines Behaelters nach Kennung: eine Liste mit `id` oder eine Zuordnung."""
    if isinstance(wert, list):
        return {str(e["id"]): e for e in wert if isinstance(e, dict) and e.get("id")}
    if isinstance(wert, Mapping):
        return {str(k): v for k, v in _n.ohne(wert).items()}
    return {}


def _leer(wert: Any) -> bool:
    """Sagt der Wert nichts: kein Wert, ein leerer Text, eine leere Liste, nur Leeres darin?"""
    if isinstance(wert, Mapping):
        return all(_leer(v) for v in wert.values())
    return wert is None or wert == "" or wert == []


def _gleich(a: Any, b: Any) -> bool:
    """Derselbe Wert, auch wenn einer als Datum und einer als Text in der Datei steht."""
    return a == b or str(a) == str(b)


def _liste(spec: dict, schluessel: str) -> list:
    liste = spec.get(schluessel)
    if liste is None:
        return []
    if not isinstance(liste, list):
        raise TypeError(f"`{schluessel}` ist keine Liste")
    return liste


# ------------------------------------------------------------- renten <-> renten_custom

#: Was der alte Leser aus der Seite nahm (`renten.quellen` bis N.3b): `renten.<id>`, Feld fuer
#: Feld. Alles andere an einem Eintrag der Seite las er nie.
_RENTEN_FELDER = ("cents", "ab", "stand", "kosten_pa", "beitrag", "pruefwert",
                  "stand_cents", "stand_wert", "beitrag_ag_cents")


def _datum(wert: Any) -> str | None:
    """Ein Datum als JJJJ-MM-TT: wie der alte Leser `JJJJ-MM` zum Ersten des Monats machte."""
    if not wert:
        return None
    if isinstance(wert, date):
        return wert.isoformat()
    text = str(wert)
    return date.fromisoformat(text + "-01" if len(text) == 7 else text[:10]).isoformat()


def _zahl(wert: Any) -> float | None:
    return None if wert in (None, "") else float(wert)


def _ganz(wert: Any) -> int | None:
    return None if wert in (None, "") else int(wert)


def _renten_werte(d: Mapping) -> dict:
    """Was eine Rentenquelle wirksam sagt, in einer Form, in der sich zwei Leser vergleichen."""
    pruef = d.get("pruefwert")
    return {
        "id": str(d["id"]), "name": str(d.get("name") or d["id"]),
        "art": str(d.get("art") or "rente"), "kaufkraft": str(d.get("kaufkraft") or "heute"),
        "cents": int(d.get("cents") or 0), "ab": _datum(d.get("ab")),
        "konto": d.get("konto") or None, "stand": _datum(d.get("stand")),
        "kosten_pa": _zahl(d.get("kosten_pa")),
        "beitrag": str(d.get("beitrag") or "").strip() or None,
        "pruefwert": None if not pruef else {
            "satz": _zahl(pruef.get("satz")), "cents": int(pruef["cents"]),
            "zum": _datum(pruef["zum"])},
        "stand_cents": _ganz(d.get("stand_cents")), "stand_wert": _datum(d.get("stand_wert")),
        "beitrag_ag_cents": _ganz(d.get("beitrag_ag_cents")),
    }


#: Die Reihenfolge der Felder einer Quelle, wie sie in der Datei von Hand stehen.
_RENTEN_REIHE = ("id", "name", "art", "kaufkraft", "cents", "ab", "konto", "stand", "kosten_pa",
                 "beitrag", "pruefwert", "stand_cents", "stand_wert", "beitrag_ag_cents")


def _in_reihe(eintrag: dict) -> dict:
    """Die Felder einer in der Seite angelegten Quelle in der Reihenfolge der Datei."""
    return {**{k: eintrag[k] for k in _RENTEN_REIHE if k in eintrag},
            **{k: v for k, v in eintrag.items() if k not in _RENTEN_REIHE}}


def _renten_legen(basis: dict, seite: dict, bericht: Zusammenlegung) -> dict:
    """Die Seite ersetzt je Quelle Feld fuer Feld; `neu:` sind danach Quellen wie die anderen.

    Die Notiz der Basis steht zuerst, die der Seite dahinter, und ein Wert der Basis, den die
    Seite ueberschrieb, steht am Ende der Notiz.
    """
    neu = copy.deepcopy(basis)
    liste = _liste(neu, "renten")
    vorhanden = set(_je_kennung(liste))
    angelegt: set[str] = set()
    for eintrag in seite.get("neu") or []:
        if not isinstance(eintrag, dict) or not eintrag.get("id"):
            bericht.ungelesen.append("neu (ein Eintrag ohne Kennung)")
            continue
        kennung = str(eintrag["id"])
        if kennung in vorhanden:
            raise ValueError(f"neu.{kennung}: die Kennung steht schon in {bericht.basis}")
        liste.append(copy.deepcopy(eintrag))
        vorhanden.add(kennung)
        angelegt.add(kennung)
        bericht.aus_seite.append(f"{kennung} (Quelle, in der Seite angelegt)")
    eigen = _je_kennung(seite.get("renten"))
    for kennung, eintrag in _je_kennung(liste).items():
        u = eigen.get(kennung)
        if u is None:
            continue
        u = u if isinstance(u, dict) else {}
        alt: list[tuple[str, Any]] = []
        for feld in _RENTEN_FELDER:
            if feld not in u:
                continue
            if not _leer(eintrag.get(feld)) and not _gleich(eintrag[feld], u[feld]):
                alt.append((f"`{feld}`", eintrag[feld]))
                bericht.ueberschrieben.append((f"{kennung}.{feld}", _wert(eintrag[feld])))
            eintrag[feld] = u[feld]
        bericht.ungelesen += [f"renten.{kennung}.{feld}" for feld in u
                              if feld not in _RENTEN_FELDER and feld not in _NOTIZ_NAMEN]
        _notizen_legen(eintrag, u, kennung, bericht, [_stand_vorher(alt)] if alt else None)
    liste[:] = [_in_reihe(e) if str(e.get("id")) in angelegt else e for e in liste]
    # Ein Eintrag der Seite ohne Quelle las der alte Leser nie. Seine Notiz geht nicht verloren.
    ohne_quelle = [k for k in eigen if k not in vorhanden]
    bericht.ungelesen += [f"renten.{k} (keine Quelle dazu)" for k in ohne_quelle]
    zusatz = [f"Zu `renten.{k}` (keine Quelle dazu): {_n.lesen(eigen[k]).text}"
              for k in ohne_quelle if _n.lesen(eigen[k]).text]
    neu["renten"] = liste
    _bereiche_legen(neu, seite, bericht, {_n.BEREICH: zusatz})
    return neu


def _renten_alt(basis: dict, seite: dict) -> list[dict]:
    """`renten.quellen`, wie es vor dem Zusammenlegen las, ohne Notizen."""
    eigen = _je_kennung(seite.get("renten"))
    aus = []
    for roh in [*(basis.get("renten") or []), *(seite.get("neu") or [])]:
        if not isinstance(roh, dict) or not roh.get("id"):
            continue
        ueber = eigen.get(str(roh["id"])) or {}
        aus.append(_renten_werte({**roh, **{f: ueber.get(f, roh.get(f)) for f in _RENTEN_FELDER}}))
    return aus


def _renten_neu(spec: dict) -> list[dict]:
    from finctl import renten

    return [_renten_werte({
        "id": q.id, "name": q.name, "art": q.art, "kaufkraft": q.kaufkraft, "cents": q.cents,
        "ab": q.ab, "konto": q.konto, "stand": q.stand, "kosten_pa": q.kosten_pa,
        "beitrag": q.beitrag,
        "pruefwert": None if q.pruefwert is None else {
            "satz": q.pruefwert.satz, "cents": q.pruefwert.cents, "zum": q.pruefwert.zum},
        "stand_cents": q.stand_cents, "stand_wert": q.stand_wert,
        "beitrag_ag_cents": q.beitrag_ag_cents}) for q in renten.aus_spec(spec)]


# ------------------------------------------- abos / versicherungen <-> ihre Seitendateien

#: Was der alte Leser aus der Seite nahm: jedes Feld, das `abos.normalisieren` kennt, dazu
#: `entfernt`. Alles andere las er nie.
_VERTRAG_FELDER = ("name", "kategorie", "konto", "betrag", "betrag_cents", "takt", "faellig",
                   "vorrat_bis", "gekuendigt_zum", "weg", "buchungen", "ignoriert", "geteilt")


def _vertraege_legen(schluessel: str):
    def legen(basis: dict, seite: dict, bericht: Zusammenlegung) -> dict:
        """Die Seite ersetzt je Kennung Feld fuer Feld; `entfernt: true` nimmt den Eintrag heraus.

        Ein Eintrag, den es nur in der Seite gab, steht danach hinter denen der Basis. Ein
        ausgeblendeter Eintrag steht in der Sicherung, nicht in der neuen Datei.
        """
        neu = copy.deepcopy(basis)
        liste = _liste(neu, schluessel)
        eigen = _je_kennung(seite.get(schluessel))
        gesehen = set(_je_kennung(liste))
        for kennung, u in eigen.items():
            if kennung in gesehen:
                continue
            if isinstance(u, dict) and u.get("entfernt"):
                bericht.ausgeblendet.append(kennung)
                continue
            liste.append({"id": kennung})
            bericht.aus_seite.append(f"{kennung} (Vertrag, in der Seite angelegt)")
        behalten = []
        zusatz: list[str] = []
        for eintrag in liste:
            if isinstance(eintrag, dict) and eintrag.get("id"):
                _vertrag_ueberschreiben(eintrag, eigen.get(str(eintrag["id"])), bericht)
                if eintrag.pop("entfernt", None):
                    bericht.ausgeblendet.append(str(eintrag["id"]))
                    zusatz.append(_ausgeblendet_satz(eintrag))
                    continue
            behalten.append(eintrag)
        neu[schluessel] = behalten
        _bereiche_legen(neu, seite, bericht, {_n.BEREICH: [s for s in zusatz if s]})
        return neu

    return legen


def _ausgeblendet_satz(eintrag: dict) -> str:
    """Die Begruendung eines ausgeblendeten Vertrags geht in die Notiz des Bereichs."""
    notiz = _n.lesen(eintrag).text
    if not notiz:
        return ""
    benannt = eintrag.get("name") or eintrag.get("display_name")
    name = f" ({benannt})" if benannt else ""
    return f"Ausgeblendet bis zur Umstellung: `{eintrag['id']}`{name}. {notiz}"


def _vertrag_ueberschreiben(eintrag: dict, u: Any, bericht: Zusammenlegung) -> None:
    """Die Felder der Seite in den Eintrag, und was sie von der Basis ersetzten, in die Notiz."""
    if u is None:
        return
    from finctl import abos

    u = u if isinstance(u, dict) else {}
    kennung = str(eintrag["id"])
    alt: list[tuple[str, Any]] = []
    if "entfernt" in u:
        eintrag["entfernt"] = u["entfernt"]
    for feld in _VERTRAG_FELDER:
        if feld not in u or (feld == "betrag_cents" and u[feld] is None):
            continue
        vorher = eintrag.get(feld)
        if feld == "betrag_cents" and "betrag" in eintrag:
            # Der Betrag stand in der Basis als Euro, die Seite schrieb Cent: derselbe Wert.
            betrag = eintrag.pop("betrag")
            vorher = None if _leer(betrag) else abos._cents(betrag)
        if not _leer(vorher) and not _gleich(vorher, u[feld]):
            alt.append((f"`{feld}`", vorher))
            bericht.ueberschrieben.append((f"{kennung}.{feld}", _wert(vorher)))
        if _leer(u[feld]):
            eintrag.pop(feld, None)
        else:
            eintrag[feld] = u[feld]
    bericht.ungelesen += [f"{kennung}.{feld}" for feld in u
                          if feld not in (*_VERTRAG_FELDER, "entfernt")
                          and feld not in _NOTIZ_NAMEN]
    _notizen_legen(eintrag, u, kennung, bericht, [_stand_vorher(alt)] if alt else None)


def _vertraege_alt(schluessel: str):
    def alt(basis: dict, seite: dict) -> list[dict]:
        """`abos.laden`, wie es vor dem Zusammenlegen las, ohne Notizen und ohne Herkunft."""
        from finctl import abos

        grund = _je_kennung(basis.get(schluessel))
        eigen = _je_kennung(seite.get(schluessel))
        aus = []
        for kennung in [*grund, *(k for k in eigen if k not in grund)]:
            roh = {**(grund.get(kennung) or {}), **(eigen.get(kennung) or {}), "id": kennung}
            if roh.get("entfernt"):
                continue
            for name in (*_NOTIZ_NAMEN, "warum"):
                roh.pop(name, None)
            aus.append({k: v for k, v in abos.normalisieren(roh).items() if k != "notiz"})
        return aus

    return alt


def _vertraege_neu(art: str):
    def neu(spec: dict) -> list[dict]:
        from finctl import abos

        return [{k: v for k, v in a.items() if k not in ("notiz", "art")}
                for a in abos.aus_spec(spec, art)]

    return neu


# --------------------------------------------------------- loans <-> loans_custom

#: Was die Seite `/kredite` an einem Kredit ablegte, und wo es danach steht. `vorlagen.<id>`
#: ersetzte die Grundkonditionen eines Kredits an einer Klammer: Es steht danach am Kredit
#: unter `vorlage`, und `lade_kredite` wendet es an wie vorher. `anschluss.<id>` las nur die
#: Seite (und die Fristen), nie die Prognose: Es steht unter `anschluss_eingegeben`, nicht
#: unter `anschluss`, das die Prognose liest.
_KREDIT_VORLAGE = "vorlage"
_KREDIT_ANSCHLUSS = "anschluss_eingegeben"

#: Die Schluessel der Seitendatei, die der alte Leser kannte.
_KREDIT_SEITE = ("kredite", "vorlagen", "anschluss", _n.BEREICHE)


def _ueberschreiben(eintrag: dict, u: Any, bericht: Zusammenlegung, kennung: str, *,
                    angelegt: bool = False, vorab: list[tuple[str, Any]] | None = None,
                    wo: str = STAND_VORHER) -> None:
    """Die Felder der Seite in den Eintrag, und was sie ersetzten, in seine Notiz.

    Feld fuer Feld, wie der alte Leser `{**basis, **seite}` las. Ein Feld, das es in der Basis
    nicht gab, steht danach da und im Bericht (nicht bei einem Eintrag, den es nur in der Seite
    gab: dort ist alles neu); die Notiz der Seite kommt hinter die der Basis. `vorab` sind
    ersetzte Werte, die der Aufrufer schon fand.
    """
    if not isinstance(u, dict):
        return
    alt: list[tuple[str, Any]] = list(vorab or [])
    for feld, wert in u.items():
        if feld in (_n.NOTIZ, _n.VOM, "entfernt", "id"):
            continue
        if feld not in eintrag:
            if not angelegt:
                bericht.aus_seite.append(f"{kennung}.{feld} (Feld, nur in der Seite)")
        elif not _leer(eintrag[feld]) and not _gleich(eintrag[feld], wert):
            alt.append((f"`{feld}`", eintrag[feld]))
            bericht.ueberschrieben.append((f"{kennung}.{feld}", _wert(eintrag[feld])))
        eintrag[feld] = wert
    _notizen_legen(eintrag, u, kennung, bericht, [_stand_vorher(alt, wo)] if alt else None)


def _ausgeblendet(eintrag: dict, bericht: Zusammenlegung, zusatz: list[str]) -> None:
    """Ein mit `entfernt: true` ausgeblendeter Eintrag steht nicht mehr da; seine Notiz schon."""
    bericht.ausgeblendet.append(str(eintrag["id"]))
    satz = _ausgeblendet_satz(eintrag)
    if satz:
        zusatz.append(satz)


def _kredite_legen(basis: dict, seite: dict, bericht: Zusammenlegung) -> dict:
    """Die Seite ersetzt je Kredit Feld fuer Feld; Vorlage und Anschluss gehen an den Kredit.

    Ein Kredit nur in der Seite steht danach hinter denen der Basis, ein ausgeblendeter
    steht in der Sicherung und mit seiner Notiz beim Bereich. Eine Vorlage gilt nur fuer
    einen Kredit der Basis (wie der alte Leser sie las).
    """
    neu = copy.deepcopy(basis)
    liste = _liste(neu, "loans")
    eigen = _je_kennung(seite.get("kredite"))
    vorlagen = _je_kennung(seite.get("vorlagen"))
    anschluss = _je_kennung(seite.get("anschluss"))
    behalten: list = []
    zusatz: list[str] = []
    aus_basis: set[str] = set()
    for kredit in liste:
        if not (isinstance(kredit, dict) and kredit.get("id")):
            behalten.append(kredit)
            continue
        kennung = str(kredit["id"])
        u = eigen.pop(kennung, None)
        _ueberschreiben(kredit, u, bericht, kennung)
        if isinstance(u, dict) and u.get("entfernt"):
            _ausgeblendet(kredit, bericht, zusatz)
            continue
        aus_basis.add(kennung)
        behalten.append(kredit)
    for kennung, u in eigen.items():
        kredit = {"id": kennung}
        _ueberschreiben(kredit, u, bericht, kennung, angelegt=True)
        if isinstance(u, dict) and u.get("entfernt"):
            _ausgeblendet(kredit, bericht, zusatz)
            continue
        bericht.aus_seite.append(f"{kennung} (Kredit, in der Seite angelegt)")
        behalten.append(kredit)
    angelegt = {str(k["id"]) for k in behalten if isinstance(k, dict) and k.get("id")}
    for kredit in behalten:
        kennung = str(kredit["id"]) if isinstance(kredit, dict) and kredit.get("id") else ""
        if kennung in aus_basis and vorlagen.get(kennung):
            kredit[_KREDIT_VORLAGE] = vorlagen[kennung]
            bericht.aus_seite.append(f"{kennung} (Vorlage, jetzt am Kredit)")
        if kennung in angelegt and anschluss.get(kennung):
            kredit[_KREDIT_ANSCHLUSS] = anschluss[kennung]
            bericht.aus_seite.append(f"{kennung} (Anschlusskondition, jetzt am Kredit)")
    bericht.ungelesen += [f"vorlagen.{k} (kein Kredit der Basis dazu)" for k, v in vorlagen.items()
                          if v and k not in aus_basis]
    bericht.ungelesen += [f"anschluss.{k} (kein Kredit dazu)" for k, v in anschluss.items()
                          if v and k not in angelegt]
    bericht.ungelesen += [f"{k} (Schlüssel der Seite, den kein Leser kannte)" for k in seite
                          if k not in _KREDIT_SEITE]
    neu["loans"] = behalten
    _bereiche_legen(neu, seite, bericht, {_n.BEREICH: zusatz})
    return neu


def _kredit_ohne_nebenwerte(kredit: dict) -> dict:
    """Ein Kredit ohne Notiz und ohne das, was die Seite an ihn legt, fuer den Vergleich."""
    weg = (*_NOTIZ_NAMEN, "entfernt", _KREDIT_VORLAGE, _KREDIT_ANSCHLUSS)
    return {k: v for k, v in kredit.items() if k not in weg}


def _kredite_alt(basis: dict, seite: dict) -> dict:
    """`lade_kredite` und die Anschlusskonditionen, wie sie vor dem Zusammenlegen lasen."""
    from finctl.realestate import loan as _loan

    vorlagen = seite.get("vorlagen") or {}
    eigene = dict(_n.ohne(seite.get("kredite")))
    aus = []
    for kredit in basis.get("loans") or []:
        kennung = str(kredit.get("id"))
        felder = eigene.pop(kennung, None)
        if (felder or {}).get("entfernt"):
            continue
        if felder:
            kredit = {**kredit, **felder}
        if _loan.an_szenario_gebunden(kredit):
            kredit = _loan.mit_vorlage(kredit, vorlagen.get(kennung) or {})
        aus.append(kredit)
    for kennung, felder in eigene.items():
        if not (felder or {}).get("entfernt"):
            aus.append({**felder, "id": kennung})
    eingegeben = _je_kennung(seite.get("anschluss"))
    return {"kredite": [_kredit_ohne_nebenwerte(k) for k in aus],
            "anschluss": {str(k["id"]): eingegeben[str(k["id"])] for k in aus
                          if eingegeben.get(str(k["id"]))}}


def _kredite_neu(spec: dict) -> dict:
    from finctl.realestate import loan as _loan

    kredite = _loan.aus_spec(spec)
    return {"kredite": [_kredit_ohne_nebenwerte(k) for k in kredite],
            "anschluss": {str(k["id"]): k[_KREDIT_ANSCHLUSS] for k in kredite
                          if k.get(_KREDIT_ANSCHLUSS)}}


# ------------------------------------------------- properties <-> properties_custom


def _objekt_ueberschreiben(objekt: dict, u: Any, bericht: Zusammenlegung, kennung: str, *,
                           angelegt: bool = False) -> None:
    """Wie `_ueberschreiben`, aber die Prognose Feld fuer Feld: `prognose.<feld>`.

    Wer auf der Seite nur die Miete tippte, behielt das Ende der Laufzeit der Basis.
    """
    if not isinstance(u, dict):
        return
    alt: list[tuple[str, Any]] = []
    if "prognose" in u:
        prognose = u["prognose"] if isinstance(u["prognose"], dict) else {}
        bisher = dict(objekt.get("prognose") or {})
        for feld, wert in prognose.items():
            if feld not in bisher:
                if not angelegt:
                    bericht.aus_seite.append(f"{kennung}.prognose.{feld} (Feld, nur in der Seite)")
            elif not _leer(bisher[feld]) and not _gleich(bisher[feld], wert):
                alt.append((f"`prognose.{feld}`", bisher[feld]))
                bericht.ueberschrieben.append((f"{kennung}.prognose.{feld}", _wert(bisher[feld])))
            bisher[feld] = wert
        if bisher:
            objekt["prognose"] = bisher
    _ueberschreiben(objekt, {k: v for k, v in u.items() if k != "prognose"}, bericht, kennung,
                    angelegt=angelegt, vorab=alt)


def _objekte_legen(basis: dict, seite: dict, bericht: Zusammenlegung) -> dict:
    """Die Seite ersetzt je Objekt Feld fuer Feld, die Prognose Unterfeld fuer Unterfeld.

    Ein Objekt nur in der Seite steht danach hinter denen der Basis, ein ausgeblendetes
    steht in der Sicherung und mit seiner Notiz beim Bereich.
    """
    neu = copy.deepcopy(basis)
    liste = _liste(neu, "properties")
    eigen = _je_kennung(seite.get("objekte"))
    behalten: list = []
    zusatz: list[str] = []
    for objekt in liste:
        if not (isinstance(objekt, dict) and objekt.get("id")):
            behalten.append(objekt)
            continue
        kennung = str(objekt["id"])
        u = eigen.pop(kennung, None)
        _objekt_ueberschreiben(objekt, u, bericht, kennung)
        if isinstance(u, dict) and u.get("entfernt"):
            _ausgeblendet(objekt, bericht, zusatz)
            continue
        behalten.append(objekt)
    for kennung, u in eigen.items():
        objekt = {"id": kennung}
        _objekt_ueberschreiben(objekt, u, bericht, kennung, angelegt=True)
        if isinstance(u, dict) and u.get("entfernt"):
            _ausgeblendet(objekt, bericht, zusatz)
            continue
        bericht.aus_seite.append(f"{kennung} (Objekt, in der Seite angelegt)")
        behalten.append(objekt)
    bericht.ungelesen += [f"{k} (Schlüssel der Seite, den kein Leser kannte)" for k in seite
                          if k not in ("objekte", _n.BEREICHE)]
    neu["properties"] = behalten
    _bereiche_legen(neu, seite, bericht, {_n.BEREICH: zusatz})
    return neu


def _objekt_ohne_nebenwerte(objekt: dict) -> dict:
    """Ein Objekt ohne Notiz und ohne leere Prognose, fuer den Vergleich."""
    aus = {k: v for k, v in objekt.items() if k not in (*_NOTIZ_NAMEN, "entfernt")}
    if not aus.get("prognose"):
        aus.pop("prognose", None)
    return aus


def _objekte_alt(basis: dict, seite: dict) -> list:
    """`objekte.vorhandene`, wie es vor dem Zusammenlegen las, in der Reihenfolge der Objekte."""
    aus = {str(p.get("id")): dict(p) for p in (basis.get("properties") or [])
           if isinstance(p, dict) and p.get("id")}
    for kennung, eintrag in _je_kennung(seite.get("objekte")).items():
        eintrag = eintrag or {}
        if eintrag.get("entfernt"):
            aus.pop(kennung, None)
            continue
        grund = aus.get(kennung, {"id": kennung})
        aus[kennung] = {**grund, **eintrag}
        if "prognose" in eintrag:
            aus[kennung]["prognose"] = {**(grund.get("prognose") or {}),
                                        **(eintrag["prognose"] or {})}
    return [(k, _objekt_ohne_nebenwerte(v)) for k, v in aus.items()]


def _objekte_neu(spec: dict) -> list:
    from finctl import objekte

    return [(k, _objekt_ohne_nebenwerte(v)) for k, v in objekte.aus_spec(spec).items()]


# ------------------------------------------------------------- goals <-> ziele_custom

#: Die Schluessel der Seitendatei, die der alte Leser kannte.
_ZIELE_SEITE = ("ziele", "reihenfolge", _n.BEREICHE)

#: Die Reihenfolge der Felder eines Ziels, wie sie in der Datei von Hand stehen.
_ZIEL_REIHE = ("id", "name", "cents", "stichtag", "basis", _n.NOTIZ, _n.VOM)


def _ziel_in_reihe(ziel: dict) -> dict:
    """Die Felder eines Ziels, das nur die Seite kannte, in der Reihenfolge der Datei.

    Die Seite schrieb sie nach Name sortiert. Hat das Ziel keinen Namen, steht danach seine
    Kennung dort -- das war der Name, den die Seite zeigte, und mit ihm schreibt Speichern ohne
    Aenderung kein Byte.
    """
    ziel = {"name": ziel["id"], **ziel} if "name" not in ziel else ziel
    return {**{k: ziel[k] for k in _ZIEL_REIHE if k in ziel},
            **{k: v for k, v in ziel.items() if k not in _ZIEL_REIHE}}


def _ziele_legen(basis: dict, seite: dict, bericht: Zusammenlegung) -> dict:
    """Die Seite ersetzt je Ziel Feld fuer Feld; die gezogene Reihenfolge wird `reihenfolge`.

    Ein Ziel nur in der Seite steht danach hinter denen der Basis, ein ausgeblendetes steht
    in der Sicherung und mit seiner Notiz beim Bereich. Die Vorgabe eines Notgroschens ohne
    Betrag bleibt beim Lesen (`forecast.ziele.aus_spec`), sie wird nicht in die Datei gebacken.
    """
    neu = copy.deepcopy(basis)
    liste = _liste(neu, "ziele")
    eigen = _je_kennung(seite.get("ziele"))
    behalten: list = []
    zusatz: list[str] = []
    for ziel in liste:
        if not (isinstance(ziel, dict) and ziel.get("id")):
            behalten.append(ziel)
            continue
        kennung = str(ziel["id"])
        u = eigen.pop(kennung, None)
        _ueberschreiben(ziel, u, bericht, kennung)
        if isinstance(u, dict) and u.get("entfernt"):
            _ausgeblendet(ziel, bericht, zusatz)
            continue
        behalten.append(ziel)
    for kennung, u in eigen.items():
        ziel = {"id": kennung}
        _ueberschreiben(ziel, u, bericht, kennung, angelegt=True)
        if isinstance(u, dict) and u.get("entfernt"):
            _ausgeblendet(ziel, bericht, zusatz)
            continue
        bericht.aus_seite.append(f"{kennung} (Ziel, in der Seite angelegt)")
        behalten.append(_ziel_in_reihe(ziel))
    bereiche = neu.pop(_n.BEREICHE, None)
    neu["ziele"] = behalten
    gezogen = [str(x) for x in seite.get("reihenfolge") or []]
    if gezogen:
        bisher = [str(x) for x in neu.get("reihenfolge") or []]
        if bisher and bisher != gezogen:
            zusatz.append(f"{STAND_VORHER}: `reihenfolge`: {_wert(bisher)}.")
            bericht.ueberschrieben.append(("reihenfolge", _wert(bisher)))
        neu["reihenfolge"] = gezogen
        bericht.aus_seite.append("reihenfolge (die auf der Seite gezogene Anordnung)")
    if bereiche is not None:
        neu[_n.BEREICHE] = bereiche
    bericht.ungelesen += [f"{k} (Schlüssel der Seite, den kein Leser kannte)" for k in seite
                          if k not in _ZIELE_SEITE]
    _bereiche_legen(neu, seite, bericht, {_n.BEREICH: zusatz})
    return neu


def _norm(wert: Any) -> Any:
    """Ein Wert fuer den Vergleich zweier Leser: ein Datum und derselbe Tag als Text sind gleich."""
    if isinstance(wert, date):
        return wert.isoformat()
    if isinstance(wert, Mapping):
        return {k: _norm(v) for k, v in wert.items()}
    if isinstance(wert, (list, tuple)):
        return [_norm(v) for v in wert]
    return wert


def _ziele_werte(ziele: dict) -> dict:
    """Was die Rechnung aus den Zielen liest: Reihenfolge, Liste und jedes Feld, ohne Notizen."""
    weg = (*_NOTIZ_NAMEN, "entfernt", "eigen")
    return {"reihenfolge": [str(x) for x in ziele.get("reihenfolge") or []],
            "ziele": [{"name": g["id"], **_norm({k: v for k, v in g.items() if k not in weg})}
                      for g in ziele.get("ziele") or []]}


def ziele_alt_gelesen(basis: dict, seite: dict) -> dict:
    """`ziele.merge_edits`, wie es vor dem Zusammenlegen las: die geltenden Ziele als Dokument.

    Mit Notizen und in der Reihenfolge von damals -- `forecast.ziele.progress` rechnet damit
    wie mit einem, das `aus_spec` liefert.
    """
    from finctl.forecast import ziele

    out = dict(basis)
    if seite.get("reihenfolge"):
        out["reihenfolge"] = [str(x) for x in seite["reihenfolge"]]
    offen = dict(_n.ohne(seite.get("ziele")))
    gelesen = []
    for ziel in basis.get("ziele") or []:
        edit = offen.pop(ziel.get("id"), None)
        if edit and edit.get("entfernt"):
            continue
        gelesen.append({**ziel, **edit} if edit else ziel)
    for kennung, edit in offen.items():
        if edit and not edit.get("entfernt"):
            gelesen.append({**edit, "id": kennung})
    out["ziele"] = gelesen
    return ziele._notgroschen_vorgabe(out)


def _ziele_alt(basis: dict, seite: dict) -> dict:
    return _ziele_werte(ziele_alt_gelesen(basis, seite))


def _ziele_neu(spec: dict) -> dict:
    from finctl.forecast import ziele

    return _ziele_werte(ziele.aus_spec(spec))


# ------------------------------------------------------- balances <-> balances_custom

#: Was der alte Leser aus der Seite fuer eine Position nahm, die einen Auszug hat: nur die
#: Notiz. Fuer jede andere: Wert, Stichtag, Gewinn und die Felder des Rueckkaufswerts.
_BESTAND_FELDER = ("cents", "as_of", "gewinn_cents", "rueckkauf_cents", "rueckkauf_as_of",
                   "eingezahlt_cents", "rueckkauf_policenwert_cents")
#: Was der alte Leser aus der Seite fuer eine Verpflichtung nahm.
_VERPFLICHTUNG_FELDER = ("cents", "name")
_BALANCES_SEITE = ("overrides", "verpflichtungen", "verlauf", _n.BEREICHE)
#: Wie eine Notiz auf der Seite zu einem Konto mit Auszug festgehalten wird.
AUSZUG_STAND = ("Bis zur Umstellung stand auf der Seite, und galt nicht, weil das Konto seinen "
                "Stand aus dem Auszug liest")


def _konto_modi(config: Path | None) -> set[str]:
    """Die Konten, die ihren Stand aus einem Auszug lesen: `ingest_mode: parsed`.

    Aus `accounts.yaml` und, wo es sie noch gibt, `accounts_custom.yaml`, so wie die Konten in
    die Datenbank kamen. Der Lauf, der `balances` zusammenlegt, legt auch `accounts` zusammen und
    schreibt erst danach: Beim Planen liegen beide Dateien noch, wie sie waren. Nach dem Lauf
    gibt es nur noch `accounts.yaml`, und es sagt dasselbe (Test
    `…the_account_modes_the_balances_merge_asks_for_survive_the_merge`). Ohne Ordner kennt keine
    Datei ein solches Konto.
    """
    if config is None:
        return set()

    def lesen(name: str) -> dict:
        pfad = config / name
        gelesen = yaml.safe_load(pfad.read_text(encoding="utf-8")) if pfad.exists() else None
        return gelesen if isinstance(gelesen, dict) else {}

    modus = {str(e["id"]): e.get("ingest_mode") for e in lesen("accounts.yaml").get("accounts")
             or [] if isinstance(e, dict) and e.get("id")}
    for kennung, felder in _n.ohne(lesen("accounts_custom.yaml").get("accounts")).items():
        felder = felder if isinstance(felder, dict) else {}
        if felder.get("entfernt"):
            modus.pop(str(kennung), None)
        elif "ingest_mode" in felder:
            modus[str(kennung)] = felder["ingest_mode"]
    return {k for k, m in modus.items() if m == "parsed"}


def _bestand_kennung(wurzel: str, eintrag: dict) -> str:
    """Wie eine Position oder Verpflichtung heisst: Konto oder Name; bei der Verpflichtung klein."""
    from finctl import bestaende

    if wurzel == "obligations":
        return bestaende.kennung(eintrag.get("name") or "")
    return str(eintrag.get("account_id") or eintrag.get("name") or "")


def _bestand_schluessel(eintrag: dict) -> str:
    return _bestand_kennung("balances", eintrag)


def _verlauf_der_seite(seite: dict) -> dict:
    return {str(k): v for k, v in _n.ohne(seite.get("verlauf")).items()}


def _position_legen(eintrag: dict, u: Any, parsed: set[str], bericht: Zusammenlegung) -> None:
    """Die Seite fuer eine Position: Felder, wo sie galten, sonst nur ihre Notiz.

    Hat das Konto einen Auszug, galt aus der Seite allein die Notiz; ein Wert, den die Seite
    trotzdem trug, steht danach in der Notiz und nirgends sonst -- in der Datei wuerde ihn
    `finctl init` lesen.
    """
    if u is None:
        return
    u = u if isinstance(u, dict) else {}
    kennung = _bestand_schluessel(eintrag)
    alt: list[tuple[str, Any]] = []
    danach: list[str] = []
    if str(eintrag.get("account_id") or "") in parsed:
        trug = [(f"`{f}`", u[f]) for f in _BESTAND_FELDER if f in u]
        if trug:
            danach.append(f"{AUSZUG_STAND}: " + "; ".join(
                f"{ort}: {_wert(w)}" for ort, w in trug) + ".")
            bericht.ungelesen += [f"overrides.{kennung}.{f} (Konto mit Auszug: galt nicht)"
                                  for f in _BESTAND_FELDER if f in u]
    else:
        for feld in _BESTAND_FELDER:
            if feld not in u or (feld == "as_of" and not u[feld]):
                continue
            if feld not in eintrag:
                bericht.aus_seite.append(f"{kennung}.{feld} (Feld, nur in der Seite)")
            elif not _leer(eintrag.get(feld)) and not _gleich(eintrag[feld], u[feld]):
                alt.append((f"`{feld}`", eintrag[feld]))
                bericht.ueberschrieben.append((f"{kennung}.{feld}", _wert(eintrag[feld])))
            eintrag[feld] = u[feld]
    bericht.ungelesen += [f"overrides.{kennung}.{f}" for f in u
                          if f not in _BESTAND_FELDER and f not in _NOTIZ_NAMEN]
    if alt:
        danach.append(_stand_vorher(alt))
    _notizen_legen(eintrag, u, kennung, bericht, danach or None)


def _verpflichtung_ersetzen(eintrag: dict, u: dict, k: str, bericht: Zusammenlegung) -> None:
    """Die Seite ersetzt `cents` und `name`; die Notizen kommen zusammen, die der Basis zuerst."""
    alt: list[tuple[str, Any]] = []
    for feld in _VERPFLICHTUNG_FELDER:
        if feld not in u:
            continue
        if not _leer(eintrag.get(feld)) and not _gleich(eintrag[feld], u[feld]):
            alt.append((f"`{feld}`", eintrag[feld]))
            bericht.ueberschrieben.append((f"verpflichtung {k}.{feld}", _wert(eintrag[feld])))
        eintrag[feld] = u[feld]
    bericht.ungelesen += [f"verpflichtungen.{k}.{f}" for f in u
                          if f not in (*_VERPFLICHTUNG_FELDER, "geloescht", *_NOTIZ_NAMEN)]
    _notizen_legen(eintrag, u, k, bericht, [_stand_vorher(alt)] if alt else None)


def _verpflichtung_anlegen(k: str, u: dict, bericht: Zusammenlegung) -> dict:
    """Eine Verpflichtung, die es nur in der Seite gab: Name, Betrag, wo einer steht, und Notiz."""
    eintrag: dict = {"name": u.get("name") or k}
    if u.get("cents") is not None:
        eintrag["cents"] = u["cents"]
    _notizen_legen(eintrag, u, k, bericht)
    bericht.ungelesen += [f"verpflichtungen.{k}.{f}" for f in u
                          if f not in (*_VERPFLICHTUNG_FELDER, "geloescht", *_NOTIZ_NAMEN)]
    bericht.aus_seite.append(f"{k} (Verpflichtung, in der Seite angelegt)")
    return eintrag


def _verpflichtungen_beisammen(neu: dict, seite: dict, bericht: Zusammenlegung
                               ) -> list[tuple[str, dict, dict]]:
    """Die Verbindlichkeiten der Datei, mit der Seite zusammen, und die, die nur die Seite hatte.

    (Kennung, Eintrag, Zeile der Seite); die Kennung ist die, unter der die Seite sie kannte.
    """
    from finctl import bestaende

    eigene = {bestaende.kennung(k): v for k, v in _n.ohne(seite.get("verpflichtungen")).items()}
    paare: list[tuple[str, dict, dict]] = []
    for eintrag in _liste(neu, "obligations"):
        if isinstance(eintrag, dict):
            k = bestaende.kennung(eintrag.get("name") or "")
            u = eigene.pop(k, None)
            u = u if isinstance(u, dict) else {}
            if u:
                _verpflichtung_ersetzen(eintrag, u, k, bericht)
            paare.append((k, eintrag, u))
    for k, u in eigene.items():
        if isinstance(u, dict) and u:
            paare.append((k, _verpflichtung_anlegen(k, u, bericht), u))
    return paare


def _verpflichtungen_legen(neu: dict, seite: dict, bericht: Zusammenlegung,
                           zusatz: list[str]) -> None:
    """Die Verbindlichkeiten: die Seite ersetzt `cents` und `name`; eine gestrichene ist weg.

    Ihre Notiz geht zum Bereich. Aendert die Seite den Namen, aendert sich die Kennung, die sich
    aus ihm ergibt; der Bericht haelt alte und neue fest.
    """
    from finctl import bestaende

    behalten = []
    for k, eintrag, u in _verpflichtungen_beisammen(neu, seite, bericht):
        if u.get("geloescht"):
            bericht.ausgeblendet.append(k)
            satz = _ausgeblendet_verpflichtung(eintrag, k)
            zusatz += [satz] if satz else []
            continue
        neu_k = bestaende.kennung(eintrag.get("name") or "")
        if neu_k != k:
            bericht.umbenannt[k] = neu_k
        behalten.append(eintrag)
    kennungen = [bestaende.kennung(e.get("name") or "") for e in behalten]
    doppelt = sorted({k for k in kennungen if kennungen.count(k) > 1})
    if doppelt:
        raise ValueError(f"zwei Verpflichtungen heißen danach gleich: {', '.join(doppelt)}")
    neu["obligations"] = behalten


def _ausgeblendet_verpflichtung(eintrag: dict, kennung: str) -> str:
    """Die Begruendung einer gestrichenen Verpflichtung geht in die Notiz des Bereichs."""
    notiz = _n.lesen(eintrag).text
    if not notiz:
        return ""
    return f"Ausgeblendet bis zur Umstellung: Verpflichtung `{kennung}`. {notiz}"


def _balances_legen(basis: dict, seite: dict, bericht: Zusammenlegung,
                    kontext: set[str] | None = None) -> dict:
    """Die Seite ersetzt je Position Wert, Stichtag, Gewinn und Rueckkaufswert -- ausser bei
    einem Konto mit Auszug --, je Verpflichtung `cents` und `name`; der Verlauf kommt dazu.

    Beide Notizen bleiben, die der Basis zuerst. Eine Position in der Seite, die es in der Datei
    nicht gibt, las kein Leser: Ihre Notiz geht zum Bereich.
    """
    parsed = kontext or set()
    neu = copy.deepcopy(basis)
    liste = _liste(neu, "balances")
    eigen = _je_kennung(seite.get("overrides"))
    zusatz: list[str] = []
    for eintrag in liste:
        if isinstance(eintrag, dict):
            _position_legen(eintrag, eigen.pop(_bestand_schluessel(eintrag), None), parsed,
                            bericht)
    for k, u in eigen.items():
        bericht.ungelesen.append(f"overrides.{k} (keine Position dazu)")
        text = _n.lesen(u).text
        if text:
            zusatz.append(f"Zu `overrides.{k}` (keine Position dazu): {text}")
    bereiche = neu.pop(_n.BEREICHE, None)
    _verpflichtungen_legen(neu, seite, bericht, zusatz)
    verlauf = _verlauf_der_seite(seite)
    if neu.get("verlauf"):
        bericht.ungelesen.append("verlauf (der Basis, den kein Leser kannte)")
    if verlauf:
        neu["verlauf"] = verlauf
        bericht.aus_seite.append("verlauf (die abgelegten Stände je Monat)")
    else:
        neu.pop("verlauf", None)
    if bereiche is not None:
        neu[_n.BEREICHE] = bereiche
    bericht.ungelesen += [f"{k} (Schlüssel der Seite, den kein Leser kannte)" for k in seite
                          if k not in _BALANCES_SEITE]
    _bereiche_legen(neu, seite, bericht, {_n.BEREICH: zusatz})
    return neu


def _bestand_zeile(zeile: dict) -> dict:
    """Eine Position ohne Notiz und ohne leere Felder: `cents: null` und kein Feld sind eines."""
    return {k: _norm(v) for k, v in zeile.items() if k not in _NOTIZ_NAMEN and v is not None}


def _bestaende_werte(spec: dict, positionen: list, verpflichtungen: list) -> dict:
    return {"as_of": _norm(spec.get("as_of")),
            "balances": [_bestand_zeile(z) for z in positionen],
            "obligations": [_bestand_zeile(z) for z in verpflichtungen],
            "verlauf": _norm(_n.ohne(spec.get("verlauf")))}


def _balances_alt(basis: dict, seite: dict, kontext: set[str] | None = None) -> dict:
    """`bestaende.zusammenfuehren` und `verpflichtungen`, wie sie vor dem Zusammenlegen lasen.

    Ohne die Staende aus dem Auszug (die kommen aus der Datenbank, nicht aus der Datei) und
    ohne Notizen. `verlauf` las nur die Seite.
    """
    from finctl import bestaende

    parsed = kontext or set()
    over = {str(k): v for k, v in _n.ohne(seite.get("overrides")).items()}
    zeilen = []
    for item in basis.get("balances") or []:
        row = dict(item)
        o = over.get(row.get("account_id") or row.get("name") or "") or {}
        if str(row.get("account_id") or "") in parsed:
            pass
        elif o:
            row["cents"] = o.get("cents", row.get("cents"))
            if o.get("as_of"):
                row["as_of"] = o["as_of"]
            if "gewinn_cents" in o:
                row["gewinn_cents"] = o["gewinn_cents"]
            row.update({f: o[f] for f in _BESTAND_FELDER[3:] if f in o})
        zeilen.append(row)
    eigene = {bestaende.kennung(k): v for k, v in _n.ohne(seite.get("verpflichtungen")).items()}
    pflichten, gesehen = [], set()
    for eintrag in basis.get("obligations") or []:
        k = bestaende.kennung(eintrag.get("name") or "")
        gesehen.add(k)
        e = eigene.get(k) or {}
        if e.get("geloescht"):
            continue
        zeile = {**eintrag, **{f: e[f] for f in _VERPFLICHTUNG_FELDER if f in e}}
        pflichten.append({**zeile, "kennung": bestaende.kennung(zeile.get("name") or "")})
    for k, e in eigene.items():
        if k in gesehen or not e or e.get("geloescht"):
            continue
        name = e.get("name") or k
        pflichten.append({"name": name, "cents": e.get("cents"),
                          "kennung": bestaende.kennung(name)})
    return _bestaende_werte({**basis, "verlauf": seite.get("verlauf")}, zeilen, pflichten)


def _balances_neu(spec: dict) -> dict:
    """Die Datei, wie die neuen Leser sie lesen: Positionen, Verpflichtungen und Verlauf."""
    from finctl import bestaende

    return _bestaende_werte(spec, [e for e in spec.get("balances") or [] if isinstance(e, dict)],
                            bestaende.verpflichtungen(spec))


# ------------------------------------------------------------- rules <-> rules_custom

#: Die Schluessel der Seitendatei, die der alte Leser kannte.
_REGELN_SEITE = ("regeln", _n.BEREICHE)

#: Die Reihenfolge der Felder einer Regel, wie sie in der Datei von Hand stehen.
_REGEL_REIHE = ("id", "name", "priority", "match", "set", "split")


def _nach_reihe(eintrag: dict, reihe: tuple[str, ...]) -> dict:
    """Die Felder eines Eintrags in der Reihenfolge, in der sie in der Datei von Hand stehen."""
    return {**{k: eintrag[k] for k in reihe if k in eintrag},
            **{k: v for k, v in eintrag.items() if k not in reihe}}


def _regeln_legen(basis: dict, seite: dict, bericht: Zusammenlegung) -> dict:
    """Die Seite ersetzt je Regel Feld fuer Feld (`match` und `set` als Ganzes).

    * Eine Regel nur in der Seite steht danach hinter denen der Basis.
    * Eine Regel der mitgelieferten Grundschicht, die die Seite aenderte, steht danach als
      ganze Regel in der Datei und gilt statt der mitgelieferten (so galt sie schon).
    * `entfernt: true` nimmt eine Regel aus der Datei; ihre Notiz steht beim Bereich. Gibt es
      die Kennung in der Grundschicht, steht sie danach unter `allgemeine_regeln_aus`, denn
      die mitgelieferte Regel blieb ausgeblendet, auch wenn die der Datei wegfiel.
    """
    from finctl.rules import engine

    neu = copy.deepcopy(basis)
    eigen = _je_kennung(seite.get("regeln"))
    aus = [str(k) for k in neu.get(engine.AUSGEBLENDET) or []]
    zusatz: list[str] = []
    behalten, in_datei = _regeln_der_datei(_liste(neu, "rules"), eigen, aus, zusatz, bericht)
    behalten += _regeln_der_seite(neu, eigen, in_datei, aus, zusatz, bericht)
    bericht.ungelesen += [f"{k} (Schlüssel der Seite, den kein Leser kannte)" for k in seite
                          if k not in _REGELN_SEITE]
    neu["rules"] = behalten
    if aus:
        # Hinter `allgemeine_regeln`, vor den Regeln.
        schluessel = [k for k in neu if k != engine.AUSGEBLENDET]
        platz = schluessel.index("rules")
        neu = {**{k: neu[k] for k in schluessel[:platz]}, engine.AUSGEBLENDET: aus,
               **{k: neu[k] for k in schluessel[platz:]}}
    _bereiche_legen(neu, seite, bericht, {_n.BEREICH: zusatz})
    return neu


def _regel_ausblenden(kennung: str, aus: list[str], bericht: Zusammenlegung) -> None:
    """Die Kennung unter `allgemeine_regeln_aus`, wenn die Grundschicht eine solche Regel hat."""
    from finctl.rules import engine

    if kennung in aus or kennung not in {str(e.get("id")) for e in engine.grundschicht()}:
        return
    aus.append(kennung)
    bericht.aus_seite.append(f"{kennung} (Regel der Grundschicht, ausgeblendet)")


def _regeln_der_datei(liste: list, eigen: dict, aus: list[str], zusatz: list[str],
                      bericht: Zusammenlegung) -> tuple[list, set[str]]:
    """Die Regeln der Basis mit dem, was die Seite zu ihnen sagte."""
    behalten: list = []
    in_datei: set[str] = set()
    for regel in liste:
        if not (isinstance(regel, dict) and regel.get("id")):
            behalten.append(regel)
            continue
        kennung = str(regel["id"])
        in_datei.add(kennung)
        u = eigen.get(kennung)
        _ueberschreiben(regel, u, bericht, kennung)
        if isinstance(u, dict) and u.get("entfernt"):
            _ausgeblendet(regel, bericht, zusatz)
            _regel_ausblenden(kennung, aus, bericht)
            continue
        behalten.append(regel)
    return behalten, in_datei


def _regeln_der_seite(neu: dict, eigen: dict, in_datei: set[str], aus: list[str],
                      zusatz: list[str], bericht: Zusammenlegung) -> list:
    """Was nur die Seite kannte: eigene Regeln und geaenderte der Grundschicht."""
    from finctl.rules import engine

    mitgeliefert = {str(e["id"]): e for e in engine.grundschicht() if e.get("id")}
    an = bool(neu.get("allgemeine_regeln"))
    dazu: list = []
    for kennung, u in eigen.items():
        if kennung in in_datei:
            continue
        gilt = an and kennung in mitgeliefert
        regel = copy.deepcopy(mitgeliefert[kennung]) if gilt else {"id": kennung}
        _ueberschreiben(regel, u, bericht, kennung, angelegt=not gilt,
                        wo=STAND_MITGELIEFERT if gilt else STAND_VORHER)
        if isinstance(u, dict) and u.get("entfernt"):
            _ausgeblendet(regel, bericht, zusatz)
            _regel_ausblenden(kennung, aus, bericht)
            continue
        if gilt:
            bericht.aus_seite.append(f"{kennung} (Regel der Grundschicht, geändert)")
        else:
            regel = _nach_reihe(regel, _REGEL_REIHE)
            bericht.aus_seite.append(f"{kennung} (Regel, in der Seite angelegt)")
        dazu.append(regel)
    return dazu


def _regel_ohne_nebenwerte(regel: dict) -> dict:
    """Eine Regel ohne Notiz, Herkunft und `entfernt`, fuer den Vergleich."""
    weg = (*_NOTIZ_NAMEN, "herkunft", "entfernt")
    return {k: v for k, v in regel.items() if k not in weg}


def _regeln_sortiert(regeln: list[dict]) -> list[dict]:
    return sorted((_regel_ohne_nebenwerte(r) for r in regeln), key=lambda r: str(r.get("id")))


def _regeln_alt(basis: dict, seite: dict) -> list[dict]:
    """`engine.rohe_regeln`, wie es vor dem Zusammenlegen las, in der Reihenfolge der Kennungen."""
    from finctl.rules import engine

    eigen = {k: dict(v or {}) for k, v in _je_kennung(seite.get("regeln")).items()}
    schichten = [(basis.get("rules") or [], "basis")]
    if basis.get("allgemeine_regeln"):
        schichten.append((engine.grundschicht(), "allgemein"))
    aus: list[dict] = []
    ids: set = set()
    for eintraege, herkunft in schichten:
        for eintrag in eintraege:
            if herkunft == "allgemein" and eintrag.get("id") in ids:
                continue
            ids.add(eintrag.get("id"))
            aenderung = eigen.get(str(eintrag.get("id")))
            if aenderung is None:
                aus.append({**eintrag})
            elif not aenderung.get("entfernt"):
                aus.append({**eintrag, **aenderung, "id": eintrag.get("id")})
    for kennung, eintrag in eigen.items():
        if kennung not in {str(i) for i in ids} and not eintrag.get("entfernt"):
            aus.append({**eintrag, "id": kennung})
    return _regeln_sortiert(aus)


def _regeln_neu(spec: dict) -> list[dict]:
    from finctl.rules import engine

    return _regeln_sortiert(engine.rohe_aus_spec(spec))


# ------------------------------------------------- accounts <-> accounts_custom


def _konten_legen(basis: dict, seite: dict, bericht: Zusammenlegung) -> dict:
    """Die Seite ersetzt je Konto Feld fuer Feld; ein Konto nur in der Seite steht dahinter.

    Ein mit `entfernt: true` ausgeblendetes Konto steht in der Sicherung, nicht in der neuen
    Datei; seine Notiz steht beim Bereich.
    """
    from finctl import konten

    neu = copy.deepcopy(basis)
    liste = _liste(neu, "accounts")
    eigen = _je_kennung(seite.get("accounts"))
    behalten: list = []
    zusatz: list[str] = []
    in_datei: set[str] = set()
    for konto in liste:
        if not (isinstance(konto, dict) and konto.get("id")):
            behalten.append(konto)
            continue
        kennung = str(konto["id"])
        in_datei.add(kennung)
        u = eigen.get(kennung)
        _ueberschreiben(konto, u, bericht, kennung)
        if isinstance(u, dict) and u.get("entfernt"):
            _ausgeblendet(konto, bericht, zusatz)
            continue
        behalten.append(konto)
    for kennung, u in eigen.items():
        if kennung in in_datei:
            continue
        konto = {"id": kennung}
        _ueberschreiben(konto, u, bericht, kennung, angelegt=True)
        if isinstance(u, dict) and u.get("entfernt"):
            _ausgeblendet(konto, bericht, zusatz)
            continue
        bericht.aus_seite.append(f"{kennung} (Konto, in der Seite angelegt)")
        behalten.append(_nach_reihe(konto, konten.FELDER))
    bericht.ungelesen += [f"{k} (Schlüssel der Seite, den kein Leser kannte)" for k in seite
                          if k not in ("accounts", _n.BEREICHE)]
    neu["accounts"] = behalten
    _bereiche_legen(neu, seite, bericht, {_n.BEREICH: zusatz})
    return neu


def _konto_ohne_nebenwerte(konto: dict) -> dict:
    return {k: v for k, v in konto.items() if k not in (*_NOTIZ_NAMEN, "entfernt")}


def _konten_alt(basis: dict, seite: dict) -> list[dict]:
    """`konten.laden`, wie es vor dem Zusammenlegen las, ohne Notizen."""
    konten: dict[str, dict] = {}
    for eintrag in basis.get("accounts") or []:
        konten[str(eintrag["id"])] = dict(eintrag)
    for kennung, felder in _je_kennung(seite.get("accounts")).items():
        if (felder or {}).get("entfernt"):
            konten.pop(str(kennung), None)
            continue
        vorher = konten.get(str(kennung)) or {"id": str(kennung)}
        konten[str(kennung)] = {**vorher, **(felder or {}), "id": str(kennung)}
    return [_konto_ohne_nebenwerte(k) for k in konten.values()]


def _konten_neu(spec: dict) -> list[dict]:
    from finctl import konten

    return [_konto_ohne_nebenwerte(k) for k in konten.aus_spec(spec)]


# ------------------------------------------------- lebensplan <-> lebensplan_custom


def _lebensplan_orte() -> dict[str, tuple[str, str]]:
    from finctl import person

    return person.ORTE


def _lebensplan_pfad(feld: str) -> str:
    abschnitt, schluessel = _lebensplan_orte()[feld]
    return f"{abschnitt}.{schluessel}"


def _lebensplan_wert(feld: str, wert: Any) -> Any:
    """Der Wert, wie die Datei ihn traegt: ein Datum als Datum, das Alter als Zahl."""
    from finctl import person

    if feld == "geburtsdatum":
        return person._datum(wert)
    if feld == "rente_ab_alter":
        return int(wert)
    return str(wert)


def _lebensplan_legen(basis: dict, seite: dict, bericht: Zusammenlegung) -> dict:
    """Die drei Angaben der Seite an ihren Ort in der Datei, unter dem Namen der Datei.

    `geburtsdatum` wird `person.birth_date`, `rente_ab_alter` wird `schwellen.grv_ab_alter`,
    `krankenversicherung` heisst gleich. Wie der alte Leser: Was die Seite leer liess, gilt
    nicht. Ein Wert der Basis, den sie ersetzte, steht in der Notiz unter dem Pfad.
    """
    neu = copy.deepcopy(basis)
    eigen = seite.get("person") if isinstance(seite.get("person"), dict) else {}
    orte = _lebensplan_orte()
    zusatz: dict[str, list[str]] = {}
    for feld, (abschnitt, schluessel) in orte.items():
        if not eigen.get(feld):
            continue
        pfad = f"{abschnitt}.{schluessel}"
        wert = _lebensplan_wert(feld, eigen[feld])
        if not isinstance(neu.get(abschnitt), dict):
            neu[abschnitt] = {}
        vorher = neu[abschnitt].get(schluessel)
        if not _leer(vorher) and _lebensplan_wert(feld, vorher) != wert:
            zusatz.setdefault(pfad, []).append(_stand_vorher([(f"`{pfad}`", vorher)]))
            bericht.ueberschrieben.append((pfad, _wert(vorher)))
        else:
            bericht.aus_seite.append(f"{pfad} (Angabe, nur in der Seite oder gleich der Basis)")
        neu[abschnitt][schluessel] = wert
    bericht.ungelesen += [f"person.{k}" for k in eigen if k not in orte]
    bericht.ungelesen += [f"{k} (Schlüssel der Seite, den kein Leser kannte)" for k in seite
                          if k not in ("person", _n.BEREICHE)]
    # Die Notizen der Seite stehen unter den Namen der Seite; die Datei kennt die ihren.
    block = seite.get(_n.BEREICHE) if isinstance(seite.get(_n.BEREICHE), Mapping) else {}
    umbenannt = {f"person.{feld}": f"{a}.{k}" for feld, (a, k) in orte.items()}
    _bereiche_legen(neu, {_n.BEREICHE: {umbenannt.get(str(o), str(o)): v
                                        for o, v in block.items()}}, bericht, zusatz)
    return neu


def _lebensplan_rest(spec: dict) -> dict:
    """Alles in der Datei ausser den drei Angaben und den Notizen, leere Abschnitte gestrichen."""
    rest = {k: copy.deepcopy(v) for k, v in spec.items() if k != _n.BEREICHE}
    for abschnitt, schluessel in _lebensplan_orte().values():
        if isinstance(rest.get(abschnitt), dict):
            rest[abschnitt].pop(schluessel, None)
            if not rest[abschnitt]:
                del rest[abschnitt]
    return rest


def _lebensplan_alt(basis: dict, seite: dict) -> dict:
    """`person.angaben`, wie es vor dem Zusammenlegen las, dazu alles andere der Basis."""
    from finctl import person

    aus = person.aus_spec(basis)
    eigen = seite.get("person") if isinstance(seite.get("person"), dict) else {}
    if eigen.get("geburtsdatum"):
        aus["geburtsdatum"] = person._datum(eigen["geburtsdatum"])
    if eigen.get("krankenversicherung"):
        aus["krankenversicherung"] = str(eigen["krankenversicherung"])
    if eigen.get("rente_ab_alter"):
        aus["rente_ab_alter"] = int(eigen["rente_ab_alter"])
    return {"angaben": aus, "rest": _lebensplan_rest(basis)}


def _lebensplan_neu(spec: dict) -> dict:
    from finctl import person

    return {"angaben": person.aus_spec(spec), "rest": _lebensplan_rest(spec)}


def _lebensplan_orte_neu(ort: str) -> str:
    """Wo die Notiz einer Angabe der Seite nach dem Zusammenlegen steht."""
    umbenannt = {f"person.{feld}": f"{a}.{k}" for feld, (a, k) in _lebensplan_orte().items()}
    return umbenannt.get(ort, ort)


# ------------------------------------------------------- backup <-> backup_custom

#: Was der alte Leser aus der Seite fuer die Sicherung nahm: `{**basis, **seite}`, gelesen
#: wurden `directory` und `keep`. Jeder andere Schluessel der Seite blieb ohne Wirkung.
_SICHERUNG_FELDER = ("directory", "keep")


def _backup_legen(basis: dict, seite: dict, bericht: Zusammenlegung) -> dict:
    """Ziel und Anzahl der Seite in die Datei; was sie ersetzten, steht in der Notiz."""
    neu = copy.deepcopy(basis)
    eigen = seite.get("backup") if isinstance(seite.get("backup"), dict) else {}
    zusatz: dict[str, list[str]] = {}
    for feld in _SICHERUNG_FELDER:
        if feld not in eigen:
            continue
        if feld in neu and not _leer(neu[feld]) and not _gleich(neu[feld], eigen[feld]):
            zusatz.setdefault(feld, []).append(_stand_vorher([(f"`{feld}`", neu[feld])]))
            bericht.ueberschrieben.append((feld, _wert(neu[feld])))
        elif feld not in neu:
            bericht.aus_seite.append(f"{feld} (Angabe, nur in der Seite)")
        neu[feld] = eigen[feld]
    bericht.ungelesen += [f"backup.{k}" for k in eigen if k not in _SICHERUNG_FELDER]
    bericht.ungelesen += [f"{k} (Schlüssel der Seite, den kein Leser kannte)" for k in seite
                          if k not in ("backup", _n.BEREICHE)]
    _bereiche_legen(neu, seite, bericht, zusatz)
    return neu


def _backup_werte(spec: dict) -> dict:
    return {"gelesen": {k: spec.get(k) for k in _SICHERUNG_FELDER},
            "rest": {k: v for k, v in spec.items()
                     if k not in (*_SICHERUNG_FELDER, _n.BEREICHE)}}


def _backup_alt(basis: dict, seite: dict) -> dict:
    """`ops.backup_settings`, wie es vor dem Zusammenlegen las: `{**spec, **seite}`."""
    eigen = seite.get("backup") if isinstance(seite.get("backup"), dict) else {}
    return _backup_werte({**basis, **{k: v for k, v in eigen.items() if k in _SICHERUNG_FELDER}})


# ------------------------------------------------ settings_custom -> assumptions + forecast

#: Der Schluessel der Seite, unter dem sie ihre Werte fuehrte, und wie er einen Wert eines Kontos
#: nannte: `floor_cents:<konto>`.
_SEITE_EINSTELLUNGEN = "einstellungen"
_UNTERGRENZE = "floor_cents:"


def _stellschrauben() -> dict[str, tuple[str, ...]]:
    """Die zwoelf Stellschrauben und ihr Pfad in `assumptions.yaml` (`UEBERSCHREIBBAR`)."""
    from finctl import assumptions

    return assumptions.UEBERSCHREIBBAR


def _werte_der_seite(seite: Mapping) -> dict:
    block = seite.get(_SEITE_EINSTELLUNGEN)
    return _n.ohne(block) if isinstance(block, Mapping) else {}


def _untergrenze(schluessel: Any) -> str | None:
    """Das Konto eines Schluessels `floor_cents:<konto>`, sonst `None`."""
    text = str(schluessel)
    return text[len(_UNTERGRENZE):] or None if text.startswith(_UNTERGRENZE) else None


def _untergrenze_cents(wert: Any) -> int | None:
    """Wie `_floor_for` den Wert las: ganze Cent, sonst galt die Zeile nicht."""
    try:
        return int(str(wert))
    except (TypeError, ValueError):
        return None


def _ort_der_seite(ort: str) -> str:
    """Der Name unter `notizen:` ohne den Schluessel der Seite davor."""
    vorn = f"{_SEITE_EINSTELLUNGEN}."
    return ort[len(vorn):] if ort.startswith(vorn) else ort


def _einstellungen_ansicht(seite: dict) -> tuple[dict, list[str]]:
    """Was `assumptions.yaml` von der Seite bekommt: die Stellschrauben und alles, was keine
    Untergrenze ist. Die Notizen stehen unter dem Pfad, den die Stellschraube in der Datei hat;
    die Notiz des Bereichs und die zu einem Schluessel, den kein Leser kannte, kommen hierher.
    """
    pfade = _stellschrauben()
    werte = _werte_der_seite(seite)
    ansicht: dict = {_SEITE_EINSTELLUNGEN: {k: v for k, v in werte.items() if k in pfade}}
    unbekannt = [str(k) for k in werte if k not in pfade and _untergrenze(k) is None]
    block = seite.get(_n.BEREICHE) if isinstance(seite.get(_n.BEREICHE), Mapping) else {}
    notizen = {}
    for ort, eintrag in block.items():
        schluessel = _ort_der_seite(str(ort))
        if _untergrenze(schluessel) is not None:
            continue
        notizen[".".join(pfade[schluessel]) if schluessel in pfade else str(ort)] = eintrag
    if notizen:
        ansicht[_n.BEREICHE] = notizen
    rest = [f"{_SEITE_EINSTELLUNGEN}.{k} (Einstellung, die kein Leser kannte)" for k in unbekannt]
    rest += [f"{k} (Schlüssel der Seite, den kein Leser kannte)" for k in seite
             if k not in (_SEITE_EINSTELLUNGEN, _n.BEREICHE)]
    return ansicht, rest


def _untergrenzen_ansicht(seite: dict) -> tuple[dict, list[str]]:
    """Was `forecast.yaml` von der Seite bekommt: je Konto `account_roles.<konto>.floor_cents`.

    Eine Notiz zu einer Untergrenze wird die Notiz der Konto-Regel, mit dem Feldnamen davor
    (Entscheidung 2). Ein Wert, den `_floor_for` nicht als ganze Zahl las, galt nie.
    """
    rollen: dict[str, dict] = {}
    verworfen = []
    for schluessel, wert in _werte_der_seite(seite).items():
        konto = _untergrenze(schluessel)
        if konto is None:
            continue
        cents = _untergrenze_cents(wert)
        if cents is None:
            verworfen.append(f"{schluessel} (kein ganzer Betrag, galt nicht)")
        else:
            rollen[konto] = {"floor_cents": cents}
    block = seite.get(_n.BEREICHE) if isinstance(seite.get(_n.BEREICHE), Mapping) else {}
    for ort, eintrag in block.items():
        konto = _untergrenze(_ort_der_seite(str(ort)))
        notiz = _n.lesen(eintrag)
        if konto is None or konto not in rollen or not notiz.text:
            continue
        rollen[konto].update(_n.Notiz(f"`floor_cents`: {notiz.text}", notiz.vom).als_dict())
    return ({"account_roles": rollen} if rollen else {}), verworfen


def _stellschrauben_legen(basis: dict, seite: dict, bericht: Zusammenlegung) -> dict:
    """Die Werte der Seite an den Pfad, den `assumptions.load` ihnen gab.

    Die Seite gewinnt, auch mit einem leeren Wert (so las es `load`). Ein Wert, den sie
    ersetzte, steht in der Notiz unter dem Pfad; was die Datei nicht kannte (`teilzeit_anteil`
    und `teilzeit_ab` in der Basis der meisten Haushalte), steht danach im Abschnitt, in dem
    `load` es angelegt hat.
    """
    neu = copy.deepcopy(basis)
    zusatz: dict[str, list[str]] = {}
    werte = _werte_der_seite(seite)
    for schluessel, pfad in _stellschrauben().items():
        if schluessel not in werte:
            continue
        knoten = neu
        for teil in pfad[:-1]:
            if not isinstance(knoten.get(teil), dict):
                knoten[teil] = {}
            knoten = knoten[teil]
        ort = ".".join(pfad)
        vorher = knoten.get(pfad[-1])
        if not _leer(vorher) and not _gleich(vorher, werte[schluessel]):
            zusatz.setdefault(ort, []).append(_stand_vorher([(f"`{ort}`", vorher)]))
            bericht.ueberschrieben.append((ort, _wert(vorher)))
        elif pfad[-1] not in knoten:
            bericht.aus_seite.append(f"{ort} (Angabe, nur in der Seite)")
        knoten[pfad[-1]] = werte[schluessel]
    _bereiche_legen(neu, seite, bericht, zusatz)
    return neu


def _stellschrauben_werte(spec: dict) -> dict:
    return {k: copy.deepcopy(v) for k, v in spec.items() if k != _n.BEREICHE}


def _stellschrauben_alt(basis: dict, seite: dict) -> dict:
    """`assumptions.load`, wie es vor dem Zusammenlegen las: die Stellschrauben darueber."""
    spec = _stellschrauben_werte(basis)
    werte = _werte_der_seite(seite)
    for schluessel, pfad in _stellschrauben().items():
        if schluessel not in werte:
            continue
        knoten = spec
        for teil in pfad[:-1]:
            knoten = knoten.setdefault(teil, {})
        knoten[pfad[-1]] = werte[schluessel]
    return spec


# ------------------------------------------------------------------------- die Paare

#: Die Paare, die `finctl umstellen` zusammenlegt. Jeder Teilschritt von N.3 nimmt seine
#: Bereiche dazu.
PAARE: tuple[Paar, ...] = (
    Paar("forecast.yaml", "forecast_custom.yaml", _forecast_legen, _forecast_alt, _forecast_neu,
         wurzeln=("account_roles",)),
    Paar("taxonomy.yaml", "taxonomy_custom.yaml", _taxonomie_legen, _taxonomie_alt,
         _taxonomie_neu, wurzeln=ACHSEN, vorlage="taxonomy.yaml"),
    Paar("renten.yaml", "renten_custom.yaml", _renten_legen, _renten_alt, _renten_neu,
         wurzeln=("renten",), angelegt="neu"),
    Paar("abos.yaml", "abos_custom.yaml", _vertraege_legen("abos"), _vertraege_alt("abos"),
         _vertraege_neu("abo"), wurzeln=("abos",)),
    Paar("versicherungen.yaml", "versicherungen_custom.yaml", _vertraege_legen("versicherungen"),
         _vertraege_alt("versicherungen"), _vertraege_neu("versicherung"),
         wurzeln=("versicherungen",)),
    Paar("loans.yaml", "loans_custom.yaml", _kredite_legen, _kredite_alt, _kredite_neu,
         wurzeln=("loans",), seitenwurzel="kredite"),
    Paar("properties.yaml", "properties_custom.yaml", _objekte_legen, _objekte_alt, _objekte_neu,
         wurzeln=("properties",), seitenwurzel="objekte"),
    Paar("goals.yaml", "ziele_custom.yaml", _ziele_legen, _ziele_alt, _ziele_neu,
         wurzeln=("ziele",), vorlage="goals.yaml"),
    Paar("balances.yaml", "balances_custom.yaml", _balances_legen, _balances_alt, _balances_neu,
         wurzeln=("balances", "obligations"), seitenwurzel=("overrides", "verpflichtungen"),
         vorlage="balances.yaml", kontext=_konto_modi, kennung_von=_bestand_kennung),
    Paar("rules.yaml", "rules_custom.yaml", _regeln_legen, _regeln_alt, _regeln_neu,
         wurzeln=("rules",), seitenwurzel="regeln", vorlage="rules.yaml"),
    Paar("accounts.yaml", "accounts_custom.yaml", _konten_legen, _konten_alt, _konten_neu,
         wurzeln=("accounts",)),
    Paar("lebensplan.yaml", "lebensplan_custom.yaml", _lebensplan_legen, _lebensplan_alt,
         _lebensplan_neu, vorlage="lebensplan.yaml", ort_neu=_lebensplan_orte_neu),
    Paar("backup.yaml", "backup_custom.yaml", _backup_legen, _backup_alt, _backup_werte),
    # `settings_custom.yaml` geht in zwei Dateien. Die Untergrenzen kommen nach `forecast.yaml`,
    # NACH dem Paar mit `forecast_custom.yaml` (oben): Wo beide ein Konto nannten, galt die
    # Untergrenze der Einstellungen vor der der Konto-Regel, und so bleibt es.
    Paar("assumptions.yaml", "settings_custom.yaml", _stellschrauben_legen, _stellschrauben_alt,
         _stellschrauben_werte, vorlage="assumptions.yaml", ansicht=_einstellungen_ansicht),
    Paar("forecast.yaml", "settings_custom.yaml", _forecast_legen, _forecast_alt, _forecast_neu,
         wurzeln=("account_roles",), ansicht=_untergrenzen_ansicht),
)


def paar_der_seite(name: str) -> Paar | None:
    return next((p for p in PAARE if p.seite == name), None)


def vorlage_lesen(paar: Paar) -> dict:
    """Die Startvorlage, die `init` als Basisdatei anlegte, wenn sie fehlt (sonst leer)."""
    if not paar.vorlage:
        return {}
    from finctl import vorgaben

    pfad = vorgaben.ORDNER / paar.vorlage
    return (yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}) if pfad.exists() else {}


# ------------------------------------------------------------------ zusammenlegen


def _je(paar: Paar, wurzel: str, wert: Any) -> dict[str, Any]:
    """Die Eintraege einer Wurzel nach Kennung; ist sie nicht `id`, sagt `kennung_von` sie."""
    if paar.kennung_von is not None and isinstance(wert, list):
        aus = ((paar.kennung_von(wurzel, e), e) for e in wert if isinstance(e, dict))
        return {k: e for k, e in aus if k}
    return _je_kennung(wert)


def _seitenwurzel(paar: Paar, nr: int) -> str:
    wurzel = paar.wurzeln[nr]
    if isinstance(paar.seitenwurzel, tuple):
        return paar.seitenwurzel[nr] or wurzel
    return paar.seitenwurzel or wurzel


def _notizen_pruefen(paar: Paar, basis: dict, seite: dict, neu: dict,
                     umbenannt: Mapping[str, str] | None = None) -> list[str]:
    """Steht der Text beider Notizen in der Notiz, die danach gilt?"""
    fehler = []
    umbenannt = umbenannt or {}
    for nr, wurzel in enumerate(paar.wurzeln):
        gilt_je = _je(paar, wurzel, neu.get(wurzel))
        basis_je = _je(paar, wurzel, basis.get(wurzel))
        seite_je = _je(paar, wurzel, seite.get(_seitenwurzel(paar, nr)))
        if paar.angelegt and wurzel == paar.wurzeln[0]:
            seite_je |= {k: v for k, v in _je_kennung(seite.get(paar.angelegt)).items()
                         if k not in seite_je}
        bereich = _n.lesen((neu.get(_n.BEREICHE) or {}).get(_n.BEREICH)).text
        for key in {*basis_je, *seite_je}:
            # Ein ausgeblendeter Eintrag ist nicht mehr da; seine Notiz steht beim Bereich.
            neuer = umbenannt.get(key, key)
            gilt = (_n.lesen(gilt_je[neuer]).text if neuer in gilt_je else bereich)
            for woher, eintrag in (("Basis", basis_je.get(key)), ("Seite", seite_je.get(key))):
                text = _n.lesen(eintrag).text
                if text and text not in gilt:
                    fehler.append(f"{paar.basis}: die Notiz der {woher} zu {wurzel}.{key} "
                                  "steht nicht in der zusammengelegten")
    return fehler


def _bereiche_pruefen(paar: Paar, basis: dict, seite: dict, neu: dict) -> list[str]:
    """Steht der Text jeder Notiz unter `notizen:` in beiden Dateien in der, die danach gilt?

    Fuer die Dateien ohne Eintraege (Einstellungen), aber auch bei den anderen: Die Notiz des
    Bereichs und die einer Einstellung gehen hier ebenfalls nicht verloren.
    """
    fehler = []
    gelegt = neu.get(_n.BEREICHE)
    gelegt = gelegt if isinstance(gelegt, Mapping) else {}
    for woher, datei in (("Basis", basis), ("Seite", seite)):
        block = datei.get(_n.BEREICHE)
        for ort, eintrag in (block if isinstance(block, Mapping) else {}).items():
            ziel = str(ort)
            if woher == "Seite" and paar.ort_neu is not None:
                ziel = paar.ort_neu(ziel)
            text = _n.lesen(eintrag).text
            if text and text not in _n.lesen(gelegt.get(ziel)).text:
                fehler.append(f"{paar.basis}: die Notiz der {woher} unter notizen.{ort} "
                              "steht nicht in der zusammengelegten")
    return fehler


def zusammenlegen(paar: Paar, basis: dict, seite: dict, *,
                  basis_text: str | None = None, config: Path | None = None) -> Zusammenlegung:
    """Das Paar zu einer Datei: das Ergebnis, was geschah und was die Pruefungen sagen.

    `basis` und `seite` sind die Dateien in Notizform, gelesen. `basis_text` ist der Text
    der Basisdatei, wie sie jetzt ist; sagt die Seite nichts anderes, bleibt er und
    `Zusammenlegung.neu` ist `None`. `config` ist der Ordner, in dem beide liegen, fuer
    ein Paar, das ueber die Datei hinaus etwas wissen muss (`Paar.kontext`).
    """
    from finctl import dateien

    bericht = Zusammenlegung(paar.basis, paar.seite)
    if paar.ansicht is not None:
        seite, ungelesen = paar.ansicht(seite)
        bericht.ungelesen += ungelesen
    kontext = {"kontext": paar.kontext(config)} if paar.kontext else {}
    try:
        neu = paar.legen(basis, seite, bericht, **kontext)
    except (ValueError, TypeError) as fehler:
        bericht.fehler.append(f"{paar.seite}: {fehler}")
        return bericht
    if paar.alt(basis, seite, **kontext) != paar.neu(neu):
        bericht.fehler.append(f"{paar.basis}: die zusammengelegte Datei liest sich nicht "
                              "wie Basis und Seite zusammen")
    bericht.fehler += _notizen_pruefen(paar, basis, seite, neu, bericht.umbenannt)
    bericht.fehler += _bereiche_pruefen(paar, basis, seite, neu)
    text = dateien.yaml_text(neu)
    if yaml.safe_load(text) != neu:
        bericht.fehler.append(f"{paar.basis}: die geschriebene Datei sagt nicht, was sie soll")
    if not bericht.fehler and (neu != basis or basis_text is None):
        bericht.neu = text
    return bericht


def seite_lesen(text: str) -> dict:
    """Die Seitendatei als Zuordnung; leer, wenn sie nichts sagt."""
    gelesen = yaml.safe_load(text)
    return gelesen if isinstance(gelesen, dict) else {}
