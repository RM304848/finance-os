"""Schritt 5b, E.7: Kurzfristige Ziele, Notgroschen und der Anfangsstand.

Ein Ziel mit Stichtag im Horizont von `/konten` misst das Monatsmodell; der Notgroschen ist
die Untergrenze seines Kontos; ein Konto ohne Auszug nimmt in beiden Modellen denselben Stand.
Die Daten sind die des Haushalts (oder des Musterhaushalts); was ein Test braucht, liest er
aus `config/`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from finctl.forecast import notgroschen, ziel_monat, ziele


def _ziele_und_bestaende(conn):
    from finctl import bestaende
    from finctl.dateien import yaml_lesen

    goals = ziele.aus_spec(yaml_lesen("config/goals.yaml"))
    return goals, bestaende.zusammenfuehren(conn, bestaende.lesen(Path("config/balances.yaml")))


def _verbindung():
    if not Path("data/finance.db").exists():
        pytest.skip("kein Hauptbuch")
    from finctl.ledger.db import connect

    return connect()


# ------------------------------------------------------- der Horizont


def test_the_horizon_runs_from_the_month_after_the_cutoff_to_the_end_of_the_last_month():
    stichtag = date(2026, 9, 30)
    assert not ziel_monat.im_horizont(None, stichtag)
    assert not ziel_monat.im_horizont(date(2026, 9, 30), stichtag)
    assert ziel_monat.im_horizont(date(2026, 10, 1), stichtag)
    assert ziel_monat.im_horizont(date(2031, 9, 30), stichtag)
    assert not ziel_monat.im_horizont(date(2031, 10, 1), stichtag)
    assert ziel_monat.im_horizont(date(2027, 3, 31), stichtag, 6)
    assert not ziel_monat.im_horizont(date(2027, 4, 1), stichtag, 6)


def _view(konto: str, anfang: int, schluesse: list[int]) -> dict:
    return {"id": konto, "opening_cents": anfang, "rows": [
        {"month": f"2026-{10 + i:02d}-01", "closing_cents": c} for i, c in enumerate(schluesse)]}


def test_a_goal_is_measured_at_the_last_month_end_up_to_its_date():
    view = _view("a", 100, [200, 300, 400])
    assert ziel_monat._stand(view, date(2026, 10, 15)) == 100       # noch kein Monat zu Ende
    assert ziel_monat._stand(view, date(2026, 10, 31)) == 200
    assert ziel_monat._stand(view, date(2026, 12, 1)) == 300        # Ende November
    assert ziel_monat._stand(view, date(2026, 12, 31)) == 400


def _ziel(basis, due=date(2026, 12, 1), kennung="x"):
    return ziele.Progress(kennung, "X", 1_000_000, 0, due=due, basis=basis)


def _bestaende(*zeilen):
    return {"balances": [dict(z) for z in zeilen]}


def test_a_basis_the_monthly_model_does_not_project_stays_with_the_yearly_model():
    views = [_view("giro-a", 100, [200, 300, 400])]
    reichlich = _bestaende({"account_id": "giro-a", "kind": "giro", "cents": 1},
                           {"account_id": "depot-a", "kind": "depot", "cents": 5_000})
    assert ziel_monat.basiskonten(_ziel(("giro",)), reichlich, views) == ["giro-a"]
    assert ziel_monat.basiskonten(_ziel(("giro", "depot")), reichlich, views) is None
    # Ohne Basis zaehlt alles Liquide, und das Depot gehoert dazu.
    assert ziel_monat.basiskonten(_ziel(None), reichlich, views) is None
    # Eine Position ohne Wert wird, wie in `progress`, uebersprungen und nicht gezaehlt.
    ohne = _bestaende({"account_id": "giro-a", "kind": "giro"},
                      {"account_id": "depot-a", "kind": "depot", "cents": None})
    assert ziel_monat.basiskonten(_ziel(("giro", "depot")), ohne, views) == ["giro-a"]


def test_the_buffer_is_taken_off_a_goal_that_counts_the_savings_but_is_not_the_buffer():
    views = [_view("giro-a", 100, [20_000, 30_000, 40_000]),
             _view("spar-a", 100, [20_000, 30_000, 40_000])]
    best = _bestaende({"account_id": "giro-a", "kind": "giro", "cents": 1},
                      {"account_id": "spar-a", "kind": "tagesgeld", "cents": 1})
    ziel = _ziel(("giro", "tagesgeld"), due=date(2026, 12, 31))
    h = ziel_monat.hochgerechnet(ziel, best, views, puffer_cents=15_000)
    assert h.cents == 2 * 40_000 - 15_000
    puffer = _ziel(("giro", "tagesgeld"), due=date(2026, 12, 31), kennung=ziele.PUFFER_ZIEL)
    assert ziel_monat.hochgerechnet(puffer, best, views, puffer_cents=15_000).cents == 80_000
    assert ziel_monat.hochgerechnet(ziel, best, views, puffer_cents=None).cents == 80_000


def test_a_short_goal_is_the_sum_of_its_accounts_in_the_monthly_model():
    """Die Zahl auf der Karte ist der Stand der Basiskonten zum Stichtag im Monatsmodell."""
    conn = _verbindung()
    try:
        goals, merged = _ziele_und_bestaende(conn)
        lauf = ziel_monat.Lauf(conn)
        kurz = [p for p in ziele.progress(goals, merged) if lauf.misst(p)
                and ziel_monat.basiskonten(p, merged, lauf.views)]
        if not kurz:
            pytest.skip("kein Ziel mit Stichtag im Horizont und projizierter Basis")
        def stand(view, tag):
            vorher = [r for r in view["rows"]
                      if ziel_monat.monatsende(date.fromisoformat(r["month"])) <= tag]
            return vorher[-1]["closing_cents"] if vorher else view["opening_cents"]

        tagesgeld_konten = {str(z["account_id"]) for z in merged["balances"]
                            if ziele.TOPF.get(ziele.art(z.get("kind"))) == "tagesgeld"}
        puffer = ziele.puffer_cents(goals)
        for prog in kurz:
            konten = ziel_monat.basiskonten(prog, merged, lauf.views)
            erwartet = sum(stand(v, prog.due) for v in lauf.views if v["id"] in konten)
            toepfe = ziele.toepfe_fuer_basis(prog.basis) if prog.basis else None
            if (puffer and prog.goal_id != ziele.PUFFER_ZIEL
                    and (not toepfe or "tagesgeld" in toepfe)):
                tagesgeld = sum(stand(v, prog.due) for v in lauf.views
                                if v["id"] in tagesgeld_konten)
                erwartet -= min(max(tagesgeld, 0), puffer)
            h, modell = ziel_monat.messen(prog, None, merged, puffer, lauf)
            assert modell == ziel_monat.MONATSMODELL
            assert h.cents == erwartet
    finally:
        conn.close()


def test_a_goal_beyond_the_horizon_is_measured_by_the_yearly_model():
    conn = _verbindung()
    try:
        _, merged = _ziele_und_bestaende(conn)
        lauf = ziel_monat.Lauf(conn)
        spaet = _ziel(("giro",), due=date(lauf.stichtag.year + 20, 1, 1))
        assert not lauf.misst(spaet)

        class Jahresrechnung:
            years = ()

        assert ziel_monat.messen(spaet, Jahresrechnung, merged, None, lauf) == (
            None, ziel_monat.JAHRESRECHNUNG)
    finally:
        conn.close()


# --------------------------------------------------------- der Notgroschen


def test_the_buffer_account_is_the_savings_account_or_the_one_the_operating_account_sweeps_to():
    best = _bestaende({"account_id": "giro-a", "kind": "giro"},
                      {"account_id": "spar-a", "kind": "tagesgeld"})
    assert notgroschen.konto_des_notgroschens(best, None) == "spar-a"
    assert notgroschen.konto_des_notgroschens(best, "giro-a") == "spar-a"
    zwei = _bestaende({"account_id": "spar-a", "kind": "tagesgeld"},
                      {"account_id": "spar-b", "kind": "tagesgeld"})
    assert notgroschen.konto_des_notgroschens(zwei, "spar-b") == "spar-b"
    assert notgroschen.konto_des_notgroschens(zwei, None) is None
    assert notgroschen.konto_des_notgroschens(_bestaende({"account_id": "g", "kind": "giro"}),
                                              None) is None


def test_the_floor_is_the_higher_of_the_rule_and_the_buffer(monkeypatch):
    from finctl.forecast import konten

    monkeypatch.setattr(konten, "_floor_for", lambda *a, **k: 20_000)
    monkeypatch.setattr(konten._ng, "untergrenze", lambda konto, fcfg: 50_000)
    assert konten._untergrenze("k", {}, None) == 50_000
    monkeypatch.setattr(konten._ng, "untergrenze", lambda konto, fcfg: 10_000)
    assert konten._untergrenze("k", {}, None) == 20_000
    monkeypatch.setattr(konten._ng, "untergrenze", lambda konto, fcfg: 0)
    assert konten._untergrenze("k", {}, None) == 20_000


def test_the_buffer_limit_is_the_floor_of_its_account_in_the_forecast():
    from finctl.forecast.konten import _operating_account, forecast_config, household_accounts

    conn = _verbindung()
    try:
        goals, merged = _ziele_und_bestaende(conn)
        grenze = ziele.puffer_cents(goals)
        fcfg = forecast_config()
        betrieb = (fcfg.get("account_roles") or {}).get(_operating_account(fcfg)) or {}
        konto = notgroschen.konto_des_notgroschens(merged, betrieb.get("sweep_to"))
        if not grenze or konto is None:
            pytest.skip("kein Notgroschen auf einem einzelnen Konto")
        views = {v["id"]: v for v in household_accounts(conn, months=12)}
        v = views[konto]
        assert v["dispo_threshold_cents"] == max(grenze, v["regel_untergrenze_cents"])
        assert v["notgroschen_cents"] == grenze
        # Ein anderes Konto behaelt seine Untergrenze.
        for kennung, andere in views.items():
            if kennung != konto and not andere.get("error"):
                assert andere["notgroschen_cents"] is None
                assert andere["dispo_threshold_cents"] == andere["regel_untergrenze_cents"]
    finally:
        conn.close()


# ----------------------------------------------------------- der Anfangsstand


def _kleine_datenbank(tmp_path):
    from finctl.ledger.db import connect, init_db

    conn = connect(init_db(tmp_path / "t.db"))
    conn.execute("INSERT INTO accounts (id, display_name, institution, account_type, "
                 "ingest_mode, parser_profile) VALUES ('neu', 'Neu', 'X', 'giro', 'parsed', 'p')")
    return conn


def test_an_account_without_a_statement_takes_the_latest_stand_up_to_the_cutoff_in_both_models(
        tmp_path):
    from finctl import bestaende
    from finctl.forecast import konten
    from finctl.forecast.stichtag import stichtag

    conn = _kleine_datenbank(tmp_path)
    try:
        ende = stichtag(conn)
        frueh, spaet, danach = (date(ende.year - 1, 1, 15), date(ende.year, ende.month, 1),
                                date(ende.year + 1, 1, 1))
        for tag, cents in ((frueh, 1_000), (spaet, 2_500), (danach, 9_900)):
            conn.execute("INSERT INTO balance_snapshots (account_id, as_of, balance_cents, "
                         "source) VALUES ('neu', ?, ?, 'manual')", (tag.isoformat(), cents))
        jahresrechnung = bestaende.auszugsstaende(conn, ["neu"])["neu"]
        assert (jahresrechnung["cents"], jahresrechnung["as_of"]) == (2_500, spaet.isoformat())
        assert jahresrechnung["auszug_bis"] == ""
        monatsmodell = konten.account_forecast(conn, "neu", months=2)
        assert monatsmodell["opening_cents"] == 2_500
        conn.execute("DELETE FROM balance_snapshots WHERE as_of <= ?", (spaet.isoformat(),))
        assert bestaende.auszugsstaende(conn, ["neu"])["neu"]["cents"] is None
        assert konten.account_forecast(conn, "neu", months=2)["opening_cents"] == 0
    finally:
        conn.close()


def test_a_stand_after_the_cutoff_counts_in_no_model(tmp_path):
    from finctl import bestaende
    from finctl.forecast import konten
    from finctl.forecast.stichtag import stichtag

    conn = _kleine_datenbank(tmp_path)
    try:
        ende = stichtag(conn)
        conn.execute("INSERT INTO balance_snapshots (account_id, as_of, balance_cents, source) "
                     "VALUES ('neu', ?, 7700, 'manual')",
                     (date.fromordinal(ende.toordinal() + 1).isoformat(),))
        assert bestaende.auszugsstaende(conn, ["neu"])["neu"]["cents"] is None
        assert konten.account_forecast(conn, "neu", months=2)["opening_cents"] == 0
    finally:
        conn.close()


def test_an_account_with_a_statement_ignores_the_typed_stand(tmp_path):
    from finctl import bestaende
    from finctl.forecast.stichtag import stichtag

    conn = _kleine_datenbank(tmp_path)
    try:
        ende = stichtag(conn)
        conn.execute("INSERT INTO balance_snapshots (account_id, as_of, balance_cents, source) "
                     "VALUES ('neu', ?, 4000, 'manual')", (ende.isoformat(),))
        conn.execute(
            "INSERT INTO statements (account_id, source_path, source_name, file_sha256, "
            "period_start, period_end, balance_start_cents, balance_end_cents, parser_profile, "
            "parser_version, status, imported_at) "
            "VALUES ('neu', 'p', 'n', 'h', ?, ?, 0, 100, 'p', '1', 'imported', '2026-01-01')",
            (ende.replace(day=1).isoformat(), ende.isoformat()))
        stand = bestaende.auszugsstaende(conn, ["neu"])["neu"]
        assert stand["cents"] == 100 and stand["auszug_bis"] == ende.isoformat()
    finally:
        conn.close()
