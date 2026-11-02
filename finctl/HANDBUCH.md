# Handbuch — Betrieb ohne KI

Finance OS liest deine Kontoauszüge ein und ordnet jede Buchung zu – lokal
auf deinem Rechner, ohne Cloud und ohne Bankzugang. Daraus entsteht jeden
Monat ein Abschluss: wohin das Geld geht, was Fixkosten sind und was übrig
bleibt. Und der Blick nach vorn: Kredite, Objekte, Anschlussfinanzierungen,
Lebensziele, große Anschaffungen und Urlaube, Rentenlücke – durchgerechnet bis
zum Lebensende, sodass Entscheidungen auf Zahlen beruhen statt auf Gefühl.

Das Werkzeug läuft vollständig ohne Sprachmodell. KI hat die Regeln *geschrieben*;
ausgeführt werden sie von gewöhnlichem Python, deterministisch und offline. Zweimal
laufen lassen ergibt byte-identische Teile — dafür gibt es einen Test.

Dieses Dokument ist die Bedienungsanleitung für den Fall, dass nie wieder ein Modell
beteiligt ist.

Die App rechnet, sie berät nicht. Was sie zu Steuern, Renten und Anlagen sagt, sind
Rechenhilfen ohne Gewähr, keine Steuer- oder Anlageberatung.

---

## 0. Der erste Start

Beim ersten Öffnen steht die **Einrichtung** da, mit leerem Datenordner. Alles bleibt auf
deinem Rechner; die App braucht kein Konto und keine Verbindung zur Bank. Der Weg zur ersten
Auswertung:

1. **Konto anlegen.** Unter „3 — Welche Konten es gibt“ eine Datei aus dem Online-Banking
   wählen und **Erkennen** drücken. Bei der Sparkasse ist es der Auszug als CSV
   („CSV-CAMT V2“). Die App nennt Bank, Konto und Zeitraum; **Neues Konto damit** füllt das
   Formular, **Anlegen** speichert es und legt die Datei im Auszugsordner des Kontos ab.
2. **Sicherung eintragen.** Unter „2 — Wohin gesichert wird“ einen Ordner wählen, am besten
   auf einer externen Platte oder einem USB-Stick. Liegt er in einem Cloud-Dienst, verlässt die
   Sicherung deinen Rechner: sie enthält deine Konfiguration und die Datenbank mit allen
   Buchungen, unverschlüsselt.
3. **Update.** Auf dem **Monatsabschluss** liest **Update** die abgelegten Auszüge ein und
   wendet die Regeln an. Danach steht unter **Buchungen → Offen**, was keine Regel erkannt
   hat; dort die Kategorie wählen. Gemerkt wird jede Entscheidung, auch beim nächsten Update.
4. **Jeden Monat wieder:** den neuen Export im Online-Banking holen, in der Einrichtung bei
   **Erkennen** wählen und im Konto ablegen, **Update** drücken, Offenes zuordnen, **Sichern**.

Angezeigt ist zunächst nur die Basis: Konten, Auszüge, Kategorien und Regeln, Rückblick.
Verträge, Kredite, Objekte, Prognose und Ziele schaltest du unter „5 — Was die App zeigen
soll“ dazu, wenn du sie brauchst; Ausschalten blendet nur aus und löscht nichts. Die Befehle
in den folgenden Abschnitten sind für alle, die lieber im Terminal arbeiten.

---

## 1. Der Monatsablauf

Vier Befehle, in dieser Reihenfolge. Zusammen unter einer Minute.

**Alles hängt am Datenordner.** Darin liegen `config/` und `data/`, die Auszüge
in `data/statements/`, je Konto ein Ordner.
Welcher Ordner das ist, sagt:

```bash
.venv/bin/finctl ort
```

Der Befehl nennt den Ordner **und warum er es ist** — das ist die Auskunft, die man
braucht, wenn plötzlich ein leeres Hauptbuch aufgeht. Es gibt vier Regeln, in dieser
Reihenfolge: die Variable `FINCTL_DATEN`, der eingetragene Ort
(`finctl ort --setzen <ordner>`), ein `config/` im aktuellen Verzeichnis, und sonst
die Vorgabe des Systems (macOS: `~/Library/Application Support/Finance OS`, Windows:
`%APPDATA%\Finance OS`).

Ohne eigene Angabe greift die letzte: der Systemordner. Dann arbeitet `finctl`
von jedem Verzeichnis aus mit denselben Daten, und die Beispiele unten laufen
überall. Wer aus einem Quellcode-Ordner arbeitet, schreibt `.venv/bin/finctl`
statt `finctl`.

### Der schnelle Weg: zwei Knöpfe

Läuft das Dashboard (`finctl serve`), reicht die **Monatsabschluss**-Seite:

| Knopf | was er tut |
|---|---|
| **Update** | Neue Auszüge einlesen, Regeln anwenden, Vorgänge zuordnen, prüfen — die Schritte 2 bis 4 unten |
| **Sichern** | Einen Stand in den Sicherungsordner schreiben |

Beide melden das Ergebnis darunter, inklusive abgelehnter Auszüge und Lücken in
der Auszugskette. Auszüge vorher ablegen (Schritt 1). Die Terminalvariante darunter
tut dasselbe und ist die Rückfallebene, wenn das Dashboard nicht läuft.

**1. Auszüge ablegen.** CSV- oder PDF-Dateien in den Ordner des jeweiligen Kontos, Dateiname egal —
identifiziert wird über den SHA-256 des Inhalts, dieselbe Datei zweimal ablegen
schadet also nicht.

```bash
finctl ort        # der Datenordner; die Auszuege liegen darin unter data/statements/
```

| Konto | Ordner |
|---|---|
| Sparkasse Giro | `data/statements/sparkasse-giro/` |
| Tagesgeld bei einer Bank | `data/statements/tagesgeld/` |

**2. Einlesen.**

```bash
finctl ingest run
```

Ein Auszug wird nur übernommen, wenn `Anfangsstand + Σ Buchungen = Endstand`.
Stimmt das nicht, wird er **abgelehnt**, nicht halb importiert. `rejected 0` ist das
Ziel.

**3. Kategorisieren.**

```bash
finctl categorize
```

Wendet den Regelsatz an. Handentscheidungen werden nie überschrieben.

**4. Prüfen.**

```bash
finctl validate
```

Muss `All invariants hold.` sagen. Meldet es eine Lücke in der Auszugskette, fehlt
ein Auszug — die Kette verlangt, dass der Endstand eines Auszugs der Anfangsstand des
nächsten ist.

**5. Nacharbeiten im Dashboard.**

```bash
finctl serve
```

→ <http://127.0.0.1:8765>, Seite **Buchungen**, Reiter **Offen**. Dort steht, was keine Regel erkannt hat.

Aus dem Paket (`.dmg`, `.exe`) oder mit `finctl app` startet dasselbe Dashboard
auf <http://127.0.0.1:8777>, richtet beim ersten Mal ein und öffnet den Browser.
Beendet wird es dann über **Beenden** oben rechts.

---

## 2. Wo was geändert wird

Alles Dauerhafte steht in `config/` als YAML. Bearbeitbar mit jedem Texteditor; nach
jeder Änderung `finctl categorize` (bzw. `finctl init` bei Stammdaten).

Es gibt **eine Datei je Sache**. Was die Oberfläche einträgt, steht in derselben Datei,
in der du von Hand arbeitest; eine zweite Datei daneben gibt es nicht mehr.

Das **Warum** steht als **Notiz** am Eintrag (`notiz`, dazu `notiz_vom` mit dem Datum der
letzten Änderung), nicht als Kommentar. Eine Einstellung ohne Kennung und eine ganze Datei
tragen ihre Notiz unter `notizen:` ganz unten, mit dem Schlüsselpfad (`kapital.rendite_depot_pa`)
oder `bereich` als Ort. Eine Notiz ohne Datum stammt aus der Zeit vor den Notizen.
Jede Seite, die einen Eintrag zeigt, zeigt auch seine Notiz, aufklappbar und mit dem Datum ihrer
letzten Änderung; fehlt es, steht dort „ohne Datum“. Ein Speichern ohne Änderung macht sie nicht jünger.

**Wer eine Datei von Hand ändert, schreibt das Warum in `notiz` und nicht als `#`-Kommentar.**
Ein neuer Kommentar in einer Datei, die eine Seite hat, gilt als alte Form: Die App hält
beim Start, bei `finctl init` und bei jedem Befehl mit Hauptbuch an und nennt
`finctl umstellen`, das ihn zur Notiz macht. Der Kopf, den die App selbst über eine Datei
schreibt, zählt nicht. Ausgenommen sind vier Dateien, die niemand in der Oberfläche bearbeitet
und deren Kommentare die Form der Datei beschreiben: `server.yaml`, `taxonomy_migrations.yaml`,
`accounts.example.yaml` und `verbotene_namen.yaml`.

