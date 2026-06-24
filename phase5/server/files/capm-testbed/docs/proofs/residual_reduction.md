# Theorem 2 — Residual Reduction (Origin-Class Capture is the Unique Residual)

**Companion experiment:** [`experiments/p2_b1_localisation.py`](../../experiments/p2_b1_localisation.py)
· **Builds on:** Lemma 1 (Monotonicity), [`experiments/p2_w1_monotonicity.py`](../../experiments/p2_w1_monotonicity.py)
· **Mechanism:** [`capm/warrant/evaluator.py`](../../capm/warrant/evaluator.py)

This note localises the *entire* residual attack surface of CAPM to a single
named vector. It is the Goal-2 backbone: once we know there is exactly one way
in, the rest of Goal 2 (B2–B6) is the study of that one way.

---

## 1. Setup and notation

Let the warrant lattice be `W = {NONE=0, WEAK=1, DERIVED=2, MODERATE=3, STRONG=4}`
with the usual total order. A delivered message carries a hash-linked manifest
`M = ⟨s₀, s₁, …, s_{k-1}⟩` of signed segments, `s₀` the **origin** segment
(the tail, nearest the real-world source) and `s_{k-1}` the head (principal-facing).

Each segment `sᵢ` declares:
- `agent_didᵢ`, `agent_vcᵢ` — the signer's identity (Plane 1);
- `transformationᵢ ∈ T` with fidelity penalty `pen(transformationᵢ) ≥ 0`;
- `content_hashᵢ`, `prev_segment_hashᵢ` — the hard binding;
- and, **only for the origin** `s₀`: `origin_source_classᵢ ∈ SC` and
  `asserted_origin_warrantᵢ ∈ W`.

For a source class `c ∈ SC` write `ceil(c) ∈ W` for its warrant ceiling
(`SourceClass.warrant_ceiling`). Let `c*` denote the **true** source class of the
content actually at the origin, and `ĉ = origin_source_class(s₀)` the **declared**
class. An honest origin declares `ĉ = c*`.

The receiver runs `WarrantEvaluator.evaluate(M)`, which (i) verifies every
signature and the hash-linkage back to a trusted registry, then (ii) computes a
final warrant `w(M)` by `_score_warrant`.

**Scoring rule (the implementation, verbatim in algebra).**
```
w₀ = min( asserted_origin_warrant(s₀),  ceil(ĉ) )          # origin cap
wᵢ = max( 0,  wᵢ₋₁ − pen(effective_transformationᵢ) )      # i = 1 … k-1
w(M) = w_{k-1}
```
where `effective_transformationᵢ` is `GENERATION` if `sᵢ` claims a fidelity-
preserving transform (`VERBATIM`/`EXTRACTION`) but `content_hashᵢ ≠ content_hashᵢ₋₁`
(the transformation-lie rule), and `transformationᵢ` otherwise.

**Attack goal (laundering).** The adversary wins iff it gets the receiver to
assign the delivered content a warrant **strictly above what its true origin
permits**:
```
        w(M) > ceil(c*).                              (★)
```
Anything at or below `ceil(c*)` is exactly the warrant an honest actor with that
source would also obtain — no laundering has occurred.

---

## 2. Lemma 1 (Monotonicity), restated

For every segment update, `pen(·) ≥ 0` and the clamp is non-increasing, so
`wᵢ ≤ wᵢ₋₁` for all `i`. Hence

> **Lemma 1.** `w(M) ≤ w₀`. *(Machine-checked, P2-W1: 50,335 checks, 0 violations.)*

In particular `w(M) ≤ w₀ ≤ ceil(ĉ)` whenever the origin ceiling is enforced.

---

## 3. Theorem 2 (Residual Reduction)

> **Theorem 2.** Suppose a manifest `M` passes `evaluate` (all signatures and
> hash-links verify) and achieves `w(M) > ceil(c*)`, i.e. the laundering goal
> (★). Then at least one of the following holds:
>
> **(a) Signature forgery** — some segment's signature verified under a key the
>     adversary does not legitimately control; or
>
> **(b) Origin-class capture** — `ĉ ≠ c*` with `ceil(ĉ) > ceil(c*)`: the manifest
>     declares (and validly signs, under a key the adversary *does* control) an
>     origin class strictly stronger than the content's true class.
>
> Equivalently: **modulo signature unforgeability, origin-class capture (b) is the
> unique residual.**

### Proof

