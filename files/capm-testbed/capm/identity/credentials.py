"""Agent identity and signing (Component 3 - the Plane-1 <-> Plane-2 binding).

This is the seam the literature names but nobody has built (open challenges
I6 and T4). We give each agent a Verifiable-Credential-like identity and bind
the *provenance manifest signature* to the key behind that VC.

Relationship to SAGA (gsiros/saga)
----------------------------------
SAGA already provides the cross-agent **Plane-1** substrate: agents register
with a Provider/CA, receive certificates, and derive one-time access-control
tokens for inter-agent calls (``saga.common.crypto``, ``saga.ca.CA``). In the
full testbed (see :mod:`capm.adapters.saga_adapter`) the CAPM ``AgentIdentity``
is backed by a real SAGA certificate and the Provider is the trust root.

Here we implement a **self-contained** crypto identity using ``cryptography``
(Ed25519) so the testbed runs with zero external services. The adapter swaps
this for SAGA when SAGA is installed. This is the "extend SAGA, don't rebuild
it" decision made concrete: the interface is identical; only the backing
changes.
"""

from __future__ import annotations

import base64
import dataclasses
import json
from typing import Optional

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey)
    from cryptography.hazmat.primitives import serialization
    from cryptography.exceptions import InvalidSignature
    _HAVE_CRYPTO = True
except Exception:  # pragma: no cover - fallback for minimal environments
    _HAVE_CRYPTO = False


@dataclasses.dataclass(frozen=True)
class VerifiableCredential:
    """Minimal W3C-VC-shaped credential for an agent.

    In the SAGA-backed configuration ``did`` is the agent's SAGA identity and
    ``issuer`` is the Provider. Here the issuer is the in-process CA.
    """

    did: str                       # decentralised identifier of the agent
    org: str                       # controlling organisation
    issuer: str                    # who vouches for this agent
    public_key_b64: str            # the verification key

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), sort_keys=True)


class AgentIdentity:
    """An agent's signing identity. Wraps an Ed25519 keypair + its VC.

    When SAGA is installed and ``CAPM_USE_SAGA=1``, signing/verification route
    through SAGA's ``common.crypto`` (the exact code accepted at NDSS 2026)
    instead of the in-process keypair. The interface is identical either way,
    so nothing downstream changes. See ``capm/adapters/saga_bridge.py``.
    """

    def __init__(self, did: str, org: str, issuer: str = "capm-local-ca"):
        self._saga_signer = None
        # Prefer SAGA's crypto if the user opted in.
        try:
            from capm.adapters import saga_bridge
            if saga_bridge.use_saga():
                self._saga_signer = saga_bridge.SagaSigner(name=did.replace(":", "_"))
        except Exception:
            self._saga_signer = None

        if self._saga_signer is not None:
            pk_b64 = self._saga_signer.public_key_b64()
            self.vc = VerifiableCredential(did=did, org=org,
                                           issuer="saga-provider",
                                           public_key_b64=pk_b64)
            return

        if not _HAVE_CRYPTO:
            raise RuntimeError("`cryptography` is required for AgentIdentity")
        self._sk = Ed25519PrivateKey.generate()
        pk = self._sk.public_key()
        pk_bytes = pk.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)
        self.vc = VerifiableCredential(
            did=did, org=org, issuer=issuer,
            public_key_b64=base64.b64encode(pk_bytes).decode())

    @property
    def did(self) -> str:
        return self.vc.did

    @property
    def org(self) -> str:
        return self.vc.org

    def sign(self, payload: bytes) -> str:
        if self._saga_signer is not None:
            return self._saga_signer.sign(payload)
        return base64.b64encode(self._sk.sign(payload)).decode()

    @staticmethod
    def verify(vc: VerifiableCredential, payload: bytes, signature_b64: str) -> bool:
        # Try SAGA's verifier first if SAGA is active; it accepts the same
        # base64 public key, so verification is interchangeable.
        try:
            from capm.adapters import saga_bridge
            if saga_bridge.use_saga():
                return saga_bridge.SagaSigner.verify(
                    vc.public_key_b64, payload, signature_b64)
        except Exception:
            pass
        if not _HAVE_CRYPTO:
            raise RuntimeError("`cryptography` is required for verification")
        try:
            pk = Ed25519PublicKey.from_public_bytes(
                base64.b64decode(vc.public_key_b64))
            pk.verify(base64.b64decode(signature_b64), payload)
            return True
        except (InvalidSignature, Exception):
            return False


class CredentialRegistry:
    """A trust root: maps DID -> VC for verification.

    Stand-in for SAGA's Provider. A receiver consults this to confirm that an
    incoming manifest was signed by a credential the registry vouches for.
    """

    def __init__(self) -> None:
        self._by_did: dict[str, VerifiableCredential] = {}

    def register(self, identity: AgentIdentity) -> None:
        self._by_did[identity.did] = identity.vc

    def lookup(self, did: str) -> Optional[VerifiableCredential]:
        return self._by_did.get(did)

    def trusts(self, did: str) -> bool:
        return did in self._by_did
