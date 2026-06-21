# CAPM Phase 2 — NDSS Final Synthesis

**Cross-Agent Provenance Manifests: from an empirical defense to a principle and its unique residual.**

*Companion to `PHASE2_IMPLEMENTATION_REPORT.md` (the full rolling ledger) and
`PHASE2_RESULTS_SUMMARY.md` (auto-generated at-a-glance results).
This document is the reviewer-facing synthesis: what Phase 2 set out to prove, how
each experiment is constructed to withstand a specific class of NDSS critique, the
empirical findings, and — at the end — a deep, honest analytical reflection on what
holds, what does not, and what remains.*

---

## 0. One-paragraph thesis

Phase 1 built CAPM — a defense that computes a claim's *warrant* (epistemic
justification) from an external, signed provenance manifest rather than from the
receiving model's in-context judgement — and showed empirically that it contains
"semantic laundering" (relay attacks → ASR 0). Phase 2 asks the two questions a
reviewer will: **why** does it work, and **where** does it break? It answers the
first by reframing containment as an **algebraic invariant** — *warrant is monotone
non-increasing under every relay operation* (**Lemma 1**) — proven by exhaustion
and shown to be **independent of CAPM's specific 5-level lattice**. It answers the
second with a **reduction**: modulo signature unforgeability, **origin-class capture
is the *unique* residual attack** (**Theorem 2**). It then *mines* that single
residual: a taxonomy of capture vectors, a **novel attack (WGOT)** that targets the
weakest high-warrant origin by warrant÷cost, a cartography that collapses the attack
surface ~19× to a handful of chokepoints, a partial-knowledge realism study, and the
second-order detection boundary. The two threat classes are never averaged.

---

## 1. Methodology at a glance

| Property | How Phase 2 enforces it |
|---|---|
| **Provenance of every number** | Each reported figure traces to a per-experiment CSV under `data/`; `experiments/implementation_report_summary.py` re-derives the headline table from those CSVs with zero model calls. |
| **Negative controls everywhere** | Every "0" claim ships with a control engineered to be *non*-zero — proving the test can fail (W1 non-monotone ops fire 144 violations; B1 class-capture/no-ceiling controls fire 694/1184; W5 non-monotone model leaks at 0.70). |
| **Grounded in the real evaluator** | Attack/surface experiments (B2–B6) decide "accepted?" by running the actual `WarrantEvaluator` over signed manifests, not a hardcoded threshold. |
| **Statistics** | Wilson CIs for rates, bootstrap CIs for ratios, Spearman for monotone trends, McNemar for paired defenses; ≥20–30 seeds where stochastic. |
| **Goal-1 / Goal-2 separation** | Relay-laundering ASR (Goal 1) and origin-capture ASR-at-cost (Goal 2) are reported in *separate* tables and never combined into a single headline number. |
| **Adversaries played to win** | The WGOT attacker and the B1 search use every lever available; where the defense fails (origin capture), the failure is reported as the *finding*, not hidden. |

The testbed is dependency-light (stdlib + `cryptography`); figures use a phase-2
`matplotlib` venv; the symbolic proof uses ProVerif 2.05; the only model-backed
steps are W3 (real Gemini-2.5-flash as the "naive content judge") and the optional
LLM hooks — all cached and degrade-gracefully.

---

## 2. Structured summary — framed to the critique each experiment answers

> **Note on claims.** This section states results *as built and as originally
> claimed*. An internal adversarial review panel (see §4) flagged several of these
> as overstated — most importantly the "novel attack" label on WGOT, the
> unqualified "unique residual," and the mean-only "~19×." §4.4 gives the precise
> softening each should receive before submission; read the two sections together.

### Goal 1 — *why* the defense works (the invariant)

**P2-W1 · Monotonicity Invariant (Lemma 1).**
*Reviewer critique answered:* "Your ASR=0 is a property of your specific constants /
test cases."
*Construction:* extract the scoring rule into pure functions (`capm/analysis/operations.py`)
and check `output ≤ min(inputs)` over the **entire** lattice cross-product (335
checks) **plus** 10,000 random *signed* manifests scored by the live evaluator, plus
a 20-seed × 2,000-chain robustness sweep (40,000 more). Two deliberately
non-monotone control operations are run through the identical harness.
*Result:* **0 violations across 50,335 checks**; controls fire **144** times. The
live evaluator and the pure algebra agree exactly (0 mismatches). "Relay attacks → ASR 0"
is now a machine-checked lemma, not an experimental number.

