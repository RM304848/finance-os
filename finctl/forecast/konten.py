"""Die Kontoprognose: Tiefpunkt je Konto und Monat, Monat fuer Monat.

Stand bis 26.09.2026 in finctl/ops.py, zwischen Sicherung und Einlesen -- die
App-Schicht trug damit eine Rechnung, die der Prognose gehoert, und die
Prognose musste die App importieren, um mit derselben Basis zu rechnen
(tests/test_module.py, OFFEN). Hier steht sie bei den anderen Rechnungen;
`ops` reicht die Namen weiter, damit Aufrufer nichts merken.
"""

from __future__ import annotations

import calendar
import math
import sqlite3
import statistics
from collections.abc import Collection, Iterable, Mapping
from datetime import date, timedelta
from functools import partial
from typing import TYPE_CHECKING

from finctl import notizen as _notizen
from finctl.dateien import yaml_lesen
from finctl.forecast import messung, verfahren, vertraege, wachstum
from finctl.forecast import notgroschen as _ng
from finctl.forecast import objektposten as _ob
from finctl.forecast import zinsen as _zn
from finctl.forecast.fortschreibung import Vorschau
from finctl.forecast.herkunft import Posten, eur_genau, prozent
from finctl.forecast.stichtag import saldo_zum as _saldo_zum
from finctl.forecast.stichtag import stichtag as _stichtag
from finctl.forecast.takt import Reihen
from finctl.forecast.verfahren import add_months
from finctl.forecast.vertraege import police_vertraege, vertragsbetrag
from finctl.pfade import CONFIG_DIR

if TYPE_CHECKING:
    from finctl.forecast.engine import Untergrenze


def _sweep_ceiling(account: str, fcfg: dict) -> int | None:
    """The ceiling an account is actually emptied down to, if it declares one.

    Only where `sweep_to` names a destination. A ceiling without a sweep is an
    observation; a ceiling with one is a monthly instruction, and the forecast
    should show the world where the instruction is followed.
    """
    role = (fcfg.get("account_roles") or {}).get(account) or {}
    return role.get("ceiling_cents") if role.get("sweep_to") else None



# _monatsschnitt_ops ist am 21.09.2026 entfallen. Es mass eine Planzeile ueber
# den Schnitt ihrer GANZEN Kategorie, waehrend die Jahresrechnung dieselbe
# Zeile ueber ihre zugeordneten Buchungen mass -- zwei Antworten auf eine
# Frage, die im Monat spuerbar auseinanderlagen. Beide Rechnungen nehmen jetzt
# `szenarien.messung`.


def _income_overrides(fcfg: dict, basisjahr: int) -> dict[str, int | Untergrenze]:
    """Feste Werte, die die Messung ersetzen.

    Die Gehaltsuntergrenze kommt aus assumptions.yaml und wird hier eingesetzt, statt
    in forecast.yaml wiederholt zu werden. Sie stand vorher an drei Stellen --
    forecast.yaml, lebensplan.yaml und der settings-Tabelle -- und nichts hielt
    sie zusammen ausser einer eigenen Pruefung, die nur meldete, wenn sie
    bereits auseinandergelaufen waren.

    Sie ist das Gehalt beider Modelle und steigt mit `gehalt_steigerung_pa`, zum 1. Januar
    nach dem Basisjahr -- dem Jahr des ersten offenen Tages, wie in der Jahresrechnung.
    Ein Wert aus forecast.yaml bleibt eine gesetzte Zahl.
    """
    from finctl import assumptions as _ann
    from finctl.forecast import engine as _fc

    out = {k: int(v) for k, v in _notizen.ohne(fcfg.get("overrides")).items()}
    if "einkommen/gehalt" not in out:
        out["einkommen/gehalt"] = _fc.Untergrenze(
            _ann.salary_floor_cents(), basisjahr, _ann.salary_growth_pa())
    return out


def _as_month(value):
    """YYYY-MM oder ein YAML-Datum, auf den Monatsersten normalisiert."""
    if isinstance(value, date):
        return value.replace(day=1)
    text = str(value)
    return date.fromisoformat(text + "-01" if len(text) == 7 else text).replace(day=1)


def _enden(fcfg: dict) -> dict:
    """Je Kategorie der Monat, in dem sie endet (`enden` in forecast.yaml)."""
    return {cat: _as_month(when) for cat, when in _notizen.ohne(fcfg.get("enden")).items()}


def _operating_account(fcfg: dict) -> str | None:
    """Where an unassigned obligation lands: the Betriebskonto.

    Declared rather than guessed: the roles in forecast.yaml already say which
    account runs salary and fixed costs, and that is the one a new rate would
    be debited from.

    Ein ARCHIVIERTES Konto zaehlt nicht. Wechselt der Anbieter, behaelt das alte
    Konto seinen Eintrag in forecast.yaml, und die Rolle gehoert dem neuen --
    gewaenne das erste in der Datei, buchte jede neue Rate auf ein
    geschlossenes Konto. Hat kein aktives Konto die Rolle, gilt das erste aktive
    Giro mit Auszuegen, nach Kennung: eine Regel statt einer Kennung. Gibt es
    auch das nicht, gibt es kein Betriebskonto (`None`).

    Liest das Kontenregister: in einer Schleife einmal davor aufrufen.
    """
    from finctl import konten

    register = konten.laden()
    archiviert = {str(k["id"]) for k in register if _archiviert(k)}
    for account, role in (fcfg.get("account_roles") or {}).items():
        if (role or {}).get("role") == "operating" and str(account) not in archiviert:
            return account
    giros = sorted(str(k["id"]) for k in register
                   if not _archiviert(k) and k.get("account_type") == "giro"
                   and k.get("ingest_mode") == "parsed")
    return giros[0] if giros else None


def _archiviert(konto: dict) -> bool:
    """Wie `konten` es beim Einlesen entscheidet: `active: false` oder ein Schlusstag."""
    return konto.get("active") is False or bool(konto.get("closed_on"))


def betriebskonto() -> str | None:
    """Das Betriebskonto nach der geltenden Konfiguration (Basis plus Kontenseite)."""
    return _operating_account(forecast_config())


def _rate_floor(loan_id: str, month=None) -> int | None:
    """Eine Monatsrate des genannten Darlehens, im genannten Monat.

    Fuer ein Konto, das nichts tut ausser eine Rate auszufuehren, IST die Rate
    der richtige Floor: genug, dass die Lastschrift nie platzt, und keinen
    Euro mehr, denn das Geld verzinst sich anderswo besser.

    Abgeleitet und nicht eingetragen, weil die Rate sich aendert. Eine Rate,
    die nach der Zinsbindung um 40 % steigt, macht jeden festen Floor danach
    zu niedrig -- oder, haette man ihn vorsorglich auf den hoeheren Wert
    gesetzt, vorher um denselben Betrag zu hoch.
    """

    from finctl.realestate.loan import amortise, lade_kredite, opening_balance_cents, segments_from

    if not (CONFIG_DIR / "loans.yaml").exists():
        return None
    loan = next((x for x in lade_kredite(CONFIG_DIR)
                 if str(x.get("id")) == str(loan_id)), None)
    if loan is None:
        return None
    try:
        sched = amortise(loan["id"], opening_balance_cents(loan),
                         segments_from(loan))
    except Exception:
        return None
    if not sched.payments:
        return None
    if month is None:
        return sched.payments[0].payment_cents
    passend = [p for p in sched.payments
               if (p.month.year, p.month.month) <= (month.year, month.month)]
    return (passend[-1] if passend else sched.payments[0]).payment_cents


def _floor_for(account: str, fcfg: dict, acct, month=None) -> int:
    """The warning floor, in order of how deliberately it was set.

    `floor_from_loan` steht GANZ VORN: ein Konto, das nur eine Rate ausfuehrt,
    soll genau eine Rate halten, und die aendert sich mit dem Tilgungsplan.
    Ein getippter Wert daneben friert die Rate von heute ein -- genau das
    passierte, als die Kontokarte den angezeigten Wert mitspeicherte und das
    Konto ab der naechsten Ratenerhoehung zu duenn gedeckt war.

    Danach die deklarierte Rolle in `forecast.yaml`, auch der im Dashboard
    getippte Wert: Seit Schritt 5 (N.3f) schreibt /konten dorthin und nirgends
    sonst hin (vorher in der Tabelle `settings`). Die
    accounts-Tabelle kommt zuletzt -- init schreibt sie bei jedem Lauf aus
    accounts.yaml neu, und so stand ein morgens gesetzter Floor nachmittags
    wieder auf dem alten Wert.
    """
    role = (fcfg.get("account_roles") or {}).get(account) or {}
    aus_plan = role.get("floor_from_loan")
    if aus_plan:
        rate = _rate_floor(str(aus_plan), month)
        if rate:
            return rate
    declared = role.get("floor_cents")
    if declared is not None:
        return int(declared)
    return acct["dispo_threshold_cents"] or 0


def _untergrenze(account: str, fcfg: dict, acct, month=None) -> int:
    """Die Untergrenze, die gilt: die der Regel oder die des Notgroschens, die hoehere.

    Liegt der Notgroschen auf diesem Konto (`notgroschen.untergrenze`), ist seine Grenze
    eine Untergrenze des Kontos, und `/konten` warnt, wenn eine Klammer ihn angreift.
    """
    return max(_floor_for(account, fcfg, acct, month), _ng.untergrenze(account, fcfg))


#: Wie weit die Liquiditaetsprognose standardmaessig reicht, und wie weit sie
#: auf Aufforderung reicht.
#:
#: Zwoelf bleibt die Vorgabe, weil die abgeleiteten Positionen nur so weit
#: belastbar sind: ein Median aus neun Monaten, fortgeschrieben mit der
#: Inflation, ist ueber ein Jahr eine gute Naeherung und ueber fuenf eine
#: Behauptung. Sechzig gibt es fuer die Faelle, in denen genau das gefragt ist
#: -- eine Kreditentscheidung ueber fuenf Jahre --, aber als ausdruecklicher
#: Aufruf und nicht als stille Voreinstellung.
HORIZON_DEFAULT = 12
HORIZON_LONG = 60


def _objektnamen(etiketten: set[str]) -> dict[str, str]:
    """Die Namen der Posten eines Objekts mit Prognose, soweit welche vorkommen."""
    if not any(e.startswith((_ob.MIETE_ETIKETT, _ob.KOSTEN_ETIKETT)) for e in etiketten):
        return {}
    from finctl import objekte as _objekte

    return _ob.anzeigenamen(_objekte.prognosen(), etiketten)


