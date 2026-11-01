"""Der Takt einer Reihe: je Fall eine erfundene Reihe, runde Betraege.

`erkennen` und `fortschreiben` rechnen auf Listen, ohne Datenbank und ohne
Datei. Nur `reihen` liest, und das auf einem Hauptbuch im Speicher.
"""

from __future__ import annotations

import builtins
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from finctl.forecast import takt as tk
from finctl.forecast.messung import Ausschluss
from finctl.forecast.takt import (
    EINMALIG,
    UNREGELMAESSIG,
    erkennen,
    fortschreiben,
    termine_bilden,
)

STICHTAG = date(2026, 9, 30)


def _monatlich(erster: date, n: int, cents: int, *, tag: int = 1) -> list[tuple[date, int]]:
    """n Buchungen, je eine im Monat, am `tag` (am Monatsende gekappt)."""
    out = []
    for i in range(n):
        index = erster.month - 1 + i
        jahr, monat = erster.year + index // 12, index % 12 + 1
        letzter = (date(jahr + monat // 12, monat % 12 + 1, 1) - timedelta(days=1)).day
        out.append((date(jahr, monat, min(tag, letzter)), cents))
    return out


def _bis_stichtag(n: int, cents: int, *, tag: int = 1) -> list[tuple[date, int]]:
    """Die letzten n Monate bis einschliesslich September 2026."""
    index = 2026 * 12 + 8 - (n - 1)
    return _monatlich(date(index // 12, index % 12 + 1, 1), n, cents, tag=tag)


# ------------------------------------------------------------- erkennen


def test_a_monthly_series_with_a_sliding_day_is_monthly_and_counts_twelve_terms():
    """Faellig am 1., gebucht an manchen Monaten schon am Letzten davor: Das
    Fenster hat dreizehn Buchungen, davon zwei im Oktober, aber nur zwoelf
    Termine."""
    buchungen = _monatlich(date(2025, 10, 1), 13, -1_000)       # 10/2025 bis 10/2026
    for i in (1, 5, 9, 12):                                       # 31.10., 28.02., 30.06., 30.09.
        buchungen[i] = (buchungen[i][0] - timedelta(days=1), -1_000)
    buchungen.sort()
    im_fenster = [b for b in buchungen if b[0] <= STICHTAG]
    assert len(im_fenster) == 13
    erkannt = erkennen(im_fenster, fixkosten=False)
    assert erkannt.takt == 1
    beitrag = fortschreiben(erkannt.termine, 1, stichtag=STICHTAG)
    assert beitrag.betrag_je_termin == -1_000
    assert beitrag.jahreswert == -12_000
    assert sum(c for _, c in im_fenster) == -13_000


def test_rent_one_month_late_is_still_monthly():
    """Ein Monat ohne Buchung, ein anderer mit zwei: drei Viertel der Abstaende
    reichen."""
    buchungen = [b for b in _bis_stichtag(14, -80_000, tag=3)
                 if b[0] != date(2026, 3, 3)]
    buchungen.append((date(2026, 4, 1), -80_000))
    erkannt = erkennen(sorted(buchungen), fixkosten=False)
    assert erkannt.takt == 1
    assert fortschreiben(erkannt.termine, 1, stichtag=STICHTAG).jahreswert == -960_000


def test_quarterly_with_one_debit_two_weeks_late_is_three():
    buchungen = _monatlich(date(2025, 1, 1), 8, -34_000, tag=15)[::3]
    buchungen[2] = (buchungen[2][0] + timedelta(days=14), -34_000)
    assert [c for _, c in buchungen] == [-34_000] * 3
    erkannt = erkennen(buchungen, fixkosten=False)
    assert erkannt.takt == 3
    assert fortschreiben(erkannt.termine, 3, stichtag=date(2025, 9, 30)
                         ).jahreswert == -136_000


def test_a_yearly_premium_in_two_instalments_is_one_term_per_year():
    """Januar und Februar sind eine Zahlung in Raten, zwei Jahre lang: Takt 12,
    der Betrag je Termin die Summe der Raten."""
    buchungen = [(date(2025, 1, 10), -40_000), (date(2025, 2, 10), -20_000),
                 (date(2026, 1, 10), -40_000), (date(2026, 2, 10), -20_000)]
    erkannt = erkennen(buchungen, fixkosten=False)
    assert erkannt.takt == 12
    assert [t.cents for t in erkannt.termine] == [-60_000, -60_000]
    beitrag = fortschreiben(erkannt.termine, 12, stichtag=STICHTAG)
    assert beitrag.betrag_je_termin == -60_000
    assert beitrag.jahreswert == -60_000


def test_a_weekly_shop_with_scattered_amounts_is_irregular():
    start = date(2025, 10, 4)
    betraege = [-4_200, -9_100, -2_300, -7_800, -5_500, -3_100, -8_800]
    buchungen = [(start + timedelta(days=7 * i), betraege[i % len(betraege)])
                 for i in range(60)]
    assert erkennen(buchungen, fixkosten=False).takt == UNREGELMAESSIG
    assert erkennen(buchungen, fixkosten=True).takt == UNREGELMAESSIG


def test_equal_spacing_with_amounts_beyond_the_tolerance_is_irregular():
    """Regelmaessiger Abstand allein macht keinen Takt: die Haelfte der Betraege
    liegt ausserhalb von +-25 %."""
    buchungen = [(d, -1_000 if i % 2 else -2_000)
                 for i, (d, _) in enumerate(_bis_stichtag(12, 0, tag=15))]
    assert erkennen(buchungen, fixkosten=False).takt == UNREGELMAESSIG


def test_a_series_that_stopped_three_months_ago_is_over_and_counts_nothing():
    buchungen = _monatlich(date(2025, 7, 1), 12, -1_500)          # bis Juni 2026
    erkannt = erkennen(buchungen, fixkosten=False)
    assert erkannt.takt == 1
    beitrag = fortschreiben(erkannt.termine, 1, stichtag=STICHTAG)
    assert beitrag.laeuft is False
    assert beitrag.letzter_termin == date(2026, 6, 1)
    assert beitrag.jahreswert == 0
    assert beitrag.text == "monatlich, beendet, zuletzt 06/2026"


def test_a_new_series_with_three_terms_runs_at_full_value():
    buchungen = _bis_stichtag(3, -2_900, tag=5)
    erkannt = erkennen(buchungen, fixkosten=False)
    assert erkannt.takt == 1
    beitrag = fortschreiben(erkannt.termine, 1, stichtag=STICHTAG)
    assert beitrag.laeuft and beitrag.jahreswert == -34_800


def test_one_missing_monthly_term_does_not_end_a_series_two_do():
    """Monatlich: der letzte Termin darf bis zwei Monate vor dem Monatsende
    liegen, ein fehlender Termin beendet nichts. Der 10. August ist 51 Tage vor
    dem 30. September (der Septembertermin fehlt), der 25. Juli 67 (zwei fehlen)."""
    einer_fehlt = _monatlich(date(2025, 11, 10), 10, -1_000, tag=10)  # bis 10.08.2026
    assert einer_fehlt[-1][0] == date(2026, 8, 10)
    assert fortschreiben(erkennen(einer_fehlt, fixkosten=False).termine, 1,
                         stichtag=STICHTAG).laeuft
    zwei_fehlen = _monatlich(date(2025, 10, 25), 10, -1_000, tag=25)  # bis 25.07.2026
    assert zwei_fehlen[-1][0] == date(2026, 7, 25)
    assert not fortschreiben(erkennen(zwei_fehlen, fixkosten=False).termine, 1,
                             stichtag=STICHTAG).laeuft


def test_from_two_months_on_half_a_term_overdue_ends_a_series():
    """Ab Takt 2 ist der halbe Takt mindestens ein Monat: vierteljaehrlich
    beendet, was mehr als viereinhalb Monate vor dem Monatsende zuletzt kam."""
    quartal = [(date(2025, 1, 15) + timedelta(days=round(91.3 * i)), -6_000)
               for i in range(6)]                                    # bis Mitte April 2026
    assert date(2026, 4, 1) <= quartal[-1][0] <= date(2026, 4, 30)
    assert not fortschreiben(erkennen(quartal, fixkosten=False).termine, 3,
                             stichtag=STICHTAG).laeuft


def test_one_term_counts_as_yearly_only_for_a_fixed_cost_category():
    einmal = [(date(2026, 3, 12), -9_000)]
    erkannt = erkennen(einmal, fixkosten=True)
    assert erkannt.takt == 12 and len(erkannt.termine) == 1
    assert fortschreiben(erkannt.termine, 12, stichtag=STICHTAG).jahreswert == -9_000
    assert erkennen(einmal, fixkosten=False).takt == UNREGELMAESSIG


def test_two_terms_a_year_apart_need_no_fixed_cost_flag_but_one_booking_does():
    zwei = [(date(2025, 3, 12), -9_000), (date(2026, 3, 12), -9_000)]
    assert erkennen(zwei, fixkosten=False).takt == 12


def test_a_monthly_advance_with_one_back_payment_keeps_the_advance_as_the_term():
    """Nachzahlung beim selben Empfaenger: Der Abschlag bleibt der Takt, die
    Nachzahlung ein Ausreisser, der im Rest seiner Kategorie zaehlt."""
    buchungen = _bis_stichtag(12, -10_000, tag=2)
    buchungen.append((date(2026, 5, 20), -60_000))
    erkannt = erkennen(sorted(buchungen), fixkosten=False)
    assert erkannt.takt == 1
    beitrag = fortschreiben(erkannt.termine, 1, stichtag=STICHTAG)
    assert beitrag.betrag_je_termin == -10_000
    assert [t.cents for t in beitrag.ausreisser] == [-60_000]
    assert beitrag.jahreswert == -120_000
    assert beitrag.laeuft and beitrag.letzter_termin == date(2026, 9, 2)
    assert beitrag.verlauf == ()


def test_a_raise_three_terms_ago_is_the_new_amount_each_term():
    buchungen = _bis_stichtag(10, -10_000, tag=2)[:-3] + _bis_stichtag(3, -14_000, tag=2)
    erkannt = erkennen(buchungen, fixkosten=False, stichtag=STICHTAG)
    assert erkannt.takt == 1
    beitrag = fortschreiben(erkannt.termine, 1, stichtag=STICHTAG)
    assert beitrag.betrag_je_termin == -14_000
    assert beitrag.jahreswert == -168_000
    assert len(beitrag.verlauf) == 7 and beitrag.ausreisser == ()


def test_a_raise_two_terms_ago_is_already_the_new_amount():
    """Zwei Termine ab der geltenden Hoehe genuegen: Die Reihe bleibt monatlich,
    mit dem neuen Betrag, und die alten Termine sind der Verlauf."""
    buchungen = _bis_stichtag(10, -10_000, tag=2)[:-2] + _bis_stichtag(2, -14_000, tag=2)
    erkannt = erkennen(buchungen, fixkosten=False, stichtag=STICHTAG)
    assert erkannt.takt == 1
    beitrag = fortschreiben(erkannt.termine, 1, stichtag=STICHTAG)
    assert beitrag.betrag_je_termin == -14_000 and beitrag.jahreswert == -168_000
    assert len(beitrag.verlauf) == 8 and beitrag.ausreisser == ()


def test_a_yearly_term_needs_only_one_term_at_the_height_in_a_fixed_cost_category():
    buchungen = [(date(2025, 3, 12), -9_000), (date(2026, 3, 12), -15_000)]
    erkannt = erkennen(buchungen, fixkosten=True, stichtag=STICHTAG)
    assert erkannt.takt == 12
    beitrag = fortschreiben(erkannt.termine, 12, stichtag=STICHTAG)
    assert beitrag.betrag_je_termin == -15_000 and len(beitrag.verlauf) == 1


def test_two_purchases_a_year_apart_at_different_prices_are_not_yearly():
    """Zwei Einkaeufe beim selben Haendler, ein Jahr auseinander und verschieden
    teuer: ohne Fixkosten-Merkmal keine Jahreszahlung, sondern Rest."""
    buchungen = [(date(2025, 3, 12), -9_000), (date(2026, 3, 12), -15_000)]
    assert erkennen(buchungen, fixkosten=False, stichtag=STICHTAG).takt == UNREGELMAESSIG


def test_a_refund_shortly_before_the_next_term_is_an_outlier():
    """Die Erstattung kommt vor dem naechsten Termin, der noch nicht gebucht ist:
    Kein passender Termin steht neben ihr, und doch ist sie keine Rate."""
    buchungen = _bis_stichtag(12, -10_000, tag=1)
    buchungen.append((date(2026, 9, 23), 8_000))
    beitrag = fortschreiben(erkennen(sorted(buchungen), fixkosten=False).termine, 1,
                            stichtag=STICHTAG)
    assert [t.cents for t in beitrag.ausreisser] == [8_000]
    assert beitrag.letzter_termin == date(2026, 9, 1)


def test_a_raise_one_term_ago_is_not_yet_the_amount():
    buchungen = _bis_stichtag(10, -10_000, tag=2)[:-1] + _bis_stichtag(1, -14_000, tag=2)
    beitrag = fortschreiben(erkennen(buchungen, fixkosten=False).termine, 1,
                            stichtag=STICHTAG)
    assert beitrag.betrag_je_termin == -10_000


def test_a_refund_with_the_opposite_sign_is_no_term_of_the_series():
    buchungen = _bis_stichtag(12, -10_000, tag=2)
    buchungen.append((date(2026, 6, 15), 10_000))
    beitrag = fortschreiben(erkennen(sorted(buchungen), fixkosten=False).termine, 1,
                            stichtag=STICHTAG)
    assert [t.cents for t in beitrag.ausreisser] == [10_000]


def test_income_series_keep_their_sign():
    beitrag = fortschreiben(erkennen(_bis_stichtag(6, 95_000, tag=15),
                                     fixkosten=False).termine, 1, stichtag=STICHTAG)
    assert beitrag.jahreswert == 1_140_000


def test_an_advance_and_a_fee_on_the_same_day_are_one_term():
    """Abschlag und Gebuehr beim selben Empfaenger: je Monat ein Termin, auch bei
    Takt 1, Betrag die Summe."""
    buchungen = sorted(b for d, c in _bis_stichtag(12, -10_000, tag=2)
                       for b in ((d, c), (d, -500)))
    assert len(buchungen) == 24
    assert [len(t.buchungen) for t in termine_bilden(buchungen, 1)] == [2] * 12
    erkannt = erkennen(buchungen, fixkosten=False, stichtag=STICHTAG)
    assert erkannt.takt == 1
    beitrag = fortschreiben(erkannt.termine, 1, stichtag=STICHTAG)
    assert beitrag.betrag_je_termin == -10_500
    assert beitrag.jahreswert == -126_000


def test_a_standing_order_that_went_up_after_ten_terms_has_the_new_amount_and_a_history():
    """Die alten Termine sind weder Takt noch Ausreisser: Die Reihe schreibt ihre
    neue Hoehe fort, und die alte ist vorbei."""
    buchungen = _bis_stichtag(22, -10_000, tag=2)[:10] + _bis_stichtag(12, -15_000, tag=2)
    erkannt = erkennen(buchungen, fixkosten=False, stichtag=STICHTAG)
    assert erkannt.takt == 1
    beitrag = fortschreiben(erkannt.termine, 1, stichtag=STICHTAG)
    assert beitrag.betrag_je_termin == -15_000
    assert beitrag.jahreswert == -180_000
    assert [t.cents for t in beitrag.verlauf] == [-10_000] * 10
    assert beitrag.ausreisser == ()


def test_a_price_change_15_months_ago_does_not_make_the_series_irregular():
    """24 Termine, 9 zum alten Preis, 15 zum neuen: vorher unter drei Vierteln."""
    buchungen = _bis_stichtag(24, -10_000, tag=2)[:9] + _bis_stichtag(15, -15_000, tag=2)
    erkannt = erkennen(buchungen, fixkosten=False, stichtag=STICHTAG)
    assert erkannt.takt == 1
    beitrag = fortschreiben(erkannt.termine, 1, stichtag=STICHTAG)
    assert beitrag.betrag_je_termin == -15_000 and len(beitrag.verlauf) == 9


def test_a_series_that_falls_term_by_term_keeps_the_far_terms_as_history_not_outliers():
    """Zinsen eines Kredits: Was mehr als 25 % vom heutigen Betrag liegt, ist der
    Weg dorthin und zaehlt nicht im Rest."""
    buchungen = [(d, -20_000 + 500 * i) for i, (d, _) in enumerate(_bis_stichtag(12, 0))]
    beitrag = fortschreiben(erkennen(buchungen, fixkosten=False,
                                     stichtag=STICHTAG).termine, 1, stichtag=STICHTAG)
    assert beitrag.betrag_je_termin == -15_000
    assert [t.cents for t in beitrag.verlauf] == [-20_000, -19_500, -19_000]
    assert beitrag.ausreisser == ()
    assert beitrag.jahreswert == -180_000


def test_seven_irregular_bookings_of_a_similar_half_year_sum_are_not_yearly():
    """Zwei Jahre Tanken: Die Summe eines Halbjahrs ist keine Jahreszahlung. Ein
    Jahrestermin legt hoechstens drei Buchungstage zusammen."""
    buchungen = [(date(2025, 1, 10), -5_000), (date(2025, 2, 2), -8_000),
                 (date(2025, 2, 20), -3_000), (date(2025, 4, 14), -4_000),
                 (date(2026, 1, 11), -6_000), (date(2026, 3, 5), -9_000),
                 (date(2026, 4, 25), -5_000)]
    assert [t.cents for t in termine_bilden(buchungen, 12)] == [-20_000, -20_000]
    assert erkennen(buchungen, fixkosten=False, stichtag=STICHTAG).takt == UNREGELMAESSIG
    assert erkennen(buchungen, fixkosten=True, stichtag=STICHTAG).takt == UNREGELMAESSIG


def test_amounts_that_scatter_without_a_stable_height_are_not_a_series():
    """Drei von vier Terminen muessen ab irgendeinem Punkt zum Betrag passen,
    sonst gibt es keine geltende Hoehe -- auch nicht mit drei Terminen am Ende."""
    buchungen = [(d, c) for (d, _), c in zip(
        _bis_stichtag(4, 0), (-6_000, -6_000, -9_000, -3_000), strict=True)]
    assert erkennen(buchungen, fixkosten=False, stichtag=STICHTAG).takt == UNREGELMAESSIG
    # Ein festgelegter Takt rechnet trotzdem: ohne Verlauf, und die abweichenden
    # Termine stehen auf ihrem Platz im Takt, sind also keine Ausreisser.
    beitrag = fortschreiben(termine_bilden(buchungen, 1), 1, stichtag=STICHTAG)
    assert beitrag.verlauf == () and beitrag.ausreisser == ()
    assert beitrag.betrag_je_termin == -6_000


def test_a_yearly_premium_in_three_instalments_two_weeks_apart_stays_yearly():
    buchungen = [(date(j, m, t), -20_000) for j in (2025, 2026)
                 for m, t in ((1, 10), (1, 24), (2, 7))]
    erkannt = erkennen(buchungen, fixkosten=False, stichtag=STICHTAG)
    assert erkannt.takt == 12
    assert [t.cents for t in erkannt.termine] == [-60_000, -60_000]
    assert max(t.tage for t in erkannt.termine) == 3


def test_one_term_of_a_fixed_cost_category_with_many_booking_days_is_not_yearly():
    """Die Ausnahme fuer Fixkosten gilt fuer eine Anschaffung, nicht fuer ein
    halbes Jahr Einkaeufe in einer Abo-Kategorie."""
    drei = [(date(2026, 3, t), -1_000) for t in (3, 10, 17)]
    fuenf = [(date(2026, 3, t), -1_000 * (t % 4 + 1)) for t in (3, 8, 13, 19, 25)]
    assert erkennen(drei, fixkosten=True, stichtag=STICHTAG).takt == 12
    assert erkennen(fuenf, fixkosten=True, stichtag=STICHTAG).takt == UNREGELMAESSIG


def test_the_height_that_applies_begins_where_three_quarters_of_the_rest_fit():
    def termine(betraege):
        return termine_bilden([(date(2026, 1 + i, 5), c) for i, c in enumerate(betraege)], 1)

    assert tk.beginn_der_hoehe(termine([-10_000] * 4 + [-20_000] * 4), -20_000) == 4
    assert tk.beginn_der_hoehe(termine([-10_000] * 8), -10_000) == 0
    # Ein Ausreisser am Ende schiebt den Beginn nicht: drei von vier passen.
    assert tk.beginn_der_hoehe(termine([-10_000] * 3 + [-30_000]), -10_000) == 0
    # Vorzeichen zaehlt: eine Gutschrift passt nicht zu einer Zahlung.
    assert tk.beginn_der_hoehe(termine([10_000, -10_000, -10_000, -10_000]), -10_000) == 1
    # Passt keine Stelle (Betrag null, streuende Betraege): keine geltende Hoehe.
    assert tk.beginn_der_hoehe(termine([-10_000, -20_000]), 0) is None
    assert tk.beginn_der_hoehe(termine([-10_000, -20_000, -10_000, -20_000]), -15_000) is None


def test_a_back_payment_in_the_month_of_an_advance_is_an_outlier():
    """Zehn Tage nach dem Abschlag: Sie kommt zusaetzlich, der Abschlag des Monats
    bleibt ein Termin."""
    buchungen = [*_bis_stichtag(12, -10_000, tag=2), (date(2026, 5, 12), -60_000)]
    beitrag = fortschreiben(erkennen(sorted(buchungen), fixkosten=False).termine, 1,
                            stichtag=STICHTAG)
    assert [t.cents for t in beitrag.ausreisser] == [-60_000]
    assert beitrag.jahreswert == -120_000


def test_a_credit_that_swings_but_keeps_a_level_is_no_outlier_and_still_runs():
    """Ein abweichender Termin auf seinem eigenen Platz im Takt, auch der letzte,
    ist ein Termin mit anderem Betrag: Er zaehlt nicht im Rest und beendet die
    Reihe nicht."""
    betraege = [9_000, 10_000, 10_000, 18_000, 10_000, 9_500, 10_000, 20_000]
    buchungen = [(d, c) for (d, _), c in zip(_bis_stichtag(8, 0, tag=15), betraege,
                                             strict=True)]
    erkannt = erkennen(buchungen, fixkosten=False, stichtag=STICHTAG)
    assert erkannt.takt == 1
    beitrag = fortschreiben(erkannt.termine, 1, stichtag=STICHTAG)
    assert beitrag.betrag_je_termin == 10_000 and beitrag.jahreswert == 120_000
    assert beitrag.ausreisser == ()
    assert beitrag.laeuft and beitrag.letzter_termin == date(2026, 9, 15)


def test_a_final_bill_two_months_after_the_last_advance_keeps_the_series_running():
    """Der Preis aus Entscheidung 4: Die Schlussabrechnung liegt auf ihrem
    eigenen Platz, ist also ein Termin des Takts, und haelt die gekuendigte
    Reihe 1,5 Takte laenger am Laufen."""
    abschlaege = _monatlich(date(2025, 6, 2), 12, -10_000, tag=2)         # bis 05/2026
    assert abschlaege[-1][0] == date(2026, 5, 2)
    schluss = (date(2026, 7, 25), -60_000)
    stichtag = date(2026, 8, 31)
    ohne = fortschreiben(erkennen(abschlaege, fixkosten=False, stichtag=stichtag).termine,
                         1, stichtag=stichtag)
    mit = fortschreiben(erkennen([*abschlaege, schluss], fixkosten=False,
                                 stichtag=stichtag).termine, 1, stichtag=stichtag)
    assert not ohne.laeuft
    assert mit.laeuft and mit.letzter_termin == schluss[0]
    assert mit.ausreisser == () and mit.betrag_je_termin == -10_000


def test_three_instalments_in_consecutive_months_every_year_are_yearly_not_monthly():
    """Vier von fuenf Abstaenden sind einen Monat lang, aber neun Monate Luecke
    dazwischen: kein monatlicher Takt."""
    buchungen = [(date(j, m, 10), -20_000) for j in (2024, 2025) for m in (1, 2, 3)]
    assert len(termine_bilden(buchungen, 1)) == 6
    erkannt = erkennen(buchungen, fixkosten=False, stichtag=STICHTAG)
    assert erkannt.takt == 12
    assert [t.cents for t in erkannt.termine] == [-60_000, -60_000]
    # Ein einmaliges Jahr davon ist ebenso nicht monatlich.
    assert erkennen(buchungen[:3], fixkosten=False, stichtag=STICHTAG).takt == 1


def test_january_to_march_and_september_to_november_is_irregular():
    buchungen = [(date(2025, m, 5), -10_000) for m in (1, 2, 3, 9, 10, 11)]
    assert erkennen(buchungen, fixkosten=False, stichtag=STICHTAG).takt == UNREGELMAESSIG
    zwei_jahre = [(date(j, m, 5), -10_000) for j in (2025, 2026)
                  for m in (1, 2, 3, 9, 10, 11)]
    assert erkennen(zwei_jahre, fixkosten=False, stichtag=STICHTAG).takt == UNREGELMAESSIG


def test_a_gap_of_a_term_or_two_does_not_break_a_series():
    """Zwei fehlende Monate in zwoelf: elf von dreizehn Takten sind noch genug."""
    buchungen = [b for b in _bis_stichtag(13, -10_000, tag=2)
                 if b[0].month not in (3, 4) or b[0].year != 2026]
    assert len(buchungen) == 11
    assert erkennen(buchungen, fixkosten=False, stichtag=STICHTAG).takt == 1


def test_the_detection_never_returns_einmalig():
    for buchungen in ([], [(date(2026, 1, 1), -100)],
                      [(date(2026, 1, 1), -100), (date(2026, 1, 2), -100)]):
        assert erkennen(buchungen, fixkosten=False).takt not in (EINMALIG,)
        assert erkennen(buchungen, fixkosten=True).takt != EINMALIG


def test_no_bookings_is_irregular_even_for_fixed_costs():
    assert erkennen([], fixkosten=True) == tk.Erkannt(UNREGELMAESSIG, ())


def test_terms_merge_bookings_less_than_half_a_term_after_the_first():
    buchungen = [(date(2026, 1, 5), -100), (date(2026, 1, 25), -100),
                 (date(2026, 4, 5), -100)]
    assert [len(t.buchungen) for t in termine_bilden(buchungen, 3)] == [2, 1]
    assert [len(t.buchungen) for t in termine_bilden(buchungen, 1)] == [1, 1, 1]


def test_only_fixed_cadences_can_be_forwarded():
    termine = termine_bilden([(date(2026, 1, 5), -100)], 1)
    with pytest.raises(ValueError):
        fortschreiben(termine, UNREGELMAESSIG, stichtag=STICHTAG)   # type: ignore[arg-type]
    with pytest.raises(ValueError):
        fortschreiben(termine, 5, stichtag=STICHTAG)
    with pytest.raises(ValueError):
        fortschreiben((), 1, stichtag=STICHTAG)


def test_the_text_names_cadence_amount_factor_and_the_back_payment():
    buchungen = [*_bis_stichtag(12, -10_000, tag=2), (date(2026, 5, 20), -60_000)]
    beitrag = fortschreiben(erkennen(sorted(buchungen), fixkosten=False).termine, 1,
                            stichtag=STICHTAG)
    assert beitrag.text == (
        "monatlich, je Termin −100,00 € (Median der letzten 3 Termine), "
        "× 12 = −1.200,00 € im Jahr; 1 abweichender Termin zählt im Rest der Kategorie")


def test_erkennen_and_fortschreiben_touch_neither_the_ledger_nor_config(monkeypatch):
    """Reine Funktionen auf Listen: ohne Datei, ohne Datenbank dasselbe."""
    buchungen = _bis_stichtag(12, -10_000, tag=2)
    erwartet = erkennen(buchungen, fixkosten=False)
    erwartet_beitrag = fortschreiben(erwartet.termine, 1, stichtag=STICHTAG)

    def verboten(*_a, **_k):
        raise AssertionError("die Rechnung greift auf Datei oder Datenbank zu")

    with monkeypatch.context() as mp:
        for name in ("read_text", "read_bytes", "exists", "is_file", "open"):
            mp.setattr(Path, name, verboten)
        mp.setattr(builtins, "open", verboten)
        mp.setattr(sqlite3, "connect", verboten)
        assert erkennen(buchungen, fixkosten=False) == erwartet
        assert fortschreiben(erwartet.termine, 1, stichtag=STICHTAG) == erwartet_beitrag


# --------------------------------------------------------------- reihen


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE mgmt_categories (id TEXT PRIMARY KEY, kind TEXT,
                                      fixkosten INTEGER DEFAULT 0, einmalig INTEGER DEFAULT 0);
        CREATE TABLE transactions (id INTEGER PRIMARY KEY, account_id TEXT,
                                   booking_date TEXT, dedup_hash TEXT NOT NULL,
                                   counterparty_norm TEXT);
        CREATE TABLE splits (transaction_id INTEGER, mgmt_category_id TEXT,
                             amount_cents INTEGER, transfer_account_id TEXT,
                             property_id TEXT);
        INSERT INTO mgmt_categories (id, kind, fixkosten) VALUES
            ('wohnen/miete', 'expense', 1),
            ('versicherung/auto', 'expense', 1),
            ('konsum/essen', 'expense', 0),
            ('transfer/eigenkonto', 'transfer', 0);
    """)
    yield c
    c.close()


def _buche(c, tag, konto, kategorie, cents, gegenpartei):
    n = c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] + 1
    c.execute("INSERT INTO transactions VALUES (?, ?, ?, ?, ?)",
              (n, konto, tag.isoformat(), f"h{n}", gegenpartei))
    c.execute("INSERT INTO splits VALUES (?, ?, ?, NULL, NULL)", (n, kategorie, cents))


def test_a_series_is_counterparty_and_category_across_all_accounts(conn):
    for i, (tag, cents) in enumerate(_bis_stichtag(12, -90_000, tag=3)):
        _buche(conn, tag, "a" if i < 6 else "b", "wohnen/miete", cents, "hausverwaltung")
    _buche(conn, date(2026, 9, 4), "a", "konsum/essen", -2_500, "hausverwaltung")
    r = tk.reihen(conn, bis=STICHTAG)
    assert [(x.gegenpartei, x.kategorie) for x in r.reihen] == [
        ("hausverwaltung", "konsum/essen"), ("hausverwaltung", "wohnen/miete")]
    miete = r.nach_schluessel("hausverwaltung", "wohnen/miete")
    assert miete.takt == 1 and not miete.festgelegt and len(miete.teile) == 12
    assert miete.beitrag.jahreswert == -1_080_000
    assert r.nach_schluessel("hausverwaltung", "konsum/essen").takt == UNREGELMAESSIG
    assert r.nach_schluessel("hausverwaltung", "wohnen/nebenkosten") is None
    assert r.nach_schluessel("anderer", "wohnen/miete") is None


def test_parts_without_a_counterparty_belong_to_no_series(conn):
    for tag, cents in _bis_stichtag(6, -1_000, tag=3):
        _buche(conn, tag, "a", "konsum/essen", cents, None)
        _buche(conn, tag, "a", "konsum/essen", cents, "")
    assert tk.reihen(conn, bis=STICHTAG).reihen == ()


def test_transfers_are_not_series(conn):
    for tag, cents in _bis_stichtag(6, -50_000, tag=3):
        _buche(conn, tag, "a", "transfer/eigenkonto", cents, "sparkonto")
    assert tk.reihen(conn, bis=STICHTAG).reihen == ()


def test_the_window_is_24_months_up_to_the_cutoff(conn):
    """Eine Buchung im 25. Monat davor und eine nach dem Stichtag bleiben aussen."""
    _buche(conn, date(2024, 8, 15), "a", "konsum/essen", -100, "markt")
    _buche(conn, date(2024, 10, 1), "a", "konsum/essen", -100, "markt")
    _buche(conn, date(2026, 10, 2), "a", "konsum/essen", -100, "markt")
    r = tk.reihen(conn, bis=STICHTAG)
    assert r.von == date(2024, 10, 1)
    assert [t.tag for t in r.reihen[0].teile] == [date(2024, 10, 1)]


def test_a_fixed_cost_category_with_one_booking_is_yearly(conn):
    _buche(conn, date(2026, 1, 15), "a", "versicherung/auto", -60_000, "versicherer")
    _buche(conn, date(2026, 1, 15), "a", "konsum/essen", -60_000, "markt")
    r = tk.reihen(conn, bis=STICHTAG)
    assert r.nach_schluessel("versicherer", "versicherung/auto").takt == 12
    assert r.nach_schluessel("markt", "konsum/essen").takt == UNREGELMAESSIG


def test_a_decision_beats_the_detection(conn):
    for tag, cents in _bis_stichtag(12, -90_000, tag=3):
        _buche(conn, tag, "a", "wohnen/miete", cents, "hausverwaltung")
    schluessel = ("hausverwaltung", "wohnen/miete")
    drei = tk.reihen(conn, bis=STICHTAG, festgelegt={schluessel: 3}
                     ).nach_schluessel(*schluessel)
    assert drei.takt == 3 and drei.festgelegt
    # Der festgelegte Takt bildet seine Termine selbst: Buchungen im Monatsabstand
    # liegen weniger als einen halben Takt auseinander und werden paarweise ein Termin.
    assert len(drei.termine) == 6
    frei = tk.reihen(conn, bis=STICHTAG, festgelegt={schluessel: UNREGELMAESSIG}
                     ).nach_schluessel(*schluessel)
    assert frei.takt == UNREGELMAESSIG and frei.beitrag is None


def test_a_decision_can_not_make_a_whole_series_einmalig(conn):
    """Einmalig gilt fuer Buchungen, nicht fuer die Reihe."""
    with pytest.raises(ValueError):
        tk.reihen(conn, bis=STICHTAG, festgelegt={("x", "y"): EINMALIG})
    with pytest.raises(ValueError):
        tk.reihen(conn, bis=STICHTAG, festgelegt={("x", "y"): 5})


def test_a_decided_cadence_can_still_be_over(conn):
    """Der Haushalt sagt, wie oft, nicht, dass es weitergeht."""
    for tag, cents in _monatlich(date(2025, 1, 1), 6, -1_000):
        _buche(conn, tag, "a", "konsum/essen", cents, "markt")
    r = tk.reihen(conn, bis=STICHTAG, festgelegt={("markt", "konsum/essen"): 1})
    reihe = r.reihen[0]
    assert reihe.festgelegt and reihe.beitrag.laeuft is False
    assert reihe.beitrag.jahreswert == 0


# --------------------------------------- Wo ein Teil in der Hochrechnung zaehlt


def _reihe_aus(conn, kategorie="wohnen/miete", gegenpartei="hausverwaltung", **kw):
    return tk.reihen(conn, bis=STICHTAG, **kw).nach_schluessel(gegenpartei, kategorie)


def test_a_part_in_a_term_of_the_series_counts_in_the_series_not_in_the_rest(conn):
    for tag, cents in _bis_stichtag(12, -90_000, tag=3):
        _buche(conn, tag, "a", "wohnen/miete", cents, "hausverwaltung")
    reihe = _reihe_aus(conn)
    assert {reihe.einordnen(t.tag) for t in reihe.teile} == {tk.IM_TAKT}
    # Ein Tag, an dem nichts gebucht ist, gehoert zu keinem Termin: Rest.
    assert reihe.einordnen(date(2026, 9, 20)) == tk.IM_REST


def test_a_series_that_is_over_counts_nowhere_not_even_its_outlier(conn):
    for tag, cents in _monatlich(date(2025, 10, 1), 6, -90_000, tag=3):
        _buche(conn, tag, "a", "wohnen/miete", cents, "hausverwaltung")
    _buche(conn, date(2026, 2, 5), "a", "wohnen/miete", -400_000, "hausverwaltung")
    reihe = _reihe_aus(conn)
    assert reihe.beitrag.laeuft is False and reihe.beitrag.ausreisser
    assert {reihe.einordnen(t.tag) for t in reihe.teile} == {tk.NIRGENDS}


def test_the_outlier_of_a_running_series_counts_in_the_rest(conn):
    """Zwoelf Abschlaege und eine Nachzahlung neben dem letzten: Sie kommt zusaetzlich."""
    for tag, cents in _bis_stichtag(12, -100_000, tag=2):
        _buche(conn, tag, "a", "wohnen/miete", cents, "hausverwaltung")
    _buche(conn, date(2026, 9, 9), "a", "wohnen/miete", -500_000, "hausverwaltung")
    reihe = _reihe_aus(conn)
    assert reihe.beitrag.laeuft and reihe.beitrag.betrag_je_termin == -100_000
    wo = {t.tag: reihe.einordnen(t.tag) for t in reihe.teile}
    assert wo[date(2026, 9, 2)] == tk.IM_TAKT
    assert wo[date(2026, 9, 9)] == tk.IM_REST


def test_the_history_of_a_series_counts_nowhere(conn):
    """Zehn Termine zu 1.000, dann zwei zu 1.500: Die Reihe schreibt ihre neue Hoehe
    fort, und die alte ist vorbei."""
    for tag, cents in _bis_stichtag(12, -100_000, tag=2)[:10]:
        _buche(conn, tag, "a", "wohnen/miete", cents, "hausverwaltung")
    for tag, cents in _bis_stichtag(2, -150_000, tag=2):
        _buche(conn, tag, "a", "wohnen/miete", cents, "hausverwaltung")
    reihe = _reihe_aus(conn)
    assert reihe.beitrag.betrag_je_termin == -150_000 and reihe.beitrag.verlauf
    wo = {t.tag: reihe.einordnen(t.tag) for t in reihe.teile}
    assert wo[date(2025, 10, 2)] == tk.NIRGENDS
    assert wo[date(2026, 9, 2)] == tk.IM_TAKT


def test_a_series_without_a_fixed_cadence_counts_in_the_rest(conn):
    _buche(conn, date(2026, 1, 5), "a", "konsum/essen", -2_500, "markt")
    _buche(conn, date(2026, 3, 9), "a", "konsum/essen", -7_100, "markt")
    reihe = _reihe_aus(conn, "konsum/essen", "markt")
    assert reihe.takt == UNREGELMAESSIG and reihe.block is None
    assert {reihe.einordnen(t.tag) for t in reihe.teile} == {tk.IM_REST}


def test_a_series_stands_in_the_block_of_its_last_term(conn):
    """Eine Reihe, deren Teile in zwei Bloecken gemessen sind, zaehlt in dem ihres
    letzten Termins: Der Block steht an der Reihe, nicht an den Teilen."""
    for tag, cents in _bis_stichtag(12, -90_000, tag=3):
        _buche(conn, tag, "a", "wohnen/miete", cents, "hausverwaltung")
    reihe = _reihe_aus(conn)
    assert reihe.block == "fixkosten"
    assert {t.block for t in reihe.teile} == {"fixkosten"}


def test_the_index_finds_a_series_by_booking_and_category(conn):
    for tag, cents in _bis_stichtag(12, -90_000, tag=3):
        _buche(conn, tag, "a", "wohnen/miete", cents, "hausverwaltung")
    _buche(conn, date(2026, 9, 4), "a", "konsum/essen", -2_500, "hausverwaltung")
    r = tk.reihen(conn, bis=STICHTAG)
    miete = r.nach_schluessel("hausverwaltung", "wohnen/miete")
    teil = miete.teile[0]
    assert r.nach_teil(teil.dedup_hash, "wohnen/miete") is miete
    assert r.nach_teil(teil.dedup_hash, "konsum/essen") is None
    assert r.nach_teil("unbekannt", "wohnen/miete") is None


def _teile(reihe) -> list[tuple[str, str, date, int]]:
    return [(t.dedup_hash, t.kategorie, t.tag, t.cents) for t in reihe.teile]


def test_the_contribution_of_a_series_is_its_year_value_once_not_its_parts(conn):
    """Dreizehn Buchungen im Fenster, zwoelf Termine: Wer die Teile summiert, zaehlt
    dreizehn; der Beitrag zaehlt die Reihe einmal mit zwoelf."""
    buchungen = _monatlich(date(2025, 10, 1), 12, -100_000, tag=1)
    for tag, cents in [*buchungen, (date(2026, 9, 30), -100_000)]:
        _buche(conn, tag, "a", "wohnen/miete", cents, "hausverwaltung")
    r = tk.reihen(conn, bis=STICHTAG)
    reihe = r.nach_schluessel("hausverwaltung", "wohnen/miete")
    assert sum(c for *_, c in _teile(reihe)) == -1_300_000
    b = tk.beitrag_in_basis(_teile(reihe), r, von=date(2025, 10, 1), bis=STICHTAG)
    assert (b.takt_jahr, b.rest_cents, len(b.reihen)) == (-1_200_000, 0, 1)
    assert b.im_jahr(12) == -1_200_000


def test_the_contribution_counts_the_rest_in_the_window_and_the_outlier_there(conn):
    for tag, cents in _bis_stichtag(12, -10_000, tag=2):
        _buche(conn, tag, "a", "konsum/essen", cents, "abo")
    _buche(conn, date(2026, 3, 12), "a", "konsum/essen", -30_000, "abo")
    r = tk.reihen(conn, bis=STICHTAG)
    reihe = r.nach_schluessel("abo", "konsum/essen")
    b = tk.beitrag_in_basis(_teile(reihe), r, von=date(2025, 10, 1), bis=STICHTAG)
    assert (b.takt_jahr, b.rest_cents) == (-120_000, -30_000)
    # Aufs Jahr: bei zwoelf Monaten die Summe, bei sechs das Doppelte des Rests.
    assert b.im_jahr(12) == -150_000
    assert b.je_monat(12) == pytest.approx(-12_500)
    assert tk.beitrag_in_basis(_teile(reihe), r, von=date(2026, 4, 1), bis=STICHTAG
                               ).rest_cents == 0


def test_the_contribution_names_its_series_largest_first_whatever_the_order_of_the_parts(conn):
    """Der Rechenweg einer Planzeile nennt Namen, die der Haushalt aendern kann: gross vor
    klein, nicht in der Reihenfolge, in der die Abfrage die Teile liefert."""
    for tag, cents in _bis_stichtag(12, -1_000, tag=2):
        _buche(conn, tag, "a", "konsum/essen", cents, "aaa")
    for tag, cents in _bis_stichtag(12, -9_000, tag=4):
        _buche(conn, tag, "a", "konsum/essen", cents, "zzz")
    r = tk.reihen(conn, bis=STICHTAG)
    teile = [t for reihe in r.reihen for t in _teile(reihe)]
    for reihenfolge in (teile, teile[::-1]):
        b = tk.beitrag_in_basis(reihenfolge, r, von=date(2025, 10, 1), bis=STICHTAG)
        assert [x.gegenpartei for x in b.reihen] == ["zzz", "aaa"]


def test_a_running_series_counts_even_when_its_term_lies_before_the_window(conn):
    """Die Basis schreibt eine laufende Reihe fort, auch wenn ihr Termin vor dem
    Messfenster liegt: Ein Wegfall nimmt sie dann auch ab."""
    _buche(conn, date(2025, 8, 15), "a", "versicherung/auto", -60_000, "versicherer")
    r = tk.reihen(conn, bis=STICHTAG)
    reihe = r.nach_schluessel("versicherer", "versicherung/auto")
    assert reihe.takt == 12 and reihe.beitrag.laeuft
    b = tk.beitrag_in_basis(_teile(reihe), r, von=date(2025, 10, 1), bis=STICHTAG)
    assert (b.takt_jahr, b.rest_cents) == (-60_000, 0)


def test_a_series_that_is_over_contributes_nothing(conn):
    for tag, cents in _monatlich(date(2025, 1, 1), 6, -90_000, tag=3):
        _buche(conn, tag, "a", "wohnen/miete", cents, "hausverwaltung")
    r = tk.reihen(conn, bis=STICHTAG)
    reihe = r.nach_schluessel("hausverwaltung", "wohnen/miete")
    b = tk.beitrag_in_basis(_teile(reihe), r, von=date(2025, 10, 1), bis=STICHTAG)
    assert (b.takt_jahr, b.rest_cents, b.reihen) == (0, 0, ())


def test_a_part_that_belongs_to_no_series_counts_in_the_rest(conn):
    _buche(conn, date(2026, 3, 3), "a", "konsum/essen", -2_500, "")
    r = tk.reihen(conn, bis=STICHTAG)
    b = tk.beitrag_in_basis([("h1", "konsum/essen", date(2026, 3, 3), -2_500)], r,
                            von=date(2025, 10, 1), bis=STICHTAG)
    assert (b.takt_jahr, b.rest_cents) == (0, -2_500)


def test_the_bookings_a_measurement_does_not_see_form_no_term(conn):
    """`ausschluss.hashes`: eine einmalige Planzeile bleibt aus der Messung und
    bildet auch keinen Termin."""
    for i, (tag, cents) in enumerate(_bis_stichtag(12, -90_000, tag=3)):
        _buche(conn, tag, "a", "wohnen/miete", cents, "hausverwaltung")
        if i == 11:
            _buche(conn, tag + timedelta(days=1), "a", "wohnen/miete", -300_000,
                   "hausverwaltung")
    kennung = conn.execute("SELECT dedup_hash FROM transactions "
                           "ORDER BY id DESC LIMIT 1").fetchone()[0]
    mit = _reihe_aus(conn)
    ohne = _reihe_aus(conn, ausschluss=Ausschluss(hashes=frozenset({kennung})))
    assert len(mit.termine) == len(ohne.termine) + 1
    assert kennung not in {t.dedup_hash for t in ohne.teile}


# ------------------------------------------------- Schreibweisen zusammenfuehren


def _in_zwei_schreibweisen(conn) -> None:
    """Zwoelf Mieten, die ersten sechs unter einer Schreibweise, die uebrigen unter einer
    anderen."""
    for i, (tag, cents) in enumerate(_bis_stichtag(12, -90_000, tag=3)):
        name = "verwaltung alt" if i < 6 else "verwaltung neu"
        _buche(conn, tag, "a", "wohnen/miete", cents, name)


def test_a_chain_of_spellings_points_at_the_last_and_a_circle_is_refused():
    assert tk.zusammen_aufloesen({"a": "b", "b": "c", "x": "y"}) == {
        "a": "c", "b": "c", "x": "y"}
    assert tk.zusammen_aufloesen({}) == {}
    with pytest.raises(ValueError, match="Kreis"):
        tk.zusammen_aufloesen({"a": "b", "b": "a"})
    with pytest.raises(ValueError, match="Kreis"):
        tk.zusammen_aufloesen({"a": "b", "b": "c", "c": "a"})


def test_two_spellings_of_six_months_each_are_one_monthly_series_of_twelve_terms(conn):
    """Derselbe Zahler, im Hauptbuch unter zwei Schreibweisen, je ein halbes Jahr
    hintereinander: Ohne Zusammenfuehren ist die alte Reihe beendet und die neue
    sechs Termine kurz; danach ist es eine laufende Reihe mit zwoelf Terminen, die nach
    der Gegenpartei heisst, auf die sie zeigt."""
    _in_zwei_schreibweisen(conn)
    getrennt = tk.reihen(conn, bis=STICHTAG)
    alt = getrennt.nach_schluessel("verwaltung alt", "wohnen/miete")
    assert (len(alt.teile), alt.beitrag.laeuft) == (6, False)
    neu = getrennt.nach_schluessel("verwaltung neu", "wohnen/miete")
    assert neu.beitrag.jahreswert == -1_080_000

    r = tk.reihen(conn, bis=STICHTAG, zusammen={"verwaltung alt": "verwaltung neu"})
    [miete] = r.reihen
    assert (miete.gegenpartei, miete.takt, len(miete.termine), len(miete.teile)) == (
        "verwaltung neu", 1, 12, 12)
    assert miete.beitrag.laeuft and miete.beitrag.jahreswert == -1_080_000
    assert miete.schreibweisen == ("verwaltung alt",)
    assert neu.schreibweisen == ()


def test_a_payment_in_two_spellings_a_year_apart_counts_once_not_twice(conn):
    """Zwei Jahreszahlungen unter zwei Schreibweisen laufen beide anderthalb Jahre und
    zaehlten doppelt; als eine Reihe sind es zwei Termine im Abstand eines Jahres."""
    _buche(conn, date(2025, 7, 24), "a", "versicherung/auto", -7_200, "steuer alt")
    _buche(conn, date(2026, 7, 24), "a", "versicherung/auto", -7_200, "steuer neu")
    getrennt = tk.reihen(conn, bis=STICHTAG)
    assert sum(r.beitrag.jahreswert for r in getrennt.reihen) == -14_400
    zusammen = tk.reihen(conn, bis=STICHTAG, zusammen={"steuer alt": "steuer neu"})
    [steuer] = zusammen.reihen
    assert (steuer.takt, len(steuer.termine), steuer.beitrag.jahreswert) == (12, 2, -7_200)


def test_a_part_finds_its_series_under_the_spelling_its_booking_carries(conn):
    """Die Hochrechnung fragt mit der Gegenpartei des Teils; eine zusammengefuehrte
    Schreibweise darf dabei nicht ins Leere laufen, sonst zaehlte der Teil im Rest."""
    from finctl.forecast import messung

    _in_zwei_schreibweisen(conn)
    r = tk.reihen(conn, bis=STICHTAG, zusammen={"verwaltung alt": "verwaltung neu"})
    assert r.nach_schluessel("verwaltung alt", "wohnen/miete") is r.reihen[0]
    teile = messung.teile(conn, von=r.von, bis=STICHTAG, je_block=True)
    assert {tk.reihe_des_teils(r, t) for t in teile} == {r.reihen[0]}
    assert all(r.reihen[0].einordnen(t.tag) == tk.IM_TAKT for t in teile)


def test_the_series_a_merge_leaves_out_of_a_booking_is_recognised_anew_with_its_spellings(conn):
    """Ein Wegfall nimmt Buchungen heraus: Was die Reihe danach noch traegt, bleibt unter
    ihrem Namen, mit den Schreibweisen, die ihr geblieben sind."""
    _in_zwei_schreibweisen(conn)
    kennungen = [f"h{i + 1}" for i in range(12)]
    r = tk.reihen(conn, bis=STICHTAG, zusammen={"verwaltung alt": "verwaltung neu"})
    ohne = r.ohne_buchungen(kennungen[6:])
    [miete] = ohne.reihen
    assert (miete.gegenpartei, len(miete.teile), miete.schreibweisen) == (
        "verwaltung neu", 6, ("verwaltung alt",))


def test_merging_changes_nothing_without_an_entry(conn):
    for tag, cents in _bis_stichtag(12, -90_000, tag=3):
        _buche(conn, tag, "a", "wohnen/miete", cents, "verwaltung")
    assert tk.reihen(conn, bis=STICHTAG, zusammen={}) == tk.reihen(conn, bis=STICHTAG)
    assert tk.reihen(conn, bis=STICHTAG, zusammen={"unbekannt": "verwaltung"}) == tk.reihen(
        conn, bis=STICHTAG)


def test_takt_names():
    assert [tk.takt_name(t) for t in (1, 2, 3, 6, 12, EINMALIG, UNREGELMAESSIG)] == [
        "monatlich", "alle 2 Monate", "alle 3 Monate", "alle 6 Monate", "jährlich",
        "einmalig", "unregelmäßig"]


# ------------------------------------------------------------------- CLI


def test_the_reihen_command_only_reads_and_lists_fixed_series():
    """Auf den Daten des Testlaufs: lesen, nichts schreiben; `--alle` zeigt dazu
    die unregelmaessigen, der Rest ist gleich."""
    import json

    from typer.testing import CliRunner

    from finctl.cli import app

    fest = CliRunner().invoke(app, ["reihen", "--json"])
    assert fest.exit_code == 0, fest.output
    alle = CliRunner().invoke(app, ["reihen", "--alle", "--json"])
    assert alle.exit_code == 0, alle.output
    fest, alle = json.loads(fest.output), json.loads(alle.output)
    assert all(isinstance(z["takt"], int) for z in fest["reihen"])
    assert [z for z in alle["reihen"] if isinstance(z["takt"], int)] == fest["reihen"]
    assert all(z["takt"] == UNREGELMAESSIG for z in alle["reihen"]
               if not isinstance(z["takt"], int))
    text = CliRunner().invoke(app, ["reihen"])
    assert text.exit_code == 0 and "mit festem Takt" in text.output
