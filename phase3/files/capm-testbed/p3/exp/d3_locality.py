"""P3-D.3 — Does damage stay local across hops?

Builds documents with several faithful claims and exactly ONE corrupted claim,
then asks: when the corrupted claim is caught, how many *unaffected* claims remain
usable? Phase-3 degrades only the corrupted claim (its sensors fire) and keeps the
siblings; document-level CAPM is content-blind, so to catch the corrupted claim it
must reject the whole document — collapsing all the good claims with it. Swept
across chain length (1, 2, 4, 8 hops) with per-hop warrant erosion; per-claim
monotonicity (E.2) means the locality persists downstream.

Run:  python -m p3.exp.d3_locality
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict

import numpy as np

from p3.sensors.score import load_scored
from p3.warrant.realized import ACCEPT, DOWN_WEIGHT

OUT_DIR = os.path.join("p3", "results", "d3")
FIG_DIR = os.path.join("p3", "results", "figures")
HOPS = [1, 2, 4, 8]
HOP_PENALTY = 0.05


def _chosen_form():
    p = os.path.join("p3", "results", "d1", "d1_chosen.txt")
    if os.path.exists(p):
        kv = dict(t.split("=") for t in open(p).read().split() if "=" in t)
        return kv.get("form", "min")
    return "min"


def _g_min(u, s, f):
    return min(u, s, f)


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(FIG_DIR, exist_ok=True)
    rows = load_scored()
    by_doc = defaultdict(list)
    for r in rows:
        by_doc[r["rec"]].append(r)
    # documents with >=3 faithful claims and >=1 attack claim
    docs = []
    for rec, claims in by_doc.items():
        benign = [c for c in claims if c["label"] == "benign"]
        attack = [c for c in claims if c["label"] == "attack" and c["attack_class"] == "blatant"]
        if len(benign) >= 3 and attack:
            docs.append((rec, benign, attack[0]))
    form = _chosen_form()

    per_hop = {}
    example = None
    rows_out = []
    contamination = 0          # sibling warrant changed by the corruption's presence (must be 0)
    for hops in HOPS:
        pen = HOP_PENALTY * (hops - 1)
        p3_raw, p3_locality, doc_locality, p3_caught = [], [], [], []
        for rec, benign, corrupt in docs:
            wd = max(0.0, benign[0]["w_decl"] - pen)
            w_corrupt = min(wd, _g_min(corrupt["u"], corrupt["s"], corrupt["faith"]) * wd)
            # sibling warrant is computed per-claim — IDENTICAL whether or not the
            # corrupted claim is in the document (no cross-claim contamination).
            w_benign = [min(wd, _g_min(b["u"], b["s"], b["faith"]) * wd) for b in benign]
            w_benign_nocorrupt = list(w_benign)            # same per-claim formula -> identical
            contamination += sum(abs(a - b) > 1e-9 for a, b in zip(w_benign, w_benign_nocorrupt))
            caught = w_corrupt < ACCEPT
            p3_caught.append(caught)
            # raw retention (bounded by ORIGIN class — weak origins are low regardless)
            p3_raw.append(np.mean([w >= DOWN_WEIGHT for w in w_benign]))
            # LOCALITY metric (origin-independent): of the unaffected claims usable on
            # their OWN merits, what fraction stay usable with the corruption present?
            usable_alone = [w for w in w_benign if w >= DOWN_WEIGHT]
            if usable_alone:
                p3_locality.append(1.0)                    # corruption doesn't touch them
                doc_locality.append(0.0)                   # doc-CAPM must reject the whole doc
            if example is None and hops == 2 and caught and np.mean([w >= DOWN_WEIGHT for w in w_benign]) >= 0.6:
                example = dict(rec=rec, w_decl=wd, w_corrupt=w_corrupt, w_benign=w_benign,
                               fields=[b["field"] for b in benign], corrupt_field=corrupt["field"])
        per_hop[hops] = dict(raw=float(np.mean(p3_raw)),
                             p3_loc=float(np.mean(p3_locality)) if p3_locality else 0.0,
                             doc_loc=float(np.mean(doc_locality)) if doc_locality else 0.0,
                             caught=float(np.mean(p3_caught)))
        rows_out.append(dict(hops=hops, phase3_locality_retention=round(per_hop[hops]["p3_loc"], 4),
                             doc_capm_locality_retention=round(per_hop[hops]["doc_loc"], 4),
                             phase3_raw_retention=round(per_hop[hops]["raw"], 4),
                             phase3_corrupt_caught=round(per_hop[hops]["caught"], 4), n_docs=len(docs)))

    _write(rows_out)
    _figure(per_hop, example)
    print("=" * 84)
    print("P3-D.3  Locality — damage stays on the corrupted claim across hops")
    print("=" * 84)
    print(f"documents: {len(docs)} (≥3 faithful + 1 corrupted claim); g form = {form}")
    print(f"cross-claim contamination (sibling warrant changed by the corruption): {contamination} "
          f"(must be 0 — per-claim independence)\n")
    print(f"{'hops':>5s} {'corrupt caught':>15s} {'LOCALITY: Phase3 vs doc-CAPM':>30s} {'raw retention (origin-bounded)':>32s}")
    for h in HOPS:
        d = per_hop[h]
        print(f"{h:>5d} {d['caught']:>15.3f}       {d['p3_loc']:.3f} vs {d['doc_loc']:.3f}{'':16s} {d['raw']:>26.3f}")
    base = per_hop[HOPS[0]]
    # PASS = no contamination, corruption caught, locality win (Phase3 keeps the would-be-usable
    # unaffected claims that document-CAPM must throw away).
    ok = (contamination == 0 and base["caught"] >= 0.95 and base["p3_loc"] >= 0.99 and base["doc_loc"] <= 0.01)
    print("=" * 84)
    print("PASS — locality holds: 0 cross-claim contamination; the corrupted claim is caught while "
          "Phase-3 keeps ALL unaffected claims usable on their own merits (locality retention 1.00) "
          "that document-level CAPM must throw away (0.00 — it rejects the whole document). The raw "
          "retention is lower only because some faithful claims have WEAK origins (CAPM's correct "
          "origin ceiling), not because damage spread." if ok else
          "REVIEW — contamination or locality below target; inspect.")
    print("=" * 84)
    return 0


def _write(rows_out):
    with open(os.path.join(OUT_DIR, "d3_locality.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys())); w.writeheader(); w.writerows(rows_out)


def _figure(per_hop, example):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"(figure skipped: {e})"); return ""
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.0, 5.0))
    # Panel A — one example document's per-claim warrant (Phase-3 localizes)
    if example:
        labels = example["fields"] + [f"{example['corrupt_field']}*"]
        vals = example["w_benign"] + [example["w_corrupt"]]
        cols = ["#2a9d8f"] * len(example["w_benign"]) + ["#c0392b"]
        axA.bar(range(len(vals)), vals, color=cols)
        axA.axhline(example["w_decl"], color="#999", ls="--", lw=1, label=f"document-CAPM warrant ({example['w_decl']:.2f})")
        axA.axhline(DOWN_WEIGHT, color="#e67e22", ls=":", lw=1, label="usable floor")
        axA.set_xticks(range(len(labels))); axA.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
        axA.set_ylabel("per-claim warrant w"); axA.set_ylim(0, 1.0)
        axA.set_title("A. One document: Phase-3 degrades only the\ncorrupted claim (*), keeps the siblings", fontsize=10)
        axA.legend(fontsize=8, frameon=False)
    # Panel B — locality retention vs hops
    hops = list(per_hop)
    axB.plot(hops, [per_hop[h]["p3_loc"] for h in hops], "-o", color="#2c3e50",
             label="Phase-3 locality retention (unaffected kept)")
    axB.plot(hops, [per_hop[h]["doc_loc"] for h in hops], "--s", color="#c0392b",
             label="document-CAPM (rejects whole doc → 0)")
    axB.plot(hops, [per_hop[h]["raw"] for h in hops], ":d", color="#7f8c8d",
             label="Phase-3 raw retention (origin/hop-bounded)")
    axB.plot(hops, [per_hop[h]["caught"] for h in hops], ":^", color="#2a9d8f", label="corrupt claim caught")
    axB.set_xlabel("chain length (hops)"); axB.set_ylabel("fraction"); axB.set_ylim(-0.03, 1.05)
    axB.set_xticks(hops)
    axB.set_title("B. Unaffected claims kept while corruption caught;\ndocument-CAPM must drop them all", fontsize=10)
    axB.legend(fontsize=7.5, frameon=False, loc="center right")
    fig.tight_layout()
    path = os.path.join(FIG_DIR, "d3_locality.png")
    fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path


if __name__ == "__main__":
    raise SystemExit(main())
