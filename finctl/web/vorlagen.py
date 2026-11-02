"""Die Kopiervorlage: ein Text, den der Haushalt selbst in ein Modell seiner Wahl einfuegt.

ADR 0002, erste Stufe. Die App ruft kein Modell auf und schickt nichts; sie
legt einen Text bereit und liest die eingefuegte Antwort. Eine Vorlage hat
drei Teile:

* BEGRIFFE: nur die Eintraege aus `CONTEXT.md`, die die Lage benutzt, damit das
  Modell dieselben Woerter spricht wie die App.
* LAGE: die Zahlen und Eintraege, die die Frage braucht, aus denselben
  Funktionen wie die Seiten. Kein Rohtext eines Auszugs, keine Nummer.
  Gegenparteien stehen nur in der Vorlage, die sie braucht (Einordnen), und
  nur bereinigt und nur, was der Haushalt angehakt laesst.
* FRAGE: mit der Form der Antwort, die die App wieder einliest.

Die Antwort ist ein Vorschlag. Nur Einordnen liefert einen, den sich der
Haushalt als Regel uebernehmen kann (ueber `rules/vorschlaege.py`); die
beiden anderen Vorlagen liefern eine Erklaerung, deren Kennungen und Betraege
die App gegen die Lage haelt. Geschrieben wird nie hier.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from finctl.rules import vorschlaege as vs
from finctl.web.basis import euro

#: Das Glossar gehoert zum CODE und liegt wie das Handbuch an zwei Orten:
#: im Repository an der Wurzel, im Paket als Kopie (`tests/test_paket.py`).
_IM_REPO = Path(__file__).resolve().parent.parent.parent / "CONTEXT.md"
_IM_PAKET = Path(__file__).resolve().parent.parent / "CONTEXT.md"
PFAD = next((p for p in (_IM_REPO, _IM_PAKET) if p.exists()), Path("CONTEXT.md"))

#: Die Vorlagen in der Reihenfolge der Reiter: Kennung, Name, die Begriffe der Lage.
ARTEN: dict[str, tuple[str, tuple[str, ...]]] = {
    "einordnen": ("Buchungen einordnen",
                  ("Buchung", "Gegenpartei", "Kategorie", "Regel", "Handentscheidung")),
    "monat": ("Monat erklären",
              ("Monatsabschluss", "Auszug", "Stand", "Belegter Stand", "Getippter Stand",
               "Kategorie", "Umbuchung")),
    "prognose": ("Frage zur Prognose",
                 ("Kontoprognose", "Monatsmodell", "Jahresrechnung", "Tiefpunkt",
                  "Untergrenze", "Deckel", "Annahme", "Fortschreibung", "Messfenster")),
}

#: Die Form, in der Erklaerung und Prognoseantwort kommen; `erklaerung_lesen`
#: liest genau sie.
ERKLAERFORM = [
    "Antworte NUR in dieser Form, auf Deutsch, in den Begriffen oben:",
    "ZUSAMMENFASSUNG: ein bis drei Sätze",
    "AUFFÄLLIG: Kennung aus der Lage ; ein Satz dazu",
    "",
    "Regeln:",
    "- AUFFÄLLIG darf mehrmals stehen, jeweils mit genau einer Kennung aus der Lage.",
    "- Nenne nur Beträge, die in der Lage stehen. Rechne keine neuen aus.",
    "- Reicht die Lage für die Frage nicht, sag in der Zusammenfassung, was fehlt.",
]

#: Wie lang die eigene Frage des Haushalts sein darf.
FRAGE_MAX = 500


# ------------------------------------------------------------------ Begriffe

def glossar() -> dict[str, dict]:
    """Die Eintraege von `CONTEXT.md`: Name -> Erklaerung und die Woerter, die man meidet."""
    out = {}
    for block in re.split(r"\n\s*\n", PFAD.read_text(encoding="utf-8")):
        treffer = re.match(r"\*\*(.+?)\*\*:\s*\n(.*)", block.strip(), re.S)
        if not treffer:
            continue
        rest = treffer.group(2)
        meide = re.search(r"\n_Avoid_:\s*(.*)$", rest, re.S)
        text = rest[:meide.start()] if meide else rest
        out[treffer.group(1)] = {
            "text": " ".join(text.split()),
            "meide": " ".join(meide.group(1).split()) if meide else ""}
    return out


def begriffe(namen: tuple[str, ...]) -> list[str]:
    """Die Zeilen des Abschnitts Begriffe; ein Name ohne Eintrag ist ein Fehler im Code."""
    g = glossar()
    fehlt = [n for n in namen if n not in g]
    if fehlt:
        raise KeyError(f"Begriff nicht in CONTEXT.md: {', '.join(fehlt)}")
    zeilen = ["Die App benutzt diese Wörter. Benutze sie auch in deiner Antwort."]
    for n in namen:
        meide = f" (Nicht: {g[n]['meide'].replace('_', '')})" if g[n]["meide"] else ""
        zeilen.append(f"- {n}: {g[n]['text']}{meide}")
    return zeilen


# ------------------------------------------------------------------- Vorlage

@dataclass(slots=True)
class Vorlage:
    art: str
    titel: str
    begriffe: list[str]
    lage: list[str]
    frage: list[str]
    #: Was eine Antwort als Kennung nennen darf (Kategorien, Konten, Jahre).
    kennungen: set[str] = field(default_factory=set)

    @property
    def text(self) -> str:
        return "\n".join(["# Begriffe", *self.begriffe, "", "# Lage", *self.lage,
                          "", "# Frage", *self.frage])


def _sauber(text: object) -> str:
    """Ein Name aus `config/` ohne alles, was eine Nummer ist."""
    return vs.bereinigt(text)


#: Eine IBAN oder eine lange Ziffernfolge (Konto-, Vertrags-, Kreditnummer).
_NUMMER = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,4})?\b|\d{9,}")


def _ohne_nummern(zeilen: list[str]) -> list[str]:
    """Letzte Sperre: was wie eine IBAN oder lange Nummer aussieht, geht nie hinaus."""
    return [_NUMMER.sub("…", z) for z in zeilen]


def _monat_ok(wert: str) -> str:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", wert or ""):
        raise ValueError("Der Monat steht als JJJJ-MM, zum Beispiel 2026-09.")
    return wert


def vormonat(heute: date) -> str:
    return f"{heute.year - 1}-12" if heute.month == 1 else f"{heute.year}-{heute.month - 1:02d}"


def bauen(art: str, c: sqlite3.Connection, *, heute: date | None = None, monat: str = "",
          frage: str = "", texte: list[str] | None = None) -> Vorlage:
    """Die Vorlage zu einer Art. `ValueError` mit einem Satz, wo die Eingabe nicht passt."""
    if art not in ARTEN:
        raise ValueError("Diese Vorlage gibt es nicht.")
    heute = heute or date.today()
    titel, namen = ARTEN[art]
    if art == "einordnen":
        lage, frage_zeilen, kennungen = _einordnen(c, texte)
    elif art == "monat":
        lage, kennungen = _monat(c, heute, _monat_ok(monat or vormonat(heute)))
        frage_zeilen = [("Was fällt in diesem Monat gegenüber dem Schnitt auf, und was ist "
                         "im Monatsabschluss noch offen?"), "", *ERKLAERFORM]
    else:
        frage = " ".join((frage or "").split())[:FRAGE_MAX]
        lage, kennungen = _prognose(c)
        frage_zeilen = [frage or "Reichen die Konten, und was ist der größte Risikopunkt?",
                        "", *ERKLAERFORM]
    return Vorlage(art, titel, begriffe(namen), _ohne_nummern(lage), frage_zeilen, kennungen)


# ----------------------------------------------------------------- Einordnen

def einordnen_texte(c: sqlite3.Connection) -> list[dict]:
    """Die bereinigten Texte der offenen Buchungen, wie sie die Seite zum Abwaehlen zeigt."""
    return vs.offene_texte(c)


def _einordnen(c: sqlite3.Connection, texte: list[str] | None):
    from finctl.rules import regelwerk as rw
    from finctl.web.basis import categories

    angeboten = [z["text"] for z in vs.offene_texte(c)]
    # Nur, was die Seite selbst bereinigt angeboten hat: ein Text von aussen
    # (eine IBAN, ein Rohtext) kommt nicht in die Vorlage.
    gewaehlt = angeboten if texte is None else [t for t in texte if t in set(angeboten)]
    if not gewaehlt:
        raise ValueError("Kein Text gewählt." if angeboten else "Keine offenen Buchungen.")
    regeln_je: dict[str, int] = {}
    for e in rw.laden():
        mgmt = (e.get("set") or {}).get("mgmt")
        if mgmt:
            regeln_je[mgmt] = regeln_je.get(mgmt, 0) + 1
    kats = categories(c)
    return vs.lage(kats, gewaehlt, regeln_je), vs.FRAGE, {k["id"] for k in kats}


# --------------------------------------------------------------------- Monat

def offene_posten(c: sqlite3.Connection, heute: date) -> list:
    """Was der Monatsabschluss noch offen sieht, aus denselben Funktionen wie die Seite."""
    from finctl import bestaende as best
    from finctl import monatsabschluss as ma
    from finctl.dateien import yaml_lesen
    from finctl.pfade import CONFIG_DIR

    balances = best.zusammenfuehren(c, yaml_lesen(CONFIG_DIR / "balances.yaml") or {})["balances"]
    geparst = {r[0] for r in c.execute("SELECT id FROM accounts WHERE ingest_mode = 'parsed'")}
    periode = f"{heute:%Y-%m}"
    posten = (ma.konten(c, heute, periode, balances)
              + ma.bestaende(balances, heute, periode, f"{heute:%Y}", geparst))
    return [p for p in posten if not p.erledigt]


def _monat(c: sqlite3.Connection, heute: date, monat: str):
    from finctl.web.routen.auswertung import _je_monat

    jahr, mm = monat.split("-")
    # Die zwoelf Monate davor, aus denen der Schnitt kommt.
    davor = []
    j, m = int(jahr), int(mm)
    for _ in range(12):
        m -= 1
        if m == 0:
            j, m = j - 1, 12
        davor.append((f"{j:04d}", f"{m:02d}"))
    je_ober: dict[str, dict] = {}
    for z in _je_monat(c, "laufend").values():
        name = "ohne Kategorie" if z["parent_id"] == "__none__" else _sauber(z["parent"])
        o = je_ober.setdefault(name, {"monat": 0, "davor": 0})
        o["monat"] += z["je_monat"].get((jahr, mm), 0) or 0
        o["davor"] += sum(z["je_monat"].get(k, 0) or 0 for k in davor)
    zeilen = [(n, o["monat"], o["davor"] // 12) for n, o in je_ober.items()
              if o["monat"] or o["davor"]]
    zeilen.sort(key=lambda r: -max(abs(r[1]), abs(r[2])))
    rein = sum(m for _n, m, _s in zeilen if m > 0)
    raus = sum(m for _n, m, _s in zeilen if m < 0)

    lage = [f"Monat: {monat}",
            "Einnahmen und Ausgaben je Oberkategorie, ohne Umbuchungen und Kapitalbewegungen.",
            "Betrag im Monat, Schnitt der zwölf Monate davor (negativ = raus):"]
    lage += [f"- {n}: {euro(m)}, Schnitt {euro(s)}" for n, m, s in zeilen[:25]]
    lage += [f"Einnahmen im Monat: {euro(rein)}", f"Ausgaben im Monat: {euro(raus)}"]
    if not zeilen:
        lage.append("In diesem Monat und davor gibt es keine Buchungen.")
    lage.append(f"Buchungen ohne Kategorie: "
                f"{c.execute('SELECT COUNT(*) FROM v_review_queue').fetchone()[0]}")

    offen = offene_posten(c, heute)
    lage.append("Im Monatsabschluss offen:" if offen else "Im Monatsabschluss ist nichts offen.")
    lage += [f"- {_sauber(p.name)}: {p.hinweis or 'Stand erneuern'}" for p in offen]
    return lage, {n for n, _m, _s in zeilen} | {_sauber(p.name) for p in offen}


# ------------------------------------------------------------------ Prognose

def _prozent(anteil: float) -> str:
    return f"{anteil * 100:.1f}".replace(".", ",") + " %"


def _konten_lage(c: sqlite3.Connection, kennungen: set[str]) -> list[str]:
    from finctl import ops

    lage = ["Kontoprognose, die nächsten zwölf Monate (Stand, Grenzen, Tiefpunkt):"]
    for v in ops.household_accounts(c, months=12):
        kennungen.add(v["id"])
        zeile = [(f"- {v['id']} ({v.get('role') or 'ohne Rolle'}): "
                  f"Stand {euro(v['opening_cents'])} am {v['opening_as_of']}")]
        for name, schluessel in (("Untergrenze", "regel_untergrenze_cents"),
                                 ("Deckel", "ceiling_cents")):
            if v.get(schluessel) is not None:
                zeile.append(f"{name} {euro(v[schluessel])}")
        if v.get("worst_month"):
            zeile.append(f"tiefster Stand {euro(v['worst_trough_cents'])} "
                         f"im {v['worst_month'][:7]}")
        if v.get("breach_months"):
            monate = v["breach_months"]
            zeile.append(f"unter der Grenze: {len(monate)} Monate, "
                         f"{monate[0][:7]} bis {monate[-1][:7]}")
        lage.append("; ".join(zeile))
    return lage


def _jahre_lage(kennungen: set[str]) -> list[str]:
    from finctl.web.routen.annahmen import _jahresrechnung

    lauf, tabelle, _namen, _fenster = _jahresrechnung("schnitt")
    # Die ersten zehn Jahre und danach alle fuenf: die Form der Kurve, nicht jede Zeile.
    zeilen = [r for i, r in enumerate(tabelle) if i < 10 or i % 5 == 0 or r is tabelle[-1]]
    kennungen |= {str(r["jahr"]) for r in zeilen}
    lage = ["Jahresrechnung, Vermögen zum Jahresende (Hochrechnung):"]
    lage += [f"- {r['jahr']}: {euro(r['schluss'])}" for r in zeilen]
    lage.append(f"Das Vermögen reicht bis {lauf.reicht_bis}." if lauf.reicht_bis
                else "Das Vermögen reicht bis zum Ende der Rechnung.")
    return lage


def _annahmen_lage(kennungen: set[str]) -> list[str]:
    from finctl import assumptions as ann

    try:
        zeilen = ["Annahmen:",
                  f"- Inflation: {_prozent(ann.inflation_pa())} im Jahr",
                  f"- Rendite nominal: {_prozent(ann.rendite_nominal_pa())} im Jahr",
                  f"- Rendite Depot: {_prozent(ann.rendite_depot_pa())} im Jahr",
                  f"- Gehaltssteigerung: {_prozent(ann.salary_growth_pa())} im Jahr"]
    except FileNotFoundError:
        return []
    kennungen.add("Annahmen")
    return zeilen


def _prognose(c: sqlite3.Connection):
    from finctl import module

    kennungen: set[str] = set()
    teile = []
    if module.seite_an("/konten"):
        teile.append(_konten_lage(c, kennungen))
    if module.seite_an("/hochrechnung"):
        teile.append(_jahre_lage(kennungen))
    teile.append(_annahmen_lage(kennungen))
    lage: list[str] = []
    for teil in (t for t in teile if t):
        lage += ([""] if lage else []) + teil
    return lage or ["Die Prognose ist in diesem Haushalt nicht eingeschaltet."], kennungen


# ------------------------------------------------------------------- Antwort

@dataclass(slots=True)
class Erklaerung:
    zusammenfassung: str
    #: (Kennung, Satz, steht die Kennung in der Lage)
    auffaellig: list[tuple[str, str, bool]]
    #: Betraege der Antwort, die in der Lage nicht stehen.
    fremde_betraege: list[str]


_KOPF = re.compile(r"^(ZUSAMMENFASSUNG|AUFF(?:Ä|AE)LLIG)\s*:\s*(.*)$", re.I)
_BETRAG = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")


def erklaerung_lesen(antwort: str, v: Vorlage) -> Erklaerung:
    """Die Antwort in der Form von ERKLAERFORM. `ValueError` sagt, was fehlt."""
    zusammen: list[str] = []
    auffaellig: list[tuple[str, str, bool]] = []
    aktuell = None
    kennungen = {k.lower() for k in v.kennungen}
    for zeile in str(antwort or "").splitlines():
        bereinigt = zeile.strip().lstrip("-*#> ").replace("**", "").strip()
        kopf = _KOPF.match(bereinigt)
        if kopf and kopf.group(1).upper().startswith("ZUSAMMEN"):
            aktuell = "z"
            zusammen = [kopf.group(2).strip()]
        elif kopf:
            aktuell = "a"
            kennung, _, satz = kopf.group(2).partition(";")
            kennung = kennung.strip().strip("`\"'„“")
            auffaellig.append((kennung, satz.strip(), kennung.lower() in kennungen))
        elif aktuell == "z" and bereinigt:
            zusammen.append(bereinigt)
    text = " ".join(t for t in zusammen if t)
    if not text:
        raise ValueError("Keine Zeile der Form „ZUSAMMENFASSUNG: …“ gefunden. "
                         "Bitte das Modell, genau die Form der Frage zu benutzen.")
    gesehen = set(_BETRAG.findall("\n".join(v.lage)))
    gesagt = _BETRAG.findall(text + " " + " ".join(s for _k, s, _b in auffaellig))
    return Erklaerung(text, auffaellig, sorted({b for b in gesagt if b not in gesehen}))
