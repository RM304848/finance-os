# Änderungen

Was sich von Version zu Version ändert, in Worten für die, die die App
benutzen. Neues kommt unter **Unveröffentlicht**; `werkzeuge/release.py`
macht daraus beim Veröffentlichen die neue Version.

## Unveröffentlicht

## 0.5.0 – 2026-11-01

**Auf einen Blick:** Diese Version ist die erste, die jemand ohne Vorkenntnisse unter Windows
einrichten kann.
- **Sparkasse:** Exporte aus dem Online-Banking werden gelesen (CSV-CAMT V8/V2, CSV-MT940). Den
  Kontostand, den der Export nicht mitliefert, trägst du einmal im Monatsabschluss ein.
- **Erster Start:** Die Einrichtung führt durch Sicherung, Konten und, falls die Prognose an ist,
  das Geburtsdatum. Seiten ohne Daten sagen, was zu tun ist, statt rot zu warnen.
- **Windows:** Pfade, Ordnernamen und Hinweise stimmen unter Windows. Die ganze Testsuite läuft
  dort mit.
- **Konten und Hochrechnung** rechnen aus denselben Eingaben: aus den letzten zwölf Monaten,
  Verträgen, Objekten, erwarteten Einnahmen und den Zinssätzen der Konten.
- **Begründungen** stehen als Notizen am Eintrag.

Die Einzelheiten:

- **Sparkasse: Kontostand aus einem eingetragenen Stand:** Die Sparkasse-CSV trägt keinen Saldo; bisher
  zeigte die App als Kontostand die Summe der letzten Datei. Jetzt trägst du im **Monatsabschluss**
  unter **Konten** einmal den „Kontostand laut Online-Banking“ ein, und alle Seiten rechnen von dort mit
  den Umsätzen vor und zurück. Bis dahin steht dort „Kontostand fehlt: einmal eintragen“. Das gilt auch
  für Commerzbank und N26.
- **Der erste Start läuft durch:** Das erste **Update** eines neuen Datenordners brach mit einem
  Datenbankfehler ab, sobald die mitgelieferten allgemeinen Regeln an waren (die Voreinstellung);
  das ist behoben. Wer nur die Basis eingeschaltet hat, liest auf dem **Monatsabschluss** keine
  Zeilen mehr zu **Planung**, **Konten** und **Fortschritt** und keine Kachel „Cashflow ohne
  Objekte“; **Ziele** zeigt den **Wendepunkt** erst, wenn es Ausgaben gibt, und **Konten** das
  Gemeinschaftskonto nur, wenn dort etwas gebucht ist. In der **Einrichtung** ist „Wo die Daten
  liegen“ von Anfang an erledigt, und „Wer plant“ ist erst offen, wenn **Prognose und Planung**
  an ist. Der Hinweis auf dem **Monatsabschluss** ist nicht mehr rot. Das **Handbuch** beginnt mit
  dem ersten Start, die Kategorie „Katze“ heißt „Haustier“, und das Sicherungsziel sagt, dass ein
  Cloud-Ordner den Rechner verlässt.
- **Sparkasse: Exporte aus dem Online-Banking werden gelesen:** **CSV-CAMT V2**, **CSV-CAMT V8**
  und **CSV-MT940** (Umsätze → Exportieren) werden beim Einlesen erkannt, mit Umlauten, vorgemerkten
  Umsätzen und Beträgen über 1.000 €. Mandats-, Gläubiger- und Kundenreferenz gehen in den Suchtext
  der Regeln. Vorgemerkte Umsätze werden übersprungen, und der Import sagt, wie viele. Eine Datei
  mit Umsätzen mehrerer Konten wird abgelehnt, damit nichts im falschen Konto landet. Der
  Monatsabschluss meldet bei Sparkasse-Konten keine „Lücke“ mehr, nur weil die Datei keinen Saldo
  trägt, und hält einen Monat für vollständig, wenn die letzte Buchung am Freitag vor dem
  Wochenende zum Monatsende lag.
- **Konten und Hochrechnung rechnen aus denselben Eingaben:** Bisher zeigten **Konten** (Monat für
  Monat, 60 Monate weit) und **Hochrechnung** und **Ziele** (Jahr für Jahr) verschiedene Zahlen
  für denselben Haushalt, weil sie ihre Eingaben verschieden lasen. Jetzt nehmen beide dieselben:
  Was nicht als Reihe mit Takt, Vertrag oder Planzeile dasteht, ist die **Summe der letzten zwölf
  Monate**, auf **Konten** durch zwölf geteilt und auf dem Konto gebucht, auf dem gemessen wurde.
  Bisher rechnete **Konten** mit sechs Monaten und dem Median; der ließ seltene Ausgaben (Arzt,
  Reparatur) ganz weg. Jetzt zählen sie mit: **Konten** wird vorsichtiger und warnt bei einem
  knapp geführten Girokonto öfter. Das ist gewollt. Eine Ausgabe, die nicht wiederkommt, markierst
  du als „einmalig“ oder trägst sie in **Planung** ein. Gemessene Beträge und Verträge steigen
  außerdem in beiden gleich, stetig ab der Mitte der zwölf Monate; Policenbeiträge und
  Kreditraten bleiben fest. Die Zahlen auf **Konten**, **Ziele**, **Monatsabschluss** und im
  Treffer-Check unter **Annahmen** ändern sich dadurch; **Hochrechnung** bewegt sich nur dort,
  wo sie bisher etwas nicht sah (Nebentätigkeit, unten).
