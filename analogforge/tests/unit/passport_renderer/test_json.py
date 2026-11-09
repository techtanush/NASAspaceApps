import json
from hashlib import sha256

import rfc8785

from analogforge.ports.hashing import canonical_sha256
from analogforge.rendering.passport import create_passport_renderer


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
