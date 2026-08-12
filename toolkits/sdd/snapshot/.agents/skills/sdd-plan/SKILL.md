---
name: sdd-plan
description: Create a repository-aware technical implementation plan from an approved SDD specification.
---

# SDD Plan

1. Read the full spec and constitution.
2. Inspect actual repository structure, patterns, dependencies, interfaces, configuration, and tests.
3. Reuse existing patterns where possible.
4. Record unknowns as `NEEDS CLARIFICATION`; do not guess.
5. Design components, data, contracts, state transitions, errors, security, observability, migrations, and rollout as applicable.
6. Compare meaningful alternatives.
7. Produce a file change map.
8. Map every requirement to verification.
9. If the design conflicts with a requirement, return to clarification/specification instead of silently changing the requirement.
