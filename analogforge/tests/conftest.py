"""Make ``tests/support`` importable as ``support`` for all science suites."""

from __future__ import annotations

import sys
from pathlib import Path

TESTS = str(Path(__file__).resolve().parent)
if TESTS not in sys.path:
    sys.path.insert(0, TESTS)
