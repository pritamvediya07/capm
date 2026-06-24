# CAPM Experiment Implementation Checklist

A complete, self-contained enumeration of **every experiment** in
[`EXPERIMENT_PLAN.md`](EXPERIMENT_PLAN.md), restructured as an implementation
tracker. The plan describes *what* each experiment proves; this document
describes *exactly what we must build* to make each one real, in a form we can
check off one by one.

There are **32 experiments** across 9 groups. This checklist is the source of
truth for implementation status; update the checkbox and the "Status" line as
each lands.

## Legend

- **Status:** `✅ done` · `🟡 partial (mechanism only — not real inputs)` · `❌ not built`
- **Each entry has:** the claim it backs · current code (if any) · the precise
  deliverable to build · independent/dependent variables · the success bar that
  closes it · upstream dependencies · target file(s).
- **Reviewer-critical caveat to carry through all of §1/§5:** the current
  headline `ASR 0.00 vs 1.00` is largely *true by construction* — the adversary
  today truthfully declares a low `SourceClass` and only lies about the
  asserted warrant number, which the ceiling caps. A real experiment must let
  the adversary lie about the **source class itself** (see E3.2). Until then,
  no §1 number counts as evidence of robustness, only of mechanism.

## Progress summary

After the testbed build-out (see [`capm-testbed/docs/TESTBED.md`](capm-testbed/docs/TESTBED.md)),
the **mechanism** for every experiment exists and runs; the remaining ❌/🟡 is
about feeding it **real inputs** (LLMs, real-attack corpora, AgentDojo, ProVerif
binary). Status legend below uses ⚙️ = *mechanism built + runs on the testbed
now*, distinct from the original ✅ (= the real, paper-grade result).

| Group                   | Experiments | ✅ real (Gemini)                                                                                                                   | 🟡 needs ext. dep | ❌ not built |
| ----------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------- | ----------------- | ------------ |
| §1 Core efficacy       | E1.1–E1.3  | E1.1, E1.2,**E1.3**                                                                                                          | —                | 0            |
| §2 Soundness / formal  | E2.1–E2.3  | E2.2, E2.3,**E2.1 (ProVerif proof + lemma)**                                                                                 | —                | 0            |
| §3 Adaptive adversary  | E3.1–E3.5  | E3.1, E3.2, E3.3, E3.4,**E3.5**                                                                                              | —                | 0            |
| §4 Real-model          | E4.1–E4.3  | E4.1, E4.2, E4.3                                                                                                                   | —                | 0            |
| §5 Real-attack corpus  | E5.1–E5.4  | **E5.1** real RAG-poison, **E5.2** real propagation, **E5.3** real denial-channel, **E5.4** real AgentDojo | —                | 0            |
| §6 Scale & stress      | E6.1–E6.3  | E6.1, E6.2, E6.3                                                                                                                   | —                | 0            |
| §7 Utility / trade-off | E7.1–E7.3  | E7.1, E7.2,**E7.3**                                                                                                          | —                | 0            |
| §8 Ablations           | E8.1–E8.5  | E8.1–E8.5                                                                                                                         | —                | 0            |
| §9 Reproducibility     | E9.1–E9.3  | **E9.1**, **E9.2**, E9.3                                                                                               | —                | 0            |

> **Status now: 32/32 experiments COMPLETE with real results — 0 remaining.**
> Every one is validated in the orchestrated flow (`run_flow` → "ALL PASS"),
> 13/13 unit tests pass. Highlights:
>
> - E1.1 CAPM ASR 0.00 vs baselines 1.00 (real Gemini, McNemar p=4.88e-4)
> - **E1.3** prevents a real harmful action ($9,999 reimbursement)
> - **E2.1** ProVerif **machine-checks** key secrecy + origin-class authentication
>   (both `RESULT … is true`), plus the empirical lemma over 120 attacker configs
> - **E3.5** adaptive Gemini adversary can't raise ASR (0/8)
> - **E5.1** real RAG poisoning, **E5.2** real 20-agent propagation, **E5.3** real
>   denial-feedback channel, **E5.4** real **AgentDojo** banking suite (CAPM contains 9/9)
> - **E7.3** warrant tracks fidelity (Spearman ρ≈0.8)
> - **E9.1** bit-for-bit reproducible across 10 seeds + CIs; **E9.2** one-command
>   report (4 SVG figures + HTML + CSV)
> - E3.2 marks the honest origin-integrity boundary
>
> **Realism dependencies are now installed** (see `scripts/setup_realism.sh`):
> agentdojo in `.venv`, and ProVerif 2.05 built from source via a sudo-free opam
> (`~/.local/bin/proverif`). Run the realism flow from the venv with ProVerif on
> PATH: `PATH=$HOME/.local/bin:$PATH .venv/bin/python -m experiments.run_flow`.

