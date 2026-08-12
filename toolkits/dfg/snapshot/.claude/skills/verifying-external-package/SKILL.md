---
name: verifying-external-package
description: Required when the diff introduces a Python import outside stdlib + repo's
  pyproject.toml deps, OR adds a new entry to [project.dependencies] / [project.optional-dependencies]
  without a paired contract citation. Forces WebFetch of canonical docs + smoke-test
  of actual import surface. Codifies ADR-019 §amendment-4 (W22-8 keystone) and §amendment-5
  trigger discipline. Activated structurally by `kit/scripts/external-lib-verification-check.py`
  AST scan — never by natural-language nudges.
criticality: important
sdlc_category: Implementation / Coding
loop_layer: L4-action
license: dfg-harness internal (Korza)
when_to_use: 'Use this skill BEFORE writing any code that imports a package not already
  in the repo''s pyproject.toml core dependencies, AND before recommending a third-party
  library to the user. The skill is the structural enforcement of "every external
  library requires docs-verified citation" per ADR-019 §amendment-4.

  '
verified_at: 2026-05-06
forged_by: dfg-harness W22-8 §amendment-4 receipt + W21-1 fabrication-cascade post-mortem
---
# Verifying External Package — pre-import gate

## Why this skill exists

W21-1 cycle-1 + cycle-2 fabricated **3 different APIs** for what turned out to be a deprecated package (`claude-code-sdk`). The canonical package is `claude-agent-sdk`. Mocked tests passed against fictional APIs in all 3 cycles. Only WebFetch of `https://code.claude.com/docs/en/agent-sdk/python` broke the cycle.

Pattern: **Hallucinated APIs pass mocked tests. Only docs-verification breaks the cycle.**

W24-1 hit the same class differently: the agent declared `pytest-testmon` as the primary mechanism in the ADR, but never installed it, never called it, never tested it. The smoke command `dfg test impacted` errored because the CLI surface was fictional.

## Trigger conditions (substrate-evidence only — per §amendment-5)

Per ADR-019 §amendment-5 ("Trigger discipline: substrate-evidence over natural-language"), this skill activates on **deterministic diff/AST signals**, never on prose hints from the operator or agent. The detector is `kit/scripts/external-lib-verification-check.py`.

Auto-trigger on ANY of:
1. **AST scan** of `git diff <base>..HEAD -- 'src/**/*.py'` finds `import X` / `from X import Y` where `X ∉ sys.stdlib_module_names ∪ pyproject.toml[project.dependencies] ∪ [project.optional-dependencies]` AND no matching `read_contract.external_libs[]` citation in any modified contract
2. **Diff** adds a new entry to `[project.dependencies]` or `[project.optional-dependencies]` AND no matching contract citation in same diff
3. **Pre-pr battery** failure from `external-lib-verification-check.py` returning a non-zero exit code

Explicitly NOT triggers (deleted per §amendment-5):
- ❌ "User asks 'should I use X library?'" — natural-language; not substrate-detectable
- ❌ "Agent says 'I'll use library Z'" — natural-language; not substrate-detectable
- ❌ "ADR or contract drafting that names a library" — covered by trigger #1 if/when the library lands as code; before that, no enforcement is owed

## Required steps (NO shortcuts)

### Step 1 — Resolve canonical name

```bash
# Search PyPI directly. Do NOT trust agent memory.
curl -s "https://pypi.org/pypi/<pkg>/json" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'name: {data[\"info\"][\"name\"]}')
print(f'version: {data[\"info\"][\"version\"]}')
print(f'docs: {data[\"info\"][\"project_urls\"]}')"
```

If 404 or `"removed_yanked"`: the package does not exist as named. **STOP. Do not invent.**

### Step 2 — WebFetch the canonical docs page

