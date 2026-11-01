# Schritt 4c: Teilzeit, betriebliche Altersvorsorge und Zielfortschritt

Arbeitsplan für die Umsetzung, geschrieben für ein Modell, das ihn Teil für
Teil abarbeitet (Claude Sonnet). Gesamtplan: `docs/Neufassung_plan.md`, dort
als Schritt 4c. Begriffe: `CONTEXT.md`. Kommt nach Schritt 4b
(`docs/schritt_policen.md`).

## Ziel in einem Satz

Die Teilzeit steht einmal, in den Annahmen, und alles, was an ihr hängt,
folgt ihr: die Zeilen ihrer Klammer und der Beitrag einer betrieblichen
Altersvorsorge, die nur der Arbeitgeber zahlt. Die Fortschrittszeile eines
Ziels misst gegen dieselbe Basis wie /ziele.

## Befund (Opus, 05.10.2026)

- Anteil und Start der Teilzeit stehen auf /annahmen (`teilzeit_anteil`,
  `teilzeit_ab`). Eine Teilzeit-Zeile ohne eigene Werte nimmt sie
  (`szenarien._teilzeit_aus_annahmen`). Andere Zeilen der Klammer
  „Teilzeit“, etwa ein wegfallender Policenbeitrag, brauchen aber ein eigenes
  Datum und wandern nicht mit.
- Eine Rentenquelle `art: kapital` ohne `konto` zahlt einen festen Betrag
  aus. Eine betriebliche Altersvorsorge, die nur der Arbeitgeber zahlt, hängt
  aber am Gehalt: Bei Teilzeit sinkt der Beitrag und damit die Auszahlung.
  Heute rechnet die Hochrechnung bei jeder Teilzeit mit dem vollen Betrag,
  und damit auch die Rentenlücke.
- `auswertung._fortschritt_zeile` nimmt für „hochgerechnet“ `Year.frei_cents`,
  und darin steckt die Anlageklasse Policen, auch wenn die Basis des Ziels
  Rentenversicherungen ausschließt. /ziele rechnet dagegen nur die
  Anlageklassen der Basis hoch (`ziele.toepfe_fuer_basis`). Auf der
  Entwicklungskopie liegt die Zeile dadurch rund 20 Prozentpunkte über
  /ziele.

## Entscheidungen (mit dem Haushalt abgestimmt, 05.10.2026)

1. **Teilzeit steht einmal, in den Annahmen.** Jede Zeile der Klammer
   „Teilzeit“ (`szenarien.TEILZEIT_ID`) ohne `start` beginnt mit
   `teilzeit_ab`. So fällt etwa ein Policenbeitrag (Wegfall-Zeile) mit dem
   Wechsel weg und wandert mit, wenn sich das Datum ändert. Eine Zeile mit
   eigenem `start` behält ihn. Außerhalb der Klammer bleibt eine Zeile ohne
   `start` ein Fehler beim Lesen, wie heute.
2. **Betriebliche Altersvorsorge als Modell.** Eine Rentenquelle
   `art: kapital` ohne `konto` darf tragen: `stand_cents` und `stand_wert`
   (Wert laut Mitteilung mit Datum), `beitrag_ag_cents` (Beitrag des
   Arbeitgebers je Jahr, nominal fest) und `cents` (der Betrag zu `ab`, mit
   dem der Haushalt rechnen will). Daraus ergibt sich **ein** Satz: der, mit
   dem Stand plus Beitrag genau `cents` zu `ab` erreichen. Er wird einmal
   gerechnet und steht in der Herleitung. Einen Zinssatz tippt der Haushalt
   nicht.
   - Ohne Teilzeit zahlt die Quelle damit genau `cents` aus.
   - Mit Teilzeit wird der Beitrag ab ihrem Start mit ihrem `anteil`
     multipliziert (`_sz.teilzeit_im_monat`, dieselbe Quelle wie das Gehalt).
     Mit dem Gehalt (`rente_ab`) endet er ganz.
   - Sie bleibt eine Rentenquelle, keine Position: kein Teil des liquiden
     Vermögens, kein Notfallwert, kein Abzug von der Sparrate.
   - Ohne die neuen Felder bleibt alles wie heute: fester Betrag.
   - `cents` darf bewusst unter der Hochrechnung der Mitteilung liegen. Die
     Zahl der Mitteilung steht dann als `pruefwert: {cents, zum}` daneben,
     wie bei den Policen.
   - Die Felder stehen beim Haushalt schon in `renten_custom.yaml` unter
     `neu:`. Die heutige App ignoriert sie, und ihre Namen sind damit
     festgelegt.
