# Schritt Policen: Beitrag, Kosten, Rückkaufswert

Arbeitsplan für die Umsetzung, geschrieben für ein Modell, das ihn Teil für
Teil abarbeitet (Claude Sonnet). Gesamtplan: `docs/Neufassung_plan.md`, dort
zwischen Schritt 4 und Schritt 5. Begriffe: `CONTEXT.md`. Begonnen wird erst,
wenn Schritt 4 abgenommen und die Referenz danach neu geschrieben ist: Beide
Schritte ändern die Hochrechnung mit Absicht, und ihre Unterschiede müssen
sich bei der Abnahme trennen lassen.

## Ziel in einem Satz

Eine Police wächst in der Hochrechnung so, wie ihre jährliche Mitteilung es
rechnet: mit ihrem Beitrag bis zur Auszahlung und mit ihrer Rendite nach
Kosten. Ihr Rückkaufswert steht als Notfallwert daneben, und die Mitteilung
dient als Prüfwert.

## Befund (Opus, 05.10.2026)

- Die Anlageklasse Policen wächst in `jahre.kaskade` nur mit dem Depotsatz
  auf den getippten Stand (`zins_policen = policen * satz_depot`). Der
  Monatsbeitrag läuft als Ausgabe aus der Sparrate heraus und kommt nie in
  der Police an. Auf der Entwicklungskopie zahlt die Hochrechnung deshalb
  rund ein Drittel dessen aus, was die Mitteilungen erwarten lassen.
- `Quelle.kosten_pa` (`finctl/renten.py`) wird gelesen und auf `/renten`
  angezeigt, aber nirgends gerechnet.
- Nach der Auszahlung bleibt der Beitrag in der Basis stehen: Die Messung
  sieht keine Kündigung (`_vertragsenden` reagiert nur auf `gekuendigt_zum`).
- Doppelt gezählt wird nichts: Eine Kapitalquelle mit `konto` zahlt den
  fortgeschriebenen Anteil aus (`_policenwechsel`), ihr `cents` steht nur in
  der Herleitung. Das bleibt so.
- Gegenprobe: Beide Mitteilungen des Haushalts lassen sich mit dem Modell
  „Stand plus Monatsbeitrag, Fondsrendite minus fester Abschlag“ auf weniger
  als 0,1 Prozentpunkte nachrechnen, in jeder ihrer Spalten. Mehr Modell
  braucht es nicht.

## Entscheidungen (mit dem Haushalt abgestimmt, 05.10.2026)

1. **Rendite je Police: Depotsatz minus `kosten_pa`.** `kosten_pa` sind die
   Effektivkosten aus der Mitteilung (Vertrag und Fonds zusammen, weil der
   Depotsatz eine Marktrendite ist). Ohne `kosten_pa` gilt 0, und `/renten`
   zeigt wie heute „nicht bekannt“. Gerechnet wird monatlich wie in der
   Mitteilung: Anteil mal Monatssatz, dann der Beitrag dazu.
2. **Der Beitrag kommt vom Vertrag.** `renten.yaml` bekommt je Quelle das
   Feld `beitrag: <vertrag-id>`, eine Kennung aus `versicherungen*.yaml`
   oder `abos*.yaml`. Betrag und Takt stehen am Vertrag (`betrag_cents`,
   `takt`) und werden nicht ein zweites Mal getippt. Fehlt der Vertrag, ist
   das ein Fehler beim Lesen, kein stilles Null.
3. **Der Beitrag bleibt eine Ausgabe** in seinem Block, denn das Geld verlässt
   das Konto. Zusätzlich wächst der Anteil der Police um denselben Betrag:
   eine Umschichtung in die Anlageklasse Policen, kein neues Geld. Im
   Basisjahr nur für die Restmonate, wie alles andere.
4. **Der Beitrag fließt, solange er als Ausgabe läuft.** Eine Regel für alle
   Fälle: In die Police geht genau, was die Hochrechnung als Beitrag abzieht.
   - Mit der Auszahlung (`renten.beginn(q)`) endet der Vertrag, über
     denselben Weg wie `gekuendigt_zum` in `_vertragsenden`, ohne dass jemand
     `gekuendigt_zum` schreibt. Eine Police ist kein gekündigter Vertrag, sie
     läuft aus.
   - **Beitragsfreistellung** ist ein Vertragsende vor der Auszahlung:
     `gekuendigt_zum` am Vertrag, wenn sie beschlossen ist, oder eine
     eingeschaltete Wegfall-Zeile über die Buchungen des Vertrags, wenn sie in
     einem Szenario durchgespielt wird (Zeile und Vertrag teilen Buchungen).
     Ab dort fließt kein Beitrag mehr, die Police wächst weiter mit ihrem
     Satz, und die Quelle bleibt. Dafür braucht es kein eigenes Feld.
   - **Nichts doppelt.** Endet der Beitrag, steigt die Sparrate um ihn, und
     er geht über die Kaskade ins Depot. Im Ruhestand sinkt um ihn die
     Entnahme. In die Police fließt er dann nicht mehr. Derselbe Euro steht
     nie zugleich in der Police und im Depot, und die Police zahlt nie aus,
     was nicht mehr eingezahlt wurde. Ein Test sichert das ab (P.2).
   - Der Prüfwert setzt Beiträge bis zur Auszahlung voraus. Endet der
     Beitrag früher, sagt die Herleitung „Prüfwert nicht vergleichbar,
     Beitrag endet MM/JJJJ“, statt eine Abweichung zu zeigen.
   - Der Beitrag ist **nominal fest**: In die Police fließt der Betrag am
     Vertrag, ohne Inflation. Wächst die Ausgabe dafür in der Basis mit der
     Inflation, ist das ein Fund für „Gefundene Abweichungen“: Nach Schritt 4
     soll eine Reihe mit Takt ihren Betrag je Termin behalten.
