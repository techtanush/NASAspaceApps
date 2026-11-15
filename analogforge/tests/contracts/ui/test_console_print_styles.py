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
    assert (ROOT / "scripts/ui/gen_tokens_css.py").read_bytes() == (
        ROOT.parent / "team guides/Aradhya/design/gen_tokens_css.py"
    ).read_bytes()
    owned_print = (ROOT / "apps/web/src/styles/print.css").read_text()
    assert "@page{background:var(--surface-1);@bottom-center{color:var(--text-secondary)}}" in owned_print
    light = document["themes"]["light"]
    assert light["surface-1"] == "#FFFFFF"
    print_theme = generated.split("@media print", 1)[1]
    assert f"--surface-1: {light['surface-1']};" in print_theme
    assert f"--text-secondary: {light['text-secondary']};" in print_theme
    # Owned page styles resolve the generated print palette, rather than copying colour literals.
    document["themes"]["light"]["surface-1"] = "#FEFEFE"
    assert "--surface-1: #FEFEFE;" in generator.render(document).split("@media print", 1)[1]


@pytest.mark.parametrize(
    ("name", "addition", "rule"),
    [
        ("print.css", "\n@page { background: #FF00FF; }", "color-outside-tokens"),
        ("mission-control.css", "\n.mc-panel { border-radius: 12px; }", "large-radius"),
    ],
)
def test_print_and_console_still_reject_unapproved_literals_and_corners(tmp_path, name, addition, rule):
    assert rule in {finding["rule"] for finding in style_tree(tmp_path, (name, addition))}
