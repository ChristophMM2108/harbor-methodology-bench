---
name: inspecting-external-library-call-shape
description: Sub-skill for RCA hierarchy — for any call into an external library (claude_agent_sdk,
  anthropic, pyyaml, jsonschema, typer, etc.), diff the ACTUAL kwargs passed against
  the LIBRARY'S DOCUMENTED surface. The skill that would have caught
criticality: important
sdlc_category: Operations / Debugging
loop_layer: L4-action
license: dfg-harness internal (Korza)
when_to_use: 'Use this skill INSIDE rca-dfg-codebase (T3) when the suspected failure

  mechanism is a call into an external library. The skill enforces that

  every external-call site has its kwargs verified against the library''s

  documented surface (per ADR-019 §amendment-4 docs-fetch discipline).

  Catches under-construction failures where required/important kwargs

  are silently omitted.

  '
verified_at: 2026-05-06
forged_by: dfg-harness 2026-05-06
---
# Inspecting external-library call shape — diff actual vs documented kwargs

## Why this skill exists

#561 root cause receipt: `_claude_agent_sdk_invoker` constructed
`ClaudeAgentOptions` with 2 of 4 documented load-bearing fields. The
absent fields (`allowed_tools`, `permission_mode`, `max_turns`, `cwd`)
defaulted to values that disabled file authoring. The dispatched
session ran, returned exit_code=0, and produced ZERO work-files — the
4+ recurrence empty-output failure mode that took 3 sprints to
diagnose without an RCA primitive.

The skill exists because: when reading the call-site, the existing
verifying-external-package skill (PR #553) confirms the package import
is real but does NOT verify the call's kwargs against the documented
public API. ADR-019 §amendment-4 (W22-8) ratifies docs-verification
discipline at the IMPORT layer; this skill extends the discipline to
the CALL-SHAPE layer.

## Trigger conditions (substrate-evidence only — per §amendment-5)

Auto-trigger on:
1. T3 (`rca-dfg-codebase`) invokes this sub-skill explicitly
2. AST scan during code review finds a non-stdlib call where:
   - The package is in pyproject.toml (so the gate doesn't fire on import)
   - The call is into a class constructor or function with ≥ 3 documented kwargs
   - Fewer than half of the documented kwargs are passed at the call site
3. Cycle-2 critic finds a "function called with X args; docs show Y are documented"

Explicitly NOT triggers (per §amendment-5):
- ❌ "Code looks suspicious" — natural-language inference
- ❌ "Library API might have changed" — vague intent

## Required workflow

### Step 1 — IDENTIFY THE CALL SITE

Read the source file at the named call site (e.g., `_claude_agent_sdk_invoker` in `src/dfg_harness/orchestrator/launcher.py`).

Capture the actual kwargs passed:
```python
options = claude_agent_sdk.ClaudeAgentOptions(
    system_prompt=directive.context_block,
    model=model,
)
```

### Step 2 — FETCH THE DOCUMENTED SURFACE

WebFetch the library's official docs URL (already cited in
`read_contract.external_libs[]` per ADR-019 §amendment-4).

Find the constructor/function signature in the docs. For
`ClaudeAgentOptions` per https://code.claude.com/docs/en/agent-sdk/python:
- `system_prompt` (str)
- `model` (str)
- `allowed_tools` (list[str])
- `max_turns` (int)
- `permission_mode` (str: "default" / "acceptEdits" / "bypassPermissions" / "plan")
- `cwd` (str | None)
- `additional_directories` (list[str])
- `env` (dict)
- ... (see docs for full surface)

### Step 3 — DIFF

Build a 3-column table:
| Documented kwarg | Passed at call site? | Default if absent |
|---|---|---|
| system_prompt | ✓ | n/a |
| model | ✓ | n/a |
| allowed_tools | ✗ | "limited set; Edit/Write/Bash NOT included by default" |
| max_turns | ✗ | "low default; insufficient for multi-file impl" |
| permission_mode | ✗ | "'default' — asks human; headless gets nothing" |
| cwd | ✗ | "current working directory of the calling process" |

### Step 4 — CLASSIFY EACH ABSENT KWARG

For each absent kwarg, classify:
- **load-bearing** — without it, the call's behavior is fundamentally wrong for this use case
- **defaultable** — the default is acceptable for this call
- **operator-overridable** — should be passed but with operator-tunable env var

Document the classification + rationale.

### Step 5 — PROPOSE FIX

Author the diff that adds the load-bearing + operator-overridable
kwargs. Include a docstring annotation citing the docs URL + verified_at
date per ADR-019 §amendment-4.

### Step 6 — TEST

Add a test that pins the call's options shape so the regression cannot
recur silently:

```python
def test_claude_agent_sdk_invoker_passes_full_options(...):
    # Capture the kwargs passed to ClaudeAgentOptions; assert all
    # load-bearing fields are present.
```

## Composition with other primitives

- **Composes-up** with `rca-dfg-codebase` (T3) — invoked AS a sub-skill
- **Composes-up** with `rca-harness-architecture` (T2) — for pattern-matching against known external-lib failure modes
- **Composes-laterally** with `verifying-external-package` (PR #553) — that skill verifies the IMPORT; this skill verifies the CALL
- **Composes-down** with `testing-hypothesis` — runs the test that pins the call shape

## Failure modes prevented

This skill would have caught:
- **#561** (4+ recurrences before identification) — `ClaudeAgentOptions(system_prompt, model)` with 4 missing load-bearing fields
- **W21-1 fabrication-cascade** — agents passed kwargs the deprecated `claude-code-sdk` didn't accept; would have surfaced "passed kwarg X not in documented surface"
- **#516** P7-vs-P11 cascade — would NOT catch this (it's logic, not call-shape)
- Future class: any new external-lib introduction where the call site under-constructs

## Test-of-skill (evaluation cases)

| Scenario | Expected output |
|---|---|
| `_claude_agent_sdk_invoker` ClaudeAgentOptions(system_prompt, model) with docs showing 4+ more fields | Identifies 4 absent kwargs; classifies each as load-bearing; proposes fix matching PR #562 |
| `yaml.safe_load(text)` (no kwargs needed beyond text) | Identifies no absent kwargs are load-bearing; passes |
| `anthropic.Anthropic()` constructor with documented `api_key`, `base_url`, `timeout` etc. | Identifies absent kwargs; classifies as defaultable (api_key from env) or operator-overridable |
| `subprocess.run([...])` (stdlib, but compose with non-stdlib) | Skill doesn't fire (stdlib outside scope) |

## References

- ADR-019 §amendment-4 (W22-8) — external-library API verification
- `verifying-external-package` skill — sister skill at the IMPORT layer
- #561 receipt — the empirical failure mode this skill prevents
- https://code.claude.com/docs/en/agent-sdk/python — claude-agent-sdk public API (verified 2026-05-06)
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices — Anthropic skill-authoring discipline
