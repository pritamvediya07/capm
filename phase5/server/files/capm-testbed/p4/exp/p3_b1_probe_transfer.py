"""P4-3.B1 — usage-probe transfer on Qwen2.5 (WS3 scale run).

Re-runs Phase-3 B.1 on a production-scale model via the white-box transformers
wrapper (the ONLY valid path — vLLM/Ollama expose no hidden states). Trains a
logistic probe on answer-token hidden states (context-driven vs parametric),
compares to two text-only controls (BoW full-prompt TF-IDF, static layer-0
embedding), sweeps layers, and — if a second size's features are cached — reports
cross-size transfer (expected to fail -> per-model retrain).

Spec recorded: dtype, layers stored {static,middle,final}, pooling=mean, quant.
Run:  python -m p4.exp.p3_b1_probe_transfer --model Qwen/Qwen2.5-7B-Instruct --dtype bf16
"""
from __future__ import annotations
import argparse, csv, os, time
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score

from p4.models.whitebox import WhiteBoxLM
from p3.sensors.probe import UsageProbe
from p3.sensors.probe_data import build_usage_examples, build_ood_examples

OUT = os.path.join("p4", "results", "ws3", "b1")
mf1 = lambda yt, yp: float(f1_score(yt, yp, average="macro"))
_tag = lambda m, d: f"{m.split('/')[-1]}_{d}"
# Phase-3 gpt2-family reference (delta target)
P3 = dict(probe_final=0.99, static_gap=0.46, bow=0.257)


def extract(wb, examples, ood, cache):
    if os.path.exists(cache):
        d = np.load(cache, allow_pickle=True)
        return {k: d[k] for k in d.files}
    loi = wb.layers_of_interest(); Ls = (loi["static"], loi["middle"], loi["final"])
    def feats(exs):
        S, M, F = [], [], []
        for e in exs:
            f = wb.features(e.prompt(), e.answer_text(), Ls)
            S.append(f[Ls[0]]); M.append(f[Ls[1]]); F.append(f[Ls[2]])
        return np.array(S), np.array(M), np.array(F)
    S, M, F = feats(examples); So, Mo, Fo = feats(ood)
    out = dict(static=S, middle=M, final=F, ood_static=So, ood_middle=Mo, ood_final=Fo,
               middle_layer=loi["middle"], final_layer=loi["final"])
    np.savez(cache, **out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--dtype", default="bf16")
    ap.add_argument("--advisories", type=int, default=80)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    ex = build_usage_examples(n_advisories=args.advisories, seed=args.seed)
    ood = build_ood_examples(seed=args.seed)
    y = np.array([e.label for e in ex]); yood = np.array([e.label for e in ood])
    rids = np.array([e.record_id for e in ex])
    uniq = sorted(set(rids)); rng = np.random.RandomState(args.seed); rng.shuffle(uniq)
    tr_ids = set(uniq[:int(0.7 * len(uniq))])
    tr = np.array([r in tr_ids for r in rids]); te = ~tr
    chance = mf1(y[te], np.zeros(te.sum(), dtype=int))

    print("=" * 90)
    print(f"P4-3.B1  usage-probe transfer — {args.model}  [dtype={args.dtype}, pooling=mean, layers=static/mid/final]")
    print("=" * 90)
    t = time.time()
    wb = WhiteBoxLM(args.model, dtype=args.dtype)
    print(f"loaded in {time.time()-t:.0f}s | layers={wb.n_layers} hidden={wb.hidden} | VRAM {wb.vram_gb():.1f} GB")
    fe = extract(wb, ex, ood, os.path.join(OUT, f"feat_{_tag(args.model, args.dtype)}.npz"))

    # text-only controls
    prompts = [e.prompt() + e.answer_text() for e in ex]
    vec = TfidfVectorizer(max_features=4000, ngram_range=(1, 2))
    Xb_tr = vec.fit_transform([p for p, m in zip(prompts, tr) if m])
    bow_f1 = mf1(y[te], LogisticRegression(class_weight="balanced", max_iter=2000)
                 .fit(Xb_tr, y[tr]).predict(vec.transform([p for p, m in zip(prompts, te) if m])))
    overlap = np.array([[1.0 if e.answer.lower() in e.context.lower() else 0.0] for e in ex])
    ov_f1 = mf1(y[te], LogisticRegression(class_weight="balanced", max_iter=200)
                .fit(overlap[tr], y[tr]).predict(overlap[te]))

    def fit_eval(key):
        return mf1(y[te], UsageProbe().fit(fe[key][tr], y[tr]).predict(fe[key][te]))
    f_final, f_mid, f_static = fit_eval("final"), fit_eval("middle"), fit_eval("static")
    probe_final = UsageProbe().fit(fe["final"][tr], y[tr])
    ood_f1 = mf1(yood, probe_final.predict(fe["ood_final"]))

    print(f"examples {len(ex)} (train {tr.sum()}, test {te.sum()}); chance macro-F1={chance:.3f}")
    print(f"  probe(final L{int(fe['final_layer'])})={f_final:.3f}  probe(mid L{int(fe['middle_layer'])})={f_mid:.3f}  "
          f"static(L0)={f_static:.3f}  BoW={bow_f1:.3f}  overlap-oracle={ov_f1:.3f}  OOD={ood_f1:.3f}")
    print(f"  gap over static = +{f_final-f_static:.3f}  gap over BoW = +{f_final-bow_f1:.3f}")
    print(f"  DELTA vs Phase-3 gpt2: probe {f_final-P3['probe_final']:+.3f}, static-gap "
          f"{(f_final-f_static)-P3['static_gap']:+.3f}")

    # cross-size transfer (if the other size's features are cached)
    cross = {}
    for other in os.listdir(OUT):
        if other.startswith("feat_") and other.endswith(".npz") and _tag(args.model, args.dtype) not in other:
            od = np.load(os.path.join(OUT, other), allow_pickle=True)
            if od["final"].shape[0] == fe["final"].shape[0] and od["final"].shape[1] == fe["final"].shape[1]:
                f = mf1(y[te], probe_final.predict(od["final"][te]))
                cross[other.replace("feat_", "").replace(".npz", "")] = round(f, 4)
    if cross:
        print(f"  CROSS-SIZE transfer (train {_tag(args.model,args.dtype)}, test other): {cross}  "
              "(≈chance ⇒ per-model retrain)")

    rows = [dict(model=args.model.split("/")[-1], dtype=args.dtype, pooling="mean",
                 probe_final_f1=round(f_final, 4), probe_mid_f1=round(f_mid, 4),
                 static_f1=round(f_static, 4), bow_f1=round(bow_f1, 4), overlap_oracle_f1=round(ov_f1, 4),
                 gap_vs_static=round(f_final - f_static, 4), gap_vs_bow=round(f_final - bow_f1, 4),
                 ood_f1=round(ood_f1, 4), cross_size=str(cross), chance=round(chance, 4))]
    with open(os.path.join(OUT, f"b1_{_tag(args.model, args.dtype)}.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    ok = f_final >= 0.85 and (f_final - f_static) > 0.1
    print("=" * 90)
    print(f"{'PASS' if ok else 'WEAK'} — usage signal is {'representational' if ok else 'lexical/weak'} at "
          f"{args.model.split('/')[-1]} scale; gap over static {f_final-f_static:+.3f}. CAVEAT: overlap-oracle "
          f"{ov_f1:.2f} (structured grounding is lexically separable — probe's unique value is prose/future-work).")
    print("=" * 90)


if __name__ == "__main__":
    main()
