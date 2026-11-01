"""Die CSV-Exporte der Sparkasse: CSV-CAMT V2, CSV-CAMT V8 und CSV-MT940.

Die Dateien unter tests/beispiele/banken/ sind erfunden (Namen, Betraege, die
Beispiel-IBAN der Bankdokumentation), aber im Aufbau echter Exporte gebaut:
ISO-8859-1, CRLF, jedes Feld in Anfuehrungszeichen, Datum `TT.MM.JJ`, Betraege
ohne Tausenderpunkt, neueste Zeile zuerst, vorgemerkte Umsaetze dazwischen.
Der Aufbau stammt aus oeffentlich geposteten Exporten, nicht aus einem eigenen
-- ob die Sparkasse ihn so liefert, zeigt erst ein echter Export.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from finctl.ingest.importer import detect, extract_pages, import_statement, load_parser, reconcile
from finctl.ledger.db import connect, init_db, statement_chain_gaps

BEISPIELE = Path("tests/beispiele/banken")
KONTO = "DE89370400440532013000"

#: Datei -> erwartetes Profil
DATEIEN = {
    "sparkasse_camt_v2.csv": "sparkasse_csv",
    "sparkasse_camt_v8.csv": "sparkasse_csv",
    "sparkasse_mt940_csv.csv": "sparkasse_mt940_csv",
}


def _lesen(name: str, pfad: Path | None = None):
    pfad = pfad or BEISPIELE / name
    seiten = extract_pages(pfad)
    parser = detect(seiten, pfad)
    assert parser is not None, name
    return parser, parser.parse(seiten, pfad)


@pytest.mark.parametrize("name", sorted(DATEIEN))
def test_each_export_is_recognised_from_the_file_alone(name):
    parser, _ = _lesen(name)
    assert parser.profile_id == DATEIEN[name]


@pytest.mark.parametrize("name", sorted(DATEIEN))
def test_the_own_account_is_the_orderer_not_the_counterparty(name):
    _, ergebnis = _lesen(name)
    assert ergebnis.header.account_hint == KONTO
    assert {t.counterparty_iban for t in ergebnis.transactions} == {"DE02100100100006820101"}


@pytest.mark.parametrize("name", sorted(DATEIEN))
def test_pending_bookings_are_dropped_and_said_so(name):
    _, ergebnis = _lesen(name)
    assert "2026-09-30" not in {t.booking_date for t in ergebnis.transactions}
    assert not any(t.amount_cents == -1250 for t in ergebnis.transactions)
    assert any("vorgemerkt" in w for w in ergebnis.warnings)


@pytest.mark.parametrize("name", sorted(DATEIEN))
def test_there_is_no_balance_and_the_import_says_so(name):
    _, ergebnis = _lesen(name)
    assert any("keinen Saldo" in w for w in ergebnis.warnings)
    assert reconcile(ergebnis).ok


def test_camt_v2_reads_every_booked_row_with_amounts_dates_and_texts():
    _, ergebnis = _lesen("sparkasse_camt_v2.csv")
    zeilen = [(t.booking_date, t.value_date, t.amount_cents, t.counterparty, t.purpose)
              for t in ergebnis.transactions]
    assert zeilen == [
        ("2026-09-02", "2026-09-01", 120000, "Techniker Beispiel Kasse", "Erstattung Zahnarzt"),
        ("2026-09-10", "2026-09-10", -5350, "Fit & Fun Öhringen", "Fitness September"),
        ("2026-09-15", "2026-09-15", -150000, "Hausverwaltung Größle",
         'Miete Oktober "Wohnung 3"'),
        ("2026-09-28", "2026-09-28", -8500, "Stadtwerke Müllheim", "Abschlag Strom September"),
        ("2026-09-29", "2026-09-29", 240000, "Süd-Äpfel Beispiel GmbH", "Gehalt September"),
    ]
    kopf = ergebnis.header
    assert (kopf.period_start, kopf.period_end) == ("2026-09-02", "2026-09-29")


def test_camt_v8_reads_the_newer_booking_texts_and_a_later_value_date():
    _, ergebnis = _lesen("sparkasse_camt_v8.csv")
    assert [t.amount_cents for t in ergebnis.transactions] == [-150000, 240000, -595, -8500, 3500]
    lastschrift = next(t for t in ergebnis.transactions if t.amount_cents == -8500)
    assert (lastschrift.booking_date, lastschrift.value_date) == ("2026-09-28", "2026-09-30")
    assert {t.tx_type for t in ergebnis.transactions} == {
        "ONLINE-UEBERWEISUNG", "GUTSCHR. UEBERWEISUNG", "BUCHUNG", "FOLGELASTSCHRIFT",
        "ECHTZEIT-GUTSCHRIFT"}
    assert "Jörg Beispiel" in {t.counterparty for t in ergebnis.transactions}


def test_references_reach_the_rules_through_the_search_text():
    """Mandat, Glaeubiger-ID und End-to-End-Referenz stehen in eigenen Spalten;
    Regeln erkennen manche Vertraege nur an ihnen."""
    _, ergebnis = _lesen("sparkasse_camt_v2.csv")
    lastschrift = next(t for t in ergebnis.transactions if t.amount_cents == -8500)
    assert "Mandatsreferenz: M-2026-001" in lastschrift.raw_text
    assert "Glaeubiger ID: DE98ZZZ09999999999" in lastschrift.raw_text
    assert "E2E-0001" in lastschrift.raw_text
    assert "M-2026-001" not in (lastschrift.purpose or "")


def test_a_returned_debit_keeps_the_original_amount_and_the_fee_for_the_rules():
    _, ergebnis = _lesen("sparkasse_camt_v2.csv")
    rueck = next(t for t in ergebnis.transactions if t.tx_type == "RUECKLASTSCHRIFT")
    assert rueck.amount_cents == -5350
    assert "Ursprungsbetrag: 50,00" in rueck.raw_text and "Ruecklastschrift: 3,50" in rueck.raw_text


def test_mt940_csv_takes_the_purpose_from_behind_its_tag_and_keeps_the_rest_for_the_rules():
    _, ergebnis = _lesen("sparkasse_mt940_csv.csv")
    assert [(t.amount_cents, t.purpose) for t in ergebnis.transactions] == [
        (120000, "Erstattung Zahnarzt"), (-150000, "Miete Oktober Wohnung 3"),
        (-8500, "Abschlag Strom September"), (240000, "Gehalt September")]
    lastschrift = next(t for t in ergebnis.transactions if t.amount_cents == -8500)
    assert "MREF+M-2026-001" in lastschrift.raw_text
    assert "CRED+DE98ZZZ09999999999" in lastschrift.raw_text


def test_a_purpose_without_tags_stays_as_it_is():
    from finctl.ingest.csvbank import _verwendungszweck

    assert _verwendungszweck("Miete Oktober") == "Miete Oktober"
    assert _verwendungszweck("EREF+x1CRED+DE0SVWZ+Miete  Oktober ") == "Miete  Oktober"
    assert _verwendungszweck("SVWZ+Miete ABWA+Vermieter") == "Miete"


@pytest.mark.parametrize("kodierung", ["utf-8", "utf-8-sig", "cp1252", "iso-8859-1"])
def test_umlauts_survive_each_encoding_a_download_may_have(tmp_path, kodierung):
    """Die Sparkasse schreibt ISO-8859-1; ein Editor oder eine Tabellenkalkulation
    macht daraus gern UTF-8, mit oder ohne Markierung am Dateianfang."""
    text = (BEISPIELE / "sparkasse_camt_v2.csv").read_bytes().decode("iso-8859-1")
    pfad = tmp_path / "umsaetze.csv"
    pfad.write_bytes(text.encode(kodierung))
    _, ergebnis = _lesen("", pfad)
    assert "Süd-Äpfel Beispiel GmbH" in {t.counterparty for t in ergebnis.transactions}
    assert "Fit & Fun Öhringen" in {t.counterparty for t in ergebnis.transactions}


def test_a_four_digit_year_and_an_uppercase_extension_do_not_matter(tmp_path):
    text = (BEISPIELE / "sparkasse_camt_v2.csv").read_bytes().decode("iso-8859-1")
    pfad = tmp_path / "20261001-umsatz-camt52v2.CSV"
    pfad.write_bytes(text.replace(".09.26", ".09.2026").encode("iso-8859-1"))
    _, ergebnis = _lesen("", pfad)
    assert ergebnis.transactions[0].booking_date == "2026-09-02"


def test_an_export_of_several_accounts_is_refused(tmp_path):
    """Sonst landeten die Umsaetze des zweiten Kontos im ersten."""
    text = (BEISPIELE / "sparkasse_camt_v2.csv").read_bytes().decode("iso-8859-1")
    pfad = tmp_path / "zwei.csv"
    pfad.write_bytes(text.replace('"DE89370400440532013000";"29.09.26"',
                                  '"DE02100100100006820101";"29.09.26"').encode("iso-8859-1"))
    seiten = extract_pages(pfad)
    with pytest.raises(ValueError, match="2 Konten"):
        detect(seiten, pfad).parse(seiten, pfad)


def test_a_file_with_only_pending_bookings_says_so(tmp_path):
    text = (BEISPIELE / "sparkasse_camt_v2.csv").read_bytes().decode("iso-8859-1")
    kopf, *zeilen = text.splitlines()
    pfad = tmp_path / "vorgemerkt.csv"
    pfad.write_bytes("\r\n".join([kopf, *(z for z in zeilen if "vorgemerkt" in z)])
                     .encode("iso-8859-1"))
    seiten = extract_pages(pfad)
    with pytest.raises(ValueError, match="keine gebuchten Umsätze"):
        detect(seiten, pfad).parse(seiten, pfad)


def test_the_profiles_name_their_source_honestly():
    for pid in ("sparkasse_csv", "sparkasse_mt940_csv"):
        quelle = load_parser(pid).profil.quelle
        assert "nicht an einem eigenen Export geprueft" in quelle, pid


# ------------------------------------------------------------- Ende zu Ende

def _konto(tmp_path, profil: str):
    db = tmp_path / "ledger.db"
    init_db(db)
    conn = connect(db)
    conn.execute(
        "INSERT INTO accounts (id, display_name, institution, account_type,"
        " ingest_mode, parser_profile) VALUES (?,?,?,?,?,?)",
        ("giro", "Giro", "Sparkasse", "giro", "parsed", profil))
    return conn


def _verschoben(tmp_path, name: str, monat: str) -> Path:
    """Dieselbe Datei fuer einen anderen Monat -- ein zweiter, eigener Export."""
    roh = (BEISPIELE / "sparkasse_camt_v2.csv").read_bytes()
    pfad = tmp_path / name
    pfad.write_bytes(roh.replace(b".09.26", f".{monat}.26".encode()))
    return pfad


def test_two_exports_without_a_balance_do_not_show_a_gap(tmp_path):
    """Ohne Saldenspalte steht `0` als Anfang und die Summe als Ende. Zwei
    solche Auszuege schliessen nie aneinander an; der Monatsabschluss meldete
    trotzdem eine Luecke ("Vermutlich fehlt ein Auszug")."""
    conn = _konto(tmp_path, "sparkasse_csv")
    for name, monat in (("sep.csv", "09"), ("okt.csv", "10")):
        ausgang = import_statement(conn, _verschoben(tmp_path, name, monat), "giro")
        assert ausgang.status == "imported", ausgang.message
        assert ausgang.transactions == 5
    assert statement_chain_gaps(conn) == []


def test_a_second_import_adds_nothing_and_an_overlapping_one_only_what_is_new(tmp_path):
    conn = _konto(tmp_path, "sparkasse_csv")
    sep = _verschoben(tmp_path, "sep.csv", "09")
    assert import_statement(conn, sep, "giro").transactions == 5
    assert import_statement(conn, sep, "giro").status == "skipped"

    # Ein Export mit mehr Zeitraum: dieselben fuenf Umsaetze plus einer am 30.09.
    roh = sep.read_bytes().split(b"\r\n")
    neu = roh[2].replace(b"29.09.26", b"30.09.26").replace(b"2400,00", b"100,00")
    ueber = tmp_path / "ueber.csv"
    ueber.write_bytes(b"\r\n".join([roh[0], neu, *roh[1:]]))
    assert import_statement(conn, ueber, "giro").status == "imported"
    assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 6
    assert statement_chain_gaps(conn) == []


def test_an_account_set_up_with_one_variant_still_reads_the_other(tmp_path):
    """Wer erst CSV-CAMT und dann CSV-MT940 exportiert, bekommt keine halb gelesene Datei:
    das Profil des Kontos passt nicht, die Erkennung nimmt das richtige."""
    conn = _konto(tmp_path, "sparkasse_csv")
    ausgang = import_statement(conn, BEISPIELE / "sparkasse_mt940_csv.csv", "giro")
    assert (ausgang.status, ausgang.profile) == ("imported", "sparkasse_mt940_csv")
    assert conn.execute("SELECT purpose FROM transactions WHERE amount_cents = -8500"
                        ).fetchone()[0] == "Abschlag Strom September"


def test_a_statement_with_a_balance_still_shows_a_real_gap(tmp_path):
    """Die Ausnahme gilt nur dem Export ohne Saldo."""
    conn = _konto(tmp_path, "sparkasse_csv")
    for monat, anfang, ende in (("a", 0, 1000), ("b", 5000, 6000)):
        conn.execute(
            "INSERT INTO statements (account_id, source_path, source_name, file_sha256,"
            " period_start, period_end, balance_start_cents, balance_end_cents,"
            " parser_profile, parser_version, status, imported_at)"
            " VALUES ('giro', ?, ?, ?, ?, ?, ?, ?, 'dkb_giro', '1', 'imported', 'x')",
            (monat, monat, monat, f"2026-0{1 if monat == 'a' else 3}-01",
             f"2026-0{1 if monat == 'a' else 3}-28", anfang, ende))
    assert len(statement_chain_gaps(conn)) == 1
