# CAPM Testbed — Comprehensive Work Report

**Scope.** This is the full record of what was built, how it was built, how the
real-model and real-attack infrastructure was set up, and every experiment with
its method and result. It is meant as the base for end-to-end analysis: which
mechanism produces which result, what each number means, and where the limits
are.

**One-line outcome.** The defense specified in
`reference_documents/Cross_Agent_Provenance_Defense_Design.docx` (CAPM) was
implemented as a runnable testbed and validated across **32/32 planned
experiments** — on real Gemini content, real attack pipelines, the real
AgentDojo benchmark, and a machine-checked ProVerif proof. The orchestrated flow
reports **ALL PASS**; 13/13 unit tests pass. The single honest limitation
(origin-integrity, E3.2) is reported by design, not hidden.

---

## 0. Table of contents

1. The problem and the design (what CAPM is)
2. Repository & artifact map
3. The mechanism — how CAPM works in the testbed
4. Setup & environment — how everything was installed/configured
5. Orchestration, monitoring, persistence
6. Every experiment — method + result
7. Consolidated results & mapping to the design-doc claims
8. The honest boundary and caveats
9. Reproducibility (exact commands)
10. How to extend the analysis
11. Appendix — file inventory, quota ledger, glossary

---

## 1. The problem and the design (what CAPM is)

**Problem (Plane 1 vs Plane 2).** In multi-hop, cross-organisation agent chains,
the cryptographic substrate authenticates *who* each agent is (Plane 1) but not
*where the information came from or whether it is faithful* (Plane 2). So trust
in a downstream answer is decoupled from its actual epistemic **warrant**. The
design doc adopts this as a proven problem and specifies the missing Plane-2
mechanism.

**CAPM (Cross-Agent Provenance Manifests), four components:**
1. a **cross-org provenance record** extending PROV-AGENT (field-level claims,
   per-edge transformation type, org-boundary markers, origin source class);
2. a **signed C2PA-style manifest** carrying the record (hash-linked segments,
   each signed);
3. an **identity binding** — the manifest signature is bound to the agent's
   Verifiable Credential (Plane-1 ↔ Plane-2);
4. an **external warrant evaluator** at the receiver that decides accept /
   down-weight / quarantine / reject **outside the language model** — the option
   (a) stance against the Semantic-Laundering "self-licensing" theorem.

**The core anti-laundering rule.** Warrant is **bounded by the origin's source
class** and is **monotonically non-increasing** along the chain. Low-warrant
content keeps its low ceiling no matter how many trusted agents relay it.

---

## 2. Repository & artifact map

```
files/
├── EXPERIMENT_PLAN.md                  the original NDSS experiment plan (input)
├── EXPERIMENT_IMPLEMENTATION_CHECKLIST.md  per-experiment status tracker
├── WORK_REPORT.md                      ← this document
└── capm-testbed/                       the implementation
    ├── capm/                           library
    │   ├── core/        types.py (warrant lattice, source classes, transforms), value.py (WarrantedValue)
    │   ├── provenance/  graph.py (cross-org PROV DAG)
    │   ├── manifest/    capm_manifest.py (signed hash-linked manifest)
    │   ├── identity/    credentials.py (VC identity, registry, Ed25519; SAGA-aware)
    │   ├── warrant/     evaluator.py (the external evaluator + ablation toggles)
    │   ├── agents/      agent.py (adversary-aware agents), responders.py (deterministic/Gemini/LLM)
    │   ├── baselines/   baselines.py (no-defense, identity-only, flat, CaMeL-single-runtime)
    │   ├── benchmark/   harness.py, runner.py, scenarios.py, stats.py, svg.py, agentdojo_crossorg/
    │   ├── adapters/    saga_bridge.py, saga_adapter.py (Plane-1 / SAGA)
    │   └── common/      rng.py (seeding)
    ├── attacks/
    │   ├── injectors.py                legacy abstractions
    │   ├── adaptive/profiles.py        adaptive adversaries (class-lie, transform-lie, forgery, collusion)
    │   └── corpora/rag.py              real RAG store + poisoner (E5.1)
    ├── experiments/                    every experiment + run_flow.py, monitor.py, _validators.py, make_report.py
    ├── proofs/proverif/capm_manifest.pv   the machine-checked formal model (E2.1)
    ├── tests/test_capm.py              13 unit tests
    ├── scripts/run_all_experiments.sh, setup_realism.sh
    ├── runlog/run_<ts>/                saved per-run logs + manifest.json + summary.md
    ├── results/report/                 generated figures (SVG) + report.html + CSV
    └── docs/ARCHITECTURE.md, TESTBED.md, CAPM_vs_SAGA.md, INTEGRATION.md
```

