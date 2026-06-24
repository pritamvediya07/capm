"""E6.3 — manifest growth & Merkle compaction for long chains.

A manifest grows O(N) in chain length. This experiment builds a real **Merkle
compaction** (`capm/manifest/compaction.py`): segments[1:-k] are rolled up into a
single **signed checkpoint** carrying a Merkle root + the exact warrant state, so
the wire form is O(window) instead of O(N). We show three things:

  1. **Size** — full manifest grows linearly; the compact form stays flat.
  2. **Correctness** — warrant computed from the compact form is BIT-IDENTICAL to
     evaluating the full manifest, at every N (the erosion algebra is incremental).
  3. **Soundness** — tampering a recent segment, or forging the signed checkpoint,
     is REJECTED; and any compacted segment can be proven included via a Merkle
     inclusion proof (auditability preserved).

Run:  python3 -m experiments.e6_3_compaction
"""

from __future__ import annotations

import csv
import dataclasses
import os

from capm.agents.responders import DeterministicResponder
from capm.benchmark.scenarios import build_chain
from capm.core.types import TransformationType
from capm.identity.credentials import AgentIdentity
from capm.manifest import compaction as cp
from capm.warrant.evaluator import WarrantEvaluator

OUT_DIR = os.path.join("results", "p2", "e6_3")
KEEP_RECENT = 4
_VERB = DeterministicResponder(transformation=TransformationType.VERBATIM)


