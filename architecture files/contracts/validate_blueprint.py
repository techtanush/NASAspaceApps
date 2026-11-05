#!/usr/bin/env python3
"""Validate architecture artifacts, not the future application's behavior."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []
CHECKS: Counter[str] = Counter()


def fail(message: str) -> None:
    ERRORS.append(message)


def load(path: Path):
    return json.loads(path.read_text())


def pointer(document, fragment: str):
    value = document
    if not fragment:
        return value
    for token in fragment.lstrip('/').split('/'):
        token = unquote(token).replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def walk_refs(value, current: Path) -> None:
    if isinstance(value, dict):
        if '$ref' in value:
            ref = value['$ref']
            if ref.startswith(('http:', 'https:', 'urn:')):
                fail(f'Unbundled external schema reference in {current.name}: {ref}')
            else:
                file_part, _, fragment = ref.partition('#')
                target = current if not file_part else (current.parent / file_part).resolve()
                try:
                    pointer(load(target), fragment)
                    CHECKS['schema_references'] += 1
                except (OSError, KeyError, IndexError, ValueError) as exc:
                    fail(f'Broken schema reference {current.name}: {ref}: {exc}')
        for child in value.values():
            walk_refs(child, current)
    elif isinstance(value, list):
        for child in value:
            walk_refs(child, current)


def normalized(value):
    # These supplied fixtures use ASCII keys and ordinary finite decimal numbers;
    # integral normalization makes their hashes match JCS numeric serialization.
    # The application must use the pinned RFC8785 implementation for arbitrary JSON.
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [normalized(v) for v in value]
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items()}
    return value


def fixture_hash(value) -> str:
    raw = json.dumps(normalized(value), sort_keys=True, separators=(',', ':'),
                     ensure_ascii=False, allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def assurance_shape_issues(value, gate_ids: set[str]) -> list[str]:
    """Planning-fixture consistency, not the future application's scientific audit."""
    issues = []
    seen_claims = set()
    for claim in value.get('claims', []):
        if claim['claim_id'] in seen_claims:
            issues.append('duplicate claim ID')
        seen_claims.add(claim['claim_id'])
        ids = [gate['gate_id'] for gate in claim['gates']]
        if len(ids) != len(set(ids)) or set(ids) != gate_ids:
            issues.append('each registered gate must occur exactly once')
        for gate in claim['gates']:
            if gate['gate_id'] in {'SC-01', 'SC-07', 'SC-12', 'SC-14', 'SC-15'} and gate['outcome'] == 'NOT_APPLICABLE':
                issues.append('an ALL gate cannot be disabled')
    return issues


