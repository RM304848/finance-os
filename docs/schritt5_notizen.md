# Schritt 5: Notiz statt Kommentar

Arbeitsplan für die Umsetzung, geschrieben für ein Modell, das ihn Teil für
Teil abarbeitet (Claude Sonnet). Gesamtplan: `docs/Neufassung_plan.md`, dort
als Schritt 5. Entscheidung: `docs/adr/0001-notiz-statt-kommentar.md`.
Begriffe: `CONTEXT.md` (Notiz). Kommt nach Schritt 4c
(`docs/schritt_teilzeit_bav.md`). Nach diesem Schritt steigt der Alltag auf
`main` um.

## Ziel in einem Satz

Was heute als Kommentar in einer Datei steht, steht danach als Notiz am
Eintrag, und jede Sache hat genau eine Datei, die die Oberfläche ganz
schreiben darf.

## Befund (Opus, 07.10.2026)

- **Zwei Dateien je Sache.** Die Basisdatei ist von Hand geschrieben und
  trägt die Begründungen als Kommentare. Die Oberfläche schreibt deshalb nur
  in eine zweite Datei (`*_custom.yaml`), die beim Lesen gewinnt
  (`finctl/overlays.py` erklärt das Muster). Paare: `abos`, `versicherungen`,
  `balances`, `goals`/`ziele_custom`, `loans`, `properties`, `forecast`,
  `taxonomy`, `renten`, `accounts`, `lebensplan`. Dazu kommt
  `settings_custom.yaml`: Es überschreibt Werte aus `assumptions.yaml` und
  `forecast.yaml`. Rund 35 Module lesen oder schreiben eine `_custom`-Datei.
- **Nicht jedes Paar liegt in der Entwicklungskopie.** Der Code kennt auch
  `accounts_custom`, `lebensplan_custom`, `backup_custom`, `reihen_custom`,
  `zinssaetze_custom` und `module_custom`. In der Entwicklungskopie fehlen
  sie, im echten Datenordner können sie stehen. Die Umwandlung muss jedes
  Paar können, das der Code kennt, nicht nur die der Kopie.
- **Wo die Kommentare stehen.** In der Entwicklungskopie sind es rund 1.700
  Kommentarzeilen in fünf Lagen:
  - **Kopf der Datei:** vor dem ersten Schlüssel. Er erklärt die Datei und
    begründet oft alles darin.
  - **Abschnitt:** Ein Block durch eine Leerzeile vom nächsten Eintrag
    getrennt, oft mit einer Linie aus Strichen. Er gilt für die folgenden
    Einträge bis zum nächsten Abschnitt (etwa in `rules.yaml`).
  - **Eintrag:** Ein Block direkt über einem Eintrag oder innerhalb von ihm
    zwischen zwei Feldern.
  - **Feld:** Ein Kommentar hinter dem Wert in derselben Zeile, manchmal über
    mehrere Zeilen fortgesetzt. Ein Teil wiederholt nur den Wert in Euro.
  - **Einstellung:** Ein Kommentar an einem Schlüssel ohne Kennung, in
    `assumptions.yaml`, `lebensplan.yaml` und `forecast.yaml`.
  Die meisten Kommentare stehen in `rules.yaml`, `properties.yaml`,
  `forecast.yaml`, `taxonomy.yaml`, `loans.yaml` und `assumptions.yaml`.
- **Notizen gibt es schon an manchen Stellen:**
  - Reihen tragen `notiz` und `notiz_vom` (`finctl/reihen.py`, `_notiz`).
    Das Datum bleibt, solange der Text derselbe ist.
  - Renten, Ziele und Bestände tragen `notiz` ohne Datum.
  - Renten haben daneben ein Freitextfeld `herleitung`, und `/renten` zeigt
    `notiz or herleitung`. Das ist eine Notiz unter anderem Namen.
  - Das Feld `note` in `set:` einer Kategorisierungsregel ist keine Notiz des
    Eintrags. Es ist der Text, den die Regel an eine Buchung schreibt, und
    bleibt, wie es ist.
- **Köpfe, die die App schreibt.** Die App setzt ihren Text über jede
  `_custom`-Datei, die sie schreibt (`EINSTELLUNGEN_KOPF` und Verwandte). Das
  ist Text der App, keine Begründung des Haushalts.
- **Dateien ohne Seite.** Ein paar Dateien bearbeitet keine Seite:
  `server.yaml`, `backup.yaml`, `verbotene_namen.yaml`,
  `taxonomy_migrations.yaml` und `accounts.example.yaml`. Ihre Kommentare
  beschreiben vor allem die Form der Datei.

## Entscheidungen (mit dem Haushalt abgestimmt, 07.10.2026)

1. **Wo eine Notiz steht.**
   - Ein Eintrag mit Kennung (Konto, Kredit, Objekt, Ziel, Rente, Abo,
     Regel, Kategorie, Bestand, Klammer) trägt `notiz` und `notiz_vom` direkt
     am Eintrag, wie heute die Reihen.
   - Eine Einstellung ohne Kennung bekommt ihre Notiz in der Datei unter
     `notizen:`, mit dem Schlüsselpfad als Ort (etwa `kapital.rendite_depot`).
   - Was für eine ganze Datei gilt, steht dort als **Notiz des Bereichs**
     unter `notizen: {bereich: …}`.
   - Alle Notizen haben dieselbe Form und lesen und schreiben sich über ein
     Modul (`finctl/notizen.py`).
2. **Zuordnung der Kommentare:**
   - Der Kopf geht in die Notiz des Bereichs.
   - Ein Abschnitt geht ebenfalls in die Notiz des Bereichs, mit dem Hinweis,
     vor welchem Eintrag er stand. Er wird nicht in jeden Eintrag des
     Abschnitts kopiert, weil eine Begründung nur einen Ort haben soll.
   - Ein Block an einem Eintrag geht in dessen Notiz, in der Reihenfolge der
     Datei.
   - Ein Kommentar an einem Feld geht in die Notiz des Eintrags, eingeleitet
     mit dem Feldnamen („`payment_cents`: …“).
   - Ein Kommentar an einer Einstellung geht in die Notiz unter ihrem Pfad.
   - Ein auskommentierter Wert bleibt Text in der Notiz.
3. **Nichts geht verloren.** Jede Kommentarzeile landet in genau einer
   Notiz. Wegfallen dürfen nur zwei Arten:
   - die Köpfe, die die App selbst geschrieben hat, wenn ihr Text mit einer
     Konstante des Codes übereinstimmt;
   - Feldkommentare, die nur den Wert des Feldes in Euro wiederholen.
   Beide stehen im Bericht der Umwandlung, und die alten Dateien bleiben in
   einer Sicherung.
4. **Datum.** Eine übernommene Notiz hat **kein Datum**, denn wann der
   Kommentar entstand, weiß niemand. Ohne Datum heißt: aus der Zeit vor den
   Notizen. Das Datum bekommt sie, wenn der Haushalt ihren Text ändert. Eine
   unveränderte Notiz behält ihr Datum, auch ein fehlendes. Später kann der
   Monatsabschluss nach Notizen ohne Datum fragen (ADR 0001).
5. **Ein Ort je Sache.**
   - Jedes Paar wird zu einer Datei unter dem Namen der Basisdatei
     (`loans.yaml`, nicht `loans_custom.yaml`).
   - Eine Datei, die es nur als `_custom` gibt, behält ihren Namen. Die
     Dateinamen räumt Schritt 8 in einem Zug auf.
   - Die Werte aus `settings_custom.yaml` gehen in die Datei, aus der der Code
     sie heute überschreibt.
   - Gelesen wird danach genau, was vorher galt. Der Code liest keine
     `_custom`-Datei mehr, wo ein Paar zusammengelegt ist.
   - Schreiben darf die Oberfläche jetzt die ganze Datei, über
     `finctl/dateien.py`, Notizen eingeschlossen.
6. **Ausdrücklich umstellen, nicht still.**
   - `finctl umstellen` wandelt einen Datenordner um. Davor sichert es
     `config/` nach `archiv/vor_umstellung_<Datum>/`, danach schreibt es einen
     Bericht nach `notizen/umstellung_<Datum>.md`: jeder Kommentar und wo er
     steht, dazu was weggefallen ist.
   - Ein zweiter Lauf ändert nichts.
   - `finctl umstellen --probe` schreibt nur den Bericht und eine umgewandelte
     Kopie in einen Ordner außerhalb des Datenordners. So sieht der Haushalt
     vor dem Umstieg, wo seine Kommentare landen.
   - Findet die App eine Datei in alter Form, die sie nicht mehr liest, hält
     sie an und nennt den Befehl. Sie liest dann nicht still nur die halben
     Werte.
7. **Dateien ohne Seite behalten ihre Kommentare:** `server.yaml`,
   `verbotene_namen.yaml`, `taxonomy_migrations.yaml`,
   `accounts.example.yaml`. Sie beschreiben die Form der Datei, und niemand
   bearbeitet sie in der Oberfläche. (`backup.yaml` stand hier zuerst. Es hat
   aber eine Seite und wird umgestellt wie die anderen, siehe N.0, Nummer 3.)
8. **Die Startvorlagen (`finctl/vorgaben/`) und der Musterhaushalt** werden
   mit umgestellt. Was ihre Kommentare über die Form sagen, gehört ins
   Handbuch, nicht in eine Notiz. Die Notizen des Musterhaushalts sind
   erfunden.
9. **Zeigen ist Schritt 6.** Notizen erscheinen in Schritt 5 nur dort, wo eine
   Seite heute schon eine zeigt (`/renten`, `/ziele`, `/reihen`,
   Monatsabschluss). Notizen überall sichtbar und datiert macht Schritt 6.

## Was „gleich“ und was „gewollt“ heißt

Wie in `docs/schritt4_reihe_takt.md`. Vor jedem Befehl gilt:

```bash
export FINCTL_DATEN="$HOME/Library/Application Support/Finance OS Entwicklung"
```

Schritt 5 ist **gleich**: Kein Betrag, kein Datum und keine Buchung ändert
sich. Nur der Text kann sich ändern, und zwar auf Seiten, die schon eine
Notiz zeigen: Dort steht dann der übernommene Kommentar.

**Geprüft wird an einer umgewandelten Kopie.** Jeder Teilschritt, der die
Form der Dateien ändert, wird so geprüft:
1. Die Entwicklungskopie in einen Ordner im Scratchpad kopieren, samt
   `data/referenz/`.
2. Dort `finctl umstellen` laufen lassen.
3. Mit `FINCTL_DATEN` auf diese Kopie `tests/referenz.py pruefen`
   (bei N.2 `--nur-zahlen`).

So probt jeder Teilschritt den Umstieg im Kleinen. Die Entwicklungskopie
selbst wandelt Opus in einem eigenen Datenschritt um (N.2), oder die Sitzung
am Ende ihres Teilschritts, wenn er es ausdrücklich sagt (N.3).

**Sicherung vor Schritt 5** (angelegt am 07.10.2026):
`sicherung_vor_schritt5/config/` in der Entwicklungskopie. Sie ist der
Stand, den N.4 in einem Lauf umwandelt. Sie wird nicht verändert.

## Die Teilschritte

### N.0 Bestandsaufnahme (nur lesen)

Kein Code, keine Datei in `config/`. Für die Entwicklungskopie, den
Musterhaushalt und `finctl/vorgaben/` wird erfasst:
- **Je Datei:**
  - welche Eintragsart sie hält und woran ein Eintrag erkannt wird
    (Kennung oder Schlüsselpfad);
  - welche Module sie lesen und schreiben, und welche Funktion ein Paar
    zusammenlegt;
  - wie viele Kommentarzeilen in welcher der fünf Lagen stehen.
- **Je Leser:** ob er an einem zusätzlichen Schlüssel `notiz`, `notiz_vom`
  oder `notizen` scheitert oder ihn als Wert nimmt (etwa ein Leser, der über
  alle Schlüssel einer Datei läuft).
- **Freitextfelder, die Notizen unter anderem Namen sind:** etwa `herleitung`
  bei den Renten. Sie werden nicht verwechselt mit Feldern, die eine Buchung
  beschreiben, wie `note` in einer Regel.
- **Köpfe, die die App schreibt:** die Konstanten und welche Datei sie
  tragen.
- **Paare, die der Code kennt und die in der Entwicklungskopie fehlen.**

Ergebnis: eine Tabelle in diesem Plan unter N.0, nur mit Dateinamen,
Modulen und Zahlen, ohne einen Kommentartext. Einzelheiten mit echtem Text
gehören nach `notizen/N.0_bestand.md` der Entwicklungskopie. Daraus legt
Opus die Reihenfolge der Bereiche für N.3 fest.

**Fertig wenn:** die Tabelle steht, und der Bericht nennt jede Stelle, die
nicht in die fünf Lagen passt.

**Umgesetzt am 07.10.2026.** Nur gelesen: kein Code, keine Datei in `config/`, `sicherung_vor_schritt5/` unberührt (`config/` der Entwicklungskopie ist gleich `sicherung_vor_schritt5/config/`). Gelesen wurden `config/` der Entwicklungskopie (36 Dateien), `tests/musterhaushalt/config/` (32) und `finctl/vorgaben/` (8). Gezählt hat ein Skript im Scratchpad, nicht im Repository: Es findet Kommentare mit dem Scanner von PyYAML (alles, was kein Token ist und mit `#` beginnt) und ordnet jede Zeile über den Pfad aus dem Parser einer Lage zu. Der Musterhaushalt wird vorher datiert, denn `{J+1}` und Verwandte sind kein YAML. Proben liefen auf Kopien im Scratchpad. Einzelheiten mit Text und Orten: `notizen/N.0_bestand.md` der Entwicklungskopie.

`pruefen` meldet auf einer unveränderten Kopie und auf einer Kopie, die jede Datei durch PyYAML neu geschrieben hat (ohne Kommentare), „Gleich“: Der Verlust der Kommentare allein ändert keine Zahl und keinen Text einer Seite.

**Wie gezählt ist.** Eine Zeile ist eine Zeile mit einem Kommentar, ob ganz oder hinter einem Wert; ein einzelnes `#` zählt mit. Der Plan lässt Grenzen offen; so sind sie ausgelegt:

- **K (Kopf):** alles vor dem ersten Inhalt der Datei.
- **A (Abschnitt):** ein Block mit Leerzeile danach, der vor dem nächsten Eintrag steht. In Einstellungsdateien: ein Block mit Leerzeile danach.
- **E (Eintrag):** ein Block direkt über einem Eintrag oder einem Feld darin, oder innerhalb eines Eintrags zwischen zwei Feldern (auch mit Leerzeile danach).
- **F (Feld):** ein Kommentar hinter dem Wert in einer Datei mit Einträgen; Fortsetzungszeilen in derselben Spalte gehören dazu.
- **S (Einstellung):** ein Kommentar hinter oder direkt über einem Schlüssel ohne Kennung: in `assumptions*.yaml`, `lebensplan.yaml`, `backup.yaml`, `settings_custom.yaml`, in `forecast.yaml` alles außer `account_roles` und `account_budgets`, in `balances.yaml` `as_of`.
- **–:** passt in keine Lage (Orte unten).

Summe der Entwicklungskopie: 1770 Zeilen. Die fünf Dateien ohne Seite aus Entscheidung 7 tragen davon 76, der Rest sind rund 1.700 wie im Befund. `backup.yaml` zählt zu den fünf, hat aber eine Seite (siehe Paare).

**Tabelle A: Dateien der Entwicklungskopie.** `r/` steht für `web/routen/`. „liest“ nennt die Module, die den Dateinamen im Code tragen; `module.py` führt viele Namen, weil es an den Dateien erkennt, ob ein Modul Daten hat. Die Funktion, die ein Paar zusammenlegt, steht in der Paartabelle.

| Datei | Eintragsart, erkannt an | liest | schreibt |
|---|---|---|---|
| `abos.yaml` | Abo: `abos[].id` | abos.py, module.py | Hand |
| `abos_custom.yaml` | Abo: `abos.<id>` | abos.py, module.py | abos.py |
| `accounts.example.yaml` | Konto: `accounts[].id` | kein Modul | Hand |
| `accounts.yaml` | Konto: `accounts[].id` | konten.py, module.py, r/einrichtung.py | Hand |
| `adjustments.yaml` | Korrektur: `corrections[]`, ohne Kennung (leer) | ingest/importer.py | Hand |
| `assumptions.yaml` | Einstellung: Pfad (`kapital.rendite_depot_pa`) | assumptions.py, vorgaben/__init__.py, r/einrichtung.py | Hand |
| `assumptions.optimistisch.yaml`, `assumptions.pessimistisch.yaml` | Einstellung: Pfad; dazu `immobilien.objekte.<id>.…` | assumptions.py (`finctl jahre --szenario`), objekte.py | Hand |
| `backup.yaml` | Einstellung: `directory`, `keep` | ops.py | Hand |
| `balances.yaml` | Bestand: `balances[].account_id`; Verpflichtung: `obligations[].name` (ein Name, keine Kennung); Einstellung: `as_of` | bestaende.py, cli.py, vorgaben/__init__.py, r/annahmen, auswertung, einrichtung, konten, planung, ziele | Hand |
| `balances_custom.yaml` | Bestand: `overrides.<account_id oder name>`; Verpflichtung: `verpflichtungen.<name kleingeschrieben>`; Beleg: `verlauf.<Position>.<Periode>` | bestaende.py, cli.py, module.py, r/annahmen, auswertung, konten, planung, ziele | r/konten.py |
| `forecast.yaml` | Konto-Regel: `account_roles.<konto>`; Budget: `account_budgets.<konto>` (nur eine Zahl); sonst Einstellung: Pfad | forecast/konten.py, kontenregeln.py, r/auswertung, konten, planung | Hand |
| `forecast_custom.yaml` | `account_roles.<konto>`, `account_budgets.<konto>` | kontenregeln.py | kontenregeln.py |
| `geteilt_custom.yaml` | Projekt: `projekte[].id`; `personen[]` und `buchungen[]` ohne Kennung | geteilt.py, module.py | geteilt.py |
| `goals.yaml` | Ziel: `ziele[].id` | cli.py, module.py, monatsabschluss.py, vorgaben/__init__.py, r/annahmen, auswertung, einrichtung, planung, ziele | Hand |
| `groups.yaml` | Gruppe: `gruppen[].id` | ledger/gruppen.py, vorgaben/__init__.py | Hand |
| `lebensplan.yaml` | Einstellung: Pfad (`person.*`, `schwellen.*`, …) | person.py, vorgaben/__init__.py, r/einrichtung | Hand |
| `loans.yaml` | Kredit: `loans[].id` | cli.py, forecast/konten.py, kredite.py, module.py, realestate/kpi.py, realestate/loan.py, r/einrichtung, r/kredite, web/verkauf.py | Hand |
| `loans_custom.yaml` | Kredit: `kredite.<id>`, `anschluss.<id>`, `vorlagen.<id>` | fristen.py, kredite.py, module.py, realestate/loan.py, r/kredite | kredite.py, r/kredite.py (zwei Stellen) |
| `overrides.yaml` | Handentscheidung: `overrides[]`, erkannt am `dedup_hash` | rules/categorize.py | rules/categorize.py, r/kategorien.py, tax/taxonomy.py (Umbenennung) |
| `properties.yaml` | Objekt: `properties[].id` | module.py, objekte.py, r/einrichtung | Hand |
| `properties_custom.yaml` | Objekt: `objekte.<id>` | module.py, objekte.py, overlays.py | objekte.py, overlays.py |
| `renten.yaml` | Rente: `renten[].id` | renten.py, r/einrichtung | Hand |
| `renten_custom.yaml` | Rente: `renten.<id>`, `neu[].id` | module.py, renten.py | renten.py |
| `rules.yaml` | Regel: `rules[].id` | rules/engine.py, vorgaben/__init__.py, r/einrichtung | Hand; als Text: `engine.repoint_rule`, `engine.grundschicht_setzen` |
| `server.yaml` | Einstellung: `host`, `port`, `passwort_hash`, `geheimnis` | web/auth.py | web/auth.py (`finctl passwort`) |
| `settings_custom.yaml` | Einstellung: `einstellungen.<Schlüssel>`; bei `floor_cents:<konto>` steht die Kennung im Schlüssel | overlays.py | overlays.py |
| `strom.yaml` | `zeitraeume[]`, `ablesungen[]`, ohne Kennung | module.py, strom.py | strom.py |
| `szenarien.yaml` | Klammer: `szenarien[].id`; darin `zeilen[]` | forecast/jahre.py, forecast/konten.py, forecast/szenarien.py, module.py, monatsabschluss.py, r/annahmen, einrichtung, planung | r/planung.py |
| `taxonomy.yaml` | Kategorie: `management.<ober>` und `….children.<blatt>`; ebenso `tax` | cli.py, nachfuehren.py, tax/taxonomy.py, vorgaben/__init__.py | Hand; als Text: `nachfuehren.taxonomie` |
| `taxonomy_custom.yaml` | wie `taxonomy.yaml` | tax/taxonomy.py | tax/taxonomy.py (`save_custom`) |
| `taxonomy_migrations.yaml` | `remap.<alt>` (Name auf Name), `retire[]` | tax/taxonomy.py | tax/taxonomy.py (`add_migration`) |
| `verbotene_namen.yaml` | Liste von Namen | nur Tests | Hand |
| `versicherungen.yaml` | Versicherung: `versicherungen[].id` (leer) | abos.py, module.py | Hand |
| `versicherungen_custom.yaml` | Versicherung: `versicherungen.<id>` | abos.py, module.py | abos.py |
| `ziele_custom.yaml` | Ziel: `ziele.<id>`, `reihenfolge[]` | cli.py, module.py, monatsabschluss.py, r/annahmen, auswertung, einrichtung, ziele | r/ziele.py |

Im Musterhaushalt kommt `zinssaetze_custom.yaml` dazu (`zinssaetze.<konto>[]`, Zeilen ohne Kennung; liest zinssaetze.py und module.py, schreibt zinssaetze.py). In `finctl/vorgaben/` liegen dieselben Arten: `assumptions`, `balances`, `goals`, `groups`, `lebensplan`, `rules`, `taxonomy`, dazu `regeln_allgemein.yaml` (Regel: `rules[].id`, gelesen von rules/engine.py als Grundschicht).

**Tabelle B: Kommentarzeilen je Datei und Lage.** Spalten: Zeilen der Datei; K, A, E, F, S, – wie oben; Σ = Kommentarzeilen; App-Kopf = Kopfzeilen, die wörtlich mit einer Konstante der App übereinstimmen; Euro (F) und Euro (S) = Kommentare, die nur den Wert des Feldes in Euro wiederholen, in der Lage Feld bzw. Einstellung.

Entwicklungskopie:

| Datei | Zeilen | K | A | E | F | S | – | Σ | App-Kopf | Euro (F) | Euro (S) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `abos.yaml` | 48 | 13 | 0 | 0 | 0 | 0 | 0 | 13 |  |  |  |
| `abos_custom.yaml` | 235 | 8 | 0 | 0 | 0 | 0 | 0 | 8 | 8 |  |  |
| `accounts.example.yaml` | 68 | 12 | 0 | 5 | 1 | 0 | 0 | 18 |  |  |  |
| `accounts.yaml` | 108 | 13 | 0 | 18 | 5 | 0 | 0 | 36 |  |  |  |
| `adjustments.yaml` | 18 | 16 | 0 | 0 | 0 | 0 | 0 | 16 |  |  |  |
| `assumptions.optimistisch.yaml` | 49 | 15 | 0 | 0 | 0 | 6 | 0 | 21 |  |  | 2 |
| `assumptions.pessimistisch.yaml` | 50 | 16 | 0 | 0 | 0 | 6 | 0 | 22 |  |  | 2 |
| `assumptions.yaml` | 151 | 20 | 20 | 0 | 0 | 77 | 0 | 117 |  |  | 1 |
| `backup.yaml` | 14 | 5 | 0 | 0 | 0 | 5 | 0 | 10 |  |  |  |
| `balances.yaml` | 195 | 58 | 0 | 18 | 7 | 0 | 0 | 83 |  | 2 |  |
| `balances_custom.yaml` | 57 | 13 | 0 | 0 | 0 | 0 | 0 | 13 | 13 |  |  |
| `forecast.yaml` | 257 | 7 | 7 | 66 | 5 | 81 | 16 | 182 |  | 3 |  |
| `forecast_custom.yaml` | 22 | 6 | 0 | 0 | 0 | 0 | 0 | 6 | 6 |  |  |
| `geteilt_custom.yaml` | 13 | 6 | 0 | 0 | 0 | 0 | 0 | 6 | 6 |  |  |
| `goals.yaml` | 56 | 41 | 0 | 0 | 0 | 0 | 4 | 45 |  |  |  |
| `groups.yaml` | 51 | 25 | 0 | 11 | 0 | 0 | 0 | 36 |  |  |  |
| `lebensplan.yaml` | 108 | 17 | 5 | 0 | 0 | 58 | 0 | 80 |  |  |  |
| `loans.yaml` | 288 | 11 | 0 | 136 | 33 | 0 | 0 | 180 |  | 11 |  |
| `loans_custom.yaml` | 19 | 11 | 0 | 0 | 0 | 0 | 0 | 11 | 11 |  |  |
| `overrides.yaml` | 12335 | 9 | 0 | 0 | 0 | 0 | 0 | 9 | 9 |  |  |
| `properties.yaml` | 290 | 7 | 0 | 179 | 15 | 0 | 0 | 201 |  | 4 |  |
| `properties_custom.yaml` | 15 | 11 | 0 | 0 | 0 | 0 | 0 | 11 | 11 |  |  |
| `renten.yaml` | 69 | 16 | 1 | 23 | 4 | 0 | 0 | 44 |  | 2 |  |
| `renten_custom.yaml` | 38 | 4 | 0 | 2 | 6 | 0 | 0 | 12 |  |  |  |
| `rules.yaml` | 1162 | 19 | 96 | 199 | 1 | 0 | 0 | 315 |  |  |  |
| `server.yaml` | 12 | 9 | 0 | 0 | 0 | 0 | 0 | 9 | 9 |  |  |
| `settings_custom.yaml` | 17 | 9 | 0 | 0 | 0 | 0 | 0 | 9 | 9 |  |  |
| `strom.yaml` | 23 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 5 |  |  |
| `szenarien.yaml` | 357 | 9 | 0 | 0 | 0 | 0 | 0 | 9 | 9 |  |  |
| `taxonomy.yaml` | 433 | 27 | 17 | 127 | 0 | 0 | 0 | 171 |  |  |  |
| `taxonomy_custom.yaml` | 15 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 5 |  |  |
| `taxonomy_migrations.yaml` | 66 | 7 | 0 | 20 | 0 | 2 | 0 | 29 |  |  |  |
| `verbotene_namen.yaml` | 30 | 10 | 0 | 0 | 0 | 0 | 0 | 10 |  |  |  |
| `versicherungen.yaml` | 12 | 10 | 0 | 0 | 0 | 0 | 0 | 10 |  |  |  |
| `versicherungen_custom.yaml` | 202 | 8 | 0 | 0 | 0 | 0 | 0 | 8 | 8 |  |  |
| `ziele_custom.yaml` | 40 | 10 | 0 | 0 | 0 | 0 | 0 | 10 |  |  |  |
| **Summe** | | 488 | 146 | 804 | 77 | 235 | 20 | 1770 | 109 | 22 | 5 |

Musterhaushalt (nach dem Datieren):

| Datei | Zeilen | K | A | E | F | S | – | Σ | App-Kopf | Euro (F) | Euro (S) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `abos.yaml` | 24 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |  |  |  |
| `abos_custom.yaml` | 17 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |  |  |  |
| `accounts.yaml` | 52 | 5 | 0 | 2 | 0 | 0 | 0 | 7 |  |  |  |
| `adjustments.yaml` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  |
| `assumptions.optimistisch.yaml` | 20 | 1 | 0 | 0 | 0 | 2 | 0 | 3 |  |  |  |
| `assumptions.pessimistisch.yaml` | 24 | 1 | 0 | 0 | 0 | 2 | 0 | 3 |  |  |  |
| `assumptions.yaml` | 20 | 1 | 0 | 0 | 0 | 2 | 0 | 3 |  |  |  |
| `backup.yaml` | 4 | 2 | 0 | 0 | 0 | 0 | 0 | 2 |  |  |  |
| `balances.yaml` | 56 | 1 | 0 | 0 | 9 | 0 | 0 | 10 |  | 4 |  |
| `balances_custom.yaml` | 19 | 0 | 0 | 0 | 0 | 0 | 3 | 3 |  |  |  |
| `forecast.yaml` | 42 | 1 | 0 | 0 | 4 | 0 | 0 | 5 |  | 1 |  |
| `forecast_custom.yaml` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  |
| `goals.yaml` | 10 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |  |  |  |
| `groups.yaml` | 15 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |  |  |  |
| `lebensplan.yaml` | 19 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |  |  |  |
| `loans.yaml` | 99 | 4 | 0 | 6 | 8 | 0 | 0 | 18 |  | 8 |  |
| `loans_custom.yaml` | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  |
| `overrides.yaml` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  |
| `properties.yaml` | 60 | 4 | 0 | 0 | 5 | 0 | 0 | 9 |  | 5 |  |
| `properties_custom.yaml` | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  |
| `renten.yaml` | 32 | 1 | 0 | 0 | 7 | 0 | 0 | 8 |  | 2 |  |
| `renten_custom.yaml` | 14 | 2 | 0 | 0 | 4 | 0 | 0 | 6 |  |  |  |
| `rules.yaml` | 249 | 5 | 0 | 6 | 0 | 0 | 0 | 11 |  |  |  |
| `settings_custom.yaml` | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  |
| `strom.yaml` | 19 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |  |  |  |
| `szenarien.yaml` | 150 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |  |  |  |
| `taxonomy_custom.yaml` | 12 | 0 | 0 | 2 | 0 | 0 | 0 | 2 |  |  |  |
| `taxonomy_migrations.yaml` | 5 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |  |  |  |
| `versicherungen.yaml` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  |
| `versicherungen_custom.yaml` | 29 | 1 | 0 | 0 | 0 | 0 | 0 | 1 |  |  |  |
| `ziele_custom.yaml` | 24 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  |  |
| `zinssaetze_custom.yaml` | 9 | 4 | 0 | 0 | 0 | 0 | 0 | 4 |  |  |  |
| **Summe** | | 41 | 0 | 16 | 37 | 6 | 3 | 103 | 0 | 20 | 0 |

Vorgaben:

| Datei | Zeilen | K | A | E | F | S | – | Σ | App-Kopf | Euro (F) | Euro (S) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `assumptions.yaml` | 67 | 9 | 1 | 0 | 0 | 31 | 0 | 41 |  |  |  |
| `balances.yaml` | 11 | 7 | 0 | 0 | 0 | 0 | 0 | 7 |  |  |  |
| `goals.yaml` | 45 | 39 | 0 | 0 | 0 | 0 | 0 | 39 |  |  |  |
| `groups.yaml` | 32 | 30 | 0 | 0 | 0 | 0 | 0 | 30 |  |  |  |
| `lebensplan.yaml` | 29 | 8 | 0 | 0 | 0 | 5 | 0 | 13 |  |  |  |
| `regeln_allgemein.yaml` | 255 | 20 | 0 | 8 | 0 | 0 | 0 | 28 |  |  |  |
| `rules.yaml` | 22 | 19 | 0 | 0 | 0 | 0 | 0 | 19 |  |  |  |
| `taxonomy.yaml` | 454 | 45 | 17 | 129 | 0 | 0 | 0 | 191 |  |  |  |
| **Summe** | | 177 | 18 | 137 | 0 | 36 | 0 | 368 | 0 | 0 | 0 |

**Stellen, die in keine Lage passen** (nur Ort):

- `forecast.yaml:74–83` und `forecast.yaml:107–112`: Block direkt über dem Schlüssel einer Zuordnung nach Konto (`account_budgets`, `account_roles`). Der Schlüssel ist weder Eintrag noch Einstellung, und der Block gilt der ganzen Zuordnung. Am nächsten liegt ein Abschnitt ohne Leerzeile davor.
- `goals.yaml:53–56`: Block am Ende der Datei, vor nichts.
- Musterhaushalt `balances_custom.yaml:6–8`: dasselbe wie bei `forecast.yaml`, über `verlauf`.

**Grenzfälle**, die ich nach dem Wortlaut der Lagen zugeordnet habe, wo aber auch eine andere passte (Ort):

- Strichlinie direkt über einem Eintrag, ohne Leerzeile danach (Eintrag oder Abschnitt?): `balances.yaml:64`, `:90`, `:157`; `vorgaben/regeln_allgemein.yaml:24`, `:31`, `:51`, `:76`, `:89`, `:145`, `:165`, `:244`. In der Datei `rules.yaml` der Entwicklungskopie steht nach jeder Strichlinie eine Leerzeile, dort ist es eindeutig ein Abschnitt.
- Block mit Leerzeile danach zwischen zwei Einstellungen einer Gruppe (Abschnitt oder Einstellung?): `assumptions.yaml:42`.
- Block vor dem ersten Schlüssel, direkt über einer Einstellung (Kopf oder Einstellung?): `assumptions.yaml:19–22`; `vorgaben/assumptions.yaml:10`; `vorgaben/rules.yaml:1–19`; Musterhaushalt `backup.yaml:1–2`.

**Paare.** Eine Seite schreibt immer die `_custom`-Datei, nie die Basisdatei. „Gewinn“ heißt: wer gilt, wenn beide dasselbe Feld nennen. Wo „je Feld“ steht, ist das Feld aus `{**basis, **eigen}`, wo eine Liste steht, nur aus dieser Liste. `entfernt: true` (bei Verpflichtungen `geloescht: true`) blendet einen Basiseintrag aus; ein Eintrag, den es nur in `_custom` gibt, gilt trotzdem.