---

## §1 — Core efficacy experiments (CLAIM-1 Containment, CLAIM-2 Preservation)

### [ ] E1.1 — Laundering containment vs. baselines

- **Status:** 🟡 (verdict-level mechanism works; needs real inputs from E4.x + E5.x)
- **Claim:** CLAIM-1.
- **Current code:** `experiments/s1_single_hop_adversarial.py`, `experiments/run_all.py`.
- **IV:** defense ∈ {no-defense, identity-only, flat-provenance, CaMeL-single-runtime, CAPM}; attack ∈ {ADMIT, Flooding-Spread, Causality-Laundering}.
- **DV:** ASR, down-weight rate.
- **Deliverable:** rerun the existing matrix but driven by **real attack code**
  (E5.x) and **real model responders** (E4.x) instead of `attacks/injectors.py`
  abstractions.
- **Success:** CAPM ASR statistically below every baseline (with CIs + a
  significance test, see E9.3) — *and* the adversary is allowed to lie about
  source class (E3.2), so the result is not by construction.
- **Depends on:** E4.1, E5.1–E5.3, E3.2, E9.3.
- **Target:** existing experiment files, re-pointed at the real harness.

### [ ] E1.2 — Provenance survival across N hops

- **Status:** 🟡 (whole-chain reconstruction works; per-field + lossy-paraphrase missing)
- **Claim:** CLAIM-2.
- **Current code:** `experiments/s2_nhop_erosion.py`.
- **IV:** n_hops ∈ {1..10}; defense.
- **DV:** provenance-reconstruction rate (full chain), **per-field attribution accuracy** (new).
- **Deliverable:** add per-field (per-claim-span) attribution scoring, not just
  "did all N segments arrive"; measure reconstruction under **real-model lossy
  paraphrase** (E4.1), where spans may merge/split.
- **Success:** CAPM = 1.00 whole-chain at all N; per-field attribution reported
  with its own accuracy number; identity-only/flat = 0 structured chain.
- **Depends on:** E4.1 (for lossy paraphrase).
- **Target:** `experiments/s2_nhop_erosion.py` + new per-field metric in `capm/benchmark/runner.py`.

### [ ] E1.3 — End-to-end task efficacy under attack

- **Status:** ❌
- **Claim:** CLAIM-1 at the **task** level (not verdict level).
- **Deliverable:** embed a laundering attack inside an actual agent task (port
  SAGA's `schedule-meeting` / `expense-report` scenarios from
  `reference_codes/saga-main/experiments/`); measure whether the *task outcome*
  (the action taken) is corrupted, with vs. without CAPM.
- **DV:** task success rate, harmful-action rate.
- **Success:** CAPM prevents the corrupted action that baselines allow.
- **Why it matters:** reviewers distrust verdict-only metrics; they want the
  attack to cause real harm the defense then prevents.
- **Depends on:** E5.4 (harness), E4.1 (real responders).
- **Target:** new `experiments/e1_3_task_efficacy.py`.

---

## §2 — Soundness / formal experiments (CLAIM-3 Soundness)

### [ ] E2.1 — Warrant-ceiling soundness argument (formal)

- **Status:** ❌ — **highest-value formal gap; SAGA has proofs and we don't.**
- **Claim:** CLAIM-3. Type: formal, not empirical.
- **Deliverable:** a ProVerif/Verifpal model (mirror `reference_codes/saga-main/proofs/`)
  of the manifest-signing + warrant-binding protocol, proving: *an agent that
  does not control the origin cannot produce a verifying manifest asserting
  warrant above the origin's class ceiling.*
- **Success:** secrecy/authenticity queries hold in ProVerif; the warrant
  monotonicity lemma is stated and discharged.
- **Note:** this is the direct formal answer to the Semantic-Laundering theorem
  (the option-(a) stance). State precisely what is assumed (honest origin
  declaration) vs. proven — E3.2 is the boundary of this proof.
