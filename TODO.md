# TODO — parallel experiment execution

Working notes for the `feature/parallel-tasks` branch. This file exists so the
work can be picked up after a machine reboot without repeating the
investigation. Delete it when the feature lands.

**State: investigation complete and verified. No implementation code written yet.**

Branch: `feature/parallel-tasks` (created from `main` at `6e382c9`, clean).

---

## 0. Blocker to clear first — reboot

Every container start failed during investigation:

```
failed to add the host (veth9077a33) <=> sandbox (veth2f16588) pair interfaces:
operation not supported
```

Root cause: the running kernel was `7.1.8-arch1-3` while `/lib/modules/` held
only `7.2.2-arch1-1`. The kernel had been upgraded without a reboot, so no
module could load for the running kernel. `sudo modprobe veth` therefore
**cannot** work — a reboot is the fix.

Note this contradicts the advice currently in `docs/troubleshooting.md` and in
`scripts/run-pilot-experiment.sh:108`, both of which say
`sudo modprobe veth && sudo systemctl restart docker`. That advice is right for
an unloaded module and wrong for a stale-module-tree kernel mismatch. Correcting
it is part of task **D** below.

Docker image builds were unaffected throughout; only container networking was
dead.

### Verify the blocker is gone (run first, after reboot)

```bash
uname -r && ls /lib/modules/          # the two must match
docker run --rm hello-world           # must succeed
hmb doctor                            # expect no new failures
```

If `hello-world` still fails, stop and diagnose before anything below — no trial
of any kind can run.

---

## 1. Verified findings — do not re-investigate

All of the following were proven empirically during the previous session, most
of them with a free `nop`-agent job that spends no tokens.

### 1.1 Trial-directory collision — does not occur

Trial names are generated at `models/trial/config.py:502`:

```python
return f"{task_name[:32].rstrip('_-')}__{ShortUUID().random(length=7)}"
```

The suffix is random per trial, not derived from the task or the condition. A
merged job of 8 trials (2 tasks × 2 conditions × 2 attempts) produced 8 distinct
directories, and every `result.json` carried the distinguishing
`config.task.path`:

```
fix-git__P3vJdWp             generated/baseline/fix-git
fix-git__9Zkhshq             generated/sdd/fix-git
cancel-async-tasks__fmSp2qq  generated/baseline/cancel-async-tasks
cancel-async-tasks__8icSSwX  generated/sdd/cancel-async-tasks
```

`hmb report` split that single merged job into `BASELINE 4 trials` and
`SDD 4 trials` correctly, with no code change — it derives the variant from the
task path (`report.py:147`), not from the job name.

**Conclusion: one Harbor job may span all conditions. Merging is safe.**

### 1.2 Harbor's job model supports the whole matrix in one job

`JobConfig` (verified against the installed 0.21.0 schema) takes a list of
datasets and a list of agents. Relevant keys, with the names that actually work:

| Key | Meaning |
|---|---|
| `n_concurrent_trials` | max concurrent trials, whole lifecycle (build + agent + verify). Default 4 |
| `agents[].n_concurrent` | per-agent cap on concurrent `agent.run()` phases. Must be ≤ `n_concurrent_trials` |
| `agents[].concurrency_group` | optional shared pool name; requires `n_concurrent` to be set |
| `n_attempts` | repetitions per trial |

Agent configs that are byte-identical already share one concurrency pool without
naming a group: `AgentConfig.concurrency_key` (`models/trial/config.py:170`)
hashes the config's identity when `concurrency_group` is unset. So all
conditions running the same Claude Code config share one credential throttle
automatically.

### 1.3 Task-major ordering is achievable through config alone

`Job._resolve_task_configs` (`job.py:377-391`) simply extends the task list
dataset by dataset with **no deduplication**, and `_init_trial_configs`
(`job.py:415-418`) iterates attempt → task → agent.

So emitting **one `DatasetConfig` per (condition, task) pair** in task-major
order produces genuinely paired execution. Confirmed by launch timestamps in the
proof run — conditions of the same task started within 40 ms of each other.

