import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';
const moonPractice = JSON.parse(readFileSync(resolve(import.meta.dirname,'../fixtures/kit/missions/mission-moon-gap.json'),'utf8'));
test('slow optional fonts cannot hold the authenticated workspace blank',async({page})=>{
 let release!:()=>void;
 const held=new Promise<void>(resolve=>{release=resolve;});
 await page.route(/\.woff2?(?:\?|$)/,async route=>{await held;await route.continue();});
 try {
  await page.goto('/',{waitUntil:'domcontentloaded'});
  await expect(page.getByTestId('btn-begin')).toBeVisible();
  await page.getByTestId('btn-begin').click();
  await expect(page.getByRole('button',{name:'Moon',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Mars',exact:true})).toBeVisible();
 } finally {release();await page.unrouteAll({behavior:'wait'});}
});
async function launch(page: import('@playwright/test').Page, siteOnly=false, moon=false, options:{unsupported?:boolean;practice?:boolean}={}) {
 await page.goto('/');
 await page.getByTestId('btn-begin').click();
 if(moon){await page.getByRole('button',{name:'Moon',exact:true}).click();await page.getByRole('button',{name:'Mare Tranquillitatis Apollo 11 landing region'}).click();}
 else await page.getByRole('button',{name:'Gale Crater Curiosity landing region'}).click();
 if(options.practice){await page.getByText('Practice datasets (synthetic)',{exact:true}).click();await page.getByTestId('btn-use-practice-target').click();}
 await page.getByTestId('btn-confirm-place').click();
 await page.getByRole('button',{name:'Slope traverse',exact:true}).click();
 await page.getByTestId('btn-mission-continue').click();
 let roverRevisionId: string | null = null;
 if(siteOnly) await page.getByTestId('rover-none').click();
 else {
  const saved = page.waitForResponse(response => response.request().method()==='POST' && new URL(response.url()).pathname==='/api/v1/rovers');
  await page.getByTestId('mc-rover-import').setInputFiles(resolve(import.meta.dirname,'../fixtures/kit/rovers/ares-1.json'));
  const response = await saved;
  expect(response.status()).toBe(201);
  const rover = await response.json() as {id:string;name:string};
  expect(rover.id).toMatch(/^[0-9a-f-]{36}$/i);
  roverRevisionId = rover.id;
  const selected = page.locator('[data-testid="rover-option"][aria-pressed="true"]');
  await expect(selected).toHaveCount(1);
  await expect(selected).toContainText(rover.name);
 }
 await expect(page.getByTestId('btn-rover-continue')).toBeEnabled();
 await page.getByTestId('btn-rover-continue').click();
 await expect(page.getByLabel('Source mode')).toHaveValue('synthetic');
 const preparation = page.waitForRequest(request => request.method()==='POST' && /^\/api\/v1\/missions\/[^/]+\/fingerprint$/.test(new URL(request.url()).pathname));
 const mission = page.waitForRequest(request => request.method()==='POST' && new URL(request.url()).pathname==='/api/v1/missions');
 await page.getByTestId('btn-prepare').click();
 if(options.practice) expect((await mission).postDataJSON().target).toEqual(moonPractice.target);
 else await mission;
 expect((await preparation).postDataJSON().rover_revision_id).toBe(roverRevisionId);
 await expect(page.getByTestId('proposed-requirements')).toBeVisible({timeout:process.env.E2E_TARGET==='mock'?15000:120000});
 await page.getByText('Assumptions and test conditions',{exact:true}).click();
 await expect(page.getByRole('region',{name:'Contract assumptions and limits',exact:true})).toBeVisible();
 await page.getByText('Assumptions and test conditions',{exact:true}).click();
 const creation = page.waitForResponse(response => response.request().method()==='POST' && new URL(response.url()).pathname==='/api/v1/runs');
 await page.getByTestId('btn-accept-start').click();
 const created = await creation;
 expect(created.status()).toBe(202);
 expect(created.request().postDataJSON().rover_revision_id).toBe(roverRevisionId);
 const {run_id:runId} = await created.json() as {run_id:string};
 let runState = '';
 let blockedDependencies: string[] = [];
 let missionRevisionId = '';
 await expect.poll(async()=>{
  const response = await page.evaluate(async id=>{const response=await fetch(`/api/v1/runs/${id}`);return {status:response.status,body:await response.json() as {state:string;blocked_dependencies:string[];mission_revision_id:string}};},runId);
  expect(response.status).toBe(200);
  runState = response.body.state;
  blockedDependencies = response.body.blocked_dependencies;
  missionRevisionId = response.body.mission_revision_id;
  return ['AWAITING_REVIEW','COMPLETED','BLOCKED','FAILED','CANCELLED'].includes(runState);
 },{timeout:process.env.E2E_TARGET==='mock'?10000:180000,message:`Run ${runId} must reach its backend review or terminal boundary`}).toBe(true);
 if(options.unsupported){expect(runState).toBe('BLOCKED');expect(blockedDependencies).toContain('NO_COVERAGE');return runId;}
 expect(runState,`Run ${runId} must have reviewable results`).toMatch(/^(AWAITING_REVIEW|COMPLETED)$/);
 if(options.practice){
  expect(created.request().postDataJSON().mission_revision_id).toBe(missionRevisionId);
  const contract = await page.evaluate(async id=>{const response=await fetch(`/api/v1/mission-revisions/${id}`);return {status:response.status,body:await response.json()};},missionRevisionId);
  expect(contract.status).toBe(200);expect(contract.body.target).toEqual(moonPractice.target);expect(contract.body.accepted_at).not.toBeNull();
 }
 await expect(page.getByRole('heading',{name:'Your Earth test locations'})).toBeVisible();
 await expect(page.getByRole('region',{name:'All-location rehearsal plan'})).toBeVisible();
 await page.getByRole('button',{name:'Inspect location 1',exact:true}).click();
 await expect(page.getByTestId('site-card')).toBeVisible();
 return runId;
}
test('globe, exact-site inspection, stable selection and printable report',async({page})=>{
 // Production imagery requires an explicit click. Block its exact public source only
 // after checking the offline default; no local API response is replaced.
 const satellite=/^https:\/\/(?:basemap\.nationalmap\.gov\/arcgis\/rest\/services\/USGSImageryOnly\/MapServer\/tile\/\d+\/\d+\/\d+|tiles\.maps\.eox\.at\/wmts\/1\.0\.0\/s2cloudless_3857\/default\/GoogleMapsCompatible\/\d+\/\d+\/\d+\.jpg)$/;
 const blockedSatellite:string[]=[];await page.context().route(satellite,route=>{blockedSatellite.push(route.request().url());return route.abort('blockedbyclient');});
 const external:string[]=[];page.context().on('request',request=>{const url=new URL(request.url());if(url.protocol.startsWith('http')&&url.origin!==new URL(process.env.E2E_BASE_URL||'http://127.0.0.1:5176').origin&&!satellite.test(url.href))external.push(url.origin);});
 const runId=await launch(page);
 expect(blockedSatellite).toEqual([]);
 if(process.env.E2E_TARGET==='real'){await page.getByRole('button',{name:'Load satellite imagery',exact:true}).click();await expect(page.getByText(/Satellite imagery unavailable\. Measured terrain/)).toBeVisible();expect(blockedSatellite.length).toBeGreaterThan(0);}
 await expect(page.getByTestId('globe-stage')).toHaveAttribute('data-state','ready');
 const first=new URL(page.url()).searchParams.get('site');
 // This practice fixture places all candidates nearby. The globe must not stack
 // their labels or combine their individual qualification results.
 await page.getByTestId('btn-all-sites').click();
 await expect(page.getByRole('heading',{name:'Your Earth test locations'})).toBeVisible();
 const locationCount=await page.getByRole('button',{name:/^Inspect location \d+$/}).count();
 expect(locationCount).toBeGreaterThan(0);
 const nearby=page.locator('.mc-ticker[data-group="true"]');
 await expect(nearby).toHaveCount(1);
 await expect(nearby).toHaveAttribute('data-member-count',String(locationCount));
 await expect(nearby).toHaveAttribute('data-status','UNKNOWN');
 await expect(nearby).toContainText('nearby sites');
 await nearby.click();
 await expect(page.getByTestId('regional-inspector')).toBeVisible();
 expect(new URL(page.url()).searchParams.get('site')).toBe(first);
 await page.getByRole('button',{name:'Inspect location',exact:true}).click();
 await expect(page.getByTestId('regional-inspector')).toBeVisible();
 await page.locator('[data-testid="tour"] .mc-panel-body').evaluate(body=>{body.scrollTop=body.scrollHeight;});
 await page.getByTestId('btn-next-site').click();
 await expect.poll(()=>new URL(page.url()).searchParams.get('site')).not.toBe(first);
 await expect(page.getByTestId('site-selection-announcement')).toContainText('Site 2 of');
 await expect(page.locator('.map-selection-readout')).toContainText('Selected: Site 2');
 await expect.poll(()=>page.getByTestId('site-card').evaluate(card=>card.getBoundingClientRect().top-card.closest('.mc-panel-body')!.getBoundingClientRect().top)).toBeGreaterThanOrEqual(-1);
 await expect.poll(()=>page.getByTestId('site-card').evaluate(card=>card.getBoundingClientRect().top-card.closest('.mc-panel-body')!.getBoundingClientRect().bottom)).toBeLessThan(0);
 await expect(page.getByTestId('regional-inspector')).toContainText('Earth site');
 await expect(page.getByTestId('site-card')).not.toContainText('null ');
 await page.screenshot({path:'../../out/mission-control-regional.png'});
 const href=await page.getByTestId('link-report').getAttribute('href');
 await page.goto(href!);
 await expect(page.getByTestId('site-report')).toBeVisible();
 await expect(page.getByTestId('site-report')).toContainText('current evidence brief');
 await expect(page.getByRole('heading',{name:'Benchmarks and measured results',exact:true})).toBeVisible();
 if(process.env.E2E_TARGET==='real'){
  const candidateId=new URL(page.url()).searchParams.get('site')!;
  const runId=new URL(page.url()).pathname.split('/')[2]!;
  const downloading=page.waitForEvent('download',{timeout:15000});
  await page.getByRole('button',{name:'Download current evidence PDF',exact:true}).click();
  const downloaded=await downloading;
  expect(downloaded.suggestedFilename()).toBe(`analogforge-evidence-brief-${runId.slice(0,8)}-${candidateId.slice(0,8)}.pdf`);
  expect(readFileSync((await downloaded.path())!).subarray(0,5).toString()).toBe('%PDF-');
 }
 await page.emulateMedia({media:'print'});
 await expect(page.getByRole('navigation',{name:'Report actions'})).toBeHidden();
 await page.pdf({path:'../../out/mission-control-report.pdf',format:'A4'});
 expect(external).toEqual([]);
 await page.emulateMedia({media:'screen'});
 await page.goto('/');
 await expect(page.getByTestId('recent-investigations').locator('a').first()).toHaveAttribute('href',`/runs/${runId}/tour`);
});
test('mobile, site-only, keyboard and reduced motion retain complete evidence access',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.emulateMedia({reducedMotion:'reduce'});
 await launch(page,true);
 await expect(page.getByTestId('site-card')).toContainText('No rover supplied');
 await page.getByRole('button',{name:'Inspect location',exact:true}).click();
 await expect(page.getByTestId('regional-inspector')).toBeVisible();
 for(const id of ['btn-prev-site','btn-next-site','btn-all-sites']){
  const bounds = await page.getByTestId(id).boundingBox();
  expect(bounds,`${id} must be rendered`).not.toBeNull();
  expect(bounds!.x).toBeGreaterThanOrEqual(0);expect(bounds!.y).toBeGreaterThanOrEqual(0);
  expect(bounds!.x+bounds!.width).toBeLessThanOrEqual(390);expect(bounds!.y+bounds!.height).toBeLessThanOrEqual(844);
 }
 const firstSite = new URL(page.url()).searchParams.get('site');
 await page.getByTestId('btn-next-site').click();
 await expect.poll(()=>new URL(page.url()).searchParams.get('site')).not.toBe(firstSite);
 await page.getByTestId('btn-prev-site').click();
 await expect.poll(()=>new URL(page.url()).searchParams.get('site')).toBe(firstSite);
 await page.getByTestId('btn-all-sites').click();
 await expect(page.getByRole('heading',{name:'Your Earth test locations'})).toBeVisible();
 await expect(page.getByRole('button',{name:'Inspect location 1',exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.keyboard.press('Tab');
 await expect(page.locator(':focus')).toBeVisible();
 const axe=await new AxeBuilder({page}).analyze();
 expect(axe.violations.filter(v=>v.impact==='critical'||v.impact==='serious')).toEqual([]);
 await page.screenshot({path:'../../out/mission-control-mobile.png'});
});
test('no-WebGL users retain setup and individual candidate access',async({page})=>{
 await page.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind:string,...args:unknown[]){if(kind==='webgl'||kind==='webgl2')return null;return get.apply(this,[kind,...args] as Parameters<typeof get>);} as typeof get;});
 await launch(page,true);
 await expect(page.getByTestId('globe-fallback')).toBeVisible();
 await page.getByTestId('btn-next-site').click();
 await expect(page.getByTestId('tour-position')).toHaveText('2 / 6');
});

test('Moon setup blocks unsupported coverage and its explicit practice target retains natural gaps',async({page})=>{
 if(process.env.E2E_TARGET!=='mock'){
  await launch(page,true,true,{unsupported:true});
  await expect(page.getByRole('heading',{name:'Investigation paused'})).toBeVisible();
  const notice=page.getByTestId('run-terminal-notice');
  await expect(notice).toHaveAttribute('data-state','BLOCKED');
  await expect(notice).toContainText('Source data does not cover the requested area.');
  await notice.getByText('Technical status',{exact:true}).click();
  await expect(notice).toContainText('NO_COVERAGE');
 }
 await launch(page,true,true,{practice:true});
 await page.getByRole('button',{name:'Target evidence',exact:true}).click();
 await expect(page.getByTestId('planetary-panel')).toHaveAttribute('data-body','MOON');
 await expect(page.getByTestId('site-card')).toContainText('No rover supplied');
 await expect(page.getByRole('heading',{name:'Benchmarks and measured results',exact:true})).toBeVisible();
 await expect(page.getByTestId('site-card')).toContainText('GAP');
});
