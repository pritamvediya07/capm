"""Explicit organisational-boundary model for the cross-org benchmark (E5.4).

AgentDojo is a *single trust-domain* benchmark: every tool result is implicitly
trusted once it enters the agent. The design doc's contribution is to make the
**organisational boundary explicit** — to say *which external organisation owns
each piece of content that flows into the user's agent*, and what warrant that
origin's source class permits.

This module supplies that missing layer. Each AgentDojo **injection vector** is a
slot where content from an *external* party lands in the user's trust domain:

  * a biller's invoice text,
  * a memo attached to an incoming transaction from an unknown sender,
  * an external address-change notice,
  * a hotel/restaurant listing, a shared-drive document, an inbound email, a
    Slack message from another workspace, …

Every one of these is content an attacker can influence, crossing from an
external organisation into the user's organisation. We model each as an
:class:`Org` with a :class:`~capm.core.types.SourceClass` (hence a warrant
ceiling). The user's agent lives in a single trusted :class:`Org`
(``trust_domain``). The boundary between an external org and the trust domain is
exactly the Plane-2 boundary CAPM gates and the baselines cannot see across.

Design choice (and its honesty caveat). Every injection vector is assigned a
*non-authoritative* source class (≤ MODERATE), because that is what these slots
really are — published-but-unauthenticated documents (MODERATE), editable
notices/messages (WEAK), or unattributed memos (NONE). The containment result is
therefore **robust to the exact assignment**: an attacker asserting STRONG
warrant is capped at the (≤ MODERATE) ceiling and eroded by relay
transformations, so CAPM down-weights/quarantines it regardless of which of these
three buckets a vector falls in. The *interesting* case — an attacker who gets a
vector classified AUTHORITATIVE (origin capture) — is the separate residual
(E3.2/B-series), surfaced by the benchmark's negative control, not hidden by the
class assignment here.
"""

from __future__ import annotations

import dataclasses

from capm.core.types import SourceClass

# The user's agent trust domain (the org the principal asks). One per suite is
# enough; the suites are all "a single user's assistant" scenarios.
TRUST_DOMAIN: dict[str, str] = {
    "banking": "org:finance-user",
    "workspace": "org:workspace-user",
    "travel": "org:traveler-user",
    "slack": "org:slack-workspace",
}
DEFAULT_TRUST_DOMAIN = "org:user"


@dataclasses.dataclass(frozen=True)
class Org:
    """An organisation that owns content entering the agent.

    ``source_class`` sets the warrant ceiling for anything this org originates;
    ``trusted`` marks the user's own trust domain (everything else is external).
    """

    name: str
    source_class: SourceClass
    description: str = ""
    trusted: bool = False

    @property
    def warrant_ceiling(self):
        return self.source_class.warrant_ceiling


# ---------------------------------------------------------------------------
# Vector -> external-org classification
# ---------------------------------------------------------------------------
# Explicit, audited mapping for the banking suite (the headline suite, whose 4
# vectors we know precisely). Each entry: vector -> (external org name, class,
# rationale).
_BANKING_VECTORS: dict[str, tuple[str, SourceClass, str]] = {
    # Principle (corrected 2026-06-15): an injection *vector* is, by definition, a
    # slot an attacker can write content into — i.e. an EDITABLE source (WEAK), not
    # a trustworthy "published" page. Classifying an injectable slot as MODERATE was
    # the very misclassification an attacker exploits (the E4.2/E7.1 finding: a
    # MODERATE-class injection sits at the accept floor and a faithful relay leaves
    # it accepted). Injectability ⟹ editability ⟹ ≤ WEAK makes containment robust
    # to relay fidelity, not reliant on paraphrase erosion.
    "injection_bill_text": (
        "org:biller", SourceClass.EDITABLE_SOURCE,
        "an attacker-injectable invoice slot: attacker-editable, hence WEAK"),
    "injection_incoming_transaction": (
        "org:remote-sender", SourceClass.UNKNOWN,
        "a memo on an incoming transaction from an unknown remote party: no provenance"),
    "injection_address_change": (
        "org:address-registry", SourceClass.EDITABLE_SOURCE,
        "an external address-change notice: an editable, attacker-influenceable form"),
    "injection_landloard_notice": (
        "org:landlord", SourceClass.EDITABLE_SOURCE,
        "a notice from a landlord: an editable third-party message"),
}

