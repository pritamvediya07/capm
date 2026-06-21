"""E8.x - ablations: remove one CAPM component at a time.

Each ablation disables a single evaluator mechanism and re-runs the catchable
adversaries + honest workload. The table shows ASR rising (or soundness
degrading) when a necessary component is removed, vs. the full defense.

  E8.1 origin-warrant ceiling     -> laundering succeeds
  E8.2 per-transformation penalty -> warrant stops eroding
  E8.3 signature verification     -> forgery succeeds
  E8.4 soft-binding               -> off-manifest edits undetected
  E8.5 cross-org awareness        -> collapses toward CaMeL baseline

Run:  python -m experiments.e8_ablations
"""

from __future__ import annotations

from capm.benchmark.harness import run_matrix
from capm.benchmark.runner import asr, utility
from capm.warrant.evaluator import EvaluatorPolicy

CATCHABLE = ["admit", "flooding_spread", "causality_laundering",
             "lying_transformation", "manifest_forgery_fake_sig", "collusion"]

ABLATIONS = {
    "full CAPM (none removed)":      EvaluatorPolicy(),
    "E8.1 -origin ceiling":          EvaluatorPolicy(enforce_origin_ceiling=False),
    "E8.2 -transformation penalty":  EvaluatorPolicy(apply_transformation_penalty=False),
    "E8.3 -signature verification":  EvaluatorPolicy(require_signatures=False),
    "E8.4 -soft-binding":            EvaluatorPolicy(enable_soft_binding_check=False,
                                                     require_soft_binding=True),
    "E8.5 -cross-org awareness":     EvaluatorPolicy(cross_org_aware=False),
    "E8.1+E8.2 (ceiling+penalty)":   EvaluatorPolicy(enforce_origin_ceiling=False,
                                                     apply_transformation_penalty=False),
}


def main() -> None:
    print("=" * 70)
    print("E8.x  Ablations: each removes one component to show it is necessary")
    print("=" * 70)
    print(f"\n{'configuration':32s} {'ASR':>7s} {'utility':>8s}  effect")
    print("-" * 70)
    base = None
    for name, pol in ABLATIONS.items():
        m = run_matrix(adversaries=CATCHABLE, hops=(2, 3, 4, 5), policy=pol)
        rs = m.rows["capm"]
        a, u = asr(rs), utility(rs)
        if base is None:
            base = (a, u)
        effect = ""
        if name.startswith("E8") and a > base[0]:
            effect = f"ASR up vs full (+{a - base[0]:.2f}) -> component necessary"
        elif name.startswith("E8") and u > base[1]:
            effect = f"utility up (+{u - base[1]:.2f}) but soundness traded away"
        print(f"{name:32s} {a:>7.2f} {u:>8.2f}  {effect}")

    print("\nReading: every ablation that raises ASR (or trades soundness for")
    print("utility) demonstrates the removed component is load-bearing. The full")
    print("CAPM row is the reference; this table feeds Table 2 of the paper.")


if __name__ == "__main__":
    main()
