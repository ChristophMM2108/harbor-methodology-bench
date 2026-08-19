#!/usr/bin/env bash
set -euo pipefail

# Harbor Experiment Runner
#
# Runs the matrix declared in the experiment configuration across a selected
# group of tasks. Both the task list and the matrix cells come from the CLI, so
# this script never needs editing to change either.

USAGE=$(cat <<'EOF'
Usage: $0 [SELECTION] [OPTIONS]

Task selection (same flags as generate/validate/preflight; combinable):
  --task ID           One task; repeat for several
  --tasks-file PATH   Task ids, one per line ('#' comments allowed)
  --suite NAME        Any axis name, plus 'all' and 'balanced'
  --category NAME     Benchmark category, e.g. software-engineering
  --difficulty LEVEL  easy | medium | hard
  --limit N           Truncate the selection, applied last

Options:
  --config PATH       Experiment configuration (default config/experiments.yaml)
  --job-prefix NAME   Job name prefix (default 'pilot')
  --attempts N        Repetitions per cell, passed to harbor -n (default 1)
  --timeout-multiplier F
                      Scale every task timeout by F (harbor --timeout-multiplier).
                      Applied to every cell, so a comparison stays fair; record
                      the value with the result, since it changes the budget the
                      benchmark declares.
  --force             Re-run cells that already have results
  --dry-run           Print the harbor invocations without executing them
  --skip-preflight    Skip the validate/preflight gate (debugging only)

With no selection flags the run defaults to '--limit 5'.
EOF
)

CONFIG="config/experiments.yaml"
JOB_PREFIX="pilot"
ATTEMPTS=1
TIMEOUT_MULTIPLIER=""
FORCE=false
DRY_RUN=false
SKIP_PREFLIGHT=false
SELECTION=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --task|--tasks-file|--suite|--category|--difficulty|--limit)
            SELECTION+=("$1" "$2")
            shift 2
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --job-prefix)
            JOB_PREFIX="$2"
            shift 2
            ;;
        --attempts)
            ATTEMPTS="$2"
            shift 2
            ;;
        --timeout-multiplier)
            TIMEOUT_MULTIPLIER="$2"
            shift 2
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-preflight)
            SKIP_PREFLIGHT=true
            shift
            ;;
        -h|--help)
            echo "$USAGE"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1"
            echo "$USAGE"
            exit 1
            ;;
    esac
done

