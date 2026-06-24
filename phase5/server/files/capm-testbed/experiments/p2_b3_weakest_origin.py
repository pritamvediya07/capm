"""P2-B3 — Warrant-Guided Origin Targeting (WGOT), the Phase-2 novel attack.

B1 localised CAPM's residual to origin-class capture; B2 showed captures differ
in cost. B3 builds the attacker that *optimises* over that cost map. WGOT reads
CAPM's **own published warrant ceilings** (visible on every manifest) and divides
by each origin's capture cost, then captures the weakest *high-warrant* origins
first — extracting maximal accepted warrant per unit of attacker effort.

It never breaks CAPM's math (Lemma 1 forbids that); it exploits the **coupling**
of warrant to integrity that an ecosystem leaves open. The experiment quantifies
how much WGOT beats naive targeting, and how that advantage depends on that
coupling (`rho`):

  * Generate ecosystems (capm.ecosystem.graph) at correlations
    rho ∈ {-1, -0.5, 0, 0.5, 1} between warrant ceiling and integrity strength.
  * Run four strategies (random / max_warrant / min_cost / wgot) at a fixed
    attacker budget, grounding every "does this capture produce accepted content?"
    in the **real `WarrantEvaluator`**.
  * Measure ASR (fraction of high-warrant surface compromised) and efficiency
    (warrant laundered per unit cost); compare WGOT against the others with
    bootstrap CIs; verify WGOT dominates random (and is robust across rho).

Run:
    python3 -m experiments.p2_b3_weakest_origin
"""

from __future__ import annotations

import csv
import os
import random
import statistics

from attacks.wgot.targeting import STRATEGIES, run_campaign
from capm.benchmark import stats
from capm.core.types import SourceClass, TransformationType, WarrantLevel
from capm.ecosystem.graph import OriginNode, generate_ecosystem
from capm.identity.credentials import AgentIdentity, CredentialRegistry
from capm.manifest.capm_manifest import CAPMManifest
from capm.warrant.evaluator import Decision, EvaluatorPolicy, WarrantEvaluator

OUT_DIR = os.path.join("results", "p2", "b3")
_CLOCK = 1_700_000_000.0

N_ORIGINS = 50
BUDGET = 40.0
RHOS = [-1.0, -0.5, 0.0, 0.5, 1.0]
SEEDS = list(range(30))
BUDGET_CURVE = [10.0, 20.0, 40.0, 80.0, 160.0]
STRATS = ["random", "max_warrant", "min_cost", "wgot"]


# ---------------------------------------------------------------------------
# Ground the "is this capture accepted?" decision in the REAL CAPM evaluator.
# A capture is modelled principal-facing (depth 1, worst case): the captured
# origin asserts its class ceiling directly to the principal. Memoised per class
# (the verdict depends only on the source class), but computed via the live
# evaluator so nothing is hand-asserted.
# ---------------------------------------------------------------------------
_accept_cache: dict[SourceClass, bool] = {}


def _capm_accepts_capture(node: OriginNode) -> bool:
    cls = node.source_class
    if cls in _accept_cache:
        return _accept_cache[cls]
    registry = CredentialRegistry()
    ident = AgentIdentity(did="did:capm:captured-origin", org="org-0")
    registry.register(ident)
    m = CAPMManifest()
    m.append_segment(identity=ident, content="malicious", transformation=TransformationType.VERBATIM,
                     from_org="org-principal", to_org="org-0",
                     origin_source_class=cls, asserted_origin_warrant=cls.warrant_ceiling,
                     timestamp=_CLOCK)
    verdict = WarrantEvaluator(registry, EvaluatorPolicy()).evaluate(m, delivered_text="malicious")
    ok = verdict.decision == Decision.ACCEPT
    _accept_cache[cls] = ok
    return ok


# ---------------------------------------------------------------------------
def _campaigns_at(rho: float, budget: float) -> list[dict]:
    """Run all strategies on one ecosystem per seed; return raw per-campaign rows."""
    rows = []
    for seed in SEEDS:
        eco = generate_ecosystem(N_ORIGINS, rho, seed=seed * 1000 + int((rho + 2) * 97))
        for strat in STRATS:
            rng = random.Random(seed * 31 + hash(strat) % 1000)
            res = run_campaign(eco, strat, budget, _capm_accepts_capture, rng)
            rows.append({
                "rho": rho, "actual_rho": round(eco.actual_rho, 3), "seed": seed,
                "strategy": strat, "budget": budget, "captured": res.captured,
                "accepted_channels": res.accepted_channels,
                "cost_spent": round(res.cost_spent, 3),
                "warrant_laundered": res.warrant_laundered,
                "n_high_value": res.n_high_value,
                "asr": round(res.asr, 4),
                "efficiency": round(res.efficiency_warrant, 4),
            })
    return rows


