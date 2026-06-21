"""P3-C.2 — Does NLI catch genuine contradictions WITHOUT flagging valid abstraction?

Builds genuine contradictions (CVSS band flips, vendor swaps, patch present→absent,
version-scope 10/11→7, patched→unpatched, ransomware-use flips) AND a valid-
abstraction control set that must NOT be flagged (CVSS 9.1→"Critical", "KB released"
→"a patch exists", "Windows 10/11"→"Windows"). Runs a small and a mid NLI model,
with and without the schema numeric rule, and measures:

  * genuine-contradiction **recall** (target ≳ 0.9), and
  * valid-abstraction **false-positive rate** (must be low — flagging valid
    abstraction is over-blocking).

The headline mechanism: prose NLI scores the digit→word severity cases *neutral*
(it doesn't know CVSS bands), so the **schema numeric rule** must own them — shown
by the with/without-rule ablation.

Run:  python -m p3.exp.c2_nli_contradiction [--seed S]
"""

from __future__ import annotations

import argparse
import csv
import os
import warnings

warnings.filterwarnings("ignore")

from p3.data.advisories.corpus import load_advisories
from p3.sensors.nli import NLISensor
from p3.sensors import schema_numeric_rule as schema

OUT_DIR = os.path.join("p3", "results", "c2")
FIG_DIR = os.path.join("p3", "results", "figures")
NLI_MODELS = [("cross-encoder/nli-deberta-v3-xsmall", "DeBERTa-v3-xsmall (small)"),
              ("roberta-large-mnli", "RoBERTa-large-MNLI (mid)")]

_SCORE_BANDS = [(2.5, "low"), (3.2, "low"), (5.5, "medium"), (6.0, "medium"),
                (7.8, "high"), (8.5, "high"), (9.1, "critical"), (9.8, "critical")]
_WRONG_BAND = {"low": "critical", "medium": "low", "high": "low", "critical": "low"}


