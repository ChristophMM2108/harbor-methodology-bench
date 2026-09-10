"""Emit LaTeX table fragments into whitepaper/tables/ from the verified numbers.

Every table the paper prints is generated here, so no figure in the text is
hand-transcribed from the source discussions.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "whitepaper" / "tables"
OUT.mkdir(parents=True, exist_ok=True)
VN = json.loads((REPO / "whitepaper/data/verified_numbers.json").read_text())
BN = json.loads((REPO / "whitepaper/data/best_of_n.json").read_text())
TBL = pd.read_csv(REPO / "whitepaper/data/pooled_task_table.csv")
CONDS = ["baseline", "codezen-viable", "sdd"]
LAB = {"baseline": "baseline", "codezen-viable": "CodeZen", "sdd": "SDD"}
RUNS = ("suite", "ceiling")


def w(name, body):
    (OUT / f"{name}.tex").write_text(body.rstrip() + "\n")
    print(f"  tables/{name}.tex")


def esc(s):
    return str(s).replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def p_fmt(p):
    if p is None:
        return "--"
    txt = "$<$0.001" if p < 0.001 else f"{p:.3f}"
    return r"\textbf{" + txt + "}" if p < 0.05 else txt


# --- t02 the two populations ------------------------------------------------
r_s, r_c = VN["runs"]["suite"], VN["runs"]["ceiling"]
w("t02-populations", rf"""
\begin{{tabular}}{{@{{}}lrr@{{}}}}
\toprule
 & \textbf{{suite}} & \textbf{{ceiling}} \\
\midrule
Inclusion rule & bare agent must fail & bare agent already passes \\
Tasks $\times$ conditions $\times$ attempts & $16\times3\times2$ & $10\times3\times2$ \\
Trials & {r_s['n_trials']} & {r_c['n_trials']} \\
Model spend & \${r_s['spend']:.2f} & \${r_c['spend']:.2f} \\
Agent wall-clock & {r_s['agent_hours']}\,h & {r_c['agent_hours']}\,h \\
Baseline pass-at-2 & {r_s['pass_at_2']['per_condition']['baseline']}/16 = {100*r_s['pass_at_2']['per_condition']['baseline']/16:.1f}\% & {r_c['pass_at_2']['per_condition']['baseline']}/10 = {100*r_c['pass_at_2']['per_condition']['baseline']/10:.1f}\% \\
Concordant tasks (pass-at-2) & {r_s['pass_at_2']['all_pass']+r_s['pass_at_2']['all_fail']}/16 & {r_c['pass_at_2']['all_pass']+r_c['pass_at_2']['all_fail']}/10 \\
\quad all three pass / all three fail & {r_s['pass_at_2']['all_pass']} / {r_s['pass_at_2']['all_fail']} & {r_c['pass_at_2']['all_pass']} / {r_c['pass_at_2']['all_fail']} \\
Spend on concordant tasks & \${r_s['pass_at_2']['concordant_spend']:.2f} ({100*r_s['pass_at_2']['concordant_spend']/r_s['spend']:.0f}\%) & \${r_c['pass_at_2']['concordant_spend']:.2f} ({100*r_c['pass_at_2']['concordant_spend']/r_c['spend']:.0f}\%) \\
Effective $n$ per pairwise test & {min(v['discordant'] for v in r_s['pass_at_2']['mcnemar'].values())}--{max(v['discordant'] for v in r_s['pass_at_2']['mcnemar'].values())} & {min(v['discordant'] for v in r_c['pass_at_2']['mcnemar'].values())}--{max(v['discordant'] for v in r_c['pass_at_2']['mcnemar'].values())} \\
Design defect & floor effect & ceiling, by construction \\
Intended endpoint & outcome & cost and regression \\
\bottomrule
\end{{tabular}}
""")


# --- t03/t04 outcome per run ------------------------------------------------
for run in RUNS:
    r = VN["runs"][run]
    rows = []
    for c in CONDS:
        v = r["conditions"][c]
        lo, hi = v["wilson_graded"]
        rows.append(
            rf"{LAB[c]} & {v['censored']} & {v['graded']} & {v['passed_graded']} & "
            rf"{100*v['success_rate_graded']:.1f}\% & [{100*lo:.1f}, {100*hi:.1f}] & "
            rf"{100*v['success_rate_timeout_fail']:.1f}\% & "
            rf"{100*v['success_rate_kill_graded']:.1f}\% & {v['partial_credit']:.3f} & "
            rf"{100*v['test_pass_rate']:.1f}\% & \${v['cost_total']:.2f} \\")
    w(f"t03-outcome-{run}", r"""
