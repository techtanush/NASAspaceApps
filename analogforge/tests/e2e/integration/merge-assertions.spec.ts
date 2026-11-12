import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { canonicalize } from 'json-canonicalize';
import { api, prove, startRun, tab } from '../support/workbench';
import { persistedResults, type S } from '../support/journeyChecks';

const root = resolve(import.meta.dirname, '../../..');
const require = createRequire(resolve(root, 'apps/web/package.json'));
const Ajv2020 = require('ajv/dist/2020').default;
const addFormats = require('ajv-formats').default;
const sha = (bytes: string | Buffer) => createHash('sha256').update(bytes).digest('hex');

test('MRG-03 real persisted attempts, frozen inputs, assurance, artifacts and export digests agree', async ({ page }) => {
  expect(process.env.E2E_TARGET, 'This gate requires the real backend').toBe('real');
  const runId = await startRun(page);
  const before = (await api<S['RunSnapshot']>(page, `/runs/${runId}`)).body;
  const mission = (await api<S['MissionTestContract']>(page, `/mission-revisions/${before.mission_revision_id}`)).body;
  const rover = (await api<S['RoverProfile']>(page, `/rover-revisions/${before.rover_revision_id}`)).body;
  await prove(page);
  const persisted = await persistedResults(page, runId);
  const tests = persisted.snapshot.test_ids.map(id => persisted.tests.find(attempt => attempt.id === id)!);
  expect(tests).toHaveLength(3);
  expect(tests.map(value => value.candidate_id)).toEqual([tests[0]!.candidate_id, tests[0]!.candidate_id, tests[2]!.candidate_id]);
  expect(tests[0]!.candidate_id).not.toBe(tests[2]!.candidate_id);
  expect((await api<S['EarthAnalogCandidate']>(page, `/candidates/${tests[0]!.candidate_id}`)).body.name).toBe('Practice grid-r0c1');
  expect((await api<S['EarthAnalogCandidate']>(page, `/candidates/${tests[2]!.candidate_id}`)).body.name).toBe('Practice grid-r0c0');
  const outcomes = tests.map(value => persisted.results.find(result => result.test_id === value.id)!.outcome);
  expect(outcomes).toEqual(['FAIL', 'FAIL', 'PASS']);
  const qualifications = await Promise.all(persisted.snapshot.qualification_ids.map(async id =>
    (await api<S['QualificationDimension']>(page, `/qualifications/${id}`)).body));
  for (const requirement of ['R-EXPOSURE', 'R-TASKS', 'R-RESERVE']) {
    expect(qualifications.find(row => row.candidate_id === tests[2]!.candidate_id && row.requirement_id === requirement)?.status)
      .toBe('PASS');
  }
  for (const attempt of tests) {
    expect(attempt.mission_revision_id).toBe(before.mission_revision_id);
    expect(attempt.rover_revision_id).toBe(before.rover_revision_id);
  }
  expect((await api<S['MissionTestContract']>(page, `/mission-revisions/${before.mission_revision_id}`)).body).toEqual(mission);
  expect((await api<S['RoverProfile']>(page, `/rover-revisions/${before.rover_revision_id}`)).body).toEqual(rover);
  await tab(page, 'passport');
  await expect(page.getByTestId('passport-view')).toHaveAttribute('data-draft', 'false');
  const passport = (await api<S['AnalogPassport']>(page, `/passports/${persisted.snapshot.passport_id}`)).body;
  expect(passport.evidence_ids).toContain(passport.assurance_evidence_id);
  const auditEvidence = (await api<S['EvidenceRecord']>(page, `/evidence/${passport.assurance_evidence_id}`)).body;
  const audit = (await api(page, `/artifacts/${auditEvidence.artifact_sha256}`)).body;
  const ajv = new Ajv2020({ strict: false, allErrors: true }); addFormats(ajv);
  const valid = ajv.compile(JSON.parse(readFileSync(resolve(root, 'contracts/scientific-assurance.schema.json'), 'utf8')));
  expect(valid(audit), JSON.stringify(valid.errors)).toBe(true);
  expect(audit.run_id).toBe(runId);
  expect(audit.mission_content_sha256).toBe(mission.content_sha256);
  expect(audit.rover_content_sha256).toBe(rover.content_sha256);
  const digests: Record<string, string> = {};
  for (const format of ['html', 'json', 'csv']) {
    const downloading = page.waitForEvent('download');
    await page.locator(`[data-testid=export-btn][data-format=${format}]`).click();
    const download = await downloading;
    const bytes = readFileSync((await download.path())!);
    const path = `/api/v1/passports/${passport.id}/exports/${format}`;
    const response = await page.request.get(path);
    expect(response.status()).toBe(200);
    expect(await response.body()).toEqual(bytes);
    expect(response.headers()['x-artifact-sha256']).toBe(sha(bytes));
    expect(await (await page.request.get(path)).body()).toEqual(bytes);
    digests[format] = sha(bytes);
    if (format === 'json') {
      const document = JSON.parse(bytes.toString());
      expect(sha(canonicalize(document.canonical_manifest))).toBe(passport.manifest_sha256);
      expect(document.bundle.mission.content_sha256).toBe(mission.content_sha256);
      expect(document.bundle.rover.content_sha256).toBe(rover.content_sha256);
      expect(document.bundle.attempts.map((attempt: { result: S['TestResult'] }) => attempt.result.outcome)).toEqual(outcomes);
    }
  }
  expect(await page.getByTestId('mock-banner').count()).toBe(0);
  expect(await page.evaluate(() => (window as unknown as { __MSW__?: boolean }).__MSW__)).toBeUndefined();
  mkdirSync(resolve(root, 'out/merge'), { recursive: true });
  execFileSync(resolve(root, '.venv/bin/python'), [resolve(root, '../merging guide/scripts/wire_check.py'), '--repo', resolve(root, '..'),
    '--stage', 'final', '--run', runId, '--api', process.env.E2E_API_URL || 'http://127.0.0.1:8000/api/v1',
    '--json', resolve(root, 'out/merge/wire-artifacts.json')], { cwd: root, stdio: 'pipe' });
  writeFileSync(resolve(root, 'out/merge/persisted-assertions.json'), JSON.stringify({ runId, outcomes, mission_hash: mission.content_sha256,
    rover_hash: rover.content_sha256, manifest_hash: passport.manifest_sha256, assurance_evidence_id: passport.assurance_evidence_id, digests }, null, 2));
});
