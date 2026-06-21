# CAPM Phase 3 — Realized-Provenance Attestation

### Binding warrant to what actually happened to each claim, not to what the agent says it did

**Status of this document.** This is the single working document for Phase 3, written in the same spirit as `CAPM_Design_Base.md`: it states the problem, develops the full mathematics in plain language, gives the build steps in order, and ends with a detailed experiment list mapped to each step. Phase 1 proved CAPM works (ASR 0.00 on transit attacks). Phase 2 proved the residual reduces to origin/wrapper capture. **Phase 3 closes the one gap both phases leave open: CAPM certifies the chain was intact, but not that the content actually travelled through it.**


---

## PART I — THE PROBLEM

### 1. What CAPM already guarantees, and the precise hole

CAPM binds a graded warrant to a claim's origin and proves that warrant is **monotone non-increasing** across hops. The warrant drops by a fixed penalty whenever an agent performs a transformation it cannot cryptographically verify (the A3 safe rule). This is correct and conservative. But look carefully at *what triggers the penalty*: it is the **declared transformation** — the operation type the agent reports ("I summarized", "I paraphrased"). CAPM penalizes the *label*, not the *effect*.

This creates a gap with two faces:

- **It is too crude.** A near-perfect summary and a content-destroying one are both labelled "summary", so both lose the same fixed warrant. The good transformation is over-penalized; the bad one is under-penalized. CAPM cannot tell them apart because it never looks at the content.
- **It quietly trusts the agent's self-report.** CAPM's founding principle is that trust must be judged from *outside* the model. But the transformation label is the agent describing its own behavior. Basing the penalty on a self-reported label re-introduces exactly the self-attestation CAPM was built to eliminate.

### 2. The phenomenon: reasoning-layer laundering

A relay agent can sign a fully valid manifest — correct keys, correct hash-chain, correct declared transformation — and still produce output that:

