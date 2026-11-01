"""Die Rentenluecke: was zum Rentenbeginn an Kapital dastehen muss.

Ein festes Ziel mit denselben Regeln fuer alle, gerechnet statt getippt:

* BEDARF sind die laufenden Ausgaben im ersten vollen Rentenjahr, wie die
  Hochrechnung sie fuehrt -- der heutige Konsum mit der Inflation
  fortgeschrieben, dazu was dann noch laeuft: Kreditraten, eingeschaltete
  Plaene, Objekte. Wer ein Objekt zum Rentenbeginn verkaufen will, plant das;
  eine Erbschaft ebenso. Keine eigene Logik fuer beides.
* EINNAHMEN sind im selben Jahr alles Laufende ausser Gehalt: Renten nach
  Abzug, Mieten, Objekte.
* Die LUECKE waechst mit der Inflation und wird bis zur Lebenserwartung
  entnommen, jeweils zu Jahresbeginn. Verzinst wird mit der Depotrendite --
  derselben, mit der die Hochrechnung im Ruhestand rechnet.
* Was man NICHT aufbrauchen will, bleibt am Ende stehen: bei 100 %
  aufbrauchen endet das Kapital bei null, bei 50 % bei der Haelfte des
  Anfangs.

Alles nominal, wie die Hochrechnung. Das Ziel misst gegen das gesamte liquide
Vermoegen und seine Hochrechnung zum Rentenbeginn.

Was sie ausser der Hochrechnung braucht (Geburtsdatum, Rentenbeginn, Satz,
Inflation, Lebenserwartung, Anteil zum Aufbrauchen), steht in den `Eingaben`
dieser Hochrechnung: Sie liest es einmal, die Rentenluecke oeffnet keine Datei.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from finctl.forecast.herkunft import eur, prozent

if TYPE_CHECKING:
    from finctl.forecast.jahre import Eingaben

ZIEL_ID = "rentenluecke"
NAME = "Rentenlücke"


@dataclass(slots=True)
class Luecke:
    beginn: date
    jahr: int                 # erstes volles Rentenjahr
    bis_jahr: int             # Jahr der Lebenserwartung
    bedarf_cents: int         # je Jahr, nominal im ersten vollen Rentenjahr
    einnahmen_cents: int
    rendite: float
    inflation: float
    aufbrauchen: float
    kapital_cents: int
    rechenweg: list[str] = field(default_factory=list)

    @property
    def luecke_cents(self) -> int:
        return max(self.bedarf_cents - self.einnahmen_cents, 0)

    @property
    def jahre(self) -> int:
        return self.bis_jahr - self.jahr + 1


def kapitalbedarf(luecke: int, jahre: int, rendite: float, inflation: float,
                  aufbrauchen: float) -> int:
    """Das Kapital, aus dem sich `luecke` (mit der Inflation wachsend) `jahre`
    lang zu Jahresbeginn entnehmen laesst, und das danach noch den nicht
    aufgebrauchten Teil seiner selbst traegt."""
    if luecke <= 0 or jahre <= 0:
        return 0
    barwert = sum(luecke * ((1 + inflation) / (1 + rendite)) ** t for t in range(jahre))
    rest = (1 - aufbrauchen) / (1 + rendite) ** jahre
    return round(barwert / (1 - rest)) if rest < 1 else 0


def rechnen(lauf, e: Eingaben) -> Luecke | None:
    """Aus einer Hochrechnung, die mindestens das erste volle Rentenjahr
    enthaelt, und den Eingaben, aus denen sie gerechnet ist. None ohne
    Geburtsdatum oder wenn die Rechnung zu frueh endet."""
    beginn, geburtstag = e.rentenbeginn, e.geburtsdatum
    if beginn is None or geburtstag is None:
        return None
    jahr = beginn.year + (1 if beginn.month > 1 else 0)
    zeile = next((y for y in lauf.years if y.year == jahr), None)
    if zeile is None:
        return None
    fluss = zeile.cashflow()
    bedarf = -fluss["laufend_raus"]
    einnahmen = fluss["laufend_rein"] - zeile.blocks.get("gehalt", 0)
    a = e.annahmen
    bis_jahr = geburtstag.year + a.lebenserwartung
    rendite, inflation, aufbrauchen = a.rendite_depot, a.inflation, a.aufbrauchen
    kapital = kapitalbedarf(bedarf - einnahmen, bis_jahr - jahr + 1, rendite,
                            inflation, aufbrauchen)
    luecke = Luecke(beginn=beginn, jahr=jahr, bis_jahr=bis_jahr, bedarf_cents=bedarf,
               einnahmen_cents=einnahmen, rendite=rendite, inflation=inflation,
               aufbrauchen=aufbrauchen, kapital_cents=kapital)
    luecke.rechenweg = [
        (f"Laufende Ausgaben {jahr}: {eur(bedarf)} — heutiger Konsum und was dann "
         "noch läuft, mit der Inflation fortgeschrieben"),
        (f"Laufende Einnahmen ohne Gehalt {jahr}: {eur(einnahmen)} — Renten nach "
         "Abzug, Mieten, Objekte"),
        f"Lücke: {eur(luecke.luecke_cents)} im Jahr, wachsend mit {prozent(inflation)} Inflation",
        (f"Entnommen {luecke.jahre} Jahre bis {bis_jahr} (Lebenserwartung), verzinst "
         f"mit {prozent(rendite)}, {round(aufbrauchen * 100)} % aufgebraucht"),
        f"Kapital zum Rentenbeginn {beginn.strftime('%Y-%m')}: {eur(kapital)}",
    ]
    return luecke


def als_ziel(luecke: Luecke) -> dict:
    """Die Luecke als Ziel fuer /ziele: gerechnet, nicht bearbeitbar."""
    return {"id": ZIEL_ID, "name": NAME, "cents": luecke.kapital_cents,
            "stichtag": luecke.beginn.isoformat(), "fest": True}


def mit_ziel(goals: dict, lauf, e: Eingaben) -> tuple[dict, Luecke | None]:
    """Die Ziele samt Rentenluecke -- unveraendert, wenn sie sich nicht
    rechnen laesst (kein Geburtsdatum, Rechnung zu kurz)."""
    luecke = rechnen(lauf, e)
    if luecke is None:
        return goals, None
    return {**goals, "ziele": [*(goals.get("ziele") or []), als_ziel(luecke)]}, luecke
