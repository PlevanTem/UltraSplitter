"""Prepare lightweight display previews from the tracked showcase contact sheets.

These are website illustrations, not primary delivery assets. The rectangles follow
the contact-sheet renderer's exact geometry; no subjects are generated or repaired.
The idol PNGs are the previously reviewed alpha variants, copied without changes.
"""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ultrasplitter.presentation import choose_grid, isolate_subject


def main() -> None:
    destination = ROOT / "docs/assets/showcase"
    destination.mkdir(parents=True, exist_ok=True)
    for name, count in (("uneven", 4), ("dense", 11), ("clipped", 5)):
        with Image.open(ROOT / f"docs/assets/case-{name}-output.png") as sheet:
            rows, columns = choose_grid(count)
            width = (sheet.width - 48 - (columns - 1) * 16) // columns
            height = (sheet.height - 48 - (rows - 1) * 16) // rows
            label_height = max(44, round(height * 0.15))
            with TemporaryDirectory(dir=ROOT / "output") as temporary:
                for index in range(count):
                    row, column = divmod(index, columns)
                    left = 24 + column * (width + 16)
                    top = 24 + row * (height + 16)
                    # Exclude card labels, dividers, frames, and shadows.
                    region = sheet.crop((left + 12, top + label_height + 8,
                                         left + width - 12, top + height - 12))
                    source = Path(temporary) / "subject.png"
                    region.save(source)
                    preview = isolate_subject(source)
                    preview.thumbnail((420, 420), Image.Resampling.LANCZOS)
                    preview.save(destination / f"{name}-{index + 1:02d}.png", optimize=True)
        print(f"{name}: {count} display previews")


if __name__ == "__main__":
    main()