| Paar (Basis ↔ Seite) | legt zusammen | gewinnt | Besonderheit |
|---|---|---|---|
| `abos` ↔ `abos_custom` | `abos.laden` | je Feld, je Kennung | Herkunft `basis`, `geaendert` oder `eigen` steht am Ergebnis |
| `versicherungen` ↔ `versicherungen_custom` | `abos.laden(art="versicherung")` | wie Abos | gleiche Maschine (`ARTEN` in abos.py); `alle_vertraege` wirft bei einer Kennung in beiden Arten |
| `balances` ↔ `balances_custom` | `bestaende.zusammenfuehren` (Bestände), `bestaende.verpflichtungen` | je Feld, aber nur aus einer Liste: Bestand `cents`, `as_of`, `gewinn_cents`, die vier Rückkauf-Felder, `note`; Verpflichtung `cents`, `note`, `name` | bei einem Konto mit Auszug zählt allein `note`; `verlauf` hat keine Basis; acht Module nennen `balances_custom.yaml` |
| `goals` ↔ `ziele_custom` | `forecast.ziele.merge_edits` | je Feld, je Kennung | `reihenfolge` gibt es nur in `_custom`; ein Eintrag nur dort bekommt `eigen: True`; ein Notgroschen ohne Betrag bekommt danach eine Vorgabe; sechs Module rufen `merge_edits` mit beiden Dateien auf, sieben Stellen (cli.py, monatsabschluss.py, r/ziele, r/annahmen zweimal, r/einrichtung, r/auswertung) |
| `loans` ↔ `loans_custom` | `realestate.loan.lade_kredite` | `kredite.<id>`: je Feld; `vorlagen.<id>`: ersetzt die Grundkonditionen eines Kredits an einer Klammer (`mit_vorlage` baut ein Segment neu) | `anschluss.<id>` wird dort **nicht** zugelegt: nur `/kredite` (r/kredite.py) und `fristen.py` lesen es, die Prognose sieht es nicht |
| `properties` ↔ `properties_custom` | `objekte.vorhandene` | je Feld, `prognose` je Unterfeld | `overlays.anwenden` spiegelt zehn Felder bei `finctl init` in die Tabelle `properties` |
| `forecast` ↔ `forecast_custom` | `kontenregeln.zusammenfuehren` | je Konto, je Feld aus `role`, `note`, `floor_cents`, `ceiling_cents`, `sweep_to`, `auffuellen`, `floor_from_loan`; ein Budget je Konto ersetzt, ein leeres entfernt es | die Untergrenze aus der Seite liegt zusätzlich in `settings_custom` und gilt vor beiden |
| `renten` ↔ `renten_custom` | `renten.quellen` | je Feld, aber nur `cents`, `ab`, `stand`, `kosten_pa`, `beitrag`, `pruefwert`, `stand_cents`, `stand_wert`, `beitrag_ag_cents`, `notiz` | `notiz` wird nur aus `_custom` gelesen; `herleitung`, `art`, `kaufkraft`, `konto`, `name` nur aus der Basis; `neu:` sind Quellen nur in `_custom` |
| `taxonomy` ↔ `taxonomy_custom` | `tax.taxonomy.load_spec` | je Blatt (das Blatt ersetzt, der Name des Oberbegriffs ersetzt); `kind` und die übrigen Merkmale zählen nur bei einem Oberbegriff, den es in der Basis nicht gibt | beide Achsen, `management` und `tax`; liest mit `safe_load`, nicht mit `yaml_lesen` |
| `rules` ↔ `rules_custom` (nicht in der Kopie) | `rules.engine.rohe_regeln` | je Feld; `match` und `set` ersetzt die Kopie als Ganzes | **fehlt in der Paarliste des Befunds**; zwei Funktionen ändern `rules.yaml` als Text |
| `accounts` ↔ `accounts_custom` (nicht in der Kopie) | `konten.laden` | je Feld, je Kennung | beim Speichern bleibt nur, was in `konten.FELDER` steht |
| `lebensplan` ↔ `lebensplan_custom` (nicht in der Kopie) | `person.angaben` | nur drei Angaben | Namen weichen ab: `geburtsdatum` ↔ `person.birth_date`, `rente_ab_alter` ↔ `schwellen.grv_ab_alter`, `krankenversicherung` gleich |
| `backup` ↔ `backup_custom` (nicht in der Kopie) | `ops.backup_settings`: `{**spec, **overlays.sicherung()}` | je Schlüssel (`directory`, `keep`) | die Seite `/system` schreibt `backup_custom.yaml`; `backup.yaml` hat also eine Seite, anders als Entscheidung 7 |

Eine `_custom`-Datei ohne Basis behält nach Entscheidung 5 ihren Namen: `geteilt_custom` (liegt in der Kopie), `reihen_custom`, `zinssaetze_custom`, `module_custom`, `csv_profile_custom`, `prognosebasis_custom`.

**Kennt der Code, liegt aber nicht in der Entwicklungskopie:** neun `_custom`-Dateien: `accounts`, `lebensplan`, `backup`, `rules`, `reihen`, `zinssaetze`, `module`, `csv_profile`, `prognosebasis`. Der Befund nannte sechs; neu sind `rules_custom` (ein Paar mit Basisdatei), `csv_profile_custom` (schreibt ingest/zuordnung.py) und `prognosebasis_custom` (schreibt forecast/prognosebasis.py). Im Musterhaushalt liegt davon nur `zinssaetze_custom`. Elf `_custom`-Dateien liegen in der Kopie (`abos`, `balances`, `forecast`, `geteilt`, `loans`, `properties`, `renten`, `settings`, `taxonomy`, `versicherungen`, `ziele`). Der Docstring von `forecast/szenarien.py` nennt noch `scenarios_custom.yaml`; die Datei heißt `szenarien.yaml`.

**`settings_custom.yaml`.** Gelesen von `overlays.einstellungen`, geschrieben von `overlays.einstellung_setzen`. Zwei Arten von Schlüsseln:

- Die zwölf Stellschrauben `inflation_pa`, `rendite_nominal_pa`, `rendite_depot_pa`, `sparerpauschbetrag_cents`, `kostenschwelle_pa`, `gehalt_steigerung_pa`, `salary_floor_cents`, `teilzeit_anteil`, `teilzeit_ab`, `lebenserwartung`, `abzug_renten`, `aufbrauchen` überschreiben in **`assumptions.yaml`** den Pfad aus `UEBERSCHREIBBAR` (`assumptions.py`, `load`, tiefe Kopie vor dem Überschreiben). Nur für die Datei selbst: eine Szenariodatei bekommt kein Overlay. Gesetzt von `/api/setting` (r/annahmen.py). In der Kopie stehen `teilzeit_anteil` und `teilzeit_ab`; beide gibt es in der Basisdatei nicht, `load` legt sie unter `erwerbseinkommen` an.
- `floor_cents:<konto>` überschreibt in **`forecast.yaml`** den Wert `account_roles.<konto>.floor_cents`. Gelesen in `forecast/konten.py`, `_floor_for`, aus der Tabelle `settings`; Vorrang: `floor_from_loan`, dann `settings`, dann `account_roles.<konto>.floor_cents` (Basis samt `forecast_custom`), dann die Dispo-Schwelle des Kontos. Gesetzt von `/api/floor` und `/api/konto` (r/konten.py). In der Kopie stehen vier.
- Beide Arten gehen auch in die Tabelle `settings` (beim Setzen und bei `finctl init` über `overlays.anwenden`): Die Werte haben zwei Ziele, Datei und Datenbank.

**Leser.** Eine Probekopie (Probe C in `notizen/N.0_bestand.md`) und die ganze Suite sagen: Mit `notiz` und `notiz_vom` an jedem Eintrag mit Kennung und `notizen:` am Ende jeder Datei (außer den Dateien ohne Seite) scheitert kein Leser: 1972 Tests bestehen, rot ist nur der Referenztest, und zwar an den vier Seiten, die schon eine Notiz zeigen und sie jetzt zeigen. Ich habe keinen Leser gefunden, der über alle Schlüssel einer Datei läuft. Anders ist es bei Zuordnungen, deren Schlüssel selbst die Daten sind; ein Schlüssel `notiz` darin wird gelesen:

| Stelle | Ergebnis bei einem Schlüssel `notiz` |
|---|---|
| `forecast.yaml`, `overrides` (`forecast/konten.py`, `_income_overrides`) | scheitert: `int()` |
| `forecast.yaml`, `enden` (`_as_month`) | scheitert: kein Datum |
| `forecast.yaml`, `account_budgets` (`forecast/konten.py`, `kontenregeln.zusammenfuehren`) | nimmt ihn als Konto mit Budget; ändert `/konten`, Bestände, Monatsabschluss, Start und die Kontoprognose |
| `taxonomy.yaml`, `children` (`tax/taxonomy.py`, `load_into_db`) | nimmt ihn als Kategorie `<ober>/notiz` |
| `settings_custom.yaml`, `einstellungen` (`overlays.anwenden`) | nimmt ihn als Einstellung: eine Zeile in `settings` |
| `taxonomy_migrations.yaml`, `remap` | nimmt ihn als Umbenennung, ohne sichtbare Wirkung |
| `zinssaetze.lesen` (Konto → Zeilen), aus dem Code gelesen | scheitert in `_satz` |
| `reihen.zusammen` (Schreibweise → Gegenpartei), aus dem Code gelesen | nimmt ihn als Schreibweise |
| `assumptions.yaml`, `kapital`; `lebensplan.yaml`, `schwellen` und `person`; `forecast.yaml`, `cashflow_ohne_objekt` | unverändert: gelesen wird über benannte Schlüssel |

Eine Notiz gehört also an den Eintrag oder unter `notizen:` am Dateikopf, nie in eine dieser Zuordnungen. Ein Eintrag, der nur eine Zahl oder ein Name ist, hat keinen Platz für eine Notiz: das Budget je Konto (`account_budgets`), das Blatt einer Kategorie (`children`, es sei denn, das Blatt wird zu `{name: …}`, was `load_into_db` kennt), `remap`. Einträge ohne Kennung: `strom.yaml` (`zeitraeume`, `ablesungen`), `szenarien[].zeilen`, die Zeilen in `zinssaetze`, `reihen[]` (erkannt an `buchungen`), `personen` und `buchungen` in `geteilt_custom.yaml`, `corrections[]`, die Handentscheidungen in `overrides.yaml` (erkannt am `dedup_hash`).

**Notizen unter anderem Namen.**

| Feld | Ort | gehört zu | Einordnung |
|---|---|---|---|
| `herleitung` | `renten[]` (3) | Rente | Notiz; nur aus der Basis gelesen, `/renten` zeigt `notiz or herleitung` |
| `note` | `balances[]`, `obligations[]` (10), `overrides.<k>`, `verpflichtungen.<k>` (6) | Bestand, Verpflichtung | Notiz; die Felder der Oberfläche heißen `note` |
| `note` | `account_roles.<konto>` in `forecast.yaml` (6) und `forecast_custom.yaml` (5) | Konto-Regel | Notiz der Konto-Regel; gehört zum Konto, steht aber nicht in `accounts.yaml` |
| `warum` | `abos[]` (2), `abos.<id>` (1) | Abo | Notiz; Feld „Warum“ auf `/abos` |
| `note` | `loans[]` (1) | Kredit | Notiz; von keinem Modul gelesen |
| `note` | `loans[].segments_observed[]` (2) | Teilstück eines Kredits | keine Notiz des Eintrags; von keinem Modul gelesen |
| `open` | `loans[]` (2), `properties[]` (2) | Kredit, Objekt | Liste von Freitexten; nur die der Kredite zeigt `/kredite` |
| `quelle` | `ziele[]` (1) | Ziel | Notiz; von keinem Modul gelesen |
| `notiz` | `ziele.<id>` (3), `renten.<id>` (1) | Ziel, Rente | schon Notiz |

Keine Notiz sind `set.note` einer Regel (26: Text, den die Regel an eine Buchung schreibt) und `label` in `szenarien[].zeilen[]` (36: Bezeichnung einer Planzeile).

**Köpfe der App.** 27 Texte in 24 Modulen werden über Dateien geschrieben: `overlays.EINSTELLUNGEN_KOPF` → `settings_custom`; `overlays.OBJEKTE_KOPF` und `objekte.KOPF` → `properties_custom`; `overlays.SICHERUNG_KOPF` → `backup_custom`; `abos.CUSTOM_KOPF` (mit `{seite}`, `{basis}`) → `abos_custom`, `versicherungen_custom`; `kredite.KOPF` und zwei Texte in `r/kredite.py` → `loans_custom`; `konten.KOPF` → `accounts_custom`; `person.KOPF` → `lebensplan_custom`; `renten.KOPF` → `renten_custom`; `reihen.KOPF` → `reihen_custom`; `zinssaetze.KOPF` → `zinssaetze_custom`; `module.KOPF` → `module_custom`; `geteilt.KOPF` → `geteilt_custom`; `forecast/prognosebasis.KOPF` → `prognosebasis_custom`; `ingest/zuordnung.KOPF` → `csv_profile_custom`; `rules/regelwerk.KOPF` → `rules_custom`; `r/konten.OVERLAY_KOPF` → `balances_custom`; Texte in `r/ziele.py` → `ziele_custom`, in `kontenregeln.py` → `forecast_custom`, in `tax/taxonomy.py` (`save_custom`, englisch) → `taxonomy_custom`; außerhalb der `_custom`-Dateien `strom.KOPF` → `strom.yaml`, `r/planung.SZENARIEN_HEADER` → `szenarien.yaml`, `web/auth.KOPF` → `server.yaml`, `energie/speicher.KOPF` → `energie.yaml` (nicht in der Kopie), ein Text in `rules/categorize.py` (englisch) → `overrides.yaml`.

In der Entwicklungskopie stimmen **13 Köpfe wörtlich** mit einer Konstante überein, zusammen 109 Zeilen: `abos_custom`, `balances_custom`, `forecast_custom`, `geteilt_custom`, `loans_custom`, `properties_custom`, `settings_custom`, `taxonomy_custom`, `versicherungen_custom` (77 Zeilen) und `overrides.yaml`, `server.yaml`, `strom.yaml`, `szenarien.yaml` (32 Zeilen). Zwei stimmen nicht: `renten_custom.yaml` (der Kopf ist eine ältere Fassung: zwei der fünf Zeilen der Konstante fehlen oder stehen anders) und `ziele_custom.yaml` (eine von zehn Zeilen weicht in einer Zahl ab). Nach Entscheidung 3 fielen beide nicht weg, sondern gingen in die Notiz des Bereichs. Zwei Dateien haben mehrere Konstanten: `properties_custom` zwei, `loans_custom` drei; der Kopf in der Datei ist der des letzten Schreibers, der Vergleich muss also gegen alle Texte der Datei laufen. Im Musterhaushalt stimmt kein Kopf mit einer Konstante überein, in `finctl/vorgaben/` schreibt die App keinen.

**Feldkommentare, die nur den Wert in Euro wiederholen.** Eine Regel erkennt sie sicher, wenn alle vier Bedingungen gelten:

1. Der Feldname ist `cents` oder endet auf `_cents`, und der Wert ist eine ganze Zahl.
2. Der Kommentar besteht nach dem `#` aus nichts als einer Zahl in deutscher Schreibweise (Tausenderpunkt, Dezimalkomma), höchstens mit einem `€`, `EUR` oder `Euro` dahinter; kein `~` davor, keine Fortsetzungszeile.
3. Zahl mal 100 ist der Wert, genau.
4. Die Zeile liegt in der Lage Feld.

Entwicklungskopie: **22** Kommentare erfüllen das (`balances` 2, `forecast` 3, `loans` 11, `properties` 4, `renten` 2). Dazu **5** in den drei `assumptions*.yaml`: dieselbe Form, aber Lage Einstellung, und Entscheidung 3 nennt nur Feldkommentare; das entscheidet Opus. Musterhaushalt: 20 (`balances` 4, `forecast` 1, `loans` 8, `properties` 5, `renten` 2). Vorgaben: keine. Weitere 17 in der Kopie und 9 im Musterhaushalt beginnen mit dem Wert in Euro und sagen etwas dazu: Sie bleiben. Kein Kommentar nennt eine Zahl, die vom Wert abweicht.

**Für Opus: was daraus für N.1 bis N.3 folgt.** Das steht auch unter „Gefundene Abweichungen“.

- Reihenfolge der Bereiche für N.3 nach der Zahl der Module, die beide Dateien nennen: `forecast` (1: kontenregeln.py), `taxonomy` (1: tax/taxonomy.py), `renten` (2), `abos` und `versicherungen` (2: abos.py, module.py), `properties` (3, dazu die Spiegelung bei `init`), `loans` (5, dazu die offene Frage zu `anschluss`), `ziele` (7), `balances` (8), `settings` zuletzt.
- Die zusammengelegten Dateien tragen Notizen nur an Einträgen und unter `notizen:`. Der Umwandler darf nie `notiz` in eine der Zuordnungen schreiben (Tabelle der Leser).

**Abgenommen am 07.10.2026 (Opus).** Nachgeprüft:
- Die Textschreiber in `rules/engine.py` hängen an der Einrückung (`"\n  - id: "`).
- `anschluss` aus `loans_custom.yaml` lesen nur `r/kredite.py` und `fristen.py`, die
  Prognose liest das `anschluss` der Basis.

Die Bestandsaufnahme gilt. Zu den Abweichungen (Nummern wie unter „Gefundene Abweichungen“):

1. **Textschreiber werden strukturiert.** Sie schreiben als Text, um Kommentare zu
   schonen. Nach N.2 gibt es keine mehr. N.2 stellt deshalb `engine.repoint_rule`,
   `engine.grundschicht_setzen` und `nachfuehren.taxonomie` auf Lesen, Ändern,
   Schreiben über `finctl/dateien.py` um, im selben Commit wie der Umwandler und nicht
   früher. Vorher würden sie Kommentare löschen, die noch nicht übernommen sind.
   `overrides.yaml` bleibt, wie es ist: Das Schneiden bei `overrides:` hängt an keinem
   Kommentar. Der Umwandler läuft vor dem Nachführen, und die App hält bei alter
   Form an, bevor sie nachführt.
2. **`rules`, `csv_profile`, `prognosebasis`:** `rules` ist ein Paar und kommt in N.3.
   Die beiden anderen haben keine Basis und behalten ihren Namen (Entscheidung 5). Den
   Docstring mit `scenarios_custom.yaml` richtet N.3 nebenbei.
3. **`backup.yaml` hat eine Seite** und wird damit wie jede andere Datei umgestellt:
   Seine Kommentare werden Notizen, und das Paar wird in N.3 zusammengelegt.
   Entscheidung 7 ist entsprechend geändert. `server.yaml` bleibt in Entscheidung 7: Der
   Umwandler fasst es nicht an, und sein einziger Kommentar ist der Kopf der App.
4. **`anschluss` aus `loans_custom.yaml`** wird ein eigener Schlüssel am Kredit, den die
   Prognose nicht liest, benannt nach dem, was `/kredite` dazu sagt. Ob eine dort
   eingetragene Anschlusskondition in die Prognose gehört, ist eine gewollte Frage für
   später, nicht für Schritt 5.
5. **`lebensplan_custom`:** Der Umwandler benennt um, wie im Befund. Getestet wird mit
   einem erfundenen Datenordner (N.3).
6. **Renten lesen `notiz` aus jeder Datei:** gehört zu N.1.
7. **Anzeigen, die vom Paar leben.** Nach N.3 gibt es keine Basis mehr. Damit
   verschwinden „überschrieben, Basis …“, `base_note`, die Herkunft (`basis`,
   `geaendert`, `eigen`), `basis_cents`/`basis_ab` und die dokumentierte Vorgabe auf
   `/annahmen`. Ebenso fällt das Speichern nur der Abweichung weg: Die Schreiber
   schreiben den ganzen Eintrag. **Ein überschriebener Wert geht dabei nicht verloren.**
   Hatte die `_custom`-Datei einen Wert der Basis überschrieben, hält der Umwandler den
   alten Wert in der Notiz fest („Bis zur Umstellung stand in der Datei: …“). N.3 ist
   damit **gleich in den Zahlen**, nicht streng. Auf der Zahlenebene dürfen nur Zeilen
   wegfallen, die einen Wert der Basis neben dem gültigen zeigten. Opus schreibt die
   Referenz nach jeder Gruppe von N.3 neu.
8. **Notizen ohne eigenen Platz:**
   - Der Kommentar zu einem Budget geht in die Notiz der Konto-Regel desselben Kontos,
     eingeleitet mit „Budget:“.
   - Der Kommentar zu einem Blatt der Taxonomie geht in die Notiz des Oberbegriffs,
     eingeleitet mit dem Namen des Blatts.
   - Eine Zeile einer Klammer gehört zur Notiz der Klammer.
   - Alles andere ohne Kennung kommt in die Notiz des Bereichs, mit dem Hinweis, vor
     welcher Stelle es stand: `strom`, `corrections`, `personen` und `buchungen` in
     `geteilt`, die Zeilen in `zinssaetze`.
   - In die Zuordnungen aus der Tabelle „Leser“ schreibt der Umwandler nie etwas.
9. **Köpfe der App.** Ein Kopf, der wörtlich einer der Konstanten entspricht, die über
   diese Datei geschrieben werden, fällt weg. Verglichen wird gegen alle Konstanten der
   Datei. Das gilt auch für `strom`, `szenarien` und `overrides`: Schreibt die App die
   Datei wieder, setzt sie ihren Kopf selbst. Die abweichenden Köpfe von `renten_custom`
   und `ziele_custom` gehen in die Notiz des Bereichs, wie Entscheidung 3 sagt. Der
   Haushalt löscht sie dort mit einem Klick.
10. **Grenzfälle der Lagen.**
    - Eine Strichlinie beginnt immer einen Abschnitt, mit oder ohne Leerzeile danach.
    - Was ohne Leerzeile direkt über einem Schlüssel steht, gehört zu ihm, auch am
      Anfang der Datei. Ausnahme: Über dem Schlüssel, der die Liste der Einträge trägt
      (`rules:`, `loans:`, …), ist es Kopf.
    - Ein Block mit Leerzeile danach ist auch zwischen Einstellungen ein Abschnitt.
    - Ein Block über einer Zuordnung nach Konto (`account_roles`, `account_budgets`,
      `verlauf`) und ein Block am Ende der Datei kommen in die Notiz des Bereichs, mit
      dem Hinweis „zu `<schlüssel>`“ bzw. „am Ende der Datei“.
    - Die Euro-Wiederholungen fallen auch in der Lage Einstellung weg, nach derselben
      Regel mit vier Bedingungen.
11. **Musterhaushalt und Vorgaben stellt die Sitzung von Hand um**, nicht mit dem
    Umwandler: Die Platzhalter des Musterhaushalts sind kein YAML. Ihre Kommentare sind
    Text der App und werden keine Notizen. Was davon einem neuen Haushalt hilft, kommt
    knapp ins Handbuch, innerhalb seiner Wortgrenzen, der Rest entfällt. Der
    Musterhaushalt bekommt ein paar erfundene Notizen, damit die Tests Notizen
    überhaupt sehen: eine mit Datum, eine ohne, eine des Bereichs und eine an einer
    Einstellung.
12. **`module.py` und `overlays.anwenden`** folgen in N.3 der zusammengelegten Datei,
    im selben Teilschritt wie der Leser.
13. **Freitext, den keine Seite kennt:**
    - `loans[].note` und `ziele[].quelle` werden Teil der Notiz des Eintrags.
    - `segments_observed[].note` geht in die Notiz des Kredits, eingeleitet mit dem
      Teilstück.
    - `open` bleibt ein eigenes Feld. Es ist eine Liste offener Punkte, keine
      Begründung, und `/kredite` zeigt sie.
    - Die übrigen Notizen unter anderem Namen werden in N.2 zu `notiz`: `herleitung`
      der Renten, `note` an Bestand, Verpflichtung und Konto-Regel, `warum` der Abos.
    - N.1 lässt die Leser `notiz` zuerst lesen und den alten Namen als Ersatz, damit die
      Seiten nach N.2 dasselbe zeigen. Die Beschriftungen der Seiten bleiben bis
      Schritt 6.

**Reihenfolge für N.3**, in sechs Gruppen. Jede Gruppe ist ein Teilschritt mit einem
Commit je Bereich:

| Teilschritt | Bereiche |
|---|---|
| N.3a | `forecast`, `taxonomy` |
| N.3b | `renten`, `abos` mit `versicherungen` |
| N.3c | `properties`, `loans` |
| N.3d | `ziele`, `balances` |
| N.3e | `rules`, `accounts`, `lebensplan`, `backup` (in der Kopie fehlt das meiste davon; getestet mit erfundenen Ordnern) |
| N.3f | `settings` |

### N.1 Notizen lesen und schreiben (gleich, streng)

- `finctl/notizen.py`: die Form einer Notiz (Text, Datum oder keins), lesen
  am Eintrag und unter `notizen:` und die Datumsregel aus Entscheidung 4. Die
  Reihen nutzen danach dasselbe Modul (`reihen._notiz`).
- Jeder Leser verträgt `notiz`, `notiz_vom` und `notizen`, und keiner nimmt
  sie als Wert.
- Wo heute eine Notiz unter anderem Namen steht (`herleitung`, `note`,
  `warum`; N.0, Nummer 13), liest der Leser zuerst `notiz` und den alten
  Namen als Ersatz. Renten lesen `notiz` aus beiden Dateien (N.0, Nummer 6).
- Jede Seite, die einen Eintrag schreibt, behält seine Notiz. Speichern ohne
  Änderung ändert nichts, auch nicht das Datum.
- Keine Datenänderung, keine neue Anzeige.
- Tests je Eintragsart: Eine Notiz übersteht Lesen und Schreiben über die
  Seite, und eine Notiz ohne Datum bleibt ohne Datum, solange ihr Text
  bleibt.

**Fertig wenn:** `pruefen` meldet „Gleich“ auf der Entwicklungskopie selbst.

**Umgesetzt am 07.10.2026 (Sonnet).** `pruefen` meldet auf der Entwicklungskopie „Gleich“ (Text und Zahlen, Stichtag 2026-10-02); `config/` ist danach noch gleich `sicherung_vor_schritt5/config/`. Beide Läufe der Suite sind grün (2043 und 1986 bestanden, ohne Browsertests), die Browsertests auch (40 bestanden, 4 übersprungen, weil dort kein Speichern-Knopf steht).

**Die Form.** `finctl/notizen.py` (Kern, jedes Modul darf es importieren) kennt sie allein:

- Am Eintrag: `notiz` (Text) und `notiz_vom` (JJJJ-MM-TT, fehlt bei einer Notiz aus der Zeit vor den Notizen). `Notiz(text, vom)` ist der Wert dazu.
- Unter `notizen:` oben in der Datei: je Ort ein Block derselben Form, `notizen: {<ort>: {notiz, notiz_vom}}`. Ort ist der Pfad der Einstellung oder `bereich`. Eine andere Form (ein bloßer Text, eine Liste) ist ein Fehler, der die Datei nennt.
- `lesen(*schichten, alt=…)`: die oberste Schicht mit einer Notiz gewinnt, mit ihrem eigenen Datum. In einer Schicht gilt `notiz` vor den alten Namen. Ein leerer Text blendet die Schicht darunter aus; `notiz:` ohne Wert sagt nichts.
- `fortschreiben(bisher, text)` ist die Datumsregel: `None` oder derselbe Text (ohne Rand verglichen) lässt die Notiz mit ihrem Datum, auch einem fehlenden; ein anderer Text bekommt das heutige Datum; leer löscht samt Datum. `setzen` wendet sie an einem Eintrag an, `bereich_setzen` unter `notizen:`.
- `ohne(zuordnung)` lässt die Schlüssel einer Notiz weg, `mit_bereichen(neu, pfad)` hält den Block `notizen:` über ein Neuschreiben der Datei, `in_zeile` legt die geltende Notiz in eine Zeile für eine Seite.

`reihen.py` nutzt `Notiz`, `lesen` und `fortschreiben`. Verhalten bei den Reihen: gleich, bis auf eine Stelle (Abweichung 5).

**Je Eintragsart.** Alle Tests liegen in `tests/test_notizen_eintraege.py` (E) und `tests/test_notizen_seiten.py` (S); die Form selbst prüft `tests/test_notizen.py`. Jeder prüft: Notiz und Datum überstehen das Schreiben, der Block `notizen:` auch, Speichern ohne Änderung lässt die Datei Byte für Byte, eine Notiz ohne Datum bleibt ohne Datum, ein neuer Text steht unter `notiz` mit dem heutigen Datum und ohne den alten Namen.

| Eintragsart | liest (alter Name) | schreibt | Test |
|---|---|---|---|
| Reihe | `reihen.lesen` | `reihen.festlegen`, `/api/reihen/takt` | E `test_a_series_note…`, `test_reihen.py` |
| Rente | `renten.quellen` (`herleitung`), beide Dateien | `renten.setzen`, `/api/rente` | E vier `…pension…`, S `…pension page…` |
| Bestand | `bestaende.zusammenfuehren` (`note`) | `/api/bestand` | S `…position…` (drei) |
| Verpflichtung | `bestaende.verpflichtungen` (`note`) | `/api/verpflichtung` | S `…liability…` (zwei) |
| Konto-Regel | `kontenregeln.zusammenfuehren`, `basiswerte` (`note`) | `kontenregeln.setzen`, `/api/konto/{id}` | E drei `…account rule…` |
| Abo, Versicherung | `abos.laden` (`warum`) | `abos.speichern` | E `…contract…` (drei), `…insurance…` |
| Ziel | `ziele.merge_edits` | `/api/ziel` | E `…goals machine…`, S `…goal…` (drei) |
| Konto | `konten.laden` | `konten.anlegen` | E `…account keeps…` |
| Kredit | `lade_kredite` | `kredite.anlegen`, `entfernen`, `/api/kredit-anschluss`, `/api/kredit-vorlage` | E `…loan…` (zwei), S `…follow-up…` |
| Objekt | `objekte.vorhandene` | `objekte.anlegen`, `prognose_setzen`, `overlays.objekt_setzen` | E `…property…` |
| Regel | `engine.rohe_regeln` | `regelwerk.speichern` | E `…rule keeps…` |
| Kategorie | `taxonomy.load_spec` | `taxonomy.save_custom` | E `…category…` (zwei) |
| Klammer | `szenarien.load` | `/api/szenario` | S `…bracket…` |
| Projekt (geteilt) | `geteilt.laden` | `geteilt.schreiben` | E `…shared project…` |
| Einstellung, Bereich | `overlays.einstellungen` | `overlays.schreiben` und alle, die eine Datei neu aufbauen | E `…setting…`, `…files without entries…` |

**Leser, die ich geändert habe.** Keiner scheiterte an `notiz`, `notiz_vom` oder `notizen` an einem Eintrag oder am Dateikopf; das zeigt die Probe unten. Geändert sind die, die Felder aus zwei Dateien einzeln zusammenlegen (sonst trüge ein neuer Text das Datum des alten) und die, die die Notiz unter anderem Namen lesen: `renten.quellen`, `bestaende.zusammenfuehren` und `verpflichtungen`, `kontenregeln.zusammenfuehren`, `abos.laden`, `forecast.ziele.merge_edits`, `konten.laden`, `realestate.loan.lade_kredite`, `objekte.vorhandene`, `rules.engine._mit_aenderung`. Die Seiten lesen weiter `note` und `warum` aus ihren Zeilen: `in_zeile` legt die geltende Notiz auch unter dem alten Namen hinein, damit sich keine Beschriftung ändert (Schritt 6).

**Zuordnungen, die ihre Schlüssel als Daten nehmen.** Die Leser der Tabelle „Leser“ rufen `notizen.ohne` auf: `forecast.konten` (`overrides` an zwei Stellen, `enden` in `_enden`, `account_budgets`), `kontenregeln` (`overlay`, `zusammenfuehren`), `tax.taxonomy.load_spec` (`children` beider Achsen) und `apply_migrations` (`remap`), `overlays.einstellungen`, `zinssaetze.lesen`, `reihen.zusammen`. Zusätzlich dieselbe Zeile an Zuordnungen, die der Befund nicht nennt und die beim Lesen alle Schlüssel durchlaufen: `balances_custom` (`overrides`, `verpflichtungen`, `verlauf`), `forecast_custom` (`account_roles`), `abos_custom`, `versicherungen_custom`, `ziele_custom` (`ziele`), `loans_custom` (`kredite`), `accounts_custom`, `rules_custom` (`regeln`). `tests/test_notizen_zuordnungen.py` setzt eine Notiz in jede der acht aus der Tabelle und prüft, dass dasselbe herauskommt wie ohne. Damit ein Schlüssel nicht selbst `notiz` heißt, verweigern es die Stellen, an denen ein Haushalt ihn benennen kann: Konto, Kredit, Abo, Ziel, Verpflichtung, Kategorie-Blatt (`notizen.RESERVIERT`).

**Alte Namen.** `notiz` gilt zuerst, dann der alte Name, in dieser Reihenfolge je Datei: Renten (`herleitung`; `notiz` aus `renten.yaml` und `renten_custom.yaml`, die Seitendatei zuerst), Bestände und Verpflichtungen (`note`), Konto-Regeln (`note`), Abos und Versicherungen (`warum`). Beweis, dass die Seiten dasselbe zeigen: Eine Kopie der Entwicklungskopie im Scratchpad, in der alle 33 Felder `herleitung`, `note` und `warum` zu `notiz` umbenannt sind (nichts sonst, Datum keins), meldet bei `pruefen` „Gleich“, Text und Zahlen. Die Kopie mit einer Notiz an jedem der 245 Einträge und `notizen:` in jeder Datei mit Seite (Probe) unterscheidet sich nur dort, wo eine Seite eine Notiz zeigt: `/annahmen` und `/prognosebasis` (die Belege der Renten), `/bestaende`, `/konten`, `/monatsabschluss`, `/start`. Die Zahlenebene dieser Seiten ändert sich dort nur, soweit der Notiztext Ziffern trug.

