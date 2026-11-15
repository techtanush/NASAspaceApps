import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Minus, Plus, RotateCcw } from 'lucide-react';
import type { components } from '../generated/schema';
import { fetchPlanetaryTile, planetaryViewport, PLANETARY_SOURCES } from '../api/planetaryImagery';
import { formatCoordinatePair } from '../format/coordinates';

type AOI = components['schemas']['AreaOfInterest'];

export function PlanetaryBasemap({ aoi }: { aoi: AOI }) {
  const [zoom, setZoom] = useState(0), [offset, setOffset] = useState<[number, number]>([0, 0]);
  const [images, setImages] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<'loading' | 'ready' | 'unavailable' | 'limited'>('loading');
  const [retry, setRetry] = useState(0), budget = useRef(64);
  const geometry = JSON.stringify(aoi);
  const viewport = useMemo(() => planetaryViewport(JSON.parse(geometry) as AOI, zoom, offset), [geometry, zoom, offset]);
  const source = viewport && PLANETARY_SOURCES[viewport.body];
  useEffect(() => {
    if (!viewport) return;
    const abort = new AbortController(), urls: string[] = [];
    setImages({}); setStatus('loading');
    let next = 0, failed = false;
    const worker = async () => {
      while (!abort.signal.aborted && next < viewport.tiles.length) {
        if (budget.current <= 0) { failed = true; setStatus('limited'); abort.abort(); return; }
        budget.current--; const tile = viewport.tiles[next++]!;
        try {
          const image = await fetchPlanetaryTile(viewport.body, viewport.z, tile.x, tile.y, abort.signal);
          if (abort.signal.aborted) return;
          const url = URL.createObjectURL(image); urls.push(url);
          setImages(current => ({ ...current, [`${tile.x}:${tile.y}`]: url }));
        } catch {
          if (!abort.signal.aborted) { failed = true; setStatus('unavailable'); abort.abort(); }
        }
      }
    };
    void Promise.all(Array.from({ length: Math.min(4, viewport.tiles.length) }, worker)).then(() => {
      if (!abort.signal.aborted && !failed) setStatus('ready');
    });
    return () => { abort.abort(); urls.forEach(url => URL.revokeObjectURL(url)); };
  }, [viewport, retry]);
  if (!viewport || !source) return <p className="helper" role="status">Orbital imagery is unavailable for this coordinate frame. Open Coordinates and region tools to inspect the declared region.</p>;
  const pan = (x: number, y: number) => setOffset([
    (viewport.bounds[0] + viewport.bounds[2]) / 2 + x * viewport.width * 0.3 - (aoi.bbox[0]! + aoi.bbox[2]!) / 2,
    (viewport.bounds[1] + viewport.bounds[3]) / 2 + y * viewport.height * 0.3 - (aoi.bbox[1]! + aoi.bbox[3]!) / 2,
  ]);
  const centre = formatCoordinatePair((aoi.bbox[0]! + aoi.bbox[2]!) / 2, (aoi.bbox[1]! + aoi.bbox[3]!) / 2, `${aoi.body === 'MARS' ? 'Mars' : 'Moon'} · planetocentric latitude, east-positive longitude`);
  return <div className="planetary-basemap">
    <p className="helper">Explore the actual surface from orbit. The outlined area is your selected mission region.</p>
    <div className="planetary-surface-frame">
      <svg viewBox="0 0 640 400" className="planetary-orbital-svg" role="img" aria-label={`${aoi.body === 'MARS' ? 'Mars' : 'Moon'} orbital imagery of the selected mission region`}>
        {viewport.tiles.map(tile => images[`${tile.x}:${tile.y}`] && <image key={`${tile.x}:${tile.y}`} href={images[`${tile.x}:${tile.y}`]} x={tile.left} y={tile.top} width={tile.size} height={tile.size} preserveAspectRatio="none"/>)}
        <rect className="planetary-target-outline" x={viewport.selection.x} y={viewport.selection.y} width={viewport.selection.width} height={viewport.selection.height} vectorEffect="non-scaling-stroke"/>
      </svg>
      <div className="planetary-map-controls" role="group" aria-label="Explore planetary imagery">
        <button type="button" aria-label="Zoom in on planetary surface" disabled={viewport.z >= source.maxZoom || status === 'limited'} onClick={() => setZoom(zoom + 1)}><Plus size={17}/></button>
        <button type="button" aria-label="Zoom out on planetary surface" disabled={viewport.z <= 0 || status === 'limited'} onClick={() => setZoom(zoom - 1)}><Minus size={17}/></button>
        <button type="button" aria-label="Recenter selected planetary region" onClick={() => { setZoom(0); setOffset([0, 0]); }}><RotateCcw size={17}/></button>
      </div>
      <div className="planetary-pan-controls" role="group" aria-label="Pan planetary imagery">
        <button type="button" aria-label="Pan planetary imagery west" onClick={() => pan(-1, 0)}><ArrowLeft size={16}/></button>
        <button type="button" aria-label="Pan planetary imagery north" onClick={() => pan(0, 1)}><ArrowUp size={16}/></button>
        <button type="button" aria-label="Pan planetary imagery south" onClick={() => pan(0, -1)}><ArrowDown size={16}/></button>
        <button type="button" aria-label="Pan planetary imagery east" onClick={() => pan(1, 0)}><ArrowRight size={16}/></button>
      </div>
      {status !== 'ready' && <div className="planetary-image-status" role="status">
        {status === 'loading' ? 'Loading orbital imagery…' : <>{status === 'limited' ? 'Imagery request limit reached.' : 'Orbital imagery could not load.'} <button type="button" onClick={() => { budget.current = 64; setRetry(retry + 1); }}>Reload imagery</button></>}
      </div>}
    </div>
    <div className="planetary-location-caption"><strong>Selected region</strong><span className="mono">{centre}</span></div>
    <p className="planetary-imagery-credit">{source.title} · <a href={source.source} target="_blank" rel="noreferrer noopener">Source and imagery service</a></p>
    <details className="planetary-technical"><summary>Imagery source and accuracy</summary>
      <p>{source.credit}. No NASA endorsement.</p><p>{source.limitations}</p>
      <p>Current tile sampling at the equator: approximately {Math.round(viewport.sampleM)} m per image pixel. Camera zoom does not change the measured terrain resolution. Uncovered or failed tiles remain empty.</p>
      <p>Planetocentric latitude and east-positive longitude. These photographs are visual context; slope, traversability and mission suitability require the measured dataset and committed evidence.</p>
    </details>
  </div>;
}
