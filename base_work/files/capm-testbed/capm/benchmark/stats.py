"""Statistical reporting (E9.3) - dependency-free.

For every comparative claim the paper makes (CAPM ASR < baseline ASR, etc.) we
must report more than a point estimate: a significance test, an effect size,
and a confidence interval. This module implements the few tests the experiment
plan calls for using only the standard library, so it runs anywhere:

* :func:`bootstrap_ci` - nonparametric CI for any statistic of a sample.
* :func:`mcnemar` - exact McNemar test for *paired* accept/reject decisions
  (the right test when CAPM and a baseline judge the *same* trials).
* :func:`proportion_ci` - Wilson CI for a single rate (ASR, utility, ...).
* :func:`risk_difference` / :func:`cohens_h` - effect sizes for two rates.

These are intentionally small and readable; swap in scipy/statsmodels if a
reviewer wants the canonical implementations - the call sites are the same.
"""

from __future__ import annotations

import math
import random
from typing import Callable, Sequence


# ---------------------------------------------------------------------------
# Single-rate confidence interval (Wilson score interval)
# ---------------------------------------------------------------------------
def proportion_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% CI for a binomial proportion. Robust at p=0 or p=1."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


# ---------------------------------------------------------------------------
# Bootstrap CI for an arbitrary statistic
# ---------------------------------------------------------------------------
def bootstrap_ci(sample: Sequence[float], stat: Callable[[Sequence[float]], float] = None,
                 *, n_boot: int = 2000, alpha: float = 0.05,
                 seed: int = 0) -> tuple[float, float, float]:
    """Return ``(point, lo, hi)`` for ``stat`` over ``sample`` via the percentile
    bootstrap. Defaults to the mean."""
    if not sample:
        return (0.0, 0.0, 0.0)
    stat = stat or (lambda s: sum(s) / len(s))
    rng = random.Random(seed)
    point = stat(sample)
    n = len(sample)
    boots = []
    for _ in range(n_boot):
        resample = [sample[rng.randrange(n)] for _ in range(n)]
        boots.append(stat(resample))
    boots.sort()
    lo = boots[int((alpha / 2) * n_boot)]
    hi = boots[int((1 - alpha / 2) * n_boot) - 1]
    return (point, lo, hi)


# ---------------------------------------------------------------------------
# Paired test: McNemar (exact, binomial) for two defenses on the same trials
# ---------------------------------------------------------------------------
def mcnemar(a_correct: Sequence[bool], b_correct: Sequence[bool]) -> dict:
    """Exact McNemar test on paired binary outcomes.

    ``a_correct[i]`` / ``b_correct[i]`` are whether defense A / B handled trial
    *i* correctly. Returns discordant counts, the exact two-sided p-value, and
    which side is favoured. Use this for "CAPM beats baseline X" claims.
    """
    if len(a_correct) != len(b_correct):
        raise ValueError("paired samples must be equal length")
    b = sum(1 for x, y in zip(a_correct, b_correct) if x and not y)  # A right, B wrong
    c = sum(1 for x, y in zip(a_correct, b_correct) if not x and y)  # A wrong, B right
    n = b + c
    # exact two-sided binomial p-value with p=0.5
    if n == 0:
        p = 1.0
    else:
        k = min(b, c)
        tail = sum(math.comb(n, i) for i in range(0, k + 1)) * (0.5 ** n)
        p = min(1.0, 2 * tail)
    favours = "A" if b > c else ("B" if c > b else "tie")
    return {"b_only_A_correct": b, "c_only_B_correct": c, "p_value": p,
            "favours": favours, "n_discordant": n}


# ---------------------------------------------------------------------------
# Effect sizes for two rates
# ---------------------------------------------------------------------------
def risk_difference(p1: float, p2: float) -> float:
    """Absolute difference in rates (e.g. ASR_baseline - ASR_capm)."""
    return p1 - p2


def cohens_h(p1: float, p2: float) -> float:
    """Cohen's h effect size for two proportions."""
    phi = lambda p: 2 * math.asin(math.sqrt(min(max(p, 0.0), 1.0)))  # noqa: E731
    return phi(p1) - phi(p2)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Spearman rank correlation (ties handled by average ranks). Pure stdlib.

    Returns a value in [-1, 1]; NaN if either series has zero variance.
    """
    if len(xs) != len(ys) or len(xs) < 2:
        return float("nan")

    def _ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        ranks = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0  # 1-based average rank for the tie group
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks

    rx, ry = _ranks(xs), _ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx == 0 or vy == 0:
        return float("nan")
    return cov / math.sqrt(vx * vy)


def format_rate(successes: int, n: int) -> str:
    """'0.00 [0.00, 0.18]' style string with a Wilson CI."""
    p = (successes / n) if n else 0.0
    lo, hi = proportion_ci(successes, n)
    return f"{p:.2f} [{lo:.2f}, {hi:.2f}]"
