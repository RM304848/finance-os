# Schritt 6 bis 8: Arbeitsplan

Stand 01.11.2026 (Opus). Der Haushalt will die Neufassung zeitnah abschließen.
Grundlage ist `docs/Neufassung_plan.md`, Schritt 6 bis 8. Die Auslieferung
an einen ersten fremden Nutzer (0.5.0, Windows, Sparkasse) hat Teile von
Schritt 8 schon vorweggenommen: das Paket, den ersten Start mit leerem
Ordner und die Einrichtung im Frontend.

Opus vergibt jeden Teilschritt an eine eigene Sitzung, nimmt ihn ab und
schreibt die Referenz neu. Parallel laufen nur Teilschritte, deren Dateien
sich nicht berühren und von denen höchstens einer die Zahlen der Referenz
ändert.

## Reihenfolge

| Teil | Inhalt | Modell | Zahlen | Läuft neben |
|---|---|---|---|---|
| 5b-H | Schritte mit dem Haushalt: App neu bauen, erwartete Einnahmen (die Schenkung jährlich im Januar), drei Korrekturzeilen löschen, tote Schlüssel, Median; die Schenkung auch in der Kopie | Opus | ja, nur in der Kopie | allem |
| 6a | Der Server baut das HTML: Tabellenzeilen von `abos.html` und `planung.html` kommen als Stücke aus Jinja-Vorlagen, die Skripte setzen keine Zeilen mehr zusammen; die Browserprobe prüft „Text hin, Antwort zeigen“ | Sonnet | gleich | 8b |
| 8b | Die Tabelle `settings` samt Abgleich aufräumen, `--probe` schreibt nur bei Erfolg, eine Notiz lässt sich ohne SQL löschen | Sonnet | gleich | 6a |
| 6b | Begriffe nach `CONTEXT.md` in allen Vorlagen außer abos/planung, Notizen sichtbar und datiert, Regel „fester Text nennt keine Einzelfälle“ in `design_conventions.yaml` mit Test | Sonnet | gleich, Text neu | 8a |
| 8a | `abos.termine` rechnet Termine als `faellig` plus ein Vielfaches des Takts | Sonnet | ja | 6b |
| 6c | Kleine Punkte: Entfernen nennt die Notiz; die Kontokarte bietet Kredite an; Umwandler mit Umlauten; Feld „Warum“ an Verträgen; „Budgettopf“ im Handbuch; Hinweis auf eine Buchung, die zu einer einmaligen Planzeile passt, ihr aber nicht zugeordnet ist | Sonnet | gleich | 7a |
| 6d | Prognosebasis neu: eine Seite, die zeigt, woraus beide Rechnungen ihre Basis nehmen, ohne zu erklären, warum sie auseinanderlaufen | Sonnet | gleich, Text neu | 7a |
| 7a | Kopiervorlage: Die App erzeugt eine Vorlage für ein Modell nach Wahl, mit Begriffen, Lage und Frage; nichts verlässt den Rechner | Sonnet | gleich | 6c, 6d |
| 7b | MCP-Zugang über dieselben geprüften Wege wie die Oberfläche. Lesen ist frei; Schreiben ist ein Vorschlag, den der Haushalt in der App bestätigt. Standard ist ein lokales Modell. `CLAUDE.md`, Regel zu den Daten, nach ADR 0002 | Opus plant, Sonnet baut | gleich | – |
| 7c | Externe API nur auf ausdrückliche Wahl, mit Anzeige, was den Rechner verlässt | Sonnet | gleich | – |
| 8c | Prüfen, was noch einen Texteditor braucht, und die Lücken schließen. Abschluss: Umbenennungsprobe und Musterhaushalt zeigen, dass der Code keinen Einzelfall kennt | Sonnet | gleich | – |

**Fertig wenn** (je Teil): beide Suiten und die Browsertests grün;
`tests/referenz.py pruefen --nur-zahlen` gleich, außer bei 8a und 5b-H, wo
der Bericht die Unterschiede erklärt; ein Abschnitt mit Bericht und
Abweichungen in dieser Datei; `CHANGELOG.md` „Unveröffentlicht“ in Worten
der Nutzer.

## Plan für 7b (Opus, 01.11.2026)

**Ziel:** Ein Modell, das der Haushalt wählt, liest über MCP dieselben Lagen wie die Seiten und kann Handentscheidungen vorschlagen. Es schreibt nie selbst. Den Vorschlag bestätigt der Haushalt in der App, und danach ist er eine Handentscheidung wie jede andere.

1. **Ein Befehl, kein Netz:** `finctl mcp` spricht MCP über stdin/stdout (JSON-RPC, `initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`). Er öffnet keinen Port. Die Umsetzung ist klein und eigen, unter `finctl/mcp/`, ohne neue Abhängigkeit, damit Rad und App ohne Netz gebaut werden. Ein Modell bindet ihn ein wie jeden MCP-Server über stdio. Das Handbuch nennt als Standard ein lokales Modell und zeigt die Einbindung allgemein, ohne Produktnamen im festen Text.
2. **Lesen:** Werkzeuge über die Funktionen, aus denen die Seiten rechnen, nicht über SQL. Dazu gehören Konten mit Kontoprognose, Jahresrechnung, Fortschreibung je Block (`forecast/quellen.py`), Buchungen suchen (höchstens 200 Zeilen, bereinigter Text, ohne IBAN, wie 7a), Kategorien, Verträge, Klammern mit Planzeilen, Kredite, Objekte, Ziele und offene Punkte des Monatsabschlusses. Das Glossar steht als Ressource (`CONTEXT.md`). Jede Antwort geht durch dieselbe Sperre wie die Vorlagen aus 7a (`_ohne_nummern`).
3. **Vorschlagen statt Schreiben:** Das Werkzeug `vorschlagen` nimmt eine Art und die Felder genau so, wie die bestehende Route sie nimmt. Arten zu Beginn: Regel, Planzeile in einer Klammer, Kredit, Notiz an einem Eintrag. Der Vorschlag landet in `data/vorschlaege/` (eine Datei je Vorschlag), nicht in `config/`. Er ist noch keine Entscheidung. Er wird mit derselben Prüfung gelesen, die die Route benutzt, und ein ungültiger Vorschlag kommt mit der Meldung der Route zurück.
4. **Bestätigen in der App:** Die neue Seite `/vorschlaege` zeigt jeden Vorschlag mit dem, was sich ändern würde. „Übernehmen“ schickt die Felder an die **bestehende** Route, „Verwerfen“ löscht die Vorschlagsdatei. Die Navigation zeigt die Zahl offener Vorschläge.
5. **Lücken nennen:** Liste im Bericht, welche Handentscheidungen die Schnittstelle noch nicht ausdrückt (ADR 0002, „vollständig genug“).
6. **Regel zu den Daten:** In `CLAUDE.md` wird „Alles bleibt lokal; Daten verlassen den Rechner nicht“ zu „Daten verlassen den Rechner nur auf ausdrückliche Wahl des Haushalts (ADR 0002); die App selbst sendet nichts ohne diese Wahl“. Das schreibt Opus bei der Abnahme.

**Tests:**
- Protokoll: Handshake, Liste und Aufruf über eine echte Pipe zu `finctl mcp`.
- Keine IBAN und keine lange Nummer in einer Antwort; die Prüfung liest sie zur Laufzeit aus `config/`.
- `vorschlagen` lässt `config/` byteweise gleich.
- Übernehmen ergibt dieselbe Datei wie derselbe Eintrag über die Seite.
- Verwerfen lässt nichts zurück.
- Ein Browsertest für `/vorschlaege`.

**Modell:** Sonnet. **Fertig wenn:** wie oben, dazu `pruefen --nur-zahlen` gleich.

## Berichte

(Hier trägt jede Sitzung ihren Abschnitt ein; Opus seine Abnahme.)

### 8b

**Umgesetzt am 01.11.2026 (Sonnet).** Alles an der Entwicklungskopie (`FINCTL_DATEN`) und an erfundenen Ordnern in Tests; der echte Datenordner und die Entwicklungskopie sind nicht umgestellt und nicht verändert worden. Beide Suiten sind grün bis auf drei Tests in `test_design.py` (`_abo_neu.html`, `_abo_teilen.html`, `_abo_editor.html`: neue Teilvorlagen von 6a, nicht von mir). Browsertests nicht gelaufen: keine Vorlage, Route oder Skript geändert. Die Referenz ist nicht neu geschrieben.

**1. Tabelle `settings`.** Befund: Sie hat seit N.3f weder Leser noch Schreiber. Der einzige Leser war der Abgleich in `umstellen`; `/api/setting` schreibt in `assumptions.yaml`, die Untergrenzen gehen über `/api/floor` nach `forecast.yaml`. Es gibt also nichts Abgeleitetes darin, das bleiben müsste. Vorschlag, umgesetzt (ändert keine Zahl):
- `schema.sql` legt die Tabelle nicht mehr an. Neue Datenbanken haben sie nicht.
- Der Abgleich ist nach `finctl/umstellen_tabelle.py` gezogen. Er hält weiter an bei einer Zeile nur in der Tabelle, bei einem abweichenden Wert und bei einer Notiz, die in keiner Notiz der Datei steht. Neu: Ist die Datei neuer als die Zeile (`mtime` gegen `updated_at`), gilt die Datei; das geht als Hinweis in den Bericht, nicht als Fehler. Eine Notiz der Tabelle zählt nicht mehr, wenn ihr Text (Leerraum ignoriert) in einer Notiz der Datei steht. Eine Zeile nur in der Tabelle hält auch bei neuerer Datei an: Aus der Zeitangabe lässt sich nicht lesen, ob sie absichtlich fehlt.
- Ein Lauf, der den Abgleich bestanden hat, entfernt die Tabelle (`DROP TABLE`) aus der Datenbank. Ohne Seitendatei kein Abgleich, also auch kein Entfernen. `--probe` entfernt nie, der Bericht sagt „würde entfernt“.
- Neu `--tabelle-verwerfen`: Funde des Abgleichs halten nicht an, sondern stehen im Bericht („Verworfen (auf Wunsch)“, mit dem Text der Notiz) und gehen mit der Tabelle. Das ist der Ausweg für eine Zeile, die der Haushalt nicht übernehmen will, und ersetzt das `DELETE FROM` im Handbuch.
- `tests/referenz.py`: Eine leere `hauptbuch/*.json` (`[]`) in der Referenz, zu der es nichts Neues gibt, zählt als gleich. Sonst meldete `pruefen` „hauptbuch/settings.json fehlt jetzt“, obwohl dort nie eine Zeile stand.
- Offen: Die Tabelle steht in der echten `finance.db` (drei Zeilen, gleich der Datei) und in der der Entwicklungskopie noch, ungelesen. Hier wird nichts angefasst; das Umstellen läuft nicht mehr, weil `settings_custom.yaml` fehlt. → Opus: Sie bleibt als totes Stück stehen. Soll sie weg (eine Zeile `DROP TABLE settings` nach der Kopie), entscheidet der Haushalt; nichts liest sie.

**2. `--probe`.** `probieren` schreibt nur, wenn `plan.zu_tun` und kein Fehler vorliegt; sonst kein Ordner, keine Kopie, kein Bericht. Das Terminal sagt „Nichts umzustellen … Es wurde keine Kopie geschrieben.“ bzw. nennt die gescheiterten Prüfungen und sagt, dass keine Kopie entstand.

**3. Notiz löschen.** Gedeutet als die Notiz in der Tabelle `settings` (so steht es bei N.4d: „in diesem Haushalt gibt es keine“). Einen Weg, auf dem sie dort „entsteht“, gibt es nicht mehr. Löschen geht jetzt ohne SQL auf zwei Wegen: Übernimmt der Haushalt sie in die Datei, ist sie dort eine gewöhnliche Notiz (löschbar in der App) und die Tabelle geht beim Umstellen; will er sie nicht, verwirft sie `--tabelle-verwerfen` samt Eintrag im Bericht. → Opus: Falls 3 etwas anderes meinte (eine Notiz auf einer Seite), bitte sagen; ich habe sonst keine solche Stelle gefunden.

**Tests.** `test_umstellen_paare.py` (Abschnitt „settings“): Datei neuer, Zeile nur in der Tabelle bei neuer Datei, Notiz in der Datei, Tabelle nach dem Lauf weg, gestoppter Lauf und Probe lassen sie stehen, Verwerfen samt Bericht, ohne Seitendatei kein Entfernen, frisches Hauptbuch ohne Tabelle, Befehl mit Hinweis und Option. `test_umstellen.py`: Probe ohne Anlass und mit gescheiterter Prüfung schreibt keine Kopie (Funktion und Befehl). Die alten Tests legen die Tabelle selbst an, weil das Schema es nicht mehr tut; `test_web.py` ebenso.

**Prüfen.** `tests/referenz.py pruefen --nur-zahlen` meldet **nicht** Gleich, aber nichts aus 8b: `hauptbuch/` und `ableitung/` sind gleich, auf `seiten/` stehen die Versionsnummer (0.4.1 → 0.5.0 auf annahmen, bestaende, einrichtung und weiteren Seiten, von Commit „Version 0.5.0“) und die Zeilen aus 6a (`abos`, `api__abos__neu`, `vertraege` …). → Opus: Die Referenz ist vor 0.5.0 geschrieben; sie muss vor der Abnahme von 6a neu, sonst lässt sich 6a und 8b nicht trennen. Fremde Fehlschläge: die drei `test_design`-Tests (6a); `test_referenz` aus demselben Grund.

**Zu 8b im selben Commit:** `CHANGELOG.md` trägt in „Unveröffentlicht“ auch den Eintrag von 6a (Treffer der Buchungssuche), weil beide in einer Datei stehen.

**8b abgenommen am 01.11.2026 (Opus).** Die Deutung von Punkt 3 stimmt: Gemeint war die Notiz in der Tabelle `settings` (N.4d). Zu den Abweichungen:
1. **Tabelle im echten Ordner und in der Kopie:** Sie bleibt stehen. Nichts liest sie, und ein `DROP TABLE` von Hand ist genau der Eingriff, den 8b abschafft.
2. **Referenz:** Vor der Abnahme für die Versionsnummer 0.5.0 neu geschrieben (`8aec989`, alte Ausgabe in `notizen/Version_0.5.0_referenz_vor_neuschreiben.txt`): 72 Unterschiede, alle „0.4.1“ zu „0.5.0“ im Fuß. Danach Gleich. 6a misst gegen diese Referenz.
3. **Leere `hauptbuch/*.json` gilt als gleich:** angenommen.

**6a abgenommen am 01.11.2026 (Opus), Referenz neu geschrieben.** `pruefen` auf einem sauberen Arbeitsbaum von `730e7f8`: sechs Unterschiede, nur `abos`, `versicherungen` und `vertraege`, und nur hinzugekommene Zeilen (alte Ausgabe in `notizen/6a_referenz_vor_neuschreiben.txt`). Danach Gleich; beide Suiten und die Browsertests grün. Zu den Abweichungen:
1. **Vorzeichenfarbe der Treffer:** angenommen.
2. **Editoren schon beim Laden in der Seite:** angenommen, so war es gemeint. Die Seite und die Schnittstelle zeichnen aus derselben Vorlage, und die Referenz sieht den Editor jetzt.
3. **Drei Erklärabsätze in Teilvorlagen:** gehen in 6b mit den Begriffen der Seite (`details.hilfe` oder Handbuch); die Ausnahmen sind `offen` und dürfen nur weniger werden.
4. **Tippen während des Neuzeichnens:** in 6c messen und, wenn nötig, absichern (das Neuzeichnen wartet, bis kein Feld mehr den Fokus hat, oder übernimmt den Fokus).
5. **`neueKlammer` doppelt in `planung.html`:** in 6c entfernen.

