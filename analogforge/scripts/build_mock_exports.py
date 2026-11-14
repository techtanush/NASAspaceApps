"""Create development exports using the real, pure passport renderer.

Run from analogforge/. Synthetic presentation bundles are generated in the
renderer test fixture builder, validated through the frozen port, then rendered.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "unit"))

from passport_renderer.fixtures.builders import FIXTURE_NAMES, build_bundle  # noqa: E402

from analogforge.rendering.passport import create_passport_renderer  # noqa: E402


def main() -> None:
    target = ROOT / "apps" / "web" / "src" / "mock" / "exports"
    target.mkdir(parents=True, exist_ok=True)
    fixtures = ROOT / "tests" / "unit" / "passport_renderer" / "fixtures" / "bundles"
    fixtures.mkdir(parents=True, exist_ok=True)
    index: dict[str, Any] = {}
    renderer = create_passport_renderer()
    for name in FIXTURE_NAMES:
        bundle = build_bundle(name)
        (fixtures / f"{name}.json").write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
        index[name] = dict(bundle=bundle.model_dump(mode="json"), manifestSha=bundle.manifest_sha256, exports={})
        for fmt in ("html", "json", "csv"):
            result = renderer.render(bundle, [], fmt)
            file = f"{name}.{fmt}"
            (target / file).write_bytes(result.content)
            index[name]["exports"][fmt] = dict(
                file=file, sha256=result.sha256, mediaType=result.media_type, filename=result.filename
            )
    (target / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "PASS", "bundles": len(index), "exports": len(index) * 3}))


if __name__ == "__main__":
    main()
