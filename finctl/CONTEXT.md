# Finance OS

Ein Haushalt sieht, wohin sein Geld ging, ob die Konten reichen und wo er in
Jahren steht. Die App kennt nur die Begriffe unten. Welche Bank, welcher
Vertrag, welcher Mensch dahintersteht und warum, sind Einträge und Notizen des
Haushalts, kein Text der App.

## Haushalt

**Haushalt**:
Die Einheit, für die gerechnet wird: alle Konten, Verträge und Pläne einer Einrichtung.
_Avoid_: Nutzer, Eigentümer

**Planende Person**:
Die Person, aus deren Geburtsjahr, Krankenversicherung und Rentenbeginn jede Altersschwelle ein Datum wird.
_Avoid_: Besitzer, Owner

**Beteiligter**:
Ein Mensch außerhalb des Haushalts, der Kosten mitträgt oder dem ein Teil eines Bestands gehört.
_Avoid_: Person (allein), Partner, Name

**Notiz**:
Ein datierter Freitext an einem Eintrag, der sagt, warum er so ist; sie trägt alles Persönliche und zeigt ihr Alter.
_Avoid_: Begründung, Kommentar, Herleitung

## Konten und Belege

**Konto**:
Ein Ort, an dem Geld des Haushalts liegt und der eine Kontoart und eine Rolle hat.
_Avoid_: Account, Position (für Konten)

**Kontoart**:
Was ein Konto technisch ist: Giro, Tagesgeld, Depot, Verrechnungskonto, Kredit, Karte.
_Avoid_: Typ, Kind

**Rolle**:
Wozu der Haushalt ein Konto benutzt, zum Beispiel Betriebskonto, Puffer, Ratenkonto oder Budgetkonto; Planung und Prognose kennen nur Rollen, nie einzelne Banken.
_Avoid_: Zweck, Funktion

**Betriebskonto**:
Das Konto mit der Rolle, über die Gehalt und Fixkosten laufen und von dem neue Raten abgehen.
_Avoid_: Hauptkonto, Girokonto (als Rolle)

**Auszug**:
Ein Beleg der Bank über einen Zeitraum, mit Anfangs- und Endstand und den Buchungen dazwischen.
_Avoid_: Statement, Export, Datei

**Buchung**:
Eine Geldbewegung auf einem Konto, so wie der Auszug sie nennt; sie wird nie verändert.
_Avoid_: Transaktion, Zahlung, Umsatz

**Teil**:
Ein Stück einer Buchung mit eigener Kategorie; jede Buchung besteht aus einem oder mehreren Teilen, die zusammen ihren Betrag ergeben.
_Avoid_: Split, Aufteilung

**Saldo**:
Einnahmen minus Ausgaben eines Zeitraums, etwa eines Monats oder Jahres; anders als ein Stand sagt er nicht, was da ist, sondern was hinzukam oder fehlte. Bei einer Themenkasse: was ein Beteiligter beigetragen hat minus seinem Anteil.
_Avoid_: Überschuss, Cashflow

**Gegenpartei**:
Wer auf der anderen Seite einer Buchung steht.
_Avoid_: Empfänger, Partner, Counterparty

**Umbuchung**:
Eine Buchung zwischen zwei Konten desselben Haushalts; sie ist weder Einnahme noch Ausgabe.
_Avoid_: Transfer, Übertrag

**Durchlaufendes Konto**:
Ein Konto, das Geld im selben Moment weiterreicht; es hat keine eigene Prognose. Seine Buchungen zählen auf dem Konto, das es deckt (das Gegenkonto seiner letzten Umbuchung), und die Umbuchung, die es ausgleicht, zählt nicht noch einmal.

## Stände

**Stand**:
Was zu einem Datum auf einem Konto oder in einer Position liegt.
_Avoid_: Saldo, Kontostand (allgemein), Wert

**Belegter Stand**:
Ein Stand, den ein Auszug beweist; wo es Auszüge gibt, gilt nur er.
_Avoid_: echter Stand

**Getippter Stand**:
Ein Stand, den der Haushalt mit Datum einträgt, weil kein Auszug ihn kennt.
_Avoid_: Livestand, Snapshot, manueller Wert

**Verlauf**:
Die Stände, die der Haushalt je Position am Monatsabschluss getippt hat und die stehen bleiben, damit sich ein Monat mit dem davor vergleichen lässt; ein Beleg, kein Wert, der gilt.
_Avoid_: Historie, Snapshot

