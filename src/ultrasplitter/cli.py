"""UltraSplitter command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import core
from .contracts import ContractError, __version__, load_json
from .evaluator import evaluate_manifest
from .repair import approve_repair, ingest_repair, prepare_repair
from .router import route_manifest


def _emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _summary(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": manifest.get("status", "unknown"),
        "review_required": bool(manifest.get("review_required", True)),
        "count": manifest.get("actual_count"),
        "deliverable_count": manifest.get("deliverable_count", manifest.get("actual_count")),
        "repair_candidate_count": manifest.get("repair_candidate_count", 0),
        "ignored_count": manifest.get("ignored_count", 0),
        "routes": {
            route: sum(item.get("route") == route for item in manifest.get("items", []))
            for route in ("source_crop", "source_composite", "generated_reconstruction")
        },
        "conflict_groups": len(manifest.get("conflict_groups", [])),
        "warnings": manifest.get("warnings", []),
        "delivery": manifest.get("delivery"),
    }


def _add_scan_options(parser: argparse.ArgumentParser, *, output_required: bool) -> None:
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=output_required)
    if not output_required:
        parser.add_argument("--name")
    parser.add_argument("--mode", choices=("auto", "panels", "objects"), default="auto")
    parser.add_argument("--layout")
    parser.add_argument("--background-tolerance", type=int, default=32)
    parser.add_argument("--min-area", type=float, default=0.00015)
    parser.add_argument("--max-scan-size", type=int, default=1400)
    parser.add_argument("--overwrite", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ultrasplit", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser("scan", help="find pixel-precise panel or object candidates")
    _add_scan_options(scan, output_required=True)
    apply = commands.add_parser("apply", help="apply an agent-authored plan")
    apply.add_argument("input", type=Path)
    apply.add_argument("--scan", type=Path, required=True)
    apply.add_argument("--plan", type=Path, required=True)
    apply.add_argument("--output-dir", type=Path, required=True)
    apply.add_argument("--overwrite", action="store_true")
    run = commands.add_parser("run", help="run the deterministic best-effort workflow")
    _add_scan_options(run, output_required=False)
    inspect = commands.add_parser("inspect", help="show the compact delivery verdict")
    inspect.add_argument("manifest", type=Path)
    evaluate = commands.add_parser("evaluate", help="evaluate a completed or repaired manifest")
    evaluate.add_argument("manifest", type=Path)
    evaluate.add_argument("--visual-verdict", choices=("pass", "retryable", "identity_uncertain"))

    repair = commands.add_parser("repair", help="prepare or ingest provider-neutral generated repairs")
    repairs = repair.add_subparsers(dest="repair_command", required=True)
    prepare = repairs.add_parser("prepare", help="write conflict crops, target maps, and prompts")
    prepare.add_argument("manifest", type=Path)
    approve = repairs.add_parser("approve", help="record the user's explicit approval")
    approve.add_argument("manifest", type=Path)
    approve.add_argument("--group", default="all")
    approve.add_argument("--approved-by", default="user")
    ingest = repairs.add_parser("ingest", help="validate and split a generated repair grid")
    ingest.add_argument("manifest", type=Path)
    ingest.add_argument("--group", required=True)
    ingest.add_argument("--grid", type=Path, required=True)
    return parser


def _scan(args: argparse.Namespace) -> dict[str, Any]:
    core.validate_scan_args(args)
    result = core.scan_image(
        args.input,
        args.output_dir,
        args.mode,
        core.parse_layout(args.layout),
        args.background_tolerance,
        args.min_area,
        args.max_scan_size,
        args.overwrite,
    )
    return {
        "status": "success",
        "scan": str(result["scan_path"].resolve()),
        "recommended_candidate_set": result["scan"]["recommended_candidate_set"],
        "previews": [candidate["preview"] for candidate in result["scan"]["candidate_sets"]],
    }


def _apply(args: argparse.Namespace) -> dict[str, Any]:
    result = core.apply_plan(args.input, args.scan, core.read_json(args.plan), args.output_dir, args.overwrite)
    manifest = route_manifest(result["manifest_path"])
    return _summary(manifest)


def _run(args: argparse.Namespace) -> dict[str, Any]:
    core.validate_scan_args(args)
    if args.output_dir is None:
        preferred = core.default_output_dir(args.input, args.name)
        output_dir = preferred if args.overwrite else core.unique_output_dir(preferred)
    else:
        output_dir = args.output_dir
    work = output_dir / "_work"
    scan_result = core.scan_image(
        args.input,
        work,
        args.mode,
        core.parse_layout(args.layout),
        args.background_tolerance,
        args.min_area,
        args.max_scan_size,
        args.overwrite,
    )
    plan = core.auto_plan(scan_result["scan"])
    plan_path = work / "auto-plan.json"
    core.ensure_writable([plan_path], args.overwrite)
    core.json_dump(plan_path, plan)
    result = core.apply_plan(args.input, scan_result["scan_path"], plan, output_dir, args.overwrite)
    return _summary(route_manifest(result["manifest_path"]))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "scan":
            payload = _scan(args)
        elif args.command == "apply":
            payload = _apply(args)
        elif args.command == "run":
            payload = _run(args)
        elif args.command == "inspect":
            payload = _summary(load_json(args.manifest))
        elif args.command == "evaluate":
            payload = _summary(evaluate_manifest(args.manifest, args.visual_verdict))
        elif args.repair_command == "prepare":
            payload = prepare_repair(args.manifest)
        elif args.repair_command == "approve":
            payload = approve_repair(args.manifest, args.group, args.approved_by)
        else:
            payload = ingest_repair(args.manifest, args.group, args.grid)
        _emit(payload)
        return 0 if payload.get("status") == "success" else 2
    except (core.SplitError, ContractError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 10
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": f"unexpected error: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 20
