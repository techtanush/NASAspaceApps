import { useState } from 'react';
import type { components } from '../generated/schema';
import { PlanetaryEvidencePanel } from './PlanetaryEvidencePanel';
import { PlanetaryBasemap } from './PlanetaryBasemap';
import './PlanetaryBasemap.css';

type AOI = components['schemas']['AreaOfInterest'];
type Layer = components['schemas']['DisplayLayerManifest'];

/** Orbital photographs and measured terrain are deliberately separate views. */
export function PlanetaryPanel({ aoi, layers = [], onChange }: {
  aoi: AOI; layers?: Layer[]; onChange?: (aoi: AOI) => void;
}) {
  const measured = layers.some(layer => layer.body === aoi.body && layer.rendering === 'PLANETARY_PLANAR_IMAGE');
  const [view, setView] = useState<'imagery' | 'measured'>('imagery');
  const showMeasured = measured && view === 'measured';
  if (aoi.body === 'EARTH') return <p role="status">Select Mars or Moon for planetary surface imagery. Earth locations use the Earth map.</p>;
  return <section className="planetary-container panel" data-testid="planetary-panel" data-body={aoi.body}>
    <div className="section-heading"><div><p className="planetary-eyebrow">TARGET REGION</p><h2>{aoi.body === 'MARS' ? 'Mars' : 'Moon'} surface</h2></div>
      {measured && <div className="planetary-view-controls" role="group" aria-label="Planetary view">
        <button type="button" aria-pressed={!showMeasured} onClick={() => setView('imagery')}>Orbital imagery</button>
        <button type="button" aria-pressed={showMeasured} onClick={() => setView('measured')}>Measured terrain</button>
      </div>}
    </div>
    {showMeasured ? <PlanetaryEvidencePanel aoi={aoi} layers={layers}/> : <>
      <PlanetaryBasemap key={`${aoi.body}:${aoi.bbox.join(',')}`} aoi={aoi}/>
      <details className="planetary-technical"><summary>Coordinates and region tools</summary>
        <PlanetaryEvidencePanel aoi={aoi} onChange={onChange}/>
      </details>
    </>}
  </section>;
}
