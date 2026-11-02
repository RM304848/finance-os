"""Abos mit Termin -- angelegt, geteilt und eingesammelt im Frontend.

Der Kostenmedian stimmt im Jahresschnitt und ist in jedem einzelnen Monat
falsch. Wann etwas abgeht, ist eine andere Frage als wieviel -- und es ist die
Frage, die die Tabellenkalkulation vorher beantwortet hat.

EINE DATEI je Art: `config/abos.yaml` (Versicherungen: `versicherungen.yaml`) haelt jeden
Vertrag mit seiner Notiz, und die Seite `/vertraege` schreibt den ganzen Eintrag dorthin
(Schritt 5, N.3b: davor lag alles, was die Seite aenderte, in einer zweiten Datei).

DER DOPPELZAEHL-SCHUTZ ist der eigentliche Inhalt. Ein Abo ERSETZT seine
Buchungen in der Prognose, statt neben ihnen zu stehen. Welche das sind,
entscheidet der Eigentuemer, indem er sie auf der Seite ZUORDNET -- keine
Gegenpartei zum Eintippen, die er nirgends sehen kann, sondern Buchungen zum
Anhaken. Gemerkt wird ihr `dedup_hash`, derselbe Schluessel, auf dem
`overrides.yaml` jede Handentscheidung ueber einen Neuaufbau rettet.

GETEILT heisst: eine BESETZUNG als Vorlage und ZEITRAEUME, die beim Anlegen
eine Kopie davon bekommen. Aendert sich die Besetzung, bleibt ein alter
Zeitraum, wie er war -- wer 2026 mitgezahlt hat, hat 2026 mitgezahlt.
Eingesammelt wird nicht abgehakt, sondern abgeglichen: Eingaenge mit dem
Namen einer Person, in der Kategorie des Abos, rund um den Zeitraum.
"""

from __future__ import annotations

import itertools
import re
import sqlite3
from collections.abc import Collection, Mapping, Sequence
from datetime import date
from pathlib import Path

from finctl import notizen as _notizen
from finctl.dateien import yaml_lesen, yaml_schreiben
from finctl.ingest.base import normalize_counterparty
from finctl.kalender import plus_monate
from finctl.ledger.db import format_eur, parse_de_amount
from finctl.pfade import CONFIG_DIR

# ZWEI ARTEN, EINE MASCHINE. Versicherungen verhalten sich wie Abos --
# Termin, Takt, zugeordnete Buchungen ersetzen den Median, teilen --, stehen
# aber auf einer eigenen Seite und in eigenen Dateien, wie vorher in der
# Tabellenkalkulation. Je Art: die Datei und der Schluessel darin.
ARTEN = {
    "abo": ("abos.yaml", "abos"),
    "versicherung": ("versicherungen.yaml", "versicherungen"),
}


def datei(art: str = "abo") -> Path:
    return CONFIG_DIR / ARTEN[art][0]


#: Die Felder, die die Seite schreibt und `normalisieren` kennt; `betrag` ist die Schreibweise
#: in Euro, die von Hand geschriebene Dateien noch tragen.
_FELDER = ("name", "kategorie", "konto", "betrag", "betrag_cents", "takt", "faellig",
           "vorrat_bis", "gekuendigt_zum", "weg", "buchungen", "ignoriert", "geteilt")

TAKTE = (1, 2, 3, 4, 6, 12)
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")
_MONAT = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

# ------------------------------------------------------------------ laden

def laden(pfad: Path | None = None, art: str = "abo") -> list[dict]:
    """Die Vertraege der Datei, in eine Form gebracht."""
    pfad = pfad or datei(art)
    if not pfad.exists():
        return []
    return aus_spec(yaml_lesen(pfad) or {}, art)


def aus_spec(spec: dict, art: str = "abo") -> list[dict]:
    """Die Vertraege einer gelesenen Datei, geprueft."""
    out = []
    for roh in spec.get(ARTEN[art][1]) or []:
        if not isinstance(roh, dict) or not roh.get("id"):
            continue
        a = normalisieren(roh)
        a["art"] = art
        out.append(a)
    doppelt = sorted({a["id"] for a in out if sum(b["id"] == a["id"] for b in out) > 1})
    if doppelt:
        raise ValueError(f"Kennung doppelt in {ARTEN[art][0]}: {', '.join(doppelt)}")
    return out


def alle_vertraege() -> list[dict]:
    """Abos und Versicherungen zusammen -- was die Prognose ersetzt.

    Eine Kennung in beiden Dateien waere derselbe Posten zweimal, oder zwei
    Posten, von denen die Seite nur einen aendern kann. Das faellt beim
    Laden auf statt im Kontostand.
    """
    out = [a for art in ARTEN for a in laden(art=art)]
    doppelt = sorted({a["id"] for a in out if sum(b["id"] == a["id"] for b in out) > 1})
    if doppelt:
        raise ValueError(f"Kennung in Abos und Versicherungen: {', '.join(doppelt)}")
    return out


