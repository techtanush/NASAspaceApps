import { STATUS_WORD, type Site } from './tour';

/** The guide only restates committed fields. It never estimates, rounds or adds a value. */
export function narrateSite(site: Site, total: number): string {
  const tested = site.rows.filter(row => row.status === 'PASS').map(row => row.requirement.label);
  const failed = site.rows.filter(row => row.status === 'FAIL').map(row => row.requirement.label);
  const gaps = site.rows.filter(row => row.status === 'GAP').length; const unknown = site.rows.filter(row => row.status === 'UNKNOWN').length;
  const parts = [`Site ${site.index} of ${total}, ${site.candidate.name}: ${STATUS_WORD[site.status].toLowerCase()}.`];
  if (tested.length) parts.push(`${tested.length} ${tested.length === 1 ? 'requirement is' : 'requirements are'} supported by current evidence.`);
  if (failed.length) parts.push(`${failed.length} ${failed.length === 1 ? 'requirement fails' : 'requirements fail'}.`);
  if (unknown) parts.push(`${unknown} ${unknown === 1 ? 'requirement remains' : 'requirements remain'} unknown.`);
  if (gaps) parts.push(`${gaps} ${gaps === 1 ? 'condition cannot' : 'conditions cannot'} be reproduced on Earth.`);
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
export const preparationProgress = (step: string) => step === 'PREPARE_FINGERPRINT' ? 'Preparing mission requirements' : sentenceCase(step);
