"""Cross-org AgentDojo benchmark (E5.4) — the substrate for the real experiments.

AgentDojo (used by CaMeL) is a single-trust-domain benchmark. The design doc's
contribution is to extend it with **explicit organisational boundaries** between
agents so the Plane-2 cross-org property is exercised inside genuine agent tasks.

This package is that extension:

* :mod:`~capm.benchmark.agentdojo_crossorg.boundaries` — the explicit org model
  (every injection vector → the external org that owns it + its source class).
* :mod:`~capm.benchmark.agentdojo_crossorg.bridge` — loads a real AgentDojo suite
  and exposes its tasks/vectors/goals as boundary-annotated :class:`InjectionSpec`.
* :mod:`~capm.benchmark.agentdojo_crossorg.runner` — runs real attacker goals
  across those boundaries through the native CAPM evaluator, scoring every defense
  (injection headline + origin-capture control + honest-utility).

The heavy lifting (warrant, manifest, evaluator) is the *same* native code; only
the source of content and the explicitness of the boundary change. Without
``agentdojo`` installed the helpers report availability=False and callers fall
back to :mod:`capm.benchmark.harness`.
"""

from capm.benchmark.agentdojo_crossorg.boundaries import (BoundaryMap, Org,
                                                          classify_vector)
from capm.benchmark.agentdojo_crossorg.bridge import (AGENTDOJO_AVAILABLE,
                                                      CrossOrgSuite,
                                                      InjectionSpec,
                                                      available_suites, status)
from capm.benchmark.agentdojo_crossorg.runner import (DEFENSES, BenchmarkResult,
                                                      CrossOrgRow, run_benchmark)

__all__ = [
    "AGENTDOJO_AVAILABLE", "CrossOrgSuite", "InjectionSpec", "available_suites",
    "status", "BoundaryMap", "Org", "classify_vector",
    "BenchmarkResult", "CrossOrgRow", "run_benchmark", "DEFENSES",
]
