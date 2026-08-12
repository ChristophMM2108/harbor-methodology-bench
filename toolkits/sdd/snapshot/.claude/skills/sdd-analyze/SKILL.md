---
name: sdd-analyze
description: Perform read-only consistency analysis across an SDD specification, plan, and tasks before coding.
---

# SDD Analyze

Check:

- every requirement maps to tasks;
- every acceptance criterion maps to verification;
- every task references requirements;
- no task contradicts the spec;
- plan decisions satisfy the spec;
- dependencies are acyclic;
- no task adds unrequested scope;
- security, migration, external integration, and compatibility risks are addressed;
- verification is concrete.

Report `PASS`, `WARN`, or `FAIL` with artifact and stable IDs. This phase is read-only.