# An unbounded default would launch every task in the suite; keep the historical
# 5-task default when the caller names no selection at all.
if [ ${#SELECTION[@]} -eq 0 ]; then
    SELECTION=(--limit 5)
    echo "No task selection given; defaulting to ${SELECTION[*]}"
fi

echo "=== 1. Checking Environment Prerequisites ==="
if [ "$DRY_RUN" = false ]; then
    if ! docker run --rm hello-world >/dev/null 2>&1; then
        echo "❌ Docker network interface issue detected."
        echo "Please run: sudo modprobe veth && sudo systemctl restart docker"
        exit 1
    fi
    echo "✓ Docker is running cleanly."

    if [ ! -f "config/local.env" ]; then
        echo "❌ config/local.env is missing!"
        echo "Please create config/local.env with CLAUDE_CODE_OAUTH_TOKEN and CODEX_FORCE_AUTH_JSON=1."
        exit 1
    fi
    echo "✓ config/local.env found."
fi

# Resolve the task group through the same selection code the generator uses, so
# stale directories under generated/ can never join the run by accident.
mapfile -t TASKS < <(./scripts/catalogue.sh --config "$CONFIG" "${SELECTION[@]}" --ids-only)

if [ ${#TASKS[@]} -eq 0 ]; then
    echo "❌ Task selection matched no tasks."
    exit 1
fi

# Cells come from the configured matrix: cell_id <TAB> variant <TAB> agent <TAB> model
mapfile -t CELLS < <(uv run harbor-methodology-bench matrix-plan --config "$CONFIG")

if [ ${#CELLS[@]} -eq 0 ]; then
    echo "❌ The configured matrix is empty."
    exit 1
fi

# Timeout scaling is a property of the whole run, never of a single cell: a
# condition given more wall-clock than its comparison would be a confound.
HARBOR_EXTRA=()
if [ -n "$TIMEOUT_MULTIPLIER" ]; then
    HARBOR_EXTRA+=(--timeout-multiplier "$TIMEOUT_MULTIPLIER")
    echo "Task timeouts scaled by ${TIMEOUT_MULTIPLIER}× for every cell in this run."
fi

TOTAL_RUNS=$((${#TASKS[@]} * ${#CELLS[@]}))
echo "✓ Selected ${#TASKS[@]} task(s) × ${#CELLS[@]} cell(s) = $TOTAL_RUNS trial(s)"
for task in "${TASKS[@]}"; do
    echo "   - $task"
done
echo ""

MISSING=()
for task in "${TASKS[@]}"; do
    for cell in "${CELLS[@]}"; do
        IFS=$'\t' read -r _ variant _ _ <<< "$cell"
        [ -d "generated/${variant}/${task}" ] || MISSING+=("generated/${variant}/${task}")
    done
done
if [ ${#MISSING[@]} -gt 0 ]; then
    echo "⚠️  ${#MISSING[@]} selected variant(s) have not been generated, e.g. ${MISSING[0]}"
    echo "Generate them with the same selection:"
    echo "   ./scripts/generate-variants.sh --config $CONFIG ${SELECTION[*]} --force"
    # A dry run is a preview, so report the gap and carry on; a real run stops.
    if [ "$DRY_RUN" = false ]; then
        exit 1
    fi
    echo ""
fi

if [ "$DRY_RUN" = false ] && [ "$SKIP_PREFLIGHT" = false ]; then
    echo "=== 2. In-Container Preflight (methodology must reach the agent workdir) ==="
    ./scripts/validate-variants.sh --config "$CONFIG" "${SELECTION[@]}"
    ./scripts/preflight-variants.sh --config "$CONFIG" "${SELECTION[@]}"
fi

# Fail closed per cell: a trial may only run against a variant whose container
# was proven to carry (or, for the baseline, to lack) the methodology payload.
assert_preflight_passed() {
    local task_path="$1"
    python3 - "$task_path" <<'PY'
import json
import sys
from pathlib import Path

report = Path(sys.argv[1]) / ".methodology-bench-preflight.json"
if not report.is_file():
    sys.exit(f"missing preflight report: {report} (run ./scripts/preflight-variants.sh)")
data = json.loads(report.read_text())
if not data.get("passed"):
    sys.exit(f"preflight failed for {report}: {data.get('errors')}")
PY
}

# A `result.json` alone does not mean a cell produced data: an interrupted run
# leaves one behind with `finished_at: null` and its trials cancelled. Skipping
# such a directory would silently drop the cell from the matrix.
job_finished() {
    local job_dir="$1"
    [ -f "$job_dir/result.json" ] || return 1
    python3 - "$job_dir/result.json" <<'PY'
import json
import sys
from pathlib import Path

try:
    data = json.loads(Path(sys.argv[1]).read_text())
except (OSError, ValueError):
    raise SystemExit(1)
stats = data.get("stats") or {}
finished = data.get("finished_at") is not None
cancelled = int(stats.get("n_cancelled_trials") or 0)
raise SystemExit(0 if finished and not cancelled else 1)
PY
}

echo "=== 3. Starting Matrix ($TOTAL_RUNS total runs) ==="

RUN_IDX=0
PASSED_RUNS=0
FAILED_RUNS=0

for task in "${TASKS[@]}"; do
    for cell in "${CELLS[@]}"; do
        IFS=$'\t' read -r cell_id variant agent model <<< "$cell"
        RUN_IDX=$((RUN_IDX + 1))
        JOB_NAME="${JOB_PREFIX}-${cell_id}-${task}"
        TASK_PATH="generated/${variant}/${task}"

        echo "----------------------------------------------------"
        echo "[$RUN_IDX/$TOTAL_RUNS] Job: $JOB_NAME"
        echo "       Task: $task ($variant)"
        echo "       Agent: $agent ($model)"

        if [ "$DRY_RUN" = true ]; then
            echo "   [DRY RUN] harbor run -p $TASK_PATH -a $agent -m $model -n $ATTEMPTS ${HARBOR_EXTRA[*]:-} --env-file config/local.env --job-name $JOB_NAME"
            continue
        fi

        if [ "$SKIP_PREFLIGHT" = false ]; then
            assert_preflight_passed "$TASK_PATH"
        fi

        if [ -d "jobs/$JOB_NAME" ]; then
            if [ "$FORCE" = true ]; then
                echo "--> Removing previous job directory: jobs/$JOB_NAME"
                rm -rf "jobs/$JOB_NAME"
            else
                echo "--> Job directory jobs/$JOB_NAME exists. Checking result..."
                if job_finished "jobs/$JOB_NAME"; then
                    echo "--> Already completed. Skipping. (Use --force to re-run)"
                    PASSED_RUNS=$((PASSED_RUNS + 1))
                    continue
                else
                    echo "--> Incomplete job found. Cleaning and re-running..."
                    rm -rf "jobs/$JOB_NAME"
                fi
            fi
        fi

        # Execute trial and allow loop to continue even if individual trial errors
        if harbor run -p "$TASK_PATH" -a "$agent" -m "$model" -n "$ATTEMPTS" \
            ${HARBOR_EXTRA[@]+"${HARBOR_EXTRA[@]}"} \
            --env-file config/local.env --job-name "$JOB_NAME"; then
            echo "✓ Job completed: $JOB_NAME"
            PASSED_RUNS=$((PASSED_RUNS + 1))
        else
            echo "⚠️ Job exited with non-zero status: $JOB_NAME"
            FAILED_RUNS=$((FAILED_RUNS + 1))
        fi
    done
done

echo "===================================================="
if [ "$DRY_RUN" = true ]; then
    echo "✓ Dry run completed for $TOTAL_RUNS trial invocations."
else
    echo "Execution finished: $PASSED_RUNS completed / $FAILED_RUNS errored (out of $TOTAL_RUNS total)."
    echo "To generate the report, run:"
    echo "   python3 scripts/report.py --pattern \"${JOB_PREFIX}-*\""
fi
