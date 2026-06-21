"""Agent layer: SAGA-aligned agents that emit and consume CAPM manifests.

The :class:`LocalAgent` interface mirrors SAGA's ``saga.local_agent.LocalAgent``
ABC (a ``run(query, initiating_agent, agent_instance)`` method) so that the
:mod:`capm.adapters.saga_adapter` can drop these agents into a real SAGA
deployment unchanged. In the standalone testbed the agents talk over an
in-process :class:`CAPMChannel` instead of SAGA's TLS sockets.
"""

from __future__ import annotations

import abc
import dataclasses
import hashlib
import time
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:  # forward refs only; no runtime dependency / import cycle
    from attacks.adaptive.profiles import AdversaryProfile, ForgeryMode

from capm.core.types import (Source, SourceClass, TransformationType,
                             WarrantLevel)
from capm.core.value import WarrantedValue
from capm.identity.credentials import AgentIdentity, CredentialRegistry
from capm.manifest.capm_manifest import CAPMManifest
from capm.warrant.evaluator import (Decision, EvaluatorPolicy, WarrantEvaluator,
                                    WarrantVerdict)


# ---------------------------------------------------------------------------
# Message envelope
# ---------------------------------------------------------------------------
@dataclasses.dataclass
class CAPMMessage:
    """What flows between agents: content + the signed manifest.

    ``manifest`` is ``None`` for baselines that do not carry provenance.
    """

    content: str
    manifest: Optional[CAPMManifest] = None
    sender_did: Optional[str] = None
    sender_org: Optional[str] = None

    def strip_metadata(self) -> "CAPMMessage":
        """Simulate text leaving the log environment (S3 scenario)."""
        return CAPMMessage(content=self.content)


# ---------------------------------------------------------------------------
# SAGA-aligned base interface
# ---------------------------------------------------------------------------
class LocalAgent(abc.ABC):
    """Mirror of SAGA's LocalAgent ABC."""

    @abc.abstractmethod
    def run(self, query: str, initiating_agent: bool = False,
            agent_instance: Optional["LocalAgent"] = None) -> tuple["LocalAgent", str]:
        ...


