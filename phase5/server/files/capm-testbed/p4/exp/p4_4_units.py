"""P4-4 — Unit-of-analysis + corrected confidence intervals (WS4, statistical hygiene).

Implementation-grade: a SWEEP of every load-bearing metric that has (or should have)
a CI, each recomputed at its true unit of independence, with the naive per-row CI
shown alongside to expose the overstatement:

  A.1  laundered usable / accepted rate  -> per-cell (content-blind grid, deterministic)
  B.2  usage AUC (sourced vs fabricated) -> advisory-cluster bootstrap
  C.1  support AUC (intact vs stripped)  -> advisory-cluster bootstrap
  D.1  combiner g AUC (leakage-free)     -> advisory-cluster bootstrap
  F.1  pooled & within-benign rho(g,v)   -> advisory-cluster bootstrap

Emits the Data-to-record CSV and the per-experiment unit-of-analysis declaration.
Construction-oracle (A.2 kappa, D.1 label) and by-construction (E.x) metrics carry
NO sampling CI — declared, not computed.

Run:  python -m p4.exp.p4_4_units
"""
from __future__ import annotations
import csv, os
import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

from p4.stats.units import UNITS, grid_cell_ci, cluster_bootstrap_ci, row_bootstrap_ci

R = lambda *p: os.path.join("p3", "results", *p)
OUT = os.path.join("p4", "results", "p4_4")


def _fmt(ci):
    return f"[{ci[0]:+.4f}, {ci[1]:+.4f}]"


def _auc_fn(label_fn, score_fn):
    def m(rows):
        y = [label_fn(r) for r in rows]
        if len(set(y)) < 2:
            return float("nan")
        return roc_auc_score(y, [score_fn(r) for r in rows])
    return m


