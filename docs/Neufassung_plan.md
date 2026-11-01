# Neufassung: Reihenfolge

Stand: 04.10.2026. Die Begriffe stehen in `CONTEXT.md`, die Entscheidungen
in `docs/adr/`. Dieser Plan sagt, in welcher Reihenfolge die App dorthin
kommt und was jeden Schritt absichert.

## Grundsatz: ein Code, ein festgehaltener Stand

Keine zweite Codebasis. Der heutige Stand wird als Tag `basis` festgehalten
und läuft für den Monatsalltag aus einem eigenen Arbeitsbaum, mit dem echten
Datenordner. Die Neufassung entsteht auf `main`, Schritt für Schritt, und
arbeitet bis zum Umstieg auf einer Kopie des Datenordners (`FINCTL_DATEN`).
Umgestiegen wird, wenn die Neufassung alles kann, was `basis` kann.

Warum nicht neu anfangen: Parser, Hauptbuch, Regeln und Sicherung sind
belegt und bleiben. Neu gedacht wird die Schicht darüber, und die lässt sich
gegen den alten Stand messen. Zwei Codebasen müssten dagegen beide gepflegt
werden, solange die alte im Einsatz ist.

## Jeder Schritt ist einer von zwei Sorten

- **Gleich:** Umbau ohne neue Zahl. `tests/referenz.py pruefen` muss
  unverändert grün bleiben.
- **Gewollt:** Eine Zahl ändert sich mit Absicht. Der Schritt nennt vorher,
  welche Zahlen sich wie bewegen. Die Referenz wird danach in einem eigenen
  Commit neu geschrieben, nie im selben.

Beide Läufe der Suite (echte Daten und Musterhaushalt) sind nach jedem
Schritt grün.

## Die Schritte

### 0. Absichern

- Tag `basis` setzen, Arbeitsbaum für den Alltag einrichten, Datenordner für
  die Entwicklung kopieren.
- **Die Referenz bekommt eine Zahlenebene.** Heute vergleicht sie den
  sichtbaren Text der Seiten. Jede Umbenennung nach dem Glossar wäre damit
  ein Unterschied, und eine echte Zahlenänderung ginge darin unter. Künftig
  wird jede Seite zweimal verglichen: ihre Zahlen streng, ihr Text getrennt.
- **Umbenennungsprobe:** Ein Test benennt in einer Kopie jedes Konto, jedes
  Objekt und jeden Kredit um. Alle Zahlen müssen gleich bleiben. So wird
  sichtbar, wo der Code noch Einzelfälle kennt. Bekannt sind zwei Stellen:
  `"dkb-giro"` als Vorgabe für das Betriebskonto und für
  `finctl forecast --account`.
- **Rechnen auf dem Server (nachgetragen, erledigt):**
  Der Server rechnet alles, was gespeichert wird oder worauf eine
  Entscheidung beruht. Der Browser nimmt Eingaben auf und zeigt, was der
  Server zurückgibt. Was er selbst tun darf: Tooltips platzieren, Tastatur,
  Spaltenbreiten, Ziehen und Ablegen.
  - **Beträge gehen als Text an den Server**, der sie mit
    `parse_de_amount` aus `finctl/ledger/db.py` liest, derselben Funktion
    wie bei den Auszügen. Heute lesen neben `_betrag.html` noch
    `split.html`, `renten.html`, `annahmen.html`, `kredite.html` und
    `immobilie.html` selbst. Auf `/split` wird „1.234,56“ dadurch als
    1,23 € gelesen; der Server lehnt ab, weil die Teile nicht aufgehen, und
    die Meldung führt in die Irre. Ist eine Eingabe mehrdeutig, antwortet der
    Server mit einer Meldung, statt zu raten.
  - **Vorschauen kommen vom Server**, nach dem Muster `vorschau: true` von
    `/api/geteilt/teilung`: Das Formular schickt, was dasteht, der Server
    gibt Ergebnis und Rechenweg zurück und speichert nichts. Zuerst Summe
    und gleichmäßiges Verteilen auf `/split`, das der Server schon kann
    (`geteilt._groesster_rest`), dann Fälligkeiten und Kennungen in
    `abos.html`.
  - **Sperre:** Ein Test verbietet `parseFloat`, `toFixed` und `* 100` in
    Skripten der Vorlagen. Was es heute noch hat, steht in einer Liste, die
    nur kürzer werden darf, wie `ZU_VERZWEIGT`.
- **Browserprobe (nachgetragen, erledigt):** Rund 3.000 Zeilen Skript in den
  Vorlagen laufen in keinem Test; die Suite rendert nur HTML. Dass das
  zählt, zeigt der Fehler in `finctl/web/basis.py`: Speichern ohne Änderung
  machte einen Betrag hundertmal so groß. Deshalb `pytest-playwright` mit
  Chromium, gegen dieselbe Datenkopie wie die übrige Suite, als langsamer
  Test markiert. Geprüft wird nur, was Daten schreibt:
  - **Speichern ohne Änderung ändert keine Datei**, für jedes Formular, das
    schreibt.
  - **Betragseingabe:** deutsche und Python-Schreibweise, Tausenderpunkte,
    negative und leere Werte.
  - Wenige Abläufe mit Zustand: Klammer an und aus, Auswahl im Kombifeld,
    der Klappzustand nach dem Neuladen.

  Gefunden wird über Feldnamen und Rollen, nicht über sichtbaren Text, sonst
  bricht Schritt 6 jeden Test aus dem falschen Grund. Layout und Farben
  bleiben bei `tests/test_design.py`. Die Probe deckt auch ab, was die
  Zahlenebene nicht sieht: Werte in Eingabefeldern. Sie muss vor Schritt 5
  stehen, der jeden Schreibweg umlegt. Vorher lohnt der Blick, welches
  Skript auf den Server ziehen kann, wie es die Diagramme schon getan haben:
  Jede verlegte Zeile braucht keinen Browsertest.

