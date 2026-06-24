"""Shared matplotlib styling for Phase-2 report figures.

Run with the phase-2 venv (`.venv/bin/python`) which has matplotlib/numpy.
All figures land in ``results/report/figures/`` as PNG (150 dpi) and are
embedded from PHASE2_IMPLEMENTATION_REPORT.md. Every figure is regenerable
from cached CSV rows under ``results/p2/`` with zero model calls.
"""
from __future__ import annotations

import os
import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt

FIG_DIR = os.path.join("results", "report", "figures")

# CAPM palette: baselines muted grey, the defense in a distinct accent.
ACCENT = "#1b6ca8"      # CAPM / "good"
BASE = "#9aa5b1"        # baselines / neutral
WARN = "#c0392b"        # attack / residual / "break"
OK = "#27ae60"          # contained / pass


def _style(ax, title: str, xlabel: str = "", ylabel: str = ""):
    ax.set_title(title, fontsize=11, fontweight="bold", pad=10)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def save(fig, name: str) -> str:
    os.makedirs(FIG_DIR, exist_ok=True)
    path = os.path.join(FIG_DIR, name)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def new(figsize=(7.2, 4.2)):
    return plt.subplots(figsize=figsize)