def _anzeigenamen(conn, rows) -> dict[str, str]:
    """Die Etiketten der Prognose in lesbare Namen uebersetzen.

    Die Engine fuehrt Posten unter ihrer Kennung -- `immobilie/grundsteuer`,
    `loan:<objekt>`. Das ist als Schluessel richtig und als Ueberschrift
    unleserlich, und eine Tabelle, die man erst uebersetzen muss, liest man
    nicht.

    Nur fuer die Anzeige: was nicht aufgeloest werden kann, bleibt stehen, wie
    es ist. Ein unbekanntes Etikett zu verschweigen waere schlimmer als ein
    haessliches -- Szenariozeilen tragen bereits deutschen Klartext.
    """
    etiketten = {e for r in rows for e in r.detail}
    namen: dict[str, str] = {}

    kategorien = {k for k in etiketten if "/" in k and not k.startswith("loan:")}
    if kategorien:
        platzhalter = ",".join("?" * len(kategorien))
        for row in conn.execute(
                f"""SELECT c.id, c.name, p.name AS oberbegriff
                    FROM   mgmt_categories c
                    LEFT   JOIN mgmt_categories p ON p.id = c.parent_id
                    WHERE  c.id IN ({platzhalter})""", sorted(kategorien)):
            # Mit Oberbegriff, weil "Sonstiges" allein nichts sagt und in vier
            # Zweigen gleichzeitig vorkommt.
            namen[row["id"]] = (f"{row['oberbegriff']}: {row['name']}"
                                if row["oberbegriff"] else row["name"])
    # Teile ohne Kategorie stehen unter dem leeren Schluessel; ihr Name ist kein leeres Feld.
    namen[""] = "ohne Kategorie"

    from finctl import abos as _ab

    for a in _ab.alle_vertraege():
        for vorsatz, text in (("abo:", f"{a['name']} (erklärt)"),
                              ("abo-zurueck:", f"{a['name']}: Rückzahlungen offen"),
                              ("abo-anteil:", f"{a['name']}: Anteil der Mitzahler")):
            if f"{vorsatz}{a['id']}" in etiketten:
                namen[f"{vorsatz}{a['id']}"] = text

    for e in etiketten:
        if e.startswith("budget:"):
            namen[e] = f"Dauerauftrag an {e[7:]}"
    namen.update(_objektnamen(etiketten))
    kredite = {k[5:] for k in etiketten if k.startswith("loan:")}
    if kredite:
        from finctl.realestate.loan import lade_kredite

        for kredit in lade_kredite(CONFIG_DIR):
            if str(kredit["id"]) in kredite:
                namen[f"loan:{kredit['id']}"] = (
                    f"Kreditrate {kredit.get('name') or kredit['id']}")
    return namen


_FREQ = {"monatlich": "monatlich", "quartalsweise": "quartalsweise",
         "jaehrlich": "jährlich", "einmalig": "einmalig"}


def _laufzeit_text(row: dict) -> str:
    """Wann eine Zeile gilt: ab und bis bei einer laufenden, der Monat bei einer einmaligen."""
    from finctl.forecast.herkunft import monat

    if row.get("frequency") != "einmalig" and row.get("start"):
        return f" ab {monat(row['start'])}" + (f" bis {monat(row['end'])}"
                                              if row.get("end") else "")
    return f" {monat(row['start'])}" if row.get("start") else ""


def _herkunft_planzeile(row: dict, konto: str) -> Posten:
    """Wie eine Planzeile auf diesem Konto ankommt."""
    from finctl.forecast.herkunft import eur_genau as eur
    from finctl.forecast.herkunft import monat

    verweis = f"{row['scenario_id']}:{row['zeile']}"
    m = row.get("gemessen") or {}
    n = len(m.get("buchungen") or [])
    belege = (f"{n} Buchung{'' if n == 1 else 'en'} dieser Reihe in "
              f"{m.get('monate') or 0} Monaten")
    frequenz = f"{_FREQ.get(row.get('frequency'), row.get('frequency'))} {eur(row['amount_cents'])}"
    kein_konto = (f"; ohne Konto in der Zeile, deshalb auf {konto}"
                  if not row.get("account_id") else "")
    if row.get("kind") == "wegfall":
        text = (f"entfällt ab {monat(row['start'])}: {eur(row['amount_cents'])} "
                f"je Monat, gemessen an {belege} — dieselbe Rechnung wie in "
                "der Jahresrechnung")
    elif row.get("kind") == "erwartet":
        z = row.get("zugeordnet") or 0
        text = (f"erwartete Einnahme, {frequenz}, fester Betrag ohne Steigerung"
                f"{_laufzeit_text(row)}; {z} zugeordnete Buchung{'' if z == 1 else 'en'} und "
                "ihre Reihe zählen nicht mehr in der Messung — dieselbe Rechnung wie in der "
                f"Jahresrechnung{kein_konto}")
    else:
        text = f"{frequenz}{_laufzeit_text(row)}"
        if n:
            # Der Rest, nicht der Plan: was schon gebucht ist, steckt im
            # Median und darf nicht ein zweites Mal danebenstehen.
            text += f"; gekürzt um {belege}, die schon in der Messung stehen"
        text += kein_konto
    return Posten(label=row["label"], cents=row["amount_cents"], quelle="plan",
                  herleitung=text, verweis=verweis,
                  kategorie=row.get("category_id"))


def _planposten(conn, account: str, fcfg: dict, as_of: str, months: int,
                gedeckt: Iterable[str] = ()) -> list:
    """Die eingeschalteten Planzeilen als datierte Posten DIESES Kontos.

    Eine Zeile auf einem durchlaufenden Konto, das dieses Konto deckt (`gedeckt`), zaehlt
    hier: das durchlaufende Konto hat keine Prognose.

    DER GESCHLOSSENE KREIS, WIE IN DER JAHRESRECHNUNG. Eine Planzeile wirkt
    nur mit dem Teil, der noch NICHT in der Messung steckt -- siehe den
    Abschnitt gleichen Namens in szenarien.py. Hier stand stattdessen
    `resolve_measured`: ein Wegfall bekam den Schnitt seiner GANZEN Kategorie,
    neue Kosten gar keinen Abgleich. Damit antworteten Kontoprognose und
    Jahresrechnung verschieden auf dieselbe Zeile, und neue Kosten zaehlten
    doppelt, sobald sie zu buchen anfingen.
    """
    from datetime import date as _date

    from finctl.forecast import abgleich as _ag
    from finctl.forecast import engine as fc
    from finctl.forecast import szenarien as _sz

    pfad = CONFIG_DIR / "szenarien.yaml"
    if not pfad.exists():
        return []
    geladen = _sz.load(yaml_lesen(pfad) or {})
    fenster = _ag.fenster(conn)
    zeilen = {(s.id, i): line for s in _sz.active(geladen)
              for i, line in enumerate(s.lines)}
    gemessen = {k: _sz.messung(conn, line, fenster) for k, line in zeilen.items()}
    rate = steigerung(None)
    horizon = fc.add_months(_date.fromisoformat(as_of).replace(day=1), months + 1)

    betrieb = _operating_account(fcfg)
    hier = {account, *gedeckt}
    out = []
    for row in _sz.dated_amounts(geladen, horizon):
        # Ein Wegfall rechnet hier nicht mit seiner Jahresmessung, sondern in
        # `wegfall_posten` mit dem, was diese Prognose fuer seine Reihe bucht.
        if row["kind"] == "wegfall":
            continue
        # A line with no account belongs to the operating account: that is
        # where a rate is debited unless stated otherwise, and dropping it
        # would make a plan look free.
        schluessel = (row["scenario_id"], row["zeile"])
        steigt = (wachstum.faktor(fenster.mitte, wachstum.monatsmitte(row["month"]), rate)
                  if fenster else 1.0)
        betrag = _sz.restbetrag_je_termin(zeilen[schluessel], gemessen[schluessel], steigt)
        if (row["account_id"] or betrieb) not in hier or not betrag:
            continue
        if row["category_id"] in _zn.GERECHNET:
            # Eine Korrektur der gemessenen Zinsen. Gemessen wird nichts mehr, der Zins
            # kommt aus Stand und Satz: Die Zeile zoege einen Betrag ab, der nirgends steht.
            continue
        out.append(fc.OneOff(
            label=row["label"], account_id=account, month=row["month"],
            amount_cents=betrag, reduces_cost=row.get("reduces_cost", False),
            category=row["category_id"],
            herkunft=_herkunft_planzeile(
                {**row, "amount_cents": betrag, "gemessen": gemessen[schluessel],
                 "zugeordnet": len(zeilen[schluessel].buchungen)}, account)))
    return out


def _klammern() -> list:
    """Die Klammern aus szenarien.yaml, geladen -- oder keine."""
    from finctl.forecast import szenarien as _sz

    pfad = CONFIG_DIR / "szenarien.yaml"
    if not pfad.exists():
        return []
    return _sz.load(yaml_lesen(pfad) or {})


