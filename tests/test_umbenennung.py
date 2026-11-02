"""Umbenennungsprobe: jedes Konto, jedes Objekt, jeden Kredit und jedes Ziel umbenennen --
alle Zahlen bleiben gleich.

Warum. Die Neufassung (`docs/Neufassung_plan.md`) will, dass Prognose und
Planung nur Rollen kennen, nie eine bestimmte Bank, ein bestimmtes Objekt, einen
bestimmten Kredit. Ob das stimmt, laesst sich nicht durch Lesen des Codes
feststellen, sondern nur dadurch, dass man den Haushalt umbenennt und
nachsieht, ob sich etwas bewegt: Wo der Code einen Einzelfall kennt, passt
ihm danach eine Kennung nicht mehr.

Wie. In einer Kopie von `config/` und den Auszuegen bekommt jedes Konto, jedes
Objekt, jeder Kredit und jedes Ziel eine neue Kennung und einen neuen Anzeigenamen; Ordner
der Auszuege heissen entsprechend. Neu gebaut wird wie bei `tests/referenz.py`, verglichen
wird die ZAHLENEBENE der Seiten und eine Zusammenfassung des Hauptbuchs ohne
Namen. Die neuen Namen enthalten keine Ziffern, damit sie keine Zahl auf einer Seite
verschieben, und sie behalten die Reihenfolge der alten. Verglichen wird trotzdem
ohne Reihenfolge: Eine Liste, die nach Kennung sortiert ist und neben
Eintraegen steht, die nicht umbenannt wurden, ordnet sich nach dem Umbenennen
anders -- das ist keine Zahl, die sich bewegt.

Die Kennungen werden in den YAML-Dateien ersetzt, wo ein Wert GENAU eine
Kennung ist (oder ein Schluessel); Text, der eine Kennung nur enthaelt, bleibt.
Ein Hash einer Buchung enthaelt das Konto und wird deshalb neu berechnet -- sonst
verlieren die Handentscheidungen ihre Buchung.

Was die Probe findet, steht in `BEKANNT`. Die Eintraege werden weniger.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent))
import referenz

from finctl.forecast.notgroschen import PUFFER_ZIEL
from finctl.ingest.importer import dedup_hash

QUELLE = Path(os.environ["FINCTL_TEST_QUELLE"])

#: Schluessel, deren Wert eine Art benennt, nicht ein Einzelnes: Ein Konto
#: mit der Kennung `giro` hat trotzdem die Kontoart `giro`.
ARTEN = {"account_type", "parser_profile", "ingest_mode", "status", "role", "institution",
         "kind", "typ", "art"}

#: Schluessel, unter denen eine Art ODER eine Kennung stehen kann (die Basis
#: eines Ziels: "alle Depots" oder "dieses Konto"). Ein Wort, das beides ist,
#: heisst hier die Art -- sonst waere `tagesgeld` plotzlich ein Konto.
ART_ODER_KENNUNG = {"basis"}

#: Nicht umgeschrieben: Server und Liste verbotener Namen kennen keine Kennung.
UEBERSPRINGEN = {"server.yaml", "verbotene_namen.yaml"}


def _laden(pfad: Path):
    if not pfad.exists():
        return {}
    return yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}


def _kennungen(config: Path) -> dict[str, dict[str, str]]:
    """Was umbenannt wird: je Sorte {alt: Anzeigename (oder Kennung)}.

    Kennungen und Anzeigenamen stehen in den Dateien der Sache (`accounts.yaml`,
    `properties.yaml`, `loans.yaml`, `goals.yaml`). Der Notgroschen heisst fest
    (`PUFFER_ZIEL`): Er ist der Posten, den die Prognose kennt, und bleibt, wie er ist.
    """
    sorten: dict[str, dict[str, str]] = {"konto": {}, "objekt": {}, "kredit": {}, "ziel": {}}
    felder = (("konto", "accounts", ("accounts.yaml",), "display_name"),
              ("objekt", "properties", ("properties.yaml",), "name"),
              ("kredit", "loans", ("loans.yaml",), "name"),
              ("ziel", "ziele", ("goals.yaml",), "name"))
    for sorte, wurzel, dateien, namensfeld in felder:
        for datei in dateien:
            for eintrag in _laden(config / datei).get(wurzel) or []:
                if isinstance(eintrag, dict) and eintrag.get("id") is not None:
                    if sorte == "ziel" and str(eintrag["id"]) == PUFFER_ZIEL:
                        continue
                    sorten[sorte][str(eintrag["id"])] = str(eintrag.get(namensfeld) or "")
    return sorten


def _buchstaben(n: int) -> str:
    """0 -> aa, 1 -> ab ... in fester Breite, also monoton."""
    return chr(97 + n // 26 % 26) + chr(97 + n % 26)


def abbildung(config: Path) -> dict[str, str]:
    """alt -> neu fuer die Kennungen.

    Die Rangfolge richtet sich nach dem Alten, damit eine nach Kennung
    sortierte Liste ihre Reihenfolge behaelt.
    """
    aus: dict[str, str] = {}
    for sorte, eintraege in _kennungen(config).items():
        for rang, alt in enumerate(sorted(eintraege)):
            aus[alt] = f"{sorte}-{_buchstaben(rang)}"
    return aus


def namen_abbildung(config: Path) -> dict[str, str]:
    """alt -> neu fuer die Anzeigenamen -- nur dort umgeschrieben, wo sie
    definiert sind. Ein Muster in einer Regel, das zufaellig wie ein Name
    aussieht, ist Text einer Buchung und bleibt."""
    aus: dict[str, str] = {}
    for sorte, eintraege in _kennungen(config).items():
        for rang, alt in enumerate(sorted({n for n in eintraege.values() if n})):
            aus[alt] = f"{sorte.capitalize()} {_buchstaben(rang).upper()}"
    return aus


def ordner_abbildung(config: Path, karte: dict[str, str]) -> dict[str, str]:
    """Ordner der Auszuege: der der Kennung folgt, oder ein eigener Name.

    Ein Konto ohne `statement_folder` hat den Ordner seiner Kennung.
    """
    aus: dict[str, str] = {}
    for eintrag in _laden(config / "accounts.yaml").get("accounts") or []:
        ordner = eintrag.get("statement_folder") or eintrag["id"]
        neu = karte[eintrag["id"]]
        aus[ordner] = neu if ordner == eintrag["id"] else f"ordner-{neu}"
    return aus


def _arten() -> set[str]:
    """Die Wörter, die der Code als Bestandsart kennt (`finctl.forecast.ziele`)."""
    from finctl.forecast import ziele

    return {str(a).lower() for a in (*ziele.BASIS_LABEL, *ziele.TOPF, *ziele.LIQUID_KINDS)}


def _schluessel(k, karte: dict[str, str]):
    """Ein Schluessel ist eine Kennung -- oder irgendein Name, der stehen bleibt.

    (Bis N.3f legte das Dashboard Einstellungen als `vorsilbe:kennung` ab, etwa
    `floor_cents:<konto>`; die Untergrenze steht jetzt am Konto in `forecast.yaml`.)
    """
    return karte.get(k, k) if isinstance(k, str) else k


def _ersetzen(wert, karte: dict[str, str], arten: set[str], schluessel: str | None = None):
    """Rekursiv: ein String, der genau eine Kennung ist, wird ersetzt."""
    if isinstance(wert, dict):
        return {_schluessel(k, karte): _ersetzen(v, karte, arten, k) for k, v in wert.items()}
    if isinstance(wert, list):
        return [_ersetzen(v, karte, arten, schluessel) for v in wert]
    if isinstance(wert, str) and schluessel not in ARTEN:
        if schluessel in ART_ODER_KENNUNG and wert.lower() in arten:
            return wert
        return karte.get(wert, wert)
    return wert


#: Die Schluessel, unter denen ein Anzeigename definiert wird, und der Ordner
#: der Auszuege. Nur dort wird ein Wert ersetzt, der kein Verweis ist.
NAMENSFELDER = {"display_name", "name"}


def _felder_ersetzen(wert, ordner: dict[str, str], namen: dict[str, str]):
    if isinstance(wert, dict):
        aus = {}
        for k, v in wert.items():
            if isinstance(v, str) and k == "statement_folder":
                v = ordner.get(v, v)
            elif isinstance(v, str) and k in NAMENSFELDER:
                v = namen.get(v, v)
            else:
                v = _felder_ersetzen(v, ordner, namen)
            aus[k] = v
        return aus
    if isinstance(wert, list):
        return [_felder_ersetzen(v, ordner, namen) for v in wert]
    return wert


def umbenannt_anlegen(quelle: Path, ziel: Path, karte: dict[str, str],
                      hashes: dict[str, str]) -> None:
    """Kopie von `config/` und den Auszuegen, alles umbenannt."""
    (ziel / "config").mkdir(parents=True)
    alle = {**karte, **hashes}
    ordner = ordner_abbildung(quelle / "config", karte)
    namen = namen_abbildung(quelle / "config")
    arten = _arten()
    for datei in sorted((quelle / "config").glob("*.yaml")):
        if datei.name in UEBERSPRINGEN:
            (ziel / "config" / datei.name).write_bytes(datei.read_bytes())
            continue
        inhalt = yaml.safe_load(datei.read_text(encoding="utf-8"))
        neu = _felder_ersetzen(_ersetzen(inhalt, alle, arten), ordner, namen)
        (ziel / "config" / datei.name).write_text(
            yaml.safe_dump(neu, allow_unicode=True, sort_keys=False, width=10**9),
            encoding="utf-8")
    statements = quelle / "data" / "statements"
    (ziel / "data" / "statements").mkdir(parents=True)
    for vorhanden in sorted(p for p in statements.iterdir() if p.is_dir()):
        neuer_name = ordner.get(vorhanden.name, vorhanden.name)
        shutil.copytree(vorhanden, ziel / "data" / "statements" / neuer_name,
                        ignore=shutil.ignore_patterns(".DS_Store"))


def neue_hashes(alt: Path, karte: dict[str, str]) -> dict[str, str]:
    """Der Hash einer Buchung enthaelt ihr Konto: alt -> neu.

    Nachgerechnet, wo es geht. Bei einigen Buchungen (ein Dutzend unter
    Tausenden) stimmt die Rechnung mit den gespeicherten Spalten nicht ueberein:
    der Hash wurde aus dem Text VOR einer Aufbereitung gebildet. Fuer sie
    gibt `hashes_aus_bauten` die Antwort, nachdem einmal gebaut wurde.
    """
    zeilen = json.loads((alt / "hauptbuch" / "transactions.json").read_text(encoding="utf-8"))
    aus: dict[str, str] = {}
    for z in zeilen:
        buchung = SimpleNamespace(booking_date=z["booking_date"], amount_cents=z["amount_cents"],
                                  counterparty=z["counterparty"], purpose=z["purpose"])
        if dedup_hash(z["account_id"], buchung, z["occurrence_index"]) == z["dedup_hash"]:
            aus[z["dedup_hash"]] = dedup_hash(karte.get(z["account_id"], z["account_id"]), buchung,
                                              z["occurrence_index"])
    return aus


def hashes_aus_bauten(alt: Path, neu: Path) -> dict[str, str]:
    """alt -> neu ueber den Platz der Buchung im Auszug, der sich nicht aendert."""
    def je_platz(ordner: Path) -> dict[tuple, str]:
        datei = ordner / "hauptbuch" / "transactions.json"
        zeilen = json.loads(datei.read_text(encoding="utf-8"))
        return {(z["statement_id"], z["seq_in_statement"]): z["dedup_hash"] for z in zeilen}

    a, n = je_platz(alt), je_platz(neu)
    return {a[platz]: n[platz] for platz in a if platz in n}


def _zahlen_der_tabellen(ordner: Path) -> dict[str, list]:
    """Das Hauptbuch ohne Namen: je Tabelle die Zahlen jeder Zeile, sortiert."""
    aus = {}
    for datei in sorted((ordner / "hauptbuch").glob("*.json")):
        zeilen = json.loads(datei.read_text(encoding="utf-8"))
        aus[datei.stem] = sorted(
            [str(v) for _, v in sorted(z.items()) if isinstance(v, int | float)]
            for z in zeilen)
    return aus


def _abgebildet(name: str, karte: dict[str, str]) -> str:
    """Der Dateiname einer Seite mit Pfadparameter (`immobilie__<kennung>.txt`)."""
    kopf, trenner, ende = name[:-4].partition("__")
    return f"{kopf}{trenner}{karte.get(ende, ende)}.txt"


def vergleichen(alt: Path, neu: Path, karte: dict[str, str]) -> list[str]:
    """Was sich beim Umbenennen bewegt hat. Leer, wenn nichts.

    `karte` hat Kennungen und Anzeigenamen.
    """
    funde: list[str] = []
    # Eine Kennung wie `001` sieht auf einer Seite aus wie eine Zahl.
    kennungen = {k for k in karte if k[:1].isdigit()}
    # Ein Name wie "Kredit 2026" traegt eine Zahl, die nur Beschriftung ist.
    mit_ziffern = sorted((k for k in karte if any(c.isdigit() for c in k) and len(k) > 4
                          and k not in kennungen), key=len, reverse=True)
    zahlen_neu = _zahlen_der_tabellen(neu)
    for tabelle, zeilen in _zahlen_der_tabellen(alt).items():
        if zeilen != zahlen_neu.get(tabelle):
            funde.append(f"hauptbuch/{tabelle}: Zahlen weichen ab")
    for pfad in sorted((alt / "seiten").glob("*.txt")):
        gegen = neu / "seiten" / _abgebildet(pfad.name, karte)
        if not gegen.exists():
            funde.append(f"seiten/{pfad.name}: fehlt nach dem Umbenennen ({gegen.name})")
            continue
        alter_text = pfad.read_text(encoding="utf-8")
        for name in mit_ziffern:
            alter_text = alter_text.replace(name, "")
        za = Counter(referenz.zahlen(alter_text.splitlines(), kennungen))
        zn = Counter(referenz.zahlen(gegen.read_text(encoding="utf-8").splitlines(), kennungen))
        if za != zn:
            fehlt, neu_da = sorted((za - zn).elements()), sorted((zn - za).elements())
            funde.append(f"seiten/{pfad.name}: {len(fehlt)} Zahlenzeilen fehlen, "
                         f"{len(neu_da)} sind neu\n    fehlt: {fehlt[:6]}\n    neu:   {neu_da[:6]}")
    return funde


# ------------------------------------------------------------------ im Code

#: Wo die Probe von oben nicht hinkommt: ein Befehl der Kommandozeile, ein
#: Rueckfall, den nur eine Einrichtung ohne Rollen erreicht, ein Platzhalter im
#: Formular. Sie stehen im Code als Zeichenkette -- das ist es, was `finctl/`
#: nicht enthalten darf.
#:
#: Ausgenommen ist `finctl/ingest/`: Ein Leser fuer die Auszuege einer Bank
#: heisst nach der Bank, und ein Konto, das nach seiner Bank heisst, trifft
#: ihn zwangslaeufig (Schritt 8 des Plans). Ausgenommen sind ausserdem Kennungen,
#: die zugleich eine Bestandsart sind (`giro`) oder nur aus Ziffern bestehen.
IM_CODE_AUSSER = ("ingest",)

#: Fundstellen, die es noch gibt: Datei -> Zahl der Treffer. Ohne die Kennung
#: selbst, die steht in `config/` und nirgends sonst. Die Liste wird kuerzer,
#: nie laenger -- auf echten Daten ist sie auch eine Untergrenze: eine Stelle,
#: die nicht mehr vorkommt, wird gestrichen.
BEKANNT: dict[str, int] = {}


def kennungen_im_code(config: Path, wurzel: Path | None = None) -> Counter:
    """Wie oft eine Kennung je Datei im Code steht.

    `wurzel` ist fuer den Test der Suche selbst: Er legt seine Probe in einen
    eigenen Ordner. Eine Probe im echten `finctl/` sahen parallel laufende Tests,
    die den Quellbaum lesen, und fielen zufaellig aus.
    """
    import re

    arten = _arten()
    ids = {k for k in abbildung(config) if k not in arten and not k[:1].isdigit()}
    funde: Counter = Counter()
    if not ids:
        return funde
    alternativen = "|".join(re.escape(i) for i in sorted(ids, key=len, reverse=True))
    zeichenkette = re.compile(r"""["'](""" + alternativen + r""")["']""")
    wort = re.compile(r"(?<![\w-])(" + alternativen + r")(?![\w-])")
    wurzel = wurzel or Path(__file__).resolve().parent.parent / "finctl"
    for datei in sorted(wurzel.rglob("*")):
        rel = datei.relative_to(wurzel)
        if rel.parts[0] in IM_CODE_AUSSER or "__pycache__" in rel.parts:
            continue
        muster = {".py": zeichenkette, ".sql": zeichenkette, ".html": wort}.get(datei.suffix)
        if muster:
            n = len(muster.findall(datei.read_text(encoding="utf-8")))
            if n:
                funde[f"finctl/{rel.as_posix()}"] = n
    return funde


