"""Read config/assumptions.yaml -- the one place a guess is allowed to live.

Everything the forecast computes comes from here. The distinction the file
exists to draw: an ANNAHME is something somebody chose, a FAKT is something a
document says. A loan rate from a contract, an AfA base from a tax assessment,
a policy value from a Standmitteilung -- those stay in loans.yaml,
properties.yaml and lebensplan.yaml, where their derivation sits beside them.

A scenario is a copy of this file with different values. Not a feature, not a
table, not a screen.

Accessed through this module rather than by reading the YAML wherever it is
needed, so that there is exactly one answer to "what inflation rate is this
projection using". The previous arrangement had the figure implied in three
places -- goals.yaml, lebensplan.yaml and a nominal return that already had it
baked in -- and finctl/config_checks.py existed solely to notice when they
drifted apart.
"""

from __future__ import annotations

import copy
from datetime import date
from functools import lru_cache
from pathlib import Path

from finctl.dateien import yaml_lesen, yaml_schreiben
from finctl.pfade import CONFIG_DIR

PATH = CONFIG_DIR / "assumptions.yaml"


@lru_cache(maxsize=8)
def _load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"{path} fehlt. Ohne Annahmen kann nichts projiziert werden -- "
            f"eine leere Datei waere schlimmer, weil dann Vorgabewerte "
            f"rechnen wuerden, die niemand gewaehlt hat.")
    return yaml_lesen(p) or {}


#: Welche Annahmen sich im Dashboard drehen lassen, und wo sie in der Datei
#: stehen. Nur diese: es sind die, an denen der ganze Plan haengt und die
#: eine Meinung sind, keine Messung und keine Unterlage. Eine Standmitteilung
#: der GRV gehoert nicht in ein Eingabefeld, was ein Objekt abwirft, steht am
#: Objekt (`prognose:` in properties.yaml). Teilzeit hat beides: ihre Werte
#: sind eine Annahme und stehen hier, ob sie gilt, schaltet die Klammer
#: "Teilzeit" auf /planung.
UEBERSCHREIBBAR: dict[str, tuple[str, ...]] = {
    "inflation_pa": ("inflation_pa",),
    "rendite_nominal_pa": ("kapital", "rendite_nominal_pa"),
    "rendite_depot_pa": ("kapital", "rendite_depot_pa"),
    "sparerpauschbetrag_cents": ("kapital", "sparerpauschbetrag_cents"),
    "kostenschwelle_pa": ("kapital", "kostenschwelle_pa"),
    "steuersatz_kapital": ("kapital", "vorabpauschale", "steuersatz"),
    "basiszins_pa": ("kapital", "vorabpauschale", "basiszins_pa"),
    "gehalt_steigerung_pa": ("erwerbseinkommen", "gehalt_steigerung_pa"),
    "salary_floor_cents": ("erwerbseinkommen", "netto_floor_monatlich_cents"),
    "teilzeit_anteil": ("erwerbseinkommen", "teilzeit_anteil"),
    "teilzeit_ab": ("erwerbseinkommen", "teilzeit_ab"),
    "lebenserwartung": ("ruhestand", "lebenserwartung"),
    "abzug_renten": ("ruhestand", "abzug_renten"),
    "aufbrauchen": ("ruhestand", "aufbrauchen"),
}


def load(path: Path | str = PATH) -> dict:
    """Die ganze Datei, wie sie steht.

    Seit Schritt 5 (N.3f) steht in ihr auch, was im Dashboard gesetzt wird; vorher legte
    eine zweite Datei es beim Lesen darueber. Ein Szenario ist ein anderer Pfad und
    erbt nichts aus dieser Datei: Es beschreibt eine andere Welt.
    """
    return _load(str(path))


def in_datei(key: str, path: Path | str = PATH):
    """Was die Datei zu einer Stellschraube sagt.

    None, wo sie schweigt: eine frische Installation traegt nur die Startwerte, und die Seite
    soll sagen "nicht eingetragen", statt mit einem KeyError abzubrechen.
    """
    knoten = load(path)
    for teil in UEBERSCHREIBBAR[key]:
        if not isinstance(knoten, dict) or teil not in knoten:
            return None
        knoten = knoten[teil]
    return knoten


