"""p4/stats/units.py — unit-of-analysis helpers (WS4 / P4-4 shared infra).

The recurring Phase-3 error is computing confidence intervals over CORRELATED rows
as if they were i.i.d. — most visibly A.1, whose 17,280 laundered rows collapse to
24 deterministic policy-grid cells, so a per-row Wilson CI overstates precision ~25x
and never narrows with more data. This module computes CIs at the TRUE independent
unit:

  * grid_cell_ci  — for content-blind grids (A.1): per-cell, with a determinism check.
  * cluster_bootstrap_ci — resamples CLUSTERS (advisories), not rows, for AUC / rho
    metrics where claims from one advisory are not independent (B/C/D/F).
  * row_bootstrap_ci — the naive per-row bootstrap, kept only to expose the overstatement.

UNITS declares the independent unit per experiment for the paper's unit-of-analysis
paragraph.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np


# ---- the per-experiment unit-of-analysis declaration (the paper paragraph) -------
UNITS = {
    "A.1": dict(unit="policy grid cell (24, exhaustive)", method="per-cell / deterministic",
                note="content-blind => rates are structural; per-row CI is invalid"),
    "A.2": dict(unit="advisory / field-type", method="cluster bootstrap over advisories",
                note="construction-oracle labels => NO human-style CI; kappa annotators are SIMULATED"),
    "B.1": dict(unit="advisory", method="cluster bootstrap", note="claims share the source advisory"),
    "B.2": dict(unit="advisory", method="cluster bootstrap", note="advisory-disjoint from B.1"),
    "C.1": dict(unit="advisory (80)", method="cluster bootstrap", note=""),
    "C.2": dict(unit="constructed case (75)", method="exact / small-n", note="cases ~independent; report counts"),
    "D.1": dict(unit="advisory", method="cluster bootstrap",
                note="oracle trust label => NO human-style CI; AUC leakage-free post-WS1"),
    "D.2": dict(unit="advisory (if any CI)", method="none (deterministic frontier)", note=""),
    "D.3": dict(unit="none (by-construction)", method="none", note="locality is structural"),
    "E.1": dict(unit="none (exhaustive enumeration)", method="none", note="60/60 is a check, not a sample"),
    "E.2": dict(unit="none (exhaustive enumeration)", method="none", note="1800/1800 is a check, not a sample"),
    "E.3": dict(unit="none (exhaustive enumeration)", method="none", note="forgery battery, not a sample"),
    "F.1": dict(unit="advisory (claims clustered)", method="cluster bootstrap + partials",
                note="pooled rho is label-driven; report within-cluster + permutation"),
    "F.3": dict(unit="advisory", method="cluster bootstrap", note="residual ASR"),
    "G.1": dict(unit="timing run", method="mean +/- std over repeats", note="latency, not a proportion"),
}


def wilson_ci(k: int, n: int, z: float = 1.96):
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (float("nan"), float("nan"))
    ph = k / n
    d = 1 + z * z / n
    center = (ph + z * z / (2 * n)) / d
    half = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, center - half), min(1.0, center + half))


def grid_cell_ci(rows, cell_keys, outcome_key):
    """For a content-blind grid: collapse rows to cells, report the per-row Wilson CI
    (the WRONG one) next to the per-cell CI (the right unit) and the determinism."""
    def b(x):
        return 1 if str(x).strip().lower() in ("1", "true", "yes") else 0
    n_rows = len(rows)
    k_rows = sum(b(r[outcome_key]) for r in rows)
    cells = defaultdict(list)
    for r in rows:
        cells[tuple(r[k] for k in cell_keys)].append(b(r[outcome_key]))
    cell_means = {c: sum(v) / len(v) for c, v in cells.items()}
    deterministic = sum(1 for v in cells.values() if len(set(v)) == 1)
    k_cells = sum(1 for m in cell_means.values() if m >= 0.5)
    n_cells = len(cells)
    return dict(
        point=k_rows / n_rows if n_rows else float("nan"),
        per_row_ci=wilson_ci(k_rows, n_rows), n_rows=n_rows,
        per_cell_ci=wilson_ci(k_cells, n_cells), n_cells=n_cells,
        deterministic_cells=deterministic, k_cells=k_cells)


def _percentile_ci(samples, ci=95):
    lo, hi = np.percentile(samples, [(100 - ci) / 2, 100 - (100 - ci) / 2])
    return float(lo), float(hi)


def cluster_bootstrap_ci(rows, cluster_key, metric_fn, n_boot=2000, seed=0, ci=95):
    """Resample CLUSTERS (e.g. advisories) with replacement; recompute the metric on
    the gathered rows each time. The honest CI when rows within a cluster are correlated."""
    clusters = defaultdict(list)
    for r in rows:
        clusters[cluster_key(r)].append(r)
    cids = list(clusters)
    rng = np.random.RandomState(seed)
    out = []
    for _ in range(n_boot):
        pick = rng.randint(0, len(cids), len(cids))
        sample = [row for i in pick for row in clusters[cids[i]]]
        try:
            s = metric_fn(sample)
            if s == s:
                out.append(s)
        except Exception:
            pass
    lo, hi = _percentile_ci(out, ci)
    return dict(point=float(np.mean(out)), ci=(lo, hi), n_units=len(cids), method="cluster bootstrap")


def row_bootstrap_ci(rows, metric_fn, n_boot=2000, seed=0, ci=95):
    """Naive per-row bootstrap (the overstated CI) — kept for the side-by-side only."""
    rng = np.random.RandomState(seed)
    n = len(rows)
    out = []
    for _ in range(n_boot):
        idx = rng.randint(0, n, n)
        sample = [rows[i] for i in idx]
        try:
            s = metric_fn(sample)
            if s == s:
                out.append(s)
        except Exception:
            pass
    lo, hi = _percentile_ci(out, ci)
    return dict(point=float(np.mean(out)), ci=(lo, hi), n_units=n, method="per-row bootstrap")
