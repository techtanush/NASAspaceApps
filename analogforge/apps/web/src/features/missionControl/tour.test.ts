import { describe, expect, it } from 'vitest';
import seed from '../../mock/fixtures/seed.json';
import { benchmarkText, buildSites, type Candidate, type Requirement, type Qualification } from './tour';

describe('committed candidate presentation', () => {
  const candidates = seed.candidates as unknown as Candidate[];
  const requirements = [{ id: 'required', mandatory: true }] as Requirement[];
  it('keeps screening order even when a later site passes and the first fails', () => {
    const input = candidates.slice(0, 2);
    const rows = input.map((candidate, index) => ({ candidate_id: candidate.id, requirement_id: 'required', status: index === 0 ? 'FAIL' : 'PASS' })) as Qualification[];
    const sites = buildSites(input, requirements, rows);
    expect(sites.map(site => site.candidate.id)).toEqual(input.map(candidate => candidate.id));
    expect(sites.map(site => site.status)).toEqual(['FAIL', 'PASS']);
    expect(sites.map(site => site.index)).toEqual([1, 2]);
  });
  it('retains adjacent footprints as separate candidates and missing evidence as unknown', () => {
    const input = candidates.slice(0, 2);
    const sites = buildSites(input, requirements, []);
    expect(sites).toHaveLength(input.length);
    expect(sites.every(site => site.status === 'UNKNOWN')).toBe(true);
    expect(sites.every(site => site.covers.length === 0)).toBe(true);
  });
});

describe('reviewable benchmark criteria', () => {
  const criterion = {operator:'GTE',lower:0.05,upper:null,unit:'fraction',minimum_support_scale_m:500,maximum_support_scale_m:500,parameters:{slope_band_deg:[12,18]}} as Requirement;
  it('distinguishes identical area thresholds for different accepted slope bands', () => {
    expect(benchmarkText(criterion)).toBe('at least 0.05 fraction · slope band 12–18 deg at 500 m support');
    expect(benchmarkText({...criterion,parameters:{...criterion.parameters,slope_band_deg:[0,5]}})).toContain('slope band 0–5 deg');
  });
  it('does not invent a slope band for a distribution-distance criterion', () => {
    expect(benchmarkText({...criterion,operator:'LTE',lower:null,upper:5,unit:'deg',parameters:{...criterion.parameters,slope_band_deg:null}})).toBe('at most 5 deg at 500 m support');
  });
});
