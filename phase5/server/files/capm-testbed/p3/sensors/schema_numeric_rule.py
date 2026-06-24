"""p3/sensors/schema_numeric_rule.py — schema-aware numeric/band comparator (§7c).

Prose NLI does not know that CVSS v3.1 maps a base score of 9.1 to the *Critical*
band — so it scores "9.1" vs "Critical" as *neutral* (confirmed empirically in
P3-C.2's no-rule ablation) and would miss the digit→word severity flip
("9.1"→"low") that is a genuine contradiction. This rule owns structured-field
comparisons by the schema, so:

  * "9.1" → "Critical"  → **entail**     (within-band abstraction, must NOT flag)
  * "9.1" → "low"       → **contradict**  (wrong band — a real downgrade)
  * "9.1" → "2.0"       → **contradict**  (different score)

NLI handles prose; this handles structured fields. The two compose in C.2.
"""

from __future__ import annotations

import re

# CVSS v3.1 qualitative severity bands (inclusive ranges).
_BANDS = [(0.0, 0.0, "none"), (0.1, 3.9, "low"), (4.0, 6.9, "medium"),
          (7.0, 8.9, "high"), (9.0, 10.0, "critical")]
_BAND_WORDS = {b[2] for b in _BANDS}


def band_of(score: float) -> str:
    for lo, hi, name in _BANDS:
        if lo <= score <= hi:
            return name
    return "none" if score <= 0 else "critical"


def parse_score(text: str) -> float | None:
    """First CVSS-plausible number (0.0–10.0) in the text."""
    for m in re.findall(r"\d+(?:\.\d+)?", text):
        v = float(m)
        if 0.0 <= v <= 10.0:
            return v
    return None


def parse_band(text: str) -> str | None:
    t = text.lower()
    for w in ("critical", "high", "medium", "low", "none"):
        if re.search(rf"\b{w}\b", t):
            return w
    return None


def schema_compare(premise: str, hypothesis: str) -> str | None:
    """entail / contradict for a CVSS score↔band|score comparison, or None if the
    rule does not apply (no parseable score in the premise)."""
    score = parse_score(premise)
    if score is None:
        return None
    hb = parse_band(hypothesis)
    if hb is not None:
        return "entail" if band_of(score) == hb else "contradict"
    hn = parse_score(hypothesis)
    if hn is not None:
        return "entail" if abs(score - hn) <= 0.5 else "contradict"
    return None


def applies(premise: str, hypothesis: str) -> bool:
    return schema_compare(premise, hypothesis) is not None
