import csv
import io
import json
from hashlib import sha256

import pytest
import rfc8785

from analogforge.ports.common import RuntimeMode
from analogforge.ports.hashing import canonical_sha256
from analogforge.rendering.passport import create_passport_renderer

from .fixtures.builders import build_bundle


def test_json_structure(bundle):
    content = create_passport_renderer().render(bundle, [], "json").content
    data = json.loads(content)
    assert data["export_schema_version"] == "1.0"
    assert data["manifest_sha256"] == bundle.manifest_sha256
    assert canonical_sha256(data["canonical_manifest"]) == bundle.manifest_sha256
    assert sha256(rfc8785.dumps(data["canonical_manifest"])).hexdigest() == bundle.manifest_sha256
    assert data["bundle"] == bundle.model_dump(mode="json", exclude={"canonical_manifest_json"})
    assert content.endswith(b"\n")
    assert data["bundle"]["rover"] is None if bundle.rover is None else data["bundle"]["rover"] is not None


@pytest.mark.parametrize("mode", ["synthetic", "replay", "live"])
def test_sci13_mode_labels_are_preserved_without_promoting_validation(mode: RuntimeMode):
    # These are authored display inputs, not evidence of a live execution.
    bundle = build_bundle("positive", mode_override=mode)
    renderer = create_passport_renderer()
    html = renderer.render(bundle, [], "html").content.decode()
    assert mode.upper() in html
    document = json.loads(renderer.render(bundle, [], "json").content)
    assert document["bundle"]["mode"] == mode
    assert document["canonical_manifest"]["mode"] == mode
    assert document["bundle"]["assurance"]["claims"] == [
        claim.model_dump(mode="json") for claim in bundle.assurance.claims
    ]
    rows = list(csv.DictReader(io.StringIO(renderer.render(bundle, [], "csv").content.decode())))
    assert rows and {row["mode"] for row in rows} == {mode}