- **drops the load-bearing facts** (information loss),
- **says the opposite of the source** (contradiction: "severity 9.1" becomes "low", "affected: Windows 10/11" becomes "only Windows 7", "patch: KB123" becomes "no patch available"),
- **adds claims the source never made** (fabrication from the model's own parametric memory),
- **keeps the claim but loses its evidence** (the assertion survives, the proof behind it disappears).

In every case the manifest verifies and the warrant stays high, because nothing in CAPM's transit model inspects whether the content the model emitted is actually grounded in the source the manifest names. This is **realized-provenance failure**: the gap between *declared* provenance (what the manifest records) and *realized* provenance (what actually drove each output token). Laundering hides in that gap.

The sharpest version is the "Lying with Truths" attack: feed an agent fragmented but individually-true facts, and its drive for narrative coherence makes it emit a false global conclusion *in good faith*. Every source is real, every manifest verifies, warrant stays high — and the laundering happens entirely inside the model's reasoning. CAPM's transit adversary model brackets this case by construction.

### 3. Problem statement (paper-ready)

> In a multi-hop, cross-organizational agent chain, CAPM cryptographically binds a graded warrant to a claim's origin and guarantees that warrant is monotone non-increasing across hops. But the warrant is bound to the **declared** transformation — the operation an agent says it performed — not to what actually happened to the content. A relay can claim "I summarized source X," sign a perfectly valid manifest, and yet have produced text that drops the load-bearing facts, contradicts the source, or substitutes its own parametric memory. The manifest verifies; the content launders. We seek a mechanism that binds warrant to the **realized fate of each claim** — whether it was actually *used* from the source, *supported* by it, *contradicted* by it, or *fabricated* — measured from **observable effects** rather than the agent's self-report, and degrading warrant **per-claim** so that damage stays local.

One-line version for the abstract:

> CAPM verifies the provenance chain; Phase 3 adds **per-claim, verifier-auditable grounding evidence** and guarantees that this evidence can only **reduce** a claim's warrant, never inflate it — surfacing reasoning-layer laundering that the transit layer structurally cannot see.

### 4. The two design commitments (these are the contribution)

Everything in Phase 3 follows from two commitments, both already present in the `Claim_Warrant_Idea` note:

1. **Measure observed effects, not the self-reported operation label.** Trust drops because information was *actually* lost / contradicted / fabricated, detected by **auditable sensors** (recomputed or validated outside the relay's say-so), not because the agent called its action a "summary."
2. **Track warrant claim-by-claim, not per document.** The content is a set of individual claims; each is followed through the chain and keeps its own warrant. Damage stays local: a recipient still receives the claims that survived intact, warned only about the ones that degraded — instead of the whole message collapsing after a few hops.

---

## PART II — THE MATHEMATICS (in plain language)

This part builds the math from scratch. Every symbol is defined in words first, then written down. Nothing here requires the reader to already know the notation.

### 5. Claims, lineage, and warrant

**A claim** is one atomic unit of content — for structured sources, a single field. The CVE advisory *vendor = Microsoft, severity = 9.1, patch = KB123, affected = Windows 10/11* is four claims, not one document.

Write the set of claims a source produces at the origin as `C₀ = {c₁, c₂, …}`. When a relay agent at hop `k` transforms its input, each output claim either descends from one or more input claims or is newly introduced. We record this with a **lineage link**: every output claim `c'` carries a pointer `parent(c')` to the input claim(s) it came from. Chaining these pointers across hops gives each claim its own thread back to the origin. This per-claim thread is the thing the closest neighboring survey says **no current system provides** — that absence is our opening.

**Lineage is claimed, not trusted.** A pointer the relay supplies is only a *claimed* parent. A malicious or careless relay could point a fabricated output claim at whatever source claim maximizes its support score, which would re-introduce exactly the self-reporting CAPM exists to eliminate. So the verifier **never trusts an agent-supplied parent**: it re-derives the link by a deterministic matching/search procedure (the same matcher used for effect-tagging, §7), or, where re-derivation is ambiguous, validates the claimed parent against that procedure and degrades on mismatch. Throughout the rest of this document, `parent(c')` denotes the **verifier-derived** parent; the agent-supplied pointer is treated only as a hint to seed the search.

**Warrant** is a number in `[0, 1]` attached to *each claim at each hop*. Write `w_k(c)` for the warrant of claim `c` after hop `k`. CAPM today computes a single document-level warrant; we refine it to per-claim.

### 6. The two warrants: declared vs. realized

At each hop there are now **two** warrant values for a claim, and the whole mechanism is about how they combine.

**Declared warrant `w^decl`.** This is exactly what CAPM already computes: start at the origin's source-class ceiling, subtract the fixed monotone penalty for the declared transformation, min-bound over composed inputs. It depends only on the manifest. Nothing about Phase 3 changes how this is computed — we inherit it unchanged.

**Realized warrant `w^real`.** This is new. It asks: *given what the sensors observed about this specific claim, how much trust does the transformation actually deserve?* It is built from a set of **effect measurements** (Section 7), each a number in `[0, 1]` where 1 means "no damage" and 0 means "total damage."

### 7. The four effect measurements (the sensors)

For each output claim `c'` with verifier-derived source claim(s) `parent(c')`, we measure four quantities. Each is defined so that **higher = more trustworthy**, and each is produced by a sensor that is **auditable** — recomputed or validated independently of the relay's say-so — never by the agent self-reporting. The sensors differ in *where they can run*, which the trust model in §7a makes precise: NLI and embedding-similarity support are recomputable purely from source and output text (fully verifier-side); the usage probe reads the relay model's hidden states (runtime-internal, requires the access discussed in §7a); influence is an offline audit.

**(a) Usage `u(c') ∈ [0,1]` — did the output come from the source or from memory?**
Produced by the **probe** (AttriWiki-style). The probe is a logistic-regression classifier trained on the relay model's normalized final-layer hidden vector. For the tokens that produced `c'`, it outputs the probability that generation was *context-driven* (from the source) rather than *parametric* (from memory). So `u(c') ≈ 1` means "the model genuinely read this from the source"; `u(c') ≈ 0` means "the model produced this from its own memory" — which, for a claim the source did not contain, is a fabrication by definition.

**(b) Support `s(c') ∈ [0,1]` — does the source actually back the output claim?**
Produced by **calibrated embedding/activation similarity**: the (calibrated) similarity between the source-claim representation and the output-claim representation. The simplest form is cosine similarity over sentence embeddings, computable entirely verifier-side from text; an activation-space variant (in the spirit of training-free activation-fusion methods such as SteerFuse within DataDignity, arXiv:2605.05687) can be used where model access is available, but is *not* required and is not load-bearing. `s(c') ≈ 1` means the source strongly supports the claim; `s(c') ≈ 0` means the source is irrelevant to it. This catches **evidence loss** — the claim survives but its backing did not. (Similarity is a weak signal on its own — topically-similar distractors can inflate it — which is exactly why it sits under the `min` with NLI as a separate contradiction check, never as a sole gate.)

**(c) Faithfulness / entailment `f(c') ∈ {entail, neutral, contradict}` — does the source contradict the output?**
Produced by a small **NLI (natural-language inference) model**: does the source claim *entail*, stay *neutral* on, or *contradict* the output claim? We map this to a number: `entail → 1`, `neutral → 0.5`, `contradict → 0`. Contradiction is the worst case — it is not missing information, it is *wrong* information ("severity 9.1" rendered as "low", or "affected: Windows 10/11" rendered as "only Windows 7"). Note that valid abstraction is **not** contradiction: "9.1" rendered as "Critical" is faithful, because CVSS v3.1 maps 9.0–10.0 to Critical — the NLI/comparison layer must treat schema-consistent abstraction as `entail`, not `contradict` (tested in E2.2).

**(d) Influence `v(c') ∈ [0,1]` — did the source causally matter at all?** *(evaluation-only — see §9)*
Produced by **NeuroTaint-style counterfactual analysis**: would the output claim still have appeared if the source were removed? This is expensive and offline, so it does **not** sit in the live warrant. We use it to *validate* that the cheap runtime sensors (a–c) actually track real influence.

### 7a. The sensor trust model — who runs the sensors, and what each placement assumes

A sensor output is only worth signing if an adversarial relay cannot forge it. This is the central systems question of Phase 3, and it must be answered explicitly rather than assumed. **The relay never computes its own warrant-affecting sensors** — that would re-introduce self-attestation. Instead, sensors are placed according to what they need to read:

| Sensor                                       | What it needs to read                                          | Where it can run                                                                                                                     | Trust assumption                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| -------------------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **NLI faithfulness `faith`**         | source text + output text only                                 | **Fully verifier-side.** The verifier recomputes it from the two texts it already holds.                                       | None beyond the NLI model itself (a named, versioned TCB component). Strongest.                                                                                                                                                                                                                                                                                                                                                                                    |
| **Embedding-similarity support `s`** | source text + output text only                                 | **Fully verifier-side** (sentence-embedding variant). The activation-space variant needs model access; we do not depend on it. | None beyond the embedding model. Strong.                                                                                                                                                                                                                                                                                                                                                                                                                           |
| **Usage probe `u`**                  | the relay model's**hidden states** for the output tokens | Runtime-internal: the hidden states exist only where generation happened.                                                            | Requires one of: (i)**white-box / open-weight relay** whose runtime exports hidden states to an audited sensor; (ii) **a trusted sensor service** co-located with the runtime under remote attestation / TEE; or (iii) **re-execution** by the verifier on an open model with the same input (deterministic decoding). **Not available for black-box API relays** — there `u` is simply absent and the claim falls back to support+NLI. |
| **Influence `v`**                    | full execution trace                                           | Offline auditor, post-hoc.                                                                                                           | Evaluation/forensics only; never in the live warrant.                                                                                                                                                                                                                                                                                                                                                                                                              |

Three consequences the paper must state plainly:

1. **The guarantee degrades gracefully with access.** With only source and output text (any relay, including black-box APIs), Phase 3 still runs NLI + embedding support — the two fully verifier-side sensors — and the `min`-clamp guarantee holds. The hidden-state probe is an *additional* signal available only when the deployment gives runtime access; its absence lowers utility (less ability to distinguish faithful from memory-substituted), never security.
2. **The probe's runtime access is a named TCB component.** Whoever runs the probe (audited runtime, attested sensor service, or re-executing verifier) joins the TCB alongside the acquisition wrapper and the signing keys — and is evaluated as such (E-cost, and the threats ledger), exactly as CAPM already treats the wrapper. We do not claim "no new TCB"; we claim "a small, named, evaluated one, and the core guarantee survives without it."
3. **Signing binds the sensor *version and placement*, not just the value.** The manifest field records `sensor_versions` and which placement produced each value, so a verifier can reject a value produced by an untrusted placement (e.g. a relay-self-reported `u`).

### 8. Combining the effects into a realized warrant

We turn the per-claim effects into one realized warrant by a **weighted combination, then a clamp**. In plain language: each effect pulls the warrant down by an amount set by a weight; nothing can pull it up.

Define a per-claim **damage-discounted score**:

```
g(c') = u(c')^α  ·  s(c')^β  ·  faith(c')^γ
```

where `faith(c') ∈ {1, 0.5, 0}` is the numeric entailment value, and `α, β, γ ≥ 0` are weights calibrated against human judgment (Experiment E3). The product form matters: if **any** effect is near zero — fabricated, unsupported, or contradicted — the whole score collapses toward zero. A claim is only fully trustworthy if it is used *and* supported *and* not contradicted. (A weighted geometric mean or a min can be substituted; the calibration experiment decides.)

The realized warrant is this score applied to the declared warrant:

```
w^real_k(c') = g(c') · w^decl_k(c')
```

### 9. The safety rule: sensors can only lower warrant, never raise it

This is the single most important equation in Phase 3, and it is what makes the whole thing publishable as *security*, not just ML. The warrant CAPM finally assigns each claim is:

```
w_k(c') = min( w^decl_k(c'),  w^real_k(c') )
```

Because `g(c') ∈ [0,1]`, we always have `w^real ≤ w^decl`, so the `min` is just `w^real` when the sensors fire and `w^decl` when they don't. The point of writing it as a `min` is the guarantee it states:

> **Graded-degrade safety theorem.** For every claim and every hop, `w_k(c') ≤ w^decl_k(c')`. No sensor — however imperfect, fooled, or adversarially manipulated — can raise a claim's warrant above the value CAPM already guarantees. Therefore Phase 3 is *never less secure* than baseline CAPM.

**Where the utility gain actually comes from (this must be stated precisely).** Because `g(c') ≤ 1`, Phase 3 can **never raise any individual claim above its declared warrant** — so it does not "recover utility" relative to the same per-claim declared warrant. That would be a contradiction. The utility gain is entirely about **granularity**: the realistic baseline is not per-claim declared warrant, it is **document-level handling**, where one degraded claim drags the whole document's warrant down (or trips a document-level reject/quarantine), discarding the claims that came through intact. Phase 3 keeps degradation **local to the affected claim**, so the unaffected claims retain their (already-declared) warrant and remain usable instead of being thrown out with the bad one. Stated exactly:

> Phase 3 does not increase any individual claim above CAPM's declared warrant. Its utility gain comes from **localizing degradation per claim** rather than rejecting or down-weighting the entire document. The security side and this utility side are therefore measured on different baselines and reported in separate columns (E3.2): security vs. *per-claim* CAPM, utility vs. *document-level* CAPM.

This mirrors CAPM's existing A3 safe rule and its source-class degrade-on-uncertainty rule exactly. It is the same move, applied to transformations instead of origins. It means even the shaky sensors (influence, attention-trust) are safe to *consult*, because they live under the `min` and can never inflate trust.

### 10. Monotonicity is preserved

CAPM's headline invariant is that warrant never rises across hops. Phase 3 preserves it trivially: at each hop, `w_k(c') = min(w^decl_k, w^real_k) ≤ w^decl_k ≤ w_{k-1}(parent)` (the last step is CAPM's existing monotonicity on the declared warrant). So per-claim warrant is still monotone non-increasing along each lineage thread. **Phase 3 adds a second downward force; it never adds an upward one.** The machine-checked monotonicity lemma from Phase 2 extends to the per-claim case by the same argument.

### 11. What the verifier now does

The external verifier (still outside the model) now, per claim:

1. verifies signatures and the hash-chain (unchanged from CAPM);
2. reads the declared warrant `w^decl` (unchanged);
3. reads the **signed sensor outputs** `u, s, faith` from the new manifest field;
4. recomputes `g(c')` and `w^real`, takes the `min`, and emits **per-claim** accept / down-weight / quarantine.

The recipient receives each surviving claim at its own warrant, plus an explicit warning on any claim that degraded — exactly the advisory example: "Microsoft affected — trustworthy; patch exists — usable but the KB number was lost (evidence loss); *affected platforms* — **do not act, source said Windows 10/11 but the relay says only Windows 7** (contradiction); two of four facts dropped."

### 12. The internal/external divergence detector (heuristic, optional)

As an *auxiliary* signal (not in the security floor), we also compute the model's internal trust estimate (A-Trust-style, over attention features) and compare it to the external warrant. A large gap — the model internally "believes" content that the external warrant says is weakly grounded — is a laundering signature, the fingerprint of the "Lying with Truths" attack where every source is real but coherence has manufactured false confidence. This is reported as a best-effort detector with explicit caveats (attention-faithfulness is contested), never as a guarantee.

---

## PART III — THE SYSTEM TO BUILD (steps in order)

The build is staged so that **each step de-risks the next** and each produces a standalone deliverable. Start where "what is a claim" is trivial — structured sources — and widen later.

### Step 0 — Claim extraction + effect taxonomy on structured sources

**What we do.** Build the spine with no ML yet. (i) A claim extractor for structured inputs — each field of a CVE/API/DB record becomes one claim. (ii) A claim matcher that locates each source claim in the relay's output (exact / numeric / entity match). (iii) An effect tagger that labels every output claim **survived / dropped / distorted / added**.

**What we expect.** The worked advisory example running end to end: four input claims, each tagged with its fate in the output. This alone demonstrates the gap is real and observable — before any probe exists.

**Why first.** It answers the most basic reviewer question ("does this gap even exist and can you see it?") at near-zero cost and risk, and it produces the data structure every later step writes into.

### Step 1 — The probe as the anchor usage-sensor

**What we do.** Obtain or train the AttriWiki probe (logistic regression on the relay model's final-layer hidden states). For each output claim, extract the hidden states of its tokens and get the usage score `u(c')`. Wire it to Step 0's tags:

- in source + probe says context-driven → **survived**, keep warrant;
- in output, not in source, probe says memory-driven → **added/fabricated**, degrade hard;
- in source, missing from output → **dropped**, local degrade.

**What we expect.** A probe-gated per-claim warrant that distinguishes a faithful summary from a memory-substituted one — the core of Contribution 1. The probe is frozen at inference (deterministic, signable, cheap).

**Risks / mitigations.** The probe is trained on Llama/Mistral/Qwen; verify it transfers to your relay models or retrain on AttriWiki (the pipeline is self-supervised, so labels are free). If transfer is weak, that itself is a reportable finding and you retrain per model.

### Step 2 — Support + entailment as the faithfulness sensors

**What we do.** Add (i) calibrated embedding/activation similarity for support scoring `s(c')` (sentence-embedding cosine by default, computable verifier-side; optional activation-space variant) and (ii) a small NLI model for `faith(c')` (entail/neutral/contradict). Now all four effects from the idea note are measured by grounded, auditable sensors. Each writes its value into the per-claim manifest field.

**What we expect.** Evidence-loss detection (support) and contradiction detection (NLI) working on the advisory set — the graded A3 penalty made real (Contribution 2). The genuine-contradiction cases (severity 9.1→"low", Windows 10/11→Windows 7 only, patch→no patch) are now caught explicitly, while valid abstractions (9.1→"Critical") are correctly *not* flagged.

### Step 3 — Manifest integration + verifier check

**What we do.** Define and sign the per-claim realized-provenance field, append it to CAPM's segment, and extend the verifier to **re-derive lineage**, recompute `g`, take the `min`, and emit per-claim verdicts. The signed field:

```
⟨claim_id, claimed_parent_id (hint only), verified_parent_id (verifier-derived),
  usage_score u, support_score s, entailment_label faith,
  effect ∈ {survived,dropped,distorted,added},
  sensor_versions, sensor_placement, hop_signature⟩
```

`claimed_parent_id` is the agent's hint; `verified_parent_id` is what the verifier's deterministic matcher actually derived — and only the verified link drives warrant (§5). `sensor_versions` and `sensor_placement` keep the sensors (and where each ran, per §7a) as a named, versioned, evaluated TCB component — same honesty posture CAPM already uses for the acquisition wrapper. A value whose `sensor_placement` is an untrusted source (e.g. a relay-computed `u`) is rejected by the verifier.

**What we expect.** End-to-end: a multi-hop run where each claim arrives with its own warrant and verdict, damage localized, manifest fully verifiable. This makes Phase 3 *one system* with CAPM, not a bolt-on.

### Step 4 — Influence oracle + divergence detector (off the critical path)

**What we do.** (i) Run NeuroTaint offline over the test traces to get counterfactual influence `v(c')`; use it to validate that the cheap runtime sensors agree with real influence. (ii) Compute the internal/external warrant divergence as the heuristic laundering detector, evaluated against "Lying with Truths."

**What we expect.** A validation result ("our cheap per-claim signals track expensive counterfactual influence at correlation ρ") that pre-empts the reviewer's "does your runtime signal mean anything?" — plus a detector for the truths-only attack CAPM cannot otherwise catch.

### Step 5 — Widen to prose (future-work boundary, scoped honestly)

**What we do.** For free-text sources, replace field-level claim extraction with atomic-claim/proposition decomposition (FactScore-style). Keep everything else identical.

**What we expect.** A demonstration that the architecture generalizes beyond structured data — but the first paper's contribution is fully carried by structured sources, and prose is explicitly framed as the widening frontier.

---

## PART IV — DETAILED EXPERIMENT LIST

Each experiment states: **which step it validates, the question, the method, the comparator, the metric, and the reviewer objection it neutralizes.** Experiments are grouped by the build step they belong to.

### Concrete experimental parameters (fixed once, used by all experiments below)

These numbers make the proposal experimentally grounded rather than abstract. They are starting targets; adjust with justification in the threats ledger, not silently.

- **Corpus.** ≥ 500 source records total: ≥ 300 real CVE advisories (NVD/CISA-KEV feed), ≥ 100 authenticated-API responses (APIs.guru-sampled schemas), ≥ 100 file/DB records. Structured sources only in this phase.
- **Transformations per record.** 6 per record → ≥ 3,000 transformed instances: {faithful-summary, faithful-paraphrase, lossy-summary (omission), contradiction-injected, fabrication-injected (memory-substituted), source-mixing (two sources merged)}.
- **Attack classes (named).** omission, contradiction, fabrication, evidence-loss, source-mixing, paraphrase-laundering, adaptive-optimization (Group F).
- **Hop counts.** 1, 2, 4, 8 (powers-of-two, matching the design doc's chain-length sweep).
- **Relay / probed models.** Exact versions: **Llama-3.1-8B-Instruct, Mistral-7B-Instruct-v0.3, Qwen2.5-7B-Instruct** (the three AttriWiki-validated open-weight models; probe is per-model). A black-box API model (no hidden states) is included to exercise the §7a fallback (NLI+support only).
- **Warrant thresholds.** accept ≥ 0.7; down-weight 0.4–0.7; quarantine < 0.4 — swept ±0.1 in the frontier experiment (E3.2), never a single hand-picked cut.
- **Human labeling.** ≥ 600 claims labeled, ≥ 3 annotators each, report Krippendorff's α / Cohen's κ; target inter-annotator agreement ≥ 0.7 before any weight-fitting.
- **Latency target.** added online cost ≤ 150 ms/claim and ≤ 1 s/hop at the 8-claim advisory size (probe = one frozen linear layer; NLI = small model; influence offline). Report, don't just assert.
- **Statistics.** every ASR / retention number with 95% CIs and paired tests vs. baseline; no claim rests on a single run.

### Group A — Gap existence (validates Step 0)

**E0.1 — Does reasoning-layer laundering occur under valid manifests?**
*Question.* Can a relay produce a cryptographically valid manifest while the content is dropped/contradicted/fabricated?
*Method.* Take real CVE advisories; have relay agents transform them (faithful summaries, lossy summaries, summaries with injected contradictions, memory-substituted rewrites). Run baseline CAPM; record manifest validity and document warrant.
*Comparator.* Baseline CAPM (document-level).
*Metric.* Fraction of laundered outputs that pass CAPM with high warrant.
*Neutralizes.* "Isn't CAPM already enough?" — shows a measurable laundering rate CAPM misses.

**E0.2 — Is the effect taxonomy observable without ML?**
*Question.* Can survived/dropped/distorted/added be assigned reliably on structured sources by matching alone?
*Method.* Hand-label a set of transformed advisories; compare against the rule-based effect tagger.
*Metric.* Tagger-vs-human agreement (Cohen's κ).
*Neutralizes.* "Your effects are fuzzy" — shows they're crisp on structured data.

### Group B — Probe as usage sensor (validates Step 1)

**E1.1 — Does the probe transfer to our relay models?**
*Question.* Does the AttriWiki probe predict context-vs-memory on our models/tasks?
*Method.* Apply released probe; if weak, retrain on AttriWiki; evaluate on held-out, title-disjoint splits.
*Comparator.* Text-only bag-of-words / DeBERTa logistic regression (the paper's own shortcut controls).
*Metric.* Macro-F1; gap over text-only controls (confirms it reads representations, not surface lexical cues).
*Neutralizes.* "The probe is just doing keyword matching" — the text-only control rules this out.

**E1.2 — Does usage separate faithful from memory-substituted claims?**
*Question.* Is `u(c')` low for fabricated claims and high for genuinely-sourced ones?
*Method.* On the advisory set with known fabrications, compare `u` distributions.
*Metric.* AUC of `u` separating fabricated vs. sourced claims.
*Neutralizes.* "Usage isn't actionable" — shows it cleanly separates the cases.

### Group C — Faithfulness sensors (validates Step 2)

**E2.1 — Does support detect evidence loss?**
*Method.* Construct claims where backing evidence is selectively removed; measure `s(c')`.
*Metric.* AUC of `s` detecting evidence-loss cases.

**E2.2 — Does NLI catch genuine contradictions while NOT flagging valid abstraction?**
*Method.* Inject genuine contradictions (severity 9.1→"low"; affected Windows 10/11→"only Windows 7"; patch KB123→"no patch available"; vendor swaps) **and** a control set of valid abstractions that must score `entail` (9.1→"Critical", since CVSS v3.1 maps 9.0–10.0→Critical; "KB123 released"→"a patch exists"). Measure `faith` on both.
*Metric.* Contradiction-detection precision/recall on the genuine set; **false-positive rate on the abstraction control** (must be low — a system that flags valid abstraction as contradiction over-blocks and is wrong).
*Neutralizes.* Both "contradiction is the dangerous case and you can't catch it" *and* the reviewer-caught error "your contradiction examples aren't actually contradictions" — shows the system distinguishes abstraction from contradiction, with a schema-aware numeric rule for the CVSS band so digit→word severity is judged correctly.

### Group D — The headline calibration & utility experiment (validates Steps 2–3; the paper's centerpiece)

**E3.1 — Do the sensors predict human per-claim judgment?**
*Question.* Does `g(c')` agree with humans on which claims to trust?
*Method.* Humans label each transformed claim (survived/dropped/distorted/added + "would you act on this?"). Fit `α,β,γ` to human labels; evaluate on held-out claims.
*Metric.* Sensor-vs-human agreement; calibration curve.
*Neutralizes.* "Your weights are arbitrary" — they're calibrated to humans, with held-out validation.

**E3.2 — The security–utility frontier win (the load-bearing result).**
*Question.* Does claim-level realized warrant keep good claims that document-level CAPM throws away, at equal security?
*Method.* Run attack + benign transformations through (a) baseline CAPM and (b) CAPM+Phase 3. Measure, for both: ASR (laundered claims accepted), and benign-claim retention (good claims still usable after multiple hops).
*Comparator.* Baseline CAPM; plus the strongest Build-C competitor from the design doc.
*Metric.* ASR at equal benign-retention, and benign-retention at equal ASR — the Pareto frontier.
*Neutralizes.* "CAPM is secure only because it distrusts most useful behavior" (the RQ7+ objection) — shows Phase 3 dominates the frontier: same security, more surviving good claims.

**E3.3 — Does damage stay local across hops?**
*Question.* After N hops with one bad transformation, does only the affected claim degrade?
*Method.* Multi-hop chains where one claim is corrupted at hop k; track all claims' warrants downstream.
*Metric.* Fraction of unaffected claims still above usable warrant at the final hop (document-CAPM collapses all; Phase 3 should preserve the rest).
*Neutralizes.* "Laundering defenses over-quarantine" — shows locality.

### Group E — Safety & monotonicity (validates the theorems)

**E4.1 — Can any sensor inflate warrant above baseline?**
*Question.* Under adversarial sensor manipulation, does `w ≤ w^decl` always hold?
*Method.* Adversarially perturb sensor outputs (force `u,s,faith` high on laundered claims); verify the `min` clamp holds.
*Metric.* Count of any warrant exceeding `w^decl` (must be zero, by construction).
*Neutralizes.* "Your ML sensor is a new attack surface that can be fooled into raising trust" — the `min` makes this impossible; worst case is baseline CAPM.

**E4.2 — Is per-claim warrant monotone non-increasing?**
*Method.* Machine-check (extend the Phase 2 lemma) that along every lineage thread `w_k ≤ w_{k-1}`.
*Metric.* Exhaustive check passes.
*Neutralizes.* "Does adding sensors break CAPM's invariant?" — proves it doesn't.

**E4.3 — Can a malicious relay forge a sensor value, or supply a self-serving parent?** *(validates §7a and §5)*
*Question.* Does the verifier reject relay-computed sensor values and re-derive lineage rather than trusting the agent's pointer?
*Method.* (a) Have a malicious relay supply inflated `u/s/faith` with an untrusted `sensor_placement`; confirm the verifier discards them and falls back to verifier-side recompute. (b) Have the relay point a fabricated output claim at a high-support source claim (`claimed_parent_id`); confirm the verifier's matcher derives a different (or null) `verified_parent_id` and degrades.
*Metric.* Rate at which forged sensor values are rejected (target 100% for untrusted placements); rate at which self-serving parents are corrected/degraded; resulting warrant ≤ baseline.
*Neutralizes.* "The signed sensor field and parent pointer are new self-attestation surfaces" — shows both are claimed-not-trusted and re-derived verifier-side.

**E4.4 — Does the §7a fallback hold for black-box (no hidden-state) relays?**
*Question.* With no usage probe available (API relay), does Phase 3 still run and still clamp safely on NLI+support alone?
*Method.* Run the full suite on the black-box API model; confirm `u` is absent, the verdict uses support+NLI, and the `min` guarantee holds.
*Metric.* Coverage/utility with vs. without the probe (quantifies the utility cost of losing `u`); security unchanged.
*Neutralizes.* "Your hidden-state probe assumes white-box access you won't have in deployment" — shows graceful degradation: less utility without the probe, never less security.

### Group F — Influence validation & adaptive attack (validates Step 4)

**E5.1 — Do cheap runtime sensors track expensive counterfactual influence?**
*Question.* Does `g(c')` correlate with NeuroTaint's offline counterfactual influence `v(c')`?
*Method.* Run NeuroTaint offline on the same traces; correlate.
*Metric.* Correlation ρ between `g` and `v`.
*Neutralizes.* "Your runtime signal is a cheap proxy that doesn't mean anything" — shows agreement with the expensive ground truth.

**E5.2 — Does the divergence detector catch the truths-only attack?**
*Question.* On "Lying with Truths"-style inputs (all sources real, false conclusion), does internal/external divergence flag it where warrant alone cannot?
*Method.* Construct truths-only laundering; compare detection by warrant-alone vs. warrant+divergence.
*Metric.* Detection rate of the truths-only attack.
*Neutralizes.* "There's an attack you still can't see" — shows the auxiliary detector covers it (as best-effort).

**E5.3 — Adaptive adversary against the full Phase 3 stack.**
*Question.* Can an attacker who knows the sensors and the warrant rules launder while keeping all signals clean?
*Method.* Design adaptive attacks that optimize content to keep `u,s,faith` high while corrupting meaning; measure residual ASR and characterize what survives.
*Comparator.* Static (non-adaptive) attacks.
*Metric.* Residual ASR under adaptive attack; which claim types remain exploitable.
*Neutralizes.* The mandatory "you only tested static attacks" objection — and an honest residual (ASR > 0) is expected and good, consistent with CAPM's managed-residual posture.

### Group G — Cost (validates Step 3 deployment)

**E6.1 — Runtime and manifest overhead.**
*Question.* What does Phase 3 cost in latency, manifest size, verifier CPU?
*Method.* Measure per-hop probe/support/NLI latency, added manifest bytes per claim, verifier recompute time.
*Metric.* Latency added per hop; manifest growth per claim; verifier CPU.
*Neutralizes.* "This is too expensive to deploy" — quantifies a modest, bounded cost (probe is a frozen linear layer; NLI is small; influence is offline).

---

## PART V — WHAT SUCCESS LOOKS LIKE

Phase 3 succeeds if, together, the experiments show:

1. the gap is real (E0.1) and observable (E0.2);
2. the sensors are grounded, not lexical tricks (E1.1) and actionable (E1.2, E2.1), and distinguish genuine contradiction from valid abstraction (E2.2);
3. they agree with human judgment (E3.1) and with expensive influence ground-truth (E5.1);
4. claim-level handling **beats document-level CAPM on the security–utility frontier by localizing degradation** (E3.2) — security measured vs. per-claim CAPM, utility vs. document-level CAPM — and damage stays local (E3.3);
5. nothing can inflate warrant above baseline (E4.1), forged sensor values and self-serving parents are rejected (E4.3), the black-box fallback holds (E4.4), and monotonicity holds (E4.2);
6. the residual under adaptive attack is honest and bounded (E5.3), at modest, measured cost (E6.1).

The single sentence that states the contribution:

> CAPM verifies the chain was intact; Phase 3 adds per-claim, verifier-auditable evidence about whether each claim is grounded in that chain — measured from the outside, per claim, able only to degrade — turning a coarse document-level guarantee into a graded, localized one. The evidence is probabilistic, so it *attests and detects*; it does not *prove* causal grounding, and it can never inflate trust above what CAPM already guarantees.

---

### Notes / caveats for the team

- The 2026 primitives are recent preprints; verify arXiv IDs, released-artifact availability, and exact numbers before citing in submission. Specifically: the usage probe is from the AttriWiki paper (arXiv:2602.22787); influence auditing is NeuroTaint / "Ghost in the Agent" (arXiv:2604.23374); support scoring is genericized (do **not** brand it "STEERFUSE" — SteerFuse is the secondary training-free method in DataDignity, arXiv:2605.05687, whose primary method is the supervised ScoringModel); A-Trust attention-trust is auxiliary only.
- A-Trust / attention-based internal trust rests on contested ground (the attention-faithfulness debate); keep it strictly auxiliary and clearly caveated.
- Start every experiment on structured sources (CVE/API/DB). Prose decomposition (Step 5) is the widening frontier, not the first paper's load-bearing contribution.
- Exact functional form of `g(c')` (product vs. weighted geometric mean vs. min) is decided empirically by E3.1, not assumed.
