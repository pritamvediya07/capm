# CAPM Testbed

**Cross-Agent Provenance Manifests** — a testbed for verifiable,
cross-organisational information provenance in multi-agent AI systems.

This is the experimental harness for the design *Cross-Agent Verifiable
Information Provenance: A Defense Design Built on the 2024–2026 State of the
Art*. It implements the four CAPM components, four comparison baselines, three
laundering-attack injectors, and the S0–S3 evaluation ladder. It is built on
and validated against **SAGA** (`gsiros/saga`, accepted at NDSS 2026).

> **New team member? Read this whole file once, then run the four commands in
> [§2 Five-minute setup](#2-five-minute-setup). If they pass, you have a working
> environment.**

---

## Table of contents

1. [What this is, in one paragraph](#1-what-this-is-in-one-paragraph)
2. [Five-minute setup](#2-five-minute-setup)
3. [Verify your install](#3-verify-your-install)
4. [Running the experiments](#4-running-the-experiments)
5. [The result the testbed produces](#5-the-result-the-testbed-produces)
6. [SAGA integration (two modes)](#6-saga-integration-two-modes)
7. [Repository layout](#7-repository-layout)
8. [How the code maps to the design doc](#8-how-the-code-maps-to-the-design-doc)
9. [The three reference repos and what we did with each](#9-the-three-reference-repos-and-what-we-did-with-each)
10. [Calibration knobs](#10-calibration-knobs)
11. [Extending the testbed](#11-extending-the-testbed)
12. [Troubleshooting](#12-troubleshooting)
13. [Glossary](#13-glossary)

---

## 1. What this is, in one paragraph

When an AI agent passes information across an organisational boundary to another
agent, today's systems verify *who sent it* (Plane 1) but never *where the
content came from or whether it is trustworthy* (Plane 2). CAPM closes that gap:
each agent attaches a signed, field-level **provenance manifest** to what it
emits, bound to its cryptographic identity; a receiving agent runs an
**external warrant evaluator** (outside the language model) that traces trust
back to the origin and down-weights laundered content — independent of who
delivered it. This testbed runs that mechanism against four baselines and three
real-attack abstractions, and validates it on SAGA's cryptographic substrate.

---

## 2. Five-minute setup

**Prerequisites:** Python **3.10+** (3.12 recommended). Nothing else — no
database, no API keys, no network services for the core testbed.

```bash
# 1. Get into the project directory (after extracting the tarball)
cd capm-testbed

# 2. (Recommended) create an isolated environment
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# 3. Install dependencies (just `cryptography` + `pytest`)
pip install -r requirements.txt

# 4. Run the tests — you should see "7/7 passed"
python -m tests.test_capm
```

That's it. If step 4 prints `7/7 passed`, your environment is correct.

> **Always run commands from the `capm-testbed/` root** (the directory that
> contains the `capm/` folder). The code uses `python -m module.path`, which
> resolves packages relative to the current directory. Running from elsewhere
> causes `ModuleNotFoundError`.

---

## 3. Verify your install

Run these three checks. All three should pass on a clean machine.

```bash
# (a) unit + integration tests
python -m tests.test_capm
# expected: PASS x7, then "7/7 passed"

# (b) the headline experiment (laundering containment)
python -m experiments.s1_single_hop_adversarial
# expected: every baseline "ATTACK SUCCEEDED"; capm "contained"; CAPM ASR 0.00

# (c) validation on SAGA's real crypto (vendored — no extra install needed)
PYTHONPATH=vendor/saga CAPM_USE_SAGA=1 python -m experiments.validate_against_saga
# expected: "SAGA active: True", "backend: SAGA crypto", ASR 0.00
```

---

## 4. Running the experiments

The S0–S3 ladder mirrors the design doc's evaluation plan. Run each with
`python -m experiments.<name>`:

| Command | Stage | What it shows |
|---|---|---|
| `python -m experiments.s0_single_hop_honest` | S0 | honest content is accepted; provenance reconstructs across the hop |
| `python -m experiments.s1_single_hop_adversarial` | S1 | CAPM down-weights laundering attacks the baselines accept (the headline) |
| `python -m experiments.s2_nhop_erosion` | S2 | the warrant-erosion curve across N hops (monotone) |
| `python -m experiments.s3_textonly_and_tamper` | S3 | soft-binding recovery, tamper → reject, unknown signer → reject |
| `python -m experiments.run_all` | all | the full comparison table; add `--json results.json` to save |
| `python -m experiments.validate_against_saga` | — | proves CAPM runs on SAGA's substrate |

Run everything at once:

```bash
bash scripts/run_all_experiments.sh
```

---

## 5. The result the testbed produces

```
defense                      ASR  down-wt  utility  prov-surv   lat(ms)
--------------------------------------------------------------------------
no_defense                  1.00     0.00     1.00       1.00     0.002
identity_only               1.00     0.00     1.00       1.00     0.003
flat_provenance             1.00     0.00     1.00       1.00     0.004
camel_single_runtime        1.00     0.00     1.00       1.00     0.010
capm                        0.00     1.00     0.75       1.00     0.734
```

Reading it: **ASR** = laundering attack success rate (lower is better);
**down-wt** = fraction of attacks correctly down-weighted; **utility** =
fraction of honest content accepted; **prov-surv** = provenance reconstructed;
**lat** = per-hop verification latency. Every baseline is fooled by all attacks
(ASR 1.00); CAPM is fooled by none (ASR 0.00) while reconstructing the full
chain at sub-millisecond cost.

> `utility = 0.75` is **expected and tunable**, not a bug: honest content
> erodes below the accept floor after ~2 paraphrase hops and is *down-weighted*
> rather than accepted. The erosion rate is a research knob — see
> [§10 Calibration knobs](#10-calibration-knobs).

---

## 6. SAGA integration (two modes)

CAPM is built **on top of** SAGA, not beside it. SAGA provides Plane 1
(identity, CA, secure channel); CAPM adds Plane 2 (provenance + warrant).

**Mode A — standalone (default).** In-process Ed25519 identities, a local
credential registry. No SAGA needed. This is what you get after [§2](#2-five-minute-setup).

**Mode B — SAGA-backed crypto (included, no extra install).** The lightweight
SAGA modules CAPM grafts onto are **vendored** under `vendor/saga/`
(`crypto`, `overhead`, `logger`, `local_agent`, `CA`, plus a `config` stub), so
you can validate on SAGA's *real* code without the full Flask/Mongo Provider:

```bash
PYTHONPATH=vendor/saga CAPM_USE_SAGA=1 python -m experiments.validate_against_saga
```

This routes signing through SAGA's actual `saga.common.crypto` and measures
overhead on SAGA's actual `saga.common.overhead.Monitor`. The security result
is identical to Mode A, which proves the defense doesn't depend on a crypto
stand-in.

**Mode C — full live SAGA (for deployment, not required for experiments).**
Clone the complete SAGA and run its Provider:

```bash
git clone https://github.com/gsiros/saga.git vendor/saga-full
pip install -e vendor/saga-full
export CAPM_USE_SAGA=1
```

Then point the trust root at SAGA's Provider/CA. See `docs/INTEGRATION.md` for
wiring and `docs/CAPM_vs_SAGA.md` for the component-by-component comparison.

---

## 7. Repository layout

```
capm-testbed/
├── README.md                  ← you are here
├── requirements.txt           cryptography + pytest
├── setup.py                   package metadata (Python 3.10+)
├── configs/
│   └── default.yaml           evaluator thresholds + penalty knobs
├── capm/                      the library
│   ├── core/
│   │   ├── types.py           warrant lattice, transformations, source classes
│   │   └── value.py           WarrantedValue (descendant of CaMeL Capabilities)
│   ├── provenance/
│   │   └── graph.py           cross-org provenance DAG (PROV-AGENT extension)
│   ├── manifest/
│   │   └── capm_manifest.py    C2PA-style hash-linked signed manifest
│   ├── identity/
│   │   └── credentials.py     VC-like identity, signing, registry (SAGA-aware)
│   ├── warrant/
│   │   └── evaluator.py        Component 4 — the external warrant evaluator
│   ├── agents/
│   │   └── agent.py           SAGA-aligned CAPM agents + message envelope
│   ├── baselines/
│   │   └── baselines.py        the four comparison defenses
│   ├── benchmark/
│   │   ├── scenarios.py        multi-hop multi-org chain builder
│   │   └── runner.py           trial runner + metrics
│   └── adapters/
│       ├── saga_adapter.py     high-level "extend SAGA" notes
│       └── saga_bridge.py      real bridge to SAGA crypto/CA/Monitor
├── attacks/
│   └── injectors.py           ADMIT / Flooding-Spread / Causality-Laundering
├── experiments/               S0–S3 + run_all + validate_against_saga
├── tests/
│   └── test_capm.py           pytest suite (7 tests)
├── scripts/
│   └── run_all_experiments.sh runs tests + every experiment
├── docs/
│   ├── ARCHITECTURE.md        runtime flow + design decisions
│   ├── CAPM_vs_SAGA.md        component comparison + integration seam
│   └── INTEGRATION.md         SAGA + real-LLM wiring
└── vendor/
    └── saga/                  lightweight SAGA modules (for Mode B)
```

---

## 8. How the code maps to the design doc

| Design-doc component | Module | Built on (SOTA) | Extends it by |
|---|---|---|---|
| 1. Cross-org provenance record | `capm/provenance/graph.py`, `capm/core/value.py` | PROV-AGENT; CaMeL `Capabilities` | field-level claims, per-edge transformation type, org-boundary edges, adversarial origin-warrant ceilings |
| 2. Signed container | `capm/manifest/capm_manifest.py` | C2PA v2.3 | hash-linked **chained, multi-agent** manifest with soft-binding |
| 3. Identity binding | `capm/identity/credentials.py`, `capm/adapters/saga_bridge.py` | DIDs/VCs; SAGA | binds the manifest signature to the agent's VC / SAGA cert |
| 4. External warrant evaluator | `capm/warrant/evaluator.py` | ARM; the SoK dynamic-authz agenda | warrant computed **outside the model**, monotone erosion, soft-binding check |

---

## 9. The three reference repos and what we did with each

- **SAGA** (`gsiros/saga`) — *extended.* Provides Plane 1; CAPM adds Plane 2.
  Real bridge in `capm/adapters/saga_bridge.py`; lightweight modules vendored.
- **CaMeL** (`google-research/camel-prompt-injection`) — *pattern ported, not
  imported.* `WarrantedValue` descends from CaMeL's frozen `Capabilities`. We
  reimplemented the pattern cleanly and did not depend on its interpreter.
  `SingleRuntimeCaMeLEvaluator` reproduces its cross-org blind spot as a baseline.
- **LLM-Latent-Source-Preferences** (`aflah02/...`) — *eval reference.* Motivates
  the `SourceClass` warrant ceilings (models have hidden source biases, so origin
  warrant must be external). Not a runtime dependency.

---

## 10. Calibration knobs

All in `configs/default.yaml` (and `EvaluatorPolicy` in
`capm/warrant/evaluator.py`):

- `min_accept` / `min_down_weight` — warrant floors for ACCEPT / DOWN_WEIGHT.
- `boundary_penalty_per_cross` — warrant lost per *verified* org boundary
  (default 0: a verified crossing doesn't erode warrant; transformations do).
- `unverified_boundary_penalty` — penalty when signatures aren't required.
- transformation `fidelity_penalty` (in `capm/core/types.py`) — how much each
  transformation type (verbatim/summary/paraphrase/…) costs.

Tuning these trades **utility** against **laundering resistance**. Producing
that trade-off curve (and the per-hop erosion curve from `s2_nhop_erosion.py`)
is itself a research result — the open challenge of *how fast warrant should
erode per honest hop*.

---

## 11. Extending the testbed

- **Real LLM agents.** Swap the deterministic `responder` in
  `capm/agents/agent.py` for a real model call returning
  `(content, TransformationType)`. See `docs/INTEGRATION.md`.
- **Real attacks.** Replace the abstractions in `attacks/injectors.py` with the
  genuine ADMIT / Flooding-Spread repos run end-to-end.
- **Adaptive adversary.** Add an attacker that knows CAPM exists (forges
  manifests, lies about transformation type, targets a high-warrant origin).
- **New baselines / metrics.** Add to `capm/baselines/baselines.py` and
  `capm/benchmark/runner.py`; both use the same `evaluate(manifest, text)`
  interface so they slot in without touching agent code.

---

## 12. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: capm` | not in the project root | `cd` into `capm-testbed/` (the dir with `capm/`) |
| `ModuleNotFoundError: cryptography` | deps not installed | `pip install -r requirements.txt` |
| `validate_against_saga` says `SAGA active: False` | env not set | prefix with `PYTHONPATH=vendor/saga CAPM_USE_SAGA=1` |
| tests fail only in your shell | stale bytecode / wrong Python | `find . -name __pycache__ -exec rm -rf {} +`; check `python --version` ≥ 3.10 |
| `pip` blocked / externally-managed env | system Python | use a venv (`python3 -m venv .venv`) or add `--break-system-packages` |
| numbers differ slightly run-to-run | latency is wall-clock | only `lat(ms)` varies; ASR/down-wt/utility are deterministic |

---

## 13. Glossary

- **Plane 1 / Plane 2** — identity (who sent it) vs. information provenance
  (where the content came from, is it faithful). SAGA is Plane 1; CAPM is Plane 2.
- **Warrant** — the justification linking a claim to its source; a level on the
  lattice `NONE < WEAK < DERIVED < MODERATE < STRONG`.
- **Warrant ceiling** — the max warrant a source class permits; an editable page
  can never exceed WEAK no matter who relays it. This is what defeats laundering.
- **Manifest** — the hash-linked chain of signed segments travelling with a
  message; each segment is one agent's signed contribution.
- **ASR** — attack success rate (fraction of laundering attacks accepted).
- **Soft-binding** — a watermark/perceptual hash that lets provenance be checked
  even after extrinsic metadata is stripped (the "final text survives" case).
- **Laundering** — low-warrant content gaining apparent trust by passing through
  trusted agents; the core attack CAPM defends against.
