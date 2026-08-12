#!/usr/bin/env bash
# Tier-1 PostToolUse hook — append a JSONL event to .dfg/events.jsonl.
#
# Routing: V02-ARCHITECTURE §4.2 row "Provenance auto-update" →
# PostToolUse (async). Mode: passive (tier 1). Never blocks; the host runs
# this async and the operator's experience never depends on its exit code.
#
# TWO call modes (W132-1):
#
#   1. Hook mode — the Claude Code hook runner invokes this script with a
#      JSON payload on stdin (and env vars from .claude/settings.json,
#      e.g. `PASSIVE=1 DFG_EVENT_TYPE=Edit kit/hooks/event-log.sh`).
#      Detected by: zero positional args AND a non-empty stdin payload.
#      Env-var driven; DFG_EVENT_TYPE defaults to "Edit"; the PASSIVE trap
#      converts every failure to exit 0. W134-1: when DFG_EVENT_FILE is
#      unset, the file path is parsed from the payload itself
#      (tool_input.file_path → tool_input.path → tool_input.notebook_path);
#      only genuinely path-less payloads (e.g. Bash) keep the legacy
#      "(unknown)" sentinel under PASSIVE=1 — honest, not a bug.
#
#   2. Manual mode — an operator/agent invokes the script directly (no
#      payload on stdin, or with positional args). W132-1 hardening:
#      misuse FAILS LOUDLY (usage on stderr + non-zero exit, no append):
#        * positional args are given, or
#        * DFG_EVENT_TYPE is unset/empty, or
#        * DFG_EVENT_TYPE is Read|Write|Edit and DFG_EVENT_FILE is
#          unset/empty.
#      The "(unknown)" sentinel is UNREACHABLE in manual mode, and manual
#      emissions stamp the enum-valid `actor: "agent"` (events.schema.json
#      actor enum; never "agent:claude"-style composites — richer identity
#      belongs under metadata). Retires the 5-receipt footgun
#      (W126-3/4/5, W127-2, W128-1): silent Edit-"(unknown)" appends from
#      forgotten env vars.
#
# Inputs (env vars provided by the Claude Code hook runner / caller):
#   DFG_EVENT_TYPE   — one of the canonical types in events.schema.json
#                      (Read|Write|Edit|TaskDispatch|TaskComplete|GateCheck|
#                       HitlIntervention|Compaction|StateTransition).
#                      Hook mode default: "Edit" (the most common
#                      PostToolUse trigger). Manual mode: REQUIRED.
#   DFG_EVENT_FILE   — repo-relative path the event refers to. Required for
#                      Read/Write/Edit per the schema's allOf.
#   DFG_EVENT_UNIT   — optional W<N>(-<M>)? id; honoured if it matches the
#                      schema's pattern.
#   DFG_EVENT_META   — optional JSON object string to merge under `metadata`.
#
# Output: appends ONE line to ${DFG_ROOT}/.dfg/events.jsonl. Stdout is silent
# on the happy path so PostToolUse stdout never leaks into Claude's view.
#
# Latency budget: V02-ARCHITECTURE §4.3 — p95 < 500ms. This script targets
# single-digit ms (one process invocation, one append).

set -u
PASSIVE="${PASSIVE:-1}"
DFG_ROOT="${DFG_ROOT:-.}"
EVENTS_FILE="${DFG_ROOT}/.dfg/events.jsonl"
_W518_T0_NS="$(date +%s%N 2>/dev/null || python3 -c 'import time;print(int(time.time()*1e9))')"

log() {
  printf '[event-log] %s\n' "$*" >&2
}

