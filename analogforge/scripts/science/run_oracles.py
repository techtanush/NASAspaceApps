#!/usr/bin/env python3
# ruff: noqa: E501, S603, S607, S101, S314
"""Run the science oracle suites with junit XML and fail on any skipped/deselected SCN test (guide 05 section 1).

Prints every oracle (test case) with its outcome and the pytest exit code; ``--json PATH`` writes the same data.
Exit 0 only if pytest exited 0, at least one test ran, and no SCN test element is ``skipped``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUITES = [
    "tests/unit/science",
    "tests/property/science",
    "tests/integration/science",
    "tests/contracts/science",
    "tests/replay/science",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--junit", type=Path, default=ROOT / "out" / "science-junit.xml")
    parser.add_argument("paths", nargs="*", default=SUITES)
    args = parser.parse_args()
    args.junit.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "pytest", *args.paths, "-q", "--strict-markers", "-p", "no:randomly",
        "--timeout=600", f"--junitxml={args.junit}",
    ]  # fmt: skip
    proc = subprocess.run(cmd, cwd=ROOT, check=False)
    cases: list[dict[str, str]] = []
    skipped: list[str] = []
    if args.junit.exists():
        for case in ET.parse(args.junit).getroot().iter("testcase"):
            name = f"{case.get('classname')}::{case.get('name')}"
            if case.find("skipped") is not None:
                outcome = "skipped"
                skipped.append(name)
            elif case.find("failure") is not None or case.find("error") is not None:
                outcome = "failed"
            else:
                outcome = "passed"
            cases.append({"oracle": name, "outcome": outcome})
    for c in cases:
        print(f"{c['outcome']:8s} {c['oracle']}")
    print(f"pytest exit code: {proc.returncode}; oracles: {len(cases)}; skipped: {len(skipped)}")
    ok = proc.returncode == 0 and bool(cases) and not skipped
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps({"exit_code": proc.returncode, "oracles": cases, "skipped": skipped, "ok": ok}, indent=2),
            encoding="utf-8",
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
