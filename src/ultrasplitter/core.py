#!/usr/bin/env python3
"""Content-aware P0/P1 image splitter for multimodal coding agents.

The script deliberately separates pixel work from semantic decisions:

* ``scan`` finds exact panel interiors or simple-background components.
* a multimodal agent chooses candidate ids and writes a small plan JSON.
* ``apply`` resolves that plan against the original image and exports pixels.
* ``run`` provides a deterministic best-effort path when no agent plan is used.

It does not perform semantic instance segmentation or invent missing pixels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


SCHEMA_VERSION = 3
SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class SplitError(Exception):
    """Expected input, plan, or output error."""


@dataclass(frozen=True)
class Band:
    start: int
    end: int
    strength: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "strength": round(self.strength, 4),
        }


def json_dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_output_dir(input_path: Path, run_name: str | None = None) -> Path:
    label = safe_label(run_name or input_path.stem, "image-split")
    return Path.cwd() / "output" / f"{label}-{file_sha256(input_path)[:8]}"


def unique_output_dir(preferred: Path) -> Path:
    if not preferred.exists():
        return preferred
    for suffix in range(2, 1000):
        candidate = preferred.with_name(f"{preferred.name}-{suffix:02d}")
        if not candidate.exists():
            return candidate
    raise SplitError(f"cannot allocate a unique output directory near: {preferred}")


def load_image(path: Path) -> Image.Image:
    if not path.is_file():
        raise SplitError(f"input does not exist: {path}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise SplitError("input must be PNG, JPEG, or WebP")
    try:
        with Image.open(path) as opened:
            return ImageOps.exif_transpose(opened).convert("RGBA")
    except Exception as exc:  # Pillow exposes format-specific exceptions.
        raise SplitError(f"cannot decode input: {exc}") from exc


def ensure_writable(paths: Iterable[Path], overwrite: bool) -> None:
    collisions = [path for path in paths if path.exists()]
    if collisions and not overwrite:
        joined = "\n  ".join(str(path) for path in collisions)
        raise SplitError(f"outputs already exist; pass --overwrite:\n  {joined}")


def scaled_copy(image: Image.Image, max_size: int) -> tuple[Image.Image, float, float]:
    if max(image.size) <= max_size:
        return image.copy(), 1.0, 1.0
    ratio = max_size / max(image.size)
    width = max(1, round(image.width * ratio))
    height = max(1, round(image.height * ratio))
    resized = image.resize((width, height), Image.Resampling.BILINEAR)
    return resized, image.width / width, image.height / height


def group_positions(
    positions: list[int], strengths: list[float], scale: float, max_thickness: int
) -> list[Band]:
    if not positions:
        return []
    groups: list[list[int]] = [[positions[0]]]
    for position in positions[1:]:
        if position <= groups[-1][-1] + 2:
            groups[-1].append(position)
        else:
            groups.append([position])

    bands: list[Band] = []
    strength_by_position = dict(zip(positions, strengths))
    for group in groups:
        start = math.floor(group[0] * scale)
        end = math.ceil((group[-1] + 1) * scale)
        if end - start > max_thickness:
            continue
        strength = sum(strength_by_position[position] for position in group) / len(group)
        bands.append(Band(start, end, strength))
    return bands


def detect_axis_bands(
    image: Image.Image,
    axis: str,
    max_scan_size: int,
    dark_threshold: int = 145,
    continuity: float = 0.56,
) -> list[Band]:
    sampled, scale_x, scale_y = scaled_copy(image, max_scan_size)
    gray = sampled.convert("L")
    pixels = gray.load()
    positions: list[int] = []
    strengths: list[float] = []

    if axis == "x":
        for x in range(gray.width):
            fraction = sum(1 for y in range(gray.height) if pixels[x, y] <= dark_threshold) / gray.height
            if fraction >= continuity:
                positions.append(x)
                strengths.append(fraction)
        scale = scale_x
        max_thickness = max(6, round(image.width * 0.012))
    else:
        for y in range(gray.height):
            fraction = sum(1 for x in range(gray.width) if pixels[x, y] <= dark_threshold) / gray.width
            if fraction >= continuity:
                positions.append(y)
                strengths.append(fraction)
        scale = scale_y
        max_thickness = max(6, round(image.height * 0.012))

    return group_positions(positions, strengths, scale, max_thickness)


def intervals_between_bands(bands: list[Band], size: int, min_fraction: float) -> list[tuple[int, int]]:
    minimum = max(12, round(size * min_fraction))
    intervals: list[tuple[int, int]] = []
    for left, right in zip(bands, bands[1:]):
        if right.start - left.end >= minimum:
            intervals.append((left.end, right.start))
    return intervals


def panel_candidate(image: Image.Image, max_scan_size: int) -> dict[str, Any] | None:
    vertical = detect_axis_bands(image, "x", max_scan_size)
    horizontal = detect_axis_bands(image, "y", max_scan_size)
    if vertical:
        strongest = max(band.strength for band in vertical)
        vertical = [band for band in vertical if band.strength >= max(0.62, strongest * 0.82)]
    if horizontal:
        strongest = max(band.strength for band in horizontal)
        horizontal = [band for band in horizontal if band.strength >= max(0.62, strongest * 0.82)]
    # Long dark runs inside a person or prop can resemble a vertical divider in
    # projection space. Real frame edges intersect the detected top/bottom frame
    # bands; filter on those intersections before constructing panel interiors.
    if len(horizontal) >= 2:
        gray = image.convert("L")
        pixels = gray.load()
        filtered_vertical: list[Band] = []
        for band in vertical:
            x = min(image.width - 1, max(0, (band.start + band.end - 1) // 2))
            intersections = []
            for horizontal_band in horizontal:
                lo = max(0, horizontal_band.start)
                hi = min(image.height, horizontal_band.end)
                intersections.append(any(pixels[x, y] <= 180 for y in range(lo, hi)))
            if sum(intersections) / len(intersections) >= 0.75:
                filtered_vertical.append(band)
        vertical = filtered_vertical
    x_intervals = intervals_between_bands(vertical, image.width, 0.075)
    y_intervals = intervals_between_bands(horizontal, image.height, 0.075)
    if not x_intervals or not y_intervals:
        return None

    boxes = [
        (left, top, right, bottom)
        for top, bottom in y_intervals
        for left, right in x_intervals
        if right > left and bottom > top
    ]
    if not 2 <= len(boxes) <= 36:
        return None

    strengths = [band.strength for band in vertical + horizontal]
    score = min(0.99, 0.55 + 0.45 * (sum(strengths) / max(1, len(strengths))))
    regions = [
        {
            "id": f"panel-{index:03d}",
            "bbox": list(box),
            "flags": [],
        }
        for index, box in enumerate(boxes, 1)
    ]
    return {
        "id": "panels-frame-001",
        "kind": "panels",
        "score": round(score, 4),
        "regions": regions,
        "evidence": {
            "vertical_bands": [band.as_dict() for band in vertical],
            "horizontal_bands": [band.as_dict() for band in horizontal],
            "rows": len(y_intervals),
            "columns": len(x_intervals),
        },
    }


def parse_layout(value: str | None) -> tuple[int, int] | None:
    if value is None:
        return None
    match = re.fullmatch(r"\s*(\d+)\s*[xX×]\s*(\d+)\s*", value)
    if not match:
        raise SplitError("--layout must look like 1x4 or 2x2")
    rows, columns = int(match.group(1)), int(match.group(2))
    if rows < 1 or columns < 1 or rows * columns > 64:
        raise SplitError("--layout must contain 1 to 64 panels")
    return rows, columns


def projection_score(gray: Image.Image, axis: str, position: int) -> float:
    if axis == "x":
        values = [gray.getpixel((position, y)) for y in range(gray.height)]
    else:
        values = [gray.getpixel((x, position)) for x in range(gray.width)]
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def snap_layout_candidate(image: Image.Image, layout: tuple[int, int]) -> dict[str, Any]:
    rows, columns = layout
    gray = image.convert("L")
    x_cuts: list[int] = []
    y_cuts: list[int] = []
    for boundary in range(1, columns):
        expected = round(image.width * boundary / columns)
        radius = max(3, round(image.width / columns * 0.05))
        lo, hi = max(1, expected - radius), min(image.width - 2, expected + radius)
        x_cuts.append(min(range(lo, hi + 1), key=lambda x: projection_score(gray, "x", x)))
    for boundary in range(1, rows):
        expected = round(image.height * boundary / rows)
        radius = max(3, round(image.height / rows * 0.05))
        lo, hi = max(1, expected - radius), min(image.height - 2, expected + radius)
        y_cuts.append(min(range(lo, hi + 1), key=lambda y: projection_score(gray, "y", y)))

    x_bounds = [0] + x_cuts + [image.width]
    y_bounds = [0] + y_cuts + [image.height]
    regions = []
    index = 1
    for row in range(rows):
        for column in range(columns):
            regions.append(
                {
                    "id": f"grid-{index:03d}",
                    "bbox": [x_bounds[column], y_bounds[row], x_bounds[column + 1], y_bounds[row + 1]],
                    "flags": ["nominal_layout_requires_visual_review"],
                }
            )
            index += 1
    return {
        "id": "panels-layout-001",
        "kind": "panels",
        "score": 0.55,
        "regions": regions,
        "evidence": {"rows": rows, "columns": columns, "x_cuts": x_cuts, "y_cuts": y_cuts},
    }


def border_samples(image: Image.Image) -> list[tuple[int, int, int, int]]:
    rgba = image.convert("RGBA")
    step = max(1, min(rgba.width, rgba.height) // 160)
    samples: list[tuple[int, int, int, int]] = []
    for x in range(0, rgba.width, step):
        samples.append(rgba.getpixel((x, 0)))
        samples.append(rgba.getpixel((x, rgba.height - 1)))
    for y in range(0, rgba.height, step):
        samples.append(rgba.getpixel((0, y)))
        samples.append(rgba.getpixel((rgba.width - 1, y)))
    return samples


def estimate_background(image: Image.Image, tolerance: int) -> tuple[tuple[int, int, int, int], float]:
    samples = border_samples(image)
    background = tuple(int(median(pixel[channel] for pixel in samples)) for channel in range(4))
    if background[3] <= 16:
        uniformity = sum(pixel[3] <= 16 for pixel in samples) / max(1, len(samples))
    else:
        distances = [
            math.sqrt(sum((pixel[channel] - background[channel]) ** 2 for channel in range(3)))
            for pixel in samples
        ]
        uniformity = sum(distance <= tolerance for distance in distances) / max(1, len(distances))
    return background, uniformity


def foreground_mask(
    image: Image.Image,
    background: tuple[int, int, int, int],
    tolerance: int,
) -> Image.Image:
    rgba = image.convert("RGBA")
    source = rgba.load()
    mask = Image.new("L", rgba.size, 0)
    target = mask.load()
    transparent_background = background[3] <= 16
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = source[x, y]
            if transparent_background:
                foreground = a > 16
            else:
                distance = math.sqrt(
                    (r - background[0]) ** 2
                    + (g - background[1]) ** 2
                    + (b - background[2]) ** 2
                )
                foreground = a > 16 and distance >= tolerance
            if foreground:
                target[x, y] = 255
    # Close one-pixel gaps without attempting semantic separation.
    return mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))


def connected_components(mask: Image.Image, min_pixels: int) -> list[dict[str, int]]:
    width, height = mask.size
    values = mask.tobytes()
    visited = bytearray(width * height)
    components: list[dict[str, int]] = []
    neighbors = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))

    for index, value in enumerate(values):
        if value == 0 or visited[index]:
            continue
        visited[index] = 1
        queue: deque[int] = deque([index])
        min_x = max_x = index % width
        min_y = max_y = index // width
        area = 0
        while queue:
            current = queue.popleft()
            x, y = current % width, current // width
            area += 1
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
            for dx, dy in neighbors:
                nx, ny = x + dx, y + dy
                if nx < 0 or nx >= width or ny < 0 or ny >= height:
                    continue
                neighbor = ny * width + nx
                if values[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    queue.append(neighbor)
        if area >= min_pixels:
            components.append(
                {"left": min_x, "top": min_y, "right": max_x + 1, "bottom": max_y + 1, "area": area}
            )
    return components


def object_candidate(
    image: Image.Image,
    tolerance: int,
    min_area_ratio: float,
    max_scan_size: int,
) -> dict[str, Any] | None:
    sampled, scale_x, scale_y = scaled_copy(image, max_scan_size)
    background, uniformity = estimate_background(sampled, tolerance)
    mask = foreground_mask(sampled, background, tolerance)
    minimum = max(4, round(sampled.width * sampled.height * min_area_ratio))
    components = connected_components(mask, minimum)
    if not components:
        return None

    components.sort(key=lambda item: (item["top"], item["left"], -item["area"]))
    regions: list[dict[str, Any]] = []
    for index, component in enumerate(components[:250], 1):
        left = max(0, math.floor(component["left"] * scale_x))
        top = max(0, math.floor(component["top"] * scale_y))
        right = min(image.width, math.ceil(component["right"] * scale_x))
        bottom = min(image.height, math.ceil(component["bottom"] * scale_y))
        flags: list[str] = []
        if left == 0 or top == 0 or right == image.width or bottom == image.height:
            flags.append("source_clipped")
        regions.append(
            {
                "id": f"cc-{index:03d}",
                "bbox": [left, top, right, bottom],
                "foreground_pixels_at_scan_scale": component["area"],
                "flags": flags,
            }
        )

    largest = max(
        ((region["bbox"][2] - region["bbox"][0]) * (region["bbox"][3] - region["bbox"][1]))
        for region in regions
    )
    largest_fraction = largest / (image.width * image.height)
    score = uniformity * (0.45 if largest_fraction > 0.82 else 1.0)
    return {
        "id": "objects-components-001",
        "kind": "objects",
        "score": round(min(0.99, score), 4),
        "regions": regions,
        "evidence": {
            "background_rgba": list(background),
            "background_uniformity": round(uniformity, 4),
            "background_tolerance": tolerance,
            "component_count": len(regions),
            "minimum_scan_area": minimum,
            "scan_size": list(sampled.size),
        },
    }


def color_for_index(index: int) -> tuple[int, int, int, int]:
    colors = [
        (230, 40, 40, 255),
        (30, 120, 240, 255),
        (0, 170, 90, 255),
        (220, 120, 0, 255),
        (150, 60, 210, 255),
    ]
    return colors[index % len(colors)]


def readable_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=max(10, size))
    except OSError:
        return ImageFont.load_default()


def draw_candidate_preview(image: Image.Image, candidate: dict[str, Any], output: Path) -> None:
    preview = image.copy()
    draw = ImageDraw.Draw(preview, "RGBA")
    font = readable_font(round(max(image.size) / 170))
    width = max(2, round(max(image.size) / 700))
    for index, region in enumerate(candidate["regions"]):
        left, top, right, bottom = region["bbox"]
        color = color_for_index(index)
        draw.rectangle((left, top, right - 1, bottom - 1), outline=color, width=width)
        label = region["id"]
        label_box = draw.textbbox((left + width, top + width), label, font=font)
        draw.rectangle(label_box, fill=(255, 255, 255, 220))
        draw.text((left + width, top + width), label, fill=color, font=font)
    preview.save(output, format="PNG", optimize=True)


def scan_image(
    input_path: Path,
    output_dir: Path,
    mode: str,
    layout: tuple[int, int] | None,
    tolerance: int,
    min_area_ratio: float,
    max_scan_size: int,
    overwrite: bool,
) -> dict[str, Any]:
    image = load_image(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    scan_path = output_dir / "scan.json"
    ensure_writable([scan_path], overwrite)

    candidates: list[dict[str, Any]] = []
    if mode in ("auto", "panels"):
        framed = panel_candidate(image, max_scan_size)
        if framed:
            candidates.append(framed)
        if layout:
            candidates.append(snap_layout_candidate(image, layout))
    if mode in ("auto", "objects"):
        objects = object_candidate(image, tolerance, min_area_ratio, max_scan_size)
        if objects:
            candidates.append(objects)
    if not candidates:
        raise SplitError("no usable panel or simple-background candidates were found")

    for candidate in candidates:
        preview_path = output_dir / f"{candidate['id']}-preview.png"
        ensure_writable([preview_path], overwrite)
        draw_candidate_preview(image, candidate, preview_path)
        candidate["preview"] = str(preview_path.resolve())

    panel_options = [candidate for candidate in candidates if candidate["kind"] == "panels"]
    object_options = [candidate for candidate in candidates if candidate["kind"] == "objects"]
    if panel_options and max(candidate["score"] for candidate in panel_options) >= 0.8:
        recommended = max(panel_options, key=lambda candidate: candidate["score"])
    elif object_options:
        recommended = max(object_options, key=lambda candidate: candidate["score"])
    else:
        recommended = max(candidates, key=lambda candidate: candidate["score"])

    scan = {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "source": {
            "path": str(input_path.resolve()),
            "width": image.width,
            "height": image.height,
            "sha256": file_sha256(input_path),
        },
        "requested_mode": mode,
        "recommended_candidate_set": recommended["id"],
        "candidate_sets": candidates,
        "agent_instruction": (
            "Inspect the candidate previews. Select one candidate_set and group its region ids in a plan. "
            "Do not copy preview pixel coordinates back into the plan."
        ),
    }
    json_dump(scan_path, scan)
    return {"scan": scan, "scan_path": scan_path}


def find_candidate(scan: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    for candidate in scan.get("candidate_sets", []):
        if candidate.get("id") == candidate_id:
            return candidate
    raise SplitError(f"candidate_set not found in scan: {candidate_id}")


def auto_plan(scan: dict[str, Any]) -> dict[str, Any]:
    candidate_id = scan["recommended_candidate_set"]
    candidate = find_candidate(scan, candidate_id)
    prefix = "panel" if candidate["kind"] == "panels" else "object"
    items = [
        {
            "id": f"item-{index:03d}",
            "label": f"{prefix}-{index:03d}",
            "regions": [region["id"]],
        }
        for index, region in enumerate(candidate["regions"], 1)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": candidate["kind"],
        "candidate_set": candidate_id,
        "items": items,
        "padding": 0.0 if candidate["kind"] == "panels" else 0.03,
        "emit": "auto",
        "expected_count": len(items),
        "created_by": "deterministic-auto-plan",
    }


def safe_label(value: str, fallback: str) -> str:
    label = re.sub(r"[^\w.-]+", "-", value.strip(), flags=re.UNICODE).strip("-.")
    return label or fallback


def union_boxes(boxes: list[list[int]], width: int, height: int, padding: float) -> list[int]:
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[2] for box in boxes)
    bottom = max(box[3] for box in boxes)
    pad_x = round((right - left) * padding)
    pad_y = round((bottom - top) * padding)
    return [max(0, left - pad_x), max(0, top - pad_y), min(width, right + pad_x), min(height, bottom + pad_y)]


def alpha_outputs(
    crop: Image.Image,
    background: tuple[int, int, int, int],
    tolerance: int,
) -> tuple[Image.Image, Image.Image]:
    rgba = crop.convert("RGBA")
    source = rgba.load()
    mask = Image.new("L", rgba.size, 0)
    mask_pixels = mask.load()
    transparent_background = background[3] <= 16
    low, high = tolerance * 0.65, max(tolerance * 1.5, tolerance + 1)
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, source_alpha = source[x, y]
            if transparent_background:
                alpha = source_alpha
            else:
                distance = math.sqrt(
                    (r - background[0]) ** 2
                    + (g - background[1]) ** 2
                    + (b - background[2]) ** 2
                )
                factor = max(0.0, min(1.0, (distance - low) / (high - low)))
                alpha = round(source_alpha * factor)
            mask_pixels[x, y] = alpha
            source[x, y] = (r, g, b, alpha)
    return rgba, mask


def edge_dark_fraction(image: Image.Image, side: str, threshold: int = 100) -> float:
    gray = image.convert("L")
    if side == "left":
        values = [gray.getpixel((0, y)) for y in range(gray.height)]
    elif side == "right":
        values = [gray.getpixel((gray.width - 1, y)) for y in range(gray.height)]
    elif side == "top":
        values = [gray.getpixel((x, 0)) for x in range(gray.width)]
    else:
        values = [gray.getpixel((x, gray.height - 1)) for x in range(gray.width)]
    return sum(value <= threshold for value in values) / max(1, len(values))


def make_contact_sheet(items: list[dict[str, Any]], output_path: Path) -> None:
    if not items:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas = Image.new("RGB", (600, 160), "#ececec")
        draw = ImageDraw.Draw(canvas)
        draw.text((24, 68), "No deliverable assets yet", fill="#555555", font=readable_font(18))
        canvas.save(output_path, format="PNG", optimize=True)
        return
    columns = min(4, len(items))
    rows = math.ceil(len(items) / columns)
    cell_width, cell_height, label_height = 300, 320, 24
    canvas = Image.new("RGB", (columns * cell_width, rows * cell_height), "#ececec")
    draw = ImageDraw.Draw(canvas)
    font = readable_font(15)
    for index, item in enumerate(items):
        with Image.open(item["image_path"]) as opened:
            thumbnail = opened.convert("RGBA")
            thumbnail.thumbnail((cell_width - 20, cell_height - label_height - 20), Image.Resampling.LANCZOS)
            x = index % columns * cell_width + (cell_width - thumbnail.width) // 2
            y = index // columns * cell_height + label_height + (cell_height - label_height - thumbnail.height) // 2
            tile = Image.new("RGBA", thumbnail.size, "white")
            tile.alpha_composite(thumbnail)
            canvas.paste(tile.convert("RGB"), (x, y))
        draw.text((index % columns * cell_width + 8, index // columns * cell_height + 6), item["label"], fill="black", font=font)
    canvas.save(output_path, format="PNG", optimize=True)


def apply_plan(
    input_path: Path,
    scan_path: Path,
    plan: dict[str, Any],
    output_dir: Path,
    overwrite: bool,
) -> dict[str, Any]:
    image = load_image(input_path)
    scan = json.loads(scan_path.read_text(encoding="utf-8"))
    if scan.get("schema_version") != SCHEMA_VERSION or plan.get("schema_version") != SCHEMA_VERSION:
        raise SplitError("unsupported scan or plan schema_version")
    if scan.get("source", {}).get("sha256") != file_sha256(input_path):
        raise SplitError("input bytes no longer match the scan manifest")

    candidate = find_candidate(scan, plan.get("candidate_set", ""))
    if plan.get("mode") != candidate.get("kind"):
        raise SplitError("plan mode does not match candidate_set kind")
    region_map = {region["id"]: region for region in candidate["regions"]}
    items_plan = plan.get("items")
    if not isinstance(items_plan, list) or not items_plan:
        raise SplitError("plan.items must be a non-empty array")
    expected = plan.get("expected_count")
    if expected is not None and expected != len(items_plan):
        raise SplitError("expected_count does not match plan.items length")
    padding = float(plan.get("padding", 0.0 if candidate["kind"] == "panels" else 0.03))
    if not 0 <= padding <= 1:
        raise SplitError("plan.padding must be between 0 and 1")
    emit = plan.get("emit", "auto")
    if emit not in {"auto", "crop", "rgba", "all"}:
        raise SplitError("plan.emit must be auto, crop, rgba, or all")

    excluded_regions = plan.get("exclude_regions", [])
    if not isinstance(excluded_regions, list) or any(not isinstance(value, str) for value in excluded_regions):
        raise SplitError("plan.exclude_regions must be an array of region ids")
    unknown_excluded = [region_id for region_id in excluded_regions if region_id not in region_map]
    if unknown_excluded:
        raise SplitError(f"plan excludes unknown regions: {', '.join(unknown_excluded)}")

    exclusions = plan.get("exclusions", [])
    if not isinstance(exclusions, list):
        raise SplitError("plan.exclusions must be an array")
    described_exclusions: set[str] = set()
    for index, exclusion in enumerate(exclusions, 1):
        if not isinstance(exclusion, dict):
            raise SplitError(f"exclusion {index} must be an object")
        region_ids = exclusion.get("regions")
        if not isinstance(region_ids, list) or not region_ids:
            raise SplitError(f"exclusion {index} must contain region ids")
        unknown = [region_id for region_id in region_ids if region_id not in region_map]
        if unknown:
            raise SplitError(f"exclusion {index} references unknown regions: {', '.join(unknown)}")
        not_excluded = [region_id for region_id in region_ids if region_id not in excluded_regions]
        if not_excluded:
            raise SplitError(
                f"exclusion {index} regions must also appear in exclude_regions: {', '.join(not_excluded)}"
            )
        duplicates = [region_id for region_id in region_ids if region_id in described_exclusions]
        if duplicates:
            raise SplitError(f"exclusion regions cannot be described twice: {', '.join(duplicates)}")
        described_exclusions.update(region_ids)
        action = exclusion.get("recommended_action", "ignore")
        if action != "ignore":
            raise SplitError(f"exclusion {index} recommended_action must be ignore")
        visible = exclusion.get("visible_fraction_estimate")
        if visible is not None and (not isinstance(visible, (int, float)) or not 0 <= visible <= 1):
            raise SplitError(f"exclusion {index} visible_fraction_estimate must be between 0 and 1")

    background_uniformity = float(candidate.get("evidence", {}).get("background_uniformity", 1.0))
    should_emit_alpha = emit in {"rgba", "all"} or (
        emit == "auto" and candidate["kind"] == "objects" and background_uniformity >= 0.8
    )

    labels: list[str] = []
    used_regions: set[str] = set()
    for index, item in enumerate(items_plan, 1):
        label = safe_label(str(item.get("label", "")), f"item-{index:03d}")
        if label in labels:
            raise SplitError(f"duplicate output label: {label}")
        labels.append(label)
        region_ids = item.get("regions")
        if not isinstance(region_ids, list) or not region_ids:
            raise SplitError(f"item {index} must contain region ids")
        unknown = [region_id for region_id in region_ids if region_id not in region_map]
        if unknown:
            raise SplitError(f"item {index} references unknown regions: {', '.join(unknown)}")
        duplicate = [region_id for region_id in region_ids if region_id in used_regions]
        if duplicate and not plan.get("allow_shared_regions_for_repair", False):
            raise SplitError(f"regions cannot appear in multiple items: {', '.join(duplicate)}")
        used_regions.update(region_ids)
        assessment = item.get("visual_assessment", {})
        if assessment is not None and not isinstance(assessment, dict):
            raise SplitError(f"item {index} visual_assessment must be an object")
        if isinstance(assessment, dict):
            action = assessment.get("recommended_action")
            if action not in {None, "deliver", "clean", "repair"}:
                raise SplitError(
                    f"item {index} recommended_action must be deliver, clean, or repair; "
                    "ignored subjects belong in exclusions"
                )
            severity = assessment.get("missing_severity")
            if severity not in {None, "none", "minor", "repairable", "severe"}:
                raise SplitError(
                    f"item {index} missing_severity must be none, minor, repairable, or severe"
                )
            if severity == "severe":
                raise SplitError(f"item {index} is severely incomplete and must be moved to exclusions")
            visible = assessment.get("visible_fraction_estimate")
            if visible is not None and (not isinstance(visible, (int, float)) or not 0 <= visible <= 1):
                raise SplitError(f"item {index} visible_fraction_estimate must be between 0 and 1")

    overlap_with_outputs = sorted(set(excluded_regions) & used_regions)
    if overlap_with_outputs:
        raise SplitError(f"excluded regions also appear in output items: {', '.join(overlap_with_outputs)}")
    if plan.get("allow_shared_regions_for_repair", False):
        for region_id in used_regions:
            owners = [item for item in items_plan if region_id in item.get("regions", [])]
            if len(owners) < 2:
                continue
            for owner in owners:
                assessment = owner.get("visual_assessment", {})
                repair_only = isinstance(assessment, dict) and (
                    assessment.get("complete") is False
                    or assessment.get("occluded") is True
                    or assessment.get("touching") is True
                    or int(assessment.get("semantic_subject_count", 1)) > 1
                )
                if not repair_only:
                    raise SplitError(
                        f"shared region {region_id} is allowed only for items explicitly assessed for repair"
                    )

    image_dir = output_dir / "images" / "source"
    alpha_dir = output_dir / "alpha"
    mask_dir = output_dir / "masks"
    review_dir = output_dir / "review"
    manifest_path = output_dir / "manifest.json"

    ordinal_width = max(2, len(str(len(items_plan))))
    planned_paths = [manifest_path, review_dir / "contact-sheet.png"]
    output_names: list[str] = []
    for index, label in enumerate(labels, 1):
        output_name = f"{index:0{ordinal_width}d}-{label}.png"
        output_names.append(output_name)
        planned_paths.append(image_dir / output_name)
        if should_emit_alpha:
            planned_paths.extend([alpha_dir / output_name, mask_dir / output_name])

    output_dir.mkdir(parents=True, exist_ok=True)
    image_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)
    if should_emit_alpha:
        alpha_dir.mkdir(parents=True, exist_ok=True)
        mask_dir.mkdir(parents=True, exist_ok=True)
    ensure_writable(planned_paths, overwrite)

    output_items: list[dict[str, Any]] = []
    global_warnings: list[str] = []
    background = tuple(candidate.get("evidence", {}).get("background_rgba", [255, 255, 255, 255]))
    tolerance = int(candidate.get("evidence", {}).get("background_tolerance", 30))

    for index, (item_plan, label, output_name) in enumerate(zip(items_plan, labels, output_names), 1):
        region_ids = item_plan.get("regions")
        assert isinstance(region_ids, list)
        regions = [region_map[region_id] for region_id in region_ids]
        bbox = union_boxes([region["bbox"] for region in regions], image.width, image.height, padding)
        left, top, right, bottom = bbox
        if left >= right or top >= bottom:
            raise SplitError(f"item {index} resolves to an empty crop")
        crop = image.crop((left, top, right, bottom))
        crop_path = image_dir / output_name
        crop.save(crop_path, format="PNG", optimize=True)

        warnings = sorted({flag for region in regions for flag in region.get("flags", [])})
        if candidate["kind"] == "panels":
            for side in ("left", "right", "top", "bottom"):
                if edge_dark_fraction(crop, side) >= 0.55:
                    warnings.append(f"possible_border_residue:{side}")
        elif background_uniformity < 0.8:
            warnings.append("alpha_unreliable:background_not_uniform")

        rgba_path = mask_path = None
        if should_emit_alpha:
            rgba, mask = alpha_outputs(crop, background, tolerance)
            rgba_path = alpha_dir / output_name
            mask_path = mask_dir / output_name
            rgba.save(rgba_path, format="PNG", optimize=True)
            mask.save(mask_path, format="PNG", optimize=True)

        global_warnings.extend(f"{label}:{warning}" for warning in warnings)
        output_items.append(
            {
                "id": str(item_plan.get("id", f"item-{index:03d}")),
                "label": label,
                "regions": region_ids,
                "bbox": bbox,
                "image_path": str(crop_path.resolve()),
                "rgba_path": str(rgba_path.resolve()) if rgba_path else None,
                "mask_path": str(mask_path.resolve()) if mask_path else None,
                "warnings": warnings,
            }
        )

    unused_regions = [
        region_id for region_id in region_map if region_id not in used_regions and region_id not in excluded_regions
    ]
    if unused_regions:
        global_warnings.append(f"unused_regions:{','.join(unused_regions)}")
    if candidate["score"] < 0.8:
        global_warnings.append("candidate_set_requires_visual_review")

    contact_path = review_dir / "contact-sheet.png"
    make_contact_sheet(output_items, contact_path)
    review_required = bool(global_warnings)
    delivery = {
        "output_dir": str(output_dir.resolve()),
        "images": [item["image_path"] for item in output_items],
        "alpha_images": [item["rgba_path"] for item in output_items if item["rgba_path"]],
        "masks": [item["mask_path"] for item in output_items if item["mask_path"]],
        "contact_sheet": str(contact_path.resolve()),
        "manifest": str(manifest_path.resolve()),
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "needs_review" if review_required else "success",
        "review_required": review_required,
        "source": scan["source"],
        "scan_path": str(scan_path.resolve()),
        "plan": plan,
        "candidate_score": candidate["score"],
        "actual_count": len(output_items),
        "contact_sheet": str(contact_path.resolve()),
        "delivery": delivery,
        "items": output_items,
        "excluded_regions": excluded_regions,
        "exclusions": [
            {
                **exclusion,
                "id": str(exclusion.get("id", f"excluded-{index:03d}")),
                "label": safe_label(str(exclusion.get("label", "")), f"excluded-{index:03d}"),
                "recommended_action": "ignore",
                "bbox": union_boxes(
                    [region_map[region_id]["bbox"] for region_id in exclusion["regions"]],
                    image.width,
                    image.height,
                    0.0,
                ),
            }
            for index, exclusion in enumerate(exclusions, 1)
        ],
        "warnings": global_warnings,
        "verifier_instruction": (
            "Compare the original image with review/contact-sheet.png. Check count, missing regions, subject cuts, "
            "divider residue, captions, duplicates, and grouping. Retry mechanical fixes at most twice."
        ),
    }
    json_dump(manifest_path, manifest)
    return {"manifest": manifest, "manifest_path": manifest_path}


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SplitError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SplitError(f"JSON root must be an object: {path}")
    return value


def add_scan_arguments(parser: argparse.ArgumentParser, *, output_required: bool = True) -> None:
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=output_required)
    if not output_required:
        parser.add_argument("--name", help="user-facing run directory name")
    parser.add_argument("--mode", choices=("auto", "panels", "objects"), default="auto")
    parser.add_argument("--layout", help="optional weak hint such as 1x4 or 2x2")
    parser.add_argument("--background-tolerance", type=int, default=32)
    parser.add_argument("--min-area", type=float, default=0.00015, help="minimum component area ratio")
    parser.add_argument("--max-scan-size", type=int, default=1400)
    parser.add_argument("--overwrite", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="generate pixel-precise candidates for agent review")
    add_scan_arguments(scan_parser)

    apply_parser = subparsers.add_parser("apply", help="apply an agent-selected plan to the source pixels")
    apply_parser.add_argument("input", type=Path)
    apply_parser.add_argument("--scan", type=Path, required=True)
    apply_parser.add_argument("--plan", type=Path, required=True)
    apply_parser.add_argument("--output-dir", type=Path, required=True)
    apply_parser.add_argument("--overwrite", action="store_true")

    run_parser = subparsers.add_parser("run", help="scan and apply the recommended deterministic candidate")
    add_scan_arguments(run_parser, output_required=False)

    inspect_parser = subparsers.add_parser("inspect", help="print a compact manifest verdict")
    inspect_parser.add_argument("manifest", type=Path)
    return parser


def validate_scan_args(args: argparse.Namespace) -> None:
    if not 1 <= args.background_tolerance <= 441:
        raise SplitError("--background-tolerance must be between 1 and 441")
    if not 0 < args.min_area < 0.25:
        raise SplitError("--min-area must be greater than 0 and less than 0.25")
    if args.max_scan_size < 128:
        raise SplitError("--max-scan-size must be at least 128")


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "scan":
            validate_scan_args(args)
            result = scan_image(
                args.input,
                args.output_dir,
                args.mode,
                parse_layout(args.layout),
                args.background_tolerance,
                args.min_area,
                args.max_scan_size,
                args.overwrite,
            )
            payload = {
                        "status": "success",
                "scan": str(result["scan_path"].resolve()),
                "recommended_candidate_set": result["scan"]["recommended_candidate_set"],
                "previews": [candidate["preview"] for candidate in result["scan"]["candidate_sets"]],
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        if args.command == "apply":
            result = apply_plan(
                args.input,
                args.scan,
                read_json(args.plan),
                args.output_dir,
                args.overwrite,
            )
            manifest = result["manifest"]
            print(
                json.dumps(
                    {
                        "status": manifest["status"],
                        "review_required": manifest["review_required"],
                        "count": manifest["actual_count"],
                        "delivery": manifest["delivery"],
                        "warnings": manifest["warnings"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2 if manifest["review_required"] else 0

        if args.command == "run":
            validate_scan_args(args)
            if args.output_dir is None:
                preferred = default_output_dir(args.input, args.name)
                output_dir = preferred if args.overwrite else unique_output_dir(preferred)
            else:
                output_dir = args.output_dir
            scan_dir = output_dir / "_work"
            scan_result = scan_image(
                args.input,
                scan_dir,
                args.mode,
                parse_layout(args.layout),
                args.background_tolerance,
                args.min_area,
                args.max_scan_size,
                args.overwrite,
            )
            plan = auto_plan(scan_result["scan"])
            plan_path = scan_dir / "auto-plan.json"
            ensure_writable([plan_path], args.overwrite)
            json_dump(plan_path, plan)
            result = apply_plan(args.input, scan_result["scan_path"], plan, output_dir, args.overwrite)
            manifest = result["manifest"]
            print(
                json.dumps(
                    {
                        "status": manifest["status"],
                        "review_required": manifest["review_required"],
                        "count": manifest["actual_count"],
                        "delivery": manifest["delivery"],
                        "warnings": manifest["warnings"],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2 if manifest["review_required"] else 0

        manifest = read_json(args.manifest)
        payload = {
            "status": manifest.get("status", "unknown"),
            "review_required": bool(manifest.get("review_required", True)),
            "count": manifest.get("actual_count"),
            "warnings": manifest.get("warnings", []),
            "delivery": manifest.get("delivery"),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2 if payload["review_required"] else 0
    except SplitError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 10
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": f"unexpected error: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
