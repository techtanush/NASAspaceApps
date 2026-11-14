from hashlib import sha256

import pytest

from analogforge.rendering.passport import create_passport_renderer


@pytest.mark.parametrize("fmt", ["html", "json", "csv"])
def test_determinism(bundle, fmt):
    renderer = create_passport_renderer()
    outputs = [renderer.render(bundle, [], fmt) for _ in range(3)]
    assert outputs[0] == outputs[1] == outputs[2]
    assert outputs[0].sha256 == sha256(outputs[0].content).hexdigest()
    assert outputs[0].sha256 != bundle.manifest_sha256
    assert outputs[0].filename.startswith(f"analogforge-passport-{bundle.mode}-")
    assert renderer.renderer_version == "1.0.0"


def test_separate_process_hash_seeds():
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    script = """
import json
from pathlib import Path
from analogforge.ports.passport_renderer import PassportExportBundle
from analogforge.rendering.passport import create_passport_renderer
renderer = create_passport_renderer()
results = []
for path in sorted(Path('tests/unit/passport_renderer/fixtures/bundles').glob('*.json')):
    bundle = PassportExportBundle.model_validate_json(path.read_bytes())
    for fmt in ['html','json','csv']:
        results.append(renderer.render(bundle, [], fmt).sha256)
print(json.dumps(results))
"""
    outputs = []
    for seed in ("1", "2", "3"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        result = subprocess.run(  # noqa: S603 — static interpreter/script only
            [sys.executable, "-c", script], cwd=root, env=env, capture_output=True, text=True, check=True
        )  # noqa: S603
        outputs.append(json.loads(result.stdout))
    assert len(outputs[0]) == 27
    assert outputs[0] == outputs[1] == outputs[2]
