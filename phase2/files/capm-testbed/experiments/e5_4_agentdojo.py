"""E5.4 — cross-org benchmark on REAL AgentDojo tasks (the priority-#1 substrate).

AgentDojo (Debenedetti et al.) is the standard prompt-injection agent benchmark.
Its injection *vectors* are exactly places where content from an external org — a
biller's invoice text, a memo on an incoming transaction, an address-change
notice — flows into the user's agent. That is the cross-organisational boundary
the design doc targets.

This experiment uses the reusable cross-org benchmark in
``capm.benchmark.agentdojo_crossorg`` to:

1. load a real AgentDojo suite and make its org boundaries **explicit** (every
   injection vector → the external org that owns it + its source class);
2. run the suite's **real attacker goals** across those boundaries through the
   native CAPM evaluator; and
3. score containment under every defense, plus a negative control (origin
   capture) and a first-party utility check.

Headline: CAPM contains every real AgentDojo injection (ASR 0) where all four
baselines accept it (Plane-1 cannot see the Plane-2 boundary). The control shows
the harness *can* represent a successful attack (origin capture accepts at ASR 1,
still attributable), so the 0.00 is a real result, not a harness artifact.

Run with the venv python (agentdojo lives there):
    .venv/bin/python -m experiments.e5_4_agentdojo
"""

from __future__ import annotations

import csv
import os

from capm.benchmark.agentdojo_crossorg import (AGENTDOJO_AVAILABLE,
                                               run_benchmark, status)

OUT_DIR = os.path.join("results", "p2", "e5_4")
HOPS = (2, 3, 4)
CONTROL_HOPS = 2
SUITE = "banking"


def _print_boundary_table(res) -> None:
    print("\nExplicit organisational boundaries (real AgentDojo injection vectors):")
    print(f"  {'injection vector':34s} {'external org':22s} {'source class':16s} {'ceiling':9s}")
    print("  " + "-" * 84)
    for row in res.boundary_table:
        print(f"  {row['vector']:34s} {row['external_org']:22s} "
              f"{row['source_class']:16s} {row['warrant_ceiling']:9s}")


def _print_matrix(res) -> None:
    print(f"\nInjection containment — {res.n_injection_tasks} real attacker goals "
          f"× hops {HOPS} (relay attack, Goal-1):")
    print(f"  {'defense':22s} {'ASR':>7s} {'95% CI':>16s}  {'by hop (2/3/4)':>16s}")
    print("  " + "-" * 70)
    for d in res.defenses:
        lo, hi = res.asr_ci("injection", d)
        byhop = "/".join(f"{res.asr('injection', d, n):.2f}" for n in HOPS)
        print(f"  {d:22s} {res.asr('injection', d):>7.3f} "
              f"   [{lo:.3f},{hi:.3f}]  {byhop:>16s}")

    print(f"\nNegative control — origin capture (Goal-2 residual, {CONTROL_HOPS} hops):")
    print(f"  {'defense':22s} {'ASR':>7s}   note")
    print("  " + "-" * 70)
    for d in res.defenses:
        note = ""
        if d == "capm":
            note = (f"residual fires; attribution preserved "
                    f"({res.attribution_rate('capm')*100:.0f}% of captures attributed)")
        print(f"  {d:22s} {res.asr('capture', d, CONTROL_HOPS):>7.3f}   {note}")

    print(f"\nUtility — legitimate first-party data ({CONTROL_HOPS} hops, honest workload):")
    print(f"  {'defense':22s} {'utility':>8s}   (fraction of trustworthy content still used)")
    print("  " + "-" * 70)
    for d in res.defenses:
        print(f"  {d:22s} {res.utility(d, CONTROL_HOPS):>8.3f}")


def _print_significance(res) -> None:
    print("\nPaired significance (McNemar, CAPM vs each baseline, injection trials):")
    for b in ("no_defense", "identity_only", "flat_provenance", "camel_single_runtime"):
        m = res.mcnemar_vs(b, "injection")
        print(f"  CAPM vs {b:22s} p={m['p_value']:.2e}  "
              f"discordant={m['n_discordant']} (all favour {m['favours']})")


def _write_csv(res) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "agentdojo_crossorg.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(res.rows[0].as_dict().keys()))
        w.writeheader()
        for r in res.rows:
            w.writerow(r.as_dict())
    # a compact summary CSV the report/figure reads
    spath = os.path.join(OUT_DIR, "summary.csv")
    with open(spath, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["defense", "injection_asr", "injection_ci_lo", "injection_ci_hi",
                    "capture_asr", "utility"])
        for d in res.defenses:
            lo, hi = res.asr_ci("injection", d)
            w.writerow([d, f"{res.asr('injection', d):.4f}", f"{lo:.4f}", f"{hi:.4f}",
                        f"{res.asr('capture', d, CONTROL_HOPS):.4f}",
                        f"{res.utility(d, CONTROL_HOPS):.4f}"])
    return path


