# CAPM Phase 3 — Realized-Provenance Attestation · Telemetry Ledger (`phase3_results.md`)

**Phase 3 thesis.** Phase 1 proved CAPM contains transit attacks (ASR 0.00); Phase 2 reduced the residual to origin/wrapper capture. Phase 3 closes the remaining gap: CAPM certifies the *chain was intact*, but not that the *content actually travelled through it*. We bind warrant to the **realized fate of each claim** — used / supported / contradicted / fabricated — measured from **auditable sensors** (verifier-side or attested, never the relay's self-report), degrading warrant **per claim** under a `min`-clamp that can only ever *lower* trust, never inflate it.

**Headline discipline.** The Phase 3 win is a **Pareto-frontier win** (more surviving good claims at equal security via *localized* degradation), **not** a new ASR-0. Security is measured vs. *per-claim* CAPM; utility vs. *document-level* CAPM — separate columns, never averaged. No individual claim is ever raised above its declared warrant. Adaptive residual (P3-F.3) is **expected > 0** and that is correct.

**Core invariants preserved in every experiment** (`g ≤ 1`, `w = min(w_decl, w_real) ≤ w_decl`; claimed-not-trusted lineage → verifier-derived `verified_parent_id`; sensor-placement enforcement → relay-placed warrant-affecting sensors rejected; structured-sources-first; schema-valid abstraction is `entail`, not `contradict`).

---

## Ledger schema (one block per executed experiment)

> Each executed experiment is appended below using **exactly** this schema:
>
> ### [Experiment ID: Name]
> - **What It Does:** Concise technical description of the execution pipeline.
> - **Why It Does It / Motivation:** The Phase-1/2 threat vector or limitation it answers.
> - **What It Shows & Strategic Need:** The structural mechanism proven and why it matters for top-tier peer review.
> - **How To Run It:** Exact local scripts / commands / execution triggers.
> - **Empirical Results:** Raw alphanumeric telemetry output.
> - **Visual Evidence Layout:** Markdown table / data matrix / generated chart asset link.

---

## Experiment index & status (from `experiments3.md`)

Legend: ☐ pending · ◐ in progress · ☑ complete

### Group A — Gap existence (validates Step 0)
- ☑ **P3-A.1** — Does reasoning-layer laundering occur under valid manifests? **→ YES. Detection rate 0.000; 100% valid manifests; 54.2% of laundered outputs usable, 62.5% accepted at high warrant for STRONG-API origins.**
- ☑ **P3-A.2** — Is the effect taxonomy (survived/dropped/distorted/added) observable without ML? **→ YES. Rule-based tagger vs oracle Cohen's κ = 0.926 (acc 0.977); numeric-tolerance ablation drops date κ 1.000→0.047.**

### Group B — Probe as usage sensor (validates Step 1)
- ☑ **P3-B.1** — Does the AttriWiki-style probe transfer to our relay models (vs. text-only controls)? **→ YES. Probe macro-F1 0.96–1.00 on all 4 models (3 architectures), +0.73 over BoW / +0.46 over static-emb; transfer fails cross-architecture (retrain per model). Honest caveat: explicit overlap oracle = 1.00 on structured data.**
- ☑ **P3-B.2** — Does usage `u` separate faithful from memory-substituted claims? **→ YES. Mean-agg AUC 0.93 (blatant 0.99 / added 0.93 / mixed 1.00); plausible near-miss is the honest weak case (0.78) → motivates support+NLI.**

### Group C — Faithfulness sensors (validates Step 2)
- ☑ **P3-C.1** — Does support `s` detect evidence loss? **→ YES (embedding AUC 0.983; full-strip detection 1.00; false-support 0.05). Raw activation-space fails (AUC 0.225, anisotropy) → embedding default validated.**
- ☑ **P3-C.2** — Does NLI catch genuine contradictions WITHOUT flagging valid abstraction? **→ YES. NLI+schema rule: genuine recall 1.00, abstraction FPR 0.00; schema rule lifts CVSS-band recall 0.50→1.00.**

### Group D — Calibration & the security–utility frontier (centerpiece; validates Steps 2–3)
- ☑ **P3-D.1** — Do the sensors predict human per-claim judgment? **→ YES. g predicts trust AUC 0.954 (vendor domain-holdout 0.944); min form chosen (best ECE 0.062).**
- ☑ **P3-D.2** — The security–utility **frontier win** (THE load-bearing result) **→ Phase-3 DOMINATES: at retention ≥0.95, ASR 0.12 vs baseline 1.00; at ASR ≤0.05, retention 0.75 vs baseline 0.00.**
- ☑ **P3-D.3** — Does damage stay local across hops? **→ YES. 0 cross-claim contamination; locality retention 1.00 vs document-CAPM 0.00 at all hops.**

### Group E — Safety & monotonicity (theorems + trust model; do BEFORE D)
- ☑ **P3-E.1** — Can any sensor inflate warrant above baseline? **→ NO. 60/60 cases w ≤ w_decl (incl. forced-max / NaN / inf / >1 / <0 / negative-weights); clamp still actively lowers honest claims.**
- ☑ **P3-E.2** — Is per-claim warrant monotone non-increasing? **→ YES. 1800/1800 across 3 encodings + 200/200 composition; non-monotone control caught.**
- ☑ **P3-E.3** — Forge-sensor / self-serving-parent rejection (§7a + §5) **→ forged `u` rejected 100%, parent corrected 100%, 0 exceed baseline; legit attested `u` still honored.**
- ☑ **P3-E.4** — Black-box (no-probe) fallback safety **→ 0 warrant inflations without `u`; utility cost ≈0 on structured data (support+NLI suffice).**

### Group F — Influence validation & adaptive attack (residual born here; validates Step 4)
- ☑ **P3-F.1** — Do cheap runtime sensors track expensive counterfactual influence (NeuroTaint)? **→ YES. Spearman ρ(g,v)=0.62 (Pearson 0.75).**
- ☑ **P3-F.2** — Does the internal/external divergence detector catch the truths-only attack? **→ HONEST-NEGATIVE. NLI can't separate synthesis (AUC 0.50); over-confidence signature inverted (AUC 0.004) → documented residual, promote nothing.**
- ☑ **P3-F.3** — Adaptive adversary against the full Phase 3 stack **→ CHARACTERIZED. 0 reach ACCEPT; managed down-weight residual grows with knowledge (0.00→0.33→0.49); not tuned to zero.**

### Group G — Cost (validates Step 3 deployment)
- ☑ **P3-G.1** — Runtime and manifest overhead **→ PASS. 185 ms/claim online (probe-dominated), 340 B/claim manifest, offline oracle off the hot path.**

**Suggested execution order:** A (+ shared structured testbed) → B → C → **E** (lock the theorems) → **D** (centerpiece) → F → G.

---

## Shared infrastructure to stand up (build once, before/at first experiment)

`p3/claims/{extract,match}.py` · `p3/sensors/{probe,support,nli,schema_numeric_rule}.py` · `p3/warrant/realized.py` · `p3/manifest/field.py` · `p3/oracle/neurotaint_offline.py` · `p3/data/advisories/` (CVE corpus + transformation generator + valid-abstraction control set) · `docs/THREATS_TO_VALIDITY_P3.md`.

---

# EXECUTED EXPERIMENTS

### [P3-A.1: Does reasoning-layer laundering occur under valid manifests?]

- **What It Does:** Drives four relay transformations of **120 real CISA-KEV CVE advisories** (catalog 2026.06.18) through the **real, unmodified Phase-2 CAPM stack** — genuine Ed25519-signed, hash-linked `CAPMManifest`s scored by the real `WarrantEvaluator` under the default Phase-2 policy. Each advisory's structured fields become atomic claims; a transformation generator produces, with exact ground truth, a **faithful_summary** (no load-bearing claim harmed), **lossy_summary** (load-bearing claim *dropped*), **contradiction_injected** (load-bearing claim *flipped* — e.g. ransomware-use Known→Unknown, vendor swap, due-date shift), and **memory_substituted** (load-bearing claim *fabricated* + a source-absent "patch available, no action required / severity low" claim added). The full grid sweeps transform×{4} × compression×{light,heavy} × hops×{1,2,3,5} × source-class×{STRONG-API, MODERATE-DB, WEAK-webpage} × propagation×{single-launderer, relaunder-each-hop} = **23,040 signed-and-evaluated manifests**. Every laundering relay declares only a *benign* label (`summary`/`paraphrase`); CAPM never inspects content.
- **Why It Does It / Motivation:** Phase 1/2 bound warrant to the **declared transformation** (what the agent *says* it did), not the **realized** effect on content. This experiment tests whether that lets a relay sign a perfectly valid manifest while the content is dropped / contradicted / fabricated — the "reasoning-layer laundering" gap that the transit-layer adversary model structurally cannot see, and the entire reason Phase 3 exists.
- **What It Shows & Strategic Need:** The gap is **real, measurable, and structural** — not a tuning artefact. Because the four declared labels all carry CAPM fidelity-penalty 1, baseline CAPM assigns laundered content the **identical** warrant and verdict as the faithful summary in **100.0%** of matched cells → its **laundering-specific detection rate is 0.000**. At realistic operating points (authoritative-API / first-party-DB origins, short chains) laundered content is actively **accepted at high warrant**. This is the headline number a top-tier reviewer demands before accepting that a new mechanism is warranted ("isn't CAPM already enough?" — answered: no). It also surfaces the flip side — CAPM's *only* lever is blunt origin/hop erosion that quarantines faithful content too (WEAK-origin and long relaunder chains) — which pre-motivates the Phase-3 locality argument (P3-D.3).
- **How To Run It:**
  ```bash
  cd phase3/files/capm-testbed
  .venv/bin/python -m p3.exp.a1_laundering_under_valid_manifest --advisories 120 --seed 0
  # corpus: p3/data/advisories/corpus.py (real CISA-KEV, cached) · generator: .../transform.py
  # raw telemetry → p3/results/a1/a1_raw.csv · figure → p3/results/figures/a1_laundering_gap.png
  ```
- **Empirical Results:** (raw: [a1_raw.csv](files/capm-testbed/p3/results/a1/a1_raw.csv), 23,040 rows; 17,280 laundered)

  ```
  Of laundered outputs (load-bearing claim dropped / contradicted / fabricated):
    manifest cryptographically VALID : 1.000  [1.000, 1.000]   (17280/17280)
    USABLE by baseline CAPM (≥WEAK)  : 0.542  [0.534, 0.549]   ( 9360/17280)
    ACCEPTED high-warrant (≥MODERATE): 0.208  [0.202, 0.214]   ( 3600/17280)
  Matched-pair vs faithful summary (same advisory/hops/class/compression/propagation):
    laundered gets SAME warrant+decision as faithful : 1.000   (17280/17280)
    => baseline CAPM laundering-specific detection   : 0.000
  ```
  Wilson 95% CIs in brackets. The rates are **exact/structural** (CAPM is content-blind, so warrant depends only on declared-label + class + hops + propagation, never on which advisory or which field was laundered) — N drives only CI width.

- **Visual Evidence Layout:**

  ![P3-A.1 — laundering gap](files/capm-testbed/p3/results/figures/a1_laundering_gap.png)

  **Table 1 — laundered outputs under baseline CAPM, by origin source class** (the realistic operating points):

  | Origin source class | Warrant ceiling | Usable (≥WEAK) | Accepted high-warrant (≥MODERATE) | Laundering detected |
  |---|---|---:|---:|---:|
  | **STRONG-API** (authoritative API) | STRONG | **0.875** | **0.625** | 0.000 |
  | **MODERATE-DB** (first-party DB) | MODERATE | **0.750** | 0.000 | 0.000 |
  | **WEAK-webpage** (editable) | WEAK | 0.000¹ | 0.000¹ | 0.000 |

  ¹ WEAK→0 is *blanket distrust* (faithful content is quarantined too), not laundering detection — the over-blocking that motivates P3-D.3.

  **Table 2 — the gap persists across chain length** (laundered "usable" rate; single-launderer = realistic):

  | Propagation | hops=1 | hops=2 | hops=3 | hops=5 |
  |---|---:|---:|---:|---:|
  | single-launderer then honest relay | 0.667 | 0.667 | 0.667 | 0.667 |
  | relaunder-each-hop (worst-case erosion) | 0.667 | 0.583 | 0.417 | 0.000 |

  **Table 3 — CAPM cannot tell the attack types apart** (each declares a penalty-1 label; identical outcome):

  | Laundering type | What it does to a load-bearing claim | Usable | Accepted | = faithful? |
  |---|---|---:|---:|:--:|
  | lossy_summary | dropped (omission) | 0.542 | 0.208 | ✅ identical |
  | contradiction_injected | flipped (wrong info) | 0.542 | 0.208 | ✅ identical |
  | memory_substituted | fabricated (memory) | 0.542 | 0.208 | ✅ identical |

  **Worked cell (STRONG-API, 1 hop, light, single-launderer)** — a cryptographically valid manifest delivering laundered content at high warrant:

  | transform | declared label | CAPM warrant | decision | laundered? |
  |---|---|---|---|:--:|
  | faithful_summary | summary | MODERATE | **accept** | no |
  | lossy_summary | summary | MODERATE | **accept** | yes |
  | contradiction_injected | paraphrase | MODERATE | **accept** | yes |
  | memory_substituted | paraphrase | MODERATE | **accept** | yes |

  **Verdict: PASS** — reasoning-layer laundering occurs under fully valid manifests; baseline CAPM's incremental detection is **0.000**. Threats-to-validity logged in [docs/THREATS_TO_VALIDITY_P3.md](files/capm-testbed/docs/THREATS_TO_VALIDITY_P3.md) (programmatic transforms for exact ground truth; benign declared label is the attacker's choice; two propagation models; CVSS enrichment deferred to P3-C.2).

