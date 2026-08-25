#!/usr/bin/env sh
set -eu
# Run from anywhere: resolve the repository root from this script's own location.
cd "$(dirname "$(readlink -f "$0")")/.."
exec uv run harbor-methodology-bench freeze-verify "$@"
