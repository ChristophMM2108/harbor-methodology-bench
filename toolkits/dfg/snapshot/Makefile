.PHONY: install test test-push test-impact-pr-full test-pr-fast test-pr-full test-release test-nightly \
        test-fast test-full lint fmt fix ci doctor build clean help \
        wave-close wave-close-light \
        dispatch-doctor

PYTEST_ARGS ?= --durations=50
IMPACT_RANGE ?= origin/main...HEAD
# Optional test-profile CI-latency knobs — empty by default (adopter suites are
# small enough to run serially with no extra deps). To parallelize, install
# pytest-xdist and set PYTEST_XDIST="-n auto --dist loadscope"; to shard across
# CI runners, install pytest-split and set PYTEST_SPLIT="--splits N --group K".
# To balance shards by MEASURED test duration instead of test count (W152-2),
# commit a pytest-split durations file and set
# PYTEST_DURATIONS="--durations-path .test_durations".
PYTEST_XDIST ?=
PYTEST_SPLIT ?=
PYTEST_DURATIONS ?=

help:        ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-30s %s\n", $$1, $$2}'

install:     ## Install dev deps via uv
	uv sync --all-extras --dev

test:        ## Backward-compatible alias for test-pr-full
	$(MAKE) test-pr-full

test-push:   ## Push profile: non-mutating substrate consistency checks
	uv run dfg preflight push

test-impact-pr-full: ## Impact authority: fail if changed surfaces require stronger than PR-full
	uv run dfg test impact-plan --changed "$(IMPACT_RANGE)" --assert-profile pr-full --explain

test-pr-fast: ## PR-fast profile: offline-clean tests (skip network/socket/heavyweight/latency)
	uv run pytest -q $(PYTEST_ARGS) $(PYTEST_XDIST) $(PYTEST_SPLIT) $(PYTEST_DURATIONS) -m "not network and not socket and not heavyweight and not latency"

test-pr-full: ## PR/release confidence excluding heavyweight nightly-only tests, parallelized + shardable
	uv run pytest -q $(PYTEST_ARGS) $(PYTEST_XDIST) $(PYTEST_SPLIT) $(PYTEST_DURATIONS) -m "not heavyweight"

test-release: ## Release profile: full pytest plus external adoption smoke
	$(MAKE) test-pr-full
	uv run dfg adoption-smoke --source-root .

test-nightly: ## Nightly profile: exhaustive full pytest authority, including heavyweight (parallelized + shardable)
	uv run pytest -q $(PYTEST_ARGS) $(PYTEST_XDIST) $(PYTEST_SPLIT) $(PYTEST_DURATIONS)

test-fast:  ## Backward-compatible alias for test-pr-fast
	$(MAKE) test-pr-fast

test-full:  ## Backward-compatible exhaustive alias for test-nightly
	$(MAKE) test-nightly

lint:        ## Lint + format-check
	uv run ruff check .
	uv run ruff format --check .

fmt:         ## Auto-format
	uv run ruff format .

fix:         ## Auto-fix lint + format issues (substrate-real discipline)
	@echo "==> Auto-fixing lint issues with ruff check --fix..."
	uv run ruff check --fix .
	@echo "==> Auto-formatting with ruff format..."
	uv run ruff format .
	@echo "==> Done. Re-run 'make lint' to verify."

build:       ## Build wheel
	uv build

clean:       ## Remove caches
	rm -rf .pytest_cache .ruff_cache .mypy_cache dist build *.egg-info

wave-close:       ## Full wave-gate close check (run before chore(W*): close wave gate PR)
	@bash scripts/wave-close-check.sh --full

wave-close-light: ## Lightweight wave-close check (runs as part of `make ci` — anti-drift lock)
	@bash scripts/wave-close-check.sh

ci: lint test-pr-full wave-close-light ## Run full CI locally (incl. wave-close anti-drift lock)

# BEGIN dfg-harness v0.11.71
dispatch-doctor:                   ## dfg-harness: environment health check
	uv run dfg doctor
# END dfg-harness
