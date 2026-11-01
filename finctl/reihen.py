"""Was der Haushalt ueber Reihen festlegt: `config/reihen_custom.yaml`.

Eine Handentscheidung zeigt auf Buchungen, wie Vertraege und Planzeilen:

    reihen:
    - buchungen: [<dedup_hash>]    # eine Buchung der Reihe genuegt
      takt: 1                      # 1, 2, 3, 4, 6, 12, einmalig, unregelmaessig
      notiz: ...                   # optional
      notiz_vom: 2026-10-05        # wann die Notiz zuletzt geaendert wurde

Bei einem festen Takt und bei `unregelmaessig` gilt der Eintrag fuer die ganze
Reihe der genannten Buchung (`ledger/reihe.paare`), bei `einmalig` nur fuer die
genannten Buchungen: derselbe Haendler kommt in derselben Kategorie wieder.
Hat eine Reihe zwei Eintraege, gilt der spaetere in der Datei.

Dazu `zusammen`: Der Importer schreibt manchen Zahler mal so, mal so, und jede
Schreibweise waere eine Reihe fuer sich. Der Haushalt sagt, welche Schreibweise zu
welcher Gegenpartei gehoert, und die Vorschauen fuehren sie zu einer Reihe zusammen:

    zusammen:
      <schreibweise>: <gegenpartei>

Das gilt nur fuer die Reihen der Vorschauen, nicht fuer Regeln, Vertraege oder
`ledger/reihe.py`: Die haengen an `counterparty_norm`, wie der Importer sie schreibt.

Der Haushalt sagt, WIE OFT eine Reihe zahlt, nicht, dass sie weitergeht: auch
ein festgelegter Takt bildet seine Termine nach `forecast/takt.py` und kann
beendet sein. Dafuer gibt es Planzeilen.

Gelesen wird ueber `dateien.yaml_lesen`, geschrieben ueber
`dateien.schreiben_wenn_geaendert`: Speichern ohne Aenderung aendert keine
Datei, und eine Reihe, die schon so festgelegt ist, ruehrt sie nicht an.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date

import yaml

from finctl import notizen as _notizen
from finctl.dateien import schreiben_wenn_geaendert, yaml_lesen
from finctl.forecast import takt as _takt
from finctl.forecast.messung import KEIN_AUSSCHLUSS, Ausschluss
from finctl.forecast.takt import EINMALIG, FESTE_TAKTE, UNREGELMAESSIG, Reihen, Takt
from finctl.ledger import reihe as _reihe
from finctl.pfade import CONFIG_DIR

DATEI = "reihen_custom.yaml"
SCHLUESSEL = "reihen"
ZUSAMMEN = "zusammen"

KOPF = """# Was im Dashboard ueber Reihen festgelegt wurde -- geschrieben von /reihen.
#
# Ein Eintrag zeigt auf Buchungen (`buchungen`: eine Buchung der Reihe
# genuegt). `takt` ist 1, 2, 3, 4, 6 oder 12 Monate, `unregelmaessig` oder
# `einmalig`. Ein fester Takt und `unregelmaessig` gelten fuer die ganze
# Reihe der Buchung, `einmalig` nur fuer die genannten Buchungen.
#
# `zusammen` fuehrt eine Schreibweise der Gegenpartei mit einer anderen zu einer
# Reihe zusammen (`<schreibweise>: <gegenpartei>`).