3. **Die Fortschrittszeile misst gegen die Basis des Ziels**, mit derselben
   Rechnung wie /ziele. Eine Anlageklasse, die die Basis nicht enthält,
   zählt auch hochgerechnet nicht.
4. **Werte des Haushalts gehören nach `config/`**, nie in Code, Tests oder
   diesen Plan. Die Zahlen des Haushalts stehen in `notizen/policen.md` im
   echten Datenordner.

## Bewusst nicht: Renten als „zugesagt“ gegen ein Ziel

Geprüft und verworfen (05.10.2026). Policen, betriebliche Altersvorsorge und
gesetzliche Rente könnten mit ihrem Barwert zum Stichtag als „zugesagt“ gegen
ein Ziel nach der 4-%-Regel stehen. Das senkte das nötige freie Kapital
deutlich. Der Haushalt rechnet Barista FIRE aber als Kapitalerhalt: Bei 7 %
Depotsatz und 2 % Inflation liegt die reale Rendite über der Entnahme von
4 %, und das Kapital wird im Mittel nicht verzehrt. Später kommende Renten
sind dann eine Reserve gegen schlechte frühe Jahre und höhere Kosten im
Alter, kein Teil des Ziels. Wo Renten Kapital ersetzen, rechnet schon die
Rentenlücke.

Die Basis des Barista-Ziels schließt Rentenversicherungen deshalb mit
Absicht aus. Entscheidung 3 sorgt dafür, dass das auch hochgerechnet gilt.

## Was „gleich“ und was „gewollt“ heißt

Wie in `docs/schritt4_reihe_takt.md`. Vor jedem Befehl gilt:

```bash
export FINCTL_DATEN="$HOME/Library/Application Support/Finance OS Entwicklung"
```

**Vorher, als eigener Schritt mit neu geschriebener Referenz** (erledigt am 07.10.2026:
Klammer und Annahmen übertragen, die betriebliche Altersvorsorge nach T.0): Die
Entwicklungskopie bekommt die betriebliche Altersvorsorge, die es im echten
Datenordner schon gibt (`renten_custom.yaml`, `neu:`), dazu die Klammer
„Teilzeit“ aus `szenarien.yaml` und `teilzeit_anteil`/`teilzeit_ab` aus
`settings_custom.yaml`. Das ist eine Datenänderung, keine Codeänderung. Sie
darf nicht in T.1 bis T.3 mitlaufen.

Der Musterhaushalt bekommt eine betriebliche Altersvorsorge mit erfundenen,
runden Werten und eine Klammer „Teilzeit“ mit einer Wegfall-Zeile ohne
`start`.

## Die Teilschritte

### T.0 Prüfwert ohne Satz (gleich)

Aus „Gefundene Abweichungen“, vor T.1. Entscheidung 6 aus `docs/schritt_policen.md`.

- Ein `pruefwert` darf ohne `satz` stehen (`renten.Pruefwert.satz` ist dann
  `None`). `cents` und `zum` bleiben Pflicht, ein falsches von beiden und ein
  falscher `satz` bleiben ein Fehler beim Lesen.
- Ohne `satz` gibt es keinen Vergleich: `policen.vergleichen` rechnet nichts,
  und die Herleitung der Auszahlung und `/renten` sagen „Prüfwert ohne Satz,
  nicht vergleichbar“ (`jahre._vergleichstext`, die eine Stelle für beide).
  Ohne `konto` gibt es ohnehin keine Police und keinen Vergleich.
- Tests: Lesen mit und ohne `satz`, falsches `cents` oder `zum` ist ein
  Fehler (`tests/test_renten.py`); kein Vergleich, Herleitung und
  `pruefvergleiche` einer Police mit `konto` und Prüfwert ohne Satz
  (`tests/test_policen.py`).

**Fertig wenn:** gleich auf den Daten ohne den Eintrag. Mit dem Eintrag liest
eine Kopie alle Rentenquellen.

**Abgenommen am 07.10.2026 (Opus).**
- **`pruefen` ohne den Eintrag:** gleich.
- **Datenschritt:** Danach steht der Eintrag der betrieblichen Altersvorsorge in
  `config/` der Entwicklungskopie. Die Kopie liest alle vier Rentenquellen.
