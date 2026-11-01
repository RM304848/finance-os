# Schritt Zielrate: die Monatsrate mit und ohne Rendite

Arbeitsplan für die Umsetzung, geschrieben für ein Modell, das ihn Teil für
Teil abarbeitet (Claude Sonnet). Gesamtplan: `docs/Neufassung_plan.md`, dort
zwischen 4b und 4c. Klein und für sich: Er ändert keine Hochrechnung, nur die
Zielkarte auf `/ziele`. Für die Referenz ist er trotzdem **gewollt**: Auf
`/ziele` kommt eine Zahl dazu. Deshalb läuft er nicht neben einem anderen
Teilschritt, der `pruefen` braucht. Begonnen wird, wenn P.3
(`docs/schritt_policen.md`) abgenommen und die Referenz danach neu geschrieben
ist. Sonst sähe P.3 in `pruefen --nur-zahlen` die neue Zahl dieses Schritts.

## Ziel in einem Satz

Die Zielkarte zeigt neben der Rate, die ohne Rendite nötig ist, eine zweite:
die Rate, wenn Bestand und Rate mit den Sätzen der Hochrechnung wachsen.

## Befund (Opus, 07.10.2026)

- `Progress.monthly_needed_cents` (`finctl/forecast/ziele.py`) teilt
  (Ziel − Bestand − zugesagt) durch die Monate bis zum Stichtag. Das ist
  Absicht und steht im Modulkopf: Eine Rate mit angenommener Rendite ist
  kleiner, und zu wenig zu sparen ist die teure Richtung.
- Für ein langes Ziel mit Depot in der Basis ist die Zahl dadurch mehr als
  doppelt so hoch wie die Rate, die unter den Annahmen des Haushalts reicht.
  Wer die Karte liest, hält das Ziel für kaum erreichbar, und die Zahl hilft
  bei der Entscheidung nicht mehr.
- Der Satz, mit dem gerechnet wurde, steht nur in der Notiz des Ziels. Die
  Karte nennt ihn nirgends, und die Rate rechnet ihn nicht.
- Die Hochrechnung darunter („extrapoliert zum …“) beantwortet eine andere
  Frage: wohin die HEUTIGE Sparrate führt. Welche Rate reichen würde, sagt
  sie nicht.

## Prüfung des Plans (Opus, 07.10.2026)

Gegen den Code geprüft. Der Plan trägt, mit vier Korrekturen, die unten
schon eingearbeitet sind:
- **Je Bestandsart statt je Topf** (Entscheidung 3). `ziele.toepfe` zählt
  einen ganzen Topf, auch Arten, die die Basis nicht nennt. Giro liegt dort
  im Topf Tagesgeld. Ein Ziel mit Basis „Tagesgeld“ bekäme so das Giro
  dazu, und die Summe der Bestände wiche von „heute“ ab. Dann träfe der Test
  „Satz 0 ergibt genau `monthly_needed_cents`“ nicht mehr. Giro 0 % braucht
  die Trennung ohnehin.
- **Ohne Depot und Tagesgeld in der Basis gibt es keine zweite Zahl**
  (Entscheidung 4). Bei einer Basis aus Giro oder nur Policen wächst die
  Rate nicht in der Basis.
- **Herleitung im aufklappbaren Rechenweg der Karte, nicht im `title`**
  (Entscheidung 7). `ein-zwecksatz-je-seite` erlaubt im `title` höchstens
  zwölf Wörter, und die Herleitung hat vier Schritte. Die Karte hat schon
  `details.rechenweg-ziel` für gerechnete Ziele. Das wird der Ort.
- **Monatlich gegen jährlich** (Entscheidung 5). Die Hochrechnung verzinst
  den Zufluss eines Jahres erst im Folgejahr (`jahre.kaskade`), die Karte
  monatlich. Wer genau die Rate der Karte spart, landet in der Hochrechnung
  deshalb einige Prozent unter dem Ziel. Das bleibt so, weil die Formel
  einfach und erklärbar ist. Die Gegenprobe in Z.3 erwartet diese Richtung.

