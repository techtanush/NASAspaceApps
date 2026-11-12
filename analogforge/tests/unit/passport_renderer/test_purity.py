import json
import subprocess
import sys
from pathlib import Path

from analogforge.rendering.passport import create_passport_renderer

from .fixtures.builders import build_bundle


def test_renderer_import_does_not_import_network_or_platform():
    script = """
import sys, json
import analogforge.ports.passport_renderer
baseline = set(sys.modules)
import analogforge.rendering.passport
forbidden = ['socket','http.client','urllib.request','requests','httpx','sqlalchemy','psycopg','openai','fastapi']
print(json.dumps([m for m in forbidden if m in sys.modules and m not in baseline]))
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)  # noqa: S603
    assert json.loads(result.stdout) == []


def test_renderer_has_no_impure_calls():
    root = Path(__file__).parents[3] / "src" / "analogforge" / "rendering" / "passport"
    for file in root.rglob("*.py"):
        text = file.read_text()
        for token in ("datetime.now", "time.time", "os.environ", "requests.", "httpx.", "socket."):
            assert token not in text, (file, token)


def test_many_attempts_and_empty_candidates():
    bundle = build_bundle()
    first = bundle.attempts[0]
    bundle = bundle.model_copy(
        update={"attempts": [first.model_copy(update={"attempt_number": i}) for i in range(1, 51)]}
    )
    text = create_passport_renderer().render(bundle, [], "html").content.decode()
    assert text.count("data-attempt-number=") == 50
    bundle = build_bundle("draft")
    bundle = bundle.model_copy(update={"candidates": [], "qualifications": []})
    assert create_passport_renderer().render(bundle, [], "html").content