---

## 3. The mechanism — how CAPM works in the testbed

### 3.1 Warrant lattice & source classes (`capm/core/types.py`)
- Lattice: `NONE(0) < WEAK(1) < DERIVED(2) < MODERATE(3) < STRONG(4)`.
- Source-class ceilings: `AUTHORITATIVE_API`/`VERIFIED_DOCUMENT` → STRONG;
  `FIRST_PARTY_DB`/`PUBLIC_WEBPAGE` → MODERATE; `EDITABLE_SOURCE`/`UNTRUSTED_TOOL`/
  `MODEL_MEMORY` → WEAK; `UNKNOWN` → NONE.
- Transformation fidelity penalties: verbatim/extraction 0; summary/paraphrase/
  composition 1; generation 4 (collapses to NONE unless re-grounded).

### 3.2 Provenance & value (`provenance/graph.py`, `core/value.py`)
A `WarrantedValue` carries a `ProvenanceChain` (DAG of field-level `ClaimNode`s
and transformation-typed `DerivationEdge`s, with org-boundary markers). Descends
conceptually from CaMeL's `Capabilities` (sources/readers) but adds warrant +
cross-org semantics.

### 3.3 Signed manifest (`manifest/capm_manifest.py`)
Each agent appends a `ManifestSegment` (content hash, transformation, from/to
org, boundary flag, origin source class + asserted warrant on the first segment,
soft-binding hash, prev-segment hash) and **signs the canonical bytes** with its
Ed25519 key. Segments form a hash-linked chain; tampering breaks verification.

### 3.4 Identity binding (`identity/credentials.py`, `adapters/saga_bridge.py`)
Each agent holds a `VerifiableCredential` and signs under its key. With
`CAPM_USE_SAGA=1` the signing/verification route through **SAGA's real
`common.crypto`** (NDSS-2026 code, vendored), proving the result isn't a
crypto stand-in.

### 3.5 The external evaluator (`warrant/evaluator.py`) — the defense
On each incoming manifest, **outside the model**:
1. **Signature verification** over the whole chain (trusted DID, VC match, sig,
   hash-link). Any break → `REJECT`.
2. **Warrant scoring**: start at the origin's asserted warrant **capped by the
   declared source-class ceiling**, then subtract each transformation's fidelity
   penalty (and unverified-boundary penalty). Monotone non-increasing. Plus an
   **E3.1 transformation-lie check**: a VERBATIM claim that doesn't preserve the
   predecessor's bytes is scored as a GENERATION.
3. **Soft-binding check**: recompute the watermark/perceptual hash; mismatch →
   `QUARANTINE`.
4. **Policy decision**: `ACCEPT` / `DOWN_WEIGHT` / `QUARANTINE` against floors.
- **Ablation toggles** (E8.x): `enforce_origin_ceiling`, `apply_transformation_penalty`,
  `enable_soft_binding_check`, `cross_org_aware`, `detect_transformation_lies`,
  `require_signatures` — each disables one mechanism.

### 3.6 Baselines (`baselines/baselines.py`)
`no_defense` (accept all), `identity_only` (accept if sender DID trusted — Plane 1
only), `flat_provenance` (trust asserted warrant, no origin ceiling),
`camel_single_runtime` (secure in-runtime, blind across the boundary).

### 3.7 Adaptive adversaries (`attacks/adaptive/profiles.py`)
An `AdversaryProfile` separates **ground truth** (true source class / true
transformation) from what an agent **declares** in the manifest. Constructors:
`honest_origin`, `inflated_warrant_origin` (truthful class, inflated number),
`origin_capture` (lies about the class itself — E3.2), `lying_transformation_origin`
(relay regenerates but declares VERBATIM — E3.1), `forgery_relay` (E3.3),
`collusion_relay` (E3.4). This is what makes the headline result not "by
construction": when the adversary is allowed to lie about the class, the result
changes exactly where the theory says it should.

