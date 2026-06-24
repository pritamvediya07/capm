# Phase-3 Independent Verification Report

**Scope.** Independent re-run and code/data audit of CAPM Phase-3 (realized-provenance attestation). Covers deterministic reproduction of six headline experiments against the ledger (`phase3_results.md`), plus an integrity audit of all seven experiment groups (A–G) against source code, raw CSVs, and the threats-to-validity documentation.

**Testbed root.** `/home/kenny/Desktop/kenny/phase3/files/capm-testbed`
**Ledger under test.** `/home/kenny/Desktop/kenny/phase3/phase3_results.md`

---

## 1. Verdict

**Phase-3 holds up to independent scrutiny, with corrections required.** The core security thesis — *no sensor can inflate a claim's warrant above its declared baseline; warrant degrades per-claim under a `min`-clamp that can only lower trust* — is sound, reproduces exactly, and is a genuine by-construction guarantee (verified in code, not just asserted). Every deterministic experiment re-run matched the ledger to the reported precision. The load-bearing results (E.1/E.2 no-inflation + monotonicity, D.2/D.3 localized-degradation Pareto win, A.1 content-blindness, A.2 effect observability) are real and honestly framed.

However, the verification confirmed **seven material findings** that survived adversarial re-checking: one HIGH-severity circular-leakage defect (D.1 calibration), four MEDIUM issues (A.1 stale table cells, D.3 tautological contamination check, F.1 label-driven correlation overclaim), and several LOW issues (D.2 competitor-dominance overclaim, E.4 oracle-premise nit, F.3 sensor-attribution mislabel). None of these overturns a PASS verdict on the security guarantee, but two of them (D.1 leakage, D.3 self-comparison) mean specific *secondary* claims are not supported by the evidence offered, and one (A.1) is a concrete published-table numerical error. These must be corrected or caveated before the results are presented as final.

---

## 2. Reproduction (deterministic re-runs vs ledger)

All six experiments below were re-run from the testbed root with the documented commands. Every reported figure matched the ledger; no numerical discrepancies were found in any deterministic re-run.

| Exp                                                                      | Match           | Key reproduced figures                                                                                                                                                                                                                                                                                    | Notes                                                                                                                                                                                      |
| ------------------------------------------------------------------------ | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **P3-E.1** Clamp adversary / graded-degrade safety                 | **match** | 60 total cases; cases with `w > w_decl` = **0** (incl. forced-max / NaN / inf / >1 / <0 / negative-weights); honest laundered claims down-graded **6/6**; PASS                                                                                                                              | `exceeds_decl` is False for every case. Deterministic, clean run. Ledger lines 47, 323–336 identical.                                                                                   |
| **P3-E.2** Per-claim warrant monotonicity (machine-checked)        | **match** | monotone_holds (real threads)**1800/1800** (0 failures); composition **200/200**; per-encoding rate continuous/lattice/learned = 1.0/1.0/1.0; checker teeth: non-chained control flagged non-monotone **1478/1800**; explicit `[0.3→0.7]` rising control caught **True**; PASS | Ran `--threads 600` (×3 encodings = 1800). Even the non-obvious checker-teeth count reproduces exactly. Ledger lines 342–357.                                                          |
| **P3-A.2** Effect-taxonomy observability without ML                | **match** | 60 CISA-KEV advisories (catalog 2026.06.18); overall Cohen's κ**0.926** (acc 0.977) with tolerance, **0.556** (acc 0.801) without; date κ ablation **1.000 → 0.047**; all five per-field rows and full 4×4 confusion matrix identical; PASS (κ ≥ 0.8)                             | Used `--advisories 60`; results deterministic. Ledger lines 139–180.                                                                                                                    |
| **P3-D.1** Sensor→trust calibration + functional-form bake-off    | **match** | claims**1540** (700 trust=1 / 840 trust=0); simulated κ 0.560; product β=5.92 AUC 0.959/0.937 ECE 0.139; geomean β=0.89 AUC 0.959/0.937 ECE 0.233; **min (chosen)** AUC **0.954/0.944** ECE **0.062**; PASS                                                                                      | Numbers reproduce exactly.**See §3 finding D.1 — the headline AUC is circular and the PASS verdict's "calibrated" claim is not supported.** Ledger lines 402–420.                 |
| **P3-D.2** Security–utility frontier (localization win)           | **match** | claims 1540 (840 attack / 700 benign), g=min; retention ≥0.95 → ASR**0.121** vs baseline 1.000; ≥0.90/0.80 → 0.082; ASR ≤0.10 → retention 0.909; ≤0.05 → **0.747** vs 0.000; ≤0.00 → 0.746; PASS                                                                                    | Headline dominance over the content-blind baseline is real.**See §3 finding D.2 — the "dominates both single-sensor competitors" framing is an overclaim.** Ledger ~lines 43, 424. |
| **P3-D.3** Locality — damage stays on corrupted claim across hops | **match** | 140 documents; cross-claim contamination**0**; per hop (corrupt caught / locality Phase3 vs doc-CAPM / raw retention): hop1 1.000/1.000 vs 0.000/0.746; hop2 …/0.744; hop4 …/0.499; hop8 …/0.250; PASS                                                                                           | All values exact.**See §3 finding D.3 — the "0 contamination" sub-metric is a self-comparison tautology, not a measurement.** Ledger lines 447–466.                               |

