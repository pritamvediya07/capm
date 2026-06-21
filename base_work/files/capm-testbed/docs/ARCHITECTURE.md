# CAPM Architecture

This document explains the runtime flow and the key design decisions.

## The chain

The testbed models the design doc's worked example as a chain of agents, each
in its own organisation:

```
  Source S ──► agent_tail (org-C) ──► agent_1 (org-B) ──► agent_0 (org-A) ──► Principal
              [origin segment]      [paraphrase seg]    [paraphrase seg]
```

Every arrow is a cross-organisation boundary — the boundary existing defenses
(CaMeL, ARM, PROV-AGENT) cannot see across. A query travels down the chain via
`CAPMAgent.handle`; each agent appends a **signed manifest segment** to the
message on its way back up.

## What travels: the message + manifest

```python
CAPMMessage(content, manifest, sender_did, sender_org)
```

`manifest` is a `CAPMManifest` = a list of hash-linked `ManifestSegment`s.
Each segment is signed by the emitting agent's `AgentIdentity` (Ed25519 key
bound to its `VerifiableCredential`). The first segment is the **origin
segment**: it declares the source class and the asserted origin warrant.

## What the receiver does (the defense)

`WarrantEvaluator.evaluate(manifest, delivered_text)` runs four steps, all
**outside the parametric model** — this is the option-(a) stance against the
Semantic Laundering self-licensing theorem:

1. **Signature verification** over the whole hash-linked chain, each segment's
   DID checked against the `CredentialRegistry` (the SAGA-Provider stand-in).
   Any broken signature or hash-link → `REJECT`.
2. **Warrant scoring.** Start at the origin's warrant, *capped by the declared
   source class's ceiling* (a lying origin cannot claim more than its class
   permits — this is what defeats laundering). Then subtract each
   transformation's fidelity penalty and any unverified-boundary penalty.
   Monotone non-increasing by construction.
3. **Soft-binding check.** Recompute the watermark/perceptual hash of the
   delivered text and compare to the manifest head. Mismatch → the text was
   regenerated off-manifest → `QUARANTINE`.
4. **Policy decision.** `ACCEPT` / `DOWN_WEIGHT` / `QUARANTINE` against the
   warrant floors.

The decision depends on the **origin warrant and transformation fidelity, not
on who delivered the message**. That is the whole point: a claim that
originated on an editable page keeps its low ceiling no matter how many trusted
agents relayed it.

## Why relays forward low-warrant content

Intermediary agents forward any **signature-valid** content even if its warrant
is low; only the principal-facing evaluator makes the accept/quarantine call.
If relays dropped low-but-valid content, the chain would truncate and the
principal would never see the provenance — the opposite of what CAPM wants.
Relays drop only on `REJECT` (broken signature / untrusted signer / tamper).

## The warrant lattice

```
NONE(0) < WEAK(1) < DERIVED(2) < MODERATE(3) < STRONG(4)
```

Source-class ceilings:

| Source class | Ceiling |
|---|---|
| authoritative_api, verified_document | STRONG |
| first_party_db, public_webpage | MODERATE |
| editable_source, untrusted_tool, model_memory | WEAK |
| unknown | NONE |

Transformation fidelity penalties: verbatim/extraction 0; summary/paraphrase/
composition 1; generation 4 (collapses to NONE unless re-grounded).

## How the attacks are defeated

| Attack | Mechanism | Why CAPM contains it |
|---|---|---|
| ADMIT | poisoned content at an editable origin, asserts STRONG | ceiling caps it to WEAK; below accept floor → down-weight |
| Flooding Spread | counterfactual in model memory, re-relayed | model_memory ceiling = WEAK; relays preserve the low origin |
| Causality Laundering | warrant "borrowed" from a denial, source UNKNOWN, asserts STRONG | UNKNOWN ceiling = NONE → quarantine |