### 8a

**Umgesetzt am 01.11.2026 (Sonnet).** Alles an der Entwicklungskopie (`FINCTL_DATEN`); der echte Datenordner ist nicht berührt, die Referenz nicht neu geschrieben. Browsertests nicht gelaufen: keine Vorlage, Route oder Skript geändert.

**1. Tests zuerst** (`tests/test_abos.py`, erfundene Verträge). Fünf schlugen vor dem Umbau fehl: Termin am 31. nach dem Februar (auch im Schaltjahr), derselbe Termin rückwärts vom erklärten aus, Fenster mehrere Takte vor `faellig` (monatlich, vierteljährlich, jährlich), Quartals- und Jahrestakt mit Tag 30 und 29. Februar, Kündigung und Vorrat in einem langen Fenster. Dazu ein Test, der die Fenstergrenzen (beide eingeschlossen, leeres Fenster) festhält und schon vorher grün war.

**2. `abos.termine`.** Jeder Termin ist `plus_monate(faellig, k * takt)` mit ganzzahligem k, auch negativ, immer direkt aus `faellig`. k beginnt beim Monat von `ab` (abgerundet), was vor `ab` liegt, fällt weg. Kündigung und Vorrat wirken wie bisher. `kalender.plus_monate` kappt den Tag am Monatsende richtig (31. → 28./29./30., aus dem Original gerechnet) und blieb unverändert.

**3. Weitere Stellen.** Gesucht über `plus_monate`, `takt` und alle Aufrufer von `termine`:
- `finctl/forecast/vertraege.py` (`termine`), `konten.py` (`_anteilsposten`), `jahre.py` (`_vertragsposten`), `prognosebasis.py` und `abos.posten` rufen alle `abos.termine`. Sie bekommen die Korrektur ohne eigene Änderung.
- `finctl/forecast/treffer.py` (`_zeitraumanteil`) hatte eine Umgehung, die den Fehler kannte („Monat für Monat: `abos.termine` zählt in einem langen Fenster nur vom letzten Termin an“). Jetzt ein Aufruf über das ganze Fenster des Zeitraums. Das Ergebnis ist gleich, außer wo ein Termin am 29. bis 31. verrutscht wäre.
- `finctl/energie/zaehler.py` (`zahlungstermine`) rechnet schon `plus_monate(beginn, n)` aus dem Beginn: keine Änderung nötig.
- `finctl/fristen.py`, `abos.py` (`erwartete_anteile`, Mitzahler: `monate // takt`) zählen nur, summieren keine Termine.
Keine weitere Stelle zählt Vertragstermine auf.

**4. Wirkung.** `tests/referenz.py pruefen --nur-zahlen`: **Gleich**, kein einziger Unterschied (Ausgabe und Vergleich in `notizen/8a_pruefen_unterschiede.txt` der Kopie). Erklärung: Kein Vertrag der Kopie ist heute fällig am 29. bis 31. und noch zahlend (der einzige am 30. ist gekündigt), und keiner der Aufrufer fragt ein Fenster, das vor `faellig` beginnt und `faellig` einschließt. Zusätzlich alt gegen neu für alle 19 Verträge im Fenster der Prognose (Nov 2026 bis Okt 2027): gleich. In einem weiten Fenster (2024 bis 2030) liefert der Umbau erwartungsgemäß mehr Termine; das ruft heute niemand.

**Abweichungen.**
- Der Test `test_nothing_is_due_after_the_cancellation` fragte ein Fenster ab 2026-09-01 bei `faellig` 2026-10-01 und erwartete nur Oktober bis Dezember. Das war das alte Verhalten (ein Fenster, das `faellig` einschließt, begann bei `faellig`). Jetzt kommt auch der 1. September, wie die Aufgabe es verlangt; ich habe das Fenster des Tests auf 2026-10-01 gesetzt statt seine Erwartung zu ändern. → Opus: Falls ein Vertrag „vor `faellig`“ nie Termine haben soll, sagen; der Wortlaut in `Neufassung_plan.md` („`faellig` ist der NÄCHSTE Termin“) spricht für die jetzige Lösung.
- → Opus: Weil die Messung keinen Unterschied zeigt, ist die Referenz nicht zu ändern; sie braucht keinen eigenen Schritt. Ein Test mit einem echten Fall am 31. fehlt in der Referenz; die erfundenen Tests decken ihn ab.

### 6b

**Umgesetzt am 01.11.2026 (Sonnet), nichts committet, bevor alles grün war.** Alles an der Entwicklungskopie (`FINCTL_DATEN`); `finctl/abos.py` und `finctl/forecast/` nicht angefasst (8a ist schon committet, `9b0dcf1`). Der echte Datenordner und `config/` der Kopie sind unverändert.

**Prüfen.** Beide Suiten grün (Entwicklungskopie, Musterhaushalt), Browsertests grün (`-m browser -n 0`), `ruff` null Funde. `tests/referenz.py pruefen --nur-zahlen` zeigt gegen die alte Referenz Unterschiede, weil 8a Zahlen ändert. Darum habe ich gegen einen Arbeitsbaum von `9b0dcf1` (8a drin, 6b nicht) gemessen, beide mit `neu_bauen` aus der Kopie, Stichtag 2026-10-25: `hauptbuch/` und `ableitung/` **gleich**, auf `seiten/` elf Seiten mit Unterschied in der Zahlenebene (`annahmen`, `prognosebasis`, `immobilien`, `immobilie__*` ×4, `kategorien`, `kredite`, `regeln`, `ziele`) und **in keiner fehlt eine Zahl**: Es sind hinzugekommene Zeilen, nämlich der Text sichtbarer Notizen mit Ziffern darin. Die einzige Ausnahme sind zwei Zeilen auf `/ziele` (die Notiz stand im Stichtag-Satz und steht jetzt im eigenen Block). Prüfung: je Seite `Counter(zahlen(alt)) - Counter(zahlen(neu))` leer. → Opus: Gleich im strengen Sinn geht bei sichtbaren Notizen nicht; wer die Referenz neu schreibt, schreibt diese Zeilen mit. Der Unterschied der Textebene (alt gegen neu, also ohne 8a) liegt in `notizen/6b_text_unterschiede.txt` im Datenordner der Kopie (47 Seiten; jede trägt die geänderte Navigation). Die Referenz ist nicht neu geschrieben.

**1. Begriffe.** Durchgesehen: alle Vorlagen, `routen/*.py`, `basis.py`, dazu die Meldungen, die ein Fachmodul an die Seite gibt (`finctl/geteilt.py`, `monatsabschluss.py`, `rules/vorschlaege.py`). Geändert nur, wo ein Wort aus `_Avoid_` genau den Begriff meinte. Tabelle alt → neu (nur sichtbarer Text; Kennungen, Adressen, Klassen, Dateinamen und Kommentare bleiben):

| Datei | alt → neu |
|---|---|
| `base.html` (Navigation) | Geteilt → Themenkassen (Gruppe); Budgettöpfe → Themenkassen; Buchungen (unter Geteilt) → Zuordnen; Transaktionen → Buchungen; Immobilien → Objekte; Abos und Versicherungen → Verträge; Renten → Rentenquellen |
| `projekte.html` | Budgettopf/Budgettöpfe → Themenkasse/Themenkassen (Titel, Überschrift, Spalte, Knopf, Platzhalter, Rückfrage, Konfigurationsfuß); Personen → Beteiligte; Neue Person → Neuer Beteiligter |
| `salden.html` | Budgettopf → Themenkasse; Personen → Beteiligte; Person → Beteiligter |
| `geteilt_buchungen.html`, `routen/geteilt.py`, `finctl/geteilt.py` | Budgettopf → Themenkasse (Beschriftungen, Meldungen); Person → Beteiligter (Meldung); Aufteilung → Teilung (Feld und Meldung: gemeint ist, wie eine Buchung auf Beteiligte verteilt wird, nicht ihre Teile) |
| `transactions.html`, `immobilie.html`, `monatsabschluss.html`, `planung.html` | Transaktion(en) → Buchung(en); Zahlung → Buchung; Umsätze → Buchungen (`einrichtung.html` ebenso) |
| `split.html`, `_ops.html`, `monatsabschluss.html`, `planung.html`, Konfigurationsfüße | Split/Splits, Aufteilung → Teil/Teile; manuelle Entscheidungen, Entscheidung von Hand → Handentscheidungen |
| `_ops.html`, `_neues_konto.html`, `einrichtung.html`, `monatsabschluss.html` | Backup, Snapshot → Sicherung |
| `monatsabschluss.html`, `_ops.html`, `_neues_konto.html`, `einrichtung.html`, `ziele.html`, `renten.html`, `routen/konten.py`, `finctl/monatsabschluss.py` | Kontostand, Saldo (eines Kontos oder Auszugs), Wert (einer Position) → Stand; Kontoauszug → Auszug; CSV-Export → Auszug als CSV |
| `rueckblick.html` | Position (Zeile einer Kategorie) → Kategorie; Partner/Vertragspartner → Gegenpartei |
| `reihen.html` | Zahlung → Reihe zahlt; Ausreißer → Einmalig |
| `_klammer.html`, `planung.html`, `routen/planung.py` | Plan, Szenario → Klammer; Position → Planzeile; Frequenz → Takt; Projektion → Hochrechnung; Schuld → Verpflichtung |
| `base.html`, `renten.html`, `immobilien.html`, `routen/auswertung.py`, `routen/einrichtung.py` | Renten, Rente (Eintrag), Quelle → Rentenquelle(n); Immobilien → Objekte (auch `einrichtung.html`) |
| `konten.html`, `annahmen.html`, `abos.html`, `routen/auswertung.py` | Abos mit Termin, Geteilte Abos → Verträge (mit Mitzahlern); Girokonto (Kontoart) → Giro; Übertrag → Umbuchung; Zweck (Feld) → Notiz; Budget und Mindestniveau → Untergrenze, Deckel und Auffüllen |
| `_abo_teilen.html`, `abos.html` | Geteilt → Mitzahler; Person → Mitzahler |
| `annahmen.html`, `routen/annahmen.py` | Prognosebasis → Fortschreibung; Einstellung → Annahme |
| `energie.html`, `hochrechnung.html`, `routen/kredite.py` | Herleitung → Rechenweg (Posten einer Zahl) bzw. Notiz (Quelle einer Rentenquelle, Kredit) |
| `kredite.html` | Darlehen → Kredit; Annuitätendarlehen → Kredit |
| `regeln.html`, `finctl/rules/vorschlaege.py` | Claude → KI-Modell (Anbieter); Empfänger → Gegenpartei |

→ Opus: Begriff fehlt (nichts geändert):
- **Saldo** als Überschuss eines Zeitraums (Kacheln, Hochrechnung, Treffer, Energie) und als Forderung einer Themenkasse (Seite `/salden`); das Glossar kennt nur Stand.
- **Teilung** (wie eine Buchung auf Beteiligte verteilt wird) und **Block** (die Gruppe von Kategorien in Planung, Annahmen, Wirkung; das Glossar benutzt „je Block“, ohne ihn zu führen).
- **Mindestbestand** eines Vorrats (Untergrenze gilt nur für Konten), **Einstellungen** eines Zählers oder Vorrats, **Rücklagen** im Flussdiagramm („aus Rücklagen“, Konvention `flussdiagramm`), **Basis** eines Ziels und der Kredittabelle, **Review** (Buchungen ohne Kategorie), **Ledger**, **Rendite** als Spalte eines Objekts.
- **Vorgang** und **Anlageklasse** kommen im sichtbaren Text nicht vor („Topf“ steht nur in Kommentaren).
- Nicht geändert, weil das Glossar das Wort selbst benutzt: Zahlung (eines Mitzahlers), Termin (eines Vertrags), Position, Bestand, Wert (einer Annahme).
- Nicht durchgesehen: Kommentare und Docstrings (auch dort stehen die alten Wörter), englische Fehlermeldungen in den Routen (`kategorien.py`, `konten.py`), der Text der Befehlszeile, `HANDBUCH.md` außer den Stellen unten („Budgettopf im Handbuch“ ist 6c).

**2. Fester Text nennt keine Einzelfälle.** Neue Regel `fester-text-nennt-keinen-einzelfall` in `design_conventions.yaml` (mit Grund), dazu `begriffe-des-glossars` (ohne Mustersuche: Handarbeit, jedes Wort hat Ausnahmen). Test in `tests/test_design.py` (`einzelfaelle`): liest zur Laufzeit Kennungen und Namen aus `config/` (Konten mit Bank und Anzeigename, Kredite, Objekte, Verträge, Ziele, Rentenquellen, Gruppen, Klammern, Themenkassen, Beteiligte; ohne die Wörter des Glossars) und sucht sie im festen Text der Vorlagen (ohne Kommentare) und den Zeichenketten der Routen (ohne Docstrings und SQL). Ausnahmen je Datei als Zahl, die nur sinkt (`ausnahmen`, `offen`). Gefunden und behoben: Platzhalter mit Anbieter (`Name bei PayPal`, `Sparkasse Giro`, `Sparkasse`, `amazon-prime`, `Amazon Prime`, `über Amazon`), „Claude“ in `regeln.html` (dreimal), eine Kennung im Konfigurationsfuß von `monatsabschluss.html`. **Eine Ausnahme bleibt:** `routen/auswertung.py: 2` (die Fortschrittszeile des Monatsabschlusses sucht ein Ziel nach seiner Kennung und nennt es beim Namen). → Opus: Das lässt sich nur mit einem Merkmal am Ziel in `goals.yaml` lösen (welches Ziel der Abschluss zeigt), und das schreibt in die Dateien des Haushalts; ohne dieses Merkmal ändert sich die Zeile. Auf dem Musterhaushalt springt der Test an (wie `test_leck.py`): seine Namen sind erfunden und allgemein, und er trägt selbst ein „Gemeinschaftskonto“, das der Code als festen Begriff führt (Karte auf `/konten`, Linie im Diagramm, Kategorie in `forecast/ohne_objekt.py`). → Opus: Das ist ein Einzelfall im Code, den die Kopie nicht findet; ich habe ihn nicht angefasst (`finctl/forecast/` ist gesperrt). Betrag und Monat prüft der Test nicht: Platzhalter wie `90,00` und `2027-04` sind Formatbeispiele (Regel `datum-als-text`), und Beträge aus dem Hauptbuch sucht `test_leck.py`.

**3. Notizen sichtbar und datiert.** *Vorschlag und Umsetzung zugleich, weil nichts Neues nötig ist:* Das Datum gibt es schon. `notizen.fortschreiben` setzt `notiz_vom`, wenn der Haushalt den Text beim Speichern ändert; ein unveränderter Text und ein fehlendes Datum bleiben, wie sie sind. Die Seiten lesen es nur. **Keine Datei des Haushalts wird geschrieben**, ohne dass jemand speichert; Einträge ohne Datum (in der Kopie fast alle) zeigen „ohne Datum“. Neu: `_notiz.html` (Makros `zeile(text, vom)` und `stand(vom)`), `notiz_felder` in `basis.py`, Regel `notiz-sichtbar` (mit Prüfung), Stil `details.notiz`. Aufklappbar mit Datum: Kredite (je Kredit), Objekte (Liste und Seite eines Objekts), Regeln (je Regel), Annahmen (je Stellschraube, aus dem Block `notizen:`), Kategorien (an der Oberkategorie, bei ihrem ersten Eintrag), Themenkassen (im Bereich zum Bearbeiten), Ziele (unter dem Stichtag-Satz, die Notiz stand dort bisher im Satz). Datum neben dem Feld: Ziele, Rentenquellen, Konten, Verträge („Warum“, kommt als `warum_vom` aus der Route; `finctl/abos.py` blieb unberührt), Monatsabschluss, Reihen. Nicht umgesetzt: Planung (Klammern tragen laut Regel keine Notiz), Einrichtung (die Notizen von `lebensplan.yaml`), Energie, Steuer, Buchungen zuordnen. Test: `tests/test_notiz_sichtbar.py` (liest die Einträge zur Laufzeit; auf dem Musterhaushalt bleiben die meisten Fälle ohne Notiz und werden übersprungen).