**Reproduction conclusion:** 6/6 deterministic re-runs matched the ledger exactly. No run-to-run number mismatch was observed in the experiments that were re-executed. (One trivial sampling-noise difference — C.1 activation AUC 0.222 in CSV vs 0.225 in ledger — was noted by the Group-C audit but not re-run here; same conclusion either way.)

---

## 3. Confirmed issues by severity

These findings survived adversarial verification (re-derivation from raw CSVs and/or direct code inspection). Severities are the *corrected* severities after mitigation review.

### HIGH

**D.1 — Circular label leakage in human-calibration AUC.**
The "calibration AUC 0.954" is circular. The trust label is constructed as `trust = 1 iff effect=="survived"`, i.e. `iff value==true_value` (`p3/sensors/score.py:104`). The `faith` feature is `NLI(premise, claim)` where the premise is a *synthesized ground-truth sentence* built from `true_value` (`score.py:54–55`: `premise = "The {field} is {true_value}."`), not the source document. So one of the three input features is a deterministic function of the same `value==true_value` condition that defines the label.

- *Data confirmation* (`p3/results/scored_claims.csv`, 1540 rows): all 700 trust=1 rows have `faith=1.0`, zero exceptions (FN=0). Faith-alone AUC vs trust = 0.966; `min(u,s,faith)` AUC = 0.999. The headline 0.954 is dominated by this leaked feature.
- *What the ledger does / does not disclose:* it honestly and prominently flags that the trust label is an **oracle** (`effect==survived`) and that annotators are simulated. It does **not** disclose that the `faith` feature is itself derived from `true_value` — the label's defining quantity. A reader of the caveat still believes the three sensors are independent measurements predicting the oracle; that is false for `faith`.
- *Why HIGH and not critical:* the oracle nature is disclosed and the numbers are not fabricated; and the conclusion's *direction* is not pure artefact — dropping the leaked feature, `u+s` alone reach logistic AUC 0.986 (s-alone 0.909) computed on real source text, so the sensors do carry genuine fidelity signal. The experiment is also explicitly framed as a placeholder for a future real human "would-you-act" study.
- **Fix needed:** (a) Compute the `faith` feature against the source/rendered document (`ctx`), not a synthesized `true_value` premise, OR (b) report calibration only on `u+s` (the non-leaked features), OR (c) replace the construction-oracle label with a label not derivable from `true_value`. At minimum, add an explicit caveat that `faith` is derived from the label's defining quantity, and retract the "calibrated, not arbitrary / generalizes across a domain-holdout" claim, which the leaked metric cannot support.

### MEDIUM

