# CAPM — Final Experiments Document
### The definitive experiment suite for *Origin-Bounded Trust for Cross-Organizational Agent Systems*

**Purpose.** This is the single, finalized experiment plan, aligned to
`CAPM_Design_Base.md` (the design base) after three review rounds. Every
experiment here exists to make one of the paper's claims *provable on a real
system* and to neutralize a specific reviewer objection. It supersedes all prior
experiment plans (Phase-1 ladder, the 32-experiment NDSS suite, the W/B Phase-2
playbook): those produced the analysis; **this** is the suite the camera-ready
rests on.

**Governing principles (carried from the design base):**
- **System-first.** RQ1 and RQ7/RQ7+ must run on the **real prototype** (Builds
  A+B), not the single-process testbed.
- **Two threat classes never averaged.** Transit attacks (→ ASR 0) and
  origin/wrapper capture (→ ASR > 0 at cost) are reported in separate tables.
- **Honesty is a result.** Residual ASR > 0 (RQ4) and utility cost (RQ7+) are
  expected, reported, and framed — not tuned away.
- **Every number traces to a raw row.** Per-trial CSV; ≥ 20 seeds where
  stochastic; Wilson/bootstrap/McNemar/Spearman as appropriate.
- **Real vs. modeled, always labeled.** System, attacks, defenses = real; only
  the ecosystem *population* (cartography) is modeled, and it is swept + grounded.

---

## 0. The build prerequisites these experiments depend on

| Build | What it is | Gates |
|---|---|---|
| **A — Acquisition wrapper** | real HTTP/API/file wrappers that sign the observed origin tuple; `source_class` from the §10.1 evidence policy | E-A*, RQ1, RQ4, RQ-W, RQ7+ |
| **B — Real transport** | separate processes/containers, real sockets, manifests on the wire, verifier in its own process | RQ1, RQ7 |
| **C — Closest-competitor** | provenance graph + signed origin + static threshold | E-C*, RQ1 |

If a build is incomplete, the experiments it gates are explicitly *not claimable
on the real system* — say so rather than substituting the testbed.

---

## 1. Experiment ↔ claim ↔ objection map (read this first)

| Exp group | RQ | Backs contribution | Neutralizes objection |
|---|---|---|---|
| **E-SYS** real-system containment | RQ1 | C1 (system) | "is there a real system?" |
| **E-C** vs closest-competitor | RQ1 | C1, C3 | **"just provenance + a score"** |
| **E-ABL** assumption ablations | RQ2 | C3 | "unrealistic assumptions" |
| **E-MONO** encoding invariance | RQ3 | C2 | "is it the principle or the constants?" |
| **E-RES** residual / origin-state | RQ4 | C3 | "origin capture does too much" |
| **E-A** acquisition-wrapper / TCB | RQ-W, RQ4 | C1 | **"the wrapper is the TCB"** |
| **E-WGOT-att** attacker targeting | RQ5 | C4 | "WGOT is just knapsack" |
| **E-WGOT-def** defender hardening | RQ6 | C4 | **"WGOT is obvious"** |
| **E-COST** deployment cost | RQ7 | C5 | "is it deployable?" |
| **E-UTIL** utility degradation | RQ7+ | C5 | **"secure by distrusting everything"** |
| **E-GROUND** grounding + robustness | (cross) | C4, C5 | "numbers are synthetic" |
| **E-FORMAL** machine-checked lemma | (appendix) | C2, C3 | "is the theorem real?" |

The **bolded** objections are the five the reviewer flagged as decisive; each has
a dedicated experiment that answers it with data, not rhetoric.

---

## 2. The experiments

For each: **goal · setup · comparators · metrics · pass criterion · which
objection it kills.** "Pass" never means "ASR 0 everywhere" — it means the
predicted, defensible result holds.

### E-SYS — Transitive-laundering containment on the REAL prototype  (RQ1, C1)
- **Goal.** Show CAPM contains transitive laundering in real cross-org workflows.
- **Setup.** On the **Build-A+B prototype** (separate processes, real transport,
  wrapper-attested origins): run all transit attack families (RAG-poisoning,
  knowledge-propagation, causality-laundering, AgentDojo injections) × chain
  lengths {2,3,4,5}.
- **Comparators.** no-defense, identity-only, flat-provenance, CaMeL-single-runtime,
  RAG-citation, semantic-filter, **closest-competitor**.
