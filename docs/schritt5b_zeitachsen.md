# Schritt 5b: Ein Haushalt, zwei Zeitachsen

Arbeitsplan für die Umsetzung, geschrieben für ein Modell, das ihn Teil für
Teil abarbeitet (Claude Sonnet). Gesamtplan: `docs/Neufassung_plan.md`, dort
als Schritt 5b. Kommt **nach dem Umstieg** (Schritt 5,
`docs/schritt5_notizen.md`) und vor Schritt 6. Er baut auf Schritt 2 auf
(`docs/schritt2_fortschreibung.md`): Dort bekam jede Vorschau ihre Eingaben
als Wert, und die Unterschiede blieben mit Absicht stehen. Hier werden sie
angeglichen.

## Ziel in einem Satz

Monatsmodell und Jahresrechnung bekommen ihre Eingaben aus einer Quelle. Der
einzige bleibende Unterschied ist die Kaskade der Jahresrechnung, und ein
Test hält das fest.

## Befund (Diagnose vom 08.10.2026)

Die Rechnung mit den Beträgen steht in `notizen/diagnose_konten_vs_jahre.md`
der Entwicklungskopie. Hier steht nur, was sie für den Plan heißt.

- **Zwei Modelle:**
  - Das **Monatsmodell** (`forecast/konten.py`, `household_accounts`, Seite
    `/konten`) rechnet je Konto und Monat. Es fragt, ob ein Konto ins Minus
    rutscht.
  - Die **Jahresrechnung** (`forecast/jahre.py`, `eingaben_je_tempo` und
    `rechnen`, Seiten `/hochrechnung` und „hochgerechnet“ auf `/ziele`)
    rechnet je Jahr für den Haushalt. Sie fragt, wie das Vermögen wächst.
- **Gleicher Ausgangspunkt:** Beide beginnen beim selben Bestand und kennen
  dieselben Kreditraten, Policenbeiträge und aktiven Klammern.
- **Die Rechnung ist nicht verschieden.** Eine Bilanzprobe geht auf den Cent
  auf. Verschieden sind die **Eingaben**:

| # | Eingabe | Monatsmodell | Jahresrechnung |
|---|---|---|---|
| 1 | Objektprognose (Miete, Kosten) | fehlt; nur gemessene Buchungen des Objekts | aus `properties.yaml`, `prognose` |
| 2 | Gehalt | Untergrenze, flach | Median, mit der Gehaltssteigerung |
| 3 | Nebentätigkeit | aus der letzten Zahlung eine Jahresreihe | fehlt |
| 4 | Schenkungen | fehlen | als laufende Einnahme fortgeschrieben |
| 5 | Zinsen | gemessen, dazu feste Korrekturzeilen in Planung | aus dem Kontostand und dem Zinssatz |
| 6 | Fenster und Verfahren | sechs Monate, Median je Konto mit Mindestzahl | zwölf Monate, Summe je Kategorie |

Daraus spart das Monatsmodell 2027 deutlich weniger. Der größte Posten ist 1,
dann 2, 6 und 4.

- **Ein zweiter Befund auf `/ziele`:**
  - Balken und Rate messen nur den heutigen Bestand.
  - „Hochgerechnet“ kennt nur Jahresenden, die linear verbunden werden.
  - Die Kaskade füllt den Notgroschen zuerst auf.

  Eine Klammer wie ein Autokauf bewegt deshalb die Karte eines kurzfristigen
  Ziels nicht, obwohl `/konten` sie sieht.

## Entscheidungen (mit dem Haushalt abgestimmt)

1. **Objektprognose** (08.10.2026):
   - Sie bleibt beim Objekt unter Immobilien. Sie ist eine Eigenschaft des
     Objekts und kein Schalter in Planung.
   - Das Monatsmodell liest sie von dort. Es bucht sie je Monat auf das Konto,
     auf dem die Miete landet.
   - Die gemessenen Buchungen des Objekts zählen dann nicht mehr. Die
     Jahresrechnung hält es schon so.
   - Eine zweite Eingabe in Planung zählte das Objekt in der Jahresrechnung
     doppelt.
2. **Gehalt** (08.10.2026):
   - Beide Modelle rechnen mit der Untergrenze (`salary_floor_cents`), nicht
     mit dem Median. „Zu vorsichtig“ ist gewollt.
   - Die Untergrenze wächst in beiden mit `gehalt_steigerung_pa` aus den
     Annahmen.
   - Der Median bleibt höchstens als Vergleichszahl.
   - Teilzeit und Ruhestand rechnen auf dieser Basis weiter wie heute.
3. **Schenkung und Nebentätigkeit** (08.10.2026):
   - Beide stehen in Planung, als erwartete Einnahme mit Betrag und Monat.
   - Die bisherigen Buchungen werden der Zeile zugeordnet. So ersetzt die
     Zeile die Messung, statt neben ihr zu stehen.
   - Beide Modelle messen sie danach nicht mehr.
4. **Zinsen** (09.10.2026): Beide Modelle rechnen sie aus dem Kontostand.
   - Das Monatsmodell rechnet Monat für Monat aus dem vorausgerechneten Stand
     des Kontos und dem Satz aus den Zinssätzen (`forecast/zinsen.py`).
   - Die Steuer folgt derselben Regel wie in der Jahresrechnung: erst der
     Freibetrag, dann der Satz.
   - Gemessene Zinsen zählen nicht mehr.
   - Die festen Korrekturzeilen in Planung werden überflüssig. Die Sitzung
     nennt sie, der Haushalt löscht sie.
   - Folge: Leert eine Klammer das Konto, sinkt der Zins von selbst.
5. **Messfenster** (09.10.2026): zwölf Monate in beiden Modellen.
   - Zwölf Monate sehen jede Jahresprämie und glätten einzelne große
     Buchungen.
   - Sechs Monate galten, damit ein beendetes Muster schnell herausfällt. Das
     leisten inzwischen Wegfall-Zeilen, `enden` und Reihen mit Vertragsende.
6. **Verfahren** (Vorschlag Opus, 09.10.2026; vom Haushalt bestätigt am
   25.10.2026): Für alles, was nicht als Reihe mit Takt oder als Planzeile
   steht, ist die Monatsrate in beiden Modellen die Zwölfmonatssumme durch
   zwölf.
   - Das Monatsmodell bucht sie je Monat auf das Konto, auf dem gemessen
     wurde.
   - Der Median mit Mindestzahl entfällt. Er lässt seltene Ausgaben
     (Arzt, Reparatur) ganz weg und ist darum für Ausgaben zu optimistisch.
   - Der Schnitt summiert sich über die Konten genau zur Summe des
     Haushalts. Nur so kann ein Test beide Modelle Posten für Posten
     vergleichen.
   - Folge, mit dem Haushalt besprochen: `/konten` wird pessimistischer,
     weil seltene Ausgaben mitzählen, und warnt bei einem knapp geführten
     Girokonto öfter. Das ist gewollt. Einzelne Ausreißer nimmt der Haushalt
     als „einmalig“ oder als Planzeile heraus.
7. **Kurzfristige Ziele:**
   - Ein Ziel, dessen Stichtag im Horizont von `/konten` liegt, misst
     „hochgerechnet“ mit dem Monatsmodell. Das ist der Stand seiner
     Basiskonten zum Stichtag, mit den aktiven Klammern.
   - Ein Ziel mit späterem Stichtag misst weiter mit der Jahresrechnung.
   - Balken und Rate bleiben beim heutigen Bestand.
8. **Notgroschen:**
   - Die Grenze des Notgroschens (`puffer_grenze`) wird Untergrenze seines
     Kontos im Monatsmodell. `/konten` warnt dann, wenn eine Klammer den
     Notgroschen angreift.
   - Die Kaskade der Jahresrechnung bleibt, wie sie ist.

## Was „gleich“ und was „gewollt“ heißt

5b ist **gewollt**: Zahlen ändern sich mit Absicht. Damit jede Änderung einen
Grund hat, gilt:
- Jeder Teilschritt ändert **eine** Eingabe, in beiden Modellen zugleich.
- Vorher misst `pruefen --nur-zahlen` gegen die Referenz. Jede geänderte Zahl
  muss sich aus dieser einen Eingabe erklären. Der Bericht nennt die Seiten
  und je Seite die Größenordnung.
- Der **Paritätstest** (E.1) führt eine Liste der bekannten Unterschiede je
  Jahr und Block. Sie darf nur kürzer werden, wie `ZU_VERZWEIGT` in
  `tests/test_lint.py`. Jeder Teilschritt streicht seinen Block.
- Opus schreibt die Referenz nach jedem Teilschritt neu, in einem eigenen
  Schritt.
- Geprüft wird an der Entwicklungskopie. Vor E.0 zieht Opus sie aus dem
  umgestellten echten Datenordner neu, damit sie den Stand nach dem Umstieg
  hat.
- Die echten Beträge stehen nur in `notizen/`.
- Werte, die der Haushalt eintragen muss (Zeilen für Schenkung und
  Nebentätigkeit), trägt in der Entwicklungskopie Opus ein, nach seiner
  Angabe. Im echten Ordner trägt der Haushalt sie über die Seite ein.

## Die Teilschritte

### E.0 Bestandsaufnahme (nur lesen)

- Jede Eingabe beider Modelle, mit Datei, Funktion und wer sie liest:
  - Fenster und Verfahren, Gehalt, Objekte, Planzeilen, Zinsen, Wegfall-Zeilen;
  - `nicht_fortschreiben` (`forecast/prognosebasis.py`);
  - Einmaliges und Verträge.
  Was Schritt 2 schon teilt (`fortschreibung.Vorschau`), steht getrennt von
  dem, was jedes Modell selbst misst. Schritt 2 nannte als offen: Gehalt,
  `szenarien.messung`, `jahre._vertragsenden` und `jahre.verkaeufe`.
- Welche Mechanismen es schon gibt, bevor etwas Neues gebaut wird:
  - Planzeilen mit zugeordneten Buchungen (`szenarien.messung`,
    `einmalig_zugeordnet`).
  - Die Abgrenzung des Objekts (`forecast/ohne_objekt.py`).
  - Die Zinsmischung (`forecast/zinsen.py`).
  - Die Steuer auf Erträge (`jahre._steuer_auf`).
- Auf welches Konto die Miete eines Objekts mit Prognose landet: Steht es am
  Objekt, an seinem Kredit oder nirgends?
- Der Anfangsstand eines Kontos ohne Auszug. Das Monatsmodell nimmt ihn aus
  `balance_snapshots` (`source='manual'`). Die Zeilen schreibt `finctl init`
  aus `balances.yaml`, und zwar nur Positionen mit dem Datum der Datei oder
  ohne eigenes (Schritt 5, Abnahme N.3d). Ein Stand, den die Seite später
  einträgt, kommt dort nicht an. Woher nimmt das Jahresmodell denselben
  Stand? Ob jede Position unter ihrem eigenen Datum in die Tabelle gehört,
  entscheidet dieser Schritt.
- Die Blöcke für den Paritätstest. Welche Größe des Monatsmodells, über alle
  Konten summiert, entspricht welchem Block der Jahresrechnung vor der
  Kaskade? Umbuchungen zwischen eigenen Konten heben sich auf.
- Welche Seiten Zahlen zeigen, die sich in E.2 bis E.7 ändern werden, je
  Teilschritt.
- Ergebnis als Abschnitt in diesem Plan, mit Abweichungen unter „Gefundene
  Abweichungen“. Die echten Beträge kommen nach
  `notizen/E.0_bestand.md`.

#### E.0 Ergebnis (Sonnet, 25.10.2026)

Gemessen an der Entwicklungskopie (Stand nach dem Umstieg, Stichtag 30.09.2026,
Haushaltsfenster 10/2025–09/2026) mit Skripten, die die Funktionen aufrufen
(`household_accounts(months=15)` gegen `jahre.eingaben_je_tempo` und `rechnen`, wie die
Route `/ziele`). Nichts geändert. Die Beträge stehen in `notizen/E.0_bestand.md` der
Entwicklungskopie; hier stehen Befunde, Verhältnisse und Dateien.

**1. Jede Eingabe beider Modelle**

| # | Eingabe | Monatsmodell | Jahresrechnung | Geteilt? |
|---|---|---|---|---|
| 1 | Messung der Teile | `messung.py`, `monatssummen`, `teile` | dieselben | ja, über `fortschreibung.messen` |
| 2 | Fenster | `konten.kontoprognose`: `window_months` aus `forecast.yaml`, Ende am Tag vor dem ersten offenen Monat. Divisor je Konto: `fortschreibung._fenstermonate` (ab erstem Auszug des Kontos) | `jahre._hochrechnung` ← `abgleich.fenster(conn, 12)`: die Zwölf ist nur ein Vorgabewert im Code; Divisor `f.monate` für alle Konten | nein |
| 3 | Verfahren | `verfahren.kontoprognose_regeln`: Kosten Schnitt (oder Median, `variable_kosten`), Einnahmen Median ab `min_occurrences` | `verfahren.HOCHRECHNUNG`: Summe aufs Jahr; `HOCHRECHNUNG_JUENGST` für den Konsum im zweiten Tempo | Funktionen ja (`verfahren.wahl`), Tabelle nein |
| 4 | Umbuchungen, Teile ohne Kategorie | `Ausschluss(umbuchung="art", ohne_kategorie=False)` | `Ausschluss()`: Präfix `transfer/`, Teile ohne Kategorie zählen unter `''` | Typ ja, Wert nein |
| 5 | Reihen mit festem Takt | `konten.reihen_vor` (Stichtag, ohne die Buchungen eines Wegfalls) | `jahre._reihen_laden` (Ende des Fensters) | Quelle ja (`reihen.laden`, `takt.Reihen`), je Modell eine Instanz |
| 6 | Einmaliges | Merkmal der Kategorie (`abgleich.einmalige_kategorien`) in `exclude`; gesetzte Buchungen `reihen.einmalige_hashes()` | Merkmal als Block `einmalig`; dieselben gesetzten Buchungen; dazu `szenarien.einmalig_zugeordnet` (`jahre._eingaben`) | halb: `einmalig_zugeordnet` kennt nur die Jahresrechnung |
| 7 | Abwahl (`nicht_fortschreiben`, `prognosebasis.py`) | die Kategorie fällt ganz heraus (`kontoprognose(abwahl=True)`, `ausser`) | nur in den Blöcken `FROM_BASE` (`jahre._basis`) | Datei ja, Wirkung nein |
| 8 | Kredite | Kinder von `kredit` aus der Messung; Raten je Konto aus dem Tilgungsplan (`konten.account_forecast`) | Block `kredit` aus `jahre._tilgungsplaene`; ein Verkauf beendet den Kredit | Quelle ja (`realestate.loan`) |
| 9 | Verträge | `abos.ausschluesse` nimmt die Reihe aus der Messung, `abos.posten` bucht Betrag und Termin (nominal), `abos.rueckzahlungen` | die Reihe bleibt in der Basis; `jahre._vertragsenden` zieht eine Kündigung ab, `_beitragsausgaben` und `_beitragsposten` halten Policenbeiträge nominal | Quelle ja, Rechnung nein |
| 10 | Gehalt | `konten._income_overrides`: `assumptions.salary_floor_cents`, flach, keine Steigerung (`engine.project`: ein Override ist eine gesetzte Zahl) | `jahre.gehalt_median_cents` (24 Gehaltsmonate, genau `einkommen/gehalt`), `_salary`, `_gehaltsposten`; Steigerung `gehalt_steigerung_pa`, wachsend zum 1. Januar; Teilzeit `_teilzeitposten` | nein |
| 11 | Objekte mit Prognose | keine; ihre Buchungen laufen gemessen in `miete` und `immobilie` | `objekte.prognosen` → `jahre._objektposten`, Block `objekt`; die Buchungen des Objekts sind dafür aus der Basis genommen (`abgleich._objekt_block`) | nein |
| 12 | Planzeilen | `konten._planposten` (Rest je Termin, `szenarien.restbetrag_je_termin`), `konten.wegfall_posten` (rechnet die eigenen Posten mit und ohne die Reihe) | `jahre._planposten` (`szenarien.jahreswirkung`); Wegfall mit der Messung der Zeile | Messung ja (`szenarien.messung`), Rechnung nein |
| 13 | Zinsen | gemessene Kategorie `einkommen/zinsen` und `steuern/kapitalertragsteuer`, dazu Korrekturzeilen in Planung | beide Kategorien aus der Basis (`jahre.GERECHNET`), gerechnet aus dem Stand des Topfs und `zinsen.mischung`, Steuer in `kaskade` mit `_steuer_auf`; Planzeilen darauf ohne Wirkung (`gilt_in_hochrechnung`) | nein |
| 14 | Steigerung | `RecurringItem.amount_in`: stufenweise, ein Mal im Jahr ab Start der Projektion; Verträge, Planzeilen, Kredite, Gehaltsuntergrenze flach | stetig von der Mitte des Fensters zur Mitte des Jahres (`seit_messung`); Policenbeiträge und Kredite flach, Objekt `year - base_year` | nein |
| 15 | `enden`, `exclude_from_recurring` (`forecast.yaml`) | ja (`konten._enden`, `exclude`) | nein; `investment` fällt über den Block heraus, `enden` gibt `jahre._hochrechnung` nicht an die Vorschau | nein |
| 16 | Anfangsstand | `stichtag.saldo_zum`, sonst `balance_snapshots`, sonst 0 | `bestaende.zusammenfuehren` → `ziele.toepfe`, `tagesgeld_je_konto` | nein (siehe 4.) |
| 17 | Nur Jahresrechnung | | Policen (`jahre._policen_lesen`), Renten (`renten.quellen`), Teilzeit und Verkauf (`szenarien.NUR_JAHRESRECHNUNG`), Rendite auf Depot und Policen, Kaskade | |
| 18 | Nur Monatsmodell | Kontenregeln: Dauerauftrags-Budgets, Auffüllen, Abräumen, Untergrenzen (`kontenregeln`, `forecast.yaml`) | | |

- **Was `fortschreibung.Vorschau` schon teilt:** die Messung (Zeile 1), `verfahren.wahl`, den Typ
  `Ausschluss`, `takt.Reihen` als Quelle, die Abwahl-Datei, die Kreditpläne und
  `szenarien.messung`. Die Vorschau selbst ist ein Wert: Fenster (`since`, `until`,
  `fenster_monate`), Tabelle (`regeln`), `ausschluss`, `ausser`, `enden`, `steigerung` und
  `reihen` setzt jeder Bauer (`konten.kontoprognose`, `jahre._hochrechnung`) für sich.
- **Was jedes Modell selbst misst oder rechnet:** Fenster, Divisor, Verfahren-Tabelle, Gehalt,
  Objekte, Planzeilen (gleiche Messung, andere Rechnung), Verträge, Zinsen, Steigerung, Anfangsstand.
- **Offene Punkte aus Schritt 2:**
  - Gehalt: `jahre.gehalt_median_cents` liest genau `einkommen/gehalt`. Jede Unterkategorie
    (`einkommen/gehalt-…`) landet im Block `gehalt` (`LIKE 'einkommen/gehalt%'` in `abgleich.bloecke`),
    den die Jahresrechnung nie aus der Basis liest. Dort gehen die Nebentätigkeit und jede andere
    Unterkategorie verloren; im Monatsmodell zählen sie als gewöhnliche Reihe. Der Median wird außer in
    `rechnen` nur noch in `annahmen.py` (Anzeige „Gehalts-Median“) und im Rechenwegtext von
    `konten._herkunft_konto` genannt.
  - `szenarien.messung`: eine Funktion, zwei Aufrufer. Das Monatsmodell ruft sie mit dem Zwölfmonatsfenster
    (`konten._planposten`: `abgleich.fenster(conn)`), misst aber seine Basis über sechs; das ist schon
    heute im Monatsmodell selbst verschieden und endet mit E.2.
  - `jahre._vertragsenden`: nur die Jahresrechnung; das Monatsmodell hört am Termin auf zu buchen
    (`abos.posten`, `gekuendigt_zum`). Zwei Wege zu derselben Kündigung, gleiche Zahl bis auf die Steigerung.
  - `jahre.verkaeufe`: nur die Jahresrechnung. Misst Miete und Kosten eines Objekts über `s.property_id`,
    auch für ein Objekt mit Prognose, das gar nicht in `miete` und `immobilie` steht (siehe Abweichung).

**2. Mechanismen, die es schon gibt**

- **Planzeile mit zugeordneten Buchungen** (`szenarien.Line.buchungen`, `szenarien.messung`,
  `restbetrag_je_termin`, `jahreswirkung`, `einmalig_zugeordnet`). Kann: Betrag, Monat, Takt
  (monatlich, quartalsweise, jährlich, einmalig), Ende, Konto und Kategorie; die zugeordneten Buchungen
  und ihre Reihe messen, wie viel der Zeile schon in der Basis steckt. **Bei einer laufenden Zeile bleibt
  die Messung in der Basis**: Die Zeile zählt nur den Rest (Plan minus Gemessenes, gleiches Vorzeichen).
  **Nur bei einer einmaligen Zeile** gehen die Buchungen aus der Basis, und dann zählt die Zeile null
  („gebucht“), und das nur in der Jahresrechnung. Kann nicht: Messung ersetzen und den vollen Betrag
  zählen, in beiden Modellen. Ist die Kategorie abgewählt, ginge der Rest von etwas ab, das in der Basis
  nicht steht. Das ist E.5 (siehe Abweichung).
- **`forecast/ohne_objekt.py`.** Summiert die Posten von `/konten` über alle Konten, ohne Umbuchungen
  (`_UMBUCHUNG`, `zaehlt`: Etiketten `budget:`, `budget/`, `Auffüllung `, `Übertrag von `, Kategorien
  `transfer/` und `investment/`) und ohne die Zeilen der Klammer des Objekts, und stellt das einer
  Messung über zwölf Monate gegenüber. Das ist der Baustein für die Summe über die Konten im
  Paritätstest. Kann nicht: nach Block aufteilen, Jahre bilden, eine Umbuchung am Merkmal statt am
  Etikett erkennen. Der Cashflow ohne Objekt nimmt nur die Klammer des Objekts heraus, nicht seine
  gemessenen Buchungen.
- **`forecast/zinsen.py`.** Rein. `satz_im_monat` gibt den Satz eines Kontos in einem Monat (datierte
  Einträge, sonst langfristig für ein Tagesgeld, sonst null), `mischung` mittelt ihn für einen Topf nach den
  Ständen zu Beginn. Kann: Satz je Konto und Monat, datierte Sätze. Kann nicht: den Stand eines Kontos
  im Verlauf kennen, Steuer, Jahreswechsel. Die Zinsen selbst rechnet `jahre.kaskade` auf den
  Anfangsstand des Jahres.
- **`jahre._steuer_auf(ertrag, frei, quote)`.** Rein: Steuer, verbrauchter Freibetrag, Rest. Der Freibetrag
  gilt für das Kalenderjahr und alle Erträge zusammen (erst Zinsen, dann Vorabpauschale, dann Verkauf).
  Kann nicht: Monate oder Konten; ein Monatsmodell braucht dazu einen Zähler je Haushalt und
  Kalenderjahr, der Zinsen über Konten und Monate summiert.
- **`prognosebasis.vergleich`** stellt je Kategorie Monatsmodell und Jahresrechnung nebeneinander
  (`konten`, `jahr`, `delta`, Grund) – ein Vorbild für den Test auf Ebene der Kategorie, aber ohne Verträge,
  Planzeilen, Zinsen und ohne Jahre.
- **`takt.Reihen`** liefern für eine Zahlung mit festem Takt Betrag und Termin. Die Nebentätigkeit ist im
  Monatsmodell eine Reihe (jährlich); die Schenkung hat keinen festen Takt und bleibt im Rest.

**3. Die Miete eines Objekts mit Prognose.** Sie steht **nirgends**: weder am Objekt
(`objekte.PROGNOSE_FELDER` sind Miete, Kosten, `ab`, `bis`, dazu `saison`) noch an seinem Kredit (das
Objekt der Kopie hat keinen; für die anderen Objekte nennt der Kredit `servicing_account_id` das Konto
der Rate, nicht der Miete). Die gemessenen Mieten aller Objekte der Kopie gehen auf dem Betriebskonto ein,
auch das Objekt, dessen Rate von einem anderen Konto abgeht. Eine Planzeile ohne Konto landet
ebenfalls dort (`konten._planposten`, `_operating_account`). Vorschlag für E.4: das Konto nicht
zu erfinden, sondern abzuleiten, auf dem die Mieten des Objekts zuletzt gebucht wurden
(`splits.property_id`, Kategorie `immobilie/mieteinnahme`), und sonst das Betriebskonto zu nehmen; ein
Feld `prognose.konto` ist nur nötig, wenn der Haushalt davon abweichen will.

**4. Der Anfangsstand eines Kontos ohne Auszug.**
- **Monatsmodell:** `konten.account_forecast` nimmt `stichtag.saldo_zum`; ohne Auszug den jüngsten
  Eintrag in `balance_snapshots` mit `as_of` bis zum Stichtag, sonst null („assumed zero“).
- **Jahresrechnung:** `bestaende.zusammenfuehren` macht jedes `parsed`-Konto zu „aus Auszug“ und setzt
  seinen Betrag auf `None`, wenn es keinen Auszug gibt; `ziele.toepfe` überspringt ihn. Ein
  getippter Betrag in `balances.yaml` zählt für ein solches Konto nicht.
- **In der Entwicklungskopie** gibt es kein solches Konto (alle projizierten Konten haben Auszüge bis zum
  Stichtag) und keine einzige Zeile in `balance_snapshots`; der Anfangsstand ist in beiden Modellen auf den
  Cent gleich. Die Jahresrechnung kennt zusätzlich Positionen (Depots, Policen), die das Monatsmodell
  nicht projiziert. Eine Probe mit einem erfundenen `parsed`-Konto ohne Auszug auf einer Kopie der Kopie
  zeigt die Trennung: Monatsmodell null, mit Snapshot das getippte, mit Snapshot nach dem Stichtag
  wieder null; Jahresrechnung in allen drei Fällen null.
- **Vorschlag zur offenen Frage:** Ja, jede Position unter ihrem eigenen Datum in `balance_snapshots`.
  Heute schreibt `cli._bestaende_spiegeln` nur Positionen mit dem Datum der Datei und löscht beim
  nächsten Lauf nur die `manual`-Zeilen dieses einen Tages; `UNIQUE(account_id, as_of)` trägt mehrere
  Daten je Konto schon. Quelle wären der Eintrag der Position und ihr `verlauf` in `balances.yaml`. Das Monatsmodell nimmt dann den
  jüngsten Stand bis zum Stichtag, und ein Stand, den die Seite später einträgt, kommt an. Dazu gehört eine
  Regel für die Jahresrechnung (derselbe Stand für ein `parsed`-Konto ohne Auszug), sonst bleibt die Trennung.
  Ein Stand nach dem Stichtag zählt auch dann nicht (der erste Prognosemonat ist ein ganzer).

**5. Die Blöcke für den Paritätstest.**

| Block der Jahresrechnung (vor Kaskade) | Größe des Monatsmodells, über alle Konten |
|---|---|
| `gehalt` | Posten mit Kategorie `einkommen/gehalt…` (Untergrenze, Nebentätigkeit) |
| `miete` | `immobilie/mieteinnahme` |
| `einkommen_sonst` | `einkommen/…` ohne Gehalt, **ohne** `einkommen/zinsen` |
| `objekt` | die Objektposten (E.4); bis dahin nichts |
| `fixkosten`, `immobilie`, `konsum`, `steuern` | Posten nach dem Block ihrer Kategorie (`abgleich.bloecke`), Verträge (`abo:…`) nach der Kategorie ihres Vertrags |
| `kredit` | `loan:…` |
| `einmalig` | alle Posten mit Quelle „plan“ (Planzeilen, Wegfall-Zeilen), die keine Umbuchung sind: die Jahresrechnung führt jede Planzeile im Block `einmalig` |
| `rente` | nichts im Horizont |
| Zinsen (kein Block) | `einkommen/zinsen` und `steuern/kapitalertragsteuer` mit den Korrekturzeilen gegen `posten["rendite"]` „Tagesgeld“ und „Kapitalertragsteuer auf Zinsen“; Depot und Policen liegen außerhalb der projizierten Konten |

