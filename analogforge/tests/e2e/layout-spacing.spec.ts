import {test,expect} from '@playwright/test';
import {startRun,tab} from './support/workbench';
import {auditPage,finishAudit,installAuditInstrumentation} from '../../scripts/ui/visual_audit.mjs';
const spacing='*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}';
test('text spacing preserves scientific column ownership and active navigation',async({page})=>{
 test.setTimeout(300000);await installAuditInstrumentation(page);await startRun(page);await tab(page,'target');
 const coordinates=await page.getByRole('region',{name:'Region extent'}).count()?await page.getByRole('region',{name:'Region extent'}).innerText():await page.locator('[aria-label="Region extent"]').innerText();expect(coordinates).not.toMatch(/\d+\.\d{6}°/);expect(coordinates).toMatch(/\d+\.\d{5}°/);
 await page.setViewportSize({width:390,height:844});await page.locator('.run-tabs').evaluate(node=>{node.scrollLeft=node.scrollWidth;});
 await auditPage(page,'nav-restored',{width:390,height:844,theme:'light',focus:false});await expect(page.locator('.run-tabs [aria-current=page]')).toBeInViewport();
 await tab(page,'qualification');
 for(const width of [1440,390])for(const theme of ['dark','light']){
  await auditPage(page,'spacing-owned',{width,height:width===390?844:900,theme,spacing:true,focus:true});
  const override=await page.addStyleTag({content:spacing});const bad=await page.evaluate(()=>{
   const items=[...document.querySelectorAll('.qual-verdict .quantity,.run-metadata>summary>span:last-child')];return items.flatMap(node=>{const owner=node.closest('td')??node.closest('summary');if(!owner)return [];const range=document.createRange();range.selectNodeContents(node);const r=range.getBoundingClientRect(),b=owner.getBoundingClientRect();return r.left<b.left-1||r.right>b.right+1?[{text:node.textContent,range:[r.left,r.right],owner:[b.left,b.right]}]:[];});
  });expect(bad).toEqual([]);await override.evaluate(node=>node.remove());
 }
 const findings=finishAudit();expect(findings,JSON.stringify(findings.slice(0,10))).toEqual([]);
});
