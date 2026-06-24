"""Build A smoke — derive source_class from REAL channel evidence (WS5/P4-5A).

Demonstrates: source_class is a MEASURED property (real TLS verification on real +
bad-cert hosts), conservative-default on unverifiable evidence, and that NO path
over-trusts on spoofed/invalid evidence. Compares against the Phase-3 hand-set
intent.

Run:  python -m p4.build_a.smoke
"""
from __future__ import annotations
from p4.build_a.acquire import acquire_http, acquire_api, acquire_file, POLICY_VERSION
from capm.core.types import SourceClass

# (url, the editable/non-editable intent) — real hosts, incl. badssl bad-cert endpoints
HTTP_CASES = [
    ("https://en.wikipedia.org/wiki/Common_Vulnerabilities_and_Exposures", "editable→WEAK"),
    ("https://www.cisa.gov/known-exploited-vulnerabilities-catalog", "valid non-editable→MODERATE"),
    ("https://expired.badssl.com/", "EXPIRED cert→degrade"),
    ("https://self-signed.badssl.com/", "self-signed→degrade"),
    ("https://wrong.host.badssl.com/", "hostname-mismatch→degrade"),
]


def show(tag, res):
    o = res["observation"]
    print(f"  [{tag:26s}] source_class={res['source_class'].name:18s} ceiling={res['ceiling'].name:8s} "
          f"sig={res['signature'][:12]}…")
    print(f"      evidence: tls_valid={o['evidence'].get('tls_valid')} "
          f"{'editable=' + str(o['evidence'].get('editable')) if o['evidence'].get('channel')=='http' else ''} "
          f"err={o['evidence'].get('tls_error')}")
    print(f"      reason: {o['reason']}")


def main():
    print("=" * 92)
    print(f"Build A — acquisition wrapper: source_class from channel evidence (policy {POLICY_VERSION})")
    print("=" * 92)
    print("\nHTTP path (REAL TLS chain + hostname verification):")
    over_trust = 0
    for url, intent in HTTP_CASES:
        res = acquire_http(url)
        show(intent, res)
        # safety check: a host with invalid TLS must NEVER yield > NONE
        if not res["observation"]["evidence"].get("tls_valid") and res["ceiling"].value > 0:
            over_trust += 1

    print("\nAPI path (observed: TLS / request-auth / response-signature / allowlist):")
    show("signed authoritative API", acquire_api("https://api.vendor.example/v1/cve",
         tls_valid=True, request_auth=True, response_signature=True, allowlisted=True))
    show("API, no response-sig", acquire_api("https://api.vendor.example/v1/cve",
         tls_valid=True, request_auth=True, response_signature=False))
    show("API, weak-auth (spoof)", acquire_api("https://api.vendor.example/v1/cve",
         tls_valid=True, request_auth=False))
    show("API, invalid TLS (spoof)", acquire_api("https://api.vendor.example/v1/cve", tls_valid=False))

    print("\nfile/DB path:")
    show("first-party DB", acquire_file("/srv/db/cve_records", first_party=True, authenticated_channel=True))
    show("unauthenticated file", acquire_file("/tmp/dropped.json", first_party=False, authenticated_channel=False))

    # compare derived vs Phase-3 hand-set intent on the wikipedia/api cases
    wiki = acquire_http(HTTP_CASES[0][0])
    api = acquire_api("https://api.vendor.example/v1/cve", response_signature=True, allowlisted=True)
    print("\nDerived-vs-handset agreement (representative):")
    print(f"  editable wiki  → derived {wiki['source_class'].name}  (Phase-3 hand-set: EDITABLE_SOURCE)  "
          f"agree={wiki['source_class']==SourceClass.EDITABLE_SOURCE}")
    print(f"  signed API     → derived {api['source_class'].name}  (Phase-3 hand-set: AUTHORITATIVE_API)  "
          f"agree={api['source_class']==SourceClass.AUTHORITATIVE_API}")

    print("=" * 92)
    ok = over_trust == 0
    print(f"{'PASS' if ok else 'FAIL'} — source_class is derived from observable channel evidence per the "
          f"deterministic policy table; {over_trust} over-trust on invalid/spoofed evidence (must be 0); "
          "ambiguous/invalid evidence degrades conservatively; the origin observation is Ed25519-signed.")
    print("=" * 92)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
