# Schritt 4: Reihe und Takt

Arbeitsplan für die Umsetzung, geschrieben für ein Modell, das ihn Teil für
Teil abarbeitet (Claude Sonnet). Gesamtplan: `docs/Neufassung_plan.md`.
Begriffe: `CONTEXT.md`. Stand des Codes beim Schreiben: nach Schritt 3
(`6647396`). Vorbild für Aufbau und Regeln: `docs/schritt3_juengst_wirkung.md`.

## Ziel in einem Satz

Eine Zahlung, die regelmäßig kommt, wird mit ihrem Betrag je Termin
fortgeschrieben und nicht mit der Summe ihrer Monate: Eine Miete, deren
Buchungstag über das Monatsende rutscht, zählt zwölfmal im Jahr und nicht
dreizehnmal, ein gekündigter Vertrag fällt sofort aus der Vorschau, ein neuer
zählt sofort voll, und was der Haushalt als einmalig markiert, kommt nicht
wieder.

## Warum jetzt

Die Wirkung aus Schritt 3 zeigt im Monatsabschluss, was ein Ziel bewegt hat.
Auf der Entwicklungskopie bewegt der Kalender die Ziele stärker als das
Verhalten: Die Zwölfmonatssumme je Kategorie zählt eine Monatszahlung
dreizehn- oder elfmal, je nachdem, wo ihr Buchungstag liegt, und das erscheint
als „Tempo“. Solange das so ist, sagt die Wirkung wenig. Die Kontoprognose
kennt das Problem schon (`verfahren.verrutschter_buchungstag`), aber nur für
Kategorien mit Fixkosten-Merkmal und mit einer eigenen Heuristik. Schritt 4
macht daraus eine Regel für beide Vorschauen: Takt je Reihe.

## Entscheidungen (Opus, 05.10.2026)

Diese Punkte sind festgelegt. Eine Sitzung, die einen davon für falsch hält,
hört auf und berichtet, statt ihn anders umzusetzen.

1. **Eine Reihe ist Gegenpartei und Kategorie, über alle Konten.** Dieselbe
   Definition wie `finctl/ledger/reihe.py` (`counterparty_norm` und
   `mgmt_category_id` des Teils), ohne die Betragstoleranz der Verträge. Teile
   ohne Gegenpartei gehören zu keiner Reihe und zählen im Rest ihrer Kategorie
   (Entscheidung 6). Eine Gegenpartei, die in derselben Kategorie Abo und
   Einkäufe bucht, ist eine Reihe ohne festen Takt; das Abo erklärt der
   Haushalt als Vertrag, wie heute.

2. **Der Takt einer Reihe ist eine Zahl von Monaten oder ein Wort.** Fest:
   1, 2, 3, 4, 6 oder 12 Monate (die Teiler des Jahres, wie `verfahren._takt`
   und `abos.yaml`). Dazu `einmalig` und `unregelmaessig`. Die Erkennung
   liefert nie `einmalig`: Was einmal vorkam, kann wiederkommen, und eine
   Erkennung, die es herausnähme, verschwiege Ausgaben. `einmalig` kommt nur
   aus einer Handentscheidung oder einem Merkmal der Kategorie
   (Entscheidung 9).

3. **Erkannt wird über die 24 Monate vor dem Stichtag, aus den Buchungen,
   nicht aus Monatssummen.** Ein Fenster für beide Vorschauen, damit eine
   Reihe in `/konten` und in der Hochrechnung denselben Takt hat; es ersetzt
   `window_months_fixkosten`. Gelesen werden alle Teile aller Konten bis zum
   Stichtag, Umbuchungen nach dem Präfix heraus (Regel „praefix“ der Messung).
   Die Erkennung ist eine reine Funktion auf einer Liste `(Tag, Cent)`; sie
   liest nichts. Ablauf, mit benannten Konstanten:

   - Für jeden Takt t in der Reihenfolge 1, 2, 3, 4, 6, 12:
     - **Termine bilden.** Buchungen am selben Tag sind immer ein Termin
       (Abschlag und Gebühr beim selben Empfänger; geändert nach 4.2). Bei
       t = 1 ist sonst jede Buchung ein Termin. Ab t = 2 werden Buchungen zu
       einem Termin zusammengelegt, die weniger als einen halben Takt nach der
       ersten Buchung dieses Termins liegen: eine Jahresprämie in zwei Raten
       im Januar und Februar ist ein Termin. Hätte dabei ein Termin mehr als
       drei Buchungstage (`MAX_TAGE_JE_TERMIN`), trägt dieser Takt nicht:
       Raten einer Prämie sind zwei oder drei, ein Halbjahr Tanken ist keine
       (geändert nach 4.2). Der Betrag eines Termins ist die Summe seiner
       Buchungen.
     - **Genug Termine:** mindestens 3, bei t = 12 mindestens 2.
     - **Regelmäßiger Abstand:** Mindestens drei Viertel der Abstände zwischen
       aufeinanderfolgenden Terminen liegen innerhalb von ±25 % von t Monaten
       (in Tagen: t mal die mittlere Monatslänge eines Jahres, `TAGE_JE_MONAT`).
     - **Ohne Lücke:** Die Zahl der Abstände ist mindestens drei Viertel der
       Spanne vom ersten zum letzten Termin, gemessen in Takten. Drei Raten
       einer Jahresprämie in drei Folgemonaten, zwei Jahre lang, sind sonst
       „monatlich“, weil vier von fünf Abständen einen Monat lang sind
       (geändert nach 4.2b).
     - **Gleicher Betrag:** Ab dem Beginn der geltenden Höhe
       (Entscheidung 4) gibt es mindestens zwei Termine, bei t = 12 einen,
       aber nur in einer Kategorie mit Fixkosten-Merkmal (geändert nach
       4.2c: sonst waren zwei Einkäufe beim selben Händler, ein Jahr
       auseinander und verschieden teuer, eine Jahreszahlung).
       Geändert nach 4.2: Vorher mussten drei Viertel aller Termine der 24
       Monate zum Median passen, und eine Preisänderung vor einem Jahr machte
       einen Vertrag unregelmäßig. Geändert nach 4.2b: Vorher waren es drei
       Termine, und eine Erhöhung vor zwei Terminen machte die Reihe zwei
       Monate lang unregelmäßig, gegen den Satz in Entscheidung 4.
     - Das erste t, das alle erfüllt, ist der Takt.
   - Keins erfüllt sie: `unregelmaessig`. Ausnahme, damit die Kontoprognose
     nicht verliert, was ihr Jahresposten heute findet: Eine Reihe in einer
     Kategorie mit Fixkosten-Merkmal, die im Fenster genau einen Termin (bei
     t = 12 gebildet) hat, gilt als jährlich.

   Was dabei herauskommt, prüft ein Test je Fall mit erfundenen Reihen (siehe
   4.2). Ein Wocheneinkauf ist unregelmäßig, weil seine Abstände eine Woche
   sind und seine Beträge streuen. Eine Miete mit einem Monat Verspätung ist
   monatlich, weil drei Viertel der Abstände reichen.

4. **Betrag je Termin: Median der letzten Termine, Ausreißer zum Rest.** Der
   Betrag je Termin ist der Median der Termine aus den letzten zwölf Monaten,
   höchstens der letzten drei (jährlich: der letzte, vierteljährlich: die
   letzten drei, monatlich: die letzten drei). So kommt eine Erhöhung nach
   zwei Terminen an und wird nicht von einem Jahr alter Beiträge überstimmt.

   **Die geltende Höhe** beginnt beim frühesten Termin, der zum Betrag je
   Termin passt (innerhalb von `reihe.TOLERANZ`, gleiches Vorzeichen) und ab
   dem mindestens drei Viertel der Termine bis zum letzten passen. Termine
   davor sind der Verlauf der Reihe: Sie zählen weder im Takt noch im Rest,
   denn die Reihe schreibt ihre neue Höhe fort, und die alte ist vorbei
   (geändert nach 4.2: ein Dauerauftrag, der von einem Betrag auf einen
   höheren ging, zählte sonst seine alten Termine im Rest weiter).

   **Ein Ausreißer kommt zusätzlich.** Ein Termin ab der geltenden Höhe, dessen
   Betrag mehr als `reihe.TOLERANZ` vom Betrag je Termin abweicht und der
   weniger als einen halben Takt neben einem passenden Termin liegt, gehört
   nicht zum Takt, sondern zum Rest seiner Kategorie: Eine
   Nebenkostennachzahlung beim selben Empfänger wie der monatliche Abschlag
   zählt in der Hochrechnung weiter einmal im Jahr, statt im Betrag je Termin
   zu verschwinden. Ein abweichender Termin, der allein auf seinem Platz im
   Takt steht, ist dagegen ein Termin des Takts mit anderem Betrag: Er zählt
   nicht im Rest (sein Monat ist im Betrag je Termin mal 12/t schon
   enthalten) und hält die Reihe am Laufen. Geändert nach 4.2b: Eine Reihe mit
   schwankendem Betrag (eine Gutschrift, die jeden Monat anders ausfällt)
   galt sonst als beendet, wenn ihr letzter Termin abwich, und ihre
   abweichenden Monate zählten im Rest ein zweites Mal. Der Preis: Eine
   Schlussabrechnung, die mehr als einen halben Takt nach dem letzten
   Abschlag kommt, hält eine gekündigte Reihe 1,5 Takte länger am Laufen.
   Ein Termin mit anderem Vorzeichen ist immer ein Ausreißer: Eine Erstattung
   ist keine Rate, auch wenn der nächste passende Termin noch nicht gebucht
   ist (geändert nach 4.2c).

5. **Eine Reihe mit festem Takt läuft, bis ihr nächster Termin um mehr als
   einen halben Takt überfällig ist, mindestens aber um einen ganzen
   Monat.** Liegt ihr letzter Termin mehr als Takt plus diesen Spielraum vor
   dem Ende des Stichtagsmonats, ist sie beendet und wird nicht
   fortgeschrieben, auch nicht im Rest. Gewollt: Ein gekündigter Vertrag
   fällt heraus, statt zwölf Monate lang auszulaufen. Monatlich heißt das: Ein
   fehlender Termin beendet nichts, zwei schon (geändert nach 4.4: Ein
   Vertrag, dessen Septemberrate ein Guthaben deckte, galt sonst als beendet,
   und seine Kategorie wurde zur Einnahme, weil der Anteil eines Mitzahlers
   weiterlief). Ob eine Reihe
   läuft und welchen Betrag je Termin sie hat, gilt je Schlüssel der Vorschau
   (Konto bei `/konten`, Haushalt und Block in der Hochrechnung) aus dessen
   Teilen; den Takt hat die ganze Reihe. Ein Dauerauftrag, der das Konto
   gewechselt hat, ist auf dem alten Konto beendet und läuft auf dem neuen.

6. **Fortschreibung je Schlüssel: Reihen mit Takt plus Rest.** Für jeden
   Schlüssel der Vorschau (Konto, Kategorie, Block) teilen sich die Teile in
   Reihen mit festem Takt und den Rest (unregelmäßig, ohne Gegenpartei,
   Ausreißer nach Entscheidung 4).
   - **Hochrechnung:** Jahreswert der Kategorie = Summe über ihre laufenden
     Reihen mit Takt von Betrag je Termin mal 12/t, plus der Rest nach der
     Tabelle der Vorschau wie heute (Summe aufs Jahr, im Konsum wahlweise
     Jüngst). Der Rechenweg der Kategorie nennt jede Reihe mit Gegenpartei,
     Takt, Betrag je Termin und Faktor, beendete mit „beendet, zuletzt MM/JJJJ“
     und null, dann den Rest mit seinem bisherigen Text.
   - **Kontoprognose:** Jede laufende Reihe mit Takt wird ein eigener Posten
     mit `every_months = t` und `starts` = letzter Termin plus t, frühestens
     der erste offene Monat (ein überfälliger, aber laufender Termin kommt im
     nächsten Monat). Der Rest je Kategorie nimmt die Regel für Kosten oder
     Einnahmen (Median mit Mindestzahl oder Schnitt, wie `variable_kosten`
     sagt) im kurzen Fenster. Der Weg für Fixkosten (langes Fenster,
     verrutschter Buchungstag, Jahresposten, `_bloecke`, `_takt`) entfällt;
     das Fixkosten-Merkmal ordnet weiter den Block zu, entscheidet aber kein
     Verfahren mehr. Der Tag im Monat bleibt, wie er ist (Kosten am 1.,
     Einnahmen am 28.); ein Buchungstag je Reihe ist ein eigener Schritt.
     Kosten und Einnahmen derselben Kategorie stehen damit getrennt, als
     eigene Reihen, und werden nicht verrechnet (geändert nach 4.5: Vorher
     stand eine geteilte Miete als Saldo am 1. da, obwohl der Anteil des
     Mitzahlers erst am Monatsende kommt. Die Senke im Monat war damit zu
     flach; gemessen an den echten Monaten der Entwicklungskopie trifft die
     getrennte Rechnung sie besser).

7. **Jüngst bleibt im Konsum und zählt dort nur den Rest.** Reihen mit festem
   Takt rechnen in beiden Tempi gleich, mit Betrag je Termin. Jüngst auf alle
   Blöcke auszudehnen bleibt falsch, aus dem Grund von Entscheidung 2 in
   Schritt 3: Eine Steuernachzahlung oder eine Reparatur ist eine Reihe ohne
   Takt, und drei Monate mal vier vervielfachten sie. `CONTEXT.md` sagt das
   seit diesem Plan so.

8. **Der Haushalt legt den Takt fest, in `config/reihen_custom.yaml`.** Ein
   Eintrag zeigt auf Buchungen, wie Verträge und Planzeilen:

   ```yaml
   reihen:
   - buchungen: [<dedup_hash>]   # eine Buchung der Reihe genügt
     takt: 1                      # 1, 2, 3, 4, 6, 12, einmalig, unregelmaessig
     notiz: ...                   # optional, datiert, ADR 0001
   ```

   Bei einem festen Takt und bei `unregelmaessig` gilt der Eintrag für die
   ganze Reihe der genannten Buchung (`reihe.paare`), bei `einmalig` nur für
   die genannten Buchungen (Entscheidung 9). Vorrang: Handentscheidung vor
   Merkmal `einmalig` der Kategorie vor der Ausnahme für Fixkosten vor der
   Erkennung. Auch ein festgelegter Takt bildet seine Termine und seinen
   Betrag nach Entscheidung 3 und 4 und kann nach Entscheidung 5 beendet sein:
   Der Haushalt sagt, wie oft, nicht, dass es weitergeht; dafür gibt es
   Planzeilen. Wie Annahmen und Planzeilen in Schritt 3 gelten
   Handentscheidungen für beide Stichtage der Wirkung so, wie sie heute
   stehen. Geschrieben wird die Datei über `finctl/dateien.py`.

9. **Einmalig ersetzt den Block `sondereffekt`.** Heute ist er genau die
   Kategorie `immobilie/kaufnebenkosten`, fest im Code. Künftig heißt der
   Block `einmalig` („Einmalig“ auf den Seiten) und nimmt jeden Teil einer
   Buchung, die der Haushalt einmalig gesetzt hat, und jeden Teil einer
   Kategorie mit dem neuen Merkmal `einmalig` (in der Taxonomie wie `fix`,
   in `mgmt_categories` eine Spalte wie `fixkosten`). Die mitgelieferte
   Taxonomie gibt Kaufnebenkosten das Merkmal, der Musterhaushalt ebenso;
   damit bleiben alle Zahlen gleich. Der Block steht in `abgleich.bloecke`
   an erster Stelle: Was einmalig ist, gehört in keinen anderen Block. Der
   Gehaltsmedian hat seine eigene Abfrage und bleibt, wie er ist; gegen eine
   einzelne Prämie ist ein Median über 24 Monate ohnehin fest. Die
   Kontoprognose misst ohne Blöcke und lässt Einmaliges erst ab 4.5 aus
   (`Ausschluss.hashes` und `ausser`), damit 4.3 gleich bleibt. Einmalig gilt für Buchungen, nicht
   für die ganze Reihe, weil derselbe Händler in derselben Kategorie
   wiederkommt; das Glossar sagt es so. Die Stellen, die Kaufnebenkosten
   wegen der Vorschau kennen (`treffer._ist_zaehlt`, `ohne_objekt`, die
   Abfrage in `routen/planung.py`), fragen danach den Block. Die Stellen, die
   sie als Kapital kennen (`realestate/kpi.py`, `web/basis.CAPITAL_PREFIXES`,
   `routen/auswertung.py`), bleiben: Dort geht es um Anschaffungskosten,
   nicht um den Takt.