**A.1 — Stale, unreproducible cells in Table 2 (relaunder row).**
`phase3_results.md:116` publishes relaunder-each-hop usable rates of `0.667 | 0.583 | 0.417 | 0.000` for hops 1|2|3|5. Recomputed directly from `p3/results/a1/a1_raw.csv` using the experiment's own logic (laundered rows, `propagation=relaunder_each_hop`, grouped by hops, mean of `usable_by_capm`), the actual values are **`0.667 | 0.667 | 0.333 | 0.000`**. Cells hop2 (0.583→0.667) and hop3 (0.417→0.333) are wrong.

- Because every `(source_class, hops, propagation)` cell is a single constant (the grid is content-blind by design), the cross-class mean can only be a multiple of 1/3 (0.000/0.333/0.667/1.000). The published 0.583 (7/12) and 0.417 (5/12) are mathematically unachievable from any grouping of this grid — almost certainly a stale row from an earlier hop/penalty configuration. A tree-wide grep finds 0.583/0.417 only in an unrelated b3 CSV, never in any a1 artifact.
- Headline numbers (manifest-valid 1.000, usable 0.542, detection 0.000) and the qualitative monotonic-erosion story are unaffected; the companion single-launderer row (line 115) matches the CSV exactly.
- **Fix needed:** regenerate Table 2's relaunder row from the current CSV to `0.667 | 0.667 | 0.333 | 0.000`.

**D.3 — "0 cross-claim contamination" is a self-comparison tautology, not a test.**
`p3/exp/d3_locality.py:70–72` builds `w_benign`, then `w_benign_nocorrupt = list(w_benign)` (a copy of the same list), then sums `abs(a-b)>1e-9` over `zip(w_benign, w_benign_nocorrupt)`. Zipping a list against its own copy makes every diff exactly 0 by construction. There is no separate code path that re-derives sibling warrants from a corruption-free document, so this guard could not detect a contamination bug even if one existed. This vacuous value is printed as an empirical measurement ("must be 0 — per-claim independence"), gates a PASS condition (line 110), and is repeated as a finding in `docs/THREATS_TO_VALIDITY_P3.md:202`.

- *Why MEDIUM not HIGH:* the asserted property is actually **true by design** — `p3/warrant/realized.py` shows the benign warrant depends only on each claim's own `(u,s,faith)` and a document-level declared warrant, with no cross-claim term — so no false scientific claim is made, just a vacuously-tested true one. The substantive locality headline (corrupt caught 1.0, phase3 locality 1.0 vs doc-CAPM 0.0, raw retention 0.746→0.250) is computed from real scored data.
- **Fix needed:** either actually re-derive sibling warrants in a corruption-free document and compare (a real independence test), or relabel the metric as a *by-construction invariant* rather than an empirical measurement, and remove it from the PASS gate / threats doc as if it were measured.

**F.1 — `ρ=0.62` "cheap g tracks expensive influence" is a two-cluster (label-driven) artifact.**
The full-pool Spearman 0.6213 / Pearson 0.7524 reproduce exactly from `p3/results/f1/f1_influence.csv`. But the pool is two well-separated clusters (180 benign: mean g=0.938, v=0.857; 220 attack: mean g=0.081, v=0.542), and both signals are strongly label-dependent (Spearman g~label=−0.884, v~label=−0.760). Controlling for the attack/benign label, the correlation **vanishes and reverses**: within-benign Spearman(g,v) = **−0.506** (n=180; permutation test p<0.001, robust — benign g has 94 distinct values, v has 167), within-attack = +0.148, partial Spearman(g,v | label) = **−0.167**.

- There is no hard leakage: the oracle `v = sigmoid(logP(claim|source) − logP(claim|source ablated))` (`neurotaint_offline.py`) is computed without reference to the label and has 347 distinct continuous values. The pool-level agreement is a real fact — but it reflects *shared label dependence* (each signal separates benign from attack), not that cheap `g` tracks the graded continuous magnitude of causal influence.
- The ledger partially caveats (line 474 discloses the attack non-monotonicity, "pritamvediya07v≈0.5 while g→0") but does **not** disclose that the correlation vanishes/reverses once the label is removed. The headline ("runtime g tracks expensive influence") overstates what a between-cluster correlation supports, and this is material to the experiment's stated purpose ("pre-empt: your runtime proxy is meaningless").
- **Fix needed:** report the partial / within-cluster correlations alongside the pooled `ρ`, and rephrase the headline to "g and v both separate attack from benign" rather than "g tracks the continuous influence magnitude."