Bestätigt:
- Die Sätze kommen aus den `Eingaben`. Die Depotformel entspricht
  `jahre.kaskade`, nur ohne den Sparerpauschbetrag, und ist damit leicht
  vorsichtig.
- Beide Zahlen stehen, die vorsichtige vorn.
- Keine zweite Zahl ohne Stichtag, nach dem Stichtag und bei einer Basis
  quer zu den Töpfen.
- Zielbeträge gelten nominal, wie in `ziele.hochgerechnet`.

## Entscheidungen (mit dem Haushalt abgestimmt, 07.10.2026)

1. **Beide Zahlen bleiben stehen.** Die Rate ohne Rendite bleibt die erste
   und unverändert. Die zweite steht direkt dahinter und trägt ihren Satz im
   Text. Keine Einstellung, die eine von beiden ausblendet.
2. **Dieselben Sätze wie die Hochrechnung**, je Bestandsart. Keine eigene
   Annahme für die Karte. Gelesen wird aus den `Eingaben`, die die Route
   schon hat (`je_tempo["schnitt"].annahmen` und `.policen`):
   - Depot: `rendite_depot` minus die Last der Vorabpauschale,
     `min(vorab_satz, rendite_depot) × steuer_quote`, wie in `jahre.kaskade`.
   - Tagesgeld: `rendite_tagesgeld`. Die Hochrechnung mischt die Sätze je
     Konto (`zinsen.mischung`). Für die Karte reicht der Satz aus den
     Annahmen; der Unterschied bleibt klein, und der Tagesgeld-Topf ist bei
     langen Zielen der kleine Teil.
   - Policen: je Position `Police.satz(depotsatz)` aus
     `finctl/forecast/policen.py` (Depotsatz minus `kosten_pa`). Eine
     Position ohne Police in `Eingaben.policen` wächst mit dem Depotsatz,
     wie in der Hochrechnung. Ohne Beitrag: Der Beitrag ist eine Ausgabe
     und nicht Teil der Rate. Das ist vorsichtig.
   - Krypto: wie Depot (`GLEICHE_ART`).
   - Giro: 0 %.
3. **Der Bestand wächst je Bestandsart mit ihrem Satz.** Gezählt werden
   dieselben Positionen wie in `liquid_cents(balances, prog.basis)`, nur nach
   Art getrennt. Die Summe ist `have_cents + abzug_cents` (ohne Basis
   abzüglich der Verbindlichkeiten). Der Abzug (Notgroschen) geht zuerst vom
   Tagesgeld ab, dann vom Giro, wie in `progress`. Verbindlichkeiten ohne
   Notgroschen gehen vom Tagesgeld ab; reicht es dort nicht, vom Depot.
   Ein Test hält fest, dass die Summe „heute“ der Karte ergibt.
4. **Die Rate wächst mit dem Satz dessen, wohin gespart wird.** Ist Depot
   in der Basis (oder gilt keine Basis), ist das der Depotsatz nach
   Vorabpauschale, denn die Kaskade lenkt alles über dem Puffer ins Depot.
   Sonst gilt der Tagesgeldsatz, wenn Tagesgeld in der Basis ist. Sonst gibt
   es keine zweite Zahl.
5. **Monatlich gerechnet, Rate am Monatsende.** Monatssatz über
   `policen.monatssatz`. Die Monate kommen aus `Progress.months_left`, wie
   bei der ersten Zahl. Formel:
   `rate = (ziel − zugesagt − Σ bestand_topf × (1+m_topf)^n) × m / ((1+m)^n − 1)`.
   Bei einem Satz von 0 fällt das auf die heutige Division zurück. Die
   Hochrechnung verzinst den Zufluss eines Jahres erst im Folgejahr; die
   Karte bleibt trotzdem monatlich (siehe „Prüfung des Plans“).
6. **Keine zweite Zahl**, wo es keine gibt: ohne Stichtag, bei einem
   erreichten Stichtag, bei einer Basis quer zu den Töpfen (dort fehlt auch
   die Hochrechnung), ohne Depot und Tagesgeld in der Basis und wenn die
   erste Rate schon 0 ist. Reicht der gewachsene Bestand allein, steht dort
   „mit Rendite reicht der Bestand“ statt einer Rate von null.
