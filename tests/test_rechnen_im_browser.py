"""Der Browser rechnet nicht: kein `parseFloat`, `toFixed` und `* 100` in Skripten.

Der Server rechnet alles, was gespeichert wird oder worauf eine Entscheidung
beruht (`docs/Neufassung_plan.md`, Schritt 0). Der Browser nimmt Eingaben auf
und zeigt, was der Server zurueckgibt. Eine Zeile wie
`Math.round(parseFloat(v.replace(',', '.')) * 100)` ist ein zweiter
Betragsparser, und der erste Fehler damit kostete Faktor hundert: auf /split
wurde "1.234,56" als 1,23 EUR gelesen, und der Hundert-Fehler beim Speichern
ohne Aenderung kam aus demselben Muster.

Was noch uebrig ist, steht in `NOCH`: Datei -> Zahl der Treffer. Die Liste darf
kuerzer werden und nichts dazubekommen -- wie `ZU_VERZWEIGT` in
`tests/test_lint.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

VORLAGEN = Path(__file__).resolve().parent.parent / "finctl" / "web" / "templates"

SKRIPT = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)
VERBOTEN = re.compile(r"parseFloat|toFixed|\*\s*100\b|\b100\s*\*")

#: Was Skripte noch rechnen, je Datei. Jede Zeile hier ist Arbeit, die auf den
#: Server gehoert; keine ist ein Grund, sie zu lassen.
NOCH: dict[str, int] = {
    # `centsAus`: der gemeinsame Betragsparser, den noch fuenfzehn Seiten rufen
    # (`grep centsAus finctl/web/templates`). Jede, die ihren Betrag als Text
    # schickt (`..._text`), macht ihn entbehrlicher; er faellt, wenn die letzte so weit ist.
    "_betrag.html": 2,
}


def treffer() -> dict[str, int]:
    aus: dict[str, int] = {}
    for datei in sorted(VORLAGEN.glob("*.html")):
        n = sum(len(VERBOTEN.findall(skript))
                for skript in SKRIPT.findall(datei.read_text(encoding="utf-8")))
        if n:
            aus[datei.name] = n
    return aus


def test_skripte_rechnen_nichts_neues():
    gefunden = treffer()
    neu = {d: n for d, n in gefunden.items() if n > NOCH.get(d, 0)}
    assert not neu, ("Ein Skript rechnet im Browser, was der Server rechnen soll "
                     "(parseFloat, toFixed, * 100):\n"
                     + "\n".join(f"  {d}: {n}x (erlaubt {NOCH.get(d, 0)})"
                                 for d, n in sorted(neu.items())))


def test_die_liste_wird_nur_kuerzer():
    gefunden = treffer()
    weg = {d: n for d, n in NOCH.items() if gefunden.get(d, 0) < n}
    assert not weg, ("Behoben, also aus NOCH streichen oder kuerzen:\n"
                     + "\n".join(f"  {d}: {n}x -> {gefunden.get(d, 0)}x"
                                 for d, n in sorted(weg.items())))


def test_die_suche_findet_etwas():
    """Ohne diesen Test koennte das Muster oder der Ordner leer laufen."""
    probe = "<script>const c = Math.round(parseFloat(t) * 100);</script>"
    assert len(VERBOTEN.findall(SKRIPT.findall(probe)[0])) == 2