Umbuchungen heben sich auf, wenn man sie am Etikett erkennt (`ohne_objekt._UMBUCHUNG`): Dauerauftrags-Paare
(`budget:…` und `budget/zuweisung`) und Auffüllungen stehen auf beiden Seiten im Detail. **Das Abräumen nicht:**
`Übertrag von …` steht nur auf dem Zielkonto im Detail, die Abgabe des Betriebskontos in `swept_cents`.
Bilanzprobe: Anfang + Fluss außer Umbuchungen + Umbuchungen im Detail − `swept_cents` = Ende, auf den Cent
(15 Monate). Ein Test sollte die Umbuchung am Merkmal erkennen (ein Feld am Posten) statt an einer Liste
von Vorsilben.

Vorschlag für die **Liste bekannter Unterschiede** (Schlüssel Block, mit Grund und Teilschritt; die
Beträge der Kopie in `notizen/E.0_bestand.md`). Verglichen werden volle Kalenderjahre im Horizont
(2027 bis 2030 bei sechzig Monaten); das Rest-Quartal 2026 nicht, weil dort die Termine des Monatsmodells
gegen den gleichmäßigen Anteil der Jahresrechnung stehen.

| Block | Grund | Teilschritt |
|---|---|---|
| `gehalt` | Untergrenze gegen Median, Steigerung | E.3 |
| `gehalt` | Nebentätigkeit nur im Monatsmodell (Block `gehalt` liest die Jahresrechnung nicht aus der Basis) | E.5 |
| `einkommen_sonst` | Schenkung nur in der Jahresrechnung | E.5 |
| `einkommen_sonst`, `steuern`, `einmalig`, Zinsen | gemessene Zinsen, Steuer und Korrekturzeilen nur im Monatsmodell; Rendite des Topfs nur in der Jahresrechnung | E.6 |
| `objekt`, `immobilie`, `miete` | Prognose nur in der Jahresrechnung; die Buchungen des Objekts zählen im Monatsmodell gemessen | E.4 |
| `miete`, `fixkosten`, `immobilie`, `konsum`, `einmalig` (Wegfall-Zeilen) | Fenster, Divisor und Verfahren | E.2 |
| alle gemessenen Blöcke | Steigerung: stufenweise ab Projektionsstart gegen stetig ab der Fenstermitte (genau 2 % bei 2 % Inflation, jedes Jahr gleich) | **kein Teilschritt, siehe Abweichung** |
| `fixkosten` | Verträge: nominal nach Termin gegen gemessen mit Inflation; Kündigungen auf zwei Wegen | Steigerung, sonst keiner |
| `einmalig` | Zeilen „nur Kontoprognose“ (die Jahresrechnung sieht sie nie) | gewollt, bleibt |
| `gehalt`, `rente` (Teilzeit, Ruhestand), Verkauf | nur Jahresrechnung | außerhalb des Horizonts oder gewollt |

**6. Welche Seiten Zahlen zeigen, die sich ändern.** Monatsmodell: `/konten` (Vorlage `konten.html`,
Route `routen/konten.py`), das Konten-Signal und der Cashflow ohne Objekt auf `/monatsabschluss`
(`routen/auswertung.py`, `monatsabschluss.html`), `finctl forecast`. Jahresrechnung: `/ziele`
(„hochgerechnet“, Rentenlücke), `/hochrechnung` (Route in `routen/annahmen.py`), `/annahmen`
(Gehalts-Median), `/monatsabschluss` (Karte Fortschritt, Wirkung), der Szenarienvergleich der
Kommandozeile (`cli.py`); `/renten` liest dieselben Eingaben, ändert sich aber in E.2 bis E.7 nicht. Beide: `/annahmen#prognosebasis` (Tabelle und Treffer-Check).

| Teilschritt | Ändert Zahlen auf |
|---|---|
| E.2 | `/konten` (jeder Monat, Tiefpunkte, Warnungen, Rechenwege „Median … Fenster ab …“), Cashflow ohne Objekt und Konten-Signal auf `/monatsabschluss`, `/annahmen#prognosebasis` (Tabelle, Treffer-Check), `finctl forecast`. Jahresrechnung unverändert. Die Beschriftung „Fenster, Mindestvorkommen“ in `annahmen.html` nennt `forecast.yaml` |
| E.3 | `/konten` und Cashflow ohne Objekt (Gehalt wächst), `/ziele`, `/hochrechnung`, `/monatsabschluss` (Fortschritt, Wirkung des Gehalts), `/annahmen` (Gehalts-Median nur noch als Vergleich), Rentenlücke, Szenarienvergleich auf der Kommandozeile |
| E.4 | `/konten` (Miete und Kosten des Objekts je Monat, auf dem Konto aus Frage 3), Cashflow ohne Objekt (die Objektposten gehören heraus), `/monatsabschluss`; `/immobilie/<id>` und `/immobilien` ändern ihren Text („wirkt in der Hochrechnung statt der Messung“, `immobilie.html`). Jahresrechnung unverändert |
| E.5 | `/konten`, `/planung` (neue Zeilenart), `/ziele`, `/hochrechnung` (die Schenkung wandert vom Block `einkommen_sonst` zum Block `einmalig`), `/annahmen#prognosebasis` (die Abwahl der Schenkung entfällt) |
| E.6 | `/konten` (Konto des Tagesgelds und Betriebskonto: Zinsen und Steuer je Monat), `/planung` und `/annahmen` (Text „ohne Wirkung in der Hochrechnung“, `annahmen._zinszeilen_ohne_wirkung`), `/monatsabschluss`. Die Jahresrechnung ändert sich höchstens, wenn der Freibetrag über die Konten anders verteilt wird |
| E.7 | `/ziele` (Karte „hochgerechnet“ der kurzfristigen Ziele), die Fortschrittskarte auf `/monatsabschluss`, `/konten` (Untergrenze des Notgroschens, Warnungen), Konten-Signal |

**Vorschläge für E.2** (entscheidet Opus). Aus `forecast.yaml` entfallen `window_months`,
`min_occurrences`, `variable_kosten` und der tote Schlüssel `window_months_fixkosten`. Es bleibt eine
Konstante im Code (`abgleich.fenster`, schon Vorgabe zwölf), die beide Bauer nehmen. Der Divisor ist
`f.monate` des Haushalts für **jedes** Konto, nicht der des Kontos ab seinem ersten Auszug
(`fortschreibung._fenstermonate`): Nur dann ergibt die Summe über die Konten die Zahl der Jahresrechnung.
Folge: Ein Konto, das jünger als zwölf Monate ist, trägt nur den Teil, den es gemessen hat. Das tut die
Jahresrechnung schon heute. Die Datei darf die alten Schlüssel weiter enthalten (ignoriert), damit der echte
Ordner nicht umgestellt werden muss.

**E.0 abgenommen am 25.10.2026 (Opus).** Die Antworten belegen jede Eingabe mit Datei und Funktion. Die Beträge stehen nur in `notizen/E.0_bestand.md`. Die Entscheidungen zu den Abweichungen:
1. **Steigerung:** ein eigener Teilschritt **E.2b**, gleich nach E.2, denn jeder Teilschritt ändert eine Eingabe. Es gilt die Regel der Jahresrechnung: Die Steigerung läuft stetig ab der Mitte des Messfensters, im Monatsmodell je Monat. Verträge steigen in beiden Modellen mit der Inflation wie gemessene Posten. Policenbeiträge, Kreditraten und die Gehaltsuntergrenze (die hat E.3) bleiben flach. Ohne E.2b wäre die Liste in E.8 nicht leer.
2. **Saisonfaktoren:** bleiben. E.4 rechnet in beiden Modellen mit der Kurve; heute ist jede Kurve 1,0.
3. **Divisor:** Jedes Konto teilt durch die Fenstermonate des Haushalts (`f.monate`), in E.2. Ein jüngeres Konto trägt damit nur den Teil, den es gemessen hat, wie in der Jahresrechnung.
4. **Erwartete Einnahme:** eine neue Art der Planzeile in E.5. Ihre zugeordneten Buchungen fallen aus beiden Messungen, und die Zeile zählt voll. Die bestehenden Arten bleiben, wie sie sind. „Erwartete Einnahme“ kommt in `CONTEXT.md`.
5. **Block `gehalt`:** nur noch genau `einkommen/gehalt`. Eine Unterkategorie geht dann in keinem Modell mehr verloren. Die Nebentätigkeit wird trotzdem nach Entscheidung 3 eine erwartete Einnahme, ihre Buchungen sind ihr zugeordnet. Beides in E.5.
6. **Konto der Objektmiete:** wie vorgeschlagen, in E.4. Es ist das Konto, auf dem die Mieten des Objekts zuletzt gebucht wurden, sonst das Betriebskonto. Ein Feld `prognose.konto` gibt es nur, wenn der Haushalt davon abweicht.
7. **Verkauf eines Objekts mit Prognose:** in E.4. Die Objektposten enden mit dem Verkauf, und `jahre.verkaeufe` zieht für ein solches Objekt nichts aus `miete` und `immobilie` ab.
8. **Art eines Kontos für den Zins:** kommt in beiden Modellen aus `kind` in `balances.yaml`, wie in der Jahresrechnung. `accounts.account_type` bleibt für das Einlesen. Festgelegt vor E.6.
9. **Umbuchungen:** Der Test erkennt sie an einem Merkmal am Posten statt an einer Liste von Vorsilben. Das baut E.1.
10. **Zeilen „nur Kontoprognose“:** bleiben gewollt in der Liste bekannter Unterschiede. Sie sind neben der Kaskade die zweite erlaubte Ausnahme in E.8.
11. **Anfangsstand eines Kontos ohne Auszug:** jede Position unter ihrem eigenen Datum in `balance_snapshots`, und die Jahresrechnung nimmt für ein Konto mit Auszug, aber ohne Auszug bis zum Stichtag, denselben Stand. Heute wirkt das bei keinem Konto. Umgesetzt in E.7, wo der Stand eines Kontos zum Stichtag zählt.
12. **Handentscheidungen für E.5 und E.6:** Auch der echte Ordner hat weder Abwahl noch Takt noch Zinssätze. Bevor E.5 und E.6 beginnen, fragt Opus den Haushalt nach Schenkung, Nebentätigkeit und Zinssätzen und trägt sie in der Entwicklungskopie ein.
13. **Tote Schlüssel in `forecast.yaml`** (`window_months`, `min_occurrences`, `variable_kosten`, `window_months_fixkosten`): E.2 liest sie nicht mehr, und der Code duldet sie. Aus der Datei des Haushalts nimmt Opus sie mit dessen Zustimmung heraus.
14. **Was wie ein Eingabefehler aussieht** (Zeile „Steuererstattung“ monatlich ohne Ende, eine einmalige Gutschrift unter Mobilfunk): Opus hat beides dem Haushalt vorgelegt. Ist es korrigiert, zieht Opus die Entwicklungskopie neu und schreibt die Referenz neu, bevor E.2 misst.

### E.1 Paritätstest (gleich)

- Ein Test vergleicht je Kalenderjahr im Horizont von `/konten` und je Block
  die externen Flüsse des Monatsmodells mit der Jahresrechnung vor der
  Kaskade.
- Die heutigen Unterschiede stehen in einer Liste bekannter Unterschiede, je
  Block mit Grund und Teilschritt. Die Liste darf nur kürzer werden.
- Die Toleranz deckt Rundung ab. Den Zeitpunkt deckt sie nicht ab: Über ein
  volles Kalenderjahr gleichen sich Termine aus.
- Er läuft auf beiden Datensätzen, also braucht der Musterhaushalt jede Art
  Eingabe.
- Keine Zahl ändert sich: `pruefen` meldet „Gleich“.

**Umgesetzt am 25.10.2026, E.1 (Sonnet).** Der Test steht in `tests/test_paritaet.py`.
- **Wie er vergleicht:**
  - Er rechnet `household_accounts` über den langen Horizont von `/konten` (60 Monate) und die
    Jahresrechnung wie die Route `/ziele` (Tempo „schnitt“).
  - Verglichen werden die vollen Kalenderjahre im Horizont (heute 2027 bis 2030), je Block der
    Jahresrechnung vor der Kaskade. Das Basisjahr zählt nur, wenn von ihm nichts im Bestand steckt.
  - Zuordnung nach E.0, Frage 5: ein Posten in den Block seiner Kategorie (`abgleich.bloecke`, über
    `prognosebasis._block_fuer`), ein Vertrag in den Block der Kategorie seines Vertrags, `loan:…` in
    `kredit`, eine Planzeile in `einmalig`.
  - `zinsen` ist ein zwölfter Eintrag neben den Blöcken: gemessene Zinsen, Kapitalertragsteuer und
    die Korrekturzeilen darauf gegen die Rendite des Tagesgelds minus die Steuer auf Zinsen in
    `posten["rendite"]`. Sie fehlen damit in `einkommen_sonst`, `steuern` und `einmalig`.
  - Die Toleranz ist ein Euro je Block und Jahr (`RUNDUNG_CENTS`). Termine gleichen sich über ein
    Jahr aus, also braucht der Test keine weitere.
- **Das Merkmal für Umbuchungen** ist `Posten.umbuchung` (`forecast/herkunft.py`). Gesetzt wird es dort,
  wo die Posten entstehen (`forecast/konten.py`): Dauerauftrag an ein Konto und Zuweisung auf ihm
  (`account_budgets`), Auffüllung (beide Seiten) und Abräumen („Übertrag von …“). `als_herkunft` gibt
  `umbuchung` nur aus, wenn es gesetzt ist; die Herkunft der übrigen Posten ist unverändert.
  - `forecast/ohne_objekt.py` liest das Merkmal und nicht mehr die Vorsilben (`_UMBUCHUNG` entfällt).
    Geblieben ist die Regel nach Kategorie: Was `transfer/` oder `investment/` heißt, ist kein Cashflow,
    gemessen wie als Planzeile. Die Zahlen sind gleich (`pruefen`, Suite).
  - Eine Planzeile mit der Kategorie `transfer/` trägt das Merkmal nicht: Ihre Gegenseite liegt nicht in
    der Projektion, und die Jahresrechnung zählt sie in `einmalig`.
- **Die Bilanzprobe** (`test_nothing_is_counted_twice_or_not_at_all`) hat zwei Gleichungen. Anfang plus
  externe Flüsse plus Umbuchungen im Detail minus Abgeräumtes ergibt das Ende, und das Detail jedes
  Monats ergibt Kosten plus Einnahmen. Dazu heben sich die Umbuchungen auf: Was als Übertrag auf dem
  Zielkonto steht, hat das Betriebskonto abgegeben.
- **Die Liste bekannter Unterschiede** (`BEKANNT`), je Block die Gründe mit ihrem Teilschritt:

  | Block | Grund | Teilschritt |
  |---|---|---|
  | `gehalt` | Untergrenze gegen Median; die Untergrenze steigt im Monatsmodell nicht | E.3 |
  | `gehalt` | Nebentätigkeit nur im Monatsmodell (der Block liest die Jahresrechnung nicht aus der Basis) | E.5 |
  | `miete`, `einkommen_sonst`, `fixkosten`, `immobilie`, `konsum`, `steuern` | Fenster, Divisor und Verfahren | E.2 |
  | dieselben | Steigerung: stufenweise ab Projektionsstart gegen stetig ab der Fenstermitte | E.2b |
  | `fixkosten` | Verträge nominal nach Termin gegen gemessen mit Inflation; Kündigungen auf zwei Wegen | E.2b |
  | `einkommen_sonst` | Schenkung nur in der Jahresrechnung | E.5 |
  | `objekt` | Prognose nur in der Jahresrechnung | E.4 |
  | `immobilie` | Objekt mit Prognose: im Monatsmodell zählen seine gemessenen Buchungen | E.4 |
  | `einmalig` | Wegfall-Zeilen: Fenster, Divisor und Verfahren (E.2) und Steigerung (E.2b) | E.2, E.2b |
  | `zinsen` | gemessen mit Korrekturzeilen gegen gerechnet aus Stand und Satz | E.6 |

  `kredit` und `rente` weichen nicht ab und stehen nicht in der Liste. Auf Dauer anders bleiben nur die
  Kaskade (der Test vergleicht die Blöcke davor) und die Planzeilen „nur Kontoprognose“ (Abnahme E.0,
  Nummer 10). Der Test nimmt sie aus `einmalig` heraus und führt sie in `DAUERHAFT`, nicht in der Liste.
  Die Anlagen (`investment/`) nimmt er heraus, weil die Jahresrechnung sie aus der Basis nimmt.
- **Wie die Liste kürzer wird:** Ein Block, der abweicht und nicht in ihr steht, lässt den Test
  fehlschlagen (`test_every_difference_is_known`). Ebenso einer, der in ihr steht, im Haushalt
  vorkommt und nicht mehr abweicht (`test_a_listed_block_that_no_longer_differs_leaves_the_list`).
  Ein Block ohne Zahl auf beiden Seiten gilt als nicht vorhanden: Die Liste gilt für beide Datensätze,
  und der Musterhaushalt hat zum Beispiel keine sonstigen Einnahmen. Jeder Teilschritt streicht seine
  Gründe und, wenn der Block danach gleich ist, den ganzen Eintrag.
- **Musterhaushalt:** Es fehlte nur der Wegfall. In der aktiven Klammer „Korrektur Forecast“
  (`tests/musterhaushalt/config/szenarien.yaml`) steht jetzt die Wegfall-Zeile „Tanken entfaellt“ ab dem
  nächsten Kalenderjahr; `tests/musterhaushalt/bauen.py` trägt die Buchungen der Reihe nach dem Einlesen
  ein, wie bei der Police. Objekt mit Prognose, Planzeilen, Vertrag, Kredit, Zinsen (gemessen, Satz und
  Korrekturzeile) und Umbuchungen (Zuweisungen, Abräumen) hatte er schon. Auf beiden Datensätzen
  weichen `gehalt`, `miete`, `objekt`, `fixkosten`, `immobilie`, `konsum` und `zinsen` ab; `einmalig`
  nur noch mit dem Wegfall; `steuern` nur im Musterhaushalt (in der Kopie ist es beide Male null);
  `einkommen_sonst` nur in der Kopie. `kredit` und `rente` sind gleich.
- **Was der Test heute zeigt:** `notizen/E.1_paritaet.md` der Entwicklungskopie, mit den Beträgen je
  Jahr und Block. Er stimmt mit den Zahlen aus `notizen/E.0_bestand.md` überein, sobald man dort die
  Zinszeilen in `zinsen` umstellt.
- **Gleich:** `tests/referenz.py pruefen` meldet „Gleich“ ohne `--nur-zahlen`. Suite auf der
  Entwicklungskopie und auf dem Musterhaushalt grün, `ruff` null Funde, `ZU_VERZWEIGT` unverändert.
  Vorlagen, Routen und Skripte sind unberührt, die Browsertests liefen deshalb nicht.

**E.1 abgenommen am 25.10.2026 (Opus).** `pruefen` meldet „Gleich“, und `test_paritaet` und `test_ohne_objekt` sind auf beiden Datensätzen grün. Das Merkmal `Posten.umbuchung` ersetzt die Vorsilben. Zu den Abweichungen:
1. **Zinsen:** `zinsen` bleibt auf Dauer anders, wie die Kaskade. Die Jahresrechnung verzinst den Topf nach der Kaskade, und dieser Stand ist ihr Ergebnis, keine Eingabe. E.6 belegt die Angleichung deshalb nicht im Paritätstest, sondern mit einem eigenen Test: Bei gleichem Stand und gleichem Satz rechnen beide Modelle für ein Jahr denselben Zins und dieselbe Steuer. Nach E.6 wandert `zinsen` von `BEKANNT` nach `DAUERHAFT`, mit diesem Grund.
2. **Gründe je Block:** angenommen. Bei jeder Abnahme sehe ich mir die Reste im Block in `notizen/E.1_paritaet.md` an.
3. **`einkommen_sonst` im Musterhaushalt:** E.5 bringt Schenkung und Nebentätigkeit dorthin.
4. **`steuern`:** angenommen, wie beschrieben.
5. **Feste Jahreszahlen im Musterhaushalt:** ein eigener kleiner Auftrag vor E.2 (Haiku). Die Zeilen bekommen Platzhalter relativ zu heute.

### E.2 Fenster und Verfahren (gewollt)

- Zwölf Monate und die Zwölfmonatssumme durch zwölf im Monatsmodell, nach
  den Entscheidungen 5 und 6.
- `window_months` in `forecast.yaml` entfällt oder gilt für beide. E.0
  schlägt vor, was davon bleibt.
- `/prognosebasis` zeigt danach eine Basis statt zwei.

**Umgesetzt am 25.10.2026, E.2 (Sonnet).** Die Beträge stehen in `notizen/E.2_pruefen_unterschiede.md`
und `notizen/E.2_paritaet.md` der Entwicklungskopie.
- **Fenster:** `abgleich.FENSTER_MONATE` (12) ist die eine Konstante und Vorgabe von `abgleich.fenster`.
  `konten.kontoprognose` und `jahre._hochrechnung` nehmen beide `abgleich.fenster` und damit dasselbe
  Fenster (`von`, `bis`, `monate`). Das Monatsmodell misst bis zum Monatsende des Tages vor dem ersten
  offenen Monat, wie bisher. Ein Test hält beides fest
  (`test_the_kontoprognose_measures_over_the_window_of_the_hochrechnung`).
- **Verfahren:** `verfahren.KONTOPROGNOSE` ersetzt `kontoprognose_regeln`: Kosten und Einnahmen rechnen mit
  `schnitt`, der Summe des Fensters durch seine Monate. Das ist die Zwölfmonatssumme der Jahresrechnung
  (`HOCHRECHNUNG`) als Monatsrate; ein Test (`test_the_kontoprognose_table_is_the_hochrechnung_sum_per_month`)
  hält fest, dass beide bis auf einen Cent je Monat übereinstimmen. `verfahren.median`, `Regel("median")`
  und `min_occurrences` (in `Einstellung`, `Vorschau`, `vorschau_konto`) entfallen, ebenso `wahl(..., ende)`,
  das nur der Median brauchte. `HOCHRECHNUNG_JUENGST` ist unberührt: Es gehört der Jahresrechnung und kennt
  nur die Summe aufs Jahr.
- **Divisor:** `Vorschau.fenster_monate` ist für beide Reihen Pflicht (ohne sie: `ValueError`), und
  `fortschreibung._fenstermonate` entfällt. Jedes Konto teilt durch die Monate des Haushaltsfensters; ein
  jüngeres Konto trägt nur, was es gemessen hat (`test_every_account_divides_by_the_months_of_the_household_window`).
  `engine.derive_recurring` (nur Tests rufen es) bekommt `fenster_monate`; ohne Angabe zählen die
  Kalendermonate von `since` bis `until`.
- **`forecast.yaml`:** `window_months`, `min_occurrences`, `variable_kosten` und `window_months_fixkosten`
  liest kein Code mehr. Sie stehen nicht mehr im Musterhaushalt (`finctl/vorgaben/` hatte sie nie); die
  Entwicklungskopie behält sie. Ein Test belegt, dass sie geduldet werden und nichts ändern
  (`test_the_old_window_keys_of_forecast_yaml_are_tolerated_and_change_nothing`).
- **Seiten:** `/annahmen#prognosebasis` zeigt `/konten` und Jahresrechnung weiter nebeneinander, aber mit
  einer Basis: Kategorien ohne eigenen Unterschied tragen den Grund „gleiche Basis: Summe von zwölf Monaten“
  (Differenz bis 5 Cent, `prognosebasis.RUNDUNG_CENTS`), die Gründe „Median je Konto über kürzeres Fenster“
  und „nicht in mindestens N von M Monaten gebucht“ entfallen, ebenso die Schlüssel `min_vorkommen` und
  `fenster_konten` der Seite. Berichtigt sind außerdem die Beschriftung von `forecast.yaml` und `abos.yaml`
  in `annahmen.html`, die Rechenwege „ersetzt den Median“ und „zählen nicht mehr im Median“
  (`konten.py`), der tote Schlüssel `median_monate` der Route `/konten`, `HANDBUCH.md` (mit der Kopie im
  Paket) und der Begriff „Verfahren“ in `CONTEXT.md`. Der Rechenweg eines Rests lautet jetzt „Summe … über
  12 vollständige Monate, im Monat …“. Den Rest des Textes erneuert Schritt 6.
- **Paritätstest:** Der Grund „Fenster, Divisor und Verfahren“ (E.2) ist aus allen Blöcken gestrichen, auch
  der aus `einmalig`; 21 Gründe wurden 16. Kein Block fällt ganz heraus, weil jeder noch aus einem anderen
  Grund abweicht. Dazu stehen drei Gründe da, die der Median bisher verdeckt hat (siehe Abweichungen):
  `miete` E.4, `konsum` und `einmalig` je E.8. Den Grund „Schenkung nur in der Jahresrechnung“ in
  `einkommen_sonst` habe ich gestrichen, weil er nicht mehr stimmt. Was je Block und Jahr vorher und nachher
  übrig ist, steht in `notizen/E.2_paritaet.md`, auch ohne Steigerung gerechnet (Inflation 0 auf einer Kopie):
  dort bleibt von `konsum`, `miete`, `immobilie`, `einkommen_sonst` und `einmalig` nur, was die Gründe der
  Liste nennen.
- **Gemessen (`pruefen --nur-zahlen`):** vorher „Gleich“, nachher 11 Unterschiede: `ableitung/` (Posten je
  Konto, Kontoprognose auf 12 und 60 Monate, Prognosebasis, Treffer-Check nur im Konten-Teil) und `seiten/`
  (`konten`, `annahmen`, `prognosebasis`, `start`, `bestaende`, `monatsabschluss`). `hauptbuch/`, die
  Jahresrechnung (`hochrechnung`, `/ziele`, `/hochrechnung`, `/renten`) und alle anderen Seiten sind gleich.
  Jeder Posten, der keine Reihe mit Takt ist (Verträge, Kredite, Planzeilen, Gehaltsuntergrenze), ist
  unverändert; der Rest von 32 auf 69 Posten: 32 ändern sich (29 Kosten durch das Fenster, 3 Einnahmen durch
  das Verfahren), 37 kommen dazu (Kosten, die nur vor dem alten Fenster lagen, und Einnahmen unter der
  Mindestzahl), keiner fällt weg. Die Größenordnung: Die Monatsrate des Rests ändert sich je Block um
  einige Prozent bis einige hundert Euro im Monat; die Einnahmen im Rest steigen (Schenkung, Nebentätigkeit
  und Kleinbeträge, die der Median wegließ) und überwiegen in dieser Kopie die zusätzlichen Kosten, sodass
  der Cashflow ohne Objekt und der Tiefpunkt des Betriebskontos sich verbessern, nicht verschlechtern.
  Das Konsumkonto liegt im kurzen Horizont um etwa ein Drittel weniger tief, das Betriebskonto um rund die
  Hälfte weniger tief; ein Girokonto mit wenigen Posten, zu dem Kosten dazukommen, liegt um ein Mehrfaches
  tiefer (von einem niedrigen Stand aus). Die Zahlen je Seite stehen in `notizen/E.2_pruefen_unterschiede.md`.
- **Tests:** Suite auf der Entwicklungskopie und auf dem Musterhaushalt grün bis auf `test_referenz` (bis zum
  Neuschreiben der Referenz) und vier Tests zu `reihen_custom.yaml` (Abweichung unten); `ruff` null Funde;
  `ZU_VERZWEIGT` um `prognosebasis._grund` kürzer, sonst unverändert. Vorlagen und Routen sind berührt
  (`annahmen.html`, `routen/konten.py`): Browsertests auf der Kopie bis auf zwei dieser vier grün.