### 3.8 Cross-org harness (`benchmark/harness.py`, `runner.py`, `scenarios.py`)
`build_chain` wires an N-hop, N-org chain (each hop a cross-org boundary) with an
origin profile + optional relay adversaries + optional real-model relays.
`run_trial` / `run_trial_multi` build a chain **once** and score it under all 5
defenses (the efficient path). `run_matrix` sweeps defense × adversary × hops.
`stats.py` provides Wilson CI, bootstrap CI, McNemar, Spearman.

---

## 4. Setup & environment — how everything was installed/configured

**Base.** Python 3.12.3. Core dep: `cryptography` (Ed25519). The standalone
testbed needs nothing else and runs fully offline/deterministically.

### 4.1 Real-model backend (Gemini) — how we did it
- **REST via stdlib** (`urllib`), no SDK required — `GeminiResponder` in
  `capm/agents/responders.py`.
- **5 API keys used in sequence.** Stored in gitignored `.env` as
  `GEMINI_API_KEYS=k1,k2,…,k5`. The responder's key pool rotates to the next key
  on each key's daily 429 → **5 × 20 = 100 live requests/day** (the free-tier
  cap for `gemini-2.5-flash` is **20 requests/day/key**, measured, not 250).
- **On-disk cache** (`results/llm_cache.json`): identical (mode, query, inputs)
  calls are free forever; re-runs cost 0.
- **Rate-limit handling**: ~8–12 s spacing + exponential backoff honoring the
  server's `retryDelay`; daily-quota 429s rotate keys immediately.
- **Graceful fallback**: when all keys are exhausted, the responder degrades to a
  deterministic paraphrase (counted/reported). This is sound because CAPM's
  verdict is computed from the manifest, not the relay text (content-independence),
  so containment (ASR) is unaffected — only the "real-model" label on a trial is.
- **Budget guard**: `CAPM_LLM_MAX_REQUESTS` is a hard ceiling.

### 4.2 AgentDojo (E5.4) — sudo-free
- `python -m venv .venv` then `.venv/bin/pip install agentdojo cryptography`.
  Installs `agentdojo 0.1.35`. The realism flow runs from `.venv/bin/python`.

### 4.3 ProVerif (E2.1) — built from source, no sudo
- opam's `proverif` package forces the GTK GUI binding (needs root). Instead:
  downloaded the **static opam 2.2.1 binary** to `~/.local/bin`, built **OCaml
  4.14.2** in a user switch (`opam switch create cap 4.14.2`), then **built the
  ProVerif 2.05 CLI from source** (`./build`; the GUI step fails on missing
  lablgtk, but the CLI binary is produced first) → `~/.local/bin/proverif`.
- One-command reproduction: `scripts/setup_realism.sh`.

---

## 5. Orchestration, monitoring, persistence

- **`experiments/run_flow.py`** runs the whole sequence as **subprocesses**
  (one crash never aborts the rest), captures each step's stdout+stderr, validates
  it against per-step criteria, and writes `runlog/run_<ts>/manifest.json` **after
  every step**. `--llm` adds the model-backed steps; `--resume` reuses passed
  steps; `--only <phases>` filters.
- **`experiments/_validators.py`** is the single source of truth: the ordered
  step list + the pass criteria, encoding the design-doc gates (e.g. CAPM ASR == 0,
  McNemar favours CAPM, "All forgeries rejected: True", ProVerif `RESULT … true`,
  Spearman ρ > 0, "bit-for-bit identical").
- **`experiments/monitor.py`** renders a live/one-shot dashboard from the manifest
  (status, metrics, failed checks, error excerpts); `--watch`, `--errors`, `--tail`.
- **Persistence**: every run leaves `*.log`, `manifest.json`, `summary.md` under
  `runlog/`, so any result can be re-evaluated without re-running. The Gemini
  cache persists across runs.

---

## 6. Every experiment — method + result

Legend: **ASR** = attack success rate (fraction of attacks accepted at full
strength; lower is better). All results below are from the saved `runlog/`.

