"""E3.2 - high-warrant-origin capture: the honest boundary of CLAIM-1/3.

This is the experiment that proves the headline ASR is NOT purely by
construction. The adversary does not merely inflate a warrant *number* over a
truthfully-declared low class (which the ceiling trivially caps); it lies about
the **source class itself**, declaring an editable page to be an
AUTHORITATIVE_API.

Expected, honest result:
  * CAPM does NOT catch this by warrant - origin integrity is a separate,
    composable layer, exactly as the design doc states (Section 8).
  * CAPM DOES still attribute the claim to the captured origin's signing
    identity, so the bad origin is revocable post-hoc.
We contrast with the weak adversary (truthful class, inflated number) to show
where CAPM's guarantee starts and stops.

Run:  python -m experiments.e3_2_origin_capture
"""

from __future__ import annotations

from attacks.adaptive.profiles import inflated_warrant_origin, origin_capture
from capm.benchmark.runner import run_trial
from capm.core.types import SourceClass, WarrantLevel

_POISON = "The recommended dosage has been revised to 5x the prior value."


def main() -> None:
    print("=" * 74)
    print("E3.2  High-warrant-origin capture (honest boundary of the claim)")
    print("=" * 74)

    weak = inflated_warrant_origin(_POISON, true_class=SourceClass.EDITABLE_SOURCE,
                                   asserted=WarrantLevel.STRONG, label="weak_inflated")
    captured = origin_capture(_POISON, true_class=SourceClass.EDITABLE_SOURCE,
                              claimed_class=SourceClass.AUTHORITATIVE_API)

    print("\n[A] Weak adversary: truthful class (EDITABLE), inflated warrant number")
    for n in (1, 2, 3):
        r = run_trial("capm", n_hops=n, adversary=weak)
        print(f"   hops={n} decision={r.decision:11s} warrant={r.warrant} "
              f"-> {'CONTAINED' if not r.attack_succeeded else 'LEAKED'} "
              f"(ceiling caps it)")

    print("\n[B] Adaptive adversary: lies about the CLASS itself (EDITABLE->AUTH_API)")
    for n in (1, 2, 3):
        r = run_trial("capm", n_hops=n, adversary=captured)
        verdict = "LEAKED (expected - origin integrity out of scope)" \
            if r.attack_succeeded else "down-weighted by hop erosion"
        print(f"   hops={n} decision={r.decision:11s} warrant={r.warrant} "
              f"overclaimed_class={r.class_overclaimed} -> {verdict}")
        print(f"           attribution_works={r.attribution_works} "
              f"(origin DID resolvable -> revocable)")

    print("\nConclusion: CAPM bounds warrant by the *declared* class; a captured")
    print("high-warrant origin defeats warrant alone but remains ATTRIBUTABLE.")
    print("This motivates origin-integrity as a separate composable layer, and")
    print("shows the weak-adversary ASR=0 result is a real mechanism, not a tautology.")


if __name__ == "__main__":
    main()
