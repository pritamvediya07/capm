"""Stateful origin-class anomaly detector (P2-B6).

Origin-class capture (the unique residual, Theorem 2) usually leaves a trace: an
origin that historically asserted a modest source class suddenly asserts a much
stronger one (e.g. PUBLIC_WEBPAGE → AUTHORITATIVE_API). This detector watches the
per-origin history of asserted source classes and flags such jumps.

It maintains, per agent DID, an exponentially-weighted **baseline** of the
asserted warrant ceiling, and flags an assertion whose ceiling exceeds that
baseline by at least ``jump_threshold``. The baseline then updates toward the new
value, so the detector slowly *learns* a genuinely changed normal — which is
exactly the seam a patient attacker exploits (see B6's gradual-evasion result):
a capture that ramps up slowly keeps every single step under the threshold and is
indistinguishable from a legitimate, gradual reputation increase.

The detector is deliberately simple and online (one EWMA per identity); it is a
*monitor*, not a gate — it raises alerts for triage, it does not change CAPM's
verdict.
"""

from __future__ import annotations

import dataclasses

from capm.core.types import SourceClass


def class_ceiling(source_class: SourceClass) -> float:
    return float(int(source_class.warrant_ceiling))


@dataclasses.dataclass
class OriginAnomalyDetector:
    """Online per-origin class-jump detector.

    Parameters
    ----------
    jump_threshold:
        Flag an assertion whose ceiling exceeds the origin's EWMA baseline by at
        least this many warrant levels. Lower → more sensitive (higher TPR and
        FPR); higher → more permissive.
    alpha:
        EWMA learning rate for the baseline (how fast "normal" adapts).
    """

    jump_threshold: float = 2.0
    alpha: float = 0.4

    def __post_init__(self):
        self._baseline: dict[str, float] = {}
        self._count: dict[str, int] = {}

    def observe(self, did: str, asserted_ceiling: float) -> bool:
        """Process one (origin, asserted-ceiling) assertion. Returns True if it is
        flagged as anomalous. Updates the per-origin baseline."""
        if did not in self._baseline:                 # first sighting establishes normal
            self._baseline[did] = asserted_ceiling
            self._count[did] = 1
            return False
        base = self._baseline[did]
        deviation = asserted_ceiling - base
        flagged = deviation >= self.jump_threshold
        # learn the new normal slowly (this is what gradual evasion abuses)
        self._baseline[did] = self.alpha * asserted_ceiling + (1.0 - self.alpha) * base
        self._count[did] += 1
        return flagged

    def reset(self) -> None:
        self._baseline.clear()
        self._count.clear()
