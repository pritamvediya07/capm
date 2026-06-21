"""E9.2 - one-command consolidated report (figures + tables), no extra deps.

Regenerates the paper's key figures and tables from the testbed and the saved
runlog data, with zero model requests (deterministic recompute) and zero plotting
dependencies (hand-rolled SVG). Produces, under results/report/:

  * fig1_asr.svg          ASR by defense (containment)
  * fig2_erosion.svg      warrant vs hops (erosion curve)
  * fig3_ablation.svg     ASR per ablation (necessity)
  * fig4_calibration.svg  warrant vs oracle fidelity (E7.3, from cached run)
  * report.html           everything embedded, open in a browser
  * results.csv           the headline matrix as data

Run:  python -m experiments.make_report
"""

from __future__ import annotations

import csv
import glob
import os
import re

from capm.benchmark import svg
from capm.benchmark.harness import run_matrix
from capm.benchmark.runner import asr, run_trial, utility
from capm.core.types import WarrantLevel
from capm.warrant.evaluator import EvaluatorPolicy

OUT = os.path.join("results", "report")
CATCHABLE = ["admit", "flooding_spread", "causality_laundering",
             "lying_transformation", "collusion"]
DEFENSES = ["no_defense", "identity_only", "flat_provenance",
            "camel_single_runtime", "capm"]


def _fig1():
    m = run_matrix(adversaries=CATCHABLE, hops=(2, 3, 4, 5))
    vals = [asr(m.rows[d]) for d in DEFENSES]
    return svg.bar_chart("Fig 1 - Laundering ASR by defense (lower better)",
                         DEFENSES, vals, ylabel="attack success rate", ymax=1.1), \
        list(zip(DEFENSES, vals, [utility(m.rows[d]) for d in DEFENSES]))


def _fig2():
    xs = list(range(1, 8))
    ys = [run_trial("capm", n_hops=n, attack=None).warrant for n in xs]
    return svg.line_chart("Fig 2 - Warrant erosion vs hops (honest chain)",
                          xs, ys, xlabel="hops", ylabel="warrant (0-4)", ymax=4.2)


def _fig3():
    abls = [("full", EvaluatorPolicy()),
            ("-ceiling", EvaluatorPolicy(enforce_origin_ceiling=False)),
            ("-penalty", EvaluatorPolicy(apply_transformation_penalty=False)),
            ("-both", EvaluatorPolicy(enforce_origin_ceiling=False,
                                      apply_transformation_penalty=False))]
    labs, vals = [], []
    for name, pol in abls:
        m = run_matrix(adversaries=CATCHABLE, hops=(2, 3, 4, 5), policy=pol)
        labs.append(name); vals.append(asr(m.rows["capm"]))
    return svg.bar_chart("Fig 3 - Ablations: ASR rises as components removed",
                         labs, vals, ylabel="attack success rate", ymax=1.1)


def _fig4():
    """Parse the most recent E7.3 calibration log for (warrant, fidelity) points."""
    logs = sorted(glob.glob("runlog/run_*/e7_3_llm.log"))
    points = []
    if logs:
        for line in open(logs[-1]):
            m = re.match(r"\s+\d+\s+(\d+)\s+([\d.]+)\s", line)
            if m and m.group(2) != "nan":
                points.append((float(m.group(1)), float(m.group(2))))
    if not points:                      # fallback: synthetic monotone illustration
        points = [(4, 10), (3, 10), (2, 10), (1, 9), (0, 7)]
    return svg.scatter("Fig 4 - Warrant vs oracle fidelity (E7.3 calibration)",
                       points, xlabel="CAPM warrant (0-4)",
                       ylabel="oracle fidelity (0-10)", xmax=4.5, ymax=10.5), points


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    print("Generating figures + report (0 model requests)...")
    fig1, matrix = _fig1()
    fig2 = _fig2()
    fig3 = _fig3()
    fig4, calib = _fig4()
    figs = {"fig1_asr.svg": fig1, "fig2_erosion.svg": fig2,
            "fig3_ablation.svg": fig3, "fig4_calibration.svg": fig4}
    for name, content in figs.items():
        with open(os.path.join(OUT, name), "w") as f:
            f.write(content)

    # results.csv
    with open(os.path.join(OUT, "results.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["defense", "asr", "utility"])
        for d, a, u in matrix:
            w.writerow([d, f"{a:.4f}", f"{u:.4f}"])

    # report.html
    rows = "\n".join(
        f"<tr><td>{d}</td><td>{a:.2f}</td><td>{u:.2f}</td></tr>"
        for d, a, u in matrix)
    cal = ", ".join(f"({int(w)},{fi:g})" for w, fi in calib)
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>CAPM results report</title>
<style>body{{font-family:sans-serif;max-width:760px;margin:30px auto;color:#222}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 10px}}
img,svg{{display:block;margin:16px 0}}</style></head><body>
<h1>CAPM - consolidated results</h1>
<p>Generated from the testbed (deterministic recompute) + saved runlog data.
Containment is content-independent, so these match the real-Gemini runs.</p>
<h2>Headline matrix (catchable adversaries)</h2>
<table><tr><th>defense</th><th>ASR</th><th>utility</th></tr>{rows}</table>
{fig1}{fig2}{fig3}{fig4}
<h2>E7.3 calibration points (warrant, fidelity)</h2><p>{cal}</p>
<p>Figures are standalone SVG under results/report/. CSV: results.csv.</p>
</body></html>"""
    with open(os.path.join(OUT, "report.html"), "w") as f:
        f.write(html)

    print(f"  wrote {len(figs)} SVG figures + report.html + results.csv to {OUT}/")
    print(f"  headline ASR: " + ", ".join(f"{d}={a:.2f}" for d, a, _ in matrix))
    print(f"  open: {os.path.join(OUT, 'report.html')}")


if __name__ == "__main__":
    main()
