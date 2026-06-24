"""Synthetic ecosystem generator: origins with warrant *and* integrity.

Every origin in a real multi-agent ecosystem has two properties that an attacker
weighs independently:

* **warrant ceiling** — how much justification a receiver will grant content from
  this origin (CAPM's `SourceClass.warrant_ceiling`). This is *public*: it is the
  defense's own published classification, visible on every manifest. It is what
  makes an origin *worth* capturing.
* **integrity strength** — how hard the origin is to capture (key custody, vetting
  rigor, monitoring). This is the *cost* axis, and it is **orthogonal** to warrant
  in principle: a highly-authoritative origin can be poorly defended, and a
  worthless one can be a fortress.

The security-relevant question is how tightly an ecosystem *couples* these two.
A well-designed ecosystem makes warrant and integrity strongly positively
correlated (high-warrant ⇒ hard to capture); a careless one leaves them
independent or anti-correlated, opening cheap high-warrant targets. This module
generates ecosystems at a *tunable* correlation `rho` via a Gaussian copula
(pure stdlib), so B3 (WGOT) and B4 (cartography) can sweep that knob.
"""

from __future__ import annotations

import dataclasses
import math
import random
from typing import Optional

from capm.core.types import SourceClass, WarrantLevel

# Classes ordered by ceiling (ascending) — the quantile ladder the copula maps onto.
_CLASSES_BY_CEILING = sorted(SourceClass, key=lambda c: int(c.warrant_ceiling))

# Capture cost as a function of integrity strength ∈ [0,1]: a floor of 1 (nothing
# is free) up to 10 for an impregnable origin.
_COST_FLOOR = 1.0
_COST_SPAN = 9.0


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def capture_cost(integrity_strength: float) -> float:
    """Map integrity ∈ [0,1] to a capture cost ∈ [1,10]."""
    return _COST_FLOOR + _COST_SPAN * max(0.0, min(1.0, integrity_strength))


@dataclasses.dataclass(frozen=True)
class OriginNode:
    """One capturable origin in the ecosystem."""

    node_id: str
    source_class: SourceClass
    integrity_strength: float          # [0,1] — orthogonal to warrant in principle

    @property
    def warrant_ceiling(self) -> int:
        return int(self.source_class.warrant_ceiling)

    @property
    def capture_cost(self) -> float:
        return capture_cost(self.integrity_strength)

    @property
    def is_high_value(self) -> bool:
        """An origin worth capturing: its ceiling can clear the ACCEPT floor
        (MODERATE). Capturing a WEAK/NONE origin cannot produce accepted content."""
        return self.warrant_ceiling >= int(WarrantLevel.MODERATE)


@dataclasses.dataclass
class Ecosystem:
    nodes: list[OriginNode]
    target_rho: float                  # the requested ceiling↔integrity correlation
    actual_rho: float                  # the realised Pearson correlation (measured)

    def high_value_nodes(self) -> list[OriginNode]:
        return [n for n in self.nodes if n.is_high_value]

    def total_capture_cost(self) -> float:
        return sum(n.capture_cost for n in self.nodes)


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    vx = sum((a - mx) ** 2 for a in xs)
    vy = sum((b - my) ** 2 for b in ys)
    if vx == 0 or vy == 0:
        return float("nan")
    return cov / math.sqrt(vx * vy)


def generate_ecosystem(n: int, rho: float, seed: int) -> Ecosystem:
    """Generate `n` origins with a target ceiling↔integrity correlation `rho`.

    Uses a Gaussian copula: draw correlated latents (z1, z2); map z1 → source
    class by quantile (so ceiling tracks z1) and z2 → integrity strength. The
    realised Pearson correlation is measured and stored (discretising the class
    ladder makes it approximate, so we report the actual value, never assume it).
    """
    rng = random.Random(seed)
    nodes: list[OriginNode] = []
    r = max(-1.0, min(1.0, rho))
    tail = math.sqrt(max(0.0, 1.0 - r * r))
    for i in range(n):
        z1 = rng.gauss(0.0, 1.0)
        z2 = r * z1 + tail * rng.gauss(0.0, 1.0)
        u1 = _norm_cdf(z1)
        idx = min(len(_CLASSES_BY_CEILING) - 1, int(u1 * len(_CLASSES_BY_CEILING)))
        cls = _CLASSES_BY_CEILING[idx]
        integrity = _norm_cdf(z2)
        nodes.append(OriginNode(node_id=f"org-{i:03d}", source_class=cls,
                                integrity_strength=integrity))

    actual = _pearson([float(n.warrant_ceiling) for n in nodes],
                      [n.integrity_strength for n in nodes])
    return Ecosystem(nodes=nodes, target_rho=rho, actual_rho=actual)