7. **Mit Herleitung im Rechenweg der Karte.** Die zweite Zahl ist eine
   Prognose. Ihre Schritte stehen als Zeilen im aufklappbaren
   `details.rechenweg-ziel`, das die Karte heute nur für gerechnete Ziele
   hat: Bestand je Art und sein Satz, Wert am Stichtag, verbleibende Lücke,
   Satz der Rate. Kein `title` mit der Herleitung (`ein-zwecksatz-je-seite`:
   höchstens zwölf Wörter). Bei einem gerechneten Ziel kommen die Zeilen zu
   dessen Rechenweg dazu. Die Zeilen entstehen in Python, nicht in der
   Vorlage.

So sähe die Zeile aus (erfundene Beträge):

    heute 20.000,00 € von 400.000,00 € · 2.000,00 €/Monat ohne Rendite · 900,00 € mit 5,0 %

## Teile

### Z.1 Rechnung

- In `finctl/forecast/ziele.py` eine reine Funktion, etwa
  `rate_mit_rendite(prog, toepfe_heute, saetze, today) -> RateMitRendite | None`.
  `RateMitRendite` trägt `cents` (oder `None`, wenn der Bestand reicht), den
  Satz der Rate und die Herleitung als Liste von Zeilen.
- Die Sätze kommen als kleines Mapping `{"tagesgeld": …, "depot": …,
  "policen": …}` herein. `ziele.py` importiert `jahre` nicht (siehe
  `hochgerechnet`); die Route baut das Mapping aus den `Eingaben`.
- Den Modulkopf und den Docstring von `monthly_needed_cents` anpassen: Die
  erste Rate rechnet weiter ohne Rendite, und das bleibt der Grund. Die
  zweite steht daneben und nennt ihren Satz. „No return is assumed
  anywhere“ stimmt danach nicht mehr wörtlich. Der Kommentar über
  `covered_cents` in `Progress` („The return to assume … declared by the goal
  itself“) beschreibt ein Feld, das es nicht mehr gibt. Er fällt weg.

Tests in `tests/test_ziele.py` (oder wo `Progress` heute getestet wird), alle
mit erfundenen runden Beträgen:
- Satz 0 ergibt genau `monthly_needed_cents`.
- Ein Bestand, der mit seinem Satz das Ziel allein erreicht, ergibt `None`
  und keine negative Rate.
- Zwei Arten mit verschiedenen Sätzen: Der Abzug geht vom Tagesgeld ab, und
  das Ergebnis passt zu einer von Hand gerechneten Zahl.
- Die Bestände je Art ergeben zusammen „heute“ der Karte, auch bei einer
  Basis mit Tagesgeld ohne Giro und ohne Basis mit Verbindlichkeiten.
- Giro wächst nicht, eine Police mit ihrem Satz nach Kosten.
- Ohne Stichtag, mit erreichtem Stichtag, bei einer Basis quer zu den
  Töpfen und bei einer Basis ohne Depot und Tagesgeld gibt es keine zweite
  Zahl.
- `covered_cents` mindert die Lücke wie bei der ersten Zahl.

**Umgesetzt am 07.10.2026.** `ziele.rate_mit_rendite(prog, balances, saetze,
today)` mit `bestand_der_basis` (Bestand je Art, Summe = `have_cents`),
`Saetze` und `saetze_aus(annahmen, policen)`. Modulkopf und Docstring von
`monthly_needed_cents` angepasst, der verwaiste Kommentar in `Progress` ist
weg. Karte und Route unverändert. Rechnung und Tests in `tests/test_ziele.py`.

**Abgenommen am 07.10.2026 (Opus).**
- **Nachgeprüft:** `pruefen` meldet gleich. Die Gegenprobe von Hand trifft, und die
  Auslegungen gelten.
- **Offen:** ein Fund zur Kaskade (siehe Gefundene Abweichungen). Er geht in Z.2 mit.

### Z.2 Karte

