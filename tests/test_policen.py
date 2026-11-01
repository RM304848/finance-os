"""Die Police in der Hochrechnung (Schritt P.2): Beitrag, Kosten, Auszahlung.

Eine Police waechst Monat fuer Monat mit ihrem Satz nach Kosten, und ihr Beitrag
vom Vertrag kommt dazu -- solange er als Ausgabe laeuft. Er bleibt eine Ausgabe in
seinem Block; in der Police kommt dasselbe Geld an, kein neues. Alles ist erfunden
und rund: eine Police mit 10.000 Euro, ein Beitrag von 100 oder 300 im Monat.
"""

from __future__ import annotations

import dataclasses
import hashlib
import sqlite3
from datetime import date
from pathlib import Path

import pytest
import yaml

from finctl import abos, reihen, renten
from finctl import assumptions as ann
from finctl.forecast import abgleich as ag
from finctl.forecast import jahre as jm
from finctl.forecast import policen as pol
from finctl.forecast import szenarien as sz
from finctl.ledger.db import connect, init_db
from finctl.renten import Pruefwert, Quelle

STAND = 10_000_00
BEITRAG = 100_00
STICHTAG = date(2026, 9, 30)


def _police(**kw) -> pol.Police:
    werte = {"konto": "p", "quelle": "p", "name": "Police P", "kosten_pa": 0.01,
             "beitrag": pol.Beitrag(vertrag="v", name="Vertrag V", cents=BEITRAG, takt=1,
                                    termin=date(2030, 1, 1))}
    werte.update(kw)
    return pol.Police(**werte)


def _geschlossen(stand: int, beitrag: int, satz: float, n: int) -> float:
    """Stand mal q^n plus die Beitraege am Monatsende: die Summe der geometrischen Reihe."""
    q = (1.0 + satz) ** (1 / 12)
    return stand * q ** n + beitrag * (q ** n - 1) / (q - 1)


def _ein_jahr(police: pol.Police, jahr: int, stand: int = STAND, nach: int = 0,
              depot: float = 0.07) -> tuple[int, int, int]:
    f = pol.fortschreiben({"p": stand}, {"p": police}, depot, jahr, nach)
    return f.ende["p"], f.zins["p"], f.beitrag["p"]


# ------------------------------------------------------ die Police, ohne Datenbank

def test_twelve_monthly_rates_make_the_yearly_rate():
    assert (1 + pol.monatssatz(0.06)) ** 12 == pytest.approx(1.06, abs=1e-12)
    assert pol.monatssatz(0.0) == 0.0


def test_a_police_with_a_contribution_follows_the_closed_formula():
    """Satz nach Kosten 7 % - 1 % = 6 %, Beitrag 100 im Monat, zwei volle Jahre."""
    erstes, zins, beitrag = _ein_jahr(_police(), 2030)
    assert beitrag == 12 * BEITRAG
    assert erstes == round(_geschlossen(STAND, BEITRAG, 0.06, 12))
    assert zins == erstes - STAND - beitrag
    zweites, _, _ = _ein_jahr(_police(), 2031, stand=erstes)
    assert zweites == pytest.approx(_geschlossen(STAND, BEITRAG, 0.06, 24), abs=1)


def test_without_costs_and_contribution_a_full_year_is_todays_growth():
    """Genau das, was die Kaskade bisher rechnete: Stand mal Depotsatz."""
    ohne = _police(kosten_pa=0.0, beitrag=None)
    ende, zins, beitrag = _ein_jahr(ohne, 2031, stand=50_000_00)
    assert (ende, zins, beitrag) == (53_500_00, 3_500_00, 0)


def test_the_base_year_runs_only_its_remaining_months():
    ende, _, beitrag = _ein_jahr(_police(kosten_pa=0.0, beitrag=None), 2026, nach=9)
    assert ende == round(STAND * 1.07 ** (3 / 12)) and beitrag == 0
    _, _, mit = _ein_jahr(_police(), 2026, nach=9)
    assert mit == 3 * BEITRAG


def test_two_policies_grow_each_with_its_own_costs():
    teuer, guenstig = _police(konto="a", kosten_pa=0.02), _police(konto="b", kosten_pa=0.005)
    f = pol.fortschreiben({"a": STAND, "b": STAND}, {"a": teuer, "b": guenstig}, 0.07, 2030, 0)
    assert f.ende["a"] == round(_geschlossen(STAND, BEITRAG, 0.05, 12))
    assert f.ende["b"] == round(_geschlossen(STAND, BEITRAG, 0.065, 12))
    assert f.ende["b"] > f.ende["a"]


def test_a_position_without_a_police_is_left_to_the_cascade():
    f = pol.fortschreiben({"fremd": STAND}, {}, 0.07, 2030, 0)
    assert dict(f.ende) == {} and dict(f.zins) == {} and dict(f.beitrag) == {}


def test_the_contribution_ends_the_month_before_the_payout():
    police = _police(beginn=date(2030, 6, 1))
    ende, _, beitrag = _ein_jahr(police, 2030)
    assert beitrag == 5 * BEITRAG                       # Januar bis Mai
    assert ende == round(_geschlossen(STAND, BEITRAG, 0.06, 5))
    assert police.letzter_beitragsmonat() == date(2030, 5, 1)
    # Im Jahr danach ist sie ausgezahlt: weder Wachstum noch Beitrag.
    assert _ein_jahr(police, 2031, stand=0) == (0, 0, 0)
    # Zahlt sie im Januar aus, kommt in dem Jahr nichts mehr dazu.
    januar = _police(beginn=date(2030, 1, 1))
    assert _ein_jahr(januar, 2030) == (STAND, 0, 0)


