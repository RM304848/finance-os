"""Der Treffer-Check rechnet nach, was die Prognose am Vormonatsende gesagt haette.

Zwei Eigenschaften machen ihn aussagekraeftig. Ein Ledger, das jeden Monat
dasselbe bucht, muss exakt getroffen werden -- sonst misst der Check sich
selbst. Und das Fenster darf keine Buchung aus dem Monat enthalten, den es
vorhersagt, sonst ist jeder Treffer geschummelt.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from finctl.forecast import abgleich as ag
from finctl.forecast import treffer as tr
from finctl.ledger.db import connect, init_db


@pytest.fixture
def konstant(tmp_path):
    """Vierzehn Monate mit identischen Buchungen: Miete, Konsum, Fixkosten."""
    pfad = init_db(tmp_path / "t.db")
    c = connect(pfad)
    c.execute("INSERT INTO accounts (id, display_name, institution, account_type, "
              "ingest_mode, parser_profile) VALUES ('a','A','X','giro','parsed','p')")
    for kid, kind, fix in (("wohnen", "expense", 0), ("wohnen/miete", "expense", 1),
                           ("konsum", "expense", 0), ("konsum/sonstiges", "expense", 0),
                           ("einkommen", "income", 0), ("einkommen/zinsen", "income", 0)):
        c.execute("INSERT INTO mgmt_categories (id, parent_id, name, kind, fixkosten) "
                  "VALUES (?,?,?,?,?)", (kid, kid.split("/")[0] if "/" in kid else None,
                                         kid, kind, fix))
    monat = date(2025, 1, 1)
    n = 0
    for i in range(14):
        m = ag._plus_monate(monat, i)
        ende = ag._month_end(m)
        sid = c.execute(
            "INSERT INTO statements (account_id, source_path, source_name, file_sha256, "
            "period_start, period_end, balance_start_cents, balance_end_cents, "
            "parser_profile, parser_version, status, imported_at) "
            "VALUES ('a','x','x',?,?,?,0,0,'p','1','imported','now')",
            (f"sha{i}", m.isoformat(), ende.isoformat())).lastrowid
        for tag, cents, kat in ((1, -90000, "wohnen/miete"), (10, -25000, "konsum/sonstiges"),
                                (20, 1500, "einkommen/zinsen")):
            n += 1
            tid = c.execute(
                "INSERT INTO transactions (account_id, statement_id, booking_date, "
                "amount_cents, raw_text, seq_in_statement, dedup_hash, created_at) "
                "VALUES ('a',?,?,?,'x',?,?,'now')",
                (sid, m.replace(day=tag).isoformat(), cents, n, f"h{n}")).lastrowid
            c.execute("INSERT INTO splits (transaction_id, amount_cents, mgmt_category_id, "
                      "source, created_at, updated_at) VALUES (?,?,?,'rule','now','now')",
                      (tid, cents, kat))
    c.commit()
    yield c
    c.close()


def test_a_constant_ledger_is_hit_exactly(konstant):
    monate = tr.letzte_monate(konstant, 3)
    assert monate[-1] == date(2026, 2, 1)
    for m in tr.jahresbasis(konstant, monate, plaene=[], objekt_cents=lambda _m: 0):
        for block in ("miete", "fixkosten", "konsum", "einkommen_sonst", "immobilie"):
            assert m.delta(block) == 0, (m.monat, block, m.soll, m.ist)
        assert m.unvorhersehbar_cents == 0


def test_the_window_never_contains_the_month_it_predicts(konstant):
    m = date(2026, 2, 1)
    f = tr.fenster_vor(konstant, m)
    assert f.bis < m
    assert f.monate == 12
    # Eine Ausreisserbuchung IM Zielmonat darf die Prognose nicht bewegen.
    tid = konstant.execute(
        "INSERT INTO transactions (account_id, statement_id, booking_date, amount_cents, "
        "raw_text, seq_in_statement, dedup_hash, created_at) "
        "VALUES ('a',1,'2026-02-15',-500000,'x',99,'ausreisser','now')").lastrowid
    konstant.execute("INSERT INTO splits (transaction_id, amount_cents, mgmt_category_id, "
                     "source, created_at, updated_at) "
                     "VALUES (?,-500000,'konsum/sonstiges','rule','now','now')", (tid,))
    [eintrag] = tr.jahresbasis(konstant, [m], plaene=[], objekt_cents=lambda _m: 0)
    assert eintrag.soll["konsum"] == -25000
    assert eintrag.delta("konsum") == -500000


def test_the_account_derivation_stops_before_the_cut_off(konstant):
    from finctl.forecast import engine as fc

    tid = konstant.execute(
        "INSERT INTO transactions (account_id, statement_id, booking_date, amount_cents, "
        "raw_text, seq_in_statement, dedup_hash, created_at) "
        "VALUES ('a',1,'2026-02-15',-500000,'x',99,'spaet','now')").lastrowid
    konstant.execute("INSERT INTO splits (transaction_id, amount_cents, mgmt_category_id, "
                     "source, created_at, updated_at) "
                     "VALUES (?,-500000,'konsum/sonstiges','rule','now','now')", (tid,))
    mit = fc.derive_recurring(konstant, "a", since="2025-08-01", escalation_pa=0.0)
    bis = fc.derive_recurring(konstant, "a", since="2025-08-01", escalation_pa=0.0,
                              until="2026-01-31")
    assert {i.measured_until for i in mit} == {date(2026, 2, 1)}
    assert {i.measured_until for i in bis} == {date(2026, 1, 1)}
    assert {i.label: i.amount_cents for i in bis}["konsum/sonstiges"] == -25000


def test_the_actual_of_an_account_leaves_out_what_no_derivation_describes(konstant):
    """Umbuchung (Praefix oder Art), Investment, Einmaliges sowie Zinsen und Kapitalertragsteuer
    (die rechnet das Konto aus seinem Stand) zaehlen im Ist nicht; Kreditbuchungen nur, wenn das
    Soll sie auch nicht hat."""
    for kid, kind in (("transfer/eigenkonto", "transfer"), ("investment/depot", "expense"),
                      ("immobilie/kaufnebenkosten", "expense"), ("kredit/rate", "expense"),
                      ("konsum/umschichtung", "transfer")):
        konstant.execute("INSERT INTO mgmt_categories (id, name, kind, einmalig) "
                         "VALUES (?,?,?,?)",
                         (kid, kid, kind, int(kid == "immobilie/kaufnebenkosten")))
    for n, (kat, cents) in enumerate((
            ("transfer/eigenkonto", -1000), ("investment/depot", -2000),
            ("immobilie/kaufnebenkosten", -3000), ("kredit/rate", -4000),
            ("konsum/umschichtung", -5000)), start=100):
        tid = konstant.execute(
            "INSERT INTO transactions (account_id, statement_id, booking_date, amount_cents, "
            "raw_text, seq_in_statement, dedup_hash, created_at) "
            f"VALUES ('a',1,'2026-02-28',{cents},'x',{n},'u{n}','now')").lastrowid
        konstant.execute("INSERT INTO splits (transaction_id, amount_cents, mgmt_category_id, "
                         "source, created_at, updated_at) "
                         "VALUES (?,?,?,'rule','now','now')", (tid, cents, kat))
    zeilen = tr._ist_je_konto(konstant, date(2026, 2, 1), ["a"], {})["a"]
    mit = sum(z.cents for z in zeilen if tr._ist_zaehlt(z, False))
    ohne = sum(z.cents for z in zeilen if tr._ist_zaehlt(z, True))
    # Miete und Konsum des Monats, dazu die Kreditbuchung; die Zinsen des Monats fehlen.
    assert mit == -90000 - 25000 - 4000
    assert ohne == -90000 - 25000


@pytest.mark.skipif(not Path("data/finance.db").exists(), reason="no ledger present")
def test_the_check_runs_on_the_real_ledger():
    c = connect()
    try:
        r = tr.pruefen(c, 3)
    finally:
        c.close()
    assert len(r["jahres"]) == 3
    for j in r["jahres"]:
        assert j.sparrate_soll or j.sparrate_ist


def _miete_als_vertrag(konstant, monkeypatch):
    """Die Miete des Ledgers (14 Buchungen, h1, h4, ...) als Vertrag, ohne Steigerung."""
    from finctl import abos
    from finctl.forecast import konten as ops

    hashes = [r[0] for r in konstant.execute(
        "SELECT t.dedup_hash FROM transactions t JOIN splits s ON s.transaction_id = t.id "
        "WHERE s.mgmt_category_id = 'wohnen/miete'")]
    vertrag = abos.normalisieren({
        "id": "miete", "name": "Miete", "kategorie": "wohnen/miete", "konto": "a",
        "betrag_cents": -90000, "takt": 1, "faellig": "2026-03-01", "buchungen": hashes})
    monkeypatch.setattr(abos, "alle_vertraege", lambda: [vertrag])
    monkeypatch.setattr(ops, "steigerung", lambda _=None: 0.0)


def test_a_contract_is_its_own_item_in_the_year_base(konstant, monkeypatch):
    """Soll aus dem Termin, Ist aus den Buchungen, die der Vertrag ersetzt -- und der Block, in
    dem die Miete stand, misst sie nicht mehr."""
    _miete_als_vertrag(konstant, monkeypatch)
    [m] = tr.jahresbasis(konstant, [date(2026, 2, 1)], plaene=[], objekt_cents=lambda _m: 0)
    assert (m.soll[tr.VERTRAEGE], m.ist[tr.VERTRAEGE]) == (-90000, -90000)
    assert m.soll["fixkosten"] == 0 and m.ist["fixkosten"] == 0
    assert m.delta(tr.VERTRAEGE) == 0


def test_a_contract_is_its_own_item_per_account(konstant, monkeypatch):
    _miete_als_vertrag(konstant, monkeypatch)
    [k] = [z for z in tr.konten(konstant, [date(2026, 2, 1)]) if z.konto == "a"]
    assert (k.vertrag_soll_cents, k.vertrag_ist_cents) == (-90000, -90000)
    assert k.objekt_soll_cents == k.objekt_ist_cents == 0


def test_the_agreed_share_of_a_period_counts_in_the_forecast_of_a_contract(konstant, monkeypatch):
    """Ein angelegter Zeitraum: Das Ist hat die Zahlungen der Mitzahler, also hat das Soll den
    vereinbarten Anteil -- auf die Termine des Zeitraums verteilt, nie den offenen Rest."""
    from finctl import abos
    from finctl.forecast import konten as ops

    vertrag = abos.normalisieren({
        "id": "tarif", "name": "Tarif", "kategorie": "wohnen/miete", "konto": "a",
        "betrag_cents": -30000, "takt": 1, "faellig": "2026-06-01", "buchungen": [],
        "geteilt": {"zeitraeume": [{"von": "2026-01", "bis": "2026-04", "einsammeln": "2026-05",
                                    "personen": [{"name": "Eine", "anteil_cents": 9000},
                                                 {"name": "Andere", "anteil_cents": 3000}]}]}})
    monkeypatch.setattr(abos, "alle_vertraege", lambda: [vertrag])
    monkeypatch.setattr(ops, "steigerung", lambda _=None: 0.0)
    # Drei Termine (Januar bis Maerz) teilen 12.000: je 4.000.
    assert tr._zeitraumanteil(vertrag, date(2026, 2, 1)) == 4000
    assert tr._zeitraumanteil(vertrag, date(2026, 4, 1)) == 0       # das Ende gehoert dem naechsten
    soll = tr._vertragssoll(konstant, [vertrag], date(2026, 2, 1), {}, ())
    assert soll == {"a": -30000 + 4000}
