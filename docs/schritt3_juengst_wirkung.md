# Schritt 3: Jüngst und Wirkung

Arbeitsplan für die Umsetzung, geschrieben für ein Modell, das ihn Teil für
Teil abarbeitet (Claude Sonnet). Gesamtplan: `docs/Neufassung_plan.md`.
Begriffe: `CONTEXT.md`. Stand des Codes beim Schreiben: nach Schritt 2
(`eca82f7`). Vorbild für Aufbau und Regeln: `docs/schritt2_fortschreibung.md`.

## Ziel in einem Satz

Wer einen sparsamen Monat hat, sieht es: Die Hochrechnung rechnet wahlweise im
Tempo der letzten drei Monate, die Ziele zeigen beide Tempi nebeneinander, und
der Monatsabschluss zeigt, wie weit jedes Ziel sich gegenüber dem Vormonat
bewegt hat und warum.

## Entscheidungen (Opus, 04.10.2026)

Diese Punkte sind festgelegt. Eine Sitzung, die einen davon für falsch hält,
hört auf und berichtet, statt ihn anders umzusetzen.

1. **Jüngst ist ein Fenster der Summe, kein eigenes Rechenverfahren.** Im
   Glossar ist Jüngst ein Verfahren, weil der Haushalt es so erlebt. Im Code
   ist es dieselbe Summe aufs Jahr wie in der Hochrechnung, nur über die
   letzten drei vollständigen Monate des Fensters (`Regel.fenster =
   "juengst"`). Gemessen wird weiter das ganze Fenster: Eine Kategorie, die in
   den letzten drei Monaten nichts gebucht hat, bleibt mit null im Rechenweg
   stehen und verschwindet nicht. So zeigen beide Tempi dieselbe Menge Posten
   (Abweichung 2.4 „`verfahren.summe` gegen die anderen“).
2. **Jüngst gilt in Schritt 3 nur im Block `konsum` und nur für Kosten.** Der
   Plan sagte „Kategorien ohne Fixkosten-Merkmal“. Das hätte auch `steuern`
   und `immobilie` getroffen, und dort sind die meisten Buchungen Klumpen
   (eine Steuernachzahlung, eine Reparatur), keine Gewohnheit. Eine
   Nachzahlung in den letzten drei Monaten würde mit vier malgenommen.
   Einnahmen bleiben ebenfalls beim Schnitt: Ein Nebenjob, der einmal im
   Jahr zahlt, wäre in drei Monaten null oder das Vierfache. Mit dem Takt aus
   Schritt 4 wird die Regel „jede Reihe ohne festen Takt“, wie es das Glossar
   sagt.
3. **Der Block bekommt seine Regeln als Wert.** `Vorschau` erhält
   `regeln_je_block: Mapping[str, Regeln]` (leer als Vorgabe). Steht der Block
   einer Reihe darin, gilt dessen Tabelle, sonst `regeln`. Nur mit
   `je_block=True` erlaubt; sonst `ValueError`.
4. **„Im Schnitt“ bleibt die Vorgabe.** Alle bestehenden Zahlen bleiben gleich.
   Jüngst ist eine zweite Rechnung daneben, keine Umstellung.
5. **Der Haushalt wählt das Tempo auf der Seite, der Server rechnet.**
   `/hochrechnung?tempo=juengst` rechnet die ganze Tabelle im Tempo der
   letzten drei Monate. Ein Link schaltet um, kein Skript rechnet. Die Wahl
   wird in Schritt 3 nicht gespeichert.
6. **Wirkung heißt: gegenüber dem Monat davor.** Verglichen werden zwei
   Hochrechnungen: eine zum Stichtag S, eine zum Stichtag S minus einen Monat,
   jede mit Buchungen nur bis zu ihrem Stichtag (wie der Treffer-Check).
   Gespeichert wird keine Hochrechnung.
7. **Beide Rechnungen nehmen Annahmen, Ziele, Planzeilen, Kredite und
   Verpflichtungen, wie sie heute stehen.** Die Wirkung zeigt, was die Daten
   bewegt haben, nicht was der Haushalt umgestellt hat. Die Seite sagt das in
   einem Satz („unter den heutigen Annahmen“). Damit fällt „Annahmen“ als
   Ursache weg; `CONTEXT.md` ist angepasst.
8. **Getippte Stände bekommen einen Verlauf.** Für die Rechnung zum Stichtag
   davor braucht es den Stand jedes Depots und jeder Police von damals. Heute
   überschreibt jede Eingabe den alten Stand. Ab Schritt 3 bleibt je Position
   und Periode des Monatsabschlusses ein Eintrag stehen, in
   `config/balances_custom.yaml` unter `verlauf`. Das ist kein gespeicherter
   Rechenstand, der veralten kann, sondern ein Beleg: „am Monatsabschluss
   08/2026 stand das Depot bei X“. Belegte Stände (Konten mit Auszügen) kommen
   weiter aus dem Hauptbuch (`stichtag.saldo_zum`).
9. **Die Ursachen werden nacheinander ausgetauscht, und ihre Summe ist exakt
   die Wirkung.** Die Eingaben der Hochrechnung zum Stichtag davor werden
   Gruppe für Gruppe durch die von heute ersetzt, in fester Reihenfolge. Jeder
   Tausch ergibt eine ganze Hochrechnung; die Differenz zur vorigen ist die
   Wirkung dieser Ursache. Nach dem letzten Tausch steht genau die
   Hochrechnung von heute da. Es gibt keinen Rest, der „Sonstiges“ hieße.
   Reihenfolge und Gruppen:

   | Ursache | Was ausgetauscht wird |
   |---|---|
   | **Der Monat** | Anfangsbestand (alle Töpfe, Einstand, Policen und Tagesgeld je Konto) **zusammen** mit Basisjahr, vergangenen Monaten und der Mitte des Fensters |
   | **Tempo: <Block>** | je Block aus `FROM_BASE` dessen Jahreswerte je Kategorie, ein Tausch je Block, in der Reihenfolge von `FROM_BASE` |
   | **Gehalt** | der gemessene Median |
   | **Planzeilen** | die Messungen der Planzeilen, die Vertragsenden und die Verkäufe (`Eingaben.planzeilen`) |

   Nach dem Review von 3.1 festgelegt: Die einmaligen Planzeilen, die die
   Messung auslässt, sind keine eigene Eingabe. Der Ausschluss wirkt beim
   Messen und steckt in `base`, und weil die Planzeilen für beide Stichtage
   gelten, wie sie heute stehen (Entscheidung 7), schließen beide Rechnungen
   dieselben Buchungen aus. Eine Wirkung davon erscheint unter „Tempo“ des
   Blocks, in dem die Buchung lag.

   Anfangsbestand und Zeit stehen in **einer** Gruppe. Getrennt zeigte „Zeit“
   ein großes Minus (ein Monat Sparen fehlt in der Rechnung) und „Bestand“ ein
   großes Plus (er liegt jetzt auf dem Konto), und beide hoben sich fast auf.
   Zusammen bleibt genau das übrig, was der Monat anders brachte als erwartet.
   Ging der Monat wie erwartet, ist „Der Monat“ nahe null, und ein Test hält
   das fest.
10. **Warum der Monat anders kam, steht daneben, nicht darin.** Unter „Der
    Monat“ zeigt die Seite die Zeile des Treffer-Checks für diesen Monat
    (`treffer.jahresbasis`, Ist gegen Soll je Block, in Euro im Monat) und die
    Kursbewegung der Depots (Änderung des getippten Stands minus den Buchungen
    unter `investment/` im Monat). Das sind Hinweise in Euro des Monats, kein
    Rechenweg der Wirkung: Ihre Summe ist nicht die Wirkung, weil die
    Wirkung bis zum Stichdatum des Ziels mitwächst. Die Seite sagt das.
11. **Gemessen wird die Zahl, die `/ziele` als Hochrechnung zeigt:** der Wert
    am Stichdatum des Ziels, mit Töpfen und Notgroschen wie dort. Die Funktion
    dafür steht heute als Closure `wert` in `finctl/web/routen/ziele.py` und
    zieht nach `finctl/forecast/ziele.py`, damit `/ziele` und die Wirkung
    dieselbe Rechnung benutzen. Ein Ziel ohne Stichdatum oder ohne
    Hochrechnung bekommt nur die Änderung seines Balkens (Bestand heute gegen
    Bestand zum Stichtag davor), ohne Aufteilung.
12. **Wirkung in beiden Tempi.** Der Monatsabschluss zeigt je Ziel die Wirkung
    im Schnitt und im Tempo der letzten drei Monate. Im Schnitt ist „Tempo:
    konsum“ klein (ein Monat von zwölf), im Tempo der letzten drei Monate
    groß. Genau dieser Unterschied ist der Grund für Schritt 3.

13. **Zinsen auf Tagesgeld werden gerechnet, nicht fortgeschrieben (3.2b).**
    Heute zählt die Hochrechnung sie doppelt: Der Topf Tagesgeld wächst mit
    `kapital.rendite_nominal_pa`, und die gebuchten Zinsen der letzten zwölf
    Monate (`einkommen/zinsen`, Block `einkommen_sonst`) werden zusätzlich als
    Einnahme fortgeschrieben, mit der Inflation statt mit dem Stand. Ebenso
    wird die gebuchte Kapitalertragsteuer (`steuern/kapitalertragsteuer`)
    fortgeschrieben, während auf die gerechneten Zinsen keine Steuer anfällt.
    Ab 3.2b fallen beide Kategorien aus der Fortschreibung der Hochrechnung
    (`Vorschau.ausser`), und die Rechnung bildet Zinsen und Steuer selbst. Die
    Kennungen stehen als Konstante neben den anderen festen Kennungen der
    mitgelieferten Taxonomie (wie `einkommen/gehalt`). Die Kontoprognose
    bleibt, wie sie ist: Für die Frage nach dem Dispo genügen die gemessenen
    Monatszinsen. Der Treffer-Check bleibt auch, er vergleicht Gebuchtes.
14. **Ein Zinssatz je Konto, datiert.** In `config/zinssaetze_custom.yaml`
    steht je Konto eine Liste von Sätzen mit `ab` und optional `bis`
    (Aktionszins). Bearbeitet wird sie auf `/annahmen` im Abschnitt Kapital,
    neben dem langfristigen Satz. Welcher Satz in einem Monat gilt:
    - der Eintrag, in dessen Zeitraum der Monat fällt;
    - sonst, wenn das Konto überhaupt Einträge hat, der langfristige Satz
      (`kapital.rendite_nominal_pa`): ein Aktionszins endet, das Konto zahlt
      danach weiter etwas;
    - sonst nach Art: ein Tagesgeld bekommt den langfristigen Satz, ein
      Girokonto 0 %. Ein Verrechnungskonto mit Zinsen hat die Art `giro` und
      bekommt seinen Satz deshalb nur über einen Eintrag.
    Ohne jeden Eintrag rechnet ein Haushalt also wie heute, nur dass
    Girokonten nichts mehr verdienen.
