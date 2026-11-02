"""Worauf die beiden Prognosen stehen -- je Kategorie, nebeneinander -- und die Abwahl.

Die Seite /prognosebasis zeigt je Block die Quelle (`quellen.py`) und von diesem Modul die
Abwahl je Kategorie.

Zwei Rechnungen, eine Basis. /konten und die Jahresrechnung messen dieselben
zwoelf Monate und nehmen die Zwoelfmonatssumme je Kategorie; /konten teilt sie
durch zwoelf und bucht sie auf dem Konto, auf dem gemessen wurde.

Hier steht je Kategorie: die gemessenen Monate, was /konten daraus macht und was
die Jahresrechnung daraus macht. Beide Spalten zaehlen, was die Rechnung zaehlt:
bleibt von der Messung nichts, weil ein Vertrag, eine erwartete Einnahme oder die
Objektprognose ihre Buchungen ersetzt, stehen dessen Posten da (`_ersetzt`).

NICHT FORTSCHREIBEN wirkt in beiden Rechnungen. Eine Schenkung, die in zwei von
zwoelf Monaten kam, schrieb die Jahresrechnung als 367 im Monat fort -- ein
Einkommen, das es nicht gibt. Die Wahl liegt in
config/prognosebasis_custom.yaml, und dort steht nur, was abgewaehlt ist.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from finctl import notizen as _notizen
from finctl.dateien import yaml_lesen
from finctl.forecast import abgleich as _ag
from finctl.forecast import messung
from finctl.pfade import CONFIG_DIR

DATEI = "prognosebasis_custom.yaml"
SCHLUESSEL = "nicht_fortschreiben"

KOPF = """# Unter Fortschreibung (/prognosebasis) abgewaehlte Kategorien.
#
# Eine Kategorie hier wird in KEINER Prognose fortgeschrieben -- weder auf
# /konten noch in der Jahresrechnung (/hochrechnung, /ziele). Gemessen und im
# Abgleich gezeigt wird sie weiter.
#
# Gedacht fuer Unregelmaessiges, das zufaellig im Messfenster lag: eine
# Schenkung, eine Erstattung. Was wirklich wiederkehrt, gehoert nicht hierher.