**4. Erklärabsätze aus 6a.** Die drei Absätze stehen jetzt als zwei `details.hilfe` oben auf `/vertraege` („Buchungen und neuer Vertrag“, „Mitzahler“, zusammen unter 60 Wörtern je Bereich); aus `_abo_editor.html`, `_abo_neu.html`, `_abo_teilen.html` sind sie raus, und die Ausnahmen (`ausnahmen` und `offen` von `ein-zwecksatz-je-seite`) sind gestrichen. Handbuch (beide Kopien gleich, `/vertraege` bleibt unter 200 Wörtern): Mitzahler statt Geteilt, ein Satz zu Notizen in Abschnitt 2, „Vorschläge über ein KI-Modell“.

**Weitere Änderungen.** Tests an den neuen Wörtern nachgezogen (`test_web.py`, `test_geteilt.py`, `test_kredite_anlegen.py`, `test_kontostand.py`, `test_browser.py`). Die Navigation heißt in `design_conventions.yaml` (`navigation`) jetzt Themenkassen. `CHANGELOG.md` „Unveröffentlicht“ hat drei neue Einträge in Worten der Nutzer.

**8a und 6b abgenommen am 01.11.2026 (Opus), Referenz neu geschrieben.** `pruefen` auf einem sauberen Arbeitsbaum von `1c588a6` ergab 47 Unterschiede. `hauptbuch/` und `ableitung/` sind gleich, auf der Zahlenebene gibt es elf Seiten mit Unterschieden. Jede Zahl, die wegfällt, steht wieder auf der Seite (auf `/regeln` und `/ziele` nur in einer anderen Zeile). Dazu kommen die Ziffern aus den Notizen. Die Ausgabe liegt in `notizen/6b_8a_referenz_vor_neuschreiben.txt`. 8a ändert für die Daten der Kopie keine Zahl. Zu den Abweichungen:
1. **8a, Fenster im Kündigungstest:** angenommen. `faellig` ist der nächste Termin; ein Fenster davor hat Termine.
2. **6b, fehlende Begriffe** (Saldo als Überschuss, Teilung, Block, Mindestbestand, Rücklagen, Basis, Review, Rendite): Opus klärt sie in 8c mit dem Glossar. Bis dahin bleibt der Text.
3. **6b, Ziel im Monatsabschluss nach Kennung:** Die Ausnahme `routen/auswertung.py: 2` bleibt. Ein Merkmal in `goals.yaml` kommt in 8c, wenn der Haushalt es will.
4. **6b, „Gemeinschaftskonto“ als fester Begriff im Code** (Karte, Linie, `forecast/ohne_objekt.py`): ein Einzelfall im Code, Teil des Abschlusses in 8c.
5. **6b, Notizdatum aus `notiz_vom`:** angenommen. Es wird nichts geschrieben, ohne dass jemand speichert.

### 7a

**Umgesetzt am 01.11.2026 (Sonnet).** Alles an der Entwicklungskopie (`FINCTL_DATEN`). Neue Seite `/vorlagen` (Gruppe Stammdaten, `APP_SEITEN`), Logik in `finctl/web/vorlagen.py`, Route in `finctl/web/routen/vorlagen.py`, Vorlagen `vorlagen.html` und `_vorlage_antwort.html`. Die App schickt nichts; geschrieben wird nur über `/api/regeln/vorschlaege/uebernehmen`, nachdem jemand anhakt.

**1. Welche Vorlagen.** Drei, wie vorgeschlagen: **Buchungen einordnen**, **Monat erklären**, **Frage zur Prognose**. Begründung: Jede beantwortet eine Frage, die der Haushalt heute von Hand stellt, und jede hat Funktionen, aus denen die Seiten schon rechnen (Offene Texte und Regeln; Monatsabschluss und Rückblick; Kontoprognose und Jahresrechnung). Weitere (Verträge, Ziele, Kredite) kommen mit 7b über den MCP-Zugang, wo das Modell selbst nachfragt.

**2. Aufbau.** Begriffe, Lage, Frage. Die Begriffe liest `glossar()` aus `CONTEXT.md` (Erklärung und „Nicht: …“), je Vorlage eine feste Liste von Namen; ein Name ohne Eintrag wirft, ein Test hält das. `CONTEXT.md` liegt dafür wie das Handbuch als Kopie unter `finctl/` (`pyproject.toml`, `test_paket.py` hält beide byteweise gleich).
- *Einordnen:* Kategorien und die bereinigten Texte der offenen Buchungen (`vorschlaege.offene_texte`), abwählbar; die Seite nimmt nur Texte, die sie selbst angeboten hat.
- *Monat:* Summen je Oberkategorie im gewählten Monat gegen den Schnitt der zwölf davor (`_je_monat`, Basis „laufend“), Einnahmen und Ausgaben, Zahl der Buchungen ohne Kategorie, offene Posten des Monatsabschlusses (`monatsabschluss.konten/bestaende`).
- *Prognose:* Kontoprognose (`ops.household_accounts`), Vermögen je Jahr (`_jahresrechnung`), Annahmen, dazu die eigene Frage (höchstens 500 Zeichen).
- Als letzte Sperre ersetzt `_ohne_nummern` jede IBAN und jede Ziffernfolge ab neun Stellen in der Lage.

**3. Antwort.** Einordnen: `Suchtext ; Kategorie`, Prüfung und Anhaken wie bisher (`vorschlaege.pruefen`). Monat und Prognose: `ZUSAMMENFASSUNG: …` und `AUFFÄLLIG: Kennung ; Satz`. Die Seite markiert Kennungen und Beträge, die in der Lage nicht stehen. Eine falsche Form gibt eine Meldung neben dem Knopf (400) und schreibt nichts.

**Abweichungen.**
1. → Opus: **Einordnen antwortet weiter als Tabelle, nicht als YAML von `rules.yaml`.** Der Weg stand mit Tests schon da und ist beim Einfügen aus einem Chatfenster robuster (Einrückung geht verloren). Übernommen wird als gewöhnliche Textregel (`PRIORITAET` 80).
2. → Opus: **Der bestehende Abschnitt „Vorschläge über ein KI-Modell“ auf `/regeln` ist in die neue Seite umgezogen** (ein Link bleibt), samt `/api/regeln/vorschlaege/prompt` und `…/pruefen`. Zwei Wege für dasselbe wären die zweite Wahrheit. `regeln.html` verliert dabei fünf Skriptzeilen mit HTML (Ausnahme 11 → 6). `vorschlaege.prompt` ist in `FRAGE` und `lage` zerlegt.
3. → Opus: **Nur Einordnen liefert etwas zum Übernehmen.** Monat und Prognose liefern eine geprüfte Erklärung. Ein Vorschlag für eine Planzeile oder Notiz bräuchte je Art eine Form und eine Prüfung; das gehört zu 7b, wo die Schnittstelle alle Handentscheidungen ausdrückt.
4. → Opus, **Entscheidung des Haushalts:** Welche Daten in die Vorlage dürfen. Gewählt nach dem bisherigen Maß beim Einordnen: Gegenparteien nur dort, bereinigt und abwählbar; in Monat und Prognose stehen **Namen von Konten und Kategorien und Beträge**, weil die Frage ohne sie sinnlos ist. Das steht im Handbuch („verlassen den Rechner, sobald du sie in ein Modell außerhalb einfügst“). Will der Haushalt Beträge schwärzen oder runden, ist das eine Wahl mehr auf der Seite; ich habe sie nicht gebaut.
5. **Einstieg in Dateien von 6c/6d:** keiner. Der Link zur Vorlage steht in `regeln.html` und in der Navigation (`base.html`), beide nicht von 6c/6d verantwortet, aber von 6c im Arbeitsbaum ebenfalls geändert (andere Hunks).

**Tests.** `tests/test_vorlagen.py`: Begriffe sind Glossareinträge; keine IBAN, keine Nummer aus `config/` (ab sieben Ziffern), kein Rohtext eines Auszugs, keine Gegenpartei in Monat und Prognose (ein Kontoname gilt nicht); fremder Text wird verworfen; falsche Antwort → 400 und `config/` byteweise gleich; gültige Antwort → Vorschlag, Datei gleich, erst `übernehmen` ändert sie (danach zurückgestellt); Seite sagt „Die App sendet nichts“. `test_browser.py`: „Text hin, Antwort zeigen“ für Monat und Prognose, Neu erzeugen mit Monat und Frage; der Einordnen-Test überspringt sich, wo die Kopie keine offene Buchung hat (hier der Fall) — das Skript `vlUebernehmen` ist deshalb im Browser nicht gelaufen. `design_conventions.yaml`: neue Regel `antwort-ist-vorschlag`. Handbuch: Abschnitt `/vorlagen` in beiden Kopien.

**Prüfen.** Auf dem Arbeitsbaum mit den Änderungen von 6c und 6d daneben:
- Suite (Entwicklungskopie): 2629 grün, 11 rot, keine davon von 7a. Fremd: `test_umstellen*` (Verträge/`abos_custom.yaml`), `test_leck` (`forecast/szenarien.py`, ein krummer Betrag), `test_lint` (`ruff` meldet `tests/test_notizen_eintraege.py`), `test_referenz` (siehe unten). Zwei Fehlschläge waren meine und sind behoben (zwei krumme Beträge in `test_vorlagen.py`, `_prognose` zu verzweigt, jetzt in drei Funktionen).
- Musterhaushalt (`FINCTL_TESTDATEN=muster`): 2666 grün, 8 rot, alle fremd (`test_umstellen*`, derselbe krumme Betrag in `test_leck`).
- Browsertests (`-m browser -n 0`): 65 grün, 5 übersprungen (darunter Einordnen, weil die Kopie keine offene Buchung hat).
- `tests/referenz.py pruefen --nur-zahlen`: **Zahlen gleich bei `hauptbuch/`, `ableitung/` und allen Seiten bis auf `annahmen`, `konten`, `prognosebasis`** — das sind 6c und 6d, nicht 7a. Neu ist `seiten/vorlagen.txt` („ist neu“, erwartet). Die Referenz habe ich nicht neu geschrieben.
- Nicht mehr bestanden, aber fremd: `test_design` meldet `prognosebasis.html` (`strftime('%m/` , datum-iso) und zu lange Handbuchabschnitte `konten`, `ziele`, `vertraege`, `kredite`.



### 6d

**Umgesetzt am 01.11.2026 (Sonnet).** Alles an der Entwicklungskopie (`FINCTL_DATEN`); der echte Datenordner ist nicht berührt, die Referenz nicht neu geschrieben. Gemessen in einem Arbeitsbaum von `910b7f9` mit nur den Dateien von 6d, weil 6c und 7a im selben Checkout offene Änderungen haben.

**1. Woher jeder Block kommt** (gelesen in `konten.py`, `jahre.py`, `fortschreibung.py`, `verfahren.py` und den Abnahmen E.2 bis E.8b):

| Block | Monatsmodell | Jahresrechnung |
|---|---|---|
| Gehalt | Untergrenze aus den Annahmen, Steigerung zum 1. Januar | dieselbe Untergrenze, Steigerung zum 1. Januar |
| Mieteinnahmen, sonstige Einnahmen, Fixkosten, Immobilienkosten, Konsum, Steuern | Fortschreibung: Messfenster, Zwölfmonatssumme durch zwölf; Reihen mit Takt je Termin | dieselbe Messung, Summe aufs Jahr |
| Verträge | Betrag je Termin mit Steigerung, Anteil der Mitzahler | dieselben Verträge; Beiträge in Policen nominal |
| Erwartete Einnahmen | Planzeile voll, auf ihrem Konto | Planzeile voll |
| Objekte | Objektprognose je Monat, auf dem Konto der Miete | Objektprognose, Jahressumme |
| Kreditraten | Tilgungsplan | Tilgungsplan |
| Zinsen und Steuer | Stand zu Monatsbeginn mal Satz je Konto; Steuer nach Sparerpauschbetrag | Stand zu Jahresbeginn mal Mischsatz des Topfs, nach der Kaskade |
| Einmalig | fällt aus der Fortschreibung (Merkmal, gesetzte Buchung) | ebenso |
| Planzeilen der Klammern | auch die nur für die Kontoprognose | ohne diese |

**2. Die Seite.** `/prognosebasis` ist wieder eine eigene Seite (`prognosebasis.html`, Zwecksatz unter 25 Wörter) und die Überschrift heißt „Fortschreibung“. Eine Zeile je Block: Quelle, Betrag im ersten Monat des Monatsmodells, Betrag im ersten vollen Jahr der Jahresrechnung, Link auf die Seite, auf der der Haushalt sie ändert (eine gemessene Zeile führt zu den Buchungen des Messfensters). Eine Quelle, die beide mit demselben Text nennen, steht einmal; sonst stehen beide, ohne Satz dazu. Gemacht ist das in `forecast/quellen.py`: Es nimmt `household_accounts` und `jahre.rechnen`, ordnet deren Posten und rechnet nichts. Die Zuordnung der Posten steht nur dort. Der Treffer-Check bleibt auf `/annahmen`, jetzt als eigener aufklappbarer Abschnitt „Treffer: Prognose gegen Ist“ unter der Überschrift „Fortschreibung“, die auch den alten Anker `#prognosebasis` trägt und auf die neue Seite zeigt. Begründung: Er misst die Prognose am Ist und erklärt keine Quelle. Die Abwahl je Kategorie (Häkchen, Vorschau, Speichern) zog mit auf die neue Seite, aufklappbar unter „Nicht fortschreiben“; die Spalten Δ und Grund und die Ampel „dauerhaft“ entfallen. Ein Vertrag ohne zugeordnete Buchung (zählt doppelt) bleibt als bedingter Hinweis. Handbuch: neuer Abschnitt `/prognosebasis` (beide Kopien, 143 Wörter), der Absatz auf `/annahmen` und der Satz bei `/vertraege` angepasst. `CHANGELOG.md` hat einen Eintrag.

**3. Test.** `tests/test_quellen.py` (12): Die Summe der Spalte „Monatsmodell“ ist die Summe aller Posten des ersten Monats ohne Umbuchungen, die Spalte „Jahresrechnung“ die Summe der Blöcke des Jahres plus die Zinsen des Tagesgelds. Dazu, nach Etikett und Block statt nach Herkunft, die Zeilen Kreditraten, Verträge, Zinsen, Objekt, Gehalt und die Blöcke des Jahres. Jede Quelle eines Postens muss zur Zeile passen, die Seite liest dasselbe erste Jahr wie die lange Rechnung bis 2045, das Fenster der Quelle ist das Messfenster der Rechnungen, und der HTML-Text nennt eine gleiche Quelle einmal. Gegenprobe: Mit vertauschter Zuordnung von Verträgen und Kreditraten schlagen drei Tests an.

**Prüfen.** Kopie: 2613 bestanden, 56 übersprungen, rot nur `test_referenz` (siehe unten). Musterhaushalt: 2596 bestanden, 72 übersprungen, alles grün. Browsertests (`-m browser -n 0`): 60 bestanden, 4 übersprungen. `ruff` null Funde in den Dateien von 6d, `ZU_VERZWEIGT` nicht länger. `tests/referenz.py pruefen` (Ausgabe in `notizen/6d_pruefen.txt`): 4 Unterschiede, **`hauptbuch/` und `ableitung/` gleich**. Es ändern sich nur `seiten/annahmen` und `seiten/prognosebasis`, jeweils Zahlen und Text:
- `/annahmen`: Die Tabelle je Kategorie samt Summen und Skript ist weg (Zahlen und Text), dafür steht der Verweis da; der Treffer-Check bleibt mit neuer Zwischenzeile.
- `/prognosebasis`: war bisher dieselbe Seite wie `/annahmen` (Umleitung), ist jetzt die neue Seite. Die Kategorietabelle steht dort wieder, ohne Δ und Grund.

