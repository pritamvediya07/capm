"""P4-1C — A.1 table regeneration + tree-wide stale-cell sweep (WS1, MEDIUM).

The Phase-3 ledger published the relaunder-each-hop row of A.1 Table 2 as
`0.667 | 0.583 | 0.417 | 0.000`. The grid is content-blind, so every cell must be
a multiple of 1/3 — `0.583` (7/12) and `0.417` (5/12) are arithmetically
impossible: stale cells from an earlier config. This regenerates every published
A.1 cell directly from `p3/results/a1/a1_raw.csv` and flags any mismatch against
the published values, then sweeps the whole results tree for the stale literals.

Run:  python -m p4.audit.recompute_tables
"""

from __future__ import annotations

import csv
import glob
import os

A1 = os.path.join("p3", "results", "a1", "a1_raw.csv")
RESULTS = os.path.join("p3", "results")
OUT = os.path.join("p4", "results", "p1c")


def _b(v):
    return str(v).strip().lower() in ("1", "true", "yes")


def _rate(rows, pred, field):
    sub = [r for r in rows if pred(r)]
    return (sum(1 for r in sub if _b(r[field])) / len(sub)) if sub else float("nan")


# ---- the PUBLISHED ledger values (what a reviewer reads) ------------------------
PUBLISHED = {
    "headline.manifest_valid": 1.000, "headline.usable": 0.542, "headline.accepted": 0.208,
    "table1.STRONG.usable": 0.875, "table1.STRONG.accepted": 0.625,
    "table1.MODERATE.usable": 0.750, "table1.MODERATE.accepted": 0.000,
    "table1.WEAK.usable": 0.000, "table1.WEAK.accepted": 0.000,
    "table2.relaunder.1": 0.667, "table2.relaunder.2": 0.583,   # <-- stale
    "table2.relaunder.3": 0.417, "table2.relaunder.5": 0.000,    # <-- stale
    "table2.single.1": 0.667, "table2.single.2": 0.667,
    "table2.single.3": 0.667, "table2.single.5": 0.667,
}
# map CSV source_class -> ceiling label used in Table 1 (actual a1_raw.csv values)
CEIL = {"STRONG-API": "STRONG", "MODERATE-DB": "MODERATE", "WEAK-webpage": "WEAK"}


def recompute_a1():
    rows = list(csv.DictReader(open(A1)))
    laundered = [r for r in rows if _b(r.get("laundered_groundtruth", "")) or r["transform_type"] != "faithful_summary"]
    rec = {}
    rec["headline.manifest_valid"] = _rate(rows, lambda r: True, "manifest_valid")
    rec["headline.usable"] = _rate(laundered, lambda r: True, "usable_by_capm")
    rec["headline.accepted"] = _rate(laundered, lambda r: True, "accepted_by_capm")
    # Table 1 — by source-class ceiling
    for ceil in ("STRONG", "MODERATE", "WEAK"):
        pred = lambda r, c=ceil: CEIL.get(r["source_class"], r["source_class"]) == c
        rec[f"table1.{ceil}.usable"] = _rate(laundered, pred, "usable_by_capm")
        rec[f"table1.{ceil}.accepted"] = _rate(laundered, pred, "accepted_by_capm")
    # Table 2 — propagation x hops (the defect)
    for prop_label, prop_val in (("relaunder", "relaunder_each_hop"), ("single", "single_launder_then_relay")):
        for h in (1, 2, 3, 5):
            pred = lambda r, p=prop_val, hh=h: r["propagation"] == p and int(float(r["hops"])) == hh
            rec[f"table2.{prop_label}.{h}"] = _rate(laundered, pred, "usable_by_capm")
    return rec


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    if not os.path.exists(A1):
        print(f"!! {A1} not found on this host — transfer it to run the A.1 audit."); return 2
    rec = recompute_a1()

    print("=" * 92)
    print("P4-1C  A.1 table regeneration — every published cell recomputed from a1_raw.csv")
    print("=" * 92)
    print(f"{'cell':28s} {'published':>10s} {'recomputed':>11s} {'match':>7s}  note")
    mism = []
    audit_rows = []
    for k in PUBLISHED:
        pub, got = PUBLISHED[k], rec.get(k, float("nan"))
        match = (got == got) and abs(pub - got) < 5e-4     # got==got guards NaN
        note = ""
        if not match:
            if got != got:                                  # NaN — recompute key mismatch
                note = "NO ROWS MATCHED (recompute key mismatch — fix the audit, not the table)"
            else:
                # content-blind grid => every cell must be a multiple of 1/3
                pub_on_grid = abs(round(pub * 3) / 3 - pub) < 1e-6
                note = "mismatch" if pub_on_grid else "STALE published cell (impossible on 1/3 grid)"
            mism.append((k, pub, got, note))
        print(f"{k:28s} {pub:>10.3f} {got:>11.3f} {('OK' if match else 'FAIL'):>7s}  {note}")
        audit_rows.append(dict(cell=k, published=round(pub, 4), recomputed=round(got, 4), match=match, note=note))

    print("\nCORRECTED relaunder row (regenerated from CSV):  " +
          " | ".join(f"{rec[f'table2.relaunder.{h}']:.3f}" for h in (1, 2, 3, 5)))

    # ---- tree-wide stale-literal sweep ----------------------------------------
    print("\nTREE-WIDE SWEEP for the stale literals 0.583 / 0.417 across results CSVs:")
    hits = []
    for path in glob.glob(os.path.join(RESULTS, "**", "*.csv"), recursive=True):
        try:
            txt = open(path, errors="ignore").read()
        except Exception:
            continue
        for lit in ("0.583", "0.417"):
            if lit in txt:
                hits.append((os.path.relpath(path), lit))
    if hits:
        for p, lit in hits:
            print(f"  {lit} appears in {p}  (verify it is a legitimate value there, not a stray A.1 cell)")
    else:
        print("  (none found in any results CSV)")

    with open(os.path.join(OUT, "p1c_table_audit.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["cell", "published", "recomputed", "match", "note"])
        w.writeheader(); w.writerows(audit_rows)

    print("=" * 92)
    if mism:
        print(f"FOUND {len(mism)} stale/mismatched published cell(s) — regenerate the ledger table from CSV:")
        for k, pub, got, note in mism:
            print(f"  {k}: published {pub:.3f} -> correct {got:.3f}   [{note}]")
        print("After regeneration every published A.1 cell must recompute exactly from a1_raw.csv.")
    else:
        print("PASS — every published A.1 cell recomputes exactly from a1_raw.csv.")
    print("=" * 92)
    return 1 if mism else 0


if __name__ == "__main__":
    raise SystemExit(main())