**E.2 abgenommen am 25.10.2026 (Opus), Referenz neu geschrieben.** `pruefen --nur-zahlen` zeigte elf Unterschiede, alle im Monatsmodell: `ableitung/` mit Posten, Kontoprognose, Prognosebasis und Treffern, dazu `/konten`, `/annahmen`, `/prognosebasis` und das Konten-Signal auf `/start`, `/bestaende` und `/monatsabschluss`. `hauptbuch/` und jede Seite der Jahresrechnung blieben gleich. Der Paritätstest ist auf beiden Datensätzen grün. Die Referenz ist danach neu geschrieben (`notizen/E.2_referenz_vor_neuschreiben.txt`). Zu den Abweichungen:
1. **`miete`:** angenommen. Die gemessene Miete des Objekts mit Prognose verschwindet mit E.4.
2. **Schenkung:** angenommen. E.5 ersetzt „gemessen in beiden“ durch die erwartete Einnahme.
3. **Durchlaufendes Konto:** Das Monatsmodell zählt seine Ausgaben auf dem Konto, das es deckt. Dafür gibt es einen eigenen Teilschritt **E.2c**, denn auch das ist eine Eingabe. Ohne ihn fehlten diese Ausgaben im Monatsmodell, und das wäre zu optimistisch.
4. **Wegfall-Zeile mit einer großen Reihe** (E.0, `notizen/E.0_bestand.md` §7 Nummer 6): Das ist eine Frage der Eingabe. Opus legt sie dem Haushalt vor. Bis dahin bleibt der Grund mit E.8 in der Liste.
5. **`zinsen`:** angenommen. Das löst E.6.
6. **Tests, die eine leere `reihen_custom.yaml` annehmen:** ein eigener kleiner Auftrag (Haiku). Die Tests prüfen danach, was sich gegenüber vorher ändert, statt eine leere Datei vorauszusetzen.
7. **Unruhiger Browsertest auf dem Musterhaushalt:** beobachten. Fällt er in E.2b wieder auf, bekommt er einen eigenen Auftrag.

### E.2b Steigerung (gewollt)

- Abgeleitete Posten und Verträge steigen im Monatsmodell stetig ab der Mitte
  des Messfensters, je Monat, wie in der Jahresrechnung (Abnahme E.0, Nummer 1).
- Policenbeiträge, Kreditraten und die Gehaltsuntergrenze bleiben flach.
- Verträge steigen auch in der Jahresrechnung; eine Kündigung wirkt in beiden
  über denselben Weg.

**Umgesetzt am 25.10.2026, E.2b (Sonnet).** Die Beträge stehen in `notizen/E.2b_paritaet.md` und
`notizen/E.2b_pruefen_unterschiede.md` der Entwicklungskopie.
- **Eine Rechnung:** `forecast/wachstum.py` hält sie für beide Modelle: Ein gemessener Betrag steigt stetig
  von der Mitte des Messfensters (`abgleich.Fenster.mitte`) bis zum Zeitpunkt, an dem er fällt, mit
  `assumptions.grow`. Die Jahresrechnung nimmt als Zeitpunkt die Mitte des Jahres (`jahresmitte`, wie bisher,
  nur über die gemeinsame Funktion), das Monatsmodell die Mitte des Monats (`monatsmitte`). Die zwölf
  Monatsmitten eines Jahres mitteln sich auf die Jahresmitte; ein Test hält fest, dass zwölf Monate bis auf
  die Rundung den Jahresbetrag ergeben (`tests/test_steigerung.py`).
- **Gemessene Posten:** `RecurringItem.amount_in(month)` steigt stetig je Monat, nicht mehr stufenweise ab
  dem Start der Projektion. Der Posten trägt die Mitte seines Fensters (`mitte`); eine Steigerung ohne sie ist
  ein Fehler. Gehaltsuntergrenze (Override), Kreditraten und Planzeilen bleiben flach. Der Treffer-Check
  (`forecast/treffer.py`) rechnet dieselbe Steigerung, sonst prüfte er ein anderes Modell als die Prognose.
- **Verträge:** `konten._vertragsposten` bucht den Betrag am Vertrag mit der Inflation seit der Mitte des
  Fensters (`konten.vertragsbetrag`). Ein Beitrag in eine Police bleibt fest (`konten.police_vertraege`: die
  Verträge, die eine Rentenquelle mit Konto als `beitrag` nennt), wie `jahre._beitragsposten`. Die Herkunft
  eines Vertrags sagt es im Text. Kündigung: Das Monatsmodell hört am Termin auf zu buchen, die Jahresrechnung
  zieht die gemessene Reihe ab (`_vertragsende_posten`, mit derselben Inflation wie die Basis). Beide kommen auf
  dieselbe Steigerung; was bleibt, steht unter Abweichungen.
- **Texte:** Rechenweg der Reihen („steigt mit … im Jahr, stetig ab der Mitte des Fensters“) und der Verträge
  (`konten.py`, `verfahren.py`), `HANDBUCH.md` (mit der Kopie im Paket) unter /vertraege, `prognosebasis.py`.
  Den Rest erneuert Schritt 6.
- **Paritätstest:** Der Grund „Steigerung“ ist aus allen Blöcken gestrichen. `einkommen_sonst` und `steuern`
  fallen ganz heraus. `fixkosten` hat noch einen Grund (Messung der Reihe eines Vertrags gegen den Betrag am
  Vertrag, E.8), `einmalig` einen neuen für die Wegfall-Zeile in der Jahresrechnung (E.8, siehe Abweichungen).
  Ohne Inflation (Kopie mit `inflation_pa: 0`) ist jeder Block nach E.2b so wie nach E.2. Was je Block und
  Jahr übrig ist: `notizen/E.2b_paritaet.md`.
- **Musterhaushalt:** `miete` ist dort ohne Steigerung gleich geworden, steht aber wegen der gemessenen Miete
  eines Objekts mit Prognose (E.4) in der Liste. Das Ferienhaus bekam eine erfundene, runde Mietbuchung
  (`tests/musterhaushalt/bauen.py`, Regel `ferienhaus-miete`), damit der Grund auch dort besteht.
- **Gemessen (`pruefen --nur-zahlen`):** vorher „Gleich“, nachher 10 Unterschiede, alle im Monatsmodell:
  `ableitung/` (Posten je Konto, nur im Text des Rechenwegs; Kontoprognose auf 12 und 60 Monate; Treffer-Check;
  `prognosebasis.json` bleibt gleich) und `seiten/` (`konten`, `annahmen`, `prognosebasis`,
  `start`, `bestaende`, `monatsabschluss`). `hauptbuch/`, die Jahresrechnung (`/ziele`, `/hochrechnung`,
  `/renten`) und alle anderen Seiten sind gleich. Größenordnung: Die Kosten der Konten steigen über 12 Monate
  um ein bis zwei Prozent, über 60 Monate bis gut zwei Prozent, die Einnahmen ähnlich; die Tiefpunkte des
  Betriebskontos und des Trade-Kontos liegen tiefer (kurzer Horizont: Betriebskonto um einige zehn Euro, Trade-Konto
  um rund 200); das Soll des Treffer-Checks liegt rund ein Prozent höher. Das Monatsmodell wird also
  pessimistischer, die Jahresrechnung bewegt sich nicht.
- **Tests:** Suite auf der Entwicklungskopie und auf dem Musterhaushalt grün bis auf `test_referenz`
  (bis zum Neuschreiben der Referenz); `ruff` null Funde; `ZU_VERZWEIGT` unverändert. Alte Tests der stufenweisen
  Steigerung sind durch stetige ersetzt (`test_forecast.py`), der Wegfall-Test erwartet den gesteigerten Betrag
  (`test_wegfall.py`). Vorlagen, Routen und Skripte sind nicht berührt, die Browsertests liefen nicht.

**E.2b abgenommen am 25.10.2026 (Opus), Referenz neu geschrieben.** `pruefen --nur-zahlen` zeigte zehn Unterschiede, alle im Monatsmodell. `hauptbuch/` und die Jahresrechnung blieben gleich. Der Paritätstest und `test_steigerung` sind auf beiden Datensätzen grün. Zu den Abweichungen:
1. **Wegfall-Zeilen in der Jahresrechnung flach:** Das wird angeglichen, in einem Nachtrag **E.2b-N**. Die Jahresrechnung zieht eine Wegfall-Zeile mit derselben Steigerung ab wie die Reihe in der Basis, über `forecast/wachstum.py`. Sonst wüchse ein Rest, den es nicht gibt. Das ist dieselbe Eingabe wie E.2b, deshalb ein Nachtrag und kein neuer Teilschritt.
2. **`fixkosten`, Vorrat und Mitzahler:** ein eigener Teilschritt **E.2d Verträge**. Der Vorrat eines Vertrags (bezahlt bis zu einem Datum) gilt auch in der Jahresrechnung, denn er ist eine Tatsache des Vertrags. Mitzahler zählen in beiden Modellen über den Vertrag: der Betrag am Vertrag und die Rückzahlungen der Mitzahler. Ihre Buchungen fallen dafür aus der Messung, wie die eigene Reihe des Vertrags. Eine gekündigte Reihe mit Wegfall-Zeile zählt in beiden Modellen an derselben Stelle.
3. **Reihen mit Takt steigen an ihrem Termin:** gewollt. Schlägt der Test wegen eines großen Jahrespostens an, wird es dann entschieden.
4. **Erfundene Miete im Musterhaushalt:** angenommen. Ein Grund in `BEKANNT` muss auf beiden Datensätzen bestehen.

**Umgesetzt am 25.10.2026, E.2b-N (Sonnet).** Die Beträge stehen in `notizen/E.2b-N_paritaet.md` und
`notizen/E.2b-N_pruefen_unterschiede.md` der Entwicklungskopie.
- **Jahresrechnung:** `szenarien.jahreswirkung` bekommt den Faktor des Jahres (`steigerung`, `wachstum.faktor`: Inflation
  von der Mitte des Messfensters zur Jahresmitte) und zieht das Gemessene damit gesteigert ab: bei einer Wegfall-Zeile die
  ganze Messung, bei einer laufenden Planzeile mit zugeordneten Buchungen den Teil in `rest = geplant − gemessen`.
  Der geplante Betrag bleibt flach, er ist eine gesetzte Zahl. `jahre._planposten` reicht denselben Faktor weiter, den
  die Reihen der Basis haben (`fakt` in `rechnen`); die Herleitung nennt die Steigerung mit. Ausgenommen sind
  Wegfall-Zeilen über den Beitrag in eine Police (`jahre._beitrags_wegfaelle`, `Planzeilen.nominal`): Die Ausgabe dafür
  ist nominal fest (`_beitragsposten`), also zieht die Zeile sie nominal ab; sonst bliebe ein Rest stehen
  (`test_policen` hielt es fest und schlug beim ersten Versuch an).
- **Monatsmodell:** `konten.wegfall_posten` zog das Gemessene schon gesteigert ab (es rechnet die Ableitung mit und ohne
  die Reihe, beide über `amount_in`); dort war nichts zu tun. Die Planzeilen mit Rest (`restbetrag_je_termin`) zogen es
  noch flach ab. Das ist angeglichen: `konten._planposten` rechnet den Faktor je Monatsmitte. Die Seite
  `/planung` (`restwirkung_monatlich`) bleibt ohne Faktor, siehe Abweichungen.
- **Paritätstest:** Der Grund „Wegfall-Zeilen: die Jahresrechnung zieht flach ab“ ist aus `einmalig` gestrichen. Der
  Block bleibt mit dem anderen Grund (Wegfall-Zeile mit der großen Reihe, E.0 §7 Nummer 6). Die Differenz wandert nicht
  mehr (vorher von negativ nach positiv), sie wächst nur noch mit der Inflation um rund 2 Prozent im Jahr. Im
  Musterhaushalt war der gestrichene Grund der einzige: `einmalig` ist dort gleich. Weil der Test verlangt, dass ein
  Block, der nicht mehr abweicht, die Liste verlässt, gibt es `NUR_IM_HAUSHALT_DES_NUTZERS` (nur `einmalig`): Dort gilt die
  Forderung auf dem Musterhaushalt nicht. Die Menge darf nur kürzer werden (siehe Abweichungen).
- **Gemessen (`pruefen --nur-zahlen`):** vorher „Gleich“, nachher 9 Unterschiede, `hauptbuch/` gleich: in `ableitung/`
  `hochrechnung_jahre`, `kontoprognose_12`, `kontoprognose_60`, in `seiten/` `ziele`, `hochrechnung`, `bestaende`,
  `start`, `monatsabschluss`, `konten`. Alles in der Jahresrechnung kommt aus dem Block `einmalig`: Die zwei Wegfall-Zeilen
  der aktiven Klammer wirken 2027 um gut zwei Prozent höher, 2030 um gut acht, danach weiter mit der Inflation; kein anderer
  Block bewegt sich. Der Endstand der Jahresrechnung steigt über die Kaskade um einige hundert Euro (2028) bis einige tausend
  (2035) und bis 2044 um rund zwei Prozent des Stands; das Ziel wird zwei bis drei Monate früher erreicht. Im Monatsmodell
  bewegen sich nur die Korrekturzeilen auf Zinsen eines Kontos um wenige Euro bis 08/2027.
- **Tests:** zwei neue in `tests/test_hochrechnung_takt.py`: Eine Wegfall-Zeile, die die ganze Reihe ersetzt, lässt in
  jedem Jahr null übrig, mit Inflation. Eine Planzeile mit demselben Betrag wie die Messung lässt nichts übrig; liegt ihr
  gesetzter Betrag zehn Prozent darüber, schrumpft der Rest mit jedem Jahr, weil die Messung steigt und der gesetzte Betrag
  nicht. Suite auf der Entwicklungskopie grün bis auf `test_referenz` (bis zum Neuschreiben der Referenz), auf dem
  Musterhaushalt ganz grün; `ruff` null Funde; `ZU_VERZWEIGT` nicht länger (`test_lint` grün). Vorlagen, Routen und
  Skripte sind nicht berührt, die Browsertests liefen nicht.

**E.2b-N abgenommen am 25.10.2026 (Opus), Referenz neu geschrieben.** `pruefen --nur-zahlen` zeigte neun Unterschiede, alle aus dem Block `einmalig` und aus den Korrekturzeilen auf Zinsen. `hauptbuch/` blieb gleich. Der Paritätstest und die neuen Tests sind auf beiden Datensätzen grün. Zu den Abweichungen:
1. **`/planung` zeigt das Gemessene flach:** lassen. „Je Monat noch übrig“ ist der Stand der Messung, keine Prognose. Schritt 6 kann es benennen.
2. **`NUR_IM_HAUSHALT_DES_NUTZERS`:** angenommen, bis der Haushalt die Wegfall-Zeile mit der großen Reihe geklärt hat. Die Menge darf nur kürzer werden und fällt mit dem Grund weg.
3. **Rest in `einmalig`, Korrekturzeilen auf Zinsen:** angenommen. Sie fallen mit der Klärung der Eingabe und mit E.6.

### E.2c Durchlaufende Konten (gewollt)

- Ausgaben über ein Konto mit der Rolle `durchlaufend` zählt das Monatsmodell
  auf dem Konto, das es deckt, wie die Jahresrechnung sie misst (Abnahme E.2,
  Nummer 3). Die Umbuchung, die das durchlaufende Konto ausgleicht, zählt nicht
  noch einmal.
- Der Grund „durchlaufendes Konto“ fällt aus `konsum` in `BEKANNT`.

**Umgesetzt am 25.10.2026, E.2c (Sonnet).** Die Beträge stehen in `notizen/E.2c_paritaet.md` und
`notizen/E.2c_pruefen_unterschiede.md` der Entwicklungskopie.
- **Woher das deckende Konto kommt:** Die App hält es nirgends fest (`forecast.yaml` kennt nur die Rolle `durchlaufend`,
  `accounts.yaml` nur eine Notiz). Es folgt aus den Umbuchungen im Hauptbuch: das Gegenkonto der letzten Umbuchung des
  durchlaufenden Kontos bis zum Stichtag (`konten.deckendes_konto`, `konten.deckung_zum`), in beide Richtungen gelesen und nur
  unter den Konten mit Kontoprognose. Ein neues Feld gibt es nicht. Ein durchlaufendes Konto ohne Umbuchung hat kein deckendes
  Konto; dann bleibt es wie vorher draußen. Die Zuordnung gilt je Stichtag, also auch im Treffer-Check zu seinem Monat.
- **Messung:** `messung.Ausschluss` hat statt der Menge `durchlaufend` die Paare `deckung` (durchlaufend, deckend). Die Messung führt
  die Teile eines durchlaufenden Kontos unter dem deckenden (`Monatssumme.konto`, `Teil.konto`), und die Auswahl `konten` meint die
  Konten nach dieser Zuordnung: Das durchlaufende Konto gibt es danach nicht mehr. Die Ausnahme der Regel „art“ (eine Umbuchung auf
  ein durchlaufendes Konto zählt als Ausgabe) ist gestrichen: Die Umbuchung, die das Konto ausgleicht, ist eine Umbuchung wie jede
  andere. Sie zählte in der Kopie ohnehin nirgends, weil `transfer/eigenkonto` in `exclude_from_recurring` steht; die Ausnahme war tot.
- **Monatsmodell:** `kontoprognose` und `reihen_vor` bauen `deckung` aus der Konfiguration und dem Hauptbuch; die Reihen mit Takt
  stehen dadurch ebenfalls auf dem deckenden Konto. Fenster, Verfahren und Steigerung sind die jedes anderen Postens. Das
  durchlaufende Konto selbst hat keine Posten (`abgeleitete_posten` gibt eine leere Liste) und erscheint wie bisher nicht in
  `household_accounts`. Eine Wegfall-Zeile auf eine Reihe des durchlaufenden Kontos gilt auf dem deckenden (`wegfall_posten`,
  `gedeckt`). Der Treffer-Check misst das Ist mit derselben Zuordnung wie das Soll, und die Prognosebasis auf `/annahmen` zählt
  das durchlaufende Konto nicht mehr daneben (`prognosebasis._konten_je_kategorie`), sonst stünde es doppelt da.
- **Texte:** `CONTEXT.md`: „Durchlaufendes Konto“.
- **Tests:** `tests/test_durchlaufend.py` belegt, dass die Summe der Posten aller Konten im Monatsmodell gleich der Messung der
  Jahresrechnung für diese Buchungen ist (Kategorie für Kategorie, auf den Cent), dass die Deckung nicht noch einmal zählt, dass das
  deckende Konto das der letzten Umbuchung ist und dass Soll und Ist des Treffer-Checks dasselbe Konto sehen. Auf dem Stand vor E.2c
  schlägt der Summentest an. `test_messung`, `test_abos`, `test_fortschreibung` und `test_kontoprognose_takt` rechnen mit `deckung`.
  Einige Tests mit kleiner Datenbank geben `reihen_vor` eine eigene Konfiguration (`fcfg={}`), weil die Kopie ein durchlaufendes
  Konto hat.
- **Paritätstest:** Der Grund „durchlaufendes Konto“ ist gestrichen. Der Musterhaushalt hat jetzt ein durchlaufendes Konto
  (`bezahldienst`, zwei runde Zahlungen im Monat, vom Alltagskonto gedeckt, Stand null). `konsum` fällt trotzdem nicht aus der Liste,
  auf keinem Datensatz: In der Kopie bleibt eine einzige Buchung eines Objekts mit Prognose, die die Jahresrechnung im Block `objekt`
  zählt (E.4), im Musterhaushalt zwei Reihen ohne Kategorie (E.8); beide hat das durchlaufende Konto bisher verdeckt. Beide stehen als
  Gründe da (siehe Abweichungen). Was je Block und Jahr vorher und nachher übrig ist: `notizen/E.2c_paritaet.md`.
- **Gemessen (`pruefen --nur-zahlen`):** vorher „Gleich“, nachher 10 Unterschiede, alle im Monatsmodell: `ableitung/` (Posten je Konto,
  Kontoprognose auf 12 und 60 Monate, Treffer-Check) und `seiten/` (`konten`, `annahmen`, `prognosebasis`, `start`, `bestaende`,
  `monatsabschluss`). `hauptbuch/`, die Jahresrechnung (`/ziele`, `/hochrechnung`, `/renten`) und `ableitung/prognosebasis.json` sind
  gleich. Der Jahreswert aller Posten über alle Konten ist vorher und nachher derselbe, keine Kategorie weicht ab: Die Posten des
  durchlaufenden Kontos sind ohne Rest auf das deckende Konto umgezogen. Größenordnung: Das deckende Konto liegt nach 12 Monaten
  um einige hundert Euro höher (nach 60 Monaten um gut tausend), sein Tiefpunkt um rund zweihundert Euro weniger tief; die
  Cashflow-Prognose des Haushalts steigt um rund zwanzig Euro im Monat, und ein Monat mehr von zwölf erreicht das Ziel. Die Richtung
  ist hier **die andere als erwartet**: Das durchlaufende Konto trägt in diesem Haushalt mehr Eingänge als Ausgaben, das Monatsmodell
  wird optimistischer, nicht pessimistischer (siehe Abweichungen). Die Zahlen je Seite stehen in
  `notizen/E.2c_pruefen_unterschiede.md`.
- **Tests (Läufe):** Suite auf der Entwicklungskopie und auf dem Musterhaushalt grün bis auf `test_referenz` (bis zum Neuschreiben der
  Referenz); `ruff` null Funde; `ZU_VERZWEIGT` unverändert. Vorlagen, Routen und Skripte sind nicht berührt, die Browsertests liefen
  nicht.

**E.2c abgenommen am 25.10.2026 (Opus), Referenz neu geschrieben.** `pruefen --nur-zahlen` zeigte zehn Unterschiede, alle im Monatsmodell. `hauptbuch/` und die Jahresrechnung blieben gleich. `test_durchlaufend` und der Paritätstest sind auf beiden Datensätzen grün. Zu den Abweichungen:
1. **Richtung:** zur Kenntnis. In diesem Haushalt trägt das durchlaufende Konto netto mehr Eingänge. Richtig ist es trotzdem.
2. **Teile ohne Kategorie:** Beide Modelle zählen sie, im Monatsmodell wie in der Jahresrechnung unter einem eigenen Schlüssel. Geld, das geflossen ist, gehört in die Prognose, auch wenn es noch keine Kategorie hat. Ein eigener kleiner Teilschritt **E.2e**.
3. **`fixkosten`:** angenommen. Den Rest beseitigt E.2d.
4. **Verträge und Planzeilen auf einem durchlaufenden Konto:** kommen zu E.2d. Sie zählen auf dem deckenden Konto.
5. **`/konten` nennt das durchlaufende Konto im Rechenweg nicht:** Schritt 6.

### E.2d Verträge (gewollt)

- Der Vorrat eines Vertrags gilt in beiden Modellen (Abnahme E.2b, Nummer 2).
- Mitzahler zählen in beiden über den Vertrag. Ihre Buchungen fallen aus der
  Messung.
- Eine gekündigte Reihe mit Wegfall-Zeile zählt in beiden an derselben Stelle.
- Ein Vertrag oder eine Planzeile auf einem durchlaufenden Konto zählt auf
  dem deckenden Konto (Abnahme E.2c, Nummer 4).
- Der Grund unter `fixkosten` in `BEKANNT` fällt.

**Umgesetzt am 25.10.2026, E.2d (Sonnet).** Die Beträge stehen in `notizen/E.2d_paritaet.md` und
`notizen/E.2d_pruefen_unterschiede.md` der Entwicklungskopie.
- **Eine Rechnung für Verträge:** Neu ist `forecast/vertraege.py` (`vertragsbetrag` und `police_vertraege` sind aus `konten.py`
  dorthin gezogen und dort weiter erreichbar, dazu `termine`, `pausen`, `aus_der_messung`, `rueckzahlungen`). Ein Vertrag zählt in
  beiden Modellen über seine Tatsachen: Betrag mit der Steigerung je Termin (`vertragsbetrag`), Termine aus `abos.termine`
  (herausgelöst aus `abos.posten`). Seine Buchungen messen beide nicht (`abos.ausschluesse`); die Jahresrechnung nimmt sie jetzt
  ebenfalls aus `ohne` (`jahre._vertraege_lesen`, `jahre.ohne_messung`) und zählt den Vertrag als Posten „<Name> (Vertrag)“ im Block
  seiner Kategorie (`jahre._vertragsposten`, neues Feld `Planzeilen.vertraege`). Ausgenommen sind die Verträge, die eine Police
  speisen (Beitrag nominal fest, Ende mit der Police) und Verträge, deren Kategorie in keinem Block der Basis steht: Sie bleiben
  gemessen, wie `_vertragsenden` sie kennt (`_vertragsenden` selbst ist unverändert; `_eingaben` nimmt nur die Verträge heraus,
  die über ihre Tatsachen zählen).
- **Punkt 1, Vorrat:** `abos.termine` kannte ihn schon; die Jahresrechnung zählt jetzt über dieselben Termine. Vorher zählte sie die
  Messung weiter.
- **Punkt 2, Mitzahler:** `abos.mitzahler` nennt die Zahlungen, die `abrechnung` einer Person eines Zeitraums zurechnet (von Hand oder
  automatisch). `abos.ausschluesse` nimmt sie mit aus der Messung, in beiden Modellen. Gezählt wird der offene Anteil
  (`abos.rueckzahlungen`), im Monatsmodell wie bisher, in der Jahresrechnung neu. Wer LAUFEND mitzahlt (`besetzung` mit `seit`),
  bleibt gemessen (siehe Abweichungen). Die Zahlungen der Mitzahler werden je Verbindung gemerkt, solange die Datenbank sich nicht
  ändert (`abos.mitzahler`); ohne das kostete `/konten` das Dreifache.
- **Punkt 3, Kündigung mit Wegfall-Zeile:** Es gilt der Weg über den Vertrag, in beiden. Die Kündigung am Vertrag beendet seine Termine.
  Eine eingeschaltete Wegfall-Zeile auf der Reihe eines Vertrags setzt ihn von ihrem Start bis zu ihrem Ende aus (`vertraege.pausen`,
  eine einmalige Zeile nur in ihrem Monat; Zeilen „nur Kontoprognose“ nicht). Ein Termin fällt weg, wenn eines von beidem ihn trifft,
  und zählt so nie zweimal. Was die Zeile über den Vertrag hinaus nennt und noch gemessen wird (der weiterlaufende Eingang eines
  Mitnutzers), zieht sie selbst ab: `szenarien.messung` hat dafür `ohne`, die Buchungen, die der Vertrag schon ersetzt. Im Monatsmodell
  tat `wegfall_posten` das schon, weil es mit und ohne die Reihe rechnet.
- **Punkt 4, durchlaufendes Konto:** `konten._vertragsposten`, die Rückzahlungen und `_planposten` zählen eine Zeile, deren Konto ein
  durchlaufendes ist, auf dem Konto, das es deckt (`gedeckt`); die Nur-Kontoprognose-Zeilen in `wegfall_posten` ebenso. In der Kopie
  gibt es keinen solchen Vertrag und keine solche Planzeile; belegt in `tests/test_vertraege.py` an `abos.posten` mit mehreren Konten.
- **Verschobener Einsammel-Monat:** Das Monatsmodell rief `rueckzahlungen` mit dem Stichtag als `ab` auf; ein verstrichener
  Einsammel-Monat rückte so in den Monat des Stichtags und fiel aus der Projektion, statt, wie der Docstring sagt, in den ersten
  Prognosemonat. Jetzt ist `ab` der erste offene Monat, in beiden Modellen. In der Kopie liegt kein solcher Fall.
- **Texte:** `CONTEXT.md` unter „Vertrag“. `prognosebasis.vergleich` (Seite „Prognosebasis“ auf `/annahmen`) misst die Jahresrechnung
  mit denselben ausgenommenen Buchungen; die Spalte „Differenz“ steht dort in jeder Kategorie mit Vertrag auf null.