# Prefix-based classification for the other suites (vector names there encode
# their channel). Every channel is external/untrusted; the class reflects how
# authenticated the channel is. Order matters: first matching prefix wins.
_PREFIX_RULES: tuple[tuple[str, str, SourceClass, str], ...] = (
    # (vector-substring, external-org, class, rationale)
    ("phishing",   "org:phisher",        SourceClass.UNKNOWN,
     "a phishing message: unattributed, hostile origin"),
    ("password",   "org:phisher",        SourceClass.UNKNOWN,
     "a password-reset lure: unattributed inbound message"),
    ("email",      "org:inbound-email",  SourceClass.EDITABLE_SOURCE,
     "an inbound email body: third-party-authored, editable"),
    ("calendar",   "org:calendar-invite", SourceClass.EDITABLE_SOURCE,
     "an external calendar invite/description: third-party-editable text"),
    ("drive",      "org:shared-drive",   SourceClass.EDITABLE_SOURCE,
     "a shared-drive document: collaboratively editable"),
    # injectable listing/web/blog slots are attacker-editable ⟹ WEAK (see the
    # banking-vector note above): if the attacker can plant the text, the slot is
    # editable, regardless of how "published" it looks.
    ("hotels",     "org:travel-listing", SourceClass.EDITABLE_SOURCE,
     "an attacker-injectable hotel listing/review slot: editable, WEAK"),
    ("restaurant", "org:travel-listing", SourceClass.EDITABLE_SOURCE,
     "an attacker-injectable restaurant listing slot: editable, WEAK"),
    ("cars",       "org:travel-listing", SourceClass.EDITABLE_SOURCE,
     "an attacker-injectable car-rental listing slot: editable, WEAK"),
    ("web",        "org:external-web",   SourceClass.EDITABLE_SOURCE,
     "an attacker-injectable external-web slot: editable, WEAK"),
    ("blog",       "org:external-web",   SourceClass.EDITABLE_SOURCE,
     "an attacker-injectable external-blog slot: editable, WEAK"),
    ("channel",    "org:other-workspace", SourceClass.EDITABLE_SOURCE,
     "a message from another Slack workspace/channel: third-party-editable"),
    ("dora",       "org:other-workspace", SourceClass.EDITABLE_SOURCE,
     "a message from another workspace member: third-party-editable"),
)

# Fallback for any vector we do not recognise: treat as an editable external
# source (WEAK) — the conservative-but-non-trivial default (still ≤ MODERATE).
_DEFAULT_EXTERNAL = ("org:external", SourceClass.EDITABLE_SOURCE,
                     "unrecognised external content slot: editable third-party source")


def classify_vector(suite_name: str, vector: str) -> Org:
    """Map an AgentDojo injection vector to the external :class:`Org` that owns it."""
    if suite_name == "banking" and vector in _BANKING_VECTORS:
        name, cls, why = _BANKING_VECTORS[vector]
        return Org(name=name, source_class=cls, description=why)
    low = vector.lower()
    for needle, name, cls, why in _PREFIX_RULES:
        if needle in low:
            return Org(name=name, source_class=cls, description=why)
    name, cls, why = _DEFAULT_EXTERNAL
    return Org(name=name, source_class=cls, description=why)


@dataclasses.dataclass
class BoundaryMap:
    """The explicit org-boundary map for one suite.

    Holds the user's trust-domain org and resolves, per injection vector, the
    external org that owns the content and the chain of orgs a relayed value
    traverses from that external origin up to the user's agent.
    """

    suite_name: str

    def __post_init__(self):
        self.trust_domain = TRUST_DOMAIN.get(self.suite_name, DEFAULT_TRUST_DOMAIN)

    def external_org(self, vector: str) -> Org:
        return classify_vector(self.suite_name, vector)

    def source_class(self, vector: str) -> SourceClass:
        return self.external_org(vector).source_class

    def orgs_for_chain(self, vector: str, n_hops: int) -> list[str]:
        """Explicit org names head(0)->tail(n_hops-1) for a relayed value.

        ``orgs[0]`` is the user's trust domain (the principal-facing agent),
        ``orgs[-1]`` is the external data-owner org. Any intermediate hops are
        distinct broker orgs, so every hop is a genuine cross-org boundary.
        """
        ext = self.external_org(vector).name
        if n_hops == 1:
            return [ext]
        head = self.trust_domain
        tail = ext
        # distinct intermediate broker orgs (e.g. an aggregator/relay service)
        middle = [f"org:relay-{i}" for i in range(1, n_hops - 1)]
        chain = [head] + middle + [tail]
        # guarantee distinctness (orgs_for_chain feeds build_chain's distinctness check)
        assert len(set(chain)) == len(chain), chain
        return chain

    def boundary_summary(self, vectors: list[str]) -> list[dict]:
        """A table (one row per vector) describing the boundary, for reporting."""
        rows = []
        for v in vectors:
            org = self.external_org(v)
            rows.append({
                "vector": v,
                "external_org": org.name,
                "source_class": org.source_class.name,
                "warrant_ceiling": org.warrant_ceiling.name,
                "trust_domain": self.trust_domain,
                "rationale": org.description,
            })
        return rows
