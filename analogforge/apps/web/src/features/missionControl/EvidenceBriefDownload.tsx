import { useEffect, useRef, useState } from 'react';
import { Download } from 'lucide-react';
import { api } from '../../api/client';
import { useWorkspace } from '../../app/WorkspaceContext';
import { Button, ErrorPanel } from '../../components/ui';
import type { components } from '../../generated/schema';

type Run = components['schemas']['RunSnapshot'];
export function evidenceBriefPath(run: Run, candidateId: string): string {
  if (!run.candidate_ids.includes(candidateId)) throw new Error('This location does not belong to the current investigation.');
  return `/runs/${encodeURIComponent(run.run_id)}/candidates/${encodeURIComponent(candidateId)}/evidence-brief.pdf`;
}
export function EvidenceBriefDownload({ run, candidateId, allLocations = false }: { run: Run; candidateId: string; allLocations?: boolean }) {
  const workspace = useWorkspace(); const request = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState<unknown>(null);
  useEffect(() => { setBusy(false); setError(null); return () => { request.current?.abort(); }; }, [workspace, run.run_id, candidateId]);
  const download = async () => {
    const controller = new AbortController(); request.current?.abort(); request.current = controller; setBusy(true); setError(null);
    try {
      if (run.workspace_id !== workspace) throw new Error('The investigation belongs to another workspace.');
      const response = await api.raw(allLocations ? `/runs/${encodeURIComponent(run.run_id)}/test-brief.pdf` : evidenceBriefPath(run, candidateId), { signal: controller.signal, headers: { Accept: 'application/pdf' } });
      if (!response.headers.get('content-type')?.startsWith('application/pdf')) throw new Error('The server did not return a PDF. No report was downloaded.');
      const blob = await response.blob();
      if (controller.signal.aborted || request.current !== controller) return;
      if (!blob.size) throw new Error('The PDF was empty. No report was downloaded.');
      const url = URL.createObjectURL(blob); const link = document.createElement('a');
      link.href = url; link.download = allLocations ? `analogforge-mission-test-brief-${run.run_id.slice(0, 8)}.pdf` : `analogforge-evidence-brief-${run.run_id.slice(0, 8)}-${candidateId.slice(0, 8)}.pdf`;
      document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) { if (!controller.signal.aborted && request.current === controller) setError(cause); }
    finally { if (!controller.signal.aborted && request.current === controller) setBusy(false); }
  };
  return <div className="mc-pdf-download"><Button variant={allLocations ? 'secondary' : 'primary'} disabled={busy} onClick={() => { void download(); }}><Download size={16} aria-hidden="true"/>{busy ? 'Preparing PDF…' : allLocations ? 'Download all-location test brief' : 'Download current evidence PDF'}</Button>{error !== null && <ErrorPanel error={error} onRetry={() => { void download(); }}/>}</div>;
}
