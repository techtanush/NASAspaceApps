import { useState } from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { OperatorFeatures, type CustomFeature } from './OperatorFeatures';

function Editor({ initial = [], limit = 32 }: { initial?: CustomFeature[]; limit?: number }) {
  const [features, setFeatures] = useState(initial);
  return <><OperatorFeatures features={features} onChange={setFeatures} limit={limit}/><output data-testid="declarations">{JSON.stringify(features)}</output></>;
}

it('keeps arbitrary features and a declared zero as informational text, then explicitly clears it to Unknown', () => {
  render(<Editor/>);
  fireEvent.click(screen.getByRole('button', { name: 'Add custom feature' }));
  const feature = within(screen.getByRole('group', { name: 'Feature 1' }));
  expect(feature.getByLabelText('Declared value')).toBeDisabled();
  fireEvent.change(feature.getByLabelText('Feature name'), { target: { value: 'Subsurface drill reach' } });
  fireEvent.click(feature.getByRole('checkbox', { name: 'Value unknown' }));
  fireEvent.change(feature.getByLabelText('Declared value'), { target: { value: '0' } });
  fireEvent.change(feature.getByLabelText('Unit (optional)'), { target: { value: 'cm' } });
  expect(JSON.parse(screen.getByTestId('declarations').textContent!)).toEqual([{ name: 'Subsurface drill reach', value: '0', unit: 'cm', unknown: false }]);
  expect(screen.getByText(/informational declarations/)).toBeVisible();
  fireEvent.click(feature.getByRole('checkbox', { name: 'Value unknown' }));
  expect(JSON.parse(screen.getByTestId('declarations').textContent!)[0]).toMatchObject({ value: null, unknown: true, unit: 'cm' });
});

it('removes only the chosen independent declaration and enforces the supplied context limit', () => {
  render(<Editor limit={2} initial={[{ name: 'A', value: 'low', unit: null, unknown: false }, { name: 'B', value: null, unit: 'm', unknown: true }]}/>);
  expect(screen.getByRole('button', { name: 'Add custom feature' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Remove feature 1' }));
  expect(screen.getByLabelText('Feature name')).toHaveValue('B');
  expect(screen.getByRole('button', { name: 'Add custom feature' })).toBeEnabled();
});

it('does not emit changes while the context is locked or saving', () => {
  const onChange = vi.fn();
  render(<OperatorFeatures features={[{ name: 'Drill', value: null, unit: null, unknown: true }]} onChange={onChange} limit={32} disabled/>);
  expect(screen.getByLabelText('Feature name')).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Remove feature 1' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Add custom feature' })).toBeDisabled();
  expect(onChange).not.toHaveBeenCalled();
});
