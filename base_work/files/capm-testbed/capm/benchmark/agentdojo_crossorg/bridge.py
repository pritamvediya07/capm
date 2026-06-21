"""Thin bridge from CAPM onto AgentDojo task suites with org boundaries.

The integration plan (concrete, so it can be implemented incrementally):

1. Load an AgentDojo suite: ``agentdojo.task_suite.get_suite("v1.2", name)``.
2. Assign each tool / sub-agent in a task to an **organisation** (a boundary map
   ``tool_name -> org``). Every tool result that crosses an org boundary is
   wrapped as a CAPM ``WarrantedValue`` and a manifest segment is signed.
3. Run the task with CAPM's evaluator gating belief on cross-org tool results,
   exactly as the native harness does, but with real AgentDojo content/tasks.
4. Injection tasks (``BaseInjectionTask``) become CAPM adversaries by planting
   content at a chosen boundary with a chosen (possibly lying) source class.

Until ``agentdojo`` is installed this module exposes the same surface but
reports availability=False so callers can fall back to the native harness.
"""

from __future__ import annotations

import dataclasses
from typing import Optional

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


@dataclasses.dataclass
class CrossOrgSuite:
    """A CAPM-wrapped AgentDojo suite with an org-boundary map.

    Parameters
    ----------
    suite_name:
        One of :data:`_KNOWN_SUITES`.
    boundary_map:
        ``tool_name -> organisation``. Tools in different orgs put a cross-org
        boundary between the agent calling the tool and the tool's data owner.
    version:
        AgentDojo suite version tag (default 'v1.2', matching CaMeL).
    """

    suite_name: str
    boundary_map: dict[str, str]
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

    def org_of(self, tool_name: str, default: str = "org-external") -> str:
        return self.boundary_map.get(tool_name, default)

    # pragma: no cover - exercised only with agentdojo installed
    def user_tasks(self):  # noqa: ANN201
        return list(self._suite.user_tasks.values())

    def injection_tasks(self):  # noqa: ANN201
        return list(self._suite.injection_tasks.values())

    def injection_vectors(self) -> dict:
        """The suite's injection slots (where untrusted external content lands).

        Returns ``{vector_id: default_text}`` - each is a place where content
        from an *external* org (a biller, a remote sender, a web page) flows into
        the agent's trust domain. These are the cross-org boundaries CAPM gates.
        """
        try:
            return dict(self._suite.get_injection_vector_defaults())
        except Exception:
            return {}

    def injection_goals(self) -> list:
        """The attacker GOAL strings from the suite's injection tasks."""
        return [getattr(t, "GOAL", "") for t in self._suite.injection_tasks.values()]


def status() -> str:
    if AGENTDOJO_AVAILABLE:
        return f"agentdojo available; suites: {', '.join(_KNOWN_SUITES)}"
    return ("agentdojo NOT installed - native cross-org harness in use. "
            "`pip install agentdojo` to enable real task suites.")
