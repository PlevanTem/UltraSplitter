"""Build an intuitive illustrated workflow banner and README navigation badges."""

from html import escape
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
BG = "#f4f7fb"
INK = "#152238"
MUTED = "#607089"
LINE = "#d9e2ec"
WHITE = "#ffffff"
TEAL = "#0f8b7c"
BLUE = "#3977e3"
ORANGE = "#ed8a3a"
PURPLE = "#7b61d1"
GREEN = "#2b9a66"


def font(size: int, bold: bool = False):
    windows = "C:/Windows/Fonts/consolab.ttf" if bold else "C:/Windows/Fonts/consola.ttf"
    linux = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    )
    for path in (windows, linux):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def centered_text(draw: ImageDraw.ImageDraw, box, text: str, face, fill: str) -> None:
    bounds = draw.textbbox((0, 0), text, font=face)
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    x = box[0] + (box[2] - box[0] - width) / 2 - bounds[0]
    y = box[1] + (box[3] - box[1] - height) / 2 - bounds[1]
    draw.text((x, y), text, font=face, fill=fill)


def sparkle(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color: str) -> None:
    draw.polygon(
        [
            (x, y - size),
            (x + 3, y - 3),
            (x + size, y),
            (x + 3, y + 3),
            (x, y + size),
            (x - 3, y + 3),
            (x - size, y),
            (x - 3, y - 3),
        ],
        fill=color,
    )