15. **Der Topf hat einen Satz je Jahr, gewichtet mit den heutigen Ständen.**
    Die Hochrechnung kennt nur den Topf Tagesgeld, keine einzelnen Konten.
    Satz des Jahres = Summe über die Konten im Topf (positive Stände heute)
    von Stand mal Satz des Kontos in diesem Jahr, geteilt durch die Summe der
    Stände. Der Satz eines Kontos in einem Jahr ist das Mittel seiner zwölf
    Monatssätze, im Basisjahr das der Restmonate. Was künftig dazukommt,
    verzinst sich mit derselben Mischung; das ist eine Vereinfachung, und der
    Rechenweg sagt es. Ist der Topf heute leer, gilt der langfristige Satz.
    Der Rechenweg der Zinszeile nennt je Konto Anteil und Satz.
16. **Kapitalertragsteuer einmal im Jahr über alle Kapitalerträge, mit dem
    Sparerpauschbetrag.** Steuer = Steuersatz mal (Zinsen Tagesgeld +
    Vorabpauschale + Gewinnanteil der Verkäufe − Pauschbetrag), nicht unter
    null. Der Pauschbetrag wird in dieser Reihenfolge verbraucht: Zinsen,
    Vorabpauschale, Verkauf. Die Reihenfolge entscheidet nur, in welcher Zeile
    des Rechenwegs der Abzug steht; die Summe ist dieselbe. Jede Steuer wird
    aus dem Topf bezahlt, in dem der Ertrag entstand.
    - `kapital.sparerpauschbetrag_cents`, Vorgabe in
      `finctl/vorgaben/assumptions.yaml`: der gesetzliche Betrag für eine
      Person. Wer zusammen veranlagt wird, trägt den doppelten auf `/annahmen`
      ein. Der Betrag ist nominal fest und wächst nicht mit der Inflation;
      ändert ihn das Gesetz, trägt der Haushalt den neuen ein.
    - Kirchensteuer steckt im Steuersatz, den der Haushalt auf `/annahmen`
      setzt. Eine eigene Zahl gibt es dafür nicht.
    - Freistellungsaufträge je Bank werden nicht nachgebildet. Über das Jahr
      zählt die Summe, den Rest holt die Steuererklärung zurück.
    - Policen bleiben ohne Steuer (Versicherungsmantel), die Teilfreistellung
      bleibt draußen, wie bisher.

## Was „gleich“ und was „gewollt“ heißt

Die Teilschritte 3.1, 3.2 und 3.4 sind **gleich**: Keine Zahl und kein Text
auf einer Seite ändert sich. Fertig heißt wie in Schritt 2:

```bash
export FINCTL_DATEN="$HOME/Library/Application Support/Finance OS Entwicklung"
.venv/bin/python -m pytest -q
FINCTL_TESTDATEN=muster .venv/bin/python -m pytest -q
.venv/bin/python tests/referenz.py pruefen
```

Die Teilschritte 3.3 und 3.6 sind **gewollt**: Sie fügen Zahlen und Text auf
genau benannten Seiten hinzu. Für sie gilt:

1. `pruefen` zeigt Unterschiede **nur** auf den Seiten, die der Teilschritt
   nennt, und dort **nur hinzugefügte** Zeilen (im Diff `+`, kein `-`). Eine
   geänderte oder fehlende alte Zahl ist ein Fehler im Code.
2. Die Sitzung schreibt die Referenz **nicht** neu. Sie committet den Code und
   legt dem Bericht die Ausgabe von `pruefen` bei (gekürzt auf die
   Unterschiede). Nach dem Review wird die Referenz in einem eigenen Commit
   neu geschrieben (`schreiben`).

Teilschritt 3.2b ist **gewollt** und **ändert** Zahlen, statt nur welche
hinzuzufügen. Für ihn gilt: `pruefen` zeigt Unterschiede nur auf Seiten und
Ableitungen, die aus der Hochrechnung lesen (`/hochrechnung`, `/ziele`,
`/annahmen`, die Auswertung, die sie zeigt, und `ableitung/` der
Hochrechnung), und keinen im Hauptbuch, auf `/konten` oder in der Ableitung
der Kontoprognose. Der Bericht nennt die Unterschiede und erklärt die größten.

Ändert ein Teilschritt Vorlagen, Routen oder Skripte, kommt
`.venv/bin/python -m pytest -m browser -n 0` dazu.

## Regeln für jede Sitzung

1. Ein Teilschritt pro Sitzung. Lies vorher `CLAUDE.md`, `CONTEXT.md`, diesen
   Plan und die Abschnitte „Gefundene Abweichungen“ in
   `docs/schritt2_fortschreibung.md`.
2. Starte `pruefen` erst, wenn du keine Datei mehr änderst.
3. Bleibt ein Gleich-Schritt rot oder zeigt ein Gewollt-Schritt ein `-`, hör
   auf und berichte.
4. Keine echten Beträge, Namen oder Konten in Code, Tests, Kommentaren und
   Doku (`tests/test_leck.py`). Tests rechnen mit erfundenen, runden Reihen.
5. Rechnen auf dem Server. Kein Skript rechnet einen Betrag
   (`tests/test_rechnen_im_browser.py`).
6. Seitenzeiten messen, vorher und nachher, mit derselben Methode: zweimal
   laden, den zweiten Aufruf zählen (`TestClient`). Stand beim Schreiben:
   `/ziele` rund 1,1 s, `/hochrechnung` rund 2,0 s, `/monatsabschluss` rund
   1,9 s.
7. Was dir zwischen den Rechnungen auffällt und nicht in deinen Teilschritt
   gehört, kommt unten unter „Gefundene Abweichungen“, mit Warum und Schritt.

## Die Teilschritte

### 3.1 Die Hochrechnung in Eingaben und Rechnung teilen (gleich)

Heute liest `jahre.project()` seine Eingaben (Messung, Gehalt, Planzeilen,
Kredite, Renten, Objekte, Annahmen) und rechnet in derselben Funktion Jahr für
Jahr. Für Jüngst muss die Rechnung zweimal laufen, für die Wirkung ein Dutzend
Mal. Die Eingaben dürfen dafür nur einmal gelesen werden.

- `Eingaben`: eine `frozen` Dataclass mit allem, was `project()` heute vor der
  Jahresschleife liest oder ableitet: Töpfe, Einstand, Policen je Konto,
  Puffer, Sätze, Basisjahr, vergangene Monate, Fenster, `base` (Jahreswert je
  Block und Kategorie), Messungen der Planzeilen, Vertragsenden, Verkäufe,
  Tilgungspläne, Gehaltsmedian, Teilzeitzeilen, Rentenbeginn, Rentenquellen,
  Objektprognosen, Depotkonten. Die Felder werden so gruppiert, dass die
  Gruppen aus Entscheidung 9 sich als Ganzes tauschen lassen (zum Beispiel
  `dataclasses.replace` mit einem Feld je Gruppe oder eine verschachtelte
  Dataclass je Gruppe; die Sitzung wählt und begründet).
- `eingaben(conn, *, ...) -> Eingaben` liest. `rechnen(e: Eingaben, *,
  end_year, target_cents) -> Projection` rechnet und fasst weder `conn` noch
  `config/` an. Ein Test hält das fest (wie `tests/test_fortschreibung.py` die
  Importe des Kerns).
- `project()` bleibt mit seiner heutigen Signatur und ruft beides.
- Seitenzeiten dürfen nicht steigen.
- Zusätzlich messen und berichten: wie lange `rechnen()` allein dauert. Davon
  hängt ab, ob die Wirkung in 3.5 zwölf Rechnungen je Tempo verträgt.

**Fertig wenn:** gleich.

### 3.2 Jüngst im Verfahren (gleich)

- `verfahren.Regel.fenster` bekommt den Wert `"juengst"`. `wahl` gibt
  `summe` dann nur die Monate ab `ende_monat` minus zwei Monaten (drei
  Monate, einschließlich) und `fenster_monate = min(3, fenster_monate)`.
  Kategorien ohne Buchung in diesen Monaten ergeben null, mit Posten
  (Entscheidung 1). Der Rechenweg sagt es: „Summe … über die letzten 3
  Monate (07/2026–09/2026), aufs Jahr …“.
- `HOCHRECHNUNG_JUENGST: Regeln`: wie `HOCHRECHNUNG`, nur `KOSTEN` mit
  `fenster="juengst"`. Einnahmen und Fixkosten bleiben beim ganzen Fenster.
- `Vorschau.regeln_je_block` (Entscheidung 3), in `fortschreibung()`
  ausgewertet.
- `jahre._hochrechnung(f, ohne, tempo)` mit `tempo: Literal["schnitt",
  "juengst"] = "schnitt"`; bei `"juengst"` `regeln_je_block={"konsum":
  HOCHRECHNUNG_JUENGST}`. `eingaben(..., tempo=...)` reicht es durch.
- Tests mit erfundenen Reihen: eine Kategorie, die in den letzten drei Monaten
  nichts hat (null mit Posten); eine Einnahme im Block `konsum` (bleibt beim
  Schnitt); eine Kostenkategorie in `steuern` (bleibt beim Schnitt); ein
  Fenster mit nur zwei Monaten (teilt durch zwei).
- Keine Seite benutzt `"juengst"` in diesem Teilschritt.

**Fertig wenn:** gleich.

### 3.2b Zinsen je Konto und Kapitalertragsteuer (gewollt)

Eingeschoben nach 3.2, mit eigener Nummer, damit die Verweise auf 3.3 bis 3.7
stimmen. Grundlage sind die Entscheidungen 13 bis 16. Läuft nach 3.2 und vor
3.3, damit die Referenz für diese Änderung allein neu geschrieben wird und der
Diff von 3.3 nur Jüngst zeigt.

- **Eingaben:** `Eingaben` bekommt die Zinssätze (gelesen) und die heutigen
  Stände je Konto im Topf Tagesgeld. Die Stände reicht der Aufrufer herein,
  wie heute `policen_je_konto` (`ziele.tagesgeld_je_konto(balances)` neben
  `ziele.policen_je_konto`). Aufrufer von `project()` sind die Routen
  `ziele`, `annahmen` und `auswertung` und `cli`; jeder reicht sie durch.
- **Fortschreibung:** Die zwei Kategorien aus Entscheidung 13 kommen in
  `Vorschau.ausser` der Hochrechnung. Der Rechenweg der Blöcke
  `einkommen_sonst` und `steuern` verliert damit je eine Zeile.
- **`kaskade`:** bekommt den Satz des Jahres (Entscheidung 15) statt des
  festen Satzes und `pauschbetrag`. Die Steuer auf Zinsen, Vorabpauschale und
  Verkauf wird nach Entscheidung 16 gemeinsam gerechnet. `kaskade` bleibt
  rein; ihre bisherigen Tests werden auf die neue Regel umgeschrieben, nicht
  gelöscht, und jede Änderung an einem erwarteten Wert steht im Bericht mit
  ihrem Grund.
- **Rechenweg:** Die Zeile „Tagesgeld“ nennt Topf, Satz des Jahres und dessen
  Zusammensetzung („Konto A 2,0 % auf 60 %, Konto B 0 % auf 40 %“). Neue
  Zeile „Kapitalertragsteuer auf Zinsen“. Die Zeilen „Vorabpauschale“ und
  „Steuer auf Depotverkauf“ nennen, wie viel Pauschbetrag sie verbraucht
  haben. Der feste Satz „ohne Teilfreistellung“ bleibt stehen.
- **`/annahmen`, Abschnitt Kapital:** eine Tabelle der Konten im Topf
  Tagesgeld mit ihren Sätzen (`ab`, `bis`, Satz), Hinzufügen und Löschen
  einer Zeile, und das Feld Sparerpauschbetrag. Schreiben über
  `finctl/dateien.py`, Prozent und Betrag als Text an den Server
  (`docs/design_conventions.yaml` vorher lesen). Speichern ohne Änderung
  ändert keine Datei (Browsertest).