def test_a_payout_in_the_middle_of_a_month_still_takes_that_months_contribution():
    police = _police(beginn=date(2030, 6, 15))
    assert _ein_jahr(police, 2030)[2] == 6 * BEITRAG
    assert police.letzter_beitragsmonat() == date(2030, 6, 1)


def test_a_cancellation_on_the_contract_ends_the_contribution():
    gekuendigt = _police(beitrag=dataclasses.replace(_police().beitrag, ende=date(2030, 3, 31)))
    ende, _, beitrag = _ein_jahr(gekuendigt, 2030)
    assert beitrag == 3 * BEITRAG
    # Danach waechst die Police ohne ihn weiter, mit demselben Satz.
    fuenf = round(_geschlossen(STAND, BEITRAG, 0.06, 3))
    assert ende == round(fuenf * (1.06 ** (9 / 12)))


def test_a_wegfall_line_pauses_the_contribution_and_the_police_grows_on():
    pausiert = _police(beitrag=dataclasses.replace(
        _police().beitrag, pausen=((date(2030, 4, 1), date(2030, 6, 1)),)))
    _, _, beitrag = _ein_jahr(pausiert, 2030)
    assert beitrag == 9 * BEITRAG                       # April bis Juni frei
    offen = _police(beitrag=dataclasses.replace(
        _police().beitrag, pausen=((date(2030, 4, 1), None),)))
    assert _ein_jahr(offen, 2030)[2] == 3 * BEITRAG
    assert _ein_jahr(offen, 2031, stand=STAND)[2] == 0
    # Die Police wuchs im Jahr danach weiter, nur ohne Beitrag.
    assert _ein_jahr(offen, 2031, stand=STAND)[0] == round(STAND * 1.06)


def test_a_quarterly_contribution_falls_in_its_months():
    quartal = _police(beitrag=dataclasses.replace(_police().beitrag, takt=3,
                                                  termin=date(2029, 2, 15)))
    assert [m for m in range(1, 13) if quartal.beitrag.zahlt(date(2030, m, 1))] == [2, 5, 8, 11]
    assert _ein_jahr(quartal, 2030)[2] == 4 * BEITRAG


# ------------------------------------------------------------------- der Pruefwert

def test_the_check_value_is_compared_at_its_own_rate_after_costs():
    police = _police()
    pruef = Pruefwert(satz=0.06, cents=15_000_00, zum=date(2032, 1, 1))
    v = pol.vergleichen(STAND, police, pruef, date(2030, 1, 1))
    erwartet = round(_geschlossen(STAND, BEITRAG, 0.05, 24))
    assert (v.satz, v.modell_cents, v.endet) == (pytest.approx(0.05), erwartet, None)
    assert v.abweichung == pytest.approx(erwartet / 15_000_00 - 1)


def test_the_check_value_ignores_the_payout_like_the_notice_does():
    """Die Mitteilung laesst den Beitrag bis zu ihrem Datum laufen, auch wenn die Police
    vorher auszahlt: Die Spalte prueft den Satz, sie sagt nicht, was ausgezahlt wird."""
    frueh = _police(beginn=date(2030, 7, 1))
    pruef = Pruefwert(satz=0.06, cents=15_000_00, zum=date(2032, 1, 1))
    spaet = _police()
    assert (pol.vergleichen(STAND, frueh, pruef, date(2030, 1, 1)).modell_cents
            == pol.vergleichen(STAND, spaet, pruef, date(2030, 1, 1)).modell_cents)


def test_a_contribution_that_ends_earlier_is_not_comparable():
    police = _police(beitrag=dataclasses.replace(_police().beitrag, ende=date(2030, 12, 31)))
    pruef = Pruefwert(satz=0.06, cents=15_000_00, zum=date(2032, 1, 1))
    v = pol.vergleichen(STAND, police, pruef, date(2030, 1, 1))
    assert (v.modell_cents, v.abweichung, v.endet) == (None, None, date(2030, 12, 1))
    # Liegt der Pruefwert vor dem Rechenbeginn, gibt es nichts zu vergleichen.
    vorher = Pruefwert(satz=0.06, cents=15_000_00, zum=date(2029, 1, 1))
    assert pol.vergleichen(STAND, _police(), vorher, date(2030, 1, 1)).modell_cents is None


def test_a_check_value_without_a_rate_is_never_compared():
    """Die Mitteilung nennt keinen Satz: Es gibt keinen Vergleich, auch wenn alles andere
    ginge -- Beitrag laeuft, Datum liegt nach dem Rechenbeginn."""
    pruef = Pruefwert(satz=None, cents=15_000_00, zum=date(2032, 1, 1))
    v = pol.vergleichen(STAND, _police(), pruef, date(2030, 1, 1))
    assert (v.satz, v.modell_cents, v.abweichung, v.endet) == (None, None, None, None)
    # Auch ein Beitrag, der frueher endet, ist nur "ohne Satz": Es gibt nichts zu vergleichen.
    police = _police(beitrag=dataclasses.replace(_police().beitrag, ende=date(2030, 12, 31)))
    assert pol.vergleichen(STAND, police, pruef, date(2030, 1, 1)).endet is None


# ----------------------------------------------------------- mit Hauptbuch und Vertrag