10. **Was eine Reihe in der Hochrechnung beiträgt, steht an einer Stelle.**
    Die Basis, ein Wegfall und ein Vertragsende rechnen denselben Beitrag:
    Hat die Reihe einen festen Takt, ist es Betrag je Termin mal 12/t, bei
    einer beendeten null; sonst ihre Teile im Rest, wie heute
    (`szenarien.messung`). Heute misst ein Wegfall die Summe der Reihe im
    Fenster; schriebe die Basis zwölf Termine fort und der Wegfall nähme
    dreizehn ab, zöge er einen Termin zu viel ab. Die Kontoprognose rechnet
    ihren Wegfall schon richtig (`konten.wegfall_posten`: mit und ohne die
    Reihe) und bleibt dabei.

11. **Das Gehalt bleibt beim Median.** Es ist eine Reihe mit Takt monatlich,
    aber sein Block hat eine eigene Quelle (Median über 24 Gehaltsmonate,
    Untergrenze des Haushalts), und ein Gehaltswechsel oder eine Sonderzahlung
    ist dort schon behandelt. Die Frage aus Schritt 2 („Gehalt als Reihe“) ist
    damit beantwortet: nicht in Schritt 4. Kredit (Tilgungsplan) und Objekt
    (Annahme) bleiben ebenso.

12. **Der Treffer-Check rechnet sein Soll aus derselben Basis.** Heute misst
    `treffer.jahresbasis` die zwölf Monate vor jedem Monat selbst
    (`ag.measure`) und teilt durch zwölf. Ab 4.4 nimmt es den Jahreswert je
    Block aus der Basis der Hochrechnung zu diesem Stichtag, durch zwölf.
    Sonst prüfte es eine Rechnung, die die Hochrechnung nicht mehr macht.

13. **Die Wirkung nennt Reihen statt Monate, wo eine Reihe Takt hat.**
    `wirkung.KategorieWandel` zeigt heute je Kategorie den Monat, der aus dem
    Fenster fiel, und den, der dazukam. Ab 4.4 teilt sich der Wandel einer
    Kategorie in ihre Reihen mit Takt (je Reihe, die sich bewegt hat:
    begonnen, beendet oder Betrag je Termin von X auf Y) und den Rest (Monat
    raus, Monat rein wie bisher). Die Summe beider ist der Wandel der
    Kategorie.

14. **Lesen einmal je Aufruf, vor allem anderen (4.1).** Schritt 4 rechnet
    je Konto mehr als heute, und `/konten` und `/monatsabschluss` lesen ihre
    Dateien schon jetzt je Konto neu (3.7: 278 und 363 Lesevorgänge, rund
    90 % der Seitenzeit). Behoben wird es mit einem Zwischenspeicher je Datei
    in `finctl/dateien.py`, nicht mit Werten durch jede Schicht: 78 Stellen
    lesen YAML, und das Muster steckt in allen. Der Schlüssel ist der Pfad mit
    `st_mtime_ns` und `st_size`; zurück kommt eine Kopie, damit kein Aufrufer
    den Speicher verändert.

## Was „gleich“ und was „gewollt“ heißt

Die Teilschritte 4.1, 4.2 und 4.6 sind **gleich**: Keine Zahl und kein Text
auf einer Seite ändert sich. Fertig heißt:

```bash
export FINCTL_DATEN="$HOME/Library/Application Support/Finance OS Entwicklung"
.venv/bin/python -m pytest -q
FINCTL_TESTDATEN=muster .venv/bin/python -m pytest -q
.venv/bin/python tests/referenz.py pruefen
```

Teilschritt 4.3 ist **gleich in den Zahlen**: Er fügt die Seite `/reihen`
hinzu und benennt den Block „Sondereffekte“ in „Einmalig“ um. Fertig heißt:
`pruefen --nur-zahlen` ist grün, und `pruefen` zeigt auf der Textebene nur
den neuen Namen und die neue Seite (dazu die Navigation, falls sie dort
erscheint). Der Bericht legt die Textunterschiede bei.

Die Teilschritte 4.4 und 4.5 sind **gewollt** und **ändern** Zahlen. Für sie
gilt:

1. `pruefen` zeigt Unterschiede nur auf den Seiten und Ableitungen, die der
   Teilschritt nennt. Ein Unterschied anderswo ist ein Fehler.
2. Der Bericht nennt je Seite die zehn größten Unterschiede und ordnet jeden
   einem Grund zu: Termin gezählt statt Monat (13 oder 11 statt 12), Reihe
   beendet, Reihe neu, Betrag je Termin statt Schnitt, Ausreißer im Rest.
   Was in keinen Grund passt, ist ein Fund und kommt unter „Gefundene
   Abweichungen“.
3. Die Sitzung schreibt die Referenz **nicht** neu. Nach dem Review wird sie
   in einem eigenen Commit neu geschrieben.

Ändert ein Teilschritt Vorlagen, Routen oder Skripte, kommt
`.venv/bin/python -m pytest -m browser -n 0` dazu.

## Regeln für jede Sitzung

1. Ein Teilschritt pro Sitzung. Lies vorher `CLAUDE.md`, `CONTEXT.md`, diesen
   Plan und die Abschnitte „Gefundene Abweichungen“ in
   `docs/schritt3_juengst_wirkung.md`.
2. Starte `pruefen` erst, wenn du keine Datei mehr änderst. Einen Vorher-Stand
   holst du nur über `pruefen` oder `neu_bauen`, nie über `_bauen`.
3. Bleibt ein Gleich-Schritt rot oder zeigt ein Gewollt-Schritt Unterschiede
   außerhalb seiner Seiten, hör auf und berichte.
4. Keine echten Beträge, Namen, Gegenparteien oder Konten in Code, Tests,
   Kommentaren und Doku (`tests/test_leck.py`). Tests rechnen mit erfundenen,
   runden Reihen. Im Bericht im Chat dürfen echte Zahlen stehen.
5. Rechnen auf dem Server. Kein Skript rechnet einen Betrag
   (`tests/test_rechnen_im_browser.py`).
6. Seitenzeiten messen, vorher und nachher, mit derselben Methode: zweimal
   laden, den zweiten Aufruf zählen (`TestClient`). Stand nach Schritt 3 auf
   der Entwicklungskopie: `/ziele` 0,13 s, `/hochrechnung` 0,22 s,
   `/monatsabschluss` 1,44 s, `/konten` 1,14 s.
7. `ZU_VERZWEIGT` bekommt nichts dazu. Wird eine Funktion zu verzweigt, teile
   sie.
8. Was dir zwischen den Rechnungen auffällt und nicht in deinen Teilschritt
   gehört, kommt unten unter „Gefundene Abweichungen“, mit Warum und Schritt.
9. Kein `git stash`, auch nicht kurz: In diesem Checkout arbeiten andere
   Sitzungen, und ein Stash nimmt ihnen ihre Dateien weg. Einen alten Stand
   holst du über `git worktree` oder `neu_bauen`. Committe nur deine Dateien
   (geändert nach 4.5b: eine Sitzung hatte gestasht und zurückgeholt).

## Die Teilschritte

### 4.1 Jede Datei einmal lesen (gleich)

Entscheidung 14.

- `finctl/dateien.py` bekommt `yaml_lesen(pfad) -> Any`: liest die Datei
  einmal und gibt bei unverändertem `(st_mtime_ns, st_size)` eine tiefe Kopie
  des Gelesenen zurück. Fehlt die Datei, wie die Aufrufer es heute behandeln
  (die Funktion wirft nicht anders als `read_text`).
- Umgestellt werden die Stellen aus dem letzten Eintrag unter „Gefundene
  Abweichungen“ in Schritt 3: `realestate/loan.lade_kredite`,
  `abos._roh_custom`, `objekte._yaml`, `szenarien.aktive_ids`,
  `konten._klammern` und `_planposten`, `forecast_config`, `overlays.lesen`
  und, was das Profil danach noch zeigt. Nicht alle 78 Stellen: nur, was auf
  `/konten` und `/monatsabschluss` mehrfach liest.
- Tests: Schreiben über `schreiben_wenn_geaendert`, danach liest
  `yaml_lesen` den neuen Inhalt; eine Änderung am zurückgegebenen Wert ändert
  den nächsten nicht; die Suite läuft parallel in Kopien der Daten, also ist
  der Schlüssel der absolute Pfad.
- Seitenzeiten vorher und nachher, dazu die Zahl der Lesevorgänge je Seite
  (wie in 3.7 gezählt).

**Fertig wenn:** gleich, und `/konten` und `/monatsabschluss` lesen jede
Datei höchstens einmal je Aufruf.

**Umgesetzt am 05.10.2026.** `dateien.yaml_lesen` mit Speicher je absolutem
Pfad, Schlüssel `(st_mtime_ns, st_size)`, tiefe Kopie bei jedem Rückgabewert;
`schreiben_wenn_geaendert` leert den Eintrag. Umgestellt sind alle 50 Stellen
der Form `safe_load(pfad.read_text())` in 30 Modulen (die Liste aus Schritt 3
und was das Profil danach zeigte: `accounts.yaml`, `forecast*.yaml`,
`balances*.yaml`, `renten*.yaml`, `goals.yaml`, `lebensplan.yaml`, `backup.yaml`),
nicht die in `ingest/`, `rules/`, `tax/taxonomy.py`, `cli.py`, `auth.py` und
`einrichtung.py`. Gemessen auf der Entwicklungskopie, zweiter Aufruf
(`TestClient`), vorher gleich nachher:

| Seite | Zeit vorher | Zeit nachher | Lesevorgänge vorher | nachher |
|---|---|---|---|---|
| `/ziele` | 0,13 s | 0,05 s | 35 | 0 |
| `/hochrechnung` | 0,22 s | 0,12 s | 49 | 0 |
| `/monatsabschluss` | 1,45 s | 0,40 s | 361 (21 Dateien) | 0 |
| `/konten` | 1,15 s | 0,15 s | 276 (13 Dateien) | 0 |

Der erste Aufruf eines frischen Prozesses (Speicher leer) liest jede Datei
genau einmal: `/konten` 14 Dateien, 0,25 s; `/monatsabschluss` 22 Dateien,
0,41 s. `tests/test_dateien.py` hält beides fest.

**Abgenommen am 05.10.2026** (`56dd273`). `pruefen` gleich, von mir
nachgeprüft. Die Frist für frisch geschriebene Dateien (`FRIST_NS`) gehört
dazu: Ohne sie wäre der Speicher bei zwei schnellen Schreibvorgängen gleicher
Länge falsch, und sie kostet nur im ersten Augenblick nach dem Speichern Zeit.

### 4.2 Teile messen und Takt erkennen (gleich)

Entscheidungen 1 bis 5. Noch rechnet keine Vorschau damit.

- **`messung.teile(conn, *, von, bis, ausschluss, konten, je_block)`**: dieselbe
  Abfrage wie `monatssummen` (die Bedingungen in einer gemeinsamen Funktion,
  nicht kopiert), aber je Teil: Konto, Kategorie, Block, Tag, Cent,
  Gegenpartei (`counterparty_norm`, leer als `""`), `dedup_hash`. Ein Test
  hält fest, dass `summiere` über die Teile je Monat genau `monatssummen`
  ergibt, für jede Umbuchungsregel.
- **`finctl/forecast/takt.py`**, rein, ohne Datenbank und Dateien:
  - `Takt = int | Literal["einmalig", "unregelmaessig"]`, die festen Werte
    als Konstante.
  - `erkennen(buchungen: list[tuple[date, int]], *, fixkosten: bool) -> Erkannt`
    nach Entscheidung 3; `Erkannt` trägt Takt und Termine.
  - `fortschreiben(termine, takt, *, stichtag) -> Beitrag`: Betrag je Termin,
    läuft oder beendet (mit letztem Termin), die Ausreißer (Entscheidung 4
    und 5), Jahreswert und Rechenweg-Text.
  - Konstanten mit Namen: `FENSTER_MONATE = 24`, `ABSTAND_TOLERANZ = 0.25`,
    `ANTEIL_REGELMAESSIG = 0.75`, `UEBERFAELLIG_TAKTE = 1.5`,
    `LETZTE_TERMINE = 3`, `TAGE_JE_MONAT` (ein Jahr durch zwölf); die
    Betragstoleranz ist `reihe.TOLERANZ`.
- **`takt.reihen(conn, *, bis, festgelegt) -> Reihen`**: liest die Teile der
  24 Monate bis `bis` und erkennt je Reihe den Takt; `festgelegt` sind die
  Handentscheidungen (in 4.2 leer). Liegt in `forecast/`, nicht in
  `ledger/`, weil nur die Vorschauen sie brauchen.
- **`finctl reihen`** (CLI, nur lesen): die Reihen mit festem Takt, je Zeile
  Gegenpartei, Kategorie, Takt, Betrag je Termin, letzter Termin, läuft oder
  beendet; `--alle` zeigt auch die unregelmäßigen. Für das Review auf der
  Entwicklungskopie.
- **Tests mit erfundenen Reihen**, je Fall einer:
  - monatlich mit rutschendem Tag (1. und 31. im Wechsel, einmal zwei
    Buchungen in einem Monat): monatlich, Jahreswert zwölf Termine;
  - Miete einen Monat zu spät (ein Monat ohne, einer mit zwei): monatlich;
  - vierteljährlich, eine Lastschrift zwei Wochen später: 3;
  - Jahresprämie in zwei Raten in benachbarten Monaten, zwei Jahre: 12,
    Betrag die Summe der Raten;
  - Wocheneinkauf mit streuenden Beträgen: unregelmäßig;
  - gleicher Abstand, aber Beträge streuen über die Toleranz: unregelmäßig;
  - beendet (letzter Termin vor drei Monaten bei Takt 1): beendet, null;
  - neu mit drei Terminen: monatlich, läuft, Jahreswert voll;
  - ein Termin, Fixkosten: 12; ein Termin ohne Fixkosten: unregelmäßig;
  - Abschlag monatlich plus eine Nachzahlung: monatlich, die Nachzahlung
    als Ausreißer im Rest;
  - Erhöhung vor zwei Terminen: Betrag je Termin der neue.
- Ein Test, dass `erkennen` und `fortschreiben` weder Datenbank noch Dateien
  öffnen, nach dem Muster von
  `test_the_calculation_touches_neither_the_ledger_nor_config`.

**Fertig wenn:** gleich. Der Bericht legt die Ausgabe von `finctl reihen` auf
der Entwicklungskopie bei (im Chat, nicht im Repository) und nennt, welche
Reihen ihm falsch erkannt vorkommen.

**Umgesetzt am 05.10.2026.** `messung.teile` mit der Bedingungsfunktion
`_bedingungen`, die `monatssummen` und `teile` gemeinsam benutzen (Test: je
Umbuchungsregel, `hashes`, `ohne_kategorie` und Kontenwahl ergibt `summiere`
über die Teile genau `monatssummen`). `finctl/forecast/takt.py` mit
`erkennen`, `termine_bilden`, `fortschreiben` (rein; ein Test sperrt Dateien und
`sqlite3.connect`) und `reihen` (liest die 24 Monate bis `bis`; `festgelegt` ist
ein Mapping `(Gegenpartei, Kategorie) -> Takt`, in 4.3 füllt es die Datei).
`finctl reihen [--alle] [--json]`. `tests/test_takt.py`: je Fall der Liste oben
eine erfundene Reihe, dazu Lesen, Entscheidung und der Befehl. Auslegungen, wo
der Plan offen ließ:

- **Median bei gerader Zahl** ist das obere mittlere Element, wie
  `verfahren.median`: ein Betrag, der gebucht wurde.
- **Ausreißer** prüft nur die Termine der letzten zwölf Monate (das Fenster,
  aus dem der Betrag je Termin kommt); ältere zählen in keinem Fenster einer
  Vorschau. **Letzter Termin** ist der letzte Termin ohne Ausreißer: Eine
  Nachzahlung nach der Kündigung hält den Abschlag nicht am Leben.
- **Ein festgelegter Takt** bildet seine Termine mit demselben Zusammenlegen
  wie die Erkennung; `einmalig` ist in `festgelegt` ein Fehler (es gilt für
  Buchungen, Entscheidung 8).
- **`--alle`** zeigt die unregelmäßigen Reihen mit mindestens zwei Buchungen
  (wie später die Seite), nicht jede Einzelbuchung.
- Der Text des Beitrags nennt keine Gegenpartei; die setzt 4.4 davor.

**Abgenommen am 05.10.2026** (`b31f362`), `pruefen` gleich. Die Funde der
Sitzung auf der Entwicklungskopie ändern Entscheidung 3 und 4 (dort mit
„geändert nach 4.2“ markiert); umgesetzt in 4.2b, bevor eine Zahl davon
abhängt. Übrige Funde, ohne Änderung:
- **Die Ausnahme für Fixkosten** macht eine Anschaffung in einer
  Abo-Kategorie zur Jahreszahlung, wie der Jahresposten heute. Der Haushalt
  setzt sie in 4.3 einmalig.
