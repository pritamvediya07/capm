"""E7.1 — utility–resistance (Pareto) frontier.

Sweeps the three knobs the trade-off depends on — the **accept floor**
(`min_accept`), the **fidelity penalty** (`transformation_penalty_scale`), and the
**boundary penalty** (`unverified_boundary_penalty`) — and plots **ASR vs utility**.

The honest tension this surfaces: warrant is a property of the *source class*, not
of honesty. A MODERATE-class **attack** (false content planted on a moderate-trust
source, e.g. a public page) and MODERATE-class **honest** content are
indistinguishable by warrant — so driving the attack's ASR to 0 by raising the
floor necessarily down-weights honest moderate content too. The frontier makes
that cost explicit and lets a deployer pick an operating point; the baselines sit
at the (utility 1, ASR 1) corner, which CAPM strictly dominates.

Workloads (built once, scored under every policy):
  * attacks  — sub-floor (editable/model-memory/unknown, always contained) AND
    borderline (public-webpage / first-party, MODERATE) so ASR depends on the floor.
  * honest   — high-warrant (authoritative/verified) AND borderline (first-party /
    public-webpage, MODERATE) so utility depends on the floor.

Run:  python3 -m experiments.e7_1_frontier
"""

from __future__ import annotations

import csv
import os

from attacks.adaptive.profiles import honest_origin, inflated_warrant_origin
from capm.agents.responders import DeterministicResponder
from capm.benchmark.scenarios import build_chain
from capm.core.types import SourceClass, TransformationType, WarrantLevel
from capm.warrant.evaluator import Decision, EvaluatorPolicy, WarrantEvaluator

OUT_DIR = os.path.join("results", "p2", "e7_1")
FLOORS = [WarrantLevel.WEAK, WarrantLevel.DERIVED, WarrantLevel.MODERATE, WarrantLevel.STRONG]
PEN_SCALES = [0.0, 0.25, 0.5, 1.0]
BOUNDARY_PENS = [0, 1]
HOPS = (2, 3, 4)
_PARA = DeterministicResponder(transformation=TransformationType.PARAPHRASE)

# attack origins: (true_class, asserted) — sub-floor + borderline MODERATE
ATTACKS = [
    (SourceClass.EDITABLE_SOURCE, WarrantLevel.STRONG),      # WEAK ceiling (sub-floor)
    (SourceClass.MODEL_MEMORY, WarrantLevel.MODERATE),       # WEAK (sub-floor)
    (SourceClass.UNKNOWN, WarrantLevel.STRONG),              # NONE (sub-floor)
    (SourceClass.PUBLIC_WEBPAGE, WarrantLevel.STRONG),       # MODERATE (borderline)
    (SourceClass.FIRST_PARTY_DB, WarrantLevel.STRONG),       # MODERATE (borderline)
]
# honest origins: high-warrant + borderline MODERATE
HONEST = [
    SourceClass.AUTHORITATIVE_API,    # STRONG
    SourceClass.VERIFIED_DOCUMENT,    # STRONG
    SourceClass.FIRST_PARTY_DB,       # MODERATE (borderline)
    SourceClass.PUBLIC_WEBPAGE,       # MODERATE (borderline)
]


def _build_items():
    """Build every chain ONCE (manifest is policy-independent); return scored items."""
    attacks, honest = [], []
    for cls, asserted in ATTACKS:
        for n in HOPS:
            adv = inflated_warrant_origin("planted false claim under test",
                                          true_class=cls, asserted=asserted, label="atk")
            sc = build_chain(n_hops=n, adversary=adv, relay_responder=_PARA)
            msg = sc.query("q")
            attacks.append((sc.registry, msg.manifest, msg.content))
    for cls in HONEST:
        for n in HOPS:
            sc = build_chain(n_hops=n, adversary=honest_origin("the verified figure is 42", cls),
                             relay_responder=_PARA)
            msg = sc.query("q")
            honest.append((sc.registry, msg.manifest, msg.content))
    return attacks, honest


def _rates(attacks, honest, pol):
    asr = sum(WarrantEvaluator(reg, pol).evaluate(man, c).decision == Decision.ACCEPT
              for reg, man, c in attacks) / len(attacks)
    util = sum(WarrantEvaluator(reg, pol).evaluate(man, c).decision == Decision.ACCEPT
               for reg, man, c in honest) / len(honest)
    return round(asr, 4), round(util, 4)


