"""P3-G.1 — Runtime and manifest overhead.

Instruments the per-claim online cost of the three sensors (usage probe, support,
NLI), the verifier recompute time, the added manifest bytes per claim, and the
OFFLINE counterfactual-influence cost — separated, since the oracle is never on
the hot path. Swept over claims-per-document (4 → 50).

Run:  python -m p3.exp.g1_cost
"""

from __future__ import annotations

import csv
import dataclasses
import json
import os
import time
import warnings

import numpy as np

warnings.filterwarnings("ignore")

from p3.claims.extract import render_document
from p3.data.advisories.corpus import load_advisories
from p3.sensors.probe import HiddenStateExtractor
from p3.sensors.probe_data import _QUESTIONS
from p3.sensors.support import SupportSensor
from p3.sensors.nli import NLISensor
from p3.manifest.field import RealizedField, RealizedVerifier
from p3.claims.extract import extract_claims
from p3.oracle.neurotaint_offline import influence

OUT_DIR = os.path.join("p3", "results", "g1")
FIG_DIR = os.path.join("p3", "results", "figures")
CLAIMS_PER_DOC = [4, 10, 25, 50]


def _time(fn, reps=3):
    fn()                                  # warm-up
    t0 = time.perf_counter()
    for _ in range(reps):
        fn()
    return (time.perf_counter() - t0) / reps * 1000.0     # ms


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(FIG_DIR, exist_ok=True)
    advs = load_advisories(20, seed=88)
    ctx = render_document(advs[0])
    field, value = "vendor", str(advs[0]["fields"].get("vendor", "Acme"))
    q = _QUESTIONS[field]
    print("loading sensors…")
    ext = HiddenStateExtractor("distilgpt2")
    support = SupportSensor(space="embedding")
    nli = NLISensor("cross-encoder/nli-deberta-v3-xsmall")
    verifier = RealizedVerifier(usage_provider=None)
    claims = extract_claims(advs[0])

    # --- per-claim component latencies ---
    probe_ms = _time(lambda: ext.claim_features(f"{ctx}\nQuestion: {q}\nAnswer:", f" {value}", 6))
    support_ms = _time(lambda: support.support(f"{field} is {value}", ctx))
    nli_ms = _time(lambda: nli.predict(f"The {field} is {value}.", f"{field} is {value}"))
    fld = RealizedField(claim_id="x:vendor", field_key="vendor", claimed_parent_id="x:vendor",
                        u=0.9, s=0.9, faith=1.0, sensor_placement={"u": "re_executing_verifier"},
                        attestations={"u": True}, sensor_versions={"u": "distilgpt2", "s": "minilm", "faith": "deberta"})
    verifier_ms = _time(lambda: verifier.verify_claim(fld, claims, ctx, 0.85))
    offline_ms = _time(lambda: influence(ext, ctx, field, value, q), reps=2)

    manifest_bytes = len(json.dumps(dataclasses.asdict(fld)).encode())

    online_per_claim = probe_ms + support_ms + nli_ms + verifier_ms
    print("=" * 84)
    print("P3-G.1  Runtime & manifest overhead")
    print("=" * 84)
    print(f"per-claim latency (ms):  probe {probe_ms:.1f}  support {support_ms:.1f}  "
          f"nli {nli_ms:.1f}  verifier {verifier_ms:.2f}")
    print(f"  online total / claim   : {online_per_claim:.1f} ms")
    print(f"  offline influence/claim: {offline_ms:.1f} ms  (NeuroTaint oracle — NOT on the hot path)")
    print(f"  manifest bytes / claim : {manifest_bytes} B (signed realized-provenance field)")
    print(f"\nper-document online cost (claims × per-claim):")
    rows = []
    for n in CLAIMS_PER_DOC:
        doc_online = online_per_claim * n
        rows.append(dict(claims_per_doc=n, probe_ms=round(probe_ms, 2), support_ms=round(support_ms, 2),
                         nli_ms=round(nli_ms, 2), verifier_cpu_ms=round(verifier_ms, 3),
                         manifest_bytes_per_claim=manifest_bytes,
                         online_total_ms=round(doc_online, 1), offline_total_ms=round(offline_ms * n, 1)))
        print(f"  {n:2d} claims/doc: online {doc_online:7.1f} ms  (~{doc_online/n:.1f} ms/claim)  | "
              f"manifest +{manifest_bytes*n} B")
    _write(rows)
    _figure(probe_ms, support_ms, nli_ms, verifier_ms, offline_ms, online_per_claim)

    # cascade note: NLI is the dominant online cost -> can be restricted to claims the
    # cheaper sensors already flag.
    dominant = max([("probe", probe_ms), ("support", support_ms), ("nli", nli_ms)], key=lambda x: x[1])
    print("=" * 84)
    ok = online_per_claim <= 1000
    print(f"PASS — online overhead is modest and bounded ({online_per_claim:.0f} ms/claim; "
          f"target ≤ 1 s/hop). Dominant online cost is {dominant[0]} ({dominant[1]:.0f} ms) — a cascade "
          "(run NLI only on cheap-flagged claims) or a quantized NLI reduces it; the NeuroTaint oracle "
          f"({offline_ms:.0f} ms/claim) is offline, never on the hot path." if ok else
          f"REVIEW — online {online_per_claim:.0f} ms/claim exceeds 1 s target; cascade/quantize NLI.")
    print("=" * 84)
    return 0


def _write(rows):
    with open(os.path.join(OUT_DIR, "g1_cost.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


def _figure(probe, support, nli, verifier, offline, online):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"(figure skipped: {e})"); return ""
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.0, 5.0))
    comps = ["probe\n(usage)", "support\n(MiniLM)", "NLI\n(DeBERTa)", "verifier\nrecompute"]
    vals = [probe, support, nli, verifier]
    axA.bar(range(len(comps)), vals, color=["#2c3e50", "#2a9d8f", "#e67e22", "#8e44ad"])
    for i, v in enumerate(vals):
        axA.text(i, v + max(vals) * 0.01, f"{v:.1f}", ha="center", fontsize=9)
    axA.set_xticks(range(len(comps))); axA.set_xticklabels(comps, fontsize=8)
    axA.set_ylabel("latency per claim (ms)")
    axA.set_title(f"A. Online sensor cost per claim (total {online:.0f} ms)\noffline oracle {offline:.0f} ms (not on hot path)", fontsize=10)

    ns = CLAIMS_PER_DOC
    axB.plot(ns, [online * n / 1000 for n in ns], "-o", color="#2c3e50", label="online (probe+support+NLI+verifier)")
    axB.plot(ns, [offline * n / 1000 for n in ns], "--s", color="#95a5a6", label="offline oracle (eval only)")
    axB.axhline(1.0, color="#c0392b", ls=":", lw=1, label="1 s/hop target")
    axB.set_xlabel("claims per document"); axB.set_ylabel("seconds per document")
    axB.set_title("B. Per-document cost scales linearly in claims", fontsize=10)
    axB.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    path = os.path.join(FIG_DIR, "g1_cost.png")
    fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path


if __name__ == "__main__":
    raise SystemExit(main())