def wert(key: str, path: Path | str = PATH):
    """Was gilt: die Datei, sonst der Wert im Code (`VORGABEN`), sonst nichts.

    Fuer eine Stellschraube, die die Datei nicht nennt (die Kostenschwelle), gilt der Wert im
    Code -- und ein Feld, das ihn zeigt, darf beim Speichern keinen Eintrag erzeugen.
    """
    gelesen = in_datei(key, path)
    return VORGABEN.get(key) if gelesen is None else gelesen


def setzen(key: str, neu, path: Path | str = PATH) -> bool:
    """Eine Stellschraube in die Datei schreiben, an ihren Pfad; leer nimmt die Angabe heraus.

    Die Seite schreibt die ganze Datei (`dateien.yaml_schreiben`): Notizen und alles andere
    bleiben. Ein Wert, der schon so gilt, aendert nichts -- auch der Vorgabewert im Code, den
    die Seite zeigt, ohne dass die Datei ihn nennt. Gibt zurueck, ob die Datei sich aenderte.
    """
    pfad = Path(path)
    spec = copy.deepcopy(_load(str(pfad)))
    wege = UEBERSCHREIBBAR[key]
    leer = neu in (None, "")
    if leer and key not in OPTIONAL:
        raise ValueError("Ohne diesen Wert kann nichts gerechnet werden.")
    if not leer and in_datei(key, pfad) is None and str(neu) == str(VORGABEN.get(key)):
        return False
    knoten = spec
    for teil in wege[:-1]:
        if leer and not isinstance(knoten.get(teil), dict):
            return False
        knoten = knoten.setdefault(teil, {})
    if leer:
        knoten.pop(wege[-1], None)
    else:
        knoten[wege[-1]] = neu
    geaendert = yaml_schreiben(pfad, spec)
    reset_cache()
    return geaendert


def reset_cache() -> None:
    """Forget what was read. For tests and for a file edited while serving."""
    _load.cache_clear()


def get(*keys: str, path: Path | str = PATH, default=None):
    """One value, by its path through the file.

    Raises rather than returning None for a missing key without a stated
    default: a projection that silently falls back to zero inflation produces
    a confident, wrong answer, and nothing about the output would say so.
    """
    node = load(path)
    walked: list[str] = []
    for key in keys:
        walked.append(key)
        if not isinstance(node, dict) or key not in node:
            if default is not None:
                return default
            raise KeyError(
                f"{'.'.join(walked)} fehlt in {path}. Entweder eintragen oder "
                f"einen Vorgabewert angeben -- stillschweigend weiterrechnen "
                f"waere die schlechtere Antwort.")
        node = node[key]
    return node


def inflation_pa(path: Path | str = PATH) -> float:
    return float(get("inflation_pa", path=path))


def rendite_nominal_pa(path: Path | str = PATH) -> float:
    """Das Tagesgeld. Depot und Policen haben ihren eigenen Satz."""
    return float(get("kapital", "rendite_nominal_pa", path=path))


def rendite_depot_pa(path: Path | str = PATH) -> float:
    """Depot und fondsgebundene Policen, vor Steuern -- in der Ansparphase wird nicht verkauft."""
    return float(get("kapital", "rendite_depot_pa", path=path))


def vorabpauschale(path: Path | str = PATH) -> tuple[float, float]:
    """(Anteil des Depotwerts, der als Vorabpauschale gilt; Steuer je Euro davon).

    Die Vorabpauschale ist Depotwert mal Basiszins mal 0,7. Versteuert wird
    sie -- wie jeder Verkaufsgewinn -- voll mit dem Steuersatz: die
    Teilfreistellung fuer Aktienfonds rechnet die Prognose bewusst nicht,
    sie waere die freundlichere Annahme.
    """
    v = get("kapital", "vorabpauschale", path=path)
    return float(v["basiszins_pa"]) * 0.7, float(v["steuersatz"])



def salary_floor_cents(path: Path | str = PATH) -> int:
    """Der schlechteste beobachtete Monat: das Gehalt, mit dem beide Modelle rechnen.

    Vorsichtig mit Absicht. Der Median der Gehaltsmonate steht nur als Vergleich auf
    /annahmen (`jahre.gehalt_median_cents`).
    """
    return int(get("erwerbseinkommen", "netto_floor_monatlich_cents", path=path))


#: Ohne Eintrag: ab welchen Effektivkosten eine Police ein Warnzeichen traegt.
KOSTENSCHWELLE_VORGABE = 0.013

