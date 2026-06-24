# Phase 5 — Agent Guide (READ THIS FIRST)

**You are Claude, running on the target GPU server, with this `server/` folder pasted in**
(the user copied only `phase5/server/`; the thin `client/` side stays on their machine).
This file orients you so the user can directly ask you to *implement components* and *run
scripts*. Read it fully before acting. The three deep-reference docs are:

- [`PHASE5_IMPLEMENTATION.md`](PHASE5_IMPLEMENTATION.md) — architecture & rationale ("why").
- [`PHASE5_BUILD_PLAN.md`](PHASE5_BUILD_PLAN.md) — the build spec: file tree, per-module
  contracts, milestones, config ("what to build, in what order").
- [`PHASE5_OPERATIONS.md`](PHASE5_OPERATIONS.md) — runbook: connect, run, monitor, debug,
  recover, and the VRAM/lifecycle Q&A ("how to operate").

When in doubt about a detail, those are authoritative; this guide is the map.

---

## 1. Purpose of Phase 5 (one paragraph)

Re-run the **exact Phase-4 experiments — B1, B2, D2, F3, plus C2 — on bigger models at
native bf16**, by building a **standalone, single-command inference server** that lives on
this box. On deploy it loads each model once, **trains and freezes that model's usage probe**,
and then serves an HTTPS API that, on request, runs the experiments on the hosted models and
returns the results **plus the probe's inference output**. The probes are trained once and
used forever after through the API. Deliverables: (a) frozen, signed per-model probes;
(b) the 14B/32B results in the Phase-4 CSV schema; (c) the cross-architecture (Qwen↔Phi-4) and
scale (14B↔32B) reads. The server is plumbing; the science is unchanged from Phase 4.

**The hosted-prober framing:** the API stands in for *the model host attesting its own usage
signal `u`* to a calling/verifying agent — exactly how CAPM intends `u` (a white-box,
runtime-internal sensor) to be deployed. See `PHASE5_BUILD_PLAN.md` §15 for the security
analysis (short version: even a dishonest host can't push a claim above its source-class
ceiling; `u` only ever *informs* under the min-clamp).

---

## 2. Target system (this machine)

- **~128 CPU cores**, **256+ GB RAM**, **96 GB VRAM** (single GPU, shared multi-user box).
- Implication: VRAM is the binding resource; **RAM and CPU are abundant** and we exploit them
  (model *parking* in RAM, parallel CPU sensor/data work). See §4 residency.
- Access is treated as **HTTP-only after deploy** (you do the one-time on-box bootstrap; the
  user drives remotely thereafter). Docker with NVIDIA GPU passthrough is the runtime.

---

## 3. How this folder is structured

This is `phase5/server/` (the only part copied to this box):
```
server/
├── PHASE5_AGENT_GUIDE.md      ← you are here (entry point)
├── PHASE5_IMPLEMENTATION.md   architecture / why
├── PHASE5_BUILD_PLAN.md       build spec: file tree, module contracts, milestones, config
├── PHASE5_OPERATIONS.md       runbook + VRAM/lifecycle Q&A
├── tests/                     barebones connectivity test server (no models) — run to prove reachability
│   ├── app.py · run_server.sh · test_server.py · requirements.txt
├── files/capm-testbed/
│   ├── p3/   ← vendored Phase-3 code (sensors, data, claims, warrant) — PRESENT
│   └── p4/   ← vendored Phase-4 code (models/whitebox, warrant/realized, exp/*) — PRESENT
├── reference_codes/ · reference_documents/ · *PHASE3* docs   research/history background
└── (capm-p5/  ← the standalone deployable package YOU will assemble at M0; does not exist yet)
```
**Both `p3` and `p4` source are already here** (in `files/capm-testbed/`). Your M0 job is to
assemble the deployable package `capm-p5/` that vendors them in next to new `p5/` code — the
full target tree is in `PHASE5_BUILD_PLAN.md` §3. The matching **client** (connection check
now; remote driver later) lives in `phase5/client/` on the user's machine, not here.

---

## 4. System architecture (what you're building)

- **One GPU-owning FastAPI service** (uvicorn, 1 worker), all CUDA work serialized behind an
  internal queue. Runs in Docker, GPU passthrough, artifacts + HF cache bind-mounted.
