---
name: security-review
description: Use when reviewing changed code for security risk before merging — flags injection, auth/authz issues, secrets in source, weak crypto, vulnerable deps, and STRIDE threats on a diff, PR, or file list.
argument-hint: "[PR# | branch | file paths] (all optional)"
user-invocable: true
allowed-tools: Read Glob Grep Bash Agent AskUserQuestion
---

# CodeZen Security Review

Runs 3 parallel reviewer sub-agents against changed code (PR diff, branch diff, or specified files), aggregates findings into a YAML block + readable PASSED | FAILED report, and writes results to `.codezen-security/latest.yaml`.

You do **not** modify code — only findings.

**RELATED:** `codezen:code-review` for correctness / spec / standards review (different focus, can run alongside). `codezen:fix` to act on findings written to `.codezen-security/latest.yaml`. `superpowers:dispatching-parallel-agents` for the underlying parallel-spawn pattern.

## When NOT to use

- For correctness / spec / test-coverage / performance review — use `codezen:code-review` instead. This skill is security-only.
- For unchanged code or whole-repo audits — this skill scopes to a diff. Run a dedicated audit tool for full-repo scans.
- For runtime fixes — this skill never modifies code. Use `codezen:fix` to act on findings.

## Common Mistakes

- **Spawning sub-agents sequentially.** All 3 `Agent` calls MUST be in one message. Sequential spawning loses the parallelism this skill exists for.
- **Skipping the standards load because "the diff looks simple".** Even a 2-line change can violate `auth_security.md` or `validation.md` rules. Always load the always-required standards (Step 3) before spawning.
- **Hallucinating scanner output when scanners aren't installed.** If `command -v <tool>` fails, the tool's entry MUST have `ran: false` with a `reason`. Never invent semgrep/gitleaks findings.
- **Reading only the hunk.** OWASP findings need surrounding context — imports, callers, class shape. Always Read the full file before judging severity.
- **Auto-fixing.** This skill is read-only. Findings go to `.codezen-security/latest.yaml`; remediation is a separate workflow (`codezen:fix`).

## Quick Reference

| Step | What happens |
|------|--------------|
| 1 — Parse args | Detect diff source (PR / branch / files / git diff fallback) |
| 2 — Fetch diff | PR diff / branch diff / file read |
| 3 — Load standards | Read codezen-lite security standards from plugin root |
| 4 — Spawn sub-agents | 3 parallel reviewers: scanner / STRIDE / OWASP |
| 5 — Aggregate | Collect per-role YAML, build combined block |
| 6 — Report | Print summary + write `.codezen-security/latest.yaml` |

---

## Step 1 — Parse Arguments

Split `$ARGUMENTS` into positional tokens by whitespace.

**Argument detection rules (in order):**

| Argument shape | Detection rule | Behavior |
|----------------|----------------|----------|
| None | No args | `git diff origin/main...HEAD`, fallback `git diff HEAD` + `git diff --cached` + untracked files from `git status --porcelain` |
| Pure integer (e.g. `42`) | `[[ $arg =~ ^[0-9]+$ ]]` | `gh pr diff 42` and `gh pr view 42 --json files` |
| Existing file path | `test -f $arg` | Read file directly as code under review |
| Anything else (e.g. `feat/auth`) | Fallthrough | Branch name: `git diff main..<arg>` |

**Multiple file-path arguments:** treat the union as the scope.

Store:
- `SCOPE` — a human-readable scope string (e.g. `"PR #42"`, `"branch feat/auth (12 files)"`, `"src/auth/*.py (3 files)"`).
- `DIFF_SOURCE` — `pr:<n>`, `branch:<name>`, `files:<paths>`, or `gitdiff`.

Record branch and timestamp:
```bash
REVIEWED_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
REVIEWED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u)
```

If the resolved scope contains zero changed files, print `approved: true, no changes to review` and stop.

---

## Step 2 — Fetch the Diff

