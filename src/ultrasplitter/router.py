"""Route source items without treating rectangular overlap as semantic overlap."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .contracts import MAX_SUBJECTS_PER_REPAIR_GRID, load_json, require_v3, write_json
from .core import make_contact_sheet
from .extractor import compose_source_item


def _intersection(first: list[int], second: list[int]) -> int:
    return max(0, min(first[2], second[2]) - max(first[0], second[0])) * max(
        0, min(first[3], second[3]) - max(first[1], second[1])
    )


def _union(boxes: list[list[int]]) -> list[int]:
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def _expanded(box: list[int], fraction: float = 0.12) -> list[int]:
    dx = round((box[2] - box[0]) * fraction)
    dy = round((box[3] - box[1]) * fraction)
    return [box[0] - dx, box[1] - dy, box[2] + dx, box[3] + dy]


def _layout(count: int) -> dict[str, int]:
    columns = max(1, math.ceil(math.sqrt(count)))
    rows = math.ceil(count / columns)
    return {"rows": rows, "columns": columns, "count": count, "min_cell_size": 512}


def _visual_requires_generation(plan_item: dict[str, Any]) -> list[str]:
    assessment = plan_item.get("visual_assessment", {})
    if not isinstance(assessment, dict):
        return []
    reasons: list[str] = []
    if assessment.get("complete") is False:
        reasons.append("visually_incomplete")
    if assessment.get("occluded") is True:
        reasons.append("visually_occluded")
    if assessment.get("touching") is True:
        reasons.append("touching_subjects")
    if int(assessment.get("semantic_subject_count", 1)) > 1:
        reasons.append("multiple_subjects_in_one_component")
    return reasons


def route_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    require_v3(manifest)
    scan = load_json(Path(manifest["scan_path"]))
    candidate = next(
        candidate
        for candidate in scan["candidate_sets"]
        if candidate["id"] == manifest["plan"]["candidate_set"]
    )
    region_map = {region["id"]: region for region in candidate["regions"]}
    plan_items = {item.get("id"): item for item in manifest["plan"]["items"]}
    raw_boxes = {
        item["id"]: _union([region_map[region_id]["bbox"] for region_id in item["regions"]])
        for item in manifest["items"]
    }

    generation_items: list[dict[str, Any]] = []
    for item in manifest["items"]:
        reasons = [warning for warning in item.get("warnings", []) if warning == "source_clipped"]
        reasons.extend(_visual_requires_generation(plan_items.get(item["id"], {})))
        bbox_overlaps = sorted(
            other["id"]
            for other in manifest["items"]
            if other["id"] != item["id"] and _intersection(raw_boxes[item["id"]], raw_boxes[other["id"]]) > 0
        )
        item["routing_evidence"] = {
            "bbox_overlaps": bbox_overlaps,
            "bbox_overlap_is_warning_only": True,
            "generation_reasons": sorted(set(reasons)),
        }
        if reasons:
            item["route"] = "generated_reconstruction"
            generation_items.append(item)
        elif candidate["kind"] == "objects" and bbox_overlaps:
            item["route"] = "source_composite"
        else:
            item["route"] = "source_crop"
        item["provenance"] = {
            "origin": item["route"],
            "source_sha256": manifest["source"]["sha256"],
            "completion_is_inferred": item["route"] == "generated_reconstruction",
        }

    composite_dir = manifest_path.parent / "images" / "source-composite"
    alpha_dir = manifest_path.parent / "alpha" / "source-composite"
    for item in manifest["items"]:
        if item["route"] != "source_composite":
            continue
        filename = Path(item["image_path"]).name
        item["original_source_path"] = item["image_path"]
        metrics = compose_source_item(
            Path(manifest["source"]["path"]),
            item,
            [region_map[region_id]["bbox"] for region_id in item["regions"]],
            candidate["evidence"].get("background_rgba", [255, 255, 255, 255]),
            int(candidate["evidence"].get("background_tolerance", 32)),
            composite_dir / filename,
            alpha_dir / filename,
        )
        item["image_path"] = str((composite_dir / filename).resolve())
        item["rgba_path"] = str((alpha_dir / filename).resolve())
        item.setdefault("evaluation", {}).update(metrics)

    item_map = {item["id"]: item for item in manifest["items"]}
    # Connected conflict groups use spatially expanded source boxes, then split at six subjects.
    pending = {item["id"] for item in generation_items}
    groups: list[list[str]] = []
    while pending:
        seed = min(pending, key=lambda value: (raw_boxes[value][1], raw_boxes[value][0], value))
        pending.remove(seed)
        component = {seed}
        frontier = [seed]
        while frontier:
            current = frontier.pop()
            neighbours = {
                candidate_id
                for candidate_id in pending
                if _intersection(_expanded(raw_boxes[current]), _expanded(raw_boxes[candidate_id])) > 0
            }
            pending -= neighbours
            component |= neighbours
            frontier.extend(neighbours)
        ordered = sorted(component, key=lambda item_id: (raw_boxes[item_id][1], raw_boxes[item_id][0]))
        groups.extend(
            ordered[index : index + MAX_SUBJECTS_PER_REPAIR_GRID]
            for index in range(0, len(ordered), MAX_SUBJECTS_PER_REPAIR_GRID)
        )

    # Batch isolated repairs by the same reason so image generation is not invoked once per subject.
    multi_groups = [group for group in groups if len(group) > 1]
    single_groups = [group[0] for group in groups if len(group) == 1]
    batched_singles: list[list[str]] = []
    reason_buckets: dict[tuple[str, ...], list[str]] = {}
    for item_id in sorted(single_groups, key=lambda value: (raw_boxes[value][1], raw_boxes[value][0])):
        key = tuple(item_map[item_id]["routing_evidence"]["generation_reasons"])
        reason_buckets.setdefault(key, []).append(item_id)
    for bucket in reason_buckets.values():
        batched_singles.extend(
            bucket[index : index + MAX_SUBJECTS_PER_REPAIR_GRID]
            for index in range(0, len(bucket), MAX_SUBJECTS_PER_REPAIR_GRID)
        )
    groups = multi_groups + batched_singles
    groups.sort(key=lambda group: (raw_boxes[group[0]][1], raw_boxes[group[0]][0], group[0]))

    manifest["conflict_groups"] = []
    for index, item_ids in enumerate(groups, 1):
        reasons = sorted(
            {
                reason
                for item_id in item_ids
                for reason in item_map[item_id]["routing_evidence"]["generation_reasons"]
            }
        )
        manifest["conflict_groups"].append(
            {
                "id": f"conflict-{index:03d}",
                "item_ids": item_ids,
                "source_bbox": _union([raw_boxes[item_id] for item_id in item_ids]),
                "reasons": reasons,
                "layout": _layout(len(item_ids)),
                "state": "pending",
                "artifacts": {},
            }
        )

    requested = [group["id"] for group in manifest["conflict_groups"]]
    manifest["approval"] = {
        "required": bool(requested),
        "state": "pending" if requested else "not_required",
        "requested_groups": requested,
        "approved_groups": [],
        "max_attempts_per_group": 2,
        "estimated_generation_calls": len(requested),
    }
    manifest.setdefault("repair_attempts", [])
    manifest["delivery"]["images"] = [item["image_path"] for item in manifest["items"]]
    manifest["delivery"]["alpha_images"] = [
        item["rgba_path"] for item in manifest["items"] if item.get("rgba_path")
    ]
    non_generation_warnings = [
        warning for warning in manifest.get("warnings", []) if not warning.endswith(":source_clipped")
    ]
    for item in manifest["items"]:
        if item["route"] != "source_composite":
            continue
        assessment = plan_items.get(item["id"], {}).get("visual_assessment", {})
        confirmed = (
            isinstance(assessment, dict)
            and assessment.get("complete") is True
            and int(assessment.get("semantic_subject_count", 1)) == 1
            and assessment.get("confidence") == "high"
        )
        if not confirmed:
            warning = f"{item['label']}:semantic_assessment_required_for_composite"
            item.setdefault("warnings", []).append("semantic_assessment_required_for_composite")
            non_generation_warnings.append(warning)
            manifest.setdefault("warnings", []).append(warning)
    if requested:
        manifest["status"] = "awaiting_user_approval"
        manifest["review_required"] = True
    elif non_generation_warnings:
        manifest["status"] = "needs_review"
        manifest["review_required"] = True
    else:
        manifest["status"] = "success"
        manifest["review_required"] = False
    manifest["evaluation"] = {
        "deterministic": "pass" if not non_generation_warnings else "review",
        "visual": "not_run",
        "success_conditions": {
            "exact_count": True,
            "foreign_foreground_ratio_max": 0.005,
            "safe_margin_ratio_min": 0.08,
            "max_repair_attempts": 2,
        },
    }
    make_contact_sheet(manifest["items"], Path(manifest["delivery"]["contact_sheet"]))
    write_json(manifest_path, manifest)
    return manifest
