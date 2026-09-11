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
            manifest, manifest_path = apply_auto(source, root)
            self.assertEqual(manifest["status"], "awaiting_user_approval")
            self.assertEqual(manifest["items"][0]["route"], "generated_reconstruction")
            packet = prepare_repair(manifest_path)
            self.assertEqual(packet["status"], "awaiting_user_approval")
            self.assertTrue(Path(packet["requests"][0]["source"]).is_file())
            self.assertTrue(Path(packet["requests"][0]["target_map"]).is_file())

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
            _, manifest_path = apply_auto(source, root)
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
            _, manifest_path = apply_auto(source, root)
            prepare_repair(manifest_path)
            approve_repair(manifest_path, "conflict-001")
            grid = root / "valid.png"
            generated = Image.new("RGB", (512, 512), "white")
            ImageDraw.Draw(generated).ellipse((110, 95, 402, 410), fill="purple")
            generated.save(grid)
            ingested = ingest_repair(manifest_path, "conflict-001", grid)
            self.assertEqual(ingested["status"], "needs_review")
            final = evaluate_manifest(manifest_path, "pass")
            self.assertEqual(final["status"], "success")
            self.assertIn("reconstructed", final["items"][0]["image_path"])


if __name__ == "__main__":
    unittest.main()
