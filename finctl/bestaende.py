"""Bestaende: getippt, wo kein Auszug etwas weiss -- belegt, wo einer es tut.

KONTEN MIT EINGELESENEN AUSZUEGEN KOMMEN NUR AUS DEM AUSZUG -- die
Girokonten und das Tagesgeld. Ihr Wert in balances.yaml war ein
getippter Livestand -- "Auszugsende plus Verkaufserloes" --, und
ein getippter Stand eines Kontos, dessen Auszuege eingelesen werden, ist eine
zweite Wahrheit neben der belegten. /konten rechnete vom Auszug, /ziele vom
getippten Wert, und beide hiessen "Stand".

Wert und Stichtag eines solchen Kontos sind deshalb der Saldo am STICHTAG: dem
letzten Monatsende, das die Auszuege ALLER Konten ganz abdecken -- derselbe
Tag, an dem /konten beginnt. Wie weit der neueste Auszug schon reicht, steht
daneben, zaehlt aber nicht. Ueberschreiben laesst sich beides nicht.

Welche das sind, sagt nicht die Art (giro, tagesgeld), sondern ob das Konto
geparst wird: Ein Tagesgeld kann Auszuege haben, und ein getippter Stand
neben dem belegten waere dort dieselbe zweite Wahrheit.
Alle anderen Positionen -- Depots, Krypto, Renten, Konten ohne Parser --
bleiben genannt und ueberschreibbar wie bisher.

DER VERLAUF. Ein getippter Stand ueberschrieb bisher den alten, und damit war
weg, was das Depot am Monatsende davor war. Wer ausrechnen will, wie sich eine
Zahl der Hochrechnung seit dem Vormonat bewegt hat (`forecast/wirkung`), braucht
diesen Stand. Deshalb bleibt je Position und Periode des Monatsabschlusses ein
Eintrag stehen, in `balances.yaml` unter `verlauf`. Das ist kein
gespeicherter Rechenstand, der veralten kann, sondern ein Beleg: "im
Abschluss 09/2026 stand das Depot bei X". Belegte Staende kommen weiter aus dem
Auszug; `zum` fuegt beides fuer einen frueheren Stichtag zusammen.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from finctl import notizen as _notizen
from finctl.dateien import yaml_lesen
from finctl.ledger import kontostand as _ks
from finctl.pfade import CONFIG_DIR

#: Wie die Notiz einer Position bisher hiess; `notiz` gilt vor ihm (`finctl/notizen.py`).
NOTIZ_ALT = ("note",)

#: Was eine Rentenversicherung zusaetzlich zu ihrem Stand aus der Mitteilung hat.
#: `rueckkauf_policenwert_cents` ist ihr Policenwert laut derselben Mitteilung: ohne
#: ihn laesst sich das Verhaeltnis zum Policenwert nicht bilden, sobald der neuer ist.
RUECKKAUF_FELDER = ("rueckkauf_cents", "rueckkauf_as_of", "eingezahlt_cents",
                    "rueckkauf_policenwert_cents")


@dataclass(frozen=True, slots=True)
class Rueckkauf:
    """Was die Versicherung bei einer Kuendigung zahlen wuerde, laut Mitteilung."""

    cents: int
    as_of: date
    #: Summe der gezahlten Beitraege; None, wenn die Mitteilung sie nicht nennt.
    eingezahlt_cents: int | None
    #: Der Policenwert laut derselben Mitteilung; None, wo er nicht eigens genannt ist.
    policenwert_cents: int | None = None


def rueckkauf(zeile: dict) -> Rueckkauf | None:
    """Der Rueckkaufswert einer Position der Bestandsart Rentenversicherung.

    None bei jeder anderen Bestandsart und bei einer Police ohne Rueckkaufswert.
    Ein Rueckkaufswert ohne Datum oder ein negativer Betrag ist ein Fehler beim
    Lesen. Gerechnet wird damit hier nichts.
    """
    if str(zeile.get("kind") or "").strip().lower() != "rentenversicherung":
        return None
    name = zeile.get("name") or zeile.get("account_id") or "?"
    cents, tag, einzahlt, basis = (zeile.get(f) for f in RUECKKAUF_FELDER)
    if cents in (None, ""):
        if tag or any(w not in (None, "") for w in (einzahlt, basis)):
            raise ValueError(f"balances, {name}: rueckkauf_cents fehlt")
        return None
    stand = _tag(tag)
    try:
        cents = int(cents)
        einzahlt = None if einzahlt in (None, "") else int(einzahlt)
        basis = None if basis in (None, "") else int(basis)
    except (TypeError, ValueError):
        raise ValueError(f"balances, {name}: Rueckkaufswert, eingezahlt und Policenwert "
                         "der Mitteilung als Cent") from None
    if stand is None or cents < 0 or any(w is not None and w < 0 for w in (einzahlt, basis)):
        raise ValueError(f"balances, {name}: rueckkauf_as_of (JJJJ-MM-TT) fehlt "
                         "oder ein Betrag ist negativ")
    if basis == 0:
        raise ValueError(f"balances, {name}: der Policenwert der Mitteilung ist null")
    return Rueckkauf(cents=cents, as_of=stand, eingezahlt_cents=einzahlt,
                     policenwert_cents=basis)


@dataclass(frozen=True, slots=True)
class Notfallwert:
    """Was eine Police bei einer Kuendigung nach Steuer brachte. Nur zur Anzeige:
    er zaehlt weder zum Notgroschen noch zum liquiden Vermoegen."""

    cents: int
    #: Der Rueckkaufswert, auf den Policenwert der Zeile gebracht (sonst der der Mitteilung).
    rueckkauf_cents: int
    steuer_cents: int
    #: Der Gewinn, auf den die Steuer faellt. None: `eingezahlt` fehlt, dann ist die
    #: Steuer auf den ganzen Rueckkaufswert gerechnet und der Notfallwert eine Untergrenze.
    ertrag_cents: int | None
    eingezahlt_cents: int | None
    mitteilung_cents: int
    #: Stand der Mitteilung.
    stand: date
    #: Rueckkaufswert durch Policenwert der Mitteilung, wo es angewandt wurde,
    #: und dieser Policenwert selbst.
    quote: float | None
    basis_cents: int | None
    #: Der Policenwert der Zeile ist neuer als die Mitteilung, ihr eigener Policenwert
    #: aber nicht bekannt: der Rueckkaufswert steht unveraendert auf seinem Stand.
    verhaeltnis_fehlt: bool


def notfallwert(zeile: dict, steuersatz: float) -> Notfallwert | None:
    """Der Notfallwert einer Position der Bestandsart Rentenversicherung, sonst None.

    Rueckkaufswert minus Steuer auf `max(Rueckkaufswert - eingezahlt, 0)`. Ist der
    Policenwert der Zeile neuer als die Mitteilung, gilt das Verhaeltnis aus
    Rueckkaufswert und Policenwert DER MITTEILUNG, angewandt auf den Policenwert der
    Zeile; ohne den Policenwert der Mitteilung bleibt der Rueckkaufswert auf seinem
    Stand. `eingezahlt` stammt aus der Mitteilung und wird nicht fortgeschrieben:
    Beitraege seither zaehlen als Ertrag, die Steuer faellt eher zu hoch aus.
    """
    r = rueckkauf(zeile)
    if r is None:
        return None
    policenwert, stand = zeile.get("cents"), _tag(zeile.get("as_of"))
    basis = r.policenwert_cents
    if basis is None and stand == r.as_of:
        basis = policenwert
    neuer = policenwert is not None and stand is not None and stand > r.as_of
    wert, quote = r.cents, None
    if neuer and basis:
        quote = r.cents / basis
        wert = round(r.cents * int(policenwert) / basis)
    ertrag = None if r.eingezahlt_cents is None else max(wert - r.eingezahlt_cents, 0)
    steuer = round((wert if ertrag is None else ertrag) * steuersatz)
    return Notfallwert(
        cents=wert - steuer, rueckkauf_cents=wert, steuer_cents=steuer,
        ertrag_cents=ertrag, eingezahlt_cents=r.eingezahlt_cents,
        mitteilung_cents=r.cents, stand=r.as_of, quote=quote,
        basis_cents=basis if quote is not None else None,
        verhaeltnis_fehlt=neuer and not basis)


def policenwert_festhalten(vorher: dict, eintrag: dict) -> None:
    """Haelt im Eintrag fest, zu welchem Policenwert der Rueckkaufswert gehoerte.

    Aendert ein Speichern den Policenwert einer Police, deren Rueckkaufswert zu
    ihrem bisherigen Stand gehoert, ohne dass der Policenwert der Mitteilung eigens
    genannt ist, sonst ginge das Verhaeltnis mit dem alten Wert verloren. Bleibt der
    Rueckkaufswert nicht derselbe, ist er eine neue Mitteilung und braucht das nicht.
    """
    r = rueckkauf(vorher)
    if r is None or r.policenwert_cents is not None or vorher.get("cents") is None:
        return
    nachher = rueckkauf({**vorher, **eintrag})
    if nachher is None or (nachher.cents, nachher.as_of) != (r.cents, r.as_of):
        return
    neu = {**vorher, **eintrag}
    geaendert = (neu.get("cents") != vorher.get("cents")
                 or _tag(neu.get("as_of")) != _tag(vorher.get("as_of")))
    if geaendert and _tag(vorher.get("as_of")) == r.as_of:
        eintrag["rueckkauf_policenwert_cents"] = int(vorher["cents"])


def spiegeln(conn: sqlite3.Connection, spec: dict) -> None:
    """Die getippten Staende aus `balances.yaml` als Schnappschuesse in die Datenbank.

    Jede Position mit Betrag steht unter ihrem eigenen Datum, sonst unter dem der Datei. So
    findet die Prognose fuer ein Konto ohne Auszug den juengsten Stand bis zu ihrem Stichtag
    (`konten.account_forecast`, `bestaende.auszugsstaende`), auch einen, den die Seite spaeter
    eintrug. Die Datei gehoert diesen Zeilen ganz: Was als `manual` in der Datenbank steht,
    wird zuerst geloescht, damit ein Eintrag, der aus der Datei verschwand, nicht liegenbleibt.
    """
    as_of = str(spec.get("as_of") or "")[:10]
    known = {r["id"] for r in conn.execute("SELECT id FROM accounts")}
    conn.execute("DELETE FROM balance_snapshots WHERE source = 'manual'")
    for bal in spec.get("balances") or []:
        acct = bal.get("account_id") if isinstance(bal, dict) else None
        if not acct or acct not in known:
            continue
        tag = str(bal.get("as_of") or as_of)[:10]
        if not tag:
            continue
        # Ein bewusst offener Wert ist keine Null und kein Fehler.
        # balances.yaml fuehrt einen Bestand mit `cents: null` und der
        # Begruendung "OFFEN: Wert zum Verkaufszeitpunkt" -- und daran
        # brach `finctl init` mit einem TypeError ab, mitten im Lauf,
        # nachdem Konten und Objekte schon geschrieben waren. Ein
        # dokumentiertes Unbekanntes darf den Import nicht anhalten.
        if bal.get("cents") is None:
            continue
        conn.execute(
            """
            INSERT INTO balance_snapshots (account_id, as_of, balance_cents, source)
            VALUES (?,?,?,'manual')
            ON CONFLICT(account_id, as_of) DO UPDATE SET
                balance_cents = excluded.balance_cents
            """,
            (acct, tag, int(bal["cents"])),
        )


def anker_eintrag(conn: sqlite3.Connection, spec: dict, konto: str) -> dict | None:
    """Der Eintrag in `balances.yaml` fuer den Kontostand eines Kontos ohne Saldo im Export.

    Gibt es ihn noch nicht, wird er angelegt (und gehoert damit zu `spec`). None, wenn
    es das Konto nicht gibt.
    """
    eintrag = position(spec, konto)
    if eintrag is not None:
        return eintrag
    k = conn.execute("SELECT display_name, account_type FROM accounts WHERE id = ?",
                     (konto,)).fetchone()
    if k is None:
        return None
    eintrag = {"account_id": konto, "name": k["display_name"] or konto,
               "kind": k["account_type"] or "giro"}
    liste = spec.get("balances") or []
    liste.append(eintrag)
    spec["balances"] = liste
    return eintrag


def geparste_konten(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT id FROM accounts WHERE ingest_mode = 'parsed'")}


def aus_auszug(item: dict, geparst: set[str]) -> bool:
    """Kommt diese Position aus dem Auszug -- und ist damit nicht ueberschreibbar?"""
    return str(item.get("account_id") or "") in geparst


def auszugsstaende(conn: sqlite3.Connection, konten: list[str]) -> dict[str, dict]:
    """Je Konto: Saldo am Stichtag, der Stichtag, und bis wann der Auszug reicht.

    Ein Konto, das Auszuege liest, aber noch keinen hat, nimmt den juengsten getippten
    Stand bis zum Stichtag (`balance_snapshots`, von `finctl init` aus `balances.yaml`
    gespiegelt) -- denselben, den das Monatsmodell nimmt (`konten.account_forecast`). Ein
    Stand nach dem Stichtag zaehlt nicht. Ohne beides bleibt der Betrag leer. Traegt der Export
    eines Kontos keinen Saldo (`ledger/kontostand.py`), rechnet der Betrag von einem
    eingetragenen Stand aus und ist leer, solange keiner da ist.
    """
    from finctl.forecast import stichtag as _st

    stichtag = _st.stichtag(conn)
    out = {}
    for konto in konten:
        bis = conn.execute(
            "SELECT MAX(period_end) FROM statements WHERE account_id = ? "
            "AND status = 'imported'", (konto,)).fetchone()[0]
        if bis:
            out[konto] = {"cents": _st.saldo_zum(conn, konto, stichtag),
                          "as_of": stichtag.isoformat(), "auszug_bis": bis}
            if _ks.ohne_saldo(conn, konto):
                # Der Export traegt keinen Saldo: der Stand kommt von dem, den der Nutzer
                # eingetragen hat, und der steht hier zum Aendern bereit.
                a = _ks.anker(conn, konto, stichtag)
                out[konto].update(ohne_saldo=True, anker_cents=a[1] if a else None,
                                  anker_as_of=a[0].isoformat() if a else "")
            continue
        stand = conn.execute(
            "SELECT balance_cents, as_of FROM balance_snapshots WHERE account_id = ? "
            "AND as_of <= ? ORDER BY as_of DESC LIMIT 1",
            (konto, stichtag.isoformat())).fetchone()
        out[konto] = {"cents": int(stand["balance_cents"]) if stand else None,
                      "as_of": stand["as_of"] if stand else "", "auszug_bis": ""}
    return out


def kennung(name: str) -> str:
    """Der Schluessel einer Verpflichtung: ihr Name, kleingeschrieben."""
    import re

    return re.sub(r"[^a-z0-9]+", "-", str(name).strip().lower()).strip("-")


#: Die Datei der Positionen, Verpflichtungen und des Verlaufs: eine, die die Seiten ganz
#: schreiben.
DATEI = "balances.yaml"


def lesen(pfad: Path | None = None) -> dict:
    """`balances.yaml`: die Positionen, die Verpflichtungen und der Verlauf, wie sie stehen.

    An einer Stelle gelesen statt in jedem Aufrufer. Der Monatsabschluss las die Eintraege
    der Seite einmal gar nicht -- dort zaehlte ein gerade abgelegter Stand deshalb nicht als
    abgelegt.
    """

    quelle = pfad or CONFIG_DIR / DATEI
    return (yaml_lesen(quelle) or {}) if quelle.exists() else {}


def verlauf(spec: dict) -> dict:
    """Der Verlauf in der Datei: je Position und Periode der Stand, der damals getippt wurde."""
    return _notizen.ohne(spec.get("verlauf"))


def position(spec: dict, schluessel_: str) -> dict | None:
    """Der Eintrag einer Position in der Datei -- das Objekt selbst, oder `None`."""
    return next((e for e in spec.get("balances") or []
                 if isinstance(e, dict) and schluessel(e) == schluessel_), None)


def verpflichtung(spec: dict, kennung_: str) -> dict | None:
    """Der Eintrag einer Verpflichtung in der Datei -- das Objekt selbst, oder `None`."""
    return next((e for e in spec.get("obligations") or []
                 if isinstance(e, dict) and kennung(e.get("name") or "") == kennung_), None)


def verpflichtungen(spec: dict) -> list[dict]:
    """Die Verbindlichkeiten aus der Datei, mit der Kennung, unter der man sie anspricht.

    Geschluesselt ueber den Namen, weil die Datei eine Liste fuehrt und eine Liste keinen
    Schluessel hat. Eine getilgte Verbindlichkeit steht nicht mehr darin.
    """
    out = []
    for eintrag in spec.get("obligations") or []:
        if not isinstance(eintrag, dict):
            continue
        zeile = {**eintrag, "kennung": kennung(eintrag.get("name") or "")}
        out.append(_notizen.in_zeile(
            zeile, _notizen.lesen(eintrag, alt=NOTIZ_ALT), NOTIZ_ALT))
    return out


def zusammenfuehren(conn: sqlite3.Connection, spec: dict) -> dict:
    """Die Datei, mit den Staenden der Konten mit Auszug aus dem Auszug.

    Eine Stelle statt vier: /ziele, /annahmen, der Monatsabschluss und die
    Bestaendeseite fuehrten dieselbe Zusammenfuehrung je fuer sich. Wo es einen Auszug gibt,
    gilt nur er: Wert und Stichtag eines solchen Kontos stehen nie in der Datei.
    """
    items = spec.get("balances") or []
    geparst = geparste_konten(conn)
    staende = auszugsstaende(conn, [i["account_id"] for i in items
                                    if aus_auszug(i, geparst)])
    out = []
    for item in items:
        row = dict(item)
        if aus_auszug(row, geparst):
            stand = staende[row["account_id"]]
            row.update(cents=stand["cents"], as_of=stand["as_of"],
                       auszug_bis=stand["auszug_bis"], aus_auszug=True)
        # DIE NOTIZ GILT AUCH FUER KONTEN MIT AUSZUG. Der Wert ist belegt, die
        # Notiz ist eine Aussage des Eigentuemers -- "davon gehoert ein Teil
        # jemand anderem" steht in keinem Auszug und muss trotzdem aenderbar
        # sein, sonst lebt sie fuer immer in einer Datei.
        _notizen.in_zeile(row, _notizen.lesen(row, alt=NOTIZ_ALT), NOTIZ_ALT)
        rueckkauf(row)              # ein falsches Feld faellt hier auf, nicht in der Anzeige
        out.append(row)
    return {**spec, "balances": out, "obligations": verpflichtungen(spec)}


# ------------------------------------------------------------------- Verlauf

def schluessel(zeile: dict) -> str:
    """Wie eine Position in `balances.yaml` und im Verlauf heisst."""
    return str(zeile.get("account_id") or zeile.get("name") or "")


def periode(kind: str | None, tag: date) -> str:
    """Die Periode des Monatsabschlusses, zu der ein Stand gehoert.

    Der Monat, in dem er abgelegt wird: Im Abschluss 2026-10 steht der Stand
    vom Ende des Septembers. Bei einer Rentenversicherung das Jahr, denn ihre
    Standmitteilung kommt einmal im Jahr (`monatsabschluss.bestaende`).
    """
    jaehrlich = str(kind or "").strip().lower() == "rentenversicherung"
    return f"{tag:%Y}" if jaehrlich else f"{tag:%Y-%m}"


def _tag(wert) -> date | None:
    if isinstance(wert, date):
        return wert
    try:
        return date.fromisoformat(str(wert)[:10]) if wert else None
    except ValueError:
        return None


def stand_von(zeile: dict, vorgabe=None) -> dict | None:
    """Was eine Zeile aus `zusammenfuehren` im Verlauf festhaelt.

    Betrag, Datum und, wo bekannt, der Gewinn im Wert -- die drei Dinge, die
    zusammen EINEN getippten Stand ausmachen. `vorgabe` ist das Datum der
    Datei fuer Positionen ohne eigenes. None fuer eine Zeile, die aus dem
    Auszug kommt, ohne Betrag oder ohne Datum ist.
    """
    tag = _tag(zeile.get("as_of")) or _tag(vorgabe)
    if zeile.get("aus_auszug") or zeile.get("cents") is None or tag is None:
        return None
    out = {"cents": int(zeile["cents"]), "as_of": tag.isoformat()}
    if zeile.get("gewinn_cents") is not None:
        out["gewinn_cents"] = int(zeile["gewinn_cents"])
    return out


def verlauf_fortschreiben(spec: dict, vorher: dict, nachher: dict, key: str,
                          heute: date) -> bool:
    """Haelt in `spec["verlauf"]` fest, was ein Speichern am Stand von `key` aendert.

    `vorher` und `nachher` sind `zusammenfuehren` vor und nach dem Speichern.
    Aendert es den Stand der Position nicht (nur die Notiz, oder derselbe Wert
    noch einmal), geschieht nichts: Speichern ohne Aenderung schreibt den
    Verlauf nicht neu. Zweimal in derselben Periode: der spaetere Eintrag gilt.

    Einmalig, solange es noch keinen Verlauf gibt, kommt der Stand von VORHER
    jeder getippten Position dazu, unter der Periode seines Datums. Sonst haette
    der naechste Abschluss keinen Vormonat, mit dem er sich vergleichen laesst.
    Wer nie speichert, schreibt auch das nicht.

    Gibt zurueck, ob `spec` sich geaendert hat.
    """
    vorgabe = spec.get("as_of")
    alt = {schluessel(z): z for z in vorher.get("balances") or []}
    zeile = next((z for z in nachher.get("balances") or [] if schluessel(z) == key), None)
    stand = stand_von(zeile, vorgabe) if zeile else None
    if stand is None or stand == stand_von(alt.get(key) or {}, vorgabe):
        return False
    if not spec.get("verlauf"):
        spec["verlauf"] = {}
        for k, z in alt.items():
            damals = stand_von(z, vorgabe)
            if damals:
                spec["verlauf"].setdefault(k, {})[
                    periode(z.get("kind"), _tag(damals["as_of"]))] = damals
    spec["verlauf"].setdefault(key, {})[periode(zeile.get("kind"), heute)] = stand
    return True


def zum(conn: sqlite3.Connection, stichtag: date, spec: dict | None = None) -> dict:
    """Die Bestaende zu einem frueheren Stichtag.

    Belegte aus dem Hauptbuch (`stichtag.saldo_zum`), getippte aus dem Verlauf:
    der Eintrag der Periode, in der der Abschluss fuer diesen Stichtag gemacht
    wurde, also des Monats danach. Gleiche Form wie `zusammenfuehren`, damit
    `ziele.toepfe` und die anderen sie lesen wie die von heute; Verpflichtungen
    stehen, wie sie heute stehen.

    Hat eine getippte Position heute einen Stand, zu diesem Stichtag aber
    keinen Eintrag, steht sie in `fehlt` (mit dem Namen, wie die Seite sie
    nennt) und NICHT in `balances`: ein Stand, den niemand kennt, zaehlt nicht
    als null. Eine Position, die heute keinen Betrag hat, braucht auch damals
    keinen.

    Ebenso ein Konto aus dem Auszug, dessen erster Auszug erst NACH dem Stichtag
    beginnt -- es wurde nur spaeter eingelesen, und sein Anfangsstand erschiene
    sonst als Zufluss des Monats. Beginnt dieser erste Auszug mit Saldo null,
    war das Konto wirklich leer und zaehlt als null. Das gilt einen Monat lang;
    danach haben beide Stichtage Auszuege.

    `fehlt_grund` sagt je Name, woran es liegt ("stand": kein Eintrag im
    Verlauf, "konto": spaeter eingelesen), und `fehlt_ab` ab welchem Stichtag
    jede dieser Luecken geschlossen ist -- bei einem Stand, sobald sein
    naechster Eintrag eine Periode abdeckt, sonst unter der Annahme, dass er im
    naechsten Abschluss eingetragen wird. None, wenn nichts fehlt.
    """
    from finctl.forecast import abgleich as _ag
    from finctl.forecast import stichtag as _st

    if spec is None:
        spec = lesen()
    folge = _ag.folgetag(stichtag)
    ende = folge - timedelta(days=1)
    heute = zusammenfuehren(conn, spec)
    belege = verlauf(spec)
    zeilen, fehlt, grund, ab = [], [], {}, []
    for zeile in heute["balances"]:
        zeile = dict(zeile)
        name = str(zeile.get("name") or zeile.get("account_id"))
        if zeile.get("aus_auszug"):
            erster = _erster_auszug(conn, zeile["account_id"])
            if erster and erster[0] > ende and erster[1] != 0:
                fehlt.append(name)
                grund[name] = "konto"
                ab.append(_ag.folgetag(_ag.folgetag(erster[0])) - timedelta(days=1))
                continue
            zeile.update(cents=_st.saldo_zum(conn, zeile["account_id"], ende),
                         as_of=ende.isoformat())
            zeile.pop("auszug_bis", None)
        elif zeile.get("cents") is not None:
            eintraege = belege.get(schluessel(zeile)) or {}
            eintrag = eintraege.get(periode(zeile.get("kind"), folge))
            if eintrag is None:
                fehlt.append(name)
                grund[name] = "stand"
                ab.append(_ab_stichtag(eintraege, periode(zeile.get("kind"), folge),
                                       ende))
                continue
            zeile.update(cents=eintrag["cents"],
                         as_of=eintrag.get("as_of") or zeile.get("as_of"))
            # Der Rueckkaufswert hat keinen Verlauf: er galt nur zu seinem Datum.
            for feld in ("gewinn_cents", *RUECKKAUF_FELDER):
                zeile.pop(feld, None)
            if eintrag.get("gewinn_cents") is not None:
                zeile["gewinn_cents"] = eintrag["gewinn_cents"]
        zeilen.append(zeile)
    return {**heute, "balances": zeilen, "fehlt": fehlt, "fehlt_grund": grund,
            "fehlt_ab": max(ab) if ab else None}


def _erster_auszug(conn: sqlite3.Connection, konto: str) -> tuple[date, int] | None:
    """Wann der erste eingelesene Auszug eines Kontos beginnt und mit welchem Saldo."""
    r = conn.execute(
        "SELECT period_start, balance_start_cents FROM statements "
        "WHERE account_id = ? AND status = 'imported' "
        "ORDER BY period_start ASC LIMIT 1", (konto,)).fetchone()
    return (date.fromisoformat(r[0]), int(r[1] or 0)) if r else None


def _ab_stichtag(eintraege: dict, fehlende: str, ende: date) -> date:
    """Der erste Stichtag, zu dem der Vormonat einer Position bekannt ist.

    Ein Eintrag unter der Periode P haelt den Stand vom Ende des Monats davor
    fest; er ist Vormonat fuer den Stichtag am Ende von P (bei einer Police
    ab Januar des Jahres). Gibt es noch keinen spaeteren Eintrag, gilt der
    uebernaechste Monatsletzte nach `ende`: der Stand, im naechsten Abschluss
    eingetragen, ist dann der Vormonat.
    """
    from finctl.forecast import abgleich as _ag

    spaeter = sorted(p for p in eintraege if p > fehlende)
    if spaeter:
        p = spaeter[0]
        if len(p) == 4:
            return date(int(p), 1, 31)
        erster = date(int(p[:4]), int(p[5:7]), 1)
        return _ag.folgetag(erster) - timedelta(days=1)
    return _ag.folgetag(_ag.folgetag(_ag.folgetag(ende))) - timedelta(days=1)
