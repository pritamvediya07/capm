"""E6.2 - verification throughput / concurrency.

Measures aggregate verification throughput (verifications/sec) to support the
honest framing: CAPM's per-verify cost is negligible relative to LLM inference
latency. Runs sequentially here (deterministic); a real deployment would thread
this, but the per-verify cost is the quantity that matters.

Run:  python -m experiments.e6_2_throughput
"""

from __future__ import annotations

import time

from capm.benchmark.scenarios import build_chain
from capm.warrant.evaluator import WarrantEvaluator


def main() -> None:
    print("=" * 60)
    print("E6.2  Verification throughput")
    print("=" * 60)
    for n in (3, 5, 8):
        sc = build_chain(n_hops=n, attack=None)
        msg = sc.query("v?")
        ev = WarrantEvaluator(sc.registry)
        N = 5000
        t0 = time.perf_counter()
        for _ in range(N):
            ev.evaluate(msg.manifest, msg.content)
        dt = time.perf_counter() - t0
        print(f"   hops={n:>2d}: {N/dt:>10.0f} verifications/sec "
              f"({dt/N*1e6:.1f} us each)")
    print("\nA single LLM call is ~10^5-10^6 us; CAPM verification is ~10^2 us,")
    print("so verification cost << model cost. Thread for real concurrency numbers.")


if __name__ == "__main__":
    main()
