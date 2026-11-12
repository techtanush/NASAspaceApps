import {test,expect} from '@playwright/test';
import {startRun,tab} from './support/workbench';
test('nonmodal operations persist outside focus and reopen with explicit dismissal',async({page})=>{
 test.setTimeout(180000);await startRun(page);await tab(page,'qualification');
 for(const width of [1920,1440,390,1440,1920,390]){
  await page.setViewportSize({width,height:900});
  await page.getByRole('button',{name:'Open operations',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Operations timeline',exact:true});await expect(dialog).toBeVisible();await expect(page.getByTestId('operation-row').first()).toBeVisible();
  const first=page.getByTestId('operation-row').first();
  await expect(first.locator('time')).toBeVisible();await expect(first.getByText('Actor unknown',{exact:true})).toBeVisible();await expect(first.locator('.operation-summary')).not.toBeEmpty();
  const geometry=await first.evaluate(node=>{const row=node.getBoundingClientRect();return {height:row.height,overflow:node.scrollWidth>node.clientWidth+1,children:[...node.children].map(child=>{const r=child.getBoundingClientRect();return {left:r.left,right:r.right,min:row.left,max:row.right};})};});
  expect(geometry.height).toBeLessThanOrEqual(width<768?164:80);expect(geometry.overflow).toBe(false);for(const item of geometry.children){expect(item.left).toBeGreaterThanOrEqual(item.min);expect(item.right).toBeLessThanOrEqual(item.max);}
  await first.locator('summary').click();await expect(first.getByText('Actor identity is not supplied by this event.')).toBeVisible();await expect(first.getByText(/^Event type:/)).toBeVisible();await first.locator('summary').click();
  await page.screenshot({path:`../../out/operations-compact-${width}.png`});
  for(let stop=0;stop<12;stop++)await page.keyboard.press('Tab');
  await page.getByRole('button',{name:'Open operations',exact:true}).focus();
  await expect(dialog).toBeVisible();
  await page.keyboard.press('Escape');await expect(dialog).toBeHidden();
  await expect(page.getByRole('button',{name:'Open operations',exact:true})).toBeFocused();
  await page.getByRole('button',{name:'Open operations',exact:true}).click();await expect(dialog).toBeVisible();await expect(page.getByTestId('operation-row').first()).toBeVisible();
  await page.keyboard.press('Escape');await expect(dialog).toBeHidden();
 }
});
