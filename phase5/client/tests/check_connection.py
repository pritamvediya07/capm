#!/usr/bin/env python3
"""Barebones connectivity check for the CAPM-P5 test server — STANDARD LIBRARY ONLY.

Hits /healthz, /ping, /v1/info and POST /v1/echo on the target URL and reports
pass/fail per endpoint. Use this from the client machine to confirm it can reach
the server (firewall / port / routing).

Usage:  python3 check_connection.py [--url http://HOST:PORT] [--timeout 10]
Exit:   0 if every check returns HTTP 200, else 1.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def call(method: str, url: str, body=None, timeout: float = 10.0):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode())
        return resp.status, payload, (time.time() - t0) * 1000.0


def main() -> int:
    ap = argparse.ArgumentParser(description="CAPM-P5 connectivity check")
    ap.add_argument("--url", default="http://localhost:8000",
                    help="base URL of the test server")
    ap.add_argument("--timeout", type=float, default=10.0)
    args = ap.parse_args()
    base = args.url.rstrip("/")

    checks = [
        ("GET", "/healthz", None),
        ("GET", "/ping", None),
        ("GET", "/v1/info", None),
        ("POST", "/v1/echo", {"message": "ping from client"}),
    ]

    print(f"checking {base} ...")
    ok = True
    for method, path, body in checks:
        try:
            status, payload, ms = call(method, base + path, body, args.timeout)
            ok &= (status == 200)
            mark = "OK " if status == 200 else "ERR"
            print(f"  [{mark}] {method:4s} {path:11s} {status} {ms:6.1f}ms  {json.dumps(payload)}")
        except (urllib.error.URLError, OSError, ValueError) as e:
            ok = False
            print(f"  [ERR] {method:4s} {path:11s} FAILED: {e}")

    print("connection OK" if ok else "connection FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
