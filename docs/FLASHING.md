# ESP32-C3 flashen und den richtigen USB-Port finden

## Browser direkt aus GitHub öffnen

[**Gas Connect Web-Installer öffnen**](https://dj-nic.github.io/gas-connect-dashboard/)

Der Link führt zu GitHub Pages über HTTPS. Der Browser auf dem PC greift auf dessen lokales USB-Gerät zu. Es wird kein ESP auf einem GitHub-Server geflasht. Die Seite zeigt nur die USB-Geräte, die der Browser nach einer bewussten Auswahl freigibt. Ein vollständiger stiller Scan aller COM-Ports ist im Browser nicht erlaubt; dafür gibt es den lokalen Assistenten.

1. Desktop-Chrome oder Edge mit Web Serial verwenden. Andere Browser nur, wenn sie Web Serial tatsächlich anbieten. iPhone/iPad sind hierfür nicht geeignet.
2. ESP abziehen. BOOT halten, USB-Datenkabel einstecken, BOOT lösen.
3. Auf **Installieren / USB-Port wählen** klicken und im Betriebssystemdialog den ESP wählen. Häufig heißt er USB JTAG/serial debug unit. Bei Unsicherheit abziehen, Dialog erneut öffnen und vergleichen, welcher Eintrag verschwunden bzw. hinzugekommen ist.
4. Das Tool prüft die Chip-Familie; das Manifest liefert nur ESP32-C3 aus. Ein Wechsel von anderer Firmware kann eine vollständige Löschung benötigen. Das löscht WLAN und Messpuffer. Bei Updates die Löschoption bewusst deaktiviert lassen, um Daten zu erhalten.
5. Nach dem Schreiben USB trennen und ohne BOOT neu starten. Die Netzwerkeinrichtung erfolgt anschließend über das ESP-Setup-WLAN. Die Firmware unterstützt keine Improv-WLAN-Einrichtung im Browser.

Der Browser-Installer verwendet ESP Web Tools. Dessen Bibliothek wird von einem versionsgebundenen CDN-Paket geladen; Firmware und Manifest liegen auf derselben GitHub-Pages-Seite. Serielle Daten gehen direkt zwischen Browser und ESP.

## Lokaler Assistent — Windows, Linux und macOS

Release-ZIP herunterladen und vollständig entpacken. Python 3.10+ oder [uv](https://docs.astral.sh/uv/) muss installiert sein. Die Skripte verwenden entweder uv oder eine lokale `.flash-venv`; sie installieren keine Pakete in die globale Python-Umgebung.

Windows: **`Flash ESP.cmd`** doppelklicken. Alternativ:

```powershell
.\scripts\flash.cmd
.\scripts\flash.cmd --list-ports
.\scripts\flash.cmd --detect
```

Linux/macOS:

```bash
bash scripts/flash.sh
bash scripts/flash.sh --list-ports
bash scripts/flash.sh --detect
```

Die Tabelle zeigt Portname, Gerätebeschreibung, USB-VID/PID und Seriennummer, soweit der Treiber diese liefert. Der Assistent kann erneut scannen und markiert beim Abzieh-/Einsteckvergleich neue oder veränderte Einträge. Bei USB-Konvertern beweisen VID/PID allein nicht den ESP-Chiptyp; die Chipprüfung erfolgt beim Flashen durch esptool. Ports werden nicht allein aufgrund einer Vermutung automatisch beschrieben.

Eine Nummer bewusst auswählen, Firmware-Prüfsumme prüfen lassen und **FLASH** eingeben. Das ausdrücklich angeforderte `--erase` verlangt **LOESCHEN**, da dabei gespeicherte Daten verschwinden:

```powershell
.\scripts\flash.cmd --detect --erase
```

Für einen bewusst unbeaufsichtigten Aufruf kann `--port <PORT> --yes` angegeben werden. `--yes` ohne Port ist gesperrt. `--list-ports --json` liefert die Portinformationen maschinenlesbar und führt keine Flash-Operation aus.

Ist `factory.bin` im Release-Paket vorhanden, wird sie lokal verwendet. Beim Quellcode-Download fehlt die Binärdatei absichtlich: der Assistent lädt dann das zu `VERSION` gehörende öffentliche Release und dessen SHA-256-Datei. Downloads liegen unter `.flash-cache/`. Ohne Netzwerk das vollständige Release-ZIP verwenden. Prüfsumme und Flashdatei sind zusammen zu betrachten; die Prüfsumme allein ist keine unabhängige Herkunftssignatur.

## VS Code Tasks

Repository lokal in VS Code öffnen. **Terminal → Task ausführen** bietet:

- **ESP: Ports auflisten** — Übersicht vor dem Anschluss bzw. zur Kontrolle.
- **ESP: Neu angeschlossenes Gerät erkennen** — geführter Abzieh-/Einsteckvergleich, dann Auswahl.
- **ESP: Flash-Assistent** — normale interaktive Einrichtung.

Codespaces und die GitHub-Codeansicht haben keinen direkten Zugriff auf physische COM-Ports des PCs. Dort stattdessen den Web-Installer-Link öffnen oder das Projekt lokal herunterladen.

## Nach dem Flash

`Gas-Setup-<Suffix>` wählen, Passwort `gas-<Suffix>`, dann den allgemeinen ESP-Setup-Zugang `http://192.168.4.1` öffnen. Eigene WLAN-/Serverdaten eintragen. Auf dem Server Impulsvolumen prüfen und speichern, danach den physischen Zählerstand abgleichen. [Vollständiges Setup](SETUP.md).
