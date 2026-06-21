# Origin-Bounded Trust for Cross-Organizational Agent Systems
### A Single-Source Design Document (SOTA → Narrative → Threat Model → Contributions → Build Base)

**Purpose.** This is the one document the team works from. It (1) reviews the
state of the art and positions us in it, (2) builds the narrative and problem
statement, (3) specifies the full scenario and threat model, (4) states the
contributions, and (5) gives an honest map of what exists in code vs. what must
be built. It is written so that a strict reviewer's questions are answered
*indirectly* throughout, and so that implementation can begin against it as the
base.

**Working title:** *Origin-Bounded Trust for Cross-Organizational Agent Systems.*

**Venue framing.** NDSS prioritizes practical network/distributed-system security
with system design and implementation, and pre-filters (possible desk-reject)
papers that are proof-only, math-only, or primarily AI/ML. Therefore the entire
document obeys one rule: **lead with the system; theory and ML serve the system.**

---

## PART I — STATE OF THE ART & RELATED WORK

### 1. The setting

Autonomous LLM agents increasingly act in **multi-hop, cross-organizational**
chains: a principal's agent delegates to another organization's agent, which
queries a third, which acquires data from an external source (web page, API,
database). Answers flow back up the chain. Each hop may transform the content
(summarize, paraphrase, compose). The principal acts on the final answer.

### 2. What prior work secures — and the gap it leaves

We group related work by *which layer of trust it addresses*, because the gap is
precisely a layer none of them covers.

