# Phase 5 — Elaborate Implementation / Build Plan

**Companion to** [`PHASE5_IMPLEMENTATION.md`](PHASE5_IMPLEMENTATION.md) (the *architecture & strategy* —
the "why"). **This document is the *build spec* — the "what files, in what order, run
how".** It is written to be self-contained enough that **an independent Claude session,
given only the `phase5/` folder, can implement and deploy Phase 5 without prior context.**

**Status:** plan only — *no code written yet.*

---

## 0. The one sentence that defines Phase 5

> **One single-command folder that, on the 96 GB box, (1) loads each bigger model in turn
> (Qwen2.5-14B, Phi-4-14B, Qwen2.5-32B; + 7B), (2) trains that model's usage probe on the
> relevant dataset and FREEZES + signs its weights, then (3) spawns one API server that, on
> request, runs the Phase-4 experiments (B1/B2/D2/F3 + C2) on the hosted models and returns
> the experiment output together with the probe's inference — so the probes are trained once
> on the hosted models and used forever after through the API.**

Everything below serves that sentence. The server is *plumbing*; the deliverables are
(a) **frozen, signed per-model probes** and (b) the **14B/32B results in the Phase-4 schema**,
plus the cross-architecture (Qwen↔Phi-4) and scale (14B↔32B) reads.

**The mental model (and the hypothetical it implements):** the API plays the role of *the
model host that attests its own usage signal `u`* to a calling/verifying agent. In CAPM, `u`
is a runtime-internal sensor that can only run where the model runs (white-box). Our endpoint
*is* that white-box party: the caller is treated as if it received the probe result from the
host. §15 works through exactly what that buys and what it assumes (the short version: a
trusted host's `u` only ever *informs* under the min-clamp; even a lying host cannot push a
claim above its source-class ceiling — see the critique), and §16 critiques feasibility.

---

## 1. Operating model (lifecycle)

```
   ┌─ ONE-TIME, on the 96 GB box (your single access window) ─────────────┐
   │  1. copy the  phase5/capm-p5/  folder onto the box                    │
   │  2. run ONE command:   ./run.sh up                                    │
   │       → preflight → build image → fetch models                        │
   │       → TRAIN-AND-FREEZE PROBES: for each model, load it, extract     │
   │         B1 features from the usage dataset, fit the UsageProbe,        │
   │         freeze + Ed25519-sign the weights → artifacts/probes/, unload  │
   │       → start the API server (daemon, frozen probes loaded read-only)  │
   │  3. note the host:port + copy the generated client certs back to you  │
   └──────────────────────────────────────────────────────────────────────┘
                                   │  server stays up (docker restart=unless-stopped)
                                   ▼
   ┌─ THEREAFTER, from your own machine (same folder, client mode) ────────┐
   │  server stays LIVE but DORMANT: no LLM in VRAM at rest (~2.5 GB sensors)│
   │  ./run.sh matrix --remote https://BOX:8443   # triggers all experiments│
   │       → on each request the server lazy-loads the model (+frozen probe),│
   │         runs on the GPU, returns; unloads after idle TTL → dormant again│
   │       → you poll + pull artifacts; results land in ./artifacts/ locally │
   └──────────────────────────────────────────────────────────────────────┘
```

**Key properties this enforces**
- **Single command to stand up** (`./run.sh up`) — everything else is automation behind it.
- **Standalone**: the folder carries all code (vendored p3 + p4 + new p5), Docker
  definition, config, certs generator, and docs. No reliance on anything outside it except
  a CUDA GPU + Docker + (for model download) network or a pre-staged model cache.
- **Symmetric folder**: the *same* folder is the server deploy (on the box) and the remote
  client (on your machine) — subcommands switch role. You keep one copy locally, ship one to
  the box.
- **Compute is always server-side.** The client only triggers jobs and pulls small
  artifacts. Hidden states never leave the box.

---

## 2. The standalone guarantee & the single command

`./run.sh` is a thin dispatcher (bash, no dependencies) over Docker Compose:

| Command | Where | Does |
|---------|-------|------|
| `./run.sh up` | on the box | preflight → `docker compose build` → fetch models → **train+freeze every model's probe** → `docker compose up -d` → healthcheck |
| `./run.sh probes [--model M]` | on the box | (re)train + freeze + sign the probe(s) only — the "train once on the hosted models" step, run standalone |
| `./run.sh matrix [--remote URL]` | box **or** your machine | run the full B1→{B2,D2,F3}+C2 grid using the **frozen** probes; poll; pull artifacts |
| `./run.sh run <exp> --model M [--remote URL]` | anywhere | one experiment |
| `./run.sh status / logs / down` | anywhere / box | health & VRAM / loaded models & frozen probes / stop |

The server **refuses to start** if a configured model has no frozen probe (`up` builds them
first). Serving never trains — it only loads frozen weights and runs inference.

**"Single command" acceptance:** on a box with Docker + a CUDA GPU + network (or staged
models), `./run.sh up` returns a healthy server with zero further input. If network is
absent, it stops with a precise message naming the missing model paths (see §11 preflight).

---

## 3. Repository layout (the standalone package)

The thing you copy is **`phase5/capm-p5/`**. Full target tree (★ = new Phase-5 code, ⎘ =
vendored unchanged from existing phases):