def wegfall_posten(conn, account: str, klammern: list, abgeleitet: list,
                   ableiten, *, start, months: int,
                   overrides: dict | None = None,
                   gedeckt: Iterable[str] = ()) -> list:
    """Die eingeschalteten Wegfall-Zeilen als datierte Posten DIESES Kontos.

    GENAU DAS, WAS DIE PROGNOSE FUER DIE REIHE BUCHT -- nicht mehr, nicht
    weniger. Die Kontoprognose bucht einen Jahresposten an seinem Termin, die
    Jahresrechnung zaehlt ihn aufs Jahr. Bis 02.10.2026 zog ein Wegfall hier
    trotzdem den Zwoelfmonatsschnitt der Jahresrechnung ab, und beides lief
    auseinander: etwa 12 Kraftstoff in der Prognose gegen 6 Wegfall, und
    eine Jahreszahlung gegen einen Abzug in jedem Monat.

    Deshalb wird die Ableitung einmal MIT und einmal OHNE die Reihe der
    zugeordneten Buchungen gerechnet; der Unterschied je Monat ist der
    Wegfall, ab seinem Start. Er hebt den fortgeschriebenen Posten auf, auch
    wenn der nur einmal im Jahr faellt, und auf jedem Konto, auf dem die
    Reihe liegt. Laeuft die Reihe aus dem Messfenster, wird der Unterschied
    von selbst null.

    Mit `nur_kontoprognose` gilt die Zeile nur fuer IHR Konto: die Reihe
    zieht um, statt zu enden. Ihre Reihe kann auf anderen Konten weiterlaufen
    -- dieselbe Gegenpartei in derselben Kategorie --, und dort bleibt sie.

    `abgeleitet` sind die Posten, wie `abgeleitete_posten` sie liefert, ohne
    Budgets; `ableiten(ohne)` rechnet sie ohne die genannten Buchungen. Eine Reihe liegt
    auch dann auf dem Konto, wenn sie auf einem durchlaufenden Konto steht, das es deckt
    (`gedeckt`).
    Zwei Zeilen auf dieselbe Reihe ziehen sie einmal ab: jede nimmt nur, was
    die vorigen noch nicht genommen haben.
    """
    from finctl.forecast import engine as fc
    from finctl.forecast import szenarien as _sz
    from finctl.forecast.herkunft import monat
    from finctl.ledger import reihe as _reihe

    overrides = overrides or {}
    horizont = fc.add_months(start, months - 1)

    def betrag(posten: list, wann) -> int:
        # Wie `engine.project`: ein Override ersetzt die Messung.
        return sum(fc.override_in(overrides, p.label, wann)
                   if p.label in overrides else p.amount_in(wann)
                   for p in posten if p.due_in(wann))

    out = []
    genommen: set[str] = set()
    vorher = abgeleitet
    for klammer in _sz.active(klammern):
        for index, line in enumerate(klammer.lines):
            if line.kind != "wegfall" or not line.buchungen or not line.start:
                continue
            if line.nur_kontoprognose and line.account_id not in {account, *gedeckt}:
                continue
            reihe = set(_reihe.hashes(conn, line.buchungen)) - genommen
            if not reihe or not _auf_konto(conn, {account, *gedeckt}, reihe):
                continue
            genommen |= reihe
            nachher = ableiten(frozenset(genommen))
            n = len(line.buchungen)
            text = (f"entfällt ab {monat(line.start)}: genau, was die Prognose "
                    f"für diese Reihe auf {account} sonst bucht — "
                    f"{n} zugeordnete Buchung{'' if n == 1 else 'en'}, "
                    f"{len(reihe)} in der Reihe")
            for wann in line.months(horizont):
                if wann < start:
                    continue
                differenz = betrag(vorher, wann) - betrag(nachher, wann)
                if not differenz:
                    continue
                # Faellt eine Ausgabe weg, steht das vor den Kosten des Tages;
                # faellt eine Einnahme weg, dort, wo sie gekommen waere.
                etikett = f"{klammer.name}: {line.label}"
                out.append(fc.OneOff(
                    label=etikett, account_id=account,
                    month=wann, amount_cents=-differenz,
                    reduces_cost=differenz < 0,
                    day=None if differenz < 0 else fc.UNDATED_INCOME_DAY,
                    herkunft=Posten(
                        label=etikett, cents=-differenz, quelle="plan",
                        herleitung=text, verweis=f"{klammer.id}:{index}",
                        kategorie=line.category_id)))
            vorher = nachher
    return out


def _auf_konto(conn, konten: set[str], hashes: set[str]) -> bool:
    """Liegt wenigstens eine dieser Buchungen auf einem der Konten?"""
    platz = ",".join("?" * len(hashes))
    return conn.execute(
        f"SELECT 1 FROM transactions WHERE account_id IN ({','.join('?' * len(konten))}) "
        f"AND dedup_hash IN ({platz}) LIMIT 1",
        (*sorted(konten), *sorted(hashes))).fetchone() is not None


def _zusammen(bisher: Posten | None, neu: Posten) -> Posten:
    """Zwei Posten unter einem Etikett: Eine Kategorie hat ihre Reihen mit festem
    Takt und ihren Rest, und die Seite zeigt sie unter einer Zeile. Der Text nennt
    beide; die Zahl der Zeile steht daneben in der Tabelle (`Posten.cents` ist hier
    die Beschreibung einer Reihe, keine Summe)."""
    if bisher is None:
        return neu
    return Posten(label=neu.label, cents=bisher.cents, quelle=bisher.quelle,
                  herleitung=f"{bisher.herleitung} | {neu.herleitung}",
                  verweis=bisher.verweis, kategorie=bisher.kategorie,
                  umbuchung=bisher.umbuchung or neu.umbuchung)


def _herkunft_konto(fcfg: dict, overrides: dict, recurring, one_offs, schedules,
                    rows) -> dict[str, dict]:
    """Je Etikett der Monatsdetails die Herkunft.

    Ein Etikett ohne Herkunft bekommt eine ehrliche Zeile statt keiner --
    sonst sieht eine Luecke hier aus wie eine Zahl, die sich selbst erklaert.
    """
    from finctl.forecast.herkunft import eur_genau as eur

    out: dict[str, Posten] = {}
    for item in recurring:
        if item.herkunft:
            out[item.label] = _zusammen(out.get(item.label), item.herkunft)
    for event in one_offs:
        if getattr(event, "herkunft", None):
            out.setdefault(event.label, event.herkunft)
    for sched in schedules:
        # Eine Rate je Monat, nicht eine Zahl: die erste steht fuer die Zeile.
        erste = sched.payments[0].payment_cents if sched.payments else 0
        out[f"loan:{sched.loan_id}"] = Posten(
            label=f"loan:{sched.loan_id}", cents=-erste, quelle="vertrag",
            verweis=str(sched.loan_id),
            herleitung="Rate laut Tilgungsplan in loans.yaml, im Monat der "
                       "Fälligkeit, nicht gesteigert")

    gesetzt = set(_notizen.ohne(fcfg.get("overrides")))
    for label, wert in overrides.items():
        if label in gesetzt:
            out[label] = Posten(
                label=label, cents=int(wert), quelle="regel", verweis=label,
                herleitung=f"fest {eur(int(wert))} aus forecast.yaml "
                           "(overrides), ersetzt die Messung")
        elif label == "einkommen/gehalt":
            out[label] = Posten(
                label=label, cents=wert.cents, quelle="annahme",
                verweis="salary_floor_cents",
                herleitung=(f"Gehalts-Untergrenze {eur(wert.cents)} aus den Annahmen, "
                            f"im Jahr {wert.base_year} wie sie ist, danach zum 1. Januar "
                            f"× {prozent(wert.rate)} Gehaltssteigerung; die Jahresrechnung "
                            "rechnet mit derselben Zahl"))

    betraege = {e: c for r in reversed(rows) for e, c in r.detail.items()}
    return {e: (out.get(e) or Posten(
                label=e, cents=betraege[e], quelle="regel", verweis=None,
                herleitung="ohne hinterlegte Herleitung")).als_herkunft()
            for e in betraege}


def _art_des_kontos(konto: str) -> str:
    """Die Bestandsart eines Kontos aus `kind` in balances.yaml -- wie die Jahresrechnung
    (`ziele.tagesgeld_je_konto`). `accounts.account_type` ist die Art fuers Einlesen und
    nennt dasselbe Konto bisweilen anders; fuer den Zins zaehlt eine Quelle."""
    from finctl import bestaende

    for zeile in bestaende.lesen().get("balances") or []:
        if str(zeile.get("account_id") or zeile.get("name") or "") == konto:
            return (zeile.get("kind") or "").lower()
    return ""


def _verzinsung(konto: str):
    """Der Satz, den dieses Konto in einem Monat verdient, und woraus er besteht.

    (`satz(monat)`, Text) -- oder None, wenn das Konto nie etwas verdient: Ein Konto ohne
    Eintrag in den Zinssaetzen und ohne die Art Tagesgeld zahlt nichts. Der Satz eines
    Monats ist `zinsen.satz_im_monat`, dieselbe Funktion wie in der Jahresrechnung.
    """
    from finctl import assumptions as _ann
    from finctl import zinssaetze as _zs
    from finctl.forecast.herkunft import monat, prozent

    saetze = _zs.lesen().get(konto, ())
    art = _art_des_kontos(konto)
    if not saetze and art != _zn.VERZINST:
        return None
    langfristig = _ann.rendite_nominal_pa()
    eintraege = [f"{prozent(z.satz)} ab {monat(z.ab)}" + (f" bis {monat(z.bis)}" if z.bis else "")
                 for z in saetze]
    text = ("; ".join(eintraege) + f"; sonst der langfristige Satz {prozent(langfristig)}"
            if eintraege else f"der langfristige Satz {prozent(langfristig)} (Tagesgeld ohne "
            "eigenen Eintrag in den Zinssätzen)")
    return (lambda wann: _zn.satz_im_monat(saetze, art, wann, langfristig)), text


def _herkunft_zins(text: str, cents: int) -> Posten:
    return Posten(
        label=_zn.ZINSEN, cents=cents, quelle="rendite", verweis="zinssaetze",
        herleitung=("Stand zu Monatsbeginn × Satz ÷ 12, am Monatsende gebucht; Satz: "
                    f"{text}. Gemessene Zinsen zählen nicht; die Jahresrechnung rechnet "
                    "den Zins aus Stand und Satz, wie hier"))


def _herkunft_steuer(cents: int) -> Posten:
    from finctl import assumptions as _ann
    from finctl.forecast.herkunft import eur, prozent

    _, quote = _ann.vorabpauschale()
    return Posten(
        label=_zn.KAPITALERTRAGSTEUER, cents=cents, quelle="regel", verweis="sparerpauschbetrag",
        herleitung=(f"{prozent(quote)} auf die Zinsen aller Konten im Kalenderjahr, soweit sie den "
                    f"Sparerpauschbetrag ({eur(_ann.sparerpauschbetrag_cents())}, im ersten Jahr "
                    "anteilig nach Restmonaten) übersteigen; fällt von dem Monat an, in dem die "
                    "Zinsen seit Januar ihn überschreiten. Über ein Jahr dieselbe Steuer wie in "
                    "der Jahresrechnung, auf die Konten nach ihrem Anteil an den Zinsen verteilt"))


def steuer_auf_zinsen(zinsen: Mapping[tuple[str, date], int],
                      erster: date) -> dict[tuple[str, date], int]:
    """Die Steuer auf die Zinsen aller Konten je (Konto, Monat), mit EINEM Pauschbetrag
    fuer den Haushalt (`zinsen.steuerplan`). `erster` ist der erste Projektionsmonat."""
    from finctl import assumptions as _ann

    _, quote = _ann.vorabpauschale()
    return _zn.steuerplan(zinsen, pauschbetrag=_ann.sparerpauschbetrag_cents(),
                          steuer_quote=quote, erster_monat=erster)


def _zinsen_der_zeilen(konto: str, zeilen) -> dict[tuple[str, date], int]:
    """Die Zinsen eines Kontos je Monat aus seinen Zeilen (Projektion oder Ausgabe)."""
    out = {}
    for z in zeilen:
        wann, detail = (z.month, z.detail) if hasattr(z, "month") else (
            date.fromisoformat(z["month"]), z["detail"])
        if detail.get(_zn.ZINSEN):
            out[(konto, wann)] = detail[_zn.ZINSEN]
    return out