- **Zerfallene Gegenparteien** (Referenznummern, zwei Schreibweisen) sind eine
  Frage des Importers, nicht des Takts.
- **Monatlich mit Buchungen am Ersten und Letzten im Wechsel** heißt „alle 2
  Monate“ mit richtigem Jahreswert; ein Name, keine Zahl.
- **Ein Abo mit Einzelkäufen beim selben Anbieter** bleibt knapp unregelmäßig
  und rechnet im Rest wie heute; der Haushalt kann den Takt festlegen.

### 4.2b Termine am selben Tag, geltende Höhe, Deckel je Termin (gleich)

Die Änderungen an Entscheidung 3 und 4 nach dem Review von 4.2. Noch rechnet
keine Vorschau mit dem Takt, also bleibt `pruefen` gleich.

- `termine_bilden`: Buchungen am selben Tag sind ein Termin, bei jedem Takt.
  Ab t = 2 trägt ein Takt nicht, wenn ein Termin mehr als
  `MAX_TAGE_JE_TERMIN = 3` Buchungstage hätte.
- Eine Funktion für den Beginn der geltenden Höhe (Entscheidung 4), benutzt
  von `erkennen` (Betragstest: ab dort genug Termine, statt drei Viertel aller)
  und von `fortschreiben` (Termine davor sind weder Takt noch Ausreißer;
  `Beitrag` nennt sie, etwa als `verlauf`, damit 4.4 und `/reihen` sie
  auslassen und zeigen können).
- `Reihen.nach_schluessel` sucht über ein Wörterbuch statt linear: 4.4 fragt
  es je Teil.
- Tests, je Fall einer, dazu die bestehenden angepasst:
  - Abschlag und Gebühr am selben Tag, monatlich: monatlich, Betrag die Summe;
  - Dauerauftrag, der nach zehn Terminen auf einen höheren Betrag geht:
    monatlich, Betrag der neue, die alten im Verlauf, kein Ausreißer;
  - Preisänderung vor 15 Monaten, 24 Termine: monatlich (vorher
    unregelmäßig);
  - sieben unregelmäßige Buchungen ähnlicher Halbjahressumme in zwei Jahren:
    unregelmäßig (vorher jährlich);
  - Jahresprämie in drei Raten: weiter jährlich;
  - die Nachzahlung zwischen gleichen Abschlägen: weiter Ausreißer.
- `finctl reihen` auf der Entwicklungskopie vorher und nachher: Der Bericht
  nennt die Reihen, deren Takt oder Betrag je Termin sich ändert, mit Grund.

**Fertig wenn:** gleich.

**Umgesetzt am 05.10.2026.** `termine_bilden` legt Buchungen am selben Tag bei
jedem Takt zusammen; `MAX_TAGE_JE_TERMIN = 3` und `Termin.tage`. Der Beginn der
geltenden Höhe ist `beginn_der_hoehe(termine, betrag)`; `erkennen` und
`fortschreiben` benutzen ihn, `Beitrag.verlauf` nennt die Termine davor (für 4.4
und `/reihen`: der Weg der Reihe, nicht zu verwechseln mit dem Verlauf der Stände
im Glossar). `Reihen.nach_schluessel` sucht über ein Wörterbuch. Ein Test je Fall
der Liste, dazu die Erhöhung vor zwei Terminen angepasst (siehe unten). `finctl
reihen` zeigt „(n im Verlauf)“. Auslegungen, wo der Plan offen ließ:

- **Keine geltende Höhe heißt: kein gleicher Betrag.** `beginn_der_hoehe` gibt
  `None` zurück, wenn von keinem Termin an drei Viertel der folgenden zum Betrag
  passen; die Erkennung trägt dann nicht, `fortschreiben` (festgelegter Takt)
  rechnet ohne Verlauf, mit Ausreißern wie vorher. Ein erster Entwurf setzte den
  Beginn dann auf null und machte streuende Zinsreihen zu „monatlich“.
- **Die Obergrenze gilt auch für die Ausnahme der Fixkosten:** Ein Jahrestermin
  mit mehr als drei Buchungstagen ist keine Anschaffung, sondern ein Halbjahr
  Einkäufe. Für einen festgelegten Takt gilt sie nicht: Der Haushalt sagt, wie
  oft.
- **Die Abstände prüft die Erkennung über alle Termine**, nicht erst ab der
  geltenden Höhe (Wortlaut von Entscheidung 3).
- **`erkennen` nimmt einen optionalen `stichtag`,** damit sein Betrag je Termin
  aus demselben Zwölfmonatsfenster kommt wie der von `fortschreiben`; ohne ihn gilt
  der Tag der letzten Buchung. `takt.reihen` reicht ihn durch.
- **Der Ausreißer-Test** prüft weiter nur die Termine der letzten zwölf Monate,
  jetzt ab der geltenden Höhe.

**Abgenommen am 05.10.2026** (`97a43e6`), `pruefen` gleich. Die
Auslegungen der Sitzung gelten; die erste (keine geltende Höhe heißt kein
gleicher Betrag) hat der Vergleich vorher und nachher gefunden, und so ist er
gedacht. Drei der vier Funde ändern Entscheidung 3 und 4 noch einmal
(„geändert nach 4.2b“), umgesetzt in 4.2c. Ohne Änderung:
- **Raten, die nur einmal beobachtet sind** (drei Folgemonate, danach nichts),
  sind monatlich und beendet, bis sie im nächsten Jahr wiederkommen und
  jährlich werden. Aus einem Jahr lässt sich eine Prämie in Raten nicht von
  einem gekündigten Vertrag unterscheiden. Der Haushalt kann den Takt in 4.3
  festlegen.
- **Zinsen und Kapitalertragsteuer als monatlich:** Die Hochrechnung rechnet
  beide selbst (3.2b); die Kontoprognose schreibt sie heute mit dem Median
  fort und ab 4.5 mit dem Betrag je Termin, ein ähnlicher Wert.
- **Ein Vertrag, dem ein Termin vor dem Stichtag fehlt,** ist beendet. Das ist
  die Regel aus Entscheidung 5, und ob er gekündigt ist, weiß nur der Haushalt.

### 4.2c Ausreißer kommen zusätzlich, Lücken, zwei Termine genügen (gleich)

Die Änderungen an Entscheidung 3 und 4 nach dem Review von 4.2b. Noch rechnet
keine Vorschau mit dem Takt, also bleibt `pruefen` gleich.

- **Ohne Lücke** als weitere Bedingung in `_traegt` (Entscheidung 3), mit
  `ANTEIL_REGELMAESSIG` als Schwelle.
- **Gleicher Betrag:** ab der geltenden Höhe zwei Termine, bei t = 12 einer
  (`MIN_TERMINE_HOEHE`, `MIN_TERMINE_HOEHE_JAEHRLICH`).
- **Ausreißer** nur, wer zusätzlich kommt (Entscheidung 4): abweichend und
  näher als einen halben Takt an einem passenden Termin. Abweichende Termine
  auf ihrem eigenen Platz bleiben im Takt; für „läuft“ zählt der letzte
  Termin, der kein Ausreißer ist.
- Tests, je Fall einer, die bestehenden angepasst:
  - Erhöhung vor zwei Terminen: monatlich, Betrag der neue (der Test aus 4.2
    gilt wieder, der aus 4.2b mit drei Terminen fällt);
  - Gutschrift, die jeden Monat um mehr als die Toleranz schwankt, acht Monate,
    der letzte Termin weicht ab: monatlich, läuft, kein Ausreißer;
  - Nachzahlung zwischen zwei gleichen Abschlägen im selben Monat: Ausreißer;
  - Schlussabrechnung zwei Monate nach dem letzten Abschlag: Termin des
    Takts, die Reihe läuft bis 1,5 Takte danach (hält den Preis fest);
  - drei Raten in Folgemonaten, zwei Jahre: jährlich, Betrag die Summe;
  - monatlich Januar bis März und September bis November: unregelmäßig.
- `finctl reihen` vorher und nachher wie in 4.2b, mit Grund je Änderung.

**Fertig wenn:** gleich.

**Umgesetzt am 05.10.2026.** `_ohne_luecke` in `_traegt` (`ANTEIL_REGELMAESSIG`),
`MIN_TERMINE_HOEHE = 2` und `MIN_TERMINE_HOEHE_JAEHRLICH = 1`, `_ausreisser`
für den Zusatz-Test. Ein Test je Fall der Liste, dazu drei angepasst (die
Erhöhung vor zwei Terminen gilt wieder; ein festgelegter Takt über streuende
Beträge hat keine Ausreißer mehr; neu: ein Jahrestermin mit einem Termin ab der
Höhe, Nachzahlung im Monat des Abschlags, Lücke von zwei Terminen schadet nicht).
Auslegungen, wo der Plan offen ließ:

- **Die Spanne** der Lücke ist die Zahl der Tage vom ersten zum letzten Termin
  durch `takt × TAGE_JE_MONAT`; die Zahl der Abstände ist die der Termine minus
  eins. Der Test gilt für jeden Takt, bei t = 12 mit zwei Terminen ist er
  immer erfüllt.
- **„Näher als einen halben Takt“** heißt: weniger als `takt × TAGE_JE_MONAT / 2`
  Tage (bei Takt 1 rund 15 Tage) zu einem Termin ab der geltenden Höhe, der zum
  Betrag passt, davor oder danach. Eine erwartete nächste Stelle, zu der noch
  kein Termin existiert, zählt nicht (siehe „Gefundene Abweichungen“).
- **Die Erkennung braucht weiter drei Termine insgesamt** (`MIN_TERMINE`, bei
  t = 12 zwei); neu ist nur, dass davon zwei (bei t = 12 einer) zur geltenden
  Höhe gehören dürfen.

`finctl reihen --alle` auf der Entwicklungskopie, vorher und nachher: 21 von 271
Reihen ändern sich, keine kommt dazu oder fällt weg. Gründe: Die Lücke macht zwei
Reihen unregelmäßig (Kraftstoff, „alle 2 Monate“ über 13 Monate verteilt;
Kreditzinsen mit elf Monaten Pause, deren Rest eine zweite, zerfallene
Gegenpartei trägt) und eine Gehaltsreihe jährlich statt monatlich (eine
Sonderzahlung je Jahr). Zwei Termine ab der Höhe genügen: ein Dauerauftrag mit
neuem Betrag seit zwei Terminen ist monatlich mit Verlauf; zwei kurze Reihen aus
dem Jahr davor sind monatlich und beendet, ohne Wirkung, weil sie im Fenster der
Vorschau nicht mehr liegen. Drei abweichende Termine auf ihrem eigenen Platz
(eine letzte Rechnung, ein Gutschriftbetrag, eine Erstattung) sind keine
Ausreißer mehr; zwei davon halten ihre Reihe am Laufen. 12 Reihen sind von
unregelmäßig zu jährlich geworden, siehe unten.

**Abgenommen am 05.10.2026** (`44e8774`), `pruefen` gleich. Die zwei Funde
der Sitzung habe ich selbst behoben, weil sie je eine Zeile waren
(„geändert nach 4.2c“ in Entscheidung 3 und 4): Bei t = 12 genügt ein Termin
ab der geltenden Höhe nur noch in einer Kategorie mit Fixkosten-Merkmal, und
ein Termin mit anderem Vorzeichen ist immer ein Ausreißer. Zwei Tests dazu,
einer angepasst. Auf der Entwicklungskopie fallen damit elf zufällige
Jahresreihen weg (Einkäufe, Dividenden, Tickets); die Kfz-Versicherung mit
neuem Preis bleibt jährlich, und die Erstattung der Krankenversicherung zählt
im Rest. 134 Reihen haben einen festen Takt. Beide Suiten und `pruefen`
grün. Die Erkennung ist damit für 4.3 fertig; was sie noch falsch erkennt, legt
der Haushalt auf `/reihen` fest.

### 4.3 Handentscheidung, Einmalig und die Seite `/reihen` (gleich in den Zahlen)

Entscheidungen 8 und 9.

- **`config/reihen_custom.yaml`** lesen und schreiben (`finctl/reihen.py`,
  Schreiben über `finctl/dateien.py`, Lesen über `yaml_lesen`). `takt.reihen`
  nimmt die Einträge als `festgelegt`.
- **Merkmal `einmalig`** in der Taxonomie (Schlüssel `einmalig: true` wie
  `fix: true`), Spalte `mgmt_categories.einmalig` (`ledger/db.py`, wie
  `fixkosten`). Kaufnebenkosten bekommen es in
  `finctl/vorgaben/taxonomy.yaml` und im Musterhaushalt.
- **Block `einmalig`** statt `sondereffekt`, als erster Arm in
  `abgleich.bloecke`: `COALESCE(m.einmalig, 0) = 1` oder die Buchung ist
  einmalig gesetzt (`t.dedup_hash IN (...)`, die Kennungen aus der Datei; wie
  der Objektblock prüft `bloecke`, dass es Hash-Werte sind, bevor sie ins SQL
  gehen). Die Kennung `sondereffekt` verschwindet aus dem Code; `jahre.SPECIAL`,
  `cashflow`, `ohne_objekt`, `prognosebasis`, `treffer` nennen `einmalig`.
  `treffer._ist_zaehlt`, `ohne_objekt` und die Abfrage in
  `routen/planung.py` fragen den Block oder das Merkmal statt der Kategorie.
- **Die Seite `/reihen`** (eigenes Modul in `finctl/web/routen/`, vorher
  `docs/design_conventions.yaml` lesen): je Reihe Gegenpartei, Kategorie,
  Takt (erkannt oder festgelegt, sichtbar unterschieden), Betrag je Termin,
  letzter Termin, läuft oder beendet, Jahreswert. Vorgabe: die Reihen mit
  festem Takt und die festgelegten; ein Schalter zeigt alle mit mindestens
  zwei Buchungen. Eine Auswahl je Reihe legt den Takt fest oder nimmt die
  Festlegung zurück. Aufgeklappt zeigt eine Reihe ihre Termine (Tag, Betrag,
  Ausreißer markiert) und je Buchung „einmalig“. Rechnen und Speichern auf
  dem Server; Speichern ohne Änderung ändert keine Datei (Browsertest).
- **Verweis aus dem Rechenweg:** Noch keiner, die Hochrechnung kennt die
  Reihen erst ab 4.4. Die Navigation bekommt den Eintrag dort, wo
  Zuordnungen stehen (Regeln, Kategorien).

**Fertig wenn:** gleich in den Zahlen (siehe oben), Browsertests grün, und
ein Test zeigt, dass eine einmalig gesetzte Buchung im Block `einmalig`
landet und aus der Basis der Hochrechnung fällt.

**Umgesetzt am 05.10.2026.** `finctl/reihen.py` liest und schreibt
`reihen_custom.yaml` (`lesen`, `festgelegt`, `festlegen`, `einmalig_setzen`,
`laden` = `takt.reihen` mit den Einträgen); die Seite ist
`finctl/web/routen/reihen.py` mit `reihen.html`, im Modul Prognose, in der
Navigation unter Stammdaten, mit Handbuchabschnitt. Merkmal `einmalig`:
Spalte `mgmt_categories.einmalig`, im Lader wie `fix` (am Ast für alle Kinder
oder am Kind). Block `einmalig` (`abgleich.EINMALIG`), bei der Zuordnung zuerst
ausgewertet, in `abgleich.bloecke` an der Stelle der Sondereffekte; `jahre`, `treffer`, `ohne_objekt` und `prognosebasis`
nennen ihn statt `sondereffekt`. Auslegungen, wo der Plan offen ließ:

- **Eine einmalige Buchung ist nie Teil einer Reihe.** `takt.reihen` misst mit
  `je_block=True` und lässt Teile im Block `einmalig` aus (Merkmal der Kategorie
  oder gesetzte Buchung): Sonst bildete sie einen Termin, und 4.4 schriebe sie
  fort. Die Seite führt gesetzte Buchungen darum unter der Tabelle („Einmalig“),
  nicht in einer Reihe; dort nimmt man sie zurück.
- **`treffer._ist_zaehlt` nimmt die Monatssumme statt der Kategorie** (die Messung
  des Ist läuft `je_block`), `ohne_objekt.zaehlt` die Menge der Kategorien mit dem
  Merkmal (`abgleich.einmalige_kategorien`), die Abfrage in `routen/planung.py`
  den Blockausdruck. Eine einmalig gesetzte Buchung fällt damit auch dort heraus.
  In der Kontoprognose steht sie bis 4.5 weiter im Soll (Entscheidung 9).
