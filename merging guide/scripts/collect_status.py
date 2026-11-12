#!/usr/bin/env python3
"""Aggregate JUnit XML files and builder STATUS.json files; fail on hidden skips.

    python3 "merging guide/scripts/collect_status.py" --junit out/junit-*.xml --json out/suites.json
    python3 "merging guide/scripts/collect_status.py" --status "team handoffs"/*/STATUS.json

Exit 1 if any <skipped> element exists in the supplied JUnit files (required suites must have none),
or if any STATUS.json has ready_to_merge != true while --status is given.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_junit(path: Path) -> dict:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == 'testsuite' else list(root.iter('testsuite'))
    total = fail = err = skip = 0
    skipped_names: list[str] = []
    for s in suites:
        total += int(s.get('tests', 0))
        fail += int(s.get('failures', 0))
        err += int(s.get('errors', 0))
        skip += int(s.get('skipped', 0))
        for case in s.iter('testcase'):
            if case.find('skipped') is not None:
                skipped_names.append(f"{case.get('classname', '')}::{case.get('name', '')}")
    return {'file': str(path), 'tests': total, 'failures': fail, 'errors': err, 'skipped': skip, 'skipped_names': skipped_names,
            'passed': total - fail - err - skip}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--junit', nargs='*', default=[])
    ap.add_argument('--status', nargs='*', default=[])
    ap.add_argument('--json', type=Path)
    args = ap.parse_args()
    files = sorted({f for pattern in args.junit for f in glob.glob(pattern)})
    report: dict = {'junit': [], 'status': [], 'problems': []}
    for f in files:
        info = parse_junit(Path(f))
        report['junit'].append(info)
        if info['tests'] == 0:
            report['problems'].append(f'{f}: no tests collected')
        if info['failures'] or info['errors']:
            report['problems'].append(f"{f}: {info['failures']} failures, {info['errors']} errors")
        if info['skipped']:
            report['problems'].append(f"{f}: {info['skipped']} skipped (hidden skip): {info['skipped_names'][:5]}")
    for pattern in args.status:
        for f in sorted(glob.glob(pattern)):
            st = json.loads(Path(f).read_text())
            rows = st.get('catalog', {})
            counts: dict[str, int] = {}
            for row in rows.values():
                s = row.get('status') if isinstance(row, dict) else row
                counts[s] = counts.get(s, 0) + 1
            report['status'].append({'file': f, 'person': st.get('person'), 'ready_to_merge': st.get('ready_to_merge'), 'counts': counts,
                                     'pushed_sha': st.get('pushed_sha')})
            if st.get('ready_to_merge') is not True:
                report['problems'].append(f'{f}: ready_to_merge is not true')
    if args.junit and not files:
        report['problems'].append('no JUnit files matched')
    report['status_overall'] = 'PASS' if not report['problems'] else 'FAIL'
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + '\n')
    print(text)
    return 0 if not report['problems'] else 1


if __name__ == '__main__':
    sys.exit(main())
