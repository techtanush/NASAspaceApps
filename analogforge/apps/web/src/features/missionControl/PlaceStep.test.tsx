import type { ReactNode } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { MissionControlProvider } from './state';
import { PlaceStep } from './PlaceStep';
vi.mock('./coverage', () => ({ useCoverage: () => ({ state: 'UNKNOWN', message: 'No coverage has been verified.' }) }));
vi.mock('../../maps/PlanetaryPanel', () => ({ PlanetaryPanel: () => <p>Planetary surface boundary</p> }));
vi.mock('./PracticeTargetArea', () => ({ PracticeTargetArea: () => <button data-testid="practice-example">Use practice target area</button>, ExactTargetBounds: () => <span>Exact target bounds</span> }));
vi.mock('./StageShell', () => ({ useScene: () => {}, Guide: ({ children }: { children: ReactNode }) => <p>{children}</p>, Panel: ({ children, footer }: { children: ReactNode; footer: ReactNode }) => <main>{children}{footer}</main>, Choice: ({ options, onChange, label }: { options: { value: string; label: string }[]; onChange: (value: string) => void; label: string }) => <div role="group" aria-label={label}>{options.map(option => <button key={option.value} onClick={() => onChange(option.value)}>{option.label}</button>)}</div> }));

it('prioritizes actual place controls and keeps optional synthetic examples closed until explicitly opened', () => {
  render(<MemoryRouter><MissionControlProvider><PlaceStep/></MissionControlProvider></MemoryRouter>);
  const summary = screen.getByText('Practice datasets (synthetic)'); const disclosure = summary.closest('details')!;
  expect(disclosure.open).toBe(false); expect(screen.getByTestId('practice-example')).not.toBeVisible();
  expect(screen.getByRole('button', { name: 'Gale Crater Curiosity landing region' })).toBeVisible();
  expect(screen.getByLabelText('Latitude (°)')).toBeVisible(); expect(screen.getByLabelText('Longitude (°)')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: /^Moon$/ }));
  fireEvent.click(screen.getByRole('button', { name: 'Mare Tranquillitatis Apollo 11 landing region' }));
  expect(screen.getByLabelText('Latitude (°)')).not.toHaveValue(''); expect(disclosure.open).toBe(false);
  fireEvent.click(summary); expect(disclosure.open).toBe(true); expect(screen.getByRole('button', { name: 'Use practice target area' })).toBeVisible();
  expect(screen.getByText(/does not establish NASA coverage/)).toBeVisible();
});