def normalisieren(roh: dict) -> dict:
    """Eine Form fuer beide Quellen, mit geprueften Feldern.

    Ein unvollstaendiger Eintrag faellt auf, statt still zu wirken: ein Abo
    ohne Termin waere ein Betrag ohne Datum und damit genau das, was der
    Median schon kann.
    """
    fehlend = [f for f in ("id", "name", "kategorie", "konto", "takt", "faellig")
               if roh.get(f) in (None, "")]
    if roh.get("betrag_cents") is None and roh.get("betrag") is None:
        fehlend.append("betrag")
    if fehlend:
        raise ValueError(f"Abo {roh.get('id') or '?'}: es fehlt {', '.join(fehlend)}")
    takt = int(roh["takt"])
    if takt not in TAKTE:
        raise ValueError(f"Abo {roh['id']}: Takt {takt} ist kein Teiler des Jahres")
    betrag = (int(roh["betrag_cents"]) if roh.get("betrag_cents") is not None
              else _cents(roh["betrag"]))
    if betrag >= 0:
        # Ein vergessenes Minus machte auf /planung aus einer Rate eine
        # Einnahme. Hier kann es das nicht geben: ein Vertrag mit Termin ist
        # immer Geld raus, Rueckzahlungen der Mitzahler laufen getrennt.
        raise ValueError(f"{roh['id']}: Betrag ist eine Ausgabe, also negativ")

    geteilt = roh.get("geteilt") or {}
    return {
        "id": str(roh["id"]),
        "name": str(roh["name"]),
        "kategorie": str(roh["kategorie"]),
        "konto": str(roh["konto"]),
        "betrag_cents": betrag,
        "takt": takt,
        "faellig": _datum(roh["faellig"]),
        "vorrat_bis": _datum(roh["vorrat_bis"]) if roh.get("vorrat_bis") else None,
        "gekuendigt_zum": (_datum(roh["gekuendigt_zum"])
                           if roh.get("gekuendigt_zum") else None),
        "weg": roh.get("weg") or "",
        "notiz": _notizen.lesen(roh).text,
        "buchungen": [str(h) for h in roh.get("buchungen") or [] if h],
        "ignoriert": [str(h) for h in roh.get("ignoriert") or [] if h],
        "geteilt": {
            "besetzung": [_person(p) for p in geteilt.get("besetzung") or []],
            "zeitraeume": [_zeitraum(z, roh["id"])
                           for z in geteilt.get("zeitraeume") or []],
        },
    }


def _person(p: dict) -> dict:
    if not p.get("name"):
        raise ValueError("Person ohne Namen")
    anteil = (int(p["anteil_cents"]) if p.get("anteil_cents") is not None
              else _cents(p.get("anteil") or 0))
    if anteil < 0:
        raise ValueError(f"{p['name']}: negativer Anteil")
    seit = str(p.get("seit") or "")
    if seit and not _MONAT.match(seit):
        raise ValueError(f"{p['name']}: seit braucht JJJJ-MM")
    return {"name": str(p["name"]).strip(), "anteil_cents": anteil,
            "aliase": [str(a).strip() for a in p.get("aliase") or [] if str(a).strip()],
            "zahlungen": [str(h) for h in p.get("zahlungen") or [] if h],
            "seit": seit or None}


def _zeitraum(z: dict, abo_id: str) -> dict:
    for feld in ("von", "bis", "einsammeln"):
        if not _MONAT.match(str(z.get(feld) or "")):
            raise ValueError(f"Abo {abo_id}: Zeitraum braucht {feld} als JJJJ-MM")
    if str(z["bis"]) < str(z["von"]):
        raise ValueError(f"Abo {abo_id}: Zeitraum endet vor seinem Beginn")
    return {"von": str(z["von"]), "bis": str(z["bis"]),
            "einsammeln": str(z["einsammeln"]),
            "personen": [_person(p) for p in z.get("personen") or []]}


def _cents(wert) -> int:
    # Zahl oder Text: in der Datei steht -84.00, von Hand getippt gern
    # "-84,00". Beides meint dasselbe.
    if isinstance(wert, (int, float)):
        return int(round(float(wert) * 100))
    return parse_de_amount(str(wert))