- **Gewollte Unterschiede durch die Quelle:**
  - Sie steht auf `/renten`, `/annahmen`, im Monatsabschluss und in den Seiten,
    die ihn zeigen.
  - `/hochrechnung` bekommt ab 2061 den Betrag laut Schreiben minus Abzug.
  - Die Extrapolation zum Rentenbeginn auf `/ziele` steigt um den Teil des
    Jahres 2061, der bis zum Stichtag vergangen ist (`Projection.zum`).
- **Referenz:** danach neu geschrieben.

Damit ist der Datenschritt vor T.1 vollständig, und T.1 ist gleich gegen diesen
Stand.

### T.1 Teilzeitstart und betriebliche Altersvorsorge (gleich)

Entscheidungen 1 und 2.

- Zeilen der Klammer „Teilzeit“ ohne `start` beginnen mit `teilzeit_ab`.
- `renten.Quelle` liest `stand_cents`, `stand_wert`, `beitrag_ag_cents`,
  `pruefwert`. Eine Funktion rechnet daraus den Satz (Bisektion genügt) und
  die Auszahlung zu `ab` bei gegebenem Teilzeitverlauf. Rein, ohne Ledger.
- `_rentenposten` nimmt bei einer solchen Quelle die gerechnete Auszahlung
  statt `cents`.
- Tests:
  - Eine Wegfall-Zeile ohne `start` in der Klammer beginnt mit den
    Annahmen, eine außerhalb ist ein Fehler.
  - Ohne Teilzeit ist die Auszahlung `cents` (auf den Cent).
  - Mit 50 % ab der Hälfte der Zeit sinkt sie um den Endwert der halben
    Beiträge der zweiten Hälfte.
  - Ohne die neuen Felder bleibt `cents`.

**Fertig wenn:** gleich. Die Klammer „Teilzeit“ der Entwicklungskopie ist
ausgeschaltet. Eingeschaltet sinkt die Auszahlung der betrieblichen
Altersvorsorge. Der Bericht nennt, um wie viel.

**Umgesetzt am 07.10.2026 (T.1).**
- `renten.Quelle` trägt `stand_cents`, `stand_wert`, `beitrag_ag_cents`. Die drei
  stehen zusammen oder gar nicht, nur bei einem nominalen Kapital ohne `konto` mit
  `cents`; sonst ein Fehler beim Lesen. Das Overlay darf sie Feld für Feld ersetzen.
- `renten.satz(q, beginn)` sucht den Satz per Bisektion (zwischen −50 und +50 %,
  gerechnet einmal je Quelle und Beginn, zwischengespeichert).
  `renten.auszahlung_cents(q, beginn, anteil_im_monat, gehalt_bis)` rechnet die
  Auszahlung. Der Verlauf ist monatlich: Stand zum Monat des Schreibens, je Monat
  verzinst, am Monatsende ein Zwölftel des Beitrags mal dem Anteil des Monats.
  Ohne Teilzeit, also ohne `anteil_im_monat`, ist es `cents`. Die Rechnung kennt
  weder Ledger noch `szenarien`.
- `jahre._kapitalposten` nimmt für eine solche Quelle die gerechnete Auszahlung,
  sobald eine Teilzeitzeile eingeschaltet ist (`e.teilzeit`); das Gehalt endet mit
  `e.rentenbeginn`. Der Text des Postens bleibt, wie er war, solange die
  Auszahlung gleich dem Betrag laut Schreiben ist, und nennt sonst den Satz.
- `szenarien.load`: Eine Zeile der Klammer „Teilzeit“ ohne `start` beginnt mit
  `teilzeit_ab` (`Line.aus_annahmen == ("start",)`); ohne Eintrag dort bleibt sie
  ohne Start und zählt nichts, wie die Teilzeitzeile selbst. Eine Zeile ohne
  `start` in einer anderen Klammer ist jetzt ein Fehler beim Lesen.
- Die Vorlagen sind unverändert. Der Satz steht dauerhaft erst auf `/renten` (T.3).

**Abgenommen am 07.10.2026 (Opus).**
- **Nachgeprüft:** `pruefen` meldet gleich, und die Auszahlung ohne Teilzeit ist auf den Cent
  der Betrag laut Schreiben. Mit der eingeschalteten Klammer stimmt die Auszahlung mit den
  Notizen überein.
