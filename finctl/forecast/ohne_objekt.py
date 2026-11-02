"""Cashflow ohne das eine Objekt: traegt sich der Haushalt auch ohne es?

Wer ein Objekt hat, dessen Ertrag vollstaendig in Puffer und Depot fliessen
soll, braucht die Gegenprobe: der Rest -- Gehalt, Mieten, Kredite, Fixkosten,
Konsum -- muss fuer sich mindestens bei null stehen. Weder /ziele noch /konten
zeigte diese Zahl: die Jahresrechnung mischt die Objektannahme in die
Sparrate, und /konten zeigt Salden je Konto, in denen Umbuchungen und
Kaufraten stecken.

ZWEI SEITEN, DIESELBE ABGRENZUNG:

* GEMESSEN je vollstaendigem Monat aus dem Ledger, mit der Blockzuordnung aus
  abgleich. Heraus fallen der Objektblock, das Einmalige (`einmalig`) und
  Investments; Umbuchungen zaehlen dort ohnehin nicht.
* VORAUSGERECHNET je Monat aus den Posten von /konten ueber alle Konten.
  Heraus fallen die Miete und die Kosten der Objekte mit Prognose (`Posten.objekt`), die
  Zeilen der zugehoerigen Planklammer und alle
  Geldbewegungen zwischen eigenen Konten -- Zuweisungen, Auffuellung,
  Abraeumen --, die sich im Haushalt ohnehin aufheben. Das Gehalt ist dort die
  Untergrenze, nicht der Median: die Prognose ist bewusst vorsichtig, in der
  Jahresrechnung ebenso.

WELCHES Objekt gemeint ist, steht in der Konfiguration, nicht hier: die
Kennung in assumptions.yaml, Ziel, Soll und Planklammer in forecast.yaml. Ohne
beides rechnet das Modul den Cashflow ohne Einmaliges und Investments --
eine sinnvolle Zahl auch fuer den, der kein Objekt hat.

DANEBEN steht, wenn forecast.yaml es nennt (`daneben`), eine Kategorie gegen ihr Soll:
der Posten, den der Haushalt neben dem Cashflow im Blick behalten will. Ohne den
Eintrag gibt es weder Karte noch Linie.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from finctl.forecast import abgleich as ag

#: Bloecke, die gemessen NICHT zum Cashflow ohne das Objekt zaehlen. Der
#: Objektblock steht nur in der Liste, wenn eines eingetragen ist -- sonst
#: gibt es ihn nicht, und die Kennung laeuft ins Leere statt etwas zu treffen.
GEMESSEN_OHNE = frozenset({ag.OBJEKT, ag.EINMALIG, "investment"})
#: Kategorien, die kein Cashflow sind: Geld zwischen eigenen Konten und was ins
#: Depot geht. Eine Umbuchung zwischen zwei projizierten Konten erkennt `zaehlt`
#: am Merkmal des Postens (`Posten.umbuchung`), nicht an seinem Etikett.
_KEIN_CASHFLOW = ("transfer/", "investment/")


@dataclass(frozen=True, slots=True)
class Monat:
    monat: date
    cents: int
    daneben_cents: int
    gemessen: bool


def einstellungen(fcfg: dict) -> dict:
    """Ziel, Daneben, Bezeichnung und Zuordnung aus forecast.yaml, mit Vorgaben.

    Auch der NAME kommt aus der Konfiguration -- hier oder, wenn hier nichts
    steht, aus properties.yaml. Fest in die Vorlage geschrieben waere er ein
    Wort, das nur ein Editor aendern kann, und ein Objekt, das verkauft ist,
    stuende noch Jahre als Ueberschrift auf der Seite.

    `klammer` sagt, welche Planklammer die Zeilen des Objekts traegt. Leer
    heisst: keine, und dann faellt aus der Vorausrechnung nur heraus, was
    ohnehin kein Cashflow ist.

    `daneben` ist leer, wo der Haushalt keine Kategorie nennt, sonst
    `{kategorie, label, soll_cents}`; ohne Bezeichnung heisst es wie die Kategorie.
    """
    roh = fcfg.get("cashflow_ohne_objekt") or {}
    return {"ziel_cents": int(roh.get("ziel_cents", 0) or 0),
            "daneben": _daneben(roh.get("daneben")),
            "label": str(roh.get("label") or ag.objekt_name()),
            "klammer": str(roh.get("klammer") or "") or None}


def _daneben(roh) -> dict | None:
    kategorie = str((roh or {}).get("kategorie") or "").strip() if isinstance(roh, dict) else ""
    if not kategorie:
        return None
    return {"kategorie": kategorie, "label": str(roh.get("label") or kategorie),
            "soll_cents": int(roh.get("soll_cents", 0) or 0)}


def gemessen(conn: sqlite3.Connection, monate: int = 12,
             daneben: str | None = None) -> list[Monat]:
    """Die letzten `monate` vollstaendigen Monate, je Monat gemessen.

    `daneben` ist die Kategorie, die zusaetzlich einzeln mitlaeuft."""
    f = ag.fenster(conn, monate)
    if f is None:
        return []
    out = []
    for m in f.monatsliste():
        kat = ag.measure_kategorien(
            conn, ag.Fenster(von=m, bis=ag._month_end(m), monate=1))
        out.append(Monat(
            monat=m,
            cents=sum(c for blk, je in kat.items() if blk not in GEMESSEN_OHNE
                      for c in je.values()),
            daneben_cents=sum(je.get(daneben, 0) for je in kat.values()) if daneben else 0,
            gemessen=True))
    return out


def zaehlt(label: str, herkunft: dict | None, klammer: str | None = None,
           einmalig: frozenset[str] = frozenset()) -> bool:
    """Gehoert ein Posten aus /konten zum Cashflow ohne das Objekt?

    Nicht: eine Umbuchung, und Miete oder Kosten eines Objekts mit Prognose -- beides
    sagt der Posten selbst (`umbuchung`, `objekt`).

    `einmalig` sind die Kategorien mit dem Merkmal: eine Planzeile darauf ist
    kein Cashflow, wie die Buchungen dort gemessen keiner sind."""
    herkunft = herkunft or {}
    if herkunft.get("umbuchung") or herkunft.get("objekt"):
        return False
    # Ein gemessener Posten heisst wie seine Kategorie, eine Planzeile traegt
    # sie im Rechenweg: Geld zwischen eigenen Konten oder ein Depotverkauf ist
    # auch als Planzeile kein Cashflow.
    kategorie = str(herkunft.get("kategorie") or label)
    if kategorie.startswith(_KEIN_CASHFLOW):
        return False
    if herkunft.get("quelle") != "plan":
        return True
    if kategorie in einmalig:
        return False
    if not klammer:
        return True
    return str(herkunft.get("verweis") or "").split(":", 1)[0] != klammer


def vorausgerechnet(views: list[dict], klammer: str | None = None,
                    einmalig: frozenset[str] = frozenset(),
                    daneben: str | None = None) -> list[Monat]:
    """Je Prognosemonat die Summe der zaehlenden Posten ueber alle Konten.

    `views` ist die Rueckgabe von ops.household_accounts.
    """
    summe: dict[str, int] = {}
    einzeln: dict[str, int] = {}
    for v in views:
        if v.get("error"):
            continue
        herkunft = v.get("herkunft") or {}
        for row in v.get("rows") or []:
            monat = row["month"][:7]
            summe.setdefault(monat, 0)
            einzeln.setdefault(monat, 0)
            for label, cents in (row.get("detail") or {}).items():
                if not zaehlt(label, herkunft.get(label), klammer, einmalig):
                    continue
                summe[monat] += cents
                if daneben and label == daneben:
                    einzeln[monat] += cents
    return [Monat(monat=date.fromisoformat(m + "-01"), cents=summe[m],
                  daneben_cents=einzeln[m], gemessen=False)
            for m in sorted(summe)]


def _schnitt(werte: list[int]) -> int | None:
    return round(sum(werte) / len(werte)) if werte else None


def kennzahl(conn: sqlite3.Connection, views: list[dict], fcfg: dict,
             monate_gemessen: int = 12) -> dict:
    """Alles, was die Seiten zeigen: Monate, Schnitte, Ziel und Daneben."""
    ein = einstellungen(fcfg)
    kategorie = (ein["daneben"] or {}).get("kategorie")
    ist = gemessen(conn, monate_gemessen, kategorie)
    prog = vorausgerechnet(views, ein["klammer"], ag.einmalige_kategorien(conn), kategorie)
    naechste = prog[:12]
    letzter = ist[-1] if ist else None
    return {
        **ein,
        "monate": ist + prog,
        "letzter": letzter,
        "schnitt_gemessen_cents": _schnitt([m.cents for m in ist]),
        "gemessen_anzahl": len(ist),
        "gemessen_erreicht": sum(1 for m in ist if m.cents >= ein["ziel_cents"]),
        "schnitt_prognose_cents": _schnitt([m.cents for m in naechste]),
        "prognose_anzahl": len(naechste),
        "prognose_erreicht": sum(1 for m in naechste
                                 if m.cents >= ein["ziel_cents"]),
        "daneben_schnitt_cents": _schnitt([m.daneben_cents for m in ist]),
    }
