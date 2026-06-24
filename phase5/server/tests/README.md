# server/tests — barebones connectivity test server

A trivial FastAPI server with **no models, no probes, no mTLS** — used to confirm the server
boots and is reachable, *before* the real inference server (`capm-p5/`) is built. Pair it with
`../../client/tests/check_connection.py` from the client side.

```
app.py            /healthz · /ping · /v1/info · POST /v1/echo
requirements.txt  fastapi + uvicorn (+ httpx for the in-process test)
run_server.sh     create ./.venv (first run) + start uvicorn on 0.0.0.0:${PORT:-8000}
test_server.py    in-process smoke test of all endpoints (no network)
```

## Run on this (server) box
```bash
cd server/tests
./run_server.sh                 # serves on 0.0.0.0:8000 ; set PORT=... to change
```

## Validate logic without a network
```bash
cd server/tests
./run_server.sh >/dev/null 2>&1 &   # or just build the venv once, then:
.venv/bin/python test_server.py     # → "OK — all barebones server checks passed"
```
(First run creates `server/tests/.venv` and installs fastapi/uvicorn — gitignore it.)

This proves boot + port-bind + JSON round-trip. It does **not** exercise models/probes/mTLS —
those belong to `capm-p5/` (see `../PHASE5_BUILD_PLAN.md`).
