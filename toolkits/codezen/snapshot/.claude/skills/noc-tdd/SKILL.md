---
name: noc-tdd
description: Use when implementing a feature or bugfix in a codezen project and you want it built test-first without launching a container (already inside a container, or Docker is unavailable or unwanted). Accepts a feature description, a GitHub or Linear issue, or a filepath.
argument-hint: "<feature-description | github/linear-issue | filepath> [--keep-worktree]"
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Skill, LSP
---

# CodeZen noc-tdd — Containerless Inline TDD

`noc` = **no container**. Runs the full Red-Green-Refactor cycle **directly in this
session** — no Docker, no inner Claude. Creates an isolated git worktree, drives TDD to
green, commits each cycle, and pushes a feature branch. Runs identically on the host or
inside a container.

Unlike the container `tdd` skill (which only orchestrates), **this session writes the code
itself** — hence `Write`/`Edit` are allowed here.

> **Shell state:** the working directory persists between Bash calls, but **environment
> variables do not**. Each bash block below re-establishes the variables it needs. Where a
> block shows `FEATURE_SLUG="..."`, paste the slug you derived in Step 1.

## Quick Reference

| Step | What happens | Hard stop if… |
|------|-------------|---------------|
| 0 — Parse args | Detect `--keep-worktree`; the rest is the description | no description left |
| 1 — Resolve input | GitHub/Linear issue, filepath, or text → `FEATURE_DESCRIPTION` + `FEATURE_SLUG` | empty input |
| 2 — Load standards | Read baseline + all layer standards | — |
| 3 — Detect language + LSP | Glob manifests → `LANGUAGES` + `LSP_AVAILABLE` | never blocks — warn only |
| 4 — Git preflight | git identity, `origin`, `gh auth`, fetch, detect base branch | identity/remote/auth missing |
| 5 — Create worktree | `git worktree add -B feat/<slug>` from `origin/<base>` | cannot create worktree |
| 6 — TDD | Run `superpowers:test-driven-development`, commit each cycle | — |
| 7 — Verify | Run full test suite in worktree | — (warn only) |
| 8 — Push | `git push --force-with-lease` | push fails after retry |
| 9 — Cleanup | Remove worktree (keep on `--keep-worktree`) | — |
| 10 — Summary | Branch, commits, tests; suggest reviews | — |

---

## Step 0 — Parse arguments

`--keep-worktree` is the **only** recognized flag. If it appears as a standalone token,
set `KEEP_WORKTREE=true` and remove it. **Everything else is the feature description** —
including any `--flags` inside it (e.g. `add a --json flag`). Do **not** treat words inside
the description as options.

- After removing `--keep-worktree`, if nothing remains → stop:
  "Usage: `/noc-tdd <feature-description | URL | filepath> [--keep-worktree]`"
- Default `KEEP_WORKTREE=false`.

---

## Step 1 — Resolve feature description

Parse the description by type, in this precedence order: GitHub issue → Linear issue → filepath → plain text.

**GitHub issue URL** (`https://github.com/<owner>/<repo>/issues/<number>`):
```bash
ISSUE_NUM=123; OWNER_REPO="owner/repo"          # ← parsed from the URL
gh issue view "$ISSUE_NUM" --repo "$OWNER_REPO" --json title,body,labels,comments
```
Use title, body, and clarifying comments as `FEATURE_DESCRIPTION`. If `gh` fails, stop.

