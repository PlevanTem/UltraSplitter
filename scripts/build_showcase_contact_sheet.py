#!/usr/bin/env python3
"""Render a compact README showcase from an UltraSplitter manifest."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = [
        "C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in names:
        if Path(name).is_file():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def background_color(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    points = [
        rgb.getpixel((0, 0)),
        rgb.getpixel((rgb.width - 1, 0)),
        rgb.getpixel((0, rgb.height - 1)),
        rgb.getpixel((rgb.width - 1, rgb.height - 1)),
    ]
    return tuple(int(median(point[channel] for point in points)) for channel in range(3))


def isolated_subject(path: Path, tolerance: int = 18) -> Image.Image:
    with Image.open(path) as opened:
        rgba = opened.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] >= 250:
        rgb = rgba.convert("RGB")
        flat = Image.new("RGB", rgb.size, background_color(rgb))
        difference = ImageChops.difference(rgb, flat)
        red, green, blue = difference.split()
        mask = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        mask = mask.point(lambda value: 255 if value > tolerance else 0)
        mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.6))
        rgba.putalpha(mask)
        alpha = mask
    bbox = alpha.getbbox()
    if bbox is None:
        return rgba
    padding = max(2, round(max(rgba.size) * 0.008))
    return rgba.crop(
        (
            max(0, bbox[0] - padding),
            max(0, bbox[1] - padding),
            min(rgba.width, bbox[2] + padding),
            min(rgba.height, bbox[3] + padding),
        )
    )


def load_items(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    deliverable_paths = set(manifest.get("delivery", {}).get("images", []))
    items = [item for item in manifest.get("items", []) if item.get("image_path") in deliverable_paths]
    if not items:
        raise SystemExit(f"manifest has no deliverable images: {manifest_path}")
    return items


def render(manifest_path: Path, output_path: Path, width: int, height: int) -> None:
    items = load_items(manifest_path)
    columns = min(4, max(1, math.ceil(math.sqrt(len(items)))))
    rows = math.ceil(len(items) / columns)
    outer, gap = 34, 18
    cell_width = (width - outer * 2 - gap * (columns - 1)) // columns
    cell_height = (height - outer * 2 - gap * (rows - 1)) // rows
    canvas = Image.new("RGB", (width, height), "#eef2f7")
    draw = ImageDraw.Draw(canvas)
    label_font = font(max(16, round(width / 85)), bold=True)

    for index, item in enumerate(items):
        row, column = divmod(index, columns)
        left = outer + column * (cell_width + gap)
        top = outer + row * (cell_height + gap)
        right, bottom = left + cell_width, top + cell_height
        draw.rounded_rectangle((left + 3, top + 5, right + 3, bottom + 5), radius=18, fill="#d9e0e9")
        draw.rounded_rectangle((left, top, right, bottom), radius=18, fill="white", outline="#d8dee8", width=2)

        label = str(item.get("label") or item.get("id") or f"asset-{index + 1:02d}")
        label_y = top + 15
        draw.text((left + 18, label_y), label, fill="#1d2735", font=label_font)
        divider_y = top + 48
        draw.line((left + 16, divider_y, right - 16, divider_y), fill="#edf0f4", width=2)

        subject = isolated_subject(Path(item["image_path"]))
        target_width = max(1, round(cell_width * 0.78))
        target_height = max(1, round((cell_height - 62) * 0.82))
        subject.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
        x = left + (cell_width - subject.width) // 2
        y = divider_y + 8 + (bottom - divider_y - 16 - subject.height) // 2
        canvas.paste(subject, (x, y), subject)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)


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
    render(args.manifest, args.output, args.width, args.height)
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
