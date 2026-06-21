"""p3/data/advisories/transform.py — the transformation generator (Step 0).

Given a structured advisory, produce the relay outputs whose *declared*
transformation is always a benign, faithful-looking label (summary / paraphrase)
while the *realized* content is one of:

  * **faithful_summary**     — every load-bearing claim preserved        (laundered=False)
  * **lossy_summary**        — one or more load-bearing claims DROPPED   (laundered=True, omission)
  * **contradiction_injected** — a load-bearing claim FLIPPED to its opposite (laundered=True, contradiction)
  * **memory_substituted**   — a load-bearing claim replaced by a fabricated value and/or a
                               source-absent claim ADDED from "memory"   (laundered=True, fabrication)

Ground truth is known by construction: every output carries per-claim effect
tags ``∈ {survived, dropped, distorted, added}`` and the list of laundered
load-bearing fields. This is the labelled data Step-0 / P3-A.1 / P3-A.2 consume.

Integrity notes
* The injected contradictions are GENUINE flips (Known↔Unknown ransomware use,
  vendor swap, CWE swap, a clearly different due date) — never a valid
  abstraction. Abstraction-vs-contradiction is exercised separately in P3-C.2.
* All four declared labels (SUMMARY, PARAPHRASE) carry the SAME CAPM fidelity
  penalty (=1), so baseline CAPM assigns them identical warrant. That identity
  is the whole point of A.1 and is a property of the real penalty table
  (capm.core.types), not something this generator arranges.
"""

from __future__ import annotations

import dataclasses
import random

from capm.core.types import TransformationType
from p3.claims.extract import extract_claims, is_load_bearing

# Pools used to manufacture genuine contradictions / fabrications. Values are
# deliberately drawn DISJOINT from a record's real value at generation time.
_VENDOR_POOL = ["Microsoft", "Adobe", "Oracle", "Cisco", "Apple", "Google",
                "Fortinet", "Citrix", "VMware", "SAP", "Atlassian", "Ivanti"]
_PRODUCT_POOL = ["Acrobat Reader", "Exchange Server", "WebLogic", "FortiOS",
                 "vCenter", "Confluence", "Struts", "GlassFish", "ColdFusion"]
_CWE_POOL = ["CWE-79", "CWE-89", "CWE-22", "CWE-352", "CWE-416", "CWE-787",
             "CWE-120", "CWE-502", "CWE-918", "CWE-269"]
_FAKE_PATCH = ["KB5005565", "KB4581309", "KB5012170", "KB5028166", "KB4524570"]


@dataclasses.dataclass
class Transformed:
    record_id: str
    transform_type: str
    declared_transformation: TransformationType
    compression: str                       # light | heavy
    text: str                              # the relayed output content
    laundered: bool                        # ground truth
    effects: list[tuple[str, str]]         # (claim_key, effect)
    laundered_fields: list[str]            # load-bearing fields dropped/distorted/added
    detail: str


def _prose(fields: dict, keys: list[str]) -> str:
    """Render selected fields as a relayed advisory summary paragraph."""
    parts = []
    for k in keys:
        v = fields.get(k)
        if v in (None, ""):
            continue
        parts.append(f"{k.replace('_', ' ')} is {v}")
    body = "; ".join(parts)
    return f"Advisory summary: {body}."


def _all_keys(fields: dict) -> list[str]:
    return [k for k, v in fields.items() if v not in (None, "")]


def _load_bearing_keys(fields: dict) -> list[str]:
    return [k for k in _all_keys(fields) if is_load_bearing(k)]


def _supporting_keys(fields: dict) -> list[str]:
    return [k for k in _all_keys(fields) if not is_load_bearing(k)]