def _monat(i: int) -> date:
    """Der i-te Monat ab Januar 2025."""
    index = 2025 * 12 + i
    return date(index // 12, index % 12 + 1, 1)


@dataclasses.dataclass
class Haus:
    c: sqlite3.Connection
    #: Die zwoelf Beitraege der Police im Fenster.
    kennungen: list[str]
    #: Eine Buchung einer anderen Reihe in einer anderen Kategorie.
    fremde: str


@pytest.fixture
def haus(tmp_path, monkeypatch):
    """Zweiundzwanzig Monate Hauptbuch; ein Beitrag von 300 im Monat in der Kategorie
    der Police, zwoelf Buchungen im Fenster (Oktober 2025 bis September 2026)."""
    (tmp_path / "config").mkdir()
    monkeypatch.setattr(reihen, "CONFIG_DIR", tmp_path / "config")
    c = connect(init_db(tmp_path / "t.db"))
    c.execute("INSERT INTO accounts (id, display_name, institution, account_type, "
              "ingest_mode, parser_profile) VALUES ('a','A','X','giro','parsed','p')")
    for kennung, kind, fix in (("versicherung", "expense", 0), ("versicherung/rente", "expense", 1),
                               ("versicherung/bu", "expense", 1)):
        c.execute("INSERT INTO mgmt_categories (id, parent_id, name, kind, fixkosten) "
                  "VALUES (?,?,?,?,?)",
                  (kennung, kennung.split("/")[0] if "/" in kennung else None,
                   kennung, kind, fix))
    for i in range(22):
        erster = _monat(i)
        c.execute(
            "INSERT INTO statements (id, account_id, source_path, source_name, file_sha256, "
            "period_start, period_end, balance_start_cents, balance_end_cents, "
            "parser_profile, parser_version, status, imported_at) "
            "VALUES (?, 'a','x','x',?,?,?,0,0,'p','1','imported','now')",
            (i + 1, f"sha{i}", erster.isoformat(), ag._month_end(erster).isoformat()))
    c.commit()
    kennungen = [_buche(c, _monat(i).replace(day=5), -300_00, "versicherung/rente", "police")
                 for i in range(9, 21)]
    yield Haus(c, kennungen, _buche(c, date(2026, 6, 6), -62_00, "versicherung/bu", "bu"))
    c.close()


def _buche(c, tag: date, cents: int, kategorie: str, gegenpartei: str) -> str:
    n = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] + 1
    kennung = hashlib.sha256(f"buchung{n}".encode()).hexdigest()
    sid = c.execute("SELECT id FROM statements WHERE period_start <= ? AND period_end >= ?",
                    (tag.isoformat(), tag.isoformat())).fetchone()[0]
    tid = c.execute(
        "INSERT INTO transactions (account_id, statement_id, booking_date, amount_cents, "
        "counterparty_norm, raw_text, seq_in_statement, dedup_hash, created_at) "
        "VALUES ('a',?,?,?,?,'x',?,?,'now')",
        (sid, tag.isoformat(), cents, gegenpartei, n, kennung)).lastrowid
    c.execute("INSERT INTO splits (transaction_id, amount_cents, mgmt_category_id, "
              "source, created_at, updated_at) VALUES (?,?,?,'rule','now','now')",
              (tid, cents, kategorie))
    c.commit()
    return kennung


def _vertrag(monkeypatch, kennungen: list[str], **extra) -> None:
    basis = {"id": "vertrag-x", "name": "Vertrag X", "kategorie": "versicherung/rente",
             "konto": "a", "betrag_cents": -300_00, "takt": 1, "faellig": "2026-10-05",
             "buchungen": kennungen[:1]}
    basis.update(extra)
    monkeypatch.setattr(abos, "alle_vertraege", lambda: [abos.normalisieren(basis)])


def _quelle(**kw) -> Quelle:
    werte = {"id": "police-x", "name": "Police X", "art": "kapital", "cents": 1,
             "kaufkraft": "nominal", "ab": date(2032, 3, 1), "konto": "police-x",
             "kosten_pa": 0.01, "beitrag": "vertrag-x"}
    werte.update(kw)
    return Quelle(**werte)


def _wegfall(kennungen: list[str], start: str = "2030-01-01", ende: str | None = None) -> list:
    zeile = {"label": "beitragsfrei", "art": "wegfall", "amount_cents": 0,
             "frequenz": "monatlich", "start": start, "kategorie": "versicherung/rente",
             "konto": "a", "buchungen": kennungen[:1]}
    if ende:
        zeile["ende"] = ende
    return sz.load({"szenarien": [{"id": "frei", "name": "Beitragsfrei", "aktiv": True,
                                   "zeilen": [zeile]}]})


def test_the_police_reads_its_contribution_from_the_contract(haus, monkeypatch):
    _vertrag(monkeypatch, haus.kennungen, gekuendigt_zum="2040-12-31", takt=3)
    q = _quelle()
    police = jm._policen_lesen(haus.c, (q,), {q.id: q.ab}, [])["police-x"]
    assert police.beitrag == pol.Beitrag(
        vertrag="vertrag-x", name="Vertrag X", cents=300_00, takt=3, termin=date(2026, 10, 5),
        ende=date(2040, 12, 31))
    assert (police.kosten_pa, police.kosten_bekannt, police.beginn) == (0.01, True, q.ab)
    # Ohne `beitrag` und ohne Kosten: eine Police ohne beides, mit Kosten 0.
    ohne = jm._policen_lesen(haus.c, (_quelle(beitrag=None, kosten_pa=None),),
                             {"police-x": q.ab}, [])["police-x"]
    assert (ohne.beitrag, ohne.kosten_pa, ohne.kosten_bekannt) == (None, 0.0, False)
    # Eine Rentenquelle ohne Position hat keine Police.
    assert jm._policen_lesen(haus.c, (_quelle(konto=None),), {}, []) == {}


