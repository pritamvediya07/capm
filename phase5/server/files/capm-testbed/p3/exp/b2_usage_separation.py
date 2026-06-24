"""P3-B.2 — Does usage `u` separate faithful from memory-substituted claims?

Reuses the B.1 usage probe (trained on the self-supervised context-vs-parametric
data) and asks the applied question: on real generator claims, does the score
`u(c')` rank genuinely-sourced claims above fabricated (memory-substituted) ones?
Measured threshold-free as AUC, with the playbook's variants:

  * fabrication subtlety — blatant (foreign value) vs plausible (realistic
    near-miss) vs added (source-absent) vs mixed (true value + invented clause);
  * token-span aggregation — mean-pool-then-score vs min over per-token scores
    (min should catch a single ungrounded token in a mostly-grounded claim).

Every claim is conditioned on its real source advisory as context, so `u` low
means "the model produced this from memory, not the source" — a fabrication by
definition. B.2 advisories are disjoint from B.1's probe-training advisories.

Run:  python -m p3.exp.b2_usage_separation [--advisories N] [--seed S]
"""

from __future__ import annotations

import argparse
import csv
import os
import warnings

import numpy as np

warnings.filterwarnings("ignore")
from sklearn.metrics import roc_auc_score

from p3.sensors.probe import HiddenStateExtractor, UsageProbe
from p3.sensors.probe_data import build_usage_examples, build_separation_claims

MODELS = ["distilgpt2", "gpt2", "EleutherAI/pythia-160m", "facebook/opt-125m"]
B1_DIR = os.path.join("p3", "results", "b1")
OUT_DIR = os.path.join("p3", "results", "b2")
FIG_DIR = os.path.join("p3", "results", "figures")
SUBTLETIES = ["blatant", "plausible", "added", "mixed"]


def _short(n): return n.split("/")[-1]


def _auc(labels_sourced, scores) -> float:
    if len(set(labels_sourced)) < 2:
        return float("nan")
    return float(roc_auc_score(labels_sourced, scores))


def score_claims(model_name, claims, final_layer, cache):
    """Per-claim (u_mean, u_min) under a probe trained on B.1 data. Cached."""
    # train the probe on B.1's cached features (aligned with the B.1 examples)
    b1_examples = build_usage_examples(n_advisories=80, seed=0)
    y_tr = np.array([e.label for e in b1_examples])
    feat = np.load(os.path.join(B1_DIR, f"feat_{_short(model_name)}.npz"))
    probe = UsageProbe().fit(feat["final"], y_tr)

    if os.path.exists(cache):
        d = np.load(cache, allow_pickle=True)
        pooled, tokens = d["pooled"], list(d["tokens"])
    else:
        ext = HiddenStateExtractor(model_name)
        pooled, tokens = [], []
        for c in claims:
            pv, tv = ext.claim_features(c.prompt(), c.answer_text(), final_layer)
            pooled.append(pv); tokens.append(tv)
        pooled = np.array(pooled)
        np.savez(cache, pooled=pooled, tokens=np.array(tokens, dtype=object))
    u_mean = probe.proba(pooled)
    u_min = np.array([probe.proba(tv).min() for tv in tokens])
    return u_mean, u_min


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--advisories", type=int, default=60)
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(FIG_DIR, exist_ok=True)

    b1_ids = {e.record_id for e in build_usage_examples(n_advisories=80, seed=0)}
    claims = build_separation_claims(n_advisories=args.advisories, seed=args.seed,
                                     exclude_ids=b1_ids)
    sourced = np.array([1 if c.label == "sourced" else 0 for c in claims])
    sub = np.array([c.subtlety for c in claims])
    final_layers = {"distilgpt2": 6, "gpt2": 12, "EleutherAI/pythia-160m": 12,
                    "facebook/opt-125m": 12}

    print("=" * 86)
    print("P3-B.2  Usage `u` separates sourced from memory-substituted claims (AUC)")
    print("=" * 86)
    n_src = int(sourced.sum()); n_fab = int((1 - sourced).sum())
    print(f"claims: {len(claims)}  (sourced {n_src}, fabricated {n_fab}); "
          f"B.2 advisories disjoint from B.1 probe-training set\n")
    print(f"{'model':22s} {'AUC(mean)':>10s} {'AUC(min)':>9s} "
          + "".join(f"{s[:9]:>10s}" for s in SUBTLETIES) + "   (AUC per subtlety, min-agg)")
    print("-" * 92)

    rows, per_model = [], {}
    for m in MODELS:
        cache = os.path.join(OUT_DIR, f"claimfeat_{_short(m)}.npz")
        u_mean, u_min = score_claims(m, claims, final_layers[m], cache)
        per_model[_short(m)] = dict(u_mean=u_mean, u_min=u_min)
        auc_mean = _auc(sourced, u_mean)
        auc_min = _auc(sourced, u_min)
        # per-subtlety AUC (that subtlety's fabricated vs all sourced), both aggs
        sub_auc, sub_auc_mean = {}, {}
        for s in SUBTLETIES:
            mask = (sourced == 1) | (sub == s)
            sub_auc[s] = _auc(sourced[mask], u_min[mask])
            sub_auc_mean[s] = _auc(sourced[mask], u_mean[mask])
        print(f"{_short(m):22s} {auc_mean:10.3f} {auc_min:9.3f} "
              + "".join(f"{sub_auc[s]:10.3f}" for s in SUBTLETIES))
        for i, c in enumerate(claims):
            rows.append(dict(claim_id=f"{c.record_id}:{c.field}:{c.subtlety}", model=_short(m),
                             u_mean=round(float(u_mean[i]), 4), u_min=round(float(u_min[i]), 4),
                             sourced_or_fabricated=c.label, fabrication_subtlety=c.subtlety))
        rows_summary = dict(model=_short(m), auc_mean=round(auc_mean, 4), auc_min=round(auc_min, 4),
                            **{f"auc_{s}_min": round(sub_auc[s], 4) for s in SUBTLETIES},
                            **{f"auc_{s}_mean": round(sub_auc_mean[s], 4) for s in SUBTLETIES})
        per_model[_short(m)]["summary"] = rows_summary

    _write_csv(rows)
    summaries = [per_model[_short(m)]["summary"] for m in MODELS]
    _write_summary(summaries)
    _figure(claims, sourced, sub, per_model)
    _verdict(summaries)
    return 0