- **Ein Eintrag je Buchungskennung, mehrere Reihen je Eintrag erlaubt.** Von Hand
  geschriebene Einträge dürfen Buchungen mehrerer Reihen nennen; die Seite ersetzt
  nur die Kennungen der einen Reihe und behält den Rest. Hat eine Reihe zwei
  Einträge, gilt der spätere. Eine Reihe, die schon so festgelegt ist (gleicher
  Takt, gleiche Notiz), lässt die Datei in Ruhe, auch über eine andere ihrer
  Buchungen angesprochen. Ohne Eintrag entsteht die Datei nicht.
- **Die Notiz trägt ihr Datum** (`notiz_vom`), das bei unverändertem Text stehen
  bleibt: ADR 0001, bis Schritt 5 für alle Einträge einen Weg festlegt.
- **Kennungen gehen als Text in SQL** (`abgleich._einmalig_block`), wie die des
  Objektblocks; `reihen.lesen` lässt nur Hexzeichen durch und nennt den Eintrag
  einer kaputten Datei beim Namen.
- **Die Termine auf der Seite nennen den Verlauf „früherer Betrag“:** „Verlauf“ ist
  im Glossar der Weg der getippten Stände.

Browsertests: Öffnen (immer nur eine Reihe), Speichern ohne Änderung, Festlegen mit
Notiz, Zurücknehmen, Einmalig setzen und zurücknehmen
(`tests/test_browser.py`, `/reihen`); der allgemeine Speichern-Test sieht den
Bereich nicht, weil er hinter einem Klick liegt. `tests/test_reihen.py`: Datei,
Taxonomie, Block, Basis der Hochrechnung, Reihe, Seite und Schnittstelle.

**Abgenommen am 05.10.2026** (`1ed49d0`), Referenz danach neu geschrieben.
Nachgeprüft: Die vier Dateien in `ableitung/` sind nach der Umbenennung
(`sondereffekt` zu `einmalig`, das Feld `zuerst`, die Bedingung des Blocks)
gleich der alten Referenz; die übrigen Unterschiede waren die Spalte
`einmalig` in `mgmt_categories` und die neue Seite. Für künftige Pläne: Die
Referenz hält auch Spalten und Blockschlüssel fest, und eine Umbenennung dort
ist für `--nur-zahlen` ein Unterschied.

### 4.4 Die Hochrechnung mit Takt (gewollt)

Entscheidungen 6, 7, 10, 12, 13.

- `fortschreibung.Gemessen` trägt die Teile mit, `fortschreiben` teilt je
  Schlüssel in Reihen mit Takt und Rest (Entscheidung 6). Die Reihen kommen
  als Wert herein (`takt.reihen` einmal je Stichtag), nicht je Schlüssel
  gelesen. `Fortgeschrieben` bekommt `reihe` (Gegenpartei oder leer für den
  Rest) und `takt`; der Rechenweg bleibt ein `herkunft.Posten` je Kategorie
  mit den Reihen im Text (Entscheidung 6).
- `jahre.eingaben` liest die Reihen einmal; `Eingaben` trägt sie, damit
  `rechnen` nichts liest. Die Wirkung tauscht sie mit `base` (sie sind Teil
  der Messung, keine eigene Ursache).
- Je Reihe mit festem Takt, die läuft: Betrag je Termin mal 12/t. Ihre Teile
  im Fenster zählen nicht im Rest, außer den Ausreißern (Entscheidung 4, „kommt
  zusätzlich“); Teile im Verlauf zählen nirgends. Eine beendete Reihe trägt
  null bei, und ihre Teile zählen ebenfalls nicht im Rest. Einmalige Teile
  stehen im Block `einmalig` und nie in einer Reihe (seit 4.3).
- In der Hochrechnung ist der Schlüssel der Haushalt mit Block: Betrag und
  „läuft“ einer Reihe gelten über alle ihre Teile, und sie steht in dem Block,
  in dem ihr letzter Termin liegt. Liegen die Teile einer Reihe in zwei Blöcken,
  nennt der Bericht sie (erwartet: keine oder wenige, etwa an einem Objekt).
- Jüngst zählt im Konsum nur den Rest (Entscheidung 7).
- Wegfall und Vertragsende in der Hochrechnung nehmen den Beitrag der Reihe
  aus derselben Funktion wie die Basis (Entscheidung 10): `szenarien.messung`
  und `jahre._vertragsenden` fragen sie, statt das Fenster selbst zu summieren.
- `treffer.jahresbasis` nimmt sein Soll aus der Basis (Entscheidung 12). Das
  sind sechs Stichtage je Aufruf; die Zeit von `/monatsabschluss` vorher und
  nachher steht im Bericht (nach 4.1: 0,40 s).
- `wirkung.KategorieWandel` nach Entscheidung 13; die Seite des
  Monatsabschlusses zeigt die Reihen, die sich bewegt haben, mit Grund.
- **Erwartet** (Entwicklungskopie): Kategorien mit Monatsreihen bewegen sich
  um einen Termin, wo das Fenster dreizehn oder elf hatte; beendete Verträge
  verschwinden; neue zählen voll; die Wirkung zwischen zwei Stichtagen zeigt
  unter „Tempo“ kaum noch Miete und Fixkosten, sondern Konsum.

**Seiten mit Unterschieden:** `/hochrechnung`, `/ziele`, `/monatsabschluss`
(samt `start`, `bestaende`), `/annahmen` (Prognosebasis, Spalte der
Hochrechnung), die Auswertung, die aus der Hochrechnung liest, `/planung`
(Wirkung der Wegfallzeilen in der Hochrechnung) und `ableitung/` der
Hochrechnung. Keine im Hauptbuch, auf `/konten` oder in der Ableitung der
Kontoprognose.

**Umgesetzt am 05.10.2026.** `Vorschau.reihen` (die Reihen eines Stichtags als Wert),
`Gemessen.teile`, `Fortgeschrieben.reihe/takt/beitrag/monate` und `Zerlegung` in
`fortschreibung.py`: Je Schlüssel zählt eine laufende Reihe mit festem Takt mit ihrem
Jahreswert, ihre Teile im Termin, im Verlauf und an einer beendeten Reihe zählen im Rest
nirgends, ein Ausreißer im Rest. `takt.Reihe.einordnen` sagt je Buchungstag „Takt“, „Rest“
oder „nirgends“, `takt.beitrag_in_basis` rechnet denselben Beitrag für die Basis, einen
Wegfall und ein Vertragsende (Entscheidung 10). `jahre._basis` liefert dazu je Kategorie die
`Zerlegung` (Reihen, Rest, Monate des Rests), `Eingaben.base_reihen` trägt sie. Auslegungen,
wo der Plan offen ließ oder anders lag:

- **`Eingaben.base_reihen` statt `Eingaben.reihen`.** Die Wirkung tauscht `base` je Block;
  ein einziges Feld `reihen` ließe sich nicht je Block tauschen. `base_reihen` hält je Block
  und Kategorie die Reihen mit ihrem Beitrag und den Rest samt seinen Monaten, wird mit `base`
  und `base_monate` getauscht und macht die zweite Abfrage der Wirkung (`_monatsbetraege`)
  überflüssig: Die Monate „raus“ und „rein“ kommen aus den Eingaben beider Stichtage.
- **Die Hochrechnung geht von den Reihen aus, nicht von den Teilen im Fenster.** Eine
  laufende Reihe zählt auch dann, wenn ihr einziger Termin vor dem Fenster liegt (jährlich:
  13 Monate her, läuft noch). Eine beendete steht nur im Rechenweg (mit null), wenn ein Teil
  von ihr im Fenster liegt. Das ist der Grund „Termin gezählt statt Monat“ in seiner
  Randform (0 statt 1).
- **Der Block einer Reihe** ist der ihres letzten Termins (`Reihe.block`); Teile in einem
  anderen Block zählen dort nirgends. Auf der Entwicklungskopie hat keine Reihe Teile in zwei
  Blöcken.
- **Die Art der Kategorie (Kosten oder Einnahme) entscheidet sich am Rest.** Hebt sich der Rest
  einer Kostenkategorie auf oder dreht das Vorzeichen, rechnet er als Einnahme (kein Jüngst).
- **`takt.reihen` und `reihen.laden` nehmen einen `ausschluss`**: Buchungen einmaliger
  Planzeilen bilden keinen Termin, wie sie in keiner Messung stehen.
- **Wegfall und Vertragsende:** `szenarien.messung(conn, line, f, reihen=None)` fügt `takt_jahr`,
  `rest_cents` und `takt_reihen` hinzu, `jahreswirkung` rechnet mit `gemessen_je_monat`. `cents`
  bleibt die Summe im Fenster: Die Kontoprognose und `/planung` lesen sie (Entscheidung 10, sie
  bleibt dabei). Die Reihen eines Wegfalls und eines Vertrags werden ohne Fenster gesucht;
  im Rest zählt nur das Fenster. Die Obergrenze „nie mehr versprechen, als der Vertrag kostet“
  gilt weiter. Der Rechenweg nennt die Reihe mit Takt statt „gemessen über 12 Monate“.
  Eine Reihe, die schon eine Wegfall-Zeile abzieht, zieht die Kündigung nicht noch einmal ab,
  auch nicht über ihre Termine vor dem Fenster (`schon_reihen`; ein erster Entwurf zählte sie
  doppelt, gefunden beim Vergleich der Vertragsenden vorher und nachher).
- **Treffer-Check** (Entscheidung 12): `treffer._soll_je_block` nimmt `jahre._basis` zum Ende
  des Fensters, durch zwölf. Zinsen, Kapitalertragsteuer (`GERECHNET`) und abgewählte
  Kategorien zählen im Soll weiter wie gebucht, ebenso wie die Buchungen einmaliger
  Planzeilen: Das Ist ist, was gebucht wurde, und der Hinweis aus 3.6 gilt weiter.
- **Reihenfolge der Reihen im Rechenweg:** groß vor klein, dann Takt und letzter Termin, erst
  zuletzt der Name (`takt.groesse`, `fortschreibung._reihenfolge`). Alphabetisch hing sie an
  Namen, die der Haushalt ändern kann, und `test_umbenennen_aendert_keine_zahl` fiel um; die
  Teile eines Wegfalls kamen zudem in der Reihenfolge der Abfrage.
- **Wirkung auf der Seite:** Eine Kategorie mit bewegten Reihen zeigt die Kategorie, je Reihe
  eine Zeile (begonnen, beendet, Betrag je Termin von X auf Y, Takt) und den Rest mit seinen
  Monaten. `KategorieWandel.reihen`, `rest_vorher`, `rest_nachher`; ihre Summe ist die Änderung.
- **Handbuch:** Wirkung, Prognosebasis und `/reihen` nennen die Reihen. Die Gründe auf
  `/annahmen` („Jahresrechnung: Zwölfmonatsschnitt“) bleiben für 4.5, wo beide Spalten
  neu formuliert werden.

**Gemessen und verglichen (Entwicklungskopie).** Beide Läufe der Suite grün; auf den
echten Daten fällt allein `test_referenz` (das ist `pruefen`). Browsertests grün. `pruefen`
zeigt 18 Unterschiede: `/hochrechnung`, `/ziele`, `/annahmen` samt Prognosebasis, `start`,
`bestaende` und `monatsabschluss` (nur die Zeile „Barista FIRE … hochgerechnet“), dazu in
`ableitung/` Basis, Jahre, Prognosebasis und den Treffer-Check (nur die Jahresbasis);
Hauptbuch, `/konten`, `/planung`, Abgleich und Kontoprognose bleiben gleich. 20 Kategorien
ändern ihren Jahreswert; die Gründe: Reihe beendet, Reihe neu, Termin gezählt statt Monat
und Betrag je Termin statt Schnitt. Der Bericht der Sitzung legt je Seite die zehn größten
Unterschiede mit Grund bei. Seitenzeiten, zweiter Aufruf, vorher gleich nachher: `/ziele`
0,04 s gleich 0,07 s, `/hochrechnung` 0,09 s gleich 0,12 s, `/monatsabschluss` 0,23 s gleich
0,28 s, `/konten` 0,13 s gleich 0,14 s, `/annahmen` 0,12 s gleich 0,30 s.

**Abgenommen am 06.10.2026** (`49daeb3`), mit einer Änderung von mir,
danach Referenz neu geschrieben. Die Unterschiede lagen auf den genannten
Seiten; die Abweichungen der Sitzung vom Plan (`Eingaben.base_reihen`, eine
laufende Reihe zählt auch mit einem Termin vor dem Fenster) gelten.

- **Ein fehlender Monatstermin beendete eine Reihe.** Der Internetvertrag
  hatte im September keine Abbuchung (ein Guthaben aus der Verlängerung deckte
  sie), galt als beendet, und die Kategorie wurde mit dem weiterlaufenden
  Anteil eines Mitzahlers zur Einnahme (+351 € im Jahr statt rund −300 €).
  Entscheidung 5 gibt jetzt mindestens einen ganzen Monat Spielraum
  (`UEBERFAELLIG_MIN_MONATE`); ab Takt 2 ändert sich nichts. Damit läuft auch
  die Gutschrift aus 4.2b wieder. Ein Test je Seite der Regel, der Fall in
  `test_wirkung` endet jetzt zwei Monate vor dem Stichtag.
- **Ein kleinerer Termin auf seinem Platz** (eine Rate, die ein Restguthaben
  mindert) ist kein Ausreißer und ändert den Betrag je Termin erst, wenn er
  der Median der letzten drei ist. So gewollt.
- **Zerfallene Gegenparteien wiegen jetzt mehr als in 4.2:** Ein Anbieter, der
  seine Schreibweise ändert, beendet nach zwei Monaten seine alte Reihe, und
  die neue braucht drei Termine; dazwischen zählt er im Rest. Die
  Kfz-Steuer unter zwei Schreibweisen zählt doppelt. Der Mobilfunk der
  Entwicklungskopie hat fünf Anbieter unter acht Schreibweisen. Das wird 4.5b.
- **Ein Erlös in einer Fixkosten-Kategorie** (ein verkauftes Gerät) ist nach
  der Ausnahme aus Entscheidung 3 eine Jahreszahlung, zählt also bis 18 Monate
  danach, statt nach 12 aus dem Fenster zu fallen. Der Haushalt setzt ihn auf
  `/reihen` einmalig.
- **`/annahmen` braucht 0,30 s statt 0,12 s** (sechs Stichtage für den
  Treffer-Check). Hingenommen.

### 4.5 Die Kontoprognose mit Takt (gewollt)

Entscheidungen 5 und 6.

- `kontoprognose_regeln` verliert die Zeile für Fixkosten; `Regel.selten`,
  `verfahren.langes_fenster`, `verrutschter_buchungstag`, `jahresposten`,
  `_bloecke` und `_takt` entfallen samt ihren Tests, ersetzt durch
  `takt.fortschreiben` und Tests dort. `Vorschau.since_fixkosten` und
  `Einstellung.since_fixkosten` entfallen; `window_months_fixkosten` in
  `forecast.yaml` wird nicht mehr gelesen (die Einstellung auf `/annahmen`,
  falls es eine gibt, verschwindet, und der Bericht sagt es).
- Je laufender Reihe mit Takt ein `RecurringItem` (Entscheidung 6). Wo der
  Code Posten nach `label` sucht (Einkommens-Untergrenze, Wegfall,
  `_korrektur_tage`, die Seite), prüft die Sitzung, ob zwei Posten derselben
  Kategorie sich stören, und berichtet jede Stelle.
- Einmaliges fällt aus der Messung der Kontoprognose: gesetzte Buchungen über
  `Ausschluss.hashes`, Kategorien mit Merkmal über `ausser` (Entscheidung 9).
- `treffer.konten` folgt von selbst (es ruft `abgeleitete_posten`).
- Die Gründe in `prognosebasis` („Median im langen Fenster“, „Jahresposten“)
  sprechen danach von Takt und Rest.

**Seiten mit Unterschieden:** `/konten`, der Treffer-Check der Konten auf
`/monatsabschluss`, `/annahmen` (Prognosebasis, Spalte `/konten`) und
`ableitung/` der Kontoprognose. Keine in der Hochrechnung.

