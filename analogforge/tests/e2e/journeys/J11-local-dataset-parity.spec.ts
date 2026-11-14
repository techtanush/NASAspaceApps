import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { startRun, prove, api, isMock } from '../support/workbench';
import { persistedResults, type S } from '../support/journeyChecks';

test('J11 local dataset practice matches synthetic qualifications and attempts', async ({ page }) => {
  test.setTimeout(isMock() ? 180000 : 1200000); // real backend: two full runs plus PROVE IT under the frozen step limits
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
  // R-MINERAL reason differs as specified (architecture 39 J11, 40 s4, PERT-07). Rows are immutable, so PROVE IT can add a
  // newer row per candidate: judge the latest row of each candidate. The reason code is read the way the UI reads it, from
  // the row's COMPARE_REQUIREMENT artifact; the explanation is free prose. The practice mineral layer covers only some
  // windows, and a window without retrievals stays EARTH_EVIDENCE_MISSING (absence of data is not absence of mineral).
  const reasons = async (rows: S['QualificationDimension'][]) => {
    const latest = new Map<string, S['QualificationDimension']>();
    for (const row of rows.filter(item => item.requirement_id === 'R-MINERAL')) {
      const seen = latest.get(row.candidate_id);
      if (!seen || seen.created_at < row.created_at) latest.set(row.candidate_id, row);
    }
    const out: { status: string; reason: string }[] = [];
    for (const row of latest.values()) {
      const records = await Promise.all(row.evidence_ids.map(id => api<S['EvidenceRecord']>(page, `/evidence/${id}`)));
      const record = records.map(item => item.body).find(item => item.algorithm_id === 'compare-requirement' && item.kind !== 'ASSUMPTION' && item.artifact_media_type === 'application/json');
      expect(record, `COMPARE_REQUIREMENT evidence for candidate ${row.candidate_id}`).toBeTruthy();
      const artifact = await api<{ reason_code: string }>(page, `/artifacts/${record!.artifact_sha256}`);
      out.push({ status: row.status, reason: artifact.body.reason_code });
    }
    return out;
  };
  const localMineral = await reasons(current.body.items);
  const baselineMineral = await reasons(baseline.body.items);
  expect(localMineral).toHaveLength(localCandidates.body.items.length);
  for (const row of [...localMineral, ...baselineMineral]) expect(row.status).toBe('UNKNOWN');
  expect(new Set(baselineMineral.map(row => row.reason))).toEqual(new Set(['EARTH_EVIDENCE_MISSING']));
  expect(localMineral.some(row => row.reason === 'TARGET_EVIDENCE_MISSING')).toBe(true);
  for (const row of localMineral) expect(['TARGET_EVIDENCE_MISSING', 'EARTH_EVIDENCE_MISSING']).toContain(row.reason);
});

