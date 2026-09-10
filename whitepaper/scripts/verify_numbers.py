"""Recompute every number quoted in the whitepaper from the exported analysis CSVs.

Reads   results/analysis-{suite,ceiling}/data/*.csv
Writes  whitepaper/data/verified_numbers.json
        whitepaper/data/verification_log.md

Nothing here reads the discussion documents; the log compares the recomputed
values against the values those documents claim, which are listed in CLAIMS
below, so a disagreement between a source document and the data surfaces as a
row in the log rather than silently entering the paper.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "whitepaper" / "data"
OUT.mkdir(parents=True, exist_ok=True)

RUNS = {"suite": REPO / "results/analysis-suite/data",
        "ceiling": REPO / "results/analysis-ceiling/data"}
CONDITIONS = ["baseline", "codezen-viable", "sdd"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p, denom = k / n, 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def load(run):
    d = RUNS[run]
    trials = pd.read_csv(d / "trials.csv")
    tests = pd.read_csv(d / "tests.csv")
    trials["censored"] = trials.agent_timeout.fillna(False) | trials.verifier_timeout.fillna(False)
    # bool -> int so that differences and means are arithmetic, not logical
    for col in ("success", "agent_timeout", "verifier_timeout", "wrote_test_file"):
        trials[col] = trials[col].fillna(False).astype(int)
    return trials, tests



def test_rate_clustered(tsub, reps: int = 20000, seed: int = 20260909):
    """Test-level pass rate with a task-clustered bootstrap interval.

    Individual verifier tests are not independent draws: they share a task, a
    verifier and a workspace, so the naive binomial interval on 357 test rows
    understates the uncertainty by the design effect computed here.
    """
    ok = (tsub.status == "passed").astype(int)
    n = len(ok)
    if n == 0:
        return {"wilson_naive": None, "cluster_ci": None,
                "design_effect": None, "effective_n": None}
    p = float(ok.mean())
    se_naive = (p * (1 - p) / n) ** 0.5
    groups = [g.values for _, g in ok.groupby(tsub.task)]
    rng = np.random.default_rng(seed)
    draws = np.empty(reps)
    for i in range(reps):
        pick = rng.integers(0, len(groups), len(groups))
        draws[i] = np.concatenate([groups[j] for j in pick]).mean()
    se_cluster = float(draws.std(ddof=1))
    lo, hi = (float(v) for v in np.percentile(draws, [2.5, 97.5]))
    deff = (se_cluster / se_naive) ** 2 if se_naive > 0 else None
    return {
        "wilson_naive": [round(v, 4) for v in wilson(int(ok.sum()), n)],
        "cluster_ci": [round(lo, 4), round(hi, 4)],
        "design_effect": round(deff, 2) if deff else None,
        "effective_n": round(n / deff, 1) if deff else None,
    }


results: dict = {"runs": {}, "pooled": {}}

# ---------------------------------------------------------------- per-run ----
for run in RUNS:
    trials, tests = load(run)
    r: dict = {}
    r["n_trials"] = int(len(trials))
    r["n_tasks"] = int(trials.task.nunique())
    r["attempts"] = int(len(trials) / trials.task.nunique() / trials.condition.nunique())
    r["spend"] = round(float(trials.cost_usd.sum()), 2)
    r["agent_hours"] = round(float(trials.agent_sec.sum() / 3600), 1)
    r["conditions"] = {}

    for c in CONDITIONS:
        sub = trials[trials.condition == c]
        graded = sub[~sub.censored]
        tsub = tests[tests.condition == c]
        n_pass_all = int(sub.success.sum())
        n_pass_graded = int(graded.success.sum())
        n_cens_pass = int(sub[sub.censored].success.sum())
        tcl = test_rate_clustered(tsub)
        r["conditions"][c] = {
            "trials": int(len(sub)),
            "censored": int(sub.censored.sum()),
            "graded": int(len(graded)),
            "passed_graded": n_pass_graded,
            "passed_all": n_pass_all,
            # convention 1 -- censored: dropped from numerator and denominator
            "success_rate_graded": round(n_pass_graded / len(graded), 4),
            "wilson_graded": [round(v, 4) for v in wilson(n_pass_graded, len(graded))],
            # convention 2 -- timeout = failure: every trial in the denominator, and a
            # censored trial counts against its condition whatever was on disk. The
            # numerator is therefore the graded passes only.
            "success_rate_timeout_fail": round(n_pass_graded / len(sub), 4),
            "wilson_timeout_fail": [round(v, 4) for v in wilson(n_pass_graded, len(sub))],
            # convention 3 -- graded at the kill: every trial in the denominator, and a
            # censored trial keeps the reward the verifier actually assigned it.
            "success_rate_kill_graded": round(n_pass_all / len(sub), 4),
            "wilson_kill_graded": [round(v, 4) for v in wilson(n_pass_all, len(sub))],
            "censored_with_reward_1": n_cens_pass,
            # pandas skips NaN, so this is a mean over the trials that have per-test
            # records; one suite baseline trial has none, and both readings are kept
            "partial_credit": round(float(sub.partial_credit.mean()), 4),
            "partial_credit_n": int(sub.partial_credit.notna().sum()),
            "partial_credit_missing": int(sub.partial_credit.isna().sum()),
            "partial_credit_missing_as_zero": round(float(sub.partial_credit.fillna(0).mean()), 4),
            "tests_total": int(len(tsub)),
            "tests_passed": int((tsub.status == "passed").sum()),
            "test_pass_rate": round(float((tsub.status == "passed").mean()), 4),
            # test-level observations are clustered within tasks, so the binomial
            # interval on them is far too narrow; these are the clustered versions
            "test_pass_rate_wilson_naive": tcl["wilson_naive"],
            "test_pass_rate_cluster_ci": tcl["cluster_ci"],
            "test_pass_rate_design_effect": tcl["design_effect"],
            "test_pass_rate_effective_n": tcl["effective_n"],
            "cost_total": round(float(sub.cost_usd.sum()), 2),
            "cost_per_trial": round(float(sub.cost_usd.mean()), 4),
            "cost_per_pass_graded": round(float(sub.cost_usd.sum() / n_pass_graded), 2) if n_pass_graded else None,
            "cost_per_passed_test": round(float(sub.cost_usd.sum() / max((tsub.status == "passed").sum(), 1)), 4),
            "agent_sec": round(float(sub.agent_sec.mean()), 1),
            "budget_used": round(float(sub.budget_used.mean()), 4),
            "budget_used_median": round(float(sub.budget_used.median()), 4),
            "over_75pct_budget": int((sub.budget_used > 0.75).sum()),
            "output_tokens": round(float(sub.output_tokens.mean()), 1),
            "thinking_tokens": round(float(sub.thinking_tokens.mean()), 1),
            "steps": round(float(sub.n_steps.mean()), 2),
            "tool_calls": round(float(sub.n_tool_calls.mean()), 2),
            "edits": round(float(sub.n_edits_total.mean()), 2),
            "bash_test": round(float(sub.bash_test.mean()), 3),
            "reads": round(float(sub.n_read.mean()), 2),
            "subagents": round(float(sub.n_agent_spawns.mean()), 3),
            "error_rate": round(float(sub.error_rate.mean()), 4),
            "cache_hit_ratio": round(float(sub.cache_hit_ratio.mean()), 4),
            "thinking_share": round(float(sub.thinking_share.mean()), 4),
            "agent_timeouts": int(sub.agent_timeout.sum()),
            "verifier_timeouts": int(sub.verifier_timeout.sum()),
            "trials_invoking_skill": int((sub.n_toolkit_skill_calls > 0).sum()),
            "toolkit_skill_calls": int(sub.n_toolkit_skill_calls.sum()),
            "wrote_test_file_share": round(float(sub.wrote_test_file.mean()), 4),
            "named_instruction_file": int(sub.config_markers.fillna("").ne("").sum()),
            "opened_instruction_file": int((sub.n_config_reads > 0).sum()),
            "skills_shipped": int(sub.n_toolkit_skills.max()),
            "skills_registered": int(sub.n_toolkit_skills_registered.max()),
        }

    # outcome matrices, both aggregations
    pa2 = trials.pivot_table(index="task", columns="condition", values="success", aggfunc="max")[CONDITIONS]
    pboth = (trials.pivot_table(index="task", columns="condition", values="success", aggfunc="mean")[CONDITIONS] == 1).astype(int)
    for name, mat in (("pass_at_2", pa2), ("pass_both", pboth)):
        m = mat.astype(int)
        r[name] = {
            "per_condition": {c: int(m[c].sum()) for c in CONDITIONS},
            "all_pass": int((m.sum(axis=1) == 3).sum()),
            "all_fail": int((m.sum(axis=1) == 0).sum()),
            "split": int(((m.sum(axis=1) > 0) & (m.sum(axis=1) < 3)).sum()),
            "split_tasks": sorted(m.index[(m.sum(axis=1) > 0) & (m.sum(axis=1) < 3)]),
            "all_fail_tasks": sorted(m.index[m.sum(axis=1) == 0]),
            "all_pass_tasks": sorted(m.index[m.sum(axis=1) == 3]),
            "mcnemar": {},
            "regressions": {},
        }
        for other in CONDITIONS[1:]:
            only_base = int(((m.baseline == 1) & (m[other] == 0)).sum())
            only_other = int(((m.baseline == 0) & (m[other] == 1)).sum())
            n_disc = only_base + only_other
            p = stats.binomtest(only_other, n_disc, 0.5).pvalue if n_disc else 1.0
            r[name]["mcnemar"][other] = {"discordant": n_disc, "only_baseline": only_base,
                                         "only_other": only_other, "p": round(float(p), 4)}
            r[name]["regressions"][other] = sorted(m.index[(m.baseline == 1) & (m[other] == 0)])
        # spend carried by concordant tasks
        conc = set(m.index) - set(r[name]["split_tasks"])
        r[name]["concordant_spend"] = round(float(trials[trials.task.isin(conc)].cost_usd.sum()), 2)

    # paired Wilcoxon on continuous metrics
    r["paired"] = {}
    metrics = ["cost_usd", "agent_sec", "output_tokens", "thinking_tokens", "n_steps",
               "n_tool_calls", "budget_used", "partial_credit", "n_agent_spawns",
               "cache_hit_ratio", "bash_test"]
    for metric in metrics:
        pv = trials.pivot_table(index="task", columns="condition", values=metric, aggfunc="mean")
        for other in CONDITIONS[1:]:
            sub = pv[["baseline", other]].dropna()
            if len(sub) < 3:
                continue
            delta = sub[other] - sub["baseline"]
            try:
                p = float(stats.wilcoxon(sub[other], sub["baseline"]).pvalue)
            except ValueError:          # all-zero differences
                p = 1.0
            r["paired"].setdefault(metric, {})[other] = {
                "n_pairs": int(len(sub)),
                "median_delta": round(float(delta.median()), 4),
                "mean_delta": round(float(delta.mean()), 4),
                "ratio_of_totals": round(float(sub[other].sum() / sub["baseline"].sum()), 4),
                "higher_on": int((delta > 0).sum()),
                "lower_on": int((delta < 0).sum()),
                "p": round(p, 4),
            }

    # censored trials, with what was on disk at the kill
    cens = trials[trials.censored][["task", "condition", "trial_name", "reward", "success",
                                    "partial_credit", "budget_used", "cost_usd",
                                    "tests_passed", "tests_total", "skill_call_sequence"]]
    r["censored_trials"] = json.loads(cens.round(3).to_json(orient="records"))
    # per-task cost ratio extremes
    cost_pt = trials.pivot_table(index="task", columns="condition", values="cost_usd", aggfunc="mean")
    ratio = (cost_pt["codezen-viable"] / cost_pt["baseline"]).sort_values()
    r["codezen_cost_ratio_per_task"] = {k: round(float(v), 3) for k, v in ratio.items()}
    results["runs"][run] = r

# ----------------------------------------------------------------- pooled ----
frames = []
for run in RUNS:
    t, _ = load(run)
    t["run"] = run
    frames.append(t)
pool = pd.concat(frames, ignore_index=True)
pool["long_horizon"] = pool["axes"].fillna("").str.contains("long-horizon")
pool["expert_budget_ratio"] = pool["expert_min"] / (pool["budget_sec"] / 60.0)

P: dict = {}
P["n_trials"] = int(len(pool))
P["n_tasks"] = int(pool.task.nunique())
P["spend"] = round(float(pool.cost_usd.sum()), 2)
P["agent_hours"] = round(float(pool.agent_sec.sum() / 3600), 1)
P["conditions"] = {}
for c in CONDITIONS:
    sub = pool[pool.condition == c]
    P["conditions"][c] = {
        "cost_per_trial": round(float(sub.cost_usd.mean()), 4),
        "timeouts": int(sub.agent_timeout.sum()),
        "timeout_share": round(float(sub.agent_timeout.mean()), 4),
        "trials": int(len(sub)),
        "subagents": round(float(sub.n_agent_spawns.mean()), 3),
    }

# per task x condition aggregate, then difference against baseline
agg = (pool.groupby(["run", "task", "condition"], observed=True)
       .agg(pass_any=("success", "max"), pass_rate=("success", "mean"),
            partial_credit=("partial_credit", "mean"), cost=("cost_usd", "mean"),
            budget=("budget_used", "mean"), timeouts=("agent_timeout", "sum"),
            skill_calls=("n_toolkit_skill_calls", "mean"),
            expert_min=("expert_min", "first"), budget_sec=("budget_sec", "first"),
            instruction_words=("instruction_words", "first"),
            long_horizon=("long_horizon", "first"),
            expert_budget_ratio=("expert_budget_ratio", "first"))
       .reset_index())
wide = agg.pivot(index=["run", "task"], columns="condition")
task_meta = agg.groupby(["run", "task"]).first()[["expert_min", "budget_sec", "instruction_words",
                                                  "long_horizon", "expert_budget_ratio"]]
tbl = task_meta.copy()
tbl["log_expert"] = np.log10(tbl.expert_min)
for c in CONDITIONS:
    for m in ("pass_any", "pass_rate", "partial_credit", "cost", "budget", "timeouts", "skill_calls"):
        tbl[f"{m}__{c}"] = wide[(m, c)]
for c in CONDITIONS[1:]:
    for m in ("pass_any", "pass_rate", "partial_credit"):
        tbl[f"d_{m}__{c}"] = tbl[f"{m}__{c}"] - tbl[f"{m}__baseline"]
    tbl[f"cost_ratio__{c}"] = tbl[f"cost__{c}"] / tbl["cost__baseline"]
    tbl[f"cost_delta__{c}"] = tbl[f"cost__{c}"] - tbl["cost__baseline"]
tbl.round(4).to_csv(OUT / "pooled_task_table.csv")


def rho(x, y):
    ok = x.notna() & y.notna()
    if ok.sum() < 4:
        return {"rho": None, "p": None, "n": int(ok.sum())}
    r_, p_ = stats.spearmanr(x[ok], y[ok])
    return {"rho": round(float(r_), 4), "p": round(float(p_), 4), "n": int(ok.sum())}


P["correlations"] = {}
P["correlations"]["baseline_pass_vs_expert"] = rho(tbl.pass_any__baseline, tbl.log_expert)
P["correlations"]["baseline_cost_vs_expert"] = rho(tbl.cost__baseline, tbl.log_expert)
for c in CONDITIONS[1:]:
    key = c.replace("-viable", "")
    P["correlations"][f"{key}_cost_ratio_vs_log_expert"] = rho(tbl[f"cost_ratio__{c}"], tbl.log_expert)
    P["correlations"][f"{key}_cost_ratio_vs_budget_sec"] = rho(tbl[f"cost_ratio__{c}"], tbl.budget_sec)
    P["correlations"][f"{key}_cost_ratio_vs_instruction_words"] = rho(tbl[f"cost_ratio__{c}"], tbl.instruction_words)
    P["correlations"][f"{key}_cost_delta_vs_log_expert"] = rho(tbl[f"cost_delta__{c}"], tbl.log_expert)
    P["correlations"][f"{key}_timeouts_vs_expert_budget"] = rho(tbl[f"timeouts__{c}"], tbl.expert_budget_ratio)
    P["correlations"][f"{key}_skill_calls_vs_log_expert"] = rho(tbl[f"skill_calls__{c}"], tbl.log_expert)
    for m in ("pass_any", "pass_rate", "partial_credit"):
        P["correlations"][f"{key}_d_{m}_vs_log_expert"] = rho(tbl[f"d_{m}__{c}"], tbl.log_expert)
        P["correlations"][f"{key}_d_{m}_vs_expert_budget"] = rho(tbl[f"d_{m}__{c}"], tbl.expert_budget_ratio)

# long-horizon axis split, Mann-Whitney
P["long_horizon"] = {"n_long": int(tbl.long_horizon.sum()), "n_short": int((~tbl.long_horizon).sum()),
                     "splits": {}}
for c in CONDITIONS[1:]:
    key = c.replace("-viable", "")
    for m in ("d_pass_any", "d_pass_rate", "d_partial_credit", "cost_ratio", "skill_calls"):
        col = f"{m}__{c}" if m != "skill_calls" else f"skill_calls__{c}"
        long_, short_ = tbl.loc[tbl.long_horizon, col].dropna(), tbl.loc[~tbl.long_horizon, col].dropna()
        if len(long_) < 2 or len(short_) < 2:
            continue
        try:
            p = float(stats.mannwhitneyu(long_, short_, alternative="two-sided").pvalue)
        except ValueError:
            p = 1.0
        P["long_horizon"]["splits"][f"{key}_{m}"] = {
            "long_mean": round(float(long_.mean()), 4), "short_mean": round(float(short_.mean()), 4),
            "p": round(p, 4)}

# CodeZen absolute overhead, short vs long budget
short_b = tbl.budget_sec <= 900
P["cost_delta_by_budget"] = {}
for c in CONDITIONS[1:]:
    key = c.replace("-viable", "")
    P["cost_delta_by_budget"][key] = {
        "short_budget_mean_delta": round(float(tbl.loc[short_b, f"cost_delta__{c}"].mean()), 4),
        "long_budget_mean_delta": round(float(tbl.loc[~short_b, f"cost_delta__{c}"].mean()), 4),
        "n_short": int(short_b.sum()), "n_long": int((~short_b).sum())}

# skill-invoking vs non-invoking trials, pooled
inv = pool[pool.n_toolkit_skill_calls > 0]
non = pool[(pool.n_toolkit_skill_calls == 0)]
P["skill_use"] = {
    "toolkit_trials": int((pool.condition != "baseline").sum()),
    "invoking": int(len(inv)),
    "invoking_share_of_toolkit": round(float(len(inv) / (pool.condition != "baseline").sum()), 4),
    "invoking_pass_rate": round(float(inv.success.mean()), 4),
    "non_invoking_pass_rate": round(float(non.success.mean()), 4),
    "non_invoking_pass_rate_toolkit_only": round(
        float(non[non.condition != "baseline"].success.mean()), 4),
}

# best-of-N at equal spend
P["best_of_n"] = {}
for run in RUNS:
    r = results["runs"][run]
    base, cz = r["conditions"]["baseline"], r["conditions"]["codezen-viable"]
    k = cz["cost_per_trial"] / base["cost_per_trial"]
    for label, key in (("graded", "success_rate_graded"),
                       ("kill_graded", "success_rate_kill_graded"),
                       ("timeout_fail", "success_rate_timeout_fail")):
        p_base = base[key]
        P["best_of_n"][f"{run}_{label}"] = {
            "k": round(k, 3),
            "p_base": p_base,
            "p_best_of_k": round(1 - (1 - p_base) ** k, 4),
            "p_codezen": cz[key],
            "delta_points": round((1 - (1 - p_base) ** k - cz[key]) * 100, 1),
        }

# censored trials that had already earned reward 1.0
P["censored"] = {
    "total": int(pool.agent_timeout.sum() + pool.verifier_timeout.sum()),
    "with_reward_1": int(pool[pool.censored].success.sum()),
    "by_condition": {c: {"censored": int(pool[(pool.condition == c)].censored.sum()),
                         "reward_1": int(pool[(pool.condition == c) & pool.censored].success.sum())}
                     for c in CONDITIONS},
}

# power: minimum detectable rho at 80 % power, two-sided alpha .05, Fisher z
def min_rho(n, power=0.80, alpha=0.05):
    from scipy.stats import norm
    z = (norm.ppf(1 - alpha / 2) + norm.ppf(power)) / np.sqrt(n - 3)
    return round(float(np.tanh(z)), 3)


P["power"] = {f"min_detectable_rho_n{n}": min_rho(n) for n in (10, 16, 26)}
results["pooled"] = P

(OUT / "verified_numbers.json").write_text(json.dumps(results, indent=1, default=str))
print(f"wrote {OUT/'verified_numbers.json'}  ({(OUT/'verified_numbers.json').stat().st_size/1024:.0f} KB)")
print(f"wrote {OUT/'pooled_task_table.csv'}")
