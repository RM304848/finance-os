"""Die Prognose eines Objekts als Betraege je Monat -- die eine Rechnung beider Modelle.

Ein Objekt mit Prognose (`objekte.prognosen`, `prognose:` in properties.yaml) wirft
Miete ab und kostet; beides nimmt die Rechnung aus der Prognose, nicht aus seinen
Buchungen. Die Jahresrechnung (`jahre._objektposten`) summiert die Monate eines Jahres
zu einem Block `objekt`, das Monatsmodell (`konten._objektposten`) bucht sie je Monat
auf ein Konto. Beide rufen `betraege`, damit Steigerung, Saison und Ende dieselben sind.

* STEIGERUNG: stufenweise, ein Mal im Jahr. Im Jahr des Basisjahrs stehen die Betraege
  der Prognose, jedes Jahr danach kommt die Inflation dazu (`assumptions.grow`).
* SAISON: die Kurve `saison` wirkt auf die Miete, nicht auf die Kosten -- die Kosten
  laufen gleichmaessig, die Belegung nicht. Eine Kurve aus lauter 1,0 aendert nichts; eine
  andere verschiebt Geld zwischen Monaten, ueber ein volles Jahr bleibt die Summe.
* ENDE: die Prognose (`ab`, `bis`) und der Verkauf. Ab dem Monat des Verkaufs wirft das
  Objekt nichts mehr ab und kostet nichts mehr.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from finctl import assumptions as ann
from finctl.objekte import Prognose

#: Die Kategorie, in der die Miete eines Objekts gebucht wird.
MIETE_KATEGORIE = "immobilie/mieteinnahme"
#: Vorsilben der Etiketten, unter denen /konten die Posten eines Objekts fuehrt.
MIETE_ETIKETT = "objekt-miete:"
KOSTEN_ETIKETT = "objekt-kosten:"


def laeuft(p: Prognose, monat: date, verkauf_ab: date | None = None) -> bool:
    """Wirft das Objekt in diesem Monat etwas ab? Nicht ab dem Monat seines Verkaufs."""
    erster = date(monat.year, monat.month, 1)
    if verkauf_ab and erster >= date(verkauf_ab.year, verkauf_ab.month, 1):
        return False
    return p.laeuft(erster)


def betraege(p: Prognose, monat: date, basisjahr: int, inflation: float,
             verkauf_ab: date | None = None) -> tuple[int, int] | None:
    """(Miete, Kosten) des Objekts in diesem Monat, beide ohne Vorzeichen; `None`, wenn es
    nicht laeuft.

    Netto ist die Prognose gesteigert (`grow(netto)`), dazu der Zuschlag der Saison auf die
    Miete; die Miete ist netto plus Kosten. So ergibt Miete minus Kosten genau den Betrag, den
    die Jahresrechnung je Monat zaehlt, auch gerundet.
    """
    if not laeuft(p, monat, verkauf_ab):
        return None
    jahre = monat.year - basisjahr
    kosten = ann.grow(p.kosten_cents, jahre, inflation)
    zuschlag = round(ann.grow(p.miete_cents, jahre, inflation)
                     * (p.saison[monat.month - 1] - 1.0))
    netto = ann.grow(p.netto_cents, jahre, inflation) + zuschlag
    return netto + kosten, kosten


def netto(p: Prognose, monat: date, basisjahr: int, inflation: float,
          verkauf_ab: date | None = None) -> int:
    """Miete minus Kosten in diesem Monat; null, wenn das Objekt nicht laeuft."""
    miete_und_kosten = betraege(p, monat, basisjahr, inflation, verkauf_ab)
    return 0 if miete_und_kosten is None else miete_und_kosten[0] - miete_und_kosten[1]


def hat_saison(p: Prognose) -> bool:
    """Weicht die Kurve des Objekts von lauter 1,0 ab?"""
    return any(f != 1.0 for f in p.saison)


def konto_der_miete(conn: sqlite3.Connection, property_id: str, bis: date) -> str | None:
    """Das Konto, auf dem die Miete des Objekts zuletzt gebucht wurde (bis `bis`).

    Das Objekt fuehrt kein Konto, und sein Kredit nennt das der Rate, nicht der Miete. Die
    Buchungen sagen es: der letzte Teil in `immobilie/mieteinnahme` mit der Kennung des
    Objekts. `None`, wo es keine gibt."""
    zeile = conn.execute(
        """SELECT t.account_id
           FROM   splits s JOIN transactions t ON t.id = s.transaction_id
           WHERE  s.property_id = ? AND s.mgmt_category_id = ? AND t.booking_date <= ?
           ORDER  BY t.booking_date DESC, t.id DESC LIMIT 1""",
        (property_id, MIETE_KATEGORIE, bis.isoformat())).fetchone()
    return zeile[0] if zeile else None


def anzeigenamen(prognosen: list[Prognose], etiketten: set[str]) -> dict[str, str]:
    """Die Namen der Posten eines Objekts auf /konten, soweit sie vorkommen."""
    namen = {}
    for p in prognosen:
        for vorsatz, text in ((MIETE_ETIKETT, "Miete (Prognose)"),
                              (KOSTEN_ETIKETT, "Kosten (Prognose)")):
            if f"{vorsatz}{p.id}" in etiketten:
                namen[f"{vorsatz}{p.id}"] = f"{p.name}: {text}"
    return namen

