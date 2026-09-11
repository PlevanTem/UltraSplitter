"""Route source items without treating rectangular overlap as semantic overlap."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .contracts import (
    MAX_SUBJECTS_PER_REPAIR_GRID,
    MIN_REPAIR_VISIBLE_FRACTION,
    load_json,
    require_v3,
    write_json,
)
from .core import load_image, make_contact_sheet
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


def _repair_eligibility(plan_item: dict[str, Any], source_clipped: bool) -> tuple[str, list[str]]:
    """Separate repair-worthy loss from clipping that still needs semantic triage."""
    assessment = plan_item.get("visual_assessment", {})
    if not isinstance(assessment, dict):
        assessment = {}
    reasons = _visual_requires_generation(plan_item)
    action = assessment.get("recommended_action")
    severity = assessment.get("missing_severity")
    confidence = assessment.get("identity_confidence", assessment.get("confidence"))
    visible = assessment.get("visible_fraction_estimate")
    recognizable = assessment.get("primary_content_recognizable")
    visibly_complete = assessment.get("complete") is True

    if action in {"deliver", "clean"} and visibly_complete and confidence == "high":
        return "not_required", []
    if action == "repair" or severity in {"minor", "repairable"}:
        if visible is None or visible < MIN_REPAIR_VISIBLE_FRACTION:
            return "needs_semantic_triage", ["below_repair_visibility_threshold"]
        if recognizable is not True or confidence == "low":
            return "needs_semantic_triage", ["insufficient_identity_evidence"]
        if source_clipped:
            reasons.append("source_clipped")
        return "eligible", sorted(set(reasons or ["visually_incomplete"]))
    if reasons:
        # Backward-compatible explicit assessments such as complete=false or touching=true
        # remain repair eligible even when the newer severity fields are absent.
        if assessment:
            if source_clipped:
                reasons.append("source_clipped")
            return "eligible", sorted(set(reasons))
    if source_clipped:
        return "needs_semantic_triage", ["source_clipped", "semantic_triage_required"]
    return "not_required", []


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
    triage_items: list[dict[str, Any]] = []
    for item in manifest["items"]:
        source_clipped = "source_clipped" in item.get("warnings", [])
        eligibility, reasons = _repair_eligibility(plan_items.get(item["id"], {}), source_clipped)
        bbox_overlaps = sorted(
            other["id"]
            for other in manifest["items"]
            if other["id"] != item["id"] and _intersection(raw_boxes[item["id"]], raw_boxes[other["id"]]) > 0
        )
        item["routing_evidence"] = {
            "bbox_overlaps": bbox_overlaps,
            "bbox_overlap_is_warning_only": True,
            "generation_reasons": sorted(set(reasons)),
            "repair_eligibility": eligibility,
        }
        if eligibility in {"eligible", "needs_semantic_triage"}:
            item["route"] = "generated_reconstruction"
            if eligibility == "eligible":
                generation_items.append(item)
            else:
                triage_items.append(item)
        elif candidate["kind"] == "objects" and bbox_overlaps:
            item["route"] = "source_composite"
        else:
            item["route"] = "source_crop"
        item["deliverable"] = item["route"] != "generated_reconstruction"
        item["provenance"] = {
            "origin": item["route"],
            "source_sha256": manifest["source"]["sha256"],
            "completion_is_inferred": item["route"] == "generated_reconstruction",
        }

    composite_dir = manifest_path.parent / "images" / "source-composite"
    alpha_dir = manifest_path.parent / "alpha" / "source-composite"
    isolated_dir = manifest_path.parent / "review" / "isolated"
    isolated_alpha_dir = manifest_path.parent / "review" / "isolated-alpha"
    for item in manifest["items"]:
        if item["route"] not in {"source_composite", "generated_reconstruction"}:
            continue
        filename = Path(item["image_path"]).name
        if candidate["kind"] != "objects":
            item["review_image_path"] = item["image_path"]
            continue
        output_path = composite_dir / filename if item["route"] == "source_composite" else isolated_dir / filename
        output_alpha = alpha_dir / filename if item["route"] == "source_composite" else isolated_alpha_dir / filename
        try:
            metrics = compose_source_item(
                Path(manifest["source"]["path"]),
                item,
                [region_map[region_id]["bbox"] for region_id in item["regions"]],
                candidate["evidence"].get("background_rgba", [255, 255, 255, 255]),
                int(candidate["evidence"].get("background_tolerance", 32)),
                output_path,
                output_alpha,
            )
            item.setdefault("evaluation", {}).update(metrics)
            if item["route"] == "source_composite":
                item["original_source_path"] = item["image_path"]
                item["image_path"] = str(output_path.resolve())
                item["rgba_path"] = str(output_alpha.resolve())
            else:
                item["review_image_path"] = str(output_path.resolve())
                item["review_alpha_path"] = str(output_alpha.resolve())
        except ValueError as exc:
            item["review_image_path"] = item["image_path"]
            warning = f"mask_cleanup_failed:{exc}"
            item.setdefault("warnings", []).append(warning)
            manifest.setdefault("warnings", []).append(f"{item['label']}:{warning}")

    ignored_preview_items: list[dict[str, Any]] = []
    source = load_image(Path(manifest["source"]["path"]))
    ignored_dir = manifest_path.parent / "review" / "ignored"
    ignored_alpha_dir = manifest_path.parent / "review" / "ignored-alpha"
    for exclusion in manifest.get("exclusions", []):
        filename = f"{exclusion['label']}.png"
        fake_item = {"id": exclusion["id"], "bbox": exclusion["bbox"]}
        output_path = ignored_dir / filename
        output_alpha = ignored_alpha_dir / filename
        try:
            if candidate["kind"] != "objects":
                raise ValueError("mask cleanup is available only for object candidates")
            compose_source_item(
                Path(manifest["source"]["path"]),
                fake_item,
                [region_map[region_id]["bbox"] for region_id in exclusion["regions"]],
                candidate["evidence"].get("background_rgba", [255, 255, 255, 255]),
                int(candidate["evidence"].get("background_tolerance", 32)),
                output_path,
                output_alpha,
            )
        except ValueError:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            source.crop(tuple(exclusion["bbox"])).save(output_path, format="PNG", optimize=True)
        exclusion["review_image_path"] = str(output_path.resolve())
        ignored_preview_items.append(
            {"label": f"[ignore] {exclusion['label']}", "image_path": str(output_path.resolve())}
        )

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
        "repair_item_count": len(generation_items),
        "recommended_ignored_count": len(manifest.get("exclusions", [])),
    }
    manifest.setdefault("repair_attempts", [])
    deliverable_items = [item for item in manifest["items"] if item.get("deliverable")]
    manifest["delivery"]["images"] = [item["image_path"] for item in deliverable_items]
    manifest["delivery"]["alpha_images"] = [
        item["rgba_path"] for item in deliverable_items if item.get("rgba_path")
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
            and assessment.get("identity_confidence", assessment.get("confidence")) == "high"
        )
        if not confirmed:
            warning = f"{item['label']}:semantic_assessment_required_for_composite"
            item.setdefault("warnings", []).append("semantic_assessment_required_for_composite")
            non_generation_warnings.append(warning)
            manifest.setdefault("warnings", []).append(warning)
    if triage_items:
        manifest["status"] = "needs_user_decision"
        manifest["review_required"] = True
    elif requested:
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
    triage_sheet = manifest_path.parent / "review" / "triage-sheet.png"
    triage_preview_items = []
    for item in manifest["items"]:
        if item.get("deliverable"):
            state = "deliver"
        elif item["routing_evidence"]["repair_eligibility"] == "eligible":
            state = "repair"
        else:
            state = "triage"
        triage_preview_items.append(
            {
                "label": f"[{state}] {item['label']}",
                "image_path": item.get("review_image_path", item["image_path"]),
            }
        )
    triage_preview_items.extend(ignored_preview_items)
    make_contact_sheet(triage_preview_items, triage_sheet)
    make_contact_sheet(deliverable_items, Path(manifest["delivery"]["contact_sheet"]))
    manifest["delivery"]["triage_sheet"] = str(triage_sheet.resolve())
    manifest["delivery"]["pending_repair_images"] = [
        item.get("review_image_path", item["image_path"])
        for item in generation_items
    ]
    manifest["delivery"]["ignored_images"] = [item["image_path"] for item in ignored_preview_items]
    manifest["deliverable_count"] = len(deliverable_items)
    manifest["repair_candidate_count"] = len(generation_items)
    manifest["ignored_count"] = len(manifest.get("exclusions", []))
    write_json(manifest_path, manifest)
    return manifest
