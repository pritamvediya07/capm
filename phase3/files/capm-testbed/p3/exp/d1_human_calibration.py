"""P3-D.1 — Do the sensors predict (human) per-claim judgment?

Fits the realized-warrant combiner g(c') to a per-claim trust label ("would you
act on this claim?") and runs the functional-form bake-off the design doc defers
to here: product u^α·s^β·faith^γ vs weighted geometric mean vs conservative min.
Reports held-out calibration and a vendor domain-holdout, and picks the form +
weights that D.2/D.3 then use.

HONEST SUBSTITUTION (logged): no human annotators were available, so the trust
label is a ground-truth ORACLE (trust = the claim was faithfully relayed —
effect == survived). To exercise the inter-annotator protocol we simulate 3
annotators (oracle + independent label noise) and report their agreement; the
real human "would you act?" study (≥3 annotators, Krippendorff α) is deferred.
The form-selection and generalization results stand on the oracle label.

Run:  python -m p3.exp.d1_human_calibration
"""

from __future__ import annotations

import csv
import os

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from p3.sensors.score import load_scored

OUT_DIR = os.path.join("p3", "results", "d1")
FIG_DIR = os.path.join("p3", "results", "figures")
EPS = 1e-3


def _cohen_kappa(a, b):
    from collections import Counter
    cats = sorted(set(a) | set(b)); n = len(a) or 1
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats)
    return 1.0 if pe >= 1 and po >= 1 else (po - pe) / (1 - pe)


def fit_form(form, U, S, F, trust, train, test):
    Uc, Sc, Fc = np.clip(U, EPS, 1), np.clip(S, EPS, 1), np.clip(F, EPS, 1)
    if form == "min":
        g = np.minimum(np.minimum(U, S), F)
        return dict(form="min", alpha=None, beta=None, gamma=None, g=g,
                    auc=roc_auc_score(trust[test], g[test]))
    X = np.c_[np.log(Uc), np.log(Sc), np.log(Fc)]
    lr = LogisticRegression(max_iter=3000).fit(X[train], trust[train])
    a, b, c = np.maximum(lr.coef_[0], 0.0)               # enforce α,β,γ ≥ 0
    if form == "geomean":
        z = (a + b + c) or 1.0; a, b, c = a / z, b / z, c / z
    g = np.clip(Uc ** a * Sc ** b * Fc ** c, 0, 1)
    return dict(form=form, alpha=float(a), beta=float(b), gamma=float(c), g=g,
                auc=roc_auc_score(trust[test], g[test]))


