"""Die Seite /prognosebasis rechnet nichts: ihre Beträge sind die Posten der Rechnungen.

Jede Zeile ist die Summe der Posten, die das Monatsmodell im ersten Monat und die
Jahresrechnung im ersten vollen Jahr selbst bilden. Der Test ordnet diese Posten ein
zweites Mal, nach dem Etikett und dem Block statt nach der Herkunft, und vergleicht:
Summe über alle Zeilen, dann Zeile für Zeile, wo das Etikett die Zeile sagt.
"""

from __future__ import annotations

import pytest

from finctl import ops
from finctl.forecast import jahre as jm
from finctl.forecast import quellen as qn
from finctl.ledger import db as ledger
from finctl.pfade import DB_PATH
from finctl.web.routen.annahmen import eingaben_der_hochrechnung

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="kein Hauptbuch")

_VERTRAG = ("abo:", "abo-anteil:", "abo-zurueck:")


@pytest.fixture(scope="module")
def lauf():
    """Die Rechnungen, wie die Seite sie liest -- aber die Kontoprognose über den ganzen
    Horizont von /konten, nicht über zwölf Monate."""
    e = eingaben_der_hochrechnung()
    jahr = e.monat.base_year + (1 if e.monat.vergangen else 0)
    projektion = jm.rechnen(e, end_year=jahr)
    conn = ledger.connect(DB_PATH)
    try:
        views = ops.household_accounts(conn, months=ops.HORIZON_DEFAULT)
        yield {"views": views, "projektion": projektion, "jahr": jahr,
               "seite": qn.bauen(conn, views, projektion, jahr)}
    finally:
        conn.close()


def _erste_monate(views):
    """(Etikett, Betrag, Herkunft) des ersten Monats, ohne Geld zwischen eigenen Konten."""
    for v in views:
        if v.get("error") or not v["rows"]:
            continue
        for label, cents in v["rows"][0]["detail"].items():
            herkunft = v["herkunft"][label]
            if not herkunft.get("umbuchung"):
                yield label, cents, herkunft


def _summe(seite, art: str) -> int:
    return sum(getattr(z, art) or 0 for z in seite.zeilen)


def _zeile(seite, schluessel: str):
    return next((z for z in seite.zeilen if z.schluessel == schluessel), None)


def test_the_monthly_column_is_the_sum_of_the_first_month_of_all_accounts(lauf):
    soll = sum(c for _, c, _ in _erste_monate(lauf["views"]))
    assert _summe(lauf["seite"], "monat_cents") == soll


def test_the_yearly_column_is_the_blocks_of_the_year_plus_the_interest_of_the_pot(lauf):
    jahr = next(y for y in lauf["projektion"].years if y.year == lauf["jahr"])
    zinsen = sum(p.cents for p in jahr.posten.get("rendite", []) if p.verweis == "tagesgeld")
    assert _summe(lauf["seite"], "jahr_cents") == sum(jahr.blocks.values()) + zinsen


def test_a_row_the_label_names_is_the_sum_of_its_postings(lauf):
    posten = list(_erste_monate(lauf["views"]))
    seite = lauf["seite"]

    def monat(schluessel):
        return getattr(_zeile(seite, schluessel), "monat_cents", None)

    assert monat(qn.KREDIT) == sum(c for lb, c, _ in posten if lb.startswith("loan:")) or (
        monat(qn.KREDIT) is None and not any(lb.startswith("loan:") for lb, _, _ in posten))
    vertraege = sum(c for lb, c, _ in posten if lb.startswith(_VERTRAG))
    assert (monat(qn.VERTRAEGE) or 0) == vertraege
    assert (monat(qn.ZINSEN) or 0) == sum(c for lb, c, _ in posten if lb in jm.GERECHNET)
    assert (monat(qn.OBJEKTE) or 0) == sum(c for _, c, h in posten if h.get("objekt"))
    assert (monat(qn.GEHALT) or 0) == sum(c for lb, c, _ in posten if lb == "einkommen/gehalt")


def test_a_row_the_block_names_is_the_block_of_the_year(lauf):
    jahr = next(y for y in lauf["projektion"].years if y.year == lauf["jahr"])
    seite = lauf["seite"]
    for schluessel in (qn.GEHALT, qn.MIETE, qn.KREDIT, qn.IMMOBILIE, qn.KONSUM, qn.STEUERN,
                       qn.OBJEKTE, qn.RENTE):
        zeile = _zeile(seite, schluessel)
        assert (zeile.jahr_cents if zeile else 0) in (None, jahr.blocks.get(schluessel, 0)), (
            schluessel)