**Schreiber.** Jede Seite, die einen Eintrag schreibt, steht in der Tabelle. Neu: Ein neuer Text steht unter `notiz`, mit Datum, und der alte Name verschwindet aus dem Eintrag. Sonst läse der Leser (`notiz` zuerst) nach N.2 einen alten Text statt der Eingabe. Gleich der Basisdatei ist keine Abweichung (`setzen(…, basis=…)`); leer löscht die eigene Notiz, und die der Basisdatei gilt wieder, nur die Ziele blenden sie aus (`ausblenden=True`, wie bisher). Jeder Schreiber, der eine Datei aus seinen eigenen Daten neu aufbaut, hält den Block `notizen:` (`mit_bereichen`): `abos`, `konten`, `overlays` (Einstellungen, Zinssätze, Objekte, Module, Sicherung), `strom`, `energie/speicher`, `geteilt`, `forecast/prognosebasis`, `ingest/zuordnung`, `rules/regelwerk`, `reihen`, `r/ziele`. Die übrigen lesen die ganze Datei, ändern ihren Teil und schreiben sie zurück.

**Nicht angefasst, wie vorgegeben:** `engine.repoint_rule`, `engine.grundschicht_setzen` und `nachfuehren.taxonomie` (N.2), `config/` der Entwicklungskopie, `sicherung_vor_schritt5/`.

**Abgenommen am 08.10.2026 (Opus).** Nachgeprüft:
- `pruefen` meldet „Gleich“, streng.
- `config/` der Entwicklungskopie gleicht `sicherung_vor_schritt5/config/`.
- Die Korrektur in `/api/kredit-anschluss` (`{**spec, "anschluss": …}`) ist richtig.

Zu den Abweichungen:
- **1 (Anschluss):** Die Korrektur gilt. `basis` hat den Fehler weiterhin. Bis zum
  Umstieg sollte deshalb auf `/kredite` im Alltag keine Anschlusskondition gespeichert
  werden. Ob im echten Datenordner schon etwas fehlt, prüft Opus nur mit dem OK des
  Haushalts. Die Prüfung steht in der Umstiegsliste im Gesamtplan.
- **2 bis 7:** Sie gelten wie beschrieben.
  - Die Reihen behalten eine Notiz ohne Datum jetzt auch beim Ändern des Takts. Das
    folgt aus Entscheidung 4 und ist gewollt.
  - Die Notiz an Projekten gilt ebenfalls.
  - Die Brücken aus Nummer 6 nimmt N.3 je Bereich zurück, N.4 prüft, dass keine
    übrig ist.

### N.2 Kommentare werden Notizen (gleich in den Zahlen)

- `finctl/umstellen.py` und `finctl umstellen` mit `--probe`, nach
  Entscheidung 6, zunächst nur für die Kommentare. Die Paare bleiben, wie sie
  sind.
- Die Zuordnung folgt Entscheidung 2. Die Umwandlung schreibt die Datei neu,
  ohne Kommentare und mit Notizen. Reihenfolge der Einträge und Schlüssel
  bleibt.
- `herleitung` der Renten und jedes andere Freitextfeld aus N.0 wird zur
  Notiz (N.0, Nummer 13). Die Zuordnung der Grenzfälle steht unter N.0,
  Nummern 8 bis 10.
- Im selben Commit schreiben `engine.repoint_rule`,
  `engine.grundschicht_setzen` und `nachfuehren.taxonomie` strukturiert statt
  als Text (N.0, Nummer 1).
- Die Umwandlung prüft sich selbst und schreibt nichts, wenn eine Prüfung
  scheitert:
  - Jede Kommentarzeile steht in genau einer Notiz oder im Bericht unter
    „weggefallen“.
  - Jede Datei liefert ohne ihre Notizen dieselben Werte wie vorher
    (geparst verglichen).
- Tests mit erfundenen Dateien für jede der fünf Lagen, für Blöcke über
  mehreren Zeilen und für eine Datei ohne Kommentar. Zweiter Lauf: keine
  Änderung.
- Der Musterhaushalt und `finctl/vorgaben/` werden von Hand umgestellt
  (Entscheidung 8, N.0, Nummer 11).

**Fertig wenn:** An der umgewandelten Kopie meldet `pruefen --nur-zahlen`
„Gleich“. Ein Textunterschied darf nur dort stehen, wo eine Seite schon eine
Notiz zeigt. Der Bericht legt alle Textunterschiede bei, und den Bericht der
Umwandlung als Datei in `notizen/` der Entwicklungskopie. Die
Entwicklungskopie selbst bleibt unverändert.

**Danach, als eigener Schritt (Opus):** die Entwicklungskopie umstellen und
die Referenz neu schreiben.

**Umgesetzt am 08.10.2026 (Sonnet).** Geprüft an einer Kopie der Entwicklungskopie im Scratchpad (`config/` und `data/referenz/` kopiert, `data/statements` verknüpft). Die Entwicklungskopie selbst ist unverändert: `config/` gleicht `sicherung_vor_schritt5/config/`, und `finctl umstellen --probe` auf ihr ließ die Prüfsumme des ganzen Datenordners gleich. Beide Läufe der Suite (2109 und 2052 bestanden) und die Browsertests (40 bestanden, 4 übersprungen) sind grün. Die Referenz ist nicht neu geschrieben.

**Wo was steht.** `finctl/umstellen.py` (Lauf, Prüfungen, Bericht, Sicherung), `finctl/umstellen_lagen.py` (Kommentare lesen, Lagen, Ziele), `finctl/umstellen_form.py` (wie jede Datei aufgebaut ist, und was die App über sie schrieb). Die Formen und die Köpfe stehen dort, nicht in den Modulen, die die Dateien heute lesen: Nach N.3 und N.4 gibt es einige davon nicht mehr. `tests/test_umstellen.py` hält die Köpfe gegen die Konstanten der Module, solange es sie gibt. Dazu `dateien.yaml_text` und `yaml_schreiben` (die ganze Datei strukturiert schreiben: kurze Sammlungen aus einfachen Werten in einer Zeile, Notizen als Block `|`, Listen eingerückt).

**`finctl umstellen`.**
- Sichert `config/` ganz nach `archiv/vor_umstellung_<Datum>/config/` (gleicher Tag zweimal: `_2`), schreibt die Dateien neu, legt den Bericht nach `notizen/umstellung_<Datum>.md`. Der Bericht nennt je Datei die Kommentarzeilen je Lage, was in Notizen ging, was wegfiel und welche alten Namen `notiz` wurden, dazu jeden Kommentar mit Zeile, Lage und Ziel.
- Zweiter Lauf: „Nichts umzustellen“, keine neue Sicherung, keine neue Datei, Prüfsumme gleich. Eine Datei ist umgestellt, wenn sie keinen Kommentar und keinen alten Namen mehr hat; der Kopf, den die App danach wieder schreibt, zählt nicht.
- `--probe <Ordner>` schreibt nur die umgewandelte Kopie (`<Ordner>/config/`) und den Bericht dorthin. Ein Ordner im Datenordner wird abgelehnt. Prüfsumme des Datenordners vorher und nachher: gleich, auch auf der Entwicklungskopie selbst. Die Probekopie ist Byte für Byte die `config/` des echten Laufs.
- Eine Datei, die sich nicht umwandeln lässt (kein YAML, keine Zuordnung an der Wurzel) oder bei der eine Prüfung scheitert, verhindert den ganzen Lauf: nichts wird geschrieben.

**Zuordnung auf der Kopie** (1704 Kommentarzeilen in 32 Dateien; die 66 der vier Dateien ohne Seite bleiben stehen, zusammen 1770 wie in Tabelle B):

| | K | A | E | F | S | – | Σ |
|---|---:|---:|---:|---:|---:|---:|---:|
| Tabelle B, ohne die vier Dateien | 450 | 146 | 779 | 76 | 233 | 20 | 1704 |
| Zuordnung jetzt | 322 | 208 | 760 | 54 | 213 | 20 | 1704 |
| davon in Notizen | | | | | | | 1577 |
| davon weggefallen | | | | | | | 127 |

Die Abweichungen von Tabelle B sind genau die Grenzfälle aus Nummer 10; alle anderen Zahlen je Datei stimmen:
- **Strichlinie über einem Eintrag ist Abschnitt, nicht Eintrag:** `balances.yaml` E 18→2, A 0→16 (drei Blöcke, jetzt „Stand vor“ drei Kennungen); `accounts.yaml` E 18→15, A 0→3.
- **Block ohne Leerzeile am Dateianfang über einer Einstellung gehört ihr:** `assumptions.yaml` K 20→16, S +4 (Zeilen 19–22, Ort `inflation_pa`).
- **Block mit Leerzeile zwischen Einstellungen ist Abschnitt:** `forecast.yaml` S 81→62, A 7→26; in `assumptions.yaml` bleibt A bei 20 (die Zeilen 42–47 waren auch nach N.0 Abschnitt).
- **Strichlinie direkt über dem Schlüssel der Eintragsliste am Dateianfang:** `goals.yaml` K 41→17, A 0→24. Nummer 10 sagt beides („Strichlinie beginnt immer einen Abschnitt“ und „über `rules:`, `loans:` ist es Kopf“); ich habe die Strichlinie gewinnen lassen. Der Block steht trotzdem in der Notiz des Bereichs, nur mit dem Hinweis „Stand vor `ziele`“ statt ohne. Ein Block mit Leerzeile ganz am Anfang ist immer Kopf, auch wenn er mit einer Linie beginnt (`goals.yaml` Zeilen 1–17).
- **Ohne Lage (–), 20 Zeilen:** `forecast.yaml:74–83` „Zu `account_budgets`“, `:107–112` „Zu `account_roles`“, `goals.yaml:53–56` „Am Ende der Datei“ (zusammen wie in Tabelle B).

**Weggefallen, 127 Zeilen:** 100 Zeilen Kopf der App in 12 Dateien (`abos_custom` 8, `balances_custom` 13, `forecast_custom` 6, `geteilt_custom` 6, `loans_custom` 11, `overrides` 9, `properties_custom` 11, `settings_custom` 9, `strom` 5, `szenarien` 9, `taxonomy_custom` 5, `versicherungen_custom` 8; die 9 von `server.yaml` kommen zu den 109 aus N.0 dazu, die Datei bleibt aber unangetastet) und 27 Euro-Wiederholungen (`loans` 11, `properties` 4, `forecast` 3, `balances` 2, `renten` 2, `assumptions*` 5 in der Lage Einstellung). `renten_custom` und `ziele_custom` tragen den abweichenden Kopf und gehen in die Notiz des Bereichs. Die 17 Zeilen „Wert und mehr“ bleiben.

**Selbstprüfung** (alle vor dem Schreiben, `umstellen._pruefen`): Jede Kommentarzeile steht in genau einem Stück (Zahl und Zeilennummern gegen den Scanner); jedes Stück steht im Text der Notiz, in die es gehört; die neue Datei hat keinen Kommentar; ohne ihre Notizen (auch ohne die alten Namen) liefert die Datei dieselben Werte; eine zweite Umwandlung der neuen Datei findet nichts mehr. Zwei Tests lassen `anwenden` eine Notiz verlieren und einen Wert ändern: Der Lauf meldet es und lässt `config/`, `archiv/` und `notizen/` Byte für Byte, wie sie waren.

**Alte Namen.** `herleitung` (Renten und `neu:` in `renten_custom`), `note` (Bestand, Verpflichtung, Konto-Regel), `warum` (Abo, Versicherung), `loans[].note` und `ziele[].quelle` werden `notiz` und bleiben an der Stelle des alten Feldes. `segments_observed[].note` geht als „Teilstück <Zeitraum>: …“ in die Notiz des Kredits. `open` bleibt. Gezählt auf der Kopie: `herleitung` 3, `note` 10 + 6 + 5 + 1, `warum` 2 + 1, `quelle` 1.

**Textschreiber.** `engine.repoint_rule`, `engine.grundschicht_setzen` und `nachfuehren.taxonomie` lesen, ändern, schreiben (`dateien.yaml_schreiben`). `tests/test_rules.py::test_repoint_rule_changes_the_right_rule_in_a_converted_file` wandelt eine `rules.yaml` um und belegt: Die Regel ohne das Feld ändert nicht die nächste, die Notizen bleiben. **Die App hält an**, bevor sie nachführt: `nachfuehren.taxonomie` wirft `umstellen.AlteFormError` mit dem Befehl, wenn es schreiben müsste und die Datei noch Kommentare trägt; `finctl init` und die Befehle mit Hauptbuch melden es rot und enden mit 1, der Start der App (`beim_start`) kommt nicht hoch. Gezeigt an einer Kopie in alter Form, der das Merkmal `einmalig` fehlt. Hat die Datei das Merkmal, gibt es nichts zu schreiben und nichts anzuhalten.

**Musterhaushalt und Vorgaben (von Hand).** Alle Kommentare entfernt (Muster 102 Zeilen ohne `taxonomy_migrations.yaml`, Vorgaben 368), geprüft: Die gelesenen Werte (Muster nach `datieren`) sind gleich. Im Muster `herleitung`, `warum` und `note` zu `notiz`. Vier erfundene Notizen kamen dazu: `loans.yaml` (Kredit `001`, mit Datum), `properties.yaml` (Objekt `nord`, ohne), `rules.yaml` (Bereich, mit Datum), `assumptions.yaml` (Einstellung `kapital.rendite_depot_pa`, ohne). Ins Handbuch kam der Abschnitt „Die Form der Startdateien“ am Ende von 2 (148 Wörter, nicht von einer Seite verlinkt) und ein Absatz zur Notiz und zu `finctl umstellen` (76 Wörter); in einem verlinkten Abschnitt (`/regeln`) wurde nur ein Wort getauscht (Begründungen → Notizen), er bleibt unter 200.

**`pruefen` an der umgewandelten Kopie.** `--nur-zahlen` meldet **nicht** „Gleich“, sondern 5 Unterschiede: `annahmen`, `bestaende`, `monatsabschluss`, `prognosebasis`, `start`, nur auf der Zahlenebene dieser Seiten. Der Grund ist der, den N.1 voraussagte: Die Seiten zeigen jetzt Notizen aus Kommentaren, und der Text trägt Ziffern. `hauptbuch/`, `ableitung/` und die anderen 37 Seiten sind gleich. Mit Text sind es 10 Unterschiede (dieselben fünf Seiten). Eine Kontrollkopie, in der nur die Notizen aus Kommentaren fehlen (Dateien neu geschrieben, alte Namen zu `notiz`), meldet „Gleich“: Das Neuschreiben und Umbenennen ändert nichts. Alle 88 neuen Zeilen stehen als Text in einer Notiz der umgestellten Dateien. Textunterschiede und Bericht: `notizen/N.2_pruefen_unterschiede.md` und `notizen/N.2_umstellung_probe.md` der Entwicklungskopie.

**Abgenommen am 08.10.2026 (Opus), mit einem Nachtrag N.2b.**

Nachgeprüft an einer eigenen Kopie der Entwicklungskopie:
- `finctl umstellen` sichert, schreibt und berichtet wie beschrieben. Ein
  zweiter Lauf meldet „Nichts umzustellen“, und die Prüfsumme bleibt gleich.
- Kommentare tragen danach nur die vier Dateien ohne Seite.
- `pruefen --nur-zahlen` meldet dieselben fünf Seiten. Jede Zeile gehört zu
  den Notizen der Renten.
- `config/` der Entwicklungskopie gleicht `sicherung_vor_schritt5/config/`.
- Grün waren `test_umstellen`, `test_rules`, `test_nachfuehren`, `test_leck`,
  `test_namen` und `test_lint`, auf beiden Datensätzen.

Zu den Abweichungen:

1. **Die Fertig-wenn-Zeile war falsch gestellt.** Die Zahlenebene zählt jede
   Ziffer im Text. Deshalb konnte eine Notiz mit Ziffern auf einer Seite, die
   Notizen zeigt, nie „Gleich“ ergeben. Angenommen: Hauptbuch und Ableitung
   sind gleich, und die Kontrollkopie ohne Kommentar-Notizen meldet „Gleich“.
   Die Textebene schreibe ich mit der Umstellung der Entwicklungskopie neu.
2. **Die Notiz der Seitendatei verdeckt die Herleitung der Basis.** Das ist
   bis N.3b angenommen. Die neue Referenz enthält diesen Stand, und N.3b
   bringt die Herleitung als gewollten Textunterschied zurück. N.3b legt die
   Notizen beider Dateien in Dateireihenfolge zusammen: zuerst die Basis, dann
   die Seitendatei.
3. **Block unter dem letzten Eintrag → Nachtrag N.2b.** Die Lesart von N.0
   bleibt, denn ein solcher Block ist meist ein Abschnitt. In der Kopie gilt
   das für fünf von sieben Fällen. Zwei Fälle stehen aber falsch:
   - Der Warnblock unter dem letzten Budget in `forecast.yaml` steht jetzt
     „vor `account_roles`“, obwohl er von dem Konto darüber handelt.
   - Der Satz unter der gesetzlichen Rente in `renten.yaml` steht beim
     Bereich, obwohl er zu ihr gehört.

   Zwei Regeln lösen das:
   - Ein Block ohne Leerzeile davor, der so tief eingerückt ist wie die Felder
     des Eintrags darüber, gehört in dessen Notiz.
   - Jeder andere Block ohne Leerzeile davor bleibt Abschnitt, mit dem Hinweis
     „Stand nach `<Schlüssel darüber>`“ statt „vor …“.
4. **Strichlinie über der Eintragsliste ist Abschnitt.** Angenommen.
5. **Anhalten → N.3a, als Erstes.** Die App hält an, sobald `finctl
   umstellen` in `config/` etwas fände. Das gilt beim Start, bei `init` und
   bei jedem Befehl mit Hauptbuch, und es ersetzt den engen Stopp in
   `nachfuehren.taxonomie`. Erst nach der Umstellung der Entwicklungskopie
   möglich, sonst hielte die Suite an.
6. **Kein Wächter in `repoint_rule` und `grundschicht_setzen`.** Der Stopp aus
   Punkt 5 deckt sie ab.
7. bis 9., 11. bis 13. Angenommen.
10. **Dateien sehen nach dem Umwandeln anders aus.** Angenommen. Eine
    Euro-Wiederholung mit Einheit („… je Monat“) bleibt Notiz. Das ist
    vorsichtig, nicht falsch.

Reihenfolge danach:
1. N.2b (Sonnet).
2. Opus stellt die Entwicklungskopie mit `finctl umstellen` um und schreibt
   die Referenz neu.
3. N.3a.

### N.2b Block unter einem Eintrag (gleich in den Zahlen)

- Die beiden Regeln aus der Abnahme von N.2, Punkt 3, gelten in
  `umstellen_lagen`.
- Tests mit erfundenen Dateien:
  - ein Block auf Feldtiefe unter einem Eintrag mitten in der Liste und am
    Ende;
  - ein Block auf Eintragstiefe am Ende einer Zuordnung;
  - ein Block mit Leerzeile davor, der wie bisher bleibt.
- Der Bericht der Probe nennt jede Zeile, die gegenüber N.2 woanders landet,
  mit altem und neuem Ziel.

**Fertig wenn:**
- An einer frischen Kopie der Entwicklungskopie landen gegenüber N.2 nur die
  sieben Blöcke ohne Leerzeile davor anders oder mit anderem Hinweis.
- Die Selbstprüfung hält.
- `pruefen --nur-zahlen` zeigt dieselben fünf Seiten. Neu dazu kommt höchstens
  die Notiz der gesetzlichen Rente auf den Seiten, die Notizen der Renten
  zeigen.
- Die Entwicklungskopie bleibt unverändert.

**Umgesetzt am 08.10.2026 (Sonnet).** Geprüft an einer frischen Kopie der Entwicklungskopie im Scratchpad (wie unter N.2). Die Entwicklungskopie ist unverändert: `config/` gleicht `sicherung_vor_schritt5/config/`, die Prüfsumme des Datenordners ist vor und nach der Probe gleich, neu ist nur der Bericht `notizen/N.2b_umstellung_probe.md`. Beide Läufe der Suite sind grün (2121 und 2064 bestanden). Browsertests nicht gelaufen: keine Vorlage, Route und kein Skript geändert. Die Referenz ist nicht neu geschrieben.

**Die Regeln** (`umstellen_lagen`, `Ordner._unter`). Sie gelten nur für einen Block, der unmittelbar unter einer Zeile mit Inhalt steht (kein Leerraum davor, keine Strichlinie) **und** dem nichts folgt, woran er hängen könnte (Leerzeile danach oder Ende der Datei). Steht etwas direkt darunter, gehört der Block wie bisher dazu (N.0, Nummer 10).
- *Feldtiefe.* `Eintrag.spalte` ist die Spalte der Felder in Blockform: bei `- id: a` mit Zeilen darunter die des ersten Feldes (`id`), bei `a:` mit eingerückten Feldern ebenso. Ein Eintrag, der nur ein Wert ist (`a: 100`, `a:`, `- {id: a, …}`, `- a`), hat keine tiefere Spalte: Für ihn zählt die seines Schlüssels, bei einer Liste die des `-`. Verglichen wird auf Gleichheit mit der Spalte des Kommentars (`#`). Tiefer eingerückt (etwa auf der Spalte der Blätter einer Kategorie) bleibt Abschnitt.
- *Regel 1.* Gleiche Spalte → Notiz des Eintrags darüber (Lage E). Bei einem Budget die Notiz der Konto-Regel mit „Budget:“ davor; bei einem Eintrag, der nur ein Wert und kein Budget ist, geht sie wie bisher über `_umleiten` in die Notiz des Bereichs („Zu `<Eintrag>`“).
- *Regel 2.* Jede andere Spalte, oder steht darüber kein Eintrag (Einstellungsdateien) → Abschnitt (Lage A) mit dem Hinweis „Stand nach `<Eintrag>`“; ohne Eintrag der Schlüsselpfad der Zeile darüber.
- *Ende der Datei.* Ohne Leerzeile davor dieselben zwei Regeln, ein Abschnitt dann mit „Stand nach `<…>`“ statt „Am Ende der Datei“. Mit Leerzeile davor bleibt es bei „Am Ende der Datei“ (Lage –).
- *Strichlinie.* Eine Strichlinie ist von beiden Regeln ausgenommen: Sie leitet ab, was folgt, und bleibt „Stand vor `<…>`“.

**Wirkung auf der Kopie.** Sieben Blöcke ohne Leerzeile davor waren in N.2 Abschnitt; sechs landen anders, einer bleibt:
- `forecast.yaml` Zeile 102–105: Abschnitt „vor `account_roles`“ → Notiz der Konto-Regel des Kontos darüber, mit „Budget:“.
- `renten.yaml` Zeile 26: Abschnitt „vor“ der nächsten Police → Notiz der gesetzlichen Rente, hinter ihrer Herleitung.
- `assumptions.yaml` Zeile 115–116, `lebensplan.yaml` Zeile 30–31 und 100–102, `taxonomy.yaml` Zeile 66–75: bleiben Abschnitt, aus „Stand vor `x`“ wird „Stand nach `y`“ (`y` die Einstellung bzw. die Oberkategorie `wohnen`).
- `balances.yaml` Zeile 64–71 bleibt „vor“ dem ersten Konto. Das ist **eine Abweichung von der wörtlichen Fassung der Abnahme**, die jeden anderen Block ohne Leerzeile davor „nach“ nennt: Es ist eine Strichlinie direkt unter `balances:`, „Stand nach `balances`“ nennte den Ort falsch. Soll sie doch „nach“ heißen, ist es eine Zeile in `Ordner._block` (`not strich` in `unter`).
- Lagen insgesamt: A 208 → 203, E 760 → 765; weggefallen (127) und in Notizen (1577) gleich. Der Vergleich liegt als Abschnitt „Gegenüber N.2“ im Bericht, mit Datei, Zeile, altem und neuem Ziel.

**Selbstprüfung und zweiter Lauf.** Der echte Lauf an der Kopie (`finctl umstellen`) meldet keine gescheiterte Prüfung. Die Probekopie ist Byte für Byte die `config/` des echten Laufs. Ein zweiter Lauf: „Nichts umzustellen“, Prüfsumme des Datenordners gleich, keine neue Sicherung.

**`pruefen --nur-zahlen` an der umgewandelten Kopie.** Dieselben fünf Seiten wie bei N.2 (`annahmen`, `bestaende`, `monatsabschluss`, `prognosebasis`, `start`), 5 Unterschiede. Gegenüber N.2 (selbe Kopie mit dem Stand von `4c3a2b5` umgewandelt und geprüft) kommt auf jeder der fünf Seiten genau eine Zeile dazu, die Ziffern des Satzes unter der gesetzlichen Rente. Nichts fällt weg.

**Tests** (`tests/test_umstellen.py`, erfundene Dateien): Feldtiefe mitten in der Liste und am Ende der Datei; andere Spalten (flacher, tiefer); Eintragstiefe am Ende einer Zuordnung; Eintrag, der nur ein Wert ist (Budget, Liste mit `{…}`); Block unter einer Einstellung; Block mit Leerzeile davor, Strichlinie und Block mit Inhalt direkt darunter bleiben. Neun davon schlagen auf dem Code von N.2 fehl.

**Abgenommen am 08.10.2026 (Opus).** Nachgeprüft:
- Eine frische Kopie, umgewandelt mit N.2b, unterscheidet sich von der Kopie
  aus N.2 genau an den sechs genannten Stellen.
- Die Probe auf der Entwicklungskopie gleicht dieser Kopie Byte für Byte.
- Die Strichlinie in `balances.yaml` bleibt „vor“. Das ist richtig, weil eine
  Strichlinie ankündigt, was folgt. Die wörtliche Fassung meiner Abnahme war
  zu weit.
- Dass der Warnblock nach Regel 1 in die Konto-Regel geht statt nach Regel 2
  in den Bereich, ist besser als meine Fassung. Es folgt N.0, Nummer 8.
- Zwei echte Kennungen im Eintrag habe ich ersetzt.

**Entwicklungskopie umgestellt am 08.10.2026 (Opus).**
- `finctl umstellen` lief auf der Entwicklungskopie. Die Sicherung liegt in
  `archiv/vor_umstellung_2026-10-08/`, der Bericht in
  `notizen/umstellung_2026-10-08.md`.
- `config/` gleicht danach der Probe. Ein zweiter Lauf meldet „Nichts
  umzustellen“.
- `pruefen` meldete vor dem Neuschreiben nur die fünf Seiten, Zahlen und Text,
  wie oben. Die Ausgabe liegt in `notizen/N.2_referenz_vor_neuschreiben.txt`.
- Dann habe ich die Referenz neu geschrieben (Stichtag 2026-10-02).
  `sicherung_vor_schritt5/` bleibt als Stand vor Schritt 5.

### N.3 Ein Ort je Sache (gleich in den Zahlen, je Gruppe)

Sechs Teilschritte, N.3a bis N.3f, in der Reihenfolge der Tabelle unter N.0.
`settings_custom.yaml` kommt zuletzt, weil seine Werte in zwei fremde Dateien
gehen.

**N.3b beginnt mit den Notizfeldern** (Befund bei der Abnahme von N.3a), auf
allen Seiten, die eine Notiz eines Eintrags bearbeiten:
- `/konten`, `/renten`, `/ziele` (Bearbeiten und Neu), `/reihen` und `/abos`
  (auch für Versicherungen).
- Jede Notiz bearbeitet die Seite in einer `<textarea>`, die
  Zeilenumbrüche behält.
- Kein `maxlength` und keine Kürzung auf dem Server unter dem, was eine aus
  Kommentaren entstandene Notiz lang ist. Das gilt auch für Verpflichtung,
  Reihe und Bestand (N.3a, Punkt 1).
- Ein Browsertest je Seite: Eine mehrzeilige Notiz öffnen und ohne Änderung
  speichern lässt die Datei Byte für Byte gleich. Eine Zeile ändern behält
  die übrigen Zeilenumbrüche und setzt das Datum.
- Wie die Notiz aussieht und wo sie steht, bleibt Schritt 6. Hier geht es nur
  darum, dass Speichern sie nicht beschädigt.

Je Bereich:
- `finctl umstellen` legt das Paar zusammen. Die `_custom`-Datei geht in die
  Sicherung und verschwindet aus `config/`.
- Der Leser liest nur noch die eine Datei, und der Schreiber schreibt den
  ganzen Eintrag dorthin.
- Der Kopf, den die App über die `_custom`-Datei schrieb, fällt weg.
- Ein Wert der Basis, den die `_custom`-Datei überschrieben hatte, steht
  danach in der Notiz des Eintrags (N.0, Nummer 7).
- Anzeigen, die Basis und Seite vergleichen, und das Speichern nur der
  Abweichung fallen weg (N.0, Nummer 7).
- Ein Paar, das die App nicht mehr liest, hält sie an und nennt den Befehl
  (Entscheidung 6). N.3a beginnt damit, für jede Datei, die `finctl
  umstellen` ändern würde (Abnahme N.2, Punkt 5).
- Der Musterhaushalt wird mit umgestellt.
- Tests:
  - Ein Datenordner mit nur der Basisdatei, nur der `_custom`-Datei oder
    beiden wird richtig zusammengelegt.
  - Speichern ohne Änderung ändert nichts.
  - Ein Feld, das nur in der `_custom`-Datei stand, gewinnt wie vorher.

**Fertig wenn:** An der umgewandelten Kopie meldet `pruefen --nur-zahlen`
nur diese Arten von Zeilen:
- Zeilen, die wegfallen, weil sie einen Wert der Basis neben dem gültigen
  zeigten.
- Zeilen, die als Text in einer Notiz stehen, auf einer Seite, die diese
  Notiz schon zeigt. Das sind etwa ein Basiswert nach Nummer 7 oder zwei
  zusammengelegte Notizen. (Die Zahlenebene zählt auch Ziffern im Text; siehe
  die Abnahme von N.2, Punkt 1.)
- Die Zahl im Fuß „Konfiguration — n Dateien“ einer Seite, die eine
  Seitendatei weniger nennt (Abnahme N.3a).
- Zeilen der Tabelle `settings` in `hauptbuch/settings.json`, deren Wert danach
  in `assumptions.yaml` oder `forecast.yaml` steht (nur N.3f; Abnahme N.3f).

`hauptbuch/` und `ableitung/` sind gleich, und kein Betrag ändert sich.
Legt ein Paar Notizen aus beiden Dateien zusammen, steht die der Basis
zuerst. Danach stellt die Sitzung die
Entwicklungskopie selbst mit `finctl umstellen` um. Das ist der einzige
Teilschritt, in dem eine Sitzung `config/` der Entwicklungskopie ändert, und
nur über den Befehl. Die Textunterschiede liegen als Datei in `notizen/`.
Die Referenz schreibt Opus danach neu.

**Umgesetzt am 08.10.2026, N.3a (Sonnet): Anhalten, `forecast`, `taxonomy`.** Geprueft an einer frischen Kopie der Entwicklungskopie im Scratchpad (mit `data/referenz/`), dann die Entwicklungskopie selbst mit `finctl umstellen` umgestellt. Beide Laeufe der Suite (2166 auf der Entwicklungskopie, 2110 auf dem Musterhaushalt) und die Browsertests (40, 4 uebersprungen) sind gruen, bis auf `test_referenz`: Die Referenz ist nicht neu geschrieben. Die Sicherung liegt in `archiv/vor_umstellung_2026-10-08_2/`, der Bericht in `notizen/umstellung_2026-10-08_2.md`; ein zweiter Lauf meldet „Nichts umzustellen“.

**Anhalten.**
- *Eine Erkennung.* `Plan.zu_tun` (`umstellen.py`) sagt, ob `finctl umstellen` etwas faende: ein Kommentar, ein alter Feldname oder die Seitendatei eines Paars. Nach ihr meldet der Befehl „Nichts umzustellen“, und nach ihr haelt die App an (`umstellen.halt_wenn_offen`). Ein Fehler der Selbstpruefung zaehlt ebenfalls (`Plan.offen`). Dateien ohne Seite (`OHNE_SEITE`) sind aussen vor.
- *Der Kopf der App ist kein Anlass.* Vorher zaehlte eine Datei, die nur ihren Kopf loswuerde, als zu tun; die App haette nach jedem eigenen Speichern angehalten. Jetzt fuehrt allein der Kopf nicht zum Halt und nicht zu einem Lauf; hat der Lauf aus anderem Grund etwas zu tun, wird er mit entfernt (`Plan.zu_schreiben`).
- *Wo.* Beim Start der App (`nachfuehren.beim_start`, im `lifespan` der App), im Starter (`finctl app`, Doppelklick) und in `finctl serve`, bei `finctl init` und in `_require_db`, also bei jedem Befehl mit Hauptbuch. Die Meldung nennt die Dateien und den Befehl, `finctl umstellen`, dazu `--probe <ordner>` zum Ansehen. `backup`, `restore`, `ort`, `passwort` und `umstellen` halten nicht an.
- *Der enge Stopp ist ersetzt.* `nachfuehren.taxonomie` ruft nichts mehr; `alte_form` und `pruefen_neu_schreiben` gibt es nicht mehr. Die Stopps von `repoint_rule` und `grundschicht_setzen` decken derselbe Halt ab (Abnahme N.2, Punkte 5 und 6).
- *Schnellweg.* Eine Datei ohne ein einziges `#` und ohne einen der alten Namen wird nicht gelesen: Sonst kostete die Frage bei jedem Start drei Sekunden (`overrides.yaml` hat zwoelftausend Zeilen). Eine Datei, die sich nicht lesen laesst, faellt damit nur dort auf, wo sie gelesen wird.
- *Tests* (`tests/test_umstellen.py`): Start, `init`, `status` und Starter halten an bei einem Kommentar, einem alten Namen, `forecast_custom.yaml` und `taxonomy_custom.yaml`, und lassen die Dateien, wie sie waren; ein umgestellter Ordner haelt nicht an; `server.yaml`, `taxonomy_migrations.yaml`, `verbotene_namen.yaml` und der Kopf der App halten nicht an; Halt und „Nichts umzustellen“ sind dieselbe Frage.

