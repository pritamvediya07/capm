# Phase 3 — Threats to Validity (honesty ledger)

Living document. Each experiment appends the assumptions it relies on and the
boundaries of what it shows. Pre-writes the paper's limitations section.

## Corpus
- **Real source data:** CISA-KEV feed (catalog 2026.06.18, 1623 entries). Every
  structured field used (vendor, product, CWE, dates, ransomware-use flag,
  required-action) is a genuine attested value.
- **CVSS deferred:** KEV does not carry the CVSS base score / severity band, and
  NVD's API was unreachable at build time (repeated read timeouts). `cvss_score`
  / `cvss_band` are therefore `None` in the corpus and will be enriched when NVD
  is reachable. **P3-A.1 does not depend on CVSS** (it injects contradictions on
  the real categorical/boolean/identifier/date fields). The CVSS-band
  abstraction-vs-contradiction case (9.1→"Critical" valid vs 9.1→"low" genuine)
  is owned by **P3-C.2**, which will require the enrichment first.

## P3-A.1 — laundering under valid manifests
- **Transformations are programmatic, not LLM-generated.** This is deliberate and
  is the design-doc's intended Step-0 method: programmatic transforms give
  *exact* per-claim ground truth (which load-bearing field was dropped /
  contradicted / fabricated), which is the labelled data the experiment needs.
  LLM-generated laundering is exercised later (relay models in Group B+).
- **The declared label is the attacker's choice, and it is benign by
  construction.** All four transforms declare `summary`/`paraphrase`
  (fidelity-penalty 1 in `capm.core.types`), because a laundering relay does not
  self-declare "I fabricated." That all four labels carry the *same* CAPM penalty
  — hence identical warrant — is a property of the real penalty table, not an
  arrangement of this experiment. The "detection rate = 0" result is therefore a
  structural property of baseline CAPM, not a tuning artefact.
- **Two propagation models reported, not one.** `single_launder_then_relay` (one
  launderer + honest VERBATIM forwarding) is the realistic case and shows the gap
  is hop-independent; `relaunder_each_hop` shows CAPM's only lever (per-hop
  fidelity erosion) eventually quarantines long chains — but it does so for
  faithful content too (Panel A), which is the over-blocking that motivates Phase
  3's per-claim locality (P3-D.3), not laundering detection.
- **WEAK-origin "0% usable" is blanket distrust, not detection.** For a WEAK
  ceiling the single penalty drops warrant to NONE, so *all* content (faithful and
  laundered alike) is quarantined; the matched-pair metric correctly scores this
  as detection = 0.
- **Scope:** structured sources only (CVE/API/DB). Prose decomposition is deferred
  (design-doc Step 5).