**Erledigt am 04.10.2026**, Rechnen auf dem Server und Browserprobe am selben Tag nachgeholt.

- Tag `basis` auf fb61206, Arbeitsbaum `~/Projects/finctl-basis` mit eigenem
  `.venv` und dem echten Datenordner; Entwicklungskopie `Finance OS
  Entwicklung` neben dem echten Ordner (ohne `referenz_archiv`, ohne `ort.txt`).
  Die Referenz der Kopie war vor und nach dem Umbau der Referenz gleich.
- Zahlenebene: `referenz.zahlen`, aus den Seitendateien abgeleitet, daher kein
  neues Format und keine neu geschriebene Referenz. `pruefen --nur-zahlen`.
  Grenze: Was die Seitendateien nicht enthalten (Werte in Eingabefeldern,
  Diagrammdaten in Skripten), sieht auch die Zahlenebene nicht.
- Umbenennungsprobe: `tests/test_umbenennung.py`. Sie besteht auf beiden
  Datenordnern, die Seiten und das Hauptbuch zeigen nach der Umbenennung
  dieselben Zahlen (Seiten ohne Reihenfolge: eine nach Kennung sortierte Liste
  ordnet sich neu). Die Seiten erreichen die zwei bekannten Stellen aber nicht;
  deshalb gehört ein zweiter Test dazu, der Kennungen aus `config/` als Text in
  `finctl/` sucht und sieben Fundstellen in sechs Dateien nennt (`BEKANNT`).
  Beim Bau war der erste Fund keiner des Codes: Die Einstellungen im
  Dashboard legen Untergrenzen unter `floor_cents:<konto>` ab, eine Kennung in
  einem zusammengesetzten Schlüssel. Die Probe benennt auch diese um.

- Rechnen auf dem Server: `parse_eingabe_betrag`, `parse_eingabe_zahl` und
  `prozent_als_anteil` in `finctl/ledger/db.py` lesen, was getippt wurde, mit
  der Auszugsfunktion `parse_de_amount` dahinter und einer Prüfung davor:
  „1,234.56“ und „1,234“ werden mit Meldung abgelehnt statt geraten
  (`EingabeError`, Antwort 400 mit `error` und `feld`). Die Seiten schicken
  `<feld>_text` (`lies_texte` in `web/basis.py`); die alten `…_cents` gelten
  weiter. Umgestellt sind `/split`, `/renten`, `/annahmen`, `/kredite`,
  `/immobilie`, der Teilzeit-Anteil auf `/planung`, Betrag und Anteile auf
  `/abos` und der Grundpreis auf `/energie`. Vorschauen vom Server: Summe und
  gleichmäßiges Verteilen auf `/split` (`/api/split/<id>/vorschau`),
  Termine und Kennung auf `/abos` (`/api/abos/vorschau`, die Kennung entsteht
  beim Speichern). Sperre: `tests/test_rechnen_im_browser.py`; übrig ist
  `centsAus` in `_betrag.html`, das noch fünfzehn Seiten rufen.
- Browserprobe: `tests/test_browser.py`, Playwright mit dem Chrome des Systems
  (ein gebündeltes Chromium wird genommen, wenn es da ist; `pytest-playwright`
  steht in den Dev-Abhängigkeiten). Der Server läuft in einem Thread auf der
  Datenkopie der Suite; `config/` und das Hauptbuch werden nach jedem Test
  zurückgestellt. Geprüft: Speichern ohne Änderung für jede Seite mit
  Formularen, Betragseingabe vom Feld bis in die Datei, Klammer an und aus,
  Kombifeld, Klappzustand.
- **Was die Browserprobe fand**, schon beim ersten Lauf, alles vor dem Umbau
  vorhanden: `/annahmen` stürzte mit 500 ab, sobald die Kostenschwelle einmal
  gespeichert war (die Seite zeigte 0,00 statt der Vorgabe und schrieb sie als
  Eintrag); `/energie` verlor beim Speichern ohne Änderung vier Cent Grundpreis
  im Jahr (gezeigt je Monat, gerundet, mal zwölf); `/immobilie` schrieb
  Nullen als Einträge, `/kredite` friert die gerechnete Rate eines
  Vorlagenkredits als Eingabe ein, `/regeln` schrieb `allgemeine_regeln: false`.
  Eine Hilfe, `finctl/dateien.py`, schreibt die Dateien der Seiten nur noch,
  wenn sich ihr Inhalt ändert (als Daten verglichen, nicht als Text).

### 1. Rollen statt Banken (gleich)

