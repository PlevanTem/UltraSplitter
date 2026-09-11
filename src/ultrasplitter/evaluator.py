"""Deterministic checks for generated repair grids and completed manifests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageStat

from .core import estimate_background, foreground_mask
from .contracts import MAX_REPAIR_ATTEMPTS, load_json, require_v3, write_json


def _shape_signature(mask: Image.Image) -> bytes:
    bbox = mask.getbbox()
    if bbox is None:
        return bytes(64 * 64)
    return mask.crop(bbox).resize((64, 64), Image.Resampling.NEAREST).tobytes()


def _shape_distance(first: bytes, second: bytes) -> float:
    return sum(abs(left - right) for left, right in zip(first, second)) / (255 * len(first))


def evaluate_grid(path: Path, layout: dict[str, int]) -> dict[str, Any]:
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
    rows, columns, expected = layout["rows"], layout["columns"], layout["count"]
    issues: list[str] = []
    if image.width < columns * 512 or image.height < rows * 512:
        issues.append("effective_cell_resolution_below_512")
    background, uniformity = estimate_background(image, 32)
    if uniformity < 0.9:
        issues.append("background_not_uniform")
    border = Image.new("RGB", (image.width * 2 + image.height * 2, 1))
    border.putdata(
        [image.getpixel((x, 0))[:3] for x in range(image.width)]
        + [image.getpixel((x, image.height - 1))[:3] for x in range(image.width)]
        + [image.getpixel((0, y))[:3] for y in range(image.height)]
        + [image.getpixel((image.width - 1, y))[:3] for y in range(image.height)]
    )
    background_stddev = max(ImageStat.Stat(border).stddev)
    if background_stddev > 4.0:
        issues.append("background_not_uniform")

    cells: list[dict[str, Any]] = []
    signatures: list[bytes] = []
    for index in range(rows * columns):
        row, column = divmod(index, columns)
        left = round(column * image.width / columns)
        right = round((column + 1) * image.width / columns)
        top = round(row * image.height / rows)
        bottom = round((row + 1) * image.height / rows)
        cell = image.crop((left, top, right, bottom))
        cell_background, _ = estimate_background(cell, 32)
        mask = foreground_mask(cell, cell_background, 32)
        bbox = mask.getbbox()
        occupancy = sum(mask.tobytes()) / (255 * max(1, cell.width * cell.height))
        edge_contact = False
        safe_margin = 0.0
        if bbox:
            edge_contact = bbox[0] == 0 or bbox[1] == 0 or bbox[2] == cell.width or bbox[3] == cell.height
            safe_margin = min(
                bbox[0] / cell.width,
                bbox[1] / cell.height,
                (cell.width - bbox[2]) / cell.width,
                (cell.height - bbox[3]) / cell.height,
            )
        cells.append(
            {
                "index": index + 1,
                "bbox": [left, top, right, bottom],
                "occupied": occupancy >= 0.001,
                "occupancy": round(occupancy, 6),
                "edge_contact": edge_contact,
                "safe_margin_ratio": round(safe_margin, 6),
            }
        )
        signatures.append(_shape_signature(mask))

    occupied = [cell for cell in cells if cell["occupied"]]
    if len(occupied) != expected:
        issues.append(f"occupied_cell_count:{len(occupied)}:expected:{expected}")
    for cell in occupied:
        if cell["edge_contact"]:
            issues.append(f"cell_{cell['index']:03d}_edge_contact")
        elif cell["safe_margin_ratio"] < 0.08:
            issues.append(f"cell_{cell['index']:03d}_insufficient_margin")

    duplicate_pairs: list[list[int]] = []
    for left in range(min(expected, len(signatures))):
        for right in range(left + 1, min(expected, len(signatures))):
            if cells[left]["occupied"] and cells[right]["occupied"] and _shape_distance(signatures[left], signatures[right]) <= 0.02:
                duplicate_pairs.append([left + 1, right + 1])

    return {
        "passed": not issues,
        "issues": sorted(set(issues)),
        "metrics": {
            "width": image.width,
            "height": image.height,
            "background_uniformity": round(uniformity, 6),
            "background_border_stddev": round(background_stddev, 6),
            "expected_count": expected,
            "occupied_count": len(occupied),
            "possible_duplicate_cells": duplicate_pairs,
            "cells": cells,
        },
        "visual_review_required": True,
    }


def evaluate_manifest(manifest_path: Path, visual_verdict: str | None = None) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    require_v3(manifest)
    if visual_verdict not in {None, "pass", "retryable", "identity_uncertain"}:
        raise ValueError("visual verdict must be pass, retryable, or identity_uncertain")
    groups = manifest.get("conflict_groups", [])
    untriaged = [
        item
        for item in manifest.get("items", [])
        if item.get("routing_evidence", {}).get("repair_eligibility") == "needs_semantic_triage"
    ]
    pending = [group for group in groups if group.get("state") not in {"ingested", "not_required"}]
    latest_attempts: dict[str, dict[str, Any]] = {}
    for attempt in manifest.get("repair_attempts", []):
        latest_attempts[attempt["group_id"]] = attempt
    hard_failures = [
        attempt
        for group_id, attempt in latest_attempts.items()
        if groups
        and next(group for group in groups if group["id"] == group_id).get("state") != "ingested"
        and not attempt.get("evaluation", {}).get("passed", False)
    ]
    manifest.setdefault("delivery", {})["pending_repair_images"] = [
        item.get("review_image_path", item["image_path"])
        for item in manifest.get("items", [])
        if item.get("route") == "generated_reconstruction" and not item.get("deliverable")
    ]
    manifest.setdefault("evaluation", {})["visual"] = visual_verdict or manifest["evaluation"].get(
        "visual", "not_run"
    )
    if untriaged:
        manifest["status"] = "needs_user_decision"
    elif pending and manifest.get("approval", {}).get("state") != "approved":
        manifest["status"] = "awaiting_user_approval"
    elif any(
        len([attempt for attempt in manifest.get("repair_attempts", []) if attempt["group_id"] == group["id"]])
        >= MAX_REPAIR_ATTEMPTS
        and group.get("state") != "ingested"
        for group in groups
    ):
        manifest["status"] = "retry_exhausted"
    elif visual_verdict == "identity_uncertain":
        manifest["status"] = "needs_user_decision"
    elif visual_verdict == "retryable" or hard_failures or pending:
        manifest["status"] = "needs_review"
    elif groups and visual_verdict != "pass":
        manifest["status"] = "needs_review"
    else:
        manifest["status"] = "success"
    manifest["review_required"] = manifest["status"] != "success"
    write_json(manifest_path, manifest)
    return manifest
