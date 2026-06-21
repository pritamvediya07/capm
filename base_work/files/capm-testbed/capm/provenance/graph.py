"""Cross-organisational provenance graph (Component 1 of CAPM).

This is the adversarial, cross-org extension of PROV-AGENT
(arXiv:2508.02866). PROV-AGENT models ``AIAgent`` as a subclass of the W3C
PROV ``Agent`` for *honest, single-workflow* settings. We keep the same
entity/activity/agent skeleton but add the three things PROV-AGENT lacks for
our threat model:

1. **Field-level granularity** - a node is a *claim* (a span), not a whole
   document. (Closes open challenge P2.)
2. **A transformation type on every derivation edge** - so warrant erosion is
   attributable to a specific transformation. (Warrant Erosion Principle.)
3. **An organisational-boundary marker on edges** - cross-domain edges are
   first-class because that is where re-signing and re-verification happen.
   (Closes the cross-org gap the SoK names.)

The graph is intentionally serialisable to W3C-PROV-style triples
(:meth:`ProvenanceChain.to_prov_triples`) so the work remains standards
adjacent, but the runtime representation is a lightweight DAG.
"""

from __future__ import annotations

import dataclasses
import hashlib
import uuid
from typing import Iterable, Optional

from capm.core.types import Source, TransformationType, WarrantLevel


def _new_id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4().hex[:12]}"


@dataclasses.dataclass
class ClaimNode:
    """A field-level claim (PROV ``Entity``).

    ``content_hash`` binds the node to specific bytes so a manifest can later
    detect off-manifest regeneration (see :mod:`capm.warrant.evaluator`).
    """

    node_id: str
    content: str
    content_hash: str
    org: str                                   # organisation that holds this claim
    origin_source: Optional[Source] = None     # set only on tail/origin nodes
    asserted_warrant: WarrantLevel = WarrantLevel.NONE

    @classmethod
    def create(cls, content: str, org: str, **kw) -> "ClaimNode":
        h = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return cls(node_id=_new_id("claim"), content=content,
                   content_hash=h, org=org, **kw)


@dataclasses.dataclass
class DerivationEdge:
    """A PROV ``wasDerivedFrom`` edge produced by an agent ``Activity``.

    Crossing an org boundary is marked explicitly; the warrant evaluator
    treats those edges specially.
    """

    edge_id: str
    src_node_id: str                 # the input claim
    dst_node_id: str                 # the produced claim
    agent_id: str                    # the AIAgent that performed the activity
    transformation: TransformationType
    crosses_org_boundary: bool
    from_org: str
    to_org: str
    timestamp: float


@dataclasses.dataclass
class ProvenanceChain:
    """A DAG of claims and derivations for one delivered response.

    The chain is what travels (signed) alongside the message. A receiver
    reconstructs and verifies it before forming beliefs.
    """

    nodes: dict[str, ClaimNode] = dataclasses.field(default_factory=dict)
    edges: list[DerivationEdge] = dataclasses.field(default_factory=list)
    head_node_id: Optional[str] = None   # the final delivered claim

    # ---- construction -------------------------------------------------
    def add_origin(self, content: str, org: str, source: Source,
                   warrant: WarrantLevel) -> ClaimNode:
        node = ClaimNode.create(content, org, origin_source=source,
                                asserted_warrant=warrant)
        self.nodes[node.node_id] = node
        self.head_node_id = node.node_id
        return node

    def add_transformation(self, src: ClaimNode, content: str, *,
                           agent_id: str, transformation: TransformationType,
                           to_org: str, timestamp: float) -> ClaimNode:
        dst = ClaimNode.create(content, to_org)
        self.nodes[dst.node_id] = dst
        crosses = src.org != to_org
        self.edges.append(DerivationEdge(
            edge_id=_new_id("edge"), src_node_id=src.node_id,
            dst_node_id=dst.node_id, agent_id=agent_id,
            transformation=transformation, crosses_org_boundary=crosses,
            from_org=src.org, to_org=to_org, timestamp=timestamp))
        self.head_node_id = dst.node_id
        return dst

    def add_composition(self, srcs: Iterable[ClaimNode], content: str, *,
                        agent_id: str, to_org: str, timestamp: float) -> ClaimNode:
        dst = ClaimNode.create(content, to_org)
        self.nodes[dst.node_id] = dst
        for src in srcs:
            self.edges.append(DerivationEdge(
                edge_id=_new_id("edge"), src_node_id=src.node_id,
                dst_node_id=dst.node_id, agent_id=agent_id,
                transformation=TransformationType.COMPOSITION,
                crosses_org_boundary=(src.org != to_org),
                from_org=src.org, to_org=to_org, timestamp=timestamp))
        self.head_node_id = dst.node_id
        return dst

    # ---- traversal ----------------------------------------------------
    def parents_of(self, node_id: str) -> list[DerivationEdge]:
        return [e for e in self.edges if e.dst_node_id == node_id]

    def path_to_origins(self, node_id: str) -> list[list[DerivationEdge]]:
        """All edge-paths from ``node_id`` back to origin (tail) nodes."""
        parents = self.parents_of(node_id)
        if not parents:
            return [[]]
        paths: list[list[DerivationEdge]] = []
        for e in parents:
            for sub in self.path_to_origins(e.src_node_id):
                paths.append([e] + sub)
        return paths

    def origin_nodes(self, node_id: str) -> list[ClaimNode]:
        outs: list[ClaimNode] = []
        for path in self.path_to_origins(node_id):
            origin_id = path[-1].src_node_id if path else node_id
            outs.append(self.nodes[origin_id])
        return outs

    def boundary_crossings(self, node_id: str) -> int:
        """Max number of org boundaries crossed on any path to an origin."""
        best = 0
        for path in self.path_to_origins(node_id):
            best = max(best, sum(1 for e in path if e.crosses_org_boundary))
        return best

    # ---- standards-adjacency -----------------------------------------
    def to_prov_triples(self) -> list[tuple[str, str, str]]:
        """Emit W3C-PROV-style triples (keeps the work standards adjacent)."""
        triples: list[tuple[str, str, str]] = []
        for n in self.nodes.values():
            triples.append((n.node_id, "rdf:type", "prov:Entity"))
            if n.origin_source is not None:
                triples.append((n.node_id, "prov:wasAttributedTo",
                                n.origin_source.source_id))
        for e in self.edges:
            triples.append((e.dst_node_id, "prov:wasDerivedFrom", e.src_node_id))
            triples.append((e.dst_node_id, "prov:wasGeneratedBy",
                            f"activity:{e.edge_id}"))
            triples.append((f"activity:{e.edge_id}", "prov:wasAssociatedWith",
                            f"agent:{e.agent_id}"))
            triples.append((f"activity:{e.edge_id}", "capm:transformation",
                            e.transformation.value))
            if e.crosses_org_boundary:
                triples.append((f"activity:{e.edge_id}", "capm:crossesOrg",
                                f"{e.from_org}->{e.to_org}"))
        return triples
