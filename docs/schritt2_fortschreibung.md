# Schritt 2: Eine Fortschreibung für beide Vorschauen

Arbeitsplan für die Umsetzung, geschrieben für ein Modell, das ihn Teil für
Teil abarbeitet (Claude Sonnet). Gesamtplan: `docs/Neufassung_plan.md`.
Begriffe: `CONTEXT.md`. Stand des Codes beim Schreiben: nach Schritt 1
(`08b2054`).

## Ziel in einem Satz

Kontoprognose und Hochrechnung bekommen ihre fortgeschriebenen Posten aus
einer gemeinsamen Messung und gemeinsamen Verfahren. Jede Vorschau wählt nur
noch Fenster, Verfahren und Ausschlüsse. Keine einzige Zahl und kein Text auf
einer Seite ändert sich.

## Was „gleich“ hier heißt

Jeder Teilschritt ist **gleich**. Nach jedem Teilschritt gilt:

```bash
export FINCTL_DATEN="$HOME/Library/Application Support/Finance OS Entwicklung"
.venv/bin/python -m pytest -q
FINCTL_TESTDATEN=muster .venv/bin/python -m pytest -q
.venv/bin/python tests/referenz.py pruefen
```

Ändert ein Teilschritt Vorlagen oder Routen (2.3 kann das), kommt
`.venv/bin/python -m pytest -m browser -n 0` dazu; der Gesamtlauf schließt die
Browsertests aus.

Alle drei grün, und zwar `pruefen` **ohne** `--nur-zahlen`: Die Rechenwege
stehen als Text auf den Seiten („Schnitt … über 6 vollständige Monate …“).
Auch ein geändertes Wort darin ist ein Fehler.

## Regeln für jede Sitzung

1. **Ein Teilschritt pro Sitzung.** Lies vorher `CLAUDE.md`, `CONTEXT.md`
   und diesen Plan. Mach nichts aus späteren Teilschritten.
2. **Die Referenz wird in Schritt 2 nie neu geschrieben**, auch nicht „nur
   kurz“. Ausnahme ist allein Teilschritt 2.0, der eine neue Ebene anlegt.
   Zeigt `pruefen` einen Unterschied, ist der Code falsch, nicht die
   Referenz.
3. **Unterschiede zwischen den Vorschauen werden benannt, nicht
   angeglichen.** Wer eine Abweichung findet, die „offensichtlich ein Fehler“
   ist, trägt sie in die Liste am Ende dieses Plans ein und lässt sie stehen.
   Angleichen ist eine gewollte Änderung und gehört in einen späteren Schritt.
4. **Abbruch statt Raten:** Bleibt `pruefen` nach zwei Erklärungsversuchen
   rot, hör auf. Committe nichts. Schreib in die Antwort, welche Datei und
   welche Zahl abweicht und was du vermutest.
5. **Lint-Sperren:** Keine neue Funktion über Verzweigungsgrad 10, nichts
   Neues in `ZU_VERZWEIGT` (`tests/test_lint.py`). Wird eine gelistete
   Funktion kleiner, Eintrag senken oder streichen; der Test verlangt das.
6. **Kommentare erklären das Warum, mit erfundenen runden Zahlen.** Keine
   Beträge, Konten oder Anbieter aus den Daten (`tests/test_leck.py`).
7. **Commit** nur mit den Dateien des Teilschritts (`git add <pfade>`, nie
   `-a`). In diesem Checkout arbeiten andere Sitzungen mit.

## Bestand: die zwei Herleitungen heute

**Kontoprognose** (je Konto, `finctl/forecast/konten.py`):
`abgeleitete_posten` stellt Fenster und Ausschlüsse zusammen und ruft
`engine.derive_recurring`. Das fragt Monatssummen je Kategorie ab und wählt je
Kategorie einen von vier Wegen (`_posten_fuer_kategorie`): Schnitt,
Jahresposten mit Takt, Median, verrutschter Buchungstag. Heraus kommen
`RecurringItem`s, der Rechenweg als Dict in `herkunft`.

**Hochrechnung** (Haushalt, `finctl/forecast/jahre.py`):
`_base_kategorien` ruft `abgleich.measure_kategorien`. Das ordnet jeden Teil
per `CASE` dem ersten passenden Block zu und summiert je Block und Kategorie
über das Haushaltsfenster (`abgleich.fenster`, zwölf Monate). Daraus wird
`round(summe / monate * 12)` je Kategorie, das `project` mit Inflation
fortschreibt. Der Rechenweg sind `herkunft.Posten`.

**Daneben**, und alle müssen nach Schritt 2 aus derselben Quelle lesen:

| Wer | Liest heute |
|---|---|
| `prognosebasis.vergleich` (`/annahmen`) | beide Seiten getrennt, um ihren Unterschied zu zeigen |
| `treffer` | `abgleich.measure` und `abgeleitete_posten(stichtag=…)` |
| `ohne_objekt` | `abgleich.measure_kategorien` |
| `abgleich.build` und `planned` | `abgleich.measure` |
| `konten.wegfall_posten` | `abgeleitete_posten` zweimal, mit und ohne Reihe |

**Bleibt in Schritt 2 außen vor**, weil es keine Fortschreibung ist: Gehalt
(Median beziehungsweise Untergrenze), Kredite (Tilgungspläne), Objekte
(Annahme), Planzeilen (`szenarien.messung`), Rentenquellen.

## Die Unterschiede, die erhalten bleiben müssen

Das ist die wichtigste Liste dieses Plans. Jeder Punkt wird zu einem
benannten Parameter, keiner wird angeglichen.

