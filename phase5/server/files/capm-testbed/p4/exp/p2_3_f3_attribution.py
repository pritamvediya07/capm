"""P4-2.3 — F.3 sensor-attribution narration fix (WS2, LOW).

The Phase-3 narration credits "support+usage" for catching the truths-only
synthesis attack. Recomputed from p3/results/f3/f3_adaptive.csv: the usage probe
`u` is the binding `min` sensor in every synthesis row, support would catch fewer
than half on its own, and NLI (faith) catches none. So it is the USAGE PROBE ALONE
that catches synthesis — and "low grounding" mislabels what `u` measures
(context-vs-parametric, not entailment).

Run:  python -m p4.exp.p2_3_f3_attribution
"""
from __future__ import annotations
import csv, os
from collections import Counter

F3 = os.path.join("p3", "results", "f3", "f3_adaptive.csv")
W_DECL = 0.85
ACCEPT, DOWN_WEIGHT = 0.7, 0.4


def main() -> int:
    syn = [r for r in csv.DictReader(open(F3)) if r["level"] == "synthesis_whitebox"]
    n = len(syn)

    def binding(r):
        d = {"u": float(r["u"]), "s": float(r["s"]), "faith": float(r["faith"])}
        return min(d, key=d.get)

    bind = Counter(binding(r) for r in syn)
    mean = {k: sum(float(r[k]) for r in syn) / n for k in ("u", "s", "faith")}

    # single-sensor catch: sensor alone (others=1.0) drives w below threshold; w=min(0.85, sensor*0.85)
    def single_catch(sensor, tau):
        return sum(1 for r in syn if min(W_DECL, float(r[sensor]) * W_DECL) < tau)

    print("=" * 84)
    print("P4-2.3  F.3 — which sensor catches the truths-only synthesis attack?")
    print("=" * 84)
    print(f"synthesis rows: {n}")
    print(f"  mean sensor scores:  u={mean['u']:.3f}   s={mean['s']:.3f}   faith={mean['faith']:.3f}")
    print(f"  BINDING min-sensor counts: {dict(bind)}")
    print(f"\n  single-sensor catch (sensor alone, others=1.0):")
    print(f"{'threshold':>22s} {'usage u':>10s} {'support s':>12s} {'NLI faith':>12s}")
    for tau, name in ((ACCEPT, "accept (<0.7)"), (DOWN_WEIGHT, "down-weight (<0.4)")):
        print(f"{name:>22s} {single_catch('u', tau):>8d}/{n} {single_catch('s', tau):>10d}/{n} "
              f"{single_catch('faith', tau):>10d}/{n}")

    os.makedirs(os.path.join("p4", "results", "p2"), exist_ok=True)
    # per-row detail (Data to record: synthesis_row_id, u, s, faith, binding_sensor, residual)
    with open(os.path.join("p4", "results", "p2", "p2_3_f3_rows.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["synthesis_row_id", "u", "s", "faith", "binding_sensor", "residual_passes_usable"])
        for i, r in enumerate(syn):
            w.writerow([f"{r['rec']}:{i}", r["u"], r["s"], r["faith"], binding(r), r["passes_usable"]])
    with open(os.path.join("p4", "results", "p2", "p2_3_f3_attribution.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["metric", "u", "s", "faith"])
        w.writerow(["mean_score", round(mean['u'], 3), round(mean['s'], 3), round(mean['faith'], 3)])
        w.writerow(["binding_count", bind.get('u', 0), bind.get('s', 0), bind.get('faith', 0)])
        w.writerow(["single_catch_downweight", single_catch('u', DOWN_WEIGHT),
                    single_catch('s', DOWN_WEIGHT), single_catch('faith', DOWN_WEIGHT)])

    ok = (bind.get("u", 0) == n and single_catch("u", DOWN_WEIGHT) > single_catch("s", DOWN_WEIGHT))
    print("=" * 84)
    print(f"PASS — the USAGE PROBE alone catches synthesis (binding in {bind.get('u',0)}/{n}; single-catch "
          f"u={single_catch('u',DOWN_WEIGHT)}/{n} vs support={single_catch('s',DOWN_WEIGHT)}/{n} vs "
          f"faith={single_catch('faith',DOWN_WEIGHT)}/{n} at the usable floor). Ledger fix: credit the "
          "usage probe alone (flags the conclusion as PARAMETRIC); do not credit support; do not call "
          "usage 'grounding'." if ok else "REVIEW — binding/single-catch not as expected; inspect.")
    print("=" * 84)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
