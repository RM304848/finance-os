"""Das Kontenregister -- gelesen, geprueft und geschrieben.

`config/accounts.yaml` war die einzige Stammdatei, die es nur im Texteditor
gab. Wer die App neu aufsetzt, kommt ohne Konto aber keinen Schritt weit: kein
Konto, kein Import, kein Hauptbuch, keine Tiefpunktwarnung. Ein Werkzeug, das
vor dem ersten nuetzlichen Bildschirm eine YAML-Datei von Hand verlangt, hat
an genau dieser Stelle seine Nutzer verloren.

EINE DATEI: `accounts.yaml` traegt die Konten und die Notiz zu jedem -- warum PayPal ein
Konto ist und kein Haendler, warum ein Konto nicht geparst wird. Die Seite schreibt sie
ganz (Schritt 5, N.3e; vorher stand, was sie anlegte, in einer zweiten Datei, damit die
Kommentare den Klick ueberstanden).

DER UPSERT STEHT HIER, NICHT IN `cli.init`. Beide Wege -- die Seite /konten
und `finctl init` -- schreiben dasselbe Konto in dieselbe Tabelle. Zweimal
geschrieben hiesse: der Editor kennt ein Feld, das `init` beim naechsten Lauf
wieder ueberbuegelt.

WO DIE AUSZUEGE LIEGEN, ist eine Entscheidung mit zwei Seiten. Ein
ORDNERNAME (`sparkasse`) liegt unter `data/statements/` -- im Datenordner,
also im Backup und beim Umzug dabei. Ein VOLLER PFAD (`/Users/…/Downloads`)
ist bequemer, wird aber nicht mitgesichert und zeigt auf einem anderen
Rechner ins Leere. Deshalb ist der Ordnername der Normalfall und der volle
Pfad die Ausnahme, die die Seite benennt.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from finctl import notizen as _notizen
from finctl.dateien import yaml_lesen, yaml_schreiben
from finctl.pfade import CONFIG_DIR, STATEMENTS_DIR

DATEI = "accounts.yaml"

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")

#: Namen, die Windows nicht als Ordner zulaesst. Die Kennung ist der Standardname des
#: Auszugsordners, und ein Konto "con" liesse sich dort weder anlegen noch einlesen.
_WINDOWS_GERAETE = frozenset({"con", "prn", "aux", "nul",
                              *(f"com{i}" for i in range(1, 10)),
                              *(f"lpt{i}" for i in range(1, 10))})

#: Was ein Konto ist. `loan` ist ein Kredit, der als Konto gefuehrt wird.
ARTEN = ("giro", "tagesgeld", "depot", "broker", "credit_card", "loan")

#: `parsed` liest Auszuege Buchung fuer Buchung. `summary` tut das nicht --
#: so ein Konto wird nur ueber die Umbuchungen sichtbar, die es von einem
#: geparsten Konto erreichen. Ohne Parserprofil bleibt nur `summary`.
MODI = ("parsed", "summary")

#: Was die Seite beim Anlegen eines Kontos annimmt, in der Reihenfolge, in der der Eintrag in
#: der Datei steht. Ein Konto, das es schon gibt, bearbeitet keine Seite: Was die Datei
#: sonst an ihm traegt (die Notiz, ein Feld von Hand), bleibt, wie es ist.
FELDER = ("id", "display_name", "institution", "account_type", "iban",
          "account_no", "currency", "ingest_mode", "parser_profile",
          "statement_folder", "dispo_threshold_cents", "active", "closed_on")


def profile() -> list[str]:
    """Die Parserprofile, die es gibt -- aus dem Ordner, nicht aus einer Liste.

    Eine gepflegte Liste waere die zweite Stelle, an der ein neues Profil
    eingetragen werden muss, und die, die man vergisst.
    """
    import importlib
    import pkgutil

    from finctl.ingest import profiles

    namen = []
    # Ueber das Paket, nicht ueber `*.py` im Ordner: in der App zum
    # Doppelklicken liegen die Module in einem Archiv, und ein Ordner voller
    # .py-Dateien existiert dort nicht -- die Auswahl der Profile war leer.
    for info in pkgutil.iter_modules(profiles.__path__):
        if info.name.startswith("_"):
            continue
        # Eine Sammlung beschriebener Exporte (banken_csv) bietet ihre
        # Eintraege an, nicht sich selbst.
        modul = importlib.import_module(f"finctl.ingest.profiles.{info.name}")
        namen += list(getattr(modul, "PARSERS", {})) or [info.name]
    # Und die selbst beschriebenen Exporte aus config/.
    from finctl.ingest import zuordnung

    return sorted(namen) + sorted(zuordnung.eigene())


# ------------------------------------------------------------------ lesen

def _yaml(pfad: Path) -> dict:
    if not pfad.exists():
        return {}
    gelesen = yaml_lesen(pfad)
    return gelesen if isinstance(gelesen, dict) else {}


def aus_spec(spec: dict) -> list[dict]:
    """Die Konten einer Datei, je Kennung eines (steht eine zweimal, gilt die letzte)."""
    konten: dict[str, dict] = {}
    for eintrag in spec.get("accounts") or []:
        konten[str(eintrag["id"])] = dict(eintrag)
    return list(konten.values())


def laden(config_dir: Path | None = None) -> list[dict]:
    """Die Konten aus `accounts.yaml`."""
    return aus_spec(_yaml((config_dir or CONFIG_DIR) / DATEI))


def auszugsordner(konto: dict, daten: Path | None = None) -> Path:
    """Wohin die Auszuege dieses Kontos gehoeren.

    Ein Ordnername wird unter `data/statements/` gelegt, ein voller Pfad
    genommen, wie er ist.
    """
    angabe = str(konto.get("statement_folder") or konto["id"]).strip()
    p = Path(angabe).expanduser()
    return p if p.is_absolute() else (daten or STATEMENTS_DIR) / p


def eigener_pfad(konto: dict) -> bool:
    """Liegt der Ordner ausserhalb des Datenordners -- also ohne Backup?"""
    angabe = str(konto.get("statement_folder") or "").strip()
    return bool(angabe) and Path(angabe).expanduser().is_absolute()


# ------------------------------------------------------------------ pruefen

def _kennung_fehler(kennung: str, vergeben: set[str]) -> str | None:
    if kennung in _notizen.RESERVIERT:
        return f"Kennung „{kennung}“ ist für Notizen reserviert"
    if not _ID.match(kennung):
        return "Kennung: klein, Ziffern und Bindestriche, höchstens 41 Zeichen"
    if kennung in _WINDOWS_GERAETE:
        return f"Kennung „{kennung}“ ist unter Windows kein Ordnername"
    if kennung in vergeben:
        return f"Kennung „{kennung}“ ist schon vergeben"
    return None


def pruefen(konto: dict, vergeben: set[str], *, neu: bool = True) -> list[str]:
    """Was an diesem Konto nicht stimmt, in Worten. Leer heisst: in Ordnung.

    Die Kennung prueft nur ein neues Konto: Ein bestehendes behaelt sie, auch wenn eine
    fruehere Fassung sie weiter schrieb, als sie heute erlaubt ist.
    """
    fehler = []
    kennung = str(konto.get("id") or "").strip()
    if neu and (grund := _kennung_fehler(kennung, vergeben)):
        fehler.append(grund)
    if not str(konto.get("display_name") or "").strip():
        fehler.append("Anzeigename fehlt")
    if not str(konto.get("institution") or "").strip():
        fehler.append("Institut fehlt")
    if konto.get("account_type") not in ARTEN:
        fehler.append(f"Art: eine von {', '.join(ARTEN)}")
    if konto.get("ingest_mode") not in MODI:
        fehler.append(f"Einlesen: {' oder '.join(MODI)}")
    elif konto["ingest_mode"] == "parsed" and konto.get("parser_profile") not in profile():
        # Ohne Profil weiss der Import nicht, wie er die Datei lesen soll --
        # das Konto saehe eingerichtet aus und bliebe beim Import stumm.
        fehler.append("Ein geparstes Konto braucht ein Parserprofil")
    schwelle = konto.get("dispo_threshold_cents")
    if schwelle is not None and (not isinstance(schwelle, int) or schwelle < 0):
        fehler.append("Schwelle für die Warnung: nicht negativ")
    return fehler


# ------------------------------------------------------------------ schreiben

_SQL = """
    INSERT INTO accounts
        (id, display_name, institution, account_type, iban, account_no,
         currency, ingest_mode, parser_profile, statement_folder,
         dispo_threshold_cents, active, closed_on)
    VALUES
        (:id, :display_name, :institution, :account_type, :iban, :account_no,
         :currency, :ingest_mode, :parser_profile, :statement_folder,
         :dispo_threshold_cents, :active, :closed_on)
    ON CONFLICT(id) DO UPDATE SET
        display_name = excluded.display_name,
        institution  = excluded.institution,
        account_type = excluded.account_type,
        iban         = excluded.iban,
        account_no   = excluded.account_no,
        ingest_mode  = excluded.ingest_mode,
        parser_profile = excluded.parser_profile,
        statement_folder = excluded.statement_folder,
        dispo_threshold_cents = excluded.dispo_threshold_cents,
        active       = excluded.active,
        closed_on    = excluded.closed_on
