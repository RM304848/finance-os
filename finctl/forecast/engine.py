"""Monthly cash-flow projection with intra-month liquidity.

The month-end balance is the wrong number to steer by. Costs land at the start
of the month and salary at the end, so the lowest point inside a month sits
well below where it closes. A projection that only reports month-end can show
a comfortable year while you are repeatedly in the Dispokredit.

This reproduces the sequence the Haushaltsbuch already modelled by hand:

    vor Gehalt  ->  minus all costs  ->  nach Kosten  ->  plus income  ->  nach Gehalt
                                         ^^^^^^^^^^^
                                         the trough that matters

`nach Gehalt` carries into the next month as `vor Gehalt`. The Dispo warning
fires on the trough, never on the closing balance.

Assuming every cost precedes every receipt is deliberately pessimistic. It is
the right bias for a liquidity guard: being warned about a trough that does
not materialise costs nothing, while missing one costs Dispo interest.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date

from finctl.forecast import fortschreibung, wachstum, zinsen
from finctl.forecast.herkunft import Posten
from finctl.forecast.takt import Reihen
from finctl.forecast.verfahren import add_months
from finctl.realestate.loan import Schedule

# Days used when an item carries none. Pessimistic by design: costs assumed
# at the start of the month, receipts at the end.
UNDATED_COST_DAY, UNDATED_INCOME_DAY = 1, 28


@dataclass(slots=True)
class RecurringItem:
    label: str
    account_id: str
    amount_cents: int              # signed: income positive, cost negative
    category: str | None = None
    # Which object produced it, where one did. Carried so a FIRE calculation can
    # exclude a leasehold's income without excluding rent as a whole.
    property_id: str | None = None
    starts: date | None = None
    ends: date | None = None
    every_months: int = 1
    #: Jaehrliche Steigerung, als Anteil. Null heisst flach.
    #:
    #: Ueber zwoelf Monate ist eine flache Fortschreibung vertretbar. Ueber
    #: sechzig nicht: die Stromrechnung von 2031 ist nicht die von heute, und
    #: eine Prognose, die das behauptet, sieht in Monat 50 praezise aus und
    #: liegt systematisch zu niedrig.
    escalation_pa: float = 0.0
    #: Die Mitte des Messfensters als Jahreszahl (`wachstum`): von hier an steigt der
    #: Betrag, je Monat. Pflicht, sobald es eine Steigerung gibt.
    mitte: float | None = None
    #: Der Monat, ab dem gerechnet statt gemessen wird. Nur zur Anzeige --
    #: `/konten` markiert damit, wo die Zahlen aufhoeren, aus Auszuegen zu
    #: stammen.
    measured_until: date | None = None
    #: Woher der Betrag kommt, derselbe Rechenweg-Typ wie in der Hochrechnung.
    herkunft: Posten | None = None

    def amount_in(self, month: date) -> int:
        """Der Betrag in diesem Monat, mit der Steigerung seit der Mitte des Messfensters.

        Stetig, je Monat, mit derselben Rechnung wie die Jahresrechnung
        (`wachstum.fortschreiben`): gemessen ist der Betrag zur Mitte des Fensters,
        und der Monat steht dort, wo seine Mitte liegt.
        """
        if not self.escalation_pa:
            return self.amount_cents
        if self.mitte is None:
            raise ValueError(f"{self.label}: eine Steigerung braucht die Mitte des Fensters")
        return wachstum.fortschreiben(self.amount_cents, self.mitte,
                                      wachstum.monatsmitte(month), self.escalation_pa)

    def due_in(self, month: date) -> bool:
        if self.starts and month < self.starts.replace(day=1):
            return False
        if self.ends and month > self.ends.replace(day=1):
            return False
        if self.every_months == 1:
            return True
        anchor = (self.starts or month).replace(day=1)
        delta = (month.year - anchor.year) * 12 + (month.month - anchor.month)
        return delta >= 0 and delta % self.every_months == 0


@dataclass(frozen=True, slots=True)
class Untergrenze:
    """Die Gehaltsuntergrenze als Override: ein fester Monatswert, der zum 1. Januar steigt.

    Dieselbe Regel wie die Jahresrechnung (`assumptions.gehalt_im_jahr`). Ein Override aus
    `forecast.yaml` bleibt eine gesetzte Zahl; nur die Untergrenze aus den Annahmen waechst.
    """

    cents: int
    base_year: int
    rate: float

    def in_month(self, month: date) -> int:
        from finctl import assumptions as _ann

        return _ann.gehalt_im_jahr(self.cents, month.year, self.base_year, self.rate)


def override_in(overrides: Mapping[str, int | Untergrenze], label: str,
                month: date) -> int | None:
    """Der Override dieses Postens in diesem Monat; None, wenn er keinen hat."""
    wert = overrides.get(label)
    return wert.in_month(month) if isinstance(wert, Untergrenze) else wert


def planned_amount_cents(item: dict) -> int:
    """The euro amount of a planned item, converting where it is not in euro.

    A foreign purchase is contracted in its own currency. Writing a euro
    estimate into planned.yaml hides that: the figure sitting there was
    60.000 against an obligation of 900.000.000 in the foreign currency, which
    implies 15.000 per euro -- a rate that does not exist. It was an
    independent guess dressed as an amount.

    Recording the foreign amount and the rate separately keeps the exposure
    visible and makes re-pricing one number rather than arithmetic done by
    hand. At 18.000 the same obligation is 50.000, at 20.000 it is 45.000 --
    a 5.000 swing on a single payment, in a plan whose headroom in that month
    may well be smaller than that.
    """
    if item.get("amount_foreign") is not None:
        rate = item.get("fx_rate")
        if not rate:
            raise ValueError(
                f"planned item {item.get('label')!r} is in "
                f"{item.get('currency', '?')} but declares no fx_rate")
        return int(round(float(item["amount_foreign"]) / float(rate) * 100))
    return int(item["amount_cents"])


def funding_legs(item: dict) -> list[dict]:
    """The internal transfer that pays for a planned item.

    A large payment is booked against the account it leaves from, but the money
    is not sitting there -- it gets moved over from savings a few days earlier.
    Modelling only the outflow makes the paying account's forecast permanently
    alarming: the giro account projected to -60.000 for the instalments of a
    purchase, which is not what will happen and is exactly the warning that
    teaches you to ignore warnings.

    Declared once on the payment, as `funded_from` and `funded_on`, so the
    amount cannot drift between the payment and the transfer that covers it.
    Returns both legs -- out of savings, into the paying account -- and nothing
    at all when no funding is declared.

    Household-level forecasts must NOT expand these: a transfer between your
    own accounts nets to zero there, and adding both legs would only add noise.
    """
    funding = item.get("funding") or []
    if not funding:
        return []

    default_when = str(item.get("date") or item.get("month") or "")
    label = f"Deckung: {item.get('label', 'geplante Zahlung')}"
    legs: list[dict] = []
    for part in funding:
        # `when`, deliberately not `on`: YAML 1.1 reads a bare `on` as the
        # boolean True, so `on: 2026-10-07` produces the key True and the date
        # is silently unreachable. That cost an afternoon -- every transfer
        # quietly fell back to the payment date and the trough stayed wrong.
        when = str(part.get("when") or default_when)
        amount = abs(int(part["amount_cents"]))
        if not when or not amount:
            continue
        legs.append({"account": part["from"], "when": when,
                     "amount_cents": -amount, "label": label})
        legs.append({"account": item.get("account"), "when": when,
                     "amount_cents": amount, "label": label})
    return legs


@dataclass(slots=True)
class OneOff:
    """A dated obligation or receipt the forecast cannot infer.

    `day` places it inside the month so the trough reflects real sequence. A
    65.000 payment on the 15th funded by a transfer on the 1st never dips; the
    same two amounts with no days look like a 65.000 hole.

    `reduces_cost` ist fuer den einen Fall, in dem das Vorzeichen die falsche
    Auskunft gibt: ein WEGFALL ist positiv, weil Geld aufhoert zu fliessen --
    aber er ist keine Einnahme, sondern eine negative Ausgabe. Nach Vorzeichen
    einsortiert landete er bei den Einnahmen, und die kommen per Konvention
    NACH den Kosten. Der Monatstiefpunkt blieb dadurch unveraendert, obwohl
    genau er sich verbessert: faellt der Sprit weg, wird er trotzdem noch als
    bezahlt dargestellt. Das ist die Zahl, fuer die die Trough-Mechanik
    ueberhaupt existiert.
    """

    label: str
    account_id: str
    month: date
    amount_cents: int
    day: int | None = None          # None -> sequenced pessimistically
    #: Positiv, aber eine Kostenminderung -- siehe Klassendoku.
    reduces_cost: bool = False
    #: Die Kategorie der Planzeile. Laeuft ein undatierter Posten gegen eine
    #: fortgeschriebene Position derselben Kategorie, steht er neben ihr --
    #: siehe `_korrektur_tage`.
    category: str | None = None
    #: Woher der Betrag kommt, wie bei RecurringItem.
    herkunft: Posten | None = None


@dataclass(slots=True)
class MonthRow:
    month: date
    opening_cents: int             # vor Gehalt
    costs_cents: int               # negative
    trough_cents: int              # nach Kosten
    income_cents: int              # positive
    closing_cents: int             # nach Gehalt
    breaches_dispo: bool
    # Was über dem Deckel lag und deshalb abgeräumt wird. Der Deckel ist kein
    # Zustand, den man beobachtet, sondern ein Auftrag: alles darüber gehört
    # aufs Tagesgeld, wo es Zinsen bringt.
    swept_cents: int = 0
    detail: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class Projection:
    account_id: str
    dispo_threshold_cents: int
    rows: list[MonthRow] = field(default_factory=list)

    @property
    def worst(self) -> MonthRow | None:
        return min(self.rows, key=lambda r: r.trough_cents) if self.rows else None

    @property
    def breaches(self) -> list[MonthRow]:
        return [r for r in self.rows if r.breaches_dispo]


def derive_recurring(
    conn: sqlite3.Connection,
    account_id: str,
    *,
    since: str = "2026-01-01",
    exclude: set[str] | None = None,
    include_transfers: bool = False,
    deckung: Mapping[str, str] | None = None,
    escalation_pa: float | None = None,
    ends: dict[str, date] | None = None,
    ohne: list[dict] | None = None,
    until: str | None = None,
    fenster_monate: int | None = None,
    reihen: Reihen | None = None,
) -> list[RecurringItem]:
    """Build a recurring baseline from what actually happened.

    Die Monatsrate ist die Summe des Fensters durch seine Monate, wie in der
    Hochrechnung. `fenster_monate` sind die Monate des Haushaltsfensters; fehlen sie,
    zaehlen die Kalendermonate von `since` bis `until` (ohne `until`: bis zur letzten
    Buchung des Kontos). Die Kontoprognose nennt sie selbst (`konten.kontoprognose`).

    Abgeleitete Positionen bekommen eine STEIGERUNG und, wo eines bekannt ist,
    ein ENDE. Beides ist ueber zwoelf Monate entbehrlich und ueber sechzig
    nicht: ein flach fortgeschriebener Median zeigt ab Monat 13 etwas, das
    plausibel aussieht und nicht stimmt -- ein Handyvertrag, der 2028
    auslaeuft, bucht sonst bis 2031 weiter, und die Stromrechnung von 2031 ist
    die von heute.

    Vertraglich bekannte Positionen sind davon nicht betroffen: Kreditplaene
    und Szenariozeilen tragen ihre Enddaten ohnehin.

    `include_transfers` is the difference between the two questions this gets
    asked. At HOUSEHOLD level a transfer is not income and not a cost -- a euro
    moved from the giro account to savings appears on both sides and counting it would
    inflate income and spending equally. At ACCOUNT level the same euro is
    entirely real: an account that receives 100 every month and spends about
    70 projected deep into the red within months once the inflow was dropped, on an account that is
    in fact stable. That is the budget model the owner ran in the spreadsheet
    -- a fixed allocation in, observed spending out -- and it only works if the
    allocation is allowed to count.

    Monate ohne Buchung zaehlen als null, Kosten wie Einnahmen. Ein Median aus den
    Monaten MIT Buchung liess Kleidung, Geschenke und Events ganz fallen und zeigte
    die Konsumprognose im Treffer-Check Monat fuer Monat um rund 1.000 zu niedrig.

    `reihen` sind die Reihen DIESES Kontos (`Reihen.fuer_konto`): Eine Reihe mit
    festem Takt wird ein eigener Posten mit ihrem Betrag je Termin und ihrem
    Termin, und ihre Buchungen zaehlen nicht im Rest ihrer Kategorie. Das ersetzt
    das lange Fenster der Fixkosten: Eine Jahrespraemie aus dem Januar ist eine
    Reihe, die im naechsten Januar wiederkommt, auch wenn sie im September
    ausserhalb des kurzen Fensters liegt. Ohne `reihen` rechnet alles im Rest.

    `until` schneidet das Fenster hinten ab (einschliesslich). Der
    Treffer-Check rechnet damit eine Prognose nach, wie sie am Monatsende
    davor ausgesehen haette -- ohne eine Buchung aus dem Monat, den sie
    vorhersagen soll.
    """
    # EIN DURCHLAUFENDES KONTO HAELT KEIN GELD, es reicht im selben Moment weiter.
    #
    # Seine Buchungen sind Ausgaben und Einnahmen des Kontos, das es deckt: Sie zaehlen
    # dort, mit Fenster, Verfahren und Steigerung wie jeder andere Posten (`deckung`).
    # Die Umbuchung, die das durchlaufende Konto ausgleicht, ist eine Umbuchung wie jede
    # andere und zaehlt nicht noch einmal -- sonst zahlte das deckende Konto die Ausgabe
    # und ihre Deckung zugleich.
    #
    # WAS ERKLAERT IST, WIRD NICHT GEMESSEN. Ein Posten, dessen Termin in
    # `config/abos.yaml` steht, ersetzt seine Spur im Ledger, statt neben ihr
    # zu stehen -- sonst zaehlt derselbe Betrag zweimal. Genau diese Buchungen
    # und keine anderen: bei einem Haendler stehen Einkauf und Abo unter
    # demselben Namen, und nur die zugeordnete Buchung gehoert zum Abo.
    from finctl.forecast.konten import vorschau_konto

    if fenster_monate is None:
        bis = until or conn.execute(
            "SELECT MAX(booking_date) FROM transactions WHERE account_id = ?",
            (account_id,)).fetchone()[0]
        von = date.fromisoformat(since)
        bis = date.fromisoformat(bis) if bis else None
        fenster_monate = (max(0, (bis.year - von.year) * 12 + bis.month - von.month + 1)
                          if bis else 0)
    vorschau = vorschau_konto(
        since=since, until=until, fenster_monate=fenster_monate, exclude=exclude,
        include_transfers=include_transfers, deckung=deckung,
        escalation_pa=escalation_pa, ends=ends, ohne=ohne, reihen=reihen)
    return recurring_items(conn, account_id, vorschau)


def recurring_items(conn: sqlite3.Connection, account_id: str,
                    vorschau: fortschreibung.Vorschau) -> list[RecurringItem]:
    """Die Fortschreibung eines Kontos als Posten der Kontoprognose."""
    mitte = wachstum.fenstermitte(date.fromisoformat(vorschau.since),
                                  vorschau.fenster_monate or 0)
    return [RecurringItem(
        label=p.kategorie, account_id=account_id, amount_cents=p.ergebnis.cents,
        category=p.kategorie, escalation_pa=vorschau.steigerung, mitte=mitte,
        ends=p.ende, measured_until=p.gemessen_bis, herkunft=p.ergebnis.herkunft,
        starts=p.ergebnis.starts, every_months=p.ergebnis.every_months)
        for p in fortschreibung.fortschreibung(
            conn, vorschau, konten=frozenset({account_id}))]


def _korrektur_tage(recurring: list[RecurringItem]) -> dict[tuple[str, bool], int]:
    """Wo eine undatierte Korrektur im Monat steht: neben der Position, die sie korrigiert.

    Schluessel ist (Kategorie, Korrektur positiv?). Eine Planzeile mit
    entgegengesetztem Vorzeichen in derselben Kategorie nimmt einen Teil der
    fortgeschriebenen Position zurueck. Nach Vorzeichen einsortiert stand sie
    am falschen Ende des Monats: "keine Zinsen" (negativ) am 1., die Zinsen
    selbst am 28. Am Monatsende hoben sich beide auf, aber der Tiefpunkt sah
    die Korrektur ohne das, was sie aufhebt, und lag Monat fuer Monat um
    ihren Betrag zu tief.

    Gleiches Vorzeichen ist keine Korrektur, sondern mehr vom Selben, und
    bleibt bei der pessimistischen Reihenfolge.
    """
    tage: dict[tuple[str, bool], int] = {}
    for item in recurring:
        if item.category and item.amount_cents:
            kosten = item.amount_cents < 0
            tage[(item.category, kosten)] = (UNDATED_COST_DAY if kosten
                                             else UNDATED_INCOME_DAY)
    return tage


def _platz(event: OneOff, korrektur_tage: dict[tuple[str, bool], int]) -> tuple[int, bool]:
    """Tag im Monat und ob der Posten vor den Kosten dieses Tages steht."""
    positiv = event.amount_cents > 0
    if event.day is not None:
        # EIN DATIERTER EINGANG STEHT VOR DEN KOSTEN SEINES TAGES.
        # Die Auffuellung am 1. existiert, damit die Kosten vom 1.
        # gedeckt sind. Nach ihnen einsortiert, bildete sich der
        # Tiefpunkt vor dem Geld: ein Konto fiel trotz Auffuellung
        # ins Minus, und die Warnung blieb stehen, obwohl die Regel sie
        # beheben sollte. Undatierte Eingaenge bleiben am 28.
        return event.day, positiv
    gegen = korrektur_tage.get((getattr(event, "category", None), positiv))
    if gegen is not None:
        # Eine Korrektur steht neben dem, was sie korrigiert. Die Minderung
        # einer Ausgabe kommt vor ihr, die Minderung einer Einnahme nach ihr
        # -- die Einnahme wurde frueher eingereiht.
        return gegen, positiv
    kosten = event.amount_cents < 0 or getattr(event, "reduces_cost", False)
    return (UNDATED_COST_DAY if kosten else UNDATED_INCOME_DAY), False


def _zins_und_steuer(stand: int, month: date, satz: Callable[[date], float] | None,
                     steuer: Mapping[date, int] | None) -> list[tuple[int, int, str]]:
    """(Tag, Betrag, Etikett) von Zins und Steuer dieses Monats: beide am Monatsende,
    der Zins auf dem Stand zu Monatsbeginn."""
    zins = zinsen.zins_im_monat(stand, satz(month)) if satz is not None else 0
    abgabe = (steuer or {}).get(month, 0)
    return ([(UNDATED_INCOME_DAY, zins, zinsen.ZINSEN)] if zins else []) + (
        [(UNDATED_INCOME_DAY, -abgabe, zinsen.KAPITALERTRAGSTEUER)] if abgabe else [])


def _raten(schedules: list[Schedule], month: date) -> list[tuple[int, int, str]]:
    """(Tag, Betrag, Etikett) der Kreditraten, die in diesem Monat faellig sind."""
    return [(payment.month.day, -payment.payment_cents, f"loan:{schedule.loan_id}")
            for schedule in schedules for payment in schedule.payments
            if (payment.month.year, payment.month.month) == (month.year, month.month)]


def project(
    *,
    account_id: str,
    opening_cents: int,
    start: date,
    months: int,
    recurring: list[RecurringItem],
    one_offs: list[OneOff] | None = None,
    loan_schedules: list[Schedule] | None = None,
    dispo_threshold_cents: int = 0,
    income_overrides: dict[str, int | Untergrenze] | None = None,
    sweep_above_cents: int | None = None,
    satz: Callable[[date], float] | None = None,
    steuer: Mapping[date, int] | None = None,
) -> Projection:
    """Project forward, splitting each month into costs then income.

    `satz` verzinst das Konto: der Zins eines Monats ist sein Stand zu Monatsbeginn
    mal der Satz dieses Monats durch zwoelf (`zinsen.zins_im_monat`), gebucht am Ende
    des Monats. Leert eine Klammer das Konto, sinkt der Zins von selbst. `steuer` ist
    die Steuer auf diese Zinsen je Monatserster, in Cent und positiv (`zinsen.steuerplan`:
    der Freibetrag gilt fuer den Haushalt, nicht fuer ein Konto, also kommt der Plan
    von aussen); sie faellt zusammen mit dem Zins.

    `sweep_above_cents` models the operating account actually being emptied
    down to its ceiling each month. Without it the projection shows 40.000
    piling up on an account that pays no interest -- a number that is only
    true if you decide not to act on it, and the whole point of the ceiling
    is that you do.
    """
    projection = Projection(account_id=account_id,
                            dispo_threshold_cents=dispo_threshold_cents)
    balance = opening_cents
    events = one_offs or []
    overrides = income_overrides or {}
    korrektur_tage = _korrektur_tage(recurring)

    for offset in range(months):
        month = add_months(start.replace(day=1), offset)
        detail: dict[str, int] = {}
        # (Tag, Rang innerhalb des Tages, Betrag). Der Rang existiert fuer
        # genau einen Fall: ein WEGFALL ist die Abwesenheit einer Zahlung,
        # nicht eine spaeter eintreffende Gutschrift. Er muss deshalb VOR den
        # Kosten desselben Tages stehen, sonst wird der Tiefpunkt gebildet,
        # bevor die Entlastung ankommt -- und faellt der Sprit weg, zeigt die
        # Prognose den Tiefpunkt weiter so, als wuerde er bezahlt.
        sequence: list[tuple[int, int, int]] = []
        costs = income = 0

        def add(day: int, amount: int, label: str,
                cost_side: bool = False, zuerst: bool = False,
                # An den Monat gebunden, in dem die Funktion entsteht.
                detail: dict = detail, sequence: list = sequence) -> None:
            nonlocal costs, income
            detail[label] = detail.get(label, 0) + amount
            sequence.append((day, 0 if cost_side or zuerst else 1, amount))
            # `cost_side` gewinnt ueber das Vorzeichen: ein Wegfall ist positiv
            # und gehoert trotzdem zu den Kosten, sonst verbessert er den
            # Monatstiefpunkt nicht.
            if amount < 0 or cost_side:
                costs += amount
            else:
                income += amount

        for item in recurring:
            if not item.due_in(month):
                continue
            # Ein Override ist eine gesetzte Zahl und wird NICHT gesteigert:
            # wer in forecast.yaml 4.500 setzt, meint 4.500. Nur die Untergrenze
            # aus den Annahmen steigt, zum 1. Januar, wie in der Jahresrechnung.
            amount = override_in(overrides, item.label, month)
            if amount is None:
                amount = item.amount_in(month)
            add(UNDATED_COST_DAY if amount < 0 else UNDATED_INCOME_DAY,
                amount, item.label)

        for day, amount, label in (*_zins_und_steuer(balance, month, satz, steuer),
                                   *_raten(loan_schedules or [], month)):
            add(day, amount, label)

        for event in events:
            if event.account_id != account_id:
                continue
            if event.month.year == month.year and event.month.month == month.month:
                day, zuerst = _platz(event, korrektur_tage)
                add(day, event.amount_cents, event.label,
                    cost_side=getattr(event, "reduces_cost", False),
                    zuerst=zuerst)

        # The trough is the running minimum through the month in date order --
        # not simply "balance after every cost". Ordering is what distinguishes
        # a funded payment from an overdraft.
        running = balance
        trough = balance
        for _, _, amount in sorted(sequence, key=lambda t: (t[0], t[1])):
            running += amount
            trough = min(trough, running)
        closing = running
        swept = 0
        if sweep_above_cents is not None and closing > sweep_above_cents:
            swept = closing - sweep_above_cents
            closing = sweep_above_cents
        projection.rows.append(
            MonthRow(
                month=month,
                opening_cents=balance,
                costs_cents=costs,
                trough_cents=trough,
                income_cents=income,
                closing_cents=closing,
                breaches_dispo=trough < dispo_threshold_cents,
                swept_cents=swept,
                detail=detail,
            )
        )
        balance = closing

    return projection
