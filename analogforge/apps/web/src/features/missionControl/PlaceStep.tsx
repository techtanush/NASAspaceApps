import { useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { Button, FormField, Input } from '../../components/ui';
import { GLOBE_ASSETS } from '../../maps/globeAssets';
import { Choice, Guide, Panel, useScene } from './StageShell';
import { useMissionControl, type TargetBody } from './state';
import { AREA_SIZES_KM, NAMED_SITES } from './namedSites';
import { formatPlace, longitude360, normalizeLongitude, parseAngle, validLatitude } from './coordinates';
import { useCoverage } from './coverage';
import { ExactTargetBounds, PracticeTargetArea } from './PracticeTargetArea';
import { PlanetaryPanel } from '../../maps/PlanetaryPanel';

const BOX_REASON = { POLE: 'This area would cross the pole. Choose a smaller area or move away from the pole.', ANTIMERIDIAN: 'This area would cross the ±180° meridian. Move the centre or choose a smaller area.', INVALID: 'Enter a latitude and longitude.' };
export function PlaceStep() {
  const { plan, update, box } = useMissionControl(); const navigate = useNavigate();
  const [search,setSearch] = useSearchParams(); const surfaceOpen = search.get('view') === 'target';
  const showSurface = (open:boolean) => { const query = new URLSearchParams(search); if(open)query.set('view','target');else query.delete('view');setSearch(query); };
  const place = useCallback((lat: number, lng: number, siteId: string | null = null) => update({ lat: Number(lat.toFixed(4)), lng: Number(lng.toFixed(4)), latText: lat.toFixed(4), lngText: lng.toFixed(4), siteId, confirmed: false }), [update]);
  const onPick = useCallback((lat: number, lng: number) => place(lat, lng), [place]);
  const hasPoint = plan.lat !== null && plan.lng !== null; const validBox = box?.ok === true;
  useScene({ body: plan.body, layout: 'panel', autoRotate: !hasPoint, focus: hasPoint ? { lat: plan.lat!, lng: plan.lng!, altitude: 1.7 } : { lat: 5, lng: plan.body === 'MARS' ? 120 : 10, altitude: 2.1 }, pin: hasPoint ? { lat: plan.lat!, lng: plan.lng! } : null, box: validBox ? box.bbox : null }, { onPick });
  const coverage = useCoverage(plan.body, validBox ? box.bbox : null);
  const typed = (latText: string, lngText: string) => {
    const lat = parseAngle(latText), lng = normalizeLongitude(parseAngle(lngText)); const ok = validLatitude(lat) && Number.isFinite(lng);
    update({ latText, lngText, lat: ok ? lat : null, lng: ok ? lng : null, siteId: null, confirmed: false });
  };
  const latError = plan.latText !== '' && !validLatitude(parseAngle(plan.latText)) ? 'Latitude is a number from −90 to 90.' : undefined;
  const lngError = plan.lngText !== '' && !Number.isFinite(normalizeLongitude(parseAngle(plan.lngText))) ? 'Longitude is a number from −180 to 360, east positive.' : undefined;
  const sites = NAMED_SITES.filter(site => site.body === plan.body); const asset = GLOBE_ASSETS[plan.body];
  return <>{surfaceOpen&&validBox&&<section className="mc-regional" aria-label="Selected planetary surface"><div className="section-heading"><h2>Explore the selected surface</h2><Button variant="secondary" onClick={()=>showSurface(false)}>Return to globe</Button></div><PlanetaryPanel aoi={plan.exactTarget??{body:plan.body,bbox:box.bbox,latitude_type:'PLANETOCENTRIC',longitude_convention:'NEG180_180',vertical_datum:'Unknown',crs_wkt:null}}/></section>}<Panel testid="place-step" step="Step 1 of 4" title="Where is the mission?" lead="Choose the body, then set the place: pick a known site, type coordinates, or click the globe."
    footer={<><p className="helper" role="status" data-testid="place-summary">{hasPoint && validBox ? `${asset.label} · ${formatPlace(plan.lat!, plan.lng!)} · ${plan.exactTarget ? 'exact target bounds' : `${plan.sizeKm} km area`}` : 'No place selected yet.'}</p><Button variant="primary" data-testid="btn-confirm-place" disabled={!validBox} disabledReason="Set a valid place first." onClick={() => { update({ confirmed: true }); navigate('/start/mission'); }}>Confirm location<ArrowRight size={16} aria-hidden="true"/></Button></>}>
    <p className="helper">Setup stays here while you navigate. Reloading starts a new setup; preparing requirements saves a mission draft.</p>
    <Guide>{hasPoint ? `Pin set on ${asset.label}. Adjust the area if needed, then confirm.` : `Start by choosing where on ${asset.label} the rover will operate.`}</Guide>
    <div className="mc-field"><span className="mc-field-label" id="body-label">Target body</span>
      <Choice<TargetBody> testid="choice-body" label="Target body" value={plan.body} options={[{ value: 'MARS', label: 'Mars' }, { value: 'MOON', label: 'Moon' }]} onChange={body => update({ body, lat: null, lng: null, latText: '', lngText: '', siteId: null, confirmed: false })}/></div>
    <div className="mc-field"><span className="mc-field-label">Known sites</span>
      <ul className="mc-sites" data-testid="named-sites">{sites.map(site => <li key={site.id}><button type="button" className="mc-site" data-testid="named-site" data-site={site.id} aria-pressed={plan.siteId === site.id} onClick={() => place(site.lat, site.lng, site.id)}><strong>{site.name}</strong><span>{site.note}</span></button></li>)}</ul></div>
    <div className="mc-coords">
      <FormField label="Latitude (°)" hint="Planetocentric, north positive" error={latError}><Input data-testid="input-latitude" inputMode="decimal" value={plan.latText} placeholder="Enter latitude" onChange={event => typed(event.target.value, plan.lngText)}/></FormField>
      <FormField label="Longitude (°)" hint="East positive; 0–360 also accepted" error={lngError}><Input data-testid="input-longitude" inputMode="decimal" value={plan.lngText} placeholder="Enter longitude" onChange={event => typed(plan.latText, event.target.value)}/></FormField>
    </div>
    {hasPoint && <p className="mc-readout mono" data-testid="coordinate-readout">{formatPlace(plan.lat!, plan.lng!)} · {longitude360(plan.lng!)}{plan.exactTarget && <><br/><ExactTargetBounds target={plan.exactTarget}/></>}</p>}
    <div className="mc-field"><span className="mc-field-label">Area to analyse</span>
      <Choice<string> testid="choice-size" label="Area size" value={plan.exactTarget ? 'exact' : String(plan.sizeKm)} options={AREA_SIZES_KM.map(size => ({ value: String(size), label: `${size} km` }))} onChange={size => update({ sizeKm: Number(size), confirmed: false })}/>
      {hasPoint && box && !box.ok && <p className="mc-error" role="alert" data-testid="box-error">{BOX_REASON[box.reason]}</p>}</div>
    <details className="mc-source"><summary>Practice datasets (synthetic)</summary><p className="helper">Optional configured examples for rehearsal. Selecting a practice area changes the target to its displayed bounds; it does not establish NASA coverage at a named site.</p><PracticeTargetArea/></details>
    <div className="mc-coverage" data-testid="coverage" data-coverage={coverage.state}><span className="mc-dot" aria-hidden="true"/><div><strong>{coverage.state === 'UNKNOWN' ? 'Coverage not yet known' : coverage.state === 'COVERED' ? 'Terrain data available' : coverage.state === 'PARTIAL' ? 'Partial terrain data' : 'No terrain data here'}</strong><span>{coverage.message}</span></div></div>
    {validBox&&<Button variant="secondary" aria-pressed={surfaceOpen} onClick={()=>showSurface(!surfaceOpen)}>{surfaceOpen?'Close surface detail':'Inspect surface imagery'}</Button>}
  </Panel></>;
}