| Datei | Wofür | Auch im Frontend? |
|---|---|---|
| `rules.yaml` | Der Regelsatz; auch was auf /regeln angelegt oder geändert wurde | teilweise („Regel ändern") |
| `taxonomy.yaml` | Kategorien, Steuerpositionen, Merkmale `fix` und `einmalig`; auch was im Dashboard angelegt wurde | Kategorien: ja |
| `taxonomy_migrations.yaml` | Umbenennungen und Zusammenlegungen | ja |
| `overrides.yaml` | Deine Handkorrekturen (automatisch geschrieben) | ja |
| `accounts.yaml` | Konten, IBANs, Dispo-Grenzen; auch was in der Einrichtung angelegt wurde | Anlegen: ja |
| `balances.yaml` | Stände der Positionen, Verpflichtungen und der Verlauf je Monat | ja (/monatsabschluss) |
| `abos.yaml`, `versicherungen.yaml` | Verträge mit Betrag, Termin und Notiz | ja (/vertraege) |
| `renten.yaml` | Rentenquellen mit Betrag, Beginn, Stand und Notiz | ja (/renten) |
| `goals.yaml` | Ziele; auch was auf /ziele angelegt oder geändert wurde | ja (/ziele) |
| `properties.yaml` | Objekte, AfA, Kaufdaten, Prognose; auch was im Dashboard angelegt oder eingetragen wurde | teilweise |
| `loans.yaml` | Kredite und Zinsbindungssegmente; auch was auf /kredite angelegt oder eingetragen wurde | teilweise |
| `szenarien.yaml` | Klammern: Verpflichtungen und Pläne | ja (Reiter Planung) |
| **`assumptions.yaml`** | **Alle Annahmen: Inflation, Rendite, Gehaltsfloor** | teilweise |
| `assumptions.optimistisch.yaml`, `assumptions.pessimistisch.yaml` | Alternative Annahmen für `finctl jahre --szenario` | nein |
| `forecast.yaml` | Was fortgeschrieben werden darf; Rolle, Budget und Untergrenze je Konto | Konten: ja (/konten) |
| `lebensplan.yaml` | Geburtsdatum, Krankenversicherung, Rentenalter | ja (/einrichtung) |
| `backup.yaml` | Sicherungsziel und Zahl der Sicherungen | ja (/einrichtung) |
| `strom.yaml`, `energie.yaml` | Zähler, Ablesungen und Vorräte | ja (/energie) |
| `groups.yaml` | Vorgänge | nein |
| `adjustments.yaml` | Korrektur eines falsch gedruckten Stands | nein |
| `server.yaml` | Adresse und Anmeldung (`finctl passwort`) | nein |

Sechs Dateien tragen `_custom` im Namen, weil es zu ihnen keine Basisdatei gab, und
behalten ihn: `reihen_custom.yaml` (Takt einer Reihe, einmalig gesetzte Buchungen,
zusammengeführte Schreibweisen; /reihen), `geteilt_custom.yaml` (Themenkassen, Beteiligte, zugeordnete
Buchungen), `zinssaetze_custom.yaml` (datierte Zinssätze je Konto, auf /annahmen) und
`prognosebasis_custom.yaml` (was unter Fortschreibung abgewählt ist, auf /prognosebasis),
`module_custom.yaml` (welche Module an sind) und `csv_profile_custom.yaml` (selbst
zugeordnete CSV-Exporte), beide in der Einrichtung. Eine Datei aus der Zeit davor, die noch
`*_custom.yaml` heißt und zu einer der Dateien oben gehört, stellt
Abschnitt 2b („Umstieg auf Notizen“) um.

**`assumptions.yaml` ist die einzige Stelle für eine Annahme.** Alles, was die
Prognose rechnet, kommt von dort: die Inflationsrate von 2 %, die nominale Rendite,
der Gehaltsfloor. Fakten stehen woanders — ein Kreditzins steht in `loans.yaml`, eine
AfA-Basis in `properties.yaml`, ein Policenwert in `balances.yaml`, jeweils mit
der Notiz, die sagt, woher er kommt. Die Trennung ist der Zweck: ein Vertrag ist nicht verhandelbar,
eine Annahme schon.

Ein **Szenario ist eine Kopie dieser Datei** mit anderen Werten, zum Beispiel
`config/assumptions.pessimistisch.yaml`; `finctl jahre --szenario <datei>` rechnet damit
neben der Basis. Kein Knopf, keine Tabelle, keine Oberfläche — eine Datei.

**`overrides.yaml` ist deine Versicherung.** Jede Handkorrektur wird dort über den
`dedup_hash` der Buchung festgehalten, nicht über die ID. Die Datenbank darf also
jederzeit gelöscht und aus den PDFs neu gebaut werden — deine Entscheidungen kommen
zurück. (Genau das ist einmal schiefgegangen, bevor es diese Datei gab.)

### Die Form der Startdateien

Was `finctl init` anlegt, ist bewusst knapp. Die Regeln dahinter:

- **Beträge in Cent**, negativ ist Geld raus. Eine Annahme steht nur in `assumptions.yaml`.
- **Kategorien** (`taxonomy.yaml`): `kind` ist `income`, `expense`, `transfer` oder
  `neutral`. Das Vorzeichen trägt die Richtung, die Kategorie den Zweck: Eine Erstattung
  gehört in die Kategorie der Ausgabe, die sie ausgleicht, als positiver Betrag.
- **Ziele** (`goals.yaml`): `cents` ist nominal zum `stichtag`, ohne Datum läuft das Ziel;
  `basis` verengt, woran gemessen wird. Der Notgroschen `tagesgeld-puffer` ohne Betrag gilt
  das Dreifache der Gehalts-Untergrenze. Die Rentenlücke wird gerechnet, nicht eingetragen.
- **Vorgänge** (`groups.yaml`): `von` ist Pflicht, `bis` fehlt, solange der Vorgang läuft.
  Eine Buchung gehört zu höchstens einem Vorgang, die erste passende Gruppe gewinnt.
- **Bestände** (`balances.yaml`): `kind: auszug` liest den Stand aus dem Kontoauszug,
  `kind: getippt` trägt ihn der Monatsabschluss ein.
- **Lebensplan** (`lebensplan.yaml`): Ohne Geburtsjahr wird keine Altersschwelle ein Datum.

---

## 2b. Umstieg auf Notizen

Wer einen Datenordner aus der Zeit vor den Notizen hat, stellt ihn **einmal** um. Das
erkennst du an zwei Dingen: Kommentare in `config/` statt Notizen, und je Sache zwei
Dateien, eine von Hand und eine (`*_custom.yaml`), die die Oberfläche schrieb. Ein neuer
Haushalt braucht diesen Abschnitt nicht.

Bis es geschehen ist, hält die App an: Sie liest diese Form nicht mehr und liest auch nicht
still nur die halben Werte. Beim Start, bei `finctl init` und bei jedem Befehl mit Hauptbuch
nennt sie, welche Dateien noch umzustellen sind, und die Befehle dafür. `config/` bleibt dabei
unberührt. Der Umstieg ändert keinen Betrag, kein Datum und keine Buchung; verschoben werden
nur die Begründungen und die Dateien.

Am besten direkt nach einem Monatsabschluss.

### Ein paar Tage vorher: ansehen

```bash
finctl umstellen --probe ~/umstieg-probe
```

Der Ordner muss außerhalb des Datenordners liegen. Der Befehl ändert im Datenordner nichts:
Er schreibt eine umgewandelte Kopie von `config/` nach `~/umstieg-probe/config` und einen
Bericht nach `~/umstieg-probe/umstellung_<Datum>.md`. Im Terminal steht, wie viele Dateien
umgewandelt und welche Paare zusammengelegt würden. Gibt es nichts umzustellen oder scheitert eine
Prüfung, schreibt er keine Kopie, wandelt nichts um und sagt, warum.

Im Bericht stehen zuerst die Paare, je eines unter „Zusammengelegt: …“, danach die
Kommentarzeilen je Datei, was wegfällt und jeder Kommentar mit seinem neuen Ort. Bei den Paaren
lohnen vier Stellen:

- **„Ausgeblendet gewesen …“:** Ein Abo, eine Versicherung, ein Kredit, ein Objekt, ein Ziel
  oder eine Verpflichtung, die auf der Seite ausgeblendet oder gestrichen war, steht nach dem
  Umstieg nicht mehr in der Datei, nur noch in der Sicherung; die Notiz steht in der Notiz des
  Bereichs. Ist einer davon noch gewollt, blende ihn vorher wieder ein.
- **„… die kein Leser je las …“:** Einträge der Seite, die die App nie gelesen hat, etwa eine
  Vorlage oder Anschlusskondition zu einem Kredit, den es nicht gibt, oder ein Stand zu einer
  Position, die `balances.yaml` nicht kennt. Sie galten nie, gehen nicht in die neue Datei und
  bleiben in der Sicherung. Was du davon willst, trägst du nach dem Umstieg ein.
- **„Basiswerte, die die Seite …“:** Wo die Seite einen Wert der Handdatei ersetzt hatte, gilt
  weiter der Wert der Seite. Der ersetzte Wert steht am Ende der Notiz („Bis zur Umstellung
  stand in der Datei: …“). Prüfe, dass gilt, was du erwartest.
- **„Notizen, die zusammentrafen …“:** Hatten Handdatei und Seite beide eine Notiz zu einem
  Eintrag, steht jetzt eine: erst die der Handdatei, nach einer Leerzeile die der Seite. Streich
  darin, was doppelt ist oder von einer Datei spricht, die es nicht mehr gibt; das tut die
  Umwandlung nicht für dich.

Unter „Was die Seite brachte“ stehen Einträge, die es nur auf der Seite gab; sie stehen danach
in der Hauptdatei. Ein Objekt, das so ohne Namen angelegt war, lädt `finctl init` nicht: Es
bekommt vorher einen Namen in `properties.yaml` oder wird gelöscht.

Unter „Weggefallen“ stehen die Köpfe, die die App selbst über ihre Dateien schrieb, und
Kommentare, die nur den Wert in Euro wiederholen. Alles andere steht als Notiz da.

### Was jeder Haushalt vorher prüft

- **`szenarien.yaml`:** Eine Zeile ohne `start` außerhalb der Klammer für die Teilzeit ist ein
  Fehler beim Lesen; `/planung`, `/hochrechnung`, `/konten` und `/ziele` laden dann nicht.
  Sie bekommt ein Datum oder wird gelöscht.
- **Untergrenze aus dem Kredit:** In `forecast.yaml` trägt jedes `floor_from_loan` die Kennung
  eines Kredits, nicht `true`. Ältere Fassungen machten beim Speichern der Kontokarte daraus
  `true`; dann gilt die Untergrenze aus dem Kredit nicht mehr. Die Kontokarte zeigt ein solches
  `true` als „kein Kredit gewählt“ und bietet die Kredite aus `loans.yaml` zur Wahl an.
- **Kredite:** Ältere Fassungen löschten beim Speichern einer Anschlusskondition auf
  **Kredite** die dort angelegten Kredite und Vorlagen. Fehlen welche, die eine ältere Sicherung
  noch hat, hol sie dort zurück. Bis zum Umstieg speicherst du mit der älteren Fassung keine
  Anschlusskondition mehr.
- **Regeln** (nur wenn es die Seitendatei gibt): Eine mitgelieferte Regel, die du geändert
  hattest, steht danach ganz in `rules.yaml`; spätere Verbesserungen der App erreichen sie
  nicht. Eine ausgeblendete steht unter `allgemeine_regeln_aus`. Ist die Grundschicht
  ausgeschaltet und eine Regel der Seite trägt die Kennung einer mitgelieferten, ist sie eine
  eigene Regel ohne Bedingung und fängt jede Buchung. So las es die App auch vorher. Steht
  „Regel, in der Seite angelegt“ im Bericht, lösch sie vorher auf /regeln.
- **Konten:** ausgeblendete Konten und ein Wechsel des Einlesens (`ingest_mode`), den die
  Seite vorgenommen hatte.
- **Lebensplan, Sicherung:** Danach zeigt die Einrichtung dasselbe Geburtsdatum, dieselbe
  Krankenversicherung, dasselbe Rentenalter, dasselbe Sicherungsziel und dieselbe Zahl der
  Stände wie vorher.
- **Stände zu Konten mit Auszug:** Ein Stand, den die Seite für ein Konto mit Auszug trug, galt
  nie und steht danach nur in der Notiz.

### Wenn der Abgleich der Tabelle `settings` anhält

Ältere Fassungen legten die Untergrenze je Konto (`floor_cents:<konto>`) und eine Notiz dazu
zusätzlich in der Tabelle `settings` der Datenbank ab. Vor jedem Lauf, auch bei `--probe`,
vergleicht `finctl umstellen` sie mit der Datei der Einstellungen. Er
**wandelt nichts um**, nennt jede Zeile („Tabelle settings, Zeile …“) und beendet sich mit einem
Fehler, wenn

- die Tabelle eine Zeile hat, die die Datei nicht hat,
- ihr Wert abweicht und die Zeile neuer ist als die Datei, oder
- eine Notiz der Tabelle in keiner Notiz der Datei steht.

Die App hält aus demselben Grund an. Ist die Datei neuer als die Zeile, gilt die Datei, und der
Bericht nennt es.

Was du behalten willst, trägst du in der Datei ein: den Wert unter `einstellungen:`, die Notiz
unter `notizen:`. Danach läuft der Befehl durch. Was du nicht willst, verwirfst du mit
`finctl umstellen --tabelle-verwerfen`; der Bericht hält fest, was dabei wegfällt. Nach dem
Umstellen ist die Tabelle aus der Datenbank entfernt. SQL brauchst du dafür nicht.

### Am Tag selbst

**1. Kopieren.** Die App beenden und den **ganzen Datenordner kopieren** (`finctl ort` zeigt,
welcher es ist), mit `config/`, `data/` und den Auszügen darin. Die Kopie ist die Sicherung und
der Stand, den die ältere Fassung der App weiter lesen kann: Sie versteht den umgestellten
Ordner nicht mehr, und zum Nachsehen zeigt `FINCTL_DATEN` dort auf die Kopie.

**2. Umstellen.**

```bash
finctl umstellen
```

Der Befehl sichert `config/` noch einmal nach `archiv/vor_umstellung_<Datum>/`, wandelt die
Dateien um, legt die Paare zusammen, entfernt die Seitendateien und schreibt den Bericht nach
`notizen/umstellung_<Datum>.md`. Ein zweiter Lauf ändert nichts und meldet „Nichts
umzustellen“.

**3. Danach, in dieser Reihenfolge.**

```bash
finctl init
finctl ingest run
finctl categorize
finctl validate
```

Einen Befehl `update` gibt es nicht. `init` gleicht die Datenbank an die Dateien an, wo sie
älter ist (zum Beispiel den Namen des Auszugsprofils eines Kontos). `ingest run` findet nichts
Neues, solange kein neuer Auszug dazukam, `categorize` wendet deine Handentscheidungen wieder
an, `validate` sagt `All invariants hold.`

**4. Die Seiten durchsehen.** Beträge, Stände und Prognosen müssen dieselben sein wie vor dem
Umstieg; die Texte können sich ändern. Weicht eine Zahl ab, lies mit der Kopie aus Schritt 1
nach.

### Was beim ersten Befehl von selbst nachgeführt wird

Der erste Befehl oder Start mit dem neuen Code führt nach, was der Code seither neu kennt. Du
tust nichts dafür:

- Dem Hauptbuch fehlt die Spalte `einmalig` bei den Kategorien: Sie wird angelegt.
- Kennt `taxonomy.yaml` das Merkmal `einmalig` nirgends, bekommt die Kategorie
  Kaufnebenkosten unter Immobilie die Zeile `einmalig: true`. Terminal oder Start melden
  „Nachgefuehrt: config/taxonomy.yaml: …“; die Notizen bleiben. Danach werden die Kategorien
  neu geladen. Steht die Zeile in einer Form, die sich nicht selbst ändern lässt, nennt die
  Meldung sie, und du ergänzt sie von Hand.

Danach auf [/reihen](#reihen) die Vorschläge zum Zusammenführen durchsehen, Einmaliges setzen
und die beendeten Verträge prüfen.

---

## 3. Eine Regel selbst schreiben

`config/rules.yaml`, aufsteigende Priorität, **die erste passende Regel gewinnt**.
Textvergleich ignoriert Leerzeichen und Satzzeichen vollständig — `WEG Musterstr`
trifft auch, wenn das PDF `WEG Muster str.` gerendert hat.

```yaml
  - id: mein-fitnessstudio
    priority: 30
    name: Fitnessstudio
    match: {text: ["FitX", "McFit"]}
    set: {mgmt: konsum/fitness, tax: privat/nicht-abzugsfaehig}
```

**Matcher:** `text` (ODER-Liste), `text_all` (UND), `regex`, `counterparty`, `iban`,
`iban_is_own`, `account`, `tx_type`, `sign`, `amount_between`, `amount_abs_between`,
`date_from`, `date_to`, `any_of`, `all_of`, `none_of`

**Aktionen:** `mgmt`, `tax`, `property`, `loan`, `transfer_account`, `note`

### Eine Buchung in Teile zerlegen

```yaml
    split:
      - {amount: 9.00,  mgmt: wohnen/gez}
      - {amount: 27.00, mgmt: wohnen/internet}
      - {mgmt: wohnen/miete}      # letzter Eintrag nimmt den Rest
```

Der letzte Eintrag ohne Betrag bekommt die Differenz, damit die Teile **immer** exakt
auf die Buchung aufgehen. Alternativ `pct:` statt `amount:`.

Eine Teilung, die du im Dashboard machst, gilt nur für die eine Buchung. Eine Regel mit
`split:` gilt für alle — vergangene wie künftige.

### Zwei Fallen, die schon zugeschlagen haben

**Namen.** `squash()` entfernt Leerzeichen. „Erika Mustermann" ist deshalb **kein**
Teilstring von „Erika Maria Mustermann". Drucken die Auszüge zwei Schreibweisen, müssen
beide in die Liste.

**Präfixe.** Ein Blattknoten wird exakt verglichen, eine Oberkategorie als Präfix.
`einkommen/gehalt` als Präfix hätte auch `einkommen/gehalt-nebentaetig` gefangen.

---

## 3b. PayPal auflösen

Eine PayPal-Buchung kommt auf dem Auszug als „PayPal Europe S.a.r.l." an —
ohne Händler, ohne Gegenpartei, ohne Grund. Das ist der Grund, warum diese Buchungen am
längsten unkategorisiert bleiben.

PayPal-Export ziehen (Aktivitäten → Berichte → Kontoauszüge, CSV), dann:

```bash
finctl paypal ~/Downloads/<export>.CSV --year 2025
```

Das nennt zu jeder offenen Buchung die Gegenpartei und schlägt eine Kategorie vor —
aus **deinen eigenen früheren Entscheidungen** zur selben Gegenpartei, nicht geraten.

**Es schreibt nichts.** Wofür eine Buchung an einen Freund war, steht in keiner der
beiden Dateien — dieselbe Gegenpartei ist einen Monat Gastronomie und den nächsten
Geschenke. Zuordnen im Dashboard oder mit `finctl split`.

---

## 4. Steuer

Reiter **Steuer**. Sortiert nach Anlage → Position → Objekt, also in der Form der
Formulare, nicht des Haushaltsbuchs. Jede Zeile führt über **Belege →** auf die
Buchungen dahinter.

Ablauf für eine Erklärung:

1. Jahr wählen.
2. Die rote Warnung **„n Buchungen ohne Steuerposition"** abarbeiten. Die stehen im
   Ledger, tauchen aber in keiner Anlage auf — die Fehlerart, die am spätesten
   auffällt, weil jede Haushaltssumme trotzdem stimmt.
3. Bei Anlage V prüfen, ob jede Zeile ein Objekt trägt. `⚠ ohne Objekt` ist ein
   Fehler: Anlage V ist ein Formular **pro Objekt**.
4. Beträge nach WISO übertragen.
5. **AfA steht bewusst nicht auf dieser Seite.** Sie kostet kein Geld und steht in
   keinem Auszug. Sie kommt aus `properties.yaml` und ist unter **Objekte**
   sichtbar.

In der Tabelle der Buchungen filtert das Feld **Steuer** auf derselben Achse,
mehrfach wählbar. `— ohne Steuerposition —` findet genau die Lücken aus Schritt 2.

---

## 5. Prognose und Allokation

Reiter **Prognose**.

Fortgeschrieben wird in zwei Teilen. Eine Reihe mit festem Takt ([/reihen](#reihen)) —
Miete, ein Vertrag, eine Jahresprämie, die Grundsteuer im Quartal — steht als eigener Posten
mit ihrem **Betrag je Termin** an ihrem Termin, nicht auf Zwölftel geglättet, damit die
Dispo-Warnung die richtige Talsohle sieht. Eine Reihe, deren nächster Termin lange
überfällig ist, ist beendet und kommt nicht mehr vor; ein Dauerauftrag, der das Konto
gewechselt hat, ist auf dem alten beendet und läuft auf dem neuen. Alles, was in keiner Reihe steht
(ein Wocheneinkauf, eine Nachzahlung neben dem Abschlag), wird als **Summe der letzten
zwölf Monate durch zwölf** fortgeschrieben, auf dem Konto, auf dem gemessen wurde, flach —
heutige Preise, keine Indexierung. Dasselbe Fenster misst die Hochrechnung. Das Gehalt hat seine eigene Quelle, die
Untergrenze aus den Annahmen.

Nicht fortgeschrieben: Kredite (die kommen aus dem Tilgungsplan in `loans.yaml` und
steigen deshalb korrekt bei Ablauf der Zinsbindung), Projektausgaben und
Vermögensumschichtungen.

Die Spalten **in Puffer** / **investierbar** / **kumuliert** sind **keine**
Vermögensprognose. Sie sagen nur, wie viel freier Cashflow in dem Monat allokierbar
ist, in der Reihenfolge aus `goals.yaml`: erst Tagesgeld bis zum Ziel, dann frei fürs
Depot. Es gibt bewusst keine Sparrate einzutragen — die Rate *ist* der Überschuss.
Was der Broker daraus macht, steht hier nicht.

---

## 6. Sicherung

```bash
finctl backup
```

Oder der Knopf **Sichern** auf der Monatsabschluss-Seite.

Ziel und Anzahl der aufbewahrten Stände stehen in **`config/backup.yaml`**, eingetragen
in der Einrichtung:

```yaml
directory: ~/Sicherung/finance-os      # ein Ordner deiner Wahl, gern in einer Cloud
keep: 12
```

Ältere Stände werden beim Schreiben gelöscht. `--to` überschreibt das Ziel einmalig.

Enthalten ist der **Datenordner, und nur der**: die Datenbank als SQL-Dump, die
komplette `config/`, die Versionen, mit denen es lief (`requirements.lock`), und ein
Blatt `stand.yaml`, das erklärt, was fehlt und wie man zurückkommt. Meist unter
einem Megabyte.

**Nicht enthalten ist der Quellcode** — das Programm kommt aus der Installation.
Das trennt, was du entschieden hast, von dem, womit du es aufgeschrieben hast.

**Nicht enthalten sind die Kontoauszüge.** Sie würden das Archiv vervielfachen;
bewahre sie dort auf, wo du sie ohnehin ablegst. Aus Auszügen und `config/` lässt
sich das Hauptbuch jederzeit neu bauen (unten).

In der App: Einrichtung → **Aus einer Sicherung wiederherstellen**. Die Sicherung
landet in einem neuen Ordner neben dem bisherigen, und **Diesen Stand verwenden**
schaltet ab dem nächsten Öffnen um. Der alte Ordner bleibt unverändert.

Im Terminal sieht die Wiederherstellung so aus — App installieren, Archiv einlesen:

```bash
.venv/bin/finctl restore <archiv>.tar.gz --to ~/finance-wieder
```

Das packt aus, baut `data/finance.db` aus dem Dump und sagt, was drin war. Danach
bekommt das Programm den Ordner genannt, und dann wird geprüft:

```bash
.venv/bin/finctl ort --setzen ~/finance-wieder && .venv/bin/finctl validate
```

`restore` schreibt nie in eine bestehende Installation: das Ziel muss leer sein.
Sonst wäre der erste Versuch einer Wiederherstellung der Moment, in dem der letzte
gute Stand verloren geht.

Oder ohne den Dump, allein aus Auszügen und Konfiguration:

```bash
finctl init && finctl ingest run && finctl categorize && finctl validate
```

---

## 7. Wenn etwas nicht stimmt

| Symptom | Ursache | Abhilfe |
|---|---|---|
| `rejected` beim Einlesen | Saldo geht nicht auf | Der Auszug bleibt draußen. Parser prüfen, oder Sonderfall in `adjustments.yaml`. |
| `gap on <konto>` | Auszug fehlt in der Kette | Fehlenden Auszug nachlegen. |
| Viele Buchungen unter Offen | Neue Gegenpartei | Regel schreiben oder im Dashboard einzeln zuordnen. |
| „Regeln, denen du widersprichst" | Dieselbe Regel oft korrigiert | Die Regel ist falsch. Knopf **Regel ändern** oder `rules.yaml` bearbeiten. |
| Kategorie verschwunden | Umbenannt ohne Migration | Eintrag in `taxonomy_migrations.yaml` unter `remap:`. |
| `command not found: finctl` | Nicht installiert oder nicht im Pfad | `uv tool install` bzw. `pipx install` erneut, oder aus dem Quellcode-Ordner `.venv/bin/finctl`. |
| `Kein config/ unter …` oder ein leeres Hauptbuch | Der falsche Datenordner | `finctl ort` zeigt, welcher es ist und warum. Stimmt er nicht: `finctl ort --setzen <ordner>`. |
| Zahl ändert sich nach `init` | YAML überschreibt | So gewollt: YAML gewinnt, wo es etwas sagt. |
| „… ist noch nicht umgestellt“ beim Start oder bei einem Befehl | Eine Datei trägt noch Kommentare, alte Feldnamen oder eine zweite Datei (`*_custom.yaml`) | `finctl umstellen --probe <ordner>` ansehen, dann `finctl umstellen`. Siehe Abschnitt 2b. |
| `finctl umstellen` schreibt nichts und nennt „Tabelle settings, Zeile …“ | Die Tabelle kennt einen Wert oder eine Notiz, die in keiner Datei steht | Zeile in die Datei übernehmen oder mit `finctl umstellen --tabelle-verwerfen` verwerfen. Siehe Abschnitt 2b. |

Nichts wird automatisch umgeschrieben. Der Regelsatz ändert sich nur, wenn du ihn
änderst — auch dann nicht, wenn du derselben Regel vierzigmal widersprochen hast. Sie
wird dir gemeldet, nicht heimlich korrigiert.

---

## 8. Tests

```bash
.venv/bin/python -m pytest -q                  # alles, vor jedem Commit
.venv/bin/python -m pytest -q -m "not langsam" # schnelle Runde, Sekunden
```

Alles läuft parallel auf allen Kernen und **in einer Kopie der Daten**: jeder
Testprozess legt `config/` und `data/` in einen Wegwerfordner und arbeitet dort.
Ein abgebrochener Lauf hinterlässt deshalb nichts in den echten Dateien, und ein
laufendes Dashboard sieht keine Testzahlen. Einen einzelnen Test ohne Parallelstart:
`-n 0 tests/test_x.py::test_y`.

Darunter: der Tilgungsplan gegen das Forward-Angebot einer Bank auf den Cent, die
Reconciliation-Schranke, dass zweimaliges Kategorisieren identische Splits ergibt,
und der **Referenzstand** (`tests/referenz.py`): ein Neuaufbau aus `config/` und den
Auszügen muss Hauptbuch und jede Seite Zeile für Zeile so ergeben wie festgehalten.
Rot heißt: nicht committen.

---

## 9. Was die Seiten zeigen

Je Seite: welche Frage sie beantwortet, wie ihre Spalten zu lesen sind und
welche Falle es dort gibt. Der Konfigurationsfuß jeder Seite verlinkt hierher.
Wie gerechnet wird, steht in Abschnitt 5.

### /monatsabschluss

Was am Monatsanfang zu tun ist, in der Reihenfolge, in der es Sinn ergibt — plus die
Kennzahlen des laufenden Jahres.

- **Die Seite hakt sich selbst ab.** Eine Zeile ist erledigt, wenn die Daten es belegen:
  ein Auszug, der den Vormonat abdeckt, oder ein Stand aus diesem Monat. Ein Haken zum
  Anklicken wäre eine Behauptung neben den Daten, die falsch werden kann, ohne aufzufallen.
- **Konten, Depots, Rentenquellen stehen je als eine Zeile** mit Haken, Stand und Notiz —
  geprüft und gepflegt an derselben Stelle. Einzelheiten unter
  [Stände](#monatsabschluss-konten-depots-renten).
- **Rot steht nur dort, wo etwas klemmt.** Eine Seite, auf der alles leuchtet, liest man
  nach dem zweiten Monat nicht mehr.
- Die **Sicherung** kommt zum Schluss: es soll den Stand sichern, den du gerade durchgesehen
  hast, und nicht den davor.
- Die **Wirkung auf deine Ziele** zeigt, wie weit sich jedes Ziel gegenüber dem Vormonat
  bewegt hat und warum. Einzelheiten unter
  [Wirkung](#monatsabschluss-wirkung-auf-die-ziele).

### /monatsabschluss — Konten, Depots, Renten

Je Position eine Zeile. Aktuell ist sie, wenn die Daten es belegen, sonst steht ein
rotes ○ davor und sie zählt oben bei „offen" mit.

| Gruppe | Woher | Aktuell, wenn … |
|---|---|---|
| Konten | aus dem Auszug, nicht änderbar | der Auszug den Vormonat abdeckt |
| Depots (auch Krypto) | getippt | der Stand aus dem laufenden Monat ist |
| Rentenversicherungen | getippt, nach der Standmitteilung | der Stand aus dem laufenden Jahr ist |
| Renten laut Mitteilung | getippt, nach Renteninformation und Standmitteilung | das Schreiben aus dem laufenden Jahr ist |

- **Der Stand eines Kontos** ist der am letzten Monatsende, das alle Auszüge abdecken —
  derselbe Stichtag, an dem die Kontenvorschau beginnt. Wie weit der neueste Auszug
  reicht, steht als Beleg daneben.
- **Getippte Stände** werden genannt, nicht gemessen, und brauchen genau deshalb diesen
  Ort: ein Depotwert, der nur in einer Datei änderbar ist, ist bald still falsch, während
  der Zielfortschritt darauf weiter präzise aussieht.
- **Unverändert** legt denselben Stand mit heutigem Datum ab, ein Klick. Wer tippt, dessen
  Knopf heißt „Speichern"; ein neuer Stand zieht das Datum auf heute, solange du es nicht
  selbst setzt. Das Datum gehört zu jedem Stand: ein alter Bestand, der sagt, wann er alt
  ist, bleibt benutzbar.
- **Die Notiz** ist bei jeder Position änderbar, auch bei Konten: dass ein Teil des
  Stands jemand anderem gehört, steht in keinem Auszug. Gespeichert wird die
  ganze Position in `balances.yaml`; eine leere Notiz löscht sie samt Datum.
- **Renten laut Mitteilung** stehen hier nur zur Prüfung, ob das Schreiben aus diesem
  Jahr ist. Gepflegt werden sie unter [Rentenquellen](#renten).
- **Rückkaufswert** (nur Rentenversicherungen): Unter der Zeile der Police stehen die
  Angaben der Standmitteilung — Rückkaufswert, eingezahlte Beiträge, ihr Policenwert und der
  Stand. Sie gehen zusammen weg. Daraus rechnet [Konten](#konten) den Notfallwert; das Feld
  „Policenwert laut Mitteilung“ darf leer bleiben, solange es denselben Stand hat wie die
  Zeile.
- **Position anlegen:** Ein Depot, Krypto, Tagesgeld oder eine Rentenversicherung gehört zu einem
  Konto ohne Auszug. Das Konto legst du zuerst in der Einrichtung an; hier trägst du Art, Stand,
  Stichtag und Notiz ein. **Entfernen** nimmt die Position samt Notiz und Verlauf aus
  `balances.yaml`; das Konto bleibt.
- **davon Gewinn** (nur Depots): wie in der Depot-App. Die Hochrechnung versteuert ihn
  beim Verkauf; leer gilt der ganze Wert als Einstand.
- **Verbindlichkeiten** werden hier nicht gepflegt. Geld, das jemand anderem gehört,
  steht als Verpflichtung in der [Planung](#planung). Was noch in `balances.yaml` steht,
  zieht weiter ab; die Seite nennt es, bis es gestrichen ist. Streichen nimmt die Notiz mit.

### /monatsabschluss — Wirkung auf die Ziele

Der Abschnitt vergleicht zwei Hochrechnungen: die von heute und die zum Stichtag davor, jede
nur mit den Buchungen bis zu ihrem Stichtag. Annahmen, Ziele und Planzeilen gelten für beide,
wie sie heute stehen: Die Wirkung zeigt, was die Buchungen bewegt haben, nicht was du
umgestellt hast. Gemessen wird der Wert am Stichdatum des Ziels, im Schnitt und im Tempo der
letzten drei Monate.

- **Die Ursachen** ergeben zusammen genau die Bewegung: „Der Monat" (was er anders brachte als
  erwartet), „Tempo" je Bereich, „Gehalt", „Planzeilen".
- **Tempo** nennt die Kategorien, deren Jahreswert sich geändert hat, mit dem Monat, der aus
  dem Zeitraum fiel, und dem, der dazukam, je mit Betrag und Zahl der Buchungen. So siehst du,
  ob sich ein Betrag geändert hat oder nur ein Buchungstag über das Monatsende gerutscht ist.
  Das Urteil trifft die Seite nicht. Wo eine Buchung zu einer [Reihe](#reihen) mit festem Takt
  gehört, nennt die Zeile die Reihe, die sich bewegt hat — begonnen, beendet oder ein anderer
  Betrag je Termin —, und dazu den Rest mit seinen Monaten; ein Buchungstag, der über das
  Monatsende rutscht, bewegt keine Reihe.
- **Der Monat** hat Hinweise in Euro des Monats: Prognose gegen Ist und die Kursbewegung der
  Depots. Sie gehören nicht zur Wirkung, denn die läuft bis zum Stichdatum weiter.
- **Der Verlauf** hält fest, was am Monatsabschluss stand. Für den Stichtag davor braucht
  die Seite den Stand jeder getippten Position von damals; jedes Speichern eines Stands legt
  ihn in `balances.yaml` unter `verlauf` ab, je Monat einen, bei einer
  Rentenversicherung je Jahr. Gilt zweimal derselbe Monat, zählt der spätere. Das erste
  Speichern legt den Verlauf an.
- **Fehlt ein Stand von damals**, nennt der Abschnitt ihn und sagt, ab wann es einen Vergleich
  gibt. Das gilt auch für einen Stand, der im Monat nicht neu abgelegt wurde, obwohl er galt.

### /konten

Je Konto der **Tiefpunkt innerhalb des Monats** („nach Kosten"): Kosten kommen am
Monatsanfang, das Gehalt am Ende, und der Monatsendstand verbirgt genau die Delle, um
die es geht. Die Kennzahl oben sagt, ob der Haushalt sich ohne das große Objekt trägt —
ohne Umbuchungen zwischen eigenen Konten, ohne Kaufraten, ohne Investments.

- **Zufluss** ist ein deklarierter Dauerauftrag, kein gemessener Wert, sondern eine
  Entscheidung.
- **Deckel** gibt es nur beim Betriebskonto: Guthaben dort wird nicht verzinst, alles
  darüber gehört aufs Tagesgeld. **Abräumen** ist deshalb ein Auftrag, kein Befund.
- Die **Reihenfolge ist die Regel**: erst auffüllen, was unter seine Grenze fiele, dann
  erst den Rest aufs Tagesgeld. Sonst würde gespart, während ein Girokonto im Dispo steht.
- **Bewusst pessimistisch**: Kosten ohne Tag zählen früh, Einnahmen spät, das Gehalt mit
  seiner Untergrenze.
- Eine Buchung gilt nur als gedeckt, wenn die Umbuchung dorthin datiert dasteht. Sonst
  sieht das Konto den Abfluss ohne den Zufluss.
- **Untergrenze aus einem Kredit**: eine Monatsrate des gewählten Kredits.
- Der **Notgroschen** (Ziele) ist die Untergrenze des Tagesgeldkontos, wenn er höher liegt;
  eine Klammer, die ihn angreift, löst die Warnung aus.
- **Policen im Notfall**: Rückkaufswert nach Steuer, nur zur Anzeige; „mind.“: eingezahlt fehlt.

### /einrichtung

Was gesetzt sein muss, in der Reihenfolge, in der es Sinn ergibt, und welche Module
an sind.
Solange etwas offen ist, weist der [Monatsabschluss](#monatsabschluss) darauf hin —
ohne Umleitung.

- **Erledigt entscheiden die Daten,** nicht ein Haken. Ein Zeiger auf einen
  Datenordner, ein eingetragenes Sicherungsziel, mindestens ein Konto, ein Geburtsdatum.
- **1 Wo die Daten liegen.** Zuerst, weil alles andere dorthin geschrieben wird. Der
  Eintrag **verschiebt nichts** und gilt ab dem nächsten Start; welcher Ordner gilt,
  sagt auch `finctl ort`.
- **2 Wohin gesichert wird.** Vor den Konten, weil ab dem ersten Import etwas da ist,
  das verloren gehen kann. Geprüft wird durch Schreiben.
- **3 Welche Konten es gibt.** Ohne Konto kein Import, ohne Import kein Hauptbuch.
  Über der Maske steht das Register aller Konten, siehe
  [Konten](#einrichtung-konten).
- **4 Wer plant.** Geburtsdatum, Krankenversicherung, Rentenalter. Daraus werden
  Rentenbeginn und, nur bei privater Versicherung, die Frist für die Rückkehr in die
  GKV.
- **5 Was die App zeigen soll.** Die Basis ist immer an, Module schaltet man dazu.
  **Aus heißt ausgeblendet**, nicht gelöscht.
- **6 Eigene Angaben** listet, was du durch deine eigenen Zahlen ersetzt, mit Seite,
  Datei und Stand.

### /einrichtung — Konten

Welche Konten es gibt — die Stammdaten, nicht die Prognose. Getrennt von
[Konten](#konten), weil es zwei Fragen sind: dort der Tiefpunkt im Monat, hier wie
ein Auszug gelesen wird und wo er liegt.

- **Einlesen** entscheidet alles Weitere. `parsed` liest den Auszug Buchung für
  Buchung und braucht ein **Parserprofil**; `summary` tut das nicht — so ein Konto
  wird nur über die Umbuchungen sichtbar, die es von einem geparsten Konto erreichen.
- **Warnen unter** ist die Schwelle, ab der die Delle auf [Konten](#konten) gemeldet
  wird. Für ein Girokonto mit Dispo ist das die wichtigste Zahl der Seite.
- **Auszüge in** ist ein Ordnername unter `data/statements/`: im Datenordner, also im
  Sicherung und beim Umzug dabei. Ein voller Pfad ist erlaubt, wird aber nicht
  mitgesichert und zeigt auf einem anderen Rechner ins Leere — die Seite schreibt
  beim Tippen mit, wohin die Dateien kommen.
- Angelegt wird in `accounts.yaml`, hinter den Konten, die dort stehen; ihre Notizen
  bleiben.
- **Öffnen** bearbeitet ein Konto: Namen, Art, Einlesen, Schwelle, Auszugsordner und
  Notiz. Die Kennung bleibt. **Geschlossen am** nimmt das Konto aus jeder Auswahl, die
  Buchungen bleiben; leer öffnet es wieder. Ein anderer Auszugsordner verschiebt keine
  Dateien.
- **Auszug erkennen:** eine Datei aus dem Online-Banking wählen. Die App nennt
  Bank, Konto, Zeitraum und ob der Auszug aufgeht, und füllt damit das Formular für
  ein neues Konto — oder legt die Datei in ein Konto, das dieselbe Bank schon liest.
  Beschrieben sind die Auszüge als CSV von ING, comdirect, DKB, Sparkasse, Volks- und
  Raiffeisenbanken, Commerzbank und N26, nach Beschreibung, noch nicht an echten
  Exporten geprüft.
  **Sparkasse:** im Online-Banking unter *Umsätze → Exportieren* das Format **CSV-CAMT V2**
  oder **CSV-CAMT V8** wählen (gleiche Spalten), ersatzweise **CSV-MT940**; je Konto eine
  Datei, den Zeitraum bis zum Monatsletzten (oder bis heute). Das PDF der Umsatzliste und
  „CSV mit Kategorien“ liest die App nicht. Die Sparkasse-CSV trägt keinen Stand: den Stand trägst du im
  Monatsabschluss unter *Konten* einmal ein („Stand laut Online-Banking“, mit Datum);
  von dort rechnet die App mit den Buchungen vor und zurück. Bis dahin steht dort „Stand
  fehlt: einmal eintragen“ und die Zeile bleibt offen. Vorgemerkte
  Buchungen fehlen, bis sie gebucht sind; der nächste Auszug bringt sie.
- **Spalten zuordnen:** kennt die App einen Auszug als CSV nicht, schlägt sie vor, welche
  Spalte Datum, Betrag, Gegenpartei und Stand ist. Nach der Vorschau wird daraus ein
  eigenes Profil in `config/csv_profile_custom.yaml`; ab dann wird die Bank erkannt.
- **Beispiel für eine fehlende Bank:** `finctl anonymisieren DATEI --name "Vorname Nachname"`
  schreibt eine Kopie ohne Namen, IBANs und Nummern; Datum und Beträge bleiben,
  `--faktor 3` verfremdet auch sie. Ein PDF wird zu Seitentext. Vor dem Weitergeben
  ansehen.

### /ziele

Zwei Balken je Ziel, zwei Fragen: **oben** der Bestand, der heute wirklich da ist, ohne
Renditeannahme; **unten** die Extrapolation auf den Stichtag, wenn Annahmen und
eingeschaltete Pläne eintreten. Erst beide zusammen sagen, ob du ankommst.

- Der **Wendepunkt** oben ist eine andere Frage als die Zielbeträge: ab wann du nicht
  mehr arbeiten *musst*, statt ob du aufhören *kannst*. Gehalt und Einmalposten zählen
  dort nicht.
- Jedes Ziel misst gegen dasselbe liquide Vermögen, außer es trägt eine eigene **Basis**.
  Nichts angehakt heißt: alles, abzüglich Verbindlichkeiten und Notgroschen.
- Die **Rentenlücke** ist gerechnet: Ausgaben im ersten vollen Rentenjahr minus Rentenquellen
  und Mieten, entnommen bis zur Lebenserwartung. Gedreht wird auf [Annahmen](#annahmen).
- Die Extrapolation steht **zweimal** da: im Schnitt und im Tempo der letzten drei Monate.
  Liegt der Stichtag im Horizont von [/konten](#konten), steht sie **einmal** da,
  „vorausgerechnet“ aus dem Stand der Konten mit den eingeschalteten Klammern.
- Ein Ziel **ohne Stichtag** bekommt weder Extrapolation noch zweite Rate.
- Die Karte nennt zwei **Monatsraten**: vorn die vorsichtige **ohne Rendite**, dahinter die
  **mit Rendite** nach den Sätzen der Hochrechnung; der **Rechenweg** zeigt sie.
- Die **Notiz** hält fest, woher die Zahl kommt, damit niemand sie „korrigiert“.
  **Löschen** nimmt Ziel und Notiz aus `goals.yaml`.

### /planung

Alles, was noch nicht in den Buchungen steht, als **Klammern** mit beliebig vielen Planzeilen.

- **Verpflichtungen** gelten in jeder Hochrechnung; die übrigen Klammern sind Optionen und lassen
  sich schalten. Der Schalter bewegt Kontenvorschau, Jahresrechnung und Ziele gemeinsam.
- Eine Planzeile ist ein **Betrag**, ein **Wegfall** oder eine **erwartete Einnahme**
  (Schenkung): Sie ersetzt ihre zugeordneten Buchungen und zählt voll.
- **Teilzeit**: Anteil und Beginn aus den Annahmen, die Klammer schaltet sie ein; Zeilen
  ohne Datum folgen.
- Beträge werden **ohne Vorzeichen** eingetragen, die Richtung ist eine Auswahl.
- Gemessen wird über die **zugeordneten Buchungen**, nie eingetippt. Ein Haken genügt:
  dazu zählt die Reihe, dieselbe Gegenpartei in derselben Kategorie. Ohne Zuordnung zieht
  ein Wegfall nichts ab.
- Ein Wegfall nimmt in jeder Rechnung genau heraus, was sie für die Reihe fortschreibt.
  **Nur Kontoprognose** heißt: die Reihe verlässt nur dieses Konto, ausgegeben wird
  weiter — die Jahresrechnung bleibt unberührt.
- Ein Betrag wirkt nur mit dem Teil, der **noch nicht im Ledger steht**; ein Wegfall
  schrumpft, sobald das Messfenster über ihn hinweggelaufen ist.
- Projiziert wird **ab dem Monat nach dem letzten Kontoauszug**.
- Sind zwei Pläne gleichzeitig an, summiert die Prognose sie. Varianten derselben
  Entscheidung gehören einzeln eingeschaltet.

### /renten

Rentenquellen: gesetzliche Rente, Fondsrenten und Policen, was im Ruhestand hereinkommt.

- **Anlegen**: Name, Monatsrente oder Kapital, Betrag laut Schreiben, Bezug ab. Immer
  nominal, wie im Schreiben; nennt es mehrere Wertentwicklungen, die mit 7 %.
- **Bezug ab** leer heißt ab dem Rentenbeginn aus der Einrichtung.
- **Effektivkosten** stehen in der Standmitteilung. Über der Schwelle aus den Annahmen
  steht ein ⚠ – deine Schwelle, keine Bewertung des Vertrags.
- **Unverändert** legt denselben Betrag mit heutigem Datum ab.
- **Prüfwert**: Hat eine Police einen aus der Mitteilung, steht darunter er neben dem Wert
  des Modells zum selben Datum, mit der Abweichung. Derselbe Satz steht im Rechenweg der
  Auszahlung auf [Hochrechnung](#hochrechnung).
- **Betriebliche Altersvorsorge**, die nur der Arbeitgeber zahlt: Mit Stand, Datum und
  Beitrag je Jahr steht darunter der **Satz**, der zum Betrag führt,
  der Prüfwert mit dem Satz, den die Mitteilung unterstellt, und die Auszahlung ohne und mit
  der Teilzeit aus den Annahmen.
- Gespeichert wird der ganze Eintrag in `renten.yaml`. Ein Klick auf „löschen" nimmt die
  Rentenquelle aus der Datei; die Rückfrage nennt den Anfang ihrer Notiz, die mitgeht.

### /annahmen

Oben wird gedreht, darunter steht, was gemessen oder belegt ist und deshalb kein
Eingabefeld hat. Jede Stellschraube nennt, was sie bewegt — nicht jede bewegt beide
Rechnungen.

- Gespeichert wird in `config/assumptions.yaml`. Ein leeres Feld nimmt die Angabe heraus, wo die App
  einen eigenen Wert kennt; sonst lehnt die Seite es ab.
- Was die Stellschrauben bewirken, zeigt die [Hochrechnung](#hochrechnung).
- **Steuersatz auf Kapitalerträge** und **Basiszins** stehen hier auch; den Satz setzt dein
  persönlicher Satz, den Basiszins nennt das Bundesfinanzministerium jedes Jahr.
- **Zinssätze je Konto**: Zeitraum und Satz. Ohne Eintrag zahlt ein Tagesgeld den
  langfristigen Satz, ein Girokonto nichts. /konten und die Hochrechnung rechnen damit Zinsen und
  Steuer selbst (ein Freibetrag für den Haushalt); eine Planzeile darauf zählt in keiner Prognose.
- Was ein Objekt abwirft, steht am Objekt ([/immobilie](#immobilie), Prognose).
- Woraus Monatsmodell und Jahresrechnung fortschreiben, steht auf [/prognosebasis](#prognosebasis).

### /prognosebasis

Je Block eine Zeile: die Quelle, der Betrag im ersten Monat des Monatsmodells, der Betrag im ersten
vollen Jahr der Jahresrechnung und die Seite, auf der der Haushalt die Quelle ändert. Die Seite
rechnet nichts; sie ordnet die Posten, die beide Rechnungen selbst bilden.

- **Fortschreibung** nennt das Messfenster und das Verfahren: die Zwölfmonatssumme, im
  Monatsmodell durch zwölf geteilt. Reihen mit festem Takt zählen mit ihrem Betrag je Termin.
- Ersetzt ein **Vertrag**, eine **erwartete Einnahme** oder eine **Objektprognose** die Messung, steht
  sie als eigene Zeile, und die ersetzten Buchungen zählen in keiner Rechnung mehr.
- Nennen beide Rechnungen dieselbe Quelle, steht sie einmal; sonst stehen beide.
- **Nicht fortschreiben** (aufklappbar) wählt eine Kategorie für beide Rechnungen ab, etwa eine
  Schenkung, die zufällig im Messfenster lag. *unregelmäßig* heißt: in weniger als der Hälfte der
  Monate gebucht und trotzdem fortgeschrieben. Gespeichert wird in `config/prognosebasis_custom.yaml`.

### /hochrechnung

Wohin das Geld in den nächsten Jahren fließt. Gedreht wird auf [Annahmen](#annahmen),
hier steht die Wirkung.

- **Fluss** zeigt ein Jahr nach Grund: Planzeilen und Kredite mit Namen, Gemessenes je
  Block. Ein Klick führt zu den Buchungen dahinter, zur Klammer oder zum Kredit.
- **Gespart** ist der Überschuss des Jahres. Er geht aufs Tagesgeld, bis dessen Ziel erreicht
  ist; was darüber liegt, wird ins Depot umgeschichtet („ins Depot" in der Tabelle).
  Rendite kommt obendrauf und steht nicht im Fluss: sie ist kein Geld, das hereinkommt.
- **Im Ruhestand** zeigt jede Rentenquelle mit Beginn und dem Betrag, der dann nominal ankommt;
  gepflegt wird sie im [Monatsabschluss](#monatsabschluss-konten-depots-renten).
  Gerechnet wird bis zur Lebenserwartung. Ab Rentenbeginn endet das Gehalt, die Renten
  kommen nach dem Abzug für Steuer und KV, und das Depot füllt das Tagesgeld auf.
  Oben steht, bis wann das Kapital reicht.
- **Jahr für Jahr**: laufende Posten kommen aus den letzten zwölf vollständigen Monaten
  und wachsen ab deren Mitte mit der Inflation. Ein Klick auf das Jahr zeigt jeden
  Posten im Rechenweg; die Posten ergeben genau die Summen der Zeile.
- Das **laufende Jahr** zählt nur seine Restmonate, auch bei der Rendite.
- **Tempo**: Konsum im Schnitt oder letzte drei Monate.

### /rueckblick

Vier Reiter auf dieselben Buchungen.

- **Vorjahr** vergleicht je Kategorie **dieselben Monate** beider Jahre; ein
  angebrochenes Jahr gegen ein volles wiese überall eine Ersparnis aus. Beträge sind
  **netto je Kategorie**: Erstattungen mindern die Kategorie, in der sie anfallen.
- Eine Zeile ohne Buchungen im laufenden Jahr ist eingespart oder vergessen — bei einem
  Vertrag derselbe Betrag mit sehr verschiedener Bedeutung.
- **Fixkosten** zeigt, was in der Taxonomie als `fix` markiert ist, **Alle Kategorien**
  alles außer Umbuchungen. Das Flag ist eine eigene Achse: KFZ-Steuer ist Fixkosten
  *und* Mobilität. Sitzt es falsch, fällt das im Vergleich beider Reiter auf und wird
  auf [Kategorien](/kategorien) abgeräumt.
- **Letzte Buchung** zeigt, was aufgehört hat zu buchen — beendet oder vergessen.
- **Jahr und Konto** engen Summe *und* Monatsteiler ein; geteilt wird nur durch
  abgeschlossene Monate, der Spaltenkopf nennt ihre Zahl.
- **Fluss** zeigt ein Jahr als Diagramm: links, was netto hereinkam, rechts, wohin
  es ging; ein Klick zeigt die Buchungen. Ohne Kapital bleibt ein **Überschuss**;
  *inkl. Kapital* zeigt, was daraus wurde: ins Depot, in einen Objektkauf, auf den Konten.

### /transactions

Jede Buchung, filterbar — und die Stelle, an der eine falsche Zuordnung korrigiert wird.
Drei Reiter, derselbe Filter darunter:

- **Offen** sind die Buchungen ohne Kategorie, größte zuerst. Kategorie wählen und Enter
  drücken; die Zeile wird blass, die nächste ist dran.
- **Aufzuteilen** sind Buchungen, die eine Regel bewusst offen gelassen hat, weil eine
  Buchung mehrere Dinge abdeckt — meist Lastschriften eines Zahlungsdienstes.
- Gespeicherte Zeilen gelten als **Handentscheidung**: ein erneutes Zuordnen aller
  Buchungen überschreibt sie nie.
- **Offen** zeigt nur, was *keine* Kategorie hat. Eine Regel, die zu breit greift, ist
  dort unsichtbar: dafür filtert man unter **Alle** nach *Quelle = Regel*.
- Eine Korrektur ist eine Ausnahme; dieselbe Regel wiederholt korrigiert ist eine falsche
  Regel, und sie je Buchung zu korrigieren behebt die nächste nicht.
- Nichts wird automatisch umgeschrieben: eine Regel, die sich aus einer Korrektur selbst
  umschreibt, hängt still eine Regel um, die vierzigmal richtig lag.

### /split

Eine Buchung in ihre Teile zerlegen, wenn sie mehrere Dinge abdeckt. Die Summe
der Teile muss den Betrag der Buchung ergeben; jeder Teil trägt Kategorie,
Steuerposition, Objekt und Notiz.

### /kategorien

Der Kategorienbaum: anlegen, umbenennen, stilllegen — und das `fix`-Flag setzen, das
entscheidet, was unter Fixkosten erscheint.

**Neue Oberkategorie** legt einen Ast ohne Kinder an (Einnahme oder Ausgabe); die
Subkategorien kommen danach. **Fixkosten** und **Einmalig** stehen an der geöffneten
Subkategorie; gilt schon der Wert des Asts, schreibt die Seite nichts.

**Stilllegen tut zwei Dinge, die zusammen gehören**: die Buchungen wandern zur
Ersatzkategorie, und jede Regel, die die alte Kennung nennt, muss umgehängt werden. Nur
das Erste zu tun heißt, dass der nächste Lauf alles zurückschiebt. Die Regeln stehen
deshalb je Zeile dabei.

### /regeln

Welche Regel welche Buchung zuordnet.

- Die **kleinere Priorität gewinnt**. Handentscheidungen auf Buchungen
  stehen über jeder Regel.
- Die **Vorschau** zeigt vor dem Speichern, welche Buchungen eine Regel fängt und welche
  dadurch die Kategorie wechseln — eine zu breite Regel ordnet sonst still das halbe
  Ledger um.
- Gespeichert wird die Regel in `config/rules.yaml`, samt ihrer Notiz. Speichern ohne
  Änderung ändert nichts.
- **Allgemeine Regeln** liefert die App mit: Supermärkte, Tankstellen, Streaming,
  Steuern. Sie gelten nach allen eigenen und lassen sich einzeln oder ganz abschalten.
- **Vorschläge über ein KI-Modell** stehen unter [/vorlagen](#vorlagen): offene Texte ohne
  Nummern und Beträge, die Antwort wird geprüft, übernommen wird nur Angehaktes.

### /vorlagen

Ein Text für ein KI-Modell deiner Wahl. Die App sendet nichts, solange du keine
[Anbindung](#vorlagen-anbindung) einträgst: Du kopierst die Vorlage selbst ins Modell und fügst die
Antwort wieder ein.

- Eine **Vorlage** hat drei Teile: die **Begriffe** aus `CONTEXT.md`, die **Lage** aus denselben
  Rechnungen wie die Seiten und die **Frage** mit der Form der Antwort. Auszugstexte und Nummern
  stehen nie darin.
- **Buchungen einordnen**: Die Lage hat die Kategorien und die Texte der offenen Buchungen, ohne
  Beträge; abgewählte gehen nicht hinaus. Die Antwort sind Zeilen „Suchtext ; Kategorie“. Die
  Seite zeigt, was jede fängt und wo sie einer Zuordnung widerspräche. Übernommen wird nur
  Angehaktes, als Regel in `config/rules.yaml`.
- **Monat erklären** hat die Summen je Oberkategorie gegen den Schnitt der zwölf Monate davor und
  die offenen Punkte des Monatsabschlusses. **Frage zur Prognose** hat die Kontoprognose, das
  Vermögen je Jahr und die Annahmen; die Frage schreibst du selbst.
- Beide antworten mit „ZUSAMMENFASSUNG: …“ und „AUFFÄLLIG: Kennung ; Satz“. Die Seite markiert
  Kennungen und Beträge, die nicht in der Lage stehen. Übernehmen lässt sich daraus nichts.
- Namen von Konten und Kategorien und Beträge stehen in diesen beiden Texten; sie verlassen den
  Rechner, sobald du sie in ein Modell außerhalb einfügst.

### /vorlagen/anbindung

Ein Modell kann die Vorlage auch von der App bekommen. Das ist **ausgeschaltet**, bis du hier
einträgst: Adresse einer Schnittstelle in der Form „chat completions“, das Modell und, wenn sie
einen verlangt, den Schlüssel. Ein Server auf diesem Rechner geht auch.

- Auf [/vorlagen](#vorlagen) erscheint dann der Knopf **Senden …**. Er zeigt den ganzen Text, der
  hinausgeht, und den Rechnernamen des Ziels: „Das verlässt den Rechner“. Bei `localhost`,
  `127.0.0.1` und `::1` steht dort, dass der Text auf diesem Rechner bleibt. Gefragt wird jedes
  Mal; „immer erlauben“ gibt es nicht.
- Die Antwort steht im Feld wie eine eingefügte und wird genauso geprüft. Übernommen wird nur, was
  du bestätigst.
- Adresse und Modell stehen in `config/anbindung.yaml`. Der **Schlüssel** nicht: Er liegt in
  der Datei `anbindung.schluessel` im Datenordner, nur für dich lesbar, und wird nie wieder
  angezeigt. Hier siehst du „eingetragen“ und kannst ihn entfernen.
- Außer diesem Knopf sendet die App nichts, auch nicht im Hintergrund.

### /vorschlaege

Was ein Modell vorschlägt und was sich dadurch ändern würde. Ein Modell deiner Wahl liest über den
Befehl `finctl mcp` deine Zahlen und kann Regeln, Planzeilen in einer Klammer, Kredite und Notizen
vorschlagen. Ein lokales Modell ist der Standard: Dann verlässt nichts deinen Rechner.

- **Einbinden:** Trage im Programm deines Modells einen MCP-Server über stdio ein, mit dem Befehl
  `finctl mcp`. In der App ist es ihr Programm mit dem Argument `mcp`. Liegt dein Datenordner nicht
  an der Vorgabe, setzt du `FINCTL_DATEN`. Der Befehl öffnet keinen Port.
- Das Modell **liest** über dieselben Rechnungen wie die Seiten. Notizen, Anschriften und lange
  Nummern gibt der Zugang nicht heraus.
- Es **schreibt nie** in `config/`. Ein Vorschlag liegt in `data/vorschlaege/`, geprüft wie die
  Seite ihn prüft.
- **Übernehmen** schickt ihn an dieselbe Route wie das Formular, **Verwerfen** löscht ihn. Die
  Navigation zeigt, wie viele offen sind.

### /reihen

Wie oft jede Reihe zahlt. Eine **Reihe** ist dieselbe Gegenpartei in derselben
Kategorie, über alle Konten. Ihren **Takt** erkennt die App aus den Buchungen der
letzten zwei Jahre: monatlich, alle zwei, drei, vier oder sechs Monate, jährlich —
oder unregelmäßig.

- Die Tabelle zeigt je Reihe den **Betrag je Termin** (nicht die Summe der Monate),
  den letzten Termin, ob sie **läuft**, und den Jahreswert. Beendet ist sie, wenn ihr
  nächster Termin um mehr als einen halben Takt überfällig ist. Beide Prognosen
  rechnen mit Reihen; auf [/konten](#konten) gilt „läuft“ je Konto.
- **Festlegen** gilt für die ganze Reihe, nur für das Wie oft; zurücknehmen stellt die
  Erkennung wieder her.
- **Aufgeklappt** stehen die Termine. Ein *einmaliger* Betrag kommt zusätzlich, der *frühere
  Betrag* liegt vor dem heutigen.
- **Gehört zu** führt zwei Schreibweisen derselben Gegenpartei zu einer Reihe zusammen,
  damit beide Prognosen sie einmal zählen; Regeln und Verträge sehen weiter jede.
  Vorgeschlagen wird es, wo eine Reihe endet und eine gleich teure einen Takt später
  beginnt, geschrieben erst auf den Klick.
- **Einmalig** nimmt einzelne Buchungen aus jeder Fortschreibung, ebenso Kategorien mit
  dem Merkmal `einmalig`.

Gespeichert wird in `reihen_custom.yaml`; Speichern ohne Änderung ändert keine Datei.

### /vertraege

Verträge mit festem Termin, in zwei Reitern: **Abos** und **Versicherungen**. Die
Prognose erwartet sie am Tag, an dem sie abgehen, statt sie als Zwölftel zu mitteln.
Ihr Betrag steigt mit der Inflation wie eine gemessene Reihe, stetig ab der Mitte des
Messfensters; der Beitrag in eine Police bleibt fest.

- Einem Vertrag werden **seine Buchungen zugeordnet**. Er ersetzt sie dann in der
  Prognose, statt neben ihnen zu stehen, und die jüngste zeigt, ob der Betrag noch
  stimmt.
- **Ein Haken genügt.** Dazu zählt die Reihe: dieselbe Gegenpartei, dieselbe Kategorie,
  ein Betrag nahe dem Vertragsbetrag. Eine Beitragserhöhung bleibt drin, eine
  Erstattung und ein Einkauf bei derselben Gegenpartei nicht.
- Was in der Kategorie **daneben** liegt, bleibt gemessen. Ein Vertrag ohne
  zugeordnete Buchung zählt doppelt.
- **Gekündigt zum** genügt ebenso: beide Rechnungen hören am Stichtag auf. Eine
  Wegfall-Zeile brauchst du dafür nicht — die bleibt für Dinge ohne Vertrag. Hast du
  beides, zählt es einmal, und versprochen wird nie mehr als die Vertragsrate.
- **Löschen** nimmt einen Vertrag samt Notiz aus `abos.yaml` bzw. `versicherungen.yaml`.
- Unter **Mitzahler** steht, wer mitzahlt. Rückzahlungen werden aus den Eingängen
  abgeglichen, nicht abgehakt: ein Haken wäre eine Behauptung neben den Daten.

### /immobilien

Cashflow und Gewinn sind verschiedene Fragen. Ein Objekt kann jeden Monat Geld kosten und
trotzdem rentabel sein — der Normalfall bei einer finanzierten Vermietung.

- **Tilgung** kostet Geld und baut Vermögen auf; **AfA** mindert den Gewinn und kostet
  nichts.
- **Kapital investiert** bleibt aus beiden heraus: Kaufraten sind Investition, keine
  laufende Kosten. Auf ein Jahr hochgerechnet ließen sie ein Objekt im Bau
  katastrophal aussehen.

### /immobilie

Ein Objekt im Einzelnen: Anschaffung, Abschreibung, geplanter Verkauf und alle Buchungen
dazu.

- Der **Grundstücksanteil** gehört gewusst, nicht geschätzt: Grund und Boden werden nicht
  abgeschrieben, der Anteil ändert die AfA-Grundlage direkt. §7 EStG sind in der Regel
  2 % (vor 1925 gebaut: 2,5 %; Neubauten seit 2023 auch degressiv).
- Ein **Verkauf ohne erwarteten Preis** wird nicht gerechnet. Den Kredit enden zu lassen,
  ohne den Erlös zu kennen, hieße eine Rate zu streichen und nichts dafür zu zahlen.
- Steht der Verkauf in einer **Planklammer**, gewinnt die Klammer; Termin und Preis hier
  sind dann nur ein Vorschlag.
- **Prognose**: Miete und Kosten je Monat, dazu wann die Vermietung beginnt und endet.
  Für ein Objekt, dessen Buchungen den Ertrag noch nicht tragen — ein Monat Miete, aufs
  Jahr gemittelt, wäre ein Zwölftel. Mit Prognose rechnen die Hochrechnung und
  [Konten](#konten) das Objekt aus ihr statt aus der Messung, dort auf dem Konto der letzten
  Miete; leer bleibt es gemessen. Die Vorgabe steht unter
  `prognose:` in `config/properties.yaml`; ein Szenario ändert sie je Objekt unter
  `immobilien.objekte`.
- **Kategorie und Steuer** sind in der Buchungstabelle änderbar: die Anlage-V-Positionen
  sind das, was der Steuerexport liest.

### /kredite

Die Tilgungspläne aus `config/loans.yaml`, je Kredit mit aktueller Kondition und
Anschlussfinanzierung nebeneinander.

- **Neuer Kredit** legt einen Kredit mit einem Segment an: Restschuld, Zins,
  Rate, Laufzeit. Ein Kredit am Objekt entsteht hier nicht — dessen Zinsbindung und Anschluss
  stehen in `loans.yaml`.
- **Entfernen** nimmt einen Kredit samt Notiz aus `loans.yaml`, damit aus jeder
  Prognose.
- **laut Plan** ist der Tilgungsplan über das ganze Jahr, auch die Monate, die noch
  kommen; **gebucht** kommt aus dem Ledger. Weichen sie ab, ist entweder der Plan falsch
  oder die Buchung — zum Beispiel eine Rate, die vollständig als Tilgung gebucht wurde
  und deren Zinsanteil dadurch in keiner Anlage V auftaucht.
- Die **Anschlussfinanzierung** ist Vorschau, solange kein Angebot vorliegt: was passiert,
  wenn zu den heutigen Konditionen weitergeführt wird. Das ist der Maßstab für alles, was
  stattdessen ausgehandelt wird.
- Die **Rate ist ein Ergebnis**, keine dritte Eingabe: sie folgt aus Zins und anfänglicher
  Tilgung, das Laufzeitende aus beiden.
- **Echte Verträge sind nicht editierbar**, Vorlagen schon. Ein Vertrag ist aus Unterlagen
  rekonstruiert; ihn überschreibbar zu machen hieße, eine Tatsache durch eine Eingabe zu
  ersetzen. Vorlage und Anschlusskondition speichern am Kredit in `config/loans.yaml`; die
  Anschlusskondition rechnet nur diese Seite, die Prognose liest allein `anschluss`.

### /steuer

Die einzige Ansicht, die nach der **Steuerachse** sortiert ist statt nach dem
Kategorienbaum. Anlage V geht je Objekt, Anlage N je Werbungskosten-Position, und keines
von beidem deckt sich mit „wohin ist das Geld geflossen".

- Jede Zeile führt auf die Buchungen dahinter: eine Zahl, die man nicht zurückverfolgen
  kann, kann man dem Finanzamt nicht erklären.
- Eine Zeile mit *⚠ ohne Objekt* ist ein Fehler — sie lässt sich keinem Formular zuordnen.
- **AfA steht bewusst nicht hier**: sie kostet kein Geld und taucht in keinem Auszug auf,
  sondern kommt aus den Objektstammdaten.
- Die Seite ersetzt keine Erklärung; sie liefert die Zahlen, die dort eingetragen werden.


### /energie

Je Zähler und je Vorrat ein Reiter. Zählerstand oder Füllstand eintragen, der Rest
ergibt sich.

- **Zähler** (Strom, Gas, Fernwärme, Wasser): Verbrauch seit Beginn des Zeitraums,
  aufs Ende fortgeschrieben, bepreist und gegen die Abschläge gestellt. Positiv ist
  Guthaben, negativ Nachzahlung; der Rechenweg zeigt jeden Posten.
- **Gas** zählt m³ und rechnet in kWh ab: m³ × Brennwert × Zustandszahl, beide von
  der Rechnung.
- **Verteilung:** gleichmäßig für Strom und Wasser, nach Gradtagen für Heizung. Wer
  im Herbst abliest, hat den Winter noch vor sich. Die **Grundlast** (Warmwasser)
  verteilt sich gleichmäßig.
- **Ein Zeitraum hat kein festes Jahr**, und abgerechnet ist erst, was abgehakt ist.
  Ein neues Abrechnungsjahr geht, sobald das Ende vorbei ist.
- **Vorrat** (Heizöl, Pellets, Flüssiggas): verbraucht ist, was drin war, plus
  Lieferungen, minus was jetzt drin ist. Daraus der Jahresverbrauch, wie lange es bis
  zum Mindestbestand reicht, und was im Monat zurückzulegen ist, zum Preis der
  letzten Lieferung.
- Strom steht in `config/strom.yaml`, alles andere in `config/energie.yaml`.

### /projekte

Eine Themenkasse sammelt Ausgaben, die zusammengehören: eine gemeinsame Reise, ein Umbau, ein
Geschenk. Sie wird von Hand gefüllt, Teil für Teil, nicht von Regeln. Kategorie und Steuer
bleiben davon unberührt; die Themenkasse ist eine eigene Achse daneben.

- **Mit Beteiligten** wird geteilt, **ohne Beteiligte** sammelt sie nur die Kosten.
- Ein zugeordneter Teil ist gleich auf alle Beteiligten und dich geteilt, bis du für
  diese eine Buchung eine andere Teilung einstellst.
- Aufgeklappt zeigt eine Themenkasse ihre Buchungen mit den Anteilen, die Kosten nach
  Kategorie und nach Monat.
- Zugeordnet und geteilt wird unter „Zuordnen".
- **Themenkasse entfernen** nimmt sie samt Notiz aus der Datei; die Rückfrage nennt den Anfang
  der Notiz und wie viele Buchungen ihre Zuordnung verlieren.

### /salden

Je Beteiligtem und Themenkasse: sein Anteil an den Ausgaben, und was davon offen ist.

- **Rückzahlungen werden nicht verfolgt.** Was andere für dich ausgelegt haben, steht
  in keinem deiner Auszüge; ein Betrag daraus wäre nur halb richtig.
- Stattdessen gibt es je Beteiligtem und Themenkasse den Haken **„ausgeglichen"**. Er merkt sich
  den Anteil beim Abhaken. Kommt danach eine Ausgabe dazu, ist genau die Differenz
  wieder offen.
- Eine Rückzahlung gehört im Ledger in dieselbe Kategorie wie die Ausgabe, positiv. So
  zeigt die Kategorie am Ende deinen echten Anteil.

### /geteilt/buchungen

Die schlanke Buchungstabelle nur zum Zuordnen. Die Kategorie ist Anzeige und Filter,
nicht änderbar; dafür gibt es /transactions.

- **Eine Zeile je Teil.** Bei einer in Teile zerlegten Buchung lässt sich so nur
  der Teil zuordnen, der zur Themenkasse gehört.
- **Mehrere auf einmal:** Zeilen markieren, Themenkasse wählen, „Markierte zuordnen".
- **Teilung** je Buchung: gleich, feste Beträge, Prozent, Gewichte oder nur ich. Die
  Vorschau zeigt die Beträge, bevor gespeichert wird.
- Alles steht in `config/geteilt_custom.yaml`, geschlüsselt über die Buchung selbst,
  und übersteht damit einen Neuaufbau der Datenbank.
