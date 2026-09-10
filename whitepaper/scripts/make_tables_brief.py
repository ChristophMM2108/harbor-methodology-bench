"""Trimmed LaTeX tables for the short report (brief.tex).

Same recomputed source as the full paper (data/verified_numbers.json), but only
the rows the short report argues from. Nothing is recalculated here.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "whitepaper" / "tables"
VN = json.loads((REPO / "whitepaper/data/verified_numbers.json").read_text())
BN = json.loads((REPO / "whitepaper/data/best_of_n.json").read_text())
CONDS = ["baseline", "codezen-viable", "sdd"]
LAB = {"baseline": "baseline", "codezen-viable": "CodeZen", "sdd": "SDD"}
RUNS = ("suite", "ceiling")


def w(name, body):
    (OUT / f"{name}.tex").write_text(body.rstrip() + "\n")
    print(f"  tables/{name}.tex")


def p_fmt(p):
    txt = "$<$0.001" if p < 0.001 else f"{p:.3f}"
    return r"\textbf{" + txt + "}" if p < 0.05 else txt


# --- b01 the two populations, compact ---------------------------------------
s, c = VN["runs"]["suite"], VN["runs"]["ceiling"]
w("b01-populations", rf"""
\begin{{tabular}}{{@{{}}lrr@{{}}}}
\toprule
 & \textbf{{suite}} & \textbf{{ceiling}} \\
\midrule
Inclusion rule & bare agent must fail & bare agent already passes \\
Trials ($\text{{tasks}}\times3\times2$) & {s['n_trials']} (16 tasks) & {c['n_trials']} (10 tasks) \\
Model spend & \${s['spend']:.2f} & \${c['spend']:.2f} \\
Baseline pass-at-2 & {s['pass_at_2']['per_condition']['baseline']}/16 = {100*s['pass_at_2']['per_condition']['baseline']/16:.0f}\,\% & {c['pass_at_2']['per_condition']['baseline']}/10 = {100*c['pass_at_2']['per_condition']['baseline']/10:.0f}\,\% \\
Concordant tasks, pass-at-2 & {s['pass_at_2']['all_pass']+s['pass_at_2']['all_fail']}/16 ({s['pass_at_2']['all_fail']} failed by everything) & {c['pass_at_2']['all_pass']+c['pass_at_2']['all_fail']}/10 ({c['pass_at_2']['all_fail']} failed by everything) \\
Spend on concordant tasks & \${s['pass_at_2']['concordant_spend']:.2f} ({100*s['pass_at_2']['concordant_spend']/s['spend']:.0f}\,\%) & \${c['pass_at_2']['concordant_spend']:.2f} ({100*c['pass_at_2']['concordant_spend']/c['spend']:.0f}\,\%) \\
Effective $n$ per paired test & 4--5 & 1--2 \\
Design defect & floor effect & ceiling, by construction \\
\bottomrule
\end{{tabular}}
""")

# --- b02 outcome, both runs in one table ------------------------------------
rows = []
for run in RUNS:
    r = VN["runs"][run]
    for i, cond in enumerate(CONDS):
        v = r["conditions"][cond]
        lo, hi = v["wilson_graded"]
        run_cell = rf"\multirow{{3}}{{*}}{{\emph{{{run}}}}}" if i == 0 else ""
        rows.append(
            rf"{run_cell} & {LAB[cond]} & {v['censored']} & {100*v['success_rate_graded']:.1f}\,\% & "
            rf"[{100*lo:.0f}, {100*hi:.0f}] & {100*v['success_rate_timeout_fail']:.1f}\,\% & "
            rf"{100*v['success_rate_kill_graded']:.1f}\,\% & "
            rf"{v['partial_credit']:.3f} & {100*v['test_pass_rate']:.1f}\,\% & \${v['cost_total']:.2f} \\")
    rows.append(r"\midrule" if run == "suite" else "")
w("b02-outcome", r"""
\begin{tabular}{@{}llrrcrrrrr@{}}
\toprule
 & & & \multicolumn{2}{c}{\textbf{1.} censored} & \multicolumn{1}{c}{\textbf{2.} t/o} &
 \multicolumn{1}{c}{\textbf{3.} graded} & & & \\
\cmidrule(lr){4-5}\cmidrule(lr){6-6}\cmidrule(lr){7-7}
 & & \multicolumn{1}{c}{cens.} & \multicolumn{1}{c}{success} & \multicolumn{1}{c}{95\,\% Wilson} &
 \multicolumn{1}{c}{$=$ fail} & \multicolumn{1}{c}{at kill} &
 \multicolumn{1}{c}{part.\ credit} &
 \multicolumn{1}{c}{test rate} & \multicolumn{1}{c}{spend} \\
