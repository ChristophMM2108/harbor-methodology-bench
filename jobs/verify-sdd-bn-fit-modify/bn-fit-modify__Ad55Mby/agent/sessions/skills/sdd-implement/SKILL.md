---
name: sdd-implement
description: Implement one approved SDD task at a time while preserving specification and task boundaries.
---

# SDD Implement

1. Select the next pending task with completed dependencies.
2. Read the task plus linked requirements and acceptance criteria.
3. Read relevant plan sections.
4. Inspect existing code before editing.
5. Implement the smallest change satisfying the task.
6. Add/update required tests.
7. Run focused and broader relevant validation.
8. If the spec/plan is defective, stop and report it rather than silently redefining behavior.
9. Mark a task complete only after evidence exists.
10. Report files changed, commands actually run, results, remaining tasks, and blockers.

Do not opportunistically refactor unrelated code.