- **Gehalt: eine Zahl für beide:** Beide rechnen mit der **Gehalts-Untergrenze** aus den
  **Annahmen**, die zum 1. Januar mit der **Gehaltssteigerung** wächst. Der Median steht nur noch
  als Vergleich auf **Annahmen**. Die Zahl „davon Gehalt“ in der Kachel Einnahmen im
  **Monatsabschluss** (und der Anteil „vom Gehalt“ in der Kachel Ausgaben) summiert genau die
  Kategorie `einkommen/gehalt`: Eine Nebentätigkeit zählt nicht mehr zum Gehalt, beide Zahlen
  sind dadurch etwas anders.
- **Planung: neue Zeilenart „Erwartete Einnahme“:** Für eine Schenkung oder eine Nebentätigkeit,
  deren Buchungen kein Muster ergeben, legst du eine Zeile mit Betrag, Takt (monatlich,
  quartalsweise, jährlich, einmalig), Start und optional Ende an und ordnest ihr die Buchungen
  zu. Die Zeile **ersetzt** diese Buchungen und ihre Reihe in beiden Rechnungen und zählt voll, mit
  festem Betrag. Schaltest du die Klammer aus, kehrt die Messung zurück. Die Nebentätigkeit fehlte
  bisher in der **Hochrechnung** ganz; sie zählt jetzt, und die Endstände sind etwas höher.
- **Zinsen und Steuer aus Kontostand und Zinssatz:** **Konten** rechnet den Zins jedes Monats aus
  dem Stand des Kontos und seinem Satz (**Annahmen**, Zinssätze je Konto), die Kapitalertragsteuer
  nach dem Sparerpauschbetrag des Haushalts, wie die **Hochrechnung**. Gebuchte Zinsen zählen in
  keiner Prognose mehr; leert eine Klammer ein Konto, sinkt der Zins von selbst. Die Zeilen in
  **Planung**, die Zinsen oder Kapitalertragsteuer von Hand ausgleichen, werden überflüssig und
  zählen nicht mehr.
- **Konten: Objekt, Verträge und durchlaufende Konten:** Die Prognose eines Objekts
  (**Immobilien**, Miete und Kosten) rechnet jetzt auch auf **Konten**, auf dem Konto, auf dem die
  Miete landet, statt der gemessenen Buchungen des Objekts; findet sie kein Konto, sagt **Konten**
  es. Verträge zählen in beiden über Betrag, Takt, Laufzeit, Kündigung und den Anteil der
  Mitzahler, nicht über ihre Buchungen. Die Ausgaben eines durchlaufenden Kontos zählen auf dem
  Konto, das es deckt, und Teile ohne Kategorie stehen als „ohne Kategorie“ in den Posten. Der
  Tiefpunkt des Betriebskontos kann dadurch tiefer liegen: Es trägt die Kosten des Objekts, bis
  die Miete kommt.
- **Notgroschen und kurzfristige Ziele:** Die Grenze des Notgroschens ist die Untergrenze des
  Tagesgeldkontos auf **Konten**; eine Klammer, die ihn angreift, löst jetzt die Warnung aus. Ein
  Ziel, dessen Stichdatum in den nächsten 60 Monaten liegt, misst **Konten**: Auf **Ziele** steht
  „vorausgerechnet zum …“, und eine Klammer mit einer Ausgabe vor dem Stichdatum bewegt die
  Karte. Hängt an der Basis etwas, das **Konten** nicht rechnet (ein Depot, eine Police), misst
  weiter die **Hochrechnung**. Im **Monatsabschluss** zerlegt „Wirkung auf deine Ziele“ ein solches
  Ziel nicht mehr nach Ursachen, sondern sagt, dass **Konten** es misst. Ein Konto ohne Auszug
  nimmt in beiden den jüngsten getippten Stand bis zum Stichtag.
- **Treffer-Check: Spalte „Verträge“:** Unter **Annahmen**, Prognosebasis, Treffer, stehen
  Verträge und Objekte als eigene Posten mit eigener Spalte „Verträge“, statt in den Fixkosten zu
  verschwinden. Eine Buchung, die ein Vertrag oder eine erwartete Einnahme ersetzt, steht in keinem
  Block mehr; die Fixkosten stehen deshalb niedriger. Die Prognosebasis
  zählt in beiden Spalten, was die Rechnungen zählen: bei Verträgen, erwarteten Einnahmen und
  der Objektprognose deren Posten statt der ersetzten Buchungen (das Objekt steht als eigene
  Zeile „… (Objektprognose)“). Die Summen im Kopf stimmen dadurch bis auf Rundung überein, und
  ihre Texte erklären nicht mehr, warum beide Rechnungen verschieden rechnen, denn sie rechnen
  gleich. Verschieden bleiben
  nur die Kaskade (Tagesgeld bis zum Ziel, der Rest ins Depot), die Rendite, Teilzeit, Verkauf und
  Ruhestand, die nur die **Hochrechnung** kennt, und die Regeln der Konten, die nur **Konten**
  kennt.
- **Nach dem Update tun:** Lösche in **Planung** die Zeilen, die Zinsen oder Kapitalertragsteuer
  ausgleichen (sie zählen nicht mehr). Lege Schenkung und Nebentätigkeit als „Erwartete
  Einnahme“ an und ordne ihnen die Buchungen zu, sonst zählt die Messung weiter. Trage auf
  **Annahmen** die Zinssätze deiner Tagesgelder ein: Ohne Eintrag zahlt ein Tagesgeld den
  langfristigen Satz, ein Girokonto nichts. Markiere Ausgaben, die nicht wiederkommen, als
  „einmalig“. Die Schlüssel `window_months`, `min_occurrences`, `variable_kosten` und
  `window_months_fixkosten` in `forecast.yaml` liest die App nicht mehr; du kannst sie löschen.

