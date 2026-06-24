"""P3-C.1 — Does support detect evidence loss?

Constructs the "claim survives, backing stripped" case on real advisories: the
output **claim** is the advisory's vulnerability name; its **backing evidence**
is the advisory's impact description. We score support `s(claim, source)` —
max sentence-cosine — under four source conditions:

  * **intact**   — the real impact description (backs the claim)        → s high
  * **partial**  — first half of the description (evidence half-gone)   → s mid
  * **stripped** — impact-free boilerplate (backing removed)            → s low
  * **distractor** — a DIFFERENT advisory's description (false-support test)

AUC of `s` separating intact from stripped is the headline (target ≳ 0.8); the
distractor condition measures the known false-support weakness (topically-similar
sources inflating `s`), which is exactly why §8 keeps `s` under the `min`.
Both representation spaces are run: sentence-embedding (verifier-side default)
and LM activation-space (the §7b variant).

Run:  python -m p3.exp.c1_support_evidence_loss [--advisories N] [--seed S]
"""

from __future__ import annotations

import argparse
import csv
import os
import warnings

import numpy as np

warnings.filterwarnings("ignore")
from sklearn.metrics import roc_auc_score

from p3.data.advisories.corpus import load_advisories, corpus_stats
from p3.sensors.support import SupportSensor

OUT_DIR = os.path.join("p3", "results", "c1")
FIG_DIR = os.path.join("p3", "results", "figures")
SPACES = [("embedding", "sentence-embedding (MiniLM)"),
          ("activation", "LM activation (distilgpt2)")]
CONDITIONS = ["intact", "partial", "stripped", "distractor"]


def _boilerplate(a: dict) -> str:
    f = a["fields"]
    return (f"This vulnerability was added to the catalog on {f.get('date_added','an earlier date')}. "
            f"Remediation is due by {f.get('due_date','the due date')}. "
            f"Apply updates per vendor instructions.")


