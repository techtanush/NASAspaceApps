"""The glass layer is exempt from two UI scanner rules, so these tests prove the exemption is narrow.

Each case damages a copy of the real glass.css (or adds a violation elsewhere) and requires the scanner to fail with
the specific rule. They guard decision D-2026-11-13-GLASS: glass exists only on listed surfaces, within limits, over one
ambient backdrop, with token-derived colours, dark below-the-element shadows and four fallbacks.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("ui_forbidden_scan", ROOT / "scripts/ui/forbidden_scan.py")
assert SPEC and SPEC.loader
scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scanner)

GLASS = ROOT / "apps/web/src/styles/glass.css"
CONTRACT = ROOT / "apps/web/design/glass-surfaces.json"


def scan_tree(tmp_path: Path, css: str, extra: dict[str, str] | None = None) -> list[dict[str, object]]:
    (tmp_path / "apps/web/src/styles").mkdir(parents=True)
    (tmp_path / "apps/web/design").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/build_mock_exports.py").write_text("")  # the scanner always reads this file
    (tmp_path / "apps/web/src/styles/glass.css").write_text(css)
    shutil.copy(CONTRACT, tmp_path / "apps/web/design/glass-surfaces.json")
    for name, content in (extra or {}).items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(content)
    return scanner.scan(tmp_path)


def rules(findings: list[dict[str, object]]) -> set[str]:
    return {str(finding["rule"]) for finding in findings}


def test_the_shipped_glass_layer_satisfies_its_contract(tmp_path):
    assert scan_tree(tmp_path, GLASS.read_text()) == []


def test_the_contract_lists_are_disjoint_and_selectors_are_classes():
    contract = json.loads(CONTRACT.read_text())
    lists = [set(contract[key]) for key in ("chrome", "panels", "frames")]
    assert not (lists[0] & lists[1]) and not (lists[0] & lists[2]) and not (lists[1] & lists[2])
    assert all(selector.startswith(".") for group in lists for selector in group)
    assert contract["limits"]["blur_px_max"] <= 24 and contract["limits"]["radius_px_max"] <= 14


MUTATIONS = {
    "blur-on-an-unlisted-control": (".button { backdrop-filter: blur(8px); }", {"glass-unlisted-surface"}),
    "blur-on-a-data-frame": (".table-frame { backdrop-filter: blur(8px); }", {"glass-unlisted-surface"}),
    "blur-above-the-limit": (".panel { backdrop-filter: blur(40px); }", {"glass-blur-unbounded"}),
    "unbounded-blur-expression": (".panel { backdrop-filter: blur(var(--missing)); }", {"glass-blur-unbounded"}),
    "foreign-filter-function": (".panel { backdrop-filter: blur(8px) hue-rotate(40deg); }", {"glass-filter-function"}),
    "linear-gradient-on-chrome": (".app-header { background-image: linear-gradient(red, blue); }", {"glass-gradient-kind", "glass-gradient-outside-ambient"}),
    "radial-gradient-on-a-panel": (".panel { background-image: radial-gradient(circle, transparent, transparent); }", {"glass-gradient-outside-ambient"}),
    "radius-above-the-limit": (".panel { border-radius: 20px; }", {"glass-radius-too-large"}),
    "large-radius-on-a-control": (".button { border-radius: 12px; }", {"glass-radius-unlisted"}),
    "coloured-glow": (".panel { box-shadow: 0 0 24px color-mix(in srgb, var(--accent) 60%, transparent); }", {"glass-coloured-shadow", "glass-shadow-halo"}),
    "neutral-glow-without-offset": (".panel { box-shadow: 0 0 18px color-mix(in srgb, var(--glass-ink) 60%, transparent); }", {"glass-shadow-halo"}),
    "inset-glow": (".panel { box-shadow: inset 0 0 12px var(--glass-sheen); }", {"glass-inset-halo"}),
    "shadow-ink-from-a-brand-colour": (":root { --glass-ink: var(--accent); }", {"glass-shadow-ink"}),
    "ambient-layer-captures-pointer": (".ambient-canvas { pointer-events: auto; }", {"glass-ambient-interactive"}),
    "ambient-layer-above-content": (".ambient-canvas { z-index: 5; }", {"glass-ambient-layering"}),
    "text-shadow": (".panel { text-shadow: 0 1px 2px var(--canvas); }", {"decorative-effect"}),
    "hex-colour": (".panel { border-color: #ff00ff; }", {"color-outside-tokens"}),
    "rgb-colour": (".panel { border-color: rgb(255 0 255); }", {"color-outside-tokens"}),
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_every_violation_of_the_glass_contract_is_caught(tmp_path, name):
    addition, expected = MUTATIONS[name]
    caught = rules(scan_tree(tmp_path, GLASS.read_text() + "\n" + addition + "\n"))
    assert expected <= caught, f"{name}: expected {expected}, scanner reported {caught}"


@pytest.mark.parametrize("fallback", json.loads(CONTRACT.read_text())["required_fallbacks"])
def test_removing_any_required_fallback_is_caught(tmp_path, fallback):
    css = GLASS.read_text().replace(fallback, "removed-fallback-marker")
    assert "glass-missing-fallback" in rules(scan_tree(tmp_path, css))


def test_the_exemption_does_not_extend_to_any_other_stylesheet(tmp_path):
    for index, (declaration, rule) in enumerate((
        ("backdrop-filter: blur(4px)", "decorative-effect"),
        ("background-image: linear-gradient(red, blue)", "decorative-effect"),
        ("background-image: radial-gradient(circle, red, blue)", "decorative-effect"),
        ("border-radius: 12px", "large-radius"),
    )):
        other = tmp_path / f"case{index}"
        findings = scan_tree(other, GLASS.read_text(), {"apps/web/src/styles/polish.css": f".panel {{ {declaration}; }}\n"})
        assert rule in rules(findings), f"{declaration} in polish.css must still fail"


def test_a_missing_contract_fails_closed(tmp_path):
    (tmp_path / "apps/web/src/styles").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/build_mock_exports.py").write_text("")
    (tmp_path / "apps/web/src/styles/glass.css").write_text(GLASS.read_text())
    assert "glass-contract-missing" in rules(scanner.scan(tmp_path))
