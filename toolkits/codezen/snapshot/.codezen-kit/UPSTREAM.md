# Upstream provenance and the adaptation diff

## What this kit is

CodeZen ships as a Claude Code / Codex **plugin**. It is installed from a
marketplace into a plugin cache, and its skills locate their own supporting
files through the `${CLAUDE_PLUGIN_ROOT}` environment variable that the plugin
runtime sets for them.

This repository is the same methodology reprojected as a **repository
checkout**, so that `claude` and `codex` discover it natively from the working
directory — the way they discover `sdd-agent-kit`. That projection is what
makes CodeZen comparable to other repository-carried methodologies under
`harbor-methodology-bench`, which deploys a repository snapshot into a
container's working directory and has no plugin runtime to set
`${CLAUDE_PLUGIN_ROOT}`.

The projection is mechanical and re-runnable — see
`.codezen-kit/sync-from-plugin.sh`. It is not a fork, and it deliberately keeps
the diff against upstream as small as it can be.

## Source

| Field | Value |
|---|---|
| Upstream plugin | `codezen` |
| Version | `0.2.0` (from `.claude-plugin/plugin.json`) |
| Local checkout synced from | `~/GitRepos/codezen-main` |
| Upstream marketplace | `korzainc/marketplace` → `/plugin install codezen@korza-marketplace` |

At the time of sync the local checkout was **not a git repository**, so there is
no upstream commit SHA to pin. The plugin's declared `version` is the only
available identifier. Any experiment built on this kit should record that
limitation rather than imply commit-level provenance.

## Transformations applied

### 1. Skills duplicated into both discovery paths

The plugin keeps one `skills/` directory and points both runtimes at it through
its manifests. A repository checkout has no manifest to do that, so the skills
are copied to **both** `.claude/skills/` (Claude Code) and `.agents/skills/`
(Codex). The two trees are byte-identical by construction.

Content otherwise unchanged.

### 2. `standards/` paths rewritten — the only edit to skill text

Upstream, seven skills read the shared standards library through
`${CLAUDE_PLUGIN_ROOT}/standards/...`. Unlike every other use of that variable
(see §3), these references have **no fallback**. In a plain checkout the
variable is unset, so the path resolves to `/standards/...` and every read
fails — silently, because a skill that cannot read its standards still runs.

Rewritten to repository-relative:

```
${CLAUDE_PLUGIN_ROOT}/standards/baseline.md   →   standards/baseline.md
```

Affected: `tdd`, `noc-tdd`, `code-review`, `security-review`, and any other
skill referencing the library. `noc-tdd` additionally carried two sentences of
prose instructing the agent to expand the variable before reading; with the
paths now relative there is nothing to expand, so that instruction is replaced
with a statement that the paths are repository-relative.

This is the whole of the skill-text diff. Everything else below adds files
without editing upstream content.

### 3. `plugin/hooks/` — no rewrite needed

Every *other* `${CLAUDE_PLUGIN_ROOT}` reference in the shipped skills is already
guarded, with a repository-relative fallback that upstream wrote itself:

```bash
if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" ]] && [[ -f "${CLAUDE_PLUGIN_ROOT}/hooks/launch-tdd-container.sh" ]]; then
    CODEZEN_LAUNCHER="${CLAUDE_PLUGIN_ROOT}/hooks/launch-tdd-container.sh"
elif [[ -f "plugin/hooks/launch-tdd-container.sh" ]]; then
    CODEZEN_LAUNCHER="plugin/hooks/launch-tdd-container.sh"
```

So the plugin's `hooks/` directory is copied to `plugin/hooks/` and the
**unmodified** upstream skill text resolves through its own `elif`. Confirmed
for `tdd`, `fix`, `setup` and `brainstorm` — the four skills that call a script.

### 4. `block-env-edits` hook rewired to the project directory

Upstream registers the hook in `hooks/hooks.json` (Claude Code) and
`hooks/codex-hooks.json` (Codex), both as `${CLAUDE_PLUGIN_ROOT}` /
`${PLUGIN_ROOT}` paths that only a plugin runtime sets. A repository checkout
declares its hooks in `.claude/settings.json` instead, so that file is added
here with the command rewritten to `$CLAUDE_PROJECT_DIR/plugin/hooks/block-env-edits.sh`.

The original `hooks.json` and `codex-hooks.json` are still shipped under
`plugin/hooks/` for reference; nothing reads them in this layout.

**Unverified:** whether a project-level `.claude/settings.json` hook fires for a
non-interactive `claude` run inside a container, and whether Codex honours any
project-level hook file at all. Treat the hook as *declared but not proven*
until a trajectory shows it firing. This is exactly the kind of assumption that
should be read out of telemetry rather than assumed.

## Known asymmetries against `sdd-agent-kit`

Worth recording because they are confounds in any head-to-head comparison, not
defects:

| | `sdd-agent-kit` | `codezen-agent-kit` |
|---|---|---|
| Skills | 7, all runnable anywhere | 11, of which 4 runnable in a plain checkout |
| Hooks | none | one `PreToolUse` hook |
| Reference library read at runtime | no | yes (`standards/`, 20 files) |
| Provenance | git commit SHA | plugin `version` only |
| Repository bulk beyond the method | `docs/`, `tests/`, `tools/`, `scripts/`, `kits/` | `standards/`, `plugin/` |

The skill-count difference is the sharpest one: seven of CodeZen's eleven skills
need something a benchmark container does not have (a Docker daemon, a running
system under test, interactive input, or an MCP server). An experiment that
ships all eleven is measuring the plugin *as shipped*, including its
portability; one that ships only the four is measuring its *method*. Those are
different questions and should be separate conditions.
