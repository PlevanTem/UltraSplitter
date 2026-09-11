#!/usr/bin/env python3
"""Generate redistributable synthetic fixtures; no external assets are used."""

from __future__ import annotations

from pathlib import Path
import random

from PIL import Image, ImageDraw


ROOT = Path(__file__).parents[1] / "tests" / "fixtures" / "generated"


def save(name: str, image: Image.Image) -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    image.save(ROOT / name, format="PNG", optimize=True)


def irregular_panels() -> None:
    image = Image.new("RGB", (900, 420), "white")
    draw = ImageDraw.Draw(image)
    frames = [(18, 190), (210, 430), (452, 650), (670, 884)]
    for index, (left, right) in enumerate(frames):
        draw.rectangle((left, 16, right, 350), outline="#202020", width=4)
        center = (left + right) // 2
        draw.ellipse((center - 42, 65, center + 42, 150), fill=(40 + index * 40, 80, 170))
        draw.rectangle((center - 34, 150, center + 34, 315), fill=(40 + index * 40, 80, 170))
        draw.text((left + 16, 375), f"panel {index + 1}", fill="#202020")
    save("p0-irregular-panels.png", image)


def scattered_objects() -> None:
    image = Image.new("RGB", (760, 460), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((32, 40, 165, 210), fill="#e74c3c")
    draw.rounded_rectangle((260, 20, 430, 150), radius=24, fill="#3498db")
    draw.polygon([(560, 40), (710, 190), (500, 220)], fill="#2ecc71")
    draw.rectangle((95, 300, 210, 430), fill="#9b59b6")
    draw.ellipse((390, 270, 700, 420), fill="#f39c12")
    save("p0-scattered-objects.png", image)


def bbox_overlap_disjoint() -> None:
    image = Image.new("RGB", (300, 270), "white")
    draw = ImageDraw.Draw(image)
    draw.line([(35, 35), (35, 220), (170, 220)], fill="#d62728", width=24, joint="curve")
    draw.line([(100, 75), (255, 75), (255, 245)], fill="#1f77b4", width=24, joint="curve")
    save("p0-bbox-overlap-disjoint.png", image)


def touching_and_occluded() -> None:
    touching = Image.new("RGB", (360, 240), "white")
    draw = ImageDraw.Draw(touching)
    draw.ellipse((35, 45, 190, 200), fill="#e74c3c")
    draw.rectangle((190, 70, 325, 190), fill="#3498db")
    save("p0-touching-subjects.png", touching)

    occluded = Image.new("RGB", (360, 240), "white")
    draw = ImageDraw.Draw(occluded)
    draw.ellipse((45, 35, 255, 215), fill="#2ecc71")
    draw.rounded_rectangle((155, 20, 330, 225), radius=32, fill="#8e44ad")
    save("p0-occluded-subjects.png", occluded)


def edge_clipped() -> None:
    image = Image.new("RGB", (420, 300), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((-45, 75, 75, 195), fill="#e74c3c")
    draw.rectangle((165, -35, 255, 75), fill="#3498db")
    draw.polygon([(345, 110), (440, 55), (440, 210)], fill="#2ecc71")
    draw.ellipse((170, 245, 285, 355), fill="#f39c12")
    save("p0-edge-clipped-four-sides.png", image)


def repair_grids() -> None:
    valid = Image.new("RGB", (1024, 1024), "white")
    draw = ImageDraw.Draw(valid)
    draw.ellipse((110, 105, 405, 405), fill="#e74c3c")
    draw.rounded_rectangle((630, 110, 910, 400), radius=45, fill="#3498db")
    draw.polygon([(255, 620), (420, 900), (90, 900)], fill="#2ecc71")
    draw.rectangle((640, 640, 900, 900), fill="#f39c12")
    save("p0-valid-repair-grid-2x2.png", valid)

    invalid = Image.new("RGB", (1024, 1024), "white")
    pixels = invalid.load()
    for y in range(invalid.height):
        tone = 245 - round(y * 20 / invalid.height)
        for x in range(invalid.width):
            pixels[x, y] = (255, tone, tone)
    draw = ImageDraw.Draw(invalid)
    draw.ellipse((110, 105, 405, 405), fill="#e74c3c")
    draw.ellipse((620, 105, 915, 405), fill="#e74c3c")
    draw.rectangle((400, 650, 620, 930), fill="#3498db")
    save("p0-invalid-repair-grid-2x2.png", invalid)


def p1_cases() -> None:
    transparent = Image.new("RGBA", (320, 240), (0, 0, 0, 0))
    draw = ImageDraw.Draw(transparent)
    draw.ellipse((45, 35, 270, 215), fill=(30, 150, 220, 90), outline=(20, 90, 160, 220), width=8)
    save("p1-transparent-subject.png", transparent)

    shadow = Image.new("RGB", (420, 280), "white")
    draw = ImageDraw.Draw(shadow)
    draw.ellipse((90, 210, 330, 255), fill="#dddddd")
    draw.rounded_rectangle((150, 40, 270, 225), radius=30, fill="#795548")
    save("p1-detached-shadow.png", shadow)

    disconnected = Image.new("RGB", (420, 280), "white")
    draw = ImageDraw.Draw(disconnected)
    draw.rectangle((90, 55, 190, 230), fill="#4caf50")
    draw.polygon([(250, 70), (330, 140), (250, 210)], fill="#4caf50")
    save("p1-disconnected-one-subject.png", disconnected)

    gradient = Image.new("RGB", (420, 280))
    pixels = gradient.load()
    for y in range(gradient.height):
        for x in range(gradient.width):
            pixels[x, y] = (230 - x // 10, 235 - y // 12, 245)
    ImageDraw.Draw(gradient).ellipse((125, 55, 300, 235), fill="#e91e63")
    save("p1-gradient-background.png", gradient)

    dense = Image.new("RGB", (1000, 650), "white")
    draw = ImageDraw.Draw(dense)
    rng = random.Random(20260911)
    for row in range(6):
        for column in range(10):
            x = 22 + column * 96 + rng.randint(-12, 12)
            y = 18 + row * 102 + rng.randint(-10, 10)
            width = rng.randint(35, 70)
            height = rng.randint(45, 85)
            color = (rng.randint(35, 220), rng.randint(35, 220), rng.randint(35, 220))
            draw.rounded_rectangle((x, y, x + width, y + height), radius=10, fill=color)
    save("p1-dense-60-subjects.png", dense)

    noise = Image.new("RGB", (480, 320), "white")
    draw = ImageDraw.Draw(noise)
    draw.ellipse((130, 55, 355, 280), fill="#673ab7")
    for _ in range(90):
        x, y = rng.randrange(480), rng.randrange(320)
        draw.point((x, y), fill=(rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    save("p1-small-noise.png", noise)

    source = Image.new("RGB", (320, 320), "white")
    draw = ImageDraw.Draw(source)
    draw.rounded_rectangle((70, 45, 250, 275), radius=35, fill="#263238")
    draw.ellipse((125, 90, 155, 120), fill="#ffc107")
    draw.ellipse((170, 90, 200, 120), fill="#ffc107")
    draw.rectangle((125, 190, 200, 210), fill="#00bcd4")
    save("p1-identity-source.png", source)
    drift = source.copy()
    draw = ImageDraw.Draw(drift)
    draw.rectangle((125, 190, 200, 210), fill="#ff5722")
    draw.polygon([(160, 135), (205, 170), (115, 170)], fill="#e91e63")
    save("p1-identity-drift.png", drift)


def main() -> None:
    irregular_panels()
    scattered_objects()
    bbox_overlap_disjoint()
    touching_and_occluded()
    edge_clipped()
    repair_grids()
    p1_cases()
    print(f"generated fixtures in {ROOT.resolve()}")


if __name__ == "__main__":
    main()