def _make_figure(res) -> str:
    """Grouped bars: injection ASR vs capture-control ASR per defense (+utility)."""
    try:
        from experiments import figtools as ft
    except Exception as e:                          # pragma: no cover
        print(f"(figure skipped: {e})")
        return ""
    import numpy as np

    defs = res.defenses
    labels = [d.replace("_", "\n") for d in defs]
    inj = [res.asr("injection", d) for d in defs]
    cap = [res.asr("capture", d, CONTROL_HOPS) for d in defs]
    x = np.arange(len(defs))
    w = 0.38

    fig, ax = ft.new(figsize=(8.2, 4.6))
    b1 = ax.bar(x - w / 2, inj, w, label="injection (relay attack, Goal-1)",
                color=ft.BASE, edgecolor="white")
    # CAPM's injection bar in the accent colour to mark the defense
    b1[defs.index("capm")].set_color(ft.OK)
    ax.bar(x + w / 2, cap, w, label="origin capture (residual, Goal-2)",
           color=ft.WARN, edgecolor="white", alpha=0.85)
    ft._style(ax, f"E5.4 — cross-org containment on real AgentDojo ({SUITE})",
              xlabel="", ylabel="attack success rate (ASR)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylim(0, 1.12)
    ax.legend(fontsize=8, loc="upper center", ncol=2, frameon=False)
    for xi, v in zip(x - w / 2, inj):
        ax.text(xi, v + 0.03, f"{v:.2f}", ha="center", fontsize=7.5)
    for xi, v in zip(x + w / 2, cap):
        ax.text(xi, v + 0.03, f"{v:.2f}", ha="center", fontsize=7.5)
    ax.annotate("CAPM contains every real\ninjection (ASR 0); the residual\n"
                "(origin capture) still fires",
                xy=(x[defs.index("capm")] - w / 2, 0.02), xytext=(2.3, 0.55),
                fontsize=7.5, color=ft.ACCENT,
                arrowprops=dict(arrowstyle="->", color=ft.ACCENT, lw=1))
    return ft.save(fig, "e5_4_agentdojo_crossorg.png")


def main() -> int:
    print("=" * 88)
    print("E5.4  Cross-org benchmark on REAL AgentDojo injection tasks")
    print("=" * 88)
    print(status())
    if not AGENTDOJO_AVAILABLE:
        print("\nagentdojo not importable in this interpreter.")
        print("run with the venv:  .venv/bin/python -m experiments.e5_4_agentdojo")
        return 1

    res = run_benchmark(SUITE, hops=HOPS, control_hops=CONTROL_HOPS)
    print(f"\nloaded real AgentDojo '{SUITE}' suite: {res.n_injection_tasks} injection "
          f"tasks, {len(res.boundary_table)} cross-org injection vectors")

    _print_boundary_table(res)
    _print_matrix(res)
    _print_significance(res)

    csv_path = _write_csv(res)
    fig_path = _make_figure(res)

    capm_inj = res.asr("injection", "capm")
    capm_cap = res.asr("capture", "capm", CONTROL_HOPS)
    n_contained = sum(1 for r in res.rows
                      if r.mode == "injection" and r.defense == "capm"
                      and not r.attack_succeeded)
    n_inj_rows = sum(1 for r in res.rows
                     if r.mode == "injection" and r.defense == "capm")
    print("\n" + "=" * 88)
    print(f"RESULT: CAPM contains {n_contained}/{n_inj_rows} real AgentDojo injection "
          f"trials across hops {HOPS} (ASR {capm_inj:.2f}); all four baselines accept "
          f"them (ASR 1.00).")
    print(f"Control: origin capture accepts at ASR {capm_cap:.2f} under CAPM "
          f"(the Goal-2 residual) — but stays 100% attributable. The harness can "
          f"represent success, so the injection 0.00 is real, not by construction.")
    print(f"CSV : {csv_path}")
    if fig_path:
        print(f"Fig : {fig_path}")
    print("=" * 88)
    # explicit PASS/FAIL gate
    ok = (capm_inj == 0.0
          and all(res.asr("injection", b) == 1.0 for b in res.defenses if b != "capm")
          and capm_cap > 0.0
          and res.attribution_rate("capm") == 1.0)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