def _scenario(n):
    sc = build_chain(n_hops=n, relay_responder=_VERB)   # verbatim → non-zero warrant
    msg = sc.query("v?")
    comp = AgentIdentity(did="did:capm:compactor", org="org-relay")
    sc.registry.register(comp)
    return sc, msg, comp


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 80)
    print("E6.3  Manifest growth & Merkle compaction (size, correctness, soundness)")
    print("=" * 80)
    print(f"compaction rolls up segments[1:-{KEEP_RECENT}] into a signed Merkle "
          f"checkpoint.\n")
    print(f"  {'hops':>5s} {'full(bytes)':>12s} {'compact(bytes)':>15s} {'saved':>7s} "
          f"{'full W':>7s} {'compact W':>10s} {'match':>6s} {'verify':>7s}")
    print("  " + "-" * 76)

    rows = []
    all_match = True
    for n in (6, 8, 12, 16, 24, 32, 48, 64):
        sc, msg, comp = _scenario(n)
        full_w = int(WarrantEvaluator(sc.registry).evaluate(msg.manifest, msg.content).warrant)
        cm = cp.compact(msg.manifest, comp, keep_recent=KEEP_RECENT)
        cw, ok = cp.compact_warrant(cm, sc.registry)
        full_sz, comp_sz = len(msg.manifest.to_json()), len(cm.to_json())
        match = (full_w == cw)
        all_match &= (match and ok)
        rows.append(dict(hops=n, full_bytes=full_sz, compact_bytes=comp_sz,
                         saved_pct=round(100 * (1 - comp_sz / full_sz), 1),
                         full_warrant=full_w, compact_warrant=cw,
                         match=int(match), verify_ok=int(ok)))
        print(f"  {n:>5d} {full_sz:>12d} {comp_sz:>15d} {rows[-1]['saved_pct']:>6.1f}% "
              f"{full_w:>7d} {cw:>10d} {str(match):>6s} {str(ok):>7s}")

    # --- soundness: tamper + forgery must be REJECTED -----------------------
    print("\nSoundness checks (all must be REJECTED):")
    # use a paraphrase chain so the checkpoint warrant is LOW (0) and the forgery
    # is a genuine inflation (→ 4), not a no-op.
    psc = build_chain(n_hops=16)            # default paraphrase relays
    pmsg = psc.query("v?")
    pcomp = AgentIdentity(did="did:capm:compactor2", org="org-relay"); psc.registry.register(pcomp)
    pcm = cp.compact(pmsg.manifest, pcomp, keep_recent=KEEP_RECENT)
    base_w, _ = cp.compact_warrant(pcm, psc.registry)
    # (a) tamper a recent segment's content_hash
    bad = cp.CompactManifest(pcm.origin_segment, pcm.checkpoint,
                             [dataclasses.replace(s) for s in pcm.recent_segments])
    bad.recent_segments[-1].content_hash = "00" * 32
    _, ok_a = cp.compact_warrant(bad, psc.registry)
    # (b) forge the checkpoint warrant: inflate from base_w to 4 without re-signing
    bad_cp = dataclasses.replace(pcm.checkpoint, warrant_at_checkpoint=4)
    bad2 = cp.CompactManifest(pcm.origin_segment, bad_cp, pcm.recent_segments)
    forged_w, ok_b = cp.compact_warrant(bad2, psc.registry)
    print(f"  (checkpoint warrant was {base_w}; forgery tries to inflate to 4)")
    # (c) Merkle inclusion proof of a compacted segment
    leaves = [s.segment_hash() for s in [pmsg.manifest.segments[0]] + pmsg.manifest.segments[1:-KEEP_RECENT]]
    proof = cp.merkle_proof(leaves, 5)
    incl = cp.verify_merkle_proof(leaves[5], proof, pcm.checkpoint.merkle_root)
    print(f"  tampered recent segment -> verify_ok={ok_a}  (expect False)")
    print(f"  forged checkpoint warrant -> verify_ok={ok_b}  (expect False)")
    print(f"  Merkle inclusion proof of a compacted segment -> valid={incl}  (expect True)")

    print(f"\nResult: the compact wire form stays ~flat (~{rows[-1]['compact_bytes']} B) "
          f"while the full manifest grows to {rows[-1]['full_bytes']} B at "
          f"{rows[-1]['hops']} hops ({rows[-1]['saved_pct']:.0f}% saved); warrant is "
          f"bit-identical full-vs-compact at every N ({all_match}); tampering/forgery "
          f"is rejected and compacted segments remain Merkle-provable. Manifest size "
          f"stays practical at long N.")

    csv_path = os.path.join(OUT_DIR, "compaction.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    fig_path = _make_figure(rows)

    print(f"\nCSV: {csv_path}")
    if fig_path:
        print(f"Fig: {fig_path}")
    print("=" * 80)
    ok = all_match and (not ok_a) and (not ok_b) and incl
    print("PASS" if ok else "FAIL")
    return 0 if ok else 2


def _make_figure(rows) -> str:
    try:
        from experiments import figtools as ft
    except Exception as e:
        print(f"(figure skipped: {e})")
        return ""
    hops = [r["hops"] for r in rows]
    full = [r["full_bytes"] / 1024 for r in rows]
    comp = [r["compact_bytes"] / 1024 for r in rows]
    fig, ax = ft.new(figsize=(7.6, 4.6))
    ax.plot(hops, full, "-o", color=ft.WARN, lw=2.2, label="full manifest (O(N))")
    ax.plot(hops, comp, "-D", color=ft.ACCENT, lw=2.2,
            label=f"Merkle-compacted (O(window={KEEP_RECENT}))")
    ax.fill_between(hops, comp, full, color=ft.BASE, alpha=0.15)
    ft._style(ax, "E6.3 — Merkle compaction bounds manifest size at long N",
              xlabel="chain length (hops)", ylabel="serialized manifest size (KiB)")
    ax.set_ylim(0, max(full) * 1.1)
    ax.legend(fontsize=8.5, frameon=False, loc="upper left")
    ax.text(hops[len(hops)//2], comp[len(comp)//2] + max(full) * 0.18,
            "warrant bit-identical\nfull ↔ compact", fontsize=8, color="#555", ha="center")
    return ft.save(fig, "e6_3_compaction.png")


if __name__ == "__main__":
    raise SystemExit(main())
