"""Build B services — Registry + Verifier as separate gRPC/mTLS runtimes (WS5/P4-5B).

The Verifier runs the REAL WarrantEvaluator in its own process and calls the
Registry (another process) over mTLS for the origin signer's trust — replacing the
Phase-3 in-process recursive calls with genuine multi-runtime transport.
"""
from __future__ import annotations

from concurrent import futures

import grpc

from p4.build_b import transport_pb2 as pb
from p4.build_b import transport_pb2_grpc as pbg
from p4.build_b.eval_core import build_and_evaluate


def _ovr(host):
    return (("grpc.ssl_target_name_override", host),)


class RegistryServicer(pbg.RegistryServicer):
    def Trusts(self, request, context):
        return pb.TrustReply(trusted=request.did.startswith("did:capm:"))


class VerifierServicer(pbg.VerifierServicer):
    def __init__(self, registry_addr, reg_creds):
        self.registry_addr = registry_addr
        self.creds = reg_creds

    def Verify(self, request, context):
        w, d, sig = build_and_evaluate(request.origin_source_class, list(request.transforms), request.hops)
        origin_trusted = False
        try:                                            # inter-service mTLS call to the Registry runtime
            host = self.registry_addr.rsplit(":", 1)[0]
            with grpc.secure_channel(self.registry_addr, self.creds, options=_ovr(host)) as ch:
                origin_trusted = pbg.RegistryStub(ch).Trusts(pb.TrustReq(did="did:capm:origin"), timeout=5).trusted
        except Exception as e:
            context.set_details(f"registry call failed: {e}")
        return pb.VerifyReply(warrant=w, decision=d, signature_ok=sig, origin_trusted=origin_trusted, hops=request.hops)


def _read(p):
    with open(p, "rb") as f:
        return f.read()


def server_creds(certdir, name):
    return grpc.ssl_server_credentials([(_read(f"{certdir}/{name}.key"), _read(f"{certdir}/{name}.crt"))],
                                       root_certificates=_read(f"{certdir}/ca.crt"), require_client_auth=True)


def channel_creds(certdir, name):
    return grpc.ssl_channel_credentials(root_certificates=_read(f"{certdir}/ca.crt"),
                                        private_key=_read(f"{certdir}/{name}.key"),
                                        certificate_chain=_read(f"{certdir}/{name}.crt"))


def serve(role, port, certdir, registry_addr=None):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    if role == "registry":
        pbg.add_RegistryServicer_to_server(RegistryServicer(), server)
    else:
        pbg.add_VerifierServicer_to_server(VerifierServicer(registry_addr, channel_creds(certdir, "verifier")), server)
    server.add_secure_port(f"0.0.0.0:{port}", server_creds(certdir, role))
    server.start()
    print(f"{role} serving on {port}", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--certdir", required=True)
    ap.add_argument("--registry", default=None)
    a = ap.parse_args()
    serve(a.role, a.port, a.certdir, a.registry)
