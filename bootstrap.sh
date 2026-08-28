#!/usr/bin/env sh
# One-command setup for harbor-methodology-bench.
#
# Needs only `git` and `curl` to start. It installs uv if missing, creates the
# project environment, installs the Harbor CLI and this repository's own `hmb`
# command, fetches every pinned source, and finishes by running `hmb doctor`.
#
# Idempotent: re-run it after pulling, or whenever `hmb doctor` reports a gap.
#
# Usage:
#   ./bootstrap.sh [--no-uv-install] [--no-harbor] [--no-tool] [--no-fetch] [--help]
#
#   --no-uv-install  fail instead of installing uv when it is absent
#   --no-harbor      skip `uv tool install harbor`
#   --no-tool        skip installing `hmb` globally; use `uv run hmb ...` instead
#   --no-fetch       skip `hmb setup`, so nothing is downloaded
set -eu

# Resolve the repository root from this script's own location, so the script can
# be invoked by any path from any working directory.
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"

INSTALL_UV=1
INSTALL_HARBOR=1
INSTALL_TOOL=1
FETCH=1

for arg in "$@"; do
    case "$arg" in
        --no-uv-install) INSTALL_UV=0 ;;
        --no-harbor)     INSTALL_HARBOR=0 ;;
        --no-tool)       INSTALL_TOOL=0 ;;
        --no-fetch)      FETCH=0 ;;
        -h|--help)       sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)               echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
    esac
done

step() { printf '\n== %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------------------
step "uv"
# ---------------------------------------------------------------------------
if have uv; then
    echo "present: $(uv --version)"
else
    if [ "$INSTALL_UV" -eq 0 ]; then
        echo "uv is not installed and --no-uv-install was given" >&2
        exit 1
    fi
    if ! have curl; then
        echo "curl is required to install uv; install uv manually: https://docs.astral.sh/uv/" >&2
        exit 1
    fi
    echo "installing uv ..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # The installer puts uv in one of these; add whichever exists to this shell.
    for candidate in "$HOME/.local/bin" "$HOME/.cargo/bin"; do
        [ -x "$candidate/uv" ] && PATH="$candidate:$PATH" && export PATH
    done
    have uv || { echo "uv installed but not on PATH; open a new shell and re-run" >&2; exit 1; }
    echo "installed: $(uv --version)"
fi

# ---------------------------------------------------------------------------
step "project environment"
# ---------------------------------------------------------------------------
# Pins the interpreter from .python-version and installs the runtime plus dev
# dependencies into .venv. The analysis extras stay out until they are wanted:
#   uv sync --group analysis
uv sync
echo "environment ready: $(uv run python --version)"

# ---------------------------------------------------------------------------
step "Harbor CLI"
# ---------------------------------------------------------------------------
if [ "$INSTALL_HARBOR" -eq 0 ]; then
    echo "skipped (--no-harbor)"
elif have harbor; then
    echo "present: harbor $(harbor --version 2>/dev/null | head -1)"
else
    uv tool install harbor
    echo "installed: harbor $(harbor --version 2>/dev/null | head -1)"
fi

# ---------------------------------------------------------------------------
step "hmb command"
# ---------------------------------------------------------------------------
if [ "$INSTALL_TOOL" -eq 0 ]; then
    echo "skipped (--no-tool); use \`uv run hmb ...\` from this directory"
else
    # Editable, so the command always reflects this checkout.
    uv tool install --force --editable .
    have hmb || echo "note: \`hmb\` is not on PATH yet — run \`uv tool update-shell\` and open a new shell"
fi

# ---------------------------------------------------------------------------
step "pinned sources"
# ---------------------------------------------------------------------------
if [ "$FETCH" -eq 0 ]; then
    echo "skipped (--no-fetch); run \`uv run hmb setup\` when you are ready"
else
    uv run hmb setup
fi

# ---------------------------------------------------------------------------
step "environment check"
# ---------------------------------------------------------------------------
# Never fail the bootstrap on a doctor warning: a missing agent CLI or an unset
# credential is a next step, not a broken installation.
uv run hmb doctor || true

cat <<'NEXT'

Next steps
  1. Put agent credentials in config/local.env   claude setup-token
  2. Pick a task set                             hmb catalogue --suite balanced --ids-only
  3. Create your experiment                      hmb experiment new my-run --toolkit demo-kit
  4. Build and prove the variants                hmb generate | validate | preflight --config ...
  5. Run it                                      ./scripts/run-pilot-experiment.sh --config ...

Read docs/setup.md for the long form, docs/experiments.md to declare conditions.
NEXT
