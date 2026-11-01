"""Die Skripte der Vorlagen in einem echten Browser (Neufassung, Schritt 0).

Rund dreitausend Zeilen Skript stehen in den Vorlagen, und die Suite rendert
nur HTML: kein Test fuehrte sie aus. Dass das zaehlt, zeigt der Fehler in
`finctl/web/basis.py`, bei dem Speichern ohne Aenderung einen Betrag hundertmal
so gross machte -- ein Fehler zwischen Seite und Server, den keiner der beiden
Teile allein zeigt.

Geprueft wird nur, was Daten schreibt, und nur an dem, was ein Nutzer sieht:

* **Speichern ohne Aenderung aendert keine Datei**, je Formular.
* **Betragseingabe**: deutsche und Python-Schreibweise, Tausenderpunkte, negative
  und leere Werte, vom Feld bis in die Datei.
* **Abläufe mit Zustand**: Klammer an und aus, Auswahl im Kombifeld, der
  Klappzustand nach dem Neuladen.

Gefunden wird ueber Feldnamen, Kennungen und Rollen, nicht ueber sichtbaren
Text -- sonst bricht jede Umbenennung nach dem Glossar (Schritt 6) einen Test
aus dem falschen Grund. Layout und Farben bleiben bei `tests/test_design.py`.

Der Browser spricht mit einem echten Server (uvicorn in einem Thread) auf der
Kopie der Daten, in der die ganze Suite arbeitet. Jeder Test sichert `config/`
und stellt es zurueck.

LAEUFT ALLEIN: `pytest -m browser -n 0`, vor jedem Commit, der Vorlagen oder
Routen aendert. Im parallelen Gesamtlauf teilten sich die Browser die Kerne mit
der Suite, Seiten brauchten dort Minuten statt Sekunden, und der Lauf hing.
Deshalb nimmt `addopts` in `pyproject.toml` die Markierung `browser` aus.

GEWARTET WIRD AUF DEN SERVER, NIE AUF DIE UHR. Nach einem Klick auf die Antwort
der Anfrage, vor dem Zurueckstellen darauf, dass der Server nichts mehr
bearbeitet (`_ruhig`). Feste Pausen waren zu kurz, wenn der Rechner voll war,
und zu lang in jedem anderen Fall.
"""

from __future__ import annotations

import re
import socket
import sqlite3
import threading
import time
from datetime import timedelta
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as Zeitueberschreitung

DB = Path("data/finance.db")
pytestmark = [pytest.mark.langsam, pytest.mark.browser,
              pytest.mark.skipif(not DB.exists(), reason="kein Hauptbuch")]

#: Anfragen, die der Server gerade bearbeitet. Gezaehlt im Server selbst: Der
#: Browser weiss nicht, ob eine abgebrochene Anfrage dort noch laeuft.
_LAUFEND = [0]


def _gezaehlt(app):
    """Die App, und jede HTTP-Anfrage zaehlt, solange sie bearbeitet wird."""
    async def gezaehlt(scope, receive, send):
        if scope["type"] != "http":
            return await app(scope, receive, send)
        _LAUFEND[0] += 1
        try:
            return await app(scope, receive, send)
        finally:
            _LAUFEND[0] -= 1
    return gezaehlt


def _ruhig(sekunden: float = 120.0) -> None:
    """Wartet, bis der Server eine Weile nichts bearbeitet hat.

    Das Zurueckstellen der Datenbank unter einer Anfrage, die gerade liest,
    hat den vollen Lauf haengen lassen.
    """
    ende = time.monotonic() + sekunden
    still_seit = None
    while time.monotonic() < ende:
        if _LAUFEND[0]:
            still_seit = None
        elif still_seit is None:
            still_seit = time.monotonic()
        elif time.monotonic() - still_seit >= 0.3:
            return
        time.sleep(0.05)
    pytest.fail(f"der Server bearbeitet nach {sekunden:.0f} s noch {_LAUFEND[0]} Anfragen")


@pytest.fixture(scope="module")
def adresse():
    """Die App, wie `finctl serve` sie startet -- nur in diesem Prozess."""
    import uvicorn

    from finctl.web.server import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(_gezaehlt(app), host="127.0.0.1", port=port,
                                           log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    else:
        pytest.fail("der Server kam nicht hoch")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(10)


def _dateien() -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(Path("config").glob("*.yaml"))}


@pytest.fixture
def config(tmp_path, page: Page, adresse):
    """Der Stand von `config/` und des Hauptbuchs vorher; danach wird zurueckgestellt.

    Das Hauptbuch gehoert dazu: eine gespeicherte Aufteilung steht in der
    Datenbank, und die Tests eines Prozesses teilen sich diese Kopie.
    """
    vorher = _dateien()
    sicherung = tmp_path / "vorher.db"
    quelle = sqlite3.connect(DB)
    ziel = sqlite3.connect(sicherung)
    quelle.backup(ziel)
    quelle.close()
    ziel.close()
    yield vorher
    # Erst die Seite verlassen: mancher Knopf laedt sie nach 700 ms neu. Dann
    # warten, bis der Server fertig ist, und erst danach zurueckstellen.
    page.goto("about:blank")
    _ruhig()
    jetzt = _dateien()
    for name in jetzt.keys() - vorher.keys():
        (Path("config") / name).unlink()
    for name, inhalt in vorher.items():
        if jetzt.get(name) != inhalt:
            (Path("config") / name).write_bytes(inhalt)
    quelle = sqlite3.connect(sicherung)
    ziel = sqlite3.connect(DB)
    quelle.backup(ziel)
    quelle.close()
    ziel.close()


@pytest.fixture
def seite(page: Page, adresse):
    """Eine Seite, die jeden Skriptfehler zum Testfehler macht."""
    # Die Suite laeuft parallel; /annahmen rechnet beim Laden und braucht dann
    # laenger als die 30 Sekunden, die Playwright vorgibt.
    page.set_default_timeout(90_000)
    expect.set_options(timeout=20_000)
    fehler: list[str] = []
    page.on("pageerror", lambda e: fehler.append(str(e)))
    # Eine Antwort mit 400 ist oft gewollt (der Server lehnt eine mehrdeutige Zahl ab);
    # Chrome meldet sie trotzdem als Konsolenfehler. Zaehlen soll, was kaputt ist.
    page.on("console", lambda m: fehler.append(m.text)
            if m.type == "error" and "Failed to load resource" not in m.text else None)
    page.on("response", lambda r: fehler.append(f"{r.status} {r.url}")
            if r.status >= 500 or (r.status == 404 and "favicon" not in r.url) else None)
    page.on("dialog", lambda d: d.accept())
    page.goto_ = lambda pfad: page.goto(adresse + pfad)
    yield page
    assert not fehler, f"Skriptfehler im Browser: {fehler}"


def _buchung(vorzeichen: str = "<") -> tuple[int, int]:
    db = sqlite3.connect(DB)
    zeile = db.execute("SELECT id, amount_cents FROM transactions "
                       f"WHERE amount_cents {vorzeichen} -100 ORDER BY id LIMIT 1").fetchone()
    db.close()
    if zeile is None:
        pytest.skip("keine Buchung")
    return zeile


# ----------------------------------------------------------------- /split