- **Texte:** Der Satz auf `/hochrechnung` zu Depot und Steuer
  („26,375 % auf Gewinne, ohne Teilfreistellung“) nennt den Pauschbetrag.
- **Tests mit erfundenen, runden Zahlen:**
  - Zinsen unter dem Pauschbetrag: keine Steuer;
  - Zinsen darüber: Steuer nur auf den Rest;
  - Zinsen und Vorabpauschale teilen sich den Pauschbetrag in der Reihenfolge
    der Entscheidung;
  - die drei Regeln für den Satz eines Monats aus Entscheidung 14, auch
    Aktionszins mit `bis` und ein Monat vor dem ersten `ab`;
  - die Gewichtung aus Entscheidung 15, auch mit leerem Topf;
  - die Basis der Hochrechnung enthält keine der zwei Kategorien mehr.
- Der Musterhaushalt bekommt eine `zinssaetze_custom.yaml` mit einem
  Aktionszins, damit beide Läufe den Weg mit Einträgen gehen.
- Unter „Gefundene Abweichungen“: Treffer-Check und Hochrechnung behandeln
  Zinsen ab jetzt verschieden (gebucht gegen gerechnet).

**Fertig wenn:** Suite beide Läufe grün, Browsertests grün, `pruefen` wie
oben unter „gewollt“ für 3.2b beschrieben. Bericht mit dem Diff und für das
erste volle Jahr: Zinsen, Steuer und Sparrate vorher und nachher. Die
Referenz schreibt der Review.

### 3.2c Planzeilen auf gerechneten Kategorien (gewollt, Nachtrag zu 3.2b)

**Review von 3.2b (04.10.2026):** 3.2b ist richtig gebaut, aber nicht
fertig. Die Referenz wird erst nach 3.2c neu geschrieben, für beide zusammen.

Abgenommen aus 3.2b, mit Begründung:
- **Rentenlücke und Deckung steigen beziehungsweise sinken**, weil die Zinsen
  nicht mehr als passives Einkommen in `einkommen_sonst` zählen. Das ist
  gewollt: Was das Kapital abwirft, rechnet die Hochrechnung schon mit seinem
  Satz. Als passives Einkommen gezählt, senkte es das nötige Kapital mit dem
  Ertrag eben dieses Kapitals.
- **Der Sparerpauschbetrag gilt im Basisjahr anteilig.** Was vom Jahr schon
  gebucht ist, hat seinen Teil des Pauschbetrags schon verbraucht; genauer
  ginge es nur mit den gebuchten Erträgen des Jahres, und das lohnt nicht.
- **Ein Topf ohne eingetragene Sätze rechnet vorsichtiger als vorher**
  (Girokonten 0 %). Das ist die Folge von Entscheidung 14 und gewollt.

**Befund:** Eine Planzeile, deren Kategorie die Hochrechnung seit 3.2b
rechnet statt fortschreibt (`jahre.GERECHNET`), korrigierte bis dahin die
fortgeschriebenen Zinsen; etwa eine Betragszeile „Konto X zahlt ein Jahr
lang keine Zinsen“. Seit 3.2b stehen diese Zinsen nicht mehr in der Basis, und
die Zeile zieht in der Hochrechnung einen Betrag ab, der nirgends mehr steht.
Die Kontoprognose misst die Zinsen weiter; dort bleibt die Zeile richtig.

- In der Hochrechnung gilt eine Planzeile nicht, deren Kategorie in
  `jahre.GERECHNET` liegt (jede Art, die eine Kategorie trägt). Ihre Aufgabe
  übernimmt dort der Zinssatz je Konto. In der Kontoprognose gilt sie wie
  bisher.
- Sichtbar wird das an der Zeile selbst: Wo `/planung` die Planzeile zeigt,
  steht „gilt nur für /konten; die Hochrechnung rechnet Zinsen aus dem
  Zinssatz des Kontos (/annahmen)“.
- Auf `/annahmen` unter „Zinssätze je Konto“ steht bei einem Konto, für das
  eine solche Planzeile existiert, ein Hinweis mit ihrem Namen und Zeitraum.
  Die App trägt nichts selbst ein: Den Satz setzt der Haushalt.
- Tests mit erfundenen Daten: eine Betragszeile mit Kategorie Zinsen ändert
  die Hochrechnung nicht und die Kontoprognose wie bisher; dasselbe für eine
  Wegfallzeile.

**Fertig wenn:** Suite beide Läufe grün, Browsertests auf der
Entwicklungskopie grün, `pruefen` gegen die alte Referenz zeigt Unterschiede
nur auf den Seiten und Ableitungen, die 3.2b schon nennt, sowie auf
`/planung`. Bericht: Sparrate im ersten vollen Jahr nach 3.2b und nach 3.2c.

**Stand bei der Umsetzung (04.10.2026):**
- **Eine Funktion entscheidet:** `jahre.gilt_in_hochrechnung(line)` ist falsch, wenn die
  Kategorie der Zeile in `GERECHNET` liegt, gleich welche Art sie hat. `_planposten` und
  die Wegfall-Menge in `_vertragsenden` fragen sie; `jahre.ohne_wirkung_in_hochrechnung`
  liefert dieselben Zeilen für die Seiten. Die Kontoprognose (`konten._planposten`,
  `wegfall_posten`) fragt sie nicht und bleibt, wie sie war.
- **/planung:** Der Satz steht in der Spalte „zählt“ der Zeile, aus der Route
  (`_gerechnet_hinweise`), weil `_klammer.html` als Teilvorlage keinen Erklärtext trägt.
  Für Kapitalertragsteuer lautet er „… rechnet die Kapitalertragsteuer selbst“.
- **/annahmen:** Der Hinweis erscheint nur für Zeilen auf Zinsen, je Zeile eine Notiz
  unter der Tabelle (`div.note`), auch bei einem Konto ohne eigenen Satz. Eine Zeile ohne
  Konto nennt das Betriebskonto, wie die Kontoprognose. Für Kapitalertragsteuer gibt es
  dort keinen Hinweis: ein Zinssatz ersetzt sie nicht, der Steuersatz steht darüber.
- **Handbuch:** Der Satz dazu steht unter `/annahmen`, nicht unter `/planung`; der
  Abschnitt zur Planung ist schon an der Grenze von 200 Wörtern.

**Abgenommen am 04.10.2026** (`9cf3c76`). Die Referenz ist danach für 3.2b
und 3.2c zusammen neu geschrieben, Stichtag weiter 2026-10-02; die alte liegt
in `data/referenz_archiv/`. Die Kachel-Zahl in `einrichtung` und
`kontenregister` („1 von 12“) kommt von der neuen Stellschraube und ist
gewollt.

### 3.3 Jüngst auf `/hochrechnung` und `/ziele` (gewollt)

- **`/hochrechnung`:** `?tempo=juengst` rechnet die ganze Seite im Tempo der
  letzten drei Monate. Oben steht, welches Tempo gilt, und ein Link auf das
  andere. Ohne Parameter ist alles wie heute. Die Eingaben werden je Aufruf
  einmal gelesen.
- **Posten mit null bleiben im Rechenweg** (nach dem Review von 3.2
  festgelegt). `_jahresposten_gemessen` überspringt heute jeden Posten mit
  null Cent. Ab 3.3 bekommt jede Kategorie aus `Eingaben.base` ihre Zeile,
  auch mit null, in beiden Tempi. Im Tempo der letzten drei Monate ist
  gerade die Null die Nachricht („hier hast du zuletzt nichts
  ausgegeben“). Im Schnitt kommen dadurch nur Zeilen für Kategorien hinzu,
  die sich über das Fenster genau aufheben; der Diff von `pruefen` zeigt
  sie als `+` und der Bericht zählt sie.
- **`/ziele`:** Jedes Ziel mit Hochrechnung zeigt zwei Werte: „im Schnitt“
  (wie heute) und „im Tempo der letzten drei Monate“, je mit Prozent vom
  Zielbetrag. Dafür zieht die Closure `wert` nach
  `finctl/forecast/ziele.py` (Entscheidung 11), als Funktion, die eine
  `Projection` und ein Ziel nimmt und den Wert am Stichdatum liefert.
- Wörter auf der Seite: „im Schnitt der letzten 12 Monate“ und „im Tempo der
  letzten 3 Monate“. Die Zahl der Monate kommt aus dem Fenster, nicht aus dem
  Text (ein junges Hauptbuch hat weniger). In Code und Kommentaren heißt es
  Jüngst.
- `docs/design_conventions.yaml` vorher lesen. Ein zweiter Wert neben einem
  Betrag folgt der Konvention dort; fehlt eine, wird sie eingetragen.
- Seitenzeit von `/ziele` darf um höchstens die Dauer einer `rechnen()`
  steigen, nicht um ein zweites Einlesen.

**Fertig wenn:** Suite beide Läufe grün, Browsertests grün, `pruefen` zeigt
nur hinzugefügte Zeilen auf `/ziele` und `/hochrechnung` (ohne Parameter).
Bericht mit dem Diff. Die Referenz schreibt der Review.

**Abgenommen am 04.10.2026** (`e9611f7`), Referenz danach neu geschrieben.
Festgelegt im Review:
- **Der Zielbetrag ist einer, in beiden Tempi.** Auch beim Ziel aus der
  Rentenlücke, dessen Betrag aus der Hochrechnung im Schnitt folgt. Das
  Tempo zeigt, wo du am Stichdatum stehst, nicht wohin du willst; wanderte
  der Zielbetrag mit, bewegten sich Zähler und Nenner zugleich, und der
  Vergleich der Tempi wäre schwer zu lesen. Der Eintrag unter „Gefundene
  Abweichungen“ ist damit entschieden, nicht offen.
- **`base` und `base_monate` sind eine Gruppe.** 3.5 tauscht sie je Block
  zusammen, sonst nennt der Rechenweg das Fenster des anderen Stichtags.
- **Ein Test fiel im Muster-Lauf einmal aus**
  (`test_herkunft_summe_is_only_used_where_posten_are_summands`) und danach
  nicht wieder. Er liest den Syntaxbaum von `finctl/`; zur selben Zeit
  schrieb eine andere Sitzung im Checkout. Fällt er wieder aus, ohne dass
  jemand parallel schreibt: aufhören und berichten.

### 3.4 Stichtag als Eingabe und Verlauf der getippten Stände (gleich)

- **`eingaben(conn, *, bis: date | None = None, ...)`:** liest alles, was aus
  dem Hauptbuch kommt, nur bis zum Monatsende `bis`, als wäre heute der
  erste Tag des Folgemonats. Ohne `bis` wie heute. Das betrifft das Fenster
  (`abgleich.fenster`), den letzten vollständigen Monat, den Gehaltsmedian
  (`gehalt_median_cents(vor=...)` gibt es schon), die Messungen der
  Planzeilen (`szenarien.messung`), die Vertragsenden und die Verkäufe. Das
  sind genau die Stellen aus „Gefundene Abweichungen“ in Schritt 2, die noch
  selbst messen; jede bekommt ein `bis`, keine zieht in die Messung um (das
  ist Schritt 4).
