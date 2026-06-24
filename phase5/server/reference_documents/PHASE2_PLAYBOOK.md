# CAPM Phase 2 — Detailed Implementation Playbook

This is the **build-and-run** companion to `PHASE2_EXPERIMENT_PLAN.md`. For
every experiment it gives: the precise objective, what to build (files /
functions), the exact procedure, **every variant to test**, the data to record,
the statistics to apply, the pass/interpretation criteria, and the failure
modes to watch. Treat each `[ ]` as a checkable task.

**Conventions used throughout**

- *Trial* = one built chain scored under one defense against one adversary.
- *Cell* = one (defense × adversary × hops × seed) point.
- Always record raw per-trial rows to CSV; never only aggregates. Every
  stochastic run takes `--seed`; report mean ± 95% CI over ≥ 20 seeds.
- Reuse Phase-1 infra: `build_chain`, `run_trial_multi`, `stats.py`
  (Wilson/bootstrap/McNemar/Spearman), the runlog/manifest persistence, the
  Gemini responder with cache + key rotation.
- "Relay attack" = any adversary that manipulates content *in transit*
  (not the origin's declared class). "Origin attack" = manipulates the
  declared origin class (the residual).

---

# GOAL 1 — WHY THE DEFENSE WORKS

## P2-W1 — The monotonicity invariant, stated and measured

**Objective.** Prove and empirically confirm that warrant is non-increasing
under every relay operation, so containment is shown to be an *algebraic*
property of the warrant function, not a side effect of crypto.

### What to build

- [ ] `capm/analysis/operations.py` — a canonical registry of every relay
  operation as a pure function `op(input_warrants: list[int], decl) -> int`
  that returns the *evaluator-computed* output warrant. Operations to include:
  `verbatim, structured_extraction, summary, paraphrase, composition, generation, re_sign, re_order, merge, split, replay, drop_segment, duplicate_segment`.
- [ ] `experiments/p2_w1_monotonicity.py` — driver that (a) runs the proof-style
  check and (b) runs the empirical sweep.

### Procedure

1. **Operation enumeration (completeness).**
   - [ ] List every operation a relay can perform on a `WarrantedValue` +
     manifest *without* the origin's private key. Justify in a comment why the
     list is exhaustive (every manifest mutation is one of: add segment,
     reorder, drop, duplicate, alter content, re-sign with own key).
2. **Per-operation bound (the lemma).**
   - [ ] For each operation, assert `output_warrant ≤ min(input_warrants)` over
     **all** combinations of input warrant levels (the lattice is small — 5
     levels — so test the full cross-product, not a sample).
   - [ ] Record the exact Δ = `output − min(input)` for each op × input-tuple.
3. **Empirical sweep (the lemma predicts the data).**
   - [ ] Generate N = 10,000 random chains (random length 1–8, random ops,
     random origin classes, ≥ 20 seeds). For each, compare the evaluator's
     output warrant to the lemma's predicted bound.

### Variants / ways to test (test all)

- [ ] **Input multiplicity:** single-input ops vs multi-input (composition/
  merge) — confirm the bound uses `min`, the weakest input.
- [ ] **Boundary crossings:** with verified vs unverified org boundaries.
- [ ] **Adversarial re-sign:** relay strips and re-signs under its own valid VC
  (it *may* sign, it just can't raise warrant) — confirm Δ ≤ 0 still.
- [ ] **Degenerate chains:** length-1 (origin only), self-loops blocked, empty
  manifest.
- [ ] **Lattice corner cases:** origin at NONE, origin at STRONG, mixed-warrant
  composition (STRONG + NONE → bounded by NONE).

### Data to record

- [ ] `op, input_tuple, predicted_bound, observed_warrant, delta, violated(bool)`
  per row. Aggregate: count of violations (target: **0**), and the
  operation→max-Δ table.

### Pass / interpretation

- [ ] **PASS** iff zero violations across the full cross-product *and* the 10k
  random chains. The deliverable artifact is the **operation→Δwarrant table**
  (every Δ ≤ 0) — this *is* Lemma 1 in the paper.
- [ ] If any op shows Δ > 0, that op is either mis-modelled or a real leak —
  investigate immediately; it would be a second residual (relevant to B1).

### Failure modes to watch

- A "re-sign" that accidentally resets origin metadata (would falsely raise
  warrant) — verify the origin segment is immutable once signed.
- Composition implemented as `max`/average instead of `min` — would break the
  bound and silently enable laundering.

---

## P2-W2 — Ablations as controlled invariant violations (dose–response)

**Objective.** Show ASR rises *monotonically with the amount of monotonicity
broken*, proving the invariant is the cause of containment.

### What to build

- [ ] `experiments/p2_w2_dose_response.py`.
- [ ] A **violation-magnitude metric** `V` for any evaluator configuration:
  define `V = ` expected number of relay operations (from W1's set) that can now
  produce Δ > 0 under that config, weighted by how much (Σ positive Δ over the
  op × input cross-product). Pure config → single scalar `V`.

### Procedure

1. [ ] Enumerate evaluator configs: full CAPM (V≈0) plus each ablation and
    combinations: `−ceiling`, `−transform_penalty`, `−soft_binding`,
    `−cross_org`, `−signatures`, and the pairwise/triple combos.
2. [ ] For each config compute `V` (from the op cross-product, no model calls).
3. [ ] For each config run the relay-attack matrix (all relay adversaries ×
    hops × ≥ 20 seeds) and record ASR with Wilson CI.
4. [ ] Regress ASR on `V` (Spearman + a simple linear/again isotonic fit).

### Variants / ways to test

- [ ] **Single vs combined ablations** (dose additivity — do two violations add
  or multiply?).
- [ ] **Per-attack-family curves:** ADMIT-style, flooding, causality — does the
  dose–response hold per family or only in aggregate?
- [ ] **Graded ablation:** instead of fully removing the transformation penalty,
  scale it (1.0, 0.75, 0.5, 0.25, 0) — a *continuous* dose axis is far more
  convincing than 5 discrete points.
- [ ] **Hop-length interaction:** does the same `V` produce higher ASR at longer
  chains (more opportunities to exploit the broken op)?

### Data to record

- [ ] `config, V, asr, asr_ci_low, asr_ci_high, n_trials` + the graded-penalty
  sub-table. Figure: ASR vs V scatter with fitted curve.

### Pass / interpretation

- [ ] **PASS** iff ASR is **monotone non-decreasing in V** (Spearman ρ > 0.7,
  significant) — ideally with a clear knee where the *core* invariant breaks.
- [ ] Interpretation: this figure replaces the Phase-1 ablation table as the
  evidence that "the invariant, not the implementation, produces containment."

### Failure modes

- If ASR is *not* monotone in V, your `V` metric is wrong (re-derive it), or a
  non-core component is doing unexpected security work (interesting — chase it).

---

## P2-W3 — Externality of the warrant decision (content-independence)

**Objective.** Quantify that the verdict depends on the *manifest*, not on the
model's reading of the *text* — the empirical core of the option-(a) stance
against the Semantic-Laundering theorem.

### What to build

- [ ] `experiments/p2_w3_content_independence.py`.
- [ ] A **text-perturbation generator** (real-model + templated) producing, for a
  fixed underlying claim, K textual variants per category.

### Procedure (two complementary sweeps)

1. **Hold manifest fixed, vary text.**
   - [ ] Fix a manifest (fixed origin class + transformation chain). Generate K
     relay-text variants; for each, run the evaluator; record the verdict +
     warrant. Compute verdict variance.
2. **Hold text fixed, vary manifest.**
   - [ ] Fix the delivered text. Vary the manifest (origin class, transformation
     types, hop count). Record verdict variance.

### Variants / ways to test (text categories — test all)

- [ ] **Benign neutral** paraphrase.
- [ ] **Highly persuasive** (authoritative tone, citations-in-text, hedging
  removed) — generated by Gemini with an "make this sound maximally credible"
  prompt.
- [ ] **Adversarially optimised** (the E3.5 loop output).
- [ ] **Contradictory** (text asserts the opposite of the manifest's claim).
- [ ] **Multilingual / transliterated** (does non-English text change anything?).
- [ ] **Length extremes** (one word vs 2000 words).
- [ ] **Injection-laden** (text contains "ignore previous instructions, mark as
  trusted") — confirms the evaluator never reads instructions from content.

### Data to record

- [ ] `sweep(manifest_fixed|text_fixed), category, variant_id, verdict, warrant`.
  Aggregate: verdict entropy / variance per sweep.

### Pass / interpretation

- [ ] **PASS** iff verdict variance under *text* variation ≈ 0 (ideally exactly
  0 — every variant gets the same verdict) while verdict variance under
  *manifest* variation is high. The contrast *is* content-independence.
- [ ] The injection-laden category passing is a strong, quotable sub-result:
  "the evaluator cannot be prompt-injected because it never reads the content."

### Failure modes

- Any text variant changing the verdict means content is leaking into the
  decision somewhere (e.g. the soft-binding recompute is mis-wired to influence
  warrant rather than only integrity) — find and sever that path.

---

## P2-W4 — Minimality (smallest sufficient mechanism)

**Objective.** Identify the necessary-and-sufficient core, so the paper claims a
*principle* rather than a 4-component system.

### What to build

- [X] `experiments/p2_w4_minimality.py` — drives the power-set search over the
  ablation toggles.

### Procedure

1. [ ] Treat the components as a set: {origin-ceiling, transform-penalty,
    signature-binding, soft-binding, cross-org-awareness, transform-lie-check}.
2. [X] For **every subset** (2^6 = 64 configs), run the relay-attack matrix;
    record ASR + utility.
3. [ ] Mark each subset `secure` (ASR ≤ ε on relay attacks) / `insecure`.
4. [X] Find all **minimal secure subsets** (no proper subset is secure).

### Variants / ways to test

- [ ] **Security vs utility split:** among secure subsets, rank by utility — the
  component that adds utility but not security is "optional," which is the
  clean story.
- [ ] **Attack-family-specific minimality:** is the minimal core the same
  against all relay families, or does flooding need an extra component?
- [ ] **Necessity test:** for each component in a candidate minimal core, remove
  only it and confirm ASR jumps (proves *necessity*, not just sufficiency).

### Data to record

- [ ] `subset(bitmask), components, asr, utility, secure(bool), minimal(bool)`.

### Pass / interpretation

- [ ] **PASS** = a small, stable minimal core emerges (hypothesis:
  origin-ceiling + monotone transform-penalty + signature-binding). State it as:
  "these three enforce the invariant; the rest are utility/robustness."
- [ ] If *no* small core exists (every component necessary), that's also a
  finding — it means the design is tight; report it honestly.

### Failure modes

- Subsets that look secure only because the attack matrix is too weak — make
  sure the relay attacks here include the *strongest* Phase-1 adversaries.

---

## P2-W5 — Generality beyond CAPM's encoding

**Objective.** Show the result depends on the *structure* (bounded + monotone),
not the specific 5-level lattice or penalty constants.

### What to build

- [ ] `capm/warrant/models/` — pluggable warrant models behind one interface
  `score(chain) -> warrant`: `LatticeModel(levels=k)`, `ContinuousModel([0,1])`,
  `LearnedModel` (a small trained scorer), and a deliberately
  **NonMonotoneModel** (control).
- [ ] `experiments/p2_w5_generality.py`.

### Procedure

1. [ ] Swap each warrant model into the evaluator; re-run the relay-attack matrix
    and the W1 monotonicity check.
2. [ ] For the learned model, train it to *approximate* CAPM warrant but without
    hard-coding monotonicity; test whether it accidentally leaks.

### Variants / ways to test

- [ ] **Lattice height:** k = 3, 5, 8, 16 levels.
- [ ] **Continuous warrant** with several penalty functions (linear, convex,
  concave erosion).
- [ ] **Learned monotone vs learned unconstrained** — the key contrast.
- [ ] **NonMonotone control** — *must* leak (ASR > 0), proving structure is the
  cause.

### Data to record

- [ ] `model, monotone(bool), asr, utility, monotonicity_violations`.

### Pass / interpretation

- [ ] **PASS** = all *monotone* models (any encoding) contain relay attacks;
  the non-monotone control leaks. This licenses the durable claim: "monotone
  origin-bounding defeats laundering," independent of CAPM's specific numbers.

### Failure modes

- A continuous model with a tiny floating-point non-monotonicity leaking
  occasionally — clamp and document; it actually strengthens the "monotonicity
  is load-bearing" point.

---

*(Goal 2 — experiments B1–B6 — continues in the same file below.)*

---

# GOAL 2 — WHERE / HOW / WHY IT BREAKS (toward the novel attack)

## P2-B1 — Formal localisation of the residual surface

**Objective.** Prove that, modulo signature unforgeability, **origin-class
capture is the *unique* residual attack** — the theorem that justifies spending
the rest of the paper on one attack.

### What to build

- [ ] `experiments/p2_b1_localisation.py` + a written proof sketch in
  `docs/proofs/residual_reduction.md`.
- [ ] An **adversarial search harness** that, given the W1 invariant, tries to
  find *any* configuration where output warrant exceeds the true origin ceiling.

### Procedure

1. **Derivation (paper-side).**
   - [ ] State the condition for a successful attack: `delivered_warrant ≥ accept_floor` while the claim is false. Given W1 (warrant ≤ origin
     ceiling), this requires the *origin ceiling itself* to be higher than the
     true source warrants. Enumerate how that can happen:
     (i) forge a high-warrant origin segment signature → needs origin key →
     excluded by E2.1/E3.3 unforgeability;
     (ii) the origin truthfully signs but *declares a class above its true
     class* → origin capture.
   - [ ] Conclude: the residual = {signature forgery} ∪ {origin-class capture};
     the first is cryptographically excluded ⇒ **origin-class capture is the
     unique residual.**
2. **Machine-checked support.**
   - [ ] Extend the ProVerif model (E2.1) with a query: "can the attacker make
     the evaluator accept a claim whose true origin class is below the accept
     floor, without the origin key?" Expect `false` (cannot) — which *is* the
     reduction, mechanically confirmed.
3. **Adversarial search (empirical falsification attempt).**
   - [ ] Run a large randomized + guided search over manifests/operations
     (millions of cases) trying to exceed the true ceiling without origin key.
     Expect **zero successes** outside origin capture.

### Variants / ways to test

- [ ] **Crypto on/off:** with signatures disabled, forgery should re-appear as a
  second residual — confirms crypto is what removes it (ties to W2/minimality).
- [ ] **Partial origin key compromise** (e.g. attacker has an *expired* key) —
  confirm it doesn't help.
- [ ] **Multi-origin composition:** can mixing a high-class honest origin with a
  low-class poisoned one launder the poison? (Must fail — composition is
  min-bounded.)

### Data to record

- [ ] `attempt_class, used_origin_key(bool), exceeded_true_ceiling(bool)`,
  ProVerif query results, search-space size.

### Pass / interpretation

- [ ] **PASS** = (proof sketch closes) ∧ (ProVerif query `false`) ∧ (search finds
  zero non-origin-capture successes). Deliverable: **Theorem 2 (Residual
  Reduction)** — the spine of Goal 2.

### Failure modes

- Search finding *any* non-capture success = a genuine third attack surface
  (publishable in its own right, but re-scopes the paper) — investigate before
  proceeding.

---

## P2-B2 — Taxonomy of origin-capture mechanisms

**Objective.** Turn "the adversary lies about the class" into a graded set of
*concrete, buildable* capture vectors against the SAGA-backed stack, each with a
measured work-factor.

### What to build

- [ ] `attacks/origin_capture/` with one module per vector, each exposing
  `attempt(target_source, deployment) -> CaptureResult(success, work_factor, detectable)`.
- [ ] `experiments/p2_b2_capture_taxonomy.py`.

### The vectors (build and grade each)

1. [ ] **Credential capture** — get the Provider/CA to issue (or accept) a VC
    that presents a low-warrant source as a high class. Test: register a
    look-alike DID; reuse a leaked key; exploit weak registration checks.
2. [ ] **Class-misattribution** — attack the *classifier* that maps a source to a
    `SourceClass`. Test each classification basis: URL/domain pattern (typosquat,
    open-redirect on a trusted domain), "signed feed" (replay an old signature),
    allow-list membership (stale entry), MIME/format heuristics.
3. [ ] **Legitimate-origin compromise** — take over a *genuinely* high-warrant
    origin that is weakly secured: stale API key, writable first-party DB row,
    stale DNS/subdomain takeover, expired-but-trusted cert.
4. [ ] **Trust-bootstrap abuse** — exploit onboarding to mint a high-class
    identity (self-asserted class accepted at registration, weak proof-of-control).

### Work-factor metric (define once, apply to all)

- [ ] `work_factor = ` tuple of (access level required ∈ {none, network,
  insider, root}, #steps, prerequisite secrets, $ cost proxy, detectability ∈
  {silent, logged, alerting}). Normalise to an ordinal 1–5 "difficulty" for the
  cross-vector comparison.

### Variants / ways to test

- [ ] **With vs without SAGA Plane-1 hardening** — crucial: some vectors
  (credential capture, bootstrap abuse) should be *blocked by SAGA already*.
  Showing which are blocked sharpens which residuals are *real* (the ones SAGA
  doesn't cover — primarily class-misattribution and legitimate-origin
  compromise, which are *outside* identity).
- [ ] **Static vs dynamic classifier** — if the SourceClass is assigned once vs
  re-checked, does the attack window differ?
- [ ] **Detectability sweep** — for each vector, what logging/anomaly signal does
  it leave? (Feeds B6.)

### Data to record

- [ ] `vector, success(bool), work_factor_tuple, difficulty_1to5, blocked_by_saga(bool), detectable`.

### Pass / interpretation

- [ ] **PASS** = a populated taxonomy table where at least one vector succeeds at
  low difficulty *and is not blocked by SAGA* (that's the real residual). The
  table is a paper figure and the menu the novel attack chooses from.

### Failure modes

- If SAGA blocks *everything*, the residual is purely "legitimate-origin
  compromise" (classifier/source security, not identity) — which is still real
  and is actually the cleanest story; don't force the others.

---

## P2-B3 — The "weakest high-warrant origin" attack (the real-world break)

**Objective.** Show the *optimal* attacker target in a realistic ecosystem, and
the striking property that **CAPM's own warrant map tells the attacker where to
aim**. This produces the headline residual ASR-at-cost and seeds the WGOT attack.

### What to build

- [ ] `capm/ecosystem/graph.py` — ecosystem model: sources (each with
  `warrant_ceiling` *and* an independent `integrity_strength`), agents, orgs,
  and which agents read which sources.
- [ ] `attacks/wgot/targeting.py` — the attacker's optimiser:
  `argmax over sources of value(s)` where `value(s) = f(warrant_ceiling(s), 1/capture_cost(s), reachability(s))`.
- [ ] `experiments/p2_b3_weakest_origin.py`.

### Procedure

1. [ ] Build a realistic ecosystem (see variants for the distributions).
2. [ ] Attacker computes the target ranking from the *observable* warrant map.
3. [ ] Execute the chosen B2 capture vector at the top target; run the full
    chain; measure end-to-end **residual ASR** and the **work-factor** spent.
4. [ ] Compare to a **baseline attacker** that targets randomly or targets the
    highest-warrant origin *ignoring* integrity cost — show WGOT (warrant ÷ cost)
    beats both.

### Variants / ways to test

- [ ] **Ceiling/integrity correlation:** the realistic and scary case is when
  high warrant does *not* imply high integrity (a trusted-but-sloppy gov API).
  Sweep correlation from −1 (worst) to +1 (best) and show how residual ASR moves.
- [ ] **Target-selection strategies:** random / max-warrant / min-cost /
  max(warrant÷cost) [=WGOT] / oracle. WGOT should dominate non-oracle.
- [ ] **Ecosystem scale:** 10, 100, 1000 sources — does targeting get *easier*
  with scale (more weak high-warrant origins to find)?
- [ ] **Multiple high-value claims:** fraction of the ecosystem's important
  claims the attacker can poison via the single best origin.

### Data to record

- [ ] `strategy, target_source, target_ceiling, target_integrity, capture_success, work_factor, end_to_end_asr, n_high_value_claims_compromised`.

### Pass / interpretation

- [ ] **PASS** = WGOT achieves **measurably higher ASR per unit work** than
  naive strategies, and residual ASR is **non-zero at realistic cost.** Embrace
  the non-zero number — it's the point.
- [ ] The quotable result: "the defense computes the attacker's optimal target."
  Show that the *better-calibrated* the warrant map, the *sharper* the targeting
  (ties to the synthesis twist).

### Failure modes

- Tuning the ecosystem so the attack always/never works — use *defensible,
  cited* distributions for ceilings and integrity (justify them in the doc), or
  report across a sweep so no single hand-picked setting carries the claim.

---

## P2-B4 — Residual-risk cartography

**Objective.** Quantify *how much* CAPM shrank the attack surface and *where*
the residual concentrates — the practitioner-facing payoff.

### What to build

- [ ] `experiments/p2_b4_cartography.py` + an SVG heat-map generator (reuse the
  Phase-1 `svg.py`, zero plotting deps).

### Procedure

1. [ ] Over many realistic topologies, compute:
    - **pre-CAPM surface** = every (relay, content) pair an attacker could
      manipulate (the whole chain).
    - **post-CAPM surface** = the set of origin-capture chokepoints (high-warrant
      origins reachable to high-value claims).
2. [ ] Compute the **collapse ratio** = |post| / |pre| and the **concentration**
    (what fraction of high-value claims route through the top-k origins).

### Variants / ways to test

- [ ] **Topology families:** star (one hub agent), deep chains, wide fan-in,
  multi-org meshes — does residual concentrate differently?
- [ ] **Source-mix sweep:** few authoritative + many editable vs the reverse.
- [ ] **k-sweep:** how few origins cover X% of high-value claims (the hardening
  budget question: "harden these 5 and you cover 80%").

### Data to record

- [ ] `topology, n_sources, pre_surface, post_surface, collapse_ratio, top_k_coverage`. Figure: chokepoint heat-map per topology.

### Pass / interpretation

- [ ] **PASS** = a strong, consistent **collapse ratio** (e.g. surface reduced by
  orders of magnitude) *and* a small top-k covering most risk. Message:
  "CAPM converts an unbounded transitive surface into N hardenable origins."

### Failure modes

- If the residual does *not* concentrate (every origin equally risky), the
  "actionable hardening" story weakens — report it honestly; it would mean the
  ecosystem matters more than the defense.

---

## P2-B5 — Adaptive origin-capture under partial knowledge

**Objective.** Bound what a *realistic* attacker (incomplete warrant map, limited
probing) can achieve — the realism envelope of WGOT.

### What to build

- [ ] `attacks/wgot/partial_knowledge.py` — attacker with a noisy/partial view of
  ceilings + a query budget to probe/infer classes from observable signals
  (real-model inference where the class must be guessed from behaviour).
- [ ] `experiments/p2_b5_partial_knowledge.py`.

### Procedure

1. [ ] Hide the true warrant map; expose only observable signals (domain,
    response style, latency, whatever a real attacker sees).
2. [ ] Give a query budget B; attacker probes, infers ceilings, targets, attacks.
3. [ ] Sweep B and noise level; measure how fast residual ASR approaches the
    full-knowledge B3 value.

### Variants / ways to test

- [ ] **Knowledge level:** full → partial → none-but-probing.
- [ ] **Probe budget:** B = 0, 1, 5, 20, 100.
- [ ] **Noise:** observation noise on inferred ceilings (0–50%).
- [ ] **Inference method:** heuristic vs LLM-based class guessing.

### Data to record

- [ ] `knowledge, budget, noise, inferred_target_correct(bool), residual_asr, fraction_of_full_knowledge_asr`.

### Pass / interpretation

- [ ] **PASS** = a curve showing whether WGOT degrades gracefully (still strong
  under partial knowledge — *scarier*, stronger paper) or sharply (needs
  near-full knowledge — bounds the threat). Either is a real finding; report the
  curve and state which regime real deployments fall in.

### Failure modes

- Letting the attacker "cheat" by reading the true map through a side channel —
  audit the harness to ensure only observable signals are exposed.

---

## P2-B6 — Detection / second-order defense boundary

**Objective.** Determine whether forcing the attacker to origin capture is itself
cheaply detectable — i.e. whether WGOT is a *durable* contribution or a one-step
fix — and characterise the next cat-and-mouse round.

### What to build

- [ ] `capm/detect/origin_anomaly.py` — a detector flagging anomalous origin-class
  assertions (class inconsistent with a source's history/behaviour/peers).
- [ ] `attacks/wgot/evasion.py` — the attacker's counter (slow, legitimate-looking
  capture; behavioural mimicry).
- [ ] `experiments/p2_b6_detection.py`.

### Procedure

1. [ ] Run the detector against WGOT captures from B3/B5; measure TPR/FPR.
2. [ ] Let the attacker adapt to evade (mimic legitimate onboarding, age the
    captured origin, match peer behaviour); re-measure.
3. [ ] Iterate a few rounds; observe whether the residual narrows to nothing or
    stabilises at a smaller-but-real surface.

### Variants / ways to test

- [ ] **Detector signals:** history-based, peer-consistency, rate-of-change,
  cross-org corroboration — which catches the most at acceptable FPR?
- [ ] **Evasion effort vs detection:** plot attacker work-factor vs detector TPR
  (the cat-and-mouse curve).
- [ ] **Cost to defender:** FPR / operational burden of running the detector
  (does it just move the problem?).

### Data to record

- [ ] `round, detector_signal, tpr, fpr, attacker_work_factor, residual_after`.

### Pass / interpretation

- [ ] **PASS** = a clear statement of the second-order boundary: either
  "origin-class anomaly detection cheaply closes most of the residual" (then
  WGOT motivates that detector as the fix — still a contribution) or "evasion
  keeps a stable residual at cost C" (then WGOT is durable — stronger). Both
  preempt the reviewer's "why not just detect it?" question.

### Failure modes

- A detector that only works because the evasion is naive — make the evader use
  the strongest realistic mimicry before declaring the residual closed.

---

# CROSS-CUTTING TASKS (do once, apply to all)

- [ ] **Seeding & CIs:** every stochastic experiment takes `--seed`; ≥ 20 seeds;
  Wilson for rates, bootstrap for ratios, McNemar for paired defense comparisons,
  Spearman for monotone relationships. (Reuse `stats.py`.)
- [ ] **Raw rows always:** write per-trial CSV under `results/p2/<exp>/`; never
  only aggregates. Every figure regenerable by `make_report` with zero model
  calls from cached rows.
- [ ] **Provenance of numbers:** every reported number traces to a `runlog/`
  entry + a CSV row; nothing from memory.
- [ ] **Ecosystem distributions:** centralise the ceiling/integrity distributions
  in `configs/ecosystem.yaml` with cited justifications; sweep rather than
  hand-pick.
- [ ] **Two framings kept separate:** "relay attacks → ASR 0 (Goal 1)" and
  "origin capture → ASR>0 at cost (Goal 2)" must never be averaged together; they
  are different threat classes and must be reported in separate tables.
- [ ] **Honesty ledger:** maintain `docs/THREATS_TO_VALIDITY.md` listing every
  assumption (ecosystem realism, classifier model, detector strength, real-model
  sample size) so the paper's limitations section is pre-written.

---

# SUGGESTED EXECUTION ORDER (matches the plan's sequencing)

1. [ ] **P2-W1** (invariant) + **P2-B1** (reduction) — the two theorems. No model
    calls. Everything hangs on these; do them first.
2. [ ] **P2-W2** (dose–response) + **P2-W3** (content-independence) — fast,
    mostly re-points existing data into the two "why" figures.
3. [ ] **P2-B2** (capture taxonomy) + **P2-B3** (weakest-origin / WGOT) — the
    empirical heart; the novel attack is born here. Highest effort.
4. [ ] **P2-B4** (cartography) — the memorable practitioner figure.
5. [ ] **P2-W4** (minimality) + **P2-W5** (generality) — strengthen the principle.
6. [ ] **P2-B5** (partial knowledge) + **P2-B6** (detection) — realism + durability.

Backbone = 1–3. Memorable figure = 4. Borderline→clear-accept = 5–6.