- **Satz:** Sein Abstand zu den Notizen kommt aus der Rechenweise. Die Notizen zahlen den
  Beitrag jährlich, T.1 monatlich. Gilt.
- **Auslegungen:** Sie gelten. Der Satz steht erst in T.3 immer in der Herleitung.
- **Zeile ohne `start` außerhalb der Klammer:** Der Plan ist nachgezogen. Sie war bisher
  still wirkungslos, jetzt ist sie ein Fehler beim Lesen. Das ist richtig, denn das Formular
  verlangt einen Start. Weil vier Seiten dann nicht mehr laden, steht unter „Umstieg“ im
  Gesamtplan eine Prüfung der echten `szenarien.yaml`.
- **Für T.3:** Den Musterhaushalt hat T.1 übersehen. Der Plan nennt ihn oben unter „Was
  ‚gleich‘ und was ‚gewollt‘ heißt“. Er kommt in T.3.

### T.2 Fortschrittszeile gegen die Basis (gewollt)

Entscheidung 3.

- `auswertung._fortschritt_zeile` rechnet „hochgerechnet“ wie /ziele, über
  `toepfe_fuer_basis` der Basis des Ziels. Die Rechnung steht danach an einer
  Stelle, nicht an zweien.
- Test: Ein Ziel, dessen Basis keine Rentenversicherung enthält, zeigt
  hochgerechnet dasselbe mit und ohne Police im Bestand.
- **Erwartet** (Entwicklungskopie): Die Prozentzahl „hochgerechnet“ sinkt um
  den Anteil der Policen am Stichtag und stimmt mit /ziele überein.

**Seiten mit Unterschieden:** die Fortschrittszeile im Monatsabschluss (samt
`start`) und die Auswertung, die sie zeigt. Keine auf /ziele, in der
Hochrechnung, im Hauptbuch, auf /konten oder in der Kontoprognose.

**Erledigt am 07.10.2026 in P.2b** (`docs/schritt_policen.md`).
- P.2 machte den Fehler sichtbar, deshalb hat P.2b ihn mitgenommen.
- `_fortschritt_zeile` ruft jetzt `ziele.hochgerechnet`.
- Ein Test hält fest, dass die Zeile und `/ziele` denselben Wert zeigen. Damit gilt
  auch der Test oben: `/ziele` misst schon gegen die Basis.
- Die Referenz ist danach neu geschrieben. Für 4c bleiben T.1 und T.3.

### T.3 Zeigen (gleich in den Zahlen)

Vorher `docs/design_conventions.yaml` lesen.

- `/renten`: Bei einer betrieblichen Altersvorsorge mit Modell stehen Stand,
  Beitrag, gerechneter Satz, Prüfwert mit seinem Satz und die Auszahlung mit
  und ohne Teilzeit. Nennt der Prüfwert keinen Satz (T.0), steht daneben der
  Satz, der von Stand und Beitrag genau zu ihm führt. Das ist dieselbe Bisektion
  wie für `cents`. So sieht man, welchen Satz der Haushalt mit `cents` ansetzt
  und welchen die Mitteilung unterstellt.
- Die Herleitung der Auszahlung auf `/hochrechnung` nennt den Satz immer, nicht
  nur bei eingeschalteter Teilzeit (Entscheidung 2, aus T.1 aufgeschoben).
- Musterhaushalt: eine betriebliche Altersvorsorge mit Modell und erfundenen,
  runden Werten und eine Klammer „Teilzeit“ mit einer Wegfall-Zeile ohne
  `start` (siehe „Was ‚gleich‘ und was ‚gewollt‘ heißt“).
- `/planung`: Eine Zeile der Klammer „Teilzeit“ ohne eigenes Datum zeigt
  „ab Teilzeitstart (MM/JJJJ)“.
- Browsertests: `.venv/bin/python -m pytest -m browser -n 0`.

**Fertig wenn:** `pruefen --nur-zahlen` ist grün. Der Bericht legt die
Textunterschiede bei.

**Umgesetzt am 07.10.2026 (T.3).**
- `renten.satz_zu(q, beginn, ziel_cents)` ist die Bisektion zu jedem Betrag; `renten.satz`
  ruft sie mit `cents` und bleibt bei einem unerreichbaren Betrag ein Fehler. Dazu
  `renten.teilzeit_ab(anteil, ab)` für den Anteil je Monat.
