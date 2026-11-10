import { expect, test } from '@playwright/test';
import {readFileSync} from 'node:fs';
import { newMission, startRun, tab, prove,api,fixture } from './support/workbench';
// The implementation is shared with the command-line audit and imports no application code.
// @ts-expect-error JavaScript audit module exports are checked by the runtime audit.
import {auditPage,auditGlyphs,finishAudit,THRESHOLDS,COMPONENTS,reports,installAuditInstrumentation,auditFailures,auditCancellations,waitForAuditData,auditStyleguide,captureStyleguide} from '../../scripts/ui/visual_audit.mjs';
test('UIX-13 complete visual audit C01–C20',async({page})=>{
 test.setTimeout(3600000);page.setDefaultTimeout(15000);
 page.on('request',request=>{if(request.method()==='POST')console.log('audit mutation',new URL(request.url()).pathname);});page.on('response',response=>{if(response.request().method()==='POST')console.log('audit acknowledgement',response.status(),new URL(response.url()).pathname);});
 page.on('framenavigated',frame=>{if(frame===page.mainFrame())console.log('audit navigation',frame.url());});
 const faults: string[]=[];const external:string[]=[];
 page.on('pageerror',e=>faults.push(e.message));page.on('console',m=>{if(['error','warning'].includes(m.type()))faults.push(m.text());});
 page.on('request',r=>{if(/^https?:/.test(r.url())&&new URL(r.url()).origin!==(process.env.E2E_BASE_URL||'http://127.0.0.1:5176'))external.push(r.url());});
 await installAuditInstrumentation(page);
 await page.clock.setFixedTime(new Date('2026-11-08T12:00:00Z'));
 const capture=async(name:string)=>{
  console.log('audit screen',name);const view=name.split('-')[0]!;const headings:Record<string,string>={S01:'Missions and runs',S02:'Mission authoring',S03:'Rover library',S04:'Mission authoring',S05:'Target evidence',S06:'Earth analog candidates',S07:'Qualification',S08:'Rover compatibility',S09:'Composite portfolio',S10:'Test lab',S11:'Test lab',S12:'Analog Passport',styleguide:'Component styleguide'};await expect(page.locator('main h1')).toHaveText(headings[view]!);await page.evaluate(()=>document.fonts.ready);
  await expect(page.locator('main h1')).toBeVisible();await waitForAuditData(page);
  for(const [width,height]of THRESHOLDS.viewports)for(const theme of ['dark','light']){
   const densities=['S06','S07','S10'].includes(view)?['compact','default','comfortable']:['default'];
   for(const density of densities)await auditPage(page,name,{width,height,theme,density,focus:true,expectedHeading:headings[view]});
   if(['S02','S04','S07','S12'].includes(view)){
    await auditPage(page,name,{width,height,theme,density:'default',spacing:true,focus:false,expectedHeading:headings[view]});
   }
  }
 };
 const evidence=async(name:string,anchor:string,scrollToEnd:string[]=[])=>{
  console.log('audit review evidence',name);
  for(const width of [1440,390])for(const theme of ['dark','light']){
   const height=width===390?844:900;
   await auditPage(page,name,{width,height,theme,density:'default',focus:false,anchor,scrollToEnd});
   await expect(page.locator(anchor).first()).toBeInViewport();
  }
 };
 const captureOverlay=async(name:string,title:string,open:()=>Promise<void>)=>{
  for(const [width,height]of THRESHOLDS.viewports)for(const theme of ['dark','light']){
   await page.setViewportSize({width,height});await open();await expect(page.getByRole('dialog',{name:title,exact:true})).toBeVisible();
   await auditPage(page,name,{width,height,theme,density:'default',focus:true});
   if(await page.getByRole('dialog',{name:title,exact:true}).isVisible())await page.keyboard.press('Escape');
   await expect(page.getByRole('dialog',{name:title,exact:true})).toBeHidden();
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  }
 };
 let crawlError:unknown=null;
 try{
  await page.goto('/?mockLatency=300');await capture('S01');
  await page.getByTestId('btn-new-mission').click();await capture('S02');await captureOverlay('change-body-dialog','Change target body',async()=>{await page.locator('[data-testid=radio-body][data-body=MOON]').click();});
  await page.goto('/rovers');await capture('S03');
  await newMission(page);await capture('S04');await evidence('review-contract-digest','[data-region=fingerprint] .hash-group');await evidence('review-acceptance-controls','[data-region=run-configuration] .actions');await page.getByTestId('btn-start-run').click();await expect(page.getByTestId('run-state-banner')).toHaveAttribute('data-state','AWAITING_REVIEW');
  for(const [screen,name]of [['S05','target'],['S06','analogs'],['S07','qualification'],['S08','compatibility'],['S09','portfolio'],['S10','test-lab']]){await tab(page,name);await capture(screen);if(screen==='S05'){await evidence('review-target-chart-description','.target-histogram .chart .section-heading');await evidence('review-target-chart','[data-testid=target-panel] .target-histogram .chart-plot-scroll');await evidence('review-target-chart-right','[data-testid=target-panel] .target-histogram .chart-plot-scroll',['.target-histogram .chart-plot-scroll']);await evidence('review-target-chart-data','.target-histogram .table-frame');}if(screen==='S10'){await evidence('review-benchmark-rules','.accepted-benchmarks');}if(name==='analogs'){const candidate=page.getByTestId('candidate-row').first();await candidate.getByTestId('btn-select-candidate').click();await expect(candidate).toHaveAttribute('data-selected','true');}if(screen==='S09'){await page.getByTestId('btn-build-portfolio').click();await expect(page.getByTestId('portfolio-row').first()).toBeVisible();await capture('S09-composite');}if(screen==='S07'){
   await captureOverlay('evidence-drawer','Evidence receipt',async()=>{const cell=page.getByTestId('qual-cell').first();const details=cell.locator('details');if(!await details.evaluate(node=>(node as HTMLDetailsElement).open))await details.locator('summary').click();const link=details.getByTestId('evidence-link').first();const evidenceId=await link.getAttribute('data-evidence-id');await link.click();await expect(page.getByTestId('evidence-drawer').getByText(evidenceId!,{exact:true})).toBeVisible();});
   await captureOverlay('operations-drawer','Operations timeline',async()=>{await page.getByRole('button',{name:'Open operations',exact:true}).click();await expect(page.getByTestId('operation-row').first()).toBeVisible();});
   await captureOverlay('shortcut-dialog','Keyboard shortcuts',async()=>{await page.getByRole('button',{name:'Keyboard shortcuts',exact:true}).click();});
  }}
  await prove(page);await expect(page.getByTestId('attempt-row')).toHaveCount(3);await capture('S11');
  await evidence('review-attempt-1','[data-testid=attempt-row]:nth-child(1) .attempt-header');
  await evidence('review-attempt-1-benchmarks','[data-testid=attempt-row]:nth-child(1) .table-frame');
  await evidence('review-attempt-2','[data-testid=attempt-row]:nth-child(2) .attempt-header');
  await evidence('review-attempt-2-benchmarks','[data-testid=attempt-row]:nth-child(2) .table-frame');
  await evidence('review-attempt-3','[data-testid=attempt-row]:nth-child(3) .attempt-header');
  await evidence('review-attempt-benchmarks','[data-testid=attempt-row]:nth-child(3) .table-frame');
  await evidence('review-attempt-benchmarks-right','[data-testid=attempt-row]:nth-child(3) .table-frame',['[data-testid=attempt-row]:nth-child(3) .table-scroll']);
  await evidence('review-replan','[data-testid=attempt-row]:nth-child(3) [data-testid=replan-diff]');
  await expect(page.getByTestId('route-playback')).toBeVisible();
  await evidence('review-playback-route','[data-testid=route-playback] .route-geometry');
  await page.getByTestId('route-playback').getByRole('button',{name:'Next sample',exact:true}).click();
  await expect(page.getByTestId('route-playback').getByText(/^Telemetry sample 2 of/)).toBeVisible();
  await evidence('review-playback-controls','[data-testid=route-playback] .actions');
  await evidence('review-playback-measurements','[data-testid=route-playback] .readout-list');
  await evidence('review-playback-samples','[data-testid=route-playback] .table-frame');
  await tab(page,'passport');await expect(page.getByTestId('manifest-digest')).toBeVisible();await capture('S12');
  await evidence('review-passport-manifest','.passport-manifest');
  await evidence('review-passport-export-controls','.export-bar');
  for(const format of ['html','json','csv']){
   const download=page.waitForEvent('download');await page.locator(`[data-testid=export-btn][data-format=${format}]`).click();
   await (await download).saveAs(`../../out/visual/review-passport.${format}`);
   await expect(page.locator(`[data-testid=export-status][data-format=${format}]`)).toHaveAttribute('data-state','ready');
   await expect(page.locator(`[data-testid=file-digest][data-format=${format}]`)).toBeVisible();
   await evidence(`review-passport-export-${format}`,`.export-row:has([data-testid=export-btn][data-format=${format}])`);
  }
  await page.emulateMedia({reducedMotion:'reduce'});const motion=await page.evaluate(()=>[...document.querySelectorAll('*')].filter(e=>{const s=getComputedStyle(e);return [...s.transitionDuration.split(','),...s.animationDuration.split(',')].some(v=>parseFloat(v)>.001)}).map(e=>e.tagName));reports.push({screen:'reduced-motion',findings:motion.map((m:string)=>({check:'C16',message:m}))});await page.emulateMedia({reducedMotion:'no-preference'});
  await page.setViewportSize({width:794,height:1123});await page.emulateMedia({media:'print'});await page.evaluate(()=>{scrollTo(0,0);for(const node of document.querySelectorAll('*')){node.scrollTop=0;node.scrollLeft=0;}});const print=await page.evaluate(()=>({mode:!!document.querySelector('[data-testid=mode-badge]'),digest:!!document.querySelector('[data-testid=manifest-digest]'),color:getComputedStyle(document.documentElement).getPropertyValue('--canvas').trim(),width:document.documentElement.scrollWidth,viewport:innerWidth,firstPage:[document.querySelector('[data-testid=passport-view] [data-testid=mode-badge]'),document.querySelector('[data-testid=passport-view] h2'),document.querySelector('[data-testid=manifest-digest]')].map(node=>{if(!node)return null;const bounds=node.getBoundingClientRect();return {top:bounds.top,bottom:bounds.bottom};})}));reports.push({screen:'print',findings:(!print.mode||!print.digest||print.width>print.viewport||print.color.toLowerCase()!=='#f4f6f9'||print.firstPage.some((bounds:{top:number;bottom:number}|null)=>!bounds||bounds.top<0||bounds.bottom>986.46))?[{check:'C17',message:JSON.stringify(print)}]:[]});await page.pdf({path:'../../out/visual/passport.pdf',format:'A4',margin:{top:'18mm',bottom:'18mm',left:'18mm',right:'18mm'}});await page.emulateMedia({media:'screen'});
  await page.goto('/__styleguide');await expect(page.locator('main h1')).toHaveText('Component styleguide');await auditGlyphs(page);await auditStyleguide(page);
  const text=await page.locator('main').innerText();reports.push({screen:'styleguide',findings:COMPONENTS.filter((name:string)=>!text.includes(name)).map((name:string)=>({check:'C18',message:'Missing '+name}))});await capture('styleguide');
  for(const theme of ['dark','light'])for(const density of ['compact','default','comfortable']){await page.goto(`/__styleguide?captureTheme=${theme}&captureDensity=${density}`);await expect(page.locator('main h1')).toHaveText('Component styleguide');await page.evaluate(({theme,density})=>{document.documentElement.dataset.theme=theme;document.documentElement.dataset.density=density;},{theme,density});await page.setViewportSize({width:1440,height:900});await page.evaluate(()=>document.fonts.ready);await captureStyleguide(page,{theme,density});}
  // Hold the real mission request: the screenshot records an actual pending query.
  await page.addInitScript(()=>{
   if(!new URLSearchParams(location.search).has('holdMissions'))return;
   const original=window.fetch.bind(window);let release:()=>void=()=>undefined;
   const pending=new Promise<void>(resolve=>{release=resolve;});
   (window as unknown as {__releaseAuditMissions:()=>void}).__releaseAuditMissions=release;
   window.fetch=async(input,init)=>{const url=new URL(input instanceof Request?input.url:String(input),location.href);if(url.pathname==='/api/v1/missions'&&(init?.method??(input instanceof Request?input.method:'GET')).toUpperCase()==='GET')await pending;return original(input,init);};
  });
  for(const width of [1440,390])for(const theme of ['dark','light']){
   const height=width===390?844:900;await page.setViewportSize({width,height});
   await page.goto('/?holdMissions=1&mockLatency=300');await expect(page.locator('main h1')).toHaveText('Missions and runs');
   await expect(page.getByRole('status',{name:'Retrieving saved missions'})).toBeVisible();
   await auditPage(page,'loading-missions',{width,height,theme,density:'default',focus:true});
   await page.evaluate(()=>(window as unknown as {__releaseAuditMissions:()=>void}).__releaseAuditMissions());
   await expect(page.getByRole('status',{name:'Retrieving saved missions'})).toBeHidden();
   await page.goto('/rovers');await expect(page.locator('main h1')).toHaveText('Rover library');
   await page.getByTestId('file-rover-import').setInputFiles({name:'invalid-rover.json',mimeType:'application/json',buffer:Buffer.from('{')});
   await expect(page.locator('[data-testid=error-panel][data-error-code=VALIDATION_ERROR]')).toBeVisible();
   await auditPage(page,'error-rover-import',{width,height,theme,density:'default',focus:true,anchor:'[data-testid=error-panel]'});
   const invalid=JSON.parse(readFileSync(fixture('rovers/ares-1.json'),'utf8'));invalid.mass_kg=-3;
   await page.getByTestId('file-rover-import').setInputFiles({name:'invalid-mass-rover.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(invalid))});
   await expect(page.locator('[data-testid=rover-field-error][data-field=mass_kg]')).toBeVisible();
   await auditPage(page,'review-rover-validation-error',{width,height,theme,density:'default',focus:false,anchor:'[data-testid=rover-field-error][data-field=mass_kg]'});
   await page.getByTestId('file-rover-import').setInputFiles(fixture('rovers/ares-1.json'));
   await expect(page.getByTestId('rover-import-preview')).toBeVisible();
   await auditPage(page,'review-rover-import-valid',{width,height,theme,density:'default',focus:false,anchor:'[data-testid=rover-import-preview]'});
   await auditPage(page,'review-rover-import-valid-final-rows',{width,height,theme,density:'default',focus:false,anchor:'[data-testid=rover-import-preview] tbody tr:last-child'});
  }
  // J05 and J10 visual states retain the same accepted run while exposing a conflicting rover and a new draft.
  const conflictRun=await startRun(page,{rover:'practice-lite'});await tab(page,'analogs');
  const conflictCandidate=page.getByTestId('candidate-row').first();await conflictCandidate.getByTestId('btn-select-candidate').click();await expect(conflictCandidate).toHaveAttribute('data-selected','true');
  await tab(page,'compatibility');await expect(page.locator('[data-testid=compat-row][data-metric-id=max_surface_slope_deg]')).toHaveAttribute('data-status','FAIL');await capture('S08-rover-conflict');
  const pinned=await api<{mission_revision_id:string;rover_revision_id:string}>(page,`/runs/${conflictRun}`);
  const frozen=await api<{mission_id:string;objective:string}>(page,`/mission-revisions/${pinned.body.mission_revision_id}`);
  await page.goto(`/missions/${frozen.body.mission_id}/edit`);await expect(page.getByTestId('input-objective')).toHaveValue(frozen.body.objective);
  await page.getByTestId('input-objective').fill('New draft objective, requiring a separately accepted contract.');await expect(page.locator('[data-testid=save-indicator][data-save-state=saved]')).toBeVisible();await capture('S04-edited-draft');
  const unchanged=await api<typeof pinned.body>(page,`/runs/${conflictRun}`);expect(unchanged.body.mission_revision_id).toBe(pinned.body.mission_revision_id);expect(unchanged.body.rover_revision_id).toBe(pinned.body.rover_revision_id);
 }catch(error){crawlError=error;console.log('audit crawl error',error instanceof Error?error.stack:String(error));}finally{
  reports.push({screen:'crawl',findings:crawlError?[{check:'C12',message:String(crawlError)}]:[]});
  await page.waitForTimeout(60);reports.push({screen:'intentional-cancellations',findings:[],observed:auditCancellations(page)});
  reports.push({screen:'transport',findings:auditFailures(page)});
  reports.push({screen:'console-network',findings:[...faults.map(message=>({check:'C12',message})),...external.map(message=>({check:'C01',message}))]});
  const findings=finishAudit();expect(findings.length,JSON.stringify(findings.slice(0,12))).toBe(0);
 }
});
