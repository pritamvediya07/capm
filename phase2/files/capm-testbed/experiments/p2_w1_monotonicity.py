"""P2-W1 — Monotonicity Invariant (Lemma 1).

Goal 1 backbone. Establishes, two independent ways, that warrant is
*non-increasing under every relay operation*:

  Part A — Proof (algebraic).  Exhaustively evaluate every operation in
    ``capm.analysis.operations.OPERATIONS`` over the full cross-product of the
    5-level warrant lattice and assert ``output <= min(inputs)`` in every case.
    The same harness is run over deliberately non-monotone NEGATIVE_CONTROLS to
    confirm it *detects* violations (so a clean pass is meaningful, not vacuous).
    Output: the operation→Δwarrant table that IS Lemma 1.

  Part B — Empirical (implementation).  Generate N random, fully *signed*
    manifest chains of varying length and origin class, score each with the live
    ``WarrantEvaluator``, and assert the final warrant never exceeds the origin
    source-class ceiling. As an extra integrity check, cross-validate that the
    live evaluator agrees exactly with the pure algebra (``evaluate_chain``) on
    truthful chains — any mismatch is a real bug.

There must be 0 violations in both parts (the controls excepted, which must
violate). All rows are written to CSV under results/p2/w1/ for full provenance.

Run:
    python3 -m experiments.p2_w1_monotonicity            # default 10000 chains
    python3 -m experiments.p2_w1_monotonicity --chains 10000 --seed 20250615
"""

from __future__ import annotations

import argparse
import csv
import itertools
import os
import random

from capm.analysis import operations as ops
from capm.core.types import SourceClass, TransformationType, WarrantLevel
from capm.identity.credentials import AgentIdentity, CredentialRegistry
from capm.manifest.capm_manifest import CAPMManifest
from capm.warrant.evaluator import WarrantEvaluator, EvaluatorPolicy

OUT_DIR = os.path.join("results", "p2", "w1")

# Relay transformations a random chain can apply (segment 0 is the origin
# emission, treated as VERBATIM; segments 1.. are these).
_RELAY_TS = [
    TransformationType.VERBATIM,
    TransformationType.STRUCTURED_EXTRACTION,
    TransformationType.SUMMARY,
    TransformationType.PARAPHRASE,
    TransformationType.GENERATION,
]
# Map a TransformationType to the matching pure-algebra operation name, so the
# empirical chain can be folded through evaluate_chain for the cross-check.
_T2OP = {
    TransformationType.VERBATIM: "verbatim",
    TransformationType.STRUCTURED_EXTRACTION: "extraction",
    TransformationType.SUMMARY: "summary",
    TransformationType.PARAPHRASE: "paraphrase",
    TransformationType.GENERATION: "generation",
}


# ===========================================================================
# Part A — exhaustive algebraic proof
# ===========================================================================
def _input_tuples(arity: int | None) -> list[tuple[int, ...]]:
    """All input tuples to test an operation against, over the full lattice.

    Unary → the 5 singletons. N-ary → all ordered pairs (25) and triples (125),
    which exercises every combination of weakest/strongest placement.
    """
    L = ops.LATTICE
    if arity == 1:
        return [(w,) for w in L]
    pairs = list(itertools.product(L, repeat=2))
    triples = list(itertools.product(L, repeat=3))
    return pairs + triples


def run_proof(out_dir: str) -> dict:
    rows = []
    violations = 0
    # operation -> worst (largest) delta observed; ≤ 0 means monotone everywhere.
    worst_delta: dict[str, int] = {}

    def check(registry: dict[str, ops.Operation], is_control: bool):
        nonlocal violations
        local_viol = 0
        for name, op in registry.items():
            for inp in _input_tuples(op.arity):
                out = op(inp)
                mn = min(inp)
                d = out - mn
                monotone = out <= mn
                worst_delta[name] = max(worst_delta.get(name, -99), d)
                if not monotone:
                    local_viol += 1
                    if not is_control:
                        violations += 1
                rows.append({
                    "operation": name, "is_control": is_control,
                    "penalty": op.penalty, "arity": op.arity or len(inp),
                    "inputs": "|".join(str(x) for x in inp),
                    "min_input": mn, "output": out, "delta": d,
                    "monotone": monotone,
                })
        return local_viol

    real_checks_before = len(rows)
    check(ops.OPERATIONS, is_control=False)
    real_checks = len(rows) - real_checks_before
    control_viol = check(ops.NEGATIVE_CONTROLS, is_control=True)

    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "operations_proof.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    return {
        "real_checks": real_checks,
        "real_violations": violations,
        "control_checks": len(rows) - real_checks,
        "control_violations": control_viol,
        "worst_delta": worst_delta,
        "csv": csv_path,
        "n_real_ops": len(ops.OPERATIONS),
    }


