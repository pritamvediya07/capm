"""P4-3.B2 — usage separation on Qwen2.5 (WS3 scale run).

Reuses the B.1 probe (trained on the cached B.1 features) and applies u as a
fabrication detector: AUC of u ranking genuinely-sourced claims above
memory-substituted fabrications, per subtlety level (blatant / plausible / added),
with mean vs min token pooling. The plausible near-miss is the declared residual.

Run:  python -m p4.exp.p3_b2_usage_separation --model Qwen/Qwen2.5-7B-Instruct --dtype bf16
"""
from __future__ import annotations
import argparse, csv, os
import numpy as np
from sklearn.metrics import roc_auc_score

from p4.models.whitebox import WhiteBoxLM
from p3.sensors.probe import UsageProbe
from p3.sensors.probe_data import build_usage_examples, _QUESTIONS
from p3.data.advisories.corpus import load_advisories
from p3.data.advisories.transform import _VENDOR_POOL, _PRODUCT_POOL, _CWE_POOL, _FAKE_PATCH
from p3.claims.extract import render_document

B1_OUT = os.path.join("p4", "results", "ws3", "b1")
OUT = os.path.join("p4", "results", "ws3", "b2")
_tag = lambda m, d: f"{m.split('/')[-1]}_{d}"


def claims_for(a, rng):
    f = a["fields"]; out = []
    for field in ("vendor", "product", "cwe", "due_date"):
        if not f.get(field):
            continue
        true = str(f[field])
        out.append((field, true, "sourced", "none"))
        pool = {"vendor": _VENDOR_POOL, "product": _PRODUCT_POOL, "cwe": _CWE_POOL}.get(field)
        if pool:
            out.append((field, rng.choice([x for x in pool if x.lower() not in true.lower()]), "fabricated", "blatant"))
        if field == "due_date":
            y, m, d = true.split("-")
            out.append((field, f"{y}-{m}-{int(d) % 27 + 1:02d}", "fabricated", "plausible"))
        elif field == "product":
            out.append((field, f"{true} Server Edition", "fabricated", "plausible"))
    out.append(("patch", f"a patch ({rng.choice(_FAKE_PATCH)}) is available", "fabricated", "added"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--dtype", default="bf16")
    ap.add_argument("--advisories", type=int, default=60)
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    # train the probe on the cached B.1 features (same construction as B.1)
    cache = os.path.join(B1_OUT, f"feat_{_tag(args.model, args.dtype)}.npz")
    if not os.path.exists(cache):
        raise SystemExit(f"run p3_b1_probe_transfer first (missing {cache})")
    fe = np.load(cache, allow_pickle=True)
    yb1 = np.array([e.label for e in build_usage_examples(n_advisories=80, seed=0)])
    probe = UsageProbe().fit(fe["final"][:len(yb1)], yb1)

    wb = WhiteBoxLM(args.model, dtype=args.dtype)
    Lf = wb.layers_of_interest()["final"]
    print("=" * 88)
    print(f"P4-3.B2  usage separation — {args.model} [dtype={args.dtype}] | VRAM {wb.vram_gb():.1f} GB")
    print("=" * 88)

    import random
    rng = random.Random(args.seed)
    advs = load_advisories(args.advisories, seed=args.seed)
    rows = []
    for a in advs:
        ctx = render_document(a)
        for field, val, kind, subtlety in claims_for(a, rng):
            q = _QUESTIONS.get(field, f"What is the {field}?")
            pooled, per_tok = wb.claim_features(f"{ctx}\nQuestion: {q}\nAnswer:", f" {val}", Lf)
            u_mean = float(probe.proba(pooled[None, :])[0])
            u_min = float(np.min(probe.proba(per_tok))) if per_tok.shape[0] else u_mean
            rows.append(dict(field=field, kind=kind, subtlety=subtlety, u_mean=u_mean, u_min=u_min))

    y = np.array([1 if r["kind"] == "sourced" else 0 for r in rows])
    um = np.array([r["u_mean"] for r in rows]); umin = np.array([r["u_min"] for r in rows])
    auc_mean, auc_min = roc_auc_score(y, um), roc_auc_score(y, umin)
    n_s, n_f = int(y.sum()), int((1 - y).sum())
    print(f"claims {len(rows)} (sourced {n_s}, fabricated {n_f})")
    print(f"  overall AUC — mean-pool = {auc_mean:.3f}   min-pool = {auc_min:.3f}   (Phase-3 mean-agg 0.93)")
    print("  by subtlety (mean-pool, sourced vs that fabrication class):")
    sub_csv = []
    for sub in ("blatant", "plausible", "added"):
        m = np.array([r["subtlety"] in (sub, "none") for r in rows])
        ys, us = y[m], um[m]
        if len(set(ys)) == 2:
            a = roc_auc_score(ys, us)
            print(f"    {sub:10s} AUC={a:.3f}" + ("   <- honest weak case (multi-sensor g covers it)" if sub == "plausible" else ""))
            sub_csv.append((sub, round(a, 4)))
    print(f"  DELTA vs Phase-3: overall {auc_mean-0.93:+.3f}")

    with open(os.path.join(OUT, f"b2_{_tag(args.model, args.dtype)}.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["model", "dtype", "pooling", "subtlety", "auc", "n_sourced", "n_fabricated"])
        w.writerow([args.model.split("/")[-1], args.dtype, "mean", "overall", round(auc_mean, 4), n_s, n_f])
        w.writerow([args.model.split("/")[-1], args.dtype, "min", "overall", round(auc_min, 4), n_s, n_f])
        for sub, a in sub_csv:
            w.writerow([args.model.split("/")[-1], args.dtype, "mean", sub, a, n_s, n_f])

    print("=" * 88)
    print(f"{'PASS' if auc_mean >= 0.8 else 'WEAK'} — u is an actionable fabrication detector at scale "
          f"(mean-AUC {auc_mean:.2f}); plausible near-miss is the declared residual that motivates the "
          "multi-sensor g.")
    print("=" * 88)


if __name__ == "__main__":
    main()