5. **Nur Kapital.** Eine Kapitalquelle mit `konto` geht wie heute zum Datum
   `ab` ins Depot. Der Abzug bleibt pauschal `ruhestand.abzug_renten` auf die
   ganze Auszahlung. Das ist bewusst zu vorsichtig (Krankenversicherung
   möglich, die Halbbesteuerung nach zwölf Jahren und ab 62 wird nicht
   gerechnet). Verrentung ist nicht Teil dieses Schritts.
6. **Prüfwert statt Endwert.** Eine Kapitalquelle mit `konto` bekommt
   `pruefwert: {satz: 0.06, cents: …, zum: JJJJ-MM}`, eine Spalte aus ihrer
   Mitteilung (nominal, mit weiterlaufendem Beitrag). `satz` darf fehlen, wenn die
   Mitteilung ihn nicht nennt (4c, T.0): Dann steht in der Herleitung
   „Prüfwert ohne Satz, nicht vergleichbar“. Die Herleitung der
   Auszahlung nennt daneben, was das Modell bei diesem Satz minus `kosten_pa`
   zum selben Datum ergibt, und die Abweichung in Prozent. Eine Warnschwelle
   gibt es nicht. Erwartet ist, dass das Modell etwas darunter liegt, weil
   `kosten_pa` die Fondskosten enthält, die der Satz der Mitteilung schon
   abgezogen hat. `cents` einer solchen Quelle wird nicht mehr gerechnet und
   darf fehlen. Ohne `pruefwert` steht in der Herleitung wie heute `cents`.
7. **Rückkaufswert als Notfallwert.** Eine Position der Bestandsart
   Rentenversicherung bekommt `rueckkauf_cents`, `rueckkauf_as_of` und
   `eingezahlt_cents` (aus der Mitteilung). Der Notfallwert ist der
   Rückkaufswert minus Abgeltungsteuer (`steuer_quote` der Annahmen) auf
   `max(rueckkauf - eingezahlt, 0)`. Er wird nur angezeigt: Er zählt weder
   zum Notgroschen noch ändert er das liquide Vermögen, das weiter den
   Policenwert zählt. In späteren Monaten gilt das Verhältnis aus
   Rückkaufswert und Policenwert der Mitteilung, angewandt auf den aktuellen
   Policenwert.
8. **Werte des Haushalts gehören nach `config/`**, nie in Code, Tests oder
   diesen Plan. Die abgestimmten Werte und die erwarteten Auszahlungen stehen
   in `notizen/policen.md`; eine Kopie liegt seit dem 06.10.2026 in
   `notizen/` der Entwicklungskopie, und nur die liest eine Sitzung, nicht den
   echten Datenordner. Die Sitzung trägt die Werte in die `config/` der
   Entwicklungskopie ein und vermerkt im Bericht, dass sie beim Umstieg in den
   echten Datenordner gehören.

## Was „gleich“ und was „gewollt“ heißt

P.1 ist **gleich**, P.3 ist **gleich in den Zahlen**, P.2 ist **gewollt**.
Regeln, Befehle und Bericht wie in `docs/schritt4_reihe_takt.md`, Abschnitte
„Was ‚gleich‘ und was ‚gewollt‘ heißt“ und „Regeln für jede Sitzung“. Vor
jedem Befehl gilt:

```bash
export FINCTL_DATEN="$HOME/Library/Application Support/Finance OS Entwicklung"
```

Beide Läufe der Suite (echte Daten und `FINCTL_TESTDATEN=muster`) sind nach
jedem Teilschritt grün. Der Musterhaushalt hat schon zwei Policen
(`police-a`, `police-b`). Er bekommt Beitrag, `kosten_pa`, Prüfwert und
Rückkaufswert mit erfundenen, runden Werten, damit jeder Fall in beiden
Läufen vorkommt.

## Die Teilschritte

### P.1 Felder lesen (gleich)

- `renten.Quelle` bekommt `beitrag` (Kennung des Vertrags) und `pruefwert`.
  `quellen()` liest sie und prüft, dass der Vertrag existiert (Entscheidung 2).
- `balances` liest `rueckkauf_cents`, `rueckkauf_as_of`, `eingezahlt_cents`
  an Positionen der Bestandsart Rentenversicherung. Gerechnet wird damit noch
  nichts.
- Tests: Lesen mit und ohne die neuen Felder; ein unbekannter Vertrag ist ein
  Fehler.

**Fertig wenn:** gleich.