def _betraege(seite: Page, *werte: str) -> None:
    """Die Betragsfelder der Teile setzen; weitere Teile werden geleert."""
    felder = seite.locator("#parts input.amt")
    for i in range(felder.count()):
        felder.nth(i).fill(werte[i] if i < len(werte) else "")


def test_split_summe_kommt_vom_server_und_liest_tausenderpunkte(seite, config):
    tid, _ = _buchung()
    seite.goto_(f"/tx/{tid}")
    _betraege(seite, "1.234,56")
    expect(seite.locator("#balance")).to_contain_text("Teile zusammen 1.234,56 €")   # nicht 1,23
    _betraege(seite, "1,234.56")
    expect(seite.locator("#balance")).to_contain_text("mehrdeutig")
    _betraege(seite, "-7,5")
    expect(seite.locator("#balance")).to_contain_text("Teile zusammen -7,50 €")
    _betraege(seite, "")
    expect(seite.locator("#balance")).to_contain_text("Teile zusammen 0,00 €")


def test_split_gleichmaessig_verteilt_und_speichert_nichts(seite, config):
    tid, _ = _buchung()
    seite.goto_(f"/tx/{tid}")
    if seite.locator("#parts input.amt").count() < 2:
        seite.get_by_role("button", name="+ Teil").click()
    # Erst leeren: Ergaben die Teile die Buchung schon (eine Regel deckt den
    # ganzen Betrag, dazu ein leerer Teil), stand "geht genau auf" vor dem
    # Klick da, und gelesen wurde, bevor die Verteilung ankam.
    _betraege(seite)
    expect(seite.locator("#balance")).to_contain_text("Differenz")
    seite.get_by_role("button", name="gleichmäßig verteilen").click()
    expect(seite.locator("#balance")).to_contain_text("geht genau auf")
    felder = seite.locator("#parts input.amt")
    for i in range(felder.count()):
        expect(felder.nth(i)).not_to_have_value("")
    assert _dateien() == config


# ------------------------------------------- Speichern ohne Aenderung

#: Seiten mit Formularen, die schreiben. `{objekt}` ist ein Objekt aus dem Hauptbuch.
SEITEN = ["/annahmen", "/einrichtung", "/renten", "/kredite", "/immobilie/{objekt}", "/konten",
          "/ziele", "/planung", "/abos", "/vertraege", "/monatsabschluss", "/energie", "/regeln",
          "/projekte", "/kategorien", "/geteilt/buchungen", "/tx/{buchung}"]
SPEICHERN = r"^(Speichern|Aufteilung speichern|Anlegen)$"


def _adresse(pfad: str) -> str:
    db = sqlite3.connect(DB)
    objekt = db.execute("SELECT id FROM properties ORDER BY id LIMIT 1").fetchone()
    db.close()
    return pfad.format(objekt=objekt[0] if objekt else "x", buchung=_buchung()[0])


def _knoepfe(seite: Page):
    """Alle Speichern-Knoepfe der Seite, sichtbar und bedienbar -- nach dem Aufklappen."""
    seite.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
    knoepfe = seite.get_by_role("button", name=re.compile(SPEICHERN))
    return [k for k in (knoepfe.nth(i) for i in range(knoepfe.count()))
            if k.is_visible() and k.is_enabled()]


#: Woran zwei Knoepfe als dieselbe Art erkannt werden: dieselbe Funktion im
#: `onclick`, sonst dasselbe Formular, sonst dieselbe Aufschrift.
_ART = ("k => (k.getAttribute('onclick') || '').split('(')[0].trim()"
        " || (k.closest('form') || {}).id || k.textContent.trim()")


def _je_art(seite: Page) -> list[tuple[int, str]]:
    """Je Art der erste Knopf, als (Position, Art).

    EIN KNOPF JE ART, NICHT JEDER. Zwanzig Vertraege haben denselben
    Speichern-Weg, und einer prueft ihn; jeder einzelne kostete einen
    Seitenaufruf und machte `/abos` zum laengsten Test der Suite.
    """
    gesehen: set[str] = set()
    out = []
    for i, knopf in enumerate(_knoepfe(seite)):
        art = knopf.evaluate(_ART)
        if art not in gesehen:
            gesehen.add(art)
            out.append((i, art))
    return out


def _neu_laden(seite: Page, adresse: str, ziel: str) -> None:
    """Die Seite frisch, ohne dass ein Neuladen der alten dazwischenfaellt.

    Erst `about:blank`: Das kommt sofort und beendet die Zeitgeber der alten
    Seite, die sonst 700 ms nach dem Speichern selbst neu laedt.
    """
    seite.goto("about:blank")
    seite.goto(adresse + ziel)


@pytest.mark.parametrize("pfad", SEITEN)
def test_speichern_ohne_aenderung_aendert_keine_datei(seite, config, adresse, pfad):
    ziel = _adresse(pfad)
    seite.goto(adresse + ziel)
    arten = _je_art(seite)
    if not arten:
        pytest.skip(f"{ziel}: kein Speichern-Knopf (leer oder ohne Daten)")
    geaendert = []
    for i, art in arten:
        _neu_laden(seite, adresse, ziel)
        knoepfe = _knoepfe(seite)
        if i >= len(knoepfe):
            break
        name = (knoepfe[i].evaluate("k => (k.closest('tr, form, details, .card, p') || k).id")
                or art)
        # Ein Knopf, der ohne Aenderung gar nicht erst sendet, ist richtig.
        _speichern_und_warten(seite, knoepfe[i], muss_senden=False)
        jetzt = _dateien()
        if jetzt != config:
            geaendert.append(f"{name}: " + ", ".join(
                n for n in sorted(jetzt.keys() | config.keys()) if jetzt.get(n) != config.get(n)))
            for n, inhalt in config.items():
                (Path("config") / n).write_bytes(inhalt)
    assert not geaendert, f"{ziel}: Speichern ohne Aenderung schrieb:\n  " + "\n  ".join(geaendert)


def test_einrichtung_speichert_sicherungsziel_und_person_ganz_und_ohne_aenderung_nichts(
        seite, config, adresse, tmp_path):
    """`backup.yaml` und `lebensplan.yaml` sind je eine Datei (N.3e). Die Seite schreibt sie ganz,
    mit den Notizen, und ein Speichern ohne Aenderung aendert kein Byte: auch nicht, wenn die
    Seite das Ziel anders zeigt, als die Datei es traegt, oder das Geburtsdatum als Text schickt.
    """
    from finctl import dateien

    ziel = tmp_path / "ziel"
    ziel.mkdir()
    _datei_aendern("backup.yaml", lambda d: d.update(
        directory=str(ziel), keep=4,
        notizen={"keep": {"notiz": "Vier Staende, weil es reicht."}}))
    _datei_aendern("lebensplan.yaml", lambda d: d.setdefault("person", {}).update(
        birth_date="1980-07-15", krankenversicherung="gesetzlich"))
    vorher = _dateien()
    _neu_laden(seite, adresse, "/einrichtung")
    seite.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")

    seite.get_by_role("button", name="Prüfen und speichern").click()
    _ruhig()
    seite.locator("button[onclick^='personSpeichern']").click()
    _ruhig()
    assert _dateien() == vorher, "Speichern ohne Aenderung hat eine Datei veraendert"

    seite.locator("#ziel-keep").fill("5")
    seite.get_by_role("button", name="Prüfen und speichern").click()
    assert _bis(lambda: _yaml("backup.yaml").get("keep") == 5)
    spec = _yaml("backup.yaml")
    assert (spec["directory"], spec["notizen"]["keep"]["notiz"]) == (
        str(ziel), "Vier Staende, weil es reicht.")
    assert not (Path("config") / "backup_custom.yaml").exists()

    seite.locator("#p-rente").fill("65")
    seite.locator("button[onclick^='personSpeichern']").click()
    assert _bis(lambda: (_yaml("lebensplan.yaml").get("schwellen") or {}).get(
        "grv_ab_alter") == 65)
    leben = _yaml("lebensplan.yaml")
    assert str(leben["person"]["birth_date"]) == "1980-07-15"
    assert dateien.yaml_text(leben)           # und bleibt eine Datei, die sich schreiben laesst
    assert not (Path("config") / "lebensplan_custom.yaml").exists()


