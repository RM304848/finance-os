"""Verträge zählen in beiden Modellen über ihre Tatsachen (Schritt 5b, E.2d).

Vorrat, Kündigung, Pause durch eine Wegfall-Zeile und offene Rückzahlungen der Mitzahler
gelten in der Jahresrechnung wie im Monatsmodell. Alles hier ist erfunden und rund.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from finctl import abos
from finctl.forecast import jahre as jm
from finctl.forecast import konten
from finctl.forecast import szenarien as sz
from finctl.forecast import vertraege as vt

MITTE = 2026.0
RATE = 0.0


def _abo(**extra):
    basis = {"id": "x", "name": "X", "kategorie": "abo/office", "konto": "a",
             "betrag_cents": -1_000, "takt": 1, "faellig": "2027-01-15"}
    basis.update(extra)
    return abos.normalisieren(basis)


def _jahr(vertrag: jm.Vertrag, jahr: int, nach: int = 0) -> int:
    posten = jm._vertragsposten((vertrag,), jahr, nach, MITTE, RATE)
    return sum(p.cents for liste in posten.values() for p in liste)


def _monatsmodell(a: dict, pausen, jahr: int) -> int:
    return sum(t["betrag_cents"] for t in abos.posten(
        [a], a["konto"], ab=date(jahr, 1, 1), bis=date(jahr, 12, 31), pausen={a["id"]: pausen}))


def test_a_prepaid_stock_costs_nothing_in_the_year_calculation_either():
    a = _abo(vorrat_bis="2027-07-15")
    v = jm.Vertrag(abo=a, block="fixkosten")
    assert _jahr(v, 2027) == -1_000 * 6        # Juli bis Dezember
    assert _jahr(v, 2028) == -1_000 * 12


def test_after_the_cancellation_nothing_is_due_in_either_model():
    a = _abo(gekuendigt_zum="2027-03-31")
    v = jm.Vertrag(abo=a, block="fixkosten")
    assert _jahr(v, 2027) == -1_000 * 3 == _monatsmodell(a, (), 2027)
    assert _jahr(v, 2028) == 0


def test_the_base_year_counts_only_the_months_still_to_come():
    v = jm.Vertrag(abo=_abo(), block="fixkosten")
    assert _jahr(v, 2027, nach=9) == -1_000 * 3


def test_a_pause_and_a_cancellation_together_take_every_due_date_out_once():
    pause = ((date(2027, 2, 1), date(2027, 3, 1)),)
    a = _abo(gekuendigt_zum="2027-06-30")
    v = jm.Vertrag(abo=a, block="fixkosten", pausen=pause)
    # Januar, April, Mai, Juni: vier Termine, ohne Februar und Maerz
    assert _jahr(v, 2027) == -1_000 * 4 == _monatsmodell(a, pause, 2027)


def test_a_pause_without_an_end_runs_on():
    a = _abo()
    pause = ((date(2027, 5, 1), None),)
    v = jm.Vertrag(abo=a, block="fixkosten", pausen=pause)
    assert _jahr(v, 2027) == -1_000 * 4
    assert _jahr(v, 2030) == 0


def test_what_the_partners_still_owe_comes_in_its_month():
    v = jm.Vertrag(abo=_abo(takt=12, faellig="2027-04-15"), block="fixkosten",
                   rueckzahlungen=((date(2027, 9, 1), 600), (date(2028, 4, 1), 300)))
    assert _jahr(v, 2027) == -1_000 + 600
    assert _jahr(v, 2028) == -1_000 + 300
    assert _jahr(v, 2027, nach=9) == 0         # April und September sind schon vorbei


def test_an_annual_contract_grows_at_its_due_date_like_in_the_account_model():
    a = _abo(takt=12, faellig="2027-12-15", betrag_cents=-10_000)
    wert = vt.vertragsbetrag(a, date(2027, 12, 15), mitte=MITTE, rate=0.02, police=())
    posten = jm._vertragsposten((jm.Vertrag(abo=a, block="fixkosten"),), 2027, 0, MITTE, 0.02)
    assert sum(p.cents for p in posten["fixkosten"]) == wert < -10_000


def test_a_police_contribution_stays_flat():
    a = _abo(id="police", betrag_cents=-10_000)
    assert vt.vertragsbetrag(a, date(2030, 1, 15), mitte=MITTE, rate=0.02,
                             police={"police"}) == -10_000


# ------------------------------------------------------------ Wegfall-Zeilen und Mitzahler

def _db(*buchungen):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE transactions (id INTEGER PRIMARY KEY, account_id TEXT,
            booking_date TEXT, amount_cents INTEGER, counterparty TEXT,
            counterparty_norm TEXT, raw_text TEXT, dedup_hash TEXT);
        CREATE TABLE splits (transaction_id INTEGER, seq INTEGER DEFAULT 0,
            mgmt_category_id TEXT, amount_cents INTEGER);
    """)
    for n, (wann, cents, name, kat, h, *konto) in enumerate(buchungen, start=1):
        norm = "".join(ch for ch in name.lower() if ch.isalnum())
        conn.execute("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)",
                     (n, konto[0] if konto else "a", wann, cents, name, norm,
                      f"Zahlung {name}", h))
        conn.execute("INSERT INTO splits VALUES (?,0,?,?)", (n, kat, cents))
    return conn


