import { useEffect, useRef, useState } from 'react';
import type { components } from '../../generated/schema';
import { Button, ErrorPanel, FormField, Input } from '../../components/ui';
import { areaBox, normalizeLongitude, parseAngle, validLatitude } from './coordinates';
import { useCoverage } from './coverage';
type S=components['schemas'];
export function nominationArea(latitude:string,longitude:string,size:string):{aoi:S['AreaOfInterest']|null;problem:string|null} {
  const lat=parseAngle(latitude),lng=normalizeLongitude(parseAngle(longitude)),edge=parseAngle(size);
  if(!validLatitude(lat)||!Number.isFinite(lng))return {aoi:null,problem:'Enter a finite latitude from −90 to 90 and an east-positive longitude from −180 to 360.'};
  if(!Number.isFinite(edge)||edge<0.1||edge>80)return {aoi:null,problem:'Choose an approximate area edge from 0.1 to 80 km.'};
  const box=areaBox('EARTH',lat,lng,edge);
  if(!box.ok)return {aoi:null,problem:box.reason==='POLE'?'This area crosses a pole. Move its centre or choose a smaller area.':'This area crosses the ±180° meridian. Move its centre or choose a smaller area.'};
  return {aoi:{body:'EARTH',bbox:box.bbox,longitude_convention:'NEG180_180',latitude_type:'GEODETIC',crs_wkt:null,vertical_datum:'Unknown'},problem:null};
}
export function EarthNomination({run,action,pending,error}:{run:S['RunSnapshot'];action:(request:S['RunAction'])=>Promise<boolean>;pending:boolean;error:unknown}) {
  const [name,setName]=useState('');const [lat,setLat]=useState('');const [lng,setLng]=useState('');const [size,setSize]=useState('1');const [submitted,setSubmitted]=useState(false);const [failed,setFailed]=useState(false);const [submitting,setSubmitting]=useState(false);const issuing=useRef(false);const alive=useRef(true);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  const area=nominationArea(lat,lng,size);const coverage=useCoverage('EARTH',area.aoi?.bbox??null,{id:run.scenario_config_id,default_dataset_lock_id:run.dataset_lock_id});
  const allowed=run.state==='AWAITING_REVIEW';const disabled=pending||submitting||!allowed||!area.aoi||!name.trim()||submitted;
  const submit=async()=>{if(disabled||issuing.current||!area.aoi)return;issuing.current=true;setSubmitting(true);setFailed(false);try{const accepted=await action({action_type:'NOMINATE_CANDIDATE',expected_revision:run.revision,payload:{name:name.trim(),aoi:area.aoi}});if(alive.current){setSubmitted(accepted);setFailed(!accepted);}}catch{if(alive.current)setFailed(true);}finally{issuing.current=false;if(alive.current)setSubmitting(false);}};
  return <details className="mc-nomination mc-source" data-testid="earth-nomination"><summary>Nominate an Earth area</summary><p>Choose a separate candidate for this investigation. The server assesses only the locked Earth source; this action does not acquire new imagery. Unsupported terrain remains unknown.</p>
    <form onSubmit={event=>{event.preventDefault();void submit();}}><FormField label="Earth area name"><Input value={name} maxLength={120} onChange={event=>setName(event.target.value)} disabled={submitted}/></FormField><div className="mc-coords"><FormField label="Earth latitude (°)" hint="Geodetic, north positive"><Input inputMode="decimal" value={lat} onChange={event=>setLat(event.target.value)} disabled={submitted}/></FormField><FormField label="Earth longitude (°)" hint="East positive, −180 to 360"><Input inputMode="decimal" value={lng} onChange={event=>setLng(event.target.value)} disabled={submitted}/></FormField></div><FormField label="Approximate area edge (km)"><Input inputMode="decimal" value={size} onChange={event=>setSize(event.target.value)} disabled={submitted}/></FormField>
    {(lat||lng)&&area.problem&&<p className="mc-error" role="status">{area.problem}</p>}{area.aoi&&<p className="helper">Source footprint: {coverage.state.toLowerCase()}. {coverage.message}</p>}{coverage.error!=null&&<ErrorPanel error={coverage.error}/>}
    <Button type="submit" variant="secondary" disabled={disabled} disabledReason={!allowed?'Earth nomination is available while the investigation awaits review.':undefined}>{submitting?'Awaiting acknowledgement':submitted?'Nomination accepted':'Nominate Earth area'}</Button></form>
    {submitted&&<p className="mc-detail-notice" role="status">The server accepted the nomination. Its separate candidate and evidence will appear as assessment commits; no result is assumed.</p>}{failed&&(error?<ErrorPanel error={error}/>:<p className="mc-error" role="alert">Nomination was not confirmed. Review the run status before retrying.</p>)}
    <p className="helper">Unsent fields are discarded on reload. Accepted nominations remain with this run; cancellation retains committed evidence.</p>
  </details>;
}
