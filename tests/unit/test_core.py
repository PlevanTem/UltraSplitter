from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from ultrasplitter import core
from ultrasplitter.router import route_manifest


class CoreTests(unittest.TestCase):
    def test_detects_irregular_framed_panels_and_excludes_captions(self) -> None:
        image = Image.new("RGB", (800, 360), "white")
        draw = ImageDraw.Draw(image)
        frames = [(12, 190), (204, 398), (413, 611), (625, 790)]
        for index, (left, right) in enumerate(frames):
            draw.rectangle((left, 12, right, 300), outline="black", width=3)
            center = (left + right) // 2
            draw.rectangle((center - 24, 55, center + 24, 270), fill=(30 + index * 45, 60, 120))
            draw.text((left + 8, 325), f"caption {index + 1}", fill="black")
        candidate = core.panel_candidate(image.convert("RGBA"), 1000)
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(len(candidate["regions"]), 4)
        self.assertTrue(all(region["bbox"][3] <= 300 for region in candidate["regions"]))

    def test_agent_plan_groups_disconnected_components_and_delivers_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "objects.png"
            image = Image.new("RGB", (420, 240), "white")
            draw = ImageDraw.Draw(image)
            draw.rectangle((30, 45, 105, 190), fill="red")
            draw.ellipse((155, 60, 245, 170), fill="blue")
            draw.rectangle((320, 45, 355, 100), fill="green")
            draw.rectangle((325, 135, 365, 195), fill="green")
            image.save(source)
            scan_result = core.scan_image(source, root / "scan", "objects", None, 32, 0.0005, 1000, False)
            candidate = scan_result["scan"]["candidate_sets"][0]
            green = [region["id"] for region in candidate["regions"] if region["bbox"][0] >= 300]
            others = [region["id"] for region in candidate["regions"] if region["bbox"][0] < 300]
            plan = {
                "schema_version": 3,
                "mode": "objects",
                "candidate_set": candidate["id"],
                "expected_count": 3,
                "padding": 0.03,
                "emit": "auto",
                "items": [
                    {"id": "item-001", "label": "red", "regions": [others[0]]},
                    {"id": "item-002", "label": "blue", "regions": [others[1]]},
                    {"id": "item-003", "label": "green-parts", "regions": green},
                ],
            }
            result = core.apply_plan(source, scan_result["scan_path"], plan, root / "result", False)
            manifest = route_manifest(result["manifest_path"])
            self.assertEqual(manifest["actual_count"], 3)
            self.assertEqual(manifest["status"], "success")
            self.assertTrue(all(Path(path).is_absolute() for path in manifest["delivery"]["images"]))

    def test_scan_is_schema_v3_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "simple.png"
            image = Image.new("RGB", (160, 100), "white")
            ImageDraw.Draw(image).ellipse((30, 20, 100, 85), fill="orange")
            image.save(source)
            result = core.scan_image(source, root / "scan", "objects", None, 32, 0.0005, 1000, False)
            parsed = json.loads(result["scan_path"].read_text(encoding="utf-8"))
            self.assertEqual(parsed["schema_version"], 3)


if __name__ == "__main__":
    unittest.main()