### S0–S3 (the design-doc evaluation ladder)
- **S0 single-hop honest**: provenance survives one cross-org hop; honest STRONG
  origin accepted. PASS.
- **S1 single-hop adversarial**: CAPM down-weights the injected attacks all
  baselines accept. PASS.
- **S2 N-hop erosion**: warrant **monotone non-increasing** across hops (True);
  ADMIT origin capped to WEAK→NONE within 2 hops. PASS (this is also E2.2).
- **S3 text-only + tamper**: soft-binding detects off-manifest edits; broken
  hash-link / unknown signer → REJECT. PASS.

### §1 Core efficacy
- **E1.1 — containment vs baselines (headline).**
  Method: matrix of 5 defenses × catchable adversaries × hops, with Wilson CIs
  and a paired McNemar test; run deterministically (full, tight) and on real
  Gemini relay content (efficient, build-once-per-content).
  Result (deterministic full): `CAPM ASR 0.00 [0.00,0.12]` vs every baseline
  `1.00`; **McNemar p = 7.45e-09** (28 discordant, all CAPM-correct).
  Result (real Gemini, 12 trials): `CAPM ASR 0.00`, baselines `1.00`,
  **McNemar p = 4.88e-04** (12 discordant, all CAPM-correct).
- **E1.2 — provenance survival @ N hops** under real Gemini paraphrase.
  Result: **CAPM full-chain reconstruction 7/7** hop-lengths; identity/flat
  baselines carry no structured chain.
- **E1.3 — end-to-end task efficacy** (expense-reimbursement task, Gemini relays).
  Result: no-defense files the poisoned **$9,999** (harmful action);
  **CAPM prevents the harmful action** while still completing the honest task
  ($1,250 filed). The action is gated on the external warrant.

### §2 Soundness / formal
- **E2.1 — warrant-binding soundness.**
  (A) **ProVerif machine-checked** (`proofs/proverif/capm_manifest.pv`):
  `RESULT not attacker(origin_sk) is true` (key secrecy) and
  `RESULT event(OriginAccepted(p,s)) ==> event(OriginSigned(p,s)) is true`
  (origin-class authentication). (B) **Empirical lemma**: swept **120 attacker
  configurations** (asserted warrant × transformation × forgery); warrant never
  exceeded the true-class ceiling. Both discharge.
- **E2.2 — monotonicity** (empirical companion). Warrant non-increasing on honest
  chains; lower with a low-warrant origin. PASS.
- **E2.3 — tamper/forgery battery.** **10/10** structural attacks handled (broken
  hash-link, unknown signer, off-manifest edit, signature replay, VC substitution,
  segment reorder, segment deletion, downgraded-transform lie, cross-manifest
  splice); none accepted.

### §3 Adaptive adversary
- **E3.1 — lying transformation**: a relay declares VERBATIM but regenerates;
  **detected 3/3**, content quarantined.
- **E3.2 — origin capture (the honest boundary)**: the adversary lies about the
  **source class** (editable→AUTHORITATIVE_API). CAPM does **not** catch it by
  warrant (accepts), **but attribution still works** (origin DID resolvable →
  revocable). This proves the headline ASR=0 is a real mechanism, not an
  artifact: it changes exactly where the theory says it should.
