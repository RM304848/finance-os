"""Die Notiz eines Eintrags steht auf der Seite, die den Eintrag zeigt, mit ihrem Datum.

Begriff und Form: `CONTEXT.md`, `finctl/notizen.py`. Ein Eintrag mit `notiz` zeigt sie
aufklappbar (`_notiz.html`) und sagt, vom wann sie ist -- oder „ohne Datum“, wo sie aus
der Zeit vor den Notizen stammt. Welche Eintraege es gibt, liest der Test zur Laufzeit aus
`config/`; wo keiner eine Notiz hat (Musterhaushalt), gibt es nichts zu zeigen.
"""

from __future__ import annotations

import pytest
import yaml
from fastapi.testclient import TestClient
from markupsafe import escape

from finctl import notizen
from finctl.pfade import CONFIG_DIR
from finctl.web.basis import TEMPLATES
from finctl.web.routen import annahmen as annahmen_seite
from finctl.web.server import app

client = TestClient(app)


def _makro(name: str):
    return getattr(TEMPLATES.env.get_template("_notiz.html").module, name)


def test_a_dated_note_says_when_it_was_changed():
    html = str(_makro("zeile")("Warum es so ist.", "2026-10-05"))
    assert '<details class="notiz">' in html
    assert "vom 2026-10-05" in html and "Warum es so ist." in html


def test_a_note_from_before_the_notes_says_it_has_no_date():
    html = str(_makro("zeile")("Alt.", ""))
    assert "ohne Datum" in html and "Alt." in html


def test_no_note_shows_nothing():
    assert str(_makro("zeile")("", "")).strip() == ""


def _eintraege(datei: str, schluessel: str) -> list[dict]:
    pfad = CONFIG_DIR / datei
    spec = (yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}) if pfad.exists() else {}
    liste = spec.get(schluessel) or []
    return [e for e in liste if isinstance(e, dict) and notizen.lesen(e)]


def _anfang(text: str) -> str:
    """Der Beginn der Notiz, wie die Seite ihn setzt: maskiert, ohne Zeilenumbruch."""
    return str(escape(notizen.lesen({"notiz": text}).text.splitlines()[0][:40]))


SEITEN = [
    ("/kredite", "loans.yaml", "loans"),
    ("/ziele", "goals.yaml", "ziele"),
]


@pytest.mark.parametrize(("seite", "datei", "schluessel"), SEITEN, ids=[s[0] for s in SEITEN])
def test_a_page_shows_the_note_of_each_entry_with_its_date(seite, datei, schluessel):
    eintraege = [e for e in _eintraege(datei, schluessel) if not e.get("fest")]
    if not eintraege:
        pytest.skip(f"kein Eintrag in {datei} mit Notiz")
    html = client.get(seite).text
    for e in eintraege:
        assert _anfang(e["notiz"]) in html, f"{seite}: Notiz von {e.get('id')} fehlt"
    vom = [e.get("notiz_vom") for e in eintraege if e.get("notiz_vom")]
    assert all(f"vom {notizen._datum(v)}" in html for v in vom)
    if len(vom) < len(eintraege):
        assert "ohne Datum" in html


def test_the_objects_show_their_notes():
    from finctl import objekte

    mit = [o for o in objekte.vorhandene().values() if notizen.lesen(o)]
    if not mit:
        pytest.skip("kein Objekt mit Notiz")
    html = client.get("/immobilien").text
    for o in mit:
        assert _anfang(o["notiz"]) in html


def test_the_rules_show_their_notes():
    from finctl.rules import regelwerk

    mit = [e for e in regelwerk.laden() if notizen.lesen(e)]
    if not mit:
        pytest.skip("keine Regel mit Notiz")
    html = client.get("/regeln").text
    assert html.count('<details class="notiz"') >= len(mit) - 1
    assert _anfang(mit[0]["notiz"]) in html


def test_the_assumptions_show_the_note_of_their_setting():
    from finctl import assumptions

    if not assumptions.PATH.exists():
        pytest.skip("keine Annahmen")
    spec = yaml.safe_load(assumptions.PATH.read_text(encoding="utf-8")) or {}
    gezeigt = {".".join(assumptions.UEBERSCHREIBBAR[k]) for k, *_ in annahmen_seite.STELLSCHRAUBEN}
    mit = [n for ort, n in notizen.bereiche(spec).items() if ort in gezeigt]
    if not mit:
        pytest.skip("keine Annahme mit Notiz")
    html = client.get("/annahmen").text
    for n in mit:
        assert str(escape(n.text.splitlines()[0][:40])) in html
