#!/usr/bin/env python3
# ruff: noqa: E501, S603, S607, S101
"""Forbidden-pattern scan over the science-owned production and test paths (guide 09 section 1).

Exit code 0 when clean, 1 when any finding exists.  ``--json PATH`` writes the findings.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
PROD_PATHS = [
    "src/analogforge/science",
    "src/analogforge/adapters/earthdata",
    "src/analogforge/adapters/pds",
    "src/analogforge/adapters/emit",
    "src/analogforge/adapters/diviner",
    "src/analogforge/adapters/user_survey",
    "src/analogforge/adapters/source_http",
    "src/analogforge/rendering/tiles",
]
TEST_PATHS = [
    "tests/unit/science",
    "tests/property/science",
    "tests/integration/science",
    "tests/replay/science",
    "tests/contracts/science",
    "tests/fixtures/science",
    "scripts/science",
]
WORD_PATTERNS = {
    "TODO": re.compile(r"\bTODO\b"),
    "FIXME": re.compile(r"\bFIXME\b"),
    "HACK": re.compile(r"\bHACK\b"),
    "XXX": re.compile(r"\bXXX\b"),
    "NotImplementedError": re.compile(r"\bNotImplementedError\b"),
}
TEST_ONLY = {
    "pytest.skip": re.compile(r"pytest\.skip\(|pytest\.mark\.skip|pytest\.mark\.xfail|\bxfail\("),
    "importorskip": re.compile(r"importorskip"),
}
ENV_PATTERN = re.compile(r"os\.environ|os\.getenv|\bgetenv\(")
FORBIDDEN_IMPORTS = ("fastapi", "sqlalchemy", "psycopg", "openai")
FORBIDDEN_INTERNAL = (
    "analogforge.api",
    "analogforge.db",
    "analogforge.jobs",
    "analogforge.application",
    "analogforge.agents",
    "analogforge.tools",
    "analogforge.rendering.passport",
)
DECISION_DIRS = ("routing", "comparison")
DECISION_FILES = ("qualification.py", "compatibility.py")
PRACTICE_LITERAL = re.compile(r"[\"']grid-r\dc\d[\"']")


@dataclass
class Finding:
    path: str
    line: int
    rule: str
    text: str


def _files(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for rel in paths:
        base = ROOT / rel
        if base.is_file():
            out.append(base)
        elif base.is_dir():
            out.extend(sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts))
    return [p for p in out if p.resolve() != SELF]


def _scan_text(path: Path, is_test: bool, findings: list[Path | Finding]) -> None:
    rel = str(path.relative_to(ROOT))
    text = path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), start=1):
        code = line.split("#", 1)[0] if not re.search(r"TODO|FIXME|HACK|XXX", line.split("#", 1)[-1]) else line
        for rule, pat in WORD_PATTERNS.items():
            if pat.search(line):
                findings.append(Finding(rel, i, rule, line.strip()))
        if is_test:
            for rule, pat in TEST_ONLY.items():
                if pat.search(code) and "forbidden_scan" not in rel:
                    findings.append(Finding(rel, i, rule, line.strip()))
        if ENV_PATTERN.search(code) and "test_import_hygiene" not in rel and "forbidden_scan" not in rel:
            findings.append(Finding(rel, i, "environment access", line.strip()))
    parts = path.relative_to(ROOT).parts
    if "science" in parts and not is_test and "fixtures" not in parts:
        in_decision = any(d in parts for d in DECISION_DIRS) or path.name in DECISION_FILES
        if in_decision:
            for i, line in enumerate(text.splitlines(), start=1):
                if PRACTICE_LITERAL.search(line):
                    findings.append(Finding(rel, i, "practice window literal in decision logic", line.strip()))


def _scan_ast(path: Path, findings: list[Path | Finding]) -> None:
    rel = str(path.relative_to(ROOT))
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        findings.append(Finding(rel, exc.lineno or 0, "syntax error", str(exc)))
        return
    is_protocol_file = rel.endswith("ports/science.py")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                top = name.split(".")[0]
                if top in FORBIDDEN_IMPORTS or any(name == m or name.startswith(m + ".") for m in FORBIDDEN_INTERNAL):
                    findings.append(Finding(rel, node.lineno, "forbidden import", name))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not is_protocol_file:
            body = [
                s
                for s in node.body
                if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))
            ]
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                findings.append(Finding(rel, node.lineno, "pass-bodied function", node.name))
        if isinstance(node, ast.ExceptHandler):
            broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"})
            if broad and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                findings.append(Finding(rel, node.lineno, "except Exception: pass", ""))


def scan() -> list[Finding]:
    findings: list[Path | Finding] = []
    for is_test, paths in ((False, PROD_PATHS), (True, TEST_PATHS)):
        for path in _files(paths):
            _scan_text(path, is_test, findings)
            _scan_ast(path, findings)
    return [f for f in findings if isinstance(f, Finding)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    findings = scan()
    for f in findings:
        print(f"{f.path}:{f.line}: {f.rule}: {f.text}")
    print(f"forbidden_scan: {len(findings)} finding(s)")
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"findings": [asdict(f) for f in findings]}, indent=2), encoding="utf-8")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
