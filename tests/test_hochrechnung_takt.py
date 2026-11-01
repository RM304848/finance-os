"""Die Hochrechnung mit Takt (Schritt 4.4): Basis, Rechenweg, Wegfall, Vertragsende, Treffer.

Eine Reihe mit festem Takt zaehlt mit ihrem Betrag je Termin mal Termine je Jahr,
nicht mit der Summe ihrer Monate. Eine Miete, deren Buchungstag ueber das Monatsende
rutscht, hat dreizehn Buchungen im Fenster und zwoelf Termine; ein gekuendigter Vertrag
faellt sofort heraus, ein neuer zaehlt voll. Die Basis, ein Wegfall und ein Vertragsende
rechnen denselben Beitrag.

Alles ist erfunden und rund: eine Monatsmiete von 1.000 Euro, am 1. faellig, die des
Oktobers 2026 schon am 30.09. gebucht.
"""

from __future__ import annotations

import dataclasses
import hashlib
from datetime import date
from pathlib import Path

import pytest

from finctl import abos, reihen
from finctl.forecast import abgleich as ag
from finctl.forecast import fortschreibung as fs
from finctl.forecast import jahre as jm
from finctl.forecast import szenarien as sz
from finctl.forecast import treffer as tr
from finctl.forecast import wachstum
from finctl.ledger.db import connect, init_db

STICHTAG = date(2026, 9, 30)
MIETE = -100_000