def test_a_wegfall_line_over_the_contracts_series_pauses_its_contribution(haus,
                                                                         monkeypatch):
    _vertrag(monkeypatch, haus.kennungen)
    q = _quelle()
    mit = jm._policen_lesen(haus.c, (q,), {q.id: q.ab}, _wegfall(haus.kennungen))
    assert mit["police-x"].beitrag.pausen == ((date(2030, 1, 1), None),)
    # Eine Zeile ueber eine andere Reihe beruehrt ihn nicht.
    fremd = jm._policen_lesen(haus.c, (q,), {q.id: q.ab}, _wegfall([haus.fremde]))
    assert fremd["police-x"].beitrag.pausen == ()
    # Eine ausgeschaltete Klammer auch nicht.
    aus = _wegfall(haus.kennungen)
    aus[0].active = False
    assert jm._policen_lesen(haus.c, (q,), {q.id: q.ab}, aus)["police-x"].beitrag.pausen == ()


def _enden(haus, police: pol.Police, geladen=()):
    f = ag.fenster(haus.c, bis=STICHTAG)
    basis = {"fixkosten": {"versicherung/rente": -3600_00}}
    return jm._vertragsenden(haus.c, f, list(geladen), basis, None, {police.konto: police},
                             police_vertraege={police.beitrag.vertrag})


def test_the_contract_ends_with_the_payout_without_anyone_cancelling_it(haus, monkeypatch):
    _vertrag(monkeypatch, haus.kennungen)                  # kein `gekuendigt_zum`
    q = _quelle()
    police = jm._policen_lesen(haus.c, (q,), {q.id: q.ab}, [])["police-x"]
    [e] = _enden(haus, police)
    assert (e["ende"], e["police"], e["jahr"]) == (date(2032, 2, 1), "Police X", 3600_00)
    # Ab Maerz 2032 fehlt der Beitrag in der Basis, im Jahr der Auszahlung fuer zehn Monate.
    [post] = jm._vertragsende_posten([e], 2032, 0, 0.0, 0.0)["fixkosten"]
    assert post.cents == round(3600_00 * 10 / 12)
    assert post.label == "Vertrag X endet mit der Auszahlung"
    assert "letzter Beitrag 02/2032, Police X zahlt 03/2032 aus" in post.herleitung


def test_an_earlier_cancellation_wins_over_the_payout(haus, monkeypatch):
    _vertrag(monkeypatch, haus.kennungen, gekuendigt_zum="2031-06-30")
    q = _quelle()
    police = jm._policen_lesen(haus.c, (q,), {q.id: q.ab}, [])["police-x"]
    [e] = _enden(haus, police)
    assert (e["ende"], e["police"]) == (date(2031, 6, 30), None)
    [post] = jm._vertragsende_posten([e], 2032, 0, 0.0, 0.0)["fixkosten"]
    assert post.label == "Vertrag X gekündigt"
    # Eine spaetere Kuendigung aendert nichts: die Police zahlt vorher aus.
    _vertrag(monkeypatch, haus.kennungen, gekuendigt_zum="2035-06-30")
    [spaeter] = _enden(haus, police)
    assert (spaeter["ende"], spaeter["police"]) == (date(2032, 2, 1), "Police X")


def test_a_contract_without_a_police_payout_ends_only_by_cancellation(haus, monkeypatch):
    _vertrag(monkeypatch, haus.kennungen)
    police = dataclasses.replace(
        jm._policen_lesen(haus.c, (_quelle(),), {"police-x": None}, [])["police-x"])
    assert police.beginn is None and _enden(haus, police) == []


def _annahmen(tmp_path, *, depot: float = 0.0, inflation: float = 0.0,
              abzug: float = 0.0) -> Path:
    """Eine Annahmedatei aus der Vorgabe: alle Saetze null, der Depotsatz, die
    Inflation und der Abzug auf eine Auszahlung nach Wunsch. Keine Vorabpauschale:
    die Steuer im Depot ist null."""
    spec = yaml.safe_load(
        (Path(jm.__file__).parent.parent / "vorgaben" / "assumptions.yaml")
        .read_text(encoding="utf-8"))
    spec["inflation_pa"] = inflation
    spec["kapital"]["rendite_nominal_pa"] = 0.0
    spec["kapital"]["rendite_depot_pa"] = depot
    spec["kapital"]["vorabpauschale"]["basiszins_pa"] = 0.0
    spec["erwerbseinkommen"]["gehalt_steigerung_pa"] = 0.0
    spec["ruhestand"]["abzug_renten"] = abzug
    pfad = tmp_path / "annahmen.yaml"
    pfad.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    # Dieselbe Datei mit anderen Werten: ohne das liest `assumptions` die alten.
    ann.reset_cache()
    return pfad


