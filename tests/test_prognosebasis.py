"""Die Prognosebasis: beide Rechnungen nebeneinander, eine Abwahl fuer beide.

Eine Schenkung aus zwei Monaten schrieb die Jahresrechnung als Einkommen
fort, waehrend /konten sie ignorierte. Abgewaehlt wird deshalb an EINER Stelle,
und es muss in beiden Rechnungen ankommen -- sonst entstuende genau die
Differenz ohne sichtbaren Grund, die diese Seite beseitigen soll.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from finctl.forecast import prognosebasis as pb

DB = Path("data/finance.db")


def test_only_the_deviation_is_stored(tmp_path, monkeypatch):
    monkeypatch.setattr(pb, "CONFIG_DIR", tmp_path)
    assert pb.nicht_fortschreiben() == set()
    pb.setzen("einkommen/schenkung", False)
    spec = yaml.safe_load((tmp_path / pb.DATEI).read_text(encoding="utf-8"))
    assert spec == {pb.SCHLUESSEL: ["einkommen/schenkung"]}
    pb.setzen("einkommen/schenkung", True)
    assert not (tmp_path / pb.DATEI).exists()


@pytest.mark.skipif(not DB.exists(), reason="no ledger present")
def test_an_excluded_category_is_gone_from_both_engines(monkeypatch):
    from datetime import date

    import yaml as _y

    from finctl import kontenregeln as kr
    from finctl import ops
    from finctl.forecast import jahre as jm
    from finctl.ledger.db import connect

    kategorie = "versicherung/pkv"
    fcfg = _y.safe_load(Path("config/forecast.yaml").read_text(encoding="utf-8"))
    betrieb = next(k for k, v in (kr.wirksam().get("account_roles") or {}).items()
                   if (v or {}).get("role") == "operating")
    jahr = date.today().year + 1
    c = connect()
    try:
        vorher_konto = {i.category for i in ops.abgeleitete_posten(c, betrieb, fcfg)}
        vorher_jahr = {p.verweis for p
                       in jm.project(c, end_year=jahr + 1).year(jahr).posten["fixkosten"]}
        assert kategorie in vorher_konto and kategorie in vorher_jahr

        monkeypatch.setattr(pb, "nicht_fortschreiben", lambda: {kategorie})
        nachher_konto = {i.category for i in ops.abgeleitete_posten(c, betrieb, fcfg)}
        nachher_jahr = {p.verweis for p
                        in jm.project(c, end_year=jahr + 1).year(jahr).posten["fixkosten"]}
    finally:
        c.close()
    assert kategorie not in nachher_konto
    assert kategorie not in nachher_jahr


@pytest.mark.skipif(not DB.exists(), reason="no ledger present")
def test_the_page_names_a_reason_for_every_difference():
    from finctl.ledger.db import connect

    c = connect()
    try:
        v = pb.vergleich(c)
    finally:
        c.close()
    assert v["zeilen"]
    for z in v["zeilen"]:
        if z["delta"]:
            assert z["grund"], z["kategorie"]
    gehalt = next(z for z in v["zeilen"] if z["kategorie"] == "einkommen/gehalt")
    assert "Untergrenze" in gehalt["grund"]


@pytest.mark.skipif(not DB.exists(), reason="no ledger present")
def test_the_two_columns_differ_only_by_rounding_or_by_a_kontenregel():
    """Beide Rechnungen nehmen dieselben Eingaben: Das Delta einer Zeile ist Rundung, es sei
    denn, nur das Monatsmodell kennt die Regel (`exclude_from_recurring` in forecast.yaml).
    Was ein Vertrag, eine erwartete Einnahme oder die Objektprognose ersetzt, steht in beiden
    Spalten als Posten, nicht als Messung der ersetzten Buchungen."""
    from finctl.ledger.db import connect

    c = connect()
    try:
        v = pb.vergleich(c)
    finally:
        c.close()
    abweichend = [(z["kategorie"], z["delta"]) for z in v["zeilen"]
                  if abs(z["delta"]) > pb.RUNDUNG_CENTS and not z["dauerhaft"]]
    assert not abweichend
    assert abs(v["summe_jahr"] - v["summe_konten"]) <= pb.RUNDUNG_CENTS * len(v["zeilen"])
    for z in v["zeilen"]:
        if z["block"] == "objekt" and "(Objektprognose)" not in z["kategorie"]:
            assert z["konten"] is None and z["jahr"] is None, z["kategorie"]