The default (one dataset per condition) is condition-major: all 30 baseline
trials queue before any toolkit trial. Avoid it — it delays comparable results
and makes host contention asymmetric across conditions, which contaminates
`duration_sec`.

Bonus: harbor's own eval stats key on the dataset directory name, so it reports
`baseline • nop` and `sdd • nop` separately at no cost.

### 1.4 Concurrency at 9 is safe on this host

Docker's `auto` resource mode resolves to **hard limits**
(`environments/docker/docker.py:467`, `auto_mode=ResourceMode.LIMIT`), so each
container is capped at its declared `cpus` / `memory_mb` regardless of its
neighbours. This is why the timeout-under-contention risk is much lower than it
first appeared.

Task suite resource declarations (89 tasks):

| Declaration | Count |
|---|---|
| `cpus = 1` | 84 |
| `cpus = 2` | 3 |
| `cpus = 4` | 2 |
| `memory_mb = 2048` | 69 |
| `memory_mb = 4096` | 17 |
| `memory_mb = 8192` | 3 |
| `storage_mb = 10240` | 89 |

Host: 16 cores, 125 GB RAM. Docker root is `/home/chriz/docker-data` on a
volume with ~395 GB free (**not** the 8 GB-free root partition — that is not in
the path).

Nine concurrent trials ≈ 9 of 16 cores and ~49 GB worst case. Comfortable.

**The real contention source is `docker build`**, which runs on the daemon
outside any container's cpu limit. Mitigation is free: `hmb preflight` already
builds every image as the mandatory gate, so the run's builds become cache hits.
Keep the gate mandatory.

`docker buildx` is absent; compose falls back to the classic builder with a
warning. Every image built fine.

### 1.5 Retry taxonomy

Defined in `agents/installed/base.py:35-75`, pattern-matched at `:441-470`.

Retry — transient, clears on its own:

- `ApiRateLimitError`
- `ApiOverloadedError`
- `ApiInternalServerError`
- `ApiConnectionClosedError`
- `ApiResponseStalledError`

Never retry:

- `ApiUsageLimitError` — needs a human to recharge the account.
- `OutputTokenExceededError` — a verbose `CLAUDE.md` blowing the output cap *is*
  a methodology effect. Retrying it hides a finding.
- Timeouts — could be genuine methodology slowness.

Structurally safe: a legitimate 0.0-reward trial has no `exception_info`, so no
filter can ever catch it.

### 1.6 Resume semantics — verified in place

Reconciliation lives at `job.py:327-357`: every planned trial is matched against
existing trials one-to-one, and unmatched planned trials are re-run. Attempt
multiplicity is handled, so 2-of-3 attempts done leaves exactly 1 remaining.

Verified by experiment on a real job directory:

| Test | Result |
|---|---|
| `harbor job resume -p <dir>` (default filter `CancelledError`) | 0 re-run — **errored trials count as complete** |
| `harbor job resume -p <dir> -f RuntimeError` | 8 deleted, 8 re-run with fresh identities, task-major order preserved |
| One trial hand-marked `ApiUsageLimitError`, then `-f RuntimeError` | **7 removed and re-run, that 1 spared** |

The last row is the budget-exhaustion workflow inverted: recharge the account,
then `-f ApiUsageLimitError` re-runs exactly the exhausted trials and nothing
else.

**Three hard constraints the wrapper must respect:**

1. **Default resume silently accepts failures as results.** Without a filter, a
   rate-limited trial becomes a permanent 0.0 reward. This is precisely the
   failure `report.py`'s own docstring warns about — "reads like a finding and
   is a bug". The filter must never be left to the operator's memory.
2. **Job directories are not relocatable.** The stored `config.json` pins
   `jobs_dir` and `job_name` as absolute paths, and resume targets those, *not*
   the `-p` path. Resuming a copied directory silently operates on the original.