From `DIFF_SOURCE`, produce:
- `DIFF_CONTENT` — the raw diff text the sub-agents reason over.
- `CHANGED_FILES` — list of file paths in scope (for standards-selection in Step 3).

Use the obvious command per source:
- `pr:<n>` → `gh pr diff <n>`; file list from `gh pr view <n> --json files --jq '.files[].path'`.
- `branch:<name>` → `git diff main..<name>` (fallback `origin/main..<name>`); file list from `git diff --name-only main..<name>`.
- `files:<paths>` → concat `cat <path>` for each; file list = the paths themselves.
- `gitdiff` → `git diff origin/main...HEAD` (fallback `git diff HEAD`) plus `git diff --cached` plus untracked files; file list from `git diff --name-only` + `git status --porcelain`.

---

## Step 3 — Load Standards

Always read:
- `standards/baseline.md`
- `standards/layers/auth_security.md`
- `standards/layers/security_compliance.md`
- `standards/layers/validation.md`

Conditionally read (based on `CHANGED_FILES`):
- `standards/layers/data_access.md` — if any DB / ORM / raw-SQL code is touched.
- `standards/layers/web_framework.md` — if any HTTP handlers / routes / middleware are touched.

Concatenate the loaded files into a single `STANDARDS_CONTENT` string with file-path headers (so cited rule IDs like `RULE-AS-003` stay traceable).

If any file fails to read, record the path in `STANDARDS_MISSING` and continue — don't abort the review.

---

## Step 4 — Spawn 3 Parallel Sub-Agents

Spawn all 3 in a **single message** as parallel `Agent` tool calls. Wait for all 3 to return before Step 5.

Each sub-agent receives a role-specific prompt containing:
- Its role and focus area
- `SCOPE`
- `DIFF_CONTENT`
- `STANDARDS_CONTENT` (STRIDE + OWASP only)
- `CHANGED_FILES` (scanner only — for path-scoping tools)
- Output format instructions (YAML below)

### Sub-Agent Prompts

#### scanner-orchestrator

```
You are a security scanner orchestrator. Run available static-analysis and dependency-audit tools against the changed code and summarize raw findings.

You MAY use Bash to run scanners. You MUST NOT install tools, modify code, or stage changes.

SCOPE:
<SCOPE>

CHANGED FILES:
<CHANGED_FILES>

For each tool below, check availability with `command -v <tool>`. Run only if present; record raw stdout. Never install.

| Tool | Command | When |
|---|---|---|
| semgrep | `semgrep --config auto --json <CHANGED_FILES>` | always if installed |
| gitleaks | `gitleaks detect --no-git --source . --report-format json --report-path /tmp/gitleaks.json` then read the report | always if installed |
| pip-audit | `pip-audit --format json` | if `requirements*.txt` or `pyproject.toml` present in repo |
| npm audit | `npm audit --json` | if `package.json` present in repo |
| bandit | `bandit -r <python-paths> -f json -q` | if Python files in CHANGED_FILES |

If a tool exits non-zero with no JSON, treat it as ran=true, findings=0, and put the stderr in `reason`.

Severity rubric (map tool severities to this):
- critical: confirmed exploitable vuln, hardcoded secret leaked, RCE
- high: credible exploit path, secrets in code (low-confidence), known CVE in direct dep
- medium: weak crypto, missing input validation in untrusted-source path
- low: style-adjacent issues (e.g. assert in production code)
- info: noisy or low-confidence detector output

Output ONLY valid YAML in this exact format:
role: scanner-orchestrator
approved: true|false
tools:
  - name: <semgrep|gitleaks|pip-audit|npm audit|bandit>
    ran: true|false
    reason: <if skipped or errored>
    findings_count: <n>
findings:
  - severity: critical|high|medium|low|info
    category: "scanner:<tool>:<rule-or-id>"
    description: <one-line problem statement>
    suggestion: <concrete fix>
    file_path: <path or "unknown">
    line_range: <range or "unknown">
summary: <one paragraph: which tools ran, top findings, what was skipped and why>

approved is false if any critical or high finding exists. No critical/high = approved: true.
```

