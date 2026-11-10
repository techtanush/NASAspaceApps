import {test,expect} from '@playwright/test';
import {startRun,tab} from './support/workbench';
test('nonmodal operations persist outside focus and reopen with explicit dismissal',async({page})=>{
 test.setTimeout(180000);await startRun(page);await tab(page,'qualification');
 for(const width of [1920,1440,390,1440,1920,390]){
  await page.setViewportSize({width,height:900});
  await page.getByRole('button',{name:'Open operations',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Operations timeline',exact:true});await expect(dialog).toBeVisible();await expect(page.getByTestId('operation-row').first()).toBeVisible();
  for(let stop=0;stop<12;stop++)await page.keyboard.press('Tab');
  await page.getByRole('button',{name:'Open operations',exact:true}).focus();
  await expect(dialog).toBeVisible();
  await page.keyboard.press('Escape');await expect(dialog).toBeHidden();
  await expect(page.getByRole('button',{name:'Open operations',exact:true})).toBeFocused();
  await page.getByRole('button',{name:'Open operations',exact:true}).click();await expect(dialog).toBeVisible();await expect(page.getByTestId('operation-row').first()).toBeVisible();
  await page.keyboard.press('Escape');await expect(dialog).toBeHidden();
 }
});
