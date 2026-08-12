#!/usr/bin/env bash
# Scaffold a new kit under kits/<name>/
set -euo pipefail
NAME="${1:?Usage: new-kit.sh <kit-name>}"
DIR="kits/$NAME"
mkdir -p "$DIR"/{.agents/skills,.claude/skills,docs,tests}
cat > "$DIR/README.md" <<EOD
# $NAME

TODO: describe what this kit does, its workflow stages, and how to install it.

## Install

\`\`\`bash
./install.sh /path/to/project
\`\`\`
EOD
cat > "$DIR/install.sh" <<'EOD'
#!/usr/bin/env bash
set -euo pipefail
echo "TODO: implement installer (managed-section pattern recommended)"
EOD
chmod +x "$DIR/install.sh"
touch "$DIR/manifest.md"
echo "Created $DIR"