def _eingaben(haus, monkeypatch, tmp_path, *, quelle: Quelle | None = None,
              szenarien: list | None = None, depot: float = 0.0, inflation: float = 0.0,
              kosten: float | None = None, abzug: float = 0.0):
    """Die Hochrechnung dieses Hauptbuchs mit einer Police: ohne Gehalt, Kredite,
    Objekte und Zinssaetze der Konfiguration, damit nur sie rechnet."""
    quelle = quelle or _quelle()
    monkeypatch.setattr(renten, "quellen", lambda config_dir=None: [quelle])
    # Ohne Angabe gar keine Planzeilen -- nicht die der Konfiguration.
    pfad = tmp_path / "szenarien.yaml"
    pfad.write_text(yaml.safe_dump({"szenarien": szenarien or []}, allow_unicode=True),
                    encoding="utf-8")
    e = jm.eingaben(
        haus.c, base_year=2026, bis=STICHTAG, assumptions=_annahmen(
            tmp_path, depot=depot, inflation=inflation, abzug=abzug),
        szenarien=pfad, puffer_cents=1_000_00,
        toepfe={"tagesgeld": 200_000_00, "depot": 0, "policen": STAND},
        policen_je_konto={quelle.konto: STAND})
    police = e.policen[quelle.konto]
    if kosten is not None:
        police = dataclasses.replace(police, kosten_pa=kosten)
    return dataclasses.replace(
        e, zinssaetze={}, teilzeit=(), tilgungsplaene=(), rentenbeginn=None,
        objektprognosen=(), policen={quelle.konto: police})


def _frei_ab(kennungen: list[str], start: str) -> list[dict]:
    return [{"id": "frei", "name": "Beitragsfrei", "aktiv": True, "zeilen": [{
        "label": "beitragsfrei", "art": "wegfall", "amount_cents": 0, "frequenz": "monatlich",
        "start": start, "kategorie": "versicherung/rente", "konto": "a",
        "buchungen": kennungen[:1]}]}]


def test_the_savings_rate_is_unchanged_until_the_payout_and_rises_by_the_contribution(
        haus, monkeypatch, tmp_path):
    """Der Beitrag war schon Ausgabe: er aendert die Sparrate nicht. Mit der Auszahlung
    endet er als Ausgabe, und die Sparrate steigt um ihn."""
    _vertrag(monkeypatch, haus.kennungen)
    e = _eingaben(haus, monkeypatch, tmp_path)
    ohne = dataclasses.replace(e, planzeilen=dataclasses.replace(e.planzeilen, enden=()),
                               policen={})
    mit, davor = jm.rechnen(e, end_year=2034), jm.rechnen(ohne, end_year=2034)
    for jahr in (2027, 2031):
        assert mit.year(jahr).saving_cents == davor.year(jahr).saving_cents, jahr
    # Die Auszahlung kostet ihren Abzug (im Block `rente`); die Ausgabe selbst endet
    # im Monat der Auszahlung: zehn Monate im Jahr der Auszahlung, danach zwoelf.
    fix = {j: mit.year(j).blocks["fixkosten"] - davor.year(j).blocks["fixkosten"]
           for j in (2031, 2032, 2033)}
    assert fix == {2031: 0, 2032: 10 * 300_00, 2033: 12 * 300_00}


def test_nothing_is_created_or_lost_when_a_contribution_flows_into_the_police(
        haus, monkeypatch, tmp_path):
    _vertrag(monkeypatch, haus.kennungen)
    lauf = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, depot=0.07), end_year=2034)
    for y in lauf.years:
        assert y.tagesgeld_cents + y.depot_cents + y.policen_cents == y.closing_cents, y.year
        assert sum(p.cents for p in y.posten["rendite"]) == y.return_cents, y.year
        assert sum(p.cents for p in y.posten["policen_beitrag"]) == y.in_policen_cents, y.year
    assert lauf.year(2026).in_policen_cents == 3 * 300_00           # drei Restmonate
    assert lauf.year(2031).in_policen_cents == 12 * 300_00
    assert lauf.year(2032).in_policen_cents == 2 * 300_00           # Januar, Februar
    assert lauf.year(2033).in_policen_cents == 0


def _ausgabe_des_vertrags(y) -> int:
    """Was dieses Jahr fuer den Vertrag der Police ausgibt: seine Kategorie, die Rueckgabe
    der Inflation und sein Ende -- ohne die Kategorie einer anderen Reihe im Block."""
    return sum(p.cents for p in y.posten["fixkosten"]
               if p.label == "versicherung/rente" or p.label.startswith("Vertrag X"))


def test_the_expense_for_the_contribution_is_as_large_as_what_flows_into_the_police(
        haus, monkeypatch, tmp_path):
    """Die eine Regel aus Entscheidung 4: in die Police geht genau, was die Hochrechnung
    als Beitrag abzieht -- auch mit Inflation. Das gemessene Jahr waechst, der Beitrag
    nicht, also gibt ein Posten den Inflationsanteil zurueck."""
    _vertrag(monkeypatch, haus.kennungen)
    lauf = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, inflation=0.02), end_year=2035)
    for y in lauf.years:
        assert -_ausgabe_des_vertrags(y) == y.in_policen_cents, y.year
    assert lauf.year(2031).in_policen_cents == 12 * 300_00
    kategorie = next(p for p in lauf.year(2031).posten["fixkosten"]
                     if p.label == "versicherung/rente")
    assert -kategorie.cents > 12 * 300_00          # die gemessene Zahl bleibt inflationiert
    [zurueck] = [p for p in lauf.year(2031).posten["fixkosten"]
                 if p.label == "Vertrag X: Beitrag bleibt nominal"]
    assert zurueck.cents == -kategorie.cents - 12 * 300_00 and zurueck.quelle == "regel"
    assert "nominal fest" in zurueck.herleitung
    # Ohne Inflation gibt es nichts zurueckzugeben.
    flach = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path), end_year=2031)
    assert not [p for p in flach.year(2031).posten["fixkosten"] if "nominal" in p.label]


