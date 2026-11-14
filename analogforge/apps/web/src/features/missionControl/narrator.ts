import { STATUS_WORD, type Site } from './tour';

/** The guide only restates committed fields. It never estimates, rounds or adds a value. */
const list = (items: string[]) => (items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items.at(-1)}`);
export function narrateSite(site: Site, total: number): string {
  const tested = site.rows.filter(row => row.status === 'PASS').map(row => row.requirement.label);
  const failed = site.rows.filter(row => row.status === 'FAIL').map(row => row.requirement.label);
  const gaps = site.rows.filter(row => row.status === 'GAP').length; const unknown = site.rows.filter(row => row.status === 'UNKNOWN').length;
  const parts = [`Site ${site.index} of ${total}, ${site.candidate.name}: ${STATUS_WORD[site.status].toLowerCase()}.`];
  if (tested.length) parts.push(`It meets ${tested.length === 1 ? 'this requirement' : `${tested.length} requirements`}: ${list(tested)}.`);
  if (failed.length) parts.push(`It does not meet: ${list(failed)}.`);
  if (unknown) parts.push(`${unknown} ${unknown === 1 ? 'requirement is' : 'requirements are'} not yet known.`);
  if (gaps) parts.push(`${gaps} ${gaps === 1 ? 'condition' : 'conditions'} cannot be reproduced on Earth.`);
  return parts.join(' ');
}
export const PROGRESS_STEPS = [
  { states: ['DRAFT', 'VALIDATING'], label: 'Checking inputs' },
  { states: ['CHARACTERIZING'], label: 'Measuring the target terrain' },
  { states: ['DISCOVERING'], label: 'Screening Earth areas' },
  { states: ['QUALIFYING'], label: 'Checking each requirement' },
  { states: ['CRITIQUING'], label: 'Independent review of the evidence' },
] as const;
export const PROVING_LABEL: Record<string, string> = { DESIGNING_TEST: 'Designing the rover test', VERIFYING: 'Verifying the route independently', DIAGNOSING: 'Diagnosing a failed attempt', REPLANNING: 'Re-planning the test', BUILDING_PASSPORT: 'Building the report' };
export const sentenceCase = (state: string) => state.toLowerCase().replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase());
