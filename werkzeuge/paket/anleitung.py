"""Die Anleitung zum Mitgeben: docs/installation.md als eine HTML-Datei.

    python werkzeuge/paket/anleitung.py Anleitung.html

Eine Datei, die jeder Rechner ohne Programm oeffnet und druckt, ohne Netz:
Schrift, Farben und Abstaende stehen in der Datei selbst. Gerendert mit
demselben Leser wie das Handbuch in der App, damit es nur EINE Form von
Markdown gibt, die hier zaehlt. Die Versionsnummer steht im Kopf, damit eine
ausgedruckte Anleitung sagt, zu welcher Datei sie gehoert.
"""

from __future__ import annotations

import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(WURZEL))

import finctl  # noqa: E402
from finctl.web import handbuch  # noqa: E402

QUELLE = WURZEL / "docs" / "installation.md"

STIL = """
body { font: 11pt/1.5 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
       color: #1d1d1f; background: #fff; max-width: 42em; margin: 2em auto; padding: 0 1em; }
h1 { font-size: 1.6em; margin-bottom: 0.2em; }
h2 { font-size: 1.15em; margin-top: 1.6em; border-bottom: 1px solid #ddd; padding-bottom: 0.2em; }
code { font: 0.92em ui-monospace, Consolas, monospace; background: #f3f3f3; padding: 0 0.25em;
       border-radius: 3px; }
li { margin: 0.25em 0; }
.version { color: #666; margin-top: 0; }
@media print { body { margin: 0; max-width: none; } h2 { break-after: avoid; } }
"""


def seite(nummer: str) -> str:
    return (f'<!doctype html>\n<html lang="de"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>Finance OS {nummer}: Anleitung</title><style>{STIL}</style></head><body>\n"
            + handbuch.als_html(QUELLE).replace(
                "</h1>", f'</h1>\n<p class="version">Zur Version {nummer}</p>', 1)
            + "\n</body></html>\n")


def main() -> None:
    ziel = Path(sys.argv[1] if len(sys.argv) > 1 else "Anleitung.html")
    ziel.write_text(seite(finctl.__version__), encoding="utf-8")
    print(ziel)


if __name__ == "__main__":
    main()
