"""Pure warrant algebra — the relay operations as side-effect-free functions.

This module is the mathematical core of Phase-2 Goal 1. It lifts the scoring
rule implemented imperatively in
:meth:`capm.warrant.evaluator.WarrantEvaluator._score_warrant` into a registry
of **pure functions over the warrant lattice** so that the central claim

    Lemma 1 (Monotonicity).  For every relay operation ``op`` and every tuple of
    input warrants ``w_1 … w_k``:   op(w_1, …, w_k)  ≤  min(w_1, …, w_k).

can be stated precisely and machine-checked by exhaustion (see
``experiments/p2_w1_monotonicity.py``), with **no** dependence on signing,
manifests, or I/O.

Faithfulness to the implementation
----------------------------------
Each operation's *fidelity penalty* is taken from the SAME source the live
evaluator uses — :pyattr:`capm.core.types.TransformationType.fidelity_penalty` —
so the algebra is not a re-derivation but a literal extraction. The empirical
half of P2-W1 cross-checks that the live ``WarrantEvaluator`` agrees with
:func:`evaluate_chain` here on random manifests; any divergence is a real bug,
not a tolerated approximation.

Every operation has the closed form

    op(inputs) = clamp(min(inputs) − penalty)            with penalty ≥ 0

which makes monotonicity hold *by construction*. To guarantee the proof harness
is not vacuous, this module also exposes :data:`NEGATIVE_CONTROLS` — operations
that deliberately *break* monotonicity (e.g. "amplify", "launder-to-max"). The
experiment runs them through the identical assertion and confirms they DO
violate, proving the test has discriminating power.
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Sequence

from capm.core.types import TransformationType, WarrantLevel

# The lattice as plain ints (NONE=0 … STRONG=4). Used by the exhaustive proof.
LATTICE: tuple[int, ...] = tuple(int(w) for w in WarrantLevel)
WMIN, WMAX = min(LATTICE), max(LATTICE)


def clamp(w: int) -> int:
    """Clamp a warrant value back into the lattice [NONE, STRONG]."""
    return max(WMIN, min(WMAX, w))


def _min_in(inputs: Sequence[int]) -> int:
    if not inputs:
        # An operation with no inputs is grounded in nothing → NONE. This mirrors
        # the evaluator's "empty manifest → WarrantLevel.NONE".
        return WMIN
    return min(int(x) for x in inputs)


# ---------------------------------------------------------------------------
# Operation registry
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Operation:
    """One relay operation as a pure function of its input warrants.

    ``fn(inputs) -> int`` returns the output warrant. ``penalty`` is the fidelity
    cost (≥ 0 for every honest operation). ``arity`` is ``1`` for unary
    operations and ``None`` for n-ary (variadic, k ≥ 1) operations. ``monotone``
    records the *intended* property: True for real operations, False for the
    negative controls so the harness can check that it correctly flags them.
    """

    name: str
    fn: Callable[[Sequence[int]], int]
    penalty: int
    arity: int | None          # 1 = unary, None = n-ary
    monotone: bool             # intended invariant: output <= min(inputs)
    description: str

    def __call__(self, inputs: Sequence[int]) -> int:
        return self.fn(inputs)


def _penalty_op(penalty: int) -> Callable[[Sequence[int]], int]:
    """A relay that costs ``penalty`` warrant levels, bounded by its weakest input.

    This single closed form covers every honest operation: the output can never
    exceed the weakest input (``min``), and a non-negative penalty only pushes it
    lower. That is exactly the evaluator's per-segment update
    ``current = max(0, current - transformation.fidelity_penalty)`` generalised
    from a single incoming warrant to a set of inputs (the weakest binds — the
    "composition is bounded by the weakest input" rule from the design doc).
    """
    return lambda inputs: clamp(_min_in(inputs) - penalty)


# Fidelity penalties are pulled directly from TransformationType so the algebra
# stays bolted to the implementation's single source of truth.
_P = {t: t.fidelity_penalty for t in TransformationType}


def _build_registry() -> dict[str, Operation]:
    ops: dict[str, Operation] = {}

    def add(name, penalty, arity, desc):
        ops[name] = Operation(name=name, fn=_penalty_op(penalty), penalty=penalty,
                              arity=arity, monotone=True, description=desc)

    # --- unary transformations (a relay rewrites one incoming value) ---------
    add("verbatim", _P[TransformationType.VERBATIM], 1,
        "exact copy, no semantic change — preserves warrant")
    add("extraction", _P[TransformationType.STRUCTURED_EXTRACTION], 1,
        "pull fields out of structured input — preserves warrant")
    add("summary", _P[TransformationType.SUMMARY], 1,
        "condense one input — loses one level of fidelity")
    add("paraphrase", _P[TransformationType.PARAPHRASE], 1,
        "reword one input — loses one level of fidelity")
    add("generation", _P[TransformationType.GENERATION], 1,
        "produce new content — collapses to NONE unless re-grounded")

    # --- relay/structural operations (no content transform) ------------------
    # Re-signing is a pure Plane-1 act: a relay re-attests the same bytes under
    # its own credential. It establishes *who relayed*, never new *warrant* —
    # penalty 0, output = the input.
    add("re_sign", 0, 1,
        "relay re-signs identical bytes — identity on warrant")
    # Splitting takes a fragment of one input. A part is at most as warranted as
    # the whole, so penalty 0 and the output is bounded by that single input.
    add("split", 0, 1,
        "emit a fragment of one input — bounded by the source")

    # --- n-ary operations (combine multiple incoming values) -----------------
    # Composition derives a new claim from several inputs. Per the design doc the
    # result is "bounded by the weakest input"; the act of composing is itself a
    # derivation, so it carries the composition fidelity penalty.
    add("composition", _P[TransformationType.COMPOSITION], None,
        "combine k inputs into a derived claim — bounded by the weakest, −1")
    # Merge aggregates multiple provenance lines into one manifest without a new
    # semantic claim (e.g. concatenation / set-union of evidence). No derivation
    # penalty, but the merged warrant is still capped by the weakest member.
    add("merge", 0, None,
        "aggregate k manifests — warrant capped by the weakest member")

    return ops


OPERATIONS: dict[str, Operation] = _build_registry()


# ---------------------------------------------------------------------------
# Negative controls — these SHOULD violate monotonicity (harness teeth)
# ---------------------------------------------------------------------------
def _amplify(inputs: Sequence[int]) -> int:
    # Dishonest "confidence boost": raise warrant above the weakest input.
    return clamp(_min_in(inputs) + 1)


def _launder_to_max(inputs: Sequence[int]) -> int:
    # Classic laundering: a composite claims the warrant of its STRONGEST input,
    # discarding the weak provenance it actually also depends on.
    if not inputs:
        return WMIN
    return clamp(max(int(x) for x in inputs))


NEGATIVE_CONTROLS: dict[str, Operation] = {
    "amplify": Operation("amplify", _amplify, penalty=-1, arity=1, monotone=False,
                         description="CONTROL: adds a warrant level (must violate)"),
    "launder_to_max": Operation("launder_to_max", _launder_to_max, penalty=0,
                                arity=None, monotone=False,
                                description="CONTROL: inherits the strongest input "
                                            "(must violate when inputs differ)"),
}


# ---------------------------------------------------------------------------
# Chain folding — mirrors WarrantEvaluator._score_warrant (no-forgery path)
# ---------------------------------------------------------------------------
def origin_warrant(asserted: int, source_ceiling: int) -> int:
    """Origin step: warrant starts at min(asserted, source-class ceiling).

    Mirrors the evaluator's ``min(asserted, ceiling)`` cap that stops a lying
    origin claiming more warrant than its declared class permits.
    """
    return clamp(min(int(asserted), int(source_ceiling)))


def evaluate_chain(asserted: int, source_ceiling: int,
                   relay_ops: Sequence[str]) -> int:
    """Fold a sequence of *named* relay operations over an origin warrant.

    Returns the final warrant. This is the pure-algebra twin of a full
    ``WarrantEvaluator.evaluate`` on an honest (non-forged, truthful-transform)
    manifest whose relays applied ``relay_ops`` in order. Used by P2-W1's
    empirical half to cross-check the live evaluator step-for-step.
    """
    w = origin_warrant(asserted, source_ceiling)
    for name in relay_ops:
        op = OPERATIONS[name]
        # Each relay sees the single running warrant as its only input.
        w = op([w])
    return w


def delta(op: Operation, inputs: Sequence[int]) -> int:
    """output − min(inputs): ≤ 0 iff this application respects monotonicity."""
    return op(inputs) - _min_in(inputs)


def is_monotone_application(op: Operation, inputs: Sequence[int]) -> bool:
    """The Lemma-1 predicate for a single application."""
    return op(inputs) <= _min_in(inputs)
