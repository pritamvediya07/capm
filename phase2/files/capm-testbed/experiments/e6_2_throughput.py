"""E6.2 — verification throughput under concurrency.

Verification is independent per manifest and CPU-bound (Ed25519 + hashing), so it
parallelises across cores. We measure aggregate throughput (verifications/sec) as
the number of worker **processes** grows (threads would be GIL-bound on the crypto),
to support the honest deployability claim: CAPM's per-verify cost is negligible
relative to LLM inference, and it scales out near-linearly with cores.

Run:  python3 -m experiments.e6_2_throughput
"""

from __future__ import annotations

import csv
import os
import time
from concurrent.futures import ProcessPoolExecutor

from capm.benchmark.scenarios import build_chain
from capm.warrant.evaluator import WarrantEvaluator

OUT_DIR = os.path.join("results", "p2", "e6_2")
HOPS = 5
REPS_PER_WORKER = 20000


def _worker(args) -> int:
    """Build one chain, then verify it REPS times (build cost amortised away)."""
    n_hops, reps = args
    sc = build_chain(n_hops=n_hops)
    msg = sc.query("v?")
    ev = WarrantEvaluator(sc.registry)
    for _ in range(reps):
        ev.evaluate(msg.manifest, msg.content)
    return reps


def _single_thread_rate() -> float:
    sc = build_chain(n_hops=HOPS)
    msg = sc.query("v?")
    ev = WarrantEvaluator(sc.registry)
    n = 20000
    t0 = time.perf_counter()
    for _ in range(n):
        ev.evaluate(msg.manifest, msg.content)
    return n / (time.perf_counter() - t0)


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    cores = os.cpu_count() or 1
    print("=" * 72)
    print("E6.2  Verification throughput under concurrency")
    print("=" * 72)
    base = _single_thread_rate()
    print(f"chain length {HOPS} hops · {cores} cores available\n")
    print(f"single-thread baseline: {base:,.0f} verifications/sec "
          f"({1e6 / base:.1f} µs each)\n")
    print(f"  {'workers':>8s} {'agg verif/sec':>15s} {'speedup':>9s} {'efficiency':>11s}")
    print("  " + "-" * 48)

    rows = []
    worker_counts = [w for w in (1, 2, 4, 8, 16, cores) if w <= cores]
    worker_counts = sorted(set(worker_counts))
    for w in worker_counts:
        with ProcessPoolExecutor(max_workers=w) as ex:
            t0 = time.perf_counter()
            total = sum(ex.map(_worker, [(HOPS, REPS_PER_WORKER)] * w))
            dt = time.perf_counter() - t0
        agg = total / dt
        speedup = agg / base
        rows.append(dict(workers=w, agg_verif_per_sec=round(agg), speedup=round(speedup, 2),
                         efficiency=round(speedup / w, 2)))
        print(f"  {w:>8d} {agg:>15,.0f} {speedup:>8.2f}x {speedup / w:>10.0%}")

    peak = max(r["agg_verif_per_sec"] for r in rows)
    print(f"\nPeak aggregate throughput: {peak:,.0f} verifications/sec across "
          f"{rows[-1]['workers']} workers ({rows[-1]['speedup']:.1f}x single-thread). "
          f"A single LLM call is ~0.1–1 s (~1–10 verif/sec-equivalent), so CAPM "
          f"verification cost is negligible vs model inference and scales out with cores.")

    csv_path = os.path.join(OUT_DIR, "throughput.csv")
    with open(csv_path, "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wtr.writeheader(); wtr.writerows(rows)
    fig_path = _make_figure(rows, base)

    print(f"\nCSV: {csv_path}")
    if fig_path:
        print(f"Fig: {fig_path}")
    print("=" * 72)
    # PASS: throughput scales with workers (real parallelism) and absolute rate is high
    ok = (rows[-1]["agg_verif_per_sec"] > base * 1.5 and peak > 1000)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 2


def _make_figure(rows, base) -> str:
    try:
        from experiments import figtools as ft
    except Exception as e:
        print(f"(figure skipped: {e})")
        return ""
    workers = [r["workers"] for r in rows]
    agg = [r["agg_verif_per_sec"] for r in rows]
    fig, ax = ft.new(figsize=(7.6, 4.6))
    ax.plot(workers, agg, "-o", color=ft.ACCENT, lw=2.4, markersize=7,
            label="measured aggregate throughput")
    ax.plot(workers, [base * w for w in workers], "--", color=ft.BASE, lw=1.8,
            label="ideal linear scaling")
    ft._style(ax, "E6.2 — verification throughput scales with cores",
              xlabel="worker processes", ylabel="aggregate verifications / sec")
    ax.legend(fontsize=8.5, frameon=False, loc="upper left")
    ax.text(0.97, 0.05, "per-verify ≈ "
            f"{1e6 / base:.0f} µs · ≪ one LLM call (~10^5–10^6 µs)",
            transform=ax.transAxes, fontsize=8, color="#444", ha="right")
    return ft.save(fig, "e6_2_throughput.png")


if __name__ == "__main__":
    raise SystemExit(main())
