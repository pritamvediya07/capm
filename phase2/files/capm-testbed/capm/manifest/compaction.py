"""Merkle compaction for long manifests (E6.3).

A manifest grows O(N) in the chain length: every hop appends a signed segment.
For very long chains the wire form becomes large even though a receiver only
*needs* (a) the origin segment — which sets the warrant ceiling and is
security-critical — and (b) the recent segments it will keep transforming. The
long run of intermediate segments can be **rolled up** into one signed
**checkpoint** that carries:

  * a **Merkle root** over the compacted segments' hashes (a commitment that lets
    any old segment be proven included on demand — auditability is preserved);
  * the **warrant-relevant running state** at the checkpoint: the warrant level
    after origin+middle (the erosion algebra is incremental, so this is exact),
    the boundary-crossing count, and the last segment's content-hash + watermark
    (so the first *recent* segment's transformation-lie / fidelity checks still
    have their predecessor).

The checkpoint is **signed by the compacting agent**, so the rolled-up state is
unforgeable; a receiver verifies the origin segment, the recent segments, and the
checkpoint signature, then computes warrant from (checkpoint state → recent
segments). The result is **bit-identical to evaluating the full manifest**, while
the wire form is O(window) instead of O(N).

This is the snapshot/checkpoint pattern (trusted compactor + Merkle audit), the
standard way to bound an append-only log; ``CompactManifest`` is the wire form and
``compact_warrant`` the receiver-side evaluation.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Optional

from capm.core.types import SourceClass, TransformationType, WarrantLevel
from capm.identity.credentials import (AgentIdentity, CredentialRegistry,
                                       VerifiableCredential)
from capm.manifest import watermark as _wm
from capm.manifest.capm_manifest import CAPMManifest, ManifestSegment, _canonical
from capm.warrant.evaluator import EvaluatorPolicy


# ---------------------------------------------------------------------------
# Merkle tree over segment hashes
# ---------------------------------------------------------------------------
def _h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def merkle_root(leaves: list[str]) -> str:
    """Binary Merkle root of the leaf hashes (duplicate-last for odd levels)."""
    if not leaves:
        return _h(b"")
    level = [bytes.fromhex(x) for x in leaves]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest()
                 for i in range(0, len(level), 2)]
    return level[0].hex()


def merkle_proof(leaves: list[str], index: int) -> list[tuple[str, bool]]:
    """Inclusion proof for ``leaves[index]``: list of (sibling_hash, sibling_is_left)."""
    proof: list[tuple[str, bool]] = []
    level = [bytes.fromhex(x) for x in leaves]
    idx = index
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        sib = idx ^ 1
        proof.append((level[sib].hex(), sib < idx))
        level = [hashlib.sha256(level[i] + level[i + 1]).digest()
                 for i in range(0, len(level), 2)]
        idx //= 2
    return proof


def verify_merkle_proof(leaf: str, proof: list[tuple[str, bool]], root: str) -> bool:
    cur = bytes.fromhex(leaf)
    for sib_hex, sib_is_left in proof:
        sib = bytes.fromhex(sib_hex)
        cur = hashlib.sha256((sib + cur) if sib_is_left else (cur + sib)).digest()
    return cur.hex() == root


# ---------------------------------------------------------------------------
# Checkpoint + compact manifest
# ---------------------------------------------------------------------------
@dataclasses.dataclass
class Checkpoint:
    """A signed roll-up of a manifest prefix (origin + middle segments)."""

    compactor_did: str
    compactor_vc: VerifiableCredential
    n_compacted: int                      # how many segments were rolled up
    merkle_root: str                      # commitment over the compacted segment hashes
    warrant_at_checkpoint: int            # running warrant after origin+middle (exact)
    crossings_at_checkpoint: int
    origin_source_class: Optional[str]    # carried for reporting/audit
    asserted_origin_warrant: Optional[int]
    last_content_hash: str                # predecessor state for the first recent segment
    last_watermark: Optional[str]
    prefix_tail_hash: str                 # last compacted segment_hash (hash-link continuity)
    signature: Optional[str] = None

    def claim_bytes(self) -> bytes:
        d = dataclasses.asdict(self)
        d.pop("signature", None)
        d["compactor_vc"] = self.compactor_vc.to_json()
        return _canonical(d)


@dataclasses.dataclass
class CompactManifest:
    """Wire form: the full origin segment, a signed checkpoint, the recent segments."""

    origin_segment: ManifestSegment
    checkpoint: Checkpoint
    recent_segments: list[ManifestSegment]

    def to_json(self) -> str:
        def seg(s):
            d = dataclasses.asdict(s); d["agent_vc"] = dataclasses.asdict(s.agent_vc)
            return d
        cp = dataclasses.asdict(self.checkpoint)
        cp["compactor_vc"] = dataclasses.asdict(self.checkpoint.compactor_vc)
        return json.dumps({"origin": seg(self.origin_segment), "checkpoint": cp,
                           "recent": [seg(s) for s in self.recent_segments]})


def _seg_penalty(seg: ManifestSegment, prev_content_hash: Optional[str],
                 prev_watermark: Optional[str], pol: EvaluatorPolicy) -> int:
    """The fidelity penalty the evaluator would charge this segment (incl. the
    watermark transformation-lie rescoring) — kept in lock-step with
    WarrantEvaluator._score_warrant so compaction is warrant-exact."""
    t = TransformationType(seg.transformation)
    faithful = t in (TransformationType.VERBATIM, TransformationType.STRUCTURED_EXTRACTION)
    if faithful and prev_content_hash is not None:
        if pol.detect_watermark_mismatch and seg.watermark and prev_watermark:
            if _wm.similarity(seg.watermark, prev_watermark) < pol.watermark_threshold:
                t = TransformationType.GENERATION
        elif pol.detect_transformation_lies and seg.content_hash != prev_content_hash:
            t = TransformationType.GENERATION
    return round(t.fidelity_penalty * pol.transformation_penalty_scale) if pol.apply_transformation_penalty else 0


def _origin_warrant(seg: ManifestSegment, pol: EvaluatorPolicy) -> int:
    if seg.asserted_origin_warrant is None:
        return int(WarrantLevel.NONE)
    asserted = int(seg.asserted_origin_warrant)
    if seg.origin_source_class is not None and pol.enforce_origin_ceiling:
        ceiling = int(SourceClass(seg.origin_source_class).warrant_ceiling)
        return min(asserted, ceiling)
    return asserted


def compact(manifest: CAPMManifest, compactor: AgentIdentity, *, keep_recent: int = 4,
            policy: Optional[EvaluatorPolicy] = None) -> CompactManifest:
    """Roll up segments[1:-keep_recent] into a signed checkpoint."""
    pol = policy or EvaluatorPolicy()
    segs = manifest.segments
    if len(segs) <= keep_recent + 1:
        raise ValueError("chain too short to compact")
    origin, middle, recent = segs[0], segs[1:-keep_recent], segs[-keep_recent:]

    # replay the evaluator's warrant scoring over origin + middle (exact)
    warrant = _origin_warrant(origin, pol)
    per_cross = pol.boundary_penalty_per_cross   # signatures verified at compaction
    crossings = 0
    prev_ch: Optional[str] = None
    prev_wm: Optional[str] = None
    for seg in [origin] + middle:
        warrant -= _seg_penalty(seg, prev_ch, prev_wm, pol)
        if seg.crosses_org_boundary and pol.cross_org_aware:
            crossings += 1; warrant -= per_cross
        warrant = max(0, warrant)
        prev_ch, prev_wm = seg.content_hash, seg.watermark

    cp = Checkpoint(
        compactor_did=compactor.did, compactor_vc=compactor.vc,
        n_compacted=len([origin] + middle),
        merkle_root=merkle_root([s.segment_hash() for s in [origin] + middle]),
        warrant_at_checkpoint=warrant, crossings_at_checkpoint=crossings,
        origin_source_class=origin.origin_source_class,
        asserted_origin_warrant=origin.asserted_origin_warrant,
        last_content_hash=prev_ch, last_watermark=prev_wm,
        prefix_tail_hash=([origin] + middle)[-1].segment_hash())
    cp.signature = compactor.sign(cp.claim_bytes())
    return CompactManifest(origin_segment=origin, checkpoint=cp, recent_segments=recent)


def compact_warrant(cm: CompactManifest, registry: CredentialRegistry,
                    policy: Optional[EvaluatorPolicy] = None) -> tuple[int, bool]:
    """Receiver-side: verify and compute warrant from the compact form.

    Returns (warrant, ok). ``ok`` is False if the origin/recent/checkpoint
    signatures or the checkpoint binding fail (→ the caller rejects)."""
    pol = policy or EvaluatorPolicy()
    cp = cm.checkpoint

    # (1) verify the checkpoint is signed by a trusted compactor over its bytes
    if not registry.trusts(cp.compactor_did):
        return 0, False
    vc = registry.lookup(cp.compactor_did)
    if vc is None or vc.public_key_b64 != cp.compactor_vc.public_key_b64:
        return 0, False
    if not AgentIdentity.verify(vc, cp.claim_bytes(), cp.signature or ""):
        return 0, False
    # (2) verify the origin segment is trusted + correctly signed
    o = cm.origin_segment
    ovc = registry.lookup(o.agent_did)
    if not registry.trusts(o.agent_did) or ovc is None \
            or ovc.public_key_b64 != o.agent_vc.public_key_b64 \
            or not AgentIdentity.verify(ovc, o.claim_bytes(), o.signature or ""):
        return 0, False

    # (3) continue warrant from the checkpoint state across the recent segments
    warrant = cp.warrant_at_checkpoint
    prev_ch, prev_wm = cp.last_content_hash, cp.last_watermark
    prev_hash = cp.prefix_tail_hash
    for seg in cm.recent_segments:
        rvc = registry.lookup(seg.agent_did)
        if not registry.trusts(seg.agent_did) or rvc is None \
                or rvc.public_key_b64 != seg.agent_vc.public_key_b64 \
                or not AgentIdentity.verify(rvc, seg.claim_bytes(), seg.signature or ""):
            return 0, False
        if seg.prev_segment_hash != prev_hash:        # hash-link continuity
            return 0, False
        warrant -= _seg_penalty(seg, prev_ch, prev_wm, pol)
        if seg.crosses_org_boundary and pol.cross_org_aware:
            warrant -= pol.boundary_penalty_per_cross
        warrant = max(0, warrant)
        prev_ch, prev_wm, prev_hash = seg.content_hash, seg.watermark, seg.segment_hash()
    return warrant, True
