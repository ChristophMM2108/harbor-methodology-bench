# Changelog

All notable changes to this project are documented here. This project is in
active development and does not yet publish versioned releases.

## Unreleased

### Added — task catalogue and deliberate task selection

New module `src/harbor_methodology_bench/catalogue.py`, CLI command
`harbor-methodology-bench catalogue`, wrapper `scripts/catalogue.sh`.

The 89 tasks in `source-tasks/terminal-bench/` carry a benchmark-native
`[metadata].category` saying what each task is *about* (`software-engineering` 26,
`system-administration` 9, `scientific-computing` 8, `security` 8, `data-science`
8, `debugging` 5, `file-operations` 5, and 10 smaller categories). That says
nothing about the *kind of work* the agent must perform, which is what decides
whether a methodology skill can help. The catalogue derives a second, orthogonal
classification — the **axes** — from measurable task metadata:

| Axis | Tasks | Rule |
|---|---:|---|
| `spec-dense` | 21 | ≥ 8 enumerated requirement lines, or ≥ 250 prompt words |
| `underspecified` | 16 | ≤ 60 words and no enumerated requirements |
| `long-horizon` | 19 | expert estimate ≥ 4 hours of human work |
| `quick` | 23 | expert estimate ≤ 30 min and agent budget ≤ 15 min |
| `diagnose-first` | 13 | category `debugging`, or ≥ 2 failure-vocabulary hits |
| `modify-existing` | 23 | changes code or state the agent did not write |
| `verification-heavy` | 12 | ≥ 10 kB of test code, or the prompt requires the agent to write tests |
| `environment-engineering` | 12 | build systems, toolchains, servers, VMs |
| `greenfield-algorithmic` | 36 | from scratch, ≤ 3 requirements, none of the above |

Every rule is a threshold over a measured signal, and all thresholds live at the
top of one module. Two deliberate choices in the rules:

- `long-horizon` reads the **expert time estimate**, not the agent timeout. The
  timeout is a budget, so a five-minute task with a generous 1800 s budget is not
  a long horizon — an earlier draft counted 40 tasks as long-horizon on that
  mistake, against 19 now.
- `verification-heavy` counts only script and text files under `tests/`. Fixture
  data does not make a task verification-heavy; `train-fasttext` ships 11.5 MB of
  test data and 0 kB of test logic.

Generated outputs, both regenerable and committed:

- `docs/task-catalogue.md` — axis legend, category rollup, a per-task table for
  all 89 tasks, and every suite's membership.
- `results/task_catalogue.json` — the same data, machine-readable.

**Selection flags** on `generate`, `validate`, `preflight` and `catalogue`:
`--task ID` (repeatable), `--tasks-file PATH`, `--suite NAME`, `--category NAME`,
`--difficulty LEVEL`, `--limit N`. Every axis name is a suite name; `all` and
`balanced` (the cheapest task per category, 16 tasks) are also available. Filters
compose deterministically — ids and suites union, category and difficulty narrow,
`--limit` truncates a sorted list last — so a selection is reproducible from its
arguments alone. Unknown task ids and empty results are hard errors.

Previously only `--limit N` existed, which takes the alphabetically first N tasks;
the five-task pilot set was an alphabetical slice rather than a chosen sample.

### Added — task selection and matrix configuration in the experiment runners

`scripts/run-pilot-experiment.sh` now takes the same selection flags as the rest
of the pipeline (`--task`, `--tasks-file`, `--suite`, `--category`,
`--difficulty`, `--limit`), so a task group chosen from the catalogue can
actually be run:

```bash
./scripts/generate-variants.sh    --category software-engineering --force
./scripts/validate-variants.sh    --category software-engineering
./scripts/preflight-variants.sh   --category software-engineering
./scripts/run-pilot-experiment.sh --category software-engineering
```

It previously discovered tasks by listing `generated/baseline` and truncating to
`--limit`, default 5. That silently mixed in variants left over from an earlier
selection and dropped everything past the fifth alphabetically — a
26-task category would have run 5 arbitrary tasks. The runner now resolves its
task list through the same selection code as the generator, verifies every
selected variant exists before starting, and names the exact command to generate
any that are missing. A `--dry-run` reports the gap as a warning and still prints
the full plan, so it is usable as a preview before anything is built.

Matrix cells now come from `config/experiments.yaml` through a new `matrix-plan`
command rather than a hard-coded shell array, so a configuration with four
conditions runs four cells. Also added `--config`, `--job-prefix` and
`--attempts` (repetitions per cell, passed to `harbor -n`).

`scripts/run-smoke-experiment.sh` is now a thin wrapper over the same runner,
pinned to one task with the `smoke` job prefix and accepting `--task ID`.

### Added — task authoring guide

README §7 documents authoring a benchmark task end to end: directory layout,
annotated `task.toml`, Dockerfile rules, how the prompt's shape determines which
axes the task lands on, the verifier's reward contract
(`/logs/verifier/reward.txt` or `reward.json`), the reference solution, and the
two token-free proofs that a task is sound — `harbor run -a oracle` must score
1.0 and `-a nop` must score 0.0. Both were verified against `fix-git`.

