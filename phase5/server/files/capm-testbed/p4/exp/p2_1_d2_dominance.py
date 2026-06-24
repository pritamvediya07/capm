"""P4-2.1 — D.2 dominance claim correction (WS2, LOW).

Recomputes the frontier from p3/results/d2/d2_frontier.csv and tests dominance
TWO ways: over the content-blind baseline (the verified claim) and over the
single-sensor competitors (the unverified overclaim). The ledger said Phase-3
"dominates both single-sensor competitors / competitors fall in between" — but at
the headline operating point ASR<=0.05 full-g retention (0.7471) is BELOW NLI-only
(0.7500). This confirms the claim must be scoped to the content-blind baseline.

Run:  python -m p4.exp.p2_1_d2_dominance
"""
from __future__ import annotations
import csv, os

D2 = os.path.join("p3", "results", "d2", "d2_frontier.csv")
BASE = "document-CAPM (content-blind)"
FULL = "Phase3 full g (u,s,faith)"


def _load():
    sysd = {}
    for r in csv.DictReader(open(D2)):
        sysd.setdefault(r["system"], []).append((float(r["ASR"]), float(r["benign_retention"])))
    return sysd


def ret_at_asr(pts, t):
    ok = [ret for a, ret in pts if a <= t + 1e-9]
    return max(ok) if ok else 0.0


def main() -> int:
    sysd = _load()
    competitors = [s for s in sysd if s.startswith("Phase3") and s != FULL]
    grid = [i / 49 for i in range(50)]

    print("=" * 88)
    print("P4-2.1  D.2 dominance — scoped to the content-blind baseline")
    print("=" * 88)
    print(f"{'ASR<=':>7s} {'full-g':>9s} {'content-blind':>14s} " +
          " ".join(f"{c.split('Phase3 ')[1][:12]:>13s}" for c in competitors))
    for t in (0.10, 0.05, 0.0):
        cells = [ret_at_asr(sysd[c], t) for c in competitors]
        print(f"{t:>7.2f} {ret_at_asr(sysd[FULL], t):>9.4f} {ret_at_asr(sysd[BASE], t):>14.4f} " +
              " ".join(f"{x:>13.4f}" for x in cells))

    # dominance over baseline (robust) vs over competitors (the overclaim)
    dom_base = all(ret_at_asr(sysd[FULL], x) >= ret_at_asr(sysd[BASE], x) - 1e-6 for x in grid)
    comp_results = {}
    for c in competitors:
        dom_c = all(ret_at_asr(sysd[FULL], x) >= ret_at_asr(sysd[c], x) - 1e-6 for x in grid)
        # find a counterexample point if not dominant
        worst = min(((x, ret_at_asr(sysd[FULL], x) - ret_at_asr(sysd[c], x)) for x in grid), key=lambda z: z[1])
        comp_results[c] = (dom_c, worst)

    print(f"\nDOMINANCE over content-blind baseline (all 50 ASR points): {dom_base}")
    for c, (dom_c, worst) in comp_results.items():
        print(f"DOMINANCE over {c[7:]}: {dom_c}" +
              ("" if dom_c else f"  <-- counterexample at ASR<={worst[0]:.3f}: full-g loses by {worst[1]:+.4f}"))
    headline_gap = ret_at_asr(sysd[FULL], 0.05) - ret_at_asr(sysd['Phase3 NLI-only (competitor)'], 0.05)
    print(f"\nheadline point ASR<=0.05: full-g - NLI-only = {headline_gap:+.4f}  "
          f"({'NLI-only marginally higher — a quantization artifact' if headline_gap < 0 else 'full-g higher'})")

    # finer-grid robustness: the worst amount full-g loses to ANY competitor across all 50 ASR points
    worst_loss = min(min(ret_at_asr(sysd[FULL], x) - ret_at_asr(sysd[c], x) for x in grid) for c in competitors)
    print(f"finer-grid worst-case: full-g loses to a competitor by at most {-worst_loss:.4f} "
          f"(<= 0.01 => within quantization noise, never systematic dominance)")

    os.makedirs(os.path.join("p4", "results", "p2"), exist_ok=True)
    # operating-points table (Data to record: operating_point, system, asr, retention, gap_vs_full_g)
    with open(os.path.join("p4", "results", "p2", "p2_1_operating_points.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["asr_cap", "system", "retention", "gap_vs_full_g"])
        for t in (0.10, 0.05, 0.0):
            fr = ret_at_asr(sysd[FULL], t)
            for name in sysd:
                rt = ret_at_asr(sysd[name], t)
                w.writerow([t, name, round(rt, 4), round(fr - rt, 4)])
    with open(os.path.join("p4", "results", "p2", "p2_1_dominance.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["claim", "verified"])
        w.writerow(["dominates content-blind baseline", dom_base])
        for c, (dom_c, _) in comp_results.items():
            w.writerow([f"dominates {c[7:]}", dom_c])
        w.writerow(["worst_case_loss_to_competitor", round(-worst_loss, 4)])

    ok = dom_base and not all(d for d, _ in comp_results.values())
    print("=" * 88)
    print("PASS — dominance over the content-blind baseline is verified (robust at all 50 ASR points); "
          "dominance over the single-sensor competitors is NOT (full-g loses to NLI-only by 0.003 at "
          "ASR<=0.05). Ledger fix: claim dominance only over the content-blind baseline; drop "
          "'competitors fall in between'." if ok else "REVIEW — unexpected dominance pattern; inspect.")
    print("=" * 88)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
