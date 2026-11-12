import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { startRun, prove, api, isMock } from '../support/workbench';
import { persistedResults, type S } from '../support/journeyChecks';

test('J11 local dataset practice matches synthetic qualifications and attempts', async ({ page }) => {
  test.setTimeout(180000);
  if (!isMock()) {
    const root = resolve(import.meta.dirname, '../../..');
    const cli = process.env.ANALOGFORGE_CLI || resolve(root, '.venv/bin/analogforge');
    execFileSync(cli, ['datasets', 'generate-practice'], { cwd: root, stdio: 'pipe' });
    // Operator sequence of architecture 36 s3: validate each practice dataset, then lock exactly those datasets.
    const practice = ['practice-mars-target-v1', 'practice-earth-grid-v1', 'practice-earth-minerals-v1'];
    for (const dataset of practice) execFileSync(cli, ['datasets', 'validate', dataset], { cwd: root, stdio: 'pipe' });
    execFileSync(cli, ['datasets', 'lock', '--policy-id', 'local-practice-policy-v1', '--datasets', ...practice], { cwd: root, stdio: 'pipe' });
  }
  const syntheticId = await startRun(page);
  await prove(page);
  const synthetic = await persistedResults(page, syntheticId);
  const baseline = await api<S['ListQualificationDimension']>(page, `/qualifications?run_id=${syntheticId}&limit=100`);
  const candidates = await api<S['ListEarthAnalogCandidate']>(page, `/candidates?run_id=${syntheticId}&limit=100`);
  const localId = await startRun(page, { scenario: 'local-dataset-practice-v1' });
  await prove(page);
  const local = await persistedResults(page, localId);
  const current = await api<S['ListQualificationDimension']>(page, `/qualifications?run_id=${localId}&limit=100`);
  const localCandidates = await api<S['ListEarthAnalogCandidate']>(page, `/candidates?run_id=${localId}&limit=100`);
  const normalize = (rows: S['QualificationDimension'][], sites: S['EarthAnalogCandidate'][]) => rows.map(row => ({ requirement: row.requirement_id, candidate: sites.find(site => site.id === row.candidate_id)?.name, status: row.status, confidence: row.confidence, comparison_scale_m: row.comparison_scale_m, critic_status: row.critic_status, rule_id: row.rule_id, rule_version: row.rule_version })).sort((a, b) => `${a.requirement}/${a.candidate}`.localeCompare(`${b.requirement}/${b.candidate}`));
  expect(normalize(current.body.items, localCandidates.body.items)).toEqual(normalize(baseline.body.items, candidates.body.items));
  expect(local.results.map(row => row.outcome)).toEqual(synthetic.results.map(row => row.outcome));
  const mineral = current.body.items.filter(row => row.requirement_id === 'R-MINERAL');
  expect(mineral).toHaveLength(6);
  for (const row of mineral) { expect(row.status).toBe('UNKNOWN'); expect(row.explanation).toContain('TARGET_EVIDENCE_MISSING'); }
});

