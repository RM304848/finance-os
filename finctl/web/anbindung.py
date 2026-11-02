"""Die Anbindung an eine Schnittstelle fuer ein Modell (ADR 0002, dritter Weg).

DIES IST DIE EINZIGE DATEI DER APP, DIE EIN NETZ ANSPRICHT. `tests/test_netz.py`
sucht in allen Modulen nach `urllib.request`, `http.client` und `socket` und
laesst sie nur hier zu (und in `starter.py`, das nur den eigenen Rechner fragt).

AUSGESCHALTET IST DER STANDARD. Ohne Eintrag in `config/anbindung.yaml` gibt es
keinen Knopf zum Senden und keinen Versuch, eine Verbindung aufzubauen. Die
Einrichtung selbst verbindet sich nie: Es gibt keine "Verbindung testen"-Taste,
denn jeder Test waere ein Senden.

WAS HINAUSGEHT, ist der Text einer Vorlage (`web/vorlagen.py`), nichts sonst --
und nur, nachdem die Seite ihn samt Ziel gezeigt hat. Das Zeigen erzeugt eine
FREIGABE: der gezeigte Text, die Adresse und das Modell, an ein Stichwort
gebunden, das genau einmal gilt. Gesendet wird der Text der Freigabe, nie ein
Text, den der Browser nachreicht, und jedes Mal braucht es eine neue.

DER SCHLUESSEL steht in `pfade.SCHLUESSEL_PATH`, nicht in `config/`, nur fuer den
Nutzer lesbar. Er geht nur als Kopfzeile an die eingetragene Adresse. Er steht in
keiner Antwort der Seiten, in keiner Meldung und in keinem Log; auch der Koerper
einer Fehlerantwort der Schnittstelle wird nicht weitergegeben, weil manche
Dienste darin den Anfang des Schluessels wiederholen.

KEINE WEITERLEITUNG: ein Server, der auf einen anderen Rechner verweist, bekaeme
sonst Text und Schluessel, die die Seite nie gezeigt hat.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

from finctl.dateien import yaml_lesen, yaml_schreiben
from finctl.pfade import CONFIG_DIR, SCHLUESSEL_PATH

PFAD = CONFIG_DIR / "anbindung.yaml"

#: Adressen, die den eigenen Rechner meinen. Dorthin darf die Verbindung auch
#: ohne Verschluesselung gehen, und die Seite sagt, dass nichts hinausgeht.
LOKAL = ("localhost", "127.0.0.1", "::1")

#: Das Ende der Adresse bei der verbreiteten Form "chat completions". Wer nur
#: die Wurzel einer Schnittstelle (`…/v1`) einträgt, bekommt es angehaengt.
ENDE = "/chat/completions"

#: Wie lange die App auf eine Antwort wartet. Ein lokales Modell braucht mitunter Minuten.
ZEIT = 120

#: Mehr liest die App von einer Antwort nicht.
MAX_ANTWORT = 1_000_000

#: Wie lange ein gezeigter Text gesendet werden darf, ohne dass er neu gezeigt wird.
FREIGABE_SEKUNDEN = 600


class AnbindungError(Exception):
    """Ein Satz, den der Haushalt lesen kann. Nie mit dem Schluessel."""

    def __init__(self, text: str, status: int = 502):
        super().__init__(text)
        self.status = status


@dataclass(frozen=True, slots=True)
class Anbindung:
    adresse: str
    modell: str

    @property
    def host(self) -> str:
        return urlsplit(self.adresse).hostname or ""

    @property
    def lokal(self) -> bool:
        return self.host in LOKAL


# ------------------------------------------------------------------ Eintrag

def adresse_pruefen(text: object) -> str:
    """Die Adresse in ihrer endgueltigen Form. `ValueError` sagt, was nicht stimmt."""
    try:
        teile = urlsplit(str(text or "").strip())
        _ = teile.port          # eine unlesbare Portnummer wirft hier
    except ValueError:
        teile = urlsplit("")
    if teile.scheme not in ("http", "https") or not teile.hostname:
        raise ValueError("Die Adresse beginnt mit https:// (oder http:// für diesen Rechner), "
                         "zum Beispiel https://host/v1.")
    if teile.username or teile.password:
        raise ValueError("Die Adresse enthält keinen Namen und kein Passwort. "
                         "Den Schlüssel trägst du im eigenen Feld ein.")
    if teile.query or teile.fragment:
        raise ValueError("Die Adresse endet beim Pfad, ohne ? und ohne #.")
    if teile.scheme == "http" and teile.hostname not in LOKAL:
        raise ValueError("Ohne https geht es nur an diesen Rechner "
                         "(localhost, 127.0.0.1 oder ::1).")
    pfad = teile.path.rstrip("/")
    if not pfad.endswith(ENDE):
        pfad += ENDE
    ziel = f"[{teile.hostname}]" if ":" in teile.hostname else teile.hostname
    if teile.port:
        ziel += f":{teile.port}"
    return f"{teile.scheme}://{ziel}{pfad}"


def laden() -> Anbindung | None:
    """Die eingetragene Anbindung. `None` heisst: ausgeschaltet."""
    try:
        spec = yaml_lesen(PFAD)
    except OSError:
        return None
    if not isinstance(spec, dict):
        return None
    adresse, modell = str(spec.get("adresse") or "").strip(), str(spec.get("modell") or "").strip()
    return Anbindung(adresse, modell) if adresse and modell else None


def speichern(adresse: object, modell: object) -> Anbindung:
    """Adresse und Modell in `config/anbindung.yaml`. Der Schluessel gehoert nicht dorthin."""
    name = " ".join(str(modell or "").split())
    if not name:
        raise ValueError("Das Modell fehlt.")
    a = Anbindung(adresse_pruefen(adresse), name)
    PFAD.parent.mkdir(parents=True, exist_ok=True)
    yaml_schreiben(PFAD, {"adresse": a.adresse, "modell": a.modell})
    return a


def entfernen() -> None:
    """Zurueck auf ausgeschaltet: Eintrag und Schluessel weg."""
    from finctl.dateien import vergessen

    PFAD.unlink(missing_ok=True)
    vergessen(PFAD)
    schluessel_entfernen()
    _FREIGABEN.clear()


# ----------------------------------------------------------------- Schluessel

_SCHLUESSEL = re.compile(r"[\x21-\x7e]{1,512}")


def schluessel_da() -> bool:
    try:
        return bool(SCHLUESSEL_PATH.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def schluessel_setzen(text: object) -> None:
    """Den Schluessel ablegen, nur fuer den Nutzer lesbar. `ValueError` nennt ihn nie."""
    wert = str(text or "").strip()
    if not _SCHLUESSEL.fullmatch(wert):
        raise ValueError("Der Schlüssel besteht aus sichtbaren Zeichen ohne Leerzeichen "
                         "und Zeilenumbruch, höchstens 512.")
    SCHLUESSEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    neu = SCHLUESSEL_PATH.with_name(SCHLUESSEL_PATH.name + ".neu")
    # Erst anlegen, dann schreiben: die Datei war nie fuer andere lesbar.
    fd = os.open(neu, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(wert + "\n")
    os.chmod(neu, 0o600)
    os.replace(neu, SCHLUESSEL_PATH)


def schluessel_entfernen() -> None:
    SCHLUESSEL_PATH.unlink(missing_ok=True)


def _schluessel() -> str:
    try:
        return SCHLUESSEL_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# ------------------------------------------------------------------ Freigabe

@dataclass(frozen=True, slots=True)
class _Freigabe:
    text: str
    anbindung: Anbindung
    bis: float


_FREIGABEN: dict[str, _Freigabe] = {}


def freigeben(text: str) -> tuple[str, Anbindung]:
    """Den gezeigten Text samt Ziel festhalten. Das Stichwort gilt fuer ein Senden."""
    a = laden()
    if a is None:
        raise AnbindungError("Es ist keine Anbindung eingetragen.", status=409)
    jetzt = time.monotonic()
    for k in [k for k, f in _FREIGABEN.items() if f.bis < jetzt]:
        del _FREIGABEN[k]
    # Wer die Seite oft neu laedt, haelt nicht beliebig viele Texte vor.
    while len(_FREIGABEN) >= 20:
        del _FREIGABEN[next(iter(_FREIGABEN))]
    stichwort = secrets.token_urlsafe(16)
    _FREIGABEN[stichwort] = _Freigabe(text, a, jetzt + FREIGABE_SEKUNDEN)
    return stichwort, a


def senden(stichwort: str) -> str:
    """Den freigegebenen Text senden und die Antwort des Modells als Text liefern."""
    f = _FREIGABEN.pop(str(stichwort or ""), None)
    if f is None or f.bis < time.monotonic():
        raise AnbindungError("Der Text wurde nicht freigegeben oder die Freigabe ist abgelaufen. "
                     "Sieh ihn dir noch einmal an.", status=409)
    if laden() != f.anbindung:
        raise AnbindungError("Die Anbindung hat sich geändert, seit du den Text gesehen hast. "
                     "Sieh ihn dir noch einmal an.", status=409)
    return _antwort_lesen(_anfrage(f.anbindung, f.text), f.anbindung)


# ---------------------------------------------------------------------- Netz

class _OhneWeiterleitung(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def _anfrage(a: Anbindung, text: str) -> bytes:
    """Der einzige Aufruf ins Netz. Fehler werden zu Saetzen, ohne Schluessel."""
    kopf = {"Content-Type": "application/json", "Accept": "application/json",
            "User-Agent": "finctl"}
    schluessel = _schluessel()
    if schluessel:
        kopf["Authorization"] = f"Bearer {schluessel}"
    koerper = json.dumps({"model": a.modell, "stream": False,
                          "messages": [{"role": "user", "content": text}]},
                         ensure_ascii=False).encode("utf-8")
    anfrage = urllib.request.Request(a.adresse, data=koerper, headers=kopf, method="POST")
    # An den eigenen Rechner geht es nie ueber einen Vermittler.
    handler = [_OhneWeiterleitung()] + ([urllib.request.ProxyHandler({})] if a.lokal else [])
    try:
        offen = urllib.request.build_opener(*handler).open
        with offen(anfrage, timeout=ZEIT) as r:
            roh = r.read(MAX_ANTWORT + 1)
    except urllib.error.HTTPError as e:
        code = e.code
        e.close()
        raise AnbindungError(_status_satz(code, a)) from None
    except urllib.error.URLError as e:
        raise AnbindungError(_verbindungs_satz(e.reason, a)) from None
    except (TimeoutError, OSError) as e:
        raise AnbindungError(_verbindungs_satz(e, a)) from None
    if len(roh) > MAX_ANTWORT:
        raise AnbindungError("Die Antwort ist größer als eine Million Zeichen "
                             "und wird nicht gelesen.")
    return roh


def _status_satz(code: int, a: Anbindung) -> str:
    if code in (401, 403):
        return (f"{a.host} hat den Schlüssel abgelehnt (Fehler {code}). "
                "Trage auf der Seite Anbindung einen gültigen Schlüssel ein.")
    if code == 404:
        return (f"Unter dieser Adresse antwortet {a.host} nicht (Fehler 404). "
                "Prüfe Adresse und Modell auf der Seite Anbindung.")
    if code == 429:
        return (f"{a.host} nimmt gerade nichts an (Fehler 429, zu viele Anfragen). "
                "Versuche es später.")
    if 300 <= code < 400:
        return (f"{a.host} verweist auf eine andere Adresse (Fehler {code}). "
                "Die App folgt dem nicht; trage die Adresse ein, unter der es antwortet.")
    if code >= 500:
        return f"{a.host} hat einen Fehler gemeldet ({code}). Versuche es später noch einmal."
    return f"{a.host} hat die Anfrage abgelehnt (Fehler {code}). Prüfe Adresse und Modell."


def _verbindungs_satz(grund: object, a: Anbindung) -> str:
    if isinstance(grund, TimeoutError) or "timed out" in str(grund):
        return (f"{a.host} hat nach {ZEIT} Sekunden nicht geantwortet. "
                "Läuft das Modell, und ist die Adresse richtig?")
    return (f"Keine Verbindung zu {a.host}. Stimmt die Adresse, und läuft der Server? "
            f"({type(grund).__name__})")


def _antwort_lesen(roh: bytes, a: Anbindung) -> str:
    """Der Text der ersten Antwort in der Form "chat completions"."""
    try:
        inhalt = json.loads(roh.decode("utf-8"))["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise AnbindungError(f"Die Antwort von {a.host} hat nicht die Form „chat completions“. "
                     "Prüfe Adresse und Modell.") from None
    if isinstance(inhalt, list):
        inhalt = "".join(str(t.get("text") or "") for t in inhalt if isinstance(t, dict))
    text = str(inhalt or "").strip()
    if not text:
        raise AnbindungError(f"{a.host} hat eine leere Antwort geschickt.")
    return text
