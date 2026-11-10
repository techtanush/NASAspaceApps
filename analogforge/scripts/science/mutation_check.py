#!/usr/bin/env python3
# ruff: noqa: E501, S603, S607, S101, S314
"""Reusable mutation runner (guide 09 section 1).

Mutants live in ``scripts/science/mutants.json``: ``{"mutants": [{id, description, file, old, new, tests}]}``.
Each names a source file (relative to ``src/``), an exact ``old`` snippet (must occur exactly once), its replacement
and the test selection that must FAIL.  The mutant is applied to a temporary copy of ``src`` that shadows the real
package through ``sys.path``; the real tree is never modified.  A surviving mutant (tests still pass) is a missing
or weak test.

``--only M4`` runs one mutant; ``--json`` writes the report.  Exit 0 only if every selected mutant was killed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
MUTANT_FILE = Path(__file__).with_name("mutants.json")


@dataclass(frozen=True)
class Mutant:
    mutant_id: str
    description: str
    file: str
    old: str
    new: str
    tests: tuple[str, ...]


def all_mutants(path: Path = MUTANT_FILE) -> list[Mutant]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        Mutant(m["id"], m["description"], m["file"], m["old"], m["new"], tuple(m["tests"])) for m in raw["mutants"]
    ]


def run_mutant(mutant: Mutant, timeout: int = 900) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="mutant-") as tmp:
        copy = Path(tmp) / "src"
        shutil.copytree(SRC, copy, ignore=shutil.ignore_patterns("__pycache__"))
        if (ROOT / "config").is_dir():
            shutil.copytree(ROOT / "config", Path(tmp) / "config")
        target = copy / mutant.file
        text = target.read_text(encoding="utf-8")
        if text.count(mutant.old) != 1:
            return {
                **asdict(mutant),
                "killed": False,
                "error": f"old snippet occurs {text.count(mutant.old)} times (need exactly 1)",
            }
        args = ["-x", "-q", "-p", "no:randomly", "-p", "no:cacheprovider", *mutant.tests]
        code = (
            "import sys; sys.dont_write_bytecode = True; sys.path.insert(0, sys.argv[1]); import pytest; "
            "sys.exit(pytest.main(sys.argv[2:]))"
        )

        def execute(stage: str) -> dict[str, object]:
            junit = Path(tmp) / f"{stage}.xml"
            cmd = [sys.executable, "-c", code, str(copy), *args, f"--junitxml={junit}"]
            try:
                proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
            except subprocess.TimeoutExpired:
                return {"exit_code": None, "tests": 0, "failures": 0, "errors": 1, "skipped": 0, "tail": "TIMEOUT"}
            counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
            if junit.is_file():
                report = ET.parse(junit).getroot()
                counts = {
                    "tests": len(report.findall(".//testcase")),
                    "failures": len(report.findall(".//failure")),
                    "errors": len(report.findall(".//error")),
                    "skipped": len(report.findall(".//skipped")),
                }
            output = proc.stdout + proc.stderr
            tail = "\n".join(output.strip().splitlines()[-20:])
            return {"exit_code": proc.returncode, **counts, "tail": tail}

        baseline = execute("baseline")
        if baseline["exit_code"] != 0 or baseline["tests"] == 0 or baseline["skipped"] != 0:
            return {**asdict(mutant), "killed": False, "baseline": baseline, "error": "BASELINE_NOT_PASSED"}
        target.write_text(text.replace(mutant.old, mutant.new), encoding="utf-8")
        changed = execute("mutant")
        # A setup/collection error or a skipped test is not evidence that the
        # scientific invariant rejected the mutation. Only executed test failures count.
        killed = (
            changed["exit_code"] == 1 and changed["failures"] > 0
            and changed["errors"] == 0 and changed["skipped"] == 0
        )
        return {**asdict(mutant), "killed": killed, "baseline": baseline,
                "mutant": changed, "exit_code": changed["exit_code"], "tail": changed["tail"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--mutants", type=Path, default=MUTANT_FILE)
    args = parser.parse_args()
    mutants = [m for m in all_mutants(args.mutants) if not args.only or m.mutant_id in args.only]
    if not mutants:
        print("mutation_check: no mutants selected", file=sys.stderr)
        return 2
    results = []
    for m in mutants:
        res = run_mutant(m)
        results.append(res)
        print(f"{m.mutant_id}: {'KILLED' if res['killed'] else 'SURVIVED/ERROR'}  {m.description}")
        if not res["killed"]:
            print(res.get("tail") or res.get("error"))
    survivors = [r for r in results if not r["killed"]]
    print(f"mutation_check: {len(results) - len(survivors)}/{len(results)} killed")
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
