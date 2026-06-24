# client/tests — connection check

A **standard-library-only** script (no install needed) that pings the server's barebones test
endpoints and reports pass/fail. Run it from the client machine to confirm it can reach the
server (firewall / port / routing) before doing anything heavier.

```
check_connection.py   hits /healthz · /ping · /v1/info · POST /v1/echo ; exits 0 if all 200
run_client.sh         wrapper → check_connection.py --url <URL>
```

## Run from the client machine
```bash
cd client/tests
./run_client.sh http://SERVER_HOST:8000
# or:  python3 check_connection.py --url http://SERVER_HOST:8000
```

Expected: one line per endpoint, then `connection OK`. A non-zero exit means the server is
unreachable or erroring — see `../../server/PHASE5_OPERATIONS.md` §7–§8 for debugging.
