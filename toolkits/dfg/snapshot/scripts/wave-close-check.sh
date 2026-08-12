#!/usr/bin/env bash
# scripts/wave-close-check.sh
# Wave-gate close enforcement check for harness-perf.
#
# Bootstrapped from dfg-harness v0.11.71 — see
# kit/METHODOLOGY/02-dfg-construction.md § "Wave-gate close — enforced
# discipline (the lock)" for the rationale.
#
# Two modes:
#   - light (default): runs on every CI invocation; fails if main has recent unresolved CI failures
#   - full (--full):    runs on wave-close PRs; adds wave-state checks + make ci verification
#
# Exit codes:
#   0 = pass
#   1 = check failed (block merge)
#   2 = environment problem (gh missing, etc.)
#
# Designed to be deterministic and cheap. No retries; no waits; no network calls
# beyond a single gh API query. Total runtime: < 5 seconds in the typical case.

set -euo pipefail

MODE="light"
if [ "${1:-}" = "--full" ]; then
  MODE="full"
fi

# --- Red-main hotfix recovery lane -------------------------------------------
# Ordinary PRs stay blocked when latest main CI is red. The one safe exception
# is a PR that explicitly declares itself as the red-main hotfix for the exact
# failed main run. This avoids a broad env-var bypass while still allowing the
# repair PR to prove itself in CI.
_declared_red_main_hotfix_pr() {
  failed_run_id="${1:-}"

  [ "${MODE}" = "light" ] || return 1
  [ "${GITHUB_EVENT_NAME:-}" = "pull_request" ] || return 1
  [ -n "${GITHUB_EVENT_PATH:-}" ] || return 1
  [ -f "${GITHUB_EVENT_PATH:-}" ] || return 1
  command -v jq >/dev/null 2>&1 || return 1

  title="$(jq -r '.pull_request.title // ""' "${GITHUB_EVENT_PATH}" 2>/dev/null || echo "")"
  body="$(jq -r '.pull_request.body // ""' "${GITHUB_EVENT_PATH}" 2>/dev/null || echo "")"
  number="$(jq -r '.pull_request.number // ""' "${GITHUB_EVENT_PATH}" 2>/dev/null || echo "")"

  printf '%s\n' "$title" | grep -qi 'red-main' || return 1
  printf '%s\n' "$body" | grep -qi 'red-main hotfix' || return 1
  printf '%s\n%s\n' "$title" "$body" | grep -q "$failed_run_id" || return 1

  echo "✅ light check passed in declared red-main hotfix mode"
  echo "   PR #${number:-unknown} cites failed main CI run ${failed_run_id}."
  echo "   This does not mark main healthy; it lets the repair PR prove itself."
  return 0
}

# --- Sanity: gh CLI present and authenticated ---------------------------------
if ! command -v gh >/dev/null 2>&1; then
  echo "wave-close-check: gh CLI not installed; skipping (warn-only)" >&2
  exit 0  # in environments without gh, skip rather than block (e.g., local docs-only edits)
fi

# Best-effort auth check; if not authenticated, skip gracefully
if ! gh auth status >/dev/null 2>&1; then
  echo "wave-close-check: gh not authenticated; skipping (warn-only)" >&2
  exit 0
fi

# --- Determine repo (works inside a fork too) ---------------------------------
# This script checks THIS project's own CI on main — not the harness's.
REPO="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")}"
if [ -z "$REPO" ]; then
  echo "wave-close-check: cannot determine repo; skipping (warn-only)" >&2
  exit 0
fi

# --- Light check: is the latest CI run on main green? -------------------------
# Deterministic semantic: "main is healthy NOW means the most recent CI on main
# concluded SUCCESS." Historical failures since-fixed don't block.
# This runs on EVERY CI invocation as the anti-drift lock.
echo "wave-close-check ($MODE): checking latest CI run on main for $REPO..."

LATEST=$(gh run list \
  --repo "$REPO" \
  --branch main \
  --workflow ci.yml \
  --limit 1 \
  --json status,conclusion,databaseId 2>/dev/null \
  | jq -r '.[0] // {} | "\(.status):\(.conclusion):\(.databaseId)"' 2>/dev/null \
  || echo "::")

LATEST_STATUS=$(echo "$LATEST" | cut -d: -f1)
LATEST_CONCLUSION=$(echo "$LATEST" | cut -d: -f2)
LATEST_ID=$(echo "$LATEST" | cut -d: -f3)

if [ -z "$LATEST_ID" ] || [ "$LATEST_STATUS" = "" ]; then
  # No history — typical for fresh bootstrapped projects before the first
  # main CI run lands. Skip warn-only; the lock activates from run 2 onwards.
  echo "wave-close-check: no recent CI runs found on main; skipping (warn-only)"
  exit 0
fi

# In-flight runs are not failures; pass through (the run we just kicked off
# may still be pending when this script runs in the same CI job).
if [ "$LATEST_STATUS" != "completed" ]; then
  echo "✅ light check passed (latest main CI is in-flight: $LATEST_STATUS)"
  exit 0
fi

if [ "$LATEST_CONCLUSION" != "success" ]; then
  if _declared_red_main_hotfix_pr "$LATEST_ID"; then
    exit 0
  fi

  echo ""
  echo "❌ WAVE-CLOSE BLOCKED — latest CI run on main is $LATEST_CONCLUSION"
  echo ""
  echo "The discipline says: no wave closes while main is broken."
  echo ""
  echo "Inspect: gh run view $LATEST_ID --repo $REPO --log-failed"
  echo ""
  echo "Fix:"
  echo "  - Open a hotfix PR addressing the failure"
  echo "  - After it merges and CI goes green on main, this check passes again"
  echo ""
  exit 1
fi

echo "✅ light check passed (latest main CI: success, run $LATEST_ID)"

# --- Full check: only on wave-close PRs ---------------------------------------
if [ "$MODE" != "full" ]; then
  exit 0
fi

echo ""
echo "wave-close-check (full): running wave-state checks..."

# Verify PROVENANCE_INDEX.md is non-empty and references a recent wave
if [ ! -f "PROVENANCE_INDEX.md" ]; then
  echo "❌ WAVE-CLOSE BLOCKED — PROVENANCE_INDEX.md not found"
  exit 1
fi

# Look for recent wave-closure markers (e.g. "W4 closed")
if ! grep -qE 'W[0-9]+ (closed|MERGED)' PROVENANCE_INDEX.md; then
  echo "⚠ warning: PROVENANCE_INDEX.md has no wave-closure markers"
  echo "   This may be the very first wave; otherwise update the index header."
fi

# Verify make ci passes
if ! make ci > /tmp/wave-close-make-ci.log 2>&1; then
  echo "❌ WAVE-CLOSE BLOCKED — make ci failed"
  echo "   Last lines:"
  tail -20 /tmp/wave-close-make-ci.log
  exit 1
fi

echo "✅ full check passed (provenance + make ci both green)"
echo ""
echo "Wave-close gate is OPEN."
exit 0
