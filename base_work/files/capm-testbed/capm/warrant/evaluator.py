"""Receiver-side warrant evaluation (Component 4 - the core defense).

This module realises the design doc's option-(a) stance against the Semantic
Laundering negative result (Theorem of Inevitable Self-Licensing,
arXiv:2601.08333): **warrant is established by external, verifiable
computation, never by the receiving model's own in-context judgement.** The
parametric LLM never self-licenses; it consults this evaluator's verdict.

The evaluator does four things before a receiving agent forms beliefs:

1. **Signature verification** over the whole hash-linked manifest chain, back
   to a trusted credential registry (SAGA Provider stand-in). Any break ->
   reject.
2. **Warrant scoring**: warrant starts at the origin source ceiling and is
   monotonically non-increasing along the chain - each transformation applies
   its fidelity penalty, each org-boundary crossing applies a boundary
   penalty. This makes the Warrant Erosion Principle *measurable* and is the
   down-payment on open challenge T2.
3. **Soft-binding check**: does the watermark/perceptual hash still match the
   delivered bytes? Detects off-manifest regeneration / paraphrase.
4. **Policy decision**: ACCEPT / DOWN_WEIGHT / QUARANTINE / REJECT against a
   threshold - the dynamic, risk-adaptive authorization the SoK calls for,
   driven by a verified external signal rather than static role permissions.

Crucially, the verdict depends on the *origin* warrant and transformation
fidelity, NOT on the identity of the delivering agent. That is what defeats
laundering: a claim that originated on an editable page keeps its low ceiling
no matter how many trusted agents relayed it.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
from typing import Optional

from capm.core.types import SourceClass, TransformationType, WarrantLevel
from capm.identity.credentials import AgentIdentity, CredentialRegistry
from capm.manifest.capm_manifest import CAPMManifest, ManifestSegment


class Decision(enum.Enum):
    ACCEPT = "accept"            # form beliefs normally
    DOWN_WEIGHT = "down_weight"  # use, but flag as lower confidence
    QUARANTINE = "quarantine"    # do not act on; keep for audit
    REJECT = "reject"            # discard (e.g. signature broken)


@dataclasses.dataclass
class WarrantVerdict:
    decision: Decision
    warrant: WarrantLevel
    signature_ok: bool
    soft_binding_ok: bool
    boundary_crossings: int
    reasons: list[str] = dataclasses.field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.decision in (Decision.ACCEPT, Decision.DOWN_WEIGHT)


@dataclasses.dataclass
class EvaluatorPolicy:
    """Tunable thresholds + ablation toggles for the warrant evaluator.

    ``min_accept`` is the warrant floor for ACCEPT. The boolean toggles below
    each disable one CAPM mechanism so the ablation suite (E8.x) can show every
    component is necessary; all default to the full defense.
    """

    min_accept: WarrantLevel = WarrantLevel.MODERATE
    min_down_weight: WarrantLevel = WarrantLevel.WEAK
    # A *verified* org boundary (signature ok + trusted DID) costs nothing on
    # its own: identity is established, so crossing it does not erode warrant.
    # Erosion comes from *transformations*, per the Warrant Erosion Principle.
    # An *unverified* crossing (no signature requirement) costs this much.
    boundary_penalty_per_cross: int = 0
    unverified_boundary_penalty: int = 1
    require_signatures: bool = True
    require_soft_binding: bool = False    # enabled in the S3 text-only scenario

    # ---- ablation toggles (E8.x) + adaptive-adversary defenses ----------
    enforce_origin_ceiling: bool = True        # E8.1: cap warrant by source class
    apply_transformation_penalty: bool = True  # E8.2: fidelity penalty per hop
    enable_soft_binding_check: bool = True     # E8.4: compare watermark to bytes
    cross_org_aware: bool = True               # E8.5: treat org boundaries specially
    # E3.1: a relay claiming VERBATIM must preserve the input bytes; if a
    # verbatim/extraction segment's content hash differs from its predecessor's,
    # the transformation claim is a lie and is scored as a GENERATION.
    detect_transformation_lies: bool = True


class WarrantEvaluator:
    """The external reference monitor. Lives at the receiving agent."""

    def __init__(self, registry: CredentialRegistry,
                 policy: Optional[EvaluatorPolicy] = None):
        self.registry = registry
        self.policy = policy or EvaluatorPolicy()

    # ---- 1. signature verification -----------------------------------
    def _verify_signatures(self, manifest: CAPMManifest, reasons: list[str]) -> bool:
        prev_hash = None
        for seg in manifest.segments:
            # (a) issuer must be trusted
            if not self.registry.trusts(seg.agent_did):
                reasons.append(f"seg{seg.segment_index}: untrusted DID {seg.agent_did}")
                return False
            vc = self.registry.lookup(seg.agent_did)
            # (b) the embedded VC must match the registered one
            if vc is None or vc.public_key_b64 != seg.agent_vc.public_key_b64:
                reasons.append(f"seg{seg.segment_index}: VC mismatch")
                return False
            # (c) signature must verify over canonical claim bytes
            if not AgentIdentity.verify(vc, seg.claim_bytes(), seg.signature or ""):
                reasons.append(f"seg{seg.segment_index}: bad signature")
                return False
            # (d) hash-linkage must be intact
            if seg.prev_segment_hash != prev_hash:
                reasons.append(f"seg{seg.segment_index}: broken hash link")
                return False
            prev_hash = seg.segment_hash()
        return True

    # ---- 2. warrant scoring (monotone non-increasing) ----------------
    def _score_warrant(self, manifest: CAPMManifest, reasons: list[str],
                       signatures_verified: bool) -> tuple[WarrantLevel, int]:
        if not manifest.segments:
            reasons.append("empty manifest")
            return WarrantLevel.NONE, 0

        origin = manifest.segments[0]
        if origin.asserted_origin_warrant is None:
            reasons.append("origin segment lacks asserted warrant")
            warrant_val = WarrantLevel.NONE
        else:
            # ceiling is bounded by the *declared source class*, so a lying
            # origin cannot claim more warrant than its class permits.
            asserted = WarrantLevel(origin.asserted_origin_warrant)
            if origin.origin_source_class is not None and self.policy.enforce_origin_ceiling:
                ceiling = SourceClass(origin.origin_source_class).warrant_ceiling
                warrant_val = WarrantLevel(min(int(asserted), int(ceiling)))
                if int(asserted) > int(ceiling):
                    reasons.append("origin over-claimed warrant; capped to source ceiling")
            else:
                # ablation E8.1 (or no declared class): trust the asserted number.
                warrant_val = asserted

        # boundary penalty depends on whether identity was actually verified:
        # a verified crossing does not erode warrant (identity is established);
        # an unverified one does.
        per_cross = (self.policy.boundary_penalty_per_cross if signatures_verified
                     else self.policy.unverified_boundary_penalty)

        crossings = 0
        current = int(warrant_val)
        prev_content_hash: Optional[str] = None
        for seg in manifest.segments:
            t = TransformationType(seg.transformation)
            # E3.1: a VERBATIM/EXTRACTION claim that does not preserve the
            # predecessor's bytes is a transformation lie -> score as GENERATION.
            if (self.policy.detect_transformation_lies and prev_content_hash is not None
                    and t in (TransformationType.VERBATIM,
                              TransformationType.STRUCTURED_EXTRACTION)
                    and seg.content_hash != prev_content_hash):
                reasons.append(
                    f"seg{seg.segment_index}: claims {t.value} but bytes changed "
                    f"-> transformation lie, scored as generation")
                t = TransformationType.GENERATION
            if self.policy.apply_transformation_penalty:
                current -= t.fidelity_penalty
            if seg.crosses_org_boundary and self.policy.cross_org_aware:
                crossings += 1
                current -= per_cross
            current = max(0, current)
            prev_content_hash = seg.content_hash
        return WarrantLevel(current), crossings

    # ---- 3. soft-binding check ---------------------------------------
    def _soft_binding_ok(self, manifest: CAPMManifest, delivered_text: Optional[str]) -> bool:
        if not self.policy.enable_soft_binding_check:
            return True  # ablation E8.4: soft-binding disabled
        if delivered_text is None:
            return True  # nothing to check against (metadata-present scenario)
        head = manifest.segments[-1]
        if head.soft_binding is None:
            return True
        # toy perceptual hash: token-set hash. A real impl uses a watermark
        # detector (Dathathri et al. Nature 2024 / WorldCup multi-bit).
        recomputed = hashlib.sha256(
            " ".join(sorted(delivered_text.lower().split())).encode()).hexdigest()
        return recomputed == head.soft_binding

    # ---- top-level evaluation ----------------------------------------
    def evaluate(self, manifest: CAPMManifest,
                 delivered_text: Optional[str] = None) -> WarrantVerdict:
        reasons: list[str] = []

        sig_ok = True
        if self.policy.require_signatures:
            sig_ok = self._verify_signatures(manifest, reasons)
            if not sig_ok:
                return WarrantVerdict(Decision.REJECT, WarrantLevel.NONE,
                                      False, False, 0, reasons)

        warrant, crossings = self._score_warrant(manifest, reasons, sig_ok)

        soft_ok = self._soft_binding_ok(manifest, delivered_text)
        if self.policy.require_soft_binding and not soft_ok:
            reasons.append("soft-binding mismatch: text regenerated off-manifest")
            return WarrantVerdict(Decision.QUARANTINE, WarrantLevel.NONE,
                                  sig_ok, False, crossings, reasons)

        # policy decision
        if warrant >= self.policy.min_accept:
            decision = Decision.ACCEPT
        elif warrant >= self.policy.min_down_weight:
            decision = Decision.DOWN_WEIGHT
            reasons.append(f"warrant {warrant.name} below accept floor")
        else:
            decision = Decision.QUARANTINE
            reasons.append(f"warrant {warrant.name} too low to act on")

        return WarrantVerdict(decision, warrant, sig_ok, soft_ok, crossings, reasons)
