"""Development-only stdin bridge to the real pure passport renderer.

This process is launched exclusively by Vite's explicitly enabled mock-preview plugin.
It is not a production application API and never reads credentials.
"""

from __future__ import annotations

import base64
import json
import sys
from hashlib import sha256
from typing import cast

from analogforge.ports.hashing import canonical_json_bytes
from analogforge.ports.passport_renderer import ExportFormat, PassportExportBundle
from analogforge.rendering.passport import create_passport_renderer


def main() -> None:
    payload = json.load(sys.stdin)
    data = payload["bundle"]
    manifest = {
        "schema_version": "1.0",
        "mode": data["mode"],
        "run_id": data["passport"]["run_id"],
        **{
            key: data.get(key)
            for key in (
                "mission",
                "rover",
                "target_profile",
                "candidates",
                "qualifications",
                "attempts",
                "assurance",
                "source_locks",
                "critiques",
                "compatibility",
                "portfolio",
                "evidence_appendix",
                "not_run_reason",
            )
        },
    }
    canonical = canonical_json_bytes(manifest)
    data["canonical_manifest_json"] = canonical.decode("utf-8")
    data["manifest_sha256"] = sha256(canonical).hexdigest()
    data["passport"]["manifest_sha256"] = data["manifest_sha256"]
    bundle = PassportExportBundle.model_validate(data)
    fmt = cast(ExportFormat, payload["format"])
    if fmt not in {"html", "json", "csv"}:
        raise ValueError("Unsupported export format")
    rendered = create_passport_renderer().render(bundle, [], fmt)
    json.dump(
        {
            "content": base64.b64encode(rendered.content).decode("ascii"),
            "media_type": rendered.media_type,
            "filename": rendered.filename,
            "sha256": rendered.sha256,
            "manifest_sha256": bundle.manifest_sha256,
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