```
phase5/capm-p5/
├── run.sh                         ★ single-command dispatcher (bash)
├── Makefile                       ★ convenience aliases for run.sh targets
├── README.md                      ★ orientation + the one command (doc set §9)
├── ARCHITECTURE.md                ★ distilled "why" (points at PHASE5_IMPLEMENTATION.md)
├── RUNBOOK.md                     ★ deploy / operate / remote-drive / teardown
├── AGENT_HANDOFF.md               ★ for a fresh Claude: state, invariants, next actions
├── requirements.txt               ★ pinned Python deps (server + ML + vendored needs)
├── .env.example                   ★ ports, paths, VRAM cap, token — copied to .env
├── .gitignore                     ★ ignores certs/, artifacts/, models cache, .env
├── docker/
│   ├── Dockerfile                 ★ CUDA + torch + deps; workdir + PYTHONPATH wiring
│   ├── docker-compose.yml         ★ 1 GPU service, volumes, restart=unless-stopped
│   └── entrypoint.sh              ★ launches uvicorn (1 worker) inside the container
├── config/
│   ├── models.yaml                ★ the 3 models + 7B: hf_id, dtype, layers, pooling
│   └── server.yaml                ★ host/port, mTLS cert paths, vram_cap_gb, pool policy
├── certs/                         ★ (generated by bootstrap; gitignored) CA + leaf + client
├── artifacts/                     (generated; gitignored)
│   ├── probes/                    FROZEN per-model probes: probe_<model>.pkl + .manifest.json (signed)
│   ├── features/                  B1 feature caches: feat_<model>_<dtype>.npz
│   └── results/                   experiment CSV/JSON + signed manifests (Phase-4 schema)
├── models/                        (generated; gitignored) HF cache mount target
├── src/
│   ├── p3/                        ⎘ vendored Phase-3 (sensors, data, claims, warrant…)
│   ├── p4/                        ⎘ vendored Phase-4 (models/whitebox, warrant/realized, exp/*)
│   └── p5/                        ★ NEW Phase-5 code
│       ├── __init__.py
│       ├── server/
│       │   ├── app.py             ★ FastAPI app + routes + lifespan (loads managers)
│       │   ├── schemas.py         ★ pydantic request/response models
│       │   ├── model_manager.py   ★ WhiteBoxLM load/evict/warm-pool + VRAM cap
│       │   ├── sensor_manager.py  ★ SupportSensor + NLISensor(+large) + schema, resident
│       │   ├── probe_store.py     ★ load FROZEN signed probes (read-only); verify signature
│       │   ├── scoring.py         ★ /v1/score primitive (the min-clamp warrant) using frozen probe
│       │   ├── experiment_runner.py ★ B1→{B2,D2,F3}+C2 DAG; runs p4 scripts as subprocesses
│       │   ├── jobs.py            ★ async job queue, status, artifact registry
│       │   ├── manifest.py        ★ reproducibility manifest + Ed25519 signing
│       │   ├── errors.py          ★ structured error envelope + typed resource exceptions
│       │   └── security.py        ★ mTLS context + bearer-token dependency
│       ├── client/
│       │   ├── capm_client.py     ★ HTTPS+mTLS client: submit/poll/pull
│       │   └── cli.py             ★ argparse CLI behind run.sh (run/matrix/status)
│       ├── bootstrap/
│       │   ├── preflight.py       ★ GPU/CUDA/VRAM/disk/network checks
│       │   ├── download_models.py ★ pull the 4 LLMs + 3 sensor models to models/
│       │   ├── train_probes.py    ★ load each model 1-by-1 → fit UsageProbe → FREEZE + sign → artifacts/probes/
│       │   └── gen_certs.py       ★ issue CA + server leaf + client cert (reuse Build-B)
│       └── tests/
│           ├── test_smoke.py      ★ load 14B, one forward, /score == realized.py
│           └── test_parity.py     ★ in-process pass == API pass (metrics + manifest)
└── docs/
    └── MODULES.md                 ★ per-file contract index (for a fresh implementer)
```

