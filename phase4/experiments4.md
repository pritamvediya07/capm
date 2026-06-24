# CAPM Phase 4 — Experiments Playbook (`experiments4.md`)

### Consolidation & Finalization: the implementation-level to-do list

**How to read this file.** This is the executable counterpart to `CAPM_Phase4_Consolidation.md`, built in the same six-part format as `experiments3.md` / `PHASE2_PLAYBOOK.md`. Every experiment uses the same structure so it reads as an actionable checklist:

- **What to build** — exact files / functions / modules to create or change.
- **Procedure** — the numbered steps to run.
- **Variants / ways to test** — every dimension to sweep (this is where the depth lives).
- **Data to record** — the exact CSV columns.
- **Pass / interpretation** — the criterion and what the result *means*.
- **Failure modes** — what would invalidate the result.

> **What Phase 4 is.** Phase 4 is **not a new mechanism**. It is consolidation: (1) fix the seven verification findings, (2) pull every claim back to exactly what the evidence supports, (3) close the model-scale gap on Qwen2.5, (4) substantiate the systems claim with real transport. The discipline is **subtraction, not addition** — the result is strongest when every sentence survives a reviewer re-running the code. Nothing here invents new scope; if a task starts to feel like a new contribution, it belongs in future work.

> **Hardware / model decision (locked).** Primary model = **Qwen2.5-7B-Instruct** and **Qwen2.5-14B-Instruct** only (not 72B). Target hardware = one **96 GB NVIDIA Blackwell**. Both 7B (~15 GB) and 14B (~29 GB) load in **bf16** with ample room for activation capture, so **quantization is an optional ablation here, not a constraint** — the probe characterizes the native bf16 model. Mistral and DeepSeek are **out of scope for this phase** (reserved for later cross-architecture ablations).

> **The serving rule (non-negotiable).** B.1/B.2 read the relay model's **hidden states**. vLLM/Ollama endpoints expose text/logprobs, **not** internal hidden states — they are **insufficient** for the probe path. The usage-probe experiments run through a **white-box `transformers` wrapper** with `output_hidden_states=True`. vLLM is fine for the text-generation-heavy parts (relay transformations in A/D; the NLI/support sensors are text-in/text-out). This split is wired once in shared infrastructure and must not be violated.

---

# EXECUTION ORDER (load-bearing — do not reorder)

The order de-risks downstream work: **correctness → honesty → scale → systems.** A scale run on un-fixed (leaked) code just reproduces the leak at higher fidelity.

1. [ ] **WS1 — correctness corrections** (P4-1A D.1 leakage, P4-1B D.3 locality, P4-1C A.1 table) — days, not weeks. These gate everything.
2. [ ] **WS2 — honesty alignment** (P4-2.x the four LOW findings) + **WS2B** (P4-2B probe-value table) — hours.
3. [ ] **WS4 — statistical hygiene** (P4-4 unit-of-analysis + CIs) — small, do it alongside WS2.
4. [ ] **WS3 — Qwen2.5 scale run** (P4-3.B1, .B2, .C2, .D2, .F3) — the biggest external-validity move. Only after WS1 (no point scaling leaked code).
5. [ ] **WS5 — systems substantiation** (P4-5A Build A acquisition wrapper, P4-5B Build B gRPC/mTLS transport) — weeks; the credible→demonstrated conversion; submission blockers.
6. [ ] **WS6 — final audit gate** (P4-6 exit-check sweep) — verify all nine Definition-of-Done checks pass before declaring submission-ready.

anBackbone correctness = 1–3. Scale credibility = 4. Systems credibility = 5. Sign-off = 6.

---

# SHARED INFRASTRUCTURE (build/modify once, before the experiments that need it)

