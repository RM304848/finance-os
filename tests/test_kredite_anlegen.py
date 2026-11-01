"""Kredite anlegen und wieder loswerden.

Wer dieses Werkzeug uebernimmt, erbt sonst fremde Vertraege in seiner
Prognose -- und eine Rate, die er nie zahlt, drueckt den Tiefpunkt jedes
Monats. Entfernen ist deshalb der wichtigere der beiden Wege.

Testdaten sind erfunden.
"""

from __future__ import annotations

import pytest
import yaml

from finctl import kredite
from finctl.realestate.loan import lade_kredite

RATE = {"id": "ratenkredit", "name": "Möbel", "lender": "Beispielbank",
        "servicing_account_id": "giro", "opening_balance_cents": 480000,
        "annuity_cents": 15000, "annual_rate_pct": 6.0,
        "start": "2026-01-01", "ende": "2029-01-01"}


GEERBT = {"id": "geerbt", "name": "Geerbt", "lender": "Fremdbank", "status": "active",
          "notiz": "Warum dieser Kredit so gerechnet wird.\n\nZweiter Absatz.",
          "notiz_vom": "2026-03-01"}


@pytest.fixture
def konfig(tmp_path):
    """Eine Datei mit einem Kredit und seiner Notiz, dazu die Notiz des Bereichs."""
    ordner = tmp_path / "config"
    ordner.mkdir()
    (ordner / kredite.DATEI).write_text(
        yaml.safe_dump({"loans": [GEERBT],
                        "notizen": {"bereich": {"notiz": "Alle Kredite des Haushalts."}}}),
        encoding="utf-8")
    return ordner


def _datei(konfig):
    return yaml.safe_load((konfig / kredite.DATEI).read_text(encoding="utf-8"))


def test_a_new_loan_is_a_loan_the_schedule_can_compute(konfig):
    """Neun Angaben ergeben ein Segment -- mehr braucht ein Ratenkredit nicht."""
    from finctl.realestate.loan import segments_from

    kredite.anlegen(dict(RATE), konfig)
    [neu] = [k for k in lade_kredite(konfig) if k["id"] == "ratenkredit"]
    [seg] = segments_from(neu)
    assert (seg.annual_rate_pct, seg.annuity_cents) == (6.0, 15000)
    assert seg.opening_balance_cents == 480000


def test_a_new_loan_stands_behind_the_others_and_nothing_else_changes(konfig):
    """Eine Datei: Der neue Kredit steht in `loans.yaml`, die Notizen bleiben."""
    kredite.anlegen(dict(RATE), konfig)
    datei = _datei(konfig)
    assert [k["id"] for k in datei["loans"]] == ["geerbt", "ratenkredit"]
    assert datei["loans"][0] == GEERBT
    assert datei["notizen"]["bereich"]["notiz"] == "Alle Kredite des Haushalts."
    assert not (konfig / "loans_custom.yaml").exists()


def test_removing_a_loan_takes_it_out_of_the_file_with_its_note(konfig):
    """Der Punkt der ganzen Uebung: fremde Vertraege muessen weg koennen. Es gibt keine
    Basisdatei mehr, die den Eintrag und seine Notiz behielte."""
    assert [k["id"] for k in lade_kredite(konfig)] == ["geerbt"]
    kredite.entfernen("geerbt", konfig)
    assert lade_kredite(konfig) == []
    assert _datei(konfig)["notizen"]["bereich"]["notiz"] == "Alle Kredite des Haushalts."


def test_removing_an_own_loan_leaves_no_trace(konfig):
    kredite.anlegen(dict(RATE), konfig)
    kredite.entfernen("ratenkredit", konfig)
    assert [k["id"] for k in _datei(konfig)["loans"]] == ["geerbt"]


def test_removing_what_is_not_there_is_refused(konfig):
    vorher = (konfig / kredite.DATEI).read_text(encoding="utf-8")
    with pytest.raises(ValueError, match=r"Kein Kredit"):
        kredite.entfernen("erfunden", konfig)
    assert (konfig / kredite.DATEI).read_text(encoding="utf-8") == vorher


