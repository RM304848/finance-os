# finance

Lokales Finanzwerkzeug: Python 3.12, SQLite, Typer-CLI `finctl`, FastAPI-Dashboard.
Start: `.venv/bin/finctl serve`, dann http://127.0.0.1:8765.

## Feste Rahmen

- Alles bleibt lokal; Daten verlassen den Rechner nicht.
- Parser und Betrieb laufen ohne KI. KI schreibt nur Regeln und Code.
- Geld in Cent, negativ = raus, positiv = rein.
- Handentscheidungen leben in `config/*_custom.yaml` und `config/overrides.yaml`,
  nie nur in der Datenbank.
- Persönliches steht nur in `config/`: keine echten Namen, Verträge, Anbieter
  oder Beträge in Code, Tests, Kommentaren und Vorlagen. Testdaten sind erfunden.
  Grund: Das Werkzeug soll später anderen dienen, und alles, was jetzt im Code
  landet, muss dann einzeln wieder heraus.
- Module bauen Pfade nicht selbst, sondern nehmen sie aus `finctl/pfade.py`:
  `CONFIG_DIR`, `DATA_DIR`, `STATEMENTS_DIR`, `DB_PATH`. Dort hängt alles an
  einer Wurzel, dem Datenordner (`finctl ort` sagt, welcher und warum).
  Seit dem 27.09.2026 liegen `config/` und `data/` nicht mehr im Repository,
  sondern unter `~/Library/Application Support/Finance OS` -- der Vorgabe des
  Systems, wie bei jedem anderen Nutzer. `FINCTL_DATEN` stellt ihn um.
  `tests/test_pfade.py` hält die Zahl der eigenen Pfade auf null.
- Beide Regeln gehören zum Plan, das Werkzeug später weiterzugeben:
  `docs/Generalization_plan.md`.

## Neufassung: zwei Datenordner

Seit dem 25.10.2026 läuft der Alltag auf `main`: Der echte Datenordner ist mit
`finctl umstellen` umgestellt (Schritt 5), und `/Applications/Finance OS.app` ist
aus `main` gebaut. Zum Nachsehen im alten Stand gibt es den Arbeitsbaum
`~/Projects/finctl-basis` (Tag `basis`, eigenes `.venv`) mit
`FINCTL_DATEN="$HOME/Library/Application Support/Finance OS vor Umstieg 2026-10-25"`.
Er versteht den umgestellten Ordner nicht. Entwickelt wird weiter auf einer Kopie: `export FINCTL_DATEN="$HOME/Library/Application
Support/Finance OS Entwicklung"` vor jedem `finctl`, `pytest` und
`tests/referenz.py`. `finctl ort` zeigt, welcher Ordner gilt. Ohne die Variable
liest und schreibt dieser Checkout die echten Daten (`ort.txt`), und was der
Nutzer im Alltag eintippt, verschiebt die Referenz. Die Kopie hat ihre eigene
`data/referenz/`; sie wird nur in einem eigenen Schritt neu geschrieben.

## Oberfläche

**Vor jeder Änderung an `finctl/web/templates/` `docs/design_conventions.yaml` lesen.**
Dort steht, wie Datumsfelder, Beträge, Farben, Konten, Überschriften, Hinweise,
Suchfelder, Speichern und Texte in dieser App aussehen — mit Begründung.
Eine neue Konvention wird dort eingetragen, nicht nur im Code.
`tests/test_design.py` prüft, was sich maschinell prüfen lässt.

Die Seiten liegen in `finctl/web/routen/`, je Seitengruppe ein Modul mit
eigenem `APIRouter`. `finctl/web/server.py` hält nur noch App, Anmeldung und
das Zusammenhängen; geteilte Bausteine stehen in `finctl/web/basis.py`.

## Tests

`.venv/bin/python -m pytest -q` — alle grün, vor jedem Commit. Zwischendurch
`-m "not langsam"`: Sekunden statt Minuten. Die Tests laufen parallel und in einer
Kopie der Daten (`tests/conftest.py`); nichts davon schreibt in `config/` oder `data/`.

Die Browsertests (`tests/test_browser.py`) laufen nicht mit, sondern allein:
`.venv/bin/python -m pytest -m browser -n 0`, vor jedem Commit, der Vorlagen,
Routen oder Skripte ändert. Im parallelen Lauf hingen sie.

