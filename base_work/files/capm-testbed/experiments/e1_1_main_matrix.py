"""E1.1 - main result matrix: laundering containment vs. baselines, with stats.

Runs every defense against the weak (non-adaptive) injectors *and* the adaptive
adversaries, across hop counts, then reports each metric with a Wilson CI and a
paired McNemar test of CAPM vs. each baseline (E9.3). Origin-capture (E3.2) is
reported separately because it is the *honest boundary* of the claim, not a
containment failure.

Run:  python -m experiments.e1_1_main_matrix
"""

from __future__ import annotations

import argparse

from capm.benchmark import stats
from capm.benchmark.harness import (DEFENSES, paired_significance, run_matrix)
from capm.benchmark.runner import asr, down_weight_rate, mean_latency, utility

# adversaries CAPM is expected to *contain* (warrant-catchable)
CATCHABLE = ["admit", "flooding_spread", "causality_laundering",
             "lying_transformation", "manifest_forgery_fake_sig",
             "manifest_forgery_replay", "collusion"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true",
                    help="use the real Gemini backend for relay content (efficient)")
    args = ap.parse_args()

    print("=" * 78)
    print("E1.1  Main result: laundering containment vs. baselines (+ stats)")
    print("=" * 78)

    relay_responder = None
    adversaries, hops = CATCHABLE, (2, 3, 4, 5)
    if args.llm:
        from capm.agents.responders import GeminiResponder, _LLMStats, load_dotenv
        load_dotenv(); _LLMStats.reset()
        relay_responder = GeminiResponder(mode="paraphrase")
        # under a real model + free-tier rate limit, focus the spend on the
        # content-based laundering attacks (the ones the model actually shapes);
        # the crypto adversaries (forgery/collusion/lying) are proven in E3.x.
        # 3 attacks x 4 hops = 12 malicious trials -> McNemar p ~ 5e-4.
        adversaries = ["admit", "flooding_spread", "causality_laundering"]
        hops = (2, 3, 4, 5)
        print(f"backend: real Gemini ({relay_responder.model}), paced for free "
              f"tier, build-once-per-content + cache")
        print(f"adversaries={adversaries} hops={hops}\n")

    m = run_matrix(adversaries=adversaries, hops=hops,
                   relay_responder=relay_responder)

    print(f"\n{'defense':22s} {'ASR [95% CI]':>22s} {'down-wt':>8s} {'utility':>8s} {'lat(ms)':>8s}")
    print("-" * 78)
    for d in DEFENSES:
        rs = m.rows[d]
        mal = [r for r in rs if r.expected_malicious]
        succ = sum(r.attack_succeeded for r in mal)
        print(f"{d:22s} {stats.format_rate(succ, len(mal)):>22s} "
              f"{down_weight_rate(rs):>8.2f} {utility(rs):>8.2f} {mean_latency(rs):>8.3f}")

    print("\nPaired McNemar: CAPM vs each baseline on the SAME adversarial trials")
    for d in DEFENSES:
        if d == "capm":
            continue
        res = paired_significance(m, "capm", d)
        print(f"  capm vs {d:22s} favours={res['favours']:4s} "
              f"p={res['p_value']:.2e}  (CAPM-correct-only={res['b_only_A_correct']}, "
              f"baseline-correct-only={res['c_only_B_correct']})")

    print("\nHonest boundary (E3.2) - reported separately, NOT a containment metric:")
    oc = run_matrix(adversaries=["origin_capture"], include_honest=False,
                    hops=hops, relay_responder=relay_responder)
    rs = oc.rows["capm"]
    print(f"  origin_capture: CAPM ASR={asr(rs):.2f} (expected > 0 - class lie is "
          f"out of scope) but attribution_works={all(r.attribution_works for r in rs)} "
          f"-> revocable. See E3.2 for the full honest-limitation write-up.")

    if args.llm:
        from capm.agents.responders import _LLMStats
        print(f"\nGemini usage this run: {_LLMStats.requests} live requests, "
              f"{_LLMStats.cache_hits} cache hits, {_LLMStats.fallbacks} "
              f"deterministic fallbacks (daily free-tier cap for gemini-2.5-flash "
              f"is 20 req/day).")
        if _LLMStats.fallbacks:
            print("  note: fallbacks use a deterministic paraphrase when the daily "
                  "quota is hit. CAPM's verdict is computed from the manifest, not "
                  "the relay text, so containment (ASR) is identical either way; "
                  "only the 'is the content real-model' label changes.")


if __name__ == "__main__":
    main()
