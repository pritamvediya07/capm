"""P2-W4 — Minimality (smallest sufficient core for the monotonicity invariant).

W1–W3 showed *that* CAPM enforces the warrant invariant and *why* it contains
laundering. W4 asks: **which components are actually load-bearing?** It searches
the full power set of the six `EvaluatorPolicy` toggles (2⁶ = 64 subsets), scores
each against the standard relay-laundering adversaries, and identifies the
*minimal secure cores* — subsets that are secure (ASR ≤ 0.1) but become insecure
if any single component is removed.

This is an ablation taken to its logical end: instead of removing one component
at a time, enumerate every combination, so we learn not just "each component
helps" but "here is the irreducible set you cannot do without."

Goal-1 purity: the adversaries are the relay/laundering set the full defense is
meant to contain (`expects_contained=True`); origin-class capture (the Goal-2
residual) is excluded so the minimality result is about the invariant, not the
residual.

Run:
    python3 -m experiments.p2_w4_minimality
"""

from __future__ import annotations

import csv
import itertools
import os

from capm.benchmark.harness import adversary_catalog, run_matrix
from capm.warrant.evaluator import EvaluatorPolicy

OUT_DIR = os.path.join("results", "p2", "w4")
HOPS = (2, 3, 4, 5)
SECURE_ASR = 0.10           # a subset is "secure" if relay ASR ≤ this

# The six toggles, in a fixed bit order. The 'soft_binding' toggle maps onto BOTH
# soft-binding policy fields so that, when on, the check can actually reject (else
# it is inert and could never be load-bearing).
TOGGLES = [
    "enforce_origin_ceiling",
    "apply_transformation_penalty",
    "require_signatures",
    "soft_binding",
    "cross_org_aware",
    "detect_transformation_lies",
]


def _policy_for(subset: frozenset[str]) -> EvaluatorPolicy:
    return EvaluatorPolicy(
        enforce_origin_ceiling="enforce_origin_ceiling" in subset,
        apply_transformation_penalty="apply_transformation_penalty" in subset,
        require_signatures="require_signatures" in subset,
        require_soft_binding="soft_binding" in subset,
        enable_soft_binding_check="soft_binding" in subset,
        cross_org_aware="cross_org_aware" in subset,
        detect_transformation_lies="detect_transformation_lies" in subset,
    )


def _goal1_adversaries() -> list[str]:
    cat = adversary_catalog()
    return [n for n, spec in cat.items() if n != "honest" and spec.expects_contained]


def _eval_subset(subset: frozenset[str], advs: list[str]) -> dict:
    matrix = run_matrix(defenses=["capm"], adversaries=advs, hops=HOPS,
                        include_honest=True, policy=_policy_for(subset))
    m = matrix.metrics("capm")
    return {"asr": m["asr"], "utility": m["utility"]}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    advs = _goal1_adversaries()
    print("=" * 84)
    print("P2-W4 — Minimality: 2^6 power-set search over EvaluatorPolicy toggles")
    print("=" * 84)
    print(f"adversaries ({len(advs)}): {', '.join(advs)}")
    print(f"secure iff relay ASR ≤ {SECURE_ASR}\n")

    # evaluate all 64 subsets
    results: dict[frozenset[str], dict] = {}
    for r in range(len(TOGGLES) + 1):
        for combo in itertools.combinations(TOGGLES, r):
            s = frozenset(combo)
            results[s] = _eval_subset(s, advs)

    secure = {s for s, v in results.items() if v["asr"] <= SECURE_ASR}

    # minimal secure subset: secure, and removing ANY one component → insecure
    def is_minimal(s: frozenset[str]) -> bool:
        if s not in secure:
            return False
        return all((s - {c}) not in secure for c in s)

    minimal = sorted((s for s in secure if is_minimal(s)), key=lambda s: (len(s), sorted(s)))

    # component criticality: in how many minimal cores does each component appear?
    crit = {t: sum(1 for s in minimal if t in s) for t in TOGGLES}

    # ---- console ----
    print(f"secure subsets: {len(secure)} / 64")
    print(f"minimal secure cores: {len(minimal)}")
    smallest = min((len(s) for s in minimal), default=None)
    print(f"smallest secure core size: {smallest}\n")
    print("Minimal secure cores (irreducible — removing any one breaks security):")
    for s in minimal:
        v = results[s]
        print(f"  {{{', '.join(sorted(s))}}}  "
              f"(|{len(s)}|, ASR={v['asr']:.3f}, util={v['utility']:.2f})")
    print("\nComponent presence in minimal cores (criticality):")
    for t in TOGGLES:
        tag = "ESSENTIAL" if crit[t] == len(minimal) and minimal else ""
        print(f"  {t:<32} in {crit[t]}/{len(minimal)} cores  {tag}")

    # ---- CSV: all 64 configs ----
    csv_path = os.path.join(OUT_DIR, "minimality.csv")
    with open(csv_path, "w", newline="") as f:
        fields = (["size"] + TOGGLES + ["asr", "utility", "secure", "minimal"])
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for s in sorted(results, key=lambda s: (len(s), sorted(s))):
            v = results[s]
            row = {"size": len(s)}
            row.update({t: (t in s) for t in TOGGLES})
            row.update({"asr": round(v["asr"], 4), "utility": round(v["utility"], 4),
                        "secure": s in secure, "minimal": is_minimal(s)})
            w.writerow(row)

    # ---- verdict ----
    print("\n" + "=" * 84)
    essential = [t for t in TOGGLES if minimal and crit[t] == len(minimal)]
    print(f"ESSENTIAL components (in every minimal core): {essential}")
    print(f"Smallest sufficient core: size {smallest} "
          f"= {{{', '.join(sorted(minimal[0]))}}}" if minimal else "none")
    ok = len(minimal) >= 1 and smallest is not None and smallest < len(TOGGLES)
    print(f"RESULT: {'PASS — invariant enforced by a strict subset of components' if ok else 'FAIL'}")
    print(f"CSV: {csv_path}")
    print("=" * 84)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
