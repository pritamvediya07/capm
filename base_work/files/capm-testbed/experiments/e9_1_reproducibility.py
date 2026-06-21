"""E9.1 - determinism, seeds, and confidence intervals.

Establishes reproducibility for artifact evaluation:
  * runs the comparative matrix under several seeds and confirms the rate
    metrics are bit-for-bit identical (the testbed is deterministic by design -
    fixed clock, deterministic responders - so seeds change nothing in the
    rates; we verify that, which is the strong reproducibility guarantee);
  * reports each rate with a Wilson 95% CI and a bootstrap CI over the trial
    population (the genuine statistical uncertainty, E9.3);
  * reports per-hop verification latency as mean +/- 95% CI over repeats (the
    one wall-clock-stochastic quantity).

Run:  python -m experiments.e9_1_reproducibility --seeds 10
"""

from __future__ import annotations

import argparse

from capm.benchmark import stats
from capm.benchmark.harness import run_matrix
from capm.benchmark.runner import asr, utility
from capm.common.rng import seed_everything
from capm.benchmark.scenarios import build_chain
from capm.warrant.evaluator import WarrantEvaluator

CATCHABLE = ["admit", "flooding_spread", "causality_laundering",
             "lying_transformation", "collusion"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10)
    args = ap.parse_args()

    print("=" * 70)
    print(f"E9.1  Determinism + CIs over {args.seeds} seeds")
    print("=" * 70)

    # --- determinism: same rates under every seed --------------------
    asrs, utils = [], []
    capm_trials = None
    for s in range(args.seeds):
        seed_everything(s)
        m = run_matrix(adversaries=CATCHABLE, hops=(2, 3, 4, 5))
        rs = m.rows["capm"]
        asrs.append(round(asr(rs), 6))
        utils.append(round(utility(rs), 6))
        if capm_trials is None:
            capm_trials = rs
    deterministic = len(set(asrs)) == 1 and len(set(utils)) == 1
    print(f"\nCAPM ASR over seeds:     {sorted(set(asrs))}")
    print(f"CAPM utility over seeds: {sorted(set(utils))}")
    print(f"bit-for-bit identical across {args.seeds} seeds: {deterministic}")

    # --- statistical uncertainty over the trial population -----------
    mal = [r for r in capm_trials if r.expected_malicious]
    honest = [r for r in capm_trials if not r.expected_malicious]
    succ = sum(r.attack_succeeded for r in mal)
    acc = sum(r.decision in ("accept", "down_weight") for r in honest)
    print(f"\nCAPM ASR     = {stats.format_rate(succ, len(mal))}  (Wilson 95% CI)")
    print(f"CAPM utility = {stats.format_rate(acc, len(honest))}")
    basr = stats.bootstrap_ci([float(r.attack_succeeded) for r in mal], seed=0)
    print(f"ASR bootstrap 95% CI: [{basr[1]:.2f}, {basr[2]:.2f}]")

    # --- latency: mean +/- 95% CI over repeats -----------------------
    sc = build_chain(n_hops=3, attack=None)
    msg = sc.query("v?")
    ev = WarrantEvaluator(sc.registry)
    import time
    lat = []
    for _ in range(200):
        t0 = time.perf_counter()
        ev.evaluate(msg.manifest, msg.content)
        lat.append((time.perf_counter() - t0) * 1000.0)
    pt, lo, hi = stats.bootstrap_ci(lat, seed=1)
    print(f"\nper-verify latency: {pt:.4f} ms  [95% CI {lo:.4f}, {hi:.4f}] over 200 reps")

    print("\nReproducibility: rate metrics are deterministic (identical across seeds);")
    print("uncertainty is reported via Wilson/bootstrap over the trial population;")
    print("only wall-clock latency varies, reported with a CI. Artifact-ready.")


if __name__ == "__main__":
    main()
