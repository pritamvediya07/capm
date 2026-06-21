"""P3-B.1 — Does the usage probe transfer to our relay models?

For each open-weight relay model we test whether a logistic-regression probe on
the answer-token hidden states separates context-driven (grounded) from
parametric (ungrounded) generation, and whether it BEATS two text-only controls
— so the signal is representational, not a surface lexical cue:

  * **probe**        — LR on the final- (and middle-) layer hidden vector of the
                       answer tokens;
  * **control_bow**  — LR on TF-IDF of the *full prompt* (the strongest lexical
                       shortcut: it can see answer-in-context overlap);
  * **control_static** — LR on the *layer-0* (pre-contextual) embedding of the
                       same answer tokens (isolates what contextualization adds).

Splits are advisory-disjoint (the "title-disjoint" rule — no record in both
train and test). Also measured: a layer sweep (middle vs final), cross-model
transfer (train on A, test on B — expected to fail, motivating per-model
retraining), and out-of-domain transfer to general-knowledge facts.

MODEL SUBSTITUTION (honest): the design doc names Llama-3.1-8B / Mistral-7B /
Qwen2.5-7B; those do not fit this CPU box. We substitute small open-weight LMs
across three architectures — distilgpt2, gpt2 (GPT-2), pythia-160m (GPT-NeoX),
opt-125m (OPT) — which exercise the *same* scientific claim at a scale this
hardware supports. The 7-8B validation is GPU future-work; the security
guarantee (probe under the min-clamp) is independent of probe quality.

Run:  python -m p3.exp.b1_probe_transfer [--advisories N] [--seed S]
"""

from __future__ import annotations

import argparse
import csv
import os
import warnings

import numpy as np

warnings.filterwarnings("ignore")

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score

from p3.sensors.probe import HiddenStateExtractor, UsageProbe
from p3.sensors.probe_data import build_usage_examples, build_ood_examples

MODELS = ["distilgpt2", "gpt2", "EleutherAI/pythia-160m", "facebook/opt-125m"]
OUT_DIR = os.path.join("p3", "results", "b1")
FIG_DIR = os.path.join("p3", "results", "figures")


def _short(name: str) -> str:
    return name.split("/")[-1]


def extract_all(model_name: str, examples, ood, cache: str):
    """Extract {static,middle,final} answer-span features for all examples (cached)."""
    if os.path.exists(cache):
        d = np.load(cache, allow_pickle=True)
        return {k: d[k] for k in d.files}
    ext = HiddenStateExtractor(model_name)
    loi = ext.layers_of_interest()
    Ls = (loi["static"], loi["middle"], loi["final"])
    def feats(exs):
        S, M, F = [], [], []
        for e in exs:
            f = ext.features(e.prompt(), e.answer_text(), Ls)
            S.append(f[Ls[0]]); M.append(f[Ls[1]]); F.append(f[Ls[2]])
        return np.array(S), np.array(M), np.array(F)
    S, M, F = feats(examples)
    So, Mo, Fo = feats(ood)
    out = dict(static=S, middle=M, final=F, ood_static=So, ood_middle=Mo, ood_final=Fo,
               middle_layer=loi["middle"], final_layer=loi["final"])
    np.savez(cache, **out)
    return out


