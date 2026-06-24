"""mTLS cert generation for the Build B transport smoke (WS5/P4-5B).

Generates a CA and per-service leaf certs (registry / verifier / client) plus a
ROGUE CA + rogue client cert for the cert-mismatch rejection test. RSA-2048 (gRPC
TLS / BoringSSL universally supports it). SANs cover localhost + 127.0.0.1.
In production this is SAGA's X.509 CA (the adapter already exists).
"""
from __future__ import annotations

import datetime
import ipaddress
import os

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_NOW = datetime.datetime.now(datetime.timezone.utc)


def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _name(cn):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def make_ca(cn="capm-ca"):
    k = _key()
    cert = (x509.CertificateBuilder().subject_name(_name(cn)).issuer_name(_name(cn))
            .public_key(k.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(_NOW - datetime.timedelta(days=1))
            .not_valid_after(_NOW + datetime.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(k, hashes.SHA256()))
    return k, cert


def make_leaf(cn, ca_key, ca_cert):
    k = _key()
    cert = (x509.CertificateBuilder().subject_name(_name(cn)).issuer_name(ca_cert.subject)
            .public_key(k.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(_NOW - datetime.timedelta(days=1))
            .not_valid_after(_NOW + datetime.timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName(
                [x509.DNSName(cn), x509.DNSName("localhost"),
                 x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(ca_key, hashes.SHA256()))
    return k, cert


def _write_key(path, k):
    with open(path, "wb") as f:
        f.write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                serialization.NoEncryption()))


def _write_cert(path, c):
    with open(path, "wb") as f:
        f.write(c.public_bytes(serialization.Encoding.PEM))


def generate_all(certdir: str):
    os.makedirs(certdir, exist_ok=True)
    ca_k, ca_c = make_ca("capm-ca")
    _write_key(f"{certdir}/ca.key", ca_k); _write_cert(f"{certdir}/ca.crt", ca_c)
    for name in ("registry", "verifier", "client"):
        k, c = make_leaf(name, ca_k, ca_c)
        _write_key(f"{certdir}/{name}.key", k); _write_cert(f"{certdir}/{name}.crt", c)
    # rogue CA + rogue client (for the cert-mismatch rejection test)
    rca_k, rca_c = make_ca("rogue-ca")
    _write_cert(f"{certdir}/rogue_ca.crt", rca_c)
    rk, rc = make_leaf("client", rca_k, rca_c)
    _write_key(f"{certdir}/rogue_client.key", rk); _write_cert(f"{certdir}/rogue_client.crt", rc)
    return certdir