**Umgesetzt am 06.10.2026.** `Reihen.fuer_konto` rechnet die Reihen des Haushalts aus den
Teilen eines Kontos (`Reihe.auf_konto`: Termine, Betrag je Termin und ob sie laeuft je Konto,
der Takt bleibt der der ganzen Reihe, Entscheidung 5); `Vorschau.reihen` gilt jetzt auch fuer
`reihe="konto"`. Ein Posten je laufender Reihe (`fortschreibung._termin_posten`): Etikett die
Kategorie, `every_months = t`, `starts` = letzter Termin plus t, frühestens der erste offene
Monat. Eine beendete Reihe bucht nichts, und ihre Teile im Fenster zaehlen nirgends. Der Rest
rechnet nach der Tabelle der Kontoprognose im kurzen Fenster; ihre Zeile fuer Fixkosten
entfaellt, `verfahren.wahl` nimmt fuer Fixkosten die Regel nach dem Vorzeichen. Entfallen sind
`langes_fenster`, `verrutschter_buchungstag`, `jahresposten`, `_bloecke`, `_takt`,
`Regel.selten`, `Einstellung.since_fixkosten`, `Vorschau.since_fixkosten` und `fenster="lang"`
samt Tests; `window_months_fixkosten` wird nicht mehr gelesen (auf `/annahmen` gab es dazu keine
Einstellung; im Musterhaushalt ist die Zeile entfernt, ein Datenordner darf sie behalten).
Einmaliges fehlt in der Messung: gesetzte Buchungen in den Hashes, Kategorien mit dem Merkmal in
`ausser`. Die Gruende auf `/annahmen` sprechen von Reihen und Rest. Auslegungen, wo der Plan
offen liess:

- **Was eine feste Zahl ersetzt, hat seine eigene Quelle.** Kategorien in `overrides` (der
  Gehaltsfloor) bekommen keine Posten aus Reihen; ihre Teile zaehlen im Rest, wo der Floor sie
  ersetzt. Der Floor haengt am Etikett und ersetzte sonst auch den Posten einer Reihe derselben
  Kategorie: Eine jaehrliche Reihe im Gehalt (drei Monate, die unter einem zerfallenen Namen
  stehen, siehe unten) stand im Oktober als zweiter Posten neben dem Monatsgehalt, und der Floor
  zaehlte beide: zweimal das Gehalt im Oktober. Das ist Entscheidung 11 fuer die Kontoprognose;
  `test_the_gehalt_is_measured_once_and_the_floor_replaces_it_once` haelt es fest.
- **Mehrere Posten unter einem Etikett.** Die Kategorie ist das Etikett von Reihen und Rest
  zugleich: `engine.project` summiert sie im Monatsdetail, `_herkunft_konto` fuegt ihre Texte zu
  einem Posten zusammen (`_zusammen`, durch `|` getrennt). Die uebrigen Stellen, die nach dem
  Etikett suchen, sind geprueft: der Floor (`engine.project`, `wegfall_posten`, `treffer.konten`)
  ist mit dem Satz oben abgedeckt; `_korrektur_tage` und `prognosebasis` gehen nach der
  Kategorie und summieren; `ohne_objekt.zaehlt` liest die Quelle der Herkunft, die bei Reihen und
  Rest `gemessen` ist.
- **Die Reihen werden einmal je Stichtag gebaut** (`konten.reihen_vor`) und an jedes Konto
  gereicht (`household_accounts`, `treffer.konten` je Monat, `prognosebasis`). Ein Wegfall nimmt
  die Buchungen seiner Reihe mit `Reihen.ohne_buchungen` heraus: erkannt wird nur neu, was sie
  trug, ohne das Hauptbuch noch einmal zu lesen (`Quelle` haelt, womit erkannt wurde).
- **`derive_recurring(reihen=...)` nimmt die Reihen eines Kontos**; ohne sie rechnet alles im
  Rest. Eine Vorschau prueft, dass Haushalts- und Kontoreihen zur richtigen Vorschau gehoeren.
- **Der Termin einer Jahrespraemie in Raten ist die erste Rate**, nicht die letzte wie im Block
  des Jahrespostens: derselbe Posten steht einen Monat frueher (siehe unten).

**Gemessen und verglichen (Entwicklungskopie).** Beide Laeufe der Suite gruen bis auf zwei
Tests auf den echten Daten: `test_referenz` (das ist `pruefen`) und
`test_the_ceiling_leaves_room_for_a_median_month` (siehe „Gefundene Abweichungen“). Browsertests
gruen. `pruefen` zeigt 17 Unterschiede: in `ableitung/` die Kontoprognose auf zwoelf und
sechzig Monate, die Posten je Konto, die Prognosebasis und den Treffer-Check, und auf den Seiten
`/konten`, `/annahmen` samt `/prognosebasis` und `/monatsabschluss` samt den Umleitungen
`start` und `bestaende` (dort nur zwei Zeilen: „Prognose Ø“ und der Tiefpunkt-Hinweis des
Kontos, nicht der Treffer-Check). Hauptbuch, Hochrechnung, `/ziele`, `/planung`, Abgleich und
Jahresrechnung bleiben gleich. 27 Kombinationen aus Konto und Kategorie aendern ihren Jahreswert
(auf sechs Konten); die Gruende: Reihe neu, Betrag je Termin statt Schnitt oder Median, Reihe
beendet, Ausreisser im Rest, und was in keinen davon passt (siehe unten). Der Bericht der Sitzung
legt je Seite die zehn groessten Unterschiede mit Grund bei. Seitenzeiten, zweiter Aufruf, vorher
(4.4) und nachher: `/ziele` 0,07 s und 0,07 s, `/hochrechnung` 0,12 s und 0,12 s, `/konten`
0,14 s und 0,19 s, `/monatsabschluss` 0,28 s und 0,34 s, `/annahmen` 0,30 s und 0,50 s (sechs
Reihenstaende fuer den Treffer-Check).

**Abgenommen am 06.10.2026 (Opus).** `pruefen` nachgerechnet: 17 Unterschiede in elf Dateien,
alle aus der Kontoprognose (fuenf Ableitungen, `/konten`, `/annahmen`, `/prognosebasis`,
`/monatsabschluss`, `start`, `bestaende`); Hauptbuch, Hochrechnung und Abgleich gleich. Die
Auslegung zum Gehaltsfloor gilt (Entscheidung 11). Die zwei Zeilen auf `/monatsabschluss` gehoeren
zur Seite, die der Plan nennt. **Brutto bleibt** (Entscheidung 6, geaendert nach 4.5): Auf dem
Betriebskonto liegt die Senke unter dem Monatsanfang, gemessen an den letzten 14 echten Monaten,
naeher an der neuen Rechnung als an der alten; die Miete geht am Monatsanfang, der Anteil des
Mitzahlers und das Gehalt kommen am Monatsende. Verrechnen hiesse, eine echte Senke zu verbergen.
Der rote `test_the_ceiling_leaves_room_for_a_median_month` ist damit ein Befund ueber den Deckel
des Haushalts, keiner ueber den Code. Der Haushalt fuehrt das Konto knapp und nimmt das Risiko an;
der Test heisst jetzt `test_the_ceiling_lies_above_the_floor` und prueft nur noch, dass der Deckel
ueber der Grenze liegt, und eine Unterschreitung zeigt `/konten` als Warnung. `/annahmen` mit
0,50 s ist angenommen. Zahlen in `notizen/` im Datenordner.

### 4.5b Gegenparteien zusammenführen (gewollt, wo der Haushalt es sagt)

Der Importer normalisiert die Gegenpartei aus dem Text der Bank, und manche
Banken tragen Referenznummern, Kontonummern oder ein Stichwort aus dem
Verwendungszweck hinein. Dieselbe Zahlung erscheint dann unter mehreren
Schreibweisen und ist mehrere Reihen (Abnahmen von 4.2 und 4.4). Den Importer
zu ändern, verschöbe Regeln und Handentscheidungen, die an
`counterparty_norm` hängen; das ist kein Teil von Schritt 4.

- **Handentscheidung „gehört zu“** in `config/reihen_custom.yaml`: Eine
  Gegenpartei zeigt auf eine andere (`zusammen: {<schreibweise>: <gegenpartei>}`),
  und `takt.reihen` gruppiert nach der Zielgegenpartei. Die Reihe heißt nach ihr.
  Nur für die Reihen der Vorschau, nicht für Regeln, Verträge oder
  `ledger/reihe.py`.
- **`/reihen`** bietet an einer Reihe „gehört zu …“ mit einer Auswahl der
  Reihen derselben Kategorie; ein Vorschlag, wo zwei Reihen derselben Kategorie
  denselben Betrag je Termin haben und die eine endet, wo die andere beginnt.
  Zusammenführen geschieht nur auf Klick.
- Ein Test: zwei Schreibweisen mit je sechs Monaten hintereinander sind nach
  dem Zusammenführen eine monatliche Reihe mit zwölf Terminen.

**Fertig wenn:** gleich ohne Einträge (`pruefen` grün, solange die Datei keine
Zusammenführung trägt), Browsertests grün. Auf der Entwicklungskopie probiert
der Bericht es an Mobilfunk und Kfz-Steuer und nennt, was sich dann ändert.

**Umgesetzt am 06.10.2026.** `zusammen` steht in `reihen_custom.yaml` neben `reihen` (`{schreibweise:
gegenpartei}`); `reihen.zusammen()` liest und prüft (bei einer Kette gilt das letzte Ziel; ein
Kreis oder ein Eintrag auf sich selbst ist ein Fehler, der die Datei nennt),
`reihen.zusammenfuehren(conn, schreibweise, ziel | None)` schreibt über `dateien.py`.
`takt.reihen(zusammen=...)` gruppiert nach der aufgelösten Gegenpartei, `Reihe.schreibweisen`
nennt, was zusammengeführt ist. `forecast/zusammenfuehren.py` schlägt Paare vor; `/reihen`
zeigt sie unter „Vorschläge“, bietet an jeder Reihe „Gehört zu“ und „Trennen“
(`POST /api/reihen/zusammen`), und `finctl reihen` zählt „(+n zusammengeführt)“. Auslegungen,
wo der Plan offen ließ:

- **Die Zusammenführung gilt je Gegenpartei, nicht je Reihe,** also in jeder Kategorie, in der
  die Schreibweise steht: Sie sagt etwas über den Zahler, und ein Zahler, der Miete, Strom und
  Internet in einer Überweisung bucht, steht in mehreren Kategorien. Der Schlüssel in der Datei
  hat darum keine Kategorie. Beim Schreiben verlangt der Server, dass beide im Hauptbuch stehen
  und eine Kategorie teilen.
- **Handentscheidungen folgen der Zusammenführung** (`reihen._schluessel` löst auf): Festlegen
  und Notiz über eine Buchung der alten Schreibweise gelten für die zusammengeführte Reihe, und
  Festlegen durch eine Buchung der einen oder der anderen Schreibweise ist dieselbe Festlegung.
- **`Reihen.nach_schluessel` findet eine Reihe auch unter einer zusammengeführten
  Schreibweise.** Sonst fände `reihe_des_teils` für die Teile der alten Schreibweise keine
  Reihe, und sie zählten im Rest ihrer Kategorie.
- **Ein Vorschlag ist eng.** Beide Reihen haben einen festen Takt und einen Betrag je Termin,
  stehen in derselben Kategorie und zahlen denselben Betrag (gleiches Vorzeichen, von beiden
  Seiten höchstens `reihe.TOLERANZ` entfernt); der erste Termin der neuen liegt einen Takt der
  alten nach deren letztem Termin (±25 %, höchstens bis die alte als beendet gilt). Zwei Reihen,
  die zugleich laufen, sind nie dieselbe Zahlung. Eine Reihe ist in höchstens einem Vorschlag
  die alte und in höchstens einem die neue. Dasselbe Paar in mehreren Kategorien steht einmal
  da. Das Ziel ist die neue Schreibweise.
- **Das Gehalt mit Monatskürzeln wird nicht vorgeschlagen,** aus zwei Gründen: Jede Schreibweise
  hat eine Buchung, also keinen festen Takt und keinen Betrag je Termin; und wo sie zwei haben
  (eine Schreibweise je Monat, zwei Jahre), liegen ihre Zeiträume ineinander. Ein Test je Fall.
- **„Gehört zu“ bietet jede Reihe derselben Kategorie,** auch eine mit einer Buchung, die keine
  Zeile hat: Eine neue Schreibweise, die noch keine Zeile hat, wählt man von der sichtbaren
  Reihe aus; die zusammengeführte Reihe heißt dann nach der neuen.
- **Die Teile einer zusammengeführten Reihe stehen nach Tag und Kennung,** nicht nach
  Schreibweise. Reihen ohne Zusammenführung bleiben, wie sie waren.
- **Regeln, Verträge und `ledger/reihe.py` bleiben bei `counterparty_norm`** (Plan), siehe
  „Gefundene Abweichungen“.

**Gemessen und verglichen (Entwicklungskopie).** Suite 1: 1779 bestanden, einer durchgefallen:
`test_referenz`, das ist `pruefen`. Suite 2 (Musterhaushalt) 1722 bestanden, Browsertests 39
bestanden, 4 übersprungen (wie vorher). `pruefen` zeigt **eine** Datei: `seiten/reihen.txt`,
einmal Zahlen und einmal Text. Hauptbuch, `ableitung/` und alle anderen Seiten sind gleich. Im
Neuaufbau gegen die Referenz fällt in `/reihen` keine Zeile weg, 2115 kommen dazu: der Hilfetext
„Zusammengeführt“, die Tabelle „Vorschläge“ und je Reihe die Auswahl „Gehört zu“ mit den Reihen
ihrer Kategorie. Das ist die Seite, die den Teilschritt trägt; der Plan hat sie bei „gleich ohne
Einträge“ nicht bedacht (wie in 4.3, wo `pruefen --nur-zahlen` die neue Seite zeigte). Die
Referenz schreibt Opus in einem eigenen Schritt neu, die Sitzung hat sie nicht angefasst.
`/reihen` hat in der Vorgabe 0,9 MB, mit „Alle“ 2,1 MB (vorher 0,6 und 1,0), lädt aber in
0,06 und 0,08 s.

Probiert auf einer Kopie des Datenordners im Scratchpad, mit Einträgen für Kfz-Steuer,
Rundfunkbeitrag und Mobilfunk, Neuaufbau mit `neu_bauen` gegen die Kopie ohne und mit Einträgen:
Seiten und Ableitungen ändern sich nur in der Kontoprognose, der Hochrechnung und dem, was aus
ihnen folgt (`/konten`, `/annahmen`, Prognosebasis, Treffer-Check, `/ziele`, `/hochrechnung`,
`/monatsabschluss`); Hauptbuch und Abgleich bleiben gleich. Je Fall: eine Jahreszahlung unter
zwei Schreibweisen zählt in der Hochrechnung einmal statt zweimal, und die Kontoprognose bucht
sie nicht mehr zusätzlich im ersten offenen Monat; ein Quartalsbeitrag unter zwei Schreibweisen
ist eine Quartalsreihe statt Quartalsreihe plus Jahresposten, ihr Termin folgt der letzten
Zahlung; ein Anbieter, dessen Schreibweisen der Reihe nach laufen, ist eine Reihe statt einer
laufenden und einer beendeten; drei Schreibweisen eines Anbieters, deren Zeiträume ineinander
liegen, wurden von Hand zusammengeführt und sind eine monatliche, inzwischen beendete Reihe statt
einer jährlichen Reihe, einer beendeten und einer unregelmäßigen.

**Abgenommen am 06.10.2026 (Opus).** `pruefen` nachgerechnet: nur `seiten/reihen.txt`, und dort
kommen nur Zeilen dazu, keine fällt weg. Das ist die Seite des Teilschritts; „gleich ohne
Einträge“ meinte die Zahlen der Vorschauen, und die sind gleich. Die Auslegungen gelten. Die
Seitengröße ist angenommen, solange `/reihen` unter 0,1 s lädt. Die Sitzung hat nicht committet;
committet und die Referenz neu geschrieben hat Opus. Eingetragen ist keine Zusammenführung: Welche
Schreibweisen zusammengehören, entscheidet der Haushalt auf `/reihen`, im Alltag.

### 4.6 Aufräumen (gleich)

- **Bestehende Datenordner nachführen:** Eine `taxonomy.yaml`, die nirgends `einmalig`
  trägt, bekommt das Merkmal an Kaufnebenkosten, bevor der echte Datenordner diesen Code
  sieht (Fund aus 4.3, bestehende Datenordner kennen `einmalig` nicht). Dazu die
  Spalte `mgmt_categories.einmalig` in einer Datenbank, die sie nicht hat: Ein Lauf
  dieses Checkouts ohne `FINCTL_DATEN` scheiterte zweimal an „no such column“.
  Bewiesen wird es an einer Kopie der Entwicklungskopie im Scratchpad, der Merkmal
  und Spalte genommen sind: Nach dem Nachführen ist `pruefen` gegen diese Kopie
  gleich. Der echte Datenordner wird dafür weder gelesen noch geschrieben.
- Die Einträge aus Schritt 2, die auf Schritt 4 zeigen
  (`docs/schritt2_fortschreibung.md`, „Gefundene Abweichungen“): ob
  `szenarien.messung`, `szenarien.vorschlaege`, `jahre._vertragsenden` und
  `jahre.verkaeufe` jetzt `messung.teile` nehmen; `round(c / monate * 12)` in
  `verkaeufe` über `verfahren.summe_aufs_jahr`; `Fortgeschrieben` trägt den Takt
  (erledigt in 4.4, nur vermerken). Jeder Eintrag bekommt „erledigt in 4.x“
  oder einen Grund.
