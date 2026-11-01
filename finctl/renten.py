"""Was im Ruhestand hereinkommt: gesetzliche Rente, Fondsrenten, Policen.

Jede Quelle steht in `config/renten.yaml`, mit ihrer Notiz. Betrag und Stand kommen
aus einem Schreiben, das jedes Jahr neu kommt -- Renteninformation, Standmitteilung --,
und werden auf /renten eingetragen; die Seite schreibt den ganzen Eintrag in dieselbe
Datei (Schritt 5, N.3b: davor lagen sie in einer zweiten Datei).

KAUFKRAFT. Die DRV nennt ihre Zahl in heutiger Kaufkraft ("ohne
Rentenanpassungen"), eine Standmitteilung meist nominal. Beides wird so
eingetragen, wie es im Schreiben steht, und erst beim Rechnen nominal gemacht
(`nominal_cents`). Eine Inflationsannahme in die Quelle zu schreiben hiesse,
eine Unterlage zu verfaelschen.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from finctl import notizen as _notizen
from finctl.dateien import yaml_lesen, yaml_schreiben
from finctl.pfade import CONFIG_DIR

DATEI = "renten.yaml"
ARTEN = {"rente": "Monatsrente", "kapital": "Kapital"}
KAUFKRAFT = ("heute", "nominal")


@dataclass(frozen=True, slots=True)
class Pruefwert:
    """Eine Spalte aus der Mitteilung einer Police, an der das Modell sich misst.

    Nominal, mit weiterlaufendem Beitrag: `cents` stehen zum Monat `zum`, wenn
    die Police mit `satz` waechst (Fondsrendite der Mitteilung, vor Kosten).
    Nennt die Mitteilung keinen Satz, ist er None: Dann gibt es nichts zu
    vergleichen, und der Wert steht nur als Zahl der Mitteilung da.
    """

    satz: float | None
    cents: int
    zum: date


@dataclass(frozen=True, slots=True)
class Quelle:
    id: str
    name: str
    art: str                      # "rente" oder "kapital"
    cents: int                    # je Monat bzw. einmalig, wie im Schreiben
    kaufkraft: str = "heute"
    #: Bezug ab: ab wann gezahlt wird -- bei einer Police oft waehlbar (62
    #: oder 67). None heisst Rentenbeginn aus der Einrichtung.
    ab: date | None = None
    konto: str | None = None
    stand: date | None = None     # Datum des Schreibens
    #: Die Notiz der Quelle und ihr Datum (`finctl/notizen.py`).
    notiz: str = ""
    notiz_vom: str = ""
    #: Effektivkosten der Police je Jahr, 0,013 fuer 1,3 % -- aus
    #: Standmitteilung oder Produktinformationsblatt. None: nicht bekannt.
    kosten_pa: float | None = None
    #: Kennung des Vertrags (abos*.yaml, versicherungen*.yaml), der die Police
    #: speist: Betrag und Takt stehen dort, nicht noch einmal hier.
    beitrag: str | None = None
    #: Eine Spalte der Mitteilung als Gegenprobe zum Modell; nur bei Kapital.
    pruefwert: Pruefwert | None = None
    #: Betriebliche Altersvorsorge, die nur der Arbeitgeber zahlt: Wert laut
    #: Mitteilung (`stand_cents` zum Datum `stand_wert`) und sein Beitrag je Jahr,
    #: nominal fest. Alle drei stehen zusammen oder gar nicht, und nur bei einem
    #: Kapital ohne `konto`; `cents` ist dann der Betrag zu `ab`, den der Haushalt
    #: ansetzt (`satz`, `auszahlung_cents`).
    stand_cents: int | None = None
    stand_wert: date | None = None
    beitrag_ag_cents: int | None = None

    @property
    def hat_modell(self) -> bool:
        return self.stand_cents is not None

    def aktuell(self, heute: date) -> bool:
        """Ein Schreiben kommt einmal im Jahr: aktuell, wenn aus diesem Jahr."""
        return bool(self.stand and self.stand.year == heute.year)


def _yaml(pfad: Path) -> dict:
    if not pfad.exists():
        return {}
    return yaml_lesen(pfad) or {}


def _datum(wert) -> date | None:
    if not wert:
        return None
    if isinstance(wert, date):
        return wert
    text = str(wert)
    return date.fromisoformat(text + "-01" if len(text) == 7 else text[:10])


def quellen(config_dir: Path | None = None) -> list[Quelle]:
    """Alle Quellen aus `renten.yaml`.

    Ein neuer Nutzer hat die Datei nicht, und seine gesetzliche Rente muss er trotzdem
    eintragen koennen: Ohne Datei gibt es keine Quellen.
    """
    config_dir = config_dir or CONFIG_DIR
    aus = aus_spec(_yaml(config_dir / DATEI))
    _vertraege_pruefen(aus, config_dir)
    return aus


def aus_spec(spec: dict) -> list[Quelle]:
    """Die Quellen einer gelesenen Datei."""
    aus = []
    for roh in spec.get("renten") or []:
        kennung = str(roh.get("id") or "")
        if not kennung:
            continue
        notiz = _notizen.lesen(roh)
        art = str(roh.get("art") or "rente")
        kaufkraft = str(roh.get("kaufkraft") or "heute")
        if art not in ARTEN or kaufkraft not in KAUFKRAFT:
            raise ValueError(f"renten.yaml, {kennung}: art {ARTEN.keys()}, "
                             f"kaufkraft {KAUFKRAFT}")
        aus.append(Quelle(
            id=kennung, name=str(roh.get("name") or kennung), art=art,
            cents=int(roh.get("cents") or 0), kaufkraft=kaufkraft, ab=_datum(roh.get("ab")),
            konto=roh.get("konto") or None, stand=_datum(roh.get("stand")),
            notiz=notiz.text, notiz_vom=notiz.vom,
            kosten_pa=_zahl(roh.get("kosten_pa")),
            beitrag=str(roh.get("beitrag") or "").strip() or None,
            pruefwert=_pruefwert(roh.get("pruefwert"), kennung),
            **_modell({f: roh.get(f) for f in MODELLFELDER}, roh, art, kaufkraft,
                      int(roh.get("cents") or 0), kennung)))
    return aus


MODELLFELDER = ("stand_cents", "stand_wert", "beitrag_ag_cents")


def _modell(felder: dict, roh: dict, art: str, kaufkraft: str, cents: int,
            kennung: str) -> dict:
    """`stand_cents`, `stand_wert`, `beitrag_ag_cents` aus der Datei; leer heisst keins.

    Die drei gehoeren zusammen und tragen nur ein nominales Kapital ohne `konto`
    mit einem Betrag: sonst waere der Satz, den sie festlegen, nicht eindeutig.
    """
    if all(w in (None, "") for w in felder.values()):
        return {}
    fehlt = (f"renten.yaml, {kennung}: {', '.join(MODELLFELDER)} stehen zusammen "
             "(Betrag nicht negativ, Datum JJJJ-MM-TT) und nur bei art kapital ohne konto, "
             "kaufkraft nominal, mit cents")
    if any(w in (None, "") for w in felder.values()) or art != "kapital" \
            or roh.get("konto") or kaufkraft != "nominal" or cents <= 0:
        raise ValueError(fehlt)
    try:
        stand, wert, beitrag = (int(felder["stand_cents"]), _datum(felder["stand_wert"]),
                                int(felder["beitrag_ag_cents"]))
    except (TypeError, ValueError):
        raise ValueError(fehlt) from None
    if stand < 0 or beitrag < 0:
        raise ValueError(fehlt)
    return {"stand_cents": stand, "stand_wert": wert, "beitrag_ag_cents": beitrag}


def _pruefwert(roh, kennung: str) -> Pruefwert | None:
    """`pruefwert: {satz, cents, zum}` aus der Datei; leer heisst keiner.

    `satz` darf fehlen (die Mitteilung nennt ihn nicht), `cents` und `zum` nicht.
    """
    if not roh:
        return None
    fehlt = (f"renten.yaml, {kennung}: pruefwert braucht cents (nicht negativ) und "
             "zum (JJJJ-MM), dazu optional satz")
    if not isinstance(roh, dict) or any(roh.get(f) in (None, "") for f in ("cents", "zum")):
        raise ValueError(fehlt)
    try:
        satz, cents, zum = _zahl(roh.get("satz")), int(roh["cents"]), _datum(roh["zum"])
    except (TypeError, ValueError):
        raise ValueError(fehlt) from None
    if cents < 0 or (satz is not None and not -0.5 < satz < 0.5):
        raise ValueError(fehlt)
    return Pruefwert(satz=satz, cents=cents, zum=zum)


def _vertraege_pruefen(quellen_: list[Quelle], config_dir: Path) -> None:
    """Jeder `beitrag` zeigt auf einen Vertrag, sonst ist es ein Fehler beim Lesen.

    Die Vertragsdateien werden nur gelesen, wenn eine Quelle einen Beitrag nennt.
    """
    if not any(q.beitrag for q in quellen_):
        return
    from finctl import abos

    bekannt = {v["id"] for art, (datei, _) in abos.ARTEN.items()
               for v in abos.laden(config_dir / datei, art)}
    for q in quellen_:
        if q.beitrag and q.beitrag not in bekannt:
            raise ValueError(f"renten.yaml, {q.id}: beitrag „{q.beitrag}“ ist kein Vertrag "
                             "in abos.yaml oder versicherungen.yaml")


def _zahl(wert) -> float | None:
    return None if wert in (None, "") else float(wert)


_UNGELESEN: Any = object()


def beginn(q: Quelle, rentenbeginn: date | None = _UNGELESEN) -> date | None:
    """Ab wann die Quelle zahlt -- ohne eigenes Datum ab dem Rentenbeginn.

    Wer mehrere Quellen fragt, liest den Rentenbeginn einmal und reicht ihn
    herein: Er kommt aus zwei Dateien, und `None` (kein Geburtsdatum) ist
    eine gueltige Antwort, deshalb steht der Marker `_UNGELESEN` fuer "lies es".
    """
    if q.ab:
        return q.ab
    if rentenbeginn is not _UNGELESEN:
        return rentenbeginn
    from finctl import person

    return person.rentenbeginn()


def nominal_cents(q: Quelle, im_jahr: int, inflation_pa: float,
                  basis_jahr: int | None = None) -> int:
    """Der Betrag in Geld des Jahres `im_jahr`.

    Heutige Kaufkraft wird mit der Inflation fortgeschrieben, vom Jahr des
    Schreibens an; eine nominale Zahl bleibt, wie sie ist. 2.000 heute werden
    bei 2 % und Rentenbeginn in 35 Jahren rund 4.000.
    """
    if q.kaufkraft == "nominal":
        return q.cents
    basis = basis_jahr or (q.stand.year if q.stand else date.today().year)
    return int(round(q.cents * (1.0 + inflation_pa) ** (im_jahr - basis)))


#: Der Satz der betrieblichen Altersvorsorge wird zwischen diesen Grenzen gesucht.
_SATZ_GRENZEN = (-0.5, 0.5)


def _endwert(q: Quelle, beginn: date, satz: float,
             anteil_im_monat: Callable[[date], float | None] | None = None,
             gehalt_bis: date | None = None) -> float:
    """Der Wert zu `beginn`: Stand zum Monat des Schreibens, je Monat verzinst und
    um den Beitrag des Arbeitgebers erhoeht (ein Zwoelftel, am Monatsende).

    `anteil_im_monat` sagt je Monat, welcher Teil des Beitrags noch fliesst (None:
    alles) -- die Teilzeit. Ab `gehalt_bis` endet er ganz: ohne Gehalt zahlt
    der Arbeitgeber nicht.
    """
    monatlich = (1.0 + satz) ** (1 / 12)
    je_monat = q.beitrag_ag_cents / 12
    wert = float(q.stand_cents)
    monat = date(q.stand_wert.year, q.stand_wert.month, 1)
    while monat < beginn:
        beitrag = je_monat
        if anteil_im_monat is not None:
            anteil = anteil_im_monat(monat)
            beitrag = 0.0 if gehalt_bis is not None and monat >= gehalt_bis \
                else je_monat * (1.0 if anteil is None else anteil)
        wert = wert * monatlich + beitrag
        monat = date(monat.year + monat.month // 12, monat.month % 12 + 1, 1)
    return wert


@lru_cache(maxsize=64)
def satz_zu(q: Quelle, beginn: date, ziel_cents: int) -> float | None:
    """Der Jahressatz, mit dem Stand plus Beitrag zu `beginn` genau `ziel_cents` ergeben.

    None ohne Modell, wenn `beginn` nicht nach dem Monat des Stands liegt (dann gibt
    es nichts zu verzinsen) und wenn kein Satz zwischen -50 und +50 % den Betrag
    erreicht.
    """
    if not q.hat_modell or beginn <= date(q.stand_wert.year, q.stand_wert.month, 1):
        return None
    unten, oben = _SATZ_GRENZEN
    if not _endwert(q, beginn, unten) <= ziel_cents <= _endwert(q, beginn, oben):
        return None
    for _ in range(200):
        mitte = (unten + oben) / 2
        if _endwert(q, beginn, mitte) < ziel_cents:
            unten = mitte
        else:
            oben = mitte
    return (unten + oben) / 2


def satz(q: Quelle, beginn: date) -> float | None:
    """Der Jahressatz, mit dem Stand plus Beitrag zu `beginn` genau `cents` ergeben.

    Er steht in keiner Datei: Die Mitteilung nennt ihn nicht, und der Haushalt
    tippt keinen. None ohne Modell oder wenn `beginn` nicht nach dem Monat des
    Stands liegt. Einen Betrag, den kein Satz zwischen -50 und +50 % erreicht,
    kann das Modell nicht tragen: Fehler.
    """
    s = satz_zu(q, beginn, q.cents)
    if s is None and q.hat_modell and beginn > date(q.stand_wert.year, q.stand_wert.month, 1):
        unten, oben = _SATZ_GRENZEN
        raise ValueError(f"renten.yaml, {q.id}: kein Satz zwischen {unten:.0%} und "
                         f"{oben:.0%} fuehrt von Stand und Beitrag zu {q.cents / 100:,.2f} "
                         f"zum {beginn:%Y-%m}")
    return s


def teilzeit_ab(anteil: float, ab: date) -> Callable[[date], float | None]:
    """Der Anteil je Monat bei einer Teilzeit mit `anteil` ab `ab` (davor: voll)."""
    return lambda monat: anteil if monat >= ab else None


def auszahlung_cents(q: Quelle, beginn: date,
                     anteil_im_monat: Callable[[date], float | None] | None = None,
                     gehalt_bis: date | None = None) -> int:
    """Was die Quelle zu `beginn` auszahlt, nominal und vor Abzug.

    Ohne Modell, ohne Teilzeit (`anteil_im_monat` None) oder ohne Monate zum
    Verzinsen ist es `cents`, wie im Schreiben. Mit Teilzeit rechnet derselbe
    Satz mit dem Beitrag, der noch fliesst (`_endwert`).
    """
    s = satz(q, beginn)
    if s is None or anteil_im_monat is None:
        return q.cents
    return round(_endwert(q, beginn, s, anteil_im_monat, gehalt_bis))


def _betrag(wert):
    cents = int(wert)
    if cents < 0:
        raise ValueError("Betrag ohne Vorzeichen")
    return cents


def _bezug_ab(wert):
    ab = str(wert or "").strip()
    if ab and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", ab):
        raise ValueError("Bezug ab als JJJJ-MM")
    # Leer heisst: kein eigener Beginn, es gilt der Rentenbeginn aus der Einrichtung.
    return ab or None


def _stand(wert):
    if not wert:
        return None
    stand = _datum(wert)
    if stand > date.today():
        raise ValueError("Stand liegt in der Zukunft")
    return stand


def _notiz(wert):
    return _notizen.eingabe(wert) or None


def _kosten(wert):
    """Effektivkosten als Anteil, 0 bis 10 %. Leer: nicht bekannt."""
    if wert in (None, ""):
        return None
    kosten = float(wert)
    if not 0 <= kosten <= 0.1:
        raise ValueError("Effektivkosten zwischen 0 und 10 %")
    return round(kosten, 5)


#: Je Feld: wie es geprueft wird. Ein leerer Wert nimmt das Feld aus dem Eintrag. Die Notiz
#: folgt der Datumsregel und steht deshalb nicht hier (`setzen`).
_FELDER = {"cents": _betrag, "ab": _bezug_ab, "stand": _stand, "kosten_pa": _kosten}


def _spec(config_dir: Path) -> dict:
    return _yaml(config_dir / DATEI)


def _eintrag_zu(spec: dict, kennung: str) -> dict | None:
    return next((e for e in spec.get("renten") or [] if str(e.get("id")) == kennung), None)


def _feld_setzen(eintrag: dict, feld: str, wert) -> None:
    """Das Feld setzen -- oder lassen, wenn die Datei schon dasselbe sagt (auch als Text)."""
    if wert is None:
        eintrag.pop(feld, None)
    elif feld not in eintrag or str(eintrag[feld]) != str(wert):
        eintrag[feld] = wert


def setzen(kennung: str, felder: dict, config_dir: Path | None = None) -> None:
    """Aus dem Monatsabschluss: Betrag, Bezug ab, Stand, Effektivkosten und Notiz einer Quelle.

    Die Datei wird ganz gelesen und ganz geschrieben. Sagt sie danach dasselbe wie vorher,
    bleibt sie, wie sie ist. Ein leerer Stand laesst den gespeicherten stehen.
    """
    config_dir = config_dir or CONFIG_DIR
    spec = _spec(config_dir)
    eintrag = _eintrag_zu(spec, kennung)
    if eintrag is None:
        raise ValueError(f"Keine Rentenquelle „{kennung}“")
    for feld, pruefen in _FELDER.items():
        if feld not in felder or (feld == "stand" and not felder[feld]):
            continue
        _feld_setzen(eintrag, feld, pruefen(felder[feld]))
    if "notiz" in felder:
        _notizen.setzen(eintrag, _notiz(felder["notiz"]) or "")
    _schreiben(config_dir, spec)


def _kennung(name: str, vergeben: set[str]) -> str:
    stamm = re.sub(r"[^a-z0-9]+", "-", name.lower()
                   .translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})))
    stamm = stamm.strip("-")[:40] or "rente"
    kennung, n = stamm, 2
    while kennung in vergeben:
        kennung, n = f"{stamm}-{n}", n + 1
    return kennung


def anlegen(felder: dict, config_dir: Path | None = None) -> str:
    """Eine Rente oder Police aus dem Monatsabschluss anlegen.

    Immer NOMINAL, wie sie im Schreiben steht: nach heutiger Kaufkraft zu
    fragen hiesse, eine Zahl zu verlangen, die in keinem Schreiben steht --
    die DRV nennt ihre ohne Anpassungen, eine Police in Euro des Auszahlungs-
    jahres. Nominal ohne Anpassung ist die vorsichtige Lesart.
    """
    config_dir = config_dir or CONFIG_DIR
    name = str(felder.get("name") or "").strip()[:80]
    if not name:
        raise ValueError("Name fehlt")
    art = str(felder.get("art") or "rente")
    if art not in ARTEN:
        raise ValueError(f"Art {', '.join(ARTEN)}")
    if felder.get("cents") in (None, ""):
        raise ValueError("Betrag fehlt")
    spec = _spec(config_dir)
    eintrag = {"id": _kennung(name, {q.id for q in aus_spec(spec)}),
               "name": name, "art": art, "kaufkraft": "nominal",
               "cents": _betrag(felder["cents"])}
    for feld, pruefen in (("ab", _bezug_ab), ("kosten_pa", _kosten)):
        wert = pruefen(felder.get(feld))
        if wert is not None:
            eintrag[feld] = wert
    spec["renten"] = [*(spec.get("renten") or []), eintrag]
    _schreiben(config_dir, spec)
    return eintrag["id"]


def loeschen(kennung: str, config_dir: Path | None = None) -> None:
    """Eine Quelle aus `renten.yaml` nehmen."""
    config_dir = config_dir or CONFIG_DIR
    spec = _spec(config_dir)
    if _eintrag_zu(spec, kennung) is None:
        raise ValueError(f"Keine Rentenquelle „{kennung}“")
    spec["renten"] = [e for e in spec["renten"] if str(e.get("id")) != kennung]
    _schreiben(config_dir, spec)


def _schreiben(config_dir: Path, spec: dict) -> None:
    """Die ganze Datei schreiben, mit allen Notizen; nur wenn sie etwas anderes sagt."""
    yaml_schreiben(config_dir / DATEI, spec)