- **Paritätstest:** `fixkosten` bleibt in `BEKANNT`, mit einem neuen Grund: Reihen mit Takt steigen im Monatsmodell an ihrem Termin, in
  der Jahresrechnung zur Jahresmitte (Abnahme E.2b, Nummer 3, gewollt, E.8). Der Rest ist ein bis zehn Euro im Jahr. Belegt: Ohne
  Inflation ist der Block auf zwei Cent gleich; mit Inflation und der Jahresmitte als Termin des Monatsmodells auf Rundung, in der Kopie
  und im Musterhaushalt (dort bleiben rund fünf Euro mit dem Termin, der Grund besteht also auf beiden). `einmalig` fällt aus
  `BEKANNT`, und `NUR_IM_HAUSHALT_DES_NUTZERS` entfällt (siehe Abweichungen). Der Musterhaushalt hatte Vorrat und Mitzahler schon
  (Office-Paket); eine Kündigung mit Wegfall-Zeile und einen Vertrag auf dem durchlaufenden Konto hat er nicht, sie stehen als
  Einheitentests in `tests/test_vertraege.py` (erfundene, runde Zahlen).
- **Gemessen (`pruefen --nur-zahlen`):** vorher „Gleich“, nachher 14 Unterschiede, `hauptbuch/` gleich. Jahresrechnung:
  `ableitung/hochrechnung_jahre`, `seiten/ziele`, `hochrechnung`; Monatsmodell: nur das Konto C24 (`ableitung/kontoprognose_12`, `_60`,
  `posten_je_konto`, `treffer`, `seiten/konten`, `start`, `bestaende`, `monatsabschluss`, `annahmen`); dazu `ableitung/prognosebasis` und
  `seiten/prognosebasis`. Größenordnung: `fixkosten` der Jahresrechnung im ersten vollen Jahr rund hundert Euro niedriger (Vorrat), danach
  200 bis 260 Euro höher im Jahr (die Eingänge der Mitzahler zählen nicht mehr als Reihe); `einmalig` der Jahresrechnung rund 270 Euro im
  Jahr niedriger; der Endstand 2044 sinkt um rund 1,4 Prozent. Im Monatsmodell verliert C24 die Eingänge der Mitzahler: rund 270 Euro Endstand
  nach 12 Monaten, rund 1.400 nach 60, was fast genau der Gewinn von E.2c war; die Cashflow-Prognose auf `/konten` sinkt um rund 23 Euro im
  Monat, „11 von 12“ wird „10 von 12 Monaten“. Jede Änderung folgt aus einem der vier Punkte (Punkt 2 für die Mitzahler, Punkt 1 und 3 für
  die Jahresrechnung).
- **Tests:** Suite auf der Entwicklungskopie grün bis auf `test_referenz` (bis zum Neuschreiben der Referenz), auf dem Musterhaushalt ganz
  grün; `ruff` null Funde; `ZU_VERZWEIGT` nicht länger. Neu: `tests/test_vertraege.py`. Vorlagen, Routen und Skripte sind nicht berührt,
  die Browsertests liefen nicht. Nach der Zwischenspeicherung der Mitzahler lief die Suite ohne die langsamen Tests noch einmal grün.

**E.2d abgenommen am 26.10.2026 (Opus), Referenz neu geschrieben.** `pruefen --nur-zahlen` zeigte 14 Unterschiede, in beiden Modellen, wie erwartet. `hauptbuch/` blieb gleich. `test_vertraege`, `test_abos` und der Paritätstest sind auf beiden Datensätzen grün. Zu den Abweichungen:
1. **Künftige und laufende Mitzahler:** Sie zählen in beiden Modellen als erwarteter Anteil je Termin des Vertrags, aus der Besetzung. Das gilt für einen Zeitraum, den der Haushalt noch nicht angelegt hat, und für jeden, der mit `seit` laufend mitzahlt. Ihre Buchungen fallen dann aus der Messung. Der Anteil gehört zum Vertrag; ihn wegzulassen wäre so falsch wie ihn zu messen. Ein Nachtrag **E.2d-N**.
2. **`einmalig` ist gleich:** gut. Die Frage an den Haushalt zur Wegfall-Zeile auf Audio-Streaming entfällt: Der Saldo war positiv, weil Mitnutzer dort mitzahlen.
3. **`fixkosten`, Reihen mit Takt am Termin:** Vorschlag angenommen. Der Test rechnet das Monatsmodell mit der Jahresmitte als Termin. Der Unterschied steht als gewollt in `DAUERHAFT`, mit dem Beleg aus diesem Bericht.
4. **Treffer-Check der Jahresbasis:** Er führt die Verträge als eigenen Posten. Das kommt zu E.8.
5. **`_vertragsenden` einengen:** kommt zu E.8, samt Tests.
6. **Wegfall auf einem Vertrag, Vertrag ohne Block der Basis:** angenommen.

**Umgesetzt am 26.10.2026, E.2d-N (Sonnet).** Die Beträge stehen in `notizen/E.2d-N_paritaet.md` und
`notizen/E.2d-N_pruefen_unterschiede.md` der Entwicklungskopie.
- **Punkt 1, erwarteter Anteil:** `abos.erwartete_anteile(abo, termin)` sagt, was die Besetzung den Mitzahlern an einem Termin zuordnet;
  `abos.zeitraum_am` sagt, ob ein angelegter Zeitraum den Termin deckt (von seinem Beginn bis zu seinem Ende, das Ende ausgenommen:
  `Zeitraum anlegen` setzt das Ende des einen als Beginn des nächsten; ein Zeitraum aus einem Monat deckt diesen Monat). Hat ein Termin
  einen Zeitraum, gilt wie bisher dessen offener Anteil, sonst der Anteil laut Besetzung, nie beides. Wer laufend mitzahlt (`seit`), zählt ab
  diesem Monat bei jedem Termin, außer ein Zeitraum nennt ihn. `vertraege.anteil_am_termin` steigert den Anteil wie den Betrag am Vertrag
  (`vertragsbetrag`; ein Policenbeitrag und ein Vertrag ohne Fenster bleiben flach). Die Jahresrechnung zählt ihn in `_vertragsposten`
  als eigenen Posten „<Name>: Anteil der Mitzahler“ im Block des Vertrags; das Monatsmodell in `konten._anteilsposten` als Eingang im Monat
  des Termins, ohne Tag (also nach den Kosten des Monats), unter dem Etikett `abo-anteil:<id>`. Termine, die eine Pause oder eine Kündigung
  trifft, haben keinen Anteil (dieselben Termine wie der Vertrag, `vertraege.termine`).
- **Punkt 2, Messung:** `abos.mitzahler` nennt jetzt auch, was `abos.laufend` einer laufenden Person zurechnet (von Hand oder automatisch).
  Damit nehmen `abos.ausschluesse` und `vertraege.aus_der_messung` es in beiden Modellen aus der Messung. Die Zahlungen werden mit
  Datum und Konto gemerkt (`abos._mitzahlungen`, wie bisher je Verbindung zwischengespeichert). Belegt in `tests/test_vertraege.py`: Über
  ein Jahr ergeben beide Modelle den Betrag am Vertrag minus die Anteile, auf den Cent gleich, auch durch `konten._vertragsposten` und
  `_anteilsposten` gerechnet.
- **Punkt 3, Konto:** `abos.eingangskonto` nennt das Konto der jüngsten Zahlung der Mitzahler. Das Monatsmodell bucht den Anteil dort, sonst
  auf dem Konto des Vertrags; ein durchlaufendes Konto zählt auf dem, das es deckt, und hat selbst nichts (wie seine übrigen Posten).
- **Punkt 4, Paritätstest:** Der Test rechnet das Monatsmodell ein zweites Mal, mit Reihen mit Takt (mehr als ein Monat, mit Steigerung)
  zur Jahresmitte (`_zur_jahresmitte`, ersetzt `RecurringItem.amount_in`), und vergleicht diese Rechnung. Den Unterschied zum Termin führt er unter
  `DAUERHAFT` als `reihen_mit_takt`, mit dem Grund „Reihen mit Takt steigen an ihrem Termin (gewollt, Abnahme E.2b, Nummer 3)“. `fixkosten` weicht
  danach um Rundung ab (wenige Cent im Jahr, vorher einige Euro) und fällt aus `BEKANNT`, auf der Kopie und im Musterhaushalt. `BEKANNT` hat
  danach: `gehalt`, `miete`, `objekt`, `immobilie`, `konsum`, `zinsen`. `DAUERHAFT`: `nur_kontoprognose`, `investment`, `reihen_mit_takt`.
- **Gemessen (`pruefen --nur-zahlen`):** vorher „Gleich“, nachher 13 Unterschiede, `hauptbuch/` gleich: Jahresrechnung `ableitung/hochrechnung_jahre`,
  `seiten/ziele`, `hochrechnung`; Monatsmodell `kontoprognose_12/_60`, `posten_je_konto`, `seiten/konten`, `start`, `bestaende`, `monatsabschluss`,
  `annahmen`; dazu `ableitung/prognosebasis` und `seiten/prognosebasis`. Jede Änderung folgt aus Punkt 1 bis 3. Die Anteile machen die Verträge mit
  Mitzahlern optimistischer, wie erwartet: die Jahresrechnung um einen Betrag in der Größe dessen, was E.2d an Eingängen entfernt hatte; das
  durchlaufende Konto und sein deckendes Konto (dasselbe, das E.2d belastet hatte) um einen Teil davon, weil ein Vertrag mit Vorrat bis zu
  einem späteren Termin davor keinen Anteil hat. **Insgesamt werden beide Modelle auf der Kopie aber pessimistischer** (Endstand der Jahresrechnung
  2044 um rund 0,3 Prozent, die Cashflow-Prognose auf `/konten` um einige Euro im Monat), weil die gemessene Reihe einer laufenden Mitzahlerin
  wegfällt (siehe Abweichungen).
- **Tests:** Suite auf der Entwicklungskopie grün bis auf `test_referenz` (bis zum Neuschreiben der Referenz), auf dem Musterhaushalt ganz grün;
  `ruff` null Funde; `ZU_VERZWEIGT` nicht länger (`_anzeigenamen` wurde dafür auf eine Schleife umgestellt). Neu in `tests/test_vertraege.py`:
  Zeitraum-Grenzen, Anteil nur für wen schon gezahlt hat, `seit`, Steigerung, Konto, durchlaufendes Konto, Pause, Jahresgleichheit. Vorlagen, Routen
  und Skripte sind nicht berührt (nur der Name eines Postens im Rechenweg), die Browsertests liefen nicht. `CONTEXT.md` unter „Vertrag“ ergänzt.

**E.2d-N abgenommen am 26.10.2026 (Opus), Referenz neu geschrieben.** `pruefen --nur-zahlen` zeigte 13 Unterschiede, alle aus den Punkten 1 bis 3. `hauptbuch/` blieb gleich. Der Paritätstest und `test_vertraege` sind auf beiden Datensätzen grün. Zu den Abweichungen:
1. **Nur wer schon gezahlt hat, zählt als Erwartung:** angenommen. Ein Anteil, den keine Buchung stützt, ist ein Vorhaben und gehört nicht in die Prognose.
2. **Die gemessene Reihe der laufenden Mitzahlerin fällt weg:** angenommen. Der höhere Betrag wird nicht mehr gezahlt.
3. **Das Ende eines Zeitraums ist ausgenommen:** bestätigt.
4. **Der Anteil zählt am Termin:** lassen. In diesem Haushalt ist der Unterschied ein Monat bei jährlichem Takt.
5. **Der Test rechnet das Monatsmodell zweimal:** angenommen.

**Eingabe des Haushalts danach (26.10.2026):** Die Reihe unter „Fixkosten Partner“ ist auf Angabe des Haushalts monatlich festgelegt. Opus hat das im echten Ordner eingetragen, in die Entwicklungskopie übernommen und die Referenz noch einmal neu geschrieben (`notizen/5b_partner_monatlich.txt`). Die Erstattung der Krankenversicherung kommt etwa einmal im Jahr, so wie die Prognose sie rechnet.

### E.2e Teile ohne Kategorie (gewollt)

- Das Monatsmodell zählt Teile ohne Kategorie, wie die Jahresrechnung
  (Abnahme E.2c, Nummer 2). Sie erscheinen in den Posten unter einem eigenen,
  sichtbaren Namen, nicht unter einem leeren.
- Der Grund „Teile ohne Kategorie“ fällt aus `BEKANNT`.

**Umgesetzt am 26.10.2026, E.2e (Haiku).** Das Monatsmodell rechnet mit dem Vorgabewert von `Ausschluss` (`ohne_kategorie=True`), also wie die Jahresrechnung. Der Posten mit leerer Kategorie heißt in `_anzeigenamen` (`finctl/forecast/konten.py`) „ohne Kategorie“. Der Grund „Teile ohne Kategorie“ ist aus `BEKANNT` unter `konsum` gestrichen, und der Test `test_fortschreibung` heißt nun `…counts_uncategorised_parts…`, weil er das alte Verhalten festschrieb.

- **Referenz:** `pruefen --nur-zahlen` ist auf der Entwicklungskopie vorher und nachher gleich. Die Kopie hat keine Teile ohne Kategorie im Messfenster, dort bewegt sich nichts. `hauptbuch/` und die Jahresrechnung sind gleich. Die Notiz steht in `notizen/E.2e_pruefen_unterschiede.md` der Entwicklungskopie.
- **Konsum bleibt in `BEKANNT`, mit dem Grund E.4.** Auf der Entwicklungskopie weicht `konsum` um einen kleinen Betrag je Jahr ab, den E.4 erklärt. Auf dem Musterhaushalt ist er gleich. Die Menge `NUR_IM_HAUSHALT_DES_NUTZERS = {"konsum"}` in `tests/test_paritaet.py` hält den Eintrag für den Musterhaushalt, wie für `einmalig` in E.2b-N. Sie darf nur kürzer werden und fällt mit E.4 weg.
- **Neuer Test:** `tests/test_ohne_kategorie.py` belegt auf erfundenen Daten, dass der Posten ohne Kategorie „ohne Kategorie“ heißt.
- **Läufe:** Die volle Suite ist auf der Entwicklungskopie grün (2408 bestanden, 47 übersprungen) und auf dem Musterhaushalt (2403 bestanden, 60 übersprungen). `test_lint.py` ist grün.

**E.2e abgenommen am 26.10.2026 (Opus).** In der Entwicklungskopie gibt es keine Teile ohne Kategorie, `pruefen` meldet deshalb weiter „Gleich“, und die Referenz bleibt. Im Musterhaushalt ist `konsum` jetzt gleich. In der Kopie bleibt der Block wegen E.4 in `BEKANNT`, dafür die Menge `NUR_IM_HAUSHALT_DES_NUTZERS` = {`konsum`}, entschieden von Opus. Sie darf nur kürzer werden und fällt mit E.4 weg. Der neue Test `tests/test_ohne_kategorie.py` fehlte im Commit, weil der Auftrag `git add` verbot. Opus hat ihn nachgereicht (`e7078c3`). Künftige Aufträge erlauben `git add` für neue Dateien.

### E.3 Gehalt (gewollt)

- Die Untergrenze in beiden Modellen, wachsend mit `gehalt_steigerung_pa` ab
  dem Basisjahr. In welchem Monat sie steigt, gilt in beiden gleich.
- Der Median steht nur noch als Vergleich, wo eine Seite ihn heute nennt.
- Die Jahresrechnung spart danach weniger. `/ziele` und `/hochrechnung`
  zeigen das, und der Bericht nennt es je Ziel.

**Umgesetzt am 26.10.2026, E.3 (Sonnet).** Beide Modelle rechnen mit der Gehaltsuntergrenze (`assumptions.salary_floor_cents`), und sie wächst in beiden mit `gehalt_steigerung_pa` zum 1. Januar nach dem Basisjahr.

- **Eine Regel:** `assumptions.gehalt_im_jahr` (Untergrenze, Jahr, Basisjahr, Rate). Im Basisjahr steht die Untergrenze, wie sie ist; vor dem Basisjahr steigt nichts. Das Basisjahr ist in beiden das Jahr des Tages nach dem Stichtag (`jahre.eingaben`: `folgetag(bis)`; `konten.account_forecast`: `as_of + 1 Tag`).
- **Jahresrechnung:** `jahre._salary` und `_gehaltsposten` nehmen die Untergrenze aus `Annahmen.gehalt_untergrenze_cents` statt des gemessenen Medians. `Eingaben.gehalt_median` und `gehalt_vorgabe_cents` entfallen. Die Rechenwegzeile „Gehalt“ nennt die Untergrenze und hat die Quelle `annahme`. Die Teilzeit (`_teilzeitposten`) rechnet von derselben Zahl wie bisher.
- **Monatsmodell:** `_income_overrides(fcfg, basisjahr)` setzt für `einkommen/gehalt` eine `engine.Untergrenze` (Wert, Basisjahr, Rate) statt einer flachen Zahl; `engine.override_in` liest sie je Monat, in `engine.project`, in `konten.wegfall_posten` und im Treffer-Check. Ein Override aus `forecast.yaml` bleibt eine gesetzte Zahl. Der Rechenweg des Gehalts auf `/konten` nennt Basisjahr und Steigerung.
- **Der Median** (`jahre.gehalt_median_cents`) steht nur noch auf `/annahmen`, mit dem Hinweis „nur zum Vergleich“; der Rückfallwert aus `assumptions.yaml` entfällt (`salary_median_cents` ist gestrichen). Berichtigt sind die Beschriftung der Gehalts-Untergrenze auf `/annahmen`, der Grund der Zeilen `einkommen/gehalt` und der Nebenkategorien in der Prognosebasis, der Text „Plan“ des Abgleichs (Soll Gehalt ist die Untergrenze), das Soll Gehalt im Treffer-Check und der Absatz zur Prognosebasis im Handbuch.
- **Wirkung:** Die Ursache „Gehalt“ entfällt (`wirkung._folge`, `GETAUSCHT`), weil nichts Gemessenes mehr in sie eingeht. `CONTEXT.md` nennt sie nicht mehr.
- **Paritätstest:** Der Grund „Untergrenze gegen Median; die Untergrenze steigt im Monatsmodell nicht“ ist aus `BEKANNT` unter `gehalt` gestrichen. Es bleibt die Nebentätigkeit (E.5), und die Differenz des Blocks ist genau sie: `einkommen/gehalt` ist in beiden Modellen auf den Cent gleich. Vorher und nachher in `notizen/E.3_paritaet.md`.
- **Referenz (`pruefen --nur-zahlen`):** vorher gleich; nachher 15 Unterschiede, alle aus dem Gehalt, `hauptbuch/` gleich. Die Unterschiede stehen in `notizen/E.3_pruefen_unterschiede.md`. Die Referenz ist nicht neu geschrieben.
  - **Jahresrechnung:** Das Gehalt ist rund 7 % tiefer (Untergrenze statt Median, der Abstand wächst mit dem Jahr). Die Endstände sind 2027 rund 5 %, 2035 rund 9 %, 2045 rund 9 % tiefer, am Ende der Rechnung knapp 10 %. Kein anderer Block ändert sich.
  - **`/ziele`, hochgerechnet:** Notgroschen rund 2 Prozentpunkte tiefer (82 % → 80 %); Barista Fire und Coast Fire je rund 10 % tiefer, rund 20 Prozentpunkte weniger (184 % → 164 %, 167 % → 149 %). Der Monat, in dem die Hochrechnung das Ziel erreicht (erster Monat auf der zwischen den Jahresenden verbundenen Linie): Notgroschen unverändert; Barista Fire und Coast Fire je rund 12 Monate später (Jüngst: 11). Die Rentenlücke, der Wendepunkt, Balken und Rate bleiben gleich: Sie rechnen ohne Gehalt oder mit dem heutigen Bestand.
  - **`/hochrechnung`, `/monatsabschluss` (Fortschritt), `/start`, `/bestaende`:** dieselben Werte. Die Wirkung im Monatsabschluss ändert keine Zahl.
  - **`/konten`, Cashflow ohne Objekt:** Das Betriebskonto nimmt ab 01/2027 jedes Jahr 2 % mehr Gehalt ein; davor ist jeder Monat gleich. Prognose Ø des Cashflows ohne Objekt steigt um rund 5 %.
  - **`/annahmen`, `/planung`, Treffer-Check, Abgleich:** Soll Gehalt ist die Untergrenze, ohne Rückgriff auf den Median; die Differenz der Zeile `einkommen/gehalt` in der Prognosebasis ist null.
- **Tests:** `test_the_page_names_a_reason_for_every_difference`, `test_wirkung` (Untergrenze gleich dem gebuchten Gehalt der erfundenen Haushalte, Ursache „Der Monat“ statt „Gehalt“), `test_stichtag_verlauf`, `test_jahre` und `test_web` (Beschriftung) sind auf die Untergrenze umgestellt; neu ist `test_the_salary_steps_up_on_the_first_of_january_after_the_base_year` (`test_assumptions.py`), und `test_the_floor_and_the_median_are_separate_figures` entfällt.
- **Läufe:** Die volle Suite ist auf der Entwicklungskopie grün (2402 bestanden, 47 übersprungen) und auf dem Musterhaushalt (2398 bestanden, 59 übersprungen), jeweils ohne `test_referenz`, das bis zum Neuschreiben der Referenz rot bleibt. Die Browsertests sind grün (52 bestanden, 4 übersprungen). `ruff` hat null Funde, `ZU_VERZWEIGT` ist nicht länger geworden.

**E.3 abgenommen am 26.10.2026 (Opus), Referenz neu geschrieben.** `pruefen --nur-zahlen` zeigte 15 Unterschiede, alle aus dem Gehalt. `hauptbuch/` blieb gleich. Der Paritätstest ist auf beiden Datensätzen grün, und `einkommen/gehalt` ist in beiden Modellen auf den Cent gleich. Zu den Abweichungen:
1. **`gehalt` in `NUR_IM_HAUSHALT_DES_NUTZERS`:** bestätigt. E.5 gibt dem Musterhaushalt eine Nebentätigkeit (Abnahme E.1, Nummer 3). Dann fällt der Block aus der Menge.
2. **Teilzeit im Monatsmodell:** lassen, solange sie außerhalb des Horizonts beginnt. E.8 bekommt einen Test, der anschlägt, sobald eine Teilzeit in den Horizont von `/konten` rückt. Dann wird sie dort als Abzug vom Gehalt gebucht.
3. **Ursache „Gehalt“ in der Wirkung entfällt:** bestätigt.
4. **Rentenlücke unverändert:** zur Kenntnis, die Erwartung im Plan war falsch.
5. **Soll Gehalt ist die Untergrenze:** bestätigt. „Plan“ ist, was die Rechnung nimmt.
6. **Notizen und `netto_median_monatlich_cents` in `assumptions.yaml`:** in E.8, mit dem Haushalt.
7. **`CHANGELOG.md`:** in E.8, für alle Teilschritte zusammen.

### E.4 Objektprognose im Monatsmodell (gewollt)

- Die Prognose eines Objekts wird im Monatsmodell zu datierten Posten je
  Monat, auf dem Konto aus E.0, mit Inflation und Saisonfaktoren wie in der
  Jahresrechnung.
- Die gemessenen Buchungen des Objekts zählen im Monatsmodell nicht mehr,
  dieselbe Abgrenzung wie in der Jahresrechnung.
- Ein Objekt ohne Prognose rechnet weiter gemessen.
- Fehlt das Konto am Objekt, braucht es ein Feld. Das entscheidet Opus nach
  E.0.

**Umgesetzt am 26.10.2026, E.4 (Sonnet).** Das Monatsmodell rechnet die Objektprognose, und beide Modelle rechnen sie aus **einer** Funktion.

- **Posten je Monat (1):** `finctl/forecast/objektposten.py` (neu) hat `betraege(prognose, monat, basisjahr, inflation, verkauf_ab)` und gibt Miete und Kosten eines Monats. Die Jahresrechnung (`jahre._objektposten`) summiert die Monate eines Jahres daraus, das Monatsmodell (`konten._objektposten`, aufgerufen in `account_forecast`) bucht Miete als Eingang (`objekt-miete:<id>`) und Kosten als Ausgang (`objekt-kosten:<id>`), je Monat von `ab` bis `bis`. Die Steigerung ist die der Jahresrechnung: stufenweise zum 1. Januar nach dem Basisjahr (das Jahr des Tages nach dem Stichtag). Die Posten tragen das Merkmal `Posten.objekt` (wie `umbuchung`); der Rechenweg auf `/konten` nennt Betrag, Steigerung, Laufzeit, Konto und dass die gemessenen Buchungen nicht mehr zählen.
- **Saison (2):** Beide Modelle rechnen mit der Kurve. Sie wirkt auf die **Miete**, nicht auf die Kosten (so beschreibt es die Notiz am Objekt: „Saisonalität der Mieten“). Die Miete eines Monats ist netto plus Kosten, damit Miete minus Kosten mit Kurve aus lauter 1,0 genau der alte Betrag ist. Belegt in `tests/test_objektposten.py`: eine Kurve ungleich 1 ergibt über ein Jahr in beiden Modellen dieselbe Summe, auch in einem Jahr, in dem die Vermietung erst beginnt (dort ändert die Kurve die Summe, in beiden gleich); dazu ein Lauf über den ganzen Haushalt.
- **Konto (3):** `konten.konto_des_objekts`: das Konto, auf dem die Miete des Objekts zuletzt gebucht wurde (`splits.property_id`, `immobilie/mieteinnahme`, bis zum Stichtag); ein durchlaufendes Konto zählt auf dem, das es deckt; gibt es keine Miete oder hat das Konto keine Prognose, das Betriebskonto. Ein Feld `prognose.konto` gibt es nicht: In der Kopie ist das Konto der Miete das Betriebskonto.
- **Abgrenzung (4):** `messung.Ausschluss.objekte`: Teile mit der Kennung eines Objekts mit Prognose fallen aus der Messung des Monatsmodells, in jeder Kategorie, auch aus den Reihen mit Takt (`reihen_vor`, `vorschau_konto`). Ein Objekt ohne Prognose bleibt gemessen. Im Treffer-Check der Konten (`treffer._ist_zaehlt`) zählt das Ist den Block `objekt` nicht mehr, sonst stünde dort gemessen, was das Soll nicht mehr fortschreibt.
- **Verkauf (5):** `jahre._objektposten` kennt den Monat des Verkaufs (aus `verkaeufe`) und das Monatsmodell auch (`konten._objektposten` ruft `jahre.verkaeufe`): ab dem Monat des Verkaufs kein Posten mehr. `jahre.rechnen` zieht für ein Objekt mit Prognose nichts mehr aus `miete` und `immobilie` ab. In der Kopie gibt es keinen Verkauf; belegt in `tests/test_objektposten.py` und `test_verkauf_plan`.
- **Cashflow ohne Objekt (6):** `ohne_objekt.zaehlt` lässt einen Posten mit `objekt` weg, auch ohne Klammer.
- **Paritätstest (7):** Aus `BEKANNT` sind die Gründe aus E.4 gestrichen; `miete`, `objekt`, `immobilie` und `konsum` fallen heraus. Es bleiben `gehalt` (E.5) und `zinsen` (E.6). `konsum` fällt auch aus `NUR_IM_HAUSHALT_DES_NUTZERS`; die Menge ist {`gehalt`} und nicht leer. Die vier Blöcke sind auf beiden Datensätzen gleich bis auf Rundung (unter 0,50 Euro im Jahr); `objekt` ist in der Kopie auf den Cent gleich. Vorher und nachher in `notizen/E.4_paritaet.md`. Der Test ordnet einen Posten mit `objekt` dem Block `objekt` zu.
- **Texte (8):** `/immobilie/<id>` sagt: „Wirkt in beiden Prognosen: Konten und Hochrechnung, statt der Messung.“ `/immobilien` hat keinen solchen Satz; dort ist nichts zu ändern. Das Handbuch (Abschnitt Immobilie) nennt beide Prognosen.
- **Referenz (`pruefen --nur-zahlen`):** vorher gleich; nachher 11 Unterschiede, alle im Monatsmodell. `hauptbuch/` und die Jahresrechnung (`/ziele`, `/hochrechnung`) sind gleich: Das Objekt hat keinen Verkauf, die Kurve steht auf lauter 1,0. Die Referenz ist nicht neu geschrieben. Die Unterschiede stehen in `notizen/E.4_pruefen_unterschiede.md`.
  - **`/konten`:** Das Konto der Miete bucht den Ertrag des Objekts bis zum Ende der Prognose. Seine Einnahmen 2027 steigen um rund 28 %, die Kosten um rund 18 %; vorher schrieb das Monatsmodell das Objekt mit einem Ertrag nahe null fort (eine Miete, vier Kostenbuchungen, durch zwölf). Das Tagesgeld bekommt in 60 Monaten rund 60 % mehr abgeräumt. Der tiefste Punkt dieses Kontos liegt rund zweieinhalbmal so tief: Kosten stehen undatiert am 1., die Miete am 28. (Abweichung unten). Zwei weitere Konten bewegen sich um die gemessenen Buchungen des Objekts, die dort nicht mehr zählen (Kosten 2027 rund 9 % geringer, Einnahmen 2027 rund 7 % geringer).
  - **Cashflow ohne Objekt, Konten-Signal:** Prognose Ø des Cashflows ohne Objekt steigt um rund 0,3 %. Das Signal (`/start`, `/bestaende`, `/monatsabschluss`): Die Warnung eines Kontos ist rund 23 % weniger tief, weil die gemessenen Kosten des Objekts dort nicht mehr fortgeschrieben werden.
  - **`/annahmen#prognosebasis`, Treffer-Check:** Die Zeilen des Objekts sinken im Monatsmodell um die Zwölftel seiner gemessenen Buchungen (Miete rund 11 %, Kosten rund 20 % der Zeile).
