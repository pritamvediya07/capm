"""Request-budget calculator for the Gemini free tier (~250 requests/day).

Prints, for every experiment, how many model requests a *real* run needs - both
the naive count and the efficient count (with the on-disk cache + building each
chain once per (content, hops) and reusing it across all 5 defenses, since the
LLM content does not depend on which evaluator scores it).

This makes NO API calls. It is a planner so you can fit the suite under 250/day.

Run:  python -m experiments.request_budget
"""

from __future__ import annotations

import dataclasses

# MEASURED reality: gemini-2.5-flash free tier =
# GenerateRequestsPerDayPerProjectPerModel-FreeTier, limit 20/day (NOT 250 -
# that figure is for other models). The responder degrades to a deterministic
# paraphrase when this is hit; CAPM containment is content-independent so the
# ASR is unaffected - only the 'real-model' label on a trial changes.
DAILY_LIMIT = 20


@dataclasses.dataclass
class Prof:
    eid: str
    uses_model: bool
    naive: int            # requests with no cache, rebuild per defense
    efficient: int        # requests with cache + build-once-per-content, 1 model
    note: str


# A trial at n_hops N uses (N-1) relay model calls. Matrix naive =
# defenses(5) x adversaries x sum_{N in hops}(N-1). Efficient = distinct origin
# contents x (max_hops-1), because (a) content is defense-independent and (b)
# temp=0 + cache makes shorter chains prefixes of the longest (cache hits).
PROFILES = [
    # --- experiments that need ZERO model requests (crypto / scoring / stats) ---
    Prof("s0/s1/s2/s3", False, 0, 0, "deterministic responders"),
    Prof("e2_1_soundness", False, 0, 0, "ProVerif model (no model calls)"),
    Prof("e2_3_forgery_battery", False, 0, 0, "manifest tamper cases"),
    Prof("e3_1_lying_transformation", False, 0, 0, "scripted relay (fixed text)"),
    Prof("e3_2_origin_capture", False, 0, 0, "deterministic"),
    Prof("e3_3_manifest_forgery", False, 0, 0, "crypto only"),
    Prof("e3_4_collusion", False, 0, 0, "deterministic"),
    Prof("e6_1/e6_2/e6_3", False, 0, 0, "overhead/size measurement"),
    Prof("e7_1_frontier", False, 0, 0, "policy sweep, deterministic"),
    Prof("e8_ablations", False, 0, 0, "toggle sweep, deterministic"),
    Prof("run_all / validate_against_saga", False, 0, 0, "deterministic"),
    # --- experiments that USE the model when run for real ---
    Prof("e4_1_real_responders --llm", True, 3, 3,
         "1 chain x 4 hops -> 3 relay calls"),
    Prof("e1_1_main_matrix (real)", True, 400, 20,
         "5 def x 8 adv x sum(1+2+3+4); efficient=5 contents x 4 hops"),
    Prof("e1_2_prov_survival (real, lossy)", True, 90, 9,
         "honest chain hops 1..10; efficient=1 content x 9"),
    Prof("e4_2_cross_model (per model)", True, 400, 20,
         "same as E1.1 per model; you have 1 model (gemini) -> x1"),
    Prof("e4_3_source_bias", True, 24, 24,
         "8 source-class variants x 3 queries (no caching benefit)"),
    Prof("e5_1_admit (real)", True, 30, 8,
         "poisoned+honest origins, hops to 3-4"),
    Prof("e5_2_flooding_spread (real)", True, 60, 12,
         "multi-round propagation; efficient with cache"),
    Prof("e5_3_causality (real)", True, 20, 5, "denial-feedback origin"),
    Prof("e1_3_task_efficacy (real)", True, 12, 6,
         "1 task, ~2 agents, few turns"),
    Prof("e7_2_false_positive (real)", True, 54, 18,
         "3 transforms x hops 2..7; efficient=3 x 6"),
    Prof("e7_3_calibration (real)", True, 30, 9,
         "honest chains + oracle (oracle may be non-LLM)"),
]


def main() -> None:
    print("=" * 84)
    print(f"Gemini request budget planner  (free tier ~{DAILY_LIMIT}/day)")
    print("=" * 84)
    print(f"\n{'experiment':34s} {'model?':>7s} {'naive':>7s} {'efficient':>10s}  note")
    print("-" * 84)
    nt = et = 0
    for p in PROFILES:
        nt += p.naive
        et += p.efficient
        flag = "yes" if p.uses_model else "no"
        print(f"{p.eid:34s} {flag:>7s} {p.naive:>7d} {p.efficient:>10d}  {p.note}")
    print("-" * 84)
    print(f"{'TOTAL (all experiments)':34s} {'':>7s} {nt:>7d} {et:>10d}")

    print(f"\nInterpretation (your limit = {DAILY_LIMIT}/day):")
    print(f"  * Zero-model experiments (most of the suite) cost NOTHING - run freely.")
    print(f"  * A full REAL run of every model-backed experiment, done efficiently")
    print(f"    (cache on, build-once-per-content, 1 model), needs ~{et} requests")
    print(f"    -> fits in a single day ({et} < {DAILY_LIMIT}).")
    print(f"  * The same suite run NAIVELY (no cache, rebuild per defense, per model)")
    print(f"    would need ~{nt} requests -> spread over {(-(-nt // DAILY_LIMIT))} days.")
    print(f"\nRecommended plan for a {DAILY_LIMIT}/day model cap:")
    print("  * The on-disk cache means each real call is spent ONCE, ever - a")
    print("    paraphrase generated today is reused free forever.")
    print("  * CAPM's verdict is content-independent (computed from the manifest,")
    print("    not the relay text), so the deterministic full matrix gives the")
    print("    tight statistics and a small real-model sample just confirms transfer.")
    print(f"  Day 1: smoke (~3) + real E1.1 lean (3 attacks x 2 hops, ~8 live) -> ~11")
    print(f"  Day 2: widen E1.1 to 4 hops (~6 new) + E4.1 -> ~8")
    print("  Anything beyond the live cap auto-degrades to a deterministic")
    print("  fallback (reported), so a run never crashes and ASR stays valid.")


if __name__ == "__main__":
    main()