\midrule
""" + "\n".join(r for r in rows if r) + r"""
\bottomrule
\end{tabular}
""")

# --- b03 paired tests, the rows the argument rests on -----------------------
KEEP = [("cost_usd", "cost"), ("budget_used", "budget consumed"),
        ("output_tokens", "output tokens"), ("n_agent_spawns", "sub-agents spawned"),
        ("partial_credit", "partial credit")]
rows = []
for key, label in KEEP:
    cells = []
    for run in RUNS:
        n = VN["runs"][run]["n_tasks"]
        for cond in ("codezen-viable", "sdd"):
            v = VN["runs"][run]["paired"][key][cond]
            cells.append(rf"{v['ratio_of_totals']:.2f}$\times$ & {v['higher_on']}/{n} & {p_fmt(v['p'])}")
    rows.append(f"{label} & " + " & ".join(cells) + r" \\")
w("b03-paired", r"""
\begin{tabular}{@{}lrcrrcrrcrrcr@{}}
\toprule
 & \multicolumn{6}{c}{\textbf{suite} ($n = 16$ tasks)} & \multicolumn{6}{c}{\textbf{ceiling} ($n = 10$ tasks)} \\
\cmidrule(lr){2-7}\cmidrule(lr){8-13}
 & \multicolumn{3}{c}{CodeZen} & \multicolumn{3}{c}{SDD} & \multicolumn{3}{c}{CodeZen} & \multicolumn{3}{c}{SDD} \\
\cmidrule(lr){2-4}\cmidrule(lr){5-7}\cmidrule(lr){8-10}\cmidrule(lr){11-13}
vs baseline & ratio & on & $p$ & ratio & on & $p$ & ratio & on & $p$ & ratio & on & $p$ \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
""")

# --- b04 behaviour, the five rows that carry a mechanism --------------------
BEH = [("subagents", "sub-agents spawned", "{:.2f}"),
       ("bash_test", "verification commands", "{:.2f}"),
       ("wrote_test_file_share", "wrote its own test file", "{:.0%}"),
       ("steps", "agent steps", "{:.1f}"),
       ("error_rate", "tool results with an error", "{:.1%}")]
rows = []
for key, label, fmt in BEH:
    cells = [fmt.format(VN["runs"][run]["conditions"][c][key]).replace("%", r"\%")
             for run in RUNS for c in CONDS]
    rows.append(f"{label} & " + " & ".join(cells) + r" \\")
w("b04-behaviour", r"""
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

# --- b05 the six correlations the length section argues from ----------------
CORR = [("baseline_pass_vs_expert", "baseline pass-at-2 vs log expert time", "human difficulty does not predict agent difficulty"),
        ("baseline_cost_vs_expert", "baseline absolute cost vs log expert time", "longer tasks cost more, as expected"),
        ("codezen_cost_ratio_vs_log_expert", "CodeZen cost \\emph{ratio} vs log expert time", "the multiplier is flat over $288\\times$ of length"),
        ("codezen_d_pass_any_vs_expert_budget", "$\\Delta$ pass-at-2, CodeZen, vs expert/budget", "the only lean in the hypothesis' direction"),
        ("codezen_d_partial_credit_vs_expert_budget", "$\\Delta$ partial credit, CodeZen, vs expert/budget", "\\dots and it is gone at 519 graded tests"),
        ("sdd_skill_calls_vs_log_expert", "SDD toolkit skill calls vs log expert time", "SDD gates itself on perceived task size")]
rows = []
for key, label, note in CORR:
    v = VN["pooled"]["correlations"][key]
    rows.append(rf"{label} & ${v['rho']:+.3f}$ & {p_fmt(v['p'])} & {note} \\")
w("b05-correlations", r"""
\begin{tabular}{@{}lrrl@{}}
\toprule
Spearman, pooled over 26 tasks & \multicolumn{1}{c}{$\rho$} & \multicolumn{1}{c}{$p$} & what it says \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
""")

# --- b06 best-of-N ----------------------------------------------------------
rows = []
for run in RUNS:
    v = BN["equal_spend"][run]["codezen-viable"]
    r = VN["runs"][run]
    pa2 = r["pass_at_2"]["per_condition"]["codezen-viable"] / r["n_tasks"]
    rows.append(
        rf"\emph{{{run}}} & {v['baseline_p_per_attempt']:.2f} & {2*v['k_equal_spend']:.1f} & "
        rf"{100*v['baseline_best_of_2k_naive']:.0f}\,\% & {100*v['baseline_best_of_2k_betabinom']:.0f}\,\% & "
        rf"{100*v['baseline_best_of_2k_plugin']:.0f}\,\% & \textbf{{{100*pa2:.0f}\,\%}} \\")
w("b06-best-of-n", r"""
\begin{tabular}{@{}lrrrrrr@{}}
\toprule
 & \multicolumn{1}{c}{baseline $\bar p$} & \multicolumn{1}{c}{$k$ at equal} &
 \multicolumn{3}{c}{baseline best-of-$k$, by estimator} & \multicolumn{1}{c}{CodeZen} \\
\cmidrule(lr){4-6}
 & per attempt & spend & homogeneous & beta-binomial & plug-in & pass-at-2 \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
""")
print("done")