- **Metrics.** ASR per family per defense; Wilson CIs; paired McNemar vs CAPM.
- **Pass.** CAPM ASR ≈ 0 on transit families; baselines high; result holds on the
  **real system**, not the testbed. (This is the systems claim — without Build B
  it is not claimable.)

### E-C — CAPM vs the strongest closest competitor (security–utility trade-off)  (RQ1, C1/C3)
- **Goal.** Prove CAPM is **not** "flat provenance + a threshold" — against the
  *strongest fair* competitor, judged on the **trade-off**, not ASR alone.
- **Setup.** Run CAPM against a **family** of tuned competitors (not one static
  threshold), each = signed provenance + a trust rule:
  - **C1** deliverer threshold · **C2** origin threshold · **C3** minimum-source
    threshold · **C4** chain-length penalty · **C5** transformation penalty
    *without* CAPM's strict monotone/min semantics.
  Evaluate all in the four stress conditions: (1) high-trust relay carries
  low-origin content; (2) aggregation of multiple low-warrant sources; (3) semantic
  summary hides low-origin text; (4) transformations cause false confidence. Each Cx
  is **swept across its threshold/penalty setting** (conservative→lenient) to trace
  its own trade-off curve.
- **Metrics (report ALL — not just ASR).** ASR, **benign throughput**, **down-rank
  rate**, **hard-block rate**, **useful-answer retention** — for CAPM and every Cx
  across its sweep. Plus the warrant trace showing where CAPM erodes and each Cx
  does not.
- **Pass (a trade-off, NOT an absolute).** We do **not** claim "every Cx leaks all
  four and CAPM contains all four." A *conservatively tuned* Cx may block some
  attacks — but only by over-blocking benign content. The defensible claim is:
  **CAPM dominates the best Cx on the security–utility frontier** (lower ASR at
  equal utility, or higher utility at equal ASR), across the four conditions.
- **Kills:** *"just provenance plus a score"* **and** *"a stricter threshold would
  also block the attacks"* — yes, at a utility cost CAPM does not pay, shown by the
  frontier.

### E-ABL — Assumption ablations (each mechanism is necessary)  (RQ2, C3)
- **Goal.** Show removing the mechanism that enforces each assumption reintroduces
  the matching attack.
- **Setup.** Ablate A1–A6 one at a time; fire the corresponding adversary:
  A1→forgery, A2→omission, A3a→verbatim-but-altered, A3b→unverifiable-as-faithful,
  A4→mid-chain reclassification, A5→wrapper-bypass/relay-authored, A6→aggregation.
- **Metrics.** ASR jump per ablation (contained → leaks); negative control (full
  defense) stays contained.
- **Pass.** Every single-mechanism ablation leaks its matching attack; full system
  contains all. (This *is* the A1–A6 table, executed.)
- **Kills:** *"the assumptions are unrealistic / hand-waved."*

### E-MONO — Monotonicity explains security across encodings  (RQ3, C2)
- **Goal.** Show containment comes from the *structure* (monotone, origin-bounded),
  not CAPM's specific lattice/constants.
- **Setup.** Swap the warrant model: lattice (k=3,5,8,16), continuous [0,1] with
  several penalty shapes, a learned scorer (monotone-constrained vs unconstrained),
  and a **non-monotone negative control**. Re-run the transit-attack matrix.
- **Metrics.** ASR per model; monotonicity-violation count.
- **Pass.** All *monotone* encodings contain; the non-monotone control leaks. (The
  empirical companion to the machine-checked lemma.)
- **Kills:** *"it only works for your specific numbers."*

### E-RES — The residual & the origin-state taxonomy  (RQ4, C3)
- **Goal.** Characterize *exactly* what remains; show it is the irreducible origin
  layer, refined — not a catch-all.
- **Setup.** Evaluate every origin state from design-base §11: honest-high,
  stale, mixed-source, UGC-on-host, compromised, unverifiable-pipeline — **plus
  gradual reputation manipulation** and **wrapper compromise** (from E-A).
- **Metrics.** Per-state: CAPM treatment realized (preserve / time-decay / min /
  sub-origin-bind / degrade / leak) and residual ASR.
- **Pass.** Stale/mixed/UGC/unverifiable are handled by the *defined degradation*
  (ASR contained or capped); only **genuine origin/wrapper compromise** leaks
  (ASR > 0) — **this is expected and is the honest residual**. Report it, don't
  tune it.
- **Kills:** *"origin capture is doing too much work / hides many problems."*