def _mit_zins(projizieren, konto: str, steuer: Mapping[date, int] | None, erster: date):
    """(Projektion, Verzinsung) eines Kontos, das Zinsen verdient und Steuer zahlt.

    `projizieren(satz=…, steuer=…)` rechnet das Konto. Mit `steuer` (je Monatserster, Cent)
    gilt dieser Plan, wie ihn `household_accounts` aus den Zinsen aller Konten bildet. Ohne
    ist das Konto der Haushalt: Der Plan folgt aus seinen eigenen Zinsen und wird neu
    gerechnet, bis er sich nicht mehr aendert (`_STEUER_DURCHLAEUFE`).
    """
    verzinsung = _verzinsung(konto)
    plan = dict(steuer or {})
    for _ in range(_STEUER_DURCHLAEUFE):
        proj = projizieren(satz=verzinsung[0] if verzinsung else None, steuer=plan)
        if steuer is not None or not verzinsung:
            break
        neu = {wann: cents for (_, wann), cents in steuer_auf_zinsen(
            _zinsen_der_zeilen(konto, proj.rows), erster).items()}
        if neu == plan:
            break
        plan = neu
    return proj, verzinsung


def _herkunft_zinsen(herkunft: dict, zeilen, verzinsung) -> None:
    """Der Rechenweg von Zins und Steuer in der Ausgabe, wo das Konto sie bucht."""
    if not verzinsung:
        return
    erste = {etikett: next((z.detail[etikett] for z in zeilen if etikett in z.detail), 0)
             for etikett in (_zn.ZINSEN, _zn.KAPITALERTRAGSTEUER)}
    posten = {_zn.ZINSEN: _herkunft_zins(verzinsung[1], erste[_zn.ZINSEN]),
              _zn.KAPITALERTRAGSTEUER: _herkunft_steuer(erste[_zn.KAPITALERTRAGSTEUER])}
    herkunft.update({etikett: p.als_herkunft() for etikett, p in posten.items()
                     if etikett in herkunft})


#: Wie oft hoechstens neu gerechnet wird, bis die Steuer zu den Zinsen passt, die sie
#: selbst mitbestimmt: Sie mindert den Stand und damit den Zins ab dem Folgemonat, um
#: Cent. Meist passt es nach zwei Laeufen, ohne Steuer nach einem.
_STEUER_DURCHLAEUFE = 3


def _erster_offener_monat(conn, account: str | None = None):
    """Der erste Monat nach dem Stichtag -- fuer alle Konten derselbe."""
    return _stichtag(conn) + timedelta(days=1)


def steigerung(escalation_pa: float | None) -> float:
    """Die Steigerung kommt aus assumptions.yaml, wenn der Aufrufer keine nennt.

    An genau einer Stelle, wie jede andere Annahme auch.
    """
    if escalation_pa is not None:
        return float(escalation_pa)
    from finctl import assumptions as _ann

    try:
        return float(_ann.inflation_pa())
    except Exception:
        return 0.0


def messfenster(conn: sqlite3.Connection, heute: date):
    """Das Messfenster, wie es `heute` (der erste offene Monat) sieht: die letzten
    zwoelf vollstaendigen Monate des Haushalts. None, wenn nichts gemessen ist."""
    from finctl.forecast import abgleich as _ag

    return _ag.fenster(conn, bis=heute - timedelta(days=1))


def durchlaufende_konten(fcfg: Mapping) -> set[str]:
    """Die Konten mit der Rolle `durchlaufend`: Sie halten kein Geld, jede Zahlung wird im
    selben Moment von einem anderen Konto gedeckt."""
    return {k for k, v in (fcfg.get("account_roles") or {}).items()
            if (v or {}).get("role") == "durchlaufend"}


def deckendes_konto(conn: sqlite3.Connection, konto: str, *, bis: date,
                    gueltig: Iterable[str]) -> str | None:
    """Das Konto, das `konto` deckt: das Gegenkonto der letzten Umbuchung bis `bis`.

    Die App haelt es nirgends fest; die Umbuchung, die ein durchlaufendes Konto
    ausgleicht, sagt es. Zaehlt die Umbuchung in beide Richtungen: auch eine Erstattung
    kommt auf das Konto zurueck, das gezahlt hat. `gueltig` sind die Konten, die eine
    Kontoprognose haben (ein durchlaufendes Konto deckt kein anderes durchlaufendes).
    """
    gueltig = frozenset(gueltig) - {konto}
    for (gegen,) in conn.execute(
            """SELECT gegen FROM (
                   SELECT s.transfer_account_id AS gegen, t.booking_date AS tag, t.id AS nr
                   FROM   splits s JOIN transactions t ON t.id = s.transaction_id
                   WHERE  t.account_id = ? AND s.transfer_account_id IS NOT NULL
                   UNION ALL
                   SELECT t.account_id, t.booking_date, t.id
                   FROM   splits s JOIN transactions t ON t.id = s.transaction_id
                   WHERE  s.transfer_account_id = ?)
               WHERE tag <= ? ORDER BY tag DESC, nr DESC""",
            (konto, konto, bis.isoformat())):
        if gegen in gueltig:
            return gegen
    return None


def deckung_zum(conn: sqlite3.Connection, fcfg: Mapping, bis: date) -> dict[str, str]:
    """Je durchlaufendem Konto das Konto, das es deckt, nach den Umbuchungen bis `bis`.

    Ein durchlaufendes Konto ohne Umbuchung hat kein deckendes Konto und fehlt."""
    durchlaufend = durchlaufende_konten(fcfg)
    if not durchlaufend:
        return {}
    gueltig = [r["id"] for r in conn.execute(
        "SELECT id FROM accounts WHERE ingest_mode='parsed' AND active=1")
        if r["id"] not in durchlaufend]
    gefunden = {k: deckendes_konto(conn, k, bis=bis, gueltig=gueltig)
                for k in sorted(durchlaufend)}
    return {k: d for k, d in gefunden.items() if d}


def hashes_aus(ohne: Iterable[Mapping] | None) -> frozenset[str]:
    """Die Buchungen, die ausgeschlossene Regeln nennen, als eine Menge.

    Vertrags-Hashes und Wegfall-Hashes sind dasselbe: einzelne Buchungen, die
    die Messung nicht sieht.
    """
    return frozenset(h for regel in (ohne or ())
                     for h in regel.get("dedup_hashes") or ())


def vorschau_konto(*, since: str, until: str | None, fenster_monate: int,
                   exclude: set[str] | None, include_transfers: bool,
                   deckung: Mapping[str, str] | None, escalation_pa: float | None,
                   ends: Mapping[str, date] | None, ohne: Iterable[Mapping] | None,
                   reihen: Reihen | None = None,
                   objekte: Iterable[str] = ()) -> Vorschau:
    """Die Vorschau der Kontoprognose.

    Teile ohne Kategorie zaehlen mit, wie in der Jahresrechnung, Umbuchungen nach ihrer
    Art, und was `ohne` nennt, ersetzt der Vertrag. Die Teile der `objekte` (die mit
    Prognose) zaehlen in keiner Kategorie: Ihr Ertrag kommt aus der Prognose. `deckung`
    sagt, welches Konto ein durchlaufendes deckt: Dessen Buchungen zaehlen auf dem
    deckenden Konto.
    `fenster_monate` sind die Monate des Haushaltsfensters (`abgleich.fenster`):
    Jedes Konto teilt durch sie.
    `reihen` sind die Reihen dieses Kontos: Was in einer Reihe mit festem Takt steht,
    ist ein eigener Posten, der Rest rechnet nach der Tabelle.
    """
    return Vorschau(
        reihe="konto",
        regeln=verfahren.KONTOPROGNOSE,
        ausschluss=messung.Ausschluss(
            umbuchung="art", umbuchungen_zaehlen=include_transfers,
            deckung=tuple(sorted((deckung or {}).items())),
            hashes=hashes_aus(ohne), objekte=frozenset(objekte)),
        je_block=False, since=since, until=until or None,
        fenster_monate=fenster_monate, steigerung=steigerung(escalation_pa),
        ausser=frozenset(exclude or ()), enden=dict(ends or {}), reihen=reihen)


def objekte_mit_prognose() -> frozenset[str]:
    """Die Objekte, deren Ertrag die Prognose liefert und die Messung nicht sieht."""
    from finctl import objekte as _objekte

    return frozenset(p.id for p in _objekte.prognosen())


def erwartete_hashes(conn: sqlite3.Connection) -> frozenset[str]:
    """Die Buchungen erwarteter Einnahmen (eingeschalteter Klammern) und ihrer Reihe: Die
    Zeile in Planung ersetzt sie, in der Messung beider Modelle zaehlen sie nicht."""
    from finctl.forecast import szenarien as _sz

    return frozenset(_sz.erwartet_zugeordnet(conn, _klammern()))


def _ausschluss_hashes(conn: sqlite3.Connection, erklaerte_abos: list,
                       ohne_reihen: frozenset[str]) -> frozenset[str]:
    """Die Buchungen, die die Kontoprognose nicht misst und die auch keinen Termin
    einer Reihe bilden: was ein Vertrag mit Termin erklaert, was ein Wegfall
    herausnimmt, was der Haushalt einmalig gesetzt hat und was eine erwartete
    Einnahme ersetzt."""
    from finctl import abos as _ab
    from finctl import reihen as _reihen

    return (hashes_aus(_ab.ausschluesse(conn, erklaerte_abos)) | ohne_reihen
            | _reihen.einmalige_hashes() | erwartete_hashes(conn))


def reihen_vor(conn: sqlite3.Connection, heute: date, erklaerte_abos: list | None = None,
               *, ohne_reihen: frozenset[str] = frozenset(),
               fcfg: Mapping | None = None) -> Reihen:
    """Die Reihen des Haushalts, wie sie am Tag vor `heute` standen (der Stichtag).

    Einmal je Stichtag zu bauen und an jedes Konto zu reichen (`Reihen.fuer_konto`):
    Sie lesen die Teile der 24 Monate aller Konten. Mit denselben Buchungen draussen
    wie die Messung der Kontoprognose, sonst stuende ein erklaerter Vertrag als
    Reihe daneben. Die Teile eines durchlaufenden Kontos stehen auf dem Konto, das es
    deckt (`deckung_zum`), und damit in dessen Reihen.
    """
    from finctl import abos as _ab
    from finctl import reihen as _reihen

    if erklaerte_abos is None:
        erklaerte_abos = _ab.alle_vertraege()
    gestern = heute - timedelta(days=1)
    deckung = deckung_zum(conn, forecast_config() if fcfg is None else fcfg, gestern)
    return _reihen.laden(conn, gestern, ausschluss=messung.Ausschluss(
        deckung=tuple(sorted(deckung.items())),
        hashes=_ausschluss_hashes(conn, erklaerte_abos, ohne_reihen),
        objekte=objekte_mit_prognose()))


