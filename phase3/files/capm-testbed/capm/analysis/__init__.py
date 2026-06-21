"""Phase-2 analysis layer: the warrant algebra extracted as pure functions.

Phase 1 proved containment empirically. Phase 2 (Goal 1) re-casts that result as
an *algebraic invariant*. :mod:`capm.analysis.operations` lifts the scoring logic
out of :meth:`capm.warrant.evaluator.WarrantEvaluator._score_warrant` into pure,
side-effect-free functions over the warrant lattice, so the Monotonicity Lemma
(Lemma 1) can be stated and machine-checked independent of any I/O, signing, or
manifest plumbing.
"""
