#!/usr/bin/env bash
# Scaffold a new standalone skill under skills/<name>/
set -euo pipefail
NAME="${1:?Usage: new-skill.sh <skill-name>}"
DIR="skills/$NAME"
mkdir -p "$DIR"
cat > "$DIR/SKILL.md" <<EOD
---
name: $NAME
description: TODO — one or two sentences, including when Claude should use this.
---

TODO: instructions for this skill.
EOD
echo "Created $DIR/SKILL.md"
