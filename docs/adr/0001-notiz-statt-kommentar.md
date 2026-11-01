# Das Warum steht als Notiz am Eintrag, nicht als Kommentar in einer Datei

Bisher stand die Begründung zu Konten, Krediten, Zielen und Kontenregeln als Kommentar in handgeschriebenen YAML-Basisdateien. Die Oberfläche schrieb ihre Änderungen deshalb in eine zweite Datei (`*_custom.yaml`), damit sie die Kommentare nicht löscht. Diese Begründungen waren persönlich, veralteten unbemerkt und gelangten über Code und Doku bis in ein öffentliches Repository. Künftig trägt jeder Eintrag eine datierte **Notiz**, die der Haushalt in der Oberfläche bearbeitet. Text der App nennt nur Begriffe, keine Einzelfälle.

## Consequences

- Der Grund für die Zweiteilung in Basisdatei und Overlay entfällt: Ein Eintrag hat einen Ort, und die Oberfläche darf ihn ganz schreiben.
- Die Kommentare der bestehenden Basisdateien werden einmal in Notizen übernommen. Danach gibt es keine Begründung mehr, die nur im Texteditor sichtbar ist.
- Das Datum der Notiz macht ihr Alter sichtbar. Der Monatsabschluss kann fragen, ob eine alte Notiz noch stimmt.
