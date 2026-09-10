"""Cross-run figures. These are new: the source discussions state these results
in prose or tables only.

x07  cost multiplier against task length            (the multiplier is flat)
x08  censoring, split by what was on disk at the kill
x09  best-of-N at equal spend, three estimators     (the corrected comparison)
x10  the length hypothesis, as the metric sharpens  (the lean dissolves)
x11  toolkit invocation against task horizon        (the toolkits self-gate)
x12  cost-effectiveness per pass and per passed test
x13  what a one-trial screen selects for            (the screening defect)
x14  are two attempts independent?                  (assumption behind x09)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from figures_common import (AXIS, CONDITIONS, COLOR, CRITICAL, GOOD, INK, INK_2, LABEL,
                            MUTED, REPO, RUN_MARK, SURFACE, bare, save, titled)

VN = json.loads((REPO / "whitepaper/data/verified_numbers.json").read_text())
BN = json.loads((REPO / "whitepaper/data/best_of_n.json").read_text())
TBL = pd.read_csv(REPO / "whitepaper/data/pooled_task_table.csv")
TBL["log_expert"] = np.log10(TBL.expert_min)
RUNS = ("suite", "ceiling")


def fisher_ci(rho, n, z=1.96):
    if n < 4 or abs(rho) >= 1:
        return (np.nan, np.nan)
    zr, se = np.arctanh(rho), 1 / np.sqrt(n - 3)
    return (np.tanh(zr - z * se), np.tanh(zr + z * se))


def x07_cost_ratio_flat():
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 3.9), sharey=True)
    for ax, cond in zip(axes, ("codezen-viable", "sdd")):
        key = cond.replace("-viable", "")
        for run in RUNS:
            sub = TBL[TBL.run == run]
            ax.scatter(sub.log_expert, sub[f"cost_ratio__{cond}"], s=64, marker=RUN_MARK[run],
                       color=COLOR[cond], alpha=0.85, zorder=3, edgecolors=SURFACE,
                       linewidths=0.9, label=run)
        r = VN["pooled"]["correlations"][f"{key}_cost_ratio_vs_log_expert"]
        ax.axhline(1.0, color=AXIS, lw=1.0, zorder=2)
        # fitted in log space, because the axis is logarithmic
        ok = TBL[f"cost_ratio__{cond}"].notna() & (TBL[f"cost_ratio__{cond}"] > 0)
        m, b = np.polyfit(TBL.log_expert[ok], np.log10(TBL.loc[ok, f"cost_ratio__{cond}"]), 1)
        xs = np.linspace(TBL.log_expert.min(), TBL.log_expert.max(), 20)
        ax.plot(xs, 10 ** (m * xs + b), color=INK_2, lw=1.3, ls=(0, (5, 3)), zorder=4)
        bare(ax)
        ax.set_yscale("log")
        ax.set_yticks([0.06, 0.25, 1, 4, 16], ["0.06x", "0.25x", "1x", "4x", "16x"])
        ax.set_xticks(np.log10([5, 15, 60, 240, 1440]), ["5 min", "15 min", "1 h", "4 h", "24 h"])
        ax.set_xlabel("expert time estimate for the task (log scale)")
        titled(ax, f"{LABEL[cond]} cost multiplier",
               f"Spearman rho = {r['rho']:+.3f}  (p = {r['p']:.3f}, n = {r['n']})")
        ax.legend(loc="upper left", ncol=2)
    axes[0].set_ylabel("cost relative to baseline, same task")
    fig.tight_layout()
    save(fig, "x07-cost-ratio-vs-length",
         "One point per task. Dashed line: least-squares fit, shown to make the flatness visible.")


def x08_censoring():
    fig, ax = plt.subplots(figsize=(8.6, 3.4))
    x, labels = 0, []
    for run in RUNS:
        for cond in CONDITIONS:
            c = VN["runs"][run]["conditions"][cond]
            n_cens, n_ok = c["censored"], c["censored_with_reward_1"]
            ax.bar(x, n_cens - n_ok, width=0.66, color=COLOR[cond], zorder=3)
            ax.bar(x, n_ok, bottom=n_cens - n_ok, width=0.66, color=GOOD, alpha=0.75, zorder=3)
            ax.text(x, n_cens + 0.16, f"{n_cens}/{c['trials']}", ha="center", va="bottom",
                    fontsize=9.5, color=INK, fontweight="bold")
            labels.append(LABEL[cond])
            x += 1
        x += 0.7
    bare(ax)
    ax.set_xticks([0, 1, 2, 3.7, 4.7, 5.7], labels, fontsize=9.5)
    ax.set_ylim(0, 8.6)
    ax.set_ylabel("trials killed by the clock")
    for xc, run in ((1, "suite"), (4.7, "ceiling")):
        ax.text(xc, 8.1, run, ha="center", fontsize=11, color=INK, fontweight="bold")
    titled(ax, "Censoring, and how much of it discarded finished work",
           "lower segment in the condition colour: still failing at the kill")
    ax.legend(handles=[Patch(facecolor=GOOD, alpha=0.75,
                             label="killed with a passing verifier already on disk")],
              loc="upper center", bbox_to_anchor=(0.5, -0.09))
    fig.tight_layout()
    save(fig, "x08-censoring", "Labels give censored trials out of trials run in that cell.")


def x09_best_of_n():
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.1))
    for ax, run in zip(axes, RUNS):
        t = pd.read_csv(REPO / f"results/analysis-{run}/data/trials.csv")
        t["success"] = t.success.fillna(False).astype(int)
        g = t[t.condition == "baseline"].groupby("task").success.agg(["sum", "size"])
        y, n = g["sum"].to_numpy(), g["size"].to_numpy()
        p_bar = y.sum() / n.sum()
        ks = np.linspace(1, 8, 80)
        naive = 1 - (1 - p_bar) ** ks
        plug = np.array([np.mean(1 - (1 - y / n) ** k) for k in ks])
        bb = BN["equal_spend"][run]["codezen-viable"]
        rng = np.random.default_rng(7)
        draws = rng.beta(bb["betabinom_a"], bb["betabinom_b"], 60000)
        beta = np.array([np.mean(1 - (1 - draws) ** k) for k in ks])

        ax.fill_between(ks, plug, naive, color=COLOR["baseline"], alpha=0.10, zorder=2)
        ax.plot(ks, naive, color=COLOR["baseline"], lw=1.9, zorder=4,
                label="baseline retries: homogeneous")
        ax.plot(ks, beta, color=COLOR["baseline"], lw=1.7, ls=(0, (5, 2)), zorder=4,
                label="baseline retries: beta-binomial")
        ax.plot(ks, plug, color=COLOR["baseline"], lw=1.5, ls=(0, (1.5, 2)), zorder=4,
                label="baseline retries: per-task plug-in")

        k_eq = 2 * bb["k_equal_spend"]
        cz_pa2 = (VN["runs"][run]["pass_at_2"]["per_condition"]["codezen-viable"]
                  / VN["runs"][run]["n_tasks"])
        ax.axvline(k_eq, color=COLOR["codezen-viable"], lw=1.2, ls=(0, (4, 3)), zorder=3,
                   label=f"equal-spend budget, k = {k_eq:.1f}")
        ax.scatter([k_eq], [cz_pa2], s=110, marker="D", color=COLOR["codezen-viable"], zorder=6,
                   edgecolors=SURFACE, linewidths=1.2, label="CodeZen, 2 attempts, same spend")
        ax.annotate(f"{cz_pa2:.0%}", (k_eq, cz_pa2), textcoords="offset points",
                    xytext=(9, -3), fontsize=10, color=COLOR["codezen-viable"], fontweight="bold")
        bare(ax)
        ax.set_xlim(1, 8)
        ax.set_ylim(0, 1.03)
        ax.set_yticks(np.arange(0, 1.01, 0.25), [f"{v:.0%}" for v in np.arange(0, 1.01, 0.25)])
        ax.set_xlabel("independent baseline attempts, k")
        titled(ax, run, f"baseline per-attempt pass rate {p_bar:.1%}")
        ax.legend(loc="lower right", fontsize=8.4, framealpha=0.95, frameon=True,
                  facecolor=SURFACE, edgecolor="none")
    axes[0].set_ylabel("probability at least one attempt passes")
    fig.suptitle("Best-of-N at equal spend turns entirely on the heterogeneity assumption",
                 x=0.005, ha="left", fontsize=13, fontweight="bold", color=INK, y=1.03)
    fig.tight_layout()
    save(fig, "x09-best-of-n",
         "Shaded band: between denying task heterogeneity and taking two-attempt estimates at face value.")


def x10_length_dissolution():
    rows = [("pass-at-2", "d_pass_any"), ("pass rate", "d_pass_rate"),
            ("partial credit", "d_partial_credit")]
    preds = [("log expert time", "vs_log_expert"), ("expert / budget ratio", "vs_expert_budget")]
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 3.6), sharex=True)
    for ax, (pname, psuffix) in zip(axes, preds):
        ypos, yticks, ylabels = 0, [], []
        for label, metric in rows:
            for cond in ("codezen-viable", "sdd"):
                key = cond.replace("-viable", "")
                r = VN["pooled"]["correlations"][f"{key}_{metric}_{psuffix}"]
                lo, hi = fisher_ci(r["rho"], r["n"])
                ax.plot([lo, hi], [ypos, ypos], color=COLOR[cond], lw=2.2, alpha=0.5,
                        solid_capstyle="round", zorder=3)
                ax.scatter([r["rho"]], [ypos], s=58, color=COLOR[cond], zorder=4,
                           edgecolors=SURFACE, linewidths=0.9)
                ax.text(hi + 0.03, ypos, f"{r['rho']:+.2f}", va="center", fontsize=8.6,
                        color=COLOR[cond])
                ypos -= 1
            yticks.append(ypos + 1.5)
            ylabels.append(label)
            ypos -= 0.6
        ax.axvline(0, color=AXIS, lw=1.1, zorder=2)
        ax.axvline(0.526, color=CRITICAL, lw=1.0, ls=(0, (3, 3)), zorder=2)
        bare(ax, grid_axis="x")
        ax.set_yticks(yticks, ylabels, fontsize=10)
        ax.tick_params(axis="y", length=0)
        ax.set_xlim(-0.95, 0.95)
        ax.set_ylim(ypos + 0.4, 0.75)
        ax.set_xlabel("Spearman rho, condition minus baseline")
        titled(ax, "against " + pname)
    fig.legend(handles=[Line2D([], [], marker="o", lw=0, color=COLOR["codezen-viable"],
                               label="CodeZen"),
                        Line2D([], [], marker="o", lw=0, color=COLOR["sdd"], label="SDD"),
                        Line2D([], [], color=CRITICAL, lw=1.2, ls=(0, (3, 3)),
                               label="rho detectable at 80 % power, n = 26")],
               loc="upper right", ncol=3, bbox_to_anchor=(0.998, 1.07))
    fig.suptitle("The length hypothesis dissolves as the outcome metric sharpens",
                 x=0.005, ha="left", fontsize=13, fontweight="bold", color=INK, y=1.05)
    fig.tight_layout()
    save(fig, "x10-length-dissolution",
         "Metric resolution rises downward: 26 task outcomes, 52 trial outcomes, 519 graded tests. "
         "Bars: 95 % Fisher-z interval.")


def x11_adherence_length():
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.5), sharey=True)
    rng = np.random.default_rng(3)
    for ax, cond in zip(axes, ("codezen-viable", "sdd")):
        key = cond.replace("-viable", "")
        col = f"skill_calls__{cond}"
        for i, mask in enumerate([~TBL.long_horizon, TBL.long_horizon]):
            v = (TBL.loc[mask, col] * 2).dropna()
            ax.scatter(np.full(len(v), i) + rng.uniform(-0.13, 0.13, len(v)), v, s=58,
                       color=COLOR[cond], alpha=0.8, zorder=3, edgecolors=SURFACE, linewidths=0.9)
            ax.plot([i - 0.26, i + 0.26], [v.mean()] * 2, color=INK, lw=2.0, zorder=4)
            ax.text(i + 0.30, v.mean(), f"mean {v.mean():.2f}", va="center", fontsize=9.5,
                    color=INK_2)
        sp = VN["pooled"]["long_horizon"]["splits"][f"{key}_skill_calls"]
        r = VN["pooled"]["correlations"][f"{key}_skill_calls_vs_log_expert"]
        bare(ax)
        ax.set_xticks([0, 1], ["short", "long-horizon"], fontsize=10.5)
        ax.set_xlim(-0.5, 1.75)
        titled(ax, LABEL[cond],
               f"Mann-Whitney p = {sp['p']:.3f}  ·  rho vs log expert time {r['rho']:+.3f} "
               f"(p = {r['p']:.3f})")
    axes[0].set_ylabel("toolkit Skill calls per task\n(both attempts)")
    fig.suptitle("Both toolkits engage more where the hypothesis says they should pay off",
                 x=0.005, ha="left", fontsize=13, fontweight="bold", color=INK, y=1.05)
    fig.tight_layout()
    save(fig, "x11-adherence-vs-length",
         "Terminal-Bench's own long-horizon axis: expert estimate at or above four hours.")


def x12_cost_effectiveness():
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 3.5))
    for ax, metric, title, fmt in (
            (axes[0], "cost_per_pass_graded", "Spend per graded pass", "${:.2f}"),
            (axes[1], "cost_per_passed_test", "Spend per passing verifier test", "${:.3f}")):
        x, labels = 0, []
        for run in RUNS:
            for cond in CONDITIONS:
                v = VN["runs"][run]["conditions"][cond][metric]
                ax.bar(x, v, width=0.66, color=COLOR[cond], zorder=3)
                ax.text(x, v * 1.03, fmt.format(v), ha="center", va="bottom", fontsize=9.5,
                        color=INK, fontweight="bold")
                labels.append(LABEL[cond])
                x += 1
            x += 0.7
        bare(ax)
        ax.set_xticks([0, 1, 2, 3.7, 4.7, 5.7], labels, fontsize=9)
        top = ax.get_ylim()[1]
        ax.set_ylim(0, top * 1.18)
        for xc, run in ((1, "suite"), (4.7, "ceiling")):
            ax.text(xc, top * 1.11, run, ha="center", fontsize=10.5, color=INK, fontweight="bold")
        titled(ax, title)
    fig.tight_layout()
    save(fig, "x12-cost-effectiveness",
         "Left: censored trials are excluded from the pass count but not from the spend.")


def x13_screen_selection():
    p = np.linspace(0, 1, 400)
    fig, ax = plt.subplots(figsize=(8.0, 3.6))
    ax.plot(p, 1 - p, color=CRITICAL, lw=2.0, zorder=4,
            label="one-trial rule: kept if the single baseline trial fails")
    ax.plot(p, 1 - (1 - p) ** 3 - p ** 3, color=COLOR["baseline"], lw=2.0, zorder=4,
            label="three-trial two-sided rule: kept if 1 or 2 of 3 pass")
    ax.axvspan(0.20, 0.75, color=GOOD, alpha=0.10, zorder=1)
    ax.text(0.475, 1.04, "discriminating band", ha="center", fontsize=9.5, color=GOOD)
    for x0 in (0.0, 0.1, 0.5, 0.8):
        ax.scatter([x0], [1 - x0], s=46, color=CRITICAL, zorder=5, edgecolors=SURFACE,
                   linewidths=0.8)
        ax.annotate(f"{(1-x0)*100:.0f}%", (x0, 1 - x0), textcoords="offset points",
                    xytext=(6, 5), fontsize=9, color=CRITICAL)
    bare(ax)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.12)
    ax.set_xticks(np.arange(0, 1.01, 0.25), [f"{v:.0%}" for v in np.arange(0, 1.01, 0.25)])
    ax.set_yticks(np.arange(0, 1.01, 0.25), [f"{v:.0%}" for v in np.arange(0, 1.01, 0.25)])
    ax.set_xlabel("true single-attempt pass probability of the task under baseline")
    ax.set_ylabel("probability the screen keeps the task")
    titled(ax, "What a one-trial screen actually selects for",
           "the rule is monotone in the wrong quantity: it keeps hopeless tasks with certainty")
    ax.legend(loc="lower left")
    fig.tight_layout()
    save(fig, "x13-screen-selection",
         "Analytic, not measured: Bernoulli screening probabilities under each inclusion rule.")


def x14_independence():
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    lim = [0, 1.05]
    ax.plot(lim, lim, color=AXIS, lw=1.2, zorder=2)
    ax.fill_between(lim, [0, 0], lim, color=CRITICAL, alpha=0.05, zorder=1)
    ax.text(0.74, 0.26,
            "observed below prediction:\npositive within-task\ncorrelation of attempts",
            fontsize=9, color=CRITICAL, ha="center")
    for key, v in BN["independence_check"].items():
        run, cond = key.split("_", 1)
        ax.scatter([v["independence_pass_at_2"]], [v["observed_pass_at_2"]], s=95,
                   color=COLOR[cond], marker=RUN_MARK[run], zorder=4, edgecolors=SURFACE,
                   linewidths=1.0)
    bare(ax, grid_axis="both")
    ax.set_xlim(*lim)
    ax.set_ylim(*lim)
    ax.set_xlabel("pass-at-2 predicted by one common Bernoulli rate")
    ax.set_ylabel("pass-at-2 observed")
    titled(ax, "Two attempts on one task are not independent draws",
           "five of six run x condition cells fall below the prediction")
    ax.legend(handles=[Line2D([], [], marker="o", lw=0, color=MUTED, label="suite"),
                       Line2D([], [], marker="^", lw=0, color=MUTED, label="ceiling"),
                       *[Line2D([], [], marker="s", lw=0, color=COLOR[c], label=LABEL[c])
                         for c in CONDITIONS]],
              loc="upper left", ncol=2, fontsize=9)
    fig.tight_layout()
    save(fig, "x14-attempt-independence",
         "No single cell rejects homogeneity at n = 10-16 tasks; the sign is consistent across cells.")


if __name__ == "__main__":
    for fn in (x07_cost_ratio_flat, x08_censoring, x09_best_of_n, x10_length_dissolution,
               x11_adherence_length, x12_cost_effectiveness, x13_screen_selection,
               x14_independence):
        fn()
