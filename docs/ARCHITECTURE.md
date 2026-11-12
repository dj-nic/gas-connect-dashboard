# Architektur und Synchronisation

## Ein Container, zwei Prozesse, ein Datenordner

Mosquitto und die Web-App werden vom Container-Startprogramm gemeinsam überwacht. Stirbt ein Kindprozess, beendet sich der Container und Dockers `restart: unless-stopped` startet ihn neu. SQLite benötigt keinen separaten Datenbankdienst. Der Datenordner `/data` wird dauerhaft vom Server eingebunden und enthält Datenbank, Zugangsdaten und Sessions. MQTT dient als Transport; die zuverlässige Wiederholung übernimmt der ESP, nicht eine behauptete unbegrenzte Broker-Warteschlange.

## Protokoll

| Topic | Richtung | Inhalt |
|---|---|---|
| `gas/<stream>/event` | ESP → Server | Abgeschlossene Minute mit Sequenz, UTC-Minute, Impulszahl und kumuliertem Zähler |
| `gas/<stream>/ack` | Server → ESP | Bestätigte Sequenz nach erfolgreicher SQLite-Transaktion |
| `gas/<stream>/status` | ESP → Server | Zustand, aktueller Impulszähler, WLAN, Uhrzeit, Puffer und Durchfluss |
| `gas/<stream>/config` | Server → ESP | Bestätigte Entprellzeit |

Beispiel ohne reale Gerätekennung:

```json
{"seq":42,"minute":30000000,"pulses":2,"total":84,"flags":0}
```

`minute` ist die Anzahl der Minuten seit Unix-Epoch in UTC; `0` bedeutet unbekannte Zeit. `flags=1` kennzeichnet unbekannte Zeit. Gerätekennungen werden bei der ersten Einrichtung zufällig erzeugt und persistent gespeichert.

Der Server führt `(stream, seq)` als eindeutigen Schlüssel. Identische Wiederholungen erhalten erneut ein ACK; widersprüchliche Wiederholungen werden abgelehnt. Für aufeinanderfolgende Einträge werden Impulszuwachs und Gesamtzähler verglichen. Erst nach dem Commit sendet die Anwendung ihr ACK. Ein MQTT-PUBACK allein ist dafür nicht ausreichend.

## Flash-Journal

43.200 Einträge zu je 20 Byte ergeben 864.000 Byte Rohspeicher für 30 Tage im Minutentakt. Der LittleFS-Bereich umfasst 1.216 KiB; zwei Firmware-Partitionen bleiben getrennt. Jeder Eintrag enthält Sequenz, Zeit, Gesamtimpulse, Minutenimpulse, Flags und CRC. Beim Start wird die gültige Historie wiedergefunden. Das System formatiert einen bereits initialisierten beschädigten Puffer nicht automatisch.

Bei Überlauf überschreibt der Ring die ältesten Minuten. Der Gesamtimpulsstand bleibt erhalten; verworfene Minuten werden gemeldet. Ein voller 30-Tage-Puffer kann nach Wiederverbindung über längere Zeit nachlaufen; Live-Status und aktueller Gesamtzähler werden unabhängig davon gesendet.

## Grenzen und Zeit

NTP synchronisiert die ESP-Uhr. Bei einem reinen Kommunikationsausfall läuft sie im weiter versorgten ESP weiter. Ohne gültige Zeit gespeicherte Mengen werden angezeigt, aber nicht auf erfundene Zeitpunkte im Diagramm verteilt. Auswertungen verwenden Europe/Berlin inklusive Sommerzeitwechsel.

Während der ESP stromlos ist, werden keine Pulse erfasst. Die noch nicht geschlossene Minute kann bei abruptem Stromverlust fehlen. Ein Abgleich mit dem physischen Zählerstand korrigiert den angezeigten Stand, rekonstruiert aber keine verlorenen Zeitverläufe. Kosten sind eine Schätzung aus €/m³ ohne Grundpreis.
