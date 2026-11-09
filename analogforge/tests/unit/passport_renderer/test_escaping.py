import csv
import io
import json

import pytest

from analogforge.rendering.passport import create_passport_renderer
from passport_renderer.fixtures.builders import build_bundle


@pytest.mark.parametrize(
    "hostile", ["=2+3", "+SUM(A1)", "-cmd", "@SUM(A1)", "\t=cmd", "\r=cmd", "</script><script>alert(1)</script>"]
)
def test_hostile_text(hostile):
    bundle = build_bundle()
    bundle.candidates[0].name = hostile
    renderer = create_passport_renderer()
    html = renderer.render(bundle, [], "html").content.decode()
    assert "<script>" not in html and "</script>" not in html
    output = json.loads(renderer.render(bundle, [], "json").content)
    assert output["bundle"]["candidates"][0]["name"] == hostile
    rows = list(csv.DictReader(io.StringIO(renderer.render(bundle, [], "csv").content.decode())))
    assert rows[0]["candidate_name"] == ("'" + hostile if hostile[0] in "=+-@\t\r" else hostile)


def test_svg_stylesheet_processing_instruction_is_rejected():
    import hashlib

    from analogforge.ports.passport_renderer import ProvidedAsset, RendererError

    source = b'<?xml-stylesheet type="text/css" href="https://attacker.invalid/style.css"?><svg xmlns="http://www.w3.org/2000/svg"/>'
    asset = ProvidedAsset(
        asset_key="unsafe-pi",
        media_type="image/svg+xml",
        content=source,
        sha256=hashlib.sha256(source).hexdigest(),
    )
    with pytest.raises(RendererError, match="UNSAFE_ASSET"):
        create_passport_renderer().render(build_bundle(), [asset], "html")
