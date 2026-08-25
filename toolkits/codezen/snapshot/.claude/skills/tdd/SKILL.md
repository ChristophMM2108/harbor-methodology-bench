---
name: tdd
description: Use when implementing any feature or bugfix for a codezen project — accepts a feature description, GitHub issue URL, or file path.
argument-hint: "<feature-description | github-issue-URL | filepath> [--use_real_infra=true]"
user-invocable: true
allowed-tools: Read Bash Glob Grep Skill
---

# CodeZen TDD — Test-Driven Development

Orchestrates a full Red-Green-Refactor cycle inside a Docker sandbox. The host skill handles setup; an inner Claude instance runs `superpowers:test-driven-development`, commits, and pushes the feature branch.

## Quick Reference

| Step | What happens | Hard stop if… |
|------|-------------|---------------|
| 0 — Credential gate | Check setup + extra credentials | anything `SETUP_REQUIRED` or `EXTRA_REQUIRED` |
| 1 — Resolve input | Parse issue URL / filepath / text → `FEATURE_DESCRIPTION` + `FEATURE_SLUG` | empty input with no clarification |
| 1.5 — Load standards | Read baseline + relevant layer standards | — |
| 2 — Detect language + LSP | Glob manifests → `LANGUAGES` + `LSP_AVAILABLE` | never blocks — warn only |
| 3 — Pre-flight | Docker running, working tree clean | docker down or dirty tree |
| 3.5 — Infra preference | Detect infra deps, ask user, gate credentials | creds missing after prompt |
| 4 — Launch container | Run inner Claude TDD, parse JSON result | non-zero exit from launcher |
| 5 — Summary | Show branch, commits, test results, log | warn if tests failed |
| 6 — Security review | Optional pre-PR review | — |
| 7 — Create PR | `gh pr create` with test + security status | — |

---

## Step 0 — Credential gate

First, resolve the launcher path:

```bash
# Find launcher: prefer plugin hooks, fall back to local plugin copy
if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" ]] && [[ -f "${CLAUDE_PLUGIN_ROOT}/hooks/launch-tdd-container.sh" ]]; then
    CODEZEN_LAUNCHER="${CLAUDE_PLUGIN_ROOT}/hooks/launch-tdd-container.sh"
elif [[ -f "plugin/hooks/launch-tdd-container.sh" ]]; then
    CODEZEN_LAUNCHER="plugin/hooks/launch-tdd-container.sh"
else
    echo "ERROR: launch-tdd-container.sh not found. Is codezen-lite installed as a Claude Code plugin?"
    exit 1
fi
echo "Launcher: ${CODEZEN_LAUNCHER}"
```

Store `CODEZEN_LAUNCHER` and use it for all subsequent launcher calls in this skill.

Run both checks:

```bash
bash "${CODEZEN_LAUNCHER}" --check-setup
bash "${CODEZEN_LAUNCHER}" --check-extra
```

**If both return `OK` or `NOT_CONFIGURED`:** proceed to Step 1.

**If `--check-setup` returns `SETUP_REQUIRED`** or **`--check-extra` returns `EXTRA_REQUIRED`:**

Stop immediately and say:

> "Some credentials are missing before I can run TDD:
>
> **Missing:** `<list what's missing>`
>
> Run `/setup` to add them, then come back and re-run `/tdd`."

Do not attempt to collect or set up credentials here. That is `/setup`'s job.

---

## Step 1 — Resolve feature description

Split `$ARGUMENTS` into positional tokens (`$1`, `$2`, …) by whitespace.

**Argument validation — fail immediately if:**
- 0 tokens → stop: "Usage: `/tdd <feature-description | URL | filepath> [--use_real_infra=true]`"
- 3+ tokens → stop: "Too many arguments. Usage: `/tdd <feature-description | URL | filepath> [--use_real_infra=true]`"

**Parse `$2` (optional):**
- If present and exactly `--use_real_infra=true` → set `USE_REAL_INFRA=true`.
- If present but does not match `--use_real_infra=true` → stop: "Unknown argument `$2`. Did you mean `--use_real_infra=true`?"
- If absent → leave `USE_REAL_INFRA` unset (Step 3.5 defaults it to `false`).

**Parse `$1` by type:**

**GitHub issue URL** (matches `https://github.com/<owner>/<repo>/issues/<number>`):
```bash
gh issue view <number> --repo <owner>/<repo> --json title,body,labels,comments
```
Use the issue title, body, and any clarifying comments as `FEATURE_DESCRIPTION`. If `gh` fails, stop and report.

**Filepath** (starts with `./`, `/`, `../`, or path exists on disk):
Read the file. Use contents as `FEATURE_DESCRIPTION`. If file not found, stop and report.

