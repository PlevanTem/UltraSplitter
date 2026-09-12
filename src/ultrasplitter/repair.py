"""Provider-neutral repair packets, approval recording, and grid ingestion."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .contracts import MAX_REPAIR_ATTEMPTS, load_json, require_v3, write_json
from .core import alpha_outputs, estimate_background, load_image, make_contact_sheet, readable_font
from .evaluator import evaluate_grid, evaluate_manifest
from .transparency import sync_transparent_delivery


def _expanded_crop(box: list[int], width: int, height: int, fraction: float = 0.08) -> list[int]:
    dx = round((box[2] - box[0]) * fraction)
    dy = round((box[3] - box[1]) * fraction)
    return [max(0, box[0] - dx), max(0, box[1] - dy), min(width, box[2] + dx), min(height, box[3] + dy)]


def _prompt(group: dict[str, Any]) -> str:
    layout = group["layout"]
    ids = ", ".join(group["item_ids"])
    return f"""Analyze the referenced dispute-region image and reconstruct exactly {layout['count']} target subjects.

Targets in row-major order: {ids}
Output layout: {layout['rows']} rows x {layout['columns']} columns.

Requirements:
The clean source montage isolates the targets; the context image preserves their original surroundings. Target IDs define row-major identity.
1. Put exactly one target in each used equal-sized cell, in the specified order.
2. Remove every unrelated object, fragment, caption, border, label, and watermark.
3. Conservatively complete parts clipped by the source edge or hidden by other elements.
4. Preserve every visible pose, silhouette, color, material, ornament, and design feature. Do not redesign, merge, duplicate, or add props.
5. Keep each subject fully visible with at least 10% safe margin and a similar visual scale.
6. Use one flat, uniform background with no drawn grid lines.
7. Produce enough resolution for at least 512 x 512 pixels per cell.