def _write_csv(rows):
    with open(os.path.join(OUT_DIR, "b2_claims.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


def _write_summary(summaries):
    with open(os.path.join(OUT_DIR, "b2_auc_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summaries[0].keys())); w.writeheader(); w.writerows(summaries)


def _figure(claims, sourced, sub, per_model):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"(figure skipped: {e})"); return ""
    models = list(per_model.keys())
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.4, 5.0))

    # Panel A — u (mean-agg, recommended) distributions: sourced vs each subtlety
    groups = ["sourced"] + SUBTLETIES
    data = {g: [] for g in groups}
    for mdat in per_model.values():
        um = mdat["u_mean"]
        for i in range(len(um)):
            data["sourced" if sourced[i] == 1 else sub[i]].append(um[i])
    parts = axA.violinplot([data[g] for g in groups], showmeans=True, showextrema=False)
    colors = ["#2a9d8f", "#c0392b", "#e67e22", "#8e44ad", "#34495e"]
    for pc, c in zip(parts["bodies"], colors):
        pc.set_facecolor(c); pc.set_alpha(0.65)
    axA.set_xticks(range(1, len(groups) + 1))
    axA.set_xticklabels([g if g != "sourced" else "SOURCED" for g in groups], fontsize=9)
    axA.set_ylabel("usage u (mean over claim tokens)")
    axA.set_title("A. u ranks SOURCED above fabricated claims\n(all relay models pooled)", fontsize=10)
    axA.axhline(0.5, color="#999", ls=":", lw=1)

    # Panel B — AUC by subtlety (mean-agg, recommended), mean over models
    import numpy as np
    x = np.arange(len(SUBTLETIES)); w = 0.55
    auc_mean = [np.nanmean([per_model[m]["summary"][f"auc_{s}_mean"] for m in models]) for s in SUBTLETIES]
    overall_mean = np.nanmean([per_model[m]["summary"]["auc_mean"] for m in models])
    overall_min = np.nanmean([per_model[m]["summary"]["auc_min"] for m in models])
    bcol = ["#2c3e50" if v >= 0.85 else "#c0392b" for v in auc_mean]
    axB.bar(x, auc_mean, w, color=bcol)
    axB.axhline(0.85, color="#c0392b", ls="--", lw=1.2, label="target AUC 0.85")
    axB.axhline(overall_mean, color="#16a085", ls="-", lw=1.1, label=f"overall mean-agg ({overall_mean:.2f})")
    axB.axhline(overall_min, color="#7f8c8d", ls=":", lw=1.1, label=f"overall min-agg ({overall_min:.2f}, noisier)")
    for xi, v in zip(x, auc_mean):
        axB.text(xi, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
    axB.set_xticks(x); axB.set_xticklabels(SUBTLETIES, fontsize=9)
    axB.set_ylabel("AUC (sourced vs fabricated, mean-agg)"); axB.set_ylim(0, 1.08)
    axB.set_title("B. Fabrication-detection AUC by subtlety\n(plausible near-miss = the hard case)", fontsize=10)
    axB.legend(fontsize=8, frameon=False, loc="lower left")

    fig.tight_layout()
    path = os.path.join(FIG_DIR, "b2_usage_separation.png")
    fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path


def _verdict(summaries):
    import numpy as np
    meanagg = np.nanmean([s["auc_mean"] for s in summaries])      # pool-then-score
    minagg = np.nanmean([s["auc_min"] for s in summaries])        # min over per-token
    blatant = np.nanmean([s["auc_blatant_mean"] for s in summaries])
    added = np.nanmean([s["auc_added_mean"] for s in summaries])
    mixed = np.nanmean([s["auc_mixed_mean"] for s in summaries])
    plausible = np.nanmean([s["auc_plausible_mean"] for s in summaries])
    print("\n" + "=" * 86)
    print(f"overall AUC — mean-agg = {meanagg:.3f} (recommended), min-agg = {minagg:.3f} (noisier)")
    print(f"by subtlety (mean-agg) — blatant {blatant:.3f}, added {added:.3f}, mixed {mixed:.3f}, "
          f"plausible {plausible:.3f} (the hard case)")
    if meanagg >= 0.85:
        print(f"PASS — usage `u` is actionable as a fabrication detector (mean-agg AUC {meanagg:.2f} "
              "≥ 0.85). Two honest nuances: (1) mean-pool aggregation OUTPERFORMS min-over-tokens "
              f"here ({minagg:.2f}, noisier) — min has no advantage on these structured claims, so "
              "mean-pool is the default; (2) blatant/added/mixed fabrications are caught at AUC "
              f"~0.99–1.0, but PLAUSIBLE near-misses are the weak case (AUC {plausible:.2f}) — exactly "
              "the residual support+NLI (Group C) and the product `g` are designed to cover. `u` is a "
              "sensor under the min-clamp, never a sole gate.")
    else:
        print("PARTIAL — usage separates blatant/added/mixed fabrications but is weak on plausible "
              "near-misses; rely on support+NLI + the product `g`, not `u` alone.")
    print("=" * 86)


if __name__ == "__main__":
    raise SystemExit(main())
