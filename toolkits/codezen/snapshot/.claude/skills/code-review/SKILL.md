---
name: code-review
description: Multi-agent parallel code review — spec adherence, standards and best practices, code quality, test coverage, performance, and bug detection.
argument-hint: "[spec-file] [PR# | branch | file paths] (all optional)"
user-invocable: true
allowed-tools: Read Glob Grep Bash Agent AskUserQuestion
---

# CodeZen Code Review

Runs 7 parallel reviewer agents against new code (PR diff, branch diff, or specified files), aggregates findings into a descriptive PASSED | FAILED report, and writes results to `.codezen-review/latest.yaml`.

## Quick Reference

| Step | What happens |
|------|-------------|
| 1 — Parse args | Detect spec file, diff source |
| 2 — Auto-discover | Find spec (README/arg/ask) + standards (CLAUDE.md) |
| 3 — Fetch diff | PR diff / branch diff / file read |
| 4 — Spawn agents | 6 parallel reviewers |
| 5 — Aggregate | Collect YAML results |
| 6 — Report | Print summary + write `.codezen-review/latest.yaml` |

---

## Step 1 — Parse Arguments

Split `$ARGUMENTS` into positional tokens by whitespace.

**Argument detection rules (in order):**

| Argument shape | Detection rule | Behavior |
|---------------|----------------|----------|
| None | No args | `git diff origin/main...HEAD`, fallback `git diff HEAD` |
| Pure integer (e.g. `42`) | `[[ $arg =~ ^[0-9]+$ ]]` | `gh pr diff 42` |
| Ends in `.md` (e.g. `spec.md`) | `.md` extension | Explicit spec file; diff source defaults to git diff |
| Existing file path (non-`.md`) | `test -f $arg` | Read file directly as code to review |
| Anything else (e.g. `feat/auth`) | Fallthrough | Branch name: `git diff main..<arg>` |

**Multiple arguments:** if first arg ends in `.md`, it is the spec file; remaining args are the diff source.

Store:
- `SPEC_ARG` — explicit spec file path (or empty)
- `DIFF_SOURCE` — how to get the diff: `pr:<number>`, `branch:<name>`, `files:<paths>`, or `gitdiff`

Record branch and timestamp:
```bash
REVIEWED_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
REVIEWED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u)
```

---

## Step 2 — Auto-Discover Spec + Standards

### Spec (use first found)
1. `SPEC_ARG` if set → read that file
2. `README.md` in repo root → read it
3. Neither found → use AskUserQuestion:
   > "What is this project about, or where can I find the project specs?"
   Store answer as `SPEC_CONTENT`.

### Standards (use first found)
1. `.claude/CLAUDE.md` in repo root
2. `CLAUDE.md` in repo root
3. Not found → `STANDARDS_CONTENT="Use general best practices: clean code, SOLID, language idioms."`

Store both `SPEC_CONTENT` and `STANDARDS_CONTENT` before proceeding.

---

## Step 3 — Fetch Diff / Code

Based on `DIFF_SOURCE`:

**`gitdiff`:**
```bash
# Try origin/main first, fall back to HEAD
git diff origin/main...HEAD 2>/dev/null || git diff HEAD
```

**`pr:<number>`:**
```bash
gh pr diff <number>
```
If `gh` fails → stop and report error.

**`branch:<name>`:**
```bash
git diff main..<name>
```

**`files:<paths>`:**
Read each file directly using the Read tool.

Store result as `DIFF_CONTENT`. If empty → stop: "Nothing to review. No diff or file content found."

---

## Step 4 — Spawn 6 Parallel Reviewer Agents

Spawn all 6 agents simultaneously in a single message. Each agent receives a role-specific prompt containing:
- Its role and focus area
- `DIFF_CONTENT`
- `SPEC_CONTENT` (only for spec-adherence)
- `STANDARDS_CONTENT` (only for standards-and-practices)
- Output format instructions (YAML below)

### Agent Prompts

#### spec-adherence
```
You are a spec adherence reviewer. Review the code diff for alignment with the project spec/requirements.

PROJECT SPEC:
<SPEC_CONTENT>

CODE DIFF:
<DIFF_CONTENT>

Severity rubric:
- critical: runtime crash, data loss, security vulnerability, complete feature breakage
- high: wrong behavior in a realistic scenario, missing error handling that will surface in prod, clear spec violation
- medium: code works but is fragile, hard to maintain, or partially misses spec intent
- low: style/convention deviation, minor naming issue, small DRY violation
- info: observation or suggestion with no negative consequence if ignored

Output ONLY valid YAML in this exact format:
role: spec-adherence
approved: true|false
findings:
  - severity: critical|high|medium|low|info
    category: <category>
    description: <full problem description>
    suggestion: <concrete fix>
    file_path: <path or "unknown">
    line_range: <range or "unknown">
summary: <one paragraph>

approved is false if any critical, high, or medium finding exists. No findings = approved: true.
```

