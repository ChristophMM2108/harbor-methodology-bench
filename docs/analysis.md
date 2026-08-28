# Analysis

[← README](../README.md) · [setup](setup.md) · [architecture](architecture.md) · [experiments](experiments.md) · [tasks](tasks.md) · [reference](reference.md) · [troubleshooting](troubleshooting.md)

Two layers. `hmb report` aggregates one row per matrix cell and is what you read
first. `hmb analysis` goes back to the raw trial artefacts and derives the
per-trial, per-test and per-step measurements the aggregate cannot carry.

---

## 1. The report

```bash
hmb report --pattern "my-run-*" \
    --md-out results/my-run_report.md \
    --json-out results/my-run_summary.json
```

Per cell: success rate, mean verifier reward, average duration, token consumption
(input / output / cache), cost in USD, and adherence. Plus per-task breakdowns, a
methodology-adherence table, and an exception summary naming the exact failure
cause — rate limits, timeouts, non-zero exits.

`--pattern` is a glob over job names, so one report can span a single cell
(`"my-run-claude-my-kit-*"`), a whole experiment (`"my-run-*"`), or everything in
`jobs/` (`"*"`). Multi-task and multi-attempt jobs are folded together
automatically. Write both forms when archiving a result: the markdown for people,
the JSON for anything downstream.

---

## 2. Reading adherence

| Column | Source | Means |
|---|---|---|
| `Skills Available` | the agent CLI's own startup log | how many of the toolkit's skills the CLI registered at runtime |
| `Skills Named` | agent-authored trajectory text | a toolkit skill name appears somewhere the agent wrote |
| `Skills Invoked` | `Skill` tool calls | the agent actually invoked a skill the variant installed |
| `Config Referenced` | agent-authored trajectory steps | whether the agent named `CLAUDE.md` / `AGENTS.md` |

**`Skills Named` and `Skills Invoked` are different measurements and must not be
conflated.** An agent that lists its own skills directory names every skill it
owns; that is not usage. The strict measure is the `Skill` tool call. In one
measured run the loose count was 8 of 16 trials and the strict count 7, and in
another condition 2 versus 1 — the gap is small but it is the difference between
"the method was used" and "the method was mentioned".

Only agent-authored steps count for the last three — a CLI's system prompt
mentions `AGENTS.md` unconditionally and would otherwise register as adherence.

Three caveats that decide how much weight the columns can carry:

- **Claude Code loads a project `CLAUDE.md` silently** into its system prompt. An
  empty `Config Referenced` means the agent never named the file, not that it
  never received it. Availability is what preflight proves.
- **Toolkits often gate themselves.** A kit that says to use its skills "for
  substantial feature development" is behaving as written when a small task skips
  them. That is a finding about the toolkit's own thresholds, not a bug.
- **A condition whose skills were never invoked measures "a repository containing
  a method", not "the method".** If adherence is near zero, say so in the
  write-up before reporting an outcome difference; it changes what the comparison
  was.

Example, a single trial:

| Agent | Condition | Reward | Skills Available | Skills Named | Skills Invoked |
|---|---|---:|---:|---:|---:|
| `claude-code` | `my-kit` | 1.00 | 7/7 | 0 | 0 |

All seven skills were registered in the container; the agent solved the task
without invoking any of them.

---

## 3. Trial-level analysis

```bash
hmb analysis init my-run --pattern "my-run-*"
uv sync --group analysis
uv run --group analysis jupyter lab results/analysis-my-run/my-run_analysis.ipynb
```

`analysis init` scaffolds a notebook under `results/analysis-<name>/`, derives the
tables into its `data/` directory, and leaves `figures/` for its output. The
notebook is a starting point, not a fixed report: extend it, and keep one analysis
per run so there is a single analysis of record.

To derive the tables without a notebook:

```bash
hmb analysis extract --pattern "my-run-*" --out-dir results/analysis-my-run/data
```

Four tidy tables, all CSV:

| Table | Grain | Carries |
|---|---|---|
| `trials.csv` | one row per trial | reward, partial credit, phase durations, budget utilisation, tokens and cost, tool-call counts, strict adherence, joined task metadata |
| `tests.csv` | one row per verifier test | task, condition, test name, status, duration |
| `steps.csv` | one row per agent step | elapsed offset, prompt / completion / cached / thinking tokens, sidechain flag |
| `tool_calls.csv` | one row per tool call | tool, Bash sub-class, elapsed offset |

