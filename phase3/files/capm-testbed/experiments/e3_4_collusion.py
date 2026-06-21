"""E3.4 — collusion / Sybil adversary: warrant is origin-bounded, not relay-bounded.

Multiple malicious relays co-sign a chain to try to launder a low-warrant origin.
The distinctive CAPM result: warrant is bounded by the *origin* segment, so the
number of colluding relays is irrelevant — ASR does not climb with the size of
the colluding coalition. We sweep the number of colluders at several fixed chain
lengths and show CAPM's delivered warrant (and ASR) is flat across the sweep.

For contrast we also plot what a **signer-counting heuristic** would do — a
(strawman) defense that raised trust with each additional trusted co-signer.
That curve climbs and the attack succeeds once enough Sybils sign; CAPM's does
not move, because co-signing relays cannot author the origin's class assertion.

Run:  python3 -m experiments.e3_4_collusion
"""

from __future__ import annotations

import csv
import os

from capm.benchmark.harness import collusion_spec
from capm.benchmark.runner import run_trial
from capm.core.types import WarrantLevel

OUT_DIR = os.path.join("results", "p2", "e3_4")
CHAIN_LENGTHS = (4, 6, 8)
ACCEPT_FLOOR = int(WarrantLevel.MODERATE)


def run():
    rows = []
    for L in CHAIN_LENGTHS:
        for k in range(0, L):                       # k colluding relays
            spec = collusion_spec(k)
            r = run_trial("capm", n_hops=L, adversary=spec.origin,
                          relay_adversaries=spec.relays)
            # strawman: a defense that adds 1 warrant level per trusted co-signer
            naive_warrant = min(int(WarrantLevel.STRONG), int(r.warrant) + k)
            rows.append(dict(chain_length=L, n_colluders=k,
                             capm_decision=r.decision, capm_warrant=int(r.warrant),
                             capm_asr=int(r.attack_succeeded),
                             naive_warrant=naive_warrant,
                             naive_asr=int(naive_warrant >= ACCEPT_FLOOR)))
    return rows


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = run()

    print("=" * 80)
    print("E3.4  Collusion / Sybil: warrant is origin-bounded, not relay-bounded")
    print("=" * 80)
    for L in CHAIN_LENGTHS:
        sub = [r for r in rows if r["chain_length"] == L]
        warrants = [r["capm_warrant"] for r in sub]
        asrs = [r["capm_asr"] for r in sub]
        flat = len(set(warrants)) == 1
        print(f"\n chain length {L}: vary colluders 0..{L-1}")
        print(f"   {'#colluders':>11s} " + " ".join(f"{r['n_colluders']:>3d}" for r in sub))
        print(f"   {'CAPM warrant':>11s} " + " ".join(f"{w:>3d}" for w in warrants))
        print(f"   {'CAPM ASR':>11s} " + " ".join(f"{a:>3d}" for a in asrs))
        print(f"   {'naive ASR':>11s} " + " ".join(f"{r['naive_asr']:>3d}" for r in sub)
              + "   (signer-counting strawman)")
        print(f"   → CAPM warrant constant across all collusion levels: {flat}")

    capm_flat = all(
        len({r["capm_warrant"] for r in rows if r["chain_length"] == L}) == 1
        for L in CHAIN_LENGTHS)
    capm_asr_total = sum(r["capm_asr"] for r in rows)
    naive_climbs = any(r["naive_asr"] == 1 for r in rows)
    print(f"\nResult: CAPM ASR = {capm_asr_total}/{len(rows)} across every coalition "
          f"size — independent of the number of colluding relays (warrant constant "
          f"per chain: {capm_flat}). A signer-counting heuristic would be laundered "
          f"as Sybils accumulate (naive attack succeeds: {naive_climbs}). Co-signing "
          f"relays cannot author the origin's class assertion, so they cannot raise "
          f"warrant — the strong, distinctive collusion result.")

    csv_path = os.path.join(OUT_DIR, "collusion.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    fig_path = _make_figure(rows)

    print(f"\nCSV: {csv_path}")
    if fig_path:
        print(f"Fig: {fig_path}")
    print("=" * 80)
    ok = capm_flat and capm_asr_total == 0 and naive_climbs
    print("PASS" if ok else "FAIL")
    return 0 if ok else 2


def _make_figure(rows) -> str:
    try:
        from experiments import figtools as ft
    except Exception as e:
        print(f"(figure skipped: {e})")
        return ""
    fig, ax = ft.new(figsize=(7.8, 4.6))
    # use the longest chain for the headline sweep
    L = max(CHAIN_LENGTHS)
    sub = [r for r in rows if r["chain_length"] == L]
    ks = [r["n_colluders"] for r in sub]
    ax.plot(ks, [r["capm_warrant"] for r in sub], marker="D", color=ft.ACCENT, lw=2.4,
            label="CAPM delivered warrant (origin-bounded)")
    ax.plot(ks, [r["naive_warrant"] for r in sub], marker="s", color=ft.WARN, lw=2.2,
            ls="--", label="signer-counting strawman warrant")
    ax.axhline(ACCEPT_FLOOR, color="#888", ls=":", lw=1)
    ax.text(0, ACCEPT_FLOOR + 0.08, "accept floor", fontsize=8, color="#666")
    ft._style(ax, f"E3.4 — colluding relays cannot raise warrant (chain length {L})",
              xlabel="number of colluding / Sybil relays co-signing",
              ylabel="delivered warrant level")
    ax.set_xticks(ks); ax.set_ylim(-0.2, 4.3)
    ax.legend(fontsize=8, frameon=False, loc="center right")
    ax.text(L / 2, 0.15, "CAPM: flat — ASR independent of coalition size",
            fontsize=8, color=ft.ACCENT, ha="center")
    return ft.save(fig, "e3_4_collusion.png")


if __name__ == "__main__":
    raise SystemExit(main())
