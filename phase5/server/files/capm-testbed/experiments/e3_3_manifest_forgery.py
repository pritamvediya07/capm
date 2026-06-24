"""E3.3 - manifest-forgery adversary battery.

A principal-facing relay tries to forge its segment's cryptographic binding
three ways. Every one must REJECT - forgery is infeasible without the private
key bound to a registered VC. This is where SAGA's Plane-1 guarantees are
load-bearing; run with ``CAPM_USE_SAGA=1`` to verify on SAGA's real crypto.

Run:  python -m experiments.e3_3_manifest_forgery
      PYTHONPATH=vendor/saga CAPM_USE_SAGA=1 python -m experiments.e3_3_manifest_forgery
"""

from __future__ import annotations

from attacks.adaptive.profiles import ForgeryMode, forgery_relay, honest_origin
from capm.benchmark.runner import run_trial
from capm.core.types import SourceClass


def main() -> None:
    print("=" * 66)
    print("E3.3  Manifest-forgery battery (all must REJECT)")
    print("=" * 66)

    origin = honest_origin("benign published figure", SourceClass.PUBLIC_WEBPAGE)
    all_rejected = True
    for mode in (ForgeryMode.FAKE_SIGNATURE, ForgeryMode.REPLAY_SEGMENT,
                 ForgeryMode.SUBSTITUTE_VC):
        r = run_trial("capm", n_hops=3, adversary=origin,
                      relay_adversaries={0: forgery_relay(mode)})
        ok = (r.decision == "reject")
        all_rejected &= ok
        print(f"   {mode.value:16s} decision={r.decision:8s} sig_ok={r.signature_ok} "
              f"-> {'REJECTED (correct)' if ok else 'NOT REJECTED (BUG)'}")

    print(f"\nAll forgeries rejected: {all_rejected}")
    print("Ties to E2.1: the ProVerif model should prove no verifying manifest")
    print("exists for a segment signed without the registered private key.")


if __name__ == "__main__":
    main()