By Lemma 1 and the origin cap,
```
        w(M) ≤ w₀ ≤ ceil(ĉ).                          (1)
```
Combining (1) with the hypothesis (★):
```
        ceil(c*) < w(M) ≤ ceil(ĉ)   ⇒   ceil(ĉ) > ceil(c*)   ⇒   ĉ ≠ c*.   (2)
```
So the **declared** origin class is strictly stronger than the **true** one: the
origin assertion is false. It remains to show this false assertion can only be
present in a verifying manifest via (a) or (b).

The origin assertion `(origin_source_class, asserted_origin_warrant)` lives inside
`s₀.claim_bytes()`, which is exactly the byte-string the origin's signature
covers, and the signature is checked against the VC registered for
`agent_did(s₀)`. Therefore a manifest carrying the false `ĉ` and passing
`_verify_signatures` must contain a **valid signature over those false bytes**
under `agent_did(s₀)`. There are only two ways to produce such a signature:

1. The adversary **holds the legitimate signing key** for `agent_did(s₀)` — it
   controls (or has compromised, or was issued) an identity that the registry
   trusts, and uses it to attest `ĉ`. This is precisely **origin-class capture (b)**:
   a trusted origin identity emitting a class stronger than the content deserves.
   (Whether the key was stolen, the principal suborned, or a real authoritative
   agent misused — all are instances of "capturing an authoritative origin." The
   taxonomy of *how* is P2-B2.)

2. The adversary **does not hold that key** yet still presents a verifying
   signature over the false bytes. By definition this is **signature forgery (a)**:
   an existential forgery against the origin's Ed25519 key, which is exactly what
   the EUF-CMA security of Ed25519 makes infeasible (and what the ProVerif model
   `proofs/proverif/capm_manifest.pv` machine-checks: `OriginAccepted ⇒
   OriginSigned`).

No third possibility exists: the false `ĉ` must be signed, and a signature is
either produced with the key (1 = b) or without it (2 = a). ∎

### What the proof *uses* (and therefore what could break it)

The argument leans on exactly three properties, each independently validated:
- **`pen(·) ≥ 0` and the non-increasing clamp** (Lemma 1 / P2-W1) — gives (1).
- **The origin cap reads `ceil(ĉ)` from `s₀` only** — a *mid-chain* class
  re-declaration cannot raise `w₀`. (Probed adversarially in P2-B1.)
- **The origin assertion is inside the signed bytes** — so a class lie cannot be
  injected without a key. (Probed by the forgery battery, E2.3 / E3.3.)

If any of these failed, the residual would be wider than (b). P2-B1 stress-tests
all three by search.

---

## 4. Corollary and consequences

> **Corollary (Unique Residual).** Under the standing assumption that Ed25519 is
> EUF-CMA-secure (so (a) is infeasible), every successful laundering attack on
> CAPM is an instance of **origin-class capture (b)**. The residual attack
> surface is one-dimensional.

This reframes the Phase-1 observation that the `origin_capture` adversary is the
only one marked `expects_contained = False`: it is not an embarrassing exception
but the **predicted and unique** residual. Two immediate consequences shape the
rest of Goal 2:

1. **Defensive focus.** Hardening CAPM ≡ hardening *origin-class attestation*:
   identity assurance, class-attestation provenance, key custody, revocation.
   Nothing else can move warrant above `ceil(c*)`.

2. **Attack focus.** The interesting offensive question is no longer "can warrant
   be laundered?" (no — Lemma 1) but "**which** authoritative origin is cheapest
   to capture?" — the warrant-to-cost targeting that P2-B3 (WGOT) formalises.

---

## 5. Empirical backing (P2-B1)

[`experiments/p2_b1_localisation.py`](../../experiments/p2_b1_localisation.py)
searches `10,000` random adversarial chains that use **every lever except**
class-lying and key-forging — number over-claims, arbitrary transformation
sequences, transformation lies, variable length and boundary crossings, and
*mid-chain origin re-declarations* designed to probe the third property above —
and checks the laundering goal (★). Theorem 2 predicts **0 successes**.

To show the search has teeth (that 0 is a finding, not a vacuum), two **negative
controls** re-run the identical search with the residual deliberately opened:
- *class-capture allowed* (the adversary may declare `ĉ > c*`) — predicts > 0;
- *origin ceiling disabled* (`enforce_origin_ceiling = False`) — predicts > 0.

See the P2-B1 entry in `PHASE2_IMPLEMENTATION_REPORT.md` for the measured rates.
