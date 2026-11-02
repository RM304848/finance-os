"""Die Regeln zwischen den Konten -- an einer Stelle gelesen und geschrieben.

Untergrenze, Deckel, Abraeumen, Auffuellen, Dauerauftrag, Rolle und Zweck
standen in `config/forecast.yaml` und waren bis auf die Untergrenze nur im
Texteditor aenderbar. Sie bewegen jede Zahl auf /konten: ob ein Konto
aufgefuellt wird, ob Geld aufs Tagesgeld geht, wo der Tiefpunkt liegt. Genau
deshalb stand auf der Seite ein Absatz, der erklaerte, was Zufluss und Deckel
bedeuten -- Prosa als Ersatz fuer Felder, die es nicht gab.

Sie sind keine Prognoseannahme. Eine Annahme sagt, wie die Welt sich
entwickelt (Inflation, Rendite, Gehalt); eine Kontenregel sagt, wie DU dein
Geld zwischen deinen eigenen Konten verschiebst. Deshalb stehen sie auf der
Kontenseite und nicht bei den Annahmen.

EINE DATEI, `config/forecast.yaml`. Die Seite schreibt den ganzen Eintrag des Kontos dorthin;
die Begruendung dazu steht als Notiz im selben Eintrag (`finctl/notizen.py`) und uebersteht
das Schreiben. Bis Schritt 5 stand, was die Seite setzte, in einer zweiten Datei;
`finctl umstellen` hat beide zusammengelegt.
"""

from __future__ import annotations

from finctl import notizen as _notizen
from finctl.dateien import yaml_lesen, yaml_schreiben
from finctl.pfade import CONFIG_DIR

DATEI = "forecast.yaml"

#: Was eine Kontenregel ausmacht, und wie der Wert gelesen wird.
FELDER: dict[str, str] = {
    "role": "text",
    "note": "text",
    "floor_cents": "cents",
    "ceiling_cents": "cents",
    "sweep_to": "text",
    "auffuellen": "schalter",
    "floor_from_loan": "kredit",
}


#: Unter welchem Namen die Seite die Notiz einer Regel noch liest und schreibt (`note`);
#: gespeichert wird `notiz`. Die Beschriftungen aendert Schritt 6.
NOTIZ_ZEILE = ("note",)

#: Was gilt, wenn die Datei zu einem Schalter nichts sagt. Ohne diese Standards
#: schriebe jedes Speichern ein "auffuellen: true" in die Datei, obwohl sich nichts
#: geaendert hat.
STANDARD: dict[str, object] = {"auffuellen": True}


def _spec() -> dict:
    pfad = CONFIG_DIR / DATEI
    return (yaml_lesen(pfad) or {}) if pfad.exists() else {}


def aus_spec(spec: dict) -> dict:
    """Die Kontenregeln einer geladenen `forecast.yaml`: Rollen mit Notiz, Budgets, der Rest.

    In einer Zuordnung, deren Schluessel Konten sind, ist `notiz` keins (`notizen.ohne`).
    Die Notiz steht in der Zeile, die die Seite liest, auch unter dem Namen `note`.
    """
    rollen = {k: dict(v or {}) for k, v in _notizen.ohne(spec.get("account_roles")).items()}
    for rolle in rollen.values():
        _notizen.in_zeile(rolle, _notizen.lesen(rolle), NOTIZ_ZEILE)
    return {**spec, "account_roles": rollen,
            "account_budgets": dict(_notizen.ohne(spec.get("account_budgets")))}


def wirksam() -> dict:
    """Die geltende Kontenkonfiguration: `forecast.yaml`, gelesen."""
    return aus_spec(_spec())


def _text_gleich(wert, bisher) -> bool:
    """Text wird ohne Rand verglichen: ein Formular endet nicht auf einem Zeilenumbruch."""
    return str(wert or "").strip() == str(bisher or "").strip()


def _feld_setzen(eintrag: dict, feld: str, wert) -> None:
    """Ein Feld der Regel setzen. Was schon so gilt, aendert die Datei nicht."""
    art = FELDER[feld]
    if art == "kredit":
        _kredit_setzen(eintrag, feld, wert)
    elif wert is None:
        eintrag.pop(feld, None)
    elif art == "schalter":
        # Der Standard steht nicht in der Datei, solange der Haushalt ihn nicht aendert.
        if feld in eintrag or bool(wert) != STANDARD.get(feld):
            eintrag[feld] = bool(wert)
    elif art == "text":
        if not _text_gleich(wert, eintrag.get(feld)):
            eintrag[feld] = str(wert).strip()
    else:
        eintrag[feld] = wert


def _kredit_setzen(eintrag: dict, feld: str, wert) -> None:
    """`floor_from_loan`: die Kennung eines Kredits. Kein Kredit nimmt das Feld heraus.

    Ein `true` oder `false`, wie fruehere Fassungen es schrieben, bewirkt nichts; die Karte
    zeigt „kein Kredit gewaehlt“ und laesst es stehen, solange niemand einen Kredit waehlt.
    Ein alter Aufruf mit `True` aendert nichts: Eine Kennung bliebe, ein Haken ohne Kredit
    wird nicht mehr geschrieben.
    """
    bisher = eintrag.get(feld)
    if isinstance(wert, str) and wert.strip():
        if bisher != wert.strip():
            eintrag[feld] = wert.strip()
    elif bisher is not None and not isinstance(bisher, bool) and wert is not True:
        del eintrag[feld]


def setzen(konto: str, felder: dict) -> dict:
    """Ein Konto aendern: der ganze Eintrag steht danach in `forecast.yaml`.

    Gibt die wirksame Regel des Kontos zurueck. Speichern ohne Aenderung schreibt nichts
    (`dateien.yaml_schreiben`).
    """
    pfad = CONFIG_DIR / DATEI
    spec = _spec()
    rollen = dict(spec.get("account_roles") or {})
    budgets = dict(spec.get("account_budgets") or {})

    eintrag = dict(rollen.get(konto) or {})
    for feld, wert in felder.items():
        if feld == "budget_cents":
            if wert is None:
                budgets.pop(konto, None)
            else:
                budgets[konto] = int(wert)
        elif feld == "note":
            _notizen.setzen(eintrag, str(wert or ""), alt=NOTIZ_ZEILE)
        elif feld in FELDER:
            _feld_setzen(eintrag, feld, wert)
    # Abraeumen kann nur das Betriebskonto: nur fuer dessen Uebertrag baut die
    # Prognose die Gegenbuchung. Ein Ziel an einem anderen Konto rechnet
    # nichts, stand aber auf /konten als Regel da -- und das gesperrte Feld
    # liess es nicht mehr loeschen.
    if eintrag.get("role") != "operating":
        eintrag.pop("sweep_to", None)
    if eintrag:
        rollen[konto] = eintrag
    else:
        rollen.pop(konto, None)

    neu = {**spec, "account_roles": rollen, "account_budgets": budgets}
    if not rollen and "account_roles" not in spec:
        neu.pop("account_roles")
    if not budgets and "account_budgets" not in spec:
        neu.pop("account_budgets")
    yaml_schreiben(pfad, neu)
    return aus_spec(neu)["account_roles"].get(konto) or {}