**Zusammenlegen** (`finctl/umstellen_paare.py`, nach dem Umwandeln der Kommentare, vor dem Schreiben).
- *`forecast`.* Konto fuer Konto, Feld fuer Feld ersetzt die Seite, was sie nennt (`role`, `floor_cents`, `ceiling_cents`, `sweep_to`, `auffuellen`, `floor_from_loan`); ein Konto nur in der Seite wird angelegt, ein Feld nur in der Seite gilt. Budgets: die der Seite ersetzen, ein leeres entfernt das Budget; sie bleiben in `account_budgets` der Datei, als Zahl je Konto. Ein Budget, das die Seite aenderte, nennt seinen alten Wert in der Notiz der Konto-Regel („Budget: …“), oder, wo das Konto keine Regel hat, in der Notiz des Bereichs.
- *`taxonomy`.* Beide Achsen. Das Blatt der Seite ersetzt das der Basis, der Name des Oberbegriffs ebenso; ein Oberbegriff nur in der Seite bringt Name, Art und Blaetter mit. Merkmale der Seite, die der alte Leser nie las, kommen nicht in die Datei und stehen im Bericht.
- *Notizen.* Treffen zwei zusammen, steht die der Basis zuerst, dann die der Seite, getrennt durch eine Leerzeile; derselbe Text steht einmal. Das Datum ist das spaetere der beiden, fehlt es beiden, fehlt es. Ein Wert der Basis, den die Seite ueberschrieb, steht danach am Ende der Notiz: „Bis zur Umstellung stand in der Datei: …“.
- *Gilt genau, was galt.* Jedes Paar hat seinen alten Leser in `umstellen_paare.py` (Basis, Seite) und liest das Ergebnis mit dem neuen Leser; beide muessen dieselben Werte liefern, ohne Notizen. Dazu: Der Text beider Notizen steht in der zusammengelegten, und die geschriebene Datei sagt, was sie soll. Scheitert eine Pruefung, geschieht nichts (Test mit einem Zusammenleger, der ein Feld verliert, und einem, der eine Notiz verliert).
- *Fehlt die Basisdatei,* gilt die Startvorlage (`finctl/vorgaben/taxonomy.yaml`) als Basis, denn so las es die App.
- *Die Seitendatei* geht in die Sicherung und verschwindet aus `config/`; auch `--probe` laesst sie in seiner Kopie weg.
- *Auf der Entwicklungskopie:* `forecast_custom.yaml` hatte fuenf Konten mit einer Notiz und ein Konto mit einer anderen Rolle als die Basis; ein Basiswert war ueberschrieben, fuenf Notizen trafen zusammen, kein Budget. `taxonomy_custom.yaml` brachte einen Oberbegriff, der in der Basis schon stand, mit sechs Blaettern; alle sechs ersetzten ein Blatt der Basis (keines war neu), sechs Basiswerte stehen in der Notiz des Oberbegriffs. Zusammen 7 Basiswerte, in Notizen.

**Leser und Schreiber.**
- `kontenregeln` liest nur `forecast.yaml` (`aus_spec`, `wirksam`), `tax.taxonomy` nur `taxonomy.yaml` (`aus_spec`, `load_spec`); `overlay`, `zusammenfuehren`, `basiswerte`, `EIGEN` und `CUSTOM_PATH` gibt es nicht mehr.
- `/api/konto` (`kontenregeln.setzen`) schreibt den ganzen Eintrag des Kontos in `forecast.yaml`, mit der Notiz und dem Block `notizen:`, ueber `dateien.yaml_schreiben`. `tax.taxonomy.save` (vorher `save_custom`) tut dasselbe in `taxonomy.yaml`. Speichern ohne Aenderung aendert kein Byte: Der Standard eines Schalters (`auffuellen` an, `floor_from_loan` aus) steht nicht in der Datei, solange er nicht abweicht.
- Auf `/konten` sind „eigen“ und der Tooltip „Abweichend von config/forecast.yaml: …“ weg (`regel_eigen`, `regel_basis`); es gibt keine Basis mehr, mit der sich vergleichen liesse. Der Fuss der Seiten nennt die Seitendateien nicht mehr.
- `floor_cents:<konto>` aus `settings_custom.yaml` und der Tabelle `settings` bleibt bis N.3f; der Vorrang aus N.0 gilt (Test `…floor_set_on_the_page_still_goes_before…`: `floor_from_loan`, dann `settings`, dann `account_roles.<konto>.floor_cents`, dann die Dispo-Schwelle).
- Die Konvention `nur-abweichungen-speichern` in `docs/design_conventions.yaml` gilt nur noch fuer Dateien, die noch ein Paar sind.

**Musterhaushalt und `module.py`.** Der Musterhaushalt hat `forecast_custom.yaml` in `forecast.yaml` und `taxonomy_custom.yaml` in eine eigene `taxonomy.yaml` gelegt (die Vorlage mit den zwei Aenderungen der Seitendatei, gelesen wie vorher; der Test `…reads_like_both_files_did` hat es fuer beide an den Dateien selbst belegt). Die Notiz des einen Kontos besteht jetzt aus zwei Absaetzen, damit der Muster einen Zusammentreffer hat. Weil die App bei jedem alten Namen anhaelt, mussten im Muster auch `warum` (Abos), `note` (Bestaende, Konto-Regeln) und `herleitung` (Renten) zu `notiz` werden, obwohl N.2 das schon behauptete. In `module.py` aendert sich keine Zeile der Dateinamen: Kein Modul nennt `forecast*.yaml` oder `taxonomy*.yaml` unter `eintraege`. Neu steht dort nur `umstellen_paare.py` in der Liste der App.

**`pruefen --nur-zahlen` an der umgewandelten Kopie.** 2 Unterschiede, beide auf `seiten/`: `konten` und `kategorien`. `hauptbuch/` und `ableitung/` sind gleich.
- *Fallen weg* (Zahlenebene, 2 Zeilen): auf beiden Seiten die Zahl im Kopf des Fusses „Konfiguration — n Dateien“, weil er eine Datei weniger nennt. Textebene dazu: „eigen“ (6 Zeilen auf `/konten`, eine als Pille im Bearbeitungsbereich, fuenf hinter dem Zweck eines Kontos), die Fussbeschreibungen der Seitendateien.
- *Kommen dazu* (Zahlenebene, 31 Zeilen): 30 auf `/konten`, eine auf `/kategorien`. Jede der 30 steht als Text in einer Notiz einer Konto-Regel, die `/konten` zeigt: dort steht jetzt die Notiz der Basis mit der der Seite dahinter und bei einem Konto der alte Wert der Rolle. Die eine auf `/kategorien` ist die Zahl im Fuss (4 statt 5 Dateien).
- *Eine dritte Art, die die Fertig-wenn-Zeile nicht nennt:* die Zeile im Fuss der Seiten, die eine entfernte Datei nannte. Sie ist die einzige Zahl, die auf `/kategorien` anders ist; kein Betrag aendert sich.
- Die 79 neuen Textzeilen und die 14 weggefallenen stehen in `notizen/N.3a_pruefen_unterschiede.md` der Entwicklungskopie, der Bericht der Umstellung in `notizen/umstellung_2026-10-08_2.md`.

**Abgenommen am 09.10.2026 (Opus), Referenz neu geschrieben.**

Nachgeprüft an der Entwicklungskopie:
- Die Seitendateien sind weg. Ein zweiter Lauf meldet „Nichts umzustellen“.
- `pruefen --nur-zahlen` meldet dieselben zwei Seiten. Die Ausgabe liegt in
  `notizen/N.3a_referenz_vor_neuschreiben.txt`.
- Danach habe ich die Referenz neu geschrieben, Stichtag 2026-10-02.
  `pruefen` meldet „Gleich“.

Zu den Abweichungen:
- **Fuß der Seiten:** Seine Zahl nennt die Dateien der Seite. Das ist eine
  dritte erlaubte Art von Zeile und steht jetzt in der Fertig-wenn-Zeile
  von N.3.
- **Punkte 2 bis 8:** angenommen.
  - Punkt 5: Löschen entfernt jetzt wirklich, und es gilt wie vorher erst nach
    der Prüfung auf Regeln und der Umleitung der Buchungen.
  - Punkt 3: Das hätte N.2 melden müssen. Gut, dass der Halt es zeigt.
- **Punkt 1 (Kürzung auf 200 Zeichen):** angenommen. Er gehört aber zu einem
  größeren Befund, siehe den nächsten Absatz.

**Befund bei der Abnahme: Ein einzeiliges Feld zerstört eine mehrzeilige
Notiz.**
- **Ursache:** Die Notiz bearbeiten die Seiten in einem `<input>`. Der Browser
  entfernt beim Setzen des Werts jeden Zeilenumbruch. Beim Speichern kommt
  deshalb ein anderer Text an.
- **Folge:** `notizen.fortschreiben` hält ihn für geändert. Die Notiz steht
  danach in einer Zeile und trägt das heutige Datum, obwohl niemand sie
  geändert hat.
- **Seit wann:** Seit N.2 sind Notizen mehrzeilig, weil sie aus
  Kommentarblöcken entstehen.
- **Betroffen:** `/konten` (Zweck), `/renten`, `/ziele`, `/reihen` und `/abos`
  (Warum, dort zusätzlich `maxlength="200"`).
- **Nicht betroffen:** Notizen an einer Buchung (`/regeln`, Aufteilen). Sie
  sind keine Notiz eines Eintrags.

Der Server-Test „Speichern ohne Änderung“ sieht das nicht, weil er den Text
unverändert schickt. → **N.3b, als Erstes.**

**Umgesetzt am 09.10.2026, N.3b (Sonnet): Notizfelder, `renten`, `abos` mit `versicherungen`.** Geprueft an einer frischen Kopie der Entwicklungskopie im Scratchpad (mit `data/referenz/`), dann die Entwicklungskopie selbst mit `finctl umstellen` umgestellt: ihre `config/` gleicht der Kopie Byte fuer Byte, ein zweiter Lauf meldet „Nichts umzustellen“, die Pruefsumme von `config/`, `archiv/` und `notizen/` bleibt gleich. Sicherung: `archiv/vor_umstellung_2026-10-09/`, Bericht: `notizen/umstellung_2026-10-09.md`. Beide Laeufe der Suite (2205 und 2149 bestanden) und die Browsertests (48 bestanden, 4 uebersprungen) sind auf der umgestellten Entwicklungskopie gruen, bis auf `test_referenz`: Die Referenz ist nicht neu geschrieben.

**Notizfelder.**
- *Mehrzeilig sind jetzt* (je eine `<textarea>`, Klasse `notizfeld`, ausser Renten und Monatsabschluss): die Notiz der Konto-Regel auf `/konten` („Zweck“), die Notiz einer Quelle auf `/renten` (zwei Zeilen sichtbar, beim Klick offen, wie im Monatsabschluss), die Notiz eines Ziels auf `/ziele` beim Bearbeiten und beim Anlegen, die Notiz einer Reihe auf `/reihen`, „Warum“ eines Abos und einer Versicherung auf `/vertraege`. Im Monatsabschluss war die Notiz eines Bestands schon eine `<textarea>`; dort ist nur das `maxlength` weg.
- *Eine Verpflichtung hat auf keiner Seite ein Notizfeld*; ihre Notiz geht nur ueber `/api/verpflichtung`, und der Server kuerzt sie nicht mehr.
- *Kuerzungen vorher:* Reihe und Verpflichtung 200 Zeichen (Server, bei der Reihe auch `maxlength`), Bestand und Rente 2000 (Server und `maxlength`; im Monatsabschluss ebenso), „Warum“ eines Vertrags `maxlength` 200, Konto-Regel seit N.3a 20.000. *Jetzt:* ein Wert, `notizen.MAX` (20.000), gilt fuer jede Notiz eines Eintrags; die Seiten rufen `notizen.eingabe` (Zeilenumbrueche als `\n`, ohne Rand, nicht laenger als `MAX`). Kein `maxlength` an einer Notiz. Die laengste Notiz eines Eintrags in der Entwicklungskopie hat rund 1.500 Zeichen (eine Konto-Regel), die laengste Notiz des Bereichs rund 7.200 (kein Feld bearbeitet sie); ein Test haelt `MAX` bei mindestens dem Doppelten der laengsten Notiz. Die Konvention `notiz-mehrzeilig` steht in `docs/design_conventions.yaml` und verbietet `<input>` und `maxlength` an einer Notiz.
- *Browsertests je Seite* (`tests/test_browser.py`, Abschnitt „Notizfelder“, acht Tests): `/konten`, `/renten`, `/ziele` (Bearbeiten; dazu ein Test fuer Anlegen), `/reihen`, `/abos` und `/versicherungen` (`/vertraege`), Monatsabschluss (Bestand). Jeder legt die Notiz wie `finctl umstellen` sie macht in die Datei (mehrere Absaetze, Leerzeile, eingerueckte Zeile, ohne Datum), oeffnet die Seite und speichert ohne Aenderung: die Dateien bleiben Byte fuer Byte, die Notiz bekommt kein Datum. Dann steht im Feld die Notiz mit allen Umbruechen; eine Zeile aendern und speichern behaelt die uebrigen Umbrueche und setzt das Datum von heute; noch einmal ohne Aenderung speichern aendert nichts. Auf `/renten` und im Monatsabschluss gibt es keinen Knopf „Speichern ohne Aenderung“ (der Knopf heisst „unveraendert“ und legt den Stand von heute ab); dort tippt der Test ein Zeichen und loescht es, so gilt das Feld als bearbeitet und der Text wird mitgeschickt.
- *Auf dem Stand vor der Aenderung* (Worktree auf dem letzten Commit, dieselbe Datei `tests/test_browser.py`) schlagen alle acht fehl. Sechs am Fehler selbst: Speichern ohne Aenderung schreibt eine Datei (die Notiz steht danach in einer Zeile, auf `/ziele` und `/reihen` mit dem Datum von heute), das Anlegen eines Ziels speichert die Notiz in einer Zeile, der Monatsabschluss erreicht den Speichern-Knopf nicht (siehe Abweichung 3). Die Seite der Abos schreibt eine Seitendatei, und fuer die Versicherungen findet der Test auf dem alten Stand keinen Eintrag in der Basisdatei, weil sie dort in der Seitendatei standen; beide scheitern also teils am alten Paar.

**Zusammenlegen** (`finctl/umstellen_paare.py`, drei Paare mehr).
- *`renten`.* Je Quelle ersetzt die Seite Feld fuer Feld, was der alte Leser aus ihr nahm (`cents`, `ab`, `stand`, `kosten_pa`, `beitrag`, `pruefwert`, `stand_cents`, `stand_wert`, `beitrag_ag_cents`). Die Quellen unter `neu:` stehen danach in der Liste `renten`, hinter denen der Basis, mit den Feldern in der Reihenfolge der Datei. Ein Eintrag der Seite ohne Quelle wird gemeldet (der alte Leser las ihn nie), seine Notiz geht in die Notiz des Bereichs.
- *`abos` und `versicherungen`.* Je Kennung ersetzt die Seite Feld fuer Feld; ein Feld, das sie leer laesst, nimmt den Wert der Basis heraus. Ein Vertrag nur in der Seite steht hinter denen der Basis. `betrag` (Euro) und `betrag_cents` sind dasselbe Feld. Ein mit `entfernt: true` ausgeblendeter Vertrag steht nicht in der neuen Datei, nur in der Sicherung; seine Notiz geht mit dem Hinweis „Ausgeblendet bis zur Umstellung“ in die Notiz des Bereichs, und der Bericht nennt ihn.
- *Notizen:* Treffen zwei zusammen, steht die der Basis zuerst, dann die der Seite, getrennt durch eine Leerzeile; das Datum ist das spaetere. Ein Basiswert, den die Seite ersetzte, steht am Ende der Notiz („Bis zur Umstellung stand in der Datei: …“). Ein leerer Wert der Basis (`stand: null`) zaehlt nicht als Wert, den die Seite ueberschrieb.
- *Gilt genau, was galt:* Jedes Paar hat seinen alten Leser in `umstellen_paare.py` (`_renten_alt`, `_vertraege_alt`, dieser ruft `abos.normalisieren`) und liest das Ergebnis mit dem neuen Leser (`renten.aus_spec`, `abos.aus_spec`); beide muessen dieselben wirksamen Werte liefern, sonst wird nichts geschrieben. Dazu: Der Text beider Notizen steht in der zusammengelegten (auch der eines ausgeblendeten oder quellenlosen Eintrags bei der Notiz des Bereichs), und die geschriebene Datei sagt, was sie soll.
- *Auf der Entwicklungskopie:* In allen drei Paaren ueberschrieb die Seite **keinen** Basiswert (0 Notizen mit „Bis zur Umstellung stand …“). Drei Notizen trafen zusammen, alle bei den Renten: die der beiden Policen und die Notiz des Bereichs. Die Seite brachte eine Quelle (`neu:`), neun Abos und acht Versicherungen, die es in der Basisdatei nicht gab; kein Vertrag war ausgeblendet.
- *Die Policen:* Die Herleitung aus `renten.yaml` und die Notiz aus `renten_custom.yaml` stehen wieder beide da, in dieser Reihenfolge, getrennt durch eine Leerzeile, in der einen Notiz (Abnahme N.2, Punkt 2). Das zeigen `/renten` (Notizfeld), `/annahmen` und `/prognosebasis` (Belege), `/bestaende`, `/monatsabschluss` und `/start`. Der Test `…the_note_of_the_base_comes_first…` belegt es an erfundenen Dateien.
- *Der Eintrag `neu:`* gibt es nicht mehr; die Quelle steht als Eintrag in `renten`. *Herkunft* (`basis`, `geaendert`, `eigen`) bei den Abos gibt es nicht mehr; `Quelle` hat kein `eigen`, `basis_cents`, `basis_ab`, `angelegt` und keine `herleitung` mehr (die Notiz ist eine).
- *Fehlt die Basisdatei,* ist die Seitendatei die neue Basisdatei (Test je Paar).

**Leser und Schreiber.**
- `renten` liest nur `renten.yaml` (`quellen`, `aus_spec`), `abos` nur `abos.yaml` und `versicherungen.yaml` (`laden`, `aus_spec`). `ARTEN`, `datei` und die Schnittstellen nehmen eine Datei statt zwei; `EIGEN`, `KOPF`, `CUSTOM_KOPF`, `NOTIZ_ALT`, `_roh_basis`, `_roh_custom` und `dateien()` gibt es nicht mehr.
- Die Schreiber (`renten.setzen`, `anlegen`, `loeschen`; `abos.speichern`, `entfernen`) lesen die ganze Datei, aendern den Eintrag und schreiben ueber `dateien.yaml_schreiben`, mit allen Notizen und dem Block `notizen:`. Der Monatsabschluss schreibt Renten ueber `/api/rente`, also denselben Weg. Speichern ohne Aenderung aendert nichts: `yaml_schreiben` schreibt nur, wenn die Datei danach etwas anderes sagt, und `abos.speichern` vergleicht die Felder des Vertrags (nicht den Text), damit ein von Hand in Euro geschriebener Betrag kein Grund zum Schreiben ist. Daten (`faellig` und Verwandte) stehen als Datum in der Datei; `renten.setzen` und `abos.speichern` halten ein Datum und denselben Tag als Text fuer gleich.
- *Weg sind die Anzeigen, die Basis und Seite verglichen:* auf `/renten` der Knopf „zurueck“ und „loeschen“ nur fuer angelegte Quellen (jetzt „loeschen“ fuer jede), im Monatsabschluss der Hinweis „Zurueck auf renten.yaml“, auf `/vertraege` die Pille „angelegt“ und das Ausblenden mit „Die Begruendung in der Basisdatei bleibt erhalten“ (jetzt „Loeschen“), der Fuss der drei Seiten mit zwei Dateien (jetzt eine), auf `/annahmen` der Beleg, der nur die Notiz der Basisdatei zeigte (jetzt die Notiz der Quelle). Die Konvention `nur-abweichungen-speichern` nennt die fuenf Dateien als schon eine.

**Musterhaushalt und `module.py`.** Der Musterhaushalt hat `renten_custom.yaml`, `abos_custom.yaml` und `versicherungen_custom.yaml` in die Basisdateien gelegt (eine Notiz mit zwei Absaetzen und Datum bei der ersten Police, die betriebliche Altersvorsorge als Eintrag in der Liste); `tests/musterhaushalt/bauen.py` haengt die Buchungen in die Liste der Versicherungen statt in die Zuordnung der Seitendatei. In `module.py` stehen bei „Verträge und Abos“ nur noch `abos.yaml` und `versicherungen.yaml`, bei „Prognose und Planung“ `renten.yaml` statt `renten_custom.yaml`.

**`pruefen --nur-zahlen` an der umgewandelten Kopie.** 10 Unterschiede, alle auf `seiten/`: `abos`, `annahmen`, `bestaende`, `monatsabschluss`, `prognosebasis`, `renten`, `start`, `versicherungen`, `vertraege`, `ziele`. `hauptbuch/` und `ableitung/` sind gleich; kein Betrag aendert sich. Mit Text sind es 20 (dieselben zehn Seiten).
- *Fallen weg:* (Art 1) auf `/abos`, `/vertraege` und `/versicherungen` die 26 Pillen „angelegt“, auf `/renten` die beiden Knoepfe „zurueck“; (Art 3) auf diesen vier Seiten der Fuss „4 Dateien“ samt den Zeilen zur Seitendatei, auf `/bestaende`, `/monatsabschluss` und `/start` der Fuss „10 Dateien“ samt den zwei Zeilen zu `renten.yaml` und `renten_custom.yaml`; (Art 2) auf `/annahmen` und `/prognosebasis` die Zeile des Belegs der betrieblichen Altersvorsorge, die jetzt mit ihrer Notiz weiterlaeuft.
- *Kommen dazu:* (Art 2) die Notizen der Renten, die Herleitung der Basis zuerst: auf `/annahmen` und `/prognosebasis` je 7 Zahlenzeilen, auf `/bestaende`, `/monatsabschluss` und `/start` je 15, auf `/renten` 26; (Art 3) „3 Dateien“ beziehungsweise „9 Dateien“ im Fuss.
- *Zwei Arten von Zeilen, die die Fertig-wenn-Zeile nicht nennt, beide aus den Notizfeldern und nicht aus dem Zusammenlegen:* Auf `/renten` und `/ziele` steht die Notiz jetzt im Text der Seite, weil eine `<textarea>` ihren Inhalt als Text hat und ein `<input value>` nicht (auf `/ziele` zeigt die Seite die Notiz schon in der Kopfzeile des Ziels: 2 Zahlenzeilen, 3 Textzeilen; auf `/renten` die 26 Zahlenzeilen oben). Ich habe beide der Art 2 zugeschlagen, denn die Seite zeigt diese Notiz schon, nur an anderer Stelle. Dazu auf `/renten` drei neue Knoepfe „loeschen“ (Text ohne Ziffer).
- Die Textunterschiede liegen in `notizen/N.3b_pruefen_unterschiede.md` der Entwicklungskopie, der Bericht der Umstellung in `notizen/umstellung_2026-10-09.md`.

**Abgenommen am 09.10.2026 (Opus), Referenz neu geschrieben.**

Nachgeprüft an der Entwicklungskopie:
- Ein zweiter Lauf meldet „Nichts umzustellen“.
- `pruefen --nur-zahlen` meldet dieselben zehn Seiten. Die neuen Zahlen stehen
  im Text der Notizen von Renten. Die Ausgabe liegt in
  `notizen/N.3b_referenz_vor_neuschreiben.txt`.
- Danach habe ich die Referenz neu geschrieben. `pruefen` meldet „Gleich“.

Entscheidungen:
- **„löschen“ an jeder Rente:** angenommen, mit Rückfrage, auch bei der
  gesetzlichen Rente. Eine Sperre für eine bestimmte Art wäre ein Einzelfall
  im Code.
- **Ausgeblendete Abos und Versicherungen fallen beim Umstellen aus der
  Datei:** angenommen. Gelesen wird damit genau, was vorher galt. Der Bericht
  nennt sie unter „ausgeblendet“, und die Sicherung behält sie. Beim Umstieg
  zeigt die Probe des echten Ordners sie, bevor etwas geschrieben wird; das
  steht in der Liste für den Umstieg.
- **Inhalt der Notiz zählt als Text der Seite:** Seit sie in einem
  `<textarea>` steht, zählt `/renten` und `/ziele` ihren Inhalt mit. Das ist
  als Art 2 angenommen.
- **Enter, verlorener Klick, Ziel nur in der Seitendatei:** angenommen. Der
  letzte Punkt geht in N.3d.
- **Sätze in Notizen über Seitendateien, die es nicht mehr gibt:** Das ist
  Text des Haushalts, den die Umwandlung nicht umschreibt. Schritt 6 macht
  Notizen sichtbar, dann fallen sie auf.

**Umgesetzt am 09.10.2026, N.3c (Sonnet): `properties` und `loans`.** Geprueft an einer frischen Kopie der Entwicklungskopie im Scratchpad (mit `data/referenz/`), dann die Entwicklungskopie selbst mit `finctl umstellen` umgestellt: ihre `config/` gleicht der Kopie Byte fuer Byte (die Probe auf ihr vorher auch), ein zweiter Lauf meldet „Nichts umzustellen“, die Pruefsumme von `config/`, `archiv/`, `notizen/` und `data/referenz/` bleibt gleich. Sicherung: `archiv/vor_umstellung_2026-10-09_2/`, Bericht: `notizen/umstellung_2026-10-09_2.md`. Beide Laeufe der Suite (2234 auf der Entwicklungskopie, 2178 auf dem Musterhaushalt) und die Browsertests (48 bestanden, 4 uebersprungen) sind gruen, bis auf `test_referenz`: Die Referenz ist nicht neu geschrieben. (Im ersten Browserlauf auf der Scratchpad-Kopie brach ein Test im Aufbau ab; allein und in drei weiteren Laeufen lief er durch.)

**`loans`.** `finctl/umstellen_paare.py`, `_kredite_legen`:
- *`kredite.<id>`* (auf der Seite angelegte oder geaenderte Kredite): Je Kredit der Basis ersetzt die Seite Feld fuer Feld, was sie nennt. Ein Kredit nur in der Seite steht danach hinter denen der Basis; `entfernt: true` nimmt einen Kredit aus der Datei (er steht nur in der Sicherung, seine Notiz mit „Ausgeblendet bis zur Umstellung“ in der Notiz des Bereichs; der Bericht nennt ihn unter „ausgeblendet“).
- *`vorlagen.<id>`* wird der Schluessel **`vorlage`** am Kredit. Die Konditionen des Eintrags bleiben darunter stehen, und `lade_kredite` (`realestate.loan.aus_spec`) wendet die Vorlage an wie vorher: nur fuer einen Kredit an einer Klammer, ueber `mit_vorlage`. Eine Vorlage zu einem Kredit der Basis geht mit, auch wenn er keine Klammer hat (der alte Leser ignorierte sie dort; der neue auch); eine zu einem Kredit, den es in der Basis nicht gibt, oder zu einem ausgeblendeten, wird nicht uebernommen und steht im Bericht unter „kein Leser kannte“.
- *`anschluss.<id>`* wird der Schluessel **`anschluss_eingegeben`** am Kredit (so heisst es auf der Seite: „eingegeben“, „Aus deiner Eingabe“). Er steht neben dem `anschluss` des Eintrags, das die Prognose liest (`segments_from`); `anschluss_eingegeben` liest nur `/kredite` und `fristen.py`. Ein Test belegt es (`…follow_up_the_page_entered_changes_no_number_the_forecast_reads`, ueber `forecast.jahre._tilgungsplaene`): Mit und ohne `anschluss_eingegeben` sind alle Raten der Tilgungsplaene gleich, ohne das `anschluss` der Datei aendern sie sich. Der Umwandler legt die Eingabe der Seite nie nach `anschluss`.
- *Die Entwicklungskopie hat kein `anschluss`* in der Seitendatei (die Zuordnung war leer). Getestet ist es an einem erfundenen Datenordner mit Eintraegen in allen drei Teilen (`tests/test_umstellen_paare.py`, `KREDITE_SEITE`): ein geaenderter Kredit, ein ausgeblendeter, zwei nur in der Seite, drei Vorlagen (eine zu einem Kredit der Basis ohne Klammer, eine zur Klammer, eine zu keinem Kredit), drei Anschlusskonditionen (eine zu einem ausgeblendeten Kredit).
- *`segments_observed[].note` und `open`:* unveraendert seit N.2. Die Bemerkung eines Teilstuecks steht als „Teilstueck <Zeitraum>: …“ in der Notiz des Kredits, `open` bleibt ein eigenes Feld, `/kredite` zeigt es. Der Umwandler fasst beides nicht an. `loans[].note` ist seit N.2 die Notiz des Kredits.
- *Auf der Entwicklungskopie:* kein Basiswert war ueberschrieben, keine Notizen trafen zusammen. Aus der Seite kam eine Vorlage (zum Kredit an der Klammer). `kredite` und `anschluss` waren leer, kein Kredit war ausgeblendet.

**`properties`.** `_objekte_legen`:
- *Je Objekt* ersetzt die Seite Feld fuer Feld, was sie nennt (jedes Feld, wie der alte Leser `{**basis, **seite}` las). Die **Prognose** (`prognose`) legt Unterfeld fuer Unterfeld zusammen: Wer nur die Miete tippte, behielt Kosten, Beginn, Ende und Saison. Ein Objekt nur in der Seite steht hinter denen der Basis; `entfernt: true` nimmt ein Objekt aus der Datei, wie bei den Krediten.
- *Notizen:* Treffen zwei zusammen, steht die der Basis zuerst; ein Basiswert, den die Seite ersetzte (auch `prognose.<unterfeld>`), steht in einer einzigen Aufzaehlung am Ende der Notiz („Bis zur Umstellung stand in der Datei: …“). Ein Feld, das es in der Basis nicht gab, steht im Bericht unter „Was die Seite brachte“.
- *Auf der Entwicklungskopie:* kein Basiswert war ueberschrieben, keine Notizen trafen zusammen. Aus der Seite kam ein Feld (`afa_start`) zu dem Objekt, das im Bau ist; das Objekt hatte es nicht.
- *`overlays.objekte`, `objekt_setzen` und `OBJEKTE_KOPF` gibt es nicht mehr.* `/api/property/<id>` schreibt ueber `objekte.felder_setzen` ins Objekt in `properties.yaml` (leere Felder nehmen die Angabe heraus; Felder, die dem Stand der Tabelle gleichen, werden nicht geschrieben). `overlays.anwenden` spiegelt nur noch die Einstellungen (bis N.3f). Die zehn Felder, die es bei `finctl init` in die Tabelle `properties` spiegelte (`DB_FELDER`), spiegelt jetzt `objekte.in_db` aus `properties.yaml`, aufgerufen von `init` gleich nach `anwenden`. Es ist verschoben, weil `tests/test_module.py` verbietet, dass der Kern (`overlays`) ein Modul (`objekte`, Immobilien) importiert. Gleich bleibt: Ein Feld der Datei gewinnt, wo es etwas sagt (`null` laesst die Zeile, wie sie ist). Neu ist nur, dass auch ein `sold_on` der Datei ankommt, das `init` bisher nur aus dem Overlay kannte; in der Entwicklungskopie steht keines. `hauptbuch/` bleibt dabei gleich (siehe `pruefen`).

**Leser und Schreiber.**
- `lade_kredite`/`aus_spec` (`realestate.loan`), `kredite` (`lesen`, `speichern`, `anlegen`, `entfernen`, `an_kredit_setzen`, `tilgungsplan`), `fristen.alle` und `objekte` (`lesen`, `aus_spec`, `vorhandene`, `anlegen`, `entfernen`, `felder_setzen`, `prognose_setzen`, `in_db`) lesen und schreiben nur `loans.yaml` und `properties.yaml`. `BASIS`, `EIGEN` und `KOPF` beider Module, `ANSCHLUSS_KOPF` und `VORLAGEN_KOPF` in `r/kredite.py` gibt es nicht mehr; `kredite.DATEI`, `VORLAGE` und `ANSCHLUSS` nennen die Dateien und Schluessel.
- Schreiber: `/kredite` (Anlegen, Entfernen, `/api/kredit-anschluss`, `/api/kredit-vorlage`) und `/immobilien` und `/immobilie/<id>` (Anlegen, Entfernen, die Zahlen, die Prognose) lesen die ganze Datei, aendern den Eintrag und schreiben sie ueber `dateien.yaml_schreiben`, mit allen Notizen und dem Block `notizen:`. Speichern ohne Aenderung aendert kein Byte (`yaml_schreiben` schreibt nur, wenn die Datei danach etwas anderes sagt; die Prognose nimmt ein Datum und `JJJJ-MM` fuer denselben Monat). Im Browser deckt es `test_speichern_ohne_aenderung_aendert_keine_datei` fuer `/kredite` (Vorlage, ohne Aenderung) und `/immobilie/<objekt>` ab.
- *Weg sind die Anzeigen, die Basis und Seite verglichen:* In den Fussnoten von `/kredite`, `/immobilien` und `/immobilie/<objekt>` die Zeilen zur Seitendatei (jeweils eine Datei weniger). Sonst zeigte keine der Seiten eine Herkunft („eigen“, Basis neben Wert); die Seiten lasen schon bisher das Zusammengelegte. Die Konvention `nur-abweichungen-speichern` nennt die beiden Dateien als schon eine.
- *Notizfelder:* `/kredite` und `/immobilien`/`/immobilie/<objekt>` (die Seiten heissen so, es gibt kein `/objekte`) haben **kein** Feld fuer die Notiz eines Eintrags, auch vorher nicht; Entscheidung 9 haelt Notizen sichtbar fuer Schritt 6. Es entsteht deshalb keine `<textarea>`, und es gibt dort keine Kuerzung. Dass die Schreiber die Notiz und ihr Datum beim Speichern behalten, belegen die Tests (`test_notizen_eintraege.py`, `…a_property_keeps_its_note…`, `…the_conditions_a_page_sets_keep_the_note_of_the_loan`; `test_notizen_seiten.py`, `…follow_up_terms…`). Die laengste Notiz eines Kredits oder Objekts hat rund 4.100 Zeichen, `notizen.MAX` ist 20.000.

