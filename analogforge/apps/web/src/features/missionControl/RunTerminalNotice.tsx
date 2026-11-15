import { Link } from 'react-router-dom';
import type { components } from '../../generated/schema';
import { sentenceCase } from './narrator';
import { useRunActivity } from './RunActivity';

export function RunTerminalNotice({ run }: { run: components['schemas']['RunSnapshot'] }) {
  const terminal = ['FAILED', 'BLOCKED', 'CANCELLED'].includes(run.state);
  const activity = useRunActivity(run, terminal);
  if (!terminal) return null;
  const dependencies = run.blocked_dependencies ?? [];
  const reviewNeeded = run.state === 'BLOCKED' && dependencies.includes('USER_REVIEW_REQUIRED');
  const title = reviewNeeded ? 'Review needed' : run.state === 'BLOCKED' ? 'Investigation paused' : `Investigation ${sentenceCase(run.state).toLowerCase()}`;
  const guidance = reviewNeeded ? 'An evidence review needs attention before research can continue. Your saved work remains available.'
    : dependencies.includes('PROVIDER_RATE_LIMITED') ? 'The research service has reached its current request limit. Your saved work remains available.'
    : dependencies.includes('NO_COVERAGE') ? 'Source data does not cover the requested area. Inspect the available coverage before continuing.'
    : dependencies.length > 0 ? 'A required input, service or evidence review needs attention before research can continue.' : null;
  const recorded = activity.error ? undefined : activity.data?.items.filter(item => item.run_id === run.run_id && item.state === run.state && item.status === run.state && !item.event_type.endsWith('.started')).at(-1);
  return <aside className="mc-terminal-notice" role="status" aria-live="polite" aria-atomic="true" aria-label="Recorded investigation outcome" data-testid="run-terminal-notice"><strong>{title}</strong><p>{guidance ?? recorded?.summary ?? (run.state === 'CANCELLED' ? 'This investigation was cancelled. Committed evidence remains available.' : 'The investigation stopped. The detailed recorded reason is unavailable here; committed evidence remains available.')}</p>{(recorded?.failure_code || dependencies.length > 0) && <details><summary>Technical status</summary>{recorded?.failure_code && <p className="mono">Recorded code: {recorded.failure_code}</p>}{dependencies.length > 0 && <p className="mono">Recorded dependencies: {dependencies.join(', ')}</p>}</details>}<Link to={`/runs/${run.run_id}/target`}>Inspect evidence and recovery options</Link></aside>;
}