Prognose und Planung kennen nur Rollen. Feste Kontokennungen im Code
verschwinden, das Betriebskonto ist das mit dieser Rolle. Ein Konto lässt
sich archivieren, wenn der Anbieter wechselt. Danach besteht die
Umbenennungsprobe.

**Erledigt am 04.10.2026.** Das Betriebskonto ist das aktive Konto mit der
Rolle `operating` (`_operating_account`); ein archiviertes zählt nicht. Ohne
Rolle gilt das erste aktive Giro mit Auszügen, ohne das kein Betriebskonto.
`finctl forecast` nimmt ohne `--account` das Betriebskonto. Erklärungen,
Kommentar und Formular-Platzhalter nennen keine Kennung mehr; `BEKANNT` in
`tests/test_umbenennung.py` ist leer. Referenz, Zahlen und Text, unverändert.

Offen, bewusst nicht in diesem Schritt:
- `finctl/ingest/paypal.py` kennt die Kennung `paypal` fest (SQL auf
  `account_id`). Das ist der Umhänger für PayPal-Zahlungen, ein Modul für eine
  Plattform, und gehört zu Schritt 8; die Kennungsprüfung nimmt `ingest/` aus.
- `web/routen/planung.py` liest das Betriebskonto aus `forecast.yaml` allein,
  ohne die Kontenseite darüber (`forecast_config()` täte das). Ein Wechsel der
  Rolle auf `/konten` kommt dort nicht an. Es zu ändern verschiebt Zahlen, wenn
  Basis und Kontenseite verschieden sind; hier waren sie es nicht.
- Tests und das Handbuch nennen noch echte Kennungen als Beispiel
  (`tests/test_forecast.py`, `finctl/HANDBUCH.md`); das ist Schritt 6 und die
  Weitergabe.

### 2. Eine Fortschreibung für beide Vorschauen (gleich)

Kontoprognose und Hochrechnung leiten ihre Posten heute getrennt her, und
mehrere Seiten erklären nur, warum beide auseinanderlaufen. Künftig gibt es
eine Herleitung je Kategorie mit Verfahren und Fenster als Eingaben. Jede
Vorschau wählt ihre Eingaben: die Kontoprognose den Schnitt über ein halbes
Jahr, die Hochrechnung die Zwölfmonatssumme, wie heute. Deshalb bleiben alle
Zahlen gleich. Jede angezeigte Zahl hat einen Rechenweg, dessen Posten sie
ergeben.

Das ist der größte Schritt und der riskanteste. Er wird in Teilen gebaut,
jeder Teil gleich. Der Arbeitsplan dazu, mit den Unterschieden, die erhalten
bleiben müssen, steht in `docs/schritt2_fortschreibung.md`.

**Erledigt am 04.10.2026** (Teilschritte 2.0 bis 2.7, jeder gegen die Referenz,
Zahlen und Text). Offen geblieben: Gehalt, `szenarien.messung`,
`jahre._vertragsenden` und `jahre.verkaeufe` messen noch mit eigenen Abfragen,
und die benannten Unterschiede zwischen den Vorschauen (Fenster, Umbuchungsregeln,
Verträge, Einmaliges) sind nicht angeglichen; beides steht mit Begründung unter
„Gefundene Abweichungen“ in `docs/schritt2_fortschreibung.md` und ist die
Eingabe für Schritt 3 und 4.

### 3. Jüngst und Wirkung (gewollt)

Das ist der Schritt, der geändertes Verhalten sichtbar macht.

Der Arbeitsplan mit den festgelegten Entscheidungen steht in
`docs/schritt3_juengst_wirkung.md`. Abweichend von der Skizze unten gilt
Jüngst dort zunächst nur für Kosten im Block Konsum, und die Wirkung
rechnet beide Stichtage unter den heutigen Annahmen.
Eingeschoben ist dort 3.2b: Zinsen je Konto und Kapitalertragsteuer mit
Sparerpauschbetrag. Die Hochrechnung zählte Tagesgeldzinsen doppelt
(Satz auf den Topf und gebuchte Zinsen fortgeschrieben).

- **Jüngst** als drittes Verfahren: die letzten drei vollständigen Monate,
  gleich gewichtet, nur für Kategorien ohne Fixkosten-Merkmal. Bis Schritt 4
  ersetzt das Merkmal den Takt.
- Ziele und Hochrechnung zeigen beide Werte nebeneinander: „im Schnitt“ und
  „in deinem Tempo der letzten drei Monate“.
- **Wirkung:** Der Monatsabschluss zeigt, wie weit sich jedes Ziel seit dem
  letzten Abschluss bewegt hat, aufgeteilt nach Ursache. Die Hochrechnung
  wird dafür so nachgerechnet, wie sie am letzten Stichtag aussah, mit Daten
  nur bis dahin, wie es der Treffer-Check schon tut. Es wird kein Stand
  gespeichert, der veralten könnte.

Gewollt sind neue Zahlen auf `/ziele`, `/hochrechnung` und
`/monatsabschluss`. Alle bestehenden Zahlen bleiben gleich, weil „im Schnitt“
weiter so rechnet wie heute.

