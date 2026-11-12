import { expect, it } from 'vitest';
import { recordedChange } from './requirements';

it('parses a recorded replan change written with the platform ASCII arrow or the fixture arrow', () => {
  expect(recordedChange('Changed elements: strategy: WAYPOINT_RETURN -> EXPOSURE_COVERAGE')).toEqual({ field: 'strategy', before: 'WAYPOINT_RETURN', after: 'EXPOSURE_COVERAGE' });
  expect(recordedChange('Changed elements: candidate: Practice grid-r0c1 → Practice grid-r0c0')).toEqual({ field: 'candidate', before: 'Practice grid-r0c1', after: 'Practice grid-r0c0' });
});

it('returns null for no change or malformed lines', () => {
  expect(recordedChange('Changed elements: none')).toBeNull();
  expect(recordedChange(undefined)).toBeNull();
  expect(recordedChange('Changed elements: strategy only')).toBeNull();
});
