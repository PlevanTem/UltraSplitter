#!/usr/bin/env python3
"""Run an installed UltraSplitter package or discover it in a repository checkout."""

from __future__ import annotations

import sys
from pathlib import Path


try:
    from ultrasplitter.cli import main
except ModuleNotFoundError as error:
    if error.name != "ultrasplitter":
        raise
    for parent in Path(__file__).resolve().parents:
        source_root = parent / "src"
        if (source_root / "ultrasplitter").is_dir():
            sys.path.insert(0, str(source_root))
            break
    else:
        raise SystemExit(
            "UltraSplitter runtime not found. Install it with: "
            "python -m pip install git+https://github.com/PlevanTem/UltraSplitter.git"
        ) from error

    from ultrasplitter.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