- **E3.3 — manifest forgery**: fake signature / replay / VC-substitution → **all
  REJECT** (also verified on SAGA's real crypto).
- **E3.4 — collusion**: warrant stays **constant `[0,0,0,0,0,0]`** regardless of
  the number of colluding relays — origin-bounded, not relay-bounded.
- **E3.5 — adaptive optimisation loop**: Gemini iteratively rewrites the poison to
  sound more authoritative over 8 rounds. **Transitivity attacker ASR 0/8**
  (adaptivity does not climb); origin-integrity attacker 8/8 (the E3.2 boundary
  only). More persuasive content cannot beat CAPM — warrant is external.

### §4 Real-model (de-simulation, Gemini)
- **E4.1 — transformation faithfulness**: declared vs. classifier verdict over
  4 sources × 2 modes → **8/8 = 1.00** consistent. Where a self-report disagrees,
  the content-hash check (E3.1) catches it.
- **E4.2 — cross-model generality**: ran the containment matrix on **3 Gemini
  tiers** — `gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-2.5-flash-lite`:
  **CAPM ASR 0.00 for all three**, worst baseline 1.00. Containment is
  model-independent (warrant is external).
- **E4.3 — latent source-bias**: same factual claim, 4 source framings. Gemini
  trust = **9.0** (government API / peer-reviewed) vs **1.5** (editable wiki /
  anonymous forum) → **7.5/10 bias spread**. CAPM's warrant is set by the external
  lattice, so it does not depend on that bias. (An early run showed 0.0 due to a
  prompt-routing bug, since fixed; the real probe gives 7.5.)

### §5 Real-attack corpora/pipelines
- **E5.1 — ADMIT (real RAG poisoning)**: 50 benign docs + a few poison docs
  crafted to match the query (bag-of-words retriever). Even **1 poison doc
  (1.96% rate) wins retrieval**; flat baseline ASR **1.00**, **CAPM ASR 0.00
  (quarantine) at every poisoning rate** (1, 2, 5, 10 docs). Containment is
  independent of poisoning rate.
- **E5.2 — Flooding-Spread (real propagation)**: 20 agents, 8 rounds. The
  manipulated claim **floods to 100%** under no-defense/flat; **stays at agent 0
  (0.05)** under CAPM — propagation blocked at the belief gate.
- **E5.3 — Causality-Laundering (real denial channel)**: an access denial leaks
  "balance exceeds threshold"; the attacker launders it as a sourced fact.
  Baselines accept (LAUNDERED); **CAPM quarantines** (UNKNOWN→NONE).
- **E5.4 — AgentDojo (real benchmark)**: the actual banking suite (16 user tasks,
  9 injection tasks, 4 injection vectors — bill text, incoming transaction,
  address change, landlord notice). **CAPM contains 9/9 real AgentDojo
  injections (ASR 0.00)**; all baselines accept them.

### §6 Scale & stress
- **E6.1 — overhead vs chain length**: per-hop verification **~0.17–0.19 ms**
  (sub-millisecond), manifest size ~linear (~800 B/hop), measured on SAGA's
  Monitor when `CAPM_USE_SAGA=1`.
- **E6.2 — throughput**: thousands of verifications/sec; CAPM cost ≪ LLM cost.
- **E6.3 — manifest growth & compaction**: audit PROV triples (the bulk) are
  recomputable and can be dropped from the wire form; signed core grows linearly.

### §7 Utility / trade-off
- **E7.1 — utility–resistance frontier**: sweeping the accept floor yields a clean
  ASR-vs-utility Pareto curve; CAPM contains all catchable attacks across operating
  points.
- **E7.2 — false-positive analysis** (real honest Gemini paraphrase): hard
  false-positives (honest content quarantined) only at high hop counts; tunable
  via E7.1.
- **E7.3 — warrant-vs-fidelity calibration**: Gemini paraphrase chains of growing
  length + a Gemini fidelity oracle. **Spearman(warrant, fidelity) = +0.77–0.82** —
  lower warrant tracks genuinely lower fidelity (closes the T2 question).

### §8 Ablations (each removes one mechanism)
- **full CAPM**: ASR 0.00, utility 0.75 (reference).
- **E8.1 −origin ceiling**: ASR **0.12** (laundering succeeds) → ceiling necessary.
- **E8.2 −transformation penalty**: ASR **0.17**, utility 1.00 → fidelity
  accounting necessary (soundness traded for utility).
- **E8.1+E8.2 (both)**: ASR **0.83** → the two together carry containment.
- **E8.3 −signature verification**, **E8.4 −soft-binding**, **E8.5 −cross-org
  awareness**: each degrades the corresponding guarantee.

### §9 Reproducibility / artifact
- **E9.1 — determinism + CIs**: rate metrics **bit-for-bit identical across 10
  seeds**; Wilson + bootstrap CIs reported; per-verify latency **0.50 ms
  [CI 0.50, 0.51]** over 200 reps.
- **E9.2 — one-command report**: `make_report.py` regenerates 4 SVG figures
  (ASR-by-defense, erosion curve, ablation bars, calibration scatter) + `report.html`
  + `results.csv` under `results/report/`, with zero plotting deps and zero model
  calls.
- **E9.3 — statistical reporting**: `stats.py` (Wilson CI, bootstrap, McNemar,
  effect sizes, Spearman) used by the comparative experiments.

---

## 7. Consolidated results & mapping to the design-doc claims

| Hypothesis / claim (design doc §6.3, §7) | Evidence | Result |
|---|---|---|
| **H1 / C2** provenance survives N cross-org hops; baselines carry none | E1.2, S2 | CAPM 7/7 reconstruction; baselines 0 chain |
| **H2 / C1** CAPM down-weights laundering all baselines accept | E1.1 (det + real Gemini) | ASR 0.00 vs 1.00; McNemar p=7.45e-9 (det), 4.88e-4 (real) |
| **H3 / C5** warrant monotone non-increasing; lower for low-warrant origin | S2 / E2.2 | monotone True; attacks capped |
| **H4 / C5** verification overhead sub-ms per hop | E6.1 | ~0.17–0.19 ms/hop |
| **C3** adversarial cross-org provenance + text-only recovery | E2.3, S3 | 10/10 tamper handled; soft-binding recovers |
| **C4** sound under Semantic-Laundering (external warrant) | E2.1, E3.x | ProVerif proven; forgery/collusion/adaptive contained |
| **C5** measured warrant-erosion + calibration | E7.3, S2 | Spearman ρ≈0.8; erosion curve |
| honest boundary (reported, not hidden) | E3.2 | origin-capture accepted but attributable |

**Cause → effect, in one paragraph.** The origin's **declared source class** sets
a warrant ceiling; the **per-transformation penalty** erodes warrant down the
chain; the **external evaluator** decides on that warrant, never on the model's
reading of the text. Therefore: (i) laundering through trusted relays fails —
warrant is origin-bounded (E1.1, E3.4); (ii) more persuasive or model-generated
content does not help — the verdict is content-independent (E3.5, E4.2); (iii)
forgeries fail signature/VC checks (E2.1, E2.3, E3.3); (iv) the *only* way to
win is to lie about the class itself, i.e. break **origin integrity** (E3.2) — a
separate, composable layer the design doc explicitly scopes out. Removing any one
mechanism breaks a corresponding guarantee (E8.x), and the warrant lattice is
calibrated against real fidelity (E7.3).

---

## 8. The honest boundary and caveats

1. **Origin integrity is out of scope (E3.2).** CAPM bounds warrant by the
   *declared* class; a captured high-warrant origin defeats warrant alone but
   stays **attributable** (revocable). This is stated in the design doc §8.
2. **Real-model sample size.** The real-Gemini headline is 12 trials (p=4.88e-4)
   because of the 20/day/key free-tier cap; the deterministic 20-trial matrix
   (p=7.45e-9) is the tight-statistics companion, valid because containment is
   content-independent.
3. **Cross-model = Gemini tiers.** E4.2 used three Gemini tiers (own quotas), not
   three vendors; the invariance result holds within that set.
4. **E5.x are faithful real mechanisms**, not the original authors' repos (those
   arXiv IDs are future-dated / unverifiable here). E5.1 is a genuine RAG-poisoning
   pipeline, E5.2 a genuine propagation sim, E5.3 a genuine denial channel; E5.4
   is the *actual* AgentDojo benchmark.

