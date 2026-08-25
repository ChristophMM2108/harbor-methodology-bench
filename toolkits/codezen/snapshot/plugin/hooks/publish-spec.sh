#!/usr/bin/env bash
# =============================================================================
# CodeZen publish-spec.sh — used by the brainstorm skill (and future
# /update-spec, /decompose-spec) to handle the mechanical side of writing
# a spec to disk and (optionally) publishing it to Linear via codezen-server.
# =============================================================================
#
# Modes:
#   --check
#       Layer-1 readiness check. No network. Verifies CODEZEN_SERVER_URL is set
#       and that curl + jq are on PATH. Prints LINEAR_CONFIGURED:<url> on
#       success (exit 0) or LINEAR_NOT_CONFIGURED + reasons on failure (exit 1).
#
#   --publish --target {linear|local} --slug <s> --title <t>
#              --content-file <path> [--journal <path>]
#       Writes the spec to docs/specs/<slug>.md and commits. When --target is
#       'linear', POSTs to ${CODEZEN_SERVER_URL}/specs first and writes a
#       pointer file instead of the full spec. On Linear-upload failure,
#       stashes the composed spec at .brainstorm/pending/<slug>.md and exits
#       non-zero — does NOT silently fall back to local (user explicitly chose
#       Linear).
#
# Output (--publish): a single JSON object on stdout — the calling skill
# parses it to report status to the user.
#
# Exit codes:
#   0   success
#   1   --check failed (Linear not configured) — or env-level error during
#       publish
#   2   usage error (bad/missing args)
#   3   Linear upload failed — spec stashed at .brainstorm/pending/<slug>.md
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
NC=$'\033[0m'

log()  { echo "${GREEN}[publish-spec]${NC} $*"; }
warn() { echo "${YELLOW}[publish-spec]${NC} $*" >&2; }
err()  { echo "${RED}[publish-spec]${NC} $*" >&2; }

usage() {
    cat <<EOF >&2
Usage:
  publish-spec.sh --check
  publish-spec.sh --publish --target {linear|local} \\
      --slug <slug> --title <title> \\
      --content-file <path> [--journal <path>]
EOF
    exit 2
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
MODE=""
TARGET=""
SLUG=""
TITLE=""
CONTENT_FILE=""
JOURNAL=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --check)         MODE="check";          shift   ;;
        --publish)       MODE="publish";        shift   ;;
        --target)        TARGET="$2";           shift 2 ;;
        --slug)          SLUG="$2";             shift 2 ;;
        --title)         TITLE="$2";            shift 2 ;;
        --content-file)  CONTENT_FILE="$2";     shift 2 ;;
        --journal)       JOURNAL="$2";          shift 2 ;;
        -h|--help)       usage ;;
        *)               err "Unknown argument: $1"; usage ;;
    esac
done

[[ -z "$MODE" ]] && usage

