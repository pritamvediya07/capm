"""p3/warrant/realized.py — realized-warrant computation (the §8–§10 core).

Combines the per-claim effect sensors into a realized warrant that can only ever
*lower* the declared warrant, never raise it:

    g(c')      = combine(u, s, faith)          ∈ [0, 1]   (form decided by P3-D.1)
    w_real     = g · w_decl                     ≤ w_decl
    w          = min(w_decl, w_real)            = w_real   (the safety clamp)

The single most important property — the **Graded-degrade safety theorem** — is
enforced at runtime by hard asserts: `g ≤ 1` and `w ≤ w_decl`, for ANY sensor
values (even adversarial: forced to 1, NaN, out-of-range, negative weights). The
final clamp on `g` is the backstop that makes this hold unconditionally.

Until P3-D.1 calibrates (α, β, γ) and the functional form, the conservative
default is `min(u, s, faith)` (cross-cutting rule). Monotonicity along a lineage
thread is guaranteed by chaining each hop's declared warrant from the previous
hop's *realized* warrant (§10).
"""

from __future__ import annotations

import dataclasses
import math

# Phase-3 warrant thresholds (design-doc §"Concrete experimental parameters")
ACCEPT = 0.7
DOWN_WEIGHT = 0.4


def _clamp01(x, default: float = 1.0) -> float:
    """Map any sensor output to [0,1]; malformed (None/NaN/inf) -> neutral default
    (no boost). A malformed sensor can never inflate warrant (final g-clamp)."""
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


def combine_g(u, s, faith, *, alpha: float = 1.0, beta: float = 1.0,
              gamma: float = 1.0, form: str = "min") -> tuple[float, tuple]:
    """g(c') ∈ [0,1]. Sensors clamped to [0,1]; g clamped to [0,1] as the safety
    backstop (robust to negative weights / malformed inputs)."""
    u_, s_, f_ = _clamp01(u), _clamp01(s), _clamp01(faith)
    if form == "product":
        g = (u_ ** alpha) * (s_ ** beta) * (f_ ** gamma)
    elif form == "geomean":
        wsum = (alpha + beta + gamma) or 1.0
        g = (max(u_, 1e-12) ** alpha * max(s_, 1e-12) ** beta
             * max(f_, 1e-12) ** gamma) ** (1.0 / wsum)
    else:  # "min" — the conservative default until D.1
        g = min(u_, s_, f_)
    g = max(0.0, min(1.0, g))                      # <-- backstop clamp (the theorem)
    return g, (u_, s_, f_)


def realized_warrant(w_decl, u, s, faith, *, alpha=1.0, beta=1.0, gamma=1.0,
                     form: str = "min") -> RealizedWarrant:
    w_decl = max(0.0, min(1.0, float(w_decl)))
    g, (u_, s_, f_) = combine_g(u, s, faith, alpha=alpha, beta=beta, gamma=gamma, form=form)
    w_real = g * w_decl
    w = min(w_decl, w_real)
    # Graded-degrade safety theorem — enforced, not assumed:
    assert g <= 1.0 + 1e-9, f"INVARIANT VIOLATED: g={g} > 1"
    assert w <= w_decl + 1e-9, f"INVARIANT VIOLATED: w={w} > w_decl={w_decl}"
    return RealizedWarrant(w_decl, g, w_real, w, u_, s_, f_, form)


def compose_decl(parent_warrants: list[float]) -> float:
    """Composition over multiple parents is MIN-bounded (a high-warrant sibling
    can NOT lift a low one — §10 / E.2 failure mode)."""
    return min((max(0.0, min(1.0, float(p))) for p in parent_warrants), default=0.0)


@dataclasses.dataclass
class Hop:
    """One step on a lineage thread: the effect sensors + the declared fidelity
    penalty applied to the incoming warrant."""
    u: float = 1.0
    s: float = 1.0
    faith: float = 1.0
    penalty: float = 0.0          # declared-transformation fidelity penalty (lowers w_decl)


def realize_thread(origin_warrant: float, hops: list[Hop], *, form: str = "min",
                   alpha=1.0, beta=1.0, gamma=1.0) -> list[RealizedWarrant]:
    """Realize a per-claim lineage thread. Each hop's DECLARED warrant chains from
    the PREVIOUS hop's REALIZED warrant minus the penalty — which is exactly what
    makes the realized warrant monotone non-increasing (§10)."""
    out: list[RealizedWarrant] = []
    prev = max(0.0, min(1.0, float(origin_warrant)))
    for h in hops:
        w_decl_k = max(0.0, prev - h.penalty)     # chain from previous REALIZED warrant
        rw = realized_warrant(w_decl_k, h.u, h.s, h.faith,
                              alpha=alpha, beta=beta, gamma=gamma, form=form)
        out.append(rw)
        prev = rw.w
    return out