def kennung_aus(text: str) -> str:
    """Eine Kennung aus einem Namen: klein, ohne Umlaute, Bindestriche statt Sonderzeichen."""
    import unicodedata

    t = unicodedata.normalize("NFKD", str(text).lower().replace("ß", "ss"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:60].strip("-")


def monat_plus(monat: str, n: int) -> str:
    """JJJJ-MM plus n Monate."""
    if not _MONAT.match(str(monat)):
        raise ValueError(f"Monat als JJJJ-MM: {monat}")
    return plus_monate(date.fromisoformat(f"{monat}-01"), int(n)).isoformat()[:7]


def datum_plus(tag: str, n: int) -> str:
    """JJJJ-MM-TT plus n Monate; der 31. bleibt im Februar der letzte Tag."""
    return plus_monate(date.fromisoformat(str(tag)[:10]), int(n)).isoformat()


def texte_lesen(abo: dict) -> dict:
    """`betrag_text` und `anteil_text` -- wie getippt -- werden Cent.

    Der Betrag eines Vertrags mit Termin ist immer eine Ausgabe: das Feld traegt
    kein Vorzeichen, gespeichert wird negativ. Ein leerer Anteil ist null.
    """
    from finctl.ledger.db import EingabeError, parse_eingabe_betrag

    def lesen(text: str, feld: str) -> int:
        try:
            return parse_eingabe_betrag(text)
        except EingabeError as fehler:
            raise EingabeError(str(fehler), feld) from None

    if abo.get("betrag_text") is not None:
        abo["betrag_cents"] = -abs(lesen(abo["betrag_text"], "betrag"))
    geteilt = abo.get("geteilt") or {}
    personen = list(geteilt.get("besetzung") or [])
    for zeitraum in geteilt.get("zeitraeume") or []:
        personen += zeitraum.get("personen") or []
    for p in personen:
        if p.get("anteil_text") is not None:
            p["anteil_cents"] = (0 if str(p["anteil_text"]).strip() == ""
                                 else lesen(p["anteil_text"], "anteil"))
    return abo


def _datum(wert) -> date:
    return wert if isinstance(wert, date) else date.fromisoformat(str(wert))


# -------------------------------------------------------------- schreiben

def _datei_lesen(pfad: Path, art: str) -> dict:
    """Die Datei ganz, mit der Liste der Vertraege darin (die es geben darf, auch leer)."""
    spec = (yaml_lesen(pfad) or {}) if pfad.exists() else {}
    schluessel = ARTEN[art][1]
    if spec.get(schluessel) is None:
        spec[schluessel] = []
    elif not isinstance(spec[schluessel], list):
        raise ValueError(f"{ARTEN[art][0]}: `{schluessel}` ist keine Liste")
    return spec


def speichern(abo: dict, pfad: Path | None = None, art: str = "abo") -> dict:
    """Ein Abo aus dem Frontend ablegen.

    Geprueft wird VOR dem Schreiben, mit derselben Funktion, die beim Lesen
    prueft: was hier durchgeht, laesst sich auch wieder laden. Sonst koennte
    ein Klick die Datei so hinterlassen, dass keine Prognose mehr rechnet.

    Der ganze Eintrag kommt in die Datei, mit seiner Notiz. Sagt er danach dasselbe wie vorher
    -- auch wenn die Datei den Betrag noch in Euro fuehrt --, bleibt die Datei, wie sie ist.
    """
    pfad = pfad or datei(art)
    abo_id = str(abo.get("id") or "").strip()
    if not _ID.match(abo_id) or abo_id in _notizen.RESERVIERT:
        raise ValueError("Kennung nur aus Kleinbuchstaben, Ziffern und Bindestrich, "
                         "und nicht „notiz“, „notiz_vom“ oder „notizen“")
    eintrag = {
        "name": abo.get("name"), "kategorie": abo.get("kategorie"),
        "konto": abo.get("konto"), "betrag_cents": abo.get("betrag_cents"),
        "takt": abo.get("takt"), "faellig": str(abo.get("faellig") or ""),
        "vorrat_bis": str(abo["vorrat_bis"]) if abo.get("vorrat_bis") else None,
        "gekuendigt_zum": (str(abo["gekuendigt_zum"])
                           if abo.get("gekuendigt_zum") else None),
        "weg": abo.get("weg") or None,
        "buchungen": sorted({str(h) for h in abo.get("buchungen") or [] if h}) or None,
        "ignoriert": sorted({str(h) for h in abo.get("ignoriert") or [] if h}) or None,
        "geteilt": None,
    }
    geteilt = abo.get("geteilt") or {}
    besetzung = [_person(p) for p in geteilt.get("besetzung") or []]
    zeitraeume = [_zeitraum(z, abo_id) for z in geteilt.get("zeitraeume") or []]
    if besetzung or zeitraeume:
        eintrag["geteilt"] = {
            "besetzung": [_person_yaml(p) for p in besetzung],
            "zeitraeume": [{**{k: z[k] for k in ("von", "bis", "einsammeln")},
                            "personen": [_person_yaml(p) for p in z["personen"]]}
                           for z in zeitraeume],
        }
    eintrag = {k: v for k, v in eintrag.items() if v not in (None, "", [])}
    neu = normalisieren({**eintrag, "id": abo_id})     # wirft, wenn unvollstaendig
    # Daten stehen in der Datei als Datum, wie von Hand geschrieben.
    for feld in ("faellig", "vorrat_bis", "gekuendigt_zum"):
        if feld in eintrag:
            eintrag[feld] = neu[feld]

    spec = _datei_lesen(pfad, art)
    liste = spec[ARTEN[art][1]]
    stelle = next((i for i, e in enumerate(liste) if str(e.get("id")) == abo_id), None)
    bisher = liste[stelle] if stelle is not None else None
    alt_notiz = _notizen.lesen(bisher) if bisher else _notizen.Notiz()
    # Die Notiz vergleicht die Datumsregel; hier zaehlen die Felder des Vertrags.
    gleich = bisher is not None and (
        {k: v for k, v in normalisieren(bisher).items() if k != "notiz"}
        == {k: v for k, v in neu.items() if k != "notiz"})

    neuer = {"id": abo_id}
    if bisher:
        # Was die Seite nicht kennt, bleibt; was sie schreibt, ersetzt das Alte.
        neuer |= {k: v for k, v in bisher.items() if k != "id" and k not in _FELDER
                  and k not in (_notizen.NOTIZ, _notizen.VOM)}
    neuer |= eintrag
    notiz = _notizen.fortschreiben(alt_notiz, str(abo.get("notiz") or ""))
    neuer |= notiz.als_dict()
    if gleich and notiz == alt_notiz:
        return bisher
    if stelle is None:
        liste.append(neuer)
    else:
        liste[stelle] = neuer
    _schreiben(pfad, spec)
    return neuer


def _person_yaml(p: dict) -> dict:
    out = {"name": p["name"], "anteil_cents": p["anteil_cents"]}
    if p["aliase"]:
        out["aliase"] = p["aliase"]
    if p["zahlungen"]:
        out["zahlungen"] = sorted(set(p["zahlungen"]))
    if p.get("seit"):
        out["seit"] = p["seit"]
    return out


def entfernen(abo_id: str, pfad: Path | None = None, art: str = "abo") -> None:
    """Einen Vertrag aus der Datei nehmen."""
    pfad = pfad or datei(art)
    spec = _datei_lesen(pfad, art)
    schluessel = ARTEN[art][1]
    spec[schluessel] = [e for e in spec[schluessel] if str(e.get("id")) != abo_id]
    _schreiben(pfad, spec)


def _schreiben(pfad: Path, spec: dict) -> None:
    """Die ganze Datei, mit allen Notizen; sie bleibt, wie sie ist, wenn sie dasselbe sagt."""
    yaml_schreiben(pfad, spec)


# --------------------------------------------------------------- Prognose

def ausschluesse(conn, abos: list[dict]) -> list[dict]:
    """Welche Buchungen die erklaerten Vertraege in der Prognose ersetzen.

    NICHT NUR DIE ANGEHAKTEN, sondern ihre ganze Reihe -- siehe
    `finctl/ledger/reihe.py`. Ein Haken ist ein Beispiel, keine Inventur:
    wer einen Vertrag erklaert, meint alle seine Buchungen, nicht die paar,
    die er angeklickt hat. Vorher blieb der Rest im Median stehen, waehrend
    der Vertrag seinen Termin zusaetzlich buchte.

    DAZU DIE ZAHLUNGEN DER MITZAHLER, die einem Zeitraum zugeordnet sind oder
    laufend eingehen (`mitzahler`): Sie zaehlen ueber den Vertrag, als offener
    Anteil (`rueckzahlungen`) und als erwarteter Anteil je Termin
    (`erwartete_anteile`). Gemessen stuenden sie daneben noch einmal da.

    `conn` darf None sein; dann bleibt es bei den angehakten Buchungen.
    """
    from finctl.ledger import reihe as _reihe

    alle = {h for a in abos for h in a["buchungen"]}
    if conn is not None:
        for a in abos:
            # Je Vertrag mit SEINEM Betrag: derselbe Empfaenger kann in
            # derselben Kategorie zweierlei sein, und der Betrag trennt das.
            alle |= set(_reihe.hashes(conn, a["buchungen"], a.get("betrag_cents")))
            alle |= mitzahler(conn, a)
    return [{"dedup_hashes": sorted(alle)}] if alle else []


#: Die Zahlungen der Mitzahler der letzten Verbindung. `abrechnung` liest alle Eingaenge, und
#: die Prognose fragt je Konto und Stichtag erneut; gemerkt wird, solange sich die Datenbank
#: nicht aendert (eigene Schreibzugriffe und die anderer Verbindungen). Die Verbindung selbst
#: bleibt gehalten, damit keine neue unter derselben Adresse einen fremden Stand erbt.
_MITZAHLER: dict = {"conn": None, "stand": None, "werte": {}}


def _mitzahlungen(conn: sqlite3.Connection, abo: dict) -> list[dict]:
    """Die Zahlungen der Mitzahler eines Vertrags: was `abrechnung` einer Person eines
    Zeitraums und `laufend` einer laufenden Person zurechnet, von Hand oder automatisch."""
    if not abo["geteilt"]["zeitraeume"] and not any(
            p.get("seit") for p in abo["geteilt"]["besetzung"]):
        return []
    stand = (conn.total_changes, conn.execute("PRAGMA data_version").fetchone()[0])
    if _MITZAHLER["conn"] is not conn or _MITZAHLER["stand"] != stand:
        _MITZAHLER.update(conn=conn, stand=stand, werte={})
    schluessel = repr((abo["id"], abo["kategorie"], abo["geteilt"], abo["ignoriert"]))
    if schluessel not in _MITZAHLER["werte"]:
        treffer = [t for z in abrechnung(conn, abo) for p in z["personen"] for t in p["treffer"]]
        treffer += [t for p in laufend(conn, abo) for t in p["treffer"]]
        _MITZAHLER["werte"][schluessel] = [
            {k: t[k] for k in ("hash", "datum", "konto")} for t in treffer]
    return list(_MITZAHLER["werte"][schluessel])


def mitzahler(conn: sqlite3.Connection, abo: dict) -> set[str]:
    """Die Zahlungen der Mitzahler, die einem Zeitraum des Vertrags zugeordnet sind oder
    von jemandem kommen, der laufend mitzahlt. Von Hand oder automatisch."""
    return {t["hash"] for t in _mitzahlungen(conn, abo)}


def eingangskonto(conn: sqlite3.Connection, abo: dict) -> str | None:
    """Das Konto, auf dem die Mitzahler zuletzt gezahlt haben; None, wo es noch keine Zahlung
    gibt. Dorthin gehoert ein erwarteter Anteil (`erwartete_anteile`)."""
    zahlungen = _mitzahlungen(conn, abo)
    return max(zahlungen, key=lambda t: (t["datum"], t["hash"]))["konto"] if zahlungen else None


def zeitraum_am(abo: dict, termin: date) -> dict | None:
    """Der angelegte Zeitraum, der den Termin deckt: ab seinem Beginn bis zu seinem Ende,
    das Ende ausgenommen. Das Ende ist der Beginn des naechsten (`Zeitraum anlegen` setzt
    es so), ein Termin dort gehoert dem naechsten; ein Zeitraum aus einem Monat deckt ihn."""
    monat = termin.replace(day=1)
    for z in abo["geteilt"]["zeitraeume"]:
        von = _monat_erster(z["von"])
        if von <= monat < max(_monat_erster(z["bis"]), plus_monate(von, 1)):
            return z
    return None


def erwartete_anteile(abo: dict, termin: date) -> int:
    """Was die Besetzung den Mitzahlern an diesem Termin zuordnet, in Cent, positiv.

    Nur, wo es keinen angelegten Zeitraum gibt: Hat einer den Termin, gilt sein offener
    Anteil (`rueckzahlungen`), nie beides. Wer laufend mitzahlt (`seit`), gehoert zu keinem
    Zeitraum und zaehlt ab diesem Monat bei jedem Termin, ausser der Zeitraum nennt ihn.

    Es zaehlt, wer schon einmal in einem Zeitraum stand oder laufend mitzahlt. Eine Person,
    die nur in der Besetzung steht, ist die Vorlage fuer einen kuenftigen Zeitraum: Wer nie
    gezahlt hat, dessen Anteil ist keine Erwartung, sondern ein Vorhaben.
    """
    zeitraum = zeitraum_am(abo, termin)
    genannt = {p["name"] for p in zeitraum["personen"]} if zeitraum else set()
    gefuehrt = {p["name"] for z in abo["geteilt"]["zeitraeume"] for p in z["personen"]}
    monat = termin.replace(day=1)
    return sum(p["anteil_cents"] for p in abo["geteilt"]["besetzung"]
               if (p.get("seit") and _monat_erster(p["seit"]) <= monat
                   and p["name"] not in genannt)
               or (not p.get("seit") and p["name"] in gefuehrt and not zeitraum))


def termine(abo: dict, *, ab: date, bis: date) -> list[date]:
    """Die Termine eines Vertrags im Fenster, wie er sie zahlt.

    Vom erklaerten Termin aus in beide Richtungen: `faellig` ist der NAECHSTE
    Termin, nicht der erste. Jeder Termin ist `faellig` plus ein ganzes
    Vielfaches des Takts, direkt von `faellig` aus gerechnet -- nicht der Vorgaenger
    plus ein Takt: Ein Termin am 31. kappt im Februar auf den 28. und kommt im
    Maerz wieder am 31. Nach einer Kuendigung kommt nichts mehr, und vor dem Ende
    eines Vorrats auch nicht -- der ist bezahlt.
    """
    faellig, takt = abo["faellig"], abo["takt"]
    out = []
    # Der erste Schritt liegt im Monat von `ab` oder davor; was davor liegt, faellt unten raus.
    k = ((ab.year * 12 + ab.month) - (faellig.year * 12 + faellig.month)) // takt
    while (termin := plus_monate(faellig, k * takt)) <= bis:
        k += 1
        if termin < ab:
            continue
        gekuendigt = abo["gekuendigt_zum"] and termin > abo["gekuendigt_zum"]
        vorrat = abo["vorrat_bis"] and termin < abo["vorrat_bis"]
        if not gekuendigt and not vorrat:
            out.append(termin)
    return out


def posten(abos: list[dict], konto: str | Collection[str], *, ab: date, bis: date,
           pausen: Mapping[str, Sequence[tuple[date, date | None]]] | None = None) -> list[dict]:
    """Die faelligen Termine eines Kontos (oder mehrerer) im Fenster.

    `pausen` sind je Vertrag die Zeitraeume, in denen eine Wegfall-Zeile ihn aussetzt
    (`forecast.vertraege.pausen`); in ihren Monaten kommt nichts.
    """
    konten = {konto} if isinstance(konto, str) else set(konto)
    out = []
    for a in abos:
        if a["konto"] not in konten:
            continue
        ruhend = (pausen or {}).get(a["id"], ())
        out.extend({"abo": a, "faellig": termin, "betrag_cents": a["betrag_cents"]}
                   for termin in termine(a, ab=ab, bis=bis)
                   if not ausgesetzt(ruhend, termin))
    return sorted(out, key=lambda p: p["faellig"])


def ausgesetzt(pausen: Sequence[tuple[date, date | None]], termin: date) -> bool:
    """Ob eine Pause den Monat dieses Termins deckt."""
    monat = termin.replace(day=1)
    return any(von <= monat and (bis is None or monat <= bis) for von, bis in pausen)


def rueckzahlungen(conn: sqlite3.Connection, abos: list[dict], konto: str | Collection[str],
                   *, ab: date, bis: date, heute: date | None = None) -> list[dict]:
    """Was von Mitzahlern noch erwartet wird, im Einsammel-Monat.

    Nur der OFFENE Teil. Ist das Geld da, verschwindet der Posten von selbst --
    sonst stuende eine laengst eingegangene Rueckzahlung weiter als erwartet
    in der Prognose. Ein verstrichener Einsammel-Monat rueckt in den ersten
    Prognosemonat: das Geld wird ja weiter erwartet, nur spaeter.
    """
    konten = {konto} if isinstance(konto, str) else set(konto)
    out = []
    for a in abos:
        if a["konto"] not in konten:
            continue
        for z in abrechnung(conn, a, heute=heute):
            if z["offen"] <= 0:
                continue
            monat = _monat_erster(z["einsammeln"])
            monat = max(monat, ab.replace(day=1))
            if monat <= bis:
                out.append({"abo": a, "monat": monat, "cents": z["offen"],
                            "zeitraum": z})
    return out


# ------------------------------------------------------------- Abrechnung

def abrechnung(conn: sqlite3.Connection, abo: dict,
               heute: date | None = None) -> list[dict]:
    """Je Zeitraum: wer schuldet was, was kam zurueck, was ist offen.

    ZWEI WEGE, und der von Hand gewinnt. Eine ZUGEORDNETE Zahlung zaehlt fuer
    genau die Person und den Zeitraum, dem sie zugeordnet ist -- egal in
    welcher Kategorie sie steht und wann sie kam: Eine Mitnutzerin hat 2024 ueber PayPal
    gezahlt, unter konsum/sonstiges und weit ausserhalb jedes Fensters.
    AUTOMATISCH zugeordnet wird nur, was niemand von Hand vergeben hat: ein
    Eingang mit dem Namen der Person, in der Kategorie des Abos oder ohne
    Kategorie, rund um den Zeitraum. Ein falscher automatischer Treffer wird
    verworfen und bleibt verworfen.

    Automatisches wird je Person gedeckelt: was ueber den Anteil hinausgeht,
    zaehlt fuer den naechsten Zeitraum. Von Hand Zugeordnetes nie -- wer es
    einem Zeitraum zuordnet, meint diesen.
    """
    heute = heute or date.today()
    zeitraeume = sorted(abo["geteilt"]["zeitraeume"], key=lambda z: z["von"])
    if not zeitraeume:
        return []

    von_hand = {h for z in zeitraeume for p in z["personen"] for h in p["zahlungen"]}
    verworfen = set(abo.get("ignoriert") or [])
    zugeordnet = _nach_hash(conn, von_hand)
    eingaenge = [e for e in _eingaenge(conn, abo["kategorie"])
                 if e["hash"] not in von_hand and e["hash"] not in verworfen]
    vergeben: set[str] = set()
    uebertrag: dict[str, list[dict]] = {}
    out = []
    for z in zeitraeume:
        von = plus_monate(_monat_erster(min(z["von"], z["einsammeln"])), -3)
        bis = plus_monate(_monat_erster(max(z["bis"], z["einsammeln"])), 4)
        personen = []
        for p in z["personen"]:
            soll = p["anteil_cents"]
            schluessel = _schluessel(p)
            genutzt = [{**zugeordnet[h], "art": "zugeordnet"}
                       for h in p["zahlungen"] if h in zugeordnet]
            zurueck = sum(t["cents"] for t in genutzt)
            automatisch = list(uebertrag.pop(p["name"], []))
            for e in eingaenge:
                if e["hash"] in vergeben or not (von <= e["datum"] < bis):
                    continue
                if any(s in e["suchtext"] for s in schluessel):
                    automatisch.append({k: e[k] for k in ("id", "hash", "datum", "cents", "konto")}
                                       | {"art": "automatisch"})
                    vergeben.add(e["hash"])
            for t in sorted(automatisch, key=lambda t: t["datum"]):
                if zurueck >= soll:
                    uebertrag.setdefault(p["name"], []).append(t)
                    continue
                zurueck += t["cents"]
                genutzt.append(t)
            personen.append({
                "name": p["name"], "aliase": p["aliase"],
                "soll": p["anteil_cents"], "zurueck": zurueck,
                "offen": max(soll - zurueck, 0),
                "treffer": sorted(genutzt, key=lambda t: t["datum"])})
        offen = sum(p["offen"] for p in personen)
        faellig = _monat_erster(z["einsammeln"]) <= heute.replace(day=1)
        out.append({
            "von": z["von"], "bis": z["bis"], "einsammeln": z["einsammeln"],
            "personen": personen,
            "soll": sum(p["soll"] for p in personen),
            "zurueck": sum(p["zurueck"] for p in personen),
            "offen": offen,
            "status": ("abgerechnet" if offen == 0
                       else "faellig" if faellig else "offen"),
        })

    # Vorschlaege je Person: Eingaenge mit ihrem Namen, die noch nirgends
    # zaehlen -- in jeder Kategorie und zu jedem Datum. Genau die, die der
    # automatische Abgleich nicht anfasst.
    gezaehlt = von_hand | verworfen | {t["hash"] for z in out for p in z["personen"]
                                       for t in p["treffer"]}
    alle = _alle_eingaenge(conn)
    for z, roh in zip(out, zeitraeume, strict=True):
        for p, rp in zip(z["personen"], roh["personen"], strict=True):
            schluessel = _schluessel(rp)
            p["vorschlaege"] = [
                {k: e[k] for k in ("hash", "datum", "cents", "konto", "gegenpartei", "kategorie")}
                for e in alle
                if e["hash"] not in gezaehlt and any(s in e["suchtext"] for s in schluessel)][:5]
    return out


def laufend(conn: sqlite3.Connection, abo: dict,
            heute: date | None = None) -> list[dict]:
    """Wer LAUFEND mitzahlt: je Takt seinen Anteil, ohne Zeitraum.

    Ein Zeitraum passt zum Vorstrecken und spaeter Einsammeln. Wer jeden
    Monat seinen Teil ueberweist, bekaeme dafuer jeden Monat einen eigenen
    -- deshalb traegt die Person in der Besetzung ein `seit`, und gezaehlt
    wird fortlaufend: Soll ist der Anteil je faelligem Takt seit diesem
    Monat, zurueck ist, was zugeordnet oder mit ihrem Namen eingegangen ist.
    Automatisch nur GENAU DER ANTEIL: wer mitzahlt, ueberweist oft auch
    anderes, und 200 Euro fuer etwas ganz anderes sind kein Handyanteil.

    In die Prognose geht davon nichts eigens: der Eingang steht in der
    Kategorie des Abos und zaehlt dort im Median mit, wie jeder andere.
    """
    heute = heute or date.today()
    personen = [p for p in abo["geteilt"]["besetzung"] if p.get("seit")]
    if not personen:
        return []
    anderswo = {h for z in abo["geteilt"]["zeitraeume"]
                for p in z["personen"] for h in p["zahlungen"]}
    von_hand = {h for p in personen for h in p["zahlungen"]}
    verworfen = set(abo.get("ignoriert") or [])
    zugeordnet = _nach_hash(conn, von_hand)
    eingaenge = [e for e in _eingaenge(conn, abo["kategorie"])
                 if e["hash"] not in von_hand | verworfen | anderswo]
    alle = _alle_eingaenge(conn)
    out = []
    for p in personen:
        beginn = _monat_erster(p["seit"])
        monate = (heute.year - beginn.year) * 12 + heute.month - beginn.month + 1
        soll = p["anteil_cents"] * max(0, -(-monate // abo["takt"]))
        schluessel = _schluessel(p)
        treffer = [{**zugeordnet[h], "art": "zugeordnet"}
                   for h in p["zahlungen"] if h in zugeordnet]
        treffer += [{k: e[k] for k in ("id", "hash", "datum", "cents", "konto")}
                    | {"art": "automatisch"}
                    for e in eingaenge
                    if e["datum"] >= beginn and e["cents"] == p["anteil_cents"]
                    and any(k in e["suchtext"] for k in schluessel)]
        gezaehlt = von_hand | verworfen | anderswo | {t["hash"] for t in treffer}
        zurueck = sum(t["cents"] for t in treffer)
        out.append({
            "name": p["name"], "seit": p["seit"], "soll": soll, "zurueck": zurueck,
            "offen": max(soll - zurueck, 0),
            "treffer": sorted(treffer, key=lambda t: t["datum"], reverse=True),
            "vorschlaege": [
                {k: e[k] for k in ("hash", "datum", "cents", "konto", "gegenpartei", "kategorie")}
                for e in alle
                if e["hash"] not in gezaehlt and any(k in e["suchtext"] for k in schluessel)][:5]})
    return out


def _schluessel(p: dict) -> list[str]:
    return [k for k in (normalize_counterparty(n) for n in [p["name"], *p["aliase"]])
            if k and len(k) >= 3]


def _eingaenge(conn: sqlite3.Connection, kategorie: str) -> list[dict]:
    """Eingaenge, die automatisch eine Rueckzahlung sein koennen.

    In der Kategorie des Abos ODER noch ohne Kategorie: eine Rueckzahlung, die
    heute eingelesen wurde, ist noch nicht einsortiert und soll trotzdem
    zaehlen. Umbuchungen nie -- die Auszahlung von PayPal aufs Girokonto
    traegt denselben Betrag wie die Rueckzahlung und waere sonst ein zweites
    Mal Geld zurueck.
    """
    rows = conn.execute(
        """SELECT t.id, t.dedup_hash, t.booking_date, t.account_id, s.amount_cents,
                  t.counterparty_norm, t.raw_text
           FROM   transactions t
           JOIN   splits s ON s.transaction_id = t.id
           WHERE  s.amount_cents > 0
             AND  (s.mgmt_category_id = ? OR s.mgmt_category_id IS NULL)
           ORDER  BY t.booking_date, t.id""", (kategorie,)).fetchall()
    return [{"id": r["id"], "hash": r["dedup_hash"],
             "datum": date.fromisoformat(r["booking_date"]),
             "konto": r["account_id"], "cents": r["amount_cents"],
             "suchtext": (r["counterparty_norm"] or "")
                         + (normalize_counterparty(r["raw_text"]) or "")}
            for r in rows]


def _alle_eingaenge(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT t.dedup_hash, t.booking_date, t.account_id, t.amount_cents,
                  t.counterparty_norm, t.raw_text, COALESCE(t.counterparty, '') AS gegenpartei,
                  s.mgmt_category_id AS kategorie
           FROM   transactions t JOIN splits s ON s.transaction_id = t.id AND s.seq = 0
           WHERE  t.amount_cents > 0
           ORDER  BY t.booking_date DESC""").fetchall()
    return [{"hash": r["dedup_hash"], "datum": date.fromisoformat(r["booking_date"]),
             "konto": r["account_id"], "cents": r["amount_cents"],
             "gegenpartei": r["gegenpartei"], "kategorie": r["kategorie"],
             "suchtext": (r["counterparty_norm"] or "")
                         + (normalize_counterparty(r["raw_text"]) or "")}
            for r in rows]


def _nach_hash(conn: sqlite3.Connection, hashes: set[str]) -> dict[str, dict]:
    if not hashes:
        return {}
    rows = conn.execute(
        f"""SELECT id, dedup_hash, booking_date, account_id, amount_cents
            FROM transactions WHERE dedup_hash IN ({','.join('?' * len(hashes))})""",
        sorted(hashes)).fetchall()
    return {r["dedup_hash"]: {"id": r["id"], "hash": r["dedup_hash"],
                              "datum": date.fromisoformat(r["booking_date"]),
                              "cents": r["amount_cents"], "konto": r["account_id"]}
            for r in rows}


def eingaenge(conn: sqlite3.Connection, suche: str, limit: int = 25) -> list[dict]:
    """Eingaenge zur Suche -- fuer eine Rueckzahlung, die von Hand zugeordnet wird."""
    muster = f"%{suche.strip()}%"
    kompakt = f"%{normalize_counterparty(suche) or suche.strip()}%"
    return [dict(r) for r in conn.execute(
        """SELECT t.dedup_hash, t.booking_date, t.account_id, t.amount_cents,
                  COALESCE(t.counterparty, '') AS gegenpartei,
                  substr(t.raw_text, 1, 90) AS text, s.mgmt_category_id AS kategorie
           FROM   transactions t JOIN splits s ON s.transaction_id = t.id AND s.seq = 0
           WHERE  t.amount_cents > 0 AND (t.raw_text LIKE ? OR t.counterparty_norm LIKE ?)
           ORDER  BY t.booking_date DESC LIMIT ?""", (muster, kompakt, limit))]


# -------------------------------------------------------- Seite: Buchungen

_BUCHUNG_SQL = """SELECT t.id, t.dedup_hash, t.booking_date, t.account_id,
                         t.amount_cents, t.counterparty_norm,
                         COALESCE(t.counterparty, '') AS gegenpartei,
                         substr(t.raw_text, 1, 90) AS text,
                         s.mgmt_category_id AS kategorie
                  FROM   transactions t
                  JOIN   splits s ON s.transaction_id = t.id AND s.seq = 0"""


def belege(conn: sqlite3.Connection, abo: dict) -> list[dict]:
    """Die zugeordneten Buchungen, juengste zuerst."""
    if not abo["buchungen"]:
        return []
    platz = ",".join("?" * len(abo["buchungen"]))
    return [dict(r) for r in conn.execute(
        f"{_BUCHUNG_SQL} WHERE t.dedup_hash IN ({platz}) "
        f"ORDER BY t.booking_date DESC", abo["buchungen"])]


def vorschlaege(conn: sqlite3.Connection, abo: dict, limit: int = 10) -> list[dict]:
    """Neuere Abbuchungen derselben Gegenpartei in der Kategorie des Abos.

    Die naechste Verlaengerung erscheint hier, sobald sie importiert ist.
    Solange sie nicht zugeordnet ist, zaehlt sie in der Prognose zusaetzlich
    -- deshalb steht sie sichtbar da, statt still mitzulaufen.

    DIE KATEGORIE IST NOETIG, nicht nur die Gegenpartei: unter
    "APPLE.COM/BILL" laufen Crunchyroll, iCloud und Claude gleichzeitig, und
    ohne sie stand bei Crunchyroll jeden Monat "neue Buchung". Und nur NACH
    dem juengsten Beleg -- was davor lag, ist keine neue Verlaengerung.
    """
    belegt = belege(conn, abo)
    namen = sorted({b["counterparty_norm"] for b in belegt if b["counterparty_norm"]})
    if not namen:
        return []
    return [dict(r) for r in conn.execute(
        f"{_BUCHUNG_SQL} WHERE t.amount_cents < 0 "
        f"AND t.counterparty_norm IN ({','.join('?' * len(namen))}) "
        f"AND s.mgmt_category_id = ? AND t.booking_date > ? "
        f"AND t.dedup_hash NOT IN ({','.join('?' * len(abo['buchungen']))}) "
        f"ORDER BY t.booking_date DESC LIMIT ?",
        [*namen, abo["kategorie"], belegt[0]["booking_date"], *abo["buchungen"], limit])]


def fruehere(conn: sqlite3.Connection, abo: dict) -> list[dict]:
    """Aeltere Abbuchungen derselben Gegenpartei in der Kategorie des Abos.

    Wer ein Abo anlegt, hakt meist die juengste Buchung an; die Monate davor
    zaehlen dann weiter im Kategoriemedian UND als Abo, also doppelt. Die
    Vorschlaege oben zeigen nur Neueres, deshalb stehen die frueheren hier --
    ohne Grenze, weil jede fehlende doppelt zaehlt. Ignorierte bleiben weg.
    """
    belegt = belege(conn, abo)
    namen = sorted({b["counterparty_norm"] for b in belegt if b["counterparty_norm"]})
    if not namen:
        return []
    bekannt = [*abo["buchungen"], *abo["ignoriert"]]
    return [dict(r) for r in conn.execute(
        f"{_BUCHUNG_SQL} WHERE t.amount_cents < 0 "
        f"AND t.counterparty_norm IN ({','.join('?' * len(namen))}) "
        f"AND s.mgmt_category_id = ? AND t.booking_date < ? "
        f"AND t.dedup_hash NOT IN ({','.join('?' * len(bekannt))}) "
        f"ORDER BY t.booking_date DESC",
        [*namen, abo["kategorie"], belegt[0]["booking_date"], *bekannt])]


def buchungen(conn: sqlite3.Connection, suche: str, limit: int = 25) -> list[dict]:
    """Abbuchungen zur Suche, jede mit einem Takt-Vorschlag."""
    muster = f"%{suche.strip()}%"
    kompakt = f"%{normalize_counterparty(suche) or suche.strip()}%"
    rows = conn.execute(
        f"{_BUCHUNG_SQL} WHERE t.amount_cents < 0 "
        f"AND (t.raw_text LIKE ? OR t.counterparty_norm LIKE ?) "
        f"ORDER BY t.booking_date DESC LIMIT ?", (muster, kompakt, limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["takt"] = takt_vorschlag(conn, r["counterparty_norm"], r["amount_cents"])
        out.append(d)
    return out


def takt_vorschlag(conn: sqlite3.Connection, gegenpartei: str | None,
                   betrag_cents: int) -> int | None:
    """Wie oft dieselbe Abbuchung bisher kam, als Takt.

    Median der Abstaende zwischen gleich hohen Buchungen derselben
    Gegenpartei, auf einen Teiler des Jahres gerundet. Eine einzige Buchung
    ergibt keinen Takt -- dann schlaegt die Seite nichts vor, statt zu raten.
    """
    if not gegenpartei:
        return None
    monate = sorted({r[0] for r in conn.execute(
        "SELECT substr(booking_date, 1, 7) FROM transactions "
        "WHERE counterparty_norm = ? AND amount_cents = ?",
        (gegenpartei, betrag_cents))})
    if len(monate) < 2:
        return None
    idx = [int(m[:4]) * 12 + int(m[5:7]) for m in monate]
    abstaende = sorted(b - a for a, b in itertools.pairwise(idx))
    gemessen = abstaende[len(abstaende) // 2]
    return min(TAKTE, key=lambda t: (abs(t - gemessen), t))


def preisabweichung(conn: sqlite3.Connection, abo: dict) -> dict | None:
    """Der juengste Beleg, wenn er anders hoch ist als der Betrag des Abos.

    Das ist zugleich die Pruefung eines Kaufs, der noch nicht im Auszug
    stand: bis er importiert und zugeordnet ist, ist der juengste Beleg der
    alte -- und der Unterschied bleibt sichtbar.
    """
    letzte = belege(conn, abo)
    if letzte and letzte[0]["amount_cents"] != abo["betrag_cents"]:
        return {"erwartet": abo["betrag_cents"], "gebucht": letzte[0]["amount_cents"],
                "datum": letzte[0]["booking_date"]}
    return None


# ------------------------------------------------------------------ Hilfen

def _monat_erster(jjjj_mm: str) -> date:
    return date(int(jjjj_mm[:4]), int(jjjj_mm[5:7]), 1)


def euro(cents: int) -> str:
    return format_eur(cents)