1. **Fenster.** Kontoprognose: je Konto, endet mit dem letzten vom Auszug
   dieses Kontos ganz gedeckten Monat (`_erster_offener_monat`), variable
   Kosten über `window_months`, Fixkosten über `window_months_fixkosten`,
   gezählt ab dem ersten Auszug des Kontos (`_fenstermonate`). Hochrechnung:
   ein Fenster für alle Konten, endet mit dem letzten Monat, den **alle**
   Konten decken (`letzter_vollstaendiger_monat`), zwölf Monate, beginnt
   frühestens mit dem ersten vollen Monat.
2. **Umbuchungen.** Kontoprognose: Kategorie muss gesetzt sein, und
   `kind <> 'transfer'`, außer auf durchlaufenden Konten oder bei Teilen mit
   `transfer_account_id` auf ein durchlaufendes Konto. Hochrechnung:
   `mgmt_category_id NOT LIKE 'transfer/%'`, Teile ohne Kategorie zählen
   unter `''`. Das sind zwei verschiedene Regeln; eine Kategorie mit Art
   „transfer“ außerhalb von `transfer/` fällt nur bei einer heraus.
3. **Kredite.** Kontoprognose schließt die Kinder von `kredit` aus. Die
   Hochrechnung misst sie in den Block `kredit`, nimmt den Block aber nicht
   aus der Basis (`FROM_BASE`).
4. **Verträge.** Kontoprognose nimmt erklärte Verträge aus der Messung
   (`abos.ausschluesse`: Hashes oder Kategorie, Gegenpartei, Betrag) und
   bucht sie nach Vertrag. Die Hochrechnung lässt sie in der Basis und zieht
   erst bei Kündigung ab (`_vertragsenden`).
5. **Einmaliges.** Hochrechnung schließt die Hashes einmaliger Planzeilen aus
   (`szenarien.einmalig_zugeordnet`). Die Kontoprognose nicht.
6. **Abwahl auf `/annahmen`.** Kontoprognose: Kategorie fällt ganz heraus.
   Hochrechnung: nur in den Blöcken aus `FROM_BASE`.
7. **Kontenmenge.** Kontoprognose: aktive geparste Konten. Hochrechnung: jede
   Buchung im Hauptbuch.
8. **Rundung.** Hochrechnung rundet **je Kategorie auf Haushaltsebene**:
   erst über alle Konten summieren, dann `round(c / monate * 12)`. Wer je
   Konto rundet und dann addiert, bekommt Centabweichungen. Schnitt:
   `round(sum / fenster_monate)`. Median: das obere mittlere Element,
   `sortiert[len // 2]`, nicht `statistics.median`. Jahresposten: Median der
   Blocksummen nach derselben Regel; Takt auf 2, 3, 4, 6 oder 12, bei
   Gleichstand der kürzere.
9. **Steigerung.** Kontoprognose: `escalation_pa` je Posten ab dem
   gemessenen Monat. Hochrechnung: Inflation von der Mitte des Fensters zur
   Mitte des Jahres. Das ist Sache der Vorschau, nicht der Fortschreibung.
10. **Groß- und Kleinschreibung.** `counterparty_norm LIKE ?` in SQLite ist
    für ASCII unabhängig von Groß- und Kleinschreibung. Wer Filter nach
    Python verlegt, muss das nachbauen. Besser: Filter bleiben in SQL.
11. **Stichtag.** `treffer` rechnet mit `stichtag`/`until` so, als wäre heute
    ein früherer Monatserster. Jede neue Funktion braucht das Ende des
    Fensters als Eingabe, nie `date.today()`.

## Die Teilschritte

### 2.0 Ableitungsreferenz (Sicherheitsnetz)

**Warum:** Die Seiten zeigen nicht jede Zwischenzahl. Ein Posten, der sich
verschiebt, aber in einer Summe aufgeht, fällt auf keiner Seite auf.

**Was:** `tests/referenz.py` bekommt eine dritte Ebene `ableitung/` neben
`hauptbuch/` und `seiten/`, als JSON, sortiert, ohne Zeitstempel:
- je aktivem geparsten Konto die Ergebnisse von `abgeleitete_posten`:
  Kategorie, Betrag, `every_months`, `starts`, `ends`, `escalation_pa`,
  Herkunft (Quelle und Herleitungstext);
- je Konto `account_forecast` mit Horizont 12 und 60: Monat, Endstand,
  Tiefpunkt;
- `jahre._base_kategorien` mit und ohne `auch_abgewaehlte`;
- die Jahre von `jahre.project`, aufgerufen wie in
  `finctl/web/routen/annahmen.py` (`_jahresrechnung`): je Jahr die Blöcke und
  je Block die Posten (Bezeichnung, Cent, Quelle);
- `abgleich.build(conn, abgleich.planned(conn))`,
  `prognosebasis.vergleich(conn)`, `treffer.pruefen(conn)`.

`pruefen` vergleicht die Ebene streng; `--nur-zahlen` lässt sie unberührt.

**Ablauf:** Code committen. Dann einmal
`tests/referenz.py schreiben` mit `FINCTL_DATEN` auf der
Entwicklungskopie. Das legt nur die neue Ebene an, weil sich sonst nichts
geändert hat; danach `pruefen` grün. Die Referenz liegt im Datenordner, nie
im Repository.

**Fertig wenn:** `pruefen` grün; ein absichtlich geänderter Schnitt (lokal
ausprobieren, nicht committen) lässt `ableitung/` rot werden.

### 2.1 Eine Messung

**Festgelegt am 04.10.2026.** Signatur und Ausschluss stehen unten fest; die
Sitzung baut sie so und entscheidet nichts davon neu.

**Was:** Neues Modul `finctl/forecast/messung.py` mit genau einer Abfrage:
Monatssummen der Teile je Konto, Kategorie, (optional) Block und Monat. Wer
misst, ruft sie und fasst in Python zusammen. Summen über ganze Cent sind
exakt, egal in welcher Reihenfolge addiert wird.