- Ein Test: `eingaben(conn, bis=<letzter vollständiger Monat>)` ist gleich
  `eingaben(conn)`, wenn heute im Folgemonat liegt (Tag festnageln wie
  `tests/referenz.py`).
- **`date('now')` fällt aus `gehalt_median_cents`.** Der Zweig ohne `vor`
  ruft den Zweig mit `vor=date.today()`. Heute fragt er die Uhr von SQLite,
  und die hält `tests/referenz.py` beim Festnageln des Tages nicht an: Die
  Referenz misst das Gehalt also mit dem echten Datum. Die beiden Zweige
  zählen außerdem den ersten Monat verschieden (ab dem Tag gegenüber ab dem
  Monatsersten). Auf der Entwicklungskopie ergeben beide am 04.10.2026
  dieselbe Zahl. Zeigt `pruefen` trotzdem einen Unterschied beim Gehalt, hör
  auf und berichte.
- **Verlauf:** Jede Speicherung eines getippten Stands schreibt zusätzlich
  `verlauf[<position>][<periode>] = {cents, gewinn_cents, as_of}` in
  `config/balances_custom.yaml`, über `finctl/dateien.py`. `<periode>` ist die
  Periode, die der Monatsabschluss gerade schließt (`monatsabschluss`
  rechnet sie heute schon). Zweimal in derselben Periode gespeichert: der
  spätere Eintrag gilt. Einmalig, beim ersten Lesen ohne `verlauf`, wird der
  heutige Stand jeder getippten Position unter seiner Periode eingetragen,
  damit der nächste Abschluss schon einen Vormonat hat.
- `bestaende.zum(conn, stichtag) -> dict`: die Bestände zu einem früheren
  Stichtag, belegte aus dem Hauptbuch, getippte aus dem Verlauf. Fehlt einer,
  steht er in einer Liste `fehlt`, statt als null zu zählen.
- Keine Seite zeigt den Verlauf in diesem Teilschritt.

**Fertig wenn:** gleich. Dazu: Speichern ohne Änderung schreibt den Verlauf
nicht neu (Browsertest „Speichern ohne Änderung“ grün).

**Stand bei der Umsetzung (04.10.2026):**
- **`eingaben(bis=...)`:** `abgleich.letzter_vollstaendiger_monat` und `abgleich.fenster`
  nehmen `bis` und kappen auf dessen Monatsende (`min` mit dem Ende der Auszüge); ein
  `bis` hinter dem Hauptbuch macht den Monat nicht vollständiger. `abgleich.folgetag(bis)`
  ist „heute“ der Rechnung: Ohne `base_year` gilt dessen Jahr, und der Gehaltsmedian
  misst von dort. Planzeilen-Messungen und Vertragsenden lesen über das Fenster, die
  Verkäufe (`verkaeufe(..., bis=)`) messen Miete und Kosten im Fenster. Termin, Preis und
  Kredit eines Verkaufs bleiben, wie sie heute stehen (Entscheidung 7).
- **Zahl der Buchungen im Rechenweg eines gekündigten Vertrags:** `_vertragsende`
  zählte alle Buchungen der Reihe, auch die nach dem Fenster; jetzt nur die bis
  `f.bis`. Auf der Entwicklungskopie gibt es keine solche Buchung, der Text ändert sich
  dort nicht.
- **`gehalt_median_cents`:** Der Zweig ohne `vor` ruft `date.today()` statt `date('now')`
  in SQL; es gibt nur noch einen Zweig. Gezählt wird ab dem Monatsersten, `monate` Monate
  zurück. Auf der Entwicklungskopie ergaben alt und neu am 04.10.2026 dieselbe Zahl; ein
  Test nagelt `date.today()` in `jahre` fest und prüft, dass der Median ihm folgt.
- **Verlauf:** `balances_custom.yaml` unter `verlauf[<position>][<periode>] = {cents,
  as_of, gewinn_cents}`; `gewinn_cents` steht nur, wo er bekannt ist. `<position>` ist
  die Kennung des Overlays (`account_id`, sonst `name`). `<periode>` ist der Monat, in dem
  der Stand abgelegt wird (`2026-10` für den Abschluss, der Ende September schließt),
  bei einer Rentenversicherung das Jahr, wie `monatsabschluss.bestaende` sie führt
  (`bestaende.periode`). Geschrieben wird er von `/api/bestand`
  (`bestaende.verlauf_fortschreiben`), und nur, wenn das Speichern den **Stand** der
  Position ändert (Betrag, Datum oder Gewinn). Eine Notiz, derselbe Wert noch einmal und
  „zurück“ ohne Overlay schreiben nichts.
- **Abweichung vom Plan: das Einmalige beim Speichern, nicht beim Lesen.** Der Plan
  trägt „beim ersten Lesen ohne `verlauf`“ den heutigen Stand jeder Position ein. Ein Lesen,
  das eine Konfigurationsdatei schreibt, wäre jeder GET auf `/monatsabschluss`, `/ziele`
  oder `/annahmen`, ein Seitenaufruf änderte `config/`, und `pruefen` und der Browsertest
  „Speichern ohne Änderung“ sähen es. Stattdessen legt das **erste Speichern, das einen
  Stand ändert,** den Verlauf an: Es trägt zuerst den Stand von *vor* dem Speichern aller
  getippten Positionen unter der Periode seines Datums ein, dann den neuen. Das ist
  dasselbe, was ein Lesen eingetragen hätte, denn nur Speichern ändert Stände. Wer nie
  speichert, hat keinen Verlauf, und `bestaende.zum` sagt dann für jede getippte Position
  `fehlt`.
- **`bestaende.zum(conn, stichtag, basis=None)`:** Gleiche Form wie `zusammenfuehren`
  (`balances`, `obligations`), dazu `fehlt`: die Namen der Positionen, die heute einen Stand
  haben, zu diesem Stichtag aber keinen Eintrag. Sie stehen nicht in `balances`. Belegte
  Stände: `saldo_zum` am Monatsende des Stichtags. Getippte: der Eintrag der Periode des
  **Monats danach** (Stichtag 31.08. gehört zum Abschluss im September); Stichtag 31.12.
  gehört bei einer Police zum Jahr danach. Eine Position, die heute keinen Betrag hat,
  braucht auch damals keinen. Verpflichtungen: wie heute (Entscheidung 7).
  `ziele.toepfe`, `depot_gewinn`, `policen_je_konto` und `tagesgeld_je_konto` lesen das
  Ergebnis unverändert (Test), auch mit der Bestandsart aus der Abweichung zu 3.2b.
- **Der Verlauf ist nur für Stichtage da, die ein Abschluss in der Periode danach
  festgehalten hat.** Hat der Haushalt eine Position im Monat nicht neu abgelegt,
  fehlt sie zum Stichtag davor, auch wenn ihr Stand weiter galt. Das ist gewollt (ein Stand, der
  nicht an diesem Stichtag getippt wurde, ist keiner von damals); der Monatsabschluss
  verlangt ohnehin jeden Monat einen neuen Stand. Renten (jährlich) sind davon
  ausgenommen.
- **Seitenzeiten** (zweiter Aufruf, `TestClient`, vorher gleich nachher):
  `/ziele` 0,13 s, `/hochrechnung` 0,22 s, `/monatsabschluss` 1,30 s, `/konten` 1,13 s.
  `eingaben()` dauert mit und ohne `bis` 0,09 s. Ein GET schreibt keine Datei
  (Prüfsumme von `balances_custom.yaml` vorher und nachher gleich).
- **Handbuch:** unverändert. Ein Absatz zum Verlauf stünde auf `/handbuch`, und 3.4 ändert
  keinen Text einer Seite; er kommt mit 3.6, wenn eine Seite den Verlauf zeigt.
- Tests: `tests/test_stichtag_verlauf.py`. Der allgemeine Browsertest „Speichern ohne
  Änderung“ überspringt `/monatsabschluss` (dort heißt der Knopf erst „Speichern“, wenn
  jemand tippt, und er sieht ihn nicht); ein eigener Browsertest in `tests/test_browser.py`
  tippt einen Wert, prüft den Eintrag im Verlauf, tippt denselben noch einmal und
  verlangt dieselben Bytes in `balances_custom.yaml`.

**Abgenommen am 04.10.2026** (`39b2a02`). Der Verlauf beginnt beim ersten
Speichern statt beim ersten Lesen: richtig, ein Lesen darf `config/` nicht
schreiben. Die Periode ist der Monat des Ablegens, und `bestaende.zum`
sucht für Stichtag S die Periode des Folgetags; das ist dieselbe Zuordnung
wie in Entscheidung 8, nur vom anderen Ende her benannt. Folge: Wer den
Abschluss für September erst im November macht, hat für Ende September
keinen Eintrag, und die Wirkung meldet `fehlt`. Das ist ehrlich und bleibt so.

Für 3.5 festgelegt: **Ein Konto, dessen erster Auszug nach dem Stichtag davor
beginnt, steht in `fehlt`**, außer der erste Auszug beginnt mit Saldo null
(dann war es wirklich leer). Sonst erschiene ein Konto, das nur später
eingelesen wurde, als großer Zufluss unter „Der Monat“. Das gilt einen Monat
lang, danach haben beide Stichtage Auszüge.

### 3.5 Die Wirkung rechnen (gleich)

Neues Modul `finctl/forecast/wirkung.py`, ohne Seite.

- `wirkung(conn, ziele, *, tempo) -> list[ZielWirkung]`: liest
  `Eingaben` zu S (heute) und zu S minus einen Monat (`bis`, Bestände aus
  `bestaende.zum`), tauscht nach Entscheidung 9 und misst nach jedem Tausch
  den Wert jedes Ziels mit der Funktion aus 3.3.
- `ZielWirkung`: Ziel, Wert vorher, Wert heute, `ursachen: list[Posten]`
  (`herkunft.Posten`, Summanden im Sinne seines Docstrings: ihre Summe ist
  Wert heute minus Wert vorher), dazu `fehlt` (welche Stände zum Stichtag
  davor fehlen; dann keine Ursachen und ein Satz, ab wann es sie gibt).
- Ein Tausch, der nichts ändert, erscheint nicht als Ursache. Ein Block mit
  Wirkung null auch nicht.
- Tests mit erfundenen Daten:
  - die Summe der Ursachen ist exakt die Differenz, für beide Tempi;
  - nach dem letzten Tausch ist das Ergebnis gleich `rechnen(eingaben_heute)`;
  - ein Monat, der genau wie erwartet lief, gibt „Der Monat“ nahe null (die
    Toleranz begründen, sie kommt aus Rundung und Inflation über einen
    Monat);
  - ein Monat mit weniger Konsum gibt im Tempo der letzten drei Monate eine
    größere „Tempo: konsum“-Wirkung als im Schnitt;
  - fehlt ein getippter Stand von damals, gibt es keine Ursachen, sondern
    `fehlt`.
- Felder von `Eingaben`, die in keiner Gruppe getauscht werden (Annahmen,
  Tilgungspläne, Renten, Objekte, Puffer), müssen in beiden Rechnungen gleich
  sein. `wirkung` prüft das und wirft sonst einen Fehler, der das Feld nennt:
  Ein Feld, das sich unbemerkt unterscheidet, wäre eine Wirkung ohne Ursache.
- Laufzeit messen: beide Tempi für alle Ziele. Über einer Sekunde: berichten,
  nicht optimieren.