- `_karte` in `finctl/web/routen/ziele.py` bekommt `mit_rendite` (Cents oder
  `None`), `mit_rendite_satz` und `mit_rendite_herleitung`. Gerechnet wird in
  der Route, sie hat Bestände, Basis und `Eingaben` schon.
- Vorher `docs/design_conventions.yaml` lesen. In `ziele.html` aus
  „· X/Monat nötig“ wird „· X/Monat ohne Rendite“, danach
  „· Y mit Z %“. Die Herleitung steht im `details.rechenweg-ziel` der Karte
  (Entscheidung 7), das dafür auch bei Zielen erscheint, die nicht gerechnet
  sind. Prozent gerendert, nicht fest im Text (`fliesstext-altert-nicht`).
  Beträge über den `euro`-Filter.
- `HANDBUCH.md`, Abschnitt `/ziele`: ein Satz, dass die Karte beide Raten
  zeigt und woher der Satz kommt. Nur dort, nicht noch einmal in der Vorlage
  (`jede-erklaerung-steht-einmal`).

Tests in `tests/test_ziele_seite.py` bzw. `tests/test_web.py`: Die Karte
eines Ziels mit Stichtag und Depot in der Basis zeigt beide Raten; ein Ziel
ohne Stichtag zeigt keine. Ziel und Basis zur Laufzeit aus `config/` lesen
oder im Test anlegen (Muster: `test_a_goal_can_be_added_and_removed_from_the_page`),
keine Beträge aus dem Haushalt.

**Umgesetzt am 07.10.2026.** Zuerst der Fund aus der Abnahme von Z.1:
`Progress.mit_puffer` (es gibt ein Puffer-Ziel, und dieses Ziel ist ein
anderes) und `ziele._umschichtet`; gilt beides und wächst die Rate mit dem
Depotsatz, wächst der Rest von Tagesgeld und Giro nach dem Notgroschen mit dem
Depotsatz, und die Herleitung sagt, dass die Kaskade ihn ins Depot schiebt.
Danach die Karte: `_karte` bekommt `mit_rendite`, `mit_rendite_satz` und
`mit_rendite_herleitung` (leer, wo es keine zweite Rate gibt; daran erkennt die
Vorlage den Unterschied zu „der Bestand reicht“), die Route ruft
`rate_mit_rendite` mit `saetze_aus(annahmen, policen)`. In `ziele.html` heißt es
„/Monat ohne Rendite · Y mit Z %“, die Herleitung steht im
`details.rechenweg-ziel`, bei der Rentenlücke unter „Rate mit Rendite“ nach
ihrem bisherigen Rechenweg. Dazu der Filter `prozent` in `web/basis.py`.
`HANDBUCH.md`: ein Absatz; `finctl/HANDBUCH.md` ist nachgezogen. Tests:
Kaskade in `tests/test_ziele.py`, Karte in `tests/test_ziele_seite.py`.

### Z.3 Abnahme

- Alles gegen die Entwicklungskopie:
  `export FINCTL_DATEN="$HOME/Library/Application Support/Finance OS Entwicklung"`.
- `.venv/bin/python -m pytest -q`, dann die Browsertests allein
  (`-m browser -n 0`), weil eine Vorlage sich ändert. Beide Läufe auch mit
  `FINCTL_TESTDATEN=muster`.
- `tests/referenz.py pruefen`: Hauptbuch und alle anderen Seiten unverändert.
  Auf `/ziele` ändert sich nur der Text der Ratenzeile, und die neue Zahl
  kommt dazu. Die bestehenden Zahlen der Seite müssen gleich bleiben.
  Erst danach, in einem eigenen Schritt, die Referenz neu schreiben.
- Gegenprobe auf der Entwicklungskopie: Für ein Ziel mit Depot in der Basis
  die zweite Rate von Hand nachrechnen (Tabelle in `notizen/` im
  Datenordner, nicht hier). Sie muss zur Hochrechnung passen: Wer genau
  diese Rate spart, landet am Stichtag ungefähr beim Ziel. Erwartet ist,
  dass die Hochrechnung etwas darunter bleibt, weil sie den Zufluss eines
  Jahres erst im Folgejahr verzinst. Der Bericht nennt den Abstand in
  Prozent. Größere Abweichungen gehen in den Befund, nicht in eine Korrektur
  der Karte.

