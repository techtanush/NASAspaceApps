"""Lossless, versioned machine-readable export."""

import json

from analogforge.ports.passport_renderer import PassportExportBundle


def render_json(bundle: PassportExportBundle) -> bytes:
    data = {
        "export_schema_version": "1.0",
        "manifest_sha256": bundle.manifest_sha256,
        "canonical_manifest": json.loads(bundle.canonical_manifest_json),
        "bundle": bundle.model_dump(mode="json", exclude={"canonical_manifest_json"}),
    }
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
