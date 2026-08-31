#!/usr/bin/env bash
set -euo pipefail

# Harbor Experiment Runner
#
# Runs the matrix declared in the experiment configuration across a selected
# group of tasks. Both the task list and the matrix cells come from the CLI, so
# this script never needs editing to change either.
#
# One Harbor job per agent holds every condition. Harbor gives each trial a
# random directory suffix and records its condition under `config.task.path`,
# so conditions cannot collide and `hmb report` still separates them. Within a
# job the dataset list is task-major, which is what makes the conditions of one
# task run side by side instead of one whole condition after another — paired
# execution keeps host contention symmetric across conditions.

# Every path below is relative to the repository root, so run from anywhere.
REPO_ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
cd "$REPO_ROOT"

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
  --job-prefix NAME   Job name prefix (default 'pilot'); jobs are '<prefix>-<agent>'
  --attempts N        Repetitions per cell (Harbor's --n-attempts, default 1)
  --concurrent N      Concurrent trials per job, whole lifecycle (default 9)
  --concurrent-agents N
                      Concurrent agent phases per job (default 6, must be <= --concurrent)
  --preflight-jobs N  Parallel image builds in the preflight gate (default 4)
  --timeout-multiplier F
                      Scale every task timeout by F (harbor --timeout-multiplier).
                      Applied to every cell, so a comparison stays fair; record
                      the value with the result, since it changes the budget the
                      benchmark declares.
  --force             Delete and re-run jobs that already have results
  --dry-run           Print the job configs and the harbor invocations only
  --skip-preflight    Skip the validate/preflight gate (debugging only)

With no selection flags the run defaults to '--limit 5'.

An interrupted job is resumed, never silently accepted: use
`hmb resume jobs/<prefix>-<agent>`, which classifies the failures first and
re-runs only those unrelated to the task.
EOF
)

CONFIG="config/experiments.yaml"
JOB_PREFIX="pilot"
ATTEMPTS=1
CONCURRENT=9
CONCURRENT_AGENTS=6
PREFLIGHT_JOBS=4
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
        --concurrent)
            CONCURRENT="$2"
            shift 2
            ;;
        --concurrent-agents)
            CONCURRENT_AGENTS="$2"
            shift 2
            ;;
        --preflight-jobs)
            PREFLIGHT_JOBS="$2"
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
        echo "❌ Docker cannot start a container."
        echo "If container networking fails with 'failed to add the host (veth...) <=> sandbox"
        echo "(veth...) pair interfaces: operation not supported', compare the running kernel"
        echo "with the installed module tree first:"
        echo "    uname -r && ls /lib/modules/"
        echo "  - They differ: the kernel was upgraded without a reboot. No module can load"
        echo "    for the running kernel, so modprobe cannot help. Reboot."
        echo "  - They match: the module is merely unloaded. Run"
        echo "    sudo modprobe veth && sudo systemctl restart docker"
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
# The CLI, however this checkout was set up: the globally installed `hmb` when
# it is on PATH, otherwise the project environment's copy. Never a bare path.
if command -v hmb >/dev/null 2>&1; then
    HMB=(hmb)
else
    HMB=(uv run --project "$REPO_ROOT" hmb)
fi

mapfile -t TASKS < <("${HMB[@]}" catalogue --config "$CONFIG" "${SELECTION[@]}" --ids-only)