### E-A — Acquisition wrapper & TCB attack suite  (RQ-W, RQ4, C1) — THE PAPER GATE
- **Goal.** Prove the origin is **observed and attested**, not scenario metadata —
  and that the wrapper's TCB status is bounded by evaluation.
- **Setup.** On Build A's three real wrappers (HTTP fetch, API/tool incl. AgentDojo
  banking tools, file/DB read):
  - **E-A.1 Evidence-driven classification — must include AMBIGUOUS cases, not
    just easy ones** (or the wrapper looks engineered to succeed). For a labeled
    corpus of real acquisition channels, does the §10.1 deterministic policy assign
    the correct `source_class` from *observable evidence alone*? The corpus **must**
    include these hard cases:
    | Case | Why it's required (what it stresses) |
    |---|---|
    | Wikipedia / wiki pages | editable but moderated → must be WEAK/sub-origin, not "trusted because reputable" |
    | GitHub issues/comments | trusted host, UGC content → sub-origin extraction (author/comment id), not host trust |
    | corporate blog | authenticated domain, **unsigned** content → MODERATE-LOW, never STRONG |
    | API without response signature | TLS-authenticated channel but **no content integrity** → not authoritative-API |
    | search snippet | indirect source (origin not directly fetched) → WEAK/unverifiable |
    | LLM-API response | generated pipeline → NONE/unverifiable-pipeline |
    | stale webpage / API result | freshness rule → decayed class |
    Report a confusion matrix over these (not just easy examples), the
    degrade-on-uncertainty behavior, and explicitly the **over-trust guard**: a
    popular-but-low-integrity source (high-traffic editable site) must stay WEAK
    because popularity is never an input — only content signature or registered
    credentialed endpoint reaches STRONG.
  - **E-A.2 Wrapper bypass.** Inject content that skips the wrapper → must surface
    as a missing origin observation → quarantine (never silent trust).
  - **E-A.3 Wrapper compromise.** Attacker forges channel evidence / controls the
    wrapper → measure resulting over-trust (the residual proper) and confirm
    attribution still names the (compromised) wrapper/origin for revocation.
  - **E-A.4 Wrapper misclassification.** Honest-but-imperfect evidence → confirm by
    rule-2 it can only **under**-trust; measure rate + utility cost.
  - **E-A.5 Stale / replay.** Stale timestamp → decay; replayed origin observation
    → rejected by nonce/freshness.
  - **E-A.6 Malicious retriever identity.** Unregistered retriever → fails
    verification.
- **Metrics.** classification accuracy + failure mode; bypass-detection rate;
  compromise over-trust rate + attribution rate; misclassification rate +
  direction (must be under-trust); replay/stale rejection.
- **Pass.** Classification matches ground truth on the evidence policy (with
  under-trust-only failures); bypass always quarantined; compromise is the *only*
  path to over-trust and remains attributable; replay/stale/identity attacks fail.
- **Kills:** *"the origin label is manually assigned"* **and** *"the wrapper is an
  unexamined TCB."* Without E-A, CAPM is not origin-bounded in practice.

### E-WGOT-att — WGOT attacker targeting under budget  (RQ5, C4)
- **Goal.** Show warrant-cost-greedy targeting beats naive strategies under a
  budget — and quantify its approximation quality honestly.
- **Setup.** On the modeled ecosystem (grounded per E-GROUND): attacker budget `B`;
  WGOT-greedy solves the §16 budgeted set-selection.
- **Comparators.** naive, random, popularity, cost-only, degree-based; **exact ILP
  on small instances** for the gap measurement.
- **Metrics.** captured residual-risk score under `B`; **greedy-vs-ILP gap**;
  sensitivity to warrant/cost **noise** and to **correlated compromise** (swept).
- **Pass.** WGOT-greedy dominates the naive strategies; greedy-ILP gap reported
  (claim *greedy approximation*, not "optimal," unless they match).
- **Kills:** *"WGOT is just a knapsack heuristic"* (we don't oversell the
  algorithm; the gap table is the honesty).

### E-WGOT-def — WGOT defender hardening (the load-bearing result)  (RQ6, C4)
- **Goal.** Show the residual-risk score, used by the **defender**, prioritizes
  hardening better than every alternative. The attack side alone is intuitive
  ("hit high-warrant, high-reach, low-cost origins"); **this defender result is
  what makes WGOT a core contribution rather than a nice add-on.**
- **Setup.** Defender budget `B_D`; harden the top-k by the §16 dual minimization;
  `p_o(H)` model stated.