"""

#: Was ein Eintrag als Takt tragen darf.
ERLAUBT = (*FESTE_TAKTE, UNREGELMAESSIG, EINMALIG)

_HASH = re.compile(r"[0-9a-f]+")

#: (Gegenpartei, Kategorie), die Kategorie '' fuer Teile ohne.
Schluessel = tuple[str, str]


@dataclass(frozen=True, slots=True)
class Eintrag:
    buchungen: tuple[str, ...]
    takt: Takt
    notiz: str = ""
    notiz_vom: str = ""

    def als_dict(self) -> dict:
        return {"buchungen": list(self.buchungen), "takt": self.takt,
                **_notizen.Notiz(self.notiz, self.notiz_vom).als_dict()}


def takt_lesen(wert: object) -> Takt:
    """Der Takt aus Datei oder Formular; sonst `ValueError`."""
    if isinstance(wert, str) and wert.strip().isdigit():
        wert = int(wert)
    if isinstance(wert, bool) or wert not in ERLAUBT:
        raise ValueError(f"Takt {wert!r} gilt nicht; erlaubt: "
                         + ", ".join(str(t) for t in ERLAUBT))
    return wert  # type: ignore[return-value]


def hash_pruefen(wert: object) -> str:
    """Eine Kennung, wie sie in `transactions.dedup_hash` steht (Hexzeichen).

    Die Kennungen gehen als Text in SQL (`abgleich.bloecke`); deshalb prueft
    schon das Lesen, dass es nichts anderes ist.
    """
    if not isinstance(wert, str) or not _HASH.fullmatch(wert):
        raise ValueError(f"{wert!r} ist keine Buchungskennung")
    return wert


def _eintrag(roh: object, nr: int) -> Eintrag:
    if not isinstance(roh, dict):
        raise ValueError(f"{DATEI}: Eintrag {nr} ist kein Eintrag")
    try:
        buchungen = roh.get("buchungen")
        if not isinstance(buchungen, list) or not buchungen:
            raise ValueError("`buchungen` fehlt")
        notiz = _notizen.lesen(roh)
        return Eintrag(tuple(hash_pruefen(h) for h in buchungen),
                       takt_lesen(roh.get("takt")), notiz.text, notiz.vom)
    except ValueError as fehler:
        raise ValueError(f"{DATEI}: Eintrag {nr}: {fehler}") from None


def _spec() -> dict:
    pfad = CONFIG_DIR / DATEI
    if not pfad.exists():
        return {}
    spec = yaml_lesen(pfad) or {}
    if not isinstance(spec, dict):
        raise ValueError(f"{DATEI}: keine Zuordnung")
    return spec


def lesen() -> list[Eintrag]:
    """Die Eintraege der Datei in ihrer Reihenfolge; ohne Datei keine."""
    roh = _spec().get(SCHLUESSEL) or []
    if not isinstance(roh, list):
        raise ValueError(f"{DATEI}: `{SCHLUESSEL}` ist keine Liste")
    return [_eintrag(e, i) for i, e in enumerate(roh, start=1)]


def zusammen() -> dict[str, str]:
    """Die zusammengefuehrten Schreibweisen, `{schreibweise: gegenpartei}`, wie in der
    Datei; ohne Datei keine. Ein Kreis oder ein Eintrag, der auf sich selbst zeigt, ist
    ein Fehler, der die Datei nennt."""
    roh = _spec().get(ZUSAMMEN) or {}
    if not isinstance(roh, dict):
        raise ValueError(f"{DATEI}: `{ZUSAMMEN}` ist keine Zuordnung")
    aus: dict[str, str] = {}
    for schreibweise, ziel in _notizen.ohne(roh).items():
        if not isinstance(schreibweise, str) or not isinstance(ziel, str) \
                or not schreibweise or not ziel:
            raise ValueError(f"{DATEI}: {ZUSAMMEN}: {schreibweise!r}: {ziel!r} ist keine "
                             f"Gegenpartei")
        if schreibweise == ziel:
            raise ValueError(f"{DATEI}: {ZUSAMMEN}: {schreibweise} zeigt auf sich selbst")
        aus[schreibweise] = ziel
    try:
        _takt.zusammen_aufloesen(aus)
    except ValueError as fehler:
        raise ValueError(f"{DATEI}: {fehler}") from None
    return aus


def einmalige_hashes() -> frozenset[str]:
    """Die Buchungen, die der Haushalt einmalig gesetzt hat."""
    return frozenset(h for e in lesen() if e.takt == EINMALIG for h in e.buchungen)


def _schluessel(conn: sqlite3.Connection, buchungen) -> dict[str, Schluessel]:
    """Je Buchungskennung ihre Reihe; was das Hauptbuch nicht kennt, fehlt.

    Eine Buchung ohne Gegenpartei hat keine Reihe (`ledger/reihe.paare`). Eine
    zusammengefuehrte Schreibweise steht unter der Gegenpartei, auf die sie zeigt: So
    gilt eine Handentscheidung fuer die Reihe, wie die Vorschauen sie bilden.
    """
    ziel = _takt.zusammen_aufloesen(zusammen())
    aus: dict[str, Schluessel] = {}
    for h in buchungen:
        paare = _reihe.paare(conn, [h])
        if paare:
            aus[h] = (ziel.get(paare[0][0], paare[0][0]), paare[0][1] or "")
    return aus


def festgelegt(conn: sqlite3.Connection) -> dict[Schluessel, Takt]:
    """Die Handentscheidungen je Reihe, fuer `takt.reihen`.

    Der Eintrag gilt fuer jede Reihe, auf die eine seiner Buchungen zeigt;
    `einmalig` gehoert nicht hierher, es gilt fuer Buchungen.
    """
    aus: dict[Schluessel, Takt] = {}
    for e in lesen():
        if e.takt == EINMALIG:
            continue
        for schluessel in _schluessel(conn, e.buchungen).values():
            aus[schluessel] = e.takt
    return aus


def notizen(conn: sqlite3.Connection) -> dict[Schluessel, Eintrag]:
    """Je Reihe der Eintrag, der ihren Takt festlegt (mit Notiz und Datum)."""
    aus: dict[Schluessel, Eintrag] = {}
    for e in lesen():
        if e.takt == EINMALIG:
            continue
        for schluessel in _schluessel(conn, e.buchungen).values():
            aus[schluessel] = e
    return aus


def laden(conn: sqlite3.Connection, bis: date, *,
          ausschluss: Ausschluss = KEIN_AUSSCHLUSS) -> Reihen:
    """Die Reihen bis `bis`, mit den Handentscheidungen der Datei.

    `ausschluss` nennt Buchungen, die eine Messung nicht sieht; sie bilden auch
    keinen Termin (`takt.reihen`)."""
    return _takt.reihen(conn, bis=bis, festgelegt=festgelegt(conn), zusammen=zusammen(),
                        ausschluss=ausschluss)


# ------------------------------------------------------------- Schreiben


def _schreiben(eintraege: list[Eintrag], zusammengefuehrt: dict[str, str] | None = None) -> bool:
    """Die Datei schreiben; `zusammengefuehrt=None` laesst die zusammengefuehrten
    Schreibweisen, wie sie sind."""
    pfad = CONFIG_DIR / DATEI
    if zusammengefuehrt is None:
        zusammengefuehrt = zusammen()
    if not eintraege and not zusammengefuehrt and not pfad.exists():
        return False
    spec: dict = {SCHLUESSEL: [e.als_dict() for e in eintraege]}
    if zusammengefuehrt:
        spec[ZUSAMMEN] = dict(sorted(zusammengefuehrt.items()))
    spec = _notizen.mit_bereichen(spec, pfad)
    text = KOPF + yaml.safe_dump(spec, allow_unicode=True, sort_keys=False)
    return schreiben_wenn_geaendert(pfad, text)


def _buchung_pruefen(conn: sqlite3.Connection, buchung: str) -> Schluessel:
    hash_pruefen(buchung)
    gefunden = _schluessel(conn, [buchung])
    if buchung not in gefunden:
        raise ValueError("Die Buchung ist nicht bekannt oder hat keine Gegenpartei, "
                         "also keine Reihe.")
    return gefunden[buchung]


def _festlegung(conn: sqlite3.Connection, alt: list[Eintrag],
                ziel: Schluessel) -> Eintrag | None:
    """Was die Reihe heute festlegt: der spaetere Eintrag gewinnt."""
    return next((e for e in reversed(alt) if e.takt != EINMALIG
                 and ziel in _schluessel(conn, e.buchungen).values()), None)


def _notiz(bisher: Eintrag | None, notiz: str | None) -> tuple[str, str]:
    """Text und Datum der Notiz nach der Datumsregel (`notizen.fortschreiben`)."""
    alt = _notizen.Notiz(bisher.notiz, bisher.notiz_vom) if bisher else _notizen.Notiz()
    neu = _notizen.fortschreiben(alt, notiz)
    return neu.text, neu.vom


def _ersetzt(conn: sqlite3.Connection, alt: list[Eintrag], ziel: Schluessel,
             neu: Eintrag | None) -> list[Eintrag]:
    """Die Eintraege ohne die Reihe `ziel`, `neu` an der Stelle des ersten, der sie betraf.

    Ein Eintrag, der mehrere Reihen nennt (von Hand geschrieben), behaelt die
    Buchungen der uebrigen.
    """
    aus: list[Eintrag] = []
    eingesetzt = neu is None
    for e in alt:
        if e.takt == EINMALIG:
            aus.append(e)
            continue
        schluessel = _schluessel(conn, e.buchungen)
        rest = tuple(h for h in e.buchungen if schluessel.get(h) != ziel)
        if rest != e.buchungen and not eingesetzt:
            aus.append(neu)  # type: ignore[arg-type]
            eingesetzt = True
        if rest:
            aus.append(Eintrag(rest, e.takt, e.notiz, e.notiz_vom))
    if not eingesetzt:
        aus.append(neu)  # type: ignore[arg-type]
    return aus


def festlegen(conn: sqlite3.Connection, buchung: str, takt: Takt | None,
              notiz: str | None = None) -> bool:
    """Den Takt der Reihe festlegen (`takt=None`: die Festlegung zurueck).

    `notiz=None` laesst die Notiz, wie sie ist; sonst steht der neue Text mit
    dem heutigen Datum, wenn er sich geaendert hat. `True`, wenn die Datei
    geschrieben wurde: eine Reihe, die schon so festgelegt ist, aendert nichts.
    """
    if takt == EINMALIG:
        raise ValueError("einmalig gilt fuer Buchungen, nicht fuer eine Reihe")
    if takt is not None:
        takt = takt_lesen(takt)
    ziel = _buchung_pruefen(conn, buchung)
    alt = lesen()
    bisher = _festlegung(conn, alt, ziel)
    if bisher is None and takt is None:
        return False
    text, vom = _notiz(bisher, notiz)
    if bisher is not None and takt == bisher.takt and text == bisher.notiz:
        return False
    neu = None if takt is None else Eintrag((buchung,), takt, text, vom)
    return _schreiben(_ersetzt(conn, alt, ziel, neu))


def einmalig_setzen(conn: sqlite3.Connection, buchung: str, einmalig: bool) -> bool:
    """Eine Buchung einmalig setzen oder die Markierung zuruecknehmen.

    `True`, wenn die Datei geschrieben wurde. Eine Markierung zuruecknehmen
    geht auch fuer eine Buchung, die das Hauptbuch nicht mehr kennt.
    """
    hash_pruefen(buchung)
    alt = lesen()
    if einmalig:
        if buchung in einmalige_hashes():
            return False
        _buchung_pruefen(conn, buchung)
        return _schreiben([*alt, Eintrag((buchung,), EINMALIG)])
    neu = []
    for e in alt:
        if e.takt == EINMALIG and buchung in e.buchungen:
            rest = tuple(h for h in e.buchungen if h != buchung)
            if rest:
                neu.append(Eintrag(rest, e.takt, e.notiz, e.notiz_vom))
        else:
            neu.append(e)
    if len(neu) == len(alt) and neu == alt:
        return False
    return _schreiben(neu)


def _kategorien(conn: sqlite3.Connection, gegenpartei: str) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT COALESCE(s.mgmt_category_id, '') FROM transactions t "
        "JOIN splits s ON s.transaction_id = t.id WHERE t.counterparty_norm = ?",
        (gegenpartei,))}


def zusammenfuehren(conn: sqlite3.Connection, schreibweise: str, ziel: str | None) -> bool:
    """Eine Schreibweise der Gegenpartei einer anderen zuordnen (`ziel=None`: die
    Zuordnung zurueck).

    Beide muessen im Hauptbuch stehen und eine Kategorie teilen: Eine Reihe ist
    Gegenpartei und Kategorie, und zwei Zahler ohne gemeinsame Kategorie haetten nichts
    zusammenzufuehren. Sie gilt fuer jede Kategorie, in der die Schreibweise steht, denn
    sie sagt etwas ueber den Zahler. `True`, wenn die Datei geschrieben wurde: Dieselbe
    Zuordnung noch einmal aendert nichts.
    """
    alt = zusammen()
    if ziel is None:
        if schreibweise not in alt:
            return False
        return _schreiben(lesen(), {k: v for k, v in alt.items() if k != schreibweise})
    if not schreibweise or not ziel or schreibweise == ziel:
        raise ValueError("Eine Gegenpartei gehoert nicht zu sich selbst.")
    gemeinsam = _kategorien(conn, schreibweise) & _kategorien(conn, ziel)
    if not gemeinsam:
        raise ValueError("Beide Gegenparteien muessen im Hauptbuch stehen und eine "
                         "Kategorie teilen.")
    neu = {**alt, schreibweise: ziel}
    if neu == alt:
        return False
    _takt.zusammen_aufloesen(neu)
    return _schreiben(lesen(), neu)


def einmalige_buchungen(conn: sqlite3.Connection) -> list[dict]:
    """Die einmalig gesetzten Buchungen mit dem, was die Seite zeigt.

    Sortiert nach Tag, dann Kennung. Eine Kennung, die das Hauptbuch nicht mehr
    kennt (ein Auszug wurde ersetzt), steht ohne Angaben da und laesst sich
    zuruecknehmen.
    """
    aus = []
    for h in sorted(einmalige_hashes()):
        zeile = conn.execute(
            "SELECT t.booking_date, COALESCE(t.counterparty_norm, '') AS gegenpartei, "
            "SUM(s.amount_cents) AS cents, MIN(s.mgmt_category_id) AS kategorie "
            "FROM transactions t JOIN splits s ON s.transaction_id = t.id "
            "WHERE t.dedup_hash = ? GROUP BY t.id", (h,)).fetchone()
        aus.append({"buchung": h, "tag": zeile[0] if zeile else "",
                    "gegenpartei": zeile[1] if zeile else "",
                    "cents": int(zeile[2]) if zeile else 0,
                    "kategorie": (zeile[3] or "") if zeile else "",
                    "bekannt": zeile is not None})
    aus.sort(key=lambda z: (z["tag"], z["buchung"]))
    return aus