def kontoprognose(conn: sqlite3.Connection, account: str, fcfg: dict,
                  erklaerte_abos: list | None, *, abwahl: bool, heute: date,
                  ohne_reihen: frozenset[str], reihen: Reihen | None = None) -> Vorschau:
    """Die Vorschau eines Kontos aus `forecast.yaml`.

    Das Fenster ist das der Jahresrechnung (`abgleich.fenster`): die letzten zwoelf
    vollstaendigen Monate des Haushalts, und jedes Konto teilt durch seine Monate.
    Was aufgehoert hat -- ein Konto wird still, wenn seine Dauerauftraege auf ein
    anderes ziehen --, faellt aus dem Fenster; was frueher endet, sagt ein Wegfall
    oder ein Vertragsende.

    NUR VOLLSTAENDIGE MONATE. Ab heute zurueckgerechnet lag der angebrochene
    Monat im Fenster: ein September mit Miete, aber noch ohne Gehalt, ging als
    eigener Monat ein. `heute` ist deshalb der erste Monat nach dem Stichtag, und
    das Fenster endet am Tag davor.

    `reihen` sind die Reihen des Haushalts zu diesem Stichtag (`reihen_vor`);
    fehlen sie, werden sie hier gebaut. Zahlungen mit festem Takt rechnen als Reihe
    mit ihrem Betrag je Termin, im ganzen Fenster von 24 Monaten -- eine
    Jahrespraemie aus dem Januar steht im September noch da. Was in keiner Reihe
    steht, rechnet im kurzen Fenster.
    """
    from finctl import abos as _ab
    from finctl import reihen as _reihen
    from finctl.forecast import abgleich as _ag
    from finctl.forecast import prognosebasis as _pb

    f = _ag.fenster(conn, bis=heute - timedelta(days=1))
    if erklaerte_abos is None:
        erklaerte_abos = _ab.alle_vertraege()

    # Konten, die nichts halten: Ihre Buchungen zaehlen auf dem Konto, das sie deckt.
    deckung = deckung_zum(conn, fcfg, heute - timedelta(days=1))
    # kredit/* comes from the amortisation schedules, never from history. A loan
    # account carried BOTH: the rate inferred from its own payments plus the full
    # rate from the schedule, so an account that is neutral by construction
    # projected into the red.
    #
    # Zinsen und Kapitalertragsteuer messen wir nicht, wir rechnen sie: `engine.project`
    # verzinst den Stand jedes Monats (`_verzinsung`), `steuerplan` setzt den Freibetrag an.
    # Was gemessen im Fenster steht, zaehlte die Zinsen doppelt.
    # Was durch eine Entscheidung AUFHOERT, steht nicht hier, sondern als
    # Wegfall-Zeile auf /planung oder als Kuendigung auf /abos -- siehe
    # `wegfall_posten`.
    kredite = {r["id"] for r in conn.execute(
        "SELECT id FROM mgmt_categories WHERE parent_id = 'kredit'")}
    # Unter Fortschreibung (/prognosebasis) abgewaehlt: gilt fuer BEIDE Rechnungen.
    abgewaehlt = _pb.nicht_fortschreiben() if abwahl else set()
    # Einmaliges kommt nicht wieder: Kategorien mit dem Merkmal fallen heraus, gesetzte
    # Buchungen stehen in den Hashes der Messung (`_ausschluss_hashes`).
    einmalig = _ag.einmalige_kategorien(conn)

    # Gebaut, wo sie fehlen; sonst ohne die Buchungen eines Wegfalls (`ohne_buchungen`).
    reihen = (reihen_vor(conn, heute, erklaerte_abos, ohne_reihen=ohne_reihen, fcfg=fcfg)
              if reihen is None else reihen.ohne_buchungen(ohne_reihen))
    # Was eine feste Zahl ersetzt (der Gehaltsfloor), hat seine eigene Quelle: Seine
    # Reihen zaehlen im Rest, wo der Floor sie ersetzt. Als Reihe daneben stuende
    # derselbe Betrag zweimal da, und der Floor stuende auch auf ihrem Termin.
    eigene_quelle = frozenset(_income_overrides(fcfg, heute.year))
    return vorschau_konto(
        since=(f.von if f else add_months(heute, -_ag.FENSTER_MONATE)).isoformat(),
        until=(f.bis if f else heute - timedelta(days=1)).isoformat(),
        fenster_monate=f.monate if f else 0,
        exclude=(set(fcfg.get("exclude_from_recurring", []) or [])
                 | kredite | abgewaehlt | set(einmalig) | _zn.GERECHNET),
        include_transfers=False, deckung=deckung,
        escalation_pa=None,
        # Bekannte Enden, wo eines belegt ist. Ueber zwoelf Monate entbehrlich,
        # ueber sechzig nicht.
        ends=_enden(fcfg),
        # Was in `abos.yaml` mit Termin erklaert ist, wird nicht zusaetzlich
        # gemessen -- sonst stuende derselbe Betrag zweimal da. Ebenso, was der
        # Haushalt einmalig gesetzt hat.
        ohne=[*_ab.ausschluesse(conn, erklaerte_abos),
              {"dedup_hashes": sorted(frozenset(ohne_reihen) | _reihen.einmalige_hashes()
                                      | erwartete_hashes(conn))}],
        reihen=reihen.fuer_konto(account).ohne(eigene_quelle),
        objekte=objekte_mit_prognose())


def abgeleitete_posten(conn, account: str, fcfg: dict,
                       erklaerte_abos: list | None = None, *,
                       abwahl: bool = True, stichtag=None,
                       ohne_reihen: frozenset[str] = frozenset(),
                       reihen: Reihen | None = None) -> list:
    """Die aus dem Ledger abgeleiteten Posten eines Kontos.

    Eigene Funktion, weil die Fortschreibung auf /prognosebasis dieselben Posten zeigt, die die
    Kontoprognose rechnet -- eine zweite Ableitung daneben liefe auseinander.

    `stichtag` (ein Monatserster) rechnet so, als waere heute dieser Tag:
    Fenster davor, keine Buchung ab dem Stichtag. Fuer den Treffer-Check.

    `ohne_reihen` laesst diese Buchungen aus der Messung -- so rechnet
    `wegfall_posten`, was eine Reihe in der Prognose ausmacht.

    `reihen` sind die Reihen des Haushalts zum selben Stichtag (`reihen_vor`), wer
    viele Konten rechnet, baut sie einmal; `ohne_reihen` nimmt `kontoprognose` dann aus
    ihnen heraus.

    Ein durchlaufendes Konto hat keine eigenen Posten: Seine Buchungen stehen auf dem
    Konto, das es deckt.
    """
    from finctl.forecast import engine as fc

    if account in durchlaufende_konten(fcfg):
        return []
    vorschau = kontoprognose(
        conn, account, fcfg, erklaerte_abos, abwahl=abwahl,
        heute=stichtag or _erster_offener_monat(conn, account),
        ohne_reihen=ohne_reihen, reihen=reihen)
    return fc.recurring_items(conn, account, vorschau)


def forecast_config() -> dict:
    """config/forecast.yaml mit den Kontenregeln, gelesen.

    Eine Stelle, weil die Regeln an sechs Punkten gelesen werden -- Rolle,
    Untergrenze, Deckel, Abraeumen, Auffuellen, Budget. Die Kontenseite schreibt
    in dieselbe Datei.
    """
    from finctl import kontenregeln as _kr

    pfad = CONFIG_DIR / "forecast.yaml"
    return _kr.aus_spec((yaml_lesen(pfad) or {}) if pfad.exists() else {})


def _vertragsposten(conn: sqlite3.Connection, account: str, abos: list, ab: date,
                    bis: date, *, gedeckt: Iterable[str] = (),
                    pausen: Mapping[str, tuple] | None = None) -> list:
    """Die Termine der erklaerten Vertraege eines Kontos, mit der Steigerung der Messung.

    Ein Vertrag steigt wie eine gemessene Reihe (`vertragsbetrag`); sein Beitrag in eine
    Police bleibt fest. Ein Vertrag auf einem durchlaufenden Konto, das dieses Konto deckt
    (`gedeckt`), zaehlt hier. `pausen` sind die Monate, in denen eine Wegfall-Zeile einen
    Vertrag aussetzt (`vertraege.pausen`).
    """
    from finctl import abos as _ab
    from finctl.forecast import engine as fc

    fenster = messfenster(conn, _erster_offener_monat(conn, account))
    mitte, rate, police = (fenster.mitte if fenster else None, steigerung(None),
                           police_vertraege())
    out = []
    for termin in _ab.posten(abos, {account, *gedeckt}, ab=ab, bis=bis, pausen=pausen):
        abo = termin["abo"]
        cents = vertragsbetrag(abo, termin["faellig"], mitte=mitte, rate=rate, police=police)
        if abo["id"] in police:
            zusatz = "; nominal fest (Beitrag in eine Police)"
        elif mitte is not None and rate:
            zusatz = (f"; Betrag am Vertrag {eur_genau(abo['betrag_cents'])}, steigt mit "
                      f"{prozent(rate)} Inflation im Jahr, stetig ab der Mitte des "
                      "Messfensters, wie eine gemessene Reihe")
        else:
            zusatz = ""
        out.append(fc.OneOff(
            label=f"abo:{abo['id']}", account_id=account,
            month=termin["faellig"], amount_cents=cents,
            day=termin["faellig"].day,
            herkunft=Posten(
                label=f"abo:{abo['id']}", cents=cents,
                quelle="vertrag", verweis=f"abo:{abo['id']}",
                herleitung=f"Termin und Betrag aus "
                           f"{_ab.ARTEN[abo.get('art', 'abo')][0]}; die "
                           "zugeordneten Buchungen zählen dafür nicht "
                           "mehr in der Messung" + zusatz)))
    return out


