"""P3-E.3 — Can a malicious relay forge a sensor value or supply a self-serving parent?

Validates §7a (sensor-placement enforcement) and §5 (claimed-not-trusted lineage).
A malicious relay tries to escape detection on a fabricated claim by:
  (a) forging the warrant-affecting sensors (u=s=faith=1.0) tagged with an
      untrusted/lied placement, and
  (b) pointing the fabricated claim at a high-support source via claimed_parent_id.

The verifier must: discard relay-placed / unattested sensor values and recompute
the verifier-side sensors itself; re-derive verified_parent_id with the matcher
and degrade on mismatch; and never let the result exceed baseline.

Positive controls confirm the verifier is not simply rejecting everything: a
LEGITIMATELY attested u (on an honest claim) IS honored, and a faithful claim with
a correct parent keeps its warrant.

Run:  python -m p3.exp.e3_forgery_and_lineage [--advisories N]
"""

from __future__ import annotations

import argparse
import csv
import os

from p3.claims.extract import extract_claims
from p3.data.advisories.corpus import load_advisories
from p3.data.advisories.transform import generate
from p3.manifest.field import RealizedField, RealizedVerifier

OUT_DIR = os.path.join("p3", "results", "e3")
FIG_DIR = os.path.join("p3", "results", "figures")
W_DECL = 0.85          # baseline CAPM gives the laundered claim a HIGH declared warrant (cf. A.1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--advisories", type=int, default=50)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(FIG_DIR, exist_ok=True)
    advs = load_advisories(n=args.advisories, seed=21)
    verifier = RealizedVerifier(usage_provider=None)   # no trusted u provider (focus: reject forgeries)

    rows = []
    for a in advs:
        claims = extract_claims(a)
        src_keys = [c.key for c in claims]
        # a memory-substituted output: substituted field (distorted) + added patch/severity
        tr = next(t for t in generate(a, seed=0)
                  if t.transform_type == "memory_substituted" and t.compression == "light")
        fab_text = tr.text
        sub_field = tr.laundered_fields[0]                       # the distorted field
        high_support_parent = f"{a['record_id']}:{src_keys[0]}"  # a self-serving (wrong) parent

        # ---- ATTACK CASES on a fabricated 'added' claim (patch_status) ----------
        attacks = [
            ("relay_forge",   {"u": "relay"},           {},            high_support_parent),
            ("lie_attested",  {"u": "attested_service"}, {},           f"{a['record_id']}:{src_keys[-1]}"),
            ("random_parent", {"u": "relay"},           {},            f"{a['record_id']}:cwe"),
        ]
        for name, placement, attest, claimed_parent in attacks:
            fld = RealizedField(claim_id=f"{a['record_id']}:patch_status:{name}",
                                field_key="patch_status", claimed_parent_id=claimed_parent,
                                u=1.0, s=1.0, faith=1.0, sensor_placement=placement,
                                attestations=attest)
            v = verifier.verify_claim(fld, claims, fab_text, W_DECL)
            rows.append(_row(name, "forged_added", fld, v))

        # the distorted (substituted) claim, forged the same way
        fld = RealizedField(claim_id=f"{a['record_id']}:{sub_field}:relay_forge",
                            field_key=sub_field, claimed_parent_id=high_support_parent,
                            u=1.0, s=1.0, faith=1.0, sensor_placement={"u": "relay"}, attestations={})
        rows.append(_row("relay_forge", "forged_distorted", fld,
                         verifier.verify_claim(fld, claims, fab_text, W_DECL)))

        # ---- POSITIVE CONTROLS --------------------------------------------------
        # (1) a faithful (survived) claim with the CORRECT parent -> warrant kept, parent not corrected
        faithful = next(t for t in generate(a, seed=0) if t.transform_type == "faithful_summary"
                        and t.compression == "light")
        fld = RealizedField(claim_id=f"{a['record_id']}:{src_keys[0]}:faithful",
                            field_key=src_keys[0], claimed_parent_id=f"{a['record_id']}:{src_keys[0]}",
                            u=None, s=None, faith=None, sensor_placement={}, attestations={})
        rows.append(_row("faithful_correct", "honest", fld,
                         verifier.verify_claim(fld, claims, faithful.text, W_DECL)))
        # (2) a LEGITIMATELY attested u on the faithful claim -> u honored
        fld = RealizedField(claim_id=f"{a['record_id']}:{src_keys[0]}:legit_attested",
                            field_key=src_keys[0], claimed_parent_id=f"{a['record_id']}:{src_keys[0]}",
                            u=0.9, s=None, faith=None,
                            sensor_placement={"u": "attested_service"}, attestations={"u": True})
        rows.append(_row("legit_attested", "honest", fld,
                         verifier.verify_claim(fld, claims, faithful.text, W_DECL)))

    _write_csv(rows)
    _summary_and_figure(rows)
    return 0