**(a) Identity / transport security — "who is talking."**
DID/VC-based agent identity and systems such as **SAGA** (cross-agent identity and
secure channels, NDSS'26) authenticate agents and protect the channel. They
answer *who relayed a message* and *was the channel tampered with*. They are
**content-agnostic**: a fully authenticated agent can faithfully relay a
falsehood, and identity security will say "the sender is legitimate."

**(b) Provenance models — "where did it come from (recorded)."**
**W3C PROV** and **PROV-AGENT** record the lineage of data through agentic
workflows. They are designed for **honest participants** and **single workflows**,
and they **grade nothing**: a recorded source is a recorded source, with no notion
that some origins justify less trust or that trust should erode under
transformation.

**(c) Capability / information-flow control — "what may flow, within one runtime."**
**CaMeL**-style capability tagging and taint/flow-control enforce policies on
values *inside a single runtime / trust domain*. They are strong locally but
**blind across the organizational boundary**: capability labels do not travel
with content once it crosses to another org's agent.

**(d) Retrieval-grounding / citation checking.**
RAG-citation defenses validate that a cited source *exists* and was retrieved.
They check **source presence**, not whether trust is preserved as content is
transformed and relayed across hops.

**(e) Content / semantic filtering.**
LLM-judge and classifier guards inspect the **text**. As our own analysis shows
(and as the laundering literature predicts), content judged on persuasiveness is
exactly what an attacker optimizes — authority-framed falsehoods score high.
These defenses see *text*, not *manifest semantics*.

**(f) Signed-manifest containers and supply-chain integrity.**
**C2PA** signs media provenance manifests (single-author). **in-toto / SLSA** and
**remote attestation** secure software supply-chain *origin integrity*. These are
mechanisms we **compose with**, not competitors: C2PA gives the container pattern;
in-toto/SLSA/attestation are the origin-integrity layer our residual hands off to.

**(g) The attack literature (what makes the problem real).**
Prompt-injection benchmarks (**AgentDojo**), RAG poisoning, multi-agent knowledge
propagation, and causality/denial laundering all demonstrate that low-quality or
adversarial content **gains apparent credibility as it moves through trusted
agents.** None of the defenses in (a)–(e) stops this across organizational
boundaries.

### 3. The gap, stated precisely

> No existing mechanism enforces a **graded trust value, bound to the true
> origin, that is preserved (and provably non-increasing) as content is
> transformed and relayed across organizational boundaries.**

Identity secures *who*; provenance *records* without grading; capabilities enforce
*locally*; citation/semantic checks read *presence/text*. The missing layer is
**cross-organizational, origin-bound, graded, monotone trust over a verifiable
manifest** — which is what we build.

---

## PART II — NARRATIVE & PROBLEM STATEMENT

### 4. The phenomenon: cross-agent information laundering

**Information laundering** is the rise of a claim's *apparent* trustworthiness as
it passes through trusted intermediaries, decoupled from the *actual* warrant of
its origin. A claim planted on an editable page can arrive at the principal
looking authoritative simply because authenticated, reputable agents relayed it.
This is a transitive-trust failure: trust in the *deliverer* is mistaken for trust
in the *information*.

### 5. Problem statement

> In a multi-hop, cross-organizational agent chain, the principal must decide how
> much to trust a delivered claim. Existing systems let the principal verify the
> deliverer's identity and (at best) read an ungraded provenance log. They provide
> no way to bound the claim's trust by the **true warrant of its origin** and to
> guarantee that no relay — however trusted — can **raise** that trust in transit.
> We seek a deployable mechanism that (i) binds trust to the origin, (ii) makes
> trust **monotone non-increasing** across hops and transformations, (iii)
> computes the trust **outside** the language model (so persuasive text cannot
> launder warrant), and (iv) does so across real organizational/process
> boundaries.

### 6. The intellectual arc (how the paper reads)

1. **Problem on a real system** — laundering demonstrated on a real multi-runtime
   deployment (separate processes, real transport, signed manifests on the wire).
2. **Mechanism (CAPM)** — origin-bound, monotone, externally-verified manifest
   chain; monotonicity introduced as *design rationale*.
3. **Decomposition** — under an explicit adversary model, transitive laundering
   reduces to a single residual: **origin-integrity compromise**.
4. **WGOT** — the residual's budgeted targeting problem (attacker), and its dual
   (defender hardening) over the same residual-risk score.
5. **System & deployment** — one coherent system with measured cost and a
   tunable security/utility operating point.
6. **Honest limits** — what CAPM does not do; the residual is *managed, not
   eliminated*.

**Best hook:** the same residual-risk score *induces both* the attacker's optimal
targeting *and* the defender's optimal hardening order — a well-built provenance
defense signposts its own weakest point, and that signpost is also the defender's
hardening checklist.

---

## PART III — SCENARIO & THREAT MODEL

### 7. System model & definitions

- **Claim.** An atomic content unit transmitted between agents.
- **Origin.** The first acquisition point of a claim.
- **Acquisition wrapper.** A trusted component (browser tool / retrieval service /
  API client) that, at the moment content crosses into the system, produces and
  signs an **origin observation** — `⟨content_hash, source_URI/API/tool_id,
  timestamp, retriever_identity, source_class_evidence, acquisition_context,
  nonce⟩` (the `nonce` gives replay protection; see the locked tuple in Part X).
  The source itself is *never* trusted to self-attest; the wrapper attests what it
  observed.
- **Manifest.** A hash-linked chain of per-hop, per-segment **signed** records
  (origin observation + each transformation), one signature per agent under its
  own key.
- **Warrant.** An ordered trust label/score the **external verifier** assigns,
  derived from the manifest — never from the delivered text.
- **Verifier.** A component *outside* the language model that validates signatures
  and computes warrant at the principal-facing boundary.
- **Laundering success.** Accepted output warrant **exceeds** the maximum warrant
  justified by the **true** origin state.
- **Capture.** The adversary causes an origin observation to bind **high** warrant
  to **low-integrity** content (incl. by compromising the acquisition wrapper).

### 8. Adversary capabilities

The adversary may: control external sources (web pages, third-party APIs); operate
or compromise one or more **relay** agents; attempt to forge, replay, reorder,
drop, or splice manifest segments; mislabel transformations; collude across
multiple relays; aggregate multiple sources to manufacture confidence; and attempt
to influence or compromise the **acquisition wrapper**. The adversary can read
published warrant values (the manifest is not secret).

The adversary may **not** (under the stated assumptions) forge signatures without
keys (A1) or cause the verifier to skip verification.

### 9. Assumptions A1–A6 (each enforced by a concrete mechanism; each ablatable)

| ID | Assumption | Enforced by | If dropped → attack returns |
|---|---|---|---|
| **A1** | Signing keys secret; signatures unforgeable | Ed25519 per-segment signing + credential registry | forged-receipt attack |
| **A2** | Receipts mandatory; their absence is detected | hash-linked chain + verifier | omission attack (launder by dropping a hop) |
| **A3a** | **Syntactic** transforms are verifiable (hash / quote / span binding) | content-hash + span binding | verbatim-claim-but-altered |
| **A3b** | **Semantic** transforms are **not** perfectly verifiable → **warrant conservatively degrades** | monotone penalty + soft-binding as a *degrade trigger, not a truth oracle* | (no fragile detector to break — safe rule below) |
| **A4** | Origin source-class is bound into the origin observation's signed bytes | acquisition-wrapper signature | mid-chain reclassification |
| **A5** | The origin observation is created and signed **at acquisition, before relay**, by the wrapper | acquisition wrapper | relay-authored origin / wrapper bypass |
| **A6** | Composition warrant is **min-bounded** (weakest input) | min-rule in the verifier | aggregation / false-confidence attack |

**A3 safe rule (the key robustness move):** *if a transformation's fidelity cannot
be cryptographically or structurally verified, warrant MUST drop.* Unverifiable-
as-faithful is treated as generation (maximum penalty). **Security never depends
on a semantic classifier being correct** — only on this conservative default; a
better detector would raise *utility*, never security.

### 10. The origin-acquisition model (why A5 is realistic)

Real sources do not sign CAPM receipts. The **acquisition wrapper** is the origin
attester: it wraps a genuine fetch/tool-call/API-response and, at the boundary,
signs an origin observation whose `source_class` is **derived from observable
evidence** (authenticated API vs. scraped page vs. signed feed vs. editable
host) — *not passed in as a parameter*. The wrapper is therefore a first-class
system component **and** a named attack surface; we evaluate:
- **wrapper compromise** (attacker controls acquisition) → an A5/A7 capture;
- **wrapper misclassification** (wrong `source_class`) → folds into the
  origin-state taxonomy (unverifiable/mixed);
- **wrapper bypass** (content enters without a wrapper) → must surface as a
  missing origin observation (A2).

#### 10.1 Deterministic source-class policy (the labels are NOT arbitrary)

The single most-attacked weak point is "how does the wrapper decide
`source_class`?" If it is a judgment call, the whole origin-bounded guarantee is
arbitrary. We therefore define a **deterministic, evidence-driven policy**: the
wrapper inspects *observable* properties of the acquisition channel and maps them
to a class by fixed rules. No content semantics, no model judgment — only channel
evidence.

| Observable evidence (from the acquisition channel) | Source class | Reason |
|---|---|---|
| Signed API response from an **allowlisted, authenticated** endpoint (valid TLS cert chain + request auth + response signature) | **STRONG / authoritative-API** | authenticated origin with content integrity |
| **Signed feed / content-credential** (e.g. C2PA-signed, verifiable signature chains to a trusted issuer) | **STRONG / verified-document** | cryptographic origin integrity |
| First-party internal DB/service read over an authenticated channel | **MODERATE / first-party-DB** | trusted but no per-record content signature |
| Unsigned **static** webpage on a non-editable corporate domain (valid TLS, no auth, no content signature) | **MODERATE-LOW / public-webpage** | host identified, no content integrity |
| **Editable / UGC** platform (wiki, issue tracker, comment, forum) | **WEAK / editable-source**, bound to **sub-origin** (author/edit id) not the host | host ≠ author; moderation ≠ integrity |
| **Search-result snippet / aggregator** (origin URL not directly fetched) | **WEAK / unverifiable** | provenance one hop removed; not directly observed |
| Response from an endpoint **known to return model-generated content** (LLM API, generative service) | **NONE / unverifiable-pipeline** | generation, not acquisition of a pre-existing fact |
| Any of the above with a **stale** timestamp beyond a freshness window | **decay** the above by the staleness rule | freshness risk |
| Channel evidence **insufficient to classify** | **default to NONE (degrade)** | the A3 safe rule applied to origin classification |

**Two rules govern the table, and both preserve security without a truth oracle:**
1. **Evidence-only.** The class is a function of *channel evidence the wrapper can
   structurally verify* (cert chains, signatures, auth, endpoint allowlist, host
   editability, freshness), never of the content's meaning.
2. **Degrade-on-uncertainty.** If the evidence does not clearly establish a class,
   the wrapper assigns the **lower** class (ultimately NONE). Misclassification can
   only ever *under*-trust by default; *over*-trust requires forged channel
   evidence, which is exactly wrapper/origin compromise (the residual).

This table is implemented as the wrapper's classifier and is itself an evaluated
component (RQ-W: does evidence-driven classification match ground truth across the
acquisition paths, and what is its failure mode under adversarial channel
evidence?).

**How each signal is actually detected (no hand-waving — reviewers will ask).**
Every cell above reduces to a *mechanically checkable* signal, not a judgment:
- **"Signed API response" vs. "normal TLS."** TLS only authenticates the
  *channel/host*; it says nothing about *content integrity*. "Signed API response"
  requires a **content signature** over the response body that verifies to a key in
  the endpoint's registered credential (e.g. an HTTP Message Signature / JWS /
  detached-COSE over the payload). No content signature → it is *only* TLS →
  classed as `public-webpage`/`first-party-DB`, never `authoritative-API`. This
  distinction is the whole point: a TLS-authenticated channel with no content
  integrity does **not** earn STRONG.