**Umgesetzt am 06.10.2026.** `renten.Quelle.beitrag` (Kennung) und
`Quelle.pruefwert` (`renten.Pruefwert`: `satz`, `cents`, `zum`); beide auch aus
`renten_custom.yaml` lesbar, geschrieben wird dort noch nichts. `quellen()`
liest die Vertragsdateien (`abos*.yaml`, `versicherungen*.yaml`, mit ihren
Seitendateien) nur, wenn eine Quelle einen `beitrag` nennt, und wirft bei einer
unbekannten Kennung einen `ValueError`; ein `pruefwert` mit fehlendem oder
falschem Feld ebenso. `bestaende.rueckkauf(zeile)` liefert
`Rueckkauf(cents, as_of, eingezahlt_cents)` für Rentenversicherungen,
`zusammenfuehren` nimmt die drei Felder aus der Basisdatei und aus dem Overlay
und prüft sie beim Zusammenführen; `zum` lässt sie für frühere Stichtage weg
(der Verlauf kennt nur den Stand). Auslegungen, wo der Plan offen ließ:
`eingezahlt_cents` darf fehlen (dann „unbekannt“, P.3 entscheidet, wie die
Steuer dann gerechnet wird); `rueckkauf_cents` ohne `rueckkauf_as_of` ist ein
Fehler; die Felder an einer anderen Bestandsart zählen nicht. Im Musterhaushalt
trägt `police-a` Rückkaufswert und Prüfwert; ein `beitrag` kommt mit P.2
zusammen mit dem Vertrag, der ihn erst rechnerisch wirksam macht. Die Werte des
Haushalts sind noch nicht eingetragen: P.1 braucht sie nicht, P.2 trägt
`kosten_pa`, `beitrag` und `pruefwert` ein, P.3 den Rückkaufswert.

**Abgenommen am 06.10.2026 (Opus).** `pruefen` nachgerechnet: gleich. Die Auslegungen gelten.
Ein falsches Rückkaufs-Feld in `balances` ist ein Fehler beim Lesen, wie ein unbekannter
Vertrag (Entscheidung 2): Bis P.3 die Felder über den Monatsabschluss schreibt, tippt sie
niemand von Hand.

### P.2 Die Police wächst mit Beitrag und Kosten (gewollt)

Entscheidungen 1 bis 6.

- Der Zins der Anlageklasse Policen kommt aus den Anteilen je Police, jeder
  mit Depotsatz minus seinen `kosten_pa`. `kaskade` bekommt ihn als Zahl,
  statt ihn aus `satz_depot` zu rechnen. Die Kaskade bleibt rein und ohne
  Ledger prüfbar.
- `_anteile_fortschreiben` schreibt jeden Anteil mit seinem eigenen Satz und
  Beitrag fort, nicht mehr verhältnisgleich aus der Summe.
- Der Beitrag fließt monatlich bis zum Monat vor `renten.beginn(q)` in seinen
  Anteil (Entscheidung 3). Im selben Monat endet die Ausgabe (Entscheidung 4).
- Die Herleitung der Auszahlung (`_policenwechsel`) nennt Stand, Beitrag,
  Satz nach Kosten und den Prüfwert (Entscheidung 6).
- Tests mit erfundenen Zahlen: eine Police mit Stand, Beitrag und Kosten
  ergibt nach n Monaten den Wert der geschlossenen Formel. Bei 0 % Kosten und
  ohne Beitrag ist das Ergebnis genau das heutige. Der Beitrag endet mit der
  Auszahlung. Er endet früher mit `gekuendigt_zum` und mit einer
  eingeschalteten Wegfall-Zeile, und die Police wächst danach ohne ihn
  weiter. Zwei Policen mit verschiedenen Kosten wachsen verschieden.
- **Test gegen Doppelzählung:** Police mit `kosten_pa` 0, Policensatz gleich
  Depotsatz, Puffer voll, Steuer im Depot 0. Mit und ohne eingeschaltete
  Wegfall-Zeile über den Beitrag ist das Vermögen (Liquidität, Depot und
  Policen) zum Auszahlungsdatum und danach gleich. Mit der Zeile ist nur
  anders verteilt: weniger Police, mehr Depot.
- **Erwartet** (Entwicklungskopie): Beide Auszahlungen landen nahe den Werten
  in `notizen/policen.md`, Abschnitt „Erwartete Wirkung“. Das Depot ist ab dem
  jeweiligen Jahr entsprechend größer. Die Sparrate ändert sich nicht, denn
  der Beitrag war schon Ausgabe. Nach der Auszahlung steigt sie um den
  Beitrag.

**Seiten mit Unterschieden:** `/hochrechnung`, `/ziele`, `/monatsabschluss`
(samt `start`, `bestaende`), `/renten` (die eingetragenen `kosten_pa` und was
aus ihnen folgt), `/annahmen` (Rentenlücke, Prognosebasis), die
Auswertung, die aus der Hochrechnung liest, und `ableitung/` der
Hochrechnung. Keine im Hauptbuch, auf `/konten` oder in der Kontoprognose.

**Umgesetzt am 06.10.2026.** Neu: `finctl/forecast/policen.py` (rein: `Police`,
`Beitrag`, `fortschreiben`, `vergleichen`); `jahre._policen_lesen` baut je Rentenquelle
mit `konto` eine Police (`Eingaben.policen`), samt Beitrag vom Vertrag und den Pausen aus
eingeschalteten Wegfall-Zeilen, die Buchungen mit dem Vertrag teilen. `kaskade` nimmt
`zins_policen` und `einzahlung_policen` als Zahl (der Satz `satz_depot` wirkt nicht mehr
auf die Policen); den Rest des Topfs ohne Police verzinst `rechnen` wie bisher mit dem
Depotsatz. `_anteile_fortschreiben` entfällt. `_vertragsenden` kennt die Auszahlung als
Ende des Vertrags (kleinerer von Auszahlung und `gekuendigt_zum`). Auslegungen, wo der
Plan offen ließ:
- **Monatssatz effektiv**, `(1 + Satz)^(1/12) − 1`: zwölf Monate ergeben den Jahressatz,
  und nur so treffen alle Spalten einer Mitteilung (nominal `Satz / 12` trifft sie nicht).
  Volle Jahre ohne Kosten und Beitrag sind deshalb genau das heutige; im Basisjahr
  (Restmonate) wächst der Stand zusammengesetzt statt linear.