- `jahre.modellzeile` baut die Zeile für `/renten`: Stand, Beitrag, Satz, Prüfwert mit dem Satz,
  der von Stand und Beitrag zu ihm führt (auch wenn er einen nennt), Auszahlung vor Abzug ohne
  und mit der Teilzeit aus den Annahmen, ob die Klammer an ist oder nicht. Ein Betrag, den das
  Modell nicht trägt, steht als Meldung in der Zeile, die Seite bleibt offen.
- Die Herleitung der Auszahlung (`_kapitalposten`) nennt den Satz immer. Eine Quelle ohne
  Modell bleibt, wie sie war.
- `/planung`: Eine Zeile der Klammer „Teilzeit“ ohne eigenes Datum zeigt „ab Teilzeitstart
  (JJJJ-MM)“, ohne Teilzeitstart „Beginn fehlt“. Das Feld „von“ bleibt leer (Platzhalter: der
  Teilzeitstart), und Speichern ohne Datum behält sie ohne eigenes Datum: `_planzeile` verlangt
  den Start nur außerhalb dieser Klammer. Ohne das hätte der erste Klick auf Speichern ihr
  still ein eigenes Datum gegeben.
- Musterhaushalt: betriebliche Altersvorsorge mit Modell und Prüfwert ohne Satz
  (`renten_custom.yaml`), `teilzeit_ab`/`teilzeit_anteil` in `settings_custom.yaml` und eine
  Wegfall-Zeile ohne `start` in der Klammer „Teilzeit“. Ein Test hält das fest (nur im
  Musterlauf).
- Handbuch (`/renten`, `/planung`) und `CHANGELOG.md` nennen es.

**Zwei Abweichungen vom Plan:**
- **Datumsform:** Der Plan sagt „ab Teilzeitstart (MM/JJJJ)“. `docs/design_conventions.yaml`
  (`datum-iso`, geprüft von `tests/test_design.py`) verbietet `strftime('%m/` in Vorlagen und
  verlangt `JJJJ-MM`. Die Vorlage folgt der Konvention.
- **`pruefen --nur-zahlen` ist nicht grün.** Drei Unterschiede, alle durch den Satz in der
  Herleitung: eine neue Zeile auf `/renten` (nur Zuwachs), eine geänderte Zeile auf
  `/hochrechnung` (die alten Zahlen bleiben, Satz, Stand, Datum und Beitrag kommen in
  dieselbe Zeile) und derselbe Text als `herleitung` in `ableitung/hochrechnung_jahre.json`,
  die der Vergleich immer streng liest. Kein Betrag hat sich bewegt. Vollständig, auch der Text:
  `notizen/T.3_pruefen_unterschiede.md` der Entwicklungskopie. Die Referenz ist nicht neu
  geschrieben.

**Abgenommen am 07.10.2026 (Opus).**
- **`--nur-zahlen` nicht grün:** Der Widerspruch lag im Plan, nicht im Code. Ein Satz, der
  „immer“ in einer bestehenden Zeile steht, ändert diese Zeile. Die Unterschiede sind
  nachgeprüft: Kein Betrag bewegt sich, die alten Zahlen der Herleitung stehen unverändert
  darin, und `/renten` bekommt nur eine Zeile dazu. Damit gilt der Teilschritt als gleich in
  den Zahlen. Die Referenz ist danach neu geschrieben, `pruefen` meldet „Gleich“.
- **Datumsform `JJJJ-MM`:** Sie gilt; die Konvention geht dem Plan vor.
- **Sätze:** Die Bisektion stimmt mit der geschlossenen Formel überein (monatlicher Beitrag,
  Monatssatz aus dem Jahressatz). Der Abstand zu den Notizen ist der aus T.1: jährlich gegen
  monatlich gerechnet.
- **Speichern ohne Datum:** Die Lücke im Feld „von“ hat die Sitzung zu Recht geschlossen.
  Ohne Datum speichern lässt sich eine Zeile nur in der Klammer „Teilzeit“.

Damit ist Schritt 4c erledigt.

## Gefundene Abweichungen

(Hier trägt jede Sitzung ein, was nicht in den Plan passt.)

