# Entwicklung und Prüfungen

Backend: Python 3.13 empfohlen. Tests:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/privacy_check.py
bash -n install.sh
```

Der Flash-Assistent ist unabhängig von einem echten ESP testbar: Gerätevergleich, explizite Auswahl, Abbruch und fehlerhafte Prüfsummen dürfen keine Schreiboperation auslösen. Für einen echten Portscan werden die Abhängigkeiten aus `scripts/requirements-flash.txt` benötigt.

Firmware:

```bash
python -m pip install platformio==6.1.18
bash firmware/scripts/build.sh
python scripts/privacy_check.py firmware/dist/factory.bin
```

PlatformIO lädt die im Projekt festgelegten Framework- und Bibliotheksversionen. `PLATFORMIO_CORE_DIR` ist optional; ohne Angabe wird der reguläre PlatformIO-Nutzerordner verwendet. Die erzeugten Binärdateien bleiben außerhalb der Git-Historie und werden als Release-Assets bzw. Pages-Dateien veröffentlicht.

Die GitHub-Actions-Workflow-Datei prüft Python/JavaScript/Shell, Backend- und Flash-Regressionen, Containerstart und MQTT-Replay über einen Neustart. Ein separater Job kompiliert die Firmware und prüft die Binärdatei auf versehentlich eingebettete private Netzwerkadressen. Der Pages-Job übernimmt genau dieses erzeugte Abbild und stellt es mit Manifest über HTTPS bereit. Ein `v*`-Tag baut die Release-Dateien und das Flash-ZIP.

Ein Hardware-Test bleibt zusätzlich erforderlich: Erstflash, BOOT-Verhalten, WLAN-Einrichtung, tatsächliche Kontaktqualität sowie Journalfüllung und Wiederanlauf nach Stromverlust sind durch CI allein nicht nachweisbar. Änderungen an Protokoll oder Partitionslayout benötigen besondere Migrationsprüfung, damit vorhandene Puffer nicht still verloren gehen.