**Position**:
Ein Vermögenswert ohne Auszug, etwa ein Depot, Krypto oder eine Police, geführt über getippte Stände.
_Avoid_: Bestand, Holding

**Bestandsart**:
Unter welcher Art eine Position oder ein Konto zum Vermögen zählt: Giro, Tagesgeld, Depot, Rentenversicherung.

**Anlageklasse**:
Eine Zusammenfassung von Bestandsarten mit eigener Rendite und Besteuerung, wie die Hochrechnung sie fortschreibt: Liquidität, Depot, Policen.
_Avoid_: Vermögenstopf, Topf

**Verpflichtung**:
Der Teil eines Bestands, der einem Beteiligten gehört; er wird abgezogen, nie mitgezählt.
_Avoid_: Schuld, Obligation

**Stichtag**:
Das letzte Monatsende, das die Auszüge aller Konten vollständig abdecken; ab hier rechnet die Prognose.

## Zuordnen

**Kategorie**:
Was für eine Einnahme oder Ausgabe ein Teil ist, aus einem Baum mit Oberkategorien.
_Avoid_: Management-Kategorie, Konto (im Sinn der Buchhaltung)

**Fixkosten**:
Ein Merkmal einer Kategorie: Ihre Kosten sind vertraglich festgelegt, unabhängig davon, in welchem Ast sie stehen.

**Steuerposition**:
Wohin ein Teil in der Steuererklärung gehört; eine zweite, von der Kategorie unabhängige Zuordnung.
_Avoid_: Steuerkategorie

**Regel**:
Eine Vorschrift, die Buchungen nach Merkmalen eine Kategorie und Steuerposition gibt.

**Grundschicht**:
Die mitgelieferten Regeln für allgemeine Händler und Buchungsarten, mit denen ein neuer Haushalt anfängt.

**Handentscheidung**:
Was der Haushalt selbst festlegt und keine Regel überschreibt: die Kategorie einer Buchung oder den Takt einer Reihe.
_Avoid_: Override, manuelle Korrektur

**Vorschlag**:
Was ein Modell dem Haushalt vorlegt und noch nichts ändert; erst wenn der Haushalt es in der App übernimmt, wird daraus eine Handentscheidung wie jede andere.
_Avoid_: Änderung (vor der Zusage), Auftrag

**Teilung**:
Wie eine Buchung einer Themenkasse auf ihre Beteiligten verteilt wird: wer welchen Anteil trägt.
_Avoid_: Aufteilung (das sind die Teile einer Buchung)

**Reihe**:
Alle Buchungen derselben Gegenpartei in derselben Kategorie über die Zeit; gemeint ist sie, wenn eine Handentscheidung auf eine einzelne Buchung zeigt. Eine Reihe hat einen Takt. Steht dieselbe Zahlung unter mehreren Schreibweisen der Gegenpartei, führt der Haushalt sie für die Vorschauen zu einer Reihe zusammen, die nach der einen heißt.

**Vorgang**:
Wozu Ausgaben gehörten, über Kategorien hinweg und mit Zeitfenster, etwa ein Auto von Kauf bis Verkauf.
_Avoid_: Gruppe, Projekt

**Themenkasse**:
Von Hand gesammelte Ausgaben zu einem Thema, etwa einer gemeinsamen Reise, meist mit Beteiligten geteilt und abgerechnet, wer wem was schuldet. Anders als ein Vorgang wird sie nicht von Regeln gefüllt, sondern Teil für Teil zugeordnet.
_Avoid_: Budgettopf, Projekt, Topf, Geteilt, Budget

## Verträge und Dinge

**Vertrag**:
Eine Verpflichtung mit Gegenpartei, Betrag, Takt und Laufzeit, etwa ein Abo oder eine Versicherung. Monatsmodell und Jahresrechnung zählen ihn über diese Angaben, nicht über seine Buchungen: Betrag mit Steigerung je Termin, nichts vor dem Ende eines Vorrats (bezahlt bis zu einem Datum), nichts nach der Kündigung oder in den Monaten einer Wegfall-Zeile auf seiner Reihe, dazu der Anteil der Mitzahler. Seine Buchungen misst keines der beiden. Der Beitrag in eine Police bleibt gemessen und nominal fest.
_Avoid_: Abo (als Oberbegriff), Mitgliedschaft

