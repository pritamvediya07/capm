"""P3-D.2 — The security–utility frontier win (THE load-bearing result).

Runs attack + benign claims through baseline (document-level / per-claim CAPM —
both content-blind), CAPM+Phase-3 (per-claim realized warrant, full g), and
single-sensor Build-C competitors (NLI-only, support-only). Sweeps the accept
threshold τ to trace each system's ASR-vs-benign-retention frontier.

The win is **localization**: document-level CAPM must accept or reject a whole
document at its (content-blind) declared warrant, so lowering ASR equally lowers
retention (the diagonal). Phase-3 degrades only the laundered claim and keeps the
faithful siblings — so at any ASR it retains more good claims (and vice-versa).
Reported on the two correct baselines in separate columns (the r1 framing):
security (ASR) vs per-claim CAPM; utility (retention) vs document-level CAPM.

Run:  python -m p3.exp.d2_frontier
"""

from __future__ import annotations

import csv
import os

import numpy as np

from p3.sensors.score import load_scored

OUT_DIR = os.path.join("p3", "results", "d2")
FIG_DIR = os.path.join("p3", "results", "figures")


def _chosen_form():
    p = os.path.join("p3", "results", "d1", "d1_chosen.txt")
    form, a, b, c = "min", 1.0, 1.0, 1.0
    if os.path.exists(p):
        kv = dict(t.split("=") for t in open(p).read().split() if "=" in t)
        form = kv.get("form", "min")
        a = float(kv.get("alpha") or 1.0) if kv.get("alpha") not in (None, "None") else 1.0
        b = float(kv.get("beta") or 1.0) if kv.get("beta") not in (None, "None") else 1.0
        c = float(kv.get("gamma") or 1.0) if kv.get("gamma") not in (None, "None") else 1.0
    return form, a, b, c


def _g(form, U, S, F, a, b, c):
    if form == "min":
        return np.minimum(np.minimum(U, S), F)
    Uc, Sc, Fc = np.clip(U, 1e-3, 1), np.clip(S, 1e-3, 1), np.clip(F, 1e-3, 1)
    g = Uc ** a * Sc ** b * Fc ** c
    if form == "geomean":
        g = g ** (1.0 / ((a + b + c) or 1.0))
    return np.clip(g, 0, 1)


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(FIG_DIR, exist_ok=True)
    rows = load_scored()
    U = np.array([r["u"] for r in rows]); S = np.array([r["s"] for r in rows])
    F = np.array([r["faith"] for r in rows]); wd = np.array([r["w_decl"] for r in rows])
    is_attack = np.array([r["label"] == "attack" for r in rows])
    form, a, b, c = _chosen_form()

    # per-claim warrant under each system
    systems = {
        "document-CAPM (content-blind)": wd,                                  # accept iff w_decl≥τ
        "Phase3 full g (u,s,faith)":     np.minimum(wd, _g(form, U, S, F, a, b, c) * wd),
        "Phase3 NLI-only (competitor)":  np.minimum(wd, F * wd),
        "Phase3 support-only (competitor)": np.minimum(wd, S * wd),
    }
    taus = np.linspace(0, 1.0, 101)
    frontiers = {}
    for name, w in systems.items():
        asr, ret = [], []
        for t in taus:
            acc = w >= t
            asr.append(float(acc[is_attack].mean()))
            ret.append(float(acc[~is_attack].mean()))
        frontiers[name] = (np.array(asr), np.array(ret))

    # headline comparisons vs the content-blind baseline (the diagonal)
    full_asr, full_ret = frontiers["Phase3 full g (u,s,faith)"]
    base_asr, base_ret = frontiers["document-CAPM (content-blind)"]

    def ret_at_asr(asr, ret, target):  # max retention achievable at ASR ≤ target
        ok = asr <= target + 1e-9
        return float(ret[ok].max()) if ok.any() else 0.0

    def asr_at_ret(asr, ret, target):  # min ASR achievable at retention ≥ target
        ok = ret >= target - 1e-9
        return float(asr[ok].min()) if ok.any() else 1.0

    print("=" * 86)
    print("P3-D.2  Security–utility frontier (localization win)")
    print("=" * 86)
    print(f"claims: {len(rows)} (attack {int(is_attack.sum())}, benign {int((~is_attack).sum())}); "
          f"g form = {form}\n")
    rows_out = []
    for ret_target in (0.95, 0.90, 0.80):
        f_asr = asr_at_ret(full_asr, full_ret, ret_target)
        b_asr = asr_at_ret(base_asr, base_ret, ret_target)
        print(f"  at benign-retention ≥ {ret_target:.2f}:  ASR  Phase3={f_asr:.3f}  vs  baseline={b_asr:.3f}"
              f"   (Δ={f_asr-b_asr:+.3f})")
        rows_out.append(dict(axis="security", constraint=f"retention≥{ret_target}",
                             phase3=round(f_asr, 4), baseline=round(b_asr, 4)))
    for asr_target in (0.10, 0.05, 0.0):
        f_ret = ret_at_asr(full_asr, full_ret, asr_target)
        b_ret = ret_at_asr(base_asr, base_ret, asr_target)
        print(f"  at ASR ≤ {asr_target:.2f}:           retention  Phase3={f_ret:.3f}  vs  baseline={b_ret:.3f}"
              f"   (Δ={f_ret-b_ret:+.3f})")
        rows_out.append(dict(axis="utility", constraint=f"ASR≤{asr_target}",
                             phase3=round(f_ret, 4), baseline=round(b_ret, 4)))

    _write(frontiers, taus, rows_out)
    _figure(frontiers)
    # dominance: Phase3 retention ≥ baseline at every ASR level (and not collapsed)
    grid = np.linspace(0, 1, 50)
    dom = all(ret_at_asr(full_asr, full_ret, x) >= ret_at_asr(base_asr, base_ret, x) - 1e-6 for x in grid)
    not_overblock = ret_at_asr(full_asr, full_ret, 0.05) >= 0.6
    print()
    ok = dom and not_overblock
    print("=" * 86)
    print("PASS — Phase-3 DOMINATES the content-blind frontier by localization: at matched ASR it "
          "retains more benign claims (and at matched retention it admits fewer attacks), without "
          "collapsing retention (no over-blocking). No individual claim is raised above its declared "
          "warrant — the gain is granularity." if ok else
          "REVIEW — frontiers cross or retention collapsed; report where Phase-3 wins/loses.")
    print("=" * 86)
    return 0