- **"Non-editable corporate domain."** Detected by **allowlist membership** (see
  below) plus the *absence* of write/edit affordances on the fetched path, not by
  "it looks corporate." If not on the allowlist, it is not corporate-trusted.
- **UGC sub-origin extraction.** For known UGC platforms, the wrapper extracts the
  **author/edit identifier** from the platform's structured metadata (e.g. the
  revision/commit/comment id and author handle) and binds warrant to that
  **sub-origin**, not the host. If the sub-origin cannot be extracted, degrade to
  WEAK/unverifiable (rule 2).
- **Stale window.** Chosen **per source class** from a declared freshness policy
  (e.g. signed-feed TTL from its own metadata; API `Cache-Control`/`Date`;
  configurable default per class) — a *declared, auditable parameter*, not an ad-hoc
  number; its sensitivity is swept in E-A.
- **Allowlist construction.** The authenticated-API/corporate allowlist is built
  from **registered, credentialed endpoints** (the deployment's own trust root /
  the SAGA-style registry), not from popularity. **Popularity is explicitly not an
  input** — this directly prevents the "over-trust popular but low-integrity
  sources" failure (a high-traffic editable site stays WEAK because it has no
  content signature and is not a credentialed endpoint).
- **Over-trust guard.** Because popularity/traffic never raises class and the only
  paths to STRONG are *content signature* or *registered credentialed endpoint*,
  the classifier cannot be talked into over-trusting a popular-but-low-integrity
  source; the only way to STRONG is forged channel evidence = wrapper/origin
  compromise (the residual).

