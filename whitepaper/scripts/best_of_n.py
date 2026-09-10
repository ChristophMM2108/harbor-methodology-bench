"""Best-of-N at equal spend, with and without the independence assumption.

The Antigravity synthesis argues that repeated independent sampling dominates
methodology, using P(>=1 success in k) = 1 - (1 - p_base)^k with p_base the
pooled per-attempt pass rate. That model assumes every attempt on every task is
an independent draw from one common Bernoulli. The two-attempt data lets us
check the assumption, and it fails: observed pass-at-2 is below the independence
prediction in five of six run x condition cells, because tasks are heterogeneous
(many are dead for every attempt, a few are reliable).

Three estimators are therefore reported:

  naive       1 - (1 - p_bar)^k                        homogeneous, independent
  plug-in     mean_i [1 - (1 - p_hat_i)^k]             per-task p from 2 attempts
  beta-binom  mean over Beta(a,b) fitted to the        heterogeneity smoothed,
              per-task counts, 1 - E[(1-p)^k]          a,b by maximum likelihood

The truth lies between plug-in (which over-commits on p_hat = 0) and naive
(which denies heterogeneity entirely). Both bounds are quoted in the paper.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize, special, stats

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "whitepaper" / "data"
CONDITIONS = ["baseline", "codezen-viable", "sdd"]
RNG = np.random.default_rng(20260904)


def counts(run: str, cond: str) -> tuple[np.ndarray, np.ndarray]:
    """Successes and attempts per task for one run x condition cell."""
    t = pd.read_csv(REPO / f"results/analysis-{run}/data/trials.csv")
    t["success"] = t.success.fillna(False).astype(int)
    g = t[t.condition == cond].groupby("task").success.agg(["sum", "size"])
    return g["sum"].to_numpy(), g["size"].to_numpy()


def naive(y, n, k):
    p = y.sum() / n.sum()
    return 1 - (1 - p) ** k


def plugin(y, n, k):
    p = y / n
    return float(np.mean(1 - (1 - p) ** k))


def beta_binom_fit(y, n):
    """MLE of Beta(a, b) for a beta-binomial with per-task counts (y, n)."""
    def nll(theta):
        a, b = np.exp(theta)
        return -np.sum(
            special.gammaln(n + 1) - special.gammaln(y + 1) - special.gammaln(n - y + 1)
            + special.betaln(y + a, n - y + b) - special.betaln(a, b))
    best, best_val = None, np.inf
    for start in ((0.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (-2.0, -2.0)):
        r = optimize.minimize(nll, np.array(start), method="Nelder-Mead")
        if r.fun < best_val:
            best, best_val = r.x, r.fun
    return float(np.exp(best[0])), float(np.exp(best[1]))


def beta_binom_pred(y, n, k, n_draw=200_000):
    a, b = beta_binom_fit(y, n)
    p = RNG.beta(a, b, n_draw)
    return float(np.mean(1 - (1 - p) ** k)), a, b


def boot_ci(fn, y, n, k, reps=4000):
    idx = np.arange(len(y))
    vals = [fn(y[s], n[s], k) for s in (RNG.choice(idx, len(idx), replace=True) for _ in range(reps))]
    return [round(float(np.percentile(vals, 2.5)), 4), round(float(np.percentile(vals, 97.5)), 4)]


out: dict = {"independence_check": {}, "equal_spend": {}}

for run in ("suite", "ceiling"):
    for cond in CONDITIONS:
        y, n = counts(run, cond)
        p_bar = y.sum() / n.sum()
        obs_at2, obs_both = float(np.mean(y >= 1)), float(np.mean(y == n))
        # exact test of the homogeneous-Bernoulli model against the observed
        # distribution of per-task success counts
        exp_counts = [len(y) * stats.binom.pmf(j, 2, p_bar) for j in (0, 1, 2)]
        obs_counts = [int((y == j).sum()) for j in (0, 1, 2)]
        chi2 = sum((o - e) ** 2 / e for o, e in zip(obs_counts, exp_counts) if e > 0)
        out["independence_check"][f"{run}_{cond}"] = {
            "p_per_attempt": round(float(p_bar), 4),
            "observed_pass_at_2": round(obs_at2, 4),
            "independence_pass_at_2": round(float(1 - (1 - p_bar) ** 2), 4),
            "observed_pass_both": round(obs_both, 4),
            "independence_pass_both": round(float(p_bar ** 2), 4),
            "observed_counts_0_1_2": obs_counts,
            "expected_counts_0_1_2": [round(e, 2) for e in exp_counts],
            "chi2_df2": round(float(chi2), 3),
            "chi2_p": round(float(stats.chi2.sf(chi2, 2)), 4),
        }

for run in ("suite", "ceiling"):
    trials = pd.read_csv(REPO / f"results/analysis-{run}/data/trials.csv")
    cost = trials.groupby("condition").cost_usd.mean()
    yb, nb = counts(run, "baseline")
    row: dict = {}
    for cond in ("codezen-viable", "sdd"):
        k = float(cost[cond] / cost["baseline"])
        bb, a, b = beta_binom_pred(yb, nb, k)
        y_c, n_c = counts(run, cond)
        row[cond] = {
            "k_equal_spend": round(k, 3),
            "baseline_p_per_attempt": round(float(yb.sum() / nb.sum()), 4),
            "baseline_best_of_k_naive": round(float(naive(yb, nb, k)), 4),
            "baseline_best_of_k_naive_ci": boot_ci(naive, yb, nb, k),
            "baseline_best_of_k_plugin": round(plugin(yb, nb, k), 4),
            "baseline_best_of_k_plugin_ci": boot_ci(plugin, yb, nb, k),
            "baseline_best_of_k_betabinom": round(bb, 4),
            "betabinom_a": round(a, 3), "betabinom_b": round(b, 3),
            "condition_p_per_attempt": round(float(y_c.sum() / n_c.sum()), 4),
            "condition_pass_at_2": round(float(np.mean(y_c >= 1)), 4),
        }
        # the honest comparison: the condition gets its 2 attempts, baseline gets
        # 2k attempts for the same money
        k2 = 2 * k
        row[cond]["baseline_best_of_2k_plugin"] = round(plugin(yb, nb, k2), 4)
        row[cond]["baseline_best_of_2k_naive"] = round(float(naive(yb, nb, k2)), 4)
        row[cond]["baseline_best_of_2k_betabinom"] = round(beta_binom_pred(yb, nb, k2)[0], 4)
    out["equal_spend"][run] = row

path = OUT / "best_of_n.json"
path.write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
print(f"\nwrote {path}")