# ===========================================================================
# Network topologies (P2-B4 cartography)
# ===========================================================================
# Realistic source-class mix: authoritative origins are RARE, low-warrant
# origins (web pages, wikis, tools, model memory) are COMMON. ~30% of sources
# clear the ACCEPT ceiling (PUBLIC_WEBPAGE/FIRST_PARTY_DB and up).
_CLASS_WEIGHTS = [
    (SourceClass.AUTHORITATIVE_API, 0.04),
    (SourceClass.VERIFIED_DOCUMENT, 0.04),
    (SourceClass.FIRST_PARTY_DB, 0.08),
    (SourceClass.PUBLIC_WEBPAGE, 0.14),
    (SourceClass.EDITABLE_SOURCE, 0.20),
    (SourceClass.UNTRUSTED_TOOL, 0.15),
    (SourceClass.MODEL_MEMORY, 0.15),
    (SourceClass.UNKNOWN, 0.20),
]


@dataclasses.dataclass
class Topology:
    """A provenance topology: relay agents + capturable sources + claim reach.

    `reach[node_id]` is how many principals receive claims that originate at that
    source — its "value" as a chokepoint. Relay agents are counted only for the
    pre-CAPM attack surface; by Lemma 1 they cannot launder, so they never enter
    the post-CAPM surface.
    """

    name: str
    n_agents: int                       # relay agents (non-origin nodes)
    n_principals: int
    sources: list[OriginNode]
    reach: dict[str, int]               # source node_id -> #principals served

    def pre_capm_surface(self) -> int:
        """Every node an attacker could try to subvert pre-CAPM: agents + sources."""
        return self.n_agents + len(self.sources)


def _sample_class(rng: random.Random) -> SourceClass:
    r = rng.random()
    acc = 0.0
    for cls, w in _CLASS_WEIGHTS:
        acc += w
        if r <= acc:
            return cls
    return _CLASS_WEIGHTS[-1][0]


def _assign_reach(sources: list[OriginNode], n_principals: int, zipf_s: float,
                  rng: random.Random) -> dict[str, int]:
    """Assign each source a reach via a Zipf law, with authoritative sources
    ranked higher (the realistic 'authoritative origins are also the popular,
    widely-queried ones' assumption — stated, not hidden). Reach of the rank-r
    source ≈ n_principals / (r+1)^zipf_s."""
    # popularity key: warrant ceiling dominates, broken by noise → rank order
    ranked = sorted(sources, key=lambda s: (-(s.warrant_ceiling + rng.random()),))
    reach = {}
    for r, node in enumerate(ranked):
        reach[node.node_id] = max(1, round(n_principals / ((r + 1) ** zipf_s)))
    return reach


def _make_sources(n: int, seed: int, tag: str) -> list[OriginNode]:
    rng = random.Random(seed)
    return [OriginNode(node_id=f"{tag}-src-{i:03d}", source_class=_sample_class(rng),
                       integrity_strength=rng.random()) for i in range(n)]


def make_star_hub(seed: int) -> Topology:
    """A few hub relays consolidate many sources to many principals. FEW agents,
    concentrated reach (a handful of sources dominate)."""
    rng = random.Random(seed + 1)
    sources = _make_sources(18, seed + 1, "star")
    n_principals, n_agents = 40, 2
    reach = _assign_reach(sources, n_principals, zipf_s=1.4, rng=rng)
    return Topology("star_hub", n_agents, n_principals, sources, reach)


def make_deep_chain(seed: int) -> Topology:
    """Long linear chains: each source feeds a deep stack of relays to one
    principal. MANY relay agents, flatter reach."""
    rng = random.Random(seed + 2)
    n_sources, depth = 25, 6
    sources = _make_sources(n_sources, seed + 2, "deep")
    n_agents = n_sources * depth
    n_principals = n_sources
    reach = _assign_reach(sources, n_principals, zipf_s=0.7, rng=rng)
    return Topology("deep_chain", n_agents, n_principals, sources, reach)


def make_wide_fan(seed: int) -> Topology:
    """Each source fans out through many relays to many principals. MANY agents,
    moderately flat reach."""
    rng = random.Random(seed + 3)
    n_sources, fan = 12, 10
    sources = _make_sources(n_sources, seed + 3, "fan")
    n_agents = n_sources * fan
    n_principals = n_sources * fan
    reach = _assign_reach(sources, n_principals, zipf_s=0.6, rng=rng)
    return Topology("wide_fan", n_agents, n_principals, sources, reach)


def make_multi_org_mesh(seed: int) -> Topology:
    """A cross-org mesh: many sources, many interconnecting relays, moderate
    reach concentration."""
    rng = random.Random(seed + 4)
    n_sources, n_agents, n_principals = 35, 70, 45
    sources = _make_sources(n_sources, seed + 4, "mesh")
    reach = _assign_reach(sources, n_principals, zipf_s=1.0, rng=rng)
    return Topology("multi_org_mesh", n_agents, n_principals, sources, reach)


TOPOLOGY_GENERATORS = {
    "star_hub": make_star_hub,
    "deep_chain": make_deep_chain,
    "wide_fan": make_wide_fan,
    "multi_org_mesh": make_multi_org_mesh,
}
