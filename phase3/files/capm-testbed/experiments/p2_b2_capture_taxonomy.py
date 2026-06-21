"""P2-B2 — Origin-Capture Taxonomy.

B1 localised CAPM's entire residual to a single vector: origin-class capture
(Theorem 2). B2 opens that vector up. It enumerates the concrete ways an attacker
can actually *execute* a capture, scores each by **work factor** (difficulty),
records whether **SAGA's Plane-1 identity layer blocks it**, estimates its
**detectability**, and then **simulates the unblocked vectors in the CAPM testbed**
to measure the empirical Attack Success Rate (ASR) each one buys at runtime.

The central finding it sets up: from CAPM's *runtime* view every successful
capture looks the same (a trusted identity presenting a high source class), so
CAPM's ASR is governed only by chain erosion — the real discriminators between
vectors are the analytic columns (difficulty, SAGA-blocked, detectability), not
CAPM itself. That is *why* Goal 2 must push the defense up into Plane-1 / origin
attestation (B3–B6), not into more warrant math.

Modelling choices are made explicit per vector (the `captured_class` an attacker
realistically reaches, with a rationale) and the worst case (principal-facing,
1-hop) is always reported alongside the eroded average, so nothing hides behind a
single number.

Run:
    python3 -m experiments.p2_b2_capture_taxonomy
"""

from __future__ import annotations

import csv
import dataclasses
import os

from capm.benchmark import stats
from capm.core.types import SourceClass, TransformationType, WarrantLevel
from capm.identity.credentials import AgentIdentity, CredentialRegistry
from capm.manifest.capm_manifest import CAPMManifest
from capm.warrant.evaluator import Decision, EvaluatorPolicy, WarrantEvaluator

OUT_DIR = os.path.join("results", "p2", "b2")
_CLOCK = 1_700_000_000.0
CAPTURE_DEPTHS = [1, 2, 3, 4, 5]   # hop position of the captured origin (1 = principal-facing)


@dataclasses.dataclass
class CaptureVector:
    name: str
    description: str
    difficulty: int                 # work factor, 1 (trivial) … 5 (nation-state)
    blocked_by_saga: bool
    saga_rationale: str
    detectability: str              # High | Medium | Low
    detect_rationale: str
    captured_class: SourceClass     # class the attacker realistically presents
    true_class: SourceClass         # ground-truth class of the content
    class_rationale: str
    # how it manifests cryptographically in the testbed:
    key_mismatch: bool              # True = impersonates a trusted DID with the WRONG key