These detection methods are exactly what **E-A.1 must test on ambiguous cases**
(Wikipedia, GitHub issues, corporate blogs, unsigned-but-TLS APIs, search snippets,
LLM-API responses, stale results) — not just easy ones — so the classifier is shown
to be honest, not engineered to succeed.

#### 10.2 The acquisition wrapper is the Trusted Computing Base (TCB) — stated, not hidden

Introducing the wrapper makes it the **TCB** for origin provenance: if the wrapper
is wrong or compromised, downstream warrant is wrong. We **admit this explicitly**
rather than letting a reviewer surface it, and we treat the wrapper's attack
surface as first-class (evaluated in RQ4 / RQ-W):
- **wrapper compromise** — attacker controls the acquisition component → forged
  channel evidence → over-trust. This is the residual proper (A7-class), and we
  measure it and bound the damage via attribution.
- **wrapper bypass** — content enters without passing a wrapper → must surface as a
  **missing origin observation** (A2) and be quarantined, never silently trusted.
- **wrapper misclassification** — wrong class from honest-but-imperfect evidence →
  by rule 2 (degrade-on-uncertainty) this can only under-trust; we measure the rate
  and its utility cost.
- **stale wrapper output / replayed origin observation** — defeated by the
  timestamp + freshness rule and nonce/replay protection in the signed tuple.
- **malicious retriever identity** — the `retriever_identity` field is itself
  signed and bound to a registered wrapper credential; an unregistered retriever
  fails verification.

The TCB is deliberately **small and well-defined** (the wrapper + the signing
keys + the verifier), which is the standard way to make a trust argument
defensible: we do not claim "no TCB," we claim "a minimal, named, evaluated TCB."

### 11. Origin-state taxonomy (replacing binary "captured/not")

| Origin state | CAPM treatment |
|---|---|
| honest, high-integrity | preserve warrant (≤ class ceiling) |
| honest but **stale** | **time-decay** warrant |
| **mixed-source** | **min** over embedded sub-sources |
| **UGC on trusted host** | bind to the **sub-origin**, not the domain |
| **compromised** (incl. wrapper compromise) | **A7 violation — the residual proper** |
| **unverifiable pipeline** (e.g. API returns model-generated text) | **degrade** |

### 12. The scoped residual theorem (state and use verbatim)

> **Theorem (Residual Reduction, scoped).** Within the CAPM transit adversary
> model (A1–A6, with A3 split and the acquisition-wrapper model), every successful
> laundering attack — via relay, reclassification, omission, collusion, or
> aggregation — is blocked unless an assumption-enforcing mechanism is removed or
> the origin-integrity assumption (A7) fails. The residual is therefore
> origin-integrity compromise (including acquisition-wrapper compromise), refined
> by the origin-state taxonomy; stale / mixed / UGC / unverifiable states are
> handled by defined degradations, leaving genuine origin/wrapper capture as the
> irreducible core.

The novelty is the **exhaustiveness** (nothing else survives), not the
origin/transit split itself (that is the established Plane-1/Plane-2 distinction
and is never claimed as ours).

---

## PART IV — THE DEFENSE (CAPM)

### 13. Mechanism

CAPM = origin observation (signed by the acquisition wrapper) + a hash-linked,
per-hop-signed manifest + an **external verifier** that computes warrant by:
1. verifying every signature back to a registry the verifier does not control;
2. starting warrant at the origin's `source_class` ceiling;
3. applying a **monotone non-increasing** penalty per transformation (with the A3
   safe rule: unverifiable → max penalty);
