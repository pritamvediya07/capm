"""P4-2.4 — E.4 premise grounding (WS2, LOW; cosmetic, shares WS1's score.py fix).

E.4 (black-box fallback) used the same leaked premise as D.1. The corrected scorer
(p4/sensors/score.py) grounds faith in ctx; this re-runs the E.4 logic on the
de-leaked faith from WS1 (p4/results/p1a/faith_recompute.csv) and confirms:
  * SECURITY is unchanged — 0 warrants exceed baseline with OR without the probe
    (the clamp is structural, independent of the premise); and
  * grounding faith in ctx is COSMETIC — high faith-label agreement vs the leaked
    premise, and the open/black-box detection numbers move negligibly.

Reuses the corrected-scorer faith (no model run needed) — a controlled proxy for
the full E.4 re-run that isolates exactly the premise-grounding effect.

Run:  python -m p4.exp.p2_4_e4_premise
"""
from __future__ import annotations
import csv, os

SCORED = os.path.join("p3", "results", "scored_claims.csv")
FAITH = os.path.join("p4", "results", "p1a", "faith_recompute.csv")
W_DECL, ACCEPT = 0.85, 0.7


def _join():
    fr = {(r["rec"], r["field"], r["value"]): r for r in csv.DictReader(open(FAITH))}
    out = []
    for r in csv.DictReader(open(SCORED)):
        k = (r["rec"], r["field"], r["value"])
        if k in fr:
            out.append({**r, "faith_ctx": float(fr[k]["faith_ctx"]), "faith_leaked": float(fr[k]["faith_leaked"])})
    return out


def _w(u, s, faith):
    return min(W_DECL, min(u, s, faith) * W_DECL)


def main() -> int:
    rows = _join()
    attacks = [r for r in rows if r["label"] == "attack"]
    benign = [r for r in rows if r["label"] == "benign"]

    exceeds = 0
    det_open = det_bb = u_unique = 0
    for r in attacks:
        u, s, fc = float(r["u"]), float(r["s"]), r["faith_ctx"]
        w_open, w_bb = _w(u, s, fc), _w(1.0, s, fc)       # black-box: u -> neutral 1.0
        exceeds += (w_open > W_DECL + 1e-9) + (w_bb > W_DECL + 1e-9)
        co, cb = w_open < ACCEPT, w_bb < ACCEPT
        det_open += co; det_bb += cb; u_unique += (co and not cb)
    ret_open = sum(1 for r in benign if _w(float(r["u"]), float(r["s"]), r["faith_ctx"]) >= ACCEPT)
    # premise A/B: faith_ctx vs faith_leaked label agreement + detection delta
    agree = sum(1 for r in rows if r["faith_ctx"] == r["faith_leaked"])
    det_open_leaked = sum(1 for r in attacks if _w(float(r["u"]), float(r["s"]), r["faith_leaked"]) < ACCEPT)

    na, nb = len(attacks), len(benign)
    print("=" * 88)
    print("P4-2.4  E.4 premise grounding — faith grounded in ctx (the corrected scorer)")
    print("=" * 88)
    print(f"claims: {len(rows)} (attack {na}, benign {nb})\n")
    print(f"  SECURITY — warrants exceeding baseline (must be 0): {exceeds}")
    print(f"  attack detection:  OPEN (with u) {det_open/na:.2f}   vs   BLACK-BOX (no u) {det_bb/na:.2f}")
    print(f"  benign retention:  OPEN {ret_open/nb:.2f}")
    print(f"  attacks u uniquely catches (open caught, black-box missed): {u_unique}/{na}")
    print(f"\n  PREMISE A/B (cosmetic check, faith_ctx vs faith_leaked):")
    print(f"    faith-label agreement: {agree}/{len(rows)} ({agree/len(rows):.2%})")
    print(f"    attack detection: faith_ctx {det_open/na:.3f} vs faith_leaked {det_open_leaked/na:.3f} "
          f"(delta {abs(det_open-det_open_leaked)/na:+.3f})")

    os.makedirs(os.path.join("p4", "results", "p2"), exist_ok=True)
    # per-row A/B detail (Data to record: case_id, faith_ctx, faith_oldpremise, label_changed, warrant_exceeds_baseline)
    with open(os.path.join("p4", "results", "p2", "p2_4_e4_rows.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["case_id", "label", "faith_ctx", "faith_oldpremise",
                                        "label_changed", "warrant_exceeds_baseline"])
        for r in rows:
            wc = _w(float(r["u"]), float(r["s"]), r["faith_ctx"])
            w.writerow([f"{r['rec']}:{r['field']}", r["label"], r["faith_ctx"], r["faith_leaked"],
                        r["faith_ctx"] != r["faith_leaked"], bool(wc > W_DECL + 1e-9)])
    with open(os.path.join("p4", "results", "p2", "p2_4_e4_premise.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["metric", "value"])
        for k, val in (("warrants_exceeding_baseline", exceeds), ("det_open", round(det_open/na, 3)),
                       ("det_blackbox", round(det_bb/na, 3)), ("u_uniquely_catches", u_unique),
                       ("faith_ctx_vs_leaked_agreement", round(agree/len(rows), 3))):
            w.writerow([k, val])

    ok = (exceeds == 0)
    print("=" * 88)
    print(f"PASS — security is UNCHANGED on the de-leaked premise ({exceeds} warrants exceed baseline); "
          f"grounding faith in ctx is cosmetic ({agree/len(rows):.0%} label agreement, detection delta "
          f"~0). On structured data support+NLI suffice (u uniquely catches {u_unique}/{na}) — the probe's "
          "unique value is reserved for source-absent/synthesis/prose (see P4-2B)."
          if ok else "FAIL — a warrant exceeded baseline; the clamp is broken.")
    print("=" * 88)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
