# Setup

[← README](../README.md) · [architecture](architecture.md) · [experiments](experiments.md) · [tasks](tasks.md) · [analysis](analysis.md) · [reference](reference.md) · [troubleshooting](troubleshooting.md)

Everything here is reproducible from a clone. Nothing depends on where the
checkout lives, and no script or configuration file contains an absolute host
path.

---

## 1. Prerequisites

| Requirement | Why | Installed by the bootstrap? |
|---|---|:---:|
| Linux or macOS, `git`, `curl` | the bootstrap itself | — |
| **Docker**, with a running daemon | every trial runs in a container | no |
| **uv** | manages the Python toolchain and the CLI | yes |
| Python 3.12+ | the framework | yes, via uv |
| **Harbor** CLI | executes trials | yes |
| `claude` and/or `codex` | the agents under test | no |
| ~20 GB free disk | task base images and preflight layers | — |

The agent CLIs are deliberately not installed for you: they carry your account
credentials, and which of them you need depends on the experiment.

---

## 2. Bootstrap

```bash
git clone git@github.com:ChristophMM2108/harbor-methodology-bench.git
cd harbor-methodology-bench
./bootstrap.sh
```

In order, it:

1. installs **uv** if it is missing (`--no-uv-install` to refuse instead);
2. runs `uv sync`, creating `.venv` at the interpreter pinned in `.python-version`;
3. installs the **Harbor** CLI as a uv tool (`--no-harbor` to skip);
4. installs this repository as an editable uv tool, which puts **`hmb`** on your
   PATH and keeps it pointed at this checkout (`--no-tool` to skip — then use
   `uv run hmb ...` from the repository instead);
5. runs `hmb setup`, which materialises every pinned source (`--no-fetch` to skip);
6. finishes with `hmb doctor`.

It is idempotent. Re-run it after pulling, or whenever `hmb doctor` reports a gap.

If `hmb` is not on your PATH afterwards, run `uv tool update-shell` and open a new
shell. Everything works without it — `uv run hmb ...` from the repository is the
same command.

---

## 3. `hmb doctor`

`doctor` changes nothing and names the fix for every problem it finds, so its
output is a to-do list rather than a verdict:

```text
ok    python                     3.12.13
ok    docker daemon              server 29.7.2
ok    harbor CLI                 0.21.0
warn  codex CLI                  `codex` is not on PATH
      fix: install the Codex CLI, or run Claude-only experiments
warn  agent credentials          config/local.env exists but every value is still a placeholder
      fix: run `claude setup-token` and paste the token into config/local.env
ok    task-suite terminal-bench  at 2fd12b88aafd
ok    toolkit demo-kit           vendored in this repository
warn  toolkit my-kit             not fetched (optional)
      fix: `hmb setup`
```

| Severity | Meaning |
|---|---|
| `ok` | usable |
| `warn` | usable, with a caveat that will bite later — a missing agent CLI, an unfilled credential, an optional toolkit |
| `fail` | an experiment cannot run |

`hmb doctor` exits non-zero on a failure; `--strict` also fails on a warning,
which is what you want in CI.

---

## 4. Credentials

Agents authenticate **inside** the container, from host-forwarded values in
`config/local.env`. `hmb setup` writes the template at mode 600, and the file is
git-ignored:

```bash
claude setup-token          # prints a single-line token
```

```bash
# config/local.env
CLAUDE_FORCE_OAUTH=1
CLAUDE_CODE_OAUTH_TOKEN="<paste-your-single-line-token-here>"
CODEX_FORCE_AUTH_JSON=1
```

```bash
chmod 700 config && chmod 600 config/local.env
```

`hmb doctor` warns when the file is absent, still contains placeholders, or is
group- or world-readable. It never prints a value.

---

## 5. Pinned sources

Everything external is declared in [`config/sources.yaml`](../config/sources.yaml)
as a repository URL plus an immutable commit. Nothing external is committed to
this repository: a pin and a URL let anyone re-derive byte-identical content,
whereas a vendored copy is provenance only its author can vouch for.

```yaml
task_suites:
  - id: terminal-bench
    repo: https://github.com/harbor-framework/terminal-bench-2.git
    ref: 2fd12b88aafdd04a52c298e3940bcb189f9766d6   # full 40-character SHA
    branch: main
    dest: source-tasks/terminal-bench
    layout: task-dirs-at-root        # a directory is a task when it has a task.toml

toolkits:
  - id: demo-kit
    vendored: true                   # committed here; nothing is fetched
    dest: toolkits/demo-kit
  - id: my-kit
    repo: git@github.com:us/our-repo.git
    ref: dc4b09e730f6e38a43ba85b44991bb6de890b6d9
    dest: toolkits/my-kit
    optional: true                   # a fetch failure is reported, not fatal
```