### LOW

**D.2 — "Dominates both single-sensor competitors" is an unverified overclaim.**
Reproduced from `p3/results/d2/d2_frontier.csv` with the code's own `ret_at_asr` semantics: at the headline operating point ASR≤0.05, full-g retention = **0.7471** but NLI-only = **0.7500** (strictly higher); full-g is below NLI-only at 2/50 ASR-grid points (ASR≈0.061, 0.082). The PASS gate (`d2_frontier.py:114–116`) computes dominance only against the content-blind baseline and never tests competitor dominance. So the ledger wording "dominates both single-sensor competitors" / "competitors fall in between" is not supported near the headline operating point.

- *Why LOW:* the magnitude is a 0.0029 retention gap (~0.2 of ~70 benign claims) at two adjacent grid points — a step-quantization artifact, not a systematic loss. The testbed's own artifacts (PASS message, figure title, threats doc) correctly claim dominance only over the content-blind baseline, which *is* true and verified; the offending phrasing is external ledger/caption wording.
- **Fix needed:** restrict the claim to "dominates the content-blind baseline" (verified), or drop the "competitors fall in between" caption.

**E.4 — Oracle-premise design/disclosure nit in the black-box fallback's secondary utility claim.**
`p3/exp/e4_blackbox_fallback.py:112–113` builds the NLI premise from the ground-truth field value (`premise = "The {field} is {true_v}."`), deviating from the sensor's documented intent (premise=source). The audit alleged this manufactures the 1.00 detection and the "u uniquely catches 0/240 / Δ≈0" finding. **Verification downgraded this from HIGH to LOW:** `render_document()` emits a verbatim key-value render of the same fields, so the legitimate source document literally contains the gold value; an A/B re-run of the real DeBERTa-v3 NLI with the gold-value premise vs the actual source-document premise gave 37/40 identical faith labels (the 3 differences made benign retention slightly *worse*, not the separation better). The "Δ≈0" finding correctly isolates the probe `u` (computed independently from distilgpt2 hidden states), so it is not a tautology.

- **Fix needed (cosmetic):** ground `faith` against `ctx` (the rendered source) instead of a hand-built gold premise, and note the premise construction in the threats doc. Numbers are unaffected.

**F.3 — Mislabeled sensor attribution in the synthesis-attack narration.**
`f3_adaptive.py:142–144` prints "support+usage flag the overgeneralization's low grounding." From `p3/results/f3/f3_adaptive.csv` (40 synthesis rows): `u` mean 0.015 is the binding `min` sensor in 40/40 rows; support averages 0.503 and on its own would catch only 17/40. So it is the **usage probe alone** that catches synthesis, not "support+usage," and "low grounding" mislabels what the usage probe measures (context-driven vs parametric, per `probe.py`), which is *not* entailment/grounding (that is the support sensor). The `residual=0` headline is genuinely true; only the causal narration is wrong.

- **Fix needed (prose):** rephrase to "the usage probe flags the synthesized conclusion as parametric (context-independent)"; do not credit support, and do not call the usage signal "grounding."

---

## 4. Integrity practices spot-checked as CORRECT

The audit specifically looked for hardcoding, rigged outcomes, oracle-into-feature leakage, train/test leakage, and metric/claim mismatch. The following were verified to be done correctly:

