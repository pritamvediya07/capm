"""Master runner - produces the full comparison table across all metrics.

Run:  python -m experiments.run_all          # console table
      python -m experiments.run_all --json results.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json

from attacks.injectors import ALL_ATTACKS
from capm.benchmark.runner import (asr, down_weight_rate, mean_latency,
                                   provenance_survival, run_trial, utility)

DEFENSES = ["no_defense", "identity_only", "flat_provenance",
            "camel_single_runtime", "capm"]


def collect():
    rows = {}
    for d in DEFENSES:
        results = []
        # honest trials across hop counts (utility + survival + latency)
        for n in (2, 3, 4, 5):
            results.append(run_trial(d, n_hops=n, attack=None))
        # adversarial trials across all attacks
        for AttackCls in ALL_ATTACKS:
            results.append(run_trial(d, n_hops=3, attack=AttackCls().make_source))
        rows[d] = results
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=str, default=None)
    args = ap.parse_args()

    rows = collect()

    print("=" * 92)
    print("CAPM testbed - full results")
    print("=" * 92)
    hdr = (f"{'defense':24s} {'ASR':>7s} {'down-wt':>8s} {'utility':>8s} "
           f"{'prov-surv':>10s} {'lat(ms)':>9s}")
    print(hdr)
    print("-" * 92)
    out = {}
    for d in DEFENSES:
        rs = rows[d]
        metrics = dict(asr=asr(rs), down_weight=down_weight_rate(rs),
                       utility=utility(rs), provenance_survival=provenance_survival(rs),
                       mean_latency_ms=mean_latency(rs))
        out[d] = metrics
        print(f"{d:24s} {metrics['asr']:>7.2f} {metrics['down_weight']:>8.2f} "
              f"{metrics['utility']:>8.2f} {metrics['provenance_survival']:>10.2f} "
              f"{metrics['mean_latency_ms']:>9.3f}")
    print("-" * 92)
    print("Reading: CAPM should show ASR=0.00, high down-weight & utility, "
          "provenance_survival=1.00, sub-ms latency. Baselines should leak "
          "(high ASR) or fail to reconstruct provenance.")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\nWrote {args.json}")


if __name__ == "__main__":
    main()