def test_the_conditions_set_on_the_page_survive_a_write(konfig):
    """`vorlage` und `anschluss_eingegeben` stehen am Kredit. Ein Schreiben, das sie
    verliert, naehme szenariogebundenen Krediten ihre Konditionen."""
    kredite.an_kredit_setzen("geerbt", kredite.VORLAGE, {"annual_rate_pct": 4.5}, konfig)
    kredite.an_kredit_setzen("geerbt", kredite.ANSCHLUSS,
                             {"zins_pct": 4.0, "tilgung_pct": 2.0}, konfig)
    kredite.anlegen(dict(RATE), konfig)
    geerbt = _datei(konfig)["loans"][0]
    assert geerbt["vorlage"] == {"annual_rate_pct": 4.5}
    assert geerbt["anschluss_eingegeben"] == {"zins_pct": 4.0, "tilgung_pct": 2.0}


def test_a_condition_for_a_loan_that_does_not_exist_is_refused(konfig):
    with pytest.raises(ValueError, match=r"Kein Kredit"):
        kredite.an_kredit_setzen("erfunden", kredite.ANSCHLUSS, {"zins_pct": 4.0}, konfig)


def test_saving_the_same_thing_again_changes_no_byte(konfig):
    kredite.an_kredit_setzen("geerbt", kredite.ANSCHLUSS,
                             {"zins_pct": 4.0, "tilgung_pct": 2.0}, konfig)
    vorher = (konfig / kredite.DATEI).read_bytes()
    assert not kredite.an_kredit_setzen("geerbt", kredite.ANSCHLUSS,
                                        {"zins_pct": 4.0, "tilgung_pct": 2.0}, konfig)
    assert (konfig / kredite.DATEI).read_bytes() == vorher


@pytest.mark.parametrize("aenderung, wort", [
    ({"id": "Mit Großbuchstaben"}, "Kennung"),
    ({"id": "geerbt"}, "vergeben"),
    ({"name": ""}, "Name"),
    ({"lender": ""}, "Gläubiger"),
    ({"servicing_account_id": None}, "Konto"),
    ({"opening_balance_cents": 0}, "Restschuld"),
    ({"annuity_cents": 0}, "Monatsrate"),
    ({"annual_rate_pct": 120}, "Zinssatz"),
    ({"start": "kein Datum"}, "Beginn"),
    ({"ende": ""}, "Ende"),
    ({"ende": "2025-01-01"}, "vor dem Beginn"),
])
def test_a_broken_loan_is_refused_with_a_reason(konfig, aenderung, wort):
    with pytest.raises(ValueError, match=wort):
        kredite.anlegen({**RATE, **aenderung}, konfig)
    assert _datei(konfig)["loans"] == [GEERBT]


def test_a_rate_below_the_monthly_interest_is_refused(konfig):
    """Sonst waechst die Restschuld, und der Tilgungsplan zeigt eine Prognose,
    die nie endet -- als Zahl plausibel, als Aussage falsch."""
    with pytest.raises(ValueError, match="Monatszins"):
        kredite.anlegen({**RATE, "annuity_cents": 100}, konfig)


# ---------------------------------------------------------------- Seite

from fastapi.testclient import TestClient  # noqa: E402

from finctl.web.server import app  # noqa: E402

client = TestClient(app)


def test_the_page_offers_the_form_and_a_way_out():
    html = client.get("/kredite").text
    assert 'id="neu-kredit"' in html and "Neues Annuitätendarlehen" in html
    # Je Kredit ein Weg, ihn loszuwerden.
    assert html.count("kreditEntfernen(") >= 1


def test_the_account_list_offers_only_open_accounts():
    """Eine Rate von einem geschlossenen Konto abzubuchen ergibt keinen Sinn."""
    import re

    html = client.get("/kredite").text
    block = html[html.index('id="k-konto"'):]
    angeboten = set(re.findall(r'<option value="([^"]+)"', block[:block.index("</select>")]))
    assert angeboten
    assert not (angeboten & {"amex", "revolut", "onvista"})   # geschlossen


def test_the_endpoints_refuse_before_they_write():
    """Beide Ablehnungen kommen vor dem Schreiben, brauchen also keine
    Konfiguration -- und fassen die echte nicht an."""
    antwort = client.post("/api/kredit-neu", json={"id": "", "name": ""})
    assert antwort.status_code == 400 and "Kennung" in antwort.json()["error"]

    antwort = client.post("/api/kredit-entfernen", json={"id": "gibtsnicht"})
    assert antwort.status_code == 400
