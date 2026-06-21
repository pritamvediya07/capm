"""E7.1 - utility-resistance (Pareto) frontier.

Sweeps the evaluator's accept floor (and boundary penalty) and plots ASR vs.
utility. A stricter floor lowers ASR but also lowers utility (honest content is
down-weighted sooner); the frontier characterises the trade-off and turns the
single 0.75 utility point into a curve. CAPM should dominate the baselines:
lower ASR at equal utility.

Run:  python -m experiments.e7_1_frontier
"""

from __future__ import annotations

from capm.benchmark.harness import run_matrix
from capm.benchmark.runner import asr, utility
from capm.core.types import WarrantLevel
from capm.warrant.evaluator import EvaluatorPolicy

# adversaries CAPM is meant to contain (origin-capture is the honest boundary,
# excluded from the resistance metric here)
CATCHABLE = ["admit", "flooding_spread", "causality_laundering",
             "lying_transformation", "collusion"]


def main() -> None:
    print("=" * 70)
    print("E7.1  Utility-resistance frontier (sweep accept floor x boundary penalty)")
    print("=" * 70)
    print(f"\n{'min_accept':>11s} {'unverif_pen':>12s} {'ASR':>7s} {'utility':>8s}")
    print("-" * 46)
    points = []
    for floor in (WarrantLevel.WEAK, WarrantLevel.DERIVED,
                  WarrantLevel.MODERATE, WarrantLevel.STRONG):
        for pen in (0, 1):
            dw = WarrantLevel(max(0, int(floor) - 1))
            pol = EvaluatorPolicy(min_accept=floor, min_down_weight=dw,
                                  unverified_boundary_penalty=pen)
            m = run_matrix(adversaries=CATCHABLE, hops=(2, 3, 4, 5), policy=pol)
            rs = m.rows["capm"]
            a, u = asr(rs), utility(rs)
            points.append((floor.name, pen, a, u))
            print(f"{floor.name:>11s} {pen:>12d} {a:>7.2f} {u:>8.2f}")

    # crude Pareto front: keep points not dominated (lower ASR & higher utility)
    front = []
    for fl, pen, a, u in points:
        dominated = any((a2 <= a and u2 >= u and (a2 < a or u2 > u))
                        for _, _, a2, u2 in points)
        if not dominated:
            front.append((fl, pen, a, u))
    print("\nPareto-optimal operating points (ASR, utility):")
    for fl, pen, a, u in front:
        print(f"   min_accept={fl:9s} unverif_pen={pen} -> ASR={a:.2f}, utility={u:.2f}")
    print("\nThis sweep is Figure 1; pick an operating point per deployment risk budget.")


if __name__ == "__main__":
    main()
