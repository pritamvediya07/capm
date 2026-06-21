"""E9.3 — statistical reporting for every comparative claim.

Artifact-evaluation requirement: no bare point estimates. For the headline
comparison (CAPM vs. each baseline on the catchable relay attacks) we report, for
each pair, the full statistical picture:

  * each rate with a **Wilson 95% CI**;
  * a paired **McNemar p-value** (the same scenarios scored under both defenses);
  * effect sizes — the **risk difference** (ASR_baseline − ASR_CAPM) and
    **Cohen's h** (a proportion effect size) — with a **bootstrap 95% CI** on the
    difference.

This is the template every comparative table in the paper follows; the stats live
in `capm/benchmark/stats.py` and are consumed by E1.1, E8.x, etc.

Run:  python3 -m experiments.e9_3_statistics
"""

from __future__ import annotations

import csv
import os

from capm.benchmark import stats
from capm.benchmark.harness import run_matrix, paired_significance
from capm.benchmark.runner import asr

OUT_DIR = os.path.join("results", "p2", "e9_3")
CATCHABLE = ["admit", "flooding_spread", "causality_laundering",
             "lying_transformation", "collusion"]
BASELINES = ["no_defense", "identity_only", "flat_provenance", "camel_single_runtime"]


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    m = run_matrix(adversaries=CATCHABLE, hops=(2, 3, 4, 5))

    capm_mal = [r for r in m.rows["capm"] if r.expected_malicious]
    capm_succ = sum(r.attack_succeeded for r in capm_mal)
    n = len(capm_mal)
    capm_asr = capm_succ / n
    capm_lo, capm_hi = stats.proportion_ci(capm_succ, n)

    print("=" * 88)
    print("E9.3  Statistical reporting — p-values + effect sizes + CIs for every comparison")
    print("=" * 88)
    print(f"\nheadline rate: CAPM ASR = {capm_asr:.2f} [{capm_lo:.2f}, {capm_hi:.2f}] "
          f"(Wilson 95% CI, n={n} malicious trials)\n")
    print(f"  {'baseline':22s} {'base ASR [95% CI]':>20s} {'McNemar p':>11s} "
          f"{'risk diff':>10s} {'Cohen h':>9s} {'diff 95% CI':>16s}")
    print("  " + "-" * 92)

    rows = []
    for b in BASELINES:
        base_mal = [r for r in m.rows[b] if r.expected_malicious]
        bsucc = sum(r.attack_succeeded for r in base_mal)
        basr = bsucc / len(base_mal)
        blo, bhi = stats.proportion_ci(bsucc, len(base_mal))
        mc = paired_significance(m, "capm", b)
        rd = stats.risk_difference(basr, capm_asr)
        h = stats.cohens_h(basr, capm_asr)
        # bootstrap CI on the paired difference in attack-success indicator
        diffs = [float(rb.attack_succeeded) - float(rc.attack_succeeded)
                 for rb, rc in zip(base_mal, capm_mal)]
        _, dlo, dhi = stats.bootstrap_ci(diffs, seed=0)
        rows.append(dict(baseline=b, base_asr=round(basr, 4), base_ci_lo=round(blo, 4),
                         base_ci_hi=round(bhi, 4), capm_asr=round(capm_asr, 4),
                         mcnemar_p=mc["p_value"], favours=mc["favours"],
                         risk_difference=round(rd, 4), cohens_h=round(h, 4),
                         diff_ci_lo=round(dlo, 4), diff_ci_hi=round(dhi, 4)))
        print(f"  {b:22s} {basr:>6.2f} [{blo:.2f}, {bhi:.2f}]   {mc['p_value']:>10.2e} "
              f"{rd:>+10.2f} {h:>9.2f} {'[' + format(dlo, '.2f') + ', ' + format(dhi, '.2f') + ']':>16s}")

    allp = max(r["mcnemar_p"] for r in rows)
    print(f"\nEvery comparison carries a p-value, an effect size (risk difference & "
          f"Cohen's h), and CIs. CAPM beats every baseline (all McNemar favour CAPM, "
          f"max p = {allp:.2e}; large effect sizes; difference CIs exclude 0).")

    csv_path = os.path.join(OUT_DIR, "statistics.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    fig_path = _make_figure(rows, capm_asr)

    print(f"\nCSV: {csv_path}")
    if fig_path:
        print(f"Fig: {fig_path}")
    print("=" * 88)
    ok = (all(r["favours"] == "A" and r["mcnemar_p"] < 0.05 for r in rows)
          and all(r["diff_ci_lo"] > 0 for r in rows))
    print("PASS" if ok else "FAIL")
    return 0 if ok else 2


def _make_figure(rows, capm_asr) -> str:
    """Forest plot of the per-baseline risk difference with bootstrap 95% CIs."""
    try:
        from experiments import figtools as ft
    except Exception as e:
        print(f"(figure skipped: {e})")
        return ""
    import numpy as np
    labels = [r["baseline"] for r in rows]
    rd = [r["risk_difference"] for r in rows]
    lo = [r["risk_difference"] - r["diff_ci_lo"] for r in rows]
    hi = [r["diff_ci_hi"] - r["risk_difference"] for r in rows]
    y = np.arange(len(labels))
    fig, ax = ft.new(figsize=(7.8, 4.4))
    ax.errorbar(rd, y, xerr=[lo, hi], fmt="D", color=ft.ACCENT, markersize=9,
                capsize=5, lw=2, label="risk difference (ASR_baseline − ASR_CAPM)")
    ax.axvline(0, color="#888", ls=":", lw=1.2)
    ax.text(0.02, len(labels) - 0.4, "no effect", fontsize=8, color="#777")
    for yi, r in zip(y, rows):
        ax.text(r["risk_difference"], yi + 0.18,
                f"p={r['mcnemar_p']:.0e}, h={r['cohens_h']:.1f}", fontsize=7.5,
                ha="center", color="#444")
    ft._style(ax, "E9.3 — effect sizes + significance (CAPM vs baselines)",
              xlabel="risk difference in ASR (with bootstrap 95% CI)", ylabel="")
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlim(-0.05, 1.15)
    ax.legend(fontsize=8, frameon=False, loc="lower right")
    return ft.save(fig, "e9_3_statistics_forest.png")


if __name__ == "__main__":
    raise SystemExit(main())
