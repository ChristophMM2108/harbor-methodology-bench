---
name: noc-fix
description: Use after /code-review to apply its findings without launching a container — when the session is already inside a container, or Docker is unavailable or unwanted. Reads the latest review from .codezen-review/latest.yaml.
argument-hint: "(no arguments — reads .codezen-review/latest.yaml)"
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Skill, LSP
---

# CodeZen noc-fix — Containerless Fix

`noc` = **no container**. Applies the findings from the most recent `/code-review`
**directly in this session** — no Docker, no inner Claude. Complex findings are fixed
**test-first** (a regression test, then the fix); simple findings are direct edits. Fixes
land on the reviewed branch, get committed one finding at a time, and are pushed back.

Unlike the container `fix` skill, this session writes the tests and fixes itself — hence
`Write`/`Edit`/`LSP` are allowed. There is no credential gate and no Docker preflight.

> **Fixes in place, not in a worktree.** `fix` operates on the *existing reviewed branch*
> (usually the one you're already on), so a worktree would only collide with "branch already
> checked out." This skill works on the reviewed branch directly, and therefore requires a
> clean working tree (Step 1).

> **Shell state:** the working directory persists between Bash calls, but **environment
> variables do not**. Each bash block below re-establishes what it needs — where a block
> shows `REVIEWED_BRANCH="..."`, paste the value from Step 0.

## Quick Reference

| Step | What happens | Hard stop if… |
|------|-------------|---------------|
| 0 — Load findings | Read `.codezen-review/latest.yaml` → `REVIEWED_BRANCH` + `ALL_FINDINGS` | file missing / `status == PASSED` |
| 1 — Preflight | git identity, `gh auth`, clean tree, then be on the reviewed branch | identity/auth missing, dirty tree |
| 2 — Classify | Set aside N/A-file findings, then split into complex / simple | — |
| 3 — Present options | User picks test-first / direct / exit | — |
| 4 — Apply fixes | Complex → TDD; simple → direct edit; commit each `fix: …` | — |
| 5 — Verify | Detect language, run full test suite | — (warn only) |
| 6 — Push | `git push` the reviewed branch | push rejected (branch diverged) |
| 7 — Re-review | Report results; offer to run `/code-review` | — |

---

## Step 0 — Load findings

```bash
cat .codezen-review/latest.yaml
```

If the file is missing, stop: "No review found. Run `/code-review` first, then re-run `/noc-fix`."

Parse the YAML and extract:
- `reviewed_branch` — the reviewed branch. If absent (older files), fall back to `git branch --show-current`.
- All findings across every agent → a flat list, each with role, severity, category, description, suggestion, file_path, line_range.
- `status`.

If `status == PASSED` (no findings), stop: "Last review passed with no findings — nothing to fix."

Store `REVIEWED_BRANCH` and `ALL_FINDINGS`.

---

## Step 1 — Preflight (no Docker, no credential gate)

First, the checks (this block only reports):
```bash
git config user.name  >/dev/null 2>&1 || git config --global user.name  >/dev/null 2>&1 || echo "MISSING: git user.name"
git config user.email >/dev/null 2>&1 || git config --global user.email >/dev/null 2>&1 || echo "MISSING: git user.email"
gh auth status >/dev/null 2>&1 || echo "MISSING: gh auth"                              # needed for the Step 6 push
[ -n "$(git status --porcelain | grep -v '^??')" ] && echo "MISSING: clean working tree"  # ?? = untracked, which is OK
```

**If any `MISSING:` line printed, STOP** with the matching guidance (configure git identity /
`gh auth login` / commit or stash first). In particular, do **not** run the checkout below
while the tree is dirty — `git checkout` would carry your uncommitted edits onto the reviewed
branch.

Only once the tree is clean, get onto the reviewed branch:
```bash
REVIEWED_BRANCH="feat/user-auth"        # ← paste your Step 0 REVIEWED_BRANCH
if [ "$(git branch --show-current)" != "$REVIEWED_BRANCH" ]; then
  git fetch origin --quiet
  git checkout "$REVIEWED_BRANCH" || { echo "cannot checkout $REVIEWED_BRANCH"; exit 1; }
fi
```

---

## Step 2 — Classify findings

**First, set aside un-fixable findings:** any finding whose `file_path` is `N/A` or missing →
`SKIPPED_FINDINGS` (reported, never auto-fixed). Classify only the rest.

For each remaining finding, classify as `complex` or `simple`.

**Complex (→ test-first fix):**
- Severity `critical` or `high`.
- Category contains any of: `logic-error`, `null-deref`, `missing-error-handling`, `race-condition`, `edge-case`, `n-plus-one`, `blocking-io`, `missing-test`, `no-error-path`, `wrong-behaviour`, `missing-feature`, `uncaught-exception`, `overflow`.
- Description mentions any of: "security", "auth", "injection", "XSS", "CSRF", "token", "behaviour changes", "new function", "add test".
- Role is `bug-hunter` or `test-coverage` with severity `medium` or above.

**Simple (→ direct edit):**
- Severity `low` or `info` only.
- Category contains any of: `naming`, `style`, `organisation`, `convention`, `dry`, `dead-code`, `unused-import`, `comment`, `doc`.
- Description mentions only: rename, remove unused, fix comment, add docstring, whitespace, formatting.

When in doubt, classify as `complex`. Produce `COMPLEX_FINDINGS`, `SIMPLE_FINDINGS`, `SKIPPED_FINDINGS`.

If both `COMPLEX_FINDINGS` and `SIMPLE_FINDINGS` are empty (every finding was set aside), stop:
list `SKIPPED_FINDINGS` and report "Nothing fixable — all findings lack a file path."

---

## Step 3 — Present options

Print a grouped summary and wait for input. Each finding's `Why` line maps directly from the
rule that triggered its classification (do not invent new reasoning). When a finding matches
multiple rows, use the first (topmost) matching row:

| Triggered rule | Why line |
|----------------|----------|
| severity `critical`/`high` | `critical/high severity — needs a verified fix` |
| category `logic-error`, `null-deref`, etc. | `logic error — needs a regression test` |
| category `missing-test`, `no-error-path` | `missing test — write it test-first` |
| description mentions security/auth/injection | `security — behaviour change + injection risk` |
| role `bug-hunter`/`test-coverage`, severity ≥ `medium` | `bug or coverage finding — verify with a test` |
| severity `low`/`info`, category `naming`/`style` | `rename/style only — no logic change` |
| category `dead-code`, `unused-import` | `dead code removal — no side effects` |
| category `comment`, `doc` | `comment/doc change — no logic change` |

```
## Fix Options

Complex findings → test-first (<count>)
  • [SEVERITY] <role>: <description ≤80 chars>
    Why test-first: <Why line>

Simple findings → direct edit (<count>)
  • [SEVERITY] <role>: <description ≤80 chars>
    Why direct: <Why line>

Skipped — no file path (<count>)          # only if SKIPPED_FINDINGS is non-empty
  • [SEVERITY] <role>: <description ≤80 chars>

How would you like to proceed?
  A) Fix all test-first (recommended — a regression test verifies every fix)
  B) Fix simple directly + complex test-first
  C) Fix all directly (no tests)
  D) Exit — I'll fix manually
```

Adjust: if `COMPLEX_FINDINGS` is empty, collapse A into "fix all directly"; if
`SIMPLE_FINDINGS` is empty, only A and D are meaningful. Always show D. On **D**, exit cleanly.

---

## Step 4 — Apply fixes

Work on the reviewed branch (Step 1 put you there). Commit **one finding per commit** with
message `fix: <short description>`. `SKIPPED_FINDINGS` are never touched — list them at the end
as "Skipped: <description> — no file path available". Count the `fix:` commits you create; that
is the "Commits" number reported in Step 7.

**Complex findings (test-first)** — for each, invoke `superpowers:test-driven-development`:
1. **RED:** write a test that reproduces the finding (fails for the reason described).
2. **GREEN:** apply the fix from `suggestion` until the test passes; keep existing tests green.
3. Commit the test + fix together: `fix: <description>`.
Apply that skill's LSP checkpoints if the `LSP` tool is functional for this repo (otherwise
skip — never block on it).

