"""Cross-org AgentDojo bridge (E5.4, optional).

AgentDojo (used by CaMeL, ``reference_codes/camel-prompt-injection-main``) is a
single-domain, single-trust-domain benchmark. The design doc's contribution is
to extend it with **explicit organisational boundaries** between agents so the
Plane-2 cross-org property is exercised inside genuine agent tasks.

This package is the seam. It is an *optional* integration: if ``agentdojo`` is
installed it wraps a real task suite (workspace/banking/travel/slack) so each
tool result becomes a CAPM-warranted value crossing an org boundary, and the
adaptive adversaries in :mod:`attacks.adaptive` inject at those boundaries.
Without ``agentdojo`` the native harness (:mod:`capm.benchmark.harness`) is used
and these helpers report that the dependency is absent.

The bridge is intentionally thin: the heavy lifting (warrant, manifest, evaluator)
is identical to the native path; only the *source of content* changes from a
deterministic responder to a real AgentDojo tool/task.
"""

from capm.benchmark.agentdojo_crossorg.bridge import (AGENTDOJO_AVAILABLE,
                                                      CrossOrgSuite,
                                                      available_suites)

__all__ = ["AGENTDOJO_AVAILABLE", "CrossOrgSuite", "available_suites"]
