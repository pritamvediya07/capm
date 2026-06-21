"""E6.1 — verification overhead & manifest size vs. chain length (SAGA Monitor).

Measures per-hop verification latency, signature count, and serialized manifest
size as functions of N hops, timed on **SAGA's own `Monitor`**
(`saga.common.overhead.Monitor`) when available, so the numbers are directly
comparable to SAGA's published negligible-overhead result. The headline: per-hop
verification stays **sub-millisecond** and the manifest grows **linearly** in N
(compaction, E6.3, bounds the wire form).

Run:  python3 -m experiments.e6_1_overhead_scaling
      PYTHONPATH=vendor/saga CAPM_USE_SAGA=1 python3 -m experiments.e6_1_overhead_scaling
"""

from __future__ import annotations

import csv
import os

from capm.adapters import saga_bridge
from capm.benchmark.scenarios import build_chain
from capm.warrant.evaluator import WarrantEvaluator

OUT_DIR = os.path.join("results", "p2", "e6_1")
HOPS = (1, 2, 3, 5, 8, 12, 16, 24, 32, 48)
REPS = 100


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    mon = saga_bridge.get_monitor()
    on_saga = saga_bridge.use_saga()

    print("=" * 78)
    print("E6.1  Verification overhead & manifest size vs. chain length")
    print("=" * 78)
    print(f"monitor: {type(mon).__module__}  (SAGA active: {on_saga})  reps/point: {REPS}\n")
    print(f"  {'hops':>5s} {'segments':>9s} {'signatures':>11s} {'verify(ms)':>11s} "
          f"{'us/hop':>8s} {'manifest(B)':>12s} {'B/hop':>7s}")
    print("  " + "-" * 70)

    rows = []
    for n in HOPS:
        sc = build_chain(n_hops=n)
        msg = sc.query("value?")
        ev = WarrantEvaluator(sc.registry)
        if hasattr(mon, "reset"):
            mon.reset("verify")
        mon.start("verify")
        for _ in range(REPS):
            ev.evaluate(msg.manifest, msg.content)
        mon.stop("verify")
        per_ms = mon.elapsed("verify") * 1000.0 / REPS
        size = len(msg.manifest.to_json())
        segs = len(msg.manifest.segments)
        rows.append(dict(hops=n, segments=segs, signatures=segs,
                         verify_ms=round(per_ms, 4), us_per_hop=round(per_ms * 1000 / n, 2),
                         manifest_bytes=size, bytes_per_hop=round(size / n, 1)))
        print(f"  {n:>5d} {segs:>9d} {segs:>11d} {per_ms:>11.4f} "
              f"{rows[-1]['us_per_hop']:>8.2f} {size:>12d} {rows[-1]['bytes_per_hop']:>7.1f}")

    max_us_hop = max(r["us_per_hop"] for r in rows)
    print(f"\nPer-hop verification ≤ {max_us_hop:.0f} µs (sub-millisecond) across N; "
          f"manifest grows linearly (~{rows[-1]['bytes_per_hop']:.0f} B/hop, one "
          f"signature/hop). A single LLM call is ~10^5–10^6 µs, so CAPM verification "
          f"is negligible relative to model cost. Compaction (E6.3) bounds the wire form.")

    csv_path = os.path.join(OUT_DIR, "overhead.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    fig_path = _make_figure(rows, on_saga)

    print(f"\nCSV: {csv_path}")
    if fig_path:
        print(f"Fig: {fig_path}")
    print("=" * 78)
    # PASS: sub-ms per hop, linear manifest (≈constant bytes/hop)
    bph = [r["bytes_per_hop"] for r in rows if r["hops"] >= 8]
    linear = (max(bph) - min(bph)) / (sum(bph) / len(bph)) < 0.15
    ok = max_us_hop < 1000.0 and linear
    print("PASS" if ok else "FAIL")
    return 0 if ok else 2


def _make_figure(rows, on_saga) -> str:
    try:
        from experiments import figtools as ft
    except Exception as e:
        print(f"(figure skipped: {e})")
        return ""
    hops = [r["hops"] for r in rows]
    fig, ax1 = ft.new(figsize=(7.8, 4.6))
    # total verify latency (ms) on the left axis
    ax1.plot(hops, [r["verify_ms"] for r in rows], "-o", color=ft.ACCENT, lw=2.2,
             label="verify latency (ms, total)")
    ft._style(ax1, f"E6.1 — overhead vs chain length "
              f"({'SAGA Monitor' if on_saga else 'local monitor'})",
              xlabel="chain length (hops)", ylabel="verification latency (ms)")
    ax1.tick_params(axis="y", labelcolor=ft.ACCENT)
    # manifest size (KiB) on the right axis
    ax2 = ax1.twinx()
    ax2.plot(hops, [r["manifest_bytes"] / 1024 for r in rows], "-s", color=ft.WARN,
             lw=2.0, label="manifest size (KiB)")
    ax2.set_ylabel("manifest size (KiB)", color=ft.WARN, fontsize=10)
    ax2.tick_params(axis="y", labelcolor=ft.WARN)
    # per-hop annotation
    mx = max(r["us_per_hop"] for r in rows)
    ax1.text(0.02, 0.92, f"per-hop ≤ {mx:.0f} µs (sub-ms) · 1 signature/hop · both linear",
             transform=ax1.transAxes, fontsize=8.5, color="#444")
    l1, lab1 = ax1.get_legend_handles_labels()
    l2, lab2 = ax2.get_legend_handles_labels()
    ax1.legend(l1 + l2, lab1 + lab2, fontsize=8, frameon=False, loc="upper center")
    return ft.save(fig, "e6_1_overhead_scaling.png")


if __name__ == "__main__":
    raise SystemExit(main())