```python
@dataclass(frozen=True, slots=True)
class Ausschluss:
    """Welche Teile eine Messung nicht sieht, VOR dem Summieren.

    Nur was je Buchung entschieden werden muss. Kategorien fallen NACH der
    Messung heraus (Kredite, `exclude_from_recurring`, Abwahl auf /annahmen),
    wie heute auch: dort entscheidet jede Vorschau selbst.
    """
    #: "praefix": COALESCE(s.mgmt_category_id, '') NOT LIKE 'transfer/%'
    #:            (Hochrechnung, Abgleich, Prognosebasis)
    #: "art":     c.kind IS NULL OR c.kind <> 'transfer', dazu Teile mit
    #:            transfer_account_id auf ein durchlaufendes Konto (Kontoprognose)
    umbuchung: Literal["praefix", "art"] = "praefix"
    #: Nur bei "art": das Konto ist selbst durchlaufend, Umbuchungen zaehlen.
    umbuchungen_zaehlen: bool = False
    #: Nur bei "art": Konten mit der Rolle `durchlaufend`.
    durchlaufend: frozenset[str] = frozenset()
    #: False: Teile ohne Kategorie fallen heraus (Kontoprognose).
    #: True:  sie zaehlen unter der Kategorie '' (alle anderen).
    ohne_kategorie: bool = True
    #: Einzelne Buchungen raus: erklaerte Vertraege samt Reihe, Wegfall-Reihen,
    #: einmalige Planzeilen.
    hashes: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class Monatssumme:
    konto: str
    kategorie: str          # '' fuer Teile ohne Kategorie
    block: str | None       # nur mit je_block=True, sonst None
    monat: str              # 'JJJJ-MM'
    cents: int


def monatssummen(conn, *, von: date | str, bis: date | str | None = None,
                 ausschluss: Ausschluss = Ausschluss(),
                 konten: frozenset[str] | None = None,
                 je_block: bool = False) -> list[Monatssumme]:
    """von und bis einschliesslich, auf booking_date. bis=None: kein Ende.
    konten=None: alle Buchungen. Sortiert nach (konto, kategorie, block, monat)."""


def summiere(zeilen: Iterable[Monatssumme],
             schluessel: Callable[[Monatssumme], K]) -> dict[K, int]:
    """Cent je Schluessel. Nullsummen bleiben drin, wie bei SQL-GROUP BY."""
```

**Wer was übergibt** (alles „gleich“):

| Aufrufer | Aufruf |
|---|---|
| `abgleich.measure(conn, f, ohne)` | `von=f.von, bis=f.bis, ausschluss=Ausschluss(hashes=ohne), je_block=True`, summiert nach `block` |
| `abgleich.measure_kategorien` | wie oben, summiert nach `(block, kategorie)` |
| `abgleich.total_excluding_transfers` | wie oben, Gesamtsumme |
| `prognosebasis._monate(conn, f)` | `von=f.von, bis=f.bis`, summiert nach `(kategorie, monat)` |
| `engine.derive_recurring` | `von=min(since, since_fixkosten or since), bis=until, konten={account_id}`, `Ausschluss(umbuchung="art", umbuchungen_zaehlen=include_transfers, durchlaufend=…, ohne_kategorie=False, hashes=…)`, summiert nach `(kategorie, monat)` |

- **`derive_recurring` behält seine Signatur.** `ohne` kommt weiter als
  Liste von Dicts; die Funktion sammelt daraus die `dedup_hashes`. Die Zweige
  für Regeln mit `kategorie`, `gegenpartei` und `betrag_cents` in
  `engine._ausschluss` benutzt niemand mehr: `abos.ausschluesse` liefert seit
  der Reihe nur Hashes, und die Tests ebenso. Sie entfallen. Damit ist auch
  Punkt 10 der Liste oben (Groß- und Kleinschreibung bei `LIKE`) erledigt.
- **Mehrere Hash-Listen werden eine Menge.** Heute stehen Vertrags-Hashes und
  Wegfall-Hashes als zwei `NOT IN` nebeneinander. Eine Vereinigung ist
  dasselbe, weil `dedup_hash` `NOT NULL` ist (`schema.sql`).
- **Den Block rechnet nur, wer ihn braucht.** `abgleich._case_expression`
  liest über `objekte.prognosen()` die Konfiguration; ohne `je_block` wird es
  nicht aufgerufen.
- **Die Reihenfolge ist fest:** `ORDER BY` auf alle Schlüssel. Heute liefert
  `GROUP BY` in SQLite dieselbe Ordnung, aber nur zufällig.
  `engine._nach_kategorie` wirft variable Kategorien vor `since` in Python
  weg; das bleibt dort, an den neuen Zeilen statt an `sqlite3.Row`.
- **Importe ohne Kreis:** `abgleich` und `engine` importieren `messung`.
  `messung` braucht von `abgleich` nur die Blockzuordnung und importiert es
  deshalb erst innerhalb der Funktion, wenn `je_block` gesetzt ist. Ein Import
  oben in der Datei wäre ein Kreis.

**Nicht in 2.1**, weil sie Buchungen statt Monatssummen brauchen oder eine
eigene Regel haben. Jede bekommt einen Eintrag unter „Gefundene
Abweichungen“, wo eine dazugehört:
- `szenarien.messung`, `szenarien.vorschlaege`, `jahre._vertragsenden`:
  Buchungen einer Reihe, nicht Summen.
- `jahre.verkaeufe`: Miete und Kosten eines einzelnen Objekts.
- `jahre.gehalt_median_cents`: eigene Kategorie, eigenes Fenster.
- `treffer.konten` (Ist je Konto): eine dritte Umbuchungsregel, die
  Präfix UND Art ausschließt und dazu `investment/` und Kaufnebenkosten.
  Kommt in 2.6 dazu, dann mit eigenem Feld im `Ausschluss`.