3. **The stored config cannot be edited.** Patching `n_concurrent_trials` in
   `config.json` and resuming raises
   `FileExistsError: ... cannot be resumed with a different config.`
   Concurrency is therefore fixed for a job's entire life — choose it at
   creation. Changing it means a new job, not a resume.

### 1.7 The `-n` bug

`scripts/run-pilot-experiment.sh:270` passes `--attempts` to `harbor -n`, but
`-n` is `--n-concurrent`; attempts is `-k` / `--n-attempts`. Every past run
claiming attempts > 1 actually ran **one** trial per cell at concurrency N.
`docs/experiments.md:252` and `:266` document the same wrong mapping.

---

## 2. Tests to run after the reboot

The investigation could not exercise a *successful* trial, because no container
would start. These tests close that gap. Run them in order; each is cheap and
the first three spend no tokens.

### Test 1 — the `nop` happy path, merged job, task-major

Writes the config below to a scratch path, then runs it. Expect: 8 trial
directories, 8 distinct names, `reward 0.0` for all (nop does nothing, which is
the correct nop outcome), **no exceptions**.

```yaml
# nop-proof.yaml — adjust jobs_dir to a scratch location
job_name: nopproof-collision
jobs_dir: /tmp/hmb-scratch/nopjobs
n_attempts: 2
n_concurrent_trials: 4
agents:
  - name: nop
    n_concurrent: 2
    concurrency_group: shared-cli
datasets:
  - {path: generated/baseline, task_names: [fix-git]}
  - {path: generated/sdd,      task_names: [fix-git]}
  - {path: generated/baseline, task_names: [cancel-async-tasks]}
  - {path: generated/sdd,      task_names: [cancel-async-tasks]}
verifier:
  disable: true
```

```bash
harbor run -c nop-proof.yaml -q
```

Check with:

```bash
python3 - <<'PY'
import json, glob
rows = []
for p in glob.glob('/tmp/hmb-scratch/nopjobs/nopproof-collision/*/result.json'):
    d = json.load(open(p))
    tp = (d.get('config', {}).get('task') or {}).get('path')
    rows.append((d['started_at'], p.split('/')[-2], tp, (d.get('exception_info') or {}).get('exception_type')))
rows.sort()
for r in rows: print(*r)
print('unique dirs:', len({r[1] for r in rows}), 'of', len(rows))
PY
```

Pass criteria: 8 of 8 unique; conditions of the same task adjacent in start
order; exception column all `None`.

### Test 2 — `oracle` proves rewards still land in a merged job

Same config, `-a oracle`, verification **enabled**, one task, one attempt per
condition. The oracle runs the reference solution and must score 1.0. This is
the check that merging conditions into one job does not disturb verification.

```bash
harbor run -p generated/baseline/fix-git -a oracle -n 1 --job-name oracle-check
```

Then the merged form (two datasets, verification on). Pass criteria: reward 1.0
for every trial, in both forms.

### Test 3 — resume selectivity on a real mixed job

Take the Test 1 job, hand-edit one trial's `result.json` to give it
`exception_info.exception_type = "ApiUsageLimitError"`, then:

```bash
harbor job resume -p /tmp/hmb-scratch/nopjobs/nopproof-collision -f ApiUsageLimitError
```

Pass criteria: exactly 1 directory removed and re-run; the other 7 untouched;
total count unchanged. **Run this in place — never on a copy** (see §1.6
constraint 2).

### Test 4 — one real paid cell, before committing to a matrix

The canary the docs already recommend. One task, one condition, Claude Code,
one attempt, to confirm credentials forward and the quota is real:

```bash
./scripts/run-smoke-experiment.sh --task sqlite-db-truncate
```

### Test 5 — the existing suite must stay green

```bash
uv run pytest
```

---

## 3. Open decisions — ask before implementing

1. **Agent sub-cap.** `n_concurrent_trials: 9` is decided. The proposed starting
   value for `agents[].n_concurrent` is **6**, leaving 3 slots so builds and
   verifiers overlap agent runs and a rate-limit stall does not idle the whole
   machine. Confirm or override.