def test_keine_kennung_im_code():
    """Keine Kennung eines Kontos, Objekts, Kredits oder Ziels steht als Text im Code."""
    funde = kennungen_im_code(QUELLE / "config")
    neu = {d: n for d, n in funde.items() if n > BEKANNT.get(d, 0)}
    assert not neu, ("Eine Kennung aus config/ steht im Code -- dort darf nur eine Rolle "
                     "stehen:\n" + "\n".join(f"  {d}: {n}x" for d, n in sorted(neu.items())))
    if os.environ.get("FINCTL_TESTDATEN") != "muster":
        weg = {d: n for d, n in BEKANNT.items() if funde.get(d, 0) < n}
        zeilen = "\n".join(f"  {d}: {n}x" for d, n in sorted(weg.items()))
        assert not weg, ("Diese Stellen sind behoben und gehoeren aus BEKANNT gestrichen "
                         f"oder gekuerzt:\n{zeilen}")


def test_die_probe_findet_eine_kennung_im_code(tmp_path):
    """Der Befund selbst: ohne diesen Test koennte die Suche leer laufen."""
    config = tmp_path / "config"
    config.mkdir()
    (config / "accounts.yaml").write_text(
        "accounts:\n  - {id: bank-xy, display_name: Konto Xy}\n", encoding="utf-8")
    wurzel = tmp_path / "finctl"
    wurzel.mkdir()
    (wurzel / "_probe_kennung.py").write_text('KONTO = "bank-xy"\n', encoding="utf-8")
    assert kennungen_im_code(config, wurzel)["finctl/_probe_kennung.py"] == 1


