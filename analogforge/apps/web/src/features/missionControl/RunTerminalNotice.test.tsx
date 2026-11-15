import { expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { components } from '../../generated/schema';
import { RunTerminalNotice } from './RunTerminalNotice';
const state = vi.hoisted(() => ({ error: null as unknown, data: { items: [] as Record<string, unknown>[] } }));
vi.mock('./RunActivity', () => ({ useRunActivity: () => state }));
const run = { run_id: 'run', state: 'FAILED' } as components['schemas']['RunSnapshot'];
it('keeps a safe recorded terminal reason and recovery link visible alongside retained evidence', () => {
  state.data.items = [{ run_id: 'run', state: 'FAILED', status: 'FAILED', event_type: 'run.failed', summary: 'The model response failed required checks; no invalid proposal was accepted.', failure_code: 'MODEL_OUTPUT_INVALID' }];
  const { rerender } = render(<MemoryRouter><RunTerminalNotice run={run}/></MemoryRouter>);
  expect(screen.getByTestId('run-terminal-notice')).toHaveTextContent('MODEL_OUTPUT_INVALID');
  expect(screen.getByRole('status', { name: 'Recorded investigation outcome' })).toHaveAttribute('aria-live', 'polite');
  expect(screen.getByRole('status', { name: 'Recorded investigation outcome' })).toHaveAttribute('aria-atomic', 'true');
  expect(screen.getByText(/no invalid proposal/)).toBeVisible();
  expect(screen.getByRole('link', { name: 'Inspect evidence and recovery options' })).toHaveAttribute('href', '/runs/run/target');
  state.error = new Error('Unauthorized');
  rerender(<MemoryRouter><RunTerminalNotice run={run}/></MemoryRouter>);
  expect(screen.queryByText(/no invalid proposal/)).not.toBeInTheDocument();
  expect(screen.getByTestId('run-terminal-notice')).toHaveTextContent('recorded reason is unavailable');
  state.error = null;
  rerender(<MemoryRouter><RunTerminalNotice run={{ ...run, state: 'COMPLETED' }}/></MemoryRouter>);
  expect(screen.queryByTestId('run-terminal-notice')).not.toBeInTheDocument();
});
it('explains a review pause without raw error codes in the primary message and retains the exact record', () => {
  state.error = null; state.data.items = [];
  render(<MemoryRouter><RunTerminalNotice run={{ ...run, state: 'BLOCKED', blocked_dependencies: ['USER_REVIEW_REQUIRED'] }}/></MemoryRouter>);
  expect(screen.getByText('Review needed')).toBeVisible();
  expect(screen.getByText(/An evidence review needs attention/)).toBeVisible();
  const code = screen.getByText(/Recorded dependencies: USER_REVIEW_REQUIRED/);
  expect(code).not.toBeVisible();
  fireEvent.click(screen.getByText('Technical status'));
  expect(code).toBeVisible();
  expect(screen.getByRole('link', { name: 'Inspect evidence and recovery options' })).toHaveAttribute('href', '/runs/run/target');
});

it('shows the admitted concern from the paused role despite its earlier workflow stage, without changing results', () => {
  state.error=null;
  state.data.items=[{run_id:'run',state:'QUALIFYING',status:'BLOCKED',event_type:'agent.completed',role_result_id:'review',review_concerns:[{message:'The accepted requirement needs a source-date check.',message_truncated:false,severity:'BLOCKING',requirement_label:'Terrain support'}]}, {run_id:'foreign',state:'BLOCKED',status:'BLOCKED',event_type:'agent.completed',role_result_id:'foreign-review',review_concerns:[{message:'Foreign concern',message_truncated:false,severity:'BLOCKING',requirement_label:null}]}];
  const {rerender}=render(<MemoryRouter><RunTerminalNotice run={{...run,state:'BLOCKED'}}/></MemoryRouter>);
  expect(screen.getByRole('region',{name:'Recorded reviewer concerns'})).toHaveTextContent('The accepted requirement needs a source-date check.');
  expect(screen.queryByText('Foreign concern')).not.toBeInTheDocument();
  expect(screen.getByText(/measured benchmark results remain unchanged/)).toBeVisible();
  state.error=new Error('Forbidden');rerender(<MemoryRouter><RunTerminalNotice run={{...run,state:'BLOCKED'}}/></MemoryRouter>);
  expect(screen.queryByRole('region',{name:'Recorded reviewer concerns'})).not.toBeInTheDocument();
  state.error=null;
});
