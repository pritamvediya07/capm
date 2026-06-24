"""P4-2.2 — F.1 partial-correlation disclosure (WS2, LOW; highest-value honesty fix).

The Phase-3 ledger reports only the POOLED Spearman rho(g,v)=0.62 ("cheap g tracks
expensive influence"). The pool is two label clusters; controlling for the
attack/benign label the correlation vanishes/reverses. This recomputes the pooled,
within-cluster, and partial correlations from p3/results/f1/f1_influence.csv and
adds a permutation test on the within-benign correlation.

Run:  python -m p4.exp.p2_2_f1_partials
"""
from __future__ import annotations
import csv, os, numpy as np
from scipy.stats import spearmanr, pearsonr

F1 = os.path.join("p3", "results", "f1", "f1_influence.csv")


def _partial_spearman(g, v, z):
    rgv, rgz, rvz = spearmanr(g, v).correlation, spearmanr(g, z).correlation, spearmanr(v, z).correlation
    return (rgv - rgz * rvz) / np.sqrt((1 - rgz ** 2) * (1 - rvz ** 2)), rgz, rvz


def main() -> int:
    rows = list(csv.DictReader(open(F1)))
    g = np.array([float(r["g_runtime"]) for r in rows])
    v = np.array([float(r["v_influence"]) for r in rows])
    lab = np.array([1 if r["label"] == "attack" else 0 for r in rows])

    pooled = spearmanr(g, v).correlation
    wb_mask, wa_mask = lab == 0, lab == 1
    wb = spearmanr(g[wb_mask], v[wb_mask]).correlation
    wa = spearmanr(g[wa_mask], v[wa_mask]).correlation
    partial, rgl, rvl = _partial_spearman(g, v, lab)

    # permutation test on within-benign rho (shuffle v within benign)
    rng = np.random.RandomState(0)
    gb, vb = g[wb_mask], v[wb_mask]
    obs = abs(wb)
    perms = [abs(spearmanr(gb, rng.permutation(vb)).correlation) for _ in range(2000)]
    pval = (1 + sum(p >= obs for p in perms)) / (1 + len(perms))

    print("=" * 84)
    print("P4-2.2  F.1 — pooled vs within-cluster vs partial correlation of g and v")
    print("=" * 84)
    print(f"n={len(rows)}  benign={int(wb_mask.sum())}  attack={int(wa_mask.sum())}")
    print(f"  means: benign g={g[wb_mask].mean():.3f} v={v[wb_mask].mean():.3f} | "
          f"attack g={g[wa_mask].mean():.3f} v={v[wa_mask].mean():.3f}")
    print(f"\n  POOLED      Spearman rho(g,v) = {pooled:+.3f}   Pearson = {pearsonr(g, v)[0]:+.3f}")
    print(f"  within-benign  rho(g,v)       = {wb:+.3f}   (permutation p = {pval:.4f})")
    print(f"  within-attack  rho(g,v)       = {wa:+.3f}")
    print(f"  rho(g,label)={rgl:+.3f}  rho(v,label)={rvl:+.3f}")
    print(f"  PARTIAL     rho(g,v | label)  = {partial:+.3f}")
    print(f"\n  -> the pooled +{pooled:.2f} is a between-cluster (label-driven) effect: it "
          f"{'vanishes/reverses' if partial < 0.1 else 'persists'} once the label is controlled.")

    os.makedirs(os.path.join("p4", "results", "p2"), exist_ok=True)
    with open(os.path.join("p4", "results", "p2", "p2_2_f1_partials.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["stat", "value"])
        for k, val in (("pooled_spearman", pooled), ("within_benign", wb), ("within_attack", wa),
                       ("partial_given_label", partial), ("perm_p_within_benign", pval)):
            w.writerow([k, round(float(val), 4)])

    ok = pooled >= 0.5 and partial < 0.1
    print("=" * 84)
    print("PASS — the pooled correlation is real but label-driven; the partial/within-cluster "
          "correlations vanish/reverse. Ledger fix: report partials alongside the pooled rho; rephrase "
          "'g tracks the continuous influence magnitude' -> 'g and v both SEPARATE attack from benign'."
          if ok else "REVIEW — partial correlation not as expected; inspect.")
    print("=" * 84)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