# W5-18: Emit a HookFire event for this hook firing (separate from the
# domain event the hook itself appends below). Non-blocking — the helper
# always exits 0 even on failure.
_w518_emit_hookfire() {
  result="${1:-allow}"
  now_ns="$(date +%s%N 2>/dev/null || python3 -c 'import time;print(int(time.time()*1e9))')"
  latency_ms="$(python3 -c "print((${now_ns} - ${_W518_T0_NS}) / 1e6)" 2>/dev/null || echo 0)"
  python3 "${DFG_ROOT}/kit/hooks/_emit_event.py" \
    --name=event-log \
    --result="${result}" \
    --latency-ms="${latency_ms}" \
    --phase=during \
    --hook-path=kit/hooks/event-log.sh \
    >/dev/null 2>&1 || true
}

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

# Capture the stdin payload when the caller piped one (Claude Code hook
# runner feeds the hook-event JSON on stdin). Pre-W132 this was drained to
# /dev/null; W132-1 kept it to DETECT hook mode; W134-1 additionally parses
# tool_input.* file paths from it when DFG_EVENT_FILE is unset (env vars
# keep precedence — the v0.2 contract).
HOOK_PAYLOAD=""
if [ -p /dev/stdin ] || [ ! -t 0 ]; then
  HOOK_PAYLOAD="$(cat 2>/dev/null || true)"
fi

# Mode detection (W132-1): hook mode iff NO positional args AND a
# non-whitespace payload arrived on stdin. Everything else — tty stdin,
# empty/closed stdin (subprocess stdin=DEVNULL), or positional args — is
# a manual invocation and gets the hardened validation below.
INVOCATION_MODE="manual"
if [ "$#" -eq 0 ] && [ -n "$(printf '%s' "${HOOK_PAYLOAD}" | tr -d '[:space:]')" ]; then
  INVOCATION_MODE="hook"
fi

usage() {
  cat >&2 <<'USAGE'
[event-log] usage (manual env-var mode):
  DFG_EVENT_TYPE=<Read|Write|Edit|TaskDispatch|TaskComplete|GateCheck|HitlIntervention|Compaction|StateTransition> \
  DFG_EVENT_FILE=<repo-relative-path>   # REQUIRED for Read|Write|Edit \
  [DFG_EVENT_UNIT=W<N>-<M>] [DFG_EVENT_META='{"k":"v"}'] \
  kit/hooks/event-log.sh
Positional arguments are not accepted. W132-1: manual misuse fails loudly —
no silent Edit/"(unknown)" sentinel appends (receipts: W126-3/4/5, W127-2, W128-1).
USAGE
}

# Manual misuse must fail loudly even under PASSIVE=1 — clear the trap so
# the non-zero exit propagates to the caller. Nothing has been appended.
_usage_fail() {
  usage
  trap - EXIT
  exit 2
}

if [ "${INVOCATION_MODE}" = "manual" ]; then
  if [ "$#" -gt 0 ]; then
    log "positional arguments are not accepted (got: $*)"
    _usage_fail
  fi
  if [ -z "${DFG_EVENT_TYPE:-}" ]; then
    log "DFG_EVENT_TYPE is required in manual mode"
    _usage_fail
  fi
  case "${DFG_EVENT_TYPE}" in
    Read|Write|Edit)
      if [ -z "${DFG_EVENT_FILE:-}" ]; then
        log "DFG_EVENT_FILE is required for DFG_EVENT_TYPE=${DFG_EVENT_TYPE}"
        _usage_fail
      fi
      ;;
  esac
fi

EVENT_TYPE="${DFG_EVENT_TYPE:-Edit}"
EVENT_FILE="${DFG_EVENT_FILE:-}"
EVENT_UNIT="${DFG_EVENT_UNIT:-}"
EVENT_META="${DFG_EVENT_META:-}"

