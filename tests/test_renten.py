"""Rentenquellen: eine Datei, `renten.yaml`, mit Notiz, Betrag und Stand je Quelle.
Alle Quellen hier sind erfunden."""

from __future__ import annotations

import os
from datetime import date

import pytest
import yaml

from finctl import renten

BASIS = """renten:
  - id: drv
    name: Gesetzliche Rente
    art: rente
    kaufkraft: heute
    cents: 150000
    ab: 2050-01
    stand: 2026-02-01
    notiz: Die Herleitung, die kein Klick loeschen darf.
  - id: police
    name: Fondspolice
    art: kapital
    kaufkraft: nominal
    cents: 5000000
    ab: 2045-06
"""


def _config(tmp_path):
    (tmp_path / "renten.yaml").write_text(BASIS, encoding="utf-8")
    return tmp_path


def test_todays_money_is_grown_to_the_start_nominal_stays(tmp_path):
    """Die DRV rechnet ohne Rentenanpassungen, eine Standmitteilung meist
    nominal. Gewandelt wird beim Rechnen, nicht in der Quelle."""
    drv, police = renten.quellen(_config(tmp_path))
    assert renten.nominal_cents(drv, 2026, 0.02) == 150000
    # 24 Jahre bei 2 %: Faktor 1,61.
    assert renten.nominal_cents(drv, 2050, 0.02) == round(150000 * 1.02 ** 24)
    assert renten.nominal_cents(police, 2045, 0.02) == 5000000


def test_a_letter_is_current_in_its_year(tmp_path):
    drv, police = renten.quellen(_config(tmp_path))
    assert drv.aktuell(date(2026, 9, 1)) and not drv.aktuell(date(2027, 1, 1))
    assert not police.aktuell(date(2026, 9, 1))      # ohne Stand


def test_the_monthly_close_writes_the_whole_entry_into_the_one_file(tmp_path):
    cfg = _config(tmp_path)
    vorher = (cfg / "renten.yaml").read_bytes()
    # Dasselbe noch einmal: die Datei bleibt, wie sie ist -- auch wenn sie das Datum als
    # Datum fuehrt und die Eingabe es als Text schickt.
    renten.setzen("drv", {"cents": 150000, "stand": "2026-02-01"}, cfg)
    assert (cfg / "renten.yaml").read_bytes() == vorher

    renten.setzen("drv", {"cents": 160000, "stand": "2026-03-01"}, cfg)
    drv = renten.quellen(cfg)[0]
    assert (drv.cents, drv.stand) == (160000, date(2026, 3, 1))
    assert "Die Herleitung" in drv.notiz
    assert not (cfg / "renten_custom.yaml").exists()
    roh = yaml.safe_load((cfg / "renten.yaml").read_text(encoding="utf-8"))
    assert [e["id"] for e in roh["renten"]] == ["drv", "police"]
    assert roh["renten"][1]["cents"] == 5000000          # die andere Quelle bleibt


def test_without_its_own_date_a_pension_starts_with_retirement(tmp_path, monkeypatch):
    from finctl import person

    monkeypatch.setattr(person, "rentenbeginn", lambda: date(2061, 3, 1))
    q = renten.Quelle(id="x", name="x", art="rente", cents=1)
    assert renten.beginn(q) == date(2061, 3, 1)


def test_a_start_that_is_handed_in_is_not_read_again(monkeypatch):
    """Wer viele Quellen fragt, liest den Rentenbeginn einmal -- auch wenn er
    fehlt: `None` ist eine Antwort, kein Grund, noch einmal zu lesen."""
    from finctl import person

    def verboten():
        raise AssertionError("der Rentenbeginn wurde noch einmal gelesen")

    monkeypatch.setattr(person, "rentenbeginn", verboten)
    ohne = renten.Quelle(id="x", name="x", art="rente", cents=1)
    mit = renten.Quelle(id="y", name="y", art="rente", cents=1, ab=date(2050, 1, 1))
    assert renten.beginn(ohne, date(2061, 3, 1)) == date(2061, 3, 1)
    assert renten.beginn(ohne, None) is None
    assert renten.beginn(mit, date(2061, 3, 1)) == date(2050, 1, 1)


@pytest.mark.parametrize("felder", [{"cents": -1}, {"stand": "2999-01-01"}])
def test_wrong_input_is_refused(tmp_path, felder):
    with pytest.raises(ValueError):
        renten.setzen("drv", felder, _config(tmp_path))


