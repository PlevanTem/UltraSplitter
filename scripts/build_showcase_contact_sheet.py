#!/usr/bin/env python3
"""Render a compact README showcase with the production contact-sheet renderer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ultrasplitter.presentation import render_contact_sheet  # noqa: E402


def load_items(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    deliverable_paths = set(manifest.get("delivery", {}).get("images", []))
    items = [item for item in manifest.get("items", []) if item.get("image_path") in deliverable_paths]
    if not items:
        raise SystemExit(f"manifest has no deliverable images: {manifest_path}")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--preview-width", type=int, default=960)
    parser.add_argument("--preview-height", type=int, default=600)
    args = parser.parse_args()
    if min(args.width, args.height, args.preview_width, args.preview_height) < 320:
        raise SystemExit("showcase dimensions must be at least 320 pixels")
    render_contact_sheet(
        load_items(args.manifest),
        args.output,
        canvas_size=(args.width, args.height),
    )
    if args.preview:
        with Image.open(args.output) as opened:
            preview = ImageOps.fit(
                opened.convert("RGB"),
                (args.preview_width, args.preview_height),
                method=Image.Resampling.LANCZOS,
            )
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        preview.save(args.preview, format="PNG", optimize=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