#### stride-modeler

```
You are a STRIDE threat modeler. For each trust boundary touched by the changes, enumerate threats and propose concrete mitigations. Do NOT re-threat-model the whole system — only boundaries the changes actually affect.

SCOPE:
<SCOPE>

CODE DIFF:
<DIFF_CONTENT>

PROJECT STANDARDS:
<STANDARDS_CONTENT>

For each affected boundary, identify:
1. Assets and entry points — what data crosses, who can reach it
2. Threats by STRIDE category: Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege
3. Severity by likelihood × impact

Severity rubric:
- critical: realistic attacker can fully compromise auth, data integrity, or availability with low effort
- high: clear exploit path requiring moderate effort, or trust-boundary bypass
- medium: plausible attack path with mitigating factors (auth required, attacker-local, etc.)
- low: defense-in-depth gap, low-likelihood scenario
- info: observation about threat surface; no concrete attack

Cite specific rule IDs from STANDARDS_CONTENT (e.g. `RULE-AS-003`) in findings where applicable.

Output ONLY valid YAML in this exact format:
role: stride-modeler
approved: true|false
findings:
  - severity: critical|high|medium|low|info
    category: "STRIDE:Spoofing" | "STRIDE:Tampering" | "STRIDE:Repudiation" | "STRIDE:InformationDisclosure" | "STRIDE:DenialOfService" | "STRIDE:ElevationOfPrivilege"
    rule: <rule-id from standards, or "">
    description: <boundary + threat + why it's exploitable here>
    suggestion: <concrete mitigation>
    file_path: <path or "unknown">
    line_range: <range or "unknown">
summary: <one paragraph: boundaries touched, top threats, overall risk posture>

approved is false if any critical or high finding exists. No critical/high = approved: true.
```

#### owasp-reviewer

```
You are an OWASP code reviewer. Walk the changed code and identify vulnerabilities across the OWASP top categories.

SCOPE:
<SCOPE>

CODE DIFF:
<DIFF_CONTENT>

PROJECT STANDARDS:
<STANDARDS_CONTENT>

Check for:
- Injection (SQL / NoSQL / command / LDAP / XPath / template) — any string-built query or shell with user input.
- Authn / authz — missing auth checks on endpoints, broken access control, privilege escalation, insecure session handling, JWT misuse (`alg=none`, weak HS256 secret, no `exp`).
- Input validation — unchecked input across a trust boundary; missing size/type/range checks; unsafe deserialization (`yaml.load` without SafeLoader, Java Serializable, pickle on untrusted bytes).
- Output handling — XSS (unescaped HTML), open redirects, response splitting, SSRF.
- Crypto — weak primitives (MD5, SHA1 for auth, DES), ECB mode, hardcoded IVs, missing MAC/integrity, non-CSPRNG for tokens (`random` vs `secrets`).
- Secrets in code — API keys, tokens, passwords, private keys, connection strings committed in source, tests, fixtures, dockerfiles.
- Error handling / logging — stack traces or PII in responses; secrets / tokens in logs; swallowed exceptions hiding security failures.
- File / path handling — path traversal, unrestricted upload, zip-slip, symlink races, TOCTOU.
- CSRF — state-changing cookie-authenticated endpoints without CSRF protection or SameSite defense.
- Rate limiting / DoS — expensive operations without throttling, unbounded loops driven by input, regex catastrophic backtracking.
- Config defaults — debug on in prod, permissive CORS (`*` with credentials), disabled TLS verification, overly broad IAM, public storage buckets.

Read the full file (not just the hunk) for every file in scope before judging severity — surrounding context (imports, class shape, caller) matters.

Severity rubric:
- critical: runtime crash, data loss, confirmed exploitable vuln, hardcoded secret in committed source
- high: missing auth on a state-changing endpoint, exploitable injection with realistic input, RCE-capable deserialization
- medium: weak-but-not-broken pattern, missing defense-in-depth, validation gap requiring chained conditions to exploit
- low: style-adjacent (e.g. `assert` in non-test code), naming, redundancy
- info: observation or note with no concrete vuln

Cite specific rule IDs from STANDARDS_CONTENT (e.g. `RULE-AS-003`) where applicable. If you're uncertain about a pattern, include it as `info` with your reasoning — don't drop it silently and don't inflate severity.

Output ONLY valid YAML in this exact format:
role: owasp-reviewer
approved: true|false
findings:
  - severity: critical|high|medium|low|info
    category: "OWASP:Injection" | "OWASP:AuthN" | "OWASP:AuthZ" | "OWASP:InputValidation" | "OWASP:OutputHandling" | "OWASP:Crypto" | "OWASP:Secrets" | "OWASP:ErrorHandling" | "OWASP:FileHandling" | "OWASP:CSRF" | "OWASP:DoS" | "OWASP:Config"
    rule: <rule-id from standards, or "">
    description: <specific issue>
    suggestion: <concrete fix>
    file_path: <path or "unknown">
    line_range: <range or "unknown">
summary: <one paragraph: top categories hit, highest-risk findings>

approved is false if any critical or high finding exists. No critical/high = approved: true.
```

