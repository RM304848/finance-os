"""Cashflow ohne das Objekt: dieselbe Abgrenzung gemessen und vorausgerechnet."""

from __future__ import annotations

import sqlite3
from datetime import date

from finctl.forecast import abgleich as ag
from finctl.forecast import ohne_objekt as ob

#: Eine Kategorie mit dem Merkmal `einmalig`, wie sie `mgmt_categories` liefert.
EINMALIG = frozenset({"immobilie/kaufnebenkosten"})

#: Erfundenes Objekt, wie CLAUDE.md es verlangt. Die Kennung ist zugleich die
#: Planklammer -- so heisst es in der Konfiguration, und der Test rechnet mit
#: dem, was er selbst mitgibt.
OBJEKT = "inselhaus"


def test_transfers_object_lines_and_purchases_do_not_count():
    assert ob.zaehlt("einkommen/gehalt", {"quelle": "annahme"}, OBJEKT)
    assert ob.zaehlt("loan:002", {"quelle": "vertrag"}, OBJEKT)
    # Geld zwischen eigenen Konten hebt sich im Haushalt auf: der Posten sagt es
    # selbst, sein Etikett gilt nichts.
    for label in ("budget:c24", "budget/zuweisung", "Auffüllung sparda-giro",
                  "Übertrag von dkb-giro"):
        assert not ob.zaehlt(label, {"quelle": "regel", "umbuchung": True}, OBJEKT), label
    assert ob.zaehlt("Auffüllung sparda-giro", {"quelle": "regel"}, OBJEKT)
    # Eine gemessene Umbuchung oder Anlage heisst wie ihre Kategorie.
    for label in ("transfer/eigenkonto", "investment/sparplan"):
        assert not ob.zaehlt(label, {"quelle": "gemessen"}, OBJEKT), label
    # Planzeilen: die Klammer des Objekts, Umbuchungen und Kaufraten fallen
    # heraus, eine echte Einnahme aus einer anderen Klammer zaehlt.
    assert not ob.zaehlt("Grundsteuer", {"quelle": "plan",
                                         "verweis": f"{OBJEKT}:2",
                                         "kategorie": "immobilie/nebenkosten"},
                         OBJEKT)
    assert not ob.zaehlt("X: Depot geleert", {"quelle": "plan", "verweis": "x:2",
                                              "kategorie": "transfer/eigenkonto"},
                         OBJEKT)
    assert not ob.zaehlt("X: Rate", {"quelle": "plan", "verweis": "x:0",
                                     "kategorie": "immobilie/kaufnebenkosten"},
                         OBJEKT, EINMALIG)
    assert ob.zaehlt("X: Nebenjob", {"quelle": "plan", "verweis": "x:3",
                                     "kategorie": "einkommen/gehalt-nebentaetig"},
                     OBJEKT)


def test_the_posts_of_an_object_with_a_forecast_do_not_count():
    """Miete und Kosten aus der Prognose des Objekts gehoeren nicht in den Cashflow ohne es --
    der Posten sagt es selbst, auch ohne Klammer; ein Posten ohne das Merkmal zaehlt."""
    for label in ("objekt-miete:haus", "objekt-kosten:haus"):
        assert not ob.zaehlt(label, {"quelle": "annahme", "objekt": True})
        assert not ob.zaehlt(label, {"quelle": "annahme", "objekt": True}, OBJEKT)
    assert ob.zaehlt("objekt-miete:haus", {"quelle": "annahme"})


def test_without_a_configured_bracket_plan_lines_still_count():
    """Ohne Objekt faellt nur heraus, was ohnehin kein Cashflow ist.

    Sonst haette eine frische Installation je nach Klammernamen ein
    zufaelliges Loch in der Kennzahl.
    """
    zeile = {"quelle": "plan", "verweis": f"{OBJEKT}:2",
             "kategorie": "immobilie/nebenkosten"}
    assert ob.zaehlt("Grundsteuer", zeile)
    assert not ob.zaehlt("X: Rate", {"quelle": "plan", "verweis": "x:0",
                                     "kategorie": "immobilie/kaufnebenkosten"},
                         einmalig=EINMALIG)
    # Ohne das Merkmal ist dieselbe Kategorie eine Ausgabe wie jede andere.
    assert ob.zaehlt("X: Rate", {"quelle": "plan", "verweis": "x:0",
                                 "kategorie": "immobilie/kaufnebenkosten"})


