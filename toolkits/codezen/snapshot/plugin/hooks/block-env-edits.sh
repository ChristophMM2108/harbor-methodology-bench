#!/usr/bin/env bash
# Block edits/writes to .env files. Reads the PreToolUse JSON payload on stdin.
set -euo pipefail

input=$(cat)
file=$(printf '%s' "$input" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n1)

[[ -z "$file" ]] && exit 0

base=$(basename "$file")
case "$base" in
  .env|.env.*)
    echo "codezen: refusing to modify $file — .env files contain secrets and are protected by the codezen plugin." >&2
    exit 2
    ;;
esac

exit 0