def test_the_contract_of_a_police_stops_without_growth_after_the_payout(
        haus, monkeypatch, tmp_path):
    """Nach der Auszahlung bleibt von der Ausgabe nichts stehen -- kein Rest aus der
    Inflation, den die gemessene Zahl mitwachsen liess."""
    _vertrag(monkeypatch, haus.kennungen)
    lauf = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, inflation=0.03), end_year=2040)
    for jahr in range(2033, 2041):
        assert _ausgabe_des_vertrags(lauf.year(jahr)) == 0, jahr


def test_the_savings_rate_of_the_payout_year_has_no_deduction_in_it(
        haus, monkeypatch, tmp_path):
    """Der Abzug geht von der Auszahlung ab und ist keine Ausgabe: er steht in keinem Block
    und nicht in der Sparrate, sondern mindert das Endkapital sichtbar."""
    _vertrag(monkeypatch, haus.kennungen)
    mit = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, kosten=0.0, abzug=0.25),
                     end_year=2034)
    ohne = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, kosten=0.0, abzug=0.0),
                      end_year=2034)
    for y in mit.years:
        assert y.blocks == ohne.year(y.year).blocks, y.year
        assert y.saving_cents == ohne.year(y.year).saving_cents, y.year
        assert y.tagesgeld_cents == ohne.year(y.year).tagesgeld_cents, y.year
    auszahlung = mit.year(2032)
    brutto = ohne.year(2032).posten["policen"][0].cents
    assert auszahlung.abzug_cents == round(brutto * 0.25)
    assert auszahlung.depot_cents == ohne.year(2032).depot_cents - auszahlung.abzug_cents
    # Die Rechnung des Auszahlungsjahres geht auf: der Abzug steht darin.
    assert auszahlung.closing_cents == (auszahlung.opening_cents + auszahlung.return_cents
                                        + auszahlung.saving_cents + auszahlung.in_policen_cents
                                        - auszahlung.abzug_cents)
    assert (auszahlung.tagesgeld_cents + auszahlung.depot_cents + auszahlung.policen_cents
            == auszahlung.closing_cents)
    assert sum(p.cents for p in auszahlung.posten["policen"]) == brutto - auszahlung.abzug_cents
    assert all(y.abzug_cents == 0 for y in mit.years if y.year != 2032)


def test_a_payout_larger_than_the_tagesgeld_does_not_push_it_below_zero(
        haus, monkeypatch, tmp_path):
    """Frueher zahlte das Tagesgeld den Abzug und fiel im Jahr der Auszahlung ins Minus,
    sobald er groesser war als das, was dort liegt. Jetzt zahlt ihn die Police."""
    _vertrag(monkeypatch, haus.kennungen)
    e = _eingaben(haus, monkeypatch, tmp_path, kosten=0.0, abzug=0.25)
    e = dataclasses.replace(e, monat=dataclasses.replace(
        e.monat, tagesgeld=1_000_00, policen=500_000_00, einstand=0,
        policen_je_konto={"police-x": 500_000_00}))
    lauf = jm.rechnen(e, end_year=2036)
    assert lauf.year(2032).abzug_cents > 100_000_00 > lauf.year(2031).tagesgeld_cents
    assert min(y.tagesgeld_cents for y in lauf.years) >= 0
    assert lauf.reicht_bis is None


def test_the_payout_names_stand_contribution_rate_and_check_value(
        haus, monkeypatch,
                                                                  tmp_path):
    _vertrag(monkeypatch, haus.kennungen)
    quelle = _quelle(pruefwert=Pruefwert(satz=0.06, cents=150_000_00, zum=date(2032, 3, 1)))
    e = _eingaben(haus, monkeypatch, tmp_path, quelle=quelle, depot=0.07)
    lauf = jm.rechnen(e, end_year=2033)
    [aus] = lauf.year(2032).posten["policen"]
    h = aus.herleitung
    assert "Policenwert 10.000,00 €" in h and "Beitrag 300,00 € im Monat (Vertrag X" in h
    assert "bis 02/2032" in h and "Rendite 6,00 % nach Kosten (Depot 7,00 % − Kosten 1,00 %)" in h
    assert "monatlich fortgeschrieben bis 03/2032" in h
    assert "Prüfwert der Mitteilung 150.000,00 € zum 03/2032 bei 6,00 %" in h
    assert "Modell bei 5,00 % zum selben Datum" in h and "% gegen den Prüfwert" in h
    # Ohne Pruefwert steht daneben, was das Schreiben sagt, wie bisher.
    ohne = _eingaben(haus, monkeypatch, tmp_path, quelle=_quelle(cents=120_000_00))
    [aus2] = jm.rechnen(ohne, end_year=2033).year(2032).posten["policen"]
    assert aus2.herleitung.endswith("laut Schreiben 120.000 €")
    assert "Prüfwert" not in aus2.herleitung


def test_a_check_value_without_a_rate_says_so_in_the_payout_and_leaves_the_rest_alone(
        haus, monkeypatch, tmp_path):
    _vertrag(monkeypatch, haus.kennungen)
    mit = _quelle(pruefwert=Pruefwert(satz=0.06, cents=150_000_00, zum=date(2032, 3, 1)))
    ohne_satz = _quelle(pruefwert=Pruefwert(satz=None, cents=150_000_00, zum=date(2032, 3, 1)))
    lauf_mit = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, quelle=mit, depot=0.07),
                          end_year=2033)
    e = _eingaben(haus, monkeypatch, tmp_path, quelle=ohne_satz, depot=0.07)
    lauf = jm.rechnen(e, end_year=2033)
    [aus] = lauf.year(2032).posten["policen"]
    [aus_mit] = lauf_mit.year(2032).posten["policen"]
    assert aus.herleitung.endswith("; Prüfwert ohne Satz, nicht vergleichbar")
    # Stand, Beitrag und Rendite stehen weiter da, und gerechnet wird wie mit Satz.
    assert aus.herleitung.startswith(aus_mit.herleitung.split("; Prüfwert")[0])
    assert aus.cents == aus_mit.cents
    assert jm.pruefvergleiche(e) == {"police-x": "Prüfwert ohne Satz, nicht vergleichbar"}


