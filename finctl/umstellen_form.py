"""Wie die Dateien in `config/` aufgebaut sind -- fuer `finctl umstellen`.

Die Umwandlung der Kommentare in Notizen (Schritt 5, N.2) muss zu jeder Datei wissen,
was ein Eintrag ist und woran man ihn erkennt, und was die App selbst ueber eine Datei
schrieb. Beides steht hier, ohne dass eines der Module importiert wird, die die Dateien
heute lesen: Nach Schritt 5 gibt es einige davon nicht mehr, die Umwandlung soll
trotzdem laufen (Plan N.4: die alten Leser leben nur noch im Umwandler).

`tests/test_umstellen.py` haelt die Koepfe gegen die Konstanten der Module, solange es
sie gibt.

Plan: `docs/schritt5_notizen.md`, Tabelle A unter N.0.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Die Formen eines Behaelters, in dem Eintraege stehen.
LISTE = "liste"          # `- id: x` -- eine Liste von Zuordnungen, die Kennung ist ein Feld
ZUORDNUNG = "zuordnung"  # `x: {...}` -- die Kennung ist der Schluessel
BUDGETS = "budgets"      # `x: 123` -- nur eine Zahl je Konto, die Notiz gehoert zur Konto-Regel


@dataclass(frozen=True, slots=True)
class Behaelter:
    """Ein Schluessel oben in der Datei, unter dem Eintraege mit Kennung stehen."""

    schluessel: str
    form: str = LISTE
    #: Bei einer Liste: das Feld, das die Kennung traegt (N.0, Tabelle A).
    kennung: str = "id"
    #: Felder des Eintrags, die eine Notiz unter anderem Namen sind: Sie werden zu `notiz`.
    alt: tuple[str, ...] = ()
    #: Das Feld, unter dem die Blaetter einer Kategorie stehen. Ein Kommentar zu einem
    #: Blatt geht in die Notiz des Oberbegriffs, eingeleitet mit dem Namen des Blatts.
    blaetter: str = ""
    #: Bei `BUDGETS`: der Behaelter mit den Konto-Regeln, in deren Notiz der Kommentar geht.
    regeln: str = ""
    #: Listen im Eintrag, deren Elemente einen Freitext tragen, den keine Seite liest:
    #: (Liste, Feld des Freitexts, Feld, das das Element benennt, Wort davor). Der Text geht
    #: in die Notiz des Eintrags, eingeleitet mit dem Element.
    elemente: tuple[tuple[str, str, str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class Datei:
    behaelter: tuple[Behaelter, ...] = ()
    #: Schluessel ausserhalb der Behaelter sind Einstellungen: Ihre Notiz steht unter
    #: `notizen:` mit dem Schluesselpfad als Ort. Sonst gehen sie in die Notiz des Bereichs.
    einstellungen: bool = False
    #: `notizen:` steht vor dem Rest statt dahinter. Fuer `overrides.yaml`, deren Schreiber
    #: den Text vor `overrides:` als Kopf behalten.
    notizen_zuerst: bool = False

    @property
    def alte_namen(self) -> frozenset[str]:
        """Alle Feldnamen, die in dieser Datei eine Notiz unter anderem Namen sind."""
        return frozenset(n for b in self.behaelter for n in (*b.alt, *(e[1] for e in b.elemente)))


#: Dateien, die niemand in der Oberflaeche bearbeitet. Ihre Kommentare beschreiben die
#: Form der Datei und bleiben (Entscheidung 7).
OHNE_SEITE = frozenset({
    "server.yaml", "verbotene_namen.yaml", "taxonomy_migrations.yaml", "accounts.example.yaml",
})

_TAXONOMIE = (
    Behaelter("management", ZUORDNUNG, blaetter="children"),
    Behaelter("tax", ZUORDNUNG, blaetter="children"),
)
_TEILSTUECKE = (("segments_observed", "note", "period", "Teilstück"),)
_ROLLEN = Behaelter("account_roles", ZUORDNUNG, alt=("note",))
_BUDGETS = Behaelter("account_budgets", BUDGETS, regeln="account_roles")

#: Die Dateien, die der Umwandler kennt. Jede andere `.yaml` in `config/` gilt als Datei
#: ohne Eintraege: alle Kommentare gehen in die Notiz des Bereichs.
DATEIEN: dict[str, Datei] = {
    "abos.yaml": Datei((Behaelter("abos", alt=("warum",)),)),
    "abos_custom.yaml": Datei((Behaelter("abos", ZUORDNUNG, alt=("warum",)),)),
    "versicherungen.yaml": Datei((Behaelter("versicherungen", alt=("warum",)),)),
    "versicherungen_custom.yaml": Datei((Behaelter("versicherungen", ZUORDNUNG, alt=("warum",)),)),
    "accounts.yaml": Datei((Behaelter("accounts"),)),
    "accounts_custom.yaml": Datei((Behaelter("accounts", ZUORDNUNG),)),
    "assumptions.yaml": Datei(einstellungen=True),
    "assumptions.optimistisch.yaml": Datei(einstellungen=True),
    "assumptions.pessimistisch.yaml": Datei(einstellungen=True),
    "backup.yaml": Datei(einstellungen=True),
    "backup_custom.yaml": Datei(einstellungen=True),
    "balances.yaml": Datei((Behaelter("balances", kennung="account_id", alt=("note",)),
                            Behaelter("obligations", kennung="name", alt=("note",))),
                           einstellungen=True),
    "balances_custom.yaml": Datei((Behaelter("overrides", ZUORDNUNG, alt=("note",)),
                                   Behaelter("verpflichtungen", ZUORDNUNG, alt=("note",)))),
    "forecast.yaml": Datei((_ROLLEN, _BUDGETS), einstellungen=True),
    "forecast_custom.yaml": Datei((_ROLLEN, _BUDGETS)),
    "geteilt_custom.yaml": Datei((Behaelter("projekte"),)),
    "goals.yaml": Datei((Behaelter("ziele", alt=("quelle",)),)),
    "ziele_custom.yaml": Datei((Behaelter("ziele", ZUORDNUNG),)),
    "groups.yaml": Datei((Behaelter("gruppen"),)),
    "lebensplan.yaml": Datei(einstellungen=True),
    "lebensplan_custom.yaml": Datei(einstellungen=True),
    "loans.yaml": Datei((Behaelter("loans", alt=("note",), elemente=_TEILSTUECKE),)),
    "loans_custom.yaml": Datei((Behaelter("kredite", ZUORDNUNG),)),
    "overrides.yaml": Datei(notizen_zuerst=True),
    "properties.yaml": Datei((Behaelter("properties"),)),
    "properties_custom.yaml": Datei((Behaelter("objekte", ZUORDNUNG),)),
    "renten.yaml": Datei((Behaelter("renten", alt=("herleitung",)),)),
    # `neu:` sind Quellen, die es nur hier gibt; der Leser nimmt auch dort `herleitung`.
    "renten_custom.yaml": Datei((Behaelter("renten", ZUORDNUNG),
                                 Behaelter("neu", alt=("herleitung",)))),
    "rules.yaml": Datei((Behaelter("rules"),), einstellungen=True),
    "rules_custom.yaml": Datei((Behaelter("regeln", ZUORDNUNG),)),
    "settings_custom.yaml": Datei(einstellungen=True),
    "szenarien.yaml": Datei((Behaelter("szenarien"),)),
    "taxonomy.yaml": Datei(_TAXONOMIE),
    "taxonomy_custom.yaml": Datei(_TAXONOMIE),
}

#: Was die App ueber eine Datei schrieb, Datei fuer Datei, als Folge von Kopfzeilen. Eine
#: Datei kann mehrere Texte tragen (mehrere Schreiber). Ein Kopf, der wortlich einem
#: dieser Texte entspricht, ist Text der App und keine Begruendung des Haushalts (N.0,
#: Nummer 9).
KOEPFE: dict[str, tuple[str, ...]] = {
    "settings_custom.yaml": (
        """\