def _monat(i: int) -> date:
    """Der i-te Monat ab Januar 2025."""
    index = 2025 * 12 + i
    return date(index // 12, index % 12 + 1, 1)


@pytest.fixture
def haushalt(tmp_path, monkeypatch):
    """Zweiundzwanzig Monate Hauptbuch auf einem Konto; Handentscheidungen im Wegwerfordner."""
    (tmp_path / "config").mkdir()
    monkeypatch.setattr(reihen, "CONFIG_DIR", tmp_path / "config")
    c = connect(init_db(tmp_path / "t.db"))
    c.execute("INSERT INTO accounts (id, display_name, institution, account_type, "
              "ingest_mode, parser_profile) VALUES ('a','A','X','giro','parsed','p')")
    for kennung, kind, fix in (
            ("wohnen", "expense", 0), ("wohnen/miete", "expense", 1),
            ("abo", "expense", 1), ("abo/video", "expense", 1),
            ("konsum", "expense", 0), ("konsum/essen", "expense", 0),
            ("einkommen", "income", 0), ("einkommen/gehalt", "income", 0)):
        c.execute("INSERT INTO mgmt_categories (id, parent_id, name, kind, fixkosten) "
                  "VALUES (?,?,?,?,?)",
                  (kennung, kennung.split("/")[0] if "/" in kennung else None,
                   kennung, kind, fix))
    for i in range(22):
        erster = _monat(i)
        ende = ag._month_end(erster)
        c.execute(
            "INSERT INTO statements (id, account_id, source_path, source_name, file_sha256, "
            "period_start, period_end, balance_start_cents, balance_end_cents, "
            "parser_profile, parser_version, status, imported_at) "
            "VALUES (?, 'a','x','x',?,?,?,0,0,'p','1','imported','now')",
            (i + 1, f"sha{i}", erster.isoformat(), ende.isoformat()))
    c.commit()
    yield c
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


def _miete_rutscht(c) -> list[str]:
    """Zwoelf Mieten am 1., Oktober 2025 bis September 2026, dazu die vom Oktober 2026,
    am 30.09. gebucht: dreizehn Buchungen im Fenster."""
    kennungen = [_buche(c, _monat(i), MIETE, "wohnen/miete", "vermieter")
                 for i in range(9, 21)]
    kennungen.append(_buche(c, date(2026, 9, 30), MIETE, "wohnen/miete", "vermieter"))
    return kennungen


def _fenster(c, bis: date = STICHTAG):
    f = ag.fenster(c, bis=bis)
    assert f is not None and f.monate == 12
    return f


# ----------------------------------------------------------------- die Basis


def test_a_rent_that_slid_over_the_month_end_counts_twelve_terms_in_the_base(haushalt):
    _miete_rutscht(haushalt)
    f = _fenster(haushalt)
    basis, _, zerlegt = jm._basis(haushalt, f)
    assert basis["fixkosten"]["wohnen/miete"] == 12 * MIETE
    z = zerlegt["fixkosten"]["wohnen/miete"]
    assert [(r.reihe, r.takt, r.beitrag.betrag_je_termin) for r in z.reihen] == [
        ("vermieter", 1, MIETE)]
    assert (z.rest_cents, z.rest_monate, z.cents) == (0, (), 12 * MIETE)


def test_without_series_the_base_is_the_sum_of_the_window_as_before(haushalt):
    _miete_rutscht(haushalt)
    f = _fenster(haushalt)
    vorschau = jm._hochrechnung(f, None)
    [p] = fs.fortschreiben(haushalt, vorschau, fs.messen(haushalt, vorschau))
    assert (p.reihe, p.ergebnis.cents) == ("", 13 * MIETE)


def test_every_category_splits_into_series_and_rest_that_add_up_to_its_base(haushalt):
    _miete_rutscht(haushalt)
    for i in range(9, 21):
        _buche(haushalt, _monat(i).replace(day=2), -2_000, "abo/video", "streamer")
    _buche(haushalt, date(2026, 1, 9), -4_000, "konsum/essen", "markt")
    _buche(haushalt, date(2026, 5, 9), -6_100, "konsum/essen", "markt")
    _buche(haushalt, date(2026, 5, 10), -300, "konsum/essen", "")
    basis, _, zerlegt = jm._basis(haushalt, _fenster(haushalt))
    assert zerlegt.keys() == basis.keys()
    for block, kategorien in basis.items():
        assert zerlegt[block].keys() == kategorien.keys()
        for kategorie, cents in kategorien.items():
            assert zerlegt[block][kategorie].cents == cents, (block, kategorie)
    assert basis["konsum"]["konsum/essen"] == jm._vf.summe_aufs_jahr(-10_400, 12)
    assert zerlegt["konsum"]["konsum/essen"].reihen == ()


def test_the_series_belong_to_the_eingaben_and_swap_with_the_base(haushalt):
    _miete_rutscht(haushalt)
    e = jm.eingaben(haushalt, base_year=2026, bis=STICHTAG)
    assert e.base["fixkosten"]["wohnen/miete"] == 12 * MIETE
    assert e.base_reihen["fixkosten"]["wohnen/miete"].reihen[0].reihe == "vermieter"
    # Eine Rechnung, die nichts liest: die Posten kommen aus `base_reihen`.
    lauf = jm.rechnen(e, end_year=2028)
    miete = next(p for p in lauf.years[0].posten["fixkosten"] if p.verweis == "wohnen/miete")
    assert miete.herleitung.startswith(
        "−12.000 € aus vermieter: monatlich, je Termin −1.000,00 € "
        "(Median der letzten 3 Termine), × 12 = −12.000,00 € im Jahr")
    assert "Inflation" in miete.herleitung and "; Rest" not in miete.herleitung


def test_the_walkthrough_names_series_then_the_rest(haushalt):
    _miete_rutscht(haushalt)
    _buche(haushalt, date(2026, 3, 9), -300_000, "wohnen/miete", "vermieter")
    _buche(haushalt, date(2026, 4, 9), -50_000, "wohnen/miete", "")
    e = jm.eingaben(haushalt, base_year=2026, bis=STICHTAG)
    lauf = jm.rechnen(e, end_year=2027)
    miete = next(p for p in lauf.years[0].posten["fixkosten"] if p.verweis == "wohnen/miete")
    text = miete.herleitung
    assert text.index("vermieter: monatlich") < text.index("Rest −3.500 € gemessen")
    assert "1 abweichender Termin zählt im Rest der Kategorie" in text
    assert e.base["fixkosten"]["wohnen/miete"] == 12 * MIETE - 300_000 - 50_000


def test_juengst_counts_the_series_the_same_and_only_the_rest_in_the_last_months(haushalt):
    for i in range(9, 21):
        _buche(haushalt, _monat(i).replace(day=2), -1_000, "konsum/essen", "abo")
    _buche(haushalt, date(2026, 1, 8), -3_000, "konsum/essen", "")
    _buche(haushalt, date(2026, 8, 20), -9_000, "konsum/essen", "")
    je_tempo = jm.eingaben_je_tempo(haushalt, base_year=2026, bis=STICHTAG)
    schnitt, juengst = je_tempo["schnitt"], je_tempo["juengst"]
    assert schnitt.base["konsum"]["konsum/essen"] == -12_000 + jm._vf.summe_aufs_jahr(-12_000, 12)
    assert juengst.base["konsum"]["konsum/essen"] == -12_000 + jm._vf.summe_aufs_jahr(-9_000, 3)
    assert juengst.base_monate["konsum"]["konsum/essen"] == 3
    assert (schnitt.base_reihen["konsum"]["konsum/essen"].reihen
            == juengst.base_reihen["konsum"]["konsum/essen"].reihen)


def test_a_cancelled_contract_leaves_the_base_at_once_and_a_new_one_counts_in_full(haushalt):
    for i in range(9, 17):               # Oktober 2025 bis Mai 2026, dann nichts mehr
        _buche(haushalt, _monat(i).replace(day=2), -1_500, "abo/video", "streamer")
    for i in range(18, 21):              # drei Termine: Juli bis September 2026
        _buche(haushalt, _monat(i).replace(day=2), -2_000, "abo/video", "neu")
    basis, _, zerlegt = jm._basis(haushalt, _fenster(haushalt))
    assert basis["fixkosten"]["abo/video"] == 12 * -2_000
    alt = {z.reihe: z for z in zerlegt["fixkosten"]["abo/video"].reihen}
    assert alt["streamer"].ergebnis.cents == 0 and not alt["streamer"].beitrag.laeuft
    assert alt["neu"].ergebnis.cents == -24_000


# ----------------------------------------------------------------- Wegfall


def _wegfall(kennungen: list[str]) -> sz.Line:
    return sz.Line(label="Miete entfällt", amount_cents=0, kind="wegfall",
                   start=date(2027, 1, 1), buchungen=kennungen[:1])


def test_a_wegfall_takes_out_what_the_base_counts_twelve_terms_not_thirteen(haushalt):
    kennungen = _miete_rutscht(haushalt)
    f = _fenster(haushalt)
    line = _wegfall(kennungen)
    ohne = sz.messung(haushalt, line, f)
    assert ohne["cents"] == 13 * MIETE and "takt_jahr" not in ohne
    m = sz.messung(haushalt, line, f, jm._reihen_laden(haushalt, f, None))
    assert (m["cents"], m["takt_jahr"], m["rest_cents"]) == (13 * MIETE, 12 * MIETE, 0)
    assert m["takt_reihen"] == [(
        "vermieter: monatlich, je Termin −1.000,00 € "
        "(Median der letzten 3 Termine), × 12 = −12.000,00 € im Jahr")]
    horizont = date(2027, 12, 1)
    # Ein ganzes Jahr: die Basis hat zwoelf Termine, der Wegfall nimmt zwoelf ab.
    assert sz.jahreswirkung(line, m, 2027, 0, horizont) == 12 * -MIETE
    # Ohne Reihen (und fuer die Kontoprognose) wie bisher: die Summe des Fensters.
    assert sz.jahreswirkung(line, ohne, 2027, 0, horizont) == 13 * -MIETE
    # Das, was die Kontoprognose liest, aendert sich nicht.
    assert sz.restbetrag_je_termin(line, m) == sz.restbetrag_je_termin(line, ohne)


def test_a_wegfall_of_a_series_that_is_over_takes_out_nothing(haushalt):
    kennungen = [_buche(haushalt, _monat(i).replace(day=2), MIETE, "wohnen/miete", "vermieter")
                 for i in range(9, 15)]
    f = _fenster(haushalt)
    line = _wegfall(kennungen)
    m = sz.messung(haushalt, line, f, jm._reihen_laden(haushalt, f, None))
    assert (m["cents"], m["takt_jahr"], m["rest_cents"]) == (6 * MIETE, 0, 0)
    assert sz.jahreswirkung(line, m, 2027, 0, date(2027, 12, 1)) == 0


def test_a_wegfall_text_names_the_series_and_counts_twelve_months(haushalt):
    kennungen = _miete_rutscht(haushalt)
    f = _fenster(haushalt)
    line = _wegfall(kennungen)
    m = sz.messung(haushalt, line, f, jm._reihen_laden(haushalt, f, None))
    klammer = sz.Scenario(id="k", name="K", active=True, lines=[line])
    [posten], _, _ = jm._planposten([klammer], {("k", 0): m}, 2027, 0)
    assert posten.cents == 12 * -MIETE
    assert posten.herleitung.startswith("entfällt: −12.000 € im Jahr: vermieter: monatlich")
    assert posten.herleitung.endswith("(13 zugeordnete Buchungen) × 12/12")


def test_the_outlier_of_a_series_leaves_with_its_wegfall_through_the_rest(haushalt):
    kennungen = [_buche(haushalt, _monat(i).replace(day=2), MIETE, "wohnen/miete", "vermieter")
                 for i in range(9, 21)]
    _buche(haushalt, date(2026, 3, 9), -300_000, "wohnen/miete", "vermieter")
    f = _fenster(haushalt)
    m = sz.messung(haushalt, _wegfall(kennungen), f, jm._reihen_laden(haushalt, f, None))
    assert (m["takt_jahr"], m["rest_cents"]) == (12 * MIETE, -300_000)
    assert sz.jahreswirkung(_wegfall(kennungen), m, 2027, 0, date(2027, 12, 1)) == 1_500_000


def _mit_klammer(haushalt, line: sz.Line):
    """Die Eingaben der Jahresrechnung mit einer Klammer, die nur diese Zeile hat."""
    klammer = sz.Scenario(id="k", name="K", active=True, lines=[line])
    e = jm.eingaben(haushalt, base_year=2026, bis=STICHTAG)
    f = _fenster(haushalt)
    m = sz.messung(haushalt, line, f, jm._reihen_laden(haushalt, f, None))
    return dataclasses.replace(
        e, szenarien=[klammer],
        planzeilen=dataclasses.replace(e.planzeilen, messungen={("k", 0): m})), m


def _miete_und_plan(lauf, jahr: int) -> tuple[int, int]:
    y = next(y for y in lauf.years if y.year == jahr)
    return (sum(p.cents for p in y.posten["fixkosten"] if p.verweis == "wohnen/miete"),
            sum(p.cents for p in y.posten[ag.EINMALIG]))


def test_a_wegfall_that_replaces_the_whole_series_leaves_nothing_in_any_year(haushalt):
    """Die Reihe steigt in der Basis mit der Inflation, der Wegfall nimmt sie mit der
    Inflation heraus: In jedem Jahr bleibt null, nicht ein mit den Jahren wachsender Rest."""
    assert jm.ann.inflation_pa() > 0
    e, _ = _mit_klammer(haushalt, _wegfall(_miete_rutscht(haushalt)))
    lauf = jm.rechnen(e, end_year=2031)
    for jahr in range(2027, 2032):
        miete, plan = _miete_und_plan(lauf, jahr)
        assert miete < 12 * MIETE * 0.99, "die Reihe steigt in der Basis"
        assert abs(miete + plan) <= 1, (jahr, miete, plan)


def test_a_plan_line_takes_the_rising_measurement_off_a_flat_amount(haushalt):
    """Der geplante Betrag ist eine gesetzte Zahl und steigt nicht, die Messung steigt mit
    der Inflation. Ist beides zunaechst gleich, bleibt nichts; liegt der gesetzte Betrag zehn
    Prozent darueber, schrumpft der Rest mit jedem Jahr, bis die Messung ihn eingeholt hat."""
    rate = jm.ann.inflation_pa()
    assert rate > 0
    kennungen = _miete_rutscht(haushalt)
    f = _fenster(haushalt)
    horizont = date(2031, 12, 1)

    def zeile(betrag: int) -> sz.Line:
        return sz.Line(label="Miete geplant", amount_cents=betrag, kind="betrag",
                       frequency="monatlich", start=date(2025, 10, 1),
                       buchungen=kennungen[:1])

    def rest(line: sz.Line, jahr: int) -> int:
        m = sz.messung(haushalt, line, f, jm._reihen_laden(haushalt, f, None))
        steigt = wachstum.faktor(f.mitte, wachstum.jahresmitte(jahr), rate)
        return sz.jahreswirkung(line, m, jahr, 0, horizont, steigt)

    assert [rest(zeile(MIETE), j) for j in (2027, 2028, 2029)] == [0, 0, 0]
    mehr = zeile(round(MIETE * 1.1))
    for jahr in (2027, 2028, 2029):
        steigt = wachstum.faktor(f.mitte, wachstum.jahresmitte(jahr), rate)
        erwartet = 12 * mehr.amount_cents - round(12 * MIETE * steigt)
        assert 0 > erwartet > 12 * mehr.amount_cents * 0.1
        assert rest(mehr, jahr) == erwartet
    assert rest(mehr, 2027) < rest(mehr, 2028) < rest(mehr, 2029) < 0


# ------------------------------------------------------------- Vertragsende


#: Der Vertrag aus `_vertrag` speist eine Police: nur dann misst die Rechnung sein Ende.
POLICE = frozenset({"miete"})


def _vertrag(monkeypatch, kennungen: list[str], **extra):
    basis = {"id": "miete", "name": "Miete", "kategorie": "wohnen/miete", "konto": "a",
             "betrag_cents": MIETE, "takt": 1, "faellig": "2026-11-01",
             "gekuendigt_zum": "2026-12-31", "buchungen": kennungen[:1]}
    basis.update(extra)
    monkeypatch.setattr(abos, "alle_vertraege", lambda: [abos.normalisieren(basis)])


def test_a_cancelled_contract_takes_out_its_year_value_not_the_window_sum(haushalt,
                                                                        monkeypatch):
    kennungen = _miete_rutscht(haushalt)
    # Die Vertragsrate liegt ueber dem, was gebucht wird: Sie deckelt nichts.
    _vertrag(monkeypatch, kennungen, betrag_cents=-110_000)
    f = _fenster(haushalt)
    reihen_ = jm._reihen_laden(haushalt, f, None)
    basis = {"fixkosten": {"wohnen/miete": 12 * MIETE}}
    [e] = jm._vertragsenden(haushalt, f, [], basis, reihen_, police_vertraege=POLICE)
    assert e["cents"] == 13 * MIETE
    assert e["jahr"] == 12 * -MIETE and not e["gedeckelt"]
    [post] = jm._vertragsende_posten([e], 2028, 0, 0.0, 0.0)["fixkosten"]
    assert post.cents == 12 * -MIETE
    assert post.herleitung.startswith("gekündigt zum 12/2026: −12.000 € im Jahr: vermieter:")
    # Ohne Reihen wie bisher: die Summe des Fensters aufs Jahr.
    [alt] = jm._vertragsenden(haushalt, f, [], basis, police_vertraege=POLICE)
    assert alt["jahr"] == 13 * -MIETE


def test_the_contract_rate_still_caps_what_a_cancellation_promises(haushalt, monkeypatch):
    """Mit Reihen wie ohne: nie mehr versprechen, als der Vertrag kostet."""
    kennungen = _miete_rutscht(haushalt)
    _vertrag(monkeypatch, kennungen, betrag_cents=-90_000)
    f = _fenster(haushalt)
    basis = {"fixkosten": {"wohnen/miete": 12 * MIETE}}
    [e] = jm._vertragsenden(haushalt, f, [], basis,
                             jm._reihen_laden(haushalt, f, None), police_vertraege=POLICE)
    assert e["gedeckelt"] and e["jahr"] == 12 * 90_000


def test_a_wegfall_line_and_a_cancellation_on_one_series_count_once(haushalt, monkeypatch):
    """Die Reihe laeuft ueber das Fenster hinaus (die Mieten davor sind ihr Alter, nicht ihr
    Fenster): Zieht eine Wegfall-Zeile sie ab, zieht die Kuendigung sie nicht noch einmal ab,
    auch nicht mit den Terminen vor dem Fenster."""
    kennungen = [_buche(haushalt, _monat(i).replace(day=2), MIETE, "wohnen/miete", "vermieter")
                 for i in range(3, 21)]
    _vertrag(monkeypatch, kennungen)
    f = _fenster(haushalt)
    reihen_ = jm._reihen_laden(haushalt, f, None)
    basis = {"fixkosten": {"wohnen/miete": 12 * MIETE}}
    assert len(jm._vertragsenden(haushalt, f, [], basis, reihen_, police_vertraege=POLICE)) == 1
    klammer = sz.Scenario(id="k", name="K", active=True, lines=[sz.Line(
        label="Miete entfällt", amount_cents=0, kind="wegfall", start=date(2027, 1, 1),
        buchungen=kennungen[:1])])
    assert jm._vertragsenden(haushalt, f, [klammer], basis, reihen_,
                             police_vertraege=POLICE) == []


def test_a_contract_whose_series_is_over_saves_nothing(haushalt, monkeypatch):
    kennungen = [_buche(haushalt, _monat(i).replace(day=2), MIETE, "wohnen/miete", "vermieter")
                 for i in range(9, 15)]
    _vertrag(monkeypatch, kennungen)
    f = _fenster(haushalt)
    basis = {"fixkosten": {"wohnen/miete": 0}}
    assert jm._vertragsenden(haushalt, f, [], basis,
                             jm._reihen_laden(haushalt, f, None), police_vertraege=POLICE) == []


# ------------------------------------------------------------- Treffer-Check


def test_the_check_expects_what_the_base_of_the_projection_counts(haushalt):
    """Das Soll ist der Jahreswert je Block aus der Basis, durch zwoelf: Die Miete, die am
    30.09. fuer den Oktober gebucht wurde, hebt es nicht auf 13/12."""
    _miete_rutscht(haushalt)
    oktober = date(2026, 10, 1)
    assert tr.fenster_vor(haushalt, oktober).monate == 12
    [m] = tr.jahresbasis(haushalt, [oktober], plaene=[], objekt_cents=lambda _m: 0)
    assert m.soll["fixkosten"] == MIETE
    assert m.soll["fixkosten"] != round(13 * MIETE / 12)


def test_the_check_still_counts_interest_and_deselected_categories_as_booked(haushalt):
    """Das Ist ist gebucht; was die Hochrechnung rechnet (Zinsen) oder abwaehlt, steht
    im Soll wie gebucht."""
    for i in range(9, 21):
        _buche(haushalt, _monat(i).replace(day=2), -1_000, "konsum/essen", "abo")
    f = _fenster(haushalt)
    soll = tr._soll_je_block(haushalt, f)
    assert soll["konsum"] == -1_000
    assert set(soll) == set(jm.FROM_BASE)
    assert Path(tr.__file__).exists()