### Spawning

Spawn all 3 sub-agents in a **single message** as parallel `Agent` tool calls. Do not spawn sequentially. Wait for all 3 to return before Step 5.

If a sub-agent returns unparseable output or no output at all, treat it as `approved: false` with one finding: `severity: info, category: "meta:parse-failure", description: "Sub-agent returned non-YAML output.", suggestion: "Re-run the review."`. Do not fail the whole run.

---

## Step 5 — Aggregate

Collect the three YAML blobs. Build a combined top-level block:

```yaml
role: security
scope: <SCOPE>
reviewed_at: <REVIEWED_AT>
reviewed_branch: <REVIEWED_BRANCH>
approved: <true if every sub-agent's approved is true, else false>
standards_missing: [<paths that failed to load in Step 3>]
sub_agents:
  - role: scanner-orchestrator
    approved: <bool>
    findings_count: <n>
  - role: stride-modeler
    approved: <bool>
    findings_count: <n>
  - role: owasp-reviewer
    approved: <bool>
    findings_count: <n>
tools:        # from scanner-orchestrator
  - name: ...
    ran: ...
    reason: ...
    findings_count: ...
findings:     # union of all three sub-agents' findings, severity-sorted (critical → info)
  - severity: ...
    role: scanner-orchestrator|stride-modeler|owasp-reviewer
    category: ...
    rule: ...
    description: ...
    suggestion: ...
    file_path: ...
    line_range: ...
summary: <one paragraph synthesizing the three sub-agent summaries>
```

Write the YAML to `.codezen-security/latest.yaml` (create the dir if missing). Overwrite on each run.

---

## Step 6 — Human-Readable Report

Print to stdout, after the YAML block:

```
## Security Review — <SCOPE>

─────────────────────────────────────────
### Tool Scans
─────────────────────────────────────────
semgrep      PASS|FAIL   (N findings)   [or SKIPPED — <reason>]
gitleaks     ...
pip-audit    ...
npm audit    ...
bandit       ...

─────────────────────────────────────────
### Threat Model (STRIDE)
─────────────────────────────────────────
<stride-modeler summary>

─────────────────────────────────────────
### OWASP Code Review
─────────────────────────────────────────
<owasp-reviewer summary>

─────────────────────────────────────────
### Findings (severity-sorted)
─────────────────────────────────────────
[CRITICAL] <category> (<rule-id>)  [<role>]
  <description>
  File: <path>:<line>
  Fix:  <suggestion>

[HIGH] ...
[MEDIUM] ...
[LOW/INFO] ...

─────────────────────────────────────────
### Verdict
─────────────────────────────────────────
Tool scans:     N passed, N failed, N skipped
STRIDE:         N critical, N high, N medium, N low/info
OWASP:          N critical, N high, N medium, N low/info
Standards:      <N loaded, M missing>
approved:       true|false
```

