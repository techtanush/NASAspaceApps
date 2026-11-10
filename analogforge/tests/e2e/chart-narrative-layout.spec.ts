import {test,expect} from '@playwright/test';
import {startRun,tab} from './support/workbench';
import {auditPage,finishAudit,installAuditInstrumentation} from '../../scripts/ui/visual_audit.mjs';
test('chart prose wraps independently of horizontally scrolling plot data',async({page})=>{
 test.setTimeout(180000);await installAuditInstrumentation(page);await startRun(page);await tab(page,'target');
 await expect(page.locator('.target-histogram .chart-description')).toContainText('Highest supplied value');
 for(const width of [390,1440])for(const theme of ['dark','light'])for(const spacing of [false,true]){
  await auditPage(page,'chart-narrative',{width,height:900,theme,spacing,focus:false,anchor:'.target-histogram .chart-description'});
  const chart=page.locator('.target-histogram .chart');const before=await chart.locator('.chart-description').boundingBox();
  const ranges=await chart.locator(':scope>.helper').evaluateAll(nodes=>nodes.map(node=>{const range=document.createRange();range.selectNodeContents(node);const text=range.getBoundingClientRect(),frame=node.closest('.chart')!.getBoundingClientRect();return {left:text.left,right:text.right,min:Math.max(0,frame.left),max:Math.min(innerWidth,frame.right)};}));
  for(const text of ranges){expect(text.left).toBeGreaterThanOrEqual(text.min-1);expect(text.right).toBeLessThanOrEqual(text.max+1);}
  await chart.locator('.chart-plot-scroll').evaluate(node=>{node.scrollLeft=node.scrollWidth;});const after=await chart.locator('.chart-description').boundingBox();expect(after!.x).toBeCloseTo(before!.x,1);expect(after!.width).toBeCloseTo(before!.width,1);
 }
 const findings=finishAudit();expect(findings,JSON.stringify(findings.slice(0,12))).toEqual([]);
});
