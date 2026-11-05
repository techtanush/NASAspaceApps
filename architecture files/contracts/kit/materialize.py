#!/usr/bin/env python3
"""Materialize or verify the FROZEN CONTRACT KIT inside analogforge/ (architecture 35).

Every branch agent runs this FIRST (before writing any code):
    python3 "architecture files/contracts/kit/materialize.py"
It copies kit/files/<path> to analogforge/<path> byte-for-byte. It never overwrites a file
whose content differs from the kit (except the merging agent's explicit --repair).

Verify at the end of every session and in every merge purity check:
    python3 "architecture files/contracts/kit/materialize.py" --verify
Exit code 0 only if every kit file exists in analogforge/ with the exact kit SHA-256, no
extra files exist under analogforge/src/analogforge/ports/, and pyproject.toml differs
from the kit only inside the three editable extra-<person> lists.

Standard library only (works before any dependency is installed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
REPO = KIT.parents[2]
APP = REPO / "analogforge"
FILES = KIT / "files"
EXTRA_START = re.compile(r"^(extra-(?:tanush|ayan|aradhya)) = \[")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_pyproject(text: str) -> str:
    """Blank out the bodies of the three editable extra-<person> lists (line based)."""
    out: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        match = EXTRA_START.match(lines[i])
        if match:
            out.append(f"{match.group(1)} = []")
            if not lines[i].rstrip().endswith("]"):
                i += 1
                while i < len(lines) and lines[i].strip() != "]":
                    i += 1
        else:
            out.append(lines[i])
        i += 1
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--verify", action="store_true", help="only check; never write")
    parser.add_argument("--repair", action="store_true", help="MERGING AGENT ONLY: overwrite drifted kit files")
    parser.add_argument("--app", type=Path, default=APP, help="target analogforge/ directory")
    args = parser.parse_args()
    app: Path = args.app.resolve()
    manifest = json.loads((KIT / "kit-manifest.json").read_text())
    problems: list[str] = []
    written: list[str] = []

    for rel, expected in manifest["files"].items():
        src = FILES / rel
        dst = app / rel
        if sha(src) != expected:
            problems.append(f"KIT CORRUPT: kit/files/{rel} does not match kit-manifest.json")
            continue
        if not dst.exists():
            if args.verify:
                problems.append(f"MISSING: analogforge/{rel}")
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
                written.append(rel)
            continue
        if sha(dst) == expected:
            continue
        if rel == "pyproject.toml" and normalize_pyproject(dst.read_text()) == normalize_pyproject(src.read_text()):
            continue
        if args.repair and not args.verify:
            shutil.copyfile(src, dst)
            written.append(rel + " (repaired)")
        else:
            problems.append(f"DRIFT: analogforge/{rel} differs from the frozen kit")

    ports_dir = app / "src/analogforge/ports"
    if ports_dir.exists():
        kit_ports = {r for r in manifest["files"] if r.startswith("src/analogforge/ports/")}
        for path in ports_dir.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                rel = path.relative_to(app).as_posix()
                if rel not in kit_ports:
                    problems.append(f"FOREIGN FILE in kit-only package: analogforge/{rel}")

    report = {
        "status": "PASS" if not problems else "FAIL",
        "mode": "verify" if args.verify else ("repair" if args.repair else "materialize"),
        "kit_version": manifest["kit_version"],
        "app": str(app),
        "written": written,
        "problems": problems,
    }
    print(json.dumps(report, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
