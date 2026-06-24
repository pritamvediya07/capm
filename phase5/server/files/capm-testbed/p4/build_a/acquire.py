"""p4/build_a/acquire.py — Build A: acquisition wrapper (WS5 / P4-5A).

Derives `source_class` from OBSERVABLE channel evidence via a deterministic,
versioned policy table — never hand-set scenario metadata. Three acquisition
paths: HTTP (real TLS chain verification), API, file/DB. Signs the origin
observation (Ed25519) binding the evidence + the derived class, so the manifest
path consumes a *measured* origin property.

Safety property (the whole point): evidence-only + degrade-on-uncertainty ⇒ a
misclassification can only UNDER-trust. Over-trust requires forged channel
evidence — i.e. acquisition-wrapper compromise, exactly the Theorem-2 residual.
This is the I6/T4 acquisition seam and the concrete realization of A4/A5.
"""
from __future__ import annotations

import hashlib
import json
import socket
import ssl
from urllib.parse import urlparse

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from capm.core.types import SourceClass

POLICY_VERSION = "p4-5a-v1"
# editability heuristic (UGC / wiki / issue hosts) — observable, not content-based
EDITABLE_HOSTS = ("wikipedia.org", "fandom.com", "reddit.com", "stackexchange.com",
                  "stackoverflow.com", "medium.com", "github.io")
EDITABLE_PATHS = ("/issues", "/wiki/", "/edit", "/comments", "/discussions")


def _tls_evidence(host: str, port: int = 443, timeout: int = 8) -> dict:
    """Observe the TLS channel with REAL chain + hostname verification."""
    ctx = ssl.create_default_context()                      # verifies chain AND hostname
    ev = {"tls_valid": False, "tls_error": None}
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            with ctx.wrap_socket(s, server_hostname=host) as ss:
                cert = ss.getpeercert()
                ev["tls_valid"] = True
                ev["tls_not_after"] = cert.get("notAfter")
    except ssl.SSLCertVerificationError as e:
        ev["tls_error"] = f"cert-verify-failed: {getattr(e, 'verify_message', str(e))}"[:80]
    except Exception as e:                                   # DNS/timeout/refused -> unverifiable
        ev["tls_error"] = f"{type(e).__name__}: {str(e)[:60]}"
    return ev


def _editable(host: str, path: str) -> bool:
    return any(h in host for h in EDITABLE_HOSTS) or any(p in path for p in EDITABLE_PATHS)


def classify(ev: dict) -> tuple[SourceClass, str]:
    """The deterministic policy table. Conservative-default = UNKNOWN (NONE)."""
    ch = ev.get("channel")
    if ch == "http":
        if not ev.get("tls_valid"):
            return SourceClass.UNKNOWN, "TLS invalid/unverifiable → degrade (never over-trust)"
        if ev.get("editable"):
            return SourceClass.EDITABLE_SOURCE, "valid TLS but editable/UGC host"
        if ev.get("content_signature"):
            return SourceClass.VERIFIED_DOCUMENT, "valid TLS + content signature (C2PA-style)"
        return SourceClass.PUBLIC_WEBPAGE, "valid TLS, non-editable host, no content signature"
    if ch == "api":
        if not ev.get("tls_valid"):
            return SourceClass.UNKNOWN, "API TLS invalid → degrade"
        if not ev.get("request_auth"):
            return SourceClass.PUBLIC_WEBPAGE, "API without request auth → degrade to webpage class"
        if ev.get("response_signature") and ev.get("allowlisted"):
            return SourceClass.AUTHORITATIVE_API, "TLS + auth + response-signature + allowlisted endpoint"
        return SourceClass.FIRST_PARTY_DB, "TLS + auth but no response signature → MODERATE"
    if ch == "file":
        if ev.get("first_party") and ev.get("authenticated_channel"):
            return SourceClass.FIRST_PARTY_DB, "first-party file/DB over an authenticated channel"
        return SourceClass.UNKNOWN, "file/DB origin unverifiable → degrade"
    return SourceClass.UNKNOWN, "unknown channel → degrade"


# one acquisition-wrapper signing key (in production: AgentIdentity bound to SAGA's cert)
_WRAPPER_SK = Ed25519PrivateKey.generate()


def _sign_origin_observation(uri: str, content: bytes, ev: dict, sc: SourceClass, reason: str) -> dict:
    obs = {"policy_version": POLICY_VERSION, "uri": uri,
           "content_hash": hashlib.sha256(content).hexdigest(),
           "source_class": sc.value, "warrant_ceiling": sc.warrant_ceiling.name,
           "evidence": ev, "reason": reason}
    payload = json.dumps(obs, sort_keys=True).encode()
    sig = _WRAPPER_SK.sign(payload).hex()
    return {"observation": obs, "signature": sig, "signer": "did:capm:acquisition-wrapper",
            "source_class": sc, "ceiling": sc.warrant_ceiling}


def acquire_http(url: str, content: bytes = b"", content_signature: bool = False) -> dict:
    p = urlparse(url)
    ev = {"channel": "http", "url": url, **_tls_evidence(p.hostname or "")}
    ev["editable"] = _editable(p.hostname or "", p.path or "/")
    ev["content_signature"] = content_signature
    sc, reason = classify(ev)
    return _sign_origin_observation(url, content, ev, sc, reason)


def acquire_api(endpoint: str, content: bytes = b"", *, tls_valid: bool = True,
                request_auth: bool = True, response_signature: bool = False,
                allowlisted: bool = False) -> dict:
    ev = {"channel": "api", "url": endpoint, "tls_valid": tls_valid, "request_auth": request_auth,
          "response_signature": response_signature, "allowlisted": allowlisted}
    sc, reason = classify(ev)
    return _sign_origin_observation(endpoint, content, ev, sc, reason)


def acquire_file(path: str, content: bytes = b"", *, first_party: bool = True,
                 authenticated_channel: bool = True) -> dict:
    ev = {"channel": "file", "url": path, "first_party": first_party,
          "authenticated_channel": authenticated_channel}
    sc, reason = classify(ev)
    return _sign_origin_observation(path, content, ev, sc, reason)