**Mitzahler**:
Ein Beteiligter, der einen Teil eines Vertrags trägt und dem Haushalt seinen Anteil zahlt. Wo der Haushalt einen Zeitraum angelegt hat, zählt der offene Anteil im Monat des Einsammelns; wo es keinen gibt, der Anteil laut Besetzung je Termin, nur für Personen, die schon in einem Zeitraum standen oder mit „seit“ laufend zahlen. Der Anteil steigt wie der Betrag des Vertrags und kommt im Monatsmodell auf dem Konto an, auf dem der Mitzahler zuletzt gezahlt hat. Seine Zahlungen misst keine Rechnung.
_Avoid_: Teilnehmer, Untermieter

**Takt**:
Wie oft eine Reihe, ein Vertrag oder eine Planzeile zahlt: monatlich, alle zwei, drei, vier oder sechs Monate, jährlich, einmalig oder unregelmäßig. Bei einer Reihe erkennt die App ihn aus den Buchungen der letzten zwei Jahre, oder der Haushalt legt ihn fest. Eine Reihe mit festem Takt wird mit ihrem Betrag je Termin fortgeschrieben, solange sie läuft; eine unregelmäßige geht in der Summe ihrer Kategorie auf.
_Avoid_: Frequenz, Rhythmus, Periodizität

**Einmalig**:
Ein Takt für Buchungen, die geschehen sind und nicht wiederkommen; sie fallen aus jeder Fortschreibung. Er gilt für die Buchungen, die der Haushalt so markiert, und für jede Buchung einer Kategorie mit diesem Merkmal, nicht für die ganze Reihe: Derselbe Händler kommt in derselben Kategorie wieder.
_Avoid_: Sondereffekt, Ausreißer

**Kredit**:
Geliehenes Geld mit Tilgungsplan, das an einem Ratenkonto hängt und einem Objekt dienen kann.
_Avoid_: Darlehen, Loan

**Zinsbindung**:
Ein Abschnitt eines Kredits mit festem Zins; an ihrem Ende steht eine Anschlussfinanzierung.

**Objekt**:
Eine Immobilie des Haushalts, der Buchungen, Kredite und eine Objektprognose zugeordnet werden.
_Avoid_: Immobilie (als Eintrag), Property, Wohnung

**Objektprognose**:
Was ein Objekt künftig an Miete abwirft und an Kosten verursacht, angenommen statt gemessen, mit Zeitraum und Saison; sie gehört dem Objekt und ist kein Schalter in der Planung. Wo ein Objekt eine hat, zählen seine gemessenen Buchungen in keiner Rechnung mehr: Beide nehmen die Prognose, das Monatsmodell bucht sie auf dem Konto, auf dem die Miete landet.
_Avoid_: Ertragsprognose, Mietprognose

**Rentenquelle**:
Etwas, das im Ruhestand regelmäßig zahlt, zum Beispiel die gesetzliche Rente oder eine Police, mit Betrag und dem Schreiben, aus dem er stammt.
_Avoid_: Rente (allein), Altersvorsorge

**Zähler**:
Ein Messgerät mit Ablesungen und Abschlag, das ein Versorger abrechnet: Strom, Gas, Wärme, Wasser.

**Vorrat**:
Ein Brennstoff, der auf einmal geliefert und über die Zeit verbraucht wird, etwa Heizöl oder Pellets.
_Avoid_: Tank, Lager

**Mindestbestand**:
Die Menge eines Vorrats, bis zu der er verbraucht werden darf; bis dorthin rechnet die App, wie lange er reicht.
_Avoid_: Untergrenze (die gilt für Konten), Reserve

**Frist**:
Ein Datum, an dem der Haushalt handeln muss, mit einem Vorlauf, ab dem es bald fällig ist.
_Avoid_: Termin, Deadline

## Blick nach vorn

**Annahme**:
Wie die Welt sich entwickelt: Inflation, Rendite, Gehaltssteigerung, Lebenserwartung.
_Avoid_: Parameter, Einstellung

**Kontenregel**:
Wie der Haushalt Geld zwischen eigenen Konten bewegt: Untergrenze, Deckel, Abräumen, Auffüllen.
_Avoid_: Allokation, Annahme

**Untergrenze**:
Der Stand, unter den ein Konto nicht fallen soll; darunter wird gewarnt oder aufgefüllt.
_Avoid_: Floor, Mindestbestand

