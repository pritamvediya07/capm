"""p3/claims/extract.py — claim extractor for structured sources (Step 0).

A *claim* is one atomic unit of content. For structured inputs (CVE advisory,
API response, DB record) each field becomes exactly one :class:`Claim`. This is
the data structure every later Phase-3 step writes into: lineage links, effect
tags, and per-claim warrants all key off ``claim_id``.

Design doc §5: "The CVE advisory {vendor, severity, patch, affected} is four
claims, not one document." This module makes that literal.
"""

from __future__ import annotations

import dataclasses
from typing import Any


# field_type drives the matcher's comparison rule (numeric tolerance, exact id,
# entity match, boolean flip, date) and the schema-aware NLI rule later.
_FIELD_TYPE = {
    "cve_id": "identifier",
    "vendor": "categorical",
    "product": "categorical",
    "vulnerability_name": "text",
    "cwe": "identifier",
    "cvss_score": "numeric",
    "cvss_band": "categorical",
    "date_added": "date",
    "due_date": "date",
    "ransomware_use": "boolean",
    "required_action": "text",
    "short_description": "text",
}

# Which fields are *load-bearing* — a recipient would act on them, so dropping or
# contradicting one is a high-stakes laundering event. Supporting fields (free
# text) still matter but their loss is evidence-loss, not a wrong-action risk.
_LOAD_BEARING = {
    "cve_id", "vendor", "product", "cwe", "cvss_score", "cvss_band",
    "ransomware_use", "due_date",
}


@dataclasses.dataclass(frozen=True)
class Claim:
    """One atomic structured claim (one field of one record)."""

    claim_id: str            # f"{source_record_id}:{key}"
    key: str
    value: str
    source_record_id: str
    field_type: str          # identifier|categorical|numeric|date|boolean|text
    load_bearing: bool

    def as_text(self) -> str:
        """Human-readable rendering used by NLI / embedding sensors later."""
        return f"{self.key.replace('_', ' ')}: {self.value}"


def field_type(key: str) -> str:
    return _FIELD_TYPE.get(key, "text")


def is_load_bearing(key: str) -> bool:
    return key in _LOAD_BEARING


def extract_claims(record: dict[str, Any]) -> list[Claim]:
    """Structured record -> one Claim per non-empty field.

    ``record`` must have ``record_id`` and a ``fields`` mapping (key -> value).
    """
    rid = record["record_id"]
    claims: list[Claim] = []
    for key, value in record["fields"].items():
        if value is None or value == "":
            continue
        claims.append(Claim(
            claim_id=f"{rid}:{key}",
            key=key,
            value=str(value),
            source_record_id=rid,
            field_type=field_type(key),
            load_bearing=is_load_bearing(key),
        ))
    return claims


def render_document(record: dict[str, Any]) -> str:
    """Render a structured record as the canonical 'source document' text."""
    lines = [f"{k.replace('_', ' ')}: {v}" for k, v in record["fields"].items()
             if v not in (None, "")]
    return "\n".join(lines)
