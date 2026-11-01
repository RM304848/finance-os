"""Does the forecast describe the same world as the ledger?

A projection that misses the current year misses 2045 too -- it just does not
look like it. So before anything is projected twenty years out, the same block
definitions are run against both sides for the year in progress and the
difference is shown.

A difference means one of two things, and both are worth knowing: a rule is
missing, so spending is landing somewhere the plan does not look, or an
assumption is wrong. Neither announces itself.

BLOCKS ARE ORDERED AND FIRST MATCH WINS, and that is not a detail. The naive
definitions overlap: `kredit/tilgung` and `kredit/zinsen` both carry the
`fixkosten` flag, so a fixed-cost total that simply sums the flag counts the
loan payments a second time -- with 1.500 a month in rates, 4.000 where the
honest figure is 2.500. Ordering makes the overlap impossible rather than merely documented.

The last block catches whatever no earlier one claimed, so the blocks always
partition the ledger completely. That is what makes the sum test meaningful:
if the parts do not add up to the whole, something is being counted twice or
dropped, and the test says so instead of the totals quietly disagreeing.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from finctl.forecast import messung, wachstum
from finctl.pfade import CONFIG_DIR


@dataclass(frozen=True, slots=True)
class Block:
    id: str
    label: str
    #: SQL fragment over `s` (splits), `m` (mgmt_categories) and `t`
    #: (transactions). Evaluated in order; the first match claims the split.
    where: str
    #: Income blocks read better positive, cost blocks positive-as-magnitude.
    income: bool = False
    #: Wird bei der Zuordnung vor allen anderen geprueft, steht in der Anzeige
    #: aber an seiner Stelle in `bloecke()`: Reihenfolge der Auswertung und der
    #: Anzeige sind zwei Dinge.
    zuerst: bool = False


#: Kennung des Objektblocks: alle Objekte, deren Ertrag angenommen statt
#: gemessen wird. WELCHE das sind, sagt `prognose:` je Objekt in
#: properties.yaml -- hier steht nur, dass sie einen Block teilen.
OBJEKT = "objekt"


def _prognosen() -> list:
    from finctl import objekte

    return objekte.prognosen()


def _objekt_planned() -> dict[str, Planned]:
    """Die Objektzeile des Abgleichs -- leer, wenn kein Objekt eine Prognose hat.

    Eigene Funktion, damit `planned` nicht um eine Verzweigung waechst: die
    Ratsche in tests/test_lint.py haelt sie bei elf.
    """
    liste = _prognosen()
    if not liste:
        return {}
    teile = [(f"{p.name}: " if len(liste) > 1 else "")
             + _eur(p.miete_cents) + " Miete minus " + _eur(p.kosten_cents) + " Kosten"
             for p in liste]
    return {OBJEKT: Planned(
        sum(p.netto_cents for p in liste),
        note="Annahme: " + "; ".join(teile)
             + "; gemessen ist, was bisher gebucht wurde")}


def objekt_name() -> str:
    """Der Name fuer Beschriftungen: das eine Objekt, sonst "Objekte"."""
    liste = _prognosen()
    return liste[0].name if len(liste) == 1 else "Objekte"


#: Kennung des Blocks `einmalig`: was geschehen ist und nicht wiederkommt. Er
#: faengt jeden Teil einer Kategorie mit dem Merkmal `einmalig` und jeden Teil
#: einer Buchung, die der Haushalt einmalig gesetzt hat (`finctl/reihen.py`).
EINMALIG = "einmalig"


def _einmalig_block() -> Block:
    """Der Block `einmalig`: Was einmalig ist, gehoert in keinen anderen Block,
    auch nicht ins Gehalt. Deshalb wertet `_case_expression` ihn zuerst aus; in
    der Anzeige steht er an der Stelle, an der vorher die Sondereffekte standen.

    Die Kennungen der gesetzten Buchungen stehen als Text im SQL (wie die des
    Objektblocks); `reihen.lesen` prueft, dass es Hexzeichen sind, bevor sie
    hier ankommen.
    """
    from finctl import reihen

    kennungen = ", ".join(f"'{h}'" for h in sorted(reihen.einmalige_hashes()))
    bedingung = "COALESCE(m.einmalig, 0) = 1"
    if kennungen:
        bedingung += f" OR t.dedup_hash IN ({kennungen})"
    return Block(EINMALIG, "Einmalig", bedingung, zuerst=True)


def einmalige_kategorien(conn: sqlite3.Connection) -> frozenset[str]:
    """Die Kategorien mit dem Merkmal `einmalig`."""
    return frozenset(r[0] for r in conn.execute(
        "SELECT id FROM mgmt_categories WHERE einmalig = 1"))


def _objekt_block() -> Block | None:
    """Die Objekte, deren Ertrag angenommen statt gemessen wird.

    EIGENER BLOCK, Mieten und laufende Kosten zusammen. Es stand genau ein
    Mietmonat im Ledger. Ueber acht vollstaendige Monate gemittelt ist das
    ein Achtel dessen, was das Objekt tatsaechlich abwirft. Bliebe es in
    `miete` und `immobilie`, wuerde die Jahresrechnung genau diese
    Verwaesserung zwanzig Jahre fortschreiben.

    Herausgeloest ist der Block im Abgleich sichtbar und in der
    Jahresrechnung durch eine erklaerte Annahme ersetzbar, statt still aus
    einem einzelnen Monat hochgerechnet zu werden. Die Kennungen prueft
    `objekte.prognosen`, bevor sie hier in SQL eingehen.
    """
    liste = _prognosen()
    if not liste:
        return None
    kennungen = ", ".join(f"'{p.id}'" for p in liste)
    return Block(OBJEKT, objekt_name(), f"s.property_id IN ({kennungen})")


def bloecke() -> tuple[Block, ...]:
    """Die Bloecke in ihrer Reihenfolge; der erste Treffer gewinnt.

    Eine Funktion und keine Konstante, weil genau einer der Bloecke aus der
    Konfiguration kommt. Wer kein Objekt mit Prognose hat, bekommt die Liste
    ohne ihn -- und sonst aendert sich nichts.
    """
    objekt = _objekt_block()
    return (
        # Genau das Gehalt. Eine Unterkategorie (`einkommen/gehalt-…`, etwa eine
        # Nebentaetigkeit) ist ein anderes Einkommen: Sie zaehlt unter `einkommen_sonst`,
        # wo die Rechnung sie fortschreibt oder eine erwartete Einnahme sie ersetzt.
        Block("gehalt", "Gehalt",
              "s.mgmt_category_id = 'einkommen/gehalt'", income=True),
        # Einmaliges vor allem Folgenden: Kaufraten wuerden jeden Monatsschnitt
        # dominieren und den Vergleich unbrauchbar machen. Bei der Zuordnung steht
        # es durch `zuerst` sogar vor dem Gehalt.
        _einmalig_block(),
        *((objekt,) if objekt else ()),
        Block("miete", "Mieteinnahmen",
              "s.mgmt_category_id = 'immobilie/mieteinnahme'", income=True),
        Block("einkommen_sonst", "sonstige Einnahmen",
              "s.mgmt_category_id LIKE 'einkommen/%'", income=True),
        # Vor den Fixkosten, weil Tilgung und Zinsen das fixkosten-Flag tragen.
        Block("kredit", "Kreditraten",
              "s.mgmt_category_id LIKE 'kredit/%'"),
        Block("immobilie", "Immobilienkosten",
              "s.mgmt_category_id LIKE 'immobilie/%'"),
        Block("fixkosten", "Fixkosten",
              "COALESCE(m.fixkosten, 0) = 1"),
        Block("investment", "Investment",
              "s.mgmt_category_id LIKE 'investment/%'"),
        Block("steuern", "Steuern",
              "s.mgmt_category_id LIKE 'steuern/%'"),
        # Faengt alles ab, was keiner der vorigen beansprucht hat. Ohne ihn
        # waere der Summentest nicht aussagekraeftig.
        Block("konsum", "Konsum und Rest", "1 = 1"),
    )


@dataclass(slots=True)
class Planned:
    """A planned figure and the months it actually covers.

    The window matters as much as the number. A loan schedule is anchored at
    the most recently observed balance -- some months into the year -- so it
    describes the future correctly and cannot reproduce the months before that
    anchor at all. Comparing its three covered months against eight measured
    ones puts one payment against eight and invites the conclusion that
    something is broken. Nothing is: the two sides were being asked about
    different months.
    """

    cents_per_month: int
    months: int | None = None      # None -> alle vollstaendigen Monate
    note: str = ""


@dataclass(slots=True)
class Row:
    block: Block
    measured_cents: int = 0
    planned_cents: int = 0
    #: Ueber wie viele Monate beide Seiten verglichen wurden.
    window_months: int = 0
    note: str = ""

    @property
    def delta_cents(self) -> int:
        return self.planned_cents - self.measured_cents


@dataclass(slots=True)
class Abgleich:
    #: Erster und letzter Tag des Messfensters, fuer Links auf die
    #: Transaktionsseite.
    von: str = ""
    bis: str = ""
    months: int = 0
    rows: list[Row] = field(default_factory=list)
    unassigned_cents: int = 0

    def by_id(self, block_id: str) -> Row:
        return next(r for r in self.rows if r.block.id == block_id)

def _eur(cents: int) -> str:
    """Deutsche Schreibweise. f-strings liefern 2,900 statt 2.900."""
    from finctl.ledger.db import format_eur

    return format_eur(cents)


def _case_expression() -> str:
    """One CASE that assigns every split to the first block it matches."""
    # Stabil sortiert: `zuerst` rueckt nach vorn, der Rest behaelt seine Folge.
    ordnung = sorted(bloecke(), key=lambda b: not b.zuerst)
    arms = "\n".join(f"        WHEN {b.where} THEN '{b.id}'" for b in ordnung)
    return f"CASE\n{arms}\n    END"


def block_der_kategorie(conn: sqlite3.Connection, kategorie: str) -> str | None:
    """Der Block einer Kategorie, auch ohne Buchung im Fenster."""
    row = conn.execute(
        f"SELECT {_case_expression()} AS block FROM (SELECT ? AS mgmt_category_id, "
        "NULL AS property_id) s LEFT JOIN mgmt_categories m ON m.id = s.mgmt_category_id "
        "CROSS JOIN (SELECT NULL AS dedup_hash) t",
        (kategorie,)).fetchone()
    return row["block"] if row else None


@dataclass(frozen=True, slots=True)
class Fenster:
    """Die letzten vollstaendigen Monate, ueber die gemessen wird.

    ROLLIEREND statt Kalenderjahr. Ueber das angebrochene Jahr gemessen und
    auf zwoelf Monate hochgerechnet zaehlte jede Jahreszahlung, die zufaellig
    in die bisherigen Monate fiel, anderthalbfach -- die KFZ-Versicherung aus
    Januar und Februar mit 920 statt 613 --, und was erst im Herbst faellig
    ist, fehlte ganz. Ueber zwoelf Monate steht jede Jahreszahlung genau einmal
    drin, ohne Hochrechnen. Und am 1. Januar gibt es kein leeres Jahr mehr,
    das man abfangen muss.
    """

    von: date          # erster Tag des ersten Monats
    bis: date          # letzter Tag des letzten Monats
    monate: int

    @property
    def mitte(self) -> float:
        """Die Mitte des Fensters als Jahreszahl, fuer die Inflation."""
        return wachstum.fenstermitte(self.von, self.monate)

    def monatsliste(self) -> list[date]:
        return [_plus_monate(self.von, i) for i in range(self.monate)]


def _plus_monate(d: date, n: int) -> date:
    idx = d.year * 12 + d.month - 1 + n
    return date(idx // 12, idx % 12 + 1, 1)


def _month_end(day: date) -> date:
    nxt = date(day.year + (day.month == 12), day.month % 12 + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


def folgetag(bis: date) -> date:
    """Der erste Tag nach dem Monat von `bis`: der Tag, an dem man steht, wenn
    man nur bis `bis` weiss."""
    return _month_end(bis) + timedelta(days=1)


def letzter_vollstaendiger_monat(conn: sqlite3.Connection,
                                 bis: date | None = None) -> date | None:
    """Der letzte Monat, den ALLE Konten vollstaendig abdecken.

    Fuer jedes Konto ist das der Monat seines letzten Auszugsendes, wenn das
    auf den Monatsletzten faellt, sonst der Monat davor: ein Auszug bis zum
    4. deckt von seinem Monat ein Fuenftel ab, und das Gehalt dafuer ist noch
    nicht gezahlt. Ein Monat ist erst vollstaendig, wenn er es ueberall ist.

    Mit `bis` hoechstens dessen Monatsende: so, als waere heute der erste Tag
    danach. Was spaeter eingelesen wurde, ist dann nicht da. Ein Konto, dessen
    erster Auszug erst nach `bis` beginnt, zaehlt trotzdem mit; die Auszuege
    gibt es ja jetzt.
    """
    rows = conn.execute(
        "SELECT account_id, MAX(period_end) AS last FROM statements "
        "WHERE status = 'imported' GROUP BY account_id").fetchall()
    if not rows:
        return None
    enden = []
    for row in rows:
        last = date.fromisoformat(row["last"])
        if last != _month_end(last):
            last = date.fromordinal(last.replace(day=1).toordinal() - 1)
        enden.append(last)
    if not enden:
        return None
    ende = min(enden)
    return min(ende, _month_end(bis)) if bis is not None else ende


#: Wie viele Monate das Messfenster umfasst. Kontoprognose und Hochrechnung messen
#: beide darueber (`fenster`): zwoelf Monate sehen jede Jahrespraemie und glaetten
#: einzelne grosse Buchungen.
FENSTER_MONATE = 12


def fenster(conn: sqlite3.Connection, monate: int = FENSTER_MONATE,
            bis: date | None = None) -> Fenster | None:
    """Die letzten `monate` vollstaendigen Monate -- oder weniger, wenn das
    Ledger juenger ist. None, wenn nichts gemessen ist. Mit `bis` die
    `monate` bis zu dessen Monatsende (`letzter_vollstaendiger_monat`)."""
    ende = letzter_vollstaendiger_monat(conn, bis)
    if ende is None:
        return None
    von = _plus_monate(ende.replace(day=1), -(monate - 1))
    erster = conn.execute(
        "SELECT MIN(period_start) FROM statements WHERE status = 'imported'"
    ).fetchone()[0]
    if erster:
        e = date.fromisoformat(erster)
        voll = e if e.day == 1 else _plus_monate(e.replace(day=1), 1)
        von = max(von, voll)
    if von > ende:
        return None
    anzahl = (ende.year * 12 + ende.month) - (von.year * 12 + von.month) + 1
    return Fenster(von=von, bis=ende, monate=anzahl)


def _gemessen(conn: sqlite3.Connection, f: Fenster, ohne: set[str] | None,
              *, je_block: bool = True) -> list[messung.Monatssumme]:
    """Die Monatssummen im Fenster, je Block und Kategorie.

    Umbuchungen sind weder Einnahme noch Kosten, also kommen sie in keinen Block
    (Regel "praefix" der Messung) statt in einen eigenen.
    """
    return messung.monatssummen(
        conn, von=f.von, bis=f.bis,
        ausschluss=messung.Ausschluss(hashes=frozenset(ohne or ())),
        je_block=je_block)


def measure(conn: sqlite3.Connection, f: Fenster,
            ohne: set[str] | None = None) -> dict[str, int]:
    """What the ledger says, per block, over the window.

    `ohne` nimmt einzelne Buchungen heraus -- die einer einmaligen
    Planposition. Eine Anzahlung, die im Fenster gebucht ist, wuerde sonst
    als laufender Posten jedes Jahr wiederkehren.
    """
    summen = messung.summiere(_gemessen(conn, f, ohne), lambda z: z.block)
    return dict(sorted(summen.items()))


def measure_kategorien(conn: sqlite3.Connection, f: Fenster,
                       ohne: set[str] | None = None) -> dict[str, dict[str, int]]:
    """Wie `measure`, aber je Block noch einmal je Kategorie aufgeteilt.

    DIESELBE Zuordnung und dieselben Ausschluesse, damit die Kategorien exakt
    auf die Blocksumme aufgehen. Eine zweite, aehnliche Abfrage wuerde sich
    irgendwann um eine Buchung von der ersten unterscheiden, und dann erklaert
    der Rechenweg eine andere Zahl als die angezeigte.

    Eine Buchung ohne Kategorie steht unter dem leeren Schluessel.
    """
    summen = messung.summiere(_gemessen(conn, f, ohne),
                              lambda z: (z.block, z.kategorie))
    out: dict[str, dict[str, int]] = {}
    for (block, kategorie), cents in sorted(summen.items()):
        out.setdefault(block, {})[kategorie] = cents
    return out


def total_excluding_transfers(conn: sqlite3.Connection, f: Fenster,
                              ohne: set[str] | None = None) -> int:
    # Ohne Block: die Gesamtsumme haengt nicht an der Zuordnung, und der
    # Summentest in `build` soll sie gerade daran messen.
    return sum(z.cents for z in _gemessen(conn, f, ohne, je_block=False))


def build(conn: sqlite3.Connection, planned: dict | None = None,
          ohne: set[str] | None = None) -> Abgleich:
    """The measured side, and the planned side where one is supplied.

    `planned` is per-block and per MONTH, like the measured column, so the two
    are read side by side without anyone converting in their head.
    """
    f = fenster(conn)
    if f is None:
        return Abgleich()
    measured = measure(conn, f, ohne)
    planned = planned or {}
    out = Abgleich(von=f.von.isoformat(), bis=f.bis.isoformat(), months=f.monate)
    for block in bloecke():
        entry = planned.get(block.id)
        if isinstance(entry, Planned):
            window = entry.months or f.monate
            note, planned_cents = entry.note, entry.cents_per_month
        else:
            window, note = f.monate, ""
            planned_cents = int(entry or 0)

        if window == f.monate:
            measured_cents = round(measured.get(block.id, 0) / f.monate)
        else:
            # Beide Seiten ueber DASSELBE Fenster, sonst vergleicht man
            # verschiedene Monate und nennt die Differenz einen Fehler.
            tail = Fenster(von=_plus_monate(f.bis.replace(day=1), -(window - 1)),
                           bis=f.bis, monate=window)
            measured_cents = round(measure(conn, tail, ohne).get(block.id, 0) / window)

        out.rows.append(Row(block=block, measured_cents=measured_cents,
                            planned_cents=planned_cents,
                            window_months=window, note=note))
    # Was die Bloecke zusammen NICHT erklaeren. Muss null sein: der letzte
    # Block faengt alles ab, also ist ein Rest hier ein Fehler in der Abfrage
    # und keine Eigenschaft der Daten.
    out.unassigned_cents = (total_excluding_transfers(conn, f, ohne)
                            - sum(measured.values()))
    return out


# ------------------------------------------------------------ die Planseite

def planned(conn: sqlite3.Connection, f: Fenster | None = None,
            ohne: set[str] | None = None) -> dict[str, Planned]:
    """What the plan says, per block and per month, over the window.

    Drawn from the sources the annual projection will use, so that what is
    compared here is what will be projected forward -- not a second
    calculation that happens to agree today.

    Three of the blocks have a source INDEPENDENT of the ledger, and those are
    the ones this comparison actually tests:

      Gehalt        the floor (Untergrenze) -- the figure BOTH projections
                    use since Schritt 5b, E.3. The gap to what is booked is a
                    deliberate margin, not an error; the median stands beside
                    it on /annahmen, as a comparison only.
      Kreditraten   the amortisation schedules in loans.yaml
      Objekt        the assumption, against what has actually been booked

    The rest -- fixed costs, consumption, property costs -- is the measured
    average, because that is what a base budget is. Their delta is small by
    construction and says little; the honest reading is that those rows
    confirm the blocks partition cleanly.
    """
    from finctl import assumptions as ann
    from finctl.forecast import szenarien as sz
    from finctl.realestate.loan import (
        amortise,
        lade_kredite,
        nur_wirksame,
        opening_balance_cents,
        segments_from,
    )

    f = f or fenster(conn)
    if f is None:
        return {}
    out: dict[str, Planned] = {}

    out["gehalt"] = Planned(ann.salary_floor_cents(),
                            note="Untergrenze; beide Rechnungen rechnen vorsichtig mit ihr")
    out.update(_objekt_planned())

    monate = {(m.year, m.month) for m in f.monatsliste()}
    per_month: dict[tuple[int, int], int] = {}
    starts: list[tuple[int, int]] = []
    spaet: list[str] = []
    # Nur Kredite, die gelten: ein Vorlagenkredit haengt an seiner Klammer und
    # zaehlt nicht, solange sie aus ist -- sonst stand die Kreditzeile wegen
    # eines Eigenheims ab 2030 dauerhaft auf "nicht vergleichbar".
    for loan in nur_wirksame(lade_kredite(CONFIG_DIR), sz.aktive_ids()):
        if not loan.get("segments"):
            continue
        try:
            sched = amortise(loan["id"], opening_balance_cents(loan),
                             segments_from(loan))
        except Exception:
            continue
        if not sched.payments:
            continue
        erste = (sched.payments[0].month.year, sched.payments[0].month.month)
        starts.append(erste)
        if erste > (f.von.year, f.von.month):
            name = str(loan.get("name") or loan.get("id")).split(" --")[0]
            spaet.append(f"{name} ab {erste[0]}-{erste[1]:02d}")
        for p in sched.payments:
            schluessel = (p.month.year, p.month.month)
            if schluessel in monate:
                per_month[schluessel] = per_month.get(schluessel, 0) + p.payment_cents
    # Nur die Monate, in denen ALLE Plaene laufen: ein Plan, der im September
    # anfaengt, sagt ueber den Maerz nichts, und ihn mit null einzurechnen
    # waere eine Aussage, die niemand getroffen hat.
    spaetester = max(starts) if starts else (f.von.year, f.von.month)
    full = sorted(m for m in per_month if m >= spaetester)
    if full:
        window = len(full)
        avg = -round(sum(per_month[m] for m in full) / window)
        note = ("" if window == f.monate
                else f"alle Pläne erst ab {full[0][0]}-{full[0][1]:02d}")
        out["kredit"] = Planned(avg, months=window, note=note)
    else:
        out["kredit"] = Planned(
            0, months=f.monate,
            note="nicht vergleichbar — " + ", ".join(spaet)
                 + "; am zuletzt beobachteten Saldo verankert")

    measured = measure(conn, f, ohne)
    for block in bloecke():
        out.setdefault(block.id, Planned(round(measured.get(block.id, 0) / f.monate)))
    return out
