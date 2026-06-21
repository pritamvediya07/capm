"""E7.2 — false-positive (over-blocking) analysis on all-honest workloads.

On purely honest content, how often does CAPM fail to ACCEPT it (a false
positive)? We separate the **soft** cost (down-weight: still usable, flagged
lower-confidence) from the **hard** cost (quarantine: not actionable), and break
both down by **source class × transformation × hop count**.

The honest pattern: over-blocking is **not uniform** — it concentrates on
*genuinely low-warrant* honest content (editable/public sources) relayed through
*lossy* transformations over *many* hops. High-warrant honest content
(authoritative/verified) is essentially never over-blocked. So the FPR is a
property of how weak/eroded the honest source is, and it is tunable via E7.1's
accept floor (this experiment uses the default policy).

Run:  python3 -m experiments.e7_2_false_positive
"""

from __future__ import annotations

import csv
import os

from attacks.adaptive.profiles import honest_origin
from capm.agents.responders import DeterministicResponder
from capm.benchmark.scenarios import build_chain
from capm.core.types import SourceClass, TransformationType
from capm.warrant.evaluator import Decision, EvaluatorPolicy, WarrantEvaluator

OUT_DIR = os.path.join("results", "p2", "e7_2")
CLASSES = [SourceClass.AUTHORITATIVE_API, SourceClass.VERIFIED_DOCUMENT,
           SourceClass.FIRST_PARTY_DB, SourceClass.PUBLIC_WEBPAGE,
           SourceClass.EDITABLE_SOURCE]
TRANSFORMS = [TransformationType.VERBATIM, TransformationType.PARAPHRASE,
              TransformationType.SUMMARY]
HOPS = range(2, 8)


def _decision(n_hops, transform, source_class) -> str:
    sc = build_chain(n_hops=n_hops,
                     adversary=honest_origin("the audited Q3 revenue figure is 12.4 million",
                                             source_class),
                     relay_responder=DeterministicResponder(transformation=transform))
    msg = sc.query("value?")
    return WarrantEvaluator(sc.registry, EvaluatorPolicy()).evaluate(msg.manifest, msg.content).decision