- `ZU_VERZWEIGT` auf gemessene Werte.
- „Gefundene Abweichungen“ unten: jeder Eintrag mit Warum und Schritt.
- `docs/Neufassung_plan.md`: Schritt 4 als erledigt markieren, mit Datum und
  dem, was offen bleibt.

**Fertig wenn:** gleich.

**Umgesetzt am 06.10.2026.** Der Punkt zu `docs/Neufassung_plan.md` ist nicht Teil dieser
Sitzung (Opus). Das Nachführen steht in `finctl/nachfuehren.py`, drei Teile:

- **Die Spalte** legt `ledger.db.connect` an, die einzige Tür zum Hauptbuch (vier Aufrufer):
  Es ruft `_add_missing_columns`, bisher nur `init`. Ein zweiter Prozess, der die Spalte
  zwischen Nachsehen und `ALTER` anlegt, ist kein Fehler (`duplicate column name` wird
  geschluckt, alles andere nicht). Gemessen: 0,08 ms je Verbindung mehr.
- **Das Merkmal** setzt `nachfuehren.taxonomie` in `taxonomy.yaml`: Nennt kein Knoten der
  Verwaltungskategorien `einmalig` (am Ast oder am Kind, ein Wort im Kommentar zählt nicht,
  `einmalig: false` ist eine Nennung und bleibt), bekommt `immobilie/kaufnebenkosten` es.
  Als Text eingefügt, nicht neu geschrieben: Die Datei trägt ihre Begründungen in Kommentaren.
  Die Stelle kommt aus dem Knotenbaum (`yaml.compose`), der Text wird vor dem Schreiben noch
  einmal gelesen und muss die Kategorie mit dem Merkmal ergeben. Gekonnt sind
  `{name: X, ...}` und der nackte Name; jede andere Form bleibt unverändert und wird
  gemeldet („bitte von Hand eintragen“).
- **Das Neuladen** macht `nachfuehren.daten`: Nennt die Taxonomie das Merkmal als wahr und hat
  die Datenbank keine Zeile damit, lädt es die Kategorien (`load_into_db`, wie `update`).
  Ohne das stünde der Block `einmalig` bis zum nächsten Update leer da, und Hochrechnung,
  Ziele und Treffer-Check zählten die Kaufnebenkosten wieder mit.

Aufgerufen wird es dort, wo ein Datenordner zum ersten Mal mit neuem Code zusammentrifft:
`finctl init` (`taxonomie`, im Bericht und in der JSON-Ausgabe als `nachgefuehrt`), jeder
Befehl, der das Hauptbuch braucht (`_require_db`, auf stderr), und der Start der App
(`lifespan` in `web/server.py`, nicht beim Import: ein Import schreibt keine Datei). Das
Modul steht in `module.APP` (`tests/test_module.py` verlangt einen Platz für jede Datei).
`tests/test_nachfuehren.py` hält fest: jede Form der Zeile, Kommentar, Entscheidung und
zweiter Lauf; die Spalte, auch im Wettlauf; Hauptbuch und Taxonomie zusammen bis zum Block
`einmalig`; Neuladen nur, wo nötig; `init`, ein Befehl und der Start der App.

**Bewiesen an einer Kopie** der Entwicklungskopie im Scratchpad, der `einmalig` in
`taxonomy.yaml` und die Spalte genommen waren (der echte Datenordner wurde nicht gelesen und
nicht geschrieben):
- Vorher scheiterten `abgleich`, `treffer`, `jahre` und `reihen` an „no such column:
  m.einmalig“.
- `pruefen` gegen diese Kopie ist **gleich** (der Neuaufbau geht durch `init`, das das Merkmal
  nachträgt). Gegenprobe: derselbe Lauf mit dem Code von vor 4.6 (`git worktree` auf `47746a9`)
  zeigt 13 Unterschiede: Block `einmalig` leer, die Kaufnebenkosten stehen im Block `objekt`,
  dazu Abgleich, Prognosebasis, Treffer-Check, `mgmt_categories` und vier Seiten.
- Der Weg in die vorhandene Datenbank: nach einem Befehl auf der Kopie ist die Zeile in
  `taxonomy.yaml` byte-gleich der der Entwicklungskopie (`diff -r` über `config/` ohne
  Unterschied), die Spalte steht da, und `abgleich`, `treffer`, `jahre`, `reihen` und
  `status` (alle `--json`) sind byte-gleich denen der Entwicklungskopie. Eine zweite Kopie, die
  nur die App startet (`TestClient` mit `with`): `/hochrechnung`, `/ziele`, `/monatsabschluss`,
  `/konten`, `/annahmen` und `/reihen` sind Byte für Byte die Seiten der Entwicklungskopie.

**Die Einträge aus Schritt 2** (`docs/schritt2_fortschreibung.md`, jeder mit „Erledigt in“
oder Grund): `Fortgeschrieben` trägt den Takt (erledigt in 4.4, nur vermerkt); das Gehalt als
Reihe (entschieden in Schritt 4, Entscheidung 11: bleibt beim Median);
`szenarien.messung`, `szenarien.vorschlaege`, `jahre._vertragsenden` und `jahre.verkaeufe`
**bleiben bei ihren Abfragen**: Sie wählen nach Identität (Kennungen, Kategorie und Konto,
Objekt), `messung.teile` kennt nur das Ausschließen von Kennungen; es zu nehmen hieße drei
Parameter dazuzugeben und vier Aufrufer zu ändern, ohne dass sich eine Zahl bewegt.
`verkaeufe` rechnet Miete und Kosten jetzt über `verfahren.summe_aufs_jahr` (dieselbe
Formel), ebenso die Anzeige des Rests in `jahre._gemessen_text`.

**`ZU_VERZWEIGT`** steht schon auf den gemessenen Werten: `ruff --select C901` findet dieselben
19 Funktionen mit denselben Werten, keine ist unter die Schwelle gefallen, keine neu dazugekommen
(`cli.init` bleibt bei 16: das Nachführen sind zwei Zeilen ohne Verzweigung). Nichts zu ändern.

**Abgenommen am 06.10.2026 (Opus).** Gleich, auch gegen die Kopie ohne Merkmal und Spalte,
und die Gegenprobe mit dem alten Code ist rot: Das Nachführen beweist, was es soll. Geprüft
auch gegen den Arbeitsbaum `basis`: Er schreibt `mgmt_categories` mit benannten Spalten, eine
Spalte mehr stört ihn nicht. Geändert bei der Abnahme: `taxonomie` schreibt über
`dateien.schreiben_wenn_geaendert`, wie jede Datei in `config/`. Den Punkt zu
`docs/Neufassung_plan.md` hat Opus gemacht, mit dem Satz unter „Umstieg“. Damit ist Schritt 4
erledigt.

**„Gefundene Abweichungen“:** Alle 42 Einträge haben jetzt „Warum“ und „Schritt“. Von den 37
vorhandenen fehlte bei 22 das Warum und bei 3 der Schritt; acht, die auf einen Teilschritt zeigten, der inzwischen kam, tragen jetzt
„Erledigt in“ (4.2c, 4.3, 4.5, 4.5b, 4.6), und fünf Einträge sind neu aus 4.6. Wo ein Eintrag
auf einen späteren Schritt der Neufassung zeigt, steht er da: Schritt 6 (die Größe von
`/reihen`, der Server baut das HTML; `/kategorien` nach dem Glossar), Schritt 8 (die
Schalterdatei der Module), die Umstellung des echten Datenordners nach Schritt 5; kein Schritt
der Neufassung ist für den Importer vorgesehen (Zerfall der Gegenpartei).

**Gemessen und verglichen (Entwicklungskopie).** Suite 1: 1799 bestanden, 46 übersprungen (darunter
`test_referenz`, das ist `pruefen`: gleich). Suite 2 (Musterhaushalt): 1741 bestanden, 60
übersprungen. Browsertests: 39 bestanden, 4 übersprungen (wie vorher). `pruefen` gegen die
Entwicklungskopie: **gleich**, ebenso gegen die Kopie ohne Merkmal und Spalte. Die Referenz ist nicht
angefasst. Seitenzeiten, zweiter Aufruf, vorher (4.5) und nachher: `/ziele` 0,07 s und 0,07 s,
`/hochrechnung` 0,12 s und 0,13 s, `/konten` 0,19 s und 0,19 s, `/monatsabschluss` 0,34 s und 0,33 s,
`/annahmen` 0,50 s und 0,49 s. Der erste Gesamtlauf der Suite zeigte 19 rote Tests; zwei Ursachen,
beide behoben: Das neue Modul stand in keinem Modul (`test_module`), und mein `init`-Test schaltete über
`module.erststart` die Module der Testkopie aus (siehe „Gefundene Abweichungen“), was 17 Tests auf
demselben Arbeitsprozess rot machte.

## Wo ein stärkeres Modell sich lohnt

- **Nach 4.2:** die Ausgabe von `finctl reihen` gegen die Entwicklungskopie
  lesen. Falsch erkannte Reihen ändern die Konstanten aus Entscheidung 3,
  bevor 4.4 sie in Zahlen gießt.
- **Nach 4.4 und 4.5:** Review des Diffs von `pruefen`, dann schreibt Opus die
  Referenz neu.

## Auftrag für eine Sitzung (Vorlage)

> Setze Teilschritt 4.N aus `docs/schritt4_reihe_takt.md` um. Lies vorher
> `CLAUDE.md`, `CONTEXT.md` und den ganzen Plan, besonders die
> Entscheidungen. Arbeite mit `FINCTL_DATEN` auf der Entwicklungskopie.
> Fertig ist der Teilschritt, wie er es dort sagt. Starte `pruefen` erst,
> wenn du keine Datei mehr änderst. Schreib die Referenz nicht neu. Für einen
> Vorher-Stand nutze nur `pruefen` oder `neu_bauen`. Bleibt ein Gleich-Schritt
> rot oder zeigt ein Gewollt-Schritt Unterschiede außerhalb seiner Seiten, hör
> auf und berichte. Committe nur die Dateien dieses Teilschritts.

## Gefundene Abweichungen

Hier tragen die Sitzungen ein, was ihnen auffällt und nicht in ihren
Teilschritt gehört: wo, was, ob es eine Zahl ändern würde, warum, und welcher
Schritt es anfassen muss.

- **4.1, Entscheidung 14 sagt nichts zu einer frisch geschriebenen Datei:** Der
  Schlüssel `(st_mtime_ns, st_size)` genügt nicht, wenn zwei Schreibvorgänge
  gleicher Länge innerhalb der Auflösung der Dateizeit liegen (Linux: einige
  Millisekunden); dann sähe der zweite Lesende den Inhalt des ersten. Deshalb
  kommt eine Datei, die vor weniger als `FRIST_NS` (2 s) geändert wurde, nicht
  in den Speicher. Ändert keine Zahl und kostet nur Zeit, solange eine Datei
  jung ist (der Server liest sie bis dahin je Aufruf wie vorher). **Warum:**
  Ein Test, der eine Datei zweimal in schneller Folge schreibt, hätte sonst
  gelegentlich den alten Inhalt gesehen. **Schritt:** keiner; wer die Frist
  verkürzen will, ändert eine Konstante in `finctl/dateien.py`.
- **4.1, der Speicher gilt je Prozess:** Das laufende Dashboard behält gelesene
  Dateien über Aufrufe hinweg und sieht eine Änderung von Hand am nächsten
  Aufruf (die Dateizeit ändert sich). Eine Datei, die ein Programm ändert und
  dabei Größe und Dateizeit erhält, bliebe unbemerkt; das tut kein Editor.
  **Warum:** Der Speicher ist der Preis dafür, dass `/konten` und `/monatsabschluss` jede
  Datei einmal statt hundertfach lesen (Entscheidung 14); ein Speicher, der bei jedem Aufruf
  die Datei prüfte, wäre keiner. **Schritt:** keiner.
- **4.1, offene Lesestellen:** `safe_load(pfad.read_text())` steht noch in
  `ingest/`, `rules/`, `tax/taxonomy.py`, `cli.py`, `web/auth.py` und
  `web/routen/einrichtung.py`. Sie laufen nicht je Konto oder je Kategorie und
  tauchten im Profil von `/konten` und `/monatsabschluss` nicht auf (die Regeln
  und die Taxonomie liest der Importer einmal je Lauf). Ändert keine Zahl.
  **Warum:** Entscheidung 14 stellt nur um, was auf den beiden Seiten mehrfach liest; die
  übrigen Stellen kosten nichts, das sich messen ließe. **Schritt:** keiner; wer sie umstellt,
  ändert eine Zeile je Stelle.
- **4.2, Entscheidung 4: Termine vor einer dauerhaften Änderung des Betrags sind
  „Ausreißer“.** Ändert sich der Betrag je Termin um mehr als 25 %, weichen
  alle Termine davor von dem neuen Betrag ab und kämen in 4.4 in den Rest ihrer
  Kategorie: Die Reihe zählt den neuen Betrag mal 12/t, und der Rest zählt die
  alten Monate dazu. Auf der Entwicklungskopie betrifft das einen Dauerauftrag
  (10 von 12 Terminen des Fensters) und Kreditzinsen mit sinkendem Betrag (7).
  Das ändert Zahlen, sobald 4.4 rechnet. **Vorschlag für 4.4:** Ausreißer sind
  nur abweichende Termine nach dem ersten Termin der Höhe, die gilt; was davor
  liegt, ist der Verlauf der Reihe, gehört weder zum Takt noch zum Rest.
  **Warum:** Entscheidung 4 ging von einer Höhe aus, die über 24 Monate gleich bleibt; ein
  Dauerauftrag mit neuem Betrag ist dort „Rauschen“.
  **Schritt:** Entscheidung vor 4.4. **Erledigt in 4.2b.**
- **4.2, Entscheidung 3: ein Jahrestermin darf beliebig viele Buchungen
  schlucken.** Bei t = 12 genügen zwei Termine, und ein Termin legt alles
  zusammen, was weniger als ein halbes Jahr nach seiner ersten Buchung liegt.
  Unregelmäßige Ausgaben (Tanken, Nebeneinkommen) in zwei Jahren mit
  ähnlicher Halbjahressumme sind damit „jährlich“, mit der Summe eines
  Halbjahrs als Jahreswert (Entwicklungskopie: sieben Buchungen Kraftstoff, vier
  Buchungen Nebeneinkommen). Auch ein Gehalt, von dem das
  Hauptbuch nur das vierte Quartal je Jahr kennt. **Vorschlag:** höchstens drei
  Buchungen je Termin bei t = 12 (Raten einer Prämie), sonst kein Jahrestermin.
  **Warum:** Wortlaut von Entscheidung 3: Ein Termin legt alles zusammen, was weniger als
  einen halben Takt nach seiner ersten Buchung liegt, und bei t = 12 sind das sechs Monate.
  **Schritt:** vor 4.4. **Erledigt in 4.2b** (drei Buchungstage, ab Takt 2).
- **4.2, Entscheidung 3: der Betragstest gilt über 24 Monate.** Eine Preis- oder
  Tarifänderung vor mehr als einem Jahr drückt den Anteil gleicher Beträge unter
  75 %, die Reihe wird unregelmäßig und fehlt (Entwicklungskopie: ein
  Internetvertrag, 15 von 23 Buchungen auf dem neuen Preis; Mobilfunk mit
  Zusatzbuchungen beim selben Anbieter). Ändert keine Zahl gegenüber heute (der
  Rest rechnet wie bisher), nimmt aber der Reihe die Vorteile aus Entscheidung 5.
  **Vorschlag:** Beträge nur über die letzten zwölf Monate prüfen.
  **Warum:** Wortlaut von Entscheidung 3 („drei Viertel aller Termine der 24 Monate“).
  **Schritt:** vor 4.4. **Erledigt in 4.2b** (statt zwölf Monaten: ab der geltenden Höhe).
- **4.2, Entscheidung 1: zwei verschiedene Beträge je Monat unter einer Reihe.**
  Ein Abschlag und eine Gebühr beim selben Empfänger in derselben Kategorie
  (52 Buchungen, zwei je Monat am selben Tag): bei t = 1 scheitern Abstände und
  Beträge, ab t = 2 legt das Zusammenlegen die Monate ungleichmäßig zu Paaren
  zusammen. Die Reihe bleibt unregelmäßig und rechnet im Rest wie heute.
  **Warum:** Entscheidung 3 legte Buchungen erst ab t = 2 zusammen, bei t = 1 war jede
  Buchung ein Termin. **Schritt:** keiner, oder 4.3 als Handentscheidung; ein Zusammenlegen
  gleichzeitiger Buchungen schon bei t = 1 wäre eine Änderung von Entscheidung 3.
  **Erledigt in 4.2b** (Entscheidung 3 geändert: Buchungen am selben Tag sind
  ein Termin).