# W245-1 (ADR-040 Phase B-2): when no explicit unit was provided, resolve the
# active unit from the git worktree branch so execution events emitted INSIDE a
# unit's worktree carry per-unit attribution — the signal the Phase C competence
# objective calibrates on (today these events are 0-6% attributed because the
# hooks fire unit-blind; see rddl.calibrate.attribution_coverage). Branch
# convention is output_contract.branch_name = feat/w<N>-<M>-<slug>  ->  unit
# W<N>-<M>. SCOPED to the execution event types this script emits, so the
# Read/Write/Edit hot path takes NO extra git call (latency budget p95<500ms).
# Defensive: no git / detached HEAD / main / no-match all leave the unit empty —
# exactly today's behaviour, never a WRONG attribution. The inline serialiser
# below re-validates against ^W[0-9]+(-[0-9]+)?$ and drops anything off-pattern.
if [ -z "${EVENT_UNIT}" ]; then
  case "${EVENT_TYPE}" in
    TaskDispatch | TaskComplete | HitlIntervention)
      _dfg_branch="$(git -C "${DFG_ROOT}" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
      _dfg_unit="$(printf '%s' "${_dfg_branch}" | grep -oiE 'w[0-9]+-[0-9]+' | head -n 1 || true)"
      if [ -n "${_dfg_unit}" ]; then
        # Canonicalise the leading w/W -> W (strip first char, re-prefix).
        EVENT_UNIT="W${_dfg_unit#?}"
      fi
      ;;
  esac
fi

# Build the JSONL line via python3 so we get correct escaping. Falling back
# to printf-with-jq would add a runtime dep we don't want here.
if ! command -v python3 >/dev/null 2>&1; then
  log "python3 not on PATH — cannot serialise event"
  exit 1
fi

# W134-1: in HOOK-PAYLOAD mode, extract the real file path from the Claude
# Code hook-event JSON (tool_input.file_path, falling back to tool_input.path
# then tool_input.notebook_path). Explicit DFG_EVENT_FILE keeps precedence
# (the v0.2 env-var contract); the payload fills the gap so PostToolUse
# events carry real paths instead of the "(unknown)" sentinel. Path-less
# tools (e.g. Bash) and malformed payloads leave EVENT_FILE empty — the
# serialiser's honest legacy fallback below is unchanged. The payload is
# piped on stdin (not env) so large Edit payloads can't hit env-size limits.
# Stdlib json only; any parse failure yields an empty result.
if [ "${INVOCATION_MODE}" = "hook" ] && [ -z "${EVENT_FILE}" ]; then
  PAYLOAD_FILE_PATH="$(printf '%s' "${HOOK_PAYLOAD}" | python3 -c '
import json, sys
try:
    payload = json.load(sys.stdin)
    tool_input = payload.get("tool_input")
    if isinstance(tool_input, dict):
        for key in ("file_path", "path", "notebook_path"):
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                print(value)
                break
except Exception:
    pass
' 2>/dev/null || true)"
  if [ -n "${PAYLOAD_FILE_PATH}" ]; then
    EVENT_FILE="${PAYLOAD_FILE_PATH}"
  fi
fi

if LINE="$(
  DFG_EVENT_TYPE="${EVENT_TYPE}" \
  DFG_EVENT_FILE="${EVENT_FILE}" \
  DFG_EVENT_UNIT="${EVENT_UNIT}" \
  DFG_EVENT_META="${EVENT_META}" \
  DFG_EVENT_MODE="${INVOCATION_MODE}" \
  python3 - <<'PY'
import json, os, re, sys
from datetime import datetime, timezone

CANONICAL_TYPES = {
    "Read", "Write", "Edit", "TaskDispatch", "TaskComplete",
    "GateCheck", "HitlIntervention", "Compaction", "StateTransition",
}

mode = os.environ.get("DFG_EVENT_MODE", "hook")

t = os.environ.get("DFG_EVENT_TYPE", "Edit")
if t not in CANONICAL_TYPES:
    print(f"[event-log] non-canonical type {t!r}; coercing to 'Edit'", file=sys.stderr)
    t = "Edit"

ev = {
    "type": t,
    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}

f = os.environ.get("DFG_EVENT_FILE") or ""
if f:
    ev["file"] = f
