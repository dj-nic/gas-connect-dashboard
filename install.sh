#!/usr/bin/env bash
# Gas Connect Linux installer. Application data and existing settings are preserved.
set -Eeuo pipefail
umask 077
ref="v0.2.0"; target="${HOME}/.local/share/gas-connect"; bind=""; port=""; name="gas-connect"
noninteractive=0; dry=0; install_docker=0; source_dir=""; stage=""
fail(){ printf 'Fehler: %s\n' "$*" >&2; exit 1; }
usage(){ cat <<'EOF'
Gas Connect Linux-Installer
  --dir PFAD             Installationsordner (Standard: ~/.local/share/gas-connect)
  --bind IPv4            Eigene Server-LAN-IP; wird nicht veröffentlicht
  --port PORT            Web-Port (Standard 8086); MQTT verwendet 1883
  --name NAME            Eigener Container-/Compose-Name (Standard gas-connect)
  --ref TAG              Release-Tag (Standard v0.2.0)
  --source-dir PFAD      Lokalen Quellcode statt Download verwenden
  --non-interactive      Benötigt --bind oder vorhandene .env
  --install-docker       Docker über das offizielle Installationsskript installieren,
                         falls Docker fehlt (bewusste Änderung am Linux-System)
  --dry-run              Nur Optionen prüfen; nichts installieren oder verändern
  --help                 Diese Hilfe
EOF
}
while (($#)); do
  case "$1" in
    --dir|--bind|--port|--ref|--name|--source-dir)
      (($#>=2)) || fail "Wert für $1 fehlt"
      case "$1" in --dir) target=$2;; --bind) bind=$2;; --port) port=$2;; --ref) ref=$2;; --name) name=$2;; --source-dir) source_dir=$2;; esac;shift 2;;
    --non-interactive) noninteractive=1;shift;; --dry-run) dry=1;shift;; --install-docker) install_docker=1;shift;;
    --help|-h) usage;exit 0;; *) fail "Unbekannte Option: $1";;
  esac
done
[[ $(uname -s) == Linux ]] || fail 'Dieser Installer ist für Linux; USB-Flash-Skripte unterstützen auch Windows/macOS.'
[[ $name =~ ^[a-z][a-z0-9-]{0,62}$ ]] || fail 'Containername: Kleinbuchstaben, Ziffern und Bindestriche.'
[[ $ref =~ ^[a-zA-Z0-9._-]+$ ]] || fail 'Ungültiger Release-Tag.'
command -v realpath >/dev/null || fail 'realpath fehlt (coreutils).'
target=$(realpath -m -- "$target")
case "$target" in /|/home|/root|/opt|/usr|/var|/etc|/tmp|/srv) fail 'Einen eigenen Unterordner als Installationsziel wählen.';; esac
if [[ -d $target && -n $(find "$target" -mindepth 1 -maxdepth 1 -print -quit) && ! -f $target/.gas-connect-install ]]; then
  fail 'Ziel enthält bereits Dateien, aber keine Gas-Connect-Installationsmarkierung. Eigenen leeren Ordner wählen.'