4. **min-bounding** composition over multiple inputs;
5. emitting accept / down-weight / quarantine **outside** the language model.

### 14. Why it works (monotonicity — design rationale, not headline)

Containment is a structural property: **no relay operation can raise warrant.**
This is the monotonicity invariant. It is what makes laundering fail regardless of
how persuasive the relayed text is, and it holds across warrant encodings (lattice
/ continuous / learned), with a non-monotone control that leaks — evidence that
the *structure*, not the constants, does the work. The machine-checked lemma lives
in an appendix / artifact, supporting the system rather than headlining it.

### 15. Deployment posture (one coherent system, not a layer pile)

Operating the system: where to place the verifier; the security/utility operating
point (tunable via the warrant floor and penalty schedule); coupling
warrant↔integrity at deployment (harden high-warrant origins); attribution of
accepted claims to their signed origin. Revocation is included **only if
implemented** (see Part VI).

---

## PART V — THE RESIDUAL ATTACK & ITS DUAL (WGOT)

### 16. WGOT as a budgeted optimization (formal)

Let origins `O` each have warrant `w_o`, reach `r_o`, capture probability `p_o`,
capture cost `c_o`. 

**Attacker (budgeted set selection, budget `B`):**
> maximize `Σ_{o∈S} w_o · r_o · p_o`  over `S ⊆ O`  s.t. `Σ_{o∈S} c_o ≤ B`.

**Defender (dual minimization over the same score, budget `B_D`, hardening cost
`h_o`, post-hardening capture prob `p_o(H)`):**
> minimize `Σ_{o∈O} w_o · r_o · p_o(H)`  over `H ⊆ O`  s.t. `Σ_{o∈H} h_o ≤ B_D`.

**Specification (answering the obvious questions up front):** WGOT selects a
**set**, not one origin; `c_o`/`h_o` are knapsack weights inside the budget
constraint, not divisors in the objective; `p_o` is **independent** in the base
model (correlated compromise is a swept extension); hardening changes `p_o`
(primarily) and may raise `c_o`; `reach` is static in the base model (post-
compromise graph effects are an extension); the defender problem is a **dual
minimization over the same residual-risk score**, not the identical problem.

**Optimality language.** This is 0/1 knapsack → NP-hard in general. We therefore
claim **WGOT is a warrant-cost *greedy* policy that approximates the budgeted
residual-risk objective**, and we report its gap to an exact/ILP solution on small
instances. We do **not** say "optimal" unless the exact solver matches greedy on
the evaluated instances.

**Duality wording (precise).** *WGOT induces both an attacker targeting policy and
a defender hardening policy over the same residual-risk score* — not "the same
algorithm." The problems are related via one score but are distinct (the
defender's action changes the landscape).

### 17. Why WGOT is more than "attack the cheap valuable node"

Its value is the **defender** result: hardening the WGOT-ranked top-k reduces
residual risk faster than degree / popularity / cheapest-first / highest-warrant-
only / highest-risk-only / random — measured, under budget, with robustness to
wrong cost estimates. A well-built provenance defense **publishes warrant**, so it
*localizes* the attacker's best target; the same localization is the defender's
prioritized hardening list.

---

## PART VI — CONTRIBUTIONS

The **system** is the contribution; the rest are properties of it (avoids the
"too many contributions / layer pile" failure mode).

**C1 — The system.**
> *To our knowledge, CAPM is the first implemented mechanism that combines
> cross-domain agent communication, graded origin-bound warrant, signed per-hop
> manifests, an acquisition wrapper that attests origins at the boundary, and
> external monotone verification.*
Real only if the multi-runtime prototype + acquisition wrapper exist (Part VII).

**C2 — Monotonicity as the explanation.** *Monotonicity explains why CAPM works;
the prototype shows it can be deployed.* (Machine-checked lemma + encoding-
invariance, appendix/artifact.)

**C3 — The scoped decomposition.** Transitive laundering provably reduces to
origin/wrapper integrity under the stated model; novelty is the exhaustiveness.

**C4 — WGOT: budgeted residual targeting + its defender dual.** Greedy
approximation with gap-to-ILP; the defender hardening result is the load-bearing
half.

**C5 — Deployment value.** Verifier placement, the tunable security/utility
operating point, warrant↔integrity coupling, **attribution + quarantine hooks**
(full global revocation is future work — see Part X.3),
and the WGOT-defense hardening recipe — presented as *how to operate C1*.

---

## PART VII — HONEST STATE OF THE IMPLEMENTATION (what exists vs. what to build)

