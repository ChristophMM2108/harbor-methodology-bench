# claude-perf-toolkit

Skills, kits, and tools for improving Claude Code's performance: reducing
token usage, speeding up the development loop, and standardizing
spec-driven / repeatable workflows.

## Structure

- `kits/`   — multi-skill bundles with their own installer (see `kits/*/README.md`)
- `skills/` — standalone, single-purpose skills (just a `SKILL.md`, no installer)
- `tools/`  — shared code that skills/kits call into (not itself a skill)
- `docs/`   — architecture notes and authoring guides
- `tests/`  — integration tests for kit installers and tool correctness
- `scripts/` — scaffolding and promotion helpers

## Kit vs. Skill

Use a **kit** (`kits/`) when you need an installer, multiple related skills,
templates, or project-level state (constitution docs, manifests). Use a
**skill** (`skills/`) when it's a single `SKILL.md` with no supporting
installer machinery. Let the artifact's actual complexity decide — don't
force small wins through kit-level ceremony.

## Contributing

See `CONTRIBUTING.md` for authoring conventions and the checklist for
promoting a skill/kit to the company Claude skills repository.

## Adding a new kit or skill

```bash
./scripts/new-kit.sh <kit-name>
./scripts/new-skill.sh <skill-name>
```

## Promoting to the company skills repo

```bash
./scripts/package-for-upstream.sh <kits/skill-name | skills/skill-name>
```