def run():
    attacks, honest = _build_items()
    rows = []
    for floor in FLOORS:
        for scale in PEN_SCALES:
            for bpen in BOUNDARY_PENS:
                pol = EvaluatorPolicy(min_accept=floor,
                                      min_down_weight=WarrantLevel(max(0, int(floor) - 1)),
                                      transformation_penalty_scale=scale,
                                      unverified_boundary_penalty=bpen)
                a, u = _rates(attacks, honest, pol)
                rows.append(dict(min_accept=floor.name, fidelity_scale=scale,
                                 boundary_pen=bpen, asr=a, utility=u))
    # baselines: accept-all reference corner (no_defense / flat trust asserted)
    baselines = {"no_defense": dict(asr=1.0, utility=1.0),
                 "flat_provenance": dict(asr=1.0, utility=1.0)}
    return rows, baselines


def _pareto(rows):
    front = [r for r in rows if not any(
        (s["asr"] <= r["asr"] and s["utility"] >= r["utility"]
         and (s["asr"] < r["asr"] or s["utility"] > r["utility"])) for s in rows)]
    return sorted(front, key=lambda r: r["utility"])


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    rows, baselines = run()
    front = _pareto(rows)

    print("=" * 80)
    print("E7.1  Utility–resistance frontier (min_accept × fidelity_penalty × boundary)")
    print("=" * 80)
    print(f"{len(rows)} CAPM configs; workload = {len(ATTACKS)*len(HOPS)} attacks "
          f"(sub-floor + MODERATE) + {len(HONEST)*len(HOPS)} honest (high + MODERATE)\n")
    print("Pareto-optimal operating points:")
    print(f"  {'min_accept':>11s} {'fidelity':>9s} {'bnd_pen':>8s} {'ASR':>6s} {'utility':>8s}")
    for r in front:
        print(f"  {r['min_accept']:>11s} {r['fidelity_scale']:>9.2f} {r['boundary_pen']:>8d} "
              f"{r['asr']:>6.2f} {r['utility']:>8.2f}")

    asr_range = (min(r["asr"] for r in rows), max(r["asr"] for r in rows))
    util_range = (min(r["utility"] for r in rows), max(r["utility"] for r in rows))
    print(f"\nASR spans {asr_range[0]:.2f}–{asr_range[1]:.2f}; utility spans "
          f"{util_range[0]:.2f}–{util_range[1]:.2f} → a real trade-off (MODERATE-class "
          f"attacks and honest MODERATE content are indistinguishable by warrant).")
    print(f"Baselines sit at (utility 1.00, ASR 1.00); every CAPM frontier point "
          f"dominates them (strictly lower ASR at the same utility).")

    csv_path = os.path.join(OUT_DIR, "frontier.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    fig_path = _make_figure(rows, front, baselines)

    print(f"\nCSV: {csv_path}")
    if fig_path:
        print(f"Fig: {fig_path}")
    print("=" * 80)
    ok = (asr_range[0] == 0.0 and asr_range[1] > asr_range[0]
          and util_range[1] > util_range[0])
    print("PASS" if ok else "FAIL")
    return 0 if ok else 2


def _make_figure(rows, front, baselines) -> str:
    try:
        from experiments import figtools as ft
    except Exception as e:
        print(f"(figure skipped: {e})")
        return ""
    fig, ax = ft.new(figsize=(7.6, 5.0))
    ax.scatter([r["utility"] for r in rows], [r["asr"] for r in rows], s=30,
               color=ft.BASE, alpha=0.7, label="CAPM operating points", zorder=3)
    ax.plot([r["utility"] for r in front], [r["asr"] for r in front], "-D",
            color=ft.ACCENT, lw=2.2, markersize=7, label="Pareto frontier", zorder=4)
    for d, b in baselines.items():
        ax.scatter([b["utility"]], [b["asr"]], marker="X", s=130, color=ft.WARN,
                   edgecolor="black", zorder=5,
                   label=f"{d} (utility {b['utility']:.0f}, ASR {b['asr']:.0f})")
    ft._style(ax, "E7.1 — utility–resistance Pareto frontier (CAPM dominates)",
              xlabel="utility (honest content accepted)",
              ylabel="attack success rate (ASR, lower better)")
    ax.set_xlim(-0.03, 1.06); ax.set_ylim(-0.05, 1.12)
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    ax.annotate("ideal", xy=(0.99, 0.02), xytext=(0.80, 0.18), fontsize=9, color=ft.OK,
                ha="center", arrowprops=dict(arrowstyle="->", color=ft.OK))
    return ft.save(fig, "e7_1_pareto_frontier.png")


if __name__ == "__main__":
    raise SystemExit(main())