**Erledigt am 05.10.2026** (Teilschritte 3.1 bis 3.7, dazu 3.2b und 3.2c;
der Stand je Teil steht in `docs/schritt3_juengst_wirkung.md`). Die
Hochrechnung rechnet wahlweise im Tempo der letzten drei Monate, `/ziele` zeigt
beide Tempi, und der Monatsabschluss zeigt je Ziel die Wirkung gegenüber dem
Vormonat nach Ursache, bei „Tempo“ mit den Kategorien dahinter. Dafür wurden
Lesen und Rechnen der Hochrechnung getrennt (`Eingaben`), getippte Stände
bekamen einen Verlauf, und die Zinsen auf Tagesgeld zählen nicht mehr doppelt:
Sie werden je Konto gerechnet, die Kapitalertragsteuer mit dem
Sparerpauschbetrag.

Offen geblieben, jeweils mit Warum unter „Gefundene Abweichungen“ in dem Plan:
- **Der Kalender bewegt die Ziele stärker als das Verhalten** (die Zwölfmonatssumme
  zählt eine Zahlung dreizehnmal, wenn ihr Buchungstag über das Monatsende
  rutscht). Das ist Schritt 4. Jüngst gilt bis dahin nur für Kosten im Block
  Konsum und wird dort „jede Reihe ohne festen Takt“.
- **Der Verlauf beginnt beim ersten Speichern.** Wer noch keinen Abschluss mit
  Speichern gemacht hat, sieht im Abschnitt den Satz, ab wann es einen Vergleich
  gibt, auch die Entwicklungskopie.
- **Die Rentenlücke hat einen Zielbetrag für beide Tempi** (der aus dem Schnitt);
  im Tempo der letzten drei Monate unterschätzt der Prozentwert sie. Die Kosten
  für eine zweite Rechnung sind weg, ob sie kommt, ist eine Frage der Anzeige.
- **Die Kategorien der Tempo-Ursachen stehen als Kennung da** (Schritt 6), und die
  Kursbewegung gilt für den ganzen Topf Depot, nicht je Depot.
- **Ein Abschluss nach dem Jahreswechsel**, bei dem die Auszüge des alten Jahres
  fehlen, trägt den Sprung des Basisjahrs in „Der Monat“; nicht nachgestellt.
- **Seitenzeit:** `/konten` und `/monatsabschluss` lesen ihre Dateien je Konto neu
  (rund 300 Lesevorgänge je Aufruf, die meiste Zeit der Seite). Ein eigener
  Gleich-Schritt; er ändert keine Zahl.

### 4. Reihe und Takt (gewollt)

Arbeitsplan: `docs/schritt4_reihe_takt.md` (Teilschritte 4.1 bis 4.6). Jüngst
bleibt im Konsum und zählt dort nur Reihen ohne festen Takt; Einmalig gilt für
markierte Buchungen und Kategorien mit Merkmal, nicht für ganze Reihen.

Jede Reihe hat einen Takt, den die App erkennt oder der Haushalt per
Handentscheidung festlegt: jährlich, einmalig und so weiter. Einmalig
ersetzt die Kategorie „Sondereffekt“. Jüngst überspringt jetzt Reihen mit
festem Takt statt Kategorien mit Fixkosten-Merkmal. Gewollt sind
Verschiebungen in der Kontoprognose, wo eine Reihe ihren Takt bekommt.

Dazu die Hochrechnung: Sie summiert heute zwölf Monate je Kategorie. Eine
Monatszahlung, deren Buchungstag über das Monatsende rutscht, steht dort
dreizehn- oder elfmal, und eine Miete, die einmal einen Monat zu spät
kommt, verschiebt den Jahreswert. Die Wirkung aus Schritt 3 hat das
sichtbar gemacht: Der Kalender bewegte die Ziele stärker als das Verhalten.
Mit Takt rechnet eine monatliche Reihe Betrag je Termin mal zwölf, wie es
die Kontoprognose mit dem verrutschten Buchungstag schon tut. Das ist der
wichtigste Grund, Schritt 4 direkt nach Schritt 3 zu machen.

**Erledigt am 06.10.2026** (Teilschritte 4.1 bis 4.6, dazu 4.2b, 4.2c und 4.5b;
der Stand je Teil steht in `docs/schritt4_reihe_takt.md`). Jede Reihe hat einen
Takt, erkannt aus 24 Monaten Buchungen oder auf `/reihen` festgelegt. Eine Reihe
mit festem Takt zählt mit ihrem Betrag je Termin, in der Hochrechnung so oft
im Jahr, wie sie kommt, in der Kontoprognose als Posten an ihrem Termin. Ist
sie beendet, zählt sie nirgends. Der Rest rechnet wie vorher, im Konsum
wahlweise Jüngst. Einmalig ersetzt den Block Sondereffekt. Schreibweisen einer
Gegenpartei führt der Haushalt auf `/reihen` zusammen. Die Kontoprognose bucht
Kosten und Einnahmen einer Kategorie getrennt an ihrem Tag; der Tiefpunkt im
Monat ist dadurch tiefer und näher an den echten Monaten. Offen und
weitergereicht: ein Buchungstag je Reihe, das Nachladen der Bedienung auf
`/reihen` (Schritt 6), die Merkmale beim Umbenennen einer Kategorie und
`module.erststart` (Schritt 8). Alles mit Warum und Schritt steht unter
„Gefundene Abweichungen“ im Arbeitsplan.