- **White-box engine** = `p4.models.whitebox.WhiteBoxLM` (`transformers`,
  `output_hidden_states=True`). This is the **only** path that yields the hidden states the
  usage probe reads — never vLLM/Ollama/chat APIs for `u`.
- **Frozen per-model probes:** trained once at bootstrap (load model → extract B1 features
  from `build_usage_examples` → fit `UsageProbe` → pickle + Ed25519-sign), served read-only.
  No train/fit endpoint. (Equivalent to the deterministic refit the Phase-4 scripts do, so
  numbers are identical — `PHASE5_BUILD_PLAN.md` §4.1.)
- **Sensors** (resident, cheap ~2.5 GB): support (all-MiniLM-L6-v2), NLI (DeBERTa-v3
  base+large), schema rule. Can optionally run on **CPU** (128 cores) to make idle VRAM ≈ 0.
- **Experiments run as subprocesses** of the unmodified `p4/exp/*` scripts (cwd = mounted
  artifacts dir, `PYTHONPATH` at vendored code), so the science is byte-identical to Phase-4;
  the server parses their CSV, attaches a signed manifest, returns JSON.
- **Three-tier residency (uses the 256 GB RAM) — the key hardware-driven design:**
  - **HOT** = weights in VRAM, serving (~33–35 GB a 14B; ~66 GB the 32B).
  - **PARKED** = weights moved to **CPU RAM** (`model.to('cpu')`, VRAM freed in seconds,
    reactivation `.to('cuda')` in ~3–6 s). 256 GB RAM holds *all* our models parked at once
    (~123 GB). This is what makes a long idle window cheap.
  - **COLD** = on disk only (first load ~30–120 s).
  - Policy: after a job/idle, **park** (free VRAM fast → good shared-box citizen); fully
    **evict** from RAM only after a long window or under RAM pressure. **One model HOT at a
    time.**
- **VRAM ceiling:** routine 14B work ≤ ~50 GB; **Qwen2.5-32B bf16 (~66 GB) is the single
  sanctioned exception**, run alone/sequentially (hard cap 70 GB).
- **Security/transport:** HTTPS + mTLS (Build-B CA) + bearer token; every result carries a
  signed manifest.
- **Robust resource errors:** load requests that can't fit return a **structured** error
  (insufficient resources / requested model / required vs available GB / suggested action) —
  see `PHASE5_BUILD_PLAN.md` §6 error envelope and `PHASE5_OPERATIONS.md` §8.

Models: **Qwen2.5-14B-Instruct** + **microsoft/phi-4 (14B)** + **Qwen2.5-32B-Instruct**
(+ Qwen2.5-7B for the B1 7B↔14B transfer), all native bf16.

---

## 5. Locked decisions — DO NOT relitigate

1. **HTTP-only deploy**, one on-box bootstrap then remote driving. Docker.
2. **Models:** Qwen2.5-14B + Phi-4 + Qwen2.5-32B (+7B for transfer), native bf16.
3. **Faith-sensor fix is DEFERRED** — D2/F3 carry the Phase-4 faith caveat *verbatim*; do not
   "fix" it.
4. **Probes frozen at bootstrap, served read-only** (one per model; transfer fails).
5. **Dormant by default**, one model HOT at a time, **32B is the one >50 GB exception**.
6. **256 GB RAM → parking tier** (long cooldown is cheap; reactivation in seconds).

## 6. Invariants you MUST NOT break (`PHASE5_BUILD_PLAN.md` §10)

White-box-only for `u` · warrant is degrade-only (`w=min(w_decl,g·w_decl)`, `g=min(u,s,faith)`,
source-class ceiling) · B1 is the root · probes frozen/read-only · **don't change the Phase-4
science** (run `p4/exp/*` unchanged; new code is plumbing, proven by the parity gate) · faith
fix out of scope · one model HOT at a time / 50 GB ceiling / 32B exception · shared-box
etiquette (cap VRAM, write only under mounted `artifacts/` + `models/`).

---

## 7. What to implement (milestones — full contracts in `PHASE5_BUILD_PLAN.md` §5, §12)