**Prüfung zusätzlich:** `tests/test_messung.py` mit einem Hauptbuch im
Speicher (wie `tests/test_ohne_objekt.py`): je Feld des `Ausschluss` ein
Fall, der genau eine Buchung hinein- oder herausnimmt, dazu ein Teil ohne
Kategorie unter beiden Einstellungen.

**Fertig wenn:** Die fünf Abfragen der Tabelle stehen nur noch in
`messung.py`; `engine._ausschluss` ist weg; `pruefen` grün, Ableitungsebene
eingeschlossen.

### 2.2 Verfahren als reine Funktionen

**Was:** Neues Modul `finctl/forecast/verfahren.py`. Hierher wandern aus
`engine.py` die Wege von Monatswerten zu einem Posten: `_schnittposten`,
`_medianposten`, `_jahresposten` mit `_bloecke` und `_takt`,
`_verrutschter_buchungstag`, `_langes_fenster`. Dazu kommt das
Hochrechnungsverfahren „Summe aufs Jahr“ (`round(c / monate * 12)`).

- Eingabe ist eine Monatsreihe (`list[tuple[str, int]]`) und die
  Fenstergröße, nie eine Datenbankverbindung.
- Die Wahl des Wegs (`_posten_fuer_kategorie`) wird eine Tabelle je Vorschau:
  welche Art Kategorie (Fixkosten, variabel, Einnahme) welches Verfahren mit
  welchem Fenster bekommt. Für die Kontoprognose ergibt die Tabelle genau die
  heutige Verzweigung, für die Hochrechnung „Summe“ für alles.
- Die Namen der Verfahren folgen `CONTEXT.md`: `median`, `schnitt`, und
  Platz für `juengst` aus Schritt 3, das hier **nicht** gebaut wird.

**Prüfung zusätzlich:** Unit-Tests je Verfahren mit erfundenen Reihen,
darunter die Randfälle: gerade Anzahl Monate beim Median, Monate ohne
Buchung beim Schnitt, zwei benachbarte Raten als ein Jahresposten,
Gleichstand beim Takt.

**Fertig wenn:** `engine.py` enthält keine Ableitungswege mehr, nur noch
`derive_recurring` als dünnen Aufruf und `project`. `pruefen` grün.

### 2.3 Ein Rechenweg-Typ

**Was:** `RecurringItem.herkunft` (ein Dict mit `quelle`, `herleitung`,
`verweis`) wird ein `herkunft.Posten` wie in der Hochrechnung, oder eine
Liste davon. Vorlagen und Aufrufer, die `herkunft["…"]` lesen, lesen die
Felder.

**Fallen:**
- Der Text der Herleitung steht auf den Seiten. Er muss Zeichen für Zeichen
  gleich bleiben.
- Das Dict entsteht nicht nur in `derive_recurring`, sondern an rund zehn
  Stellen in `konten.py` (Budgets, Verträge, Auffüllen, Planzeilen) und an
  `OneOff`. Alle umstellen oder keine.
- Jinja liest `h.quelle` aus einem Dict und aus einer Dataclass gleich,
  Python nicht: `ohne_objekt.py` benutzt `herkunft.get(...)`.
- Schnittstellen unter `/api/…` geben die Herkunft als JSON aus, und ihre
  Antworten stehen in der Referenz. Was dort ankommt, muss genau die heutigen
  Schlüssel haben, keinen mehr. Eine Methode am Posten, die das heutige Dict
  liefert, ist der sichere Weg.

Erst alle Stellen finden (`grep -rn "herkunft" finctl`), dann umstellen.

**Fertig wenn:** Es gibt einen Rechenweg-Typ. `pruefen` grün, auch die
Textebene.

### 2.4 Die Fortschreibung als Ergebnis

**Festgelegt nach 2.2 (04.10.2026):** Ein Verfahren rechnet auf einer
Monatsreihe. **Welche Reihe** das ist, entscheidet die Vorschau, nicht das
Verfahren: die Reihe eines Kontos (Kontoprognose) oder die Reihe des
Haushalts, über alle Konten addiert (Hochrechnung). Damit rundet die
Hochrechnung von selbst einmal auf der Haushaltssumme (Punkt 8 der Liste
oben), und Jüngst aus Schritt 3 lässt sich in beiden Vorschauen benutzen,
ohne neu gebaut zu werden.

**Was:** In `finctl/forecast/fortschreibung.py`:

```python
@dataclass(frozen=True, slots=True)
class Vorschau:
    """Wie eine Vorschau fortschreibt. Ein Wert, kein Wissen im Code."""
    reihe: Literal["konto", "haushalt"]
    regeln: verfahren.Regeln
    ausschluss: messung.Ausschluss
    je_block: bool          # Hochrechnung: ja, Kontoprognose: nein
    # dazu die Fenster und Grenzen, die heute in abgeleitete_posten und
    # derive_recurring zusammengesucht werden


def fortschreibung(conn, vorschau: Vorschau, *, konten, ...) -> list[Posten]:
    """Messung, Reihe bilden, je Reihe `verfahren.wahl`."""
```

- Ein Posten trägt seinen Schlüssel: Konto (bei `reihe="haushalt"` leer),
  Kategorie und Block (bei `je_block=False` leer). Eine Kategorie kann in der
  Hochrechnung in zwei Blöcken stehen, etwa Kosten eines Objekts mit
  Prognose und eines ohne. Der Block gehört deshalb zum Schlüssel der Reihe.