**Musterhaushalt und `module.py`.** Der Musterhaushalt hat `loans_custom.yaml` (die Vorlage des Kredits an der Klammer) als `vorlage` in `loans.yaml` und `properties_custom.yaml` (`afa_start` des Objekts im Bau) in `properties.yaml` gelegt; beide Seitendateien sind entfernt. In `module.py` stehen bei „Kredite“ nur noch `loans.yaml`, bei „Immobilien“ nur noch `properties.yaml`.

**`pruefen` an der umgewandelten Kopie.** `--nur-zahlen`: 6 Unterschiede, alle auf `seiten/`: `kredite`, `immobilien` und die vier `immobilie/<objekt>`. `hauptbuch/` und `ableitung/` sind gleich; kein Betrag aendert sich. Mit Text sind es 12 (dieselben sechs Seiten). Auf jeder der sechs Seiten ist es **eine** Zahlenzeile, die Zahl im Fuss „Konfiguration — n Dateien“, eine weniger (Art 3). Dazu der Text des Fusses: die Zeile zur Seitendatei faellt weg, die Beschreibung der einen Datei wird laenger. Arten 1 und 2 kommen nicht vor: Keine der Seiten zeigte einen Wert der Basis neben dem gueltigen, und keine zeigt die Notiz eines Kredits oder Objekts. Die Textunterschiede liegen in `notizen/N.3c_pruefen_unterschiede.md` der Entwicklungskopie, der Bericht der Umstellung in `notizen/umstellung_2026-10-09_2.md`. Auf der Entwicklungskopie selbst meldet `pruefen` dieselben Unterschiede wie auf der Kopie.

**Tests.** `tests/test_umstellen_paare.py` (Abschnitt N.3c): das Paar je Feld, die Vorlage am Kredit, `anschluss` und `anschluss_eingegeben` getrennt, die Prognose je Unterfeld, ausgeblendete Eintraege, die Notiz mit dem ersetzten Wert, „liest sich wie beide Dateien“ (`alt` gegen `neu`), der Lauf mit zweitem Lauf, nur Basis, nur Seite, Kommentare in beiden, die Fristen, die Tabelle `properties`, und: Leser und Schreiber lassen eine stehengebliebene Seitendatei unberuehrt. Ersetzt sind die Tests der alten Form in `test_kredite_anlegen.py`, `test_objekte_anlegen.py`, `test_objektprognose.py`, `test_notizen_eintraege.py`, `test_notizen_seiten.py`, `test_server_rechnet.py`, `test_web.py`, `test_browser.py`, `test_umbenennung.py` und `test_umstellen.py` (die Koepfe von `loans_custom` und `properties_custom` stehen nur noch im Umwandler).

**Abgenommen am 12.10.2026 (Opus), Referenz neu geschrieben.**

Nachgeprüft an der Entwicklungskopie:
- Ein zweiter Lauf meldet „Nichts umzustellen“. `loans_custom.yaml` und
  `properties_custom.yaml` sind weg; gegenüber der Sicherung kamen genau die
  Vorlage am Kredit an der Klammer und `afa_start` am Objekt im Bau dazu.
- `pruefen --nur-zahlen` meldet dieselben sechs Seiten. Jede Zahlenzeile ist
  die Zahl im Fuß, eine weniger (Art 3); `hauptbuch/` und `ableitung/` sind
  gleich. Die Ausgabe liegt in `notizen/N.3c_referenz_vor_neuschreiben.txt`.
- Die Tests der Paare, der Kredite, Objekte, Notizen, `test_module`,
  `test_leck` und `test_namen` sind auf beiden Daten grün. Der Test zur
  Anschlusskondition rechnet die Tilgungspläne der Prognose mit und ohne
  `anschluss_eingegeben` und mit und ohne `anschluss`.
- Danach habe ich die Referenz neu geschrieben. `pruefen` meldet „Gleich“.

Entscheidungen zu den Abweichungen:
1. **`vorlage` bleibt ein eigener Schlüssel am Kredit:** bestätigt. Gelesen
   wird genau, was vorher galt, und die Tabelle `loans` bleibt gleich.
   Eingebacken wäre die Vorlage eine Tatsache geworden, die keine ist.
2. **`anschluss_eingegeben`:** bestätigt, ebenso die 404 für einen Kredit,
   den es nicht gibt. Ob die Eingabe in die Prognose gehört, bleibt die
   Frage für später (N.0, Abnahme Nummer 4).
3. **400 für ein Objekt ohne Eintrag:** bestätigt.
4. **Entfernen löscht den Eintrag samt Notiz:** angenommen, wie bei den
   Renten in N.3b. Die Rückfrage bleibt, wie sie ist: Solange die Notiz nicht
   sichtbar ist, sagt ein Hinweis auf sie wenig, und Renten und Abos nennen
   sie auch nicht. Schritt 6 nennt die Notiz in jeder Rückfrage zum Entfernen;
   das steht im Gesamtplan.
5. **Ein leeres Feld der Objektprognose löscht die Angabe:** angenommen.
   Ohne Basis gibt es keinen Wert, der wieder gelten könnte.
6. **Andere Leser von `loans.yaml` sehen, was die Seite schrieb:** gewollt;
   so soll es mit einer Datei sein. Für den echten Ordner kann das die Tabelle
   `loans` ändern, wenn dort Kredite auf `/kredite` angelegt sind. N.4 zeigt
   es an der Probe.
7. **`objekte.in_db` statt `overlays.anwenden`:** angenommen, die Grenze
   zwischen Kern und Modul gilt vor.
8. **`Paar.seitenwurzel`:** angenommen.
9. **Umstieg:** Die Punkte stehen jetzt in der Liste für den Umstieg im
   Gesamtplan, neben den ausgeblendeten Abos aus N.3b.

**Umgesetzt am 12.10.2026, N.3d (Sonnet): `ziele` und `balances`.** Geprueft an einer frischen Kopie der Entwicklungskopie im Scratchpad (mit `data/referenz/`, `finance.db` und verknuepften Auszuegen), dann die Entwicklungskopie selbst mit `finctl umstellen` umgestellt: ihre `config/` gleicht der Kopie Byte fuer Byte (die Probe auf ihr vorher auch), ein zweiter Lauf meldet „Nichts umzustellen“, die Pruefsumme von `data/referenz/` bleibt gleich. Sicherung: `archiv/vor_umstellung_2026-10-12/`, Bericht: `notizen/umstellung_2026-10-12.md`. Beide Laeufe der Suite (2274 auf der Entwicklungskopie, 2218 auf dem Musterhaushalt) und die Browsertests (48 bestanden, 4 uebersprungen) sind auf der umgestellten Entwicklungskopie gruen, bis auf `test_referenz`: Die Referenz ist nicht neu geschrieben.

**`ziele`.** `finctl/umstellen_paare.py`, `_ziele_legen`:
- *Je Ziel* ersetzt die Seite Feld fuer Feld, was sie nennt (alle Felder, wie der alte Leser `{**basis, **seite}` las). Ein Ziel nur in der Seite steht danach hinter denen der Basis, in der Reihenfolge der Seitendatei, mit den Feldern in der Reihenfolge der Datei (Kennung, Name, Betrag, Stichtag, Basis, Notiz). `entfernt: true` nimmt ein Ziel aus der Datei; seine Notiz steht mit „Ausgeblendet bis zur Umstellung“ in der Notiz des Bereichs, der Bericht nennt es unter „ausgeblendet“.
- *`reihenfolge`* gibt es nur in der Seitendatei. Es wird der Schluessel `reihenfolge` oben in `goals.yaml`, hinter `ziele`. Hatte die Basis schon eine, steht sie als „Bis zur Umstellung stand in der Datei: `reihenfolge`: …“ in der Notiz des Bereichs. Die Reihenfolge gilt danach auch fuer Ziele, die dort nicht genannt sind: `progress` sortiert erst nach Stichtag und Platz in der Liste und stellt dann die genannten voran, die anderen folgen dahinter (unveraendert). Ein Test rechnet `progress` an beiden Lesern (`ziele_alt_gelesen` gegen `aus_spec`): dieselbe Folge, auch mit einem Ziel, das die Anordnung nicht nennt. Die Liste selbst behaelt die Folge der alten Zusammenfuehrung (Basis, dann Seite), sie entscheidet bei gleichem Stichtag.
- *`eigen: True`* war eine Markierung des Lesers fuer ein Ziel nur in der Seitendatei („Auf dieser Seite angelegt“). Es gibt sie nicht mehr, und die Pille „eigen“ auf `/ziele` auch nicht. Die Vorgabe fuer einen Notgroschen ohne Betrag bleibt **Lesen**, nicht Backen: `aus_spec` setzt drei Gehalts-Untergrenzen ein, wenn das Ziel keinen Betrag traegt; der Umwandler schreibt sie nie in die Datei (Test), und wer die Untergrenze aendert, verschiebt sie mit. Auch Speichern auf `/ziele` backt sie nicht ein: `api_ziel` schreibt Betrag und Notiz nur, wenn sie von dem abweichen, was die Seite vorher zeigte.
- *N.3b, Punkt 4 (Name):* Ein Ziel nur in der Seitendatei ohne Namen bekommt beim Umstellen `name:` mit seiner Kennung, hinter der Kennung. Das ist der Name, den die Seite zeigte. Ausserdem schreibt `api_ziel` einen Namen nur, wenn er vom angezeigten abweicht: Speichern ohne Aenderung schreibt kein Byte, auch bei einem Ziel, das keinen Namen traegt (Test `…a_goal_without_a_name_shows_its_id_and_saving_writes_no_name`; im Browser `test_notiz_eines_ziels_ist_mehrzeilig`). Neu angelegte Ziele tragen ihren Namen immer.
- *Die sieben Stellen von `merge_edits`* (`cli.py`, `monatsabschluss.py`, `r/ziele.py`, `r/annahmen.py` zweimal, `r/einrichtung.py`, `r/auswertung.py`) rufen `ziele.aus_spec(goals.yaml)` mit nur dieser Datei; `merge_edits` gibt es nicht mehr. Dazu `r/planung.py`, das `goals.yaml` roh las (und damit die Ziele der Seite nie sah): Es liest jetzt ebenfalls `aus_spec`. Die Vorlage nutzt das Ergebnis (`fire`) nicht; nichts auf der Seite aendert sich (Abweichung 1).
- *Auf der Entwicklungskopie:* ein Basiswert war ueberschrieben (die `basis` des ersten Ziels; ihr Betrag war gleich, und ihr Stichtag fehlte in der Basis), zwei Notizen trafen zusammen (das erste Ziel und die Notiz des Bereichs), zwei Ziele kamen nur aus der Seite. Keine `reihenfolge`, kein ausgeblendetes Ziel.

**`balances`.** `_balances_legen`:
- *Je Bestand* (Schluessel `account_id`, sonst `name`) ersetzt die Seite Wert, Stichtag, Gewinn und die vier Felder des Rueckkaufswerts (`cents`, `as_of`, `gewinn_cents`, `rueckkauf_cents`, `rueckkauf_as_of`, `eingezahlt_cents`, `rueckkauf_policenwert_cents`), wo sie sie nennt; ein leeres Datum ersetzt nichts. Was der alte Leser sonst aus einem Eintrag der Seite nahm, gab es nicht. Ein Eintrag der Seite ohne Position in der Datei las kein Leser: Er steht im Bericht, seine Notiz mit „Zu `overrides.<Schluessel>` (keine Position dazu)“ beim Bereich.
- *Je Verpflichtung* (Schluessel `bestaende.kennung(name)`, der Name klein, ohne Sonderzeichen) ersetzt die Seite `cents` und `name`. `geloescht: true` nimmt die Verpflichtung aus der Datei, ihre Notiz geht zum Bereich. Eine Verpflichtung nur in der Seite steht danach hinter denen der Basis. Aendert die Seite den Namen, aendert sich die Kennung; `Zusammenlegung.umbenannt` haelt alt und neu fest, damit die Pruefung der Notizen folgt. Heissen zwei danach gleich, wird nichts geschrieben.
- *`verlauf`* hat keine Basis. Es wird der Schluessel `verlauf` in `balances.yaml`, hinter `obligations`, in derselben Form (`<Position>.<Periode>`); `bestaende.verlauf(spec)` liest ihn. Hatte die Basis einen, las ihn nie ein Leser: Er steht im Bericht und kommt nicht in die Datei.
- *Konto mit Auszug.* Aus der Seitendatei zaehlte fuer ein Konto mit Auszug allein die Notiz. Ob ein Konto einen Auszug hat, sagt `ingest_mode: parsed` in `accounts.yaml` (und, wo es sie gibt, `accounts_custom.yaml`); `Paar.kontext` gibt dem Zusammenleger diese Menge. Fuer ein solches Konto uebernimmt er nur die Notiz. Ein Betrag oder ein Datum, den die Seite trotzdem trug, steht danach **nur in der Notiz**: „Bis zur Umstellung stand auf der Seite, und galt nicht, weil das Konto seinen Stand aus dem Auszug liest: …“; der Bericht nennt ihn unter „kein Leser kannte“. In die Datei kommt er nicht, weil `finctl init` die Datei liest. Test `…the_number_of_an_account_with_a_statement_stays_the_statement…`: ein Hauptbuch mit einem Auszug, der Bestand aus der Basis allein und aus der zusammengelegten Datei (mit dem Wert der Seite in der Notiz) liefern denselben Wert und denselben Stichtag aus dem Auszug. `zusammenfuehren` liest den Wert aus dem Auszug, nie aus der Datei (Test `test_accounts_with_statements_come_only_from_statements` mit einem falschen Wert in der Datei). In der Kopie trug kein Konto mit Auszug einen Wert der Seite; der Fall ist an erfundenen Dateien geprueft.
- *Die acht Module*, die `balances_custom.yaml` nannten (`bestaende.py`, `cli.py`, `module.py`, `r/annahmen.py`, `r/auswertung.py`, `r/konten.py`, `r/planung.py`, `r/ziele.py`), lesen und schreiben nur noch `balances.yaml`; `module.py` fuehrt dort `balances.yaml` bzw. `goals.yaml`. `bestaende.zusammenfuehren(conn, spec)` hat nur noch die eine Datei; `overlay`, `basisdatei`, `basis_position` und `basis_verpflichtung` gibt es nicht mehr, dafuer `lesen`, `position`, `verpflichtung` und `verlauf`.
- *Auf der Entwicklungskopie:* acht Basiswerte standen in Notizen (Datum an fuenf Positionen, Betrag an dreien: vier Depots und ein Kryptobestand), fuenf Notizen trafen zusammen (vier davon bei diesen Positionen, eine bei einer Police), drei Depots und ein Kryptobestand bekamen `gewinn_cents` und zwei Policen die Felder des Rueckkaufswerts nur aus der Seite; die eine Verpflichtung der Basis war mit `geloescht` gestrichen: Sie steht nicht mehr in der Datei, ihre Notiz mit „Ausgeblendet bis zur Umstellung“ beim Bereich. Kein `verlauf`, keine neue Verpflichtung.

**Zusammenlegen.**
- *Gilt genau, was galt?* Jedes Paar hat seinen alten Leser in `umstellen_paare.py` (`ziele_alt_gelesen`/`_ziele_alt`, `_balances_alt`) und liest das Ergebnis mit dem neuen (`ziele.aus_spec`, die Datei und `bestaende.verpflichtungen`); beide muessen dieselben Werte liefern, sonst wird nichts geschrieben. Tests „liest sich wie beide Dateien“ je Paar (`test_the_merged_goals_file_reads_like_both_files_did`, `test_the_merged_balances_file_reads_like_both_files_did`) und ein Test, dass ein Zusammenleger, der eine Reihenfolge oder einen Gewinn verliert, nichts schreibt. Dazu: Der Text beider Notizen steht in der zusammengelegten (auch der eines ausgeblendeten Ziels oder einer gestrichenen Verpflichtung beim Bereich).
- *Zahlen der Entwicklungskopie:* Ziele 1 Basiswert in einer Notiz, 2 Notizen zusammengetroffen, 2 Ziele nur aus der Seite; Bestaende 8 Basiswerte in Notizen, 5 Notizen zusammengetroffen, 1 Verpflichtung ausgeblendet.
- *Der abweichende Kopf von `ziele_custom.yaml`* (N.0, Nummer 9; eine Zahl weicht von der Konstante ab) fiel nach Entscheidung 3 nicht weg und stand seit N.2 in der Notiz des Bereichs der Seitendatei. Er steht danach in der Notiz des Bereichs von `goals.yaml`, hinter der Notiz der Basis (Test `…the_odd_head_of_the_goals_page_file…`). Der Kopf von `balances_custom.yaml` stimmte wortlich und fiel weg.
- *Fehlt die Basisdatei,* gilt die Startvorlage (`goals.yaml`, `balances.yaml`) als Basis, denn so las es die App.

**Leser und Schreiber.**
- `/api/ziel` (`routen/ziele.py`), `/api/ziele/reihenfolge`, `/api/bestand` und `/api/verpflichtung` (`routen/konten.py`) lesen die ganze Datei, aendern den Eintrag und schreiben ihn ueber `dateien.yaml_schreiben`, mit allen Notizen und dem Block `notizen:`. Der Monatsabschluss schreibt Staende ueber `/api/bestand`, also denselben Weg; `/konten` zeigt Policen aus derselben Datei. Speichern ohne Aenderung aendert kein Byte (Server-Tests `test_saving_a_goal_without_a_change_changes_nothing`, `test_a_note_sent_with_windows_line_breaks…`; im Browser `test_speichern_ohne_aenderung_aendert_keine_datei` und die Notiztests fuer Ziel und Bestand, die ohne Aenderung speichern). Ein Datum, das dieselben Tag als Text und als Datum sagt, ist keine Aenderung.
- *Weg sind die Anzeigen, die Basis und Seite verglichen:* auf `/ziele` die Pille „eigen“ (`eigen`), der Zweig `zuruecksetzen` der Schnittstelle und die Fusszeile zu `ziele_custom.yaml`; im Monatsabschluss (und damit `/bestaende`, `/start`) der Knopf „zurueck“ mit `standZurueck` und `remove` der Schnittstelle, `eigen` (`overridden`, `note_eigen`) und `base_cents`/`base_note` der Zeilen von `bestaende_daten`, die Fusszeile zu `balances_custom.yaml` und der Satz „Die Begruendung in balances.yaml bleibt“ in der Rueckfrage beim Streichen einer Verbindlichkeit (jetzt: „Die Notiz geht mit“); auf `/konten` und `/ziele` die Fusszeilen zu `balances_custom.yaml`. `basis_cents`, `basis_ab` und `base_note` im engeren Sinn (Renten) waren seit N.3b weg. Streichen einer Verbindlichkeit und Loeschen eines Ziels nehmen den Eintrag samt Notiz aus der Datei (wie bei den Krediten in N.3c); `/api/bestand` kennt keine Position mehr, die nicht in der Datei steht (404 statt eines Eintrags, den kein Leser las).
- `finctl init` (`_bestaende_spiegeln`): Der Schnappschuss eines Tages sind die Positionen, die fuer diesen Tag gelten (Datum der Datei oder keines eigenes); ein Stand, den die Seite spaeter eintrug, traegt sein Datum und gehoert in den Verlauf (Abweichung 2).
- *Browsertests (N.3b, Punkt 11):* `test_notiz_eines_ziels_ist_mehrzeilig` legt die Notiz in `goals.yaml` (das Ziel in der Liste), `test_notiz_eines_bestands_ist_mehrzeilig` in die Position in `balances.yaml`; die Tests zum Verlauf und zum Rueckkaufswert lesen und vergleichen `balances.yaml`.

**Notizfelder.** Es gibt keine Kuerzung unter `notizen.MAX` mehr: weder `BESTAND_NOTIZ_MAX` noch `[:NOTIZ_MAX]` bei einer Verpflichtung (beide Seiten lesen `notizen.eingabe`; ein Bestand und eine Verpflichtung gehen ueber dieselbe Stelle). Die laengste Notiz in der Entwicklungskopie: ein Ziel 240 Zeichen, ein Bestand 889; keine Verpflichtung traegt mehr eine (die ausgeblendete hatte 126), die Notiz des Bereichs von `balances.yaml` rund 4.300 und die von `goals.yaml` rund 2.900. `notizen.MAX` ist 20.000. Namen kuerzt der Server weiter (Ziel 80 Zeichen, Konto `FELD_MAX`); das sind keine Notizen.

**Musterhaushalt, `finctl/vorgaben/`, `module.py`.** Der Musterhaushalt hat `balances_custom.yaml` (den Stand eines Kryptobestands und den Verlauf) in `balances.yaml` und `ziele_custom.yaml` (Notizen, Stichtage und zwei Ziele) in `goals.yaml` gelegt; beide Seitendateien sind entfernt. Beleg: Der Zusammenleger auf den alten Dateien (aus Git) liefert dieselben Daten wie die von Hand geschriebenen Dateien, und beide Paare lesen sich wie vorher (Test an den Dateien selbst bei der Sitzung, kein Dauertest, weil die alten Dateien nicht mehr im Baum stehen). `finctl/vorgaben/` ist unveraendert: Dort schreibt die App keine Seitendatei, und die Vorlagen tragen keine Notiz ueber eine. In `module.py` stehen bei „Prognose und Planung“ `balances.yaml` statt `balances_custom.yaml` und bei „Ziele“ nur noch `goals.yaml`.

**`pruefen --nur-zahlen` an der umgewandelten Kopie.** 5 Unterschiede, alle auf `seiten/`: `bestaende`, `monatsabschluss`, `start`, `konten`, `ziele`. `hauptbuch/` (12 Dateien) und `ableitung/` (8 Dateien) sind Byte fuer Byte gleich; kein Betrag aendert sich. Mit Text sind es 10 (dieselben fuenf). `/bestaende`, `/monatsabschluss` und `/start` sind eine Seite in drei Dateien; ich zaehle sie getrennt, sie tragen je dieselben Zeilen.

| Seite | faellt weg | kommt dazu | Art |
|---|---|---|---|
| `bestaende`, `monatsabschluss`, `start` je | Zahlenebene: 1 Zeile, die Zahl im Fuss („9 Dateien“) | 1 Zeile, „8 Dateien“ | 3 |
| dieselben je | Text: 7× „zurueck“ an Positionen, die die Seite ueberschrieben hatte | die Zeilen „unveraendert“ ohne „zurueck“ | 1 |
| dieselben je | Text: im Fuss „9 Dateien“, die Zeile `balances_custom.yaml` mit ihrer Beschreibung, die alte Beschreibung von `balances.yaml` | „8 Dateien“, eine Beschreibung, die beides sagt | 3 |
| dieselben je | — | Zahlenebene: 16 Zeilen; Text: 19 Zeilen aus den Notizen der Positionen: die Notiz der Basis, die bisher die der Seite verdeckte, und fuenfmal „Bis zur Umstellung stand in der Datei: …“ (die Ziffern in Betraegen, Daten und Absaetzen der Notizen) | 2 |
| `konten` | Zahlenebene 1 Zeile („10 Dateien“); Text: 4 Zeilen im Fuss (die Zahl, `balances_custom.yaml` mit Beschreibung, die alte Beschreibung) | „9 Dateien“, eine Beschreibung (2 Zeilen) | 3 |
| `ziele` | Zahlenebene: 1 Zeile im Fuss („8 Dateien“) und 1 Zeile mit Stichtag und Ziffern der Notiz des ersten Ziels; Text: die Pille „eigen“ an zwei Zielen, im Fuss `ziele_custom.yaml` und `balances_custom.yaml` mit Beschreibungen, die Zahl und die alte Beschreibung von `goals.yaml`; die zwei Zeilen mit dem Stichtag und der Notiz des ersten Ziels | Zahlenebene: „6 Dateien“ und 3 Zeilen der Notiz; Text: die Notiz der Basis zuerst, dann die der Seite, dann „Bis zur Umstellung stand in der Datei: `basis`: …“, in Kopfzeile und Notizfeld; Fuss mit sechs Dateien | 1 (die Pillen), 2 (die Notiz), 3 (der Fuss) |

Eine Zeile, die in keine der drei Arten passt, gibt es nicht. Auf `/ziele` ist die Ziffernzeile mit dem Stichtag eine Art-2-Zeile: Die Notiz steht in einem Feld, das ihren Text zeigt, und ihr Umbruch hat die Zeile verschoben. Die Textunterschiede liegen in `notizen/N.3d_pruefen_unterschiede.md` der Entwicklungskopie, der Bericht der Umstellung in `notizen/umstellung_2026-10-12.md`. Auf der Entwicklungskopie selbst meldet `pruefen` dieselben Unterschiede wie auf der Kopie.

**Tests.** `tests/test_umstellen_paare.py` (Abschnitt N.3d): je Paar das Zusammenlegen je Feld; Kennung und Name eines Ziels nur der Seite; „liest sich wie beide Dateien“; ersetzte Basiswerte in der Notiz, die Notizen Basis zuerst; `reihenfolge` und Reihenfolge von `progress`; ausgeblendete Ziele und gestrichene Verpflichtungen beim Bereich; die Vorgabe des Notgroschens bleibt Lesen; Konto mit Auszug (Wert nur in der Notiz, Zahl bleibt der Auszug); Verpflichtungen (umbenannt, doppelt, neu); `verlauf`; der Lauf mit zweitem Lauf, nur Basis, nur Seite, Kommentare in beiden; der abweichende Kopf; ein Lauf, in dem ein Zusammenleger etwas verliert, schreibt nichts; Leser und Schreiber lassen eine stehengebliebene Seitendatei unberuehrt; Speichern ohne Aenderung schreibt nach dem Umwandeln kein Byte (Ziele mit und ohne Namen, Bestand); `finctl init`. Ersetzt sind die Tests der alten Form in `test_web.py`, `test_ziele.py`, `test_ziele_seite.py`, `test_notizen_eintraege.py`, `test_notizen_seiten.py`, `test_stichtag_verlauf.py`, `test_notfallwert.py`, `test_rueckkauf.py`, `test_wirkung.py`, `test_wirkung_seite.py`, `test_umstellen.py` und `test_browser.py`.

**Abgenommen am 12.10.2026 (Opus), Referenz neu geschrieben.**

Nachgeprüft an der Entwicklungskopie:
- Ein zweiter Lauf meldet „Nichts umzustellen“. `balances_custom.yaml` und
  `ziele_custom.yaml` sind weg.
- Gegen die Sicherung gelesen: Jeder Wert der Seitendatei steht an seiner
  Position in `balances.yaml`, jeder andere Wert der Basis ist unverändert,
  die Folge der Positionen auch. Die gestrichene Verpflichtung fehlt, ihre
  Notiz steht beim Bereich. `goals.yaml` hat die drei Ziele mit Namen.
- `pruefen --nur-zahlen` meldet dieselben fünf Seiten. Was auf `/bestaende`
  dazukommt, sind Ziffern aus den Notizen der Positionen (Art 2); dazu der
  Fuß (Art 3) und auf `/ziele` die Notiz des ersten Ziels (Art 2).
  `hauptbuch/` und `ableitung/` sind gleich. Die Ausgabe liegt in
  `notizen/N.3d_referenz_vor_neuschreiben.txt`.
- Die Tests der Paare, Ziele, Bestände, Notizen, Rückkaufswerte, des
  Verlaufs, `test_module`, `test_leck`, `test_namen`, `test_lint` und
  `test_design` sind auf beiden Daten grün.
- Danach habe ich die Referenz neu geschrieben. `pruefen` meldet „Gleich“.

Entscheidungen zu den Abweichungen:
1. **Der tote Zweig in `r/planung.py`:** entfernen, in N.3e. `test_referenz`
   bleibt dabei gleich.
2. **`finctl init` und `balance_snapshots`:** Sonnets Regel gilt. Der
   Schnappschuss des Tages der Datei sind die Positionen mit diesem Datum
   oder ohne eigenes. Das ist gleich für alles, was es gibt. In der
   Entwicklungskopie hat nur ein bekanntes Konto keinen Auszug, und dessen
   Basiswert war leer. Ob ein Stand der Seite unter seinem eigenen Datum in
   die Tabelle gehört, ist eine gewollte Frage. Die Tabelle ist der
   Anfangsstand des Monatsmodells, deshalb steht sie in Schritt 5b, E.0.
3. **404 für eine Position, die es nicht gibt; „zurück“ fällt weg:**
   bestätigt.
4. **Streichen und Löschen nehmen die Notiz mit:** angenommen. Der neue Satz
   bei der Verbindlichkeit bleibt. Bei den Zielen kommt er mit Schritt 6.
5. **Eine ausgeblendete Notiz kommt wieder:** angenommen. Nichts geht
   verloren (Entscheidung 3), und eine Notiz, die wieder dasteht, löscht der
   Haushalt mit einem Klick. N.4 entfernt `ausblenden` und, nach N.3e,
   `basis=`.
6. **Name eines Ziels nur aus der Seite:** angenommen.
7. **`Paar.kontext` braucht `ingest_mode`:** angenommen. N.3e legt
   `accounts` zusammen und muss `_konto_modi` dabei mitnehmen.
8. **Die Kennung einer Verpflichtung folgt dem Namen:** angenommen.
9. **Datum als Text und als Datum:** lassen. Beide Formen lesen sich gleich;
   die Dateiformen räumt Schritt 8 auf.
10. **Umstieg:** Die Punkte stehen in der Liste im Gesamtplan.

**Umgesetzt am 12.10.2026, N.3e (Sonnet): `rules`, `accounts`, `lebensplan` und `backup`.** Geprueft an einer frischen Kopie der Entwicklungskopie im Scratchpad (mit `data/referenz/`, `finance.db` und verknuepften Auszuegen). Keine der vier Seitendateien gibt es in der Entwicklungskopie: `finctl umstellen` sagt dort „Nichts umzustellen“, schreibt weder Sicherung noch Bericht, und die Pruefsumme von `config/`, `data/referenz/`, `notizen/` und `archiv/` bleibt gleich. Die Paare sind deshalb an erfundenen Datenordnern geprueft (`tests/test_umstellen_paare.py`, Abschnitt N.3e); der Bericht eines solchen Laufs liegt als `notizen/N.3e_umstellung_probe_erfundener_ordner.md` in der Entwicklungskopie. Beide Laeufe der Suite (2316 auf der Entwicklungskopie, 2260 auf dem Musterhaushalt) und die Browsertests (49 bestanden, 4 uebersprungen) sind gruen, bis auf `test_referenz`: Die Referenz ist nicht neu geschrieben.

**`rules`.** `finctl/umstellen_paare.py`, `_regeln_legen`:
- *Je Regel* ersetzt die Seite `match` und `set` als Ganzes und jedes andere Feld einzeln (der alte Leser las `{**regel, **seite}`). Ob danach gilt, was galt: `_regeln_alt` ist der alte Leser (`engine.rohe_regeln` mit Seitendatei, nachgebaut), `_regeln_neu` der neue; beide muessen dieselben Regeln liefern, mit `provenance` und ohne Notizen. Der Test laeuft mit eingeschalteter und ausgeschalteter Grundschicht.
- *Eine Regel nur in der Seite* steht danach hinter denen der Basis, ihre Felder in der Reihenfolge der Datei (Kennung, Name, Prioritaet, Bedingung, Aktion).
- *Die Grundschicht* (`finctl/vorgaben/regeln_allgemein.yaml`) bleibt eine Schicht der App und kommt nicht in `rules.yaml`. Zwei Folgen: Eine mitgelieferte Regel, die die Seite geaendert hatte, steht danach als **ganze Regel** in `rules.yaml` (mit der Prioritaet, die galt, und `provenance: allgemein`) und verdeckt die mitgelieferte mit derselben Kennung, so wie eine eigene Regel es immer tat. Eine mitgelieferte Regel, die die Seite ausgeblendet hatte, steht mit ihrer Kennung unter **`allgemeine_regeln_aus`** (neuer Schluessel in `rules.yaml`, hinter `allgemeine_regeln`); `engine.rohe_aus_spec` laesst sie weg. Das gilt auch, wenn die Seite eine Regel der Datei ausblendete, deren Kennung die der mitgelieferten war: Die Regel der Datei faellt weg, die mitgelieferte bleibt ausgeblendet, wie vorher. Ein ersetzter Wert einer mitgelieferten Regel steht als „Bis zur Umstellung stand in den mitgelieferten Regeln: …“ in ihrer Notiz.
- *`entfernt: true`* nimmt eine Regel aus der Datei; ihre Notiz steht mit „Ausgeblendet bis zur Umstellung“ in der Notiz des Bereichs. Ersetzte Werte der Basis (auch `match` und `set`) stehen am Ende der Notiz der Regel, Basis zuerst, dann die Seite.
- *`engine.grundschicht_setzen` und `engine.repoint_rule`* schreiben nur noch `rules.yaml`, beide ueber `dateien.yaml_schreiben` (seit N.2 strukturiert). In `repoint_rule` fiel der Zweig weg, der eine Aktion in `rules_custom.yaml` aenderte. Ein Test belegt, dass beide eine umgestellte Datei samt Notizen und `allgemeine_regeln_aus` lassen.
- *`notizen.setzen(…, basis=…)`* hat keinen Aufrufer mehr (`regelwerk.speichern` war der letzte); das Argument ist noch da, N.4 nimmt es heraus, ebenso `ausblenden`.
- *Fehlt `rules.yaml`,* gilt die Startvorlage als Basis, denn `init` legt sie an.