# ---------------------------------------------------------------------------
# Mode: --check  (Layer-1: env + tools, no network)
# ---------------------------------------------------------------------------
if [[ "$MODE" == "check" ]]; then
    issues=()
    [[ -z "${CODEZEN_SERVER_URL:-}" ]] && issues+=("CODEZEN_SERVER_URL not set")
    command -v curl >/dev/null 2>&1 || issues+=("curl not installed")
    command -v jq   >/dev/null 2>&1 || issues+=("jq not installed")

    if [[ ${#issues[@]} -eq 0 ]]; then
        echo "LINEAR_CONFIGURED: ${CODEZEN_SERVER_URL}"
        exit 0
    fi

    echo "LINEAR_NOT_CONFIGURED"
    for issue in "${issues[@]}"; do
        echo "  - ${issue}"
    done
    exit 1
fi

# ---------------------------------------------------------------------------
# Mode: --publish  (write spec, commit, optionally upload to Linear)
# ---------------------------------------------------------------------------
[[ -z "$TARGET"        ]] && { err "--target required for --publish";       usage; }
[[ -z "$SLUG"          ]] && { err "--slug required for --publish";         usage; }
[[ -z "$CONTENT_FILE"  ]] && { err "--content-file required for --publish"; usage; }
[[ ! -f "$CONTENT_FILE" ]] && { err "Content file does not exist: $CONTENT_FILE"; exit 2; }

case "$TARGET" in
    linear|local) ;;
    *) err "--target must be 'linear' or 'local' (got '$TARGET')"; exit 2 ;;
esac

SPEC_PATH="docs/specs/${SLUG}.md"
TODAY=$(date -u +%Y-%m-%d)

# Remove the journal — its content is now embedded in the spec or in Linear.
# Called on success paths only.
cleanup_journal() {
    # Note: must use `if` rather than `&&` so the function always returns 0.
    # With `set -e`, a `[[ ]] && rm` form that short-circuits via a false test
    # causes the whole function (and thus the script) to exit non-zero.
    if [[ -n "$JOURNAL" && -f "$JOURNAL" ]]; then
        rm -f "$JOURNAL"
    fi
}

# Stage + commit the spec. $1 = commit message.
commit_spec() {
    local msg="$1"
    git add "$SPEC_PATH" .gitignore 2>/dev/null || true
    if git commit -m "$msg" >/dev/null 2>&1; then
        git rev-parse HEAD
    else
        warn "git commit produced no new commit (no staged changes?)"
        echo "unknown"
    fi
}

# ---------------------------------------------------------------------------
# Target: local
# ---------------------------------------------------------------------------
if [[ "$TARGET" == "local" ]]; then
    mkdir -p "$(dirname "$SPEC_PATH")"
    cp "$CONTENT_FILE" "$SPEC_PATH"
    cleanup_journal

    COMMIT_MSG=$(cat <<EOF
docs(spec): add ${SLUG} spec

Linear publishing not selected — spec stored locally only.
EOF
)
    COMMIT_SHA=$(commit_spec "$COMMIT_MSG")

    jq -n \
        --arg target "local" \
        --arg spec_path "$SPEC_PATH" \
        --arg commit_sha "$COMMIT_SHA" \
        '{status: "success", target: $target, spec_path: $spec_path, commit_sha: $commit_sha}'
    exit 0
fi

# ---------------------------------------------------------------------------
# Target: linear
# ---------------------------------------------------------------------------
[[ -z "$TITLE" ]] && { err "--title required when --target=linear"; exit 2; }

if [[ -z "${CODEZEN_SERVER_URL:-}" ]]; then
    err "CODEZEN_SERVER_URL not set — cannot publish to Linear"
    err "Run --check first to verify configuration"
    exit 1
fi

# Ensure required tools (mirrors --check, but --check may not have been called)
for tool in curl jq; do
    command -v "$tool" >/dev/null 2>&1 || { err "$tool not installed"; exit 1; }
done

PENDING_DIR=".brainstorm/pending"

stash_and_exit() {
    local reason="$1"
    mkdir -p "$PENDING_DIR"
    local stash_path="${PENDING_DIR}/${SLUG}.md"
    cp "$CONTENT_FILE" "$stash_path"

    jq -n \
        --arg reason "$reason" \
        --arg stash_path "$stash_path" \
        '{status: "error", target: "linear", reason: $reason, stash_path: $stash_path}'

    err "Linear upload failed: ${reason}"
    err "Composed spec stashed at: ${stash_path}"
    exit 3
}

RESPONSE_BODY=$(mktemp)
trap 'rm -f "$RESPONSE_BODY"' EXIT

# Build the JSON payload via jq --rawfile so the entire spec content is
# correctly JSON-escaped without any sed/printf gymnastics.
HTTP_CODE=$(curl -sS -o "$RESPONSE_BODY" -w '%{http_code}' \
    --max-time 30 \
    -X POST "${CODEZEN_SERVER_URL%/}/specs" \
    -H "Content-Type: application/json" \
    --data-binary @<(jq -n \
        --arg slug    "$SLUG" \
        --arg title   "$TITLE" \
        --rawfile content "$CONTENT_FILE" \
        '{slug: $slug, title: $title, content: $content, source: "brainstorm-cli"}') \
    2>/dev/null || echo "000")

if [[ "$HTTP_CODE" != "200" && "$HTTP_CODE" != "201" ]]; then
    body=$(head -c 500 "$RESPONSE_BODY" 2>/dev/null || echo "")
    stash_and_exit "HTTP ${HTTP_CODE}: ${body:-<empty response>}"
fi

LINEAR_DOC_ID=$(jq -r '.linear_doc_id  // empty' "$RESPONSE_BODY")
LINEAR_DOC_URL=$(jq -r '.linear_doc_url // empty' "$RESPONSE_BODY")

if [[ -z "$LINEAR_DOC_ID" || -z "$LINEAR_DOC_URL" ]]; then
    stash_and_exit "server response missing linear_doc_id or linear_doc_url"
fi

# Extract the first non-empty paragraph from the spec's ## Overview section.
# Used as the pointer file's summary so the repo browser sees some content
# without having to click through to Linear.
SUMMARY=$(awk '
    /^## Overview$/ { in_overview = 1; next }
    /^## / && in_overview { exit }
    in_overview && NF { lines[++n] = $0 }
    in_overview && !NF && n > 0 { exit }
    END { for (i = 1; i <= n; i++) print lines[i] }
' "$CONTENT_FILE" | head -5)

[[ -z "$SUMMARY" ]] && SUMMARY="(See Linear Document for full content.)"

mkdir -p "$(dirname "$SPEC_PATH")"
cat > "$SPEC_PATH" <<EOF
---
type: codezen-spec-pointer
slug: ${SLUG}
title: ${TITLE}
linear_doc_id: ${LINEAR_DOC_ID}
linear_doc_url: ${LINEAR_DOC_URL}
status: draft
created: ${TODAY}
last_synced_version: 1
---

# ${TITLE}

> **Authoritative source:** [Linear Document](${LINEAR_DOC_URL})
>
> This is a pointer file. The spec lives in Linear — edit there, not here.
> A read-only mirror at \`docs/specs/cache/${SLUG}.cached.md\` will be
> auto-updated by codezen-server when the Linear Document changes.

## Summary
${SUMMARY}
EOF

cleanup_journal

COMMIT_MSG=$(cat <<EOF
docs(spec): add ${SLUG} spec pointer

Spec published to Linear: ${LINEAR_DOC_URL}

Linear-doc: ${LINEAR_DOC_ID}
EOF
)
COMMIT_SHA=$(commit_spec "$COMMIT_MSG")

jq -n \
    --arg target "linear" \
    --arg spec_path "$SPEC_PATH" \
    --arg linear_doc_id "$LINEAR_DOC_ID" \
    --arg linear_doc_url "$LINEAR_DOC_URL" \
    --arg commit_sha "$COMMIT_SHA" \
    '{status: "success", target: $target, spec_path: $spec_path,
      linear_doc_id: $linear_doc_id, linear_doc_url: $linear_doc_url,
      commit_sha: $commit_sha}'
exit 0