- **Auszahlung im Monat der Auszahlung:** Eine Police rechnet im Jahr der Auszahlung bis
  zum Monat davor weiter, samt Beiträgen; ihr Stand dann geht ins Depot. Vorher war es der
  Stand vom Jahresanfang. Ihr Zins bis dahin steht in der Rendite des Jahres.
- **Beitrag als Umschichtung:** `Year.in_policen_cents`; `closing_cents` zählt ihn dazu
  (Endkapital = Anfang + Rendite + Saldo + Beiträge in die Policen). Neue Gruppe
  `policen_beitrag` im Rechenweg (Verteilung, kein Knoten im Fluss).
- **Prüfwert:** Das Modell rechnet vom Stand zum Rechenbeginn zum Datum des Prüfwerts, den
  Beitrag bis dahin, auch über die Auszahlung hinaus. Endet er vorher (Kündigung, Wegfall),
  sagt die Herleitung „Prüfwert nicht vergleichbar, Beitrag endet MM/JJJJ“.
- Der Beitrag fließt nur mit einem Vertrag, der `beitrag` der Quelle ist, und seine
  Ausgabe endet mit der Auszahlung nur, wenn der Vertrag `buchungen` hat.
- Musterhaushalt: `police-a` mit Beitrag und Kosten, `police-b` mit anderen Kosten;
  `tests/musterhaushalt/bauen.py` hängt dem Vertrag nach dem Einlesen die Buchungen seiner
  Reihe an. Tests: `tests/test_policen.py`, darin der Test gegen Doppelzählung (mit und
  ohne Wegfall-Zeile gleiches Vermögen bei Satz null, Inflation null, Abzug null; mit
  Rendite höchstens ein Tausendstel Unterschied) auch auf den Daten des Haushalts.

**Abgenommen am 07.10.2026 (Opus).** `pruefen` nachgerechnet: Unterschiede nur auf den
Seiten und Ableitungen, die P.2 nennt; Hauptbuch, `/konten` und Kontoprognose gleich. Die
größere Auszahlung mit der geschlossenen Formel nachgerechnet (Stand mal Jahressatz hoch
Monate durch zwölf, dazu der Endwert der Monatsbeiträge): Sie trifft den Wert der Seite.
Die Auslegungen gelten. Die Referenz ist danach neu geschrieben. Was die Abnahme fand,
geht nach P.2b:
- Der Abzug kommt aus dem Tagesgeld und lässt es im Jahr der größeren Auszahlung ins
  Minus fallen. Die Kopfzeile meldet dann ein Ende des Kapitals, das es nicht gibt.
- Die Ausgabe des Beitrags wächst mit der Inflation, der Beitrag in die Police nicht.
  Das widerspricht der einen Regel aus Entscheidung 4.
- Die Zeile „Barista FIRE … hochgerechnet“ auf `/monatsabschluss`, `start` und
  `bestaende` rechnet nicht wie `/ziele`. Sie nimmt `frei_cents`, also das ganze
  Endkapital samt Policen am Jahresende. Die Basis des Ziels und sein Stichtag zählen
  dabei nicht. Das war schon vor P.2 so, und P.2 macht es sichtbar.
- Die Herleitung „n × Beitrag … × 3/12 Restmonate“ rechnet die Restmonate zweimal.

### P.2b Abzug aus der Auszahlung, Beitrag nominal, Barista-Zeile (gewollt)

Entscheidungen 4 und 5. Keine neue Entscheidung des Haushalts: Höhe und Art des Abzugs
bleiben, nur seine Quelle ändert sich. Die Ausgabe folgt der Regel, die Entscheidung 4
schon setzt.

- **Abzug aus der Auszahlung.** Der pauschale Abzug auf eine Kapitalauszahlung einer
  Police mit `konto` geht von der Auszahlung selbst ab, wie der Versicherer die Steuer
  einbehält. Ins Depot kommt der Nettobetrag. Die Höhe bleibt
  `ruhestand.abzug_renten` auf die ganze Auszahlung (Entscheidung 5). Das Tagesgeld
  zahlt ihn nicht mehr, und die Sparrate des Jahres enthält ihn nicht. Die Herleitung
  der Umschichtung nennt brutto, Abzug und netto. Die Rechnung auf `/hochrechnung`
  geht weiter auf: Der Abzug mindert das Endkapital sichtbar und steht nicht als
  Ausgabe in einem Block. Eine Kapitalquelle ohne `konto` und die Verrentung bleiben
  wie sie sind.
- **Die Ausgabe des Beitrags bleibt nominal.** Die Ausgabe des Vertrags, der eine
  Police speist (`beitrag` der Quelle), wächst in der Basis nicht mit der Inflation.
  Sie bleibt beim Betrag je Termin, solange der Beitrag fließt. Damit gilt
  Entscheidung 4 wörtlich: In die Police geht genau, was die Hochrechnung als Beitrag
  abzieht. Eine Wegfall-Zeile über den Beitrag lässt dann keinen wachsenden Rest
  stehen, und `_vertragsenden` braucht die Ausnahme dafür nicht mehr. Alle anderen
  Reihen wachsen weiter mit der Inflation. Ob Reihen mit Takt allgemein nominal
  bleiben, gehört nicht zu diesem Schritt.