**`accounts`.** `_konten_legen`:
- *Je Konto* ersetzt die Seite jedes Feld, das sie nennt (der alte Leser nahm **alle** Felder der Seite, nicht nur `konten.FELDER`). Ein Konto nur in der Seite steht hinter denen der Basis, seine Felder in der Reihenfolge von `konten.FELDER`; `entfernt: true` nimmt ein Konto aus der Datei, seine Notiz steht beim Bereich.
- *`konten.FELDER`* bleibt, aber nur als das, was die Seite beim **Anlegen** annimmt (`/api/konto-neu` und `konten.anlegen`). Es schnitt nur dort ab; ein Konto, das es schon gibt, bearbeitet keine Seite. `anlegen` liest die ganze Datei, haengt das Konto an und schreibt sie ueber `dateien.yaml_schreiben`: Notizen und der Block `notizen:` bleiben. `konten.laden(config)` liest nur `accounts.yaml` (`aus_spec`); `EIGEN`, `KOPF` und `BASIS` gibt es nicht mehr (die Datei heisst `konten.DATEI`).
- *`Paar.kontext` (`_konto_modi`)* liest weiter beide Dateien, solange es die Seitendatei gibt: Der Lauf, der `balances` zusammenlegt, legt auch `accounts` zusammen und schreibt erst danach, beim Planen liegen also beide noch, wie sie waren. Nach dem Lauf gibt es nur `accounts.yaml`, und `_konto_modi` liefert dieselbe Menge. Ein Test (`…the_account_modes_the_balances_merge_asks_for_survive_the_merge`) macht es an einem Ordner, in dem die Seite ein Konto mit Auszug zu einem ohne machte und umgekehrt: Der Wert der Seite steht fuer das Konto mit Auszug nur in der Notiz, fuer das andere in der Datei, und vor und nach dem Lauf ist die Menge gleich.
- `module.erststart` fragt nur noch nach `accounts.yaml`.

**`lebensplan`.** `_lebensplan_legen`:
- *Die Namen:* `geburtsdatum` der Seite steht danach als `person.birth_date` (als Datum), `rente_ab_alter` als `schwellen.grv_ab_alter` (als Zahl), `krankenversicherung` gleich als `person.krankenversicherung`. Wie der alte Leser: Ein leerer Wert der Seite (`""`, `null`, `0`) galt nicht und wird nicht uebernommen. Alles andere der Datei bleibt, wie es war (Test an `rest`).
- *Die Notizen* der Seite (Einstellungen: unter `notizen:` mit dem Pfad) ziehen mit um: `person.geburtsdatum` wird `person.birth_date`, `person.rente_ab_alter` wird `schwellen.grv_ab_alter` (`Paar.ort_neu`). Der Wert der Basis, den die Seite ersetzte, steht in der Notiz unter dem Pfad der Datei.
- *Leser:* `person.angaben`, `rentenbeginn`, `geburtstag`, `pkv_sperre` und `pkv_stichtag` lesen nur `lebensplan.yaml` (`aus_spec`); alle Leser der Angaben (Hochrechnung, `/ziele`, `/renten`, `/annahmen`, Auswertung, Einrichtung, Renten) rufen sie auf und lesen keine Datei selbst. Der Test vergleicht den alten und den neuen Leser fuer fuenf Seitendateien (alles, nur eine Angabe, leer, keine).
- Fehlt `lebensplan.yaml`, gilt die Startvorlage als Basis.

**`backup`.** `_backup_legen`:
- Der alte Leser nahm `{**backup.yaml, **backup_custom.yaml:backup}` und las `directory` und `keep`. Beide stehen danach in `backup.yaml`; ersetzte Werte stehen in der Notiz unter dem Schluessel (`notizen: {directory: …}`), andere Schluessel der Seite im Bericht („kein Leser kannte“).
- *`/api/backup/ziel`* schreibt ueber `ops.backup_setzen` die ganze `backup.yaml`, mit dem Block `notizen:`. Ein leerer Wert nimmt die Angabe heraus; derselbe Wert aendert kein Byte, auch wenn die Seite das Ziel ohne `~` zeigt und die Datei mit `~` fuehrt (sonst haette jedes Speichern ohne Aenderung den Pfad ausgeschrieben).
- *`overlays.sicherung`, `sicherung_setzen` und `SICHERUNG_KOPF`* gibt es nicht mehr. *`overlays.anwenden`* spiegelt danach nur noch `settings_custom.yaml` in die Tabelle `settings` (bis N.3f); die Sicherung hat es nie gespiegelt, die Objekte seit N.3c `objekte.in_db`. Von den vier Paaren spiegelt `anwenden` also nichts.

**Zusammenlegen.** Je Paar der Test „liest sich wie beide Dateien“ (`PAAR.alt(basis, seite) == PAAR.neu(neu)`), dazu: Notizen Basis zuerst, ersetzte Werte in der Notiz, ausgeblendete Eintraege beim Bereich, nur Seite (die Seite wird die Datei), nur Basis (nichts zu tun), Kommentare in beiden Dateien, Lauf mit zweitem Lauf, Probe gleich echter Lauf, der Halt der App bei einer stehengebliebenen Seitendatei, Leser und Schreiber lassen eine stehengebliebene Seitendatei unberuehrt. Ein Zusammenleger, der eine Regel-Bedingung, ein Konto, ein Alter oder das Ziel der Sicherung verliert, haelt den ganzen Lauf an: nichts wird geschrieben (Test fuer alle vier). Neu in der Pruefung: `_bereiche_pruefen` stellt fuer **alle** Paare sicher, dass der Text jeder Notiz unter `notizen:` in beiden Dateien in der zusammengelegten steht; ohne sie waere bei `lebensplan` und `backup` (Einstellungen, keine Eintraege) kein Text geprueft worden.

**Leser und Schreiber.** `rules` (`engine.rohe_regeln`, `load_rules`, `regelwerk.laden`, `entwurf`, `speichern`, `entfernen`), `accounts` (`konten`), `lebensplan` (`person`) und `backup` (`ops.backup_settings`, `backup_setzen`) lesen und schreiben nur noch ihre eine Datei. `/regeln` (`regelwerk.speichern`) schreibt den Eintrag der Regel in `rules.yaml`: nur Felder, die sich vom Formular unterscheiden; eine geaenderte mitgelieferte Regel kommt ganz in die Datei; vor dem Schreiben wird das Regelwerk geladen, das danach gilt. `/konten` schreibt keine Konten, das tut `/einrichtung` (`konten.anlegen`, `/api/person`) und `/api/backup/ziel`. Speichern ohne Aenderung aendert kein Byte: Server-Tests je Schreiber (`test_regeln.py`, `test_person.py`, `test_sicherung.py`, `test_konten_anlegen.py`, `test_notizen_eintraege.py`); im Browser deckt `/regeln` der Test `test_speichern_ohne_aenderung_aendert_keine_datei`, `/einrichtung` der neue `test_einrichtung_speichert_sicherungsziel_und_person_ganz_und_ohne_aenderung_nichts`.
- *Weg sind die Anzeigen, die Basis und Seite verglichen:* auf `/regeln` die Pillen „geaendert“ und „eigen“ und die Zeilen „aus config/rules.yaml, hier geaendert“ und „hier angelegt“ im Formular (es bleiben `basis` und `allgemein`); der Fuss von `/regeln`, `/einrichtung` (`/kontenregister`) und `/annahmen` (`/prognosebasis`) nennt je eine Seitendatei weniger (`/regeln` eine, `/annahmen` eine, `/einrichtung` drei). Auf `/system` gibt es keine Seite; `_sicherungsziel.html` verglich nichts. Die Zahl der Regeln auf `/einrichtung` zaehlt jetzt auch, was die Seite angelegt hat.
- Die Konvention `nur-abweichungen-speichern` nennt die vier Dateien als schon eine, `darf_fehlen` der Fusszeilen verliert die vier Namen.

**Notizfelder.** Keine der Seiten hat ein Notizfeld fuer die Notiz eines Eintrags (Schritt 6), und es gibt auf ihnen keine Kuerzung mehr unter `notizen.MAX`: `regelwerk.speichern` reicht die Notiz ohne Kuerzung durch (Test), `konten.anlegen` kennt keine Notiz, Person und Sicherung keine. Die laengste Notiz in den vier Dateien der Entwicklungskopie: die Notiz des Bereichs von `rules.yaml` mit rund 7.200 Zeichen, die einer Regel rund 750, eines Kontos rund 600; `notizen.MAX` ist 20.000.

**Nebenbei (N.3d, Punkt 1).** In `r/planung.py` ist der tote Zweig weg: `goals`, `balances`, die Abfrage des Ueberschusses, `fire` und `fire_rows` samt dem Schluessel `fire` im Kontext, den `planung.html` nie nutzte, dazu der Absatz im Docstring. `planung.txt` der Referenz bleibt gleich; `planung` faellt unter die Schwelle und verlaesst `ZU_VERZWEIGT`.

**Musterhaushalt, `finctl/vorgaben/` und `module.py`.** Der Musterhaushalt hat keine der vier Seitendateien (`rules.yaml`, `accounts.yaml`, `lebensplan.yaml` und `backup.yaml` liegen schon als eine Datei da) und ist unveraendert; `finctl/vorgaben/` ebenso. In `module.py` ist nur `erststart` angepasst (nur `accounts.yaml`). Die Suite auf dem Musterhaushalt ist gruen.

**`pruefen --nur-zahlen` an der Kopie.** 5 Unterschiede, alle auf `seiten/`: `annahmen`, `prognosebasis` (10 zu 9), `einrichtung`, `kontenregister` (9 zu 6) und `regeln` (4 zu 3). `hauptbuch/` (12 Dateien) und `ableitung/` (8 Dateien) sind Byte fuer Byte gleich. Auf jeder Seite ist es **eine** Zahlenzeile, die Zahl im Fuss „Konfiguration — n Dateien“ (Art 3: die Seite nennt weniger Dateien); die Fusszeile zaehlt die genannten Dateien, auch wenn es sie nie gab. Mit Text sind es 10 (dieselben fuenf): im Fuss fallen die Zeilen der Seitendateien weg, und die Beschreibung der einen Datei sagt jetzt beides. Art 1 (Werte der Basis neben dem gueltigen) und Art 2 (Notizen im Text einer Seite) kommen nicht vor, denn die Kopie hatte keine Seitendatei zu diesen vier. Auf der Entwicklungskopie selbst meldet `pruefen` dieselben Unterschiede. Die Textunterschiede liegen in `notizen/N.3e_pruefen_unterschiede.md` der Entwicklungskopie.

**Fuer den Umstieg im echten Datenordner,** vor dem Schreiben mit `--probe` ansehen (`docs`: die Punkte kommen in die Liste im Gesamtplan):
- `rules`: Zeilen „Regel der Grundschicht, geaendert“ (diese Regeln stehen danach als ganze Regel in `rules.yaml`, und Verbesserungen der mitgelieferten Regel kommen dort nicht mehr an), „Regel der Grundschicht, ausgeblendet“ (Kennung unter `allgemeine_regeln_aus`), ausgeblendete Regeln der Datei (fallen weg, Notiz beim Bereich), ersetzte `match` und `set` (alter Wert in der Notiz) und Regeln, die nur die Seite kannte. Ist die Grundschicht ausgeschaltet und die Seite nennt eine Kennung einer mitgelieferten Regel, bleibt es, wie es der alte Leser las: als Regel nur mit den Feldern der Seite.
- `accounts`: ausgeblendete Konten (fallen aus der Datei), Konten nur der Seite, ein Wechsel von `ingest_mode` durch die Seite (er bestimmt, was bei `balances` „kein Leser kannte“ meldet) und Felder der Seite, die `konten.FELDER` nicht kannte (gehen mit).
- `lebensplan`: die Zeilen „Basiswerte, die die Seite ueberschrieben hatte“ fuer `person.birth_date`, `person.krankenversicherung` und `schwellen.grv_ab_alter`; danach muss `/einrichtung` dasselbe zeigen wie vorher („geboren …, Rente mit …“).
- `backup`: `directory` und `keep` in der Notiz, und ob unter „kein Leser kannte“ ein Schluessel steht (`backup.<name>`).
- Fuer alle vier: der Abschnitt „Notizen, die zusammentrafen“ und die Notiz des Bereichs.

**Abgenommen am 25.10.2026 (Opus), Referenz neu geschrieben.**

Nachgeprüft an der Entwicklungskopie:
- `finctl umstellen --probe` meldet „Nichts umzustellen“. Es gibt keine neue
  Sicherung. Übrig sind nur `geteilt_custom.yaml` (bleibt, keine Basis) und
  `settings_custom.yaml` (N.3f).
- `pruefen --nur-zahlen` meldet dieselben fünf Seiten. Jede Zahlenzeile ist
  die Zahl im Fuß (Art 3), der Text ist nur der Fuß. `hauptbuch/` und
  `ableitung/` sind gleich. Die Ausgabe liegt in
  `notizen/N.3e_referenz_vor_neuschreiben.txt`.
- Die Tests der Paare, Regeln, Grundschicht, Person, Sicherung, Konten,
  Notizen, `test_jahre`, `test_module`, `test_leck`, `test_namen`, `test_lint`
  und `test_design` sind auf beiden Daten grün.
- Danach habe ich die Referenz neu geschrieben. `pruefen` meldet „Gleich“.

Entscheidungen zu den Abweichungen:
1. **`allgemeine_regeln_aus`:** bestätigt. Er steht neben dem Schalter
   `allgemeine_regeln`, und kein Leser der Liste `rules` sieht einen Eintrag
   ohne Bedingung.
2. **Eine geänderte mitgelieferte Regel ist eingefroren:** angenommen. Für
   einen Haushalt ist das gleich. Ob sie bei einer Weitergabe nur ihre
   Abweichung tragen soll, steht als offene Frage in
   `docs/Generalization_plan.md`, Phase 4.
3. **Grundschicht aus, Seite kennt eine mitgelieferte Kennung:** gleich ist
   gleich, angenommen. Die Liste für den Umstieg im Gesamtplan nennt den Fall.
4. **Ein leerer Wert nimmt die Angabe heraus:** angenommen.
5. **Sicherungsziel mit `~`:** angenommen.
6. **„Speichern“ der Module auf `/einrichtung` legt `module_custom.yaml` an,
   auch ohne Änderung:** Das ist ein Fehler der Konvention „Speichern ohne
   Änderung ändert nichts“. N.3f behebt ihn nebenbei, auf derselben Seite, und
   nimmt `/einrichtung` dann ganz in den Browsertest auf.
7. **Die Zahl im Fuß zählt die genannten Dateien:** so gewollt.
8. **`test_jahre`:** angenommen.
9. **`darf_fehlen` nennt Seitendateien, die es nicht mehr gibt:** N.3f räumt
   die Liste auf, wenn das letzte Paar zusammengelegt ist.
10. **Für N.4:** angenommen, wie eingetragen.

**Umgesetzt am 25.10.2026, N.3f (Sonnet): `settings`.** Code und Tests an einer frischen Kopie der Entwicklungskopie im Scratchpad (mit `data/referenz/`, `finance.db`, verknuepften Auszuegen), dann die Entwicklungskopie mit `finctl umstellen` umgestellt: ihre `config/` gleicht der Kopie Byte fuer Byte (die Probe auf ihr auch), ein zweiter Lauf meldet „Nichts umzustellen“. Sicherung: `archiv/vor_umstellung_2026-10-25/`, Bericht: `notizen/umstellung_2026-10-25.md`. Beide Laeufe der Suite (2348 auf der Entwicklungskopie, 2294 auf dem Musterhaushalt) und die Browsertests (52 bestanden, 4 uebersprungen) sind gruen, bis auf `test_referenz`: Die Referenz ist nicht neu geschrieben. **Ablauf-Abweichung:** Die Entwicklungskopie war umgestellt, bevor der Abgleich der Tabelle (unten) im Code stand; er stand erst danach. Nachgeprueft an der Sicherung und der unveraenderten `finance.db`: Tabelle und Datei stimmten ueberein (vier Untergrenzen, gleiche Werte, keine Notiz, nichts nur in der Tabelle).

**Ein Paar mit zwei Basisdateien.** `settings_custom.yaml` hatte zwei Basen: Die zwoelf Stellschrauben ueberschrieben `assumptions.yaml`, `floor_cents:<konto>` die Konto-Regeln in `forecast.yaml`. `PAARE` hat deshalb zwei Eintraege mit derselben Seitendatei; `Paar.ansicht` gibt jedem Paar seinen Teil der Seite (Werte und Notizen, jede Stelle genau einem). `Umwandlung.zusammengelegt` ist eine Liste, und `Umwandlung.seitentext` haelt die Seite, wie sie ins erste Paar einging.
- *Stellschrauben.* Jeder Wert geht an den Pfad aus `UEBERSCHREIBBAR`; die Seite gewinnt, auch mit einem leeren Wert (so las es `load`). `teilzeit_anteil` und `teilzeit_ab` standen in der Basis nicht und stehen danach unter `erwerbseinkommen`, hinter den vorhandenen Schluesseln; fehlt der Abschnitt, wird er angelegt. Ein ersetzter Basiswert steht in der Notiz unter dem Pfad der Datei („Bis zur Umstellung stand in der Datei: …“). Eine Notiz an einer Einstellung geht unter ihren Pfad, die Notiz des Bereichs zu `assumptions.yaml`, ein Schluessel, den kein Leser kannte, in den Bericht.
- *Untergrenzen.* Je Konto `account_roles.<konto>.floor_cents`, die Seite gewinnt wie vorher. Das Paar steht in `PAARE` **hinter** dem mit `forecast_custom.yaml`: Der alte Leser nahm Einstellungen vor der Seite der Konten vor der Basis, und die Reihenfolge der Zusammenleger bringt denselben Wert. Ein Test legt `forecast.yaml`, `forecast_custom.yaml` und `settings_custom.yaml` in einen Lauf; beide ersetzten Werte stehen in der Notiz. Ein Konto, das `forecast.yaml` nicht kennt, bekommt eine Regel nur mit `floor_cents` (Bericht: „Konto, neu“), auch eines, das `accounts.yaml` nicht kennt (nichts geht verloren). Ein Wert, den `_floor_for` nicht als ganze Zahl las, galt nie und steht im Bericht. `floor_from_loan` bleibt vorn, die Untergrenze daneben.
- *Gilt genau, was galt.* `alt` (`assumptions.load` mit dem Overlay, die Konto-Regeln mit den Untergrenzen darueber) gegen `neu`; Tests „liest sich wie beide Dateien“ fuer beide, und je ein Zusammenleger, der einen Wert, eine Untergrenze oder eine Notiz verliert (schreibt nichts).
- *Auf der Entwicklungskopie:* `assumptions.yaml` 0 ueberschriebene Basiswerte, 0 zusammentreffende Notizen, zwei Angaben nur aus der Seite (Teilzeit); `forecast.yaml` 1 ueberschriebener Basiswert (die Untergrenze des Kontos mit der Rolle consumption, in der Notiz der Konto-Regel), 0 Notizen. Kein `forecast_custom.yaml`.
- *Szenarien.* `assumptions.optimistisch.yaml` und `assumptions.pessimistisch.yaml` bekamen nie ein Overlay und erben nichts (`load` eines anderen Pfads gibt die Datei). Belege: Test (gleiche Werte vor und nach dem Lauf, Datei Byte fuer Byte) und `finctl jahre` mit beiden Szenarien: dasselbe JSON mit altem Code auf der alten Config und neuem Code auf der umgestellten.

**Tabelle `settings`.** Der einzige Leser war `_floor_for`; `web/basis.setting()` hatte keinen Aufrufer und ist entfernt. `finctl init` schreibt nichts mehr hinein (`overlays.anwenden` ist weg), die leere Tabelle bleibt im Schema bis N.4. Alte Zeilen in einer `finance.db` bleiben stehen und werden nicht gelesen. `hauptbuch/settings.json` verliert damit sechs Zeilen: vier `floor_cents:<konto>`, `teilzeit_ab`, `teilzeit_anteil`. Das ist die vierte erlaubte Art in der Fertig-wenn-Zeile von N.3 (Opus, 25.10.2026).
- *Abgleich vor dem Lauf* (`umstellen.tabelle_gegen_datei`, in `planen`, also bei `finctl umstellen`, `--probe` und beim Halt der App): Gibt es `settings_custom.yaml` und eine `finance.db`, vergleicht der Lauf die Tabelle mit der Datei. Eine Zeile nur in der Tabelle, ein anderer Wert oder eine Notiz in der Tabelle: Der Lauf haelt an, schreibt nichts und nennt die Zeilen. Eine Zeile nur in der Datei ist kein Fund. Ohne `finance.db`, ohne die Tabelle oder ohne Seitendatei entfaellt er. Gelesen wird eine Kopie der Datenbank (im WAL-Betrieb legt schon das Lesen `-shm` und `-wal` an). Tests an erfundenen Ordnern: gleich geht durch, Zeile nur in der Tabelle, anderer Wert, Notiz, `--probe`, und die Faelle ohne Vergleich.

**Leser und Schreiber.** `assumptions.load` liest die Datei; `basiswert` und `vorgabe` sind `in_datei` und `wert`; `assumptions.setzen` schreibt die ganze Datei ueber `dateien.yaml_schreiben` (Notizen bleiben; derselbe Wert, auch der Wert im Code, den die Seite zeigt, aendert kein Byte). `/api/setting` ruft es; ein leeres Feld nimmt die Angabe heraus, wo die Rechnung ohne sie auskommt (`assumptions.OPTIONAL`: Teilzeit, Kostenschwelle, Sparerpauschbetrag), sonst 400; ein unbekannter Schluessel ebenso (vorher nahm die Seite jeden). `/api/floor` und `/api/konto` schreiben die Untergrenze mit der Regel ueber `kontenregeln.setzen`; die Karte auf `/konten` schickt die Untergrenze, die sie zeigt, und zeigt sie nur die Schwelle des Kontos, wird nichts eingetragen.
- *Weg:* auf `/annahmen` (und `/prognosebasis`, dieselbe Tabelle) „ueberschrieben“, „dokumentiert: …“ und „zurueck“ (in der Kopie an den zwei Teilzeit-Zeilen); die Zeile `settings_custom.yaml` im Fuss von `/annahmen`, `/konten` und `/planung`. Auf `/konten` gab es keine Herkunft zu zeigen.
- *Speichern ohne Aenderung:* Server-Tests je Schreiber; im Browser `/annahmen` und neu `/einrichtung` in `SEITEN`, dazu ein Test, der auf `/konten` die Karte je einer Art von Konto speichert (mit Untergrenze, mit Rate als Untergrenze, ohne Regel, ohne Untergrenze).
- `module.setzen` (Module auf `/einrichtung`) schreibt nur, wenn die Auswahl von dem abweicht, was gilt; vorher legte jedes Speichern `module_custom.yaml` an (N.3e, Abnahme Punkt 6).

**Nebenbei.** `overlays.py` bleibt mit `lesen`, `schreiben` und `CONFIG_DIR`; `module.py`, `zinssaetze.py` und `forecast/prognosebasis.py` brauchen sie (Dateien ohne Basis). `darf_fehlen` in `docs/design_conventions.yaml` nennt nur noch Dateien, die es ohne Seitendatei geben darf (ein Test haelt Seitendateien der Paare heraus); `nur-abweichungen-speichern` sagt: Die Seite schreibt die ganze Datei, Speichern ohne Aenderung aendert kein Byte. Musterhaushalt: `settings_custom.yaml` ist weg, die zwei Teilzeit-Werte stehen in `assumptions.yaml` (gleiche Daten wie der Lauf des Umwandlers auf den alten Dateien); `finctl/vorgaben/` unveraendert, `module.py` nennt `settings_custom.yaml` nicht.

**`pruefen --nur-zahlen` an der umgewandelten Kopie.** 5 Unterschiede: `hauptbuch/settings.json` (Art 4) und auf `seiten/` `annahmen`, `prognosebasis`, `planung`, `konten`. `hauptbuch/` (11 von 12) und `ableitung/` (8) sind Byte fuer Byte gleich. Auf `annahmen`, `prognosebasis` und `planung` ist die Zahlenzeile die Zahl im Fuss (Art 3); auf `konten` der Fuss (Art 3) und eine Zeile, die „5000“ aus „Bis zur Umstellung stand in der Datei: `floor_cents`: 5000.“ in der Notiz der Konto-Regel (Art 2). Text: die Pillen und „zurueck“ der Teilzeit-Zeilen (Art 1), der Fuss. Die Textunterschiede liegen in `notizen/N.3f_pruefen_unterschiede.md` der Entwicklungskopie. Auf der Kopie im Scratchpad dieselben fuenf.

**Fuer den Umstieg im echten Datenordner,** vor dem Schreiben mit `--probe` ansehen: der Abgleich der Tabelle (haelt der Lauf an, steht die Zeile im Fehler; so eine Untergrenze oder Notiz steht nur in der Datenbank und muss vorher in die Datei); in beiden Abschnitten „Zusammengelegt: `settings_custom.yaml` in …“ die Basiswerte, die die Seite ueberschrieben hatte, „Was die Seite brachte“ (Teilzeit, Konten neu) und „Felder, die kein Leser kannte“ (unbekannte Schluessel, Untergrenzen ohne ganze Zahl); liegt zugleich ein `forecast_custom.yaml` da, stehen beide Paare fuer `forecast.yaml` im Bericht und beide ersetzten Werte in der Notiz; und ob eine Untergrenze zu einem Konto gehoert, das `accounts.yaml` nicht kennt.

**Abgenommen am 25.10.2026 (Opus), Referenz neu geschrieben.**

Nachgeprüft an der Entwicklungskopie:
- Ein zweiter Lauf meldet „Nichts umzustellen“. Von den Seitendateien ist nur
  `geteilt_custom.yaml` übrig, die keine Basis hat.
- Gegen die Sicherung gelesen: Jede der vier Untergrenzen steht danach mit dem
  Wert der Seite an der Konto-Regel. Bei drei Konten war er dort schon gleich,
  bei einem steht der ersetzte Wert in der Notiz. Die Teilzeit steht unter
  `erwerbseinkommen`. Die Szenariodateien sind Byte für Byte gleich, und
  `floor_from_loan` trägt weiter die Kennung des Kredits.
- Die Tabelle `settings` der `finance.db` hatte vor der Umstellung dieselben
  vier Untergrenzen wie die Datei, ohne Notiz (vor der Bedingung an Sonnet
  gesehen). Dass Sonnet vor dieser Bedingung umgestellt hat, hat also nichts
  gekostet.
- `pruefen` meldet `hauptbuch/settings.json` (die sechs Zeilen, Art 4), auf vier
  Seiten den Fuß (Art 3), auf `/konten` die Notiz mit dem alten Wert (Art 2) und
  auf `/annahmen` und `/prognosebasis` im Text „überschrieben“, „dokumentiert“
  und „zurück“ (Art 1). Die Ausgabe liegt in
  `notizen/N.3f_referenz_vor_neuschreiben.txt`.
- Die Tests der Paare, des Umstellens, der Annahmen, der Notizen, der Prognose,
  `test_module`, `test_design`, `test_leck`, `test_namen` und `test_lint` sind
  auf beiden Daten grün. Die Tabelle `settings` liest nur noch der Abgleich in
  `umstellen.py`.
- Danach habe ich die Referenz neu geschrieben. `pruefen` meldet „Gleich“.

Entscheidungen:
- **Art 4, Zeilen der Tabelle `settings`:** erlaubt, nur für N.3f (Opus,
  25.10.2026, auf Sonnets Halt).
- **Abgleich von Tabelle und Datei vor jedem Lauf:** so gewollt. Er steht in
  der Liste für den Umstieg im Gesamtplan.
- **Der Fehler mit `floor_from_loan`:** angenommen, mit Test. Der Haushalt
  prüft beim Umstieg, ob jedes `floor_from_loan` eine Kennung trägt; das steht
  in der Liste.
- **Ein Haken ohne Kredit schreibt `true`:** Schritt 6. Die Kontokarte bietet
  dann die Kredite zur Auswahl an. Bis dahin bleibt es, wie es ist.
- **Die Tabelle `settings` selbst:** Sie bleibt im Schema, und der Abgleich
  bleibt in `umstellen.py`, bis der Umstieg im echten Ordner geschehen ist.
  Der Abgleich braucht beides. Danach räumt Schritt 8 beides weg.

### N.4 Den Umstieg proben (gleich)

- Eine frische Kopie aus `sicherung_vor_schritt5/` wird mit einem einzigen
  `finctl umstellen` umgewandelt. Das Ergebnis gleicht der schrittweise
  umgestellten Entwicklungskopie Datei für Datei.
- `pruefen` meldet auf dieser Kopie „Gleich“.
- Ein zweiter Lauf ändert nichts.
- `--probe` lässt den Datenordner unberührt (Prüfsumme vorher und nachher).
- `overlays.py` und alles, was nur dem Zusammenlegen diente, ist entfernt.
  Die alten Leser leben nur noch in `finctl/umstellen.py`.
- Handbuch und `CHANGELOG.md` nennen, was der Haushalt beim Umstieg tut.

**Fertig wenn:** Alles oben gilt, und beide Läufe der Suite und die
Browsertests sind grün.

**Aufteilung (Opus, 25.10.2026).** Vier Aufträge, nacheinander, jeder mit
eigener Abnahme:

| Teil | Inhalt | Modell |
|---|---|---|
| N.4a | `notizen.setzen` ohne `ausblenden` und `basis` (keine Aufrufer mehr, N.3d Punkt 5, N.3e Punkt 10) | Haiku |
| N.4b | Aufräumen: `overlays.py` weg; was nur dem Zusammenlegen diente, lebt nur noch in `umstellen.py` und `umstellen_paare.py` | Sonnet |
| N.4c | Die Probe: frische Kopie aus `sicherung_vor_schritt5/`, ein Lauf, Vergleich mit der Entwicklungskopie | Sonnet |
| N.4d | Handbuch und `CHANGELOG.md`: was der Haushalt beim Umstieg tut | Sonnet |

**Umgesetzt am 25.10.2026, N.4a (Haiku).** Weg sind die Parameter `basis` und `ausblenden` von `notizen.setzen` samt dem Code, der sie nutzte, und die zwei Tests, die nur sie prüften; keiner der übrigen Aufrufer übergab sie. Ganze Suite auf der Entwicklungskopie: 2347 bestanden, 47 übersprungen; auf dem Musterhaushalt: 2292 bestanden, 60 übersprungen.

**N.4a abgenommen am 25.10.2026 (Opus).** Diff gelesen: nur die zwei Parameter, ihr Zweig und die zwei Tests. Die schnelle Suite ist grün, und `pruefen` meldet „Gleich“.

Die Tabelle `settings` und der Abgleich bleiben (Abnahme N.3f).

**Umgesetzt am 25.10.2026, N.4b (Sonnet).** Beide Laeufe der Suite (2359 bestanden, 47 uebersprungen auf der Entwicklungskopie; 2304 und 60 auf dem Musterhaushalt) und die Browsertests (52 bestanden, 4 uebersprungen) sind gruen, `ruff` meldet nichts. `tests/referenz.py pruefen` meldet auf der Entwicklungskopie „Gleich“, ohne `--nur-zahlen`; die Referenz ist nicht neu geschrieben. Am Umwandler (`umstellen*.py`) und an seinen Tests (`tests/test_umstellen*.py`) hat sich nichts geaendert, bis auf einen Importpfad in `test_umstellen_paare.py`.

**Weg.**
- *`overlays.py`.* `lesen` und `schreiben` heissen jetzt `dateien.zuordnung_lesen(pfad, schluessel)` und `dateien.zuordnung_schreiben(pfad, schluessel, daten, kopf)` und nehmen den Pfad der Datei. `module.py`, `zinssaetze.py` und `forecast/prognosebasis.py` halten ihr `CONFIG_DIR` selbst (aus `pfade.py`), wie jedes andere Modul; die Tests biegen es am benutzenden Modul um (`module.CONFIG_DIR` statt `overlays.CONFIG_DIR`). `tests/test_pfade.py` fuehrt die drei Module statt `overlays`. `speichern ohne Aenderung` ist gleich: Der Code der beiden Funktionen ist derselbe.
- *`notizen.lesen`* liest nur noch einen Eintrag (`lesen(eintrag, alt=())`). Kein Aufrufer hatte mehr als eine Schicht uebergeben, auch der Umwandler nicht; `_schicht` ist darin aufgegangen. Zwei Tests, die nur die Schichten pruefen, sind durch einen ersetzt (leerer Text, Feld ohne Wert und alter Name).
- *`renten.BASIS`* heisst `renten.DATEI` wie die Konstante der uebrigen Module.
- *Docstrings und Kommentare,* die eine `_custom`-Datei oder „Overlay“ als heutigen Ort nannten, sagen jetzt „eine zweite Datei“ oder nennen die Datei, die gilt (`konten`, `person`, `kontenregeln`, `abos`, `renten`, `assumptions`, `forecast/konten`, `web/routen/konten`, `tax/taxonomy`, `rules/regelwerk`, `forecast/szenarien`, `bestaende`, `forecast/jahre`, `forecast/ziele`, `cli`, Kommentar in `ziele.html`). Der Docstring von `/api/objekt-entfernen` sagte, die Basisdatei bleibe unangetastet; er sagt jetzt, was der Weg tut (Eintrag samt Notiz aus `properties.yaml`).
- Nach `umstellen_paare.py` musste nichts umziehen: Ausser `notizen.lesen` kannte kein Leser ausserhalb der `umstellen*`-Module zwei Dateien. Gesucht habe ich mit einem Skript im Scratchpad: jeder Name auf oberster Ebene und jede Methode ausserhalb der `umstellen*`-Module, dessen einzige Aufrufer im Umwandler stehen. Treffer: nur `notizen.BEREICH` und `notizen.bereiche` (siehe unten).