`FINCTL_TESTDATEN=muster` laesst dieselbe Suite auf dem erfundenen Haushalt in
`tests/musterhaushalt/` laufen; ohne `config/` im Projekt geschieht das von
selbst. Beide Laeufe muessen gruen sein. Ein Test nennt deshalb kein Konto,
keinen Kredit und keinen Betrag, sondern liest sie aus `config/` -- Muster:
`_rolle` und `_bindung_im_abschnitt` in `tests/test_web.py`. Braucht ein Test
etwas, das der Musterhaushalt nicht hat, gehoert es dorthin.

`tests/referenz.py pruefen` baut aus `config/` und den Auszuegen neu und vergleicht
Hauptbuch und Seiten mit `data/referenz/`. Ein Umbau darf daran nichts aendern.
Aendert sich ein Ergebnis mit Absicht, wird die Referenz in einem EIGENEN Schritt
neu geschrieben (`schreiben`, die alte wandert nach `data/referenz_archiv/`).

Die Referenz vergleicht jede Seite zweimal: ihre **Zahlen** streng, ihren
**Text** getrennt (`ZAHLEN …` und `TEXT …` in der Ausgabe). Ein Umbau, der Text
mit Absicht ändert, wird mit `tests/referenz.py pruefen --nur-zahlen` gegen die
alte Referenz gemessen, bevor die Textebene neu geschrieben wird.

`tests/test_umbenennung.py` benennt in einer Kopie jedes Konto, Objekt und jeden
Kredit um und baut neu: alle Zahlen müssen gleich bleiben. Dazu ein Test, dass
keine Kennung aus `config/` als Text in `finctl/` steht (ohne `ingest/`, dessen
Leser nach Banken heißen); `BEKANNT` dort darf nur kürzer werden.

`tests/test_browser.py` führt die Skripte der Vorlagen in einem echten Browser
aus (Playwright, das Chrome des Systems; ohne `pytest-playwright` wird die Datei
übersprungen). Sie sichert `config/` und das Hauptbuch und stellt sie zurück.
Skripte rechnen nichts: `tests/test_rechnen_im_browser.py` verbietet `parseFloat`,
`toFixed` und `* 100`; Beträge gehen als Text (`<feld>_text`) an den Server, der
sie mit `parse_eingabe_betrag` liest. Dateien in `config/` schreibt eine Seite nur
über `finctl/dateien.py`, damit Speichern ohne Änderung nichts verändert.

Darin läuft `ruff` mit (`tests/test_lint.py`): null Funde, nicht „wenige".
Was geduldet wird, gehört mit Begründung in `[tool.ruff.lint]` in
`pyproject.toml`, nicht in eine Ausnahmeliste im Test.

`tests/test_namen.py` steht seit dem 23.09.2026 bei **null Fundstellen** und
ist damit eine Sperre, keine Ratsche: Jede neue Stelle mit einem echten Namen
lässt ihn umfallen, es gibt keinen Restposten mehr, in dem sie untergeht.
Braucht ein Test eine Kennung, liest er sie zur Laufzeit aus `config/` --
Muster: `_ein_objekt` in `tests/test_web.py`, `_geteilte_regeln` in
`tests/test_rules.py`.

Die Liste der Namen steht in `config/verbotene_namen.yaml` im Datenordner,
nicht im Repository -- sie besteht aus genau den Namen, die sie verbietet.
`tests/test_leck.py` nimmt das Hauptbuch selbst als Liste: keine Gegenpartei,
kein Betrag mit Cent, keine lange Nummer aus `config/` und niemand, der einen
Anteil traegt, darf im Code, in Tests oder Doku stehen -- und auch kein Stand
und keine Monats- oder Jahressumme, die aus dem Hauptbuch folgt, und kein
Verwandter. Beispiele sind erfunden und rund, und das ist geprueft: In Code und
Doku haben Betraege ab 10 Euro glatte Cent und ab 1.000 glatte Hunderter.
Befunde und Notizen mit echten Zahlen gehoeren nach `notizen/` im Datenordner,
nicht in einen Kommentar -- dort fallen sie beim Weitergeben mit raus.

`ZU_VERZWEIGT` in `tests/test_lint.py` führt die Funktionen mit einem
Verzweigungsgrad über 10. Die Liste darf kürzer werden und nichts
dazubekommen — wie `ausnahmen`/`offen` in `docs/design_conventions.yaml`.
