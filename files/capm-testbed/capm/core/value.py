"""WarrantedValue - a value plus its provenance chain (Component 1, runtime side).

This is the direct descendant of CaMeL's ``Capabilities``
(google-research/camel-prompt-injection,
``src/camel/capabilities/capabilities.py``). CaMeL attaches an immutable
``sources_set`` / ``readers_set`` to every value and enforces flows inside a
*single runtime*. We extend the idea so the metadata also carries a
:class:`~capm.provenance.graph.ProvenanceChain` and is designed to survive the
agent-to-agent, cross-organisational boundary by being signed into a manifest
(see :mod:`capm.manifest.capm_manifest`).

We deliberately do NOT re-use CaMeL's interpreter; per the build-strategy
decision we *port the pattern* and keep our own clean module.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Optional

from capm.core.types import Source, TransformationType, WarrantLevel
from capm.provenance.graph import ClaimNode, ProvenanceChain


@dataclasses.dataclass
class WarrantedValue:
    """A piece of content together with everything needed to judge its warrant.

    Attributes
    ----------
    content:
        The actual text/claim.
    chain:
        The provenance DAG ending at ``head``.
    head:
        The :class:`ClaimNode` in ``chain`` representing this value.
    verified:
        Set by the receiver-side evaluator after signature verification.
        ``None`` means "not yet verified".
    """

    content: str
    chain: ProvenanceChain
    head: ClaimNode
    verified: Optional[bool] = None
    other_metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    # ---- factory: an origin value (chain tail) ------------------------
    @classmethod
    def from_origin(cls, content: str, *, org: str, source: Source) -> "WarrantedValue":
        chain = ProvenanceChain()
        node = chain.add_origin(content, org, source, source.source_class.warrant_ceiling)
        return cls(content=content, chain=chain, head=node)

    # ---- transform into a new value, extending the chain --------------
    def transform(self, new_content: str, *, agent_id: str,
                  transformation: TransformationType, to_org: str,
                  timestamp: float) -> "WarrantedValue":
        node = self.chain.add_transformation(
            self.head, new_content, agent_id=agent_id,
            transformation=transformation, to_org=to_org, timestamp=timestamp)
        return WarrantedValue(content=new_content, chain=self.chain, head=node)

    @staticmethod
    def compose(values: list["WarrantedValue"], new_content: str, *,
                agent_id: str, to_org: str, timestamp: float) -> "WarrantedValue":
        """Combine several warranted values (e.g. a synthesised answer).

        All input chains are merged so the composite head can be traced back
        to every contributing origin. Warrant of the composite is bounded by
        the *weakest* contributing input (see the evaluator).
        """
        merged = ProvenanceChain()
        heads: list[ClaimNode] = []
        for v in values:
            merged.nodes.update(v.chain.nodes)
            merged.edges.extend(v.chain.edges)
            heads.append(v.head)
        node = merged.add_composition(heads, new_content, agent_id=agent_id,
                                      to_org=to_org, timestamp=timestamp)
        return WarrantedValue(content=new_content, chain=merged, head=node)