\begin{tabular}{@{}lrrrrcrrrrr@{}}
\toprule
 & & & & \multicolumn{2}{c}{\textbf{1.} censored} & \multicolumn{1}{c}{\textbf{2.} t/o} &
 \multicolumn{1}{c}{\textbf{3.} graded} & & & \\
\cmidrule(lr){5-6}\cmidrule(lr){7-7}\cmidrule(lr){8-8}
 & \multicolumn{1}{c}{cens.} & \multicolumn{1}{c}{graded} &
 \multicolumn{1}{c}{passed} & \multicolumn{1}{c}{rate} & \multicolumn{1}{c}{95\,\% Wilson} &
 \multicolumn{1}{c}{$=$ fail} & \multicolumn{1}{c}{at kill} &
 \multicolumn{1}{c}{part.\ credit} &
 \multicolumn{1}{c}{test rate} & \multicolumn{1}{c}{spend} \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
""")


# --- t05/t06 paired tests ---------------------------------------------------
METRIC_LABEL = {"cost_usd": "cost (\\$)", "budget_used": "budget consumed",
                "agent_sec": "agent wall-clock", "output_tokens": "output tokens",
                "thinking_tokens": "thinking tokens", "n_tool_calls": "tool calls",
                "n_steps": "agent steps", "n_agent_spawns": "sub-agents spawned",
                "partial_credit": "partial credit", "cache_hit_ratio": "cache hit ratio",
                "bash_test": "verification commands"}
ORDER = ["cost_usd", "budget_used", "agent_sec", "output_tokens", "thinking_tokens",
         "n_tool_calls", "n_steps", "n_agent_spawns", "bash_test", "cache_hit_ratio",
         "partial_credit"]
for run in RUNS:
    r = VN["runs"][run]["paired"]
    n = VN["runs"][run]["n_tasks"]
    rows = []
    for m in ORDER:
        if m not in r:
            continue
        cz, sd = r[m]["codezen-viable"], r[m]["sdd"]
        rows.append(
            rf"{METRIC_LABEL[m]} & {cz['ratio_of_totals']:.3f} & {cz['higher_on']}/{n} & {p_fmt(cz['p'])} & "
            rf"{sd['ratio_of_totals']:.3f} & {sd['higher_on']}/{n} & {p_fmt(sd['p'])} \\")
    w(f"t05-paired-{run}", r"""
\begin{tabular}{@{}lrcrrcr@{}}
\toprule
 & \multicolumn{3}{c}{CodeZen vs baseline} & \multicolumn{3}{c}{SDD vs baseline} \\
\cmidrule(lr){2-4}\cmidrule(lr){5-7}
metric & ratio & higher on & \multicolumn{1}{c}{$p$} & ratio & higher on & \multicolumn{1}{c}{$p$} \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
""")


# --- t07 behaviour ----------------------------------------------------------
BEH = [("steps", "agent steps", "{:.1f}"), ("tool_calls", "tool calls", "{:.1f}"),
       ("edits", "file edits / writes", "{:.2f}"), ("bash_test", "verification commands", "{:.2f}"),
       ("subagents", "sub-agents spawned", "{:.2f}"), ("reads", "file reads", "{:.2f}"),
       ("wrote_test_file_share", "wrote a test file", "{:.1%}"),
       ("error_rate", "tool results with an error", "{:.1%}"),
       ("cache_hit_ratio", "cache hit ratio", "{:.1%}"),
       ("thinking_share", "thinking share of output", "{:.1%}")]
rows = []
for key, label, fmt in BEH:
    cells = []
    for run in RUNS:
        for c in CONDS:
            v = VN["runs"][run]["conditions"][c][key]
            cells.append(fmt.format(v).replace("%", r"\%"))
    rows.append(f"{label} & " + " & ".join(cells) + r" \\")
w("t07-behaviour", r"""
\begin{tabular}{@{}lrrrrrr@{}}
\toprule
 & \multicolumn{3}{c}{\textbf{suite}} & \multicolumn{3}{c}{\textbf{ceiling}} \\
