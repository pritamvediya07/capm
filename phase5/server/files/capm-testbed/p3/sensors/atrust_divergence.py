"""p3/sensors/atrust_divergence.py — internal/external divergence detector (§12, AUXILIARY).

An A-Trust-style heuristic, OFF the security floor and explicitly caveated. It
estimates the model's INTERNAL trust in a claim (here: the relay model's
confidence in the conclusion given the premises — a defensible proxy; the raw-
attention variant is contested, see the threats ledger) and compares it to the
EXTERNAL grounding (the verifier-side sensors). A large gap — the model
internally "believes" content the external warrant says is weakly grounded — is
the fingerprint of the "Lying with Truths" attack where every source is real but
narrative coherence manufactured false confidence. Best-effort detector, never a
guarantee.
"""

from __future__ import annotations

import math


def internal_trust(extractor, premises: str, conclusion: str) -> float:
    """Relay-model confidence in the conclusion given the premises ∈ [0,1]
    (proxy for A-Trust's attention-based internal trust; attention variant
    deferred — contested faithfulness)."""
    lp = extractor.answer_logprob(f"{premises}\nConclusion:", f" {conclusion}")
    return 1.0 / (1.0 + math.exp(-(lp + 4.0)))      # squash mean-logprob to [0,1]


def divergence(internal: float, external: float) -> float:
    """internal − external; large positive = believed-but-ungrounded (laundering)."""
    return internal - external
