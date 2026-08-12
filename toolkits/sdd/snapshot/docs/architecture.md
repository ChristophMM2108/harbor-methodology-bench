# Architecture

## Design principles

- Token budgets are a first-class concern: prefer minimal, structured
  context over dumping full files.
- Skills should degrade gracefully — flag what they can't resolve rather
  than guessing.
- Kits own their own installer and are safe to re-run (idempotent,
  managed-section pattern — see `kits/sdd-agent-kit`).

## When to build a kit vs. a skill

Build a **kit** when the feature needs an installer, templates, or
multi-file project state. Build a **skill** when it's a single instruction
file that either needs no supporting code or calls into `tools/`.