def macro_f1(y_true, y_pred) -> float:
    return float(f1_score(y_true, y_pred, average="macro"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--advisories", type=int, default=80)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)

    ex = build_usage_examples(n_advisories=args.advisories, seed=args.seed)
    ood = build_ood_examples(seed=args.seed)
    y = np.array([e.label for e in ex])
    yood = np.array([e.label for e in ood])
    rids = np.array([e.record_id for e in ex])
    # the lexical control sees the FULL sequence the model saw (prompt + answer),
    # so it CAN exploit answer-in-context lexical overlap — a fair, non-strawman
    # shortcut baseline, not a crippled one.
    prompts = [e.prompt() + e.answer_text() for e in ex]

    # advisory-disjoint split (title-disjoint analog)
    uniq = sorted(set(rids))
    rng = np.random.RandomState(args.seed)
    rng.shuffle(uniq)
    n_tr = int(0.7 * len(uniq))
    train_ids = set(uniq[:n_tr])
    tr = np.array([r in train_ids for r in rids])
    te = ~tr
    chance = macro_f1(y[te], np.zeros(te.sum(), dtype=int)) if te.sum() else 0.0

    # text-only BoW control (model-independent): TF-IDF over full prompt
    vec = TfidfVectorizer(max_features=4000, ngram_range=(1, 2))
    Xb_tr = vec.fit_transform([p for p, m in zip(prompts, tr) if m])
    Xb_te = vec.transform([p for p, m in zip(prompts, te) if m])
    bow = LogisticRegression(class_weight="balanced", max_iter=2000).fit(Xb_tr, y[tr])
    bow_f1 = macro_f1(y[te], bow.predict(Xb_te))

    # explicit answer-in-context overlap ORACLE (transparency control): on
    # structured data, grounding is ~defined by whether the answer string is in
    # the context, so this hand-crafted lexical feature is near-perfect. Reporting
    # it stops us overclaiming the probe is uniquely necessary HERE — its
    # representational advantage is for NON-lexical grounding (paraphrase/implicit),
    # which structured sources do not stress (that is the prose-extension frontier).
    overlap = np.array([[1.0 if e.answer.lower() in e.context.lower() else 0.0] for e in ex])
    ov = LogisticRegression(class_weight="balanced", max_iter=200).fit(overlap[tr], y[tr])
    overlap_f1 = macro_f1(y[te], ov.predict(overlap[te]))

    rows, feats_by_model = [], {}
    print("=" * 86)
    print("P3-B.1  Usage-probe transfer (context-driven vs parametric) — per model")
    print("=" * 86)
    print(f"examples: {len(ex)} (train {tr.sum()}, test {te.sum()}); label balance "
          f"{int((y==1).sum())}:+ / {int((y==0).sum())}:-  ; chance macro-F1={chance:.3f}")
    print(f"text-only BoW control (full prompt TF-IDF) macro-F1 = {bow_f1:.3f}")
    print(f"explicit answer-in-context overlap ORACLE  macro-F1 = {overlap_f1:.3f}  "
          f"(near-perfect by construction on structured data — see note)\n")
    print(f"{'model':22s} {'arch':9s} {'probe(final)':>12s} {'probe(mid)':>11s} "
          f"{'static':>8s} {'bow':>7s} {'best layer':>11s} {'OOD':>6s}")
    print("-" * 86)

    ARCH = {"distilgpt2": "GPT-2", "gpt2": "GPT-2",
            "EleutherAI/pythia-160m": "NeoX", "facebook/opt-125m": "OPT"}
    for mname in MODELS:
        cache = os.path.join(OUT_DIR, f"feat_{_short(mname)}.npz")
        fe = extract_all(mname, ex, ood, cache)
        feats_by_model[mname] = fe
        # probe at final + middle, static control, all on the same split
        def fit_eval(Xkey):
            X = fe[Xkey]
            p = UsageProbe().fit(X[tr], y[tr])
            return macro_f1(y[te], p.predict(X[te])), p
        f_final, probe_final = fit_eval("final")
        f_mid, _ = fit_eval("middle")
        f_static, _ = fit_eval("static")
        best_layer = "final" if f_final >= f_mid else "middle"
        # OOD transfer: probe trained on CVE (final layer), applied to OOD facts
        ood_f1 = macro_f1(yood, probe_final.predict(fe["ood_final"]))
        rows.append(dict(model=_short(mname), arch=ARCH[mname],
                         probe_final_f1=round(f_final, 4), probe_mid_f1=round(f_mid, 4),
                         control_bow_f1=round(bow_f1, 4), control_static_f1=round(f_static, 4),
                         overlap_oracle_f1=round(overlap_f1, 4),
                         best_layer=best_layer, final_layer=int(fe["final_layer"]),
                         middle_layer=int(fe["middle_layer"]),
                         gap_over_bow=round(f_final - bow_f1, 4),
                         gap_over_static=round(f_final - f_static, 4),
                         ood_f1=round(ood_f1, 4)))
        print(f"{_short(mname):22s} {ARCH[mname]:9s} {f_final:12.3f} {f_mid:11.3f} "
              f"{f_static:8.3f} {bow_f1:7.3f} {best_layer:>11s} {ood_f1:6.3f}")

    # cross-model transfer (final layer): train on A, test on B (same test rows)
    print("\nCross-model transfer (final-layer probe, macro-F1 on test split):")
    names = [_short(m) for m in MODELS]
    print("  train↓ / test→   " + "".join(f"{n[:10]:>11s}" for n in names))
    transfer = {}
    for a in MODELS:
        Xa = feats_by_model[a]["final"]
        pa = UsageProbe().fit(Xa[tr], y[tr])
        line = []
        for b in MODELS:
            Xb = feats_by_model[b]["final"]
            f = macro_f1(y[te], pa.predict(Xb[te]))
            transfer[(_short(a), _short(b))] = f
            line.append(f)
        print(f"  {_short(a):14s}   " + "".join(f"{v:11.3f}" for v in line))

    _write_csv(rows)
    _figure(rows, transfer, names, chance, overlap_f1)
    _verdict(rows, chance)
    return 0


def _write_csv(rows) -> None:
    with open(os.path.join(OUT_DIR, "b1_results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)


def _figure(rows, transfer, names, chance, overlap_f1) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"(figure skipped: {e})")
        return ""
    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.4, 5.0))

    models = [r["model"] for r in rows]
    x = np.arange(len(models)); w = 0.24
    axA.bar(x - 1.5 * w, [r["probe_final_f1"] for r in rows], w, color="#2c3e50", label="probe (final layer)")
    axA.bar(x - 0.5 * w, [r["probe_mid_f1"] for r in rows], w, color="#7f8c8d", label="probe (middle layer)")
    axA.bar(x + 0.5 * w, [r["control_bow_f1"] for r in rows], w, color="#e67e22", label="control: BoW (full prompt)")
    axA.bar(x + 1.5 * w, [r["control_static_f1"] for r in rows], w, color="#bdc3c7", label="control: static emb")
    axA.axhline(overlap_f1, color="#16a085", ls="--", lw=1.3,
                label=f"explicit overlap oracle ({overlap_f1:.2f})")
    axA.axhline(chance, color="#c0392b", ls=":", lw=1.2, label=f"chance ({chance:.2f})")
    axA.set_xticks(x); axA.set_xticklabels([f"{r['model']}\n({r['arch']})" for r in rows], fontsize=8)
    axA.set_ylabel("usage macro-F1 (context-driven vs parametric)"); axA.set_ylim(0, 1.05)
    axA.set_title("A. Hidden-state probe vs text-only controls, per relay model", fontsize=10)
    axA.legend(fontsize=7.5, frameon=False, ncol=1, loc="lower right")

    M = np.array([[transfer[(a, b)] for b in names] for a in names])
    im = axB.imshow(M, cmap="viridis", vmin=chance, vmax=1.0)
    axB.set_xticks(range(len(names))); axB.set_xticklabels(names, rotation=30, ha="right", fontsize=8)
    axB.set_yticks(range(len(names))); axB.set_yticklabels(names, fontsize=8)
    axB.set_xlabel("tested on →"); axB.set_ylabel("trained on ↓")
    for i in range(len(names)):
        for j in range(len(names)):
            axB.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=8,
                     color="white" if M[i, j] < (chance + 1) / 2 else "black")
    axB.set_title("B. Cross-model transfer fails → retrain per model\n(diagonal = in-model)", fontsize=10)
    fig.colorbar(im, ax=axB, fraction=0.046, pad=0.04)

    fig.tight_layout()
    path = os.path.join(FIG_DIR, "b1_probe_transfer.png")
    fig.savefig(path, dpi=140, bbox_inches="tight"); plt.close(fig)
    return path


