"""Progress against the declared goals.

A goal is only useful if the same number can be recomputed next month without
remembering how it was built. So each goal names its target, its date and which
holdings count towards it, and the progress is derived rather than typed in.

Two rules that decide whether the bar tells the truth:

* An obligation is subtracted, never counted. Money held for someone else
  often sits in the same account as the owner's own buffer, and counting it
  makes the portfolio look larger than it is.

* A target with a date is compared against a CURRENT balance, so the bar
  measures what is saved, not what it will have grown into. Projecting the
  balance forward would show 60% for a portfolio that is barely started, which
  is exactly the reassurance a progress bar should not give.

* Every goal counts the SAME liquid assets. Letting each goal name its own
  list produced two Barista FIRE style targets measured against different
  pots, which made them incomparable for no reason -- and one of the lists
  quietly named kinds that no longer existed, so it counted nothing at all.
  There is one question here, "what is available today", and one answer.

The bar and the gap assume no return: the gap to a target is the target minus
what exists today. The monthly rate is computed twice, side by side. The first,
`Progress.monthly_needed_cents`, is that gap divided by the months left, with
no return -- being told to save less than necessary is the expensive direction
to be wrong in, so it stays first and unchanged. The second,
`rate_mit_rendite`, lets what exists and what is saved grow at the rates of the
Hochrechnung and names them. It is a forecast and is shown as one: it never
replaces the first, and neither the bar nor the gap move because of it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from finctl.forecast import notgroschen as _ng
from finctl.forecast import zinsen
from finctl.forecast.herkunft import eur, eur_genau, prozent
from finctl.forecast.policen import Police, monatssatz

# Everything the owner counts as their own free capital, by their decision:
# accounts, savings, depots, crypto and the private pension policies.
#
# The policies come with a caveat worth keeping visible rather than acting on
# unilaterally: one cannot be drawn before a given age and the other not before
# its maturity date, so a target dated earlier cannot actually be met with
# them. Counting them answers "what have I built", which is the question being
# asked here; the phase model in lebensplan.yaml answers "what can I spend
# when", and that one keeps them apart.
LIQUID_KINDS = ("giro", "tagesgeld", "depot", "krypto", "rentenversicherung")

#: Arten, die nur anders heissen. Krypto ist ein Depot wie jedes andere: es
#: waechst mit dem Depotsatz, liegt im Depot-Topf und wird im selben Abschnitt
#: gepflegt. Eine eigene Art davon machte aus einer Frage zwei Haken, und ein
#: Ziel, das "alle Depots" meinte, liess die Coins still draussen.
GLEICHE_ART = {"krypto": "depot"}


def art(kind: str | None) -> str:
    """Die Bestandsart, unter der eine Position zaehlt und gezeigt wird."""
    k = (kind or "").strip().lower()
    return GLEICHE_ART.get(k, k)


def _as_due(value) -> date | None:
    """A date from YAML, which may arrive parsed or as a string.

    goals.yaml is read by the YAML loader and yields date objects; the
    dashboard may write ISO strings. Accepting only the former is why a
    date typed into the page vanished the moment it was saved.
    """
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


@dataclass(slots=True)
class Progress:
    goal_id: str
    name: str
    target_cents: int
    have_cents: int
    due: date | None = None
    # A future payment that is already committed to this goal -- an endowment
    # maturing, a refund due. Held SEPARATE from have_cents on purpose: it is
    # not saved yet, and folding it in would let the bar show a goal as met
    # years before any money exists. It answers a different question, namely
    # whether the goal still needs a saving plan at all.
    covered_cents: int = 0
    #: Gegen welche Bestandsarten gemessen wird. None heisst: gegen alles
    #: Liquide, wie bisher.
    basis: tuple[str, ...] | None = None
    basis_text: str = "liquidem Vermögen"
    #: Positionen in dieser Basis, die gar keinen Wert tragen. Sie werden
    #: uebersprungen statt als null gezaehlt -- aber bei einer verengten
    #: Basis faellt eine von fuenf ins Gewicht, und ein Balken, der sie
    #: verschweigt, sieht praezise aus und ist es nicht.
    ohne_wert: tuple[str, ...] = ()
    #: Der Notgroschen, der von diesem Ziel abgeht -- schon aus have_cents heraus.
    abzug_cents: int = 0
    #: Es gibt ein Tagesgeld-Ziel, und dieses Ziel ist ein anderes: Die Kaskade
    #: schiebt, was im Tagesgeld darueber liegt, jedes Jahr ins Depot.
    mit_puffer: bool = False

    @property
    def pct(self) -> float:
        if self.target_cents <= 0:
            return 100.0
        return min(100.0, 100.0 * self.have_cents / self.target_cents)

    @property
    def uncovered_cents(self) -> int:
        """What neither saved nor promised money covers."""
        return max(0, self.target_cents - self.have_cents - self.covered_cents)

    def months_left(self, today: date) -> int | None:
        if self.due is None:
            return None
        return max(0, (self.due.year - today.year) * 12
                   + (self.due.month - today.month))

    def monthly_needed_cents(self, today: date) -> int | None:
        """What has to be put aside every month to close the gap in time.

        Straight division, no compounding, no return: the rate WITHOUT
        Rendite. A rate computed against an assumed return is smaller than the
        cautious one, and being told to save less than necessary is the
        expensive direction to be wrong in. The rate WITH Rendite is
        `rate_mit_rendite`; it stands beside this one and says which rates it
        assumed.

        Returns None for a goal with no date: "per month until never" has no
        answer.
        """
        months = self.months_left(today)
        if months is None:
            return None
        return self.uncovered_cents if months == 0 else \
            int(round(self.uncovered_cents / months))


def liquid_cents(balances: dict, kinds: tuple[str, ...] | None = None) -> int:
    """Was heute da ist, abzueglich dessen, was schon jemandem gehoert.

    A holding with no stated value is skipped rather than counted as zero:
    staked ETH is worth something, and showing it as nothing would look like a
    measurement instead of a gap in the data.

    `kinds` verengt die Basis auf einzelne Bestandsarten -- "alle Depots"
    statt "alles Liquide". Verbindlichkeiten werden dann NICHT abgezogen. Beim
    Notgroschen gehoert der fremde Anteil am Tagesgeld nach Entscheidung des
    Eigentuemers ausdruecklich dazu, und von einem Depotziel abgezogen hiesse
    es, dasselbe Geld zweimal zu verplanen.
    """
    verengt = kinds is not None
    erlaubt = tuple(k.lower() for k in (kinds or LIQUID_KINDS))
    total = 0
    for row in balances.get("balances") or []:
        if row.get("cents") is None:
            continue
        if _passt(row, erlaubt):
            total += int(row["cents"])
    if verengt:
        return max(0, total)
    owed = sum(int(o["cents"]) for o in (balances.get("obligations") or [])
               if o.get("cents") is not None)
    return max(0, total - owed)


def _passt(row: dict, erlaubt: tuple[str, ...]) -> bool:
    """Zaehlt diese Position zur Basis?

    Eine Basis nennt entweder eine ART ("alle Depots") oder eine einzelne
    POSITION (die Kennung eines Kontos). Beides in einer Liste, weil beides gemeint sein
    kann und man in Konten denkt, nicht in Kategorien: ein Notgroschen ist
    oft "diese vier Konten" und nicht "alles Tagesgeld".
    """
    erlaubt = tuple(art(k) for k in erlaubt)
    return (art(row.get("kind")) in erlaubt
            or str(row.get("account_id") or "").lower() in erlaubt
            or str(row.get("name") or "").lower() in erlaubt)


#: In welchen Topf der Jahresrechnung eine Bestandsart faellt.
TOPF = {"tagesgeld": "tagesgeld", "giro": "tagesgeld", "depot": "depot",
        "krypto": "depot", "rentenversicherung": "policen"}


def toepfe(balances: dict) -> dict[str, int]:
    """Das liquide Vermoegen, aufgeteilt so, wie die Jahresrechnung es fuehrt.

    Das Tagesgeld so, wie es auf den Konten liegt -- samt dem Anteil, der
    jemand anderem gehoert. Er gehoert zum Notgroschen, und ueber ihn geht er
    bei jedem Ziel ab, das ihn nicht mitzaehlt. Ihn hier zusaetzlich
    abzuziehen hiesse, ihn zweimal abzuziehen.
    """
    out = {"tagesgeld": 0, "depot": 0, "policen": 0}
    for row in balances.get("balances") or []:
        topf = TOPF.get((row.get("kind") or "").lower())
        if topf and row.get("cents") is not None:
            out[topf] += int(row["cents"])
    return out


def depot_gewinn(balances: dict) -> int:
    """Der Gewinn, der heute im Depot-Topf steckt -- soweit im Monatsabschluss
    angegeben ("davon Gewinn"). Die Hochrechnung versteuert ihn beim Verkauf."""
    return sum(int(row["gewinn_cents"]) for row in balances.get("balances") or []
               if TOPF.get((row.get("kind") or "").lower()) == "depot"
               and row.get("cents") is not None and row.get("gewinn_cents") is not None)


def policen_je_konto(balances: dict) -> dict[str, int]:
    """Der Topf `policen`, je Police -- damit eine Auszahlung genau ihren
    Anteil aus dem Topf nimmt."""
    return {str(row.get("account_id")): int(row["cents"])
            for row in balances.get("balances") or []
            if (row.get("kind") or "").lower() == "rentenversicherung"
            and row.get("account_id") and row.get("cents") is not None}


def tagesgeld_je_konto(balances: dict) -> dict[str, zinsen.Konto]:
    """Der Topf `tagesgeld`, je Konto mit seiner Bestandsart -- damit die
    Hochrechnung jedem Konto seinen Zinssatz geben kann und den Topf mit dem
    Satz verzinst, der aus seinen Konten folgt.

    Bei einem Konto ohne Kennung steht der Name. Ein Stand, den niemand
    getippt hat, fehlt wie in `toepfe`.
    """
    out = {}
    for row in balances.get("balances") or []:
        art = (row.get("kind") or "").lower()
        schluessel = str(row.get("account_id") or row.get("name") or "")
        if TOPF.get(art) == "tagesgeld" and schluessel and row.get("cents") is not None:
            out[schluessel] = zinsen.Konto(art, int(row["cents"]))
    return out


@dataclass(frozen=True, slots=True)
class Hochgerechnet:
    """Der Wert eines Ziels an seinem Stichdatum, aus einer Hochrechnung."""

    cents: int
    #: Das Jahr der Zeile, zu der der Wert gehoert: das Stichjahr, begrenzt auf
    #: den Horizont der Rechnung.
    jahr: int
    #: Prozent vom Zielbetrag.
    pct: float


def hochgerechnet(lauf, prog: Progress) -> Hochgerechnet | None:
    """Der Wert, den `lauf` einem Ziel an seinem Stichdatum gibt -- oder None.

    Jedes Ziel wird auf SEINEN Stichtag hochgerechnet, nicht auf das Ende der
    Projektion. Ein Ziel ohne Stichtag bekommt gar keine Hochrechnung: der
    Tagesgeld-Puffer gegen das Kapital von 2045 gemessen stuende bei ueber
    3.000 %, und das beantwortet keine Frage, die jemand gestellt hat. Ohne
    Zielbetrag gibt es keine Prozent.

    Ein Ziel gegen EINEN Topf bekommt die Hochrechnung dieses Topfs: die
    Jahresrechnung fuehrt Tagesgeld, Depot und Policen getrennt. Eine Basis quer
    dazu -- einzelne Konten, ein halber Topf -- bekommt keine, statt Tagesgeld
    als Depotfortschritt auszuweisen.

    Der Notgroschen ist Grundstock, kein Zielkapital -- auch in der
    Hochrechnung nicht. Er liegt im Tagesgeld-Topf, und nur ein Ziel, das
    diesen Topf zaehlt, gibt ihn ab. Gemessen wird zum Stichtag selbst, nicht
    zum Ende seines Jahres (`Projection.zum`).

    `lauf` ist eine `jahre.Projection`; sie hier zu importieren zoege `jahre` in
    dieses Modul.
    """
    if prog.due is None or not prog.target_cents or not lauf.years:
        return None
    toepfe_ziel = toepfe_fuer_basis(prog.basis) if prog.basis else None
    if prog.basis and toepfe_ziel is None:
        return None
    ohne_puffer = (prog.goal_id != PUFFER_ZIEL
                   and (not toepfe_ziel or "tagesgeld" in toepfe_ziel))

    def wert(zeile) -> int:
        v = (sum(getattr(zeile, f"{topf}_cents") for topf in toepfe_ziel)
             if toepfe_ziel else zeile.closing_cents)
        if ohne_puffer:
            v -= min(max(zeile.tagesgeld_cents, 0), zeile.puffer_grenze_cents)
        return v

    cents = lauf.zum(prog.due, wert)
    erstes, letztes = lauf.years[0].year, lauf.years[-1].year
    return Hochgerechnet(cents, min(max(prog.due.year, erstes), letztes),
                         100.0 * cents / prog.target_cents)


def toepfe_fuer_basis(kinds: tuple[str, ...] | None) -> tuple[str, ...] | None:
    """Welche Toepfe eine Basis abdeckt -- oder None, wenn sie quer dazu liegt.

    Hochgerechnet wird, was angehakt ist: jede Bestandsart zieht ihren Topf
    mit, und der waechst mit seinem Satz -- Depot und Policen mit dem
    Depotsatz, das Tagesgeld mit seinem. Nur eine Basis aus einzelnen Konten
    liegt quer zu den Toepfen und bleibt ohne Hochrechnung.
    """
    if not kinds or any(k not in TOPF for k in kinds):
        return None
    return tuple(sorted({TOPF[k] for k in kinds}))


#: Wie eine verengte Basis heisst, wenn die Seite sie nennt.
BASIS_LABEL = {
    "giro": "Girokonten", "tagesgeld": "Tagesgeld", "depot": "Depots",
    "krypto": "Krypto", "rentenversicherung": "Rentenversicherungen",
}


def basis_von(goal: dict) -> tuple[str, ...] | None:
    """Die Bestandsarten, gegen die ein Ziel misst -- oder None fuer alles."""
    roh = goal.get("basis")
    if not roh:
        return None
    if isinstance(roh, str):
        roh = [roh]
    return tuple(dict.fromkeys(art(k) for k in roh if str(k).strip()))


def basis_text(kinds: tuple[str, ...] | None,
               balances: dict | None = None) -> str:
    if not kinds:
        return "liquidem Vermögen"
    namen = {}
    for r in ((balances or {}).get("balances") or []):
        for schluessel in (r.get("account_id"), r.get("name")):
            if schluessel:
                namen[str(schluessel).lower()] = r.get("name") or str(schluessel)
    return " + ".join(BASIS_LABEL.get(k) or namen.get(k) or k for k in kinds)


# ------------------------------------------------------ die Rate mit Rendite

#: In welcher Reihenfolge ein Abzug die Bestandsarten leert: das Tagesgeld
#: zuerst, dann das Giro -- so nimmt `progress` den Notgroschen aus dem Topf
#: Tagesgeld --, danach Depot und Policen.
ABZUG_REIHE = ("tagesgeld", "giro", "depot", "rentenversicherung")


@dataclass(frozen=True, slots=True)
class Bestandsteil:
    """Was ein Ziel von einer Bestandsart zaehlt, so wie die Karte es zaehlt.

    Eine Police steht einzeln, mit der Kennung ihres Kontos, weil jede ihren
    eigenen Satz nach Kosten hat. Alles andere steht je Art, `kennung` leer.
    """

    art: str
    kennung: str
    cents: int


def _abziehen(teile: dict[tuple[str, str], int], betrag: int, arten: tuple[str, ...]) -> None:
    """Nimmt `betrag` aus den positiven Teilen, Art fuer Art in der Reihenfolge."""
    for a in arten:
        for schluessel in [k for k in teile if k[0] == a]:
            nimmt = min(betrag, max(teile[schluessel], 0))
            teile[schluessel] -= nimmt
            betrag -= nimmt


def bestand_der_basis(balances: dict, prog: Progress) -> list[Bestandsteil]:
    """Der Bestand, gegen den `prog` misst, nach Bestandsart getrennt.

    Gezaehlt werden dieselben Positionen wie in `liquid_cents(balances,
    prog.basis)`, und die Summe ist `prog.have_cents`: Vom Brutto geht ab,
    was die Karte abzieht -- die Verbindlichkeiten, die `liquid_cents` ohne
    Basis abzieht, zuerst vom Tagesgeld, dann vom Giro und, reicht es dort
    nicht, vom Depot; danach der Notgroschen (`prog.abzug_cents`) aus
    Tagesgeld und Giro. Ein Abzug nimmt nur aus positiven Teilen.
    """
    erlaubt = tuple(k.lower() for k in (prog.basis or LIQUID_KINDS))
    teile: dict[tuple[str, str], int] = {}
    for row in balances.get("balances") or []:
        if row.get("cents") is None or not _passt(row, erlaubt):
            continue
        a = art(row.get("kind"))
        schluessel = (a, str(row.get("account_id") or "") if a == "rentenversicherung" else "")
        teile[schluessel] = teile.get(schluessel, 0) + int(row["cents"])
    brutto = sum(teile.values())
    if brutto <= 0:
        return []
    uebrige = tuple(sorted({a for a, _ in teile} - set(ABZUG_REIHE)))
    _abziehen(teile, brutto - (prog.have_cents + prog.abzug_cents), ABZUG_REIHE + uebrige)
    _abziehen(teile, prog.abzug_cents, ("tagesgeld", "giro"))
    return [Bestandsteil(a, kennung, cents) for (a, kennung), cents in teile.items() if cents]


@dataclass(frozen=True, slots=True)
class Saetze:
    """Die Jahressaetze, mit denen die Karte rechnet -- die der Hochrechnung."""

    tagesgeld: float
    #: Der Depotsatz nach der Last der Vorabpauschale.
    depot: float
    #: Eine Police, die die Rentenquellen nicht kennen, waechst mit dem
    #: Depotsatz vor Steuern: der Versicherungsmantel schuetzt sie.
    police: float
    #: Je Police (Kennung des Kontos) ihr Satz nach Kosten.
    policen: Mapping[str, float] = field(default_factory=dict)

    def fuer(self, teil: Bestandsteil) -> float:
        """Das Giro waechst nicht, und eine Art, die niemand kennt, auch nicht."""
        if teil.art == "tagesgeld":
            return self.tagesgeld
        if teil.art == "depot":
            return self.depot
        if teil.art == "rentenversicherung":
            return self.policen.get(teil.kennung, self.police)
        return 0.0


def saetze_aus(a, policen: Mapping[str, Police] | None = None) -> Saetze:
    """Die Saetze aus den Annahmen (`jahre.Annahmen`) und den Policen der Eingaben.

    Der Depotsatz verliert, was `jahre.kaskade` an Vorabpauschale versteuert:
    `min(vorab_satz, Depotsatz) x steuer_quote`. Den Sparerpauschbetrag
    kennt die Karte nicht; das macht sie leicht vorsichtig.
    """
    last = min(a.vorab_satz, max(a.rendite_depot, 0.0)) * a.steuer_quote
    return Saetze(
        tagesgeld=a.rendite_tagesgeld, depot=a.rendite_depot - last, police=a.rendite_depot,
        policen={konto: p.satz(a.rendite_depot) for konto, p in (policen or {}).items()})


@dataclass(frozen=True, slots=True)
class RateMitRendite:
    """Die zweite Rate neben der ohne Rendite, samt dem, woraus sie folgt."""

    #: Cent im Monat; None, wo der gewachsene Bestand das Ziel allein erreicht.
    cents: int | None
    #: Der Jahressatz, mit dem die Rate selbst waechst.
    satz: float
    #: Die Schritte, einer je Zeile: Bestand je Art, Wert zum Stichtag, Luecke, Rate.
    herleitung: tuple[str, ...]


#: Wie die Herleitung den Depotsatz nennt -- und woran `rate_mit_rendite` ihn erkennt.
DEPOTSATZ = "Depotsatz nach Vorabpauschale"


def _satz_der_rate(prog: Progress, saetze: Saetze) -> tuple[float, str] | None:
    """Mit welchem Satz die Rate waechst: dem dessen, wohin gespart wird.

    Ohne Basis oder mit Depot darin lenkt die Kaskade alles ueber dem Puffer
    ins Depot. Sonst zaehlt das Tagesgeld, wenn es in der Basis steht. Bei
    einer Basis aus Giro oder nur Policen waechst die Rate nicht in der Basis,
    und eine Basis quer zu den Toepfen hat auch keine Hochrechnung.
    """
    if prog.basis is None:
        return saetze.depot, DEPOTSATZ
    if toepfe_fuer_basis(prog.basis) is None:
        return None
    if "depot" in prog.basis:
        return saetze.depot, DEPOTSATZ
    if "tagesgeld" in prog.basis:
        return saetze.tagesgeld, "Tagesgeldsatz"
    return None


#: Die Arten, die die Kaskade ins Depot schiebt, sobald sie ueber dem Notgroschen liegen.
UMGESCHICHTET = ("tagesgeld", "giro")


def _umschichtet(prog: Progress, satz_name: str) -> bool:
    """Wandert der Rest von Tagesgeld und Giro ins Depot? Nur wo es ein
    Tagesgeld-Ziel gibt und die Rate selbst mit dem Depotsatz waechst; sonst
    bleibt er, wo er liegt."""
    return prog.mit_puffer and satz_name == DEPOTSATZ


def _wachsen(teile: list[Bestandsteil], saetze: Saetze, monate: int,
             umschichten: bool) -> dict[tuple[str, float], tuple[int, int]]:
    """Je (Art, Satz) der Bestand heute und der Bestand nach `monate`, monatlich verzinst.

    Mit `umschichten` waechst, was nach dem Notgroschen auf Tagesgeld und Giro
    liegt, mit dem Depotsatz: Die Kaskade schiebt es jedes Jahr dorthin.
    """
    heute: dict[tuple[str, float], int] = {}
    for teil in teile:
        satz = saetze.depot if umschichten and teil.art in UMGESCHICHTET else saetze.fuer(teil)
        heute[(teil.art, satz)] = heute.get((teil.art, satz), 0) + teil.cents
    reihe = {a: i for i, a in enumerate(ABZUG_REIHE)}
    return {(a, satz): (cents, round(cents * (1 + monatssatz(satz)) ** monate))
            for (a, satz), cents in sorted(
                heute.items(), key=lambda kv: (reihe.get(kv[0][0], len(reihe)), kv[0][1]))}


def _rate(luecke: int, satz: float, monate: int) -> int:
    """Die Monatsrate, die `luecke` in `monate` fuellt, am Monatsende gezahlt.

    Bei einem Satz von 0 ist das die Division der Rate ohne Rendite.
    """
    m = monatssatz(satz)
    if m == 0:
        return int(round(luecke / monate))
    return int(round(luecke * m / ((1 + m) ** monate - 1)))


def _herleitung(prog: Progress, gewachsen: dict, luecke: int, rate: int | None,
                satz: float, satz_name: str, monate: int) -> tuple[str, ...]:
    umschichten = _umschichtet(prog, satz_name)
    zeilen = [f"{BASIS_LABEL.get(a, a)}: {eur(heute)} heute, mit {prozent(s)} im Jahr "
              f"{eur(spaeter)} zum Stichtag"
              + (", weil die Kaskade, was über dem Notgroschen liegt, ins Depot schiebt"
                 if umschichten and a in UMGESCHICHTET else "")
              for (a, s), (heute, spaeter) in gewachsen.items()]
    bestand = sum(spaeter for _, spaeter in gewachsen.values())
    zugesagt = f" − {eur(prog.covered_cents)} zugesagt" if prog.covered_cents else ""
    zeilen.append(f"Lücke: {eur(prog.target_cents)} Ziel{zugesagt} − {eur(bestand)} Bestand "
                  f"zum Stichtag = {eur(max(luecke, 0))}")
    zeilen.append("Der gewachsene Bestand erreicht das Ziel allein" if rate is None else
                  f"Rate: {eur_genau(rate)} im Monat, am Monatsende gespart und mit "
                  f"{prozent(satz)} im Jahr verzinst ({satz_name}), {monate} Monate")
    return tuple(zeilen)


def rate_mit_rendite(prog: Progress, balances: dict, saetze: Saetze,
                     today: date) -> RateMitRendite | None:
    """Die Monatsrate, wenn Bestand und Rate mit den Saetzen der Hochrechnung wachsen.

    Die zweite Zahl neben `Progress.monthly_needed_cents`, die ohne Rendite
    rechnet und vorn bleibt. Monatlich gerechnet, die Rate am Monatsende:
    `(Ziel - zugesagt - Summe Bestand x (1+m)^n) x m / ((1+m)^n - 1)`, der
    Bestand je Art mit seinem Satz (`bestand_der_basis`). Bei einem Satz von 0
    ist das genau die erste Rate.

    Gibt es ein Tagesgeld-Ziel und waechst die Rate mit dem Depotsatz, waechst
    auch, was nach dem Notgroschen auf Tagesgeld und Giro liegt, mit dem
    Depotsatz: Die Kaskade der Hochrechnung schiebt es jedes Jahr ins Depot.

    Keine zweite Zahl (None), wo es keine gibt: ohne Stichtag, bei einem
    erreichten Stichtag, wenn die erste Rate schon 0 ist und wo die Rate in
    keiner Art der Basis waechst (`_satz_der_rate`). Reicht der gewachsene
    Bestand allein, ist `cents` None, und die Herleitung sagt es.
    """
    monate = prog.months_left(today)
    wachstum = _satz_der_rate(prog, saetze)
    if not monate or not prog.monthly_needed_cents(today) or wachstum is None:
        return None
    satz, satz_name = wachstum
    gewachsen = _wachsen(bestand_der_basis(balances, prog), saetze, monate,
                         _umschichtet(prog, satz_name))
    luecke = prog.target_cents - prog.covered_cents - sum(s for _, s in gewachsen.values())
    rate = _rate(luecke, satz, monate) if luecke > 0 else None
    return RateMitRendite(rate, satz, _herleitung(prog, gewachsen, luecke, rate,
                                                  satz, satz_name, monate))


def aus_spec(spec: dict) -> dict:
    """Die Ziele, wie `goals.yaml` sie sagt -- eine Datei, die die Seite ganz schreibt.

    Betrag und Herleitung sind eingetragen, nicht berechnet. Die Reihenfolge der Liste ist
    die, in der die Ziele stehen; `reihenfolge` ist die auf der Seite gezogene Anordnung und
    gilt vor ihr (`progress`). Ein Notgroschen ohne Betrag bekommt seine Vorgabe beim Lesen,
    nicht in der Datei: Wer die Untergrenze aendert, verschiebt sie mit.
    """
    out = dict(spec)
    if spec.get("reihenfolge"):
        out["reihenfolge"] = [str(x) for x in spec["reihenfolge"]]
    out["ziele"] = list(spec.get("ziele") or [])
    return _notgroschen_vorgabe(out)


#: Der Notgroschen und seine Grenze stehen in `notgroschen`: Die Prognose braucht sie fuer die
#: Untergrenze eines Kontos und darf dieses Modul nicht importieren.
NOTGROSCHEN_MONATE = _ng.NOTGROSCHEN_MONATE
PUFFER_ZIEL = _ng.PUFFER_ZIEL
_notgroschen_vorgabe = _ng.vorgabe
puffer_cents = _ng.puffer_cents


def progress(goals: dict, balances: dict, *, today: date | None = None) -> list[Progress]:
    """One row per goal that has a target, obligations already deducted."""
    today = today or date.today()

    out: list[Progress] = []
    for goal in goals.get("ziele") or []:
        if goal.get("art") == "verbindlichkeit":
            continue          # a liability is not a thing to make progress on
        # Je Ziel, nicht einmal fuer alle: ein Ziel darf gegen EINEN Topf
        # messen statt gegen das ganze Vermoegen. Zwei Balken, die
        # verschiedene Dinge messen, muessen es sagen -- deshalb kommt die
        # Basis mit zurueck und steht neben dem Balken.
        kinds = basis_von(goal)
        have = liquid_cents(balances, kinds)
        # Der Notgroschen ist Grundstock, kein Zielkapital: er zaehlt bei
        # keinem Ziel mit ausser bei seinem eigenen. Abgezogen wird er dort, wo
        # er liegt -- im Tagesgeld --, und nur so weit, wie dort etwas liegt.
        # Ein reines Depotziel gibt nichts ab.
        abzug = 0
        puffer = puffer_cents(goals)
        if puffer and goal["id"] != PUFFER_ZIEL:
            if kinds is None:
                tagesgeld = toepfe(balances)["tagesgeld"]
                # Die Verbindlichkeiten stecken im Notgroschen und gehen mit
                # ihm ab -- nicht noch einmal obendrauf.
                have = liquid_cents(balances, LIQUID_KINDS)
            else:
                eigene = tuple(k for k in kinds if TOPF.get(k) == "tagesgeld")
                tagesgeld = liquid_cents(balances, eigene) if eigene else 0
            abzug = min(puffer, max(0, tagesgeld), have)
        erlaubt = tuple(k.lower() for k in (kinds or LIQUID_KINDS))
        offen = tuple(
            (r.get("name") or r.get("account_id") or "?")
            for r in (balances.get("balances") or [])
            if r.get("cents") is None and _passt(r, erlaubt))
        out.append(Progress(
            goal_id=goal["id"], name=goal.get("name", goal["id"]),
            basis=kinds, basis_text=basis_text(kinds, balances), ohne_wert=offen,
            target_cents=int(goal.get("cents") or 0), have_cents=have - abzug,
            abzug_cents=abzug, mit_puffer=bool(puffer) and goal["id"] != PUFFER_ZIEL,
            due=_as_due(goal.get("stichtag")),
            covered_cents=sum(int(c["cents"]) for c in (goal.get("gedeckt_durch") or [])
                              if c.get("cents") is not None)))

    # Erst, was ohne Termin immer gilt -- der Tagesgeld-Puffer ist eine
    # stehende Untergrenze und kein Meilenstein --, dann chronologisch von
    # nah nach fern. Die Liste liest sich damit als Weg und nicht als
    # Aufzaehlung: was als naechstes ansteht, steht oben.
    #
    # Bei gleichem Stichtag entscheidet die Reihenfolge in goals.yaml. Zwei
    # Ziele auf denselben Tag sollen nicht bei jedem Aufruf die Plaetze
    # tauschen.
    reihe = {g["id"]: i for i, g in enumerate(goals.get("ziele") or [])}
    out.sort(key=lambda p: (p.due is not None, p.due or date.min,
                            reihe.get(p.goal_id, 0)))
    # Eine auf der Seite gezogene Reihenfolge gewinnt. Was darin fehlt -- ein
    # spaeter angelegtes Ziel --, folgt dahinter in der Reihenfolge von oben;
    # die Sortierung ist stabil.
    gezogen = {gid: i for i, gid in enumerate(goals.get("reihenfolge") or [])}
    if gezogen:
        out.sort(key=lambda p: gezogen.get(p.goal_id, len(gezogen)))
    return out
