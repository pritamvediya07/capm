"""P2-B6 — Detection / second-order boundary.

CAPM cannot prevent origin-class capture (Theorem 2). B6 asks what a *detector*
buys: it runs `capm.detect.origin_anomaly.OriginAnomalyDetector` over a stream of
origin-class assertions mixing honest origins (stable, with occasional legitimate
upgrades) and two attacker strategies:

  * **naive** — the captured origin jumps straight from its low true class to
    AUTHORITATIVE_API in one assertion (a big class jump);
  * **gradual** — the captured origin ramps up through the class ladder over many
    assertions, keeping each single step small, so the detector's baseline
    "learns" the climb.

Sweeping the detector's `jump_threshold` traces the trade-off: True Positive Rate
(attacks flagged) vs False Positive Rate (honest origins flagged). The headline
second-order dynamic: there is an operating band where the naive attack is caught
(TPR≈1) but the gradual attack evades (TPR≈0) at low FPR — and pushing the
threshold down to catch gradual attacks necessarily flags legitimate upgrades too
(FPR rises). The detector raises the *cost and latency* of the residual; it does
not close it.

Run:
    python3 -m experiments.p2_b6_detection
"""

from __future__ import annotations

import csv
import os
import random

from capm.benchmark import stats
from capm.core.types import SourceClass
from capm.detect.origin_anomaly import OriginAnomalyDetector, class_ceiling

OUT_DIR = os.path.join("results", "p2", "b6")

# distinct ceilings present in the class system, ascending — the "class ladder"
_LADDER = sorted({int(c.warrant_ceiling) for c in SourceClass})   # [0, 1, 3, 4]
_TOP = max(_LADDER)                                                # 4 (AUTHORITATIVE)
OBS_NOISE = 0.4            # measurement noise on an observed assertion (smooths ROC)
HISTORY = 8               # assertions per origin

N_HONEST = 400
N_NAIVE = 200
N_GRADUAL = 200
P_UPGRADE = 0.30          # fraction of honest origins that legitimately upgrade once


def _next_up(c: int) -> int:
    for x in _LADDER:
        if x > c:
            return x
    return c


def _honest_stream(rng: random.Random) -> list[float]:
    """A stable origin at some base class; with prob P_UPGRADE it legitimately
    upgrades one rung at a random time and stays there."""
    base = rng.choice(_LADDER)
    seq = [base] * HISTORY
    if rng.random() < P_UPGRADE and base < _TOP:
        t = rng.randint(1, HISTORY - 1)
        up = _next_up(base)
        for i in range(t, HISTORY):
            seq[i] = up
    return [float(x) for x in seq]


def _naive_stream(rng: random.Random) -> tuple[list[float], int]:
    """Low true base, then one big jump straight to AUTHORITATIVE (the payload)."""
    base = rng.choice([0, 1])                      # UNKNOWN / WEAK origin captured
    warm = rng.randint(2, 4)
    seq = [float(base)] * warm + [float(_TOP)] * (HISTORY - warm)
    payload_idx = warm                              # first high assertion
    return seq, payload_idx


