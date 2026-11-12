"""Executable renderer mutation probes, isolated from the working tree.

Each probe changes a temporary copy of the production renderer and runs the
original behavior tests against it. Infrastructure/collection failures are not
counted as killed mutations: at least one assertion failure is required.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

# (catalog id, source filename, exact original, mutated source, relevant suite)
MUTATIONS = (
    ("M8", "html.py", "Environment(autoescape=True", "Environment(autoescape=False", "test_escaping.py"),
    ("M9", "escaping.py", 'return "\'" + text', "return text", "test_escaping.py"),
    (
        "M10",
        "renderer.py",
        "        return RenderedExport(",
        '        content += str(__import__("time").time_ns()).encode()\n        return RenderedExport(',
        "test_determinism.py",
    ),
    ("M11", "html.py", "{% for attempt in data.attempts %}", "{% for attempt in data.attempts[-1:] %}", "test_html.py"),
    ("M15", "html.py", "    if qualified:\n", "    if True:\n", "test_html.py"),
    (
        "M17",
        "html.py",
        "<title>AnalogForge",
        '<script src="https://example.com/external.js"></script><title>AnalogForge',
        "test_html.py",
    ),
    ("M20", "html.py", "DRAFT — INCOMPLETE", "Incomplete draft", "test_html.py"),
    ("M21", "json_export.py", '"canonical_manifest":', '"removed_manifest":', "test_json.py"),
    ("M22", "csv_export.py", "fieldnames=CSV_COLUMNS", "fieldnames=tuple(reversed(CSV_COLUMNS))", "test_csv.py"),
)


def _prepare(root: Path, target: Path) -> None:
    source = root / "src" / "analogforge"
    package = target / "src" / "analogforge"
    package.mkdir(parents=True)
    shutil.copy2(source / "__init__.py", package / "__init__.py")
    shutil.copytree(source / "ports", package / "ports", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(source / "rendering", package / "rendering", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(
        root / "tests" / "unit" / "passport_renderer",
        target / "tests" / "unit" / "passport_renderer",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copytree(root / "tests" / "fixtures" / "kit", target / "tests" / "fixtures" / "kit")
    shutil.copy2(root / "pyproject.toml", target / "pyproject.toml")


def run_renderer_mutations(root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    logs = root / "out" / "mutations"
    logs.mkdir(parents=True, exist_ok=True)
    interpreter = root / ".venv" / "bin" / "python"
    records = []
    for identifier, filename, before, after, suite in MUTATIONS:
        with tempfile.TemporaryDirectory(prefix=f"analogforge-{identifier}-") as directory:
            target = Path(directory)
            _prepare(root, target)
            source = target / "src" / "analogforge" / "rendering" / "passport" / filename
            original = source.read_text()
            if original.count(before) != 1:
                records.append(
                    dict(
                        id=identifier,
                        status="INVALID_PROBE",
                        killed=False,
                        reason="Mutation anchor is missing or ambiguous",
                    )
                )
                continue
            source.write_text(original.replace(before, after, 1))
            command = [str(interpreter), "-m", "pytest", f"tests/unit/passport_renderer/{suite}", "-q"]
            env = dict(os.environ, PYTHONPATH=str(target / "src"), PYTHONDONTWRITEBYTECODE="1")
            result = subprocess.run(command, cwd=target, env=env, capture_output=True, text=True, check=False)  # noqa: S603
            output = result.stdout + result.stderr
            log = logs / f"renderer-{identifier}.log"
            log.write_text(output)
            # A syntax/import failure must never masquerade as assertion coverage.
            failures = re.search(r"\b([1-9][0-9]*) failed\b", result.stdout)
            killed = result.returncode == 1 and failures is not None and "ERROR collecting" not in output
            records.append(
                dict(
                    id=identifier,
                    status="KILLED" if killed else "SURVIVED",
                    killed=killed,
                    exit_code=result.returncode,
                    command=command,
                    failures=int(failures[1]) if failures else 0,
                    output_file=str(log.relative_to(root)),
                    summary=result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "No pytest output",
                )
            )
    return records


if __name__ == "__main__":
    results = run_renderer_mutations(Path(__file__).resolve().parents[2])
    print(json.dumps(results, indent=2))
    raise SystemExit(0 if all(row["killed"] for row in results) else 1)