- **Depends on:** none (can start now); informs E3.3.
- **Target:** new `proofs/proverif/capm_manifest.pv`, `proofs/verifpal/capm.vp`.

### [x] E2.2 — Monotonicity verification (empirical companion to E2.1)

- **Status:** ✅ done.
- **Claim:** CLAIM-3.
- **Current code:** `experiments/s2_nhop_erosion.py`, `tests/test_capm.py::test_warrant_monotone_non_increasing`.
- **DV:** warrant level along every honest path.
- **Success:** warrant non-increasing on honest chains; strictly lower with a
  low-warrant origin. **Already passing — keep as the empirical check on E2.1.**
- **Maintenance:** re-confirm it still holds once real-model paraphrase (E4.1)
  introduces noisy transformation labels.

### [ ] E2.3 — Forgery / tamper battery (extend)

- **Status:** 🟡 (3 cases exist; 6 more required)
- **Claim:** CLAIM-3.
- **Current code:** `experiments/s3_textonly_and_tamper.py` covers: broken
  hash-link, unknown signer, off-manifest text edit.
- **Deliverable — add these forgery cases:**
  1. signature replay across segments
  2. VC-substitution
  3. segment reordering
  4. segment deletion (truncation)
  5. downgraded-transformation-type lie (claim VERBATIM for a paraphrase)
  6. cross-manifest splice (graft a segment from another chain)
- **Success:** every forgery → `REJECT` or capped warrant; **no** forgery → `ACCEPT`.
- **Depends on:** none; case 5 overlaps E3.1's defense (soft-binding).
- **Target:** extend `experiments/s3_textonly_and_tamper.py`; add cases to `tests/test_capm.py`.

---

## §3 — Adaptive adversary experiments (CLAIM-4 Robustness) — biggest gap

> All ❌. A non-adaptive attacker is a workshop result; these are the
> highest-priority new work after the real harness exists.

### [ ] E3.1 — Lying-transformation adversary

- **Status:** ❌
- **Adversary:** labels a `GENERATION` as `VERBATIM` to dodge the fidelity penalty.
- **Defense under test:** soft-binding / watermark mismatch — delivered text
  does not match a verbatim claim of its declared input.
- **DV:** ASR vs. detection rate of the lie.
- **Success:** CAPM detects the transformation lie above chance; ASR stays low.
- **Depends on:** a real soft-binding/watermark detector (currently a toy
  token-set hash in `capm/warrant/evaluator.py::_soft_binding_ok`).
- **Target:** new `attacks/adaptive/lying_transformation.py` + `experiments/e3_1_lying_transformation.py`.

### [ ] E3.2 — High-warrant-origin capture  ⚑ closes the "by-construction" caveat

- **Status:** ❌ — **implement early; it defines the honest boundary of CLAIM-1/3.**
- **Adversary:** does not inject at an editable page — instead spoofs/compromises
  a source it can get classified as `AUTHORITATIVE_API`, then poisons it (i.e.
  **lies about the source class itself**, not just the asserted warrant).
- **Point:** CAPM bounds warrant by origin; if the origin is high-warrant and
  compromised, CAPM should *not* magically catch it. This tests — and bounds —
  the claim.
- **DV:** ASR; whether provenance still correctly **attributes** the bad claim
  to the captured origin (enabling post-hoc revocation).
- **Success:** report honestly as a limitation **and** show attribution still
  works, motivating origin-integrity as a separate composable layer.
- **Depends on:** none; this is the experiment that proves the headline number
  is not purely by construction.
- **Target:** new `attacks/adaptive/origin_capture.py` + `experiments/e3_2_origin_capture.py`.

### [ ] E3.3 — Manifest-forgery adversary

- **Status:** ❌
- **Adversary:** fabricate a signature / VC for a trusted DID.
- **Defense under test:** Ed25519 + CA verification (where SAGA's Plane-1
  guarantees are load-bearing).
- **Success:** forgery infeasible without the private key; ties to E2.1.
- **Depends on:** E2.1 (formal companion); SAGA-backed crypto (`CAPM_USE_SAGA=1`).
- **Target:** new `experiments/e3_3_manifest_forgery.py` (negative test: all attempts → REJECT).

### [ ] E3.4 — Collusion / Sybil adversary

