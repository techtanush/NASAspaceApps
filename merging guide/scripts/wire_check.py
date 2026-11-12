#!/usr/bin/env python3
"""Seam, entry-point and configuration checks on the merged tree (run inside the merged venv).

    python3 "merging guide/scripts/wire_check.py" --repo . --stage final --json out/wire.json
    python3 "merging guide/scripts/wire_check.py" --repo . --stage final --run <run_id> --api http://localhost:8000/api/v1 --json out/wire-run.json

Stages: after-tanush | after-ayan | after-aradhya | final. Exit 0 only if every executed check passes.
Checks are named W-xx / K / E / H / C / P / T / A / S / R and map to 03-INTEGRATION-WIRING.md.
"""
from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

FACADE = 'analogforge.science.facade:create_science_service'
RENDERER = 'analogforge.rendering.passport:create_passport_renderer'
EXTRA_ENTRY = {
    'analogforge.science.fixtures.practice:generate_all',
    'analogforge.science.fixtures.mock_nasa_drop:generate',
    'analogforge.science.datasets.inspect:draft_manifest',
    'analogforge.main:app',
    'analogforge.cli:main',
}
HEAVY = {'fastapi', 'sqlalchemy', 'psycopg', 'openai'}
NETWORKY = {'socket', 'http.client', 'urllib.request', 'requests', 'httpx', 'sqlalchemy', 'psycopg', 'openai', 'fastapi'}
ARTIFACT_MODELS = {
    'characterize-target': 'CharacterizeTargetPayload', 'screen-candidates': 'ScreenCandidatesPayload',
    'analysis-summary': 'AnalyzeCandidatePayload', 'compare-requirement': 'CompareRequirementPayload',
    'assess-compatibility': 'AssessCompatibilityPayload', 'design-benchmark': 'ConstraintsArtifact',
    'search-route': 'RouteArtifact', 'verify-route': 'VerifyRoutePayload', 'route-telemetry': 'TelemetryArtifact',
    'diagnose-result': 'DiagnoseResultPayload', 'optimize-portfolio': 'OptimizePortfolioPayload',
    'audit-evidence': 'AuditEvidencePayload',
}


def load_entry(spec: str):
    mod, _, attr = spec.partition(':')
    return getattr(importlib.import_module(mod), attr)


