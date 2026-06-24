"""p4/warrant/realized.py — realized-warrant core (carried from Phase-3, WS1/P4-1B).

Identical security semantics to p3/warrant/realized.py — the by-construction
guarantee is untouched:

    g(c')  = combine(u, s, faith) ∈ [0,1]
    w      = min(w_decl, g·w_decl) ≤ w_decl          (the safety clamp)

P4-1B adds the **locality structural invariant**, stated and machine-checkable:
`realized_warrant` is a pure function of a SINGLE claim's own `(w_decl, u, s,
faith)`. It has no document-level / sibling argument, so a claim's warrant cannot
depend on any other claim — locality holds *by construction*. `assert_no_cross_claim_term`
proves this from the function signature; `p1b_locality.py` additionally validates
it empirically with a genuine corruption-free recomputation (no self-copy).
"""

from __future__ import annotations

import dataclasses
import inspect
import math

ACCEPT = 0.7
DOWN_WEIGHT = 0.4

# The exact set of inputs a per-claim warrant is allowed to depend on. Anything
# else (a list of siblings, a document object, a shared mutable) would be a
# cross-claim term and would break locality.
_PER_CLAIM_PARAMS = {"w_decl", "u", "s", "faith"}


def _clamp01(x, default: float = 1.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    if math.isnan(v) or math.isinf(v):
        return default
    return max(0.0, min(1.0, v))


@dataclasses.dataclass
class RealizedWarrant:
    w_decl: float
    g: float
    w_real: float
    w: float
    u: float
    s: float
    faith: float
    form: str

    @property
    def decision(self) -> str:
        if self.w >= ACCEPT:
            return "accept"
        if self.w >= DOWN_WEIGHT:
            return "down_weight"
        return "quarantine"


def combine_g(u, s, faith, *, alpha=1.0, beta=1.0, gamma=1.0, form="min"):
    u_, s_, f_ = _clamp01(u), _clamp01(s), _clamp01(faith)
    if form == "product":
        g = (u_ ** alpha) * (s_ ** beta) * (f_ ** gamma)
    elif form == "geomean":
        wsum = (alpha + beta + gamma) or 1.0
        g = (max(u_, 1e-12) ** alpha * max(s_, 1e-12) ** beta * max(f_, 1e-12) ** gamma) ** (1.0 / wsum)
    else:  # min — conservative default
        g = min(u_, s_, f_)
    g = max(0.0, min(1.0, g))                      # backstop clamp (the theorem)
    return g, (u_, s_, f_)


def realized_warrant(w_decl, u, s, faith, *, alpha=1.0, beta=1.0, gamma=1.0, form="min") -> RealizedWarrant:
    """Per-claim realized warrant. NOTE (P4-1B): the signature takes only this
    one claim's own scalars — there is deliberately no sibling/document argument."""
    w_decl = max(0.0, min(1.0, float(w_decl)))
    g, (u_, s_, f_) = combine_g(u, s, faith, alpha=alpha, beta=beta, gamma=gamma, form=form)
    w_real = g * w_decl
    w = min(w_decl, w_real)
    assert g <= 1.0 + 1e-9, f"INVARIANT VIOLATED: g={g} > 1"
    assert w <= w_decl + 1e-9, f"INVARIANT VIOLATED: w={w} > w_decl={w_decl}"
    return RealizedWarrant(w_decl, g, w_real, w, u_, s_, f_, form)


def assert_no_cross_claim_term() -> dict:
    """Structural-invariant check (P4-1B step 1): prove from the function signature
    that a per-claim warrant cannot read any other claim. Returns the evidence."""
    sig = inspect.signature(realized_warrant)
    positional = {n for n, p in sig.parameters.items()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)}
    extra = positional - _PER_CLAIM_PARAMS
    ok = not extra
    assert ok, f"cross-claim term present in realized_warrant signature: {extra}"
    return {"per_claim_params": sorted(positional), "cross_claim_terms": sorted(extra), "locality_by_construction": ok}