def test_the_payout_is_the_value_one_month_before_the_payout_month(
        haus, monkeypatch,
                                                                   tmp_path):
    """Zahlt die Police im Maerz aus, rechnet sie Januar und Februar noch mit, samt
    deren Beitraegen: genau der Stand der geschlossenen Formel."""
    _vertrag(monkeypatch, haus.kennungen)
    e = _eingaben(haus, monkeypatch, tmp_path, depot=0.07)
    lauf = jm.rechnen(e, end_year=2033)
    jahresanfang = lauf.year(2031).policen_cents
    [aus] = lauf.year(2032).posten["policen"]
    assert aus.cents == round(_geschlossen(jahresanfang, 300_00, 0.06, 2))


def test_a_wegfall_line_over_the_contribution_ends_it_and_the_police_grows_on(
        haus, monkeypatch, tmp_path):
    """Beitragsfreistellung im Szenario: ab dem Datum der Zeile fliesst nichts mehr
    in die Police, und ihre Auszahlung ist kleiner."""
    _vertrag(monkeypatch, haus.kennungen)
    offen = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, depot=0.07), end_year=2033)
    frei = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, depot=0.07,
                                szenarien=_frei_ab(haus.kennungen, "2030-01-01")),
                      end_year=2033)
    assert frei.year(2029).in_policen_cents == offen.year(2029).in_policen_cents
    for jahr in (2030, 2031, 2032):
        assert frei.year(jahr).in_policen_cents == 0, jahr
    assert frei.year(2031).policen_cents == pytest.approx(
        frei.year(2030).policen_cents * 1.06, abs=1)       # wuchs mit ihrem Satz weiter
    assert frei.year(2032).posten["policen"][0].cents < offen.year(2032).posten["policen"][0].cents


def _vermoegen(lauf, jahr: int) -> int:
    y = lauf.year(jahr)
    return y.tagesgeld_cents + y.depot_cents + y.policen_cents


def test_a_wegfall_line_over_the_contribution_does_not_count_it_twice(
        haus, monkeypatch, tmp_path):
    """Police ohne Kosten, Satz der Police gleich Depotsatz, Steuer im Depot null: mit
    und ohne die Zeile ist das Vermoegen zur Auszahlung und danach gleich. Die Zeile
    verteilt nur um -- weniger Police, mehr Depot --, sie schafft kein Geld."""
    _vertrag(monkeypatch, haus.kennungen)
    # Satz null: nichts verwischt, was gleich sein muss. Mit Inflation halten die
    # Zahlen genau, nicht nur auf ein Tausendstel: der Beitrag ist nominal fest, die
    # Zeile zieht ihn nominal ab, und nach der Auszahlung bleibt kein Rest stehen.
    for inflation in (0.0, 0.02, 0.05):
        ohne = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, kosten=0.0,
                                    inflation=inflation), end_year=2036)
        mit = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, kosten=0.0,
                                   inflation=inflation,
                                   szenarien=_frei_ab(haus.kennungen, "2030-01-01")),
                         end_year=2036)
        for jahr in range(2026, 2037):
            assert _vermoegen(mit, jahr) == _vermoegen(ohne, jahr), (inflation, jahr)
        assert mit.year(2031).policen_cents < ohne.year(2031).policen_cents
        assert mit.year(2031).depot_cents > ohne.year(2031).depot_cents
        assert mit.year(2034).policen_cents == ohne.year(2034).policen_cents == 0
    # Mit Rendite: die Police verzinst den Beitrag schon im Jahr, das Depot erst im
    # naechsten. Das Vermoegen der Police-Variante ist deshalb nicht kleiner, und der
    # Unterschied bleibt unter einem Zehntel Prozent.
    ohne7 = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, depot=0.07, kosten=0.0),
                       end_year=2036)
    mit7 = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, depot=0.07, kosten=0.0,
                                szenarien=_frei_ab(haus.kennungen, "2030-01-01")),
                      end_year=2036)
    for jahr in (2032, 2033, 2036):
        unterschied = _vermoegen(ohne7, jahr) - _vermoegen(mit7, jahr)
        assert 0 <= unterschied < _vermoegen(ohne7, jahr) / 1000, (jahr, unterschied)


def test_a_wegfall_line_that_ends_before_the_payout_leaves_nothing_standing_after_it(
        haus, monkeypatch, tmp_path):
    """Beitragsfrei nur von 2029 bis 2030, Auszahlung im Maerz 2032: in den Monaten der
    Zeile zieht sie die Ausgabe ab, ab der Auszahlung das Ende des Vertrags -- keines
    von beiden doppelt, und nach der Auszahlung steht keine Ausgabe ohne Police da."""
    _vertrag(monkeypatch, haus.kennungen)
    frei = _frei_ab(haus.kennungen, "2029-01-01")
    frei[0]["zeilen"][0]["ende"] = "2030-12-31"
    for inflation in (0.0, 0.03):
        ohne = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, kosten=0.0,
                                    inflation=inflation), end_year=2036)
        mit = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, kosten=0.0,
                                   inflation=inflation, szenarien=frei), end_year=2036)
        for jahr in range(2026, 2037):
            assert _vermoegen(mit, jahr) == _vermoegen(ohne, jahr), (inflation, jahr)
        assert mit.year(2029).in_policen_cents == mit.year(2030).in_policen_cents == 0
        assert mit.year(2031).in_policen_cents == 12 * 300_00
        for jahr in range(2033, 2037):
            assert _ausgabe_des_vertrags(mit.year(jahr)) == 0, jahr


