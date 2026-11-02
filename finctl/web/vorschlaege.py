"""Vorschlaege einer KI: geprueft, abgelegt, vom Haushalt bestaetigt (ADR 0002).

Ein Modell schreibt nie in `config/`. Es legt einen Vorschlag ab: eine Datei in
`data/vorschlaege/` mit der Art, den Feldern und einem Satz, warum. Ein Vorschlag
ist keine Handentscheidung. Erst "Uebernehmen" auf `/vorschlaege` schickt seine
Felder an die Route, die die Seiten selbst benutzen; danach ist es eine
Handentscheidung wie jede andere, und die Datei faellt weg.

GEPRUEFT wird mit den Pruefungen der Routen, nicht mit eigenen: `regel_pruefen`,
`neue_planzeile`, `kredite.neuer_kredit`. Eine Regel, die die Seite ablehnt, nimmt
auch die Ablage nicht an, und die Meldung ist dieselbe. Dieselbe Pruefung laeuft
noch einmal, wenn die Seite den Vorschlag zeigt: Zwischen Ablage und Ansehen kann
sich `config/` geaendert haben.

Die Felder sind die, die die Route nimmt (Betraege in Cent, negativ = raus). Nur
`notiz` ist eine Huelle, weil jeder Eintrag seine eigene Route hat: `ort` sagt,
welche (`ziel`, `konto`).
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from finctl import notizen as _notizen
from finctl import pfade
from finctl.dateien import yaml_lesen, yaml_text

#: Wie lang das "warum" eines Modells sein darf.
WARUM_MAX = 500

_KENNUNG = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$")


@dataclass(frozen=True, slots=True)
class Art:
    kennung: str
    name: str
    #: Die Felder, die ein Vorschlag dieser Art tragen darf (alle anderen sind ein Fehler).
    felder: tuple[str, ...]
    #: Ein Satz fuer das Modell: was die Art anlegt und welche Felder sie braucht.
    beschreibung: str


ARTEN: dict[str, Art] = {a.kennung: a for a in (
    Art("regel", "Regel",
        ("name", "text", "text_all", "counterparty", "account", "sign", "betrag_von_cents",
         "betrag_bis_cents", "datum_von", "datum_bis", "mgmt", "tax", "property", "note",
         "priority"),
        "Eine neue Regel. Pflicht: name, mgmt (Kategorie, ID aus kategorien) und mindestens "
        "eine Bedingung (text, text_all, counterparty oder account). text, text_all und "
        "counterparty sind Listen von Suchtexten; sign ist '+' oder '-'; Betraege in Cent."),
    Art("planzeile", "Planzeile in einer Klammer",
        ("szenario", "art", "label", "kategorie", "konto", "frequenz", "start", "ende",
         "amount_cents", "nur_kontoprognose"),
        "Eine Planzeile in einer Klammer (szenario = Kennung oder Name; eine neue Klammer "
        "entsteht, wo es sie nicht gibt). Pflicht: szenario, label, kategorie, start "
        "(JJJJ-MM-TT). art: betrag (Standard), wegfall oder erwartet. amount_cents in Cent, "
        "negativ = raus, positiv = rein. frequenz: monatlich (Standard), einmalig u. a."),
    Art("kredit", "Kredit",
        ("id", "name", "lender", "servicing_account_id", "start", "ende",
         "opening_balance_cents", "annuity_cents", "annual_rate_pct"),
        "Ein Ratenkredit mit festem Zins. Pflicht: alle Felder. id: klein, Ziffern und "
        "Bindestriche; servicing_account_id: das Konto, von dem die Rate abgeht; start und "
        "ende als JJJJ-MM-TT; Restschuld und Monatsrate in Cent, positiv; Zins in Prozent."),
    Art("notiz", "Notiz an einem Eintrag",
        ("ort", "id", "notiz"),
        "Eine Notiz an einem Ziel (ort = ziel) oder einem Konto (ort = konto); id ist die "
        "Kennung des Eintrags. Die Notiz sagt, WARUM der Eintrag so ist; sie ersetzt eine "
        "vorhandene."),
)}

#: Kreditfelder, die die Route als Text liest (`<feld>_text`).
KREDIT_TEXT = {"opening_balance_cents": "betrag", "annuity_cents": "betrag",
               "annual_rate_pct": "zahl"}


@dataclass(slots=True)
class Pruefung:
    """Was ein Vorschlag tut, wenn jemand zusagt: Route, Koerper, und was sich aendert."""

    route: str
    body: dict
    #: Eine Zeile, die sagt, was entsteht.
    titel: str
    #: (Feld, Wert) -- das, was sich aendern wuerde.
    zeilen: list[tuple[str, str]] = field(default_factory=list)
    #: Was der Haushalt wissen sollte, bevor er zusagt (Wirkung, Klammer aus ...).
    hinweise: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Vorschlag:
    id: str
    art: str
    felder: dict
    warum: str = ""
    angelegt: str = ""


# --------------------------------------------------------------------- Ablage

def _ordner() -> Path:
    return pfade.VORSCHLAEGE_DIR


def _datei(kennung: str) -> Path:
    if not _KENNUNG.match(kennung):
        raise ValueError("Diesen Vorschlag gibt es nicht.")
    return _ordner() / f"{kennung}.json"


def _schreiben(v: Vorschlag) -> None:
    ordner = _ordner()
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = _datei(v.id)
    roh = {"art": v.art, "felder": v.felder, "warum": v.warum, "angelegt": v.angelegt}
    tmp = ziel.with_suffix(".tmp")
    tmp.write_text(json.dumps(roh, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, ziel)


def _lesen(pfad: Path) -> Vorschlag | None:
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
        felder = roh["felder"]
        if roh["art"] not in ARTEN or not isinstance(felder, dict):
            return None
        return Vorschlag(pfad.stem, roh["art"], felder, str(roh.get("warum") or ""),
                         str(roh.get("angelegt") or ""))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def alle() -> list[Vorschlag]:
    """Die offenen Vorschlaege, aelteste zuerst. Eine unlesbare Datei zaehlt nicht."""
    if not _ordner().is_dir():
        return []
    return [v for v in (_lesen(p) for p in sorted(_ordner().glob("*.json"))) if v]


def anzahl() -> int:
    return len(alle())


def verwerfen(kennung: str) -> bool:
    """Den Vorschlag loeschen. `True`, wenn es ihn gab."""
    try:
        _datei(kennung).unlink()
    except FileNotFoundError:
        return False
    return True


def ablegen(art: str, felder: object, warum: str, c: sqlite3.Connection) -> Vorschlag:
    """Pruefen und ablegen. `ValueError` mit der Meldung der Route, wenn er nicht taugt."""
    pruefen(art, felder, c)
    jetzt = datetime.now()
    satz = " ".join(str(warum or "").split())[:WARUM_MAX]
    v = Vorschlag(f"{jetzt:%Y%m%d-%H%M%S}-{secrets.token_hex(3)}", art, dict(felder), satz,
                  jetzt.isoformat(timespec="seconds"))
    _schreiben(v)
    return v


# -------------------------------------------------------------------- Pruefen

def pruefen(art: str, felder: object, c: sqlite3.Connection) -> Pruefung:
    """Was der Vorschlag taete, mit der Pruefung der Route. `ValueError` sagt, was nicht stimmt."""
    if art not in ARTEN:
        raise ValueError(f"Unbekannte Art „{art}“. Es gibt: {', '.join(ARTEN)}.")
    if not isinstance(felder, dict) or not felder:
        raise ValueError("Die Felder fehlen.")
    erlaubt = set(ARTEN[art].felder)
    if art == "kredit":
        erlaubt |= {f"{f}_text" for f in KREDIT_TEXT}
    fremd = sorted(str(k) for k in felder if k not in erlaubt)
    if fremd:
        raise ValueError(f"Unbekannte Felder: {', '.join(fremd)}. Erlaubt: "
                         f"{', '.join(ARTEN[art].felder)}.")
    return {"regel": _regel, "planzeile": _planzeile, "kredit": _kredit,
            "notiz": _notiz}[art](dict(felder), c)


def _euro(cents: object) -> str:
    from finctl.web.basis import euro

    return euro(cents if isinstance(cents, int) else 0)


def _betrag(wert: object, feld: str) -> int | None:
    if wert in (None, ""):
        return None
    if isinstance(wert, bool) or not isinstance(wert, int):
        raise ValueError(f"{feld}: ein Betrag in Cent als ganze Zahl")
    return wert


def _regel(felder: dict, c: sqlite3.Connection) -> Pruefung:
    from finctl.rules import categorize as cz
    from finctl.rules import engine
    from finctl.web.routen.regeln import regel_pruefen

    for f in ("betrag_von_cents", "betrag_bis_cents"):
        _betrag(felder.get(f), f)
    body = {**felder, "neu": True}
    if not str(body.get("name") or "").strip():
        raise ValueError("Name fehlt")
    e, alle_regeln = regel_pruefen(c, body)
    wirkung = cz.vorschau(c, engine.regeln_aus(alle_regeln), e["id"])
    match, setzt = e.get("match") or {}, e.get("set") or {}
    zeilen = [("Name", e["name"]), ("Bedingung", yaml_text(match).strip().replace("\n", "; "))]
    zeilen += [("Setzt", yaml_text(setzt).strip().replace("\n", "; ")),
               ("Priorität", str(e.get("priority")))]
    hinweise = [(f"Träfe heute {wirkung['treffer']} Buchungen, davon würden "
                 f"{wirkung['aendert']} ihre Kategorie wechseln.")]
    if wirkung["verdeckt"]:
        hinweise.append(f"{wirkung['verdeckt']} weitere passen, gehen aber an eine "
                        f"Regel mit Vorrang.")
    if wirkung["eigen"]:
        hinweise.append(f"{wirkung['eigen']} Buchungen mit eigener Entscheidung "
                        "bleiben, wie sie sind.")
    return Pruefung("/api/regeln", body, f"Neue Regel „{e['name']}“", zeilen, hinweise)


def _klammern() -> list[dict]:
    from finctl.web.routen.planung import _read_szenarien

    return list((_read_szenarien().get("szenarien")) or [])


def _planzeile(felder: dict, c: sqlite3.Connection) -> Pruefung:
    from finctl.web.routen.planung import neue_planzeile

    ziel = str(felder.get("szenario") or "").strip()
    if not ziel:
        raise ValueError("Klammer fehlt")
    _betrag(felder.get("amount_cents"), "amount_cents")
    klammer = next((k for k in _klammern() if k.get("id") == ziel
                    or str(k.get("name", "")).strip().lower() == ziel.lower()), None)
    eintrag = neue_planzeile(felder, str(klammer.get("id") if klammer else ""))
    zeilen = [("Klammer", ziel), ("Bezeichnung", eintrag["label"]), ("Art", eintrag["art"])]
    if eintrag["art"] != "wegfall":
        zeilen.append(("Betrag", f"{_euro(eintrag['amount_cents'])} {eintrag['frequenz']}"))
    zeilen += [("Kategorie", eintrag["kategorie"]), ("ab", eintrag["start"])]
    zeilen += [(n, str(eintrag[k])) for n, k in (("bis", "ende"), ("Konto", "konto"))
               if k in eintrag]
    hinweise = []
    if klammer is None:
        hinweise.append(f"Die Klammer „{ziel}“ gibt es noch nicht; sie wird angelegt "
                        "und ist eingeschaltet.")
    elif not klammer.get("aktiv"):
        hinweise.append(f"Die Klammer „{klammer.get('name') or ziel}“ ist ausgeschaltet; "
                        "die Zeile zählt erst, wenn du sie einschaltest.")
    return Pruefung("/api/szenario-zeile", dict(felder), f"Neue Planzeile „{eintrag['label']}“",
                    zeilen, hinweise)


def _kredit(felder: dict, c: sqlite3.Connection) -> Pruefung:
    from finctl import kredite as _kr
    from finctl.web.basis import lies_texte

    gelesen = lies_texte(dict(felder), KREDIT_TEXT)
    kredit = _kr.neuer_kredit(gelesen, _kr.lesen())
    if not c.execute("SELECT 1 FROM accounts WHERE id = ?",
                     (kredit["servicing_account_id"],)).fetchone():
        raise ValueError(f"Kein Konto „{kredit['servicing_account_id']}“")
    seg = kredit["segments"][0]
    zeilen = [("Kennung", kredit["id"]), ("Name", kredit["name"]),
              ("Gläubiger", kredit["lender"]), ("Konto der Rate", kredit["servicing_account_id"]),
              ("Restschuld", _euro(seg["opening_balance_cents"])),
              ("Monatsrate", _euro(seg["annuity_cents"])),
              ("Zins", f"{seg['annual_rate_pct']} % im Jahr"),
              ("Laufzeit", f"{seg['start']} bis {seg['end']}")]
    return Pruefung("/api/kredit-neu", dict(felder), f"Neuer Kredit „{kredit['name']}“", zeilen)


def _notiz(felder: dict, c: sqlite3.Connection) -> Pruefung:
    ort, kennung = str(felder.get("ort") or ""), str(felder.get("id") or "").strip()
    text = _notizen.eingabe(felder.get("notiz"))
    if ort not in ("ziel", "konto"):
        raise ValueError("ort: ziel oder konto")
    if not kennung:
        raise ValueError("id fehlt")
    if not text.strip():
        raise ValueError("Die Notiz ist leer")
    if ort == "ziel":
        from finctl.web.routen.ziele import _ID_FEHLER

        if _ID_FEHLER.get(kennung):
            raise ValueError(_ID_FEHLER[kennung])
        pfad = pfade.CONFIG_DIR / "goals.yaml"
        ziele = ((yaml_lesen(pfad) or {}) if pfad.exists() else {}).get("ziele") or []
        eintrag = next((g for g in ziele if isinstance(g, dict) and str(g.get("id")) == kennung),
                       None)
        if eintrag is None:
            raise ValueError(f"unbekanntes Ziel {kennung}")
        route, body, wo = "/api/ziel", {"id": kennung, "notiz": text}, "Ziel"
    else:
        from finctl import kontenregeln as _kr

        if not c.execute("SELECT 1 FROM accounts WHERE id = ?", (kennung,)).fetchone():
            raise ValueError(f"Kein Konto „{kennung}“")
        eintrag = _kr.wirksam()["account_roles"].get(kennung) or {}
        route, body, wo = f"/api/konto/{kennung}", {"note": text}, "Konto"
    bisher = _notizen.lesen(eintrag, ("note",))
    if text.strip() == bisher.text.strip():
        raise ValueError("Die Notiz steht schon so da.")
    zeilen = [(wo, kennung), ("Bisher", bisher.text or "keine Notiz"), ("Neu", text)]
    return Pruefung(route, body, f"Notiz am {wo} „{kennung}“", zeilen)


# ---------------------------------------------------------------- Anzeige

def _mit_pruefung(v: Vorschlag, c: sqlite3.Connection) -> dict:
    """Der Vorschlag fuer die Seite: Pruefung heute, oder die Meldung, warum er nicht mehr geht."""
    try:
        p, fehler = pruefen(v.art, v.felder, c), ""
    except (ValueError, yaml.YAMLError) as e:
        p, fehler = None, str(e)
    return {"id": v.id, "art": ARTEN[v.art].name, "warum": v.warum, "angelegt": v.angelegt,
            "pruefung": p, "fehler": fehler}


def fuer_seite(c: sqlite3.Connection) -> list[dict]:
    return [_mit_pruefung(v, c) for v in alle()]