**Plain text**: use `$1` directly as `FEATURE_DESCRIPTION`.

**Derive `FEATURE_SLUG`:**
- From GitHub issue: slugify the issue title (lowercase, hyphens, max 50 chars, e.g. `add-user-search`)
- From filepath: use the filename without extension
- From plain text: auto-derive from first 5 words, or ask the user for a short slug

Store both `FEATURE_DESCRIPTION` and `FEATURE_SLUG` before proceeding.

---

## Step 1.5 — Load standards

Read the relevant files from the plugin's standards library:

- `standards/baseline.md` — always
- `standards/layers/testing.md` — always
- `standards/layers/code_quality.md` — always
- Any other `layers/*.md` that matches the area you're changing (e.g. `auth_security.md` for auth, `data_access.md` for DB)

Apply these rules to every test and implementation file you write.

---

## Step 2 — LSP preflight

Announce: "Checking LSP server for code intelligence."

Glob for manifest files in the project root to determine the primary language:

| Manifest | Language |
|---|---|
| `package.json` | typescript / javascript |
| `pyproject.toml`, `setup.py` | python |
| `go.mod` | go |
| `Cargo.toml` | rust |
| `Gemfile` | ruby |
| `pom.xml`, `build.gradle`, `build.gradle.kts` | java |
| `composer.json` | php |

Check for these files using Glob. Map each match to its language. If multiple manifests are found, list all languages comma-separated (e.g. `typescript,python`). If none are found, glob for source file extensions (`.py`, `.ts`, `.js`, `.go`, `.rs`, etc.) and infer from the most common extension.

Store the result as `LANGUAGES` (comma-separated, primary language first).
If no language can be determined, assume language to be python `LANGUAGES=python` and `LSP_AVAILABLE=true`.

---

## Step 3 — Pre-flight (Docker + working tree)

```bash
# Docker daemon running?
docker info >/dev/null 2>&1 && echo "docker:ok" || echo "docker:fail"

# Working tree clean? (untracked files OK)
git status --porcelain | grep -v '^??' | head -1 | wc -l | tr -d ' '
# outputs "0" if clean, "1" if dirty
```

If `docker:fail` → "Docker is not running. Start Docker Desktop first."
If working tree dirty → "Uncommitted changes found. Run `git stash` or commit first."

---

## Step 3.5 — Infrastructure test preference

If `USE_REAL_INFRA` was not set in Step 1 (i.e. `--use_real_infra=true` was not passed), default it to `false`.

Scan the project manifest for infrastructure dependencies:

```bash
# Python
cat pyproject.toml requirements.txt setup.py 2>/dev/null | grep -iE \
  'azure-storage-blob|azure-storage-queue|azure-cosmos|boto3|aioboto3|botocore|redis|aioredis|psycopg2|asyncpg|sqlalchemy'

# Node
cat package.json 2>/dev/null | grep -iE \
  'azurite|aws-sdk|@aws-sdk|ioredis|redis|pg|postgres'
```

Map detected packages to infra type:

| Package pattern | INFRA_TYPE | Emulator |
|---|---|---|
| `azure-storage-blob`, `azure-storage-queue`, `azure-cosmos` | `azurite` | Azurite process (starts in container) |
| `boto3`, `aioboto3`, `botocore`, `aws-sdk`, `@aws-sdk` | `localstack` | moto (in-process, no daemon) |
| `redis`, `aioredis`, `ioredis` | `redis` | Redis server process (starts in container) |
| `psycopg2`, `asyncpg`, `sqlalchemy`, `pg`, `postgres` | `postgres` | Local Postgres (starts in container) |

**If no infra deps detected:** set `INFRA_TYPE=""`. Skip to Step 4.

**If infra deps detected** and USE_REAL_INFRA is `true`:

Required credentials per infra type:

| INFRA_TYPE | Required env vars |
|---|---|
| `azurite` | `AZURE_STORAGE_CONNECTION_STRING` |
| `localstack` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` |
| `redis` | `REDIS_URL` |
| `postgres` | `DATABASE_URL` |

For each required credential:

1. Check `.codezen/extra-credentials.json` — auto-append the entry if missing
2. Check keychain: `bash "${CODEZEN_LAUNCHER}" --check-extra`
3. If `EXTRA_REQUIRED` → send the user to setup:
   > "Store `<ENV_VAR>` now:"
   > `! bash "${CODEZEN_LAUNCHER%hooks/*}hooks/setup-credentials.sh" --store <account_name>`
   > "Confirm when done."
4. Re-run `--check-extra` until it returns `OK`.

Set `USE_REAL_INFRA=true`, `INFRA_TYPE=<type>`.

**else if USE_REAL_INFRA is `false`:**

Keep `USE_REAL_INFRA=false`. Set `INFRA_TYPE=<type>` so inner Claude knows what to mock.

> "Integration tests will mock `<INFRA_TYPE>`. No credentials needed."

---

## Step 4 — Launch TDD container

Announce: "Launching TDD container for `<FEATURE_SLUG>`..."

```bash
bash "${CODEZEN_LAUNCHER}" \
  --feature-slug "<FEATURE_SLUG>" \
  --feature-desc "<FEATURE_DESCRIPTION>" \
  --base-branch main \
  --timeout 1800 \
  --max-cycles 10 \
  --env "USE_REAL_INFRA=${USE_REAL_INFRA:-false}" \
  --env "INFRA_TYPE=${INFRA_TYPE:-}" \
  --env "LSP_AVAILABLE=${LSP_AVAILABLE:-false}"
