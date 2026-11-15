import { Link } from 'react-router-dom';
import type { components } from '../../generated/schema';
import { sentenceCase } from './narrator';
import { useRunActivity } from './RunActivity';

export function RunTerminalNotice({ run }: { run: components['schemas']['RunSnapshot'] }) {
  const terminal = ['FAILED', 'BLOCKED', 'CANCELLED'].includes(run.state);
  const activity = useRunActivity(run, terminal);
  if (!terminal) return null;
  const recorded = activity.error ? undefined : activity.data?.items.filter(item => item.run_id === run.run_id && item.state === run.state && item.status === run.state && !item.event_type.endsWith('.started')).at(-1);
  return <aside className="mc-terminal-notice" role="status" aria-live="polite" aria-atomic="true" aria-label="Recorded investigation outcome" data-testid="run-terminal-notice"><strong>Investigation {sentenceCase(run.state).toLowerCase()}</strong><p>{recorded?.summary ?? (run.state === 'CANCELLED' ? 'This investigation was cancelled. Committed evidence remains available.' : 'The investigation stopped. The detailed recorded reason is unavailable here; committed evidence remains available.')}</p>{recorded?.failure_code && <p className="mono">Recorded code: {recorded.failure_code}</p>}<Link to={`/runs/${run.run_id}/target`}>Inspect evidence and recovery options</Link></aside>;
}
