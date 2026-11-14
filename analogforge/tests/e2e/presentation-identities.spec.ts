import {test,expect} from '@playwright/test';
import {api,newMission,tab} from './support/workbench';
test('authoring groups stay bounded and pinned contract identity remains inspectable',async({page})=>{
 test.setTimeout(180000);await newMission(page);
 for(const width of [1440,1024,390]){
  await page.setViewportSize({width,height:900});
  const geometry=await page.locator('.author-grid').evaluate(node=>{const form=node.querySelector('.mission-identity')!.getBoundingClientRect(),target=node.querySelector('.planetary-container')!.getBoundingClientRect();return {available:node.getBoundingClientRect().width,form:{left:form.left,right:form.right,top:form.top,bottom:form.bottom,width:form.width},target:{left:target.left,top:target.top}};});
  expect(geometry.form.width).toBeLessThanOrEqual(480);expect(geometry.form.width).toBeLessThanOrEqual(geometry.available);
  if(geometry.available>=824)expect(geometry.target.left).toBeGreaterThanOrEqual(geometry.form.right+23);else expect(geometry.target.top).toBeGreaterThanOrEqual(geometry.form.bottom);
 }
 const editor=page.getByRole('textbox',{name:'Energy model JSON'});await expect(editor).toHaveCSS('font-family',/mono/i);await expect(editor).toHaveCSS('white-space','pre-wrap');await expect(editor).toHaveValue(/^\{\n {2}"model_id"/);
 await page.setViewportSize({width:1440,height:900});await page.getByTestId('btn-start-run').click();await expect(page.getByTestId('run-state-banner')).toHaveAttribute('data-state','AWAITING_REVIEW');
 await expect(page.locator('[data-planetary-ground-scale]')).toBeVisible();expect(Number(await page.locator('[data-planetary-ground-scale]').getAttribute('data-distance-m'))).toBeGreaterThan(0);await expect(page.getByLabel('Ground-distance scale',{exact:true})).toContainText('Approximate reference-sphere scale');
 await page.locator('[data-testid=planetary-panel] svg').focus();await page.keyboard.press('Enter');await expect(page.locator('[data-testid=planetary-panel] .coordinate-readout')).toContainText('display CRS coordinates (native units)');
 const runId=page.url().match(/\/runs\/([^/?]+)/)![1];const run=await api<{mission_revision_id:string}>(page,`/runs/${runId}`);const contract=await api<{content_sha256:string}>(page,`/mission-revisions/${run.body.mission_revision_id}`);
 const reference=page.getByLabel('Pinned contract revision and digest',{exact:true});await expect(reference.locator('.hash-disclosure>summary')).toHaveText(`${contract.body.content_sha256.slice(0,12)}…`);await reference.locator('.hash-disclosure>summary').click();await expect(reference.locator('.hash-disclosure>code')).toHaveText(contract.body.content_sha256);await expect(reference.locator('[data-testid=copy-hash][data-hash-kind=contract]')).toBeVisible();await reference.locator('.hash-disclosure>summary').click();
 await page.setViewportSize({width:390,height:844});await expect(page.locator('.run-metadata')).not.toHaveAttribute('open');await expect(reference).toBeHidden();await tab(page,'analogs');await expect(page.getByTestId('candidate-row').nth(1)).toBeVisible();const rows=await page.getByTestId('candidate-row').evaluateAll(nodes=>nodes.slice(0,2).map(node=>({bottom:node.getBoundingClientRect().bottom,limit:document.querySelector('.operations-bar')!.getBoundingClientRect().top})));for(const row of rows)expect(row.bottom).toBeLessThanOrEqual(row.limit+1);
});
