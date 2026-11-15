"""Only the reviewed EOX vintage endpoint and its exact attribution links are allowed."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("imagery_forbidden_scan", ROOT / "scripts/ui/forbidden_scan.py")
assert SPEC and SPEC.loader
scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scanner)


@pytest.mark.parametrize("path,urls", scanner.IMAGERY_URLS.items())
def test_exact_reviewed_urls_are_allowed_only_in_their_module(path, urls):
    for url in urls:
        assert scanner.approved_imagery_url_line(path, f"const url = '{url}';")
        assert not scanner.approved_imagery_url_line("apps/web/src/maps/Other.tsx", f"const url = '{url}';")
        for changed in (url + "?token=private", url + "/other", url.replace("https:", "http:"),
                        url.replace("://", "://unapproved.")):
            assert not scanner.approved_imagery_url_line(path, f"const url = '{changed}';")


def test_unreviewed_url_on_an_approved_line_still_fails():
    path = "apps/web/src/api/earthImagery.ts"
    url = next(iter(scanner.IMAGERY_URLS[path]))
    assert not scanner.approved_imagery_url_line(path, f"const urls = ['{url}', 'https://other.example'];")
    assert not scanner.approved_imagery_url_line(path, "const url = 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2025';")
