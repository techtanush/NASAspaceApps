"""Make the Ayan-owned ``tests/fixtures/science/support`` package importable as ``support``."""

from __future__ import annotations

import sys
from pathlib import Path

_FIX = str(Path(__file__).resolve().parents[2] / "fixtures" / "science")
if _FIX not in sys.path:
    sys.path.insert(0, _FIX)