def test_monatsabschluss_schreibt_den_verlauf_einmal_und_beim_selben_stand_nicht_neu(
        seite, config, adresse):
    """Auf /monatsabschluss heisst der Knopf erst "Speichern", wenn jemand tippt; der
    allgemeine Test oben sieht ihn deshalb nicht. Ein neuer Stand schreibt den Verlauf,
    derselbe Stand noch einmal schreibt keine Datei."""
    from datetime import date

    from finctl import bestaende as best

    seite.goto_("/monatsabschluss")
    feld = seite.locator("table.staende tr[data-key] input[data-feld='wert']").first
    if feld.count() == 0:
        pytest.skip("/monatsabschluss: keine getippte Position")
    zeile = feld.locator("xpath=ancestor::tr")
    key = zeile.get_attribute("data-key")
    feld.fill("1.234,56")
    _speichern_und_warten(seite, zeile.locator("[data-knopf]"))

    heute = date.today()
    art = next((b.get("kind") for b in _yaml("balances.yaml")["balances"]
                if (b.get("account_id") or b.get("name")) == key), None)
    eintrag = _yaml("balances.yaml")["verlauf"][key][best.periode(art, heute)]
    assert (eintrag["cents"], eintrag["as_of"]) == (123456, heute.isoformat())
    gesehen = (Path("config") / "balances.yaml").read_bytes()

    _neu_laden(seite, adresse, "/monatsabschluss")
    feld = seite.locator(f"table.staende tr[data-key='{key}'] input[data-feld='wert']")
    feld.fill("1.234,56")
    _speichern_und_warten(seite, seite.locator(f"tr[data-key='{key}'] [data-knopf]"))
    assert (Path("config") / "balances.yaml").read_bytes() == gesehen


def test_monatsabschluss_speichert_den_rueckkaufswert_als_text_und_beim_selben_wert_nicht_neu(
        seite, config, adresse):
    """Die Angaben der Mitteilung einer Police stehen in der Unterzeile und gehen als Text an
    den Server. Derselbe Wert noch einmal schreibt keine Datei, und der Verlauf der Position
    bleibt, wie er war: nur ein neuer Policenwert schreibt ihn."""
    seite.goto_("/monatsabschluss")
    unter = seite.locator("tr.unterzeile[data-zu]:has([data-feld='rueckkauf'])").first
    if unter.count() == 0:
        pytest.skip("/monatsabschluss: keine Police")
    key = unter.get_attribute("data-zu")
    verlauf = _yaml("balances.yaml").get("verlauf")
    for feld, text in (("rueckkauf", "1.234,56"), ("eingezahlt", "1.000,00"),
                       ("rpolice", "1.300,00"), ("rstand", "2026-01-01")):
        unter.locator(f"[data-feld='{feld}']").fill(text)
    zeile = seite.locator(f"tr[data-key='{key}']")
    _speichern_und_warten(seite, zeile.locator("[data-knopf]"))

    eintrag = next(b for b in _yaml("balances.yaml")["balances"]
                   if (b.get("account_id") or b.get("name")) == key)
    assert (eintrag["rueckkauf_cents"], eintrag["eingezahlt_cents"],
            eintrag["rueckkauf_policenwert_cents"], eintrag["rueckkauf_as_of"]) == (
        123456, 100000, 130000, "2026-01-01")
    assert _yaml("balances.yaml").get("verlauf") == verlauf
    gesehen = (Path("config") / "balances.yaml").read_bytes()

    _neu_laden(seite, adresse, "/monatsabschluss")
    unter = seite.locator(f"tr.unterzeile[data-zu='{key}']")
    assert unter.locator("[data-feld='rueckkauf']").input_value() == "1.234,56"
    unter.locator("[data-feld='rueckkauf']").fill("1.234,56")
    _speichern_und_warten(seite, seite.locator(f"tr[data-key='{key}'] [data-knopf]"))
    assert (Path("config") / "balances.yaml").read_bytes() == gesehen


def test_wirkung_klappt_je_ziel_auf_und_zu(seite, config, adresse):
    """Die Zeile eines Ziels zeigt seine Ursachen erst nach einem Klick; ein zweiter schliesst
    sie wieder. Der Verlauf kommt von Hand: der heutige Stand jeder getippten Position, als
    haette der Abschluss vom Monat davor ihn abgelegt."""
    import yaml

    from finctl import bestaende as best
    from finctl.forecast import abgleich as ag
    from finctl.web.basis import conn

    c = conn()
    try:
        davor = ag.letzter_vollstaendiger_monat(c).replace(day=1) - timedelta(days=1)
        jetzt = best.zusammenfuehren(c, best.lesen())
    finally:
        c.close()
    eintraege: dict = {}
    for z in jetzt["balances"]:
        if not z.get("aus_auszug") and z.get("cents") is not None:
            eintraege.setdefault(best.schluessel(z), {})[
                best.periode(z.get("kind"), ag.folgetag(davor))] = {
                "cents": int(z["cents"]), "as_of": davor.isoformat()}
    pfad = Path("config") / "balances.yaml"
    spec = yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}
    spec["verlauf"] = eintraege
    pfad.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")

    seite.goto_("/monatsabschluss")
    zeile = seite.locator("table.wirkung tr.klappbar").first
    if zeile.count() == 0:
        pytest.skip("/monatsabschluss: kein Ziel mit Hochrechnung")
    # Eine Zeile mit Panel laesst sich nicht sortieren: das Panel bliebe zurueck.
    expect(seite.locator("table.wirkung th.sortable")).to_have_count(0)
    panel = seite.locator("table.wirkung tr.panel").first
    expect(panel).to_be_hidden()
    zeile.click()
    expect(panel).to_be_visible()
    zeile.click()
    expect(panel).to_be_hidden()


# ------------------------------------------------------ Betragseingabe

def _yaml(name: str) -> dict:
    import yaml

    pfad = Path("config") / name
    return (yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}) if pfad.exists() else {}


def _speichern_und_warten(seite: Page, knopf, *, muss_senden: bool = True) -> None:
    """Klicken und auf die Antwort des Servers warten.

    Ist die Antwort da, steht die Datei schon: Der Server schreibt, bevor er
    antwortet. Danach noch warten, bis er ganz fertig ist -- mancher Knopf
    schickt eine zweite Anfrage hinterher.
    """
    try:
        with seite.expect_response(lambda r: r.request.method == "POST",
                                   timeout=60_000 if muss_senden else 5_000):
            knopf.click()
    except Zeitueberschreitung:
        if muss_senden:
            raise
    _ruhig()


