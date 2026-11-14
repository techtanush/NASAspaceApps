import {test,expect} from '@playwright/test';
test('preview worker survives rapid document replacement without update errors',async({page})=>{
 test.setTimeout(90000);const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
 for(let index=0;index<16;index++){
  await page.goto(index%2?'/rovers':'/');await expect(page.getByTestId('app-shell')).toBeVisible();
  expect(await page.evaluate(async()=>{const response=await fetch('/auth/session');return response.status;})).toBe(200);
 }
 expect(errors).toEqual([]);
});
