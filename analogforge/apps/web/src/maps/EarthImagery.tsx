import { useEffect, useState } from 'react';
import { addProtocol, removeProtocol, type Map as MapInstance } from 'maplibre-gl';
import type { components } from '../generated/schema';
import { createEarthTileLoader, earthImageryMaxZoom, type EarthImageryProvider } from '../api/earthImagery';

type Aoi = components['schemas']['AreaOfInterest'];
type Bounds = [number, number, number, number];
export const EARTH_IMAGERY_SOURCE = 'earth-satellite-source';
export const EARTH_IMAGERY_WORLD_BOUNDS: Bounds = [-180, -85, 180, 85];
const PROVIDER = 'https://cloudless.eox.at';
const PUBLISHER = 'https://eox.at';
const LICENSE = 'https://creativecommons.org/licenses/by/4.0/';
// Verified against the official WMTS capabilities and EOX license-non-commercial page.
// The 2016 layer contains modified Copernicus Sentinel data 2016 & 2017; newer layers have different terms.
let nextProtocol = 0;

/** Only an explicitly geographic, local Earth footprint can authorize a regional visual view. */
export function earthImageryBounds(aoi: Aoi): Bounds | null {
  const b = aoi.bbox;
  // Architecture 05 defines Earth API AOIs as WGS84 longitude/latitude. The science screen emits
  // exactly EARTH/GEODETIC/NEG180_180 with crs_wkt=null after its explicit WGS84 always-xy inverse transform
  // (science/ops/terrain.py:aoi_for_bounds). Null is a valid canonical API shape, not permission to guess
  // an arbitrary source CRS. Missing, empty, projected or unrecognized explicit CRS values still fail.
  const canonicalCrs = aoi.crs_wkt === null || aoi.crs_wkt === 'EPSG:4326';
  if (aoi.body !== 'EARTH' || !canonicalCrs || aoi.latitude_type !== 'GEODETIC'
    || aoi.longitude_convention !== 'NEG180_180' || b.length !== 4 || !b.every(Number.isFinite)) return null;
  const [w, s, e, n] = b as Bounds;
  if (w < -180 || e > 180 || s < -85 || n > 85 || w >= e || s >= n || e - w > 2 || n - s > 2) return null;
  return [Math.max(-180, w - 0.1), Math.max(-85, s - 0.1), Math.min(180, e + 0.1), Math.min(85, n + 0.1)];
}

/** Approximate horizontal ground sampling of the finest public Mercator tile at the footprint centre. */
export function earthImageryGroundSampling(aoi: Aoi, provider: EarthImageryProvider = 'eox'): number | null {
  if (!earthImageryBounds(aoi)) return null;
  const latitude = (aoi.bbox[1]! + aoi.bbox[3]!) / 2;
  return (2 * Math.PI * 6378137 * Math.cos(latitude * Math.PI / 180)) / (256 * 2 ** earthImageryMaxZoom(provider));
}

/** Provider coverage preference only; this never nominates or qualifies a research site. */
export function supportsUsgsDetail(aoi: Aoi): boolean {
  if (!earthImageryBounds(aoi)) return false;
  const [w, s, e, n] = aoi.bbox;
  return w! >= -125 && e! <= -66 && s! >= 25 && n! <= 49;
}

