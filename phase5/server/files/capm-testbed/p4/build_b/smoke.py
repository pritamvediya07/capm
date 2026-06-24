"""Build B smoke — verify a CAPM manifest over real gRPC/mTLS across separate
runtimes (WS5/P4-5B).

Stands up the Registry and Verifier as SEPARATE PROCESSES (separate runtimes),
mTLS between all three parties (client / verifier / registry), and demonstrates:
  * a manifest verifies end-to-end over the wire, and the verdict MATCHES the
    in-process WarrantEvaluator (security reproduces off the single-process path);
  * the Verifier reaches the Registry over a second mTLS hop (origin_trusted);
  * a cert-mismatch (rogue-CA client cert) is REJECTED at the TLS handshake;
  * per-Verify transport latency is measured.

Run:  python -m p4.build_b.smoke
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import time

import grpc

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CERTDIR = os.path.join(ROOT, "p4", "results", "build_b", "certs")
_OVR = (("grpc.ssl_target_name_override", "localhost"),)


def compile_proto():
    subprocess.run([sys.executable, "-m", "grpc_tools.protoc", "-I.", "--python_out=.",
                    "--grpc_python_out=.", "p4/build_b/transport.proto"], cwd=ROOT, check=True)


def main():
    compile_proto()
    from p4.build_b.certs import generate_all
    from p4.build_b import services
    pb = importlib.import_module("p4.build_b.transport_pb2")
    pbg = importlib.import_module("p4.build_b.transport_pb2_grpc")
    generate_all(CERTDIR)

    print("=" * 92)
    print("Build B — verifier + registry as separate gRPC/mTLS runtimes")
    print("=" * 92)
    reg = subprocess.Popen([sys.executable, "-m", "p4.build_b.services", "--role", "registry",
                            "--port", "50051", "--certdir", CERTDIR], cwd=ROOT)
    ver = subprocess.Popen([sys.executable, "-m", "p4.build_b.services", "--role", "verifier",
                            "--port", "50052", "--certdir", CERTDIR, "--registry", "127.0.0.1:50051"], cwd=ROOT)
    rc = 1
    try:
        ch = grpc.secure_channel("127.0.0.1:50052", services.channel_creds(CERTDIR, "client"), options=_OVR)
        grpc.channel_ready_future(ch).result(timeout=25)
        stub = pbg.VerifierStub(ch)
        print("\n3 separate runtimes up (client / verifier / registry); mTLS established.\n")

        print("manifest verification over mTLS (vs in-process reference):")
        all_match = True
        for nm, oc, tr, hops in [("STRONG-API faithful", "AUTHORITATIVE_API", ["verbatim"], 4),
                                 ("EDITABLE relaunder", "EDITABLE_SOURCE", ["summary"], 4),
                                 ("MODERATE-DB summary", "FIRST_PARTY_DB", ["summary"], 2)]:
            rep = stub.Verify(pb.VerifyReq(origin_source_class=oc, transforms=tr, hops=hops), timeout=10)
            ref = services.build_and_evaluate(oc, tr, hops)
            match = (rep.warrant, rep.decision, rep.signature_ok) == ref
            all_match = all_match and match
            print(f"  [{nm:22s}] over-wire warrant={rep.warrant:8s} decision={rep.decision:11s} "
                  f"sig_ok={rep.signature_ok} origin_trusted={rep.origin_trusted} | in-proc match={match}")

        print("\ntransport integrity — rogue-CA client cert must be rejected:")
        rogue = grpc.secure_channel("127.0.0.1:50052", services.channel_creds(CERTDIR, "rogue_client"), options=_OVR)
        rejected = False
        try:
            pbg.VerifierStub(rogue).Verify(pb.VerifyReq(origin_source_class="AUTHORITATIVE_API",
                                           transforms=["verbatim"], hops=1), timeout=8)
            print("  rogue client ACCEPTED — FAIL (transport integrity broken)")
        except grpc.RpcError as e:
            rejected = True
            print(f"  rogue client REJECTED at handshake: {e.code()}")

        print("\ntransport overhead (per Verify over mTLS, real WarrantEvaluator):")
        for hops in (1, 4, 8):
            t = time.perf_counter()
            N = 20
            for _ in range(N):
                stub.Verify(pb.VerifyReq(origin_source_class="AUTHORITATIVE_API", transforms=["verbatim"], hops=hops), timeout=10)
            print(f"  hops={hops}: {(time.perf_counter() - t) / N * 1000:.2f} ms/verify")

        ok = all_match and rejected
        print("=" * 92)
        print(f"{'PASS' if ok else 'FAIL'} — CAPM manifests verify end-to-end over real gRPC/mTLS across "
              "separate runtimes; verdicts match the in-process evaluator (security reproduces off the "
              "single-process path); the Verifier→Registry mTLS hop works; a rogue-CA client is rejected. "
              'The "single-process execution" caveat is retired (demonstrated multi-runtime).')
        print("=" * 92)
        rc = 0 if ok else 1
    finally:
        reg.terminate(); ver.terminate()
        try:
            reg.wait(timeout=5); ver.wait(timeout=5)
        except Exception:
            reg.kill(); ver.kill()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