def main() -> int:
    for path in ROOT.rglob('*.json'):
        try:
            load(path)
            CHECKS['json_files'] += 1
        except (OSError, ValueError) as exc:
            fail(f'Invalid JSON {path.relative_to(ROOT)}: {exc}')

    domain_path = ROOT / 'contracts/domain.schema.json'
    api_path = ROOT / 'contracts/openapi.yaml'
    domain, api = load(domain_path), load(api_path)
    Draft202012Validator.check_schema(domain)
    for name, schema in domain['$defs'].items():
        Draft202012Validator.check_schema(schema)
        CHECKS['domain_definitions'] += 1
    walk_refs(domain, domain_path)
    walk_refs(api, api_path)
    if api.get('openapi') != '3.1.0':
        fail('Expected OpenAPI 3.1.0')
    for name, schema in api['components']['schemas'].items():
        Draft202012Validator.check_schema(schema)
        CHECKS['api_component_schemas'] += 1
    seen = set()
    for path, methods in api['paths'].items():
        for method, operation in methods.items():
            if method not in {'get', 'post', 'patch', 'put', 'delete'}:
                continue
            oid = operation.get('operationId')
            if not oid or oid in seen:
                fail(f'Duplicate/missing operationId at {path}')
            seen.add(oid)
            if 'responses' not in operation:
                fail(f'Missing responses at {path}')
            parameters = operation.get('parameters', [])
            declared = {p.get('name') for p in parameters if p.get('in') == 'path'}
            if not set(re.findall(r'{(.*?)}', path)).issubset(declared):
                fail(f'Undeclared path parameter at {path}')
            if method == 'post' and not any(
                p.get('$ref', '').endswith('/IdempotencyKey') for p in parameters
            ):
                fail(f'Missing mutation idempotency parameter at {path}')
            CHECKS['api_operations'] += 1

    api_schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
                  '$id': api_path.as_uri(), 'components': api['components']}
    registry = Registry().with_resources([
        (domain_path.as_uri(), Resource.from_contents(domain)),
        (domain['$id'], Resource.from_contents(domain)),
        (api_path.as_uri(), Resource.from_contents(api_schema, default_specification=DRAFT202012)),
    ])
    cases = {
        'mission-contract.json': (domain['$id'], '/$defs/MissionTestContract'),
        'rover-profile.json': (domain['$id'], '/$defs/RoverProfile'),
        'run-event.json': (domain['$id'], '/$defs/RunEvent'),
        'qualification-unknown.json': (domain['$id'], '/$defs/QualificationDimension'),
        'rover-import.json': (api_path.as_uri(), '/components/schemas/RoverInput'),
        'request-create-run.json': (api_path.as_uri(), '/components/schemas/RunCreateInput'),
        'request-prove-it.json': (api_path.as_uri(), '/components/schemas/RunAction'),
    }
    for filename, (base, fragment) in cases.items():
        validator = Draft202012Validator({'$ref': base + '#' + fragment},
                                         registry=registry, format_checker=FormatChecker())
        errors = list(validator.iter_errors(load(ROOT / 'examples' / filename)))
        for error in errors:
            fail(f'{filename} {list(error.path)}: {error.message}')
        CHECKS['schema_validated_examples'] += 1

    assurance_path = ROOT / 'contracts/scientific-assurance.schema.json'
    assurance = load(assurance_path)
    Draft202012Validator.check_schema(assurance)
    walk_refs(assurance, assurance_path)
    gate_registry = load(ROOT / 'contracts/scientific-gates.json')
    expected_gates = {f'SC-{i:02d}' for i in range(1, 16)}
    if (set(gate_registry['required_gate_ids']) != expected_gates
            or len(gate_registry['required_gate_ids']) != 15
            or {gate['gate_id'] for gate in gate_registry['gates']} != expected_gates
            or len(gate_registry['gates']) != 15):
        fail('Scientific gate registry must define each SC-01 through SC-15 once')
    CHECKS['scientific_gate_definitions'] = len(gate_registry['gates'])
    audit_validator = Draft202012Validator(assurance, format_checker=FormatChecker())
    audit_cases = ['assurance-supported-negative.json', 'assurance-supported-positive.json',
                   'assurance-limited-unknown.json', 'assurance-blocked-claim.json']
    for filename in audit_cases:
        value = load(ROOT / 'examples' / filename)
        for error in audit_validator.iter_errors(value):
            fail(f'{filename} {list(error.path)}: {error.message}')
        for issue in assurance_shape_issues(value, expected_gates):
            fail(f'{filename}: {issue}')
        CHECKS['assurance_validated_examples'] += 1
    import copy
    valid = load(ROOT / 'examples/assurance-supported-negative.json')
    missing = copy.deepcopy(valid)
    missing['claims'][0]['gates'].pop()
    duplicate = copy.deepcopy(valid)
    duplicate['claims'][0]['gates'][-1] = copy.deepcopy(duplicate['claims'][0]['gates'][0])
    disabled = copy.deepcopy(valid)
    disabled['claims'][0]['gates'][0]['outcome'] = 'NOT_APPLICABLE'
    unknown_id = copy.deepcopy(valid)
    unknown_id['claims'][0]['gates'][0]['gate_id'] = 'SC-99'
    empty_blocked = copy.deepcopy(valid)
    empty_blocked['publication'] = 'BLOCKED'
    rejected_published = copy.deepcopy(valid)
    rejected_published['claims'][0]['disposition'] = 'REJECTED'
    for mutation in [missing, duplicate, disabled, unknown_id, empty_blocked, rejected_published]:
        if audit_validator.is_valid(mutation) and not assurance_shape_issues(mutation, expected_gates):
            fail('Malformed assurance planning fixture was accepted')
        CHECKS['assurance_invalid_fixture_rejections'] += 1
    passport = domain['$defs']['AnalogPassport']
    if 'assurance_evidence_id' not in passport['required']:
        fail('C1 passport must require assurance_evidence_id')

    for filename, meta in [
        ('mission-contract.json', {'schema_version', 'id', 'mission_id', 'workspace_id',
                                   'revision', 'created_at', 'accepted_at', 'content_sha256'}),
        ('rover-profile.json', {'schema_version', 'id', 'rover_id', 'workspace_id',
                                'revision', 'created_at', 'content_sha256'}),
    ]:
        value = load(ROOT / 'examples' / filename)
        if fixture_hash({k: v for k, v in value.items() if k not in meta}) != value['content_sha256']:
            fail(f'Fixture semantic hash mismatch: {filename}')
        CHECKS['example_hashes'] += 1

    source_manifest = load(ROOT / 'references/source-manifest.json')
    for source in source_manifest['sources']:
        raw = (ROOT / 'references' / source['file']).read_bytes()
        if len(raw) != source['bytes'] or hashlib.sha256(raw).hexdigest() != source['sha256']:
            fail(f'Source copy mismatch: {source["file"]}')
        CHECKS['source_hashes'] += 1

    product = (ROOT / '02-PRODUCT-REQUIREMENTS.md').read_text()
    expected_ids = set(re.findall(r'^\| (PR-\d{3}) \|', product, re.M))
    with (ROOT / 'contracts/requirements-traceability.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    if {row['requirement_id'] for row in rows} != expected_ids or len(rows) != len(expected_ids):
        fail('Traceability CSV differs from exact product requirement IDs')
    CHECKS['traceable_product_requirements'] = len(rows)

    for path in ROOT.rglob('*.md'):
        content = path.read_text()
        if sum(1 for line in content.splitlines() if line.startswith('```')) % 2:
            fail(f'Unbalanced code fences: {path.relative_to(ROOT)}')
        for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', content):
            target = target.strip().strip('<>')
            if target.startswith(('http:', 'https:', 'mailto:', '#', 'codex:')):
                continue
            clean = unquote(target.split('#')[0])
            if clean and not (path.parent / clean).exists():
                fail(f'Broken link {path.relative_to(ROOT)} -> {target}')
            CHECKS['local_document_links'] += 1
        for i, block in enumerate(re.findall(r'```json\s*\n(.*?)\n```', content, re.S), 1):
            try:
                json.loads(block)
            except ValueError as exc:
                fail(f'Invalid JSON block {path.relative_to(ROOT)} block{i}: {exc}')
            CHECKS['json_document_examples'] += 1

    graph = load(ROOT / 'examples/synthetic-route-graph.json')
    edges = {frozenset((e['a'], e['b'])): e for e in graph['edges']}
    c = graph['constraints']
    for attempt in graph['attempts']:
        route = attempt['route']
        used = Counter(frozenset((a, b)) for a, b in zip(route, route[1:]))
        length = sum(edges[k]['length_m'] * count for k, count in used.items())
        energy = sum(edges[k]['mock_energy_wh'] * count for k, count in used.items())
        energy += sum(cost for node, cost in graph['tasks'].items() if node in route)
        exposure = sum(edges[k]['length_m'] for k in used
                       if c['slope_band_deg'][0] <= edges[k]['surface_slope_deg'] <= c['slope_band_deg'][1])
        passes = (exposure >= c['minimum_unique_exposure_m'] and length <= c['max_distance_m']
                  and route[0] == route[-1] == c['start']
                  and set(c['required_task_ids']).issubset(route)
                  and all(count <= c['max_undirected_edge_traversals'] for count in used.values())
                  and all(edges[k]['surface_slope_deg'] <= c['max_slope_deg'] for k in used)
                  and energy <= c['battery_wh'] * (1 - c['min_reserve_pct'] / 100))
        if (length, energy, exposure, 'PASS' if passes else 'FAIL') != (
            attempt['expected_length_m'], attempt['expected_energy_wh'],
            attempt['expected_unique_exposure_m'], attempt['expected_outcome']):
            fail('Synthetic graph expected arithmetic/outcome mismatch')
        CHECKS['synthetic_graph_attempts'] += 1

    report = {'blueprint_validation_only': True, 'status': 'PASS' if not ERRORS else 'FAIL',
              'checks': dict(CHECKS), 'errors': ERRORS,
              'not_validated': ['future application behavior', 'real source granules',
                                'live AI account/model capability', 'physical rover performance']}
    (ROOT / 'BLUEPRINT-VALIDATION.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 1 if ERRORS else 0


if __name__ == '__main__':
    raise SystemExit(main())