- **4.2, Entscheidung 3: „halber Takt“ bei t = 2 ist ein Monat.** Buchungen im
  Monatsabstand (30 bis 31 Tage) liegen je nach Monatslänge knapp über oder
  unter 30,4 Tagen und werden ungleichmäßig zusammengelegt. Betrifft nur t = 2:
  eine Reihe, deren Buchungen abwechselnd am Monatsersten und am Monatsletzten
  liegen (Abstände 1 und 60 Tage), wird „alle 2 Monate“ mit richtigem
  Jahreswert, aber falschem Namen; ein von Hand auf 2 gesetzter Takt für
  monatliche Buchungen bildet acht statt sechs Termine. **Warum:** Der halbe Takt ist bei
  t = 2 ein Monat, und ein Monat ist kein fester Abstand in Tagen. **Schritt:** keiner; 4.3
  zeigt den Namen (erledigt: `/reihen` nennt den Takt je Reihe), die Zahl stimmt.
- **4.2, Entscheidung 1: die Gegenpartei zerfällt.** `counterparty_norm` trägt
  bei manchen Zahlern Referenznummern oder ein Stichwort aus dem Verwendungszweck.
  Auf der Entwicklungskopie stehen sechs Buchungen am selben Tag mit gleichem
  Betrag in einer Fixkosten-Kategorie unter sechs Gegenparteien: sechs „jährliche“
  Reihen statt einer monatlichen. Dieselbe Hausverwaltung unter zwei Schreibweisen
  gibt eine beendete und eine laufende Reihe, im Betrag richtig. Das ist die
  Definition der Reihe, nicht der Takt. **Warum:** Der Importer schreibt die Gegenpartei so,
  wie die Bank sie liefert; ein Umbau schöbe Regeln und Handentscheidungen, die an
  `counterparty_norm` hängen. **Schritt:** keiner in Schritt 4, und kein Schritt der
  Neufassung ist dafür vorgesehen; wer es ändert, ändert `counterparty_norm` im Importer.
  **Gemildert in 4.5b:** Der Haushalt führt Schreibweisen für die Vorschauen auf `/reihen`
  zusammen.
- **4.2, Entscheidung 3: die Ausnahme für Fixkosten macht eine Anschaffung zur
  Jahreszahlung.** Ein Gerät in einer Abo-Kategorie ist eine Reihe mit einem
  Termin und zählt als jährlich, wie der Jahresposten der Kontoprognose heute. In
  der Hochrechnung zählt es heute einmal in der Summe des Fensters, später als
  Jahreswert; gleich, solange es im Fenster liegt. **Warum:** Aus einem Termin lässt sich eine
  Anschaffung nicht von einer Jahreszahlung unterscheiden; nur der Haushalt weiß es.
  **Schritt:** 4.3 (Einmalig setzen), nicht Erkennung. **Erledigt in 4.3:** Der Haushalt setzt
  die Buchung auf `/reihen` einmalig.
- **4.2b, Entscheidung 3 und 4: eine Erhöhung vor zwei Terminen macht die Reihe für
  zwei Monate unregelmäßig.** Ab der geltenden Höhe verlangt die Erkennung drei
  Termine (zwei bei t = 12); nach einer Erhöhung um mehr als 25 % hat die neue
  Höhe erst nach dem dritten Termin so viele. Bis dahin rechnet die Reihe im Rest
  wie heute (Summe des Fensters), danach mit dem neuen Betrag je Termin; ein
  festgelegter Takt hat den neuen Betrag sofort. Auf der Entwicklungskopie trifft
  es einen Dauerauftrag mit zwei Terminen am neuen Betrag nach fünfzehn am alten.
  Vorher war er „monatlich“ mit zehn Ausreißern. **Warum:** Wortlaut von
  Entscheidung 3 („genug Termine“ ab der geltenden Höhe). **Schritt:** vor 4.4
  entscheiden: bei t ≤ 2 zwei Termine ab der Höhe genügen lassen, wenn der Rest
  der Reihe davor mindestens drei Termine hatte, oder es bei der Wartezeit lassen.
  **Erledigt in 4.2c** (`MIN_TERMINE_HOEHE = 2`: zwei Termine ab der Höhe genügen).
- **4.2b, Entscheidung 3: eine Prämie in drei Raten an aufeinanderfolgenden
  Monaten ist „monatlich“,** nicht „jährlich“: Bei zwei Jahren (sechs Buchungen)
  passen vier von fünf Abständen zum Monat. Nach dem letzten Termin des Jahres gilt
  sie als beendet, ihr Jahreswert ist dann null statt der Summe der drei Raten. Das
  war vor 4.2b so und ändert 4.2b nicht; Raten im Abstand von zwei Wochen werden
  „jährlich“. **Schritt:** vor 4.4: ein Abstand-Test, der Lücken im Jahr
  berücksichtigt (ein Abstand über 4 Monate bricht die Regelmäßigkeit), oder 4.3
  als Handentscheidung. **Warum:** Der Abstandstest prüft Abstände, nicht, wie viel des
  Zeitraums fehlt: Drei Raten in Folge sind zwei gute Abstände, der Rest des Jahres ist
  keiner. **Erledigt in 4.2c** (Bedingung „ohne Lücke“; Raten, die nur einmal beobachtet sind,
  bleiben „monatlich, beendet“, siehe die Abnahme von 4.2b).
- **4.2b, Entscheidung 4: schwankende Beträge verlieren ihren Verlauf.** Eine
  Reihe, die jeden Monat kommt, aber um mehr als 25 % schwankt (Gutschriften,
  Zinsen), bekommt als geltende Höhe nur das Ende, der Rest ist „Verlauf“ und
  zählt in 4.4 weder im Takt noch im Rest; liegt der letzte Termin außerhalb der
  Toleranz, ist er ein Ausreißer und die Reihe nach 1,5 Takten „beendet“, obwohl
  sie weiterläuft. Auf der Entwicklungskopie: eine Gutschrift mit acht Monaten,
  die von „alle zwei Monate, läuft“ zu „monatlich, beendet“ mit null wird.
  **Warum:** Entscheidung 4 geht von Stufen aus, nicht von Rauschen.
  **Schritt:** vor 4.4: nur Termine als Verlauf zählen, wenn sie unter dem Betrag
  liegen, auf den eine Stufe folgt (zwei Termine in Folge innerhalb der Toleranz
  vor dem ersten Termin der Höhe), oder Ausreißer am Ende nicht als Beendigung
  lesen. **Erledigt in 4.2c** (Ausreißer nur, wer zusätzlich kommt; der Verlauf
  bleibt, wie er war).
- **4.2c, Entscheidung 3: ein Jahrestermin mit einem Termin ab der Höhe nimmt
  jede zweite Buchung im Abstand von neun bis fünfzehn Monaten.** Bei t = 12
  genügt seit 4.2c ein Termin ab der geltenden Höhe, und der Abstand darf um 25 %
  von einem Jahr abweichen. Zwei Einkäufe beim selben Händler in derselben
  Kategorie, ein Jahr (± drei Monate) auseinander und mit verschiedenem Betrag,
  sind damit eine jährliche Reihe mit dem letzten Betrag als Jahreswert und dem
  ersten im Verlauf. Auf der Entwicklungskopie sind 12 Reihen neu jährlich:
  einige echt (Versicherungsbeitrag mit neuem Preis), die meisten Zufall
  (Supermarkt, Veranstaltung, Spiel, Möbel, Wertpapierkauf, Arzt). In 4.4
  verschwände ihr Verlauf aus der Rechnung, und sie zählten einmal im Jahr statt
  mit der Summe ihres Fensters. **Warum:** Wortlaut von 4.2c. **Schritt:** vor 4.4
  entscheiden: bei t = 12 weiter zwei Termine ab der Höhe verlangen, außer in einer
  Kategorie mit Fixkosten-Merkmal; oder den Abstand bei t = 12 enger fassen.
  **Erledigt in der Abnahme von 4.2c** (erste Variante, „geändert nach 4.2c“ in
  Entscheidung 3).
- **4.2c, Entscheidung 4: „näher als einen halben Takt“ kennt nur vorhandene
  Termine.** Eine Erstattung mit anderem Vorzeichen, die drei Wochen nach der
  Monatsrate und eine Woche vor der nächsten kommt, ist weder nah an einem
  Termin (22 Tage) noch am erwarteten nächsten (der noch nicht existiert) und gilt
  als Termin des Takts mit anderem Betrag: Sie fehlt im Rest und wird in 4.4
  nirgends gezählt. Auf der Entwicklungskopie trifft es die Erstattung einer
  Krankenversicherung im letzten Monat und hat den „letzten Termin“ der Reihe vom
  Monatsersten auf den 23. verschoben. **Warum:** Entscheidung 4 misst nur an
  passenden Terminen. **Schritt:** vor 4.4: ein Termin mit anderem Vorzeichen ist
  immer ein Ausreißer, oder die Nähe misst auch an der erwarteten Stelle (letzter
  passender Termin plus Takt). **Erledigt in der Abnahme von 4.2c** (erste Variante,
  „geändert nach 4.2c“ in Entscheidung 4).
- **4.3, bestehende Datenordner kennen `einmalig` nicht:** Die Startvorlage
  `vorgaben/taxonomy.yaml` wird nur kopiert, wo `config/taxonomy.yaml` fehlt
  (`vorgaben.sicherstellen`). Ein Datenordner, der schon eine hat, bekommt das Merkmal
  an Kaufnebenkosten nicht: Der Block `einmalig` bliebe leer, die Kaufraten zählten in
  „Immobilienkosten“, und Zahlen von Hochrechnung, Ziele und Treffer-Check änderten sich
  ohne Hinweis. Auf der Entwicklungskopie steht die Zeile von Hand
  (`kaufnebenkosten: {name: Kaufnebenkosten, einmalig: true}`); der Musterhaushalt holt
  sie sich aus der Startvorlage. **Warum:** Der Plan sagt „die mitgelieferte Taxonomie
  gibt Kaufnebenkosten das Merkmal“, das erreicht nur neue Einrichtungen. **Schritt:**
  vor dem ersten Alltagsstart mit diesem Code: den echten Datenordner nachziehen, oder
  eine Migration, die einer `taxonomy.yaml` ohne ein einziges `einmalig` das Merkmal an
  Kaufnebenkosten gibt (Schritt 5 fasst den Datenordner ohnehin an).
  **Erledigt in 4.6** (`finctl/nachfuehren.py`, siehe dort). Der Umstieg des echten
  Datenordners (Neufassung, „Umstieg“) braucht dafür keinen eigenen Schritt: Das Nachführen
  läuft beim ersten Befehl und beim Start der App von selbst.
- **4.3, Umbenennen auf /kategorien verliert die Merkmale einer Kategorie:**
  `taxonomy.save_custom` schreibt ein umbenanntes Kind als nackten Namen, und
  `load_spec` ersetzt damit den ganzen Eintrag aus `taxonomy.yaml`: `fix: true` und
  seit 4.3 `einmalig: true` sind danach weg. Gesehen mit einer erfundenen Vorlage; die
  Seite hat es nicht gezeigt. Ändert Zahlen, sobald jemand eine Kategorie mit Merkmal
  umbenennt (Fixkosten fallen in „Konsum“, Kaufraten in „Immobilienkosten“).
  **Warum:** `load_spec` legt die Einträge aus `taxonomy_custom.yaml` mit `children.update`
  über die der `taxonomy.yaml`, und `save_custom` schreibt ein umbenanntes Kind als nackten
  Namen: Der ganze Eintrag samt Merkmalen wird ersetzt. **Schritt:** keiner der Schritte 4, in
  4.6 nicht angefasst (kein Teil des Aufräumens; eine Änderung an der Seite brächte
  Browsertests mit). Ein eigener Gleich-Schritt vor dem Umstieg des echten Datenordners
  (Neufassung, nach Schritt 5), am besten vor Schritt 6, der `/kategorien` ohnehin nach dem
  Glossar umschreibt: `save_custom` schreibt `{name: …}` und lässt die Merkmale stehen, mit
  einem Test je Merkmal. Bis dahin: eine Kategorie mit Merkmal auf `/kategorien` nicht
  umbenennen.
- **4.3, `/reihen` ist groß:** Jede Zeile trägt ihr Panel mit den Terminen: 0,6 MB in der
  Vorgabe, 1,0 MB mit „Alle“, auf der Entwicklungskopie. Es lädt in 0,06 s und rendert
  flott; mit mehr Reihen wächst es linear. **Warum:** Das Panel einer Reihe (Termine, Auswahl)
  steht im HTML jeder Zeile, damit „Öffnen“ kein Skript braucht, das rechnet (Regel 5).
  **Schritt:** 6 („Der Server baut das HTML“) kann
  das Panel beim Öffnen nachladen.
- **4.3, `pruefen --nur-zahlen` blieb bei diesem Schritt rot, ohne dass sich eine Zahl
  ändert:** Die Referenz hält mehr fest als den Text der Seiten. Gegen die Referenz vom
  02.10.2026 zeigt `pruefen --nur-zahlen` acht Unterschiede: (1) `hauptbuch/mgmt_categories.json`
  (neue Spalte `einmalig` in jeder der 110 Zeilen, die Zeile mit 1 sortiert anders),
  (2) vier Dateien in `ableitung/` (Abgleich, Basis, Jahre, Prognosebasis), in denen der
  Block vorher `sondereffekt` hieß: Schlüssel, Etikett, `where` und Platz in der Liste,
  (3) die **Reihenfolge** der Zahlen auf `/hochrechnung` (Rechenweg: die Gruppe „Einmalig“
  steht jetzt vor „Gehalt“) und `/planung` (Abgleich: die Zeile „Einmalig“ steht vor
  „Gehalt“), und (4) die neue Seite `/reihen`. Rechnet man die Umbenennung auf der alten
  Referenz nach (`sondereffekt` zu `einmalig`, Etikett, die Spalte, Reihenfolge nach
  Kennung), sind alle fünf Dateien und alle 41 Seiten gleich: Zeilen als Mehrfachmenge
  verglichen, bleibt nur die eine Zeile „Reihen“ in der Navigation. Der Text unterscheidet
  sich auf 35 Seiten: 33 nur durch diese Zeile, `/annahmen` und `/prognosebasis` dazu
  durch die Kennung (`sondereffekt` zu `einmalig`), `/hochrechnung` und `/planung` durch
  das Etikett „Einmalig“ an neuer Stelle. **Warum:** Der Plan sagt, die Zahlen blieben
  gleich und der Text ändere sich nur im Namen. Die Dumps der Referenz lesen jede Spalte
  der Tabelle und jeden Blockschlüssel; ein neues Merkmal und ein umbenannter Block
  bleiben dort nicht unsichtbar. Dass der Block „an erster Stelle“ steht (Entscheidung
  9), ordnet zugleich die Anzeige um, weil Abgleich und Rechenweg dieselbe Liste
  (`abgleich.bloecke`) lesen. **Schritt:** keiner; **entschieden (Opus, 05.10.2026): (b).** `_case_expression`
  wertet `einmalig` zuerst aus (`Block.zuerst`), `bloecke()` zeigt es an der alten Stelle
  der Sondereffekte, nach „Gehalt“; ein Test hält beides fest. Damit zeigt `pruefen
  --nur-zahlen` genau die fünf Dateien und die neue Seite. Die Referenz schreibt Opus neu.
  Zur Wahl standen
  (a) so lassen und die Referenz in einem eigenen Schritt neu schreiben wie nach
  4.4 und 4.5; (b) die Anzeige in der alten Reihenfolge halten, indem die Reihenfolge
  der Auswertung (`_case_expression`: Einmalig zuerst) von der der Anzeige (`bloecke()`)
  getrennt wird: dann bleiben `/hochrechnung` und `/planung` in den Zahlen gleich, die
  fünf Dateien nicht; (c) `tests/referenz.py` bekommt eine Umbenennungstabelle für
  Dateien außerhalb der Seiten. (b) und (c) ändern, wie die Sicherung gemessen wird oder
  was Entscheidung 9 sagt.
- **4.4, die Zeit von `/annahmen` wächst, die von `/monatsabschluss` kaum:** Der Treffer-Check
  baut für jeden seiner sechs Monate die Reihen zum Stichtag neu (rund 30 ms je Stichtag). Auf
  `/annahmen` steht er unter „Prognose gegen Ist“; auf `/monatsabschluss` nur der eine Monat
  der Hinweise. **Warum:** Entscheidung 12 verlangt die Basis zu diesem Stichtag. **Schritt:**
  6 („Der Server baut das HTML“), falls die Zeit stört; `takt.reihen` könnte die Teile für
  alle sechs Stichtage einmal lesen.
