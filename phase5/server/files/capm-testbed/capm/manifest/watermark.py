"""Soft-binding **watermark** for relay-fidelity verification (E3.1).

A relay that claims a faithful transformation (VERBATIM / STRUCTURED_EXTRACTION)
asserts that its output preserves its input's content. A robust way to check that
*without* trusting the relay's self-report is a **perceptual fingerprint**
(watermark) that survives cosmetic edits (whitespace, case, light reordering) but
is destroyed by regeneration. We use a 64-bit **SimHash** (Charikar 2002): the
Hamming distance between two SimHashes is monotone in the token-distribution
distance, so similarity is threshold-comparable — unlike an exact hash, which
flags every byte change (brittle) and so cannot distinguish a reformatted verbatim
copy from a full regeneration.

The receiver-side evaluator compares a segment's watermark to its predecessor's:
a VERBATIM claim whose watermark similarity to its input falls below a threshold
is a transformation lie and is rescored as a GENERATION. This is the
soft-binding / watermark **mismatch detector**.

A real deployment would use a content watermark detector (e.g. SynthID,
Dathathri et al., Nature 2024) or a learned perceptual hash; SimHash is the
dependency-free stand-in with the same interface (fingerprint + similarity).
"""

from __future__ import annotations

import hashlib
import re

_TOK = re.compile(r"[a-z0-9]+")
_BITS = 64
_MASK = (1 << _BITS) - 1


def _shingles(text: str) -> list[str]:
    """Token unigrams + bigrams — captures content and light local order."""
    toks = _TOK.findall(text.lower())
    if not toks:
        return [""]
    grams = list(toks)
    grams += [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
    return grams


def _feature_hash(feature: str) -> int:
    return int.from_bytes(hashlib.sha1(feature.encode()).digest()[:8], "big") & _MASK


def simhash(text: str) -> int:
    """64-bit SimHash of ``text`` (weighted by shingle frequency)."""
    from collections import Counter
    v = [0] * _BITS
    for feature, w in Counter(_shingles(text)).items():
        h = _feature_hash(feature)
        for i in range(_BITS):
            v[i] += w if (h >> i) & 1 else -w
    out = 0
    for i in range(_BITS):
        if v[i] > 0:
            out |= (1 << i)
    return out


def to_hex(h: int) -> str:
    return f"{h:016x}"


def _from_hex(s: str) -> int:
    return int(s, 16)


def fingerprint(text: str) -> str:
    """The watermark stored on a manifest segment (hex SimHash)."""
    return to_hex(simhash(text))


def similarity(a_hex: str, b_hex: str) -> float:
    """1 - normalised Hamming distance between two hex SimHashes, in [0, 1]."""
    try:
        a, b = _from_hex(a_hex), _from_hex(b_hex)
    except (ValueError, TypeError):
        return 0.0
    return 1.0 - (bin((a ^ b) & _MASK).count("1") / _BITS)
