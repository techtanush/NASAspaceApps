#!/usr/bin/env python3
"""Rewrite team coordination/contracts/architecture-baseline.json from the current architecture files.

Run only after a recorded architecture change (change process in 01). The generated report
BLUEPRINT-VALIDATION.json is excluded because validate_blueprint.py rewrites it on every run.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXCLUDE = {'architecture files/BLUEPRINT-VALIDATION.json'}


def main() -> int:
    baseline_path = ROOT / 'team coordination/contracts/architecture-baseline.json'
    old = json.loads(baseline_path.read_text())
    files = []
    for path in sorted((ROOT / 'architecture files').rglob('*')):
        rel = path.relative_to(ROOT).as_posix()
        if not path.is_file() or rel in EXCLUDE or '__pycache__' in path.parts:
            continue
        data = path.read_bytes()
        files.append({'path': rel, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    old['baseline'] = sys.argv[1] if len(sys.argv) > 1 else old['baseline']
    old['note'] = 'Refreshed by refresh_baseline.py after a recorded change (see contracts/C2-ONE-SHOT-KIT-CHANGE.json).'
    old['files'] = files
    baseline_path.write_text(json.dumps(old, indent=2) + '\n')
    print(f'baseline {old["baseline"]}: {len(files)} files')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