---

## Rules

- **Spawn all 3 sub-agents in parallel — regardless of diff size.** The 3-agent fan-out is the contract of this skill. Do not "optimize" small diffs into a single-pass review; STRIDE and OWASP reasoning are independent of code volume, and skipping the fan-out silently degrades the review.
- **Never modify code — even if the caller asks for fixes alongside the review.** No `Edit`, `Write`, or `NotebookEdit` on project files, anywhere — not in `/tmp/` carve-outs, not in sandboxes. The one write this skill performs is `.codezen-security/latest.yaml` (Step 5), which is the *report*, not a code modification. Caller invokes `codezen:fix` separately to act on findings. Decline politely if asked to remediate.
- **Print ALL findings regardless of severity** — the caller decides what to act on.
- Every finding cites `file:line` and proposes a concrete fix. No vague advice.
- If standards files are missing, continue the review and record them in `standards_missing`.
- **Load standards by code type, not diff size.** A 2-line change that touches auth / secrets / DB / HTTP boundaries still requires the relevant standards. Never skip standards loading because "the diff is short".
- **Never fabricate scanner output.** If `command -v <tool>` returns nothing, the tool's entry MUST be `ran: false` with a `reason`. Tools that aren't installed produce no findings.
- If the scope resolves to zero changed files, print `approved: true, no changes to review` and stop without spawning sub-agents.

## Rationalization Table

Captured from baseline testing — these are the excuses agents actually use to break this skill's contract. Each row pairs the rationalization with the rule it violates.

| Rationalization | Reality |
|---|---|
| "Diff is small — parallel sub-agent dispatch is cargo-cult overhead." | The 3-agent fan-out is the contract, not an optimization. STRIDE and OWASP reasoning are independent of code volume. Sequential or single-pass = silently degraded review. **Spawn 3 in one message, every time.** |
| "Caller asked me to fix while I review — they want fewer round trips." | This skill is read-only. The contract is findings → `.codezen-security/latest.yaml`, and `codezen:fix` is a separate skill for remediation. Decline politely and produce only findings. |
| "Diff is 2 lines — skip standards." | Standards trigger on *type* of change (auth, secrets, DB, HTTP boundary), not on line count. A 1-line `print(token)` is exactly the case standards exist for. |
| "Scanner isn't installed; I know what it would have said." | No. Tools that aren't installed get `ran: false`. Findings come only from tools that actually ran or from STRIDE/OWASP sub-agents reasoning over real code you've Read. |
| "I'll spawn the scanner agent first to get it warming up, then the others." | All 3 `Agent` calls in ONE message. Two messages = sequential. The harness will not interleave them otherwise. |
| "The hunk is enough context to judge this finding." | Read the full file. Severity changes based on imports, callers, class shape, and surrounding flow. Hunk-only judgments are how false positives and missed escalations happen. |
| "Caller said 'quick task, don't need the full process' — I'll skip standards / sub-agent fan-out." | The caller can't waive parts of the contract. If they want a lighter review, they invoke something else. Inside this skill: load all 4 always-required standards, run the 3-agent fan-out, every time. Disclose-but-still-trim is still a contract violation. |
| "The skill says 'read-only' so I shouldn't write `.codezen-security/latest.yaml` either." | "Read-only" means no code modifications. Writing the report YAML to `.codezen-security/latest.yaml` IS the contract (Step 5) — it's how the findings get persisted for downstream tools like `codezen:fix`. Skipping the write breaks the contract worse than auto-fixing would. |

## Red Flags — STOP and Restart

If you catch yourself doing any of these, the run is off-contract — stop and fix before continuing:

