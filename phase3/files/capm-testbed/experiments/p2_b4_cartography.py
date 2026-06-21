"""P2-B4 — Residual-Risk Cartography.

The pay-off of Goal 2. B1 proved the residual is *only* origin-class capture;
B3 showed an attacker optimises within it. B4 maps the consequence for a
defender: CAPM **collapses the attack surface** from "every agent and every
source in the mesh" down to "the few high-warrant origins" — a small, *namable,
hardenable* set of chokepoints.

For each of several network topologies (star hub, deep chains, wide fan,
multi-org mesh):

* **Pre-CAPM surface** = every node an attacker could subvert = all relay agents
  + all sources. (Pre-CAPM, any relay can launder and any source can inject.)
* **Post-CAPM surface** = only the sources whose warrant ceiling clears the
  evaluator's ACCEPT threshold — verified against the **real `WarrantEvaluator`**.
  By Lemma 1 relays cannot launder, and by the origin cap low-warrant sources
  cannot be accepted, so they all drop out.
* **Collapse ratio** = post / pre (small ⇒ large collapse).
* **Top-3 coverage** = the fraction of high-value claims that route through the
  three highest-reach high-warrant origins — the hardening priority list.

Run:
    python3 -m experiments.p2_b4_cartography
"""

from __future__ import annotations

import csv
import os
import statistics

from capm.benchmark import stats
from capm.core.types import SourceClass, TransformationType
from capm.ecosystem.graph import TOPOLOGY_GENERATORS, Topology
from capm.identity.credentials import AgentIdentity, CredentialRegistry
from capm.manifest.capm_manifest import CAPMManifest
from capm.warrant.evaluator import Decision, EvaluatorPolicy, WarrantEvaluator

OUT_DIR = os.path.join("results", "p2", "b4")
_CLOCK = 1_700_000_000.0
SEEDS = list(range(30))

# Ground "does this source clear the ACCEPT threshold?" in the real evaluator.
_accept_cache: dict[SourceClass, bool] = {}


def _capm_accepts(cls: SourceClass) -> bool:
    if cls in _accept_cache:
        return _accept_cache[cls]
    reg = CredentialRegistry()
    ident = AgentIdentity(did="did:capm:src", org="org-0")
    reg.register(ident)
    m = CAPMManifest()
    m.append_segment(identity=ident, content="x", transformation=TransformationType.VERBATIM,
                     from_org="org-principal", to_org="org-0",
                     origin_source_class=cls, asserted_origin_warrant=cls.warrant_ceiling,
                     timestamp=_CLOCK)
    ok = WarrantEvaluator(reg, EvaluatorPolicy()).evaluate(m).decision == Decision.ACCEPT
    _accept_cache[cls] = ok
    return ok


def analyse(topo: Topology) -> dict:
    # post-CAPM surface: sources the real evaluator would ACCEPT if captured
    chokepoints = [s for s in topo.sources if _capm_accepts(s.source_class)]
    pre = topo.pre_capm_surface()
    post = len(chokepoints)
    collapse = post / pre if pre else 0.0

    # high-value claims routed through the chokepoints, and top-3 coverage
    hv_reach = sorted((topo.reach[s.node_id] for s in chokepoints), reverse=True)
    total_hv_claims = sum(hv_reach)
    top3 = sum(hv_reach[:3])
    top3_cov = (top3 / total_hv_claims) if total_hv_claims else 0.0

    return {
        "topology": topo.name,
        "n_agents": topo.n_agents, "n_sources": len(topo.sources),
        "n_principals": topo.n_principals,
        "pre_surface": pre, "post_surface": post,
        "collapse_ratio": collapse,
        "collapse_factor": (pre / post) if post else float("inf"),
        "n_chokepoints": post,
        "total_high_value_claims": total_hv_claims,
        "top3_coverage": top3_cov,
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 88)
    print("P2-B4 — Residual-Risk Cartography")
    print("=" * 88)
    accept_map = {c.value: _capm_accepts(c) for c in SourceClass}
    print(f"Sources that clear ACCEPT (post-CAPM surface members): "
          f"{[k for k,v in accept_map.items() if v]}")

    rows = []          # one row per (topology, seed)
    for name in TOPOLOGY_GENERATORS:
        for seed in SEEDS:
            topo = TOPOLOGY_GENERATORS[name](seed=seed)
            rows.append({**analyse(topo), "seed": seed})

    # aggregate per topology
    print(f"\n{'topology':<18}{'pre':>6}{'post':>6}{'collapse':>10}{'factor':>9}"
          f"{'top3_cov':>10}")
    print("-" * 88)
    summary = []
    for name in TOPOLOGY_GENERATORS:
        rs = [r for r in rows if r["topology"] == name]
        pre = statistics.mean(r["pre_surface"] for r in rs)
        post = statistics.mean(r["post_surface"] for r in rs)
        cr = [r["collapse_ratio"] for r in rs]
        cr_pt, cr_lo, cr_hi = stats.bootstrap_ci(cr, seed=5)
        factor = statistics.mean(r["collapse_factor"] for r in rs)
        t3 = [r["top3_coverage"] for r in rs]
        t3_pt, t3_lo, t3_hi = stats.bootstrap_ci(t3, seed=5)
        print(f"{name:<18}{pre:>6.0f}{post:>6.1f}{cr_pt:>10.3f}{factor:>9.1f}x"
              f"{t3_pt:>10.2f}")
        summary.append({
            "topology": name, "mean_pre_surface": round(pre, 1),
            "mean_post_surface": round(post, 2),
            "mean_collapse_ratio": round(cr_pt, 4),
            "collapse_ratio_lo": round(cr_lo, 4), "collapse_ratio_hi": round(cr_hi, 4),
            "mean_collapse_factor": round(factor, 2),
            "mean_top3_coverage": round(t3_pt, 4),
            "top3_lo": round(t3_lo, 4), "top3_hi": round(t3_hi, 4),
            "n_seeds": len(SEEDS),
        })
    print("-" * 88)

    avg_collapse = statistics.mean(r["collapse_ratio"] for r in rows)
    avg_factor = statistics.mean(r["collapse_factor"] for r in rows
                                 if r["collapse_factor"] != float("inf"))
    avg_top3 = statistics.mean(r["top3_coverage"] for r in rows)
    print(f"\nAVERAGE collapse ratio (all topologies): {avg_collapse:.4f} "
          f"(≈ {avg_factor:.1f}× surface reduction)")
    print(f"AVERAGE top-3 chokepoint coverage     : {avg_top3:.2%} of high-value claims")

    # CSVs
    with open(os.path.join(OUT_DIR, "cartography.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    summary.append({
        "topology": "AVERAGE", "mean_pre_surface": "",
        "mean_post_surface": "", "mean_collapse_ratio": round(avg_collapse, 4),
        "collapse_ratio_lo": "", "collapse_ratio_hi": "",
        "mean_collapse_factor": round(avg_factor, 2),
        "mean_top3_coverage": round(avg_top3, 4), "top3_lo": "", "top3_hi": "",
        "n_seeds": len(SEEDS) * len(TOPOLOGY_GENERATORS)})
    with open(os.path.join(OUT_DIR, "cartography_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader(); w.writerows(summary)

    print("\nFinding: CAPM collapses the attack surface to a small set of "
          "high-warrant origins; a handful of chokepoints carry most high-value "
          "claims — exactly the hardening target B3 says to protect (raise their "
          "integrity / couple warrant↔integrity).")
    print(f"CSV: {OUT_DIR}/cartography.csv ; {OUT_DIR}/cartography_summary.csv")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