#: Der gesetzliche Sparerpauschbetrag fuer eine Person, in Cent. Wer zusammen
#: veranlagt wird, traegt den doppelten ein; aendert ihn das Gesetz, den neuen.
SPARERPAUSCHBETRAG_VORGABE = 100_000

#: Stellschrauben, die die Datei nicht nennen muss.
VORGABEN: dict[str, float] = {"kostenschwelle_pa": KOSTENSCHWELLE_VORGABE,
                              "sparerpauschbetrag_cents": SPARERPAUSCHBETRAG_VORGABE}

#: Stellschrauben, die die Datei auch ohne Eintrag verkraftet: die mit einem Wert im Code und die
#: Teilzeit, die nur rechnet, wo sie steht. Bei jeder anderen bricht die Rechnung ohne Wert ab.
OPTIONAL = frozenset({*VORGABEN, "teilzeit_anteil", "teilzeit_ab"})


def kostenschwelle_pa(path: Path | str = PATH) -> float:
    """Effektivkosten, ab denen eine Police markiert wird -- eine Meinung, keine Norm."""
    return float(get("kapital", "kostenschwelle_pa", path=path,
                     default=KOSTENSCHWELLE_VORGABE))


def sparerpauschbetrag_cents(path: Path | str = PATH) -> int:
    """Was an Kapitalertraegen im Jahr steuerfrei bleibt. Nominal fest, kein Wachstum."""
    return int(get("kapital", "sparerpauschbetrag_cents", path=path,
                   default=SPARERPAUSCHBETRAG_VORGABE))


def teilzeit_anteil(path: Path | str = PATH) -> float | None:
    """Der Anteil am vollen Gehalt in Teilzeit, 0,8 fuer 80 % -- oder None."""
    wert = get("erwerbseinkommen", "teilzeit_anteil", path=path, default="")
    return float(wert) if wert not in ("", None) else None


def teilzeit_ab(path: Path | str = PATH) -> date | None:
    """Der erste Monat in Teilzeit -- oder None, solange keiner eingetragen ist."""
    wert = str(get("erwerbseinkommen", "teilzeit_ab", path=path, default="") or "")
    if not wert:
        return None
    try:
        return date.fromisoformat(wert[:7] + "-01")
    except ValueError:
        return None


def salary_growth_pa(path: Path | str = PATH) -> float:
    """Wie schnell das Gehalt steigt -- nicht zwingend wie die Inflation."""
    return float(get("erwerbseinkommen", "gehalt_steigerung_pa",
                     path=path, default=inflation_pa(path)))


def grow(cents: int, years: float, rate: float) -> int:
    """Einen Betrag mit einer beliebigen Rate fortschreiben."""
    return int(round(cents * (1.0 + rate) ** years))


def gehalt_im_jahr(untergrenze_cents: int, year: int, base_year: int, rate: float) -> int:
    """Das Monatsgehalt in einem Jahr: die Untergrenze, zum 1. Januar gesteigert.

    Die EINE Regel fuer beide Modelle. Im Basisjahr steht die Untergrenze, wie sie ist;
    jedes Jahr danach kommt ein Mal die Gehaltssteigerung dazu. Vor dem Basisjahr steigt
    nichts: gemessene Monate der Vergangenheit rechnen mit der Untergrenze von heute.
    """
    return grow(untergrenze_cents, max(year - base_year, 0), rate)


def inflate(cents: int, years: float, path: Path | str = PATH) -> int:
    """Carry an amount forward at the inflation rate.

    Used for everything that rises with prices. NOT for a loan payment: an
    annuity is fixed in nominal terms and gets cheaper in real terms every
    year, which is the borrower's quiet advantage and must not be inflated
    away.
    """
    return int(round(cents * (1.0 + inflation_pa(path)) ** years))


def lebenserwartung(path: Path | str = PATH) -> int:
    """Bis zu welchem Alter gerechnet wird -- 95, wenn nichts eingetragen ist."""
    return int(get("ruhestand", "lebenserwartung", path=path, default=95))


def aufbrauchen(path: Path | str = PATH) -> float:
    """Wie viel des Kapitals bis zur Lebenserwartung verbraucht werden darf."""
    return float(get("ruhestand", "aufbrauchen", path=path, default=1.0))


def abzug_renten(path: Path | str = PATH) -> float:
    """Anteil einer Rente, der fuer Steuer und Krankenversicherung abgeht."""
    return float(get("ruhestand", "abzug_renten", path=path, default=0.25))