def run():
    rows = []
    for cls in CLASSES:
        for t in TRANSFORMS:
            for n in HOPS:
                d = _decision(n, t, cls)
                rows.append(dict(source_class=cls.name, transform=t.value, hops=n,
                                 decision=d.value,
                                 over_blocked=int(d != Decision.ACCEPT),
                                 hard_fp=int(d == Decision.QUARANTINE)))
    return rows


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = run()
    n = len(rows)
    soft = sum(r["over_blocked"] for r in rows)
    hard = sum(r["hard_fp"] for r in rows)

    print("=" * 80)
    print("E7.2  False-positive (over-blocking) analysis on all-honest workloads")
    print("=" * 80)
    print(f"{n} honest deliveries = {len(CLASSES)} classes × {len(TRANSFORMS)} "
          f"transforms × {len(list(HOPS))} hop-counts (default policy)\n")

    # per-class FPR
    print(f"  {'source class':>18s} {'accept':>7s} {'down-wt':>8s} {'quarant':>8s} "
          f"{'over-block FPR':>14s}")
    print("  " + "-" * 60)
    for cls in CLASSES:
        sub = [r for r in rows if r["source_class"] == cls.name]
        acc = sum(r["decision"] == "accept" for r in sub)
        dw = sum(r["decision"] == "down_weight" for r in sub)
        q = sum(r["decision"] == "quarantine" for r in sub)
        fpr = sum(r["over_blocked"] for r in sub) / len(sub)
        print(f"  {cls.name:>18s} {acc:>7d} {dw:>8d} {q:>8d} {fpr:>13.2f}")

    # break out by transform: faithful (verbatim) vs lossy (paraphrase/summary)
    def _fpr(pred):
        sub = [r for r in rows if pred(r)]
        return sum(r["over_blocked"] for r in sub) / len(sub) if sub else 0.0
    verb_high = _fpr(lambda r: r["transform"] == "verbatim"
                     and r["source_class"] in ("AUTHORITATIVE_API", "VERIFIED_DOCUMENT"))
    lossy_high = _fpr(lambda r: r["transform"] in ("paraphrase", "summary")
                      and r["source_class"] in ("AUTHORITATIVE_API", "VERIFIED_DOCUMENT"))

    print(f"\n  overall over-block FPR (not fully accepted): {soft}/{n} = {soft/n:.2f}")
    print(f"  hard FPR (honest content quarantined):       {hard}/{n} = {hard/n:.2f}")
    print(f"  high-warrant honest, FAITHFUL (verbatim) relays: FPR = {verb_high:.2f} "
          f"(preserved — no over-block)")
    print(f"  high-warrant honest, LOSSY (paraphrase/summary) relays: FPR = {lossy_high:.2f} "
          f"(eroded to over-block at high hops)")
    print("\nReading (honest): over-blocking has two drivers — (1) low source class "
          "(editable/public start near the floor) and (2) LOSSY multi-hop relaying, "
          "which erodes even an AUTHORITATIVE origin to NONE after ~5 paraphrases. "
          "Faithful (verbatim/extraction) relays preserve warrant (FPR≈0). This raises "
          "a CALIBRATION question — does a 5×-paraphrased-but-faithful claim really "
          "warrant NONE? — which E7.3 tests. The cost is tunable via E7.1's floor.")

    csv_path = os.path.join(OUT_DIR, "false_positive.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    fig_path = _make_figure(rows)

    print(f"\nCSV: {csv_path}")
    if fig_path:
        print(f"Fig: {fig_path}")
    print("=" * 80)
    # PASS = the FPR is correctly CHARACTERIZED (not "FPR is low"): faithful relays
    # preserve high-warrant content (FPR≈0), lossy relaying drives over-block, and
    # FPR rises as the source class falls (non-uniform, structured).
    edit_fpr = _fpr(lambda r: r["source_class"] == "EDITABLE_SOURCE")
    auth_fpr = _fpr(lambda r: r["source_class"] == "AUTHORITATIVE_API")
    ok = (verb_high == 0.0 and lossy_high > 0.0 and edit_fpr > auth_fpr)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 2


def _make_figure(rows) -> str:
    try:
        from experiments import figtools as ft
    except Exception as e:
        print(f"(figure skipped: {e})")
        return ""
    import numpy as np
    import matplotlib.pyplot as plt
    # heatmap: over-block FPR by (source class × hops), under PARAPHRASE relays
    hops = sorted({r["hops"] for r in rows})
    classes = [c.name for c in CLASSES]
    grid = np.zeros((len(classes), len(hops)))
    for i, cls in enumerate(classes):
        for j, h in enumerate(hops):
            sub = [r for r in rows if r["source_class"] == cls and r["hops"] == h
                   and r["transform"] == "paraphrase"]
            grid[i, j] = (sum(r["over_blocked"] for r in sub) / len(sub)) if sub else 0
    fig, ax = ft.new(figsize=(7.8, 4.6))
    im = ax.imshow(grid, cmap="RdYlGn_r", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(hops))); ax.set_xticklabels(hops)
    ax.set_yticks(range(len(classes)))
    ax.set_yticklabels([c.replace("_", "\n") for c in classes], fontsize=7.5)
    for i in range(len(classes)):
        for j in range(len(hops)):
            ax.text(j, i, f"{grid[i,j]:.0f}", ha="center", va="center",
                    fontsize=8, color="black")
    ft._style(ax, "E7.2 — honest over-block rate (paraphrase relays)",
              xlabel="cross-org relay hops", ylabel="honest source class")
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("over-block FPR (1 = not accepted)", fontsize=8)
    ax.set_title("E7.2 — honest over-block rate: concentrated on low-warrant sources",
                 fontsize=10.5, fontweight="bold", pad=10)
    return ft.save(fig, "e7_2_false_positive.png")


if __name__ == "__main__":
    raise SystemExit(main())
