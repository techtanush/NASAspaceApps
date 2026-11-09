import { expect, test } from '@playwright/test';
import { newMission, startRun, tab, prove } from './support/workbench';
// The implementation is shared with the command-line audit and imports no application code.
// @ts-expect-error JavaScript audit module exports are checked by the runtime audit.
import {auditPage,auditGlyphs,finishAudit,THRESHOLDS,COMPONENTS,reports,installAuditInstrumentation,auditFailures,auditCancellations,waitForAuditData} from '../../scripts/ui/visual_audit.mjs';
test('UIX-13 complete visual audit C01–C20',async({page})=>{
 test.setTimeout(1800000);page.setDefaultTimeout(15000);
 page.on('request',request=>{if(request.method()==='POST')console.log('audit mutation',new URL(request.url()).pathname);});page.on('response',response=>{if(response.request().method()==='POST')console.log('audit acknowledgement',response.status(),new URL(response.url()).pathname);});
 const faults: string[]=[];const external:string[]=[];
 page.on('pageerror',e=>faults.push(e.message));page.on('console',m=>{if(['error','warning'].includes(m.type()))faults.push(m.text());});
 page.on('request',r=>{if(/^https?:/.test(r.url())&&new URL(r.url()).origin!==(process.env.E2E_BASE_URL||'http://127.0.0.1:5176'))external.push(r.url());});
 await installAuditInstrumentation(page);
 await page.clock.setFixedTime(new Date('2026-11-08T12:00:00Z'));
 const capture=async(name:string)=>{
  console.log('audit screen',name);const headings:Record<string,string>={S01:'Missions and runs',S02:'Mission authoring',S03:'Rover library',S04:'Mission authoring',S05:'Target evidence',S06:'Earth analog candidates',S07:'Qualification',S08:'Rover compatibility',S09:'Composite portfolio',S10:'Test lab',S11:'Test lab',S12:'Analog Passport',styleguide:'Component styleguide'};await expect(page.locator('main h1')).toHaveText(headings[name]!);await page.evaluate(()=>document.fonts.ready);
  await expect(page.locator('main h1')).toBeVisible();await waitForAuditData(page);
  for(const [width,height]of THRESHOLDS.viewports)for(const theme of ['dark','light']){
   const densities=['S06','S07','S10'].includes(name)?['compact','default','comfortable']:['default'];
   for(const density of densities)await auditPage(page,name,{width,height,theme,density,focus:true});
   if(['S02','S04','S07','S12'].includes(name)){
    await auditPage(page,name,{width,height,theme,density:'default',spacing:true,focus:false});
   }
  }
 };
 const captureOverlay=async(name:string,title:string,open:()=>Promise<void>)=>{
  for(const [width,height]of THRESHOLDS.viewports)for(const theme of ['dark','light']){
   await page.setViewportSize({width,height});await open();await expect(page.getByRole('dialog',{name:title,exact:true})).toBeVisible();
   await auditPage(page,name,{width,height,theme,density:'default',focus:true});
   if(await page.getByRole('dialog',{name:title,exact:true}).isVisible())await page.keyboard.press('Escape');
  }
 };
 let crawlError:unknown=null;
 try{
  await page.goto('/?mockLatency=300');await capture('S01');
  await page.getByTestId('btn-new-mission').click();await capture('S02');await captureOverlay('change-body-dialog','Change target body',async()=>{await page.locator('[data-testid=radio-body][data-body=MOON]').click();});
  await page.goto('/rovers');await capture('S03');
  await newMission(page);await capture('S04');await page.getByTestId('btn-start-run').click();await expect(page.getByTestId('run-state-banner')).toHaveAttribute('data-state','AWAITING_REVIEW');
  for(const [screen,name]of [['S05','target'],['S06','analogs'],['S07','qualification'],['S08','compatibility'],['S09','portfolio'],['S10','test-lab']]){await tab(page,name);await capture(screen);if(name==='analogs'){const candidate=page.getByTestId('candidate-row').first();await candidate.getByTestId('btn-select-candidate').click();await expect(candidate).toHaveAttribute('data-selected','true');}if(screen==='S07'){
   await captureOverlay('evidence-drawer','Evidence receipt',async()=>{const cell=page.getByTestId('qual-cell').first();const details=cell.locator('details');if(!await details.evaluate(node=>(node as HTMLDetailsElement).open))await details.locator('summary').click();const link=details.getByTestId('evidence-link').first();const evidenceId=await link.getAttribute('data-evidence-id');await link.click();await expect(page.getByTestId('evidence-drawer').getByText(evidenceId!,{exact:true})).toBeVisible();});
   await captureOverlay('operations-drawer','Operations timeline',async()=>{await page.getByRole('button',{name:'Open operations',exact:true}).click();await expect(page.getByTestId('operation-row').first()).toBeVisible();});
   await captureOverlay('shortcut-dialog','Keyboard shortcuts',async()=>{await page.getByRole('button',{name:'Keyboard shortcuts',exact:true}).click();});
  }}
  await prove(page);await expect(page.getByTestId('attempt-row')).toHaveCount(3);await capture('S11');await tab(page,'passport');await expect(page.getByTestId('manifest-digest')).toBeVisible();await capture('S12');
  await page.emulateMedia({reducedMotion:'reduce'});const motion=await page.evaluate(()=>[...document.querySelectorAll('*')].filter(e=>{const s=getComputedStyle(e);return [...s.transitionDuration.split(','),...s.animationDuration.split(',')].some(v=>parseFloat(v)>.001)}).map(e=>e.tagName));reports.push({screen:'reduced-motion',findings:motion.map((m:string)=>({check:'C16',message:m}))});await page.emulateMedia({reducedMotion:'no-preference'});
  await page.setViewportSize({width:794,height:1123});await page.emulateMedia({media:'print'});const print=await page.evaluate(()=>({mode:!!document.querySelector('[data-testid=mode-badge]'),digest:!!document.querySelector('[data-testid=manifest-digest]'),color:getComputedStyle(document.documentElement).getPropertyValue('--canvas').trim(),width:document.documentElement.scrollWidth,viewport:innerWidth,firstPage:[document.querySelector('[data-testid=passport-view] [data-testid=mode-badge]'),document.querySelector('[data-testid=passport-view] h2'),document.querySelector('[data-testid=manifest-digest]')].map(node=>{if(!node)return null;const bounds=node.getBoundingClientRect();return {top:bounds.top,bottom:bounds.bottom};})}));reports.push({screen:'print',findings:(!print.mode||!print.digest||print.width>print.viewport||print.color.toLowerCase()!=='#f4f6f9'||print.firstPage.some((bounds:{top:number;bottom:number}|null)=>!bounds||bounds.top<0||bounds.bottom>986.46))?[{check:'C17',message:JSON.stringify(print)}]:[]});await page.pdf({path:'../../out/visual/passport.pdf',format:'A4',margin:{top:'18mm',bottom:'18mm',left:'18mm',right:'18mm'}});await page.emulateMedia({media:'screen'});
  await page.goto('/__styleguide');await expect(page.locator('main h1')).toHaveText('Component styleguide');await auditGlyphs(page);
  const text=await page.locator('main').innerText();reports.push({screen:'styleguide',findings:COMPONENTS.filter((name:string)=>!text.includes(name)).map((name:string)=>({check:'C18',message:'Missing '+name}))});await capture('styleguide');
  for(const theme of ['dark','light'])for(const density of ['compact','default','comfortable']){await page.goto(`/__styleguide?captureTheme=${theme}&captureDensity=${density}`);await expect(page.locator('main h1')).toHaveText('Component styleguide');await page.evaluate(({theme,density})=>{document.documentElement.dataset.theme=theme;document.documentElement.dataset.density=density;},{theme,density});await page.setViewportSize({width:1440,height:900});await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:`docs/design-review/styleguide-${theme}-${density}.png`,fullPage:true});}
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
   await auditPage(page,'error-rover-import',{width,height,theme,density:'default',focus:true});
  }
 }catch(error){crawlError=error;}finally{
  reports.push({screen:'crawl',findings:crawlError?[{check:'C12',message:String(crawlError)}]:[]});
  await page.waitForTimeout(60);reports.push({screen:'intentional-cancellations',findings:[],observed:auditCancellations(page)});
  reports.push({screen:'transport',findings:auditFailures(page)});
  reports.push({screen:'console-network',findings:[...faults.map(message=>({check:'C12',message})),...external.map(message=>({check:'C01',message}))]});
  const findings=finishAudit();expect(findings.length,JSON.stringify(findings.slice(0,12))).toBe(0);
 }
});
