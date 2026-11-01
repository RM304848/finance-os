"""Woraus eine Prognosezahl besteht.

Eine Jahressumme von -30.000 Fixkosten ist nicht pruefbar. Pruefbar ist sie
erst, wenn daneben steht, welche Kategorien darin stecken, ueber welches
Fenster sie gemessen wurden und mit welchem Faktor sie fortgeschrieben sind.
Ohne das fielen zwei Rechenmaschinen mit verschiedenen Basen erst im Chat auf.

DIE SUMME DER POSTEN IST DIE ANGEZEIGTE ZAHL. Blocksummen werden aus den
Posten gebildet und nicht daneben gerechnet -- eine Erklaerung, die neben der
Rechnung herlaeuft, stimmt am ersten Tag und danach nicht mehr.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Der feste Satz an Quellen. Die Seite zeigt sie als Pill, und ein freier
#: Text an dieser Stelle waere nach dem dritten Posten nicht mehr vergleichbar.
QUELLEN = {
    "gemessen": "aus dem Ledger gemessen",
    "annahme": "aus assumptions.yaml",
    "vertrag": "aus dem Tilgungsplan",
    "plan": "aus einer Planklammer",
    "rendite": "Satz auf einen Bestand",
    "regel": "aus einer Regel der Rechnung",
}


@dataclass(frozen=True, slots=True)
class Posten:
    """Ein Posten im Rechenweg einer angezeigten Zahl.

    `cents` hat zwei Bedeutungen, je nachdem, wer den Posten baut:

    - **Hochrechnung:** ein Summand. Die Posten eines Blocks ergeben seine
      Zahl, `summe` bildet sie, und nichts daneben rechnet.
    - **Kontoprognose:** die Beschreibung einer Reihe. `cents` ist der Betrag
      je Termin, beim Kredit die erste Rate. Keine Summe dieser Posten ergibt
      eine angezeigte Zahl, weil die Reihen verschieden oft zahlen.

    Wer Posten addiert, etwa fuer die Wirkung nach Ursachen, darf nur die der
    ersten Art nehmen. `tests/test_verfahren.py` haelt fest, dass `summe` nur
    dort vorkommt, wo Posten Summanden sind.
    """

    label: str
    #: Vorzeichen wie im Ledger.
    cents: int
    quelle: str
    herleitung: str
    #: Kennung zum Nachschlagen: Kategorie, Kredit-id, klammer:zeile.
    verweis: str | None = None
    #: Einmalig statt laufend -- fuer "einmalig rein/raus" auf /annahmen.
    einmalig: bool = False
    #: Nur bei Planposten: die Kategorie der Planzeile, damit die Kennzahl
    #: "ohne Objekt" sie von Kaufnebenkosten unterscheiden kann.
    kategorie: str | None = None
    #: Geld zwischen zwei Konten, die die Prognose beide rechnet: Dauerauftrag
    #: und Zuweisung, Auffuellung, Abraeumen. Es steht auf beiden Seiten im
    #: Haushalt und ist weder Einnahme noch Ausgabe. Wer ueber Konten summiert
    #: (`ohne_objekt`, `tests/test_paritaet.py`), erkennt es an diesem Merkmal und
    #: nicht am Etikett des Postens.
    umbuchung: bool = False
    #: Miete oder Kosten eines Objekts mit Prognose (`objektposten`). Wie `umbuchung` ein
    #: Merkmal des Postens: `ohne_objekt` nimmt ihn heraus, der Paritaetstest ordnet ihn dem
    #: Block `objekt` zu, und beide lesen es hier, nicht am Etikett.
    objekt: bool = False

    def __post_init__(self) -> None:
        if self.quelle not in QUELLEN:
            raise ValueError(f"unbekannte Quelle {self.quelle!r}")

    def als_dict(self) -> dict:
        return {"label": self.label, "cents": self.cents, "quelle": self.quelle,
                "herleitung": self.herleitung, "verweis": self.verweis,
                "einmalig": self.einmalig}

    def als_herkunft(self) -> dict:
        """Der Rechenweg, wie ihn die Kontoprognose ausgibt: je Etikett drei
        Schluessel, bei Planposten dazu die Kategorie, bei einer Umbuchung
        `umbuchung`, bei einem Objektposten `objekt`. Die Seite, ihre Schnittstelle und
        die Kennzahl lesen genau diese Schluessel."""
        out = {"quelle": self.quelle, "herleitung": self.herleitung,
               "verweis": self.verweis}
        if self.quelle == "plan":
            out["kategorie"] = self.kategorie
        if self.umbuchung:
            out["umbuchung"] = True
        if self.objekt:
            out["objekt"] = True
        return out


def summe(posten: list[Posten]) -> int:
    return sum(p.cents for p in posten)


def eur(cents: int) -> str:
    """Ganze Euro, deutsch, mit echtem Minus. Fuer Herleitungen reicht das."""
    euro = round(cents / 100)
    text = f"{abs(euro):,}".replace(",", ".")
    return f"−{text} €" if euro < 0 else f"{text} €"


def eur_genau(cents: int) -> str:
    """Mit Cent -- fuer Monatsbetraege, wo ganze Euro 9,60 zu 10 machen."""
    text = f"{abs(cents) // 100:,}".replace(",", ".") + f",{abs(cents) % 100:02d} €"
    return f"−{text}" if cents < 0 else text


def faktor(wert: float) -> str:
    return f"{wert:.3f}".replace(".", ",")


def prozent(satz: float) -> str:
    return f"{satz * 100:.2f}".replace(".", ",") + " %"


def monat(d) -> str:
    return f"{d.month:02d}/{d.year}"