### Fixed — methodology toolkits never reached the container

The central defect of the previous pipeline. Toolkit snapshots were injected at
the **generated task root**, which Harbor never copies into the environment.
Harbor's task contract (`harbor/models/task/paths.py`) transfers only:

- `instruction.md` — rendered as the agent prompt
- `tests/` — copied to `/tests`, for the verifier
- `solution/` — copied to `/solution`, for the oracle agent only

`harbor/trial/trial.py` uploads nothing else from the task directory. On top of
that, the pilot tasks pin a prebuilt `[environment].docker_image`, and
`harbor/environments/definition.py` skips `environment/Dockerfile` entirely when
a prebuilt image is set without `--force-build`. The consequence: `baseline`,
`sdd` and `dfg` containers were identical, and every published comparison
between them measured nothing but run-to-run noise.

Confirmed empirically before the fix: across all ten Claude toolkit trials in
`jobs/pilot-claude-{sdd,dfg}-*`, the agent trajectories contain zero occurrences
of `CLAUDE.md`, `AGENTS.md`, `.sdd-kit` or any registered skill name.

### Added — the payload layer

New module `src/harbor_methodology_bench/environment.py`.

- The frozen snapshot is staged under `environment/.methodology-bench/` (payload,
  merged skill registry, deployment script), inside the Docker build context.
- A generated `environment/Dockerfile` adds exactly one layer on top of the
  task's own base image:

  ```dockerfile
  FROM <the task's own base image>

  COPY .methodology-bench/ /methodology-bench/
  RUN sh /methodology-bench/deploy-payload.sh <variant> . /methodology-bench/skills
  ```

- **The rendered Dockerfile is byte-identical across every variant of a task.**
  Only the staged payload differs, so the image build path introduces no
  baseline-versus-toolkit confound.
- `deploy-payload.sh` copies each top-level payload entry into the agent's
  working directory and diverts any entry whose name already exists there to
  `/methodology-bench/toolkit-collisions/`. Collisions are now resolved against
  the real container filesystem rather than against the source task directory.
- Everything the harness owns lives outside the working directory, so a baseline
  container's workdir is byte-identical to the base image's.
- The generated task root no longer carries a copy of the toolkit; the payload
  exists once, where it can actually be read.

### Added — skill installation

Skill directories found under `.claude/skills/`, `.agents/skills/` or `skills/`
are merged into a single registry, and `[environment].skills_dir` is set in the
generated `task.toml`. Harbor's agent adapters install from there into the CLI's
own configuration (`claude-code` → `$CLAUDE_CONFIG_DIR/skills`, `codex` →
`$HOME/.agents/skills`).

Verified in a live trial: Claude Code's startup event inside the container lists
`"skills":["sdd-analyze","sdd-clarify","sdd-implement","sdd-plan","sdd-specify","sdd-tasks","sdd-verify",…]`.

### Added — `preflight`, the in-container assertion

New module `src/harbor_methodology_bench/preflight.py`, CLI command
`harbor-methodology-bench preflight`, wrapper `scripts/preflight-variants.sh`.

Builds each variant's image, probes the resulting container from the inside, and
fails closed. Per task it probes the untouched base image, the built baseline,
and every toolkit variant, then asserts:

| Check | Applies to |
|---|---|
| Workdir byte-identical to the untouched base image (SHA-256 per file) | baseline |
| Every payload file present in the workdir with a matching digest | conditions with a payload |
| `CLAUDE.md` / `AGENTS.md` present — or absent | per the condition's `expect_instructions` |
| Registered skills resolvable, and installable by replaying the adapter's own `cp` step | per the condition's `expect_skills` |
| No benchmark file overwritten, no unexplained file added | all variants |

Results are written to `.methodology-bench-preflight.json` per variant. The
smoke and pilot runners run validation plus preflight up front and additionally
refuse any individual cell without a passing report (`--skip-preflight` escapes).

### Added — declarative experimental conditions

`PayloadSpec` replaces the loose per-call arguments. Each condition in
`config/experiments.yaml` may declare:

| Key | Meaning |
|---|---|
| `exclude` | names dropped at any depth |
| `include` | allowlist of top-level snapshot entries |
| `expect_instructions` | must a `CLAUDE.md` / `AGENTS.md` reach the agent workdir? |
| `expect_skills` | must the toolkit's skills be installed for the agent? |
| `skill_sources` | override the global skill source directories |

Both `expect_*` flags are asserted **in both directions**, which makes new
condition shapes possible without weakening the gates — in particular a
*content-only* condition that deploys the same repository with the instruction
and skill surface filtered out. `config/experiments.scenarios.yaml` is a worked
four-condition example; all four pass generation, validation and preflight.

`baseline` is now a reserved id and is rejected in `toolkits:`.