- **Minimum acceptable result (all required; without these WGOT is incremental):**
  | Requirement | Why |
  |---|---|
  | beats **random, degree, popularity, cheapest-first, highest-warrant-only, highest-risk-only** | proves non-obvious value |
  | evaluated under **wrong cost estimates** (noisy costs) | real defenders don't know true costs |
  | evaluated under **correlated compromise** | the independence assumption is weak; must not collapse |
  | reports **cost to reach 50/80/95% risk reduction** | operationally meaningful, not just a ranking |
  | **term ablation**: drop each of warrant / reach / cost from the score and re-rank | shows *which* term carries the result (not just the composite) |
- **Metrics.** residual score under `B_D`; cost-to-X%-reduction; #origins hardened;
  robustness under cost-estimate error and correlated compromise; per-term ablation
  deltas.
- **Pass.** WGOT-ranked hardening reaches each risk-reduction target at lower cost /
  fewer origins than **all six** alternatives, degrades gracefully under
  cost-estimate error and correlated compromise, and the term ablation shows the
  composite (warrant × reach ÷ cost) beats any single-term ranking.
- **Kills:** *"WGOT is obvious / just knapsack"* — its value is this operational
  defender result against all alternatives, with the term ablation showing the
  composite score is what matters.

### E-COST — Deployment cost on the real prototype  (RQ7, C5)
- **Goal.** Show CAPM is deployable.
- **Setup.** Measure on Build-A+B: per-hop verification latency, manifest size &
  growth, bandwidth, verifier CPU, and **time-to-quarantine** (the locked Q2
  decision: attribution + quarantine hooks are implemented and measured; full
  global revocation is future work and is **not** claimed).
- **Metrics.** the above, vs chain length; on SAGA's Monitor for comparability;
  time-to-quarantine = denylisting an `origin_id`/`wrapper_id` → first quarantined
  downstream claim.
- **Pass.** sub-ms-class per-hop verification; manifest growth characterized with a
  compaction story; overhead ≪ model-inference latency.

### E-UTIL — Utility degradation (CENTRAL)  (RQ7+, C5)
- **Goal.** Refute *"CAPM is secure because it distrusts most useful agent
  behavior."* This is **not optional**.
- **Setup.** Benign, all-honest workloads dominated by summarize/paraphrase/
  synthesize (what agents actually do). Sweep strictness (warrant floor, penalty
  schedule).
- **Metrics.** rate at which benign summarization collapses warrant to unusable;
  fraction of useful chains down-ranked; rate of low-warrant outputs reaching the
  user; **down-weight vs hard-block ratio**; the **strictness↔utility Pareto
  curve** against the E-SYS ASR.
- **Pass.** A real operating point exists with **both** low transit-ASR **and**
  acceptable benign throughput; CAPM **down-weights rather than over-blocks**;
  strictness is tunable. If no such point exists, that is a true negative result we
  must surface — but the expectation (from the graded verdict design) is that it
  does.
- **Kills:** *"secure by distrusting everything useful."*

### E-GROUND — Grounding & robustness of the modeled ecosystem  (cross-cutting)
- **Goal.** Defuse *"the numbers are synthetic."*
- **Setup.** (a) **Ground** each modeled distribution in the locked datasets
  (design-base Part X.4):
  | Modeled variable | Dataset |
  |---|---|
  | API/tool catalog mix | APIs.guru OpenAPI Directory |
  | web source/domain sampling | Tranco |
  | webpage source-class evidence | Common Crawl + HTTP Archive |
  | vulnerability/capture proxy | CISA KEV |
  | exploit probability | FIRST EPSS |
  | query/reach distribution | MS MARCO / MS MARCO Web Search |
  | agent task/security workflows | AgentDojo |
  (b) **Sweep** every Goal-2 headline under the **locked four-distribution rule**:
  no major number (19× / 73% / top-k) may rest on one synthetic distribution; each
  is shown under **(i)** the real-data-anchored distribution, **(ii)** uniform,
  **(iii)** heavy-tail, and **(iv)** adversarial/noisy — plus the ρ sweep.
- **Metrics.** for each Goal-2 headline (surface-collapse factor, top-k coverage,
  WGOT dominance): the value under all four distributions + the grounded anchor.
- **Pass.** The qualitative conclusions hold under all four distributions and the
  grounded anchor falls inside the range — so no single hand-picked setting carries
  any claim.
- **Kills:** *"the ecosystem is tuned to flatter you."*

