#!/usr/bin/env bash
set -euo pipefail

echo "=== 1. Checking Docker Health ==="
if ! docker run --rm hello-world >/dev/null 2>&1; then
    echo "❌ Docker network interface issue detected."
    echo "Please run: sudo modprobe veth && sudo systemctl restart docker"
    exit 1
fi
echo "✓ Docker is running cleanly."

echo "=== 2. Checking Local Credentials ==="
if [ ! -f "config/local.env" ]; then
    echo "❌ config/local.env is missing!"
    echo "Please create config/local.env with CLAUDE_CODE_OAUTH_TOKEN and CODEX_FORCE_AUTH_JSON=1."
    exit 1
fi
echo "✓ config/local.env found."

echo "=== 3. Executing Smoke Matrix (6 Cells) ==="

CELLS=(
    "smoke-claude-baseline-rerun|generated/baseline/adaptive-rejection-sampler|claude-code|claude-sonnet-5"
    "smoke-claude-sdd|generated/sdd/adaptive-rejection-sampler|claude-code|claude-sonnet-5"
    "smoke-claude-dfg|generated/dfg/adaptive-rejection-sampler|claude-code|claude-sonnet-5"
    "smoke-codex-baseline|generated/baseline/adaptive-rejection-sampler|codex|gpt-5.6-terra"
    "smoke-codex-sdd|generated/sdd/adaptive-rejection-sampler|codex|gpt-5.6-terra"
    "smoke-codex-dfg|generated/dfg/adaptive-rejection-sampler|codex|gpt-5.6-terra"
)

for item in "${CELLS[@]}"; do
    IFS="|" read -r job_name task_path agent model <<< "$item"
    if [ -d "jobs/$job_name" ]; then
        echo "--> Cleaning previous run: jobs/$job_name"
        rm -rf "jobs/$job_name"
    fi
    echo "--> Starting Cell: $job_name ($agent on $task_path)"
    harbor run -p "$task_path" -a "$agent" -m "$model" -n 1 --env-file config/local.env --job-name "$job_name"
    echo "✓ Finished $job_name"
    echo "----------------------------------------------------"
done

echo "=== All 6 Smoke Cells Executed Successfully ==="