def _klammer(*zeilen):
    return [sz.Scenario(id="k", name="K", active=True, lines=list(zeilen))]


def test_a_removal_line_on_the_series_of_a_contract_pauses_it():
    conn = _db(("2026-11-15", -1_000, "Dienst", "abo/office", "v1"))
    a = _abo(buchungen=["v1"])
    zeile = sz.Line(label="Dienst entfaellt", amount_cents=0, kind="wegfall",
                    start=date(2027, 4, 1), buchungen=["v1"])
    assert vt.pausen(conn, _klammer(zeile), [a]) == {"x": ((date(2027, 4, 1), None),)}


def test_a_line_that_only_moves_the_series_between_accounts_does_not_pause():
    conn = _db(("2026-11-15", -1_000, "Dienst", "abo/office", "v1"))
    a = _abo(buchungen=["v1"])
    zeile = sz.Line(label="zieht um", amount_cents=0, kind="wegfall",
                    start=date(2027, 4, 1), buchungen=["v1"], nur_kontoprognose=True)
    assert vt.pausen(conn, _klammer(zeile), [a]) == {}


def test_the_payments_of_the_partners_leave_the_measurement_with_the_contract():
    conn = _db(("2026-11-15", -1_000, "Dienst", "abo/office", "v1"),
               ("2026-11-20", 500, "Mitzahler Eins", "abo/office", "m1"),
               ("2026-12-20", 500, "Mitzahler Eins", "abo/office", "m2"))
    a = _abo(buchungen=["v1"], geteilt={"zeitraeume": [
        {"von": "2026-11", "bis": "2026-11", "einsammeln": "2026-11", "personen": [
            {"name": "Mitzahler Eins", "anteil_cents": 500, "zahlungen": ["m1"]}]}]})
    ausgenommen = vt.aus_der_messung(conn, [a])
    assert "v1" in ausgenommen and "m1" in ausgenommen
    assert "m2" not in ausgenommen            # kein Teil des Zeitraums: bleibt gemessen


def test_a_contract_on_a_pass_through_account_counts_on_the_covering_account():
    a = _abo(konto="pp")
    gedeckt = abos.posten([a], {"a", "pp"}, ab=date(2027, 1, 1), bis=date(2027, 3, 31))
    assert [t["faellig"].month for t in gedeckt] == [1, 2, 3]
    assert abos.posten([a], "a", ab=date(2027, 1, 1), bis=date(2027, 3, 31)) == []


# ------------------------------------------------------------ erwarteter Anteil der Mitzahler

def _geteilt(*, zeitraeume=(), seit=None):
    """Zwei Personen in der Besetzung; die erste stand in den Zeitraeumen, die zweite nur hier
    (oder zahlt laufend, wenn `seit` gesetzt ist)."""
    personen = [{"name": "Eins", "anteil_cents": 300}, {"name": "Zwei", "anteil_cents": 200}]
    if seit:
        personen[1]["seit"] = seit
    return {"besetzung": personen,
            "zeitraeume": [{**z, "personen": [personen[0]]} for z in zeitraeume]}


def _zr(von, bis):
    return {"von": von, "bis": bis, "einsammeln": bis}