This section exists so the team builds the *right* things and the paper never
overclaims. **Be precise about which layer is real.**

### 18. What is genuinely real today
- **Cryptography:** each agent has a distinct Ed25519 keypair; every segment is
  really signed over canonical bytes; the receiver verifies against a registry it
  does not control. The **trust boundary is cryptographically genuine.**
- **Warrant logic:** monotone scoring, origin ceiling, min-bounded composition,
  the A3 conservative-degrade rule — implemented and machine-checked.
- **Vendored SAGA crypto/CA/Monitor** for the signing primitive, trust root, and
  overhead measurement.
- **Analysis layer:** the decomposition search, WGOT (as analysis), ablations,
  encoding-invariance — all run in the single-process testbed.

### 19. What is SIMULATED today (and must become real for the systems claim)
- **Process/transport boundary (Q1).** A "cross-org hop" is a recursive in-process
  method call; there is no socket, serialization boundary, or second runtime. The
  vendored SAGA transport is an ABC + DummyAgent, not real networking. Honest
  framing: **"cryptographic multi-runtime semantics, single-process execution."**
- **Origin acquisition/classification (Q1b).** Origin `source_class` is a scenario
  parameter / static lookup, **not** observed by an acquisition wrapper. The
  signature on the origin is real; *what it asserts* (the class) is hand-set ground
  truth. **No code wraps a real fetch/tool-call and signs what it observed.**

### 20. The two foundational builds (in priority order)

**Build A — Acquisition wrapper (highest value; this is novel and load-bearing).**
This is **the true paper gate**: without it, the "origin" is scenario metadata, and
a reviewer's fatal line is *"CAPM's guarantee depends on an origin label manually
assigned in the experiment."* Build A must demonstrate **all** of:
- a **real HTTP fetch** wrapper;
- a **real API/tool** wrapper (AgentDojo banking tools are ideal);
- a **real file/database** wrapper;
- the wrapper **signs the observed tuple** at the boundary;
- `source_class` **derived from observable channel evidence** per the §10.1 policy
  (never a parameter);
- **wrapper bypass detected** (missing origin observation → quarantine);
- **wrapper compromise evaluated** (forged channel evidence → measured residual);
- **wrapper misclassification evaluated** (rate + utility cost; under-trust only).

Only when all of these hold is CAPM **origin-bounded in practice**, not just in
the scenario config. This build converts the threat model from "asserted origin"
to "observed, attested origin" and constructs the I6/T4 seam the literature names
as open.

**Build B — Real process/transport boundary (necessary; mostly engineering).**
Locked stack (Part X.2): **Docker Compose containers** + **gRPC over mTLS** +
**verifier and registry/CA as separate containers**; manifests genuinely on the
wire (gRPC serialization); CAPM Ed25519 signatures on segments. **Two linked
identity layers:** mTLS cert = transport/service identity; SAGA-style registry maps
agent IDs → Ed25519 manifest-signing keys. The verifier checks *both* `mTLS
identity == registered agent identity` **and** `manifest signature verifies under
that agent's registered CAPM key`. The SAGA `DummyAgent`/ABC is replaced by real
gRPC transport. Yields real latency/bandwidth/CPU (RQ7) and makes C1's deployment
claim true.

**Build C — Closest-competitor baseline (cheap; decisive).**
"Provenance graph + signed origin + a trust policy." CAPM must beat the
**strongest fair** version of this, not a static-threshold strawman. So Build C is
a *family* of tuned competitors, and CAPM must beat the best of them:
- **C1** signed provenance + **deliverer** threshold;
- **C2** signed provenance + **origin** threshold;
- **C3** signed provenance + **minimum-source** threshold;
- **C4** signed provenance + **chain-length** penalty;
- **C5** signed provenance + a **transformation** penalty *without* CAPM's strict
  monotone / min-bounded semantics.
CAPM's delta is precisely the A1–A6 semantics (strict per-hop monotone erosion +
min-bounded composition + degrade-on-unverifiable) that none of C1–C5 enforce
together.

**The "just provenance + a score" objection is answered experimentally, not
rhetorically.** Each Cx *has* signed origins and a trust rule; what none has is the
full strict semantics. We construct four conditions that stress exactly that gap
(part of RQ1):
1. **High-trust relay carries low-origin content** — defeats deliverer-threshold
   (C1); CAPM caps at the WEAK origin (monotonicity).
2. **Aggregation of multiple low-warrant sources** — defeats min-source/threshold
   variants that count corroboration (C3); CAPM min-bounds the composition (A6).
3. **Semantic summary hides low-origin text** — defeats variants without
   degrade-on-unverifiable (C5); CAPM applies the transformation penalty + A3 rule.
