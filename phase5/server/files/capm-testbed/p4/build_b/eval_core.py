"""Shared manifest build+evaluate (no gRPC dep) for Build A/B (WS5).

Builds a real signed CAPM manifest from a scenario and runs the real
WarrantEvaluator. Used by the acquisition wrapper (Build A, to feed a
channel-derived source_class into the manifest path) and the verifier service
(Build B, over transport).
"""
from __future__ import annotations

import hashlib

from capm.core.types import SourceClass, TransformationType
from capm.identity.credentials import AgentIdentity, CredentialRegistry
from capm.manifest.capm_manifest import CAPMManifest
from capm.manifest import watermark as _wm
from capm.warrant.evaluator import WarrantEvaluator, EvaluatorPolicy

_CLOCK = lambda: 1_700_000_000.0


def _soft(content: str) -> str:
    return hashlib.sha256(" ".join(sorted(content.lower().split())).encode()).hexdigest()


def build_and_evaluate(origin_class_name: str, transforms, hops: int):
    """(warrant_name, decision_value, signature_ok) for a real signed manifest."""
    reg = CredentialRegistry()
    origin = AgentIdentity(did="did:capm:origin", org="org:source"); reg.register(origin)
    relays = []
    for i in range(1, hops + 1):
        r = AgentIdentity(did=f"did:capm:relay{i}", org=f"org:relay{i}"); reg.register(r); relays.append(r)
    ev = WarrantEvaluator(reg, EvaluatorPolicy())
    try:
        sc = SourceClass[origin_class_name]
    except KeyError:
        sc = SourceClass(origin_class_name)
    content = "advisory: example content for the transport test"
    m = CAPMManifest()
    m.append_segment(identity=origin, content=content, transformation=TransformationType.VERBATIM,
                     from_org="org:source", to_org=("org:relay1" if hops >= 1 else "org:principal"),
                     origin_source_class=sc, asserted_origin_warrant=sc.warrant_ceiling,
                     soft_binding=_soft(content), watermark=_wm.fingerprint(content), timestamp=_CLOCK())
    for i, r in enumerate(relays):
        t = TransformationType(transforms[i % len(transforms)]) if transforms else TransformationType.VERBATIM
        to = f"org:relay{i + 2}" if (i + 1) < hops else "org:principal"
        m.append_segment(identity=r, content=content, transformation=t, from_org=r.org, to_org=to,
                         soft_binding=_soft(content), watermark=_wm.fingerprint(content), timestamp=_CLOCK())
    res = ev.evaluate(m, content)
    return res.warrant.name, res.decision.value, bool(res.signature_ok)
