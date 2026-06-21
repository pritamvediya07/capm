"""Multi-hop, multi-organisation scenario builder (the testbed core).

Builds the agent chain from the design doc's worked example:

    Source S --> gamma (org C) --> beta (org B) --> alpha (org A) --> Principal

Each agent is in a different organisation, so every hop is a cross-org
boundary - which is exactly the boundary existing defenses cannot see across.

The builder supports the four stages of the evaluation ladder:

* **S0** honest path: a high-warrant origin flows up the chain.
* **S1** adversarial: an attack injector plants low-warrant content at the
  tail; we measure whether the receiver down-weights it.
* **S2** N-hop: arbitrary chain length to measure the warrant-erosion curve.
* **S3** text-only: the manifest metadata is stripped before delivery; only
  the soft-binding/watermark remains.

Adversaries are now expressed as :class:`attacks.adaptive.profiles.AdversaryProfile`
objects rather than a monkeypatch. The legacy ``attack`` callable (an injector's
``make_source`` returning ``(Source, content, asserted_warrant)``) is still
accepted and mapped to a truthful-class / inflated-warrant profile, so existing
experiments and tests are unchanged. New experiments pass an ``adversary=``
profile directly (e.g. origin capture, forgery, lying transformation).
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Optional

from attacks.adaptive.profiles import (AdversaryProfile, honest_origin,
                                        inflated_warrant_origin)
from capm.agents.agent import CAPMAgent, CAPMMessage
from capm.core.types import Source, SourceClass, TransformationType, WarrantLevel
from capm.identity.credentials import AgentIdentity, CredentialRegistry
from capm.warrant.evaluator import EvaluatorPolicy

# A fixed clock keeps manifests byte-stable across runs (reproducibility, E9.1).
_FIXED_CLOCK = lambda: 1_700_000_000.0  # noqa: E731


@dataclasses.dataclass
class Scenario:
    """A fully wired chain ready to run."""

    registry: CredentialRegistry
    principal_facing: CAPMAgent          # alpha - the agent the principal asks
    chain: list[CAPMAgent]               # [alpha, beta, gamma, ...] head->tail
    expected_malicious: bool             # ground truth: is the tail content an attack?
    label: str
    adversary: Optional[AdversaryProfile] = None   # the origin profile in play

    def query(self, q: str) -> CAPMMessage:
        """Run the query; return the message alpha would hand the principal."""
        return self.principal_facing.handle(q, caller_org="org-principal")


def _make_agent(name: str, org: str, registry: CredentialRegistry, **kw) -> CAPMAgent:
    ident = AgentIdentity(did=f"did:capm:{name}", org=org)
    registry.register(ident)
    # scenarios pass `policy=`; CAPMAgent expects `evaluator_policy=`
    if "policy" in kw:
        kw["evaluator_policy"] = kw.pop("policy")
    kw.setdefault("clock", _FIXED_CLOCK)
    return CAPMAgent(did=ident.did, org=org, identity=ident, registry=registry, **kw)


def build_chain(*, n_hops: int = 3,
                attack: Optional[Callable[[], tuple[Source, str, WarrantLevel]]] = None,
                adversary: Optional[AdversaryProfile] = None,
                honest_source_class: SourceClass = SourceClass.AUTHORITATIVE_API,
                honest_content: str = "The verified specification value is 42.",
                policy: Optional[EvaluatorPolicy] = None,
                register_tail: bool = True,
                relay_adversaries: Optional[dict[int, AdversaryProfile]] = None,
                relay_responder: Optional[Callable] = None) -> Scenario:
    """Build an n-hop cross-org chain.

    Parameters
    ----------
    n_hops:
        Number of agents in the chain (>=1). Each is in its own org, so there
        are ``n_hops`` cross-org boundaries up to the principal.
    attack:
        Legacy injector callable returning ``(Source, content, asserted)``. The
        origin truthfully declares its class and inflates the warrant number -
        the *weak* adversary. Mapped to an ``inflated_warrant_origin`` profile.
    adversary:
        An explicit origin :class:`AdversaryProfile` (overrides ``attack``).
        Use this for the adaptive adversaries (origin capture, forgery, ...).
    relay_adversaries:
        Map of chain-index (0 = head/alpha) -> profile for malicious *relays*
        (E3.1 lying transformation, E3.4 collusion). is_origin must be False.
    register_tail:
        If False, the tail agent's DID is NOT added to the registry - used to
        test signature rejection of an unknown signer.
    """
    registry = CredentialRegistry()
    policy = policy or EvaluatorPolicy()

    # resolve the origin profile (honest / legacy attack / explicit adversary)
    if adversary is not None:
        origin_profile = adversary
        expected_malicious = adversary.is_malicious
    elif attack is not None:
        src, content, asserted = attack()
        origin_profile = inflated_warrant_origin(
            content, true_class=src.source_class, asserted=asserted,
            label=getattr(attack, "__self__", None).name  # type: ignore[union-attr]
            if hasattr(attack, "__self__") else "attack")
        expected_malicious = True
    else:
        origin_profile = honest_origin(honest_content, honest_source_class)
        expected_malicious = False

    # build tail -> head
    orgs = [f"org-{chr(ord('A') + i)}" for i in range(n_hops)]
    agents: list[CAPMAgent] = []
    tail = _make_agent("agent_tail", orgs[-1], registry, policy=policy,
                       adversary=origin_profile)
    agents.append(tail)

    downstream = tail
    for i in range(n_hops - 2, -1, -1):
        a = _make_agent(f"agent_{i}", orgs[i], registry, policy=policy,
                        downstream=[downstream])
        agents.append(a)
        downstream = a

    agents.reverse()           # head .. tail
    head = agents[0] if agents else tail

    # install a real (e.g. Gemini) responder on every relay agent. Shared
    # instance -> shared cache + shared request budget, which is what makes the
    # "build once per content" efficient run stay under the daily quota.
    if relay_responder is not None:
        for ag in agents:
            if ag.downstream:        # relays only; the tail/origin emits directly
                ag.responder = relay_responder

    # attach relay adversaries by head-relative index. A malicious *relay*
    # (forgery, lying transformation, collusion) makes the whole chain
    # adversarial even when the origin profile itself is honest.
    if relay_adversaries:
        for idx, prof in relay_adversaries.items():
            if 0 <= idx < len(agents):
                agents[idx].adversary = prof
                if getattr(prof, "responder_override", None) is not None:
                    agents[idx].responder = prof.responder_override
        if any(getattr(p, "is_malicious", False) for p in relay_adversaries.values()):
            expected_malicious = True

    # If we asked not to register the tail, drop it from the registry now.
    if not register_tail:
        registry._by_did.pop(tail.did, None)  # noqa: SLF001 (test hook)

    return Scenario(registry=registry, principal_facing=head, chain=agents,
                    expected_malicious=expected_malicious,
                    label=origin_profile.label, adversary=origin_profile)
