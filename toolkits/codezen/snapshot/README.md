# codezen-agent-kit

The CodeZen engineering method, packaged as a **repository checkout** rather
than as a Claude Code / Codex plugin.

Drop this repository's contents into a project and both `claude` and `codex`
discover the method natively from the working directory: `CLAUDE.md` and
`AGENTS.md` for the instructions, `.claude/skills/` and `.agents/skills/` for
the skills, `standards/` for the shared reference library.

## Why it exists

CodeZen upstream is installed from a marketplace, and its skills find their
supporting files through the `${CLAUDE_PLUGIN_ROOT}` variable that a plugin
runtime sets. That makes it invisible to any tool that measures a repository's
agent configuration by deploying the repository itself — including
`harbor-methodology-bench`, which is what this kit was built for.

This kit is the same method with the plugin assumptions removed. The full diff
against upstream is documented in
[`.codezen-kit/UPSTREAM.md`](.codezen-kit/UPSTREAM.md); it amounts to one
rewrite of the `standards/` paths plus files added around the unmodified skills.

## Layout

```text
codezen-agent-kit/
├── CLAUDE.md              # Claude Code instructions (managed block)
├── AGENTS.md              # Codex instructions (managed block)
├── .claude/
│   ├── settings.json      # block-env-edits PreToolUse hook
│   └── skills/            # 11 CodeZen skills, for Claude Code
├── .agents/
│   └── skills/            # the same 11 skills, for Codex
├── standards/             # shared reference library the skills read by path
│   ├── baseline.md
│   ├── design_cheatsheet.md
│   ├── layers/            # testing, auth_security, data_access, …
│   └── project_types/     # api_backend, genai_app, llm_nlp_app
├── plugin/hooks/          # hook and launcher scripts
└── .codezen-kit/
    ├── manifest.md        # version, entry points, per-skill runnability
    ├── UPSTREAM.md        # provenance and the exact adaptation diff
    └── sync-from-plugin.sh
```

## The workflow

```text
brainstorm → noc-tdd → code-review → noc-fix → security-review
```

`noc` means *no container*. `noc-tdd` and `noc-fix` run the Red-Green-Refactor
and fix cycles in the current session; `tdd` and `fix` do the same inside a
Docker sandbox and need a Docker daemon on the host. In a CI runner,
devcontainer or benchmark container, use the `noc-` variants.

`.codezen-kit/manifest.md` lists all eleven skills and what each one requires.
Four of them run in a plain checkout with nothing else present; the rest need a
Docker daemon, a running system under test, interactive input, or an MCP server.

## Regenerating from upstream

The kit is generated, not hand-maintained:

```bash
.codezen-kit/sync-from-plugin.sh /path/to/codezen-plugin-checkout
```

The script re-derives `.claude/skills/`, `.agents/skills/`, `standards/` and
`plugin/hooks/`, reapplies the single documented rewrite, and fails if any
unresolvable `${CLAUDE_PLUGIN_ROOT}/standards` reference survives. Files this
kit adds — `CLAUDE.md`, `AGENTS.md`, `.claude/settings.json`, `.codezen-kit/` —
are left alone.

## Upstream

CodeZen plugin `0.2.0`, from the `korzainc/marketplace` marketplace:

```
/plugin marketplace add korzainc/marketplace
/plugin install codezen@korza-marketplace
```

Use the plugin, not this kit, for day-to-day work on a machine with Docker.
