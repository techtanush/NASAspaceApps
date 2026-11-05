#!/usr/bin/env python3
"""Read-only changed-path ownership check for a contributor branch."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def owner_for(path: str, rules: list[dict]) -> str | None:
    matches = [r for r in rules if (path == r['path'] if r['kind'] == 'file'
                                    else path.startswith(r['path']))]
    return max(matches, key=lambda r: len(r['path']))['owner'] if matches else None


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(['git', '-C', str(repo), *args], text=True,
                            capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--person', required=True, type=str.lower,
                        choices=['tanush', 'ayan', 'aradhya'])
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--base', default='main', help='Accepted integration ref, not a guessed SHA')
    args = parser.parse_args()
    repo = args.repo.resolve()
    registry = json.loads((repo / 'team coordination/contracts/ownership.json').read_text())
    expected = registry['people'][args.person]['branch']
    try:
        branch = git(repo, 'branch', '--show-current').strip()
        head = git(repo, 'rev-parse', 'HEAD').strip()
        base = git(repo, 'rev-parse', '--verify', args.base + '^{commit}').strip()
        committed = git(repo, 'diff', '--name-only', '--no-renames', '-z', args.base + '...HEAD')
        working = git(repo, 'diff', '--name-only', '--no-renames', '-z', 'HEAD')
        untracked = git(repo, 'ls-files', '--others', '--exclude-standard', '-z')
        paths = sorted(set(p for p in (committed + working + untracked).split('\0') if p))
    except RuntimeError as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}, indent=2))
        return 1
    violations = [{'path': path, 'owner': owner_for(path, registry['rules'])}
                  for path in paths if owner_for(path, registry['rules']) != args.person]
    report = {'status': 'PASS' if branch == expected and not violations else 'FAIL',
              'person': args.person, 'repository': str(repo), 'branch': branch,
              'expected_branch': expected, 'head': head, 'accepted_base': base,
              'changed_path_count': len(paths), 'changed_paths': paths,
              'ownership_violations': violations,
              'note': 'Path ownership only. This does not certify tests, secrets, scientific validity or merge readiness.'}
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