Task metadata — difficulty, axes,
each task's declared agent budget — is joined from
`results/task_catalogue.json` when it exists; write it with
`hmb catalogue --json-out`.

---

## 4. Metrics worth reading, and why

### Partial credit

The fraction of the verifier's individual tests that passed, from
`verifier/ctrf.json`. It is strictly finer than the binary reward, it is free, and
it multiplies the graded outcomes several-fold — one measured run had 48 binary
rewards and 183 test outcomes from the same trials. If an effect exists but the
reward is too coarse to see it, this is where it shows first.

### Budget utilisation and censoring

`agent_sec` divided by the task's declared agent budget. Absolute duration is not
comparable across tasks with different budgets; this is. It also exposes the
mechanism by which a methodology can *lose*: extra planning consumes headroom, and
past the wall Harbor kills the agent and grades whatever is on disk.

A timeout is **right-censoring, not a wrong answer**. Folding it into a success
rate converts "we stopped watching" into "it failed", and it biases against
exactly the conditions that add process. Report censored trials separately. In one
measured run, two of the five informative outcomes were decided by the clock
rather than by capability.

### Discriminative capacity

The count of task pairs where two conditions disagree. That count — not the task
count — is the effective sample size of a paired binary comparison. Compute it
before quoting a p-value; see [tasks.md](tasks.md#1-choosing-tasks-that-can-discriminate).

### Behaviour

Steps, tool calls, tool mix, sub-agent spawns, file edits, verification commands,
error rate, time to first edit, thinking-token share. These separate conditions
even when the outcome does not, and they say whether a methodology changed the
work in the direction it claims. Sub-agent spawns in particular are a strong
signature of delegation-heavy kits and are invisible to the cell-level report.

Note the limit: shell commands are bucketed by pattern, not parsed. The
verification bucket catches test runners and self-written `test_x.c` /
`verify_y.py` scripts, but misses checks done inline in a heredoc — so read it as
a comparison between conditions on one corpus, not as an absolute count.

### Cost per success

Total condition spend divided by tasks passed. When success rates are equal the
marginal cost per additional success is undefined, and this is the honest framing:
the decision an operator faces is what one passing task costs under each
configuration.

---

## 5. Metrics worth adding

Ordered by value per unit of effort. The first three need no new trials.

| Metric | Definition | What it settles |
|---|---|---|
| **Time to first passing test** | timestamp of the first agent-run test command whose output shows a pass | a speed metric that survives a ceiling: when most tasks pass, *when* still differs |
| **Rework ratio** | edits to a file after that file's first successful test run | separates churn from progress, which an edit count cannot |
| **Recovery rate** | share of error observations followed within k steps by a non-error result on the same target | resilience, which is what root-cause skills claim |
| **Instruction compliance** | did the agent produce the artefacts its own `CLAUDE.md` prescribes (a spec file, a plan, a checklist)? | separates "the method was available" from "the method was followed" — the gap most runs turn on |
| **Requirement-level scoring** | map each enumerated requirement in `instruction.md` to the verifier tests that check it | per-requirement credit; tests the `spec-dense` claim directly |
| **Reward trajectory** | run the verifier against the workdir at intervals, or on the final state at k checkpoints | turns a censored trial into a curve: was the condition behind at the wall, or ahead and unlucky? |
| **Solution quality beyond pass** | a fixed linter / complexity / coverage pass over the final workdir | methodologies claim quality, and a pass/fail verifier cannot see it |
| **Verifier flakiness control** | re-run the verifier k times on the same final state | separates a flaky verifier from a real failure; costs no model tokens |

---

## 6. Presenting a result

The figures the scaffolded notebook writes are sized for a 16:9 slide and saved
as 300 dpi PNG plus SVG. Three habits keep a presentation honest:

- **Lead with what the design could measure**, not with the p-value. A null from
  an underpowered design is not evidence of no effect.
- **Report cost and outcome together.** Equal outcomes at unequal cost is a
  result, and usually the most decision-relevant one.
- **State the attempt count and the censoring rule** on the slide that shows a
  success rate. Both change the number.