def _anteilsposten(conn: sqlite3.Connection, account: str, abos: list, ab: date,
                   bis: date, *, gedeckt: Iterable[str] = (),
                   pausen: Mapping[str, tuple] | None = None,
                   durchlaufend: Collection[str] = ()) -> list:
    """Was die Mitzahler an jedem Termin eines Vertrags erwartet zahlen, als Eingang.

    Der Anteil laut Besetzung, wo es keinen angelegten Zeitraum gibt (`vertraege.anteil_am_termin`);
    sonst gilt der offene Anteil des Zeitraums. Er steigt wie der Betrag am Vertrag und landet
    auf dem Konto, auf dem die Mitzahler zuletzt gezahlt haben, sonst auf dem des Vertrags; ein
    durchlaufendes Konto zaehlt auf dem, das es deckt (`gedeckt`) und hat selbst nichts
    (`durchlaufend`).
    """
    from finctl import abos as _ab
    from finctl.forecast import engine as fc

    if account in durchlaufend:
        return []
    fenster = messfenster(conn, _erster_offener_monat(conn, account))
    mitte, rate, police = (fenster.mitte if fenster else None, steigerung(None),
                           police_vertraege())
    konten = {account, *gedeckt}
    out = []
    for abo in abos:
        if (not abo["geteilt"]["besetzung"]
                or (_ab.eingangskonto(conn, abo) or abo["konto"]) not in konten):
            continue
        for termin in vertraege.termine(abo, (pausen or {}).get(abo["id"], ()), ab=ab, bis=bis):
            cents = vertraege.anteil_am_termin(abo, termin, mitte=mitte, rate=rate, police=police)
            if cents:
                out.append(fc.OneOff(
                    label=f"abo-anteil:{abo['id']}", account_id=account,
                    month=termin.replace(day=1), amount_cents=cents,
                    herkunft=Posten(
                        label=f"abo-anteil:{abo['id']}", cents=cents, quelle="regel",
                        verweis=f"abo:{abo['id']}",
                        herleitung="Anteil der Mitzahler laut Besetzung, an jedem Termin ohne "
                                   "angelegten Zeitraum" + (
                                       ", steigt wie der Betrag am Vertrag"
                                       if mitte is not None and rate else ""))))
    return out


def projizierte_konten(conn: sqlite3.Connection, fcfg: Mapping) -> set[str]:
    """Die Konten, die `household_accounts` rechnet: mit Auszuegen, aktiv, nicht durchlaufend."""
    durchlaufend = durchlaufende_konten(fcfg)
    return {r["id"] for r in conn.execute(
        "SELECT id FROM accounts WHERE ingest_mode='parsed' AND active=1")
        if r["id"] not in durchlaufend}


def konto_des_objekts(conn: sqlite3.Connection, fcfg: Mapping, property_id: str,
                      stichtag: date, betrieb: str | None) -> tuple[str | None, str]:
    """Auf welchem Konto ein Objekt mit Prognose zaehlt, und warum.

    Auf dem Konto, auf dem seine Miete zuletzt gebucht wurde; ein durchlaufendes Konto
    zaehlt auf dem, das es deckt. Gibt es keine Miete oder das Konto hat keine Prognose,
    auf dem Betriebskonto.
    """
    konto = _ob.konto_der_miete(conn, property_id, stichtag)
    if konto is not None:
        konto = deckung_zum(conn, fcfg, stichtag).get(konto, konto)
        if konto in projizierte_konten(conn, fcfg):
            return konto, "dem Konto, auf dem die Miete des Objekts zuletzt einging"
    return betrieb, ("dem Betriebskonto, weil dem Objekt noch keine Miete auf einem Konto "
                     "der Prognose zugeordnet ist")


def objekte_ohne_konto(conn: sqlite3.Connection, fcfg: Mapping | None = None) -> list:
    """Die Objekte mit Prognose, die das Monatsmodell auf kein Konto buchen kann.

    Ihre Miete ist auf keinem Konto der Prognose gebucht, und es gibt kein Betriebskonto, auf
    das sie ausweichen (`konto_des_objekts`): Miete und Kosten fehlen dann auf `/konten`,
    ohne dass etwas es sagt."""
    from finctl import objekte as _objekte

    fcfg = forecast_config() if fcfg is None else fcfg
    betrieb, stichtag = _operating_account(fcfg), _stichtag(conn)
    return [p for p in _objekte.prognosen()
            if konto_des_objekts(conn, fcfg, p.id, stichtag, betrieb)[0] is None]


#: Der Tag, auf den ein Posten ohne Buchung fällt: die Monatsmitte.
_TAG_OHNE_BUCHUNG = 15


def tage_des_objekts(conn: sqlite3.Connection, objekt_id: str, stichtag: date) -> tuple[int, int]:
    """Der Tag im Monat, an dem ein Objekt mit Prognose im Monatsmodell bucht: (Miete, Kosten).

    Die Miete fällt auf den Tag ihrer jüngsten Buchung bis zum Stichtag, mit derselben
    Abfrage wie `objektposten.konto_der_miete`. Die Kosten fallen auf den Median der Tage
    aller Kostenbuchungen (Buchungsteile unter null) des Objekts in den zwölf Monaten bis
    zum Stichtag, abgerundet. Fehlt eine der beiden, gilt die Monatsmitte.
    """
    miete = conn.execute(
        """SELECT t.booking_date
           FROM   splits s JOIN transactions t ON t.id = s.transaction_id
           WHERE  s.property_id = ? AND s.mgmt_category_id = ? AND t.booking_date <= ?
           ORDER  BY t.booking_date DESC, t.id DESC LIMIT 1""",
        (objekt_id, _ob.MIETE_KATEGORIE, stichtag.isoformat())).fetchone()
    kosten = [date.fromisoformat(zeile[0]).day for zeile in conn.execute(
        """SELECT t.booking_date
           FROM   splits s JOIN transactions t ON t.id = s.transaction_id
           WHERE  s.property_id = ? AND s.amount_cents < 0
           AND    t.booking_date >= ? AND t.booking_date <= ?""",
        (objekt_id, add_months(stichtag.replace(day=1), -11).isoformat(),
         stichtag.isoformat()))]
    tag_miete = date.fromisoformat(miete[0]).day if miete else _TAG_OHNE_BUCHUNG
    tag_kosten = math.floor(statistics.median(kosten)) if kosten else _TAG_OHNE_BUCHUNG
    return tag_miete, tag_kosten


def _tag_im_monat(tag: int, monat: date) -> int:
    """Der Tag, auf den letzten Tag des Monats gekuerzt: der 31. ist im Februar der 28."""
    return min(tag, calendar.monthrange(monat.year, monat.month)[1])


def _objektposten(conn: sqlite3.Connection, account: str, fcfg: Mapping, stichtag: date,
                  months: int, betrieb: str | None) -> list:
    """Miete und Kosten der Objekte mit Prognose als Posten je Monat dieses Kontos.

    Die Rechnung steht in `objektposten.betraege` und ist die der Jahresrechnung: Prognose
    des Objekts, zum 1. Januar mit der Inflation gesteigert, die Miete nach der Saison, nichts
    ab dem Verkauf und ausserhalb von `ab` und `bis`. Seine gemessenen Buchungen zaehlen
    dafuer nirgends (`Ausschluss.objekte`). Der Tag je Posten kommt aus `tage_des_objekts`.
    """
    from finctl import objekte as _objekte
    from finctl.forecast import engine as fc
    from finctl.forecast import jahre as _jahre

    hier = {}
    for p in _objekte.prognosen():
        konto, warum = konto_des_objekts(conn, fcfg, p.id, stichtag, betrieb)
        if konto == account:
            hier[p.id] = (p, warum)
    if not hier:
        return []
    basisjahr = (stichtag + timedelta(days=1)).year
    rate = steigerung(None)
    verkauf = {v.property_id: v.ab for v in _jahre.verkaeufe(conn, basisjahr)}
    erster = fc.add_months(stichtag.replace(day=1), 1)
    out = []
    for p, warum in hier.values():
        ab = verkauf.get(p.id)
        tag_miete, tag_kosten = tage_des_objekts(conn, p.id, stichtag)
        for i in range(months):
            monat = fc.add_months(erster, i)
            miete_und_kosten = _ob.betraege(p, monat, basisjahr, rate, ab)
            if miete_und_kosten is None:
                continue
            for etikett, was, cents, tag in (
                    (_ob.MIETE_ETIKETT, "Miete", miete_und_kosten[0], tag_miete),
                    (_ob.KOSTEN_ETIKETT, "Kosten", -miete_und_kosten[1], tag_kosten)):
                if cents:
                    out.append(fc.OneOff(
                        label=f"{etikett}{p.id}", account_id=account, month=monat,
                        amount_cents=cents, day=_tag_im_monat(tag, monat),
                        herkunft=_herkunft_objekt(p, was, cents, basisjahr, rate, ab, warum,
                                                  etikett)))
    return out


def _herkunft_objekt(p, was: str, cents: int, basisjahr: int, rate: float, verkauf_ab,
                     warum: str, etikett: str) -> Posten:
    """Der Rechenweg eines Objektpostens: woher der Betrag kommt und was nicht mehr zaehlt."""
    je_monat = p.miete_cents if was == "Miete" else p.kosten_cents
    saison = (", nach der Saison des Objekts"
              if was == "Miete" and _ob.hat_saison(p) else "")
    laufzeit = (f", von {p.ab.month:02d}/{p.ab.year}" if p.ab else "") + (
        f" bis {p.bis.month:02d}/{p.bis.year}" if p.bis else "")
    ende = (f", bis zum Verkauf {verkauf_ab.month:02d}/{verkauf_ab.year}" if verkauf_ab else "")
    return Posten(
        label=f"{etikett}{p.id}", cents=cents, quelle="annahme", verweis=p.id, objekt=True,
        herleitung=(f"{was} laut Prognose des Objekts {p.name}: {eur_genau(je_monat)} je Monat, "
                    f"zum 1. Januar × {prozent(rate)} Inflation seit {basisjahr}{saison}"
                    f"{laufzeit}{ende}; steht auf {warum}. Die gemessenen Buchungen des "
                    "Objekts zählen dafür nicht mehr; die Jahresrechnung rechnet mit "
                    "denselben Zahlen"))


