"""Toggleable what-if plans: a car, a house, a sabbatical.

The point is sketching several ideas, seeing what each does to the plan, and
switching them off again without deleting the work. Three properties matter.

They are ADDITIVE. Any number can be active at once, because the real question
is usually "can I do both" -- the car and the extra property -- and answering
it one scenario at a time cannot show the interaction.

They are TOGGLEABLE rather than deletable. Parking a plan has to be one click,
or the plan gets deleted and the thinking behind it goes with it.

They reach EVERYWHERE. A cost line that shows up in the forecast but not in
the Barista FIRE target would let a 350-a-month commitment look free against
the goal it actually delays by years.

Amounts follow the ledger's sign convention throughout: negative is money out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from finctl.dateien import yaml_lesen
from finctl.pfade import CONFIG_DIR

FREQUENCIES = ("einmalig", "monatlich", "quartalsweise", "jaehrlich")

# Was eine Zeile ist.
#
# BETRAG ist der gewöhnliche Fall: eine Zahlung mit einer Summe.
#
# WEGFALL ist der Fall, ohne den ein Plan die halbe Wahrheit zeigt. Ein neues
# Auto kostet nicht 350 im Monat, es kostet 350 MINUS dem, was das alte Auto
# kostet. Beim Hauskauf dasselbe mit der Miete. Die Summe dafür wird NICHT
# eingetippt, sondern aus dem Ledger gemessen -- eine eingetippte Ersparnis ist
# ab dem Tag der Eingabe eine Behauptung, und sie schmeichelt dem Plan.
#
# VERKAUF ist ein Objekt, das den Bestand verlaesst: Preis, Monat, Kosten. Die
# Zeile traegt keine Buchungen und wirkt nur in der Jahresrechnung -- dort
# endet der Kredit, Miete und Kosten fallen weg und der Nettoerloes kommt
# einmal (siehe jahre.verkaeufe). Auf die Konten verteilt wird er nicht.
#
# TEILZEIT ist ein Anteil am Gehalt ab einem Monat, kein Betrag: das Gehalt
# wird gemessen und steigt, und ein eingetippter Betrag waere am Tag danach
# falsch. Wirkt nur in der Jahresrechnung -- die Kontoprognose rechnet mit der
# Gehalts-Untergrenze und reicht selten bis zum Wechsel. Laufen zwei Zeilen
# zugleich, gilt die spaeter begonnene.
#
# ERWARTET ist eine Einnahme, die der Haushalt zugesagt bekommen hat oder mit ihr
# rechnet, ohne dass ihre Buchungen ein Muster ergeben: eine Schenkung, eine
# Nebentaetigkeit. Ihre Buchungen sind der Zeile zugeordnet, und die Zeile ERSETZT
# sie: Die zugeordneten Buchungen und ihre Reihe zaehlen in keiner Messung, die
# Zeile zaehlt voll, mit festem Betrag und ohne Steigerung. So steht die Einnahme
# in beiden Prognosen genau einmal da. Die anderen Arten bleiben, wie sie sind:
# `betrag` kuerzt sich um das Gemessene, statt es zu ersetzen.
KINDS = ("betrag", "wegfall", "verkauf", "teilzeit", "erwartet")
#: Arten, die nur in der Jahresrechnung wirken und keine Buchungen tragen.
NUR_JAHRESRECHNUNG = ("verkauf", "teilzeit")

_STEP = {"monatlich": 1, "quartalsweise": 3, "jaehrlich": 12}


@dataclass(slots=True)
class Line:
    """One cost or income line inside a scenario."""

    label: str
    amount_cents: int
    frequency: str = "monatlich"
    kind: str = "betrag"
    start: date | None = None
    end: date | None = None
    account_id: str | None = None
    # Required in practice, optional in the type so old files still load. A
    # line without a category is a lump sum with a name: switch it on and the
    # forecast gains money movements that no report can place.
    category_id: str | None = None
    #: Zugeordnete Buchungen, als dedup_hash. Sagen, welche Buchungen im
    #: Ledger zu dieser Zeile gehoeren -- beim Wegfall die Reihe, die endet,
    #: bei neuen Kosten die Reihe, die beginnt.
    buchungen: list[str] = field(default_factory=list)
    #: Nur beim Verkauf: welches Objekt, und was vom Preis vorher abgeht
    #: (Makler, Vorfaelligkeitsentschaedigung). Der Preis steht in amount_cents.
    property_id: str | None = None
    kosten_cents: int = 0
    #: Nur bei Teilzeit: der Anteil am vollen Gehalt, 0,7 fuer 70 %.
    anteil: float | None = None
    #: Welche Werte ("anteil", "start") aus den Annahmen kommen, weil die Zeile
    #: selbst keine eigenen traegt: bei Teilzeit beide, in der Klammer "Teilzeit"
    #: auch der Start jeder anderen Zeile.
    aus_annahmen: tuple[str, ...] = ()
    #: Nur beim Wegfall: die Reihe verlaesst nur DIESES Konto, ausgegeben wird
    #: weiter -- etwa Tanken, das von einer Karte auf eine andere zieht. Wirkt
    #: dann nur in der Kontoprognose und nur auf `account_id`; die
    #: Jahresrechnung misst den Haushalt und sieht keinen Unterschied.
    nur_kontoprognose: bool = False

    def months(self, horizon_end: date) -> list[date]:
        """Every month this line touches, up to the horizon.

        A line with no end runs to the horizon rather than forever: an open
        commitment is a real thing (a subscription, a rate with no stated
        term) and refusing to model it would push the user to invent an end
        date, which is worse than carrying it to the edge of the projection.
        """
        if self.start is None:
            return []
        if self.frequency == "einmalig":
            return [self.start] if self.start <= horizon_end else []

        step = _STEP.get(self.frequency)
        if not step:
            return []
        last = min(self.end or horizon_end, horizon_end)
        out, when = [], self.start
        while when <= last:
            out.append(when)
            month = when.month - 1 + step
            when = date(when.year + month // 12, month % 12 + 1, 1)
        return out

    def annual_cents(self) -> int:
        """What the line costs in a full year, for comparing lines directly."""
        if self.frequency == "einmalig":
            return 0
        return self.amount_cents * (12 // _STEP[self.frequency])

    def monthly_equivalent_cents(self) -> int:
        """The line spread evenly over a year.

        A yearly insurance premium and a monthly rate are not comparable as
        written, and the question "what does this plan cost me a month" is the
        one actually being asked.
        """
        return round(self.annual_cents() / 12) if self.frequency != "einmalig" else 0


@dataclass(slots=True)
class Scenario:
    id: str
    name: str
    active: bool = False
    lines: list[Line] = field(default_factory=list)
    # Eine Verpflichtung ist ein Plan, der nicht abschaltbar ist. Damit teilen
    # beide dasselbe Modell und dasselbe Formular, und der Unterschied ist ein
    # Feld statt einer zweiten Datenstruktur. Abschaltbar wäre falsch: die
    # Kaufraten sind geschuldet, egal was sonst entschieden wird, und das
    # Wegrechnen einer Schuld darf kein Klick sein.
    obligation: bool = False

    def monthly_equivalent_cents(self) -> int:
        return sum(line.monthly_equivalent_cents() for line in self.lines)

    @property
    def summiert(self) -> bool:
        """Addiert die Prognose diese Klammer zu anderen auf?

        Zwei eingeschaltete Plaene sind meist zwei Varianten derselben
        Entscheidung, und die Summe waere falsch. Teilzeit addiert nichts:
        sie ersetzt einen Anteil am Gehalt, und von zweien gilt die spaeter
        begonnene.
        """
        return any(line.kind != "teilzeit" for line in self.lines)

    @property
    def nur_erwartet(self) -> bool:
        """Besteht die Klammer nur aus erwarteten Einnahmen?

        Dann ist sie keine Variante einer Entscheidung, die sich mit einer anderen beisst:
        Schenkung und Nebentaetigkeit gelten neben jedem Plan.
        """
        return bool(self.lines) and all(line.kind == "erwartet" for line in self.lines)

    def one_off_cents(self) -> int:
        # Ohne Verkauf: sein Preis ist nicht der Zufluss, das ist erst der
        # Preis nach Kosten und Restschuld -- und den kennt die Klammer nicht.
        return sum(line.amount_cents for line in self.lines
                   if line.frequency == "einmalig" and line.kind != "verkauf")


def _as_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return date(value.year, value.month, 1)
    text = str(value)
    return date.fromisoformat(text + "-01" if len(text) == 7 else text).replace(day=1)


#: Die Klammer, die es immer gibt: der Schalter fuer die Teilzeit.
TEILZEIT_ID = "teilzeit"
_TEILZEIT_KLAMMER = {"id": TEILZEIT_ID, "name": "Teilzeit", "aktiv": False,
                     "zeilen": [{"label": "Teilzeit laut Annahmen", "art": "teilzeit",
                                 "frequenz": "monatlich"}]}


def mit_teilzeit(spec: dict) -> dict:
    """Die Klammer "Teilzeit" gibt es immer, von Haus aus ausgeschaltet.

    Ihre Werte stehen in den Annahmen (Anteil, Beginn); die Klammer ist der
    Schalter. Ohne sie liesse sich die Teilzeit weder einschalten noch fuer
    einen Vergleich wieder ausschalten, und eine frische Installation kennte
    sie gar nicht.
    """
    szenarien = list(spec.get("szenarien") or [])
    if any(str(s.get("id")) == TEILZEIT_ID for s in szenarien):
        return spec
    import copy

    return {**spec, "szenarien": [*szenarien, copy.deepcopy(_TEILZEIT_KLAMMER)]}


def _teilzeit_aus_annahmen(line: Line) -> None:
    """Was die Zeile nicht selbst traegt, kommt aus den Annahmen."""
    from finctl import assumptions as _ann

    if line.anteil is None:
        line.anteil = _ann.teilzeit_anteil()
        line.aus_annahmen += ("anteil",)
    if line.start is None:
        line.start = _ann.teilzeit_ab()
        line.aus_annahmen += ("start",)


def _ohne_start(kennung, item: dict) -> ValueError:
    return ValueError(f"szenarien.yaml, {kennung}: Zeile „{item.get('label') or ''}“ hat "
                      "keinen start. Nur in der Klammer „Teilzeit“ beginnt eine Zeile ohne "
                      "start mit dem Teilzeitstart aus den Annahmen.")


def _start_der_zeile(raw: dict, item: dict, kind: str) -> tuple[date | None, bool]:
    """Der Start einer Zeile und ob er aus den Annahmen kommt.

    Eine Zeile der Klammer „Teilzeit“ ohne `start` beginnt mit dem Teilzeitstart
    und wandert mit, wenn er sich aendert (None, solange keiner eingetragen ist,
    wie bei der Teilzeitzeile selbst). Eine Teilzeitzeile holt sich ihren
    Start spaeter selbst. Jede andere Zeile ohne `start` ist ein Fehler.
    """
    start = _as_date(item.get("start"))
    if start is not None or kind == "teilzeit":
        return start, False
    if str(raw.get("id")) != TEILZEIT_ID:
        raise _ohne_start(raw.get("id"), item)
    from finctl import assumptions as _ann

    ab = _ann.teilzeit_ab()
    return ab, ab is not None


def load(spec: dict) -> list[Scenario]:
    """Read the scenarios of szenarien.yaml into objects, skipping nothing silently."""
    out = []
    for raw in mit_teilzeit(spec).get("szenarien") or []:
        lines = []
        for item in raw.get("zeilen") or []:
            freq = str(item.get("frequenz") or "monatlich")
            if freq not in FREQUENCIES:
                freq = "monatlich"
            kind = str(item.get("art") or "betrag")
            if kind not in KINDS:
                kind = "betrag"
            if kind == "verkauf":
                freq = "einmalig"
            if kind == "teilzeit":
                freq = "monatlich"
            start, start_aus_annahmen = _start_der_zeile(raw, item, kind)
            lines.append(Line(
                label=str(item.get("label") or ""),
                amount_cents=int(item.get("amount_cents") or 0),
                frequency=freq, kind=kind,
                start=start,
                aus_annahmen=("start",) if start_aus_annahmen else (),
                end=_as_date(item.get("ende")),
                account_id=item.get("konto") or None,
                category_id=item.get("kategorie") or None,
                buchungen=[str(h) for h in item.get("buchungen") or [] if h],
                property_id=item.get("objekt") or None,
                kosten_cents=int(item.get("verkaufskosten_cents") or 0),
                anteil=(float(item["anteil"]) if item.get("anteil") is not None
                        else None),
                nur_kontoprognose=kind == "wegfall"
                and bool(item.get("nur_kontoprognose"))))
            if kind == "teilzeit":
                _teilzeit_aus_annahmen(lines[-1])
        pflicht = bool(raw.get("pflicht"))
        out.append(Scenario(
            id=str(raw.get("id")), name=str(raw.get("name") or raw.get("id")),
            # Eine Verpflichtung ist immer aktiv, unabhängig vom gespeicherten
            # Haken -- sonst liesse sich das Abschaltverbot dadurch umgehen,
            # dass jemand die Datei von Hand bearbeitet.
            active=True if pflicht else bool(raw.get("aktiv")),
            lines=lines,
            obligation=pflicht))
    return out


# resolve_measured ist am 21.09.2026 entfallen. Es fuellte den Betrag einer
# Wegfall-Zeile aus dem Schnitt ihrer ganzen Kategorie -- die zweite, groebere
# Rechnung neben `messung`, und die einzige, die die Kontoprognose kannte.
# Dass eine Zeile nichts misst, sagt jetzt /planung ueber `offen`, statt dass
# eine Funktion es zurueckgibt und der Aufrufer es wegwirft.


def active(scenarios: list[Scenario]) -> list[Scenario]:
    return [s for s in scenarios if s.active]


def monthly_impact_cents(scenarios: list[Scenario]) -> int:
    """Combined monthly equivalent of everything switched on.

    One-offs are deliberately excluded: they change the balance once, not the
    rate of saving, and folding them into a monthly figure would misstate both.
    """
    return sum(s.monthly_equivalent_cents() for s in active(scenarios))


def aktive_ids(spec_path: Path | str | None = None) -> set[str]:
    """Die Kennungen der eingeschalteten Klammern.

    Verpflichtungen zaehlen immer mit -- `Scenario.active` traegt das bereits,
    weil `obligation` es erzwingt.
    """
    path = Path(spec_path) if spec_path else CONFIG_DIR / "szenarien.yaml"
    if not path.exists():
        return set()
    spec = yaml_lesen(path) or {}
    return {s.id for s in load(spec) if s.active}


def dated_amounts(scenarios: list[Scenario], horizon_end: date) -> list[dict]:
    """Every active line expanded into the months it actually lands in.

    Expanded here rather than in the projection, so the engine keeps seeing
    nothing but dated amounts and never has to know what a scenario is.
    """
    out = []
    for scenario in active(scenarios):
        for index, line in enumerate(scenario.lines):
            if line.kind in NUR_JAHRESRECHNUNG:
                continue          # siehe KINDS
            for when in line.months(horizon_end):
                out.append({
                    "zeile": index, "kind": line.kind,
                    "frequency": line.frequency, "start": line.start,
                    "end": line.end,
                    "label": f"{scenario.name}: {line.label}",
                    "month": when,
                    "amount_cents": line.amount_cents,
                    "account_id": line.account_id,
                    "category_id": line.category_id,
                    "scenario_id": scenario.id,
                    # Ein Wegfall ist positiv und trotzdem eine Kostenminderung.
                    # Ohne das landet er als Einnahme und hebt den
                    # Monatstiefpunkt nicht, obwohl genau er sich verbessert.
                    "reduces_cost": line.kind == "wegfall",
                })
    return out


# ------------------------------------------------------- geschlossener Kreis
#
# Eine Planzeile wirkt nur mit dem Teil, der NOCH NICHT in der Messung steckt.
#
# Die Extrapolation misst die letzten zwoelf Monate und schreibt sie fort. Ein
# Posten, der wegfaellt, steckt dort noch drin, bis er aus dem Fenster
# herausgelaufen ist; ein Posten, der neu dazukommt, steckt dort schon drin,
# sobald er gebucht wird. Ohne diesen Ausgleich zieht ein Wegfall ein Jahr
# nach dem Ende doppelt ab, und neue Kosten zaehlen doppelt, sobald sie im
# Ledger stehen.
#
# Kein Enddatum, kein Betrag von Hand: die Zeile schaut bei jedem Lauf nach,
# wie viel von ihr noch im Fenster steckt, und das schrumpft mit jedem
# importierten Monat von selbst.

def messung(conn, line: Line, f, reihen=None, ohne=frozenset()) -> dict:
    """Was von dieser Zeile im Messfenster steckt.

    NUR ZUGEORDNETES ZAEHLT: genau diese Buchungen, und die Reihe, zu der
    sie gehoeren -- dieselbe Gegenpartei in derselben Kategorie, definiert in
    `finctl/ledger/reihe.py`. Dieselbe Definition nimmt `abos.ausschluesse`:
    eine Erklaerung soll auf beiden Wegen dasselbe aus der Messung nehmen.
    Ohne Zuordnung zaehlt nichts. Ein stiller Rueckfall auf die ganze
    Kategorie hat verschleiert, woran eine Zeile eigentlich rechnet; was
    passen koennte, zeigt `vorschlaege`, und gezaehlt wird es erst nach dem
    Zuordnen.

    Mit `reihen` (`takt.Reihen` zum Ende des Fensters) steht dazu, was die
    zugeordneten Buchungen in der Basis der Hochrechnung zaehlen
    (`takt.beitrag_in_basis`): `takt_jahr` die Jahreswerte ihrer laufenden Reihen
    mit festem Takt, `rest_cents` den Rest im Fenster, `takt_reihen` die Reihen mit
    ihrem Takt als Text. `cents` bleibt die Summe im Fenster: Die Kontoprognose
    rechnet damit.

    `ohne` sind Buchungen, die eine andere Quelle schon zaehlt und die Messung nicht sieht
    (die Reihe eines Vertrags und die Zahlungen seiner Mitzahler): Eine Wegfall-Zeile nimmt
    nur, was die Basis noch misst. Fuer eine einmalige Zeile gilt das nicht.
    """
    from finctl.ledger import reihe as _reihe

    leer = {"cents": 0, "monate": f.monate if f else 0, "buchungen": [],
            "quelle": "keine"}
    if f is None or conn is None or line.kind in NUR_JAHRESRECHNUNG:
        return leer
    bedingung = ["t.booking_date BETWEEN ? AND ?",
                 "COALESCE(s.mgmt_category_id, '') NOT LIKE 'transfer/%'"]
    args: list = [f.von.isoformat(), f.bis.isoformat()]
    if line.buchungen:
        # Einmalige Zeilen stehen fuer GENAU diese Zahlung: eine Anzahlung
        # wiederholt sich nicht, und ihre Reihe gibt es nicht.
        treffer = ([h for h in _reihe.hashes(conn, line.buchungen) if h not in ohne]
                   if line.frequency != "einmalig" else sorted(set(line.buchungen)))
        if not treffer:
            return leer
        bedingung.append(f"t.dedup_hash IN ({','.join('?' * len(treffer))})")
        args += treffer
        quelle = "zugeordnet"
    else:
        return leer
    # Zieht eine Reihe nur von einem Konto weg, gehoert nur ihr Teil auf diesem
    # Konto zur Zeile; auf den anderen laeuft sie weiter.
    if line.nur_kontoprognose and line.account_id:
        bedingung.append("t.account_id = ?")
        args.append(line.account_id)
    # Neue Kosten zaehlen erst ab ihrem Start: was davor in der Kategorie lief,
    # ist etwas anderes.
    if line.kind == "betrag" and line.start and line.frequency != "einmalig":
        bedingung.append("t.booking_date >= ?")
        args.append(line.start.isoformat())
    rows = conn.execute(
        f"""SELECT t.dedup_hash, t.booking_date, t.account_id, s.amount_cents,
                   substr(t.raw_text, 1, 80) AS text, s.mgmt_category_id AS kategorie
            FROM   transactions t JOIN splits s ON s.transaction_id = t.id
            WHERE  {' AND '.join(bedingung)}
            ORDER  BY t.booking_date DESC""", args).fetchall()
    buchungen = [dict(r) for r in rows]
    gemessen = {"cents": sum(b["amount_cents"] for b in buchungen), "monate": f.monate,
                "buchungen": buchungen, "quelle": quelle}
    if reihen is not None:
        gemessen.update(_im_takt(conn, reihen, f, bedingung[1:], args[2:]))
    return gemessen


def _im_takt(conn, reihen, f, bedingung: list[str], args: list) -> dict:
    """Was die zugeordneten Teile in der Basis zaehlen. Gesucht wird ohne das
    Fenster: Eine laufende Reihe zaehlt in der Basis auch mit einem Termin davor."""
    from finctl.forecast import takt as _takt

    alle = conn.execute(
        f"""SELECT t.dedup_hash, COALESCE(s.mgmt_category_id, '') AS kategorie,
                   t.booking_date, s.amount_cents
            FROM   transactions t JOIN splits s ON s.transaction_id = t.id
            WHERE  {' AND '.join(bedingung)}""", args).fetchall()
    b = _takt.beitrag_in_basis(
        ((h, k, date.fromisoformat(tag), int(c)) for h, k, tag, c in alle), reihen,
        von=f.von, bis=f.bis)
    return {"takt_jahr": b.takt_jahr, "rest_cents": b.rest_cents,
            "takt_reihen": [f"{r.gegenpartei}: {r.beitrag.text}" for r in b.reihen
                            if r.beitrag]}


def gemessen_je_monat(m: dict) -> float:
    """Was die zugeordneten Buchungen in der Basis der Hochrechnung je Monat zaehlen:
    mit Reihen ihr Beitrag nach Takt (`messung`), sonst die Summe des Fensters durch
    seine Monate."""
    n = m.get("monate") or 0
    if "takt_jahr" in m:
        return m["takt_jahr"] / 12 + (m["rest_cents"] / n if n else 0)
    return m["cents"] / n


def vorschlaege(conn, line: Line, f, limit: int = 60) -> list[dict]:
    """Buchungen, die zu dieser Zeile passen koennten: ihre Kategorie im
    Messfenster, noch nicht zugeordnet. Ein Vorschlag zaehlt nicht, bis er
    zugeordnet ist."""
    if f is None or conn is None or not line.category_id \
            or line.kind in NUR_JAHRESRECHNUNG:
        return []
    bedingung = ["t.booking_date BETWEEN ? AND ?", "s.mgmt_category_id = ?"]
    args: list = [f.von.isoformat(), f.bis.isoformat(), line.category_id]
    if line.account_id:
        bedingung.append("t.account_id = ?")
        args.append(line.account_id)
    if line.kind == "betrag" and line.start and line.frequency != "einmalig":
        bedingung.append("t.booking_date >= ?")
        args.append(line.start.isoformat())
    if line.buchungen:
        bedingung.append(f"t.dedup_hash NOT IN ({','.join('?' * len(line.buchungen))})")
        args += line.buchungen
    return [dict(r) for r in conn.execute(
        f"""SELECT t.dedup_hash, t.booking_date, t.account_id, s.amount_cents,
                   substr(t.raw_text, 1, 80) AS text, s.mgmt_category_id AS kategorie
            FROM   transactions t JOIN splits s ON s.transaction_id = t.id
            WHERE  {' AND '.join(bedingung)}
            ORDER  BY t.booking_date DESC LIMIT ?""", [*args, limit])]


def einmalig_zugeordnet(scenarios: list[Scenario]) -> set[str]:
    """Buchungen einmaliger Zeilen -- sie gehoeren nicht in die Basis."""
    return {h for s in scenarios for line in s.lines
            if line.frequency == "einmalig" for h in line.buchungen}


def erwartet_zugeordnet(conn, scenarios: list[Scenario]) -> set[str]:
    """Buchungen erwarteter Einnahmen und ihrer Reihe -- sie zaehlt keine Messung.

    Nur eingeschaltete Klammern: Wer eine Klammer ausschaltet, bekommt die Messung
    zurueck, statt dass die Einnahme in keiner Rechnung mehr steht. Die Reihe kommt
    dazu (`ledger.reihe.hashes`), denn die Zeile ersetzt die ganze Spur im Hauptbuch,
    nicht die Haelfte davon.
    """
    from finctl.ledger import reihe as _reihe

    zugeordnet = [h for s in active(scenarios) for line in s.lines
                  if line.kind == "erwartet" for h in line.buchungen]
    if not zugeordnet or conn is None:
        return set(zugeordnet)
    return set(_reihe.hashes(conn, zugeordnet))


def _gleiches_vorzeichen(a: int, b: int) -> bool:
    return (a >= 0) == (b >= 0)


def restbetrag_je_termin(line: Line, m: dict, steigerung: float = 1.0) -> int:
    """Was die Zeile an EINEM ihrer Termine noch beitraegt.

    `steigerung` ist der Faktor, um den das Gemessene bis zu diesem Termin gestiegen
    ist (`wachstum.faktor`): Die Reihe steigt in der Basis, und was die Zeile von ihr
    abzieht, steigt mit. Der geplante Betrag ist eine gesetzte Zahl und bleibt flach.

    Dieselbe Rechnung wie `restwirkung_monatlich`, nur nicht auf den Monat
    geglaettet: die Kontoprognose braucht den Tag, an dem das Geld geht. Eine
    Jahrespraemie als Zwoelftel reisst den Monatstiefpunkt nicht, den sie in
    Wahrheit reisst, und genau den liest die Dispo-Warnung.
    """
    n = m.get("monate") or 0
    if line.kind in NUR_JAHRESRECHNUNG or line.nur_kontoprognose:
        return 0
    if line.kind == "erwartet":
        return line.amount_cents      # voll: ihre Buchungen zaehlen in keiner Messung
    if line.kind == "wegfall":
        return round(-m["cents"] / n * steigerung) if n else 0
    if line.frequency == "einmalig":
        return 0 if line.buchungen else line.amount_cents
    if not n:
        return line.amount_cents
    # Gemessen wird je Monat; ein Termin deckt so viele Monate, wie sein Takt
    # lang ist. Sonst zoege eine Jahreszeile einen Monatswert ab.
    rest = line.amount_cents - round(
        m["cents"] / n * _STEP.get(line.frequency, 1) * steigerung)
    return rest if rest and _gleiches_vorzeichen(rest, line.amount_cents) else 0


def restwirkung_monatlich(line: Line, m: dict) -> int:
    """Was die Zeile je Monat noch zur Prognose beitraegt -- fuer die Seite.

    Derselbe Rest wie `restbetrag_je_termin`, auf den Monat verteilt, damit
    Zeilen verschiedener Takte vergleichbar nebeneinander stehen.
    """
    if line.kind in (*NUR_JAHRESRECHNUNG, "wegfall") or line.frequency == "einmalig":
        return restbetrag_je_termin(line, m)
    return round(restbetrag_je_termin(line, m) / _STEP.get(line.frequency, 1))


def jahreswirkung(line: Line, m: dict, year: int, after_month: int,
                  horizon_end: date, steigerung: float = 1.0) -> int:
    """Was die Zeile in einem projizierten Jahr beitraegt, im Kreis gerechnet.

    `steigerung` ist der Faktor, um den das Gemessene von der Mitte des Messfensters bis
    zur Mitte des Jahres gestiegen ist (`wachstum.faktor`), wie die Reihe in der Basis.
    Der geplante Betrag ist gesetzt und steigt nicht.
    """
    if line.kind in NUR_JAHRESRECHNUNG:
        return 0              # wirkt ueber jahre.verkaeufe bzw. das Gehalt
    if line.nur_kontoprognose:
        return 0              # der Haushalt gibt weiter aus, nur anderswo
    n = m.get("monate") or 0
    if line.kind == "erwartet":
        # Voll, mit festem Betrag: die Messung hat ihre Buchungen nicht gezaehlt.
        return sum(line.amount_cents for w in line.months(horizon_end)
                   if w.year == year and w.month > after_month)
    if line.frequency == "einmalig":
        if line.buchungen:
            return 0          # gebucht: steht im Bestand, nicht mehr in der Zukunft
        return sum(line.amount_cents for w in line.months(horizon_end)
                   if w.year == year and w.month > after_month)
    aktiv = [mm for mm in range(after_month + 1, 13)
             if line.start and date(year, mm, 1) >= line.start
             and (line.end is None or date(year, mm, 1) <= line.end)]
    if not aktiv:
        return 0
    if line.kind == "wegfall":
        return round(-gemessen_je_monat(m) * steigerung * len(aktiv)) if n else 0
    geplant = sum(line.amount_cents for w in line.months(horizon_end)
                  if w.year == year and w.month > after_month)
    if not n:
        return geplant
    rest = geplant - round(gemessen_je_monat(m) * steigerung * len(aktiv))
    return rest if rest and _gleiches_vorzeichen(rest, geplant) else 0


def verkaufszeilen(scenarios: list[Scenario]) -> list[tuple[Scenario, int, Line]]:
    """Die Verkaufszeilen eingeschalteter Klammern."""
    return [(s, i, line) for s in active(scenarios)
            for i, line in enumerate(s.lines)
            if line.kind == "verkauf" and line.property_id and line.start]


def teilzeitzeilen(scenarios: list[Scenario]) -> list[tuple[Scenario, int, Line]]:
    """Die Teilzeitzeilen eingeschalteter Klammern, frueh begonnene zuerst."""
    zeilen = [(s, i, line) for s in active(scenarios)
              for i, line in enumerate(s.lines)
              if line.kind == "teilzeit" and line.start and line.anteil is not None]
    return sorted(zeilen, key=lambda z: z[2].start)


def teilzeit_im_monat(zeilen: list[tuple[Scenario, int, Line]],
                      monat: date) -> tuple[Scenario, int, Line] | None:
    """Welche Teilzeitzeile in diesem Monat gilt -- die zuletzt begonnene."""
    treffer = None
    for z in zeilen:
        line = z[2]
        if line.start <= monat and (line.end is None or monat <= line.end):
            treffer = z
    return treffer