def test_contracts_are_the_postings_with_a_contract_reference_in_the_year(lauf):
    jahr = next(y for y in lauf["projektion"].years if y.year == lauf["jahr"])
    soll = sum(p.cents for b, ps in jahr.posten.items() if b not in qn._KEINE_BASIS
               for p in ps if str(p.verweis or "").startswith("abo:"))
    assert (getattr(_zeile(lauf["seite"], qn.VERTRAEGE), "jahr_cents", None) or 0) == soll


def test_every_posting_of_a_row_comes_from_a_source_the_row_allows(lauf):
    """Eine Zeile mit einer Quelle, die nicht zu ihr gehört, ist eine falsche Zuordnung."""
    conn = ledger.connect(DB_PATH)
    try:
        zuordnung = qn.Zuordnung(conn)
        for v in lauf["views"]:
            if v.get("error"):
                continue
            for label, h in v["herkunft"].items():
                zeile = zuordnung.von(label, h)
                if zeile is not None and h["quelle"] not in qn.ERLAUBT[zeile]:
                    pytest.fail(f"{zeile}: Quelle {h['quelle']} im Monatsmodell")
    finally:
        conn.close()
    jahr = next(y for y in lauf["projektion"].years if y.year == lauf["jahr"])
    erwartet = qn.erwartete_zeilen()
    for block, posten in jahr.posten.items():
        if block in qn._KEINE_BASIS:
            continue
        for p in posten:
            zeile = qn._zeile_im_jahr(block, p, erwartet)
            assert p.quelle in qn.ERLAUBT.get(zeile, set()), (
                f"{zeile}: Quelle {p.quelle} in der Jahresrechnung")


def test_the_page_reads_the_same_first_year_as_the_long_calculation(lauf):
    """Die Seite rechnet nur bis zum ersten Jahr; das darf keine Zahl dieses Jahres ändern."""
    e = eingaben_der_hochrechnung()
    lang = jm.rechnen(e, end_year=lauf["jahr"] + 12)
    kurz = next(y for y in lauf["projektion"].years if y.year == lauf["jahr"])
    lang_jahr = next(y for y in lang.years if y.year == lauf["jahr"])
    assert kurz.blocks == lang_jahr.blocks


def test_the_first_year_is_a_whole_year(lauf):
    e = eingaben_der_hochrechnung()
    assert lauf["jahr"] == e.monat.base_year + (1 if e.monat.vergangen else 0)
    assert lauf["jahr"] > e.monat.base_year or not e.monat.vergangen


def test_a_row_without_postings_in_one_calculation_has_no_source_there(lauf):
    for z in lauf["seite"].zeilen:
        assert (z.monat_cents is None) == (z.quelle_monat is None), z.schluessel
        assert (z.jahr_cents is None) == (z.quelle_jahr is None), z.schluessel


def test_the_window_in_the_source_is_the_window_the_calculations_measure(lauf):
    conn = ledger.connect(DB_PATH)
    try:
        from finctl.forecast import abgleich as ag

        f = ag.fenster(conn)
    finally:
        conn.close()
    if f is None:
        pytest.skip("kein vollständiger Monat")
    assert lauf["seite"].fenster == f"{f.von:%Y-%m} bis {f.bis:%Y-%m}"
    gemessen = [h["herleitung"] for v in lauf["views"] if not v.get("error")
                for h in v["herkunft"].values()
                if h["quelle"] == "gemessen" and "vollständige Monate" in h["herleitung"]]
    if gemessen:
        assert all(f"über {f.monate} vollständige Monate" in t for t in gemessen)


def test_a_source_both_calculations_share_stands_once_on_the_page():
    """Gleich ist, was beide mit demselben Text nennen -- dann steht es einmal da."""
    gleich = qn.Zeile("x", "X", 1, 2, "Q", "Q", "/", "Ort")
    verschieden = qn.Zeile("y", "Y", 1, 2, "Q1", "Q2", "/", "Ort")
    allein = qn.Zeile("z", "Z", None, 2, None, "Q", "/", "Ort")
    assert gleich.gleiche_quelle
    assert not verschieden.gleiche_quelle
    assert not allein.gleiche_quelle


def test_the_page_names_a_shared_source_once_and_a_different_one_twice():
    from fastapi.testclient import TestClient

    from finctl.web import server as srv

    html = TestClient(srv.app).get("/prognosebasis").text
    zeilen = html.split("</table>")[0].split("<tr>")[2:]
    assert zeilen, "keine Zeile der Seite"
    for zeile in zeilen:
        if "<td>" not in zeile:
            continue
        if zeile.count("klein\">Monatsmodell</span>") == 1:
            assert zeile.count("klein\">Jahresrechnung</span>") == 1, zeile[:200]
        else:
            assert "klein\">Jahresrechnung</span>" not in zeile
