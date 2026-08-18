#!/usr/bin/env bash
set -euo pipefail

# Harbor Smoke Runner
#
# Runs the configured matrix across a single task to prove the pipeline
# end to end: containers build, credentials forward, verifiers emit rewards.

USAGE="Usage: $0 [--task ID] [--config PATH] [--force] [--dry-run]"

TASK="adaptive-rejection-sampler"
CONFIG="config/experiments.yaml"
EXTRA=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --task)
            TASK="$2"
            shift 2
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --force|--dry-run)
            EXTRA+=("$1")
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

exec ./scripts/run-pilot-experiment.sh \
    --config "$CONFIG" \
    --task "$TASK" \
    --job-prefix smoke \
    "${EXTRA[@]}"