def _bis(bedingung, sekunden: float = 30.0) -> bool:
    """Wartet, bis etwas eintritt -- statt zu raten, wie lange der Server braucht."""
    ende = time.monotonic() + sekunden
    while time.monotonic() < ende:
        if bedingung():
            return True
        time.sleep(0.2)
    return bedingung()


@pytest.mark.parametrize(("getippt", "cents"), [
    ("1.234,56", 123456),       # deutsch mit Tausenderpunkt
    ("1234.56", 123456),        # wie Python es schreibt
    ("1234,5", 123450),
    ("5.000", 500000),          # ein Punkt vor drei Ziffern trennt Tausender
    ("-5,00", -500),            # negativ
])
def test_betrag_vom_feld_bis_in_die_datei(seite, config, adresse, getippt, cents):
    seite.goto(adresse + "/annahmen")
    feld = seite.locator("#a-salary_floor_cents")
    feld.fill(getippt)
    _speichern_und_warten(seite, seite.locator(
        "tr:has(#a-salary_floor_cents) button[onclick^='speichern']"))
    assert _yaml("assumptions.yaml")["erwerbseinkommen"]["netto_floor_monatlich_cents"] == cents


def test_leeres_feld_nimmt_eine_optionale_angabe_aus_der_datei(seite, config, adresse):
    seite.goto(adresse + "/annahmen")
    seite.locator("#a-teilzeit_ab").fill("2046-01")
    knopf = seite.locator("tr:has(#a-teilzeit_ab) button[onclick^='speichern']")
    _speichern_und_warten(seite, knopf)
    assert str(_yaml("assumptions.yaml")["erwerbseinkommen"]["teilzeit_ab"]) == "2046-01"
    seite.locator("#a-teilzeit_ab").fill("")
    _speichern_und_warten(seite, seite.locator(
        "tr:has(#a-teilzeit_ab) button[onclick^='speichern']"))
    assert "teilzeit_ab" not in _yaml("assumptions.yaml")["erwerbseinkommen"]


def test_leeres_feld_einer_noetigen_angabe_wird_gemeldet_und_aendert_nichts(
        seite, config, adresse):
    seite.goto(adresse + "/annahmen")
    seite.locator("#a-salary_floor_cents").fill("")
    seite.locator("tr:has(#a-salary_floor_cents) button[onclick^='speichern']").click()
    expect(seite.locator("#m-salary_floor_cents")).to_contain_text("Fehler")
    assert _dateien() == config


@pytest.mark.parametrize("getippt", ["1,234.56", "1,234", "abc"])
def test_mehrdeutiger_betrag_wird_gemeldet_und_nicht_gespeichert(seite, config, adresse, getippt):
    seite.goto(adresse + "/annahmen")
    seite.locator("#a-salary_floor_cents").fill(getippt)
    knopf = seite.locator("tr:has(#a-salary_floor_cents) button[onclick^='speichern']")
    knopf.click()
    expect(seite.locator("#m-salary_floor_cents")).to_contain_text("Fehler")
    assert _dateien() == config


def test_prozent_und_anteil_gehen_als_text_an_den_server(seite, config, adresse):
    seite.goto(adresse + "/annahmen")
    seite.locator("#a-inflation_pa").fill("2,35")
    _speichern_und_warten(seite, seite.locator(
        "tr:has(#a-inflation_pa) button[onclick^='speichern']"))
    assert _yaml("assumptions.yaml")["inflation_pa"] == 0.0235


def test_sparerpauschbetrag_vom_feld_bis_in_die_datei(seite, config, adresse):
    seite.goto(adresse + "/annahmen")
    seite.locator("#a-sparerpauschbetrag_cents").fill("2.000,00")
    _speichern_und_warten(seite, seite.locator(
        "tr:has(#a-sparerpauschbetrag_cents) button[onclick^='speichern']"))
    assert _yaml("assumptions.yaml")["kapital"]["sparerpauschbetrag_cents"] == 200000


def test_zinssatz_anlegen_und_loeschen_liest_prozent_als_text(seite, config, adresse):
    seite.goto(adresse + "/annahmen")
    konto = seite.locator("#z-konto option").first.get_attribute("value")
    seite.locator("#z-ab").fill("2031-01")
    seite.locator("#z-bis").fill("2031-06")
    seite.locator("#z-satz").fill("3,25")
    _speichern_und_warten(seite, seite.get_by_role("button", name="Anlegen"))
    eintrag = _yaml("zinssaetze_custom.yaml")["zinssaetze"][konto]
    assert eintrag == [{"ab": "2031-01", "bis": "2031-06", "satz": 0.0325}]
    _neu_laden(seite, adresse, "/annahmen")
    seite.once("dialog", lambda dialog: dialog.accept())
    _speichern_und_warten(seite, seite.get_by_role("button", name="Löschen").first)
    assert not (_yaml("zinssaetze_custom.yaml").get("zinssaetze") or {}).get(konto)


def test_ein_zinssatz_mit_falschem_zeitraum_wird_gemeldet_und_nicht_gespeichert(
        seite, config, adresse):
    seite.goto(adresse + "/annahmen")
    seite.locator("#z-ab").fill("2031-06")
    seite.locator("#z-bis").fill("2031-01")
    seite.locator("#z-satz").fill("3")
    seite.get_by_role("button", name="Anlegen").click()
    expect(seite.locator("tr:has(#z-satz) .meldung")).to_contain_text("bis liegt vor ab")
    assert _dateien() == config


def test_objekt_betraege_und_prozent_vom_feld_bis_in_die_datei(seite, config, adresse):
    seite.goto(adresse + _adresse("/immobilie/{objekt}"))
    seite.locator("#price").fill("250.000,00")
    seite.locator("#equity").fill("50000.5")
    seite.locator("#incidental").fill("")
    seite.locator("#land").fill("22,5")
    _speichern_und_warten(seite, seite.locator("button[onclick='savep()']"))
    kennung = _adresse("{objekt}")
    objekt = next(p for p in _yaml("properties.yaml")["properties"] if str(p["id"]) == kennung)
    assert objekt["purchase_price_cents"] == 25000000
    assert objekt["equity_cents"] == 5000050
    assert objekt["land_share_pct"] == 22.5
    assert "incidental_costs_cents" not in objekt


def test_split_speichern_liest_den_betrag_als_text(seite, config, adresse):
    tid, gesamt = _buchung()
    seite.goto(adresse + f"/tx/{tid}")
    text = f"{gesamt / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    _betraege(seite, text)
    expect(seite.locator("#balance")).to_contain_text("geht genau auf")
    seite.get_by_role("button", name="Aufteilung speichern").click()
    expect(seite.locator("#status")).to_contain_text("Teile gespeichert")
    db = sqlite3.connect(DB)
    assert db.execute("SELECT SUM(amount_cents) FROM splits WHERE transaction_id=?",
                      (tid,)).fetchone()[0] == gesamt
    db.close()


def test_kredit_anschluss_liest_prozent_als_text(seite, config, adresse):
    seite.goto(adresse + "/kredite")
    seite.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
    zins = seite.locator("[id^='a-zins-']").first
    if not zins.count():
        pytest.skip("kein Kredit mit Anschlussangebot")
    kennung = zins.get_attribute("id").removeprefix("a-zins-")
    zins.fill("3,8")
    seite.locator(f"#a-tilg-{kennung}").fill("2")
    _speichern_und_warten(
        seite, seite.locator(f"button[onclick^=\"anschluss(this, '{kennung}'\"]"))
    kredit = next(k for k in _yaml("loans.yaml")["loans"] if str(k["id"]) == kennung)
    eintrag = kredit["anschluss_eingegeben"]
    assert eintrag["zins_pct"] == 3.8 and eintrag["tilgung_pct"] == 2.0


