"""Bridge from CAPM onto real AgentDojo task suites with explicit org boundaries.

This loads a genuine AgentDojo suite (workspace/banking/travel/slack) and exposes
its real artifacts — user tasks, injection tasks, injection vectors, attacker
GOAL strings — together with the explicit organisational boundary each injection
vector represents (via :mod:`capm.benchmark.agentdojo_crossorg.boundaries`).

The integration is deliberately thin: the warrant/manifest/evaluator machinery
is the *same* native code; only the **source of content** changes from a
deterministic responder to real AgentDojo attacker goals, and the **boundary**
is made explicit (which external org owns each vector, at what source class).
:mod:`capm.benchmark.agentdojo_crossorg.runner` consumes these specs to run the
cross-org attack benchmark.

If ``agentdojo`` is not installed the module exposes the same surface but reports
availability=False so callers fall back to the native harness.
"""

from __future__ import annotations

import dataclasses
from typing import Optional

from capm.benchmark.agentdojo_crossorg.boundaries import BoundaryMap, Org
from capm.core.types import SourceClass

AGENTDOJO_AVAILABLE = False
try:  # pragma: no cover - only when agentdojo is installed
    import agentdojo  # noqa: F401
    from agentdojo.task_suite.load_suites import get_suites  # noqa: F401
    AGENTDOJO_AVAILABLE = True
except Exception:
    get_suites = None  # type: ignore


_KNOWN_SUITES = ("workspace", "banking", "travel", "slack")


def available_suites() -> tuple[str, ...]:
    """The AgentDojo suites we can wrap (empty if agentdojo is absent)."""
    return _KNOWN_SUITES if AGENTDOJO_AVAILABLE else ()


@dataclasses.dataclass(frozen=True)
class InjectionSpec:
    """One real AgentDojo injection mapped onto an explicit cross-org boundary.

    ``goal`` is the suite's genuine attacker GOAL string. ``vector`` is the real
    injection slot it is planted in; ``external_org`` / ``true_class`` describe
    the organisation that owns that slot and the warrant its class permits.
    """

    task_id: str
    goal: str
    vector: str
    external_org: str
    true_class: SourceClass


@dataclasses.dataclass
class CrossOrgSuite:
    """A CAPM-wrapped AgentDojo suite with an explicit org-boundary map.

    Parameters
    ----------
    suite_name:
        One of :data:`_KNOWN_SUITES`.
    boundary_map:
        An explicit :class:`BoundaryMap`. Defaults to the suite's audited map
        (every injection vector -> the external org that owns it + its source
        class). Pass a custom one to study different deployments.
    version:
        AgentDojo suite version tag (default 'v1.2', matching CaMeL).
    """

    suite_name: str
    boundary_map: Optional[BoundaryMap] = None
    version: str = "v1.2"

    def __post_init__(self):
        if not AGENTDOJO_AVAILABLE:
            raise RuntimeError(
                "agentdojo is not installed. `pip install agentdojo` to run the "
                "cross-org task benchmark (E5.4/E1.3/E5.x); otherwise use the "
                "native harness in capm.benchmark.harness.")
        if self.suite_name not in _KNOWN_SUITES:
            raise ValueError(f"unknown suite {self.suite_name!r}; pick from {_KNOWN_SUITES}")
        self._suite = get_suites(self.version)[self.suite_name]  # type: ignore
        if self.boundary_map is None:
            self.boundary_map = BoundaryMap(self.suite_name)

    # ---- raw AgentDojo surface ----------------------------------------
    def user_tasks(self):  # noqa: ANN201
        return list(self._suite.user_tasks.values())

    def injection_tasks(self):  # noqa: ANN201
        return list(self._suite.injection_tasks.values())

    def injection_vectors(self) -> dict:
        """``{vector_id: default_text}`` - each is a slot where external content
        flows into the agent's trust domain (the cross-org boundaries CAPM gates)."""
        try:
            return dict(self._suite.get_injection_vector_defaults())
        except Exception:
            return {}

    def injection_goals(self) -> list:
        """The attacker GOAL strings from the suite's injection tasks."""
        return [getattr(t, "GOAL", "") for t in self._suite.injection_tasks.values()]

    # ---- explicit-boundary view --------------------------------------
    def external_org(self, vector: str) -> Org:
        return self.boundary_map.external_org(vector)

    def boundary_summary(self) -> list[dict]:
        """One row per injection vector: which external org owns it, at what class."""
        return self.boundary_map.boundary_summary(list(self.injection_vectors()))

    def injection_specs(self) -> list[InjectionSpec]:
        """Pair every real injection GOAL with a real injection vector + its org.

        AgentDojo injection tasks are not bound 1:1 to a single vector (the same
        goal can be planted in any external slot), so we assign vectors
        **deterministically round-robin** over the suite's real vectors. Each
        spec therefore represents a genuine attacker goal landing in a genuine
        external content slot owned by a specific external organisation.
        """
        vectors = list(self.injection_vectors())
        specs: list[InjectionSpec] = []
        tasks = self._suite.injection_tasks
        for i, (tid, task) in enumerate(sorted(tasks.items())):
            vec = vectors[i % len(vectors)] if vectors else "external_content"
            org = self.boundary_map.external_org(vec)
            specs.append(InjectionSpec(
                task_id=tid, goal=getattr(task, "GOAL", ""), vector=vec,
                external_org=org.name, true_class=org.source_class))
        return specs

    def orgs_for_chain(self, vector: str, n_hops: int) -> list[str]:
        return self.boundary_map.orgs_for_chain(vector, n_hops)


def status() -> str:
    if AGENTDOJO_AVAILABLE:
        return f"agentdojo available; suites: {', '.join(_KNOWN_SUITES)}"
    return ("agentdojo NOT installed - native cross-org harness in use. "
            "`pip install agentdojo` to enable real task suites.")