The PyPI metadata's `project_urls.Documentation` (or `Homepage`) is the source of truth. WebFetch that URL. Look for:
- Exact import statement (e.g., `from anthropic import Anthropic` vs `import anthropic`)
- Public API surface (class names, function signatures, async vs sync)
- Whether it's a Python library OR a wrapper around a CLI binary
- Auth requirements (env vars, ~/.config/, ~/.<vendor>/)
- Deprecation notices

**Do not skip.** Trusting agent memory of an SDK from training data is the failure mode.

### Step 3 — Install + smoke-import

```bash
# In the actual worktree where the dispatched session will run:
uv add <canonical-name>             # or uv pip install
uv run python -c "import <pkg>; print(f'{pkg.__name__} v{pkg.__version__ if hasattr(pkg, \"__version__\") else \"unknown\"}'); print(dir(pkg))"
```

Verify:
- Import succeeds (no ModuleNotFoundError)
- Version is the one PyPI advertised
- `dir(pkg)` shows the symbols the docs claimed

If smoke fails: this is the package giving you the truth. Do not "fix it" by mocking — fix the import.

### Step 4 — Cite in contract

Add to the unit's `.dfg/agents/<unit>-<slug>.md` frontmatter:

```yaml
read_contract:
  external_libs:
    - package: <canonical-name>     # exact PyPI name
      version: ">=<X.Y>"            # constraint actually verified
      docs_url: "<URL fetched>"     # exact URL
      docs_url_verified_at: 2026-05-06
      verified_imports:             # the import statements you smoke-tested
        - "from <pkg> import <sym>"
      auth_requirements: |
        # Any env vars, config files, runtime CLI deps
      python_native_or_subprocess: "native"  # or "subprocess-cli-bridge"
```

This satisfies §amendment-4 (W22-8) and is checked by `kit/scripts/external-lib-verification-check.py`.

### Step 5 — If wiring as optional extra

If using `[project.optional-dependencies]`:
- Document in CLAUDE.md or README how the extra is installed (`uv sync --extra <name>`)
- Verify dispatched-session worktrees inherit the extra (per W23 cycle-1 pain)
- Smoke-test by running `uv pip list | grep <pkg>` AFTER `uv sync --extra <name>`

### Step 6 — If recommending to user

When recommending a library to the operator, your recommendation must include:
- Canonical PyPI name (verified above)
- Last-release date (active vs abandoned)
- Maintenance signal (last commit, open issue count)
- The exact import line operators will write
- Auth requirements (no surprises)

## Failure modes this prevents

1. **Hallucinated package name** — operator types `pip install <fictional>`, gets 404
2. **Hallucinated API surface** — code references `pkg.foo()` where the real surface is `pkg.foo` (attr) or `pkg.bar()`
3. **Fictional integration** — the docs-claimed integration pattern is just wrong (e.g., async-only API used synchronously)
4. **Optional-extra not inherited** — works in main venv, dies in worktree venv
5. **Subprocess-CLI dependency hidden** — package "imports" but actually shells to a missing binary

## Test-of-skill (evaluation cases)

This skill must produce ALL of these citations for ANY new external lib:
- ✅ Canonical PyPI name
- ✅ docs URL fetched today
- ✅ verified_imports list smoke-tested
- ✅ python_native vs subprocess-cli-bridge classified

Skill considered FAILED if a downstream PR is shipped with an external lib that wasn't pre-cited.

## Layer composition

- L4 (Action): this skill, fires per import
- L3 (Unit): `harness-pre-pr-checklist` verifies the contract has external_libs cited
- L1 (Sprint): `dependency-management` skill (W25-2 if forged) audits all citations for staleness
- L0 (Release): release-cadence skill freezes the citation set at tag-time

## References

- ADR-019 §amendment-4 (W22-8) — the structural mandate
- W21-1 fabrication-cascade — the empirical receipt
- https://code.claude.com/docs/en/agent-sdk/python — the WebFetch that broke the cycle
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices — Anthropic skill authoring discipline