2. **Merged-only, or keep per-cell jobs behind `--no-merge`?** Merged jobs give
   one resumable unit and paired ordering; per-cell jobs give finer restart
   granularity and match the existing `jobs/<prefix>-<cell>-<task>/` layout that
   `hmb report --pattern` and every result in `results/` already assume.

---

## 4. Implementation plan

### A. `hmb plan-job`

Emit a Harbor job config from an experiment configuration.

- One `DatasetConfig` per (condition, task) pair, ordered **task-major** (§1.3).
- `n_concurrent_trials: 9`, `agents[].n_concurrent: 6` (pending decision 1).
- `n_attempts` from `--attempts`.
- `retry.include_exceptions` = the allowlist in §1.5.
- Cells group into one job per agent. A sparse matrix yields several jobs.
- Deterministic output, so a job config is reproducible from the experiment
  file — same property the rest of the framework already guarantees.

New module, probably `src/harbor_methodology_bench/jobplan.py`, plus a CLI
command in `cli.py`. Mirror `matrix-plan`'s shape: it should be printable and
inspectable without running anything.

### B. Runner rewrite — `scripts/run-pilot-experiment.sh`

- Build job configs via `hmb plan-job`; run the per-agent jobs through a
  host-side pool.
- **Fix the `-n` bug**: attempts is `-k` / `--n-attempts` (§1.7).
- Keep the validate/preflight gate mandatory — it is also what makes the run's
  image builds cache hits (§1.4).
- Parallelise the preflight image builds: `preflight_task`
  (`preflight.py:381`) currently builds baseline plus every toolkit variant
  serially, per task. This is pure host-side work Harbor never sees.
- Per-job log files; parallel jobs must not interleave on the terminal.

### C. `hmb resume <job>`

- Classify every trial in the job directory by exception type and print the
  breakdown before doing anything.
- Re-run with the appropriate filter. Default: `CancelledError` plus infra
  `RuntimeError`. `--recharged` adds `ApiUsageLimitError`.
- Refuse to filter any type outside the allowlist, so a task failure can never
  be laundered into a retry.
- Enforce §1.6 constraint 2: operate on the real job directory, and fail loudly
  if `config.json`'s `jobs_dir` / `job_name` do not point at the directory
  given.

### D. Reporting and documentation

- Record the run's concurrency settings in the report header.
- State that `duration_sec` is contention-affected under parallel execution and
  is not comparable with the serial numbers already in `results/`; cost and
  token metrics are unaffected. This belongs with the other confounds in
  `docs/troubleshooting.md`.
- Document the resume workflow, especially that a bare resume treats failures as
  results.
- **Correct the veth advice** in `docs/troubleshooting.md` and
  `scripts/run-pilot-experiment.sh:108` to distinguish an unloaded module from a
  kernel/module-tree mismatch that needs a reboot (§0).
- Fix the attempts mapping in `docs/experiments.md:252` and `:266`.
- Remove the "Trials run serially" limitation from `docs/troubleshooting.md`
  once B lands.
- Update `docs/reference.md` with the new commands, and `CHANGELOG.md`.

Keep the invariants in `docs/architecture.md#6-invariants` intact; each has a
test.

---

## 5. Reference — files that matter

| Path | Why |
|---|---|
| `scripts/run-pilot-experiment.sh:231-280` | the serial matrix loop being replaced; `:270` is the `-n` bug |
| `src/harbor_methodology_bench/preflight.py:381` | serial per-task image builds |
| `src/harbor_methodology_bench/report.py:147` | derives variant from `config.task.path` — why merged jobs report correctly |
| `src/harbor_methodology_bench/config.py` | `ExperimentConfig`, `specs()`, the matrix |
| `src/harbor_methodology_bench/cli.py:338` | `matrix-plan`, the shape `plan-job` should follow |
| `docs/troubleshooting.md` | confounds and limitations sections both need edits |

Harbor internals referenced above live under
`~/.local/share/uv/tools/harbor/lib/python3.12/site-packages/harbor/`
(version 0.21.0).