# ------------------------------------------------ Ablaeufe mit Zustand

def test_klammer_an_und_aus(seite, config, adresse):
    seite.goto(adresse + "/planung")
    seite.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
    schalter = seite.locator("button[onclick^='toggle(']")
    if not schalter.count():
        pytest.skip("keine Klammer")
    knopf = schalter.first
    kennung = knopf.get_attribute("onclick").split("'")[1]

    def aktiv() -> bool:
        spec = _yaml("szenarien.yaml")
        return next(k for k in spec["szenarien"] if k["id"] == kennung).get("aktiv", True)

    vorher = aktiv()
    _speichern_und_warten(seite, knopf)
    assert aktiv() is not vorher
    _neu_laden(seite, adresse, "/planung")
    seite.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
    seite.locator(f"button[onclick^=\"toggle('{kennung}'\"]").click()
    assert _bis(lambda: aktiv() is vorher)


def test_erwartete_einnahme_wird_ueber_die_seite_angelegt(seite, config, adresse):
    """Die Art „Erwartete Einnahme“ stellt die Richtung fest auf Einnahme und speichert den
    Betrag ohne Vorzeichen als positive Zahl."""
    seite.goto(adresse + "/planung")
    seite.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
    knoepfe = seite.locator("button[onclick^='neueZeile(']")
    kennungen = [k.get_attribute("onclick").split("'")[1] for k in knoepfe.all()]
    kennung = next((k for k in kennungen if k != "teilzeit"), None)
    if kennung is None:
        pytest.skip("keine Klammer, in die eine Position kommt")
    zid = f"{kennung}-neu"
    seite.locator(f"tr.klappbar[onclick=\"oeffneZeile('{zid}')\"]").click()
    seite.locator(f"#e-art-{zid}").select_option("erwartet")
    richtung = seite.locator(f"#e-richtung-{zid}")
    expect(richtung).to_have_value("+")
    expect(richtung).to_be_disabled()
    seite.locator(f"#e-label-{zid}").fill("Zuschuss Pytest")
    seite.evaluate(f"document.getElementById('e-kat-{zid}').value = 'einkommen/schenkung'")
    seite.locator(f"#e-von-{zid}").fill("2031-06")
    seite.locator(f"#e-amt-{zid}").fill("1.200,00")
    _speichern_und_warten(seite, seite.locator(f"button[onclick=\"neueZeile('{kennung}')\"]"))
    zeilen = next(k for k in _yaml("szenarien.yaml")["szenarien"] if k["id"] == kennung)["zeilen"]
    neu = next(z for z in zeilen if z["label"] == "Zuschuss Pytest")
    assert (neu["art"], neu["amount_cents"], neu["kategorie"]) == (
        "erwartet", 120000, "einkommen/schenkung")


def test_eine_ausgabe_vor_dem_stichtag_verschiebt_die_karte_eines_kurzfristigen_ziels(
        seite, config, adresse):
    """Schritt 5b, E.7: Ein Ziel mit Stichtag im Horizont von `/konten` misst das Monatsmodell,
    und eine Klammer mit einer Ausgabe vor dem Stichtag bewegt seine Karte um diese Ausgabe."""
    import re
    from datetime import date

    def karte() -> tuple[str, int, date] | None:
        """Kennung, Stand zum Stichtag und Monat des Stichtags der ersten Monatsmodell-Karte."""
        seite.goto(adresse + "/ziele")
        for block in seite.content().split('<div class="card ziel-karte"')[1:]:
            treffer = re.search(r"vorausgerechnet zum <a[^>]*>(\d{4})-(\d\d)-\d\d</a>:"
                                r"\s*<strong>([^<]+)</strong>", block)
            if treffer is None:
                continue
            kennung = re.search(r'data-ziel="([^"]+)"', block).group(1)
            euro = re.sub(r"[^\d,-]", "", treffer.group(3)).replace(",", ".")
            return kennung, round(float(euro) * 100), date(int(treffer[1]), int(treffer[2]), 1)
        return None

    vorher = karte()
    if vorher is None:
        pytest.skip("kein Ziel mit Stichtag im Horizont von /konten")
    kennung, cents_vorher, monat = vorher
    vorher_monat = date(monat.year - (monat.month == 1), (monat.month - 2) % 12 + 1, 1)
    _datei_aendern("szenarien.yaml", lambda d: d.setdefault("szenarien", []).append(
        {"id": "pytest-ausgabe", "name": "Pytest Ausgabe", "aktiv": True, "zeilen": [
            {"label": "Ausgabe Pytest", "art": "betrag", "amount_cents": -100000,
             "frequenz": "einmalig", "start": vorher_monat.isoformat(),
             "kategorie": "immobilie/kaufnebenkosten"}]}))
    nachher = karte()
    assert nachher is not None and nachher[0] == kennung
    # Die Ausgabe von 1.000 mindert den Stand; die Zinsen darauf kommen als Rest dazu.
    assert -105_000 <= nachher[1] - cents_vorher <= -95_000, (cents_vorher, nachher[1])


def test_kombifeld_uebernimmt_die_kennung_der_auswahl(seite, config, adresse):
    tid, _ = _buchung()
    seite.goto(adresse + f"/tx/{tid}")
    feld = seite.locator("#parts input.mgmt").first
    feld.click()
    feld.fill("a")
    seite.keyboard.press("ArrowDown")
    seite.keyboard.press("Enter")
    kennung = feld.evaluate("el => el.dataset.id")
    assert kennung and feld.input_value()
    feld.fill("zzzz-gibt-es-nicht")
    assert feld.evaluate("el => el.dataset.id") == ""    # getippt ist noch nichts gewaehlt


def test_klappzustand_ueberlebt_das_neuladen(seite, config, adresse):
    seite.goto(adresse + "/annahmen")
    kasten = seite.locator("details#prognosebasis")
    if not kasten.count():
        pytest.skip("keine Prognosebasis")
    assert kasten.evaluate("d => d.open") is False
    kasten.locator("> summary").click()
    assert kasten.evaluate("d => d.open") is True
    seite.reload()
    assert seite.locator("details#prognosebasis").evaluate("d => d.open") is True
    seite.locator("details#prognosebasis > summary").click()
    seite.reload()
    assert seite.locator("details#prognosebasis").evaluate("d => d.open") is False


# ------------------------------------------------------------- /reihen

def _reihen_eintraege() -> list:
    return _yaml("reihen_custom.yaml").get("reihen", [])


