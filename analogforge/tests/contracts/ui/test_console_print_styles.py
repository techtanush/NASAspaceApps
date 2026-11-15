"""Keep console polish within the existing scanner and paper on the verified light palette."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/ui" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scanner = load_script("forbidden_scan")
generator = load_script("gen_tokens_css")


def style_tree(tmp_path: Path, addition: tuple[str, str] | None = None):
    styles = tmp_path / "apps/web/src/styles"
    styles.mkdir(parents=True)
    for name in ("mission-control.css", "print.css", "tokens.css"):
        (styles / name).write_text((ROOT / "apps/web/src/styles" / name).read_text())
    if addition:
        name, css = addition
        with (styles / name).open("a") as output:
            output.write(css)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/build_mock_exports.py").write_text("")
    return scanner.scan(tmp_path)


def test_shipped_console_and_print_styles_obey_the_existing_scanner(tmp_path):
    assert style_tree(tmp_path) == []


def test_print_page_canvas_and_footer_use_the_verified_light_palette():
    document = json.loads((ROOT / "apps/web/design/tokens.json").read_text())
    generated = generator.render(document)
    assert generated == (ROOT / "apps/web/src/styles/tokens.css").read_text()
    light = document["themes"]["light"]
    assert light["surface-1"] == "#FFFFFF"
    assert f"@page {{\n  background: {light['surface-1']};" in generated
    assert f"@bottom-center {{ color: {light['text-secondary']}; }}" in generated
    # The page colours must be generated from the palette, rather than copied literals.
    document["themes"]["light"]["surface-1"] = "#FEFEFE"
    assert "@page {\n  background: #FEFEFE;" in generator.render(document)


@pytest.mark.parametrize(
    ("name", "addition", "rule"),
    [
        ("print.css", "\n@page { background: #FF00FF; }", "color-outside-tokens"),
        ("mission-control.css", "\n.mc-panel { border-radius: 12px; }", "large-radius"),
    ],
)
def test_print_and_console_still_reject_unapproved_literals_and_corners(tmp_path, name, addition, rule):
    assert rule in {finding["rule"] for finding in style_tree(tmp_path, (name, addition))}
