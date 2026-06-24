# Phase 5 — client side

This folder stays on **your local machine**. It is the thin side that **drives the remote
Phase-5 server** over HTTPS (you copy only the `../server/` folder to the big GPU machine).

```
client/
└── tests/                  connectivity check (stdlib only) — run this FIRST to prove reachability
    ├── check_connection.py
    └── run_client.sh
```

**Today:** `tests/` confirms the client↔server connection works against the barebones test
server (`../server/tests/`).

**Later (built per `../server/PHASE5_BUILD_PLAN.md`):** the real remote client/CLI
(`capm_client.py` + `cli.py`, mTLS + bearer token) lands here — it submits experiment jobs,
polls, and pulls artifacts from the live server. The same `./run.sh matrix --remote URL`
workflow is documented in `../server/PHASE5_OPERATIONS.md` (connect / run / monitor / recover).

> The full architecture, build spec, and ops runbook live in `../server/` (the 4 `PHASE5_*.md`
> docs). The client only needs to know the server's URL, the client cert, and the bearer token.