**Fertig wenn:** gleich.

**Stand bei der Umsetzung (04.10.2026):**
- **Aufrufe:** `wirkung.wirkung(conn, ziele, *, tempo)` wie im Plan, dazu
  `wirkung_je_tempo(conn, ziele, *, tempi=beide)`, das beide Stichtage nur einmal liest
  (die Lesezeit ist fast die ganze Laufzeit). `ziele` ist das Ziel-Dokument, wie
  `ziele.progress` es nimmt und wie `/ziele` es nach `rentenluecke.mit_ziel` hat: der
  Zielbetrag steht darin fest und gilt zu beiden Stichtagen und in beiden Tempi
  (Review 3.3). Es braucht das Dokument und keine `Progress`-Liste, weil der Balken zum
  Stichtag davor mit den Ständen von damals neu gerechnet wird und die Grenze der Kaskade
  (`puffer_cents`) aus ihm kommt. `basis` (`balances.yaml`) und `assumptions` lassen sich
  hereinreichen, die Tests tun es.
- **`ZielWirkung`:** Ziel (`Progress`), `stichtag` (S) und `davor`, `vorher` und `heute`
  (der Wert, den `/ziele` als Hochrechnung zeigt), `ursachen` (Posten, Summe = `heute −
  vorher`), `balken_vorher` und `balken_heute` (Bestand gegen Bestand, auch für ein Ziel
  ohne Stichdatum), `fehlt`, `fehlt_grund`, `ab` und `satz` (der Satz für die Seite).
  `vorher` ist `None`, wo Stände fehlen, `heute` ist immer da. `Posten.verweis` trägt die
  Block-Kennung bei „Tempo: <Block>“; das Etikett nennt den Block mit dem Namen aus der
  Oberfläche („Tempo: Konsum und Rest“).
- **Die Rechnung selbst steht in `wirkung.tauschen(davor, heute, messen, von, bis)`**,
  ohne Datenbank und Dateien: Die Tests rechnen dort mit Eingaben von Hand. Die Reihenfolge
  ist die aus Entscheidung 9. Ein Tausch, der die Eingaben nicht ändert, kostet keine
  Rechnung (Gleichheit der Eingaben), erscheint also nie als Ursache; ebenso fällt eine
  Ursache mit Wirkung null auf einem Ziel für dieses Ziel heraus. Am Ende werden die
  Eingaben auf Gleichheit mit denen von heute geprüft; der Rest von `base` (Blöcke außerhalb
  von `FROM_BASE`, die `rechnen` nicht liest) wird dafür still mit getauscht.
- **Felder, die nicht getauscht werden** (Annahmen samt Zinssätzen, Planzeilen selbst,
  Kredite, Renten, Objekte, Grenze, Depotkonten): `tauschen` prüft sie auf Gleichheit
  und wirft sonst `ValueError` mit dem Feldnamen.
- **Fehlt etwas, fehlt es für alle Ziele:** Ein getippter Stand von damals, ein später
  eingelesenes Konto (`bestaende.zum`, Festlegung aus der Abnahme 3.4) oder ein Hauptbuch,
  das vor dem Stichtag davor noch kein Fenster hat. Die Kaskade schiebt, was das
  Tagesgeld-Ziel übersteigt, ins Depot, also kann ein fehlender Stand jedes Ziel
  bewegen, auch eines, das nur das Depot zählt. Die Wirkung gibt dann `vorher=None`,
  keine Ursachen, `fehlt` mit den Namen und `ab` mit dem ersten Stichtag, zu dem der
  Vergleich möglich ist. `bestaende.zum` liefert dafür `fehlt_grund` (`stand` oder
  `konto`) und `fehlt_ab`: bei einem Stand der Monatsletzte der Periode seines nächsten
  Eintrags, sonst der übernächste Monatsletzte nach dem Stichtag davor (im nächsten
  Abschluss eingetragen, ist der Stand dann der Vormonat); bei einem Konto der Monatsletzte
  des Monats nach dem Beginn seines ersten Auszugs.
- **Horizont:** Die Wirkung rechnet bis zum spätesten Stichdatum (mindestens 2045), die
  Seite bis ins erste Rentenjahr. Spätere Jahre ändern frühere nicht; eine Gegenprobe gegen
  die Rechnung der Seite auf der Entwicklungskopie ergab für jedes Ziel und beide Tempi
  dieselbe Zahl.
- **Modul:** `finctl/forecast/wirkung.py` gehört zum Modul `ziele` (`finctl/module.py`),
  denn es braucht `ziele.hochgerechnet`, und die Prognose darf kein Modul importieren.
  `finctl/monatsabschluss.py` ist App und darf es importieren (3.6), muss aber den Abschnitt
  weglassen, wenn das Modul ausgeschaltet ist.
- **Laufzeit** (Entwicklungskopie, Wegwerfkopie mit nachgetragenem Verlauf, zweiter Aufruf):
  beide Tempi für alle Ziele rund 0,32 s mit 18 Rechnungen, ein Tempo rund 0,25 s mit 9. Eine
  Rechnung (`rechnen`) dauert rund 5 ms; die zwei Lesevorgänge der Eingaben sind der Rest.
  Unter einer Sekunde, nichts zu optimieren. Ohne Verlauf (der Entwicklungskopie, wie sie
  ist) bricht `wirkung_je_tempo` vor der zweiten Lesung ab: rund 0,11 s.
- Tests: `tests/test_wirkung.py` (17), darunter die vom Plan genannten fünf. „Der Monat“
  ist ohne Inflation und Rendite exakt null; mit 2 % Inflation bleibt er unter einem
  Viertel einer Monatsrate (Begründung im Test: ein Zwölftel Inflation auf die Kosten der
  übrigen Jahre).

**Abgenommen am 05.10.2026** (`4075c4a`). Die Ursachen summieren sich
exakt, der heutige Wert stimmt mit `/ziele` überein, und die Laufzeit
(beide Tempi, alle Ziele, rund 0,3 s) passt.

**Befund aus dem Review:** In einer Wegwerfkopie mit angenommenem Verlauf
waren die größten Ursachen nicht Verhalten, sondern der Kalender. Ein
Monat, der aus dem Zwölfmonatsfenster fiel, und einer, der dazukam,
verschoben die Jahreswerte von Mieteinnahmen und Fixkosten so, dass die
Wirkung auf ein Ziel mit fernem Stichdatum in die Zehntausende ging:
Mieten kamen in einem Monat mit einer Zahlung mehr oder weniger, und eine
Monatszahlung, deren Buchungstag über das Monatsende rutscht, stand im
Fenster dreizehnmal. Die Rechnung ist richtig; sie macht eine Schwäche der
Summe über zwölf Monate sichtbar, die Schritt 4 (Takt je Reihe) behebt.
Bis dahin muss die Seite zeigen, woher eine Tempo-Ursache kommt, sonst
liest man „Miete gesunken“, wo nur ein Zahlungstag gewandert ist.

### 3.6 Die Wirkung im Monatsabschluss (gewollt)

- `/monatsabschluss` zeigt einen Abschnitt „Wirkung auf deine Ziele“: je Ziel
  die Bewegung gegenüber dem Vormonat in beiden Tempi, aufklappbar nach
  Ursachen, mit dem Satz „unter den heutigen Annahmen“.
- Unter „Der Monat“ die Hinweise aus Entscheidung 10, als Hinweis
  gekennzeichnet, nicht als Rechenweg.
- **Jede Tempo-Ursache nennt ihre Kategorien** (nach dem Review von 3.5):
  je Kategorie, deren Jahreswert sich zwischen den Stichtagen geändert hat,
  der Jahreswert vorher und nachher, der Monat, der aus dem Fenster fiel,
  und der, der dazukam, je mit Betrag und Zahl der Buchungen. Damit sieht
  man auf einen Blick, ob sich ein Betrag geändert hat oder nur ein
  Zahlungstag. Ein Text, der das deutet, gehört nicht dazu: Die Zahlen
  stehen da, das Urteil trifft der Haushalt. Die Werte liefert
  `wirkung.py`, die Seite rechnet nichts.
- Fehlen Stände von damals: der Satz aus 3.5 statt der Zahlen.
- Ist das Modul Ziele aus, fehlt der Abschnitt.
- Der Musterhaushalt bekommt einen erfundenen Verlauf, sodass der Lauf mit
  `FINCTL_TESTDATEN=muster` den Abschnitt mit Zahlen zeigt und testet. Die
  Entwicklungskopie bekommt keinen: Sie zeigt den Satz, bis jemand dort
  einen Monatsabschluss macht, und die Referenz bleibt davon frei.
- Stimmt der Stichtag nicht mit der Periode überein, die der Abschluss gerade
  schließt (Auszüge fehlen noch), sagt die Seite, auf welchen Stichtag sich
  die Wirkung bezieht.

**Fertig wenn:** Suite beide Läufe grün, Browsertests grün, `pruefen` zeigt
nur hinzugefügte Zeilen auf `/monatsabschluss`. Bericht mit dem Diff.

**Stand bei der Umsetzung (05.10.2026):**
- **Aufbau:** `wirkung.vergleichen(conn, ziele, *, tempi, mit_luecke, mit_hinweisen)`
  liefert einen `Vergleich` (Stichtage, `je_tempo`, `hinweise`); `wirkung_je_tempo` und
  `wirkung` bleiben und rufen es. `finctl/monatsabschluss.py` ordnet es für die Seite
  (`wirkung(conn, heute) -> Wirkung | None`; None ohne Modul Ziele, ohne Hauptbuch, ohne
  Ziele). Die Route reicht es nur durch. Der Abschnitt steht nach den offenen Listen, vor
  „Bald fällig“.
- **Rentenlücke:** `mit_luecke=True` hängt sie an die Ziele, gerechnet aus der Hochrechnung
  von heute im Schnitt bis ins erste volle Rentenjahr, wie `/ziele` es tut: ein Zielbetrag
  für beide Stichtage und beide Tempi (Review 3.3). Ohne den Wunsch bleibt `vergleichen`,
  was `wirkung_je_tempo` in 3.5 war.
- **Kategorien je Tempo-Ursache:** `KategorieWandel(kategorie, vorher, nachher, heraus,
  dazu)` mit `MonatBetrag(monat, cents, buchungen)`; `ZielWirkung.kategorien` führt sie je
  Block (für alle Ziele dieselben), die Ursache „Tempo: <Block>“ findet sie über
  `Posten.verweis`. Der Jahreswert ist der aus `Eingaben.base`; die Monate sind die
  Differenz der beiden Fenster (bei Jüngst die der letzten drei Monate, aus
  `base_monate`). Betrag und Buchungszahl kommen aus derselben Messung wie die Basis
  (`jahre._hochrechnung`, dieselben Umbuchungen und einmaligen Planzeilen): dazu zählt
  `messung.Monatssumme` jetzt `buchungen` (eine Buchung mit zwei Teilen derselben Kategorie
  zählt einmal; nicht Teil des Vergleichs zweier Zeilen). Ein Monat ohne Buchung steht mit
  null und null Buchungen da. Die Seite deutet nichts; ein Test hält das fest.