### 4b. Policen (gewollt)

Arbeitsplan: `docs/schritt_policen.md` (Teilschritte P.1 bis P.3). Erst nach
Abnahme von Schritt 4 und neu geschriebener Referenz.

Eine Police wächst in der Hochrechnung mit ihrem Beitrag bis zur Auszahlung
und mit Depotsatz minus ihren Effektivkosten. Heute wächst sie nur mit dem
Depotsatz auf den getippten Stand, und der Beitrag verschwindet als Ausgabe.
Der Rückkaufswert steht als Notfallwert daneben, die jährliche Mitteilung
als Prüfwert. Gewollt sind höhere Auszahlungen der Policen und ein größeres
Depot ab dem Jahr der Auszahlung.

Stand 07.10.2026: P.1, P.2 und P.2b sind abgenommen, die Referenz ist danach
neu geschrieben. P.2b hat zwei Dinge geändert:
- Der Abzug auf eine Kapitalauszahlung geht von der Auszahlung ab, nicht aus
  dem Tagesgeld.
- Die Ausgabe für den Beitrag einer Police bleibt nominal.

Es hat außerdem die Fortschrittszeile aus 4c (T.2) erledigt.

**Erledigt am 07.10.2026** (P.1 bis P.3 mit P.2b). P.3 zeigt:
- den Notfallwert in einem eigenen Abschnitt auf `/konten`;
- den Prüfwert auf `/renten`;
- die Angaben der Mitteilung im Monatsabschluss.

Die Referenz ist danach neu geschrieben.

### 4b′. Zielrate (gewollt, nur /ziele)

Arbeitsplan: `docs/schritt_ziel_rate.md` (Z.1 bis Z.3). Nach Abnahme von
P.3 und neu geschriebener Referenz, vor 4c.

Die Zielkarte zeigt neben der Rate ohne Rendite eine zweite: die Rate, wenn
Bestand und Rate mit den Sätzen der Hochrechnung wachsen. Die Sätze kommen
aus den Annahmen, je Bestandsart. Die Hochrechnung ändert sich nicht. Auf
`/ziele` ändert sich nur der Text der Ratenzeile, und die neue Zahl kommt
dazu.

**Erledigt am 07.10.2026** (Z.1 bis Z.3). Die Referenz ist danach neu geschrieben.
Entschieden: Eine Auszahlung vor dem Stichtag bleibt, wie sie ist. Die Karte
zählt sie nicht, und /ziele zählt sie im Depot mit.

### 4c. Teilzeit, betriebliche Altersvorsorge (gewollt → gleich)

Arbeitsplan: `docs/schritt_teilzeit_bav.md` (T.1 und T.3; T.2 ist in P.2b
erledigt). Nach 4b′.

Die Teilzeit steht einmal, in den Annahmen, und die Zeilen ihrer Klammer
folgen ihrem Start. Eine betriebliche Altersvorsorge, die nur der
Arbeitgeber zahlt, bekommt ein Modell aus Stand, Arbeitgeberbeitrag und
gewählter Hochrechnung, und ihr Beitrag sinkt mit der Teilzeit. Gewollt war
nur, dass die Fortschrittszeile im Monatsabschluss gegen die Basis des Ziels
misst wie /ziele. Das hat P.2b schon erledigt. Was bleibt, ist gleich, solange
die Klammer „Teilzeit“ ausgeschaltet ist.
Renten als „zugesagt“ gegen Barista FIRE sind geprüft und verworfen
(Kapitalerhalt, Begründung im Arbeitsplan).

Erledigt am 07.10.2026 (T.0, T.1 und T.3). Dazu kam T.0: Ein Prüfwert darf
ohne Satz stehen. Die Herleitung der Auszahlung nennt jetzt den Satz. Die
Zahlen sind gleich geblieben, die Referenz ist neu geschrieben.

### 5. Notiz statt Kommentar (gleich)

ADR 0001. Jeder Eintrag hat einen Ort und eine datierte Notiz. Die
Kommentare der Basisdateien werden einmal in Notizen übernommen; das ist der
einzige Schritt, der persönlichen Text anfasst, und er läuft nur im
Datenordner. Die Zweiteilung in Basisdatei und `_custom`-Datei entfällt.
Gleich, weil sich nur der Ort der Begründungen ändert.

Arbeitsplan: `docs/schritt5_notizen.md` (N.0 bis N.4). Die Umwandlung ist
ein Befehl, `finctl umstellen`, und derselbe Befehl stellt beim Umstieg den
echten Datenordner um.

**Abgeschlossen am 25.10.2026.** N.0 bis N.4d sind abgenommen. Die
Entwicklungskopie ist umgestellt, und eine einzelne Umstellung der Sicherung von
vor Schritt 5 ergibt Byte für Byte dasselbe. Eine Kopie des echten Ordners ließ
sich umstellen, und alle Seiten antworten. Handbuch (Abschnitt 2b) und
`CHANGELOG.md` beschreiben den Umstieg. Offen für später:
- **Schritt 6:** Text des Umwandlers ohne Umlaute; das Feld „Warum“ auf
  Verträge; „Budgettopf“ im Handbuch; die Rückfragen beim Entfernen.