**Deckel**:
Der Stand, über dem Geld auf einem Konto nur herumliegt und abgeräumt wird.
_Avoid_: Ceiling, Obergrenze

**Kontoprognose**:
Die Vorschau je Konto und Monat bis auf den Tiefpunkt, für die Frage, ob das Geld reicht; die Seite Konten zeigt sie, das Monatsmodell rechnet sie.
_Avoid_: Liquiditätsprognose, Forecast

**Monatsmodell**:
Die Rechnung je Konto und Monat, 60 Monate weit, mit den eingeschalteten Klammern und den Kontenregeln; sie beantwortet, ob ein Konto ins Minus rutscht. Ein Ziel, dessen Stichdatum in diese 60 Monate fällt, misst ebenfalls sie.
_Avoid_: Liquiditätsmodell

**Jahresrechnung**:
Die Rechnung je Jahr für den ganzen Haushalt, bis zur Lebenserwartung, mit Rendite, Ruhestand und der Kaskade: Das Tagesgeld füllt sich bis zu seinem Ziel, der Rest geht ins Depot. Sie beantwortet, wie das Vermögen wächst, und misst die Ziele mit späterem Stichdatum. Monatsmodell und Jahresrechnung nehmen dieselben Eingaben; verschieden bleibt nur, was die Jahresrechnung allein kennt (Kaskade, Rendite, Ruhestand, Teilzeit, Verkauf), und die Kontenregeln, die nur das Monatsmodell kennt.
_Avoid_: Jahresmodell

**Tiefpunkt**:
Der niedrigste Stand eines Kontos innerhalb eines Monats, nicht der Stand am Monatsende.
_Avoid_: Senke, Trough

**Hochrechnung**:
Die Vorschau in Jahren bis zum Lebensende, für die Frage, wo das Vermögen steht und ob es reicht; die Seite Hochrechnung zeigt sie, die Jahresrechnung rechnet sie.
_Avoid_: Tragfähigkeitsrechnung, Projektion

**Fortschreibung**:
Was Monatsmodell und Jahresrechnung aus der Vergangenheit in die Zukunft übernehmen, je Kategorie und Takt.
_Avoid_: Basis, Baseline, Prognosebasis

**Block**:
Eine Gruppe von Kategorien, die beide Rechnungen gleich behandeln, etwa Gehalt, Fixkosten, Konsum, Verträge, Objekte oder Zinsen und Steuer.
_Avoid_: Gruppe, Topf

**Quelle**:
Woher eine Rechnung den Betrag eines Blocks nimmt: aus dem Messfenster, aus einem Vertrag, einer erwarteten Einnahme, der Objektprognose, aus Stand und Satz oder aus einer Planzeile.
_Avoid_: Herkunft, Basis

**Messfenster**:
Die zwölf letzten vollständigen Monate, aus denen beide Rechnungen ablesen, was fortzuschreiben ist. Was keine Reihe mit Takt, kein Vertrag und keine Planzeile erklärt, geht als ihre Summe, die Zwölfmonatssumme, in die Prognose ein: im Monatsmodell durch zwölf geteilt und auf dem Konto gebucht, auf dem gemessen wurde. Was eine Handentscheidung erklärt, steht nicht noch einmal im Messfenster.
_Avoid_: Basisfenster, Referenzzeitraum

**Verfahren**:
Wie eine Fortschreibung aus vergangenen Monaten einen Monatsbetrag macht: die Zwölfmonatssumme des Messfensters, im Monatsmodell durch zwölf geteilt, oder Jüngst; der Haushalt wählt das Tempo, und die Vorschau sagt, welches gilt.
_Avoid_: Methode, Modus, Basis

**Jüngst**:
Ein Verfahren, das nur die letzten drei vollständigen Monate gleich gewichtet zählt, damit geändertes Verhalten sofort in der Vorschau ankommt; es gilt nur für Kosten im Konsum, und dort nur für Reihen ohne festen Takt.
_Avoid_: Recency, Trend

**Rechenweg**:
Die Posten, aus denen eine angezeigte Zahl besteht, jeder mit Kategorie, Fenster, Verfahren und Faktor; ihre Summe ist die Zahl.
_Avoid_: Herkunft, Herleitung, Erklärung