| Key | Meaning |
|---|---|
| `repo`, `ref`, `branch` | where and what. `ref` must be a full 40-character SHA — an abbreviation is ambiguous, and a pin that can drift is not a pin |
| `dest` | where it lands. Toolkit content goes to `<dest>/snapshot/`; a task suite goes straight to `<dest>/` |
| `layout` | `tree` (default, the whole repository) or `task-dirs-at-root` (only directories holding a `task.toml`) |
| `optional` | a fetch failure is reported and skipped. Use it for private repositories, so a colleague without access can still set up and run the conditions they do have |
| `vendored` | the content is committed here; nothing is fetched |

```bash
hmb sources        # what is declared, and whether it is present at its pin
hmb setup          # materialise everything missing or stale
hmb setup --only my-kit --force
hmb setup --skip-credentials
```

`setup` is idempotent: a source already at its pin is left alone. Fetching writes
`SOURCE`, `GIT_SHA`, `BRANCH` and `VERSION` next to the content, and
`hmb freeze-verify` checks them.

Source states reported by `hmb sources` and `hmb doctor`:

| State | Meaning |
|---|---|
| `ready` | present, and its recorded `GIT_SHA` equals the declared pin |
| `stale` | present, but at a different commit — `hmb setup --force` |
| `missing` | not fetched yet — `hmb setup` |
| `vendored` | committed in this repository |

### Verifying the task suite

```bash
find source-tasks/terminal-bench -mindepth 2 -maxdepth 2 -name task.toml | wc -l   # 89 at the current pin
hmb catalogue
```

---

## 6. Adding your own toolkit

A "toolkit" is any repository whose configuration you want to measure — your
team's `CLAUDE.md` and skills, a published agent kit, or two commits of the same
repository against each other.

1. **Declare it** in `config/sources.yaml`:

   ```yaml
   toolkits:
     - id: my-kit
       description: Our team's agent configuration.
       repo: git@github.com:us/our-repo.git
       ref: <full 40-character SHA>
       branch: main
       dest: toolkits/my-kit
   ```

   Use the **remote URL**, not a local path: paired with the SHA that is enough
   for anyone to re-derive the snapshot, whereas a path under your home directory
   is provenance only you can follow.

2. **Fetch it**: `hmb setup --only my-kit`

3. **Declare it as a condition** in an experiment configuration, or let the
   scaffold do it:

   ```bash
   hmb experiment new my-run --toolkit my-kit --agent claude-code
   ```

4. **Prove it reaches the agent**:

   ```bash
   hmb generate  --config config/experiments.my-run.yaml --task sqlite-db-truncate --force
   hmb validate  --config config/experiments.my-run.yaml --task sqlite-db-truncate
   hmb preflight --config config/experiments.my-run.yaml --task sqlite-db-truncate
   ```

   Preflight prints what actually appeared in the container. `markers=-` on a
   condition that should carry instructions means the payload never arrived, and
   the run would have measured the baseline three times.

**Before trusting a new snapshot, grep it for absolute paths.** A snapshot is
byte-identical to its commit and the framework deliberately does not rewrite it,
so a `settings.json` registering hooks under `/home/someone/...` will fail
silently inside every container of that condition. Preflight cannot catch this —
the files it asserts on *are* present. See
[troubleshooting](troubleshooting.md#known-confounds).

### Comparing two commits of one repository

Declare the same repository twice at different refs, and give each its own `id`
and `dest`. That measures a change to the **methodology repository**. If instead
you want the agent to modify a feature *inside* a repository at two commits, that
is a benchmark task, not a condition — see
[tasks.md](tasks.md#5-authoring-your-own-task).

---

## 7. Updating a pin

```bash
# 1. Change `ref` in config/sources.yaml
hmb setup --force --only terminal-bench

# 2. Re-derive anything downstream of the suite
hmb catalogue --json-out results/task_catalogue.json
hmb generate --config config/experiments.my-run.yaml --tasks-file config/tasks-my-run.txt --force
hmb validate --config config/experiments.my-run.yaml --tasks-file config/tasks-my-run.txt
```

Record the change with the result. Task-suite membership and axis classification
are derived from task metadata, so a new pin can change which tasks a suite name
resolves to — which is exactly why the SHA is recorded next to the tasks and why
[experiments pin explicit task ids](tasks.md#pinning-a-task-set) rather than a
suite query.

---

## 8. Working on an experiment

Keep the framework on `main` and each experiment on its own branch: results,
scenario files and analysis notebooks belong with the run that produced them.

```bash
git switch -c experiment/my-run
hmb experiment new my-run --toolkit my-kit --agent claude-code --suite spec-dense
# ... run it, report it, analyse it ...
git add config/experiments.my-run.yaml config/tasks-my-run.txt results/
git commit -m "feat: my-run measurement"
```

`results/` is git-ignored except for `.gitkeep`, so committing a result is a
deliberate act: `git add -f results/my-run_report.md`. Raw job output under
`jobs/` is never committed — it is large, and it is reproducible from the pins
plus the configuration.

---

## 9. Uninstalling

```bash
uv tool uninstall harbor-methodology-bench   # removes `hmb`
uv tool uninstall harbor                     # removes the Harbor CLI
rm -rf .venv generated jobs                  # the environment and all local output
docker image prune                           # preflight leaves one thin layer per variant
```