**Abweichungen.**
1. **Erstes Jahr der Jahresrechnung ist das erste volle Jahr**, nicht das Basisjahr mit seinen Restmonaten (sonst stünden dort drei Zwölftel neben einem vollen Monat). → Opus: Wenn du das Basisjahr willst, ändert sich eine Zeile in der Route.
2. **Ein Block steht in der Spalte „Monatsmodell“, sobald irgendein Monat der nächsten zwölf einen Posten von ihm hat**, der Betrag ist der des ersten Monats. Eine Schenkung im Januar steht so mit 0,00 € und ihrer Quelle da, statt zu fehlen.
3. **`prognosebasis.vergleich` bleibt unverändert, auch `grund`, `delta` und `dauerhaft`,** weil `ableitung/prognosebasis` sie trägt und `ableitung/` gleich bleiben sollte. Die Seite zeigt sie nicht. → Opus: Beim Neuschreiben der Referenz kann der Code dazu (`_grund`, `_grund_vertrag`, `GERECHNET_GRUND`, `_GRUND_JE_BLOCK`) und der Test dafür entfallen, als eigener Schritt.
4. **„Block“ und „Quelle“ stehen nicht im Glossar.** „Block“ meldete schon 6b als fehlenden Begriff; „Quelle“ ist die Spaltenüberschrift hier. → Opus: in 8c klären.
5. **Nicht in der Navigation.** Die Seite hängt an `/annahmen`; ein Navigationseintrag änderte den Kopf aller Seiten in der Referenz.
6. **`test_paritaet.py` behält seine eigene Zuordnung** (`_Zuordnung`) statt `quellen.Zuordnung`: Der Test soll die Seite unabhängig nachrechnen, nicht dieselbe Funktion zweimal aufrufen.
7. **Kopfzeile von `prognosebasis_custom.yaml`** (`prognosebasis.KOPF`, `umstellen_form.py`) und vier Kommentare nennen jetzt „Fortschreibung (/prognosebasis)“ statt „Prognosebasis (/annahmen)“. Bestehende Dateien ändern sich nicht.
8. **Fremd rot, nicht von 6d (Stand `70f74f3`, in einem Arbeitsbaum ohne meine Änderungen gemessen):** `docs/design_conventions.yaml` lässt sich nicht lesen (Zeile 820, ein Doppelpunkt im Text der Regel `ein-zwecksatz-je-seite`), dadurch bricht `test_design` ab und `test_namen` fällt; im Checkout steht eine geänderte Fassung, die liest. Dazu meldet `ruff` in `tests/test_browser.py` drei Funde (`treffer` unbenutzt und undefiniert, Zeilen um 1220 und 1262), aus dem Test zum Neuzeichnen von 6c. Mit der Fassung der Konventionen aus dem Checkout ist die Kopie bis auf diese drei Funde grün.

### 6c

**Umgesetzt am 01.11.2026 (Sonnet).** Alles an der Entwicklungskopie (`FINCTL_DATEN`); der echte Datenordner ist nicht berührt, die Referenz nicht neu geschrieben. Die Dateien von 6d (`prognosebasis`) und 7a (Vorlagen) habe ich nicht angefasst. `base.html`, `regeln.html`, `HANDBUCH.md` (beide Kopien), `CHANGELOG.md` und `docs/design_conventions.yaml` trugen beim Committen auch Änderungen der Nachbarsitzungen; ich habe nur meine Stellen committet.

**1. Entfernen nennt die Notiz.** Neu `rueckfrage(frage, knopf)` in `base.html`, `geht_mit(text)` in `_notiz.html` (Attribut `data-notiz-geht`) und der Filter `notiz_geht_mit` in `basis.py`: „Die Notiz geht mit: „Anfang …““, 60 Zeichen, an einer Wortgrenze, Zeilenumbruch als Leerzeichen, leer ohne Notiz. Umgestellt sind die Stellen, an denen ein Eintrag mit `notiz` aus einer Datei geht: Kredite, Objekte (beide Zeilenarten), Rentenquellen, Ziele, Regeln, Themenkassen und Verträge. Geprüft und bewusst ohne: Klammern (tragen keine Notiz), Kategorien (die Notiz hängt an der Oberkategorie, gelöscht wird ein Blatt), Energie (Zähler und Vorrat haben kein Notizfeld), Zinssätze (eine Zeile ohne Notiz), Ablesungen, Stände (`monatsabschluss.html` sagte es schon). Regel `entfernen-nennt-notiz` in `design_conventions.yaml`, Test `tests/test_entfernen_notiz.py` (der Satz, das Makro, jede der sieben Vorlagen nimmt den Weg über `rueckfrage`).

**2. Kontokarte.** „Untergrenze aus einem Kredit“ ist eine Auswahl (`#f-loan`) mit „kein Kredit gewählt“ vorn und den Krediten aus `loans.yaml` (Name, Kennung als Wert). `floor_from_loan` hat in `kontenregeln.py` die Art `kredit`: Eine Kennung wird geschrieben, „kein Kredit“ nimmt das Feld heraus, ein `true`/`false` aus früheren Fassungen bleibt unberührt (Speichern ohne Änderung schreibt nichts), und ein alter Aufruf mit `true` schreibt kein `true` mehr. Die Route lehnt eine unbekannte Kennung ab, außer sie steht schon an der Regel (ein inzwischen gelöschter Kredit darf stehen bleiben; die Karte bietet ihn dann als „… (kein solcher Kredit)“ an). `tests/test_kontokarte_kredit.py`, `test_notizen_eintraege.py` nachgezogen. Der bestehende Browsertest „Speichern ohne Änderung“ deckt die Karte mit Kredit ab.

**3. Umlaute im Umwandler.** Alle Meldungen an Nutzer in `umstellen.py`, `umstellen_paare.py`, `umstellen_tabelle.py` und der Ausgabe von `finctl umstellen` in `cli.py` (Fehler, Hilfetexte, Bericht): ä/ö/ü/ß. Gefunden mit einer Suche über alle Zeichenketten (ohne Docstrings), Kennungen, Schlüssel (`ueberschrieben`, `unberuehrt`), Dateinamen und Kommentare bleiben. `umstellen_form.py` habe ich nicht geändert: Es sind die Kopfzeilen der alten Dateiform, die der Umwandler erkennt, keine Meldungen. Tests nachgezogen (`match="außerhalb"`, „Schlüssel der Seite“, „würde“, „trägt“).

**4. Feld „Warum“.** Die Beschriftung heißt **Notiz** und zeigt das Datum daneben; das Feld war schon mehrzeilig. Ich habe auch den Namen im Seitenzustand umbenannt (`warum` → `notiz`, `warum_vom` → `notiz_vom`; `data-f="notiz"`). **Die Dateien des Haushalts schreibt das nicht:** Dort steht seit Schritt 5 `notiz`, der Schlüssel `warum` kam nur in der Seite vor. Alte Dateien mit `warum` liest `notizen.lesen` weiter. Mitgezogen: `umstellen_paare.py` (es rechnet den Vertragsstand ohne Notiz, jetzt ohne `notiz`), Tests.

**5. Handbuch.** Beide Kopien (gleich, `test_paket`): Themenkasse und Beteiligte (Abschnitte `/projekte`, `/salden`, `/geteilt/buchungen`), Buchung statt Zahlung/Transaktion/Umsatz, Stand statt Saldo und Kontostand, Auszug statt Kontoauszug, Sicherung statt Backup, Gegenpartei statt Empfänger, Teil statt Split, Handentscheidung, Rentenquelle, Objekt, Klammer und Planzeile, Rechenweg. Die Überschriften bleiben, wie sie sind (sie sind die Adressen der Seiten und Anker). Neu: ein Wort zur Auswahl im Abschnitt `/konten`, zur Rückfrage bei Rentenquellen und Themenkassen. Grenze 200 Wörter: `konten`, `ziele`, `kredite` lagen durch meine Zusätze darüber und sind gekürzt (in `konten` ist der Satz „Eine übersehene Delle kostet Dispozinsen“ gefallen).

**6. Hinweis auf Doppelzählung.** `szenarien.doppelt_gezaehlt` (eine Stelle, mit den Gründen im Kommentar davor), `doppelt_je_zeile` für alle eingeschalteten Klammern. „Passt“ heißt: einmalige Zeile der Art Betrag oder erwartet, dieselbe Kategorie, dasselbe Vorzeichen, Konto gleich (wenn die Zeile eins nennt), nicht zugeordnet (auch nicht an eine andere Zeile, samt der Reihe, wo eine Zeile mit Takt sie nimmt), und
- **Betrag**: Abweichung höchstens 10 % des geplanten, mindestens 5 €. Der Plan ist eine Schätzung, gerundet auf zehn oder hundert Euro; Versand, Gebühren und Steuer verschieben selten mehr als ein Zehntel; darüber ist es eher eine andere Zahlung derselben Kategorie. Die 5 € lassen eine Zeile über 20 € eine Buchung über 24 € noch treffen.
- **Datum**: im Monat der Zeile oder 14 Tage davor oder danach. Die Zeile nennt einen Monat, gezahlt wird in der Woche davor oder danach; zwei Wochen decken das, ohne in den übernächsten Monat zu greifen. Vor dem Messfenster zählt keine Messung etwas, also nichts doppelt.
- Höchstens 20 Buchungen je Zeile.
Die Schwellen sind so gesetzt, dass der Hinweis eher anschlägt als schweigt: Ein Hinweis zu viel kostet einen Blick und geht mit dem Zuordnen; einer zu wenig lässt eine Zahlung doppelt zählen. Zu sehen: an der Planzeile in der Spalte „zählt“ („N passende Buchungen nicht zugeordnet — zählt doppelt“) und im aufgeklappten Bereich „Zählt doppelt: gemessen und geplant“ mit denselben Zeilen und demselben „zuordnen“ wie die Buchungssuche (`buchungZu`); im Monatsabschluss als Punkt der Gruppe Planung (`monatsabschluss.planung_doppelt`). Eine ausgeschaltete Klammer zählt nichts doppelt und bekommt keinen Hinweis. Regel `doppelt-gezaehlt-hinweis` in `design_conventions.yaml`; `tests/test_doppelt_gezaehlt.py` (21: Grenzen der Schwellen, Konto, Zuordnung, Reihe, Monatsabschluss, Seite mit einer Buchung aus dem Hauptbuch). → Opus: Ich habe die Messfenstergrenze nur nach unten gesetzt; eine Buchung nach dem Stichtag meldet der Hinweis auch, obwohl sie erst mit dem nächsten Stichtag in die Basis fällt. Das ist der Fall „gerade eingelesen“, den der Haushalt meint. In den Daten der Kopie findet er keine Buchung (planung hat keine Textänderung dazu).

**7. Aus der Abnahme von 6a.** `neueKlammer` steht nur noch einmal. **Tippen beim Neuzeichnen, gemessen:** Browsertest `test_tippen_waehrend_des_neuzeichnens_geht_nicht_verloren` (je Reiter): Die Antwort von `/api/abos/editor` braucht im Browser 700 ms, acht Buchstaben im Abstand von 150 ms nach dem Klick auf „Person hinzufügen“. Vor der Änderung ging die ganze Eingabe verloren (der Name blieb unverändert). Abgesichert in `abos.html`: Kam während der Anfrage eine Eingabe, liest `editor()` den Entwurf neu und fragt noch einmal, bis nichts dazukam; nach dem Ersetzen steht der Fokus wieder im selben Feld an derselben Stelle (Feldname aus den `data-`-Attributen). Danach stehen alle acht Buchstaben in der Reihenfolge im Feld, der Fokus bleibt.

**Prüfen.** Entwicklungskopie: 2683 bestanden im ersten Gesamtlauf, danach die sieben eigenen Fehlschläge behoben (einzeln grün); einzig `test_referenz` bleibt rot (6d, `prognosebasis`). Musterhaushalt: 2674 bestanden. Browsertests (`-m browser -n 0`): 65 bestanden, 5 übersprungen. `ruff` null Funde. `tests/referenz.py pruefen --nur-zahlen`: Unterschiede in `annahmen`, `prognosebasis` und `vorlagen` (6d und 7a, nicht von mir) und **eine Zeile in `konten`**: die „2026“ im Namen eines Kredits, der jetzt in der Auswahl der Kontokarte steht. Sonst nichts; `hauptbuch/` und `ableitung/` gleich. Die Textebene liegt in `notizen/6c_text_unterschiede.txt` der Kopie (alle Seiten tragen die geänderte Navigation von 7a; an `planung` und `monatsabschluss` ändert mein Hinweis in den Daten der Kopie nichts).

**Fremde Fehlschläge.** Im ersten Gesamtlauf `test_leck` und sechs `test_umstellen*`-Tests: von mir (Kommentar mit Betrag, Notizschlüssel beim Zusammenlegen), behoben. Nicht von mir: `test_referenz` (siehe oben).

**6c, 6d und 7a abgenommen am 01.11.2026 (Opus), Referenz neu geschrieben.** Nach den drei Commits waren zwei Stellen zwischen den Sitzungen zerbrochen. Die Regel `antwort-ist-vorschlag` stand mitten in `ein-zwecksatz-je-seite`, sodass die Datei kein gültiges YAML war. Im Browsertest stand der Kopf des Notiztests für den Monatsabschluss getrennt von seinem Rumpf. Beides ist in `8deb5f3` behoben. `pruefen` auf einem sauberen Arbeitsbaum von `8deb5f3` ergab 40 Unterschiede (Ausgabe in `notizen/6c_6d_7a_referenz_vor_neuschreiben.txt`). `hauptbuch/` und `ableitung/` sind gleich. Fast jede Textseite trägt den neuen Eintrag „Vorlagen“ in der Navigation, und `/vorlagen` ist neu. Auf der Zahlenebene ändern sich nur `annahmen` und `prognosebasis` (6d) und `konten`: Die Kontokarte bietet die Kredite an, und einer trägt eine Jahreszahl im Namen. Danach meldet `pruefen` Gleich. Beide Suiten sind grün, die Browsertests auch (65 bestanden). Zu den Abweichungen:
1. **7a, Einordnen als Tabelle statt YAML; Vorschläge von `/regeln` auf `/vorlagen` umgezogen; nur Einordnen übernimmt:** angenommen. Planzeilen, Kredite und Notizen kommen mit 7b.
2. **7a, Daten in den Vorlagen:** Namen von Konten und Kategorien und Beträge stehen darin. Der Haushalt ist informiert; ein Schalter zum Runden kommt, wenn er ihn will.
3. **6d, erstes volles Jahr; Block ohne Posten im ersten Monat mit 0,00; nicht in der Navigation:** angenommen. Die nicht mehr gezeigten Felder `grund`, `delta` und `dauerhaft` in `prognosebasis.vergleich` fallen in 8c samt Referenz.
4. **6d, „Block“ und „Quelle“ im Glossar:** in 8c, zusammen mit der Liste aus 6b.
5. **6c:** wie berichtet angenommen.

### 7b

**Umgesetzt am 01.11.2026 (Sonnet).** Alles an der Entwicklungskopie (`FINCTL_DATEN`). `CLAUDE.md` unverändert, wie vorgegeben.