def test_the_flat_deduction_on_a_payout_also_takes_the_contributions(haus, monkeypatch,
                                                                    tmp_path):
    """Entscheidung 5: Der Abzug gilt pauschal auf die ganze Auszahlung -- auch auf das,
    was als Beitrag hineinfloss. Wer beitragsfrei stellt, hat deshalb nach der
    Auszahlung mehr: genau den Abzug auf die Beitraege, die er nicht eingezahlt hat."""
    _vertrag(monkeypatch, haus.kennungen)
    ohne = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, kosten=0.0, abzug=0.25),
                      end_year=2034)
    mit = jm.rechnen(_eingaben(haus, monkeypatch, tmp_path, kosten=0.0, abzug=0.25,
                               szenarien=_frei_ab(haus.kennungen, "2030-01-01")),
                     end_year=2034)
    nicht_eingezahlt = (ohne.year(2032).posten["policen"][0].cents
                        - mit.year(2032).posten["policen"][0].cents)
    assert nicht_eingezahlt == 26 * 300_00                  # 2030 bis Februar 2032
    assert _vermoegen(mit, 2033) - _vermoegen(ohne, 2033) == round(nicht_eingezahlt * 0.25)


# ------------------------------------------- auf den Daten dieses Haushalts (Config)

@pytest.fixture
def conn():
    c = connect()
    yield c
    c.close()


def _police_mit_beitrag():
    """Die erste Rentenquelle mit Beitrag, ihr Vertrag und ihre Buchungen -- aus der Config."""
    for q in renten.quellen():
        if q.beitrag and q.konto and q.art == "kapital" and q.pruefwert:
            vertrag = next(a for a in abos.alle_vertraege() if a["id"] == q.beitrag)
            return q, vertrag
    pytest.skip("keine Police mit Beitrag und Pruefwert in dieser Config")


def test_a_police_in_the_config_reads_its_contribution_from_its_contract(conn):
    q, vertrag = _police_mit_beitrag()
    police = jm._policen_lesen(conn, (q,), {q.id: renten.beginn(q)}, [])[q.konto]
    assert police.beitrag.cents == -vertrag["betrag_cents"]
    assert (police.beitrag.takt, police.beitrag.vertrag) == (vertrag["takt"], vertrag["id"])
    assert police.kosten_pa == (q.kosten_pa or 0.0) and police.pruefwert == q.pruefwert


def test_the_double_count_test_holds_on_the_data_of_this_household(conn, monkeypatch, tmp_path):
    """Dieselbe Probe auf dem echten Hauptbuch (oder dem Musterhaushalt): eine Wegfall-Zeile
    ueber den Beitrag der ersten Police verteilt nur um."""
    q, vertrag = _police_mit_beitrag()
    ab = renten.beginn(q)
    if not vertrag["buchungen"] or ab is None:
        pytest.skip("der Vertrag hat keine Buchungen oder die Police keinen Auszahlungstermin")
    start = f"{max(date.today().year + 1, ab.year - 3)}-01-01"
    if date.fromisoformat(start) >= ab:
        pytest.skip("die Auszahlung liegt zu nah")
    pfad = tmp_path / "frei.yaml"
    pfad.write_text(yaml.safe_dump({"szenarien": [{
        "id": "frei", "name": "Beitragsfrei", "aktiv": True, "zeilen": [{
            "label": "beitragsfrei", "art": "wegfall", "amount_cents": 0,
            "frequenz": "monatlich", "start": start, "kategorie": vertrag["kategorie"],
            "konto": vertrag["konto"], "buchungen": vertrag["buchungen"][:1]}]}]},
        allow_unicode=True), encoding="utf-8")
    stand = 20_000_00
    leer = tmp_path / "leer.yaml"
    leer.write_text("szenarien: []\n", encoding="utf-8")

    def lauf(szenarien, inflation):
        # Alle Saetze null, Steuer null: nur die Inflation darf etwas verwischen.
        e = jm.eingaben(conn, assumptions=_annahmen(tmp_path, inflation=inflation),
                        szenarien=szenarien, puffer_cents=1_000_00,
                        toepfe={"tagesgeld": 100_000_00, "depot": 0, "policen": stand},
                        policen_je_konto={q.konto: stand})
        police = dataclasses.replace(e.policen[q.konto], kosten_pa=0.0)
        e = dataclasses.replace(e, policen={**e.policen, q.konto: police},
                                rentenbeginn=None, teilzeit=())
        assert e.policen[q.konto].beitrag.pausen == (
            ((date.fromisoformat(start), None),) if szenarien == pfad else ())
        return jm.rechnen(e, end_year=ab.year + 2)

    # Mit Inflation genau, nicht nur auf ein Tausendstel: die Ausgabe fuer den Beitrag ist
    # nominal fest, und nach der Auszahlung bleibt kein Rest stehen.
    for inflation in (0.0, 0.02):
        ohne, mit = lauf(leer, inflation), lauf(pfad, inflation)
        for jahr in range(ohne.base_year, ab.year + 3):
            assert _vermoegen(mit, jahr) == _vermoegen(ohne, jahr), (inflation, jahr)
    assert mit.year(ab.year - 1).policen_cents < ohne.year(ab.year - 1).policen_cents
