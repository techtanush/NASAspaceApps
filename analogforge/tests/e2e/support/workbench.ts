import { expect, test, type Page } from '@playwright/test';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { createRequire } from 'node:module';
export const isMock = () => process.env.E2E_TARGET === 'mock';
const root = resolve(import.meta.dirname, '../../..');
const require = createRequire(resolve(root,'apps/web/package.json'));
const Ajv2020=require('ajv/dist/2020').default;
const addFormats=require('ajv-formats').default;
const bundled=JSON.parse(readFileSync(resolve(root,'contracts/openapi.bundled.json'),'utf8'));
const requestValidator=new Ajv2020({strict:false,allErrors:true});addFormats(requestValidator);requestValidator.addSchema(bundled,'contract');
const requestErrors=new WeakMap<Page,string[]>();
test.beforeEach(async({page})=>{
 const errors:string[]=[];requestErrors.set(page,errors);
 page.on('request',request=>{
  const url=new URL(request.url());if(!url.pathname.startsWith('/api/v1/')||!['POST','PATCH','PUT','DELETE'].includes(request.method())||request.headers()['x-analogforge-negative-probe'])return;
  const path=url.pathname.slice('/api/v1'.length);const template=Object.keys(bundled.paths).find(candidate=>new RegExp('^'+candidate.replace(/\{[^}]+\}/g,'[^/]+')+'$').test(path));
  if(!template){errors.push(`${request.method()} ${path}: operation is outside frozen API`);return;}
  const method=request.method().toLowerCase();const operation=bundled.paths[template][method];
  if(!operation){errors.push(`${request.method()} ${template}: unsupported method`);return;}
  const schema=operation.requestBody?.content?.['application/json']?.schema;if(!schema)return;
  const pointer=template.replace(/~/g,'~0').replace(/\//g,'~1');
  const validate=requestValidator.compile({$ref:`contract#/paths/${pointer}/${method}/requestBody/content/application~1json/schema`});
  let body:unknown;try{body=request.postDataJSON();}catch{errors.push(`${request.method()} ${template}: invalid JSON`);return;}
  if(!validate(body))errors.push(`${request.method()} ${template}: ${JSON.stringify(validate.errors)}`);
  if(!/^[0-9a-f-]{36}$/i.test(request.headers()['idempotency-key']||''))errors.push(`${request.method()} ${template}: missing stable UUID key`);
 });
});
test.afterEach(async({page})=>{expect(requestErrors.get(page)||[],'UI mutations must satisfy frozen OpenAPI request schemas').toEqual([]);});
export const fixture = (name: string) => resolve(root, 'tests/fixtures/kit', name);
export const contract = JSON.parse(readFileSync(resolve(root, 'contracts/ui-testids.json'), 'utf8')) as { testids: { id: string; required_attributes: string[] }[] };
const renderedTruth=new Map<string,string>();
const observedHooks=new Set<string>();
const observedStatuses=new Map<string,{status:string;label:string;glyph:string;html:string}>();
export async function inspectHooks(page: Page) {
 for (const hook of contract.testids) {
  const elements = page.getByTestId(hook.id);
  for (const el of await elements.all()) {
   const inClosedDisclosure=await el.evaluate(node=>{for(let parent=node.parentElement;parent;parent=parent.parentElement)if(parent.tagName==='DETAILS'&&!parent.hasAttribute('open')&&!parent.querySelector(':scope > summary')?.contains(node))return true;return false;});
   if(inClosedDisclosure)continue;
   await expect(el,`${hook.id} must remain visible`).toBeVisible();
   observedHooks.add(hook.id);
   for (const attr of hook.required_attributes) await expect(el, `${hook.id} requires ${attr}`).toHaveAttribute(attr, /.+/);
  }
 }
 const badges=await page.locator('[data-status]').evaluateAll(elements=>elements.filter(el=>el.querySelector('svg')&&el.getBoundingClientRect().width>0).map(el=>({status:el.getAttribute('data-status')!,label:el.textContent!.trim(),glyph:el.querySelector('svg')!.outerHTML,html:el.outerHTML})));
 for(const badge of badges)if(!observedStatuses.has(badge.status))observedStatuses.set(badge.status,badge);
 mkdirSync(resolve(root,'out'),{recursive:true});
 renderedTruth.set(page.url(),await page.locator('main').innerText());
 writeFileSync(resolve(root,`out/truth-rendered-${process.env.E2E_RUN_NAME||'default'}-${process.env.TEST_WORKER_INDEX||'0'}.json`),JSON.stringify([...renderedTruth].map(([url,text])=>({url,text})),null,2));
 writeFileSync(resolve(root,`out/truth-statuses-${process.env.E2E_RUN_NAME||'default'}-${process.env.TEST_WORKER_INDEX||'0'}.json`),JSON.stringify([...observedStatuses.values()],null,2));
 writeFileSync(resolve(root,`out/hooks-${process.env.E2E_RUN_NAME||'default'}-${process.env.TEST_WORKER_INDEX||'0'}.json`),JSON.stringify([...observedHooks].sort(),null,2));
}
export async function choose(page: Page, id: string, value: string) {
 const el = page.getByTestId(id);
 if (await el.evaluate(n => n.tagName === 'SELECT')) await el.selectOption(value);
 else {
  await el.click();
  const option = page.getByRole('option').filter({ hasText: value });
  if (await option.count() === 1) await option.click();
  else await page.locator(`[role=option][data-value="${value}"]`).click();
 }
}
export async function api<T = Record<string, unknown>>(page: Page, path: string, init: { method?: string; body?: unknown } = {}): Promise<{ status: number; body: T }> {
 return page.evaluate(async ({ path, init }) => {
  let csrf: string|undefined;
  if(init.method&&init.method!=='GET'){const auth=await fetch('/auth/session',{credentials:'same-origin'});if(auth.ok){const session=await auth.json();csrf=session.csrf_token??session.csrfToken;}}
  const response = await fetch(`/api/v1${path}`, { method: init.method || 'GET', headers: { 'Content-Type': 'application/json', ...(csrf?{'X-CSRF-Token':csrf}:{}), 'Idempotency-Key': crypto.randomUUID(), ...(init.method && !['GET','POST'].includes(init.method) ? {'X-AnalogForge-Negative-Probe':'1'} : {}) }, body: init.body === undefined ? undefined : JSON.stringify(init.body) });
  return { status: response.status, body: await response.json() };
 }, { path, init });
}
export async function newMission(page: Page, options: { moon?: boolean; rover?: string | null; scenario?: string; mode?: string; preview?: string } = {}) {
 page.on('pageerror',error=>console.error('Browser error:',error.message));
 await page.goto(options.preview ? `/?mockScenario=${encodeURIComponent(options.preview)}` : '/');
 await expect(page.getByTestId('app-shell')).toBeVisible();
 await expect(page.getByTestId('btn-new-mission')).toBeVisible();
 await inspectHooks(page);
 if (isMock()) await expect(page.getByTestId('mock-banner')).toContainText('MOCK PREVIEW');
 else expect(await page.evaluate(() => (window as unknown as {__MSW__?: boolean}).__MSW__)).toBeUndefined();
 await page.getByTestId('btn-new-mission').click();
 await page.getByTestId('input-mission-name').fill(options.moon ? 'Polar thermal investigation' : 'Mobility exposure investigation');
 await page.locator(`[data-testid=radio-body][data-body=${options.moon ? 'MOON' : 'MARS'}]`).click();
 const dialog = page.getByRole('dialog');
 if (await dialog.isVisible()) await dialog.getByRole('button', { name: /confirm|change body/i }).click();
 await page.getByTestId('input-objective').fill(options.moon ? 'Evaluate lunar polar thermal and terrain analogs.' : 'Test geological sampling mobility with 100 m unique exposure on 12–18 degree slopes and return with reserve.');
 await choose(page, 'select-target-preset', options.moon ? 'Moon' : 'Mars');
 await expect(page.locator('[data-testid=save-indicator][data-save-state=saved]')).toBeVisible();
 if (options.rover === null) await page.getByTestId('btn-continue-no-rover').click();
 else {
  await page.getByTestId('file-rover-import').setInputFiles(fixture(`rovers/${options.rover || 'ares-1'}.json`));
  await expect(page.getByTestId('rover-import-preview')).toBeVisible();
  await page.getByTestId('btn-rover-save').click();
  await expect(page.getByRole('status').filter({hasText:/Saved revision/})).toBeVisible();
 }
 await expect(page.getByTestId('btn-build-fingerprint')).toBeEnabled();
 await page.getByTestId('btn-build-fingerprint').click();
 await expect(page.locator('[data-testid=preparation-status][data-job-state=SUCCEEDED]')).toBeVisible({ timeout: 60000 });
 await inspectHooks(page);
 await choose(page, 'select-scenario', options.scenario || (options.moon ? 'synthetic-moon-gap-v1' : 'synthetic-mars-mobility-v1'));
 await choose(page, 'select-mode', options.mode || 'synthetic');
 await expect(page.getByTestId('btn-accept-contract')).toBeEnabled();
 await page.getByTestId('btn-accept-contract').click();
}
export async function startRun(page: Page, options: Parameters<typeof newMission>[1] = {}) {
 await newMission(page, options);
 await expect(page.getByTestId('btn-start-run')).toBeEnabled();
 await page.getByTestId('btn-start-run').click();
 await expect(page.getByTestId('run-state-banner')).toBeVisible();
 await expect(page.getByTestId('run-state-banner')).toHaveAttribute('data-state', options.moon ? /COMPLETED|AWAITING_REVIEW/ : 'AWAITING_REVIEW', { timeout: isMock() ? 10000 : 180000 });
 await inspectHooks(page);
 return page.url().match(/\/runs\/([^/?]+)/)![1];
}
export async function tab(page: Page, name: string) {
 await page.locator(`[data-testid=run-nav-tab][data-tab="${name}"]`).click();
 await inspectHooks(page);
}
export async function prove(page: Page, candidate = 'Practice grid-r0c1') {
 await tab(page, 'analogs');
 if(await page.locator(`[data-testid=candidate-row][data-candidate-name="${candidate}"]`).getAttribute('data-selected')!=='true') await page.locator(`[data-testid=btn-select-candidate][data-candidate-name="${candidate}"]`).click();
 await expect(page.locator(`[data-testid=candidate-row][data-candidate-name="${candidate}"]`)).toHaveAttribute('data-selected', 'true');
 await tab(page, 'test-lab');
 await expect(page.getByTestId('benchmark-preview')).toBeVisible();
 await expect(page.getByTestId('attempt-row')).toHaveCount(0);
 await expect(page.getByTestId('route-playback')).toHaveCount(0);
 await expect(page.getByTestId('btn-prove-it')).toHaveAttribute('data-enabled', 'true');
 await page.getByTestId('btn-prove-it').click();
 await expect(page.getByTestId('run-state-banner')).toHaveAttribute('data-state', 'COMPLETED', { timeout: isMock() ? 15000 : 240000 });
 await inspectHooks(page);
}