def test_the_payout_start_is_chosen_in_the_monthly_close(tmp_path):
    """Eine Police zahlt oft wahlweise ab 62 oder ab 67: das "Bezug ab" traegt
    man selbst ein. Leer heisst Rentenbeginn aus der Einrichtung."""
    cfg = _config(tmp_path)
    renten.setzen("police", {"ab": "2050-02"}, cfg)
    assert renten.quellen(cfg)[1].ab == date(2050, 2, 1)
    renten.setzen("police", {"ab": ""}, cfg)
    assert renten.quellen(cfg)[1].ab is None
    with pytest.raises(ValueError):
        renten.setzen("police", {"ab": "62"}, cfg)


# -------------------------------------------------- anlegen, Effektivkosten

def test_a_newcomer_creates_a_pension_without_any_file(tmp_path):
    """Ohne renten.yaml legt die erste Rente die Datei an, immer nominal."""
    kennung = renten.anlegen({"name": "Gesetzliche Rente", "art": "rente",
                              "cents": 150_000}, tmp_path)
    [q] = renten.quellen(tmp_path)
    assert (q.id, q.kaufkraft, q.cents) == (kennung, "nominal", 150_000)
    assert kennung == "gesetzliche-rente"
    assert (tmp_path / "renten.yaml").exists() and not (tmp_path / "renten_custom.yaml").exists()


def test_a_created_pension_takes_amount_updates_and_can_be_deleted(tmp_path):
    kennung = renten.anlegen({"name": "Police", "art": "kapital", "cents": 5_000_000,
                              "ab": "2050-01", "kosten_pa": 0.018}, tmp_path)
    renten.setzen(kennung, {"cents": 5_500_000}, tmp_path)
    [q] = renten.quellen(tmp_path)
    assert (q.cents, q.ab, q.kosten_pa) == (5_500_000, date(2050, 1, 1), 0.018)
    renten.loeschen(kennung, tmp_path)
    assert renten.quellen(tmp_path) == []


def test_any_pension_can_be_taken_out_of_the_file_and_an_unknown_one_is_refused(tmp_path):
    cfg = _config(tmp_path)
    renten.loeschen("drv", cfg)
    assert [q.id for q in renten.quellen(cfg)] == ["police"]
    with pytest.raises(ValueError, match="Keine Rentenquelle"):
        renten.loeschen("drv", cfg)


def test_two_pensions_with_the_same_name_get_two_ids(tmp_path):
    a = renten.anlegen({"name": "Police", "cents": 1}, tmp_path)
    b = renten.anlegen({"name": "Police", "cents": 1}, tmp_path)
    assert (a, b) == ("police", "police-2")


@pytest.mark.parametrize("felder", [
    {"name": "", "cents": 1}, {"name": "x"}, {"name": "x", "cents": -5},
    {"name": "x", "cents": 1, "art": "lotto"}, {"name": "x", "cents": 1, "ab": "2050"},
    {"name": "x", "cents": 1, "kosten_pa": 0.5}])
def test_a_pension_with_wrong_input_is_refused(tmp_path, felder):
    with pytest.raises(ValueError):
        renten.anlegen(felder, tmp_path)


def test_costs_are_set_and_cleared_on_an_existing_source(tmp_path):
    cfg = _config(tmp_path)
    renten.setzen("drv", {"kosten_pa": 0.015}, cfg)
    assert renten.quellen(cfg)[0].kosten_pa == 0.015
    renten.setzen("drv", {"kosten_pa": ""}, cfg)
    assert renten.quellen(cfg)[0].kosten_pa is None


def test_costs_above_the_threshold_are_flagged_on_the_monthly_close(monkeypatch):
    from finctl import assumptions as ann
    from finctl.web.routen import auswertung

    teuer = renten.Quelle(id="p", name="Police", art="kapital", cents=1, kosten_pa=0.02)
    guenstig = renten.Quelle(id="q", name="Fonds", art="kapital", cents=1, kosten_pa=0.01)
    monkeypatch.setattr(renten, "quellen", lambda *a, **k: [teuer, guenstig])
    monkeypatch.setattr(ann, "kostenschwelle_pa", lambda *a, **k: 0.013)

    class P:
        gruppe = "renten"

        def __init__(self, schluessel):
            self.schluessel = schluessel

    zeilen = auswertung._rentenzeilen([P("p"), P("q")])
    assert [z["kosten_hoch"] for z in zeilen] == [True, False]


# --------------------------------------------------------------- /renten