**Simple findings (direct edit)** — for each: Read `file_path`, apply `suggestion` with Edit,
commit `fix: <description>`. Report: "Fixed [severity] `<file_path>`: <description ≤60 chars>".

(Option B does simple direct edits first, then complex test-first. Option C does everything as
direct edits — no tests.)

---

## Step 5 — Verify

Detect the language, then run the full suite on the branch:
```bash
if [ -f pyproject.toml ] || [ -f setup.py ]; then
  pytest -v --tb=short
elif [ -f package.json ]; then
  npm test
else
  echo "no recognised test runner — skipping verification"
fi
```
Record pass/fail. A failing suite does not abort — it is surfaced in Step 7; fixes are still
pushed for review.

---

## Step 6 — Push

In-place fixes only *add* commits on top of the branch tip, so a plain push is correct:
```bash
REVIEWED_BRANCH="feat/user-auth"        # ← paste your Step 0 REVIEWED_BRANCH
git push origin "$REVIEWED_BRANCH"
```
If the push is **rejected** (non-fast-forward), the remote branch advanced since you started —
**STOP and report** it. Do **not** fetch-and-force: your commits are safe locally, and a forced
push here could overwrite someone else's work on the branch.

---

## Step 7 — Results + re-review

```
## noc-fix Results
Branch:  <REVIEWED_BRANCH>
Commits: <number of fix: commits created this session>
Tests:   passed / failed
Skipped: <N> finding(s) with no file path   # only if any
```
If tests failed: "⚠ Tests were failing when fixes were pushed. Review before merging."

Then offer:
```
Fixes applied. Re-run /code-review to verify?
  1. Yes — run /code-review now
  2. No — done
```
On **1**, invoke the `code-review` skill. If it returns `PASSED`, print "All findings
resolved." Otherwise report the remaining count and offer to re-run `/noc-fix` (it will read
the new `latest.yaml`). On **2**, done.

---

## Rules

- **This session writes the tests and fixes.** For complex findings follow `superpowers:test-driven-development` exactly.
- **Fixes in place on the reviewed branch** — no worktree, no new branch. Requires a clean tree; a dirty tree must stop Step 1 *before* the checkout.
- **One finding per commit** (`fix: …`), so each change is revertible on its own.
- **Plain push, never force.** A rejected push means the branch diverged — stop and report; don't fetch-and-force.
- **No container, no credential gate, no Docker preflight.**
- **Never invent a finding's reasoning** — the `Why` line maps from the classification table only.
- **When in doubt, classify complex** (test-first) rather than simple.
- **LSP is optional** — skip its checkpoints when the tool isn't functional; never block on it.
