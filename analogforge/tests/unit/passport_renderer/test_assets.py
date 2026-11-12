import base64
from hashlib import sha256

import pytest

from analogforge.ports.passport_renderer import ProvidedAsset, RendererError
from analogforge.rendering.passport import create_passport_renderer

from .fixtures.builders import build_bundle


def asset(content):
    return ProvidedAsset(
        asset_key="route-map", media_type="image/svg+xml", sha256=sha256(content).hexdigest(), content=content
    )


def test_svg_is_embedded_offline():
    content = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0L10 10"/><text>Route</text></svg>'
    output = create_passport_renderer().render(build_bundle(), [asset(content)], "html").content
    assert b"data:image/svg+xml;base64," + base64.b64encode(content) in output
    assert b'alt="route-map"' in output


@pytest.mark.parametrize(
    "content",
    [
        b"<svg><script>alert(1)</script></svg>",
        b'<svg onload="alert(1)"/>',
        b'<svg><image href="https://example.com/pixel"/></svg>',
        b'<svg><path style="fill:url(https://example.com/pixel)"/></svg>',
        b"<!DOCTYPE svg><svg/>",
        b"<svg><foreignObject>text</foreignObject></svg>",
        b"not xml",
    ],
)
def test_unsafe_svg_rejected(content):
    with pytest.raises(RendererError, match="UNSAFE_ASSET"):
        create_passport_renderer().render(build_bundle(), [asset(content)], "html")


def test_asset_digest_and_budget_enforced():
    image = asset(b"<svg/>").model_copy(update={"sha256": "0" * 64})
    with pytest.raises(RendererError, match="UNSAFE_ASSET"):
        create_passport_renderer().render(build_bundle(), [image], "html")
    image = asset(b"<svg/>" + b" " * 2_000_000)
    with pytest.raises(RendererError, match="UNSAFE_ASSET"):
        create_passport_renderer().render(build_bundle(), [image], "html")
