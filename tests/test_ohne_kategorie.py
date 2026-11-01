"""Teile ohne Kategorie im Monatsmodell heissen „ohne Kategorie“ (Schritt 5b, E.2e).

Die Jahresrechnung zaehlt sie unter dem leeren Schluessel, das Monatsmodell jetzt auch.
Der Posten braucht dafuer einen Namen, und den gibt `_anzeigenamen` an einer einzigen
Stelle. Alles hier ist erfunden und rund.
"""

from types import SimpleNamespace

from finctl.forecast import konten as ops


def test_a_part_without_category_is_named_ohne_kategorie():
    """Ein Monat mit einem Teil ohne Kategorie und einem Posten mit Namen: der Posten ohne
    Kategorie heisst „ohne Kategorie“, der andere bleibt, wie er ist."""
    rows = [SimpleNamespace(detail={"": -4_000, "wohnen": -90_000})]
    namen = ops._anzeigenamen(None, rows)
    assert namen[""] == "ohne Kategorie"
    assert "wohnen" not in namen