**P2-W2 · Dose-Response (Figure A).**
*Critique answered:* "Is the invariant actually load-bearing, or incidental?"
*Construction:* define a violation-magnitude metric **V** = expected positive Δwarrant
a weakened policy hands the attacker (a magnitude, defined a priori from the algebra,
*not* the outcome); measure ASR via the real benchmark; correlate across 10 policy
configs.
*Result:* **Spearman ρ(V, ASR) = 0.899 (>0.7)**. Crucially the relation is *not*
tautological: `no_signatures` gives V=0.281 but ASR=0, and `penalty_x0.50` gives V=0.5
but ASR=0 — warrant inflation below the accept threshold yields no success. The strong
rank-correlation across the gradient is therefore evidence, not bookkeeping.

**P2-W3 · Content-Independence (Option A vs Semantic Laundering).**
*Critique answered:* "A model in the loop can always be talked into self-licensing."
*Construction:* (Sweep 1) fix a low-warrant manifest, vary the *text* across neutral →
prompt-injection → authority-spoof payloads; (Sweep 2) fix the text, vary the manifest.
The same payloads are scored by a **real Gemini-2.5-flash** content judge as a contrast.
*Result:* CAPM verdict variance over text = **0.000** while the real LLM judge's variance
= **3.556** — and the honest nuance is that Gemini *resisted* crude injection but was
**laundered by authority framing** (rated an editable-source claim 4/4 as "peer-reviewed
consensus" / "[OFFICIAL] Verified Authority Registry"). Sweep 2: the CAPM verdict moves
systematically with origin class and hop count (variance 1.648). Text has no channel into
the verdict; the manifest fully controls it.

**P2-W4 · Minimality (smallest sufficient core).**
*Critique answered:* "Which of your six components actually matter?"
*Construction:* exhaustive 2⁶ = 64-subset power-set search; a subset is *secure* if
relay ASR ≤ 0.1 and *minimal* if removing any one component breaks it.
*Result:* **two minimal cores, both size 2.** `apply_transformation_penalty` is the lone
**essential** component (criticality 1.00); it needs exactly one of `{origin ceiling,
lie-detection}` as a partner. Signatures / soft-binding / cross-org awareness carry no
weight *for the relay-laundering ASR metric* (they defend other threats — forgery
rejection, the text-only scenario, unverified boundaries — explicitly scoped).

**P2-W5 · Generality beyond the lattice.**
*Critique answered:* "This all depends on your bespoke 5-level lattice."
*Construction:* lift the warrant algebra behind a `WarrantModel` ABC; re-run the relay
adversaries under lattices of heights 3/5/7/10 and continuous linear/convex/concave decay,
against a non-monotone control — signatures and lie-detection held constant.
*Result:* **all 7 monotone models contain (ASR 0.000); the non-monotone control leaks
(0.700).** Honest secondary finding: the *encoding* tunes the utility/precision tradeoff
(coarse `lattice_h3` → utility 0.25; mild `concave` → 1.00) but never containment.
Containment follows from monotonicity *as algebraic structure*.

### Goal 2 — *where/how* it breaks (the residual)

**P2-B1 · Residual Reduction (Theorem 2).**
*Critique answered:* "You haven't bounded the attack surface; you've just listed attacks
you tried."
*Construction:* a markdown proof (`docs/proofs/residual_reduction.md`) that exceeding the
true origin ceiling forces a false *signed* origin class ⇒ key-forgery (crypto-prevented)
or origin-class capture; plus a 10,000-chain adversarial search using **every lever except**
class-lying and key-forging (number over-claims, transformation lies, mid-chain origin
re-declarations), with two residual-open controls.
*Result:* **0/10,000 residual successes** (3,739 over-claims, 3,315 transformation lies,
5,571 mid-chain injections all contained); controls fire at **6.94% / 11.84%**. The
residual is provably one-dimensional.

**P2-B2 · Origin-Capture Taxonomy.**
*Critique answered:* "Origin capture' is a hand-wave; how would it actually happen?"
*Construction:* 5 concrete vectors (typosquatting, stale allowlist, credential leak,
legitimate origin compromise, trust-bootstrap abuse) each scored for difficulty (1–5),
SAGA-blocked?, detectability, with a testbed ASR simulation.
*Result:* **SAGA blocks exactly 1 of 5** (typosquatting, via key-binding); the other 4
present a *legitimately authenticated* identity and reach CAPM with **principal-facing
ASR 1.00**. Empirically the three top-tier vectors are *identical* to CAPM — discrimination
lives in the analytic columns (difficulty/detectability), not CAPM's runtime.

**P2-B3 · WGOT — Warrant-Guided Origin Targeting (the novel attack).**
*Critique answered:* "Is there a real, non-obvious attack here, or just 'capture is bad'?"
*Construction:* a synthetic ecosystem with *independent* warrant-ceiling and
integrity-strength axes at tunable correlation ρ; four targeting strategies (random,
max-warrant, min-cost, **WGOT = ceiling÷cost**); ASR grounded in the real evaluator;
30 seeds.
*Result:* **WGOT strictly dominates random** (ΔASR +0.280 [+0.259,+0.302]) and is the
**robust optimum at every ρ**. Its edge peaks at ρ≈0 (warrant/cost decoupled); at ρ→+1
("secure design") `min_cost` collapses to 0 while WGOT stays on top. WGOT uses only
*public* information (CAPM's own published ceilings) — the defense's transparency becomes
a targeting oracle.

**P2-B4 · Residual-Risk Cartography.**
*Critique answered:* "Even if capture is the only residual, the surface is still the whole
mesh."
*Construction:* four network topologies (star hub, deep chains, wide fan, multi-org mesh);
pre-CAPM surface = all agents+sources; post-CAPM surface = only sources the real evaluator
would ACCEPT; collapse ratio + top-3 chokepoint coverage; 30 seeds.
*Result:* **~19× average surface collapse** (ratio 0.121; **median ~9.7×, range
3.9×–37×** — relay-heavy meshes collapse hardest because Lemma 1 makes relays
unlaunderable); **top-3 chokepoints carry 73%** of high-value claims. The defender's
hardening list is three names long. *(Conditional on the Zipf-reach-by-warrant
assumption — see §4.4.)*

**P2-B5 · Adaptive capture under partial knowledge.**
*Critique answered:* "WGOT assumes an oracle no real attacker has."
*Construction:* the attacker probes ceilings under Gaussian observation noise and a limited
probing budget, then runs WGOT on the *estimates*; success decided by *true* ceilings; swept
across noise σ ∈ {0.1, 0.25, 0.4}.
*Result:* WGOT **degrades gracefully**: blind (0 probes) lands at **0.31** (it reduces to
min-cost targeting, since *cost* is still known — reported accurately, not "≈ random"), and
climbs to the oracle bound (**0.46**) with probing; noisier signals need proportionally more
probes (σ=0.1 → 1 probe/origin reaches 99%; σ=0.4 → ~4). Exploiting the residual carries a
measurable reconnaissance cost.

**P2-B6 · Detection / second-order boundary.**
*Critique answered:* "If you can't prevent capture, is the defense useless?"
*Construction:* a stateful per-origin EWMA class-jump detector (`capm/detect/origin_anomaly.py`);
a stream of honest origins (with legitimate upgrades), naive attackers (one big class jump),
and gradual attackers (slow class ramp); sweep the detector threshold for TPR/FPR.
*Result:* the detector catches **naive** capture (TPR 0.975 at FPR 0.022) but **gradual**
evasion erodes it (TPR 0.655 → 0.135). It **cannot close** the residual: catching gradual
ramps requires dropping the threshold until FPR spikes >10%, because a gradual class-ramp is
*statistically indistinguishable from a legitimate reputation upgrade*. Detection raises the
attacker's cost and latency — a genuine second-order boundary, not a fix.

---

## 3. The arc in one figure-of-merit table

| | Goal 1 (*why* — invariant) | Goal 2 (*where* — residual) |
|---|---|---|
| **Backbone** | W1: Lemma 1, 0/50,335 violations | B1: Theorem 2, 0/10,000 residual successes |
| **Load-bearing-ness** | W2: ρ(V,ASR)=0.899 · W4: 2-component core | B2: 1/5 SAGA-blocked, 4 reach CAPM |
| **Mechanism isolation** | W3: text-variance 0 vs LLM 3.556 | B3: WGOT ΔASR +0.280, robust optimum |
| **Generality / scope** | W5: 7/7 monotone contain, control leaks | B4: ~19× collapse, top-3 = 73% |
| **Realism / limits** | — | B5: recon cost · B6: TPR 0.97 naive, gradual evades |

Goal 1 says laundering is *structurally* impossible; Goal 2 says the one thing left —
capturing an authoritative origin's identity — is a one-dimensional, mappable, costly,
partially-detectable residual. Together they convert "we tried attacks and it held" into
"here is the theorem, here is the unique way past it, and here is its cost surface."

---

---

# 4. Deep Analytical Synthesis

*This section was written after running an internal **adversarial review panel** —
six independent reviewer personas (formal-methods, empirical-rigor, threat-model,
reproducibility, related-work, and a harsh completeness skeptic), each instructed
to read the artifact and critique it as an NDSS reviewer, followed by a Program-
Committee meta-reviewer that consolidated their verdicts. The panel's consensus
verdict was **MAJOR REVISION** (4 weak-accept, 2 major-revision). I treat that
verdict as the honest baseline for this reflection rather than my own builder's
optimism. Where the panel made a factual error — one reviewer claimed the ProVerif
model was absent — the meta-reviewer caught it: the model **is** present and
substantive (`proofs/proverif/capm_manifest.pv`, 80 lines, 15 queries/events).*

## 4.1 Holistic summary — how the experiments tie together

Phase 2 is a single argument in two movements, deliberately structured so each
experiment closes a door a skeptic would otherwise leave open.

**Movement 1 (Goal 1) turns an observation into a theorem.** Phase 1's "relay
attacks → ASR 0" was a number; a reviewer rightly distrusts numbers. W1 re-derives
it as **Lemma 1**: warrant is a quantity that can only move *down* the lattice,
proven by exhausting the operation×lattice cross-product and 50,335 signed-manifest
checks, with negative controls that fire to prove the test isn't vacuous. W2 then
shows the invariant is *causally* load-bearing (ASR rises monotonically as you
remove it, ρ=0.899) and not circular (warrant inflation below threshold buys no
attack). W3 isolates the *mechanism* — the verdict is a function of the manifest,
not the text — by contrasting CAPM's flat response with a real LLM that the same
payloads sway. W4 strips the defense to its **irreducible core**, and W5 shows the
whole thing survives swapping the lattice for any monotone encoding. The five
experiments together say: *containment is structural, minimal, and encoding-
independent — it is the monotonicity, not the constants.*

**Movement 2 (Goal 2) bounds, then mines, the failure.** B1 proves **Theorem 2**:
once you assume signatures hold, the *only* way past CAPM is to capture an
authoritative origin's identity — a one-dimensional residual, confirmed by a
10,000-chain search that tries everything else and fails 0/10,000 while its
controls breach. Having localized the hole, B2 enumerates *how* you'd reach it
(five capture vectors, only one of which SAGA's identity layer blocks), B3 builds
the **rational attacker** that picks the cheapest high-warrant origin, B4 measures
the **defensive payoff** (the surface collapses ~19× to a 3-origin hardening list),
B5 adds **realism** (the attacker must pay for reconnaissance), and B6 maps the
**detection boundary** (you can raise the cost of capture but never close it).

The seam between the movements is the honest center of the whole work: the *same*
property (monotonicity) that makes relay laundering impossible is *silent* about
who the origin is — so the residual is exactly, and only, origin identity. Goal 1
and Goal 2 are not two papers stapled together; they are the positive and negative
space of one invariant.

## 4.2 Final results and their core theoretical inferences

1. **Containment is an algebraic property, not a tuning artifact.** Lemma 1 +
   W5's seven-encoding generalization mean the result transfers to any warrant
   system whose composition operator is monotone. *Inference:* the design
   principle — "score provenance with a monotone, externally-computed lattice" —
   is portable beyond CAPM's specific constants. This is the most defensible and
   most reusable contribution; all six reviewers ranked it the strongest.

2. **The attack surface of a provenance defense is reducible to its trust
   roots.** Theorem 2 says relay topology is irrelevant to the residual — only the
   origin identities matter. *Inference:* defending a multi-agent mesh is not a
   mesh-wide problem; it is an origin-attestation problem (B4 makes this concrete:
   harden 3 nodes, cover 73% of high-value claims). This reframes "secure the
   pipeline" as "secure the sources."

3. **Transparency is double-edged.** WGOT (B3) shows that *publishing* warrant
   makes the defense legible to defenders **and** to attackers, who can compute
   warrant÷cost. *Inference:* a provenance system should expose enough warrant for
   receivers to act but couple high warrant to high integrity (ρ→+1), or the map
   becomes a targeting oracle. This is a genuine design tension the field has not
   articulated.

4. **Detection of identity capture is fundamentally limited by the legitimacy of
   change.** B6's gradual-evasion result is, at root, that "an origin earning a
   higher reputation" and "an attacker faking one slowly" produce the same signal.
   *Inference:* no anomaly detector on class-assertions alone can be both
   sensitive and specific; closing the residual needs *out-of-band* attestation
   (offline certification, hardware roots), not better statistics on the manifest
   stream.

## 4.3 What worked, and what did not (honest limitations)

**What worked — robustly:**
- **The formal-and-empirical core (W1/B1).** Rigorous, machine-checked, with
  teeth-bearing controls and exact algebra↔evaluator agreement on the sampled
  space. The panel was unanimous that this is publishable.
- **Provenance discipline.** Every number traces to a CSV; 11/12 experiments are
  deterministic; the summary script re-derives the headline table from raw rows.
  The artifact-evaluation reviewer credited this explicitly.
- **Intellectual honesty in the hard places.** B6 states outright that detection
  cannot close the residual; W4 flags non-load-bearing components; B5 corrects
  "blind ≈ random" to "blind = min-cost." Multiple reviewers praised this even
  while critiquing the framing.

**What did not hold up to adversarial review:**

- **Everything is synthetic (panel's #1, HIGH).** There is no real multi-agent
  deployment, no human-subject study of whether agents/people respect a
  QUARANTINE verdict, and the ecosystem's integrity values are literally
  `rng.random()`. A systems-security venue will ask whether the headline numbers
  (19× collapse, WGOT dominance) reflect reality or chosen parameters. *This is
  the single most likely rejection driver and I concur it is real.*
- **WGOT is a greedy heuristic, over-billed as a "novel attack" (#2, HIGH).** It
  is a one-line `warrant_ceiling / capture_cost` sort — the textbook value-per-cost
  best response — running on an *unjustified* cost model (`capture_cost =
  1 + 9·integrity`) that is moreover **decoupled from B2's own difficulty
  ratings** (B3–B6 never read the taxonomy's numbers). The contribution is the
  *application to CAPM and the ρ-dependence*, not the algorithm; calling it "novel"
  invites a novelty rejection.
- **The "unique residual" framing conflates a proof of incompleteness with a
  feature (#3, HIGH).** Theorem 2 proves CAPM is *unavoidably incomplete* on
  origin capture; B2 confirms 4/5 vectors reach ASR 1.00 principal-facing. Spending
  the back half "mining" that residual can read as dressing up an unfixable hole. A
  naive reader of the ASR table sees "CAPM lets through 100%" because the metric
  mixes depth-1 origin capture (unpreventable by design) with relay laundering
  (prevented).
- **Soft-binding is a toy (#4, MEDIUM).** Token-set SHA256 — the code says so
  itself ("toy perceptual hash… a real impl uses a watermark detector"). W3
  Sweep-1b only tests reordered payloads, never an adversarial LLM paraphrase. Any
  "integrity" claim for it is unsupported.
- **No Related Work section (#5, MEDIUM).** Positioning vs SAGA / C2PA / CaMeL /
  W3C-PROV / Denning-style information-flow lattices is scattered and superficial;
  the only baselines are four strawmen at ASR 1.00. Reviewers read missing
  positioning as inability to substantiate novelty.
- **The theorem framing outruns its evidence in two places (#6, #9, MEDIUM).** The
  algebra↔implementation equivalence is *sampling-validated, not proved* (rounding
  and clamp-boundary cases could be missed); and the EUF-CMA / trust-registry /
  ground-truth-ceiling premises of Theorem 2 are stated but not grounded or
  enforced (e.g., `origin_source_class = None` silently skips the ceiling —
  `evaluator.py:146`).
- **Statistical thinness (#7, #8, MEDIUM).** W2's ρ rests on **n=10** configs;
  W4's minimality conclusion sits on a **0.094-vs-0.10 knife-edge**. I ran the
  threshold sweep the panel asked for: at 0.05 the only core is {penalty, ceiling}
  (both essential); at 0.10 there are two size-2 cores; at ≥0.15 `apply_
  transformation_penalty` becomes *individually* sufficient (ASR 0.125). The honest,
  threshold-robust statement is therefore **not** "the core is exactly two
  components" but "**the transformation penalty is the one component that is load-
  bearing at every threshold — necessary in every minimal core, and sufficient
  alone once the security bar relaxes to 0.15**"; the ceiling/lie-detection partner
  is required only at stricter bars.

## 4.4 Overstated claims to soften before submission

| As written | Should become |
|---|---|
| "WGOT — the Phase-2 **novel attack**" | "the optimal capture-targeting heuristic under cost–value coupling; the contribution is its application to CAPM and the ρ-dependence" |
| "origin-class capture is the **unique residual**" | "**modulo Ed25519 EUF-CMA and CAPM's stated trust assumptions**, origin-class capture is the unique residual" |
| "CAPM collapses the attack surface **~19×**" | "~19× on average, **median ~9.7×, range 3.9×–37×**, conditional on the Zipf-reach-by-warrant assumption" |
| "soft-binding provides integrity" | "soft-binding is a **placeholder** pending a watermark backend; no integrity claim" |
| "Option A **defeats** Semantic Laundering" | "CAPM's external-evaluator design admits **no in-context-text channel** into the verdict, as instantiated by current LLMs" |
| "smallest sufficient core = 2 components" | "the transformation penalty is load-bearing at every threshold; the *size-2 core* claim is specific to the 0.10 bar" |

## 4.5 Specific refinements needed before paper submission

Prioritized from the panel's must-do list (high → low leverage):

1. **Add at least one real-world anchor.** A small live multi-agent mesh (mixed
   LLM families in a retrieval pipeline) measuring whether agents actually verify
   and respect CAPM verdicts and the real per-chain latency; and/or a human-subject
   study (N≈20–40) on verdict comprehension/trust. If infeasible, *validate the
   ecosystem generator* (class mix, reach, warrant–integrity coupling) against one
   open multi-agent system and state which assumptions real systems violate.
2. **Ground or ablate the WGOT cost model and reach assumption.** Replace
   `capture_cost = 1 + 9·integrity` with a B2-difficulty-grounded mapping (so
   B3–B6 operate on the *named* capture vectors, not fungible nodes), **and** run a
   sensitivity analysis over cost shape (linear/quadratic/exponential) and reach
   distribution (uniform/clustered/adversarial) showing the dominance and top-3
   results are not artifacts.
3. **Reframe WGOT and the residual** per §4.4, and add an **ASR-by-chain-depth**
   figure that separates the erosion win (relay laundering contained) from the
   depth-1 residual (origin capture, unpreventable). Annotate the ASR tables.
4. **Fix or demote soft-binding** — integrate a real robust watermark/perceptual
   hash and test it against LLM-generated adversarial paraphrases, or move it out
   of the warrant path as an explicit, claim-free placeholder.
5. **Write a unified ~1-page Related Work** (per-system: reuse / add / why), and
   add at least one non-strawman baseline (e.g., SAGA Plane-1 + revocation).
6. **Close or honestly scope the algebra↔code equivalence** — enumerate all
   (operation × lattice point × penalty-scale ∈ {0,0.5,1}) combinations, or add a
   Coq/Lean equivalence proof, or relabel it "empirically validated equivalence"
   with the sampling scope disclosed.
7. **Strengthen statistics** — raise W2 to ~15–20 configs or report a Fisher-z CI
   on ρ; sweep B6's σ and B3's copula ρ; document the full multi-level seeding in
   the README; ship the W4 threshold-sweep (already computed in §4.3).
8. **Restate cryptographic/trust qualifications** — cite RFC 8032 / Bernstein et
   al. for Ed25519 EUF-CMA, foreground Theorem 2's design premises, and enforce a
   non-null `origin_source_class` at the origin.

## 4.6 Research gaps and predictions for evolving threats

- **Adaptive, LLM-driven adversaries.** Every laundering attack here is rule-based.
  The next adversary jailbreaks or manipulates the *manifest generator itself*,
  learns cost distributions inductively, corrupts several *cheap* origins to
  assemble joint justification, or times captures to an origin's high-baseline
  window to slip the B6 detector. WGOT is the *floor* of attacker sophistication,
  not the ceiling.
- **Residuals within the residual.** Theorem 2 localizes to origin-class capture
  but does not classify *inside* it (typosquatting and legitimate-origin compromise
  are radically different costs/detectabilities), nor survey adjacent residuals: VC
  compromise, registry poisoning, signature-verification side-channels, or relays
  that *regenerate* content instead of passing the manifest at all.
- **Machine-checked and crypto-grounded foundations.** A Coq/Lean formalization of
  the evaluator against the abstract algebra, plus a symbolic unforgeability model
  for the manifest canonicalization (`dataclasses.asdict` + JSON — collision
  resistance is assumed), would elevate the "theorem" framing to its billing.
- **Cross-vendor generality.** Content-independence is shown on Gemini-2.5-flash
  with six calls; the result must be reproduced across Claude / GPT / open-source
  backends to show it is not model-specific.
- **Real ecosystem ground truth.** The ~30%-authoritative class mix,
  Zipf-reach-by-warrant, and Gaussian warrant–integrity copula are *posited*. Real
  registries (ML model hubs, GAIA-X, DeFi bridges) may have distributions that
  **invert** the cartography result — e.g., if authoritative origins are *not* the
  popular ones, the top-3 chokepoint story weakens. Measuring one real distribution
  is the highest-value future data point.
- **The deployment economics question.** Theorem 2 implies origin-class capture
  may be *cheaper* than other subversions; whether an organization would deploy
  CAPM, and with which complementary layers (revocation, freshness, offline
  attestation), is unaddressed and is ultimately what decides real-world impact.
- **Detector–attacker game theory.** B6's naive-vs-gradual contrast is stylized; a
  formal two-player incomplete-information game (gradual-ramp time/operational cost
  vs detector threshold, with active-learning detectors that probe marginal
  origins) is an open and natural next study.

## 4.7 Bottom line

Phase 2 delivers a **genuinely strong formal core** (Lemma 1, Theorem 2) with
exemplary reproducibility, wrapped in **experimental and positioning scaffolding
that an NDSS panel would send back for major revision** — chiefly because the
evaluation is entirely synthetic, the "novel attack" is an applied greedy
heuristic on an unjustified cost model, the "unique residual" framing under-states
that it is a proof of unavoidable incompleteness, and there is no related-work
positioning. None of these is fatal: the formal contribution is publishable, and
every flagged issue is addressable with one real-world anchor, an honest reframing,
a cost-model grounding, and the standard hardening of statistics, related work, and
qualified claims. The work's defining virtue — that it reports its own negative
controls, corrects its own optimistic phrasings, and now carries an adversarial
review of itself — is exactly the disposition needed to carry it from a strong
artifact to an accepted paper.

---

*Generated 2026-06-15. Empirical results: `PHASE2_RESULTS_SUMMARY.md`
(auto-derived). Full methodology + per-experiment integrity notes:
`PHASE2_IMPLEMENTATION_REPORT.md`. Formal proof: `docs/proofs/residual_reduction.md`
and `proofs/proverif/capm_manifest.pv`.*
