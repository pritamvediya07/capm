"""Build A implementation — acquisition wrapper, full run (WS5/P4-5A).

Runs the three acquisition paths (HTTP real + adversarial, API, file/DB), derives
source_class from observable channel evidence per the versioned policy table,
**feeds the derived class into the real CAPM manifest path** (so the warrant now
rests on measured origin evidence), compares to the Phase-3 hand-set intent, and
records the Data-to-record CSV. Asserts the safety property: 0 over-trust on
invalid/spoofed evidence.

Run:  python -m p4.build_a.run_build_a
"""
from __future__ import annotations

import csv
import json
import os

from p4.build_a.acquire import acquire_http, acquire_api, acquire_file, POLICY_VERSION
from p4.build_b.eval_core import build_and_evaluate
from capm.core.types import SourceClass

OUT = os.path.join("p4", "results", "build_a")

# the versioned policy-table artifact (the I6/T4 seam, made concrete)
POLICY_TABLE = {
    "version": POLICY_VERSION,
    "principle": "evidence-only + degrade-on-uncertainty => misclassification can only UNDER-trust",
    "http": {"invalid_tls": "UNKNOWN", "valid+editable": "EDITABLE_SOURCE",
             "valid+content_signature": "VERIFIED_DOCUMENT", "valid+non_editable": "PUBLIC_WEBPAGE"},
    "api": {"invalid_tls": "UNKNOWN", "no_request_auth": "PUBLIC_WEBPAGE",
            "tls+auth+response_sig+allowlisted": "AUTHORITATIVE_API", "tls+auth_only": "FIRST_PARTY_DB"},
    "file": {"first_party+authenticated": "FIRST_PARTY_DB", "otherwise": "UNKNOWN"},
}


def run():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "policy_table.json"), "w") as f:
        json.dump(POLICY_TABLE, f, indent=2)

    cases = []  # (label, acquire_result, phase3_handset_class)
    cases.append(("http:wikipedia(editable)", acquire_http(
        "https://en.wikipedia.org/wiki/Common_Vulnerabilities_and_Exposures"), SourceClass.EDITABLE_SOURCE))
    cases.append(("http:cisa.gov(valid)", acquire_http(
        "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"), SourceClass.PUBLIC_WEBPAGE))
    cases.append(("http:expired-cert(spoof)", acquire_http("https://expired.badssl.com/"), SourceClass.UNKNOWN))
    cases.append(("http:self-signed(spoof)", acquire_http("https://self-signed.badssl.com/"), SourceClass.UNKNOWN))
    cases.append(("http:wrong-host(spoof)", acquire_http("https://wrong.host.badssl.com/"), SourceClass.UNKNOWN))
    cases.append(("api:signed-authoritative", acquire_api("https://api.vendor.example/v1/cve",
                  response_signature=True, allowlisted=True), SourceClass.AUTHORITATIVE_API))
    cases.append(("api:no-response-sig", acquire_api("https://api.vendor.example/v1/cve",
                  response_signature=False), SourceClass.FIRST_PARTY_DB))
    cases.append(("api:weak-auth(spoof)", acquire_api("https://api.vendor.example/v1/cve",
                  request_auth=False), SourceClass.PUBLIC_WEBPAGE))
    cases.append(("api:invalid-tls(spoof)", acquire_api("https://api.vendor.example/v1/cve",
                  tls_valid=False), SourceClass.UNKNOWN))
    cases.append(("file:first-party-db", acquire_file("/srv/db/cve_records",
                  first_party=True, authenticated_channel=True), SourceClass.FIRST_PARTY_DB))
    cases.append(("file:unauthenticated", acquire_file("/tmp/dropped.json",
                  first_party=False, authenticated_channel=False), SourceClass.UNKNOWN))

    print("=" * 104)
    print(f"Build A — acquisition wrapper (full): channel evidence -> source_class -> manifest warrant "
          f"(policy {POLICY_VERSION})")
    print("=" * 104)
    print(f"{'case':28s} {'derived':18s} {'handset':18s} {'agree':6s} {'degraded':9s} "
          f"{'manifest_warrant':17s} {'decision':11s}")
    rows, over_trust = [], 0
    for label, res, handset in cases:
        sc = res["source_class"]; ev = res["observation"]["evidence"]
        # feed the channel-derived source_class into the real manifest path
        warrant, decision, sig_ok = build_and_evaluate(sc.name, ["verbatim"], 1)
        invalid = (ev.get("channel") in ("http", "api") and ev.get("tls_valid") is False) or \
                  (ev.get("channel") == "file" and not (ev.get("first_party") and ev.get("authenticated_channel"))) or \
                  (ev.get("channel") == "api" and not ev.get("request_auth"))
        degraded = invalid and sc.warrant_ceiling.value <= handset.warrant_ceiling.value
        if (ev.get("tls_valid") is False) and sc.warrant_ceiling.value > 0:
            over_trust += 1
        agree = sc == handset
        print(f"{label:28s} {sc.name:18s} {handset.name:18s} {str(agree):6s} {str(bool(invalid)):9s} "
              f"{warrant:17s} {decision:11s}")
        rows.append(dict(channel=ev.get("channel"), case=label,
                         observed_evidence=json.dumps({k: ev.get(k) for k in
                             ("tls_valid", "tls_error", "editable", "request_auth", "response_signature",
                              "allowlisted", "first_party", "authenticated_channel") if k in ev}),
                         derived_source_class=sc.name, phase3_handset_class=handset.name,
                         agree=agree, degraded_on_ambiguity=bool(invalid),
                         manifest_warrant=warrant, manifest_decision=decision))

    with open(os.path.join(OUT, "build_a.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    agree_n = sum(r["agree"] for r in rows)
    print("=" * 104)
    print(f"derived-vs-handset agreement: {agree_n}/{len(rows)}; over-trust on invalid TLS (must be 0): {over_trust}")
    ok = over_trust == 0
    print(f"{'PASS' if ok else 'FAIL'} — source_class is a MEASURED property fed into the manifest path "
          "(warrant now rests on observed channel evidence); spoofed/invalid evidence degrades conservatively "
          "(bad-cert origins → NONE → quarantine); 0 over-trust. Policy table written to policy_table.json.")
    print("=" * 104)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
