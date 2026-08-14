#!/usr/bin/env bash
set -euo pipefail

# Harbor Pilot Experiment Runner
# Executes the 6-cell matrix across generated tasks (e.g. 5 tasks x 6 cells = 30 trials)

USAGE="Usage: $0 [--limit N] [--force] [--dry-run]"

LIMIT=5
FORCE=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --limit)
            LIMIT="$2"
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

# Discover available tasks from generated/baseline
if [ ! -d "generated/baseline" ]; then
    echo "❌ No generated tasks found in generated/baseline/."
    echo "Run: ./scripts/generate-variants.sh --limit $LIMIT --force"
    exit 1
fi

TASKS=($(find generated/baseline -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort | head -n "$LIMIT"))

if [ ${#TASKS[@]} -eq 0 ]; then
    echo "❌ No task directories found in generated/baseline/."
    exit 1
fi

echo "✓ Discovered ${#TASKS[@]} task(s) for Pilot Matrix:"
for task in "${TASKS[@]}"; do
    echo "   - $task"
done
echo ""

# Define the 6 Matrix Cells: cell_id | variant | agent | model
CELLS=(
    "claude-baseline|baseline|claude-code|claude-sonnet-5"
    "claude-sdd|sdd|claude-code|claude-sonnet-5"
    "claude-dfg|dfg|claude-code|claude-sonnet-5"
    "codex-baseline|baseline|codex|gpt-5.6-terra"
    "codex-sdd|sdd|codex|gpt-5.6-terra"
    "codex-dfg|dfg|codex|gpt-5.6-terra"
)

TOTAL_RUNS=$((${#TASKS[@]} * ${#CELLS[@]}))
echo "=== 2. Starting Pilot Matrix ($TOTAL_RUNS total runs) ==="

RUN_IDX=0
PASSED_RUNS=0
FAILED_RUNS=0

for task in "${TASKS[@]}"; do
    for cell in "${CELLS[@]}"; do
        IFS="|" read -r cell_id variant agent model <<< "$cell"
        RUN_IDX=$((RUN_IDX + 1))
        JOB_NAME="pilot-${cell_id}-${task}"
        TASK_PATH="generated/${variant}/${task}"

        echo "----------------------------------------------------"
        echo "[$RUN_IDX/$TOTAL_RUNS] Job: $JOB_NAME"
        echo "       Task: $task ($variant)"
        echo "       Agent: $agent ($model)"

        if [ "$DRY_RUN" = true ]; then
            echo "   [DRY RUN] harbor run -p $TASK_PATH -a $agent -m $model -n 1 --env-file config/local.env --job-name $JOB_NAME"
            continue
        fi

        if [ -d "jobs/$JOB_NAME" ]; then
            if [ "$FORCE" = true ]; then
                echo "--> Removing previous job directory: jobs/$JOB_NAME"
                rm -rf "jobs/$JOB_NAME"
            else
                echo "--> Job directory jobs/$JOB_NAME exists. Checking result..."
                if [ -f "jobs/$JOB_NAME/result.json" ]; then
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
        if harbor run -p "$TASK_PATH" -a "$agent" -m "$model" -n 1 --env-file config/local.env --job-name "$JOB_NAME"; then
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
    echo "Pilot Execution Finished: $PASSED_RUNS completed / $FAILED_RUNS errored (out of $TOTAL_RUNS total)."
    echo "To generate the report, run:"
    echo "   python scripts/report.py"
fi