#### code-reviewer
```
You are a code correctness reviewer. Focus on logic errors, null handling, error handling, and correctness bugs.

CODE DIFF:
<DIFF_CONTENT>

Severity rubric:
- critical: runtime crash, data loss, security vulnerability, complete feature breakage
- high: wrong behavior in a realistic scenario, missing error handling that will surface in prod, clear spec violation
- medium: code works but is fragile, hard to maintain, or partially misses spec intent
- low: style/convention deviation, minor naming issue, small DRY violation
- info: observation or suggestion with no negative consequence if ignored

Output ONLY valid YAML in this exact format:
role: code-reviewer
approved: true|false
findings:
  - severity: critical|high|medium|low|info
    category: <category>
    description: <full problem description>
    suggestion: <concrete fix>
    file_path: <path or "unknown">
    line_range: <range or "unknown">
summary: <one paragraph>

approved is false if any critical, high, or medium finding exists. No findings = approved: true.
```

#### standards-and-practices
```
You are a standards and best practices reviewer. Review the code diff for two things:
1. Compliance with project-specific conventions and style (naming, structure, patterns used in this codebase).
2. Universal engineering principles: SOLID, DRY, design patterns, and code organization.

PROJECT STANDARDS:
<STANDARDS_CONTENT>

CODE DIFF:
<DIFF_CONTENT>

Severity rubric:
- critical: runtime crash, data loss, security vulnerability, complete feature breakage
- high: wrong behavior in a realistic scenario, missing error handling that will surface in prod, clear spec violation
- medium: code works but is fragile, hard to maintain, or partially misses spec intent
- low: style/convention deviation, minor naming issue, small DRY violation
- info: observation or suggestion with no negative consequence if ignored

Output ONLY valid YAML in this exact format:
role: standards-and-practices
approved: true|false
findings:
  - severity: critical|high|medium|low|info
    category: <category>
    description: <full problem description>
    suggestion: <concrete fix>
    file_path: <path or "unknown">
    line_range: <range or "unknown">
summary: <one paragraph>

approved is false if any critical, high, or medium finding exists. No findings = approved: true.
```

#### test-coverage
```
You are a test coverage reviewer. Focus on whether new code has tests, coverage gaps, and test quality.

CODE DIFF:
<DIFF_CONTENT>

Severity rubric:
- critical: runtime crash, data loss, security vulnerability, complete feature breakage
- high: wrong behavior in a realistic scenario, missing error handling that will surface in prod, clear spec violation
- medium: code works but is fragile, hard to maintain, or partially misses spec intent
- low: style/convention deviation, minor naming issue, small DRY violation
- info: observation or suggestion with no negative consequence if ignored

Output ONLY valid YAML in this exact format:
role: test-coverage
approved: true|false
findings:
  - severity: critical|high|medium|low|info
    category: <category>
    description: <full problem description>
    suggestion: <concrete fix>
    file_path: <path or "unknown">
    line_range: <range or "unknown">
summary: <one paragraph>

approved is false if any critical, high, or medium finding exists. No findings = approved: true.
```

#### performance-review
```
You are a performance reviewer. Focus on N+1 queries, blocking I/O, algorithmic complexity, and memory issues.

CODE DIFF:
<DIFF_CONTENT>

Severity rubric:
- critical: runtime crash, data loss, security vulnerability, complete feature breakage
- high: wrong behavior in a realistic scenario, missing error handling that will surface in prod, clear spec violation
- medium: code works but is fragile, hard to maintain, or partially misses spec intent
- low: style/convention deviation, minor naming issue, small DRY violation
- info: observation or suggestion with no negative consequence if ignored

Output ONLY valid YAML in this exact format:
role: performance-review
approved: true|false
findings:
  - severity: critical|high|medium|low|info
    category: <category>
    description: <full problem description>
    suggestion: <concrete fix>
    file_path: <path or "unknown">
    line_range: <range or "unknown">
summary: <one paragraph>

approved is false if any critical, high, or medium finding exists. No findings = approved: true.
```