- **Hinweise unter „Der Monat“:** `wirkung.Hinweise` mit der Zeile des Treffer-Checks
  (`treffer.jahresbasis` für den Monat des Stichtags, mit den Tilgungsplänen von heute) und
  `Kurs(stand_vorher, stand_heute, buchungen_cents)`: Die Seite zeigt Änderung und Buchungen
  unter `investment/` nebeneinander, und ihre Summe ist die Kursbewegung. Die Buchungen
  lassen sich keinem Depot zuordnen, also gilt es für den ganzen Topf Depot (auch Krypto).
  **Abweichung vom Wortlaut:** Die Hinweise stehen **einmal** unter der Tabelle („Der Monat“),
  nicht unter der Zeile „Der Monat“ jedes Ziels: Sie sind für alle Ziele gleich, und die
  Ursache verweist mit „Hinweise zum Monat“ auf sie. Zwei Sätze erklären sie, beide nur
  dort, wo sie zutreffen: dass sie nicht zur Wirkung gehören (die läuft bis zum
  Stichdatum weiter), und dass gebuchte Zinsen und Kapitalertragsteuer in der Zeile als Ist
  zählen, die Hochrechnung sie aber rechnet (die Abweichung aus 3.2b). Die Zeile des
  Treffer-Checks nimmt die beiden Kategorien nicht heraus.
- **Konfigurationsfuß unverändert:** Ein Eintrag für `ziele_custom.yaml` oder der Verlauf in
  der Beschreibung von `balances_custom.yaml` änderte eine alte Zeile („Konfiguration — 10
  Dateien“ und den Text) und ließe `pruefen` ein `-` zeigen. Die Referenz schreibt das
  nach dem Review; bis dahin steht der Verlauf im Handbuch.
- **Fehlen Stände von damals:** ein Satz (`fehlt_satz`) statt Tabelle und Hinweisen. Ein
  anderer Stichtag als der, den der Abschluss schließt, steht in einem eigenen Hinweis.
- **Aufklappen:** `tr.klappbar` mit einem Panel je Ziel, wie die Jahre auf `/hochrechnung`.
  Ein Ziel ohne Hochrechnung zeigt nur die Änderung seines Balkens und klappt nicht auf.
- **Musterhaushalt:** `config/balances_custom.yaml` trägt einen erfundenen Verlauf (je
  Monat der Stand vom Monatsende davor; die Policen unter dem Jahr, dafür die neue Marke
  `{Y-1}` in `tests/musterhaushalt/bauen.py`). Die Entwicklungskopie bekommt keinen und zeigt
  den Satz.
- **Handbuch:** Unterabschnitt „/monatsabschluss — Wirkung auf die Ziele“ mit dem Verlauf,
  in `HANDBUCH.md` und `finctl/HANDBUCH.md`; der verlinkte Abschnitt „/monatsabschluss“
  bleibt unter 200 Wörtern. **CHANGELOG:** zwei Einträge für 3.6, dazu einer für 3.3, der
  dort fehlte (das Tempo der letzten drei Monate stand in keinem Eintrag).
- **Seitenzeiten** (zweiter Aufruf, `TestClient`, vorher gleich nachher):
  `/monatsabschluss` auf der Entwicklungskopie ohne Verlauf 1,27 s → 1,42 s (die Eingaben
  von heute werden gelesen, dann bricht der Vergleich ab); in einer Wegwerfkopie mit
  nachgetragenem Verlauf 1,27 s → 1,80 s. Davon die Wirkung selbst rund 0,33 s, die
  Rentenlücke rund 0,13 s (sie liest Annahmen und Person je Aufruf neu, siehe unten), die
  Hinweise rund 0,05 s. Musterhaushalt 0,34 s → 0,47 s. `/ziele` und `/hochrechnung`
  unverändert.
- Tests: `tests/test_wirkung.py` (7 neue), `tests/test_wirkung_seite.py` (7, beide
  Datenlagen), ein Browsertest für das Aufklappen.

**Abgenommen am 05.10.2026** (`b2fe628`), Referenz danach neu geschrieben.
Im Browser auf dem Musterhaushalt angesehen: Aufklappen zeigt je Tempo-Ursache
die Kategorien mit Monat raus und Monat rein. Die Entscheidungen der Sitzung
(Hinweise einmal unter der Tabelle, Konfigurationsfuß unverändert, Rentenlücke
mit Zielbetrag aus dem Schnitt) sind abgenommen. Die Kategorien stehen als
Kennung da, nicht mit Anzeigenamen; das gehört zu Schritt 6. `/monatsabschluss`
braucht mit Verlauf rund 0,5 s mehr, davon 0,13 s die Rentenlücke, die ihre
Annahmen je Aufruf neu liest (unten).

### 3.7 Aufräumen (gleich, bis auf den Hinweis auf /planung)

- Die Closure-Reste in `finctl/web/routen/ziele.py`, die 3.3 übrig ließ.
- `ZU_VERZWEIGT` auf gemessene Werte (`project` ist seit 3.1 heraus).
- Auf `/planung` sagt eine Wegfallzeile auf Kapitalertragsteuer es seit 3.2c
  doppelt („nur Kontoprognose · gilt nur für /konten …“). Ein Hinweis genügt.
- Der Test `test_the_calculation_touches_neither_the_ledger_nor_config`
  sperrt Dateien, aber nicht die Datenbank: `sqlite3.connect` öffnet die
  Datei ohne Python-`open`. Er sperrt auch `sqlite3.connect`, sonst hält er
  sein „neither the ledger“ nicht.
- `rentenluecke.rechnen` liest Annahmen und Person je Aufruf neu (rund 0,13 s);
  einmal lesen wie `eingaben` seit 3.1. Gleich, nur Zeit.
- Seitenzeiten von `/konten` und `/monatsabschluss` messen und nach dem
  Muster aus 3.1 suchen (Annahmen, die in einer Schleife je Aufruf Datei und
  Overlay lesen). Nur berichten und unter „Gefundene Abweichungen“
  eintragen; behoben wird es in einem eigenen Gleich-Schritt.
- „Gefundene Abweichungen“ unten: jeder Eintrag mit Warum und Schritt.
- `docs/Neufassung_plan.md`: Schritt 3 als erledigt markieren, mit Datum und
  dem, was offen bleibt.

**Fertig wenn:** gleich.

**Stand bei der Umsetzung (05.10.2026):**
- **Closure-Reste:** Von der Closure `read` und den Importen in der Funktion ist in
  `finctl/web/routen/ziele.py` nichts übrig. `_lesen(name)` liest eine Datei aus `config/`
  für die Seite und beide Schreibwege (`/api/ziel`, `/api/ziele/reihenfolge`, die dasselbe
  inline taten); die Importe stehen oben. `ziele()` ist in `_karte` (die Zeile eines Ziels),
  `_hochrechnung_anhaengen` (beide Tempi neben den Balken), `_basis_arten` und
  `_basis_beschriften` zerlegt, mit den Begründungen bei den Stücken, zu denen sie gehören.
  Das HTML bleibt gleich (`pruefen`, Tests der Seite).
- **`ZU_VERZWEIGT`:** Die Liste stimmte schon mit der Messung überein (19 Einträge, jeder
  gleich). `engine.py::project` ist nicht `jahre.project`, sondern die ältere Funktion in
  `engine.py`; sie steht bei 15 und bleibt. Nichts zu ändern. `api_ziel` bleibt bei 21: der
  Umbau oben betrifft die Seite, nicht den Schreibweg.
- **`/planung`, doppelter Hinweis:** `_klammer.html` zeigt „nur Kontoprognose“ an einer
  Wegfallzeile nur noch, wenn die Zeile nicht den Satz „gilt nur für /konten; …“ trägt. Der
  Satz sagt dasselbe und nennt dazu, was die Hochrechnung stattdessen tut. Ein Test legt eine
  Wegfallzeile auf Kapitalertragsteuer mit zugeordneter Buchung an und zählt beide Texte; er
  schlägt ohne die Änderung fehl. **`pruefen` darf auf `/planung` ein `-` zeigen**, wo die
  Entwicklungskopie so eine Zeile hat: Das ist die gewollte Änderung, die Referenz folgt in
  ihrem eigenen Schritt.
- **Der Test sperrt jetzt auch die Datenbank:**
  `test_the_calculation_touches_neither_the_ledger_nor_config` setzt `sqlite3.connect`
  außer Kraft, und ein zweiter Test hält fest, dass die Sperre greift (`ledger.db.connect`
  geht durch dasselbe Modul und fällt darauf herein).
- **Die Rentenlücke liest nichts mehr:** `rentenluecke.rechnen(lauf, e)` und
  `mit_ziel(goals, lauf, e)` nehmen die `Eingaben` der Hochrechnung. Dafür tragen die
  `Eingaben` drei Werte mehr: `Annahmen.lebenserwartung`, `Annahmen.aufbrauchen`
  (`ann.aufbrauchen` ersetzt `rentenluecke.aufbrauchen_anteil`) und `Eingaben.geburtsdatum`
  (neben `rentenbeginn`, beide aus einem Lesen der Person: `person.rentenbeginn_aus`). Ein
  Test rechnet die Lücke aus erfundenen Werten bei gesperrten Dateien und gesperrter
  Datenbank nach. Als Nebenfolge rechnet sie mit den Annahmen, mit denen auch die
  Hochrechnung gerechnet ist; vorher griff sie immer zur Standarddatei, auch wenn die
  Eingaben aus einer anderen kamen. Die Tests, die `rl.rechnen` und `rl.mit_ziel`
  ersetzen, nehmen die zweite Angabe mit.
- **Gemessen, und das ist weniger, als der Plan sagte:** Ein Aufruf von
  `rentenluecke.rechnen` kostete 4,3 ms auf der Entwicklungskopie (1,8 ms im Musterhaushalt)
  und kostet jetzt unter 0,1 ms. Die 0,13 s aus dem Plan und der Abnahme von 3.6 ließen sich
  nicht nachstellen: Die ganze Rentenlücke, samt der Hochrechnung bis ins erste Rentenjahr,
  macht auf `/monatsabschluss` im Musterhaushalt (der einen Verlauf hat) 17 ms aus (0,457 s
  ohne sie, 0,470 s mit). Die Zahl 0,13 s passt dagegen zur ganzen Wirkung: Die Seite braucht
  dort 0,466 s, ohne den Abschnitt 0,334 s. Davon sind rund 0,02 s die Rentenlücke; den Rest
  machen zwei Lesevorgänge der Eingaben (31 ms je Lesen im Musterhaushalt) und die
  Rechnungen der Tausche aus.
- **Gleich, nur Zeit, auch in `eingaben`:** `renten.beginn(q)` las die Person (zwei Dateien)
  je Rentenquelle neu, mitten in `eingaben`. Jetzt nimmt es den Rentenbeginn als Wert
  (`renten.beginn(q, rentenbeginn)`, mit einem Marker für „lies ihn“, weil `None` ein
  gültiger Wert ist), und `eingaben` liest die Person einmal: zwei Lesevorgänge statt vier
  bei einer Quelle ohne eigenes Datum, einen weniger je weiterer. Ein Test zählt sie.
- **Seitenzeiten** (zweiter Aufruf, `TestClient`, vorher gleich nachher): Entwicklungskopie
  `/ziele` 0,13 s, `/hochrechnung` 0,22 s, `/monatsabschluss` 1,44 s (ohne Verlauf),
  `/konten` 1,14 s; Musterhaushalt (mit Verlauf) 0,05 s, 0,09 s, 0,49 s, 0,32 s. `eingaben`
  87 ms.
