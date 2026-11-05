#!/usr/bin/env python3
"""Read-only changed-path ownership check for a contributor branch (kit-aware).

Exit 0 only when: the checked-out branch is the person's branch, every changed path is owned by
that person (longest-prefix registry) OR is an exact frozen-kit file, pyproject.toml differs from the kit
only inside the person's own extra-<name> list, and no kit file was deleted or modified.
`--person merging` skips ownership (the merging agent may touch anything) but still reports kit drift.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

EXTRA_START = re.compile(r'^(extra-(?:tanush|ayan|aradhya)) = \[')


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


def extra_bodies(text: str) -> dict[str, tuple[str, ...]]:
    """Map extra-<name> -> body lines between the opening line and the closing bracket."""
    out: dict[str, tuple[str, ...]] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        match = EXTRA_START.match(lines[i])
        if match:
            name, body = match.group(1), []
            if lines[i].rstrip().endswith(']'):
                inline = lines[i].split('[', 1)[1].rsplit(']', 1)[0].strip()
                body = [inline] if inline else []
            else:
                i += 1
                while i < len(lines) and lines[i].strip() != ']':
                    body.append(lines[i].strip())
                    i += 1
            out[name] = tuple(b for b in body if b)
        i += 1
    return out


def normalized(text: str) -> str:
    lines, out, i = text.splitlines(), [], 0
    while i < len(lines):
        match = EXTRA_START.match(lines[i])
        if match:
            out.append(f'{match.group(1)} = []')
            if not lines[i].rstrip().endswith(']'):
                i += 1
                while i < len(lines) and lines[i].strip() != ']':
                    i += 1
        else:
            out.append(lines[i])
        i += 1
    return '\n'.join(out)


def kit_state(repo: Path):
    manifest_path = repo / 'architecture files/contracts/kit/kit-manifest.json'
    if not manifest_path.is_file():
        return {}
    manifest = json.loads(manifest_path.read_text())
    return {'analogforge/' + rel: digest for rel, digest in manifest['files'].items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--person', required=True, type=str.lower,
                        choices=['tanush', 'ayan', 'aradhya', 'merging'])
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

    kit = kit_state(repo)
    kit_pyproject = None
    kp = repo / 'architecture files/contracts/kit/files/pyproject.toml'
    if kp.is_file():
        kit_pyproject = kp.read_text()
    violations, kit_ok = [], []
    for path in paths:
        full = repo / path
        if path in kit:
            if not full.exists():
                violations.append({'path': path, 'reason': 'kit file deleted'})
                continue
            if path == 'analogforge/pyproject.toml' and kit_pyproject is not None:
                text = full.read_text()
                mine = f'extra-{args.person}'
                others_ok = all(extra_bodies(text).get(name, ()) == extra_bodies(kit_pyproject).get(name, ())
                                for name in extra_bodies(kit_pyproject) if name != mine)
                if args.person == 'merging' or (normalized(text) == normalized(kit_pyproject) and others_ok):
                    kit_ok.append(path)
                else:
                    violations.append({'path': path, 'reason': 'pyproject.toml differs from kit outside own extra list'})
                continue
            if hashlib.sha256(full.read_bytes()).hexdigest() == kit[path]:
                kit_ok.append(path)
            else:
                violations.append({'path': path, 'reason': 'frozen kit file modified'})
            continue
        if path.startswith('analogforge/src/analogforge/ports/') and args.person != 'merging':
            violations.append({'path': path, 'reason': 'foreign file in kit-only ports package'})
            continue
        if args.person == 'merging':
            continue
        owner = owner_for(path, registry['rules'])
        if owner != args.person:
            violations.append({'path': path, 'reason': 'owned by ' + str(owner)})
    report = {'status': 'PASS' if branch == expected and not violations else 'FAIL',
              'person': args.person, 'repository': str(repo), 'branch': branch,
              'expected_branch': expected, 'head': head, 'accepted_base': base,
              'changed_path_count': len(paths), 'changed_paths': paths,
              'kit_files_unchanged_copies': kit_ok,
              'ownership_violations': violations,
              'note': 'Path ownership and kit integrity only. This does not certify tests, secrets, scientific validity or merge readiness.'}
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