**Aufbau.**
- `finctl mcp` (und im Paket das Programm mit dem Argument `mcp`, `starter.main`) spricht MCP über stdio: `finctl/mcp/protokoll.py` (JSON-RPC, `initialize`, `ping`, `tools/list`, `tools/call`, `resources/list`, `resources/read`), `finctl/mcp/werkzeuge.py`. Kein Port, keine neue Abhängigkeit (ein Test liest die Importe und prüft, dass das Paket nur die Standardbibliothek und `finctl` benutzt; `collect_submodules("finctl")` nimmt es in den Bau mit). Während eines Aufrufs geht `stdout` nach `stderr`, damit nichts den Strom bricht.
- Lesen, 12 Werkzeuge, alle über Funktionen der Seiten: `konten`, `jahresrechnung`, `annahmen` (die Lage-Bausteine aus 7a), `fortschreibung` (`quellen.bauen`), `buchungen_suchen` (die Suche der Seite, höchstens 200 Zeilen, bereinigter Text, **ohne** den Hash der Buchung), `kategorien`, `vertraege`, `klammern`, `kredite`, `objekte` (ohne Anschrift), `ziele` (die Karten der Seite), `offene_punkte`. Das Glossar ist die Ressource `finctl://glossar`. Jede Antwort geht durch `_ohne_nummern`.
- `vorschlagen` (`art`, `felder`, optional `warum`): `finctl/web/vorschlaege.py` prüft und legt `data/vorschlaege/<Zeitstempel>-<Zufall>.json` ab (neuer Pfad `VORSCHLAEGE_DIR` in `pfade.py`; die Tests kopieren den Ordner nicht mit). Arten: `regel`, `planzeile`, `kredit`, `notiz`. Unbekannte Felder werden abgelehnt.
- Die Prüfung ist die der Routen. Dafür habe ich vier Stücke aus Routen herausgelöst, ohne ihr Verhalten zu ändern: `regel_pruefen` (Regeln, von Vorschau und Speichern mitbenutzt), `kredite.neuer_kredit` (von `anlegen` mitbenutzt), `ziele_kontext` und `fortschreibung_seite` (Seiten, aus denen die Werkzeuge lesen) und `neue_planzeile` (Hülle um `_planzeile`; die Route ruft `_planzeile` weiter selbst auf). Dazu `vorlagen.offene_posten` aus `_monat`.
- Seite `/vorschlaege` (Gruppe Stammdaten, `APP_SEITEN`): je Vorschlag das „warum“, Feld/Wert dessen, was sich ändern würde, und Hinweise (Regel: wie viele Buchungen sie träfe und wie viele die Kategorie wechseln; Planzeile: neue oder ausgeschaltete Klammer). „Übernehmen“ schickt **Route und Körper, die der Server aus seiner Prüfung ableitet** (nicht aus der Datei), an die bestehende Route und löscht den Vorschlag erst, wenn sie angenommen hat. Ein Vorschlag, den die Prüfung heute nicht mehr annimmt, nennt die Meldung und hat keinen Knopf. Die Navigation zeigt die Zahl offener Vorschläge.
- Handbuch (beide Kopien, `### /vorschlaege`, unter 200 Wörter, ohne Produktnamen, lokales Modell als Standard), `CHANGELOG.md`, `docs/design_conventions.yaml` (`vorschlag-wird-in-der-app-bestaetigt`, mit Prüfung), Glossar.

**Abweichungen.**
1. → Opus: **Neuer Begriff „Vorschlag“ in `CONTEXT.md`** (beide Kopien). Er stand im Plan nicht, aber Seite, Navigation und ADR benutzen das Wort, und `begriffe-des-glossars` verlangt, dass das Glossar es führt. Bitte lesen und ändern, wenn „Auftrag“ in _Avoid_ nicht passt.
2. → Opus: **Notiz nur an einem Ziel oder einem Konto.** Das sind die beiden Einträge, deren Route eine Notiz allein nimmt (`/api/ziel` mit `id` und `notiz`, `/api/konto/{id}` mit `note`). Die Routen für Kredit, Objekt, Vertrag, Rentenquelle, Regel und Kategorie nehmen die Notiz nur mit dem ganzen Eintrag. Der Vorschlag `notiz` hat deshalb eine Hülle: `ort` (`ziel` oder `konto`), `id`, `notiz`. Eine Notiz, die schon so dasteht, ist kein Vorschlag.
3. → Opus: **Feld `warum` am Vorschlag.** Nicht im Plan. Ohne es sieht der Haushalt nur Felder und weiß nicht, warum das Modell sie vorschlägt. Höchstens 500 Zeichen, steht nie in `config/`.
4. → Opus, **Entscheidung des Haushalts: Notizen.** Keine Antwort enthält eine Notiz (ein Test hält das), weil sie „alles Persönliche“ tragen. Ein Modell kann also nicht lesen, warum ein Eintrag so ist. Soll es, ist das eine Wahl mehr (nur bei lokalem Modell?). Ebenso: Beträge und Namen von Konten, Verträgen und Kategorien stehen in den Antworten (wie in 7a); Anschriften und Nummern nicht.
5. → Opus: **Eine Planzeile in einer Klammer, die es nicht gibt, legt die Klammer an**, wie die Route es tut (als „Plan“, nie als Verpflichtung). Die Seite sagt es als Hinweis. Verkauf und Teilzeit sind keine Vorschlagsart; sie haben eigene Felder.
6. **`Finance OS mcp` im Paket nicht gebaut.** Ich habe den PyInstaller-Bau nicht gelaufen; getestet ist `starter.main()` mit dem Argument `mcp` über eine echte Pipe. Ob die Mac-App ohne Fenster (`console=False`) stdin/stdout an einen startenden Prozess gibt, ist beim nächsten Bau mit `werkzeuge/paket/rauchtest.py` zu prüfen.
7. **Nicht gebaut:** ein Werkzeug, das offene Vorschläge listet. Das Modell sieht, was es abgelegt hat, nur in der Antwort des Aufrufs.

**Lücken (ADR 0002, „vollständig genug“): Handentscheidungen, die die Schnittstelle noch nicht ausdrückt.**
- *Zuordnen:* eine bestehende Regel ändern oder entfernen, die Grundschicht ein- und ausschalten, die Kategorie einer Buchung festlegen oder sie in Teile zerlegen (`overrides.yaml`), eine Buchung einer einmaligen Planzeile zuordnen, Kategorien anlegen oder umbenennen.
- *Planung:* eine Zeile ersetzen oder löschen, eine Klammer ein- und ausschalten oder zur Verpflichtung machen, Verkauf und Teilzeit.
- *Verträge und Dinge:* Verträge anlegen, ändern, kündigen, Mitzahler; Objekte anlegen und ihre Angaben und Objektprognose; Ziele anlegen oder ändern; Rentenquellen; Zähler und Vorräte; Themenkassen und ihre Zuordnung; Fristen.
- *Kredit:* nur der Ratenkredit mit einem Segment. Immobiliendarlehen, Anschlussfinanzierung (`/api/kredit-anschluss`) und Vorlage fehlen.
- *Stände und Annahmen:* getippte Stände (Monatsabschluss), Annahmen, Kontenregeln (Untergrenze, Deckel, Rolle), Zinssätze, Reihen (Takt, einmalig, Schreibweisen zusammenführen), Module.
- *Notizen:* an allen Einträgen außer Ziel und Konto.
- *Lesen, das fehlt:* Notizen (Abweichung 4), Reihen und ihr Takt, Rentenquellen, Energie, Themenkassen, Steuer, Stände und Verlauf, der Rechenweg einer Zahl, die Wirkung auf die Ziele.

**Tests.** `tests/test_mcp.py` (45): Protokoll über eine echte Pipe (Handshake, Liste, Aufruf, Fehler, Benachrichtigung, kaputte Zeile, Glossar, Paketstart mit `mcp`); jedes lesende Werkzeug ohne IBAN, ohne Ziffernfolge ab neun Stellen und ohne Nummer aus `config/` (zur Laufzeit gelesen), Suche höchstens 200 und ohne Hash oder Nummer aus einem Auszug, keine Notiz in einer Antwort; `vorschlagen` lässt `config/` byteweise gleich und legt genau eine Datei ab; ein ungültiger Vorschlag kommt mit **derselben Meldung wie die Route** zurück und legt nichts ab; Übernehmen (wie die Seite es schickt) ergibt **byteweise dieselben Dateien** wie derselbe Eintrag über die Route, je Art; Verwerfen lässt nichts zurück; Route und Körper stammen nicht aus der Datei; die Kennung kommt nicht aus dem Ordner heraus; die Navigation zeigt die Zahl. `test_browser.py`: Übernehmen und Verwerfen auf `/vorschlaege` im echten Browser. `test_paket.py`: Rad und Bau tragen `finctl/mcp`, keine neue Bibliothek.

**Prüfen.** 
- Suite (Entwicklungskopie): 2742 grün, 1 rot: `test_referenz` (nur die Zeile „Vorschläge“ in der Navigation von zehn Seiten und die neue Seite `vorschlaege.txt`; erwartet, die Referenz schreibt Opus neu).
- Musterhaushalt (`FINCTL_TESTDATEN=muster`): 2725 grün, 75 übersprungen, keine rote.
- Browsertests (`-m browser -n 0`): 66 grün, 5 übersprungen, davon der Vorschlags-Test grün; nach der letzten Änderung der Vorlage erneut der Vorschlags- und Vorlagenteil: 5 grün.
- `ruff`: null Funde.
- `tests/referenz.py pruefen --nur-zahlen`: **Zahlen gleich**; neu ist nur `seiten/vorschlaege.txt` („ist neu“). Die Referenz habe ich nicht neu geschrieben.


**7b abgenommen am 01.11.2026 (Opus), Referenz neu geschrieben.** Auf der Zahlenebene ist nur `seiten/vorschlaege` neu. Im Text kommt auf zehn Seiten der Eintrag „Vorschläge“ in der Navigation hinzu (Ausgabe in `notizen/7b_referenz_vor_neuschreiben.txt`). Danach meldet `pruefen` Gleich. Zu den Abweichungen:
1. **Begriff „Vorschlag“:** angenommen, umformuliert, damit er nicht mehr auf sich selbst verweist (`4cf5a7c`). Die Datenregel in `CLAUDE.md` folgt ADR 0002 im selben Commit.
2. **Notiz nur an Ziel und Konto; Feld `warum`; Planzeile legt die Klammer an:** angenommen.
3. **Keine Notiz in Antworten:** bleibt so. Notizen tragen das Persönliche; ob ein lokales Modell sie lesen darf, entscheidet der Haushalt später.
4. **`Finance OS mcp` aus dem Paket:** wird beim nächsten Bau der App mit geprüft.
5. **Lücken:** Sie sind die Liste für 8c1 und für spätere Arten von Vorschlägen.

**Glossar (Opus, 01.11.2026):** Neu sind Saldo, Teilung, Mindestbestand, Block und Quelle (aus 6b und 6d). Nicht aufgenommen: Rücklagen, Review, Ledger und Rendite als Spalte eines Objekts. Sie sollen auf der Seite einem vorhandenen Begriff weichen, statt das Glossar zu dehnen. „Basis“ eines Ziels und der Kredittabelle widerspricht „Basis“ im Betrieb; beides geht in die letzte Durchsicht.

### 8c2

**Umgesetzt am 01.11.2026 (Sonnet).** Alles an der Entwicklungskopie (`FINCTL_DATEN`) und am Musterhaushalt; der echte Ordner ist nicht berührt, die Referenz nicht neu geschrieben. Die Ausgabe von `tests/referenz.py pruefen` liegt in `notizen/8c2_pruefen.txt` der Kopie.

**1. „Gemeinschaftskonto“ ist ein Eintrag in `forecast.yaml`.** Es gab weder eine Rolle für Kategorien noch eine für Konten, die passte: Es ist eine *Kategorie*, die neben dem Cashflow ohne Objekt einzeln mitläuft, und das Soll stand schon in `cashflow_ohne_objekt`. Darum jetzt dort `daneben: {kategorie, label, soll_cents}` (`forecast/ohne_objekt.py`, `Monat.daneben_cents`, `kennzahl()["daneben"]`). Karte (`konten.html`) und Linie (`_diagramm_ohne_objekt`) hängen an `daneben` und tragen dessen `label`. **Ohne den Eintrag gibt es weder Karte noch Linie.** Die Konstante `GEMEINSCHAFTSKONTO` und der Schlüssel `gemeinschaftskonto_soll_cents` sind weg. Kopie (`label: Gemeinschaftskonto`, Soll 400,00) und Musterhaushalt (Soll 300,00) tragen den Eintrag; ihre Zahlen auf `/konten` sind gleich. Die Kategorie `familie/gemeinschaftskonto` bleibt in `vorgaben/taxonomy.yaml` als gewöhnliche Kategorie (Wortschatz, nicht Code). Tests: `test_ohne_objekt.py` (gemessen, vorausgerechnet, `einstellungen` ohne Eintrag), `test_web.py` (Karte trägt das `label` aus der Konfiguration; ohne `daneben` keine Karte).
→ Opus: **Im echten Ordner** `forecast.yaml`, `cashflow_ohne_objekt`: `gemeinschaftskonto_soll_cents: <Betrag>` ersetzen durch
`daneben: {kategorie: familie/gemeinschaftskonto, label: Gemeinschaftskonto, soll_cents: <derselbe Betrag>}`; den Notizschlüssel `cashflow_ohne_objekt.gemeinschaftskonto_soll_cents` in `cashflow_ohne_objekt.daneben` umbenennen. Bis dahin fehlen Karte und Linie auf `/konten`. Eine Eingabemaske für `daneben` gibt es nicht (der Eintrag steht nur in der Datei).

**2. Das Ziel der Fortschrittszeile trägt `im_monatsabschluss: true` in `goals.yaml`.** `ziele.monatsabschluss_ziel(goals)` nimmt das erste Ziel mit dem Merkmal; die Zeile nennt es mit seinem Namen aus der Datei (`{name} heute … %, hochgerechnet …`). **Ohne Merkmal gibt es keine Zeile.** Begründung: Das erste Ziel der Liste wäre eine stille Wahl; der Monatsabschluss zeigte als Fortschritt, was der Haushalt so nie gewählt hat. Eine fehlende Zeile sagt ehrlicher, dass noch keines gewählt ist, und folgt dem Muster der Zeile („keine Zeile, wo es das Ziel nicht gibt“). Dieselbe Wahl gilt für `finctl jahre` (`cli.py` suchte ebenfalls `barista-fire`; ohne Merkmal rechnet der Befehl mit Ziel 0, wie bisher ohne dieses Ziel). Kopie und Musterhaushalt tragen das Merkmal am Ziel `barista-fire`. Die Ausnahme `routen/auswertung.py: 2` in `einzelfaelle` ist gestrichen (`ausnahmen: {}`, `offen` weg). Tests: `test_ziele_seite.py` liest das Ziel zur Laufzeit statt `barista-fire` und `Barista FIRE` zu nennen, dazu `monatsabschluss_ziel` und „ohne Merkmal keine Zeile“.
→ Opus: **Im echten Ordner** `goals.yaml`: am Ziel `barista-fire` die Zeile `im_monatsabschluss: true` ergänzen. Ohne sie fehlt die Zeile im Monatsabschluss, und `finctl jahre` rechnet mit Ziel 0. Das Merkmal überlebt das Speichern auf `/ziele` (`_ziel_aendern` ändert nur die bekannten Felder); ein Häkchen dafür gibt es nicht. → Opus: Maske für beide Einträge (Häkchen am Ziel, Karte neben dem Cashflow) in 8c1 oder als eigener Schritt; ich habe `ziele.html` nicht angefasst, weil 8c1 in Vorlagen und Routen arbeitet.
**Abweichung vom Text:** Die Zeile heißt jetzt wie das Ziel in der Datei. In der Kopie steht dort „Barista Fire“, bisher fest „Barista FIRE“; auf `/monatsabschluss` und `/start` ändert sich diese eine Textzeile, die Zahlen nicht.