def test_a_term_without_a_period_expects_the_share_of_everyone_who_has_paid():
    a = _abo(takt=12, faellig="2028-04-15", betrag_cents=-1_000,
             geteilt=_geteilt(zeitraeume=[_zr("2027-04", "2028-04")]))
    assert abos.erwartete_anteile(a, date(2028, 4, 15)) == 300    # Zwei steht nur in der Vorlage
    assert abos.erwartete_anteile(a, date(2027, 4, 15)) == 0      # der Zeitraum deckt ihn


def test_a_period_ends_where_the_next_one_begins_and_a_one_month_period_covers_its_month():
    a = _abo(geteilt=_geteilt(zeitraeume=[_zr("2027-04", "2028-04"), _zr("2026-09", "2026-09")]))
    assert abos.zeitraum_am(a, date(2028, 3, 31))["von"] == "2027-04"
    assert abos.zeitraum_am(a, date(2028, 4, 1)) is None
    assert abos.zeitraum_am(a, date(2026, 9, 30))["von"] == "2026-09"
    assert abos.zeitraum_am(a, date(2026, 10, 1)) is None


def test_a_person_who_only_stands_in_the_template_is_no_expectation():
    a = _abo(geteilt={"besetzung": [{"name": "Zwei", "anteil_cents": 200}], "zeitraeume": []})
    assert abos.erwartete_anteile(a, date(2027, 1, 15)) == 0


def test_a_person_who_pays_along_counts_from_the_month_they_started():
    a = _abo(geteilt=_geteilt(seit="2027-03"))
    assert abos.erwartete_anteile(a, date(2027, 2, 15)) == 0
    assert abos.erwartete_anteile(a, date(2027, 3, 15)) == 200
    assert abos.erwartete_anteile(a, date(2027, 4, 15)) == 200


def test_a_period_that_names_the_person_leaves_them_to_its_open_share():
    a = _abo(geteilt=_geteilt(zeitraeume=[_zr("2027-01", "2027-03")], seit="2026-01"))
    # Der Zeitraum nennt nur Eins: Zwei zahlt laufend weiter und zaehlt je Termin.
    assert abos.erwartete_anteile(a, date(2027, 2, 15)) == 200
    a["geteilt"]["zeitraeume"][0]["personen"].append(a["geteilt"]["besetzung"][1])
    assert abos.erwartete_anteile(a, date(2027, 2, 15)) == 0      # jetzt nennt er auch Zwei
    assert abos.erwartete_anteile(a, date(2027, 3, 15)) == 200 + 300   # ohne Zeitraum beide


def test_the_share_grows_like_the_amount_at_the_contract():
    a = _abo(takt=12, faellig="2027-12-15", betrag_cents=-10_000,
             geteilt=_geteilt(zeitraeume=[_zr("2025-12", "2026-12")]))
    termin = date(2027, 12, 15)
    betrag = vt.vertragsbetrag(a, termin, mitte=MITTE, rate=0.02, police=())
    anteil = vt.anteil_am_termin(a, termin, mitte=MITTE, rate=0.02, police=())
    assert abs(anteil - 300 * betrag / -10_000) <= 1 and anteil > 300
    assert vt.anteil_am_termin(a, termin, mitte=MITTE, rate=0.02, police={"x"}) == 300
    assert vt.anteil_am_termin(a, termin, mitte=None, rate=0.02, police=()) == 300


def test_over_a_year_both_models_count_the_amount_minus_the_shares_once():
    a = _abo(betrag_cents=-1_000, geteilt=_geteilt(seit="2027-04"))
    v = jm.Vertrag(abo=a, block="fixkosten")
    termine = vt.termine(a, (), ab=date(2027, 1, 1), bis=date(2027, 12, 31))
    monatsmodell = sum(vt.vertragsbetrag(a, t, mitte=MITTE, rate=0.0, police=())
                       + vt.anteil_am_termin(a, t, mitte=MITTE, rate=0.0, police=())
                       for t in termine)
    assert _jahr(v, 2027) == monatsmodell == -1_000 * 12 + 200 * 9     # April bis Dezember


def test_the_year_calculation_names_the_share_as_its_own_item():
    a = _abo(betrag_cents=-1_000, geteilt=_geteilt(seit="2027-04"))
    posten = jm._vertragsposten((jm.Vertrag(abo=a, block="fixkosten"),), 2027, 0, MITTE, RATE)
    assert [p.cents for p in posten["fixkosten"]] == [-12_000, 1_800]
    assert "Anteil der Mitzahler" in posten["fixkosten"][1].label


