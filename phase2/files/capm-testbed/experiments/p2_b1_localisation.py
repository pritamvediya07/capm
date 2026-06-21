"""P2-B1 — Residual Localisation (empirical backing for Theorem 2).

Theorem 2 (docs/proofs/residual_reduction.md): modulo signature unforgeability,
**origin-class capture is the unique residual** — the only way a verifying
manifest can be assigned warrant above its true origin ceiling.

This experiment provides the empirical half. An adversarial search generates
random attack chains that use **every lever except** the two the theorem
excludes — it does NOT lie about the origin class and does NOT forge keys (every
segment is validly signed by a registered identity). It pulls every *other*
string: over-claiming the asserted warrant number, arbitrary transformation
sequences, transformation lies (claim VERBATIM, change bytes), variable length
and boundary crossings, duplicated high-warrant assertions, and — the sharpest
probe — **mid-chain origin re-declarations** that try to reset the ceiling after
the tail. Theorem 2 predicts the laundering goal

        (★)   final_warrant  >  ceil(true_origin_class)

is reached in **exactly 0** of these chains.

Teeth (negative controls). To prove the search can detect a breach when one
exists, it is re-run with the residual deliberately opened:
  * `class_capture`  — the adversary may declare a class stronger than the true
                       one (i.e. perform origin-class capture). Expect successes.
  * `no_ceiling`     — `enforce_origin_ceiling=False`. Expect successes.
If these controls also returned 0, the search would be vacuous; they must fire.

Run:
    python3 -m experiments.p2_b1_localisation                 # 10000 chains
    python3 -m experiments.p2_b1_localisation --chains 10000 --seed 7
"""

from __future__ import annotations

import argparse
import csv
import os
import random

from capm.core.types import SourceClass, TransformationType, WarrantLevel
from capm.identity.credentials import AgentIdentity, CredentialRegistry
from capm.manifest.capm_manifest import CAPMManifest
from capm.warrant.evaluator import Decision, EvaluatorPolicy, WarrantEvaluator

OUT_DIR = os.path.join("results", "p2", "b1")
_CLOCK = 1_700_000_000.0

_CLASSES = list(SourceClass)
_TRANSFORMS = list(TransformationType)
# classes with a strictly higher ceiling than `c`, for the capture control
def _stronger_classes(c: SourceClass) -> list[SourceClass]:
    cc = int(c.warrant_ceiling)
    return [k for k in _CLASSES if int(k.warrant_ceiling) > cc]


def _build_attack(rng: random.Random, cid: int, *, allow_class_lie: bool):
    """Construct one adversarial, fully-signed chain.

    Returns (manifest, registry, true_class, declared_class, meta) where meta
    records which levers the attacker pulled. No key forgery: every segment is
    signed by a freshly registered, trusted identity (the adversary is assumed to
    control its own legitimate agents — capturing someone else's key is the
    excluded vector (a)).
    """
    true_class = rng.choice(_CLASSES)
    declared_class = true_class
    class_lie = False
    if allow_class_lie:
        stronger = _stronger_classes(true_class)
        if stronger and rng.random() < 0.7:
            declared_class = rng.choice(stronger)
            class_lie = True

    asserted = WarrantLevel(rng.randint(0, 4))     # over-claim the NUMBER freely
    hops = rng.randint(1, 6)

    registry = CredentialRegistry()
    m = CAPMManifest()
    prev_content = None
    prev_org = "org-principal"
    used_transformation_lie = False
    used_midchain_origin = False

    for i in range(hops):
        ident = AgentIdentity(did=f"did:capm:b1-{cid}-{i}", org=f"org-{i}")
        registry.register(ident)               # valid, trusted signer (no forgery)

        if i == 0:
            transform = TransformationType.VERBATIM
            content = f"payload-{cid}"
            o_class = declared_class
            o_warrant = asserted
        else:
            transform = rng.choice(_TRANSFORMS)
            # content behaviour: truthfully preserve for verbatim/extraction, OR
            # deliberately change bytes while keeping the claim (transformation lie)
            tell_truth = rng.random() < 0.5
            if transform in (TransformationType.VERBATIM,
                             TransformationType.STRUCTURED_EXTRACTION) and tell_truth:
                content = prev_content
            else:
                content = f"payload-{cid}-{i}-{rng.random()}"
                if transform in (TransformationType.VERBATIM,
                                 TransformationType.STRUCTURED_EXTRACTION):
                    used_transformation_lie = True
            # SHARPEST PROBE: with some probability, a mid-chain relay also
            # *re-declares* a strong origin class + STRONG warrant, trying to
            # reset/raise the ceiling after the tail. The evaluator must ignore
            # any origin assertion past s0.
            if rng.random() < 0.35:
                o_class = SourceClass.AUTHORITATIVE_API
                o_warrant = WarrantLevel.STRONG
                used_midchain_origin = True
            else:
                o_class = None
                o_warrant = None

        crosses = rng.random() < 0.7
        to_org = f"org-{i}" if crosses else prev_org
        m.append_segment(
            identity=ident, content=content, transformation=transform,
            from_org=prev_org, to_org=to_org,
            origin_source_class=o_class, asserted_origin_warrant=o_warrant,
            timestamp=_CLOCK + i,
        )
        prev_content, prev_org = content, to_org

    meta = {
        "asserted": int(asserted), "hops": hops, "class_lie": class_lie,
        "transformation_lie": used_transformation_lie,
        "midchain_origin": used_midchain_origin,
    }
    return m, registry, true_class, declared_class, meta


