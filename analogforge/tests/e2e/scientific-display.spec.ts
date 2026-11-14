import {test,expect} from '@playwright/test';
import {startRun,tab} from './support/workbench';
test('displayed slope boundaries and submeter rover clearance preserve the supplied engineering meaning',async({page})=>{
 await startRun(page);await tab(page,'target');
 const plot=page.getByRole('region',{name:/Slope histogram plot/});await expect(plot.locator('line[stroke-dasharray]')).toHaveCount(2);
 for(const [index,bin] of [[0,'12–15 deg:'],[1,'18–25 deg:']] as const){
  const boundary=await plot.locator('line[stroke-dasharray]').nth(index).getAttribute('x1');const bar=plot.locator('g[role=img]').filter({has:page.locator('title')}).filter({hasText:bin}).locator('rect');
  expect(Number(boundary)).toBeCloseTo(Number(await bar.getAttribute('x')),5);
 }
 await tab(page,'analogs');const first=page.getByTestId('candidate-row').first();await first.getByTestId('btn-select-candidate').click();await expect(first).toHaveAttribute('data-selected','true');await tab(page,'compatibility');
 const clearance=page.locator('[data-testid=compat-row][data-metric-id=ground_clearance_m]');await expect(clearance).toHaveAttribute('data-status','UNKNOWN');await expect(clearance.locator('td').first()).toContainText(/0\.20\s*m/);
});
