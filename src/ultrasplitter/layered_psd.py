"""Export reviewed production assets as full-resolution editable PSD layers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


MAX_PSD_DIMENSION = 30_000
LAYER_GAP = 32
MAX_LAYER_DIMENSION = MAX_PSD_DIMENSION


@dataclass(frozen=True)
class LayerSource:
    label: str
    path: Path
    size: tuple[int, int]
    crop: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class PlacedLayer:
    source: LayerSource
    left: int
    top: int


def _layer_items(manifest: dict[str, Any]) -> list[tuple[str, Path]]:
    transparent_is_approved = (
        manifest.get("evaluation", {}).get("transparent", {}).get("status") == "pass"
    )
    items: list[tuple[str, Path]] = []
    for item in manifest.get("items", []):
        if not item.get("deliverable"):
            continue
        variants = item.get("variants", {})
        path = variants.get("transparent") if transparent_is_approved else None
        path = path or item.get("image_path")
        if path:
            items.append((str(item.get("label") or item.get("id") or "Asset"), Path(path)))
    if not items:
        raise ValueError("no reviewed production assets are available for PSD export")
    return items


def _split_large_sources(items: list[tuple[str, Path]]) -> list[LayerSource]:
    sources: list[LayerSource] = []
    for label, path in items:
        if not path.is_file():
            raise ValueError(f"PSD layer source is missing for {label}: {path}")
        with Image.open(path) as opened:
            width, height = opened.size
        columns = (width + MAX_LAYER_DIMENSION - 1) // MAX_LAYER_DIMENSION
        rows = (height + MAX_LAYER_DIMENSION - 1) // MAX_LAYER_DIMENSION
        for row in range(rows):
            top = row * MAX_LAYER_DIMENSION
            bottom = min(height, top + MAX_LAYER_DIMENSION)
            for column in range(columns):
                left = column * MAX_LAYER_DIMENSION
                right = min(width, left + MAX_LAYER_DIMENSION)
                crop = None if rows == columns == 1 else (left, top, right, bottom)
                tile_label = label
                if crop is not None:
                    tile_label = f"{label} [tile r{row + 1} c{column + 1}]"
                sources.append(
                    LayerSource(tile_label, path, (right - left, bottom - top), crop)
                )
    return sources


def _pack_layers(sources: list[LayerSource]) -> list[list[PlacedLayer]]:
    """Pack native-size layers into PSD pages; split only assets wider than one page."""
    ordered = sorted(
        sources,
        key=lambda source: (-max(source.size), -source.size[1], -source.size[0], source.label),
    )
    pages: list[list[PlacedLayer]] = [[]]
    left = 0
    top = 0
    shelf_height = 0

    for source in ordered:
        width, height = source.size
        if width > MAX_LAYER_DIMENSION or height > MAX_LAYER_DIMENSION:
            raise ValueError(f"internal PSD tiling error for {source.label}: {width}x{height}px")
        if left + width > MAX_PSD_DIMENSION:
            left = 0
            top += shelf_height + LAYER_GAP
            shelf_height = 0
        if top + height > MAX_PSD_DIMENSION:
            pages.append([])
            left = 0
            top = 0
            shelf_height = 0
        pages[-1].append(PlacedLayer(source, left, top))
        left += width + LAYER_GAP
        shelf_height = max(shelf_height, height)
    return pages


def _page_size(layers: list[PlacedLayer]) -> tuple[int, int]:
    width = max(layer.left + layer.source.size[0] for layer in layers)
    height = max(layer.top + layer.source.size[1] for layer in layers)
    if max(width, height) > MAX_PSD_DIMENSION:
        raise ValueError(f"internal PSD packing error: page would be {width}x{height}px")
    return width, height


def _page_path(output_path: Path, index: int) -> Path:
    if index == 0:
        return output_path
    return output_path.with_name(f"{output_path.stem}-{index + 1:02d}{output_path.suffix}")


def export_layered_psd(manifest: dict[str, Any], output_path: Path) -> dict[str, Any]:
    """Export one PSD when it fits; otherwise emit lossless, full-resolution PSD pages."""
    try:
        from psd_tools import PSDImage
    except ImportError as exc:
        raise ValueError("PSD export requires psd-tools; reinstall UltraSplitter from pyproject.toml") from exc

    sources = _split_large_sources(_layer_items(manifest))
    pages = _pack_layers(sources)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    page_info: list[dict[str, Any]] = []
    for page_index, layers in enumerate(pages):
        canvas = _page_size(layers)
        psd = PSDImage.new(mode="RGB", size=canvas, depth=8)
        psd.background_color = None
        layer_info: list[dict[str, Any]] = []
        for layer_index, placed in enumerate(layers, 1):
            source = placed.source
            with Image.open(source.path) as opened:
                if source.crop is not None:
                    layer_image = opened.crop(source.crop).convert("RGBA")
                else:
                    layer_image = opened.convert("RGBA")
            name = f"{layer_index:02d} {source.label}"
            psd.create_pixel_layer(
                layer_image,
                name=name,
                top=placed.top,
                left=placed.left,
            )
            layer_info.append(
                {
                    "name": name,
                    "source": str(source.path.resolve()),
                    "source_crop": list(source.crop) if source.crop is not None else None,
                }
            )

        page_path = _page_path(output_path, page_index)
        psd.save(page_path)
        page_info.append(
            {
                "path": str(page_path.resolve()),
                "canvas": list(canvas),
                "layer_count": len(layers),
                "layers": layer_info,
            }
        )

    source_variant = (
        "transparent"
        if manifest.get("evaluation", {}).get("transparent", {}).get("status") == "pass"
        else "primary"
    )
    return {
        "path": page_info[0]["path"],
        "paths": [page["path"] for page in page_info],
        "page_count": len(page_info),
        "layer_count": len(sources),
        "asset_count": len({source.path.resolve() for source in sources}),
        "canvas": page_info[0]["canvas"],
        "pages": page_info,
        "layout": "compact_native_size_pages",
        "source_variant": source_variant,
        "resampled": False,
        "tiled_layer_count": sum(source.crop is not None for source in sources),
    }