\cmidrule(lr){2-4}\cmidrule(lr){5-7}
per-trial mean & baseline & CodeZen & SDD & baseline & CodeZen & SDD \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
""")


# --- t08 adherence ----------------------------------------------------------
AD = [("skills_shipped", "skills shipped"), ("skills_registered", "registered by the CLI"),
      ("named_instruction_file", "named an instruction file in its output"),
      ("opened_instruction_file", "opened one with \\texttt{Read} or \\texttt{cat}"),
      ("trials_invoking_skill", "invoked a toolkit skill"),
      ("toolkit_skill_calls", "toolkit \\texttt{Skill} calls in total")]
rows = []
for key, label in AD:
    cells = [str(VN["runs"][run]["conditions"][c][key]) for run in RUNS for c in CONDS]
    rows.append(f"{label} & " + " & ".join(cells) + r" \\")
w("t08-adherence", r"""
\begin{tabular}{@{}lrrrrrr@{}}
\toprule
 & \multicolumn{3}{c}{\textbf{suite} (32 trials each)} & \multicolumn{3}{c}{\textbf{ceiling} (20 trials each)} \\
\cmidrule(lr){2-4}\cmidrule(lr){5-7}
 & baseline & CodeZen & SDD & baseline & CodeZen & SDD \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
""")


# --- t09 every skill-invoking trial ----------------------------------------
rows = []
for run in RUNS:
    t = pd.read_csv(REPO / f"results/analysis-{run}/data/trials.csv")
    t["success"] = t.success.fillna(False).astype(int)
    sub = t[t.n_toolkit_skill_calls > 0].sort_values(["condition", "task"])
    for _, x in sub.iterrows():
        seq = esc(x.skill_call_sequence).replace(";", ", ")
        outcome = "pass" if x.success else "fail"
        if x.agent_timeout:
            outcome += ", censored"
        rows.append(rf"{run} & {esc(x.task)} & {LAB[x.condition]} & \texttt{{\footnotesize {seq}}} & "
                    rf"{x.n_agent_spawns:.0f} & {x.reward:.1f} & {100*x.budget_used:.0f}\% & "
                    rf"\${x.cost_usd:.2f} & {outcome} \\")
w("t09-skill-trials", r"""
\begin{tabular}{@{}llllrrrrl@{}}
\toprule
run & task & condition & skills invoked, in order & sub & reward & budget & cost & outcome \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
""")


# --- t10 cost effectiveness -------------------------------------------------
rows = []
for run in RUNS:
    for c in CONDS:
        v = VN["runs"][run]["conditions"][c]
        rows.append(rf"{run} & {LAB[c]} & {v['passed_graded']} & \${v['cost_total']:.2f} & "
                    rf"\${v['cost_per_pass_graded']:.2f} & {v['tests_passed']} & "
                    rf"\${v['cost_per_passed_test']:.3f} \\")
w("t10-cost-effectiveness", r"""
\begin{tabular}{@{}llrrrrr@{}}
\toprule
run & condition & graded passes & spend & spend per pass & passing tests & spend per passing test \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
""")


# --- t11 length correlations ------------------------------------------------
CORR = [("baseline_pass_vs_expert", "baseline pass-at-2 vs log expert time"),
        ("baseline_cost_vs_expert", "baseline absolute cost vs log expert time"),
        ("codezen_cost_ratio_vs_log_expert", "CodeZen cost \\emph{ratio} vs log expert time"),
        ("sdd_cost_ratio_vs_log_expert", "SDD cost \\emph{ratio} vs log expert time"),
        ("codezen_cost_ratio_vs_budget_sec", "CodeZen cost ratio vs declared budget"),
        ("codezen_cost_ratio_vs_instruction_words", "CodeZen cost ratio vs instruction words"),
        ("codezen_cost_delta_vs_log_expert", "CodeZen absolute overhead vs log expert time"),
        ("sdd_cost_delta_vs_log_expert", "SDD absolute overhead vs log expert time"),
        ("codezen_timeouts_vs_expert_budget", "CodeZen timeouts vs expert/budget ratio"),
        ("sdd_timeouts_vs_expert_budget", "SDD timeouts vs expert/budget ratio"),
        ("codezen_skill_calls_vs_log_expert", "CodeZen skill calls vs log expert time"),
        ("sdd_skill_calls_vs_log_expert", "SDD skill calls vs log expert time"),
        ("codezen_d_pass_any_vs_log_expert", "$\\Delta$ pass-at-2, CodeZen, vs log expert time"),
        ("sdd_d_pass_any_vs_log_expert", "$\\Delta$ pass-at-2, SDD, vs log expert time"),
        ("codezen_d_pass_any_vs_expert_budget", "$\\Delta$ pass-at-2, CodeZen, vs expert/budget"),
        ("sdd_d_pass_any_vs_expert_budget", "$\\Delta$ pass-at-2, SDD, vs expert/budget"),
        ("codezen_d_pass_rate_vs_log_expert", "$\\Delta$ pass rate, CodeZen, vs log expert time"),
        ("sdd_d_pass_rate_vs_log_expert", "$\\Delta$ pass rate, SDD, vs log expert time"),
        ("codezen_d_pass_rate_vs_expert_budget", "$\\Delta$ pass rate, CodeZen, vs expert/budget"),
        ("sdd_d_pass_rate_vs_expert_budget", "$\\Delta$ pass rate, SDD, vs expert/budget"),
        ("codezen_d_partial_credit_vs_log_expert", "$\\Delta$ partial credit, CodeZen, vs log expert time"),
        ("sdd_d_partial_credit_vs_log_expert", "$\\Delta$ partial credit, SDD, vs log expert time"),
        ("codezen_d_partial_credit_vs_expert_budget", "$\\Delta$ partial credit, CodeZen, vs expert/budget"),
        ("sdd_d_partial_credit_vs_expert_budget", "$\\Delta$ partial credit, SDD, vs expert/budget")]
rows = []
for key, label in CORR:
    v = VN["pooled"]["correlations"][key]
    rows.append(rf"{label} & ${v['rho']:+.3f}$ & {p_fmt(v['p'])} & {v['n']} \\")
w("t11-correlations", r"""
\begin{tabular}{@{}lrrr@{}}
\toprule
Spearman rank correlation, pooled over 26 tasks & \multicolumn{1}{c}{$\rho$} & \multicolumn{1}{c}{$p$} & \multicolumn{1}{c}{$n$} \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
""")


# --- t12 long-horizon split -------------------------------------------------
SPL = [("codezen_d_pass_any", "$\\Delta$ pass-at-2, CodeZen"),
       ("sdd_d_pass_any", "$\\Delta$ pass-at-2, SDD"),
       ("codezen_d_pass_rate", "$\\Delta$ pass rate, CodeZen"),
       ("sdd_d_pass_rate", "$\\Delta$ pass rate, SDD"),
       ("codezen_d_partial_credit", "$\\Delta$ partial credit, CodeZen"),
       ("sdd_d_partial_credit", "$\\Delta$ partial credit, SDD"),
       ("codezen_cost_ratio", "cost ratio, CodeZen"),
       ("sdd_cost_ratio", "cost ratio, SDD"),
       ("codezen_skill_calls", "toolkit skill calls per attempt, CodeZen"),
       ("sdd_skill_calls", "toolkit skill calls per attempt, SDD")]
rows = []
for key, label in SPL:
    v = VN["pooled"]["long_horizon"]["splits"][key]
    rows.append(rf"{label} & ${v['long_mean']:+.3f}$ & ${v['short_mean']:+.3f}$ & {p_fmt(v['p'])} \\")
lh = VN["pooled"]["long_horizon"]
w("t12-long-horizon", rf"""
\begin{{tabular}}{{@{{}}lrrr@{{}}}}
\toprule
 & long-horizon ($n = {lh['n_long']}$) & short ($n = {lh['n_short']}$) & \multicolumn{{1}}{{c}}{{Mann--Whitney $p$}} \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