def _agg(rows: list[dict], key: str) -> dict:
    """Mean + bootstrap 95% CI of `key` grouped by strategy."""
    out = {}
    for strat in STRATS:
        vals = [r[key] for r in rows if r["strategy"] == strat]
        point, lo, hi = stats.bootstrap_ci(vals, seed=7)
        out[strat] = {"mean": point, "lo": lo, "hi": hi,
                      "raw_mean": statistics.mean(vals) if vals else 0.0}
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 84)
    print("P2-B3 — Warrant-Guided Origin Targeting (WGOT)")
    print("=" * 84)
    print(f"ecosystem: {N_ORIGINS} origins · budget {BUDGET} · {len(SEEDS)} seeds/cell")
    accept_by_class = {c.value: _capm_accepts_capture(OriginNode("x", c, 0.5))
                       for c in SourceClass}
    print(f"CAPM accepts capture by class (grounded): {accept_by_class}")

    all_raw = []

    # ---- correlation sweep at fixed budget ----
    print(f"\n[Correlation sweep @ budget={BUDGET}]  ASR (fraction of high-warrant surface) "
          f"and efficiency (warrant/cost)")
    by_corr_rows = []
    for rho in RHOS:
        rows = _campaigns_at(rho, BUDGET)
        all_raw.extend(rows)
        asr = _agg(rows, "asr")
        eff = _agg(rows, "efficiency")
        actual = statistics.mean([r["actual_rho"] for r in rows])
        print(f"\n  rho={rho:+.1f} (actual {actual:+.2f}):")
        print(f"    {'strategy':<14}{'ASR':>8}{'  [95% CI]':>16}{'eff':>9}{'  [95% CI]':>16}")
        for s in STRATS:
            print(f"    {s:<14}{asr[s]['mean']:>8.3f}  [{asr[s]['lo']:.2f},{asr[s]['hi']:.2f}]"
                  f"{eff[s]['mean']:>9.3f}  [{eff[s]['lo']:.2f},{eff[s]['hi']:.2f}]")
        for s in STRATS:
            by_corr_rows.append({
                "rho": rho, "actual_rho": round(actual, 3), "strategy": s,
                "mean_asr": round(asr[s]["mean"], 4), "asr_lo": round(asr[s]["lo"], 4),
                "asr_hi": round(asr[s]["hi"], 4), "mean_efficiency": round(eff[s]["mean"], 4),
                "eff_lo": round(eff[s]["lo"], 4), "eff_hi": round(eff[s]["hi"], 4),
                "n_seeds": len(SEEDS)})

    # ---- budget curve at rho=0 ----
    print(f"\n[Budget curve @ rho=0]  ASR vs attacker budget")
    budget_rows = []
    for b in BUDGET_CURVE:
        rows = _campaigns_at(0.0, b)
        asr = _agg(rows, "asr")
        line = "  ".join(f"{s}={asr[s]['mean']:.2f}" for s in STRATS)
        print(f"  budget={b:>6.0f}: {line}")
        for s in STRATS:
            budget_rows.append({"budget": b, "strategy": s,
                                "mean_asr": round(asr[s]["mean"], 4),
                                "mean_efficiency": round(_agg(rows, "efficiency")[s]["mean"], 4)})

    # ---- dominance test: WGOT vs random, paired per ecosystem (all rho) ----
    paired = {}
    for r in all_raw:
        paired.setdefault((r["rho"], r["seed"]), {})[r["strategy"]] = r["efficiency"]
    diffs_eff = [v["wgot"] - v["random"] for v in paired.values() if "wgot" in v and "random" in v]
    diffs_asr = []
    paired_asr = {}
    for r in all_raw:
        paired_asr.setdefault((r["rho"], r["seed"]), {})[r["strategy"]] = r["asr"]
    diffs_asr = [v["wgot"] - v["random"] for v in paired_asr.values()]
    dpoint, dlo, dhi = stats.bootstrap_ci(diffs_eff, seed=11)
    apoint, alo, ahi = stats.bootstrap_ci(diffs_asr, seed=11)

    # ---- write CSVs ----
    with open(os.path.join(OUT_DIR, "strategy_by_correlation.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(by_corr_rows[0].keys()))
        w.writeheader(); w.writerows(by_corr_rows)
    with open(os.path.join(OUT_DIR, "budget_curve.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(budget_rows[0].keys()))
        w.writeheader(); w.writerows(budget_rows)
    with open(os.path.join(OUT_DIR, "raw_campaigns.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_raw[0].keys()))
        w.writeheader(); w.writerows(all_raw)

    # ---- verdict ----
    print("\n" + "=" * 84)
    print(f"WGOT − random  efficiency Δ (paired, all rho): "
          f"{dpoint:+.3f}  [95% CI {dlo:+.3f}, {dhi:+.3f}]")
    print(f"WGOT − random  ASR Δ        (paired, all rho): "
          f"{apoint:+.3f}  [95% CI {alo:+.3f}, {ahi:+.3f}]")
    dominates = dlo > 0 and alo > 0
    print(f"RESULT: {'PASS — WGOT strictly dominates random (CI excludes 0)' if dominates else 'FAIL'}")
    print(f"CSV: {OUT_DIR}/{{strategy_by_correlation,budget_curve,raw_campaigns}}.csv")
    print("=" * 84)
    return 0 if dominates else 1


if __name__ == "__main__":
    raise SystemExit(main())