- **Begründungen stehen als Notizen am Eintrag:** Was bisher als `#`-Kommentar in den Dateien
  von `config/` stand, ist jetzt die **Notiz** des Eintrags: eines Kontos, Kredits, Objekts,
  Ziels, einer Rente, eines Vertrags, einer Regel, einer Kategorie oder einer Position im
  Monatsabschluss. Eine Einstellung ohne Kennung und eine ganze Datei tragen ihre Notiz unten in
  der Datei unter `notizen:`. Eine Notiz bekommt ihr Datum, sobald du ihren Text änderst; die
  übernommenen haben keins, denn wann ein Kommentar entstand, weiß niemand. Wer eine Datei von
  Hand ändert, schreibt das Warum in `notiz`, nicht als Kommentar. Die Seiten schreiben die
  ganze Datei samt Notizen, und Speichern ohne Änderung ändert nichts. Die Notizfelder auf
  **Konten**, **Reihen**, **Ziele**, **Renten**, **Verträge** und im **Monatsabschluss** sind
  mehrzeilig, behalten ihre Zeilenumbrüche und kürzen nichts mehr.
- **Eine Datei je Sache:** Die zweite Datei, in die die Oberfläche bisher schrieb
  (`*_custom.yaml`), gibt es nicht mehr. Verträge, Versicherungen, Stände, Ziele, Kredite,
  Objekte, Renten, Kategorien, Regeln, Konten, Lebensplan, Sicherung und Annahmen stehen je in
  der Datei, die du auch von Hand schreibst: `abos.yaml`, `versicherungen.yaml`,
  `balances.yaml`, `goals.yaml`, `loans.yaml`, `properties.yaml`, `renten.yaml`,
  `taxonomy.yaml`, `rules.yaml`, `accounts.yaml`, `lebensplan.yaml`, `backup.yaml`,
  `forecast.yaml` und `assumptions.yaml`. Was du auf **Annahmen** gedreht oder auf **Konten**
  als Untergrenze gesetzt hast, steht jetzt dort. Sechs Dateien ohne Gegenstück behalten ihren
  Namen: Reihen, Geteilt, Zinssätze, Prognosebasis, Module und die CSV-Zuordnungen
  (`reihen_custom.yaml` und die übrigen). Die Fußzeile der Seiten nennt entsprechend weniger
  Dateien.
- **Umstieg mit `finctl umstellen`:** Wer schon Daten hat, stellt den Datenordner einmal um.
  Der Befehl sichert `config/` nach `archiv/vor_umstellung_<Datum>/`, macht aus den
  Kommentaren Notizen, legt je zwei Dateien zu einer zusammen und schreibt einen Bericht nach
  `notizen/umstellung_<Datum>.md`: jeder Kommentar und wo er jetzt steht, was weggefallen ist,
  was beim Zusammenlegen mit der Seite geschah. Ein zweiter Lauf ändert nichts. Mit
  `finctl umstellen --probe <ordner>` siehst du den Bericht vorher, ohne dass im Datenordner
  etwas geschieht. Solange etwas umzustellen ist, hält die App an, nennt beide Befehle und
  liest nicht still nur die halben Werte; sie tut es auch, wenn du später in einer Datei einen
  neuen `#`-Kommentar schreibst. Kein Betrag, kein Datum und keine Buchung ändert sich.
  Danach `finctl init`, `finctl ingest run`, `finctl categorize` und `finctl validate`; was
  vorher zu prüfen ist, steht im Handbuch unter „Umstieg auf Notizen“.
- **Was auf den Seiten wegfällt:** Es gibt keine zweite Datei mehr, die ein Wert überschreiben
  könnte, und also nichts, wohin man „zurück“ könnte. Weg sind auf **Annahmen** die Pille
  „überschrieben“ mit dem „dokumentierten“ Wert und der Knopf „zurück“ (ein leeres Feld nimmt
  die Angabe heraus), auf **Monatsabschluss** und **Renten** der Knopf „zurück“, auf **Konten**
  und **Ziele** die Pille „eigen“, auf **Verträge** die Pille „angelegt“ und das „Ausblenden“
  (es gibt nur noch „Löschen“) und auf **Regeln** der Hinweis, ob eine Regel „hier geändert“
  oder „hier angelegt“ wurde.
- **Entfernen nimmt die Notiz mit:** „Entfernen“ auf **Kredite** und **Immobilien**, „Löschen“
  auf **Verträge**, **Ziele** und **Renten** (jetzt für jede Rente) und „streichen“ einer
  Verbindlichkeit im **Monatsabschluss** nehmen den Eintrag samt seiner Notiz aus der Datei.
  Ein leeres Feld der Objektprognose nimmt die Angabe heraus. Was vorher mit „Ausblenden“ nur
  versteckt war, steht nach dem Umstieg nicht mehr in der Datei, sondern in der Sicherung.
- **Konten, die Untergrenze aus dem Kredit bleibt:** Wer auf **Konten** eine Kontokarte
  speicherte, deren Untergrenze aus einem Kredit kommt, ersetzte dessen Kennung durch ein
  bloßes „ja“; dann suchte die Prognose keinen Kredit mehr, und die Untergrenze fiel auf den
  getippten Wert oder die Warnschwelle des Kontos zurück. Jetzt bleibt die Kennung stehen.