def test_the_pension_page_is_the_one_place_to_maintain_them(monkeypatch):
    """Anlegen und Pflegen auf /renten; der Monatsabschluss prueft nur und
    fuehrt hierher -- zwei Felder fuer einen Betrag laufen auseinander."""
    from fastapi.testclient import TestClient

    from finctl import module
    from finctl.web.server import app

    if not module.seite_an("/renten"):
        pytest.skip("Prognose ist ausgeschaltet")
    q = renten.Quelle(id="erfunden", name="Erfundene Rente", art="rente", cents=123_400,
                      kosten_pa=0.02)
    monkeypatch.setattr(renten, "quellen", lambda *a, **k: [q])
    client = TestClient(app)
    seite = client.get("/renten").text
    assert 'id="rente-erfunden"' in seite and 'id="rente-neu"' in seite
    assert "⚠" in seite.split('id="rente-erfunden"')[1].split("</tr>")[0]

    abschluss = client.get("/monatsabschluss").text
    zeile = abschluss.split('id="pos-rente-erfunden"')[1].split("</tr>")[0]
    assert 'href="/renten#rente-erfunden"' in zeile
    assert 'data-feld="wert"' not in zeile, "im Monatsabschluss nur lesen"
    assert 'id="rente-neu"' not in abschluss


def _bav_quelle(**kw) -> renten.Quelle:
    werte = {"id": "bav", "name": "Erfundene Betriebsrente", "art": "kapital",
             "kaufkraft": "nominal", "cents": 20_000_000, "ab": date(2055, 8, 1),
             "stand_cents": 2_000_000, "stand_wert": date(2026, 9, 1),
             "beitrag_ag_cents": 240_000}
    werte.update(kw)
    return renten.Quelle(**werte)


def _seite_mit(monkeypatch, quellen: list) -> str:
    from fastapi.testclient import TestClient

    from finctl import module
    from finctl.web.server import app

    if not module.seite_an("/renten"):
        pytest.skip("Prognose ist ausgeschaltet")
    monkeypatch.setattr(renten, "quellen", lambda *a, **k: quellen)
    return TestClient(app).get("/renten").text


def test_a_source_with_the_model_shows_its_rate_check_value_and_payout(monkeypatch):
    q = _bav_quelle(pruefwert=renten.Pruefwert(satz=None, cents=30_000_000,
                                               zum=date(2055, 8, 1)))
    seite = _seite_mit(monkeypatch, [q, _bav_quelle(id="ohne", name="Ohne Modell",
                                                    stand_cents=None, stand_wert=None,
                                                    beitrag_ag_cents=None)])
    zeile = seite.split('data-modell="bav"')[1].split("</tr>")[0]
    for text in ("Stand 20.000,00 € zum 09/2026", "Beitrag des Arbeitgebers 2.400,00 € im Jahr",
                 "Satz ", "zu 200.000,00 € zum 08/2055 führt",
                 "Prüfwert der Mitteilung 300.000,00 € zum 08/2055, ohne Satz",
                 "führt ein Satz von ", "Auszahlung ohne Teilzeit 200.000,00 €"):
        assert text in zeile, text
    assert 'data-modell="ohne"' not in seite, "ohne Modell keine Modellzeile"


def test_an_amount_the_model_cannot_carry_does_not_break_the_page(monkeypatch):
    seite = _seite_mit(monkeypatch, [_bav_quelle(cents=10 ** 15)])
    assert "kein Satz zwischen" in seite.split('data-modell="bav"')[1].split("</tr>")[0]


def test_without_any_pension_the_page_opens_the_form(monkeypatch):
    from fastapi.testclient import TestClient

    from finctl import module
    from finctl.web.server import app

    if not module.seite_an("/renten"):
        pytest.skip("Prognose ist ausgeschaltet")
    monkeypatch.setattr(renten, "quellen", lambda *a, **k: [])
    seite = TestClient(app).get("/renten").text
    assert '<details class="klapp" id="rente-neu" open>' in seite


# ------------------------------------------- Beitrag und Pruefwert einer Police

VERTRAEGE = """versicherungen:
  - id: police-beitrag
    name: Beitrag Fondspolice
    kategorie: versicherung/rente
    konto: giro
    betrag: -150.00
    takt: 1
    faellig: 2026-10-01
"""
ABOS = """abos:
  - id: abo-beitrag
    name: Beitrag Kapitalpolice
    kategorie: versicherung/rente
    konto: giro
    betrag_cents: -9000
    takt: 3
    faellig: 2026-10-01
"""