def account_forecast(conn, account: str, *, months: int = HORIZON_DEFAULT,
                     extra_one_offs: list | None = None,
                     allow_sweep: bool = True, reihen: Reihen | None = None,
                     steuer: Mapping[date, int] | None = None) -> dict:
    """Per-account projection with the intra-month trough.

    Lived inside the Typer command, so the only way to see whether the Giro
    dips below its floor was to open a terminal -- which is the same reason
    the monthly import never got run. Same treatment as ingest: the work
    moves here and both callers stay thin.

    `reihen` sind die Reihen des Haushalts zum Stichtag (`reihen_vor`); wer mehrere
    Konten rechnet, baut sie einmal, sonst liest jedes Konto die Teile der 24 Monate.

    Das Konto verdient Zinsen aus seinem Stand (`_verzinsung`), und die Steuer darauf
    kommt als `steuer` (je Monatserster, Cent): Der Freibetrag gilt fuer den Haushalt,
    also rechnet `household_accounts` sie aus den Zinsen aller Konten. Ohne `steuer`
    ist dieses Konto der Haushalt und rechnet den Plan aus seinen eigenen Zinsen.
    """
    from datetime import date as _date

    from finctl.forecast import engine as fc
    from finctl.realestate.loan import amortise, opening_balance_cents, segments_from

    acct = conn.execute(
        "SELECT id, dispo_threshold_cents FROM accounts WHERE id = ?", (account,)
    ).fetchone()
    if acct is None:
        raise ValueError(f"unknown account: {account}")

    # Start am STICHTAG, dem Ende des letzten Monats, den alle Konten ganz
    # abdecken. Ein neuerer Snapshot oder ein Auszug bis zum 4. zaehlt nicht:
    # der erste Prognosemonat ist immer ein ganzer, und was in ihm schon
    # gebucht ist, rechnet die Prognose selbst -- sonst stuende es doppelt
    # oder gar nicht da.
    stichtag = _stichtag(conn)
    as_of = stichtag.isoformat()
    saldo = _saldo_zum(conn, account, stichtag)
    if saldo is not None:
        opening, source = saldo, "statement close"
    else:
        snap = conn.execute(
            "SELECT balance_cents FROM balance_snapshots WHERE account_id=? "
            "AND as_of <= ? ORDER BY as_of DESC LIMIT 1", (account, as_of)).fetchone()
        opening, source = ((snap["balance_cents"], "live snapshot") if snap
                           else (0, "assumed zero"))

    fcfg = forecast_config()
    notgroschen = _ng.untergrenze(account, fcfg)
    from finctl import abos as _ab

    erklaerte_abos = _ab.alle_vertraege()
    reihen = reihen or reihen_vor(conn, stichtag + timedelta(days=1), erklaerte_abos,
                                  fcfg=fcfg)
    recurring = abgeleitete_posten(conn, account, fcfg, erklaerte_abos, reihen=reihen)
    abgeleitet = list(recurring)       # ohne die Budgets, fuer wegfall_posten

    # Budgets, declared rather than derived. This is the model the spreadsheet
    # ran: a fixed allocation in, observed spending out. It has to be declared
    # because history cannot see a decision -- an allocation cut from 100 to 50
    # last month, and no median over the preceding months knows that.
    betrieb = _operating_account(fcfg)
    for account_id, cents in _notizen.ohne(fcfg.get("account_budgets")).items():
        # DIE GEGENSEITE. Die Zuweisung kommt per Dauerauftrag vom
        # Betriebskonto, und dort ist sie ein Abgang. Ohne diese Zeile zaehlte
        # die Prognose das Geld auf dem Zielkonto als Zufluss und liess es auf
        # dem Betriebskonto trotzdem liegen -- jeden Monat die ganze Zuweisung,
        # die der Treffer-Check als systematisch zu optimistische Prognose zeigte.
        if cents and account == betrieb and account_id != account:
            recurring.append(fc.RecurringItem(
                label=f"budget:{account_id}", account_id=account,
                amount_cents=-int(cents), category="transfer/eigenkonto",
                herkunft=Posten(
                    label=f"budget:{account_id}", cents=-int(cents),
                    quelle="regel", verweis="account_budgets", umbuchung=True,
                    herleitung=f"Dauerauftrag an {account_id} laut "
                               "forecast.yaml (account_budgets)")))
        if account_id != account or not cents:
            continue
        recurring.append(fc.RecurringItem(
            label="budget/zuweisung", account_id=account,
            amount_cents=int(cents), category="transfer/eigenkonto",
            herkunft=Posten(
                label="budget/zuweisung", cents=int(cents), quelle="regel",
                verweis="account_budgets", umbuchung=True,
                herleitung="feste Zuweisung je Monat aus forecast.yaml "
                           "(account_budgets), nicht gemessen")))

    from finctl.forecast import szenarien as _szk
    from finctl.realestate.loan import lade_kredite as _lade
    from finctl.realestate.loan import nur_wirksame as _wirksam

    schedules = []
    # Nur wirksame Kredite: eine Vorlage wie das Eigenheim rechnet nur mit,
    # solange ihre Klammer an ist -- wie in der Jahresrechnung.
    for loan in _wirksam(_lade(CONFIG_DIR), _szk.aktive_ids()):
        if not loan.get("segments") or loan.get("servicing_account_id") != account:
            continue
        schedules.append(amortise(
            str(loan["id"]), opening_balance_cents(loan), segments_from(loan)))


    one_offs = []

    # config/planned.yaml ist am 13.09.2026 entfallen. Sie trug datierte
    # Verpflichtungen, und alle sind in Klammern gewandert -- dort stehen sie
    # neben dem Vorgang, zu dem sie gehoeren, statt in einer flachen Liste.
    #
    # WAS DAMIT WEGFAELLT und im Zeilenmodell fehlt, falls es wieder gebraucht
    # wird: Fremdwaehrung (amount_foreign/fx_rate, der Eurobetrag abgeleitet)
    # und zweiseitige Deckung (`funding`: Geld verlaesst das Tagesgeld am 7.
    # und kommt auf dem Girokonto an). Eine Klammerzeile gehoert zu EINEM Konto.
    #
    # engine.planned_amount_cents und engine.funding_legs bleiben stehen und
    # getestet -- sie sind die Bausteine dafuer, und sie wegzuwerfen hiesse,
    # sie beim naechsten Auslandsposten neu zu schreiben.

    # Toggleable what-if plans from the dashboard. These apply ON TOP of
    # the base forecast and independently of each other: any
    # number can be switched on at once, because the question is usually
    # "can I do both".
    #
    # They live here rather than in the web layer so that every forecast sees
    # them -- the CLI included. Wiring them into one page was how the toggle
    # ended up affecting the goals but not the projection.

    stichtag_tag = _date.fromisoformat(as_of)
    overrides = _income_overrides(fcfg, (stichtag_tag + timedelta(days=1)).year)
    # Ein durchlaufendes Konto hat keine Prognose; was auf ihm steht, zaehlt auf dem
    # Konto, das es deckt.
    gedeckt = {k for k, d in deckung_zum(conn, fcfg, stichtag_tag).items() if d == account}
    one_offs.extend(_planposten(conn, account, fcfg, as_of, months, gedeckt))
    one_offs.extend(wegfall_posten(
        conn, account, _klammern(), abgeleitet,
        lambda ohne: abgeleitete_posten(conn, account, fcfg, erklaerte_abos,
                                        ohne_reihen=ohne, reihen=reihen),
        start=fc.add_months(_date.fromisoformat(as_of).replace(day=1), 1),
        months=months, overrides=overrides, gedeckt=gedeckt))

    # Die erklaerten Abos, mit ihrem TERMIN statt als Zwoelftel. Genau das
    # unterscheidet diese Ansicht von einem Median: die 84,00 gehen an einem
    # Tag ab und nicht mit 10 im Monat, und die Senke liest den Tag.
    horizont_abos = fc.add_months(_date.fromisoformat(as_of).replace(day=1),
                                  months + 1)
    pausen = vertraege.pausen(conn, _klammern(), erklaerte_abos)
    one_offs.extend(_vertragsposten(conn, account, erklaerte_abos, stichtag_tag,
                                    horizont_abos, gedeckt=gedeckt, pausen=pausen))

    # Was die Mitzahler erwartet zahlen, wo es keinen Zeitraum gibt: ihr Anteil je Termin.
    one_offs.extend(_anteilsposten(conn, account, erklaerte_abos, stichtag_tag,
                                   horizont_abos, gedeckt=gedeckt, pausen=pausen,
                                   durchlaufend=durchlaufende_konten(fcfg)))

    # Miete und Kosten der Objekte mit Prognose, auf dem Konto, auf dem die Miete einging.
    one_offs.extend(_objektposten(conn, account, fcfg, stichtag_tag, months, betrieb))

    # Und was Mitzahler noch schulden -- nur der offene Teil, im Einsammel-
    # Monat. Ist das Geld da, faellt der Posten von selbst heraus.
    for rueck in _ab.rueckzahlungen(conn, erklaerte_abos, {account, *gedeckt},
                                    ab=stichtag_tag + timedelta(days=1),
                                    bis=horizont_abos):
        one_offs.append(fc.OneOff(
            label=f"abo-zurueck:{rueck['abo']['id']}", account_id=account,
            month=rueck["monat"], amount_cents=rueck["cents"],
            herkunft=Posten(
                label=f"abo-zurueck:{rueck['abo']['id']}", cents=rueck["cents"],
                quelle="regel", verweis=f"abo:{rueck['abo']['id']}",
                herleitung="offener Anteil der Mitzahler laut "
                           f"{_ab.ARTEN[rueck['abo'].get('art', 'abo')][0]}, "
                           "im Einsammel-Monat")))

    # Money swept in from another account is real income here. Without it the
    # savings account shows the target but never the deposits that reach it.
    one_offs.extend(extra_one_offs or [])

    start = _date.fromisoformat(as_of)
    erster = fc.add_months(start.replace(day=1), 1)
    proj, verzinsung = _mit_zins(
        partial(fc.project, account_id=account, opening_cents=opening, start=erster,
                months=months, recurring=recurring, one_offs=one_offs,
                loan_schedules=schedules,
                dispo_threshold_cents=_untergrenze(account, fcfg, acct),
                sweep_above_cents=_sweep_ceiling(account, fcfg) if allow_sweep else None,
                income_overrides=overrides),
        account, steuer, erster)
    herkunft = _herkunft_konto(fcfg, overrides, recurring, one_offs, schedules,
                               proj.rows)
    _herkunft_zinsen(herkunft, proj.rows, verzinsung)

    # An account can be wrong in two directions. A Giro is capped because its
    # only job is avoiding the Dispo and it pays no interest -- anything above
    # the cap is money sitting idle that belongs on the Tagesgeld. Warning only
    # downwards would treat 40.000 parked on a current account as a success.
    role = (fcfg.get("account_roles") or {}).get(account) or {}
    ceiling = role.get("ceiling_cents")
    if not ceiling and role.get("ceiling_months"):
        typical = sorted(-r.costs_cents for r in proj.rows)
        if typical:
            typical = typical[len(typical) // 2]     # median month, not the worst
            ceiling = int(round(typical * float(role["ceiling_months"])))
    over = [r for r in proj.rows if ceiling and r.closing_cents > ceiling]

    return {
        "account": account,
        "opening_cents": opening, "opening_as_of": as_of, "opening_source": source,
        "dispo_threshold_cents": proj.dispo_threshold_cents,
        # Die Grenze des Notgroschens, wenn er auf diesem Konto liegt (sie steckt in der
        # Untergrenze oben), und die Untergrenze, die die Kontoregel allein sagt.
        "notgroschen_cents": notgroschen or None,
        "regel_untergrenze_cents": _floor_for(account, fcfg, acct),
        "role": role.get("role"), "role_note": role.get("note"),
        "budget_cents": (fcfg.get("account_budgets") or {}).get(account),
        "ceiling_cents": ceiling,
        "over_ceiling_months": [r.month.isoformat() for r in over],
        "sweep_total_cents": sum(r.swept_cents for r in proj.rows),
        "sweeps_to": ((fcfg.get("account_roles") or {}).get(account) or {}).get("sweep_to"),
        "idle_cents": max((r.closing_cents - ceiling for r in over), default=0),
        # WOFUER, nicht nur WIE VIEL. `project` baut das Detail je Monat
        # ohnehin; es hier wegzuwerfen war der Grund, warum ein teurer Monat
        # auf `/konten` teuer aussah, ohne zu sagen, was ihn teuer macht --
        # genau die Frage, die die Tabellenkalkulation vorher beantwortet hat.
        "labels": _anzeigenamen(conn, proj.rows),
        # Je Etikett, woher der Betrag kommt. Dieselben Quellen wie im
        # Rechenweg der Jahresrechnung, damit beide Seiten vergleichbar sind.
        "herkunft": herkunft,
        "rows": [
            {"month": r.month.isoformat(), "opening_cents": r.opening_cents,
             "costs_cents": r.costs_cents, "trough_cents": r.trough_cents,
             "income_cents": r.income_cents, "closing_cents": r.closing_cents,
             "breaches_dispo": r.breaches_dispo, "swept_cents": r.swept_cents,
             "detail": dict(sorted(r.detail.items(), key=lambda kv: kv[1]))}
            for r in proj.rows
        ],
        "worst_trough_cents": proj.worst.trough_cents if proj.worst else None,
        "worst_month": proj.worst.month.isoformat() if proj.worst else None,
        "breach_months": [r.month.isoformat() for r in proj.breaches],
    }


def household_accounts(conn, *, months: int = HORIZON_DEFAULT) -> list[dict]:
    """Jedes Konto mit seinen Umbuchungen, Zinsen und der Steuer darauf (`_haushalt`).

    Der Freibetrag auf Zinsen gilt fuer den Haushalt und das Kalenderjahr, ueber alle
    Konten. Welche Steuer wann faellt, folgt aus den Zinsen aller Konten; die Steuer
    mindert den Stand und damit den Zins ab dem Folgemonat. Also wird gerechnet, den
    Plan aus den Zinsen des Laufs davor gebildet, bis er sich nicht mehr aendert
    (hoechstens `_STEUER_DURCHLAEUFE` Mal; ohne Steuer ist es einer). Die Ausgabe ist
    die des letzten Laufs.
    """
    fcfg = forecast_config()
    # Die Reihen des Haushalts einmal, nicht je Konto und je Durchlauf.
    reihen = reihen_vor(conn, _stichtag(conn) + timedelta(days=1), fcfg=fcfg)
    erster = add_months(_stichtag(conn).replace(day=1), 1)
    plan: dict[tuple[str, date], int] = {}
    for _ in range(_STEUER_DURCHLAEUFE):
        out = _haushalt(conn, months, fcfg, reihen, plan)
        zinsen = {}
        for view in out:
            if not view.get("error"):
                zinsen.update(_zinsen_der_zeilen(view["id"], view["rows"]))
        neu = steuer_auf_zinsen(zinsen, erster) if zinsen else {}
        if neu == plan:
            break
        plan = neu
    return out


def _haushalt(conn, months: int, fcfg_cache: dict, reihen: Reihen,
              plan: Mapping[tuple[str, date], int]) -> list[dict]:
    """Every account, with the transfers between them resolved.

    Three passes, and the order is the policy:

      1. Project each account alone. Where one falls below its floor, that is
         a shortfall the operating account has to cover.
      2. Top those up from the operating account, dated to the 1st so the
         money is there BEFORE the costs that would have breached the floor.
         Not for accounts with `auffuellen: false` in forecast.yaml -- there
         only the declared standing orders count.
      3. Only what is left above the ceiling is swept to savings.

    NO OTHER ACCOUNT MAY EVER GO NEGATIVE. Sweeping first and topping up
    afterwards would move money to a savings account while a Giro sits in
    Dispo -- paying overdraft interest to earn deposit interest, which is
    the exact trade this arrangement exists to avoid.
    """
    from datetime import date as _d

    from finctl.forecast.engine import OneOff


    accounts = [dict(r) for r in conn.execute(
        "SELECT id, display_name, account_type, dispo_threshold_cents FROM accounts "
        "WHERE ingest_mode='parsed' AND active=1 ORDER BY id")]
    # Durchlaufende Konten haben keinen Bestand, den man projizieren koennte.
    # PayPal deckt jede Zahlung im selben Moment; projiziert man es wie ein
    # Girokonto, stehen die Ausgaben ohne ihre Deckung da, das Konto rutscht
    # rechnerisch ins Minus, und die Auffuellung vom Betriebskonto zaehlt
    # denselben Betrag ein zweites Mal.
    # Einmal gelesen statt je Monat: die Datei aendert sich waehrend eines
    # Laufs nicht, und sie je Zeile neu zu parsen waere sechzig Mal dieselbe
    # Arbeit.
    durchlaufend = durchlaufende_konten(fcfg_cache)
    accounts = [a for a in accounts if a["id"] not in durchlaufend]
    acct_cache = {a["id"]: a for a in accounts}

    def run(account_id, extra=None, allow_sweep=True):
        return account_forecast(
            conn, account_id, months=months, extra_one_offs=extra,
            allow_sweep=allow_sweep, reihen=reihen,
            steuer={wann: cents for (konto, wann), cents in plan.items()
                    if konto == account_id})

    base, errors = {}, {}
    for a in accounts:
        try:
            base[a["id"]] = run(a["id"], allow_sweep=False)
        except Exception as exc:
            errors[a["id"]] = f"{type(exc).__name__}: {exc}"

    # Das Konto, das die anderen versorgt, ist das mit der ROLLE `operating`
    # -- nicht einfach das erste mit einem Abraeum-Ziel. Sobald ein zweites
    # Konto eines deklariert (auf /konten ein Klick), gewann sonst das
    # alphabetisch erste: das Betriebskonto raeumte nicht mehr ab, und sein
    # Guthaben lief auf einem unverzinsten Konto auf, ohne dass sich an der
    # Regel etwas geaendert haette.
    operator = _operating_account(fcfg_cache)
    if operator not in base:
        operator = next((k for k, v in base.items() if v.get("sweeps_to")), None)

    topups: dict[str, list] = {}
    operator_cost: list = []
    for account_id, f in base.items():
        if account_id == operator:
            continue
        # Je Monat gelesen, nicht einmal fuer die ganze Projektion: ein Floor,
        # der aus einer Kreditrate stammt, aendert sich mit ihr. Steigt die
        # Rate mit der Anschlussfinanzierung, fuellte ein einmal gelesener
        # Wert danach zu wenig auf.
        rolle = (fcfg_cache.get("account_roles") or {}).get(account_id) or {}
        # Abgeschaltet je Konto: dann zaehlen nur die Dauerauftraege, und
        # eine Unterschreitung bleibt sichtbar statt still gedeckt.
        if rolle.get("auffuellen") is False:
            continue
        variabel = bool(rolle.get("floor_from_loan"))
        floor = f["dispo_threshold_cents"]
        # KUMULIERT MITFUEHREN, sonst wird jeden Monat dieselbe Luecke erneut
        # gefuellt. Die ungedeckte Projektion zeigt die Luecke als WACHSEND --
        # ein Konto faellt ab einem Monat um 200 im Monat, also 200, dann 400,
        # dann 600 --, aber nach der ersten Auffuellung ist der Rueckstand bereits
        # bezahlt und nur der Monatsbetrag kommt neu hinzu.
        #
        # Jede Monatsluecke einzeln zu ueberweisen summiert sich quadratisch:
        # nach zwoelf Monaten 15.600 statt 2.400, Faktor sechseinhalb. Dadurch
        # standen in der Prognose fast 16.000 auf einem Konto, das eine Rate
        # halten soll -- und das Betriebskonto zahlte es.
        gedeckt = 0
        for row in f["rows"]:
            wann = _d.fromisoformat(row["month"])
            if variabel:
                floor = _untergrenze(account_id, fcfg_cache,
                                     acct_cache[account_id], month=wann)
            short = floor - row["trough_cents"] - gedeckt
            if short <= 0:
                continue
            gedeckt += short
            when = wann
            label = f"Auffüllung {account_id}"
            topups.setdefault(account_id, []).append(
                OneOff(label=label, account_id=account_id, month=when,
                       amount_cents=short, day=1,
                       herkunft=Posten(
                           label=label, cents=short, quelle="regel",
                           verweis=operator, umbuchung=True,
                           herleitung=f"Tiefpunkt läge unter dem Floor; "
                                      f"{operator} füllt am 1. auf")))
            operator_cost.append(
                OneOff(label=label, account_id=operator, month=when,
                       amount_cents=-short, day=1,
                       herkunft=Posten(
                           label=label, cents=-short, quelle="regel",
                           verweis=account_id, umbuchung=True,
                           herleitung=f"an {account_id}, damit dessen "
                                      "Floor hält — vor dem Abräumen")))

    out = []
    op_view = None
    if operator:
        op_view = run(operator, extra=operator_cost)
    sweeps: dict[str, list] = {}
    if op_view:
        for row in op_view["rows"]:
            if row["swept_cents"]:
                sweeps.setdefault(op_view["sweeps_to"], []).append(OneOff(
                    label=f"Übertrag von {operator}", account_id=op_view["sweeps_to"],
                    month=_d.fromisoformat(row["month"]),
                    amount_cents=row["swept_cents"], day=28,
                    herkunft=Posten(
                        label=f"Übertrag von {operator}",
                        cents=row["swept_cents"], quelle="regel", verweis=operator,
                        umbuchung=True,
                        herleitung=f"was auf {operator} über dem Deckel "
                                   "liegt, am Monatsende abgeräumt")))

    for a in accounts:
        if a["id"] in errors:
            out.append({**a, "error": errors[a["id"]]})
            continue
        if a["id"] == operator:
            out.append({**a, **op_view, "topped_up_cents":
                        -sum(o.amount_cents for o in operator_cost)})
            continue
        extra = (topups.get(a["id"]) or []) + (sweeps.get(a["id"]) or [])
        # ABRAEUMEN NUR VOM BETRIEBSKONTO. Nur fuer dessen Uebertrag gibt es
        # die Gegenbuchung auf dem Zielkonto; bei jedem anderen verschwaende
        # die Prognose Geld, das nirgends ankommt. Ohne diese Zeile hing es
        # davon ab, ob das Konto zufaellig eine Auffuellung bekommt: mit
        # Auffuellung wurde abgeraeumt, ohne nicht.
        view = (run(a["id"], extra=extra, allow_sweep=False) if extra
                else base[a["id"]])
        # Und deshalb auch kein Ziel in der Sicht: die Seite zeigte sonst
        # „0 € → Ziel" als Regel, die nie etwas bewegt.
        out.append({**a, **view, "sweeps_to": None,
                    "topped_up_cents": sum(o.amount_cents for o in topups.get(a["id"], []))})
    return out


