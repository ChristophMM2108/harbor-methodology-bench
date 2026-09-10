"""Shared plotting style for the whitepaper figures.

Deliberately close to the notebook style the runs were analysed with, retuned
for print: a Times-compatible serif (STIXGeneral) so figure text matches the
body font, larger tick labels relative to figure width, and a PDF primary
output with a PNG companion for preview.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
FIG = REPO / "whitepaper" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

CONDITIONS = ["baseline", "codezen-viable", "sdd"]
LABEL = {"baseline": "baseline", "codezen-viable": "CodeZen", "sdd": "SDD"}

SURFACE, INK, INK_2, MUTED, GRID, AXIS = "#ffffff", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#b9b8ad"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
COLOR = {c: SLOTS[i] for i, c in enumerate(CONDITIONS)}
GOOD, WARNING, CRITICAL = "#0ca30c", "#fab219", "#d03b3b"
RUN_MARK = {"suite": "o", "ceiling": "^"}

mpl.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": ["STIXGeneral"], "mathtext.fontset": "stix", "font.size": 11,
    "axes.titlesize": 12.5, "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlepad": 10,
    "axes.labelsize": 11, "axes.labelcolor": INK_2, "axes.edgecolor": AXIS, "axes.linewidth": 0.8,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2, "ytick.labelcolor": INK_2,
    "xtick.labelsize": 10, "ytick.labelsize": 10,
    "legend.frameon": False, "legend.fontsize": 10, "legend.labelcolor": INK_2,
    "grid.color": GRID, "grid.linewidth": 0.7, "grid.linestyle": "-",
    "figure.dpi": 120, "savefig.bbox": "tight", "pdf.fonttype": 42, "text.parse_math": False,
})


def bare(ax, grid_axis="y"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(AXIS)
    ax.spines["bottom"].set_color(AXIS)
    if grid_axis:
        ax.grid(True, axis=grid_axis, zorder=0)
        ax.set_axisbelow(True)
    return ax


def titled(ax, title, sub=None):
    ax.set_title(title, loc="left", pad=26 if sub else 10)
    if sub:
        ax.text(0, 1.012, sub, transform=ax.transAxes, fontsize=9.5, color=MUTED, va="bottom")


def save(fig, name, note=None):
    if note:
        fig.text(0.01, -0.01, note, ha="left", va="top", fontsize=8.5, color=MUTED)
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"{name}.{ext}", dpi=300 if ext == "png" else None)
    plt.close(fig)
    print(f"  figures/{name}.pdf + .png")


def wilson(k, n, z=1.96):
    if not n:
        return (np.nan, np.nan)
    p, denom = k / n, 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def load(run):
    d = REPO / f"results/analysis-{run}/data"
    trials = pd.read_csv(d / "trials.csv")
    for col in ("success", "agent_timeout", "verifier_timeout", "wrote_test_file"):
        trials[col] = trials[col].fillna(False).astype(int)
    trials["censored"] = (trials.agent_timeout | trials.verifier_timeout).astype(bool)
    trials["condition"] = pd.Categorical(trials.condition, CONDITIONS, ordered=True)
    tests = pd.read_csv(d / "tests.csv")
    return trials, tests