def test_the_forecast_sums_counting_items_across_accounts():
    views = [
        {"id": "dkb-giro",
         "herkunft": {"budget:c24": {"quelle": "regel", "umbuchung": True},
                      "familie/gemeinschaftskonto": {"quelle": "gemessen"},
                      "einkommen/gehalt": {"quelle": "annahme"}},
         "rows": [{"month": "2026-10-01", "detail": {
             "budget:c24": -5000, "familie/gemeinschaftskonto": -30000,
             "einkommen/gehalt": 300000}}]},
        {"id": "c24",
         "herkunft": {"budget/zuweisung": {"quelle": "regel", "umbuchung": True},
                      "abo/video": {"quelle": "gemessen"}},
         "rows": [{"month": "2026-10-01", "detail": {
             "budget/zuweisung": 5000, "abo/video": -1000}}]},
        {"id": "kaputt", "error": "x"},
    ]
    [monat] = ob.vorausgerechnet(views, OBJEKT, daneben="familie/gemeinschaftskonto")
    assert monat.monat == date(2026, 10, 1) and not monat.gemessen
    assert monat.cents == 300000 - 30000 - 1000
    assert monat.daneben_cents == -30000
    # Ohne Eintrag laeuft nichts daneben mit.
    [ohne] = ob.vorausgerechnet(views, OBJEKT)
    assert ohne.cents == monat.cents and ohne.daneben_cents == 0


def _ledger() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE statements (id INTEGER PRIMARY KEY, account_id TEXT,
            period_start TEXT, period_end TEXT, status TEXT);
        CREATE TABLE transactions (id INTEGER PRIMARY KEY, account_id TEXT,
            booking_date TEXT, dedup_hash TEXT);
        CREATE TABLE splits (transaction_id INTEGER, amount_cents INTEGER,
            mgmt_category_id TEXT, property_id TEXT);
        CREATE TABLE mgmt_categories (id TEXT PRIMARY KEY, fixkosten INTEGER,
            einmalig INTEGER);
        INSERT INTO mgmt_categories VALUES ('immobilie/kaufnebenkosten', 0, 1);
        INSERT INTO statements VALUES (1, 'dkb', '2026-07-01', '2026-08-31', 'imported');
    """)
    buchungen = [
        ("2026-07-28", 500000, "einkommen/gehalt", None),
        ("2026-07-03", -30000, "familie/gemeinschaftskonto", None),
        ("2026-07-10", -2000000, "immobilie/kaufnebenkosten", None),  # Kaufrate
        ("2026-07-31", 250000, "immobilie/mieteinnahme", OBJEKT),
        ("2026-07-15", -100000, "investment/wertpapier", None),
        ("2026-07-16", -300000, "transfer/eigenkonto", None),
        ("2026-08-28", 500000, "einkommen/gehalt", None),
        ("2026-08-03", -110000, "familie/gemeinschaftskonto", None),
        ("2026-08-12", -450000, "konsum/sonstiges", None),
    ]
    for i, (tag, cents, kat, objekt) in enumerate(buchungen, 1):
        conn.execute("INSERT INTO transactions VALUES (?,?,?,?)",
                     (i, "dkb", tag, f"h{i}"))
        conn.execute("INSERT INTO splits VALUES (?,?,?,?)", (i, cents, kat, objekt))
    return conn


def test_measured_months_leave_out_object_purchases_investments_and_transfers(
        monkeypatch):
    # Der Objektblock haengt an der Prognose in properties.yaml. Hier steht
    # das erfundene Objekt, sonst zaehlte die Miete als gewoehnliche
    # Mieteinnahme mit.
    monkeypatch.setattr(ag, "_objekt_block",
                        lambda: ag.Block(ag.OBJEKT, "Inselhaus",
                                         f"s.property_id = '{OBJEKT}'"))
    juli, august = ob.gemessen(_ledger(), 12, "familie/gemeinschaftskonto")
    assert (juli.monat, august.monat) == (date(2026, 7, 1), date(2026, 8, 1))
    assert juli.cents == 500000 - 30000
    assert juli.daneben_cents == -30000
    assert august.cents == 500000 - 110000 - 450000
    assert [m.daneben_cents for m in ob.gemessen(_ledger(), 12)] == [0, 0]
    k = ob.kennzahl(_ledger(), [], {"cashflow_ohne_objekt": {
        "label": "Inselhaus",
        "daneben": {"kategorie": "familie/gemeinschaftskonto", "label": "Nebenkasse",
                    "soll_cents": 30000}}})
    assert k["letzter"].cents == august.cents and k["gemessen_erreicht"] == 1
    assert k["daneben"] == {"kategorie": "familie/gemeinschaftskonto", "label": "Nebenkasse",
                            "soll_cents": 30000}
    assert k["daneben_schnitt_cents"] == -70000
    assert k["label"] == "Inselhaus"
    assert k["schnitt_prognose_cents"] is None


def test_without_a_daneben_there_is_none():
    """Ohne Eintrag in forecast.yaml gibt es kein Daneben: keine Karte, keine Linie."""
    assert ob.einstellungen({})["daneben"] is None
    assert ob.einstellungen({"cashflow_ohne_objekt": {"daneben": {"soll_cents": 5}}})[
        "daneben"] is None
    k = ob.kennzahl(_ledger(), [], {})
    assert k["daneben"] is None and k["daneben_schnitt_cents"] == 0