def build_cases(seed: int):
    vendors = sorted({a["fields"]["vendor"] for a in load_advisories(120, seed)
                      if a["fields"].get("vendor")})
    rng = __import__("random").Random(seed)
    cases = []

    def add(prem, hyp, gt, ctype, framing, structured, case_type):
        cases.append(dict(claim_id=f"c{len(cases)}", premise=prem, hypothesis=hyp,
                          groundtruth=gt, contradiction_type=ctype, framing=framing,
                          structured=structured, case_type=case_type))

    # --- CVSS numeric (structured) ---
    for score, band in _SCORE_BANDS:
        prem = f"The CVSS base score is {score}."
        add(prem, f"The severity is {_WRONG_BAND[band]}.", "contradict", "cvss_numeric",
            "digit_word_flip", True, "genuine")
        add(prem, f"The severity is {band}.", "entail", "cvss_numeric",
            "digit_word_abstraction", True, "abstraction")
        wrong = 2.0 if score >= 5 else 9.5
        add(prem, f"The CVSS base score is {wrong}.", "contradict", "cvss_numeric",
            "digit_digit", True, "genuine")

    # --- prose genuine contradictions ---
    for v1 in vendors[:10]:
        v2 = rng.choice([v for v in vendors if v != v1])
        add(f"The affected vendor is {v1}.", f"The affected vendor is {v2}.",
            "contradict", "categorical_vendor", "prose", False, "genuine")
    for kb in ("KB5005565", "KB4581309", "KB5012170", "KB5028166", "KB4524570", "KB5011487"):
        add(f"A patch ({kb}) has been released for this vulnerability.",
            "No patch is available for this vulnerability.",
            "contradict", "patch_boolean", "prose", False, "genuine")
    for plat in ("Windows 10 and Windows 11", "Windows Server 2019 and 2022", "macOS 13 and 14"):
        add(f"The vulnerability affects {plat}.", "The vulnerability affects only Windows 7.",
            "contradict", "version_scope", "prose", False, "genuine")
    for _ in range(6):
        add("This vulnerability is known to be used in ransomware campaigns.",
            "This vulnerability is not used in ransomware campaigns.",
            "contradict", "ransomware_boolean", "prose", False, "genuine")
    for ver in ("2.3", "9.0.1", "14.2", "3.1.4"):
        add(f"The issue has been patched in version {ver}.", "The issue remains unpatched.",
            "contradict", "patched_unpatched", "prose", False, "genuine")

    # --- prose valid abstractions (must NOT be flagged contradict) ---
    for kb in ("KB5005565", "KB4581309", "KB5012170", "KB5028166", "KB4524570", "KB5011487"):
        add(f"{kb} has been released to fix this issue.", "A patch exists for this issue.",
            "entail", "patch_boolean", "prose", False, "abstraction")
    for plat in ("Windows 10 and Windows 11", "Windows Server 2019 and 2022", "Ubuntu 20.04 and 22.04"):
        base = plat.split()[0]
        add(f"The vulnerability affects {plat}.", f"The vulnerability affects {base}.",
            "entail", "version_scope", "prose", False, "abstraction")
    for v1 in vendors[:8]:
        add(f"The affected vendor is {v1}.", f"{v1} is the affected vendor.",
            "entail", "categorical_vendor", "prose", False, "abstraction")
    for _ in range(5):
        add("This vulnerability is known to be used in ransomware campaigns.",
            "It has been exploited by ransomware operators.",
            "entail", "ransomware_boolean", "prose", False, "abstraction")
    return cases


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=5)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(FIG_DIR, exist_ok=True)
    cases = build_cases(args.seed)
    genuine = [c for c in cases if c["case_type"] == "genuine"]
    abstr = [c for c in cases if c["case_type"] == "abstraction"]

    print("=" * 88)
    print("P3-C.2  NLI catches genuine contradictions WITHOUT flagging valid abstraction")
    print("=" * 88)
    print(f"cases: {len(cases)}  (genuine contradictions {len(genuine)}, valid abstractions {len(abstr)})\n")

    rows, summary = [], []
    for model_name, label in NLI_MODELS:
        nli = NLISensor(model_name)
        for c in cases:
            nli_label, _ = nli.predict(c["premise"], c["hypothesis"])
            rule_label = schema.schema_compare(c["premise"], c["hypothesis"]) if c["structured"] else None
            final_with = rule_label if rule_label is not None else nli_label
            final_without = nli_label
            rows.append(dict(claim_id=c["claim_id"], model=label, case_type=c["case_type"],
                             contradiction_type=c["contradiction_type"], framing=c["framing"],
                             nli_label=nli_label, schema_rule_label=(rule_label or "n/a"),
                             final_label=final_with, groundtruth=c["groundtruth"],
                             correct=(final_with == c["groundtruth"] or
                                      (c["case_type"] == "abstraction" and final_with != "contradict"))))
        # metrics with vs without rule
        def metrics(use_rule):
            def fin(c, nl):
                rl = schema.schema_compare(c["premise"], c["hypothesis"]) if (use_rule and c["structured"]) else None
                return rl if rl is not None else nl
            nl = {c["claim_id"]: nli.predict(c["premise"], c["hypothesis"])[0] for c in cases}
            rec = sum(1 for c in genuine if fin(c, nl[c["claim_id"]]) == "contradict") / len(genuine)
            fpr = sum(1 for c in abstr if fin(c, nl[c["claim_id"]]) == "contradict") / len(abstr)
            # cvss-only recall (the case the rule fixes)
            cv = [c for c in genuine if c["contradiction_type"] == "cvss_numeric"]
            cv_rec = sum(1 for c in cv if fin(c, nl[c["claim_id"]]) == "contradict") / len(cv)
            return rec, fpr, cv_rec
        rec_w, fpr_w, cv_w = metrics(True)
        rec_n, fpr_n, cv_n = metrics(False)
        summary.append(dict(model=label, recall_with=rec_w, fpr_with=fpr_w, cvss_recall_with=cv_w,
                            recall_without=rec_n, fpr_without=fpr_n, cvss_recall_without=cv_n))
        print(f"[{label}]")
        print(f"  WITHOUT schema rule: genuine recall {rec_n:.2f}  abstraction FPR {fpr_n:.2f}  "
              f"(CVSS recall {cv_n:.2f})")
        print(f"  WITH    schema rule: genuine recall {rec_w:.2f}  abstraction FPR {fpr_w:.2f}  "
              f"(CVSS recall {cv_w:.2f})\n")

    _write_csv(rows)
    _write_summary(summary)
    _figure(rows, summary, genuine, abstr)
    _verdict(summary)
    return 0


