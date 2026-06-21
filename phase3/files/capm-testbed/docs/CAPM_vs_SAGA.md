# CAPM ↔ SAGA: comparison and integration map

This document compares the CAPM testbed against SAGA
(github.com/gsiros/saga, **accepted at NDSS 2026**) component by component,
and specifies exactly how CAPM grafts onto SAGA's real codebase. The goal is
twofold: (1) **validate** the CAPM testbed against an accepted system, and
(2) build CAPM **on top of** SAGA rather than beside it.

The comparison is grounded in SAGA's actual source, not its paper:
`saga/agent.py`, `saga/provider/provider.py`, `saga/common/crypto.py`,
`saga/common/contact_policy.py`, `saga/ca/CA.py`, `saga/common/overhead.py`,
`saga/local_agent.py`, and `saga/attack_models/adversaries/A1..A8`.

---

## 1. What SAGA actually is (from the code)

SAGA is a **Plane-1** system: it governs *who may talk to whom* and secures the
channel. Concretely:

| SAGA piece | File | What it does |
|---|---|---|
| `Provider` | `provider/provider.py` | Flask service: user `/register`, `/login` (JWT), `/register_agent`, agent `/lookup`, `/access`. Holds contact policies. The central trust authority. |
| `CA` | `ca/CA.py` | X.509 certificate authority; `get_SAGA_CA()`; verifies agent/user certs. |
| `crypto` | `common/crypto.py` | Ed25519 signing keys, X25519 key-agreement, X.509 cert gen/verify, **AES-GCM token encryption** (`encrypt_token`/`decrypt_token`) over a Diffie-Hellman shared key. |
| `Agent` | `agent.py` | The networked agent: `access()`, `lookup()`, `generate_token()`, `token_is_valid()`, `initiate_conversation()`, `receive_conversation()`, `connect()`, TLS sockets. |
| One-time token (OTK) | `agent.py:generate_token` | `{nonce, issue_ts, expiration_ts, communication_quota, recipient_pac}` encrypted with the DH shared key. Enforces a **communication quota** (budget). |
| `contact_policy` | `common/contact_policy.py` | Rulebook matching (`check_rulebook`, `match`, AID-pattern specificity) — the access-control policy SAGA enforces. |
| `Monitor` | `common/overhead.py` | `start/stop/elapsed` overhead timing — how SAGA reports its negligible-overhead result. |
| Attack models | `attack_models/adversaries/A1..A8` | SAGA's own adversaries (malicious agents, spoofing, etc.) used in its evaluation. |
| Formal proofs | `proofs/proverif/*.pv`, `proofs/verifpal/*.vp` | ProVerif + Verifpal proofs of registration and agent-communication secrecy/authentication. |

**Key point SAGA's own related work concedes:** SAGA secures *identity and the
channel*. It does **not** model the *provenance or warrant of the information*
flowing through that channel. A SAGA token says "this message is from a
quota-bounded, authenticated agent you allowed" — it says nothing about where
the *content* originated or whether it is faithful. That is exactly the
Plane-2 gap CAPM fills.

---

## 2. Component-by-component comparison

| Concern | SAGA | CAPM (current testbed) | Relationship |
|---|---|---|---|
| **Plane** | Plane 1 (identity + channel) | Plane 2 (information provenance + warrant) | **Complementary**, not competing |
| **Trust root** | `Provider` + `CA` (X.509) | `CredentialRegistry` (in-process stand-in) | CAPM's registry **should be replaced by** SAGA's Provider/CA |
| **Agent identity** | X.509 cert + Ed25519 keys, AID | `AgentIdentity` (Ed25519) + VC | CAPM VC **should wrap** SAGA's cert |
| **Signing primitive** | `crypto.sign_message` / `verify_signature` (Ed25519) | `AgentIdentity.sign` / `verify` (Ed25519) | **Same primitive** — CAPM can call SAGA's `crypto` directly |
| **Inter-agent unit** | encrypted OTK (quota-bounded) | `CAPMMessage` + `CAPMManifest` | CAPM manifest **rides alongside** the OTK as payload |
| **Access control** | `contact_policy` rulebook match | `EvaluatorPolicy` warrant thresholds | **Orthogonal**: SAGA gates *contact*; CAPM gates *belief on content* |
| **Agent base class** | `local_agent.LocalAgent.run(query, initiating_agent, agent_instance)` | `agents.LocalAgent.run(...)` — **identical signature** | CAPM agents drop into SAGA unchanged |
| **Overhead measurement** | `common/overhead.Monitor` | per-trial `time.perf_counter` | CAPM **should adopt** SAGA's `Monitor` for comparable numbers |
| **Adversary models** | `attack_models/A1..A8` (identity/channel attacks) | `attacks/injectors` (ADMIT, Flooding-Spread, Causality-Laundering — content attacks) | **Disjoint and complementary** attack surfaces |
| **Formal verification** | ProVerif + Verifpal proofs | (none yet) | CAPM **gap** — see §5 |

