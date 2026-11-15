import type { components } from '../../generated/schema';

type S = components['schemas'];
export type Requirement = S['Requirement']; export type Candidate = S['EarthAnalogCandidate']; export type Qualification = S['QualificationDimension'];
export type Status = S['QualificationStatus'];
/** Presentation only: restates accepted contract fields and committed statuses. Nothing here computes a result. */
const number = (value: number | null) => (value === null ? 'unspecified' : String(value));
const quantity = (value: number | null, unit: string) => (unit && unit !== 'none' && unit !== '1' ? `${number(value)} ${unit}` : number(value));
export function readableQuantity(value: number | null, unit: string, simplified = false): string {
  if (simplified && unit === 'fraction') return value === null ? 'unspecified' : `${Number((value * 100).toPrecision(3))}%`;
  return quantity(value, unit);
}
export function benchmarkText(requirement: Requirement, simplified = false): string {
  const { operator, unit } = requirement; const low = requirement.lower, high = requirement.upper;
  const label = (value: number | null) => readableQuantity(value, unit, simplified);
  const rule = operator === 'LTE' ? `at most ${label(high)}` : operator === 'GTE' ? `at least ${label(low)}`
    : operator === 'BETWEEN' ? `between ${simplified && unit === 'fraction' ? label(low) : number(low)} and ${label(high)}` : operator === 'EQUALS' ? `exactly ${label(low ?? high)}`
    : operator === 'PRESENT' ? 'must be present' : 'cannot be reproduced naturally on Earth';
  const min = requirement.minimum_support_scale_m, max = requirement.maximum_support_scale_m;
  const support = min !== null && max !== null ? (min === max ? ` at ${min} m support` : ` at ${min}–${max} m support`) : '';
  const band = requirement.parameters?.slope_band_deg;
  const bandText = band?.length === 2 && band.every(Number.isFinite) ? ` · slope band ${band[0]}–${band[1]} deg` : '';
  return `${rule}${bandText}${support}`;
}
export const ORIGIN_LABEL: Record<Requirement['origin'], string> = { USER: 'Supplied by you', TARGET_DERIVED: 'Derived from the target', PROPOSED_DEFAULT: 'Proposed default' };
export const STATUS_WORD: Record<Status, string> = { PASS: 'Matches', PARTIAL: 'Partly matches', FAIL: 'Does not match', GAP: 'Cannot be tested on Earth', UNKNOWN: 'Not yet known' };
const SEVERITY: Status[] = ['FAIL', 'UNKNOWN', 'PARTIAL', 'GAP', 'PASS'];
export interface SiteRow { requirement: Requirement; qualification: Qualification | null; status: Status }
export interface Site { candidate: Candidate; index: number; lat: number; lng: number; rows: SiteRow[]; status: Status; covers: string[] }
/** Overall site status is the most severe mandatory row; natural gaps do not by themselves fail a site. */
export function buildSites(candidates: Candidate[], requirements: Requirement[], qualifications: Qualification[]): Site[] {
  const sites = candidates.filter(candidate => candidate.aoi.body === 'EARTH' && candidate.aoi.bbox.length === 4 && candidate.aoi.bbox.every(Number.isFinite) && candidate.aoi.bbox[0]! < candidate.aoi.bbox[2]! && candidate.aoi.bbox[1]! < candidate.aoi.bbox[3]!).map(candidate => {
    const rows = requirements.map<SiteRow>(requirement => {
      const qualification = qualifications.find(row => row.candidate_id === candidate.id && row.requirement_id === requirement.id) ?? null;
      return { requirement, qualification, status: qualification?.status ?? 'UNKNOWN' };
    });
    const mandatory = rows.filter(row => row.requirement.mandatory && row.status !== 'GAP');
    const status = mandatory.length === 0 ? 'UNKNOWN' : SEVERITY.find(level => mandatory.some(row => row.status === level)) ?? 'UNKNOWN';
    const [west, south, east, north] = candidate.aoi.bbox as [number, number, number, number];
    return { candidate, index: 0, lat: (south + north) / 2, lng: (west + east) / 2, rows, status, covers: rows.filter(row => row.status === 'PASS').map(row => row.requirement.id) };
  });
  return sites.map((site, position) => ({ ...site, index: position + 1 }));
}
export interface CoverageRow { requirement: Requirement; sites: Site[]; state: 'COVERED' | 'GAP' | 'UNCOVERED' }
export function buildCoverage(requirements: Requirement[], sites: Site[]): CoverageRow[] {
  return requirements.map(requirement => {
    const covering = sites.filter(site => site.covers.includes(requirement.id));
    const natural = requirement.operator === 'NOT_NATURALLY_REPRODUCIBLE' || (sites.length > 0 && sites.every(site => site.rows.find(row => row.requirement.id === requirement.id)?.status === 'GAP'));
    return { requirement, sites: covering, state: covering.length > 0 ? 'COVERED' : natural ? 'GAP' : 'UNCOVERED' };
  });
}
