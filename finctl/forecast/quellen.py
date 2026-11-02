"""Woraus Monatsmodell und Jahresrechnung fortschreiben -- je Block eine Zeile.

Die Seite /prognosebasis rechnet nichts. Sie ordnet die Posten, die beide
Rechnungen selbst bilden, in Zeilen: aus dem ersten Monat des Monatsmodells
(`konten.household_accounts`, der Rechenweg `herkunft` jedes Kontos) und aus
dem ersten vollen Jahr der Jahresrechnung (`jahre.Year.posten`). Eine Zeile hat
je Rechnung die Summe ihrer Posten und die Quelle, aus der sie stammen. Wer die
Quelle ansieht, sieht, was die Rechnung gezaehlt hat -- nicht, was eine dritte
Rechnung daneben fuer richtig haelt.

Gleich ist eine Quelle, wenn beide Rechnungen sie mit demselben Text nennen;
dann steht sie einmal da. Verschieden ist sie, wo die Rechnungen verschieden
rechnen (Zinsen) oder verschieden viel kennen (Planzeilen nur fuer die Konten);
dann stehen beide da. Warum, steht nicht hier.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from finctl.forecast import abgleich as ag
from finctl.forecast import jahre as jm
from finctl.forecast import verfahren

#: Die Zeilen der Seite in ihrer Reihenfolge: Einnahmen, dann Ausgaben, dann das,
#: was die Rechnungen selbst rechnen.
GEHALT, MIETE, EINKOMMEN_SONST, ERWARTET = "gehalt", "miete", "einkommen_sonst", "erwartet"
OBJEKTE, FIXKOSTEN, VERTRAEGE, IMMOBILIE = "objekt", "fixkosten", "vertraege", "immobilie"
KONSUM, STEUERN, KREDIT, ZINSEN = "konsum", "steuern", "kredit", "zinsen"
KLAMMERN, INVESTMENT, RENTE = "klammern", "investment", "rente"

REIHENFOLGE = (GEHALT, MIETE, EINKOMMEN_SONST, ERWARTET, OBJEKTE, FIXKOSTEN, VERTRAEGE,
               IMMOBILIE, KONSUM, STEUERN, KREDIT, ZINSEN, KLAMMERN, INVESTMENT, RENTE)

#: Wo der Haushalt die Quelle einer Zeile aendert. Eine gemessene Zeile hat keine eigene
#: Seite: ihre Quelle sind die Buchungen des Messfensters, und geaendert wird, was ihnen
#: zugeordnet ist.
ORT = {
    GEHALT: ("/annahmen", "Annahmen"),
    ERWARTET: ("/planung", "Planung"),
    OBJEKTE: ("/immobilien", "Objekte"),
    VERTRAEGE: ("/vertraege", "Verträge"),
    KREDIT: ("/kredite", "Kredite"),
    ZINSEN: ("/annahmen#zinssaetze", "Annahmen, Zinssätze"),
    KLAMMERN: ("/planung", "Planung"),
    RENTE: ("/renten", "Rentenquellen"),
}

#: Welche Quellen die Posten einer Zeile haben duerfen (`herkunft.QUELLEN`). Ein Posten
#: mit anderer Quelle ist ein Fehler der Zuordnung und kein Fall fuer die Anzeige.
ERLAUBT = {
    GEHALT: {"annahme"}, MIETE: {"gemessen"}, EINKOMMEN_SONST: {"gemessen"},
    ERWARTET: {"plan"}, OBJEKTE: {"annahme"}, FIXKOSTEN: {"gemessen"},
    VERTRAEGE: {"vertrag", "regel"}, IMMOBILIE: {"gemessen"}, KONSUM: {"gemessen"},
    STEUERN: {"gemessen"}, KREDIT: {"vertrag"}, ZINSEN: {"rendite", "regel"},
    KLAMMERN: {"plan"}, INVESTMENT: {"gemessen"}, RENTE: {"regel", "annahme", "gemessen"},
}

#: In der Jahresrechnung stehen diese Bloecke neben der Fortschreibung: was in Policen
#: fliesst, ausgezahlt und verzinst wird und die Kaskade. Sie sind keine Basis.
_KEINE_BASIS = {"rendite", "kaskade", "depotentnahme", "policen", "policen_beitrag"}


class Zuordnung:
    """In welche Zeile ein Posten des Monatsmodells gehoert.

    Der Rechenweg eines Kontos nennt je Etikett seine Herkunft; die Zeile folgt aus dieser
    Herkunft und, wo es nur das Etikett gibt, aus der Kategorie des Etiketts.
    """

    def __init__(self, conn) -> None:
        from finctl import abos as _abos

        self.conn = conn
        self.vertraege = {a["id"]: a["kategorie"] for a in _abos.alle_vertraege()}
        self.zeilen = {s.id: s for s in jm._szenarien_laden()}
        self._bloecke: dict[str, str | None] = {}

    def block_der_kategorie(self, kategorie: str) -> str | None:
        if kategorie not in self._bloecke:
            self._bloecke[kategorie] = ag.block_der_kategorie(self.conn, kategorie)
        return self._bloecke[kategorie]

    def planzeile(self, verweis: str):
        klammer, index = str(verweis).rsplit(":", 1)
        return self.zeilen[klammer].lines[int(index)]

    def erwartet(self, herkunft: dict) -> bool:
        return (herkunft.get("quelle") == "plan"
                and self.planzeile(herkunft["verweis"]).kind == "erwartet")

    def _planposten(self, herkunft: dict) -> str:
        """Eine Planzeile gehoert zu den Klammern, eine erwartete Einnahme zu sich."""
        zeile = self.planzeile(herkunft["verweis"])
        if herkunft.get("kategorie") in jm.GERECHNET:
            return ZINSEN
        return ERWARTET if zeile.kind == "erwartet" else KLAMMERN

    def von(self, label: str, herkunft: dict) -> str | None:
        """Die Zeile eines Postens; `None` fuer Geld zwischen eigenen Konten."""
        if herkunft.get("umbuchung"):
            return None
        if herkunft.get("objekt"):
            return OBJEKTE
        if herkunft.get("quelle") == "plan":
            return self._planposten(herkunft)
        if label.startswith("loan:"):
            return KREDIT
        if label.startswith(("abo-zurueck:", "abo-anteil:", "abo:")):
            return VERTRAEGE
        if label in jm.GERECHNET:
            return ZINSEN
        block = self.block_der_kategorie(label)
        return {"einmalig": KLAMMERN, None: KONSUM}.get(block, block)


@dataclass(frozen=True, slots=True)
class Zeile:
    """Ein Block der Fortschreibung: je Rechnung die Summe und die Quelle.

    `None` heisst: Diese Rechnung kennt den Block nicht (keine Posten) -- etwas anderes als
    eine Summe von null.
    """

    schluessel: str
    name: str
    monat_cents: int | None
    jahr_cents: int | None
    quelle_monat: str | None
    quelle_jahr: str | None
    href: str
    ort: str

    @property
    def gleiche_quelle(self) -> bool:
        return self.quelle_monat == self.quelle_jahr


@dataclass(frozen=True, slots=True)
class Seite:
    #: Der erste Monat der Kontoprognose und das erste volle Jahr der Jahresrechnung.
    monat: date | None
    jahr: int | None
    #: Das Messfenster als Text, `2025-07 bis 2026-06`.
    fenster: str
    zeilen: list[Zeile]


def _name(schluessel: str, bloecke: dict[str, str]) -> str:
    eigene = {ERWARTET: "Erwartete Einnahmen", VERTRAEGE: "Verträge",
              ZINSEN: "Zinsen und Steuer darauf", KLAMMERN: "Planzeilen der Klammern",
              RENTE: "Renten", INVESTMENT: "Investment"}
    text = eigene.get(schluessel) or bloecke.get(schluessel, schluessel)
    return text[:1].upper() + text[1:]


def _verfahren(regel: verfahren.Regel) -> str:
    """Der Name des Verfahrens, wie CONTEXT.md ihn fuehrt: Jüngst oder die Zwölfmonatssumme."""
    return "Jüngst" if regel.fenster == "juengst" else "Zwölfmonatssumme"


def _quelle(schluessel: str, fenster: str, *, monatsmodell: bool, nur_konten: bool) -> str:
    """Wie die Rechnung diese Zeile nennt. Der Text haengt an der Zeile und an der
    Rechnung, nie an einem Betrag."""
    if schluessel == GEHALT:
        return "Untergrenze des Gehalts aus den Annahmen, mit Gehaltssteigerung"
    if schluessel == ERWARTET:
        return "Erwartete Einnahme: Betrag, Takt und Start der Planzeile"
    if schluessel == OBJEKTE:
        return "Objektprognose: Miete und Kosten des Objekts"
    if schluessel == VERTRAEGE:
        return "Vertrag: Betrag je Termin, mit Steigerung"
    if schluessel == KREDIT:
        return "Tilgungsplan des Kredits"
    if schluessel == RENTE:
        return "Rentenquellen"
    if schluessel == ZINSEN:
        return ("Gerechnet: Stand zu Monatsbeginn mal Satz je Konto, Steuer nach Sparerpauschbetrag"
                if monatsmodell else
                "Gerechnet: Stand zu Jahresbeginn mal Satz je Topf, Steuer nach Sparerpauschbetrag")
    if schluessel == KLAMMERN:
        return ("Planzeilen eingeschalteter Klammern, auch die nur für die Kontoprognose"
                if nur_konten and monatsmodell else "Planzeilen eingeschalteter Klammern")
    tabelle = verfahren.KONTOPROGNOSE if monatsmodell else verfahren.HOCHRECHNUNG
    return f"Fortschreibung {fenster}, {_verfahren(tabelle[verfahren.KOSTEN])}"


def _monatsposten(views: list[dict], zuordnung: Zuordnung):
    """Die Posten der Kontoprognose ueber alle Konten und Monate: (Zeile, Betrag, Herkunft,
    erster Monat). Ein Block, der erst im Januar zahlt, gehoert in die Seite, auch wenn der
    erste Monat nichts von ihm hat."""
    for view in views:
        if view.get("error"):
            continue
        for i, row in enumerate(view["rows"]):
            for label, cents in row["detail"].items():
                herkunft = view["herkunft"][label]
                zeile = zuordnung.von(label, herkunft)
                if zeile is not None:
                    yield zeile, cents, herkunft, i == 0


def _zeile_im_jahr(block: str, p, erwartet: set[str]) -> str:
    """Die Zeile eines Postens der Jahresrechnung: sein Block, ausser wo seine Herkunft mehr
    sagt."""
    if p.objekt or block == ag.OBJEKT:
        return OBJEKTE
    if p.verweis in erwartet:
        return ERWARTET
    if str(p.verweis or "").startswith("abo:"):
        return VERTRAEGE
    return KLAMMERN if block == ag.EINMALIG else block


def _jahresposten(lauf: jm.Projection, jahr: int, erwartet: set[str]):
    """Die Posten des Jahres: (Zeile, Betrag, Quelle)."""
    year = next((y for y in lauf.years if y.year == jahr), None)
    if year is None:
        return
    for block, posten in year.posten.items():
        if block in _KEINE_BASIS:
            continue
        for p in posten:
            if not p.umbuchung:
                yield _zeile_im_jahr(block, p, erwartet), p.cents, p.quelle
    # Die Zinsen des Tagesgelds und die Steuer darauf rechnet die Jahresrechnung als Rendite
    # des Topfs; die Renditen von Depot und Policen kennt das Monatsmodell nicht.
    for p in year.posten.get("rendite", []):
        if p.verweis == "tagesgeld":
            yield ZINSEN, p.cents, p.quelle


def erwartete_zeilen() -> set[str]:
    """Die Planzeilen, die eine erwartete Einnahme sind (`Klammer:Nummer`), eingeschaltet."""
    from finctl.forecast import szenarien as sz

    return {f"{s.id}:{i}" for s in sz.active(jm._szenarien_laden())
            for i, line in enumerate(s.lines) if line.kind == "erwartet"}


def vertraege_ohne_zuordnung() -> set[str]:
    """Die Kategorien, in denen ein Vertrag keine einzige Buchung kennt.

    Er weiss dann nicht, welche Reihe er ersetzt, und steht neben ihr: Betrag und Messung
    zaehlen beide.
    """
    from finctl import abos as _abos

    return {a["kategorie"] for a in _abos.alle_vertraege()
            if a.get("kategorie") and not a["buchungen"]}


def bauen(conn, views: list[dict], lauf: jm.Projection, jahr: int) -> Seite:
    """Die Seite aus den Rechnungen, wie sie sie gebildet haben.

    `views` ist die Rueckgabe von `konten.household_accounts` (zwoelf Monate genuegen),
    `lauf` die der Jahresrechnung und `jahr` das erste Jahr, das sie ganz projiziert. Der
    Betrag der Kontoprognose ist der des ersten Monats; eine Zeile steht da, sobald irgendein
    Monat der Vorschau einen Posten von ihr hat.
    """
    f = ag.fenster(conn)
    fenster = f"{f.von:%Y-%m} bis {f.bis:%Y-%m}" if f else ""
    zuordnung = Zuordnung(conn)
    monat: dict[str, int] = {}
    quellen_monat: dict[str, set[str]] = {}
    nur_konten = False
    erster = None
    for view in views:
        if not view.get("error") and view["rows"]:
            erster = erster or view["rows"][0]["month"]
    for zeile, cents, herkunft, im_ersten in _monatsposten(views, zuordnung):
        monat[zeile] = monat.get(zeile, 0) + (cents if im_ersten else 0)
        quellen_monat.setdefault(zeile, set()).add(herkunft["quelle"])
        if zeile == KLAMMERN and zuordnung.planzeile(herkunft["verweis"]).nur_kontoprognose:
            nur_konten = True
    jahresbetrag: dict[str, int] = {}
    quellen_jahr: dict[str, set[str]] = {}
    for zeile, cents, quelle in _jahresposten(lauf, jahr, erwartete_zeilen()):
        jahresbetrag[zeile] = jahresbetrag.get(zeile, 0) + cents
        quellen_jahr.setdefault(zeile, set()).add(quelle)

    bloecke = {b.id: b.label for b in ag.bloecke()}
    zeilen = []
    for schluessel in REIHENFOLGE:
        im_monat, im_jahr = schluessel in monat, schluessel in jahresbetrag
        if not (im_monat or im_jahr):
            continue
        href, ort = ORT.get(schluessel, ("", ""))
        if not href:
            href = (f"/transactions?block={schluessel}&start={f.von.isoformat()}"
                    f"&end={f.bis.isoformat()}") if f else "/transactions"
            ort = "Buchungen des Messfensters"
        zeilen.append(Zeile(
            schluessel, _name(schluessel, bloecke),
            monat.get(schluessel) if im_monat else None,
            jahresbetrag.get(schluessel) if im_jahr else None,
            _quelle(schluessel, fenster, monatsmodell=True, nur_konten=nur_konten)
            if im_monat else None,
            _quelle(schluessel, fenster, monatsmodell=False, nur_konten=nur_konten)
            if im_jahr else None,
            href, ort))
    return Seite(monat=date.fromisoformat(erster[:7] + "-01") if erster else None,
                 jahr=jahr, fenster=fenster, zeilen=zeilen)
