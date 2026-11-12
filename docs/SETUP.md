# Einrichtung von Server und Sensor

## 1 · Linux-Server

Docker Engine mit Compose v2, eine freie LAN-Adresse des Servers sowie freie TCP-Ports 8086 (Web) und 1883 (MQTT) werden benötigt. `curl`, `tar` und `realpath` gehören zu den Installer-Voraussetzungen.

```bash
curl -fsSL https://raw.githubusercontent.com/dj-nic/gas-connect-dashboard/v0.2.0/install.sh -o gas-connect-install.sh
bash gas-connect-install.sh
```

Das Skript schlägt die vom Betriebssystem ermittelte eigene LAN-IP vor und fragt nach. Es lädt das festgelegte Release, baut genau einen Container und wartet auf dessen Gesundheitsprüfung. Das Standardziel ist `~/.local/share/gas-connect`. Docker wird nur mit der ausdrücklich angegebenen Option `--install-docker` nachinstalliert; das verwendet das offizielle Docker-Installationsskript und benötigt entsprechende Rechte.

Vollautomatisch mit selbst einzusetzender Serveradresse:

```bash
bash gas-connect-install.sh --non-interactive --bind "<SERVER-LAN-IP>" --dir "$HOME/gas-connect"
```

Weitere Beispiele:

```bash
bash gas-connect-install.sh --help
bash gas-connect-install.sh --bind "<SERVER-LAN-IP>" --port 8087 --name gas-connect-second
bash gas-connect-install.sh --bind "<SERVER-LAN-IP>" --dry-run
```

Eine bereits belegte Installation wird nicht blind übernommen. Zielordner ohne Installationsmarkierung und gleichnamige Container mit einem anderen Datenverzeichnis werden abgelehnt. MQTT bleibt auf Port 1883; bei mehreren Installationen müssen unterschiedliche Serveradressen verwendet werden.

### Manuell mit Docker Compose

```bash
git clone https://github.com/dj-nic/gas-connect-dashboard.git
cd gas-connect-dashboard
cp .env.example .env
# LAN_IP in .env auf die eigene Server-LAN-IP setzen.
docker compose up -d --build
```

Der manuelle Standard ist bewusst die Loopback-Adresse. Damit ist zunächst nur lokaler Zugriff möglich; ein ESP im WLAN braucht eine erreichbare LAN-IP. Es wird keine Portfreigabe im Router eingerichtet.

## 2 · Dashboard anmelden

Die Oberfläche liegt auf `http://<SERVER-LAN-IP>:8086`. Auf dem Server:

```bash
docker exec gas-connect cat /data/setup-token
```

Den Code auf der ersten Anmeldeseite eingeben und ein eigenes Passwort mit mindestens zwölf Zeichen festlegen. Bei einem eigenen Containernamen den Befehl entsprechend anpassen. Dann unter **Einstellungen** den Impulswert des Gaszählers prüfen und speichern. Der Typenschildwert ist maßgeblich, nicht eine pauschale Annahme. Bis zur ersten Bestätigung der Einstellungen werden Sensoreinträge nicht bestätigt und bleiben im ESP-Puffer.

Unter **Sensor einrichten** erscheint das für diese Installation zufällig erzeugte Sensor-Passwort. Es ist kein allgemeines Standardpasswort. WLAN-Passwörter, Serveradresse und Sensor-Passwort stehen in keinem Release-Abbild.

## 3 · ESP flashen

