import { useMemo } from 'react';
import { useApi } from '../../api/hooks/useApi';
import { useWorkspace } from '../../app/WorkspaceContext';
import type { components } from '../../generated/schema';
import { EarthMap } from '../../maps/EarthMap';
import { PlanetaryPanel } from '../../maps/PlanetaryPanel';
import { ErrorPanel, Skeleton } from '../../components/ui';
import type { Site } from './tour';

type S = components['schemas'];
export function RegionalInspector({ runId, site }: { runId: string; site: Site }) {
  const workspace = useWorkspace();
  const layers = useApi<S['ListDisplayLayerManifest']>(workspace, `/display-layers?run_id=${runId}&candidate_id=${site.candidate.id}`);
  const matching = useMemo(() => (layers.data?.items ?? []).filter(layer => layer.candidate_id === site.candidate.id && layer.body === site.candidate.aoi.body && layer.run_id === runId && layer.workspace_id === workspace && layer.mode === site.candidate.mode), [layers.data, site.candidate.id, site.candidate.aoi.body, runId, workspace, site.candidate.mode]);
  const candidates = useMemo(() => [site.candidate], [site.candidate]);
  return <section className="mc-regional" aria-label={`Regional evidence for ${site.candidate.name}`} data-testid="regional-inspector">
    <header><p className="mc-eyebrow">Regional evidence</p><h2>{site.candidate.name}</h2><p>Selected footprint · {site.candidate.aoi.body} · {site.candidate.mode}</p></header>
    {layers.isPending && <Skeleton label="Loading selected-site layers"/>}
    {layers.error && <ErrorPanel error={layers.error} onRetry={() => { void layers.refetch(); }}/ >}
    {!layers.isPending && !layers.error && matching.length === 0 && <p className="mc-detail-notice" role="status">Terrain imagery unavailable for this site. The boundary is the registered candidate footprint; it is not a terrain measurement.</p>}
    <EarthMap key={site.candidate.id} candidates={candidates} selected={site.candidate.id} onSelect={() => {}} layers={matching}/>
    {matching.map(layer => <details key={layer.id} className="mc-source"><summary>{layer.layer_kind} · source and resolution</summary><p>Comparison support: {layer.support_scale_m === null ? 'Unknown' : `${layer.support_scale_m} m`}. Native / effective source resolution: see source receipts.</p><p>Height reference: {site.candidate.aoi.vertical_datum}</p><p className="mono">Display CRS: {layer.display_crs_wkt}</p><p>No-data: transparent mask · {layer.width_px} × {layer.height_px} display pixels</p><p className="mono">Source evidence: {layer.source_evidence_ids.join(', ') || 'Unknown'}</p></details>)}
    <p className="mc-detail-notice">Zoom changes the display, not the evidence resolution. Layer units, comparison support and limitations appear below the map.</p>
  </section>;
}

export function TargetInspector({ runId, profileId, target }: { runId: string; profileId: string | null; target: S['AreaOfInterest'] }) {
  const workspace = useWorkspace();
  const layers = useApi<S['ListDisplayLayerManifest']>(workspace, `/display-layers?run_id=${runId}&target_profile_id=${profileId}`, !!profileId);
  return <section className="mc-regional" aria-label="Planetary target detail"><header><p className="mc-eyebrow">Planetary evidence</p><h2>Mission target</h2></header>{layers.error && <ErrorPanel error={layers.error}/>}<PlanetaryPanel key={profileId ?? target.body} aoi={target} layers={(layers.data?.items ?? []).filter(layer => layer.run_id === runId && layer.workspace_id === workspace && layer.target_profile_id === profileId && layer.body === target.body)}/></section>;
}