- **Die Barista-Zeile rechnet wie `/ziele`.** `_fortschritt_zeile` in
  `finctl/web/routen/auswertung.py` nimmt `ziele.hochgerechnet` und damit die Basis
  und den Stichtag des Ziels. Auf der Entwicklungskopie zeigt die Zeile danach
  denselben Prozentwert wie das Ziel auf `/ziele`. Such nach weiteren Stellen, die
  ein Ziel mit `frei_cents` messen, und nenn sie im Bericht.
- **Herleitung des Beitrags:** die Restmonate nur einmal, etwa „3 × 50,00 € in den
  3 Restmonaten“. Gilt ebenso für die Rendite je Police.
- **Tests:**
  - Der Test gegen Doppelzählung rechnet jetzt auch mit Inflation und hält dann
    genau, nicht nur auf ein Tausendstel.
  - Eine Police, deren Auszahlung samt Abzug größer ist als das Tagesgeld, lässt
    das Tagesgeld nicht ins Minus fallen.
  - Die Barista-Zeile und `/ziele` zeigen für dasselbe Ziel denselben Wert.

**Seiten mit Unterschieden:** `/hochrechnung`, `/ziele`, `/annahmen`,
`/monatsabschluss` (samt `start` und `bestaende`, nur die Barista-Zeile), die
Auswertung und `ableitung/` der Hochrechnung. Keine im Hauptbuch, auf `/konten`, auf
`/renten` und in der Kontoprognose.

**Erwartet** (Entwicklungskopie):
- Die Auszahlungen brutto bleiben, wie P.2 sie rechnet.
- Die Kopfzeile meldet wieder „Kapital reicht bis zum Ende“.
- Die Sparrate im Jahr einer Auszahlung enthält den Abzug nicht mehr.
- Vor der Auszahlung ist die Sparrate etwas höher, weil der Beitrag nicht mehr mit
  der Inflation wächst.
- Die Barista-Zeile sinkt auf den Wert von `/ziele`.

**Fertig wenn:** `pruefen` zeigt Unterschiede nur auf diesen Seiten, und der Bericht
legt die zehn größten je Seite mit Grund bei.

**Umgesetzt am 07.10.2026.**
- **Abzug:** `_policenwechsel` gibt jetzt `_Wechsel` zurück (verrentet, umgeschichtet, ins
  Depot netto, aufs Tagesgeld, Abzug). Der Posten „ausgezahlt ins Depot“ trägt die
  Auszahlung brutto, seine Herleitung nennt brutto, Abzug und netto; daneben steht der
  Abzug als eigener Posten („Steuer und KV auf die Auszahlung“, Quelle `annahme`) in der
  Gruppe „Policen ausgezahlt“, deren Summe das ist, was ins Depot kommt. In keinem Block
  und nicht in der Sparrate. `Year.abzug_cents` hält ihn fest, `closing_cents` zieht ihn
  ab, und die Zeile unter dem Rechenweg nennt „− Abzug auf die Auszahlung“.
- **Beitrag nominal:** `_beitragsausgaben` misst je Vertrag, der eine Police speist, wie
  die Basis ihn zählt (dieselbe Messung wie das Vertragsende, `_vertragsjahr`), und
  `_beitragsposten` gibt den Inflationsanteil als Posten „<Vertrag>: Beitrag bleibt nominal“
  (Quelle `regel`) im Block des Vertrags zurück. Ein eigener Posten statt einer Zerlegung
  der Kategorie, weil die Kategorie weitere Reihen trägt und ihre Herleitung die gemessene
  Zahl beschreibt. Das Ende dieses Vertrags (`_vertragsende_posten`) zieht ohne Inflation
  ab. Die Ausnahme `schon` gilt für ihn nicht mehr: Eine Wegfall-Zeile zieht ihn nur in
  ihren Monaten ab, das Ende zählt die übrigen (`pausen`). Sonst bliebe nach einer Zeile,
  die vor der Auszahlung endet, die Ausgabe ohne Police stehen (ein Test hält es fest).
- **Barista-Zeile:** `_fortschritt_zeile` ruft `ziele.hochgerechnet` und zeigt dessen
  Prozentwert; ein Ziel ohne Stichtag oder mit einer Basis quer zu den Töpfen bekommt nur
  „heute“, wie auf `/ziele`. Der Musterhaushalt bekommt dafür das Ziel `barista-fire`.
- **Herleitung:** Beitrag und Rendite einer Police nennen die Restmonate einmal („3 × 50,00 €
  in den 3 Restmonaten“); der Rest des Topfs ohne Police rechnet weiter linear mit
  `× 3/12`.
- Die Tests in `tests/test_policen.py` setzten ihre Annahmedatei mehrfach unter demselben
  Pfad neu, und `assumptions` hält gelesene Dateien im Zwischenspeicher: Die Läufe mit
  anderem Depotsatz im selben Test lasen die erste Datei. `_annahmen` setzt ihn zurück.
- Weitere Stellen, die ein Ziel mit `frei_cents` messen: `Projection.pct_of_target`, das
  der Befehl `finctl jahre` zeigt (letztes Jahr, ohne Basis und Stichtag). Keine Seite.
  `wirkung.py` und `/ziele` nehmen schon `ziele.hochgerechnet`.