def test_ersetzen_trifft_kennungen_und_laesst_arten_stehen():
    karte = {"giro": "konto-aa", "bank-xy": "konto-ab"}
    arten = {"giro", "depot"}
    inhalt = {"accounts": [{"id": "giro", "account_type": "giro", "sweep_to": "bank-xy"}],
              "account_roles": {"bank-xy": {"floor_cents": 5}},
              "ziele": [{"basis": ["giro", "bank-xy"], "notiz": "giro bank-xy"}]}
    assert _ersetzen(inhalt, karte, arten) == {
        "accounts": [{"id": "konto-aa", "account_type": "giro", "sweep_to": "konto-ab"}],
        "account_roles": {"konto-ab": {"floor_cents": 5}},
        "ziele": [{"basis": ["giro", "konto-ab"], "notiz": "giro bank-xy"}]}


# ------------------------------------------------------------------ die Probe

@pytest.mark.langsam
def test_umbenennen_aendert_keine_zahl(tmp_path):
    """Jedes Konto, Objekt, jeder Kredit und jedes Ziel bekommt einen neuen Namen: Hauptbuch
    und Seiten zeigen dieselben Zahlen."""
    tag = dt.date.today()
    alt = tmp_path / "alt"
    referenz.neu_bauen(QUELLE, tag, alt)

    karte = abbildung(QUELLE / "config")
    assert karte, "Der Haushalt hat nichts, was sich umbenennen liesse"
    quelle2 = tmp_path / "quelle2"
    hashes = neue_hashes(alt, karte)
    umbenannt_anlegen(QUELLE, quelle2, karte, hashes)
    neu = tmp_path / "neu"
    referenz.neu_bauen(quelle2, tag, neu)
    echt = hashes_aus_bauten(alt, neu)
    if any(hashes.get(k) != v for k, v in echt.items()):
        # Einige Hashes liessen sich nicht nachrechnen: mit den echten noch einmal.
        shutil.rmtree(quelle2)
        shutil.rmtree(neu)
        umbenannt_anlegen(QUELLE, quelle2, karte, echt)
        referenz.neu_bauen(quelle2, tag, neu)

    funde = vergleichen(alt, neu, {**karte, **namen_abbildung(QUELLE / "config")})
    assert not funde, ("Nach dem Umbenennen aller Konten, Objekte, Kredite und Ziele:\n\n"
                       + "\n".join(funde[:40]))