def taxonomy() -> list[CaptureVector]:
    return [
        CaptureVector(
            name="typosquatting",
            description="Register a look-alike agent/DID resembling a trusted "
                        "authoritative origin to slip into a verifier's allowlist.",
            difficulty=2,
            blocked_by_saga=True,
            saga_rationale="SAGA binds DIDs to CA-issued keys, so trust is by "
                           "exact key, not by name string. A look-alike carries a "
                           "DIFFERENT key than the genuine origin and cannot present "
                           "the trusted entry's signature → rejected at Plane 1 "
                           "(and again by CAPM's exact VC-key match).",
            detectability="High",
            detect_rationale="Name divergence and an unrecognised key are trivially "
                             "auditable; the CA never issued the authoritative name.",
            captured_class=SourceClass.AUTHORITATIVE_API,
            true_class=SourceClass.EDITABLE_SOURCE,
            class_rationale="Aims for the top tier but never reaches CAPM: identity "
                            "binding rejects the wrong key.",
            key_mismatch=True),
        CaptureVector(
            name="stale_allowlist",
            description="Use a once-trusted origin whose credential was revoked/"
                        "expired but still lingers in the verifier's registry "
                        "(revocation-propagation lag).",
            difficulty=3,
            blocked_by_saga=False,
            saga_rationale="SAGA supports revocation, but propagation is not "
                           "instantaneous; during the lag the stale entry is still "
                           "cryptographically valid and trusted. Plane-1 closes "
                           "this only with fresh revocation checks.",
            detectability="Medium",
            detect_rationale="Visible in revocation lists / cert-expiry audits, but "
                             "only if the verifier actively checks freshness.",
            captured_class=SourceClass.AUTHORITATIVE_API,
            true_class=SourceClass.PUBLIC_WEBPAGE,
            class_rationale="The lingering entry was a genuine top-tier origin, so "
                            "the attacker presents AUTHORITATIVE_API.",
            key_mismatch=False),
        CaptureVector(
            name="credential_leak",
            description="Obtain the legitimate signing key of a trusted authoritative "
                        "origin (key theft, phishing, supply-chain, insider).",
            difficulty=4,
            blocked_by_saga=False,
            saga_rationale="A stolen-but-genuine key passes every Plane-1 check — "
                           "valid signature, trusted DID, valid cert. SAGA cannot "
                           "distinguish legitimate from stolen use of its own key.",
            detectability="Low",
            detect_rationale="Signatures are valid and the DID is trusted; only "
                             "key-use anomaly / behavioural monitoring (B6) can flag it.",
            captured_class=SourceClass.AUTHORITATIVE_API,
            true_class=SourceClass.EDITABLE_SOURCE,
            class_rationale="Holds a real top-tier key → presents AUTHORITATIVE_API.",
            key_mismatch=False),
        CaptureVector(
            name="legitimate_origin_compromise",
            description="Subvert the genuine authoritative origin itself (poison its "
                        "data store or prompt-inject its agent) so it HONESTLY signs "
                        "malicious content with its real key and real class.",
            difficulty=5,
            blocked_by_saga=False,
            saga_rationale="The identity is genuine and the class is truthful — there "
                           "is NO identity anomaly at all. SAGA sees a legitimate "
                           "agent doing legitimate signing.",
            detectability="Low",
            detect_rationale="Nothing in identity or provenance is off; only content/"
                             "behavioural anomaly detection has any purchase. The "
                             "subtlest vector — not even a class lie.",
            captured_class=SourceClass.AUTHORITATIVE_API,
            true_class=SourceClass.AUTHORITATIVE_API,
            class_rationale="Genuinely authoritative class (no class lie); the "
                            "compromise is of the content, not the attestation.",
            key_mismatch=False),
        CaptureVector(
            name="trust_bootstrap_abuse",
            description="Abuse the onboarding/enrolment process to get a malicious "
                        "agent admitted and to claim a high source class.",
            difficulty=3,
            blocked_by_saga=False,
            saga_rationale="SAGA authenticates *identity* at enrolment but does NOT "
                           "attest the *source class* an agent may claim — that is a "
                           "Plane-2 binding SAGA leaves open. A validly enrolled "
                           "agent can still over-declare its class.",
            detectability="Medium",
            detect_rationale="Anomalous new-origin / enrolment patterns are "
                             "detectable by origin-anomaly monitoring (B6), but not "
                             "by signature checks.",
            captured_class=SourceClass.FIRST_PARTY_DB,
            true_class=SourceClass.UNTRUSTED_TOOL,
            class_rationale="Bootstrapping into top-tier authoritative classes "
                            "requires strong proofs that are hard to fake; a "
                            "moderate internal class (FIRST_PARTY_DB) is the "
                            "realistic reach.",
            key_mismatch=False),
    ]


# ---------------------------------------------------------------------------
# Testbed simulation — build a signed capture manifest and evaluate it
# ---------------------------------------------------------------------------
def _simulate_capture(vec: CaptureVector, depth: int) -> dict:
    """Build a fully-signed chain where a captured origin (at `depth` hops from
    the principal) presents `vec.captured_class`, then evaluate with live CAPM.

    `depth` = number of agents; depth 1 means the captured origin faces the
    principal directly. Relays paraphrase (the harness default), eroding 1 level
    per hop — so the captured warrant decays with chain length.
    """
    registry = CredentialRegistry()
    m = CAPMManifest()
    content = f"malicious::{vec.name}"
    prev_org = "org-principal"

    for i in range(depth):
        did = "did:capm:trusted-origin" if i == 0 else f"did:capm:relay-{i}"
        ident = AgentIdentity(did=did, org=f"org-{i}")
        if i == 0 and vec.key_mismatch:
            # impersonation: the registry holds the GENUINE origin's key for this
            # DID; the attacker signs with its own key + embeds its own VC → the
            # evaluator's exact VC-key match fails → REJECT.
            genuine = AgentIdentity(did=did, org=f"org-{i}")
            registry.register(genuine)               # genuine key on record
        else:
            registry.register(ident)                 # trusted (valid) signer
        t = TransformationType.VERBATIM if i == 0 else TransformationType.PARAPHRASE
        m.append_segment(
            identity=ident, content=content, transformation=t,
            from_org=prev_org, to_org=f"org-{i}",
            origin_source_class=vec.captured_class if i == 0 else None,
            asserted_origin_warrant=vec.captured_class.warrant_ceiling if i == 0 else None,
            timestamp=_CLOCK + i)
        prev_org = f"org-{i}"

    verdict = WarrantEvaluator(registry, EvaluatorPolicy()).evaluate(m, delivered_text=content)
    succeeded = verdict.decision == Decision.ACCEPT
    return {"depth": depth, "decision": verdict.decision.value,
            "warrant": int(verdict.warrant), "succeeded": succeeded,
            "signature_ok": verdict.signature_ok}


