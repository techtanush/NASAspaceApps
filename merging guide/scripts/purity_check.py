#!/usr/bin/env python3
"""Structural purity checks for one builder branch (or the merged tree).

    python3 "merging guide/scripts/purity_check.py" --person ayan --repo ../af-verify-ayan --base origin/main --json out/purity-ayan.json

Automates generic checks G-01..G-06 and G-09 of 02-BRANCH-PURITY-CHECKS.md plus the forbidden-pattern scan.
It does NOT replace running the builder's gates (G-08), mutation re-runs (G-10) or the hunts (G-11): those are manual.
With --person merging it scans the whole tree for forbidden patterns, secrets and large files only.
Exit 0 only if every executed check passes.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

CODE_EXT = {'.py', '.ts', '.tsx', '.js', '.jsx', '.mjs'}
COMMON_PATTERNS = {
    'NOT_IMPLEMENTED': re.compile(r'NotImplementedError'),
    'TODO_MARKER': re.compile(r'\b(TODO|FIXME|HACK|XXX)\b'),
    'SWALLOWED_EXCEPTION': re.compile(r'except(\s+Exception)?\s*:\s*\n\s*pass\b'),
    'SKIPPED_TEST': re.compile(r'pytest\.skip|pytest\.mark\.skip|pytest\.mark\.xfail|\bit\.skip|\btest\.skip|\btest\.fixme|\bdescribe\.skip|\bxit\(|\.only\('),
}
SECRET_PATTERNS = {
    'OPENAI_KEY_LITERAL': re.compile(r'sk-[A-Za-z0-9_-]{20,}'),
    'PRIVATE_KEY': re.compile(r'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY'),
    'DSN_WITH_PASSWORD': re.compile(r'postgres(ql)?(\+\w+)?://[^:\s/]+:(?!change-me|password|example|\$\{)[^@\s]{8,}@'),
    'BEARER_TOKEN': re.compile(r'Bearer [A-Za-z0-9._-]{24,}'),
}
BIG_EXT = {'.tif', '.tiff', '.hgt', '.nc', '.img', '.zip', '.h5', '.npz', '.png', '.jpg'}
SCOPES = {
    'tanush': {
        'dirs': ['analogforge/src/analogforge', 'analogforge/tests/unit/platform', 'analogforge/tests/integration/platform',
                 'analogforge/tests/contracts/platform', 'analogforge/tests/support'],
        'skip': ['analogforge/src/analogforge/ports/', 'analogforge/src/analogforge/science/', 'analogforge/src/analogforge/rendering/passport/',
                 'analogforge/src/analogforge/rendering/tiles/', 'analogforge/src/analogforge/adapters/earthdata/', 'analogforge/src/analogforge/adapters/pds/',
                 'analogforge/src/analogforge/adapters/emit/', 'analogforge/src/analogforge/adapters/diviner/',
                 'analogforge/src/analogforge/adapters/user_survey/', 'analogforge/src/analogforge/adapters/source_http/'],
        'extra': {
            'PRACTICE_WINDOW_LITERAL_IN_SRC': re.compile(r'grid-r\dc\d|graph-zone'),
            'PRINT_IN_SRC': re.compile(r'^\s*print\(', re.M),
        },
        'extra_src_only': {'PRACTICE_WINDOW_LITERAL_IN_SRC', 'PRINT_IN_SRC'},
    },
    'ayan': {
        'dirs': ['analogforge/src/analogforge/science', 'analogforge/src/analogforge/adapters/earthdata', 'analogforge/src/analogforge/adapters/pds',
                 'analogforge/src/analogforge/adapters/emit', 'analogforge/src/analogforge/adapters/diviner',
                 'analogforge/src/analogforge/adapters/user_survey', 'analogforge/src/analogforge/adapters/source_http',
                 'analogforge/src/analogforge/rendering/tiles', 'analogforge/tests/unit/science', 'analogforge/tests/property/science',
                 'analogforge/tests/integration/science', 'analogforge/tests/replay/science', 'analogforge/tests/contracts/science',
                 'analogforge/scripts/science'],
        'skip': [],
        'extra': {
            'ENV_ACCESS': re.compile(r'os\.environ|os\.getenv|\bgetenv\('),
            'PRACTICE_WINDOW_LITERAL_IN_DECISION_CODE': re.compile(r'grid-r\dc\d'),
        },
        'extra_src_only': {'ENV_ACCESS', 'PRACTICE_WINDOW_LITERAL_IN_DECISION_CODE'},
        'allow_in': {'PRACTICE_WINDOW_LITERAL_IN_DECISION_CODE': ['/fixtures/']},
    },
    'aradhya': {
        'dirs': ['analogforge/apps/web/src', 'analogforge/src/analogforge/rendering/passport', 'analogforge/tests/unit/passport_renderer',
                 'analogforge/tests/e2e', 'analogforge/tests/contracts/ui', 'analogforge/scripts/ui'],
        'skip': ['analogforge/apps/web/src/generated/'],
        'extra': {
            'UNSAFE_HTML': re.compile(r'dangerouslySetInnerHTML|\.innerHTML\s*=|\beval\(|new Function\(|document\.write'),
            'LOCALSTORAGE_STATE': re.compile(r'localStorage|sessionStorage'),
            'RENDERER_TIME_OR_ENV': re.compile(r'datetime\.now|time\.time\(|os\.environ|\bgetenv\('),
        },
        'extra_src_only': set(),
        'only_in': {'RENDERER_TIME_OR_ENV': ['analogforge/src/analogforge/rendering/passport/']},
    },
}
FORBIDDEN_IMPORTS = {
    'tanush': ('analogforge.science', 'analogforge.rendering.passport'),
    'ayan': ('fastapi', 'sqlalchemy', 'psycopg', 'openai', 'analogforge.api', 'analogforge.db', 'analogforge.jobs',
             'analogforge.application', 'analogforge.agents', 'analogforge.tools', 'analogforge.rendering.passport'),
}
IMPORT_SCAN_SKIP_TESTS = {'tanush'}  # tests may import the real entry points (AF_*_IMPL=real); production code may not
RENDERER_ALLOWED_TOP = {'jinja2', 'markupsafe', 'pydantic', 'analogforge', '__future__'}


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)
    return p.returncode, (p.stdout + p.stderr).strip()


def tracked(repo: Path) -> list[str]:
    code, out = run(['git', '-C', str(repo), 'ls-files', '-z'])
    return [p for p in out.split('\0') if p] if code == 0 else []


def scan_files(repo: Path, files: list[str], patterns: dict[str, re.Pattern], *, is_test_path=lambda p: False,
               allow_in: dict[str, list[str]] | None = None, only_in: dict[str, list[str]] | None = None,
               src_only: set[str] | None = None) -> list[dict]:
    findings = []
    for rel in files:
        path = repo / rel
        if path.suffix not in CODE_EXT or not path.is_file():
            continue
        try:
            text = path.read_text(errors='ignore')
        except OSError:
            continue
        for name, rx in patterns.items():
            if src_only and name in src_only and is_test_path(rel):
                continue
            if allow_in and any(a in '/' + rel for a in allow_in.get(name, [])):
                continue
            if only_in and name in only_in and not any(rel.startswith(o) for o in only_in[name]):
                continue
            for m in rx.finditer(text):
                line = text.count('\n', 0, m.start()) + 1
                findings.append({'file': rel, 'line': line, 'pattern': name, 'text': text.splitlines()[line - 1].strip()[:160]})
    return findings


def forbidden_import_findings(repo: Path, files: list[str], prefixes: tuple[str, ...], skip_tests: bool) -> list[dict]:
    findings = []
    for rel in files:
        if not rel.endswith('.py'):
            continue
        if skip_tests and (rel.startswith('analogforge/tests/') or '/tests/' in rel):
            continue
        try:
            tree = ast.parse((repo / rel).read_text())
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module] + [f'{node.module}.{a.name}' for a in node.names]
            for n in names:
                if any(n == p or n.startswith(p + '.') for p in prefixes):
                    findings.append({'file': rel, 'line': node.lineno, 'pattern': 'FORBIDDEN_IMPORT', 'text': n})
    return findings


def renderer_import_findings(repo: Path) -> list[dict]:
    findings = []
    base = repo / 'analogforge/src/analogforge/rendering/passport'
    if not base.is_dir():
        return findings
    for path in base.rglob('*.py'):
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError as exc:
            findings.append({'file': str(path.relative_to(repo)), 'line': exc.lineno or 0, 'pattern': 'SYNTAX_ERROR', 'text': str(exc)})
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split('.')[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module.split('.')[0]]
            for n in names:
                if n not in sys.stdlib_module_names and n not in RENDERER_ALLOWED_TOP:
                    findings.append({'file': str(path.relative_to(repo)), 'line': node.lineno, 'pattern': 'RENDERER_FORBIDDEN_IMPORT', 'text': n})
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--person', required=True, choices=['tanush', 'ayan', 'aradhya', 'merging'])
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--base', default='origin/main')
    ap.add_argument('--json', type=Path)
    args = ap.parse_args()
    repo = args.repo.resolve()
    checks: dict[str, dict] = {}

    def record(cid: str, ok: bool, notes: str = '', findings: list | None = None) -> None:
        checks[cid] = {'status': 'PASS' if ok else 'FAIL', 'notes': notes, 'findings': findings or []}

    files = tracked(repo)
    code, head = run(['git', '-C', str(repo), 'rev-parse', 'HEAD'])
    branch_code, branch = run(['git', '-C', str(repo), 'branch', '--show-current'])
    person = args.person

    if person != 'merging':
        reg = json.loads((repo / 'team coordination/contracts/ownership.json').read_text())
        expected = reg['people'][person]['branch']
        status_path = repo / f'team handoffs/{person}/STATUS.json'
        problems = []
        if branch and branch != expected and not branch.startswith('HEAD'):
            problems.append(f'branch {branch} != {expected} (detached worktrees are acceptable)')
        if not status_path.is_file():
            problems.append('STATUS.json missing')
        else:
            st = json.loads(status_path.read_text())
            if st.get('ready_to_merge') is not True:
                problems.append('STATUS.json ready_to_merge is not true')
            pushed = st.get('pushed_sha')
            if not pushed:
                problems.append('STATUS.json pushed_sha missing')
            else:
                anc, _ = run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', pushed, 'HEAD'])
                if anc != 0:
                    problems.append('pushed_sha is not an ancestor of HEAD')
            for name in ('DECISIONS.md', 'PROGRESS.md'):
                if not (repo / f'team handoffs/{person}/{name}').is_file():
                    problems.append(f'{name} missing')
        record('G-01', not problems, '; '.join(problems) or f'HEAD {head}')

        mat = repo / 'architecture files/contracts/kit/materialize.py'
        c, out = run([sys.executable, str(mat), '--verify', '--app', str(repo / 'analogforge')])
        record('G-02', c == 0, out[-400:] if c else 'kit verified')

        own = repo / 'team coordination/scripts/check_branch_ownership.py'
        c, out = run([sys.executable, str(own), '--person', person, '--repo', str(repo), '--base', args.base])
        try:
            viol = json.loads(out).get('ownership_violations', [])
        except json.JSONDecodeError:
            viol = [{'path': '?', 'reason': out[-200:]}]
        record('G-03', c == 0, 'ownership + kit integrity', viol)

        # G-06 dependency hygiene
        dep_problems = []
        if person != 'tanush' and 'analogforge/uv.lock' in files:
            dep_problems.append('uv.lock committed by a non-Tanush branch')
        if person != 'aradhya' and any(f.endswith('pnpm-lock.yaml') for f in files):
            dep_problems.append('pnpm-lock.yaml committed by a non-Aradhya branch')
        record('G-06', not dep_problems, '; '.join(dep_problems) or 'dependency files ok')

        # G-04 forbidden patterns
        scope = SCOPES[person]
        scoped = [f for f in files if any(f.startswith(d + '/') or f == d for d in scope['dirs'])
                  and not any(f.startswith(s) for s in scope['skip'])]
        is_test = lambda p: '/tests/' in '/' + p or p.startswith('analogforge/tests/') or '/test/' in p or p.endswith(('.test.ts', '.test.tsx', '.spec.ts'))
        patterns = dict(COMMON_PATTERNS)
        patterns.update(scope['extra'])
        findings = scan_files(repo, scoped, patterns, is_test_path=is_test, allow_in=scope.get('allow_in'),
                              only_in=scope.get('only_in'), src_only=scope.get('extra_src_only'))
        # LOCALSTORAGE allowed only with an explicit marker on the line
        findings = [f for f in findings if not (f['pattern'] == 'LOCALSTORAGE_STATE' and 'allowed:' in f['text'])]
        if person in FORBIDDEN_IMPORTS:
            findings += forbidden_import_findings(repo, scoped, FORBIDDEN_IMPORTS[person], person in IMPORT_SCAN_SKIP_TESTS)
        if person == 'aradhya':
            findings += renderer_import_findings(repo)
        record('G-04', not findings, f'{len(scoped)} files scanned', findings)

        # G-09 STATUS claims coherence
        claim_problems = []
        if status_path.is_file():
            st = json.loads(status_path.read_text())
            cat = st.get('catalog', {})
            if not cat:
                claim_problems.append('catalog empty')
            for cid, row in cat.items():
                s = row.get('status') if isinstance(row, dict) else row
                if s in ('NOT_RUN', 'NOT_IMPLEMENTED', 'FAILED'):
                    claim_problems.append(f'{cid} is {s}')
                if s in ('BLOCKED_ENVIRONMENT', 'BLOCKED_EXTERNAL') and not (isinstance(row, dict) and (row.get('notes') or row.get('proof'))):
                    claim_problems.append(f'{cid} blocked without proof')
            for key in ('kit_verify', 'ownership_check'):
                if st.get(key, {}).get('status') != 'PASS':
                    claim_problems.append(f'{key} not PASS in STATUS.json')
        record('G-09', not claim_problems, 'STATUS.json internal coherence (NOT a substitute for re-running gates)', [{'problem': p} for p in claim_problems])
    else:
        allfind = []
        for person_scope in SCOPES.values():
            scoped = [f for f in files if any(f.startswith(d + '/') for d in person_scope['dirs']) and not any(f.startswith(s) for s in person_scope['skip'])]
            patterns = dict(COMMON_PATTERNS)
            patterns.update(person_scope['extra'])
            is_test = lambda p: p.startswith('analogforge/tests/') or '/test/' in p or p.endswith(('.test.ts', '.test.tsx', '.spec.ts'))
            fs = scan_files(repo, scoped, patterns, is_test_path=is_test, allow_in=person_scope.get('allow_in'),
                            only_in=person_scope.get('only_in'), src_only=person_scope.get('extra_src_only'))
            allfind += [f for f in fs if not (f['pattern'] == 'LOCALSTORAGE_STATE' and 'allowed:' in f['text'])]
        for who, prefixes in FORBIDDEN_IMPORTS.items():
            sc = SCOPES[who]
            sf = [f for f in files if any(f.startswith(d + '/') for d in sc['dirs']) and not any(f.startswith(s) for s in sc['skip'])]
            allfind += forbidden_import_findings(repo, sf, prefixes, who in IMPORT_SCAN_SKIP_TESTS)
        allfind += renderer_import_findings(repo)
        record('G-04', not allfind, 'merged-tree forbidden patterns', allfind)

    # G-05 secrets / data / build output (all persons)
    sec_findings = []
    for rel in files:
        p = repo / rel
        if rel.endswith('.env.example') or rel.startswith('team guides/') or rel.startswith('merging guide/') or rel.startswith('architecture files/'):
            pass
        elif p.is_file() and p.stat().st_size < 2_000_000:
            try:
                text = p.read_text(errors='ignore')
            except OSError:
                text = ''
            for name, rx in SECRET_PATTERNS.items():
                m = rx.search(text)
                if m:
                    sec_findings.append({'file': rel, 'pattern': name, 'text': m.group(0)[:12] + '…'})
        parts = rel.split('/')
        if any(x in parts for x in ('node_modules', 'dist', '.venv', '__pycache__')) or rel.startswith('analogforge/data/') or rel.endswith('/.env') or rel == 'analogforge/.env':
            sec_findings.append({'file': rel, 'pattern': 'FORBIDDEN_TRACKED_PATH', 'text': rel})
        if p.is_file() and p.stat().st_size > 1_048_576 and Path(rel).suffix in BIG_EXT | {'.bin', '.pkl', '.parquet', '.gpkg'}:
            sec_findings.append({'file': rel, 'pattern': 'LARGE_BINARY', 'text': f'{p.stat().st_size} bytes'})
    record('G-05', not sec_findings, 'secrets/data/build output', sec_findings)

    ok = all(c['status'] == 'PASS' for c in checks.values())
    report = {'person': person, 'repo': str(repo), 'head': head, 'branch': branch, 'checks': checks, 'status': 'PASS' if ok else 'FAIL',
              'note': 'Structural checks only. Run the builder gates (G-08), mutation checks (G-10) and hunts (G-11) separately.'}
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + '\n')
    print(text)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
