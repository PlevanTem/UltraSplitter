from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from ultrasplitter.presentation import choose_grid, isolate_subject, render_contact_sheet


class PresentationTests(unittest.TestCase):
    def test_grid_is_compact_and_bounded(self) -> None:
        self.assertEqual(choose_grid(1), (1, 1))
        self.assertEqual(choose_grid(4), (2, 2))
        self.assertEqual(choose_grid(11), (3, 4))
        self.assertEqual(choose_grid(74), (10, 8))

    def test_uniform_background_is_trimmed_for_preview(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "subject.png"
            image = Image.new("RGB", (240, 160), "white")
            ImageDraw.Draw(image).rectangle((92, 25, 148, 135), fill="#285f9e")
            image.save(path)
            isolated = isolate_subject(path)
            self.assertLess(isolated.width, image.width)
            self.assertLess(isolated.height, image.height)
            self.assertLess(isolated.getchannel("A").getextrema()[0], 255)

    def test_nonuniform_edge_is_not_invented_as_transparency(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "edge-filled.png"
            image = Image.new("RGB", (120, 80), "#335577")
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, 40, 79), fill="#cc6633")
            draw.rectangle((80, 0, 119, 79), fill="#55aa77")
            image.save(path)
            isolated = isolate_subject(path)
            self.assertEqual(isolated.size, image.size)
            self.assertEqual(isolated.getchannel("A").getextrema(), (255, 255))

    def test_contact_sheet_uses_cards_and_reports_layout(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            items = []
            original_bytes = {}
            for index, size in enumerate(((220, 120), (120, 220), (300, 90), (90, 300)), 1):
                path = root / f"asset-{index}.png"
                image = Image.new("RGBA", size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(image)
                draw.rounded_rectangle((5, 5, size[0] - 6, size[1] - 6), radius=8, fill="#247c72")
                image.save(path)
                items.append({"label": f"asset {index}", "image_path": str(path)})
                original_bytes[path] = path.read_bytes()

            output = root / "contact-sheet.png"
            metadata = render_contact_sheet(items, output)
            self.assertEqual(metadata["rows"], 2)
            self.assertEqual(metadata["columns"], 2)
            self.assertEqual(metadata["count"], 4)
            self.assertEqual(metadata["style"], "compact_cards_v1")
            self.assertEqual(metadata["subject_scale"], "longest_edge_normalized")
            self.assertEqual(metadata["canvas"], [704, 744])
            self.assertTrue(all(path.read_bytes() == content for path, content in original_bytes.items()))
            with Image.open(output) as rendered:
                self.assertEqual(rendered.size, (704, 744))
                self.assertEqual(rendered.getpixel((0, 0)), (238, 242, 247))
                self.assertEqual(rendered.getpixel((300, 50)), (255, 255, 255))

    def test_empty_sheet_remains_accessible(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "empty.png"
            metadata = render_contact_sheet([], output)
            self.assertEqual(metadata["count"], 0)
            self.assertEqual(metadata["canvas"], [640, 180])
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