def test_reihen_oeffnen_festlegen_und_speichern_ohne_aenderung(seite, config, adresse):
    """Die Zeile zeigt, ein Klick oeffnet den Bereich darunter (immer nur einer). Speichern
    ohne Aenderung schreibt keine Datei; ein Takt wird geschrieben, ein zweites Speichern
    desselben Takts aendert nichts mehr, und Zuruecknehmen leert den Eintrag."""
    seite.goto_("/reihen")
    zeilen = seite.locator("table.reihen tr.klappbar")
    if zeilen.count() < 2:
        pytest.skip("/reihen: weniger als zwei Reihen mit festem Takt")
    vorher = _reihen_eintraege()
    # Eine Zeile mit Bereich laesst sich nicht sortieren: der Bereich bliebe zurueck.
    expect(seite.locator("table.reihen th.sortable")).to_have_count(0)
    kennung = zeilen.first.get_attribute("id")
    panel = seite.locator(f"#p-{kennung}")
    expect(panel).to_be_hidden()
    zeilen.first.click()
    expect(panel).to_be_visible()
    zeilen.nth(1).click()
    expect(panel).to_be_hidden()                  # offen ist immer nur einer
    zeilen.first.click()
    expect(panel).to_be_visible()

    # Ohne etwas zu aendern: der Server nimmt die Anfrage und schreibt nichts.
    _speichern_und_warten(seite, panel.get_by_role("button", name="Speichern"))
    assert _dateien() == config

    # Festgelegt wird eine Reihe ohne Takt: auf eine festgelegte schriebe der Test ueber,
    # und dann kaeme kein Eintrag dazu. Ein Klick auf die offene Zeile schlösse sie.
    frei = zeilen.filter(has_not=seite.locator(".pill", has_text="festgelegt"))
    if frei.count() == 0:
        pytest.skip("/reihen: jede Reihe hat schon einen festgelegten Takt")
    kennung = frei.first.get_attribute("id")
    panel = seite.locator(f"#p-{kennung}")
    if panel.is_hidden():
        frei.first.click()
    expect(panel).to_be_visible()

    seite.locator(f"#t-{kennung}").select_option("12")
    seite.locator(f"#n-{kennung}").fill("von Hand")
    _speichern_und_warten(seite, panel.get_by_role("button", name="Speichern"))
    [eintrag] = [e for e in _reihen_eintraege() if e not in vorher]
    assert (eintrag["takt"], eintrag["notiz"]) == (12, "von Hand")

    # Die Seite laedt neu und oeffnet dieselbe Reihe, nun als festgelegt.
    expect(seite.locator(f"#{kennung} .pill.eigen")).to_have_text("festgelegt")
    expect(seite.locator(f"#p-{kennung}")).to_be_visible()
    gesehen = (Path("config") / "reihen_custom.yaml").read_bytes()
    _speichern_und_warten(seite, seite.locator(f"#p-{kennung}").get_by_role(
        "button", name="Speichern"))
    assert (Path("config") / "reihen_custom.yaml").read_bytes() == gesehen

    _speichern_und_warten(seite, seite.locator(f"#p-{kennung}").get_by_role(
        "button", name="Festlegung zurücknehmen"))
    assert _reihen_eintraege() == vorher


def test_reihen_einmalig_setzen_und_zuruecknehmen(seite, config, adresse):
    seite.goto_("/reihen")
    zeilen = seite.locator("table.reihen tr.klappbar")
    if zeilen.count() == 0:
        pytest.skip("/reihen: keine Reihe mit festem Takt")
    vorher = _reihen_eintraege()
    # Eine Buchung, die schon einmalig ist, bleibt wie sie ist: der Knopf bliebe wirkungslos.
    schon = {b for e in vorher if e.get("takt") == "einmalig" for b in e.get("buchungen") or []}
    kennung = zeilen.first.get_attribute("id")
    zeilen.first.click()
    knoepfe = seite.locator(f"#p-{kennung}").get_by_role("button", name="einmalig", exact=True)
    frei = [k for k in knoepfe.all() if k.get_attribute("data-buchung") not in schon]
    if not frei:
        pytest.skip("/reihen: jede Buchung der ersten Reihe ist schon einmalig")
    buchung = frei[0].get_attribute("data-buchung")
    _speichern_und_warten(seite, frei[0])
    [eintrag] = [e for e in _reihen_eintraege() if e not in vorher]
    assert eintrag["takt"] == "einmalig" and eintrag["buchungen"] == [buchung]

    knopf = seite.locator(f"#einmalig ~ .wrap button[data-buchung='{buchung}']")
    expect(knopf).to_have_count(1)
    _speichern_und_warten(seite, knopf)
    assert _reihen_eintraege() == vorher


def _zusammen() -> dict:
    return _yaml("reihen_custom.yaml").get("zusammen", {})


def test_reihen_schreibweisen_zusammenfuehren_und_trennen(seite, config, adresse):
    """Eine Reihe waehlt eine andere ihrer Kategorie als Ziel: Die Seite schreibt die
    Zuordnung, laedt neu und zeigt die Reihe als zusammengefuehrt. Trennen nimmt sie
    zurueck; die Datei bleibt ohne Zuordnung."""
    seite.goto_("/reihen?zeige=alle")
    wahl = seite.locator('select[id^="z-"]')
    if wahl.count() == 0:
        pytest.skip("/reihen: keine Reihe, zu der eine andere derselben Kategorie gehoeren koennte")
    kennung = wahl.first.get_attribute("id")[2:]
    seite.locator(f"#{kennung}").click()
    panel = seite.locator(f"#p-{kennung}")
    expect(panel).to_be_visible()

    # Ohne Auswahl sendet der Knopf nichts, und die Seite sagt es.
    panel.get_by_role("button", name="Zusammenführen").click()
    knopf = seite.locator("button", has_text="Zusammenführen")
    zeile = panel.locator("p.zeilen-knoepfe", has=knopf)
    expect(zeile.locator(".meldung")).to_contain_text("wählen")
    assert _zusammen() == {}

    ziel = wahl.first.locator("option").nth(1).get_attribute("value")
    wahl.first.select_option(ziel)
    schreibweise = panel.get_by_role("button", name="Zusammenführen").get_attribute(
        "data-schreibweise")
    _speichern_und_warten(seite, panel.get_by_role("button", name="Zusammenführen"))
    assert _zusammen() == {schreibweise: ziel}

    # Dieselbe Reihe heisst nun nach dem Ziel und traegt die alte Schreibweise.
    zusammengefuehrt = seite.locator("table.reihen tr.klappbar", has=seite.locator(
        ".pill.eigen", has_text="zusammengeführt"))
    expect(zusammengefuehrt.first).to_be_visible()
    zusammengefuehrt.first.click()
    trennen = seite.locator(f'button[data-schreibweise="{schreibweise}"]', has_text="Trennen")
    expect(trennen).to_be_visible()
    gesehen = (Path("config") / "reihen_custom.yaml").read_bytes()
    _speichern_und_warten(seite, trennen)
    assert _zusammen() == {}
    assert (Path("config") / "reihen_custom.yaml").read_bytes() != gesehen


def test_reihen_vorschlag_fuehrt_erst_auf_den_klick_zusammen(seite, config, adresse):
    seite.goto_("/reihen")
    knoepfe = seite.locator("table.vorschlaege").get_by_role("button", name="Zusammenführen")
    if knoepfe.count() == 0:
        pytest.skip("/reihen: kein Vorschlag auf diesen Daten")
    assert _zusammen() == {}
    alt, neu = (knoepfe.first.get_attribute("data-schreibweise"),
                knoepfe.first.get_attribute("data-ziel"))
    _speichern_und_warten(seite, knoepfe.first)
    assert _zusammen() == {alt: neu}