- [ ] **`p4/sensors/score.py`** — the corrected scorer. `faith = NLI(premise = rendered_source_ctx, claim)` (premise is the **rendered source document `ctx`**, never a synthesized `"The {field} is {true_value}."` sentence). Emits `(u, s, faith)` per claim and caches them. This single change is the root fix for both D.1 (1A) and E.4 (cosmetic).
- [ ] **`p4/models/whitebox.py`** — white-box `transformers` wrapper: loads `Qwen/Qwen2.5-7B-Instruct` / `Qwen/Qwen2.5-14B-Instruct` in bf16, runs generation with `output_hidden_states=True`, and records **answer-token activations per claim** at the declared layer set. Exposes a clean `get_claim_activations(prompt, answer_span) -> {layer: tensor}` API. **This is the only path B.1/B.2 may use.**
- [ ] **`p4/models/served.py`** — vLLM client for the **text-generation** parts only (relay transformations, A/D generation). Never used for probe activations.
- [ ] **`p4/sensors/probe.py`** — usage probe: logistic regression over the wrapper's normalized answer-token hidden vector; per-model retrain; emits `u(c') ∈ [0,1]` = P(context-driven). Records `model`, `layer`, `dtype`, `pooling`.
- [ ] **`p4/sensors/support.py`** — `support` sensor: calibrated embedding similarity (current MiniLM/BGE/E5 encoder), verifier-side. Records `encoder_id`.
- [ ] **`p4/sensors/nli.py`** — `faith` sensor: DeBERTa-v3 NLI (`-base` and `-large`), premise = `ctx`. Records `nli_model`.
- [ ] **`p4/sensors/schema_numeric_rule.py`** — CVSS-band / structured-field comparator (carried from Phase 3; 9.0–10.0 → Critical, etc.). Owns digit↔word band judgments so abstraction is `entail`, genuine flip is `contradict`.
- [ ] **`p4/warrant/realized.py`** — `g = min(u, s, faith)` (default form from Phase-3 D.1) and `w = min(w_decl, g·w_decl)`; hard-assert `g ≤ 1` and `w ≤ w_decl` before returning (clamp invariant).
- [ ] **`p4/stats/units.py`** — the unit-of-analysis helper: per-experiment, declares the independent unit (grid cell / advisory / claim) and computes CIs at that unit, never per-correlated-row.
- [ ] **`p4/audit/recompute_tables.py`** — regenerates every published table cell directly from its source CSV; the A.1 fix and the tree-wide stale-cell sweep run through here.
- [ ] **`docs/THREATS_TO_VALIDITY_P4.md`** — the honesty ledger, carried forward and extended: D.1 leakage fix + the construction-oracle-label caveat, probe runtime-access TCB, NLI numeric blind spot, support false-positive under distractors, Qwen-2.5-only scope (Mistral/DeepSeek deferred), bf16 default + quantization-as-ablation note, unit-of-analysis statements.

---

# WORKSTREAM 1 — THE THREE NON-OPTIONAL CORRECTIONS (gate everything)

## P4-1A — D.1 leakage fix (HIGH; mandatory before ANY calibration claim)

**What to build**

- [ ] The corrected `score.py` (shared infra) grounding `faith` in `ctx`.
- [ ] `p4/exp/p1a_calibration_fixed.py` — re-runs the D.1 calibration on the **leakage-free** features and reports the three-number breakdown.

**Procedure**

1. [ ] Confirm in code that **no input feature is a deterministic function of the label** (`trust = 1 iff effect==survived iff value==true_value`); in particular `faith` no longer reads `true_value`.
2. [ ] Recompute `(u, s, faith)` for all scored claims with the fixed scorer.
3. [ ] Report **three separate numbers**: (i) `u+s` only; (ii) `faith` only (source-grounded); (iii) full `g = min(u, s, faith)`.
4. [ ] Run the **faith-adds-value test**: logistic AUC of `u+s` vs `u+s+faith`; report the marginal lift.

**Variants / ways to test**

- [ ] Random hold-out **and** vendor domain-holdout (same splits as Phase-3 D.1, so the delta is comparable).
- [ ] Both Qwen2.5-7B and 14B (the probe `u` differs per model).
- [ ] Faith with DeBERTa-v3 `-base` vs `-large` (does a stronger NLI change the marginal lift?).
- [ ] Sanity control: re-introduce the leaked premise and confirm the AUC jumps back up (proves the leak was the cause, not noise).

**Data to record**
`model, feature_set(u+s | faith | g), nli_model, split(random|domain), auc, ece, faith_marginal_lift_over_us`

**Pass / interpretation**

- [ ] No feature derives from the label's defining quantity (code-verified).
- [ ] The three numbers are reported separately; the faith-adds-value question is answered explicitly.
- [ ] **If `faith` adds marginal AUC over `u+s`**, report the lift and keep it as a calibration contributor. **If it does not**, reposition `faith` as a **contradiction-specific safety signal** (it earns its place via C.2 contradiction recall, not calibration) — and say so plainly.
- [ ] No calibration adjective ("calibrated / non-arbitrary / domain-generalizing") appears anywhere until this rerun is in hand.

**Failure modes**

- [ ] AUC barely drops → check the leak was actually removed (the sanity control must show the jump); a tiny drop with the control *not* jumping means the fix didn't land.
- [ ] `u+s` collapses to chance once leakage is gone → then the *honest* finding is that structured-source calibration rests mostly on the (now-removed) signal; report it, and lean on the by-construction guarantee rather than calibration. This is an acceptable, honest outcome.

## P4-1B — D.3 locality (MEDIUM; do BOTH, invariant + independent recomputation)

**What to build**

- [ ] `p4/exp/p1b_locality.py` — (a) states the structural invariant explicitly in a docstring/assert, and (b) runs a **genuine** independence test via an independent code path.
- [ ] Remove the self-copy tautology (`w_benign_nocorrupt = list(w_benign)`) from the PASS gate.

**Procedure**

1. [ ] **Structural argument:** assert in code that `realized.py` has no cross-claim term — each claim's warrant is a function of its own `(u,s,faith)` and the document-level declared warrant only.
2. [ ] **Independent recomputation:** for each document, build the **corruption-free version** (remove the injected corruption), re-derive every sibling claim's warrant through the real scorer from scratch, and compare to the warrants from the corrupted document.
3. [ ] Contamination = any sibling whose warrant differs between the two independently-scored documents.

**Variants / ways to test**

- [ ] Corruption type: dropped / contradicted / fabricated.
- [ ] Corruption position: first / middle / last claim.
- [ ] 1 vs 2 corrupted claims out of N.
- [ ] Document size: 4-claim advisory vs larger record.
- [ ] **Negative control:** inject an artificial cross-claim term into a copy of `realized.py` and confirm the independent test now *detects* contamination (so the test has teeth — unlike the old tautology).

**Data to record**
`doc_id, n_claims, corruption_type, corruption_pos, sibling_warrant_corrupted_run, sibling_warrant_cleanrun, contaminated(bool), control_detects(bool)`

**Pass / interpretation**

- [ ] Real independence test shows **0 contamination** across all real configs, AND the negative control (artificial cross-claim term) is **detected** — proving the test is not vacuous.
- [ ] Report as: *"Locality follows structurally because each claim warrant depends only on its own sensor tuple and declared warrant; we additionally validate this with an independent corruption-free recomputation."*

**Failure modes**

- [ ] Negative control NOT detected → the "independent" path still shares state with the corrupted run; make it genuinely independent (re-instantiate the scorer, re-read inputs).
- [ ] Any real contamination → there is an unintended cross-claim coupling; find it in `realized.py` before claiming locality.

## P4-1C — A.1 table regeneration + tree-wide stale-cell sweep (MEDIUM)

**What to build**

- [ ] `p4/audit/recompute_tables.py` (shared infra) regenerating every published table cell from its CSV.

**Procedure**

1. [ ] Regenerate Table 2's relaunder row from `a1_raw.csv` → must yield `0.667 | 0.667 | 0.333 | 0.000`.
2. [ ] Confirm the impossible values (0.583, 0.417) are gone — every cell on this content-blind grid must be a multiple of 1/3.
3. [ ] **Tree-wide sweep:** for every table in `phase3_results.md` (and any carried into the paper), re-derive each cell from its source CSV; flag any hand-entered value that doesn't reproduce.

**Variants / ways to test**

- [ ] Grep for the specific stale values (`0.583`, `0.417`) across the whole results tree to confirm they appear only where they're being corrected.
- [ ] Spot-check at least one cell per table by hand against the CSV.

**Data to record**
`table_id, cell, published_value, recomputed_value, matches(bool), source_csv`

**Pass / interpretation**

- [ ] Every published table cell recomputes exactly from its source CSV (0 mismatches after the fix).

**Failure modes**

- [ ] More stale cells found → fix them all now; "stale cells travel in packs," and one wrong cell a reviewer catches discredits the rest.

---

# WORKSTREAM 2 — HONESTY ALIGNMENT ON THE FOUR LOW FINDINGS

## P4-2.1 — D.2 dominance claim correction (LOW)

**What to build**

- [ ] `p4/exp/p2_1_d2_dominance.py` — recompute the frontier dominance claim against the **content-blind baseline only**.

**Procedure**

1. [ ] Recompute, from `d2_frontier.csv`, the ASR-at-retention and retention-at-ASR for Phase-3 vs the **content-blind baseline** (verified-true claim).
2. [ ] Separately compute full-`g` vs NLI-only / support-only at the headline operating points; record the actual gap (expect ~0.003 at ASR≤0.05 — a quantization artifact, not dominance).
3. [ ] Edit all prose/captions: "dominates both single-sensor competitors" → "dominates the content-blind baseline"; drop "competitors fall in between."

**Variants / ways to test**

- [ ] Finer ASR grid → confirm the full-g-vs-NLI-only gap stays within quantization noise (it should not become systematic dominance).
- [ ] Both Qwen sizes (does the competitor relationship change at 14B? report if so).

**Data to record**
`operating_point, system(phase3|content_blind|nli_only|support_only), asr, retention, gap_vs_full_g`

**Pass / interpretation**

- [ ] Dominance is claimed **only** over the content-blind baseline (verified); no claim of dominance over single-sensor competitors.

**Failure modes**

- [ ] Tempting to keep "competitors fall in between" because it's *almost* true → don't; a 0.003 reversal at the headline point makes it false where it matters most.

## P4-2.2 — F.1 partial-correlation disclosure (LOW; highest-value honesty fix)

**What to build**

- [ ] `p4/exp/p2_2_f1_partials.py` — recompute influence correlation with **within-cluster and partial** controls.

**Procedure**

1. [ ] Recompute pooled Spearman/Pearson ρ(g, v) from `f1_influence.csv` (reproduce the 0.62/0.75).
2. [ ] Compute **within-benign**, **within-attack**, and **partial ρ(g,v | label)**.
3. [ ] Rephrase the headline: "g and v both **separate attack from benign**" — NOT "g tracks the continuous magnitude of influence."

**Variants / ways to test**

- [ ] Both Qwen sizes.
- [ ] Permutation test on the within-cluster correlations (report p-values).

**Data to record**
`model, pooled_rho, within_benign_rho, within_attack_rho, partial_rho_given_label, perm_p`

**Pass / interpretation**

- [ ] Partial/within-cluster correlations are reported **alongside** the pooled number; the headline claims separation, not magnitude-tracking. Reporting this unprompted converts a reviewer gotcha into a credibility signal.

**Failure modes**

- [ ] Reporting only the pooled ρ → a reviewer recomputes the partial in five minutes and the omission reads as spin. Always show both.

## P4-2.3 — F.3 sensor-attribution narration fix (LOW)

**What to build**

- [ ] `p4/exp/p2_3_f3_attribution.py` — recompute, from `f3_adaptive.csv`, which sensor is binding per synthesis row.

**Procedure**

1. [ ] Confirm `u` is the binding `min` sensor in the synthesis rows (Phase-3: 40/40).
2. [ ] Edit narration: "the usage probe flags the synthesized conclusion as **parametric** (context-independent)"; do **not** credit support; do **not** call the usage signal "grounding" (it measures context-vs-parametric, not entailment).

**Data to record**
`synthesis_row_id, u, s, faith, binding_sensor, residual`

**Pass / interpretation**

- [ ] Narration credits the usage probe alone and names what it measures correctly.

**Failure modes**

- [ ] Calling `u` "grounding" → conflates it with the support sensor; precise sensor naming is what makes the 2B table defensible.

## P4-2.4 — E.4 premise grounding (LOW; cosmetic, already in shared infra)

**What to build**

- [ ] Confirm the shared-infra `score.py` change grounds `faith` against `ctx` everywhere (E.4 and D.1 share this root fix).

**Procedure**

1. [ ] Re-run the E.4 black-box fallback with `faith` grounded in `ctx`; confirm the security result (0 inflation) is unchanged and the utility numbers move negligibly (Phase-3 A/B: 37/40 identical labels).

**Data to record**
`case_id, faith_ctx, faith_oldpremise, label_changed(bool), warrant_exceeds_baseline(bool — must be False)`

**Pass / interpretation**

- [ ] `faith` is grounded in `ctx`; the premise construction is noted in the threats doc; numbers unaffected; 0 inflation holds.

---

# WORKSTREAM 2B — DEFEND THE USAGE PROBE FROM LOOKING REDUNDANT

## P4-2B — Sensor-attribution table (single-sensor catch + binding rate)

**What to build**

- [ ] `p4/exp/p2b_sensor_attribution.py` building the per-case-type table with **two precisely-defined metrics**.

**Definitions (must be implemented exactly):**

- **Single-sensor catch:** a sensor *catches* a claim if its score **alone** — with the other two sensors neutralized to 1.0 — pushes the claim below the down-weight/quarantine threshold.
- **Binding sensor:** the sensor that is the **minimum** in `g = min(u,s,faith)` **and** whose minimum crosses the decision threshold.

**Procedure**

1. [ ] For each attack case type (source-absent addition, synthesis-like conclusion, exact contradiction, field omission), compute per-sensor **single-sensor catch rate** and the **binding-sensor rate** from the CSVs.
2. [ ] Fill the table with real numbers (no "strong/weak" labels):

| Case type                 | support single-catch | NLI single-catch | usage single-catch | binding sensor (rate) |
| ------------------------- | -------------------- | ---------------- | ------------------ | --------------------- |
| source-absent addition    | (rate)               | (rate)           | (rate)             | usage (rate)          |
| synthesis-like conclusion | (rate)               | (rate)           | (rate)             | usage (rate)          |
| exact contradiction       | (rate)               | (rate)           | (rate)             | NLI (rate)            |
| field omission            | matcher              | n/a              | n/a                | matcher               |

3. [ ] Identify the rows where **support+NLI both fail (low single-catch) but usage catches** — those rows are the probe's justification.

**Variants / ways to test**

- [ ] Both Qwen sizes (does the probe's unique-catch region hold at 14B?).
- [ ] Threshold sensitivity: recompute at the accept/down-weight/quarantine cutoffs ±0.1.
- [ ] Subtlety levels for source-absent / synthesis (blatant vs plausible) — the probe's edge should be clearest on the cases where lexical overlap is highest (so support/NLI are fooled).

**Data to record**
`case_type, subtlety, model, support_single_catch, nli_single_catch, usage_single_catch, binding_sensor, binding_rate, threshold`

**Pass / interpretation**

- [ ] There is at least one case type where support+NLI single-catch is low **and** usage single-catch (and binding rate) is high — concrete evidence the probe is not redundant.
- [ ] The probe is framed for **source-absent additions / synthesis / prose**; never claimed essential for exact-contradiction or omission (where NLI / the matcher already suffice).

**Failure modes**

- [ ] If usage never has a unique-catch region even at scale → the honest conclusion is that on *structured* sources support+NLI suffice, and the probe's value is **prose/future-work** only; say so, and down-scope the probe's role in the current paper rather than overselling it.

---

# WORKSTREAM 3 — THE QWEN2.5 SCALE RUN (B.1, B.2, C.2, D.2, F.3)

> All five re-run the Phase-3 experiments on **Qwen2.5-7B and 14B**, reporting **deltas vs the small-model Phase-3 numbers**. B.1/B.2 use the **white-box `transformers` wrapper** (not vLLM). Report the precision/layer/token spec for every probe number.

## P4-3.B1 — Probe transfer on Qwen2.5 (does the usage probe hold at scale?)

**What to build**

- [ ] `p4/exp/p3_b1_probe_transfer.py` using `whitebox.py`; self-supervised context-vs-parametric dataset from real CVE advisories (same construction as Phase-3 B.1).
- [ ] Text-only controls: BoW (TF-IDF) and static-embedding (layer-0) — the lexical-shortcut refutation.

**Procedure**

1. [ ] Build the context/parametric dataset (advisory-disjoint splits).
2. [ ] For Qwen2.5-7B and 14B: extract answer-token hidden states (declared layers), train the probe, evaluate macro-F1 vs the two text-only controls.
3. [ ] **Cross-size transfer:** train on 7B, test on 14B and vice-versa (expect failure — different hidden geometry — confirming per-model retrain).
4. [ ] OOD transfer (general-knowledge QA) without retraining.

**Variants / ways to test**

- [ ] **dtype:** bf16 default; **plus** one quantized ablation (8-bit) → report probe-AUC delta (quantization-sensitivity, measured not assumed).
- [ ] **layers:** final-only vs final+middle vs all (best-layer sweep); declare which are stored.
- [ ] **pooling:** mean vs min over answer-span tokens.
- [ ] 7B vs 14B (does separability improve, saturate, or degrade with size?).

**Data to record**
`model, dtype, layer, pooling, macro_f1, bow_f1, static_emb_f1, gap_vs_bow, gap_vs_static, ood_f1, cross_size_f1`

**Pass / interpretation**

- [ ] High macro-F1 (target ≳ 0.9 in-model) **and** a clear gap over both text-only controls → the usage signal is representational, not lexical, **at modern scale**.
- [ ] Cross-size transfer ≈ chance → confirms per-model retrain (carry the Phase-3 caveat forward, now on Qwen).
- [ ] Report the delta vs Phase-3 gpt2-family numbers explicitly.

**Failure modes**

- [ ] Probe ≈ text-only control at scale → the signal was lexical; this is a reportable negative that down-scopes the probe to prose/future work (and the by-construction guarantee still stands).
- [ ] Using a vLLM/Ollama endpoint instead of the white-box wrapper → no hidden states; the experiment is invalid. Enforce the wrapper.
- [ ] Lexical-separability caveat (answer-in-context overlap oracle = 1.0 on structured data) still applies — keep it disclosed, as in Phase-3.

## P4-3.B2 — Usage separation on Qwen2.5 (is `u` an actionable fabrication detector?)

**What to build**

- [ ] `p4/exp/p3_b2_usage_separation.py`; reuse the B.1 probe; apply to generator claims on **advisories disjoint from B.1 training**.

**Procedure**

1. [ ] Score 300 genuinely-sourced vs ~480 memory-substituted fabrications (4 subtlety levels: blatant / plausible / added / mixed).
2. [ ] Measure threshold-free AUC of `u` ranking sourced above fabricated, per model, mean vs min pooling.

**Variants / ways to test**

- [ ] Subtlety levels (the **plausible near-miss** is the honest weak case — track it explicitly).
- [ ] 7B vs 14B.
- [ ] bf16 vs 8-bit (does the fabrication-separation AUC move under quantization?).

**Data to record**
`model, dtype, pooling, subtlety, auc, n_sourced, n_fabricated`

**Pass / interpretation**

- [ ] Mean-agg AUC high overall (Phase-3 was 0.93); **report the plausible-near-miss AUC separately** as the declared residual that justifies the multi-sensor `g` (this is the honesty the venue rewards).
- [ ] Delta vs Phase-3 reported.

**Failure modes**

- [ ] If plausible-near-miss separation *improves* a lot at 14B → good, report it; if it degrades → the multi-sensor argument is even more necessary, report that too. Either way, don't hide the weak case.

## P4-3.C2 — Contradiction vs valid abstraction on Qwen2.5-era NLI (does the faith sensor hold?)

**What to build**

- [ ] `p4/exp/p3_c2_nli_contradiction.py`; genuine-contradiction set + valid-abstraction control set + schema numeric rule.

**Procedure**

1. [ ] Generate genuine contradictions (severity 9.1→low; Win10/11→Win7-only; patch→no-patch; vendor swap) and the abstraction control (9.1→"Critical"; "KB123 released"→"a patch exists").
2. [ ] Run DeBERTa-v3 NLI (`-base` and `-large`) **with premise = `ctx`** + the schema numeric rule.
3. [ ] Measure genuine-recall and abstraction-FPR; isolate the CVSS-band recall with vs without the schema rule.

**Variants / ways to test**

- [ ] NLI size: `-base` vs `-large` (now that VRAM allows large).
- [ ] With vs without the schema numeric rule (must show the rule lifts band recall 0.50→1.00).
- [ ] Premise = `ctx` (rendered source) — confirm the E.4 grounding fix is in force here too.

**Data to record**
`nli_model, schema_rule(on|off), genuine_recall, abstraction_fpr, cvss_band_recall, premise_source(ctx)`

**Pass / interpretation**

- [ ] Genuine recall ≳ 0.9 **and** abstraction FPR low (valid abstraction scored `entail`); schema rule shown necessary for band cases.
- [ ] Delta vs Phase-3 reported; if `-large` changes the entail/neutral boundary materially, report it (this is exactly the "faith saturation could move at scale" risk).

**Failure modes**

- [ ] Larger NLI flags valid abstraction as contradiction (over-blocking) → the schema rule must own band cases; NLI handles prose only.
- [ ] Premise accidentally still built from gold value → re-check the shared `score.py` fix.

## P4-3.D2 — Security–utility frontier on Qwen2.5 (the centerpiece, at scale)

**What to build**

- [ ] `p4/exp/p3_d2_frontier.py`; attack+benign transformations through content-blind/per-claim CAPM, CAPM+Phase-4 (full `g` with the fixed scorer), and single-sensor references; sweep the accept threshold.

**Procedure**

1. [ ] Run the full transformation set on Qwen2.5-7B and 14B relays (text-gen via vLLM; sensor scoring via the fixed pipeline).
2. [ ] Trace the ASR-vs-benign-retention frontier; report against the **two correct baselines** (security vs per-claim CAPM; utility vs document-level CAPM).
3. [ ] Confirm no individual claim is raised above its declared warrant (the gain is localization).

**Variants / ways to test**

- [ ] Attack family: omission, contradiction, fabrication, evidence-loss, source-mixing, synthesis (truths-only).
- [ ] Chain length 1/2/4/8.
- [ ] Strictness sweep across the full knob range (makes it a frontier, not a point).
- [ ] 7B vs 14B.

**Data to record**
`model, operating_point, attack_family, hops, asr_vs_perclaim_capm, retention_vs_doc_capm, down_rank_rate, hard_block_rate`

**Pass / interpretation**

- [ ] CAPM+Phase-4 **wins the frontier by localization** vs the content-blind baseline (equal-or-lower ASR vs per-claim CAPM; higher retention vs document-level CAPM), **at modern scale**.
- [ ] Dominance claimed **only** over the content-blind baseline (per P4-2.1).
- [ ] Delta vs Phase-3 reported.

**Failure modes**

- [ ] "Blocks everything" (ASR 0, retention collapses) → over-blocking; recalibrate `g`. This is the failure the whole localization argument exists to refute — do not ship it.
- [ ] Frontier shifts unfavorably at 14B → report honestly; a scale-dependent frontier is still a result, and better found by you than a reviewer.

## P4-3.F3 — Adaptive adversary on Qwen2.5 (the core adversary result, at scale)

**What to build**

- [ ] `p4/exp/p3_f3_adaptive.py`; attacker who knows `u,s,faith,g` and the `min` rule, optimizing corruption to keep all sensors above threshold; black/grey/white-box knowledge + the synthesis attack.

**Procedure**

1. [ ] Run adaptive attacks against the full Phase-4 stack on Qwen2.5-7B/14B; measure residual ASR at ACCEPT (≥0.7) and DOWN-WEIGHT/usable (≥0.4).
2. [ ] Record which sensor is binding per case (feeds the 2B table).

**Variants / ways to test**

- [ ] Attacker knowledge: black → grey → white.
- [ ] Per-sensor evasion individually vs all simultaneously; correlated evasion.
- [ ] Synthesis (truths-only) attack — confirm the usage probe binds it (per F.3).
- [ ] 7B vs 14B.

**Data to record**
`model, attacker_knowledge, sensors_evaded, residual_asr_accept, residual_asr_downweight, binding_sensor, surviving_case_types`

**Pass / interpretation**

- [ ] **Residual ASR > 0 at DOWN-WEIGHT is expected and correct** (managed-residual posture); residual at ACCEPT should stay ~0 (the multi-sensor `min` holds `w<0.7`).
- [ ] The residual is **characterized** (grows with attacker knowledge), not tuned to zero.
- [ ] Delta vs Phase-3 reported; if the residual grows at scale, report it as the honest boundary.

**Failure modes**

- [ ] Tuning the residual toward zero → systems-demo mode; a measured "X% at cost C" is the goal.
- [ ] Adaptive attack reaches ACCEPT at scale → a real weakening; investigate whether a stronger model makes a sensor easier to satisfy, and report it.

---

# WORKSTREAM 4 — STATISTICAL HYGIENE

## P4-4 — Unit-of-analysis + corrected confidence intervals

**What to build**

- [ ] `p4/stats/units.py` (shared infra); a paper subsection stating the independent unit per experiment.

**Procedure**

1. [ ] **A.1 CIs:** recompute Wilson CIs **per grid cell** (24 deterministic cells), not per-row over 17,280 correlated rows.
2. [ ] **Unit-of-analysis statement**, per experiment: A.1 = grid cell; A.2 = advisory or field (state which per aggregation); B/D/F = advisory or claim (state explicitly; claims from one advisory are not independent); construction-oracle labels → **no human-style CIs**.
3. [ ] Sweep every other CI/significance number for the same iid-over-correlated-rows error.

**Variants / ways to test**

- [ ] Recompute at least one CI both ways (per-row vs per-unit) to show the per-row version was overstated.

**Data to record**
`experiment, independent_unit, n_units, metric, ci_low, ci_high, prev_per_row_ci_low, prev_per_row_ci_high`

**Pass / interpretation**

- [ ] Every CI reflects the true unit of independence; the paper has an explicit per-experiment unit-of-analysis statement.

**Failure modes**

- [ ] Reporting a construction-oracle metric with a human-style CI → implies a human study that didn't happen; label oracle metrics as such.

---

# WORKSTREAM 5 — SYSTEMS SUBSTANTIATION (submission blockers)

> These convert "cryptographic multi-runtime semantics, single-process execution" into a demonstrated multi-runtime system. They are weeks, not days, and are **blockers** — for NDSS the cross-org multi-runtime story is the heart of the contribution.

## P4-5A — Build A: acquisition wrapper (source_class from channel evidence)

**What to build**

- [ ] `p4/build_a/acquire.py` — three real acquisition paths: **HTTP**, **API**, **file/DB**, each deriving `source_class` from **observable channel evidence** per the deterministic policy table (not hand-set scenario metadata).
- [ ] The policy table itself as a versioned artifact (the I6/T4 seam the literature names as open).

**Procedure**

1. [ ] Acquire real content over each of the three channels; derive `source_class` from channel evidence (TLS/cert chain, API auth, file/DB origin) deterministically.
2. [ ] Feed the derived `source_class` into the existing manifest path; confirm warrants now rest on **measured** origin evidence.
3. [ ] Compare derived `source_class` against the Phase-3 hand-set values on the same scenarios (agreement + where channel evidence changes the class).

**Variants / ways to test**

- [ ] Each channel (HTTP/API/file-DB) independently and mixed.
- [ ] Adversarial channel evidence (spoofed cert, weak-auth API) → confirm the policy table degrades `source_class` correctly.
- [ ] Missing/ambiguous evidence → confirm conservative-default (degrade, never inflate).

**Data to record**
`channel, observed_evidence, derived_source_class, phase3_handset_class, agree(bool), degraded_on_ambiguity(bool)`

**Pass / interpretation**

- [ ] `source_class` is a **measured** property derived from channel evidence per the deterministic table; ambiguity degrades conservatively; the manifest path consumes it unchanged.

**Failure modes**

- [ ] Any path where ambiguous/spoofed evidence yields a *higher* class → the policy table is unsafe; conservative-default must hold.

## P4-5B — Build B: containerized gRPC/mTLS transport (highest systems weight)

**What to build**

- [ ] `p4/build_b/` — verifier and registry as **separate containers/runtimes**; gRPC over **mTLS**; real cross-org hops replacing the recursive in-process method calls.

**Procedure**

1. [ ] Stand up verifier + registry as separate containers; mutual-TLS between runtimes.
2. [ ] Run a multi-hop, cross-org chain over real transport; confirm manifests verify end-to-end across runtimes.
3. [ ] Re-run a representative slice of A.1/D.2/D.3 over the real transport to confirm the security/locality results hold off the single-process path.
4. [ ] Measure transport overhead (added latency per hop) separately from sensor overhead (G.1-style).

**Variants / ways to test**

- [ ] Hop count 1/2/4/8 across real containers.
- [ ] mTLS failure / cert-mismatch → confirm the hop is rejected (transport-layer integrity).
- [ ] Cross-container clock skew / retry → confirm manifest verification is robust.
- [ ] Transport overhead vs the Phase-3 single-process baseline.

**Data to record**
`hops, transport, mtls_ok(bool), manifest_verifies_e2e(bool), added_latency_per_hop_ms, asr_slice, locality_slice`

**Pass / interpretation**

- [ ] Multi-hop cross-org chains verify end-to-end over real gRPC/mTLS across separate runtimes; the security/locality results reproduce off the single-process path; transport overhead is measured and modest.
- [ ] The honesty framing flips: "cryptographic multi-runtime semantics, single-process execution" → **demonstrated multi-runtime execution**.

**Failure modes**

- [ ] Results only reproduce in-process, not over real transport → the systems claim is not yet substantiated; do not submit the systems framing until they do.
- [ ] mTLS misconfig accepted a bad hop → transport integrity is broken; fix before any cross-org claim.

---

# WORKSTREAM 6 — FINAL AUDIT GATE

## P4-6 — Exit-check sweep (the nine Definition-of-Done conditions)

**What to build**

- [ ] `p4/audit/exit_checks.py` — a single script that asserts each of the nine Phase-4 exit checks and prints PASS/FAIL per item.

**Procedure**

1. [ ] Run the full sweep; every check must be green before "submission-ready" is claimed.

**The nine checks (mirror of Phase-4 Part IV):**

1. [ ] No calibration feature derives from the label's defining quantity; three numbers (u+s / faith-fixed / full-g) reported; faith-adds-value answered; no calibration adjective pre-rerun (P4-1A).
2. [ ] D.3 locality stated as by-construction invariant AND confirmed by independent recomputation; tautology removed from PASS gate (P4-1B).
3. [ ] Every published table cell recomputes from its CSV (P4-1C).
4. [ ] Every headline sentence states only what its data supports — "closes"→"reduces", dominance scoped to content-blind baseline, "g tracks influence"→"g and v separate attack/benign", A.1 scoped to declared-benign (P4-2.x, §III).
5. [ ] B.1/B.2/C.2/D.2/F.3 carry a Qwen2.5 (7B+14B) confirmation via the white-box wrapper, with precision/layer/token/quantization spec reported; cross-architecture deferred to Mistral/DeepSeek ablations (P4-3.x).
6. [ ] Every CI reflects the true unit of independence; per-experiment unit-of-analysis statement present (P4-4).
7. [ ] Systems claim demonstrated on real transport across separate runtimes with channel-derived source classes (P4-5A/5B).
8. [ ] The paper contains an explicit internal-audit subsection reporting the findings and fixes.
9. [ ] The usage probe's unique value is shown with a CSV-backed sensor-attribution table; probe framed for source-absent/synthesis/prose, not oversold (P4-2B).

**Pass / interpretation**

- [ ] All nine green → the contribution is a system-led result whose central guarantee is by-construction, whose ML is a degrade-only sensor that can never weaken security, and whose every claim survives a reviewer re-running the code.

**Failure modes**

- [ ] Any check red → not submission-ready; the gate is all-or-nothing by design.

---

# CROSS-CUTTING TASKS (apply to every experiment)

- [ ] **Serving rule:** B.1/B.2 use the white-box `transformers` wrapper (`output_hidden_states=True`); never a vLLM/Ollama endpoint for activations. vLLM only for text generation.
- [ ] **bf16 default, quantization is an ablation:** at 7B/14B on 96 GB, bf16 fits with room for activation capture; any quantized run is an explicit, labeled ablation, and a probe trained on quantized states characterizes that runtime, not the bf16 model.
- [ ] **No calibration adjective until P4-1A lands:** "calibrated / non-arbitrary / domain-generalizing" are forbidden until the leakage-free rerun exists.
- [ ] **Reduce, never close:** the laundering claim is always "reduce/bound/localize/down-weight," never "close"; the F.1/F.2/F.3 residuals are named.
- [ ] **Dominance scoped:** only over the content-blind baseline, never over single-sensor competitors.
- [ ] **Report deltas vs Phase-3** for every scaled experiment (B.1/B.2/C.2/D.2/F.3) — the point is the change at scale, not just the new number.
- [ ] **Clamp invariant everywhere:** every warrant write asserts `g ≤ 1` and `w ≤ w_decl`; a violation is a hard failure.
- [ ] **Unit-of-analysis:** every CI computed at the true independent unit; construction-oracle metrics never get human-style CIs.
- [ ] **Honesty ledger current:** keep `docs/THREATS_TO_VALIDITY_P4.md` updated as each experiment runs — Qwen-2.5-only scope, probe runtime-access TCB, plausible-near-miss residual, adaptive residual, transport overhead.
- [ ] **Qwen-2.5-only this phase:** Mistral/DeepSeek are deferred; do not silently introduce them, and do not claim cross-architecture generality until that ablation pass runs.

---

# WHAT EACH WORKSTREAM PROVES (one-line map)

- **WS1** — the three findings that touch *correctness* are fixed: no calibration leakage, real (non-tautological) locality test, every table cell reproduces.
- **WS2 / 2B** — every over-narrated claim is pulled back to what the data supports; the usage probe's unique value is demonstrated, not assumed.
- **WS3** — the load-bearing learned sensors hold (or their shifts are honestly reported) **at modern Qwen2.5 scale**, closing the threat-model/eval mismatch.
- **WS4** — every statistical claim reflects the true unit of independence.
- **WS5** — the systems claim is **demonstrated** on real cross-org multi-runtime transport, not simulated.
- **WS6** — all nine exit checks pass; the result is submission-ready.

Backbone correctness = WS1. Honesty = WS2/2B/4. Scale credibility = WS3. Systems credibility = WS5. Sign-off = WS6.

---

### Notes / caveats for the team

- **Order is load-bearing:** WS1 (correctness) before WS3 (scale) — a scale run on leaked code wastes the run.
- **Qwen2.5-7B and 14B only** this phase, bf16 default; Mistral/DeepSeek cross-architecture is a *later* ablation pass, not this one.
- **B.1/B.2 must use the white-box wrapper** — the single most common way this suite goes wrong is running the probe against a served endpoint with no hidden states.
- **Builds A and B are the only multi-week items** and are submission blockers; everything in WS1/WS2/WS4 is a small, bounded fix.
- **Nothing here adds a new mechanism.** If a task starts to feel like new scope, it is future work, not Phase-4 finalization.
- Verify the 2026 primitive arXiv IDs and the SteerFuse/DataDignity attribution before submission (carried from Phase 3).