- **Monatsabschluss, Notiz und Speichern:** In einer Notiz ist Enter ein Zeilenumbruch;
  gespeichert wird mit Strg oder Cmd und Enter. Bisher speicherte Enter, und eine zweite Zeile
  ließ sich nicht schreiben. Der Klick auf „Speichern“ ging verloren, wenn die Notiz länger als
  zwei Zeilen war: Beim Klick schrumpfte sie, die Zeile wurde niedriger, und der Knopf rutschte
  unter dem Zeiger weg.
- **Einrichtung, Speichern ohne Änderung:** „Speichern“ bei den Modulen legte jedes Mal die
  Datei der Module an, auch wenn sich nichts geändert hatte. Jetzt entsteht sie erst, wenn
  sich die Auswahl ändert.
- **Kategorien, Umbenennen und Löschen:** Eine Kategorie umbenennen behält jetzt ihre
  Merkmale (`fix`, `tax`, `einmalig`); bisher blieb nur der Name. Eine Kategorie,
  die schon in der Kategorienliste stand und die du auf **Kategorien** löschst, bleibt
  gelöscht; bisher kam sie beim nächsten `finctl init` zurück.
- **Anschlusskonditionen löschen keine anderen Kredite mehr:** Wer auf **Kredite** die
  Anschlusskonditionen eines Vertrags speicherte, verlor dabei die selbst angelegten Kredite und
  die Konditionen der Vorlagen: Gespeichert blieb nur dieser Anschluss. Jetzt bleibt alles
  andere stehen. Dazu: Ein Konto, ein Kredit, eine Kategorie, ein Abo, ein Ziel oder eine
  Verpflichtung lässt sich nicht „notiz“, „notiz_vom“ oder „notizen“ nennen, denn diese Wörter
  gehören den Notizen; und die Notiz einer Reihe auf **Reihen** bekommt kein Datum, wenn nur
  der Takt geändert wird und sie keins hatte.
- **Betriebliche Altersvorsorge, Satz und Teilzeit sichtbar:** Eine betriebliche
  Altersvorsorge, die nur der Arbeitgeber zahlt, steht auf **Renten** jetzt mit Stand, Beitrag
  des Arbeitgebers je Jahr und dem **Satz**, mit dem beides zum eingetragenen Betrag wächst.
  Nennt die Mitteilung zu ihrem Prüfwert keinen Satz, steht daneben der Satz, der von Stand und
  Beitrag zu ihm führt, damit man sieht, was die Mitteilung unterstellt und was du ansetzt.
  Dazu die Auszahlung ohne und mit der Teilzeit aus den **Annahmen**. Im Rechenweg der
  Auszahlung auf **Hochrechnung** nennt die Herleitung den Satz immer, nicht nur bei
  eingeschalteter Teilzeit. Auf **Planung** zeigt eine Zeile der Klammer „Teilzeit“ ohne
  eigenes Datum „ab Teilzeitstart“ mit dem Monat aus den Annahmen; im Bearbeitungsfeld bleibt
  das Datum leer, und Speichern behält die Zeile ohne eigenes Datum, damit sie mit dem
  Teilzeitstart wandert.
- **Ziele, zweite Monatsrate mit Rendite:** Neben der Rate, die ein Ziel **ohne Rendite** braucht
  (die Lücke geteilt durch die Monate bis zum Stichtag, wie bisher, nur jetzt so benannt), zeigt
  die Karte auf **Ziele** dahinter die Rate **mit Rendite** samt ihrem Satz, zum Beispiel
  „· 900,00 € mit 5,00 %“. Dabei wachsen Bestand und Rate mit den Sätzen der Hochrechnung: Tagesgeld,
  Depot nach Vorabpauschale, Policen nach Kosten, Giro gar nicht. Gibt es ein Tagesgeld-Ziel
  (Notgroschen), wächst, was darüber liegt, wie das Depot, weil die Hochrechnung es dorthin
  schiebt. Reicht der gewachsene Bestand allein, steht „mit Rendite reicht der Bestand“. Jeder
  Schritt der Rechnung steht im aufklappbaren **Rechenweg** der Karte, auch bei Zielen, die nicht
  gerechnet sind. Ohne Stichtag, bei einer Basis aus einzelnen Konten oder nur aus Giro und
  Policen gibt es keine zweite Rate.
- **Policen, Notfallwert und Prüfwert:** Im **Monatsabschluss** fragt jede Rentenversicherung
  unter ihrer Zeile den **Rückkaufswert**, die **eingezahlten** Beiträge, den Policenwert laut
  Mitteilung und den Stand der Mitteilung ab. Gespeichert wird wie beim Policenwert, in
  `balances.yaml`. Auf **Konten** zeigt der neue Abschnitt „Policen im Notfall“ je
  Police den **Notfallwert**: Rückkaufswert minus Steuer auf den Ertrag (Rückkaufswert minus
  eingezahlt, nicht unter null). Ist der Policenwert neuer als die Mitteilung, gilt das
  Verhältnis aus Rückkaufswert und Policenwert der Mitteilung, angewandt auf den aktuellen
  Policenwert; fehlt der Policenwert der Mitteilung, bleibt der Rückkaufswert auf seinem
  Stand, und die Zeile sagt es. Fehlen die eingezahlten Beiträge, ist die Steuer auf den
  ganzen Rückkaufswert gerechnet und der Notfallwert steht als „mind.“ da. Der Notfallwert wird
  nur gezeigt: Notgroschen und liquides Vermögen rechnen weiter mit dem Policenwert. Auf
  **Renten** steht bei einer Police mit Prüfwert darunter der Prüfwert der Mitteilung neben
  dem Wert des Modells, in demselben Satz, den der Rechenweg der Auszahlung auf
  **Hochrechnung** nennt.