def check(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.ellipse((x - 11, y - 11, x + 11, y + 11), fill="#e5f6ee", outline=GREEN, width=2)
    draw.line((x - 5, y, x - 1, y + 5, x + 6, y - 5), fill=GREEN, width=3, joint="curve")


def character(draw: ImageDraw.ImageDraw, box, color: str = ORANGE) -> None:
    x1, y1, x2, y2 = box
    cx = (x1 + x2) // 2
    head = max(5, (x2 - x1) // 8)
    draw.ellipse((cx - head, y1, cx + head, y1 + head * 2), fill="#ffd6b8", outline=INK, width=2)
    shoulder = y1 + head * 2 + 3
    draw.polygon([(cx, shoulder), (x1 + 5, y2 - 12), (x2 - 5, y2 - 12)], fill=color, outline=INK)
    draw.line((x1 + 8, shoulder + 8, x1, y2 - 4), fill=INK, width=3)
    draw.line((x2 - 8, shoulder + 8, x2, y2 - 4), fill=INK, width=3)
    draw.line((cx - 5, y2 - 12, cx - 8, y2), fill=INK, width=3)
    draw.line((cx + 5, y2 - 12, cx + 8, y2), fill=INK, width=3)


def sword(draw: ImageDraw.ImageDraw, box, color: str = BLUE) -> None:
    x1, y1, x2, y2 = box
    cx = (x1 + x2) // 2
    draw.polygon(
        [(cx, y1), (cx + 7, y1 + 12), (cx + 4, y2 - 17), (cx - 4, y2 - 17), (cx - 7, y1 + 12)],
        fill="#dbe7f5",
        outline=INK,
    )
    draw.line((cx - 16, y2 - 17, cx + 16, y2 - 17), fill=color, width=5)
    draw.rectangle((cx - 4, y2 - 17, cx + 4, y2 - 3), fill=color, outline=INK)
    draw.ellipse((cx - 6, y2 - 6, cx + 6, y2 + 4), fill=ORANGE, outline=INK)


def building(draw: ImageDraw.ImageDraw, box, color: str = PURPLE) -> None:
    x1, y1, x2, y2 = box
    center = (x1 + x2) // 2
    draw.polygon(
        [(center, y1), (x2, y1 + 14), (x2 - 5, y1 + 14), (x2 - 5, y2), (x1 + 5, y2), (x1 + 5, y1 + 14), (x1, y1 + 14)],
        fill="#ede9fb",
        outline=INK,
    )
    for column in range(3):
        for row in range(2):
            wx = x1 + 12 + column * 15
            wy = y1 + 20 + row * 16
            draw.rectangle((wx, wy, wx + 7, wy + 8), fill=color)
    draw.rectangle((center - 5, y2 - 15, center + 5, y2), fill=color)


def ui_tile(draw: ImageDraw.ImageDraw, box, color: str = TEAL) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=9, fill="#e4f5f2", outline=color, width=2)
    sparkle(draw, (x1 + x2) // 2, (y1 + y2) // 2, 16, color)


def asset_icon(draw: ImageDraw.ImageDraw, kind: int, box) -> None:
    if kind == 0:
        character(draw, box)
    elif kind == 1:
        sword(draw, box)
    elif kind == 2:
        building(draw, box)
    else:
        ui_tile(draw, box)


def arrow(draw: ImageDraw.ImageDraw, start: int, end: int, y: int, progress: float) -> None:
    draw.line((start, y, end, y), fill="#aab8ca", width=4)
    draw.polygon([(end, y), (end - 13, y - 9), (end - 13, y + 9)], fill="#aab8ca")
    dot_x = start + round((end - start) * progress)
    draw.ellipse((dot_x - 6, y - 6, dot_x + 6, y + 6), fill=TEAL)


def frame(progress: float) -> Image.Image:
    image = Image.new("RGB", (1200, 360), BG)
    draw = ImageDraw.Draw(image)
    label_font = font(15, bold=True)
    body_font = font(13)

    draw.text((34, 20), "[ UltraSplitter ]", font=font(28, bold=True), fill=INK)
    draw.text((339, 26), "one generated image  ->  usable individual assets", font=font(17), fill=MUTED)
    sparkle(draw, 1160, 35, 12, ORANGE)

    panels = [(34, 76, 356, 324), (438, 76, 762, 324), (844, 76, 1166, 324)]
    for panel in panels:
        draw.rounded_rectangle(panel, radius=16, fill=WHITE, outline=LINE, width=2)

    draw.rounded_rectangle((52, 92, 338, 126), radius=8, fill="#fff3e8")
    draw.text((66, 101), "1  AIGC ASSET SHEET", font=label_font, fill=ORANGE)
    draw.text((66, 136), "many ideas locked in one image", font=body_font, fill=MUTED)
    source_cards = [(68, 178, 125, 258), (139, 178, 196, 258), (210, 178, 267, 258), (279, 188, 327, 246)]
    for index, card in enumerate(source_cards):
        draw.rounded_rectangle((card[0] - 5, card[1] - 5, card[2] + 5, card[3] + 5), radius=8, fill="#f7f9fc", outline="#cbd6e3")
        asset_icon(draw, index, card)
    draw.text((66, 282), "uneven spacing  +  mixed sizes", font=body_font, fill=INK)
    scan_x = 60 + round((1 - math.cos(progress * math.pi * 2)) * 135)
    draw.line((scan_x, 169, scan_x, 271), fill=TEAL, width=3)

    draw.rounded_rectangle((456, 92, 744, 126), radius=8, fill="#eaf2ff")
    draw.text((470, 101), "2  AI FINDS + REVIEWS", font=label_font, fill=BLUE)
    draw.text((470, 136), "detect each subject and its condition", font=body_font, fill=MUTED)
    draw.ellipse((531, 169, 669, 235), fill="#f1f6ff", outline=BLUE, width=3)
    draw.ellipse((573, 179, 627, 233), fill=WHITE, outline=BLUE, width=3)
    pulse = 10 + round(4 * math.sin(progress * math.pi * 2) ** 2)
    draw.ellipse((600 - pulse, 206 - pulse, 600 + pulse, 206 + pulse), fill=BLUE)
    draw.rounded_rectangle((474, 255, 550, 292), radius=10, fill="#e5f6ee")
    draw.rounded_rectangle((562, 255, 638, 292), radius=10, fill="#fff2df")
    draw.rounded_rectangle((650, 255, 726, 292), radius=10, fill="#f0edf9")
    centered_text(draw, (474, 255, 550, 292), "KEEP", body_font, GREEN)
    centered_text(draw, (562, 255, 638, 292), "REPAIR", body_font, ORANGE)
    centered_text(draw, (650, 255, 726, 292), "IGNORE", body_font, PURPLE)
    draw.text((510, 302), "user approves repair", font=body_font, fill=INK)

    draw.rounded_rectangle((862, 92, 1148, 126), radius=8, fill="#e5f6ee")
    draw.text((876, 101), "3  INDIVIDUAL FILES", font=label_font, fill=GREEN)
    draw.text((876, 136), "clean, named, ready to use", font=body_font, fill=MUTED)
    output_cards = [(866, 170, 991, 234), (1011, 170, 1136, 234), (866, 248, 991, 312), (1011, 248, 1136, 312)]
    visible_count = min(4, 1 + int(progress * 4.5))
    for index, card in enumerate(output_cards):
        draw.rounded_rectangle(card, radius=10, fill="#f7fafc", outline="#cbd6e3")
        if index < visible_count:
            icon_box = (card[0] + 18, card[1] + 9, card[0] + 62, card[3] - 9)
            asset_icon(draw, index, icon_box)
            draw.text((card[0] + 70, card[1] + 30), f"{index + 1:02d}.png", font=font(11, bold=True), fill=INK)
            check(draw, card[2] - 15, card[1] + 15)

    arrow(draw, 372, 420, 203, progress)
    arrow(draw, 778, 826, 203, progress)
    return image


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    frames = [frame(index / 39) for index in range(40)]
    frames[-1].save(ASSETS / "banner-static.png", optimize=True)
    frames[0].save(
        ASSETS / "banner.gif",
        save_all=True,
        append_images=frames[1:],
        duration=150,
        loop=0,
        optimize=True,
    )
    for name, symbol, label in (
        ("quickstart", ">_", "Quickstart"),
        ("showcases", "[]", "Showcases"),
        ("releases", "v", "Releases"),
        ("issues", "?", "Feedback"),
        ("support", "+", "Consult / Sponsor"),
    ):
        width = 54 + len(label) * 7
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="28" role="img" aria-label="{escape(label)}">
<rect x=".5" y=".5" width="{width-1}" height="27" rx="5" fill="#f6f7f9" stroke="#dce1e6"/>
<text x="11" y="18" font-family="monospace" font-size="12" fill="#247c72">{escape(symbol)}</text>
<text x="36" y="18" font-family="Arial,sans-serif" font-size="12" fill="#202630">{escape(label)}</text>
</svg>'''
        (ASSETS / f"nav-{name}.svg").write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    main()