- **Schritt 8:** die Tabelle `settings` samt Abgleich; `--probe` schreibt auch
  dann eine Kopie, wenn nichts umzustellen ist oder eine Prüfung scheitert; eine
  Notiz in der Tabelle lässt sich nur mit SQL löschen.

### 5b. Ein Haushalt, zwei Zeitachsen (gewollt)

Arbeitsplan: `docs/schritt5b_zeitachsen.md` (E.0 bis E.8). Zinsen aus dem
Kontostand und zwölf Monate Messfenster am 09.10.2026 entschieden. Am
25.10.2026 bestätigt: Die Monatsrate ist in beiden Modellen die
Zwölfmonatssumme durch zwölf, der Median entfällt (dort Entscheidung 6).

Gefunden am 08.10.2026 bei der Frage, ob /ziele dieselben Daten sieht wie
/konten. Beide beginnen beim selben Bestand. Das Monatsmodell (/konten) spart
2027 aber rund 2.700 € im Monat weniger als die Jahresrechnung (/ziele
„hochgerechnet“, /hochrechnung). Ursache sind sechs verschiedene Eingaben, keine
falsche Rechnung:
- **Objektprognose:** Das Monatsmodell kennt sie nicht.
- **Gehalt:** Das Monatsmodell nimmt die Untergrenze statt des Medians.
- **Schenkungen und Nebentätigkeit:** Die Modelle schreiben sie verschieden fort.
- **Zinsen:** Das Monatsmodell nimmt gemessene Zinsen mit einer festen Korrektur,
  die Jahresrechnung rechnet sie aus dem Kontostand.
- **Messfenster:** sechs Monate im Monatsmodell, zwölf in der Jahresrechnung.
Die Rechnung mit den Beträgen steht in `notizen/diagnose_konten_vs_jahre.md` der
Entwicklungskopie.

Dazu kommt ein Befund auf /ziele. Balken und Rate messen nur den heutigen
Bestand. „Hochgerechnet“ kennt nur Jahresenden, und die Kaskade füllt den
Notgroschen zuerst auf. Eine Klammer wie ein Autokauf bewegt deshalb die Karte
eines kurzfristigen Ziels nicht, obwohl /konten sie sieht.

Entschieden am 08.10.2026:
- **Objektprognose** (Miete, Kosten) bleibt unter Immobilien, nicht in Planung.
  Sie ist eine Eigenschaft des Objekts und kein Schalter. Das Monatsmodell liest
  sie von dort und bucht sie auf das Konto, auf dem sie landet. Eine zweite
  Eingabe in Planung zählte das Objekt in der Jahresrechnung doppelt.
- **Gehalt:** beide Modelle rechnen mit dem Gehaltsfloor, nicht mit dem Median.
  Zu defensiv ist gewollt. Der Floor wächst in beiden mit der
  Gehaltssteigerung der Annahmen (heute 2 % im Jahr); das Monatsmodell rechnet
  ihn heute flach und wird angepasst. Der Median bleibt höchstens als
  Vergleichszahl.
- **Schenkung und Nebentätigkeit** (Lehrvergütung, einmal im Jahr) stehen in
  Planung, als erwartete Einnahme mit Betrag und Monat. Die bisherigen Buchungen
  werden der Zeile zugeordnet, damit sie die Messung ersetzt und nicht neben ihr
  steht. Nach dem Eintragen prüfen beide Modelle gegeneinander, dass nichts doppelt
  zählt.
- Offen bleiben die Zinsen aus dem Kontostand und das gemeinsame Messfenster.

Ziel: beide Modelle bekommen ihre Eingaben aus einer Quelle. Der einzige
bleibende Unterschied ist die Kaskade der Jahresrechnung. Ein Paritätstest
vergleicht je Jahr die Flüsse beider Modelle. Kurzfristige Ziele (Stichtag
innerhalb des Horizonts von /konten) messen mit dem Monatsmodell, und der
Notgroschen wird Untergrenze seines Kontos. Kommt nach dem Umstieg: Der Schritt
bewegt viele Zahlen, und der Umstieg soll nicht auf ihn warten.

### 6. Oberfläche nach dem Glossar (gleich in den Zahlen)

Begriffe nach `CONTEXT.md` (Themenkasse, Vorgang, Anlageklasse,
Untergrenze), Text nur über Begriffe, Notizen sichtbar und datiert. Die
Zahlenebene der Referenz bleibt gleich, die Textebene wird mit Absicht neu
geschrieben. `docs/design_conventions.yaml` bekommt die Regel, dass fester
Text keine Einzelfälle nennt.

**Der Server baut das HTML.** `abos.html` und `planung.html` setzen
Tabellenzeilen heute als Text in Skripten zusammen. Künftig schickt der
Server fertige Stücke aus denselben Jinja-Vorlagen, die auch die Seite
rendern. Das ist der größte Abbau an Skript, und die Browserprobe prüft
danach nur noch „Text hin, Antwort zeigen“.

**Entfernen nennt die Notiz.** Seit Schritt 5 nimmt „entfernen“ oder
„löschen“ einen Eintrag samt Notiz aus der Datei (Renten, Abos, Kredite,
Objekte). Sobald die Notiz sichtbar ist, sagt die Rückfrage, dass sie mitgeht.

