"""Der Notgroschen als Untergrenze seines Kontos im Monatsmodell.

Die Jahresrechnung kennt die Grenze des Notgroschens als Kaskade: Was im Tagesgeld darueber
liegt, wandert ins Depot (`jahre.kaskade`, `ziele.puffer_cents`). Das Monatsmodell hat keine
Kaskade, aber Konten mit Untergrenze: Es warnt, wenn der Tiefpunkt eines Kontos darunter
faellt. Der Notgroschen ist dort die Untergrenze des Kontos, auf dem er liegt -- so warnt
`/konten`, wenn eine Klammer ihn angreift.

Die Grenze selbst steht hier und nicht bei den Zielen: Die Prognose darf das Modul Ziele nicht
importieren (`finctl/module.py`), und die Ziele nehmen die Grenze von hier.

Auf welchem Konto er liegt, sagt keine Datei. Abgeleitet wird es: das Konto der Bestandsart
Tagesgeld in `balances.yaml`; gibt es mehrere, das, auf das das Betriebskonto abraeumt. Findet
sich kein einzelnes, gibt es keine Untergrenze aus dem Notgroschen -- die Grenze auf mehrere
Konten zu legen, hiesse, sie mehrfach zu fordern.
"""

from __future__ import annotations

from collections.abc import Mapping

from finctl.dateien import yaml_lesen
from finctl.pfade import CONFIG_DIR

#: Welches Ziel die Grenze zwischen Tagesgeld und Depot setzt.
PUFFER_ZIEL = "tagesgeld-puffer"

#: Wie viele Monate der Gehalts-Untergrenze der Notgroschen ohne eigenen
#: Betrag umfasst.
NOTGROSCHEN_MONATE = 3


def vorgabe(goals: dict) -> dict:
    """Ein Notgroschen ohne Betrag bekommt drei Monate Gehalts-Untergrenze.

    Die Startvorlage traegt ihn ohne Betrag: ein fester Betrag waere eine
    fremde Zahl, und ohne jeden Betrag stuende die Seite leer da. Wer einen
    eigenen Betrag eintraegt, ueberschreibt die Vorgabe; wer die Untergrenze
    auf /annahmen aendert, verschiebt sie mit.
    """
    ziele = goals.get("ziele") or []
    if not any(g.get("id") == PUFFER_ZIEL and not g.get("cents") for g in ziele):
        return goals
    from finctl import assumptions as _ann

    try:
        betrag = NOTGROSCHEN_MONATE * _ann.salary_floor_cents()
    except KeyError:
        return goals
    notiz = f"{NOTGROSCHEN_MONATE} × Gehalts-Untergrenze aus den Annahmen"
    return {**goals, "ziele": [
        {**g, "cents": betrag, "notiz": g.get("notiz") or notiz}
        if g.get("id") == PUFFER_ZIEL and not g.get("cents") else g for g in ziele]}


def puffer_cents(goals: dict) -> int | None:
    """Das Tagesgeld-Ziel: die Grenze der Kaskade in der Hochrechnung.

    Von Hand gesetzt, nicht gemessen. Wer von seinem Vermoegen zu leben
    beginnt, zieht es auf eine Jahresausgabe hoch -- die laesst sich aus den
    Berichten ablesen, und die Hochrechnung folgt dem Ziel sofort.
    """
    ziel = next((g for g in (goals.get("ziele") or []) if g.get("id") == PUFFER_ZIEL), None)
    return int(ziel["cents"]) if ziel and ziel.get("cents") else None


def _lesen(name: str) -> dict:
    pfad = CONFIG_DIR / name
    return (yaml_lesen(pfad) or {}) if pfad.exists() else {}


def konto_des_notgroschens(balances: Mapping, abraeumen_auf: str | None) -> str | None:
    """Das Konto, auf dem der Notgroschen liegt, oder None."""
    kandidaten = [str(r["account_id"]) for r in balances.get("balances") or []
                  if isinstance(r, dict) and r.get("account_id")
                  and str(r.get("kind") or "").strip().lower() == "tagesgeld"]
    if abraeumen_auf is not None and str(abraeumen_auf) in kandidaten:
        return str(abraeumen_auf)
    return kandidaten[0] if len(kandidaten) == 1 else None


def untergrenze(konto: str, fcfg: Mapping) -> int:
    """Die Grenze des Notgroschens, wenn `konto` das Konto des Notgroschens ist; sonst 0."""
    from finctl import module

    if "ziele" not in module.aktive():
        return 0
    goals = _lesen("goals.yaml")
    grenze = puffer_cents(vorgabe({**goals, "ziele": list(goals.get("ziele") or [])}))
    if not grenze:
        return 0
    from finctl.forecast.konten import _operating_account

    betrieb = _operating_account(dict(fcfg))
    ziel = ((fcfg.get("account_roles") or {}).get(betrieb) or {}).get("sweep_to")
    return int(grenze) if konto_des_notgroschens(_lesen("balances.yaml"), ziel) == konto else 0
