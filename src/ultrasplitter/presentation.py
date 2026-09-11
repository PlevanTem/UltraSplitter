"""Production contact-sheet rendering for delivered and review assets."""

from __future__ import annotations

import math
from pathlib import Path
from statistics import median
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


CANVAS_BACKGROUND = "#eef2f7"
CARD_BACKGROUND = "#ffffff"
CARD_BORDER = "#d8dee8"
CARD_SHADOW = "#d9e0e9"
TEXT_COLOR = "#1d2735"
DIVIDER_COLOR = "#edf0f4"
DEFAULT_CARD_SIZE = (320, 340)
DEFAULT_OUTER_MARGIN = 24
DEFAULT_GAP = 16
MAX_COLUMNS = 8


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = [
        "C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in names:
        if Path(name).is_file():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def choose_grid(count: int, max_columns: int = MAX_COLUMNS) -> tuple[int, int]:
    """Return a compact near-square row/column layout in row-major order."""
    if count < 1:
        return 0, 0
    columns = min(max_columns, max(1, math.ceil(math.sqrt(count))))
    rows = math.ceil(count / columns)
    return rows, columns


def _corner_background(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    points = [
        rgb.getpixel((0, 0)),
        rgb.getpixel((rgb.width - 1, 0)),
        rgb.getpixel((0, rgb.height - 1)),
        rgb.getpixel((rgb.width - 1, rgb.height - 1)),
    ]
    return tuple(int(median(point[channel] for point in points)) for channel in range(3))


def _color_distance(first: tuple[int, ...], second: tuple[int, ...]) -> int:
    return max(abs(int(first[index]) - int(second[index])) for index in range(3))


def _can_remove_opaque_background(image: Image.Image, background: tuple[int, int, int], tolerance: int) -> bool:
    rgb = image.convert("RGB")
    corners = [
        rgb.getpixel((0, 0)),
        rgb.getpixel((rgb.width - 1, 0)),
        rgb.getpixel((0, rgb.height - 1)),
        rgb.getpixel((rgb.width - 1, rgb.height - 1)),
    ]
    if max(_color_distance(corner, background) for corner in corners) > tolerance:
        return False
    border = (
        [rgb.getpixel((x, 0)) for x in range(rgb.width)]
        + [rgb.getpixel((x, rgb.height - 1)) for x in range(rgb.width)]
        + [rgb.getpixel((0, y)) for y in range(rgb.height)]
        + [rgb.getpixel((rgb.width - 1, y)) for y in range(rgb.height)]
    )
    matching = sum(_color_distance(pixel, background) <= tolerance for pixel in border)
    return matching / max(1, len(border)) >= 0.6


def isolate_subject(path: Path, tolerance: int = 18) -> Image.Image:
    """Trim transparent or confidently uniform background for preview use only."""
    with Image.open(path) as opened:
        rgba = opened.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] >= 250:
        rgb = rgba.convert("RGB")
        background = _corner_background(rgb)
        if _can_remove_opaque_background(rgb, background, tolerance):
            flat = Image.new("RGB", rgb.size, background)
            difference = ImageChops.difference(rgb, flat)
            red, green, blue = difference.split()
            mask = ImageChops.lighter(ImageChops.lighter(red, green), blue)
            mask = mask.point(lambda value: 255 if value > tolerance else 0)
            mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.6))
            bbox = mask.getbbox()
            foreground_ratio = sum(mask.histogram()[1:]) / max(1, mask.width * mask.height)
            if bbox is not None and 0.001 <= foreground_ratio <= 0.95:
                rgba.putalpha(mask)
                alpha = mask
    bbox = alpha.getbbox()
    if bbox is None:
        return rgba
    padding = max(2, round(max(rgba.size) * 0.008))
    return rgba.crop(
        (
            max(0, bbox[0] - padding),
            max(0, bbox[1] - padding),
            min(rgba.width, bbox[2] + padding),
            min(rgba.height, bbox[3] + padding),
        )
    )


