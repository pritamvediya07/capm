"""P2-W5 — Generality beyond CAPM's specific encoding.

W1–W4 established the monotonicity invariant and its minimal core in the
canonical 5-level lattice. W5 asks whether that lattice is *load-bearing* or
incidental: it re-runs the relay-laundering adversaries through the SAME pipeline
but swaps the warrant algebra for a family of pluggable
`capm.warrant.models.WarrantModel`s —

  * `LatticeModel` at heights 3, 5 (canonical), 7, 10,
  * `ContinuousModel` with linear / convex / concave decay on [0,1],
  * `NonMonotoneModel` — a control that *adds* warrant per hop.

Hypothesis: **every monotone model contains the attacks (ASR ≤ 0.1); the
non-monotone control leaks.** If so, containment is a property of the *algebraic
structure* (monotonicity), not of the 5-level encoding.

Signature checks and transformation-lie detection are held constant across all
models, so the only variable is the warrant arithmetic.

Run:
    python3 -m experiments.p2_w5_generality
"""

from __future__ import annotations

import csv
import os

from attacks.adaptive.profiles import AdversaryProfile
from capm.benchmark import stats
from capm.benchmark.harness import adversary_catalog, collusion_spec
from capm.benchmark.scenarios import build_chain
from capm.warrant.evaluator import EvaluatorPolicy
from capm.warrant.models import ModelEvaluator, default_models

OUT_DIR = os.path.join("results", "p2", "w5")
HOPS = (2, 3, 4, 5)
SECURE_ASR = 0.10

# The laundering adversaries whose containment depends on the WARRANT ALGEBRA
# (not on signatures). Forgeries are rejected by the signature layer in every
# model alike, so they are reported separately as a constant, not mixed in.
LAUNDERING = ["admit", "flooding_spread", "causality_laundering",
              "lying_transformation", "collusion"]


def _spec_for(name: str, hops: int):
    if name == "collusion":
        return collusion_spec(hops - 1)          # make every relay a colluder
    return adversary_catalog()[name]


def _trial(model, name: str, hops: int) -> dict:
    spec = _spec_for(name, hops)
    scenario = build_chain(n_hops=hops, adversary=spec.origin,
                           relay_adversaries=spec.relays, policy=EvaluatorPolicy())
    msg = scenario.query("what is the value?")
    norm_w, accepted, usable, sig_ok = ModelEvaluator(scenario.registry, model).evaluate(msg.manifest)
    return {"norm_warrant": norm_w, "accepted": accepted, "usable": usable,
            "expected_malicious": scenario.expected_malicious}


def _honest_usable(model, hops: int) -> bool:
    spec = adversary_catalog()["honest"]
    scenario = build_chain(n_hops=hops, adversary=spec.origin, policy=EvaluatorPolicy())
    msg = scenario.query("what is the value?")
    _, accepted, usable, _ = ModelEvaluator(scenario.registry, model).evaluate(msg.manifest)
    return usable


def run() -> dict:
    models = default_models()
    rows = []                       # per (model, adversary, hop)
    summary = []                    # per model
    for model in models:
        succ = trials = 0
        for name in LAUNDERING:
            for h in HOPS:
                t = _trial(model, name, h)
                attack_ok = t["expected_malicious"] and t["accepted"]
                succ += int(attack_ok); trials += 1
                rows.append({"model": model.name, "is_monotone": model.is_monotone,
                             "adversary": name, "hops": h,
                             "norm_warrant": round(t["norm_warrant"], 3),
                             "accepted": t["accepted"], "attack_succeeded": attack_ok})
        # utility: honest content usable across hops
        util = sum(_honest_usable(model, h) for h in HOPS) / len(HOPS)
        asr = succ / trials
        lo, hi = stats.proportion_ci(succ, trials)
        summary.append({"model": model.name, "is_monotone": model.is_monotone,
                        "asr": round(asr, 4), "asr_lo": round(lo, 4),
                        "asr_hi": round(hi, 4), "utility": round(util, 3),
                        "n_trials": trials, "contained": asr <= SECURE_ASR})
    return {"rows": rows, "summary": summary}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 86)
    print("P2-W5 — Generality: monotonicity vs the specific lattice")
    print("=" * 86)
    print(f"laundering adversaries: {', '.join(LAUNDERING)}  (forgeries handled by "
          f"signatures, constant across models)\n")

    R = run()
    print(f"{'model':<22}{'monotone':>10}{'ASR':>8}{'  [95% CI]':>16}"
          f"{'utility':>9}{'contained':>11}")
    print("-" * 86)
    for s in R["summary"]:
        print(f"{s['model']:<22}{str(s['is_monotone']):>10}{s['asr']:>8.3f}"
              f"  [{s['asr_lo']:.2f},{s['asr_hi']:.2f}]{s['utility']:>9.2f}"
              f"{str(s['contained']):>11}")
    print("-" * 86)

    with open(os.path.join(OUT_DIR, "generality_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(R["summary"][0].keys()))
        w.writeheader(); w.writerows(R["summary"])
    with open(os.path.join(OUT_DIR, "generality_trials.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(R["rows"][0].keys()))
        w.writeheader(); w.writerows(R["rows"])

    mono = [s for s in R["summary"] if s["is_monotone"]]
    nonmono = [s for s in R["summary"] if not s["is_monotone"]]
    all_mono_contain = all(s["contained"] for s in mono)
    all_nonmono_leak = all(not s["contained"] for s in nonmono)
    ok = all_mono_contain and all_nonmono_leak and len(mono) >= 4 and len(nonmono) >= 1

    print(f"\nMonotone models contained : {sum(s['contained'] for s in mono)}/{len(mono)} "
          f"(ASR ≤ {SECURE_ASR})")
    print(f"Non-monotone control leaked: {sum(not s['contained'] for s in nonmono)}/{len(nonmono)} "
          f"(ASR {nonmono[0]['asr']:.3f})")
    print(f"RESULT: {'PASS — containment follows from monotonicity, not the 5-level lattice' if ok else 'FAIL'}")
    print(f"CSV: {OUT_DIR}/generality_summary.csv ; {OUT_DIR}/generality_trials.csv")
    print("=" * 86)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
