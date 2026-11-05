#!/usr/bin/env python3
"""Validate shared team guides; optionally verify the root's three worktrees."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--check-git', action='store_true', help='Run only from integrator root after worktree creation')
    parser.add_argument('--report', type=Path, help='Optional report path; keep dynamic reports in ignored .local-team/')
    args = parser.parse_args()
    root = args.repo.resolve()
    errors: list[str] = []
    checks: dict[str, int] = {}
    required = ['README.md', 'CODING-AGENT-PROMPT.md', '01-SCOPE-AND-FILE-OWNERSHIP.md',
                '02-IMPLEMENTATION-PLAN.md', '03-ARCHITECTURE-READING-MAP.md',
                '04-SERVICE-INTERFACES-AND-HANDOFFS.md', '05-TEST-AND-MERGE-GATES.md',
                '06-HANDOFF-CHECKLIST.md', '07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md',
                '08-MODULE-SPECIFICATION.md', '09-SELF-AUDIT-AND-LOOPHOLE-CHECKLIST.md', 'STATUS-TEMPLATE.json']
    registry = json.loads((root / 'team coordination/contracts/ownership.json').read_text())
    for person, spec in registry['people'].items():
        if person == 'merging':
            continue
        for name in required:
            if not (root / 'team guides' / spec['name'] / name).is_file():
                errors.append(f'Missing {spec["name"]}/{name}')
        prompt = (root / 'team guides' / spec['name'] / 'CODING-AGENT-PROMPT.md').read_text()
        if spec['branch'] not in prompt:
            errors.append(f'Missing expected branch in {person} prompt')
    checks['personal_required_files'] = len(required) * 3

    docs = [root / 'README.md']
    for directory in ['team guides', 'team coordination']:
        docs.extend((root / directory).rglob('*.md'))
        for path in (root / directory).rglob('*.json'):
            try:
                json.loads(path.read_text())
                checks['json_documents'] = checks.get('json_documents', 0) + 1
            except ValueError as exc:
                errors.append(f'Invalid JSON {path.relative_to(root)}: {exc}')
    for path in docs:
        content = path.read_text()
        if sum(line.startswith('```') for line in content.splitlines()) % 2:
            errors.append(f'Unbalanced code fence {path.relative_to(root)}')
        for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', content):
            target = target.strip().strip('<>')
            if target.startswith(('https:', 'http:', 'mailto:', '#')):
                continue
            file_part = unquote(target.split('#')[0])
            if file_part and not (path.parent / file_part).exists():
                errors.append(f'Broken link {path.relative_to(root)} -> {target}')
            checks['local_links'] = checks.get('local_links', 0) + 1
    checks['markdown_documents'] = len(docs)

    baseline = json.loads((root / 'team coordination/contracts/architecture-baseline.json').read_text())
    for entry in baseline['files']:
        path = root / entry['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            errors.append(f'Original architecture changed/missing: {entry["path"]}')
    checks['architecture_snapshot_files'] = len(baseline['files'])

    rules = registry['rules']
    if len({(r['path'], r['kind']) for r in rules}) != len(rules):
        errors.append('Duplicate ownership rules')
    for rule in rules:
        if rule['owner'] not in registry['people'] or rule['kind'] not in {'file', 'prefix'}:
            errors.append(f'Invalid ownership rule {rule}')
    checks['ownership_rules'] = len(rules)
    for path in (root / 'team coordination/scripts').glob('*.py'):
        try:
            compile(path.read_text(), str(path), 'exec')
            checks['compiled_helper_scripts'] = checks.get('compiled_helper_scripts', 0) + 1
        except SyntaxError as exc:
            errors.append(str(exc))

    git_report = {'checked': args.check_git}
    if args.check_git:
        def git(repo: Path, *items: str) -> str:
            p = subprocess.run(['git', '-C', str(repo), *items], capture_output=True, text=True)
            if p.returncode:
                raise RuntimeError(p.stderr.strip() or p.stdout.strip())
            return p.stdout.strip()
        try:
            git_report['root_branch'] = git(root, 'branch', '--show-current')
            if git_report['root_branch'] != 'main':
                errors.append('Integrator root must stay on main')
            common_raw = Path(git(root, 'rev-parse', '--git-common-dir'))
            common = (common_raw if common_raw.is_absolute() else root / common_raw).resolve()
            git_report['worktrees'] = []
            for key, spec in registry['people'].items():
                if key == 'merging':
                    continue
                checkout = root / spec['worktree']
                branch = git(checkout, 'branch', '--show-current')
                actual_root = Path(git(checkout, 'rev-parse', '--show-toplevel')).resolve()
                raw = Path(git(checkout, 'rev-parse', '--git-common-dir'))
                actual_common = (raw if raw.is_absolute() else checkout / raw).resolve()
                clean = not bool(git(checkout, 'status', '--porcelain'))
                if branch != spec['branch'] or actual_root != checkout.resolve() or actual_common != common:
                    errors.append(f'Wrong branch/check-out/shared repository for {spec["name"]}')
                for entry in baseline['files']:
                    path = checkout / entry['path']
                    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                        errors.append(f'Missing/different branch architecture: {spec["name"]}/{entry["path"]}')
                git_report['worktrees'].append({'person': spec['name'], 'path': str(checkout),
                    'branch': branch, 'head': git(checkout, 'rev-parse', 'HEAD'), 'clean': clean})
                checks['verified_worktrees'] = checks.get('verified_worktrees', 0) + 1
            git_report['root_clean'] = not bool(git(root, 'status', '--porcelain'))
            git_report['remotes'] = git(root, 'remote').splitlines()
        except (OSError, RuntimeError) as exc:
            errors.append(f'Git setup check failed: {exc}')

    report = {'status': 'PASS' if not errors else 'FAIL', 'checks': checks, 'git': git_report,
              'errors': errors, 'scope': 'Planning/setup integrity only; no application implementation or live-source test is certified.'}
    if args.report:
        destination = args.report.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
