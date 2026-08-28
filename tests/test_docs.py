"""Guards on the documentation set.

The README is a navigation bar into `docs/`. A broken link there is the first
thing a new colleague hits, and nothing else in the suite would catch it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = sorted((REPO_ROOT / "docs").glob("*.md"))
PAGES = [REPO_ROOT / "README.md", *DOCS]


def github_anchor(heading: str) -> str:
    """GitHub's slug: lower-case, punctuation dropped, one hyphen per space."""
    text = re.sub(r"[^\w\s-]", "", heading.strip().lower())
    return re.sub(r"\s", "-", text)


def headings(path: Path) -> set[str]:
    return {github_anchor(h) for h in re.findall(r"^#{1,6}\s+(.*)$", path.read_text(), re.M)}


ANCHORS = {path.name: headings(path) for path in PAGES}


def links(path: Path) -> list[str]:
    return [
        target
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text())
        if not target.startswith(("http", "mailto:"))
    ]


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_internal_links_resolve(page: Path) -> None:
    for target in links(page):
        path, _, fragment = target.partition("#")
        resolved = (page.parent / path).resolve() if path else page.resolve()
        assert resolved.exists(), f"{page.name}: {target} points at nothing"
        if fragment and resolved.name in ANCHORS:
            assert fragment in ANCHORS[resolved.name], f"{page.name}: {target} has no such heading"


def test_readme_links_every_document() -> None:
    """A document nobody links to is a document nobody reads."""
    readme = (REPO_ROOT / "README.md").read_text()
    for doc in DOCS:
        assert f"docs/{doc.name}" in readme, f"README does not link docs/{doc.name}"


@pytest.mark.parametrize("page", DOCS, ids=lambda p: p.name)
def test_each_document_links_back(page: Path) -> None:
    """Every page carries the navigation bar, so no page is a dead end."""
    if page.name == "evaluation-pipeline.md":
        pytest.skip("standalone document, mirrored as HTML")
    assert "../README.md" in page.read_text(), f"{page.name} has no link back to the README"


def test_no_document_references_a_removed_wrapper_script() -> None:
    """The thin wrapper scripts were replaced by `hmb` subcommands.

    A command line in the documentation that no longer exists costs a reader more
    than a missing paragraph.
    """
    removed = (
        "scripts/catalogue.sh",
        "scripts/generate-variants.sh",
        "scripts/validate-variants.sh",
        "scripts/preflight-variants.sh",
        "scripts/freeze-kits.sh",
        "scripts/run-smoke-plan.sh",
    )
    for page in PAGES:
        text = page.read_text()
        for name in removed:
            assert name not in text, f"{page.name} still references {name}"