```

The launcher reads all credentials directly from macOS Keychain. No credentials pass through this skill at any point.

When `LSP_AVAILABLE=true` is passed, the container injects LSP checkpoint instructions into the inner Claude prompt so it applies them during each TDD cycle:

- **After writing the failing test (Red phase):** `lsp getDiagnostics` on the test file — confirm the error is a missing symbol, not a syntax error or wrong import.
- **After writing the implementation (Green phase):** `lsp getDiagnostics` on both the test file and implementation file before running the test suite — surface type errors without burning a full test cycle.
- **Before any rename or structural change (Refactor phase):** `lsp findReferences` on the symbol being changed — confirm no call sites will be silently broken.

### Integration boundary check

The container prompt instructs inner Claude to write multi-tier tests (unit + integration)
during the TDD cycle, based on the detected project type. After the container exits, verify:

1. **Check commit log** — there should be separate commits for unit tests and integration tests.
   ```bash
   git log --oneline feat/<FEATURE_SLUG>
   ```

2. **Red flags to catch** — if integration commits are missing, warn the user:
   - Every test for a public endpoint calls an internal helper directly (no HTTP-layer test)
   - All tests use fully mocked external deps with no wiring test at all

   > "Inner Claude only wrote unit tests. Consider adding integration tests before merging."

3. **Units tested ≠ boundaries tested.** Mocks isolate the unit; they do not test the wiring.

Parse the JSON result at the end of output. Store:
- `TDD_BRANCH` = `.branch`
- `TDD_TESTS_PASSED` = `.tests_passed`
- `TDD_COMMITS` = `.commits`

If the launcher exits non-zero, stop and report the error. Do not proceed.

---

## Step 5 — Show summary

```bash
git log --oneline -10
git diff main...HEAD --stat
```

Print:
```
## TDD Complete

Branch:       feat/<slug>
Commits:      <count>
Tests:        passed / failed / unknown
Activity Log: found / not found
```

If `log.md` exists in the project root, display its contents:
```bash
if [[ -f log.md ]]; then
    echo ""
    echo "## TDD Activity Log"
    cat log.md
fi
```

If `TDD_TESTS_PASSED` is `false`, warn:
> WARNING: Tests were failing when the branch was pushed. Review carefully before creating a PR.

---

## Step 6 — Security review

Ask the user:
```
Run /codezen-security-review before creating the PR? (recommended)

  1. Yes — run security review now
  2. Skip — create PR immediately
```

**If yes:** invoke the `codezen-security-review` skill directly. Wait for the user to acknowledge findings before proceeding.

**If skip:** note it in the PR body and proceed.

---

## Step 7 — Create PR

```bash
gh pr create \
  --title "feat: <feature-slug>" \
  --body "$(cat <<'EOF'
## Summary
<first 3 sentences of FEATURE_DESCRIPTION>

## TDD
- Branch: feat/<slug>
- Commits: <count>
- Tests: passed / failed
- Security review: passed / skipped

## Test plan
- [ ] All new tests pass (verified in TDD container)
- [ ] No regressions in full test suite
- [ ] Security review completed (or skipped — see above)
EOF
)" \
  --base main \
  --head "feat/<FEATURE_SLUG>"
```

Print the PR URL. Done.

---

## Rules

- **Credentials are opaque.** Never check env vars, print, or reference credential values.
- **Credential gate is a hard stop.** If anything is missing, send to `/setup` and stop. Do not collect credentials here.
- **LSP failures are warn-only.** Never block TDD because of a failed LSP preflight.
- **Never skip the security review prompt.** The user may choose to skip, but always ask.
- **If container fails**, print the exit code and stop. Do not retry automatically.
- **If tests failed** but branch was pushed, warn prominently before asking about PR.
- **Feature description must be resolved** before Step 4. Never launch without both `FEATURE_DESCRIPTION` and `FEATURE_SLUG`.
