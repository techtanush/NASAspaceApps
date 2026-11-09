import { useEffect, useRef, useState } from 'react';
import maplibregl, { type Map as MapInstance } from 'maplibre-gl';
import type { components } from '../generated/schema';
import { Attribution, CoordinateReadout, IconButton, ScaleBar } from '../components/ui';
import { Minus, Plus, RotateCcw } from 'lucide-react';
import { api } from '../api/client';
import { validateEarthLayer } from './layerRegistry';
type Candidate=components['schemas']['EarthAnalogCandidate'];
export function EarthMap({candidates,selected,onSelect,layers=[]}:{candidates:Candidate[];selected?:string|null;onSelect:(id:string)=>void;layers?:components['schemas']['DisplayLayerManifest'][]}) {
  const container=useRef<HTMLDivElement>(null);const map=useRef<MapInstance|null>(null);const callback=useRef(onSelect);callback.current=onSelect;
  const [unavailable,setUnavailable]=useState(false);const [coordinate,setCoordinate]=useState('WGS84 · longitude, latitude');
  useEffect(()=>{
    if(!container.current)return;
    const probe=document.createElement('canvas');if(!probe.getContext('webgl2')&&!probe.getContext('webgl')){setUnavailable(true);return;}
    const styles=getComputedStyle(document.documentElement);
    try{const instance=new maplibregl.Map({container:container.current,style:{version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':styles.getPropertyValue('--map-water').trim()}}]},center:[-111,36],zoom:3,attributionControl:false,renderWorldCopies:false});map.current=instance;
      instance.on('load',()=>{instance.addSource('graticule',{type:'geojson',data:{type:'FeatureCollection',features:Array.from({length:13},(_,i)=>({type:'Feature' as const,properties:{},geometry:{type:'LineString' as const,coordinates:[[-180+i*30,-80],[-180+i*30,80]]}}))}});instance.addLayer({id:'graticule',type:'line',source:'graticule',paint:{'line-color':styles.getPropertyValue('--map-graticule').trim(),'line-width':1}});instance.addSource('candidates',{type:'geojson',data:{type:'FeatureCollection',features:[]}});instance.addLayer({id:'candidates',type:'fill',source:'candidates',paint:{'fill-color':styles.getPropertyValue('--map-land').trim(),'fill-opacity':1}});instance.addLayer({id:'candidate-outline',type:'line',source:'candidates',paint:{'line-color':styles.getPropertyValue('--accent').trim(),'line-width':2}});instance.on('click','candidates',event=>{const id=event.features?.[0]?.properties?.id;if(typeof id==='string')callback.current(id);});
      });
      instance.on('mousemove',event=>setCoordinate(`${event.lngLat.lng.toFixed(4)}, ${event.lngLat.lat.toFixed(4)} · WGS84`));
      instance.on('error',()=>setUnavailable(true));
      return()=>{instance.remove();map.current=null;};
    }catch{setUnavailable(true);}
  },[]);
  useEffect(()=>{const instance=map.current;if(!instance)return;const update=()=>{const source=instance.getSource('candidates') as maplibregl.GeoJSONSource|undefined;if(!source)return;source.setData({type:'FeatureCollection',features:candidates.map(candidate=>{const [west,south,east,north]=candidate.aoi.bbox;return {type:'Feature',id:candidate.id,properties:{id:candidate.id,name:candidate.name,selected:candidate.id===selected},geometry:{type:'Polygon',coordinates:[[[west,south],[east,south],[east,north],[west,north],[west,south]]]}};})});};if(instance.isStyleLoaded())update();else instance.once('load',update);return()=>{instance.off('load',update);};},[candidates,selected]);
  useEffect(()=>{
    const instance=map.current;if(!instance)return;let disposed=false;const sourceIds:string[]=[];const urls:string[]=[];
    const install=async()=>{for(const layer of layers.filter(item=>item.candidate_id===selected)){try{validateEarthLayer(layer);const response=await api.raw(`/artifacts/${layer.image_artifact_sha256}`);const blob=await response.blob();if(disposed)return;const url=URL.createObjectURL(blob);urls.push(url);const id=`display-${layer.id}`;instance.addSource(id,{type:'image',url,coordinates:layer.earth_corners as [[number,number],[number,number],[number,number],[number,number]]});instance.addLayer({id,type:'raster',source:id,paint:{'raster-opacity':0.8,'raster-resampling':'nearest'}},'candidate-outline');sourceIds.push(id);}catch{setUnavailable(true);}}};
    if(instance.isStyleLoaded())void install();else instance.once('load',install);
    return()=>{disposed=true;instance.off('load',install);if(map.current===instance){for(const id of sourceIds){if(instance.getLayer(id))instance.removeLayer(id);if(instance.getSource(id))instance.removeSource(id);}}urls.forEach(url=>URL.revokeObjectURL(url));};
  },[layers,selected]);
  return <section className="map-region" data-testid="earth-map" aria-label="Earth analog candidate map"><div ref={container} className="map-canvas" aria-label="Candidate extents on Earth"/>{unavailable?<div className="map-fallback" role="status">Map unavailable (WebGL not supported). The candidate list and tables show the same information.</div>:<div className="map-controls"><IconButton label="Zoom in" onClick={()=>map.current?.zoomIn()}><Plus size={16}/></IconButton><IconButton label="Zoom out" onClick={()=>map.current?.zoomOut()}><Minus size={16}/></IconButton><IconButton label="Reset Earth view" onClick={()=>map.current?.jumpTo({center:[-111,36],zoom:3,bearing:0})}><RotateCcw size={16}/></IconButton></div>}<div className="map-footer"><div><ScaleBar text="Earth context · WGS84"/><CoordinateReadout text={coordinate}/></div><Attribution>Offline graticule · candidate extents from server</Attribution></div></section>;
}
