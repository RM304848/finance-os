"""Die Wirkung gegenueber dem Monat davor (Schritt 3.5).

Zwei Hochrechnungen, zum Stichtag und einen Monat davor, und dazwischen die
Eingaben Gruppe fuer Gruppe getauscht. Alles erfunden, mit runden Zahlen: ein
Haushalt mit Gehalt 3.000, Miete 900 und Konsum 250 im Monat, der jeden Monat
1.850 spart.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from pathlib import Path

import pytest
import yaml

from finctl import bestaende as best
from finctl.forecast import abgleich as ag
from finctl.forecast import jahre as jm
from finctl.forecast import stichtag as st
from finctl.forecast import wirkung as wk
from finctl.forecast import ziel_monat as zm
from finctl.forecast import ziele as zl
from finctl.ledger.db import connect, init_db

# ----------------------------------------------------------------- Hauptbuch


def _konto(c, konto: str) -> None:
    c.execute("INSERT INTO accounts (id, display_name, institution, account_type, "
              "ingest_mode, parser_profile) VALUES (?,?,?,?,?,?)",
              (konto, konto.upper(), "X", "giro", "parsed", "p"))


def _auszuege(c, konto: str, monate: dict[str, dict[str, int]], *, start: int = 0,
              zaehler: int = 0, gegenpartei: dict[str, str] | None = None) -> int:
    """Ein Auszug je Monat. `monate`: "2025-03" -> {Kategorie: Cent}. Gibt den Endsaldo.
    `gegenpartei` nennt je Kategorie die Gegenpartei der Buchungen; ohne sie haben sie
    keine, und es gibt keine Reihen mit Takt."""
    saldo, n = start, zaehler
    for monat, buchungen in sorted(monate.items()):
        erster = date.fromisoformat(monat + "-01")
        summe = sum(buchungen.values())
        sid = c.execute(
            "INSERT INTO statements (account_id, source_path, source_name, file_sha256, "
            "period_start, period_end, balance_start_cents, balance_end_cents, "
            "parser_profile, parser_version, status, imported_at) "
            "VALUES (?,?,?,?,?,?,?,?,'p','1','imported','now')",
            (konto, "x", "x", f"{konto}{monat}", erster.isoformat(),
             ag._month_end(erster).isoformat(), saldo, saldo + summe)).lastrowid
        saldo += summe
        for tag, (kategorie, cents) in enumerate(sorted(buchungen.items()), start=1):
            n += 1
            tid = c.execute(
                "INSERT INTO transactions (account_id, statement_id, booking_date, "
                "amount_cents, counterparty_norm, raw_text, seq_in_statement, dedup_hash, "
                "created_at) VALUES (?,?,?,?,?,'x',?,?,'now')",
                (konto, sid, erster.replace(day=tag).isoformat(), cents,
                 (gegenpartei or {}).get(kategorie), n, f"{konto}{n}")).lastrowid
            c.execute("INSERT INTO splits (transaction_id, amount_cents, mgmt_category_id, "
                      "source, created_at, updated_at) VALUES (?,?,?,'rule','now','now')",
                      (tid, cents, kategorie))
    c.commit()
    return saldo


def _hauptbuch(tmp_path, monate: dict[str, dict[str, int]], *,
               gegenpartei: dict[str, str] | None = None):
    c = connect(init_db(tmp_path / "t.db"))
    _konto(c, "a")
    for kid, kind in (("wohnen", "expense"), ("wohnen/miete", "expense"),
                      ("konsum", "expense"), ("konsum/sonstiges", "expense"),
                      ("konsum/abo_a", "expense"), ("konsum/abo_b", "expense"),
                      ("einkommen", "income"), ("einkommen/gehalt", "income"),
                      ("einkommen/zinsen", "income"),
                      ("investment", "expense"), ("investment/etf", "expense")):
        c.execute("INSERT INTO mgmt_categories (id, parent_id, name, kind, fixkosten) "
                  "VALUES (?,?,?,?,?)", (kid, kid.split("/")[0] if "/" in kid else None,
                                         kid, kind, int(kid == "wohnen/miete")))
    _auszuege(c, "a", monate, gegenpartei=gegenpartei)
    return c


def _monate(von: str, bis: str, buchungen) -> dict[str, dict[str, int]]:
    out, m = {}, date.fromisoformat(von + "-01")
    while m <= date.fromisoformat(bis + "-01"):
        out[f"{m:%Y-%m}"] = dict(buchungen)
        m = ag._plus_monate(m, 1)
    return out


RUHIG = {"konsum/sonstiges": -250_00, "wohnen/miete": -900_00, "einkommen/gehalt": 3_000_00}


def _annahmen(tmp_path, **ueber) -> Path:
    """Eine Annahmedatei aus der Vorgabe, mit anderen Saetzen. Ohne Angabe alles auf null:
    keine Inflation, keine Rendite, keine Steigerung."""
    spec = yaml.safe_load(
        (Path(jm.__file__).parent.parent / "vorgaben" / "assumptions.yaml")
        .read_text(encoding="utf-8"))
    spec["inflation_pa"] = ueber.get("inflation", 0.0)
    spec["kapital"]["rendite_nominal_pa"] = 0.0
    spec["kapital"]["rendite_depot_pa"] = 0.0
    spec["kapital"]["vorabpauschale"]["basiszins_pa"] = 0.0
    spec["erwerbseinkommen"]["gehalt_steigerung_pa"] = 0.0
    # Die Hochrechnung rechnet mit der Untergrenze, nicht mit dem gebuchten Gehalt: gleich
    # setzen, damit sie dem Geld auf dem Konto folgt.
    spec["erwerbseinkommen"]["netto_floor_monatlich_cents"] = RUHIG["einkommen/gehalt"]
    pfad = tmp_path / "annahmen.yaml"
    pfad.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    return pfad


def _heute_ist(monkeypatch, tag: date) -> None:
    """`date.today()` in `jahre` liefert `tag`; alles andere bleibt ein echtes `date`."""
    class Wie(type):
        def __instancecheck__(cls, obj):
            return isinstance(obj, date)

        def __subclasscheck__(cls, sub):
            return issubclass(sub, date)

    class Fest(date, metaclass=Wie):
        def __new__(cls, *a, **k):
            return date(*a, **k)

        @classmethod
        def today(cls):
            return tag

    monkeypatch.setattr(jm, "date", Fest)


# -------------------------------------------------- Eingaben von Hand, ohne Config

def _hermetisch(e: jm.Eingaben) -> jm.Eingaben:
    """Alles, was die Konfiguration des Haushalts beisteuert, weg: Kredite, Renten, Objekte,
    Planzeilen, Zinssaetze. Uebrig bleibt, was das erfundene Hauptbuch hergibt."""
    return dataclasses.replace(
        e, zinssaetze={}, szenarien=(), teilzeit=(), tilgungsplaene=(), rentenquellen=(),
        rentenbeginne={}, rentenbeginn=None, objektprognosen=(),
        planzeilen=jm.Planzeilen(messungen={}, enden=(), verkaeufe=()))


def _paar(c, tmp_path, *, inflation: float = 0.0, depot: int = 0):
    """Eingaben zum Stichtag davor und zum Stichtag, jede mit dem Saldo von damals."""
    davor, jetzt = date(2026, 1, 31), date(2026, 2, 28)
    annahmen = _annahmen(tmp_path, inflation=inflation)

    def lesen(bis):
        return _hermetisch(jm.eingaben(
            c, bis=bis, assumptions=annahmen,
            toepfe={"tagesgeld": st.saldo_zum(c, "a", bis), "depot": depot}))

    return lesen(davor), lesen(jetzt), davor, jetzt


ZIEL = zl.Progress(goal_id="g", name="G", target_cents=1_000_000_00, have_cents=0,
                   due=date(2029, 1, 1))


def _ursache(ursachen, verweis=None, label=None):
    """Die Summe der Ursachen mit diesem Verweis oder Etikett."""
    return sum(u.cents for u in ursachen
               if (verweis is None or u.verweis == verweis)
               and (label is None or u.label == label))


@pytest.fixture
def haushalt(tmp_path):
    """Vierzehn ruhige Monate (2025-01 bis 2026-02): jeden Monat dasselbe."""
    c = _hauptbuch(tmp_path, _monate("2025-01", "2026-02", RUHIG))
    yield c
    c.close()


# ----------------------------------------------------------------- die Rechnung

def test_a_month_that_went_as_expected_moves_nothing(haushalt, tmp_path):
    """Ohne Inflation und Rendite ist die Hochrechnung davor genau eine Monatsrate
    hinter der von heute: das Geld liegt jetzt auf dem Konto, ein Monat weniger
    ist zu sparen. "Der Monat" ist dann null, und es gibt keine Ursache."""
    davor, heute, von, bis = _paar(haushalt, tmp_path)
    w0, w1, ursachen = wk.tauschen(davor, heute, wk.Messung([ZIEL]), von, bis)
    assert w0["g"] == w1["g"]
    assert ursachen["g"] == []


def test_the_month_stays_close_to_zero_with_inflation(haushalt, tmp_path):
    """Mit Inflation ist die Messung einen Monat juenger und wird kuerzer fortgeschrieben:
    jedes kuenftige Jahr rechnet seine Kosten mit einem Zwoelftel Inflation weniger. Das
    ist die Toleranz -- hier 2 % von 13.800 Kosten im Jahr, ein Zwoelftel davon, drei
    Jahre bis zum Stichdatum, also gut 60 Euro (die Rundung kommt aus den Restmonaten) --
    und sie bleibt klein gegen die Monatsrate (1.850): unter einem Viertel."""
    davor, heute, von, bis = _paar(haushalt, tmp_path, inflation=0.02)
    ursachen = wk.tauschen(davor, heute, wk.Messung([ZIEL]), von, bis)[2]
    monat = _ursache(ursachen["g"], label="Der Monat")
    assert 0 < monat < 1_850_00 / 4
    assert [u.label for u in ursachen["g"]] == ["Der Monat"]


def test_the_causes_add_up_to_exactly_the_difference(tmp_path):
    """Ein sparsamer letzter Monat: in beiden Tempi ist die Summe der Ursachen genau die
    Differenz der zwei Hochrechnungen."""
    c = _hauptbuch(tmp_path, {**_monate("2025-01", "2026-01", RUHIG),
                              "2026-02": {**RUHIG, "konsum/sonstiges": -50_00}})
    try:
        annahmen = _annahmen(tmp_path, inflation=0.02)
        for tempo in jm.TEMPI:
            davor, heute = (_hermetisch(jm.eingaben(
                c, bis=bis, assumptions=annahmen, tempo=tempo,
                toepfe={"tagesgeld": st.saldo_zum(c, "a", bis)}))
                for bis in (date(2026, 1, 31), date(2026, 2, 28)))
            w0, w1, ursachen = wk.tauschen(davor, heute, wk.Messung([ZIEL]),
                                           date(2026, 1, 31), date(2026, 2, 28))
            assert w1["g"] != w0["g"]
            assert sum(u.cents for u in ursachen["g"]) == w1["g"] - w0["g"], tempo
            assert {u.verweis for u in ursachen["g"]} >= {"konsum"}
            assert "Der Monat" in {u.label for u in ursachen["g"]}
    finally:
        c.close()


def test_the_last_swap_ends_at_the_inputs_of_today(haushalt, tmp_path):
    davor, heute, von, bis = _paar(haushalt, tmp_path, inflation=0.02)
    messen = wk.Messung([ZIEL])
    _, w1, _ = wk.tauschen(davor, heute, messen, von, bis)
    assert w1 == messen(heute)


def test_a_swap_that_changes_nothing_is_no_cause(haushalt, tmp_path):
    davor, _, von, bis = _paar(haushalt, tmp_path)
    # Nur der Bestand anders: genau eine Ursache.
    anders = dataclasses.replace(davor, monat=dataclasses.replace(
        davor.monat, tagesgeld=davor.monat.tagesgeld + 100_00))
    _, _, ursachen = wk.tauschen(anders, davor, wk.Messung([ZIEL]), von, bis)
    assert [u.label for u in ursachen["g"]] == ["Der Monat"]
    # Beide gleich: keine.
    _, _, ursachen = wk.tauschen(davor, davor, wk.Messung([ZIEL]), von, bis)
    assert ursachen["g"] == []


def test_a_block_with_no_effect_is_not_listed(haushalt, tmp_path):
    _, heute, von, bis = _paar(haushalt, tmp_path)
    # Die Miete steht in einem anderen Block als der Konsum; nur der Konsum aendert sich.
    mehr = dataclasses.replace(
        heute, base={**heute.base, "konsum": {k: v * 2 for k, v in heute.base["konsum"].items()}})
    _, _, ursachen = wk.tauschen(mehr, heute, wk.Messung([ZIEL]), von, bis)
    assert [u.verweis for u in ursachen["g"]] == ["konsum"]
    assert ursachen["g"][0].label.startswith("Tempo: ")
    assert ursachen["g"][0].quelle == "gemessen"


def test_less_consumption_weighs_more_at_the_pace_of_the_last_three_months(tmp_path):
    """Ein sparsamer letzter Monat: im Schnitt von zwoelf ein Zwoelftel, im Tempo der
    letzten drei Monate ein Drittel. Genau dieser Unterschied ist der Grund fuer Jüngst."""
    c = _hauptbuch(tmp_path, {**_monate("2025-01", "2026-01", RUHIG),
                              "2026-02": {**RUHIG, "konsum/sonstiges": -50_00}})
    try:
        annahmen = _annahmen(tmp_path)
        effekt = {}
        for tempo in jm.TEMPI:
            ein = {}
            for bis in (date(2026, 1, 31), date(2026, 2, 28)):
                ein[bis] = _hermetisch(jm.eingaben(
                    c, bis=bis, assumptions=annahmen, tempo=tempo,
                    toepfe={"tagesgeld": st.saldo_zum(c, "a", bis)}))
            _, _, ursachen = wk.tauschen(ein[date(2026, 1, 31)], ein[date(2026, 2, 28)],
                                         wk.Messung([ZIEL]), date(2026, 1, 31),
                                         date(2026, 2, 28))
            effekt[tempo] = _ursache(ursachen["g"], verweis="konsum")
        assert effekt["schnitt"] > 0
        assert effekt["juengst"] > 3 * effekt["schnitt"]
    finally:
        c.close()


def test_a_field_no_cause_swaps_must_be_equal(haushalt, tmp_path):
    davor, heute, von, bis = _paar(haushalt, tmp_path)
    anders = dataclasses.replace(
        heute, annahmen=dataclasses.replace(heute.annahmen, inflation=0.5))
    with pytest.raises(ValueError, match="annahmen"):
        wk.tauschen(davor, anders, wk.Messung([ZIEL]), von, bis)
    anders = dataclasses.replace(heute, grenze=123)
    with pytest.raises(ValueError, match="grenze"):
        wk.tauschen(davor, anders, wk.Messung([ZIEL]), von, bis)


def test_every_field_of_the_inputs_is_swapped_or_checked():
    """Neues Feld in `Eingaben` ohne Gruppe: dann gilt es als "muss gleich sein" und
    bricht die Wirkung, bis jemand entscheidet, wohin es gehoert."""
    namen = {f.name for f in dataclasses.fields(jm.Eingaben)}
    assert namen >= wk.GETAUSCHT


# -------------------------------------------------------- der Weg durch die Seite

#: `balances.yaml` nach dem Tippen im Maerz: das Depot steht bei 12.000. Den Verlauf davor setzt
#: die Fixture `seite` (`monkeypatch.setitem`).
BASIS = {"as_of": date(2026, 2, 1), "balances": [
    {"account_id": "a", "name": "A", "kind": "giro"},
    {"account_id": "depot-a", "name": "Depot A", "cents": 12_000_00,
     "as_of": "2026-03-02", "kind": "depot"}],
    "obligations": []}

ZIELE = {"ziele": [
    {"id": "g", "name": "G", "cents": 1_000_000_00, "stichtag": "2029-01-01"},
    {"id": "offen", "name": "Ohne Termin", "cents": 50_000_00}]}


@pytest.fixture
def seite(haushalt, tmp_path, monkeypatch):
    """Das Hauptbuch bis Ende 02/2026, heute der 4. Maerz, ein getipptes Depot mit Verlauf."""
    _heute_ist(monkeypatch, date(2026, 3, 4))

    def verlauf(eintraege):
        monkeypatch.setitem(BASIS, "verlauf", eintraege)

    verlauf({"depot-a": {"2026-02": {"cents": 10_000_00, "as_of": "2026-02-03"},
                         "2026-03": {"cents": 12_000_00, "as_of": "2026-03-02"}}})
    return haushalt, _annahmen(tmp_path, inflation=0.02), verlauf


def test_the_whole_way_over_the_page_adds_up_in_both_paces(seite):
    c, annahmen, _ = seite
    je_tempo = wk.wirkung_je_tempo(c, ZIELE, basis=BASIS, assumptions=annahmen)
    assert set(je_tempo) == set(jm.TEMPI)
    for tempo, liste in je_tempo.items():
        g = next(w for w in liste if w.ziel.goal_id == "g")
        assert g.fehlt == () and g.satz is None
        assert (g.stichtag, g.davor) == (date(2026, 2, 28), date(2026, 1, 31))
        assert g.aenderung == sum(u.cents for u in g.ursachen), tempo
        # Das Depot ist um 2.000 gestiegen, ohne Buchung: der Monat traegt es.
        assert _ursache(g.ursachen, label="Der Monat") > 1_500_00, tempo
        assert g.balken_aenderung is not None


def test_the_value_of_today_is_the_one_the_goals_page_shows(seite):
    from finctl.forecast import ziele as zl_

    c, annahmen, _ = seite
    bestand = best.zusammenfuehren(c, BASIS)
    for tempo in jm.TEMPI:
        e = jm.eingaben(c, tempo=tempo, assumptions=annahmen,
                        opening_cents=zl_.liquid_cents(bestand), toepfe=zl_.toepfe(bestand),
                        depot_gewinn_cents=zl_.depot_gewinn(bestand),
                        puffer_cents=zl_.puffer_cents(ZIELE),
                        policen_je_konto=zl_.policen_je_konto(bestand),
                        tagesgeld_je_konto=zl_.tagesgeld_je_konto(bestand))
        lauf = jm.rechnen(e, end_year=2045)
        prog = next(p for p in zl_.progress(ZIELE, bestand) if p.goal_id == "g")
        w = wk.wirkung(c, ZIELE, tempo=tempo, basis=BASIS, assumptions=annahmen)
        assert next(x for x in w if x.ziel.goal_id == "g").heute == (
            zl_.hochgerechnet(lauf, prog).cents)


def test_a_goal_without_a_date_has_only_its_bar(seite):
    c, annahmen, _ = seite
    offen = next(w for w in wk.wirkung(c, ZIELE, tempo="schnitt", basis=BASIS,
                                       assumptions=annahmen)
                 if w.ziel.goal_id == "offen")
    assert (offen.vorher, offen.heute, offen.ursachen) == (None, None, [])
    assert offen.aenderung is None
    # Der Balken: das Depot von heute (12.000) gegen das von damals (10.000),
    # dazu der Saldo des Kontos.
    assert offen.balken_aenderung == (
        12_000_00 + st.saldo_zum(c, "a", date(2026, 2, 28))
        - 10_000_00 - st.saldo_zum(c, "a", date(2026, 1, 31)))


def test_a_goal_the_monthly_model_measures_has_no_causes_of_the_yearly_model(seite, monkeypatch):
    c, annahmen, _ = seite
    monkeypatch.setattr(zm, "misst_das_monatsmodell", lambda p, merged, monat: p.goal_id == "g")
    for tempo in jm.TEMPI:
        liste = wk.wirkung(c, ZIELE, tempo=tempo, basis=BASIS, assumptions=annahmen)
        g = next(w for w in liste if w.ziel.goal_id == "g")
        assert g.im_monatsmodell and g.modell == zm.MONATSMODELL
        assert (g.vorher, g.heute, g.aenderung, g.ursachen) == (None, None, None, [])
        assert g.balken_aenderung is not None, "der Balken bleibt beim Bestand"
        offen = next(w for w in liste if w.ziel.goal_id == "offen")
        assert not offen.im_monatsmodell


def test_a_goal_the_yearly_model_measures_keeps_its_causes(seite):
    c, annahmen, _ = seite
    g = next(w for w in wk.wirkung(c, ZIELE, tempo="schnitt", basis=BASIS, assumptions=annahmen)
             if w.ziel.goal_id == "g")
    assert g.modell == zm.JAHRESRECHNUNG and g.ursachen
    assert g.aenderung == sum(u.cents for u in g.ursachen)


def test_a_stand_missing_from_back_then_gives_no_causes_but_a_sentence(seite):
    c, annahmen, verlauf = seite
    verlauf({})
    for tempo in jm.TEMPI:
        g = next(w for w in wk.wirkung(c, ZIELE, tempo=tempo, basis=BASIS,
                                       assumptions=annahmen) if w.ziel.goal_id == "g")
        assert (g.vorher, g.ursachen, g.balken_vorher) == (None, [], None)
        assert g.heute is not None
        assert g.fehlt == ("Depot A",)
        # Im naechsten Abschluss eingetragen, ist er ab Ende 03/2026 der Vormonat.
        assert g.ab == date(2026, 3, 31)
        assert "Depot A" in g.satz and "01/2026" in g.satz and "03/2026" in g.satz


def test_a_ledger_younger_than_the_month_before_has_nothing_to_compare(tmp_path, monkeypatch):
    c = _hauptbuch(tmp_path, {"2026-02": RUHIG})
    try:
        monkeypatch.setattr(best, "CONFIG_DIR", tmp_path)
        _heute_ist(monkeypatch, date(2026, 3, 4))
        g = next(w for w in wk.wirkung(
            c, ZIELE, tempo="schnitt", assumptions=_annahmen(tmp_path),
            basis={"balances": [{"account_id": "a", "name": "A", "kind": "giro"}],
                   "obligations": []}) if w.ziel.goal_id == "g")
        assert g.fehlt == ("Hauptbuch",) and g.vorher is None and g.ursachen == []
        assert g.ab == date(2026, 3, 31)
        assert "Hauptbuch" in g.satz
    finally:
        c.close()


def test_no_ledger_no_comparison(tmp_path):
    c = connect(init_db(tmp_path / "leer.db"))
    try:
        assert wk.wirkung_je_tempo(c, ZIELE, basis={"balances": [], "obligations": []}) == {
            "schnitt": [], "juengst": []}
    finally:
        c.close()


# --------------------------------------------- Konten, die spaeter eingelesen wurden

def test_an_account_read_in_later_is_missing_unless_it_started_empty(tmp_path, monkeypatch):
    """Ein Konto, dessen erster Auszug nach dem Stichtag davor beginnt, erschiene sonst als
    grosser Zufluss. Beginnt er mit Saldo null, war es wirklich leer."""
    c = _hauptbuch(tmp_path, _monate("2025-11", "2026-02", RUHIG))
    try:
        _konto(c, "b")
        basis = {"balances": [{"account_id": "a", "name": "A", "kind": "giro"},
                              {"account_id": "b", "name": "B", "kind": "tagesgeld"}],
                 "obligations": []}
        _auszuege(c, "b", {"2026-02": {"einkommen/gehalt": 1_000_00}}, start=5_000_00,
                  zaehler=1000)
        z = best.zum(c, date(2026, 1, 31), basis)
        assert z["fehlt"] == ["B"]
        assert z["fehlt_grund"] == {"B": "konto"}
        # Ab dem naechsten Stichtag haben beide Stichtage Auszuege.
        assert z["fehlt_ab"] == date(2026, 3, 31)
        assert {r["account_id"] for r in z["balances"]} == {"a"}
        # Heute (Ende Februar) ist das Konto da.
        assert best.zum(c, date(2026, 2, 28), basis)["fehlt"] == []
        # Anfangsstand null: es war leer, nicht unbekannt.
        c.execute("UPDATE statements SET balance_start_cents = 0, "
                  "balance_end_cents = 100000 WHERE account_id = 'b'")
        z = best.zum(c, date(2026, 1, 31), basis)
        assert z["fehlt"] == [] and z["fehlt_ab"] is None
        assert {r["account_id"]: r["cents"] for r in z["balances"]}["b"] == 0
    finally:
        c.close()


def test_the_default_for_a_stand_with_a_later_entry_is_that_entries_month(tmp_path, monkeypatch):
    c = _hauptbuch(tmp_path, _monate("2025-11", "2026-02", RUHIG))
    try:
        basis = {"as_of": date(2026, 1, 5), "balances": [
            {"account_id": "depot-a", "name": "Depot A", "cents": 10_000_00,
             "as_of": date(2026, 1, 5), "kind": "depot"}], "obligations": [],
            "verlauf": {"depot-a": {"2026-04": {"cents": 1, "as_of": "2026-04-02"}}}}
        z = best.zum(c, date(2026, 1, 31), basis)
        assert z["fehlt"] == ["Depot A"]
        assert z["fehlt_ab"] == date(2026, 4, 30)
    finally:
        c.close()


# ------------------------------------------------ die Kategorien einer Tempo-Ursache

def _eingaben_je_tempo(c, tmp_path, tempo, *, inflation: float = 0.0,
                       stichtage=(date(2026, 1, 31), date(2026, 2, 28))):
    annahmen = _annahmen(tmp_path, inflation=inflation)
    return [_hermetisch(jm.eingaben(c, bis=bis, assumptions=annahmen, tempo=tempo,
                                    toepfe={"tagesgeld": st.saldo_zum(c, "a", bis)}))
            for bis in stichtage]


def test_a_tempo_cause_names_its_categories_and_the_months_that_moved(tmp_path):
    """Ein sparsamer letzter Monat. Im Schnitt faellt der alteste von zwoelf Monaten
    heraus, im Tempo der letzten drei Monate der alteste von drei; es kommt jeweils der neue
    Monat dazu. Was sich nicht geaendert hat (die Miete), steht nicht da."""
    c = _hauptbuch(tmp_path, {**_monate("2025-01", "2026-01", RUHIG),
                              "2026-02": {**RUHIG, "konsum/sonstiges": -50_00}})
    try:
        erwartet = {
            "schnitt": (12, -3_000_00, -2_800_00, date(2025, 2, 1)),
            "juengst": (3, -3_000_00, -2_200_00, date(2025, 11, 1)),
        }
        for tempo, (monate, vorher, nachher, raus) in erwartet.items():
            davor, heute = _eingaben_je_tempo(c, tmp_path, tempo)
            wandel = wk.kategorien(davor, heute)
            assert set(wandel) == {"konsum"}, tempo
            [k] = wandel["konsum"]
            assert (k.kategorie, k.vorher, k.nachher) == ("konsum/sonstiges", vorher, nachher)
            assert k.heraus == (wk.MonatBetrag(raus, -250_00, 1),), tempo
            assert k.dazu == (wk.MonatBetrag(date(2026, 2, 1), -50_00, 1),), tempo
            # Die Monate erklaeren die Aenderung des Jahreswerts.
            assert k.aenderung == round((-50_00 + 250_00) * 12 / monate)
    finally:
        c.close()


def _rutschende_zahlung(c, gegenpartei: str | None = None) -> None:
    """Eine dreizehnte Zahlung der Miete, am Monatsende des letzten Monats."""
    sid = c.execute("SELECT id FROM statements WHERE period_start = '2026-02-01'"
                    ).fetchone()[0]
    tid = c.execute(
        "INSERT INTO transactions (account_id, statement_id, booking_date, "
        "amount_cents, counterparty_norm, raw_text, seq_in_statement, dedup_hash, "
        "created_at) VALUES ('a', ?, '2026-02-28', -90000, ?, 'x', 99, "
        "'nochmal', 'now')", (sid, gegenpartei)).lastrowid
    c.execute("INSERT INTO splits (transaction_id, amount_cents, mgmt_category_id, "
              "source, created_at, updated_at) VALUES (?, -90000, 'wohnen/miete', "
              "'rule', 'now', 'now')", (tid,))
    c.commit()


def test_a_payment_without_a_series_that_slid_over_the_month_end_shows_as_two_bookings(
        tmp_path):
    """Ohne Gegenpartei gibt es keine Reihe: Dreizehn Zahlungen in zwoelf Monaten, der
    Jahreswert steigt, obwohl sich kein Betrag geaendert hat. Die Zahl der Buchungen im
    neuen Monat zeigt es."""
    c = _hauptbuch(tmp_path, _monate("2025-01", "2026-02", RUHIG))
    try:
        _rutschende_zahlung(c)
        davor, heute = _eingaben_je_tempo(c, tmp_path, "schnitt")
        wandel = wk.kategorien(davor, heute)
        [k] = wandel["fixkosten"]
        assert k.kategorie == "wohnen/miete"
        assert (k.vorher, k.nachher) == (-10_800_00, -11_700_00)
        assert k.heraus == (wk.MonatBetrag(date(2025, 2, 1), -900_00, 1),)
        assert k.dazu == (wk.MonatBetrag(date(2026, 2, 1), -1_800_00, 2),)
        assert k.reihen == ()
        assert (k.rest_vorher, k.rest_nachher) == (-10_800_00, -11_700_00)
    finally:
        c.close()


def test_a_payment_of_a_series_that_slid_over_the_month_end_moves_nothing(tmp_path):
    """Dieselben dreizehn Zahlungen, aber die Miete ist eine Reihe mit Takt: Sie zaehlt
    ihre Termine, nicht die Monate des Fensters, und der Jahreswert bleibt bei zwoelf."""
    c = _hauptbuch(tmp_path, _monate("2025-01", "2026-02", RUHIG),
                   gegenpartei={"wohnen/miete": "vermieter"})
    try:
        _rutschende_zahlung(c, "vermieter")
        davor, heute = _eingaben_je_tempo(c, tmp_path, "schnitt")
        assert davor.base["fixkosten"]["wohnen/miete"] == -10_800_00
        assert heute.base["fixkosten"]["wohnen/miete"] == -10_800_00
        assert "fixkosten" not in wk.kategorien(davor, heute)
    finally:
        c.close()


def test_a_category_splits_into_the_series_that_moved_and_the_rest(tmp_path):
    """Eine Reihe endet, eine beginnt, die Miete bleibt. Die Reihen nennen ihren Grund,
    der Rest die Monate; die Summe beider ist die Aenderung der Kategorie."""
    gegenpartei = {"wohnen/miete": "vermieter", "konsum/abo_a": "kino", "konsum/abo_b": "neu"}
    monate = _monate("2025-01", "2026-01", RUHIG)
    for m, buchungen in monate.items():
        # Endet im November: Ende Januar fehlen zwei Termine, das beendet sie;
        # Ende Dezember fehlt einer, und sie laeuft noch.
        if m <= "2025-11":
            buchungen["konsum/abo_a"] = -15_00
        if m >= "2025-11":
            buchungen["konsum/abo_b"] = -10_00
    c = _hauptbuch(tmp_path, monate, gegenpartei=gegenpartei)
    try:
        davor, heute = _eingaben_je_tempo(
            c, tmp_path, "schnitt", stichtage=(date(2025, 12, 31), date(2026, 1, 31)))
        wandel = wk.kategorien(davor, heute)
        assert set(wandel) == {"konsum"}
        je_kat = {k.kategorie: k for k in wandel["konsum"]}
        assert set(je_kat) == {"konsum/abo_a", "konsum/abo_b"}

        kino = je_kat["konsum/abo_a"]
        assert (kino.vorher, kino.nachher) == (-180_00, 0)
        assert kino.reihen == (wk.ReiheWandel(
            "kino", -180_00, 0, "beendet", 1, None, -15_00, None),)
        assert kino.reihen[0].beschreibung == "beendet, monatlich, bisher je Termin −15,00 €"
        assert (kino.rest_vorher, kino.rest_nachher) == (0, 0)

        neu = je_kat["konsum/abo_b"]
        assert (neu.vorher, neu.nachher) == (-20_00, -120_00)
        assert neu.reihen == (wk.ReiheWandel(
            "neu", 0, -120_00, "begonnen", None, 1, None, -10_00),)
        assert neu.reihen[0].beschreibung == "begonnen, monatlich, je Termin −10,00 €"
        # Vorher zwei Zahlungen im Rest, aufs Jahr; heute stecken sie in der Reihe.
        assert (neu.rest_vorher, neu.rest_nachher) == (-20_00, 0)
        for k in (kino, neu):
            assert k.aenderung == (sum(r.aenderung for r in k.reihen)
                                   + k.rest_nachher - k.rest_vorher)
    finally:
        c.close()


def test_a_cause_gets_its_categories_on_every_goal_in_both_paces(seite):
    c, annahmen, _ = seite
    for tempo, liste in wk.wirkung_je_tempo(c, ZIELE, basis=BASIS, assumptions=annahmen).items():
        for w in liste:
            assert set(w.kategorien) <= set(jm.FROM_BASE), tempo
        # Alle Ziele zeigen dieselben; eine Ursache "Tempo: ..." findet dort ihre Kategorien.
        g = next(w for w in liste if w.ziel.goal_id == "g")
        for u in g.ursachen:
            if u.label.startswith("Tempo: "):
                assert g.kategorien[u.verweis], tempo


def test_percent_of_the_goal_before_and_after(seite):
    c, annahmen, _ = seite
    g = next(w for w in wk.wirkung(c, ZIELE, tempo="schnitt", basis=BASIS, assumptions=annahmen)
             if w.ziel.goal_id == "g")
    assert g.pct_heute == pytest.approx(100.0 * g.heute / 1_000_000_00)
    assert g.pct_vorher == pytest.approx(100.0 * g.vorher / 1_000_000_00)
    offen = next(w for w in wk.wirkung(c, ZIELE, tempo="schnitt", basis=BASIS,
                                       assumptions=annahmen) if w.ziel.goal_id == "offen")
    assert (offen.pct_vorher, offen.pct_heute) == (None, None)


# ------------------------------------------------------------- die Hinweise zum Monat

def _seite_mit(c, tmp_path, monkeypatch, eintraege):
    """Wie die Fixture `seite`, fuer ein Hauptbuch, das der Test selbst gebaut hat."""
    _heute_ist(monkeypatch, date(2026, 3, 4))
    monkeypatch.setitem(BASIS, "verlauf", eintraege)
    return _annahmen(tmp_path, inflation=0.02)


def test_the_hints_split_the_depot_into_deposits_and_course(tmp_path, monkeypatch):
    """Das Depot stieg von 10.000 auf 12.000, 200 davon ueber eine Buchung unter
    investment/: die Kursbewegung sind 1.800. Zinsen im Monat sind gebucht, die Rechnung
    rechnet sie selbst, und die Seite sagt das (`gerechnet_gebucht`)."""
    c = _hauptbuch(tmp_path, {**_monate("2025-01", "2026-01", RUHIG),
                              "2026-02": {**RUHIG, "investment/etf": -200_00,
                                          "einkommen/zinsen": 5_00}})
    try:
        annahmen = _seite_mit(c, tmp_path, monkeypatch, {"depot-a": {
            "2026-02": {"cents": 10_000_00, "as_of": "2026-02-03"}}})
        v = wk.vergleichen(c, ZIELE, basis=BASIS, assumptions=annahmen, mit_hinweisen=True)
        h = v.hinweise
        assert h.monat == date(2026, 2, 1) and h.treffer.monat == h.monat
        assert h.kurs == wk.Kurs(10_000_00, 12_000_00, -200_00)
        assert (h.kurs.aenderung, h.kurs.kursbewegung) == (2_000_00, 1_800_00)
        assert h.gerechnet_gebucht
        # Die Zeile des Treffer-Checks ist die, die `treffer.jahresbasis` fuer den Monat gibt.
        assert h.treffer.ist["konsum"] == -250_00
        # Ohne die Hinweise zu verlangen, rechnet nichts davon.
        assert wk.vergleichen(c, ZIELE, basis=BASIS, assumptions=annahmen).hinweise is None
    finally:
        c.close()


def test_a_month_without_zinsen_or_depot_has_no_such_hints(seite):
    c, annahmen, verlauf = seite
    h = wk.vergleichen(c, ZIELE, basis=BASIS, assumptions=annahmen, mit_hinweisen=True).hinweise
    assert h.kurs == wk.Kurs(10_000_00, 12_000_00, 0)
    assert not h.gerechnet_gebucht
    # Ohne Staende von damals gibt es auch keine Hinweise: der Satz steht statt der Zahlen.
    verlauf({})
    assert wk.vergleichen(c, ZIELE, basis=BASIS, assumptions=annahmen,
                          mit_hinweisen=True).hinweise is None


# ------------------------------------------------------------------ die Rentenluecke

def test_the_pension_gap_joins_the_goals_with_one_amount_for_both_paces(seite, monkeypatch):
    c, annahmen, _ = seite
    gesehen = {}

    def luecke(ziele, lauf, e):
        gesehen["bis"] = lauf.years[-1].year
        return {**ziele, "ziele": [*ziele["ziele"], {
            "id": "luecke", "name": "L", "cents": 500_000_00, "stichtag": "2031-01-01",
            "fest": True}]}, None

    monkeypatch.setattr(wk.rl, "mit_ziel", luecke)
    v = wk.vergleichen(c, ZIELE, basis=BASIS, assumptions=annahmen, mit_luecke=True)
    for tempo, liste in v.je_tempo.items():
        z = next(w for w in liste if w.ziel.goal_id == "luecke")
        assert z.ziel.target_cents == 500_000_00, tempo
        assert z.aenderung == sum(u.cents for u in z.ursachen), tempo
    assert gesehen["bis"] >= 2045
    # Ohne den Wunsch bleiben die Ziele, wie sie sind.
    ohne = wk.vergleichen(c, ZIELE, basis=BASIS, assumptions=annahmen)
    assert "luecke" not in {w.ziel.goal_id for w in ohne.je_tempo["schnitt"]}
    with pytest.raises(ValueError, match="Schnitt"):
        wk.vergleichen(c, ZIELE, tempi=("juengst",), basis=BASIS, assumptions=annahmen,
                       mit_luecke=True)