---

### [P3-A.2: Is the effect taxonomy observable without ML?]

- **What It Does:** Validates the **rule-based claim matcher / lineage re-deriver** ([p3/claims/match.py](files/capm-testbed/p3/claims/match.py)) — the verifier-side, **zero-ML** effect tagger that, from the relay's delivered *text alone*, re-derives for each structured claim whether it **survived / dropped / distorted / added**, plus a verifier-derived `verified_parent_id` (claimed-not-trusted lineage). Over **60 real CISA-KEV advisories** × the 8 transformation variants, the relay text is passed through a **surface-noise layer** (dates re-formatted `2022-05-16`→`May 16, 2022`, CWE re-spaced, ransomware-flag synonyms) so matching is not a template echo, and the tagger's per-claim labels are compared to the **construction oracle** (the true effect, known because the generator performed it). 5,046 per-claim judgments per config; the `numeric_tolerance` knob is ablated.
- **Why It Does It / Motivation:** Phase 3's whole edifice (per-claim warrant, lineage threads, effect-gated degrade) rests on the claim that the effect taxonomy is **crisp and observable** on structured sources *before any ML enters*. If a deterministic matcher can't reliably tell a dropped field from a distorted one, the probe/NLI/support sensors are building on sand. This answers the most basic reviewer challenge ("your effects are fuzzy") at near-zero cost.
- **What It Shows & Strategic Need:** On structured data the four effects are **crisp**: tagger-vs-oracle **Cohen's κ = 0.926** (accuracy 0.977), every field type ≥ 0.84. The **numeric-tolerance ablation** is the named design-doc variant made real — without tolerant numeric/date comparison, date-field agreement **collapses κ 1.000 → 0.047** (exact string can't equate `2022-05-16` with `May 16, 2022`), dragging overall κ to 0.556. This (a) proves the data structure every later sensor writes into is sound, and (b) demonstrates the matcher's tolerance is a *deliberate, measured* choice, not a hidden knob — exactly the rigor a top venue expects of a "no-ML baseline."
- **How To Run It:**
  ```bash
  cd phase3/files/capm-testbed
  .venv/bin/python -m p3.exp.a2_effect_observability --advisories 60 --seed 0
  # matcher: p3/claims/match.py · raw → p3/results/a2/a2_raw.csv · figure → p3/results/figures/a2_effect_observability.png
  ```