**Die Kontokarte fragt nach dem Kredit.** Die Untergrenze aus einem Kredit ist
ein Haken. Ohne Kredit schreibt er `true`, und das bewirkt nichts (Schritt 5,
N.3f). Die Karte bietet stattdessen die Kredite zur Auswahl an.

**Nachreichen gehört in den Regelprozess** (Haushalt, 27.10.2026). Was der
Haushalt im Laufe des Jahres nachreicht, nämlich Auszüge und die Mitteilung
einer Police, ist kein Auftrag für die Programmierung. Der Monatsabschluss
fragt beides schon ab: fehlende Auszüge und unter „jährlich“ die vier Werte
einer Mitteilung. Es fehlt ein Hinweis für eine eingelesene Buchung, die zu
einer einmaligen Planzeile passt, ihr aber nicht zugeordnet ist. Diese
Buchung zählt sonst doppelt, einmal gemessen und einmal geplant. Bisher prüft
Opus das von Hand nach dem Import. Künftig sagt es der Abgleich auf
`/planung` oder der Monatsabschluss.

Kleine Umbenennungen dürfen schon mit den Schritten davor kommen; hier wird
der Rest erledigt.

### 7. KI über die Schnittstelle

ADR 0002, in dieser Reihenfolge: erst die Kopiervorlage, dann der
MCP-Zugang mit lokalem Modell, dann eine API nach Wahl. Erst jetzt, weil die
Schnittstelle die Handentscheidungen aus Schritt 1 bis 5 ausdrücken muss.

### 8. Die schlanke Fassung

Basis und Module, Einrichtung ohne Texteditor, ein Paket zum Weitergeben.
Voraussetzung ist, dass die Umbenennungsprobe und der Musterhaushalt zeigen,
dass der Code keinen Einzelfall mehr kennt.

**Die Termine eines Vertrags ohne Aufsummieren** (gefunden in 5b E.8a). Es geht um
`abos.termine` in einem Fenster, das vor `faellig` beginnt und länger als ein Takt ist.
Dort liefert die Funktion nur die Termine ab dem letzten vor `bis`. Heute ruft sie niemand
so auf: Der Treffer-Check fragt je Monat, die Modelle ab heute. Richtig wäre, jeden Termin
als `faellig` plus ein Vielfaches des Takts zu rechnen, statt Schritt für Schritt
weiterzuzählen. Dann verrutscht auch ein Termin am 29. bis 31. nicht mehr, nachdem er
einmal auf einen kurzen Monat gefallen ist. Das kann Tage im Monatsmodell verschieben.
Deshalb ist es ein eigener Schritt mit neuer Referenz.

## Umstieg

**Geschehen am 25.10.2026 (Opus, mit dem Haushalt).** Den ganzen Datenordner
kopiert nach `Finance OS vor Umstieg 2026-10-25`, alle Dateien gleich. Dann
`finctl umstellen`, und das Ergebnis gleicht der Probe vom selben Tag. Danach
liefen `init` (mit dem Nachführen von `einmalig`), `ingest`, `categorize` und
`validate` ohne Fehler, und alle 42 Seiten antworten. Die Policenwerte aus P.2
stehen in `renten.yaml` und `balances.yaml`. Bei myLife sind 2.300 € Honorar
zu „eingezahlt“ addiert, mit einer Notiz an der Position. Die Menüleisten-App
ist aus `main` neu gebaut, und die alte liegt als `Finance OS (alt).app`
daneben. Was unten steht, ist damit erledigt; es bleibt als Anleitung für einen
anderen Ordner.

Wenn Schritt 5 durch ist, kann der Alltag auf `main` wechseln: Der echte
Datenordner wird einmal umgestellt (Sicherung vorher), der Arbeitsbaum
`basis` bleibt zum Nachsehen stehen.

Am besten direkt nach einem Monatsabschluss:
1. Ein paar Tage vorher `finctl umstellen --probe` auf den echten Ordner. Es
   ändert nichts und zeigt im Bericht, wo jeder Kommentar landet.
2. Am Tag des Umstiegs zuerst den ganzen Datenordner kopieren. Die Kopie ist
   die Sicherung und zugleich der Stand, den `basis` weiter lesen kann:
   `basis` versteht den umgestellten Ordner nicht mehr, und zum Nachsehen
   zeigt `FINCTL_DATEN` dort auf diese Kopie.
3. Dann `finctl umstellen`. Es sichert `config/` noch einmal nach
   `archiv/vor_umstellung_<Datum>/` und schreibt den Bericht nach
   `notizen/`.
4. Danach `finctl init`, `finctl ingest run`, `finctl categorize` und
   `finctl validate` (N.4c: so an einer Kopie des echten Ordners geprobt,
   alle 42 Seiten antworten). Einen Befehl `update` gibt es nicht.

