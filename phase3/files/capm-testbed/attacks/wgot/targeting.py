"""Origin-targeting strategies + campaign runner for the WGOT attack (B3).

Given an :class:`capm.ecosystem.graph.Ecosystem`, a *strategy* produces a ranked
priority list of origins to capture. The attacker then captures greedily within a
fixed budget. The strategies span the obvious options plus the novel one:

* ``random``        — no information; shuffle (the control / lower bound).
* ``max_warrant``   — greedily target the highest *warrant ceiling* (the naive
                      "go for the most authoritative source" attacker).
* ``min_cost``      — greedily target the cheapest origin (lowest integrity).
* ``wgot``          — **Warrant Ceiling ÷ Capture Cost**: target the *weakest
                      high-warrant* origin first. The novel strategy.

WGOT needs only public information — `warrant_ceiling` is on every manifest, and
`capture_cost` is the attacker's own estimate of an origin's defenses. It never
needs to break CAPM's math (it can't — Lemma 1); it exploits the *coupling* of
warrant to integrity that the ecosystem leaves open.

The campaign runner is decoupled from CAPM: the caller injects an ``accept_fn``
that returns whether capturing a given node yields content CAPM will ACCEPT, so
the experiment can ground that decision in the *real* `WarrantEvaluator`.
"""

from __future__ import annotations

import dataclasses
import random
from typing import Callable

from capm.ecosystem.graph import Ecosystem, OriginNode

# A strategy ranks the nodes (highest priority first).
Strategy = Callable[[list[OriginNode], random.Random], list[OriginNode]]


def strat_random(nodes: list[OriginNode], rng: random.Random) -> list[OriginNode]:
    out = list(nodes)
    rng.shuffle(out)
    return out


def strat_max_warrant(nodes: list[OriginNode], rng: random.Random) -> list[OriginNode]:
    # tie-break randomly so ceiling ties don't smuggle in cost information
    return sorted(nodes, key=lambda n: (-n.warrant_ceiling, rng.random()))


def strat_min_cost(nodes: list[OriginNode], rng: random.Random) -> list[OriginNode]:
    return sorted(nodes, key=lambda n: (n.capture_cost, rng.random()))


def strat_wgot(nodes: list[OriginNode], rng: random.Random) -> list[OriginNode]:
    # the WGOT score: warrant ceiling per unit capture cost (higher = better target)
    return sorted(nodes, key=lambda n: (-(n.warrant_ceiling / n.capture_cost), rng.random()))


STRATEGIES: dict[str, Strategy] = {
    "random": strat_random,
    "max_warrant": strat_max_warrant,
    "min_cost": strat_min_cost,
    "wgot": strat_wgot,
}


@dataclasses.dataclass
class CampaignResult:
    strategy: str
    budget: float
    captured: int
    accepted_channels: int          # captures CAPM actually ACCEPTs (grounded)
    cost_spent: float
    warrant_laundered: int          # Σ ceiling over accepted channels
    n_high_value: int               # high-value origins available in the ecosystem

    @property
    def asr(self) -> float:
        """Fraction of the ecosystem's high-warrant surface compromised."""
        return self.accepted_channels / self.n_high_value if self.n_high_value else 0.0

    @property
    def efficiency_warrant(self) -> float:
        """Warrant laundered per unit capture cost — WGOT's own objective."""
        return self.warrant_laundered / self.cost_spent if self.cost_spent > 0 else 0.0

    @property
    def efficiency_channels(self) -> float:
        """Accepted channels per unit capture cost."""
        return self.accepted_channels / self.cost_spent if self.cost_spent > 0 else 0.0


def run_campaign(eco: Ecosystem, strategy: str, budget: float,
                 accept_fn: Callable[[OriginNode], bool],
                 rng: random.Random) -> CampaignResult:
    """Greedily capture origins in the strategy's priority order until the budget
    is exhausted, grounding each "did it produce accepted content?" decision in
    ``accept_fn`` (the real CAPM evaluator in the experiment)."""
    ranked = STRATEGIES[strategy](eco.nodes, rng)
    spent = 0.0
    captured = accepted = warrant_laundered = 0
    for node in ranked:
        if spent + node.capture_cost > budget:
            continue            # skip ones we cannot afford; keep scanning cheaper ones
        spent += node.capture_cost
        captured += 1
        if accept_fn(node):
            accepted += 1
            warrant_laundered += node.warrant_ceiling
    return CampaignResult(
        strategy=strategy, budget=budget, captured=captured,
        accepted_channels=accepted, cost_spent=spent,
        warrant_laundered=warrant_laundered,
        n_high_value=len(eco.high_value_nodes()))
