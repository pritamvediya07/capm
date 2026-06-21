"""E6.1 - verification overhead & manifest size vs. chain length.

Measures per-hop verification latency and serialized manifest size as functions
of N hops, on SAGA's own Monitor when available (CAPM_USE_SAGA=1) so the numbers
are directly comparable to SAGA's published negligible-overhead result.

Run:  python -m experiments.e6_1_overhead_scaling
      PYTHONPATH=vendor/saga CAPM_USE_SAGA=1 python -m experiments.e6_1_overhead_scaling
"""

from __future__ import annotations

from capm.adapters import saga_bridge
from capm.benchmark.scenarios import build_chain
from capm.warrant.evaluator import WarrantEvaluator


def main() -> None:
    print("=" * 68)
    print("E6.1  Overhead & manifest size vs. chain length")
    print("=" * 68)
    mon = saga_bridge.get_monitor()
    backend = type(mon).__module__
    print(f"monitor: {backend}  (SAGA active: {saga_bridge.use_saga()})\n")

    print(f"   {'hops':>5s} {'segments':>9s} {'verify(ms)':>11s} {'manifest(bytes)':>16s} {'us/hop':>8s}")
    for n in (1, 2, 3, 5, 8, 12, 16, 24, 32):
        sc = build_chain(n_hops=n, attack=None)
        msg = sc.query("value?")
        ev = WarrantEvaluator(sc.registry)
        # average a few verifications for a stable latency number
        reps = 50
        mon.reset("verify") if hasattr(mon, "reset") else None
        mon.start("verify")
        for _ in range(reps):
            ev.evaluate(msg.manifest, msg.content)
        mon.stop("verify")
        total_ms = mon.elapsed("verify") * 1000.0
        per_ms = total_ms / reps
        size = len(msg.manifest.to_json())
        print(f"   {n:>5d} {len(msg.manifest.segments):>9d} {per_ms:>11.4f} "
              f"{size:>16d} {1000 * per_ms / n:>8.2f}")

    print("\nExpected: per-hop verification stays sub-millisecond and manifest size")
    print("grows ~linearly in hops. Feeds Table 3; compaction is E6.3.")


if __name__ == "__main__":
    main()