| M | Build | Needs GPU? |
|---|-------|-----------|
| **M0** | Assemble `capm-p5/` skeleton: vendor `p3`+`p4` from `files/capm-testbed/`, scaffold `p5/`, `run.sh`, Docker, config, doc set | no (CPU) |
| **M1** | Core service: `app`, `model_manager` (3-tier residency + structured errors), `sensor_manager`, `security`, `manifest` | load test only |
| **M2** | Probe bootstrap: `bootstrap/train_probes.py`, `probe_store.py` — train+freeze+sign one probe per model | **yes (run)** |
| **M3** | `scoring.py` (`/v1/score` == `p4/warrant/realized.py`, returns probe inference) + `test_smoke` | load test |
| **M4** | `experiment_runner` + `jobs` + `/v1/experiments/*` routes (run `p4/exp/*` as subprocesses) | for real runs |
| **M5** | Remote `client` + `cli` + `test_parity` (in-process == API) | for parity |
| **M6** | **Run the matrix** over the 3 models (+7B transfer); write the Phase-5 ledger | **yes (run)** |
| **M7** | (optional) batched forward passes for speed; numbers unchanged | yes |

Code for M0–M5 is wiring-testable on CPU with a tiny stand-in LM (`distilgpt2`); the GPU is
needed only to *run* M2 (real probe training) and M6 (the matrix).

---

## 8. What scripts to run, in what order

**Step 0 — connectivity sanity (optional, no build needed):** prove the box serves HTTP and is
reachable using the barebones test server before investing in the build.
```bash
cd tests && ./run_server.sh        # serves on :8000 (no models); from the client run check_connection.py
```

Once `capm-p5/` is built (M0–M5 done):

```bash
cd capm-p5/
cp .env.example .env            # set CAPM_P5_TOKEN, port, HF_HOME, CUDA_VISIBLE_DEVICES
./run.sh up                     # preflight → build image → fetch models → TRAIN+FREEZE probes → serve (daemon)
./run.sh status                 # confirm healthy + /v1/probes lists a signed probe per model
./run.sh matrix                 # run B1/B2/D2/F3(+C2) over all models; pull artifacts
```
- `./run.sh up` is **idempotent** — re-running skips finished build/download/probe steps.
- `./run.sh probes [--model M]` retrains a probe alone. `down`/`logs`/`status` for ops.
- Bootstrap order is enforced: **probes are trained before the server accepts experiment
  requests** (it fail-closes if a model lacks a signed probe).
- Preflight gate before anything heavy: **GPU/CUDA, ≥~200 GB disk, network-to-HF (or
  pre-staged `models/`), Docker.** If air-gapped, stage the model cache first.

---

## 9. How to debug / recover (full tables in `PHASE5_OPERATIONS.md` §7–§8)

First checks for the common cases:
- **Server won't start** → a frozen probe missing (`./run.sh probes`), or cert/port; `logs`.
- **Insufficient VRAM on load** → the API returns a structured error (required vs available
  GB + suggested action); evict/park the HOT model, or for 32B ensure the GPU is free.
- **OOM mid-run** → catch, free, retry the job (idempotent key); reduce batch if batching on.
- **Job stuck** → `logs` + `nvidia-smi` (co-tenant contention?); `down && up`, re-submit.
- **After crash/reboot** → daemon auto-restarts; model cache + frozen probes survive on the
  mounts, so recovery never retrains/redownloads unless an artifact is actually missing.

**Recovery principle:** the two expensive assets — the ~140 GB model cache and the frozen
signed probes — live on mounted volumes and survive restarts.

---

## 10. How to work with the user here

- The user will ask you to **implement specific components** and **run scripts**. Match the
  request to a milestone (§7) and build to the module contract in `PHASE5_BUILD_PLAN.md` §5.
- **Default first action if asked to "start":** M0 (assemble `capm-p5/`). It needs no GPU.
- **Before any heavy GPU step** (M2 probe training, M6 matrix): run preflight and confirm the
  air-gap/disk/Docker facts (§8).
- **Honor the invariants** (§6). If a request would break one (e.g. "fix the faith sensor",
  "use vLLM for the probe", "retrain at request time"), flag it rather than silently doing it.
- **Keep the science byte-identical:** run `p4/exp/*` unchanged; verify with the parity gate.
- Report failures honestly with the actual output; this project's norm is no overclaiming.

> TL;DR: read this guide → read `PHASE5_BUILD_PLAN.md` for contracts → start at M0 → bootstrap
> (`./run.sh up`, which trains+freezes probes) → run the matrix → pull results. VRAM is the
> only tight resource; use RAM (parking) and CPU (sensors/parallel prep) freely.