- **Datenschritt, 07.10.2026 (Opus).** Die Entwicklungskopie hat jetzt die
  Klammer „Teilzeit“ aus `szenarien.yaml` und `teilzeit_anteil`/`teilzeit_ab`.
  Beide stammen wortgleich aus dem echten Datenordner, gelesen mit
  ausdrücklichem OK des Haushalts. Danach ist die Referenz neu geschrieben.
  Die Unterschiede zeigen sich nur in Einstellungen, Planung und Text, weil die
  Klammer ausgeschaltet ist.
- **T.1, 07.10.2026: „Fehler beim Lesen“ stimmte vorher nicht.** Der Plan nennt
  eine Zeile ohne `start` außerhalb der Klammer „Teilzeit“ einen Fehler „wie heute“.
  Heute war sie keiner: `Line.months` lieferte nichts, die Zeile zählte still nichts.
  T.1 macht daraus den Fehler (`szenarien.load`, eine Meldung mit Klammer und
  Zeile); alle Seiten, die `szenarien.yaml` lesen, antworten dann mit 500, wie bei
  jedem anderen Lesefehler. Das Formular auf `/planung` verlangt einen Start, also
  entsteht so eine Zeile nur von Hand. Vor dem Umstieg in den echten Datenordner
  dessen `szenarien.yaml` auf Zeilen ohne `start` prüfen.
- **T.1: Zahl im Plan.** Der gerechnete Satz der betrieblichen Altersvorsorge liegt
  mit dem monatlichen Verlauf rund 0,06 Prozentpunkte unter den „rund 5,1 %“ der
  Notizen, die einen Beitrag je Jahr am Jahresende rechneten. Der Betrag laut
  Schreiben ist davon nicht berührt, die Teilzeit-Auszahlung stimmt mit den
  Notizen überein. Die Zahlen stehen in `notizen/T.1_bav_teilzeit.md` der
  Entwicklungskopie.
- **T.1: Musterhaushalt.** Der Plan nennt eine betriebliche Altersvorsorge und eine
  Wegfall-Zeile ohne `start` für `tests/musterhaushalt/`, ohne Teilschritt. T.1
  prüft beides mit erfundenen Werten in den Tests und lässt den Musterhaushalt
  unverändert; T.3 braucht ihn für die Browsertests.
- **Die betriebliche Altersvorsorge fehlt noch.** Ihr Eintrag unter `neu:`
  trägt einen `pruefwert` ohne `satz`. Das ist Absicht: Die Mitteilung nennt
  ihre Fondsrendite nicht, und der Satz der Quelle wird in T.1 aus Stand und
  Beitrag gerechnet. Seit P.1 bricht `renten.quellen()` bei einem Prüfwert
  ohne Satz mit einem Fehler ab. Mit dem Eintrag liest die Entwicklungskopie
  keine Rentenquelle mehr. Dasselbe träfe den echten Datenordner beim
  Umstieg, denn dort steht der Eintrag schon. Die Datei mit dem Eintrag liegt
  deshalb in `notizen/4c_renten_custom_mit_bav.yaml` der Entwicklungskopie,
  nicht in `config/`.
  **Schritt:** T.0, vor T.1. Ein Prüfwert darf ohne `satz` stehen. Dann
  vergleicht ihn niemand: Eine Police mit `konto` sagt in der Herleitung
  „Prüfwert ohne Satz, nicht vergleichbar“. Ohne `konto` gibt es ohnehin
  keinen Vergleich. Gleich auf den heutigen Daten. Danach überträgt Opus den
  Eintrag und schreibt die Referenz neu: gewollt, denn die Hochrechnung
  bekommt die Auszahlung der Quelle.

**Umgesetzt am 07.10.2026 (T.0).** `Pruefwert.satz` ist `float | None`;
`renten._pruefwert` liest `satz` optional (leer oder fehlend heißt `None`),
`policen.vergleichen` gibt dann `Vergleich(satz=None, …)` ohne Rechnung zurück,
`jahre._vergleichstext` sagt „Prüfwert ohne Satz, nicht vergleichbar“. Der
Eintrag wurde nur in einer Kopie des Datenordners probiert, `config/` der
Entwicklungskopie ist unverändert. Offen bleibt, was Opus tut: den Eintrag aus
`notizen/4c_renten_custom_mit_bav.yaml` nach `config/` übertragen und die
Referenz neu schreiben (gewollt: die Hochrechnung bekommt die Auszahlung der
Quelle). Die bAV ohne `konto` zeigt ihren Prüfwert nirgends; T.3 zeigt ihn auf
`/renten`.
