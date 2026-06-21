# CAPM Phase 3 — Experiments Playbook (`experiments3.md`)

### Realized-Provenance Attestation: the implementation-level to-do list

**How to read this file.** This is the executable counterpart to `CAPM_Phase3_Realized_Provenance.md`, built in the same format as `PHASE2_PLAYBOOK.md`. Every experiment uses the same six-part structure so it reads as an actionable checklist:

> **Sync note (tracks Phase 3 r1).** This playbook is aligned to the reviewer-integrated Phase 3 design doc. Changes carried over: STEERFUSE branding removed (support = calibrated embedding/activation similarity); CVE examples fixed (9.1→Critical is a *valid abstraction*, not a contradiction — genuine contradictions are 9.1→low, Win10/11→Win7-only, KB123→no-patch); `parent_claim_id` is now *claimed-not-trusted* (verifier re-derives `verified_parent_id`); "external sensors" → *auditable / verifier-side* with placement recorded; and two new experiments — **P3-E.3** (forge-sensor / self-serving-parent rejection) and **P3-E.4** (black-box no-probe fallback) — added to match §7a. The utility framing is stated as *localized degradation* vs document-level CAPM, never "raising a claim above its declared warrant."

- **What to build** — exact files / functions / modules to create.
- **Procedure** — the numbered steps to run.
- **Variants / ways to test** — every dimension to sweep (this is where the depth lives).
- **Data to record** — the exact CSV columns.
- **Pass / interpretation** — the criterion and what the result *means*.
- **Failure modes** — what would invalidate the result.

**The Phase 3 discipline (read before coding).** Phase 1 earned ASR 0.00; Phase 2's honesty was letting B3 produce a *non-zero* ASR at a cost. Phase 3's equivalent discipline is this: **the headline result is a Pareto-frontier win, not a new ASR-0.** If you find E3.2 collapsing into "Phase 3 blocks everything," you have slipped back into over-blocking — the very failure mode you are refuting. The win is *more surviving good claims at equal security*, and the residual under adaptive attack (E5.3) is **expected to be > 0** and that is correct, consistent with CAPM's managed-residual posture.

**Naming.** Phase 3 experiments are `P3-Gx.y` (group, experiment). Groups: **A** gap-existence, **B** probe/usage, **C** faithfulness, **D** calibration+utility (the centerpiece), **E** safety/monotonicity, **F** influence+adaptive, **G** cost.

**Two framings kept separate (same rule as Phase 2).** "Phase 3 recovers utility (benign-retention up)" and "Phase 3 holds the line on security (ASR flat or better)" are *different axes* and must be reported in separate columns of the same frontier table — never collapsed into one score.

---

# SUGGESTED EXECUTION ORDER

1. [ ] **P3-A** (gap existence) + **P3-G build of the structured testbed** — prove the gap is real and the effect taxonomy is observable, no ML. Everything hangs on the gap being measurable; do it first.
2. [ ] **P3-B** (probe transfer + usage separation) — stand up the anchor sensor; the rest depends on it working on your relay models.
3. [ ] **P3-C** (support + NLI) — add the faithfulness sensors; now all four effects are measured.
4. [ ] **P3-E** (safety + monotonicity + trust model) — the theorems plus the sensor-forgery / self-serving-parent rejection (E.3) and the black-box fallback (E.4). Low-compute, machine-checked; lock them before the headline experiment so the guarantee is provably intact.
5. [ ] **P3-D** (calibration + the security–utility frontier) — the empirical heart and the paper's centerpiece. Highest effort.
6. [ ] **P3-F** (influence validation + adaptive attack) — realism and durability; the residual is born here.
7. [ ] **P3-G** (cost) — measured last, on the assembled system.

Backbone = 1–4. Centerpiece figure = 5. Borderline→clear-accept = 6–7.

---

# SHARED INFRASTRUCTURE (build once, before any experiment)

