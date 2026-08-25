---
name: fix
description: Fix findings from /code-review — classifies issues, runs complex fixes in the TDD container on the reviewed branch, applies simple fixes directly. Run after /code-review.
argument-hint: "(no arguments — reads .codezen-review/latest.yaml)"
user-invocable: true
allowed-tools: Read Glob Grep Bash Skill Edit
---

# CodeZen Fix

Fix findings from the most recent `/code-review` run. Classifies each finding as complex (needs tests → container) or simple (one-liner → direct edit), then lets the user decide.

## Step 0 — Resolve launcher path

```bash
if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" ]] && [[ -f "${CLAUDE_PLUGIN_ROOT}/hooks/launch-tdd-container.sh" ]]; then
    CODEZEN_LAUNCHER="${CLAUDE_PLUGIN_ROOT}/hooks/launch-tdd-container.sh"
elif [[ -f "plugin/hooks/launch-tdd-container.sh" ]]; then
    CODEZEN_LAUNCHER="plugin/hooks/launch-tdd-container.sh"
else
    echo "ERROR: launch-tdd-container.sh not found. Is codezen-lite installed as a Claude Code plugin?"
    exit 1
fi
```

Store `CODEZEN_LAUNCHER` — use it for all launcher calls in this skill.

## Step 1 — Load findings

```bash
cat .codezen-review/latest.yaml
```

If the file is missing, stop immediately:
> "No review found. Run `/code-review` first, then re-run `/codezen:fix`."

Parse the YAML. Extract:
- `reviewed_branch` — the branch that was reviewed. If the field is absent (older review files), fall back to: `git branch --show-current`
- All findings across all 6 agents — collect into a flat list with their role (from the parent agent entry), severity, category, description, suggestion, file_path, line_range
- `status`

If `status == PASSED` (no findings at all), stop:
> "Last review passed with no findings — nothing to fix."

Store:
- `REVIEWED_BRANCH` = the reviewed branch name
- `ALL_FINDINGS` = flat list of all findings with severity, category, description, suggestion, file_path, line_range, role

## Step 2 — Credential gate

Run the credential checks now to fail fast before the user picks an option.

```bash
bash "${CODEZEN_LAUNCHER}" --check-setup
bash "${CODEZEN_LAUNCHER}" --check-extra
```

If `SETUP_REQUIRED` or `EXTRA_REQUIRED`, stop:
> "Credentials missing: <list what's missing>. Run `/setup` to add them, then re-run `/codezen:fix`."

## Step 3 — Classify findings

For each finding in `ALL_FINDINGS`, classify as `complex` or `simple` using these rules.

**Complex (→ TDD container, needs tests):**
- Severity is `critical` or `high`
- Category contains any of: `logic-error`, `null-deref`, `missing-error-handling`, `race-condition`, `edge-case`, `n-plus-one`, `blocking-io`, `missing-test`, `no-error-path`, `wrong-behaviour`, `missing-feature`, `uncaught-exception`, `overflow`
- Description mentions any of: "security", "auth", "injection", "XSS", "CSRF", "token", "behaviour changes", "new function", "add test"
- Role is `bug-hunter` or `test-coverage` with severity `medium` or above

**Simple (→ direct edit, no tests needed):**
- Severity is `low` or `info` only
- Category contains any of: `naming`, `style`, `organisation`, `convention`, `dry`, `dead-code`, `unused-import`, `comment`, `doc`
- Description mentions only: rename, remove unused, fix comment, add docstring, whitespace, formatting

When in doubt, classify as `complex`.

Produce two lists:
- `COMPLEX_FINDINGS` — findings classified as complex
- `SIMPLE_FINDINGS` — findings classified as simple

## Step 4 — Present options

Print a grouped summary and wait for user input. For each finding include a one-sentence `Why` derived from the classification rule that triggered it — do not infer new reasoning, map directly from the rule:

| Triggered rule | Why line |
|----------------|----------|
| severity `critical` or `high` | `critical/high severity — needs verified fix` |
| category `logic-error`, `null-deref`, etc. | `logic error — needs regression test` |
| category `missing-test`, `no-error-path` | `missing test — container writes it` |
| description mentions security/auth/injection | `security — behaviour change + injection risk` |
| role `bug-hunter` or `test-coverage`, severity ≥ `medium` | `bug or coverage finding — container verifies` |
| severity `low` or `info`, category `naming`/`style` | `rename/style only — no logic change` |
| category `dead-code`, `unused-import` | `dead code removal — no side effects` |
| category `comment`, `doc` | `comment/doc change — no logic change` |