def _fit_label(draw: ImageDraw.ImageDraw, value: str, font: ImageFont.ImageFont, max_width: int) -> str:
    if draw.textbbox((0, 0), value, font=font)[2] <= max_width:
        return value
    suffix = "…"
    shortened = value
    while shortened and draw.textbbox((0, 0), shortened + suffix, font=font)[2] > max_width:
        shortened = shortened[:-1]
    return shortened + suffix if shortened else suffix


def render_contact_sheet(
    items: list[dict[str, Any]],
    output_path: Path,
    *,
    canvas_size: tuple[int, int] | None = None,
    empty_message: str = "No deliverable assets yet",
) -> dict[str, Any]:
    """Render accessible cards without modifying any delivered source image."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not items:
        width, height = canvas_size or (640, 180)
        canvas = Image.new("RGB", (width, height), CANVAS_BACKGROUND)
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=18, fill=CARD_BACKGROUND, outline=CARD_BORDER, width=2)
        draw.text((48, height // 2 - 12), empty_message, fill="#596579", font=_font(18, bold=True))
        canvas.save(output_path, format="PNG", optimize=True)
        return {
            "rows": 0,
            "columns": 0,
            "count": 0,
            "canvas": [width, height],
            "style": "compact_cards_v1",
            "subject_scale": "longest_edge_normalized",
        }

    rows, columns = choose_grid(len(items))
    outer, gap = DEFAULT_OUTER_MARGIN, DEFAULT_GAP
    if canvas_size is None:
        card_width, card_height = DEFAULT_CARD_SIZE
        width = outer * 2 + columns * card_width + (columns - 1) * gap
        height = outer * 2 + rows * card_height + (rows - 1) * gap
    else:
        width, height = canvas_size
        if min(width, height) < 320:
            raise ValueError("contact-sheet dimensions must be at least 320 pixels")
        card_width = (width - outer * 2 - gap * (columns - 1)) // columns
        card_height = (height - outer * 2 - gap * (rows - 1)) // rows
        if min(card_width, card_height) < 96:
            raise ValueError("contact-sheet canvas is too small for the requested asset count")

    canvas = Image.new("RGB", (width, height), CANVAS_BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    label_height = max(44, round(card_height * 0.15))
    label_font = _font(max(14, min(20, round(card_width / 18))), bold=True)

    for index, item in enumerate(items):
        row, column = divmod(index, columns)
        left = outer + column * (card_width + gap)
        top = outer + row * (card_height + gap)
        right, bottom = left + card_width, top + card_height
        radius = max(10, min(18, round(min(card_width, card_height) * 0.055)))
        draw.rounded_rectangle((left + 3, top + 5, right + 3, bottom + 5), radius=radius, fill=CARD_SHADOW)
        draw.rounded_rectangle((left, top, right, bottom), radius=radius, fill=CARD_BACKGROUND, outline=CARD_BORDER, width=2)

        raw_label = str(item.get("label") or item.get("id") or f"asset-{index + 1:02d}")
        label = _fit_label(draw, raw_label, label_font, card_width - 36)
        label_box = draw.textbbox((0, 0), label, font=label_font)
        label_text_height = label_box[3] - label_box[1]
        label_y = top + max(10, (label_height - label_text_height) // 2 - label_box[1])
        draw.text((left + 18, label_y), label, fill=TEXT_COLOR, font=label_font)
        divider_y = top + label_height
        draw.line((left + 16, divider_y, right - 16, divider_y), fill=DIVIDER_COLOR, width=2)

        subject = isolate_subject(Path(item["image_path"]))
        available_width = max(1, round(card_width * 0.8))
        available_height = max(1, round((card_height - label_height) * 0.82))
        normalized_edge = max(1, min(available_width, available_height))
        scale = normalized_edge / max(1, max(subject.size))
        subject = subject.resize(
            (max(1, round(subject.width * scale)), max(1, round(subject.height * scale))),
            Image.Resampling.LANCZOS,
        )
        x = left + (card_width - subject.width) // 2
        y = divider_y + (bottom - divider_y - subject.height) // 2
        canvas.paste(subject, (x, y), subject)

    canvas.save(output_path, format="PNG", optimize=True)
    return {
        "rows": rows,
        "columns": columns,
        "count": len(items),
        "canvas": [width, height],
        "style": "compact_cards_v1",
        "subject_scale": "longest_edge_normalized",
    }
