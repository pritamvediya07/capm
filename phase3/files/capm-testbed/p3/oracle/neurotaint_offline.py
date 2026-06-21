"""p3/oracle/neurotaint_offline.py — offline counterfactual influence v(c') (§7d, eval-only).

NeuroTaint-style counterfactual: would the output claim still appear if its source
were removed? We measure it as the drop in the relay model's log-probability of the
claim when the supporting source is ablated from the context:

    v(c') = sigmoid( logP(claim | source present) − logP(claim | source ablated) )

A claim genuinely read from the source loses probability when the source is removed
(high influence); a claim produced from parametric memory does not (low influence).
This is expensive and offline, so it never sits in the live warrant — it VALIDATES
that the cheap runtime g(c') tracks real causal influence (P3-F.1).
"""

from __future__ import annotations

import math
import re


def ablate_source(source_text: str, field: str, value: str | None) -> str:
    """Remove the line(s) of the source that back this claim (the counterfactual)."""
    keep = []
    needle = (value or "").lower()
    for line in source_text.split("\n"):
        low = line.lower()
        if field.replace("_", " ") in low:                 # drop the field's own line
            continue
        if needle and needle in low:                       # and any line stating the value
            continue
        keep.append(line)
    return "\n".join(keep) or "(no context)"


def influence(extractor, source_text: str, field: str, value: str,
              question: str) -> float:
    """v(c') ∈ [0,1] — counterfactual influence of the source on the claim."""
    full = f"{source_text}\nQuestion: {question}\nAnswer:"
    abl = f"{ablate_source(source_text, field, value)}\nQuestion: {question}\nAnswer:"
    lp_full = extractor.answer_logprob(full, f" {value}")
    lp_abl = extractor.answer_logprob(abl, f" {value}")
    return 1.0 / (1.0 + math.exp(-(lp_full - lp_abl)))     # sigmoid of the logprob drop
