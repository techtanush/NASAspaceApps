#!/usr/bin/env python3
"""Fail on platform source patterns that would bypass frozen scientific boundaries."""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "analogforge"
FORBIDDEN = {
    "scenario-outcome literal": re.compile(
        r"(?:attempt\s*[123]\s*(?:passes|fails)|grid-r0c[01].*?(?:PASS|FAIL))", re.I
    ),
    "inline scientific slope": re.compile(r"(?:np\.gradient|numpy\.gradient|arctan\s*\(|atan\s*\()"),
    "secret output": re.compile(
        r"(?:print|logger\.[a-z]+)\s*\([^\n]*(?:openai_api_key|earthdata_token|session_secret)"
    ),
}


def scan() -> list[str]:
    findings: list[str] = []
    for path in SOURCE.rglob("*.py"):
        if "ports" in path.parts or "science" in path.parts or "rendering" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for label, pattern in FORBIDDEN.items():
            for hit in pattern.finditer(text):
                line = text.count("\n", 0, hit.start()) + 1
                findings.append(f"{path.relative_to(ROOT)}:{line}: {label}")
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT and re.search(r"\b(?:TODO|FIXME|HACK|XXX)\b", token.string):
                findings.append(f"{path.relative_to(ROOT)}:{token.start[0]}: unfinished marker")
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            findings.append(f"{path.relative_to(ROOT)}:{exc.lineno}: syntax error")
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and len(node.body) == 1
                and isinstance(node.body[0], ast.Pass)
            ):
                findings.append(f"{path.relative_to(ROOT)}:{node.lineno}: bare-pass function")
            if isinstance(node, ast.ExceptHandler) and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                findings.append(f"{path.relative_to(ROOT)}:{node.lineno}: swallowed exception")
            if isinstance(node, ast.Name) and node.id == "NotImplementedError":
                findings.append(f"{path.relative_to(ROOT)}:{node.lineno}: NotImplementedError")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                findings.append(f"{path.relative_to(ROOT)}:{node.lineno}: print in production source")
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if re.search(r"(?:grid-r[012]c|graph-zone)", node.value):
                    findings.append(f"{path.relative_to(ROOT)}:{node.lineno}: literal practice candidate id")
                if re.search(r"sk-[A-Za-z0-9]{20,}|BEGIN (?:RSA|PRIVATE) KEY", node.value):
                    findings.append(f"{path.relative_to(ROOT)}:{node.lineno}: secret-looking literal")
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name == "analogforge.science" or name.startswith(
                    ("analogforge.science.", "analogforge.rendering.passport")
                ):
                    findings.append(f"{path.relative_to(ROOT)}:{node.lineno}: static cross-branch import {name}")
                if name == "dotenv" and path.name != "settings.py":
                    findings.append(f"{path.relative_to(ROOT)}:{node.lineno}: environment reader outside settings.py")
            if isinstance(node, ast.ImportFrom) and node.module == "os" and path.name != "settings.py":
                if any(alias.name in {"environ", "getenv"} for alias in node.names):
                    findings.append(f"{path.relative_to(ROOT)}:{node.lineno}: environment reader outside settings.py")
        if path.name != "settings.py":
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    if node.value.id == "os" and node.attr in {"environ", "getenv"}:
                        findings.append(
                            f"{path.relative_to(ROOT)}:{node.lineno}: environment reader outside settings.py"
                        )
    for root in (
        ROOT / "tests" / "unit" / "platform",
        ROOT / "tests" / "integration" / "platform",
        ROOT / "tests" / "contracts" / "platform",
    ):
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "pytest"
                        and node.func.attr in {"skip", "xfail", "importorskip"}
                    ):
                        findings.append(
                            f"{path.relative_to(ROOT)}:{node.lineno}: required test skip/xfail/importorskip"
                        )
    return findings


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    issues = scan()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps({"status": "FAIL" if issues else "PASS", "findings": issues}, indent=2) + "\n", encoding="utf-8"
        )
    for issue in issues:
        print(issue)
    print(f"forbidden_scan: {'FAIL' if issues else 'PASS'} ({len(issues)} findings)")
    raise SystemExit(bool(issues))