""")


# --- t13 best-of-N ----------------------------------------------------------
rows = []
for run in RUNS:
    v = BN["equal_spend"][run]["codezen-viable"]
    r = VN["runs"][run]
    pa2 = r["pass_at_2"]["per_condition"]["codezen-viable"] / r["n_tasks"]
    k2 = 2 * v["k_equal_spend"]
    rows.append(
        rf"{run} & {v['baseline_p_per_attempt']:.3f} & {k2:.1f} & "
        rf"{100*v['baseline_best_of_2k_naive']:.1f}\% & {100*v['baseline_best_of_2k_betabinom']:.1f}\% & "
        rf"{100*v['baseline_best_of_2k_plugin']:.1f}\% & {100*pa2:.1f}\% \\")
w("t13-best-of-n", r"""
\begin{tabular}{@{}lrrrrrr@{}}
\toprule
 & \multicolumn{1}{c}{baseline $\bar p$} & \multicolumn{1}{c}{$k$ at equal spend} &
 \multicolumn{3}{c}{baseline best-of-$k$, by estimator} & \multicolumn{1}{c}{CodeZen} \\
\cmidrule(lr){4-6}
run & per attempt & (2 CodeZen attempts) & homogeneous & beta-binomial & plug-in & pass-at-2 \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
""")


# --- t14 every censored trial ----------------------------------------------
rows = []
for run in RUNS:
    for x in VN["runs"][run]["censored_trials"]:
        rows.append(rf"{run} & {esc(x['task'])} & {LAB[x['condition']]} & {x['reward']:.1f} & "
                    rf"{x['tests_passed']:.0f}/{x['tests_total']:.0f} & {x['partial_credit']:.2f} & "
                    rf"{100*x['budget_used']:.0f}\% & \${x['cost_usd']:.2f} \\")
w("t14-censored", r"""
\begin{tabular}{@{}lllrrrrr@{}}
\toprule
run & task & condition & reward & tests & partial credit & budget & cost \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
""")


# --- t15/t16 task tables ----------------------------------------------------
cat = pd.read_csv(REPO / "results/analysis-suite/data/trials.csv")
for run in RUNS:
    t = pd.read_csv(REPO / f"results/analysis-{run}/data/trials.csv")
    t["success"] = t.success.fillna(False).astype(int)
    meta = (t.groupby("task")
            .agg(category=("category", "first"), difficulty=("difficulty", "first"),
                 axes=("axes", "first"), expert=("expert_min", "first"),
                 budget=("budget_sec", "first"))
            .reset_index())
    pa2 = t.pivot_table(index="task", columns="condition", values="success", aggfunc="max")
    pb = (t.pivot_table(index="task", columns="condition", values="success", aggfunc="mean") == 1)
    rows = []
    for _, x in meta.sort_values("task").iterrows():
        def cell(c):
            n = int(pa2.loc[x.task, c]) + int(pb.loc[x.task, c])
            return {0: "0/2", 1: "1/2", 2: "2/2"}[n]
        rows.append(rf"\texttt{{\footnotesize {esc(x.task)}}} & {esc(x.category)} & {esc(x.difficulty)} & "
                    rf"{x.expert:.0f} & {x.budget/60:.1f} & {x.expert/(x.budget/60):.1f}$\times$ & "
                    rf"{cell('baseline')} & {cell('codezen-viable')} & {cell('sdd')} \\")
    w(f"t15-tasks-{run}", r"""
