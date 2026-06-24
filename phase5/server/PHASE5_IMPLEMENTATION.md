# Phase 5 — Inference-Server Implementation Plan

**Status:** engineering plan only — *no implementation yet.*
**Target hardware:** single shared host — **~128 CPU cores · 256+ GB RAM · 96 GB VRAM**
(one GPU). VRAM is the only tight resource; RAM/CPU are abundant and exploited (model
*parking* in RAM, CPU sensors/prep) — see §3.
**Scope:** stand up a dedicated inference service that hosts the relay models
(Qwen2.5-14B / Phi-4 / Qwen2.5-32B) and the CAPM sensor stack, exposes API endpoints, and
runs the **B1 / B2 / D2 / F3** (+C2) passes server-side, returning small JSON verdicts
(never raw tensors).

> This document refines the original idea ("host a model, expose an API, let external
> systems call it to run B1/B2/D2/F3") into a concrete architecture, **and critiques it
> honestly** (see §11). The short version of the critique: the instinct to run the
> pipeline *server-side, co-located with the GPU* is correct and is what makes the design
> sound. The two things to get right are (a) make it a **purpose-built scoring/experiment
> service**, not a generic LLM chat gateway, and (b) on a shared box, **own exactly one
> GPU-resident process**; since access is HTTP-only the port must be exposed, so secure it
> with TLS + mTLS + a bearer token rather than relying on a tunnel.

---

## 0. What B1 / B2 / D2 / F3 actually are (grounding)

The plan only makes sense against what these passes compute. From the Phase-4 drivers
(`p4/exp/p3_b1_probe_transfer.py`, `…b2…`, `…d2…`, `…f3…`, `…c2…`):

| Pass | What it computes | White-box LLM? | Depends on |
|------|------------------|----------------|------------|
| **B1** *(root)* | Trains the usage probe `u` on **mean-pooled answer-span hidden states** at static/middle/final layers; text-only controls (BoW, static-L0, overlap-oracle); OOD + cross-size transfer. **Caches features → `feat_<model>_<dtype>.npz`.** | **Yes** (forward pass, `output_hidden_states=True`) | — |
| **B2** | Reuses the **B1 cache** to train the probe, then forward-passes new claims to get `u` as a fabrication detector (AUC by subtlety: blatant/plausible/added; mean vs min pooling). | **Yes** | B1 cache |
| **D2** | Security–utility **frontier**: full `g = min(u,s,faith)` vs content-blind baseline and single-sensor refs; sweeps τ; ASR@retention and retention@ASR. Also a relay *generation* sample. | **Yes** (forward + `generate`) | B1 cache |
| **F3** | **Adaptive adversary** (black→grey→white knowledge + truths-only synthesis) scored through the corrected stack; residual ASR@ACCEPT / @DOWN-WEIGHT and the binding sensor. | **Yes** | B1 cache |
| **C2** | Faith sensor at scale (DeBERTa base/large), premise=ctx + schema numeric rule: genuine-contradiction recall, valid-abstraction FPR, CVSS-band recall. | **No** (NLI + schema only) | — |

**Two facts drive the entire architecture:**

1. **B1 is the single point of expensive computation that everything reuses.** The probe
   itself is a cheap logistic regression; the cost is the LLM forward passes. Load the
   model once, build the B1 cache once, and B2/D2/F3 become incremental.
2. **The usage signal `u` requires internal hidden states.** That forecloses vLLM, Ollama,
   TGI, and every "chat-completions" gateway for the `u` path. Only a `transformers`
   model with `output_hidden_states=True` works. This is non-negotiable and is the reason
   a *generic* model API is the wrong abstraction (§11).

The CAPM warrant itself is unchanged: `w = min(w_decl, g · w_decl)`, `g = min(u,s,faith)`,
monotone non-increasing, capped by origin source-class. The server **computes the
sensors; it never inflates the warrant.**

---

## 1. Overall system architecture

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  96 GB VRAM host  (shared, multi-user)                                 │
  │                                                                        │
  │   ┌────────────────────────────────────────────────────────────────┐  │
  │   │  capm-p5-server  (ONE process, single GPU owner)                 │  │
  │   │                                                                  │  │
  │   │   FastAPI / uvicorn (1 worker)                                   │  │
  │   │        │                                                         │  │
  │   │        ▼                                                         │  │
  │   │   Request queue ──► Inference worker (asyncio, GPU-serialized)   │  │
  │   │                          │                                       │  │
  │   │     ┌────────────────────┼─────────────────────────┐            │  │
  │   │     ▼                    ▼                          ▼            │  │
  │   │  ModelManager       SensorManager            ExperimentRunner    │  │
  │   │  • WhiteBoxLM(s)    • SupportSensor (embed)   • B1 (root)         │  │
  │   │    resident on GPU  • NLISensor (DeBERTa)     • B2/D2/F3 (reuse)  │  │
  │   │    warm-swap pool   • schema numeric rule     • C2 (no LLM)       │  │
  │   │  • probe cache      (resident on GPU)         • DAG + cache       │  │
  │   └────────────────────────────────────────────────────────────────┘  │
  │            │ exposed HTTPS port (TLS + mTLS + bearer token)            │
  │   ┌────────┴───────────┐   /scratch/panora/CAPM-P5/  (bind-mounted)    │
  │   │ HF model cache      │   • feat_*.npz  (B1 feature cache)           │
  │   │ results / artifacts │   • results CSV/JSON + signed manifests      │
  │   └────────────────────┘   (Docker container, --gpus)                  │
  └───────────────────────────────┬────────────────────────────────────────┘
                                   │  HTTPS + mTLS  (HTTP-only access; no SSH/tunnel)
                                   ▼
                        External orchestrator (thin client)
                        (submits jobs, polls, stores verdicts)
```

**Design principles**

- **Orchestration lives server-side, next to the GPU.** A request says "run D2 on
  Qwen2.5-14B"; the server runs the whole pass and returns a compact result. The client
  never sees hidden states.
- **Return verdicts, not tensors.** Responses are JSON: sensor scores, warrants, AUCs,
  frontier points, plus a reproducibility manifest. The only endpoint that returns a
  vector returns the **pooled** feature (~3.5–5k floats), never the raw all-layers tensor.
- **One GPU owner.** A single process holds the resident models. uvicorn runs **one
  worker** (multiple workers would each try to load 29 GB). GPU work is serialized through
  an internal queue; HTTP concurrency is fine, GPU concurrency is not.
- **Reuse is first-class.** The B1 feature cache and the loaded model are the two assets
  the server exists to amortize.

---

## 2. Model serving strategy

### 2.1 The white-box engine (mandatory for u)

The relay LLM is served via the existing `WhiteBoxLM` wrapper (`transformers`,
`output_hidden_states=True`, bf16 on CUDA). On 96 GB, **14B runs bf16 native** (~29.5 GB)
— no quantization, so **no quantization caveat** (the Phase-4 A10 had to 8-bit 14B; that
limitation is gone).

VRAM budget (bf16, weights only; add ~2–4 GB working set + KV cache):

| Model | bf16 VRAM | Fits 96 GB? | Notes |
|-------|-----------|-------------|-------|
| 7B | ~15 GB | yes | Phase-4 baseline; keep for 7B↔14B transfer |
| **14B** | **~29.5 GB** | **yes (native)** | Phase-5 primary target |
| 32B | ~64 GB | yes (one at a time) | optional Tier-3 |
| 72B | ~145 GB | no bf16 → 8-bit ~72 GB | low marginal value; advise against |

### 2.2 Should you also run vLLM for generation? — No, not initially

D2 needs *text generation* (the relay path), and plain `transformers.generate` is slower
than vLLM. The temptation is to run **vLLM for generation + transformers for hidden
states**. Honest assessment:

- **Against (default):** at the experiment scale here (30–80 advisories, a few hundred
  claims, ~36-token relay samples), generation volume is tiny. The forward passes for
  `u` dominate, not generation. Adding vLLM doubles the resident copy of the model
  (29 + 29 GB), adds a two-engine **consistency caveat** (same weights/dtype/tokenizer,
  or the frontier mixes two models), and adds operational surface.
- **For (only if):** generation ever becomes the bottleneck (e.g., large-scale relay
  output evaluation). On 96 GB you *can* afford both copies, so revisit only if profiling
  shows generation > forward-pass time.

**Decision:** single `transformers` engine for both hidden states and generation in
P5.1–P5.4. vLLM is a documented, deferred optimization with a known VRAM/consistency cost.

### 2.3 Sensor models (always resident)

- **SupportSensor** (`space="embedding"`) — sentence-transformer embedder, small (<2 GB).
- **NLISensor** — DeBERTa cross-encoder; Phase-5 scales to **`nli-deberta-v3-large`** (a
  few GB), which C2 already targets. Resident.
- **schema_numeric_rule** — pure code, no GPU.

All three load once at startup and are shared across passes.

### 2.4 Warm-swap model pool

**Chosen model set (Phase-5 matrix):**

| Tier | Model | Family | bf16 VRAM | Role |
|------|-------|--------|-----------|------|
| 14B-A | **Qwen2.5-14B-Instruct** | Qwen | ~29.5 GB | primary 14B relay |
| 14B-B | **Phi-4 (14B)** | Microsoft | ~29 GB | second 14B, *different architecture* → the true 14B-vs-14B cross-arch comparison |
| bigger | **Qwen2.5-32B-Instruct** | Qwen | ~64 GB | scale arm; shares Qwen lineage with 14B-A for a clean within-family 14B→32B scale read |

(Llama has no 14B — 8B→70B — and Mistral's nearest are 12B/24B, so a genuine 14B-vs-14B
pair across families lands on Qwen + Phi-4. 7B stays from Phase-4 for the 7B↔14B transfer
in B1.) All three run **native bf16** — no quantization, no probe-on-quantized caveat.

**VRAM ceiling (decided):** routine work stays **≤ ~50 GB** — each 14B is ~33–35 GB resident
(weights + ~2.5 GB sensors + working set). **Qwen2.5-32B bf16 (~66 GB) is the single
sanctioned exception** to that ceiling: it runs **alone, sequentially**, one model at a time,
still leaving ~30 GB free on the 96 GB box. We chose bf16 over 8-bit 32B so the 14B→32B scale
read stays at one precision (no scale/quantization confound).

**Residency = dormant by default (§2.4 below, OPERATIONS §9):** the server is always live but
holds **no LLM at rest**; it lazy-loads one model per request and evicts it after an idle TTL.
There is never more than one LLM resident.

`ModelManager` exposes `load(model, dtype)` / `evict(model)` / `get(model)` (lazy) /
`list()`; default policy = **`resident_pool_max: 0` (dormant)**, `idle_evict_seconds` TTL,
`one_model_at_a_time` (loading evicts any other LLM), hard `vram_cap_gb: 70` (admits the one
32B exception), with sensors + frozen probes always resident (~2.5 GB). Shared-box etiquette
(§9): idle footprint ≈ 2.5 GB, returning ~93 GB to co-tenants between jobs.

### 2.5 Frozen per-model probes (train once at bootstrap, serve inference only)

The usage probe is **trained once per model during bootstrap and frozen** — not trained at
request time. When `./run.sh up` runs on the box, it loads each model in turn, extracts B1
features from the usage dataset (`build_usage_examples`, 80 advisories), fits the
`UsageProbe` (logistic regression), and persists the weights as a signed artifact
(`artifacts/probes/probe_<model>.pkl` + Ed25519 manifest). Serving then loads these
**read-only** and only ever runs inference — there is **no train/fit endpoint**.

Why this is the right shape, not just a preference:
- **It is required.** B1 showed cross-model/cross-size probe transfer ≈ chance ⇒ one probe
  per model is mandatory. Bootstrap-per-model is the natural place to do it.
- **It matches the design.** The probe is meant to be "frozen and signable at inference"
  (its own docstring); freezing + signing realizes that literally.
- **It changes no Phase-4 number.** The fit is deterministic on the cached features, so the
  frozen probe equals the probe the Phase-4 scripts would refit at runtime (asserted to
  1e-9). See [`PHASE5_BUILD_PLAN.md`](PHASE5_BUILD_PLAN.md) §4.1–§4.2.
- **It bounds the failure mode.** A read-only probe can't be retrained to inflate warrant;
  combined with the min-clamp, the probe can only *inform*.

---

## 3. Hardware utilization plan (128 cores · 256+ GB RAM · 96 GB VRAM)

**VRAM is the only tight resource; RAM and CPU are abundant and we exploit both.**

### 3.0 Three-tier residency (the RAM-driven design)
A model is in one of three states; the 256 GB RAM is what makes a long cooldown cheap:
- **HOT** — weights in VRAM, serving (~33–35 GB a 14B; ~66 GB the 32B).
- **PARKED** — weights in **CPU RAM** (`model.to('cpu')`): VRAM freed in seconds, reactivation
  (`.to('cuda')`) in **~3–6 s** (vs ~30–120 s cold from disk). 256 GB RAM holds **all** our
  models parked at once (~123 GB), so after the first load each matrix model switch is seconds.
- **COLD** — on disk only (HF cache); first load ~30–120 s.

Policy: after a job/idle, **park** (frees VRAM fast → good shared-box citizen) on
`idle_park_seconds`; fully **evict** RAM only after `idle_evict_seconds` or under RAM
pressure. **At most one HOT model.** This is the concrete answer to "longer cooldown" — we
keep models *parked* (cheap) rather than *hot* (VRAM-hoarding).

### 3.1 CPU / RAM use (128 cores, 256 GB)
- **Sensors can run on CPU** (`sensor_device: cpu`) so idle VRAM ≈ 0; with 128 cores, batched
  CPU NLI/embedding is fast enough, and it frees the GPU entirely between forward passes.
- **C2 (no LLM) runs on CPU**, optionally concurrent with a GPU job.
- **Host-side data prep / tokenization** parallelizes across cores (`cpu_threads`).
- **HF cache benefits from the page cache** (plenty of RAM), speeding cold loads.

### 3.2 GPU plan
- **bf16 everywhere ≤32B.** Native fidelity; the probe reads true (un-quantized) hidden
  states. This is the whole point of moving off the 23 GB A10.
- **Dormant by default + memory cap + structured OOM.** No HOT LLM at rest; lazy-load one
  model per request, park to RAM on idle (§3.0), evict on the long TTL (≤50 GB soft ceiling
  for 14B; the single 32B run is the sanctioned ~66 GB exception). Set
  `PYTORCH_CUDA_ALLOC_CONF` and a hard reserved cap (`vram_cap_gb: 70`) so the server cannot
  starve co-tenants. A load that won't fit is caught **before** allocation and returned as a
  **structured `insufficient_vram` error** (required vs available GB + suggested action; full
  envelope in [`PHASE5_BUILD_PLAN.md`](PHASE5_BUILD_PLAN.md) §6.1) — never a worker-crashing
  500; CUDA-OOM is caught, freed, and surfaced the same way.
- **Single CUDA context, serialized forward passes.** GPU calls run on the inference
  worker thread; the HTTP layer never touches CUDA directly.
- **Batched forward passes (the main throughput win, §7).** The Phase-4 scripts score one
  claim per forward call. The server should batch claims (pad + attention mask + per-span
  mean-pool) — typically a 5–20× wall-clock reduction on the B1/B2/D2/F3 inner loops.
- **`eval()` + `no_grad` + greedy decode** preserved for determinism.
- **Decode-time hidden states off.** `WhiteBoxLM.generate` already disables
  `output_hidden_states` during decode so the relay path doesn't accumulate hidden states.
- **Layer selection.** Only `{static, middle, final}` layers are pooled and stored; never
  ship or persist all-layers tensors.

---

## 4. API design

Purpose-built, **not** a chat-completions clone. Three tiers: a scoring primitive, the
experiment jobs, and ops. All responses carry a **reproducibility manifest** (§4.4).

### 4.1 Scoring primitive (synchronous, fast)

```
POST /v1/score
  { "model": "Qwen/Qwen2.5-14B-Instruct", "dtype": "bf16",
    "ctx": "<source document text>", "field": "due_date",
    "value": "2025-01-01", "w_decl": 0.85,
    "source_class": "AUTHORITATIVE_API", "leaked_premise": false }
→ { "u": 0.97, "s": 0.81, "faith": 1.0, "g": 0.81,
    "w_realized": 0.6885, "binding": "support",
    "ceil": 0.85, "manifest": { … } }
```
This is the atomic CAPM operation (the same `min`-clamp logic as `p4/warrant/realized.py`).
B2/D2/F3 are batched aggregations over this primitive.

```
POST /v1/score/batch        # many claims, one forward batch — the workhorse
POST /v1/features           # pooled answer-span vector for one (prompt, answer, layer)
                            # returns ~3584 (7B) / ~5120 (14B) floats — pooled only, guarded
```

### 4.2 Experiment jobs (asynchronous — they take minutes)

```
POST /v1/experiments/b1   { model, dtype, advisories=80, seed=0 }   → { job_id }
POST /v1/experiments/b2   { model, dtype, advisories=60, seed=11 }  → { job_id }
POST /v1/experiments/d2   { model, dtype, advisories=30, seed=7 }   → { job_id }
POST /v1/experiments/f3   { model, dtype, advisories=30, seed=55 }  → { job_id }
POST /v1/experiments/c2   { }                                       → { job_id }   # no LLM

GET  /v1/jobs/{id}        → { status: queued|running|done|error,
                              progress, result_summary, artifact_paths, manifest }
GET  /v1/jobs            → list
```

- Jobs return the **CSV-equivalent JSON** the Phase-4 scripts already emit, plus write the
  same artifacts to `/scratch/.../results/...` (so the existing audit/figure tooling keeps
  working unchanged).
- **Dependency enforcement:** posting `b2`/`d2`/`f3` for a `(model,dtype)` with no B1
  cache **auto-schedules B1 first** (or 409s with a pointer, configurable). This encodes
  the DAG (§6) in the API.

### 4.3 Ops / model management

```
GET  /healthz                         → liveness
GET  /v1/gpu                          → { reserved_gb, free_gb, cap_gb, resident_models }
GET  /v1/models                       → resident + cached-feature inventory
POST /v1/models/load   { model, dtype }
POST /v1/models/evict  { model }
GET  /v1/version                      → { git_sha, probe_hash, sensor_versions }
```

### 4.4 Reproducibility manifest (on every result)

```
"manifest": { "model": "...", "dtype": "bf16", "layers": {static, middle, final},
              "pooling": "mean", "probe_sha256": "...", "support_model": "...",
              "nli_model": "nli-deberta-v3-large", "schema_rule": true,
              "code_git_sha": "...", "seed": 7, "ts": "..." }
```
Thematically aligned with CAPM: optionally **Ed25519-sign the manifest** (reuse Build-A's
signing) so a returned verdict is itself an attestable record — a result you can't quietly
mutate the server out from under. This directly addresses the "long-lived mutable server is
a reproducibility hazard" risk (§10).

---

## 5. Infrastructure choices

| Concern | Choice | Why |
|---------|--------|-----|
| Web framework | **FastAPI + uvicorn, 1 worker** | async, typed, free OpenAPI docs; one worker because the model is a GPU singleton |
| GPU concurrency | **asyncio job queue + single inference worker** | forward passes must serialize on one CUDA context; HTTP stays concurrent |
| Engine | **`transformers` white-box** (`WhiteBoxLM`) | only path that exposes hidden states; vLLM deferred (§2.2) |
| Transport | **HTTPS port (exposed), mTLS + bearer token** | access is **HTTP-only** (no SSH) → no tunnel available; the port *must* be reachable, so secure it: TLS, mutual-TLS client certs (reuse Build-B's RSA CA + leaf SANs), and a bearer token. Bind to the specific interface, minimize surface |
| Containers | **Docker, with NVIDIA GPU passthrough** (`--gpus`, nvidia-container-toolkit) | chosen; Build-B already ships Docker patterns (Dockerfile + compose). HF cache + `/scratch` artifacts bind-mounted in |
| Process mgmt | **container `restart: unless-stopped`** via compose; **one** GPU-owning service container | container runtime supervises restarts; reload cost on crash is the 14B/32B weights only (cache survives on the mount) |
| Deployment | **your own one-time access window**: copy the `capm-p5/` folder onto the box and run **one command** (`./run.sh up` → build + fetch models + `docker compose up`); **all experiment interaction thereafter is HTTP** | you get direct access once to upload + execute; after that you drive it remotely. See [`PHASE5_BUILD_PLAN.md`](PHASE5_BUILD_PLAN.md) for the standalone package + single-command bootstrap |
| Storage | **HF cache + artifacts on `/scratch/panora/CAPM-P5`** | never the shared `/home`; large + fast |
| Deps | **fresh venv inside the P5 workspace only** | same discipline as Phase-4 env rules |
| Config | pinned `requirements.txt` (torch/transformers/bitsandbytes/sentence-transformers/sklearn/fastapi/uvicorn) + a `models.yaml` registry | reproducibility |

**Workspace discipline (carried over, non-negotiable):** work only inside the P5
workspace; do not modify other folders, other repos, other venvs; no global installs; do
not touch other users' files.

---

## 6. Pipeline orchestration for B1 / B2 / D2 / F3

**Dependency DAG (enforced by `ExperimentRunner`):**

```
        ┌──────► B2 (fabrication AUC)
B1 ─────┼──────► D2 (frontier)              C2 (NLI/schema) ── independent, no LLM
(probe  └──────► F3 (adaptive adversary)
 + cache)
```

- **B1 = root, run at bootstrap.** Loads the model once, extracts mean-pooled features at
  `{static,middle,final}`, trains `UsageProbe`, writes `feat_<model>_<dtype>.npz`, and
  **freezes + signs the probe** (§2.5). This happens once per model during `./run.sh up`,
  not at request time; the frozen probe + cache are on disk for the rest of the matrix.
- **B2/D2/F3** reuse the **same resident `WhiteBoxLM`** and the **same B1 cache** to train
  the probe; they only forward-pass *new* claims (B2 fabrications, D2 frontier claims, F3
  adversarial candidates). Sensors (`support`, `nli`, `schema`) shared.
- **C2** runs anytime; it needs no relay model (just NLI + schema). Can run on the same
  box or even a CPU-only path.
- **Determinism:** seeds, greedy decode, `eval()` carried through unchanged; manifest pins
  every version so a job is reproducible regardless of server uptime.
- **Idempotence:** a job keyed by `(experiment, model, dtype, advisories, seed)` returns
  the cached result if artifacts already exist and the code SHA matches (configurable
  `force=true`).

Critically, **none of this changes the science** — the server is an execution substrate.
The known Phase-4 finding (the leakage-free faith sensor degrades D2/F3 at scale because
premise=ctx on structured `key:value` text rates benign claims *neutral*) is a **sensor
fix**, not a serving fix. C2's scale-up to DeBERTa-large + the schema rule is the first
lever; a natural-prose ctx rendering and/or an LLM-as-judge faith path is the second. The
plan flags this honestly: Phase 5 *enables* the 14B runs at full fidelity; it does not by
itself resolve the faith-sensor scale sensitivity.

---

## 7. Performance considerations

1. **Batched forward passes — the single biggest win.** Phase-4 scripts call the model
   once per claim. Batching (pad to max length, attention-masked, per-span mean-pool of
   the answer tokens) cuts the B1/B2/D2/F3 inner loops by ~5–20× at 14B. This is the main
   engineering deliverable of P5.3 and the chief reason the server beats naive per-claim
   scripts.
2. **Model-load amortization.** 14B loads in ~30–90 s. A batch script pays that *per run*;
   the resident server pays it *once* and serves many jobs — the core value proposition for
   an HTTP-only or many-runs workflow.
3. **B1 feature cache.** B2/D2/F3 read the `.npz` instead of recomputing B1 features —
   already in the design; the server just makes it a managed, shared asset.
4. **Sensor residency.** Embedder + NLI loaded once, not per pass.
5. **bf16 native.** No dequant overhead; faster than the A10's 8-bit path and higher
   fidelity.
6. **KV cache** is modest at this scale (short relay generations); not a bottleneck.
7. **Warm pool** (2 resident 14B) removes reload latency across the cross-architecture
   matrix.

Rough envelope (14B bf16, batched): a full B1 over 80 advisories should land in single-digit
minutes; B2/D2/F3 faster (cache reuse). The dominant variable is total claim count × forward
cost, which batching attacks directly.

---

## 8. Bottlenecks and risks

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| 1 | **GPU contention on a shared box** (co-tenant OOMs you / you OOM them) | **High** | reserved-VRAM cap, fail-fast OOM, MPS/MIG if available, coordinate windows, `/v1/gpu` visibility |
| 2 | **Single GPU-resident process = SPOF**; crash ⇒ 29 GB reload | Med | supervise + auto-restart; persist B1 cache so only the model (not features) reloads |
| 3 | **White-box constraint forecloses fast serving for `u`** | Structural | accept it; batch instead; vLLM only for the generate path if ever needed (§2.2) |
| 4 | **Long-lived mutable server drifts from reproducibility** | Med | pinned versions + signed manifest + immutable deploy + idempotent job keys |
| 5 | **Exposed port on a multi-user host** (HTTP-only access ⇒ no tunnel; the port is reachable) | **High (security)** | TLS + **mTLS** client certs (Build-B CA) + bearer token; bind a specific interface; minimal surface; rate-limit. This is a *managed* exposure, not an avoided one |
| 6 | **Two-engine inconsistency** (if vLLM added) | Med (deferred) | pin identical weights/dtype/tokenizer; keep single-engine by default |
| 7 | **Faith-sensor scale degradation (D2/F3)** — *science, not serving* | **High for the result** | C2 → DeBERTa-large + schema rule; natural-prose ctx and/or LLM-judge faith; report honestly |
| 8 | **Quantization caveat** for >32B | Low (avoidable) | stay ≤32B bf16; if 72B, declare 8-bit and caveat the probe-on-quantized-states |
| 9 | **HF download / disk on shared FS** | Low | cache on `/scratch`, pre-download in P5.0 |
| 10 | **Client/server version skew** | Low | `/v1/version`; manifest on every result |

---

## 9. Shared-box operating etiquette (operational appendix)

- Cap reserved VRAM well below 96 GB; leave headroom for co-tenants.
- Pin `CUDA_VISIBLE_DEVICES`; if MIG/MPS is configured, use a slice.
- Run as a Docker service (`docker compose`, `--gpus`, `restart: unless-stopped`);
  document `docker ps` / `docker compose down` so you never orphan a 29–64 GB resident
  model. (Docker access implies the box permits it and you're in the `docker` group.)
- All writes under `/scratch/panora/CAPM-P5`; never `/home`, never other users' paths.
- Health endpoint + a `STOP`/drain so the server releases GPU cleanly on request.

---

## 10. Reproducibility & audit integration

- Every job artifact mirrors the Phase-4 CSV schema, so existing `audit/recompute_tables`,
  the WS6 exit-gate, and the figure scripts keep working against server output unchanged.
- The signed manifest makes each verdict attestable (CAPM-native).
- An optional `/v1/audit/exit-checks` can run the WS6 gate over server-produced artifacts,
  closing the loop between serving and the Definition-of-Done.

---

## 11. Honest critique & recommended architecture

**The core idea is sound where it matters and risky where it's vague.** Refinements:

**What's right (keep it):**
- **Server-side orchestration.** Running B1/B2/D2/F3 *on the box* and returning small JSON
  is the correct call. The anti-pattern — shipping raw hidden-state tensors to an external
  orchestrator — would be slow, fragile, and pointless. Your phrasing ("run the pipeline …
  and return the results") already avoids it. Good.
- **Hosting the model resident.** Amortizing the 14B load and the B1 cache across many
  jobs is the real value, especially without direct (AnyDesk) access.

**What to change:**
1. **Not a generic LLM API.** A `/v1/chat/completions`-style gateway is the wrong
   abstraction: it can't expose hidden states (so `u` is impossible through it) and it
   invites free-form, unversioned calls. Build a **purpose-built scoring + experiment
   service** whose endpoints mirror the CAPM contract and the four passes (§4).
2. **Ship the pooled feature vector, never weights or raw tensors.** If a low-level
   feature endpoint is wanted, return the **mean-pooled** answer-span vector (~3.5–5k
   floats), guarded — not the all-layers tensor (hundreds of MB) and certainly not model
   weights (static params are useless to the probe; the probe needs *activations from a
   specific forward pass*).
3. **One GPU owner, internal queue.** Single uvicorn worker, serialized CUDA. Resist
   "scale out with more workers" — each worker reloads 29 GB and they'll contend.
4. **Secure the exposed port.** Access is **HTTP-only** (no SSH), so the tunnel option is
   off the table and the port is genuinely reachable on a shared host — the single most
   important security work is TLS + mTLS + token (§5, §8.5), not avoidance.

**The architecture decision is settled by the access mode:**

- **Option A — Batch-in-process over SSH** (rsync code, `python -m p5.exp…`, like the A10):
  simplest and most reproducible **but requires an SSH shell, which you do not have.** So
  it is **not available as the primary path.** It survives only as an *in-container parity
  check* (§ below).

- **Option B — Persistent inference service (this document): CHOSEN.** HTTP-only access
  forces it, and it's independently justified — a warm resident model amortizes the
  30–90 s (14B) / longer (32B) load across the whole cross-model matrix, and one resident
  copy serves all consumers instead of each reloading tens of GB.

**Consequences of HTTP-only worth stating plainly:**
- **You deploy once, during your own access window.** You get direct access to the box one
  time to copy the standalone `capm-p5/` folder and run a single command (`./run.sh up`:
  build → fetch models → `docker compose up`). From then on *everything* — B1/B2/D2/F3/C2,
  model load/evict, health — is driven remotely through the API. The server runs as a
  daemon (`restart: unless-stopped`) so it survives your disconnect.
- **No tunnel ⇒ the port is exposed ⇒ mTLS is mandatory, not optional.**

**Parity check (free correctness gate):** even without SSH, run one pass **both ways inside
the same container** — once in-process (Option-A style) and once through the API — and
require the **signed manifests + metrics to match**. That's your acceptance test that the
service wraps the science faithfully and adds nothing.

**The hosted-prober hypothetical (threat-model fit — full treatment in
[`PHASE5_BUILD_PLAN.md`](PHASE5_BUILD_PLAN.md) §15–§16):** the endpoint is treated as *the
model host attesting its own usage signal `u`* to the calling/verifying agent — which is
exactly how CAPM intends `u` (a runtime-internal, white-box sensor) to be deployed. The
honest security statement: because `g=min(u,s,faith)` with `s`/`faith` recomputed
verifier-side, and `w=min(w_decl,g·w_decl)` capped by source-class, **even a lying host
cannot push a claim above its origin-class ceiling** — the by-construction guarantee never
rested on `u`. A dishonest `u` can only forfeit `u`'s *localization* benefit for the
usage-binding cases (e.g. truths-only synthesis), which a real deployment discharges via
attestation/re-execution. Phase-5 experiments run under an honest host, so this is sound for
measurement; the caveat is what it would mean adversarially.

---

## 12. Phased implementation roadmap

> No code yet — this is the build order once approved.

**P5.0 — Foundations, image & one-time deploy handoff** *(prereq for everything)*
- **Build the Docker image** (CUDA + torch/transformers/bitsandbytes/sentence-transformers/
  sklearn/fastapi/uvicorn, pinned) with NVIDIA GPU passthrough; reuse Build-B's Docker
  patterns. Bind-mount the `/scratch/panora/CAPM-P5` HF cache + artifacts dir.
- **Your one-time access window:** copy the standalone `capm-p5/` folder to the box and run
  the single bootstrap command (`./run.sh up`). After that, all interaction is HTTP.
- Pre-download **Qwen2.5-14B-Instruct, Phi-4 (14B), Qwen2.5-32B-Instruct** (+ keep 7B for
  the B1 7B↔14B transfer) to the `/scratch` HF cache.
- Smoke: load 14B bf16 in `WhiteBoxLM`, verify `output_hidden_states`, print VRAM, one
  `/score`-equivalent forward; load 32B bf16 and confirm it fits (~64 GB).
- **Train + freeze the per-model probes** (the "train once on the hosted models" step,
  §2.5): for each model, extract B1 features, fit `UsageProbe`, persist + Ed25519-sign
  → `artifacts/probes/`. **Exit:** all three load native bf16; one signed frozen probe per
  model (`/v1/probes` lists them); API reachable over HTTPS+mTLS.

**P5.1 — Core scoring service**
- FastAPI skeleton, `ModelManager` (load/evict/list, VRAM cap), `SensorManager`.
- `POST /v1/score`, `/v1/score/batch`, `/healthz`, `/v1/gpu`, `/v1/models`.
- Exposed HTTPS port + mTLS + bearer token (no tunnel — HTTP-only access). Single worker + inference queue.
- **Exit:** a remote client scores a claim over HTTPS/mTLS end-to-end; warrant matches `p4/warrant/realized.py`.

**P5.2 — Experiment endpoints + DAG**
- **B2/D2/F3** reuse the **frozen probe + B1 cache produced at bootstrap** (P5.0); **C2**
  standalone (no LLM). Async jobs + `/v1/jobs/{id}`. Serving never re-fits the probe.
- Emit the Phase-4 CSV schema + signed manifest. **Exit:** all five run via API; artifacts
  drop where the audit/figure tooling expects them.

**P5.3 — Performance**
- **Batched forward passes** (the main win); model-load amortization metrics; warm-pool
  (≤2 resident 14B, LRU evict). **Exit:** B1/80-adv batched in single-digit minutes;
  measured speedup reported.

**P5.4 — Cross-model & scale matrix**
- Run the full B1/B2/D2/F3 (+C2) grid over **Qwen2.5-14B + Phi-4 (14B-vs-14B cross-arch)
  + Qwen2.5-32B (within-Qwen 14B→32B scale)**, plus 7B↔14B cross-size transfer in B1.
  Append to a Phase-5 results ledger in the house style. **Exit:** native-bf16 results for
  all three relays; cross-arch (Qwen↔Phi-4) and scale (14B↔32B) reads reported.

**P5.5 — Hardening, reproducibility & faith-sensor follow-up**
- Manifest signing (Ed25519, reuse Build-A); optional mTLS; OOM guards; deploy/run-book;
  `/v1/audit/exit-checks` over server artifacts.
- **Faith-sensor fix: DEFERRED (out of Phase-5 scope by decision).** The known D2/F3
  scale degradation (premise=ctx rating structured benign claims *neutral*) is **not**
  addressed here. C2 still scales NLI to DeBERTa-large as a serving artifact, but the
  D2/F3 14B/32B numbers are reported **with the faith caveat carried forward verbatim**
  from Phase-4. Flag it as the top open scientific item for a later phase.
- **Exit:** in-container parity check passes (in-process vs API metrics + manifests match);
  results reproducible from manifests.

---

## 13. Resolved decisions

1. **Access mode → HTTP-only** (no SSH), **with one direct access window to deploy**. ⇒
   **Option B (persistent service) is the architecture**; you copy the standalone folder
   and run one command during that window, then drive it remotely over an exposed HTTPS
   port secured by mTLS + token. Build steps live in [`PHASE5_BUILD_PLAN.md`](PHASE5_BUILD_PLAN.md) (§5, §11).
2. **Container → Docker** with NVIDIA GPU passthrough, reusing Build-B's Docker patterns;
   HF cache + artifacts bind-mounted from `/scratch` (§5).
3. **Model set → Qwen2.5-14B-Instruct + Phi-4 (14B) + Qwen2.5-32B-Instruct**, all native
   bf16 on 96 GB (+ 7B retained for B1 transfer). Qwen↔Phi-4 = the 14B-vs-14B cross-arch
   pair; Qwen-14B↔Qwen-32B = the within-family scale read. 72B excluded (§2.1, §2.4, §12).
4. **Faith-sensor fix → DEFERRED.** Out of Phase-5 scope; D2/F3 numbers carry the Phase-4
   faith caveat forward; flagged as the top open scientific item (§6, §8.7, §12 P5.5).

*Remaining low-level calls (can be made at P5.1, not blockers): exact mTLS cert issuance
(reuse Build-B CA), bearer-token scheme, and the resident-pool default (≤2 vs warm-swap).*
```