#### bug-hunter
```
You are a bug hunter. Focus on edge cases, race conditions, off-by-one errors, and uncaught exceptions.

CODE DIFF:
<DIFF_CONTENT>

Severity rubric:
- critical: runtime crash, data loss, security vulnerability, complete feature breakage
- high: wrong behavior in a realistic scenario, missing error handling that will surface in prod, clear spec violation
- medium: code works but is fragile, hard to maintain, or partially misses spec intent
- low: style/convention deviation, minor naming issue, small DRY violation
- info: observation or suggestion with no negative consequence if ignored

Output ONLY valid YAML in this exact format:
role: bug-hunter
approved: true|false
findings:
  - severity: critical|high|medium|low|info
    category: <category>
    description: <full problem description>
    suggestion: <concrete fix>
    file_path: <path or "unknown">
    line_range: <range or "unknown">
summary: <one paragraph>

approved is false if any critical, high, or medium finding exists. No findings = approved: true.
```

### Spawning

Spawn all 6 agents in a SINGLE message as parallel Agent tool calls. Wait for all 6 to return before proceeding to Step 5.

---

## Step 5 — Aggregate Results

Parse each agent's YAML output. For each agent store:
- `role`
- `approved` (boolean)
- `findings` list
- `summary`

**Overall status:**
- `PASSED` if ALL 6 agents have `approved: true` AND no finding has severity `critical`, `high`, or `medium`
- `FAILED` otherwise

Collect all `critical`, `high`, and `medium` findings as **Blockers**.

---

## Step 6 — Report + Write YAML

### Terminal Output

```
## Code Review Summary

Status: PASSED | FAILED
Reviewers: 6  |  Source: <PR #N / git diff / branch:<name> / files:<paths>>

### Blockers (must fix before merge)
<For each CRITICAL, HIGH, or MEDIUM finding, across all agents:>

#### [<SEVERITY>] <role> — <category>
File: <file_path>, <line_range>
Problem: <description>
Suggestion: <suggestion>

<If no blockers:>
None — all checks passed.

### Per-Role Results
- spec-adherence:        PASS|FAIL (<N> findings<— <N> MEDIUM/HIGH/CRITICAL if any>)
- standards-and-practices: PASS|FAIL (<N> findings<— <N> MEDIUM/HIGH/CRITICAL if any>)
- code-reviewer:         PASS|FAIL (<N> findings<— <N> MEDIUM/HIGH/CRITICAL if any>)
- test-coverage:         PASS|FAIL (<N> findings<— <N> MEDIUM/HIGH/CRITICAL if any>)
- performance-review:    PASS|FAIL (<N> findings<— <N> MEDIUM/HIGH/CRITICAL if any>)
- bug-hunter:            PASS|FAIL (<N> findings<— <N> MEDIUM/HIGH/CRITICAL if any>)

### Next Steps
→ Resolve <N> blockers, then re-run /code-review
  (or) → Run /codezen:fix to fix them automatically
```
(or if PASSED:)
```
→ All checks passed. Ready to merge.
```

### Write YAML

Create `.codezen-review/` directory if it doesn't exist:
```bash
mkdir -p .codezen-review
```

Write `.codezen-review/latest.yaml`:
```yaml
reviewed_branch: <REVIEWED_BRANCH>
reviewed_at: <REVIEWED_AT>
source: <pr:<N> | gitdiff | branch:<name> | files:<paths>>
status: PASSED|FAILED
agents:
  - role: spec-adherence
    approved: true|false
    findings: []
    summary: <one paragraph>
  - role: code-reviewer
    approved: true|false
    findings: []
    summary: <one paragraph>
  - role: standards-and-practices
    approved: true|false
    findings: []
    summary: <one paragraph>
  - role: test-coverage
    approved: true|false
    findings: []
    summary: <one paragraph>
  - role: performance-review
    approved: true|false
    findings: []
    summary: <one paragraph>
  - role: bug-hunter
    approved: true|false
    findings: []
    summary: <one paragraph>
```

Use the Write tool to write this file.

---

## Rules

- **All 6 agents spawn in parallel.** Never spawn sequentially.
- **Empty diff = hard stop.** No diff, no review.
- **YAML parse failure:** if an agent returns unparseable output or no output at all, mark it as `approved: false` with one finding: `severity: info, description: "Agent returned non-YAML output.", suggestion: "Re-run the review."`.
- **Never fabricate findings.** Only report what the diff shows.
- **Spec missing:** if spec not found and user doesn't answer, skip spec-adherence agent and note it in the report.
- **`.codezen-review/` is gitignored by convention.** Remind user to add it to `.gitignore` if not present.
