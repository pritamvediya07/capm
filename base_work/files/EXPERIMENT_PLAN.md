# CAPM Experiment Plan for NDSS

This document specifies the **complete experiment suite** an NDSS submission
needs, separating what the testbed already has from what must still be built.
It is organised by the criteria a top-tier security reviewer applies, and each
experiment has: a stable ID, the claim/hypothesis it supports, the independent
and dependent variables, the baselines it runs against, the success criterion,
and its current status.

Legend for **Status**: ✅ implemented · 🟡 partial (mechanism only, needs real
inputs) · ❌ not yet built.

---

## 0. Reading guide: the experiments map to claims, not features

Every experiment must back a sentence in the paper's contributions. We make
five top-level claims; each numbered experiment below is tagged with the claim
it serves.

- **CLAIM-1 (Containment).** CAPM reduces laundering attack success rate (ASR)
  far below all baselines, across real attacks and real models.
- **CLAIM-2 (Preservation).** Provenance is verifiably reconstructed across N
  cross-org hops where existing systems carry no structured chain.
- **CLAIM-3 (Soundness).** Warrant cannot be inflated above its origin ceiling
  by any signer who does not control the origin — argued formally, not only
  measured.
- **CLAIM-4 (Robustness).** The defense holds against an adaptive adversary who
  knows CAPM exists.
- **CLAIM-5 (Deployability).** Verification overhead and utility cost are low
  enough for real use, measured on SAGA's substrate.

---

## 1. Core efficacy experiments (CLAIM-1, CLAIM-2)

### E1.1 — Laundering containment vs. baselines  ✅ (🟡 for real inputs)
- **Claim:** CLAIM-1. **Current:** `s1_single_hop_adversarial`, `run_all`.
- **IV:** defense ∈ {no-defense, identity-only, flat-provenance, CaMeL-single-runtime, CAPM}; attack ∈ {ADMIT, Flooding-Spread, Causality-Laundering}.
- **DV:** ASR, down-weight rate.
- **Success:** CAPM ASR statistically below every baseline (currently 0.00 vs 1.00).
- **Gap to close:** rerun with **real attack code** (E5.x) and **real models**
  (E4.x), not abstractions. The 0.00 only counts when the attacks are genuine.

### E1.2 — Provenance survival across N hops  ✅ (🟡)
- **Claim:** CLAIM-2. **Current:** `s2_nhop_erosion`.
- **IV:** n_hops ∈ {1..10}; defense.
- **DV:** provenance-reconstruction rate (full chain recovered), per-field attribution accuracy.
- **Success:** CAPM = 1.00 reconstruction at all N; identity-only/flat = 0 structured chain.
- **Gap:** add **per-field** attribution accuracy (not just whole-chain), and
  measure under lossy real-model paraphrase.

### E1.3 — End-to-end task efficacy under attack  ❌
- **Claim:** CLAIM-1 at the *task* level (not just the verdict level).
- **Setup:** an actual agent task (e.g. SAGA's schedule-meeting / expense-report
  scenarios) with a laundering attack embedded; measure whether the *task
  outcome* is corrupted.
- **DV:** task success rate, harmful-action rate, with vs. without CAPM.
- **Success:** CAPM prevents the corrupted action that baselines allow.
- **Why NDSS needs it:** reviewers distrust verdict-only metrics; they want the
  attack to cause real harm that the defense then prevents.

---

## 2. Soundness / formal experiments (CLAIM-3)

