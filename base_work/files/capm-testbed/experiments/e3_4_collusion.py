"""E3.4 - collusion / Sybil adversary.

Multiple malicious relays co-sign to try to launder a low-warrant origin. The
distinctive CAPM result: because warrant is bounded by the *origin* segment,
colluding relays cannot raise it - ASR is independent of the number of
colluders. We sweep #colluders at a fixed chain length and show warrant stays
flat at the origin ceiling.

Run:  python -m experiments.e3_4_collusion
"""

from __future__ import annotations

from capm.benchmark.harness import collusion_spec
from capm.benchmark.runner import run_trial


def main() -> None:
    print("=" * 64)
    print("E3.4  Collusion: warrant is origin-bounded, not relay-bounded")
    print("=" * 64)

    n_hops = 6
    print(f"\nChain length fixed at {n_hops}; vary number of colluding relays:")
    print(f"   {'#colluders':>11s} {'decision':>12s} {'warrant':>8s} {'ASR-leaked':>11s}")
    warrants = []
    for k in range(0, n_hops):
        spec = collusion_spec(k)
        r = run_trial("capm", n_hops=n_hops, adversary=spec.origin,
                      relay_adversaries=spec.relays)
        warrants.append(r.warrant)
        print(f"   {k:>11d} {r.decision:>12s} {r.warrant:>8d} "
              f"{str(r.attack_succeeded):>11s}")

    flat = len(set(warrants)) == 1
    print(f"\nWarrant constant across all collusion levels: {flat} (values={warrants})")
    print("Interpretation: colluding *relays* cannot inflate warrant; only the")
    print("origin's declared class sets the ceiling. This is the strong, distinctive")
    print("result the plan calls out - ASR does not climb with the number of colluders.")


if __name__ == "__main__":
    main()
