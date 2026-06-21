"""Adversary profiles: declarative control over what an agent emits.

An :class:`AdversaryProfile` is attached to a :class:`capm.agents.agent.CAPMAgent`
(via ``agent.adversary``) and overrides its emission. It separates **ground
truth** (the real source class / real transformation) from what the agent
**declares** in the signed manifest. The gap between the two is the attack; the
warrant evaluator's job is to be robust to it.

Threat-model note (important for the paper's honesty):

* CAPM bounds warrant by the *declared* origin source class, because that is
  what a receiver can see. If an attacker can get a *false* high class declared
  and have it accepted as the origin, CAPM cannot catch it by warrant alone -
  that is **origin integrity**, a separate composable layer (E3.2). What CAPM
  still guarantees in that case is faithful **attribution**: the manifest names
  the captured origin, enabling post-hoc revocation.
* What CAPM *does* defeat: a relay (non-origin) signer trying to raise warrant.
  No matter how many trusted relays co-sign (E3.4), warrant stays bounded by
  the origin segment, because relays cannot author an origin segment for a
  source they do not control without breaking the signature/registry checks.
"""

from __future__ import annotations

import dataclasses
import enum
from typing import Callable, Optional

from capm.core.types import SourceClass, TransformationType, WarrantLevel


class ForgeryMode(enum.Enum):
    """How a forging adversary tampers with the cryptographic binding (E3.3)."""

    NONE = "none"
    FAKE_SIGNATURE = "fake_signature"      # sign with a key not bound to the VC
    SUBSTITUTE_VC = "substitute_vc"        # swap in a trusted DID's VC, own key
    REPLAY_SEGMENT = "replay_segment"      # copy another segment's signature


@dataclasses.dataclass
class AdversaryProfile:
    """Declarative emission control for an adversarial agent.

    Attributes
    ----------
    content:
        The text the adversary plants/emits.
    true_source_class:
        Ground truth of where the content really came from (for attribution and
        for the calibration/oracle metrics). Never shown to the receiver.
    declared_source_class:
        What the adversary writes into the manifest's origin assertion. Equal to
        ``true_source_class`` for an honest origin; *higher* for origin capture.
    asserted_warrant:
        The warrant level the adversary asserts at the origin.
    declared_transformation:
        The transformation the adversary *claims* it performed.
    actual_transformation:
        What it really did (used by the classifier / soft-binding to catch a
        lie). Defaults to equal the declared one (no transformation lie).
    forgery:
        Cryptographic tampering mode (E3.3); NONE for content-only attacks.
    is_origin:
        True if this profile authors an origin segment (a tail). A relay profile
        (is_origin=False) is used for collusion (E3.4).
    label:
        Human-readable attack name for reporting.
    """

    content: str
    true_source_class: SourceClass
    declared_source_class: SourceClass
    asserted_warrant: WarrantLevel
    declared_transformation: TransformationType = TransformationType.VERBATIM
    actual_transformation: Optional[TransformationType] = None
    forgery: ForgeryMode = ForgeryMode.NONE
    is_origin: bool = True
    is_malicious: bool = True
    label: str = "adversary"
    # When set, the harness installs this responder on the agent so the relay
    # actually produces the ``actual_transformation`` content (E3.1). The
    # signature is ``(query, inputs) -> (content, TransformationType)``.
    responder_override: Optional[Callable] = None

    def __post_init__(self):
        if self.actual_transformation is None:
            self.actual_transformation = self.declared_transformation

    # ---- introspection used by metrics --------------------------------
    @property
    def overclaims_class(self) -> bool:
        """True if the declared class outranks the true class (origin capture)."""
        return (self.declared_source_class.warrant_ceiling
                > self.true_source_class.warrant_ceiling)

    @property
    def lies_about_transformation(self) -> bool:
        return self.actual_transformation != self.declared_transformation


# ---------------------------------------------------------------------------
# Constructors for the named adversaries in the experiment plan
# ---------------------------------------------------------------------------
def honest_origin(content: str, source_class: SourceClass,
                  transformation: TransformationType = TransformationType.VERBATIM
                  ) -> AdversaryProfile:
    """A truthful origin (not an attack) - used as the honest control."""
    return AdversaryProfile(
        content=content, true_source_class=source_class,
        declared_source_class=source_class,
        asserted_warrant=source_class.warrant_ceiling,
        declared_transformation=transformation, is_malicious=False,
        label="honest")