\begin{tabular}{@{}lllrrrccc@{}}
\toprule
task & category & diff. & expert (min) & budget (min) & ratio & base & CZ & SDD \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
""")


# --- t17 pooled headline ----------------------------------------------------
P = VN["pooled"]
w("t17-pooled", rf"""
\begin{{tabular}}{{@{{}}lrrr@{{}}}}
\toprule
pooled over 156 trials, 26 tasks, \${P['spend']:.2f} & baseline & CodeZen & SDD \\
\midrule
cost per trial & \${P['conditions']['baseline']['cost_per_trial']:.3f} & \${P['conditions']['codezen-viable']['cost_per_trial']:.3f} & \${P['conditions']['sdd']['cost_per_trial']:.3f} \\
sub-agents spawned per trial & {P['conditions']['baseline']['subagents']:.3f} & {P['conditions']['codezen-viable']['subagents']:.3f} & {P['conditions']['sdd']['subagents']:.3f} \\
agent timeouts & {P['conditions']['baseline']['timeouts']} of 52 ({100*P['conditions']['baseline']['timeout_share']:.1f}\%) & {P['conditions']['codezen-viable']['timeouts']} of 52 ({100*P['conditions']['codezen-viable']['timeout_share']:.1f}\%) & {P['conditions']['sdd']['timeouts']} of 52 ({100*P['conditions']['sdd']['timeout_share']:.1f}\%) \\
\bottomrule
\end{{tabular}}
""")

print("done")
