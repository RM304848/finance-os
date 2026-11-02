"""Ein erfundener Server, der sich wie eine Schnittstelle fuer ein Modell meldet.

Er hoert nur auf 127.0.0.1 (Port vom System), merkt, was bei ihm ankommt, und antwortet in
der Form "chat completions". Die Tests der Anbindung (`test_anbindung.py`, `test_browser.py`)
brauchen ihn, weil ausserhalb dieses Rechners nie verbunden wird.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SCHLUESSEL = "geheim-Zq81xK7vP3"
ANTWORT = "ZUSAMMENFASSUNG: Nichts fällt auf.\nAUFFÄLLIG: Annahmen ; Alles wie gewohnt."


class Server:
    """Ein Server auf 127.0.0.1, der nur merkt, was bei ihm ankommt."""

    def __init__(self):
        self.anfragen: list[dict] = []
        self.modus = "ok"
        self.wartezeit = 0.0
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                laenge = int(self.headers.get("Content-Length") or 0)
                roh = self.rfile.read(laenge)
                server.anfragen.append({"pfad": self.path, "kopf": dict(self.headers),
                                        "koerper": json.loads(roh.decode("utf-8"))})
                if server.wartezeit:
                    time.sleep(server.wartezeit)
                modus = server.modus
                if modus in ("401", "404", "500"):
                    # Wie mancher Dienst: der Koerper wiederholt den Anfang des Schluessels.
                    antwort = json.dumps({"error": f"bad key {SCHLUESSEL[:8]}…"}).encode()
                    return self._senden(int(modus), antwort)
                if modus == "weiter":
                    self.send_response(302)
                    self.send_header("Location", f"http://127.0.0.1:{server.zweit_port}/x")
                    self.end_headers()
                    return None
                if modus == "form":
                    return self._senden(200, b'{"hallo": "welt"}')
                antwort = json.dumps({"choices": [{"message": {"role": "assistant",
                                                               "content": ANTWORT}}]})
                return self._senden(200, antwort.encode("utf-8"))

            def _senden(self, status, antwort):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(antwort)))
                self.end_headers()
                self.wfile.write(antwort)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.zweit_port = 0
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def adresse(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def schliessen(self):
        self.httpd.shutdown()
        self.httpd.server_close()
