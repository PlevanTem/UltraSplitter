from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from ultrasplitter import core
from ultrasplitter.evaluator import evaluate_manifest
from ultrasplitter.repair import approve_repair, ingest_repair, prepare_repair
from ultrasplitter.router import route_manifest


def apply_auto(source: Path, root: Path, mode: str = "objects") -> tuple[dict, Path]:
    scan = core.scan_image(source, root / "scan", mode, None, 32, 0.0005, 1000, False)
    plan = core.auto_plan(scan["scan"])
    result = core.apply_plan(source, scan["scan_path"], plan, root / "result", False)
    return route_manifest(result["manifest_path"]), result["manifest_path"]


def apply_repair_eligible(source: Path, root: Path) -> tuple[dict, Path]:
    scan = core.scan_image(source, root / "scan", "objects", None, 32, 0.0005, 1000, False)
    region = scan["scan"]["candidate_sets"][0]["regions"][0]["id"]
    plan = {
        "schema_version": 3,
        "mode": "objects",
        "candidate_set": scan["scan"]["candidate_sets"][0]["id"],
        "expected_count": 1,
        "items": [
            {
                "id": "item-001",
                "label": "repairable",
                "regions": [region],
                "visual_assessment": {
                    "complete": False,
                    "missing_severity": "repairable",
                    "visible_fraction_estimate": 0.75,
                    "primary_content_recognizable": True,
                    "critical_parts_missing": [],
                    "identity_confidence": "high",
                    "recommended_action": "repair",
                },
            }
        ],
    }
    result = core.apply_plan(source, scan["scan_path"], plan, root / "result", False)
    return route_manifest(result["manifest_path"]), result["manifest_path"]


