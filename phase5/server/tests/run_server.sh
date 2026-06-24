#!/usr/bin/env bash
# Start the barebones connectivity-test server.
# Creates a local venv (./.venv, inside server/tests/) on first run and installs fastapi + uvicorn.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
VENV="${VENV:-.venv}"

if [ ! -x "$VENV/bin/uvicorn" ]; then
  echo "[run_server] creating venv at $VENV and installing deps ..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q -r requirements.txt
fi

echo "[run_server] capm-p5-test serving on http://$HOST:$PORT  (Ctrl-C to stop)"
exec "$VENV/bin/uvicorn" app:app --host "$HOST" --port "$PORT"
