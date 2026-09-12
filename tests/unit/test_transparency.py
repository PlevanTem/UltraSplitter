from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from ultrasplitter.transparency import (
    apply_transparent_verdict,
    inspect_transparent_candidate,
    prepare_transparent_candidate,
)


class TransparencyTests(unittest.TestCase):
    def test_opaque_image_is_not_an_eligible_transparent_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "opaque.png"
            Image.new("RGB", (160, 160), "white").save(path)
            result = inspect_transparent_candidate(path)
            self.assertFalse(result["passed"])
            self.assertIn("missing_alpha_channel", result["issues"])
            self.assertIn("no_transparent_background", result["issues"])

    def test_safe_transparent_candidate_passes_automatic_checks(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "safe.png"
            image = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
            ImageDraw.Draw(image).ellipse((45, 35, 155, 165), fill="#eeeeee")
            image.save(path)
            result = inspect_transparent_candidate(path)
            self.assertTrue(result["passed"])
            self.assertGreaterEqual(result["metrics"]["safe_margin_ratio"], 0.08)

    def test_edge_contact_blocks_transparent_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "edge.png"
            image = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
            ImageDraw.Draw(image).rectangle((0, 30, 90, 130), fill="orange")
            image.save(path)
            result = inspect_transparent_candidate(path)
            self.assertFalse(result["passed"])
            self.assertIn("foreground_touches_canvas_edge", result["issues"])

    def test_candidate_padding_preserves_subject_pixels_and_meets_margin(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            source_path = Path(folder) / "source.png"
            output_path = Path(folder) / "candidate.png"
            source = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
            ImageDraw.Draw(source).rectangle((0, 10, 90, 90), fill=(255, 80, 20, 255))
            source.save(source_path)

            prepare_transparent_candidate(source_path, output_path)

            with Image.open(output_path) as opened:
                candidate = opened.convert("RGBA")
            source_bbox = source.getchannel("A").getbbox()
            candidate_bbox = candidate.getchannel("A").getbbox()
            source_subject = source.crop(source_bbox)
            candidate_subject = candidate.crop(candidate_bbox)
            self.assertEqual(candidate_subject.size, source_subject.size)
            self.assertEqual(candidate_subject.tobytes(), source_subject.tobytes())
            self.assertTrue(inspect_transparent_candidate(output_path)["passed"])

    def test_visual_pass_cannot_override_failed_automatic_checks(self) -> None:
        candidate = str((Path.cwd() / "candidate.png").resolve())
        manifest = {
            "status": "success",
            "delivery": {
                "transparent_candidates": [candidate],
                "transparent_images": [],
            },
            "items": [
                {
                    "deliverable": True,
                    "variants": {
                        "transparent_candidate": candidate,
                        "transparent": None,
                    },
                }
            ],
            "evaluation": {
                "transparent": {
                    "status": "needs_review",
                    "visual": "not_run",
                    "automatic": {"passed": False},
                }
            },
        }

        apply_transparent_verdict(manifest, "pass")

        self.assertEqual(manifest["evaluation"]["transparent"]["status"], "retryable")
        self.assertEqual(
            manifest["evaluation"]["transparent"]["visual"],
            "pass_rejected_by_automatic_checks",
        )
        self.assertEqual(manifest["delivery"]["transparent_images"], [])
        self.assertIsNone(manifest["items"][0]["variants"]["transparent"])


if __name__ == "__main__":
    unittest.main()
