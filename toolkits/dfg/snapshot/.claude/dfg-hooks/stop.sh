#!/usr/bin/env bash
# Tier-1 Stop hook — turn-end projection trigger.
#
# Routing: V02-ARCHITECTURE §4.2 row "Discipline heartbeat" → Stop (async).
# Mode: passive (tier 1). Never blocks Claude Code's continuation. Exit code
# is informational; the host runs this async and ignores nonzero in PASSIVE
# mode.
#
# What it does today: invokes `dfg index` to replay events.jsonl into the
# derived projections (state.json, master-index.md, PROVENANCE_INDEX.md,
# modifications.md). The projector itself is a W3 deliverable; today this is
# a no-op stub that logs and exits 0 when the command does not exist.
#
# Latency budget: V02-ARCHITECTURE §4.3 commits to p95 < 500ms for sync
# command hooks (warm-cache). This script's own overhead is single-digit ms;
# `dfg index` carries the budget responsibility once W3 landed.
#
# W63-3 empirical receipts (2026-05-16): the per-turn `dfg index` invocation
# costs ~500-1100ms warm-cache and ~1100-4100ms cold-cache. Cold-start cost
# is legitimate work — uv resolve, dfg import, events.jsonl reprojection of
# 15k+ events — not a regression. The doctor.py SMOKE_CEILING_MS = 5000ms
# covers cold-start variance; BUDGET_MS_SYNC_COMMAND = 500ms remains the
# warm-cache p95 production target. Use `dfg doctor --hooks --warm-only` on
# CI to assert the warm budget separately from cold-start variance.
# Receipts: W61-1 release-prep (4110ms cold breach), W63 admission (2099ms).

set -u
PASSIVE="${PASSIVE:-1}"
DFG_ROOT="${DFG_ROOT:-.}"
_W518_T0_NS="$(date +%s%N 2>/dev/null || python3 -c 'import time;print(int(time.time()*1e9))')"

log() {
  printf '[stop] %s\n' "$*" >&2
}

# W5-18: HookFire emission via the shared stdlib-only Python helper.
# Non-blocking — _emit_event.py's CLI always exits 0 even on bad input.
_w518_emit_hookfire() {
  result="${1:-allow}"
  rationale="${2:-}"
  now_ns="$(date +%s%N 2>/dev/null || python3 -c 'import time;print(int(time.time()*1e9))')"
  latency_ms="$(python3 -c "print((${now_ns} - ${_W518_T0_NS}) / 1e6)" 2>/dev/null || echo 0)"
  emit_args="--name=stop --result=${result} --latency-ms=${latency_ms} --phase=during --hook-path=kit/hooks/stop.sh"
  if [ -n "${rationale}" ]; then
    python3 "${DFG_ROOT}/kit/hooks/_emit_event.py" $emit_args --rationale="${rationale}" >/dev/null 2>&1 || true
  else
    python3 "${DFG_ROOT}/kit/hooks/_emit_event.py" $emit_args >/dev/null 2>&1 || true
  fi
}

# Always exit 0 in passive mode, regardless of how we got here.
trap '
  status=$?
  if [ "${PASSIVE}" != "0" ]; then
    if [ "${status}" -ne 0 ]; then
      log "ignoring exit ${status} (PASSIVE=${PASSIVE})"
    fi
    exit 0
  fi
  exit "${status}"
' EXIT

# Drain stdin so Claude Code's pipe close is clean. Today the payload is
# unused; future tiers may extract session_id.
if [ -p /dev/stdin ] || [ ! -t 0 ]; then
  cat >/dev/null 2>&1 || true
fi

if ! command -v dfg >/dev/null 2>&1; then
  log "dfg CLI not on PATH — Tier-1 stub (W3 ships the projector)"
  _w518_emit_hookfire "allow" ""
  exit 0
fi

# `dfg index` may not yet be implemented; tolerate "unknown command" the same
# way we tolerate the CLI itself being missing.
if ! dfg index --help >/dev/null 2>&1; then
  log "dfg index unavailable — Tier-1 stub"
  _w518_emit_hookfire "allow" ""
  exit 0
fi

# Real invocation — once W3 ships, this is the actual heartbeat.
if ! dfg index --root "${DFG_ROOT}"; then
  log "dfg index returned nonzero — passive, not blocking"
  _w518_emit_hookfire "error" "dfg index returned nonzero"
  exit 0
fi

_w518_emit_hookfire "allow" ""
exit 0