**Die `_custom`-Namen im Code** stehen nur noch in den `umstellen*`-Modulen und bei diesen sechs Dateien, die keine Basis haben (Entscheidung 5), geprueft an Code, `finctl/vorgaben/`, Musterhaushalt und `PAARE`: `geteilt_custom` (Projekte, Personen, geteilte Buchungen), `reihen_custom` (Takt und Schreibweisen der Reihen), `zinssaetze_custom` (datierte Zinssaetze), `prognosebasis_custom` (abgewaehlte Kategorien), `module_custom` (Schalter der Module), `csv_profile_custom` (selbst zugeordnete CSV-Exporte). Vorher nannten 26 Module einen solchen Namen; jetzt tun es 19 Dateien unter `finctl/` (Module, Vorlagen, Schema), alle mit einem dieser sechs Namen, dazu `HANDBUCH.md` (N.4d). **Test:** `tests/test_dateinamen.py` haelt das fest. `OHNE_BASIS` ist die Liste der sechs und darf nur kuerzer werden: Ein anderer `_custom`-Name im Code faellt auf, ein Name der Liste, der nirgends mehr steht, auch. Je Datei prueft er, dass es keine Basisdatei im Code, in den Startvorlagen oder im Musterhaushalt gibt und dass die Datei kein Paar in `PAARE` ist.

**Bewusst gelassen.**
- Die Tabelle `settings` im Schema und `umstellen.tabelle_gegen_datei`, `halt_wenn_offen`, `--probe` (Abnahme N.3f und Auftrag).
- `notizen.bereiche` und `notizen.BEREICH` rufen nur der Umwandler und Tests; sie sind aber der Leser des neuen Formats, den Schritt 6 fuer die Anzeige braucht. `notizen.bereich_setzen` hat gar keinen Aufrufer ausser Tests, ebenfalls fuer Schritt 6.
- `NOTIZ_ALT` (`note`) in `bestaende.py` und die `alt=`-Namen der Leser: Sie benennen das Feld, das die Seite schickt und liest, nicht eine alte Datei.
- Die vierte Datei `umstellen_lagen.py` zaehle ich zu den `umstellen*`-Modulen; der Test nimmt alle vier aus.
- `HANDBUCH.md` und `CHANGELOG.md` (N.4d). Das Handbuch nennt `*_custom.yaml` als Glob und die sechs Dateien.

**N.4b abgenommen am 25.10.2026 (Opus).** `overlays.py` ist weg, `pruefen` meldet „Gleich“ ohne `--nur-zahlen`, und die schnelle Suite ist grün. `tests/test_dateinamen.py` hält die sechs Dateien ohne Basis fest; die Liste darf nur kürzer werden. Zu den Abweichungen:
1. Die Löschung von `overlays.py` ging in meinen Commit `8731ce0` mit: Ich hatte `git add` und dann `git commit` ohne Pfade benutzt. Ab jetzt committe ich nur mit ausdrücklichen Pfaden.
2. Vier `umstellen*`-Module: angenommen.
3. `notizen.bereiche`, `BEREICH` und `bereich_setzen` bleiben für Schritt 6, der die Notizen zeigt.
4. `module.erststart` prüft einen Ordner und schreibt in einen anderen: gleich gelassen; Schritt 8 räumt das auf.

**Erlaubnis für N.4c (Haushalt, 25.10.2026):** Die Probe darf zusätzlich an einer Kopie des echten Datenordners laufen. Die Kopie liegt im Scratchpad, der Ordner selbst wird nur einmal zum Kopieren gelesen (Prüfsumme vorher und nachher). Echte Werte stehen nur in `notizen/` der Entwicklungskopie.

**Umgesetzt am 25.10.2026, N.4c (Sonnet).** Nur gelesen und geprobt: kein Code, kein Test, keine Referenz und kein anderes Dokument geändert. Jeder Aufruf lief mit `FINCTL_DATEN` auf eine Kopie im Scratchpad. Die Befunde mit echten Werten stehen in `notizen/N.4c_probe_echter_ordner.md` der Entwicklungskopie.

**Teil A, Probe an der Sicherung.** Frische Kopie: `config/` aus `sicherung_vor_schritt5/`, `data/` aus der Entwicklungskopie.
- Ein Lauf `finctl umstellen`: 22 Dateien umgewandelt, 11 Paare zusammengelegt. `config/` gleicht der schrittweise umgestellten Entwicklungskopie **Byte für Byte** (`diff -r`: 26 Dateien, kein Unterschied).
- `tests/referenz.py pruefen` auf dieser Kopie: „Gleich“, ohne `--nur-zahlen`.
- Zweiter Lauf: „Nichts umzustellen“, Prüfsumme über `config/`, `data/`, `archiv/` und `notizen/` unverändert.
- `--probe`: Prüfsumme über dieselben vier Ordner vorher und nachher gleich, an einer frischen, noch nicht umgestellten Kopie. Die Probe-Kopie in `config/` gleicht der Entwicklungskopie ebenfalls Byte für Byte.

**Teil B, Probe an einer Kopie des echten Ordners.** Prüfsumme (SHA-1 über die Einzelsummen, ohne `.DS_Store`) vor und nach dem Kopieren gleich, für `config/` (f7fca9c87a92…), `data/` ohne `statements/` (613bd97a4031…), `data/statements/` (e4138148dda0…) und `notizen/` (bf3d2faaa7df…). Danach wurde der echte Ordner nicht mehr gelesen. Kopiert wurden `config/`, `data/depots`, `data/statements`, `finance.db` (es gab weder `-wal` noch `-shm`) und `notizen/`, ohne `data/referenz*`; `tests/referenz.py` lief an dieser Kopie deshalb nicht.
- **Umstellen.** `--probe` ließ den Ordner unberührt (Prüfsumme vorher und nachher gleich); dann ein Lauf, dann „Nichts umzustellen“. Dieselben 22 Dateien und elf Paare wie in der Entwicklungskopie. Die Probe-Kopie gleicht dem Ergebnis bis auf eine leere Sperrdatei (siehe unten).
- **`init`, Befehle, `validate`.** `finctl update` gibt es nicht. Ich ließ die Folge laufen, die das Handbuch nennt: `init`, `ingest run`, `categorize`, `validate`. Alle vier liefen ohne Fehler, `validate` meldet „All invariants hold.“, `ingest run` fand nichts Neues, `categorize` wendete die Handentscheidungen wieder an. Transaktionen, Kredite, Objekte und die Tabelle `settings` sind danach gleich; `rules` und `splits` unterscheiden sich nur in Kennungen und Zeitstempeln (Abweichung 3).
- **Nachführen aus 4.6.** Läuft beim ersten Befehl: Meldung „Nachgefuehrt: config/taxonomy.yaml: immobilie/kaufnebenkosten traegt jetzt `einmalig: true`“, in `taxonomy.yaml` ändert sich genau diese eine Zeile, in der Datenbank hat danach genau diese Kategorie das Merkmal. Die Spalte `einmalig` stand in der Datenbank des echten Ordners schon (Abweichung 1); in einer Wegwerfkopie ohne die Spalte legte der Start der App sie an. Die App hielt dabei nicht an.
- **Die App vor dem Umstellen.** Sie hält an, nennt `finctl umstellen --probe` und `finctl umstellen`, und `config/` bleibt unberührt; `finctl init` hält ebenso an.
- **Seiten.** Alle 42 Seiten, die `tests/referenz.py` kennt (38 feste und vier Objektseiten), antworten mit 200: nach `init` und noch einmal in der Wegwerfkopie, wo der Start der App der erste Befehl nach dem Umstellen war.
- **Die Liste aus dem Gesamtplan, an dieser Kopie.**
  - *Ausgeblendete Einträge:* Eine einzige gestrichene Verpflichtung (`geloescht: true` in `balances_custom.yaml`). Sie fällt aus der Datei, die Notiz steht beim Bereich. Kein Abo, keine Versicherung, kein Kredit, kein Objekt, kein Ziel, keine Regel, kein Konto ist ausgeblendet.
  - *„kein Leser kannte“:* leer. Der Bericht hat den Abschnitt nicht; auch „Konto mit Auszug: galt nicht“ kommt nicht vor.
  - *Tabelle `settings`:* drei Zeilen, alle mit demselben Wert in `settings_custom.yaml`; `tabelle_gegen_datei` meldet nichts, der Lauf hält nicht an. Das Konto mit dem überschriebenen Mindeststand trägt danach den Wert der Seite, der Basiswert steht in der Notiz.
  - *`floor_from_loan`:* ein einziges, und es trägt die Kennung eines Kredits, der in `loans.yaml` steht. Kein `true`.
  - *`szenarien.yaml`:* sieben Klammern, eine Zeile ohne `start` (die Klammer „Teilzeit“, die erlaubte Ausnahme).
  - *Die vier Seitendateien aus N.3e* (Regeln, Konten, Lebensplan, Sicherung) gibt es im echten Ordner nicht; dort ist nichts zu prüfen.

**Was der Haushalt vor oder beim Umstieg tun muss, das noch nicht in der Liste steht.**
- Nach dem Umstellen als Erstes `finctl init`, dann `finctl ingest run`, `finctl categorize`, `finctl validate`. Ein Befehl `update` existiert nicht; das Handbuch (N.4d) soll diese Folge nennen.
- Die eine gestrichene Verpflichtung bestätigen: Sie steht danach nur noch in der Sicherung und in der Notiz des Bereichs.
- Wissen, dass `taxonomy.yaml` beim ersten Befehl eine Zeile bekommt (das Merkmal `einmalig`), und dass `init` die Datenbank dort angleicht, wo sie älter ist als die Dateien (Abweichung 3).

**N.4c abgenommen am 25.10.2026 (Opus).** Teil A habe ich selbst wiederholt: Aus einer frischen Kopie von `sicherung_vor_schritt5/config` ergibt ein einziger `finctl umstellen` Byte für Byte dieselbe `config/` wie die schrittweise umgestellte Entwicklungskopie (`diff -rq`). Teil B deckt sich mit meiner eigenen Probe am echten Ordner vom selben Tag (`notizen/probe_echter_ordner_2026-10-25.md`): dieselben Paare, dieselbe gestrichene Verpflichtung, nichts unter „kein Leser kannte“. Zu den Abweichungen:
1. Die Spalte `einmalig` gibt es im echten Hauptbuch schon: Der Abschnitt „Umstieg“ im Gesamtplan ist berichtigt.
2. Kein `finctl update`: N.4d nennt die Folge `init`, `ingest run`, `categorize`, `validate`.
3. Ältere Profilnamen in der Tabelle `accounts`: `init` gleicht sie an, das gehört nicht zum Umstieg. Lassen.
4. `overrides.yaml.lock` bleibt im Ordner: harmlos. Lassen.
5. `--probe` an einem umgestellten Ordner schreibt trotzdem Kopie und Bericht: unschön, aber harmlos. Schritt 8 räumt auf.
6. Der Änderungstag von `data/` im echten Ordner (12:24) liegt vor meiner Probe (14:06). Er kommt nicht von einer der Proben, denn beide haben die Datenbank nur in einem Ordner außerhalb gelesen (`tabelle_gegen_datei` kopiert in ein temporäres Verzeichnis). Wahrscheinlich hat ihn die App von `basis` gesetzt, mit der der Haushalt im Alltag arbeitet.

**Umgesetzt am 25.10.2026, N.4d (Sonnet).** Geändert sind nur `HANDBUCH.md`, `finctl/HANDBUCH.md` (byteweise gleich), `CHANGELOG.md` und dieses Dokument; kein Code, kein Test, keine Referenz, kein Tag. Beide Läufe der Suite sind grün (2359 bestanden, 47 übersprungen auf der Entwicklungskopie, 2304 bestanden, 60 übersprungen auf dem Musterhaushalt), darin `test_leck`, `test_namen`, `test_design`, `test_paket` und `test_dateinamen`. Zum Prüfen habe ich `finctl umstellen --probe` an einer Kopie von `sicherung_vor_schritt5/config` im Scratchpad laufen lassen (nur zum Lesen des Berichts und der Terminalausgabe) und an einer Kopie der Entwicklungskopie mit neuen `#`-Kommentaren in verschiedenen Dateien `umstellen.halt_wenn_offen` aufgerufen.

**Handbuch, Abschnitt 2b „Umstieg auf Notizen“** (neu, nach den Startdateien), in der Reihenfolge der Liste im Gesamtplan, allgemein formuliert und ohne die Befunde des echten Ordners:
- *Wann:* nach einem Monatsabschluss; die App hält an, bis umgestellt ist; der Umstieg ändert keine Zahl.
- *Ein paar Tage vorher:* `finctl umstellen --probe <ordner>`; was es schreibt (Kopie von `config/`, Bericht); die vier Stellen im Bericht: „Ausgeblendet gewesen“, „… die kein Leser je las“, „Basiswerte, die die Seite …“, „Notizen, die zusammentrafen“; dazu „Was die Seite brachte“ und „Weggefallen“.
- *Was jeder Haushalt vorher prüft:* `szenarien.yaml` (Zeile ohne `start`), `floor_from_loan` mit Kennung, Kredite und Anschlusskonditionen, Regeln (vier Fälle aus N.3e), Konten, Lebensplan und Sicherung, Stände zu Konten mit Auszug.
- *Wenn der Abgleich der Tabelle `settings` anhält:* was er vergleicht, was der Lauf dann tut (nichts umwandeln, jede Zeile nennen, Fehler; die App hält ebenfalls), und was der Haushalt tut (übernehmen und aus der Tabelle löschen).
- *Am Tag selbst:* Datenordner kopieren (Sicherung und Stand für die ältere Fassung), `finctl umstellen`, dann `init`, `ingest run`, `categorize`, `validate`; kein `update`; Seiten durchsehen.
- *Was beim ersten Befehl nachgeführt wird:* die Spalte `einmalig`, die Zeile in `taxonomy.yaml`, das Neuladen der Kategorien; danach `/reihen` durchsehen.
- Die Anleitung ist Fließtext mit je einem Codeblock auf oberster Ebene, nicht als verschachtelte Liste: Der Handbuch-Leser der App (`finctl/web/handbuch.py`) kennt keinen Codeblock in einer Listenzeile und zeigte ihn mit „``“ im Text.

**Handbuch, Abschnitt 2 „Wo was geändert wird“.**
- Tabelle gegen `config/` der Entwicklungskopie und die Seiten geprüft. Weg sind `planned.yaml` (am 13.09.2026 entfallen) und `scenarios.yaml` (gibt es nicht; die Alternativen sind `assumptions.optimistisch.yaml` und `assumptions.pessimistisch.yaml`, `finctl jahre --szenario`). Neu in der Tabelle: `abos.yaml`, `versicherungen.yaml`, `balances.yaml`, `renten.yaml`, `lebensplan.yaml`, `backup.yaml`, `strom.yaml`, `energie.yaml`, `groups.yaml`, `server.yaml`; `forecast.yaml` ist nicht mehr „nein“, denn die Konto-Regel schreibt `/konten`.
- Die sechs Dateien ohne Basis stehen darunter mit ihrem Zweck, geprüft an `OHNE_BASIS` in `tests/test_dateinamen.py`. Andere `_custom`-Namen stehen nirgends im Handbuch (der Test liest `finctl/HANDBUCH.md` mit).
- Ausdrücklich: Wer eine Datei von Hand ändert, schreibt das Warum in `notiz`, nicht als `#`-Kommentar. Geprüft an `umstellen.halt_wenn_offen`: Ein neuer Kommentar hält die App an (Start, `finctl init`, Befehle mit Hauptbuch), und zwar in jeder Datei von `config/` außer `server.yaml`, `verbotene_namen.yaml`, `taxonomy_migrations.yaml` und `accounts.example.yaml` (`OHNE_SEITE`); den Kopf, den die App selbst schreibt, zählt der Lauf nicht. Ich habe es an Kopien von `goals`, `loans`, `rules`, `strom` (hält an) und den vier Ausnahmen (hält nicht an) gelaufen.

**Handbuch, sonst berichtigt.**
- „Ein Policenwert steht in `lebensplan.yaml`“ stimmte nie: Er steht in `balances.yaml`. „Herleitung“ ist jetzt „Notiz“.
- Das Szenario nennt jetzt die Datei und den Befehl.
- *Abschnitt 7:* zwei Zeilen: die App hält an („… ist noch nicht umgestellt“), und der Abgleich von `settings` hält den Lauf an.
- */annahmen:* „ein leeres Feld nimmt die Angabe heraus“ war nur halb richtig: Bei einer Stellschraube ohne Vorgabewert der App (und ohne Teilzeit) lehnt die Seite ein leeres Feld ab (`assumptions.setzen`, `OPTIONAL`). Damit der Abschnitt unter 200 Wörtern bleibt (`test_a_handbook_section_stays_shorter_…`), fielen „etwa ein Aktionszins“ und der Satz „Gespeichert in `config/zinssaetze_custom.yaml`“ weg; die Datei steht jetzt in Abschnitt 2.
- */monatsabschluss:* Streichen einer Verbindlichkeit nimmt die Notiz mit (die Rückfrage der Seite sagt es).
- */vertraege:* „Löschen“ nimmt den Vertrag samt Notiz aus der Datei.
- */kredite, /ziele, /renten, /regeln, /immobilien:* geprüft, nichts zu berichtigen.
- Knöpfe und Pillen: Im Handbuch stand keiner der in Schritt 5 gefallenen („zurück“, „eigen“, „überschrieben“, „dokumentiert“, „angelegt“, „Ausblenden“, Herkunft); die Abschnitte waren in N.3 schon nachgezogen. Gefunden habe ich die Liste mit `git diff 871640c HEAD -- finctl/web/templates`; sie steht im CHANGELOG.

**CHANGELOG, unter „Unveröffentlicht“.**
- *Neu, in Worten des Haushalts:* „Begründungen stehen als Notizen am Eintrag“ (mit den mehrzeiligen Notizfeldern), „Eine Datei je Sache“, „Umstieg mit `finctl umstellen`“ (mit `--probe` und dem Halt der App), „Was auf den Seiten wegfällt“ (mit den Seiten, auf denen), „Entfernen nimmt die Notiz mit“.
- *Fehler, die die Abnahmen bestätigen:* die Untergrenze aus dem Kredit (N.3f), Enter und der verlorene Klick im Monatsabschluss (N.3b), „Speichern“ der Module (N.3e, Nr. 6; N.3f), Kategorie umbenennen und löschen (N.3a, Punkte 4 und 5, „angenommen“). Die Kürzung auf 200 und 2000 Zeichen steht beim Eintrag zu den Notizen.
- *Berichtigt:* Der Eintrag zu den Anschlusskonditionen sprach von „der Datei der Seite“; er sagt jetzt, was der Haushalt verlor. In den Einträgen zu den Policen und zum Verlauf heißt der Ort jetzt `balances.yaml` statt der Seitendatei. `reihen_custom.yaml` blieb, denn die Datei heißt weiter so.
- Nicht aufgenommen, weil nur Entwickler es merken oder weil es erst mit Schritt 6 sichtbar wird: die Textdateien, die Tabelle `settings`, `anschluss_eingegeben`, die Rückfragen ohne Hinweis auf die Notiz.

**N.4d abgenommen am 25.10.2026 (Opus). Schritt 5 ist abgeschlossen.** Abschnitt 2b im Handbuch und die Einträge in `CHANGELOG.md` gelesen: Sie stimmen mit den Abnahmen überein und sind in Worten des Haushalts geschrieben. Die zwei Handbücher sind gleich, und `test_paket`, `test_design`, `test_leck`, `test_namen` und `test_dateinamen` sind grün. Zu den Funden: 1 bis 3 und 6 gehören zu Schritt 6, 4 zu Schritt 8 (wie N.4c, Nummer 5). 5 ist so gewollt. Auch für Schritt 8: Eine Notiz in der Tabelle `settings` lässt sich nur mit SQL löschen; in diesem Haushalt gibt es keine. Beides steht im Gesamtplan.

## Gefundene Abweichungen

(Hier trägt jede Sitzung ein, was nicht in den Plan passt.)

**N.0, 07.10.2026 (Sonnet).** Alle Fundstellen stehen in der Bestandsaufnahme oben; hier das, was nicht zum Plan passt, mit Schritt.

1. **`rules` ist ein Paar, das der Befund nicht nennt.** `rules.yaml` und `rules_custom.yaml` (`rules/engine.py`, `rohe_regeln`; `rules/regelwerk.py`). Zwei Funktionen ändern `rules.yaml` als Text: `engine.repoint_rule` sucht `- id: <kennung>` und das nächste `\n  - id: ` mit zwei Leerzeichen Einrückung, `engine.grundschicht_setzen` ersetzt Zeilen, die mit `allgemeine_regeln:` oder `rules:` beginnen. Schreibt N.2 die Datei mit PyYAML, stehen die Listenelemente ohne Einrückung: `repoint_rule` findet das Ende der Regel nicht mehr und kann, wenn die Regel das Feld nicht hat, das einer späteren ändern. Dasselbe Muster, nur anders: `nachfuehren.taxonomie` (fügt ein Merkmal an einem Blatt in Flow-Form ein, sonst „von Hand“) und `tax/taxonomy.remap_overrides` sowie `r/kategorien.py` (schneiden `overrides.yaml` bei `overrides:` und setzen den Kopf davor). → **N.2 und N.1; Opus entscheidet**, ob die Textschreiber auf strukturiertes Schreiben umgestellt werden oder ob die Umwandlung die Form der Datei erhält.
2. **Weitere `_custom`-Dateien, die der Befund nicht nennt:** `rules_custom`, `csv_profile_custom`, `prognosebasis_custom`. Die beiden letzten haben keine Basis und behalten ihren Namen. Der Docstring von `forecast/szenarien.py` nennt noch `scenarios_custom.yaml`. → N.3.
3. **`backup.yaml` hat eine Seite:** `/system` schreibt `backup_custom.yaml`, `ops.backup_settings` legt beide zusammen. Entscheidung 7 zählt `backup.yaml` zu den Dateien ohne Seite. Ähnlich `server.yaml`: `finctl passwort` schreibt sie mit einem Kopf der App (`web/auth.py`); Entscheidung 7 lässt ihre Kommentare stehen, Entscheidung 3 lässt App-Köpfe wegfallen. → **Opus entscheidet.**
4. **`loans_custom.yaml`, `anschluss.<id>` ist kein Overlay des Eintrags.** Nur `/kredite` (`r/kredite.py`) und `fristen.py` lesen es; die Prognose sieht es nicht. In der Basis gibt es denselben Schlüssel `anschluss` am Kredit, und `segments_from` liest ihn für die Prognose. Würde N.3 `anschluss.<id>` an den Kredit legen, ginge eine Probeeingabe der Seite in die Prognose. In der Kopie ist `anschluss` leer, im echten Datenordner kann es Einträge geben. → **N.3 (Opus: eigener Schlüssel oder nicht).**
5. **`lebensplan_custom` heißt Felder anders als die Basis:** `geburtsdatum` ↔ `person.birth_date`, `rente_ab_alter` ↔ `schwellen.grv_ab_alter`. Die Umwandlung muss umbenennen. Die Datei liegt nicht in der Kopie; N.3 braucht dafür einen erfundenen Datenordner (der Test mit nur der `_custom`-Datei). → N.3.
6. **Renten: die Notiz einer Basisdatei wird heute nicht gelesen.** `renten.quellen` liest `notiz` nur aus `renten_custom`, `herleitung` nur aus `renten.yaml`. Nach N.2 steht die übernommene Notiz in `renten.yaml`; ohne Änderung am Leser sähe `/renten` sie nicht und zeigte weiter nichts oder die Herleitung. → **N.1** (Leser liest `notiz` aus jeder Datei).
7. **Anzeigen und Schreiber, die vom Paar leben.** `/konten` zeigt „überschrieben, Basis …“ (`kontenregeln.basiswerte`, `regel_eigen`), `/bestaende` die Basisnotiz (`base_note`), `abos.laden` setzt die Herkunft `basis`, `geaendert`, `eigen`, `renten.Quelle` trägt `eigen`, `basis_cents`, `basis_ab`, `rules.rohe_regeln` die Herkunft, `/annahmen` zeigt die dokumentierte Vorgabe (`assumptions.basiswert`). Die Schreiber speichern nur die Abweichung (`kontenregeln._gleich`, `abos.speichern`, `objekte.prognose_setzen`, `renten`). Nach N.3 gibt es keine Basis zum Vergleichen; diese Texte ändern sich oder entfallen. Das trifft die Textebene von `pruefen`, nicht die Zahlen. → **N.3 (Opus legt vorher fest, was bleibt).**
8. **Notiz ohne Platz, Einträge ohne Kennung, Zuordnungen, die `notiz` als Wert nähmen:** Tabelle „Leser“ und der Absatz darunter. Der Umwandler darf `notiz` nie in `forecast.yaml: overrides`, `enden`, `account_budgets`, in ein `children` der Taxonomie, in `settings_custom.yaml: einstellungen`, in `taxonomy_migrations.yaml: remap`, in die Zeilen von `zinssaetze` oder in `reihen.zusammen` schreiben. Das Budget je Konto und das Blatt einer Kategorie haben keinen Platz für eine Notiz: Vorschlag: Ihre Kommentare gehen in die Notiz der Konto-Regel (`account_roles.<konto>`) bzw. des Oberbegriffs, mit dem Namen des Blatts als Einleitung. → **N.2 (Opus bestätigt)**.
9. **Köpfe.** `renten_custom.yaml` und `ziele_custom.yaml` tragen eine ältere Fassung des App-Textes und fielen nach Entscheidung 3 nicht weg; zwei Dateien haben mehrere Konstanten (`properties_custom` zwei, `loans_custom` drei), der Vergleich muss gegen alle laufen. Köpfe der App stehen auch über Dateien, die keine `_custom` sind (`strom`, `szenarien`, `overrides`, `server`; 32 Zeilen): Entscheidung 3 nennt sie nicht ausdrücklich. → **Opus entscheidet** für N.2.
10. **Kopf, Abschnitt und Einstellung lassen Grenzfälle.** Die Orte stehen oben. Die Strichlinien über einem Eintrag, der Block vor dem ersten Schlüssel direkt über einer Einstellung und der Block zwischen Einstellungen mit Leerzeile danach brauchen eine Regel; die vier Stellen ohne Lage ebenfalls. Die fünf Euro-Wiederholungen in den `assumptions*.yaml` sind Einstellungs-, keine Feldkommentare, und Entscheidung 3 nennt nur Feldkommentare. → **Opus entscheidet** für N.2.
11. **Musterhaushalt: Vorlagen sind kein YAML.** `abos.yaml`, `balances.yaml`, `renten.yaml` lassen sich ohne `datieren` nicht lesen, `abos_custom.yaml` liest sich falsch (`{M-10}` wird eine Zuordnung). Die Umwandlung nach Entscheidung 8 braucht einen Weg, die Platzhalter zu überstehen. → **N.2.**
12. **`module.py` führt die Dateinamen** (`eintraege=`), an denen es erkennt, ob ein Modul Daten hat, dazu `erststart`. Nach N.3 müssen dort die Namen der zusammengelegten Dateien stehen, im selben Schritt wie der Leser. `overlays.anwenden` liest `settings_custom` und `properties_custom` und schreibt in die Tabellen `settings` und `properties`; auch das folgt den zusammengelegten Dateien (`pruefen` deckt es über `hauptbuch/settings.json`). → N.3.
13. **Freitext, den keine Seite kennt:** `loans[].note`, `loans[].segments_observed[].note`, `properties[].open[]` und `ziele[].quelle` liest kein Modul. Ein Element von `properties[].open[]` ist wegen eines Doppelpunkts als Zuordnung gelesen worden (Datenbefund, nicht Teil von Schritt 5). → N.2 (Opus nimmt sie in die Zuordnung der Notizen unter anderem Namen auf).

**N.1, 07.10.2026 (Sonnet).**

1. **`/api/kredit-anschluss` schrieb `loans_custom.yaml` nur mit `anschluss`.** Die Kredite der Seite (`kredite`), die Vorlagen und alles andere in der Datei gingen bei jedem Speichern verloren (`r/kredite.py`, `{"anschluss": entries}`). Behoben, weil sonst auch die Notizen verloren gingen; Test `…follow-up terms…`. Im echten Datenordner kann das schon passiert sein. → Opus: ansehen, ob dort `kredite:` oder `vorlagen:` fehlen, die in der Sicherung stehen.
2. **Ein Leser der alten Namen fehlte in N.0:** `annahmen._renten` (Belege auf `/annahmen` und `/prognosebasis`) las `q.herleitung` ohne den Umweg über `notiz`. `Quelle.herleitung` heißt jetzt „was die Basisdatei dazu sagt: `notiz`, sonst `herleitung`“. Nach N.2 zeigen diese beiden Seiten deshalb auch die aus Kommentaren übernommenen Notizen der Renten, nicht nur die bisherigen Herleitungen. Das ist ein Textunterschied auf einer Seite, die heute schon etwas an dieser Stelle zeigt. → N.2, Bericht der Textunterschiede.
3. **Mehr Zuordnungen, die `notiz` als Eintrag läsen** als die Tabelle „Leser“: `verpflichtungen` in `balances_custom` stürzt bei einem Schlüssel `notiz` ab (`dict`-Zugriff auf einen Text), ebenso `account_roles`, `abos`, `ziele`, `kredite`, `accounts`, `regeln`, jeweils nach Kennung. Alle rufen jetzt `ohne`. `module_custom` (`module`) und `properties_custom` (`objekte`) nicht; dort schreibt der Umwandler keine Notiz in die Zuordnung.
4. **Die Seiten schrieben die Notiz unter dem alten Namen** (`note`, `warum`). Sie schreiben jetzt `notiz` und `notiz_vom` und nehmen den alten Namen heraus. Das Format der Dateien ändert sich damit bei jedem Speichern einer Notiz; der Test `test_a_note_can_be_changed_and_an_empty_field_restores_the_base` in `tests/test_web.py` fragt jetzt `notiz`.
5. **Reihen: eine Notiz ohne Datum bekam bisher beim Ändern des Takts das heutige Datum** (`reihen._notiz`: ein fehlendes Datum zählte als geändert). Nach Entscheidung 4 bleibt sie ohne. Kein Test zuvor, keiner rot.
6. **Brücken, die mit N.3 entfallen:** `setzen(…, basis=…, ausblenden=…)`, `lesen(*schichten)` mit mehreren Schichten und das Paar-Lesen in `in_zeile` gibt es nur, solange Basis- und Seitendatei getrennt sind. N.3 vereinfacht sie je Bereich; N.4 prüft, dass nichts davon übrig ist.
7. **`Projekt` in `geteilt` trägt jetzt eine Notiz** (`Projekt.notiz`), obwohl Entscheidung 1 die Projekte nicht nennt. Ein Projekt hat eine Kennung, und `geteilt.schreiben` baut die Datei aus den Daten neu auf; ohne das Feld ginge die Notiz bei jedem Speichern verloren. Die Seiten zeigen sie nicht.

**N.2, 08.10.2026 (Sonnet).**