- **Hochrechnung, Policen wachsen mit Beitrag und Kosten:** Eine Police wächst jetzt so,
  wie ihre Mitteilung es rechnet: Monat für Monat mit der Rendite des Depots abzüglich
  ihrer **Effektivkosten** (auf **Renten**), und ihr Monatsbeitrag kommt dazu. Bisher
  wuchs sie nur mit dem Depotsatz auf den getippten Stand, der Beitrag kam nie in ihr an
  und ihre Kosten zählten nicht: Die Auszahlungen waren viel zu niedrig. Der Beitrag
  bleibt eine Ausgabe, und die Sparrate ändert sich nicht; sein Geld kommt in der Police
  an (auf **Hochrechnung** im Rechenweg als „Beiträge in die Policen“, ohne neues Geld zu
  schaffen). Er endet mit der Auszahlung, mit einer Kündigung des Vertrags und in einem
  Szenario, das ihn mit einer Wegfall-Zeile beitragsfrei stellt; die Police wächst dann
  ohne ihn weiter. Nach der Auszahlung steigt die Sparrate um ihn. Im Rechenweg der
  Auszahlung stehen Stand, Beitrag und Satz nach Kosten, daneben eine Spalte aus der
  Mitteilung als Prüfwert mit der Abweichung des Modells in Prozent. Damit der Beitrag
  ankommt, trägst du bei der Rentenquelle `beitrag:` ein (die Kennung des Vertrags unter
  **Versicherungen**; Betrag und Takt stehen dort) und optional `pruefwert:`. Hochrechnung,
  Ziele und Annahmen zeigen dadurch andere Zahlen; der Abzug auf eine Auszahlung bleibt
  pauschal und trifft jetzt eine größere.
- **Hochrechnung, Abzug von der Auszahlung einer Police:** Der pauschale Abzug („Abzug auf
  Renten (Steuer und KV)“ auf **Annahmen**) geht bei der Kapitalauszahlung einer Police von
  der Auszahlung selbst ab, wie der Versicherer die Steuer einbehält: Ins Depot kommt der
  Rest. Bisher zahlte ihn das Tagesgeld, das im Jahr der größeren Auszahlung ins Minus fiel,
  und die Kopfzeile von **Hochrechnung** meldete ein Ende des Kapitals, das es nicht gibt.
  Der Abzug steht nicht mehr als Ausgabe unter „Renten“ und fehlt in der Sparrate des
  Jahres; der Rechenweg nennt Auszahlung brutto, Abzug und netto, und das Endkapital des
  Jahres rechnet ihn ab. Außerdem wächst die Ausgabe für den Beitrag in eine Police in der
  Hochrechnung nicht mehr mit der Inflation: Es geht genau das in die Police, was als
  Beitrag abgezogen wird, und nach der Auszahlung oder einer Beitragsfreistellung bleibt
  kein Rest stehen. Die Sparrate vor der Auszahlung ist dadurch etwas höher. Die Zeile
  „Barista FIRE … hochgerechnet“ im **Monatsabschluss** rechnet wie das Ziel auf **Ziele**:
  zum Stichtag des Ziels und gegen seine Basis, nicht mehr mit dem ganzen Endkapital
  samt Policen am Jahresende. Im Rechenweg stehen die Restmonate des laufenden Jahres bei
  Beitrag und Rendite einer Police nur einmal.
- **Reihen, neue Seite unter Stammdaten:** Sie zeigt zu jeder Zahlung, die regelmäßig
  kommt, wie oft sie kommt (monatlich, alle zwei, drei, vier oder sechs Monate, jährlich
  oder unregelmäßig), den Betrag je Termin, den letzten Termin, ob sie noch läuft, und
  den Jahreswert. Eine Reihe ist derselbe Empfänger in derselben Kategorie, über alle
  Konten. Aufklappen zeigt die Termine; was zusätzlich kommt, etwa eine Nachzahlung, ist
  als Ausreißer markiert. Den Takt legst du je Reihe fest, mit Notiz, oder nimmst die
  Festlegung zurück; er steht in `reihen_custom.yaml`.
- **Hochrechnung und Konten rechnen mit dem Takt der Reihen:** Eine Zahlung mit festem
  Takt zählt mit ihrem Betrag je Termin, so oft sie im Jahr kommt, statt mit dem, was
  zufällig in den letzten Monaten lag. Eine Erhöhung zählt sofort, ein gekündigter
  Vertrag fällt heraus, sobald zwei Termine fehlen (bei längeren Takten ein halber Takt),
  und eine Jahreszahlung steht auf **Konten** in ihrem Monat. Kosten und Einnahmen
  derselben Kategorie stehen dort getrennt, jede an ihrem Tag: Wer eine geteilte Miete am
  Monatsanfang zahlt und den Anteil am Monatsende bekommt, sieht den Tiefpunkt im Monat
  jetzt so tief, wie er ist. Ziele, Konten und Annahmen zeigen dadurch andere Zahlen.