elif t in {"Read", "Write", "Edit"}:
    # Schema requires `file` for these.
    # W132-1: in MANUAL mode this is unreachable misuse (the shell guard
    # already failed loudly for explicit Read/Write/Edit; a non-canonical
    # type coerced to Edit lands here) — fail, never append a sentinel.
    # In HOOK mode the legacy behaviour is preserved byte-identically:
    # fail-closed only under PASSIVE=0; under PASSIVE emit the sentinel
    # so downstream replay can spot it.
    if mode == "manual":
        print(f"[event-log] DFG_EVENT_FILE required for type={t} (manual mode)", file=sys.stderr)
        sys.exit(2)
    if os.environ.get("PASSIVE", "1") == "0":
        print(f"[event-log] DFG_EVENT_FILE required for type={t}", file=sys.stderr)
        sys.exit(2)
    print(f"[event-log] DFG_EVENT_FILE empty for type={t}; emitting sentinel", file=sys.stderr)
    ev["file"] = "(unknown)"

unit = os.environ.get("DFG_EVENT_UNIT") or ""
if unit and re.match(r"^W[0-9]+(-[0-9]+)?$", unit):
    ev["unit"] = unit
elif unit:
    print(f"[event-log] non-canonical unit {unit!r}; dropping", file=sys.stderr)

meta_raw = os.environ.get("DFG_EVENT_META") or ""
if meta_raw:
    try:
        meta = json.loads(meta_raw)
        if isinstance(meta, dict):
            ev["metadata"] = meta
        else:
            print(f"[event-log] DFG_EVENT_META not an object; dropping", file=sys.stderr)
    except json.JSONDecodeError as exc:
        print(f"[event-log] DFG_EVENT_META JSON parse error: {exc}; dropping", file=sys.stderr)

# W132-1: manual emissions stamp an enum-valid actor (events.schema.json
# actor enum: dispatch|agent|operator|hook|ci|critic|watchdog-consumer).
# NEVER a composite like "agent:claude" — richer identity belongs under
# metadata. Hook-mode envelopes stay byte-identical (no actor field).
if mode == "manual":
    ev["actor"] = "agent"

print(json.dumps(ev, ensure_ascii=False, separators=(",", ":")))
PY
)"; then
  : # serialiser succeeded — fall through to append
else
  rc=$?
  log "event serialiser exited ${rc}; not appending"
  if [ "${INVOCATION_MODE}" = "manual" ]; then
    # W132-1: manual failures propagate even under PASSIVE=1.
    trap - EXIT
    exit "${rc}"
  fi
  # Trap converts to 0 under PASSIVE=1; propagates rc under PASSIVE=0.
  exit "${rc}"
fi

# Chained append (W161-3, W159-1 follow-up): route the domain event through
# _emit_event.py's _flock_append choke point so it picks up prev_digest
# (verified by `dfg substrate attest`). DFG_ROOT is passed explicitly so the
# python side resolves the SAME ${DFG_ROOT}/.dfg/events.jsonl as this script.
# On ANY failure fall back to the legacy raw append — losing the chain link
# is acceptable, losing the event is not.
mkdir -p "${DFG_ROOT}/.dfg"
if [ -f "${DFG_ROOT}/kit/hooks/_emit_event.py" ] \
  && printf '%s\n' "${LINE}" | DFG_ROOT="${DFG_ROOT}" python3 "${DFG_ROOT}/kit/hooks/_emit_event.py" append; then
  : # chained append landed (prev_digest injected under flock)
else
  log "chained append unavailable; falling back to raw (unchained) append"
  printf '%s\n' "${LINE}" >> "${EVENTS_FILE}"
fi

# W5-18: Emit HookFire after the domain-event append so the HookFire
# detail.latency_ms reflects the full hook duration (not pre-append).
_w518_emit_hookfire "allow"
exit 0
