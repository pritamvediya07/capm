"""Experiment S1 - single cross-org hop, adversarial.

Claim under test (Hypothesis H2): against ADMIT / Flooding-Spread /
Causality-Laundering style injections, CAPM down-weights the low-warrant
content that the flat and identity-only baselines accept.

Run:  python -m experiments.s1_single_hop_adversarial
"""

from __future__ import annotations

from attacks.injectors import ALL_ATTACKS
from capm.benchmark.runner import (asr, down_weight_rate, run_trial, utility)


def main() -> None:
    print("=" * 70)
    print("S1  Single-hop, adversarial  (laundering ASR + down-weight rate)")
    print("=" * 70)
    defenses = ["no_defense", "identity_only", "flat_provenance",
                "camel_single_runtime", "capm"]

    per_defense = {d: [] for d in defenses}
    for AttackCls in ALL_ATTACKS:
        atk = AttackCls()
        print(f"\nAttack: {atk.name}")
        for d in defenses:
            r = run_trial(d, n_hops=2, attack=atk.make_source)
            per_defense[d].append(r)
            tag = "ATTACK SUCCEEDED" if r.attack_succeeded else "contained"
            print(f"  {d:24s} decision={r.decision:11s} warrant={r.warrant}  -> {tag}")

    print("\n" + "-" * 70)
    print(f"{'defense':24s} {'ASR':>8s} {'down-weight':>12s}")
    for d in defenses:
        print(f"{d:24s} {asr(per_defense[d]):>8.2f} {down_weight_rate(per_defense[d]):>12.2f}")
    print("\nExpected: CAPM ASR = 0.00 (all attacks down-weighted/quarantined); "
          "flat & identity-only ASR high.")


if __name__ == "__main__":
    main()