- **Das Muster aus 3.1 steht in `/konten` und `/monatsabschluss` noch** (Einträge unter
  „Gefundene Abweichungen“): `/konten` öffnet 278 Mal eine YAML-Datei, `/monatsabschluss`
  363 Mal, aus 14 beziehungsweise 22 Dateien; im Profil sind es rund 90 % der Zeit der
  Seite. Behoben wird es nicht hier.

**Abgenommen am 05.10.2026** (`ea9aa90`), Referenz danach neu geschrieben.
`pruefen` zeigte nur die eine Zeile auf `/planung`. Die 0,13 s im Plan waren
meine Schätzung aus dem Profil der ganzen Wirkung, nicht der Rentenlücke; die
Messung der Sitzung gilt. Der Marker `_UNGELESEN` in `renten.beginn` bleibt:
Die übrigen Aufrufer fragen eine einzelne Quelle und sollen nicht selbst lesen.

## Wo ein stärkeres Modell sich lohnt

- **Nach 3.2b, 3.3 und 3.6:** Review des Diffs von `pruefen`, dann schreibt
  Opus die Referenz neu.
- **Vor 3.5, falls `rechnen()` in 3.1 langsamer als 50 ms war:** wie die
  Wirkung schneller wird, ohne Entscheidung 9 aufzugeben.

## Auftrag für eine Sitzung (Vorlage)

> Setze Teilschritt 3.N aus `docs/schritt3_juengst_wirkung.md` um. Lies
> vorher `CLAUDE.md`, `CONTEXT.md` und den ganzen Plan, besonders die
> Entscheidungen. Arbeite mit `FINCTL_DATEN` auf der Entwicklungskopie.
> Fertig ist der Teilschritt, wie er es dort sagt. Starte `pruefen` erst,
> wenn du keine Datei mehr änderst. Schreib die Referenz nicht neu. Bleibt
> ein Gleich-Schritt rot oder zeigt ein Gewollt-Schritt ein `-`, hör auf und
> berichte. Committe nur die Dateien dieses Teilschritts.

## Gefundene Abweichungen

Hier tragen die Sitzungen ein, was ihnen auffällt und nicht in ihren
Teilschritt gehört: wo, was, ob es eine Zahl ändern würde, warum, und welcher
Schritt es anfassen muss.

- **3.1, `jahre.project` las die Konfiguration in der Jahresschleife:**
  `ann.inflate`, `ann.salary_median_cents`, `ann.salary_growth_pa` und
  `renten.beginn` bekamen einen Pfad und lasen bei jedem Aufruf Datei und
  Overlay neu, je Jahr und Posten hundertfach. Das war fast die ganze Zeit von
  `project()` (rund 1,0 s, jetzt 0,1 s). Seit 3.1 liest `eingaben` sie einmal,
  `rechnen` rechnet mit `ann.grow` und den Werten in `Eingaben.annahmen`. Die
  Zahlen sind gleich (`inflate` ist `grow` mit gelesenem Satz). **Warum:** Die
  Funktionen nahmen einen Pfad statt eines Werts. **Schritt:** keiner; wer
  anderswo `ann.*` in einer Schleife ruft (nicht geprüft), kann dasselbe
  finden.
- **3.1, Entscheidung 9, Zeile „Planzeilen“ nennt „die einmaligen Planzeilen,
  die die Messung auslässt“:** In `Eingaben` gibt es dafür kein Feld. Der
  Ausschluss (`szenarien.einmalig_zugeordnet`) wirkt beim Messen der Basis und
  steckt damit in `base`; `rechnen` liest ihn nicht. Die Planzeilen selbst
  gelten für beide Stichtage, wie sie heute stehen (Entscheidung 7), also
  schließt die Rechnung zum Stichtag davor dieselben Buchungen aus. Ändert
  keine Zahl. **Warum:** Der Ausschluss ist eine Eigenschaft der Messung, kein
  Eingabewert der Rechnung. **Schritt:** 3.5; die Zeile der Tabelle entfällt
  dort wohl, oder 3.5 sagt, was sie sonst tauschen soll.
- **3.2, `jahre._jahresposten_gemessen` lässt Posten mit null weg:** Die Zeile
  `if not cents: continue` überspringt eine Kategorie, deren Jahreswert null
  ist. Im Tempo der letzten drei Monate ergibt eine Kategorie ohne Buchung dort
  null (Entscheidung 1) und steht in `Eingaben.base` mit null, im Rechenweg der
  Seite aber fehlt ihre Zeile. Im Schnitt trifft das heute nur Kategorien, die
  sich im Fenster aufheben. Eine Zahl ändert das nicht (null addiert nichts).
  **Warum:** Die Zeile spart leere Zeilen im Rechenweg, bevor es ein zweites
  Tempo gab. **Schritt:** 3.3; zeigt die Seite, welche Posten „im Tempo der
  letzten drei Monate“ auf null gefallen sind, muss die Zeile dort bleiben,
  mindestens für Jüngst.
- **3.2b, Treffer-Check und Hochrechnung behandeln Zinsen verschieden:**
  `treffer.jahresbasis` misst `einkommen/zinsen` und `steuern/kapitalertragsteuer`
  wie jede Kategorie über `ag.measure`, also als Gebuchtes in den Blöcken
  `einkommen_sonst` und `steuern`. Die Hochrechnung schreibt beide seit 3.2b nicht
  mehr fort, sie rechnet sie. Eine Zahl des Treffer-Checks ändert das nicht.
  **Warum:** Der Treffer-Check fragt, ob die Basis des Vormonats stimmte, und
  gebucht ist gebucht; die Hochrechnung fragt, was ein Topf mit seinem Satz
  verdient. **Schritt:** 3.6; die Hinweise unter „Der Monat“ zeigen Ist gegen Soll
  je Block, und der Soll-Wert von `einkommen_sonst` und `steuern` enthält Beträge,
  die in der Hochrechnung an anderer Stelle (Rendite) stehen. Der Hinweis sagt das
  oder nimmt die zwei Kategorien aus.
  **Erledigt in 3.6:** Die Seite sagt es in einem Hinweis, wenn im Monat Zinsen oder
  Kapitalertragsteuer gebucht sind.
- **3.2b, die Kontoprognose schreibt die Zinsen weiter fort:** Ihre `Vorschau`
  trägt kein `ausser` für `GERECHNET`; Dispo und Untergrenze fragen nach dem
  Monat, nicht nach dem Kapital (Entscheidung 13). Ändert keine Zahl. **Warum:**
  Die Kontoprognose bucht Termine auf Konten; ein Satz je Konto und Jahr hätte dort
  keine Entsprechung. **Schritt:** keiner.
- **3.2b, der Sparerpauschbetrag gilt im Basisjahr anteilig:** Entscheidung 16 sagt
  nichts zum laufenden Jahr. Auch die Zinsen und die Vorabpauschale dort sind nur
  die der Restmonate; den ganzen Betrag dagegenzuhalten schützte sie zu stark,
  denn was im Jahr schon gebucht ist, hat ihn zum Teil verbraucht. `kaskade`
  rechnet mit `pauschbetrag × anteil`, der Rechenweg schreibt „anteilig, Restmonate“.
  **Warum:** Lieber zu viel Steuer als zu wenig (`assumptions.yaml`).
  **Schritt:** keiner; wer es anders will, ändert eine Zeile in `kaskade`.
- **3.2b, der Topf Tagesgeld enthält die Girokonten:** `ziele.TOPF` ordnet Giro und
  Tagesgeld demselben Topf zu. Mit Entscheidung 14 verdient ein Girokonto im Topf
  0 %, und sein Stand senkt den Satz des Topfs. Ohne Eintrag und ohne Girokonto im
  Topf bleibt es bei dem Satz von vorher. **Warum:** Die Hochrechnung kennt Töpfe, keine
  Konten; Giro und Tagesgeld sind ein Topf, weil beides jederzeit verfügbar liegt, und
  Entscheidung 14 fragt nach dem Satz je Konto statt nach dem des Topfs. **Schritt:** keiner.
- **3.2b, `tagesgeld_je_konto` liefert die Bestandsart mit:** Entscheidung 14
  entscheidet nach Art (Tagesgeld oder Giro), wenn ein Konto keinen Eintrag hat;
  die Art steht in der Bestandszeile, nicht im Satz. `ziele.tagesgeld_je_konto`
  gibt deshalb `Konto(art, cents)` zurück, keine nackten Stände. **Warum:** Ohne die Art
  ließe sich ein Konto ohne eigenen Satz nicht einordnen (Tagesgeld verdient den
  langfristigen Satz, Giro nichts). **Schritt:** 3.4 und 3.5; `bestaende.zum` muss für den
  Stichtag davor dieselbe Form liefern, und „Der Monat“ tauscht `Monat.tagesgeld_je_konto`
  mit dem übrigen Bestand. **Erledigt in 3.4 und 3.5.**
- **3.2b, Prognosebasis auf /annahmen:** Für `einkommen/zinsen` und
  `steuern/kapitalertragsteuer` zeigt die Spalte „Jahresrechnung“ jetzt „—“ und der
  Grund sagt, dass die Jahresrechnung sie rechnet. Vorher stand dort der
  fortgeschriebene Zwölftel. Die Summe „Jahresrechnung“ enthält sie nicht mehr.
  **Warum:** Eine Zahl, die die Rechnung nicht benutzt, gehört nicht in die Spalte.
  **Schritt:** keiner.
- **3.2b, Browsertest auf dem Musterhaushalt:**
  `test_split_gleichmaessig_verteilt_und_speichert_nichts` schlägt mit
  `FINCTL_TESTDATEN=muster` fehl (ein Betragsfeld bleibt nach „gleichmäßig verteilen“
  leer), auf der Entwicklungskopie nicht. Er schlägt auch auf `f554115` ohne
  die Änderungen von 3.2b fehl und hat mit ihnen nichts zu tun. **Warum:** Der
  Test wartete auf „geht genau auf“, und das stand schon vor dem Klick da: Im
  Musterhaushalt deckt eine Regel die Buchung ganz ab, der Test fügt einen leeren
  Teil hinzu, und die Summe stimmt weiter. Gelesen wurde, bevor die Verteilung
  vom Server ankam. Auf der Entwicklungskopie hat die Buchung schon zwei
  ausgefüllte Teile; dort lief der Test durch, ohne das Verteilen zu prüfen.
  Seite und Route sind richtig. Jetzt leert der Test die Felder vorher und
  wartet auf jedes einzelne. **Schritt:** erledigt, nur der Test; keine Zahl
  geändert.
- **3.2c, Kopf der Klammer und Barista-FIRE auf /planung:** „wirkt noch … /Monat“ in der
  Kopfzeile und `monthly_impact_cents` (der Streifen gegen das Ziel) summieren eine Zeile
  auf Zinsen oder Kapitalertragsteuer weiter mit, obwohl die Hochrechnung sie nicht mehr
  auswertet. Keine Zahl der Hochrechnung ändert das; der Streifen auf /planung bildet die
  Zeile ab, die Kontoprognose bucht. **Warum:** Beide Summen beschreiben die Zeile als
  Betrag je Monat, nicht ihre Wirkung in einer Rechnung. **Schritt:** keiner der Schritte 3;
  wer den Streifen an die Hochrechnung binden will, nimmt die Zeilen aus
  `ohne_wirkung_in_hochrechnung` heraus.
