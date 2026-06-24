#!/usr/bin/env bash
# Simple connection check against the barebones test server (stdlib only — no deps).
# Usage:  ./run_client.sh [http://HOST:PORT]
set -euo pipefail
cd "$(dirname "$0")"
URL="${1:-${CAPM_P5_TEST_URL:-http://172.17.254.118:9025}}"
exec python3 check_connection.py --url "$URL"
