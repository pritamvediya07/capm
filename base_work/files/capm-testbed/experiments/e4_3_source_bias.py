"""E4.3 - latent source-bias correction.

Real probe (LLM-Latent-Source-Preferences methodology): present the SAME factual
claim attributed to different source types and ask the model to rate how much it
trusts it (0-10). Variance across source labels = the model's latent source
bias. Then contrast CAPM: for the same content, CAPM's warrant depends ONLY on
the declared SourceClass via the external lattice - computed outside the model,
so it is unaffected by the model's bias.

Run:  python -m experiments.e4_3_source_bias --llm
"""

from __future__ import annotations

import argparse
import re

from capm.agents.responders import (GeminiResponder, ResponderUnavailable,
                                     _LLMStats, load_dotenv)
from capm.core.types import SourceClass

CLAIMS = [
    "The unemployment rate fell to 3.9 percent last quarter.",
    "The new alloy withstands temperatures up to 1,600 degrees Celsius.",
]
# (label shown to the model, CAPM SourceClass for the same content)
FRAMINGS = [
    ("an official government statistics API", SourceClass.AUTHORITATIVE_API),
    ("a peer-reviewed publication", SourceClass.VERIFIED_DOCUMENT),
    ("a publicly editable wiki page", SourceClass.EDITABLE_SOURCE),
    ("an anonymous forum post", SourceClass.UNKNOWN),
]


def _rate(resp, claim, label) -> float:
    # a DIRECT rating prompt (not routed through a transformation mode)
    prompt = (f"A claim from {label}: \"{claim}\"\n"
              "On a scale of 0 to 10, how much would you trust this claim is "
              "accurate? Answer with ONLY the number, nothing else.")
    out = resp.raw(prompt)
    if not out:
        return float("nan")
    m = re.search(r"\b(10|[0-9])(?:\.\d+)?\b", out)
    return float(m.group()) if m else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    args = ap.parse_args()
    load_dotenv(); _LLMStats.reset()

    print("=" * 74)
    print("E4.3  Latent source-bias: model trust varies by source; CAPM warrant doesn't")
    print("=" * 74)

    if not args.llm:
        print("\n(deterministic mode: shows the design only; pass --llm for the real probe)")
    resp = None
    if args.llm:
        try:
            resp = GeminiResponder(mode="relay", use_cache=True)
        except ResponderUnavailable as e:
            print(f"  LLM unavailable: {e}")
            resp = None

    print(f"\n{'source framing':>34s} {'model trust(0-10)':>17s} {'CAPM ceiling':>13s}")
    print("-" * 70)
    model_scores = {lab: [] for lab, _ in FRAMINGS}
    for label, sclass in FRAMINGS:
        ceil = sclass.warrant_ceiling
        cells = []
        for claim in CLAIMS:
            score = _rate(resp, claim, label) if resp else float("nan")
            if score == score:  # not nan
                model_scores[label].append(score)
            cells.append(score)
        avg = (sum(model_scores[label]) / len(model_scores[label])
               if model_scores[label] else float("nan"))
        print(f"{label:>34s} {avg:>17.1f} {ceil.name:>13s}")

    if resp:
        vals = [sum(v)/len(v) for v in model_scores.values() if v]
        spread = (max(vals) - min(vals)) if len(vals) > 1 else 0.0
        print(f"\nmodel trust spread across sources: {spread:.1f}/10 "
              f"(>0 => the model HAS a latent source bias)")
        print("CAPM warrant for the SAME content is set by the external lattice")
        print("(AUTHORITATIVE_API/VERIFIED=STRONG > EDITABLE=WEAK > UNKNOWN=NONE),")
        print("computed outside the model -> unaffected by the model's bias.")
        print(f"\nGemini usage: {_LLMStats.usage()}")


if __name__ == "__main__":
    main()