**Wirkung**:
Wie weit sich eine Zahl der Hochrechnung, etwa der erwartete Stand eines Ziels an seinem Stichdatum, gegenüber dem Stichtag davor bewegt hat, aufgeteilt nach Ursache: der Monat selbst (was er anders brachte als erwartet), das Tempo je Block, die Planzeilen. Annahmen und Ziele gelten dabei für beide Stichtage so, wie sie heute stehen; die Wirkung zeigt, was die Buchungen bewegt haben, nicht was der Haushalt umgestellt hat. Ein Ziel, das das Monatsmodell misst, wird nicht zerlegt: Die Wirkung sagt das und verweist auf Konten.
_Avoid_: Delta, Effekt, Veränderung

**Kursbewegung**:
Was ein Depot im Monat gewonnen oder verloren hat, getrennt von dem, was eingezahlt oder entnommen wurde: die Änderung des getippten Stands ohne das, was über Buchungen unter `investment/` hinein- oder herausging; ein Hinweis zum Monat, kein Teil der Wirkung.
_Avoid_: Performance, Rendite (die ist eine Annahme)

**Planzeile**:
Ein künftiger Posten, den der Haushalt selbst einträgt: ein Betrag, ein Wegfall, eine erwartete Einnahme, ein Verkauf oder eine Teilzeit.
_Avoid_: Szenariozeile, geplanter Posten

**Wegfall**:
Eine Planzeile, die eine Reihe ab einem Datum aus der Fortschreibung nimmt.
_Avoid_: Kündigung (in der Planung), discontinued

**Erwartete Einnahme**:
Eine Planzeile für eine Einnahme, die der Haushalt erwartet, ohne dass ihre Buchungen ein Muster ergeben: eine Schenkung, eine Nebentätigkeit. Sie hat Betrag, Takt (monatlich, quartalsweise, jährlich oder einmalig), Start, optional Ende, Kategorie und Konto. Die Buchungen, die der Haushalt ihr zuordnet, und ihre Reihe zählt keine Messung mehr; die Zeile zählt voll, mit festem Betrag und ohne Steigerung. Beide Rechnungen zählen sie als Einnahme ihrer Kategorie, das Monatsmodell auf ihrem Konto. Sie gehört nicht zum Gehalt. Schaltet der Haushalt die Klammer aus, kehrt die Messung zurück.
_Avoid_: Prognose-Einnahme, geplante Einnahme

**Klammer**:
Eine benannte Gruppe von Planzeilen, die sich als Ganzes ein- und ausschalten lässt; mehrere Klammern gelten zugleich.
_Avoid_: Szenario, Plan, Variante

**Ziel**:
Ein Betrag zu einem Stichdatum, gemessen an dem, was heute an Vermögen da ist. Wo es am Stichdatum steht, misst das Monatsmodell, wenn das Datum in seinen 60 Monaten liegt und die ganze Basis dort vorkommt, sonst die Jahresrechnung.
_Avoid_: Sparziel, Target

**Notgroschen**:
Das Geld, das für den Notfall unangetastet bleiben soll, ein Ziel mit einer Grenze. Im Monatsmodell ist sie die Untergrenze des Tagesgeldkontos: Greift eine Klammer ihn an, warnt Konten. Die Kaskade der Jahresrechnung füllt ihn zuerst.
_Avoid_: Reserve, Rücklage

**Rentenlücke**:
Das Kapital, das zum Rentenbeginn dastehen muss, damit Ausgaben minus Rentenquellen bis zur Lebenserwartung gedeckt sind.

**Schwelle**:
Ein Alter, ab dem sich etwas ändert, etwa Rentenbeginn oder Teilzeit, das über die planende Person zu einem Datum wird.

## Betrieb

**Monatsabschluss**:
Was am Monatsanfang zu tun ist: Auszüge einlesen, getippte Stände erneuern, offene Zuordnungen klären, bald fällige Fristen sehen.

**Basis**:
Was jeder Haushalt hat und nicht abschalten kann: Konten, Einlesen, Zuordnen, Rückblick, Sicherung.

**Modul**:
Ein Teil, den ein Haushalt zuschaltet, wenn er ihn braucht, etwa Verträge, Energie, Themenkassen, Kredite, Objekte, Steuer, Prognose oder Ziele.
_Avoid_: Feature, Plugin

**Sicherung**:
Ein Archiv des Datenordners, aus dem sich der Haushalt ohne den Code wiederherstellen lässt.
_Avoid_: Backup, Export