- **By-construction security guarantee is real (E.1, E.2).** The no-inflation result holds for forced-max, NaN, inf, >1, <0, and negative-weight inputs; the `min`-clamp can only lower warrant. Monotonicity is machine-checked across 1800 real threads and 3 encodings, with a working checker-teeth control (1478/1800 non-monotone flags on a non-chained control; explicit rising `[0.3→0.7]` control caught). These are honest by-construction guarantees, correctly labeled as such in the threats doc.
- **A.1 content-blindness is structural, not rigged.** Confirmed in `capm/core/types.py` that SUMMARY and PARAPHRASE carry the real fidelity penalty (not arranged by the generator) and in `evaluator.py` that the verdict is a pure function of origin-ceiling + declared-penalty + hops and never inspects content. The 0.000 laundering-detection rate is a genuine structural property of the baseline.
- **A.2 errors counted against the tagger (conservative κ).** Off-diagonal confusion-matrix entries are honest residuals charged to the tagger, so κ=0.926 is if anything conservative. The date 1.000→0.047 ablation reproduces exactly.
- **Group B: no leakage, honest negatives reported.** B.2 advisories verified disjoint from B.1 (0 overlap); no train/test leakage. The B.1 lexical-separability caveat (answer-in-context overlap oracle = 1.000, "probe not uniquely necessary here") and the model-substitution caveat (small open-weight LMs vs 7–8B) are fully disclosed, not buried. The "min-agg gives no benefit" negative is reported as a negative.
- **Group C: clean separation, honest activation-space negative.** C.1 uses a real 80-CVE CISA-KEV corpus with no leakage; the activation-space failure (all cosines saturate in [0.98,1.0] due to anisotropy) is a verified honest negative. C.2's schema rule independently recomputes the CVSS band and is genuinely correct on every constructed case (not a tautology).
- **F.1 influence oracle is independent.** `v` is a genuine logprob-ablation oracle with 347 distinct continuous values, computed with no reference to the attack/benign label — no hard leakage (the overclaim is about interpretation, not data integrity).
- **F.2 is a correctly-reported honest negative.** External NLI is a constant 0.5 and the divergence signature is genuinely inverted (div-AUC 0.004); nothing is promoted to the guarantee and the caveats are accurate. This honest negative deserves credit.
- **Group G cost numbers are real forward passes.** All g1 latency figures reproduce from `g1_cost.csv`; the sensors and the NeuroTaint offline oracle are genuine model forward passes (the offline oracle's ~2× cost matches its two-forward-pass implementation), not stubs. The online/offline separation is implemented correctly.

---

## 5. Residual risks / what a GPU + 7–8B re-run might change

- **Model substitution is the largest external-validity gap.** Groups B, C, D, E, F, G use small open-weight LMs (gpt2/distilgpt2 class, DeBERTa-v3 NLI) on CPU. The probe-transfer (B), NLI-contradiction (C.2), and black-box-fallback (E.4) results could shift materially on 7–8B models: probe separability, NLI entailment/neutral boundaries, and the faith-sensor saturation that currently makes several "min" clamps fire could all move. The threats doc carries a specific, honest CPU/small-model caveat for the cost work; the same caveat should be read as applying to every AUC/F1/κ in the suite.
- **D.1 leakage would not be fixed by a bigger model.** The circularity is structural (feature derived from the label's defining quantity), so a GPU re-run would reproduce the inflated AUC, not correct it. This requires the code/label fix in §3, independent of scale.
- **D.2 competitor-dominance margins are within quantization noise.** A finer ASR grid or a larger benign set could either erase or widen the 0.0029 full-g-vs-NLI-only gap; the headline (dominance over the content-blind baseline) is robust regardless.
- **F.1 within-cluster sign could change.** The within-benign ρ=−0.51 reversal is robust on this data (permutation p<0.001) but is computed on small open-model influence estimates; a larger model's influence oracle might yield a different within-cluster relationship. The pooled, label-driven correlation would persist either way.
- **Wilson-CI precision (A.1) overstated.** CIs treating ~17,280 rows as iid when they collapse to 24 deterministic grid cells will not narrow with more data; they should be reported per-cell, not per-row. A re-run does not change this.
- **B.1 lexical separability is a property of the task, not the model.** The 100%/0% answer-in-context construction means a larger model would still find the task perfectly lexically separable; the probe's claimed *non-lexical* advantage remains undemonstrated future work, as the ledger already states.

---

## Bottom line

Phase-3's central security guarantee (no warrant inflation; per-claim `min`-clamp degradation) reproduces exactly and is a sound by-construction result, but the D.1 calibration AUC is circular, the D.3 "0-contamination" check is a self-comparison tautology, A.1's Table-2 relaunder row is numerically wrong, and the F.1/D.2 "tracking"/"dominance" headlines overclaim — all fixable without touching the load-bearing PASS verdicts.
