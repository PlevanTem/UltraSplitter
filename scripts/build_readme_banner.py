"""Build a small ASCII motion graphic and local navigation badges for README."""

from pathlib import Path
from html import escape
import math

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
BG, INK, MUTED, ACCENT = "#f6f7f9", "#202630", "#697582", "#247c72"


def font(size):
    for path in (
        "C:/Windows/Fonts/consola.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def frame(progress):
    im = Image.new("RGB", (1120, 320), BG)
    d = ImageDraw.Draw(im)
    d.text((38, 27), "[ UltraSplitter ]", font=font(34), fill=INK)
    d.text((40, 80), "One generated sheet. Assets ready for your next step.", font=font(18), fill=MUTED)
    d.line((40, 117, 1080, 117), fill="#dce1e6")
    for row, line in enumerate(("+------------------+", "|  /\\     [##]     |", "| /__\\         <>  |", "|       { asset }  |", "+------------------+")):
        d.text((58, 146 + row * 23), line, font=font(20), fill=INK)
    d.text((370, 188), "---", font=font(22), fill=MUTED)
    d.text((420, 188), ">", font=font(22), fill=ACCENT)
    d.text((470, 153), "[ locate ]", font=font(20), fill=INK)
    d.text((470, 186), "[ review ]", font=font(20), fill=INK)
    d.text((470, 219), "[ export ]", font=font(20), fill=INK)
    stage = min(2, int(progress * 3))
    d.text((450, 153 + stage * 33), ">", font=font(20), fill=ACCENT)
    d.text((630, 188), "---->", font=font(22), fill=MUTED)
    symbols = (" /\\\n/__\\", "[##]", "<>", "{ asset }")
    for i, symbol in enumerate(symbols):
        x, y = 744 + (i % 2) * 165, 143 + (i // 2) * 62
        d.rounded_rectangle((x, y, x + 145, y + 52), radius=7, fill="white", outline="#dce1e6")
        asset_font = font(16 if i in (0, 3) else 20)
        bounds = d.multiline_textbbox((0, 0), symbol, font=asset_font, spacing=0)
        tx = x + (145 - (bounds[2] - bounds[0])) / 2 - bounds[0]
        ty = y + (52 - (bounds[3] - bounds[1])) / 2 - bounds[1]
        d.multiline_text((tx, ty), symbol, font=asset_font, spacing=0, fill=ACCENT if progress > i / 5 else MUTED)
    scan_x = 65 + round((1 - math.cos(progress * math.pi * 2)) * 104)
    d.line((scan_x, 171, scan_x, 235), fill=ACCENT, width=2)
    d.text((40, 286), "UI / GAME / ARCHITECTURE", font=font(14), fill=MUTED)
    d.text((795, 286), "workflow illustration", font=font(14), fill=MUTED)
    return im


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    frames = [frame(i / 39) for i in range(40)]
    frames[-1].save(ASSETS / "banner-static.png", optimize=True)
    frames[0].save(ASSETS / "banner.gif", save_all=True, append_images=frames[1:], duration=150, loop=0, optimize=True)
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