- **Läufe:** Die volle Suite ist auf der Entwicklungskopie grün (2422 bestanden, 47 übersprungen) und auf dem Musterhaushalt (2419 bestanden, 60 übersprungen), jeweils ohne `test_referenz`, das bis zum Neuschreiben der Referenz rot bleibt. `test_paket` war rot, bis die Kopie des Handbuchs im Paket nachgezogen war (`cp HANDBUCH.md finctl/HANDBUCH.md`); danach grün. Die Browsertests sind grün (52 bestanden, 4 übersprungen). `ruff` hat null Funde, `ZU_VERZWEIGT` ist nicht länger geworden. `household_accounts` braucht für zwölf Monate wie vorher rund 0,35 s.
- **Tests:** neu sind `tests/test_objektposten.py` (die Rechnung, Saison und Jahressumme in beiden Modellen, Verkauf, Konto der Miete, ein Lauf über den ganzen Haushalt mit Kurve, der Verkauf eines Objekts mit Prognose in der Jahresrechnung), je ein Fall in `test_messung.py` (`Ausschluss.objekte`) und `test_ohne_objekt.py`.

**E.4 abgenommen am 26.10.2026 (Opus), Referenz neu geschrieben.** `pruefen --nur-zahlen` zeigte elf Unterschiede, alle im Monatsmodell. `hauptbuch/` und die Jahresrechnung blieben gleich. `miete`, `objekt`, `immobilie` und `konsum` sind aus `BEKANNT`, und der Paritätstest ist auf beiden Datensätzen grün. Zu den Abweichungen:
1. **Die Saison wirkt auf die Miete:** bestätigt.
2. **`/immobilien` ohne Satz:** angenommen.
3. **Treffer-Check der Konten ohne Objekt:** lassen. Kommt zu E.8, zusammen mit dem Treffer-Check der Verträge (Abnahme E.2d, Nummer 4).
4. **Tiefpunkt des Betriebskontos:** Der Tag der Posten ist eine Eingabe und gehört zum Objekt. Ein Nachtrag **E.4-N** legt ihn fest. Die Miete fällt auf den Tag, an dem sie zuletzt gebucht wurde, die Kosten auf den mittleren Tag der gemessenen Kostenbuchungen des Objekts. Ohne Buchung gilt die Monatsmitte. Für ein knapp geführtes Betriebskonto zählt der Tag.
5. **Kein Feld `prognose.konto`:** angenommen.
6. **Objekt ohne Konto:** E.8 bekommt einen Hinweis auf `/konten`, wenn eine Objektprognose kein Konto findet.
7. **`jahre.verkaeufe` misst weiter:** E.8 räumt auf.
8. **Rundung:** angenommen.

**Umgesetzt am 26.10.2026, E.4-N (Haiku).** Die Objektposten im Monatsmodell tragen einen Tag (`konten.tage_des_objekts`, `konten._objektposten`). Das Objekt hat die Miete am 31. und die Kosten am 14. Die Engine kürzt einen Tag nicht selbst (sie sortiert nur danach), deshalb kürzt `_objektposten` ihn auf den letzten Tag des Monats. Der Tiefpunkt des Betriebskontos bewegt sich um 0,00 % in allen zwölf Monaten; Monatssummen und Warnmonate bleiben gleich. Der Grund: Der Tiefpunkt ist die Summe der Ausgaben bis zum ersten Eingang des Monats. Die Kosten liegen davor, die Miete danach, und der Tag der Kosten ändert daran nichts, solange er vor der Miete liegt. Der Nachtrag ändert auf diesem Haushalt also keine Zahl. Ob der Tiefpunkt so viel tiefer liegt wie vor E.4, ist nicht gemessen; das ist ein Befund für Opus. `pruefen --nur-zahlen` ist vorher und nachher gleich, die Referenz ist nicht neu geschrieben. Tests: vier neue Fälle in `tests/test_objektposten.py`; `test_objektposten`, `test_paritaet` und `test_lint` sind grün auf der Entwicklungskopie und mit `FINCTL_TESTDATEN=muster`; `-m "not langsam"` hat 1581 bestanden und 1 übersprungen, `test_referenz` eingeschlossen. Die Messung steht als `notizen/E.4-N_pruefen_unterschiede.md` im Datenordner.

**E.4-N abgenommen am 26.10.2026 (Opus).** `pruefen` meldet „Gleich“, die Referenz bleibt. Der Befund stimmt: Der Tiefpunkt eines Monats ist die Summe der Ausgaben bis zum ersten Eingang. Die Kosten des Objekts liegen vor der Miete am Monatsende, wie in Wirklichkeit. Der tiefere Tiefpunkt seit E.4 ist also echt: Das Betriebskonto trägt die Kosten des Objekts, bis die Miete kommt. Vorher verdünnte die Messung diese Kosten auf ein Zwölftel. Die Tage aus den Buchungen bleiben, denn sie sind richtiger als 1. und 28.

### E.5 Schenkung und Nebentätigkeit (gewollt)

- Die Planzeile „erwartete Einnahme“ mit Betrag, Monat und Takt, falls es
  sie noch nicht gibt. E.0 sagt, ob eine bestehende Zeile das schon kann.
- Zugeordnete Buchungen zählen in keiner Messung.
- Opus trägt die Zeilen in der Entwicklungskopie nach Angabe des Haushalts
  ein.
- Der Paritätstest zeigt, dass nichts doppelt zählt.

**Umgesetzt am 26.10.2026, E.5 (Sonnet).** Es gibt eine neue Art der Planzeile, die **erwartete Einnahme** (`art: erwartet`), und der Block `gehalt` zählt nur noch genau `einkommen/gehalt`.

- **Die Art (1):** Betrag (positiv), Takt (monatlich, quartalsweise, jährlich, einmalig), Start, optional Ende, Kategorie, Konto und zugeordnete Buchungen. Ihre zugeordneten Buchungen und alle Buchungen ihrer Reihe (`ledger.reihe.hashes`, dieselbe Definition wie beim Vertrag und beim Wegfall) fallen aus der Messung **beider** Modelle: `szenarien.erwartet_zugeordnet` liefert die Menge, `konten.erwartete_hashes` gibt sie an die Kontoprognose und an die Reihen (`_ausschluss_hashes`, `kontoprognose`), `jahre._eingaben` und `jahre.ohne_messung` an die Basis. Nur eingeschaltete Klammern zählen: Wer die Klammer ausschaltet, bekommt die Messung zurück. Die Zeile zählt in beiden Modellen **voll**, mit festem Betrag und ohne Steigerung (`restbetrag_je_termin`, `jahreswirkung`: kein Abzug des Gemessenen, auch bei einer einmaligen Zeile mit Buchungen). Die bestehenden Arten sind unverändert.
  - **Monatsmodell:** Die Zeile bucht als Planposten auf ihr Konto (`konten._planposten`); ohne Konto auf dem Betriebskonto, auf einem durchlaufenden auf dem Konto, das es deckt. Der Rechenweg nennt Betrag, Takt, Laufzeit, die Zahl der zugeordneten Buchungen und dass die Jahresrechnung dasselbe rechnet.
  - **Jahresrechnung:** `jahre._erwartete_posten` zählt die Zeile im Block ihrer Kategorie (`Planzeilen.erwartet_block`, gelesen in `_eingaben` mit `abgleich.block_der_kategorie`), nicht in `einmalig`. Ein Block, den die Rechnung nicht fortschreibt, fällt auf `einmalig` zurück.
  - **`/planung`:** Die Art „Erwartete Einnahme“ lässt sich anlegen, zeigen und bearbeiten (`_klammer.html`, `planung.html`, `routen/planung._planzeile`). Die Richtung steht fest auf Einnahme, ein Betrag unter null oder null wird abgelehnt. Das Feld für die zugeordneten Buchungen ist das schon vorhandene. Die Spalte „zählt“ sagt „ersetzt die Messung, die Zeile zählt voll“.
  - **Weitere Stellen, die die Messung kennen:** Das Ist des Treffer-Checks der Konten (`treffer._ist_je_konto`) zählt die ersetzten Buchungen nicht, sonst stünde dort gemessen, was das Soll nicht fortschreibt. Die Prognosebasis nennt den Grund „erwartete Einnahme in Planung …“ und zeigt die Zeile der Kategorie ohne `konten` und `jahr`. Der Abgleich auf `/planung` misst ohne die Buchungen. Die Warnung „mehr als ein Plan gleichzeitig an“ (`monatsabschluss`) zählt eine Klammer, die nur aus erwarteten Einnahmen besteht (`Scenario.nur_erwartet`), nicht mit.
- **Block `gehalt` (2):** `abgleich.bloecke` ordnet nur noch `einkommen/gehalt` dem Block `gehalt` zu. Eine Unterkategorie wie `einkommen/gehalt-nebentaetig` zählt unter `einkommen_sonst`, in beiden Modellen. Die Zeile „Gehalt“ in der Prognosebasis rechnet im Block die Untergrenze; der Grund „nur die Untergrenze von einkommen/gehalt“ entfällt.
- **Die Zeilen in der Entwicklungskopie (3):** in der neuen aktiven Klammer „Erwartete Einnahmen“, geschrieben über `/api/szenario-zeile` und `/api/szenario-zeile-buchungen` (mit dem `TestClient` der App, nicht von Hand). „Schenkung“ (`einkommen/schenkung`, monatlich ab 2026-10) und „Nebentätigkeit“ (`einkommen/gehalt-nebentaetig`, jährlich ab 2027-06), beide ohne Ende, auf dem Konto der jüngsten Buchung ihrer Kategorie (beide dasselbe Giro), mit allen 4 bzw. 5 Buchungen ihrer Kategorie im Hauptbuch. Die Beträge stehen in `notizen/E.5_pruefen_unterschiede.md`. Der Schreiber der App hat `szenarien.yaml` dabei in seinem Format neu geschrieben (Kopf und Einrückung); inhaltlich ist nur die neue Klammer dazugekommen.
- **Musterhaushalt (4):** eine Schenkung (vierteljährlich 600 €) und eine Nebentätigkeit (ein Honorar von 1.200 € im Juli), je mit Regel (`rules.yaml`) und Buchungen im Konto `giro`, dazu die aktive Klammer „Erwartete Einnahmen“ mit je einer Zeile `erwartet` (Takt quartalsweise und jährlich; `bauen.py` ordnet nach dem Einlesen alle Buchungen der beiden Kategorien zu). Der Block `einkommen_sonst` ist damit im Musterhaushalt belegt.
- **Paritätstest (5):** Aus `BEKANNT` ist der Grund unter `gehalt` gestrichen; der Eintrag fällt ganz heraus. Der Grund unter `einkommen_sonst` (Schenkung) war seit E.2 schon gestrichen. `NUR_IM_HAUSHALT_DES_NUTZERS` war {`gehalt`} und ist leer: die Menge ist entfernt. Es bleibt `zinsen` (E.6). Neu ist `test_an_expected_income_counts_once_in_both_models`: Je volles Jahr zählt die Zeile in beiden Modellen genau ihren Betrag (auf den Cent, ohne Steigerung), und die Messung ihrer Kategorie steht in keinem der beiden noch einmal da. Er schlägt an, wenn die Hashes nicht ausgeschlossen werden (geprüft). Der Test ordnet eine erwartete Einnahme dem Block ihrer Kategorie zu. `gehalt` und `einkommen_sonst` sind auf beiden Datensätzen gleich bis auf Rundung (unter 0,50 € im Jahr). Vorher und nachher in `notizen/E.5_paritaet.md`.
- **Abwahl (6):** `prognosebasis_custom.yaml` gibt es in der Entwicklungskopie nicht (und nach E.0, Nummer 12 auch im echten Ordner nicht): Die Schenkung ist nirgends abgewählt, die Abwahl entfällt nicht erst, sie fehlt. Ein Ordner, der sie abgewählt hat, hätte sie nach E.5 überflüssig: Die Kategorie ist ersetzt und die Zeile zählt. Nichts geändert.
- **Referenz (`pruefen --nur-zahlen`):** vorher gleich.
  - **Nach dem Code, ohne die Zeilen:** 13 Unterschiede, alle aus dem Block `gehalt`. Das Monatsmodell bleibt gleich (es hat die Nebentätigkeit schon als Reihe gebucht). In der Jahresrechnung fehlte sie bisher ganz, jetzt zählt sie als gemessene Reihe in `einkommen_sonst`: der Block ist rund 25 % größer, die Endstände rund 1,4 % (2027) bis 3,7 % (2089) höher. `/ziele`: Barista Fire und Coast Fire zum Stichtag der Ziele je rund 3 % höher (164 → 169 %, 174 → 179 %).
  - **Mit den Zeilen:** 19 Unterschiede, `hauptbuch/` gleich. Beide Modelle zählen die Einnahme als Zeile mit festem Betrag statt als Messung mit Steigerung. Im Monatsmodell bewegt sich nur das Konto der Zeilen: Einnahmen in zwölf Monaten rund 0,08 % niedriger, Tiefpunkt und Endstand gleich. Jahresrechnung: `einkommen_sonst` 2027 rund 22 % größer als in der Referenz, 2030 rund 16 %, 2045 rund 13 % kleiner, 2089 rund 60 % kleiner (die Messung steigt mit der Inflation, die Zeile nicht); Endstände 2027 rund 1 % höher, 2045 rund 0,7 % höher, 2089 rund 1,4 % niedriger. `/ziele`: Barista Fire und Coast Fire je rund 2 Prozentpunkte höher, die Rentenlücke 2062 von 100 % auf 96 % Deckung. Die Unterschiede stehen in `notizen/E.5_pruefen_unterschiede.md`; es ist keiner dabei, den die eine Eingabe nicht erklärt. Die Referenz ist nicht neu geschrieben.
- **Läufe:** Die volle Suite ist auf der Entwicklungskopie grün (2447 bestanden, 47 übersprungen) und auf dem Musterhaushalt (2443 bestanden, 60 übersprungen), jeweils ohne `test_referenz`, das bis zum Neuschreiben der Referenz rot bleibt. Die Browsertests sind grün (mit einem neuen Test für die Art: Richtung fest auf Einnahme, Betrag positiv gespeichert). `ruff` hat null Funde, `ZU_VERZWEIGT` ist nicht länger geworden (`_herkunft_planzeile`, `routen/planung._planzeile` und `_Zuordnung.von` im Paritätstest blieben darunter, indem ich sie geteilt habe). Der Abschnitt `/planung` im Handbuch stand bei 198 von 200 Wörtern; die Art steht jetzt dort, dafür fehlt das Beispiel mit dem neuen Auto. `CONTEXT.md` führt den Begriff „Erwartete Einnahme“.
- **Tests:** neu ist `tests/test_erwartet.py` (die Art in beiden Rechnungen, jeder Takt, Ende, die ersetzte Messung samt Reihe, ausgeschaltete Klammer, der Block `gehalt`, die Seite einschließlich der Ablehnung eines Betrags unter null); geändert sind `test_paritaet` und der Musterhaushalt.

**E.5 abgenommen am 26.10.2026 (Opus), Referenz neu geschrieben.** `pruefen --nur-zahlen` zeigte 19 Unterschiede, alle aus dem Block `gehalt` und den beiden Zeilen. `hauptbuch/` blieb gleich. `test_erwartet` und der Paritätstest sind auf beiden Datensätzen grün. `BEKANNT` hat nur noch `zinsen`. Zu den Abweichungen:
1. **Keine Abwahl der Schenkung:** zur Kenntnis.
2. **Die Nebentätigkeit fehlte in der Jahresrechnung:** zur Kenntnis, behoben.
3. **Feste Beträge ohne Steigerung:** lassen. Der Haushalt hat „gleicher Betrag“ gesagt.
4. **Eine ausgeschaltete Klammer gibt die Messung zurück:** bestätigt.
5. **Klammern aus erwarteten Einnahmen zählen nicht in die Warnung „mehr als ein Plan“:** bestätigt.
6. **Treffer-Check der Jahresbasis:** kommt zu E.8, mit den übrigen Punkten zum Treffer-Check.
7. **Karte „Gehalt“ auf der Startseite:** angleichen auf genau `einkommen/gehalt`, in E.8.
8. **`szenarien.yaml` im Format der App:** zur Kenntnis.
9. **`tests/referenz.py`:** angenommen.

**Im echten Ordner noch nicht eingetragen:** die beiden Zeilen „Erwartete Einnahmen“. Die installierte App ist älter als E.5 und kennt die Art `erwartet` nicht. Opus trägt sie ein, sobald die App aus dem Stand nach 5b neu gebaut ist.

**Eingabe des Haushalts danach (26.10.2026):** Zinssätze 2,6 % für das Tagesgeld bei Scalable und 2,5 % bei Trade Republic, ab 10/2026. Opus hat sie im echten Ordner über `/api/zinssatz` eingetragen, in die Entwicklungskopie übernommen und die Referenz noch einmal neu geschrieben (`notizen/5b_zinssaetze.txt`). Fünf Unterschiede, alle in der Jahresrechnung, denn nur sie rechnet bisher mit den Sätzen.

### E.6 Zinsen aus dem Kontostand (gewollt)

- Das Monatsmodell rechnet Zins und Steuer je Monat aus dem
  vorausgerechneten Stand, nach Entscheidung 4.
- Die gemessene Zinskategorie zählt nicht mehr.
- Der Bericht nennt die Korrekturzeilen in Planung, die überflüssig werden.

**Umgesetzt am 26.10.2026, E.6 (Sonnet).** Das Monatsmodell rechnet Zins und Steuer je Monat aus dem Stand des Kontos, in `engine.project`, `forecast/zinsen.py` und `forecast/konten.py`. Die Jahresrechnung ändert sich nicht.

- **Zins je Monat (1):** `zinsen.zins_im_monat` gibt `round(Stand × Satz ÷ 12)` auf den **Stand zu Monatsbeginn** des Kontos; `engine.project` bucht ihn am Monatsende (Tag 28) unter `einkommen/zinsen`. Der Satz ist `zinsen.satz_im_monat`, dieselbe Funktion wie in der Jahresrechnung. Stand zu Monatsbeginn folgt der Jahresrechnung (sie verzinst den Anfangsbestand, nicht den Zufluss des Jahres): Was das Abräumen im Monat bringt, verdient erst vom Folgemonat an. Ein Konto im Minus verdient nichts und zahlt auch nichts, wie in der Jahresrechnung. Leert eine Klammer das Konto, sinkt der Zins von selbst (Test `test_a_balance_that_a_clause_empties_earns_less_from_that_month_on`). Der Rechenweg auf `/konten` nennt Stand, Satz und dass die Jahresrechnung dasselbe rechnet.
- **Art des Kontos (2):** `konten._art_des_kontos` liest `kind` aus `balances.yaml`, wie `ziele.tagesgeld_je_konto`. `accounts.account_type` bleibt für das Einlesen. Ein Konto ohne Eintrag in den Zinssätzen und ohne die Art Tagesgeld verdient nichts.
- **Steuer (3):** Eine Funktion für beide Modelle: `zinsen.steuer_auf` (aus `jahre._steuer_auf`; dort bleibt der Name als Verweis). Der Zähler ist `zinsen.steuerplan`: Die Zinsen aller Konten laufen Monat für Monat in einen Zähler je Kalenderjahr; die Steuer ist `steuer_auf(Zähler, Pauschbetrag, Satz)` minus die schon gezahlte, und jedes Konto zahlt seinen Anteil an den Zinsen des Monats. **Wann im Jahr sie fällt:** erst in dem Monat, in dem die Zinsen seit Januar den Sparerpauschbetrag übersteigen, und danach mit jedem Monat. Im ersten Jahr der Projektion gilt der Pauschbetrag anteilig nach den Restmonaten (`zinsen.freibetrag_im_jahr`), wie in der Jahresrechnung. Weil die Steuer den Stand und damit den Zins des Folgemonats mindert, rechnet `household_accounts` neu, bis der Plan zu den Zinsen passt (höchstens dreimal; ohne Steuer einmal), und ein Konto allein (`account_forecast` ohne `steuer`) tut es mit seinen eigenen Zinsen. Über ein volles Jahr ist die Steuer die der Jahresrechnung: `tests/test_zinsen_paritaet.py` (Fälle: unter und über dem Pauschbetrag, wechselnder Satz, zwei Konten mit verschiedenem Satz, erstes Jahr mit Restmonaten) vergleicht `engine.project` mit `zinsen.steuerplan` gegen `jahre.kaskade` bei gleichem Stand und Satz: Zins bis sechs Cent, Steuer bis zwei Cent. Dazu `test_the_allowance_is_one_for_the_household_and_not_one_per_account` und `test_the_tax_falls_when_the_interest_of_the_year_pass_the_allowance`.
- **Gemessene Zinsen (4):** `GERECHNET` (jetzt in `zinsen.py`, `jahre.GERECHNET` ist derselbe Wert) steht in `kontoprognose` in `exclude`, auch für Reihen mit Takt. Das Ist des Treffer-Checks der Konten zählt sie nicht mehr (`treffer._ist_zaehlt`), sonst stünde dort gemessen, was das Soll nicht fortschreibt.
- **Korrekturzeilen (5):** Die Kopie hat in der Klammer „Korrektur Forecast“ zwei Betragszeilen (Zinsen und Kapitalertragsteuer des Tagesgelds, monatlich bis 08/2027) und eine Wegfall-Zeile (Kapitalertragsteuer eines Girokontos, nur Kontoprognose). Alle drei sind überflüssig; ich habe sie nicht geändert. **Sie gelten nach E.6 in keinem Modell mehr:** Die Jahresrechnung wertete sie schon nicht aus (`gilt_in_hochrechnung`), und `konten._planposten` überspringt jetzt jede Zeile auf einer gerechneten Kategorie. Ließe das Monatsmodell sie stehen, zöge die Zeile auf die Zinsen bis 08/2027 ein Mehrfaches des gerechneten Zinses ab. Die Wegfall-Zeile bucht ohnehin nichts (die Reihe, die sie nimmt, wird nicht mehr gemessen). Der Haushalt kann alle drei löschen.
- **Paritätstest (6):** `zinsen` ist aus `BEKANNT` und aus `BLOECKE` heraus und steht in `DAUERHAFT` mit dem Grund „die Jahresrechnung verzinst den Topf nach der Kaskade; der Stand ist ihr Ergebnis, keine Eingabe“. `BEKANNT` ist eine leere Tabelle (`{}`); der Test, dass sie nur kürzer wird, bleibt. Was vorher und nachher übrig ist, steht in `notizen/E.6_paritaet.md`: Außer `zinsen` weicht kein Block ab, auf beiden Datensätzen. Neu ist `tests/test_zinsen_paritaet.py` (14 Tests, davon zwei am Haushalt der Daten: Der Zins eines Monats ist Stand zu Monatsbeginn mal Satz mit der Art aus `kind`, und die Jahressteuer ist die Steuer auf die Jahressumme).
- **Texte (7):** `/planung` sagt an einer Zeile auf Zinsen oder Kapitalertragsteuer „zählt in keiner Prognose; /konten und die Hochrechnung rechnen …“, `/annahmen` ebenso, die Prognosebasis nennt als Grund „beide Rechnungen: nicht fortgeschrieben, gerechnet“, das Handbuch (`/annahmen`) ist berichtigt. Die Namen `gilt_in_hochrechnung` und `ohne_wirkung_in_hochrechnung` sind geblieben.
- **Referenz (`pruefen --nur-zahlen`):** vorher gleich. Nachher 11 Unterschiede, `hauptbuch/` gleich und die Jahresrechnung unverändert (`hochrechnung_*`, `/ziele`, `/hochrechnung`). Alle im Monatsmodell, alle durch die eine Eingabe erklärt (`notizen/E.6_pruefen_unterschiede.md`):
  - `/konten`: Das Tagesgeld verdient in den ersten zwölf Monaten rund 57 % weniger Zins als gemessen, ohne Steuer und ohne die Korrekturzeilen; ein Girokonto mit Satz verdient fast nichts mehr, weil es im Minus liegt. Betriebskonto und die übrigen Konten bewegen sich nicht.
  - Cashflow ohne Objekt (`/monatsabschluss`, Startseite): Prognose Ø +3,6 % (rund 50 € im Monat); Konten-Signal: der Tiefpunkt eines Girokontos im Minus rund 13 % tiefer.
  - `/annahmen#prognosebasis`: Summe Konten im Monat −3,4 % (Zinsen und Steuer fallen aus der Spalte); Treffer-Check der Konten ohne Zinsen und Steuer im Ist.
- **Läufe:** Volle Suite auf der Entwicklungskopie und auf dem Musterhaushalt grün, jeweils ohne `test_referenz`; `ruff` null Funde; `ZU_VERZWEIGT` ist nicht länger geworden (`project` 15 → 13, `account_forecast` 12 → 11, der Eintrag `household_accounts` heißt jetzt `_haushalt` mit demselben Wert 18, weil die Funktion mit der Schleife um den Plan jetzt `household_accounts` heißt). Vorlagen geändert (zwei Hinweise), Browsertests grün.

**E.6 abgenommen am 26.10.2026 (Opus), Referenz neu geschrieben.** `pruefen --nur-zahlen` zeigte elf Unterschiede, alle im Monatsmodell. `hauptbuch/` und die Jahresrechnung blieben gleich. `test_zinsen_paritaet` und der Paritätstest sind auf beiden Datensätzen grün. `BEKANNT` ist leer, und `zinsen` steht in `DAUERHAFT`. Zu den Abweichungen:
1. **Korrekturzeilen gelten in keinem Modell:** bestätigt. Opus legt dem Haushalt vor, die drei Zeilen zu löschen. Im echten Ordner geschieht das erst, wenn die App nach 5b neu gebaut ist, denn die alte App rechnet sie noch.
2. **Treffer-Check der Konten ohne Zinsen:** bestätigt. Er kommt mit den übrigen Punkten zum Treffer-Check in E.8.
3. **Bis zu drei Läufe:** lassen. Die Seiten bleiben gleich schnell.
4. **Betriebskonto unverändert, Konto nur in den Zinssätzen, keine Vorabpauschale, Pauschbetrag im ersten Jahr, ein Konto allein:** zur Kenntnis.
5. **Namen `gilt_in_hochrechnung` und `ohne_wirkung_in_hochrechnung`:** werden in E.8 umbenannt.
6. **`ZU_VERZWEIGT`:** Der Eintrag ist umbenannt, nicht neu, mit demselben Wert. Angenommen.

