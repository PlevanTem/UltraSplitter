"""Source-faithful pixel extraction and simple-mask recomposition."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from PIL import Image

from .core import estimate_background, foreground_mask, load_image


def _component_pixels(mask: Image.Image) -> list[dict[str, Any]]:
    width, height = mask.size
    values = mask.tobytes()
    visited = bytearray(width * height)
    neighbors = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))
    components: list[dict[str, Any]] = []
    for start, value in enumerate(values):
        if not value or visited[start]:
            continue
        visited[start] = 1
        queue: deque[int] = deque([start])
        pixels: list[int] = []
        min_x = max_x = start % width
        min_y = max_y = start // width
        while queue:
            current = queue.popleft()
            pixels.append(current)
            x, y = current % width, current // width
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
            for dx, dy in neighbors:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    neighbor = ny * width + nx
                    if values[neighbor] and not visited[neighbor]:
                        visited[neighbor] = 1
                        queue.append(neighbor)
        components.append(
            {"bbox": [min_x, min_y, max_x + 1, max_y + 1], "pixels": pixels, "area": len(pixels)}
        )
    return components


def _iou(first: list[int], second: list[int]) -> float:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0, right - left) * max(0, bottom - top)
    if not intersection:
        return 0.0
    area_first = (first[2] - first[0]) * (first[3] - first[1])
    area_second = (second[2] - second[0]) * (second[3] - second[1])
    return intersection / max(1, area_first + area_second - intersection)


def compose_source_item(
    source_path: Path,
    item: dict[str, Any],
    region_boxes: list[list[int]],
    background_rgba: list[int],
    tolerance: int,
    output_path: Path,
    alpha_path: Path,
) -> dict[str, float]:
    """Isolate selected connected components and center original pixels on a clean square canvas."""
    image = load_image(source_path)
    left, top, right, bottom = item["bbox"]
    crop = image.crop((left, top, right, bottom))
    background = tuple(background_rgba)
    mask = foreground_mask(crop, background, tolerance)
    components = _component_pixels(mask)
    relative_targets = [
        [box[0] - left, box[1] - top, box[2] - left, box[3] - top] for box in region_boxes
    ]
    selected: set[int] = set()
    for target in relative_targets:
        if components:
            best = max(range(len(components)), key=lambda index: _iou(components[index]["bbox"], target))
            if _iou(components[best]["bbox"], target) > 0:
                selected.add(best)
    if not selected:
        raise ValueError(f"could not isolate components for {item.get('id')}")

    target_mask = Image.new("L", crop.size, 0)
    target_pixels = target_mask.load()
    for index in selected:
        for offset in components[index]["pixels"]:
            target_pixels[offset % crop.width, offset // crop.width] = 255
    foreground_total = sum(component["area"] for component in components)
    target_total = sum(components[index]["area"] for index in selected)
    contamination = max(0, foreground_total - target_total) / max(1, foreground_total)

    alpha_crop = crop.copy()
    alpha_crop.putalpha(target_mask)
    content_box = target_mask.getbbox()
    if content_box is None:
        raise ValueError(f"empty isolated mask for {item.get('id')}")
    cutout = alpha_crop.crop(content_box)
    side = max(64, round(max(cutout.size) / 0.8))
    canvas = Image.new("RGBA", (side, side), tuple(background_rgba))
    alpha_canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    x = (side - cutout.width) // 2
    y = (side - cutout.height) // 2
    canvas.alpha_composite(cutout, (x, y))
    alpha_canvas.alpha_composite(cutout, (x, y))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    alpha_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, format="PNG", optimize=True)
    alpha_canvas.save(alpha_path, format="PNG", optimize=True)
    return {
        "source_foreign_foreground_ratio_removed": round(contamination, 6),
        "output_foreign_foreground_ratio": 0.0,
        "safe_margin_ratio": round(min(x, y) / side, 6),
    }
