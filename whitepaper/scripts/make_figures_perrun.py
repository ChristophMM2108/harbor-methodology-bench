"""Per-run figures: outcome, outcome matrix, overhead, budget, behaviour, adherence.

Same six views the analysis notebooks produce, regenerated from the exported
CSVs in a print style and written as PDF (for LaTeX) plus PNG (for preview).
Filenames are prefixed with the run, so both runs coexist in one directory.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib import ticker
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt

from figures_common import (AXIS, CONDITIONS, COLOR, CRITICAL, GOOD, INK, INK_2, LABEL,
                            MUTED, SURFACE, WARNING, bare, load, save, titled, wilson)


def task_boot(sub, col, reps: int = 20000, seed: int = 20260909):
    """Task-clustered bootstrap interval on a per-trial continuous score."""
    v = sub[["task", col]].dropna(subset=[col])
    groups = [g.values for _, g in v.groupby("task", observed=True)[col]]
    if not groups:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    draws = np.array([np.concatenate([groups[j] for j in
                                      rng.integers(0, len(groups), len(groups))]).mean()
                      for _ in range(reps)])
    return tuple(float(v) for v in np.percentile(draws, [2.5, 97.5]))


def cluster_ci(t, reps: int = 20000, seed: int = 20260909):
    """Task-clustered bootstrap interval on a test-level pass rate.

    Verifier tests share a task, a workspace and a verifier, so they are not
    independent Bernoulli draws and the binomial interval on them is too narrow.
    Resampling whole tasks with replacement keeps the within-task correlation.
    """
    ok = (t.status == "passed").astype(int)
    if len(ok) == 0:
        return (np.nan, np.nan)
    groups = [g.values for _, g in ok.groupby(t.task, observed=True)]
    rng = np.random.default_rng(seed)
    draws = np.array([np.concatenate([groups[j] for j in
                                      rng.integers(0, len(groups), len(groups))]).mean()
                      for _ in range(reps)])
    return tuple(float(v) for v in np.percentile(draws, [2.5, 97.5]))


def f01_outcome(run, trials, tests):
    graded = trials[~trials.censored]
    panels = []
    vals, cis = [], []
    for c in CONDITIONS:
        g = graded[graded.condition == c]
        vals.append(g.success.mean())
        cis.append(wilson(int(g.success.sum()), len(g)))
    panels.append(("Task success rate", vals, cis,
                   f"graded trials only; censored trials excluded"))
    panels.append(("Partial credit",
                   [trials.loc[trials.condition == c, "partial_credit"].mean() for c in CONDITIONS],
                   [task_boot(trials[trials.condition == c], "partial_credit")
                    for c in CONDITIONS],
                   "mean fraction of each verifier's tests passed"))
    vals, cis = [], []
    for c in CONDITIONS:
        t = tests[tests.condition == c]
        k, n = int((t.status == "passed").sum()), len(t)
        vals.append(k / n if n else np.nan)
        # tests are clustered within tasks -- a binomial interval on n test rows
        # treats them as independent and is roughly 2.5x too narrow here
        cis.append(cluster_ci(t))
    panels.append(("Test-level pass rate", vals, cis,
                   f"{len(tests)} verifier tests, clustered by task"))

    fig, axes = plt.subplots(1, 3, figsize=(11.0, 3.5))
    for ax, (title, values, ci, sub) in zip(axes, panels):
        x = np.arange(len(CONDITIONS))
        for i, cond in enumerate(CONDITIONS):
            v = 0 if pd.isna(values[i]) else values[i]
            ax.bar(x[i], v, width=0.6, color=COLOR[cond], zorder=3)
            top = max(v, ci[i][1] if ci and not pd.isna(ci[i][1]) else 0)
            ax.text(x[i], top + 0.035, f"{v*100:.1f}%", ha="center", va="bottom",
                    fontsize=10.5, color=INK, fontweight="bold")
        if ci:
            for i, (lo, hi) in enumerate(ci):
                if not pd.isna(lo):
                    ax.plot([x[i], x[i]], [lo, hi], color=INK_2, lw=1.5, zorder=4,
                            solid_capstyle="butt")
        bare(ax)
        ax.set_xticks(x, [LABEL[c] for c in CONDITIONS], fontsize=9.5)
        ax.set_ylim(0, 1.14)
        ax.set_yticks(np.arange(0, 1.01, 0.25), [f"{v:.0%}" for v in np.arange(0, 1.01, 0.25)])
        titled(ax, title, sub)
    fig.tight_layout()
    save(fig, f"{run}-01-outcome", "Bars: point estimate. Whiskers: 95 % interval -- Wilson "
         "on the binary rate, task-clustered bootstrap on the two fine metrics, whose "
         "observations are clustered within tasks.")


def f02_matrix(run, trials):
    pa2 = trials.pivot_table(index="task", columns="condition", values="success",
                             observed=True, aggfunc="max")[CONDITIONS]
    pboth = (trials.pivot_table(index="task", columns="condition", values="success",
                                observed=True, aggfunc="mean")[CONDITIONS] == 1).astype(int)
    to = trials.pivot_table(index="task", columns="condition", values="agent_timeout",
                            observed=True, aggfunc="max")[CONDITIONS]
    order = (pa2.sum(axis=1) * 10 + pboth.sum(axis=1)).sort_values(ascending=False).index
    pa2, pboth, to = pa2.loc[order], pboth.loc[order], to.loc[order]
    split = set(pa2.index[(pa2.sum(axis=1) > 0) & (pa2.sum(axis=1) < 3)])

    fig, ax = plt.subplots(figsize=(7.4, 0.40 * len(pa2) + 1.9))
    for j, cond in enumerate(CONDITIONS):
        for i, task in enumerate(pa2.index):
            passed, both = bool(pa2.loc[task, cond]), bool(pboth.loc[task, cond])
            color = GOOD if passed else CRITICAL
            ax.scatter(j, i, s=460, marker="s", color=color,
                       alpha=0.30 if both else 0.14, zorder=2, edgecolors="none")
            mark = "2/2" if both else ("1/2" if passed else "0/2")
            ax.text(j, i, mark, ha="center", va="center", fontsize=9,
                    color=color, fontweight="bold", zorder=3)
            if bool(to.loc[task, cond]):
                ax.scatter(j + 0.30, i, s=34, marker="o", color=WARNING, zorder=3,
                           edgecolors=SURFACE, linewidths=1.2)
    for i, task in enumerate(pa2.index):
        ax.text(-0.62, i, task, ha="right", va="center", fontsize=9.5,
                color=INK if task in split else MUTED,
                fontweight="bold" if task in split else "normal")
    ax.set_xlim(-0.7, 2.55)
    ax.set_ylim(len(pa2) - 0.5, -0.5)
    ax.set_xticks(range(3), [LABEL[c] for c in CONDITIONS])
    ax.set_yticks([])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(axis="x", length=0, labelsize=10.5)
    n_ap = int((pa2.sum(axis=1) == 3).sum())
    n_af = int((pa2.sum(axis=1) == 0).sum())
    titled(ax, f"{len(split)} of {len(pa2)} tasks discriminate between conditions",
           f"{n_ap} passed everywhere · {n_af} failed everywhere · split tasks in bold")
    ax.legend(handles=[
        Line2D([], [], marker="s", color=GOOD, lw=0, markersize=9, alpha=0.35, label="passed"),
        Line2D([], [], marker="s", color=CRITICAL, lw=0, markersize=9, alpha=0.35, label="failed"),
        Line2D([], [], marker="o", color=WARNING, lw=0, markersize=6, label="hit its time budget"),
    ], loc="lower right", bbox_to_anchor=(1.02, -0.13 - 1.2 / len(pa2)), ncol=3)
    fig.tight_layout()
    save(fig, f"{run}-02-outcome-matrix",
         "Cell label: attempts passed of two. Fill intensity marks pass-both.")


def f03_overhead(run, trials):
    summ = trials.groupby("condition", observed=True).agg(
        cost_per_trial=("cost_usd", "mean"), agent_sec=("agent_sec", "mean"),
        output_tokens=("output_tokens", "mean"), steps=("n_steps", "mean"),
        tool_calls=("n_tool_calls", "mean"), budget=("budget_used", "mean"),
        cost_total=("cost_usd", "sum"))
    cols = ["cost_per_trial", "agent_sec", "output_tokens", "steps", "tool_calls", "budget"]
    labels = ["cost per trial", "agent wall-clock", "output tokens", "agent steps",
              "tool calls", "budget consumed"]
    index = summ[cols].div(summ.loc["baseline", cols])
    fig, ax = plt.subplots(figsize=(11.0, 3.9))
    x = np.arange(len(cols))
    width = 0.26
    for k, cond in enumerate(CONDITIONS):
        v = [index.loc[cond, c] for c in cols]
        pos = x + (k - 1) * (width + 0.015)
        ax.bar(pos, v, width=width, color=COLOR[cond], zorder=3, label=LABEL[cond])
        for xi, vi in zip(pos, v):
            ax.text(xi, vi + 0.04, f"{vi:.2f}", ha="center", va="bottom", fontsize=8.6,
                    color=INK, fontweight="bold")
    ax.axhline(1.0, color=AXIS, lw=1.1, zorder=2)
    bare(ax)
    ax.set_xticks(x, labels)
    ax.set_ylabel("indexed to baseline = 1.00")
    titled(ax, "Overhead relative to baseline",
           " · ".join(f"{LABEL[c]}: ${summ.loc[c, 'cost_total']:.2f}" for c in CONDITIONS))
    ax.legend(loc="upper left", ncol=3)
    ax.set_ylim(0, max(index.to_numpy().max() * 1.22, 1.3))
    fig.tight_layout()
    save(fig, f"{run}-03-overhead", "Every measure on one axis, so no second scale is invented.")


def f04_budget(run, trials):
    fig, ax = plt.subplots(figsize=(11.0, 3.4))
    rng = np.random.default_rng(0)
    for k, cond in enumerate(CONDITIONS):
        sub = trials[trials.condition == cond].reset_index(drop=True)
        # one jitter per trial, reused by the censoring rings, so a ring always
        # sits on its own point instead of collapsing onto the wall
        y = k + rng.uniform(-0.17, 0.17, len(sub))
        ax.scatter(sub.budget_used, y, s=62, color=COLOR[cond], alpha=0.85, zorder=3,
                   edgecolors=SURFACE, linewidths=1.0)
        cens = sub.censored.to_numpy()
        solved = (sub.success == 1).to_numpy() & cens
        ax.scatter(sub.budget_used[cens & ~solved], y[cens & ~solved], s=175, facecolors="none",
                   edgecolors=WARNING, linewidths=1.7, zorder=4)
        ax.scatter(sub.budget_used[solved], y[solved], s=175, facecolors="none",
                   edgecolors=GOOD, linewidths=1.9, zorder=5)
        note = f"mean {sub.budget_used.mean():.0%}"
        if cens.sum():
            note += f"  ·  {int(cens.sum())} censored"
            if solved.sum():
                note += f", {int(solved.sum())} already passing"
        ax.text(1.06, k, note, va="center", fontsize=9.5, color=INK_2)
    ax.axvline(1.0, color=CRITICAL, lw=1.4, zorder=2)
    ax.text(1.005, 2.46, "budget wall", fontsize=9.5, color=CRITICAL, va="top")
    bare(ax, grid_axis="x")
    ax.set_yticks(range(3), [LABEL[c] for c in CONDITIONS], fontsize=10.5)
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(-0.5, 2.58)
    ax.set_xlim(0, 1.62)
    ax.set_xticks(np.arange(0, 1.01, 0.25), [f"{v:.0%}" for v in np.arange(0, 1.01, 0.25)])
    ax.set_xlabel("share of the task's declared agent budget consumed")
    titled(ax, "Budget consumption and censoring",
           "amber ring: killed by the clock  ·  green ring: killed with a passing verifier already on disk")
    fig.tight_layout()
    save(fig, f"{run}-04-budget", "Budget from each task's task.toml via results/task_catalogue.json.")


def f05_behaviour(run, trials):
    spec = [("n_steps", "agent steps"), ("n_tool_calls", "tool calls"),
            ("n_edits_total", "file edits / writes"), ("bash_test", "verification commands"),
            ("n_agent_spawns", "sub-agents spawned"), ("error_rate", "tool results with an error")]
    fig, axes = plt.subplots(2, 3, figsize=(11.0, 5.4))
    for ax, (col, label) in zip(axes.ravel(), spec):
        v = [trials.loc[trials.condition == c, col].mean() for c in CONDITIONS]
        peak = max([x for x in v if not pd.isna(x)] or [1])
        for i, cond in enumerate(CONDITIONS):
            ax.bar(i, v[i], width=0.6, color=COLOR[cond], zorder=3)
            txt = f"{v[i]:.0%}" if col == "error_rate" else (
                f"{v[i]:.2f}" if peak < 10 else f"{v[i]:.1f}")
            ax.text(i, v[i] + peak * 0.045, txt, ha="center", va="bottom", fontsize=10,
                    color=INK, fontweight="bold")
        bare(ax)
        ax.set_xticks(range(3), [LABEL[c] for c in CONDITIONS], fontsize=9)
        ax.set_ylim(0, peak * 1.30)
        if col == "error_rate":
            ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1, decimals=0))
        ax.set_title(label, loc="left", fontsize=11.5)
    fig.suptitle("Behavioural profile, per-trial means", x=0.005, ha="left", fontsize=13,
                 fontweight="bold", color=INK, y=1.02)
    fig.tight_layout()
    save(fig, f"{run}-05-behaviour",
         "Verification commands are pattern-matched shell buckets, not parsed invocations.")


def f06_adherence(run, trials):
    n = int(trials.groupby("condition", observed=True).size().max())
    stages = [("named CLAUDE.md / AGENTS.md\nin its own output",
               lambda s: int(s.config_markers.fillna("").ne("").sum())),
              ("opened it with\nRead or cat", lambda s: int((s.n_config_reads > 0).sum())),
              ("invoked a toolkit skill\nvia the Skill tool",
               lambda s: int((s.n_toolkit_skill_calls > 0).sum()))]
    toolkits = [c for c in CONDITIONS if c != "baseline"]
    fig, ax = plt.subplots(figsize=(8.2, 3.5))
    x = np.arange(len(stages))
    width = 0.34
    for k, cond in enumerate(toolkits):
        sub = trials[trials.condition == cond]
        v = [fn(sub) for _, fn in stages]
        pos = x + (k - 0.5) * (width + 0.02)
        ax.bar(pos, v, width=width, color=COLOR[cond], zorder=3, label=LABEL[cond])
        for xi, vi in zip(pos, v):
            ax.text(xi, vi + n * 0.012, f"{vi:.0f}", ha="center", va="bottom", fontsize=10,
                    color=INK, fontweight="bold")
    ax.axhline(n, color=AXIS, lw=1.0, ls=(0, (4, 3)), zorder=2)
    ax.text(len(stages) - 0.52, n * 1.015, f"all {n} trials", fontsize=9, color=MUTED, ha="right")
    bare(ax)
    ax.set_xticks(x, [s for s, _ in stages], fontsize=9.5)
    ax.set_ylabel(f"trials out of {n}")
    ax.set_ylim(0, n * 1.14)
    titled(ax, "Availability versus adherence",
           "strict: a Skill tool call whose skill name is one the variant installed")
    ax.legend(loc="upper right", ncol=2)
    fig.tight_layout()
    save(fig, f"{run}-06-adherence")


if __name__ == "__main__":
    for run in ("suite", "ceiling"):
        print(run)
        trials, tests = load(run)
        f01_outcome(run, trials, tests)
        f02_matrix(run, trials)
        f03_overhead(run, trials)
        f04_budget(run, trials)
        f05_behaviour(run, trials)
        f06_adherence(run, trials)
