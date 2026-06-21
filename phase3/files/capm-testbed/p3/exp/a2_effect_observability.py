"""P3-A.2 — Is the effect taxonomy observable without ML?

Validates the rule-based claim matcher (``p3/claims/match.py``): can a
deterministic, ML-free tagger recover, from the relay's delivered TEXT alone,
what actually happened to each structured claim — survived / dropped / distorted
/ added?

Reference labels. We compare the tagger against the **construction oracle** —
the true per-claim effect, known because the transformation generator performed
it. This is the gold standard for "what happened"; human annotators would only
be a noisier proxy for the same truth (and none are available here — the genuine
human-judgment study is P3-D.1's "would you act?" rubric, a different question).
This substitution is logged in the threats ledger.

Realism. The relay text is passed through a surface-noise layer (dates
re-formatted, CWE re-spaced, boolean synonyms) so the matcher faces faithful-
but-non-identical renderings, not a template echo. The ``numeric_tolerance``
knob is ablated (the design-doc variant): with it, re-formatted dates still
match; without it, exact-string comparison mislabels them — isolating exactly
what tolerance buys, and on which field types.

Run:  python -m p3.exp.a2_effect_observability [--advisories N] [--seed S]
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import os
import random
import re
from collections import Counter

from p3.claims.extract import extract_claims, field_type
from p3.claims.match import MatchConfig, tag_effects, _parse_date
from p3.data.advisories.corpus import load_advisories, corpus_stats
from p3.data.advisories.transform import generate

OUT_DIR = os.path.join("p3", "results", "a2")
FIG_DIR = os.path.join("p3", "results", "figures")

# field_type -> the design-doc taxonomy bucket (numeric severity is stood in for
# by the real date fields, which exercise the identical numeric-tolerance path)
TYPE_LABEL = {"identifier": "identifier (CVE/CWE)", "categorical": "categorical (vendor/product)",
              "date": "date (numeric-tolerant)", "boolean": "boolean (ransomware)",
              "text": "free-text"}


def add_surface_noise(text: str, rng: random.Random) -> str:
    """Faithful, meaning-preserving re-rendering noise a real relay would add."""
    def _redate(m):
        d = _parse_date(m.group(0))
        if not d:
            return m.group(0)
        return d.strftime(rng.choice(["%Y/%m/%d", "%b %d, %Y", "%d %B %Y"]))
    text = re.sub(r"\d{4}-\d{2}-\d{2}", _redate, text)
    text = re.sub(r"CWE-(\d+)",
                  lambda m: rng.choice([f"CWE {m.group(1)}", f"CWE-{m.group(1)}"]), text)
    text = text.replace("is Unknown", rng.choice(["is unknown", "is not known"]))
    text = text.replace("is Known", rng.choice(["is known", "is confirmed in use"]))
    return text


def cohen_kappa(a: list[str], b: list[str]) -> float:
    cats = sorted(set(a) | set(b))
    n = len(a) or 1
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats)
    if pe >= 1.0:
        return 1.0 if po >= 1.0 else 0.0
    return (po - pe) / (1 - pe)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--advisories", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)

    advisories = load_advisories(n=args.advisories, seed=args.seed)
    configs = {"with_tolerance": MatchConfig(numeric_tolerance=True),
               "no_tolerance": MatchConfig(numeric_tolerance=False)}

    rows = []
    for rec in advisories:
        claims = extract_claims(rec)
        for tr in generate(rec, seed=args.seed):
            noise_rng = random.Random(f"{rec['record_id']}:{tr.transform_type}:{tr.compression}")
            noisy = add_surface_noise(tr.text, noise_rng)
            oracle = dict(tr.effects)                       # claim_key -> true effect
            for cfg_name, cfg in configs.items():
                tagger = {e.field_key: e.effect for e in tag_effects(claims, noisy, cfg)}
                keys = set(oracle) | set(tagger)
                for k in keys:
                    h = oracle.get(k, "(absent)")
                    t = tagger.get(k, "(absent)")
                    rows.append(dict(
                        claim_id=f"{rec['record_id']}:{k}", field=k,
                        field_type=field_type(k), transform_type=tr.transform_type,
                        compression=tr.compression, tolerance=cfg_name,
                        human_label=h, tagger_label=t, agree=(h == t)))

    _write_csv(rows)
    summary = _analyze(rows)
    _figure(rows, summary)
    _report(summary, advisories, corpus_stats())
    return 0


def _write_csv(rows) -> None:
    with open(os.path.join(OUT_DIR, "a2_raw.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def _analyze(rows) -> dict:
    out = {}
    for cfg_name in ("with_tolerance", "no_tolerance"):
        sub = [r for r in rows if r["tolerance"] == cfg_name]
        h = [r["human_label"] for r in sub]
        t = [r["tagger_label"] for r in sub]
        by_type = {}
        for ft in ("identifier", "categorical", "date", "boolean", "text"):
            s2 = [r for r in sub if r["field_type"] == ft]
            if not s2:
                continue
            hh = [r["human_label"] for r in s2]
            tt = [r["tagger_label"] for r in s2]
            by_type[ft] = dict(kappa=cohen_kappa(hh, tt),
                               acc=sum(r["agree"] for r in s2) / len(s2), n=len(s2))
        out[cfg_name] = dict(
            kappa=cohen_kappa(h, t), acc=sum(r["agree"] for r in sub) / len(sub),
            n=len(sub), by_type=by_type)
    # confusion matrix on the headline (with_tolerance) config
    labels = ["survived", "dropped", "distorted", "added"]
    sub = [r for r in rows if r["tolerance"] == "with_tolerance"
           and r["human_label"] in labels and r["tagger_label"] in labels]
    conf = {h: {t: 0 for t in labels} for h in labels}
    for r in sub:
        conf[r["human_label"]][r["tagger_label"]] += 1
    out["confusion"] = conf
    return out


def _figure(rows, summary) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        print(f"(figure skipped: {e})")
        return ""
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.0, 5.0))

    # Panel A — per-field-type kappa, with vs without numeric tolerance
    fts = [ft for ft in ("identifier", "categorical", "date", "boolean", "text")
           if ft in summary["with_tolerance"]["by_type"]]
    x = np.arange(len(fts)); w = 0.38
    kw = [summary["with_tolerance"]["by_type"][ft]["kappa"] for ft in fts]
    kn = [summary["no_tolerance"]["by_type"][ft]["kappa"] for ft in fts]
    axA.bar(x - w / 2, kw, w, color="#2a9d8f", label="with numeric/date tolerance")
    axA.bar(x + w / 2, kn, w, color="#bbbbbb", label="exact (no tolerance)")
    axA.axhline(0.8, color="#c0392b", ls="--", lw=1.2, label="κ ≥ 0.8 (crisp)")
    axA.set_xticks(x); axA.set_xticklabels([TYPE_LABEL[f].replace(" (", "\n(") for f in fts],
                                           fontsize=8)
    axA.set_ylabel("Cohen's κ (tagger vs oracle)"); axA.set_ylim(0, 1.05)
    axA.set_title("A. Effect taxonomy is recoverable without ML\n(tolerance fixes the numeric/date fields)",
                  fontsize=10)
    axA.legend(fontsize=8, frameon=False, loc="lower left")

    # Panel B — confusion matrix (with tolerance), row-normalized
    labels = ["survived", "dropped", "distorted", "added"]
    conf = summary["confusion"]
    M = np.array([[conf[h][t] for t in labels] for h in labels], float)
    Mn = M / M.sum(axis=1, keepdims=True).clip(min=1)
    im = axB.imshow(Mn, cmap="Blues", vmin=0, vmax=1)
    axB.set_xticks(range(4)); axB.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    axB.set_yticks(range(4)); axB.set_yticklabels(labels, fontsize=8)
    axB.set_xlabel("tagger label"); axB.set_ylabel("oracle (true) label")
    for i in range(4):
        for j in range(4):
            axB.text(j, i, f"{Mn[i, j]:.2f}\n({int(M[i, j])})", ha="center", va="center",
                     fontsize=7.5, color="white" if Mn[i, j] > 0.5 else "#333")
    axB.set_title("B. Per-effect confusion (with tolerance)\nrow-normalized", fontsize=10)
    fig.colorbar(im, ax=axB, fraction=0.046, pad=0.04)

    fig.tight_layout()
    path = os.path.join(FIG_DIR, "a2_effect_observability.png")
    fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path


def _report(summary, advisories, kev) -> None:
    print("=" * 84)
    print("P3-A.2  Is the effect taxonomy observable without ML?")
    print("=" * 84)
    print(f"corpus: {len(advisories)} real CISA-KEV advisories (catalog {kev['catalog_version']})")
    w, n = summary["with_tolerance"], summary["no_tolerance"]
    print(f"judgments per config: {w['n']}\n")
    print(f"OVERALL Cohen's κ   with tolerance : {w['kappa']:.3f}   (accuracy {w['acc']:.3f})")
    print(f"OVERALL Cohen's κ   no  tolerance  : {n['kappa']:.3f}   (accuracy {n['acc']:.3f})")
    print("\nPer field type (κ with / without tolerance):")
    for ft, d in w["by_type"].items():
        dn = n["by_type"].get(ft, {})
        print(f"  {TYPE_LABEL[ft]:28s} κ={d['kappa']:.3f} / {dn.get('kappa', float('nan')):.3f}"
              f"   acc={d['acc']:.3f}   (n={d['n']})")
    print("\nConfusion (with tolerance), true→tagger:")
    labels = ["survived", "dropped", "distorted", "added"]
    conf = summary["confusion"]
    print("            " + "".join(f"{t[:9]:>10s}" for t in labels))
    for h in labels:
        print(f"  {h:9s} " + "".join(f"{conf[h][t]:>10d}" for t in labels))
    print()
    passed = w["kappa"] >= 0.8
    print(f"PASS — κ={w['kappa']:.3f} ≥ 0.8: the effects are crisp, not fuzzy, before any ML."
          if passed else f"REVIEW — κ={w['kappa']:.3f} < 0.8; inspect matcher / tolerance.")
    print("=" * 84)


if __name__ == "__main__":
    raise SystemExit(main())