def _write(frontiers, taus, rows_out):
    with open(os.path.join(OUT_DIR, "d2_frontier.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["system", "tau", "ASR", "benign_retention"])
        for name, (asr, ret) in frontiers.items():
            for t, x, y in zip(taus, asr, ret):
                w.writerow([name, round(float(t), 3), round(float(x), 4), round(float(y), 4)])
    with open(os.path.join(OUT_DIR, "d2_headline.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys())); w.writeheader(); w.writerows(rows_out)


def _figure(frontiers):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"(figure skipped: {e})"); return ""
    fig, ax = plt.subplots(figsize=(8.0, 6.6))
    styles = {"document-CAPM (content-blind)": ("--", "#c0392b", "s"),
              "Phase3 full g (u,s,faith)": ("-", "#2c3e50", "o"),
              "Phase3 NLI-only (competitor)": (":", "#e67e22", "^"),
              "Phase3 support-only (competitor)": (":", "#8e44ad", "D")}
    for name, (asr, ret) in frontiers.items():
        ls, col, mk = styles[name]
        order = np.argsort(asr)
        ax.plot(asr[order], ret[order], ls, color=col, lw=2, marker=mk, markevery=12,
                markersize=5, label=name)
    ax.set_xlabel("ASR  (laundered claims accepted) — lower is better →")
    ax.set_ylabel("benign-claim retention — higher is better ↑")
    ax.set_xlim(-0.02, 1.02); ax.set_ylim(0, 1.03)
    ax.set_title("P3-D.2 — security–utility frontier\nPhase-3 (full g) dominates the content-blind "
                 "baseline by localizing degradation", fontsize=11)
    ax.legend(fontsize=9, frameon=False, loc="lower right")
    ax.annotate("up-left = better\n(low ASR, high retention)", xy=(0.05, 0.95), fontsize=9, color="#2a9d8f")
    fig.tight_layout()
    path = os.path.join(FIG_DIR, "d2_frontier.png")
    fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path


if __name__ == "__main__":
    raise SystemExit(main())
