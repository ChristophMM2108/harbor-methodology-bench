# SDD Agent Kit Manifest

**Kit:** sdd-agent-kit
**Version:** 1.1.0
**Workflow:** specify → clarify → plan → tasks → analyze → implement → verify

## Canonical entry points

- Codex instructions: `AGENTS.md`
- Claude Code instructions: `CLAUDE.md`
- Codex Skills: `.agents/skills/`
- Claude Code Skills: `.claude/skills/`
- Constitution: `docs/sdd/constitution.md`
- Specifications: `docs/sdd/specs/`

## Managed instruction markers

The installer owns only:

`<!-- SDD-AGENT-KIT:START -->`

through:

`<!-- SDD-AGENT-KIT:END -->`

All other content in `AGENTS.md` and `CLAUDE.md` is project-owned.

## Installed components

- 7 SDD Skills
- SDD constitution
- specification/plan/task/verification templates
- Codex and Claude Code integration sections
- manifest

## Upgrade

Re-run the installer from a newer kit version. It is designed to be idempotent.

## Uninstall

Remove the managed SDD section from `AGENTS.md` and `CLAUDE.md`, then remove:

- `.sdd-kit/`
- `.agents/skills/sdd-*`
- `.claude/skills/sdd-*`

Remove `docs/sdd/` only if it contains no project-owned material.