# ---------------------------------------------------------------------------
# CAPM agents
# ---------------------------------------------------------------------------
class CAPMAgent(LocalAgent):
    """An agent that signs a CAPM segment onto every value it emits.

    ``responder`` is a pluggable callable ``(query, inputs) -> (content,
    transformation)`` standing in for the underlying LLM. The testbed uses
    deterministic responders so experiments are reproducible without API keys;
    the :mod:`capm.adapters` layer swaps in real model calls.
    """

    def __init__(self, did: str, org: str, identity: AgentIdentity,
                 registry: CredentialRegistry, *,
                 responder: Optional[Callable[[str, list[WarrantedValue]],
                                              tuple[str, TransformationType]]] = None,
                 downstream: Optional[list["CAPMAgent"]] = None,
                 evaluator_policy: Optional[EvaluatorPolicy] = None,
                 owns_source: Optional[tuple[Source, str]] = None,
                 adversary: Optional["AdversaryProfile"] = None,
                 clock: Optional[Callable[[], float]] = None):
        self.did = did
        self.org = org
        self.identity = identity
        self.registry = registry
        self.responder = responder or self._default_responder
        self.downstream = downstream or []
        self.evaluator = WarrantEvaluator(registry, evaluator_policy)
        self.owns_source = owns_source       # (Source, content) if this is a tail agent
        # An AdversaryProfile (attacks.adaptive) makes this agent emit
        # adversarially: lie about source class / transformation, or forge the
        # binding. None => honest. See attacks/adaptive/profiles.py.
        self.adversary = adversary
        # Injectable clock so experiments can be fully deterministic (E9.1).
        self._clock = clock or time.time
        self.last_verdict: Optional[WarrantVerdict] = None

    # default deterministic responder: faithfully relays (paraphrase) ----
    @staticmethod
    def _default_responder(query: str, inputs: list[WarrantedValue]):
        if inputs:
            return inputs[0].content, TransformationType.PARAPHRASE
        return f"[no data for: {query}]", TransformationType.GENERATION

    # ---- emit a value as a signed message ----------------------------
    def _emit(self, value: WarrantedValue, to_org: str,
              transformation: TransformationType,
              origin_source_class: Optional[SourceClass],
              origin_warrant: Optional[WarrantLevel],
              forgery: Optional["ForgeryMode"] = None) -> CAPMMessage:
        manifest = value.other_metadata.get("manifest") or CAPMManifest()
        soft = hashlib.sha256(
            " ".join(sorted(value.content.lower().split())).encode()).hexdigest()
        seg = manifest.append_segment(
            identity=self.identity, content=value.content,
            transformation=transformation, from_org=self.org, to_org=to_org,
            origin_source_class=origin_source_class,
            asserted_origin_warrant=origin_warrant,
            soft_binding=soft, timestamp=self._clock())
        if forgery is not None:
            self._apply_forgery(manifest, seg, forgery)
        manifest.attach_prov(value.chain)
        value.other_metadata["manifest"] = manifest
        return CAPMMessage(content=value.content, manifest=manifest,
                           sender_did=self.did, sender_org=self.org)

    @staticmethod
    def _apply_forgery(manifest: CAPMManifest, seg, forgery: "ForgeryMode") -> None:
        """Tamper with the cryptographic binding (E3.3). All must fail to verify."""
        from attacks.adaptive.profiles import ForgeryMode
        if forgery is ForgeryMode.NONE:
            return
        if forgery is ForgeryMode.FAKE_SIGNATURE:
            seg.signature = "AAAA" + (seg.signature or "")[4:]   # corrupt the sig
        elif forgery is ForgeryMode.REPLAY_SEGMENT and len(manifest.segments) >= 2:
            seg.signature = manifest.segments[-2].signature      # replay another sig
        elif forgery is ForgeryMode.SUBSTITUTE_VC and len(manifest.segments) >= 2:
            # claim a different (trusted) DID's identity but keep our own key:
            # registry VC pubkey will not match the embedded VC -> reject.
            victim = manifest.segments[0]
            seg.agent_did = victim.agent_did

    # ---- LocalAgent.run ----------------------------------------------
    def run(self, query: str, initiating_agent: bool = False,
            agent_instance: Optional[LocalAgent] = None) -> tuple[LocalAgent, str]:
        # 1. gather inputs from downstream agents (recursively)
        inputs: list[WarrantedValue] = []
        for child in self.downstream:
            msg = child.handle(query, caller_org=self.org)
            verdict = self.evaluator.evaluate(msg.manifest, msg.content) if msg.manifest else None
            self.last_verdict = verdict
            wv = self._message_to_value(msg)
            if verdict is None or verdict.accepted:
                inputs.append(wv)
        # 2. produce our own value
        content, transformation = self.responder(query, inputs)
        out = self._make_output(content, transformation, inputs)
        return self, out.content

    def handle(self, query: str, caller_org: str) -> CAPMMessage:
        """Respond to an upstream caller, emitting a signed message."""
        # adversarial origin (E3.1/E3.2/E3.3): emit using *declared* (possibly
        # lying) class/warrant/transformation, with optional forgery. Ground
        # truth is preserved on the Source for attribution metrics.
        if self.adversary is not None and self.adversary.is_origin:
            return self._emit_adversarial_origin(self.adversary, caller_org)
        # honest tail agent: fabricate from its owned source
        if self.owns_source is not None and not self.downstream:
            source, content = self.owns_source
            wv = WarrantedValue.from_origin(content, org=self.org, source=source)
            return self._emit(wv, to_org=caller_org,
                              transformation=TransformationType.VERBATIM,
                              origin_source_class=source.source_class,
                              origin_warrant=source.source_class.warrant_ceiling)
        # intermediary: query its own downstream, transform, re-sign.
        # A relay forwards any content whose signatures VERIFY; the warrant
        # level is the *principal's* decision, not a relay gate. Dropping
        # low-but-valid warrant here would truncate the chain and hide
        # provenance from the principal - the opposite of what CAPM wants.
        inputs: list[WarrantedValue] = []
        for child in self.downstream:
            msg = child.handle(query, caller_org=self.org)
            verdict = self.evaluator.evaluate(msg.manifest, msg.content) if msg.manifest else None
            self.last_verdict = verdict
            # forward unless signatures are broken (REJECT)
            from capm.warrant.evaluator import Decision as _D
            if verdict is None or verdict.decision != _D.REJECT:
                inputs.append(self._message_to_value(msg))
        content, transformation = self.responder(query, inputs)
        out = self._make_output(content, transformation, inputs)
        # a malicious *relay* (E3.1/E3.4) may lie about its transformation type
        # or forge; warrant must still stay bounded by the true origin.
        declared = transformation
        forgery = None
        if self.adversary is not None and not self.adversary.is_origin:
            declared = self.adversary.declared_transformation
            forgery = self.adversary.forgery
        return self._emit(out, to_org=caller_org, transformation=declared,
                         origin_source_class=None, origin_warrant=None,
                         forgery=forgery)

    def _emit_adversarial_origin(self, adv: "AdversaryProfile",
                                 caller_org: str) -> CAPMMessage:
        """Emit an origin segment under an adversary profile.

        The manifest carries the *declared* (possibly false) source class and
        asserted warrant; the :class:`~capm.core.types.Source` retains the
        *true* class so attribution/oracle metrics can recover ground truth even
        when the receiver is fooled (the honest boundary of CLAIM-1; see E3.2).
        """
        true_src = Source(f"origin:{adv.label}", adv.true_source_class,
                          metadata={"attack": adv.label,
                                    "declared_class": adv.declared_source_class.value,
                                    "is_malicious": adv.is_malicious})
        wv = WarrantedValue.from_origin(adv.content, org=self.org, source=true_src)
        return self._emit(wv, to_org=caller_org,
                          transformation=adv.declared_transformation,
                          origin_source_class=adv.declared_source_class,
                          origin_warrant=adv.asserted_warrant,
                          forgery=adv.forgery)

    # ---- helpers ------------------------------------------------------
    def _make_output(self, content: str, transformation: TransformationType,
                     inputs: list[WarrantedValue]) -> WarrantedValue:
        now = time.time()
        if not inputs:
            src = Source("model_memory", SourceClass.MODEL_MEMORY)
            return WarrantedValue.from_origin(content, org=self.org, source=src)
        if len(inputs) == 1:
            out = inputs[0].transform(content, agent_id=self.did,
                                      transformation=transformation,
                                      to_org=self.org, timestamp=now)
        else:
            out = WarrantedValue.compose(inputs, content, agent_id=self.did,
                                         to_org=self.org, timestamp=now)
        # thread the incoming manifest forward so _emit appends to it
        for inp in inputs:
            if "manifest" in inp.other_metadata:
                out.other_metadata["manifest"] = inp.other_metadata["manifest"]
                break
        return out

    @staticmethod
    def _message_to_value(msg: CAPMMessage) -> WarrantedValue:
        src = Source("relayed", SourceClass.UNKNOWN)
        wv = WarrantedValue.from_origin(msg.content, org=msg.sender_org or "?", source=src)
        if msg.manifest is not None:
            wv.other_metadata["manifest"] = msg.manifest
        return wv