## P3-A.2 — effect taxonomy observable without ML
- **Reference labels are the construction oracle, not crowd annotators.** The true
  per-claim effect is known because the generator performed it; this is the gold
  standard, and human labels would only be a noisier proxy for the same truth.
  No human annotators were available. The genuine human-judgment study ("would
  you act on this?") is **P3-D.1** — a different question (trust, not effect).
  Inter-annotator agreement (≥3 annotators, Krippendorff α) is therefore deferred
  to D.1, not claimed here.
- **The matcher assumes labeled field→value structure** ("`<field> is <value>`"),
  which is the design-doc's *structured-sources-first* premise. Field identity is
  resolved from a clause's **subject**, not from any word appearing anywhere in
  the clause (this fixed a real cross-field collision: "Apply updates per *vendor*
  instructions" was being read as a vendor assertion). Free-text fields, which
  lack this structure, are the lowest-agreement type (κ=0.844) — honestly the
  fuzzy edge of "structured".
- **Surface noise is applied** (date re-formatting, CWE re-spacing, boolean
  synonyms) so matching is not a template echo; the `numeric_tolerance` ablation
  shows date agreement collapses κ 1.000→0.047 without it — i.e. the result
  depends on tolerant numeric/date comparison, which is named and measured.
- **Three matcher bugs were found and fixed during this experiment** (whole-text
  value leakage; identifier label-vs-value cue; "Advisory summary:" preamble
  hijacking the subject split). Each was a genuine logic fix, not a label
  adjustment — the κ rose from 0.53→0.93 by correcting the matcher, and the
  residual ~2% disagreement (mostly free-text near-misses) is reported in the
  confusion matrix rather than smoothed away.
- **CVSS-numeric tolerance** (the design-doc's flagship "severity 9.1") is stood in
  for by the real **date** fields, which exercise the identical numeric-tolerance
  path; the genuine CVSS-band case still awaits NVD enrichment (→ P3-C.2).

## P3-B.1 — usage-probe transfer
- **MODEL SUBSTITUTION (the load-bearing caveat).** The design doc names
  Llama-3.1-8B / Mistral-7B / Qwen2.5-7B; none fit this CPU-only box. We
  substitute four small open-weight LMs across **three architectures** —
  distilgpt2, gpt2 (GPT-2), pythia-160m (GPT-NeoX), opt-125m (OPT). This tests the
  *same scientific claim* (a linear probe on answer-token hidden states recovers
  the context-vs-parametric signal, and it is representational) at a scale this
  hardware supports. The 7-8B validation is **GPU future-work**. Crucially, the
  **security guarantee is independent of probe quality**: the probe sits under the
  min-clamp (§9) and can never inflate warrant — a weaker probe lowers utility,
  never security — so the substitution cannot affect any Phase-3 safety result.
- **Self-supervised labels, not the AttriWiki artifact.** We could not obtain the
  AttriWiki dataset/probe; instead we construct context-vs-parametric examples
  from our own real CVE corpus (contextual = answer-bearing advisory; parametric =
  distractor advisory). Labels are free (set by the prompt), matching the
  AttriWiki self-supervised idea. Class balance here is ~1:1 (not AttriWiki's
  3.2:1); we use a balanced-loss LR regardless.
- **Structured data does NOT stress the probe's unique advantage.** An explicit
  answer-in-context overlap oracle scores **macro-F1 = 1.000** — on structured
  sources, grounding is *also* lexically separable (consistent with A.2). So the
  probe is **not uniquely necessary here**; it cleanly beats the *generic*
  text-only controls (BoW 0.257, static-embedding ~0.51) which proves the signal
  is representational/contextual, but its UNIQUE value — detecting grounding when
  lexical overlap fails (paraphrase / implicit support) — is the **prose-extension
  frontier (Step 5)**, not demonstrated on CVE fields. Accordingly usage is
  positioned as the runtime-internal sensor that **complements** verifier-side
  support+NLI, never as a sole gate (matching §7a / §8's `min` product).
- **OOD transfer is partial** (CVE-trained probe → general-knowledge facts:
  macro-F1 0.50–0.70, above the 0.33 chance floor but well below in-domain),
  and **cross-model transfer fails across architectures** (within the GPT-2
  family it partially transfers: gpt2→distilgpt2 = 0.78; cross-architecture ≈
  chance) — so the probe must be **retrained per model**, exactly as the playbook
  anticipated (cheap, self-supervised).

## P3-B.2 — usage separates sourced vs memory-substituted
- **Min-aggregation gives NO advantage here** (and is noisier). We tested the
  playbook's mean-vs-min token aggregation: mean-pool-then-score AUC = 0.926 vs
  min-over-per-token = 0.845. The original hypothesis (min catches a single
  ungrounded token in a mostly-grounded claim) did not bear out on these
  structured claims — even the "mixed" claims separate at ~1.0 under *both*
  aggregations because the invented clause is long enough to move the mean. We
  report mean-pool as the recommended default and do **not** claim a min-agg
  benefit the data does not show.
- **Plausible near-misses are the honest weak spot** (AUC 0.78, below the 0.85
  target, vs 0.99 blatant / 0.93 added / 1.00 mixed). This is the *expected*
  failure mode named in the playbook: a realistic-but-wrong value the model's
  own memory partly endorses raises `u`. It is exactly the residual that
  support+NLI (Group C) and the multi-sensor product `g` exist to cover; `u` is
  never a sole gate (it sits under the `min`-clamp).
- **Same model-substitution caveat as B.1** (small open-weight LMs; 7-8B is GPU
  future-work; security is independent of probe quality).

## P3-C.1 — support detects evidence loss
- **Raw activation-space cosine fails (anisotropy).** The §7b activation-space
  variant (distilgpt2 mean-pooled hidden states) gave AUC 0.225 — cosine
  saturates near 0.99 for *all* pairs (the well-known LM-representation anisotropy
  problem), so it cannot discriminate without whitening/calibration. This is an
  honest negative that **validates the design-doc's choice**: sentence-embedding
  is the load-bearing default (AUC 0.983), activation-space is explicitly
  "not load-bearing". Calibrated activation similarity is future work.
- **Partial evidence is (correctly) not flagged.** Removing half the description
  still leaves backing, so s stays high and partial-strip detection is ~0.06 —
  this is *correct* behaviour (partial support is still support), not a miss; only
  full backing-removal is the evidence-loss case.
- **False-support is real but small here** (distractor sources wrongly ≥ τ:
  0.05). The distractors are other CVE descriptions, mostly dissimilar; a more
  topically-aligned distractor would raise this. The weakness is exactly why §8
  keeps `s` under the `min` with NLI, never as a sole gate — as designed.

## P3-C.2 — NLI contradiction vs valid abstraction
- **Test pairs are constructed, grounded in real values where available.** KEV has
  no CVSS or affected-versions fields, so the CVSS-band and version-scope cases are
  constructed against the *real* CVSS v3.1 schema; vendor cases use real corpus
  vendors. C.2 is a sensor *mechanism* test (can NLI+schema distinguish
  contradiction from abstraction), so constructed premise/hypothesis pairs with
  ground-truth labels are the right instrument. CVSS enrichment from NVD would let
  the same pairs be drawn from live advisories (still pending).
- **The schema rule is necessary and sufficient for the CVSS band cases.** Prose
  NLI scores digit→word severity ("9.1"→"low") as *neutral* (CVSS recall 0.50);
  the schema rule lifts CVSS recall to 1.00 while correctly entailing "9.1"→
  "Critical" (abstraction FPR stays 0.00). Both a small (DeBERTa-v3-xsmall) and a
  mid (RoBERTa-large-MNLI) NLI model gave identical results — the prose cases are
  easy; the band semantics are the schema rule's job, not the model's.

## P3-E (safety & monotonicity)
- **E.1/E.2 are guarantees by construction, not empirical luck.** The clamp
  (`w = min(w_decl, g·w_decl)`, `g` clamped to [0,1]) makes `w ≤ w_decl` and
  monotonicity hold for *any* sensor values; the experiments confirm the
  implementation matches the theorem (60/60 no-inflation incl. NaN/inf/>1/<0/
  negative-weights; 1800/1800 monotone × 3 encodings; 200/200 composition). The
  honest content is the *control*: E.2's non-chained control is only non-monotone
  ~82% of the time (random g sometimes decreases), so we also assert an explicit
  guaranteed-rising control is caught — the checker's soundness, not a 100%
  artefact.
- **E.3 trust model — attestation, not just a placement string.** A relay could
  *claim* `sensor_placement="attested_service"`; the verifier therefore honors a
  `u` only with a valid attestation (modeled as an attestation bit a relay cannot
  set), never on the placement label alone. s/faith are always verifier-recomputed
  from the matcher effect (the A.2 matcher is itself the verifier-side sensor), so
  relay-supplied s/faith are structurally ignored. Positive controls (legit
  attested `u` honored; faithful claim kept) prove it is not blanket rejection.
- **E.4 — the black-box utility cost is ~0 HERE, and that is honest, not evasion.**
  On structured data support+NLI alone catch every attack class (u uniquely
  catches 0/240), so dropping the probe costs no detection — the §7a degradation
  is nearly free. This is the *same* boundary B.1 flagged: the probe's marginal
  value is for non-lexical/prose grounding (Step 5), which structured CVE fields
  do not exercise. We report Δ≈0 rather than manufacturing a loss. The
  load-bearing E.4 result is the security one: **0 warrant inflations** without
  the probe.
- **E.4 used the real sensors** (distilgpt2 probe + MiniLM support + DeBERTa-v3
  NLI); same small-model substitution caveat as B/C applies to the probe.

## P3-D (calibration + frontier + locality)
- **D.1 trust label is a ground-truth ORACLE, not humans** (same substitution as
  A.2). Annotators are SIMULATED (oracle + 12% noise, mean pairwise κ 0.56) to
  exercise the inter-annotator protocol; the real human "would you act?" study is
  deferred. The form-selection (min chosen) and generalization (vendor
  domain-holdout AUC 0.94) results stand on the oracle label. The fitted product
  form put **α(usage)=0** — usage adds no *marginal* trust signal on structured
  data (consistent with B.1/E.4); min (which still includes u) is chosen as
  simplest + best-calibrated.
- **D.2/D.3 baselines collapse to one diagonal.** Document-level and per-claim
  CAPM are both content-blind, so on the claim axes they coincide (accept iff
  w_decl ≥ τ). The Phase-3 win is measured against that content-blind frontier;
  the single-sensor (NLI-only, support-only) competitors are the intermediate
  Build-C comparators.
- **D.3 raw retention is origin-bounded, not a locality failure.** Faithful claims
  from WEAK origins (w_decl=0.30) sit below the usable floor by CAPM's correct
  origin ceiling; the *locality* metric (does the corruption spread to siblings?)
  is isolated and clean — 0 cross-claim contamination, Phase-3 keeps 100% of the
  would-be-usable unaffected claims that document-CAPM must discard.

## P3-F (influence + adaptive)
- **F.2 is an HONEST NEGATIVE (documented limitation).** The auxiliary divergence
  detector does NOT catch the truths-only attack on distilgpt2: pairwise NLI rates
  the true and false synthesis identically (AUC 0.50 — it cannot judge
  multi-premise synthesis), and the hypothesized over-confidence signature is
  INVERTED (AUC 0.004 — the relay is *less* confident in the false conclusion). We
  used an output-confidence proxy for internal trust; the attention-based A-Trust
  variant is contested (§12) and deferred. We promote NOTHING to the guarantee —
  the truths-only attack is the documented residual frontier.
- **F.3 residual is NOT tuned to zero.** At the ACCEPT threshold no adaptive attack
  succeeds (multi-sensor min holds w < 0.7), but the DOWN-WEIGHT residual grows
  with attacker knowledge (0.00 → 0.33 → 0.49) — single-field near-misses that keep
  all sensors moderately high reach 'usable'. This is the measured managed
  residual; the multi-sensor min catches the synthesis attack (low support/usage)
  even though NLI-alone (F.2) does not. Probe-substitution caveat applies.
- **F.1 ρ is positive but g is sharper than v.** g tracks the counterfactual
  influence v at Spearman ρ=0.62; for attack claims v≈0.5 (ablating an
  already-ignored source barely changes logprob) while g→0, so g is the sharper
  detector — the honest boundary is that v measures content influence, not control.

## P3-G (cost)
- **G.1 latencies are CPU, small-model.** 185 ms/claim online is on a CPU box with
  distilgpt2/MiniLM/DeBERTa-v3-xsmall; the probe dominates (124 ms). On the named
  7-8B models with a GPU these change, but the *shape* (probe + small NLI, offline
  oracle off the hot path, ~340 B/claim manifest) holds. A cascade (NLI only on
  cheap-flagged claims) is the noted reduction.
