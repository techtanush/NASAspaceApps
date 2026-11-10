import json
import sys
import tempfile
from pathlib import Path

app = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(app / "tests/fixtures/science"))
sys.path.insert(0, str(app / "tests/integration/science"))
from test_determinism import _flow, _no_elapsed
from analogforge.ports.hashing import canonical_sha256

with tempfile.TemporaryDirectory() as directory:
    _, _, results = _flow(Path(directory))
    receipts = [
        dict(operation=r.operation.value, status=r.status.value, params=r.parameters_sha256,
             payload=_no_elapsed(r.payload.model_dump(mode="json")) if r.payload is not None else None,
             artifacts=[dict(key=a.local_key, sha256=a.sha256, size=a.size_bytes) for a in r.artifacts],
             evidence_parameters=[e.parameters_sha256 for e in r.evidence_drafts])
        for r in results
    ]
Path(sys.argv[2]).write_text(json.dumps(dict(sha256=canonical_sha256(receipts), results=receipts),
                                      sort_keys=True, indent=2) + "\n")
