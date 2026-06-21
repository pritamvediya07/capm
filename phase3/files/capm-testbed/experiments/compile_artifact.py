"""E9.2 — compile every figure and table into one reproducible PDF.

After the experiments have run (each writes its raw CSV under results/p2/<exp>/
and its PNG under results/report/figures/), this regenerates the single
artifact-evaluation deliverable: **results/report/CAPM_artifact.pdf** — a
multi-page PDF with a title/index page, every figure (one per page with its
source), and every results table (rendered from the raw CSVs). No external
toolchain required (matplotlib PdfPages only).

Run:  python3 -m experiments.compile_artifact
"""

from __future__ import annotations

import csv
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

FIG_DIR = os.path.join("results", "report", "figures")
CSV_GLOB = os.path.join("results", "p2", "*", "*.csv")
OUT_PDF = os.path.join("results", "report", "CAPM_artifact.pdf")

# figure filename → (paper section, caption)
FIG_INFO = {
    "e1_1_containment_matrix": ("E1.1", "Laundering containment vs baselines (real attacks + models)"),
    "e1_2_attribution_survival": ("E1.2", "Per-field attribution survives real lossy paraphrase"),
    "e1_3_task_efficacy": ("E1.3", "Task outcome under attack (SAGA tasks)"),
    "e2_": ("E2.x", "Soundness / forgery"),
    "e3_1_watermark_detection": ("E3.1", "Lying-transformation vs watermark detector"),
    "e3_2_origin_capture": ("E3.2", "Origin capture: warrant boundary → attribution → revocation"),
    "e3_4_collusion": ("E3.4", "Collusion: warrant is origin-bounded"),
    "e3_5_adaptive_loop": ("E3.5", "Adaptive loop: persuasiveness ↑, ASR flat"),
    "e4_2_cross_model": ("E4.2", "Cross-model generality"),
    "e4_3_source_bias": ("E4.3", "Latent source-bias correction"),
    "e4_1_transformation_faithfulness": ("E4.1", "Real responders: classify actual transformation"),
    "e5_1_admit": ("E5.1", "ADMIT: ASR vs poisoning rate"),
    "e5_2_flooding": ("E5.2", "Flooding-Spread propagation over rounds"),
    "e5_3_causality": ("E5.3", "Causality-Laundering"),
    "e5_4_agentdojo": ("E5.4", "Cross-org containment on real AgentDojo"),
    "e6_1_overhead": ("E6.1", "Overhead vs chain length (SAGA Monitor)"),
    "e6_2_throughput": ("E6.2", "Verification throughput scaling"),
    "e6_3_compaction": ("E6.3", "Merkle compaction bounds manifest size"),
    "e7_1_pareto": ("E7.1", "Utility–resistance Pareto frontier"),
    "e7_2_false_positive": ("E7.2", "Over-blocking FPR"),
    "e7_3_calibration": ("E7.3", "Warrant–fidelity calibration"),
    "e8_ablation": ("E8.x", "Component-ablation necessity matrix"),
    "e9_3_statistics": ("E9.3", "Effect sizes + significance (forest plot)"),
}


def _info(stem: str):
    for key, val in FIG_INFO.items():
        if stem.startswith(key):
            return val
    return ("—", stem.replace("_", " "))


def _text_page(pdf, lines, title=""):
    fig = plt.figure(figsize=(8.27, 11.69))   # A4 portrait
    fig.text(0.5, 0.95, title, ha="center", fontsize=14, fontweight="bold")
    fig.text(0.06, 0.90, "\n".join(lines), ha="left", va="top", family="monospace",
             fontsize=7.5)
    pdf.savefig(fig); plt.close(fig)


def _figure_page(pdf, png_path, section, caption):
    img = mpimg.imread(png_path)
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.text(0.5, 0.95, f"Figure — {section}", ha="center", fontsize=13, fontweight="bold")
    fig.text(0.5, 0.915, caption, ha="center", fontsize=9, color="#444")
    ax = fig.add_axes([0.06, 0.12, 0.88, 0.76]); ax.imshow(img); ax.axis("off")
    fig.text(0.5, 0.05, os.path.basename(png_path), ha="center", fontsize=7, color="#999")
    pdf.savefig(fig); plt.close(fig)


def _csv_lines(path, max_rows=28):
    out = [os.path.relpath(path)]
    with open(path) as f:
        rows = list(csv.reader(f))
    if not rows:
        return out + ["(empty)"]
    widths = [max(len(str(r[i])) if i < len(r) else 0 for r in rows[:max_rows + 1])
              for i in range(len(rows[0]))]
    for r in rows[:max_rows + 1]:
        out.append("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(r)))
    if len(rows) > max_rows + 1:
        out.append(f"... (+{len(rows) - max_rows - 1} more rows)")
    return out


def main() -> int:
    os.makedirs(os.path.dirname(OUT_PDF), exist_ok=True)
    figs = sorted(glob.glob(os.path.join(FIG_DIR, "*.png")))
    csvs = sorted(glob.glob(CSV_GLOB))

    with PdfPages(OUT_PDF) as pdf:
        # title / index page
        idx = ["CAPM — Cross-Agent Provenance Manifests",
               "Artifact-evaluation bundle (E9.2): every figure + table, reproducible.",
               "", f"figures: {len(figs)}    tables (raw CSVs): {len(csvs)}",
               "", "Reproduce from scratch:",
               "  bash scripts/run_all_experiments.sh", "",
               "Figures included:"]
        for p in figs:
            stem = os.path.splitext(os.path.basename(p))[0]
            sec, cap = _info(stem)
            idx.append(f"  [{sec:5s}] {cap}")
        _text_page(pdf, idx, "CAPM Artifact Bundle")

        # one page per figure
        for p in figs:
            stem = os.path.splitext(os.path.basename(p))[0]
            sec, cap = _info(stem)
            _figure_page(pdf, p, sec, cap)

        # table pages (group several CSVs per page)
        per_page, buf = 0, []
        for c in csvs:
            block = _csv_lines(c) + [""]
            if per_page and per_page + len(block) > 90:
                _text_page(pdf, buf, "Results tables (raw CSV)"); buf, per_page = [], 0
            buf += block; per_page += len(block)
        if buf:
            _text_page(pdf, buf, "Results tables (raw CSV)")

    size_kb = os.path.getsize(OUT_PDF) / 1024
    print(f"E9.2  Artifact PDF compiled: {OUT_PDF}")
    print(f"  {len(figs)} figures + {len(csvs)} raw tables → {size_kb:.0f} KB PDF")
    print(f"  one-command reproduction: bash scripts/run_all_experiments.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