**3. Tote Felder.** `grund`, `delta` und `dauerhaft` sind aus `prognosebasis.vergleich` (Zeilen und Objektzeilen) entfernt, dazu `_grund`, `_grund_vertrag`, `GERECHNET_GRUND`, `_GRUND_JE_BLOCK`, `RUNDUNG_CENTS` und das, was nur sie brauchten (`abo_kategorien`, `erwartet`, `ohne_zuordnung`, `fcfg` im Kontext, zwei Importe). Gelöscht: `test_the_page_names_a_reason_for_every_difference`. Behalten: `test_the_two_columns_differ_only_by_rounding_or_by_a_kontenregel`, die das Delta jetzt aus `konten` und `jahr` selbst rechnet und `exclude_from_recurring` aus der Konfiguration liest (`RUNDUNG_CENTS` steht jetzt im Test). Der Hinweis „zählt doppelt“ auf `/prognosebasis` kommt aus `quellen.vertraege_ohne_zuordnung` und ist unberührt. **`ableitung/prognosebasis` ändert sich in der Referenz**, wie gewollt: Ich habe die alte Datei geladen, die drei Felder je Zeile (71 Zeilen) entfernt und mit der neuen verglichen: gleich.

**4. Abschlussprobe.** **`BEKANNT` in `tests/test_umbenennung.py` ist schon leer** (`{}`), es gibt nichts zu kürzen. Stattdessen habe ich die Probe verschärft: Sie benennt jetzt auch jedes **Ziel** um (neue Sorte `ziel`; ausgenommen der Notgroschen, `PUFFER_ZIEL`, den die Prognose beim Namen kennt) und sucht dessen Kennung im Code. Beides grün auf der Kopie und dem Musterhaushalt (`test_umbenennen_aendert_keine_zahl`, `test_keine_kennung_im_code`). Eine Suche über alle Kennungen und Werte aus `config/` der Kopie (Ziele, Klammern, Verträge, Kategorien, Regeln …) als Zeichenkette in `finctl/` (ohne `ingest/`) fand außer den behobenen:
- `observed_balance_2026_01_cents` in `realestate/loan.py:37`: ein Rückfallschlüssel mit Datum, den ein Kredit der Kopie noch trägt (`loans.yaml` Zeile 12). **Nicht ersetzt:** Ohne Umbenennung der Datei fiele der Kredit still auf `principal_cents` zurück und rechnete falsch. → Opus: im echten Ordner und in der Kopie den Schlüssel in `opening_balance_cents` umbenennen (gleicher Wert; prüfen, ob `opening_balance_as_of` dazu soll), dann entfällt die Zeile im Code.
- `PUFFER_ZIEL = "tagesgeld-puffer"` (`forecast/notgroschen.py`, `jahre.py`): Das Produkt kennt den Notgroschen; `vorgaben/goals.yaml` liefert ihn. Bleibt, die Probe nimmt ihn aus.
- Kategorien in `abgleich.py`, `jahre.py`, `konten.py`, `zinsen.py`, `kpi.py`, `categorize.py` u. a. (`einkommen/gehalt`, `einkommen/zinsen`, `immobilie/mieteinnahme`, `kredit/zinsen`, `kredit/tilgung`, `steuern/kapitalertragsteuer`, `transfer/eigenkonto`, `anlage_v/zinsen`, `privat/nicht-abzugsfaehig`, Präfixe `transfer/`, `investment/`): Sie stehen in der mitgelieferten Taxonomie (`vorgaben/taxonomy.yaml`) und sind das, was die Prognose von jedem Haushalt erwartet: Gehalt, Miete, Zinsen, Kredit. Das ist ein Vertrag zwischen Produkt und Taxonomie, kein Einzelfall des Haushalts. Ein Haushalt, der sie umbenennt, bricht die Prognose; ein Test, der jede dieser Kennungen in der Vorgabe sucht, fehlt. → Opus: ob gewünscht.
- Keine Fundstellen sind `einkommen/gehalt-nebentaetig` (Kommentar, `buchungen.py:341`), `eltern` (SQL-Alias, `buchungen.py`), Datumsbeispiele in Platzhaltern (Formatbeispiele nach der Regel `datum-als-text`) und die Rollenwörter (`servicing` usw. sind Wortschatz des Produkts).
- „Barista FIRE“ steht noch in Docstrings und Kommentaren (`jahre.py`, `ziele.py`, `szenarien.py`, `routen/ziele.py`, `cli.py` Befehlsname `jahre`) und in Tests (`test_jahre.py`, `test_erstlauf.py`). Es ist der Name eines allgemeinen Konzepts, keine Kennung und kein Name aus dem Haushalt; `test_namen.py` bleibt bei null. Nicht angefasst.

**Prüfen.**
- Kopie: 2790 grün, 62 übersprungen, 10 rot (siehe unten). Musterhaushalt: 2804 grün, 78 übersprungen, 8 rot (unten). Browsertests (`-m browser -n 0`): 68 grün, 4 übersprungen. `ruff` in den Dateien von 8c2: null Funde.
- `tests/referenz.py pruefen` (Ausgabe in `notizen/8c2_pruefen.txt`): **`hauptbuch/` gleich**, in `ableitung/` ändert sich nur `prognosebasis` (die drei Felder, siehe oben). `seiten/konten` ist gleich (Karte und Linie wie vorher). Von mir stammt nur eine Zeile: `/monatsabschluss` und `/start`, „Barista FIRE heute …“ → „Barista Fire heute …“, Zahlen gleich (Abweichung 2).
- **Fremd rot oder verschoben (nicht von 8c2, nicht behoben):** (a) 7c, nicht abgeschlossen: `test_design` (`_hinaus.html`, `vorlagen.html` zu viel Text), `test_lint` (`ruff` in `anbindung.py` und `test_anbindung.py`), `test_plattform` (`anbindung.py:247` ohne `encoding=`), `test_web::test_nothing_in_the_runtime_reaches_the_network_or_a_model` (`import urllib` in `anbindung.py`), zwei Fälle in `test_vorlagen`; in der Referenz die Seiten `vorlagen` und `vorlagen__anbindung`. (b) 8c1, nicht abgeschlossen: `test_web::test_the_setup_asks_who_plans` und `test_wiederherstellen::test_the_setup_lists_the_backups` (`konten_maske` in `einrichtung.html` ist undefiniert), auf dem Musterhaushalt `test_lint` (`konten.py::aendern`, `kategorien.py::api_category` zu verzweigt); in der Referenz die „entfernen“-Zeilen auf `/monatsabschluss`, `/start`, `/bestaende`, `/kategorien`, `/kontenregister`, `/einrichtung`. (c) Steuersatz-Arbeit (`assumptions`/`annahmen.py`): in der Referenz 26,375 auf `/annahmen` und `/hochrechnung` (Zahlen und Text) weg; auf dem Musterhaushalt `test_leck::test_amounts_in_prose_are_round` (ein gerundeter Satz in `annahmen.py` und `CHANGELOG.md`) und `test_umstellen_paare::test_settings_the_twelve_values…` (`basiszins_pa`, `steuersatz_kapital` fehlen in der Liste des Tests). `test_referenz` ist deshalb rot, aus diesen Gründen und wegen `prognosebasis`.

**Git.** Die Dateien `CHANGELOG.md`, `docs/design_conventions.yaml`, `finctl/web/routen/auswertung.py`, `finctl/web/routen/konten.py` und `tests/test_web.py` tragen im Arbeitsbaum auch Änderungen anderer Sitzungen. Ich habe nur meine Teile (Hunks) in den Commit genommen.

### 8c1

**Umgesetzt am 01.11.2026 (Sonnet).** Alles an der Entwicklungskopie (`FINCTL_DATEN`); der echte Datenordner ist nicht berührt, die Referenz nicht neu geschrieben. `finctl/forecast/`, `prognosebasis`, `goals.yaml`, `/ziele`, `/vorlagen` und die Karte des Gemeinschaftskontos auf `/konten` habe ich nicht angefasst.

**1. Bestandsaufnahme.** Geprüft an der Kopie und am Musterhaushalt (`tests/musterhaushalt/config/`), je Schlüssel gegen den Code (Leser und Schreiber) und gegen die Routen. Zusätzlich auf einem leeren Datenordner nach `finctl init` gemessen, was ein neuer Haushalt tun kann (Konto anlegen, Stand eintragen): Dort scheiterte das Eintragen eines Standes für ein Depot mit „unbekannte Position“. „Seite“ heißt: anlegen, ändern und entfernen gehen auf der genannten Seite. „tot“: Der Code liest den Schlüssel nirgends.

| Datei | Schlüssel | Seite oder Texteditor |
|---|---|---|
| `accounts.yaml` | `id`, `display_name`, `institution`, `account_type`, `ingest_mode`, `parser_profile`, `statement_folder`, `dispo_threshold_cents` | **anlegen:** `/einrichtung`. **ändern: neu in 8c1,** `/einrichtung` → Öffnen |
| | `closed_on` (`active`) | **neu:** „Geschlossen am“ (leer öffnet). `active: false` aus alten Dateien bleibt, wie es ist |
| | `notiz` | **neu:** im selben Bereich |
| | `iban`, `account_no`, `currency` | nur Texteditor; die App liest sie nirgends (Anzeige ohne Wirkung) |
| | Konto löschen | nur Texteditor, bewusst: schließen genügt, Buchungen und Verweise bleiben |
| `accounts.example.yaml` | – | Beispiel in der Kopie, vom Code nicht gelesen |
| `balances.yaml` | `balances` (Stand, Stichtag, `gewinn_cents`, Rückkauf-Felder, `notiz`) | `/monatsabschluss` → Stände. **Position anlegen und entfernen: neu in 8c1** |
| | `kind`, `account_id`, `name` | **neu:** beim Anlegen (Konto, Art) |
| | `liquidity`, `realised_cents` | nur Texteditor (Beschreibung; nur der Stand zählt) |
| | `obligations` | Streichen: `/monatsabschluss`; anlegen: `/planung` (Verpflichtung) |
| | `verlauf` | von der Seite geschrieben (Monatsabschluss), nicht eingegeben |
| `assumptions.yaml` | `inflation_pa`, `kapital.rendite_*`, `kapital.sparerpauschbetrag_cents`, `kostenschwelle_pa`, `erwerbseinkommen.gehalt_steigerung_pa`, `…netto_floor_monatlich_cents`, `teilzeit_*`, `ruhestand.*` | `/annahmen` |
| | `kapital.vorabpauschale.steuersatz`, `….basiszins_pa` | **neu in 8c1:** `/annahmen` |
| | `kapital.vorabpauschale.teilfreistellung`, `erwerbseinkommen.netto_median_monatlich_cents`, `ziel.*` | tot (die Prognose rechnet ohne Teilfreistellung; der Median wird nur gemessen) |
| | `immobilien.objekte` | nur Datei, nur für `finctl jahre --szenario` |
| `assumptions.optimistisch.yaml`, `.pessimistisch.yaml` | alle | nur Texteditor und Befehlszeile (`finctl jahre --szenario`); keine Seite liest sie |
| `lebensplan.yaml` | `person.birth_date`, `person.krankenversicherung`, `schwellen.grv_ab_alter` | `/einrichtung` |
| | alle übrigen (`schwellen.*`, `bali`, `erwerbseinkommen`, `kapital`, `birth_year*`) | tot |
| `forecast.yaml` | `account_roles.*`, `account_budgets` | `/konten` (Kontokarte) |
| | `exclude_from_recurring`, `overrides`, `enden` | nur Texteditor; die Seiten schreiben sie nicht (Abwahl je Kategorie: `/prognosebasis`, andere Datei). Gehört zu `forecast/` und 8c2 |
| | `cashflow_ohne_objekt` | 8c2 |
| | `min_occurrences`, `variable_kosten`, `window_months`, `window_months_fixkosten` | tot |
| `goals.yaml` | `ziele`, `reihenfolge` | `/ziele` (8c2) |
| `groups.yaml` | `gruppen` | nur Texteditor und `finctl gruppen`; keine Seite zeigt `group_id` |
| `loans.yaml` | Ratenkredit (neun Felder) | `/kredite`: anlegen, entfernen |
| | `anschluss_eingegeben`, `vorlage` | `/kredite` |
| | Immobiliendarlehen (`segments`, `zinsbindung_*`, `followup_*`, `beobachtete_raten` …) | nur Texteditor, **große Lücke** (siehe unten) |
| | `notiz` | `/kredite` (am ganzen Eintrag) |
| `overrides.yaml` | `overrides` | `/transactions`, `/split`, `/regeln` (Umhängen) |
| `properties.yaml` | `id`, `name`, `status` | `/immobilien`: anlegen, entfernen |
| | Kaufpreis, Nebenkosten, Eigenkapital, Grundanteil, AfA, Datum, Verkauf, `prognose` | `/immobilie/<id>` |
| | `address`, `afa_base_cents`, `afa_extra_annual_cents` | nur Texteditor (`address` zeigt die Seite an) |
| | `living_space_sqm`, `contract_on`, `handover_on`, `ownership_*`, `erbbauzins_*`, `lease_*`, `tenure` u. a. | tot |
| `renten.yaml` | `name`, `art`, `cents`, `stand`, `ab`, `kosten_pa`, `notiz` | `/renten` (Betrag und Stand auch `/monatsabschluss`) |
| | `kaufkraft`, `konto`, `beitrag`, `pruefwert`, `stand_cents`, `stand_wert`, `beitrag_ag_cents` | nur Texteditor, bewusst: Die Seite legt nominal an; die Prüfwerte einer Police sind Sache der Datei |
| `rules.yaml` | `rules` (Name, `match`, `set`, `priority`, `notiz`) | `/regeln`; Grundschicht: `/regeln` |
| | `split` (Regel mit Teilung), `provenance` | nur Texteditor (Regel wird angezeigt, nicht angelegt) |
| `taxonomy.yaml` | Name einer Subkategorie | `/kategorien`: anlegen, umbenennen, stilllegen, löschen |
| | **neu in 8c1:** Oberkategorie anlegen; `fix`, `einmalig` an der Subkategorie | `/kategorien` |
| | `kind` einer bestehenden Oberkategorie, Name einer Oberkategorie, `tax` je Subkategorie, der `tax`-Baum (Steuerzuordnung) | nur Texteditor |
| | `notiz` an der Oberkategorie | nur Texteditor (die Seite zeigt sie) |
| `taxonomy_migrations.yaml` | `remap` | von `/kategorien` → Stilllegen geschrieben; `retire` tot |
| `szenarien.yaml` | Klammern, Planzeilen, `aktiv`, `pflicht` | `/planung` |
| `geteilt_custom.yaml` | `personen`, `projekte`, `buchungen` | `/projekte`, `/salden`, `/geteilt/buchungen` |
| `strom.yaml`, `energie.yaml` | Zeiträume, Ablesungen, Zähler, Vorräte | `/energie` |
| `reihen_custom.yaml` | `reihen` (Takt, einmalig, zusammenführen) | `/reihen` |
| `zinssaetze_custom.yaml` | `zinssaetze` | `/annahmen` |
| `abos.yaml`, `versicherungen.yaml` | alle Felder eines Vertrags, Mitzahler, Zeiträume | `/vertraege` |
| `module_custom.yaml` | Auswahl der Module | `/einrichtung` |
| `csv_profile_custom.yaml` | eigene Profile | `/einrichtung` (anlegen; ändern und entfernen nur Texteditor) |
| `prognosebasis_custom.yaml` | Abwahl je Kategorie | `/prognosebasis` (6d) |
| `adjustments.yaml` | `corrections` | nur Texteditor; Korrektur eines Auszugskopfs, kommt im ersten Jahr nicht vor |
| `backup.yaml` (technisch) | `directory`, `keep` | `/einrichtung` |
| `server.yaml` (technisch) | `host`, `port`, `passwort_hash`, `geheimnis` | Befehlszeile (`finctl passwort`, `finctl serve --host`); keine Seite |
| `verbotene_namen.yaml` | – | nur für Entwickler (`tests/`), die App liest sie nicht |