# ===========================================================================
# Part B — empirical validation over random signed manifests
# ===========================================================================
def _build_random_manifest(rng: random.Random, chain_id: int):
    """Build one fully-signed manifest with a random length, origin class, and
    truthful relay-transformation sequence. Returns (manifest, registry,
    source_ceiling, asserted, relay_op_names)."""
    length = rng.randint(1, 6)                       # 1..6 hops
    source_class = rng.choice(list(SourceClass))
    ceiling = int(source_class.warrant_ceiling)
    asserted = rng.randint(0, 4)                     # origin may over-claim

    registry = CredentialRegistry()
    m = CAPMManifest()
    relay_op_names: list[str] = []
    prev_content = None
    prev_org = "org-principal"

    for i in range(length):
        ident = AgentIdentity(did=f"did:capm:w1-{chain_id}-{i}", org=f"org-{i}")
        registry.register(ident)
        if i == 0:
            t = TransformationType.VERBATIM            # origin emits its source
        else:
            t = rng.choice(_RELAY_TS)
            relay_op_names.append(_T2OP[t])
        # truthful content: verbatim/extraction preserve bytes; others change
        if t in (TransformationType.VERBATIM,
                 TransformationType.STRUCTURED_EXTRACTION) and prev_content is not None:
            content = prev_content
        else:
            content = f"c-{chain_id}-{i}-{rng.random()}"
        to_org = f"org-{i}"
        m.append_segment(
            identity=ident, content=content, transformation=t,
            from_org=prev_org, to_org=to_org,
            origin_source_class=source_class if i == 0 else None,
            asserted_origin_warrant=WarrantLevel(asserted) if i == 0 else None,
        )
        prev_content, prev_org = content, to_org

    return m, registry, ceiling, asserted, relay_op_names


