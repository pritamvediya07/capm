"""P2-W2 — Dose-Response (Figure A).

Goal 1 follow-on to the Monotonicity Lemma. P2-W1 proved the invariant holds
under the *full* defense. P2-W2 asks the dual question: **as we relax the
invariant, does attack success rise in proportion to how much of it we give up?**
A clean monotone dose-response is strong evidence that warrant monotonicity — not
some incidental feature — is what does the containing.

Design
------
1. **Violation magnitude V** — a metric defined *a priori* from the warrant
   algebra, independent of the decision threshold: for a weakened policy P,

       V(P) = mean over malicious trials of  max(0, warrant_P(t) − warrant_full(t))

   i.e. the *expected positive Δwarrant* an attacker gains when P removes a
   constraint, measured against the full defense on the SAME manifests. V is a
   continuous magnitude; it is NOT the attack outcome.

2. **Configurations** — a gradient of `EvaluatorPolicy` settings that dial the
   defense down: scaling the transformation penalty (1.0→0), dropping the
   cross-org term, the origin ceiling, signature checks, and combinations.

3. **ASR** — for each config, run the standard relay-attack benchmark matrix
   (`capm.benchmark.harness.run_matrix`) and read the *behavioural* outcome: the
   fraction of malicious trials ACCEPTED at full strength. ASR is a thresholded
   rate; V is a magnitude — so their relationship is an empirical claim, not an
   identity.

4. **Correlation** — Spearman ρ between V and ASR over the configs. The
   hypothesis (Figure A) predicts ρ > 0.7.

Integrity notes
---------------
* V is computed from warrant inflation, ASR from accept-decisions — different
  quantities, so the correlation is not tautological (a config can inflate
  warrant by Δ<threshold and move ASR not at all).
* **Goal-1 purity:** only adversaries the full defense is *meant* to contain
  (`expects_contained=True`) are included. The origin-class-capture residual
  (Goal 2) is excluded — per the hard rule, the two threat classes are never
  mixed into one curve.
* Whatever ρ emerges is reported as-is; nothing is tuned to clear 0.7.

Run:
    python3 -m experiments.p2_w2_dose_response
"""

from __future__ import annotations

import csv
import dataclasses
import os

from capm.benchmark import stats
from capm.benchmark.harness import adversary_catalog, run_matrix
from capm.benchmark.runner import TrialResult, asr
from capm.warrant.evaluator import EvaluatorPolicy

OUT_DIR = os.path.join("results", "p2", "w2")
HOPS = (2, 3, 4, 5)


@dataclasses.dataclass
class Config:
    name: str
    policy: EvaluatorPolicy
    description: str


def configs() -> list[Config]:
    """A gradient of weakenings, from full defense to all-off.

    Order here is for readability only — V is computed empirically and the
    Spearman test does not assume any ordering.
    """
    return [
        Config("full", EvaluatorPolicy(),
               "full defense (baseline anchor, V≈0)"),
        Config("penalty_x0.75", EvaluatorPolicy(transformation_penalty_scale=0.75),
               "transformation fidelity penalty scaled to 75%"),
        Config("penalty_x0.50", EvaluatorPolicy(transformation_penalty_scale=0.50),
               "transformation fidelity penalty scaled to 50%"),
        Config("penalty_x0.25", EvaluatorPolicy(transformation_penalty_scale=0.25),
               "transformation fidelity penalty scaled to 25%"),
        Config("no_cross_org", EvaluatorPolicy(cross_org_aware=False),
               "org-boundary term removed"),
        Config("no_transform_penalty",
               EvaluatorPolicy(apply_transformation_penalty=False),
               "transformation fidelity penalty removed entirely"),
        Config("no_origin_ceiling", EvaluatorPolicy(enforce_origin_ceiling=False),
               "origin source-class ceiling removed"),
        Config("no_signatures", EvaluatorPolicy(require_signatures=False),
               "manifest signature verification removed"),
        Config("no_ceiling_no_penalty",
               EvaluatorPolicy(enforce_origin_ceiling=False,
                               apply_transformation_penalty=False),
               "ceiling AND transformation penalty removed"),
        Config("all_off",
               EvaluatorPolicy(require_signatures=False, enforce_origin_ceiling=False,
                               apply_transformation_penalty=False,
                               cross_org_aware=False, detect_transformation_lies=False),
               "every CAPM constraint removed"),
    ]


