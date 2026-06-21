"""Cross-Agent Provenance Manifest (Component 2 - the signed container).

Adapts the C2PA manifest structure (claim + assertions + signature) to a
*chained, multi-agent* derivation, which single-author C2PA does not handle.

Each time an agent emits a value across a boundary it produces a
``ManifestSegment``:

* a **claim** - what transformation this agent performed, on which input
  segment, when;
* **assertions** - origin source-warrant, transformation type, boundary
  crossing;
* a **signature** over the canonical bytes, produced under the key bound to
  the agent's Verifiable Credential (the Plane-1<->Plane-2 binding).

Segments form a hash-linked chain (each references the previous segment's
hash), so tampering anywhere breaks verification - the "hard binding". A
``soft_binding`` field carries a perceptual/watermark hash so the manifest can
be re-associated with text after extrinsic metadata is stripped (addresses
C5/P3, "when only the final text survives").
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from typing import Optional

from capm.core.types import SourceClass, TransformationType, WarrantLevel
from capm.identity.credentials import (AgentIdentity, CredentialRegistry,
                                       VerifiableCredential)
from capm.provenance.graph import ProvenanceChain


def _canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclasses.dataclass
class ManifestSegment:
    """One agent's signed contribution to the provenance manifest."""

    segment_index: int
    agent_did: str
    agent_org: str
    agent_vc: VerifiableCredential
    # claim
    content_hash: str                       # sha256 of the emitted content
    transformation: str                     # TransformationType.value
    from_org: str
    to_org: str
    crosses_org_boundary: bool
    timestamp: float
    # assertions
    origin_source_class: Optional[str]      # SourceClass.value if this is origin
    asserted_origin_warrant: Optional[int]  # WarrantLevel int if origin
    # linkage
    prev_segment_hash: Optional[str]
    soft_binding: Optional[str] = None      # token-set hash (re-association after strip)
    watermark: Optional[str] = None         # SimHash perceptual fingerprint (E3.1 fidelity)
    signature: Optional[str] = None         # filled by sign()

    def claim_bytes(self) -> bytes:
        """Canonical bytes that the signature covers (everything but the sig)."""
        d = dataclasses.asdict(self)
        d.pop("signature", None)
        # VC is embedded as its own canonical json so it is part of the binding
        d["agent_vc"] = self.agent_vc.to_json()
        return _canonical(d)

    def segment_hash(self) -> str:
        return hashlib.sha256(self.claim_bytes()
                              + (self.signature or "").encode()).hexdigest()


@dataclasses.dataclass
class CAPMManifest:
    """The full hash-linked, signed manifest travelling with a message."""

    segments: list[ManifestSegment] = dataclasses.field(default_factory=list)
    # the W3C-PROV triples are carried for standards-adjacency / audit
    prov_triples: list[tuple[str, str, str]] = dataclasses.field(default_factory=list)

    # ---- emission -----------------------------------------------------
    def append_segment(self, *, identity: AgentIdentity, content: str,
                       transformation: TransformationType, from_org: str,
                       to_org: str, origin_source_class: Optional[SourceClass] = None,
                       asserted_origin_warrant: Optional[WarrantLevel] = None,
                       soft_binding: Optional[str] = None,
                       watermark: Optional[str] = None,
                       timestamp: Optional[float] = None) -> ManifestSegment:
        prev_hash = self.segments[-1].segment_hash() if self.segments else None
        seg = ManifestSegment(
            segment_index=len(self.segments),
            agent_did=identity.did,
            agent_org=identity.org,
            agent_vc=identity.vc,
            content_hash=hashlib.sha256(content.encode()).hexdigest(),
            transformation=transformation.value,
            from_org=from_org,
            to_org=to_org,
            crosses_org_boundary=(from_org != to_org),
            timestamp=timestamp if timestamp is not None else time.time(),
            origin_source_class=origin_source_class.value if origin_source_class else None,
            asserted_origin_warrant=int(asserted_origin_warrant) if asserted_origin_warrant is not None else None,
            prev_segment_hash=prev_hash,
            soft_binding=soft_binding,
            watermark=watermark,
        )
        seg.signature = identity.sign(seg.claim_bytes())
        self.segments.append(seg)
        return seg

    def attach_prov(self, chain: ProvenanceChain) -> None:
        self.prov_triples = chain.to_prov_triples()

    # ---- serialisation ------------------------------------------------
    def to_json(self) -> str:
        return json.dumps({
            "segments": [self._seg_dict(s) for s in self.segments],
            "prov_triples": self.prov_triples,
        })

    @staticmethod
    def _seg_dict(s: ManifestSegment) -> dict:
        d = dataclasses.asdict(s)
        d["agent_vc"] = dataclasses.asdict(s.agent_vc)
        return d

    @classmethod
    def from_json(cls, blob: str) -> "CAPMManifest":
        data = json.loads(blob)
        m = cls(prov_triples=[tuple(t) for t in data.get("prov_triples", [])])
        for sd in data["segments"]:
            vc = VerifiableCredential(**sd.pop("agent_vc"))
            m.segments.append(ManifestSegment(agent_vc=vc, **sd))
        return m