### E.7 Kurzfristige Ziele und Notgroschen (gewollt)

- „Hochgerechnet“ auf `/ziele` für Ziele im Horizont von `/konten` aus dem
  Monatsmodell, nach Entscheidung 7.
- Die Grenze des Notgroschens wird Untergrenze seines Kontos, nach
  Entscheidung 8.
- Ein Browsertest: Eine Klammer mit einer Ausgabe vor dem Stichtag
  verschiebt die Karte eines kurzfristigen Ziels.

**Umgesetzt am 26.10.2026, E.7 (Sonnet).** Alle drei Punkte stehen, die Jahresrechnung ändert sich nicht. Beträge und Konten stehen in `notizen/E.7_pruefen_unterschiede.md` der Entwicklungskopie.

- **Kurzfristige Ziele (1):** Neu `forecast/ziel_monat.py` (gehört dem Modul Ziele). `ziel_monat.messen` gibt den Wert eines Ziels und das Modell, das ihn misst. Ein Ziel mit Stichtag nach dem Start der Prognose und bis zum Ende ihres letzten Monats (60 Monate, `HORIZONT_MONATE`) misst das Monatsmodell: der Stand seiner Basiskonten am Ende des letzten Monats, der bis zum Stichtag zu Ende ist (liegt noch kein Monat dahinter, der Anfangsstand), mit den aktiven Klammern. Der Notgroschen geht ab wie in `ziele.hochgerechnet`: nur bei einem Ziel, das das Tagesgeld zählt und nicht selbst der Notgroschen ist. Das Monatsmodell rechnet erst, wenn ein Ziel es braucht (`ziel_monat.Lauf`), einmal je Seite. Balken und Rate bleiben beim heutigen Bestand. `/ziele` und die Fortschrittskarte auf `/monatsabschluss` rufen dieselbe Funktion. Die Karte sagt „Monatsmodell“ und „vorausgerechnet zum …“ mit Verweis auf `/konten`; die Fortschrittskarte hängt „(Monatsmodell)“ an. Das Tempo „Jüngst“ gibt es dort nicht (nur die Jahresrechnung kennt es), seine zweite Zeile entfällt.
- **Mischbasis (Opus, 26.10.2026: B bestätigt):** Gehört zur Basis etwas, das das Monatsmodell nicht projiziert (Depot, Krypto, Police, ein Konto ohne Auszüge, die Basis „alles Liquide“ mit solchen Positionen), bleibt das **ganze Ziel in der Jahresrechnung** (Vorschlag B). Ein Depotstand, unverzinst fortgeschrieben und zum Monatsmodell addiert, wäre eine Zahl, die keine der Rechnungen so rechnet (A). Die Karte sagt in diesem Fall „Jahresrechnung“ (vor dem Tempo), beim Monatsmodell „Monatsmodell“. Ein Ziel dieser Art gibt es weder in der Entwicklungskopie noch im Musterhaushalt (`test_a_basis_the_monthly_model_does_not_project_stays_with_the_yearly_model`).
- **Notgroschen (2):** Neu `forecast/notgroschen.py` (gehört der Prognose). Die Grenze (`puffer_cents`, `PUFFER_ZIEL`, die Vorgabe von drei Gehalts-Untergrenzen) ist dorthin gezogen, weil die Prognose das Modul Ziele nicht importieren darf (`finctl/module.py`); `forecast/ziele.py` nimmt die Namen von dort, sie heißen weiter gleich. Das Konto des Notgroschens ist das Konto der Bestandsart Tagesgeld in `balances.yaml`, bei mehreren das, auf das das Betriebskonto abräumt, sonst keines. `konten._untergrenze` nimmt die höhere von Kontoregel und Notgroschen (für `account_forecast` und das Auffüllen). Ist das Modul Ziele aus, gilt keine Grenze. Die Karte auf `/konten` zeigt weiter die Untergrenze der Regel (`regel_untergrenze_cents`), damit Speichern ohne Änderung die Grenze des Notgroschens nicht in `forecast.yaml` schreibt; die Tabelle nennt unter dem Wert „Notgroschen“, die Statuszeile der Karte sagt es. Die Kaskade der Jahresrechnung ist unverändert.
- **Anfangsstand (3):** `cli._bestaende_spiegeln` löscht alle `manual`-Zeilen und schreibt jede Position mit Betrag, die ein Konto der Tabelle `accounts` ist, unter ihrem eigenen Datum (sonst dem der Datei). `bestaende.auszugsstaende` nimmt für ein Konto mit Auszügen, aber ohne importierten Auszug den jüngsten Stand bis zum Stichtag aus `balance_snapshots` (Datum und Betrag, `auszug_bis` leer); das Monatsmodell tat es schon (`account_forecast`). Ein Stand nach dem Stichtag zählt in keinem der beiden; ein Konto mit Auszug ignoriert den getippten Stand. Belegt an einer erfundenen Datenbank (`test_an_account_without_a_statement_takes_the_latest_stand_up_to_the_cutoff_in_both_models` und zwei weitere). In der Entwicklungskopie wirkt es bei keinem Konto: Die eine neue Zeile gehört zu einem Konto ohne Auszug, das das Monatsmodell nicht projiziert und dessen Stand nach dem Stichtag liegt.
- **Paritätstest (4):** `BEKANNT` ist leer geblieben. Der neue Test `tests/test_ziel_monat.py::test_a_short_goal_is_the_sum_of_its_accounts_in_the_monthly_model` rechnet für jedes kurzfristige Ziel die Summe der Basiskonten aus den Zeilen von `household_accounts` nach (mit dem Abzug des Notgroschens) und vergleicht sie mit `ziel_monat.messen`. Dazu Tests für Horizont, Stichtagsregel, Mischbasis, Notgroschenabzug, Konto und Höhe der Untergrenze und ein Browsertest: Eine Klammer mit einer Ausgabe von 1.000 in dem Monat vor dem Stichtag verschiebt die Karte um diese Ausgabe (mit dem Zins darauf als Rest).
- **Referenz (`pruefen --nur-zahlen`):** vorher gleich. Nachher drei Unterschiede, alle durch E.7 erklärt:
  - `hauptbuch/balance_snapshots.json`: eine neue Zeile (ein Krypto-Konto ohne Auszug, getippter Stand mit eigenem Datum); alle anderen Dateien in `hauptbuch/` gleich.
  - `/konten`: Untergrenze des Tagesgeldkontos von 0 auf die Grenze des Notgroschens; Monate unter der Grenze in den ersten zwölf von 1 auf 10. Tiefpunkte und alle anderen Konten gleich.
  - `/ziele`: nur der Notgroschen (Stichtag im Horizont). „Hochgerechnet“ steigt von rund 80 % auf rund 106 % seines Betrags. Die Ziele mit Stichtag 2044 messen weiter die Jahresrechnung und bleiben gleich.
  - Nicht bewegt, anders als der Plan erwartet: die Fortschrittskarte auf `/monatsabschluss` (sie zeigt das Ziel von 2044) und das Konten-Signal (es nennt das Konto mit dem tiefsten Tiefpunkt, und das ist ein Girokonto).
- **Läufe:** Volle Suite auf der Entwicklungskopie (2468 bestanden, 47 übersprungen) und auf dem Musterhaushalt (2464, 59 übersprungen) grün, jeweils ohne `test_referenz`; Browsertests (54 bestanden, 4 übersprungen); `ruff` null Funde; `ZU_VERZWEIGT` nicht länger geworden. Vorlagen geändert (`konten.html`, `ziele.html`), Handbuch ergänzt (`/konten`, `/ziele`).

**E.7 abgenommen am 26.10.2026 (Opus), Referenz neu geschrieben.** `pruefen --nur-zahlen` zeigte drei Unterschiede: eine Zeile in `hauptbuch/balance_snapshots.json`, das Konto des Notgroschens auf `/konten` und den Notgroschen auf `/ziele`. `test_ziel_monat` und der Paritätstest sind auf beiden Datensätzen grün. Zu den Abweichungen:
1. **Mischbasis:** B ist bestätigt (Opus an die Sitzung, 26.10.2026).
2. **Notgroschen als Untergrenze eines Kontos:** bestätigt, als Näherung. Sie ist etwas vorsichtiger als die Summe des Topfs, denn das Betriebskonto wird bewusst knapp geführt. Die Warnung in zehn von zwölf Monaten ist gemeint: Die Klammer des Objekts greift den Notgroschen an.
3. **Auffüllen bis zur Grenze:** angenommen.
4. **Wirkung bei einem Ziel im Monatsmodell:** in E.8. Die Wirkung zeigt dort keine Zerlegung der Jahresrechnung, sondern sagt, dass das Monatsmodell misst, und verweist auf `/konten`.
5. **Stichtag mitten im Monat, Verlauf nicht gespiegelt, Seite der Bestände:** lassen.

### E.8 Abschluss (gleich)

- Die Liste bekannter Unterschiede im Paritätstest ist leer, bis auf die
  Kaskade.
- Seiten, die erklärten, warum `/konten` und `/hochrechnung`
  auseinanderlaufen, verlieren diese Erklärung. Zuerst
  `/prognosebasis`; den Text erneuert Schritt 6.
- `CONTEXT.md` bekommt die Begriffe, die sich geklärt haben (etwa „erwartete
  Einnahme“).

**Zusammengetragen für E.8 (Opus, 26.10.2026)**, aus den Abnahmen von E.2d bis E.7:
- *Code, gleich in den Zahlen außer wo genannt:*
  - Treffer-Check: Er führt Verträge und Objektposten als eigene Posten. Die Jahresbasis misst ohne die Buchungen, die ein Vertrag oder eine erwartete Einnahme ersetzt.
  - `_vertragsenden` auf die Verträge einer Police einengen, samt Tests.
  - `jahre.verkaeufe`: Für ein Objekt mit Prognose misst es nichts mehr.
  - Hinweis auf `/konten`, wenn eine Objektprognose kein Konto findet.
  - Ein Test, der anschlägt, sobald eine Teilzeit in den Horizont von `/konten` rückt.
  - Die Karte „Gehalt“ auf der Startseite summiert genau `einkommen/gehalt`. Das ändert eine Zahl auf der Startseite.
  - `gilt_in_hochrechnung` und `ohne_wirkung_in_hochrechnung` umbenennen, so dass die Namen sagen, dass eine Zeile in keiner Prognose zählt.
  - Die Wirkung bei einem Ziel im Monatsmodell (Abnahme E.7, Nummer 4).
- *Doku:*
  - Seiten, die erklärten, warum die Modelle auseinanderlaufen, verlieren diese Erklärung.
  - `CONTEXT.md` prüfen.
  - `CHANGELOG.md` unter „Unveröffentlicht“ erklärt in Worten des Haushalts, was sich mit 5b an seinen Zahlen ändert.
- *Mit dem Haushalt, durch Opus:*
  - die App aus `main` neu bauen;
  - die erwarteten Einnahmen und die Löschung der drei Korrekturzeilen in den echten Ordner;
  - die toten Schlüssel aus `forecast.yaml`;
  - `netto_median_monatlich_cents` und die Notizen zum Median in `assumptions.yaml`.

**Entscheidungen des Haushalts, 27.10.2026:**
1. **Die drei Korrekturzeilen** werden gelöscht, nachdem die App neu gebaut ist.
2. **Die toten Schlüssel** in `forecast.yaml` und der Median in `assumptions.yaml` werden entfernt.
3. **Der Notgroschen bleibt, wie er ist.** Die Warnung auf dem Tagesgeld bleibt stehen, weil die Monate um die Klammer des Objekts tatsächlich knapp waren.
4. **Die Schenkung kommt nicht monatlich.** Sie ist eine erwartete Einnahme mit Takt jährlich, gebucht im Januar, mit der Jahressumme als Betrag. Das gilt für den echten Ordner und genauso für die Entwicklungskopie. In der Kopie ändert das die Referenz, deshalb ist es ein eigener Schritt von Opus nach E.8b.
5. **Die Nebentätigkeit** bleibt jährlich ab Juni 2027.
6. **Nachgereicht wird im Regelprozess:** Auszüge und Mitteilungen der Policen kommen über den Monatsabschluss, ohne Programmierung. Es fehlt nur ein Hinweis für eine Buchung, die doppelt zählt (`docs/Neufassung_plan.md`, Schritt 6).

### E.8a Aufräumen im Code

Umgesetzt (Sonnet 5.5, 27.10.2026); Doku, CHANGELOG, Startkarte „Gehalt“ und Wirkung folgen in E.8b.

1. **Treffer-Check** (`forecast/treffer.py`):
   - Neuer Posten `vertraege` (Spalte „Verträge“) in der Jahresbasis und je Konto. Soll: die Termine der Verträge mit Betrag und Steigerung wie die Modelle, dazu der erwartete Anteil der Mitzahler (`vertraege.anteil_am_termin`). Ist: die Buchungen, die der Vertrag ersetzt (Reihe und Zahlungen der Mitzahler), als Unterschied der Messung mit und ohne sie.
   - Die Jahresbasis misst Soll und Ist ohne diese Buchungen und ohne die einer erwarteten Einnahme, wie `jahre._eingaben`. Die Nebentätigkeit steht damit in keinem Block des Checks mehr.
   - Das Soll `objekt` der Jahresbasis rechnet wie die Jahresrechnung (`objektposten.netto`: Saison, Ende, Verkauf).
   - Wo ein angelegter Zeitraum einen Termin deckt, zählt das Soll den vereinbarten Anteil seiner Personen (auf die Termine des Zeitraums verteilt, `treffer._zeitraumanteil`), nie den offenen Rest; das Ist hat ihre Zahlungen. Soll und Ist zählen damit dasselbe (Opus, 27.10.2026).
   - Der Check der Konten führt Vertrag und Objekt je Konto als eigene Posten (`KontoMonat.vertrag_*`, `objekt_*`; im Tooltip der Seite). Das Objekt hat jetzt ein Soll (`konten._objektposten`) und ein Ist (alle Buchungen des Objekts, auch vor `ab`). Zinsen und Steuer bleiben, wie E.6 sie festgelegt hat.
   - `konten()` ist in die Klasse `_Konten` zerlegt und steht nicht mehr in `ZU_VERZWEIGT`.
2. **`_vertragsenden`** rechnet nur für Verträge einer Police (`police_vertraege`); der Filter in `_eingaben` entfällt. Die Tests übergeben die Police und prüfen, dass ein gewöhnlicher Vertrag nicht gemessen wird.
3. **`jahre.verkaeufe`** misst für ein Objekt mit Prognose nichts mehr (`_miete_und_kosten_messen`).
4. **Hinweis auf `/konten`** (`konten.objekte_ohne_konto`, `div.note` in der Vorlage), mit Tests.
5. **Test `tests/test_teilzeit_horizont.py`**: schlägt an, sobald eine Teilzeit (auch einer ausgeschalteten Klammer, auch aus den Annahmen) innerhalb der 60 Monate von `/konten` beginnt, und nennt den Grund.
6. **Umbenannt**: `zaehlt_in_prognose` und `ohne_wirkung_in_prognose`. Kein Verhalten geändert.

**Was sich im Treffer-Check ändert:** `pruefen --nur-zahlen` vorher gleich, nachher drei Unterschiede, alle im Treffer-Check (`ableitung/treffer`, `/annahmen#prognosebasis` und seine Zahlenebene). Der Block `fixkosten` verliert die Verträge (Soll wie Ist) und steht deutlich niedriger; die Verträge stehen als eigene Spalte. `einkommen_sonst` verliert im Soll die Nebentätigkeit und im Ist die erwartete Einnahme. Das Soll des Objekts und der Konten ändert sich nur, wo eine Saison oder ein Objekt auf einem Konto liegt. Keine andere Seite ändert sich (kein Unterschied in `/konten`, `/hochrechnung`, `/ziele`, `/monatsabschluss`). Die Datei steht unter `notizen/E.8a_pruefen_unterschiede.md` im Datenordner der Entwicklungskopie. Die Referenz ist nicht neu geschrieben.

**Tests (27.10.2026, nach der Änderung des Mitzahler-Anteils nochmals; Browsertests nicht wiederholt, keine Vorlage oder Route geändert):** Suite auf der Entwicklungskopie 2480 grün, 2 rot; Musterhaushalt 2476 grün, 1 rot; Browsertests 54 grün, 4 übersprungen. Rot sind (a) `test_referenz` auf der Kopie, wie erwartet: Der Treffer-Check weicht von der Referenz ab, Opus schreibt sie neu; (b) `test_paket::test_the_shipped_handbook_is_the_one_that_is_maintained` auf beiden: `HANDBUCH.md` und `finctl/HANDBUCH.md` sind verschieden, schon vor E.8a (diese Sitzung hat das Handbuch nicht angefasst). → Opus: von Opus selbst angeglichen (7ba3993). Seitdem rot auf beiden Läufen: `test_design::test_a_handbook_section_stays_shorter_than_the_page_it_explains` (Abschnitte `konten` 226 und `ziele` 224 Wörter, Grenze 200); die Texte stammen nicht aus E.8a.

**E.8a abgenommen am 27.10.2026 (Opus), Referenz neu geschrieben.** `pruefen` zeigte fünf Unterschiede, alle im Treffer-Check: `ableitung/treffer.json` und die Seiten `/annahmen` und `/prognosebasis`, jeweils mit Zahlen und Text. Die neue Spalte heißt „Verträge“. Die Ausgabe liegt in `notizen/E.8a_referenz_vor_neuschreiben.txt`. Zu den Abweichungen:
1. **Ist des Vertrags mit den Zeiträumen der Mitzahler:** Das Soll nimmt jetzt den vereinbarten Anteil eines angelegten Zeitraums mit (`8626885`). Soll und Ist zählen damit dasselbe.
2. **Der Zweig ohne Police in `_vertragsenden`:** bestätigt, er bleibt für den Randfall.
3. **Keine Pausen im Check, Ist des Objekts je Konto, Name der Spalte:** angenommen.
4. **Zwei rote Tests am Handbuch:** Beide kamen aus E.7. Diese Sitzung hat das Handbuch nicht angefasst. Bei der Abnahme von E.7 habe ich sie übersehen. Opus hat die Wurzel an die Kopie angeglichen (`7ba3993`) und die Abschnitte `konten` und `ziele` unter 200 Wörter gekürzt.
5. **`abos.termine` in einem langen Fenster vor `faellig`:** Heute ist keine Zahl betroffen. Die Korrektur ist für Schritt 8 notiert (`docs/Neufassung_plan.md`).

### E.8b Wirkung, Startkarte, Doku

Umgesetzt (Sonnet 5.5, 27.10.2026). Die Zahlen und der Text der Vergleiche stehen in `notizen/E.8b_pruefen_unterschiede.md` der Entwicklungskopie.

1. **Karte „Gehalt“** (`routen/start.py`, `_kacheln`): summiert genau `einkommen/gehalt`, nicht mehr `einkommen/gehalt%`. Die Nebentätigkeit zählt nicht mehr zum Gehalt. Die Karte steht als Kachel im Monatsabschluss („davon Gehalt“ bei den Einnahmen, „% vom Gehalt“ bei den Ausgaben) und auf `/bestaende`. Test `test_the_salary_card_counts_exactly_the_salary_category` in `tests/test_erwartet.py`.
2. **Wirkung bei einem Ziel im Monatsmodell:**
   - `ziel_monat.misst_das_monatsmodell` sagt, ob das Monatsmodell ein Ziel misst (Stichtag im Horizont und die ganze Basis dort projiziert); `ziel_monat.messen` ruft sie auf, damit beide dieselbe Antwort geben.
   - `wirkung.vergleichen` fragt sie für jedes Ziel. `wirkung.Messung` bekommt die Kennungen (`monatsmodell`) und rechnet für sie nichts in der Jahresrechnung: Wert null, keine Ursachen, keine Tauschrechnung. `ZielWirkung` hat dazu `modell` und `im_monatsmodell`.
   - Auf `/monatsabschluss`, „Wirkung auf deine Ziele“, steht in beiden Tempo-Zellen „Monatsmodell“. Die Zeile klappt auf und sagt in einem Satz, dass das Monatsmodell das Ziel misst, mit Link auf Konten. Der Bestand-Balken bleibt. Der Satz steht einmal in `monatsabschluss.html`, als `div.note` im `{% if %}`, unter 40 Wörtern.
   - Tests: `test_a_goal_the_monthly_model_measures_has_no_causes_of_the_yearly_model` und `test_a_goal_the_yearly_model_measures_keeps_its_causes` (`tests/test_wirkung.py`), `test_a_goal_the_monthly_model_measures_says_so_and_points_to_konten` (`tests/test_wirkung_seite.py`, auf der Seite).
3. **Erklärungen des Auseinanderlaufens:** Gesucht wurde in den Vorlagen, den Texten der Routen, dem Handbuch und `design_conventions.yaml` nach „auseinander“, „nur in der Jahresrechnung“, „nur im Monatsmodell“, „anders als“, „Unterschied“, „verschieden“, „Median“ und „sechs Monate“.
   - `forecast/prognosebasis.py`, Kopf und `vergleich`: der Satz „was die beiden noch trennt …“ und „warum beide verschieden sind“ entfallen; die Seite zeigt je Kategorie die Messung, beide Werte und die Quelle.
   - `routen/annahmen._prognosebasis`: Docstring ohne „Grund jeder Differenz“.
   - `HANDBUCH.md` und `finctl/HANDBUCH.md` (identisch), `/annahmen`: Der Absatz zur Prognosebasis nannte, worin sich beide Rechnungen unterscheiden (Termin gegen Jahressumme). Er nennt jetzt, was beide fortschreiben. Dazu ein Satz, was verschieden bleibt: nur, was die Hochrechnung allein kennt (Kaskade, Rendite, Teilzeit, Verkauf, Ruhestand), und die Regeln der Konten.
   - `docs/design_conventions.yaml`, Regel `rechenweg-zu-jeder-prognose`: Der Satz „worin sich /konten und die Jahresrechnung unterscheiden, steht je Kategorie …“ verweist jetzt auf `DAUERHAFT` im Paritätstest.
   - Geblieben und erklärt: Kaskade, Rendite, Teilzeit, Verkauf (`_klammer.html`: „nur Jahresrechnung“), „nur Kontoprognose“ (Planung), Verkauf-Hinweis auf `/konten`, die Gründe der Prognosebasis „in forecast.yaml ausgeschlossen“, „gleiche Basis … rundet je Konto“ und die Zeilen „beide Rechnungen: …“. Die Rechenwege, die schreiben „die Jahresrechnung rechnet dasselbe“, sagen Gleichheit und bleiben.
   - Kein gerenderter Text einer Seite hat sich damit geändert; die Referenz zeigt daher in Teil 3 keinen Textunterschied.
4. **`CONTEXT.md`:** neu **Monatsmodell**, **Jahresrechnung**, **Messfenster** (mit der Zwölfmonatssumme), **Mitzahler**, **Objektprognose**, **Notgroschen**. Berichtigt: **Durchlaufendes Konto** (hat keine eigene Prognose), **Vertrag** (die Mitzahler stehen jetzt in einem eigenen Eintrag), **Objekt** (Objektprognose statt Ertragsprognose), **Kontoprognose** und **Hochrechnung** (die Seite zeigt, das Modell rechnet; „Jahresrechnung“ steht nicht mehr unter _Avoid_), **Fortschreibung**, **Verfahren** (Zwölfmonatssumme des Messfensters), **Wirkung** (ein Ziel im Monatsmodell wird nicht zerlegt), **Erwartete Einnahme** (ohne „Block“, gehört nicht zum Gehalt), **Ziel** (welches Modell misst).
5. **`CHANGELOG.md`**, „Unveröffentlicht“: sieben Einträge (Konten und Hochrechnung aus denselben Eingaben; Gehalt; erwartete Einnahme; Zinsen und Steuer; Objekt, Verträge, durchlaufende Konten; Notgroschen und kurzfristige Ziele; Treffer-Check mit der Spalte „Verträge“) und ein Eintrag „Nach dem Update tun“ (Korrekturzeilen auf Zinsen und Kapitalertragsteuer löschen, Schenkung und Nebentätigkeit als erwartete Einnahme anlegen, Zinssätze eintragen, einmalige Ausgaben markieren, die toten Schlüssel in `forecast.yaml`). Grundlage: `git log v0.4.1..HEAD`, die Abnahmen E.2 bis E.8a.

6. **Nachtrag (Opus-Auftrag 27.10.2026): Prognosebasis zählt in beiden Spalten, was die Rechnungen zählen** (`forecast/prognosebasis.py`):
   - `_ersetzt` rechnet die zwölf Monate ab dem ersten offenen, zu Preisen der Messung, aus den Tatsachen beider Rechnungen: Verträge (`vertraege.termine`, `vertragsbetrag`, `anteil_am_termin`, Pausen, offene Rückzahlungen), erwartete Einnahmen (Zeile voll) und Objektprognosen (`objektposten.netto`). `_plus_ersetztes` legt das zu dem, was von der Messung bleibt; die Messung der ersetzten Buchungen steht nicht mehr da. Der Beitrag in eine Police zählt in Konten als Vertrag (nominal, ohne Ende) und in der Jahresrechnung als gemessen, wie `vertraege.police_vertraege` es sagt.
   - Die Messung eines Objekts mit Prognose (Block `objekt`) zeigt in beiden Spalten nichts; das Objekt steht als eigene Zeile „… (Objektprognose)“. Teile ohne Kategorie zählt Konten unter dem leeren Namen, wie die Jahresrechnung.
   - Berichtigt: der Grund „auf /konten als Vertrag mit Termin“ heißt jetzt „Vertrag mit Termin in beiden Rechnungen, nicht aus der Messung“; der Grund beim Objekt „ersetzt durch die Objektprognose“. Neu: Feld `dauerhaft` je Zeile (nur eine Regel in `forecast.yaml` `exclude_from_recurring`, die nur Konten kennt).
   - Test `test_the_two_columns_differ_only_by_rounding_or_by_a_kontenregel` (`tests/test_prognosebasis.py`): kein Delta über `RUNDUNG_CENTS` ohne `dauerhaft`, Summen bis auf Rundung gleich, Objekt-Messung leer. Grün auf der Kopie und auf dem Musterhaushalt (dort belegte er zuerst zwei Abweichungen: Teile ohne Kategorie und die Police mit erstem Termin im Fenster). Die Summen im Kopf: vorher stark verschieden, nachher 1 Cent.
   - Referenz: dazu `ableitung/prognosebasis.json`, `/annahmen` und `/prognosebasis` mit Zahlen und Text (Spalten, Summen, Zeile des Objekts, Gründe); 6 Unterschiede nur Zahlen, 11 mit Text. Die Zahlen stehen im Nachtrag von `notizen/E.8b_pruefen_unterschiede.md`. `vergleich` blieb unter der Schwelle von `ZU_VERZWEIGT` (zwei Hilfsfunktionen). Handbuch (`/annahmen`) und `CHANGELOG.md` sagen es.
   - Läufe: Kopie 2486 grün, 1 rot (`test_referenz`); Musterhaushalt 2482 grün; Browsertests 54 grün, 4 übersprungen; `ruff` null Funde.

**Was sich in der Referenz ändert:** `pruefen --nur-zahlen` vorher Gleich, nachher drei Unterschiede, alle dieselbe Kachel auf `/start`, `/monatsabschluss` und `/bestaende`: „davon Gehalt“ und der Anteil vom Gehalt an den Ausgaben. Die Differenz ist die Nebentätigkeit des Jahres. `pruefen` mit Text: sechs Unterschiede (je Seite einmal Zahlen und einmal Text), dieselbe Kachel, sonst nichts. Die Wirkung bewegt sich in der Kopie nicht, denn sie hat keinen Verlauf: Die Seite zeigt statt der Tabelle den Satz „kein Stand zum Stichtag“. Die Referenz ist nicht neu geschrieben.

