#!/usr/bin/env sh
set -eu
exec uv run harbor-methodology-bench freeze-verify "$@"
