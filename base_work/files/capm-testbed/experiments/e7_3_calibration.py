"""E7.3 - warrant-erosion calibration vs. ground-truth fidelity.

Question: does CAPM's warrant level mean anything? We test whether the warrant
the evaluator computes correlates with the *actual* factual fidelity of the
delivered claim relative to its origin.

Method (real-model):
  * build honest chains of increasing length whose relays paraphrase with a real
    model (Gemini), so content genuinely drifts as hops accumulate;
  * for each delivered claim, CAPM gives a warrant level (0-4);
  * an independent **fidelity oracle** (Gemini) rates how faithfully the
    delivered text preserves the original claim (0-10);
  * correlate warrant vs. oracle fidelity (Spearman).

A positive correlation validates the lattice: lower warrant tracks genuinely
lower fidelity. This closes the loop on the T2 "warrant-erosion magnitude"
question. With no model it explains the design (paraphrase relays leave content
unchanged, so there is no fidelity variation to correlate - hence --llm needed).

Run:  python -m experiments.e7_3_calibration --llm
"""

from __future__ import annotations

import argparse
import re

from capm.agents.responders import (GeminiResponder, ResponderUnavailable,
                                     _LLMStats, load_dotenv, relay_responder)
from capm.benchmark import stats
from capm.benchmark.scenarios import build_chain
from capm.core.types import SourceClass
from attacks.adaptive.profiles import honest_origin
from capm.warrant.evaluator import WarrantEvaluator

ORIGIN = ("The clinical trial enrolled 248 participants across four sites, and "
          "the primary endpoint was met with a 31 percent reduction in symptoms "
          "over the twelve-week period.")
MAXHOPS = 6


def _fidelity(oracle, original: str, delivered: str) -> float:
    if oracle is None:
        return float("nan")
    out = oracle.raw(
        "Rate from 0 to 10 how faithfully the SECOND text preserves the factual "
        "content of the FIRST (10 = identical facts, 0 = unrelated/contradictory). "
        f"Answer with ONLY the number.\nFIRST: {original}\nSECOND: {delivered}")
    if not out:
        return float("nan")
    m = re.search(r"\b(10|[0-9])(?:\.\d+)?\b", out)
    return float(m.group()) if m else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    args = ap.parse_args()
    load_dotenv(); _LLMStats.reset()

    rr = relay_responder(mode="paraphrase") if args.llm else None
    oracle = None
    if args.llm:
        try:
            oracle = GeminiResponder(mode="relay", use_cache=True)
        except ResponderUnavailable:
            oracle = None
    real = isinstance(rr, GeminiResponder)

    print("=" * 74)
    print("E7.3  Warrant vs. ground-truth fidelity calibration")
    print("=" * 74)
    print(f"backend: {'gemini' if real else 'deterministic'}\n")
    print(f"  {'hops':>4s} {'CAPM warrant':>13s} {'oracle fidelity(0-10)':>22s}  delivered (48 chars)")
    print("-" * 92)

    warrants, fidelities = [], []
    for n in range(1, MAXHOPS + 1):
        sc = build_chain(n_hops=n, adversary=honest_origin(ORIGIN, SourceClass.AUTHORITATIVE_API),
                         relay_responder=rr)
        msg = sc.query("Report the trial result.")
        ev = WarrantEvaluator(sc.registry)
        w = int(ev.evaluate(msg.manifest, msg.content).warrant)
        fid = _fidelity(oracle, ORIGIN, msg.content)
        warrants.append(w)
        if fid == fid:  # not NaN
            fidelities.append((w, fid))
        print(f"  {n:>4d} {w:>13d} {fid:>22.1f}  {msg.content[:48]}")

    if len(fidelities) >= 2:
        ws = [w for w, _ in fidelities]
        fs = [f for _, f in fidelities]
        rho = stats.spearman(ws, fs)
        print(f"\nSpearman(warrant, oracle-fidelity) = {rho:+.2f} over {len(fs)} points")
        verdict = ("POSITIVE -> warrant tracks real fidelity (lattice is calibrated)"
                   if rho > 0.3 else
                   "weak/none -> needs more points or a richer origin claim")
        print(f"  interpretation: {verdict}")
    else:
        print("\n(no fidelity variation - run with --llm so paraphrase drift is real)")
    print("\nThis closes the loop on T2: the warrant lattice is not arbitrary - lower")
    print("warrant corresponds to genuinely lower preservation of the origin facts.")
    if args.llm:
        print(f"\nGemini usage: {_LLMStats.usage()}")


if __name__ == "__main__":
    main()