- [ ] **`p3/claims/extract.py`** — claim extractor. For structured input (CVE/API/DB record), each field → one `Claim{claim_id, key, value, source_record_id}`.
- [ ] **`p3/claims/match.py`** — claim matcher / **lineage re-deriver**: locate each source claim in a relay's output via exact / numeric-tolerant / entity match; return per-output-claim `effect ∈ {survived, dropped, distorted, added}` plus a **`verified_parent_id`** the verifier derives itself. The relay's `claimed_parent_id` is only a hint to seed the search and is **never** trusted (see §5 of the design doc).
- [ ] **`p3/sensors/probe.py`** — usage sensor: load AttriWiki-style logistic-regression probe over the relay model's normalized final-layer hidden vector `h_L`; return `u(c') ∈ [0,1]` = P(context-driven). **Runtime-internal** — requires the access described in §7a (open-weight runtime / attested sensor service / re-executing verifier); absent for black-box relays.
- [ ] **`p3/sensors/support.py`** — support sensor: **calibrated embedding/activation similarity** between source-claim and output-claim representations; return `s(c') ∈ [0,1]`. Default = sentence-embedding cosine, fully verifier-side from text; optional activation-space variant where model access exists (not load-bearing, do **not** brand it "STEERFUSE").
- [ ] **`p3/sensors/nli.py`** — faithfulness sensor: small NLI model; return `faith(c') ∈ {entail→1, neutral→0.5, contradict→0}`. **Fully verifier-side** (source + output text only).
- [ ] **`p3/sensors/schema_numeric_rule.py`** — schema-aware numeric/band comparator: for known structured fields (e.g. CVSS score↔severity band), decide entail-vs-contradict by the schema, so digit→word abstraction (9.1→"Critical") scores `entail` and a genuine flip (9.1→"low") scores `contradict`. NLI handles prose; this handles structured fields.
- [ ] **`p3/warrant/realized.py`** — compute `g(c') = u^α · s^β · faith^γ`, `w_real = g · w_decl`, and `w = min(w_decl, w_real)`. Hard-assert `g ≤ 1` and `w ≤ w_decl` before returning.
- [ ] **`p3/manifest/field.py`** — sign and append the per-claim realized-provenance field `⟨claim_id, claimed_parent_id (hint), verified_parent_id, u, s, faith, effect, sensor_versions, sensor_placement, hop_signature⟩`; the verifier re-derives lineage, recomputes `g`, takes the `min`, **rejects any value whose `sensor_placement` is untrusted** (e.g. a relay-computed `u`), and emits per-claim verdicts.
- [ ] **`p3/oracle/neurotaint_offline.py`** — offline counterfactual influence `v(c')` (evaluation only).
- [ ] **`p3/data/advisories/`** — the structured corpus: real CVE advisories (ties to the design doc's CISA-KEV / dataset map) + a transformation generator producing faithful / lossy / contradicted / fabricated / source-mixed variants with ground-truth per-claim labels. **Include a valid-abstraction control set** (9.1→"Critical", "KB123 released"→"a patch exists") that must NOT be flagged as contradiction.
- [ ] **`docs/THREATS_TO_VALIDITY_P3.md`** — the honesty ledger: probe-transfer assumption, probe runtime-access TCB, NLI error rate + numeric blind spot, support false-positive under distractors, structured-only scope, human-label sample size, attention-faithfulness caveat for A-Trust. Pre-writes the limitations section.

---

# GROUP A — GAP EXISTENCE (validates Step 0)

## P3-A.1 — Does reasoning-layer laundering occur under valid manifests?

**What to build**
- [ ] `p3/exp/a1_laundering_under_valid_manifest.py` driving relay transformations through baseline CAPM (document-level warrant, no sensors).
- [ ] Transformation set: faithful summary, lossy summary, contradiction-injected summary, memory-substituted rewrite.

**Procedure**
1. [ ] For each advisory, run each transformation through a relay that signs a valid manifest.
2. [ ] Record manifest validity and the document-level warrant baseline CAPM assigns.
3. [ ] Independently (ground truth) record whether the content was actually laundered (dropped/contradicted/fabricated).

**Variants / ways to test**
- [ ] Transformation type (4 above).
- [ ] Chain length: 1, 2, 3, 5 hops.
- [ ] Source class: STRONG-API, MODERATE-DB, WEAK-webpage (does the gap appear at every class?).
- [ ] Compression ratio: light / heavy summary.

**Data to record**
`advisory_id, transform_type, hops, source_class, manifest_valid(bool), capm_doc_warrant, laundered_groundtruth(bool), accepted_by_capm(bool)`

**Pass / interpretation**
- [ ] A measurable fraction of laundered outputs pass baseline CAPM with high warrant. **This fraction is the reason Phase 3 exists** — report it as a headline number.

**Failure modes**
- [ ] If the fraction is ~0, either the transformations are too obvious (strengthen them) or CAPM's document degrade already catches them (in which case re-scope to the locality argument E3.3, where document-CAPM still over-quarantines).

## P3-A.2 — Is the effect taxonomy observable without ML?

**What to build**
- [ ] Hand-label harness; rule-based effect tagger from `match.py`.

**Procedure**
1. [ ] Two annotators label each output claim survived/dropped/distorted/added on a sample.
2. [ ] Run the rule-based tagger; compare.

**Variants / ways to test**
- [ ] Numeric fields (severity scores) vs. categorical (vendor) vs. identifier (KB number).
- [ ] With/without numeric tolerance in the matcher.

**Data to record**
`claim_id, field_type, human_label, tagger_label, agree(bool)`

**Pass / interpretation**
- [ ] Cohen's κ ≥ 0.8 between tagger and humans on structured data → the effects are crisp, not fuzzy, before any ML enters.

**Failure modes**
- [ ] Low κ on numeric fields usually means the tolerance threshold is wrong; sweep it. Document the chosen tolerance in the validity ledger.

---

# GROUP B — PROBE AS USAGE SENSOR (validates Step 1)

## P3-B.1 — Does the probe transfer to our relay models?

**What to build**
- [ ] `p3/sensors/probe_train.py` — retrain the AttriWiki probe per relay model if the released probe doesn't transfer; enforce **title-disjoint** train/test splits (no article in both).
- [ ] Text-only shortcut controls: balanced bag-of-words LR and a DeBERTa-embedding LR (the paper's own controls).

**Procedure**
1. [ ] Try the released probe first; evaluate macro-F1 on held-out splits.
2. [ ] If weak, regenerate AttriWiki labels (self-supervised — free) on your model and retrain.
3. [ ] Train the text-only controls on the same passages.

**Variants / ways to test**
- [ ] Each relay model you deploy (run the probe per model; never assume cross-model transfer).
- [ ] Probe layer: final layer vs. a swept middle layer (report best, note the layer).
- [ ] Class-imbalance handling: balanced loss (AttriWiki is ~3.2:1 parametric:contextual).
- [ ] Out-of-domain check: SQuAD / WebQuestions transfer without retraining.

**Data to record**
`model, probe_type, layer, macro_f1, text_only_bow_f1, text_only_deberta_f1, ood_f1`

**Pass / interpretation**
- [ ] Probe macro-F1 high (target ≳ 0.9 in-domain) **and** a clear gap over both text-only controls → the probe reads representations, not surface lexical cues. The gap is the load-bearing result; without it a reviewer says "it's just keyword matching."

**Failure modes**
- [ ] Probe ≈ text-only control → the signal is lexical, not representational; this is a reportable negative, and you fall back to support+NLI as the primary sensors with usage demoted to auxiliary.
- [ ] Probe doesn't transfer cross-model → retrain per model and state it (it's cheap; the pipeline is self-supervised).

## P3-B.2 — Does usage separate faithful from memory-substituted claims?

**What to build**
- [ ] `p3/exp/b2_usage_separation.py` over the advisory set with known fabrications.

**Procedure**
1. [ ] For each output claim, get `u(c')`.
2. [ ] Split into genuinely-sourced vs. fabricated (memory-substituted) by ground truth.
3. [ ] Compare `u` distributions.

**Variants / ways to test**
- [ ] Fabrication subtlety: blatant (invented vendor) vs. plausible (wrong-but-realistic severity).
- [ ] Mixed claims (partly sourced, partly invented).
- [ ] Token-span aggregation: mean vs. min `u` over a claim's tokens.

**Data to record**
`claim_id, u_score, sourced_or_fabricated, fabrication_subtlety, aggregation`

**Pass / interpretation**
- [ ] AUC of `u` separating fabricated vs. sourced ≳ 0.85 → usage is actionable as the fabrication detector.

**Failure modes**
- [ ] Plausible fabrications evade `u` → expected; this is exactly where support+NLI (Group C) must cover, and the multi-sensor product `g` is justified.

---

# GROUP C — FAITHFULNESS SENSORS (validates Step 2)

## P3-C.1 — Does support detect evidence loss?

**What to build**
- [ ] `p3/exp/c1_support_evidence_loss.py`; construct claims where backing evidence is selectively removed but the assertion survives.

**Procedure**
1. [ ] Generate "claim survives, evidence stripped" cases.
2. [ ] Measure `s(c')`; compare against evidence-intact cases.

**Variants / ways to test**
- [ ] Representation space: sentence-embedding cosine (verifier-side default) vs. activation-space similarity (where model access exists).
- [ ] Partial vs. full evidence removal.
- [ ] Distractor source present (a topically-similar but irrelevant source) to test false-support.

**Data to record**
`claim_id, support_score, evidence_intact_or_stripped, space, distractor_present, detected(bool)`

**Pass / interpretation**
- [ ] AUC of `s` detecting evidence-loss ≳ 0.8 → support catches the "claim survives, proof gone" case CAPM's structural penalty cannot.

**Failure modes**
- [ ] Distractor sources inflate `s` (false support) → report it; this is a known support-attribution weakness and motivates keeping `s` under the `min`, never as a sole gate.

## P3-C.2 — Does NLI catch genuine contradictions WITHOUT flagging valid abstraction?

**What to build**
- [ ] `p3/exp/c2_nli_contradiction.py`; inject **genuine contradictions** (severity 9.1→"low"; affected Windows 10/11→"only Windows 7"; patch KB123→"no patch available"; vendor swaps; patched→unpatched) **and** a **valid-abstraction control set** that must score `entail` (9.1→"Critical", since CVSS v3.1 maps 9.0–10.0→Critical; "KB123 released"→"a patch exists").
- [ ] Wire in `p3/sensors/schema_numeric_rule.py` so structured field comparisons (score↔band) are judged by schema, not left to prose-NLI.

**Procedure**
1. [ ] Generate the genuine-contradiction set and the valid-abstraction control set with ground-truth labels.
2. [ ] Run NLI (+ the schema numeric rule for structured fields) on both; record entail/neutral/contradict.

**Variants / ways to test**
- [ ] Contradiction type: numeric (severity flip across bands), categorical (vendor), boolean (patched/unpatched), version-scope (10/11→7).
- [ ] Numeric framing: digit→word genuine flip ("9.1"→"low") vs. digit→word valid abstraction ("9.1"→"Critical") vs. digit→digit ("9.1"→"2.0").
- [ ] NLI model size (small vs. mid) — cost/accuracy trade.
- [ ] With vs. without the schema numeric rule (show the rule is what fixes the digit↔word band cases).

**Data to record**
`claim_id, case_type(genuine|abstraction), contradiction_type, framing, nli_label, schema_rule_label, final_label, groundtruth, correct(bool)`

**Pass / interpretation**
- [ ] High contradiction recall on the genuine set (target ≳ 0.9) **and low false-positive rate on the abstraction control** (valid abstraction must score `entail`) → the system catches wrong information without over-blocking faithful abstraction. This is the reviewer-caught correctness point made into a test.

**Failure modes**
- [ ] Digit→word severity cases evade prose-NLI (it doesn't know 9.1 ↔ "Critical"/"low" band semantics) → the schema numeric rule must own these; NLI handles prose, the rule handles structured fields. Document the split.
- [ ] The system flags 9.1→"Critical" as a contradiction → that is the over-blocking error; the schema rule must classify within-band abstraction as `entail`.

---

# GROUP D — CALIBRATION & THE SECURITY–UTILITY FRONTIER (validates Steps 2–3; THE CENTERPIECE)

## P3-D.1 — Do the sensors predict human per-claim judgment?

**What to build**
- [ ] `p3/exp/d1_human_calibration.py`; human-labeling protocol; weight-fitting for `α, β, γ`.
- [ ] Functional-form bake-off: product `u^α·s^β·faith^γ` vs. weighted geometric mean vs. `min`.

**Procedure**
1. [ ] Humans label each transformed claim: survived/dropped/distorted/added **and** "would you act on this?" (the trust label).
2. [ ] Fit `α,β,γ` (and pick the functional form) to the human trust labels on a training split.
3. [ ] Evaluate on a held-out split.

**Variants / ways to test**
- [ ] Functional form (3 above) — **the form is decided here empirically, not assumed.**
- [ ] Annotator count (≥ 3) and inter-annotator agreement.
- [ ] Claim type weighting on/off (schema-declared importance: severity/patch load-bearing vs. references).
- [ ] Domain holdout: fit on one advisory vendor, test on another.

**Data to record**
`claim_id, u, s, faith, g_pred, human_trust_label, form, alpha, beta, gamma, fold, agreement_kappa`

**Pass / interpretation**
- [ ] `g(c')` agrees with human trust on held-out claims (high correlation / calibration), and the chosen form generalizes across domain holdout → the weights are calibrated, not arbitrary.

**Failure modes**
- [ ] Overfit weights (great in-fold, poor held-out) → regularize, reduce free parameters, prefer the simpler `min` form.
- [ ] Low inter-annotator agreement → the "would you act" question is underspecified; tighten the rubric and re-collect.

## P3-D.2 — The security–utility frontier win (THE LOAD-BEARING RESULT)

**What to build**
- [ ] `p3/exp/d2_frontier.py` running attack + benign transformations through (a) baseline CAPM, (b) CAPM+Phase 3, (c) the strongest Build-C competitor from the design doc.
- [ ] Frontier plotter (ASR vs. benign-retention).

**Procedure**
1. [ ] Run the full transformation set (laundered + benign) through all three systems.
2. [ ] Sweep the strictness knob (warrant floor / penalty schedule) for each to trace its frontier.
3. [ ] For every operating point record ASR and benign-claim retention.
4. [ ] **Report the two axes against their correct baselines** (the r1 framing): *security* (ASR) vs. **per-claim** CAPM — Phase 3 must not be worse; *utility* (benign-retention) vs. **document-level** CAPM — Phase 3's gain comes from localizing degradation, since document-level handling discards intact claims when one claim degrades. Phase 3 never raises any individual claim above its declared warrant; the win is granularity, not inflation.

**Variants / ways to test**
- [ ] Attack family: information-loss, contradiction, fabrication, evidence-loss, source-mixing, truths-only (preview of F).
- [ ] Benign family: faithful summary, faithful paraphrase, faithful composition.
- [ ] Chain length: 1, 2, 4, 8.
- [ ] Strictness sweep across the full knob range (this is what makes it a *frontier*, not a point).
- [ ] Two reported framings, separate columns: utility axis (vs document-level CAPM) and security axis (vs per-claim CAPM).

**Data to record**
`system, operating_point, attack_family, benign_family, hops, ASR, benign_claim_retention, down_rank_rate, hard_block_rate, useful_answer_retention`

**Pass / interpretation**
- [ ] CAPM+Phase 3 **wins the frontier by localization**: equal-or-lower ASR vs. per-claim CAPM, and higher benign-retention vs. document-level CAPM (it keeps intact claims the document-level baseline throws out), vs. both baselines and the best Build-C. **This is the result that refutes "CAPM is secure only because it distrusts useful behavior."** Note explicitly: no individual claim is raised above its declared warrant — the gain is granularity.

**Failure modes**
- [ ] Phase 3 = "blocks everything" (ASR 0 but benign-retention collapses) → you've over-blocked; you are reproducing the failure you set out to refute. The product `g` weights or the `min` clamp are too aggressive; re-calibrate from D.1.
- [ ] No dominance (frontiers cross) → report honestly where Phase 3 wins and where it doesn't; a partial frontier win is still a contribution if the win region is the realistic operating range.

## P3-D.3 — Does damage stay local across hops?

**What to build**
- [ ] `p3/exp/d3_locality.py`; multi-hop chains corrupting exactly one claim at hop k.

**Procedure**
1. [ ] Build chains where one claim is corrupted at hop k; all others pass faithfully.
2. [ ] Track every claim's warrant downstream to the final hop.

**Variants / ways to test**
- [ ] Corruption hop k ∈ {1, middle, last}.
- [ ] Number of corrupted claims: 1 vs. 2 of N.
- [ ] Document size: 4-claim advisory vs. larger record.

**Data to record**
`chain_id, total_claims, corrupted_claims, corruption_hop, final_hop, unaffected_claims_above_threshold, capm_doc_collapsed(bool)`

**Pass / interpretation**
- [ ] Under Phase 3, unaffected claims stay usable at the final hop while baseline document-CAPM collapses all of them → locality demonstrated, the core claim-level argument.

**Failure modes**
- [ ] Lineage threading bug causes cross-claim contamination → unit-test `verified_parent_id` propagation; a single claim's degrade must not touch siblings.

---

# GROUP E — SAFETY & MONOTONICITY (validates the theorems; do BEFORE D)

## P3-E.1 — Can any sensor inflate warrant above baseline?

**What to build**
- [ ] `p3/exp/e1_clamp_adversary.py`; adversarially force `u, s, faith` to their max on laundered claims.

**Procedure**
1. [ ] For every laundered claim, override sensor outputs to 1.0 (simulating a fully fooled or compromised sensor).
2. [ ] Compute final warrant; assert `w ≤ w_decl` holds.

**Variants / ways to test**
- [ ] Each sensor maxed individually and all together.
- [ ] Negative weights / malformed sensor outputs (robustness of the clamp to bad input).
- [ ] Sensor returns NaN / out-of-range → must clamp to the conservative baseline, never propagate.

**Data to record**
`claim_id, forced_sensor, w_decl, w_real, w_final, exceeds_decl(bool — must be False)`

**Pass / interpretation**
- [ ] `exceeds_decl` is **False for every claim, by construction** (the `min`). This is the Graded-degrade safety theorem, empirically confirmed: a fooled sensor degrades to baseline CAPM, never above.

**Failure modes**
- [ ] Any True → the clamp is implemented wrong (e.g. a sensor multiplied before the min, or `g > 1` possible); fix immediately — this is the whole security argument.

## P3-E.2 — Is per-claim warrant monotone non-increasing?

**What to build**
- [ ] Extend the Phase 2 machine-checked monotonicity lemma to the per-claim case in the verifier.

**Procedure**
1. [ ] Exhaustively/symbolically check that along every lineage thread `w_k(c') ≤ w_{k-1}(verified_parent(c'))` (using the verifier-derived parent, not the agent's hint).

**Variants / ways to test**
- [ ] All warrant encodings (lattice / continuous / learned) — same as Phase 2's encoding-invariance.
- [ ] Composition (min-bounded multi-parent claims).
- [ ] Non-monotone control: deliberately break the clamp and confirm the checker catches the leak.

**Data to record**
`thread_id, encoding, monotone_holds(bool), control_leaks(bool)`

**Pass / interpretation**
- [ ] Monotonicity holds for all real configs; the non-monotone control leaks (proving the checker has teeth). Phase 3 preserves CAPM's headline invariant.

**Failure modes**
- [ ] A composition case where a high-warrant sibling lifts a low one → confirm min-bounding is applied per-claim, not per-document.

## P3-E.3 — Can a malicious relay forge a sensor value or supply a self-serving parent? *(validates §7a and §5)*

**What to build**
- [ ] `p3/exp/e3_forgery_and_lineage.py`; a malicious relay that (a) emits inflated `u/s/faith` tagged with an untrusted `sensor_placement`, and (b) points a fabricated output claim at a high-support source claim via `claimed_parent_id`.

**Procedure**
1. [ ] Relay submits forged sensor values with `sensor_placement = relay`; confirm the verifier discards them and recomputes the verifier-side sensors (NLI + support) itself.
2. [ ] Relay submits a self-serving `claimed_parent_id`; confirm the verifier's matcher derives a different (or null) `verified_parent_id` and degrades the claim on mismatch.

**Variants / ways to test**
- [ ] Forge each sensor individually and all together.
- [ ] `sensor_placement` values: relay (untrusted) vs. attested-service vs. re-executing-verifier (trusted) — only trusted placements are honored.
- [ ] Self-serving parent: point fabricated claim at the highest-support, the highest-warrant, and a random source claim.
- [ ] Ambiguous lineage (two plausible parents) → confirm degrade-on-ambiguity.

**Data to record**
`case_id, forged_sensor, sensor_placement, placement_honored(bool), claimed_parent, verified_parent, parent_corrected(bool), w_final, exceeds_baseline(bool — must be False)`

**Pass / interpretation**
- [ ] Forged values from untrusted placements are rejected at ~100%; self-serving parents are corrected or the claim degrades; final warrant never exceeds baseline → the signed sensor field and the parent pointer are **claimed, not trusted**, closing the re-self-attestation hole.

**Failure modes**
- [ ] Any honored relay-placed sensor value, or any agent-supplied parent driving warrant unverified → the trust model is mis-implemented; this is a hard-fail (it would re-introduce self-reporting).

## P3-E.4 — Does the §7a fallback hold for black-box (no hidden-state) relays?

**What to build**
- [ ] `p3/exp/e4_blackbox_fallback.py`; run the full suite on the black-box API model where the usage probe `u` is unavailable.

**Procedure**
1. [ ] Run benign + attack transformations through the black-box relay.
2. [ ] Confirm `u` is absent, the verdict is computed from support + NLI alone, and the `min`-clamp guarantee still holds.

**Variants / ways to test**
- [ ] With probe (open-weight relay) vs. without probe (black-box) on the same transformations.
- [ ] Each attack class — which ones become harder to catch without `u` (fabrication is the expected loss).

**Data to record**
`relay_type(open|blackbox), probe_available(bool), attack_class, caught(bool), benign_retention, w_exceeds_baseline(bool — must be False)`

**Pass / interpretation**
- [ ] Without the probe, security is unchanged (clamp holds, no warrant inflation) and only *utility* drops (less ability to separate faithful from memory-substituted) → graceful degradation with deployment access, exactly the §7a claim. Quantify the utility cost of losing `u`.

**Failure modes**
- [ ] Black-box path raises any warrant above baseline, or silently trusts the relay for `u` → the fallback is unsafe; fix before claiming deployment generality.

---

# GROUP F — INFLUENCE VALIDATION & ADAPTIVE ATTACK (validates Step 4; residual born here)

## P3-F.1 — Do cheap runtime sensors track expensive counterfactual influence?

**What to build**
- [ ] `p3/oracle/neurotaint_offline.py` over the same traces; correlation harness `g` vs. `v`.

**Procedure**
1. [ ] Run NeuroTaint-style counterfactual ("would the sink/claim appear if the source were removed?") offline on each trace.
2. [ ] Correlate `g(c')` (runtime) with `v(c')` (offline influence).

**Variants / ways to test**
- [ ] Per propagation class: explicit content, implicit control, asynchronous (poisoned-memory) reuse.
- [ ] Counterfactual judge model varied (the LLM-judge is itself attackable — note its sensitivity).

**Data to record**
`claim_id, g_runtime, v_influence, propagation_class, judge_model, correlation_rho`

**Pass / interpretation**
- [ ] Meaningful correlation ρ between `g` and `v` → the cheap runtime signal tracks real counterfactual influence; pre-empts "your proxy is meaningless." Note honestly where it diverges (asynchronous reuse is where the runtime probe is blind and the offline oracle is needed).

**Failure modes**
- [ ] Low ρ on implicit-control cases → expected; the runtime sensors measure content usage, not control influence. State the boundary; this is why NeuroTaint stays the oracle, not the floor.

## P3-F.2 — Does the divergence detector catch the truths-only attack?

**What to build**
- [ ] `p3/sensors/atrust_divergence.py` (attention-feature internal-trust estimate) — **clearly caveated, off the security floor**.
- [ ] "Lying with Truths"-style generator: all sources real, false global conclusion.

**Procedure**
1. [ ] Build truths-only laundering cases (external warrant stays high).
2. [ ] Compare detection by warrant-alone vs. warrant + internal/external divergence.

**Variants / ways to test**
- [ ] Degree of coherence-manufactured confidence (mild → strong).
- [ ] With the attention-faithfulness caveat: report both raw-attention and gradient-corrected attention features, since raw attention is contested.

**Data to record**
`case_id, external_warrant, internal_trust, divergence, detected_by_warrant_alone(bool), detected_by_divergence(bool), attention_variant`

**Pass / interpretation**
- [ ] Divergence flags truths-only cases that warrant-alone misses → the auxiliary detector covers the attack CAPM structurally cannot, framed as best-effort.

**Failure modes**
- [ ] Adversarial attention keeps divergence low while laundering → this is the documented attention-faithfulness weakness; report it as a limitation, do **not** promote the detector into the guarantee.

## P3-F.3 — Adaptive adversary against the full Phase 3 stack

**What to build**
- [ ] `p3/exp/f3_adaptive.py`; attacker that knows `u, s, faith`, `g`, weights, and the `min` rule, and optimizes content to keep all sensors clean while corrupting meaning.

**Procedure**
1. [ ] Define the adaptive objective: maximize laundering subject to `u, s, faith` staying above their degrade thresholds.
2. [ ] Run; measure residual ASR; characterize which claim types survive the attack.

**Variants / ways to test**
- [ ] Attacker knowledge: black-box (no sensor access) → grey-box (knows sensors) → white-box (knows weights).
- [ ] Per sensor evaded individually vs. all simultaneously.
- [ ] Correlated evasion (one perturbation fools multiple sensors).

**Data to record**
`attack_knowledge, sensors_evaded, residual_ASR, surviving_claim_types, perturbation_cost`

**Pass / interpretation**
- [ ] **Residual ASR > 0 is expected and correct** (managed-residual posture). The result is a *characterization*: what the adaptive attacker must do, at what cost, and which claim types remain exploitable — the honest boundary of Phase 3.

**Failure modes**
- [ ] If you find yourself tuning the residual back toward 0, you've slipped into systems-demo mode (the exact Phase 2 warning). A measured "X% at cost C" is the goal.
- [ ] Adaptive attack trivially breaks everything (residual ≈ baseline) → the sensors add no security; re-examine whether the product `g` is too easy to satisfy.

---

# GROUP G — COST (validates Step 3 deployment)

## P3-G.1 — Runtime and manifest overhead

**What to build**
- [ ] `p3/exp/g1_cost.py`; instrument per-hop sensor latency, manifest size, verifier CPU.

**Procedure**
1. [ ] Measure probe forward-pass, support cosine, NLI inference latency per claim.
2. [ ] Measure added manifest bytes per claim and verifier recompute time.
3. [ ] Separate online cost (probe/support/NLI) from offline cost (NeuroTaint).

**Variants / ways to test**
- [ ] Claims per document: 4 → 50.
- [ ] Batch vs. per-claim sensor calls.
- [ ] Probe layer cached vs. recomputed.
- [ ] With/without the offline oracle (show it's not on the hot path).

**Data to record**
`claims_per_doc, probe_ms, support_ms, nli_ms, manifest_bytes_per_claim, verifier_cpu_ms, online_total_ms, offline_total_ms`

**Pass / interpretation**
- [ ] Online overhead is modest and bounded (probe = one frozen linear layer; NLI = small model; influence = offline) → Phase 3 is deployable, answering "too expensive."

**Failure modes**
- [ ] NLI dominates latency → quantize / use a smaller NLI, or restrict NLI to claims the cheaper sensors already flag (cascade), and report the cascade's cost.

---

# CROSS-CUTTING TASKS (apply to every experiment)

- [ ] **Separate-tables rule:** utility (vs document-level CAPM) and security (vs per-claim CAPM) reported in distinct columns; never averaged into one score. No claim is ever raised above its declared warrant — the utility gain is localization.
- [ ] **Claimed-not-trusted lineage:** any code path that uses a parent link uses the verifier-derived `verified_parent_id`, never the agent's `claimed_parent_id` (a hint only). Degrade on mismatch/ambiguity.
- [ ] **Sensor-placement enforcement:** the verifier honors a sensor value only if its `sensor_placement` is trusted (verifier-side / attested / re-executing). Relay-placed warrant-affecting sensors (especially `u`) are rejected.
- [ ] **Structured-first:** every experiment runs on CVE/API/DB sources first; prose (atomic-claim decomposition) is explicitly deferred and labeled future work.
- [ ] **Abstraction-is-not-contradiction:** the contradiction sensor must pass schema-valid abstraction (9.1→Critical) as `entail`; the schema numeric rule owns structured-field comparisons.
- [ ] **Clamp invariant everywhere:** any code path that writes a warrant asserts `g ≤ 1` and `w ≤ w_decl` before persisting; a violation is a hard failure, not a warning.
- [ ] **`g` form is data-decided:** the functional form of `g(c')` is fixed by P3-D.1, not assumed elsewhere; until D.1 runs, use the conservative `min`.
- [ ] **Honesty ledger:** keep `docs/THREATS_TO_VALIDITY_P3.md` current — probe transfer, probe runtime-access TCB, NLI numeric blind spot, support false-positive under distractors, attention-faithfulness caveat, structured-only scope, human-label N.
- [ ] **Preprint caution:** verify all 2026 primitive arXiv IDs, released artifacts, and reported numbers before any of them appears in submission text (probe = AttriWiki 2602.22787; influence = NeuroTaint/"Ghost in the Agent" 2604.23374; support = generic, *not* "STEERFUSE" — SteerFuse is DataDignity 2605.05687's secondary method).

---

# WHAT EACH GROUP PROVES (one-line map)

- **A** — the gap is real and the effects are observable (no ML).
- **B** — usage is representational (not lexical) and separates fabrication.
- **C** — support catches evidence loss; NLI catches genuine contradiction without flagging valid abstraction.
- **D** — sensors match humans; **claim-level handling beats document-level CAPM on the frontier by localizing degradation** (no claim raised above its declared warrant); damage stays local.
- **E** — no sensor can inflate warrant; forged sensor values and self-serving parents are rejected; the black-box fallback is safe; monotonicity preserved (the theorems + trust model).
- **F** — runtime signals track real influence; the truths-only attack is covered; the adaptive residual is honest and bounded.
- **G** — the whole thing deploys at modest, measured cost.

Backbone = A–E. Centerpiece = D.2. Borderline→clear-accept = F–G.
