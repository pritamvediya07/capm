"""Experiment S2 - N-hop composition; the warrant-erosion curve.

Claims under test:
  * H1: CAPM reconstructs provenance across N cross-org hops where flat and
    identity-only baselines reconstruct zero structured chain.
  * H3: warrant measured at the receiver is monotonically non-increasing along
    honest chains and strictly lower when a low-warrant origin is present.
This produces the first measured warrant-erosion curve (down-payment on T2).

Run:  python -m experiments.s2_nhop_erosion
"""

from __future__ import annotations

from attacks.injectors import ADMITInjection
from capm.benchmark.runner import provenance_survival, run_trial


def main() -> None:
    print("=" * 70)
    print("S2  N-hop composition  (warrant-erosion curve)")
    print("=" * 70)

    print("\nHonest chain - warrant vs. hops (CAPM):")
    print(f"  {'hops':>5s} {'warrant':>8s} {'boundary_crossings':>20s} {'reconstructed':>14s}")
    honest_curve = []
    for n in range(1, 8):
        r = run_trial("capm", n_hops=n, attack=None)
        honest_curve.append((n, r.warrant))
        print(f"  {n:>5d} {r.warrant:>8d} {r.boundary_crossings:>20d} "
              f"{str(r.provenance_reconstructed):>14s}")

    # monotone check (H3)
    mono = all(honest_curve[i][1] >= honest_curve[i + 1][1]
               for i in range(len(honest_curve) - 1))
    print(f"\n  H3 monotone non-increasing: {mono}")

    print("\nAdversarial origin (ADMIT) - warrant vs. hops (CAPM):")
    for n in range(1, 8):
        r = run_trial("capm", n_hops=n, attack=ADMITInjection().make_source)
        print(f"  hops={n} warrant={r.warrant} decision={r.decision}")

    print("\nProvenance survival @ 5 hops:")
    for d in ["identity_only", "flat_provenance", "capm"]:
        rs = [run_trial(d, n_hops=5, attack=None) for _ in range(3)]
        print(f"  {d:20s} survival={provenance_survival(rs):.2f}")


if __name__ == "__main__":
    main()
