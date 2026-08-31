# Troubleshooting and limitations

[← README](../README.md) · [setup](setup.md) · [architecture](architecture.md) · [experiments](experiments.md) · [tasks](tasks.md) · [analysis](analysis.md) · [reference](reference.md)

Run `hmb doctor` first: it checks the whole environment and names the fix for
everything it finds.

---

## Symptoms

| Symptom | Cause and fix |
|---|---|
| `not inside a harbor-methodology-bench checkout` | `hmb` was run from elsewhere. `cd` into the repository, or set `HMB_ROOT=/path/to/checkout` |
| `hmb: command not found` after the bootstrap | the uv tool directory is not on PATH. `uv tool update-shell`, then open a new shell. `uv run hmb ...` works meanwhile |
| `cannot fetch <sha> or branch <branch>` during setup | no access to that repository, or the pin is not reachable from the branch. For a private toolkit, mark it `optional: true` in `config/sources.yaml` |
| `<id> resolved to <sha>, not the pinned <sha>` | the ref does not exist upstream any more, e.g. after a force-push. Update `ref` and record the change |
| `` `ref` must be a full 40-character commit SHA `` | an abbreviated or numeric ref. Quote it, and use the full SHA |
| `docker build failed` during preflight | read the quoted tail. Usually the base image cannot be pulled, or the source `Dockerfile` needs network access |
| `condition expects project instructions but the payload provides neither` | the snapshot has no `CLAUDE.md` / `AGENTS.md` at its root, or your `exclude` / `include` filtered them out |
| `condition expects no project instructions but the agent workdir contains [...]` | a subtractive condition still ships instruction files. Add them to `exclude` |
| `benchmark image already owns [...]; the toolkit copy was archived` | the base image already has a file of that name at the workdir. The benchmark wins by design; rename the toolkit's file or accept the archive |
| `unexpected file in generated task` | something wrote into `generated/`. Regenerate with `--force` |
| `missing preflight report` when a runner starts a cell | run `hmb preflight` for that task set |
| `ApiUsageLimitError` on every trial of one agent | that account's quota is exhausted; the trial never reached the task. Canary one cheap cell before committing to a run |
| `compose-defined environments are not supported yet` | the task ships `environment/docker-compose.yaml`; the payload layer only patches Dockerfile-defined tasks |
| Docker network errors on Linux (`failed to add the host (veth...) <=> sandbox (veth...) pair interfaces: operation not supported`) | Compare `uname -r` with `ls /lib/modules/` first. **They differ**: the kernel was upgraded without a reboot, no module can load for the running kernel, and `modprobe` cannot help — reboot. **They match**: the module is merely unloaded — `sudo modprobe veth && sudo systemctl restart docker` |
| Disk fills during a multi-task run | `docker image prune` — preflight leaves one thin tagged layer per variant |
| A report shows every condition performing identically | check `hmb preflight` output for that task set. If `markers=-` on a toolkit condition, the payload never arrived and you measured the baseline several times |

---

## Known confounds

These are properties of the measurement, not bugs to be fixed silently. Each one
should be stated in a write-up that depends on it.

**A snapshot may carry absolute host paths from the machine it was frozen on**,
and the framework deliberately does not rewrite them: a snapshot is
byte-identical to its `GIT_SHA`, and editing it would make the pin a lie. A
`settings.json` that registers hooks under `/home/someone/...` will fail silently
inside every container of that condition. Preflight cannot catch this, because the
files it asserts on *are* present. Grep a new snapshot for absolute paths before
trusting a condition built from it:

```bash
grep -rIl -e '/home/' -e '/Users/' toolkits/my-kit/snapshot | head
```

**A toolkit's own entry point can be a dead link inside the container.** If a
`CLAUDE.md` routes the agent to files that are git-ignored upstream, they are
absent from the snapshot and the methodology's first instruction fails. Check
that every path a snapshot's instruction files reference exists in the snapshot.

**Payload breadth is a design decision.** Deploying a toolkit natively also puts
its `src/`, `tests/`, `docs/` and lockfiles in the agent's working directory. Use
`include` / `exclude` to draw the boundary you intend, and record the reasoning —
see [experiments.md § D](experiments.md#d--the-toolkit-as-shipped).

**A curated subset is a different condition.** If some of a toolkit's skills
cannot run in a benchmark container — they need a Docker daemon, a human, a
running system under test, or an MCP server — then the condition you measured is
the runnable subset, not the toolkit. Say which skills were dropped and why.

**`duration_sec` is contention-affected under parallel execution.** The runner
runs up to `--concurrent` trials at once, and although Docker's `auto` resource
mode gives each container hard cpu and memory limits, `docker build` runs on the
daemon outside any container's allowance. A duration measured under concurrency
is therefore not comparable with one measured serially — including the numbers
already in `results/`. Cost and token metrics are unaffected, and every report
records the concurrency its jobs used. Comparisons *within* one run stay fair,
because the task-major dataset order runs the conditions of a task side by side.

**A bare `harbor job resume` accepts a failure as a result.** Without a filter,
a trial that died of a rate limit keeps a permanent 0.0 reward, which reads like
a finding. Resume through `hmb resume <job-dir>`, which classifies the failures
first and re-runs only the ones unrelated to the task. Two Harbor properties
make this sharp: a job directory is not relocatable — the stored `config.json`
pins `jobs_dir` and `job_name`, so resuming a *copy* silently operates on the
original — and a trial whose `result.json` cannot be parsed is skipped by both
the filter and the reconciliation, leaving an orphan directory beside a re-run
of the same trial. `hmb resume` refuses the first and reports the second.

**Adherence detection is textual.** It reads the agent's trajectory and startup
log. It cannot see a `CLAUDE.md` that a CLI loads silently, and a skill name in
prose is not an invocation — see [analysis.md](analysis.md#2-reading-adherence).

**Task axes are heuristics** over each task's own metadata, not curated labels.
They are good enough to choose a task set deliberately and bad enough to produce
the occasional odd member; audit the generated catalogue before publishing a
result that depends on a suite's exact composition.

---

## Current limitations

- **Compose-defined environments** are rejected rather than silently skipped.
- **Snapshot freezing is pull-only.** `hmb setup` fetches a pinned commit; there
  is no command to publish a snapshot from a local working copy that is not
  committed and pushed.
- **The configuration schema carries no per-cell endpoint settings.** Local and
  self-hosted models are reachable through the agent CLIs' base-URL environment
  variables (`ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL`) and through Harbor's own
  LiteLLM-backed agents, but not yet declared per cell.
- **`hmb generate --force` replaces only the selected variants.** Directories
  under `generated/` from an earlier selection are left in place. They cannot join
  a run, but `rm -rf generated/` is the way to start clean.
- **A job's concurrency is fixed at creation.** Harbor refuses to resume a job
  whose stored `config.json` differs, so changing `--concurrent` means a new job,
  not a resume.