- **`verfahren.wahl` lernt „summe“.** Heute deklariert die Tabelle
  `HOCHRECHNUNG` das Verfahren, `wahl` kennt es aber nicht: Mit dieser
  Tabelle aufgerufen fiele jede Kategorie unter der Mindestzahl stumm
  heraus, der Rest bekäme einen Median. „summe“ heißt:
  `summe_aufs_jahr(sum(betraege), fenster_monate)`, ohne Mindestzahl, ohne
  langes Fenster. Ein Test ruft `wahl` mit `HOCHRECHNUNG` und prüft genau
  das.
- `konten.abgeleitete_posten` wird zum Aufruf mit `reihe="konto"` und der
  Konfiguration aus `forecast.yaml`, gelesen wie heute.

**Fertig wenn:** `abgeleitete_posten` ist höchstens ein Dutzend Zeilen und
liefert dieselben Posten; `wahl` rechnet „summe“. `pruefen` grün,
Ableitungsebene eingeschlossen.

### 2.5 Die Hochrechnung liest dieselbe Fortschreibung

**Was:** `jahre._base_kategorien` ruft die Fortschreibung mit
`reihe="haushalt"`, `je_block=True`, den Regeln `HOCHRECHNUNG`, dem
Haushaltsfenster (`abgleich.fenster`) und dem Ausschluss nach den Punkten 2,
5 und 7 der Liste oben. Die Abwahl (Punkt 6) bleibt in `_base_kategorien`,
weil sie nur für die Blöcke aus `FROM_BASE` gilt. Die Fortschreibung
addiert die Konten, bevor das Verfahren rechnet; `_base_kategorien` rundet
nichts mehr selbst.

**Falle:** `fenster_monate` ist hier die Zahl der Monate des
Haushaltsfensters (`f.monate`), nicht die eines Kontos. Konten, die später
beginnen, verkürzen das Haushaltsfenster nicht; so ist es heute.

**Fertig wenn:** `jahre.py` fragt das Hauptbuch für die Basis nicht mehr
selbst ab und ruft `summe_aufs_jahr` nicht mehr selbst auf. `pruefen` grün.

**Dazu, nach 2.4 festgelegt:** Wer eine Vorschau baut, steht bei seiner
Vorschau, nicht im Kern. Seit 2.4 liegt `fortschreibung.kontoprognose()` im
Kern und importiert von dort `abos`, `prognosebasis` und sogar `konten`
(`_as_month`), obwohl `konten` selbst den Kern importiert. Damit kennt der
Kern doch wieder die Konfiguration, die als Wert hineingehen sollte.
- `kontoprognose()` zieht nach `konten.py`, neben `abgeleitete_posten`.
- Der Bauer der Hochrechnung entsteht in `jahre.py`, nicht im Kern.
- Die Vorgabe der Steigerung (`fortschreibung.steigerung`, liest
  `assumptions`) wandert mit: Der Bauer setzt `escalation_pa`, der Kern
  nimmt den Wert.
- `fortschreibung.py` importiert danach aus `finctl` nur `messung` und
  `verfahren`. Ein Test in `tests/test_fortschreibung.py` prüft das über den
  Syntaxbaum der Datei, damit es so bleibt.

### 2.6 Die Nebenrechnungen umstellen

**Was:** `prognosebasis.vergleich`, `treffer`, `ohne_objekt`,
`abgleich.build` und `planned`, `konten.wegfall_posten` lesen aus der
Fortschreibung beziehungsweise der Messung. Ein Teilschritt je Datei ist
erlaubt, wenn eine Sitzung sonst zu groß wird.

`prognosebasis.vergleich` zeigt weiter beide Spalten. Der Unterschied ist
jetzt aber kein Vergleich zweier Rechnungen mehr, sondern zweier
Konfigurationen derselben Rechnung. Der Text der Seite bleibt in Schritt 2
gleich; eine neue Erklärung gehört zu Schritt 6.

**Stand bei der Umsetzung (04.10.2026):** Von den fünf Dateien maß nur noch
`treffer.konten` selbst (das Ist je Konto, mit der dritten Umbuchungsregel). Die
anderen vier lesen seit 2.1 bis 2.5 aus der Messung und der Fortschreibung:
`prognosebasis` über `messung.monatssummen`, `jahre._base_kategorien` und
`konten.abgeleitete_posten`; `ohne_objekt` und `abgleich` über `measure` und
`measure_kategorien`; `wegfall_posten` über `ableiten`, das
`abgeleitete_posten` ruft. Ihre übrigen `execute` schlagen Konten, Kategorien und
Auszüge nach, messen nichts. Umgestellt ist deshalb nur `treffer`.

**Fertig wenn:** Keine Datei außer `messung.py` misst selbst. `pruefen` grün.

### 2.7 Aufräumen

**Was:** Tote Funktionen und Aliase löschen. Einträge in `ZU_VERZWEIGT`
senken oder streichen, wo die Funktionen kleiner geworden sind. Die Liste
„Gefundene Abweichungen“ unten durchsehen und jeden Eintrag mit einem Satz
begründen. Sie ist die Eingabe für die gewollten Schritte 3 und 4.

**Aus dem Review nach 2.5 und 2.6 (04.10.2026):**
- **Der Bauer der Kontoprognose an einen Ort.** `kontoprognose()` steht in
  `konten.py`, seine Helfer `vorschau_konto`, `hashes_aus` und `steigerung`
  in `engine.py`. Sie ziehen zu `kontoprognose()`; `derive_recurring` ruft
  sie von dort.
- **`_fenstermonate` einmal je Konto.** Seit 2.4 fragt `_einstellung` die
  Monatszahl je Kategorie neu ab, eine Abfrage auf `statements` je Reihe.
  Ohne messbare Wirkung, aber unnötig: je Konto einmal rechnen und
  weitergeben.
