"""p3/manifest/field.py — the signed per-claim realized-provenance field + verifier.

The field a relay appends per output claim (design-doc §11 / Step 3):

    ⟨claim_id, claimed_parent_id (HINT), verified_parent_id (verifier-derived),
     u, s, faith, effect, sensor_versions, sensor_placement, hop_signature⟩

The verifier enforces the §7a / §5 trust model:

  * **claimed-not-trusted lineage** — it re-derives ``verified_parent_id`` with
    the deterministic matcher (p3.claims.match) and degrades on mismatch /
    ambiguity; the relay's ``claimed_parent_id`` is only a search hint;
  * **sensor-placement enforcement** — the fully-verifier-side sensors (support,
    NLI) are ALWAYS recomputed by the verifier from text (the relay's s/faith are
    never honored); the runtime-internal usage ``u`` is honored ONLY if its
    ``sensor_placement`` is trusted (verifier-side / attested / re-executing),
    else it is absent (the black-box fallback);
  * then it computes ``g``, takes ``min(w_decl, g·w_decl)`` and emits a per-claim
    verdict — so a forged sensor value or a self-serving parent can never raise
    warrant above baseline.
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Optional

from p3.claims.extract import Claim
from p3.claims.match import tag_effects
from p3.warrant.realized import realized_warrant, RealizedWarrant

TRUSTED_PLACEMENTS = {"verifier_side", "attested_service", "re_executing_verifier"}

# verifier-side recompute of (support, faith) from the matcher's effect — the
# fully-verifier-side, ML-free signal (the A.2 matcher IS a verifier-side sensor).
_EFFECT_TO_SENSORS = {
    "survived":  (1.0, 1.0),   # supported + entailed
    "distorted": (0.5, 0.0),   # contradiction -> faith 0
    "added":     (0.0, 0.0),   # fabrication -> no support, ungrounded
    "dropped":   (0.0, 0.0),   # claim unsupported by source
}


@dataclasses.dataclass
class RealizedField:
    claim_id: str
    field_key: str
    claimed_parent_id: Optional[str]                 # relay HINT (untrusted)
    u: Optional[float] = None                        # relay-asserted sensor values
    s: Optional[float] = None
    faith: Optional[float] = None
    sensor_placement: dict = dataclasses.field(default_factory=dict)  # per-sensor placement claim
    # per-sensor VALID attestation (an attested service / re-executing verifier signs the
    # value with a key the verifier trusts). A relay cannot forge it — so claiming a trusted
    # `sensor_placement` string is NOT enough; the attestation must verify too.
    attestations: dict = dataclasses.field(default_factory=dict)
    sensor_versions: dict = dataclasses.field(default_factory=dict)
    hop_signature: Optional[str] = None
    verified_parent_id: Optional[str] = None         # filled by the verifier


@dataclasses.dataclass
class ClaimVerdict:
    claim_id: str
    effect: str
    rw: RealizedWarrant
    verified_parent_id: Optional[str]
    claimed_parent_id: Optional[str]
    parent_corrected: bool                           # claimed != verified (or null)
    u_placement: Optional[str]
    u_honored: bool                                  # relay/attested u accepted?
    s_faith_source: str                              # always "verifier_recomputed"

    @property
    def decision(self) -> str:
        return self.rw.decision


class RealizedVerifier:
    """External reference monitor for the per-claim realized field."""

    def __init__(self, *, usage_provider: Optional[Callable] = None,
                 form: str = "min", trusted: set | None = None):
        # usage_provider(field, output_text) -> float : a TRUSTED u source
        # (re-executing verifier on an open model / attested sensor). None => the
        # black-box fallback (no usage signal available).
        self.usage_provider = usage_provider
        self.form = form
        self.trusted = trusted or TRUSTED_PLACEMENTS

    def verify_claim(self, field: RealizedField, source_claims: list[Claim],
                     output_text: str, w_decl: float) -> ClaimVerdict:
        # 1. re-derive lineage + effect with the deterministic matcher (claimed-not-trusted)
        effects = tag_effects(source_claims, output_text)
        eff = next((e for e in effects if e.field_key == field.field_key), None)
        effect = eff.effect if eff else "added"
        verified_parent = eff.verified_parent_id if eff else None
        field.verified_parent_id = verified_parent
        parent_corrected = (field.claimed_parent_id is not None
                            and field.claimed_parent_id != verified_parent)

        # 2. s, faith are FULLY verifier-side -> always recomputed; relay values ignored
        s_re, faith_re = _EFFECT_TO_SENSORS.get(effect, (0.0, 0.0))

        # 3. usage u: honor a relay-supplied value ONLY if its placement is trusted
        #    AND it carries a valid attestation (a relay cannot forge the attestation,
        #    so merely *claiming* "attested_service" is not enough). Otherwise discard
        #    and try the verifier's own trusted provider (re-execution); if none, u is
        #    absent -> black-box fallback (neutral 1.0, no boost).
        u_placement = field.sensor_placement.get("u")
        u_attested = bool(field.attestations.get("u", False))
        u_honored = (u_placement in self.trusted) and u_attested and field.u is not None
        u = field.u if u_honored else None
        if u is None and self.usage_provider is not None:
            u = self.usage_provider(field, output_text)   # trusted recompute
            u_honored = True
            u_placement = "re_executing_verifier"

        # 4. if lineage is suspect (no verified parent, or relay lied about it), the
        #    grounding is not established -> degrade by forcing faith/support down.
        if verified_parent is None or parent_corrected:
            s_re = min(s_re, 0.0 if effect in ("added", "distorted") else s_re)
            faith_re = min(faith_re, 0.0)

        u_eff = u if u is not None else 1.0    # absent u = neutral; clamp still holds
        rw = realized_warrant(w_decl, u_eff, s_re, faith_re, form=self.form)
        return ClaimVerdict(field.claim_id, effect, rw, verified_parent,
                            field.claimed_parent_id, parent_corrected,
                            u_placement, u_honored, "verifier_recomputed")
