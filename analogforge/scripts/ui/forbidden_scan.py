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


GLASS_CSS = "apps/web/src/styles/glass.css"
GLASS_CONTRACT = "apps/web/design/glass-surfaces.json"
ELEVATION_INK = {"var(--glass-ink)"}
COLOURED_SHADOW_TOKENS = ("--accent", "--state-", "--focus", "--ambient", "--on-accent", "--glass-tint")


def _css_rules(css: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """Flat (selector, declarations) pairs; at-rule wrappers are transparent."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        declarations = []
        for part in match.group(2).split(";"):
            if ":" in part:
                name, value = part.split(":", 1)
                declarations.append((name.strip().lower(), " ".join(value.split())))
        rules.append((" ".join(match.group(1).split()), declarations))
    return rules


def _layers(value: str) -> list[str]:
    layers, depth, current = [], 0, ""
    for char in value:
        depth += char == "("
        depth -= char == ")"
        if char == "," and depth == 0:
            layers.append(current.strip())
            current = ""
        else:
            current += char
    return [layer for layer in [*layers, current.strip()] if layer]


def _last_compound_classes(selector: str) -> set[str]:
    last = re.split(r"\s*[>+~]\s*|\s+", selector.strip())[-1]
    return set(re.findall(r"\.[A-Za-z][\w-]*", last))


def scan_glass_stylesheet(css: str, contract: dict[str, object]) -> list[dict[str, object]]:
    """Validate glass.css against design/glass-surfaces.json.

    glass.css is the only file exempt from the decorative-effect and large-radius rules, so it is held to a stricter,
    structural contract: bounded blur, radial gradients on the ambient element only, listed surfaces only, dark
    below-the-element elevation shadows (no halos, no coloured shadows), token-derived colours and four fallbacks.
    """
    findings: list[dict[str, object]] = []

    def add(rule: str, detail: str, selector: str = "") -> None:
        findings.append({"path": GLASS_CSS, "rule": rule, "detail": detail, "selector": selector})

    chrome, panels = set(contract["chrome"]), set(contract["panels"])  # type: ignore[call-overload]
    frames, ambient = set(contract["frames"]), str(contract["ambient"])  # type: ignore[call-overload]
    limits = contract["limits"]  # type: ignore[assignment]
    glass = chrome | panels
    rules = _css_rules(css)
    properties = {name: value for _, decls in rules for name, value in decls if name.startswith("--")}

    def resolve(value: str, depth: int = 0) -> str:
        if depth > 6:
            return value
        return re.sub(r"var\((--[\w-]+)\)", lambda m: resolve(properties.get(m[1], m[0]), depth + 1), value)

    for selector, declarations in rules:
        selectors = [part.strip() for part in selector.split(",") if part.strip()]
        for name, raw in declarations:
            value = resolve(raw)
            if name in {"backdrop-filter", "-webkit-backdrop-filter"} and value.strip() != "none":
                for part in selectors:
                    classes = _last_compound_classes(part)
                    if not classes & glass:
                        add("glass-unlisted-surface", "backdrop-filter outside chrome and panels", part)
                    if classes & frames and not classes & glass:
                        add("glass-blurred-data-frame", "data frames must stay opaque", part)
                blurs = [float(number) for number in re.findall(r"blur\(\s*([\d.]+)px\s*\)", value)]
                if not blurs or max(blurs) > float(limits["blur_px_max"]):  # type: ignore[index]
                    add("glass-blur-unbounded", value, selector)
                if re.sub(r"blur\([^)]*\)|saturate\(\s*(?:1(?:\.[0-6]\d*)?)\s*\)", "", value).strip():
                    add("glass-filter-function", value, selector)
            if "gradient" in value:
                if re.findall(r"([\w-]*gradient)\(", value) != ["radial-gradient"] * len(re.findall(r"gradient\(", value)):
                    add("glass-gradient-kind", "only radial gradients are permitted", selector)
                if selectors != [ambient]:
                    add("glass-gradient-outside-ambient", "gradients belong to the ambient element only", selector)
            if name.endswith("radius"):
                sizes = [float(number) for number in re.findall(r"([\d.]+)px", value)]
                if sizes and max(sizes) > float(limits["radius_px_max"]):  # type: ignore[index]
                    add("glass-radius-too-large", value, selector)
                if sizes and max(sizes) > 6:
                    for part in selectors:
                        if not _last_compound_classes(part) & (glass | frames):
                            add("glass-radius-unlisted", "radius above 6 px outside listed surfaces", part)
            if name == "box-shadow" or name.startswith("--glass-shadow"):
                # Checked on the raw value: a layer that is only var(--x) is validated where --x is defined.
                if any(token in raw for token in COLOURED_SHADOW_TOKENS):
                    add("glass-coloured-shadow", raw, selector)
                for layer in _layers(raw):
                    if layer == "none" or re.fullmatch(r"var\(--[\w-]+\)", layer):
                        continue
                    head = re.split(r"color-mix|var\(|#|rgb|hsl", layer)[0]
                    lengths = [float(number) for number in re.findall(r"-?\d*\.?\d+(?=px|\s|$)", head)]
                    lengths += [0.0] * (4 - len(lengths))
                    x, y, blur, spread = lengths[:4]
                    if "inset" in layer:
                        if blur > float(limits["inset_highlight_blur_px_max"]):  # type: ignore[index]
                            add("glass-inset-halo", layer, selector)
                    elif not (x == 0 and y > 0 and blur > 0 and spread <= 0):
                        add("glass-shadow-halo", f"outer shadows fall below the element: {layer}", selector)
                    elif "var(--glass-ink)" not in layer:
                        add("glass-shadow-ink", f"outer shadows use --glass-ink: {layer}", selector)
    ambient_declared: dict[str, str] = {}
    for selector, declarations in rules:
        if [part.strip() for part in selector.split(",")] == [ambient]:
            ambient_declared.update(dict(declarations))
    if ambient_declared.get("position") != "fixed" or ambient_declared.get("pointer-events") != "none":
        add("glass-ambient-interactive", "ambient layer must be fixed and non-interactive", ambient)
    if not ambient_declared.get("z-index", "0").startswith("-"):
        add("glass-ambient-layering", "ambient layer must sit behind content", ambient)
    for ink in ("--glass-ink",):
        for selector, declarations in rules:
            for name, value in declarations:
                if name == ink and value not in {"var(--canvas)", "var(--text-primary)"}:
                    add("glass-shadow-ink", f"{ink} must derive from a neutral token", selector)
    for fallback in contract["required_fallbacks"]:  # type: ignore[attr-defined]
        if fallback not in css:
            add("glass-missing-fallback", str(fallback))
    return findings


def scan(root: Path = ROOT) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    paths = (
        list((root / "apps/web/src").rglob("*"))
        + list((root / "src/analogforge/rendering/passport").rglob("*"))
        + list((root / "tests/e2e").rglob("*"))
        + list((root / "scripts/ui").rglob("*"))
        + [root / "scripts/build_mock_exports.py"]
    )
    for path in paths:
        if path.suffix not in {".ts", ".tsx", ".css", ".py", ".mjs", ".j2"} or "generated" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        content = path.read_text()
        # The scanner contains the patterns it detects; mutation catalogs deliberately inject violations.
        if path.name in {"forbidden_scan.py", "mutation_check.py", "api_mutations.py", "renderer_mutations.py"}:
            continue
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
            is_glass = relative == GLASS_CSS
            if is_glass:
                contract_path = root / GLASS_CONTRACT
                if not contract_path.is_file():
                    findings.append({"path": relative, "rule": "glass-contract-missing"})
                else:
                    findings.extend(scan_glass_stylesheet(content, json.loads(contract_path.read_text())))
                if re.search(r"text-shadow:\s*(?!none)[^;]+", content):
                    findings.append({"path": relative, "rule": "decorative-effect"})
            elif re.search(r"(?:linear|radial|conic)-gradient|backdrop-filter|text-shadow:\s*(?!none)[^;]+", content):
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
                if float(radius[1]) > 6 and not is_glass:
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