class RouteAndRepairTests(unittest.TestCase):
    def test_overlapping_boxes_with_disjoint_foreground_use_source_composite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "overlap.png"
            image = Image.new("RGB", (300, 270), "white")
            draw = ImageDraw.Draw(image)
            draw.line([(35, 35), (35, 220), (170, 220)], fill="red", width=24)
            draw.line([(100, 75), (255, 75), (255, 245)], fill="blue", width=24)
            image.save(source)
            manifest, _ = apply_auto(source, root)
            self.assertEqual(len(manifest["items"]), 2)
            self.assertTrue(all(item["route"] == "source_composite" for item in manifest["items"]))
            self.assertEqual(manifest["status"], "needs_review")
            self.assertTrue(all("source-composite" in item["image_path"] for item in manifest["items"]))
            with Image.open(manifest["items"][0]["rgba_path"]) as alpha:
                self.assertEqual(alpha.convert("RGBA").getpixel((0, 0))[3], 0)

    def test_clipped_source_requires_approval_and_prepare_creates_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "clipped.png"
            image = Image.new("RGB", (220, 160), "white")
            ImageDraw.Draw(image).rectangle((0, 30, 80, 130), fill="purple")
            image.save(source)
            manifest, manifest_path = apply_repair_eligible(source, root)
            self.assertEqual(manifest["status"], "awaiting_user_approval")
            self.assertEqual(manifest["items"][0]["route"], "generated_reconstruction")
            self.assertFalse(manifest["items"][0]["deliverable"])
            self.assertEqual(manifest["delivery"]["images"], [])
            packet = prepare_repair(manifest_path)
            self.assertEqual(packet["status"], "awaiting_user_approval")
            self.assertTrue(Path(packet["requests"][0]["source"]).is_file())
            self.assertTrue(Path(packet["requests"][0]["context"]).is_file())
            self.assertTrue(Path(packet["requests"][0]["target_map"]).is_file())

    def test_unassessed_clipped_source_requires_semantic_triage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "clipped.png"
            image = Image.new("RGB", (220, 160), "white")
            ImageDraw.Draw(image).rectangle((0, 30, 80, 130), fill="purple")
            image.save(source)
            manifest, _ = apply_auto(source, root)
            self.assertEqual(manifest["status"], "needs_user_decision")
            self.assertEqual(manifest["conflict_groups"], [])
            self.assertEqual(manifest["approval"]["estimated_generation_calls"], 0)
            self.assertEqual(manifest["delivery"]["images"], [])
            self.assertTrue(Path(manifest["delivery"]["triage_sheet"]).is_file())
            reevaluated = evaluate_manifest(Path(manifest["delivery"]["manifest"]), "pass")
            self.assertEqual(reevaluated["status"], "needs_user_decision")

    def test_severe_fragments_are_ignored_and_never_enter_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "mixed.png"
            image = Image.new("RGB", (320, 220), "white")
            draw = ImageDraw.Draw(image)
            draw.ellipse((120, 55, 215, 170), fill="green")
            draw.rectangle((0, 175, 35, 219), fill="purple")
            image.save(source)
            scan = core.scan_image(source, root / "scan", "objects", None, 32, 0.0005, 1000, False)
            candidate = scan["scan"]["candidate_sets"][0]
            complete = next(region for region in candidate["regions"] if "source_clipped" not in region["flags"])
            fragment = next(region for region in candidate["regions"] if "source_clipped" in region["flags"])
            plan = {
                "schema_version": 3,
                "mode": "objects",
                "candidate_set": candidate["id"],
                "expected_count": 1,
                "exclude_regions": [fragment["id"]],
                "exclusions": [
                    {
                        "id": "excluded-001",
                        "label": "severe-fragment",
                        "regions": [fragment["id"]],
                        "missing_severity": "severe",
                        "visible_fraction_estimate": 0.15,
                        "primary_content_recognizable": False,
                        "critical_parts_missing": ["identity"],
                        "recommended_action": "ignore",
                        "reason": ["insufficient_identity_evidence"],
                    }
                ],
                "items": [{"id": "item-001", "label": "complete", "regions": [complete["id"]]}],
            }
            result = core.apply_plan(source, scan["scan_path"], plan, root / "result", False)
            manifest = route_manifest(result["manifest_path"])
            self.assertEqual(manifest["conflict_groups"], [])
            self.assertEqual(manifest["repair_candidate_count"], 0)
            self.assertEqual(manifest["ignored_count"], 1)
            self.assertEqual(manifest["deliverable_count"], 1)
            self.assertEqual(len(manifest["delivery"]["images"]), 1)
            self.assertEqual(len(manifest["delivery"]["ignored_images"]), 1)

    def test_repair_preview_removes_unrelated_foreground(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "contaminated.png"
            image = Image.new("RGB", (240, 180), "white")
            draw = ImageDraw.Draw(image)
            draw.line([(0, 20), (110, 20), (110, 155), (0, 155)], fill="purple", width=12)
            draw.ellipse((40, 65, 75, 105), fill="orange")
            image.save(source)
            scan = core.scan_image(source, root / "scan", "objects", None, 32, 0.0005, 1000, False)
            candidate = scan["scan"]["candidate_sets"][0]
            clipped = next(region for region in candidate["regions"] if "source_clipped" in region["flags"])
            inner = next(region for region in candidate["regions"] if "source_clipped" not in region["flags"])
            assessment = {
                "complete": False,
                "missing_severity": "repairable",
                "visible_fraction_estimate": 0.8,
                "primary_content_recognizable": True,
                "identity_confidence": "high",
                "recommended_action": "repair",
            }
            plan = {
                "schema_version": 3,
                "mode": "objects",
                "candidate_set": candidate["id"],
                "expected_count": 2,
                "items": [
                    {"id": "item-001", "label": "frame", "regions": [clipped["id"]], "visual_assessment": assessment},
                    {
                        "id": "item-002",
                        "label": "inner",
                        "regions": [inner["id"]],
                        "visual_assessment": {
                            "complete": True,
                            "semantic_subject_count": 1,
                            "confidence": "high",
                            "recommended_action": "clean",
                        },
                    },
                ],
            }
            result = core.apply_plan(source, scan["scan_path"], plan, root / "result", False)
            manifest = route_manifest(result["manifest_path"])
            repair_item = manifest["items"][0]
            self.assertFalse(repair_item["deliverable"])
            self.assertNotIn(repair_item["image_path"], manifest["delivery"]["images"])
            with Image.open(repair_item["review_image_path"]) as preview:
                pixels = preview.convert("RGB").tobytes()
                orange_pixels = sum(
                    1
                    for red, green, blue in zip(pixels[0::3], pixels[1::3], pixels[2::3])
                    if red > 180 and 60 < green < 190 and blue < 80
                )
            self.assertEqual(orange_pixels, 0)

    def test_repair_requires_visible_recognizable_majority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "clipped.png"
            image = Image.new("RGB", (220, 160), "white")
            ImageDraw.Draw(image).rectangle((0, 30, 80, 130), fill="purple")
            image.save(source)
            scan = core.scan_image(source, root / "scan", "objects", None, 32, 0.0005, 1000, False)
            region = scan["scan"]["candidate_sets"][0]["regions"][0]["id"]
            base_assessment = {
                "complete": False,
                "missing_severity": "repairable",
                "identity_confidence": "high",
                "recommended_action": "repair",
            }
            for visible, recognizable, message in (
                (0.64, True, "visible_fraction_estimate >= 0.65"),
                (0.65, False, "primary_content_recognizable=true"),
            ):
                plan = {
                    "schema_version": 3,
                    "mode": "objects",
                    "candidate_set": scan["scan"]["candidate_sets"][0]["id"],
                    "expected_count": 1,
                    "items": [
                        {
                            "id": "item-001",
                            "label": "candidate",
                            "regions": [region],
                            "visual_assessment": {
                                **base_assessment,
                                "visible_fraction_estimate": visible,
                                "primary_content_recognizable": recognizable,
                            },
                        }
                    ],
                }
                with self.assertRaisesRegex(core.SplitError, message):
                    core.apply_plan(source, scan["scan_path"], plan, root / f"result-{visible}-{recognizable}", False)

    def test_recognizable_majority_cannot_be_silently_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "clipped.png"
            image = Image.new("RGB", (220, 160), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 30, 65, 130), fill="purple")
            draw.ellipse((125, 45, 195, 120), fill="green")
            image.save(source)
            scan = core.scan_image(source, root / "scan", "objects", None, 32, 0.0005, 1000, False)
            regions = scan["scan"]["candidate_sets"][0]["regions"]
            region = next(item for item in regions if "source_clipped" in item["flags"])["id"]
            complete = next(item for item in regions if "source_clipped" not in item["flags"])["id"]
            plan = {
                "schema_version": 3,
                "mode": "objects",
                "candidate_set": scan["scan"]["candidate_sets"][0]["id"],
                "expected_count": 1,
                "exclude_regions": [region],
                "exclusions": [
                    {
                        "id": "excluded-001",
                        "label": "recognizable-majority",
                        "regions": [region],
                        "missing_severity": "repairable",
                        "visible_fraction_estimate": 0.65,
                        "primary_content_recognizable": True,
                        "identity_confidence": "high",
                        "recommended_action": "ignore",
                    }
                ],
                "items": [{"id": "item-001", "label": "complete", "regions": [complete]}],
            }
            with self.assertRaisesRegex(core.SplitError, "must be offered for repair"):
                core.apply_plan(source, scan["scan_path"], plan, root / "result", False)

    def test_touching_semantic_targets_share_region_only_for_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "touching.png"
            image = Image.new("RGB", (360, 240), "white")
            draw = ImageDraw.Draw(image)
            draw.ellipse((35, 45, 190, 200), fill="red")
            draw.rectangle((190, 70, 325, 190), fill="blue")
            image.save(source)
            scan = core.scan_image(source, root / "scan", "objects", None, 32, 0.0005, 1000, False)
            region = scan["scan"]["candidate_sets"][0]["regions"][0]["id"]
            assessment = {"complete": False, "touching": True, "semantic_subject_count": 2}
            plan = {
                "schema_version": 3,
                "mode": "objects",
                "candidate_set": scan["scan"]["candidate_sets"][0]["id"],
                "expected_count": 2,
                "allow_shared_regions_for_repair": True,
                "items": [
                    {"id": "item-001", "label": "red", "regions": [region], "visual_assessment": assessment},
                    {"id": "item-002", "label": "blue", "regions": [region], "visual_assessment": assessment},
                ],
            }
            result = core.apply_plan(source, scan["scan_path"], plan, root / "result", False)
            manifest = route_manifest(result["manifest_path"])
            self.assertEqual(manifest["status"], "awaiting_user_approval")
            self.assertEqual(manifest["conflict_groups"][0]["layout"]["count"], 2)

    def test_unapproved_ingest_is_rejected_and_failed_attempts_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "clipped.png"
            image = Image.new("RGB", (220, 160), "white")
            ImageDraw.Draw(image).rectangle((0, 30, 80, 130), fill="purple")
            image.save(source)
            _, manifest_path = apply_repair_eligible(source, root)
            prepare_repair(manifest_path)
            invalid = root / "invalid.png"
            Image.new("RGB", (512, 512), "white").save(invalid)
            with self.assertRaises(ValueError):
                ingest_repair(manifest_path, "conflict-001", invalid)
            approve_repair(manifest_path, "conflict-001")
            first = ingest_repair(manifest_path, "conflict-001", invalid)
            self.assertEqual(first["status"], "needs_review")
            second = ingest_repair(manifest_path, "conflict-001", invalid)
            self.assertEqual(second["status"], "retry_exhausted")
            with self.assertRaises(ValueError):
                ingest_repair(manifest_path, "conflict-001", invalid)

    def test_valid_repair_requires_visual_verdict_then_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "clipped.png"
            image = Image.new("RGB", (220, 160), "white")
            ImageDraw.Draw(image).rectangle((0, 30, 80, 130), fill="purple")
            image.save(source)
            _, manifest_path = apply_repair_eligible(source, root)
            prepare_repair(manifest_path)
            approve_repair(manifest_path, "conflict-001")
            grid = root / "valid.png"
            generated = Image.new("RGB", (512, 512), "white")
            ImageDraw.Draw(generated).ellipse((110, 95, 402, 410), fill="purple")
            generated.save(grid)
            ingested = ingest_repair(manifest_path, "conflict-001", grid)
            self.assertEqual(ingested["status"], "needs_review")
            self.assertEqual(ingested["delivery"]["pending_repair_images"], [])
            self.assertEqual(
                ingested["delivery"]["contact_sheet_layout"]["style"],
                "compact_cards_v1",
            )
            final = evaluate_manifest(manifest_path, "pass")
            self.assertEqual(final["status"], "success")
            self.assertIn("reconstructed", final["items"][0]["image_path"])


if __name__ == "__main__":
    unittest.main()
