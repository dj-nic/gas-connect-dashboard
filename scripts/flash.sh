#!/usr/bin/env bash
set -Eeuo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if command -v uv >/dev/null; then
  exec uv run --no-project --system-certs --with-requirements "$root/scripts/requirements-flash.txt" python "$root/scripts/flash.py" "$@"
fi
command -v python3 >/dev/null || { echo 'Python 3 oder uv installieren.' >&2; exit 1; }
python3 -m venv "$root/.flash-venv" || { echo 'Das venv-Paket für Python installieren oder uv verwenden.' >&2; exit 1; }
"$root/.flash-venv/bin/python" -m pip install -r "$root/scripts/requirements-flash.txt"
exec "$root/.flash-venv/bin/python" "$root/scripts/flash.py" "$@"