- **Reihen, Schreibweisen zusammenführen:** Schreibt die Bank einen Zahler mal so, mal so,
  zählte jede Schreibweise als eigene Reihe: Die alte war nach zwei Monaten beendet, die
  neue brauchte drei Termine, und dieselbe Zahlung kam in der Vorschau doppelt vor oder
  gar nicht. Auf **Reihen** wählst du an einer Reihe „Gehört zu“ und führst zwei
  Schreibweisen zu einer Reihe zusammen; sie heißt nach der, zu der sie gehört, und
  Kontoprognose und Hochrechnung zählen sie einmal. Wo eine Reihe endet und eine gleich
  teure derselben Kategorie einen Takt später beginnt, steht oben ein Vorschlag;
  zusammengeführt wird erst auf den Klick, und Trennen nimmt es zurück. Regeln und
  Verträge sehen weiter jede Schreibweise einzeln. Es steht in `reihen_custom.yaml`.
- **Einmalig statt Sondereffekte:** Der Bereich „Sondereffekte“ heißt überall „Einmalig“.
  Auf **Reihen** setzt du einzelne Buchungen einmalig, bei den Terminen einer Reihe; sie
  zählen dann in keiner Fortschreibung und gehören in keine Reihe. Kategorien tragen dafür
  das Merkmal `einmalig` (wie `fix`); in der mitgelieferten Kategorienliste trägt es
  „Kaufnebenkosten“. Wer eine eigene `taxonomy.yaml` hat, trägt `einmalig: true` bei
  Kaufnebenkosten nach, sonst zählen sie wie Immobilienkosten. Die Datenbank wird beim
  ersten Start erweitert, die Daten bleiben erhalten.
- **Monatsabschluss, Wirkung auf deine Ziele:** Neuer Abschnitt. Er zeigt je Ziel,
  wie weit sich der erwartete Stand am Stichdatum gegenüber dem Monat davor bewegt
  hat, im Schnitt der letzten Monate und im Tempo der letzten drei Monate. Aufklappen
  zeigt die Ursachen: „Der Monat“, „Tempo“ je Bereich, „Gehalt“ und „Planzeilen“. Bei
  „Tempo“ stehen die Kategorien dabei, deren Jahreswert sich geändert hat, mit dem
  Monat, der aus dem Zeitraum fiel, und dem, der dazukam, je mit Betrag und Zahl der
  Buchungen. Darunter steht „Der Monat“ mit Prognose gegen Ist und der Kursbewegung
  der Depots. Gerechnet wird unter den heutigen Annahmen.
- **Monatsabschluss, Verlauf der Stände:** Für den Vergleich merkt sich die App den
  Stand jeder getippten Position je Monat: Jedes Speichern im Monatsabschluss legt
  ihn in `balances.yaml` ab. Solange der Stand vom Monat davor fehlt, nennt
  der Abschnitt, was fehlt und ab wann es einen Vergleich gibt.
- **Hochrechnung und Ziele, Tempo der letzten drei Monate:** Die Hochrechnung
  rechnet wahlweise im Tempo der letzten drei Monate statt im Schnitt der letzten
  zwölf. Auf **Hochrechnung** schaltest du oben um, auf **Ziele** stehen beide
  Werte nebeneinander. Das gilt für „Konsum und Rest“; Einnahmen, Fixkosten,
  Steuern und Immobilienkosten bleiben beim Schnitt. Wer zuletzt sparsamer war,
  sieht es sofort. Im Rechenweg steht jetzt auch eine Kategorie mit null, die in
  der Zeit nichts gebucht hat.
- **Hochrechnung, Zinsen und Steuer:** Zinsen auf dem Tagesgeld zählten bisher
  doppelt: einmal mit dem Satz des Tagesgelds und noch einmal als gebuchte
  Einnahme, die mit der Inflation fortgeschrieben wurde. Die gebuchte
  Kapitalertragsteuer wurde ebenfalls fortgeschrieben, obwohl auf die
  gerechneten Zinsen keine Steuer anfiel. Jetzt rechnet die Hochrechnung beides
  selbst: Das Tagesgeld verdient den Satz seiner Konten, und die Steuer fällt auf
  Zinsen, Vorabpauschale und Verkaufsgewinne erst nach dem Sparerpauschbetrag an.
  Zahlen auf **Hochrechnung**, **Ziele** und in der Auswertung ändern sich.
- **Planung, Zeilen auf Zinsen und Kapitalertragsteuer:** Eine Planzeile in
  einer dieser beiden Kategorien, etwa „Konto X zahlt ein Jahr lang keine
  Zinsen“, gilt nur noch für die **Kontoprognose** unter /konten. Die
  Hochrechnung rechnet Zinsen aus dem Zinssatz des Kontos und die Steuer selbst;
  die Zeile zog dort einen Betrag ab, der nirgends mehr stand. Auf **/planung**
  steht das an der Zeile, auf **/annahmen** unter „Zinssätze je Konto“ beim Konto.
  Den Zinssatz, der die Zeile ersetzt, trägt der Haushalt selbst ein. Zahlen auf
  **Hochrechnung** und **Ziele** ändern sich, wo es solche Zeilen gibt.
- **Annahmen, Zinssätze je Konto:** Neuer Abschnitt unter den Stellschrauben.
  Je Konto ein Satz mit Zeitraum, etwa ein Aktionszins mit Ende. Ohne Eintrag
  verdient ein Tagesgeld den langfristigen Satz („Rendite Tagesgeld,
  langfristig“), ein Girokonto nichts.
- **Annahmen, Sparerpauschbetrag:** Neue Stellschraube, vorbelegt mit dem
  gesetzlichen Betrag für eine Person. Wer zusammen veranlagt wird, trägt den
  doppelten ein.
- **Kategorien:** Eine Kategorie-Kennung mit Großbuchstaben in der
  `taxonomy.yaml` wird beim Einlesen mit einer Meldung abgelehnt, die die
  Kennungen nennt. Kennungen sind klein geschrieben, damit Auswertungen eine
  Kategorie nicht übersehen; der Anzeigename darf Großbuchstaben haben. Was die
  Oberfläche anlegt, ist es schon.