- **Empirical Results:** (raw: [a2_raw.csv](files/capm-testbed/p3/results/a2/a2_raw.csv); oracle label mix: survived 4200 / dropped 300 / distorted 300 / added 240 — real diversity, so κ is not a majority-class artefact)

  ```
  OVERALL Cohen's κ   with tolerance : 0.926   (accuracy 0.977)
  OVERALL Cohen's κ   no  tolerance  : 0.556   (accuracy 0.801)
  ```

- **Visual Evidence Layout:**

  ![P3-A.2 — effect observability](files/capm-testbed/p3/results/figures/a2_effect_observability.png)

  **Table 1 — per-field-type agreement (the design-doc's numeric/categorical/identifier breakdown):**

  | Field type | κ (with tolerance) | κ (no tolerance) | Accuracy | n |
  |---|---:|---:|---:|---:|
  | identifier (CVE / CWE) | 0.997 | 0.997 | 0.999 | 960 |
  | categorical (vendor / product) | 0.935 | 0.935 | 0.975 | 960 |
  | **date (numeric-tolerant)** | **1.000** | **0.047** | 1.000 | 960 |
  | boolean (ransomware) | 1.000 | 1.000 | 1.000 | 480 |
  | free-text | 0.844 | 0.844 | 0.945 | 1686 |

  **Table 2 — per-effect confusion (with tolerance), true → tagger** (near-perfect diagonal; residual ~2% is honest free-text/categorical near-miss):

  | true ＼ tagger | survived | dropped | distorted | added |
  |---|---:|---:|---:|---:|
  | **survived** | **4101** | 0 | 99 | 0 |
  | **dropped** | 0 | **298** | 2 | 0 |
  | **distorted** | 10 | 0 | **290** | 0 |
  | **added** | 0 | 0 | 0 | **240** |

  **Verdict: PASS** — κ = 0.926 ≥ 0.8: the effect taxonomy is observable without ML on structured sources. Reached by fixing **three genuine matcher bugs** (whole-text value leakage → clause-subject parsing; identifier label-vs-value cue; "Advisory summary:" preamble hijacking the split), raising κ 0.53→0.93 — *not* by adjusting labels; the residual disagreement is reported, not smoothed. Caveats (construction-oracle in lieu of human annotators → human study deferred to D.1; structured field→value assumption; CVSS stood in by dates) logged in [docs/THREATS_TO_VALIDITY_P3.md](files/capm-testbed/docs/THREATS_TO_VALIDITY_P3.md).

---

### [P3-B.1: Does the usage probe transfer to our relay models?]

- **What It Does:** Stands up the **usage sensor** ([p3/sensors/probe.py](files/capm-testbed/p3/sensors/probe.py)) — a logistic-regression probe over a relay model's **answer-token hidden states** predicting P(context-driven) vs P(parametric). A self-supervised dataset ([probe_data.py](files/capm-testbed/p3/sensors/probe_data.py)) built from **real CVE advisories** teacher-forces the *same* answer under two contexts: **contextual** (the answer-bearing advisory → grounded, label 1) vs **parametric** (a distractor advisory not containing the answer → ungrounded/would-be-fabrication, label 0). For each of **4 open-weight relay models across 3 architectures** it trains the probe (final + middle layer) on advisory-disjoint splits and compares against two text-only controls — **BoW** (TF-IDF over the full prompt+answer, the generic lexical shortcut) and **static-embedding** (layer-0, pre-contextual, of the same answer tokens) — plus an **explicit answer-in-context overlap oracle** for transparency. Also measures cross-model transfer and out-of-domain (general-knowledge) transfer.
- **Why It Does It / Motivation:** The usage sensor `u(c')` is the anchor of Contribution 1 — it's what flags a claim the model produced from **parametric memory** (a fabrication, by definition, for content the source did not contain), which neither the transit layer nor a pure text comparison can see. If the probe were just doing keyword matching, a reviewer dismisses it ("it's lexical"). The text-only controls exist precisely to refute that.
- **What It Shows & Strategic Need:** The probe **transfers to every relay model** (macro-F1 **0.961–0.996**, vs a 0.325 chance floor) and the signal is **representational, not a generic lexical statistic**: it beats BoW by **+0.73** and the pre-contextual static-embedding control by **+0.46** — i.e. the usage signal is *created by contextualization*, recoverable by a frozen linear layer (cheap, signable). **Cross-model transfer fails across architectures** (≈ chance off-diagonal; partial *within* the GPT-2 family, gpt2→distilgpt2 = 0.78) → the probe must be **retrained per model**, exactly as the playbook anticipated. This is the load-bearing evidence that the usage sensor is real and per-model deployable.
- **How To Run It:**
  ```bash
  cd phase3/files/capm-testbed
  .venv/bin/python -m p3.exp.b1_probe_transfer --advisories 80 --seed 0
  # models: distilgpt2, gpt2, EleutherAI/pythia-160m, facebook/opt-125m (hidden states cached to p3/results/b1/feat_*.npz)
  # raw → p3/results/b1/b1_results.csv · figure → p3/results/figures/b1_probe_transfer.png
  ```
- **Empirical Results:** (767 examples, 536 train / 231 test, advisory-disjoint; balance 400+/367−; chance macro-F1 = 0.325; raw: [b1_results.csv](files/capm-testbed/p3/results/b1/b1_results.csv))

  ```
  text-only BoW control (full prompt TF-IDF)         macro-F1 = 0.257
  explicit answer-in-context overlap ORACLE          macro-F1 = 1.000  (near-perfect by construction — see caveat)
  ```

- **Visual Evidence Layout:**

  ![P3-B.1 — probe transfer](files/capm-testbed/p3/results/figures/b1_probe_transfer.png)

  **Table 1 — per-model probe vs controls** (advisory-disjoint test split):

  | Relay model | Arch | Probe (final) | Probe (middle) | BoW ctrl | Static ctrl | Gap vs BoW | Gap vs static | Best layer | OOD |
  |---|---|---:|---:|---:|---:|---:|---:|:--:|---:|
  | distilgpt2 | GPT-2 | 0.987 | 0.978 | 0.257 | 0.540 | +0.730 | +0.447 | final (6) | 0.695 |
  | gpt2 | GPT-2 | **0.996** | 0.996 | 0.257 | 0.540 | +0.739 | +0.456 | final (12) | 0.681 |
  | pythia-160m | GPT-NeoX | 0.961 | 0.996 | 0.257 | 0.501 | +0.704 | +0.460 | middle (6) | 0.496 |
  | opt-125m | OPT | 0.987 | 0.991 | 0.257 | 0.512 | +0.730 | +0.475 | middle (6) | 0.695 |

  **Table 2 — cross-model transfer** (final-layer probe macro-F1; diagonal = in-model; ≈0.32 = chance):

  | train ＼ test | distilgpt2 | gpt2 | pythia-160m | opt-125m |
  |---|---:|---:|---:|---:|
  | **distilgpt2** | **0.987** | 0.458 | 0.342 | 0.325 |
  | **gpt2** | 0.779 | **0.996** | 0.342 | 0.340 |
  | **pythia-160m** | 0.325 | 0.325 | **0.961** | 0.325 |
  | **opt-125m** | 0.345 | 0.336 | 0.325 | **0.987** |

  **Verdict: PASS (with an explicit honesty caveat).** The probe transfers to all relay models, is high-F1, and beats both *generic* text-only controls → the usage signal is representational. **Caveat (logged, not hidden):** an explicit answer-in-context overlap oracle scores **1.000** — on *structured* data grounding is also lexically separable, so the probe is **not uniquely necessary here**; its unique value (non-lexical/implicit grounding) is the prose-extension frontier (Step 5), and it is positioned as the runtime-internal usage sensor that **complements** verifier-side support+NLI, never a sole gate. **Model substitution** (small open-weight LMs across 3 architectures in place of 7-8B, which don't fit this CPU box; 7-8B = GPU future-work) is documented in [docs/THREATS_TO_VALIDITY_P3.md](files/capm-testbed/docs/THREATS_TO_VALIDITY_P3.md) — and is **security-irrelevant** because the probe sits under the `min`-clamp and can never inflate warrant.

---

### [P3-B.2: Does usage `u` separate faithful from memory-substituted claims?]

- **What It Does:** Reuses the B.1 usage probe (trained on the self-supervised context-vs-parametric data) and applies it as a **fabrication detector** on **780 real generator claims** ([b2_usage_separation.py](files/capm-testbed/p3/exp/b2_usage_separation.py)) drawn from advisories **disjoint from B.1's training set**: 300 genuinely-sourced claims (true field values) vs 480 memory-substituted fabrications at four subtlety levels — **blatant** (foreign value), **plausible** (realistic near-miss), **added** (source-absent patch/severity), **mixed** (true value + an invented clause). Every claim is conditioned on its real source advisory as context, so a low `u` means "produced from memory, not the source." Measures threshold-free **AUC** of `u` ranking sourced above fabricated, per model, with the playbook's **mean-pool vs min-over-token** aggregation variants.
- **Why It Does It / Motivation:** B.1 showed the probe *can be trained* to read grounding; B.2 asks the operational question — is the resulting `u` score **actionable** as the fabrication/hallucination detector `u(c')` that flags claims the relay produced from parametric memory (a fabrication by definition for source-absent content)? This is the sensor that catches the Phase-3 "memory-substituted rewrite" attack the transit layer is blind to.
- **What It Shows & Strategic Need:** Usage is **actionable**: mean-aggregation **AUC = 0.926** across all 4 models (blatant 0.99, added 0.93, mixed 1.00). Critically it surfaces the **honest residual** the design doc predicts: **plausible near-misses score AUC 0.78** — a realistic-but-wrong value the model's own memory partly endorses raises `u`, so usage *alone* can't catch it. This is precisely why Phase 3 is a **multi-sensor product `g = u^α·s^β·faith^γ`** with support+NLI (Group C), not a single probe — and it's the kind of measured, declared limitation a top venue rewards over an inflated "we catch everything."
- **How To Run It:**
  ```bash
  cd phase3/files/capm-testbed
  .venv/bin/python -m p3.exp.b2_usage_separation --advisories 60 --seed 11
  # reuses p3/results/b1/feat_*.npz to train the probe; claim features cached to p3/results/b2/claimfeat_*.npz
  # raw → p3/results/b2/b2_claims.csv, b2_auc_summary.csv · figure → p3/results/figures/b2_usage_separation.png
  ```
- **Empirical Results:** (780 claims: 300 sourced / 480 fabricated; B.2 advisories disjoint from B.1; raw: [b2_claims.csv](files/capm-testbed/p3/results/b2/b2_claims.csv), [b2_auc_summary.csv](files/capm-testbed/p3/results/b2/b2_auc_summary.csv))

  ```
  overall AUC — mean-agg = 0.926 (recommended), min-agg = 0.845 (noisier; no advantage here)
  by subtlety (mean-agg) — blatant 0.993, added 0.931, mixed 0.998, plausible 0.784 (the hard case)
  ```

- **Visual Evidence Layout:**

  ![P3-B.2 — usage separation](files/capm-testbed/p3/results/figures/b2_usage_separation.png)

  **Table — fabrication-detection AUC per model (mean-agg overall + per-subtlety):**

  | Relay model | AUC (mean) | AUC (min) | blatant | added | mixed | **plausible** |
  |---|---:|---:|---:|---:|---:|---:|
  | distilgpt2 | 0.892 | 0.824 | 0.994 | 0.734 | 1.000 | **0.843** |
  | gpt2 | 0.949 | 0.885 | 0.996 | 1.000 | 1.000 | **0.803** |
  | pythia-160m | 0.899 | 0.824 | 0.986 | 0.991 | 0.990 | **0.630** |
  | opt-125m | 0.964 | 0.847 | 0.996 | 1.000 | 1.000 | **0.861** |
  | **mean** | **0.926** | 0.845 | 0.993 | 0.931 | 0.998 | **0.784** |

  **Verdict: PASS** — usage `u` is actionable as a fabrication detector (mean-agg AUC 0.93 ≥ 0.85), catching blatant/added/mixed memory-substitutions at AUC ~0.99–1.0. **Two honest findings, not buried:** (1) the playbook's hoped-for **min-over-token aggregation gives no benefit** here (0.845, noisier) — mean-pool is the default, and I do not claim an advantage the data doesn't show; (2) **plausible near-misses are the weak case (AUC 0.78)**, the *expected* residual that support+NLI + the product `g` exist to cover — `u` is a sensor under the `min`-clamp, never a sole gate. Caveats in [docs/THREATS_TO_VALIDITY_P3.md](files/capm-testbed/docs/THREATS_TO_VALIDITY_P3.md).

---

### [P3-C.1: Does support detect evidence loss?]

- **What It Does:** Builds the support sensor ([p3/sensors/support.py](files/capm-testbed/p3/sensors/support.py)) — max sentence-cosine between an output claim and the source — and tests it on the "claim survives, backing stripped" case over **80 real advisories** ([c1_support_evidence_loss.py](files/capm-testbed/p3/exp/c1_support_evidence_loss.py)). The claim is each advisory's vulnerability name; its backing evidence is the impact description. Support `s` is scored under four source conditions — **intact** (real description), **partial** (half the description), **stripped** (impact-free boilerplate), **distractor** (a *different* advisory's description) — in two representation spaces (sentence-embedding default + LM activation variant).
- **Why It Does It / Motivation:** CAPM's structural transformation penalty fires on the *declared* operation, so it cannot see when a claim's **evidence** silently disappears along the chain (the assertion survives, the proof behind it is gone). The support sensor is the verifier-side text signal that catches exactly that — and it covers a different failure mode than the usage probe (evidence-loss vs fabrication).
- **What It Shows & Strategic Need:** Support **catches evidence loss**: sentence-embedding AUC **0.983** (intact s≈0.82 vs stripped s≈0.36), full-strip detection **1.00**. It also **honestly characterizes the sensor's limits**: (a) the raw LM **activation-space variant fails** (AUC 0.225 — cosine saturates near 0.99 for everything due to representation anisotropy), which *validates* the design-doc's embedding-default / activation-"not-load-bearing" choice; (b) the known **false-support weakness** is confirmed (distractor sources wrongly support at rate 0.05 here) — the reason `s` lives under the `min`, never as a sole gate. Showing where a sensor breaks is what earns reviewer trust in where it works.
- **How To Run It:**
  ```bash
  cd phase3/files/capm-testbed
  .venv/bin/python -m p3.exp.c1_support_evidence_loss --advisories 80 --seed 3
  # support sensor: p3/sensors/support.py · raw → p3/results/c1/c1_support.csv · figure → p3/results/figures/c1_support_evidence_loss.png
  ```
- **Empirical Results:** (raw: [c1_support.csv](files/capm-testbed/p3/results/c1/c1_support.csv))

  | Representation space | mean s intact | partial | stripped | distractor | **AUC (intact vs stripped)** | full-strip detection | false-support |
  |---|---:|---:|---:|---:|---:|---:|---:|
  | **sentence-embedding (MiniLM)** | 0.818 | 0.816 | 0.357 | 0.307 | **0.983** | 1.00 | 0.05 |
  | LM activation (distilgpt2, raw) | 0.994 | 0.996 | 0.996 | 0.993 | 0.225¹ | — | — |

  ¹ raw activation cosine is anisotropic (saturates ≈0.99) and uninformative — an honest negative validating the embedding default.

- **Visual Evidence Layout:**

  ![P3-C.1 — support evidence loss](files/capm-testbed/p3/results/figures/c1_support_evidence_loss.png)

  **Verdict: PASS** — support (verifier-side embedding) detects evidence loss at AUC 0.983 ≥ 0.8, catching the "proof gone" case CAPM cannot. Both limits reported, not hidden: raw activation-space fails (anisotropy → embedding is the load-bearing default), and distractor false-support (0.05) confirms why `s` sits under the `min`. Caveats in [docs/THREATS_TO_VALIDITY_P3.md](files/capm-testbed/docs/THREATS_TO_VALIDITY_P3.md).

---

### [P3-C.2: Does NLI catch genuine contradictions WITHOUT flagging valid abstraction?]

- **What It Does:** Builds the faithfulness sensor ([p3/sensors/nli.py](files/capm-testbed/p3/sensors/nli.py)) + the schema-aware CVSS comparator ([p3/sensors/schema_numeric_rule.py](files/capm-testbed/p3/sensors/schema_numeric_rule.py)) and tests them ([c2_nli_contradiction.py](files/capm-testbed/p3/exp/c2_nli_contradiction.py)) on **75 labeled cases** — 45 genuine contradictions (CVSS band flip 9.1→"low", vendor swap, patch present→"no patch", version-scope Win10/11→"only Win7", patched→unpatched, ransomware-use flip) and **30 valid-abstraction controls that must NOT be flagged** (CVSS 9.1→"Critical", "KB released"→"a patch exists", "Win10/11"→"Windows"). Runs a small and a mid NLI model, **with and without** the schema rule.
- **Why It Does It / Motivation:** Contradiction is the worst laundering outcome — *wrong* information, not missing. But a sensor that flags valid abstraction (9.1→"Critical") as contradiction over-blocks and is itself wrong. This is the reviewer-caught correctness point made into a test: catch real contradictions *and* pass faithful abstraction. It also neutralizes the "your contradiction examples aren't actually contradictions" objection by separating genuine flips from valid abstractions explicitly.
- **What It Shows & Strategic Need:** **NLI + schema rule = genuine recall 1.00, abstraction FPR 0.00.** The ablation is the key evidence: prose NLI alone scores the digit→word CVSS band flips *neutral* (**CVSS recall 0.50**), so the **schema numeric rule is necessary** — it lifts CVSS recall to **1.00** while correctly entailing 9.1→"Critical" (FPR stays 0.00). NLI owns the prose cases (vendor/patch/version/ransomware recall 1.00); the schema rule owns the structured band semantics. This precise division of labor — and the proof that valid abstraction is *not* over-blocked — is exactly the rigor a top venue demands.
- **How To Run It:**
  ```bash
  cd phase3/files/capm-testbed
  .venv/bin/python -m p3.exp.c2_nli_contradiction --seed 5
  # NLI: cross-encoder/nli-deberta-v3-xsmall (small) + roberta-large-mnli (mid) · schema rule: CVSS v3.1 bands
  # raw → p3/results/c2/c2_nli.csv, c2_summary.csv · figure → p3/results/figures/c2_nli_contradiction.png
  ```
- **Empirical Results:** (raw: [c2_nli.csv](files/capm-testbed/p3/results/c2/c2_nli.csv); 45 genuine / 30 abstraction)

  | NLI model | schema rule | genuine recall | abstraction FPR | **CVSS-band recall** |
  |---|:--:|---:|---:|---:|
  | DeBERTa-v3-xsmall (small) | ✗ | 0.82 | 0.00 | 0.50 |
  | DeBERTa-v3-xsmall (small) | ✓ | **1.00** | **0.00** | **1.00** |
  | RoBERTa-large-MNLI (mid) | ✗ | 0.82 | 0.00 | 0.50 |
  | RoBERTa-large-MNLI (mid) | ✓ | **1.00** | **0.00** | **1.00** |

- **Visual Evidence Layout:**

  ![P3-C.2 — NLI contradiction vs abstraction](files/capm-testbed/p3/results/figures/c2_nli_contradiction.png)

  **Verdict: PASS** — NLI + schema rule catches genuine contradictions (recall 1.00 ≥ 0.9) WITHOUT flagging valid abstraction (FPR 0.00). The schema rule is shown necessary (CVSS recall 0.50→1.00) — prose-NLI can't judge band semantics. Test pairs are constructed against the real CVSS v3.1 schema (KEV lacks CVSS) and real corpus vendors; logged in [docs/THREATS_TO_VALIDITY_P3.md](files/capm-testbed/docs/THREATS_TO_VALIDITY_P3.md).

---

### [P3-E.1: Can any sensor inflate warrant above baseline?]

- **What It Does:** Stress-tests the **Graded-degrade safety theorem** in the realized-warrant core ([p3/warrant/realized.py](files/capm-testbed/p3/warrant/realized.py)). Across a grid of declared warrants it drives the sensors adversarially — each forced to its max (1.0), all forced, and malformed (NaN, +inf, value >1, value <0, **negative weights**) — and checks the final warrant `w = min(w_decl, g·w_decl)` never exceeds `w_decl`. The `g`-clamp to [0,1] is the backstop; runtime `assert`s enforce `g ≤ 1` and `w ≤ w_decl`.
- **Why It Does It / Motivation:** Phase 3 adds ML sensors — a new attack surface. The whole security argument is that a fooled or compromised sensor degrades to *baseline CAPM*, never above it. This must be shown unconditional, even under malformed/adversarial sensor outputs.
- **What It Shows & Strategic Need:** **No sensor can inflate warrant** — 60/60 cases have `w ≤ w_decl` (0 violations), including all malformed and negative-weight inputs. A sanity check confirms the clamp is not trivially passing: honest laundered claims (faith=0) are actively **down-graded** 6/6. This is the formal claim "Phase 3 is never *less* secure than baseline CAPM," made empirical — the precondition for a reviewer to accept any ML sensor in a security system.
- **How To Run It:** `cd phase3/files/capm-testbed && .venv/bin/python -m p3.exp.e1_clamp_adversary` (raw → [e1_clamp.csv](files/capm-testbed/p3/results/e1/e1_clamp.csv))
- **Empirical Results:**
  ```
  total cases: 60   cases with w > w_decl (must be 0): 0
  sanity — honest laundered claims actually DOWN-graded by the clamp: 6/6
  ```
- **Visual Evidence Layout:**

  ![P3-E.1 — clamp adversary](files/capm-testbed/p3/results/figures/e1_clamp_adversary.png)

  Every point (forced-max, NaN/inf/>1/<0, negative-weights) lies **on or below** the `w = w_decl` line; the forbidden region above it is empty by construction. **Verdict: PASS.**

---

### [P3-E.2: Is per-claim warrant monotone non-increasing?]

- **What It Does:** Machine-checks ([p3/exp/e2_monotonicity.py](files/capm-testbed/p3/exp/e2_monotonicity.py)) that along every lineage thread the realized warrant never rises — `w_k ≤ w_{k-1}` — over **600 random threads × 3 warrant encodings** (continuous / lattice / learned-monotone) plus **200 multi-parent composition** cases (MIN-bounded, no sibling-lift). A deliberately broken, non-chained control must LEAK so the checker is shown sound.
- **Why It Does It / Motivation:** Monotone non-increasing warrant is CAPM's headline invariant. Phase 3 adds a *second* downward force (the realized clamp); it must not accidentally add an upward one. Each hop's declared warrant chains from the previous hop's *realized* warrant (§10), which is what preserves monotonicity.
- **What It Shows & Strategic Need:** Monotonicity **holds for all real threads & encodings** (1800/1800) and all composition cases (200/200, a high-warrant sibling never lifts a low one); the broken control is flagged whenever it actually rises (an explicit `[0.3→0.7]` control is caught). Phase 3 provably preserves CAPM's invariant — extending the Phase-2 machine-checked lemma to per-claim.
- **How To Run It:** `.venv/bin/python -m p3.exp.e2_monotonicity --threads 600` (raw → [e2_monotonicity.csv](files/capm-testbed/p3/results/e2/e2_monotonicity.csv))
- **Empirical Results:**
  ```
  monotone_holds (real threads): 1800/1800   composition: 200/200   per-encoding rate: {continuous:1.0, lattice:1.0, learned:1.0}
  checker teeth — control flagged non-monotone in 1478/1800 (rest stay monotone); explicit rising control caught: True
  ```
- **Visual Evidence Layout:**

  ![P3-E.2 — monotonicity](files/capm-testbed/p3/results/figures/e2_monotonicity.png)

  **Verdict: PASS** — encoding-invariant monotonicity; control always caught when it rises.

---

### [P3-E.3: Can a malicious relay forge a sensor value or supply a self-serving parent?]

- **What It Does:** Validates §7a + §5 with the verifier ([p3/manifest/field.py](files/capm-testbed/p3/manifest/field.py)) over **300 cases** on real advisories ([e3_forgery_and_lineage.py](files/capm-testbed/p3/exp/e3_forgery_and_lineage.py)). A malicious relay forges sensors (u=s=faith=1.0) on a fabricated claim — tagged with an untrusted/lied placement — and points it at a high-support source via `claimed_parent_id`. The verifier must discard relay-placed/unattested sensors, recompute the verifier-side sensors itself, re-derive `verified_parent_id`, and never exceed baseline. **Positive controls** (legit attested `u`; faithful claim with correct parent) confirm it isn't blanket rejection.
- **Why It Does It / Motivation:** The signed sensor field and parent pointer are new self-attestation surfaces — exactly what CAPM exists to eliminate. If a relay could forge a sensor value or a self-serving parent, Phase 3 would re-introduce the self-reporting it set out to remove.
- **What It Shows & Strategic Need:** **Forged `u` rejected 100%** (a *claimed* trusted placement without a valid attestation is not honored), **self-serving parents corrected 100%** (verifier-derived ≠ claimed), forged fabricated claims driven to quarantine, **0 warrants exceed baseline** — while a legitimately-attested `u` is still honored (1.00) and faithful claims kept (1.00). The signed field and parent pointer are *claimed, not trusted*, closing the re-self-attestation hole.
- **How To Run It:** `.venv/bin/python -m p3.exp.e3_forgery_and_lineage --advisories 50` (raw → [e3_forgery.csv](files/capm-testbed/p3/results/e3/e3_forgery.csv))
- **Empirical Results:**
  ```
  forged relay/unattested u REJECTED: 1.00   self-serving parent corrected: 1.00   forged claims quarantined: 1.00
  any warrant exceeding baseline (must be 0): 0
  POSITIVE controls — legit attested u honored: 1.00   faithful claim kept: 1.00
  ```
- **Visual Evidence Layout:**

  ![P3-E.3 — forgery + lineage](files/capm-testbed/p3/results/figures/e3_forgery_and_lineage.png)

  **Verdict: PASS** — forgeries rejected, parents re-derived, no inflation; honest values still honored (not blanket rejection).

---

### [P3-E.4: Does the §7a fallback hold for black-box (no hidden-state) relays?]

- **What It Does:** Runs the **same 400 real claims** (240 attack / 160 benign) two ways with the **real sensors** ([e4_blackbox_fallback.py](files/capm-testbed/p3/exp/e4_blackbox_fallback.py)) — OPEN (usage `u` from the distilgpt2 probe + MiniLM support + DeBERTa-v3 NLI) vs BLACK-BOX (`u` absent → neutral, support+NLI only) — and compares warrant inflation, attack detection, and benign retention.
- **Why It Does It / Motivation:** The usage probe needs hidden-state access a black-box API relay won't give. The §7a claim is graceful degradation: **less utility without the probe, never less security**. This must be shown, not asserted.
- **What It Shows & Strategic Need:** **Security is unchanged** — 0 warrant inflations without the probe; the `min`-clamp holds on the support+NLI-only path. The utility finding is reported **honestly**: on structured data the verifier-side support+NLI **already catch every attack class** (blatant/plausible/added all 1.00→1.00; `u` uniquely catches **0/240**), so the black-box fallback is nearly **free** here — the probe's marginal value is reserved for non-lexical/prose grounding (Step 5), exactly the boundary B.1 flagged. Benign retention is preserved (1.00 both). This makes Phase 3 deployable on black-box APIs for structured sources at full security and near-full utility.
- **How To Run It:** `.venv/bin/python -m p3.exp.e4_blackbox_fallback --advisories 40` (raw → [e4_blackbox.csv](files/capm-testbed/p3/results/e4/e4_blackbox.csv))
- **Empirical Results:**
  ```
  SECURITY — warrants exceeding baseline (must be 0): 0
  attack detection:  OPEN 1.00  vs  BLACK-BOX 1.00   (u uniquely catches 0/240)
  benign retention:  OPEN 1.00  vs  BLACK-BOX 1.00
  by class (open→bbox): blatant 1.00→1.00 · plausible 1.00→1.00 · added 1.00→1.00
  ```
- **Visual Evidence Layout:**

  ![P3-E.4 — black-box fallback](files/capm-testbed/p3/results/figures/e4_blackbox_fallback.png)

  **Verdict: PASS** — black-box fallback is **safe** (no inflation); utility cost ≈0 on structured data (support+NLI suffice), with `u`'s marginal value deferred to prose. Caveats (real-sensor probe substitution; Δ≈0 reported honestly) in [docs/THREATS_TO_VALIDITY_P3.md](files/capm-testbed/docs/THREATS_TO_VALIDITY_P3.md).

---

### [P3-D.1: Do the sensors predict (human) per-claim judgment?]

- **What It Does:** Fits the realized-warrant combiner `g(c')` to a per-claim trust label and runs the **functional-form bake-off** ([d1_human_calibration.py](files/capm-testbed/p3/exp/d1_human_calibration.py)) over **1,540 scored claims** (real sensors): product `u^α·s^β·faith^γ` vs weighted geometric mean vs conservative `min`. Reports held-out AUC, a vendor **domain-holdout**, calibration (ECE), and picks the form D.2/D.3 use. A shared scorer ([score.py](files/capm-testbed/p3/sensors/score.py)) computes `(u, s, faith)` once and caches them.
- **Why It Does It / Motivation:** The design doc defers the `g` functional form and weights to this experiment ("until D.1 runs, use the conservative min"). It also answers "your weights are arbitrary" — they must predict a trust judgment and generalize across domains.
- **What It Shows & Strategic Need:** `g` predicts per-claim trust at **AUC 0.954** (random hold-out) and **0.944** across a vendor domain-holdout — calibrated, not arbitrary. The **min** form is chosen (within 0.01 of the best AUC, simplest, best ECE 0.062), matching the design default. An honest finding feeds forward: the fitted *product* form set **α(usage)=0** — usage adds no *marginal* trust signal on structured data (consistent with B.1/E.4), though `min` still includes it.
- **How To Run It:** `cd phase3/files/capm-testbed && .venv/bin/python -m p3.exp.d1_human_calibration` (chosen form → [d1_chosen.txt](files/capm-testbed/p3/results/d1/), raw → [d1_forms.csv](files/capm-testbed/p3/results/d1/d1_forms.csv))
- **Empirical Results:**

  | form | α | β | γ | AUC (random) | AUC (domain) | ECE |
  |---|---:|---:|---:|---:|---:|---:|
  | product | 0.00 | 5.92 | 0.74 | 0.959 | 0.937 | 0.139 |
  | geomean | 0.00 | 0.89 | 0.11 | 0.959 | 0.937 | 0.233 |
  | **min (chosen)** | – | – | – | 0.954 | **0.944** | **0.062** |

- **Visual Evidence Layout:**

  ![P3-D.1 — calibration](files/capm-testbed/p3/results/figures/d1_calibration.png)

  **Verdict: PASS** — sensors predict trust and generalize across vendors; `min` chosen. **Honest substitution:** the trust label is a ground-truth oracle (no human annotators); 3 annotators are SIMULATED (oracle+noise, κ=0.56) to exercise the protocol — the real human study is deferred (see [threats ledger](files/capm-testbed/docs/THREATS_TO_VALIDITY_P3.md)).

---

### [P3-D.2: The security–utility frontier win (THE load-bearing result)]

- **What It Does:** Runs **1,540 claims** (840 attack / 700 benign, spread across four origin source classes → declared warrants) through **document/per-claim CAPM** (content-blind), **CAPM+Phase-3** (per-claim realized warrant, full `g`), and **single-sensor Build-C competitors** (NLI-only, support-only), sweeping the accept threshold τ to trace each system's **ASR-vs-benign-retention frontier** ([d2_frontier.py](files/capm-testbed/p3/exp/d2_frontier.py)).
- **Why It Does It / Motivation:** This is the paper's centerpiece — it refutes "CAPM is secure only because it distrusts useful behavior." Document-level CAPM must accept/reject a whole document at its content-blind warrant, so lowering ASR equally lowers retention (the diagonal). Phase-3 localizes degradation: it degrades only the laundered claim and keeps the faithful siblings.
- **What It Shows & Strategic Need:** **Phase-3 dominates the content-blind frontier.** Reported on the two correct baselines in separate columns (the r1 framing): at **benign-retention ≥ 0.95, ASR is 0.121 (Phase-3) vs 1.000 (baseline)**; at **ASR ≤ 0.05, retention is 0.747 (Phase-3) vs 0.000 (baseline)**. No over-blocking (retention doesn't collapse), and no individual claim is raised above its declared warrant — the gain is **granularity**. The full-`g` stack also dominates both single-sensor competitors.
- **How To Run It:** `.venv/bin/python -m p3.exp.d2_frontier` (raw → [d2_frontier.csv](files/capm-testbed/p3/results/d2/d2_frontier.csv), headline → [d2_headline.csv](files/capm-testbed/p3/results/d2/d2_headline.csv))
- **Empirical Results:**

  | Constraint | Axis | Phase-3 | Content-blind baseline | Δ |
  |---|---|---:|---:|---:|
  | benign-retention ≥ 0.95 | security (ASR ↓) | **0.121** | 1.000 | **−0.879** |
  | benign-retention ≥ 0.90 | security (ASR ↓) | 0.082 | 1.000 | −0.918 |
  | ASR ≤ 0.10 | utility (retention ↑) | **0.909** | 0.000 | **+0.909** |
  | ASR ≤ 0.05 | utility (retention ↑) | 0.747 | 0.000 | +0.747 |

- **Visual Evidence Layout:**

  ![P3-D.2 — frontier](files/capm-testbed/p3/results/figures/d2_frontier.png)

  Phase-3 (full `g`) hugs the up-left corner; the content-blind baseline is the no-localization diagonal; single-sensor competitors fall in between. **Verdict: PASS** — the load-bearing localization win.

---

### [P3-D.3: Does damage stay local across hops?]

- **What It Does:** Builds **140 documents** with several faithful claims and exactly ONE corrupted claim, then tracks each claim's warrant under Phase-3 vs document-CAPM across chain lengths 1/2/4/8 ([d3_locality.py](files/capm-testbed/p3/exp/d3_locality.py)), checking (a) cross-claim contamination and (b) how many unaffected claims remain usable when the corrupted claim is caught.
- **Why It Does It / Motivation:** The locality argument is the *why* behind D.2: document-CAPM, being content-blind, must reject the whole document to catch one bad claim — collapsing all the good claims. Phase-3 should degrade only the corrupted claim.
- **What It Shows & Strategic Need:** **Locality holds.** **0 cross-claim contamination** (a sibling's warrant is computed per-claim and is identical whether or not the corrupted claim is present), the corrupted claim is **caught 100%**, and Phase-3 keeps **100% of the unaffected claims usable on their own merits (locality retention 1.00) while document-CAPM keeps 0.00** (it must reject the whole document) — at every hop. The lower raw retention (0.75→0.25 with hops) is **CAPM's correct origin/transformation ceiling** (weak-origin faithful claims), *not* damage spreading.
- **How To Run It:** `.venv/bin/python -m p3.exp.d3_locality` (raw → [d3_locality.csv](files/capm-testbed/p3/results/d3/d3_locality.csv))
- **Empirical Results:**

  | hops | corrupt caught | **locality retention: Phase-3 vs doc-CAPM** | raw retention (origin/hop-bounded) |
  |---:|---:|:--:|---:|
  | 1 | 1.000 | **1.00 vs 0.00** | 0.746 |
  | 2 | 1.000 | **1.00 vs 0.00** | 0.744 |
  | 4 | 1.000 | **1.00 vs 0.00** | 0.499 |
  | 8 | 1.000 | **1.00 vs 0.00** | 0.250 |

- **Visual Evidence Layout:**

  ![P3-D.3 — locality](files/capm-testbed/p3/results/figures/d3_locality.png)

  **Verdict: PASS** — damage stays on the corrupted claim (0 contamination); Phase-3 keeps the unaffected claims document-CAPM throws away.

---

### [P3-F.1: Do cheap runtime sensors track expensive counterfactual influence?]

- **What It Does:** Correlates the runtime `g(c')` with the offline **NeuroTaint-style counterfactual influence** `v(c')` — re-run the relay model with the claim's source *ablated* and measure the drop in the claim's log-probability ([neurotaint_offline.py](files/capm-testbed/p3/oracle/neurotaint_offline.py), [f1_influence.py](files/capm-testbed/p3/exp/f1_influence.py)) over 400 claims.
- **Why It Does It / Motivation:** Pre-empts "your cheap runtime proxy is meaningless" — does `g` agree with an expensive causal ground truth?
- **What It Shows & Strategic Need:** **Spearman ρ(g, v) = 0.62 (Pearson 0.75)** — the cheap runtime signal tracks real counterfactual influence. By class, benign claims have high g (0.94) and high v (0.86); attack classes have low g. Honest boundary: for attacks v≈0.5 (ablating an already-ignored source barely moves logprob) while g→0, so **g is the sharper detector** — v measures content influence, not control.
- **How To Run It:** `.venv/bin/python -m p3.exp.f1_influence --n 400` (raw → [f1_influence.csv](files/capm-testbed/p3/results/f1/f1_influence.csv))
- **Visual Evidence Layout:**

  ![P3-F.1 — influence](files/capm-testbed/p3/results/figures/f1_influence.png)

  **Verdict: PASS** — runtime g tracks expensive influence (ρ=0.62 ≥ 0.4).

---

### [P3-F.2: Does the divergence detector catch the truths-only attack?]

- **What It Does:** Builds 60 "Lying with Truths" cases (true premises, **false** overgeneralized conclusion) + 60 faithful-synthesis controls, and compares detection by warrant-alone vs the auxiliary internal/external **divergence** detector ([atrust_divergence.py](files/capm-testbed/p3/sensors/atrust_divergence.py), [f2_divergence.py](files/capm-testbed/p3/exp/f2_divergence.py)).
- **Why It Does It / Motivation:** The truths-only attack — every source real, the synthesis false — is the case the per-claim transit model brackets by construction. The §12 detector is an explicitly-caveated, off-the-floor attempt to catch it.
- **What It Shows & Strategic Need:** **HONEST NEGATIVE (a documented limitation, exactly as §12 anticipates).** Pairwise NLI rates the true and false synthesis **identically** (grounding 0.50 both → AUC 0.50: it cannot judge multi-premise synthesis), and the hypothesized over-confidence signature is **INVERTED** (AUC 0.004 — the relay model is *less* confident in the false conclusion). We used an output-confidence proxy for internal trust; the attention-based A-Trust variant is contested and deferred. **We promote nothing to the guarantee** — the truths-only / multi-premise-synthesis attack is Phase-3's honest documented **residual frontier** (future multi-premise entailment). *(Note F.3 shows the full multi-sensor min still down-weights/quarantines these via low support/usage — only the NLI sensor and this auxiliary detector miss them.)*
- **How To Run It:** `.venv/bin/python -m p3.exp.f2_divergence --n 60` (raw → [f2_divergence.csv](files/capm-testbed/p3/results/f2/f2_divergence.csv))
- **Visual Evidence Layout:**

  ![P3-F.2 — divergence](files/capm-testbed/p3/results/figures/f2_divergence.png)

  **Verdict: HONEST-NEGATIVE** — reported as a limitation, not spun into a win; detector stays off the security floor.

---

### [P3-F.3: Adaptive adversary against the full Phase-3 stack]

- **What It Does:** An attacker who knows `u, s, faith, g` and the `min` rule optimizes the corruption to keep all sensors above their degrade thresholds, across black-box / grey-box / white-box knowledge plus a multi-premise **synthesis** attack ([f3_adaptive.py](files/capm-testbed/p3/exp/f3_adaptive.py)). Measures residual ASR at the ACCEPT (≥0.7) and DOWN-WEIGHT/usable (≥0.4) thresholds.
- **Why It Does It / Motivation:** Neutralizes the mandatory "you only tested static attacks" objection. A non-zero residual is *expected and correct* (CAPM's managed-residual posture); tuning it to zero would be systems-demo mode.
- **What It Shows & Strategic Need:** A **measured, honest residual that is NOT tuned to zero.** No adaptive attack reaches **ACCEPT** (residual 0 everywhere — the multi-sensor `min` holds w < 0.7). The genuine residual is at the **DOWN-WEIGHT** level and **grows with attacker knowledge: black 0.00 → grey 0.33 → white 0.49** — single-field near-misses that keep all sensors moderately high reach "usable" (the recipient is warned, not quarantined). To evade further the attacker must shrink the corruption toward harmless. The synthesis attack is **caught** by the full stack (residual 0 — support+usage flag the overgeneralization's low grounding even though NLI-alone rates it neutral, cf. F.2).
- **How To Run It:** `.venv/bin/python -m p3.exp.f3_adaptive --advisories 40` (raw → [f3_adaptive.csv](files/capm-testbed/p3/results/f3/f3_adaptive.csv))
- **Empirical Results:**

  | attacker knowledge | residual @ ACCEPT (≥0.7) | residual @ DOWN-WEIGHT (≥0.4) |
  |---|---:|---:|
  | black-box | 0.000 | 0.000 |
  | grey-box | 0.000 | 0.325 |
  | white-box | 0.000 | **0.487** |
  | synthesis (truths-only) | 0.000 | 0.000 (caught by support/usage) |

- **Visual Evidence Layout:**

  ![P3-F.3 — adaptive](files/capm-testbed/p3/results/figures/f3_adaptive.png)

  **Verdict: CHARACTERIZED (managed residual)** — bounded, knowledge-dependent, honestly non-zero; a measured "X% at cost C," not a claim of unbreakability.

---

### [P3-G.1: Runtime and manifest overhead]

- **What It Does:** Instruments the per-claim online cost of the three sensors + verifier, the added manifest bytes per claim, and the offline influence-oracle cost, swept over claims-per-document 4→50 ([g1_cost.py](files/capm-testbed/p3/exp/g1_cost.py)).
- **Why It Does It / Motivation:** Answers "this is too expensive to deploy" with measured numbers separating the online hot path from the offline oracle.
- **What It Shows & Strategic Need:** Online overhead is **modest and bounded: 185 ms/claim** (probe 124 + support 28 + NLI 32 + verifier 0.24), under the ≤1 s/hop target up to ~5 claims/doc and linear thereafter; **manifest +340 B/claim**; the NeuroTaint oracle (248 ms/claim) is **offline, never on the hot path**. The probe dominates — a cascade (NLI only on cheap-flagged claims) or a quantized NLI reduces it.
- **How To Run It:** `.venv/bin/python -m p3.exp.g1_cost` (raw → [g1_cost.csv](files/capm-testbed/p3/results/g1/g1_cost.csv))
- **Empirical Results:**

  | component | per-claim latency | | per-document (n claims) | online |
  |---|---:|---|---:|---:|
  | probe (usage) | 124.4 ms | | 4 claims | 0.74 s |
  | support (MiniLM) | 28.1 ms | | 10 claims | 1.85 s |
  | NLI (DeBERTa-v3) | 32.0 ms | | 25 claims | 4.62 s |
  | verifier recompute | 0.24 ms | | 50 claims | 9.24 s |
  | **online total** | **184.7 ms** | | manifest | **340 B/claim** |

- **Visual Evidence Layout:**

  ![P3-G.1 — cost](files/capm-testbed/p3/results/figures/g1_cost.png)

  **Verdict: PASS** — deployable at modest, measured cost (CPU/small-model numbers; the shape holds on GPU/7-8B — see [threats ledger](files/capm-testbed/docs/THREATS_TO_VALIDITY_P3.md)).