export function EarthImagery({ map, aoi, onActiveChange, onViewChange, autoLoad = false, preferHighDetail = false }: { map: MapInstance | null; aoi: Aoi; onActiveChange: (active: boolean) => void; onViewChange?: (satellite: boolean) => void; autoLoad?: boolean; preferHighDetail?: boolean }) {
  const bounds = earthImageryBounds(aoi), key = bounds?.join(',') ?? '';
  const usgsEligible = supportsUsgsDetail(aoi);
  const [choice, setChoice] = useState<EarthImageryProvider>(preferHighDetail && usgsEligible ? 'usgs' : 'eox');
  const provider = choice === 'usgs' && usgsEligible ? 'usgs' : 'eox';
  const maxZoom = earthImageryMaxZoom(provider);
  // A production selected-site view may start imagery automatically. This initial choice never retries
  // a failed view or overrides the user's later Measured terrain choice; a new keyed site starts fresh.
  const [requested, setRequested] = useState(autoLoad && !!bounds);
  const [status, setStatus] = useState<'offline' | 'loading' | 'ready' | 'failed' | 'limited'>(autoLoad && !!bounds ? 'loading' : 'offline');
  useEffect(() => {
    if (!requested || !map || !key) return;
    // The selected footprint establishes eligibility, not a scientific coverage claim for the
    // globally available visual mosaic. Only visible tiles are requested within the session budget.
    const region = EARTH_IMAGERY_WORLD_BOUNDS;
    const protocol = `af-${provider}-${++nextProtocol}`;
    let disposed = false, removed = false, handledFailure = false;
    const loader = createEarthTileLoader(protocol, () => { if (!disposed) setStatus('ready'); }, limited => {
      if (!disposed) { handledFailure = true; setStatus(limited ? 'limited' : 'failed'); setRequested(false); }
    }, globalThis.fetch, provider);
    const oldMaxZoom = map.getMaxZoom();
    const onError = (event: { sourceId?: string; error?: { message: string; name?: string } }) => {
      // Camera changes normally abort superseded raster requests. MapLibre identifies these by name.
      if (event.error?.name === 'AbortError') return;
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
        map.setMaxZoom(oldMaxZoom);
      }
      onActiveChange(false);
    };
    try {
      map.on('error', onError);
      map.on('remove', onRemove);
      addProtocol(protocol, loader.load);
      map.setMaxZoom(maxZoom - 1);
      // Keep MapLibre's native Mercator camera extent. A 360-degree maxBounds constraint
      // triggers a camera matrix failure in the installed version; source bounds remain latitude-safe.
      map.addSource(EARTH_IMAGERY_SOURCE, { type: 'raster', tiles: [`${protocol}://tiles/{z}/{x}/{y}`], tileSize: 256,
        minzoom: 0, maxzoom: maxZoom, bounds: region });
      map.addLayer({ id: EARTH_IMAGERY_SOURCE, type: 'raster', source: EARTH_IMAGERY_SOURCE, paint: { 'raster-opacity': 1, 'raster-fade-duration': 0 } }, 'candidates');
      onActiveChange(true);
    } catch { setStatus('failed'); setRequested(false); }
    return cleanup;
  }, [requested, map, key, onActiveChange, provider, maxZoom]);
  return <section className="earth-imagery" aria-label="Satellite visual context">
    <div className="inline-fields"><button type="button" disabled={!map || !bounds} onClick={() => {
      if (requested) { setRequested(false); setStatus('offline'); onViewChange?.(false); }
      else { setStatus('loading'); setRequested(true); onViewChange?.(true); }
    }}>{requested ? 'Measured terrain view' : 'Load satellite imagery'}</button>{!requested && status !== 'offline' && onViewChange && <button type="button" onClick={() => onViewChange(false)}>View terrain measurements</button>}<span className="helper">{requested ? 'Satellite imagery · visual context' : 'Satellite imagery is off'}</span></div>
    <p className="helper">{provider === 'usgs' ? 'Historical aerial · USDA / USGS · 2017–2021 regional mosaic' : 'Historical satellite · 2016/2017'}{bounds&&<> · finest tile near selected site ~{earthImageryGroundSampling(aoi, provider)!.toFixed(1)} m/pixel</>} · visual context only.</p>
    {!bounds && <p className="helper">Satellite imagery requires a local Earth footprint in WGS84 geographic coordinates, below 85° latitude.</p>}
    {status === 'loading' && map && <p role="status">Loading satellite tiles…</p>}
    {status === 'failed' && <p role="status">Satellite imagery unavailable. Measured terrain and the offline footprint view remain available. Select Load satellite imagery to retry.</p>}
    {status === 'limited' && <p role="status">This view reached its 256-tile limit. Satellite loading has stopped. The offline footprint and an explicit terrain-measurement view remain available. Select Load satellite imagery for another bounded view.</p>}
    <details><summary>Imagery source and resolution</summary>
    {usgsEligible && <label>Imagery layer<select value={provider} onChange={event => {
      setChoice(event.target.value as EarthImageryProvider);
      if (requested) setStatus('loading');
    }}><option value="usgs">USGS aerial · continental United States</option><option value="eox">EOX satellite · global context</option></select></label>}
    {provider === 'usgs' ? <>
      <p className="helper">USGS The National Map · mostly NAIP aerial imagery, 2017–2021 in the continental United States. Source dates and detail vary. The delivered zoom limit is source 16 / camera 15; nominal 1 m inputs do not guarantee 1 m resolved detail. Outside this region, choose the global EOX layer.</p>
      <p className="helper earth-imagery-credit"><a href="https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer" target="_blank" rel="noreferrer">USDA / USGS The National Map: Orthoimagery</a> · service refreshed June 2024.</p>
    </> : <>
      <p className="helper">Historical 2016/2017 mosaic · nominal 10 m Sentinel-2 input. Zoom stops at the delivered public tile limit, source zoom 13 / camera zoom 12.</p>
      <p className="helper earth-imagery-credit"><a href={PROVIDER} target="_blank" rel="noreferrer">EOxCloudless</a> by <a href={PUBLISHER} target="_blank" rel="noreferrer">EOX IT Services GmbH</a> (Contains modified Copernicus Sentinel data 2016 &amp; 2017) · <a href={LICENSE} target="_blank" rel="noreferrer">CC BY 4.0</a></p>
    </>}
    <p className="helper">Visual context only; it does not measure slope, surface safety or benchmark coverage. Loading uses the public {provider === 'usgs' ? 'USGS' : 'EOX'} tile service for the visible map, with at most 256 tile requests per view. Zoom out for global context; measured coverage remains limited to the selected footprint. Tile sampling is not a guarantee of resolved surface detail.</p>
    </details>
  </section>;
}