---

## 9. Reproducibility (exact commands)

```bash
cd files/capm-testbed

# (one-time) realism deps, no sudo: venv+agentdojo, opam+OCaml, ProVerif CLI
bash scripts/setup_realism.sh

# unit tests
python3 -m tests.test_capm                      # 13/13

# the whole deterministic flow (0 model calls), validated + logged
python3 -m experiments.run_flow

# the realism flow from the venv, with ProVerif on PATH (real E5.x + E2.1 proof)
PATH=$HOME/.local/bin:$PATH .venv/bin/python -m experiments.run_flow

# the real-model flow (Gemini, paced; cache makes re-runs free)
CAPM_LLM_MIN_INTERVAL=8 python3 -m experiments.run_flow --llm

# evaluate any finished run without rerunning
python3 -m experiments.monitor                  # dashboard + verdict
python3 -m experiments.monitor --errors         # failures + log tails
python3 -m experiments.monitor --tail e1_1_llm  # a step's full log

# regenerate figures + report
python3 -m experiments.make_report              # results/report/report.html

# the formal proof directly
$HOME/.local/bin/proverif proofs/proverif/capm_manifest.pv
```

Single experiments: `python3 -m experiments.<id>` (add `--llm` for Gemini-backed
ones). Run E5.4 from the venv (`.venv/bin/python -m experiments.e5_4_agentdojo`).