- **Status:** ❌
- **Adversary:** multiple malicious agents in the chain co-sign to launder.
- **DV:** ASR as a function of (#malicious / chain length).
- **Success:** because warrant is origin-bounded, colluding **relays** cannot
  raise warrant — show ASR independent of the number of colluding relays.
  (Distinctive result if it holds.)
- **Depends on:** E5.4 (multi-hop harness).
- **Target:** new `attacks/adaptive/collusion.py` + `experiments/e3_4_collusion.py`; feeds Figure 3.

### [ ] E3.5 — Adaptive optimisation loop

- **Status:** ❌
- **Adversary:** iteratively searches (gradient-free / LLM-driven) for
  content/prompts that maximise downstream acceptance against CAPM.
- **DV:** ASR over attack iterations (does it climb?).
- **Success:** ASR stays bounded as the adversary adapts; report the curve.
- **Depends on:** E4.1 (real responders to attack), E5.4.
- **Target:** new `attacks/adaptive/optimization_loop.py` + `experiments/e3_5_adaptive_loop.py`; feeds Figure 3.

---

## §4 — Real-model experiments / de-simulation (CLAIM-1/2/5 realism)

> All ❌. **Single most important credibility upgrade** — kills "you simulated it".

### [ ] E4.1 — Real LLM responders

- **Status:** ❌
- **Deliverable:** replace the deterministic `responder` in
  `capm/agents/agent.py` with real model calls (multiple families) that
  summarise/paraphrase/compose; **classify the actual transformation performed**
  so the evaluator applies the right fidelity penalty.
- **DV:** how often the model's self-reported transformation matches reality
  (ties to CoT-faithfulness literature); CAPM robustness when it doesn't.
- **Success:** CAPM result holds with real models; transformation
  mis-classification measured and bounded.
- **Note:** use the latest Claude models (e.g. `claude-opus-4-8`,
  `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`) via the Anthropic SDK for
  the frontier/mid tiers; pick one open-weight model for E4.2.
- **Depends on:** none (unblocks E1.x, E3.5, E5.x).
- **Target:** new `capm/agents/llm_responder.py`; wire via `docs/INTEGRATION.md` notes.

### [ ] E4.2 — Cross-model generality

- **Status:** ❌
- **IV:** model family (≥3: one frontier, one mid, one open-weight).
- **DV:** ASR, utility, provenance survival per model.
- **Success:** the containment result is not model-specific.
- **Depends on:** E4.1.
- **Target:** new `experiments/e4_2_cross_model.py` (sweeps model id over E1.1 matrix).

### [ ] E4.3 — Latent-source-bias correction

- **Status:** ❌
- **Claim:** CLAIM-1 robustness.
- **Deliverable:** use the `LLM-Latent-Source-Preferences` methodology
  (`reference_codes/LLM-Latent-Source-Preferences-ICLR-2026/`) as a
  *measurement*: show models have source biases, then show CAPM's **external**
  warrant is unaffected (because warrant is computed outside the model).
- **Success:** baseline acceptance correlates with model source-bias; CAPM
  acceptance does not.
- **Depends on:** E4.1.
- **Target:** new `experiments/e4_3_source_bias.py`.

---

## §5 — Real-attack-corpus experiments (CLAIM-1 realism)

> All ❌. Promote the abstractions in `attacks/injectors.py` to real code.

### [ ] E5.1 — ADMIT end-to-end

- **Status:** ❌
- **Deliverable:** wire the genuine ADMIT few-shot RAG-poisoning pipeline
  (arXiv:2510.13842) against a real retrieval source feeding the tail agent.
- **DV:** ASR at the published ADMIT poisoning rates, with vs. without CAPM.
- **Success:** reproduce ADMIT's high ASR on baselines; CAPM contains it.
- **Depends on:** E5.4 (harness), E4.1 (real responder consuming the retrieval).
- **Target:** new `attacks/corpora/admit/` + `experiments/e5_1_admit.py`.

### [ ] E5.2 — Flooding-Spread end-to-end

- **Status:** ❌
- **Deliverable:** use the KnowledgeSpread propagation setup (arXiv:2407.07791);
  manipulated knowledge persisting in multi-agent memory over rounds.
- **DV:** fraction of benign agents that adopt the manipulated claim over rounds.
- **Success:** CAPM blocks propagation that baselines permit.
- **Depends on:** E5.4, E4.1.
- **Target:** new `attacks/corpora/flooding_spread/` + `experiments/e5_2_flooding_spread.py`.

### [ ] E5.3 — Causality-Laundering end-to-end

- **Status:** ❌
- **Deliverable:** reproduce the denial-feedback laundering scenario from ARM
  (arXiv:2604.04035).
- **Success:** CAPM caps the borrowed-warrant claim at the origin ceiling (NONE).
- **Depends on:** E5.4.
- **Target:** new `attacks/corpora/causality_laundering/` + `experiments/e5_3_causality.py`.

### [ ] E5.4 — AgentDojo / cross-org benchmark harness  ⚑ substrate for everything real

- **Status:** ❌ — **build this first (priority #1).**
- **Deliverable:** extend an AgentDojo-style benchmark with **explicit
  organisational boundaries** between agents (the benchmark contribution
  itself). This is the substrate for E1.3, E3.4/E3.5, E4.x, E5.1–E5.3.
- **Success:** a reusable multi-hop, multi-org attack benchmark others can run.
- **Depends on:** none — unblocks the most downstream work.
- **Target:** new `capm/benchmark/agentdojo_crossorg/` package.

---

## §6 — Scale & stress experiments (CLAIM-5 Deployability)

### [ ] E6.1 — Overhead vs. chain length

- **Status:** 🟡 (single-point latency only)
- **Current code:** single latency point in `run_all` / `validate_against_saga`.
- **Deliverable:** latency & manifest-size as functions of **N hops** and
  **#sources**, measured on **SAGA's `Monitor`** (`saga.common.overhead`) for
  parity with SAGA's published numbers.
- **DV:** verification latency, signature count, serialized manifest bytes.
- **Success:** sub-ms per hop; growth clearly characterised (sub-linear or linear).
- **Depends on:** none.
- **Target:** new `experiments/e6_1_overhead_scaling.py`; feeds Table 3.

### [ ] E6.2 — Throughput / concurrency

- **Status:** ❌
- **Deliverable:** many concurrent chains; measure aggregate verification throughput.
- **Success:** overhead remains negligible relative to LLM inference latency
  (honest framing: CAPM cost ≪ model cost).
- **Depends on:** E6.1.
- **Target:** new `experiments/e6_2_throughput.py`.

### [ ] E6.3 — Manifest growth & compaction

- **Status:** ❌
- **Deliverable:** measure manifest growth on long chains; design + test a
  compaction / Merkle scheme.
- **Success:** manifest size stays practical at long N.
- **Depends on:** E6.1.
- **Target:** new `capm/manifest/compaction.py` + `experiments/e6_3_compaction.py`.

---

## §7 — Utility / trade-off experiments (CLAIM-5)

### [ ] E7.1 — Utility–resistance frontier  ⚑ turns the 0.75 into a headline

- **Status:** 🟡 → must become a real sweep
- **Current:** single utility=0.75 point.
- **Deliverable:** sweep `min_accept`, transformation `fidelity_penalty`, and
  boundary penalties; plot **ASR vs. utility** (the Pareto frontier).
- **DV:** ASR, utility across the grid.
- **Success:** a frontier showing CAPM dominates baselines (lower ASR at equal
  utility).
- **Depends on:** E1.1 with real inputs (ideally), but the sweep itself can be
  built now on current mechanism.
- **Target:** new `experiments/e7_1_frontier.py`; feeds Figure 1.

### [ ] E7.2 — False-positive (over-blocking) analysis

- **Status:** ❌
- **Deliverable:** on all-honest workloads, measure how often CAPM
  down-weights/quarantines good content, by transformation type and hop count.
- **Success:** characterise and bound the FPR; show it is tunable via E7.1.
- **Depends on:** E4.1 (real honest paraphrase), E7.1.
- **Target:** new `experiments/e7_2_false_positive.py`.

### [ ] E7.3 — Warrant-erosion calibration vs. ground truth

- **Status:** ❌
- **Deliverable:** test whether warrant levels correlate with actual factual
  fidelity (human- or oracle-labelled).
- **Success:** warrant correlates with measured faithfulness — closes the loop
  on the T2 "warrant-erosion magnitude" open question.
- **Depends on:** E4.1; a labelling oracle/dataset.
- **Target:** new `experiments/e7_3_calibration.py`.

---

## §8 — Ablations (each removes one CAPM component to show it is necessary)

> All ❌. Standard reviewer expectation; feeds Table 2.

### [ ] E8.1 — Remove origin-warrant ceiling

- **Predicted effect:** ASR rises (laundering succeeds).
- **Shows necessity of:** the ceiling (the anti-laundering core).
- **Target:** flag in `EvaluatorPolicy` / ablation runner.

### [ ] E8.2 — Remove per-transformation penalty

- **Predicted effect:** warrant stops eroding; utility up, soundness down.
- **Shows necessity of:** fidelity accounting.

### [ ] E8.3 — Remove signature verification

- **Predicted effect:** forgery succeeds.
- **Shows necessity of:** the cryptographic binding.

### [ ] E8.4 — Remove soft-binding

- **Predicted effect:** off-manifest edits undetected.
- **Shows necessity of:** the text-survives mechanism.

### [ ] E8.5 — Remove cross-org awareness (treat all as one org)

- **Predicted effect:** collapses toward the CaMeL baseline.
- **Shows necessity of:** the Plane-2 cross-org contribution.
- **Common deliverable for E8.x:** add ablation toggles to `EvaluatorPolicy`
  (`capm/warrant/evaluator.py`) and one driver that runs the full matrix with
  each component disabled in turn.
- **Success (all):** disabling each component degrades the predicted metric;
  the full system dominates every ablation.
- **Depends on:** E1.1 matrix.
- **Target:** new `experiments/e8_ablations.py` + policy toggles.

---

## §9 — Reproducibility / artifact-evaluation track

### [ ] E9.1 — Determinism & seeds

- **Status:** 🟡 (current experiments deterministic except latency)
- **Deliverable:** every stochastic experiment takes `--seed`; report mean ±
  95% CI over ≥10 seeds. Critical once real-model (E4.x) randomness enters.
- **Success:** every reported number is reproducible from a seed.
- **Target:** add `--seed` plumbing across `experiments/` and `capm/benchmark/runner.py`.

### [ ] E9.2 — One-command reproduction

- **Status:** 🟡 (`scripts/run_all_experiments.sh` exists)
- **Deliverable:** extend the script to regenerate **every figure and table**
  from raw → PDF, in a fixed environment (pinned versions or a container).
- **Success:** one command reproduces the whole paper's empirical content.
- **Target:** extend `scripts/run_all_experiments.sh`; add `Dockerfile` / pinned `requirements.txt`.

### [ ] E9.3 — Statistical reporting

- **Status:** ❌
- **Deliverable:** for every comparative claim, a significance test (bootstrap
  or McNemar for paired accept/reject), effect size, and CIs — not bare point
  estimates.
- **Success:** every comparison in Table 1 carries a p-value/effect size/CI.
- **Depends on:** E9.1.
- **Target:** new `capm/benchmark/stats.py`; consumed by all comparative experiments.

---

## Build order (from the plan's §10 priority, expressed as a dependency chain)

1. **E5.4** cross-org benchmark harness — substrate for everything real.
2. **E4.1 + E5.1** real models + real ADMIT — kills "you simulated it".
3. **E3.2** origin-capture — closes the by-construction caveat (do early, cheap).
4. **E3.1, E3.4, E3.5** adaptive adversary — kills "non-adaptive attacker".
5. **E2.1** ProVerif soundness — matches SAGA's bar; answers the theorem.
6. **E7.1** utility–resistance frontier — turns 0.75 into a headline.
7. **E8.x** ablations — standard reviewer expectation.
8. **E6.x, E9.x** scale + reproducibility — artifact badges and deployability.

Plan §10 calls items 1–5 here the difference between "promising" and "accept";
6–8 the difference between "accept" and "strong accept". E3.2 is inserted early
because it is cheap and it is the single experiment that proves the headline
result is not an artifact of the attack model.

## Target figures/tables each experiment feeds (from plan §11)

| Artifact                                                                           | Fed by                 |
| ---------------------------------------------------------------------------------- | ---------------------- |
| Table 1 — main result (ASR/utility/prov-surv/latency × defenses × real attacks) | E1.1, E4.x, E5.x, E9.3 |
| Figure 1 — utility–resistance Pareto frontier                                    | E7.1                   |
| Figure 2 — warrant-erosion curve vs. hops (honest vs. adversarial)                | E1.2, E2.2             |
| Figure 3 — adaptive-adversary ASR over iterations / vs. #colluders                | E3.5, E3.4             |
| Table 2 — ablations                                                               | E8.x                   |
| Table 3 — overhead on SAGA's Monitor vs. chain length                             | E6.1                   |
| Appendix — ProVerif model + queries; forgery battery                              | E2.1, E2.3             |