# ------------------------------------------------------- Notizfelder (N.3b)
#
# Die Notiz eines Eintrags ist mehrzeilig, seit sie aus Kommentaren entsteht. Ein `<input>`
# nahm beim Setzen seines Werts jeden Zeilenumbruch: Der Text, den die Seite beim Speichern
# schickte, war ein anderer als der in der Datei, und die Notiz trug danach das heutige
# Datum, obwohl niemand sie geaendert hatte. Der Server-Test "Speichern ohne Aenderung" sieht
# das nicht, denn er schickt den Text unveraendert. Hier laeuft derselbe Weg im Browser.

#: Mit Leerzeile, einer eingerueckten Zeile, Umlauten und Anfuehrungszeichen.
NOTIZ = ('Erste Zeile.\n\nNach einer Leerzeile: ein Satz mit ä, ö und "Anführungszeichen".\n'
         '  Eine eingerückte Zeile.\nLetzte Zeile.')
NOTIZ_GEAENDERT = NOTIZ.replace("Erste Zeile.", "Geänderte erste Zeile.")
ALTES_DATUM = "2020-01-01"


def _mit_notiz(text: str) -> list[tuple[str, dict]]:
    """Alle Eintraege in `config/`, deren Notiz genau dieser Text ist: (Datei, Eintrag)."""
    import yaml

    funde: list[tuple[str, dict]] = []

    def gehe(wert, datei: str) -> None:
        if isinstance(wert, dict):
            if wert.get("notiz") == text:
                funde.append((datei, wert))
            for v in wert.values():
                gehe(v, datei)
        elif isinstance(wert, list):
            for v in wert:
                gehe(v, datei)

    for pfad in sorted(Path("config").glob("*.yaml")):
        if pfad.name != "overrides.yaml":
            gehe(yaml.safe_load(pfad.read_text(encoding="utf-8")), pfad.name)
    return funde


def _datei_aendern(name: str, aendern) -> None:
    """Eine Datei in `config/` lesen, mit `aendern(daten)` aendern und ganz schreiben."""
    import yaml

    from finctl import dateien

    pfad = Path("config") / name
    daten = (yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}) if pfad.exists() else {}
    aendern(daten)
    dateien.yaml_schreiben(pfad, daten)


def _notiz_legen(eintrag: dict) -> dict:
    """Die Notiz in den Eintrag, wie `finctl umstellen` sie aus Kommentaren macht: ohne Datum."""
    for name in ("notiz", "notiz_vom", "note", "warum", "herleitung"):
        eintrag.pop(name, None)
    eintrag["notiz"] = NOTIZ
    return eintrag


def _eine_notiz(text: str) -> dict:
    gefunden = _mit_notiz(text)
    assert len(gefunden) == 1, f"{len(gefunden)} Eintraege mit dieser Notiz: {gefunden}"
    return gefunden[0][1]


def _tippen_und_zuruecknehmen(feld) -> None:
    """Ein Zeichen tippen und wieder loeschen: Das Feld gilt als bearbeitet, der Text bleibt."""
    feld.focus()
    feld.press_sequentially("x")
    feld.press("Backspace")


def _notiz_ablauf(seite, adresse, ziel, *, vorgeben, oeffnen, feld, speichern, unveraendert=None):
    """Der Weg, den jede Seite mit einer mehrzeiligen Notiz gehen muss.

    `vorgeben` legt die Notiz in die Datei, wie sie aus Kommentaren entstanden ist: mehrere
    Absaetze, ohne Datum.

    1. Die Seite oeffnen und ohne Aenderung speichern: die Dateien bleiben Byte fuer Byte,
       und die Notiz bekommt kein Datum. Das ist der Fehler, den ein `<input>` verursachte:
       Es entfernt beim Setzen des Werts jeden Zeilenumbruch, die Seite schickte einen anderen
       Text, und die Notiz stand danach in einer Zeile mit dem Datum von heute.
    2. Das Feld zeigt die Notiz mit allen Umbruechen. Eine Zeile aendern und speichern: Die
       anderen Umbrueche bleiben, das Datum ist heute.
    3. Wieder ohne Aenderung speichern: nichts aendert sich, auch das Datum nicht.
    """
    from datetime import date

    vorgeben()
    start = _dateien()
    _neu_laden(seite, adresse, ziel)
    oeffnen(seite)
    if unveraendert is not None:
        unveraendert(feld(seite))
    speichern(seite)
    assert _dateien() == start, "Speichern ohne Aenderung hat eine Datei veraendert"
    assert "notiz_vom" not in _eine_notiz(NOTIZ)

    _neu_laden(seite, adresse, ziel)
    oeffnen(seite)
    assert feld(seite).input_value() == NOTIZ
    feld(seite).fill(NOTIZ_GEAENDERT)
    speichern(seite)
    assert _mit_notiz(NOTIZ) == []
    assert str(_eine_notiz(NOTIZ_GEAENDERT)["notiz_vom"]) == date.today().isoformat()

    gesehen = _dateien()
    _neu_laden(seite, adresse, ziel)
    oeffnen(seite)
    if unveraendert is not None:
        unveraendert(feld(seite))
    speichern(seite)
    assert _dateien() == gesehen, "Speichern ohne Aenderung hat eine Datei veraendert"


def test_notiz_einer_kontenregel_ist_mehrzeilig(seite, config, adresse):
    seite.goto_("/konten")
    zeile = seite.locator("tr.hauptzeile").first
    if zeile.count() == 0:
        pytest.skip("/konten: kein Konto")
    kennung = zeile.get_attribute("id").removeprefix("r-")
    _notiz_ablauf(
        seite, adresse, "/konten",
        vorgeben=lambda: _datei_aendern("forecast.yaml", lambda d: _notiz_legen(
            d.setdefault("account_roles", {}).setdefault(kennung, {}))),
        # Nach dem Neuladen oeffnet die Seite die gemerkte Zeile selbst; ein Klick schlosse sie.
        oeffnen=lambda s: None if s.locator("#f-note").is_visible()
        else s.locator(f"#r-{kennung}").click(),
        feld=lambda s: s.locator("#f-note"),
        speichern=lambda s: _speichern_und_warten(
            s, s.locator("button[onclick='regelSpeichern()']")))


def test_speichern_ohne_aenderung_auf_der_karte_jeder_art_von_konto(seite, config, adresse):
    """Die Karte schickt die Untergrenze, die sie zeigt -- auch wenn die Datei keine nennt.

    Seit N.3f steht sie in `forecast.yaml`; ein Konto ohne Regel, eines ohne Untergrenze in
    seiner Regel, eines mit Untergrenze und eines mit einer Rate als Untergrenze speichern,
    ohne dass sich ein Byte aendert.
    """
    rollen = _yaml("forecast.yaml").get("account_roles") or {}
    seite.goto(adresse + "/konten")
    ids = [z.get_attribute("id").removeprefix("r-") for z in seite.locator("tr.hauptzeile").all()]
    if not ids:
        pytest.skip("/konten: kein Konto")

    def regel(k):
        return rollen.get(k) or {}

    wahl = [next((k for k in ids if bedingung(k)), None) for bedingung in (
        lambda k: regel(k).get("floor_cents") is not None and not regel(k).get("floor_from_loan"),
        lambda k: bool(regel(k).get("floor_from_loan")),
        lambda k: k not in rollen,
        lambda k: k in rollen and "floor_cents" not in regel(k))]
    wahl = [k for k in dict.fromkeys(wahl) if k]
    assert wahl, "kein Konto, an dem sich das pruefen laesst"
    for kennung in wahl:
        _neu_laden(seite, adresse, "/konten")
        seite.evaluate(f"oeffne('{kennung}')")
        _speichern_und_warten(seite, seite.locator("button[onclick='regelSpeichern()']"))
        assert _dateien() == config, f"Speichern ohne Aenderung auf {kennung} schrieb"