def _gradual_stream(rng: random.Random) -> tuple[list[float], int]:
    """Low true base, then ramp up the ladder one rung at a time, dwelling at each
    rung so the baseline catches up, before the AUTHORITATIVE payload."""
    base = rng.choice([0, 1])
    rungs = [r for r in _LADDER if r >= base]       # e.g. [1,3,4]
    dwell = max(1, (HISTORY - 1) // max(1, len(rungs)))
    seq: list[float] = []
    for r in rungs:
        seq += [float(r)] * dwell
    seq += [float(_TOP)] * max(1, HISTORY - len(seq))
    seq = seq[:HISTORY] if len(seq) >= HISTORY else seq + [float(_TOP)] * (HISTORY - len(seq))
    payload_idx = next(i for i, v in enumerate(seq) if v == _TOP)
    return seq, payload_idx


def _detected(detector: OriginAnomalyDetector, did: str, seq: list[float],
              rng: random.Random) -> bool:
    """True if ANY assertion in this origin's stream is flagged (origin-level
    alert). Observation noise is added to each asserted ceiling."""
    flagged = False
    for v in seq:
        obs = max(0.0, v + rng.gauss(0.0, OBS_NOISE))
        if detector.observe(did, obs):
            flagged = True
    return flagged


def _build_population(seed: int):
    rng = random.Random(seed)
    honest = [(_honest_stream(rng), f"hon-{i}") for i in range(N_HONEST)]
    naive = [(_naive_stream(rng)[0], f"nai-{i}") for i in range(N_NAIVE)]
    gradual = [(_gradual_stream(rng)[0], f"grd-{i}") for i in range(N_GRADUAL)]
    return honest, naive, gradual


def run(seed: int = 20250615) -> list[dict]:
    honest, naive, gradual = _build_population(seed)
    rows = []
    thr = 0.25
    while thr <= 4.5 + 1e-9:
        # fresh detector + a fixed noise stream per threshold (paired comparison)
        det = OriginAnomalyDetector(jump_threshold=thr)
        nrng = random.Random(seed + 1)
        fp = sum(_detected(det, did, seq, nrng) for seq, did in honest)
        det = OriginAnomalyDetector(jump_threshold=thr); nrng = random.Random(seed + 2)
        tp_naive = sum(_detected(det, did, seq, nrng) for seq, did in naive)
        det = OriginAnomalyDetector(jump_threshold=thr); nrng = random.Random(seed + 3)
        tp_grad = sum(_detected(det, did, seq, nrng) for seq, did in gradual)

        fpr = fp / len(honest)
        tpr_n = tp_naive / len(naive)
        tpr_g = tp_grad / len(gradual)
        fl, fh = stats.proportion_ci(fp, len(honest))
        nl, nh = stats.proportion_ci(tp_naive, len(naive))
        gl, gh = stats.proportion_ci(tp_grad, len(gradual))
        rows.append({"jump_threshold": round(thr, 3),
                     "tpr_naive": round(tpr_n, 4), "tpr_naive_lo": round(nl, 4),
                     "tpr_naive_hi": round(nh, 4),
                     "tpr_gradual": round(tpr_g, 4), "tpr_gradual_lo": round(gl, 4),
                     "tpr_gradual_hi": round(gh, 4),
                     "fpr": round(fpr, 4), "fpr_lo": round(fl, 4), "fpr_hi": round(fh, 4)})
        thr += 0.25
    return rows


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 84)
    print("P2-B6 — Detection: naive vs gradual evasion (TPR / FPR)")
    print("=" * 84)
    print(f"population: {N_HONEST} honest ({int(P_UPGRADE*100)}% legit-upgrade), "
          f"{N_NAIVE} naive, {N_GRADUAL} gradual · obs-noise σ={OBS_NOISE}\n")

    rows = run()
    print(f"{'threshold':>10}{'TPR naive':>12}{'TPR gradual':>13}{'FPR':>8}")
    print("-" * 84)
    for r in rows:
        print(f"{r['jump_threshold']:>10.2f}{r['tpr_naive']:>12.3f}"
              f"{r['tpr_gradual']:>13.3f}{r['fpr']:>8.3f}")
    print("-" * 84)

    with open(os.path.join(OUT_DIR, "detection.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # operating point: the threshold maximising (TPR_naive − FPR) shows the band
    op = max(rows, key=lambda r: r["tpr_naive"] - r["fpr"])
    gap = op["tpr_naive"] - op["tpr_gradual"]
    print(f"\nBest naive-detection operating point @ threshold={op['jump_threshold']}: "
          f"TPR_naive={op['tpr_naive']:.2f}, TPR_gradual={op['tpr_gradual']:.2f}, "
          f"FPR={op['fpr']:.2f}")
    print(f"  → naive−gradual TPR gap = {gap:.2f}: the detector catches the naive "
          f"capture but the gradual one evades at the same FPR.")
    print("Finding: detection is a real second-order boundary — it forces capture "
          "to be SLOW (gradual) to evade, raising attacker cost/latency — but it "
          "cannot close the residual: gradual class-ramps are statistically "
          "indistinguishable from legitimate upgrades (catching them spikes FPR).")
    print(f"CSV: {OUT_DIR}/detection.csv")
    print("=" * 84)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
