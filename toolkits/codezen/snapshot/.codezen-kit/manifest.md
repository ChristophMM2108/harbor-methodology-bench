# CodeZen Agent Kit Manifest

**Kit:** codezen-agent-kit
**Upstream plugin:** codezen 0.2.0
**Workflow:** brainstorm → noc-tdd → code-review → noc-fix → security-review

## Canonical entry points

- Codex instructions: `AGENTS.md`
- Claude Code instructions: `CLAUDE.md`
- Codex Skills: `.agents/skills/`
- Claude Code Skills: `.claude/skills/`
- Shared standards: `standards/`
- Hook and launcher scripts: `plugin/hooks/`

## Managed instruction markers

The installer owns only:

`<!-- CODEZEN-AGENT-KIT:START -->`

through:

`<!-- CODEZEN-AGENT-KIT:END -->`

All other content in `AGENTS.md` and `CLAUDE.md` is project-owned.

## Installed components

- 11 CodeZen Skills (`.claude/skills/`, `.agents/skills/`)
- 20-file shared standards library (`standards/`)
- 6 hook and launcher scripts (`plugin/hooks/`)
- `block-env-edits` PreToolUse hook (`.claude/settings.json`)
- Codex and Claude Code integration sections
- manifest

### Skills, and where each one can run

| Skill | Needs | Runs in a plain checkout |
|---|---|:---:|
| `noc-tdd` | nothing beyond the repo | yes |
| `noc-fix` | a prior `code-review` result | yes |
| `code-review` | subagents | yes |
| `security-review` | subagents | yes |
| `tdd` | Docker daemon | no |
| `fix` | Docker daemon | no |
| `setup` | interactive input, API keys | no |
| `brainstorm` | a human in the dialogue | no |
| `agentic-e2e` | a running system under test | no |
| `sut-bootstrap` | a running system under test | no |
| `to-notion` | Notion MCP server | no |

The `noc-` prefix means *no container*. In any environment without a Docker
daemon — a CI runner, a devcontainer, a benchmark container — `noc-tdd` and
`noc-fix` are the correct entry points and `tdd` / `fix` will fail at their
pre-flight check.

## Provenance and upgrade

This kit is generated from a CodeZen plugin checkout, not hand-maintained. See
`.codezen-kit/UPSTREAM.md` for the exact transformations. To upgrade, point the
sync script at a newer plugin checkout:

```bash
.codezen-kit/sync-from-plugin.sh /path/to/codezen-plugin
```

## Uninstall

Remove the managed CodeZen section from `AGENTS.md` and `CLAUDE.md`, then remove:

- `.codezen-kit/`
- `.agents/skills/` (the CodeZen skill directories)
- `.claude/skills/` (the CodeZen skill directories)
- `.claude/settings.json` hook entry
- `plugin/hooks/`
- `standards/`