- **3.2c, `eingaben` misst die Zeilen weiter:** `Planzeilen.messungen` enthält auch die
  Messung einer Zeile, die `_planposten` überspringt: eine Abfrage je Zeile, ohne
  Wirkung. **Warum:** Die Auswahl steht an einer Stelle (`gilt_in_hochrechnung`) und nicht
  zusätzlich beim Lesen. **Schritt:** keiner.
- **3.3, Rentenlücke im Tempo der letzten Monate:** `/ziele` misst den Jüngst-Wert der
  Rentenlücke gegen denselben Zielbetrag wie den Schnitt-Wert. Ihr Kapital folgt aus dem
  Bedarf des ersten Rentenjahres, und der ist im Tempo der letzten Monate ein anderer
  (wer zuletzt weniger ausgab, braucht weniger); der gezeigte Prozentwert unterschätzt
  das. Eine zweite `rentenluecke.rechnen` kostete rund 7 ms, weil sie Annahmen und
  Person je Aufruf neu liest, und sprengte die Zeitgrenze von 3.3. **Warum:** Der Plan
  nennt den Zielbetrag nur einmal. **Schritt:** keiner. **Seit 3.7** nimmt
  `rentenluecke.rechnen` die Annahmen als Wert (`Eingaben`) und kostet unter 0,1 ms; die
  Zeitgrenze steht einem zweiten Aufruf nicht mehr im Weg. Ob der Jüngst-Wert einen eigenen
  Zielbetrag bekommen soll, ist eine Entscheidung über die Anzeige, keine über die Zeit, und
  bleibt offen.
- **3.4, Bestandsart und Konto bei `bis`:** Ein Konto, dessen erster Auszug erst nach
  `bis` beginnt, zählt in `eingaben(bis=...)` und `bestaende.zum` als vorhanden: das
  Hauptbuch kennt seine Auszüge ja jetzt, und `saldo_zum` rechnet vor dem ersten Auszug
  den Anfangsstand zurück. Eine Zahl für ein Konto, das es am Stichtag noch nicht gab, ist
  deshalb Anfangsstand statt „fehlt“. Ändert keine Zahl in 3.4. **Warum:** Wann ein Konto
  eröffnet wurde, steht nirgends; der erste Auszug ist die beste Näherung, und `fenster`
  nutzt sie schon für den Beginn der Messung. **Schritt:** 3.5; wer Konten aus der
  Wirkung herausnehmen will, die es zu S minus einem Monat nicht gab, braucht den Beginn
  des ersten Auszugs in `bestaende.zum`.
- **3.4, die Suite stört sich im parallelen Lauf selbst:**
  `test_die_probe_findet_eine_kennung_im_code` (`tests/test_umbenennung.py`) legt
  `finctl/_probe_kennung.py` im echten Quellbaum an (`Path(__file__).resolve()` führt aus der
  Testkopie heraus) und löscht sie nach dem Test. Liest ein anderer Worker in derselben
  Zeit `finctl/**/*.py`, steht die Datei in `rglob` und ist beim Lesen weg. Gesehen in vier
  Läufen auf dem Musterhaushalt (die anderen drei waren grün): einmal
  `test_keine_kennung_im_code` mit `FileNotFoundError: finctl/_probe_kennung.py`, einmal
  `test_herkunft_summe_is_only_used_where_posten_are_summands`, der den Baum ebenso liest
  (seine Meldung habe ich nicht gesehen; derselbe Weg ist wahrscheinlich). Das ist wohl
  auch der Ausfall, den der Vermerk zu 3.3 einer anderen Sitzung zuschrieb: kein
  fremder Schreiber, sondern die Suite. Ändert keine Zahl. **Warum:** Die Probe braucht
  eine Datei im Baum, den `kennungen_im_code` durchsucht. **Schritt:** keiner der Schritte
  3; ein eigener Gleich-Schritt lässt die Probe in einer Kopie von `finctl/` laufen oder
  hängt die Tests, die den Baum lesen, an eine `xdist_group`. **Behoben** im Review
  von 3.4: `kennungen_im_code` nimmt eine `wurzel`, und die Probe liegt in `tmp_path`.
- **3.4, Handbuch zum Verlauf:** Gehört nach `finctl/HANDBUCH.md` und `HANDBUCH.md`
  (beide gleich halten, `tests/test_paket.py`), sobald eine Seite den Verlauf zeigt.
  **Schritt:** 3.6.
  **Erledigt in 3.6.**
- **3.3, Herleitung im Tempo der letzten Monate:** `Ergebnis.letzte_monate` und
  `Eingaben.base_monate` tragen, über wie viele Monate eine Kategorie gemessen ist; der
  Rechenweg nennt dieses Fenster statt des ganzen. **Warum:** Im Tempo der letzten Monate
  ist das Fenster kleiner als das der Hochrechnung, und eine Zahl über drei Monate darf
  nicht „über zwölf“ heißen. **Schritt:** 3.5; „Tempo: <Block>“ tauscht `base` und
  `base_monate` zusammen. **Erledigt in 3.5.**
- **3.5, die Entwicklungskopie hat keinen Verlauf:** Niemand hat dort seit 3.4 einen
  Stand gespeichert, also fehlt jeder getippte Stand von damals und die Wirkung nennt für
  jedes Ziel nur `fehlt`. Das ist 3.4 so entschieden („wer nie speichert, hat keinen Verlauf“).
  Sichtbar werden Zahlen auf der Kopie, sobald im Monatsabschluss ein Stand gespeichert ist
  und ein Monat später der nächste Abschluss kommt. **Schritt:** 3.6 sagt den Satz; der
  Review kann einen Verlauf von Hand eintragen, um Zahlen zu sehen.
  **Erledigt in 3.6:** Die Seite sagt den Satz; der Musterhaushalt hat einen erfundenen
  Verlauf.
- **3.5, ein Abschluss nach dem Jahreswechsel:** Liegt heute im neuen Jahr und fehlen die
  Auszüge des alten noch, hat die Rechnung von heute ein anderes Basisjahr als die zum
  Stichtag davor (`eingaben` nimmt das Jahr von `date.today()` ohne `bis`, das Jahr des
  Folgetags mit). „Der Monat“ trägt dann den Sprung des Basisjahrs mit, und das ist
  dasselbe, was `/ziele` heute schon tut (die Monate zwischen Stichtag und Jahreswechsel
  stehen weder im Bestand noch in den Restmonaten). Nicht mit Daten nachgestellt.
  Ändert keine Zahl. **Schritt:** keiner der Schritte 3; ein eigener Gleich-Schritt für
  die Hochrechnung bei verspäteten Auszügen.
- **3.6, die Rentenlücke rechnet ihre Annahmen je Aufruf neu:** `rentenluecke.rechnen` liest
  Person, Lebenserwartung, Depotrendite, Inflation und den Anteil zum Aufbrauchen je Aufruf
  aus Datei und Overlay; mit der Wirkung läuft sie auf `/monatsabschluss` einmal, auf `/ziele`
  schon lang. Rund 0,13 s je Aufruf. Ändert keine Zahl. **Warum:** Wie die Funktionen aus
  3.1, die einen Pfad statt eines Werts nehmen. **Schritt:** 3.7 (Muster aus 3.1 suchen);
  ein eigener Gleich-Schritt, der `rentenluecke.rechnen` die Annahmen als Wert nehmen lässt.
  **Erledigt in 3.7**, dort statt in einem eigenen Schritt, weil die Änderung klein und gleich
  ist. Gemessen waren es nicht 0,13 s, sondern 4,3 ms je Aufruf (siehe dort).
- **3.6, der Kurs lässt sich keinem Depot zuordnen:** Die Buchungen unter `investment/` tragen
  kein Depot, also steht die Kursbewegung für den ganzen Topf Depot, Krypto eingeschlossen.
  Ändert keine Zahl. **Warum:** Der Plan sagt „Kursbewegung der Depots“ im Plural und kennt
  keine Zuordnung. **Schritt:** keiner; sie bräuchte ein Depot an der Kategorie oder am
  Teil.
- **3.6, Tempo-Ursachen nennen Kategorien, Gehalt und Planzeilen nicht:** Die Ursache
  „Gehalt“ ist der gemessene Median, „Planzeilen“ ihre Messungen und Vertragsenden; beide
  haben keinen Jahreswert je Kategorie. Der Plan verlangt es auch nur für Tempo. Wer sehen
  will, welcher Wegfall oder welcher Verkauf bewegt hat, braucht eine eigene Aufschlüsselung.
  **Schritt:** keiner der Schritte 3.
- **3.5, `Posten` der Wirkung tragen den Block in `verweis`:** Wer in 3.6 „Tempo: <Block>“
  verlinken will (etwa auf die Zeile im Rechenweg der Hochrechnung), nimmt `verweis`; das
  Etikett ist der Name aus der Oberfläche und kein Schlüssel. **Warum:** Ein Etikett, das
  sich beim Umbenennen eines Bereichs ändert, taugt nicht, um eine Ursache wiederzufinden.
  **Schritt:** 3.6. **Erledigt in 3.6:** Die Kategorien je Tempo-Ursache finden sich über
  `Posten.verweis`.
- **3.6, die Kategorien der Tempo-Ursachen stehen als Kennung da:** Die Seite zeigt
  `konsum/sonstiges`, nicht den Anzeigenamen der Kategorie (Review 3.6). Ändert keine Zahl.
  **Warum:** `wirkung.py` liefert die Kennung, und der Name gehört zur Oberfläche; der
  Rechenweg der Hochrechnung führt dieselbe Kennung. **Schritt:** 6 (Oberfläche nach dem
  Glossar).
- **3.7, `/konten` und `/monatsabschluss` lesen die Dateien je Konto und Aufruf neu:** Das
  Muster aus 3.1 steht dort noch. `/konten` öffnet 278 Mal eine YAML-Datei (14 Dateien),
  `/monatsabschluss` 363 Mal (22 Dateien); im Profil sind es rund 90 % der Zeit der Seite
  (`/konten` 1,14 s, `/monatsabschluss` 1,44 s auf der Entwicklungskopie, 0,32 s und 0,49 s
  im Musterhaushalt). Die Stellen: `realestate/loan.lade_kredite` (52 und 58 Mal je Seite:
  `loans.yaml` und `loans_custom.yaml` je Aufruf), `abos._roh_custom` (32 und 40),
  `objekte._yaml` (50 und 62; `properties*.yaml`), `szenarien.aktive_ids` und
  `konten._klammern`/`_planposten` (je acht, einmal je Konto), `forecast_config` (9) und das
  Overlay der Annahmen (`overlays.lesen` für `settings_custom.yaml`, 40 und 63 Mal: jedes
  `ann.get` öffnet es neu). Der größte Teil läuft unter `account_forecast`, das je Konto
  gerufen wird (acht Aufrufe, im Profil 2,0 von 2,8 s auf `/konten`). Ändert keine Zahl. **Warum:** Die Funktionen nehmen einen Pfad statt eines Werts,
  wie `ann.*` vor 3.1, und die Schleife über die Konten ruft sie je Konto. **Schritt:**
  keiner der Schritte 3; ein eigener Gleich-Schritt, entweder mit einem Lesen je Aufruf der
  Seite (die Werte hineinreichen, wie `eingaben`) oder einem Zwischenspeicher je Datei nach
  Änderungszeit. Er lässt sich an `pruefen` messen und ändert keine Zahl.
