#!/usr/bin/env bash
# Package a kit or skill into ./.upstream-staging/ for promotion to the
# company Claude skills repository.
set -euo pipefail
SRC="${1:?Usage: package-for-upstream.sh <kits/name | skills/name>}"

if [ ! -d "$SRC" ]; then
  echo "Error: '$SRC' not found." >&2
  exit 1
fi

DEST=".upstream-staging/$(basename "$SRC")"
rm -rf "$DEST"
mkdir -p "$DEST"
cp -R "$SRC/." "$DEST/"

echo "TODO: strip repo-local paths / internal references in $DEST"
echo "TODO: run tools/skill_validator against $DEST"
echo "Staged at: $DEST"
