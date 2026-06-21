"""E3.1 — lying-transformation adversary + the soft-binding/watermark detector.

A malicious *relay* claims a faithful transformation (VERBATIM) to inherit its
input's high warrant, while actually rewriting the content to inject a falsehood.
The defense is the **soft-binding / watermark mismatch detector** (SimHash,
`capm/manifest/watermark.py`): a VERBATIM claim whose watermark similarity to its
input falls below threshold did not preserve the input → it is rescored as a
GENERATION and its warrant collapses.

We sweep the relay's **edit fraction** (how much of the input it rewrites while
still claiming VERBATIM) and measure, at each level:
  * watermark similarity to the input,
  * the detector's flag rate (true-positive detection of the lie),
  * the resulting ASR (can the relay deliver materially-altered content at high
    warrant?), with the detector ON vs OFF (ablation).

The key result is a **no-win** for the relay: to inject a meaningful falsehood it
must edit substantially (high fraction) — which the watermark catches; to evade
the watermark it can only make cosmetic edits (low fraction) — which carry no
attack. The region that both evades detection *and* alters content is empty. The
detector also does **not** false-positive on a genuinely faithful (or merely
reformatted) relay (edit fraction 0 → similarity ~1 → not flagged).

Run:  python3 -m experiments.e3_1_lying_transformation
"""

from __future__ import annotations

import csv
import os

from attacks.adaptive.profiles import AdversaryProfile, honest_origin
from capm.benchmark import stats
from capm.benchmark.runner import run_trial
from capm.core.types import SourceClass, TransformationType, WarrantLevel
from capm.warrant.evaluator import EvaluatorPolicy

OUT_DIR = os.path.join("results", "p2", "e3_1")
EDIT_FRACTIONS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0]
# honest high-warrant origins the lying relay tries to launder its falsehood under
ORIGINS = [
    "The audited quarterly revenue figure is 17.3 million dollars across all regions.",
    "The committee approved the merger on March 14 after a unanimous vote.",
    "The verified specification value for the component tolerance is 0.05 millimetres.",
    "The certified lab result lists the contaminant level at 2 parts per billion.",
]
_FILLER = ("certainly definitely must surely doubled tripled urgent immediately "
           "approved authorised override release transfer now critical").split()


