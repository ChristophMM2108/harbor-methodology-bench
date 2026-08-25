#!/usr/bin/env bash
#
# Regenerate this kit from a CodeZen plugin checkout.
#
# CodeZen ships as a Claude Code / Codex *plugin*: it is installed from a
# marketplace into a plugin cache, and its skills locate their own supporting
# files through ${CLAUDE_PLUGIN_ROOT}. This kit is the same methodology
# reprojected as a *repository* checkout, so that `claude` and `codex` discover
# it natively from the working directory the way they discover sdd-agent-kit.
#
# The projection is mechanical and re-runnable, which is the point: the diff
# against upstream stays auditable instead of becoming a hand-maintained fork.
# See .codezen-kit/UPSTREAM.md for the exact transformations and why each one
# is needed.
#
# Usage: .codezen-kit/sync-from-plugin.sh [/path/to/codezen-plugin-checkout]

set -euo pipefail

KIT_ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
PLUGIN_SRC="${1:-$HOME/GitRepos/codezen-main}"

if [ ! -d "$PLUGIN_SRC/skills" ] || [ ! -d "$PLUGIN_SRC/standards" ]; then
    echo "not a CodeZen plugin checkout: $PLUGIN_SRC" >&2
    echo "expected skills/ and standards/ directories" >&2
    exit 1
fi

echo "kit:    $KIT_ROOT"
echo "plugin: $PLUGIN_SRC"

# --- 1. Skills, projected into both agents' discovery paths -----------------
#
# Claude Code reads .claude/skills/, Codex reads .agents/skills/. The plugin
# has a single skills/ directory that its manifests point both runtimes at, so
# a repository checkout has to carry two copies. They are byte-identical by
# construction; step 3 rewrites both.
for dest in .claude/skills .agents/skills; do
    rm -rf "$KIT_ROOT/$dest"
    mkdir -p "$KIT_ROOT/$dest"
    cp -a "$PLUGIN_SRC/skills/." "$KIT_ROOT/$dest/"
done

# --- 2. Supporting files the skills read by path ----------------------------
#
# standards/ is a reference library skills open directly. plugin/hooks/ holds
# the launcher and hook scripts; the skills already contain a repo-relative
# `plugin/hooks/...` fallback for when ${CLAUDE_PLUGIN_ROOT} is unset, so
# placing them here makes the *unmodified* upstream skill text resolve.
rm -rf "$KIT_ROOT/standards" "$KIT_ROOT/plugin"
mkdir -p "$KIT_ROOT/plugin"
cp -a "$PLUGIN_SRC/standards" "$KIT_ROOT/standards"
cp -a "$PLUGIN_SRC/hooks" "$KIT_ROOT/plugin/hooks"

# --- 3. The one rewrite: standards paths ------------------------------------
#
# Unlike the hook references, ${CLAUDE_PLUGIN_ROOT}/standards/... has no
# fallback in the upstream text. Unset in a plain checkout, it resolves to
# /standards/... and every read fails silently. Rewriting to a repo-relative
# path is the minimum change that makes the reference library reachable.
find "$KIT_ROOT/.claude/skills" "$KIT_ROOT/.agents/skills" -name 'SKILL.md' -print0 |
    xargs -0 sed -i 's|\${CLAUDE_PLUGIN_ROOT}/standards/|standards/|g'

# noc-tdd wraps those paths in two sentences of prose telling the agent to
# expand the variable before reading. With the paths now repo-relative there is
# nothing to expand, and leaving the instruction in would send the agent looking
# for a variable that is never set.
find "$KIT_ROOT/.claude/skills/noc-tdd" "$KIT_ROOT/.agents/skills/noc-tdd" -name 'SKILL.md' -print0 |
    xargs -0 sed -i \
      -e 's|The Read tool does \*\*not\*\* expand shell variables — resolve `\${CLAUDE_PLUGIN_ROOT}` first|Standards paths are relative to the repository root — read them directly|' \
      -e 's|(`echo "\$CLAUDE_PLUGIN_ROOT"` via Bash, or Glob for `standards/baseline.md`)\. Then read:|from the working directory. Read:|'

# --- 4. Report --------------------------------------------------------------
skills=$(find "$KIT_ROOT/.claude/skills" -mindepth 1 -maxdepth 1 -type d | wc -l)
# `grep -rl` exits 1 when it finds nothing, which is the success case here, so
# the pipeline is neutralised rather than allowed to trip `set -o pipefail`.
leftover=$({ grep -rl 'CLAUDE_PLUGIN_ROOT}/standards' "$KIT_ROOT/.claude/skills" "$KIT_ROOT/.agents/skills" 2>/dev/null || true; } | wc -l)

echo "synced $skills skills into .claude/skills and .agents/skills"
echo "standards files: $(find "$KIT_ROOT/standards" -type f | wc -l)"
echo "hook scripts:    $(find "$KIT_ROOT/plugin/hooks" -type f | wc -l)"

if [ "$leftover" -ne 0 ]; then
    echo "ERROR: $leftover skill file(s) still reference \${CLAUDE_PLUGIN_ROOT}/standards" >&2
    exit 1
fi
echo "ok: no unresolvable standards references remain"
