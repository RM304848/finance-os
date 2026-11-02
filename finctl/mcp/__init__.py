"""Der MCP-Zugang: ein Modell liest ueber die Seiten und schlaegt vor (ADR 0002).

`finctl mcp` spricht das Model Context Protocol ueber stdin/stdout. Es oeffnet keinen
Port und braucht keine Bibliothek: das Protokoll ist JSON-RPC, Zeile fuer Zeile.

* `protokoll.py`: Handshake, Liste, Aufruf. Kennt keine Finanzen.
* `werkzeuge.py`: was ein Modell lesen darf (Funktionen der Seiten, nie SQL) und
  `vorschlagen`, das nur nach `data/vorschlaege/` schreibt.
"""

from finctl.mcp.protokoll import laufen

__all__ = ["laufen"]