- **4.4, `abgleich` und die Kontoprognose bleiben:** `ableitung/abgleich.json`, `/konten` und der
  Konten-Teil des Treffer-Checks ändern sich nicht; sie messen Gebuchtes oder rechnen noch nach
  dem alten Weg (4.5). **Warum:** Der Abgleich fragt, was gebucht wurde, und dafür gibt es
  keinen Takt; die Kontoprognose war der Gegenstand von 4.5. **Schritt:** **Erledigt in 4.5**
  für die Kontoprognose; der Abgleich bleibt, wie er ist.
- **4.4, eine einzelne Gutschrift in einer Fixkosten-Kategorie zählt jährlich:** Die Ausnahme
  aus 4.2 („genau ein Termin in einer Fixkosten-Kategorie ist jährlich“) schreibt jetzt auch
  eine einmalige Einnahme (der Verkauf eines Geräts in einer Abo-Kategorie) als Jahreswert
  fort, solange sie im Zeitraum von eineinhalb Jahren liegt. **Warum:** Wortlaut von
  Entscheidung 3. **Schritt:** keiner; der Haushalt setzt sie auf `/reihen` einmalig.
- **4.4, zwei Schreibweisen derselben Zahlung zählen doppelt:** Eine Jahreszahlung, deren
  Gegenpartei sich von Jahr zu Jahr anders schreibt (ein Verwendungszweck mit Jahr, eine
  Referenz), sind zwei Reihen mit je einem Termin. Beide laufen anderthalb Jahre, und die
  Hochrechnung zählt beide: Auf der Entwicklungskopie verdoppelt sich so eine Steuer von 72 auf
  144 Euro im Jahr, ihr Termin vor 13 Monaten lag vorher außerhalb des Fensters. **Warum:**
  Die Gegenpartei zerfällt (4.2, „Zerfallene Gegenparteien“); mit dem Takt wirkt es auf eine
  Zahl, solange die ältere Reihe läuft. **Schritt:** eine Frage des Importers
  (`counterparty_norm`); bis dahin legt der Haushalt eine der Reihen auf `/reihen` als
  `unregelmaessig` fest.
- **4.4, Block `kredit` in der Basis:** Die Basis führt auch Blöcke, die `rechnen` nicht liest
  (`kredit`, `gehalt`, `objekt`). Reihen gelten dort wie überall; ein beendeter Kredit
  (Rückzahlung) steht mit null. Keine Zahl der Rechnung ändert das, die Anzeige schon.
  **Warum:** `abgleich.bloecke` ist eine Liste für Anzeige und Basis zugleich, und der Takt
  gilt für jede Kategorie, nicht je Block. **Schritt:** keiner; ein Kredit rechnet weiter
  nach seinem Tilgungsplan (Entscheidung 11).
- **4.5, brutto statt netto: eine Kosten- und eine Einnahmenreihe derselben Kategorie.** Die Miete
  und der Anteil eines Mitzahlers standen im Median der Kategorie als ein Posten mit dem Saldo,
  am 1. Jetzt sind es zwei Reihen: die Kosten am 1., die Einnahme am 28. (Entscheidung 6: „der Tag
  im Monat bleibt“). Der Tiefpunkt sinkt damit in jedem Monat um den Einnahmenanteil, auf dem
  Betriebskonto der Entwicklungskopie um rund ein Tausender, und eine Unterschreitung der Grenze
  erscheint, wo keine war. Die Summe ueber den Monat aendert das nicht. Auf den echten Daten
  faellt deshalb `test_the_ceiling_leaves_room_for_a_median_month` (Deckel gegen den Median der
  Monatskosten: die Kosten sind jetzt brutto). **Warum:** Wortlaut von Entscheidung 6.
  **Schritt:** keiner, entschieden bei der Abnahme von 4.5: Brutto bleibt, denn die Senke ist echt
  (Kosten am Monatsanfang, Anteil und Gehalt am Monatsende). Verrechnen verbirgt sie, und ein
  Buchungstag je Reihe aenderte hier nichts an der Reihenfolge. Den Deckel stellt der Haushalt.
- **4.5, zerfallene Gegenparteien zaehlen doppelt oder gar falsch.** Dieselbe Zahlung unter zwei
  Schreibweisen ist zwei Reihen: Die Kfz-Steuer steht im ersten offenen Monat (die alte Schreibweise
  laeuft noch, ihr Termin ist ueberfaellig) und ein zweites Mal zu ihrem Termin; der
  Rundfunkbeitrag quartalsweise und zusaetzlich einmal jaehrlich. Im Gehalt sind es drei
  Monatsgehaelter im Herbst, die unter dem Namen ohne Monatskuerzel stehen: eine jaehrliche Reihe
  mit der Summe von drei Monaten. Sie waere im Oktober zweimal das Gehalt gewesen und steht auf
  `/konten` wegen der Ausnahme fuer den Gehaltsfloor nicht als Posten da; `/reihen` zeigt sie
  weiter. **Warum:** Die Gegenpartei zerfaellt (4.2, 4.4). **Schritt:** 4.5b. **Erledigt in 4.5b**
  als Handentscheidung: Welche Schreibweisen zusammengehoeren, sagt der Haushalt auf
  `/reihen` (Vorschlaege dort); eingetragen ist noch keine, bis er es tut.
- **4.5, eine einzelne Gutschrift in einer Fixkosten-Kategorie ist eine Jahreseinnahme.** Der
  Verkauf eines Geraets in der Kategorie der Mobilfunkvertraege kommt im November als Einnahme
  (am 28., nach den Kosten) zurueck, solange er im Fenster von 24 Monaten liegt. Fuer eine
  Dispo-Warnung ist das die falsche Richtung. **Warum:** Wortlaut der Ausnahme in Entscheidung 3
  (4.4 hat denselben Fall fuer die Hochrechnung gefunden). **Schritt:** keiner; der Haushalt setzt
  die Buchung auf `/reihen` einmalig.
- **4.5, der Termin einer Praemie in Raten ist jetzt die erste Rate.** Der Jahresposten ankerte am
  Monat der letzten Rate, die Reihe am Tag der ersten Buchung des Termins: Eine Praemie in zwei
  Raten (Januar und Februar) steht im Folgejahr im Januar statt im Februar. Fuer die Senke der
  harmlosere Fehler. **Warum:** Entscheidung 3 legt Raten zu einem Termin zusammen, der mit
  der ersten Buchung beginnt; einen Anker an der letzten Rate gibt es dort nicht mehr.
  **Schritt:** keiner.
- **4.5, Teile ohne Gegenpartei und Einnahmen im Rest.** Fixkosten rechneten als Median oder als
  Jahresposten, wie viele Buchungen auch dahinter standen. Teile ohne Gegenpartei gehoeren zu keiner
  Reihe (Entscheidung 1) und zaehlen jetzt im Rest nach dem Vorzeichen: Kosten im Schnitt, Einnahmen
  im Median mit Mindestzahl. Eine Einnahme, die nur einmal oder von mehreren Absendern je einmal
  kam, faellt damit heraus (eine seltene Gutschrift ist kein Einkommen, auf das eine Warnung bauen
  darf); vorher stand sie als Jahresposten da. **Warum:** Mit Entscheidung 6 hat die Kontoprognose
  nur noch den Rest und die Reihen; der Jahresposten, der solche Einzelfaelle auffing,
  entfaellt. **Schritt:** keiner.
- **4.5, eine beendete Reihe nimmt ihre Ausreisser mit.** Ein einzelner Betrag, der neben den
  Terminen einer beendeten Reihe liegt (etwa eine Jahresgebuehr beim selben Anbieter, dessen
  Monatsabo gekuendigt ist), zaehlt weder im Takt noch im Rest, auch nicht als Jahresposten wie
  vorher. **Warum:** Eine beendete Reihe wird nicht fortgeschrieben, auch nicht im Rest (4.4,
  derselbe Satz). **Schritt:** keiner; was wiederkommen soll, legt der Haushalt auf `/reihen`
  fest.
- **4.5, `/monatsabschluss`, `start` und `bestaende` aendern zwei Zeilen**, die der Plan nicht
  nannte: „Prognose Ø“ und den Tiefpunkt-Hinweis zu einem Konto. Beide kommen aus der
  Kontoprognose (`household_accounts`), nicht aus dem Treffer-Check. Die Seite stand ohnehin in
  der Liste. **Warum:** Der Plan nannte den Treffer-Check als Teil von `/monatsabschluss`, die
  Seite zeigt aber auch die Kontoprognose selbst. **Schritt:** keiner.
- **4.5, `test_klammer_an_und_aus` schlug in einem Lauf fehl** (`KeyError: 'szenarien'`: der Test
  las `szenarien.yaml`, waehrend die Seite sie schrieb) und lief danach dreimal einzeln und im
  zweiten Gesamtlauf. Mit der Kontoprognose hat er nichts zu tun. **Schritt:** keiner; wer ihn
  haerten will, laesst den Test nach dem Schreiben warten, bis die Datei den Schluessel hat.
  **Warum:** Test und Seite teilen sich `szenarien.yaml`, und der Test liest, waehrend die
  Seite schreibt; eine Datei ohne den Schluessel ist ein Zwischenstand, kein Fehler der Seite.
- **4.5b, ein Vertrag kennt die Zusammenführung nicht.** Ein erklärter Vertrag nimmt über
  `ledger/reihe.hashes` die Buchungen derselben `counterparty_norm` aus der Messung. Steht die neue
  Schreibweise darunter nicht, bleibt sie als eigene Reihe stehen und kommt neben dem Posten des
  Vertrags in die Kontoprognose (Entwicklungskopie: ein Mobilfunkvertrag, dessen neue Schreibweise
  als Jahresposten daneben steht, obwohl der Vertrag den Betrag monatlich bucht). Die
  Zusammenführung ändert das nicht, denn der Plan nimmt Verträge aus. **Warum:** Wortlaut von 4.5b
  (nicht fuer Regeln, Vertraege oder `ledger/reihe.py`): Deren Zuordnung haengt an
  `counterparty_norm`. **Schritt:** keiner in Schritt 4; der Haushalt ordnet die Buchung auf `/vertraege` dem Vertrag
  zu, dann nimmt `reihe.hashes` alle ihre Buchungen.
- **4.5b, eine Teil-Zusammenführung kann eine Reihe unregelmäßig machen.** Fehlen den Auszügen
  Monate (zwei Konten, einzelne Auszüge), ergeben erst alle Schreibweisen zusammen genug
  regelmäßige Termine: Zwei von dreien sind auf der Entwicklungskopie unregelmäßig, alle drei
  monatlich. Kein Fehler, die Seite zeigt es unter „Alle“. **Warum:** Die Erkennung braucht Termine
  (Entscheidung 3), und wo Auszüge fehlen, hat eine einzelne Schreibweise zu wenige.
  **Schritt:** keiner.
- **4.5b, der Vorschlag trifft bei Jahreszahlungen auch Zufall.** Zwei Reihen in einer
  Fixkosten-Kategorie mit je einer Buchung, ein Jahr (± ein Vierteljahr) auseinander und mit etwa
  gleichem Betrag, sind vorgeschlagen, auch wenn es zwei Anbieter sind (Entwicklungskopie: zwei
  Vereine, ein Vermieter und eine Nebenkostenabrechnung). Von 11 Vorschlägen sehen nach den Namen 9 nach demselben Zahler aus, 2 nach
  Zufall. Es steht nichts fest, bis der Haushalt klickt. **Warum:** Ein Jahresbeitrag hat je
  Schreibweise einen Termin; mehr Anhaltspunkte als Kategorie, Betrag und Abstand gibt es
  nicht. **Schritt:** keiner; strenger hieße, echte
  Jahreszahlungen zu übersehen.
- **4.5b, `/reihen` wächst mit der Auswahl je Reihe:** Jede Zeile trägt in ihrem Panel die
  Reihen ihrer Kategorie, in der Vorgabe 0,9 MB, mit „Alle“ 2,1 MB. Es lädt in unter 0,1 s.
  **Warum:** Wie beim Panel (4.3): Die Auswahl steht im HTML, damit „Öffnen“ ohne Rechnen im
  Skript geht. **Schritt:** 6 („Der Server baut das HTML“) kann Panel und Auswahl beim Öffnen nachladen
  (siehe der Eintrag zu 4.3).
- **4.5b, die Zusammenführung einer Gegenpartei gilt in jeder ihrer Kategorien.** Wer
  zwei Schreibweisen in einer Kategorie für dieselbe Zahlung hält, sagt es damit auch dort, wo
  beide sonst noch stehen. **Warum:** Gewollt (der Zahler ist derselbe), aber auf der Seite nicht zu sehen,
  bis man die andere Kategorie öffnet. **Schritt:** keiner.
- **4.6, `module.erststart(config_dir)` prüft den Ordner, den es bekommt, und schreibt in einen
  anderen.** Es sieht nach `config_dir / module_custom.yaml` und `accounts.yaml`, schreibt aber über
  `overlays.schreiben` nach `overlays.CONFIG_DIR`. Ein Test, der `init` gegen einen Wegwerfordner
  ruft, schaltete so in der Testkopie jedes Arbeitsprozesses alle Module außer der Basis aus; 17 Tests
  (`/reihen`, `/ziele`, die Planung) fielen danach rot, nicht der, der es verursacht hatte. Mein Test
  setzt jetzt auch `overlays.CONFIG_DIR` und prüft, dass die Datei im Wegwerfordner liegt. Ändert
  keine Zahl. **Warum:** Die Funktion nimmt einen Ordner als Parameter und liest zugleich einen Wert
  aus dem Modul. **Schritt:** keiner in Schritt 4; Schritt 8 („Einrichtung ohne Texteditor“) fasst die
  Module an und kann die beiden gleichsetzen.
- **4.6, das Nachführen ändert beim ersten Lauf eine Datei und die Datenbank des echten
  Datenordners.** Es trägt eine Zeile in `taxonomy.yaml` ein und lädt die Kategorien neu, sobald dieser
  Code zum ersten Mal einen Befehl oder die App für den Ordner startet (stderr und Konsole nennen es).
  Beides ist klein, aber eine Änderung am Datenordner. **Warum:** Das Ziel von 4.6 ist, dass keine
  Zahl sich ohne Hinweis bewegt, und dafür muss der Code die Änderung selbst vornehmen, nicht ein
  Handgriff, den man vergisst. **Schritt:** Der Umstieg des echten Datenordners (Neufassung, „Umstieg“,
  nach Schritt 5) hat die Sicherung vorher schon; er sollte sagen, dass das Nachführen beim ersten
  Start von selbst läuft und nichts von Hand zu tun ist. Das ergänzt Opus in `docs/Neufassung_plan.md`.
- **4.6, `nachfuehren` kennt nur das Merkmal `einmalig`.** Neue Spalten legt `_ADDED_COLUMNS` von
  selbst an; was dazu in `taxonomy.yaml` gehört und in die Datenbank geladen werden muss, schreibt
  jedes künftige Merkmal selbst in `nachfuehren`. **Warum:** Welche Kategorie ein Merkmal bekommt, ist
  eine Entscheidung je Merkmal, kein Muster, das sich verallgemeinern ließe. **Schritt:** keiner;
  wer ein Merkmal einführt, ergänzt `nachfuehren` und seinen Test. Schritt 5 (der Datenordner wird
  ohnehin angefasst) ist der nächste, bei dem es nötig werden kann.
- **4.6, eine Zeile in einer fremden Form wird gemeldet und nicht geändert.** Steht
  `kaufnebenkosten:` als Blockeintrag (`name:` in der nächsten Zeile) oder mit Anführungszeichen in
  `taxonomy.yaml`, schreibt `nachfuehren` nichts und sagt, es sei von Hand zu tun; bis dahin bleibt
  der Block `einmalig` leer. **Warum:** Ein Textänderer, der zwei Formen kann, ist ehrlicher als
  einer, der jede zu können vorgibt und eine Datei zerschießt; die Startvorlage und die Entwicklungskopie
  haben die erste. **Schritt:** keiner.
- **4.6, `ledger.connect` ändert ein altes Hauptbuch und scheitert an einer schreibgeschützten
  Datei, der die Spalte fehlt.** `ops.restore` und `ziel_pruefen` öffnen mit `sqlite3.connect` und
  sind nicht betroffen. **Warum:** `connect` ist die Tür, durch die jede Abfrage geht, die die Spalte
  nennt; die Spalte dort anzulegen ist der einzige Ort, an dem „no such column“ ausgeschlossen ist.
  **Schritt:** keiner.
