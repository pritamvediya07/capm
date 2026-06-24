"""P4-3.C2 — contradiction vs valid abstraction on scaled NLI (WS3).

Scales the faith sensor from Phase-3's DeBERTa-v3-xsmall to -base and -large, with
premise = ctx (the WS1/E.4 fix) and the schema numeric rule. Measures genuine-
contradiction recall, valid-abstraction FPR (must stay low — the over-blocking
risk a bigger NLI raises), and the CVSS-band recall the schema rule must lift.

Run:  python -m p4.exp.p3_c2_nli_contradiction
"""
from __future__ import annotations
import csv, os
from p3.sensors.nli import NLISensor
from p3.sensors import schema_numeric_rule as schema

OUT = os.path.join("p4", "results", "ws3", "c2")
NLI_MODELS = ["cross-encoder/nli-deberta-v3-base", "cross-encoder/nli-deberta-v3-large"]

# genuine contradictions (premise = source ctx, hypothesis = the laundered claim) — must score contradict
GENUINE = [
    ("CVSS base score is 9.1.", "the severity is low"),                         # band flip (schema)
    ("CVSS base score is 8.8.", "the severity is none"),                        # band flip (schema)
    ("CVSS base score is 9.1.", "CVSS base score is 2.0"),                      # score flip (schema)
    ("vendor Microsoft; product Windows.", "the vendor is Adobe"),             # vendor swap (NLI)
    ("vendor Cisco; product IOS XE.", "the vendor is Juniper"),                # vendor swap (NLI)
    ("A patch (KB5005) is available.", "no patch is available"),               # patch flip (NLI)
    ("Patched in version 2.4.1.", "the product remains unpatched"),            # patch flip (NLI)
    ("Affected: Windows 10 and Windows 11.", "only Windows 7 is affected"),    # scope (NLI)
    ("Known ransomware use: yes.", "there is no known ransomware use"),        # boolean flip (NLI)
    ("Due date 2022-05-16.", "the due date is 2025-01-01"),                    # date flip (NLI)
]
# valid abstractions (must NOT be flagged contradict)
ABSTRACTION = [
    ("CVSS base score is 9.1.", "the severity is Critical"),                   # band abstraction (schema entail)
    ("CVSS base score is 8.8.", "the severity is High"),                       # band abstraction (schema entail)
    ("Patch KB5005 was released.", "a patch exists"),                          # NLI entail
    ("Affected: Windows 10 and Windows 11.", "Windows is affected"),          # NLI entail
    ("vendor Microsoft; product Exchange Server.", "a Microsoft product is affected"),
    ("Known ransomware use: yes.", "the vulnerability has been used in attacks"),
]
BAND = [("CVSS base score is 9.1.", "the severity is low"),
        ("CVSS base score is 7.5.", "the severity is none")]


def faith_lab(nli, prem, hyp, use_schema):
    if use_schema:
        sc = schema.schema_compare(prem, hyp)
        if sc is not None:
            return sc
    return nli.predict(prem, hyp)[0]


def main():
    os.makedirs(OUT, exist_ok=True)
    print("=" * 92)
    print("P4-3.C2  contradiction vs abstraction on scaled NLI (premise = ctx)")
    print("=" * 92)
    print(f"genuine contradictions: {len(GENUINE)} | valid abstractions: {len(ABSTRACTION)} | CVSS-band: {len(BAND)}")
    print(f"{'NLI model':40s} {'schema':>7s} {'genuine-recall':>15s} {'abstraction-FPR':>16s} {'band-recall':>12s}")
    rows = []
    for mname in NLI_MODELS:
        try:
            nli = NLISensor(mname)
        except Exception as e:
            print(f"  {mname}: load failed ({e})"); continue
        for use_schema in (False, True):
            gr = sum(faith_lab(nli, p, h, use_schema) == "contradict" for p, h in GENUINE) / len(GENUINE)
            fpr = sum(faith_lab(nli, p, h, use_schema) == "contradict" for p, h in ABSTRACTION) / len(ABSTRACTION)
            br = sum(faith_lab(nli, p, h, use_schema) == "contradict" for p, h in BAND) / len(BAND)
            print(f"{mname.split('/')[-1]:40s} {'on' if use_schema else 'off':>7s} {gr:>15.2f} {fpr:>16.2f} {br:>12.2f}")
            rows.append(dict(nli_model=mname.split("/")[-1], schema_rule="on" if use_schema else "off",
                             genuine_recall=round(gr, 3), abstraction_fpr=round(fpr, 3),
                             cvss_band_recall=round(br, 3), premise_source="ctx"))
    with open(os.path.join(OUT, "c2_nli.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    best = [r for r in rows if r["schema_rule"] == "on"]
    ok = best and all(r["genuine_recall"] >= 0.9 and r["abstraction_fpr"] <= 0.1 for r in best)
    print("=" * 92)
    print(f"{'PASS' if ok else 'REVIEW'} — with the schema rule, genuine recall ≥0.9 and abstraction FPR low at "
          "scaled NLI; the schema rule lifts CVSS-band recall (NLI alone scores digit→word band flips neutral). "
          "Delta vs Phase-3 (xsmall): report any entail/neutral boundary shift at -large (faith-saturation risk).")
    print("=" * 92)


if __name__ == "__main__":
    main()
