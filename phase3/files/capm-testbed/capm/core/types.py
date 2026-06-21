"""Core type definitions for the CAPM testbed.

This module defines the foundational enumerations and value types used
throughout the Cross-Agent Provenance Manifest (CAPM) system.

Design lineage
--------------
* ``Capabilities`` (CaMeL, google-research/camel-prompt-injection,
  ``src/camel/capabilities/capabilities.py``) is the design ancestor of
  :class:`~capm.core.value.WarrantedValue`. CaMeL attaches a frozen
  ``sources_set`` + ``readers_set`` to every value; we extend that idea so
  that every value also carries a *warrant level* and a *provenance chain*
  that survive the agent-to-agent boundary.
* Warrant is the epistemological notion from the Semantic Laundering paper
  (arXiv:2601.08333): justification linking a claim to its source. It is
  deliberately *not* the same as identity (Plane 1) or authorization.

Everything here is plain-Python and dependency-free so it can be imported by
the manifest, warrant and benchmark layers without circular imports.
"""

from __future__ import annotations

import dataclasses
import enum
from typing import Any


class WarrantLevel(enum.IntEnum):
    """Ordered warrant lattice (higher == stronger justification).

    The ordering is what makes the Warrant Erosion Principle measurable: a
    transformation or a boundary crossing can only move a value *down* this
    lattice, never up. See :mod:`capm.warrant.evaluator`.
    """

    NONE = 0          # unjustified relative to any source (e.g. hallucination)
    WEAK = 1          # brittle / partially broken link to a source
    DERIVED = 2       # faithfully derived from a MODERATE+ source
    MODERATE = 3      # ordinary source, no special authority
    STRONG = 4        # verifiable, faithful link to an authoritative source

    @classmethod
    def from_str(cls, name: str) -> "WarrantLevel":
        return cls[name.strip().upper()]


class TransformationType(enum.Enum):
    """The operation an agent performed on an incoming value.

    Each transformation type carries a *fidelity penalty* used by the warrant
    evaluator. Verbatim preserves warrant; paraphrase / summary lose some;
    composition over multiple inputs is bounded by the weakest input.
    """

    VERBATIM = "verbatim"                 # exact copy, no semantic change
    STRUCTURED_EXTRACTION = "extraction"  # pulled fields out of structured data
    SUMMARY = "summary"                   # condensed
    PARAPHRASE = "paraphrase"             # reworded
    COMPOSITION = "composition"           # combined multiple inputs
    GENERATION = "generation"             # produced new content (lowest fidelity)

    @property
    def fidelity_penalty(self) -> int:
        """How many warrant levels this transformation can cost (>=0)."""
        return {
            TransformationType.VERBATIM: 0,
            TransformationType.STRUCTURED_EXTRACTION: 0,
            TransformationType.SUMMARY: 1,
            TransformationType.PARAPHRASE: 1,
            TransformationType.COMPOSITION: 1,
            TransformationType.GENERATION: 4,  # collapses to NONE unless re-grounded
        }[self]


class SourceClass(enum.Enum):
    """Classification of an originating (non-agent) source.

    The initial warrant of a value is bounded by the class of its origin.
    This is the mechanism that defeats laundering: a claim that originated on
    a publicly editable page keeps a low ceiling no matter how many trusted
    agents relay it.
    """

    AUTHORITATIVE_API = "authoritative_api"   # signed/first-party API -> STRONG
    VERIFIED_DOCUMENT = "verified_document"    # signed document -> STRONG
    FIRST_PARTY_DB = "first_party_db"          # internal trusted store -> MODERATE
    PUBLIC_WEBPAGE = "public_webpage"          # ordinary web page -> MODERATE
    EDITABLE_SOURCE = "editable_source"        # wiki/issue/comment -> WEAK
    UNTRUSTED_TOOL = "untrusted_tool"          # unvetted MCP server -> WEAK
    MODEL_MEMORY = "model_memory"              # parametric recall -> WEAK
    UNKNOWN = "unknown"                         # no provenance -> NONE

    @property
    def warrant_ceiling(self) -> WarrantLevel:
        return {
            SourceClass.AUTHORITATIVE_API: WarrantLevel.STRONG,
            SourceClass.VERIFIED_DOCUMENT: WarrantLevel.STRONG,
            SourceClass.FIRST_PARTY_DB: WarrantLevel.MODERATE,
            SourceClass.PUBLIC_WEBPAGE: WarrantLevel.MODERATE,
            SourceClass.EDITABLE_SOURCE: WarrantLevel.WEAK,
            SourceClass.UNTRUSTED_TOOL: WarrantLevel.WEAK,
            SourceClass.MODEL_MEMORY: WarrantLevel.WEAK,
            SourceClass.UNKNOWN: WarrantLevel.NONE,
        }[self]


@dataclasses.dataclass(frozen=True)
class Source:
    """An originating producer of a claim (the chain's tail, a non-agent).

    Mirrors CaMeL's ``sources.Tool`` but adds a :class:`SourceClass` so that
    origin warrant can be computed.
    """

    source_id: str
    source_class: SourceClass = SourceClass.UNKNOWN
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __hash__(self) -> int:  # frozen dataclass with dict field needs this
        return hash((self.source_id, self.source_class))
