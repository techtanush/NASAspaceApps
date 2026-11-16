import { loadGlobeCatalog } from '../api/globeCatalog';
import { useEffect, useRef, useState } from 'react';
import { GLOBE_ASSETS, GLOBE_INK, STARFIELD, type GlobeBody } from './globeAssets';
import { markerElement, markerOverlays, type GlobeMarker, type MarkerOverlay } from './globeMarkers';

export type { GlobeMarker } from './globeMarkers';
export interface GlobeScene {
  body: GlobeBody;
  focus?: { lat: number; lng: number; altitude?: number } | null;
  pin?: { lat: number; lng: number } | null;
  box?: number[] | null;
  markers?: GlobeMarker[];
  selectedMarker?: string | null;
  autoRotate?: boolean;
  layout?: 'hero' | 'panel' | 'center' | 'dashboard';
  scanning?: boolean;
}
type OverlayDatum = MarkerOverlay | { kind: 'pin'; lat: number; lng: number };
type Instance = import('globe.gl').GlobeInstance;

const reducedMotion = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
function webglAvailable(): boolean {
  try { const canvas = document.createElement('canvas'); return Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl')); } catch { return false; }
}
function pinElement(): HTMLElement {
  const element = document.createElement('div'); element.className = 'mc-pin'; element.setAttribute('aria-hidden', 'true');
  const stem = document.createElement('span'); stem.className = 'mc-pin-stem'; const head = document.createElement('span'); head.className = 'mc-pin-head';
  element.append(head, stem); return element;
}
function boxPath(box: number[]): number[][] {
  const [west, south, east, north] = box as [number, number, number, number]; const steps = 12; const points: number[][] = [];
  for (let i = 0; i <= steps; i++) points.push([south, west + ((east - west) * i) / steps]);
  for (let i = 0; i <= steps; i++) points.push([south + ((north - south) * i) / steps, east]);
  for (let i = 0; i <= steps; i++) points.push([north, east - ((east - west) * i) / steps]);
  for (let i = 0; i <= steps; i++) points.push([north - ((north - south) * i) / steps, west]);
  return points;
}

/** The persistent 3-D stage. It only displays positions it is given; it derives no scientific quantity. */
export function GlobeStage({ scene, onPick, onMarkerSelect, onSurfaceDetail }: { scene: GlobeScene; onPick?: (lat: number, lng: number) => void; onMarkerSelect?: (id: string) => void; onSurfaceDetail?: () => void }) {
  const [assets, setAssets] = useState(GLOBE_ASSETS);
  useEffect(() => { const controller = new AbortController(); const urls:string[] = []; void loadGlobeCatalog(controller.signal, url => { if (controller.signal.aborted) URL.revokeObjectURL(url); else urls.push(url); }).then(value => { if (!controller.signal.aborted) setAssets(value); }).catch(() => {}); return () => { controller.abort(); urls.forEach(url => URL.revokeObjectURL(url)); }; }, []);
  const container = useRef<HTMLDivElement>(null); const globe = useRef<Instance | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'unavailable'>('loading');
  const pick = useRef(onPick); pick.current = onPick; const select = useRef(onMarkerSelect); select.current = onMarkerSelect;
  const detail = useRef(onSurfaceDetail); detail.current = onSurfaceDetail;
  const layout = useRef(scene.layout ?? 'center'); layout.current = scene.layout ?? 'center';
  const applyOffset = useRef(() => {});
  useEffect(() => {
    const element = container.current; if (!element) return; let cancelled = false; let observer: ResizeObserver | null = null;
    if (!webglAvailable()) { setState('unavailable'); return; }
    void import('globe.gl').then(module => {
      if (cancelled) return; const Globe = module.default;
      const instance = new Globe(element, { animateIn: false, waitForGlobeReady: true });
      instance.backgroundImageUrl(STARFIELD).backgroundColor(GLOBE_INK.space).showGraticules(true)
        .htmlElementsData([]).htmlLat('lat').htmlLng('lng').htmlAltitude(0.01)
        .htmlElement((datum: object) => { const value = datum as OverlayDatum; return value.kind === 'pin' ? pinElement() : markerElement(value, id => select.current?.(id)); })
        .ringsData([]).ringColor(() => GLOBE_INK.ring).ringMaxRadius(5).ringPropagationSpeed(2.2).ringRepeatPeriod(1500)
        .pathsData([]).pathPoints((path: object) => path as number[][]).pathPointLat((point: number[]) => point[0]!).pathPointLng((point: number[]) => point[1]!)
        .pathPointAlt(0.006).pathColor(() => GLOBE_INK.accent).pathStroke(1.4).pathDashLength(1).pathDashGap(0).pathTransitionDuration(0)
        .onGlobeClick(({ lat, lng }: { lat: number; lng: number }) => pick.current?.(lat, lng));
      const controls = instance.controls(); controls.enableRotate = true; controls.enableZoom = true; controls.enablePan = false; controls.minDistance = 165; controls.maxDistance = 520; controls.autoRotateSpeed = 0.35;
      // The overview texture has fixed resolution. Hand a deliberate close zoom to the
      // selected site's tiled map rather than magnifying it down to surface pixels.
      const openDetail = () => { if (instance.pointOfView().altitude <= 0.72) detail.current?.(); };
      controls.addEventListener('end', openDetail);
      const resize = () => {
        const width = element.clientWidth, height = element.clientHeight; if (!width || !height) return;
        instance.width(width).height(height); applyOffset.current();
      };
      applyOffset.current = () => {
        const width = element.clientWidth, height = element.clientHeight; const mobile = width < 768;
        const offset: [number, number] = layout.current === 'center' ? [0, 0] : mobile ? [0, -Math.round(height * 0.2)] : layout.current === 'panel' ? [-Math.round(Math.min(440, width * 0.34) / 2), 0] : [Math.round(width * 0.2), 0];
        instance.globeOffset(offset);
      };
      const contextLost = (event: Event) => { event.preventDefault(); setState('unavailable'); };
      instance.renderer().domElement.addEventListener('webglcontextlost', contextLost);
      resize(); observer = new ResizeObserver(resize); observer.observe(element);
      globe.current = instance; setState('ready');
    }).catch(() => { if (!cancelled) setState('unavailable'); });
    return () => { cancelled = true; observer?.disconnect(); globe.current?._destructor(); globe.current = null; };
  }, []);
  const ready = state === 'ready';
  useEffect(() => {
    const instance = globe.current; if (!ready || !instance) return; const asset = assets[scene.body];
    instance.globeImageUrl(asset.surface).bumpImageUrl(asset.relief ?? '').showAtmosphere(asset.atmosphere !== null);
    if (asset.atmosphere) instance.atmosphereColor(asset.atmosphere.color).atmosphereAltitude(asset.atmosphere.altitude);
  }, [ready, scene.body, assets]);
  useEffect(() => { if (ready) applyOffset.current(); }, [ready, scene.layout]);
  useEffect(() => {
    const instance = globe.current; if (!ready || !instance) return;
    const controls = instance.controls(); controls.autoRotate = false;
  }, [ready, scene.autoRotate]);
  const focusKey = scene.focus ? `${scene.focus.lat}:${scene.focus.lng}:${scene.focus.altitude ?? ''}` : '';
  useEffect(() => {
    const instance = globe.current; if (!ready || !instance || !scene.focus) return;
    instance.pointOfView({ lat: scene.focus.lat, lng: scene.focus.lng, altitude: scene.focus.altitude ?? 1.6 }, reducedMotion() ? 0 : 1500);
  }, [ready, focusKey]);
  const markersKey = JSON.stringify([scene.markers ?? [], scene.selectedMarker ?? null, scene.pin ?? null]);
  useEffect(() => {
    const instance = globe.current; if (!ready || !instance) return;
    const data: OverlayDatum[] = markerOverlays(scene.markers ?? [], scene.selectedMarker);
    if (scene.pin) data.push({ kind: 'pin', lat: scene.pin.lat, lng: scene.pin.lng });
    instance.htmlElementsData(data);
    const selected = (scene.markers ?? []).find(marker => marker.id === scene.selectedMarker);
    const rings = reducedMotion() ? [] : scene.pin ? [scene.pin] : selected ? [{ lat: selected.lat, lng: selected.lng }] : [];
    instance.ringsData(scene.pin && !reducedMotion() ? rings : []);
  }, [ready, markersKey]);
  const boxKey = scene.box ? scene.box.join(',') : '';
  useEffect(() => { const instance = globe.current; if (!ready || !instance) return; instance.pathsData(scene.box ? [boxPath(scene.box)] : []); }, [ready, boxKey]);
  const asset = assets[scene.body];
  return <div className="mc-globe" data-testid="globe-stage" data-body={scene.body} data-state={state} data-scanning={scene.scanning ? 'true' : 'false'}>
    <div ref={container} className="mc-globe-canvas" role="region" aria-label={`Interactive globe of ${asset.label}. Every action is also available from the panel.`}/>
    {state === 'unavailable' && <div className="mc-globe-fallback" data-testid="globe-fallback"><p>The 3-D globe is not available in this browser.</p><p className="helper">Use the coordinate fields and site list; every step works without it.</p></div>}
    <p className="mc-globe-credit" data-testid="globe-credit" data-placeholder={asset.placeholder}>{asset.attribution}</p>
    {asset.context&&<details className="mc-globe-source"><summary>Imagery source and limits</summary><strong>{asset.context.sourceProduct}</strong><p>{asset.attribution}</p><p>{asset.context.width} × {asset.context.height} global context pixels · north up, east-positive longitude. Zooming does not add source detail. This image does not establish scientific coverage.</p><p>{asset.context.usageTerms}</p><p className="mono">{asset.context.sourceUri}</p></details>}
  </div>;
}
