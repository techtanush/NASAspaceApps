import { expect, test } from '@playwright/test';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { canonicalize } from 'json-canonicalize';
import { startRun, tab, prove, api, inspectHooks, isMock } from '../support/workbench';
const sha = (data: string | Buffer) => createHash('sha256').update(data).digest('hex');
test('J01 full Mars investigation, immutable fail/replan/pass and independently verified exports', async ({ page }) => {
 const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
 const external: string[] = []; page.on('request', r => { if (/^https?:/.test(r.url()) && !['localhost','127.0.0.1'].includes(new URL(r.url()).hostname)) external.push(r.url()); });
 const runId = await startRun(page);
 await expect(page.getByTestId('mode-badge')).toHaveAttribute('data-mode','synthetic');
 const pinnedRun=await api<{rover_revision_id:string}>(page,`/runs/${runId}`);const pinnedRover=await api<{name:string;revision:number}>(page,`/rover-revisions/${pinnedRun.body.rover_revision_id}`);await expect(page.getByTestId('run-state-banner')).toContainText(`Rover ${pinnedRover.body.name} rev ${pinnedRover.body.revision}`);
 await tab(page,'target');
 await expect(page.locator('[data-testid=planetary-panel][data-body=MARS]')).toBeVisible();
 await expect(page.getByTestId('earth-map')).toHaveCount(0);
 await tab(page,'analogs');
 await expect(page.getByTestId('candidate-row')).toHaveCount(6);
 await expect(page.locator('[data-testid=candidate-row][data-origin=KNOWN_CONTROL]')).toHaveCount(1);
 await page.locator('summary').filter({hasText:'Excluded and not detailed'}).click();
 await expect(page.locator('[data-testid=excluded-window][data-reason=WATER_ONLY]')).toBeVisible();
 await expect(page.locator('[data-testid=excluded-window][data-reason=INSUFFICIENT_VALID_DATA]')).toBeVisible();
 await expect(page.getByTestId('earth-map')).toBeVisible();
 await expect(page.getByTestId('candidate-list')).toBeVisible();
 let mapSelections=0;const countMapSelection=(request:import('@playwright/test').Request)=>{if(request.method()==='POST'&&request.url().endsWith('/actions')&&request.postDataJSON()?.action_type==='SELECT_CANDIDATE')mapSelections++;};page.on('request',countMapSelection);await page.getByRole('button',{name:/^Select C1:/}).click();await expect(page.getByTestId('candidate-row').first()).toHaveAttribute('data-selected','true');expect(mapSelections).toBe(1);page.off('request',countMapSelection);
 await tab(page,'qualification');
 const cell=(id:string)=>page.locator(`[data-testid=qual-cell][data-requirement-id="${id}"][data-candidate-name="Practice grid-r0c1"]`);
 await expect(cell('R-SLOPE-AVAILABILITY')).toHaveAttribute('data-status','PASS');
 await expect(cell('R-EXPOSURE')).toHaveAttribute('data-status','UNKNOWN');
 await expect(cell('R-EXPOSURE')).toHaveAttribute('data-stage','PRELIMINARY');
 await expect(cell('R-CLEARANCE')).toHaveAttribute('data-status','UNKNOWN');
 await expect(cell('R-GRAVITY')).toHaveAttribute('data-status','GAP');
 await expect(page.locator('[data-testid=critic-card][data-severity=BLOCKING][data-status=RESOLVED]')).toBeVisible();
 await expect(page.locator('[data-testid=qual-history][data-requirement-id=R-TARGET-SLOPE-CONTEXT]').first()).toContainText(/Previous.*Current/);
 await cell('R-SLOPE-AVAILABILITY').locator('summary').click(); await cell('R-SLOPE-AVAILABILITY').getByTestId('evidence-link').first().click(); await expect(page.getByTestId('evidence-drawer')).toBeVisible(); await inspectHooks(page); await page.keyboard.press('Escape');
 await page.locator('[data-testid=btn-select-candidate][data-candidate-name="Practice grid-r0c1"]').click();
 await tab(page,'compatibility');
 await expect(page.getByTestId('compat-table')).toHaveAttribute('data-preliminary','true');
 await expect(page.locator('[data-testid=compat-row][data-metric-id=ground_clearance_m]')).toHaveAttribute('data-status','UNKNOWN');await inspectHooks(page);
 await page.keyboard.press('o');await expect(page.getByTestId('operations-timeline')).toBeVisible();await inspectHooks(page);
 const seq=await page.getByTestId('operation-row').evaluateAll(es=>es.map(e=>Number(e.getAttribute('data-seq'))));
 expect(seq.length).toBeGreaterThan(0);expect(new Set(seq).size).toBe(seq.length);expect(seq).toEqual([...seq].sort((a,b)=>a-b));
 await page.keyboard.press('Escape');
 await prove(page);
 const attempts=page.getByTestId('attempt-row'); await expect(attempts).toHaveCount(3);
 for (const [n,outcome] of [[1,'FAIL'],[2,'FAIL'],[3,'PASS']] as const) await expect(page.locator(`[data-testid=attempt-row][data-attempt-number="${n}"]`)).toHaveAttribute('data-outcome',outcome);
 await expect(page.locator('[data-testid=attempt-row][data-attempt-number="1"]').getByTestId('failure-category')).toHaveAttribute('data-category','ROUTE');
 await expect(page.locator('[data-testid=attempt-row][data-attempt-number="2"]').getByTestId('failure-category')).toHaveAttribute('data-category','ANALOG');
 await expect(page.locator('[data-testid=attempt-row][data-attempt-number="3"]')).toHaveAttribute('data-candidate-name','Practice grid-r0c0');
 await expect(page.getByTestId('replan-diff').first()).toContainText(/EXPOSURE_COVERAGE/);
 await expect(page.getByTestId('route-playback')).toBeVisible();
 await tab(page,'passport');
 await expect(page.getByTestId('passport-view')).toHaveAttribute('data-draft','false');
 await expect(page.getByTestId('attempt-row')).toHaveCount(3);
 await expect(page.getByTestId('assurance-badge')).toHaveAttribute('data-publication','LIMITED');
 const manifest=(await page.getByTestId('manifest-digest').textContent())!.trim(); expect(manifest).toMatch(/^[a-f0-9]{64}$/);
 for (const format of ['html','json','csv']) {
  const downloadPromise=page.waitForEvent('download'); await page.locator(`[data-testid=export-btn][data-format=${format}]`).click();
  await expect(page.locator(`[data-testid=export-status][data-format=${format}]`)).toHaveAttribute('data-state','ready');
  const download=await downloadPromise; const path=await download.path(); expect(path).not.toBeNull(); const bytes=await readFile(path!);
  const displayed=(await page.locator(`[data-testid=file-digest][data-format=${format}]`).textContent())!.trim(); expect(sha(bytes)).toBe(displayed);await inspectHooks(page);
  expect(displayed).not.toBe(manifest);
  if(format==='json') { const doc=JSON.parse(bytes.toString()); expect(sha(canonicalize(doc.canonical_manifest))).toBe(manifest); expect(doc.bundle.attempts).toHaveLength(3); }
  if(format==='html') { const html=bytes.toString(); expect(html).toContain(manifest); expect(html).toContain('synthetic'); expect(html).not.toMatch(/<script\b|(?:src|href)=["']https?:/i); for(const id of ['R-GRAVITY','R-ATMOSPHERE','R-CLEARANCE']) expect(html).toContain(id); }
  if(format==='csv') { const kit=await readFile(new URL('../../../src/analogforge/ports/passport_renderer.py',import.meta.url),'utf8'); const columns=[...kit.match(/CSV_COLUMNS:[\s\S]*?= \(([\s\S]*?)\n\)/)![1].matchAll(/"([^"]+)"/g)].map(m=>m[1]); expect(bytes.toString().split('\n')[0]).toBe(columns.join(',')); }
 }
 await page.reload(); await expect(page.getByTestId('passport-view')).toHaveAttribute('data-draft','false'); await expect(page.getByTestId('attempt-row')).toHaveCount(3);
 await inspectHooks(page); const snapshot=await api<{state:string;passport_id:string;last_event_seq:number}>(page,`/runs/${runId}`); expect(snapshot.status).toBe(200); expect(snapshot.body.state).toBe('COMPLETED');
 if(!isMock()) { const results=await api<{items: {id:string;evidence_ids:string[]}[]}>(page,`/tests?run_id=${runId}`); expect(results.body.items.length).toBe(3); for(const result of results.body.items) expect(result.id).toBeTruthy(); }
 await page.goto('/');await expect(page.getByTestId('run-row').first()).toBeVisible();await inspectHooks(page);
 expect(errors).toEqual([]); expect(external).toEqual([]);
});