def run_search(n: int, seed: int, *, allow_class_lie: bool, ceiling_enabled: bool,
               label: str, write_rows: bool = False) -> dict:
    rng = random.Random(seed)
    policy = EvaluatorPolicy(enforce_origin_ceiling=ceiling_enabled)
    successes = 0
    accepted_breaches = 0          # success AND decision==accept (worst case)
    rows = []
    # bookkeeping: how often each lever was exercised (shows the search explored)
    levers = {"class_lie": 0, "transformation_lie": 0, "midchain_origin": 0,
              "overclaim": 0}

    for cid in range(n):
        m, registry, true_class, declared_class, meta = _build_attack(
            rng, cid, allow_class_lie=allow_class_lie)
        verdict = WarrantEvaluator(registry, policy).evaluate(m)
        w = int(verdict.warrant)
        true_ceiling = int(true_class.warrant_ceiling)
        success = w > true_ceiling                       # the laundering goal (★)
        if success:
            successes += 1
            if verdict.decision == Decision.ACCEPT:
                accepted_breaches += 1
        levers["class_lie"] += meta["class_lie"]
        levers["transformation_lie"] += meta["transformation_lie"]
        levers["midchain_origin"] += meta["midchain_origin"]
        levers["overclaim"] += int(meta["asserted"] > true_ceiling)

        if write_rows:
            rows.append({
                "chain_id": cid, "true_class": true_class.value,
                "declared_class": declared_class.value,
                "true_ceiling": true_ceiling, "asserted": meta["asserted"],
                "hops": meta["hops"], "final_warrant": w,
                "decision": verdict.decision.value,
                "class_lie": meta["class_lie"],
                "transformation_lie": meta["transformation_lie"],
                "midchain_origin": meta["midchain_origin"],
                "exceeds_true_ceiling": success,
            })

    out = {"label": label, "n": n, "seed": seed,
           "allow_class_lie": allow_class_lie, "ceiling_enabled": ceiling_enabled,
           "successes": successes, "success_rate": successes / n,
           "accepted_breaches": accepted_breaches, "levers": levers}

    if write_rows:
        os.makedirs(OUT_DIR, exist_ok=True)
        path = os.path.join(OUT_DIR, "localisation_search.csv")
        with open(path, "w", newline="") as f:
            w_ = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w_.writeheader(); w_.writerows(rows)
        out["csv"] = path
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chains", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20250615)
    args = ap.parse_args()

    print("=" * 78)
    print("P2-B1 — Residual Localisation (Theorem 2)")
    print("=" * 78)
    print("Laundering goal (★): final_warrant > ceil(true_origin_class)\n")

    # ---- MAIN search: no class lie, no key forgery, full defense ----
    print(f"[MAIN] {args.chains} adversarial chains — truthful class, valid sigs, "
          f"full defense")
    main = run_search(args.chains, args.seed, allow_class_lie=False,
                      ceiling_enabled=True, label="main_no_class_lie",
                      write_rows=True)
    lv = main["levers"]
    print(f"  levers exercised: over-claim={lv['overclaim']}, "
          f"transformation-lie={lv['transformation_lie']}, "
          f"mid-chain-origin={lv['midchain_origin']}")
    print(f"  >>> SUCCESSES (warrant > true ceiling): {main['successes']} "
          f"/ {main['n']}   (rate {main['success_rate']:.4f})")

    # ---- CONTROL A: origin-class capture allowed ----
    print(f"\n[CONTROL A] class-capture allowed (declare ĉ > c*) — residual OPEN")
    ctrlA = run_search(args.chains, args.seed + 1, allow_class_lie=True,
                       ceiling_enabled=True, label="control_class_capture")
    print(f"  class-lies attempted: {ctrlA['levers']['class_lie']}")
    print(f"  >>> SUCCESSES: {ctrlA['successes']} / {ctrlA['n']} "
          f"(rate {ctrlA['success_rate']:.4f}); accepted breaches "
          f"{ctrlA['accepted_breaches']}")

    # ---- CONTROL B: origin ceiling disabled ----
    print(f"\n[CONTROL B] origin ceiling disabled (enforce_origin_ceiling=False)")
    ctrlB = run_search(args.chains, args.seed + 2, allow_class_lie=False,
                       ceiling_enabled=False, label="control_no_ceiling")
    print(f"  >>> SUCCESSES: {ctrlB['successes']} / {ctrlB['n']} "
          f"(rate {ctrlB['success_rate']:.4f}); accepted breaches "
          f"{ctrlB['accepted_breaches']}")

    # ---- summary CSV ----
    os.makedirs(OUT_DIR, exist_ok=True)
    summ = os.path.join(OUT_DIR, "conditions_summary.csv")
    with open(summ, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "n", "successes", "success_rate",
                    "accepted_breaches", "allow_class_lie", "ceiling_enabled"])
        for r in (main, ctrlA, ctrlB):
            w.writerow([r["label"], r["n"], r["successes"],
                        f"{r['success_rate']:.4f}", r["accepted_breaches"],
                        r["allow_class_lie"], r["ceiling_enabled"]])

    # ---- verdict ----
    teeth = ctrlA["successes"] > 0 and ctrlB["successes"] > 0
    ok = main["successes"] == 0 and teeth
    print("\n" + "=" * 78)
    print(f"MAIN successes (must be 0)            : {main['successes']}")
    print(f"Control A successes (must be > 0)     : {ctrlA['successes']}")
    print(f"Control B successes (must be > 0)     : {ctrlB['successes']}")
    print(f"Search has teeth (controls fire)     : {teeth}")
    print(f"RESULT: {'PASS — origin-class capture is the unique residual' if ok else 'FAIL'}")
    print(f"CSV: {main.get('csv')} , {summ}")
    print("=" * 78)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
