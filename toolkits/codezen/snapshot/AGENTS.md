<!-- CODEZEN-AGENT-KIT:START -->
## CodeZen Engineering Method

This repository uses the CodeZen Agent Kit.

For substantial changes, use:

`brainstorm → noc-tdd → code-review → noc-fix → security-review`

Canonical CodeZen locations:
- Shared standards: `standards/baseline.md`, `standards/layers/`, `standards/project_types/`
- Codex Skills: `.agents/skills/`
- Hook and launcher scripts: `plugin/hooks/`
- Kit manifest: `.codezen-kit/manifest.md`

Read `standards/baseline.md` and the relevant `standards/layers/*.md` before writing code. Write the test first: use `noc-tdd` for any feature or bugfix, and `code-review` before declaring work done. Never edit a `.env` file — the `block-env-edits` hook refuses it.

`noc-tdd` and `noc-fix` are the containerless variants and are the correct choice here; `tdd` and `fix` launch a Docker sandbox and require a Docker daemon on the host.

See `.codezen-kit/manifest.md` for the installed kit version and entry points.
<!-- CODEZEN-AGENT-KIT:END -->