**Abgenommen am 07.10.2026 (Opus).** `pruefen` nachgerechnet: Unterschiede nur auf den
Seiten, die P.2b nennt. `/renten`, `/annahmen`, `/konten`, Hauptbuch und Kontoprognose
sind gleich. Die Vorzeichen geprüft:
- Die Basis zieht die Ausgabe mit Inflation ab, der Posten „Beitrag bleibt nominal“ gibt
  den Inflationsanteil zurück. Netto bleibt der Betrag laut Vertrag.
- Nach der Auszahlung zieht das Vertragsende genau diesen Betrag ab, und es bleibt kein
  Rest.
- In den Monaten einer Wegfall-Zeile zieht die Zeile ihn ab und das Vertragsende nicht.

Die Barista-Zeile und das Ziel auf `/ziele` zeigen denselben Wert. Er ist gegenüber der
Referenz leicht gestiegen, weil die Sparrate ohne die Inflation des Beitrags höher ist.
Die Auslegungen gelten. Dazu gehören der Abzug als eigener Posten in der Gruppe „Policen
ausgezahlt“ und der Fund zur Wegfall-Zeile mit Enddatum. `Projection.pct_of_target` bleibt
wie es ist. Die Referenz ist danach neu geschrieben.

### P.3 Notfallwert und Prüfwert zeigen (gleich in den Zahlen)

Entscheidungen 6 und 7. Vorher `docs/design_conventions.yaml` lesen.

- Der Monatsabschluss fragt im Abschnitt „Rentenversicherungen“ neben dem
  Policenwert den Rückkaufswert und die eingezahlten Beiträge ab, mit eigenem
  Stand. Gespeichert wird über `finctl/dateien.py`, Beträge gehen als Text an
  den Server.
- `/konten` zeigt bei jeder Position der Bestandsart Rentenversicherung den
  Notfallwert als Zusatz, etwa „im Notfall 20.000“, mit Herleitung
  (Rückkaufswert, Steuer auf den Ertrag, Stand).
- `/renten` zeigt bei einer Kapitalquelle mit `konto` den Prüfwert neben dem
  Modellwert.
- Browsertests: `.venv/bin/python -m pytest -m browser -n 0`.

**Fertig wenn:** `pruefen --nur-zahlen` ist grün. Die Textebene zeigt nur die
neuen Zusätze, und der Bericht legt sie bei.

**Umgesetzt am 07.10.2026.**
- **Rückkauf-Felder speichern:** `/api/bestand` nimmt `rueckkauf_cents`, `eingezahlt_cents`,
  `rueckkauf_policenwert_cents` (je als `<feld>_text`, vom Server gelesen) und `rueckkauf_as_of`.
  Ein leerer Rückkaufswert nimmt alle vier aus dem Overlay, ein leeres anderes Feld heißt
  „nicht bekannt“. Ein falsches Feld ist eine Antwort mit 400 und schreibt nichts. Im
  Monatsabschluss steht unter jeder Rentenversicherung eine Unterzeile mit den vier Feldern.
  Speichern ohne Änderung schreibt keine Datei, und der Verlauf der Position bleibt, wie er war.
- **Notfallwert:** `bestaende.notfallwert` (Rückkaufswert minus `steuer_quote` auf
  `max(Rückkaufswert − eingezahlt, 0)`; die Quote ist `ann.vorabpauschale()[1]`). Der Abschnitt
  „Policen im Notfall“ auf `/konten` zeigt Policenwert, Rückkaufswert, eingezahlt, Steuer,
  Notfallwert und Stand der Mitteilung; die Rechnung steht im Tooltip. Er zählt weder zum
  Notgroschen noch zum liquiden Vermögen (ein Test hält es fest).
- **Prüfwert auf `/renten`:** `jahre.pruefvergleiche` liefert den Satz, den auch die Herleitung
  der Auszahlung nennt (`_vergleichstext`); eine Stelle, ein Test, dass beide Seiten ihn tragen.
  `annahmen.eingaben_der_hochrechnung` ist das Lesen aus `_jahresrechnung`, herausgezogen, damit
  `/renten` genau die Eingaben von `/hochrechnung` nimmt.
- **Musterhaushalt:** `police-a` trägt den Fall „gleicher Stand“, `police-b` den Fall „Policenwert
  neuer, Policenwert der Mitteilung genannt, eingezahlt fehlt“.

Auslegungen, wo der Plan offen ließ:
- **Verschiedene Stände (Entscheidung 7):** „Verhältnis aus Rückkaufswert und Policenwert der
  Mitteilung“ braucht den Policenwert der Mitteilung. Steht er nicht am Eintrag, hilft der
  heutige Policenwert nicht (er gehört zu einem anderen Stand). Deshalb ein viertes, optionales
  Feld `rueckkauf_policenwert_cents`. Ist der Policenwert der Zeile neuer als die Mitteilung,
  gilt `Rückkaufswert × Policenwert ÷ Policenwert der Mitteilung`. Ist er gleich alt oder älter,
  gilt der Rückkaufswert, wie er steht. Fehlt der Policenwert der Mitteilung bei neuerem
  Policenwert, bleibt der Rückkaufswert auf seinem Stand, und die Zeile sagt „Verhältnis fehlt“.
  Ändert ein Speichern den Policenwert, dessen Stand der der Mitteilung ist, hält der Server den
  alten als `rueckkauf_policenwert_cents` fest (`bestaende.policenwert_festhalten`), sonst ginge
  das Verhältnis mit dem ersten späteren Speichern verloren. Ein neuer Rückkaufswert wirft den
  alten Policenwert der Mitteilung weg.