def test_the_payments_of_those_who_pay_along_leave_the_measurement_and_name_the_account():
    conn = _db(("2026-11-20", 200, "Zwei", "abo/office", "m1", "b"),
               ("2026-12-20", 200, "Zwei", "abo/office", "m2", "c"),
               ("2026-12-21", 700, "Zwei", "abo/office", "m3", "d"))   # nicht der Anteil
    a = _abo(geteilt=_geteilt(seit="2026-11"))
    ausgenommen = vt.aus_der_messung(conn, [a])
    assert {"m1", "m2"} <= ausgenommen and "m3" not in ausgenommen
    assert abos.eingangskonto(conn, a) == "c"


def test_without_any_payment_the_share_has_no_account_of_its_own():
    conn = _db()
    assert abos.eingangskonto(conn, _abo(geteilt=_geteilt(seit="2026-11"))) is None
    assert abos.eingangskonto(conn, _abo()) is None


def _anteile(monkeypatch, conn, a, konto, **kw):
    monkeypatch.setattr(konten, "messfenster", lambda *args, **k: None)
    monkeypatch.setattr(konten, "_erster_offener_monat", lambda *args, **k: None)
    return konten._anteilsposten(conn, konto, [a], date(2027, 1, 1), date(2027, 3, 31), **kw)


def test_the_expected_share_lands_where_the_partners_paid_last(monkeypatch):
    conn = _db(("2026-12-20", 200, "Zwei", "abo/office", "m2", "c"))
    a = _abo(konto="a", geteilt=_geteilt(seit="2026-11"))
    assert [(o.month.month, o.amount_cents) for o in _anteile(monkeypatch, conn, a, "c")] == [
        (1, 200), (2, 200), (3, 200)]
    assert _anteile(monkeypatch, conn, a, "a") == []


def test_without_a_payment_the_share_lands_on_the_account_of_the_contract(monkeypatch):
    conn = _db()
    a = _abo(konto="a", geteilt=_geteilt(seit="2026-11"))
    assert len(_anteile(monkeypatch, conn, a, "a")) == 3
    assert _anteile(monkeypatch, conn, a, "c") == []


def test_a_pass_through_account_counts_on_the_covering_one(monkeypatch):
    conn = _db(("2026-12-20", 200, "Zwei", "abo/office", "m2", "durch"))
    a = _abo(konto="a", geteilt=_geteilt(seit="2026-11"))
    assert len(_anteile(monkeypatch, conn, a, "a", gedeckt={"durch"})) == 3
    assert _anteile(monkeypatch, conn, a, "a") == []


def test_a_paused_term_expects_no_share(monkeypatch):
    conn = _db()
    a = _abo(konto="a", geteilt=_geteilt(seit="2026-11"))
    pause = {"x": ((date(2027, 2, 1), date(2027, 2, 1)),)}
    assert [o.month.month for o in _anteile(monkeypatch, conn, a, "a", pausen=pause)] == [1, 3]


def test_a_pass_through_account_has_no_share_of_its_own(monkeypatch):
    conn = _db(("2026-12-20", 200, "Zwei", "abo/office", "m2", "durch"))
    a = _abo(konto="a", geteilt=_geteilt(seit="2026-11"))
    assert _anteile(monkeypatch, conn, a, "durch", durchlaufend={"durch"}) == []


def test_the_account_model_books_what_the_year_calculation_counts(monkeypatch):
    conn = _db(("2026-12-20", 200, "Zwei", "abo/office", "m2"))
    a = _abo(konto="a", betrag_cents=-1_000, geteilt=_geteilt(seit="2026-11"))
    monkeypatch.setattr(konten, "messfenster", lambda *args, **k: None)
    monkeypatch.setattr(konten, "_erster_offener_monat", lambda *args, **k: None)
    ab, bis = date(2027, 1, 1), date(2027, 12, 31)
    gebucht = sum(o.amount_cents for o in [
        *konten._vertragsposten(conn, "a", [a], ab, bis),
        *konten._anteilsposten(conn, "a", [a], ab, bis)])
    assert gebucht == _jahr(jm.Vertrag(abo=a, block="fixkosten"), 2027) == -12_000 + 12 * 200
