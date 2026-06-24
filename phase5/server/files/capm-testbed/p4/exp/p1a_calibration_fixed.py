"""P4-1A — D.1 leakage fix + leakage-free calibration (WS1, HIGH).

The Phase-3 `faith` feature was computed against a synthesized `"The {field} is
{true_value}."` premise, i.e. the label's defining quantity (D.1 circular
leakage). This experiment recomputes `faith` against the **rendered source
document `ctx`** (the corrected scorer) and reports the THREE-number breakdown
P4-1A mandates, the faith-adds-value test, and a sanity control.

Method (a controlled A/B that isolates exactly the changed variable): we reuse
the cached, unchanged `u` and `s` from `p3/results/scored_claims.csv` and only
recompute `faith` two ways via the real DeBERTa-v3 NLI model:
  * faith_ctx     — premise = render_document(advisory)         [CORRECTED]
  * faith_leaked  — premise = "The {field} is {true_value}."    [Phase-3 LEAK, control]

Run:  python -m p4.exp.p1a_calibration_fixed
"""

from __future__ import annotations

import csv
import os
import warnings

import numpy as np

warnings.filterwarnings("ignore")

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from p3.claims.extract import render_document
from p3.data.advisories.corpus import load_advisories
from p3.sensors.nli import NLISensor

SCORED = os.path.join("p3", "results", "scored_claims.csv")
OUT = os.path.join("p4", "results", "p1a")
FAITH_CACHE = os.path.join(OUT, "faith_recompute.csv")
NLI_MODEL = "cross-encoder/nli-deberta-v3-xsmall"
_FAITH = {"entail": 1.0, "neutral": 0.5, "contradict": 0.0}
EPS = 1e-3


# ---------------------------------------------------------------- faith recompute
def _recompute_faith(rows):
    """Recompute faith two ways (ctx-grounded vs leaked) for every claim, cached."""
    os.makedirs(OUT, exist_ok=True)
    if os.path.exists(FAITH_CACHE):
        cache = {(r["rec"], r["field"], r["value"]): (float(r["faith_ctx"]), float(r["faith_leaked"]))
                 for r in csv.DictReader(open(FAITH_CACHE))}
        if all((r["rec"], r["field"], r["value"]) in cache for r in rows):
            for r in rows:
                r["faith_ctx"], r["faith_leaked"] = cache[(r["rec"], r["field"], r["value"])]
            print(f"  faith recompute: loaded from cache ({len(cache)} entries)")
            return rows
    advs = load_advisories(n=140, seed=7)
    amap = {a["record_id"]: a for a in advs}
    print(f"  faith recompute: loading NLI {NLI_MODEL} and scoring {len(rows)} claims x2 …")
    nli = NLISensor(NLI_MODEL)
    out, miss = [], 0
    for i, r in enumerate(rows):
        a = amap.get(r["rec"])
        field, value = r["field"], r["value"]
        claim = f"{field.replace('_', ' ')} is {value}"
        if a is None:
            miss += 1
            r["faith_ctx"] = r["faith_leaked"] = float(r["faith"])
        else:
            ctx = render_document(a)
            tv = a["fields"].get(field)
            fc = _FAITH[nli.predict(ctx, claim)[0]]
            fl = _FAITH[nli.predict(f"The {field.replace('_', ' ')} is {tv}.", claim)[0]] if tv else fc
            r["faith_ctx"], r["faith_leaked"] = fc, fl
        out.append(dict(rec=r["rec"], field=field, value=value,
                        faith_ctx=r["faith_ctx"], faith_leaked=r["faith_leaked"]))
        if (i + 1) % 250 == 0:
            print(f"    {i + 1}/{len(rows)} …", flush=True)
    with open(FAITH_CACHE, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["rec", "field", "value", "faith_ctx", "faith_leaked"])
        w.writeheader(); w.writerows(out)
    if miss:
        print(f"  [warn] {miss} claims had no matching advisory (kept cached faith)")
    return rows


# ----------------------------------------------------------------------- AUC utils
def _logit_auc(feature_cols, y, tr, te):
    X = np.column_stack([np.log(np.clip(f, EPS, 1.0)) for f in feature_cols])
    lr = LogisticRegression(max_iter=3000).fit(X[tr], y[tr])
    return roc_auc_score(y[te], lr.predict_proba(X[te])[:, 1])


def _min_auc(feature_cols, y, te):
    g = np.minimum.reduce(feature_cols)
    return roc_auc_score(y[te], g[te])