Generated pixels are a reconstruction, not recovered source truth.
"""


def _reference_images(
    source: Image.Image, item_map: dict[str, dict[str, Any]], group: dict[str, Any]
) -> tuple[Image.Image, Image.Image, str]:
    boxes = [item_map[item_id]["bbox"] for item_id in group["item_ids"]]
    if all(item_map[item_id].get("review_image_path") for item_id in group["item_ids"]):
        rows, columns = group["layout"]["rows"], group["layout"]["columns"]
        cell = 512
        clean = Image.new("RGBA", (columns * cell, rows * cell), "white")
        target_map = Image.new("RGBA", clean.size, "white")
        draw = ImageDraw.Draw(target_map, "RGBA")
        font = readable_font(20)
        for index, item_id in enumerate(group["item_ids"]):
            with Image.open(item_map[item_id]["review_image_path"]) as opened:
                snippet = opened.convert("RGBA")
            snippet.thumbnail((cell - 48, cell - 72), Image.Resampling.LANCZOS)
            row, column = divmod(index, columns)
            x = column * cell + (cell - snippet.width) // 2
            y = row * cell + 44 + (cell - 44 - snippet.height) // 2
            clean.alpha_composite(snippet, (x, y))
            target_map.alpha_composite(snippet, (x, y))
            draw.rectangle(
                (column * cell + 8, row * cell + 8, (column + 1) * cell - 8, (row + 1) * cell - 8),
                outline=(230, 40, 40, 255),
                width=3,
            )
            draw.text((column * cell + 18, row * cell + 16), item_id, fill=(230, 40, 40, 255), font=font)
        return clean, target_map, "isolated_reference_montage"

    union = _expanded_crop(group["source_bbox"], source.width, source.height)
    union_area = max(1, (union[2] - union[0]) * (union[3] - union[1]))
    item_area = max(1, sum((box[2] - box[0]) * (box[3] - box[1]) for box in boxes))
    if len(boxes) == 1 or union_area <= item_area * 2.5:
        crop = source.crop(tuple(union))
        target_map = crop.copy()
        draw = ImageDraw.Draw(target_map, "RGBA")
        font = readable_font(max(12, round(max(crop.size) / 60)))
        for item_id, box in zip(group["item_ids"], boxes):
            relative = [box[0] - union[0], box[1] - union[1], box[2] - union[0], box[3] - union[1]]
            draw.rectangle(relative, outline=(230, 40, 40, 255), width=max(2, round(max(crop.size) / 500)))
            draw.text((relative[0] + 3, relative[1] + 3), item_id, fill=(230, 40, 40, 255), font=font)
        return crop, target_map, "contiguous_crop"

    columns = math.ceil(math.sqrt(len(boxes)))
    rows = math.ceil(len(boxes) / columns)
    cell = 512
    clean = Image.new("RGBA", (columns * cell, rows * cell), "white")
    target_map = Image.new("RGBA", clean.size, "white")
    draw = ImageDraw.Draw(target_map, "RGBA")
    font = readable_font(20)
    for index, (item_id, box) in enumerate(zip(group["item_ids"], boxes)):
        crop_box = _expanded_crop(box, source.width, source.height)
        snippet = source.crop(tuple(crop_box))
        snippet.thumbnail((cell - 48, cell - 72), Image.Resampling.LANCZOS)
        row, column = divmod(index, columns)
        x = column * cell + (cell - snippet.width) // 2
        y = row * cell + 44 + (cell - 44 - snippet.height) // 2
        clean.alpha_composite(snippet, (x, y))
        target_map.alpha_composite(snippet, (x, y))
        draw.rectangle((column * cell + 8, row * cell + 8, (column + 1) * cell - 8, (row + 1) * cell - 8), outline=(230, 40, 40, 255), width=3)
        draw.text((column * cell + 18, row * cell + 16), item_id, fill=(230, 40, 40, 255), font=font)
    return clean, target_map, "reference_montage"


def prepare_repair(manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    require_v3(manifest)
    source = load_image(Path(manifest["source"]["path"]))
    repair_root = manifest_path.parent / "repair"
    item_map = {item["id"]: item for item in manifest["items"]}
    prepared: list[dict[str, Any]] = []
    for group in manifest.get("conflict_groups", []):
        group_dir = repair_root / group["id"]
        group_dir.mkdir(parents=True, exist_ok=True)
        source_path = group_dir / "source.png"
        context_path = group_dir / "context.png"
        target_map_path = group_dir / "target-map.png"
        prompt_path = group_dir / "prompt.txt"
        request_path = group_dir / "request.json"
        crop, target_map, source_mode = _reference_images(source, item_map, group)
        context_box = _expanded_crop(group["source_bbox"], source.width, source.height)
        context = source.crop(tuple(context_box))
        crop.save(source_path, format="PNG", optimize=True)
        context.save(context_path, format="PNG", optimize=True)
        target_map.save(target_map_path, format="PNG", optimize=True)
        prompt = _prompt(group)
        prompt_path.write_text(prompt, encoding="utf-8")
        request = {
            "schema_version": 3,
            "group_id": group["id"],
            "item_ids": group["item_ids"],
            "reasons": group["reasons"],
            "layout": group["layout"],
            "source_mode": source_mode,
            "source_bboxes": [item_map[item_id]["bbox"] for item_id in group["item_ids"]],
            "source": str(source_path.resolve()),
            "context": str(context_path.resolve()),
            "target_map": str(target_map_path.resolve()),
            "prompt": str(prompt_path.resolve()),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "generation_provider": None,
        }
        write_json(request_path, request)
        group["state"] = "prepared"
        group["artifacts"] = {
            "source": str(source_path.resolve()),
            "context": str(context_path.resolve()),
            "target_map": str(target_map_path.resolve()),
            "prompt": str(prompt_path.resolve()),
            "request": str(request_path.resolve()),
        }
        prepared.append(request)
    manifest["status"] = "awaiting_user_approval" if prepared else manifest["status"]
    manifest["review_required"] = manifest["status"] != "success"
    write_json(manifest_path, manifest)
    return {
        "status": manifest["status"],
        "summary": {
            "deliverable_count": manifest.get("deliverable_count", 0),
            "repair_candidate_count": manifest.get("repair_candidate_count", 0),
            "recommended_ignored_count": manifest.get("ignored_count", 0),
            "estimated_generation_calls": len(prepared),
            "max_attempts_per_group": MAX_REPAIR_ATTEMPTS,
            "triage_sheet": manifest.get("delivery", {}).get("triage_sheet"),
        },
        "requests": prepared,
        "manifest": str(manifest_path.resolve()),
    }


def approve_repair(manifest_path: Path, group_id: str, approved_by: str = "user") -> dict[str, Any]:
    manifest = load_json(manifest_path)
    require_v3(manifest)
    available = {group["id"] for group in manifest.get("conflict_groups", [])}
    selected = available if group_id == "all" else {group_id}
    unknown = selected - available
    if unknown:
        raise ValueError(f"unknown conflict groups: {', '.join(sorted(unknown))}")
    approval = manifest.setdefault("approval", {})
    approval["approved_groups"] = sorted(set(approval.get("approved_groups", [])) | selected)
    approval["approved_by"] = approved_by
    approval["state"] = "approved" if available <= set(approval["approved_groups"]) else "partial"
    for group in manifest.get("conflict_groups", []):
        if group["id"] in selected:
            group["state"] = "approved"
    manifest["status"] = "needs_review"
    write_json(manifest_path, manifest)
    return {"status": manifest["status"], "approval": approval, "manifest": str(manifest_path.resolve())}


def ingest_repair(manifest_path: Path, group_id: str, grid_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    require_v3(manifest)
    groups = {group["id"]: group for group in manifest.get("conflict_groups", [])}
    if group_id not in groups:
        raise ValueError(f"unknown conflict group: {group_id}")
    if group_id not in manifest.get("approval", {}).get("approved_groups", []):
        raise ValueError(f"repair group {group_id} has not been approved by the user")
    group = groups[group_id]
    prior = [attempt for attempt in manifest.get("repair_attempts", []) if attempt["group_id"] == group_id]
    if len(prior) >= MAX_REPAIR_ATTEMPTS:
        raise ValueError(f"repair group {group_id} exhausted its two allowed attempts")
    if not grid_path.is_file():
        raise ValueError(f"generated grid does not exist: {grid_path}")
    evaluation = evaluate_grid(grid_path, group["layout"])
    attempt_number = len(prior) + 1
    group_dir = manifest_path.parent / "repair" / group_id
    group_dir.mkdir(parents=True, exist_ok=True)
    archived_grid = group_dir / f"attempt-{attempt_number:02d}-grid.png"
    with Image.open(grid_path) as opened:
        grid = opened.convert("RGBA")
        grid.save(archived_grid, format="PNG", optimize=True)
    manifest.setdefault("repair_attempts", []).append(
        {
            "group_id": group_id,
            "attempt": attempt_number,
            "grid": str(archived_grid.resolve()),
            "evaluation": evaluation,
        }
    )
    if not evaluation["passed"]:
        group["state"] = "retry_exhausted" if attempt_number >= MAX_REPAIR_ATTEMPTS else "retryable"
        manifest["status"] = "retry_exhausted" if attempt_number >= MAX_REPAIR_ATTEMPTS else "needs_review"
        manifest["review_required"] = True
        write_json(manifest_path, manifest)
        return {"status": manifest["status"], "evaluation": evaluation, "manifest": str(manifest_path.resolve())}

    rows, columns = group["layout"]["rows"], group["layout"]["columns"]
    reconstructed = manifest_path.parent / "images" / "reconstructed"
    reconstructed_alpha = manifest_path.parent / "alpha" / "reconstructed"
    reconstructed_masks = manifest_path.parent / "masks" / "reconstructed"
    reconstructed.mkdir(parents=True, exist_ok=True)
    reconstructed_alpha.mkdir(parents=True, exist_ok=True)
    reconstructed_masks.mkdir(parents=True, exist_ok=True)
    item_map = {item["id"]: item for item in manifest["items"]}
    for index, item_id in enumerate(group["item_ids"]):
        row, column = divmod(index, columns)
        box = (
            round(column * grid.width / columns),
            round(row * grid.height / rows),
            round((column + 1) * grid.width / columns),
            round((row + 1) * grid.height / rows),
        )
        filename = Path(item_map[item_id]["image_path"]).name
        target = reconstructed / filename
        crop = grid.crop(box)
        crop.save(target, format="PNG", optimize=True)
        background, uniformity = estimate_background(crop, 32)
        item_map[item_id]["rgba_path"] = None
        item_map[item_id]["mask_path"] = None
        if background[3] <= 16 or uniformity >= 0.8:
            rgba, mask = alpha_outputs(crop, background, 32)
            rgba_path = reconstructed_alpha / filename
            mask_path = reconstructed_masks / filename
            rgba.save(rgba_path, format="PNG", optimize=True)
            mask.save(mask_path, format="PNG", optimize=True)
            item_map[item_id]["rgba_path"] = str(rgba_path.resolve())
            item_map[item_id]["mask_path"] = str(mask_path.resolve())
        item_map[item_id]["original_source_path"] = item_map[item_id]["image_path"]
        item_map[item_id]["image_path"] = str(target.resolve())
        item_map[item_id]["deliverable"] = True
        item_map[item_id]["provenance"].update(
            {"origin": "generated_reconstruction", "repair_group": group_id, "attempt": attempt_number}
        )
    group["state"] = "ingested"
    deliverable_items = [item for item in manifest["items"] if item.get("deliverable")]
    manifest["delivery"]["images"] = [item["image_path"] for item in deliverable_items]
    manifest["delivery"]["pending_repair_images"] = [
        item.get("review_image_path", item["image_path"])
        for item in manifest["items"]
        if item.get("route") == "generated_reconstruction" and not item.get("deliverable")
    ]
    manifest["deliverable_count"] = len(deliverable_items)
    manifest["delivery"]["contact_sheet_layout"] = make_contact_sheet(
        deliverable_items, Path(manifest["delivery"]["contact_sheet"])
    )
    sync_transparent_delivery(manifest, manifest_path)
    write_json(manifest_path, manifest)
    manifest = evaluate_manifest(manifest_path)
    return {"status": manifest["status"], "evaluation": evaluation, "delivery": manifest["delivery"]}
