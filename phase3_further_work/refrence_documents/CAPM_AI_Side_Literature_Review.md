## Part 1 — The five AI-side problem regions (and the SOTA in each)

### Region A — Internal provenance: does the model itself track where information came from?

This is the deepest and most promising complement to CAPM, because it is the literal AI-layer mirror of what CAPM does cryptographically.

**Probing for Knowledge Attribution in Large Language Models** (Boer, Brink, Ulmer; arXiv:2602.22787, Feb 2026). The headline AI-side result for your work. A *linear probe* on hidden representations predicts whether a given output token was driven by the prompt/context or by the model's parametric memory — up to 0.96 Macro-F1 on Llama-3.1-8B, Mistral-7B, Qwen-7B, transferring out-of-domain to SQuAD/WebQuestions at 0.94–0.99 without retraining. Crucially: *attribution mismatches raise error rates by up to 70%*, establishing a direct causal-ish link between "the model lost track of its source" and "the model produced an unfaithful answer." Their AttriWiki pipeline auto-generates training labels by prompting models to recall withheld entities from memory vs. read them from context.

> **Why this matters for CAPM.** This probe is a runtime, model-internal *source signal* that you could read at each agent hop and **fold into the manifest as an additional signed field**. CAPM signs what the wrapper observed at acquisition; this would let each relay agent additionally sign *what its own model actually conditioned on*. A laundering relay that claims "I summarized source X" but whose probe says "this came from parametric memory" is caught — by an AI signal CAPM's crypto cannot produce.

**DataDignity / FakeWiki** (arXiv:2605.05687, May 2026). Introduces FakeWiki: 3,537 fabricated Wikipedia-style articles with QA probes, *source-preserving variants*, and *hard anti-documents* (topically similar, answer-critical facts removed). The design deliberately strips the "easy paths" — lexical overlap, rare names — that let retrieval-based attribution *look* like it works without robustly tracing provenance. Their SteerFuse method compares document-induced *activation directions* against response representations, treating activation-space evidence as complementary to text retrieval. This is the benchmark you would evaluate an internal-provenance signal against, and its anti-document construction is exactly the adversarial pressure your reviewers will demand.

**Probing Language Models on Their Knowledge Source** (Tighidet et al., arXiv:2410.05817, Oct 2024) and **Zhao et al. 2025** (entity-level knowledge flow tracing). The mechanistic foundations: parametric vs. contextual knowledge are routed through *largely distinct attention circuits* and coexist as superposed signals; conflicts resolve by differential accumulation across layers, not by suppression. This is the interpretability ground truth that makes a provenance probe theoretically plausible rather than a lucky correlation.

**Large Language Model Sourcing: A Survey** (arXiv:2510.10161). The umbrella taxonomy distinguishing training-data sourcing, in-context sourcing, and prior-based (watermark/signature) sourcing. Useful for positioning: your internal-provenance signal is *in-context sourcing at runtime*, a relatively underdeveloped cell.

**Unifying Corroborative and Contributive Attributions** (arXiv:2311.12233). The conceptual scaffolding separating "the source *supports* this claim" (corroborative) from "the source *caused* this output" (contributive). CAPM is implicitly corroborative (the manifest records what was cited); the AI-side gap is contributive (what actually drove generation). Naming this distinction sharpens your novelty claim.

---

### Region B — Faithfulness and reasoning provenance: did the transformation preserve the warrant?

CAPM penalizes all unverifiable transformations equally. The AI-side question is whether a transformation was *actually* faithful — which would let warrant degrade gracefully instead of conservatively.

**From Agent Traces to Trust: Evidence Tracing and Execution Provenance in LLM Agents** (arXiv:2606.04990, ~June 2026). The single most important paper for situating your combined work, because it is converging on your exact territory. It synthesizes the emerging "provenance-aware enforcement" family and articulates the governing principle: *unsafe behavior arises from **influence**, not merely from content* — "a webpage may be safe to summarize, but unsafe if its hidden instruction becomes an email recipient." It explicitly proposes organizing provenance-aware agent systems along dimensions of sources, transformations, and actions. **Read this first; it is both your closest neighbor and your best source of vocabulary.** Your CAPM-plus-AI angle differentiates by binding the *influence* signal cryptographically across org boundaries, which this line does within a runtime.

**The FIDES / NeuroTaint / Agent-Sentry family** (Costa et al. 2025; Cai et al. 2026; Sequeira et al. 2026). The execution-provenance / semantic-taint-tracking school. FIDES formalizes agent-level IFC tracking confidentiality and integrity labels enforced *during execution*. NeuroTaint propagates taint across *neural and symbolic* components — notable because it crosses the model boundary that CaMeL's interpreter-level tracking does not. Agent-Sentry tracks whether sensitive tool arguments are influenced by untrusted sources. These are the within-runtime contributive-influence trackers; CAPM is the cross-runtime declared-provenance tracker. The seam between them is open.

**Reasoning Provenance** (Vispute, arXiv:2603.21692, Mar 2026) — already in your library as challenge D2. Distinguishes *mechanical-layer* provenance (checkpoints, traces, PROV-AGENT lineage) from *reasoning-layer* provenance (what beliefs the agent formed and why). Your AI-side contribution is squarely reasoning-layer; CAPM is mechanical-layer. Citing this lets you claim you address *both* layers, which the paper explicitly says current tooling does not.