- **Kategorie-Kennungen sind klein, und das wird geprüft.** Seit 2.6 filtert
  `treffer` Kategorien in Python mit `startswith`; vorher tat es `LIKE` in
  SQLite, das Groß- und Kleinschreibung bei ASCII nicht unterscheidet. Die
  Oberfläche legt Kennungen klein an, eine von Hand geschriebene
  `taxonomy.yaml` aber nicht zwingend. Statt jeden Vergleich abzusichern:
  `taxonomy.load_into_db` lehnt eine Kennung mit Großbuchstaben mit einer
  Meldung ab, und ein Test hält das fest. Danach ist jeder Präfixvergleich in
  Python so sicher wie der in SQL, auch die künftigen.

**`Posten.cents` hat seit 2.3 zwei Bedeutungen**, und das gehört in den
Docstring von `herkunft.Posten`: In der Hochrechnung ist ein Posten ein
Summand, die Posten eines Blocks ergeben seine Zahl. In der Kontoprognose
beschreibt ein Posten eine Reihe, und `cents` ist der Betrag je Termin, beim
Kredit die erste Rate. Dort ergibt keine Summe von Posten eine angezeigte
Zahl. Wer in Schritt 3 die Wirkung nach Ursachen aufteilt, darf nur Posten
der ersten Art addieren. Ein Test hält fest, dass `herkunft.summe` nie auf
Posten der Kontoprognose angewendet wird, oder die zwei Bedeutungen werden
zwei Felder.

**Stand bei der Umsetzung (04.10.2026):**
- **Bauer an einen Ort:** `steigerung`, `hashes_aus` und `vorschau_konto` stehen
  jetzt in `konten.py` vor `kontoprognose()`, das `vorschau_konto` direkt ruft.
  `engine.derive_recurring` importiert es erst in der Funktion; `konten`
  importiert `engine` ebenso nur in Funktionen, ein Kreis, der beim Laden nicht
  zuschlägt. `engine.py` kennt weder `messung` noch `verfahren` mehr.
- **Fenstermonate:** `fortschreibung()` rechnet die `Einstellung` je Konto einmal
  und gibt sie weiter; ein Test zählt die Abfragen auf `statements` (zwei Konten,
  sechs Reihen, zwei Abfragen).
- **Kleine Kennungen:** `taxonomy.kennungen_pruefen` lehnt eine Kategorie-Kennung
  mit Großbuchstaben ab, bevor `load_into_db` etwas schreibt; zwei Tests in
  `tests/test_rules.py` (Ablehnung ohne halb geladene Kategorien, und die
  mitgelieferte Taxonomie besteht).
- **`Posten.cents`:** Der Docstring von `herkunft.Posten` nennt die zwei
  Bedeutungen. Ein Test in `tests/test_verfahren.py` liest den Syntaxbaum von
  `finctl/` und verlangt, dass nur `jahre.py` `herkunft.summe` benutzt. Es blieb
  bei einem Feld; wer in Schritt 3 die Wirkung nach Ursachen aufteilt und dafür
  Posten der Kontoprognose addieren will, trennt sie dann in zwei Felder.
- **Tot und gelöscht:** `konten.date_vor` (nirgends gerufen); in `ops.py` zehn
  durchgereichte Namen, die niemand über `ops` las (`_FREQ`, `_anzeigenamen`,
  `_as_month`, `_floor_for`, `_herkunft_konto`, `_herkunft_planzeile`,
  `_income_overrides`, `_planposten`, `date_vor`, `forecast_config`) und die zwei
  Aliase `_stichtag` und `_saldo_zum`, deren letzte Nutzer (`/konten`, zwei
  Tests) jetzt `forecast.stichtag` ansprechen.
- **Tot und bewusst geblieben:** `engine.planned_amount_cents` und
  `engine.funding_legs` (nur Tests rufen sie, `konten.py` begründet bei
  `account_forecast`, warum sie als Bausteine bleiben) sowie `jahre.SPECIAL` und
  `jahre.IGNORED` (nur `tests/test_jahre.py` liest sie, dort halten sie die
  Aufteilung der Blöcke zusammen). `derive_recurring` hat keinen Aufrufer im Code
  mehr, nur in Tests; es bleibt die Schnittstelle, die der Plan in 2.1 zugesagt hat.
- **`ZU_VERZWEIGT`:** Kein Eintrag rutschte unter die Schwelle, keiner kam dazu.
  Vier Einträge standen höher, als gemessen wird, und sind auf den Wert von
  heute gesenkt (`cli.init`, `categorize`, `api_szenario_zeile`,
  `_zwecktext_funde`); sie stammen aus früheren Umbauten, nicht aus Schritt 2.
- **Gefundene Abweichungen:** Jeder Eintrag unten hat jetzt ein „Warum“ und sagt,
  ob Schritt 3 oder 4 ihn berührt.

**Fertig wenn:** Beide Läufe der Suite und `pruefen` grün, `ruff` ohne Fund.

## Wo ein stärkeres Modell sich lohnt

- **Vor 2.1:** den `Ausschluss` und die Signatur der Messung einmal mit Opus
  festlegen. Erledigt, siehe 2.1.
- **Nach 2.5:** `/code-review` über die Teilschritte 2.1 bis 2.5.

Alles andere ist Abarbeiten gegen die Referenz.

## Auftrag für eine Sitzung (Vorlage)

> Setze Teilschritt 2.N aus `docs/schritt2_fortschreibung.md` um. Lies
> vorher `CLAUDE.md`, `CONTEXT.md` und den ganzen Plan. Arbeite mit
> `FINCTL_DATEN` auf der Entwicklungskopie. Fertig ist der Teilschritt, wenn
> beide Läufe der Suite und `tests/referenz.py pruefen` (ohne
> `--nur-zahlen`) grün sind. Schreib die Referenz nicht neu. Bleibt
> `pruefen` rot, hör auf und berichte. Committe nur die Dateien dieses
> Teilschritts.