1. **`pruefen --nur-zahlen` meldet nicht „Gleich“.** Fünf Seiten (`annahmen`, `bestaende`, `monatsabschluss`, `prognosebasis`, `start`) zeigen auf der Zahlenebene Unterschiede, weil die Notizen aus Kommentaren dort Ziffern tragen (N.1, Abweichung 2, hatte es angekündigt). Kein Betrag der Rechnung ändert sich: `hauptbuch/` und `ableitung/` sind gleich, und eine Kontrollkopie ohne die Kommentar-Notizen meldet „Gleich“. Die Fertig-wenn-Zeile von N.2 verlangt „Gleich“; sie lässt sich nur erfüllen, wenn Opus die Notizen aus dem Vergleich nimmt oder die Referenz auf der Textebene neu schreibt. → **Opus.**
2. **Eine Notiz der Seitendatei verdeckt die der Basisdatei.** `renten_custom.yaml` trägt für zwei Policen Kommentare, die jetzt Notizen sind; `renten.quellen` nimmt die oberste Schicht, also zeigen `/bestaende`, `/monatsabschluss` und `/start` dort nur noch den Text aus `renten_custom.yaml`, nicht mehr die Herleitung aus `renten.yaml`. Der Text steht weiter in der Datei. Dasselbe kann in jedem Paar geschehen, in dem beide Dateien Kommentare tragen; in der Kopie nur hier. Mit der Zusammenlegung (N.3b) entfällt die Schichtung. → N.3b.
3. **Der Block hinter dem letzten Eintrag ist Abschnitt, auch wenn er an ihm hängt.** Nach der Lesart von N.0 (Abschnitt: Leerzeile danach, vor dem nächsten Eintrag) landet der „ACHTUNG“-Block in `forecast.yaml:102–105`, der unmittelbar unter dem letzten Budget steht und davon handelt, in der Notiz des Bereichs („Stand vor `account_roles`“), nicht beim Budget. Die Zeilen gehen nicht verloren. Eine Lesart „ohne Leerzeile davor, also am Eintrag darüber“ würde ihn zu „Budget:“ der Konto-Regel machen, aber auch andere Blöcke umhängen. → **Opus entscheidet.**
4. **Strichlinie über der Eintragsliste am Dateianfang** (`goals.yaml`): Nummer 10 sagt Abschnitt und Kopf zugleich; ich habe Abschnitt gewählt (Zeilen 18–41). Ändert nur den Hinweis „Stand vor `ziele`“.
5. **Der Stopp der App ist enger als „Datei in alter Form“.** Er gilt, wo das Nachführen schreiben müsste (`nachfuehren.taxonomie`, über `beim_start`, `finctl init` und die Befehle mit Hauptbuch). Ein Stopp bei jeder Datei mit Kommentaren hielte den Start der App auf der Entwicklungskopie an, also auch die Browsertests und die Suite auf ihr, bevor sie umgestellt ist. Das Muster aus Entscheidung 6 (App liest nicht still halbe Werte) braucht N.3: Erst dann liest sie eine Datei nicht mehr.
6. **`repoint_rule` und `grundschicht_setzen` schreiben ohne Wächter**, auch in eine Datei mit Kommentaren. Erreichbar sind sie über Seiten der App; eine Entwicklungskopie in alter Form läuft nur, wenn das Merkmal schon da ist. Ein Wächter wie bei `taxonomie` wäre eine Zeile je Funktion; ich habe ihn nicht gesetzt, weil er die Seitentests auf der Entwicklungskopie in alter Form treffen könnte (nicht ausprobiert). → Opus, mit der Umstellung der Entwicklungskopie.
7. **`neu:` in `renten_custom.yaml`** trägt auch `herleitung` (N.0 nannte nur `renten[]`). Der Leser nimmt es dort; der Umwandler benennt es mit um, sonst verdeckte `notiz` aus einem Kommentar sie. Test `…exists_only_in_the_page_file…`.
8. **`anschluss` und `vorlagen` in `loans_custom.yaml`, `verlauf`, `reihen[]`, `personen`, `buchungen`, `zinssaetze`, `module`** sind keine Einträge mit Notiz; ihre Kommentare gehen in die Notiz des Bereichs („Zu `anschluss`“). Nur `kredite.<id>` trägt eine Notiz am Kredit. Eine Datei, die der Umwandler nicht kennt (`csv_profile_custom`, `prognosebasis_custom`, `energie`, …), behandelt er als Datei ohne Einträge. Die Formen aller Dateien, die der Code kennt, stehen in `umstellen_form.DATEIEN`; getestet sind sie an erfundenen Dateien, nicht alle an echten.
9. **Ein Eintrag, der nur ein Wert ist** (`kennung:` ohne Felder), kann keine Notiz tragen; sein Kommentar geht in die Notiz des Bereichs.
10. **Die Dateien sehen nach dem Umwandeln anders aus.** Sie werden gelesen und neu geschrieben (`dateien.yaml_text`): kurze Sammlungen aus einfachen Werten bleiben in einer Zeile, der Rest ist Block; Anführungszeichen und Abstände folgen PyYAML; Reihenfolge der Schlüssel und Einträge bleibt. Eine Datei, bei der nur der Kopf der App wegfällt (`overrides.yaml`, `settings_custom.yaml`, …), wird nicht neu gesetzt: Die Kommentarzeilen werden herausgeschnitten, der Rest bleibt Byte für Byte.
11. **Sechs Köpfe der App standen im Code, nicht als Konstante** (`kontenregeln`, `routen/kredite` zweimal, `routen/ziele`, `tax/taxonomy`, `rules/categorize`). Sie sind jetzt Konstanten, ohne anderes Verhalten; der Umwandler und der Test brauchen sie.
12. **Eine Notiz aus Kommentaren hat kein Datum.** Kommen zu einer Notiz mit Datum Kommentare hinzu (kommt in der Kopie nicht vor), bleibt das Datum der vorhandenen Notiz an der ganzen.
13. **Die Reihenfolge in der Notiz ist die der Datei**, auch gegenüber einem vorhandenen Freitext: Auf `/annahmen` steht deshalb bei der Police jetzt zuerst der Kommentar und am Ende die frühere Herleitung.

**N.3a, 08.10.2026 (Sonnet).**

1. **Ein Speichern auf `/konten` kuerzte die Notiz einer Konto-Regel auf 200 Zeichen.** `api_konto` schnitt jeden Text bei `NOTIZ_MAX` ab, und das Feld hatte `maxlength="200"`; mit den Kommentaren, die seit N.2 Notizen sind, und den zusammengelegten ist eine Notiz bis zu 1500 Zeichen lang. Jedes Speichern, auch ohne Aenderung, haette die Begruendung abgeschnitten (aufgefallen, weil „Speichern ohne Aenderung“ in `test_an_account_rule_set_on_the_page_moves_the_forecast` Bytes aenderte). Behoben: `REGEL_NOTIZ_MAX` (20.000) fuer die Notiz der Konto-Regel. **Dasselbe Muster steht noch an anderen Stellen**, die N.3b bis N.3d treffen: `konten.py` bei der Notiz einer Verpflichtung (`[:NOTIZ_MAX]`), Reihen (`reihen.py`), und `BESTAND_NOTIZ_MAX = 2000` fuer Bestaende. → jeweils dort pruefen, ob die Notizen der Entwicklungskopie laenger sind.
2. **Der Bericht eines zweiten Laufs am selben Tag haette den ersten ueberschrieben.** Die Sicherung war schon mit `_2` nummeriert, der Bericht nicht. Jetzt auch der Bericht (`umstellung_<Datum>_2.md`); `--probe` schreibt unnummeriert.
3. **Die Musterdateien trugen noch alte Namen,** obwohl N.2 sie als umgestellt meldete (`warum`, `note`, `herleitung`). Sie sind jetzt `notiz`. Wer N.2 pruefen wollte, hatte dort nichts gesehen, weil die App noch nicht anhielt.
4. **Eine Kategorie umbenennen verlor deren Merkmale** (`fix`, `tax`, `einmalig`): `save_custom` ersetzte das ganze Blatt durch den neuen Namen. `tax.taxonomy.save` aendert nur den Namen. Das ist eine Verhaltensaenderung gegenueber vorher, in die gute Richtung.
5. **Eine Kategorie loeschen oder stilllegen entfernt das Blatt jetzt aus `taxonomy.yaml`.** Vorher nahm es nur aus der Seitendatei heraus, was die Seite angelegt hatte; ein Blatt der Basis blieb deklariert und kam beim naechsten `init` zurueck.
6. **`Plan.zu_tun` zaehlt den Kopf der App nicht mehr** (siehe oben). N.4 vergleicht eine frische Umwandlung der Sicherung mit der Entwicklungskopie Datei fuer Datei: Es laeuft ein einziger Befehl mit viel zu tun, der die Koepfe mit entfernt, also bleibt der Vergleich gleich. Ein Kopf, den die App danach wieder schreibt (zum Beispiel `overrides.yaml` bei `categorize`), ist kein Unterschied.
7. **Die Selbstpruefung der Paare vergleicht ohne Notizen,** aber sie ist so streng wie die Werte: Ein Feld der Seite, das der alte Leser ignorierte (ein Merkmal an einem schon vorhandenen Oberbegriff, ein Feld, das es nicht gibt), geht nicht in die neue Datei und steht im Bericht. In der Entwicklungskopie kam das nicht vor.
8. **Ein leerer Text als Notiz der Seite** (`notiz: ""`) verdeckte die Notiz der Basis; nach dem Zusammenlegen steht sie wieder da. Kommt in der Entwicklungskopie nicht vor.

**N.3b, 09.10.2026 (Sonnet).**

1. **Die Notizen sind laenger als N.3a schrieb.** N.3a nannte „bis zu 1500 Zeichen“. Gemessen an der Entwicklungskopie: eine Konto-Regel rund 1.500, eine Quelle rund 1.000, ein Bestand rund 800; die Notizen des Bereichs bis rund 7.200 (am laengsten in `rules.yaml`); Objekte und Kredite bis rund 4.100, ohne Notizfeld bis N.3c. Die Kuerzungen bei 200 und 2000 Zeichen haetten beim Speichern ohne Aenderung also Begruendungen abgeschnitten (Reihe, Verpflichtung, Bestand, Rente). → N.3b, behoben (`notizen.MAX`). *N.3c prueft dasselbe fuer Objekte und Kredite, wenn dort ein Notizfeld entsteht.*
2. **Im Monatsabschluss speicherte Enter die Notiz** (`standTaste`), statt einen Zeilenumbruch zu schreiben. Seit die Notiz eine `<textarea>` ist, konnte man dort keine zweite Zeile tippen. Jetzt ist Enter ein Zeilenumbruch, Strg oder Cmd mit Enter speichert. Betrifft nur die Notiz; die Felder fuer Betrag und Stand speichern weiter mit Enter.
3. **Im Monatsabschluss ging der Klick auf „Speichern“ verloren, wenn die Notiz laenger als zwei Zeilen war.** Verlor die Notiz den Fokus (der Klick auf den Knopf), schrumpfte sie auf zwei Zeilen, die Zeile wurde niedriger, und der in der Zeile mittig stehende Knopf rutschte unter dem Zeiger weg, bevor der Klick ankam. Der Fehler bestand seit N.2 (Notizen aus mehreren Absaetzen); aufgefallen ist er, weil der neue Browsertest eine solche Notiz tippt. Behoben: Die Spalte mit den Knoepfen ist oben ausgerichtet (`table.staende td.tun`).
4. **Speichern ohne Aenderung auf `/ziele` schreibt den Namen, wenn ein Ziel nur in `ziele_custom.yaml` steht und dort keinen Namen traegt** (der Name kommt dann aus einer Vorgabe der Seite). Kein Fehler von N.3b, bis N.3d bleibt es so; der Browsertest legt den Namen vorher in die Datei. → N.3d (die Seitendatei entfaellt).
5. **Die Textebene der Referenz aendert sich auf `/ziele` und `/renten` durch die Notizfelder,** nicht durch das Zusammenlegen (siehe oben, `pruefen`). Wer die Referenz neu schreibt, schreibt diesen Stand. → Opus.
6. **Ausgeblendete Eintraege.** `entfernt: true` an einem Abo oder einer Versicherung blendete sie aus und liess die Begruendung in der Basisdatei. Eine Datei kennt das nach N.3b nicht mehr: Der Eintrag verschwindet aus der Datei, die Notiz steht in der Notiz des Bereichs, der Bericht nennt ihn (Abschnitt „Ausgeblendet gewesen“). In der Entwicklungskopie war keiner ausgeblendet; **im echten Datenordner pruefen** (`grep entfernt` in den drei Seitendateien) und den Bericht der Probe (`--probe`) ansehen.
7. **„loeschen“ fuer jede Rente.** Bis N.3b liess sich nur loeschen, was die Seite angelegt hatte; was in der Basisdatei stand, nur „zurueck“setzen. Es gibt keine Basis mehr, auf die sich zuruecksetzen liesse, und eine falsch angelegte Quelle soll sich loeschen lassen. Die Rueckfrage bleibt. → Opus: bestaetigen oder bei der gesetzlichen Rente sperren.
8. **Die Notizen des Bereichs tragen Saetze ueber Dateien, die es nicht mehr gibt.** Der abweichende Kopf von `renten_custom.yaml` (N.2, Nummer 9) steht in der Notiz des Bereichs von `renten.yaml`, und die Basisdateien von `renten` und `abos` nennen die Seitendatei in ihrer eigenen Notiz. Der Umwandler loescht keinen Text des Haushalts; der Haushalt loescht die Saetze mit einem Klick, wenn die Seiten Notizen des Bereichs zeigen (Schritt 6).
9. **Eine Kennung doppelt in einer Datei** wurde beim Lesen von Abos und Versicherungen still zu einem Eintrag. Jetzt meldet `abos.laden` einen Fehler. Kommt in der Entwicklungskopie nicht vor.
10. **`finctl umstellen` schreibt Daten als Datum.** Die Basisdateien tragen `faellig: 2027-04-13` (ein Datum), die Seitendatei trug dasselbe als Text in Anfuehrungszeichen. Beim Zusammenlegen bleibt, was die Datei hatte; `abos.speichern` schreibt neu ein Datum. Beides liest dieselbe Funktion.
11. **`tests/test_browser.py` legt Notizen fuer Ziele und Bestaende noch in die Seitendateien** (`ziele_custom.yaml`, `balances_custom.yaml`), weil die Seiten dorthin schreiben. N.3d stellt die beiden Zeilen um.

**N.3c, 09.10.2026 (Sonnet).**

1. **`vorlagen.<id>` bleibt ein eigener Schluessel (`vorlage`), die Konditionen werden nicht in den Eintrag gebacken.** Gebacken stuende die Vorlage in `principal_cents`, `segments` und Verwandten; dann zeigte die Tabelle `loans` nach `init` einen anderen Wert als bisher (`init` liest die Datei direkt, und die Kopie hat bei dem Kredit an der Klammer zwei verschiedene Summen: Eintrag und Vorlage) und `hauptbuch/` waere nicht gleich geblieben. Dazu waere „Zuruecksetzen“ auf `/kredite` sinnlos geworden. → Opus: bestaetigen oder entscheiden, dass die Vorlage doch eingebacken wird (dann faellt „Zuruecksetzen“ weg und `hauptbuch/` aendert sich in der Tabelle `loans`).
2. **`anschluss_eingegeben` als Name.** Gewaehlt nach `/kredite` („eingegeben“, „Aus deiner Eingabe“); der Name `anschluss` waere die Prognose. `/api/kredit-anschluss` lehnt jetzt einen Kredit ab, den es nicht gibt (404). Vorher nahm es jede Kennung an und schrieb einen Eintrag, den niemand las.
3. **`/api/property/<id>` fuer ein Objekt, das nicht in `properties.yaml` steht, antwortet mit 400 und aendert auch die Tabelle nicht.** Vorher entstand in der Seitendatei ein Eintrag ohne Namen (`objekte.<id>` ohne Basis), an dem `finctl init` mit einem `KeyError` scheitert, und die Tabelle wurde trotzdem aktualisiert. Kommt in der Entwicklungskopie nicht vor.
4. **Entfernen loescht den Eintrag mit seiner Notiz,** bei Krediten und Objekten wie bei den Abos in N.3b. Vorher blieb der Eintrag der Basisdatei mit `entfernt: true` stehen, damit die Begruendung nicht verloren ging. Die Rueckfrage der beiden Seiten sagt nicht, dass die Notiz mit geht (nur „Er faellt aus jeder Prognose“ und „Es faellt aus jeder Rechnung“). → Opus: Satz ergaenzen oder lassen.
5. **Ein leeres Feld der Objektprognose loescht die Angabe.** Vorher nahm es sie nur aus der Seitendatei, und der Wert der Basis galt wieder. Es gibt keine Basis mehr. Gleich bleibt: Ein Wert, der dem entspricht, was dasteht, aendert nichts.
6. **Andere Leser von `loans.yaml` sehen jetzt, was die Seite schrieb.** `finctl init` (Tabelle `loans`), `realestate.kpi.split_annuity`, `web/verkauf.py` und `kredite.tilgungsplan` lasen schon bisher nur die Basisdatei und ignorierten die Seitendatei; sie sehen jetzt auch auf `/kredite` angelegte Kredite und geaenderte Felder (ein angelegter Ratenkredit steht nach `init` in der Tabelle `loans`, ein ausgeblendeter Kredit der Basis nicht mehr; eine schon vorhandene Zeile bleibt). In der Entwicklungskopie gab es weder das eine noch das andere, `hauptbuch/` ist gleich.
7. **`overlays.anwenden` spiegelt keine Objekte mehr,** siehe oben (`objekte.in_db`). Der Rest von N.0, Nummer 12, folgt mit `settings` in N.3f.
8. **`Paar.seitenwurzel`:** Bei `loans` und `properties` heisst der Schluessel der Seitendatei anders als die Wurzel der Basis (`kredite`, `objekte`); die Pruefung „Text beider Notizen steht in der zusammengelegten“ braucht den Namen. Ein ausgeblendeter Eintrag, den es nur in der Seitendatei gab, bringt seine Notiz in die Notiz des Bereichs (bei den Abos in N.3b noch nicht; dort hielte die Pruefung einen solchen Eintrag mit Notiz an).
9. **Fuer den Umstieg im echten Datenordner,** vor dem Schreiben mit `--probe` ansehen: `kredite:` mit `entfernt: true` (fallen aus der Datei, Notiz beim Bereich), `kredite:`-Eintraege ohne Kredit der Basis (stehen danach in `loans.yaml`), `vorlagen:` und `anschluss:` zu Kennungen, die es nicht gibt (stehen im Bericht unter „kein Leser kannte“), `objekte:` mit `entfernt: true` und `objekte:` ohne Eintrag in `properties.yaml` (waere ein Objekt ohne Namen; `init` scheiterte schon heute daran). Dazu die Frage aus N.1, Abweichung 1: Ob `kredite:` oder `vorlagen:` im echten Ordner fehlen, die in der Sicherung stehen, weil `/api/kredit-anschluss` bis N.1 die Datei nur mit sich selbst schrieb.

**N.3d, 12.10.2026 (Sonnet).**

1. **`/planung` las `goals.yaml` roh** (`r/planung.py`) und sah deshalb die Ziele, die nur die Seitendatei trug, nie: In der Kopie fehlten dort die zwei Ziele, die die Seite angelegt hatte; `/ziele` kannte sie. Mit einer Datei liest es `aus_spec` wie die anderen. Das Ergebnis (`fire`) nutzt die Vorlage `planung.html` nicht; die Seite aendert sich nicht (`planung.txt` der Referenz gleich). Der tote Zweig ist nicht entfernt. → Opus: entfernen oder lassen.
2. **`finctl init` und `balance_snapshots`.** Nach dem Zusammenlegen traegt `balances.yaml` die Werte, die die Seite eintrug. Die alte Schleife schrieb jede Position mit `cents` unter dem **Datum der Datei**; damit stuende ein Wert der Seite (in der Kopie der Kryptobestand, dessen Basiswert `null` war) mit dem alten Datum in der Tabelle, und `hauptbuch/balance_snapshots.json` waere nicht mehr gleich (eine neue Zeile). Jetzt gilt: Der Schnappschuss eines Tages sind die Positionen mit diesem Datum oder ohne eigenes; was die Seite spaeter eintrug, gehoert in den Verlauf. `hauptbuch/` bleibt gleich. **Das ist eine Aenderung gegenueber vorher** fuer Positionen mit einem eigenen, anderen Datum, die ein bekanntes Konto sind (die Tabelle `accounts`) und einen Betrag tragen: Ihre Zeile fehlt jetzt, vorher stand sie unter dem Datum der Datei. In der Entwicklungskopie gibt es das nicht (die Tabelle hat dort keine Zeile). Alternative: jede Position unter ihrem eigenen Datum, dann gibt es in der Kopie eine Zeile mehr. → Opus entscheidet.
3. **`/api/bestand` kennt nur Positionen der Datei** (404 sonst). Vorher legte es fuer jeden Schluessel einen Eintrag in der Seitendatei an, den kein Leser las. `remove` und der Knopf „zurueck“ fallen weg: Es gibt keine Basis, auf die sich zuruecksetzen liesse. `zuruecksetzen` an `/api/ziel` ebenso.
4. **Streichen und Loeschen nehmen die Notiz mit.** Eine Verbindlichkeit samt ihrer Notiz und ein Ziel samt seiner. Die Rueckfrage beim Streichen einer Verbindlichkeit sagte „Die Begruendung in balances.yaml bleibt“; das stimmt nicht mehr, sie sagt jetzt „Die Notiz geht mit.“ Die Rueckfrage beim Loeschen eines Ziels nennt die Notiz nicht (wie bei Krediten und Objekten in N.3c; Schritt 6). → Opus.
5. **Eine ausgeblendete Notiz kommt wieder.** `notiz: ""` an einem Ziel der Seitendatei verdeckte die Notiz der Basis (`ausblenden`); `notiz: ""` an einem Bestand ebenso. Nach dem Zusammenlegen steht die der Basis wieder da (wie N.3a, Abweichung 8). In der Kopie kommt es nicht vor. `notizen.setzen(…, ausblenden=…)` hat keinen Aufrufer mehr, `basis=` nur noch `rules/regelwerk.py` (N.3e). → N.4 entfernt beides.
6. **Der Name eines Ziels nur in der Seitendatei.** Hatte es keinen, zeigte die Seite die Kennung; jetzt steht sie als `name` in der Datei (nur bei den Zielen, die die Seite angelegt hatte). Eine Basis ohne Namen aendert das nicht: Dort schreibt Speichern ihn nicht (Test). Der Betrag eines Notgroschens ohne Betrag und sein Satz stehen auch nach dem Speichern nicht in der Datei.
7. **Ein Konto mit Auszug und ein Wert der Seite.** Das Zusammenlegen braucht `ingest_mode` aus `accounts.yaml` (und `accounts_custom.yaml`); `Paar.kontext` und `Paar.kennung_von` sind neu. Fehlen beide Dateien, kennt es keinen Auszug und uebernimmt alle Felder (dann gelten sie, wie der alte Leser sie las: Ohne Konto in der Datenbank gab es keinen Auszug). Faellt `accounts.yaml` in N.3e mit seinem Paar zusammen, liest `_konto_modi` die zusammengelegte Datei weiter richtig; die `accounts_custom`-Lesart dort entfaellt dann mit dem Paar.
8. **Die Kennung einer Verpflichtung folgt dem Namen.** Aendert die Seite den Namen einer Verpflichtung, aendert sich die Kennung, mit der `/api/verpflichtung` sie anspricht (`bestaende.kennung(name)`). Der Umwandler haelt es fest (`umbenannt`), `/monatsabschluss` sendet die aktuelle Kennung. Eine Kennung, die danach doppelt vorkaeme, haelt den Lauf an.
9. **Datum als Text und als Datum.** Die Datei traegt die Stichtage und `as_of` so, wie sie standen: Text, wo die Seite sie schrieb, Datum, wo sie von Hand standen. Beide Schreiber behandeln denselben Tag als gleich und schreiben dann nichts; ein neuer Wert steht als Text, wie vorher. → N.4 oder Schritt 6 vereinheitlicht, wenn gewollt.
10. **Fuer den Umstieg im echten Datenordner** vor dem Schreiben mit `--probe` ansehen: `geloescht: true` an Verpflichtungen und `entfernt: true` an Zielen (fallen aus der Datei, Notiz beim Bereich); Eintraege in `overrides:` zu Schluesseln, die es in `balances.yaml` nicht gibt (stehen im Bericht unter „kein Leser kannte“); Werte der Seite zu Konten mit Auszug (stehen nur in der Notiz); und ob eine Position mit eigenem Datum ein bekanntes Konto ist (Abweichung 2).

**N.3e, 12.10.2026 (Sonnet).**

1. **`allgemeine_regeln_aus` ist ein neuer Schluessel in `rules.yaml`.** Eine ausgeblendete mitgelieferte Regel liess sich nicht weglassen, ohne dass sie wiederkam, und eine mitgelieferte Regel gehoert nicht in die Datei. Alternativen: ein Eintrag `{id, entfernt: true}` in `rules` (dann liest jeder Leser der Liste einen Eintrag ohne Bedingung) oder die Regel ausgeschaltet im Code. → Opus: bestaetigen.
2. **Eine geaenderte mitgelieferte Regel ist danach eingefroren.** Sie steht ganz in `rules.yaml`; eine spaetere Aenderung der mitgelieferten Regel erreicht sie nicht. Vorher stand nur die Abweichung in `rules_custom.yaml`, und die Grundlage wanderte mit. Die Prioritaet steht mit dem Wert, der galt (10.000 und mehr), das Feld `provenance: allgemein` bleibt. → Opus.
3. **Grundschicht aus, Seite kennt eine mitgelieferte Kennung:** Der alte Leser las die Seiteneintraege dann als eigene Regeln, nur mit den Feldern der Seite (ohne Bedingung fing so eine Regel jede Buchung). Der Zusammenleger gibt das genauso weiter, denn gleich ist gleich; im Bericht steht sie als „Regel, in der Seite angelegt“. In der Entwicklungskopie kommt das nicht vor. → Opus: ansehen, ob die Probe des echten Ordners es zeigt.
4. **Ein leerer Wert nimmt die Angabe heraus** (`person.setzen`, `ops.backup_setzen`). Vorher entfernte er nur die Ueberschreibung, und der Wert der Basis galt wieder. Ohne Basis gibt es nichts, was wieder gelten koennte; ein leeres Rentenalter laesst die Vorgabe der App (67) gelten.
5. **`ops.backup_setzen` und das Sicherungsziel mit `~`:** Die Seite zeigt das Ziel ausgeschrieben (`ops.sicherungsstand`), die Datei fuehrt `~`. Speichern ohne Aenderung haette die Datei veraendert; jetzt gilt derselbe Pfad als keine Aenderung.
6. **`/einrichtung` „Speichern“ der Module legt `module_custom.yaml` an, auch ohne Aenderung** (kein Paar, nicht Teil von N.3e). Deshalb steht `/einrichtung` nicht in der Liste `SEITEN` des Browsertests „Speichern ohne Aenderung“; der neue Test deckt nur Person und Sicherung. → Opus: eigener Schritt oder N.3f.
7. **Die Zahl im Fuss zaehlt die genannten Dateien,** nicht die, die es gibt. Darum faellt sie auf fuenf Seiten, obwohl die Entwicklungskopie nie eine der vier Seitendateien hatte (Art 3 der Fertig-wenn-Zeile).
8. **`test_jahre.py::test_person_and_pension_start_come_from_one_reading`** erwartete zwei Lesevorgaenge (zwei Dateien) und erwartet jetzt einen.
9. **`darf_fehlen` in `design_conventions.yaml`** nennt weiter Seitendateien, die frueher zusammengelegt wurden (`balances_custom`, `ziele_custom`, `abos_custom` und andere); ich habe nur die vier von N.3e herausgenommen.
10. **Fuer N.4:** `notizen.setzen(…, basis=…)` und `ausblenden` haben keinen Aufrufer mehr; `engine.RULES_CUSTOM_PATH`, `regelwerk.custom_lesen`, `custom_schreiben`, `KOPF`, `konten.EIGEN` und `person.EIGEN` sind schon weg, die Zusammenleger der vier Paare brauchen ihre Formen in `umstellen_form.py` (Koepfe) weiter.

**N.3f, 25.10.2026 (Sonnet).**

1. **Vierte Art in `pruefen`: Zeilen der Tabelle `settings`.** Der Lauf haelt an (Opus entschied am 25.10.2026), die Fertig-wenn-Zeile von N.3 nennt die Art jetzt. Danach liest niemand die Tabelle, `init` fuellt sie nicht; sie bleibt leer bis N.4.
2. **Die Entwicklungskopie wurde umgestellt, bevor der Abgleich der Tabelle im Code stand** (die Anweisung kam waehrend des Laufs an). Nachgeprueft, dass Tabelle und Datei uebereinstimmten; die Umstellung hat nichts verloren. Der Abgleich steht jetzt vor jedem Lauf.
3. **Fehler: Speichern ohne Aenderung machte aus `floor_from_loan: <kennung>` ein `true`.** Die Karte auf `/konten` schickt nur den Haken; `kontenregeln._feld_setzen` schrieb `True` und verlor die Kennung des Kredits, danach suchte `_rate_floor` einen Kredit „True“ und die Untergrenze fiel auf den getippten Wert oder die Schwelle zurueck. Gefunden vom neuen Browsertest der Kontokarten. Behoben: Ein Haken, der schon gilt, laesst den Wert stehen. Der Fehler bestand seit N.3a, in der Form davor schon mit der Seitendatei (`{**basis, **seite}`); im echten Datenordner pruefen, ob `floor_from_loan` an einem Konto noch eine Kennung ist, und die Untergrenzen der Konten mit Rate ansehen.
4. **Ein Haken ohne Kredit** (`floor_from_loan` an einem Konto, das noch keinen hatte) schreibt weiter `true`, mit dem alten Verhalten; die Karte fragt nicht nach dem Kredit. → Opus: gewollt, die Karte um die Wahl des Kredits ergaenzen?
5. **`/api/setting` lehnt einen unbekannten Schluessel ab** und meldet 400 fuer ein leeres Feld einer Angabe, ohne die nichts gerechnet wird. Vorher stellte „zurueck“ den dokumentierten Wert her; den gibt es nicht mehr.
6. **Alte Zeilen in `settings` bleiben in einer vorhandenen `finance.db`** (auch in der Entwicklungskopie: vier). Sie sind harmlos und werden nicht gelesen; N.4 raeumt die Tabelle.

**N.4b, 25.10.2026 (Sonnet).**

1. **Ein gestuftes `git rm` ging in den Commit einer anderen Sitzung.** Ich habe `overlays.py` mit `git rm` entfernt, noch bevor der Rest fertig war. Die Opus-Sitzung hat darauf mit ihrem Commit „Plan: echte Kredite geprueft …“ (`8731ce0`) die Loeschung mitcommittet, ohne meine Aenderungen an `module.py`, `zinssaetze.py` und `prognosebasis.py`. Zwischen diesem Commit und meinem war `HEAD` nicht lauffaehig (Import von `overlays`). Danach habe ich die Arbeit in einem Commit mit ausdruecklichen Pfaden abgeschlossen.
2. **Vier statt drei `umstellen*`-Module:** `umstellen_lagen.py` gibt es auch (Kommentarlagen). Der Test nimmt alle `finctl/umstellen*.py` aus.
3. **`bereich_setzen` und `bereiche` bleiben,** obwohl nur Tests (und der Umwandler) sie rufen, siehe oben. → Opus: bestaetigen oder fuer Schritt 8 vormerken.
4. **`module.erststart(config_dir)` prueft den uebergebenen Ordner, schreibt aber nach `module.CONFIG_DIR`** (vorher `overlays.CONFIG_DIR`; im Betrieb derselbe Ordner). Nicht angefasst, weil gleich bleiben sollte; ein Test (`test_init_reports_what_it_brought_forward`) haengt daran und biegt jetzt `module.CONFIG_DIR` um.

**N.4c, 25.10.2026 (Sonnet).**

1. **Die Spalte `einmalig` stand in der Datenbank des echten Ordners schon.** Der Plan (Umstieg) sagt, das Hauptbuch bekomme sie beim ersten Befehl. Im echten Ordner ist sie seit dem 07.10. da; neu ist dort nur die Zeile in `taxonomy.yaml` und das Neuladen der Kategorien. Das Anlegen der Spalte selbst habe ich an einer Wegwerfkopie gesehen, aus der ich sie vorher entfernt hatte. Kein Fehler; die Beschreibung im Gesamtplan stimmt für einen Ordner, dessen Datenbank älter ist.
2. **Es gibt kein `finctl update`.** Der Auftrag fragte danach. Nach dem Umstellen genügt, was das Handbuch schon nennt (`init`, `ingest run`, `categorize`, `validate`). → N.4d: die Folge in den Abschnitt zum Umstieg.
3. **`init` ändert in der Kopie des echten Ordners die Tabelle `accounts`.** Zwei Konten tragen dort einen älteren Namen des Auszugsleser-Profils als `accounts.yaml`. Die Datenbank ist älter als die Datei; mit dem Umstieg hat das nichts zu tun, aber wer vor und nach `init` die Datenbank vergleicht, sieht es. `rules` und `splits` unterscheiden sich nur in Kennungen und Zeitstempeln.
4. **Im echten `config/` liegt eine leere Datei `overrides.yaml.lock`.** Der Umwandler kopiert `*.lock` weder in die Sicherung noch in die `--probe`-Kopie (`umstellen.py`, `copytree`) und lässt sie im Ordner liegen. Ein `diff -r` zwischen `--probe`-Kopie und umgestelltem Ordner zeigt sie deshalb als einzigen Unterschied. Harmlos; im Handbuch (N.4d) erwähnen, falls dort verglichen wird.
5. **`--probe` an einem schon umgestellten Ordner meldet „Nichts umzustellen“ und schreibt trotzdem eine Kopie und einen Bericht** in den Ordner, den man ihm gab. Der Datenordner bleibt unberührt, also kein Fehler; die Meldung und der Inhalt des Ordners passen nur nicht zueinander.
6. **Der Änderungstag von `data/` im echten Ordner liegt am 25.10. vor meiner Probe;** `finance.db` selbst ist seit dem 07.10. unverändert. Vermutlich eine frühere Probe am selben Tag (die Notiz `probe_echter_ordner_2026-10-25.md` liegt in `notizen/` der Entwicklungskopie).

**N.4d, 25.10.2026 (Sonnet).** Funde im Code, nicht behoben:

1. *Terminal und Bericht von `finctl umstellen` schreiben ohne Umlaute* („Pruefung“, „ueberschrieben“, „uebernommen“). Das Handbuch zitiert deshalb nur Wortanfänge. Alles andere in der App hat Umlaute.
2. *Das Feld „Warum“ der Verträge* (`abos.html`) heißt noch so. CONTEXT.md nennt „Begründung“ als zu vermeidend (Notiz). Schritt 6.
3. *Das Handbuch sagt in `/projekte`, `/salden` und `/geteilt/buchungen` „Budgettopf“,* CONTEXT.md nennt das Wort bei Themenkasse unter „Avoid“. Die Seiten selbst habe ich nicht gelesen. Schritt 6 (Oberfläche nach dem Glossar).
4. *`--probe` mit einem Fehler der Prüfungen* (zum Beispiel dem Abgleich von `settings`) schreibt trotzdem schon die Kopie von `config/` in den Probeordner (`umstellen.probieren`, `_kopieren` vor `if plan.fehler`), nur ohne Umwandlung und ohne Bericht. Harmlos, aber der Probeordner sieht danach aus, als wäre etwas geschehen. Das Handbuch sagt „wandelt nichts um“.
5. *Ein Kommentar, den der Umwandler als „wiederholt den Wert in Euro“ wegfallen ließe,* hält die App allein nicht an (`Umwandlung.anlass`) und bleibt, bis in der Datei etwas anderes zum Umstellen anfällt. Das ist so gewollt; ich nenne es, weil das Handbuch sagt, ein neuer Kommentar halte die App an: Es stimmt für jeden Kommentar, der als Notiz landen würde.
6. *Die Rückfragen zu „Entfernen“ auf Kredite und Immobilien* sagen nicht, dass die Notiz mit geht (N.3c, Nr. 4; Schritt 6).