def run_empirical(n_chains: int, seed: int, out_dir: str) -> dict:
    rng = random.Random(seed)
    ceiling_violations = 0
    algebra_mismatches = 0
    prefix_non_monotone = 0
    rows = []

    for cid in range(n_chains):
        m, registry, ceiling, asserted, relay_ops = _build_random_manifest(rng, cid)
        evaluator = WarrantEvaluator(registry, EvaluatorPolicy())
        verdict = evaluator.evaluate(m)
        final = int(verdict.warrant)

        # (1) headline assertion: final warrant ≤ origin source-class ceiling
        ceiling_ok = final <= ceiling
        if not ceiling_ok:
            ceiling_violations += 1

        # (2) integrity cross-check: live evaluator == pure algebra
        algebra = ops.evaluate_chain(asserted, ceiling, relay_ops)
        algebra_ok = (algebra == final)
        if not algebra_ok:
            algebra_mismatches += 1

        # (3) per-prefix monotonicity: warrant non-increasing along the chain
        prefix_ok = True
        running = ops.origin_warrant(asserted, ceiling)
        for opname in relay_ops:
            nxt = ops.OPERATIONS[opname]([running])
            if nxt > running:
                prefix_ok = False
                break
            running = nxt
        if not prefix_ok:
            prefix_non_monotone += 1

        rows.append({
            "chain_id": cid, "length": len(m.segments),
            "source_class": m.segments[0].origin_source_class,
            "ceiling": ceiling, "asserted": asserted,
            "final_warrant": final, "algebra_warrant": algebra,
            "signature_ok": verdict.signature_ok,
            "ceiling_ok": ceiling_ok, "algebra_ok": algebra_ok,
            "prefix_monotone": prefix_ok,
            "relay_ops": ">".join(relay_ops),
        })

    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "empirical_chains.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # also persist a compact per-source-class summary for the figure
    by_class: dict[str, dict] = {}
    for r in rows:
        c = r["source_class"]
        d = by_class.setdefault(c, {"n": 0, "max_final": 0, "ceiling": r["ceiling"]})
        d["n"] += 1
        d["max_final"] = max(d["max_final"], r["final_warrant"])
    summ_path = os.path.join(out_dir, "empirical_by_class.csv")
    with open(summ_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source_class", "n", "ceiling", "max_final_warrant"])
        for c, d in sorted(by_class.items()):
            w.writerow([c, d["n"], d["ceiling"], d["max_final"]])

    return {
        "n_chains": n_chains, "seed": seed,
        "ceiling_violations": ceiling_violations,
        "algebra_mismatches": algebra_mismatches,
        "prefix_non_monotone": prefix_non_monotone,
        "csv": csv_path, "by_class_csv": summ_path,
        "by_class": by_class,
    }


def run_seed_sweep(seeds: list[int], chains_per_seed: int, out_dir: str) -> dict:
    """Robustness: repeat the empirical check across many seeds (≥20 convention).

    Confirms 0 ceiling violations in *every* seed, not just one lucky draw.
    """
    per_seed = []
    total_chains = total_viol = 0
    for s in seeds:
        rng = random.Random(s)
        viol = 0
        for cid in range(chains_per_seed):
            m, registry, ceiling, asserted, relay_ops = _build_random_manifest(rng, cid)
            final = int(WarrantEvaluator(registry, EvaluatorPolicy()).evaluate(m).warrant)
            if final > ceiling:
                viol += 1
        per_seed.append({"seed": s, "chains": chains_per_seed, "violations": viol})
        total_chains += chains_per_seed
        total_viol += viol
    csv_path = os.path.join(out_dir, "seed_sweep.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["seed", "chains", "violations"])
        w.writeheader(); w.writerows(per_seed)
    return {"seeds": len(seeds), "total_chains": total_chains,
            "total_violations": total_viol, "csv": csv_path, "per_seed": per_seed}


# ===========================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chains", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20250615)
    ap.add_argument("--sweep-seeds", type=int, default=20,
                    help="number of additional seeds for the robustness sweep")
    ap.add_argument("--sweep-chains", type=int, default=2000,
                    help="chains per seed in the robustness sweep")
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args()

    print("=" * 78)
    print("P2-W1 — Monotonicity Invariant (Lemma 1)")
    print("=" * 78)

    # ---- Part A ----
    print("\n[Part A] Exhaustive algebraic proof over the 5-level lattice")
    A = run_proof(args.out)
    print(f"  real operations         : {A['n_real_ops']}")
    print(f"  lattice checks (real)   : {A['real_checks']}")
    print(f"  >>> VIOLATIONS (real)   : {A['real_violations']}")
    print(f"  negative-control checks : {A['control_checks']}  "
          f"(violations: {A['control_violations']} — expected > 0, proves teeth)")
    print("  operation → worst Δwarrant (output − min(inputs)); ≤ 0 ⇒ monotone:")
    for name in ops.OPERATIONS:
        print(f"     {name:<13} Δmax = {A['worst_delta'][name]:+d}")
    for name in ops.NEGATIVE_CONTROLS:
        print(f"     {name:<13} Δmax = {A['worst_delta'][name]:+d}  [CONTROL]")

    # ---- Part B ----
    print(f"\n[Part B] Empirical: {args.chains} random signed manifests, seed={args.seed}")
    B = run_empirical(args.chains, args.seed, args.out)
    print(f"  chains evaluated        : {B['n_chains']}")
    print(f"  >>> ceiling VIOLATIONS  : {B['ceiling_violations']}")
    print(f"  algebra mismatches      : {B['algebra_mismatches']}  "
          f"(live evaluator vs pure algebra; must be 0)")
    print(f"  prefix non-monotone     : {B['prefix_non_monotone']}")
    print("  per source-class: max final warrant must be ≤ ceiling")
    for c, d in sorted(B["by_class"].items()):
        flag = "OK" if d["max_final"] <= d["ceiling"] else "VIOLATION"
        print(f"     {c:<20} n={d['n']:<5} ceiling={d['ceiling']} "
              f"max_final={d['max_final']}  [{flag}]")

    # ---- Part C: robustness sweep ----
    sweep_seeds = list(range(1, args.sweep_seeds + 1))
    print(f"\n[Part C] Robustness sweep: {len(sweep_seeds)} seeds × "
          f"{args.sweep_chains} chains")
    C = run_seed_sweep(sweep_seeds, args.sweep_chains, args.out)
    print(f"  total chains            : {C['total_chains']}")
    print(f"  >>> total VIOLATIONS    : {C['total_violations']}")

    # ---- verdict ----
    total_violations = (A["real_violations"] + B["ceiling_violations"]
                        + B["algebra_mismatches"] + B["prefix_non_monotone"]
                        + C["total_violations"])
    controls_fired = A["control_violations"] > 0
    print("\n" + "=" * 78)
    print(f"TOTAL VIOLATIONS (real ops): {total_violations}")
    print(f"Negative controls fired   : {controls_fired} "
          f"({A['control_violations']} control violations)")
    ok = (total_violations == 0) and controls_fired
    print(f"RESULT: {'PASS — Lemma 1 holds' if ok else 'FAIL'}")
    print("=" * 78)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