**2. Lücken geschlossen** (je mit Handbuch in beiden Kopien, Abschnitte unter 200 Wörtern, `CHANGELOG.md` und Test; jede Eingabe schreibt über `finctl/dateien.py`):
- **Stände: Position anlegen und entfernen** (`/monatsabschluss`, `bestaende.position_anlegen`, `position_entfernen`, Routen `/api/bestand-neu`, `/api/bestand-entfernen`). Der größte Befund: Auf einem leeren Datenordner ließ sich ein Konto für ein Depot anlegen, sein Stand aber nicht eintragen (`/api/bestand` änderte nur, was die Datei schon trug). Die neue Position hängt an einem offenen Konto ohne Auszug und beginnt mit Art, Stand, Stichtag und Notiz; der Stand zählt sofort (Spiegelung wie bei `finctl init`) und beginnt den Verlauf. Entfernen nimmt Notiz und Verlauf mit (Rückfrage nennt die Notiz) und lässt das Konto stehen; eine Position, die ein Auszug belegt, lehnt es ab. Test: `tests/test_positionen_anlegen.py` (19; Anlegen, jede Ablehnung ändert nichts, Topf und Verlauf, Seite, Entfernen ohne Spur).
- **Konten: bearbeiten und schließen** (`/einrichtung` → Öffnen, `konten.aendern`, `/api/konto-stammdaten/<id>`). Die Einrichtung legte ein Konto an und ließ es danach in Ruhe. Jetzt: Anzeigename, Institut, Art, Einlesen, Parserprofil, Warnschwelle, Auszugsordner, Notiz, „Geschlossen am“. Die Kennung bleibt; ein anderer Auszugsordner verschiebt keine Dateien. **Speichern ohne Änderung schreibt nichts**, auch nicht bei `active: false` in einer alten Datei. `konten.pruefen` prüft die Kennung nur noch bei neuen Konten (`neu=True`), damit ein altes Konto mit einer früher erlaubten Kennung bearbeitbar bleibt. Test: Abschnitt „bearbeiten“ in `tests/test_konten_anlegen.py`.
- **Annahmen: Steuersatz auf Kapitalerträge und Basiszins** (`/annahmen`, `assumptions.UEBERSCHREIBBAR`). Beide waren gelesen (Vorabpauschale, Steuer in Ziele und Konten), aber nur im Texteditor änderbar. Das Feld zeigt jetzt den Satz ohne Rundung (`_feldtext`: 26,375 bleibt 26,375), sonst hätte Speichern ohne Änderung den Satz verschoben. Zwei feste Sätze „26,375 %“ (Hilfe auf `/hochrechnung`, Beschreibung der Depot-Rendite) sind weg, weil der Satz jetzt drehbar ist. Test: `tests/test_annahmen_steuer.py`.
- **Kategorien: Oberkategorie anlegen, Fixkosten und Einmalig** (`/kategorien`, `taxonomy.oberkategorie_anlegen`, `merkmale_setzen`). Das Handbuch versprach das `fix`-Flag auf der Seite; die Seite kannte es nicht. Gilt der Wert des Asts schon, schreibt die Seite nichts; ein Eintrag, der nur den Ast wiederholt, fällt weg. Test: `tests/test_kategorien_merkmale.py`.

**3. Große Lücken, nicht geschlossen, mit Aufwand.**
- **Immobiliendarlehen anlegen und ändern** (`loans.yaml`, rund dreißig Felder: Segmente, Zinsbindung, Anschluss, beobachtete Raten): groß. Ein Assistent mit mehreren Segmenten und einer Prüfung gegen den Tilgungsplan; mit eigener Seite und Tests rund so viel wie 6a. Das ist die wichtigste offene Lücke für einen Haushalt mit Wohneigentum.
- **Regel mit Teilung** (`split` in `rules.yaml`) anlegen: mittel. Die Seite zeigt sie, legt sie nicht an.
- **Steuerzuordnung** (`tax` je Subkategorie und der Baum `tax:`): mittel, nur für das Steuermodul.
- **Konto löschen** (nur ohne Buchungen, Positionen, Rollen, Kredite, Verträge): klein bis mittel; Schließen genügt bis dahin.
- **Netzzugang und Passwort** (`server.yaml`) in der App: mittel, sicherheitsrelevant (`finctl passwort`).
- **Rentenquellen: `kaufkraft`, Prüfwerte einer Police**: mittel, bewusst Datei.
- **Klein:** Anschrift und AfA-Basis eines Objekts; Name und Art einer bestehenden Oberkategorie, Notiz an einer Kategorie; eigene CSV-Profile ändern und entfernen.
- **Nicht von hier:** `forecast.yaml` (`exclude_from_recurring`, `overrides`, `enden`) und `cashflow_ohne_objekt` gehören zu `forecast/` und 8c2; `goals.yaml` ebenso.
- **Tote Schlüssel** (Tabelle oben, „tot“): `lebensplan.yaml` (bis auf drei Angaben), `forecast.yaml` (vier), `assumptions.yaml` (`ziel.*`, Median, Teilfreistellung), `properties.yaml` (rund zwanzig), `taxonomy_migrations.yaml: retire`. Entfernen wäre ein Schritt mit dem Haushalt (wie 5b-H), nicht hier.

**Abweichungen.**
1. → Opus: **Neue Felder erscheinen auf der Zahlenebene.** `/einrichtung` trägt die Daten der Konten zum Bearbeiten (ohne IBAN), `/annahmen` zwei Zeilen mit Werten, `/monatsabschluss` die Zahl der freien Konten im Auswahlfeld und `/kategorien` die Merkmale als Zahl 0/1 im Seitenzustand. Das ist bei einem neuen Feld nicht zu vermeiden. Hauptbuch und Ableitung bleiben gleich. Die Liste steht in `notizen/8c1_text_unterschiede.txt`.
2. → Opus: **Zwei feste Sätze mit „26,375 %“ entfernt** (siehe oben); ein Text, der einen jetzt drehbaren Wert nennt, wäre falsch geworden.
3. → Opus: **Eine Position hängt immer an einem Konto.** Ich habe keine Position „nur mit Namen“ angelegt, obwohl `balances.yaml` sie kennt: Eine Rentenversicherung ohne Konto fiele still aus der Auszahlungsrechnung (`policen_je_konto`). Wer ein Depot hat, legt zuerst das Konto an; die Seite sagt es.
4. → Opus: **`active: false` ohne Schliessdatum** bleibt, wie es ist, solange das Feld leer bleibt; nur ein anderer Wert im Feld ändert die Datei.

**Prüfen.**
- Suite (Entwicklungskopie): im ersten Gesamtlauf 2805 grün, 62 übersprungen, 9 rot. Fünf davon waren von mir und sind behoben (zwei Zeilen zu lang für `ruff`; `konten.aendern` und `api_category` über der Verzweigungsgrenze, jetzt aufgeteilt; ein gerundeter Satz im Text, den `test_leck` als krummen Betrag liest). `test_plattform` und `test_web` (Netz) liefen einzeln grün. Übrig und fremd: `test_design` (`vorlagen.html`, 7c, zu viel Text), `test_referenz` (erwartet, Opus schreibt neu).
- Musterhaushalt (`FINCTL_TESTDATEN=muster`): 2810 grün, 78 übersprungen, 2 rot. Eines war meins (`test_umstellen_paare` kannte die zwei neuen Annahmen nicht; behoben, 173 grün), das andere ist `test_leck` (fremd, siehe unten).
- Browsertests (`-m browser -n 0`): 68 grün, 4 übersprungen.
- `ruff`: null Funde.
- `tests/referenz.py pruefen --nur-zahlen`: `hauptbuch/` **gleich**. Von mir auf der Zahlenebene nur: `/annahmen` und `/hochrechnung` verlieren die Zeile „26,375“ (der feste Satz ist weg, der Wert steht im Feld), und `/einrichtung` und `kontenregister` zeigen „3 von 14 angepasst“ statt „3 von 12“ (zwei Stellschrauben mehr). Nicht von mir: `ableitung/prognosebasis` (`grund`, `delta`, `dauerhaft`: 6d/8c2), `vorlagen` und `vorlagen__anbindung` (7c). Die Textebene liegt in `notizen/8c1_text_unterschiede.txt` der Kopie.

**Fremde Fehlschläge, nicht behoben.** `test_design` für `vorlagen.html` (7c). `test_leck::test_amounts_in_prose_are_round` meldet auf dem Musterhaushalt einen gerundeten Prozentsatz in `docs/schritt6_bis_8.md` im Bericht von 8c2 (Satz über den Steuersatz im Text der Annahmen). `test_referenz` (erwartet).

### 7c

**Umgesetzt am 01.11.2026 (Sonnet).** Alles an der Entwicklungskopie (`FINCTL_DATEN`). Der dritte Weg aus ADR 0002: Die App schickt eine Vorlage selbst an eine Schnittstelle, aber nur, wenn der Haushalt sie eingetragen hat, und nur nach dem Zeigen.

**Aufbau.**
- `finctl/web/anbindung.py` ist die **einzige** Datei, die ein Netz anspricht (`urllib.request`, Standardbibliothek, keine neue Abhängigkeit). Form „chat completions“; eine Adresse ohne `/chat/completions` am Ende bekommt es angehängt. Ohne https geht es nur an `localhost`, `127.0.0.1`, `::1`. Weiterleitungen werden nicht gefolgt (sonst bekäme ein anderer Rechner Text und Schlüssel), an den eigenen Rechner geht es nie über einen Vermittler. Zeitlimit 120 s, Antwort höchstens eine Million Zeichen.
- **Ausgeschaltet ist der Standard:** ohne `config/anbindung.yaml` (`adresse`, `modell`, geschrieben über `dateien.yaml_schreiben`) zeigt `/vorlagen` keinen Knopf zum Senden, die Routen antworten 409, und es gibt keinen Verbindungsversuch. Es gibt bewusst **keine „Verbindung testen“-Taste**: Jeder Test wäre ein Senden.
- **Schlüssel** in `pfade.SCHLUESSEL_PATH` (`<Datenordner>/anbindung.schluessel`), Rechte `0600`, atomar geschrieben, nicht in `config/`. Die Seite hat ein leeres Passwortfeld, zeigt nur „eingetragen“ und hat „Schlüssel entfernen“ und „Anbindung entfernen“ (beides mit `confirm()`).
- **Seite `/vorlagen/anbindung`** (neu, in `APP_SEITEN`, Handbuch `### /vorlagen/anbindung`, 157 Wörter). Auf `/vorlagen` gibt es mit Anbindung den Knopf „Senden …“, ohne sie einen Link „Anbindung einrichten“.
- **Zeigen, dann senden:** `POST /api/vorlagen/hinaus` baut die Vorlage und liefert das Stück `_hinaus.html`: der vollständige Text, der Rechnername, „Das verlässt den Rechner“ (bei `localhost`, `127.0.0.1`, `::1`: „Der Text bleibt auf diesem Rechner“). Dabei legt der Server eine **Freigabe** an (Text, Adresse und Modell an ein Stichwort, zehn Minuten, genau ein Senden). `POST /api/vorlagen/senden` nimmt nur das Stichwort und sendet den Text der Freigabe, **nie einen, den der Browser nachreicht**. Hat sich die Anbindung dazwischen geändert, geht nichts hinaus. „Immer erlauben“ gibt es nicht.
- **Antwort:** Das Skript trägt sie in `#vl-antwort` ein und ruft `vlPruefen` auf, also dieselbe Prüfung wie bei einer eingefügten Antwort. Übernommen wird nichts.
- Fehler sind Sätze mit dem Rechnernamen: Adresse falsch („Keine Verbindung zu …“), Zeitüberschreitung, 401/403 (Schlüssel abgelehnt), 404, 429, 5xx, Weiterleitung, falsche Form. **Der Körper einer Fehlerantwort wird nicht weitergegeben**, weil mancher Dienst darin den Anfang des Schlüssels wiederholt.

**Abweichungen.**
1. → Opus: **`finctl/starter.py` bleibt neben `anbindung.py` im Test erlaubt.** Der Auftrag sagt „nur in dieser einen Datei“. Der Starter nutzt `socket` und `urllib.request` schon, um auf `127.0.0.1` zu fragen, ob die App läuft, und um einen freien Port zu finden (`test_web.py` führte ihn schon als `nur_lokal`). `tests/test_netz.py` führt ihn als eigene Ausnahme mit Grund und prüft, dass jeder `urlopen` dort mit `http://{HOST}:` beginnt und `HOST = "127.0.0.1"` gilt. Die Liste darf nur kürzer werden. `test_web.py::test_nothing_in_the_runtime_reaches_the_network_or_a_model` kennt jetzt auch `anbindung.py`.
2. → Opus: **Die Einrichtung liegt auf einer Unterseite `/vorlagen/anbindung`**, nicht in `/vorlagen` selbst (der Auftrag ließ beides zu). Sie trägt sonst `/vorlagen` und seinen Handbuchabschnitt, der schon fast an der Grenze war.
3. → Opus: **Freigabe mit Stichwort** ist mehr als der Auftrag verlangte („gesendet wird erst auf einen Knopf, bei jedem Mal neu“). Ohne sie könnte ein Aufruf von `/api/vorlagen/senden` Text senden, den nie jemand sah. Die Freigaben liegen im Arbeitsspeicher; ein Neustart der App verwirft sie.
4. → Opus: **Http nur an den eigenen Rechner.** Ein Server im Heimnetz (eine Adresse im Heimnetz) wird abgelehnt; der Schlüssel ginge sonst im Klartext. Soll das gehen, ist das eine Wahl mehr.
5. **Die gesendete Vorlage trägt, was auch die Kopiervorlage trägt** (Namen von Konten und Kategorien, Beträge; Gegenparteien nur beim Einordnen), jeweils durch `_ohne_nummern`. Die Anzeige davor ist der Schutz.
6. **Referenz, Text:** `seiten/vorlagen.txt` ändert sich (ein Satz, „Anbindung einrichten“, eine Datei mehr im Konfigurationsfuß, deshalb „2 Dateien → 3 Dateien“ in der Zahlenebene), `seiten/vorlagen__anbindung.txt` ist neu. Nur-Zahlen-Unterschiede an `annahmen`, `hochrechnung`, `kontenregister` und `einrichtung` (eine Zeile weniger, eine Zahl mehr in einer Zählung) stammen nicht von 7c.

**Tests.** `tests/test_anbindung.py` (16 Tests): ohne Anbindung kein Knopf und kein Verbindungsversuch (Netz im Test gesperrt: `connect`, `create_connection`, `getaddrinfo`); Eintragen und Zeigen verbinden nicht; mit einem erfundenen Server auf `127.0.0.1` (`tests/modellattrappe.py`) geht **genau der gezeigte Text** hinaus (ein nachgereichter `text` im Körper wird ignoriert), und die Antwort wird ein Vorschlag, `config/` bleibt gleich; ein zweites Senden mit demselben Stichwort, ein abgelaufenes oder bei geänderter Anbindung geht nicht hinaus; „Das verlässt den Rechner“ bei entfernter, „bleibt auf diesem Rechner“ bei lokaler Adresse; Adressprüfung; **der Schlüssel steht nie in einer Antwort der Seiten (auch nicht sein Anfang), nicht in `config/`, nicht im Log und nicht in der Ausgabe**, liegt mit `0600` außerhalb von `config/` und lässt sich nicht mit Zeilenumbruch eintragen; Entfernen schaltet alles aus; falsche Adresse, Zeitüberschreitung, 401, 404, 500, falsche Form und Weiterleitung ergeben je eine verständliche Meldung (die Weiterleitung erreicht den zweiten Server nie). `tests/test_netz.py` (4 Tests): Netz nur in `anbindung.py`, nur `routen/vorlagen.py` importiert sie. `test_browser.py`: „Text hin, Antwort zeigen“ mit dem erfundenen Server, einschließlich Abbrechen und Entfernen. `design_conventions.yaml`: neue Regel `senden-nur-auf-knopf`.

