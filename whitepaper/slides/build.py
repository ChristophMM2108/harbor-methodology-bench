#!/usr/bin/env python3
"""Inline every {{IMG:name}} placeholder in slides.src.html as a WebP data URI.

The whitepaper's figures are print-resolution PNGs; embedding them raw would be
several megabytes. Each is downscaled to a slide-sized raster and re-encoded as
WebP, which keeps the deck a single self-contained file that the Artifact
runtime can serve without external asset requests.

    cd whitepaper/slides && ../../.venv/bin/python build.py
"""
from __future__ import annotations

import base64
import io
import re
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
PAPER = HERE.parent
SEARCH = [PAPER / "figures", PAPER / "diagrams"]
MAX_WIDTH = 1500
QUALITY = 88

PLACEHOLDER = re.compile(r"\{\{IMG:([A-Za-z0-9._-]+)\}\}")


def locate(name: str) -> Path:
    for directory in SEARCH:
        candidate = directory / f"{name}.png"
        if candidate.exists():
            return candidate
    raise SystemExit(f"build.py: no figure or diagram named {name}.png")


def encode(path: Path) -> str:
    image = Image.open(path).convert("RGB")
    width, height = image.size
    if width > MAX_WIDTH:
        scale = MAX_WIDTH / width
        image = image.resize((MAX_WIDTH, round(height * scale)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=QUALITY, method=6)
    return "data:image/webp;base64," + base64.b64encode(buffer.getvalue()).decode()


def main() -> int:
    source = HERE / "slides.src.html"
    target = HERE / "slides.html"
    html = source.read_text(encoding="utf-8")

    cache: dict[str, str] = {}
    used: list[tuple[str, int]] = []

    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in cache:
            uri = encode(locate(name))
            cache[name] = uri
            used.append((name, len(uri)))
        return cache[name]

    html = PLACEHOLDER.sub(substitute, html)
    target.write_text(html, encoding="utf-8")

    for name, size in used:
        print(f"  {name:32s} {size / 1024:7.0f} KB")
    print(f"wrote {target.relative_to(PAPER.parent)}  ({len(html) / 1024 / 1024:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
