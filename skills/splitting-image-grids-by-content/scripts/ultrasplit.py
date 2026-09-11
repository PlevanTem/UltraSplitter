#!/usr/bin/env python3
"""Run UltraSplitter from a repository checkout without an editable install."""

from __future__ import annotations

import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if not SOURCE_ROOT.is_dir():
    raise SystemExit("UltraSplitter package not found. Run this skill inside the UltraSplitter repository.")
sys.path.insert(0, str(SOURCE_ROOT))

from ultrasplitter.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
