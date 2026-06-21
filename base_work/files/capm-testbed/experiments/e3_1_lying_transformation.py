"""E3.1 - lying-transformation adversary.

A malicious *relay* regenerates content (a GENERATION) but stamps the segment
VERBATIM to dodge the fidelity penalty. CAPM's content-hash check (a verbatim
claim must reproduce its predecessor's bytes) detects the lie and scores the
segment as a GENERATION, collapsing its warrant.

DV: ASR vs. detection rate of the lie.

Run:  python -m experiments.e3_1_lying_transformation
"""

from __future__ import annotations

from attacks.adaptive.profiles import (inflated_warrant_origin,
                                        lying_transformation_origin)
from capm.benchmark.runner import run_trial
from capm.core.types import SourceClass, WarrantLevel
from capm.warrant.evaluator import EvaluatorPolicy

_ORIGIN = "The board meeting minutes are published on the corporate site."
_FORGED = "Per analysis, the merger is certain to close and the stock will double."


def main() -> None:
    print("=" * 70)
    print("E3.1  Lying-transformation adversary (declare VERBATIM, actually GENERATE)")
    print("=" * 70)

    origin = inflated_warrant_origin(_ORIGIN, true_class=SourceClass.PUBLIC_WEBPAGE,
                                     asserted=WarrantLevel.MODERATE, label="lt_origin")
    relay = lying_transformation_origin(_FORGED)

    print("\nWith CAPM transformation-lie detection ON (default):")
    detected = 0
    for n in (2, 3, 4):
        r = run_trial("capm", n_hops=n, adversary=origin, relay_adversaries={0: relay})
        detected += int(r.lie_detected)
        print(f"   hops={n} decision={r.decision:11s} warrant={r.warrant} "
              f"lie_present={r.transformation_lie} lie_detected={r.lie_detected} "
              f"-> {'CONTAINED' if not r.attack_succeeded else 'LEAKED'}")
    print(f"   detection rate: {detected}/3")

    print("\nAblation: transformation-lie detection OFF (E8 companion):")
    pol = EvaluatorPolicy(detect_transformation_lies=False)
    for n in (2, 3, 4):
        r = run_trial("capm", n_hops=n, adversary=origin,
                      relay_adversaries={0: relay}, policy=pol)
        print(f"   hops={n} decision={r.decision:11s} warrant={r.warrant} "
              f"lie_detected={r.lie_detected} "
              f"-> {'CONTAINED' if not r.attack_succeeded else 'LEAKED (lie paid off)'}")

    print("\nExpected: with detection ON the lie is caught and warrant collapses;")
    print("with it OFF the relay's false VERBATIM claim preserves warrant it did not earn.")


if __name__ == "__main__":
    main()
