import { expect, it } from 'vitest';
import { preparationProgress } from './narrator';

it('describes the persisted preparation operation in plain language', () => {
  expect(preparationProgress('PREPARE_FINGERPRINT')).toBe('Preparing mission requirements');
  expect(preparationProgress('PROPOSING_REQUIREMENTS')).toBe('Proposing requirements');
  expect(preparationProgress('Proposing measurable requirements')).toBe('Proposing measurable requirements');
});