4. **Transformations cause false confidence** — defeats chain-length/transformation
   penalties that are not strictly monotone (C4/C5); CAPM erodes monotonically.

**Pass criterion — a trade-off, not an absolute (this matters).** We do **not**
claim "the competitor leaks all four and CAPM contains all four" — a *conservatively
tuned* threshold could block some attacks too, but only by over-blocking benign
content. The honest, defensible claim is: **CAPM achieves a strictly better
security–utility trade-off than the best Cx.** So the comparison reports, for CAPM
and each Cx, **all of**: ASR, benign throughput, down-rank rate, hard-block rate,
and useful-answer retention — and shows CAPM dominates on the security–utility
frontier (lower ASR at equal utility, or higher utility at equal ASR). This
pre-empts *"a stricter threshold would also block the attacks"* — yes, at a utility
cost CAPM does not pay.

### 21. Priority note (so effort goes to the right place)
Build A (acquisition wrapper) is **more important than** Build B (transport),
because A is the novel contribution and is load-bearing for the residual theorem,
while B is necessary-but-routine. Do A first, B second, C alongside.

---

## PART VIII — EVALUATION (the seven RQs + utility)

Each RQ states question, method, comparators, metric. RQ1 and RQ7 **must** run on
the real prototype (Builds A+B); the rest may run in the testbed where noted.

- **RQ1 — Prevent transitive laundering on the real system?** all attack families
  × all baselines (incl. **closest-competitor**) on the multi-runtime prototype;
  ASR + CIs + paired tests; CAPM≈0 on transit, baselines high, **CAPM beats
  closest-competitor** on multi-hop erosion / composition / unverifiable cases.
- **RQ2 — Which mechanisms are necessary?** ablate A1–A6; the matching
  counterexample (forgery / omission / alteration / reclassification /
  wrapper-bypass / aggregation) returns; ASR jump per ablation.
- **RQ3 — Does monotonicity explain security across implementations?** lattice /
  continuous / learned warrant + non-monotone control (must leak).
- **RQ4 — What residual remains?** full origin-state taxonomy incl. **wrapper
  compromise** and **gradual reputation manipulation**; residual ASR + which states
  are degraded vs. irreducible. *(Residual ASR > 0 expected and good.)*
- **RQ5 — WGOT attacker value?** WGOT-greedy vs naive / random / popularity /
  cost-only / degree; gap-to-ILP on small instances; noise + correlated-compromise
  sensitivity.
- **RQ6 — WGOT defender value?** WGOT-ranked hardening vs random / degree /
  popularity / cheapest-first / highest-warrant-only / highest-risk-only; residual
  under `B_D`, **cost to reach 50/80/95% reduction**, #origins hardened, robustness
  to wrong cost estimates.
- **RQ7 — Deployment cost?** latency, manifest size, bandwidth growth, verifier
  CPU, revocation latency (if built).
- **RQ7+ — Utility degradation (CENTRAL, not optional).** Because LLM agents mostly
  summarize, synthesize, and paraphrase, the A3 safe rule could label most useful
  outputs low-warrant — so a reviewer's live worry is *"CAPM is secure because it
  distrusts most useful agent behavior."* This RQ must refute that with data, by
  showing **all** of: benign summarization does **not** always collapse warrant to
  useless levels; users still receive **actionable** outputs; CAPM **down-weights
  rather than over-blocks** (graded verdict, not binary reject); strictness is
  **tunable**; and the **strictness↔utility Pareto curve is acceptable** (a real
  operating point exists with both low ASR and high benign-throughput). Without
  this result, the security claim is hollow.

---

## PART IX — NON-GOALS & HONEST LIMITS (state these; they build trust)

- A high-quality answer from a low-warrant origin **stays low-warrant** (we bound
  by origin, not apparent quality).
- A trusted origin **can still be wrong** — CAPM does **not verify truth**.
- CAPM does **not solve source reputation** (it consumes a class signal; it does
  not compute reputation).
- CAPM may **penalize synthesis-heavy workflows** (the A3 safe rule) — quantified
  in RQ7+.
- CAPM does **not solve origin integrity**; it **reduces** the threat to it and
  **composes** with attestation/SLSA.
- Ecosystem-scale cartography (surface-collapse / chokepoint numbers) is **modeled
  population-level analysis**; the **system, attacks, and defenses are real**, and
  the modeled numbers are robustness-swept and **grounded in real data wherever
  possible**: tool/API catalogs (for the source-class mix), public domain/
  source-class distributions, breach and exploit statistics (as capture-cost
  proxies), query-frequency logs (for reach), public vulnerability statistics, and
  enterprise workflow traces where available. Each modeled distribution cites its
  real-data anchor or is swept across a justified range; no single hand-picked
  setting carries any conclusion.