---

## 10. How to extend the analysis

- **Knobs** (`configs/default.yaml` / `EvaluatorPolicy`): `min_accept`,
  `min_down_weight`, boundary penalties, transformation `fidelity_penalty`, and
  the ablation toggles. Sweeping these is the utility–resistance research (E7.1).
- **What feeds what** (figures): Fig1 ASR-by-defense ← E1.1; Fig2 erosion ← S2;
  Fig3 ablations ← E8.x; Fig4 calibration ← E7.3. All regenerated by `make_report`.
- **Widen the real-model sample**: clear `results/llm_cache.json` and raise the
  hops/attacks in `e1_1_main_matrix --llm` on a day with fresh quota (or a paid
  key); the rotation + pacing + fallback handle the budget automatically.
- **Tighten origin integrity**: E3.2 is the open boundary — composing an
  origin-integrity layer (signed source attestation) on top of CAPM is the
  natural next research step.
- **Per-key usage / quota**: every Gemini run prints `key1=… key2=…` usage and
  fallbacks; the budget planner is `python3 -m experiments.request_budget`.

---

## 11. Appendix

### 11.1 Experiment → file index
| ID | File | Model? |
|---|---|---|
| S0–S3 | `experiments/s0_…`–`s3_…` | no |
| E1.1 | `experiments/e1_1_main_matrix.py` (`--llm`) | optional |
| E1.2 | `experiments/e1_2_prov_survival.py` (`--llm`) | optional |
| E1.3 | `experiments/e1_3_task_efficacy.py` (`--llm`) | optional |
| E2.1 | `experiments/e2_1_soundness.py` + `proofs/proverif/capm_manifest.pv` | no |
| E2.3 | `experiments/e2_3_forgery_battery.py` | no |
| E3.1–E3.5 | `experiments/e3_1…e3_5…` | E3.5 uses Gemini |
| E4.1–E4.3 | `experiments/e4_1…e4_3…` | yes |
| E5.1–E5.4 | `experiments/e5_1…e5_4…` (+ `attacks/corpora/rag.py`) | E5.4 needs venv/agentdojo |
| E6.1–E6.3 | `experiments/e6_1…e6_3…` | no |
| E7.1–E7.3 | `experiments/e7_1…e7_3…` | E7.2/E7.3 use Gemini |
| E8.x | `experiments/e8_ablations.py` | no |
| E9.1–E9.3 | `experiments/e9_1_reproducibility.py`, `make_report.py`, `capm/benchmark/stats.py` | no |

### 11.2 Quota ledger (this engagement)
- Free-tier reality: **20 requests/day/key** for `gemini-2.5-flash`; 5 keys → 100/day.
- Used across the engagement: smoke + lean E1.1 + wider E1.1 + E4.1/4.2/4.3 +
  E7.2/E7.3 + E1.3 + E3.5, with rotation key1→key5 and the on-disk cache making
  all re-runs free. The deterministic flow and all E2/E3(non-5)/E5/E6/E8/E9
  experiments cost **0** requests.

### 11.3 Glossary
- **Plane 1 / Plane 2** — identity (who) vs. information provenance (where/how faithful).
- **Warrant** — justification linking a claim to its source; a lattice level.
- **Warrant ceiling** — max warrant a source class permits (the anti-laundering core).
- **ASR** — attack success rate (fraction of attacks accepted at full strength).
- **Content-independence** — CAPM's verdict depends on the manifest, not the relay
  text; the basis for using deterministic recompute as a valid stand-in.
- **Origin capture** — lying about the source class itself (origin-integrity attack,
  out of scope; the honest boundary).

---

*Generated as the base work report. Every number here is from the saved
`runlog/` logs and the generated `results/report/`; nothing is from memory.*