def _police(tmp_path, zusatz: str):
    (tmp_path / "renten.yaml").write_text(
        "renten:\n  - id: police\n    name: Fondspolice\n    art: kapital\n"
        "    cents: 5000000\n    ab: 2045-06\n    konto: police\n" + zusatz,
        encoding="utf-8")
    return tmp_path


def test_a_source_without_the_new_fields_has_none(tmp_path):
    [q] = renten.quellen(_police(tmp_path, ""))
    assert (q.beitrag, q.pruefwert) == (None, None)


def test_the_contribution_names_a_contract_from_either_contract_file(tmp_path):
    (tmp_path / "versicherungen.yaml").write_text(VERTRAEGE, encoding="utf-8")
    (tmp_path / "abos.yaml").write_text(ABOS, encoding="utf-8")
    [q] = renten.quellen(_police(tmp_path, "    beitrag: police-beitrag\n"))
    assert q.beitrag == "police-beitrag"
    [q] = renten.quellen(_police(tmp_path, "    beitrag: abo-beitrag\n"))
    assert q.beitrag == "abo-beitrag"


def test_an_unknown_contract_is_an_error_not_a_silent_zero(tmp_path):
    (tmp_path / "versicherungen.yaml").write_text(VERTRAEGE, encoding="utf-8")
    with pytest.raises(ValueError, match=r"police.*gibt-es-nicht"):
        renten.quellen(_police(tmp_path, "    beitrag: gibt-es-nicht\n"))


def test_a_contract_in_neither_file_exists_for_a_source_without_files(tmp_path):
    with pytest.raises(ValueError, match="kein Vertrag"):
        renten.quellen(_police(tmp_path, "    beitrag: police-beitrag\n"))


def test_the_contract_files_are_not_read_without_a_contribution(tmp_path):
    (tmp_path / "versicherungen.yaml").write_text("versicherungen: [kaputt", encoding="utf-8")
    [q] = renten.quellen(_police(tmp_path, ""))
    assert q.beitrag is None


def test_the_check_value_reads_rate_amount_and_month(tmp_path):
    [q] = renten.quellen(_police(
        tmp_path, "    pruefwert: {satz: 0.06, cents: 12000000, zum: 2056-02}\n"))
    assert q.pruefwert == renten.Pruefwert(satz=0.06, cents=12_000_000, zum=date(2056, 2, 1))


@pytest.mark.parametrize("zusatz", ["{cents: 12000000, zum: 2056-02}",
                                    "{satz: , cents: 12000000, zum: 2056-02}"])
def test_the_check_value_may_come_without_a_rate(tmp_path, zusatz):
    [q] = renten.quellen(_police(tmp_path, f"    pruefwert: {zusatz}\n"))
    assert q.pruefwert == renten.Pruefwert(satz=None, cents=12_000_000, zum=date(2056, 2, 1))


@pytest.mark.parametrize("pruefwert", [
    "{satz: 0.06, cents: 12000000}", "{satz: 0.06, zum: 2056-02}", "{zum: 2056-02}",
    "{cents: 12000000}", "{cents: 12000000, zum: 2056-02, satz: x}",
    "{satz: 0.06, cents: -1, zum: 2056-02}", "{satz: 0.06, cents: 1, zum: bald}",
    "{cents: -1, zum: 2056-02}", "{cents: eins, zum: 2056-02}", "{cents: 1, zum: bald}",
    "{satz: 0.9, cents: 1, zum: 2056-02}", "5"])
def test_a_check_value_with_a_missing_or_wrong_field_is_an_error(tmp_path, pruefwert):
    with pytest.raises(ValueError, match="pruefwert"):
        renten.quellen(_police(tmp_path, f"    pruefwert: {pruefwert}\n"))



# ---------------------------------------- betriebliche Altersvorsorge mit Modell
#
# Alle Werte erfunden: 40.000 Stand zum 01.01.2026, 2.400 Beitrag je Jahr, 300.000
# zum 01.01.2056, das sind 360 Monate.

BAV = ("    stand_cents: 4000000\n    stand_wert: 2026-01-01\n"
       "    beitrag_ag_cents: 240000\n")


def _bav(tmp_path, zusatz: str = BAV, cents: int = 30_000_000, kopf: str = ""):
    (tmp_path / "renten.yaml").write_text(
        "renten:\n  - id: bav\n    name: Betriebsrente\n    art: kapital\n"
        f"    kaufkraft: nominal\n    cents: {cents}\n    ab: 2056-01\n{kopf}{zusatz}",
        encoding="utf-8")
    [q] = renten.quellen(tmp_path)
    return q