class EditingResponder:
    """Rewrites a fraction of the input's tokens (deterministically) while the
    relay still stamps VERBATIM — the lying-transformation attack, tunable in
    magnitude so we can trace the detector's discrimination."""

    def __init__(self, edit_fraction: float):
        self.frac = edit_fraction

    def __call__(self, query, inputs):
        if not inputs:
            return f"[no data for {query}]", TransformationType.GENERATION
        toks = inputs[0].content.split()
        k = int(round(self.frac * len(toks)))
        # replace an evenly-spaced set of k tokens with filler (monotone in frac)
        if k > 0:
            step = max(1, len(toks) // k)
            j = 0
            for i in range(0, len(toks), step):
                if j >= k:
                    break
                toks[i] = _FILLER[j % len(_FILLER)]
                j += 1
        return " ".join(toks), TransformationType.VERBATIM


def _lying_relay(frac: float) -> AdversaryProfile:
    return AdversaryProfile(
        content="", true_source_class=SourceClass.MODEL_MEMORY,
        declared_source_class=SourceClass.MODEL_MEMORY,
        asserted_warrant=WarrantLevel.NONE,
        declared_transformation=TransformationType.VERBATIM,           # the lie
        actual_transformation=TransformationType.GENERATION,
        is_origin=False, label=f"lying_relay_{frac}",
        responder_override=EditingResponder(frac))


def _trial(frac, origin_text, policy):
    origin = honest_origin(origin_text, SourceClass.AUTHORITATIVE_API)
    return run_trial("capm", n_hops=2, adversary=origin,
                     relay_adversaries={0: _lying_relay(frac)}, policy=policy)


def run():
    on = EvaluatorPolicy()                                   # watermark detector ON
    off = EvaluatorPolicy(detect_watermark_mismatch=False,   # ablation: detector OFF
                          detect_transformation_lies=False)
    rows = []
    for frac in EDIT_FRACTIONS:
        det = asr_on = asr_off = 0
        for text in ORIGINS:
            r_on = _trial(frac, text, on)
            r_off = _trial(frac, text, off)
            det += int(r_on.lie_detected)
            asr_on += int(r_on.decision == "accept")
            asr_off += int(r_off.decision == "accept")
        n = len(ORIGINS)
        rows.append(dict(edit_fraction=frac, n=n,
                         detection_rate=det / n,
                         asr_detector_on=asr_on / n,
                         asr_detector_off=asr_off / n))
    return rows


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = run()

    print("=" * 84)
    print("E3.1  Lying transformation vs. the soft-binding / watermark mismatch detector")
    print("=" * 84)
    print(f"{len(ORIGINS)} honest STRONG origins; a relay claims VERBATIM while "
          f"rewriting an increasing fraction of the content.\n")
    print(f"  {'edit frac':>10s} {'watermark detect (TPR)':>23s} "
          f"{'ASR detector ON':>16s} {'ASR detector OFF':>17s}")
    print("  " + "-" * 72)
    for r in rows:
        print(f"  {r['edit_fraction']:>10.2f} {r['detection_rate']:>23.2f} "
              f"{r['asr_detector_on']:>16.2f} {r['asr_detector_off']:>17.2f}")

    # the attack is "material" once a non-trivial fraction is rewritten
    material = [r for r in rows if r["edit_fraction"] >= 0.2]
    det_material = sum(r["detection_rate"] for r in material) / len(material)
    asr_on_material = sum(r["asr_detector_on"] for r in material) / len(material)
    asr_off_material = sum(r["asr_detector_off"] for r in material) / len(material)
    fp = rows[0]["detection_rate"]            # edit_fraction 0 → false-positive rate

    print(f"\n  detector OFF: a false VERBATIM claim keeps the origin's STRONG warrant "
          f"→ ASR {asr_off_material:.2f} on materially-edited content (the lie pays off).")
    print(f"  detector ON:  material edits (≥20%) are caught {det_material:.0%} of the "
          f"time → warrant collapses → ASR {asr_on_material:.2f}.")
    print(f"  false positives on a faithful relay (edit 0%): {fp:.2f} "
          f"(watermark tolerates cosmetic variation; only regeneration is flagged).")
    print("\nNo-win for the relay: evading the watermark requires ~verbatim content "
          "(no attack); injecting a falsehood requires editing (caught).")

    csv_path = os.path.join(OUT_DIR, "lying_transformation.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    fig_path = _make_figure(rows)

    print(f"\nCSV: {csv_path}")
    if fig_path:
        print(f"Fig: {fig_path}")
    print("=" * 84)
    ok = (det_material >= 0.99 and asr_on_material == 0.0
          and asr_off_material > 0.0 and fp == 0.0)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 2


def _make_figure(rows) -> str:
    try:
        from experiments import figtools as ft
    except Exception as e:
        print(f"(figure skipped: {e})")
        return ""
    fr = [r["edit_fraction"] for r in rows]
    det = [r["detection_rate"] for r in rows]
    on = [r["asr_detector_on"] for r in rows]
    off = [r["asr_detector_off"] for r in rows]
    fig, ax = ft.new(figsize=(7.8, 4.6))
    ax.plot(fr, det, marker="o", color=ft.ACCENT, lw=2.2,
            label="watermark detection rate (TPR)")
    ax.plot(fr, on, marker="D", color=ft.OK, lw=2.2,
            label="ASR — detector ON")
    ax.plot(fr, off, marker="s", color=ft.WARN, lw=2.2, ls="--",
            label="ASR — detector OFF (lie pays off)")
    ft._style(ax, "E3.1 — false VERBATIM claim vs. watermark mismatch detector",
              xlabel="fraction of content the relay rewrote (while claiming VERBATIM)",
              ylabel="rate")
    ax.set_ylim(-0.05, 1.1)
    ax.axvspan(0.0, 0.1, color="#dfe7ec", alpha=0.6)
    ax.text(0.05, 0.5, "cosmetic\n(no attack)", fontsize=7, ha="center", color="#667")
    ax.legend(fontsize=8, frameon=False, loc="center right")
    return ft.save(fig, "e3_1_watermark_detection.png")


if __name__ == "__main__":
    raise SystemExit(main())
