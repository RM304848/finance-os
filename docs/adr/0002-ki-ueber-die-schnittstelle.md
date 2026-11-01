# KI spricht nur über die Schnittstelle der App, und Daten verlassen den Rechner nur auf Wahl

Der Haushalt soll über seine Buchungen reden und Planzeilen oder Kredite mit Hilfe einer KI anlegen können. Die KI bekommt dafür einen MCP-Zugang, der dieselben geprüften Lese- und Schreibwege benutzt wie die Oberfläche. Was sie anlegen will, ist ein Vorschlag, den der Haushalt bestätigt; danach ist es eine Handentscheidung wie jede andere. Das Modell ist frei wählbar. Als Standard gilt ein lokales Modell. Eine externe API bindet der Haushalt nur ausdrücklich ein, und die App sagt dabei, was den Rechner verlässt. Ohne jede Anbindung erzeugt die App eine Kopiervorlage, die der Haushalt selbst in ein Modell seiner Wahl einfügt.

## Considered Options

- **Kostenlose Modelle über einen Vermittler als Standard:** abgelehnt. Eingaben gehen an wechselnde Anbieter, die sie oft speichern oder zum Training verwenden dürfen.
- **Nur lokal:** abgelehnt. Lokale Modelle sind für Planung und Rechnen oft zu schwach, und die Wahl gehört dem Haushalt.

## Consequences

- Die Grundregel „Daten verlassen den Rechner nicht“ wird zu „nur auf ausdrückliche Wahl des Haushalts“. `CLAUDE.md` wird angepasst, sobald der Zugang gebaut wird.
- Einlesen, Zuordnen und Rechnen laufen weiter ohne KI. Die KI liest und schlägt vor; sie rechnet keine angezeigte Zahl.
- Die Schnittstelle muss vollständig genug sein, um jede Handentscheidung auszudrücken. Das schärft das Domänenmodell, statt es zu umgehen.