BEGINN = date(2056, 1, 1)


def _monatsfaktor(q) -> float:
    return (1.0 + renten.satz(q, BEGINN)) ** (1 / 12)


def test_the_model_reads_stand_date_and_contribution(tmp_path):
    q = _bav(tmp_path)
    assert (q.stand_cents, q.stand_wert, q.beitrag_ag_cents) == (4_000_000, date(2026, 1, 1),
                                                                  240_000)
    assert q.hat_modell


def test_a_source_without_the_model_fields_keeps_its_amount(tmp_path):
    q = _bav(tmp_path, zusatz="")
    assert (q.hat_modell, renten.satz(q, BEGINN)) == (False, None)
    assert renten.auszahlung_cents(q, BEGINN, lambda monat: 0.5) == 30_000_000


@pytest.mark.parametrize("zusatz", [
    "    stand_cents: 4000000\n", "    stand_wert: 2026-01-01\n    beitrag_ag_cents: 1\n",
    "    stand_cents: 4000000\n    stand_wert: bald\n    beitrag_ag_cents: 240000\n",
    "    stand_cents: -1\n    stand_wert: 2026-01-01\n    beitrag_ag_cents: 240000\n",
    "    stand_cents: 1\n    stand_wert: 2026-01-01\n    beitrag_ag_cents: -1\n",
    "    stand_cents: eins\n    stand_wert: 2026-01-01\n    beitrag_ag_cents: 240000\n"])
def test_the_model_fields_come_together_or_not_at_all(tmp_path, zusatz):
    with pytest.raises(ValueError, match="stand_cents"):
        _bav(tmp_path, zusatz)


@pytest.mark.parametrize("kopf", ["    konto: police\n"])
def test_the_model_needs_a_capital_without_a_policy_account(tmp_path, kopf):
    with pytest.raises(ValueError, match="stand_cents"):
        _bav(tmp_path, kopf=kopf)


def test_the_model_refuses_a_pension_and_todays_money(tmp_path):
    (tmp_path / "renten.yaml").write_text(
        "renten:\n  - id: r\n    name: R\n    art: rente\n    kaufkraft: nominal\n"
        "    cents: 100000\n" + BAV, encoding="utf-8")
    with pytest.raises(ValueError, match="stand_cents"):
        renten.quellen(tmp_path)
    (tmp_path / "renten.yaml").write_text(
        "renten:\n  - id: r\n    name: R\n    art: kapital\n    kaufkraft: heute\n"
        "    cents: 100000\n" + BAV, encoding="utf-8")
    with pytest.raises(ValueError, match="stand_cents"):
        renten.quellen(tmp_path)
    with pytest.raises(ValueError, match="stand_cents"):
        _bav(tmp_path, cents=0)


def test_a_source_created_on_the_page_carries_the_model_fields_like_any_other(tmp_path):
    (tmp_path / "renten.yaml").write_text(
        "renten:\n- id: bav\n  name: Betriebsrente\n  art: kapital\n  kaufkraft: nominal\n"
        "  cents: 30000000\n  ab: 2056-01\n  stand_cents: 4000000\n"
        "  stand_wert: '2026-01-01'\n  beitrag_ag_cents: 240000\n", encoding="utf-8")
    [q] = renten.quellen(tmp_path)
    assert q.hat_modell and q.beitrag_ag_cents == 240_000


def test_the_rate_is_the_one_that_reaches_the_amount_to_the_cent(tmp_path):
    q = _bav(tmp_path)
    satz = renten.satz(q, BEGINN)
    assert 0.0 < satz < 0.07
    assert round(renten._endwert(q, BEGINN, satz)) == 30_000_000
    # Mehr Betrag bei gleichem Stand und Beitrag heisst mehr Satz.
    assert renten.satz(_bav(tmp_path, cents=40_000_000), BEGINN) > satz


def test_without_part_time_the_payout_is_the_amount_to_the_cent(tmp_path):
    q = _bav(tmp_path)
    assert renten.auszahlung_cents(q, BEGINN) == 30_000_000
    # Auch ueber den Verlauf gerechnet, wenn die Teilzeit nichts kuerzt.
    assert renten.auszahlung_cents(q, BEGINN, lambda monat: None) == 30_000_000
    assert renten.auszahlung_cents(q, BEGINN, lambda monat: 1.0) == 30_000_000


