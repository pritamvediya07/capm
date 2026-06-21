"""Deterministic seeding for reproducible experiments (E9.1).

Every stochastic experiment must take a ``--seed`` and report mean +/- CI over
multiple seeds. This module centralises seed handling so that:

* a single ``seed_everything(seed)`` call makes Python's ``random`` (and
  ``numpy`` if present) deterministic;
* each experiment can derive child seeds from a base seed deterministically
  (so trial *k* under base seed *s* is always the same draw), which is what
  lets us average over seeds without hidden cross-trial coupling.

No third-party requirement: ``numpy`` is seeded only if it is importable.
"""

from __future__ import annotations

import hashlib
import random
from typing import Optional


def seed_everything(seed: int) -> None:
    """Seed all RNGs the testbed may touch."""
    random.seed(seed)
    try:  # pragma: no cover - numpy is optional
        import numpy as _np
        _np.random.seed(seed % (2 ** 32 - 1))
    except Exception:
        pass


def derive_seed(base_seed: int, *labels: object) -> int:
    """Deterministically derive a child seed from a base seed + labels.

    ``derive_seed(7, "admit", 3)`` is stable across runs and independent of the
    order other seeds were drawn, so trials are reproducible in isolation.
    """
    h = hashlib.sha256()
    h.update(str(base_seed).encode())
    for lab in labels:
        h.update(b"\x00")
        h.update(str(lab).encode())
    return int.from_bytes(h.digest()[:8], "big")


def rng_for(base_seed: Optional[int], *labels: object) -> random.Random:
    """Return an isolated ``random.Random`` for one experiment/trial.

    If ``base_seed`` is None the RNG is unseeded (nondeterministic) - used only
    when a caller explicitly wants entropy.
    """
    r = random.Random()
    if base_seed is not None:
        r.seed(derive_seed(base_seed, *labels))
    return r