The headline: **there is no overlap in purpose.** Every place the two systems
touch the same primitive (Ed25519, agent identity, the Provider), CAPM should
*reuse SAGA's implementation*. Every place they differ (warrant, content
provenance, content attacks), CAPM *adds a new plane SAGA does not have*.

---

## 3. Where CAPM grafts onto SAGA (the integration seam)

Five concrete wiring points, smallest to largest:

1. **Identity backed by SAGA.** Replace CAPM's fresh Ed25519 keypair in
   `AgentIdentity` with SAGA's loaded signing key
   (`crypto.load_ed25519_keys`) and bind the VC's `public_key_b64` to the
   agent's SAGA X.509 cert. Signing/verifying then routes through
   `crypto.sign_message` / `crypto.verify_signature`. → `capm/adapters/saga_bridge.py`.

2. **Trust root = the Provider/CA.** `CredentialRegistry.trusts(did)` delegates
   to SAGA: an agent is trusted iff the Provider has a registered, CA-verified
   cert for it. CAPM stops being its own PKI.

3. **Manifest rides with the OTK.** When a SAGA agent calls
   `initiate_conversation` / `receive_conversation`, the CAPM manifest is
   attached as application payload inside the already-encrypted SAGA channel.
   SAGA authorises and secures the hop (Plane 1); CAPM's evaluator runs on
   arrival (Plane 2).

4. **Overhead via SAGA's Monitor.** The benchmark uses
   `saga.common.overhead.Monitor` so CAPM's latency numbers are reported on the
   same instrument SAGA used for its NDSS result — directly comparable.

5. **Two attack planes, one harness.** The combined evaluation runs SAGA's
   `A1..A8` *and* CAPM's content injectors, demonstrating that the two defenses
   cover disjoint surfaces and compose.

---

## 4. What this validates

Running CAPM on SAGA's base validates the testbed in three reviewer-relevant
ways:

* **Realism.** The cryptographic substrate is no longer a stand-in — it is the
  exact code accepted at NDSS 2026. CAPM's signatures, certs, and trust root
  are SAGA's.
* **Composability.** Showing CAPM defends against content attacks that pass
  *straight through* SAGA's authenticated channel demonstrates the Plane-1/
  Plane-2 separation empirically: SAGA accepts the message (sender is a valid,
  allowed agent), and CAPM is what catches the laundered content.
* **Overhead parity.** Measured on SAGA's own Monitor, CAPM's per-hop
  verification overhead can be reported next to SAGA's, supporting the
  "negligible additional overhead" claim.

---

## 5. Gaps this surfaces (the NDSS to-do, made concrete)

The comparison also exposes exactly what CAPM still lacks relative to an
accepted NDSS system:

* **Formal verification.** SAGA has ProVerif/Verifpal proofs of its protocol.
  CAPM should add at least a ProVerif model of the manifest-signing + warrant
  binding, proving the warrant ceiling cannot be bypassed by a signer who does
  not control the origin. (Maps to the design doc's option-(a) claim against
  the self-licensing theorem.)
* **Real adversary.** SAGA's `A1..A8` are concrete adversary *classes*. CAPM's
  injectors should be promoted to the same status: an adaptive adversary that
  knows CAPM exists and tries to forge a manifest, lie about transformation
  type, or acquire a high-warrant origin and poison it.
* **Real model behaviour.** SAGA runs real on-device/cloud LLMs in its agents.
  CAPM's deterministic responders should be swapped for real model calls so the
  transformation classification is genuine.

These three are precisely the NDSS-readiness gaps identified earlier; the SAGA
comparison turns them from abstract advice into concrete, SAGA-shaped tasks.
