# SDD Constitution

Version: 1.1.0
Status: active

## Principle 1 — Requirements are explicit
Substantial behavior changes have version-controlled specifications with stable requirement IDs.

## Principle 2 — Behavior before technology
Specifications describe behavior, business rules, constraints, and non-goals. Technical choices belong in the plan unless they are requirements.

## Principle 3 — Repository-aware design
Plans must reflect actual repository structure, conventions, dependencies, interfaces, and tests.

## Principle 4 — Small executable tasks
Tasks should be independently understandable and verifiable, with explicit dependencies.

## Principle 5 — Traceability
Every requirement maps to implementation work and at least one verification method.

## Principle 6 — No silent scope changes
If implementation reveals that a requirement is wrong or incomplete, update the specification explicitly.

## Principle 7 — Behavioral verification
Passing tests is evidence, not the definition of correctness. Verification compares actual behavior with acceptance criteria.

## Principle 8 — Safety and compatibility
Authentication, authorization, secrets, migrations, persistence, external services, destructive operations, and backwards compatibility require explicit risk analysis.

## Principle 9 — Simplicity
Prefer the simplest design satisfying the specification and existing architecture.

## Principle 10 — Honest reporting
Agents distinguish between verified, inferred, not checked, and blocked. Never fabricate evidence.