fi
read_env(){ [[ ! -f $target/.env ]] || sed -n "s/^$1=//p" "$target/.env" | tail -1; }
[[ -n $bind ]] || bind=$(read_env LAN_IP)
[[ -n $port ]] || port=$(read_env WEB_PORT)
port=${port:-8086}
valid_ip(){
  local a b c d
  [[ $1 =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || return 1
  IFS=. read -r a b c d <<< "$1"
  for octet in "$a" "$b" "$c" "$d"; do ((10#$octet<=255)) || return 1; done
}
if [[ -z $bind ]]; then
  ((noninteractive==0)) || fail '--bind mit der eigenen LAN-IP angeben.'
  suggestion=$(ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([^ ]*\).*/\1/p' | head -1 || true)
  suggestion=${suggestion:-127.0.0.1}
  read -r -p "Eigene Server-LAN-IP [$suggestion]: " answer < /dev/tty
  bind=${answer:-$suggestion}
fi
valid_ip "$bind" || fail 'Gültige eigene IPv4-Adresse angeben.'
[[ $bind != 0.0.0.0 ]] || fail 'Eine konkrete Server-LAN-IP statt aller Netzwerkschnittstellen wählen.'
[[ $port =~ ^[0-9]{1,5}$ ]] && ((10#$port>=1 && 10#$port<=65535)) || fail 'Web-Port muss zwischen 1 und 65535 liegen.'
port=$((10#$port))
[[ $port != 1883 ]] || fail 'Web-Port und MQTT-Port dürfen nicht identisch sein.'
if [[ -n $source_dir ]]; then source_dir=$(realpath -- "$source_dir"); fi
if [[ -z $source_dir ]]; then
  script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
  if [[ -f $script_dir/Dockerfile && -f $script_dir/compose.yaml ]]; then source_dir=$script_dir; fi
fi
if [[ -n $source_dir ]]; then
  [[ -f $source_dir/Dockerfile && -f $source_dir/compose.yaml ]] || fail 'Quellordner enthält kein Gas-Connect-Projekt.'
fi
printf 'Gas Connect: %s · %s\nZiel: %s\nWeb: http://%s:%s · MQTT: %s:1883\n' "$name" "$ref" "$target" "$bind" "$port" "$bind"
((dry==0)) || { echo 'Dry-run erfolgreich. Keine Dateien oder Container verändert.';exit 0; }
command -v curl >/dev/null || fail 'curl installieren.'
command -v tar >/dev/null || fail 'tar installieren.'
stage=$(mktemp -d)
cleanup(){ [[ -z $stage || ! -d $stage ]] || rm -rf -- "$stage"; }
trap cleanup EXIT
if ! command -v docker >/dev/null; then
  ((install_docker==1)) || fail 'Docker Engine + Compose fehlen. Docker installieren oder bewusst --install-docker verwenden.'
  curl --fail --show-error --silent --location --proto '=https' https://get.docker.com -o "$stage/get-docker.sh"
  if ((EUID==0)); then sh "$stage/get-docker.sh";else sudo sh "$stage/get-docker.sh";fi
fi
DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then
  command -v sudo >/dev/null || fail 'Kein Zugriff auf Docker. Berechtigungen prüfen.'
  DOCKER=(sudo docker)
  "${DOCKER[@]}" info >/dev/null || fail 'Docker-Dienst nicht erreichbar.'
fi
"${DOCKER[@]}" compose version >/dev/null || fail 'Docker Compose v2 fehlt. Docker Compose Plugin installieren.'
if "${DOCKER[@]}" inspect "$name" >/dev/null 2>&1; then
  mounted=$("${DOCKER[@]}" inspect "$name" --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Source}}{{end}}{{end}}')
  [[ $mounted == "$target/data" ]] || fail 'Ein gleichnamiger Container gehört zu einer anderen Installation. --name ändern.'
fi
if [[ -z $source_dir ]]; then
  curl --fail --show-error --silent --location --proto '=https' "https://codeload.github.com/dj-nic/gas-connect-dashboard/tar.gz/refs/tags/$ref" -o "$stage/source.tar.gz"
  mkdir "$stage/source";tar -xzf "$stage/source.tar.gz" --strip-components=1 -C "$stage/source"
  source_dir=$stage/source
fi
[[ -f $source_dir/Dockerfile && -f $source_dir/compose.yaml ]] || fail 'Release-Download unvollständig.'
mkdir -p "$stage/payload" "$target"
tar -C "$source_dir" --exclude='./.git' --exclude='./data' --exclude='./.env' --exclude='./.env.backup' --exclude='./.gas-connect-install' --exclude='./.flash-cache' --exclude='./.flash-venv' --exclude='./firmware/.pio' --exclude='./work' -cf - . | tar -xf - -C "$stage/payload"
cp -a "$stage/payload/." "$target/"
if [[ -f $target/.env ]];then cp -p "$target/.env" "$target/.env.backup";fi
printf 'LAN_IP=%s\nWEB_PORT=%s\nCONTAINER_NAME=%s\n' "$bind" "$port" "$name" > "$target/.env"
printf 'dj-nic/gas-connect-dashboard\n' > "$target/.gas-connect-install"
cd "$target"
"${DOCKER[@]}" compose -p "$name" up -d --build
ready=0
for ((attempt=0;attempt<60;attempt++));do
  health=$("${DOCKER[@]}" inspect "$name" --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' 2>/dev/null || true)
  if [[ $health == healthy ]];then ready=1;break;fi
  sleep 2
done
((ready==1)) || { "${DOCKER[@]}" compose -p "$name" logs --tail=30;fail 'Container noch nicht gesund; Logs prüfen. Datenordner bleibt erhalten.'; }
printf '\nBereit: http://%s:%s\nErsten Einrichtungscode auf diesem Server anzeigen:\n  ' "$bind" "$port"
printf '%q ' "${DOCKER[@]}" exec "$name" cat /data/setup-token
printf '\nDaten und Passwörter bleiben ausschließlich in %s/data/.\n' "$target"
