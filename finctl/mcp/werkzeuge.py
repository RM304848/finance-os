"""Was ein Modell ueber MCP lesen darf, und der eine Weg zu schreiben: `vorschlagen`.

LESEN geht ueber die Funktionen, aus denen die Seiten rechnen (Kontoprognose,
Jahresrechnung, Fortschreibung, Karten der Ziele ...), nie ueber SQL. Ein Modell
sieht damit dieselben Zahlen wie der Haushalt, und eine Seite, die sich aendert,
aendert das Werkzeug mit. Jede Antwort geht durch dieselbe Sperre wie die
Kopiervorlagen (`vorlagen._ohne_nummern`): keine IBAN, keine lange Nummer, und
Buchungstexte nur bereinigt.

SCHREIBEN gibt es nicht. `vorschlagen` legt eine Datei in `data/vorschlaege/` ab
(`web/vorschlaege.py`); der Haushalt bestaetigt sie in der App.

Notizen stehen in keiner Antwort: Sie tragen alles Persoenliche. Ob ein Modell sie
lesen darf, ist eine Entscheidung des Haushalts und noch keine getroffen.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from finctl.web import vorlagen as _vl
from finctl.web import vorschlaege as _vs


@dataclass(frozen=True, slots=True)
class Werkzeug:
    name: str
    beschreibung: str
    funktion: Callable[[dict, object], list[str]]
    #: Name -> (Typ, Beschreibung, Pflicht)
    parameter: dict[str, tuple[str, str, bool]] = field(default_factory=dict)
    schema_zusatz: dict = field(default_factory=dict)

    def als_dict(self) -> dict:
        schema = {"type": "object",
                  "properties": {n: {"type": t, "description": b}
                                 for n, (t, b, _p) in self.parameter.items()},
                  "required": [n for n, (_t, _b, pflicht) in self.parameter.items() if pflicht]}
        for name, zusatz in self.schema_zusatz.items():
            schema["properties"][name].update(zusatz)
        return {"name": self.name, "description": self.beschreibung, "inputSchema": schema}


@dataclass(frozen=True, slots=True)
class Ressource:
    uri: str
    name: str
    beschreibung: str
    lesen: Callable[[], str]

    def als_dict(self) -> dict:
        return {"uri": self.uri, "name": self.name, "description": self.beschreibung,
                "mimeType": "text/markdown"}


def _euro(cents: object) -> str:
    from finctl.web.basis import euro

    return euro(cents if isinstance(cents, int) else 0)


def _sauber(text: object) -> str:
    return _vl._sauber(text)


def _seite(*pfade: str) -> bool:
    from finctl import module

    return module.seite_an(*pfade)


NICHT_AN = "Diese Seite ist in diesem Haushalt nicht eingeschaltet."


# --------------------------------------------------------------------- Lesen

def _konten(args: dict, c) -> list[str]:
    return _vl._konten_lage(c, set()) if _seite("/konten") else [NICHT_AN]


def _jahresrechnung(args: dict, c) -> list[str]:
    return _vl._jahre_lage(set()) if _seite("/hochrechnung") else [NICHT_AN]


def _annahmen(args: dict, c) -> list[str]:
    return _vl._annahmen_lage(set()) or ["Es sind keine Annahmen eingetragen."]


def _fortschreibung(args: dict, c) -> list[str]:
    from finctl.web.routen.annahmen import fortschreibung_seite

    if not _seite("/prognosebasis"):
        return [NICHT_AN]
    seite = fortschreibung_seite(c)
    zeilen = [f"Messfenster: {seite.fenster}",
              ("Fortschreibung je Block: Monat (Kontoprognose) / Jahr (Jahresrechnung), "
               "mit der Quelle (negativ = raus):")]
    for z in seite.zeilen:
        monat = "—" if z.monat_cents is None else f"{_euro(z.monat_cents)} ({z.quelle_monat})"
        jahr = "—" if z.jahr_cents is None else f"{_euro(z.jahr_cents)} ({z.quelle_jahr})"
        zeilen.append(f"- {_sauber(z.name)}: Monat {monat}; Jahr {jahr}")
    return zeilen


def _buchungen(args: dict, c) -> list[str]:
    from finctl.web.routen.buchungen import api_buchungen_suche

    q, kategorie = str(args.get("text") or ""), str(args.get("kategorie") or "")
    if len(q.strip()) < 2 and not kategorie.strip():
        raise ValueError("Gib einen Suchtext (mindestens zwei Zeichen) oder eine Kategorie an.")
    try:
        limit = int(args.get("limit") or 50)
    except (TypeError, ValueError):
        raise ValueError("limit ist eine ganze Zahl") from None
    zeilen = api_buchungen_suche(q=q, kategorie=kategorie, limit=min(max(limit, 1), 200),
                                 zid="", ausser=[])["rows"]
    out = [f"{len(zeilen)} Buchungen (neueste zuerst, höchstens 200; Texte bereinigt):"]
    out += [f"- {z['booking_date']} · {z['account_id']} · {_euro(z['amount_cents'])} · "
            f"{z['kategorie'] or 'ohne Kategorie'} · {_vs_text(z['text'])}" for z in zeilen]
    return out


def _vs_text(text: object) -> str:
    from finctl.rules import vorschlaege as vs

    return vs.bereinigt(text)


def _kategorien(args: dict, c) -> list[str]:
    from finctl.web.basis import categories

    return ["Kategorien (Kennung: Oberkategorie / Name):",
            *[f"- {k['id']}: {_sauber(k['label'])}" for k in categories(c)]]


def _vertraege(args: dict, c) -> list[str]:
    from finctl import abos

    if not _seite("/vertraege"):
        return [NICHT_AN]
    zeilen = ["Verträge (Betrag je Termin, negativ = raus; Takt in Monaten):"]
    for a in abos.alle_vertraege():
        extra = "".join([f"; gekündigt zum {a['gekuendigt_zum']}" if a["gekuendigt_zum"] else "",
                         f"; bezahlt bis {a['vorrat_bis']}" if a["vorrat_bis"] else ""])
        zeilen.append(f"- {a['id']} ({_sauber(a['name'])}): {_euro(a['betrag_cents'])} alle "
                      f"{a['takt']} Monate, fällig {a['faellig']}, Kategorie {a['kategorie']}, "
                      f"Konto {a['konto']}{extra}")
    return zeilen if len(zeilen) > 1 else [*zeilen, "Keine Verträge eingetragen."]


def _klammern(args: dict, c) -> list[str]:
    if not _seite("/planung"):
        return [NICHT_AN]
    zeilen = ["Klammern mit ihren Planzeilen (Betrag negativ = raus):"]
    for k in _vs._klammern():
        zeilen.append(f"- Klammer {k.get('id')} ({_sauber(k.get('name'))}): "
                      f"{'an' if k.get('aktiv') else 'aus'}"
                      f"{', Verpflichtung' if k.get('pflicht') else ''}")
        for i, z in enumerate(k.get("zeilen") or []):
            betrag = _euro(z.get("amount_cents")) if z.get("art") in ("betrag", "erwartet") else "—"
            zeilen.append(f"  - [{i}] {_sauber(z.get('label'))}: {z.get('art')}, {betrag} "
                          f"{z.get('frequenz', '')}, ab {z.get('start', '—')}"
                          f"{', bis ' + str(z['ende']) if z.get('ende') else ''}, "
                          f"Kategorie {z.get('kategorie', '—')}")
    return zeilen if len(zeilen) > 1 else [*zeilen, "Keine Klammern angelegt."]


def _kredite(args: dict, c) -> list[str]:
    from finctl import kredite

    if not _seite("/kredite"):
        return [NICHT_AN]
    zeilen = ["Kredite:"]
    for k in kredite.lesen().get("loans") or []:
        if not isinstance(k, dict):
            continue
        segmente = [s for s in k.get("segments") or [] if isinstance(s, dict)]
        kond = "; ".join(f"{s.get('start')} bis {s.get('end')}: Zins {s.get('annual_rate_pct')} %, "
                         f"Rate {_euro(s.get('annuity_cents'))}" for s in segmente)
        zeilen.append(f"- {k.get('id')} ({_sauber(k.get('name'))}), Konto "
                      f"{k.get('servicing_account_id')}, Status {k.get('status')}"
                      f"{': ' + kond if kond else ''}")
    return zeilen if len(zeilen) > 1 else [*zeilen, "Keine Kredite eingetragen."]


def _objekte(args: dict, c) -> list[str]:
    from finctl import objekte

    if not _seite("/immobilien"):
        return [NICHT_AN]
    zeilen = ["Objekte (ohne Anschrift):"]
    for kennung, o in objekte.vorhandene().items():
        zeilen.append(f"- {kennung} ({_sauber(o.get('name'))}), Status {o.get('status', '—')}, "
                      f"erworben {o.get('acquired_on', '—')}")
    return zeilen if len(zeilen) > 1 else [*zeilen, "Keine Objekte eingetragen."]


def _ziele(args: dict, c) -> list[str]:
    from finctl.web.routen.ziele import ziele_kontext

    if not _seite("/ziele"):
        return [NICHT_AN]
    k = ziele_kontext()
    zeilen = ["Ziele (Stand heute und erwarteter Stand am Stichdatum):"]
    for t in k["targets"]:
        pro = f", erwartet {_euro(t['projiziert'])}" if t.get("projiziert") is not None else ""
        zeilen.append(f"- {t['id']} ({_sauber(t['name'])}): Ziel {_euro(t['target'])}, "
                      f"da {_euro(t['have'])} ({t['pct']:.0f} %), Stichdatum "
                      f"{t['due'] or 'ohne'}{pro}")
    return zeilen


def _offene_punkte(args: dict, c) -> list[str]:
    offen = _vl.offene_posten(c, date.today())
    n = c.execute("SELECT COUNT(*) FROM v_review_queue").fetchone()[0]
    zeilen = [f"Buchungen ohne Kategorie: {n}",
              "Im Monatsabschluss offen:" if offen else "Im Monatsabschluss ist nichts offen."]
    return zeilen + [f"- {_sauber(p.name)}: {p.hinweis or 'Stand erneuern'}" for p in offen]


# ------------------------------------------------------------------ Vorschlagen

def _vorschlagen(args: dict, c) -> list[str]:
    art = str(args.get("art") or "")
    v = _vs.ablegen(art, args.get("felder"), str(args.get("warum") or ""), c)
    p = _vs.pruefen(v.art, v.felder, c)
    return [f"Vorschlag abgelegt: {p.titel}.",
            ("Er ist noch keine Entscheidung. Der Haushalt sieht ihn unter /vorschlaege in der "
             "App und übernimmt oder verwirft ihn dort."), *p.hinweise]


def _beschreibung_vorschlagen() -> str:
    arten = " ".join(f"[{a.kennung}] {a.beschreibung} Felder: {', '.join(a.felder)}."
                     for a in _vs.ARTEN.values())
    return ("Schlägt dem Haushalt eine Handentscheidung vor. Schreibt nichts in seine "
            "Dateien: der Vorschlag wird geprüft (wie die Seite ihn prüft) und abgelegt, der "
            "Haushalt bestätigt ihn in der App. Eine ungültige Eingabe kommt mit der Meldung "
            "der Seite zurück. " + arten)


WERKZEUGE: dict[str, Werkzeug] = {w.name: w for w in (
    Werkzeug("konten", "Konten mit Kontoprognose: Stand, Grenzen, Tiefpunkt, die nächsten "
             "zwölf Monate.", _konten),
    Werkzeug("jahresrechnung", "Vermögen je Jahr bis zum Ende der Rechnung (Hochrechnung).",
             _jahresrechnung),
    Werkzeug("annahmen", "Inflation, Rendite und Gehaltssteigerung, mit denen gerechnet wird.",
             _annahmen),
    Werkzeug("fortschreibung", "Woraus Kontoprognose und Jahresrechnung fortschreiben: je Block "
             "Betrag und Quelle.", _fortschreibung),
    Werkzeug("buchungen_suchen", "Buchungen nach Text und/oder Kategorie, höchstens 200, neueste "
             "zuerst. Texte sind bereinigt, ohne IBAN und Nummern.", _buchungen,
             {"text": ("string", "Suchtext, mindestens zwei Zeichen.", False),
              "kategorie": ("string", "Kennung aus `kategorien`.", False),
              "limit": ("integer", "Wie viele Zeilen, höchstens 200 (Standard 50).", False)}),
    Werkzeug("kategorien", "Die Kategorien, die eine Buchung haben kann (Kennung und Name).",
             _kategorien),
    Werkzeug("vertraege", "Verträge: Betrag, Takt, Fälligkeit, Kündigung.", _vertraege),
    Werkzeug("klammern", "Klammern mit ihren Planzeilen und ob sie eingeschaltet sind.",
             _klammern),
    Werkzeug("kredite", "Kredite mit Konto, Zins und Rate.", _kredite),
    Werkzeug("objekte", "Objekte (Immobilien) ohne Anschrift.", _objekte),
    Werkzeug("ziele", "Ziele mit Stand heute und erwartetem Stand am Stichdatum.", _ziele),
    Werkzeug("offene_punkte", "Was im Monatsabschluss offen ist und wie viele Buchungen noch "
             "keine Kategorie haben.", _offene_punkte),
    Werkzeug("vorschlagen", "", _vorschlagen,
             {"art": ("string", "Die Art des Vorschlags.", True),
              "felder": ("object", "Die Felder der Art.", True),
              "warum": ("string", "Ein Satz, warum du das vorschlägst; der Haushalt liest ihn.",
                        False)},
             {"art": {"enum": list(_vs.ARTEN)}}),
)}
# Die Beschreibung von `vorschlagen` haengt an den Arten; sie wird hier gesetzt, weil das
# Werkzeug erst mit ihnen vollstaendig ist.
WERKZEUGE["vorschlagen"] = Werkzeug(
    "vorschlagen", _beschreibung_vorschlagen(), _vorschlagen,
    WERKZEUGE["vorschlagen"].parameter, WERKZEUGE["vorschlagen"].schema_zusatz)


def aufrufen(name: str, args: dict) -> str:
    """Das Werkzeug ausfuehren und die Antwort durch die Sperre schicken.

    `ValueError` ist eine Meldung fuer das Modell (falsche Eingabe, abgelehnter Vorschlag).
    """
    from finctl.ledger.db import connect
    from finctl.pfade import DB_PATH

    if not DB_PATH.exists():
        raise ValueError("Es gibt noch kein Hauptbuch. In der App einrichten und Auszüge lesen.")
    c = connect()
    try:
        zeilen = WERKZEUGE[name].funktion(args, c)
    finally:
        c.close()
    return "\n".join(_vl._ohne_nummern(zeilen))


# -------------------------------------------------------------------- Ressourcen

def _glossar() -> str:
    return _vl.PFAD.read_text(encoding="utf-8")


RESSOURCEN: dict[str, Ressource] = {r.uri: r for r in (
    Ressource("finctl://glossar", "Glossar",
              "Die Begriffe der App (CONTEXT.md). Benutze diese Wörter.", _glossar),
)}