def _verdict(rows, chance) -> None:
    best = max(r["probe_final_f1"] for r in rows)
    gaps_bow = [r["gap_over_bow"] for r in rows]
    gaps_static = [r["gap_over_static"] for r in rows]
    print("\n" + "=" * 86)
    print(f"best probe macro-F1 = {best:.3f}; mean gap over BoW = {np.mean(gaps_bow):+.3f}; "
          f"mean gap over static = {np.mean(gaps_static):+.3f}")
    strong = best >= 0.85 and np.mean(gaps_static) > 0.1
    repr_signal = np.mean(gaps_static) > 0.1
    ov = rows[0]["overlap_oracle_f1"]
    if strong and np.mean(gaps_bow) > 0.05:
        print("PASS — probe is high-F1 AND beats both generic text-only controls: the usage "
              "signal is representational (contextualization), not a generic lexical statistic.")
        print(f"HONEST CAVEAT — an explicit answer-in-context overlap oracle scores "
              f"{ov:.3f} (near-perfect): on STRUCTURED data grounding is also lexically "
              "separable, so the probe's UNIQUE value (non-lexical/implicit grounding) is not "
              "stressed here — it is positioned as the runtime-internal usage sensor that "
              "complements verifier-side support+NLI; its prose advantage is future work.")
    elif repr_signal:
        print("PARTIAL/HONEST — probe clearly beats the static (pre-contextual) control "
              "(signal is representational), but the gap over the lexical BoW control is "
              "small: on STRUCTURED data grounding is partly lexically observable (cf. A.2), "
              "so usage is best used ALONGSIDE support+NLI, not as a sole sensor.")
    else:
        print("NEGATIVE (reportable) — probe ≈ text-only controls: the signal is lexical, "
              "not representational. Per the playbook, demote usage to auxiliary and rely on "
              "support+NLI as the primary (fully verifier-side) sensors.")
    print("=" * 86)


if __name__ == "__main__":
    raise SystemExit(main())