## Gefundene Abweichungen

Hier tragen die Sitzungen ein, was zwischen den Vorschauen verschieden ist
und vielleicht nicht sein sollte. Jeder Eintrag: wo, was, und ob es eine
Zahl ändern würde. Nichts davon wird in Schritt 2 behoben. Seit 2.7 hat jeder
Eintrag ein **Warum** (der eine Satz, der die Abweichung erklärt) und ein
**Schritt** (ob 3 oder 4 sie anfassen muss, und sonst „keiner“). Die Liste ist
die Eingabe für diese beiden gewollten Schritte.

- **2.1, `treffer.konten` (Ist je Konto):** Eine dritte Umbuchungsregel. Sie
  schließt Präfix `transfer/` UND Art `transfer` aus, dazu `investment/` und
  Kaufnebenkosten. Seit 2.6 ist sie ein Wert im `Ausschluss`
  (`umbuchung="beide"`); `investment/`, Kaufnebenkosten und `kredit/` (nur ohne
  Tilgungsplan) fallen danach in `treffer._ist_zaehlt` heraus, wie jede
  Kategorie NACH der Messung. Die dritte Regel ist damit benannt, nicht
  angeglichen. Eine Zahl ändert das nicht. Das `LIKE` von SQLite unterscheidet
  ASCII-Groß- und Kleinschreibung nicht, `startswith` schon; alle Kategorien
  stehen klein (seit 2.7 lehnt `taxonomy.kennungen_pruefen` andere ab).
  **Warum:** Das Ist beantwortet „was hat das Konto verbraucht?“ und lässt aus,
  was keine Fortschreibung beschreiben kann; die beiden anderen Regeln
  beantworten „was schreibt die Vorschau fort?“. **Schritt:** keiner; wer die
  Regeln angleicht, ändert den Treffer-Check, den auch die Wirkung in Schritt 3
  als Vorbild nimmt.
- **2.1, `jahre.gehalt_median_cents`:** Eigene Kategorie, eigenes Fenster, eigene
  Abfrage; gehört nicht zur Fortschreibung (Median beziehungsweise Untergrenze).
  Bleibt bis auf Weiteres, ändert keine Zahl. **Warum:** Das Gehalt zählt je
  Gehaltsmonat über vierundzwanzig Monate, nicht je Kategorie über das
  Fenster der Vorschau, und der Haushalt kann es mit einer Untergrenze
  überstimmen. **Schritt:** 4; sobald jede Reihe einen Takt hat, ist das Gehalt
  eine Reihe mit Takt „monatlich“, und zu prüfen ist, ob der Median dann ein
  Verfahren der Fortschreibung wird.
  **Entschieden in Schritt 4 (Entscheidung 11), nichts offen:** Das Gehalt bleibt
  beim Median. Es ist eine Reihe mit Takt monatlich, aber sein Block hat eine
  eigene Quelle (Median über 24 Gehaltsmonate, Untergrenze des Haushalts), und ein
  Gehaltswechsel oder eine Sonderzahlung ist dort schon behandelt; als Reihe zählte
  eine Sonderzahlung einmal je Jahr als eigene Reihe daneben. In der Kontoprognose
  hat 4.5 es abgesichert: Kategorien mit fester Zahl (`overrides`, der Gehaltsfloor)
  bekommen keine Posten aus Reihen.
- **2.1, `szenarien.messung`, `szenarien.vorschlaege`, `jahre._vertragsenden`,
  `jahre.verkaeufe`:** Sie lesen Buchungen einer Reihe oder eines Objekts, keine
  Monatssummen, und bleiben deshalb bei ihren eigenen Abfragen. **Warum:** Sie
  brauchen Datum, Gegenpartei und Hash der einzelnen Buchung (eine Planzeile
  misst „diese Reihe“, ein Wegfall nimmt „genau diese Buchungen“), und
  `messung.monatssummen` verwirft das beim Summieren. **Schritt:** 4; mit dem
  Takt je Reihe wird die Reihe ein Wert, und dann lässt sich entscheiden, ob
  ihre Abfrage zur Messung gehört.
  **Entschieden in 4.6, sie bleiben bei ihren Abfragen.** Seit 4.2 gibt es
  `messung.teile` (je Teil Konto, Kategorie, Tag, Cent, Gegenpartei, Kennung), und
  4.4 hat die Reihe zu einem Wert gemacht (`takt.Reihen`, `takt.beitrag_in_basis`);
  `szenarien.messung` und `jahre._vertragsenden` rechnen damit. Ihre Abfragen
  wählen aber nach Identität, nicht nach Fenster: eine Liste von Kennungen
  (`messung`, `_vertragsenden`), eine Kategorie samt Konto und Start
  (`vorschlaege`), ein Objekt (`verkaeufe`: `s.property_id`). `messung.teile` kennt
  nur das Ausschließen von Kennungen (`Ausschluss.hashes`), keine Auswahl. Sie zu
  nehmen hieße drei Parameter dazuzugeben (nur diese Kennungen, eine Kategorie, ein
  Objekt), und die vier Aufrufer änderten sich, ohne dass eine Zahl oder ein Text
  sich bewegt: Aufwand und Risiko ohne Gewinn. Was an ihnen Zahl war (der Beitrag
  einer Reihe), steht seit 4.4 an einer Stelle (Entscheidung 10 in Schritt 4).
  **Schritt:** keiner.