**The five anticipated reviewer objections, answered indirectly above:**
*"just provenance + a score"* → Build C comparison (RQ1); *"unrealistic
assumptions"* → each enforced, removal reintroduces the attack (RQ2); *"origin
capture does too much"* → taxonomy, only genuine compromise irreducible (RQ4);
*"WGOT is obvious"* → the defender result vs all alternatives (RQ6); *"numbers are
synthetic"* → real system/attacks/defenses, only cartography modeled + swept +
grounded.

---

## PART X — LOCKED DECISIONS (Part X is now decided, not open)

These four decisions are **locked**; build against them.

**1. Build A scope — three acquisition paths, in this priority order.**
Do all three; do **not** add more (more wrappers dilute effort).
| Priority | Path | Why |
|---|---|---|
| 1 | **HTTP fetch wrapper** | most general, most reviewer-relevant; covers web-origin laundering |
| 2 | **AgentDojo banking/tool wrapper** | strong benchmark fit; real tool-using agent tasks (e-banking, etc.) |
| 3 | **File/DB read wrapper** | shows CAPM is not web/RAG-only; covers enterprise/internal sources |

Locked signed origin tuple (every wrapper signs exactly this):
```
⟨content_hash, source_URI/API/tool_id, timestamp, retriever_identity,
  source_class_evidence, acquisition_context, nonce⟩
```
(The `nonce` is added for replay protection; `source_class_evidence` feeds the
§10.1 deterministic policy.)

**2. Build B target — containers + gRPC + mTLS.**
Locked stack: **Docker Compose / containers** + **gRPC transport** + **mTLS**
service-to-service auth + **CAPM Ed25519** signatures on manifest segments +
**verifier as a separate container** + **registry/CA as a separate service.**
Not "separate Python processes" (too weak for an NDSS systems claim); not raw TLS
sockets (use gRPC's built-in TLS + client certs for mutual auth).

**Two linked identity layers (locked):**
- **Transport identity:** the mTLS cert identifies the service/container.
- **CAPM identity:** the SAGA-style CA/registry maps agent IDs → Ed25519
  manifest-signing keys.

The verifier checks **both**: `mTLS service identity == registered agent identity`
**AND** `manifest signature verifies under that agent's registered CAPM key`. Do
**not** force the SAGA CA to become the TLS CA; keep transport auth and
manifest-signing identity *linked through the registry*.

**3. Q2 — claim attribution + quarantine; defer full revocation.**
Implement and claim **attribution + quarantine hooks**. Do **not** claim full
global revocation as a main contribution. Paper wording (locked):
> *CAPM preserves signed attribution for every accepted claim and supports
> quarantine of origins whose wrapper or source class is later invalidated.
> Automated global revocation is future work unless fully implemented and
> measured.*

Minimal safe implementation: add `origin_id`/`wrapper_id` to a denylist → the
verifier downgrades/quarantines future claims from that origin → report
**time-to-quarantine**. Call this **quarantine**, not revocation. (Full revocation
opens propagation delay, stale cached outputs, already-acted-upon claims, cross-org
policy agreement, partial rollback — a reviewer trap we avoid.)

**4. Real grounding distributions — locked dataset map.**
| Modeled variable | Dataset / source | Use |
|---|---|---|
| API/tool catalog mix | **APIs.guru OpenAPI Directory** | public API/source-type distribution |
| Web source/domain sampling | **Tranco** | reproducible popular-domain sampling |
| Webpage source-class evidence | **Common Crawl + HTTP Archive** | large-scale crawl + request/response metadata |
| Vulnerability/capture proxy | **CISA KEV** | known-exploited → compromise/capture likelihood |
| Exploit probability | **FIRST EPSS** | probability-of-exploitation proxy |
| Query/reach distribution | **MS MARCO / MS MARCO Web Search** | real query/click reach distribution |
| Agent task/security benchmark | **AgentDojo** | realistic tool-using workflows + attacks |

**Locked rule:** no major ecosystem number (19× / 73% / top-k) may depend on one
synthetic distribution. Every such number is shown under **(a)** the real-data-
anchored distribution, **(b)** uniform, **(c)** heavy-tail, and **(d)**
adversarial/noisy distributions.

---

### Appendix pointers (for the artifact / formal track)
- Machine-checked monotonicity lemma + encoding-invariance (C2).
- Adversarial-search evidence for the residual reduction (C3).
- WGOT greedy-vs-ILP gap tables (C4).
- ProVerif/formal model of the manifest-signing + acquisition-wrapper protocol.