**Läufe:** Suite auf der Entwicklungskopie 2485 grün, 1 rot (`test_referenz`, wie erwartet); Musterhaushalt 2481 grün, 60 übersprungen; Browsertests 54 grün, 4 übersprungen; `ruff` und `ZU_VERZWEIGT` über `test_lint` grün.

**E.8b abgenommen am 01.11.2026 (Opus), Referenz neu geschrieben.** `pruefen` zeigte elf Unterschiede: `ableitung/prognosebasis.json`, `/annahmen` und `/prognosebasis` (beide Spalten zählen die Posten, die Summen sind bis auf Rundung gleich), dazu die Kachel „Gehalt“ auf `/start`, `/monatsabschluss` und `/bestaende`. Die Ausgabe liegt in `notizen/E.8b_referenz_vor_neuschreiben.txt`. Abweichung 1 ist behoben (`201e7e7`), 2 bis 4 sind angenommen. Damit ist 5b im Code abgeschlossen. Offen sind nur noch die Schritte mit dem Haushalt (oben).

**Fertig wenn** (je Teilschritt E.2 bis E.7):
- Der Paritätstest ist grün, und seine Liste ist um den Block des
  Teilschritts kürzer.
- `pruefen --nur-zahlen` zeigt Unterschiede nur dort, wo die eine Eingabe
  wirkt. Der Bericht erklärt sie und legt die Unterschiede als Datei in
  `notizen/`.
- Beide Läufe der Suite und die Browsertests, wenn Vorlagen, Routen oder
  Skripte sich ändern.

## Gefundene Abweichungen

(Hier trägt jede Sitzung ein, was nicht in den Plan passt.)

- **E.8b, Prognosebasis zeigte in der Spalte „Jahresrechnung“ nicht immer die Rechnung.** Behoben im Nachtrag oben (Punkt 6), auf Auftrag von Opus noch in 5b. → Opus: Ein Delta in der Tabelle hat jetzt nur noch Rundung oder eine Regel, die nur Konten kennt, als Grund; die Police läuft in Konten ohne Ende (die Police regelt es), und eine Kündigung oder ein Vorrat eines gewöhnlichen Vertrags im Fenster steht in beiden Spalten.
- **E.8b, Wirkung hat in der Kopie keine Anschauung.** Ohne `verlauf` in `balances.yaml` zeigt die Seite keine Tabelle, die Referenz sieht die neue Zeile also nicht; belegt ist sie durch die Tests mit einem Verlauf aus den heutigen Ständen. → Opus: zur Kenntnis. Die Zelle sagt in beiden Tempi „Monatsmodell“ ohne Zahl, auch im Tempo „Jüngst“, das das Monatsmodell nicht kennt.
- **E.8b, `wirkung.vergleichen` entscheidet mit dem Monatsmodell der Standardkonfiguration.** `ziel_monat.Lauf(conn)` liest die Klammern aus `szenarien.yaml`, nicht den Pfad `szenarien=`, den ein Aufrufer an `vergleichen` übergibt. Die Entscheidung, welches Modell ein Ziel misst, hängt nur von Horizont und Basis ab, nicht von den Klammern; die Zahlen der Ursachen nehmen den Pfad weiter. → Opus: zur Kenntnis.
- **E.8b, `CONTEXT.md` hat jetzt zwei Namen für dieselbe Seite:** „Kontoprognose“ und „Monatsmodell“, „Hochrechnung“ und „Jahresrechnung“. Ich habe die Seiten-Namen behalten und die Rechnungen dazugestellt, statt umzubenennen. → Opus: bestätigen oder zusammenlegen.

- **E.0, Steigerung ist eine Eingabe, die in keinem Teilschritt steht.** Das Monatsmodell steigert
  abgeleitete Posten stufenweise ab dem Start der Projektion, die Jahresrechnung stetig ab der Mitte des
  Messfensters. Bei gleicher Eingabe ist jeder gemessene Block der Jahresrechnung dadurch um genau die
  Inflation eines Jahres größer (1,02 bei 2 %), in jedem Jahr gleich. Dazu kommen Verträge, die das
  Monatsmodell nominal bucht und die Jahresrechnung mit der Inflation fortschreibt. Ohne Angleichung
  bleibt die Liste bekannter Unterschiede für alle gemessenen Blöcke bestehen, und E.8 („leer bis auf die
  Kaskade“) ist nicht erreichbar; eine prozentuale Toleranz deckte Fehler zu. → Opus: Angleichung in E.2
  mitnehmen oder als eigenen Teilschritt, und festlegen, welche Steigerung gilt (Vorschlag: die der
  Jahresrechnung) und ob Verträge mitsteigen.
- **E.0, E.4 verlangt Saisonfaktoren „wie in der Jahresrechnung“; die Jahresrechnung benutzt sie nicht.**
  `objekte.Prognose.saison` wird gelesen und auf 12 geprüft, aber `jahre._objekt` und `_objektposten`
  lesen es nirgends (Tests prüfen nur die Prüfung). Alle Kurven der Kopie und des Musterhaushalts sind 1,0.
  → Opus: in E.4 in beiden Modellen mit der Kurve rechnen (ändert die Jahresrechnung nur im Basisjahr mit
  Restmonaten und bei einer Kurve ungleich 1) oder das Feld streichen.
- **E.0, E.2: Divisor je Konto gegen Haushalt.** `fortschreibung._fenstermonate` zählt die Monate eines
  Kontos ab seinem ersten Auszug; die Jahresrechnung teilt alle Konten durch `f.monate`. Bei sechs Monaten
  und einem Konto, das jünger ist, fällt das nicht auf; bei zwölf schon, und die Summe über die Konten ist
  dann nicht die Zahl der Jahresrechnung (Entscheidung 6 verlangt genau das). → Opus: Vorschlag
  `f.monate` des Haushalts für jedes Konto (Folge siehe E.0 Ergebnis).
- **E.0, E.5: Eine laufende Planzeile mit zugeordneten Buchungen ersetzt die Messung nicht.** Heute zählt sie
  den Rest (Plan minus Gemessenes), die Messung bleibt in der Basis; nur bei einer einmaligen Zeile gehen die
  Buchungen aus der Basis, und dann zählt die Zeile null und nur in der Jahresrechnung
  (`szenarien.einmalig_zugeordnet` kennt das Monatsmodell nicht, heute ohne Wirkung, weil die Kategorie das
  Merkmal „einmalig“ trägt). Entscheidung 3 verlangt „ersetzt“. → Opus: eine neue Art (Vorschlag „erwartete
  Einnahme“) mit dem Verhalten „zugeordnete Buchungen fallen aus beiden Messungen, die Zeile zählt voll“;
  die bestehenden Arten bleiben, wie sie sind.
- **E.0, E.5: Der Block `gehalt` schluckt jede Unterkategorie.** `abgleich.bloecke` ordnet
  `einkommen/gehalt%` dem Block `gehalt` zu, den die Jahresrechnung nie aus der Basis liest. Die
  Nebentätigkeit fehlt dort deshalb (Befund 3 der Diagnose); jede weitere Unterkategorie ebenso. Eine
  Regel auf genau `einkommen/gehalt` machte die Nebentätigkeit in beiden Modellen zur Reihe, ohne neue
  Planzeile. → Opus: entscheiden, ob das neben der Planzeile aus Entscheidung 3 gelten soll.
- **E.0, E.4: Das Konto der Objektmiete** steht nirgends. → Opus: Vorschlag aus E.0 Ergebnis Frage 3
  (aus den gemessenen Mieten des Objekts ableiten, sonst Betriebskonto; ein Feld nur für Abweichungen).
- **E.0, Anfangsstand eines Kontos ohne Auszug.** Die Modelle trennen sich (siehe E.0 Ergebnis Frage 4),
  in der Kopie noch ohne Wirkung. → Opus mit dem Haushalt: Vorschlag „jede Position unter ihrem eigenen
  Datum“ in `balance_snapshots`, und die Jahresrechnung nimmt für ein `parsed`-Konto ohne Auszug denselben
  Stand.
- **E.0, E.4: Verkauf eines Objekts mit Prognose.** `jahre.rechnen` zieht bei einem Verkauf die
  gemessene Miete und Kosten des Objekts (`jahre.verkaeufe`, über `s.property_id`) von den Blöcken
  `miete` und `immobilie` ab, obwohl ein Objekt mit Prognose dort nicht steht; `_objektposten`
  kennt den Verkauf nicht und rechnet bis `bis` weiter. In der Kopie kein Fall (`verkaeufe` ist leer).
  → Opus: in E.4 mitnehmen oder als eigenen Punkt führen.
- **E.0, E.6: Zwei Quellen für die Art eines Kontos.** `zinsen.satz_im_monat` entscheidet nach der Art
  („tagesgeld“ bekommt den langfristigen Satz). Die Jahresrechnung nimmt sie aus `balances.yaml` (`kind`),
  das Monatsmodell hätte nur `accounts.account_type`; bei einem Konto der Kopie heißt sie dort „broker“,
  hier „giro“. Ohne Zinssatzeintrag ist das Ergebnis beide Male null, mit einem nicht. Außerdem braucht die
  Steuer einen Zähler des Sparerpauschbetrags je Haushalt und Kalenderjahr (`jahre._steuer_auf` ist rein
  und kennt keine Monate). → Opus: vor E.6 festlegen, woher die Art kommt.
- **E.0, E.1: Umbuchungen werden an Etiketten erkannt.** `ohne_objekt._UMBUCHUNG` ist eine Liste von
  Vorsilben; ein neues Etikett fiele durch. → Opus: für den Test ein Merkmal am Posten (`OneOff`,
  `RecurringItem`) statt der Liste.
- **E.0, Zeilen „nur Kontoprognose“** zählen im Monatsmodell, in der Jahresrechnung nie, auch wenn die
  Ausgabe nur das Konto wechselt. Über alle Konten summiert ist das eine Differenz, die kein Teilschritt
  beseitigt. → Opus: als bleibend in die Liste bekannter Unterschiede, oder die Zeile gleicht im Monatsmodell
  auf einem anderen Konto aus.
- **E.0, Kopie ohne Handentscheidungen.** Im Entwicklungsordner fehlen `prognosebasis_custom.yaml`,
  `reihen_custom.yaml` und `zinssaetze_custom.yaml`: Nichts ist abgewählt, kein Takt gesetzt, kein
  Zinssatz eingetragen. E.5 und E.6 prüft man daran nur, wenn die Kopie die Einträge bekommt. → Opus:
  vor E.5 und E.6 in der Kopie eintragen (nach Angabe des Haushalts).
- **E.1, Zinsen: der Vergleich vor der Kaskade geht nicht ganz auf.** Die Jahresrechnung verzinst den Stand
  des Topfs Tagesgeld zu Jahresbeginn, also nach der Kaskade des Vorjahres und mit allen Konten dieser
  Art. Das Monatsmodell verzinst den vorausgerechneten Stand seiner Konten, in den das Abräumen eingeht,
  nicht aber die Kaskade. Beide Stände laufen auseinander, auch wenn E.6 Satz und Steuer angleicht;
  `zinsen` kann dann nicht auf null kommen, und E.8 („leer bis auf die Kaskade“) wäre nicht erreichbar.
  → Opus: für E.6 festlegen, wie der Test Zinsen vergleicht (etwa Zins je Stand und Satz bei gleichem Stand,
  oder `zinsen` als bleibender Unterschied wie die Kaskade).
- **E.1, die Gründe einer Zeile sind nicht einzeln prüfbar.** Die Liste hat Gründe je Block, geprüft wird
  nur der Block: Streicht ein Teilschritt einen Grund, obwohl der Block seinetwegen noch abweicht,
  merkt der Test es nicht; er merkt erst, wenn der Block gleich ist und noch dasteht. Ein Block, der
  bis zuletzt abweicht, hält so einen schon erledigten Grund. → Opus: bei der Abnahme jedes Teilschritts
  die Reste im Block ansehen (`notizen/E.1_paritaet.md` hat die Zerlegung für 2027).
- **E.1, `einkommen_sonst` fehlt im Musterhaushalt.** Weder eine sonstige Einnahme noch eine
  Nebentätigkeit oder Schenkung steht dort. Der Test greift auf diesen Blöcken nur in der Kopie. E.5
  braucht beides im Musterhaushalt (erfundene, runde Beträge), sonst bleibt `einkommen_sonst` dort
  ungeprüft. → E.5.
- **E.1, `steuern` weicht nur im Musterhaushalt ab.** In der Kopie liegt die Kapitalertragsteuer in
  `zinsen`, und `steuern` ist dort null. Der Eintrag in der Liste (E.2, E.2b) gilt für den
  Musterhaushalt. Die Liste in E.0 hatte `steuern` unter E.6, weil sie die Zinsen noch nicht abgetrennt hatte.
- **E.1, Muster-Planzeilen mit festen Jahreszahlen.** Die Klammern „Ferienhaus“ und „Korrektur Forecast“
  im Musterhaushalt stehen auf 2030 und 2031. Der Musterhaushalt rechnet relativ zu heute, diese Zeilen
  nicht; ab 2031 fielen sie aus dem Horizont. Die neue Wegfall-Zeile nutzt `{J+1}`. Kein Fehler von E.1,
  aber der Test für `einmalig` hängt daran.

- **E.2, `miete`: Das Objekt mit Prognose zählt jetzt gemessen mit.** Seine eine gemessene Miete fiel im
  Monatsmodell bisher heraus, weil der Median fünf Monate mit Buchung verlangte. Mit der Summe durch zwölf
  steht ein Zwölftel davon auf dem Betriebskonto, bis E.4 die Buchungen des Objekts durch die Prognose
  ersetzt. Der Grund steht jetzt unter `miete` in der Liste (E.4); in `immobilie` stand er schon. Die
  Kosten des Objekts dagegen sinken im Monatsmodell, weil alle vier Buchungen in den letzten sechs Monaten
  lagen und das Zwölfmonatsfenster sie verdünnt. Kein Fehler von E.2.
- **E.2, `einkommen_sonst`: Die Schenkung steht jetzt in beiden Modellen.** Das Monatsmodell fortschreibt
  sie als Summe durch zwölf, die Jahresrechnung tat es schon; die Differenz ist genau die Steigerung. Der
  Grund „Schenkung nur in der Jahresrechnung“ (E.5) stimmt nicht mehr und ist gestrichen. E.5 ersetzt dann
  nicht mehr „fehlt im Monatsmodell“, sondern „gemessen in beiden“ durch die Planzeile. → Opus: E.5
  entsprechend lesen.
- **E.2, `konsum`: Ein durchlaufendes Konto fehlt im Monatsmodell.** `household_accounts` lässt Konten mit
  der Rolle `durchlaufend` aus, die Jahresrechnung misst ihre Buchungen mit; ein Konto der Kopie trägt so
  einige zehn Euro im Jahr, quer durch Restaurant, Reise, Event und Geschenke. Vorher stand das hinter dem
  Median. Jetzt gleich als Grund in der Liste, mit E.8 (kein Teilschritt beseitigt es). → Opus: entscheiden,
  ob das Monatsmodell die Ausgaben über ein durchlaufendes Konto auf dem deckenden Konto zählt (dann sind
  Karte und Girokonto im Haushaltsblock richtig, und der Unterschied fällt), oder ob es dauerhaft anders
  bleibt (`DAUERHAFT`).
- **E.2, `einmalig`: Die Wegfall-Zeile einer Reihe mit vielen Buchungen stimmt in beiden Modellen nicht
  überein.** Das Monatsmodell nimmt heraus, was es für die ganze Reihe bucht (70 Buchungen in der Reihe),
  die Jahresrechnung die Messung der vier zugeordneten Buchungen; das ist E.0 §7 Nummer 6 (Vorzeichen).
  Beide Werte haben sich durch E.2 nicht geändert. Steht jetzt als Grund in der Liste, mit E.8. → Opus:
  Eingabe klären (die Zeile den Buchungen der ganzen Reihe zuordnen oder die Gegenpartei trennen), dann
  fällt der Grund weg.
- **E.2, `zinsen`: gemessen über zwölf Monate.** Die gemessenen Zinsen zählen jetzt über das längere
  Fenster, die Korrekturzeilen darauf laufen unverändert bis 08/2027. Der Unterschied 2028 bis 2030 wird
  dadurch größer, nicht kleiner; E.6 löst beides ab.
- **E.2b, `einmalig`: Wegfall-Zeilen sind in der Jahresrechnung flach.** *(Erledigt in E.2b-N.)* `szenarien.jahreswirkung` zieht den
  gemessenen Betrag einer Wegfall-Zeile ohne Inflation ab, während die Reihe in der Basis mit der Inflation
  steigt (`jahre._vertragsende_posten` tut es mit Inflation, genau wegen dieses „wachsenden Rests“). Das
  Monatsmodell zieht ab, was es bucht, und das steigt jetzt. Ohne Inflation ist `einmalig` jedes Jahr gleich;
  mit ihr wandert es um rund 80 im Jahr (2027 bis 2030 von -167 auf +76). Das ist der alte Grund „Steigerung
  der Reihe, die endet“, und E.2b beseitigt ihn nicht, weil dafür die Jahresrechnung ändern müsste. Er steht
  jetzt in `BEKANNT` unter `einmalig` mit E.8. → Opus: Wegfall-Zeilen in der Jahresrechnung mit der Inflation der
  Basis abziehen (ändert `/ziele`, `/hochrechnung`, Planung) oder als bleibend annehmen.
- **E.2b-N, `/planung` zeigt das Gemessene weiter flach.** `restwirkung_monatlich` ist die Zahl der Seite „je Monat noch
  übrig“ und hat keinen Zeitpunkt; sie rechnet mit der Messung, wie sie im Fenster steht. Die Prognosen (Jahresrechnung
  und Monatsmodell) steigern. Die Seite wäre nur mit einem gewählten Zeitpunkt gleich. → Opus: so lassen oder die Seite
  zeigt den Rest zum ersten Monat nach dem Fenster.
- **E.2b-N, `einmalig` im Musterhaushalt gleich.** Der verbliebene Grund (E.0 §7 Nummer 6) ist eine Eingabe des Haushalts
  des Nutzers (eine Wegfall-Zeile, die nur vier Buchungen einer Reihe mit vielen nennt) und besteht im Musterhaushalt
  nicht. Ich habe ihn dort nicht erfunden (das hätte Buchungen und Zahlen des Musterhaushalts verändert, auf denen andere
  Tests stehen), sondern `NUR_IM_HAUSHALT_DES_NUTZERS` in `tests/test_paritaet.py` eingeführt. → Opus: so lassen, bis die
  Eingabe geklärt ist (E.8; dann fällt die Menge mit dem Grund weg), oder den Fall im Musterhaushalt nachbauen.
- **E.2b-N, ein Rest in `einmalig` wächst weiter mit der Inflation.** Er ist der andere Grund (Wegfall-Zeile mit der
  großen Reihe, E.0 §7 Nummer 6) und bleibt in `BEKANNT`; er fällt mit der Entscheidung dazu (E.8).
- **E.2b-N, Korrekturzeilen auf Zinsen bewegen sich im Monatsmodell.** `restbetrag_je_termin` steigert für jede Planzeile mit
  Rest, also auch für die Korrekturzeilen auf Zinsen und Steuer (E.6, bis 08/2027). Wenige Euro; der Block `zinsen` bleibt
  aus dem Grund E.6 in `BEKANNT`.
- **E.2c, die Richtung stimmt nicht mit der Erwartung.** Der Plan nahm an, ohne E.2c fehlten Ausgaben und das Monatsmodell sei zu
  optimistisch. In diesem Haushalt trägt das durchlaufende Konto netto mehr Eingänge (in `abo/*`, `konsum/geschenke`,
  `reisen/reise-privat`) als Ausgaben, und das Monatsmodell wird mit E.2c um rund zwanzig Euro im Monat optimistischer. Es ist
  trotzdem richtig (die Jahresrechnung zählt es so), aber wer die Seite `/konten` vorher und nachher vergleicht, sieht den Cashflow
  steigen. → Opus: zur Kenntnis; die Referenz geht danach mit.
- **E.2c, `konsum` bleibt in `BEKANNT`, mit zwei neuen Gründen statt „durchlaufendes Konto“.** Das durchlaufende Konto hat den Block
  auf keinem Datensatz gleich gemacht; es hat zwei andere Unterschiede nur aufgedeckt. (1) Kopie: Eine Buchung des durchlaufenden
  Kontos ist einem Objekt mit Prognose zugeordnet; die Jahresrechnung zählt sie im Block `objekt`, das Monatsmodell in der Kategorie
  (`konsum`): E.4. (2) Musterhaushalt: Teile ohne Kategorie zählt die Jahresrechnung unter dem leeren Schlüssel, das Monatsmodell
  nicht (Schritt 2, Tabelle: „Typ ja, Wert nein“); in der Kopie gibt es keine: E.8, kein Teilschritt beseitigt es. → Opus: Teile ohne
  Kategorie in beiden gleich behandeln (dann fällt der Grund), dauerhaft lassen (`DAUERHAFT`) oder den Musterhaushalt ohne solche
  Teile bauen. Beides macht die Liste länger, nicht kürzer; E.2 hat es mit drei Gründen, die der Median verdeckt hatte, ebenso getan.
- **E.2c, `fixkosten`: die Differenz wächst im ersten Jahr, schrumpft danach.** Die Posten des durchlaufenden Kontos in `abo/*` zählen
  jetzt im Monatsmodell; den Rest zeigt der Grund aus E.2d jetzt ohne das Fehlende davor. 2027 liegt die Differenz um einige hundert
  Euro höher als vorher, 2028 bis 2030 um zweihundert bis dreihundert Euro niedriger. Kein Fehler von E.2c.
- **E.2c, Verträge und Planzeilen auf dem durchlaufenden Konto.** Ein Vertrag, dessen `konto` das durchlaufende Konto ist, und eine
  Planzeile auf ihm buchen weiter dort und fehlen damit im Monatsmodell. In der Kopie gibt es keinen (`abos.yaml`, Planung). Die
  Zuordnung auf das deckende Konto gehört zu E.2d (Verträge) beziehungsweise zu den Planzeilen. → Opus: E.2d um den Satz erweitern,
  „ein Vertrag auf dem durchlaufenden Konto zählt auf dem deckenden“.
- **E.2c, `/konten` sagt nicht, dass ein Posten vom durchlaufenden Konto kommt.** Das durchlaufende Konto erscheint dort wie vorher
  nicht; seine Buchungen stehen im Rechenweg der Posten des deckenden Kontos, ohne dass der Rechenweg es sagt. → Opus: Schritt 6
  kann es benennen.

- **E.2b, `fixkosten` bleibt aus anderen Gründen als der Steigerung.** Vorher verdeckte die Steigerung den Rest.
  Jetzt zeigt sich: Der Vorrat eines Vertrags (bezahlt bis zu einem Datum) kennt nur das Monatsmodell; die
  Jahresrechnung zählt die Messung weiter. Eine gekündigte Reihe mit Wegfall-Zeile führt die Jahresrechnung in
  `einmalig`, das Monatsmodell nimmt sie aus `fixkosten`. Bei Verträgen mit Mitzahlern zählt die Jahresrechnung
  deren Zahlungen als Reihe mit Takt, das Monatsmodell nur den Betrag am Vertrag und die offenen Rückzahlungen.
  Die Kündigung selbst (`gekuendigt_zum`) wirkt in beiden gleich, wo sie allein steht. Der Grund steht in
  `BEKANNT` unter `fixkosten` mit E.8. → Opus: ob der Vorrat in die Jahresrechnung gehört und wie Mitzahler
  in beiden zählen.
- **E.2b, Reihen mit Takt steigen im Monatsmodell an ihrem Termin.** Ein Jahresbeitrag im Januar steigt weniger
  als einer im Dezember; die Jahresrechnung rechnet beide zur Jahresmitte. Der Unterschied liegt bei gut einem
  halben Prozent des Betrags (bei einer Kfz-Versicherung wenige Euro im Jahr), mit dem Vorzeichen des Termins.
  Das ist gewollt (ein Betrag steigt zu seinem Datum) und bleibt unter der Toleranz, wo nur kleine Jahresposten
  im Block stehen. → Opus: bei einem großen Jahresposten in einem sonst gleichen Block würde der Test anschlagen.
- **E.2b, Musterhaushalt: Das Ferienhaus hatte keine gemessene Miete.** Der Test verlangt, dass ein Grund in
  `BEKANNT` auf beiden Datensätzen besteht; `miete` (E.4) stand nur in der Kopie. Gelöst mit einer erfundenen
  Mietbuchung. Gilt künftig für jeden Grund, der nur in einem Datensatz besteht.

- **E.2d, die Eingänge der Mitzahler fehlen in der Zukunft.** Mitzahler zählen über den Vertrag, und `rueckzahlungen` kennt nur den
  OFFENEN Anteil eines Zeitraums, den es schon gibt. Ein künftiger Zeitraum, den der Haushalt noch nicht angelegt hat, hat keine
  Rückzahlung: Der Betrag am Vertrag zählt voll, der Anteil der Mitzahler gar nicht. Vorher zählte die Messung ihre Eingänge als Reihe
  fort. Folge: Beide Modelle werden pessimistischer, die Jahresrechnung um 200 bis 260 Euro im Jahr, C24 im Monatsmodell um die Eingänge
  des durchlaufenden Kontos (das war E.2cs Gewinn). → Opus: so lassen, oder die Besetzung als erwarteten Anteil je Termin des Vertrags
  zählen, wenn ein Zeitraum fehlt.
- **E.2d, laufende Mitzahler bleiben gemessen.** Wer mit `seit` laufend mitzahlt, steht in `laufend`, nicht in den Zeiträumen; sein
  Eingang bleibt in beiden Modellen eine gemessene Reihe (gleich in beiden, vorher auch). Der Auftrag sagt, die Zahlungen der Mitzahler
  fielen aus der Messung; für diese Gruppe gibt es keinen offenen Anteil, der sie ersetzte, und sie herauszunehmen ließe rund achtzig Euro im Jahr
  verschwinden. → Opus: so lassen, oder laufende Mitzahler als Anteil je Termin über den Vertrag zählen.
- **E.2d, `einmalig` fällt aus `BEKANNT`, und der Grund war ein anderer als gedacht.** Der Rest kam nicht von „Wegfall-Zeile nennt nur
  einen Teil der großen Reihe“ (E.0 §7 Nummer 6), sondern von einer Wegfall-Zeile auf der Reihe eines gekündigten Vertrags mit
  Mitnutzern: Das Monatsmodell nahm nur den Rest nach Abzug des Vertrags heraus, die Jahresrechnung die ganze Messung. Seit beide nur
  nehmen, was die Messung noch sieht (`szenarien.messung(..., ohne=...)`), ist `einmalig` auf den Cent gleich. `NUR_IM_HAUSHALT_DES_NUTZERS`
  ist damit leer und entfällt.
- **E.2d, `fixkosten` bleibt in `BEKANNT`** (Reihen mit Takt am Termin, E.2b Nummer 3), und zwar auf beiden Datensätzen über der
  Toleranz von einem Euro, weil beide einen Jahresposten in `fixkosten` haben. → Opus: entscheiden, wie der Test damit umgeht. Vorschlag:
  Der Test rechnet das Monatsmodell mit der Jahresmitte als Termin (die Wirkung ist belegt, siehe oben) und führt den Unterschied als
  `DAUERHAFT` wie die Anlagen; dann ist `fixkosten` gleich und fällt aus der Liste.
- **E.2d, der Treffer-Check der Jahresbasis misst weiter die alte Basis.** `treffer._soll_je_block` rechnet die Basis ohne die
  Buchungen der Verträge und mit den Reihen der Verträge, also nicht mehr, was die Hochrechnung für Verträge tut. Der Check ändert sich
  nicht, aber er prüft für `fixkosten` eine Rechnung, die es so nicht mehr gibt. → Opus: der Check sollte die Verträge als eigenen Posten
  mitführen (ein Teilschritt, nicht dieser).
