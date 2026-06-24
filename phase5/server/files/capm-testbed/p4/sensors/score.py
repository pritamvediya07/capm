"""p4/sensors/score.py — the CORRECTED per-claim scorer (WS1 / P4-1A, root fix).

This is the single root fix for BOTH D.1 (calibration leakage, HIGH) and E.4
(oracle-premise nit, LOW). In Phase-3 `p3/sensors/score.py:54` the faith sensor's
NLI premise was a *synthesized* sentence built from the label's defining quantity:

    premise = "The {field} is {true_value}."          # <-- D.1 leakage

so `faith` was a near-deterministic function of `value == true_value`, which is
exactly the trust label. Here the premise is the **rendered source document
`ctx`** — faith is measured against the real source, never the label:

    faith = NLI(premise = ctx, hypothesis = "{field} is {value}")

`leaked_premise=True` reproduces the Phase-3 behaviour for the controlled A/B in
`p1a_calibration_fixed.py`; the default (`False`) is the corrected, ctx-grounded
path. `u` (usage probe) and `s` (support) are unchanged by this fix.
"""

from __future__ import annotations

import csv
import os
import warnings

import numpy as np

warnings.filterwarnings("ignore")

from p3.claims.extract import render_document
from p3.data.advisories.corpus import load_advisories
from p3.sensors.probe import HiddenStateExtractor, UsageProbe
from p3.sensors.probe_data import build_usage_examples, _QUESTIONS
from p3.sensors.support import SupportSensor
from p3.sensors.nli import NLISensor

_FAITH = {"entail": 1.0, "neutral": 0.5, "contradict": 0.0}
PROBE_MODEL, PROBE_LAYER = "distilgpt2", 6
NLI_MODEL = "cross-encoder/nli-deberta-v3-xsmall"
SCORED_CACHE = os.path.join("p4", "results", "scored_claims_fixed.csv")

SOURCE_W = {"AUTHORITATIVE_API": 0.85, "FIRST_PARTY_DB": 0.65,
            "PUBLIC_WEBPAGE": 0.55, "EDITABLE_SOURCE": 0.30}
SOURCE_CYCLE = list(SOURCE_W)


class ClaimScorer:
    """Loads the three sensors once; scores a claim -> (u, s, faith)."""

    def __init__(self, leaked_premise: bool = False):
        self.leaked_premise = leaked_premise         # True only for the D.1 A/B control
        self.ext = HiddenStateExtractor(PROBE_MODEL)
        y = np.array([e.label for e in build_usage_examples(80, 0)])
        feat = np.load(os.path.join("p3", "results", "b1", "feat_distilgpt2.npz"))["final"]
        self.probe = UsageProbe().fit(feat, y)
        self.support = SupportSensor(space="embedding")
        self.nli = NLISensor(NLI_MODEL)

    def faith_premise(self, source_text: str, field: str, true_value: str | None) -> str:
        """THE FIX. Corrected: premise is the source doc. Leaked: the label quantity."""
        if self.leaked_premise and true_value:
            return f"The {field.replace('_', ' ')} is {true_value}."   # Phase-3 leak (A/B only)
        return source_text                                              # corrected: ctx

    def score(self, source_text: str, field: str, value: str, true_value: str | None):
        q = _QUESTIONS.get(field, f"What is the {field}?")
        pooled, _ = self.ext.claim_features(
            f"{source_text}\nQuestion: {q}\nAnswer:", f" {value}", PROBE_LAYER)
        u = float(self.probe.proba(pooled[None, :])[0])
        claim_text = f"{field.replace('_', ' ')} is {value}"
        s = self.support.support(claim_text, source_text)
        premise = self.faith_premise(source_text, field, true_value)
        faith = _FAITH[self.nli.predict(premise, claim_text)[0]]
        return u, s, faith
