import { useEffect, useState } from 'react';
import { addProtocol, removeProtocol, type Map as MapInstance } from 'maplibre-gl';
import type { components } from '../generated/schema';
import { createEarthTileLoader, EARTH_IMAGERY_MAP_MAX_ZOOM, EARTH_IMAGERY_MAX_ZOOM } from '../api/earthImagery';

type Aoi = components['schemas']['AreaOfInterest'];
type Bounds = [number, number, number, number];
export const EARTH_IMAGERY_SOURCE = 'earth-satellite-source';
const PROVIDER = 'https://cloudless.eox.at';
const PUBLISHER = 'https://eox.at';
const LICENSE = 'https://creativecommons.org/licenses/by/4.0/';
// Verified against the official WMTS capabilities and EOX license-non-commercial page.
// The 2016 layer contains modified Copernicus Sentinel data 2016 & 2017; newer layers have different terms.
let nextProtocol = 0;

/** Only an explicitly geographic, local Earth footprint can authorize a regional visual view. */
export function earthImageryBounds(aoi: Aoi): Bounds | null {
  const b = aoi.bbox;
  if (aoi.body !== 'EARTH' || aoi.crs_wkt !== 'EPSG:4326' || aoi.latitude_type !== 'GEODETIC'
    || aoi.longitude_convention !== 'NEG180_180' || b.length !== 4 || !b.every(Number.isFinite)) return null;
  const [w, s, e, n] = b as Bounds;
  if (w < -180 || e > 180 || s < -85 || n > 85 || w >= e || s >= n || e - w > 2 || n - s > 2) return null;
  return [Math.max(-180, w - 0.1), Math.max(-85, s - 0.1), Math.min(180, e + 0.1), Math.min(85, n + 0.1)];
}

/** Approximate horizontal ground sampling of the finest public Mercator tile at the footprint centre. */
export function earthImageryGroundSampling(aoi: Aoi): number | null {
  if (!earthImageryBounds(aoi)) return null;
  const latitude = (aoi.bbox[1]! + aoi.bbox[3]!) / 2;
  return (2 * Math.PI * 6378137 * Math.cos(latitude * Math.PI / 180)) / (256 * 2 ** EARTH_IMAGERY_MAX_ZOOM);
}


export function EarthImagery({ map, aoi, onActiveChange }: { map: MapInstance | null; aoi: Aoi; onActiveChange: (active: boolean) => void }) {
  const [requested, setRequested] = useState(false);
  const [status, setStatus] = useState<'offline' | 'loading' | 'ready' | 'failed' | 'limited'>('offline');
  const bounds = earthImageryBounds(aoi), key = bounds?.join(',') ?? '';
  useEffect(() => {
    if (!requested || !map || !key) return;
    const region = key.split(',').map(Number) as Bounds;
    const protocol = `af-eox-${++nextProtocol}`;
    let disposed = false, removed = false, handledFailure = false;
    const loader = createEarthTileLoader(protocol, () => { if (!disposed) setStatus('ready'); }, limited => {
      if (!disposed) { handledFailure = true; setStatus(limited ? 'limited' : 'failed'); setRequested(false); }
    });
    const oldMaxZoom = map.getMaxZoom(), oldBounds = map.getMaxBounds();
    const onError = (event: { sourceId?: string; error?: { message: string } }) => {
      if (!disposed && !handledFailure && (event.sourceId === EARTH_IMAGERY_SOURCE || event.error?.message === 'SATELLITE_IMAGERY_UNAVAILABLE')) {
        handledFailure = true; setStatus('failed'); setRequested(false);
      }
    };
    const onRemove = () => { removed = true; disposed = true; loader.close(); removeProtocol(protocol); };
    const cleanup = () => {
      disposed = true; loader.close(); map.off('error', onError); map.off('remove', onRemove); removeProtocol(protocol);
      if (!removed) {
        if (map.getLayer(EARTH_IMAGERY_SOURCE)) map.removeLayer(EARTH_IMAGERY_SOURCE);
        if (map.getSource(EARTH_IMAGERY_SOURCE)) map.removeSource(EARTH_IMAGERY_SOURCE);
        map.setMaxBounds(oldBounds); map.setMaxZoom(oldMaxZoom);
      }
      onActiveChange(false);
    };
    try {
      map.on('error', onError);
      map.on('remove', onRemove);
      addProtocol(protocol, loader.load);
      map.setMaxZoom(EARTH_IMAGERY_MAP_MAX_ZOOM);
      map.setMaxBounds([[region[0], region[1]], [region[2], region[3]]]);
      map.addSource(EARTH_IMAGERY_SOURCE, { type: 'raster', tiles: [`${protocol}://tiles/{z}/{x}/{y}`], tileSize: 256,
        minzoom: 0, maxzoom: EARTH_IMAGERY_MAX_ZOOM, bounds: region });
      map.addLayer({ id: EARTH_IMAGERY_SOURCE, type: 'raster', source: EARTH_IMAGERY_SOURCE, paint: { 'raster-opacity': 1, 'raster-fade-duration': 0 } }, 'candidates');
      onActiveChange(true);
    } catch { setStatus('failed'); setRequested(false); }
    return cleanup;
  }, [requested, map, key, onActiveChange]);
  return <section className="earth-imagery" aria-label="Optional satellite visual context">
    <div className="inline-fields"><button type="button" disabled={!map || !bounds} onClick={() => {
      if (requested) { setRequested(false); setStatus('offline'); }
      else { setStatus('loading'); setRequested(true); }
    }}>{requested ? 'Measured terrain view' : 'Load satellite imagery'}</button><span className="helper">{requested ? 'Satellite imagery view · prepared measurements temporarily hidden' : 'Measured terrain / offline extent view'}</span></div>
    <p className="helper">Historical 2016/2017 mosaic · nominal 10 m Sentinel-2 input. {bounds&&<>Finest public tile sampling near this footprint: about {earthImageryGroundSampling(aoi)!.toFixed(1)} m/pixel. </>}Zoom stops at this tile limit.</p>
    <p className="helper">Visual context only; it does not measure slope, surface safety or benchmark coverage. Loading uses the public EOX tile service for this region. Tile sampling is not a guarantee of resolved surface detail.</p>
    {!bounds && <p className="helper">Satellite imagery requires a local Earth footprint in WGS84 geographic coordinates, below 85° latitude.</p>}
    {status === 'loading' && <p role="status">Loading satellite tiles…</p>}
    {status === 'failed' && <p role="status">Satellite imagery unavailable. Measured terrain and the offline footprint view remain available. Select Load satellite imagery to retry.</p>}
    {status === 'limited' && <p role="status">This view reached its 64-tile limit. Measured terrain and the offline footprint view have been restored. Select Load satellite imagery for another bounded view.</p>}
    <p className="helper earth-imagery-credit"><a href={PROVIDER} target="_blank" rel="noreferrer">EOxCloudless</a> by <a href={PUBLISHER} target="_blank" rel="noreferrer">EOX IT Services GmbH</a> (Contains modified Copernicus Sentinel data 2016 &amp; 2017) · <a href={LICENSE} target="_blank" rel="noreferrer">CC BY 4.0</a></p>
  </section>;
}
