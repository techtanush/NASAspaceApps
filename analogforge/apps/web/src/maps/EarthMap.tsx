import { formatCoordinatePair } from '../format/coordinates';
import { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import type { Map as MapInstance } from 'maplibre-gl';
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import type { components } from '../generated/schema';
import { Attribution, CoordinateReadout, ErrorPanel, IconButton, Legend, Quantity } from '../components/ui';
import { Minus, Plus, RotateCcw } from 'lucide-react';
import { api } from '../api/client';
import { validateEarthLayer } from './layerRegistry';

// MapLibre 6 loads its web worker from a separate file whose URL it computes at run time (new URL('./maplibre-gl-worker.mjs',
// import.meta.url)). A bundler cannot see that, so the worker would never be emitted: the map would fail to start in the
// production build and in the pre-bundled dev server. Importing the file as an asset makes the bundler emit and serve it.
maplibregl.setWorkerUrl(maplibreWorkerUrl);
type Candidate=components['schemas']['EarthAnalogCandidate'];
type Layer=components['schemas']['DisplayLayerManifest'];
/** Camera geometry only: no scientific quantity or qualification is derived here. */
export function candidateCameraBounds(candidates:Candidate[]):[[number,number],[number,number]]|null {
 const boxes=candidates.filter(candidate=>candidate.aoi.body==='EARTH'&&candidate.aoi.bbox.length===4&&candidate.aoi.bbox.every(Number.isFinite)).map(candidate=>candidate.aoi.bbox);
 if(boxes.length===0)return null;
 return [[Math.min(...boxes.map(box=>box[0]!)),Math.min(...boxes.map(box=>box[1]!))],[Math.max(...boxes.map(box=>box[2]!)),Math.max(...boxes.map(box=>box[3]!))]];
}
export function EarthMap({candidates,selected,onSelect,layers=[]}:{candidates:Candidate[];selected?:string|null;onSelect:(id:string)=>void;layers?:Layer[]}) {
 const container=useRef<HTMLDivElement>(null);const map=useRef<MapInstance|null>(null);const callback=useRef(onSelect);callback.current=onSelect;
 const markers=useRef<maplibregl.Marker[]>([]);
 const currentCandidates=useRef(candidates);currentCandidates.current=candidates;const fitted=useRef(false);
 const [unavailable,setUnavailable]=useState(false);const [layerError,setLayerError]=useState<unknown>(null);const [coordinate,setCoordinate]=useState('WGS84 · move pointer to inspect coordinates');
 const [cameraRevision,setCameraRevision]=useState(0);
 const [visibility,setVisibility]=useState<Record<string,boolean>>({});const [opacity,setOpacity]=useState<Record<string,number>>({});
 const activeLayers=layers.filter(layer=>layer.candidate_id===selected);const viewPreferences=useRef({visibility,opacity});viewPreferences.current={visibility,opacity};
 const fitCandidates=()=>{const instance=map.current;const bounds=candidateCameraBounds(currentCandidates.current);if(instance&&bounds)instance.fitBounds(bounds,{padding:40,maxZoom:15,duration:0});};
 useEffect(()=>{
  if(!container.current)return;
  const probe=document.createElement('canvas');if(!probe.getContext('webgl2')&&!probe.getContext('webgl')){setUnavailable(true);return;}
  try{
   const styles=getComputedStyle(document.documentElement);
   const instance=new maplibregl.Map({container:container.current,style:{version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':styles.getPropertyValue('--map-water').trim()}}]},center:[0,0],zoom:1,attributionControl:false,renderWorldCopies:false});map.current=instance;
   const applyTheme=()=>{
    const tokens=getComputedStyle(document.documentElement);const read=(name:string)=>tokens.getPropertyValue(name).trim();
    if(instance.getLayer('background'))instance.setPaintProperty('background','background-color',read('--map-water'));
    if(instance.getLayer('graticule'))instance.setPaintProperty('graticule','line-color',read('--map-graticule'));
    if(instance.getLayer('candidates'))instance.setPaintProperty('candidates','fill-color',['case',['boolean',['get','selected'],false],read('--surface-3'),read('--map-land')]);
    if(instance.getLayer('candidate-outline'))instance.setPaintProperty('candidate-outline','line-color',['case',['boolean',['get','selected'],false],read('--accent'),read('--accent')]);
   };
   instance.on('load',()=>{
    const meridians=Array.from({length:13},(_,i)=>({type:'Feature' as const,properties:{},geometry:{type:'LineString' as const,coordinates:[[-180+i*30,-80],[-180+i*30,80]]}}));
    const parallels=Array.from({length:9},(_,i)=>({type:'Feature' as const,properties:{},geometry:{type:'LineString' as const,coordinates:[[-180,-80+i*20],[180,-80+i*20]]}}));
    instance.addSource('graticule',{type:'geojson',data:{type:'FeatureCollection',features:[...meridians,...parallels]}});
    instance.addLayer({id:'graticule',type:'line',source:'graticule',paint:{'line-color':styles.getPropertyValue('--map-graticule').trim(),'line-width':1}});
    instance.addSource('candidates',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
    instance.addLayer({id:'candidates',type:'fill',source:'candidates',paint:{'fill-color':styles.getPropertyValue('--map-land').trim(),'fill-opacity':1}});
    instance.addLayer({id:'candidate-outline',type:'line',source:'candidates',paint:{'line-color':styles.getPropertyValue('--accent').trim(),'line-width':['case',['boolean',['get','selected'],false],3,2]}});
    instance.on('click','candidates',event=>{const id=event.features?.[0]?.properties?.id;if(typeof id==='string')callback.current(id);});
    instance.on('mouseenter','candidates',()=>{instance.getCanvas().style.cursor='pointer';});instance.on('mouseleave','candidates',()=>{instance.getCanvas().style.cursor='';});
    instance.addControl(new maplibregl.ScaleControl({maxWidth:100,unit:'metric'}),'bottom-left');applyTheme();setCameraRevision(value=>value+1);
   });
   instance.on('mousemove',event=>setCoordinate(formatCoordinatePair(event.lngLat.lng,event.lngLat.lat)));
   instance.on('error',event=>setLayerError(event.error));
   const themeObserver=new MutationObserver(()=>{if(map.current===instance&&instance.isStyleLoaded())applyTheme();});themeObserver.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
   const resizeObserver=new ResizeObserver(()=>instance.resize());resizeObserver.observe(container.current);
   return()=>{themeObserver.disconnect();resizeObserver.disconnect();markers.current.forEach(marker=>marker.remove());markers.current=[];instance.remove();map.current=null;fitted.current=false;};
  }catch{setUnavailable(true);}
 },[]);
 useEffect(()=>{
  const instance=map.current;if(!instance)return;
  const update=()=>{
   const source=instance.getSource('candidates') as maplibregl.GeoJSONSource|undefined;if(!source)return;
   source.setData({type:'FeatureCollection',features:candidates.filter(candidate=>candidate.aoi.body==='EARTH').map(candidate=>{const [west,south,east,north]=candidate.aoi.bbox;return {type:'Feature',id:candidate.id,properties:{id:candidate.id,name:candidate.name,selected:candidate.id===selected},geometry:{type:'Polygon',coordinates:[[[west,south],[east,south],[east,north],[west,north],[west,south]]]}};})});
   markers.current.forEach(marker=>marker.remove());markers.current=[];
   candidates.forEach((candidate,index)=>{if(candidate.aoi.body!=='EARTH')return;const [west,south,east,north]=candidate.aoi.bbox;if([west,south,east,north].some(value=>value===undefined||!Number.isFinite(value)))return;const element=document.createElement('button');element.type='button';element.className='map-candidate-label';element.textContent=`C${index+1}`;element.setAttribute('aria-label',`Select C${index+1}: ${candidate.name}${candidate.id===selected?' (selected)':''}`);element.setAttribute('aria-pressed',String(candidate.id===selected));element.title=candidate.name;element.addEventListener('click',()=>callback.current(candidate.id));markers.current.push(new maplibregl.Marker({element,anchor:'center'}).setLngLat([(west!+east!)/2,(south!+north!)/2]).addTo(instance));});
   if(!fitted.current&&candidateCameraBounds(candidates)){fitCandidates();fitted.current=true;}
  };
  if(instance.isStyleLoaded())update();else instance.once('load',update);return()=>{instance.off('load',update);};
 },[candidates,selected,cameraRevision]);
 useEffect(()=>{
  const instance=map.current;if(!instance)return;let disposed=false;const abort=new AbortController();const sourceIds:string[]=[];const urls:string[]=[];setLayerError(null);
  const install=async()=>{for(const layer of layers.filter(item=>item.candidate_id===selected)){try{validateEarthLayer(layer);const response=await api.raw(`/artifacts/${layer.image_artifact_sha256}`,{signal:abort.signal});const blob=await response.blob();if(disposed)return;const url=URL.createObjectURL(blob);urls.push(url);const id=`display-${layer.id}`;instance.addSource(id,{type:'image',url,coordinates:layer.earth_corners as [[number,number],[number,number],[number,number],[number,number]]});instance.addLayer({id,type:'raster',source:id,layout:{visibility:viewPreferences.current.visibility[layer.id]===false?'none':'visible'},paint:{'raster-opacity':viewPreferences.current.opacity[layer.id]??0.8,'raster-resampling':'nearest'}},'candidate-outline');sourceIds.push(id);}catch(error){if(!disposed)setLayerError(error);}}};
  if(instance.isStyleLoaded())void install();else instance.once('load',install);
  return()=>{disposed=true;abort.abort();instance.off('load',install);if(map.current===instance){for(const id of sourceIds){if(instance.getLayer(id))instance.removeLayer(id);if(instance.getSource(id))instance.removeSource(id);}}urls.forEach(url=>URL.revokeObjectURL(url));};
 },[layers,selected]);
 useEffect(()=>{const instance=map.current;if(!instance||!instance.isStyleLoaded())return;for(const layer of activeLayers){const id=`display-${layer.id}`;if(instance.getLayer(id)){instance.setLayoutProperty(id,'visibility',visibility[layer.id]===false?'none':'visible');instance.setPaintProperty(id,'raster-opacity',opacity[layer.id]??0.8);}}},[activeLayers,visibility,opacity]);
 return <div className="earth-map-panel"><p className="map-context helper">Offline extent view · WGS84 · no basemap imagery. Labels C1–C{candidates.length} match the candidate table. {activeLayers.length?`Prepared layer source mode: ${activeLayers.map(layer=>layer.mode).join(', ')}.`:'No prepared raster selected; outlines show server-provided geometry only.'}{selected&&candidates.some(candidate=>candidate.id===selected)&&<span className="map-selection-readout">Selected: C{candidates.findIndex(candidate=>candidate.id===selected)+1} · {candidates.find(candidate=>candidate.id===selected)?.name}</span>}</p><section className="map-region" data-testid="earth-map" aria-label="Earth analog candidate map"><div ref={container} className="map-canvas" aria-label="Candidate extents on Earth"/>{unavailable?<div className="map-fallback" role="status">Map unavailable (WebGL not supported). The candidate list and tables show the same information.</div>:<div className="map-controls"><IconButton label="Zoom in" onClick={()=>map.current?.zoomIn()}><Plus size={16}/></IconButton><IconButton label="Zoom out" onClick={()=>map.current?.zoomOut()}><Minus size={16}/></IconButton><IconButton label="Fit candidate extents" onClick={fitCandidates}><RotateCcw size={16}/></IconButton></div>}<div className="map-footer"><CoordinateReadout text={coordinate}/><Attribution>Source: server candidate extents · mode {Array.from(new Set(candidates.map(candidate=>candidate.mode))).join(', ')||'Unknown'} · offline graticule</Attribution></div></section>{layerError!=null&&<ErrorPanel error={{code:'DISPLAY_LAYER_UNAVAILABLE',message:'A prepared layer could not be displayed. The candidate list and evidence tables remain available.'}}/>}{activeLayers.map(layer=><fieldset key={layer.id} className="map-layer-controls"><legend>{layer.layer_kind} · {layer.mode.toUpperCase()}</legend><label className="inline-fields"><input type="checkbox" checked={visibility[layer.id]!==false} onChange={event=>setVisibility({...visibility,[layer.id]:event.target.checked})}/>Show prepared layer</label><label className="form-field">Opacity (0–1)<input type="range" min="0" max="1" step="0.1" value={opacity[layer.id]??0.8} onChange={event=>setOpacity({...opacity,[layer.id]:Number(event.target.value)})}/></label><p className="helper">Units: {layer.unit} · comparison support <Quantity value={layer.support_scale_m} unit="m"/></p><Legend items={layer.legend} unit={layer.unit}/><p className="helper">{layer.limitations.join(' · ')}</p><Attribution>{layer.attribution.join(' · ')}</Attribution></fieldset>)}</div>;
}