- **2.1, `total_excluding_transfers`:** Der Plan nennt „wie oben“ (mit Block).
  Umgesetzt ohne Block (`je_block=False`): die Gesamtsumme hängt nicht an der
  Zuordnung, und der Summentest in `abgleich.build` soll sie gerade daran
  messen. Gleiche Zahl, ein Konfigurationszugriff weniger je Aufruf.
  **Warum:** Mit Block gebildet, prüfte der Summentest die Zuordnung gegen sich
  selbst. **Schritt:** keiner.
- **2.2, `jahre.verkaeufe` und `jahre._vertragsenden`:** Beide rechnen
  `round(c / monate * 12)` selbst (Miete und Kosten eines Objekts, gemessene
  Jahressumme eines Vertrags), nicht über `verfahren.summe_aufs_jahr`. Gleiche
  Formel, andere Eingabe (eine Buchungsreihe statt Monatssummen). Auch 2.6 hat
  sie nicht umgestellt, weil sie keine der fünf Nebenrechnungen sind; Stand 2.7:
  unverändert. Ändert keine Zahl. **Warum:** Die Eingabe ist eine Buchungsreihe
  eines Objekts oder Vertrags, nicht die Monatsreihe einer Kategorie, die
  `summe_aufs_jahr` im Verfahren bekommt. **Schritt:** 4, zusammen mit dem
  Eintrag davor.
  **Erledigt in 4.6 für `verkaeufe`:** Miete und Kosten eines Objekts rechnen über
  `verfahren.summe_aufs_jahr`, ebenso die Anzeige des Rests in
  `jahre._gemessen_text`; dieselbe Formel, also keine Zahl anders. Für
  `_vertragsenden` ist es seit 4.4 anders gelöst: Es rechnet mit
  `takt.BeitragInBasis.im_jahr`, das den Beitrag der Reihen und den Rest zusammen
  rundet; das hier zu ersetzen ändert die Rundung um höchstens einen Cent und
  bleibt.
- **2.3, Ausgabe der Kontoprognose:** Intern trägt jeder Posten (`RecurringItem`,
  `OneOff`, `verfahren.Ergebnis`) ein `herkunft.Posten`. Die Ansicht
  (`account_forecast["herkunft"]`) bleibt ein Dict je Etikett, gebildet mit
  `Posten.als_herkunft()`: Seite, `/api/…` und `ohne_objekt` lesen es als JSON mit
  den heutigen Schlüsseln (bei Planposten dazu `kategorie`). Für die Zeilen
  „Kredit-Etikett“ und „ohne hinterlegte Herleitung“ gibt es keinen einen Betrag;
  `cents` ist dort die erste Rate beziehungsweise der Betrag im ersten Monat und
  geht nirgends in eine Zahl ein. Ändert nichts. **Warum:** Die Seite und die
  Schnittstelle stehen in der Referenz und dürfen in Schritt 2 weder Schlüssel
  gewinnen noch verlieren; `Posten.cents` ist in der Kontoprognose der Betrag je
  Termin, nicht ein Summand (Docstring von `herkunft.Posten`, Test in
  `tests/test_verfahren.py`). **Schritt:** 3; wer die Wirkung nach Ursachen
  aufteilt, addiert nur Posten der Hochrechnung, und muss er dabei Posten der
  Kontoprognose addieren, werden aus `cents` zwei Felder.
- **2.4, `verfahren.summe` gegen die anderen Verfahren:** Eine Kategorie, deren
  Fenster sich auf null aufhebt, bleibt in „summe“ ein Posten mit null (die
  Hochrechnung führt sie so weiter). Median, Schnitt und Jahresposten lassen
  einen Betrag von null herausfallen. Ändert keine Zahl, aber einen Posten mit
  null Cent, der nur in der Hochrechnung vorkommt. **Warum:** Die Blöcke der
  Hochrechnung sind die Summe ihrer Kategorien, und ein Posten weniger ließe
  den Rechenweg einer Kategorie verschwinden, die in der Anzeige stand.
  **Schritt:** 3; zeigt die Seite „im Schnitt“ neben „im Tempo der letzten
  drei Monate“, hat ein Verfahren einen Posten mit null, wo das andere keinen
  hat, und beide Spalten müssen dieselbe Menge Posten zeigen.
- **2.4, Rückgabe der Fortschreibung:** Der Plan nennt `list[Posten]`. Umgesetzt
  ist `list[Fortgeschrieben]` (Konto, Kategorie, Block, `verfahren.Ergebnis`, Ende,
  letzter gemessener Monat), weil `herkunft.Posten` weder Schlüssel noch Takt noch
  Beginn trägt und ein zweiter Typ gleichen Namens verwechselt würde. Der Posten
  der Kontoprognose (`RecurringItem`) entsteht daraus in `engine.recurring_items`.
  **Warum:** Der Schlüssel (Konto, Kategorie, Block) und Takt und Beginn
  gehören zum Ergebnis, nicht zum Rechenweg. **Schritt:** 4; der Takt je Reihe
  ist ein Feld von `Fortgeschrieben`, nicht von `herkunft.Posten`.
  **Erledigt in 4.4:** `Fortgeschrieben` trägt `reihe`, `takt`, `beitrag` und
  `monate`; `herkunft.Posten` blieb, wie es war.
- **2.7, ungerufene Bausteine:** `engine.planned_amount_cents`,
  `engine.funding_legs`, `jahre.SPECIAL` und `jahre.IGNORED` hat im Code niemand
  im Aufruf, nur Tests; gelöscht wurden sie nicht. **Warum:** Die beiden
  `engine`-Funktionen sind die Bausteine für Fremdwährung und Deckung, die das
  Klammerzeilenmodell nicht hat (Begründung bei `konten.account_forecast`), und
  die beiden Tupel halten im Test `test_jahre` die Aufteilung der Blöcke
  zusammen. **Schritt:** keiner.