### E2.1 — Warrant-ceiling soundness argument  ❌
- **Claim:** CLAIM-3. **Type:** formal, not empirical.
- **Deliverable:** a ProVerif/Verifpal model (mirroring SAGA's `proofs/`) of the
  manifest-signing + warrant-binding protocol, proving: an agent that does not
  control the origin cannot produce a verifying manifest asserting warrant above
  the origin's class ceiling.
- **Success:** the secrecy/authenticity queries hold in ProVerif; the warrant
  monotonicity lemma is stated and discharged.
- **Why NDSS needs it:** SAGA (your substrate) has formal proofs; a defense
  paper that only shows experiments looks weaker by comparison. This also
  answers the Semantic-Laundering theorem head-on (your option-(a) stance).

### E2.2 — Monotonicity verification (empirical companion to E2.1)  ✅
- **Claim:** CLAIM-3. **Current:** `s2_nhop_erosion`, `test_warrant_monotone…`.
- **DV:** warrant level along every honest path.
- **Success:** warrant is non-increasing on honest chains; strictly lower with a
  low-warrant origin. (Already passing; keep as the empirical check on E2.1.)

### E2.3 — Forgery / tamper battery  ✅ (extend)
- **Claim:** CLAIM-3. **Current:** `s3_textonly_and_tamper`.
- **Cases now:** broken hash-link, unknown signer, off-manifest text edit.
- **Add:** signature replay across segments, VC-substitution, segment reordering,
  segment deletion, downgraded-transformation-type lie, cross-manifest splice.
- **Success:** every forgery → REJECT or capped warrant; none → ACCEPT.

---

## 3. Adaptive adversary experiments (CLAIM-4) — the biggest current gap

A non-adaptive attacker is a workshop result. NDSS reviewers will ask "what if
the attacker knows your defense?" These are all ❌ and are the highest-priority
new work.

### E3.1 — Lying-transformation adversary  ❌
- **Adversary:** labels a GENERATION as VERBATIM to avoid the fidelity penalty.
- **Defense response:** soft-binding / watermark mismatch detection (the text
  doesn't match a verbatim claim of its input).
- **DV:** ASR vs. detection rate of the lie.
- **Success:** CAPM detects the transformation lie above chance; ASR stays low.

### E3.2 — High-warrant-origin capture  ❌
- **Adversary:** instead of injecting at an editable page, compromises or spoofs
  a source it can get classified as AUTHORITATIVE_API, then poisons it.
- **Point:** CAPM bounds warrant by *origin*; if the origin itself is high-warrant
  and compromised, CAPM should *not* magically catch it — this tests the honest
  boundary of the claim.
- **DV:** ASR; and whether the provenance still correctly *attributes* the bad
  claim to the captured origin (enabling post-hoc revocation).
- **Success:** we report this honestly as a limitation + show attribution still
  works, motivating origin-integrity as a composable separate layer.

### E3.3 — Manifest-forgery adversary  ❌
- **Adversary:** tries to fabricate a signature / VC for a trusted DID.
- **Defense response:** Ed25519 + CA verification (this is where SAGA's Plane-1
  guarantees are load-bearing).
- **Success:** forgery infeasible without the private key; ties to E2.1.

### E3.4 — Collusion / Sybil adversary  ❌
- **Adversary:** multiple malicious agents in the chain co-sign to launder.
- **DV:** ASR as a function of (#malicious / chain length).
- **Success:** because warrant is origin-bounded, colluding *relays* cannot
  raise warrant; show ASR independent of the number of colluding relays. This is
  a strong, distinctive result if it holds.

### E3.5 — Adaptive optimisation loop  ❌
- **Adversary:** an attacker that iteratively searches for prompts/content that
  maximise downstream acceptance against CAPM (gradient-free / LLM-driven).
- **DV:** ASR over attack iterations (does it climb?).
- **Success:** ASR stays bounded as the adversary adapts; report the curve.

---

## 4. Real-model experiments (de-simulation) — CLAIM-1/2/5 realism

All ❌. This is the single most important credibility upgrade.

### E4.1 — Real LLM responders  ❌
- **Setup:** replace deterministic responders with real model calls (multiple
  model families) that summarise/paraphrase/compose; classify the actual
  transformation performed.
- **DV:** how often the model's self-reported transformation matches reality
  (ties to CoT-faithfulness literature), and CAPM's robustness when it doesn't.
- **Success:** CAPM result holds with real models; transformation
  mis-classification is measured and bounded.

### E4.2 — Cross-model generality  ❌
- **IV:** model family (≥3, e.g. one frontier, one mid, one open-weight).
- **DV:** ASR, utility, provenance survival per model.
- **Success:** the containment result is not model-specific.

### E4.3 — Latent-source-bias correction  ❌
- **Claim:** CLAIM-1 robustness. Uses the LLM-Latent-Source-Preferences
  methodology as a *measurement*: show models have source biases, then show
  CAPM's external warrant is unaffected by them (because warrant is computed
  outside the model).
- **Success:** baseline acceptance correlates with model source-bias; CAPM
  acceptance does not.

---

## 5. Real-attack-corpus experiments — CLAIM-1 realism

All ❌. Promote the abstractions in `attacks/injectors.py` to real code.

### E5.1 — ADMIT end-to-end  ❌
- Wire the genuine ADMIT poisoning pipeline (few-shot RAG poisoning) against a
  real retrieval source feeding the tail agent.
- **DV:** ASR at the published ADMIT poisoning rates, with vs. without CAPM.
- **Success:** reproduce ADMIT's high ASR on baselines; CAPM contains it.

### E5.2 — Flooding-Spread end-to-end  ❌
- Use the KnowledgeSpread propagation setup; manipulated knowledge persisting in
  multi-agent memory.
- **DV:** fraction of benign agents that adopt the manipulated claim over rounds.
- **Success:** CAPM blocks propagation that baselines permit.

### E5.3 — Causality-Laundering end-to-end  ❌
- Reproduce the denial-feedback laundering scenario from ARM.
- **Success:** CAPM caps the borrowed-warrant claim at the origin ceiling (NONE).

### E5.4 — AgentDojo / cross-org benchmark harness  ❌
- Extend an AgentDojo-style benchmark with explicit organisational boundaries
  (the benchmark contribution itself). This is the substrate for E1.3, E4.x, E5.x.
- **Success:** a reusable multi-hop, multi-org attack benchmark others can run.

---

## 6. Scale & stress experiments (CLAIM-5)

### E6.1 — Overhead vs. chain length  🟡
- **Current:** single-point latency in `run_all`/`validate_against_saga`.
- **Extend:** latency & manifest-size as functions of N hops and #sources;
  measured on **SAGA's Monitor** for parity with SAGA's published numbers.
- **DV:** verification latency, signature count, serialized manifest bytes.
- **Success:** sub-ms per hop; sub-linear or linear, clearly characterised.

### E6.2 — Throughput / concurrency  ❌
- Many concurrent chains; measure aggregate verification throughput.
- **Success:** overhead remains negligible relative to LLM inference latency
  (the honest framing: CAPM cost ≪ model cost).

### E6.3 — Manifest growth & compaction  ❌
- Long chains grow the manifest; measure growth and test a compaction/merkle
  scheme.
- **Success:** manifest size stays practical at long N.

---

## 7. Utility / trade-off experiments (CLAIM-5)

### E7.1 — Utility–resistance frontier  🟡 → ❌ (must be a real sweep)
- **Current:** single utility=0.75 point.
- **Build:** sweep `min_accept`, transformation `fidelity_penalty`, boundary
  penalties; plot ASR vs. utility (the Pareto frontier).
- **DV:** ASR, utility across the grid.
- **Success:** a frontier showing CAPM dominates baselines (lower ASR at equal
  utility). **This converts the 0.75 "weakness" into a headline figure.**

### E7.2 — False-positive (over-blocking) analysis  ❌
- On all-honest workloads, how often does CAPM down-weight/quarantine good
  content, by transformation type and hop count?
- **Success:** characterise and bound the FPR; show it is tunable via E7.1.

### E7.3 — Warrant-erosion calibration vs. ground truth  ❌
- Do warrant levels correlate with actual factual fidelity (human or oracle
  labelled)? Validates that the lattice means something.
- **Success:** warrant correlates with measured faithfulness — closes the loop on
  the T2 "warrant-erosion magnitude" open question.

---

## 8. Ablations (every NDSS paper needs these)

All ❌. Each removes one CAPM component to show it is necessary.

| ID | Remove… | Predicted effect | Shows necessity of |
|----|---------|------------------|--------------------|
| E8.1 | origin-warrant ceiling | ASR rises (laundering succeeds) | the ceiling (the anti-laundering core) |
| E8.2 | per-transformation penalty | warrant stops eroding; utility up, soundness down | fidelity accounting |
| E8.3 | signature verification | forgery succeeds | the cryptographic binding |
| E8.4 | soft-binding | off-manifest edits undetected | text-survives mechanism |
| E8.5 | cross-org awareness (treat all as one org) | collapses toward CaMeL baseline | the Plane-2 cross-org contribution |

---

## 9. Reproducibility / artifact-evaluation track

NDSS runs an Artifact Evaluation. Plan for the badges.

### E9.1 — Determinism & seeds  🟡
- Every stochastic experiment takes a `--seed`; report mean ± 95% CI over ≥10
  seeds. (Current experiments are deterministic except latency — extend the
  real-model ones.)

### E9.2 — One-command reproduction  🟡
- `scripts/run_all_experiments.sh` exists; extend to regenerate **every figure
  and table** from raw to PDF, with a fixed environment (pinned versions, or a
  container).

### E9.3 — Statistical reporting  ❌
- For every comparative claim: significance test (e.g. bootstrap or McNemar for
  paired accept/reject), effect size, and CIs — not bare point estimates.

---

## 10. Priority ordering (what to build first)

If time is bounded, build in this order — each unlocks the next and maps to the
NDSS-readiness gaps:

1. **E5.4** cross-org benchmark harness — substrate for everything real.
2. **E4.1 + E5.1** real models + real ADMIT — kills "you simulated it".
3. **E3.1, E3.4, E3.5** adaptive adversary — kills "non-adaptive attacker".
4. **E2.1** ProVerif soundness — matches SAGA's bar; answers the theorem.
5. **E7.1** utility–resistance frontier — turns the 0.75 into a headline.
6. **E8.x** ablations — standard reviewer expectation.
7. **E6.x, E9.x** scale + reproducibility — artifact badges and deployability.

Items 1–4 are the difference between "promising" and "accept". 5–7 are the
difference between "accept" and "strong accept".

---

## 11. Mapping to the paper's figures/tables (target)

- **Table 1** — main result: ASR/utility/prov-survival/latency × defenses × real
  attacks (E1.1, E4.x, E5.x).
- **Figure 1** — utility–resistance Pareto frontier (E7.1).
- **Figure 2** — warrant-erosion curve vs. hops, honest vs. adversarial (E1.2/E2.2).
- **Figure 3** — adaptive-adversary ASR over iterations (E3.5) and vs. #colluders (E3.4).
- **Table 2** — ablations (E8.x).
- **Table 3** — overhead on SAGA's Monitor vs. chain length (E6.1).
- **Appendix** — ProVerif model + queries (E2.1); forgery battery (E2.3).
