"""Ein kurzfristiges Ziel, gemessen mit dem Monatsmodell.

Zwei Rechnungen sagen, wo ein Ziel an seinem Stichtag steht: die Jahresrechnung (Jahresenden,
dazwischen linear verbunden, Kaskade) und das Monatsmodell von `/konten` (je Konto und Monat,
mit den aktiven Klammern). Liegt der Stichtag im Horizont des Monatsmodells, misst es:
Eine Klammer wie ein Autokauf bewegt die Karte nur, wenn die Rechnung sie am Termin sieht.

Das Ziel misst den Stand seiner Basiskonten zum Stichtag. Gehoert zur Basis etwas, das das
Monatsmodell nicht projiziert (ein Depot, eine Police, ein Konto ohne Auszuege), misst die
Jahresrechnung das ganze Ziel: Der heutige Stand eines Depots, fortgeschrieben, waere eine
Zahl, die keine der beiden Rechnungen so rechnet.

Der Notgroschen geht ab wie in der Jahresrechnung (`ziele.hochgerechnet`): Ein Ziel, das das
Tagesgeld zaehlt, ohne selbst der Notgroschen zu sein, misst ohne seine Grenze.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable, Mapping
from datetime import date

from finctl.forecast import ziele as _z

#: Welches Modell eine Karte misst.
MONATSMODELL = "monat"
JAHRESRECHNUNG = "jahr"

#: Der Horizont von `/konten` (`ops.HORIZON_LONG`).
HORIZONT_MONATE = 60


def monatsende(erster: date) -> date:
    return erster.replace(day=calendar.monthrange(erster.year, erster.month)[1])


def im_horizont(due: date | None, stichtag: date, monate: int = HORIZONT_MONATE) -> bool:
    """Liegt der Stichtag nach dem Start der Prognose und bis zum Ende ihres letzten Monats?"""
    if due is None or due <= stichtag:
        return False
    jahr, monat = divmod(stichtag.month - 1 + monate, 12)
    return due <= monatsende(date(stichtag.year + jahr, monat + 1, 1))


def brauchbar(prog: _z.Progress, stichtag: date, monate: int = HORIZONT_MONATE) -> bool:
    """Kommt das Ziel fuer das Monatsmodell in Frage: Zielbetrag, Stichtag im Horizont."""
    return bool(prog.target_cents) and im_horizont(prog.due, stichtag, monate)


def _stand(view: Mapping, bis: date) -> int:
    """Der Stand eines Kontos am Ende des letzten Monats, der bis `bis` zu Ende ist.

    Ist noch kein Monat zu Ende, der Anfangsstand der Prognose.
    """
    stand = int(view["opening_cents"])
    for row in view["rows"]:
        if monatsende(date.fromisoformat(row["month"])) > bis:
            break
        stand = int(row["closing_cents"])
    return stand


def basiskonten(prog: _z.Progress, merged: Mapping,
                views: Iterable[Mapping]) -> list[str] | None:
    """Die projizierten Konten der Basis -- oder None, wenn etwas davon nicht projiziert ist."""
    projiziert = {v["id"] for v in views if not v.get("error") and v.get("rows")}
    erlaubt = tuple(k.lower() for k in (prog.basis or _z.LIQUID_KINDS))
    konten = []
    for zeile in merged.get("balances") or []:
        if not _z._passt(zeile, erlaubt):
            continue
        konto = str(zeile.get("account_id") or "")
        if konto in projiziert:
            konten.append(konto)
        elif zeile.get("cents") is not None:
            return None
    return konten or None


def hochgerechnet(prog: _z.Progress, merged: Mapping, views: list[dict],
                  puffer_cents: int | None) -> _z.Hochgerechnet | None:
    """Der Wert des Ziels an seinem Stichtag aus dem Monatsmodell -- oder None."""
    konten = basiskonten(prog, merged, views)
    if konten is None or prog.due is None or not prog.target_cents:
        return None
    nach_id = {v["id"]: v for v in views if not v.get("error") and v.get("rows")}
    bis = prog.due
    cents = sum(_stand(nach_id[k], bis) for k in konten)
    toepfe = _z.toepfe_fuer_basis(prog.basis) if prog.basis else None
    if (puffer_cents and prog.goal_id != _z.PUFFER_ZIEL
            and (not toepfe or "tagesgeld" in toepfe)):
        tagesgeld = sum(_stand(nach_id[str(z["account_id"])], bis)
                        for z in merged.get("balances") or []
                        if _z.TOPF.get(_z.art(z.get("kind"))) == "tagesgeld"
                        and str(z.get("account_id") or "") in nach_id)
        cents -= min(max(tagesgeld, 0), puffer_cents)
    return _z.Hochgerechnet(cents, prog.due.year, 100.0 * cents / prog.target_cents)


class Lauf:
    """Das Monatsmodell fuer die Ziele einer Seite: einmal gerechnet, nur wenn eines es braucht."""

    def __init__(self, conn, monate: int = HORIZONT_MONATE) -> None:
        from finctl.forecast.stichtag import stichtag

        self.conn = conn
        self.monate = monate
        self.stichtag = stichtag(conn)
        self._views: list[dict] | None = None

    @property
    def views(self) -> list[dict]:
        if self._views is None:
            from finctl.forecast.konten import household_accounts

            self._views = household_accounts(self.conn, months=self.monate)
        return self._views

    def misst(self, prog: _z.Progress) -> bool:
        return brauchbar(prog, self.stichtag, self.monate)


def misst_das_monatsmodell(prog: _z.Progress, merged: Mapping, monat: Lauf) -> bool:
    """Misst das Monatsmodell dieses Ziel: Stichtag im Horizont, ganze Basis dort projiziert."""
    return monat.misst(prog) and basiskonten(prog, merged, monat.views) is not None


def messen(prog: _z.Progress, jahresrechnung, merged: Mapping, puffer_cents: int | None,
           monat: Lauf) -> tuple[_z.Hochgerechnet | None, str]:
    """Der Wert des Ziels an seinem Stichtag und das Modell, das ihn misst.

    Das Monatsmodell, wenn der Stichtag in seinem Horizont liegt und die ganze Basis dort
    projiziert wird (`misst_das_monatsmodell`); sonst die Jahresrechnung
    (`ziele.hochgerechnet`).
    """
    if misst_das_monatsmodell(prog, merged, monat):
        h = hochgerechnet(prog, merged, monat.views, puffer_cents)
        if h is not None:
            return h, MONATSMODELL
    return _z.hochgerechnet(jahresrechnung, prog), JAHRESRECHNUNG