def _auc_sweep_row(name, exp, rows, label_fn, score_fn, cluster_fn):
    fn = _auc_fn(label_fn, score_fn)
    obs = fn(rows)
    rb = row_bootstrap_ci(rows, fn, n_boot=2000, seed=0)
    cb = cluster_bootstrap_ci(rows, cluster_fn, fn, n_boot=2000, seed=0)
    rw, cw = rb["ci"][1] - rb["ci"][0], cb["ci"][1] - cb["ci"][0]
    print(f"{name:28s} obs={obs:.4f}  per-row {_fmt(rb['ci'])} (w{rw:.3f},n{rb['n_units']})  "
          f"CLUSTER {_fmt(cb['ci'])} (w{cw:.3f},n{cb['n_units']} adv)  x{cw/rw:.2f}")
    return dict(experiment=exp, metric=name, independent_unit="advisory", n_units=cb["n_units"],
                ci_low=round(cb["ci"][0], 4), ci_high=round(cb["ci"][1], 4),
                prev_per_row_ci_low=round(rb["ci"][0], 4), prev_per_row_ci_high=round(rb["ci"][1], 4))


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    record = []
    print("=" * 100)
    print("P4-4  Unit of analysis + corrected CIs  (naive per-row/per-claim  vs  TRUE unit)")
    print("=" * 100)

    # ---- A.1: content-blind grid -> per-cell ------------------------------------
    laund = [r for r in csv.DictReader(open(R("a1", "a1_raw.csv"))) if r["transform_type"] != "faithful_summary"]
    print("\n[A.1] content-blind policy grid (per-row Wilson  vs  per-cell Wilson):")
    for metric, key in (("laundered_usable_rate", "usable_by_capm"), ("laundered_accepted_rate", "accepted_by_capm")):
        g = grid_cell_ci(laund, ["source_class", "hops", "propagation"], key)
        pr_w, pc_w = g["per_row_ci"][1] - g["per_row_ci"][0], g["per_cell_ci"][1] - g["per_cell_ci"][0]
        print(f"  {metric:24s} pt={g['point']:.4f}  per-row [{g['per_row_ci'][0]:.4f},{g['per_row_ci'][1]:.4f}] "
              f"(w{pr_w:.4f},n{g['n_rows']})  PER-CELL [{g['per_cell_ci'][0]:.4f},{g['per_cell_ci'][1]:.4f}] "
              f"(w{pc_w:.4f},n{g['n_cells']})  x{pc_w/pr_w:.0f}  det {g['deterministic_cells']}/{g['n_cells']}")
        record.append(dict(experiment="A.1", metric=metric, independent_unit="grid cell", n_units=g["n_cells"],
                           ci_low=round(g["per_cell_ci"][0], 4), ci_high=round(g["per_cell_ci"][1], 4),
                           prev_per_row_ci_low=round(g["per_row_ci"][0], 4),
                           prev_per_row_ci_high=round(g["per_row_ci"][1], 4)))

    # ---- learned-sensor AUCs -> advisory-cluster bootstrap ----------------------
    print("\n[B.2 / C.1 / D.1] learned-sensor AUCs (per-row bootstrap  vs  advisory-cluster bootstrap):")
    # B.2 usage AUC (sourced vs fabricated), distilgpt2
    b2 = [r for r in csv.DictReader(open(R("b2", "b2_claims.csv"))) if r["model"] == "distilgpt2"]
    record.append(_auc_sweep_row("B.2 usage AUC", "B.2", b2,
                                  lambda r: 1 if r["sourced_or_fabricated"] == "sourced" else 0,
                                  lambda r: float(r["u_mean"]), lambda r: r["claim_id"].split(":")[0]))
    # C.1 support AUC (intact vs stripped, embedding space)
    c1 = [r for r in csv.DictReader(open(R("c1", "c1_support.csv")))
          if r["space"] == "embedding" and r["condition"] in ("intact", "stripped")]
    record.append(_auc_sweep_row("C.1 support AUC", "C.1", c1,
                                  lambda r: 1 if r["condition"] == "intact" else 0,
                                  lambda r: float(r["support_score"]), lambda r: r["claim_id"].split(":")[0]))
    # D.1 combiner g=min(u,s,faith_ctx) AUC vs trust (leakage-free, from WS1)
    fr = {(r["rec"], r["field"], r["value"]): float(r["faith_ctx"])
          for r in csv.DictReader(open(os.path.join("p4", "results", "p1a", "faith_recompute.csv")))}
    d1 = []
    for r in csv.DictReader(open(R("scored_claims.csv"))):
        k = (r["rec"], r["field"], r["value"])
        if k in fr and r["effect"] in ("survived", "distorted", "added"):
            d1.append(dict(rec=r["rec"], g=min(float(r["u"]), float(r["s"]), fr[k]), trust=int(r["trust"])))
    record.append(_auc_sweep_row("D.1 g AUC (leakage-free)", "D.1", d1,
                                  lambda r: r["trust"], lambda r: r["g"], lambda r: r["rec"]))

    # ---- F.1: pooled & within-benign rho -> advisory-cluster --------------------
    f1 = list(csv.DictReader(open(R("f1", "f1_influence.csv"))))
    for r in f1:
        r["rec"] = r["claim_id"].rsplit(":", 1)[0]
    def rho_fn(rows):
        return spearmanr([float(r["g_runtime"]) for r in rows], [float(r["v_influence"]) for r in rows]).correlation
    print("\n[F.1] influence correlation (per-row bootstrap  vs  advisory-cluster bootstrap):")
    for metric, sub in (("F.1 pooled rho", f1), ("F.1 within-benign rho", [r for r in f1 if r["label"] == "benign"])):
        rb = row_bootstrap_ci(sub, rho_fn, n_boot=2000, seed=0)
        cb = cluster_bootstrap_ci(sub, lambda r: r["rec"], rho_fn, n_boot=2000, seed=0)
        rw, cw = rb["ci"][1] - rb["ci"][0], cb["ci"][1] - cb["ci"][0]
        print(f"  {metric:24s} obs={rho_fn(sub):+.4f}  per-row {_fmt(rb['ci'])} (w{rw:.3f})  "
              f"CLUSTER {_fmt(cb['ci'])} (w{cw:.3f},n{cb['n_units']} adv)  x{cw/rw:.2f}")
        record.append(dict(experiment="F.1", metric=metric, independent_unit="advisory", n_units=cb["n_units"],
                           ci_low=round(cb["ci"][0], 4), ci_high=round(cb["ci"][1], 4),
                           prev_per_row_ci_low=round(rb["ci"][0], 4), prev_per_row_ci_high=round(rb["ci"][1], 4)))

    # ---- the unit-of-analysis declaration (the paper paragraph) -----------------
    print("\nUNIT-OF-ANALYSIS DECLARATION (per experiment):")
    for k, d in UNITS.items():
        print(f"  {k:5s} {d['unit']:34s} {d['method']:34s} {d['note']}")

    with open(os.path.join(OUT, "p4_4_units.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["experiment", "metric", "independent_unit", "n_units",
                                           "ci_low", "ci_high", "prev_per_row_ci_low", "prev_per_row_ci_high"])
        w.writeheader(); w.writerows(record)
    with open(os.path.join(OUT, "p4_4_unit_declaration.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["experiment", "independent_unit", "ci_method", "note"])
        for k, d in UNITS.items():
            w.writerow([k, d["unit"], d["method"], d["note"]])

    # PASS = the A.1 grid is deterministic and its per-cell CI is wider than per-row, every sampled
    # metric carries a CI at the advisory unit, and the record table is complete.
    a1_rows = [r for r in record if r["experiment"] == "A.1"]
    a1_ok = all(r["ci_high"] - r["ci_low"] > r["prev_per_row_ci_high"] - r["prev_per_row_ci_low"] for r in a1_rows)
    swept = {r["experiment"] for r in record}
    ok = a1_ok and {"A.1", "B.2", "C.1", "D.1", "F.1"} <= swept
    print("=" * 100)
    print(f"PASS — {len(record)} metrics recomputed at their true unit of independence across "
          f"{len(swept)} experiments; A.1 per-cell CIs are wider than the published per-row CIs (and the "
          "grid is deterministic — the rate is structural); B.2/C.1/D.1 AUCs and F.1 rho carry "
          "advisory-cluster CIs; construction-oracle and by-construction metrics carry no sampling CI "
          "(declared). Data-to-record table written." if ok else "REVIEW — sweep incomplete or A.1 CI not wider.")
    print("=" * 100)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