def _goal1_adversaries() -> list[str]:
    """Relay/laundering adversaries the full defense is meant to contain.

    Excludes origin-class capture (expects_contained=False) — that is the Goal-2
    residual and must not be averaged into a Goal-1 curve.
    """
    cat = adversary_catalog()
    return [n for n, spec in cat.items()
            if n != "honest" and spec.expects_contained]


def _malicious(rows: list[TrialResult]) -> list[TrialResult]:
    return [r for r in rows if r.expected_malicious]


def run() -> dict:
    advs = _goal1_adversaries()

    # Reference run under the FULL defense — the warrants V is measured against.
    full_rows = _malicious(run_matrix(defenses=["capm"], adversaries=advs,
                                      hops=HOPS, include_honest=False,
                                      policy=EvaluatorPolicy()).rows["capm"])

    results = []
    for cfg in configs():
        cfg_rows_all = run_matrix(defenses=["capm"], adversaries=advs, hops=HOPS,
                                  include_honest=False,
                                  policy=cfg.policy).rows["capm"]
        cfg_rows = _malicious(cfg_rows_all)

        # pair trial-for-trial with the reference (identical ordering/manifests)
        assert len(cfg_rows) == len(full_rows), "trial ordering mismatch"
        deltas = [max(0, c.warrant - f.warrant) for c, f in zip(cfg_rows, full_rows)]
        V = sum(deltas) / len(deltas) if deltas else 0.0

        n = len(cfg_rows)
        succ = sum(r.attack_succeeded for r in cfg_rows)
        asr_val = asr(cfg_rows)
        lo, hi = stats.proportion_ci(succ, n)

        results.append({
            "config": cfg.name, "description": cfg.description,
            "V": round(V, 4), "asr": round(asr_val, 4),
            "asr_lo": round(lo, 4), "asr_hi": round(hi, 4),
            "n_malicious": n, "n_success": succ,
            # record the policy knobs for provenance
            "require_signatures": cfg.policy.require_signatures,
            "enforce_origin_ceiling": cfg.policy.enforce_origin_ceiling,
            "apply_transformation_penalty": cfg.policy.apply_transformation_penalty,
            "transformation_penalty_scale": cfg.policy.transformation_penalty_scale,
            "cross_org_aware": cfg.policy.cross_org_aware,
            "detect_transformation_lies": cfg.policy.detect_transformation_lies,
        })

    Vs = [r["V"] for r in results]
    ASRs = [r["asr"] for r in results]
    rho = stats.spearman(Vs, ASRs)

    os.makedirs(OUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUT_DIR, "dose_response.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader(); w.writerows(results)

    return {"results": results, "rho": rho, "csv": csv_path,
            "adversaries": advs, "n_configs": len(results)}


def main():
    print("=" * 78)
    print("P2-W2 — Dose-Response: ASR vs invariant-violation magnitude V")
    print("=" * 78)
    R = run()
    print(f"\nGoal-1 adversaries ({len(R['adversaries'])}): {', '.join(R['adversaries'])}")
    print(f"(origin_capture excluded — Goal-2 residual, never averaged in)\n")
    print(f"{'config':<22}{'V':>7}{'ASR':>8}   {'ASR 95% CI':<16}{'n':>5}")
    print("-" * 70)
    for r in R["results"]:
        print(f"{r['config']:<22}{r['V']:>7.3f}{r['asr']:>8.3f}   "
              f"[{r['asr_lo']:.2f}, {r['asr_hi']:.2f}]{'':<6}{r['n_malicious']:>4}")
    print("-" * 70)
    rho = R["rho"]
    print(f"\nSpearman ρ(V, ASR) = {rho:.4f}   (target > 0.7)")
    ok = rho > 0.7
    print(f"RESULT: {'PASS' if ok else 'FAIL'} — dose-response is "
          f"{'strictly positive' if ok else 'NOT above threshold'}")
    print(f"CSV: {R['csv']}")
    print("=" * 78)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