### E-FORMAL — Machine-checked lemma + residual reduction  (appendix / Artifact Eval)
- **Goal.** Back C2/C3 formally without headlining theory (NDSS topic-gate).
- **Setup.** Machine-checked monotonicity lemma (exhaustive lattice cross-product +
  random signed chains) and the adversarial-search evidence for the residual
  reduction (0 breaches under A1–A6; breaches return when an assumption is opened —
  controls fire). ProVerif model of manifest-signing + the acquisition-wrapper
  protocol.
- **Pass.** Lemma holds (0 violations, controls fire); search finds no non-residual
  breach; ProVerif queries hold. Lives in appendix/artifact, *supporting* the
  system.

---

## 3. The paper's figures & tables (what each experiment produces)

| Artifact | From | Role |
|---|---|---|
| **Table 1** — real-system containment matrix (defenses × families, ASR+CI) | E-SYS | the headline systems result |
| **Table 2** — CAPM vs strongest Cx: security–utility frontier on the 4 conditions | E-C | kills "just provenance + score" |
| **Table 3** — assumption-ablation (mechanism removed → attack returns) | E-ABL | the A1–A6 table executed |
| **Fig 1** — strictness↔utility Pareto (ASR vs benign throughput) | E-UTIL | kills "distrusts everything" |
| **Fig 2** — residual ASR by origin state | E-RES | the honest residual |
| **Fig 3** — WGOT defender: cost-to-X%-risk-reduction vs alternatives | E-WGOT-def | the load-bearing WGOT result |
| **Fig 4** — encoding invariance (monotone contain, control leaks) | E-MONO | "principle not constants" |
| **Fig 5** — surface-collapse + top-k coverage, swept + grounded | E-GROUND | cartography, de-synthesized |
| **Table 4** — deployment cost vs chain length | E-COST | deployability |
| **Table 5** — wrapper TCB attack suite outcomes | E-A | wrapper is examined, not blind |
| **Appendix** — lemma + reduction + ProVerif | E-FORMAL | formal backing (AE badge) |

---

## 4. Execution order (gated by the builds)

1. **Build C** + **E-C** (cheap, decisive, runnable largely in current testbed) —
   establishes the contribution delta early.
2. **Build A** + **E-A** + **E-RES** + **RQ-W** — the paper gate; converts
   origin from asserted to observed. *Highest value.*
3. **Build B** + **E-SYS** + **E-COST** — the systems claim on real transport.
4. **E-ABL**, **E-MONO**, **E-FORMAL** — mostly reuse existing analysis; re-run
   against the updated mechanisms (A3 split, wrapper).
5. **E-WGOT-att**, **E-WGOT-def**, **E-GROUND** — the residual-surface results,
   grounded + swept.
6. **E-UTIL** — central; run once the graded verdict + A3 rule are final on the
   prototype.

**Backbone for acceptance:** E-C, E-A, E-SYS, E-WGOT-def, E-UTIL. These five are
the difference between weak-reject and accept; the rest strengthen and de-risk.

### Locked target cycle & submission gate
Target: **NDSS 2027 Fall Cycle — deadline 19 Aug 2026** (Summer Cycle, 6 May 2026,
has passed). As of 15 Jun 2026 that is ~2 months — tight, disciplined scope only.
**Submit the full systems paper only if all six are complete:**
1. Build A (acquisition wrapper) · 2. Build B (containerized gRPC/mTLS transport) ·
3. Build C (closest-competitor) · 4. **RQ1 / E-SYS** (real-system laundering) ·
5. **RQ6 / E-WGOT-def** (defender hardening) · 6. **RQ7+ / E-UTIL** (utility curve).
If any of the six is incomplete by the deadline, do **not** force the full systems
claim — fall back to a protocol/analysis or workshop anchor and target the next
cycle. (This six-item gate = the acceptance backbone above + the two enabling
builds it depends on.)

---

## 5. Reporting discipline (applies to every experiment)
- Separate tables for transit (→0) vs origin/wrapper capture (→>0 at cost); never
  one averaged number.
- ≥ 20 seeds where stochastic; Wilson (rates), bootstrap (ratios), McNemar (paired
  defenses), Spearman (monotone relations).
- Every figure regenerable from cached raw rows with zero model calls.
- Label every result **real-system** vs **testbed** vs **modeled-population**.
- Negative/expected-nonzero results (RQ4 residual, RQ7+ utility cost) are reported
  as findings, never tuned away.
- Maintain a `THREATS_TO_VALIDITY` ledger so the limitations section writes itself.