**Linear issue** — a URL (`https://linear.app/<workspace>/issue/<IDENTIFIER>/...`) or a bare
identifier matching `^[A-Z][A-Z0-9]*-[0-9]+$` (e.g. `ENG-123`). Linear has no `gh`-equivalent
CLI, so this uses the GraphQL API and **requires `LINEAR_API_KEY` in env** (Linear → Settings
→ API → Personal API keys):
```bash
LINEAR_ID="ENG-123"        # ← the identifier from the URL or the bare token
[ -n "${LINEAR_API_KEY:-}" ] || { echo "LINEAR_API_KEY not set — export it and re-run"; exit 1; }
QUERY='query($id:String!){issue(id:$id){identifier title description comments{nodes{body}}}}'
# Capture the response (don't pipe curl→jq: a piped curl failure exits 0 and yields empty output)
RESP="$(curl -sS https://api.linear.app/graphql \
  -H "Authorization: ${LINEAR_API_KEY}" -H "Content-Type: application/json" \
  --data "$(jq -n --arg q "$QUERY" --arg id "$LINEAR_ID" '{query:$q,variables:{id:$id}}')")" \
  || { echo "Linear API request failed"; exit 1; }
# Linear returns HTTP 200 with data.issue=null or an errors[] on a bad id — catch both
echo "$RESP" | jq -e '.data.issue != null' >/dev/null 2>&1 \
  || { echo "Linear issue ${LINEAR_ID} not found or API error: $(echo "$RESP" | jq -c '.errors // .')"; exit 1; }
echo "$RESP" | jq -r '.data.issue | "\(.identifier) \(.title)\n\n\(.description // "")\n\n" + ([.comments.nodes[].body] | join("\n---\n"))'
```
Use the identifier, title, description, and comments as `FEATURE_DESCRIPTION`. The
`Authorization` header is the **raw** key (no `Bearer`). If `curl`/`jq` fails, the key is
missing, or `.data.issue` is null, stop and report.

**Filepath** (starts with `./`, `/`, `../`, or the path exists): read it → `FEATURE_DESCRIPTION`. If not found, stop.

**Plain text**: use it directly as `FEATURE_DESCRIPTION`.

**Derive `FEATURE_SLUG`** deterministically:
- GitHub/Linear issue → slugify the issue title. Filepath → the filename stem. Plain text → slugify the description.
- Slugify = lowercase, replace runs of non-alphanumerics with `-`, trim leading/trailing `-`, cap at 50 chars:
```bash
printf '%s' "add a --json output flag to the export command" \
  | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g' | cut -c1-50 | sed -E 's/-+$//'
# -> add-a-json-output-flag-to-the-export-command
```
Record the resulting `FEATURE_SLUG` string — you paste it into the bash blocks below.

---

## Step 2 — Load standards

Standards paths are relative to the repository root — read them directly
from the working directory. Read:

- `standards/baseline.md`
- Every file under `standards/layers/` (testing, code_quality, and domain layers).

---

## Step 3 — Detect language + LSP

Glob for manifests and map to a language:

| Manifest | Language |
|---|---|
| `package.json` | typescript / javascript |
| `pyproject.toml`, `setup.py` | python |
| `go.mod` | go |
| `Cargo.toml` | rust |
| `Gemfile` | ruby |
| `pom.xml`, `build.gradle`, `build.gradle.kts` | java |
| `composer.json` | php |

Multiple manifests → list all (primary first). None → infer from source extensions.
Undeterminable → assume `python`. Store `LANGUAGES`.

The `LSP` tool is allowed by this skill but is not functional for every project. Set
`LSP_AVAILABLE=true` only after a quick `LSP` call actually succeeds for this repo;
otherwise `false` (and when unsure, `false`). LSP is optional — the Step 6 checkpoints are
skipped when `false`. Never blocks — warn only.

---

## Step 4 — Git preflight (no Docker)

```bash
git config user.name  >/dev/null 2>&1 || git config --global user.name  >/dev/null 2>&1 || echo "MISSING: git user.name"
git config user.email >/dev/null 2>&1 || git config --global user.email >/dev/null 2>&1 || echo "MISSING: git user.email"
git remote get-url origin >/dev/null 2>&1 || echo "MISSING: origin remote"
gh auth status >/dev/null 2>&1 || echo "MISSING: gh auth"

# Sync refs and detect the repo's real default branch (not a hardcoded 'main')
git fetch origin --quiet
git remote set-head origin --auto >/dev/null 2>&1 || true
BASE_BRANCH="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')"
echo "base branch: ${BASE_BRANCH:-main}"
```