**Umgesetzt am 07.10.2026.** Beide Läufe der Suite und die Browsertests grün,
auch mit `FINCTL_TESTDATEN=muster`. Einzige rote Stelle:
`tests/test_referenz.py` (`seiten/ziele.txt`), gewollt, bis die Referenz in
einem eigenen Schritt neu geschrieben ist. `pruefen` meldet 2 Unterschiede in
1 Datei (`/ziele`, Zahlen und Text), und zwar nur die Ratenzeile und den
Rechenweg; alle bisherigen Zahlen der Seite bleiben. Die Zahlenebene ist reiner
Zuwachs. Vollständig in `notizen/Z.2_pruefen_unterschiede.md` im Datenordner,
neue Raten und Gegenprobe in `notizen/Z.1_zweite_rate.md`.

**Gegenprobe.** Die Hochrechnung mit der zweiten Rate als fester Sparrate
landet am Stichtag **nicht** knapp darunter, sondern beim größten Ziel bei
rund 107 % und beim zweiten bei rund 101 % des Ziels. Zwei Ursachen, beide
nicht die Karte (siehe unten). Ohne sie: rund 99,2 % und 99,9 %, also knapp
darunter wie erwartet. Mit der ersten Rate als Sparrate landen beide bei
rund 170 bis 200 %.

**Abgenommen am 07.10.2026 (Opus), Z.2 und Z.3.**
- **`pruefen` nachgerechnet:** Auf `/ziele` ändern sich nur die Ratenzeile und der
  Rechenweg. Die bisherigen Zahlen bleiben und stehen in derselben Zeile, die neuen
  kommen dazu. Hauptbuch und alle anderen Seiten sind gleich.
- **Kaskaden-Fund aus Z.1:** behoben.
- **Gegenprobe:** Ihre Zerlegung ist schlüssig. Ohne den Sparerpauschbetrag und ohne die
  auszahlende Police landet die Hochrechnung knapp unter dem Ziel, wie erwartet.
- **Handbuch:** Die Kürzungen sind angenommen. Die gestrichenen Begründungen stehen weiter
  in den Kommentaren von Vorlage und Code.
- **Auszahlende Police:** Die Frage geht an den Haushalt (siehe Gefundene Abweichungen).
- **Referenz:** Sie ist danach neu geschrieben.

Damit ist der Schritt erledigt.

## Ebenfalls entschieden (07.10.2026)

- Ob die zweite Zahl auch beim jüngsten Tempo stehen soll: nein.
  Die Sätze sind in beiden Tempi dieselben, nur die Sparrate unterscheidet
  sich, und die geht in diese Rechnung nicht ein.
- Ob „mit Rendite“ die erste Zahl werden soll, sobald der Haushalt ihr
  vertraut: nicht in diesem Schritt. Die Reihenfolge ist eine
  eigene Entscheidung, und die vorsichtige Zahl steht hier mit Absicht vorn.

## Gefundene Abweichungen

(Hier trägt jede Sitzung ein, was nicht in den Plan passt.)

- **Z.1, `Saetze` statt Mapping.** Die Sätze kommen als kleines Dataclass
  `Saetze(tagesgeld, depot, police, policen)` herein, nicht als Mapping mit
  drei Schlüsseln: Die Policen brauchen je Konto einen Satz und eine
  Vorgabe für eine Police ohne Eintrag. Die Route (Z.2) ruft nur
  `ziele.saetze_aus(e.annahmen, e.policen)`; `ziele.py` importiert `jahre`
  weiterhin nicht (`saetze_aus` liest die Felder der `Annahmen`).
- **Z.1, Signatur.** `rate_mit_rendite` nimmt `balances` statt `toepfe_heute`
  und bildet den Bestand je Art selbst (`bestand_der_basis`). Nur so lässt
  sich der Abzug und die Basis genauso zählen wie `progress`.
- **Z.1, Schuld über dem Depot.** Entscheidung 3 hört bei „vom Depot“ auf.
  Reicht auch das nicht, nimmt der Abzug weiter aus den Policen, zuletzt.
  Ohne diese Fortsetzung stimmte die Summe nicht mehr mit `have_cents`
  (`liquid_cents` zieht bis null ab).