# Im Dashboard gesetzte Stellschrauben.
#
# Ueberschreibt, was config/assumptions.yaml und config/forecast.yaml
# dokumentiert vorgeben. Die Basisdateien bleiben unangetastet, weil dort die
# Begruendung zu jeder Zahl steht -- und die Begruendung ist das, was am
# schnellsten verfaellt.
#
# `salary_floor_cents`   : die Untergrenze, mit der die Prognose rechnen darf
# `floor_cents:<konto>`  : das Mindestniveau eines einzelnen Kontos""",
    ),
    "properties_custom.yaml": (
        """\
# Im Dashboard erfasste Objektdaten.
#
# Ueberschreibt config/properties.yaml je Objekt. Dort stehen die Fakten mit
# ihrer Herleitung -- AfA-Basis aus der Feststellung, Anschaffungsdatum aus
# dem Notarvertrag --, hier stehen die Zahlen, die in keiner Unterlage stehen
# und die nur der Eigentuemer kennt: was er gezahlt hat, was er einsetzt, was
# er beim Verkauf erwartet.
#
# Ohne diese Datei laegen sie ausschliesslich in der Datenbank. Die laesst
# sich aus Auszuegen wiederherstellen -- diese Zahlen nicht, denn sie sind
# nirgends gebucht.""",
        """\
# Im Dashboard erfasste Objektdaten.
#
# Ueberschreibt config/properties.yaml je Objekt. Dort stehen die Fakten mit
# ihrer Herleitung -- AfA-Basis aus der Feststellung, Anschaffungsdatum aus
# dem Notarvertrag --, hier stehen die Zahlen, die in keiner Unterlage stehen
# und die nur der Eigentuemer kennt: was er gezahlt hat, was er einsetzt, was
# er beim Verkauf erwartet. Dazu die auf /immobilien angelegten Objekte.
#
# `entfernt: true` blendet ein Objekt der Basisdatei aus, ohne deren
# Begruendung zu loeschen.
#
# Ohne diese Datei laegen die getippten Zahlen ausschliesslich in der
# Datenbank. Die laesst sich aus Auszuegen wiederherstellen -- diese Zahlen
# nicht, denn sie sind nirgends gebucht.""",
    ),
    "backup_custom.yaml": (
        """\
# Im Dashboard gesetztes Backup-Ziel.
#
# Ueberschreibt config/backup.yaml. Die Basisdatei bleibt unangetastet, weil
# dort steht, WARUM nur zwoelf Staende aufbewahrt werden und was das Archiv
# enthaelt -- und weil sie auf einer frischen Installation die Vorlage ist.
#
# `directory` : wohin gesichert wird. Cloud-Ordner, externe Platte, USB-Stick.
# `keep`      : wie viele Staende bleiben. Aeltere werden beim Schreiben
#               geloescht.""",
    ),
    "abos_custom.yaml": (
        """\
# Auf der Seite /abos angelegt und geaendert.
#
# Ueberschreibt config/abos.yaml Feld fuer Feld, je Kennung. Dort steht,
# WARUM ein Vertrag erklaert werden muss; hier steht, was im Frontend eingetragen
# wurde: Betrag, Termin, Besetzung, Zeitraeume. `entfernt: true` blendet ein
# Eintrag aus der Basisdatei aus, ohne deren Begruendung zu loeschen.
#
# Betraege in Cent. Monate als JJJJ-MM.""",
    ),
    "versicherungen_custom.yaml": (
        """\
# Auf der Seite /versicherungen angelegt und geaendert.
#
# Ueberschreibt config/versicherungen.yaml Feld fuer Feld, je Kennung. Dort steht,
# WARUM ein Vertrag erklaert werden muss; hier steht, was im Frontend eingetragen
# wurde: Betrag, Termin, Besetzung, Zeitraeume. `entfernt: true` blendet ein
# Eintrag aus der Basisdatei aus, ohne deren Begruendung zu loeschen.
#
# Betraege in Cent. Monate als JJJJ-MM.""",
    ),
    "loans_custom.yaml": (
        """\
# Auf der Seite /kredite angelegt und geaendert.
#
# `kredite:` sind die Eintraege dieser Seite, je Kennung. Sie ueberschreiben
# config/loans.yaml Feld fuer Feld; `entfernt: true` blendet einen Kredit der
# Basisdatei aus, ohne deren Begruendung zu loeschen.
#
# `vorlagen:` sind die Konditionen szenariogebundener Kredite.
#
# Betraege in Cent, Zinssatz in Prozent je Jahr.""",
        """\
# Anschlusskonditionen, im Dashboard gesetzt.
#
# Zins und anfängliche Tilgung in Prozent, so wie eine Bank ein
# Annuitätendarlehen anbietet. Die Rate folgt daraus, und die
# LAUFZEIT ebenfalls -- sie ist ein Ergebnis dieser beiden Zahlen und
# keine dritte Eingabe. Ein zusätzlich eingetipptes Enddatum könnte
# der Rechnung nur widersprechen.""",
        """\
# Im Dashboard gesetzte Kreditkonditionen.
#
# `anschluss`: Anschlusskonditionen zu den echten Verträgen -- Zins und
# anfängliche Tilgung in Prozent, so wie eine Bank ein
# Annuitätendarlehen anbietet. Die Rate folgt daraus, und die LAUFZEIT
# ebenfalls; sie ist ein Ergebnis dieser beiden Zahlen und keine dritte
# Eingabe.
#
# `vorlagen`: die Grundkonditionen der Szenario-Kredite. Nur diese sind
# änderbar. loans.yaml bleibt unangetastet, weil dort 136 Zeilen
# Herleitung stehen -- ein YAML-Schreiber wirft jede davon weg.""",
    ),
    "accounts_custom.yaml": (
        """\
# Auf der Seite /konten angelegt und geaendert.
#
# Ueberschreibt config/accounts.yaml Feld fuer Feld, je Kennung. Dort steht,
# WARUM ein Konto so gefuehrt wird; hier steht, was im Frontend eingetragen
# wurde. `entfernt: true` blendet einen Eintrag der Basisdatei aus, ohne
# deren Begruendung zu loeschen.
#
# statement_folder: ein Ordnername liegt unter data/statements/ und ist damit
# im Backup. Ein voller Pfad wird NICHT mitgesichert.""",
    ),
    "lebensplan_custom.yaml": (
        """\
# Auf /einrichtung gesetzt: Geburtstag, Krankenversicherung, Rentenalter.
#
# Ueberschreibt config/lebensplan.yaml, wo die Herleitung steht. Nur was
# davon abweicht, steht hier.""",
    ),
    "renten_custom.yaml": (
        """\
# Im Monatsabschluss eingetragen: Betrag und Stand je Rentenquelle.
#
# `renten:` ueberschreibt config/renten.yaml je Quelle, wo die Herleitung
# steht -- nur was davon abweicht. `neu:` sind Quellen, die im
# Monatsabschluss angelegt wurden, immer nominal.""",
    ),
    "reihen_custom.yaml": (
        """\
# Was im Dashboard ueber Reihen festgelegt wurde -- geschrieben von /reihen.
#
# Ein Eintrag zeigt auf Buchungen (`buchungen`: eine Buchung der Reihe
# genuegt). `takt` ist 1, 2, 3, 4, 6 oder 12 Monate, `unregelmaessig` oder
# `einmalig`. Ein fester Takt und `unregelmaessig` gelten fuer die ganze
# Reihe der Buchung, `einmalig` nur fuer die genannten Buchungen.
#
# `zusammen` fuehrt eine Schreibweise der Gegenpartei mit einer anderen zu einer
# Reihe zusammen (`<schreibweise>: <gegenpartei>`).""",
    ),
    "zinssaetze_custom.yaml": (
        """\
# Im Dashboard eingetragen: Zinssaetze je Konto, datiert.
#
# Je Konto eine Liste mit `ab` und optional `bis` (beide JJJJ-MM, einschliesslich)
# und `satz` als Anteil (0.03 fuer 3 %). Ohne Eintrag zahlt ein Tagesgeld den
# langfristigen Satz aus den Annahmen, ein Girokonto nichts; nach dem letzten
# Eintrag zahlt das Konto den langfristigen Satz weiter.""",
    ),
    "module_custom.yaml": (
        """\
# Welche Module eingeschaltet sind -- geschrieben von /einrichtung.
#
# Die Basis (Konten, Auszuege einlesen, Kategorien und Regeln, Rueckblick)
# ist immer an und steht hier nicht. Ausschalten blendet ein Modul aus und
# loescht nichts: seine Eintraege in config/ bleiben liegen.""",
    ),
    "geteilt_custom.yaml": (
        """\
# Geteilt -- geschrieben von den Seiten unter "Geteilt".
#
# personen: wer mitmacht. projekte: was zusammengehoert, mit wem, und je
# Person der Stand beim Abhaken "ausgeglichen". buchungen: welcher Teil
# welcher Buchung zu welchem Projekt gehoert, geschluesselt ueber dedup_hash
# wie overrides.yaml; ohne `teilung` gleich auf alle Projektpersonen und mich.""",
    ),
    "prognosebasis_custom.yaml": (
        """\
# Unter Fortschreibung (/prognosebasis) abgewaehlte Kategorien.
#
# Eine Kategorie hier wird in KEINER Prognose fortgeschrieben -- weder auf
# /konten noch in der Jahresrechnung (/hochrechnung, /ziele). Gemessen und im
# Abgleich gezeigt wird sie weiter.
#
# Gedacht fuer Unregelmaessiges, das zufaellig im Messfenster lag: eine
# Schenkung, eine Erstattung. Was wirklich wiederkehrt, gehoert nicht hierher.""",
    ),
    "csv_profile_custom.yaml": (
        """\
# Selbst beschriebene CSV-Exporte -- geschrieben von der Einrichtung.
#
# Je Bank: woran die Kopfzeile zu erkennen ist und welche Spalte was bedeutet.
# Aufbau wie finctl/ingest/profiles/banken_csv.py; `saldo` ist spalte, kopf,
# ende oder keiner. Der Import nennt ein Profil hier eigen_<kennung>.""",
    ),
    "rules_custom.yaml": (
        """\
# Auf der Seite /regeln angelegt und geaendert.
#
# Je Kennung nur, was von config/rules.yaml abweicht: ein Feld hier ersetzt das
# gleichnamige dort (match und set als Ganzes). `entfernt: true` blendet eine
# Regel aus rules.yaml aus. Kennungen, die es dort nicht gibt, sind eigene
# Regeln. Von Hand bearbeiten geht; die Seite liest es genauso.""",
    ),
    "balances_custom.yaml": (
        """\
# Bestände und Verbindlichkeiten, die im Dashboard erfasst wurden.
#
# Überschreibt balances.yaml je Position — Wert, Stichtag und Notiz.
# Die Basisdatei bleibt unangetastet, weil dort die Begründung zu
# jeder Position steht. Ein Dashboard, das sie neu schreibt, löscht
# das beim ersten Klick.
#
# as_of gehört zu jedem Wert. Ein veralteter Bestand, der sagt, wann
# er veraltet ist, bleibt benutzbar; einer, der Aktualität behauptet,
# nicht.
#
# verlauf hält je Position und Abschluss fest, was damals stand: Belege
# für den Vergleich mit dem Vormonat, kein Wert, der gilt.""",
    ),
    "ziele_custom.yaml": (
        """\
# Im Dashboard bearbeitete Ziele.
#
# Überschreibt goals.yaml je Ziel. Die Basisdatei bleibt unangetastet,
# weil dort die Herleitung jeder Zahl steht -- und die Herleitung ist
# das, was am schnellsten verfällt. Ein Ziel von 1.100.000 ohne Notiz
# ist in einem Jahr nicht mehr nachvollziehbar.
#
# Ziele, die es in goals.yaml nicht gibt, wurden hier angelegt;
# `entfernt: true` blendet eines aus goals.yaml aus. `reihenfolge` ist
# die auf der Seite gezogene Anordnung.""",
    ),
    "forecast_custom.yaml": (
        """\
# Kontenregeln, die auf /konten gesetzt wurden.
#
# Ueberschreibt forecast.yaml je Konto -- Rolle, Zweck, Untergrenze,
# Deckel, Abraeumen, Auffuellen, Dauerauftrag. Gespeichert wird nur,
# was von der Basisdatei abweicht: dort steht die Begruendung zu
# jedem Wert, und die soll ein Klick nicht loeschen.""",
    ),
    "taxonomy_custom.yaml": (
        """\
# Categories added or renamed from the dashboard.
#
# Merged on top of taxonomy.yaml, which stays the documented base with
# its reasoning intact -- a YAML writer would strip every comment there.
# Safe to edit by hand or to keep in git.""",
    ),
    "strom.yaml": (
        """\
# Strom -- geschrieben von der Seite /strom.
#
# Von Hand aendern geht, die Seite liest die Datei bei jedem Aufruf neu.
# Zeitraeume: das neueste zuletzt. Ablesungen: Datum und Zaehlerstand in kWh.
# Geld in Cent; Arbeitspreis in Cent je kWh.""",
    ),
    "szenarien.yaml": (
        """\
# Eigene Was-wäre-wenn-Pläne, im Dashboard gepflegt.
#
# Hier darf beliebig vieles gleichzeitig AN sein, weil die eigentliche Frage meist
# "geht beides" lautet -- das Auto und die zweite Wohnung.
#
# Ausschalten statt löschen. Einen Plan zu parken muss ein Klick sein, sonst
# wird er gelöscht und die Überlegung dahinter verschwindet mit ihm.
#
# Vorzeichen wie im Ledger: negativ ist Geld raus.""",
    ),
    "energie.yaml": (
        """\
# Energie ausser Strom -- geschrieben von der Seite /energie.
#
# zaehler: je Zaehler Art, Einheit, Profil und dieselben Zeitraeume und
#   Ablesungen wie config/strom.yaml. Gas rechnet m³ mit Brennwert und
#   Zustandszahl (beide auf der Rechnung) in kWh um.
# vorraete: je Tank oder Lager die Lieferungen (Menge, Betrag in Cent) und
#   die Peilungen (Fuellstand am Tag).
# profil: linear, oder heizung (Gradtagzahlen); grundlast ist der Anteil
#   ohne Jahresgang, etwa Warmwasser.""",
    ),
    "overrides.yaml": (
        """\
# Manual categorization decisions, replayed after every categorize.
#
# Keyed on dedup_hash, not transaction id: ids are assigned at import
# and shift on every rebuild, the hash is derived from the transaction
# itself and does not. This is what makes your own decisions survive a
# `rm data/finance.db` -- they did not, once, and roughly thirty were
# lost.
#
# Written automatically. Safe to edit or to keep in git.""",
    ),
}


def datei(name: str) -> Datei:
    """Die Form einer Datei; eine unbekannte ist eine Datei ohne Eintraege."""
    return DATEIEN.get(name, Datei())


def kopf_zeilen(text: str) -> tuple[str, ...]:
    """Die Zeilen eines Kopfes ohne `#`, ohne Rand und ohne leere Zeilen."""
    zeilen = (z.strip().removeprefix("#").strip() for z in text.splitlines())
    return tuple(z for z in zeilen if z)


def ist_kopf_der_app(name: str, zeilen: tuple[str, ...]) -> bool:
    """Stimmt dieser Kopf wortlich mit einem Text ueberein, den die App ueber die Datei schrieb?"""
    return bool(zeilen) and any(kopf_zeilen(t) == zeilen for t in KOEPFE.get(name, ()))