"""


def als_zeile(konto: dict) -> dict:
    """Ein Registereintrag als Zeile der Tabelle `accounts`."""
    return {
        "id": konto["id"],
        "display_name": konto["display_name"],
        "institution": konto["institution"],
        "account_type": konto["account_type"],
        "iban": konto.get("iban"),
        "account_no": konto.get("account_no"),
        "currency": konto.get("currency", "EUR"),
        "ingest_mode": konto["ingest_mode"],
        "parser_profile": konto.get("parser_profile"),
        "statement_folder": konto.get("statement_folder"),
        "dispo_threshold_cents": konto.get("dispo_threshold_cents"),
        # Geschlossen bleibt in der Historie, faellt aber aus jeder Auswahl.
        # Vorher setzte init jedes Konto auf aktiv, und laengst gekuendigte
        # Konten standen Jahre spaeter noch in der Kontenliste.
        "active": 0 if konto.get("active") is False or konto.get("closed_on") else 1,
        "closed_on": str(konto["closed_on"]) if konto.get("closed_on") else None,
    }


def in_db(conn: sqlite3.Connection, konto: dict) -> int:
    """Ein Konto in die Tabelle schreiben oder auffrischen."""
    return conn.execute(_SQL, als_zeile(konto)).rowcount or 0


def anlegen(conn: sqlite3.Connection, konto: dict,
            config_dir: Path | None = None,
            statements: Path | None = None) -> dict:
    """Ein neues Konto: erst in die Datei, dann in die Tabelle.

    In dieser Reihenfolge, weil die Datei die Handentscheidung traegt und die
    Tabelle daraus jederzeit neu gebaut werden kann -- umgekehrt nicht.
    """
    config_dir = config_dir or CONFIG_DIR
    fehler = pruefen(konto, {str(k["id"]) for k in laden(config_dir)})
    if fehler:
        raise ValueError("; ".join(fehler))

    schlank = {f: konto[f] for f in FELDER if konto.get(f) not in (None, "")}
    pfad = config_dir / DATEI
    pfad.parent.mkdir(parents=True, exist_ok=True)
    spec = _yaml(pfad)
    if not isinstance(spec.get("accounts"), list):
        spec["accounts"] = []
    spec["accounts"].append(schlank)
    yaml_schreiben(pfad, spec)

    in_db(conn, schlank)
    conn.commit()
    # Der Ordner wird gleich angelegt: ein Konto, dessen Ablage erst beim
    # ersten Import entsteht, laesst den Nutzer raten, wohin die Datei soll.
    auszugsordner(schlank, statements).mkdir(parents=True, exist_ok=True)
    return schlank


#: Die Angaben, die die Seite an einem bestehenden Konto aendert, mit der Art, wie sie
#: gelesen werden: Text, Betrag in Cent oder Tag.
AENDERBAR = {"display_name": "text", "institution": "text", "account_type": "text",
             "ingest_mode": "text", "parser_profile": "text", "statement_folder": "text",
             "dispo_threshold_cents": "cents", "closed_on": "tag"}


def _schliessen(eintrag: dict, tag: str) -> None:
    """Den Tag, an dem das Konto geschlossen wurde, setzen oder, leer, es wieder oeffnen."""
    eintrag.pop("active", None)
    if tag:
        eintrag["closed_on"] = tag
    else:
        eintrag.pop("closed_on", None)


def _felder_uebernehmen(eintrag: dict, felder: dict) -> None:
    """Was die Seite schickt, in den Eintrag; was schon so gilt, bleibt unberuehrt."""
    for feld, art in AENDERBAR.items():
        if feld not in felder:
            continue
        wert = felder[feld]
        if feld == "closed_on":
            # Die Seite zeigt den Tag; ohne ihn (auch bei `active: false`) bleibt es, wie es ist.
            if str(wert or "").strip() != str(eintrag.get(feld) or "").strip():
                _schliessen(eintrag, str(wert or "").strip())
            continue
        if art == "cents":
            wert = None if wert in (None, "") else int(wert)
        else:
            wert = str(wert or "").strip()
        if wert in (None, ""):
            eintrag.pop(feld, None)
        elif wert != eintrag.get(feld):
            eintrag[feld] = wert


def aendern(conn: sqlite3.Connection, kennung: str, felder: dict,
            config_dir: Path | None = None, statements: Path | None = None) -> dict:
    """Die Angaben eines bestehenden Kontos aendern; die Kennung bleibt.

    Gilt, was die Seite schickt, schon so, schreibt sie nichts: auch nicht, wo die Datei
    `active: false` fuehrt und die Seite kein Schliessdatum zeigt. Die Datei traegt die
    Entscheidung, die Tabelle wird daraus nachgefuehrt, damit die Anzeige sofort stimmt.
    `felder` darf `notiz` tragen. Gibt den Eintrag zurueck, wie er jetzt in der Datei steht.
    """
    config_dir = config_dir or CONFIG_DIR
    pfad = config_dir / DATEI
    spec = _yaml(pfad)
    eintrag = next((k for k in spec.get("accounts") or []
                    if isinstance(k, dict) and str(k.get("id")) == kennung), None)
    if eintrag is None:
        raise ValueError(f"Kein Konto „{kennung}“")
    vorher = {**eintrag}
    _felder_uebernehmen(eintrag, felder)
    if "closed_on" in eintrag and _tag_text(eintrag["closed_on"]) is None:
        raise ValueError("Geschlossen am: JJJJ-MM-TT, oder leer")
    if fehler := pruefen(eintrag, set(), neu=False):
        raise ValueError("; ".join(fehler))
    if "notiz" in felder:
        _notizen.setzen(eintrag, _notizen.eingabe(felder["notiz"]))
    if eintrag == vorher:
        return eintrag
    yaml_schreiben(pfad, spec)
    in_db(conn, eintrag)
    conn.commit()
    auszugsordner(eintrag, statements).mkdir(parents=True, exist_ok=True)
    return eintrag


def _tag_text(wert) -> str | None:
    from datetime import date

    try:
        return date.fromisoformat(str(wert)[:10]).isoformat()
    except ValueError:
        return None