def inflated_warrant_origin(content: str, true_class: SourceClass,
                            asserted: WarrantLevel = WarrantLevel.STRONG,
                            label: str = "inflated_warrant") -> AdversaryProfile:
    """Truthful class, inflated warrant number (the original injectors' model).

    The ceiling caps it; CAPM contains this trivially. Kept as the *weak*
    adversary baseline so the frontier between weak and adaptive is visible.
    """
    return AdversaryProfile(
        content=content, true_source_class=true_class,
        declared_source_class=true_class, asserted_warrant=asserted,
        declared_transformation=TransformationType.VERBATIM, label=label)


def origin_capture(content: str, true_class: SourceClass = SourceClass.EDITABLE_SOURCE,
                   claimed_class: SourceClass = SourceClass.AUTHORITATIVE_API,
                   label: str = "origin_capture") -> AdversaryProfile:
    """E3.2: lie about the *source class itself*, not just the warrant.

    The adversary plants content on a low-warrant source but declares a
    high-warrant class. This is the experiment that bounds CLAIM-1/3: CAPM will
    *not* catch this by warrant alone (origin integrity is out of scope), but
    must still attribute the claim to the captured origin.
    """
    return AdversaryProfile(
        content=content, true_source_class=true_class,
        declared_source_class=claimed_class,
        asserted_warrant=claimed_class.warrant_ceiling,
        declared_transformation=TransformationType.VERBATIM, label=label)


def lying_transformation_origin(generated_content: str,
                                label: str = "lying_transformation") -> AdversaryProfile:
    """E3.1: a malicious *relay* that regenerates content but declares VERBATIM.

    A VERBATIM claim must preserve the input bytes; this relay instead emits
    ``generated_content`` (different bytes) while stamping VERBATIM to dodge the
    fidelity penalty. The evaluator's content-hash check (a relay claiming
    verbatim must reproduce its predecessor's hash) catches the lie and scores
    the segment as a GENERATION. Implemented as a relay (is_origin=False) with a
    responder that emits the new content.
    """
    from capm.agents.responders import ScriptedResponder
    return AdversaryProfile(
        content="", true_source_class=SourceClass.MODEL_MEMORY,
        declared_source_class=SourceClass.MODEL_MEMORY,
        asserted_warrant=WarrantLevel.NONE,
        declared_transformation=TransformationType.VERBATIM,
        actual_transformation=TransformationType.GENERATION,
        is_origin=False, label=label,
        responder_override=ScriptedResponder(
            generated_content, TransformationType.GENERATION))


def forgery_relay(mode: ForgeryMode, label: str = "forgery_relay") -> AdversaryProfile:
    """E3.3: a principal-facing relay that forges its own segment's binding.

    Placed at chain index 0 (the head) so the principal evaluates the forged
    segment directly rather than an honest hop dropping it first. Must REJECT.
    """
    return AdversaryProfile(
        content="", true_source_class=SourceClass.UNKNOWN,
        declared_source_class=SourceClass.UNKNOWN,
        asserted_warrant=WarrantLevel.NONE,
        declared_transformation=TransformationType.PARAPHRASE,
        forgery=mode, is_origin=False, label=f"{label}:{mode.value}")


def manifest_forgery_origin(content: str, mode: ForgeryMode,
                            true_class: SourceClass = SourceClass.EDITABLE_SOURCE,
                            label: str = "manifest_forgery") -> AdversaryProfile:
    """E3.3: forge the cryptographic binding. Must always be REJECTed."""
    return AdversaryProfile(
        content=content, true_source_class=true_class,
        declared_source_class=SourceClass.AUTHORITATIVE_API,
        asserted_warrant=WarrantLevel.STRONG,
        declared_transformation=TransformationType.VERBATIM,
        forgery=mode, label=f"{label}:{mode.value}")


def collusion_relay(label: str = "collusion_relay") -> AdversaryProfile:
    """E3.4: a malicious *relay* (not origin) that co-signs to launder.

    Carries no origin assertion of its own; its only power is to relay and
    re-sign. Warrant must stay bounded by the true origin regardless of how many
    of these are chained.
    """
    return AdversaryProfile(
        content="", true_source_class=SourceClass.UNKNOWN,
        declared_source_class=SourceClass.UNKNOWN,
        asserted_warrant=WarrantLevel.NONE,
        declared_transformation=TransformationType.PARAPHRASE,
        is_origin=False, label=label)