def fresh_modules(code: str, app: Path) -> tuple[int, str]:
    env_path = str(app / 'src')
    p = subprocess.run([sys.executable, '-c', code], text=True, capture_output=True, env={'PYTHONPATH': env_path, 'PATH': '/usr/bin:/bin'})
    return p.returncode, (p.stdout + p.stderr).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--stage', choices=['after-tanush', 'after-ayan', 'after-aradhya', 'final'], required=True)
    ap.add_argument('--run')
    ap.add_argument('--api')
    ap.add_argument('--json', type=Path)
    args = ap.parse_args()
    repo = args.repo.resolve()
    app = repo / 'analogforge'
    sys.path.insert(0, str(app / 'src'))
    stage = args.stage
    results: dict[str, dict] = {}

    def rec(cid: str, ok: bool, notes: str = '') -> None:
        results[cid] = {'status': 'PASS' if ok else 'FAIL', 'notes': notes}

    # K: kit
    p = subprocess.run([sys.executable, str(repo / 'architecture files/contracts/kit/materialize.py'), '--verify', '--app', str(app)],
                       text=True, capture_output=True)
    rec('K-kit-verify', p.returncode == 0, (p.stdout + p.stderr)[-300:] if p.returncode else 'kit verified')

    from analogforge.ports import catalog  # kit import must always work

    # H: import hygiene of analogforge.main (never imports science/renderer at import time)
    if stage in ('after-tanush', 'after-ayan', 'after-aradhya', 'final'):
        code = ("import sys, analogforge.main\n"
                "bad=[m for m in sys.modules if m.startswith('analogforge.science') or m.startswith('analogforge.rendering.passport')]\n"
                "print(','.join(bad)); sys.exit(1 if bad else 0)")
        c, out = fresh_modules(code, app)
        rec('H-main-no-science-or-renderer-import', c == 0, out[:300])

    # E: entry points
    if stage in ('after-ayan', 'final'):
        try:
            from analogforge.ports.science import ScienceOperation
            svc = load_entry(FACADE)()
            ops = set(svc.supported_operations())
            rec('E-science-facade', ops == set(ScienceOperation) and callable(svc.execute), f'ops={len(ops)}/{len(set(ScienceOperation))}')
        except Exception as exc:  # noqa: BLE001 - report any failure as a named check
            rec('E-science-facade', False, f'{type(exc).__name__}: {exc}')
        for spec in sorted(EXTRA_ENTRY - {'analogforge.main:app', 'analogforge.cli:main'}):
            try:
                rec(f'E-{spec}', callable(load_entry(spec)))
            except Exception as exc:  # noqa: BLE001
                rec(f'E-{spec}', False, f'{type(exc).__name__}: {exc}')
        code = ("import sys, analogforge.science.facade as f\n"
                f"bad=[m for m in sys.modules if m.split('.')[0] in {sorted(HEAVY)!r}]\n"
                "print(','.join(bad)); sys.exit(1 if bad else 0)")
        c, out = fresh_modules(code, app)
        rec('H-facade-import-hygiene', c == 0, out[:300])
    if stage in ('after-aradhya', 'final'):
        try:
            r = load_entry(RENDERER)()
            rec('E-passport-renderer', hasattr(r, 'render') and bool(getattr(r, 'renderer_version', '')))
        except Exception as exc:  # noqa: BLE001
            rec('E-passport-renderer', False, f'{type(exc).__name__}: {exc}')
        code = ("import sys, analogforge.rendering.passport as r\n"
                f"bad=[m for m in sys.modules if m in {sorted(NETWORKY)!r} or m.split('.')[0] in {sorted(HEAVY)!r}]\n"
                "print(','.join(bad)); sys.exit(1 if bad else 0)")
        c, out = fresh_modules(code, app)
        rec('H-renderer-import-hygiene', c == 0, out[:300])
    for spec in ('analogforge.main:app', 'analogforge.cli:main'):
        try:
            obj = load_entry(spec)
            ok = obj is not None
            if spec.endswith(':app'):
                ok = len([1 for r in obj.openapi()['paths'].values() for m in r if m in {'get', 'post', 'put', 'patch', 'delete'}]) >= 43
            rec(f'E-{spec}', ok)
        except Exception as exc:  # noqa: BLE001
            rec(f'E-{spec}', False, f'{type(exc).__name__}: {exc}')

    # C: config cross-keys + P: presets
    if stage in ('after-ayan', 'after-aradhya', 'final'):
        try:
            import yaml
            cfg = app / 'config'
            scen = yaml.safe_load((cfg / 'scenarios.yaml').read_text())
            scen = scen.get('scenarios', scen)
            alg = yaml.safe_load((cfg / 'algorithms.yaml').read_text())
            cand = yaml.safe_load((cfg / 'candidates.yaml').read_text())
            yaml.safe_load((cfg / 'datasets.yaml').read_text())
            problems = []
            for sid in catalog.ALL_SCENARIOS:
                if sid not in scen:
                    problems.append(f'scenario {sid} missing')
            pol = (alg.get('observable_policies') or {})
            for pid in set(catalog.OBSERVABLE_POLICY_BY_OBSERVABLE.values()):
                if pid not in pol:
                    problems.append(f'observable policy {pid} missing')
            ms = alg.get('measurement_specs') or {}
            for mid in (catalog.MEASUREMENT_SPEC_TARGET, catalog.MEASUREMENT_SPEC_EARTH):
                if mid not in ms:
                    problems.append(f'measurement spec {mid} missing')
            lock = alg.get('algorithm_lock') or {}
            for aid in catalog.ALGORITHM_IDS.values():
                if aid not in lock and aid != catalog.ALGORITHM_IDS['SCIENTIFIC_ASSURANCE']:
                    problems.append(f'algorithm_lock lacks {aid}')
            regions = (cand.get('search_region_sets') or {})
            refs = (cand.get('reference_sets') or {})
            if catalog.SEARCH_REGION_PRACTICE not in regions:
                problems.append('search region set practice missing')
            if catalog.REFERENCE_SET_PRACTICE not in refs:
                problems.append('reference set practice missing')
            for sid, s in scen.items():
                for key in ('search_region_set_id',):
                    v = (s or {}).get(key)
                    if v and v not in regions and not str(v).startswith('dataset-grid'):
                        problems.append(f'{sid}.{key}={v} not in candidates.yaml')
            rec('C-config-cross-keys', not problems, '; '.join(problems)[:600])
        except Exception as exc:  # noqa: BLE001
            rec('C-config-cross-keys', False, f'{type(exc).__name__}: {exc}')
        kit_fix = repo / 'architecture files/contracts/kit/files/tests/fixtures/kit'
        diffs = []
        for sub in ('missions', 'rovers'):
            for f in sorted((kit_fix / sub).glob('*.json')):
                target = app / 'config/presets' / sub / f.name
                if not target.is_file() or target.read_bytes() != f.read_bytes():
                    diffs.append(f'{sub}/{f.name}')
        rec('P-presets-byte-equal', not diffs, ', '.join(diffs))

    # T: test ids; A: algorithm ids
    if stage in ('after-aradhya', 'final'):
        ids = [t['id'] for t in json.loads((app / 'contracts/ui-testids.json').read_text())['testids']]
        src = app / 'apps/web/src'
        blob = '\n'.join(p.read_text(errors='ignore') for p in src.rglob('*') if p.is_file() and p.suffix in {'.ts', '.tsx'}) if src.is_dir() else ''
        missing = [i for i in ids if i not in blob]
        rec('T-testids-in-ui-source', not missing, f'missing: {missing[:20]}')
        a1 = json.loads((app / 'contracts/algorithm-ids.json').read_text())['algorithm_ids']
        rec('A-algorithm-ids-equal-catalog', a1 == dict(catalog.ALGORITHM_IDS))

    # S: smoke science through the real facade (kit-valid result, artifacts exist, ids from catalog)
    if stage in ('after-ayan', 'final'):
        try:
            from analogforge.ports.domain_models import AreaOfInterest
            from analogforge.ports.science import LocalScienceContext, ScienceRequest, SourcePolicy
            from analogforge.ports.science_payloads import CharacterizeTargetInput, SourceSelector
            from analogforge.ports.hashing import canonical_sha256, file_sha256
            svc = load_entry(FACADE)()
            mission = json.loads((app / 'tests/fixtures/kit/missions/mission-mars-mobility.json').read_text())
            req = ScienceRequest(
                request_id=uuid.uuid4(), operation='CHARACTERIZE_TARGET', mode='synthetic',
                inputs=CharacterizeTargetInput(target=AreaOfInterest.model_validate(mission['target']),
                                               source=SourceSelector(kind='SYNTHETIC_FIXTURE', fixture_id=catalog.FIXTURE_MARS_TARGET),
                                               measurement_spec_id=catalog.MEASUREMENT_SPEC_TARGET, requested_dimensions=['TERRAIN', 'THERMAL']),
                source_policy=SourcePolicy(policy_id='wire-check', policy_sha256='0' * 64, synthetic_fixture_ids=[catalog.FIXTURE_MARS_TARGET]))
            with tempfile.TemporaryDirectory() as tmp:
                ctx = LocalScienceContext(scratch=Path(tmp), workspace_id=uuid.uuid4(), job_id=uuid.uuid4())
                res = svc.execute(req, ctx)
                problems = []
                if res.status.value not in ('SUCCEEDED', 'LIMITED'):
                    problems.append(f'status {res.status.value}: {[i.message for i in res.issues][:2]}')
                if res.input_sha256 != canonical_sha256(req):
                    problems.append('input_sha256 != canonical_sha256(request)')
                allowed = set(catalog.ALGORITHM_IDS.values())
                for e in res.evidence_drafts:
                    if e.algorithm_id not in allowed:
                        problems.append(f'unknown algorithm_id {e.algorithm_id}')
                    if res.mode == 'synthetic' and e.dataset_product_id and not e.dataset_product_id.startswith('SYNTHETIC_'):
                        problems.append(f'non-synthetic product id {e.dataset_product_id}')
                for a in res.artifacts:
                    path = Path(tmp) / a.scratch_relpath
                    if not path.is_file() or file_sha256(path) != a.sha256 or path.stat().st_size != a.size_bytes:
                        problems.append(f'artifact {a.local_key} missing or hash/size mismatch')
                rec('S-science-smoke-characterize-target', not problems, '; '.join(problems))
        except Exception as exc:  # noqa: BLE001
            rec('S-science-smoke-characterize-target', False, f'{type(exc).__name__}: {exc}')

    # R: walk public endpoints of a completed run and parse UI-readable artifacts
    if args.run and args.api:
        try:
            import httpx
            from analogforge.ports import assurance_models, science_payloads
            c = httpx.Client(base_url=args.api.rstrip('/'), timeout=30)
            snap = c.get(f'/runs/{args.run}').raise_for_status().json()
            ev_ids: set[str] = set()
            for key in ('candidate_ids',):
                for cid in snap.get(key, []):
                    ev_ids.update(c.get(f'/candidates/{cid}').raise_for_status().json().get('evidence_ids', []))
            if snap.get('target_profile_id'):
                ev_ids.update(c.get(f"/target-profiles/{snap['target_profile_id']}").raise_for_status().json().get('evidence_ids', []))
            for qid in snap.get('qualification_ids', []):
                ev_ids.update(c.get(f'/qualifications/{qid}').raise_for_status().json().get('evidence_ids', []))
            for rid in snap.get('test_result_ids', []):
                ev_ids.update(c.get(f'/test-results/{rid}').raise_for_status().json().get('evidence_ids', []))
            if snap.get('passport_id'):
                pp = c.get(f"/passports/{snap['passport_id']}").raise_for_status().json()
                ev_ids.update(pp.get('evidence_ids', []))
            problems, seen = [], set()
            for eid in sorted(ev_ids):
                ev = c.get(f'/evidence/{eid}').raise_for_status().json()
                aid, sha, mt = ev.get('algorithm_id'), ev.get('artifact_sha256'), ev.get('artifact_media_type')
                if aid in ARTIFACT_MODELS and sha and mt == 'application/json':
                    body = c.get(f'/artifacts/{sha}').raise_for_status().content
                    getattr(science_payloads, ARTIFACT_MODELS[aid]).model_validate_json(body)
                    seen.add(aid)
                elif aid == 'scientific-assurance' and sha:
                    assurance_models.ScientificAssuranceArtifact.model_validate_json(c.get(f'/artifacts/{sha}').raise_for_status().content)
                    seen.add(aid)
            required = {'characterize-target', 'screen-candidates', 'compare-requirement', 'verify-route', 'route-telemetry', 'scientific-assurance'}
            missing = sorted(required - seen)
            if missing:
                problems.append(f'UI-readable artifacts not reachable: {missing}')
            rec('R-ui-readable-artifacts-reachable', not problems, '; '.join(problems) or f'parsed: {sorted(seen)}')
        except Exception as exc:  # noqa: BLE001
            rec('R-ui-readable-artifacts-reachable', False, f'{type(exc).__name__}: {exc}')

    ok = all(r['status'] == 'PASS' for r in results.values())
    report = {'stage': stage, 'status': 'PASS' if ok else 'FAIL', 'results': results}
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text + '\n')
    print(text)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