Was der Code dabei von selbst nachführt, beim ersten Befehl oder Start der App
mit dem echten Ordner (`finctl/nachfuehren.py`, aus Schritt 4.6): Das
Hauptbuch hat die Spalte `einmalig` schon (seit dem 07.10.2026; ein älteres
bekäme sie beim Start). Kennt `taxonomy.yaml` das Merkmal
nirgends, bekommt Kaufnebenkosten eine Zeile mit `einmalig: true`; die
Kommentare bleiben. Danach werden die Kategorien neu geladen. Von Hand ist nichts zu
tun. Steht die Zeile in einer Form, die sich nicht selbst ändern lässt, sagt
die App es beim Start. Danach auf `/reihen` die Vorschläge zum Zusammenführen
durchsehen, Einmaliges setzen und die beendeten Verträge prüfen.

Von Hand zu übertragen (Schritt 4b), weil die Entwicklungskopie sie nur für
sich hat:
- Je Police `kosten_pa`, `beitrag` und `pruefwert`, nach dem Umstellen an die
  Quelle in `renten.yaml`. `renten_custom.yaml` gibt es danach nicht mehr.
- Im Monatsabschluss Rückkaufswert, eingezahlt, Policenwert laut Mitteilung
  und Stand.

Die Werte stehen in `notizen/policen.md`. Bei einer neueren Mitteilung gelten
deren Werte.

Vor dem Umstieg die echte `szenarien.yaml` prüfen (Schritt 4c, T.1): Eine
Zeile ohne `start` außerhalb der Klammer „Teilzeit“ ist seit T.1 ein Fehler
beim Lesen. `/planung`, `/hochrechnung`, `/konten` und `/ziele` laden dann
nicht. Bisher zählte sie still nichts. Eine solche Zeile bekommt ein Datum
oder wird gelöscht.

Im Bericht der Probe (`finctl umstellen --probe`) die Liste „ausgeblendet“
ansehen (Schritt 5, N.3b und N.3c). Ein Abo, eine Versicherung, ein Kredit oder
ein Objekt, das auf der Seite ausgeblendet ist, steht nach dem Umstieg nicht
mehr in der Datei, nur noch in der Sicherung. Ist einer davon noch gewollt,
vorher wieder einblenden. Im selben Bericht „kein Leser kannte“ ansehen:
Vorlagen und Anschlusskonditionen zu einem Kredit, den es nicht gibt, gehen
nicht mit. Ein Objekt, das nur in `properties_custom.yaml` steht, hat keinen
Namen; daran scheitert `finctl init` schon heute. Es bekommt vorher einen
Eintrag in `properties.yaml` oder wird gelöscht. Ebenso (N.3d): gelöschte
Ziele und gestrichene Verpflichtungen fallen aus der Datei. *Am echten Ordner
geprüft (25.10.2026):* Es gibt genau eine gestrichene Verpflichtung, und der
Haushalt hat bestätigt, dass das Streichen gewollt war. Ein Stand, den
die Seite für ein Konto mit Auszug trug, galt nie und steht danach nur in der
Notiz. Ein Stand zu einer Position, die `balances.yaml` nicht hat, steht unter
„kein Leser kannte“. Dazu, falls es die Seitendateien gibt (N.3e):
- **Regeln:** geänderte mitgelieferte Regeln stehen danach ganz in `rules.yaml`;
  ausgeblendete unter `allgemeine_regeln_aus`. Bei ausgeschalteter Grundschicht
  ist eine Regel der Seite mit der Kennung einer mitgelieferten eine eigene
  Regel ohne Bedingung und fängt jede Buchung. So las es die App schon vorher.
  Steht so eine im Bericht, vorher auf `/regeln` löschen.
- **Konten:** ausgeblendete Konten und ein Wechsel von `ingest_mode` durch die
  Seite.
- **Lebensplan:** Danach zeigt `/einrichtung` dasselbe Geburtsdatum, dieselbe
  Krankenversicherung und dasselbe Rentenalter wie vorher.
- **Sicherung:** Ziel und Zahl der Stände.
- **Einstellungen (N.3f):** Der Umwandler vergleicht die Tabelle `settings` der
  `finance.db` mit `settings_custom.yaml` und hält an, wenn dort eine Zeile,
  ein Wert oder eine Notiz nur in der Tabelle steht. Hält er an, wird jede
  genannte Zeile vorher in die Datei übernommen oder bewusst verworfen.
- **Untergrenze aus dem Kredit:** In `forecast.yaml` trägt jedes
  `floor_from_loan` die Kennung eines Kredits, nicht `true`. Ein Fehler beim
  Speichern der Kontokarte machte daraus `true`, und dann galt die Untergrenze
  aus dem Kredit nicht mehr. `basis` hat den Fehler in älterer Form.

Vor dem Umstieg die echte `loans_custom.yaml` prüfen (Schritt 5, N.1): Bis N.1
schrieb `/api/kredit-anschluss` die Datei nur mit `anschluss` neu. Dabei gingen
die auf `/kredite` angelegten Kredite und Vorlagen verloren. `basis` hat den
Fehler weiterhin. Bis zum Umstieg dort deshalb keine Anschlusskondition
speichern. Fehlen `kredite:` oder `vorlagen:`, die eine ältere Sicherung noch
hat, werden sie aus der Sicherung zurückgeholt. *Geprüft am 25.10.2026 (Opus,
mit dem Haushalt):* Die drei laufenden Kredite stehen alle in `loans.yaml`,
die Vorlage steht in `loans_custom.yaml`. Auf `/kredite` angelegte Kredite gab
es keine. Verloren ist nichts.