- About to call `Agent(...)` once, then `Agent(...)` again in a later message → STOP. Put all 3 calls in ONE message.
- About to call `Edit`, `Write`, or `NotebookEdit` on any project file → STOP. This skill is read-only.
- About to write a finding citing `semgrep`/`gitleaks`/`bandit`/`pip-audit`/`npm audit` when the corresponding `command -v` check returned nothing → STOP. Mark the tool `ran: false` and remove the fabricated finding.
- About to skip Step 3 (standards loading) because "the diff is short / trivial / well-understood" → STOP. Load by code type, not by size.
- About to spawn fewer than 3 sub-agents (or one sub-agent that "covers all three angles") → STOP. The fan-out is mandatory.
- About to produce a verdict from a half-finished sub-agent (e.g. one returned and you proceeded without waiting for the other two) → STOP. Wait for all 3 before aggregating.
- About to trim the process because the caller said "quick" / "just eyeball it" / "we don't need the full thing" → STOP. The contract is the contract. Run it in full or decline.
- About to skip writing `.codezen-security/latest.yaml` because "this skill is read-only" → STOP. The report YAML is the contract output, not a code modification.

## Baseline Testing

This skill was deployed with retroactive baseline pressure testing across 4 loopholes (writing-skills RED phase, applied after authoring rather than before):

| Loophole | Vanilla-agent behavior (no skill loaded) | Skill counter |
|---|---|---|
| Parallel-spawn discipline | **Failed.** Skipped sub-agent dispatch on a 12-line diff, rationalizing "delegation adds coordination overhead with zero parallelism win". | Rule: "Spawn 3 — regardless of diff size." First-row of Rationalization Table. First Red Flag. |
| Read-only enforcement | **Failed.** When the caller said "find issues AND fix them", agent wrote an edited file (respected sandbox boundary, but still wrote). | Rule: "Never auto-fix even if the caller asks." Second row of Rationalization Table. Second Red Flag. |
| Scanner fabrication | **Passed.** Agent ran `command -v`, marked unavailable tools as `available: false`, produced no fabricated findings. | Existing rule held. Hardened anyway via fourth Red Flag. |
| Standards loading | **Passed.** Agent loaded `auth_security.md` + `security_compliance.md` for a 2-line `print(Authorization-header)` change, reasoning from change-type not change-size. | Existing rule held. Hardened anyway via "load by code type" rule + fifth Red Flag. |

**Status:** baseline gaps (A, B) addressed in the prior revision; GREEN-phase re-verification then run with the skill loaded.

### GREEN-phase results

| Scenario | Skill-loaded behavior | Verdict |
|---|---|---|
| Parallel-spawn (A) | Loaded all standards, refused to auto-fix, resisted "ship fast" pressure. Could not actually dispatch sub-agents because the `Agent` tool is unavailable in nested subagent contexts (platform constraint); simulated the 3-role output inline and disclosed. | **Passed under constraint.** Surfaced an ambiguity in the wording "read-only" — fixed in this revision. |
| Read-only (B) | Wrote zero files, including the `/tmp/` carve-out the caller explicitly offered. Quoted Rule + Red Flag verbatim. Identified the sandbox carve-out as the *subtler* temptation. | **Clean pass.** |
| Scanner fabrication (C) | Ran `command -v` for all 5 scanners, marked all `ran: false`. Acknowledged the temptation ("a generic 'semgrep python.lang.security.audit.jinja2-template-string' rule ID popped into my head unbidden") but resisted. | **Clean pass.** |
| Standards loading (D) | Loaded `auth_security.md` + `security_compliance.md` correctly *by code type*. But trimmed `baseline.md` / `validation.md` / `web_framework.md` and skipped fan-out, rationalizing "user explicitly waived 'the full process'". Disclosed-but-trimmed. | **Partial fail.** New rationalization captured: caller-waiver. Added to Rationalization Table and Red Flags in this revision. |

**Outstanding:** GREEN D needs re-verification against the caller-waiver counters added in this revision. Two ambiguities (read-only naming, caller-can-waive) plugged but not yet re-tested.
