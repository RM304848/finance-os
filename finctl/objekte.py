"""Objekte anlegen und entfernen -- ohne YAML von Hand.

`config/properties.yaml` traegt zu jedem Objekt seine Herleitung: die
AfA-Basis aus der Feststellungserklaerung, das Anschaffungsdatum aus dem
Notarvertrag, bei einem Leasehold den Restwert null am Ende der Laufzeit.
Dreissig Zeilen Begruendung je Eintrag, die als Notiz am Objekt stehen.

DREI FELDER. Ein Objekt anzulegen heisst hier: ihm eine Kennung geben, damit
Buchungen ihm zugeordnet werden koennen. Mehr nicht.

Der erste Entwurf fragte zusaetzlich nach dem Anschaffungsdatum und lehnte
ohne es ab, mit der Zehnjahresfrist des §23 EStG als Begruendung. Das war zu
viel: WAS ein Objekt gekostet hat, steht als einmaliger Betrag in der
Planung, und die kann das laengst -- `immobilie/kaufnebenkosten` mit
`frequenz: einmalig`. Zwei Stellen fuer dieselbe Zahl waeren zwei Wahrheiten,
und wer ein Objekt anlegt, hat den Notarvertrag nicht neben sich liegen.

Steuerfelder und Datum bleiben auf /immobilie, neben der Unterlage, aus der
sie stammen. Wer sie braucht, traegt sie dort ein; wer nicht, wird nicht
danach gefragt.

ENTFERNEN IST DER WICHTIGERE TEIL, wie bei den Krediten. Wer dieses Werkzeug
uebernimmt, erbt sonst fremde Wohnungen in seiner Vermoegensrechnung.

EINE DATEI. Seit Schritt 5 (N.3c) steht jedes Objekt nur in `properties.yaml`,
samt seiner Notiz -- auch die Zahlen, die /immobilie ablegt, und die Prognose.
Die Seite liest die Datei ganz und schreibt sie ganz (`dateien.yaml_schreiben`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from finctl.dateien import yaml_lesen, yaml_schreiben
from finctl.pfade import CONFIG_DIR

DATEI = "properties.yaml"

#: Was ein Objekt sein kann, und wie es auf der Seite heisst. Die Kennungen
#: stehen so in der Datenbank und in properties.yaml; die Beschriftung ist
#: deutsch, weil die Oberflaeche es ist.
ZUSTAENDE = {
    "rented": "vermietet",
    "owner_occupied": "selbst bewohnt",
    "construction": "im Bau",
    "sold": "verkauft",
}

#: Die Felder dieser Maske, in der Reihenfolge der Seite.
FELDER = ("id", "name", "status")

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


def _yaml(pfad: Path) -> dict:
    if not pfad.exists():
        return {}
    return yaml_lesen(pfad) or {}


def objekt(felder: dict) -> dict:
    """Aus den Angaben der Maske ein Eintrag, wie ihn `init` einliest."""
    return {
        "id": str(felder.get("id") or "").strip(),
        "name": str(felder.get("name") or "").strip(),
        "status": str(felder.get("status") or "").strip(),
    }


def lesen(config_dir: Path | None = None) -> dict:
    """Die ganze `properties.yaml` als Zuordnung; leer, wo es sie nicht gibt."""
    return _yaml((config_dir or CONFIG_DIR) / DATEI)


def aus_spec(spec: dict) -> dict[str, dict]:
    """Alle Objekte einer gelesenen `properties.yaml`, nach Kennung."""
    return {str(p.get("id")): dict(p) for p in (spec.get("properties") or [])
            if isinstance(p, dict) and p.get("id")}


def vorhandene(config_dir: Path | None = None) -> dict[str, dict]:
    """Alle Objekte der Datei, nach Kennung."""
    return aus_spec(lesen(config_dir))


def pruefen(eintrag: dict, vergeben: set[str]) -> list[str]:
    """Was an diesem Objekt nicht stimmt, in Worten. Leer heisst: in Ordnung."""
    fehler = []
    kennung = eintrag.get("id") or ""
    if not _ID.match(kennung):
        fehler.append("Kennung: klein, Ziffern und Bindestriche, "
                      "höchstens 41 Zeichen")
    elif kennung in vergeben:
        fehler.append(f"Kennung „{kennung}“ ist schon vergeben")
    if not eintrag.get("name"):
        fehler.append("Name fehlt")
    if eintrag.get("status") not in ZUSTAENDE:
        fehler.append("Zustand: " + ", ".join(ZUSTAENDE.values()))
    return fehler


# ------------------------------------------------------------------ schreiben

def speichern(spec: dict, config_dir: Path | None = None) -> bool:
    """Die ganze Datei schreiben, samt Notizen. `True`, wenn sie sich aenderte."""
    config_dir = config_dir or CONFIG_DIR
    config_dir.mkdir(parents=True, exist_ok=True)
    return yaml_schreiben(config_dir / DATEI, spec)


def _eintrag(spec: dict, kennung: str) -> dict | None:
    """Der Eintrag eines Objekts in der gelesenen Datei (dieselbe Zuordnung, nicht eine Kopie)."""
    return next((p for p in spec.get("properties") or []
                 if isinstance(p, dict) and str(p.get("id")) == kennung), None)


def anlegen(felder: dict, config_dir: Path | None = None) -> dict:
    """Ein Objekt anlegen: ein neuer Eintrag hinter den vorhandenen."""
    config_dir = config_dir or CONFIG_DIR
    neu = objekt(felder)
    spec = lesen(config_dir)
    fehler = pruefen(neu, set(aus_spec(spec)))
    if fehler:
        raise ValueError("; ".join(fehler))

    spec.setdefault("properties", []).append({f: v for f, v in neu.items() if v is not None})
    speichern(spec, config_dir)
    return neu


def entfernen(kennung: str, config_dir: Path | None = None) -> None:
    """Ein Objekt aus der Datei nehmen -- mit seiner Notiz."""
    config_dir = config_dir or CONFIG_DIR
    spec = lesen(config_dir)
    if _eintrag(spec, kennung) is None:
        raise ValueError(f"Kein Objekt „{kennung}“")
    spec["properties"] = [p for p in spec["properties"]
                          if not (isinstance(p, dict) and str(p.get("id")) == kennung)]
    speichern(spec, config_dir)


#: Die Felder eines Objekts, die `in_db` in die Tabelle `properties` spiegelt.
DB_FELDER = frozenset({
    "purchase_price_cents", "incidental_costs_cents", "equity_cents", "land_share_pct",
    "afa_rate_pct", "afa_start", "acquired_on", "planned_sale_on", "sale_price_cents",
    "sold_on"})


def in_db(conn, config_dir: Path | None = None) -> None:
    """Die Zahlen der Objekte aus `properties.yaml` in die Tabelle `properties` spiegeln.

    Beim `init` aufgerufen, nachdem die Zeilen angelegt sind: Die Datei gewinnt, wo sie
    etwas sagt (`init` kennt `sold_on` nicht und nimmt die uebrigen mit COALESCE). Die
    Zahlen sind nirgends gebucht; ohne die Datei liessen sie sich nicht wiederherstellen.
    """
    for kennung, eintrag in vorhandene(config_dir).items():
        setzbar = {k: (str(v) if hasattr(v, "isoformat") else v)
                   for k, v in eintrag.items() if k in DB_FELDER and v is not None}
        if setzbar:
            zuweisung = ", ".join(f"{k} = ?" for k in setzbar)
            conn.execute(f"UPDATE properties SET {zuweisung} WHERE id = ?",
                         (*setzbar.values(), kennung))
    conn.commit()


def felder_setzen(kennung: str, felder: dict, config_dir: Path | None = None) -> bool:
    """Zahlen und Daten, die /immobilie ablegt, am Objekt setzen.

    `True`, wenn die Datei sich aenderte.

    Ein leeres Feld (`None` oder Text ohne Inhalt) nimmt die Angabe heraus. Die Zahlen,
    die nirgends gebucht sind -- was gezahlt wurde, was eingesetzt ist, was beim Verkauf
    erwartet wird --, stehen so in der Datei und ueberstehen eine neu gebaute Datenbank.
    """
    config_dir = config_dir or CONFIG_DIR
    spec = lesen(config_dir)
    eintrag = _eintrag(spec, kennung)
    if eintrag is None:
        raise ValueError(f"Kein Objekt „{kennung}“ in {DATEI}")
    for feld, wert in felder.items():
        if wert in (None, ""):
            eintrag.pop(feld, None)
        else:
            eintrag[feld] = wert
    return speichern(spec, config_dir)


# ------------------------------------------------------------------ Prognose

#: Die Felder einer Objektprognose, wie sie auf /immobilie/<id> stehen und in
#: `prognose:` eines Objekts gespeichert werden.
PROGNOSE_FELDER = ("miete_monatlich_cents", "kosten_monatlich_cents", "ab", "bis")


@dataclass(frozen=True, slots=True)
class Prognose:
    """Was ein Objekt kuenftig abwirft -- angenommen statt gemessen.

    Ein Objekt bekommt eine Prognose, wenn die Messung es nicht tragen kann:
    ein Monat Miete im Ledger, ueber ein Jahr gemittelt, waere ein Zwoelftel
    des Ertrags, und zwanzig Jahre fortgeschrieben der groesste stille Fehler
    der Hochrechnung. Objekte ohne Prognose bleiben gemessen.
    """

    id: str
    name: str
    miete_cents: int
    kosten_cents: int
    #: Erster und letzter Monat. None heisst: offen.
    ab: date | None = None
    bis: date | None = None
    saison: tuple[float, ...] = (1.0,) * 12

    @property
    def netto_cents(self) -> int:
        return self.miete_cents - self.kosten_cents

    def laeuft(self, monat: date) -> bool:
        erster = date(monat.year, monat.month, 1)
        if self.ab and erster < date(self.ab.year, self.ab.month, 1):
            return False
        return not (self.bis and erster > date(self.bis.year, self.bis.month, 1))


def als_monat(wert) -> date | None:
    """YAML liefert ein Datum mal geparst, mal als "2026-09"."""
    if not wert:
        return None
    if isinstance(wert, date):
        return wert
    text = str(wert)
    return date.fromisoformat(text + "-01" if len(text) == 7 else text[:10])


def saison(roh, wo: str = "prognose.saison") -> tuple[float, ...]:
    """Zwoelf Monatsfaktoren, die sich auf 12 summieren.

    Saisonalitaet verschiebt Geld zwischen Monaten, sie erfindet und
    vernichtet keines. Eine Kurve, die sich nebenbei auf 13 summiert, waere
    eine verdeckte Ertragsannahme.
    """
    faktoren = tuple(float(x) for x in (roh if roh is not None else [1.0] * 12))
    if len(faktoren) != 12:
        raise ValueError(f"{wo} hat {len(faktoren)} Werte, gebraucht werden 12 "
                         f"-- einer je Monat.")
    if abs(sum(faktoren) - 12.0) > 0.01:
        raise ValueError(f"{wo} summiert sich auf {sum(faktoren):.2f} statt auf 12. "
                         f"Saisonalitaet verschiebt Geld zwischen Monaten; eine "
                         f"abweichende Summe waere eine verdeckte Ertragsannahme.")
    return faktoren


def _szenario_objekte(szenario: Path | str | None) -> dict[str, dict]:
    """Was eine Szenariodatei je Objekt anders annimmt.

    Unter `immobilien.objekte.<kennung>` in einer Kopie von assumptions.yaml.
    Nur die Groessen, die das Szenario bewegt -- Beginn und Ende der
    Vermietung sind Fakten des Objekts und bleiben dort.
    """
    if szenario is None:
        return {}
    roh = _yaml(Path(szenario)).get("immobilien") or {}
    return dict(roh.get("objekte") or {})


def prognosen(szenario: Path | str | None = None,
              config_dir: Path | None = None) -> list[Prognose]:
    """Alle Objekte mit Prognose, in der Reihenfolge der Konfiguration.

    Aus `properties.yaml` (auch was auf /immobilie/<id> getippt wurde), darueber ein
    Szenario. Wer kein Objekt hat oder keines mit Prognose, bekommt eine leere
    Liste -- der Normalfall.
    """
    anders = _szenario_objekte(szenario)
    aus = []
    for kennung, eintrag in vorhandene(config_dir).items():
        if eintrag.get("status") == "sold":
            continue
        p = {**(eintrag.get("prognose") or {}), **(anders.get(kennung) or {})}
        if not p:
            continue
        if not _ID.match(kennung):
            raise ValueError(f"Objekt {kennung!r}: die Kennung geht in SQL ein -- "
                             f"erlaubt sind Kleinbuchstaben, Ziffern und Strich.")
        aus.append(Prognose(
            id=kennung, name=str(eintrag.get("name") or kennung),
            miete_cents=int(p.get("miete_monatlich_cents") or 0),
            kosten_cents=int(p.get("kosten_monatlich_cents") or 0),
            ab=als_monat(p.get("ab")), bis=als_monat(p.get("bis")),
            saison=saison(p.get("saison"), f"{kennung}.prognose.saison")))
    return aus


def _prognosewert(feld: str, wert):
    if wert in (None, ""):
        return None
    if feld in ("ab", "bis"):
        if not re.fullmatch(r"\d{4}-\d{2}", str(wert)):
            raise ValueError(f"{feld}: Monat als JJJJ-MM")
        return str(wert)
    cents = int(wert)
    if cents < 0:
        raise ValueError(f"{feld}: ohne Vorzeichen eintragen")
    return cents


def prognose_setzen(kennung: str, felder: dict,
                    config_dir: Path | None = None) -> dict:
    """Die Prognose eines Objekts aus der Seite speichern.

    In den Eintrag des Objekts, Feld fuer Feld: Was die Seite nicht nennt, bleibt (auch die
    Saison). Ein leeres Feld nimmt die Angabe heraus. Ein Wert, der dem entspricht, was
    schon dasteht, aendert nichts -- ein Monat steht als `2026-09` oder als Datum.
    """
    config_dir = config_dir or CONFIG_DIR
    spec = lesen(config_dir)
    eintrag = _eintrag(spec, kennung)
    if eintrag is None:
        raise ValueError(f"Kein Objekt „{kennung}“")
    prognose = dict(eintrag.get("prognose") or {})
    for feld in PROGNOSE_FELDER:
        if feld not in felder:
            continue
        wert = _prognosewert(feld, felder[feld])
        bisher = prognose.get(feld)
        if feld in ("ab", "bis") and bisher:
            bisher = als_monat(bisher).strftime("%Y-%m")
        if wert is None:
            prognose.pop(feld, None)
        elif wert != bisher:
            prognose[feld] = wert
    if prognose != (eintrag.get("prognose") or {}):
        if prognose:
            eintrag["prognose"] = prognose
        else:
            eintrag.pop("prognose", None)
        speichern(spec, config_dir)
    return prognose