Die Optionen stehen ausführlich in [FLASHING.md](FLASHING.md). Am einfachsten ist der [Browser-Installer](https://dj-nic.github.io/gas-connect-dashboard/). Alternativ den lokalen Flash-Assistenten starten; er zeigt COM-/USB-Ports, Gerätebeschreibung, USB-ID und Seriennummer an und kann einen Abzieh-/Einsteckvergleich durchführen.

Nur den unterstützten ESP32-C3 mit 4 MB Flash wählen. Für den ersten Flash BOOT gedrückt halten, USB einstecken und BOOT wieder loslassen. Bei einem Wechsel von fremder Firmware die bewusste Löschoption verwenden; dabei gehen alte Einstellungen und Messwerte verloren.

## 4 · WLAN und Server verbinden

1. Nach dem Flash USB abziehen und ohne BOOT neu einstecken.
2. Mit dem WLAN `Gas-Setup-<Suffix>` verbinden. Das Passwort ist `gas-<Suffix>` mit identischer Schreibweise.
3. `http://192.168.4.1` öffnen. Diese Adresse ist das allgemeine temporäre ESP-Setup-Netz, keine voreingestellte Serveradresse.
4. Eigenes Heim-WLAN, dessen Passwort, die tatsächliche Serveradresse und das Sensor-Passwort aus dem Dashboard eintragen.
5. Mindestens eine Messminute abwarten. Im Dashboard den physischen Zählerstand unter **Einstellungen** abgleichen. Dieser Abgleich verändert den Gesamtstand, nicht den gemessenen Verbrauch.

Das Setup-WLAN schließt nach 15 Minuten. Fünf Sekunden BOOT öffnet die Einrichtung erneut; der vorhandene Messpuffer bleibt erhalten. Die Pinbelegung ist Reedkontakt an **GPIO4 und GND**, Versorgung über **USB-C**. Den Gaszähler und seine Plomben geschlossen lassen; es wird nur der externe Impulsmagnet erfasst.

## 5 · Betrieb, Update und Backup

```bash
cd ~/.local/share/gas-connect
docker compose -p gas-connect logs --tail=50
docker inspect gas-connect --format '{{.State.Health.Status}}'
```

Zum Aktualisieren den neuen versionsgebundenen Installer mit demselben Ziel und Namen starten. Vorhandene Daten und Passwörter im Ordner `data/` bleiben erhalten; die bisherige `.env` wird als `.env.backup` gesichert. Der Installer verändert keine fremden Container und legt keinen Cloud-Zugang an.

Für ein konsistentes Backup den Container kurz stoppen, `data/` einschließlich SQLite, WAL-Dateien, Zugangsdaten und Sitzungsschlüsseln als Administrator sichern, danach wieder starten. Ein Backup enthält Geheimnisse und gehört nicht ins Repository. Wiederherstellung: Container stoppen, gesicherten Datenordner zurückspielen und denselben Container wieder starten.

## Fehlerbehebung

| Beobachtung | Prüfen |
|---|---|
| Kein USB-Port | Datenkabel statt Ladekabel, BOOT beim Einstecken, Gerät abziehen/einstecken, andere serielle Programme schließen |
| Linux: Permission denied beim USB-Port | Rechte für die passende Gruppe (`dialout` oder distributionsabhängig `uucp`) einrichten und neu anmelden |
| ESP erreicht den Server nicht | Eigene LAN-IP in `.env`, TCP 1883 und Firewall prüfen; Loopback funktioniert nicht aus dem WLAN |
| Sensor verbunden, aber keine Historie | Impulswert in den Einstellungen speichern und mindestens eine Minute warten |
| Doppelte Pulse | Entprellzeit vorsichtig erhöhen und Kontaktposition prüfen |
| Mengen um Faktor zehn falsch | Impulswert mit dem Typenschild abgleichen; nach Beginn ist er zum Schutz der Historie gesperrt |
| Browser kann nicht flashen | HTTPS, Desktop-Chrome/Edge, freie USB-Schnittstelle; sonst lokalen Assistenten nutzen |
| Unbekannte Zeit | ESP braucht zunächst eine gültige NTP-Zeit; unbekannte Messzeiten werden nicht erfunden |

MQTT ist hier für ein vertrauenswürdiges Heimnetz mit Passwortschutz vorbereitet und verwendet unverschlüsselten Transport. Für fremde Netze ist eine eigene TLS-/VPN-Erweiterung erforderlich. Es gibt keine zugesagte allgemeine Freigabe für beliebige Gaszähler oder explosionsgefährdete Einsatzorte.