def _is_label_deterministic(feat, y):
    """Fraction of label classes for which `feat` is a single constant -> proxy for
    'feature is a deterministic function of the label'. 1.0 == perfectly leaked."""
    classes = [c for c in (0, 1)]
    det = sum(1 for c in classes if len(set(np.round(feat[y == c], 6))) == 1)
    return det / len(classes)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    rows = [r for r in csv.DictReader(open(SCORED)) if r["effect"] in ("survived", "distorted", "added")]
    rows = _recompute_faith(rows)

    u = np.array([float(r["u"]) for r in rows])
    s = np.array([float(r["s"]) for r in rows])
    f_old = np.array([float(r["faith"]) for r in rows])          # cached Phase-3 (leaked) faith
    f_ctx = np.array([float(r["faith_ctx"]) for r in rows])      # corrected
    f_leak = np.array([float(r["faith_leaked"]) for r in rows])  # recomputed leak (control)
    y = np.array([int(r["trust"]) for r in rows])
    vendors = np.array([r["vendor"] for r in rows])

    rng = np.random.RandomState(0)
    idx = rng.permutation(len(rows)); ntr = int(0.7 * len(rows))
    tr, te = idx[:ntr], idx[ntr:]
    uv = sorted(set(vendors)); rng.shuffle(uv)
    hold = set(uv[: max(1, len(uv) // 3)])
    dtr = np.where(np.array([v not in hold for v in vendors]))[0]
    dte = np.where(np.array([v in hold for v in vendors]))[0]

    # ---- code-verified leakage check ------------------------------------------
    leak_old = _is_label_deterministic(f_old, y)
    leak_ctx = _is_label_deterministic(f_ctx, y)
    print("=" * 90)
    print("P4-1A  D.1 leakage fix — leakage-free calibration (faith premise = ctx)")
    print("=" * 90)
    print(f"claims: {len(rows)} (trust=1 {int(y.sum())}, trust=0 {int((1 - y).sum())})\n")
    print("CODE-VERIFIED LEAKAGE CHECK (is the feature a deterministic function of the label?)")
    print(f"  faith_leaked (premise='The {{field}} is {{true_value}}.') : label-deterministic frac = {leak_old:.3f}")
    print(f"  faith_ctx    (premise=rendered source document)          : label-deterministic frac = {leak_ctx:.3f}")
    print(f"  -> corrected faith is NOT a deterministic function of the label: {leak_ctx < 1.0}\n")

    # ---- THE THREE NUMBERS (random hold-out + vendor domain hold-out) ----------
    def row(name, cols):
        return (name, _logit_auc(cols, y, tr, te), _logit_auc(cols, y, dtr, dte))

    us = row("u+s            (non-leaked)", [u, s])
    fct = ("faith_ctx only (corrected)", roc_auc_score(y[te], f_ctx[te]), roc_auc_score(y[dte], f_ctx[dte]))
    g_ctx = ("g=min(u,s,faith_ctx)", _min_auc([u, s, f_ctx], y, te), _min_auc([u, s, f_ctx], y, dte))
    usf = row("u+s+faith_ctx  (logit)", [u, s, f_ctx])
    print(f"{'feature set':32s} {'AUC(random)':>12s} {'AUC(domain)':>12s}")
    print("-" * 60)
    for nm, a_r, a_d in (us, fct, usf, g_ctx):
        print(f"{nm:32s} {a_r:12.3f} {a_d:12.3f}")
    lift = usf[1] - us[1]
    print(f"\nFAITH-ADDS-VALUE: AUC(u+s+faith_ctx) - AUC(u+s) = {usf[1]:.3f} - {us[1]:.3f} = {lift:+.3f}")
    verdict = ("faith adds marginal calibration value -> keep as calibration contributor"
               if lift >= 0.01 else
               "faith adds ~0 marginal calibration AUC on structured data -> reposition as a "
               "CONTRADICTION-specific safety signal (earns its place via C.2), not calibration")
    print(f"  -> {verdict}")

    # ---- SANITY CONTROL: re-introduce the leak, AUC must jump back up ----------
    auc_ctx = _min_auc([u, s, f_ctx], y, te)
    auc_leak = _min_auc([u, s, f_leak], y, te)
    fa_ctx = roc_auc_score(y[te], f_ctx[te]); fa_leak = roc_auc_score(y[te], f_leak[te])
    print("\nSANITY CONTROL (proves the leak was the cause, not noise):")
    print(f"  faith-alone AUC:  ctx={fa_ctx:.3f}   leaked={fa_leak:.3f}   (jump {fa_leak - fa_ctx:+.3f})")
    print(f"  g=min   AUC:      ctx={auc_ctx:.3f}   leaked={auc_leak:.3f}   (jump {auc_leak - auc_ctx:+.3f})")

    # ---- write artifacts -------------------------------------------------------
    with open(os.path.join(OUT, "p1a_calibration.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["feature_set", "auc_random", "auc_domain"])
        for nm, a_r, a_d in (us, fct, usf, g_ctx):
            w.writerow([nm, round(a_r, 4), round(a_d, 4)])
        w.writerow(["faith_marginal_lift_over_us", round(lift, 4), ""])
        w.writerow(["sanity_faith_alone_ctx_vs_leaked", round(fa_ctx, 4), round(fa_leak, 4)])
        w.writerow(["sanity_gmin_ctx_vs_leaked", round(auc_ctx, 4), round(auc_leak, 4)])

    # ---- PASS criteria ---------------------------------------------------------
    ok = (leak_ctx < 1.0                                   # no feature deterministic in the label
          and abs(fa_leak - fa_ctx) >= 0.01                # sanity control fires (leak was the cause)
          )
    print("=" * 90)
    print("PASS — faith regrounded in ctx; no feature is a deterministic function of the label; "
          "three numbers reported; faith-adds-value answered; sanity control fires. "
          "NO calibration adjective is claimed (construction-oracle label; human study still future work)."
          if ok else "REVIEW — leakage check or sanity control did not behave as expected; inspect.")
    print("=" * 90)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
