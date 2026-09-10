#!/usr/bin/env bash
# Render every diagrams/*.mmd to PDF (for LaTeX) and PNG (for preview).
#
# mermaid-cli drives a headless browser. There is no bundled chrome-headless-shell
# here, so it is pointed at the system Chrome through puppeteer.json.
set -euo pipefail
cd "$(dirname "$0")/.."
DIAG=diagrams
CHROME=${CHROME:-$(command -v google-chrome-stable || command -v chromium || true)}
if [[ -z "$CHROME" ]]; then
  echo "no Chrome/Chromium found; set CHROME=/path/to/chrome" >&2
  exit 1
fi
cat > "$DIAG/puppeteer.json" <<JSON
{"executablePath":"$CHROME","args":["--no-sandbox","--disable-dev-shm-usage"]}
JSON
for f in "$DIAG"/*.mmd; do
  base=$(basename "$f" .mmd)
  echo "  $base"
  npx -y @mermaid-js/mermaid-cli@11 -p "$DIAG/puppeteer.json" -c "$DIAG/mermaid-config.json" \
      -b transparent -i "$f" -o "$DIAG/$base.pdf" --pdfFit >/dev/null 2>&1
  npx -y @mermaid-js/mermaid-cli@11 -p "$DIAG/puppeteer.json" -c "$DIAG/mermaid-config.json" \
      -b white -i "$f" -o "$DIAG/$base.png" -s 3 >/dev/null 2>&1
done
echo "done: $(ls "$DIAG"/*.pdf | wc -l) diagrams"
