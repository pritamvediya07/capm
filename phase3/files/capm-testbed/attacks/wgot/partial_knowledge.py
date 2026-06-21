"""WGOT under partial knowledge (P2-B5).

B3's WGOT attacker had an oracle: it read every origin's exact warrant ceiling.
A real attacker doesn't — it must **probe** to learn ceilings, under two frictions:

* **noisy observation** — each probe returns the ceiling plus measurement noise
  (the attacker infers warrant from an origin's behaviour / acceptance signals,
  which is imperfect);
* **a limited probing budget** — only so many probes can be spent before the
  campaign, so most ceilings are estimated from few (or zero) observations.

This module implements that attacker. It estimates each origin's ceiling from the
probes it can afford (falling back to the population prior for unprobed origins),
then runs WGOT on the *estimates*. The capture's success is still decided by the
origin's *true* ceiling (via the real evaluator in the experiment), so bad
estimates waste capture budget — the cost of imperfect reconnaissance.
"""

from __future__ import annotations

import dataclasses
import random
from typing import Optional

from capm.ecosystem.graph import Ecosystem, OriginNode

_MAXLVL = 4.0


def _ceiling_frac(node: OriginNode) -> float:
    return node.warrant_ceiling / _MAXLVL


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclasses.dataclass
class ProbeEstimator:
    """Turns a probing budget into per-origin ceiling estimates.

    ``noise_sigma`` is the std-dev of a single probe's observation error (on the
    [0,1] ceiling-fraction scale). Probes are spread round-robin over a shuffled
    origin order, so each origin receives ``floor(budget/N)`` or ``+1`` probes;
    origins that receive none are estimated by the ``prior`` (the attacker knows
    the population mean but not the individual)."""

    noise_sigma: float

    def estimate(self, eco: Ecosystem, probe_budget: int, rng: random.Random,
                 prior: Optional[float] = None) -> dict[str, float]:
        nodes = list(eco.nodes)
        n = len(nodes)
        if prior is None:
            prior = sum(_ceiling_frac(x) for x in nodes) / n      # population mean
        order = list(range(n))
        rng.shuffle(order)
        probes = [probe_budget // n] * n
        for i in range(probe_budget % n):
            probes[order[i]] += 1

        est: dict[str, float] = {}
        for idx, node in enumerate(nodes):
            k = probes[idx]
            if k == 0:
                est[node.node_id] = prior
            else:
                true = _ceiling_frac(node)
                obs = [_clamp01(true + rng.gauss(0.0, self.noise_sigma)) for _ in range(k)]
                est[node.node_id] = sum(obs) / k
        return est


def wgot_select_partial(eco: Ecosystem, estimates: dict[str, float],
                        capture_budget: float) -> tuple[list[OriginNode], float]:
    """WGOT on *estimated* ceilings: rank by est_ceiling / capture_cost, capture
    greedily within budget. Returns (captured_nodes, cost_spent)."""
    ranked = sorted(eco.nodes,
                    key=lambda nd: -(estimates[nd.node_id] / nd.capture_cost))
    captured, spent = [], 0.0
    for nd in ranked:
        if spent + nd.capture_cost <= capture_budget:
            spent += nd.capture_cost
            captured.append(nd)
    return captured, spent