def simulate_vector(vec: CaptureVector) -> dict:
    per_depth = [_simulate_capture(vec, d) for d in CAPTURE_DEPTHS]
    n = len(per_depth)
    succ = sum(r["succeeded"] for r in per_depth)
    asr = succ / n
    lo, hi = stats.proportion_ci(succ, n)
    principal_facing = per_depth[0]["succeeded"]      # depth == 1
    return {"per_depth": per_depth, "asr": asr, "asr_lo": lo, "asr_hi": hi,
            "n": n, "succ": succ, "asr_principal_facing": 1.0 if principal_facing else 0.0}


def main():
    print("=" * 86)
    print("P2-B2 — Origin-Capture Taxonomy")
    print("=" * 86)

    vecs = taxonomy()
    rows = []
    for v in vecs:
        sim = simulate_vector(v)
        rows.append({
            "vector": v.name,
            "difficulty_1to5": v.difficulty,
            "blocked_by_saga": v.blocked_by_saga,
            "detectability": v.detectability,
            "captured_class": v.captured_class.value,
            "true_class": v.true_class.value,
            "testbed_asr_hops1to5": round(sim["asr"], 4),
            "asr_ci_lo": round(sim["asr_lo"], 4),
            "asr_ci_hi": round(sim["asr_hi"], 4),
            "asr_principal_facing": sim["asr_principal_facing"],
            "succeeded_depths": sum(r["succeeded"] for r in sim["per_depth"]),
            "n_depths": sim["n"],
            "saga_rationale": v.saga_rationale,
            "detect_rationale": v.detect_rationale,
            "class_rationale": v.class_rationale,
            "description": v.description,
        })

    # console table
    print(f"\n{'vector':<28}{'diff':>5}{'SAGA-blk':>9}{'detect':>8}"
          f"{'cap.class':>18}{'ASR(1-5)':>10}{'ASR_PF':>8}")
    print("-" * 86)
    for r in rows:
        print(f"{r['vector']:<28}{r['difficulty_1to5']:>5}"
              f"{str(r['blocked_by_saga']):>9}{r['detectability']:>8}"
              f"{r['captured_class']:>18}{r['testbed_asr_hops1to5']:>10.2f}"
              f"{r['asr_principal_facing']:>8.2f}")
    print("-" * 86)

    # per-depth detail
    print("\nPer-capture-depth detail (decision @ hop position; 1 = principal-facing):")
    for v, r in zip(vecs, rows):
        sim = simulate_vector(v)
        cells = "  ".join(f"h{d['depth']}={d['decision'][:4]}({d['warrant']})"
                          for d in sim["per_depth"])
        print(f"  {v.name:<28} {cells}")

    os.makedirs(OUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUT_DIR, "taxonomy.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # also dump the full per-depth grid for the figure
    grid_path = os.path.join(OUT_DIR, "capture_depth_grid.csv")
    with open(grid_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["vector", "depth", "decision", "warrant", "succeeded"])
        for v in vecs:
            for d in simulate_vector(v)["per_depth"]:
                w.writerow([v.name, d["depth"], d["decision"], d["warrant"], d["succeeded"]])

    n_blocked = sum(r["blocked_by_saga"] for r in rows)
    n_unblocked = len(rows) - n_blocked
    print(f"\nSAGA blocks {n_blocked}/{len(rows)} vectors (typosquatting); "
          f"{n_unblocked} residual vectors reach CAPM.")
    print("Finding: among unblocked vectors CAPM's ASR is governed by chain "
          "erosion, NOT by which vector was used — discrimination lives in the "
          "difficulty/detectability columns, motivating B3–B6.")
    print(f"CSV: {csv_path} ; {grid_path}")
    print("=" * 86)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