```
## Fix Options

Complex findings → TDD container (<count>)
  • [SEVERITY] <role>: <description truncated to 80 chars>
    Why container: <one-sentence reason>
  (repeat for each complex finding)

Simple findings → direct edit (<count>)
  • [SEVERITY] <role>: <description truncated to 80 chars>
    Why direct: <one-sentence reason>
  (repeat for each simple finding)

How would you like to proceed?

  A) Fix all in TDD container (recommended — tests verify every fix)
  B) Fix simple findings directly + run complex ones in container
  C) Fix all directly (no container, no tests)
  D) Exit — I'll fix manually
```

Adjust the options shown:
- If `COMPLEX_FINDINGS` is empty: option A is unnecessary — label it differently or remove it, show B as "Fix all directly (no container needed)"
- If `SIMPLE_FINDINGS` is empty: only A and D are meaningful
- Always show D

Wait for user to respond. If user picks **D**: print nothing, exit cleanly.

## Step 5a — Container path (options A or B)

Build the feature slug:
```bash
FEATURE_SLUG="fix-$(echo "${REVIEWED_BRANCH}" | tr '/' '-' | tr '_' '-' | tr '[:upper:]' '[:lower:]' | cut -c1-40)"
```
Example: `feat/user-auth` → `fix-feat-user-auth`

Build the findings prompt. For option A use all findings; for option B use only `COMPLEX_FINDINGS`:

```
Fix the following code review findings on branch <REVIEWED_BRANCH>.

Finding 1 [<SEVERITY> — <role>]:
File: <file_path>, lines <line_range>
Problem: <description>
Fix: <suggestion>

Finding 2 [<SEVERITY> — <role>]:
File: <file_path>, lines <line_range>
Problem: <description>
Fix: <suggestion>

(one block per finding)
```

Announce: "Launching TDD container in fix mode on branch `<REVIEWED_BRANCH>`..."

```bash
bash "${CODEZEN_LAUNCHER}" \
  --feature-slug "${FEATURE_SLUG}" \
  --feature-desc "<FINDINGS_PROMPT>" \
  --fix-branch "${REVIEWED_BRANCH}" \
  --base-branch main \
  --timeout 1800 \
  --max-cycles 10
```

The launcher reads all credentials from macOS Keychain. The container checks out `REVIEWED_BRANCH`, applies fixes, runs tests, and pushes back to the same branch.

Parse the JSON result at the end of launcher output. Store `TESTS_PASSED` and `COMMIT_COUNT`.

## Step 5b — Direct path (options B or C)

For option B: apply `SIMPLE_FINDINGS` directly (complex ones go to Step 5a after).
For option C: apply ALL findings directly.

For each finding:
1. Read the file at `file_path` using the Read tool
2. Apply the change described in `suggestion` using the Edit tool
3. Report: "Fixed [severity] `<file_path>`: <description (first 60 chars)>"

If a finding's `file_path` is `N/A` or the file doesn't exist, skip it and warn:
> "Skipped: <description> — no file path available"

## Step 6 — Show results

After container path (Step 5a):
```
## Fix Results

Branch:  <REVIEWED_BRANCH>
Commits: <COMMIT_COUNT>
Tests:   passed | failed | unknown
```

If `TESTS_PASSED == false`:
> "⚠ Tests were failing when fixes were pushed. Review the output above before merging."

After direct-only path (Step 5b, option C):
```
## Fix Results

Fixed <N> findings directly:
  ✓ [severity] <short description>
  (one line per finding fixed)
```

## Step 7 — Offer re-review

```
Fixes applied. Re-run /code-review to verify?

  1. Yes — run /code-review now
  2. No — done
```

If user picks 2: done.

If user picks 1: invoke the `code-review` skill. After it completes:

- If review returns `status == PASSED`: print "All findings resolved." and stop.
- If review returns new findings: print:

```
/code-review found <N> remaining finding(s). Run /codezen:fix to address them?

  1. Yes — run /codezen:fix now
  2. No — done
```

If user picks 1: invoke the `fix` skill (it will read the new `latest.yaml` automatically).
If user picks 2: done.
