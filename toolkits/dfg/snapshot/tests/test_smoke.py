"""Smoke tests — verify the package imports and exposes its version.

Per dfg-harness #15: a freshly-bootstrapped project must have at least one
real test so that `pytest` does not exit 5 (no-tests-collected) and break
`make ci` from the very first commit.
"""

import importlib


def test_import() -> None:
    """The harness_perf package is importable."""
    importlib.import_module("harness_perf")


def test_version() -> None:
    """The harness_perf package exposes a non-empty __version__."""
    pkg = importlib.import_module("harness_perf")
    assert hasattr(pkg, "__version__"), "harness_perf must expose __version__"
    assert isinstance(pkg.__version__, str)
    assert len(pkg.__version__) > 0
