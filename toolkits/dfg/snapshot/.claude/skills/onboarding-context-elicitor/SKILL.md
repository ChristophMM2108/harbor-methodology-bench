---
name: onboarding-context-elicitor
description: Surfaces structured onboarding questions when new contributors are added
  to the repo. Fires on SessionStart only when unhandled ContributorAdded events exist
  in .dfg/events.jsonl. Prompts operator to run 'dfg onboarding context <user>' to
  elicit role, subsystem scope, tier, and notification channel.
criticality: important
sdlc_category: Operations
loop_layer: L2-wave
license: dfg-harness internal (Korza)
when_to_use: 'This skill AUTOMATICALLY fires at SessionStart (via hook or manual check)
  when:

  1. .dfg/events.jsonl contains one or more ContributorAdded events

  2. No matching OnboardingCompleted event exists for the same github_handle


  DO NOT manually invoke this skill — it''s substrate-triggered only.

  '
verified_at: 2026-05-06
forged_by: dfg-harness W26-6 onboarding-context-elicitor 2026-05-06
idempotent: true
trigger_conditions:
- ContributorAdded event exists in events.jsonl
- No OnboardingCompleted event for same github_handle
- SessionStart hook fires
---
# Onboarding Context Elicitor

## Purpose

Per ADR-022 multi-operator governance (W26-1), dfg-harness supports delegated authority across subsystems with cooperation-tiered enforcement. When a new contributor is added to the GitHub repo, the operator needs a structured onboarding flow to capture:

1. **Role** (peer-hub-leader / contributor / pilot)
2. **Subsystem scope** (which subsystems they can modify)
3. **Tier override** (default Tier 1 strong cooperation, or override to Tier 2/3)
4. **Notification channel** (where to ping for cooperation violations)

This skill surfaces a reminder to the operator when unhandled ContributorAdded events exist, directing them to run `dfg onboarding context <user>`.

## Trigger Conditions (Substrate-Evidence Only)

Per ADR-019 §amendment-5, this skill fires on **deterministic substrate signals**, not natural-language nudges:

**Auto-trigger when ALL of:**
1. SessionStart hook fires (or operator first turn in a new session)
2. `.dfg/events.jsonl` contains ≥1 `ContributorAdded` event (emitted by W26-5 gh-poll cron)
3. No matching `OnboardingCompleted` event exists for the same `github_handle`

**Detection logic:**
```python
import json
from pathlib import Path

def unhandled_contributor_added_events(repo_root: Path) -> list[str]:
    """Return list of github_handles with ContributorAdded but no OnboardingCompleted."""
    events_file = repo_root / ".dfg" / "events.jsonl"
    if not events_file.exists():
        return []
    
    added = set()
    completed = set()
    
    for line in events_file.read_text().splitlines():
        event = json.loads(line)
        if event.get("type") == "ContributorAdded":
            added.add(event["data"]["github_handle"])
        elif event.get("type") == "OnboardingCompleted":
            completed.add(event["data"]["github_handle"])
    
    return list(added - completed)
```

## Skill Action

When triggered, the skill surfaces a structured prompt to the operator:

```
## 🚀 New Contributor Detected

The following contributors were added to the repo but have not completed onboarding:

- @<handle-1>
- @<handle-2>

**Action required:**
Run `dfg onboarding context <user>` to elicit onboarding context (role, scope, tier, channel) and generate an authority.yaml diff PR.

Example:
  dfg onboarding context ashish
```

The skill does NOT invoke the CLI automatically — it prompts the operator to do so explicitly. This preserves the operator-in-the-loop discipline for VT2 governance changes.

## Composition with dfg onboarding CLI

The CLI command `dfg onboarding context <user>` (implemented in `src/dfg_harness/commands/onboarding.py`) walks through the structured Q&A and:

1. Prompts for role, scope, tier, channel
2. Updates `.dfg/governance/authority.yaml`
3. Creates a welcome retrospective at `.dfg/retrospectives/W26/onboarding-<user>.md`
4. Commits changes to a branch `feat/onboard-<user>`
5. Opens a PR via `gh pr create`
6. Emits `OnboardingCompleted` event to `.dfg/events.jsonl`

The OnboardingCompleted event prevents this skill from re-firing for the same user.

## Idempotency Contract

**Idempotent: true**

The skill fires once per unhandled ContributorAdded event. After `dfg onboarding context` completes and emits OnboardingCompleted, the detection logic filters that user out and the skill no longer fires for them.

Multiple contributors can be onboarded in sequence — the skill surfaces all unhandled contributors in a single prompt.

## Layer Classification

- **SDLC category:** Operations (onboarding is a sprint-level ceremony, not a unit-level action)
- **Loop layer:** L2-wave (onboarding happens once per contributor, aligned with sprint/wave cadence)

## Composes With

- **W26-1 ADR-022** — multi-operator governance model that defines authority.yaml schema
- **W26-5 gh-poll** — emits ContributorAdded events that trigger this skill
- **W26-2 cooperation-classifier** — classifies contributions after onboarding completes
- **ADR-019 §amendment-5** — substrate-evidence trigger discipline

## When This Skill REFUSES

- ❌ **SessionStart with no ContributorAdded events** — skill short-circuits with no output
- ❌ **All ContributorAdded events have matching OnboardingCompleted** — no unhandled contributors
- ❌ **Called manually outside SessionStart** — skill is substrate-triggered only; manual invocation is a no-op

## Implementation Notes

This skill is a **passive reminder skill** per ADR-024 optional-feature discipline. It surfaces information but does NOT gate execution. The operator can defer onboarding (e.g., contributor added but not actively working yet) without blocking other work.

The OnboardingCompleted event is the canonical signal that onboarding finished. If the operator runs `dfg onboarding context` but abandons the PR, the event is NOT emitted and the skill continues to fire — intentional, because onboarding is incomplete until the PR merges.

## Test-of-Skill (Evaluation Cases)

| Scenario | Expected Behavior |
|---|---|
| SessionStart + 1 ContributorAdded, no OnboardingCompleted | Skill fires with 1 github_handle listed |
| SessionStart + 2 ContributorAdded, 1 OnboardingCompleted | Skill fires with 1 unhandled github_handle |
| SessionStart + ContributorAdded + OnboardingCompleted (same handle) | Skill does not fire (no unhandled contributors) |
| SessionStart + no ContributorAdded events | Skill does not fire |
| Manual invocation outside SessionStart | Skill no-ops (substrate-triggered only) |

## References

- ADR-022 multi-operator governance (W26-1)
- ADR-019 §amendment-5 substrate-evidence trigger discipline
- W26-5 gh-poll team listener (ContributorAdded event producer)
- `.dfg/governance/authority.yaml` schema
- `.dfg/governance/subsystems.yaml` scope options
- `.dfg/governance/cooperation-tiers.yaml` tier definitions
