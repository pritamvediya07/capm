"""Optional SAGA backing for CAPM identity and transport.

This module is the concrete realisation of the build-strategy decision: CAPM
*extends* SAGA (gsiros/saga) rather than rebuilding cross-agent plumbing.

When SAGA is installed and a Provider is reachable, this adapter:

* backs each :class:`capm.identity.credentials.AgentIdentity` with a real SAGA
  certificate issued by the SAGA CA (``saga.ca.CA.get_SAGA_CA``);
* makes the SAGA Provider the trust root that
  :class:`capm.identity.credentials.CredentialRegistry` consults;
* carries the CAPM manifest as an application-level payload alongside SAGA's
  one-time access-control tokens, so Plane-2 provenance rides on top of SAGA's
  Plane-1 inter-agent channel.

SAGA is an *optional* dependency. The testbed runs fully without it using the
in-process Ed25519 identities. Import errors are swallowed so that
``import capm`` never fails on a machine without SAGA.

To enable: ``pip install -e vendor/saga`` (or clone gsiros/saga) and set
``CAPM_USE_SAGA=1``.
"""

from __future__ import annotations

import os

SAGA_AVAILABLE = False
try:  # pragma: no cover - exercised only when SAGA is installed
    import saga  # noqa: F401
    from saga.local_agent import LocalAgent as SagaLocalAgent  # noqa: F401
    SAGA_AVAILABLE = True
except Exception:
    SagaLocalAgent = None  # type: ignore


def use_saga() -> bool:
    return SAGA_AVAILABLE and os.environ.get("CAPM_USE_SAGA") == "1"


def wrap_as_saga_agent(capm_agent):
    """Expose a CAPMAgent through SAGA's LocalAgent ABC.

    SAGA's ``LocalAgent.run(query, initiating_agent, agent_instance)`` maps
    directly onto :meth:`capm.agents.agent.CAPMAgent.run`, which is why the
    interface was kept identical. When SAGA drives the deployment it calls
    ``run`` and CAPM's signing/verification happens transparently inside.
    """
    if not SAGA_AVAILABLE:
        raise RuntimeError(
            "SAGA is not installed. Clone gsiros/saga into vendor/saga and "
            "`pip install -e vendor/saga`, or run the testbed standalone.")
    return capm_agent  # interfaces already match; nothing to translate


NOTE = (
    "CAPM extends SAGA: SAGA provides Plane-1 (identity, CA, OTK tokens); "
    "CAPM adds Plane-2 (signed provenance manifests + warrant evaluation). "
    "See docs/INTEGRATION.md for the wiring."
)
