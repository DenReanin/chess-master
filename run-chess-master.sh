#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

CHESSMASTER_PORT="${CHESSMASTER_PORT:-8020}"
export CHESSMASTER_PORT

if [ ! -x ".venv/bin/python" ]; then
  echo "[Chess Master] Creando entorno virtual .venv..."
  python3 -m venv --system-site-packages .venv
  echo "[Chess Master] Instalando dependencias..."
  ./.venv/bin/pip install --upgrade pip >/dev/null || true
  ./.venv/bin/pip install -r requirements.txt
fi

if [ "${1:-}" = "--setup-only" ]; then
  echo "[Chess Master] Entorno listo."
  exit 0
fi

(
  for _ in $(seq 1 30); do
    if "$ROOT/.venv/bin/python" -c "import os, socket; s=socket.socket(); s.settimeout(0.2); s.connect(('127.0.0.1', int(os.environ.get('CHESSMASTER_PORT', '8020')))); s.close()" 2>/dev/null; then
      if command -v xdg-open >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
        xdg-open "http://127.0.0.1:${CHESSMASTER_PORT}" >/dev/null 2>&1 || true
      fi
      break
    fi
    sleep 0.5
  done
) >/dev/null 2>&1 &

exec "$ROOT/.venv/bin/python" -u -m uvicorn backend.main:app --host 127.0.0.1 --port "$CHESSMASTER_PORT"
