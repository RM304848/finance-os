"""Der Notfallwert einer Police (Plan Policen, P.3): Rueckkaufswert nach Steuer.

Erfunden und rund. Gerechnet wird `bestaende.notfallwert`; hier steht, was es mit
verschiedenen Staenden und fehlenden Angaben tut, dass der Monatsabschluss die
Felder speichert, und dass der Wert nur gezeigt wird: Notgroschen und liquides
Vermoegen bleiben, wie sie sind.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from finctl import assumptions as ann
from finctl import bestaende as best
from finctl.forecast import ziele as zl
from finctl.ledger.db import connect

SATZ = 0.25


def _police(**felder):
    """Policenwert 20.000 und Rueckkaufswert 18.000, beide vom 01.04.2026."""
    return {"account_id": "police", "name": "Police", "kind": "rentenversicherung",
            "cents": 20_000_00, "as_of": "2026-04-01",
            "rueckkauf_cents": 18_000_00, "rueckkauf_as_of": "2026-04-01",
            "eingezahlt_cents": 15_000_00, **felder}


# ------------------------------------------------------------------- Rechnung

def test_with_the_same_stand_the_surrender_value_stands_as_stated():
    n = best.notfallwert(_police(), SATZ)
    assert (n.rueckkauf_cents, n.ertrag_cents, n.steuer_cents, n.cents) == (
        18_000_00, 3_000_00, 750_00, 17_250_00)
    assert n.quote is None and not n.verhaeltnis_fehlt
    assert n.stand == date(2026, 4, 1)


def test_no_tax_when_less_was_paid_in_than_the_policy_would_return():
    n = best.notfallwert(_police(eingezahlt_cents=19_000_00), SATZ)
    assert (n.ertrag_cents, n.steuer_cents, n.cents) == (0, 0, 18_000_00)


def test_a_newer_policenwert_applies_the_ratio_of_the_mitteilung():
    """Rueckkauf 18.000 bei Policenwert 20.000 sind 90 %; heute 24.000 -> 21.600."""
    n = best.notfallwert(_police(
        cents=24_000_00, as_of="2026-10-01", rueckkauf_policenwert_cents=20_000_00), SATZ)
    assert n.quote == pytest.approx(0.9)
    assert (n.rueckkauf_cents, n.ertrag_cents, n.steuer_cents, n.cents) == (
        21_600_00, 6_600_00, 1_650_00, 19_950_00)
    assert (n.mitteilung_cents, n.basis_cents, n.stand) == (18_000_00, 20_000_00, date(2026, 4, 1))


def test_the_ratio_needs_the_policenwert_of_the_mitteilung_not_the_current_one():
    """Ohne ihn bliebe nur der heutige Policenwert: 18.000 gegen 24.000 gaebe 75 % und
    beschriebe die Kosten einer Police, die es nie gab. Also bleibt der Rueckkaufswert auf
    seinem Stand und die Zeile sagt, dass das Verhaeltnis fehlt."""
    n = best.notfallwert(_police(cents=24_000_00, as_of="2026-10-01"), SATZ)
    assert n.verhaeltnis_fehlt and n.quote is None
    assert (n.rueckkauf_cents, n.cents) == (18_000_00, 17_250_00)


def test_at_the_same_stand_nothing_is_converted_and_one_day_later_the_ratio_is_missing():
    assert best.notfallwert(_police(), SATZ).basis_cents is None
    n = best.notfallwert(_police(cents=22_000_00, as_of="2026-04-02"), SATZ)
    assert n.verhaeltnis_fehlt and n.rueckkauf_cents == 18_000_00


def test_an_older_policenwert_than_the_rueckkaufswert_does_not_scale_it():
    n = best.notfallwert(_police(cents=10_000_00, as_of="2026-01-01",
                                 rueckkauf_policenwert_cents=20_000_00), SATZ)
    assert (n.rueckkauf_cents, n.quote) == (18_000_00, None)


def test_without_eingezahlt_the_tax_falls_on_the_whole_surrender_value():
    """Der Notfallwert ist dann eine Untergrenze, und die Zeile sagt es (`ertrag` fehlt)."""
    n = best.notfallwert(_police(eingezahlt_cents=None), SATZ)
    assert n.ertrag_cents is None and n.eingezahlt_cents is None
    assert (n.steuer_cents, n.cents) == (4_500_00, 13_500_00)


def test_the_policenwert_of_the_mitteilung_is_read_with_the_other_fields():
    zeile = _police(rueckkauf_policenwert_cents=20_000_00)
    assert best.rueckkauf(zeile).policenwert_cents == 20_000_00
    assert best.rueckkauf(_police()).policenwert_cents is None


def test_a_policy_without_surrender_value_has_no_emergency_value():
    zeile = _police()
    for feld in best.RUECKKAUF_FELDER:
        zeile.pop(feld, None)
    assert best.notfallwert(zeile, SATZ) is None
    assert best.notfallwert({**_police(), "kind": "depot"}, SATZ) is None


@pytest.mark.parametrize("felder", [
    {"rueckkauf_policenwert_cents": -1},
    {"rueckkauf_policenwert_cents": 0},
    {"rueckkauf_cents": None, "rueckkauf_as_of": None, "eingezahlt_cents": None},  # nur Policenwert
])
def test_a_wrong_policenwert_of_the_mitteilung_is_an_error_when_reading(felder):
    with pytest.raises(ValueError, match="Police"):
        best.rueckkauf(_police(**{"rueckkauf_policenwert_cents": 20_000_00, **felder}))


# ------------------------------------------------------ Policenwert festhalten

def _festhalten(eintrag, vorher=None):
    best.policenwert_festhalten(vorher or _police(), eintrag)
    return eintrag


def test_a_new_policenwert_keeps_the_one_the_rueckkaufswert_belonged_to():
    eintrag = _festhalten({"cents": 24_000_00, "as_of": "2026-10-01"})
    assert eintrag["rueckkauf_policenwert_cents"] == 20_000_00
    n = best.notfallwert({**_police(), **eintrag}, SATZ)
    assert n.quote == pytest.approx(0.9) and not n.verhaeltnis_fehlt


def test_the_same_policenwert_again_changes_nothing_in_the_entry():
    assert "rueckkauf_policenwert_cents" not in _festhalten(
        {"cents": 20_000_00, "as_of": "2026-04-01"})


def test_a_new_surrender_value_is_a_new_mitteilung_and_keeps_nothing():
    eintrag = _festhalten({"cents": 24_000_00, "as_of": "2026-10-01",
                           "rueckkauf_cents": 22_000_00, "rueckkauf_as_of": "2026-10-01"})
    assert "rueckkauf_policenwert_cents" not in eintrag


def test_a_stated_policenwert_of_the_mitteilung_is_not_overwritten():
    vorher = _police(rueckkauf_policenwert_cents=19_000_00)
    assert "rueckkauf_policenwert_cents" not in _festhalten(
        {"cents": 24_000_00, "as_of": "2026-10-01"}, vorher)


def test_a_policenwert_that_was_already_newer_than_the_mitteilung_keeps_nothing():
    """Der Policenwert der Mitteilung ist dann nicht der, der dastand."""
    vorher = _police(cents=21_000_00, as_of="2026-07-01")
    assert "rueckkauf_policenwert_cents" not in _festhalten(
        {"cents": 24_000_00, "as_of": "2026-10-01"}, vorher)


# ----------------------------------------------------- Speichern und Anzeigen

@pytest.fixture
def seite():
    from fastapi.testclient import TestClient

    from finctl.web.server import app

    pfad = Path("config/balances.yaml")
    vorher = pfad.read_bytes()
    yield TestClient(app), pfad
    pfad.write_bytes(vorher)


def _police_der_daten() -> dict:
    """Eine Rentenversicherung mit Betrag, wie die Daten sie fuehren."""
    basis = yaml.safe_load(Path("config/balances.yaml").read_text(encoding="utf-8"))
    for z in basis["balances"]:
        if z.get("kind") == "rentenversicherung" and z.get("cents") and z.get("as_of"):
            return z
    pytest.skip("keine Rentenversicherung mit Stand")


def _zeile(key: str) -> dict:
    c = connect()
    try:
        return next(z for z in best.zusammenfuehren(
            c, yaml.safe_load(Path("config/balances.yaml").read_text(encoding="utf-8")))["balances"]
            if best.schluessel(z) == key)
    finally:
        c.close()


def _eingeben(client, key: str, **felder):
    return client.post("/api/bestand", json={"key": key, **felder})


def _datei(pfad: Path) -> dict:
    return yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}


def _eintrag(pfad: Path, key: str) -> dict:
    """Die Position `key` in der Datei."""
    return next(e for e in _datei(pfad)["balances"] if best.schluessel(e) == key)


def test_the_monatsabschluss_saves_the_four_fields_as_text_and_again_without_a_change(seite):
    client, pfad = seite
    key = best.schluessel(_police_der_daten())
    davor = _datei(pfad)
    ein = {"rueckkauf_cents_text": "1.234,56", "eingezahlt_cents_text": "1.000,00",
           "rueckkauf_policenwert_cents_text": "1.300,00", "rueckkauf_as_of": "2026-01-01"}
    assert _eingeben(client, key, **ein).json()["ok"]
    spec = _datei(pfad)
    eintrag = _eintrag(pfad, key)
    assert {f: eintrag[f] for f in best.RUECKKAUF_FELDER} == {
        "rueckkauf_cents": 123456, "eingezahlt_cents": 100000,
        "rueckkauf_policenwert_cents": 130000, "rueckkauf_as_of": "2026-01-01"}
    # Nur die Angaben der Mitteilung: Stand und Verlauf der Position bleiben, wie sie waren.
    vorher = next(e for e in davor["balances"] if best.schluessel(e) == key)
    assert eintrag.get("cents") == vorher.get("cents")
    assert spec.get("verlauf") == davor.get("verlauf")

    gesehen, zeit = pfad.read_bytes(), pfad.stat().st_mtime_ns
    assert _eingeben(client, key, **ein).json()["ok"]
    assert (pfad.read_bytes(), pfad.stat().st_mtime_ns) == (gesehen, zeit)


def test_an_empty_field_means_not_known_and_an_empty_surrender_value_removes_all_four(seite):
    client, pfad = seite
    key = best.schluessel(_police_der_daten())
    ein = {"rueckkauf_cents_text": "1.000,00", "rueckkauf_as_of": "2026-01-01",
           "rueckkauf_policenwert_cents_text": "1.100,00"}
    _eingeben(client, key, **ein, eingezahlt_cents_text="900,00")
    assert _eintrag(pfad, key)["eingezahlt_cents"] == 90000
    _eingeben(client, key, **ein, eingezahlt_cents_text="")
    eintrag = _eintrag(pfad, key)
    assert "eingezahlt_cents" not in eintrag and eintrag["rueckkauf_cents"] == 100000

    _eingeben(client, key, rueckkauf_cents_text="")
    assert not set(best.RUECKKAUF_FELDER) & set(_eintrag(pfad, key))


def test_a_new_surrender_value_drops_the_policenwert_of_the_old_mitteilung(seite):
    client, pfad = seite
    key = best.schluessel(_police_der_daten())
    _eingeben(client, key, rueckkauf_cents_text="1.000,00", rueckkauf_as_of="2026-01-01",
              rueckkauf_policenwert_cents_text="1.100,00")
    _eingeben(client, key, rueckkauf_cents_text="1.200,00", rueckkauf_as_of="2026-05-01")
    assert "rueckkauf_policenwert_cents" not in _eintrag(pfad, key)


def test_a_wrong_field_is_answered_with_400_and_writes_nothing(seite):
    client, pfad = seite
    key = best.schluessel(_police_der_daten())
    vorher = pfad.read_bytes()
    for felder in ({"rueckkauf_cents_text": "1.000,00", "rueckkauf_as_of": "bald"},
                   {"rueckkauf_cents_text": "1.000,00", "rueckkauf_as_of": "2026-01-01",
                    "eingezahlt_cents_text": "-5,00"},
                   {"rueckkauf_cents_text": "1.000,00", "rueckkauf_as_of": "2026-01-01",
                    "rueckkauf_policenwert_cents_text": "0,00"},
                   {"rueckkauf_cents_text": "1,234.56", "rueckkauf_as_of": "2026-01-01"}):
        antwort = _eingeben(client, key, **felder)
        assert antwort.status_code == 400, felder
        assert antwort.json()["error"]
    assert pfad.read_bytes() == vorher


def test_saving_a_newer_policenwert_keeps_the_ratio_of_the_mitteilung(seite):
    client, pfad = seite
    key = best.schluessel(_police_der_daten())
    z = _zeile(key)
    p = int(z["cents"])
    _eingeben(client, key, rueckkauf_cents_text="1.000,00", rueckkauf_as_of=str(z["as_of"]))
    assert _eingeben(client, key, cents=p * 2, as_of="2099-01-01").json()["ok"]
    assert _eintrag(pfad, key)["rueckkauf_policenwert_cents"] == p
    n = best.notfallwert(_zeile(key), SATZ)
    assert n.quote == pytest.approx(100000 / p) and not n.verhaeltnis_fehlt


def _satz() -> float:
    return ann.vorabpauschale()[1]


def test_konten_shows_the_emergency_value_with_its_derivation_and_a_missing_one(seite):
    client, _ = seite
    key = best.schluessel(_police_der_daten())
    z = _zeile(key)
    p, stand = int(z["cents"]), str(z["as_of"])
    rueckkauf, eingezahlt = p // 200 * 100, p // 400 * 100       # in Cent, auf Euro gerundet
    assert _eingeben(client, key, rueckkauf_cents=rueckkauf, eingezahlt_cents=eingezahlt,
                     rueckkauf_as_of=stand, rueckkauf_policenwert_cents=p).json()["ok"]
    html = client.get("/konten").text
    zeile = html[html.index(f'id="notfall-{key}"'):]
    zeile = zeile[:zeile.index("</tr>")]
    steuer = round(max(rueckkauf - eingezahlt, 0) * _satz())
    erwartet = best.notfallwert(_zeile(key), _satz())
    assert erwartet.cents == rueckkauf - steuer
    from finctl.ledger.db import format_eur
    assert format_eur(erwartet.cents) in zeile and format_eur(steuer) in zeile
    assert "Steuer auf den Ertrag" in html

    # Ohne Rueckkaufswert steht die Police trotzdem da, mit leerem Notfallwert. Wo die
    # Basisdatei einen fuehrt, bleibt er; dann gibt es diesen Fall in den Daten nicht.
    _eingeben(client, key, rueckkauf_cents="")
    if best.rueckkauf(_zeile(key)) is None:
        zeile = client.get("/konten").text
        zeile = zeile[zeile.index(f'id="notfall-{key}"'):]
        assert "kein Rückkaufswert" in zeile[:zeile.index("</tr>")]


def test_the_emergency_value_changes_neither_the_emergency_fund_nor_the_liquid_wealth(seite):
    """Er wird nur gezeigt: Toepfe, liquides Vermoegen und die Seiten, die damit rechnen,
    bleiben Zeichen fuer Zeichen gleich."""
    client, _ = seite
    key = best.schluessel(_police_der_daten())
    z = _zeile(key)
    p = int(z["cents"])

    def stand():
        c = connect()
        try:
            merged = best.zusammenfuehren(c, yaml.safe_load(
                Path("config/balances.yaml").read_text(encoding="utf-8")))
        finally:
            c.close()
        return (zl.liquid_cents(merged), zl.toepfe(merged), zl.policen_je_konto(merged),
                client.get("/ziele").text, client.get("/hochrechnung").text)

    vorher = stand()
    assert _eingeben(client, key, rueckkauf_cents=p // 2, eingezahlt_cents=p // 4,
                     rueckkauf_as_of=str(z["as_of"])).json()["ok"]
    assert stand() == vorher


def test_konten_shows_the_cases_the_data_may_not_have(seite, monkeypatch):
    """Ohne Rueckkaufswert, ohne `eingezahlt` (Untergrenze) und mit fehlendem Verhaeltnis:
    jede Zeile sagt, was an ihr anders ist, statt eine runde Zahl zu behaupten."""
    from finctl.web.routen import konten as route

    client, _ = seite
    z = {"cents": 24_000_00, "as_of": "2026-10-01", **{
        f: _police()[f] for f in ("rueckkauf_cents", "rueckkauf_as_of")}}
    ohne_basis = best.notfallwert({**_police(), **z, "eingezahlt_cents": None}, SATZ)
    verhaeltnis = best.notfallwert({**_police(), **z}, SATZ)
    zeilen = [
        {"key": "a", "name": "Ohne", "cents": 1_000_00, "as_of": "2026-01-01",
         "notfall": None, "herleitung": ""},
        {"key": "b", "name": "Untergrenze", "cents": z["cents"], "as_of": z["as_of"],
         "notfall": ohne_basis,
         "herleitung": route.notfall_herleitung(ohne_basis, z, SATZ)},
        {"key": "c", "name": "Verhaeltnis", "cents": z["cents"], "as_of": z["as_of"],
         "notfall": verhaeltnis,
         "herleitung": route.notfall_herleitung(verhaeltnis, z, SATZ)}]
    monkeypatch.setattr(route, "policen_im_notfall", lambda: zeilen)
    html = client.get("/konten").text
    a, b, c = (html[html.index(f'id="notfall-{k}"'):] for k in "abc")
    assert "kein Rückkaufswert" in a[:a.index("</tr>")]
    assert "mind. " in b[:b.index("</tr>")]
    assert "Untergrenze" in b[:b.index("</tr>")]          # im Tooltip der Zeile
    assert "Verhältnis fehlt" in c[:c.index("</tr>")]
    assert "ihr Policenwert fehlt" in zeilen[2]["herleitung"]


def test_the_derivation_names_every_step():
    z = _police(cents=24_000_00, as_of="2026-10-01", rueckkauf_policenwert_cents=20_000_00)
    from finctl.web.routen import konten as route

    text = route.notfall_herleitung(best.notfallwert(z, 0.26375), z, 0.26375)
    for teil in ("Rückkaufswert der Mitteilung 18.000,00 € (Stand 2026-04-01)",
                 "Policenwert 24.000,00 €", "Policenwert der Mitteilung 20.000,00 €",
                 "= 21.600,00 €", "26,375 % Steuer auf den Ertrag 6.600,00 €",
                 "eingezahlt 15.000,00 €", "Notfallwert"):
        assert teil in text, teil


def test_renten_shows_the_check_value_exactly_as_the_hochrechnung_derives_it(seite):
    """Eine Stelle rechnet den Vergleich (`jahre.pruefvergleiche`); /renten und die
    Herleitung der Auszahlung auf /hochrechnung nennen denselben Satz."""
    import html

    from finctl import renten
    from finctl.forecast import jahre as jm
    from finctl.ledger.db import format_eur
    from finctl.web.routen.annahmen import eingaben_der_hochrechnung

    client, _ = seite
    mit = [q for q in renten.quellen() if q.pruefwert and q.konto]
    if not mit:
        pytest.skip("keine Rentenquelle mit Pruefwert")
    saetze = jm.pruefvergleiche(eingaben_der_hochrechnung())
    seite_renten = html.unescape(client.get("/renten").text)
    seite_hochrechnung = html.unescape(client.get("/hochrechnung").text)
    for q in mit:
        satz = saetze[q.id]
        assert format_eur(q.pruefwert.cents) in satz or "nicht vergleichbar" in satz
        assert satz in seite_renten
        assert satz in seite_hochrechnung