### 3.1 Vendoring plan (how the tree gets populated — a build step, not runtime)
Both sources are **already inside this `server/` folder** at `files/capm-testbed/` (paths
below are relative to the `server/` root you're working in):
- `src/p3/` ← copy from `files/capm-testbed/p3/`. Strip `__pycache__/` and the bulky
  `p3/results/` (not needed at runtime).
- `src/p4/` ← copy from `files/capm-testbed/p4/` (the corrected Phase-4 scorer,
  `models/whitebox.py`, `warrant/realized.py`, and `exp/p3_*.py`). Keep `exp/`, `models/`,
  `warrant/`, `sensors/`, `stats/`, `audit/`. `build_a/`/`build_b/`/`figures/` optional.
- `src/p5/` ← all new (this plan).
- **Import contract:** container sets `PYTHONPATH=/app/src`, so `import p3`, `import p4`,
  `import p5` resolve as top-level packages — exactly as the Phase-4 scripts expect.

---

## 4. The integration decision that keeps the science identical

The Phase-4 drivers (`p4/exp/p3_b1_probe_transfer.py`, …) **already** import `p3.*`/`p4.*`
and write CSVs to **relative** paths like `p4/results/ws3/b1/…`. Therefore:

> **The server runs the *unmodified* Phase-4 scripts as subprocesses**, with
> `cwd = <mounted artifacts run dir>` and `PYTHONPATH = /app/src`. Imports resolve to the
> vendored code; relative `p4/results/...` writes land on the mounted `artifacts/` volume.
> The runner captures stdout, reads the emitted CSV, attaches a signed manifest, returns JSON.

Why this is the right call:
- **Zero divergence from Phase-4.** The 14B/32B numbers are produced by literally the same
  code that produced the A10 7B numbers — only the `--model`/`--dtype` flags change. No
  re-implementation risk.
- **Parity check is free** (§8): "in-process vs API" is the same code path; the gate is that
  wrapping it in HTTP changed nothing.
- **Batching (perf, §7 of the architecture doc) is a later, optional milestone** that
  refactors the inner extract loop in `whitebox.py`/the runner — *after* correctness is
  locked. Correctness-first, speed-second.

The only new "science-touching" code is `scoring.py` (the `/v1/score` primitive), which must
reproduce `p4/warrant/realized.py` exactly and is unit-tested against it.

### 4.1 Frozen probe ≡ deterministic refit (why this changes no Phase-4 number)

The Phase-4 scripts construct the probe with `UsageProbe().fit(fe["final"][:len(yb1)], yb1)`
— a `LogisticRegression` (balanced, standardized) on the B1 feature cache. That fit is
**deterministic** given the same features + labels. So:

> **freezing the probe at bootstrap = persisting exactly the probe the Phase-4 scripts would
> have refit at runtime.** The frozen `probe_<model>.pkl` and an in-place refit produce
> identical coefficients (asserted by a test: `‖coef_frozen − coef_refit‖ < 1e-9`).

This lets us satisfy "train once, freeze, serve inference" **without** editing the Phase-4
inner loop: `scoring.py` and the on-demand serving load the frozen probe; the unmodified
`p4/exp/*` subprocesses still refit-from-cache (provably the same numbers). The B1 feature
cache (`artifacts/features/feat_*.npz`) is produced once during probe training and reused.

### 4.2 Probe lifecycle (train-once → freeze+sign → serve inference)

```
bootstrap (on the box, GPU):                 serving (remote, inference only):
  for model in [qwen14b, phi4, qwen32b, 7b]:   load model on demand (warm-pool)
    load WhiteBoxLM(model, bf16)               load FROZEN probe_<model>.pkl (verify sig)
    feats = extract(build_usage_examples,80,0) /v1/score, /v1/experiments/* run inference
    probe = UsageProbe().fit(feats.final, y)   NEVER retrain — read-only weights
    sign+save probe_<model>.pkl + manifest
    cache feat_<model>.npz ; unload model
```
- **Dataset = the relevant database:** `p3.sensors.probe_data.build_usage_examples(n_advisories=80, seed=0)`
  (context-driven vs parametric labels over the advisory corpus) — the same construction
  B1/B2/D2/F3 use. One probe per model (cross-model transfer fails ⇒ per-model is mandatory,
  not a preference — B1's own finding).
- **Frozen artifact:** the pickled `LogisticRegression` + `StandardScaler` + a spec
  (`model, dtype, layer=final, pooling=mean, feature_dim, train_n, seed`) + an **Ed25519
  signature** over a content hash → "frozen and signable at inference," per the probe's own
  design docstring.
- **Serving guarantee:** `probe_store` loads weights read-only and **verifies the signature**;
  a missing/!verified probe makes the model unservable (fail-closed).

---

## 5. Module-by-module specification

Each entry: **responsibility · key API · depends on · acceptance.** This is the contract a
fresh implementer builds to.

### server/app.py
- **Responsibility:** FastAPI app; `lifespan` loads `SensorManager` + `ModelManager` (lazy
  for LLMs), wires routes, applies `security` dependency to all `/v1/*`.
- **Routes:** `GET /healthz`, `GET /v1/gpu`, `GET /v1/models`, `POST /v1/models/{load,evict}`,
  `POST /v1/score`, `POST /v1/score/batch`, `POST /v1/experiments/{b1,b2,d2,f3,c2}`,
  `GET /v1/jobs`, `GET /v1/jobs/{id}`, `GET /v1/jobs/{id}/artifacts`, `GET /v1/version`.
- **Acceptance:** `uvicorn` serves; OpenAPI at `/docs`; one worker only.

### server/schemas.py
- **Responsibility:** pydantic models for every request/response in §4 of the architecture
  doc (ScoreRequest/Response, ExperimentRequest, Job, Manifest, GpuStatus…).
- **Acceptance:** every endpoint is fully typed; manifest embedded in every result.

### server/model_manager.py
- **Responsibility:** own the GPU + the **3-tier residency** (HOT in VRAM / PARKED in CPU RAM /
  COLD on disk). Wraps `p4.models.whitebox.WhiteBoxLM`. `get(hf_id,dtype)` returns a HOT model,
  promoting from PARKED (`~3–6 s`, `.to('cuda')`) or COLD (`30–120 s`, disk) as needed;
  `park(hf_id)` (VRAM→RAM, frees VRAM), `evict(hf_id)` (frees RAM), `list()`, `vram()`,
  `ram()`. **Dormant by default** (`resident_pool_max: 0`, `one_hot_model: true`): no HOT LLM
  at rest; an `idle_park_seconds` timer parks, an `idle_evict_seconds` timer (or RAM pressure)
  evicts. Loading the next model parks/evicts the current HOT one first (never two HOT).
  Sensors + frozen probes always resident. Serializes all GPU access behind one lock.
- **Resource preflight (production-safety):** before any promotion, check
  `required_gb ≤ vram_cap_gb − reserved`; if not, try parking the HOT model; if still short,
  raise `InsufficientVRAM` (→ structured 503, see `errors.py`). Same for RAM on park. Catch
  CUDA OOM, free, and surface the structured error rather than crashing the worker.
- **Depends on:** `WhiteBoxLM`, `errors`, `config/models.yaml`, `config/server.yaml`.
- **Acceptance:** at rest holds no HOT LLM (idle VRAM ≈ sensors only, or ≈0 if sensors on
  CPU); promotes 14B bf16 (~33–35 GB) / 32B bf16 (~66 GB, the sanctioned >soft_ceiling
  exception); parking frees VRAM and reactivation is seconds-not-minutes; a load that can't
  fit returns the structured `InsufficientVRAM` error (required vs available + suggested
  action), never a 500/worker-crash; `list()` reports HOT/PARKED/COLD per model + VRAM/RAM.
  See [`PHASE5_OPERATIONS.md`](PHASE5_OPERATIONS.md) §9.

### server/errors.py
- **Responsibility:** the structured error envelope + typed exceptions mapped to HTTP. One
  shape for every error (so clients can branch on `error` code): `{error, message, details,
  suggested_action, retry_after_s}`. Typed exceptions: `InsufficientVRAM`, `InsufficientRAM`,
  `ModelNotConfigured`, `ProbeMissing`/`ProbeUnverified`, `ModelLoadFailed`, `CeilingExceeded`,
  `JobFailed`, `Unauthorized`/`Forbidden` → 400/401/403/409/500/503 with the envelope.
- **Acceptance:** an over-budget model load yields HTTP 503 with the resource details (§6);
  no unhandled exception ever reaches the client as a bare 500.

### server/sensor_manager.py
- **Responsibility:** load once, hold resident: `SupportSensor(space="embedding")`
  (all-MiniLM-L6-v2), `NLISensor("cross-encoder/nli-deberta-v3-base")` **and**
  `…-large` (C2 scale), and the `schema_numeric_rule` module. Expose `support`, `faith`.
- **Acceptance:** sensors load on startup; `faith`/`support` callable; no per-request reload.

### server/probe_store.py
- **Responsibility:** load FROZEN probes read-only. `get(model) -> UsageProbe` from
  `artifacts/probes/probe_<model>.pkl`; **verify the Ed25519 signature** against the content
  hash; expose the probe spec (layer, pooling, dim, train_n, seed). Cache in memory. **Never
  fits.** `available() -> set[model]`.
- **Depends on:** `manifest` (verify), `p3.sensors.probe.UsageProbe`.
- **Acceptance:** loads a frozen probe and verifies its signature; a tampered pkl or missing
  signature → load refused (fail-closed); no training code path reachable from serving.

### server/scoring.py
- **Responsibility:** the atomic CAPM op. Given (ctx, field, value, w_decl, source_class,
  leaked_premise), compute `u` (the **frozen** probe over WhiteBox features), `s`, `faith`,
  `g=min(u,s,faith)`, `w_realized=min(w_decl, g·w_decl)` capped by source-class ceiling;
  report `binding` and the **raw probe inference** (`u`, P(context-driven), pooled-vector
  dim) so callers see the probing output alongside the warrant.
- **Depends on:** `model_manager` (features), `sensor_manager`, **`probe_store`** (frozen
  weights — never refits), `p4.warrant.realized`.
- **Acceptance:** for a fixed input, output **equals** `p4/warrant/realized.realized_warrant`
  to 1e-9 (unit test). The clamp can only *lower* warrant — asserted.

### server/experiment_runner.py  *(the heart of the matrix)*
- **Responsibility:** the B1→{B2,D2,F3} DAG + standalone C2. Runs the vendored Phase-4
  scripts as subprocesses (cwd=artifacts run dir, PYTHONPATH=/app/src), parses the emitted
  CSV into JSON, attaches a signed manifest, registers artifacts. Because probe training
  happened at **bootstrap**, the B1 feature cache + frozen probe already exist — B2/D2/F3
  reuse them; the runner re-runs B1 only if a cache is somehow absent (fail-safe, not the
  normal path).
- **Key API:** `run(exp, model, dtype, params) -> JobResult`; `b1_cache_path(model,dtype)`.
- **Depends on:** `jobs`, `manifest`, `probe_store`, vendored `p4/exp/*`.
- **Acceptance:** each of b1/b2/d2/f3/c2 produces the same CSV columns as Phase-4; uses the
  frozen probe/cache from bootstrap; artifacts retrievable.

### server/jobs.py
- **Responsibility:** asyncio job queue (GPU work serialized), `submit/get/list`, statuses
  `queued|running|done|error`, progress, artifact path registry, idempotency key
  `(exp,model,dtype,advisories,seed,code_sha)`.
- **Acceptance:** concurrent HTTP submits queue cleanly; a duplicate key returns the cached
  result unless `force=true`.

### server/manifest.py
- **Responsibility:** build the reproducibility manifest (model, dtype, layers, pooling,
  probe sha256, sensor model ids, schema flag, code git sha, seed, ts-from-request) and
  Ed25519-sign it (reuse the existing signing util / `cryptography`).
- **Acceptance:** every result carries a verifiable signature; tamper → verify fails (test).

### server/security.py
- **Responsibility:** uvicorn mTLS (server cert + require client cert from our CA) + a
  bearer-token FastAPI dependency. Reject missing/!valid cert or token with 401/403.
- **Depends on:** `certs/` (from `gen_certs.py`), `config/server.yaml`.
- **Acceptance:** a request without the client cert **or** without the token is refused.

### client/capm_client.py + client/cli.py
- **Responsibility:** httpx client with mTLS + token; `score`, `run_experiment`, `poll`,
  `pull_artifacts`. CLI maps `run.sh` subcommands to calls; writes artifacts to local
  `./artifacts/`.
- **Acceptance:** `run.sh matrix --remote URL` drives a remote server end-to-end and lands
  Phase-4-schema CSVs locally.

### bootstrap/preflight.py
- **Responsibility:** fail fast *before* the build: CUDA visible, free VRAM ≥ needed, disk
  ≥ ~200 GB for the model cache, Docker present, network-to-HF **or** models already staged.
- **Acceptance:** prints a green/red checklist; non-zero exit on any red with a fix hint.

### bootstrap/download_models.py
- **Responsibility:** pull to `models/` (HF cache): `Qwen/Qwen2.5-14B-Instruct`,
  `microsoft/phi-4`, `Qwen/Qwen2.5-32B-Instruct`, `Qwen/Qwen2.5-7B-Instruct`,
  `sentence-transformers/all-MiniLM-L6-v2`, `cross-encoder/nli-deberta-v3-base`, `…-large`.
  Resumable; verifies presence; skips what exists.
- **Acceptance:** idempotent; total ~140 GB; on no-network, errors naming the staged path it
  expects.

### bootstrap/train_probes.py  *(the "train once on the hosted models" step)*
- **Responsibility:** for each configured model (one at a time, to bound VRAM): load
  `WhiteBoxLM(model, bf16)`, extract B1 features from `build_usage_examples(80, seed=0)`,
  fit `UsageProbe`, **freeze** (pickle probe+scaler+spec), **Ed25519-sign** the content hash,
  write `artifacts/probes/probe_<model>.pkl` + `.manifest.json`, cache
  `artifacts/features/feat_<model>.npz`, then **unload** the model before the next.
- **Depends on:** `WhiteBoxLM`, `p3.sensors.probe.UsageProbe`, `p3.sensors.probe_data`,
  `manifest`.
- **Acceptance:** produces one signed frozen probe per model; the frozen coefficients match a
  fresh refit to 1e-9 (§4.1); reports per-model B1 test macro-F1 (sanity: ≥ chance, gap over
  static) so a bad train is caught at bootstrap, not at experiment time.

### bootstrap/gen_certs.py
- **Responsibility:** issue the mTLS CA, a server leaf (SANs: hostname/IP/localhost), and a
  client cert+key. Reuse Build-B's `certs.py` logic. Write to `certs/`.
- **Acceptance:** server starts with the leaf; the client cert authenticates; a foreign cert
  is rejected.

### tests/test_smoke.py & tests/test_parity.py
- **smoke:** load 14B, one forward, `/score` equals `realized.py`.
- **parity:** run one pass (e.g. B2, small N) **in-process** and **via the API**; assert
  metric equality + manifest field match. **This is the Phase-5 correctness gate.**

---

## 6. API surface (authoritative summary)

(Full bodies in `PHASE5_IMPLEMENTATION.md` §4; this is the build checklist.)

```
GET  /healthz                         GET  /v1/version
GET  /v1/gpu                          GET  /v1/models     (resident models + frozen-probe inventory)
GET  /v1/probes                       (frozen probes: model, spec, sig-verified, train F1)
POST /v1/models/load  {model,dtype}   POST /v1/models/evict {model}
POST /v1/score        {ctx,field,value,w_decl,source_class,leaked_premise}
        -> {u, s, faith, g, w_realized, binding, probe:{p_context_driven,dim}, manifest}
POST /v1/score/batch  {items:[…]}
POST /v1/experiments/b1 {model,dtype,advisories=80,seed=0}     -> {job_id}
POST /v1/experiments/b2 {model,dtype,advisories=60,seed=11}    -> {job_id}
POST /v1/experiments/d2 {model,dtype,advisories=30,seed=7}     -> {job_id}
POST /v1/experiments/f3 {model,dtype,advisories=30,seed=55}    -> {job_id}
POST /v1/experiments/c2 {}                                     -> {job_id}
GET  /v1/jobs   GET /v1/jobs/{id}   GET /v1/jobs/{id}/artifacts
```
All `/v1/*` require **mTLS client cert + bearer token**. Every result embeds the **signed
manifest**, and `/score` returns the **probe inference** alongside the warrant (the "probing
output" the caller is treated as having received from the host — §15). There is **no
train/fit endpoint**: probes are frozen at bootstrap and served read-only.

### 6.1 Structured error envelope (production-safety)

Every error — not just resource ones — returns this shape so clients branch on `error`:
```json
{ "error": "insufficient_vram",
  "message": "Cannot load qwen32b: needs 66.0 GB, only 31.2 GB free under the 70 GB cap.",
  "details": { "requested_model": "qwen32b", "dtype": "bf16",
               "required_gb": 66.0, "available_gb": 31.2, "vram_cap_gb": 70,
               "hot_model": "qwen14b", "parked_models": ["phi4"] },
  "suggested_action": "Park/evict the HOT model (POST /v1/models/park {\"model\":\"qwen14b\"}) then retry; the 32B needs the GPU to itself (sanctioned >50 GB exception).",
  "retry_after_s": 60 }
```
Error codes → HTTP: `insufficient_vram`/`insufficient_ram` → **503**; `model_not_configured`
→ 400; `probe_missing`/`probe_unverified` → **409** (fail-closed); `ceiling_exceeded` → 409;
`unauthorized`/`forbidden` → 401/403; `model_load_failed`/`job_failed` → 500 (still
enveloped). The server **never** returns a bare unhandled 500 — `errors.py` wraps everything,
and CUDA-OOM is caught, VRAM freed, and surfaced as `insufficient_vram` with the live numbers.
New ops endpoints this implies: `POST /v1/models/park {model}` (HOT→PARKED) alongside
`load`/`evict`; `GET /v1/models` reports HOT/PARKED/COLD + VRAM/RAM.

---

## 7. Configuration files (exact shapes)

`config/models.yaml`
```yaml
models:
  qwen14b:  { hf_id: Qwen/Qwen2.5-14B-Instruct, dtype: bf16, role: relay-14b }
  phi4:     { hf_id: microsoft/phi-4,           dtype: bf16, role: relay-14b }
  qwen32b:  { hf_id: Qwen/Qwen2.5-32B-Instruct, dtype: bf16, role: relay-bigger }
  qwen7b:   { hf_id: Qwen/Qwen2.5-7B-Instruct,  dtype: bf16, role: transfer-baseline }
layers: { static: 0, middle: mid, final: last }   # WhiteBoxLM.layers_of_interest()
pooling: mean
sensors:
  support_embed: sentence-transformers/all-MiniLM-L6-v2
  nli_base:      cross-encoder/nli-deberta-v3-base
  nli_large:     cross-encoder/nli-deberta-v3-large
```
`config/server.yaml`
```yaml
server: { host: 0.0.0.0, port: 8443 }
tls:    { ca: certs/ca.pem, cert: certs/server.pem, key: certs/server.key, require_client_cert: true }
auth:   { bearer_token_env: CAPM_P5_TOKEN }
host:                          # 128 cores / 256+ GB RAM — VRAM is the only tight resource
  cpu_threads: 32              # torch CPU threads for sensors + host-side data prep / tokenization
  sensor_device: cuda          # cuda (default, ~2.5 GB) | cpu (idle VRAM ≈ 0; uses the 128 cores)
gpu:                           # DORMANT-by-default, 3-tier residency HOT→PARKED→COLD (OPERATIONS §9)
  resident_pool_max: 0         # # of HOT models kept at rest (0 = none; lazy-load per request)
  one_hot_model: true          # at most ONE LLM in VRAM at a time (honors the ceiling)
  soft_ceiling_gb: 50          # preferred max per workload — both 14B ~33–35 GB
  vram_cap_gb: 70              # hard cap; admits the one 32B exception (~66 GB)
  idle_park_seconds: 120       # after 2 min idle: HOT→PARKED (VRAM→CPU RAM; frees VRAM; reactivates ~3–6 s)
  idle_evict_seconds: 1800     # after 30 min idle (or RAM pressure): PARKED→COLD (free RAM). null = keep parked
  cpu_park_max_models: 3       # parked models RAM may hold (256 GB holds ALL of ours, ~123 GB)
  ram_cap_gb: 200              # cap on parked-model RAM, leaving headroom within the 256 GB
paths:  { artifacts: /data/artifacts, models: /data/models }
# 256 GB RAM is what makes a long cooldown cheap: idle models PARK in RAM (VRAM freed in
# seconds, reactivation in ~3–6 s) instead of cold-reloading 30–64 GB from disk.
```
`.env.example`: `CAPM_P5_TOKEN=…`, `CAPM_P5_PORT=8443`, `HF_HOME=/data/models`, `CUDA_VISIBLE_DEVICES=0`.

`requirements.txt` (pinned at implementation time):
`torch` (CUDA build) · `transformers` · `scikit-learn` · `numpy` · `sentencepiece`
(DeBERTa-v3 tokenizer) · `cryptography` (Ed25519 manifest) · `fastapi` · `uvicorn[standard]`
· `pydantic` · `httpx` · `pyyaml` · `huggingface_hub` · `bitsandbytes` (optional; only if a
quantized fallback is ever needed — bf16 path doesn't require it).

---

## 8. Correctness gates (definition of "done right")

1. **Warrant parity:** `scoring.py` == `p4/warrant/realized.py` to 1e-9 (`test_smoke`).
2. **Pass parity:** in-process vs API metrics + manifest equal (`test_parity`). *This is the
   gate that proves the server added zero scientific change.*
3. **Monotonicity invariant:** `assert_no_cross_claim_term()` (locality) and the min-clamp
   (warrant can only drop) still hold — re-assert in tests.
4. **Schema match:** every experiment CSV has the Phase-4 columns, so the existing
   `p4/audit/*` and figure tooling work unchanged on Phase-5 output.
5. **Security:** request without client cert or token → refused.
6. **Frozen-probe fidelity:** `‖coef_frozen − coef_refit‖ < 1e-9` (§4.1); the probe signature
   verifies; **no fit path is reachable from serving** (probe_store is read-only).

---

## 9. The self-describing doc set (so a fresh Claude can take over)

Each ships **inside** `capm-p5/`:

- **README.md** — what Phase 5 is (the §0 sentence), the *one command*, the lifecycle
  picture (§1), and "if you are a new Claude, read AGENT_HANDOFF.md".
- **ARCHITECTURE.md** — the distilled "why": white-box constraint, B1-root DAG, min-clamp,
  the 3-model matrix; defers detail to `../PHASE5_IMPLEMENTATION.md`.
- **RUNBOOK.md** — step-by-step: preflight, `./run.sh up`, `warm`, remote `matrix`, pulling
  results, `status/logs/down`, and recovery (container restart, cache reuse).
- **AGENT_HANDOFF.md** — *for an independent Claude session*: current build state, the
  **invariants that must never break** (§10), the module contracts (`docs/MODULES.md`), the
  next unbuilt milestone, and the four locked decisions (HTTP-only/own-access, Docker,
  Qwen14B+Phi4+Qwen32B, faith-deferred).
- **docs/MODULES.md** — the §5 per-file contract table, kept in sync with the code.

**Writing rule for these docs:** every file states its *purpose, inputs, outputs, and
acceptance* at the top, so the folder is understandable without this plan.

---

## 10. Invariants a future implementer MUST NOT break

1. **White-box only for `u`.** Hidden states ⇒ `transformers` + `output_hidden_states=True`.
   **Never** route the usage signal through vLLM/Ollama/a chat API. (Generation-only paths
   may use a faster engine later, but not the probe path.)
2. **The warrant is degrade-only.** `w = min(w_decl, g·w_decl)`, `g=min(u,s,faith)`, capped
   by source-class. Sensors inform; they never inflate.
3. **B1 is the root.** B2/D2/F3 reuse the B1 `feat_*.npz` cache + the resident model; do not
   recompute features per pass.
3a. **Probes are frozen at bootstrap, served read-only.** Train once per model; persist +
   sign; serving loads and verifies but **never re-fits**. One probe per model (transfer
   fails). No `/fit` endpoint exists.
4. **Don't change the Phase-4 science.** Run the vendored `p4/exp/*` unchanged; new code is
   plumbing (serving, manifest, transport) — verified by the parity gate.
5. **Faith fix is OUT of scope** (decided). D2/F3 carry the Phase-4 faith caveat forward
   verbatim; do not silently "fix" it here.
6. **Shared box etiquette:** VRAM cap < 96 GB, one GPU-owning container, writes only under
   the mounted `artifacts/` + `models/`.
7. **bf16 native** for all of 14B/32B (no quantization caveat); 72B excluded.

---

## 11. One-time-access checklist & preflight (do not waste the window)

Confirm *during* the access window, in this order — `preflight.py` automates the checks:

1. **GPU/CUDA** visible; ≥ ~70 GB free VRAM (32B needs ~64). 
2. **Disk** ≥ ~200 GB free for the model cache (`models/` ~140 GB + working space).
3. **Docker** usable (in the `docker` group / GPU runtime installed). *Contingency:* if
   Docker is unavailable, fall back to a bare venv mode (`./run.sh up --no-docker` builds a
   venv and runs uvicorn directly) — keep this path documented as insurance for a one-shot
   window.
4. **Network to Hugging Face?** ← **the single biggest risk.** If the box is air-gapped,
   `./run.sh up` cannot download 140 GB. Mitigation: pre-stage the models into `models/`
   (download on a connected host, ship the cache), and bootstrap detects + skips download.
   **Decide this before you go.**
5. **Inbound port** reachable from your machine (so remote driving works); note host/IP.
6. **Probe-training time budget.** `up` loads each model once and extracts B1 features
   (build_usage_examples, 80 advisories) before fitting — order minutes per model on GPU,
   so ~15–40 min total for the four models on top of the ~140 GB fetch. Budget the window
   accordingly; it is one-time.
7. After `up`: confirm `/v1/probes` lists a signed probe per model; run `test_smoke` + a tiny
   `test_parity`; copy `certs/client.*` back to your machine.

---

## 12. Build milestones (implementation order + acceptance)

| M | Milestone | Files | Acceptance gate |
|---|-----------|-------|-----------------|
| **M0** | **Assemble standalone skeleton** | tree §3, vendor p3+p4, `run.sh`, docker, config, doc stubs | `docker compose build` succeeds; `import p3,p4,p5` works in-container |
| **M1** | **Core service up** | app, schemas, model_manager, sensor_manager, security, manifest | `./run.sh up` healthy; loads 14B bf16; mTLS+token enforced |
| **M2** | **Probe bootstrap (train+freeze)** | bootstrap/train_probes.py, probe_store.py | one signed frozen probe per model; frozen ≡ refit (1e-9, §4.1); server refuses to start with a probe missing |
| **M3** | **Scoring primitive** | scoring.py, test_smoke | `/v1/score` == `realized.py` (1e-9); response carries the probe inference |
| **M4** | **Experiment DAG** | experiment_runner, jobs, the b1/b2/d2/f3/c2 routes | each pass runs via API using the frozen probe; CSVs match Phase-4 schema |
| **M5** | **Remote client + parity** | capm_client, cli, test_parity, RUNBOOK | `matrix --remote` drives end-to-end; parity gate passes |
| **M6** | **Run the matrix** | — (operation) | B1/B2/D2/F3(+C2) over Qwen14B + Phi-4 + Qwen32B; 7B↔14B transfer; ledger written |
| **M7** | **Perf (optional)** | batching in whitebox/runner | batched forward; measured speedup; numbers unchanged vs M6 |

**Off-box vs on-box.** All *code* (M0–M5) is buildable and wiring-testable **off the box** —
use a tiny stand-in LM (e.g. `distilgpt2`, already a Phase-3 dep) so `train_probes`/`scoring`/
the DAG run on CPU for tests. The **96 GB box is needed only at run time, for two things**:
the **real probe training (M2 run)** on the actual 14B/32B models, and the **matrix (M6 run)**.
Both happen on the still-running daemon — M2's training is part of `./run.sh up` during the
access window; M6 is triggered remotely afterward. So the access window must reach: *deploy →
train+freeze probes → server healthy & remotely reachable.* Everything else is remote.

---

## 13. Risks specific to "standalone + one-shot deploy"

| Risk | Mitigation |
|------|------------|
| **Air-gapped box (no HF download)** | pre-stage `models/`; bootstrap detects & skips; preflight flags it (§11.4) — *resolve before the window* |
| **Window closes mid-download (140 GB)** | resumable downloads; idempotent `./run.sh up`; or pre-stage |
| **Docker unavailable on the box** | `--no-docker` venv fallback path (§11.3) |
| **Server orphaned after you disconnect** | `restart: unless-stopped` (daemon survives); `./run.sh down` to stop; RUNBOOK documents `docker ps` |
| **Port not reachable from your machine** | confirm inbound during the window (§11.5); else you can't drive it remotely |
| **Folder copied without the big caches** | `models/` & `artifacts/` are *generated*, gitignored, and rebuilt by bootstrap — the copy stays small/standalone |
| **Faith caveat misread as fixed** | invariant §10.5 + explicit note in every D2/F3 result manifest |

---

## 14. Phase-5 Definition of Done

1. Standalone `capm-p5/` deploys with `./run.sh up` in one command — which **trains and
   freezes one signed probe per model** as part of bootstrap.
2. B1/B2/D2/F3 (+C2) produce results for **Qwen2.5-14B, Phi-4, Qwen2.5-32B** at native bf16,
   in the Phase-4 CSV schema, plus 7B↔14B transfer (B1) and Qwen-14B↔32B scale — all using
   the **frozen** probes, served inference-only.
3. Parity gate + frozen-probe fidelity gate pass (server added no scientific change).
4. Results pulled to your machine; a Phase-5 results ledger (house style) written, with the
   faith caveat carried forward verbatim and cross-arch / scale deltas reported honestly.
5. The doc set lets an independent Claude session rebuild/operate from the folder alone.

---

## 15. The hosted-prober hypothetical (what the endpoint actually models)

**The framing:** the API is treated as if **the calling/verifying agent received the usage
probe result `u` directly from the model host** — i.e., the host attests its own `u`, and the
caller proceeds as though the probing was done for it.

**Why this is the *intended* CAPM deployment, not a shortcut:**
- `u` is, by design (the probe's own docstring), a **runtime-internal sensor**: it reads
  hidden states, so it "runs only where the model does (open-weight / attested / re-executing
  verifier). Its placement is recorded in the manifest and it sits under the min-clamp."
- A real cross-agent pipeline *cannot* recompute `u` verifier-side without the weights +
  per-forward activations. So the relay/host computes it and ships the (signed) result. **Our
  endpoint is exactly that host.**
- `s` (embedding support) and `faith` (NLI) are **verifier-side** (text-only) — the caller
  can and does recompute them independently. Only `u` is "trusted from the host."

**The security consequence — stated precisely (this is the crux of the critique):**
- `g = min(u, s, faith)`, `w = min(w_decl, g·w_decl)`, capped by the source-class ceiling.
- A **lying host** can only *inflate* `u`. That can raise `g` only up to where the
  caller's **independent** `s`/`faith` still cap it, and can raise `w` only up to `w_decl` —
  which is itself **bounded by the source-class ceiling**. So **a dishonest probe cannot push
  a claim above what its origin class already permits.** The by-construction guarantee
  (P1/P2: ASR=0 modulo origin-class capture) does **not** rest on `u`.
- What a lying host *can* cost you: the **localization benefit** of `u` for the
  **usage-binding** cases — those where *only* `u` would have degraded the claim (the
  truths-only synthesis attack F3 flags as "bound by usage"). For those, trusting the host's
  `u` is a real trust assumption, discharged in a production system by attestation /
  re-execution, and **recorded in the manifest**.

**For Phase 5 specifically:** the experiments run under an **honest host** (we host the
models and compute `u` faithfully) — exactly the setting in which sensor efficacy is
*measured*. So the hypothetical is sound for the experiments, and the paragraph above is the
honest statement of what it would (and would not) guarantee if the host were adversarial.

---

## 16. Feasibility critique (honest)

**Engineering — green:**
- Per-model probe training is cheap (logistic regression); the cost is feature extraction (a
  forward pass over ~80 advisories of labeled examples) — minutes per model at bf16.
- Freezing + signing is trivial and matches the "frozen and signable" design.
- Inference serving is fast: one forward pass + a frozen LR + two small sensors.
- Subprocess integration ⇒ the science is byte-identical to Phase-4; near-zero
  reimplementation risk; the parity gate proves it.

**Engineering — yellow (manageable):**
- **VRAM choreography:** 32B (~64 GB) cannot co-reside with both 14B; warm-swap handles it
  but the pool policy must be right (≤2×14B *or* 1×32B). Already in the design.
- **One-shot window load:** ~140 GB fetch + ~15–40 min probe training. The air-gap /
  time-budget question (§11) is the real gate, not the code.
- **Docker + GPU passthrough on a shared box** assumes docker-group / nvidia-runtime access;
  the `--no-docker` venv fallback de-risks the single window.

**Scientific — green, with one carried caveat:**
- Frozen probe ≡ deterministic refit ⇒ the 14B/32B numbers come from the same code as the
  A10 7B numbers.
- One probe per model is *required* (cross-model transfer fails) — the design already does it.
- **The faith-sensor scale degradation is NOT fixed** (deferred by decision). D2/F3 at
  14B/32B will likely still show the loose-end behavior premise=ctx produces on structured
  key:value text. We carry the Phase-4 caveat **verbatim** — bigger models do not make it go
  away, and implying otherwise would break the honesty rule.

**Where this could be *over*-built (don't):**
- **No train/fit endpoint.** Frozen + read-only is safer (no warrant inflation via
  retraining) and truer to the design. Keep probes immutable post-bootstrap.
- **Never ship raw hidden states / all-layers tensors.** The pooled vector / scalar `u` (+
  P(context-driven)) is all the caller needs.
- **Don't trust `u` for the security guarantee** — it's a localizer. The guarantee is the
  min-clamp + source-class ceiling + Ed25519, which hold regardless of `u`.

**Net:** the idea is feasible and unusually well-matched to the architecture — it *is* how
CAPM intends `u` to be deployed. The only hard external dependency is the air-gap/time
question for the one-shot window; the only scientific limitation is the deliberately-deferred
faith caveat.

---

## 17. What I need from you before the access window

- **Network at the box?** online (bootstrap downloads) vs air-gapped (pre-stage `models/`). ← decide first
- **Inbound port** you can reach from your machine (default 8443) + the box's host/IP.
- **Docker confirmed** usable (else we lean on the `--no-docker` venv fallback).
- **Time budget** for the one-time window (~140 GB fetch + ~15–40 min probe training).

> No code is written yet. On your go-ahead I start at **M0** (assemble the standalone
> skeleton: vendor p3+p4, scaffold p5, `run.sh`, Docker, config, doc set) — all buildable
> off the box. The 96 GB box is then needed at run time for just two things: **M2** (train +
> freeze the real probes, part of `./run.sh up`) and **M6** (the big-model matrix, triggered
> remotely).
