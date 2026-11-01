"""Nichts aus dem Hauptbuch steht im Code -- gemessen, nicht gelistet.

`tests/test_namen.py` prueft eine Liste verbotener Namen. Eine Liste belegt
aber nur, dass DIESE Namen fehlen: Als der Code am 27.09.2026 zum ersten Mal
gegen das Hauptbuch gehalten wurde, standen darin trotzdem sechs Menschen, mit
denen Abos geteilt werden, zwei Wohnorte, eine echte IBAN, der Anfang eines
echten Kontoauszugs und die Zins- und Tilgungsbetraege eines laufenden
Kredits -- in Tests und Docstrings, also in genau dem, was weitergegeben
werden soll.

Dieser Test nimmt deshalb das Hauptbuch selbst als Liste:

* jede GEGENPARTEI, die in einer Buchung steht,
* jeden BETRAG mit Cent (ab 10 Euro), deutsch geschrieben oder als Centzahl,
* jede lange ZIFFERNFOLGE aus `config/` -- Kreditnummern, IBANs, Vertraege,
* jeden NAMEN, der in `config/` einen Anteil an etwas traegt.

Nichts davon darf im Code, in den Tests oder in der Doku stehen. Runde
Betraege zaehlen nicht (1.200,00 ist ein Beispiel, 1.217,43 eine Buchung).

Auf dem Musterhaushalt laeuft er nicht: dort IST das Hauptbuch erfunden und
steht absichtlich in `tests/musterhaushalt/`.

EINE BUCHUNG IST NICHT DAS EINZIGE, WAS SIE VERRAET. Am 02.10.2026 standen,
an allen vier Pruefungen vorbei, Kontostaende aus echten Auszuegen in
Parser-Docstrings, Monatssummen eines Kredits, ein Gehaltsmedian und ein
Endkapital in Kommentaren -- Zahlen, die aus Buchungen FOLGEN, ohne selbst
eine zu sein. Dagegen stehen drei weitere Pruefungen:

* jeder STAND, den ein Auszug nennt oder der sich Tag fuer Tag ergibt, und
  jede SUMME je Monat und Jahr nach Kategorie, Konto, Kredit und Objekt --
  das, was die Seiten anzeigen, also das, was man beim Schreiben abliest;
* BETRAEGE IN PROSA SIND RUND, im Code und in der Doku, unabhaengig vom
  Hauptbuch: Ein Median, eine Hochrechnung, ein Endkapital laesst sich nicht
  aufzaehlen, ein Beispiel auf glatte Hunderter zu setzen schon;
* kein VERWANDTER: wer im Haushalt wem Geld schuldet, ist eine Auskunft ueber
  Menschen, auch ohne Namen.
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

import pytest
import yaml

WURZEL = Path(__file__).resolve().parent.parent

ORDNER = ("finctl", "tests", "docs", "werkzeuge", ".github")
DATEIEN = ("HANDBUCH.md", "CLAUDE.md", "CHANGELOG.md", "README.md", "pyproject.toml")
ENDUNGEN = {".py", ".html", ".sql", ".yaml", ".yml", ".md", ".csv", ".txt", ".toml", ".json"}
#: Erfunden, und dort absichtlich.
AUSSER = ("tests/musterhaushalt/", "tests/beispiele/")

#: Gegenparteien, die kein Mensch und kein Ort sind: Buchungsarten, Banken,
#: Plattformen. Ein Eintrag hier ist eine Aussage -- "das ist kein Name" --
#: und keiner fuer eine Person.
KEIN_NAME = {
    "Abhebung vom Geldkonto", "Cash reward allocation", "Deutschland",
    "Erhaltene Zinsen", "Gaming", "Gemeinschaftskonto", "Kreditrate",
    "Restaurant", "Tankstelle", "Überweisung", "Vertrieb", "Vertrieb GmbH",
    "APPLE.COM/BILL", "C24 Bank", "Microsoft Payments", "Spotify",
    "PayPal Europe S.a.r.l. et Cie S.C.A", "RTL interactive GmbH",
    "JET-Tankstelle",
    # Buchungsarten und eine Handelskette, die in den mitgelieferten
    # allgemeinen Regeln stehen (finctl/vorgaben/regeln_allgemein.yaml).
    "Interest payment", "Kontoführungsentgelt", "Uniqlo",
}


def _texte() -> dict[str, str]:
    out = {}
    pfade = [p for o in ORDNER for p in (WURZEL / o).rglob("*")]
    pfade += [WURZEL / d for d in DATEIEN]
    for pfad in pfade:
        rel = pfad.relative_to(WURZEL).as_posix()
        if (not pfad.is_file() or pfad.suffix not in ENDUNGEN
                or rel.startswith(AUSSER) or "__pycache__" in rel):
            continue
        out[rel] = pfad.read_text(encoding="utf-8", errors="replace")
    return out


@pytest.fixture(scope="module")
def hauptbuch():
    if os.environ.get("FINCTL_TESTDATEN") == "muster":
        pytest.skip("auf dem Musterhaushalt ist das Hauptbuch erfunden")
    db = Path("data/finance.db")
    if not db.exists():
        pytest.skip("kein Hauptbuch")
    conn = sqlite3.connect(db)
    try:
        yield conn
    finally:
        conn.close()


def _funde(muster: re.Pattern, texte: dict[str, str]) -> list[str]:
    return [f"{datei}: {m.group(0)!r}" for datei, text in texte.items()
            for m in muster.finditer(text)]


def test_no_counterparty_from_the_ledger_appears_in_the_code(hauptbuch):
    namen = {r[0].strip() for r in hauptbuch.execute(
        "SELECT DISTINCT counterparty FROM transactions WHERE counterparty IS NOT NULL")}
    namen = {n for n in namen if len(n) >= 6 and n not in KEIN_NAME}
    muster = re.compile("|".join(re.escape(n) for n in sorted(namen, key=len, reverse=True)))
    funde = _funde(muster, _texte())
    assert not funde, "Gegenparteien aus dem Hauptbuch:\n  " + "\n  ".join(funde[:30])


def test_no_booked_amount_with_cents_appears_in_the_code(hauptbuch):
    gebucht = {r[0] for tabelle in ("transactions", "splits") for r in hauptbuch.execute(
        f"SELECT DISTINCT ABS(amount_cents) FROM {tabelle}")}
    gebucht = {c for c in gebucht if c >= 1000 and c % 100}
    funde = []
    for datei, text in _texte().items():
        for m in re.finditer(r"\b(\d{1,3}(?:\.\d{3})*),(\d{2})\b", text):
            if int(m.group(1).replace(".", "")) * 100 + int(m.group(2)) in gebucht:
                funde.append(f"{datei}: {m.group(0)}")
        # Als Centzahl erst ab 100 Euro: darunter sind es Jahreszahlen.
        for m in re.finditer(r"(?<![\d.,_])(\d{1,3}(?:_\d{3})+|\d{5,9})(?![\d_])", text):
            if int(m.group(1).replace("_", "")) in gebucht:
                funde.append(f"{datei}: {m.group(0)}")
    assert not funde, "Gebuchte Betraege:\n  " + "\n  ".join(funde[:30])


def test_no_reference_number_from_the_config_appears_in_the_code(hauptbuch):
    """Kreditnummern, Vertragsnummern, IBANs -- alles ab sieben Ziffern."""
    config = Path("config")
    nummern = set()
    for datei in config.glob("*.yaml"):
        if datei.name == "overrides.yaml":      # Hashes, keine Nummern
            continue
        nummern |= set(re.findall(r"(?<!\d)\d{7,}(?!\d)", datei.read_text(encoding="utf-8")))
    # Runde Betraege in Cent (13000000) sind keine Kennung.
    nummern = {n for n in nummern if not n.endswith("00000")}
    if not nummern:
        pytest.skip("keine Nummern in config/")
    muster = re.compile(r"(?<!\d)(" + "|".join(sorted(nummern, key=len, reverse=True))
                        + r")(?!\d)")
    funde = _funde(muster, _texte())
    assert not funde, "Nummern aus config/:\n  " + "\n  ".join(funde[:30])


def test_no_person_who_shares_a_cost_appears_in_the_code(hauptbuch):
    """Wer an einem Abo oder einer Versicherung einen Anteil traegt."""
    namen: set[str] = set()

    def sammeln(knoten) -> None:
        if isinstance(knoten, dict):
            if "anteil_cents" in knoten and isinstance(knoten.get("name"), str):
                namen.add(knoten["name"])
            for wert in knoten.values():
                sammeln(wert)
        elif isinstance(knoten, list):
            for wert in knoten:
                sammeln(wert)

    for datei in Path("config").glob("*.yaml"):
        sammeln(yaml.safe_load(datei.read_text(encoding="utf-8")))
    teile = {t for n in namen for t in [n, *re.split(r"[\s-]+", n)] if len(t) >= 4}
    if not teile:
        pytest.skip("niemand teilt etwas")
    muster = re.compile(r"\b(" + "|".join(re.escape(t) for t in sorted(teile)) + r")\b")
    funde = _funde(muster, _texte())
    assert not funde, "Namen aus config/:\n  " + "\n  ".join(funde[:30])


def _abgeleitet(conn: sqlite3.Connection) -> set[int]:
    """Was aus den Buchungen folgt: Staende und Summen, in Cent, ohne Vorzeichen."""
    werte = {abs(v) for a, e in conn.execute(
        "SELECT balance_start_cents, balance_end_cents FROM statements") for v in (a, e)}
    # Der Stand am Ende jedes Buchungstags, vom ersten Auszug je Konto an.
    for konto, anfang in conn.execute(
            "SELECT account_id, balance_start_cents FROM statements s WHERE period_start = "
            "(SELECT MIN(period_start) FROM statements WHERE account_id = s.account_id)"):
        stand = anfang
        for (summe,) in conn.execute(
                "SELECT SUM(amount_cents) FROM transactions WHERE account_id = ? "
                "GROUP BY booking_date ORDER BY booking_date", (konto,)):
            stand += summe
            werte.add(abs(stand))
    achsen = ("s.mgmt_category_id", "m.parent_id", "t.account_id", "m.kind", "m.fixkosten",
              "s.loan_id", "s.property_id", "'alle'")
    for laenge in (7, 4):                       # Monat, Jahr
        for achse in achsen:
            werte |= {abs(r[0]) for r in conn.execute(
                f"SELECT SUM(s.amount_cents) FROM splits s "
                f"JOIN transactions t ON t.id = s.transaction_id "
                f"LEFT JOIN mgmt_categories m ON m.id = s.mgmt_category_id "
                f"GROUP BY substr(t.booking_date, 1, {laenge}), {achse}") if r[0]}
    return {w for w in werte if w >= 1000 and w % 100}


def test_no_balance_or_sum_from_the_ledger_appears_in_the_code(hauptbuch):
    """Staende und Summen mit Cent, wie die Seiten sie zeigen."""
    abgeleitet = _abgeleitet(hauptbuch)
    funde = [f"{datei}: {m.group(0)}" for datei, text in _texte().items()
             for m in re.finditer(r"\b(\d{1,3}(?:\.\d{3})*),(\d{2})\b", text)
             if int(m.group(1).replace(".", "")) * 100 + int(m.group(2)) in abgeleitet]
    assert not funde, "Staende und Summen aus dem Hauptbuch:\n  " + "\n  ".join(funde[:30])


#: Schreibweisen, keine Betraege: so sieht eine Zahl aus, nicht was jemand hat.
FORMATBEISPIELE = {"1.234", "12.345", "1.234.567", "12.345.678", "1.234,56", "12,34"}

#: Wo Prosa steht, die weitergegeben wird. Tests rechnen mit krummen Zahlen,
#: die sie selbst erfinden; dort wacht das Hauptbuch (oben).
PROSA_ORDNER = ("finctl", "docs", "werkzeuge", ".github")

_MIT_CENT = re.compile(r"(?<![\d.,{])(\d{1,3}(?:\.\d{3})*),(\d{2})(?!\d)")
_GANZE_EURO = re.compile(r"(?<![\d.,])([1-9]\d{0,2}(?:\.\d{3})+)(?!\d|[.,]\d)")


def _prosa() -> dict[str, str]:
    """Kommentare und Zeichenketten aus Python, alles andere ganz.

    Im Python-Code selbst ist `1.025` ein Faktor und keine Tausenderzahl.
    """
    import io
    import tokenize

    out = {}
    for datei, text in _texte().items():
        if not datei.startswith(PROSA_ORDNER) and datei not in DATEIEN:
            continue
        if datei.endswith(".py"):
            text = "\n".join(
                t.string for t in tokenize.generate_tokens(io.StringIO(text).readline)
                if t.type in (tokenize.COMMENT, tokenize.STRING, tokenize.FSTRING_MIDDLE))
        out[datei] = text
    return out


def test_amounts_in_prose_are_round():
    """Ab 10 Euro: glatte Cent, ab 1.000 glatte Hunderter.

    Unter 1.000 ohne Cent laesst sich ein Betrag nicht von einer Anzahl
    unterscheiden; dort bleibt es bei der Regel aus CLAUDE.md.
    """
    funde = []
    for datei, text in _prosa().items():
        for m in _MIT_CENT.finditer(text):
            cent = int(m.group(1).replace(".", "")) * 100 + int(m.group(2))
            if cent >= 1000 and cent % 100 and m.group(0) not in FORMATBEISPIELE:
                funde.append(f"{datei}: {m.group(0)}")
        for m in _GANZE_EURO.finditer(text):
            if int(m.group(1).replace(".", "")) % 100 and m.group(1) not in FORMATBEISPIELE:
                funde.append(f"{datei}: {m.group(1)}")
    assert not funde, ("Krumme Betraege -- erfinden und runden, oder als Schreibweise "
                       "in FORMATBEISPIELE:\n  " + "\n  ".join(funde[:40]))


#: Je Wort der erste Buchstabe als Klasse: So steht keins woertlich hier, und
#: `tests/test_namen.py` zaehlt die Liste nicht selbst als Fundstelle --
#: manche dieser Woerter stehen auch in `config/verbotene_namen.yaml`.
_VERWANDTE = re.compile(
    r"\b(?:[s]chwester|[b]ruder|[b]r(?:ue|ü)der|[m]utter|[v]ater|[e]lternteil|[t]ochter|"
    r"[s]ohn|[s]öhne|[e]hefrau|[e]hemann|[f]reundin|[t]ante|[o]nkel|[s]chwager|"
    r"[s]chwägerin|[s]chwieger\w+|[s]ister|[b]rother|[m]other|[f]ather|[d]aughter|[s]on|"
    r"[w]ife|[h]usband|[g]irlfriend|[b]oyfriend|[a]unt|[u]ncle|[i]n-law)"
    r"(?:s|n|en|e|'s)?\b", re.IGNORECASE)


def test_no_relative_appears_in_the_code():
    """"Eltern" fehlt mit Absicht: im Code ist es die Oberkategorie."""
    funde = [f"{datei}: {m.group(0)!r}" for datei, text in _texte().items()
             for m in _VERWANDTE.finditer(text)]
    assert not funde, "Verwandte:\n  " + "\n  ".join(funde[:30])