def _write_csv(rows):
    cols = ["claim_id", "model", "case_type", "contradiction_type", "framing",
            "nli_label", "schema_rule_label", "final_label", "groundtruth", "correct"]
    with open(os.path.join(OUT_DIR, "c2_nli.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)


def _write_summary(summary):
    with open(os.path.join(OUT_DIR, "c2_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys())); w.writeheader(); w.writerows(summary)


def _figure(rows, summary, genuine, abstr):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        print(f"(figure skipped: {e})"); return ""
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.4, 5.0))

    # Panel A — per-contradiction-type recall, with vs without rule (mid model)
    mid = summary[-1]["model"]
    types = ["cvss_numeric", "categorical_vendor", "patch_boolean", "version_scope",
             "ransomware_boolean", "patched_unpatched"]
    def type_recall(use_rule_label):
        out = []
        for t in types:
            sub = [r for r in rows if r["model"] == mid and r["case_type"] == "genuine"
                   and r["contradiction_type"] == t]
            if not sub:
                out.append(np.nan); continue
            if use_rule_label:
                hit = sum(1 for r in sub if r["final_label"] == "contradict")
            else:
                hit = sum(1 for r in sub if r["nli_label"] == "contradict")
            out.append(hit / len(sub))
        return out
    x = np.arange(len(types)); w = 0.38
    axA.bar(x - w / 2, type_recall(False), w, color="#bdc3c7", label="NLI only (no schema rule)")
    axA.bar(x + w / 2, type_recall(True), w, color="#2c3e50", label="NLI + schema rule")
    axA.axhline(0.9, color="#c0392b", ls="--", lw=1.2, label="target recall 0.9")
    axA.set_xticks(x); axA.set_xticklabels([t.replace("_", "\n") for t in types], fontsize=7.5)
    axA.set_ylabel("genuine-contradiction recall"); axA.set_ylim(0, 1.08)
    axA.set_title(f"A. Contradiction recall by type ({mid})\nschema rule recovers the CVSS band cases", fontsize=10)
    axA.legend(fontsize=8, frameon=False, loc="lower right")

    # Panel B — recall & abstraction-FPR, with vs without rule, per model
    models = [s["model"].split(" (")[0] for s in summary]
    xb = np.arange(len(models)); bw = 0.2
    axB.bar(xb - 1.5 * bw, [s["recall_without"] for s in summary], bw, color="#95a5a6", label="recall (no rule)")
    axB.bar(xb - 0.5 * bw, [s["recall_with"] for s in summary], bw, color="#2c3e50", label="recall (rule)")
    axB.bar(xb + 0.5 * bw, [s["fpr_without"] for s in summary], bw, color="#e74c3c", label="abstraction FPR (no rule)")
    axB.bar(xb + 1.5 * bw, [s["fpr_with"] for s in summary], bw, color="#e67e22", label="abstraction FPR (rule)")
    axB.axhline(0.9, color="#c0392b", ls="--", lw=1, label="recall target 0.9")
    axB.set_xticks(xb); axB.set_xticklabels(models, fontsize=8)
    axB.set_ylim(0, 1.08); axB.set_ylabel("rate")
    axB.set_title("B. Genuine recall ↑ and abstraction FPR ↓\n(valid abstraction not over-blocked)", fontsize=10)
    axB.legend(fontsize=7.5, frameon=False, ncol=1, loc="center right")

    fig.tight_layout()
    path = os.path.join(FIG_DIR, "c2_nli_contradiction.png")
    fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path


def _verdict(summary):
    print("=" * 88)
    best = max(summary, key=lambda s: s["recall_with"] - s["fpr_with"])
    ok = best["recall_with"] >= 0.9 and best["fpr_with"] <= 0.15
    print(f"best config: {best['model']} — genuine recall {best['recall_with']:.2f}, "
          f"abstraction FPR {best['fpr_with']:.2f}")
    print(f"schema rule lifts CVSS-band recall {best['cvss_recall_without']:.2f} → "
          f"{best['cvss_recall_with']:.2f} (prose-NLI alone scores those neutral)")
    if ok:
        print("PASS — NLI + schema rule catches genuine contradictions (recall ≥ 0.9) WITHOUT "
              "flagging valid abstraction (low FPR): wrong information caught, faithful "
              "abstraction not over-blocked.")
    else:
        print("REVIEW — recall/FPR target not jointly met; inspect per-type breakdown.")
    print("=" * 88)


if __name__ == "__main__":
    raise SystemExit(main())