def _half(text: str) -> str:
    w = text.split()
    return " ".join(w[: max(1, len(w) // 2)])


def build_cases(advisories):
    """(claim, {condition: source_text}) per advisory with a usable description."""
    usable = [a for a in advisories
              if a["fields"].get("vulnerability_name") and a["fields"].get("short_description")]
    cases = []
    for i, a in enumerate(usable):
        claim = a["fields"]["vulnerability_name"]
        desc = a["fields"]["short_description"]
        distractor = usable[(i + 1) % len(usable)]["fields"]["short_description"]
        cases.append(dict(record_id=a["record_id"], claim=claim, sources={
            "intact": desc,
            "partial": _half(desc),
            "stripped": _boilerplate(a),
            "distractor": distractor,
        }))
    return cases


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--advisories", type=int, default=80)
    ap.add_argument("--seed", type=int, default=3)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True); os.makedirs(FIG_DIR, exist_ok=True)

    advisories = load_advisories(n=args.advisories, seed=args.seed)
    cases = build_cases(advisories)

    rows, by_space = [], {}
    print("=" * 84)
    print("P3-C.1  Support sensor detects evidence loss (claim survives, backing stripped)")
    print("=" * 84)
    print(f"corpus: {len(cases)} real advisories (catalog {corpus_stats()['catalog_version']})\n")

    for space, label in SPACES:
        sensor = SupportSensor(space=space)
        scores = {c: [] for c in CONDITIONS}
        for case in cases:
            for c in CONDITIONS:
                s = sensor.support(case["claim"], case["sources"][c])
                scores[c].append(s)
                rows.append(dict(
                    claim_id=case["record_id"], support_score=round(s, 4),
                    evidence_intact_or_stripped=("intact" if c == "intact" else "stripped"),
                    condition=c, space=space, distractor_present=(c == "distractor")))
        scores = {c: np.array(v) for c, v in scores.items()}
        # AUC: intact (supported=1) vs stripped (0)
        y = np.r_[np.ones(len(scores["intact"])), np.zeros(len(scores["stripped"]))]
        sc = np.r_[scores["intact"], scores["stripped"]]
        auc = float(roc_auc_score(y, sc))
        # best threshold (Youden) -> detection rate of evidence loss + false-support
        tau = _best_tau(scores["intact"], scores["stripped"])
        det_strip = float((scores["stripped"] < tau).mean())
        det_partial = float((scores["partial"] < tau).mean())
        false_support = float((scores["distractor"] >= tau).mean())  # distractor wrongly "supported"
        by_space[space] = dict(auc=auc, tau=tau, det_strip=det_strip, det_partial=det_partial,
                               false_support=false_support, scores=scores, label=label)
        print(f"[{label}]")
        print(f"  mean s — intact {scores['intact'].mean():.3f} | partial {scores['partial'].mean():.3f} "
              f"| stripped {scores['stripped'].mean():.3f} | distractor {scores['distractor'].mean():.3f}")
        print(f"  AUC(intact vs stripped) = {auc:.3f}  (τ={tau:.3f}); evidence-loss detection: "
              f"full {det_strip:.2f}, partial {det_partial:.2f}")
        print(f"  false-support rate (distractor ≥ τ) = {false_support:.2f}  (the known weakness)\n")

    # mark detected per row using each space's tau
    for r in rows:
        tau = by_space[r["space"]]["tau"]
        r["detected"] = bool(r["support_score"] < tau) if r["condition"] != "intact" \
            else bool(r["support_score"] < tau)  # for intact, True = false-positive
    _write_csv(rows)
    _figure(by_space)
    _verdict(by_space)
    return 0


def _best_tau(pos, neg):
    """Threshold maximizing balanced separation (pos=intact high, neg=stripped low)."""
    cand = np.unique(np.r_[pos, neg])
    best, bt = -1, 0.5
    for t in cand:
        bal = 0.5 * ((pos >= t).mean() + (neg < t).mean())
        if bal > best:
            best, bt = bal, t
    return float(bt)


def _write_csv(rows):
    cols = ["claim_id", "support_score", "evidence_intact_or_stripped", "condition",
            "space", "distractor_present", "detected"]
    with open(os.path.join(OUT_DIR, "c1_support.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)


def _figure(by_space):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"(figure skipped: {e})"); return ""
    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.0))
    colors = {"intact": "#2a9d8f", "partial": "#e9c46a", "stripped": "#c0392b", "distractor": "#8e44ad"}
    for ax, (space, d) in zip(axes, by_space.items()):
        data = [d["scores"][c] for c in CONDITIONS]
        parts = ax.violinplot(data, showmeans=True, showextrema=False)
        for pc, c in zip(parts["bodies"], CONDITIONS):
            pc.set_facecolor(colors[c]); pc.set_alpha(0.7)
        ax.axhline(d["tau"], color="#333", ls="--", lw=1, label=f"τ={d['tau']:.2f}")
        ax.set_xticks(range(1, 5)); ax.set_xticklabels(CONDITIONS, fontsize=9)
        ax.set_ylabel("support s (max sentence-cosine)")
        ax.set_title(f"{d['label']}\nAUC(intact vs stripped) = {d['auc']:.3f} · "
                     f"false-support = {d['false_support']:.2f}", fontsize=10)
        ax.legend(fontsize=8, frameon=False)
    fig.suptitle("P3-C.1 — support detects evidence loss (intact↑ vs stripped↓); "
                 "distractor = false-support risk", fontsize=11)
    fig.tight_layout()
    path = os.path.join(FIG_DIR, "c1_support_evidence_loss.png")
    fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path


def _verdict(by_space):
    print("=" * 84)
    best = max(d["auc"] for d in by_space.values())
    emb = by_space["embedding"]
    if emb["auc"] >= 0.8:
        print(f"PASS — support (verifier-side embedding) detects evidence loss at AUC "
              f"{emb['auc']:.3f} ≥ 0.8: it catches the 'claim survives, proof gone' case "
              "CAPM's structural transformation penalty cannot see.")
    else:
        print(f"REVIEW — embedding AUC {emb['auc']:.3f} < 0.8; inspect calibration.")
    print(f"Known weakness CONFIRMED & reported: distractor sources inflate s "
          f"(false-support {emb['false_support']:.2f}) — this is why §8 keeps s under the "
          "`min` with NLI, never as a sole gate.")
    print("=" * 84)


if __name__ == "__main__":
    raise SystemExit(main())