def _row(scenario, kind, fld, v):
    return dict(case_id=fld.claim_id, scenario=scenario, kind=kind,
                forged_sensor="u,s,faith" if kind.startswith("forged") else "none",
                sensor_placement=fld.sensor_placement.get("u", "n/a"),
                placement_honored=v.u_honored,
                claimed_parent=fld.claimed_parent_id, verified_parent=v.verified_parent_id,
                parent_corrected=v.parent_corrected, effect=v.effect,
                w_decl=W_DECL, w_final=round(v.rw.w, 4), decision=v.decision,
                exceeds_baseline=bool(v.rw.w > W_DECL + 1e-9))


def _write_csv(rows):
    with open(os.path.join(OUT_DIR, "e3_forgery.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


def _summary_and_figure(rows):
    forged = [r for r in rows if r["kind"].startswith("forged")]
    honest = [r for r in rows if r["kind"] == "honest"]
    legit = [r for r in honest if r["scenario"] == "legit_attested"]
    faithful = [r for r in honest if r["scenario"] == "faithful_correct"]

    forged_u_rejected = sum(1 for r in forged if not r["placement_honored"]) / len(forged)
    parent_corrected = sum(1 for r in forged if r["parent_corrected"]) / len(forged)
    exceeds = sum(1 for r in rows if r["exceeds_baseline"])
    forged_quarantined = sum(1 for r in forged if r["decision"] == "quarantine") / len(forged)
    legit_honored = sum(1 for r in legit if r["placement_honored"]) / max(1, len(legit))
    faithful_kept = sum(1 for r in faithful if r["decision"] == "accept") / max(1, len(faithful))

    print("=" * 84)
    print("P3-E.3  Forged sensors & self-serving parents are rejected (§7a, §5)")
    print("=" * 84)
    print(f"cases: {len(rows)}  (forged {len(forged)}, honest controls {len(honest)})\n")
    print(f"  forged relay/unattested u REJECTED (placement not honored): {forged_u_rejected:.2f}  (target 1.00)")
    print(f"  self-serving parent corrected (verified ≠ claimed)        : {parent_corrected:.2f}")
    print(f"  forged fabricated claims QUARANTINED (warrant → low)      : {forged_quarantined:.2f}")
    print(f"  any warrant exceeding baseline (must be 0)                : {exceeds}")
    print(f"  POSITIVE control — legitimately attested u honored        : {legit_honored:.2f}")
    print(f"  POSITIVE control — faithful claim with correct parent kept: {faithful_kept:.2f}")
    _figure(rows, dict(forged_u_rejected=forged_u_rejected, parent_corrected=parent_corrected,
                       forged_quarantined=forged_quarantined, legit_honored=legit_honored,
                       faithful_kept=faithful_kept))
    ok = (forged_u_rejected >= 0.999 and exceeds == 0 and parent_corrected >= 0.999
          and legit_honored >= 0.999 and faithful_kept >= 0.999)
    print("=" * 84)
    print("PASS — forged sensor values from untrusted/unattested placements are rejected 100%, "
          "self-serving parents are corrected, no warrant exceeds baseline; and the verifier still "
          "honors a legitimately-attested u and keeps faithful claims (not blanket rejection)."
          if ok else "FAIL — a forged value was honored or a warrant exceeded baseline.")
    print("=" * 84)
    return 0 if ok else 2


def _figure(rows, m):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        print(f"(figure skipped: {e})"); return ""
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.0, 5.0))
    labels = ["forged u\nrejected", "self-serving\nparent corrected", "forged claim\nquarantined",
              "legit attested u\nhonored", "faithful claim\nkept"]
    vals = [m["forged_u_rejected"], m["parent_corrected"], m["forged_quarantined"],
            m["legit_honored"], m["faithful_kept"]]
    cols = ["#2c3e50", "#2c3e50", "#2c3e50", "#2a9d8f", "#2a9d8f"]
    axA.bar(range(len(vals)), vals, color=cols)
    for i, v in enumerate(vals):
        axA.text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=9)
    axA.set_xticks(range(len(vals))); axA.set_xticklabels(labels, fontsize=8)
    axA.set_ylim(0, 1.12); axA.set_ylabel("rate")
    axA.set_title("A. Trust-model enforcement\n(dark = attacks blocked · green = honest honored)", fontsize=10)

    # final warrant: forged-fabricated (→ low) vs honest (→ kept high)
    forged_w = [r["w_final"] for r in rows if r["kind"].startswith("forged")]
    honest_w = [r["w_final"] for r in rows if r["kind"] == "honest"]
    axB.hist([forged_w, honest_w], bins=12, color=["#c0392b", "#2a9d8f"],
             label=["forged/fabricated claims", "honest claims"])
    axB.axvline(0.85, color="#333", ls="--", lw=1, label="baseline w_decl = 0.85")
    axB.set_xlabel("final realized warrant w"); axB.set_ylabel("count")
    axB.set_title("B. Forged claims driven to quarantine;\nhonest kept — none exceed baseline", fontsize=10)
    axB.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    path = os.path.join(FIG_DIR, "e3_forgery_and_lineage.png")
    fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path


if __name__ == "__main__":
    raise SystemExit(main())
