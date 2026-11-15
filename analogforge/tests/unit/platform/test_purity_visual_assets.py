"""The globe asset exception cannot authorize unrelated or changed large files."""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location("merge_purity", REPO / "merging guide/scripts/purity_check.py")
assert SPEC is not None and SPEC.loader is not None
PURITY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PURITY)


def test_only_exact_reviewed_visual_bytes_are_exempted(tmp_path):
    for rel in PURITY.SHIPPED_VISUAL_ASSETS:
        assert PURITY.reviewed_visual_asset(REPO, rel)
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (REPO / rel).read_bytes()
        target.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        assert not PURITY.reviewed_visual_asset(tmp_path, rel)
        target.write_bytes(raw + b"changed")
        assert not PURITY.reviewed_visual_asset(tmp_path, rel)
    assert not PURITY.reviewed_visual_asset(REPO, "analogforge/data/arbitrary.jpg")
    assert not PURITY.reviewed_visual_asset(REPO, "analogforge/apps/web/public/globe/unreviewed.jpg")


def test_symlinks_cannot_authorize_an_asset_exception(tmp_path):
    rel = next(iter(PURITY.SHIPPED_VISUAL_ASSETS))
    target = tmp_path / rel
    target.parent.mkdir(parents=True)
    target.symlink_to(REPO / rel)
    assert not PURITY.reviewed_visual_asset(tmp_path, rel)