**Prüfen.**
- Suite (Entwicklungskopie): beim letzten Gesamtlauf 2826 grün, 4 rot: `test_referenz` (erwartet), `test_leck::test_amounts_in_prose_are_round` (ein krummer Betrag in einem fremden Abschnitt dieser Datei), `test_umstellen_paare` (allein grün, wackelt im parallelen Lauf), und ein Test von mir (`test_vorlagen`, durch ein `monkeypatch.undo()` in meinem Test), danach behoben.
- Musterhaushalt: 2811 grün, 1 rot (`test_leck`, derselbe Betrag).
- Browsertests (`-m browser -n 0`): 68 grün, 4 übersprungen.
- `ruff`: null Funde.
- `tests/referenz.py pruefen --nur-zahlen`: die Zahlen von `hauptbuch/`, `ableitung/` und allen Seiten sind gleich bis auf die oben genannten; `vorlagen`: nur die Zahl der Dateien im Fuß. Die Referenz habe ich nicht neu geschrieben.


**8c1, 8c2 und 7c abgenommen am 01.11.2026 (Opus), Referenz neu geschrieben.** Nach den drei Commits war `main` an einer Stelle kaputt: `_fortschritt_zeile` benutzte `gewaehlt`, bevor es gesetzt war. Zwei Einträge in `CHANGELOG.md` standen mitten in einem anderen. Die Reparatur lag im Arbeitsbaum und ist in `bd754b3` eingecheckt. `pruefen` auf `bd754b3` ergab 16 Unterschiede, das Hauptbuch ist gleich (Ausgabe in `notizen/8c_7c_referenz_vor_neuschreiben.txt`):
- In `ableitung/prognosebasis` fallen nur `grund`, `delta` und `dauerhaft` weg (8c2).
- `annahmen` und `hochrechnung` verlieren den festen Satz zum Steuersatz und bekommen zwei Felder (8c1).
- `einrichtung` und `kontenregister` zeigen die Daten zum Bearbeiten und „3 von 14“ (8c1).
- `vorlagen` hat die Anbindung, `vorlagen__anbindung` ist neu (7c).

Danach meldet `pruefen` Gleich. Beide Suiten sind grün bis auf eine gerundete Prozentzahl in diesem Bericht, die jetzt umschrieben ist. Bei den Browsertests war ein Notiztest rot, solange parallel die App gebaut wurde; allein ist er grün.

**Im echten Ordner (Opus, 01.11.2026):**
- `loans.yaml` trägt `opening_balance_cents` statt des Schlüssels mit Datum im Namen, und der Rückfall im Code ist weg (`3b32eb3`, auch in der Kopie).
- Mit dem Neubau der App aus `bd754b3` kamen die beiden Merkmale aus 8c2 dazu: `daneben` in `forecast.yaml` und `im_monatsabschluss` am Ziel in `goals.yaml`.
- Die alten Dateien liegen unter `notizen/vor_8c2_2026-11-01`.
- Geprüft auf einer Kopie des echten Ordners: 13 Seiten laden, Karte und Fortschrittszeile stehen wie vorher.
- `Finance OS mcp` antwortet aus der gebauten App, mit Handshake und Werkzeugliste.

Zu den Abweichungen:
1. **7c, Starter darf ans eigene Netz; Unterseite `/vorlagen/anbindung`; Freigabe je Text; unverschlüsselt nur an den eigenen Rechner:** angenommen.
2. **8c1, große Lücken** (Immobiliendarlehen, Regel mit Teilung, Steuerzuordnung, Netzzugang): bleiben für nach der Neufassung, mit dem Immobiliendarlehen zuerst. Die toten Schlüssel aus der Tabelle räumt ein Schritt mit dem Haushalt auf.
3. **8c2, Kategorien der mitgelieferten Taxonomie im Code:** Das ist ein Vertrag zwischen Produkt und Taxonomie, kein Einzelfall. Ein Test, dass jede dieser Kennungen in `vorgaben/taxonomy.yaml` steht, kommt mit dem nächsten Schritt.
4. **8c2, keine Maske für `daneben` und `im_monatsabschluss`:** bleibt so, bis ein zweiter Haushalt es braucht.

**Damit ist die Neufassung im Code abgeschlossen.**

### 5b-H

**Im echten Ordner erledigt am 01.11.2026 (Opus).** Die App in `/Applications` ist aus `7349ddb` neu gebaut (0.5.0; Rauchtest grün); die alte liegt im Papierkorb. Danach im echten Ordner, mit Sicherung der drei Dateien unter `notizen/vor_5b-H_2026-11-01`:
1. Die drei Korrekturzeilen in der Klammer „Korrektur Forecast“ gelöscht. Die übrigen Zeilen der Klammer bleiben.
2. Neue Klammer „Erwartete Einnahmen“, wie in der Kopie: die Schenkung jährlich ab Januar 2027 mit der Jahressumme, die Nebentätigkeit jährlich ab Juni 2027, je mit ihren Buchungen.
3. Die vier toten Schlüssel in `forecast.yaml` und der Median in `assumptions.yaml` samt Notizen entfernt.
Geprüft auf einer Kopie des echten Ordners mit dem neuen Stand: `/planung`, `/konten`, `/hochrechnung`, `/monatsabschluss`, `/annahmen` und `/ziele` laden, die Klammer zeigt beide Zeilen.

**In der Entwicklungskopie am 01.11.2026 (Opus), Referenz neu geschrieben.** Die Schenkung steht dort jetzt auch jährlich ab Januar 2027 mit der Jahressumme statt monatlich (alte Datei in `notizen/szenarien_vor_schenkung_jaehrlich_2026-11-01.yaml`). `pruefen --nur-zahlen` zeigte neun Unterschiede: `hochrechnung_jahre`, `kontoprognose_12` und `_60` und die Seiten `bestaende`, `hochrechnung`, `konten`, `monatsabschluss`, `start` und `ziele`. Die Einnahmen der Kontoprognose sinken in jedem Monat um den alten Monatsbetrag. Im Januar steigen sie um die Jahressumme minus diesen Betrag. Weitere Unterschiede gab es nicht (Ausgabe in `notizen/5b-H_schenkung_referenz_vor_neuschreiben.txt`). Danach Gleich; beide Suiten grün. Damit ist 5b-H abgeschlossen.

### 6a

**Umgesetzt am 01.11.2026 (Sonnet).** Alles an der Entwicklungskopie (`FINCTL_DATEN`). Beide Suiten grün bis auf `test_referenz` (siehe Prüfen), Browsertests grün (59 bestanden, 4 übersprungen wie vorher), `ruff` ohne Fund.

**Planung.** Die einzige Stelle in `planung.html`, an der ein Skript Zeilen baute, war die Trefferliste der Buchungssuche (`buchungSuchen`). Die Zeile steht jetzt in `_planung_buchungszeile.html`, die Liste in `_planung_vorschlaege.html`; `_klammer.html` bindet sie beim Laden ein. `/api/buchungen/suche` nimmt zusätzlich `zid` und `ausser` und antwortet dann mit `html` (die Liste), `kopf` (der Satz darüber) und `alle`. Das Skript setzt die Liste mit `outerHTML` ein, setzt den Satz und blendet „alle zuordnen“ ein oder aus. Ohne `zid` bleibt die Antwort so, wie sie war.

**Verträge.** In `abos.html` stand der ganze Editor als Zeichenkette im Skript (eine Datei von 555 Zeilen, 471 davon Skript). Er steht jetzt in `_abo_editor.html`, `_abo_teilen.html` und `_abo_bausteine.html` (Makros für Buchungszeile, Treffer, Eingangszeile, Zahlungssuche). Die Seite bindet den Editor jedes Vertrags beim Laden ein. Dazu:
- `POST /api/abos/editor`: der Browser schickt Entwurf (`st`) und Wissen (`info`), der Server zeichnet. So wird nach jedem Klick neu gezeichnet.
- `POST /api/abos/neu`: der Kasten „Neues Abo“ samt leerem Entwurf. (POST, damit `tests/referenz.py` keine neue GET-Schnittstelle sieht und nichts Neues in der Referenz entsteht.)
- `GET /api/abos/buchungen` nimmt `ausser` und liefert `html` (Trefferliste); bei weniger als zwei Zeichen weiter nur `{"rows": []}`.
- Der Entwurf eines Vertrags (`kopie` im Skript) kommt vom Server (`abo_zustand`, `ENTWUERFE`). Das Skript hält Entwurf und Wissen, liest Formularwerte (`lesen`), ändert beide bei Klicks und schickt sie zurück. `abos.html` hat jetzt 270 statt 471 Skriptzeilen, `planung.html` 200 statt 213.

`stueck()` in `basis.py` rendert ein Stück aus einer Vorlage; Seite und Schnittstelle gehen beide durch dieselbe Vorlage.

**Gleich geblieben, gemessen.** Ich habe den alten Stand (HEAD, als Arbeitsbaum) neben den neuen gestellt, beide gegen dieselben Daten, und in einem echten Browser das DOM jedes Editors verglichen (Tags, Klassen, Daten-Attribute, Text, Attributwerte): beim Laden alle 19 Verträge gleich; nach „Person hinzufügen“, „Zeitraum anlegen“, „Zahlung zuordnen“ (Suchfeld offen), Eingangssuche, Schließen und Buchungssuche 190 Zustände gleich; dazu mit eingespeistem Preisvorschlag, Vorschlägen, früheren Buchungen und Herkunftshinweisen (mit `<`, `&` und `"` im Text) vier Verträge gleich. Das Messskript liegt nur in meinem Scratchpad, nicht im Repository.

**Zwangsläufig anders, genannt:**
1. **Treffer der Buchungssuche auf `/planung` tragen die Vorzeichenfarbe** (`class="num neg"` oder `pos`), die jede Buchungszeile der Seite hat. Das Skript ließ sie weg; dieselbe Vorlage kann das nicht mehr. Im `CHANGELOG.md` (Eintrag steht, 8b hat ihn mitcommittet).
2. **Referenz: drei Seiten ändern sich, sonst nichts.** `abos`, `versicherungen` und `vertraege` (je Zahlen und Text) wachsen um den Inhalt der Editoren: Der Editor stand nur im Skript und kam deshalb in der Referenz nie vor; jetzt steht er in der Seite. Gemessen gegen die von dir neu geschriebene Referenz: `pruefen` meldet genau diese sechs Unterschiede (3 Seiten × Zahlen und Text), `planung`, alle anderen Seiten, `hauptbuch/` und `ableitung/` sind Gleich. Der Text hat **keine Zeile verloren** (0 entfernt, 1237 hinzu auf `vertraege`; auf der Zahlenebene nur Einfügungen). → Opus: Wenn das nicht gewollt ist, wäre die Alternative, die Editoren erst beim Aufklappen zu holen; dann bliebe die Referenz gleich, aber es gäbe keinen Seitenteil, den die Schnittstelle gegenzeichnen kann. Ich habe das Einbinden beim Laden gewählt, wie der Auftrag es vorsieht. Die Referenz muss für diese drei Seiten neu.
3. **`ein-zwecksatz-je-seite` bekommt drei Ausnahmen** (`_abo_editor.html`, `_abo_neu.html`, `_abo_teilen.html`, mit `offen`). Die Regel verbietet Erklärtext in Teilvorlagen; drei Absätze (Buchungen, Geteilt, neuer Vertrag) standen bisher im Skript, wo die Prüfung sie nicht sah, und ich habe sie wortgleich übernommen. → Opus: Sie gehören in ein `details.hilfe` oder ins Handbuch; das passt zu 6b/6c, sobald die Seite ihre Begriffe bekommt.
4. **`vertragsbetrag-ohne-vorzeichen`** prüft jetzt `_abo_editor.html` statt `abos.html` (dort steht das Feld jetzt).

**Konvention und Test.** `docs/design_conventions.yaml`: neue Regel `html-vom-server` („Ein Skript baut kein HTML, es setzt Stücke vom Server ein“). Prüfung `skript_ohne_html` in `tests/test_design.py`: zählt je Vorlage die Skriptzeilen, in denen ein Tag als Text steht (`<tr`, `<td`, `<div` und die übrigen Elemente) oder `createElement('tr'|'td'|'th'|'tbody')`; Kommentare zählen nicht. Die Ausnahmen stehen mit Zeilenzahl in `ausnahmen` und dürfen nur sinken, wie `ZU_VERZWEIGT`: `_combo.html` 1, `_ops.html` 6, `einrichtung.html` 18, `energie.html` 7, `konten.html` 5, `regeln.html` 11, `split.html` 9. `abos.html` und `planung.html` stehen nicht darauf.

**Tests.** `tests/test_html_stuecke.py` (11): Der Editor jedes Vertrags aus der Antwort ist der Editor der Seite (beide Reiter, verglichen als Ereignisfolge ohne Leerraum), er zeigt den Entwurf statt des Dateistands (mit Sonderzeichen), der Kasten für einen neuen Vertrag, die Trefferliste der Verträge mit und ohne `ausser`, und auf `/planung` jede Zeile der Seite steht in der Antwort der Suche gleich, `ausser` lässt Zugeordnetes weg und sagt es, ohne Angabe kommt die Meldung als Stück, ohne `zid` bleibt die Antwort wie sie war, die Treffer tragen die Vorzeichenfarbe. `tests/test_browser.py` (+5): Planung („Text hin, Antwort zeigen“: ein Suchtext, der nichts findet, zeigt den Satz und blendet den Knopf aus), Editor je Reiter (Person hinzufügen und Suchen zeichnen neu, nichts wird geschrieben), neuer Vertrag je Reiter (Kasten erscheint, Abbrechen leert ihn). → Opus: Bestehende Browsertests für diese Seiten habe ich nicht vereinfacht, weil keiner mehr Zeilen zusammensetzte, die er prüfen musste; der Notiztest (`test_notiz_eines_vertrags_ist_mehrzeilig`) läuft unverändert, nur findet er den Editor jetzt schon beim Laden.

**Prüfen.** `.venv/bin/python -m pytest -q`: 2579 bestanden, 54 übersprungen, 1 Fehlschlag: `test_referenz` (die sechs Unterschiede oben, sonst nichts). Mit `FINCTL_TESTDATEN=muster`: 2565 bestanden, 67 übersprungen. `-m browser -n 0`: 59 bestanden, 4 übersprungen. `ruff` null Funde. Ein erster Lauf unter Last (Last 170 durch parallele Sitzungen) zeigte zusätzlich `test_dateinamen`, `test_module` und `test_lint`; sie liefen einzeln und im zweiten Gesamtlauf grün, die Ursache war, dass die Dateien der anderen Sitzung mitten im Lauf wechselten.

**Offen / nicht getan.** Die anderen Seiten mit Skript-HTML (siehe Ausnahmen) sind nicht angefasst. `planung.html` definiert `neueKlammer` zweimal (steht so schon in 0.5.0, ich habe es gelassen). Das Neuzeichnen des Editors kostet jetzt eine Anfrage an den lokalen Server. Gelesen wird vor jedem Neuzeichnen (`lesen`), Eingaben gehen dabei nicht verloren; wer aber während der Antwort noch tippt, tippt in den alten Editor. Das habe ich nicht gemessen und nicht abgesichert.