def _endwert_der_beitraege(q, monate: int, anteil: float) -> float:
    """Was `monate` Beitraege am Ende noch wert sind, der letzte ohne Verzinsung."""
    g = _monatsfaktor(q)
    return anteil * q.beitrag_ag_cents / 12 * (g ** monate - 1) / (g - 1)


def test_half_the_contribution_in_the_second_half_costs_half_of_its_final_value(tmp_path):
    q = _bav(tmp_path)
    halb = date(2041, 1, 1)                           # 180 von 360 Monaten
    aus = renten.auszahlung_cents(q, BEGINN, lambda monat: 0.5 if monat >= halb else None)
    erwartet = 30_000_000 - _endwert_der_beitraege(q, 180, 0.5)
    assert aus == pytest.approx(erwartet, abs=1)
    assert aus < 30_000_000


def test_without_salary_the_contribution_ends_completely(tmp_path):
    q = _bav(tmp_path)
    halb = date(2041, 1, 1)
    aus = renten.auszahlung_cents(q, BEGINN, lambda monat: None, gehalt_bis=halb)
    assert aus == pytest.approx(30_000_000 - _endwert_der_beitraege(q, 180, 1.0), abs=1)
    # Endet das Gehalt erst mit dem Bezug, bleibt es beim Betrag.
    assert renten.auszahlung_cents(q, BEGINN, lambda monat: None, gehalt_bis=BEGINN) \
        == 30_000_000


def test_an_amount_no_rate_can_reach_is_an_error_not_a_guess(tmp_path):
    q = _bav(tmp_path, cents=10 ** 15)
    with pytest.raises(ValueError, match="kein Satz"):
        renten.satz(q, BEGINN)


def test_without_months_to_grow_there_is_no_rate_and_the_amount_stands(tmp_path):
    q = _bav(tmp_path)
    assert renten.satz(q, date(2026, 1, 1)) is None
    assert renten.auszahlung_cents(q, date(2026, 1, 1), lambda monat: 0.5) == 30_000_000


def test_the_rate_to_any_amount_is_the_rate_of_the_amount_when_it_is_the_amount(tmp_path):
    q = _bav(tmp_path)
    assert renten.satz_zu(q, BEGINN, q.cents) == renten.satz(q, BEGINN)
    assert renten.satz_zu(q, BEGINN, 40_000_000) > renten.satz_zu(q, BEGINN, q.cents)


def test_the_rate_to_an_amount_no_rate_reaches_is_none(tmp_path):
    q = _bav(tmp_path)
    assert renten.satz_zu(q, BEGINN, 10 ** 15) is None
    assert renten.satz_zu(q, date(2026, 1, 1), q.cents) is None


def test_the_rate_to_an_amount_needs_the_model(tmp_path):
    q = _bav(tmp_path, zusatz="")
    assert renten.satz_zu(q, BEGINN, q.cents) is None


def test_part_time_from_a_month_leaves_the_months_before_whole():
    anteil = renten.teilzeit_ab(0.6, date(2041, 1, 1))
    assert anteil(date(2040, 12, 1)) is None
    assert anteil(date(2041, 1, 1)) == 0.6 and anteil(date(2050, 5, 1)) == 0.6


# ------------------------------------------------ der Musterhaushalt hat beides

@pytest.mark.skipif(os.environ.get("FINCTL_TESTDATEN") != "muster",
                    reason="gilt nur fuer den erfundenen Haushalt")
def test_the_sample_household_has_an_employer_pension_and_a_teilzeit_line_without_a_start():
    """Die Browsertests laufen im Musterlauf auf beidem: /renten zeigt die Modellzeile,
    /planung die Zeile ohne eigenes Datum."""
    from fastapi.testclient import TestClient

    from finctl import module
    from finctl.forecast import szenarien as sz
    from finctl.pfade import CONFIG_DIR
    from finctl.web.server import app

    [bav] = [q for q in renten.quellen() if q.hat_modell]
    assert bav.pruefwert is not None and bav.pruefwert.satz is None
    assert renten.satz(bav, bav.ab) is not None
    spec = yaml.safe_load((CONFIG_DIR / "szenarien.yaml").read_text(encoding="utf-8"))
    [klammer] = [k for k in sz.load(spec) if k.id == sz.TEILZEIT_ID]
    [ohne] = [z for z in klammer.lines if z.kind == "wegfall"]
    assert ohne.aus_annahmen == ("start",) and ohne.start is not None
    if module.seite_an("/renten"):
        seite = TestClient(app).get("/renten").text
        assert f'data-modell="{bav.id}"' in seite
