"""p3/data/advisories/corpus.py — the structured CVE corpus (real CISA-KEV).

Loads real advisories from the CISA Known-Exploited-Vulnerabilities feed and
normalizes each into the Phase-3 structured-record schema (``record_id`` +
``fields``). The feed is cached on disk so the corpus is reproducible offline
after the first fetch.

Why KEV. It is a real, authoritative, *structured* vulnerability feed (every
field is a genuine attested value: vendor, product, CWE, dates, the
ransomware-use flag, the required-action text). Those crisp fields are exactly
what Step 0 needs — load-bearing claims whose loss / contradiction / fabrication
have unambiguous ground truth.

CVSS note (honesty). KEV does not carry the CVSS base score / severity band
(NVD does, but NVD's API was unreachable at build time). ``cvss_score`` /
``cvss_band`` are therefore left ``None`` here and enriched separately when NVD
is reachable; the gap-existence experiment (P3-A.1) does not depend on them —
it injects contradictions on the real categorical / boolean / identifier / date
fields. The CVSS-band abstraction-vs-contradiction case is exercised in P3-C.2.
"""

from __future__ import annotations

import json
import os
import random
import socket
import urllib.request

_HERE = os.path.dirname(__file__)
_RAW_DIR = os.path.join(_HERE, "_raw")
_KEV_CACHE = os.path.join(_RAW_DIR, "kev.json")
_KEV_URL = ("https://www.cisa.gov/sites/default/files/feeds/"
            "known_exploited_vulnerabilities.json")


def _fetch_kev() -> dict:
    """Download KEV (cached). Returns the parsed feed."""
    if os.path.exists(_KEV_CACHE):
        with open(_KEV_CACHE) as f:
            return json.load(f)
    os.makedirs(_RAW_DIR, exist_ok=True)
    socket.setdefaulttimeout(30)
    req = urllib.request.Request(_KEV_URL, headers={"User-Agent": "capm-research/0.1"})
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    with open(_KEV_CACHE, "w") as f:
        json.dump(data, f)
    return data


def _normalize(entry: dict) -> dict:
    """One raw KEV entry -> a Phase-3 structured record (real fields only)."""
    cwes = entry.get("cwes") or []
    cwe = cwes[0] if cwes else None
    ransom = entry.get("knownRansomwareCampaignUse", "Unknown")
    fields = {
        "cve_id": entry.get("cveID"),
        "vendor": entry.get("vendorProject"),
        "product": entry.get("product"),
        "vulnerability_name": entry.get("vulnerabilityName"),
        "cwe": cwe,
        "cvss_score": None,     # enriched from NVD when reachable (see module note)
        "cvss_band": None,
        "date_added": entry.get("dateAdded"),
        "due_date": entry.get("dueDate"),
        "ransomware_use": ransom,
        "required_action": entry.get("requiredAction"),
        "short_description": entry.get("shortDescription"),
    }
    return {
        "record_id": entry.get("cveID"),
        "source_type": "cve_advisory",
        "provenance": "CISA-KEV",
        "fields": fields,
    }


def load_advisories(n: int = 150, seed: int = 0,
                    require_fields: tuple[str, ...] = (
                        "cve_id", "vendor", "product", "cwe",
                        "ransomware_use", "due_date", "required_action")) -> list[dict]:
    """Return a deterministic sample of ``n`` normalized real advisories.

    Only records that carry every field in ``require_fields`` are eligible, so
    every sampled advisory has the full set of load-bearing claims the
    transformation generator needs (no ragged records).
    """
    feed = _fetch_kev()
    records = [_normalize(e) for e in feed.get("vulnerabilities", [])]
    eligible = [r for r in records
                if all(r["fields"].get(k) for k in require_fields)]
    eligible.sort(key=lambda r: r["record_id"])      # stable order before sampling
    rng = random.Random(seed)
    if n >= len(eligible):
        return eligible
    return rng.sample(eligible, n)


def corpus_stats() -> dict:
    feed = _fetch_kev()
    return {"kev_total": len(feed.get("vulnerabilities", [])),
            "catalog_version": feed.get("catalogVersion"),
            "date_released": feed.get("dateReleased")}


if __name__ == "__main__":
    print("KEV stats:", corpus_stats())
    sample = load_advisories(n=5, seed=0)
    print(f"sampled {len(sample)} advisories; first:")
    print(json.dumps(sample[0], indent=2)[:900])