def test_notiz_einer_rente_ist_mehrzeilig(seite, config, adresse):
    seite.goto_("/renten")
    zeile = seite.locator("table.renten tr[data-key]").first
    if zeile.count() == 0:
        pytest.skip("/renten: keine Rente")
    kennung = zeile.get_attribute("data-key")
    _notiz_ablauf(
        seite, adresse, "/renten",
        vorgeben=lambda: _datei_aendern("renten.yaml", lambda d: _notiz_legen(
            next(e for e in d["renten"] if e["id"] == kennung))),
        oeffnen=lambda s: None,
        feld=lambda s: s.locator(f"tr.unterzeile[data-zu='{kennung}'] [data-feld='notiz']"),
        speichern=lambda s: _speichern_und_warten(
            s, s.locator(f"#rente-{kennung} [data-knopf]")),
        # Der Knopf "unveraendert" legt den Stand mit dem Datum von heute ab; hier geht
        # es um die Notiz, die nur mitgeschickt wird, wenn ihr Feld bearbeitet wurde.
        unveraendert=_tippen_und_zuruecknehmen)


def test_notiz_eines_ziels_ist_mehrzeilig(seite, config, adresse):
    seite.goto_("/ziele")
    karte = seite.locator(".ziel-karte:has(.ziel-zeile)").first
    if karte.count() == 0:
        pytest.skip("/ziele: kein Ziel, das sich bearbeiten laesst")
    kennung = karte.get_attribute("data-ziel")
    name = seite.locator(f"#z-name-{kennung}").input_value()

    def vorgeben():
        def legen(d):
            ziel = next(g for g in d["ziele"] if g["id"] == kennung)
            _notiz_legen(ziel)
            # Ein Ziel ohne Namen zeigt seine Kennung; Speichern schreibt den Namen nicht.
            if name != kennung:
                ziel.setdefault("name", name)

        _datei_aendern("goals.yaml", legen)

    _notiz_ablauf(
        seite, adresse, "/ziele",
        vorgeben=vorgeben,
        oeffnen=lambda s: s.locator(f"button[onclick=\"zielOeffnen('{kennung}')\"]").click(),
        feld=lambda s: s.locator(f"#z-notiz-{kennung}"),
        speichern=lambda s: _speichern_und_warten(
            s, s.locator(f"#z-form-{kennung} button[onclick=\"speichern('{kennung}')\"]")))


def test_notiz_eines_neuen_ziels_behaelt_ihre_umbrueche(seite, config, adresse):
    from datetime import date

    seite.goto_("/ziele")
    seite.locator("#neues-ziel summary").click()
    seite.locator("#n-name").fill("Probeziel")
    seite.locator("#n-cents").fill("1.000,00")
    seite.locator("#n-datum").fill("2040-12-31")
    seite.locator("#n-notiz").fill(NOTIZ)
    _speichern_und_warten(seite, seite.locator("#neues-ziel button[onclick='anlegen()']"))
    assert str(_eine_notiz(NOTIZ)["notiz_vom"]) == date.today().isoformat()


def test_notiz_einer_reihe_ist_mehrzeilig(seite, config, adresse):
    seite.goto_("/reihen")
    zeile = seite.locator("table.reihen tr.klappbar").first
    if zeile.count() == 0:
        pytest.skip("/reihen: keine Reihe mit festem Takt")
    kennung = zeile.get_attribute("id")
    buchung = seite.locator(f"#p-{kennung} button[data-buchung]").first.get_attribute(
        "data-buchung")
    panel = f"#p-{kennung}"

    def vorgeben():
        from finctl import reihen
        from finctl.ledger import db

        c = db.connect(DB)
        try:
            # Eine Notiz steht nur an einer festgelegten Reihe.
            reihen.festlegen(c, buchung, 12, NOTIZ)
        finally:
            c.close()
        _datei_aendern("reihen_custom.yaml", lambda d: [
            e.pop("notiz_vom", None) for e in d.get("reihen") or []])

    _notiz_ablauf(
        seite, adresse, "/reihen",
        vorgeben=vorgeben,
        oeffnen=lambda s: s.locator(f"#{kennung}").click(),
        feld=lambda s: s.locator(f"#n-{kennung}"),
        speichern=lambda s: _speichern_und_warten(
            s, s.locator(panel).get_by_role("button", name="Speichern", exact=True)))


@pytest.mark.parametrize("ansicht", ["abos", "versicherungen"])
def test_notiz_eines_vertrags_ist_mehrzeilig(seite, config, adresse, ansicht):
    ziel = f"/vertraege?ansicht={ansicht}"
    seite.goto(adresse + ziel)
    zeile = seite.locator("table tr.klappbar").first
    if zeile.count() == 0:
        pytest.skip(f"{ziel}: kein Vertrag")
    kennung = zeile.get_attribute("onclick").split("oeffne('")[1].split("'")[0]
    box = f"#editor-{kennung}"
    datei = "abos.yaml" if ansicht == "abos" else "versicherungen.yaml"
    _notiz_ablauf(
        seite, adresse, ziel,
        vorgeben=lambda: _datei_aendern(datei, lambda d: _notiz_legen(
            next(e for e in d[ansicht] if e["id"] == kennung))),
        # Die Seite merkt, welcher Vertrag offen war; ein Klick auf den offenen schlosse ihn.
        oeffnen=lambda s: None if s.locator(f"{box} [data-f='warum']").is_visible()
        else s.locator(f"#abo-{kennung} summary").click(),
        feld=lambda s: s.locator(f"{box} [data-f='warum']"),
        speichern=lambda s: _speichern_und_warten(s, s.locator(f"{box} [data-a='speichern']")))


def test_notiz_eines_bestands_ist_mehrzeilig(seite, config, adresse):
    """Eine Verpflichtung hat auf keiner Seite ein Notizfeld (nur "streichen"); ihren Weg
    ueber die Schnittstelle prueft `tests/test_notizen_seiten.py`."""
    seite.goto_("/monatsabschluss")
    treffer = seite.locator(
        "table.staende tr[data-key]:not([data-api]):has(textarea[data-feld='notiz'])").first
    if treffer.count() == 0:
        pytest.skip("/monatsabschluss: keine Position mit Notiz")
    kennung = treffer.get_attribute("data-key")
    zeile_ = f"table.staende tr[data-key='{kennung}']"
    _notiz_ablauf(
        seite, adresse, "/monatsabschluss",
        vorgeben=lambda: _datei_aendern("balances.yaml", lambda d: _notiz_legen(
            next(b for b in d["balances"] if (b.get("account_id") or b.get("name")) == kennung))),
        oeffnen=lambda s: None,
        feld=lambda s: s.locator(f"{zeile_} textarea[data-feld='notiz']"),
        speichern=lambda s: _speichern_und_warten(s, s.locator(f"{zeile_} [data-knopf]")),
        unveraendert=_tippen_und_zuruecknehmen)