- **Z.1, keine zweite Zahl bei gerundeter erster Rate 0.** Die Bedingung
  „erste Rate schon 0“ gilt für `monthly_needed_cents == 0`, nicht nur für
  eine Lücke von null Cent.
- **Z.1, Beobachtung, kein Fehler von Z.1.** Mit Notgroschen (und ohne Basis)
  zieht `progress` die Verbindlichkeiten nicht zusätzlich ab, sie stecken im
  Notgroschen. Die Bestände je Art folgen dem und zählen sie dann auch nicht
  ab.
- **Abnahme Z.1, Tagesgeld über dem Notgroschen (Opus).** Die Prüfung des
  Plans hat übersehen, dass die Kaskade umschichtet. Gibt es ein Ziel
  `tagesgeld-puffer`, schiebt sie jedes Jahr alles über der Grenze ins Depot
  (`jahre.kaskade`, `ins_depot`). Ohne dieses Ziel ist die Grenze unendlich,
  und nichts wandert. Die Karte lässt den Rest von Tagesgeld und Giro nach dem
  Notgroschen aber mit dem Tagesgeldsatz und mit 0 % stehen. Die zweite Rate
  ist dadurch höher als nötig, auf der Entwicklungskopie um rund ein Zehntel.
  **Schritt:** Z.2, vor der Karte. Wächst die Rate mit dem Depotsatz und gibt
  es ein Puffer-Ziel, wächst dieser Rest mit dem Depotsatz. Die Herleitung
  sagt, dass die Kaskade ihn ins Depot schiebt. Ohne Puffer-Ziel und bei einer
  Basis ohne Depot bleibt es wie in Z.1.
- **Z.2, Handbuch an der Wortgrenze.** Der Abschnitt `/ziele` stand bei genau
  200 Wörtern (`handbuch_woerter_max`). Der neue Absatz kam nur hinein, weil
  vier vorhandene Sätze kürzer wurden. Gestrichen sind nur Begründungen: beim
  Wendepunkt (Erstattung), beim Ziel ohne Stichtag (kein Zeitpunkt) und in der
  Einleitung („nur der zweite lässt ein kaum begonnenes Depot halb fertig
  aussehen“, steht weiter im Kommentar von `ziele.html`); die Notiz ist knapper
  gefasst.
- **Z.2, Feld statt Parameter.** Ob es ein Puffer-Ziel gibt, steht als
  `Progress.mit_puffer`, nicht als vierter Parameter von `rate_mit_rendite`:
  `progress` weiß es ohnehin, und die Signatur bleibt die von Z.1.
- **Z.3, Gegenprobe, Ursache 1: der Sparerpauschbetrag.** Die Hochrechnung
  rechnet ihn mit, die Karte nicht (Entscheidung 2). Das macht auf die
  Gegenprobe rund 1 Prozentpunkt. Gewollt vorsichtig, keine Änderung.
- **Z.3, Gegenprobe, Ursache 2: eine auszahlende Police.** Hat ein Ziel eine
  Basis ohne Policen und fällt eine Auszahlung vor den Stichtag, schiebt die
  Hochrechnung sie in den Topf Depot, und das Ziel zählt sie dort mit; die
  Karte zählt nur, was heute in der Basis liegt. Beim größten Ziel sind das
  rund 7 Prozentpunkte. Die Karte ist dadurch vorsichtig, nicht falsch. Das
  Ziel selbst benennt die Auszahlung nicht (`gedeckt_durch` fehlt); trüge der
  Haushalt sie dort ein, senkte `covered_cents` beide Raten. Ob stattdessen
  die Hochrechnung die Auszahlung nur den Zielen zurechnen soll, deren Basis
  Policen nennt, ist eine eigene Entscheidung. **Schritt:** keiner. Entschieden
  am 07.10.2026: Es bleibt so. Policen sind Reserve, die Karte ist dadurch
  vorsichtig, und kein Ziel trägt die Auszahlung als zugesagt.