Any `MISSING:` line → stop with the matching guidance (configure git identity /
add `origin` / `gh auth login`). No working-tree cleanliness check on the caller — the
worktree isolates from it.

---

## Step 5 — Create worktree

The worktree isolates TDD from the caller's working tree, index, and current branch, and
behaves identically in a container or on the host.

```bash
FEATURE_SLUG="add-a-json-output-flag-to-the-export-command"   # ← paste your Step 1 slug
BASE_BRANCH="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')"; BASE_BRANCH="${BASE_BRANCH:-main}"
# Derive REPO from the MAIN worktree (correct even if the caller cwd is itself a linked worktree)
MAIN_REPO="$(git worktree list --porcelain | awk '/^worktree /{sub(/^worktree /,""); print; exit}')"
WT_PATH="${TMPDIR:-/tmp}/noc-tdd-$(basename "$MAIN_REPO")-${FEATURE_SLUG}"

# Remove a stale worktree from a previous run with the same slug
if git worktree list --porcelain | grep -qF "$WT_PATH" || [ -e "$WT_PATH" ]; then
  git worktree remove --force "$WT_PATH" 2>/dev/null || true
  git worktree prune
  rm -rf "$WT_PATH" 2>/dev/null || true   # also clear a plain leftover dir (e.g. after a crash)
fi

# Create the worktree on feat/<slug> from the remote base tip, then enter it
git worktree add -B "feat/${FEATURE_SLUG}" "$WT_PATH" "origin/${BASE_BRANCH}"
cd "$WT_PATH" && echo "WT_PATH=$WT_PATH"
```

If the branch is already checked out elsewhere or the add fails, stop and report. The cwd
now persists at `$WT_PATH` for the following steps. The Step 9 cleanup blocks recompute
`WT_PATH` with the identical formula (`${TMPDIR:-/tmp}` + main-repo name + slug); the value
echoed here is your check that they match.

> **Deps:** project dependencies are assumed installed. Only if a TDD cycle genuinely
> needs a new library, add it to the manifest and install it before the first failing test.

---

## Step 6 — Run TDD

Invoke `superpowers:test-driven-development` and follow it exactly — do not deviate from
its Red-Green-Refactor cycle.

**Multi-tier tests.** After the unit cycle, also write integration tests appropriate to the
project type. Mocks isolate a unit; they do not test wiring. Red flag: a test for a public
endpoint that calls an internal helper directly. Place integration tests in
`tests/integration/` (or mark `@pytest.mark.integration`). Skip integration tests only if
the feature is purely internal with no external boundaries.

**LSP checkpoints (if `LSP_AVAILABLE`).**
- *Red:* `getDiagnostics` on the test file — confirm a "missing symbol / not implemented" diagnostic (valid RED), not a syntax/import error (broken test — fix first).
- *Green:* `getDiagnostics` on test + implementation before running the suite.
- *Refactor:* `findReferences` on any renamed symbol to confirm no call site silently breaks.

**Activity log.** Maintain `log.md` in the worktree root, updated **each cycle**:
```markdown
# TDD Activity Log
**Feature:** <slug>   **Branch:** feat/<slug>   **Project type:** <type>

## Dependencies Added
- <package>: <why> (or "none")

## TDD Cycles
### Cycle N: <description>
- **RED:** wrote `<test>` in `<file>` — tests <behaviour>
- **GREEN:** implemented `<symbol>` in `<file>` — <key decision>
- **REFACTOR:** <what, or "none">

## Integration Tests Written
- `<file>`: <boundary flow> (or "none written" + reason)

## Key Decisions
- <decision>: <rationale>
```
Do **not** commit `log.md` if it is gitignored.

**Commit each Red-Green-Refactor cycle** with a clear message; unit tests and integration
tests as separate commits. Soft cap of ~10 cycles.