- **`eingezahlt_cents` fehlt:** Die Steuer fällt auf den ganzen Rückkaufswert, der Notfallwert
  steht als Untergrenze da („mind.“, Tooltip nennt den Grund). Vorsichtig, weil ein
  Notfallwert zu hoch gefährlicher ist als zu niedrig; ohne Steuer zu rechnen wäre die
  freundlichere Annahme.
- **`eingezahlt` wird nicht fortgeschrieben:** Beiträge seit der Mitteilung zählen als Ertrag,
  die Steuer fällt eher zu hoch aus (Notfallwert zu niedrig). Fund unten.
- **`/konten` hatte keine Positionen:** Die Seite zeigt Konten; der Plan nennt sie für den
  Notfallwert. Er steht jetzt in einem eigenen Abschnitt unter der Kontentabelle.
- **Zahlenebene von `pruefen`:** Sie zählt jede Zahl, die auf einer Seite steht. Ein neu
  angezeigter Wert ist deshalb ein Unterschied der Zahlenebene, auch wenn keine bestehende Zahl
  sich ändert. „Gleich in den Zahlen“ heißt hier: nur neue Zeilen, keine geänderte oder
  fehlende (im Bericht belegt).

**Abgenommen am 07.10.2026 (Opus).**
- **`pruefen --nur-zahlen` nachgerechnet:**
  - Auf `/konten` und `/renten` kommen nur Zeilen dazu.
  - Weg fällt nur der alte Dateizähler im Konfigurationsfuß, der neue steht daneben.
  - Hauptbuch, `/hochrechnung`, `/ziele`, `/annahmen` und Kontoprognose sind gleich.
- **Fertig:** So erfüllt P.3 sein Kriterium. Die Auslegung von „gleich in den Zahlen“ gilt
  für jeden Teilschritt, der nur Anzeigen hinzufügt.
- **Auslegungen:** Sie gelten. Dazu gehören das vierte Feld für den Policenwert der
  Mitteilung und „mind.“ bei fehlendem `eingezahlt`.
- **`policenwert_festhalten`:** Es hält den alten Policenwert nur fest, wenn sein Stand der
  der Mitteilung ist. Ein späterer Policenwert gerät also nicht als Policenwert der
  Mitteilung in den Eintrag.
- **Notfallwert in einem eigenen Abschnitt auf `/konten`:** Er bleibt dort, bis Schritt 6
  die Oberfläche ordnet.
- **Der fehlende Fortschritt von `eingezahlt`:** Er geht in die vorsichtige Richtung, und es
  gibt keinen Teilschritt dafür (siehe Gefundene Abweichungen).
- **Referenz:** Sie ist danach neu geschrieben.

Damit ist Schritt 4b erledigt.

## Nicht in diesem Schritt

- Die betriebliche Altersvorsorge mit Teilzeit: eigener Schritt,
  `docs/schritt_teilzeit_bav.md`.
- **Verrentung** und die genaue Besteuerung einer Kapitalauszahlung.
- **Kapital ohne Position** (Rentenquelle `art: kapital` ohne `konto`, etwa
  eine betriebliche Altersvorsorge, die nur der Arbeitgeber zahlt) bleibt in
  diesem Schritt, wie es ist: einmal zu `ab` der Betrag der Mitteilung, minus
  Abzug. Ihr Modell mit Teilzeit kommt in `docs/schritt_teilzeit_bav.md`. Der
  Haushalt zahlt keinen Beitrag, und kündigen kann er nicht. Es gibt also
  weder Umschichtung noch Notfallwert, und die Hochrechnung kann die Beiträge
  des Arbeitgebers nicht kennen. Der Wert der Mitteilung ist hier die beste
  Zahl. Nicht als Position mit Bestandsart Rentenversicherung anlegen: Sie
  zählte sonst zum liquiden Vermögen.

## Gefundene Abweichungen

(Hier trägt jede Sitzung ein, was nicht in den Plan passt.)

- **P.2, Entscheidung 4, Beitrag nominal: Nein, die Ausgabe wächst mit der Inflation.**
  `_jahresposten_gemessen` schreibt jede Kategorie der Basis mit `ann.grow` fort, auch die
  Reihen mit Takt; Schritt 4 hat den Betrag je Termin eingeführt, nicht seine Inflation
  abgeschaltet. In die Police fließt nominal der Betrag am Vertrag, die Ausgabe wächst
  darüber hinaus: Der Unterschied (Inflationsanteil) geht als Ausgabe ohne Gegenwert weg,
  und beim Ende des Vertrags fällt die Ausgabe mit demselben Faktor weg (kein Rest).
  Ändert Zahlen; **Schritt:** P.2b für den Beitrag einer Police (Entscheidung 4).
  Ob Reihen mit Takt allgemein nominal fest bleiben, ist offen und gehört nicht hierher.
  **Erledigt in P.2b** (für den Beitrag einer Police).
- **P.2, Wegfall nimmt nominal, die Basis wächst:** `szenarien.jahreswirkung` zieht den
  gemessenen Betrag ohne Inflation ab (bestand vor P.2). Eine Wegfall-Zeile über den
  Beitrag lässt deshalb einen wachsenden Rest der Ausgabe stehen, und `_vertragsenden`
  nimmt die Reihe in dem Fall aus (`schon`), sodass er auch nach der Auszahlung bleibt.
  Der Test gegen Doppelzählung rechnet deshalb ohne Inflation. **Schritt:** P.2b.
  **Erledigt in P.2b**; der Test rechnet jetzt auch mit Inflation und hält genau.
