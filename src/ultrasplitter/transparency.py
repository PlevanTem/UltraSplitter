"""Independent candidate, preview, and verdict handling for transparent variants."""

from __future__ import annotations

from math import ceil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .presentation import render_transparency_review_sheet


TRANSPARENT_VERDICTS = {"pass", "retryable", "reject"}
MIN_SAFE_MARGIN_RATIO = 0.08


def _required_symmetric_padding(size: int, near: int, far: int) -> int:
    current_margin = min(near, size - far)
    required = (MIN_SAFE_MARGIN_RATIO * size - current_margin) / (
        1 - 2 * MIN_SAFE_MARGIN_RATIO
    )
    return max(0, ceil(required))


def prepare_transparent_candidate(source_path: Path, output_path: Path) -> Path:
    """Copy an alpha candidate while adding only transparent pixels for safe review margin."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as opened:
        source = opened.copy()
    if "A" not in source.getbands():
        source.save(output_path, format="PNG", optimize=True)
        return output_path.resolve()

    rgba = source.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] > 16:
        rgba.save(output_path, format="PNG", optimize=True)
        return output_path.resolve()
    foreground = alpha.point(lambda value: 255 if value > 16 else 0)
    bbox = foreground.getbbox()
    if bbox is None:
        rgba.save(output_path, format="PNG", optimize=True)
        return output_path.resolve()

    horizontal = _required_symmetric_padding(rgba.width, bbox[0], bbox[2])
    vertical = _required_symmetric_padding(rgba.height, bbox[1], bbox[3])
    if horizontal or vertical:
        padded = Image.new(
            "RGBA",
            (rgba.width + horizontal * 2, rgba.height + vertical * 2),
            (0, 0, 0, 0),
        )
        padded.alpha_composite(rgba, (horizontal, vertical))
        rgba = padded
    rgba.save(output_path, format="PNG", optimize=True)
    return output_path.resolve()


def inspect_transparent_candidate(path: Path) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    if not path.is_file():
        return {
            "path": str(path.resolve()),
            "passed": False,
            "issues": ["missing_file"],
            "warnings": [],
        }
    with Image.open(path) as opened:
        has_alpha = "A" in opened.getbands()
        rgba = opened.convert("RGBA")
    alpha = rgba.getchannel("A")
    alpha_min, alpha_max = alpha.getextrema()
    if not has_alpha:
        issues.append("missing_alpha_channel")
    if alpha_min > 16:
        issues.append("no_transparent_background")
    foreground = alpha.point(lambda value: 255 if value > 16 else 0)
    bbox = foreground.getbbox()
    safe_margin = 0.0
    hole_ratio = 0.0
    if bbox is None:
        issues.append("empty_foreground")
    else:
        edge_contact = (
            bbox[0] == 0
            or bbox[1] == 0
            or bbox[2] == rgba.width
            or bbox[3] == rgba.height
        )
        safe_margin = min(
            bbox[0] / rgba.width,
            bbox[1] / rgba.height,
            (rgba.width - bbox[2]) / rgba.width,
            (rgba.height - bbox[3]) / rgba.height,
        )
        if edge_contact:
            issues.append("foreground_touches_canvas_edge")
        elif safe_margin < MIN_SAFE_MARGIN_RATIO:
            issues.append("insufficient_safe_margin")

        exterior = foreground.copy()
        corners = (
            (0, 0),
            (rgba.width - 1, 0),
            (0, rgba.height - 1),
            (rgba.width - 1, rgba.height - 1),
        )
        for point in corners:
            if exterior.getpixel(point) == 0:
                ImageDraw.floodfill(exterior, point, 128, thresh=0)
        holes = exterior.crop(bbox).histogram()[0]
        hole_ratio = holes / max(1, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
        if hole_ratio > 0.002:
            warnings.append("interior_transparency_requires_visual_review")

    histogram = alpha.histogram()
    total = max(1, rgba.width * rgba.height)
    semi_transparent_ratio = sum(histogram[17:240]) / total
    return {
        "path": str(path.resolve()),
        "passed": not issues,
        "issues": issues,
        "warnings": warnings,
        "metrics": {
            "size": [rgba.width, rgba.height],
            "alpha_extrema": [alpha_min, alpha_max],
            "foreground_bbox": list(bbox) if bbox else None,
            "safe_margin_ratio": round(safe_margin, 6),
            "interior_transparent_hole_ratio": round(hole_ratio, 6),
            "semi_transparent_ratio": round(semi_transparent_ratio, 6),
        },
    }


def sync_transparent_delivery(manifest: dict[str, Any], manifest_path: Path) -> None:
    delivery = manifest.setdefault("delivery", {})
    items = [
        item
        for item in manifest.get("items", [])
        if item.get("deliverable") and item.get("rgba_path")
    ]
    candidate_root = manifest_path.parent / "transparent-candidates"
    candidates: list[str] = []
    for item in items:
        source = Path(item["rgba_path"])
        filename = Path(item.get("image_path") or source).name
        target = candidate_root / filename
        candidates.append(str(prepare_transparent_candidate(source, target)))
    candidate_by_id = {
        item["id"]: candidate for item, candidate in zip(items, candidates)
    }
    delivery["alpha_images"] = candidates  # Backward-compatible candidate alias.
    delivery["transparent_candidates"] = candidates
    delivery["transparent_images"] = []
    for item in manifest.get("items", []):
        variants = item.setdefault("variants", {})
        variants["opaque"] = item.get("image_path") if item.get("deliverable") else None
        variants["transparent_candidate"] = candidate_by_id.get(item.get("id"))
        variants["transparent"] = None

    review_root = manifest_path.parent / "review"
    sheets: dict[str, str] = {}
    sheet_layouts: dict[str, dict[str, Any]] = {}
    preview_items = [
        {"label": item["label"], "image_path": candidate}
        for item, candidate in zip(items, candidates)
    ]
    for style in ("white", "black", "checkerboard"):
        sheet = review_root / f"transparent-{style}-sheet.png"
        layout = render_transparency_review_sheet(preview_items, sheet, style)
        sheets[style] = str(sheet.resolve())
        sheet_layouts[style] = layout
    delivery["transparent_review_sheets"] = sheets
    delivery["transparent_review_sheet_layouts"] = sheet_layouts

    checks = [inspect_transparent_candidate(Path(path)) for path in candidates]
    manifest.setdefault("evaluation", {})["transparent"] = {
        "status": "needs_review" if candidates else "not_requested",
        "visual": "not_run",
        "candidate_count": len(candidates),
        "deliverable_count": 0,
        "automatic": {
            "passed": bool(candidates) and all(check["passed"] for check in checks),
            "items": checks,
        },
        "success_conditions": {
            "alpha_channel": True,
            "transparent_background": True,
            "safe_margin_ratio_min": MIN_SAFE_MARGIN_RATIO,
            "review_backgrounds": ["white", "black", "checkerboard"],
            "no_holes_halos_or_subject_damage": True,
        },
    }
    delivery["transparent_review_required"] = bool(candidates)


def apply_transparent_verdict(manifest: dict[str, Any], verdict: str | None) -> None:
    delivery = manifest.setdefault("delivery", {})
    candidates = delivery.get("transparent_candidates", [])
    transparent = manifest.setdefault("evaluation", {}).setdefault("transparent", {})
    if manifest.get("status") != "success" and transparent.get("status") == "pass":
        transparent["status"] = "needs_primary_review"
        transparent["deliverable_count"] = 0
        delivery["transparent_images"] = []
        delivery["transparent_review_required"] = True
        for item in manifest.get("items", []):
            item.setdefault("variants", {})["transparent"] = None
    if verdict is None:
        return
    if verdict not in TRANSPARENT_VERDICTS:
        raise ValueError("transparent verdict must be pass, retryable, or reject")
    if not candidates:
        raise ValueError("manifest has no transparent candidates to review")
    transparent["visual"] = verdict
    if verdict == "pass" and manifest.get("status") != "success":
        transparent["status"] = "needs_primary_review"
        delivery["transparent_images"] = []
        transparent["deliverable_count"] = 0
        delivery["transparent_review_required"] = True
    elif verdict == "pass" and transparent.get("automatic", {}).get("passed") is True:
        transparent["status"] = "pass"
        delivery["transparent_images"] = list(candidates)
        transparent["deliverable_count"] = len(candidates)
        delivery["transparent_review_required"] = False
        approved = set(candidates)
        for item in manifest.get("items", []):
            candidate = item.get("variants", {}).get("transparent_candidate")
            item.setdefault("variants", {})["transparent"] = candidate if candidate in approved else None
    else:
        transparent["status"] = "retryable" if verdict in {"pass", "retryable"} else "rejected"
        if verdict == "pass":
            transparent["visual"] = "pass_rejected_by_automatic_checks"
        delivery["transparent_images"] = []
        transparent["deliverable_count"] = 0
        delivery["transparent_review_required"] = transparent["status"] == "retryable"
        for item in manifest.get("items", []):
            item.setdefault("variants", {})["transparent"] = None