### Changed — validator

`validate` re-derives the entire generated environment through the same code
path that produced it and hash-compares, making it a reproducibility check
rather than a restatement of what is on disk. It now catches an edited generated
`Dockerfile`, an edited `task.toml`, a tampered benchmark file, instruction files
leaking into a condition that declares none, and a condition that declares
instructions but ships none.

### Changed — `task.toml` patching

Two edits, both recorded in `.methodology-bench-manifest.json`:

- `[environment].docker_image` is commented out and reused as the Dockerfile
  `FROM`, so Harbor cannot silently prefer a prebuilt image over the payload
  layer.
- `[environment].skills_dir` is set so the agent adapter installs the toolkit's
  skills.

When a task runs its verifier in a *separate* environment without pinning one,
the original image is pinned under `[verifier.environment]` so verification keeps
running against clean, toolkit-free benchmark code.

### Changed — snapshot payload hygiene

Host-side build artifacts (`.git`, `.venv`, `node_modules`, `__pycache__`,
`.ruff_cache`, `.pytest_cache`, `.mypy_cache`, `.tox`, `.DS_Store`) are dropped
from the payload, configurable globally via `snapshot_excludes` or per toolkit
via `exclude`. The DFG payload shrank from 38 MB to 3.1 MB, most of it a
host-built `.venv` that would have been useless inside the container anyway.

### Added — methodology adherence telemetry

`scripts/report.py` now separates availability from use, with three signals per
trial:

- **Skills Available** — how many of the toolkit's skills the agent CLI
  registered at runtime, read from the CLI's own startup log.
- **Skills Used** — which registered skills appear in agent-authored trajectory
  steps, plus the skill tool-call count.
- **Config Referenced** — whether the agent named `CLAUDE.md` / `AGENTS.md`.

Only agent-authored steps count for the last two. Codex's system prompt mentions
`AGENTS.md` unconditionally and produced a false 5-of-5 before that filter.

Two caveats when reading these numbers: Claude Code loads a project `CLAUDE.md`
silently into its system prompt, so an empty *Config Referenced* means the agent
never named the file, not that it never received it; and toolkits often gate
themselves — SDD tells agents to use its skills "for substantial feature
development", so a small task skipping them is the toolkit behaving as written.

Applied retroactively to the old pilot, every toolkit condition reports
**0 of 5** skills available, which documents the original defect from the
trial artifacts themselves.

### Removed

`inject.inject_snapshot` and `inject.deployment_paths`. Root-level injection was
the mechanism that never reached the container; `inject.py` now only copies the
source task.

### Voided results

`results/pilot_report.md` carries a VOID banner. Those 30 trials ran against
containers that never received a toolkit, so all three conditions were
effectively the baseline. The pilot must be re-run.

### Known issues

- **Codex authentication.** All 15 Codex trials in the old pilot failed with
  `ApiUsageLimitError` before reaching the task. Unrelated to the payload layer;
  renew the account quota before the next matrix run.
- **DFG snapshot is incomplete.** `toolkits/dfg/snapshot/CLAUDE.md` routes agents
  to `MASTER_CONTEXT_INDEX.md`, `DFG.md` and `PROVENANCE_INDEX.md`, none of which
  exist in the snapshot — they appear to be git-ignored in the source repository.
  The toolkit's own entry point is a dead link inside the container.
- **Compose-defined environments are unsupported.** Tasks shipping an
  `environment/docker-compose.yaml` raise a clear error rather than silently
  skipping injection. None of the Terminal-Bench tasks use compose.
- **Payload breadth is an open design question.** A full native deploy also puts
  the toolkit's `src/`, `tests/`, `Makefile` and lockfiles in the agent's working
  directory. See `TODO.md`.

### Verification performed

- 31 unit tests pass (`uv run pytest`), including the classification rules, the
  suite resolution and the selection filter composition.
- `catalogue` classifies all 89 tasks; the generated catalogue and JSON are
  committed.
- Selection verified end to end: `generate` / `validate` / `preflight` with
  `--task fix-git` produced and passed all three conditions. That task also
  exercises two edge cases for real — its workdir is `/app/personal-site` rather
  than `/app`, and its base image already owns a `.gitignore`, which the payload
  layer correctly archived with a warning while keeping the benchmark's copy.
- `harbor run -a oracle` scored 1.0 and `-a nop` scored 0.0 on `fix-git`,
  confirming the task-authoring proof loop documented in README §7.
- 5 tasks × 3 variants pass `validate` and `preflight`.
- 1 task × 4 conditions of `config/experiments.scenarios.yaml` pass `validate`
  and `preflight`, including the content-only condition asserted to carry
  repository content with no instruction files and no skills.
- Harbor built and ran a generated task with `-a nop` (environment start and
  verifier path intact).
- A live `claude-code` trial on `generated/sdd/bn-fit-modify` returned reward
  1.00 with all 7 SDD skills registered inside the container.
