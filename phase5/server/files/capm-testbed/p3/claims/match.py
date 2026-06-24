"""p3/claims/match.py — rule-based claim matcher / lineage re-deriver (Step 0).

No ML. Given a source record's claims and a relay's delivered TEXT, this
re-derives, per source field, what actually happened to it:

  * **survived**  — the source value is present (field-type-appropriate match);
  * **dropped**   — the field is not present at all;
  * **distorted** — the field is talked about but carries a *different* value;
  * **added**     — the output asserts a field the source never contained.

It also returns, per output claim, a verifier-derived ``verified_parent_id`` —
the source claim it descends from — which is the lineage link the design doc
insists must be **claimed-not-trusted** (re-derived here, never read from an
agent-supplied pointer; §5).

Matching is field-type aware (the design doc's "exact / numeric-tolerant /
entity match"): identifiers normalize prefix/space/case, categoricals use
token-set containment, dates parse multiple formats and compare within a
tolerance window, booleans map synonyms/negation. The single
``numeric_tolerance`` switch toggles tolerant numeric/date comparison so the
A.2 ablation can show it is what fixes cosmetic numeric/date re-rendering.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import re

from p3.claims.extract import Claim, field_type

EFFECTS = ("survived", "dropped", "distorted", "added")

# Field-mention cues: a field is "mentioned" in the output if any cue appears.
# Used to separate distorted (field present, value differs) from dropped.
_FIELD_CUES: dict[str, tuple[str, ...]] = {
    # cues match a clause SUBJECT (the field label), not the value, so identifier
    # cues are the label words ("cve id", "cwe"), not the digit pattern.
    "cve_id": ("cve id", "cve"),
    "vendor": ("vendor",),
    "product": ("product",),
    "vulnerability_name": ("vulnerability name", "moniker"),
    "cwe": ("cwe",),
    "cvss_score": ("cvss", "base score", "severity score"),
    "cvss_band": ("severity band",),
    "date_added": ("date added",),
    "due_date": ("due date", "remediate by"),
    "ransomware_use": ("ransomware",),
    "required_action": ("required action", "apply updates", "remediation"),
    "short_description": ("description",),
    # source-absent fields a laundering relay may fabricate -> "added"
    "patch_status": ("patch", r"kb\d{4,}", "no further action", "no action"),
    "severity": ("severity",),
}
_EXTRA_FIELDS = ("patch_status", "severity")   # not in any source record


@dataclasses.dataclass
class MatchConfig:
    numeric_tolerance: bool = True     # tolerant numeric/date matching (the ablation knob)
    date_tol_days: int = 7             # cosmetic-reformat tolerance window
    numeric_tol: float = 0.05          # absolute tolerance for numeric values
    text_overlap: float = 0.6          # token-overlap ratio for free-text survival


@dataclasses.dataclass
class ClaimEffect:
    claim_id: str
    field_key: str
    field_type: str
    effect: str                        # one of EFFECTS
    verified_parent_id: str | None     # re-derived lineage (None for 'added')


# --------------------------------------------------------------------------- #
# normalization helpers
# --------------------------------------------------------------------------- #
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if len(t) > 1}


def _norm_id(s: str) -> str:
    """CVE/CWE id canonical form: 'CWE 665'|'cwe-665'|'665'(+cue) -> 'CWE-665'."""
    s = s.upper().replace(" ", "")
    s = re.sub(r"(CVE|CWE)-?", r"\1-", s)
    return s


_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%d %B %Y",
                 "%b %d, %Y", "%B %d, %Y", "%m/%d/%Y")
_DATE_RE = re.compile(
    r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}"
    r"|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}"
    r"|[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})\b")


def _parse_date(s: str):
    s = s.strip()
    for fmt in _DATE_FORMATS:
        try:
            return _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _bool_polarity(value: str) -> bool | None:
    v = _norm(value)
    if any(w in v for w in ("known", "yes", "true", "confirmed", "in use")):
        if "unknown" in v or "not known" in v:
            return False
        return True
    if any(w in v for w in ("unknown", "no ", "none", "false", "not ")):
        return False
    return None


# --------------------------------------------------------------------------- #
# field-type value presence
# --------------------------------------------------------------------------- #
def _field_mentioned(field_key: str, text: str) -> bool:
    t = _norm(text)
    return any(re.search(cue, t) for cue in _FIELD_CUES.get(field_key, ()))


def _clauses(text: str) -> list[str]:
    """Rough clause segmentation of a structured-advisory relay message."""
    return [p.strip() for p in re.split(r"[;.\n]", text) if p.strip()]


def _parse_clause(clause: str) -> tuple[str | None, str]:
    """Identify which field a clause ASSERTS from its subject, + the value phrase.

    Structured advisory text is ``<field label> is/:  <value>``. Keying off the
    *subject* (left of the first ``is``/``:``) — not any word anywhere in the
    clause — is what stops ``required action is Apply updates per vendor
    instructions`` from being mistaken for a *vendor* assertion.
    """
    # split on the copula ` is `, not ':' — the latter appears in the
    # "Advisory summary:" preamble and would hijack the first field's subject.
    m = re.split(r"\bis\b", clause, maxsplit=1)
    subj, val = (m[0], m[1]) if len(m) == 2 else (clause, clause)
    subj_n = _norm(subj)
    for key, cues in _FIELD_CUES.items():
        if any(re.search(cue, subj_n) for cue in cues):
            return key, val.strip()
    return None, clause


def _value_present(field_type_: str, value: str, text: str, cfg: MatchConfig) -> bool:
    t_norm = _norm(text)
    if field_type_ == "identifier":
        ids = {_norm_id(m) for m in re.findall(r"\b(?:cve|cwe)[-\s]?\d+(?:[-\s]?\d+)?\b", t_norm)}
        return _norm_id(value) in ids

    if field_type_ == "date":
        if not cfg.numeric_tolerance:
            return value.strip() in text          # exact string only
        src = _parse_date(value)
        if src is None:
            return value.strip() in text
        for m in _DATE_RE.findall(text):
            d = _parse_date(m)
            if d and abs((d - src).days) <= cfg.date_tol_days:
                return True
        return False

    if field_type_ == "numeric":
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text)]
        try:
            sv = float(re.findall(r"\d+(?:\.\d+)?", value)[0])
        except (IndexError, ValueError):
            return False
        if not cfg.numeric_tolerance:
            return any(x == sv for x in nums)      # exact
        return any(abs(x - sv) <= cfg.numeric_tol for x in nums)

    if field_type_ == "boolean":
        # `text` here is the clause's value phrase; compare source vs asserted polarity
        sp, ap = _bool_polarity(value), _bool_polarity(text)
        return sp is not None and sp == ap

    # categorical / text: token-set containment
    src_tok = _tokens(value)
    if not src_tok:
        return False
    txt_tok = _tokens(text)
    overlap = len(src_tok & txt_tok) / len(src_tok)
    thresh = 1.0 if field_type_ == "categorical" else cfg.text_overlap
    return overlap >= thresh


# --------------------------------------------------------------------------- #
# top-level effect tagger
# --------------------------------------------------------------------------- #
def tag_effects(source_claims: list[Claim], output_text: str,
                cfg: MatchConfig | None = None) -> list[ClaimEffect]:
    """Re-derive the per-claim effect taxonomy from delivered text alone."""
    cfg = cfg or MatchConfig()
    effects: list[ClaimEffect] = []
    source_keys = {c.key for c in source_claims}

    # Parse the output into an asserted field->value map by clause SUBJECT, so a
    # field 'survives' only if the clause that actually asserts it carries the
    # value (a value/word reused in another field's clause can't fake survival).
    asserted: dict[str, str] = {}
    for cl in _clauses(output_text):
        key, val = _parse_clause(cl)
        if key is not None:
            asserted.setdefault(key, val)

    for c in source_claims:
        if c.key not in asserted:
            eff = "dropped"
        elif _value_present(c.field_type, c.value, asserted[c.key], cfg):
            eff = "survived"
        else:
            eff = "distorted"
        effects.append(ClaimEffect(c.claim_id, c.key, c.field_type, eff, c.claim_id))

    # added: source-absent fields the output nonetheless asserts
    rid = source_claims[0].source_record_id if source_claims else "?"
    for extra in _EXTRA_FIELDS:
        if extra in asserted and extra not in source_keys:
            effects.append(ClaimEffect(
                claim_id=f"{rid}:{extra}", field_key=extra,
                field_type=field_type(extra), effect="added", verified_parent_id=None))
    return effects


if __name__ == "__main__":
    from p3.claims.extract import extract_claims
    from p3.data.advisories.corpus import load_advisories
    from p3.data.advisories.transform import generate
    rec = load_advisories(n=1, seed=0)[0]
    claims = extract_claims(rec)
    for tr in generate(rec, seed=0)[:4]:
        tags = {e.field_key: e.effect for e in tag_effects(claims, tr.text)}
        print(f"\n[{tr.transform_type}] {tr.detail[:70]}")
        print("  tagger:", tags)