## 0.4.1 – 2026-10-02

- **Prognose, tiefster Stand im Monat:** Eine Planzeile, die eine
  fortgeschriebene Position derselben Kategorie aufhebt (etwa „keine
  Zinsen“ gegen die Zinsen), steht jetzt am selben Tag wie diese Position.
  Bisher lag sie am anderen Ende des Monats, und der tiefste Stand fiel
  jeden Monat um ihren Betrag zu tief aus.
- **Wegfall** nimmt in der Kontoprognose genau heraus, was die Prognose für
  die Reihe bucht – auch bei Jahresposten und auf jedem Konto, auf dem sie
  liegt –, statt eines Durchschnitts der letzten zwölf Monate.
- Neu an der Wegfall-Zeile auf /planung: der Haken **„nur Kontoprognose“**.
  Für Ausgaben, die nur das Konto wechseln: Die Reihe verlässt das Konto
  der Zeile, die Jahresrechnung bleibt unberührt.
- `discontinued` in `forecast.yaml` gibt es nicht mehr. Was durch eine
  Entscheidung aufhört, steht als Wegfall auf /planung oder als Kündigung
  auf /abos. Wer `discontinued` benutzt hat, trägt diese Posten dort ein.

## 0.4.0 – 2026-10-02

- **DKB-CSV** ist an einem echten Export geprüft und berichtigt: Ganze
  Beträge ohne Komma (`2.000`) wurden als 2,00 € gelesen, jetzt als
  2.000,00 €. Der Zeitraum kommt aus der Zeile „Zeitraum:“.
- Die DKB nennt den Kontostand vom Tag des Exports. Deshalb: den Export
  **bis heute** wählen. Die Buchungen von heute bleiben für den nächsten
  Export, der an diesem Tag beginnt; ein Export, der früher endet, wird mit
  einer Meldung abgelehnt.
- Mandatsreferenz und Gläubiger-ID eines CSV-Exports erreichen die Regeln,
  wie im PDF-Auszug.
- Auf dem Mac steht Finance OS jetzt **in der Menüleiste** (ein Euro im
  Kreis): „Finance OS öffnen“ holt die Seite zurück, wenn der Tab zu ist,
  „Beenden“ beendet die App.
- **Rückblick → Fluss** zeigt auf Wunsch einen einzelnen Monat statt des
  ganzen Jahres; die Knoten führen zu den Buchungen dieses Monats.
- **Rückblick → Vorjahr** zeigt jedes Jahr nebeneinander, mit der
  Veränderung gegen das Jahr davor. Verglichen werden nur Monate, die in
  beiden Jahren abgeschlossen sind: kein Teiljahr gegen ein volles, und der
  laufende Monat nie.
- **Transaktionen** und **Buchungen zuordnen** haben eine Zeile „Zeitraum“
  (dieser Monat, letzter Monat, 90 Tage, dieses Jahr, letztes Jahr). Jede
  Wahl bei Zeitraum, Konto und Quelle sagt vorher, wie viele Buchungen übrig
  blieben; was nichts übrig ließe, ist blass.
- **Monatsabschluss**: Einnahmen, Ausgaben und Saldo führen zum
  Vorjahresvergleich. Neu ist „Bald fällig“ aus Verträgen und Krediten –
  größere Zahlungen 30 Tage vorher, das Ende einer Zinsbindung ein Jahr
  vorher –, als Kalenderdatei (.ics) je Frist oder alle zusammen.
- Fehlt einem Konto der Vormonat, nennt der Monatsabschluss trotzdem, bis
  wann der letzte Auszug reicht.
- Die Diagramme auf **Konten** zeichnet jetzt der Server: mit Legende,
  Tooltip (auch per Tastatur) und einer Tabelle mit denselben Werten.
- **CSV-Exporte** reichen so weit, wie die Bank im Kopf der Datei sagt,
  nicht nur bis zur letzten Buchung – ein ganzer Monat gilt damit als
  vollständig. Passt der genannte Zeitraum nicht zu den Buchungen, gelten
  die Buchungen, mit einer Meldung.
- **Sparda**: Der CSV-Export wird über das Atruvia-Profil eingelesen.
- **Scalable**: Auszüge mit einer Buchung am Monatsersten wurden abgelehnt,
  weil der Anfangsstand sie schon enthält. Jetzt passen sie.
- Kürzere Seiten: Monatsabschluss, Rückblick und Transaktionen tragen
  keine erklärenden Unterzeilen mehr; wann ein Stand aktuell ist, steht
  beim Haken.

## 0.3.0 – 2026-09-29

- Die Einrichtung sagt oben in drei Sätzen, wozu die App da ist, und
  verweist ins Handbuch. Derselbe Text steht oben im Handbuch.
- Rückblick: Der Fluss ist die erste Ansicht, danach Alle Kategorien,
  Fixkosten, Vorjahr.
- **Beenden** und die Speichern-Knöpfe der Einrichtung sind gefüllt und gehen
  nicht mehr unter.
- Kredite: **Neues Annuitätendarlehen** statt „Neuer Ratenkredit“ – gerechnet
  wird genau das, feste Rate mit wachsendem Tilgungsanteil.
- Die Einrichtung weist darauf hin, die Annahmen durchzugehen, solange noch
  keine angepasst ist – sie sind mitgelieferte Schätzungen.