---

## Step 7 — Final verification

Run the full suite in the worktree (cwd is `$WT_PATH`):
```bash
pytest -v --tb=short     # python
npm test                 # node
```
Record pass/fail. A failing suite does not abort — it selects the failure cleanup path in
Step 9, but the branch is still pushed for review.

---

## Step 8 — Push

```bash
FEATURE_SLUG="add-a-json-output-flag-to-the-export-command"   # ← same slug
git push origin "feat/${FEATURE_SLUG}" --force-with-lease
```
On failure, `git fetch origin` and retry once. If it still fails, stop and report — and do
**not** delete the worktree, so state can be recovered.

---

## Step 9 — Cleanup

The durable artifact is the **pushed branch**, not the worktree — so clean by default.
`git worktree remove` refuses while cwd is inside the worktree, so each path first `cd`s to
the main worktree (found via `git worktree list`, which works from inside a linked worktree).

**Success** (final tests passed, branch pushed):
```bash
FEATURE_SLUG="add-a-json-output-flag-to-the-export-command"   # ← same slug
MAIN_REPO="$(git worktree list --porcelain | awk '/^worktree /{sub(/^worktree /,""); print; exit}')"
WT_PATH="${TMPDIR:-/tmp}/noc-tdd-$(basename "$MAIN_REPO")-${FEATURE_SLUG}"   # must equal the WT_PATH Step 5 printed
cd "$MAIN_REPO"
git worktree remove --force "$WT_PATH"
git worktree prune
```

**Failure / timeout (default):**
```bash
FEATURE_SLUG="add-a-json-output-flag-to-the-export-command"   # ← same slug
git add -A && git commit -m "wip: partial TDD state (tests failing)" || true   # run from inside the worktree
git push origin "feat/${FEATURE_SLUG}" --force-with-lease || true
MAIN_REPO="$(git worktree list --porcelain | awk '/^worktree /{sub(/^worktree /,""); print; exit}')"
WT_PATH="${TMPDIR:-/tmp}/noc-tdd-$(basename "$MAIN_REPO")-${FEATURE_SLUG}"   # must equal the WT_PATH Step 5 printed
cd "$MAIN_REPO"
git worktree remove --force "$WT_PATH"
git worktree prune
echo "Reproduce: git fetch && git checkout feat/${FEATURE_SLUG}"
```

**`--keep-worktree` set:** skip the `git worktree remove`/`prune`; print the `$WT_PATH`
instead.

---

## Step 10 — Summary

Compute the commit count (the branch persists after worktree removal):
```bash
FEATURE_SLUG="add-a-json-output-flag-to-the-export-command"   # ← same slug
BASE_BRANCH="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')"; BASE_BRANCH="${BASE_BRANCH:-main}"
git rev-list --count "origin/${BASE_BRANCH}..feat/${FEATURE_SLUG}"
```

Print:
```
## noc-tdd Complete
Branch:   feat/<slug>
Commits:  <count>
Tests:    passed / failed
Log:      log.md present / missing
```
On failure also print the repro line; on `--keep-worktree` print the worktree path.

Then suggest optional follow-ups (do **not** run them):
> Recommended next: run `/security-review` and `/code-review` on `feat/<slug>` before merging.

---

## Rules

- **This session writes the code.** Follow `superpowers:test-driven-development` exactly.
- **Worktree isolates.** Never modify the caller's working tree, index, or current branch.
- **Clean by default.** Remove the worktree unless `--keep-worktree`; reproducibility comes
  from the pushed branch, so always push (even partial work on failure).
- **`cd` out before removing a worktree** — use the `git worktree list` main path, never `cd -`.
- **Detect the base branch** — never hardcode `main`.
- **No container, no credential gate, no infra emulators, no dependency-install step.**
- **Ends at push.** No security review, no PR — only suggest them.
- **Words inside the feature description are not flags** — only `--keep-worktree` is.
- **Feature description must be resolved** before Step 5.
