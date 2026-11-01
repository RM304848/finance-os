"""Eine Teilzeit im Horizont von /konten muss dort gebucht werden (Schritt 5b, E.3/E.8).

Das Monatsmodell rechnet keine Teilzeit (`szenarien.NUR_JAHRESRECHNUNG`): Es bucht das volle
Gehalt. Das ist richtig, solange sie hinter den sechzig Monaten beginnt. Rueckt sie hinein,
schlaegt dieser Test an. Er liest die Teilzeit aus `config/` und nennt kein Jahr.
"""

from __future__ import annotations

from finctl import assumptions as ann
from finctl.forecast import jahre as jm
from finctl.forecast import konten as ops
from finctl.forecast.engine import add_months
from finctl.forecast.stichtag import stichtag
from finctl.ledger.db import connect


def test_no_teilzeit_begins_inside_the_horizon_of_konten():
    starts = {line.start for s in jm._szenarien_laden() for line in s.lines
              if line.kind == "teilzeit" and line.start}
    if ann.teilzeit_ab():
        starts.add(ann.teilzeit_ab())
    conn = connect()
    try:
        erster = add_months(stichtag(conn).replace(day=1), 1)
    finally:
        conn.close()
    letzter = add_months(erster, ops.HORIZON_LONG - 1)
    drin = sorted(d for d in starts if d <= letzter)
    assert not drin, (
        f"Eine Teilzeit beginnt {drin[0]:%Y-%m}, innerhalb der {ops.HORIZON_LONG} Monate von "
        f"/konten (bis {letzter:%Y-%m}). Das Monatsmodell rechnet sie nicht: Sie muss dort als "
        "Abzug vom Gehalt gebucht werden (szenarien.NUR_JAHRESRECHNUNG).")
