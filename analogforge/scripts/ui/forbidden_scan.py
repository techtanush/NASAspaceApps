#!/usr/bin/env python3
"""Check owned production sources and test reports for prohibited patterns."""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANS = [
    ("unsafe-dom", r"dangerouslySetInnerHTML|\binnerHTML\s*=|\beval\s*\(|new Function\s*\(|document\.write\s*\("),
    ("unfinished", r"\b(?:TO" + r"DO|FIX" + r"ME|HA" + r"CK|XXX|NotImplementedError)\b"),
    ("external-font", r"fonts\.googleapis|fonts\.gstatic|use\.typekit|cdnjs|unpkg|jsdelivr"),
    (
        "banned-library",
        r"""(?:from\s*|import\s*)['"](?:@mui|antd|@chakra-ui|@mantine|bootstrap|framer-motion|gsap|lottie|chart\.js|echarts)""",
    ),
    ("unsafe-test-selection", r"\b(?:test|it|describe)\.(?:skip|fixme|only)\s*\(|\bxit\s*\("),
]
PURE_IMPORTS = {
    "__future__",
    "uuid",
    "xml",
    "typing",
    "collections",
    "dataclasses",
    "hashlib",
    "json",
    "csv",
    "io",
    "base64",
    "html",
    "re",
    "math",
    "decimal",
    "datetime",
    "pathlib",
    "enum",
    "itertools",
    "functools",
    "jinja2",
    "markupsafe",
    "pydantic",
    "analogforge",
}


def scan(root: Path = ROOT) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    paths = (
        list((root / "apps/web/src").rglob("*"))
        + list((root / "src/analogforge/rendering/passport").rglob("*"))
        + list((root / "tests/e2e").rglob("*"))
    )
    for path in paths:
        if path.suffix not in {".ts", ".tsx", ".css", ".py", ".j2"} or "generated" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        content = path.read_text()
        testing = ".test." in path.name or ".spec." in path.name
        for rule, expression in SCANS:
            if testing and rule not in {"unsafe-test-selection"}:
                continue
            for match in re.finditer(expression, content):
                findings.append({"path": relative, "line": content.count("\n", 0, match.start()) + 1, "rule": rule})
        if relative.startswith("apps/web/src/") and not testing:
            if "/mock/" not in relative and re.search(r"crypto\.subtle\.digest|createHash\s*\(", content):
                findings.append({"path": relative, "rule": "client-side-manifest-hash"})
            if "/api/" not in relative and re.search(r"\bfetch\s*\(|XMLHttpRequest", content):
                findings.append({"path": relative, "rule": "transport-outside-api"})
            for line, value in enumerate(content.splitlines(), 1):
                if re.search(r"(?:localStorage|sessionStorage)", value) and not (
                    "view-preference" in value or "af.theme" in value or "af.density" in value
                ):
                    findings.append({"path": relative, "line": line, "rule": "persisted-domain-state"})
            if "/maps/" not in relative and "/mock/fixtures/" not in relative and path.name != "tokens.css":
                for match in re.finditer(r"#[0-9a-fA-F]{3,8}\b|\brgb\s*\(|\bhsl\s*\(", content):
                    findings.append(
                        {
                            "path": relative,
                            "line": content.count("\n", 0, match.start()) + 1,
                            "rule": "color-outside-tokens",
                        }
                    )
            if re.search(r"(?:linear|radial|conic)-gradient|backdrop-filter|text-shadow:\s*(?!none)[^;]+", content):
                findings.append({"path": relative, "rule": "decorative-effect"})
            if re.search(r"Lorem ipsum|Coming soon", content, re.IGNORECASE):
                findings.append({"path": relative, "rule": "unfinished-copy"})
            if "/mock/" not in relative:
                for line, value in enumerate(content.splitlines(), 1):
                    if not value.lstrip().startswith(("//", "*")) and re.search(r"https?://", value):
                        findings.append({"path": relative, "line": line, "rule": "absolute-url"})
                if "/format/time." not in relative and re.search(r"Math\.random|Date\.now|new Date\(\)", content):
                    findings.append({"path": relative, "rule": "nondeterministic-display"})
            for radius in re.finditer(r"border(?:-[a-z]+)*-radius\s*:\s*(\d+(?:\.\d+)?)px", content):
                if float(radius[1]) > 6:
                    findings.append({"path": relative, "rule": "large-radius"})
            if re.search(r"[\U0001f300-\U0001faff]", content):
                findings.append({"path": relative, "rule": "emoji"})
            if re.search(r"\.(?:value|measured|threshold|lower|upper|reserve)\w*\s*[-+*/]\s*", content):
                findings.append({"path": relative, "rule": "scientific-arithmetic"})
            if re.search(r"""['"]PASS['"]\s*\|\s*['"]PARTIAL['"]""", content):
                findings.append({"path": relative, "rule": "duplicated-science-enum"})
        if relative.startswith("src/analogforge/rendering/passport/") and path.suffix == ".py":
            for node in ast.walk(ast.parse(content)):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    modules = [x.name for x in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                    for module in modules:
                        if node.level if isinstance(node, ast.ImportFrom) else False:
                            continue
                        if module.split(".")[0] not in PURE_IMPORTS:
                            findings.append(
                                {"path": relative, "line": node.lineno, "rule": "impure-import", "module": module}
                            )
            if re.search(r'datetime\.now|time\.time|os\.environ|open\([^\n]+[\'"]w', content):
                findings.append({"path": relative, "rule": "impure-renderer"})
    for asset in (root / "apps/web/public").rglob("*"):
        if re.search(r"meatball|nasa-logo|worm", asset.name, re.IGNORECASE):
            findings.append({"path": asset.relative_to(root).as_posix(), "rule": "insignia"})
    report = root / "out/e2e-results.json"
    if report.exists():
        data = json.loads(report.read_text())
        if data.get("stats", {}).get("skipped", 0):
            findings.append({"path": "out/e2e-results.json", "rule": "skipped-journey"})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    findings = scan()
    result = {"status": "PASS" if not findings else "FAIL", "findings": findings}
    rendered = json.dumps(result, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n")
    print(rendered)
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
