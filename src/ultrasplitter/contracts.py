"""Shared public contract constants and manifest helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__version__ = "0.1.0"
SCHEMA_VERSION = 3
MAX_REPAIR_ATTEMPTS = 2
MAX_SUBJECTS_PER_REPAIR_GRID = 6
MIN_REPAIR_VISIBLE_FRACTION = 0.65

ORIGINS = {"source_crop", "source_composite", "generated_reconstruction"}
TERMINAL_STATUSES = {
    "success",
    "needs_review",
    "awaiting_user_approval",
    "needs_user_decision",
    "retry_exhausted",
    "unsupported",
    "failed",
}


class ContractError(ValueError):
    """Raised when a public manifest or repair contract is invalid."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ContractError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def require_v3(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(
            f"manifest schema_version must be {SCHEMA_VERSION}; got {manifest.get('schema_version')}"
        )
