"""P3-E.1 — Can any sensor inflate warrant above baseline?

The Graded-degrade safety theorem, empirically. For a grid of declared warrants
we drive the sensors adversarially — forced to their max (a fully fooled or
compromised sensor), and malformed (NaN, +inf, >1, <0, negative weights) — and
confirm the realized warrant NEVER exceeds the declared (baseline-CAPM) warrant.
Worst case is exactly baseline CAPM; Phase 3 is never *less* secure.

Run:  python -m p3.exp.e1_clamp_adversary
"""

from __future__ import annotations

import csv
import os

from p3.warrant.realized import realized_warrant

OUT_DIR = os.path.join("p3", "results", "e1")
FIG_DIR = os.path.join("p3", "results", "figures")
W_DECLS = [0.25, 0.40, 0.55, 0.70, 0.85, 1.00]

# (label, kwargs for realized_warrant) — adversarial / malformed sensor drivers
CONDITIONS = [
    ("honest_laundered (faith=0)", dict(u=0.9, s=0.3, faith=0.0, form="min")),
    ("force_u=1",                  dict(u=1.0, s=0.3, faith=0.0, form="min")),
    ("force_s=1",                  dict(u=0.9, s=1.0, faith=0.0, form="min")),
    ("force_faith=1",              dict(u=0.9, s=0.3, faith=1.0, form="min")),
    ("force_ALL=1",                dict(u=1.0, s=1.0, faith=1.0, form="min")),
    ("malformed_NaN",              dict(u=float("nan"), s=float("nan"), faith=float("nan"), form="min")),
    ("malformed_+inf",             dict(u=float("inf"), s=float("inf"), faith=float("inf"), form="min")),
    ("malformed_>1 (2.0)",         dict(u=2.0, s=2.0, faith=2.0, form="min")),
    ("malformed_<0 (-1.0)",        dict(u=-1.0, s=-1.0, faith=-1.0, form="min")),
    ("neg_weights (a=b=c=-1)",     dict(u=0.5, s=0.5, faith=0.5, alpha=-1, beta=-1, gamma=-1, form="product")),
]


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(FIG_DIR, exist_ok=True)
    rows, violations = [], 0
    print("=" * 84)
    print("P3-E.1  Graded-degrade safety: no sensor can inflate warrant above baseline")
    print("=" * 84)
    for w_decl in W_DECLS:
        for label, kw in CONDITIONS:
            try:
                rw = realized_warrant(w_decl, kw["u"], kw["s"], kw["faith"],
                                      alpha=kw.get("alpha", 1.0), beta=kw.get("beta", 1.0),
                                      gamma=kw.get("gamma", 1.0), form=kw.get("form", "min"))
                exceeds = rw.w > rw.w_decl + 1e-9
                g_over1 = rw.g > 1.0 + 1e-9
            except AssertionError as e:        # an invariant violation would land here
                exceeds, g_over1 = True, True
                rw = None
                print(f"  ASSERT FIRED ({label} @ w_decl={w_decl}): {e}")
            violations += int(bool(exceeds))
            rows.append(dict(
                claim_id=f"wd{w_decl:.2f}|{label}", forced_sensor=label, w_decl=w_decl,
                g=round(rw.g, 4) if rw else None, w_real=round(rw.w_real, 4) if rw else None,
                w_final=round(rw.w, 4) if rw else None,
                g_exceeds_1=g_over1, exceeds_decl=bool(exceeds)))

    _write_csv(rows)
    _figure(rows)
    print(f"\ntotal cases: {len(rows)}   cases with w > w_decl (must be 0): {violations}")
    # show the clamp actively lowers warrant in the honest case (not trivially passing)
    honest = [r for r in rows if r["forced_sensor"].startswith("honest")]
    lowered = sum(1 for r in honest if r["w_final"] < r["w_decl"] - 1e-9)
    print(f"sanity — honest laundered claims actually DOWN-graded by the clamp: "
          f"{lowered}/{len(honest)} (clamp lowers when sensors are low; can't raise)")
    print("=" * 84)
    print("PASS — exceeds_decl is False for EVERY case, by construction (the min-clamp). "
          "Worst case (all sensors forced/malformed) = baseline CAPM, never above."
          if violations == 0 else "FAIL — a sensor inflated warrant; clamp is broken.")
    print("=" * 84)
    return 0 if violations == 0 else 2


def _write_csv(rows):
    with open(os.path.join(OUT_DIR, "e1_clamp.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


def _figure(rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        print(f"(figure skipped: {e})"); return ""
    fig, ax = plt.subplots(figsize=(7.6, 6.2))
    ax.plot([0, 1], [0, 1], color="#c0392b", lw=1.5, ls="--",
            label="baseline ceiling  w = w_decl (theorem bound)")
    ax.fill_between([0, 1], [0, 1], [1, 1], color="#c0392b", alpha=0.06)
    ax.text(0.30, 0.86, "FORBIDDEN region (w > w_decl)\n— empty by construction",
            color="#c0392b", fontsize=9)
    markers = {"honest_laundered (faith=0)": ("o", "#2a9d8f", "honest (sensors low → clamp lowers)"),
               "force_ALL=1": ("s", "#2c3e50", "all sensors forced to 1 (fooled)"),
               "malformed_NaN": ("^", "#8e44ad", "malformed (NaN/inf/>1/<0)"),
               "neg_weights (a=b=c=-1)": ("D", "#e67e22", "negative weights")}
    seen = set()
    for r in rows:
        key = r["forced_sensor"]
        style = markers.get(key)
        if key in ("malformed_+inf", "malformed_>1 (2.0)", "malformed_<0 (-1.0)"):
            style = markers["malformed_NaN"]
        if style is None:
            ax.scatter(r["w_decl"], r["w_final"], marker="x", color="#95a5a6", s=30, zorder=3)
            continue
        m, c, lab = style
        ax.scatter(r["w_decl"], r["w_final"], marker=m, color=c, s=70, zorder=4,
                   label=lab if lab not in seen else None, edgecolor="white", linewidth=0.5)
        seen.add(lab)
    ax.set_xlabel("declared warrant w_decl (baseline CAPM)")
    ax.set_ylabel("realized warrant w_final = min(w_decl, g·w_decl)")
    ax.set_xlim(0, 1.02); ax.set_ylim(0, 1.02)
    ax.set_title("P3-E.1 — no sensor (forced/malformed) inflates warrant above baseline\n"
                 "every point on or below the w=w_decl line", fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    fig.tight_layout()
    path = os.path.join(FIG_DIR, "e1_clamp_adversary.png")
    fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path


if __name__ == "__main__":
    raise SystemExit(main())