- **E.2d, `_vertragsenden` rechnet für alle Verträge und wird gefiltert.** Die Funktion misst die Reihe jedes gekündigten Vertrags; `_eingaben`
  nimmt die heraus, die über ihre Tatsachen zählen. Das ist etwas Arbeit für nichts (Sekundenbruchteile), und die Tests von
  `_vertragsenden` prüfen weiter die Messung für gewöhnliche Verträge, die so nicht mehr in die Rechnung geht. → Opus: später auf die
  Verträge einer Police einengen und die Tests mitnehmen.
- **E.2d, Wegfall-Zeilen wirken jetzt auch im Monatsmodell auf den Vertrag selbst.** Vorher setzte eine Wegfall-Zeile auf der Reihe eines
  Vertrags dessen Termine im Monatsmodell nicht aus (die Reihe war aus der Messung, es gab nichts abzuziehen), in der Jahresrechnung
  über die Messung schon. Jetzt setzt sie ihn in beiden aus. In der Kopie hat das keine Wirkung (die Zeile liegt hinter der Kündigung).
- **E.2d, ein Vertrag in einer Kategorie ohne Block der Basis** (nicht `FROM_BASE`) zählt im Monatsmodell, in der Jahresrechnung bleibt er
  gemessen. Kein Fall in der Kopie oder im Musterhaushalt.

- **E.2d-N, nur wer schon gezahlt hat, zählt als Erwartung.** Gelesen nach dem Wortlaut („jeder Termin ohne Zeitraum, der Anteil der Besetzung“)
  zählte auch eine Person, die nur in der Besetzung steht und weder in einem Zeitraum stand noch mit `seit` laufend mitzahlt. Die
  Besetzung ist laut Oberfläche die Vorlage für neue Zeiträume; wer nie zugeordnet gezahlt hat, dessen Anteil ist ein Vorhaben. In der Kopie
  trifft das vier Verträge (ein Streaming-Abo und drei Versicherungen mit je einer Person in der Besetzung); ihr Anteil hätte beide Modelle noch einmal
  um etwa so viel angehoben, wie E.2d entfernt hatte, ohne dass eine Buchung es stützte. Die Regel steht in `abos.erwartete_anteile`: Es zählt, wer in
  irgendeinem Zeitraum steht oder `seit` hat. → Opus: so lassen, oder auch die reine Besetzung zählen (dann steht ein Anteil im Plan, den der
  Haushalt nie bekommen hat).
- **E.2d-N, die gemessene Reihe der laufenden Mitzahlerin fällt weg, und die Kopie wird pessimistischer.** Die Gegenpartei der laufenden Person
  eines Mobilfunk-Vertrags zahlte bis Juli einen höheren Betrag im Monat in dieselbe Kategorie und zahlt seit August nur noch ihren Anteil. Die
  Messung hielt die Reihe aus den letzten drei Terminen für fortlaufend und rechnete mit dem alten, höheren Betrag. Seit die Zahlung vom August aus der
  Messung ist (Punkt 2), reichen die Termine nicht mehr für eine Reihe, und der Posten fällt weg; dafür steht der Anteil laut Besetzung da. Die
  Änderung folgt aus Punkt 2 und ist inhaltlich richtig (der höhere Betrag wird nicht mehr gezahlt), macht aber `fixkosten` der Jahresrechnung
  um rund ein halbes Prozent tiefer und überwiegt die neuen Anteile. Die Zahlung vom September steht in einer anderen Kategorie und bleibt gemessen.
  → Opus: nichts zu tun, außer der Haushalt ordnet sie zu; sonst wissen, dass E.2d-N diese Kopie nicht optimistischer macht.
- **E.2d-N, Zeitraumende ist ausgenommen.** Ein Termin am `bis` eines Zeitraums gehört dem nächsten (`Zeitraum anlegen` setzt das Ende des einen als Beginn
  des nächsten; die Jahreszeiträume der Kopie enden alle auf den Beginn des nächsten). Ein Zeitraum mit `von` = `bis` deckt seinen einen Monat. → Opus: bestätigen.
- **E.2d-N, der Anteil zählt am Termin, nicht im Einsammel-Monat.** Der offene Anteil eines Zeitraums kommt im Einsammel-Monat (Wochen bis Monate
  nach dem Termin), der erwartete Anteil im Monat des Termins, ohne Tag. In der Kopie ist der Unterschied klein (Jahrestakt, ein Monat). Eine spätere
  Zahlung der Mitzahler schöbe ihn nach hinten. → Opus: so lassen oder einen Verzug einführen.
- **E.2d-N, der Test rechnet das Monatsmodell zweimal.** Einmal an den Terminen (für den Bilanztest und die Zahl in `DAUERHAFT`), einmal zur Jahresmitte
  (der Vergleich). Das kostet auf der Kopie rund eine Sekunde. Die Jahresmitte betrifft alle Reihen mit Takt, nicht nur die von `fixkosten`: In `gehalt`,
  `immobilie` und `konsum` bewegt sich das Monatsmodell damit um bis zu etwa einen Euro im Jahr; ihre Einträge in `BEKANNT` bleiben, wie sie waren.

- **E.3, `gehalt` steht nun auch in `NUR_IM_HAUSHALT_DES_NUTZERS`.** Auf dem Musterhaushalt gleicht sich der Block, weil er keine Nebentätigkeit hat; der Test
  `test_a_listed_block_that_no_longer_differs_leaves_the_list` schlug dort mit „gehalt (E.5)“ fehl. Wie bei `konsum` (E.2e) steht der Block in der Menge
  und fällt mit E.5 wieder heraus. → Opus: bestätigen, oder dem Musterhaushalt eine Nebentätigkeit geben.
- **E.3, die Teilzeit rechnet im Monatsmodell nicht, auch nicht auf derselben Basis.** `szenarien.NUR_JAHRESRECHNUNG` nimmt `teilzeit` aus dem
  Monatsmodell; es bucht das volle Gehalt, wenn eine Teilzeit im Horizont läge. Die Teilzeit der Kopie beginnt erst 2045, also weit außerhalb der
  sechzig Monate, und die Jahresrechnung rechnet sie von der Untergrenze (nicht mehr vom Median). Bei einer Teilzeit im Horizont wären beide Modelle
  verschieden, und die Liste bekannter Unterschiede hat dafür keinen Grund („außerhalb des Horizonts oder gewollt“, E.0). → Opus: so lassen, oder
  im Monatsmodell als Abzug vom Gehalt buchen.
- **E.3, die Ursache „Gehalt“ in der Wirkung entfällt.** Sie tauschte den gemessenen Median zwischen den Stichtagen; die Untergrenze ist eine Annahme und
  gilt in beiden Rechnungen gleich (`CONTEXT.md`: „Annahmen … gelten für beide Stichtage so, wie sie heute stehen“). Ein Gehalt, das sich
  zwischen zwei Monaten ändert, gibt es nicht mehr; ein Monatsabschluss zeigt deshalb nie wieder eine Zeile „Gehalt“. `CONTEXT.md` und `wirkung._folge`
  sind angepasst, der Test `test_a_swap_that_changes_nothing_is_no_cause` tauscht nun den Bestand. → Opus: bestätigen.
- **E.3, die Rentenlücke bewegt sich nicht.** Der Plan (E.3 und Abschnitt 6) erwartet eine Änderung; sie rechnet aber „Laufende Einnahmen ohne Gehalt“,
  und die Teilzeit wirkt nur im Gehalt davor. `/ziele` zeigt sie unverändert. Kein Fehler, nur eine falsche Erwartung im Plan.
- **E.3, das Soll Gehalt im Treffer-Check und im Abgleich ist jetzt die Untergrenze.** Beide verglichen bisher mit dem (gleitenden) Median als „Plan“ und
  begründeten das damit, dass die Untergrenze eine Absicht sei und keine Prognose. Die Jahresrechnung rechnet nun mit ihr; „Plan“ ist, was sie
  rechnet. Die Zeile steht damit meist unter dem Ist (die Untergrenze liegt unter dem gebuchten Gehalt). → Opus: bestätigen, oder die Zeile auf
  `/annahmen` und im Abgleich ausblenden.
- **E.3, die Notizen in `assumptions.yaml` des Haushalts sprechen noch vom Median als Grundlage.** `erwerbseinkommen.netto_floor_monatlich_cents` und
  `…netto_median_monatlich_cents` (Notizen zu „Floor = Dispo-Frage, Median = was sich anhäuft“ und „Benutzt von der Jahresrechnung“) stimmen nicht mehr.
  Der Schlüssel `netto_median_monatlich_cents` hat keinen Leser mehr. → Opus mit dem Haushalt: Notizen berichtigen, Schlüssel aus Datei und
  `finctl/vorgaben/assumptions.yaml` nehmen (E.8).
- **E.3, `CHANGELOG.md` bleibt für E.8.** Der Unterschied für den Haushalt (Ziele, Hochrechnung und Konten rechnen mit der Untergrenze, sie wächst jedes
  Jahr) gehört in die Änderungen unter „Unveröffentlicht“; wie bei E.2 bis E.2e fasse ich die Datei hier nicht an.

- **E.4, die Saison wirkt auf die Miete, nicht auf Miete minus Kosten.** Der Plan sagt „Saisonfaktoren“; die Notiz am Objekt spricht von der „Saisonalität der Mieten“, und die Kosten laufen gleichmäßig. Ich habe den Faktor auf die Miete gelegt (`objektposten.betraege`). Mit Kurven aus lauter 1,0 ändert das keine Zahl; eine Kurve auf Miete minus Kosten verschöbe bei kleinem Netto den Ertrag stärker. → Opus: bestätigen, oder die Kurve auf das Netto legen (eine Zeile in `betraege`).
- **E.4, `/immobilien` hat den Satz nicht.** Der Auftrag nannte beide Seiten; nur `/immobilie/<id>` sagte „wirkt in der Hochrechnung statt der Messung“ (jetzt: in beiden Prognosen). `/immobilien` trägt keinen Text zur Prognose, dort ist nichts geändert. Das Handbuch (Abschnitt Immobilie) nennt beide Prognosen; mehr Text verbietet die Grenze von 200 Wörtern je Abschnitt.
- **E.4, der Treffer-Check der Konten zählt das Objekt nicht.** Das Ist enthält den Block `objekt` nicht mehr, und das Soll hat die Objektposten nicht: Die Prognose des Objekts steht dort weder im Soll noch im Ist. Die Jahresbasis (`treffer.jahresbasis`) prüft sie weiter gegen den Block `objekt`. → Opus: so lassen, oder die Posten ins Soll aufnehmen (dann auch ein Ist für Monate vor `ab`).
- **E.4, der Tiefpunkt des Betriebskontos wird deutlich tiefer.** Die Posten sind undatiert: Kosten am 1., Miete am 28. (Vorgabe der Engine). Das Objekt zahlt seine Miete tatsächlich zum Monatsende, die Kosten fallen über den Monat. Der Monat bringt netto mehr, der Tiefpunkt liegt aber rund zweieinhalbmal so tief wie vorher, und ein knapp geführtes Betriebskonto spürt das. → Opus: den Tag der Miete festlegen (Vorschlag: Monatsende wie gebucht) und die Kosten auf einen Tag in der Monatsmitte, oder so lassen.
- **E.4, kein Feld `prognose.konto`.** Es war nötig nur, wenn der Haushalt abweichen will. In der Kopie liegt die gemessene Miete auf dem Betriebskonto, im Musterhaushalt auf dem Konto der Miete; kein Fall braucht das Feld.
- **E.4, ein Objekt ohne gebuchte Miete und ohne Betriebskonto fehlt im Monatsmodell.** Dann hat der Posten kein Konto; `konto_des_objekts` gibt `None`, und es wird nichts gebucht, ohne dass die Seite es sagt. Der Fall setzt voraus, dass die Konten weder ein Betriebskonto noch ein Giro mit Auszügen haben. → Opus: ob eine Meldung nötig ist.
- **E.4, `jahre.verkaeufe` misst Miete und Kosten eines Objekts mit Prognose weiter.** Die Werte (`miete_jahr_cents`, `kosten_jahr_cents`) gehen für dieses Objekt in keine Rechnung mehr ein; `rechnen` überspringt es. Aufwand: eine Abfrage je Verkauf. → Opus: später aus `Verkauf` nehmen, wenn kein Objekt ohne Prognose mehr verkauft wird.
- **E.4, Rundung der Miete.** Die Miete eines Monats ist netto plus Kosten, nicht `grow(Miete)`, damit Miete minus Kosten in beiden Modellen auf den Cent der alte Betrag bleibt; sie weicht von `grow(Miete)` um höchstens einen Cent im Monat ab.
- **E.4, `miete`, `immobilie` und `konsum` sind nachher nicht auf den Cent gleich, sondern unter einem Euro im Jahr** (Rundung der Posten je Konto gegen eine Summe); nur `objekt` ist auf den Cent gleich. Die Toleranz des Paritätstests deckt es, wie für jeden anderen Block.

- **E.2, vier Tests zu `reihen_custom.yaml` schlagen auf der Entwicklungskopie fehl, nicht wegen E.2.**
  `test_reihen.py::test_a_decision_through_the_page_is_written_once_and_taken_back`,
  `::test_einmalig_through_the_page_lists_the_booking_and_takes_it_back` und die beiden
  `test_browser.py`-Tests `test_reihen_oeffnen_festlegen_und_speichern_ohne_aenderung` und
  `test_reihen_einmalig_setzen_und_zuruecknehmen` nehmen an, dass die Datei leer ist
  (`reihen.lesen() == []`, `[eintrag] = _reihen_eintraege()`). Seit der Korrektur der Eingaben durch Opus
  (16:08) steht dort ein Eintrag „einmalig“. Auf dem Stand vor E.2 fallen sie genauso (geprüft für die beiden
  ersten); auf dem Musterhaushalt sind sie grün. → Opus: die Tests von der Datei des Haushalts entkoppeln.
- **E.2, ein Browsertest ist auf dem Musterhaushalt unruhig.** `test_notiz_einer_kontenregel_ist_mehrzeilig`
  wartete auf `#r-giro` und lief in die Zeitgrenze; auf dem Stand vor E.2 ebenso. Nicht von E.2.

- **E.5, die Entwicklungskopie hat keine Abwahl der Schenkung.** `prognosebasis_custom.yaml` fehlt dort (nach E.0, Nummer 12, auch im echten Ordner), die Schenkung war nie abgewählt. Nichts geändert. Ein Ordner, der sie abgewählt hätte, braucht die Abwahl nach E.5 nicht mehr: Die Kategorie ist ersetzt und die Zeile zählt.
- **E.5, die Nebentätigkeit fehlte in der Jahresrechnung der Referenz ganz.** Der Block `gehalt` stand nicht in `FROM_BASE`; die Buchungen der Nebentätigkeit gingen verloren, im Monatsmodell zählten sie als Reihe. Mit dem engeren Block zählt sie in beiden Modellen als gemessene Reihe (13 Unterschiede, noch ohne die Zeilen). Das war E.0, Befund 3; die Zeile ersetzt die Messung danach. → Opus: zur Kenntnis.
- **E.5, die Zeilen haben keine Steigerung.** So war es verlangt (fester Betrag): Die Messung stieg mit 2 % im Jahr, die Zeile nicht, und `einkommen_sonst` liegt im Jahr 2089 rund 60 % unter der Referenz, im Jahr 2030 rund 16 % darüber. Die Ziele bewegen sich um höchstens 2 Prozentpunkte, die Deckung der Rentenlücke 2062 um 4. → Opus: so lassen, oder die Zeile bekommt später ein Feld für die Steigerung.
- **E.5, eine ausgeschaltete Klammer gibt die Messung zurück.** `erwartet_zugeordnet` zählt nur eingeschaltete Klammern; wer „Erwartete Einnahmen“ ausschaltet, hat die Schenkung wieder gemessen, mit Steigerung, in beiden Modellen. Der andere Weg (die Buchungen bleiben draußen, die Einnahme steht nirgends) schien mir schlechter. → Opus: bestätigen.
- **E.5, die Warnung „mehr als ein Plan gleichzeitig an“ nimmt Klammern aus erwarteten Einnahmen aus** (`Scenario.nur_erwartet`, `monatsabschluss`). Schenkung und Nebentätigkeit sind keine Variante einer Entscheidung; die Karte nennt die Klammer weiter unter den eingeschalteten. → Opus: bestätigen.
- **E.5, der Treffer-Check misst die ersetzten Buchungen unterschiedlich.** Das Ist der Konten (`treffer._ist_je_konto`) zählt sie nicht mehr, sonst stünde dort gemessen, was das Soll nicht fortschreibt (wie bei E.4 das Objekt). Die Jahresbasis (`treffer.jahresbasis`) bleibt gemessen, denn sie prüft die Messung der Basis, nicht die Zeile; ihr Soll `einkommen_sonst` steigt um die Nebentätigkeit. → Opus: so lassen, oder die Jahresbasis ohne die ersetzten Buchungen messen.
- **E.5, die Karte „Gehalt“ auf der Startseite zählt die Nebentätigkeit weiter.** `routen/start.py` summiert `einkommen/gehalt%` für die Anzeige des Gehalts im Jahr; mit Prognose hat das nichts zu tun, und ich habe es nicht angefasst. → Opus: angleichen (genau `einkommen/gehalt`) oder lassen.
- **E.5, der Schreiber der App hat `szenarien.yaml` der Kopie in seinem Format neu geschrieben.** Kopfzeilen und Einrückung sind anders als vorher; die Klammern sind inhaltlich gleich, dazugekommen ist nur „Erwartete Einnahmen“.
- **E.5, `tests/referenz.py` nimmt die ersetzten Buchungen aus der Basis.** `_hochrechnung` ruft `einmalig_zugeordnet` auf; ohne `erwartet_zugeordnet` zeigte `ableitung/hochrechnung_basis` die Schenkung weiter gemessen. Nur das Werkzeug, die Zahlen der Seiten kommen aus `jahre.eingaben`.

- **E.6, die Korrekturzeilen auf Zinsen und Steuer gelten in keinem Modell mehr.** Der Auftrag ließ offen, ob sie im Monatsmodell weiter zählen. Ich habe `konten._planposten` angewiesen, jede Zeile auf einer gerechneten Kategorie zu überspringen: Gemessen wird nichts mehr, und eine Korrektur der Messung zöge sonst einen Betrag vom gerechneten Zins ab, der dort nicht steht (bis 08/2027 ein Mehrfaches des Zinses). Die Seiten sagen es an der Zeile („zählt in keiner Prognose“). → Opus: bestätigen; der Haushalt löscht die drei Zeilen der Kopie.
- **E.6, das Ist des Treffer-Checks der Konten zählt Zinsen und Steuer nicht mehr.** Sonst stünde dort gemessen, was das Soll nicht fortschreibt (wie bei E.4 das Objekt, bei E.5 die ersetzten Buchungen). Die Jahresbasis (`treffer.jahresbasis`) misst sie weiter wie gebucht, denn sie prüft die Messung der Basis. → Opus: bestätigen.
- **E.6, `household_accounts` rechnet bis zu dreimal.** Fällt keine Steuer (Pauschbetrag nicht erreicht), bleibt es bei einem Lauf. Fällt sie, braucht der Plan die Zinsen des Laufs davor, und die Steuer ändert den Zins des Folgemonats um Cent: höchstens drei Läufe, die Zeit der Rechnung auf der Kopie (60 Monate) steigt von 0,7 auf 1,6 s. Die Seiten blieben gleich schnell (`/konten` 0,5 s, `/monatsabschluss` 1,2 s, `/ziele` 0,4 s, `/hochrechnung` 0,6 s; der zweite Aufruf). Der dritte Lauf endet auch, wenn der Plan noch um einen Cent schwankt; die Steuer eines Jahres weicht dann um wenige Cent von der Steuer auf die Jahressumme ab (der Test gibt 20 Cent). → Opus: so lassen, oder die Steuer in `engine.project` als Zähler über die Konten führen (dann nur ein Lauf, aber ein Zustand quer durch die Durchgänge).
- **E.6, das Betriebskonto bewegt sich in der Kopie nicht.** Der Auftrag erwartete es; es hat keinen Satz und keine gemessenen Zinsen im Fenster, und sein Abräumen aufs Tagesgeld hängt nicht von Zinsen ab. Die Konten, die ohne gemessene Zinsen tiefer fallen, füllt es nicht auf (`auffuellen: false`). Bewegen würde es sich, wenn der Haushalt ihm einen Satz gäbe oder eines dieser Konten das Auffüllen einschaltet.
- **E.6, das Monatsmodell verzinst ein Konto, das die Jahresrechnung nicht kennt.** Ein Konto mit Eintrag in den Zinssätzen, das nicht in `balances.yaml` steht, verzinst das Monatsmodell, die Jahresrechnung nicht (der Topf kommt aus `balances.yaml`). Kein Fall in der Kopie oder im Musterhaushalt. → Opus: so lassen.
- **E.6, das Monatsmodell hat keine Vorabpauschale.** Die Zinsen bekommen den ganzen Pauschbetrag (in der Jahresrechnung zuerst auch sie, die Vorabpauschale bekommt den Rest). Hat der Haushalt ein Depot, fehlt dem Monatsmodell dieser Anteil nicht, denn die Steuer der Vorabpauschale bucht es nicht.
- **E.6, die Zinsen des laufenden Jahres vor dem Stichtag verbrauchen den Pauschbetrag real.** Das erste Jahr der Projektion bekommt den Pauschbetrag anteilig nach Restmonaten, wie in der Jahresrechnung; die Zinsen von Januar bis zum Stichtag, die der Freibetrag real schon aufgebraucht hat, kennt keines der beiden Modelle. Kein Fehler von E.6. → Opus: zur Kenntnis.
- **E.6, ein Konto allein rechnet mit dem vollen Pauschbetrag.** `account_forecast` ohne `steuer` (`finctl forecast`, die Kontoprognosen der Referenz) behandelt das Konto als den Haushalt, ohne die Umbuchungen der anderen Konten. Die Seiten rechnen über `household_accounts`; die Einzelkonten in der Referenz (`kontoprognose_12`, `_60`) zeigen deshalb auch für das Tagesgeld einen anderen Verlauf als `/konten` (auch vor E.6).
- **E.6, die Namen `gilt_in_hochrechnung` und `ohne_wirkung_in_hochrechnung` stimmen nicht mehr.** Die Zeilen gelten in keiner Prognose; die Namen erinnern an die Zeit, als es nur die Hochrechnung war. Ich habe sie nicht umbenannt (zwei Aufrufer in `jahre.py`, Tests, Seiten). → Opus: später umbenennen, wenn es sich lohnt.
- **E.6, der Eintrag in `ZU_VERZWEIGT`.** `household_accounts` ist jetzt die kurze Schleife um den Plan; die schwere Funktion mit dem alten Namen und dem Wert 18 heißt `_haushalt`. Der Eintrag ist umbenannt, nicht neu.

- **E.7, Mischbasis: das ganze Ziel bleibt in der Jahresrechnung.** Opus, 26.10.2026: B bestätigt (die Alternative, den Bestand nicht projizierter Töpfe unverzinst zum Monatsmodell zu addieren, wäre eine Zahl, die kein Modell rechnet). Keine Wirkung auf einen der beiden Datensätze.
- **E.7, der Notgroschen als Untergrenze eines Kontos ist eine Näherung.** Seine Grenze gilt für das Tagesgeld insgesamt (Giro und Tagesgeld, Kaskade), das Monatsmodell legt sie ganz auf ein Konto. Liegt auf diesem Konto weniger als die Grenze, warnt `/konten` ab dem ersten Monat, auch wenn die anderen Konten den Rest tragen; in der Entwicklungskopie sind es zehn von zwölf Monaten, weil die Raten des Oktobers das Konto fast leeren (so gemeint: „eine Klammer greift den Notgroschen an“). Gibt es mehrere Konten der Art Tagesgeld und keines, auf das abgeräumt wird, gibt es keine Untergrenze aus dem Notgroschen, ohne dass die Seite es sagt. → Opus: bestätigen, oder die Grenze auf die Summe der Konten des Topfs legen (dann warnt nur noch die Summe, `Giro + Tagesgeld zusammen`).
- **E.7, das Auffüllen füllt die Untergrenze des Notgroschens mit auf.** Hat das Konto des Notgroschens `auffuellen` an (in der Entwicklungskopie aus), zieht das Betriebskonto die Grenze nach. Das folgt aus „Untergrenze“ und ist nicht eigens geprüft.
- **E.7, `Wirkung` rechnet weiter mit der Jahresrechnung.** `wirkung.Messung` ruft `ziele.hochgerechnet`; für ein kurzfristiges Ziel erklärt die Zerlegung deshalb die Bewegung der Jahresrechnung, nicht die Zahl der Karte. In der Entwicklungskopie betrifft das den Notgroschen. → Opus: Wirkung für ein Ziel im Monatsmodell weglassen oder neu zerlegen (eigener Schritt).
- **E.7, Stichtag zwischen zwei Monatsenden.** Das Monatsmodell kennt Monatsenden; ein Stichtag mitten im Monat misst den Stand des Vormonatsendes, nicht anteilig wie `Projection.zum`. Bei einem Stichtag am Monatsersten (Normalfall) ist es der Stand des Vortags.
- **E.7, die Anfangsstände kommen nur aus den Positionen.** Der `verlauf` in `balances.yaml` wird nicht in `balance_snapshots` gespiegelt (E.0 nannte ihn als mögliche Quelle). Ein Stand, der erst nach dem Stichtag eingetragen wurde, hat dann keinen älteren Stand dahinter. Eine Zeile je Position und Datum genügt dem Auftrag; ein früherer Stand aus dem Verlauf käme sonst zu jeder Position dazu. → Opus: so lassen oder den Verlauf mitnehmen.
- **E.7, die Seite „Monatsabschluss: Bestände“ zeigt für ein Konto mit Auszug aber ohne Auszug jetzt den getippten Stand** mit leerem „Auszug bis“ und gesperrt (`aus_auszug` bleibt). Das Feld lässt sich dort nicht ändern, der Wert kommt aus der Datei; kein Fall in den Datensätzen.

- **E.8a, das Ist des Vertrags enthält auch Zahlungen von Mitzahlern aus angelegten Zeiträumen.** Das Soll hat dafür nur den erwarteten Anteil laut Besetzung (wo es keinen Zeitraum gibt); der offene Anteil eines Zeitraums ist in einem vergangenen Monat null. Der Vertrag zeigt dann ein Ist über dem Soll. → Opus: entschieden, das Soll nimmt den vereinbarten Anteil des Zeitraums mit (siehe oben).
- **E.8a, `_vertragsenden` filtert über `vertraege.police_vertraege()`, nicht über die `auszahlungen`.** Zwei Rentenquellen auf demselben Konto lassen in `_policen_lesen` nur die letzte Police stehen; ein Vertrag der ersten behält so sein gemessenes Ende wie bisher. Der Zweig ohne Police in `_vertragsenden` ist damit nur in diesem Randfall erreichbar. → Opus: bestätigen, oder den Zweig samt `geladen` entfernen.
- **E.8a, der Check der Konten setzt keine Pausen (Wegfall-Zeilen) an.** Er rechnet die Verträge, wie sie ohne Plan standen. Ein Vertrag auf einem durchlaufenden Konto zählt jetzt auf dem deckenden Konto, wie im Monatsmodell.
- **E.8a, Objekt-Ist je Konto.** Das Ist sind alle Buchungen des Blocks `objekt` auf dem Konto, auf dem sie liegen; das Soll liegt auf dem Konto der Miete. Liegen Kosten auf einem anderen Konto, weichen die Konten gegenläufig ab, der Haushalt nicht.
- **E.8a, die Spaltenbezeichnung „vertraege“** steht in `treffer.NAMEN` als „Verträge“; die übrigen Spalten zeigen weiter ihre Kennung.