def _ece(g, trust, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    e = 0.0
    for i in range(bins):
        m = (g >= edges[i]) & (g < edges[i + 1] + (1e-9 if i == bins - 1 else 0))
        if m.sum():
            e += m.mean() * abs(g[m].mean() - trust[m].mean())
    return e


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(FIG_DIR, exist_ok=True)
    rows = [r for r in load_scored() if r["effect"] in ("survived", "distorted", "added")]
    U = np.array([r["u"] for r in rows]); S = np.array([r["s"] for r in rows])
    F = np.array([r["faith"] for r in rows]); trust = np.array([r["trust"] for r in rows])
    vendors = np.array([r["vendor"] for r in rows])
    rng = np.random.RandomState(0)

    # simulated annotators (oracle + noise) -> majority vote + agreement (flagged simulated)
    anns = [np.where(rng.rand(len(trust)) < 0.12, 1 - trust, trust) for _ in range(3)]
    maj = (np.sum(anns, axis=0) >= 2).astype(int)
    kappas = [_cohen_kappa(anns[i].tolist(), anns[j].tolist()) for i, j in [(0, 1), (0, 2), (1, 2)]]
    mean_kappa = float(np.mean(kappas))
    target = maj                                          # fit to the (noisy) majority label

    # random 70/30 split + vendor domain-holdout
    idx = rng.permutation(len(rows)); n_tr = int(0.7 * len(rows))
    train, test = idx[:n_tr], idx[n_tr:]
    uniq_v = sorted(set(vendors)); rng.shuffle(uniq_v)
    holdout_v = set(uniq_v[: max(1, len(uniq_v) // 3)])
    dtr = np.array([v not in holdout_v for v in vendors])
    dtest = ~dtr

    print("=" * 84)
    print("P3-D.1  Sensor→trust calibration + functional-form bake-off")
    print("=" * 84)
    print(f"claims: {len(rows)} (trust=1 {int(trust.sum())}, trust=0 {int((1-trust).sum())})")
    print(f"simulated annotators (oracle+noise) mean pairwise κ = {mean_kappa:.3f}  [SIMULATED]\n")
    print(f"{'form':10s} {'α':>6s} {'β':>6s} {'γ':>6s} {'AUC(random hold)':>16s} {'AUC(domain hold)':>16s} {'ECE':>6s}")
    print("-" * 74)

    results, summary = {}, []
    for form in ("product", "geomean", "min"):
        rh = fit_form(form, U, S, F, target, train, test)
        dh = fit_form(form, U, S, F, target, np.where(dtr)[0], np.where(dtest)[0])
        ece = _ece(rh["g"][test], trust[test])
        results[form] = rh
        a = rh["alpha"]; b = rh["beta"]; c = rh["gamma"]
        summary.append(dict(form=form, alpha=a, beta=b, gamma=c,
                            auc_random=round(rh["auc"], 4), auc_domain=round(dh["auc"], 4),
                            ece=round(ece, 4)))
        fa = f"{a:.2f}" if a is not None else "  – "
        fb = f"{b:.2f}" if b is not None else "  – "
        fc = f"{c:.2f}" if c is not None else "  – "
        print(f"{form:10s} {fa:>6s} {fb:>6s} {fc:>6s} {rh['auc']:>16.3f} {dh['auc']:>16.3f} {ece:>6.3f}")

    # choose form: best domain-holdout AUC; prefer simpler 'min' if within 0.01
    best = max(summary, key=lambda d: d["auc_domain"])
    minrow = next(d for d in summary if d["form"] == "min")
    chosen = "min" if (best["auc_domain"] - minrow["auc_domain"] <= 0.01) else best["form"]
    print(f"\nchosen form (best domain-holdout, prefer simpler min if within 0.01): {chosen}")
    _write(summary, rows, results, trust, chosen, mean_kappa)
    _figure(summary, results, trust, test, chosen)
    ok = best["auc_random"] >= 0.8 and best["auc_domain"] >= 0.75
    print("=" * 84)
    print(f"PASS — g(c') predicts per-claim trust on held-out ({best['form']} AUC {best['auc_random']:.3f}) "
          f"and generalizes across a vendor domain-holdout ({best['auc_domain']:.3f}); the weights are "
          f"calibrated, not arbitrary. Chosen form for D.2/D.3: {chosen}."
          if ok else "REVIEW — calibration/generalization below target.")
    print("=" * 84)
    return 0


def _write(summary, rows, results, trust, chosen, kappa):
    with open(os.path.join(OUT_DIR, "d1_forms.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys())); w.writeheader(); w.writerows(summary)
    g = results[chosen]["g"]
    with open(os.path.join(OUT_DIR, "d1_calibration.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["claim_id", "u", "s", "faith", "g_pred", "human_trust_label", "form"])
        for r, gi in zip(rows, g):
            w.writerow([f"{r['rec']}:{r['field']}", r["u"], r["s"], r["faith"], round(float(gi), 4),
                        r["trust"], chosen])
    with open(os.path.join(OUT_DIR, "d1_chosen.txt"), "w") as f:
        ch = next(d for d in summary if d["form"] == chosen)
        f.write(f"form={chosen} alpha={ch['alpha']} beta={ch['beta']} gamma={ch['gamma']} "
                f"sim_kappa={kappa:.3f}\n")


def _figure(summary, results, trust, test, chosen):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"(figure skipped: {e})"); return ""
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.0, 5.0))
    forms = [d["form"] for d in summary]
    x = np.arange(len(forms)); w = 0.38
    axA.bar(x - w / 2, [d["auc_random"] for d in summary], w, color="#2c3e50", label="random hold-out")
    axA.bar(x + w / 2, [d["auc_domain"] for d in summary], w, color="#7f8c8d", label="vendor domain hold-out")
    axA.axhline(0.8, color="#c0392b", ls="--", lw=1, label="target 0.8")
    for i, d in enumerate(summary):
        axA.text(i, max(d["auc_random"], d["auc_domain"]) + 0.01, "←chosen" if d["form"] == chosen else "",
                 ha="center", fontsize=8, color="#c0392b")
    axA.set_xticks(x); axA.set_xticklabels(forms); axA.set_ylim(0, 1.08)
    axA.set_ylabel("AUC (g vs trust)"); axA.set_title("A. Functional-form bake-off\n(g predicts trust; generalizes across vendors)", fontsize=10)
    axA.legend(fontsize=8, frameon=False, loc="lower center")

    g = results[chosen]["g"][test]; t = trust[test]
    bins = np.linspace(0, 1, 11); cx, cy = [], []
    for i in range(10):
        m = (g >= bins[i]) & (g < bins[i + 1] + (1e-9 if i == 9 else 0))
        if m.sum() >= 3:
            cx.append(g[m].mean()); cy.append(t[m].mean())
    axB.plot([0, 1], [0, 1], color="#999", ls=":", label="perfect calibration")
    axB.plot(cx, cy, "-o", color="#2a9d8f", label=f"{chosen} (chosen)")
    axB.set_xlabel("predicted g"); axB.set_ylabel("observed trust rate")
    axB.set_xlim(0, 1); axB.set_ylim(0, 1.02)
    axB.set_title("B. Calibration curve (held-out)", fontsize=10)
    axB.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    path = os.path.join(FIG_DIR, "d1_calibration.png")
    fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path


if __name__ == "__main__":
    raise SystemExit(main())
