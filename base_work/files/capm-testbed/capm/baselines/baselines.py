"""Baseline defenses for comparison against CAPM.

The design doc specifies four baselines. Each is implemented as an *evaluator*
with the same ``evaluate(manifest, text) -> WarrantVerdict`` interface as
:class:`capm.warrant.evaluator.WarrantEvaluator`, so the benchmark can swap
them in without touching agent code.

* :class:`NoDefenseEvaluator` - accept everything (today's default agent).
* :class:`IdentityOnlyEvaluator` - Plane-1 only: accept iff the sender's DID is
  trusted, regardless of content provenance (SAGA / DID-VC without Plane-2).
* :class:`FlatProvenanceEvaluator` - document-level provenance with no
  origin-warrant ceiling and no per-transformation erosion: accepts if *a*
  source is named (PROV-AGENT-style honest-participant assumption).
* :class:`SingleRuntimeCaMeLEvaluator` - CaMeL-style: enforces within a single
  runtime/org but has no view across the agent-to-agent boundary, so it treats
  cross-org input as trusted once it arrives.

CAPM itself is :class:`capm.warrant.evaluator.WarrantEvaluator`.
"""

from __future__ import annotations

from capm.core.types import WarrantLevel
from capm.identity.credentials import CredentialRegistry
from capm.manifest.capm_manifest import CAPMManifest
from capm.warrant.evaluator import Decision, WarrantVerdict


class NoDefenseEvaluator:
    def __init__(self, *_a, **_k): ...
    def evaluate(self, manifest, delivered_text=None) -> WarrantVerdict:
        return WarrantVerdict(Decision.ACCEPT, WarrantLevel.MODERATE,
                              True, True, 0, ["no-defense: accept all"])


class IdentityOnlyEvaluator:
    """Accept iff sender DID is trusted (Plane 1 only)."""
    def __init__(self, registry: CredentialRegistry, *_a, **_k):
        self.registry = registry
    def evaluate(self, manifest: CAPMManifest, delivered_text=None) -> WarrantVerdict:
        if not manifest or not manifest.segments:
            return WarrantVerdict(Decision.REJECT, WarrantLevel.NONE, False, True, 0,
                                  ["identity-only: no manifest"])
        sender = manifest.segments[-1].agent_did
        if self.registry.trusts(sender):
            return WarrantVerdict(Decision.ACCEPT, WarrantLevel.MODERATE, True, True, 0,
                                  ["identity-only: trusted sender -> accept"])
        return WarrantVerdict(Decision.REJECT, WarrantLevel.NONE, False, True, 0,
                              ["identity-only: untrusted sender"])


class FlatProvenanceEvaluator:
    """Document-level provenance, honest-participant assumption (PROV-AGENT-like)."""
    def __init__(self, *_a, **_k): ...
    def evaluate(self, manifest: CAPMManifest, delivered_text=None) -> WarrantVerdict:
        if not manifest or not manifest.segments:
            return WarrantVerdict(Decision.QUARANTINE, WarrantLevel.NONE, True, True, 0,
                                  ["flat: no provenance"])
        # a source is named -> trust the *asserted* warrant verbatim (no ceiling)
        origin = manifest.segments[0]
        w = WarrantLevel(origin.asserted_origin_warrant) if origin.asserted_origin_warrant is not None else WarrantLevel.MODERATE
        decision = Decision.ACCEPT if w >= WarrantLevel.WEAK else Decision.QUARANTINE
        return WarrantVerdict(decision, w, True, True, 0,
                              ["flat: trusts asserted warrant, no origin-ceiling"])


class SingleRuntimeCaMeLEvaluator:
    """CaMeL-style: secure within one runtime, blind across the boundary."""
    def __init__(self, home_org: str, *_a, **_k):
        self.home_org = home_org
    def evaluate(self, manifest: CAPMManifest, delivered_text=None) -> WarrantVerdict:
        if not manifest or not manifest.segments:
            return WarrantVerdict(Decision.ACCEPT, WarrantLevel.MODERATE, True, True, 0,
                                  ["camel: no cross-org view, accept"])
        # if the value never left our org, in-runtime IFC applies; if it crossed
        # a boundary, CaMeL has no labels for it -> treats as trusted on arrival
        crossed = any(s.crosses_org_boundary for s in manifest.segments)
        reason = "camel: cross-org input trusted on arrival (single-runtime blind spot)" if crossed \
            else "camel: in-runtime IFC"
        return WarrantVerdict(Decision.ACCEPT, WarrantLevel.MODERATE, True, True,
                              sum(1 for s in manifest.segments if s.crosses_org_boundary),
                              [reason])


BASELINES = {
    "no_defense": NoDefenseEvaluator,
    "identity_only": IdentityOnlyEvaluator,
    "flat_provenance": FlatProvenanceEvaluator,
    "camel_single_runtime": SingleRuntimeCaMeLEvaluator,
}