"""

#: Mindestens so viele Monate mit Buchungen, sonst gilt eine Kategorie als
#: unregelmaessig -- sofern sie keine Fixkosten sind, die jaehrlich kommen.
REGELMAESSIG_AB = 6


def nicht_fortschreiben() -> set[str]:

    pfad = CONFIG_DIR / DATEI
    if not pfad.exists():
        return set()
    spec = yaml_lesen(pfad) or {}
    return {str(k) for k in (spec.get(SCHLUESSEL) or [])}


def setzen(kategorie: str, fortschreiben: bool) -> set[str]:
    """Eine Kategorie ab- oder wieder anwaehlen. Gespeichert wird nur die
    Abweichung; ist nichts abgewaehlt, verschwindet die Datei."""
    import yaml

    aus = nicht_fortschreiben()
    if fortschreiben:
        aus.discard(kategorie)
    else:
        aus.add(kategorie)
    pfad = CONFIG_DIR / DATEI
    spec = _notizen.mit_bereichen({SCHLUESSEL: sorted(aus)} if aus else {}, pfad)
    if not spec:
        pfad.unlink(missing_ok=True)
        return aus
    pfad.write_text(KOPF + yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    return aus


def _monate(conn: sqlite3.Connection, f) -> dict[str, dict[str, int]]:
    """Je Kategorie die Monatssummen im Fenster, haushaltsweit."""
    out: dict[str, dict[str, int]] = {}
    summen = messung.summiere(messung.monatssummen(conn, von=f.von, bis=f.bis),
                              lambda z: (z.kategorie, z.monat))
    for (kategorie, monat), cents in sorted(summen.items()):
        out.setdefault(kategorie, {})[monat] = cents
    return out


def _konten_je_kategorie(conn: sqlite3.Connection) -> tuple[dict[str, int], dict]:
    """Was /konten je Kategorie im Monat fortschreibt, ueber alle Konten.

    Aus DENSELBEN abgeleiteten Posten wie die Kontoprognose. Eine Reihe mit
    festem Takt zaehlt mit ihrem Monatsanteil (Betrag je Termin durch den Takt),
    damit sie neben dem Rest ihrer Kategorie stehen kann.
    """

    from finctl import abos as _ab
    from finctl.forecast import konten as ops

    fcfg = ops.forecast_config()
    abos = _ab.alle_vertraege()
    durchlaufend = ops.durchlaufende_konten(fcfg)
    konten = [r["id"] for r in conn.execute(
        "SELECT id FROM accounts WHERE ingest_mode='parsed' AND active=1")
        if r["id"] not in durchlaufend]
    summe: dict[str, float] = {}
    reihen = ops.reihen_vor(conn, ops._erster_offener_monat(conn), abos, fcfg=fcfg)
    for konto in konten:
        for item in ops.abgeleitete_posten(conn, konto, fcfg, abos, abwahl=False,
                                           reihen=reihen):
            # Teile ohne Kategorie zaehlen in beiden Rechnungen, unter dem leeren Namen.
            kategorie = item.category or ""
            summe[kategorie] = (summe.get(kategorie, 0.0)
                                + item.amount_cents / (item.every_months or 1))
    overrides = ops._income_overrides(fcfg, ops._erster_offener_monat(conn).year)
    return {k: round(v) for k, v in summe.items()}, {"overrides": overrides}


def vergleich(conn: sqlite3.Connection) -> dict:
    """Je Kategorie: gemessen, /konten und Jahresrechnung."""
    from finctl import assumptions as ann
    from finctl.forecast import abgleich as ag
    from finctl.forecast import engine as fc
    from finctl.forecast import jahre as jm
    from finctl.forecast import konten as ops

    f = ag.fenster(conn)
    if f is None:
        return {"fenster": None, "zeilen": [], "monate": []}
    monatsliste = [f"{m.year}-{m.month:02d}" for m in f.monatsliste()]
    gemessen = _monate(conn, f)
    aus = nicht_fortschreiben()

    # Die Jahresrechnung, wie sie rechnet: Basis ohne die Abwahl, damit die
    # Seite auch zeigt, was eine abgewaehlte Kategorie waere.
    geladen = jm._szenarien_laden()
    basis = jm._base_kategorien(conn, f, jm.ohne_messung(conn, geladen),
                                auch_abgewaehlte=True)
    block_von = {k: b for b, kat in basis.items() for k in kat}

    konten, kontext = _konten_je_kategorie(conn)
    ersetzt = _ersetzt(conn, geladen)
    fixkosten = {r[0] for r in conn.execute(
        "SELECT id FROM mgmt_categories WHERE fixkosten = 1")}
    namen = {r["id"]: r["name"] for r in conn.execute(
        "SELECT id, name FROM mgmt_categories")}
    untergrenze = ann.salary_floor_cents()
    erster_offener = ops._erster_offener_monat(conn)

    zeilen = []
    kategorien = (set(gemessen) | set(konten) | set(ersetzt["monatsmodell"])
                  | set(ersetzt["erwartet"]))
    for kategorie in sorted(kategorien):
        werte = gemessen.get(kategorie, {})
        mit_buchung = sum(1 for m in monatsliste if werte.get(m))
        block = block_von.get(kategorie) or _block_fuer(conn, kategorie)
        abgewaehlt = kategorie in aus
        # Jahresrechnung je Monat.
        if kategorie in jm.GERECHNET:
            jahr = None
        elif block in jm.FROM_BASE:
            jahr = round(basis.get(block, {}).get(kategorie, 0) / 12)
        elif block == "gehalt":
            # Die Jahresrechnung ersetzt den Block durch die Untergrenze.
            jahr = untergrenze
        else:
            jahr = None
        konto = konten.get(kategorie)
        if block == _ag.OBJEKT:
            # Die Objektprognose ersetzt die Messung in beiden Rechnungen (eigene Zeilen unten).
            konto, jahr = None, None
        if kategorie in kontext["overrides"]:
            # Im ersten Monat nach dem Fenster: die Untergrenze steigt erst danach.
            konto = fc.override_in(kontext["overrides"], kategorie, erster_offener)
        konto_wirksam, jahr_wirksam = (None, None) if abgewaehlt else (konto, jahr)
        # Dazu, was ein Vertrag oder eine erwartete Einnahme statt der Messung zaehlt: das
        # bleibt, auch wenn die Messung abgewaehlt ist.
        konto_wirksam = _plus_ersetztes(konto_wirksam, ersetzt, "monatsmodell", kategorie)
        jahr_wirksam = _plus_ersetztes(jahr_wirksam, ersetzt, "jahresrechnung", kategorie)

        unregelmaessig = (block in jm.FROM_BASE and 0 < mit_buchung < REGELMAESSIG_AB
                          and kategorie not in fixkosten)
        zeilen.append({
            "kategorie": kategorie, "name": namen.get(kategorie, ""),
            "block": block, "werte": [werte.get(m, 0) for m in monatsliste],
            "mit_buchung": mit_buchung,
            "schnitt": round(sum(werte.values()) / f.monate),
            "konten": konto_wirksam, "jahr": jahr_wirksam,
            "konten_roh": konto, "jahr_roh": jahr,
            "unregelmaessig": unregelmaessig, "abgewaehlt": abgewaehlt,
            "abwaehlbar": block in jm.FROM_BASE,
        })
    zeilen += _objektzeilen(ersetzt, len(monatsliste))
    return {"fenster": f, "monate": monatsliste, "zeilen": zeilen,
            "summe_konten": sum(z["konten"] or 0 for z in zeilen),
            "summe_jahr": sum(z["jahr"] or 0 for z in zeilen)}


def _ersetzt(conn: sqlite3.Connection, geladen: list) -> dict:
    """Was Vertraege, erwartete Einnahmen und Objektprognosen statt der Messung zaehlen, je Monat.

    Die Zwoelf Monate ab dem ersten offenen, zu Preisen der Messung (ohne Steigerung), aus
    denselben Tatsachen wie beide Rechnungen: `vertraege` und `objektposten`, die Zeilen der
    Klammern. Der Beitrag in eine Police zaehlt nur im Monatsmodell als Vertrag; die
    Jahresrechnung laesst ihn gemessen (`vertraege.police_vertraege`).
    """
    from finctl import objekte as objekte_
    from finctl.forecast import abgleich as ag
    from finctl.forecast import jahre as jm
    from finctl.forecast import konten as ops
    from finctl.forecast import objektposten as ob
    from finctl.forecast import szenarien as sz
    from finctl.forecast import vertraege as vt

    ab = ops._erster_offener_monat(conn).replace(day=1)
    bis = ag._month_end(date(ab.year + (ab.month + 10) // 12, (ab.month + 10) % 12 + 1, 1))

    def wert(abo: dict, pausen, rueck) -> int:
        summe = sum(vt.vertragsbetrag(abo, t, mitte=None, rate=0.0, police=())
                    + vt.anteil_am_termin(abo, t, mitte=None, rate=0.0, police=())
                    for t in vt.termine(abo, pausen, ab=ab, bis=bis))
        return summe + sum(c for m, c in rueck if ab <= m <= bis)

    police = vt.police_vertraege()
    alle = jm.gezaehlte_vertraege(conn, frozenset())
    pausen = vt.pausen(conn, geladen, [a for a, _ in alle])
    monatsmodell: dict[str, int] = {}
    jahresrechnung: dict[str, int] = {}
    for abo, _ in alle:
        if abo["id"] in police:
            # Das Ende regelt die Police, nicht der Vertrag: die Rate steht ohne Ende da,
            # zwoelf Monate lang, wie die Jahresrechnung den Beitrag gemessen fortschreibt.
            w = round(abo["betrag_cents"] * 12 / abo["takt"])
        else:
            w = wert(abo, pausen.get(abo["id"], ()), vt.rueckzahlungen(conn, abo, ab=ab))
        monatsmodell[abo["kategorie"]] = monatsmodell.get(abo["kategorie"], 0) + w
        if abo["id"] not in police:
            jahresrechnung[abo["kategorie"]] = jahresrechnung.get(abo["kategorie"], 0) + w
    erwartet: dict[str, int] = {}
    for sc in sz.active(geladen):
        for line in sc.lines:
            if line.kind != "erwartet" or not jm.zaehlt_in_prognose(line) or not line.category_id:
                continue
            w = sum(line.amount_cents for t in line.months(bis) if ab <= date(t.year, t.month, 1))
            erwartet[line.category_id] = erwartet.get(line.category_id, 0) + w
    objekte = {p.id: (p.name, sum(ob.netto(p, date(ab.year + (ab.month - 1 + i) // 12,
                                                  (ab.month - 1 + i) % 12 + 1, 1),
                                           ab.year, 0.0) for i in range(12)))
               for p in objekte_.prognosen()}
    return {"monatsmodell": monatsmodell, "jahresrechnung": jahresrechnung,
            "erwartet": erwartet,
            "objekte": {k: (n, round(w / 12)) for k, (n, w) in objekte.items()}}


def _plus_ersetztes(wert: int | None, ersetzt: dict, rechnung: str, kategorie: str) -> int | None:
    """Der Wert einer Kategorie in einer Rechnung samt dem, was ein Vertrag oder eine erwartete
    Einnahme statt der Messung zaehlt (je Monat). Das bleibt, auch wo die Messung abgewaehlt ist."""
    dazu = ersetzt[rechnung].get(kategorie, 0) + ersetzt["erwartet"].get(kategorie, 0)
    return wert if not dazu else (wert or 0) + round(dazu / 12)


def _objektzeilen(ersetzt: dict, monate: int) -> list[dict]:
    """Je Objekt mit Prognose eine Zeile: beide Rechnungen nehmen dieselbe Zahl."""
    return [{
        "kategorie": f"{name} (Objektprognose)", "name": name, "block": _ag.OBJEKT,
        "werte": [0] * monate, "mit_buchung": 0, "schnitt": 0,
        "konten": netto, "jahr": netto, "konten_roh": netto, "jahr_roh": netto,
        "unregelmaessig": False, "abgewaehlt": False, "abwaehlbar": False}
        for name, netto in ersetzt["objekte"].values()]


def _block_fuer(conn: sqlite3.Connection, kategorie: str) -> str | None:
    """Der Block einer Kategorie ohne Buchung im Fenster -- per derselben
    Zuordnung wie im Abgleich."""
    from finctl.forecast import abgleich as ag

    return ag.block_der_kategorie(conn, kategorie)


def monat_text(d: date) -> str:
    return f"{d.month:02d}/{d.year}"
