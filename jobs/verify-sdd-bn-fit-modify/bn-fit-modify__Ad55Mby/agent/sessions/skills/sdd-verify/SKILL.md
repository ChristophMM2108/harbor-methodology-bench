---
name: sdd-verify
description: Verify implemented behavior against the SDD specification, acceptance criteria, tests, and repository behavior.
---

# SDD Verify

1. Read spec, plan, tasks, constitution, and resulting code/tests.
2. Build requirement → task → verification traceability.
3. Run relevant automated checks.
4. Exercise important acceptance criteria behaviorally where practical.
5. Check edge cases, errors, security, compatibility, migrations, and observability specified by the feature.
6. Use only:
   - PASS = verified with evidence
   - FAIL = behavior violates requirement
   - BLOCKED = prerequisite unavailable
   - UNCHECKED = not attempted
7. Never turn BLOCKED or UNCHECKED into PASS.
8. Write `verification.md`.
9. Create follow-up tasks for gaps.
10. `complete` requires every in-scope requirement to PASS and required checks to pass.
