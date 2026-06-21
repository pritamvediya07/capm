# CAPM testbed infrastructure

This document maps the testbed's building blocks to the experiment plan so a new
contributor can find where each experiment plugs in. The standalone testbed runs
with only `cryptography` (offline, deterministic). Every "real" capability (LLMs,
AgentDojo, real-attack corpora, ProVerif) is an **optional plug-in** behind a
lazy import with a deterministic fallback, so nothing here ever blocks a run.

## Layers

| Layer | Module | Purpose | Experiments it serves |
|---|---|---|---|
| Warrant lattice / source classes / transforms | `capm/core/types.py` | the algebra of warrant | all |
| Warranted value (CaMeL descendant) | `capm/core/value.py` | value + provenance chain | E1.2 |
| Cross-org provenance DAG | `capm/provenance/graph.py` | PROV-AGENT extension | E1.2 |
| Signed C2PA-style manifest | `capm/manifest/capm_manifest.py` | hash-linked segments | E2.3, E6.x |
| VC identity / registry (SAGA-aware) | `capm/identity/credentials.py` | Plane-1↔2 binding | E3.3, E2.1 |
| **External warrant evaluator (+ ablation toggles)** | `capm/warrant/evaluator.py` | the defense, E8.x toggles | E1.1, E3.1, E8.x |
| **Pluggable responders + transform classifier** | `capm/agents/responders.py` | deterministic/LLM/scripted | E4.x, E3.1 |
| Agents (adversary-aware, deterministic clock) | `capm/agents/agent.py` | emit/relay/forge | E3.x |
| **Adaptive adversary profiles** | `attacks/adaptive/profiles.py` | class/transform lies, forgery, collusion | E3.x |
| Legacy injectors (abstractions) | `attacks/injectors.py` | weak adversaries | E5.x stand-ins |
| Scenario builder | `capm/benchmark/scenarios.py` | wire a cross-org chain | all |
| **Cross-org harness + adversary catalog** | `capm/benchmark/harness.py` | E5.4 substrate, matrix runner | E1.1, E8.x |
| **Statistics (CI, McNemar, effect size)** | `capm/benchmark/stats.py` | E9.3 reporting | E1.1, E9.3 |
| Runner + metrics (+ attribution instrumentation) | `capm/benchmark/runner.py` | trial -> metrics | all |
| **AgentDojo cross-org bridge (optional)** | `capm/benchmark/agentdojo_crossorg/` | real task suites | E5.4, E1.3, E5.x |
| Seeding / reproducibility | `capm/common/rng.py` | deterministic seeds | E9.1 |
| ProVerif model | `proofs/proverif/capm_manifest.pv` | soundness | E2.1 |

## The adversary catalog (the core of E5.4)

`capm/benchmark/harness.py::adversary_catalog()` returns one `AdversarySpec` per
attack the plan names. Each is a portable `AdversaryProfile` separating **ground
truth** (true source class / true transformation) from what the agent
**declares** in the signed manifest — the gap is the attack:

| Adversary | Lies about | CAPM expected to | Experiment |
|---|---|---|---|
| `admit` / `flooding_spread` / `causality_laundering` | warrant *number* (truthful class) | contain (ceiling caps) | E1.1, E5.x |
| `origin_capture` | the source **class itself** | NOT catch by warrant; still attribute | **E3.2** |
| `lying_transformation` | transformation type (VERBATIM for a regeneration) | detect via content-hash | E3.1 |
| `manifest_forgery_*` | the cryptographic binding | REJECT | E3.3 |
| `collusion` | nothing (many relays co-sign) | keep warrant origin-bounded | E3.4 |

`origin_capture` is the experiment that proves the headline ASR is **not** an
artifact of the attack model: the adversary lies about the class itself, CAPM
cannot catch it by warrant (origin integrity is a separate layer), but the
origin stays attributable — exactly the honest boundary the design doc states.

## How to run real backends

```bash
# real LLM responders (E4.x)
pip install anthropic && export ANTHROPIC_API_KEY=...
python -m experiments.e4_1_real_responders --llm

# real cross-org task suites (E5.4 / E1.3 / E5.x)
pip install agentdojo            # capm.benchmark.agentdojo_crossorg activates

# SAGA real crypto + overhead Monitor (E3.3 / E6.1)
PYTHONPATH=vendor/saga CAPM_USE_SAGA=1 python -m experiments.e6_1_overhead_scaling

# ProVerif soundness (E2.1)
#   install ProVerif, then:
python -m experiments.e2_1_soundness
```

## Adding a new adversary or experiment

1. Add an `AdversaryProfile` constructor in `attacks/adaptive/profiles.py`.
2. Register it in `adversary_catalog()` (`harness.py`).
3. It is now available to `run_matrix(...)` and `run_trial(..., adversary=...)`.
4. Write `experiments/eX_Y_name.py` calling the harness; report with `stats`.