**Chain-of-thought faithfulness** (T3 in your open-challenges table; Lanham et al., Turpin et al., and the *Lie to Me* / *Why Models Know But Don't Say* line). The hard negative result: a model's stated reasoning is not reliably its actual reasoning. This is a *constraint* on any AI-side faithfulness signal you build — you cannot trust the model's self-report of its sources, which is exactly why a *probe on hidden states* (Region A) is more defensible than asking the model to declare its provenance.

---

### Region C — Adaptive adversaries: the evaluation your reviewers will demand

Your CAPM readiness memo already names "an adaptive adversary evaluation" as a primary open workstream. The AI-side literature is where the adaptive-attack methodology lives.

**Adaptive Attacks Break Defenses Against Indirect Prompt Injection Attacks on LLM Agents** (arXiv:2503.00061). The canonical warning. Analyzes eight IPI defenses (LLM detector, perplexity filtering, instructional prevention, data-prompt isolation, sandwich prevention, paraphrasing, adversarial finetuning) and designs an adaptive attack that breaks *all of them*. The methodological point your reviewers will hold you to: a defense that is only evaluated against static attacks proves nothing. Any CAPM evaluation must include an adversary that knows CAPM's warrant rules and optimizes against them — and the AI-side version of that adversary optimizes the *content* to maximize internalization while keeping the manifest clean.

**A Framework for Formalizing LLM Agent Security** (arXiv:2603.19469, 2026). A fresh formalization of the agent-security game. Useful for stating your adaptive-adversary model with the rigor NDSS expects, and for citing alongside your scoped residual theorem.

**Lying with Truths: Open-Channel Multi-Agent Collusion for Belief Manipulation via Generative Montage** (arXiv:2601.01685, Jan 2026). The most direct AI-layer analogue of CAPM's "information laundering," and the attack CAPM structurally cannot catch. It exploits the model's *drive for narrative coherence*: by feeding fragmented but individually-true facts, attackers induce a benign victim agent to construct a false global conclusion, which it then publishes *in good faith*. They formalize the resulting **trust-amplification / belief-transfer** cascade: downstream agents update on the trusted outputs of multiple victims, driving P(false hypothesis) → 1. Every message is authentic, every source is real, every manifest would verify — and the laundering happens entirely inside the victims' reasoning. **This is your sharpest motivating example for why CAPM needs an AI-side companion: the attack uses only truths, so origin-bounded warrant stays high throughout.**

**Compromising Embodied Agents with Contextual Backdoor Attacks** (arXiv:2408.02882) and **DeepContext: Stateful Real-Time Detection of Multi-Turn Adversarial Intent Drift** (arXiv:2602.16935, 2026). The multi-turn / stateful adversary line — attacks that weaponize the model's own reasoning chain and memory across turns. Relevant if your evaluation considers laundering that builds up over a conversation rather than a single hop.

---

### Region D 

CAPM enforces trust externally because models lack native skepticism. The AI-side question is whether that can change — and what the limits are.

**Attention Knows Whom to Trust** (2025) and **CI-RL / CI-CoT / PrivacyChecker** (Microsoft Research, NeurIPS 2025) — both in your library as D6 and the contextual-integrity line. The "make the receiving agent evaluate its inputs" school: within-agent trust scoring and contextual-integrity internalization via RL. Your open-challenges table already flags the gap: *cross-hop* trust composition and *provenance-as-structured-signal* are unaddressed. An AI-side contribution here would train or steer a model to condition its generation on CAPM's signed warrant field — making warrant a *first-class input to generation*, not just an external gate.

**TrustTrade: Human-Inspired Selective Consensus** (arXiv:2603.22567, 2026). Names the core AI-side failure mode crisply: the *implicit uniform-trust assumption* — agents "treat information retrieved or generated as factual and equally reliable," ignoring variation in source quality, reliability, and temporal relevance. TrustTrade selectively discounts divergent, weakly-grounded, or temporally-inconsistent inputs. This is the behavioral target: a model that *natively* down-weights low-warrant sources the way CAPM down-weights them externally. The interesting research question is whether internalized trust and external warrant *agree* — and what an attacker does in the gap.

**The agentic-RL lines** (Agent-R1, arXiv:2511.14460; Rethinking Agentic RL, arXiv:2604.27859; Constitutional AI / RLAIF foundations). The training machinery if you pursue a "train the model to respect signed warrant" contribution. Note the cost: RL post-training is heavy and may push the paper toward an AI/ML framing that NDSS pre-filters. Likely better as a *steering* or *probe-gated* mechanism than a full retrain.

---

### Region E — Multi-agent belief dynamics: laundering as a network phenomenon

This region reframes laundering from a per-hop property (CAPM's view) to an emergent network property — useful for your ecosystem-cartography analysis and the WGOT dual.

**Decentralized Belief Propagation in LLM Agents** (Hayashi, ICONIP 2025; Springer 2026). Models belief propagation via decentralized Bayesian inference (Metropolis-Hastings Naming Games), showing misinformation resistance can rise from 0.21 to 0.79 while truth propagation stays at 0.98. Establishes that *belief revision dynamics* in agent networks are tractable and that resistance is a tunable network property — a complement to your population-level WGOT cartography.

**You Can't Fool Us: Resilience of LLM-driven Agent Communities to Misinformation** (arXiv:2605.17353, May 2026) and **NetSafe** (Yu et al. 2024, via the Trustworthy LLM Agents survey arXiv:2503.09648). NetSafe specifically analyzes *how hallucinations and misinformation propagate across MAS topologies*, revealing structural dependencies — directly relevant to your "surface-collapse / chokepoint" modeling and to the defender half of WGOT. The resilience paper gives you the benign-baseline: how much laundering a community resists *without* a defense, which is your control condition.

**Prompt Infection** (Lee & Tiwari 2024) and **CORBA** (Zhou et al. 2025) — the self-propagating infectious-attack line, already implied in your attack literature (Flooding Spread). The AI-side framing: these are *contagion* models where the model is the transmission medium, not just the conduit.