- **P.2, der pauschale Abzug trifft die größere Auszahlung aus dem Tagesgeld:** Er wird
  im Block `rente` aus dem Tagesgeld bezahlt (Entscheidung 5). Zahlt eine Police vor dem
  Rentenbeginn aus, kann das Tagesgeld im Jahr der Auszahlung ins Minus fallen
  (`reicht_bis` rutscht davor). Auf der Entwicklungskopie trifft das die größere Police.
  Der Abzug trifft auch die eingezahlten Beiträge (ein Test hält es fest).
  **Schritt:** P.2b, netto: Der Abzug geht von der Auszahlung ab (entschieden bei der
  Abnahme von P.2). **Erledigt in P.2b.**
- **P.2, das Alter des Stands fließt nicht ein:** Die Hochrechnung rechnet den getippten
  Stand ab dem Rechenbeginn, auch wenn er älter ist; der Prüfwert-Vergleich erbt das. Eine
  Police mit einem Stand von vor einem halben Jahr liegt deshalb darunter. Wer den Stand zu
  seinem Datum (`as_of`) nähme, bräuchte es in den Eingaben. **Schritt:** keiner, nicht
  P.3 (der ist gleich in den Zahlen). Der Stand wird im Monatsabschluss aktuell gehalten;
  P.3 fragt ihn dort mit eigenem Stand ab. Ein Fortschreiben ab `as_of` bräuchte einen
  eigenen Teilschritt: Die Hochrechnung finge dann mit einem anderen Vermögen an als
  `/konten`.
- **P.2, der Beitrag kommt vom Vertrag, nicht aus der Messung:** Hört eine Reihe auf zu
  buchen, ohne dass `gekuendigt_zum` steht, fehlt ihre Ausgabe in der Basis, die Police
  bekommt aber weiter den Beitrag. **Schritt:** keiner; wer kündigt, trägt es ein.
- **P.2, Werte des Haushalts:** `kosten_pa`, `beitrag` und `pruefwert` beider Policen
  stehen nur in `renten_custom.yaml` der Entwicklungskopie und gehören beim Umstieg in den
  echten Datenordner. `cents` und `herleitung` in `renten.yaml` sind überholt; die Seiten
  zeigen sie weiter als „laut Schreiben“.
- **P.2b, `Projection.pct_of_target` misst ohne Stichtag und Basis:** Der Befehl `finctl jahre`
  zeigt das Ziel gegen `frei_cents` des letzten Jahres der Rechnung, mit dem skalierten
  Betrag je Szenario (`target_under`). Das ist ein Vergleich von Szenarien, keine Seite;
  dass er ein Ziel anders misst als `/ziele`, ist beabsichtigt oder nicht, entscheidet der
  Haushalt. **Schritt:** keiner.
- **P.2b, die Notiz zur Barista-Zeile stimmte nicht:** Die Abnahme von P.2 schrieb, das Ziel
  zähle in der Entwicklungskopie die Policen mit, weil keine Basis eingetragen sei. Es
  trägt eine Basis ohne Policen; nur die alte Zeile maß ohne sie und zählte deshalb die
  Policen mit. Die Zeile fällt darum stärker, als der Plan es sagt (siehe Bericht P.2b).
  **Schritt:** keiner.
- **P.3, `/konten` zeigte keine Position:** Der Plan setzt den Notfallwert dorthin; die Seite ist
  die Kontoprognose. Abschnitt „Policen im Notfall“ unter der Kontentabelle. **Schritt:** keiner;
  gehört der Notfallwert lieber in den Monatsabschluss oder auf `/ziele`, ist es ein Umzug des
  Abschnitts.
- **P.3, `pruefen --nur-zahlen` kann bei neu angezeigten Werten nicht „gleich“ sein:** Die
  Zahlenebene vergleicht jede Zahl einer Seite. **Schritt:** keiner; der Maßstab für P.3 ist
  „nur Zeilen dazu“.
- **P.3, `eingezahlt_cents` altert:** Mit dem Stand der Mitteilung eingetragen, ohne die Beiträge
  seither. Der Notfallwert einer Police, deren Policenwert neuer ist, versteuert sie als
  Ertrag und fällt zu niedrig aus. **Schritt:** eigener Teilschritt möglich: Beiträge des
  Vertrags seit dem Stand dazuzählen (Betrag und Takt stehen am Vertrag). Nicht P.3.
- **P.3, Policenwert und Rückkaufswert aus verschiedenen Mitteilungen:** Ist der Policenwert
  einer Position neuer als ihre Mitteilung und der Policenwert der Mitteilung nicht genannt,
  zeigt die Seite „Verhältnis fehlt“. **Schritt:** keiner; die Zeile im Monatsabschluss fragt
  das Feld ab.
- **P.3, Prüfwert bei altem Stand:** `/renten` zeigt das Modell gegen den Prüfwert. Eine Police
  mit einem Stand von vor Monaten liegt darunter (siehe „Das Alter des Stands fließt nicht ein“
  oben), der Prüfwert vergleicht also zum Teil das Alter des Stands. **Schritt:** keiner.
- **P.3, Werte des Haushalts:** Rückkaufswert, eingezahlt, Policenwert der Mitteilung und Stand
  beider Policen stehen nur in `balances_custom.yaml` der Entwicklungskopie (eingetragen über
  `/api/bestand`, den Weg des Monatsabschlusses) und gehören beim Umstieg in den echten
  Datenordner.
