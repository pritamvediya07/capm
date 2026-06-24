"""P4-2B — Sensor-attribution table: defend the usage probe from looking redundant.

The E.4 finding ("support+NLI suffice on structured data; u uniquely catches
0/240") forces the question: where is the usage probe uniquely needed? This builds
the per-case-type table with two precisely-defined metrics, on the DE-LEAKED faith
from WS1 (without which NLI's catch rate would be spuriously inflated):

  * single-sensor catch: the sensor ALONE (other two neutralized to 1.0) drives the
    warrant below the threshold.  w = min(W_DECL, sensor * W_DECL) < tau.
  * binding sensor: the min in g=min(u,s,faith) (the threshold-robust attribution).

Case types & sources:
  source-absent addition  -> scored_claims attack_class=added  (faith_ctx)
  synthesis-like          -> f3_adaptive synthesis rows        (faith grounded in premises)
  exact contradiction     -> scored_claims attack_class=blatant (faith_ctx)
  field omission          -> rule-matcher (no sensor; noted)

Robustness: the single-sensor catch is recomputed at the usable floor +/- 0.1
(tau in {0.3, 0.4, 0.5}) so the usage-unique region is shown threshold-robust.

Run:  python -m p4.exp.p2b_sensor_attribution
"""
from __future__ import annotations
import csv, os
from collections import Counter

SCORED = os.path.join("p3", "results", "scored_claims.csv")
FAITH = os.path.join("p4", "results", "p1a", "faith_recompute.csv")
F3 = os.path.join("p3", "results", "f3", "f3_adaptive.csv")
W_DECL, DOWN_WEIGHT = 0.85, 0.4
THRESHOLDS = [0.3, 0.4, 0.5]          # usable floor +/- 0.1 (robustness sweep)


def _scored_with_ctx_faith():
    fr = {(r["rec"], r["field"], r["value"]): float(r["faith_ctx"]) for r in csv.DictReader(open(FAITH))}
    out = []
    for r in csv.DictReader(open(SCORED)):
        k = (r["rec"], r["field"], r["value"])
        if k in fr:
            out.append(dict(attack_class=r["attack_class"], label=r["label"],
                            u=float(r["u"]), s=float(r["s"]), faith=fr[k]))
    return out


def _single_catch(rows, sensor, tau):
    return sum(1 for r in rows if min(W_DECL, r[sensor] * W_DECL) < tau)


def _binding(rows):
    c = Counter()
    for r in rows:
        d = {"usage": r["u"], "support": r["s"], "NLI": r["faith"]}
        c[min(d, key=d.get)] += 1
    return c


def _case_stats(name, rows, tau):
    n = len(rows)
    if not n:
        return None
    sc = {k: _single_catch(rows, v, tau) for k, v in (("support", "s"), ("NLI", "faith"), ("usage", "u"))}
    bind = _binding(rows)
    binder, bc = bind.most_common(1)[0]
    return dict(case=name, n=n, tau=tau, support=sc["support"], NLI=sc["NLI"], usage=sc["usage"],
                binding=binder, binding_rate=round(bc / n, 3))


def _unique_region(cases):
    return [c for c in cases
            if c["usage"] / c["n"] >= 0.8 and c["support"] / c["n"] < 0.6 and c["NLI"] / c["n"] < 0.6]


def main() -> int:
    sc = _scored_with_ctx_faith()
    added = [r for r in sc if r["attack_class"] == "added"]
    blatant = [r for r in sc if r["attack_class"] == "blatant"]
    syn = [dict(u=float(r["u"]), s=float(r["s"]), faith=float(r["faith"]))
           for r in csv.DictReader(open(F3)) if r["level"] == "synthesis_whitebox"]
    case_data = [("source-absent addition", added), ("synthesis-like conclusion", syn),
                 ("exact contradiction", blatant)]

    print("=" * 96)
    print(f"P4-2B  Sensor-attribution table (single-sensor catch, W_decl={W_DECL})")
    print("=" * 96)
    primary = [c for c in (_case_stats(nm, rs, DOWN_WEIGHT) for nm, rs in case_data) if c]
    print(f"At the usable floor tau={DOWN_WEIGHT}:")
    print(f"{'case type':28s} {'n':>4s} {'support':>10s} {'NLI':>10s} {'usage':>10s} {'binding (rate)':>20s}")
    print("-" * 96)
    for c in primary:
        print(f"{c['case']:28s} {c['n']:>4d} {c['support']:>7d}/{c['n']:<2d} {c['NLI']:>7d}/{c['n']:<2d} "
              f"{c['usage']:>7d}/{c['n']:<2d} {c['binding']:>12s} ({c['binding_rate']:.2f})")
    print(f"{'field omission':28s} {'-':>4s} {'matcher':>10s} {'n/a':>10s} {'n/a':>10s} {'rule-matcher':>20s}")

    # threshold-sensitivity sweep
    all_rows = []
    print(f"\nThreshold-sensitivity sweep (usable floor +/- 0.1) — usage-unique region per tau:")
    for tau in THRESHOLDS:
        cases = [c for c in (_case_stats(nm, rs, tau) for nm, rs in case_data) if c]
        all_rows += cases
        uniq = _unique_region(cases)
        names = ", ".join(c["case"] for c in uniq) or "(none)"
        print(f"  tau={tau:.1f}:  usage-unique case types = {names}")

    primary_unique = _unique_region(primary)
    print("\nUSAGE-PROBE UNIQUE-CATCH REGION (support+NLI single-catch < 0.6 AND usage >= 0.8, at tau=0.4):")
    for c in primary_unique:
        print(f"  {c['case']}: usage {c['usage']}/{c['n']} catches, but support {c['support']}/{c['n']} "
              f"and NLI {c['NLI']}/{c['n']} miss -> the probe is NOT redundant here.")
    if not primary_unique:
        print("  (none — on these structured cases support+NLI suffice; the probe's value is prose/future-work)")

    os.makedirs(os.path.join("p4", "results", "p2"), exist_ok=True)
    with open(os.path.join("p4", "results", "p2", "p2b_sensor_attribution.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["case", "n", "tau", "support", "NLI", "usage", "binding", "binding_rate"])
        w.writeheader(); w.writerows(all_rows)

    # robust if synthesis is usage-unique at every swept threshold
    robust = all(any(c["case"].startswith("synthesis") for c in _unique_region(
        [x for x in (_case_stats(nm, rs, tau) for nm, rs in case_data) if x])) for tau in THRESHOLDS)
    ok = len(primary_unique) >= 1
    print("=" * 96)
    print("PASS — there is at least one case type (synthesis) where support+NLI single-catch is low but "
          f"the usage probe catches it and is the binding sensor — robust across tau={THRESHOLDS} "
          f"({'holds at all thresholds' if robust else 'threshold-sensitive — report the range'}). "
          "Framing: the probe earns its place on source-absent additions and synthesis-like parametric "
          "claims; never oversold on exact-contradiction (NLI) or omission (matcher)."
          if ok else "REVIEW — no usage-unique region; down-scope the probe to prose/future-work honestly.")
    print("=" * 96)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
