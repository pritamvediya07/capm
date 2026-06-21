"""saga_bridge - graft CAPM onto SAGA's *real* codebase (gsiros/saga).

This is the concrete integration the comparison (docs/CAPM_vs_SAGA.md)
specifies. It backs CAPM's four touch-points with SAGA's actual modules:

    CAPM concept              backed by SAGA module
    ------------------------  -----------------------------------------
    AgentIdentity.sign/verify saga.common.crypto.sign_message/verify_signature
    AgentIdentity key+cert    saga.common.crypto Ed25519 keys + X.509 cert
    CredentialRegistry trust  saga.ca.CA (cert verification) + Provider view
    benchmark overhead        saga.common.overhead.Monitor

SAGA is an OPTIONAL dependency. If it is not importable, every function here
falls back to CAPM's self-contained Ed25519 implementation, and
``SAGA_AVAILABLE`` is False. So ``import capm`` and the standalone testbed
never break on a machine without SAGA.

Enable the real backing:

    git clone https://github.com/gsiros/saga.git vendor/saga
    pip install -e vendor/saga
    export CAPM_USE_SAGA=1
"""

from __future__ import annotations

import base64
import os
from typing import Optional

# ---- try to import SAGA's real modules -----------------------------------
SAGA_AVAILABLE = False
_saga_crypto = None
_saga_CA = None
_SagaMonitor = None
_SagaLocalAgent = None
try:  # pragma: no cover - only when SAGA installed
    import saga.common.crypto as _saga_crypto          # noqa: F401
    from saga.ca.CA import get_SAGA_CA as _get_saga_ca  # noqa: F401
    from saga.common.overhead import Monitor as _SagaMonitor  # noqa: F401
    from saga.local_agent import LocalAgent as _SagaLocalAgent  # noqa: F401
    SAGA_AVAILABLE = True
except Exception:
    pass


def use_saga() -> bool:
    """True iff SAGA is installed AND the user opted in via env var."""
    return SAGA_AVAILABLE and os.environ.get("CAPM_USE_SAGA") == "1"


# ---------------------------------------------------------------------------
# Signing primitive: route through SAGA's crypto when available
# ---------------------------------------------------------------------------
class SagaSigner:
    """Wraps a SAGA Ed25519 keypair behind CAPM's sign/verify interface.

    SAGA and CAPM use the *same* primitive (Ed25519), so this is a thin
    adapter: ``sign`` -> ``crypto.sign_message``; ``verify`` ->
    ``crypto.verify_signature``. The CAPM manifest layer is unchanged.
    """

    def __init__(self, name: str, keys_dir: Optional[str] = None):
        if not SAGA_AVAILABLE:
            raise RuntimeError("SAGA not installed; use the in-process identity")
        # SAGA stores/loads Ed25519 keys by name
        if keys_dir and os.path.exists(os.path.join(keys_dir, f"{name}.key")):
            self._sk, self._pk = _saga_crypto.load_ed25519_keys(
                os.path.join(keys_dir, name))
        else:
            self._sk, self._pk = _saga_crypto.generate_ed25519_keypair()
        self.name = name

    def public_key_b64(self) -> str:
        from cryptography.hazmat.primitives import serialization
        raw = self._pk.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)
        return base64.b64encode(raw).decode()

    def sign(self, payload: bytes) -> str:
        # SAGA's sign_message takes a *str* and returns (message, signature).
        # CAPM signs arbitrary bytes, so we base64-encode to a str first.
        msg_str = base64.b64encode(payload).decode()
        _msg, sig = _saga_crypto.sign_message(self._sk, msg_str)
        return base64.b64encode(sig).decode()

    @staticmethod
    def verify(public_key_b64: str, payload: bytes, signature_b64: str) -> bool:
        try:
            pk = _saga_crypto.bytesToPublicEd25519Key(
                base64.b64decode(public_key_b64))
            msg_str = base64.b64encode(payload).decode()
            return bool(_saga_crypto.verify_signature(
                pk, msg_str, base64.b64decode(signature_b64)))
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Trust root: SAGA's CA / Provider view
# ---------------------------------------------------------------------------
class SagaTrustRoot:
    """A CAPM CredentialRegistry-compatible trust root backed by SAGA's CA.

    ``trusts(did)`` returns True iff SAGA's CA can verify the agent's
    certificate (i.e. the Provider issued/registered it). In a live deployment
    this also consults the Provider's ``/lookup``; here we verify against the
    SAGA CA, which is what the agent code itself does on every connection.
    """

    def __init__(self):
        if not SAGA_AVAILABLE:
            raise RuntimeError("SAGA not installed")
        self._ca = _get_saga_ca()
        self._certs: dict[str, object] = {}

    def register_cert(self, did: str, certificate) -> None:
        self._certs[did] = certificate

    def trusts(self, did: str) -> bool:
        cert = self._certs.get(did)
        if cert is None:
            return False
        try:
            self._ca.verify(cert)   # raises on failure
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Overhead measurement: prefer SAGA's Monitor so numbers are comparable
# ---------------------------------------------------------------------------
def get_monitor():
    """Return SAGA's Monitor if available, else a tiny compatible shim.

    Using SAGA's own Monitor means CAPM's overhead is reported on the exact
    instrument SAGA used for its NDSS-2026 negligible-overhead result.
    """
    if SAGA_AVAILABLE and _SagaMonitor is not None:
        return _SagaMonitor()
    return _FallbackMonitor()


class _FallbackMonitor:
    """Minimal start/stop/elapsed shim mirroring saga.common.overhead.Monitor."""

    def __init__(self):
        import time
        self._t = time
        self._starts: dict[str, float] = {}
        self._elapsed: dict[str, float] = {}

    def start(self, run_id: str) -> None:
        self._starts[run_id] = self._t.perf_counter()

    def stop(self, run_id: str) -> None:
        if run_id in self._starts:
            self._elapsed[run_id] = self._t.perf_counter() - self._starts[run_id]

    def elapsed(self, run_id: str) -> float:
        return self._elapsed.get(run_id, 0.0)


def saga_local_agent_base():
    """Return SAGA's LocalAgent ABC if present (CAPMAgent already matches it)."""
    return _SagaLocalAgent