- Neue Startwerte: Tagesgeld 2,5 %, Depot 7 % im Jahr (vorher je 5 %). Gilt
  für neue Installationen; eigene Annahmen bleiben, wie sie sind.
- Handbuch: Die Auszüge liegen in `data/statements/`, je Konto ein Ordner.
- **Ziele** sind von Anfang an nicht leer: Der Notgroschen ist vorgegeben,
  mit drei Monaten Gehalts-Untergrenze, bis du einen eigenen Betrag
  einträgst. Die Rentenlücke steht immer da; ohne Geburtsdatum sagt sie, was
  fehlt.
- **Teilzeit**: Anteil und Beginn stehen wieder in den Annahmen. Die Klammer
  „Teilzeit“ auf **Planung** gibt es immer, auch frisch installiert; sie ist
  von Haus aus aus und schaltet die Teilzeit ein. Werte, die du in der
  Klammer einträgst, gehen vor; leer gelassen gelten die Annahmen.
- Neue Seite **Renten** (unter Verträge): gesetzliche Rente und Policen
  anlegen und pflegen – Betrag laut Schreiben (nominal, bei mehreren
  Szenarien der mit 7 % Wertentwicklung), Bezug ab, Stand. Bisher ließen sich
  nur vorhandene ändern. Der Monatsabschluss prüft nur noch, ob das Schreiben
  aktuell ist, und führt dorthin.
- **Effektivkosten** je Rente oder Police. Liegen sie über deiner Schwelle
  (Annahmen, Vorgabe 1,3 %), steht ein Warnzeichen daneben.
- **Steuern in der Hochrechnung**, bewusst vorsichtig: Verkäufe aus dem
  Depot zahlen 26,375 % auf ihren Gewinnanteil (bisher gar nichts), ohne
  Teilfreistellung – auch bei der Vorabpauschale. Auf Kapitalauszahlungen
  von Policen geht derselbe Abzug wie auf Renten. Was vereinfacht ist, steht
  auf der Hochrechnung.
- Geteilt: **Budgettöpfe** statt Projekte – derselbe Inhalt, ein passenderer Name.
- **Allgemeine Regeln** kommen mit: rund vierzig Regeln für Supermärkte,
  Tankstellen, Streaming, Mobilfunk, Steuern und mehr. Wer neu anfängt, muss
  nicht jede Buchung von Hand zuordnen. Eigene Regeln gehen immer vor; unter
  **Regeln** lässt sich die Grundschicht abschalten, und vorher steht dort, wie
  viele offene Buchungen sie zuordnen würde.
- **Regelvorschläge über Claude** (Regeln → Vorschläge über Claude): Die App
  stellt die offenen Buchungstexte zusammen – ohne Beträge, IBANs und andere
  Nummern, einzeln abwählbar – und kopiert einen fertigen Auftrag. Die Antwort
  von Claude (auch der kostenlosen Version) fügst du ein; die App prüft jede
  Zeile gegen deine Kategorien und dein Hauptbuch, übernommen wird nur, was
  du anhakst. Die App selbst schickt nichts ins Netz.
- Depots haben im Monatsabschluss ein Feld **davon Gewinn** (wie in der
  Depot-App). Die Hochrechnung versteuert damit auch den Gewinn, der heute
  schon im Depot steckt; ohne Angabe gilt der Wert als Einstand.
- Die Gehalts-Untergrenze steht nur noch unter **Annahmen**, nicht mehr
  zusätzlich auf **Planung**.
- Die Entnahmerate ist aus den Annahmen verschwunden: Gerechnet wurde mit ihr
  nirgends. Die Rentenlücke rechnet mit Lebenserwartung, Rendite und
  „Vermögen aufbrauchen“.

## 0.2.1 – 2026-09-27

- Eine Sicherung lässt sich in der App wiederherstellen: Einrichtung → **Aus
  einer Sicherung wiederherstellen**. Aus dem Sicherungsordner oder als
  hochgeladene Datei, etwa auf einem neuen Rechner. Die Sicherung landet in
  einem neuen Ordner neben dem bisherigen; umgeschaltet wird erst mit
  **Diesen Stand verwenden**, und der alte Ordner bleibt unverändert.
- Beim ersten Öffnen – solange es kein Konto gibt – startet die App in der
  Einrichtung statt im Monatsabschluss.

## 0.2.0 – 2026-09-27

- Die App gibt es zum Doppelklicken: `.dmg` für den Mac (Apple-Chip), `.exe`
  für Windows. Sie richtet sich beim ersten Start selbst ein und lässt sich
  über **Beenden** oben rechts schließen.
- Die Versionsnummer steht unten auf jeder Seite.
- Neue Akzentfarbe: Petrol statt Blau.
- Lizenz: PolyForm Strict 1.0.0 – privat und nicht-kommerziell nutzbar. Die
  Lizenzen der mitgelieferten Bibliotheken liegen als `DRITTLIZENZEN.txt` bei.
- Hinweis in der Einrichtung: Die App rechnet, sie berät nicht.

## 0.1.0 – 2026-09-27

Die erste Version, die auf einem anderen Rechner laufen kann.

- Konten, Auszüge einlesen (PDF-Profile einiger Banken, CSV jeder Bank über die
  Spaltenzuordnung), Kategorien und Regeln, Rückblick.
- Module zum Zuschalten: Verträge, Energie, Geteiltes, Kredite, Immobilien,
  Steuer, Prognose, Ziele.
- Hochrechnung bis zur Lebenserwartung mit Renten und festem Ziel Rentenlücke.
- Die Daten liegen im Datenordner des Systems, getrennt vom Programm.