def generate(record: dict, seed: int = 0) -> list[Transformed]:
    """Produce the 4 transformation types × {light, heavy} for one record."""
    rid = record["record_id"]
    fields = dict(record["fields"])
    rng = random.Random(f"{rid}:{seed}")
    present = _all_keys(fields)
    lb = _load_bearing_keys(fields)
    sup = _supporting_keys(fields)
    out: list[Transformed] = []

    for compression in ("light", "heavy"):
        # ---- 1. faithful summary: preserve every load-bearing claim --------
        if compression == "light":
            keep = present
        else:  # heavy: drop only non-load-bearing free text (still faithful)
            keep = lb + [k for k in sup if k not in ("short_description",)]
        effects = [(k, "survived") for k in keep]
        effects += [(k, "dropped") for k in present if k not in keep]  # only supporting
        out.append(Transformed(
            rid, "faithful_summary", TransformationType.SUMMARY, compression,
            _prose(fields, keep), laundered=False, effects=effects,
            laundered_fields=[],
            detail=f"faithful; {len(keep)}/{len(present)} fields kept (only "
                   f"non-load-bearing dropped)"))

        # ---- 2. lossy summary: DROP load-bearing claims (omission) ---------
        n_drop = 1 if compression == "light" else min(3, max(1, len(lb) - 1))
        drop = rng.sample(lb, min(n_drop, len(lb)))
        keep2 = [k for k in present if k not in drop]
        effects = [(k, "survived") for k in keep2] + [(k, "dropped") for k in drop]
        out.append(Transformed(
            rid, "lossy_summary", TransformationType.SUMMARY, compression,
            _prose(fields, keep2), laundered=True, effects=effects,
            laundered_fields=list(drop),
            detail=f"omission: dropped load-bearing {drop}"))

        # ---- 3. contradiction injected: FLIP load-bearing claim(s) ---------
        n_flip = 1 if compression == "light" else 2
        flip = rng.sample(lb, min(n_flip, len(lb)))
        cf = dict(fields)
        for k in flip:
            cf[k] = _contradict(k, str(fields[k]), rng)
        effects = [(k, "distorted" if k in flip else "survived") for k in present]
        out.append(Transformed(
            rid, "contradiction_injected", TransformationType.PARAPHRASE, compression,
            _prose(cf, present), laundered=True, effects=effects,
            laundered_fields=list(flip),
            detail=f"contradiction: flipped {{{', '.join(f'{k}:{fields[k]}->{cf[k]}' for k in flip)}}}"))

        # ---- 4. memory substituted: fabricate / substitute from memory -----
        ff = dict(fields)
        sub = rng.choice([k for k in lb if k in ("product", "cwe", "vendor")] or lb)
        ff[sub] = _fabricate(sub, str(fields[sub]), rng)
        # also ADD a source-absent claim from "memory" (a fabricated patch +
        # a downplaying severity the source never stated)
        added_patch = rng.choice(_FAKE_PATCH)
        eff = [(k, "distorted" if k == sub else "survived") for k in present]
        eff.append(("patch_status", "added"))
        eff.append(("severity", "added"))
        text = (_prose(ff, present)
                + f" A patch ({added_patch}) is already available, so no further "
                  f"action is required. Severity is low.")
        out.append(Transformed(
            rid, "memory_substituted", TransformationType.PARAPHRASE, compression,
            text, laundered=True, effects=eff,
            laundered_fields=[sub, "patch_status(added)", "severity(added)"],
            detail=f"fabrication: substituted {sub} {fields[sub]!r}->{ff[sub]!r}; "
                   f"added fabricated patch={added_patch} + 'severity low' (source had neither)"))

    return out


def _contradict(key: str, value: str, rng: random.Random) -> str:
    """A GENUINE contradiction of a load-bearing field's value."""
    if key == "ransomware_use":
        return "Unknown" if value.strip().lower().startswith("known") else "Known"
    if key == "vendor":
        return rng.choice([v for v in _VENDOR_POOL if v.lower() != value.lower()])
    if key == "cwe":
        return rng.choice([c for c in _CWE_POOL if c.lower() != value.lower()])
    if key == "due_date":
        # shift to a clearly different date (year + 3)
        try:
            y, rest = value.split("-", 1)
            return f"{int(y) + 3}-{rest}"
        except Exception:
            return "1999-01-01"
    if key in ("cvss_score",):
        return "2.0"
    if key == "product":
        return rng.choice([p for p in _PRODUCT_POOL
                           if p.split()[0].lower() not in value.lower()])
    if key == "cve_id":
        return "CVE-1999-0001"        # a genuinely different identifier
    return "the opposite of " + value


def _fabricate(key: str, value: str, rng: random.Random) -> str:
    """A plausible but source-absent (memory-substituted) value."""
    if key == "vendor":
        return rng.choice([v for v in _VENDOR_POOL if v.lower() != value.lower()])
    if key == "cwe":
        return rng.choice([c for c in _CWE_POOL if c.lower() != value.lower()])
    if key == "product":
        return value.split()[0] + " Server 2019" if value else "Server 2019"
    return value + "-x"


if __name__ == "__main__":
    from p3.data.advisories.corpus import load_advisories
    rec = load_advisories(n=1, seed=0)[0]
    print("record:", rec["record_id"])
    for t in generate(rec, seed=0):
        print(f"\n[{t.transform_type}/{t.compression}] declared={t.declared_transformation.value} "
              f"laundered={t.laundered}")
        print("  detail:", t.detail)
        print("  text:", t.text[:160])
