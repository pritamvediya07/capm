"""p3/sensors/score.py — the unified per-claim sensor scorer (u, s, faith).

Loads the three sensors once (usage probe, support, NLI) and scores a claim,
returning the realized-effect signals the warrant layer consumes. Also builds and
caches a scored claim dataset (real sensors over real advisories, with a spread
of origin source classes → declared warrants) that the Group-D / Group-F
experiments all read, so the expensive forward passes happen once.
"""

from __future__ import annotations

import csv
import os
import warnings

import numpy as np

warnings.filterwarnings("ignore")

from p3.claims.extract import render_document
from p3.data.advisories.corpus import load_advisories
from p3.data.advisories.transform import _VENDOR_POOL, _PRODUCT_POOL, _CWE_POOL, _FAKE_PATCH
from p3.sensors.probe import HiddenStateExtractor, UsageProbe
from p3.sensors.probe_data import build_usage_examples, _QUESTIONS
from p3.sensors.support import SupportSensor
from p3.sensors.nli import NLISensor

_FAITH = {"entail": 1.0, "neutral": 0.5, "contradict": 0.0}
PROBE_MODEL, PROBE_LAYER = "distilgpt2", 6
SCORED_CACHE = os.path.join("p3", "results", "scored_claims.csv")

# origin source class -> declared warrant in [0,1] (Phase-2 ceiling minus a relay
# summary penalty, normalized). Spread so the frontier has operating points.
SOURCE_W = {"AUTHORITATIVE_API": 0.85, "FIRST_PARTY_DB": 0.65,
            "PUBLIC_WEBPAGE": 0.55, "EDITABLE_SOURCE": 0.30}
SOURCE_CYCLE = list(SOURCE_W)


class ClaimScorer:
    def __init__(self):
        self.ext = HiddenStateExtractor(PROBE_MODEL)
        y = np.array([e.label for e in build_usage_examples(80, 0)])
        feat = np.load(os.path.join("p3", "results", "b1", "feat_distilgpt2.npz"))["final"]
        self.probe = UsageProbe().fit(feat, y)
        self.support = SupportSensor(space="embedding")
        self.nli = NLISensor("cross-encoder/nli-deberta-v3-xsmall")

    def score(self, source_text: str, field: str, value: str, true_value: str | None):
        q = _QUESTIONS.get(field, f"What is the {field}?")
        pooled, _ = self.ext.claim_features(f"{source_text}\nQuestion: {q}\nAnswer:", f" {value}", PROBE_LAYER)
        u = float(self.probe.proba(pooled[None, :])[0])
        claim_text = f"{field.replace('_', ' ')} is {value}"
        s = self.support.support(claim_text, source_text)
        premise = f"The {field.replace('_', ' ')} is {true_value}." if true_value else source_text
        faith = _FAITH[self.nli.predict(premise, claim_text)[0]]
        return u, s, faith


def _claim_variants(a, rng):
    """benign + attack (blatant/plausible/added) claims for one advisory."""
    f = a["fields"]
    out = []
    for field in ("vendor", "product", "cwe", "due_date", "ransomware_use"):
        if not f.get(field):
            continue
        true = str(f[field])
        out.append((field, true, true, "benign", "survived", "benign"))
        pool = {"vendor": _VENDOR_POOL, "product": _PRODUCT_POOL, "cwe": _CWE_POOL}.get(field)
        if pool:
            foreign = rng.choice([x for x in pool if x.lower() not in true.lower()])
            out.append((field, foreign, true, "attack", "distorted", "blatant"))
        if field == "due_date":
            try:
                y, m, d = true.split("-")
                out.append((field, f"{y}-{m}-{int(d) % 27 + 1:02d}", true, "attack", "distorted", "plausible"))
            except Exception:
                pass
        elif field == "product":
            out.append((field, f"{true} Server Edition", true, "attack", "distorted", "plausible"))
    out.append(("patch", f"a patch ({rng.choice(_FAKE_PATCH)}) is available", None, "attack", "added", "added"))
    return out


def build_scored_dataset(n_advisories: int = 140, seed: int = 7, force: bool = False) -> list[dict]:
    if os.path.exists(SCORED_CACHE) and not force:
        with open(SCORED_CACHE) as fh:
            return list(csv.DictReader(fh))
    os.makedirs(os.path.dirname(SCORED_CACHE), exist_ok=True)
    import random
    rng = random.Random(seed)
    advs = load_advisories(n=n_advisories, seed=seed)
    scorer = ClaimScorer()
    rows = []
    for i, a in enumerate(advs):
        sc = SOURCE_CYCLE[i % len(SOURCE_CYCLE)]
        w_decl = SOURCE_W[sc]
        ctx = render_document(a)
        for field, value, true, label, effect, attack_class in _claim_variants(a, rng):
            u, s, faith = scorer.score(ctx, field, value, true)
            rows.append(dict(rec=a["record_id"], vendor=a["fields"].get("vendor", "?"),
                             source_class=sc, w_decl=w_decl, field=field, value=value,
                             label=label, effect=effect, attack_class=attack_class,
                             u=round(u, 4), s=round(s, 4), faith=faith,
                             trust=1 if effect == "survived" else 0))
        if (i + 1) % 25 == 0:
            print(f"  scored {i+1}/{len(advs)} advisories ({len(rows)} claims)…", flush=True)
    with open(SCORED_CACHE, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"scored dataset cached: {SCORED_CACHE} ({len(rows)} claims)")
    return rows


def load_scored() -> list[dict]:
    rows = build_scored_dataset()
    for r in rows:                       # coerce numeric strings on cache reload
        for k in ("w_decl", "u", "s", "faith"):
            r[k] = float(r[k])
        r["trust"] = int(r["trust"])
    return rows


if __name__ == "__main__":
    rows = build_scored_dataset(force=True)
    import collections
    print("label:", collections.Counter(r["label"] for r in rows))
    print("attack_class:", collections.Counter(r["attack_class"] for r in rows))