if [ ${#TASKS[@]} -eq 0 ]; then
    echo "❌ Task selection matched no tasks."
    exit 1
fi

# Cells come from the configured matrix: cell_id <TAB> variant <TAB> agent <TAB> model
mapfile -t CELLS < <("${HMB[@]}" matrix-plan --config "$CONFIG")

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

TOTAL_RUNS=$((${#TASKS[@]} * ${#CELLS[@]} * ATTEMPTS))
echo "✓ Selected ${#TASKS[@]} task(s) × ${#CELLS[@]} cell(s) × $ATTEMPTS attempt(s) = $TOTAL_RUNS trial(s)"
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
    echo "   hmb generate --config $CONFIG ${SELECTION[*]} --force"
    # A dry run is a preview, so report the gap and carry on; a real run stops.
    if [ "$DRY_RUN" = false ]; then
        exit 1
    fi
    echo ""
fi

# The gate is mandatory for a second reason under parallel execution: it builds
# every image up front, so the run's own builds are cache hits. `docker build`
# runs on the daemon, outside any container's cpu allowance, and is the one part
# of a trial that concurrency can genuinely contend over.
if [ "$DRY_RUN" = false ] && [ "$SKIP_PREFLIGHT" = false ]; then
    echo "=== 2. In-Container Preflight (methodology must reach the agent workdir) ==="
    "${HMB[@]}" validate --config "$CONFIG" "${SELECTION[@]}"
    "${HMB[@]}" preflight --config "$CONFIG" "${SELECTION[@]}" --jobs "$PREFLIGHT_JOBS"
fi

# Fail closed per variant: a trial may only run against a variant whose container
# was proven to carry (or, for the baseline, to lack) the methodology payload.
assert_preflight_passed() {
    local task_path="$1"
    python3 - "$task_path" <<'PY'
import json
import sys
from pathlib import Path

report = Path(sys.argv[1]) / ".methodology-bench-preflight.json"
if not report.is_file():
    sys.exit(f"missing preflight report: {report} (run `hmb preflight`)")
data = json.loads(report.read_text())
if not data.get("passed"):
    sys.exit(f"preflight failed for {report}: {data.get('errors')}")
PY
}

# A `result.json` alone does not mean a job produced data: an interrupted run
# leaves one behind with `finished_at: null` and its trials cancelled. Skipping
# such a directory would silently drop those cells from the matrix.
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

if [ "$SKIP_PREFLIGHT" = false ] && [ "$DRY_RUN" = false ]; then
    for task in "${TASKS[@]}"; do
        for cell in "${CELLS[@]}"; do
            IFS=$'\t' read -r _ variant _ _ <<< "$cell"
            assert_preflight_passed "generated/${variant}/${task}"
        done
    done
fi

# One job config per agent, written where the run can be reproduced from it.
PLAN_DIR="jobs/${JOB_PREFIX}-plan"
TASK_ARGS=()
for task in "${TASKS[@]}"; do
    TASK_ARGS+=(--task "$task")
done

echo "=== 3. Planning Jobs ==="
"${HMB[@]}" plan-job \
    --config "$CONFIG" \
    "${TASK_ARGS[@]}" \
    --job-prefix "$JOB_PREFIX" \
    --attempts "$ATTEMPTS" \
    --n-concurrent "$CONCURRENT" \
    --n-concurrent-agents "$CONCURRENT_AGENTS" \
    --out-dir "$PLAN_DIR"

mapfile -t PLANS < <(ls "$PLAN_DIR"/*.yaml)

if [ "$DRY_RUN" = true ]; then
    for plan in "${PLANS[@]}"; do
        job_name="$(basename "$plan" .yaml)"
        echo "   [DRY RUN] harbor run -c $plan ${HARBOR_EXTRA[*]:-} --env-file config/local.env"
        echo "             -> jobs/$job_name, log jobs/${job_name}.log"
    done
    echo ""
    echo "✓ Dry run completed for ${#PLANS[@]} job(s), $TOTAL_RUNS trial(s)."
    exit 0
fi

echo ""
echo "=== 4. Running ${#PLANS[@]} job(s), $TOTAL_RUNS trial(s), $CONCURRENT concurrent ==="

# Each job writes to its own log: parallel jobs must never interleave on the
# terminal, or neither log can be read afterwards.
PIDS=()
NAMES=()
for plan in "${PLANS[@]}"; do
    job_name="$(basename "$plan" .yaml)"
    job_dir="jobs/$job_name"
    log="jobs/${job_name}.log"

    if [ -d "$job_dir" ]; then
        if [ "$FORCE" = true ]; then
            echo "--> Removing previous job directory: $job_dir"
            rm -rf "$job_dir"
        elif job_finished "$job_dir"; then
            echo "--> $job_name already completed. Skipping. (Use --force to re-run)"
            continue
        else
            echo "--> $job_name exists but did not finish."
            echo "    Resume it instead of re-running: hmb resume $job_dir"
            echo "    A bare re-run would discard the trials it already paid for."
            continue
        fi
    fi

    echo "--> $job_name  (log: $log)"
    harbor run -c "$plan" \
        ${HARBOR_EXTRA[@]+"${HARBOR_EXTRA[@]}"} \
        --env-file config/local.env >"$log" 2>&1 &
    PIDS+=("$!")
    NAMES+=("$job_name")
done

PASSED_JOBS=0
FAILED_JOBS=0
for index in "${!PIDS[@]}"; do
    if wait "${PIDS[$index]}"; then
        echo "✓ Job completed: ${NAMES[$index]}"
        PASSED_JOBS=$((PASSED_JOBS + 1))
    else
        echo "⚠️ Job exited with non-zero status: ${NAMES[$index]} (see jobs/${NAMES[$index]}.log)"
        FAILED_JOBS=$((FAILED_JOBS + 1))
    fi
done

echo "===================================================="
echo "Execution finished: $PASSED_JOBS completed / $FAILED_JOBS errored (out of ${#PIDS[@]} job(s))."
echo "Trials ran up to $CONCURRENT at a time, so duration_sec carries host contention"
echo "and is not comparable with the serial numbers in results/. Cost and token"
echo "metrics are unaffected."
echo "To generate the report, run:"
echo "   hmb report --pattern \"${JOB_PREFIX}-*\" --md-out results/${JOB_PREFIX}_report.md"
