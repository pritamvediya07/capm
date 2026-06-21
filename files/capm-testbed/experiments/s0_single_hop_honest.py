"""Experiment S0 - single cross-org hop, honest path.

Claim under test: provenance survives one cross-org hop with verifiable
preservation, and the honest high-warrant value is accepted.

Run:  python -m experiments.s0_single_hop_honest
"""

from __future__ import annotations

from capm.benchmark.runner import run_trial
from capm.core.types import SourceClass


def main() -> None:
    print("=" * 70)
    print("S0  Single-hop, honest path  (provenance survival + utility)")
    print("=" * 70)
    for defense in ["no_defense", "identity_only", "flat_provenance",
                    "camel_single_runtime", "capm"]:
        r = run_trial(defense, n_hops=2, attack=None)
        print(f"  {defense:24s} decision={r.decision:11s} "
              f"warrant={r.warrant} sig_ok={r.signature_ok} "
              f"prov_reconstructed={r.provenance_reconstructed} "
              f"latency={r.latency_ms:.3f}ms")
    print("\nExpected: CAPM ACCEPTs honest STRONG-origin content and "
          "reconstructs the full chain; signature verifies.")


if __name__ == "__main__":
    main()
