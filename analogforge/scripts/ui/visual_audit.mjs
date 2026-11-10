import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { mkdirSync, readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
const require=createRequire(resolve(root,'apps/web/package.json'));
const { PNG }=require('pngjs');
const AxeBuilder=require('@axe-core/playwright').default;
export const THRESHOLDS=Object.freeze({minText:12,bodyText:13,contrast:4.5,largeContrast:3,grid:4,cls:0.02,target:24,touchTarget:44,radius:6,glyphIoU:0.85,viewports:[[1920,1080],[1440,900],[1280,800],[1024,768],[768,1024],[390,844]]});
export const COMPONENTS=['AppShell','AppHeader','ModeBadge','ConnectionIndicator','RevisionBadge','StatusBadge','StatusGlyph','Button','IconButton','Input','NumberInput','Select','Segmented','FileDrop','FormField','Table','MatrixCell','SortHeader','Tabs','Banner','MockBanner','EmptyState','ErrorPanel','Skeleton','Dialog','Drawer','Tooltip','Toast','Popover','CopyHash','Mono','Quantity','Timestamp','Hash','Stepper','Timeline','Histogram','Line','Bar','DataTableToggle','LayerPanel','Legend','ScaleBar','CoordinateReadout','Attribution','KbdHint','VisuallyHidden'];
const requiredHooks=JSON.parse(readFileSync(resolve(root,'contracts/ui-testids.json'),'utf8')).testids;
const auditStates=new WeakMap();
export async function installAuditInstrumentation(page){
 if(auditStates.has(page))return;
 const state={inflight:new Set(),navigationAborts:new WeakSet(),signals:new Map(),failures:[],cancellations:[]};auditStates.set(page,state);
 await page.exposeBinding('__analogForgeAuditAbort',(_source,url,method)=>{const key=method+' '+url;state.signals.set(key,(state.signals.get(key)||0)+1);});
 page.on('request',request=>{
  if(request.isNavigationRequest()&&request.frame()===page.mainFrame())for(const pending of state.inflight)state.navigationAborts.add(pending);
  state.inflight.add(request);
 });page.on('requestfinished',request=>state.inflight.delete(request));
 page.on('requestfailed',async request=>{
  state.inflight.delete(request);await new Promise(resolve=>setTimeout(resolve,40));
  const error=request.failure()?.errorText||'Transport failed';const key=request.method()+' '+request.url();const signalled=(state.signals.get(key)||0)>0;
  if(error==='net::ERR_ABORTED'&&(state.navigationAborts.has(request)||signalled)){
   if(signalled)state.signals.set(key,state.signals.get(key)-1);
   state.cancellations.push({method:request.method(),path:new URL(request.url()).pathname,reason:state.navigationAborts.has(request)?'audit navigation':'observed AbortSignal'});
  }else state.failures.push({check:'C12',message:request.method()+' '+new URL(request.url()).pathname+': '+error});
 });
 await page.addInitScript(()=>{
  window.__auditCLS=0;window.__auditShifts=[];window.__auditMeasureCLS=true;window.__auditPending=0;
  const original=window.fetch.bind(window);
  window.fetch=(input,init)=>{
   const request=input instanceof Request?input:null;const url=new URL(request?request.url:String(input),location.href).href;const method=init?.method||request?.method||'GET';const signal=init?.signal||request?.signal;
   if(signal){const record=()=>{void window.__analogForgeAuditAbort(url,method);};if(signal.aborted)record();else signal.addEventListener('abort',record,{once:true});}
   const observed=/\/(?:api\/v1|auth|artifacts)\//.test(new URL(url).pathname);if(observed)window.__auditPending++;
   return original(input,init).finally(()=>{if(observed)window.__auditPending--;});
  };
  const observer=new PerformanceObserver(list=>{if(window.__auditMeasureCLS)for(const entry of list.getEntries())if(!entry.hadRecentInput){window.__auditCLS+=entry.value;window.__auditShifts.push({value:entry.value,sources:(entry.sources||[]).map(source=>({node:source.node?.outerHTML?.slice(0,300),before:source.previousRect,after:source.currentRect}))});}});observer.observe({type:'layout-shift',buffered:true});
  for(const name of ['pushState','replaceState']){const method=history[name].bind(history);history[name]=(...args)=>{observer.takeRecords();window.__auditCLS=0;window.__auditShifts=[];window.__auditMeasureCLS=true;method(...args);};}
 });
}
export function auditFailures(page){return auditStates.get(page)?.failures||[];}
export function auditCancellations(page){return auditStates.get(page)?.cancellations||[];}
export async function waitForAuditData(page){
 for(let pass=0;pass<12;pass++){
  await page.waitForFunction(()=>!(window.__auditPending||0)&&document.fonts.status==='loaded');
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  if(await page.evaluate(()=>!(window.__auditPending||0)))return;
 }
 throw new Error('Scientific display requests did not settle');
}
async function beginLoadedCohort(page,{width,height,theme,density}){
 await page.setViewportSize({width,height});
 await page.evaluate(({theme,density})=>{localStorage.setItem('af.theme',theme);localStorage.setItem('af.density',density);},{theme,density});
 const state=auditStates.get(page);if(state)for(const request of state.inflight)state.navigationAborts.add(request);
 await page.reload({waitUntil:'domcontentloaded'});await page.locator('main h1').waitFor({state:'visible',timeout:60000});
 await waitForAuditData(page);
 return page.evaluate(()=>{window.__auditMeasureCLS=false;return window.__auditCLS||0;});
}
export const reports=[];
export const manifest=[];
const hash=b=>createHash('sha256').update(b).digest('hex');
export async function auditPage(page,name,{theme='dark',density='default',width=1440,height=900,focus=true,spacing=false}={}){
 const measureLoad=['S01','S06','S07','S10','S12'].some(prefix=>name.startsWith(prefix));
 if(measureLoad)await beginLoadedCohort(page,{width,height,theme,density});else{await page.evaluate(()=>{window.__auditMeasureCLS=false;});await page.setViewportSize({width,height});}
 await page.evaluate(()=>{if(!document.querySelector('[role=dialog]')&&document.activeElement instanceof HTMLElement)document.activeElement.blur();window.scrollTo(0,0);for(const element of document.querySelectorAll('*')){const style=getComputedStyle(element);if(/auto|scroll/.test(style.overflow+style.overflowX+style.overflowY)){element.scrollTop=0;element.scrollLeft=0;}}});
 // Use the application's preference controls so header labels and effective styles agree.
 // DOM click preserves the focus of an already open nonmodal evidence drawer.
 for(const [id,attribute,value]of [['theme-toggle','data-theme-choice',theme],['density-toggle','data-density',density]]){
  const control=page.getByTestId(id);for(let attempt=0;attempt<3&&await control.getAttribute(attribute)!==value;attempt++){await control.evaluate(node=>node.click());await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(resolve)));}
 }
 await page.evaluate(({theme,density})=>{document.documentElement.dataset.theme=theme; document.documentElement.dataset.density=density;},{theme,density});
 await page.evaluate(()=>document.fonts.ready);
 const spacingStyle=spacing?await page.addStyleTag({content:'*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}'}):null;
 const screenshot=await page.screenshot();
 const png=PNG.sync.read(screenshot);
 const facts=await page.evaluate(({limits,spacing,width,requiredHooks})=>{
  const findings=[]; const text=[]; const all=[...document.querySelectorAll('body *')];
  const visible=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();
   if(s.display==='none'||s.visibility==='hidden'||s.clipPath==='inset(50%)'||r.width<=0||r.height<=0)return false;
   for(let parent=e.parentElement;parent;parent=parent.parentElement){if(parent.tagName==='DETAILS'&&!parent.open){const summary=parent.querySelector(':scope > summary');if(!summary?.contains(e))return false;}}
   return true;
  };
  const paintedRect=e=>{const initial=e.getBoundingClientRect();const box={left:Math.max(0,initial.left),right:Math.min(innerWidth,initial.right),top:Math.max(0,initial.top),bottom:Math.min(innerHeight,initial.bottom)};for(let parent=e.parentElement;parent;parent=parent.parentElement){const style=getComputedStyle(parent),r=parent.getBoundingClientRect();if(/auto|scroll|hidden|clip/.test(style.overflowX)){box.left=Math.max(box.left,r.left+parent.clientLeft);box.right=Math.min(box.right,r.left+parent.clientLeft+parent.clientWidth);}if(/auto|scroll|hidden|clip/.test(style.overflowY)){box.top=Math.max(box.top,r.top+parent.clientTop);box.bottom=Math.min(box.bottom,r.top+parent.clientTop+parent.clientHeight);}}return box;};
  const canvasBounds=[...document.querySelectorAll('[data-testid="earth-map"] canvas,[data-testid="planetary-panel"] svg.planetary-svg')].map(canvas=>({element:canvas,rect:canvas.getBoundingClientRect()}));
  const add=(check,e,message)=>findings.push({check,selector:e.getAttribute('data-testid')||e.id||e.tagName.toLowerCase(),message});
  const rgb=s=>{const m=s.match(/[\d.]+/g);return m?m.map(Number):[0,0,0,0];};
  const lum=c=>{const s=c.slice(0,3).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return .2126*s[0]+.7152*s[1]+.0722*s[2]};
  const ratio=(a,b)=>(Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
  for(const e of all.filter(visible)){
   const s=getComputedStyle(e),r=e.getBoundingClientRect();
   const nodes=[...e.childNodes].filter(n=>n.nodeType===Node.TEXT_NODE&&n.textContent.trim());
   if(nodes.length){
    const family=s.fontFamily.split(',')[0].replace(/["']/g,'').trim(); if(!['Inter','Inter Variable','IBM Plex Mono'].includes(family))add('C01',e,`Font ${family}`);
    if(parseFloat(s.fontSize)<limits.minText)add('C02',e,`Text ${s.fontSize}`);
    if(e.matches('td,input,textarea,button')&&parseFloat(s.fontSize)<limits.bodyText)add('C02',e,`Body text ${s.fontSize}`);
    let parent=e,bg=[0,0,0,0]; while(parent){const c=rgb(getComputedStyle(parent).backgroundColor); if(c.length<4||c[3]===1){bg=c;break;}parent=parent.parentElement;}
    const fg=rgb(s.color); const min=parseFloat(s.fontSize)>=24||(parseFloat(s.fontSize)>=18.66&&Number(s.fontWeight)>=700)?limits.largeContrast:limits.contrast;
    if(bg[3]!==0&&ratio(fg,bg)<min-.01)add('C03',e,`Contrast ${ratio(fg,bg).toFixed(2)} < ${min}`);
    for(const node of nodes){const range=document.createRange();range.selectNodeContents(node);const box=range.getBoundingClientRect();
     // An opaque foreground plate is measured above against its own background,
     // not against canvas pixels behind it or adjacent inline glyphs.
     const painted=paintedRect(e);
     const overCanvas=box.left>=painted.left&&box.right<=painted.right&&box.top>=painted.top&&box.bottom<=painted.bottom&&canvasBounds.some(({element,rect:c})=>parent?.contains(element)&&box.left>=c.left&&box.right<=c.right&&box.top>=c.top&&box.bottom<=c.bottom);
     text.push({x:box.x,y:box.y,w:box.width,h:box.height,fg,min,text:node.textContent,selector:e.getAttribute('data-testid')||e.tagName.toLowerCase(),overCanvas});
    }
    if(/\b(NaN|undefined|null|\[object Object\])\b/.test(nodes.map(n=>n.textContent).join(' ')))add('C09',e,'Invalid rendered value');
    if(e.scrollWidth>e.clientWidth+1&&s.display!=='inline'&&!e.closest('[data-overflow="intentional"]'))add('C05',e,`Text overflow ${e.scrollWidth}/${e.clientWidth}`);
   }
   if(e.matches('[class*="panel"],[class*="card"],td,th,button,input,select,[role="tab"],[role="row"]')){
    for(const prop of ['paddingTop','paddingRight','paddingBottom','paddingLeft','marginTop','marginRight','marginBottom','marginLeft','gap','rowGap','columnGap']){const v=parseFloat(s[prop]);if(Number.isFinite(v)&&v!==0&&Math.abs(v/4-Math.round(v/4))>.01)add('C04',e,`${prop}=${v}`);}
    // CSS Typed OM preserves auto/percentage/flex-derived dimensions. Only explicit pixel sizes are grid-constrained.
    for(const prop of ['width','height']){const v=e.computedStyleMap?.().get(prop);if(v?.unit==='px'&&v.value!==0&&Math.abs(v.value/4-Math.round(v.value/4))>.01)add('C04',e,`${prop}=${v.value}`);}
   }
   if(e.matches('button,input:not([type=hidden]),select,textarea,a[href],summary,[role=button],[role=tab],[role=combobox],[role=option],[role=checkbox],[role=switch]')){
    const min=width<=390?limits.touchTarget:limits.target;
    if(r.width<min-.5||r.height<min-.5)add('C06',e,`Target ${r.width.toFixed(1)}×${r.height.toFixed(1)} < ${min}`);
   }
   if(e.matches('td,[data-numeric]')&&/^[-+−]?[\d,.]+(?:\s*[%a-zA-Z/°]+)?$/.test(e.textContent.trim())){if(s.textAlign!=='right'||!s.fontVariantNumeric.includes('tabular-nums'))add('C09',e,'Numeric cell lacks alignment/tabular figures');}
   if(s.backgroundImage.includes('gradient')&&e.dataset.allowed!=='scientific-ramp')add('C10',e,'Gradient');
   if(s.backdropFilter!=='none'||s.textShadow!=='none')add('C10',e,'Backdrop or text shadow');
   if(s.boxShadow!=='none'&&!e.closest('[role=dialog],[data-overlay], [data-testid=evidence-drawer]'))add('C10',e,'Unexpected shadow');
   for(const prop of ['borderTopLeftRadius','borderTopRightRadius','borderBottomLeftRadius','borderBottomRightRadius'])if(parseFloat(s[prop])>limits.radius&&!(r.width<=12&&r.height<=12&&s[prop].includes('%')))add('C10',e,`${prop}=${s[prop]}`);
   if(/[\u{1f300}-\u{1faff}]/u.test((nodes.map(n=>n.textContent).join(' '))+['alt','title','aria-label'].map(a=>e.getAttribute(a)||'').join(' ')))add('C10',e,'Emoji');
   if(/lorem ipsum|todo|coming soon|!+\s*$/i.test(nodes.map(n=>n.textContent).join(' ')))add('C10',e,'Unfinished or promotional copy');
  }
  for(const hook of requiredHooks)for(const element of document.querySelectorAll(`[data-testid="${hook.id}"]`)){
   let closed=false;for(let parent=element.parentElement;parent;parent=parent.parentElement)if(parent.tagName==='DETAILS'&&!parent.open&&!parent.querySelector(':scope > summary')?.contains(element)){closed=true;break;}
   if(closed)continue;
   if(!visible(element))add('C05',element,'Required hook is hidden or zero-sized');
   for(const attr of hook.required_attributes)if(!element.getAttribute(attr))add('C05',element,'Required hook attribute missing: '+attr);
  }
  if(document.documentElement.scrollWidth>innerWidth)add('C05',document.documentElement,'Page overflow');
  const interactive=all.filter(e=>visible(e)&&e.matches('button,input:not([type=hidden]),select,textarea,a[href],summary,[role=button],[role=tab],[role=combobox],[role=option],[role=checkbox],[role=switch]'));
  const interactiveBoxes=interactive.map(element=>paintedRect(element));
  for(let i=0;i<interactive.length;i++)for(let j=i+1;j<interactive.length;j++){const a=interactive[i],b=interactive[j];if(a.contains(b)||b.contains(a)||a.closest('[role=dialog]')!==b.closest('[role=dialog]'))continue;const x=interactiveBoxes[i],y=interactiveBoxes[j];if(x.right<=x.left||y.right<=y.left||x.bottom<=x.top||y.bottom<=y.top)continue;if(Math.min(x.right,y.right)-Math.max(x.left,y.left)>2&&Math.min(x.bottom,y.bottom)-Math.max(x.top,y.top)>2)add('C05',a,'Interactive overlap '+(b.id||b.tagName));}
  if(document.querySelectorAll('main h1').length!==1)add('C13',document.body,'Exactly one h1 required');
  let previous=0;for(const h of all.filter(e=>visible(e)&&/^H[1-6]$/.test(e.tagName))){const level=Number(h.tagName[1]);if(previous&&level>previous+1)add('C13',h,'Heading level skipped');previous=level;}
  for(const region of document.querySelectorAll('[data-region]'))if([...region.querySelectorAll('[data-variant=primary]')].filter(visible).length>1)add('C13',region,'Multiple primary actions');
  for(const large of document.querySelectorAll('[data-size=xl]'))if(large.getAttribute('data-testid')!=='btn-prove-it')add('C13',large,'Only PROVE IT may be xl');
  const faces=[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family);if(!faces.some(f=>f.includes('Inter'))||!faces.some(f=>f.includes('Plex')))add('C01',document.body,'Self-hosted fonts not loaded');
  return {findings,text,spacing,cls:window.__auditCLS||0,layoutShifts:window.__auditShifts||[]};
 },{limits:THRESHOLDS,spacing,width,requiredHooks});
 const findings=[...facts.findings];
 // Canvas-overlay contrast uses screenshot pixels in a four-pixel ring around the text box.
 for(const t of facts.text.filter(t=>t.overCanvas)){
  const samples=[[t.x-4,t.y+t.h/2],[t.x+t.w+4,t.y+t.h/2],[t.x+t.w/2,t.y-4],[t.x+t.w/2,t.y+t.h+4]];
  const luminosity=c=>c.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
  for(const [x,y]of samples){if(x<0||y<0||x>=png.width||y>=png.height)continue;const p=(Math.floor(y)*png.width+Math.floor(x))*4;const bg=[...png.data.subarray(p,p+3)];const a=luminosity(t.fg),b=luminosity(bg),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);if(ratio<t.min-.01)findings.push({check:'C03',selector:t.selector,message:`Canvas contrast ${ratio.toFixed(2)}`,text:t.text,box:[t.x,t.y,t.w,t.h],sample:[x,y],background:bg});}
 }
 const axe=await new AxeBuilder({page}).withRules(['color-contrast']).analyze();for(const v of axe.violations)for(const n of v.nodes)findings.push({check:'C03',selector:n.target.join(' '),message:n.failureSummary});
 if(facts.cls>THRESHOLDS.cls&&['S01','S06','S07','S10','S12'].some(s=>name.startsWith(s)))findings.push({check:'C11',message:`CLS ${facts.cls}`});
 if(focus){
  const overlay=await page.locator('[role=dialog]').count()>0;
  await page.evaluate(()=>{if(!document.querySelector('[role=dialog]')&&document.activeElement instanceof HTMLElement)document.activeElement.blur();});
  await page.evaluate(()=>{window.__auditFocusIDs=new WeakMap();window.__auditNextFocusID=0;});
  const seen=new Set();for(let n=0;n<80;n++){
   await page.keyboard.press('Tab');const result=await page.evaluate(()=>{const e=document.activeElement;if(!(e instanceof HTMLElement)||e===document.body)return null;const s=getComputedStyle(e),r=e.getBoundingClientRect();const box={left:Math.max(0,r.left),right:Math.min(innerWidth,r.right),top:Math.max(0,r.top),bottom:Math.min(innerHeight,r.bottom)};for(let parent=e.parentElement;parent;parent=parent.parentElement){const style=getComputedStyle(parent),p=parent.getBoundingClientRect();if(/auto|scroll|hidden|clip/.test(style.overflowX)){box.left=Math.max(box.left,p.left+parent.clientLeft);box.right=Math.min(box.right,p.left+parent.clientLeft+parent.clientWidth);}if(/auto|scroll|hidden|clip/.test(style.overflowY)){box.top=Math.max(box.top,p.top+parent.clientTop);box.bottom=Math.min(box.bottom,p.top+parent.clientTop+parent.clientHeight);}}
   const hit=box.right>box.left&&box.bottom>box.top?document.elementFromPoint((box.left+box.right)/2,(box.top+box.bottom)/2):null;const rgb=value=>(value.match(/[\d.]+/g)||[]).map(Number);const lum=value=>rgb(value).slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);let adjacent=e.parentElement,bg='';while(adjacent){const value=getComputedStyle(adjacent).backgroundColor,channels=rgb(value);if(channels.length===3||channels[3]===1){bg=value;break;}adjacent=adjacent.parentElement;}const a=lum(s.outlineColor),b=lum(bg);const ringContrast=bg?(Math.max(a,b)+.05)/(Math.min(a,b)+.05):0;let focusID=window.__auditFocusIDs.get(e);if(!focusID){focusID=++window.__auditNextFocusID;window.__auditFocusIDs.set(e,focusID);}return {focusID,inDialog:!!e.closest('[role=dialog]'),id:e.outerHTML.slice(0,240),ring:parseFloat(s.outlineWidth)>=2&&s.outlineStyle!=='none',ringContrast,covered:!hit||!(e===hit||e.contains(hit)),rect:box,hit:hit?.outerHTML.slice(0,120)};});
   if(!result||overlay&&!result.inDialog||seen.has(result.focusID))break;seen.add(result.focusID);if(!result.ring)findings.push({check:'C07',selector:result.id,message:'Missing focus ring'});else if(result.ringContrast<THRESHOLDS.largeContrast-.01)findings.push({check:'C07',selector:result.id,message:'Focus contrast '+result.ringContrast.toFixed(2)});if(result.covered)findings.push({check:'C07',selector:result.id,message:'Focus obscured '+JSON.stringify({rect:result.rect,hit:result.hit})});
  }
 }
 const filename=`${name}-${width}-${theme}-${density}${spacing?'-spacing':''}.png`;mkdirSync(resolve(root,'out/visual'),{recursive:true});writeFileSync(resolve(root,'out/visual',filename),screenshot);manifest.push({file:filename,screen:name,theme,density,width,height,sha256:hash(screenshot)});
 reports.push({screen:name,width,height,theme,density,findings,layoutShifts:facts.layoutShifts});if(spacingStyle)await spacingStyle.evaluate(node=>node.remove());return findings;
}
export async function auditStyleguide(page){
 const result=await new AxeBuilder({page}).analyze();const findings=result.violations.filter(row=>['critical','serious'].includes(row.impact||'')).flatMap(row=>row.nodes.map(node=>({check:'C18',selector:node.target.join(' '),message:row.id+': '+node.failureSummary})));
 reports.push({screen:'styleguide-accessibility',findings});return findings;
}
export async function auditGlyphs(page){
 const result=await page.evaluate(async()=>{
  const states=['PASS','PARTIAL','FAIL','GAP','UNKNOWN','PENDING'];const findings=[],masks=[];
  document.documentElement.style.filter='grayscale(1)';
  for(const state of states){const node=document.querySelector(`[data-status="${state}"]`),svg=node?.querySelector('svg');if(!node||!svg){findings.push({check:'C08',message:`Missing ${state} word/glyph`});continue;}if(!node.textContent.toLowerCase().includes(state.toLowerCase()))findings.push({check:'C08',message:`Missing ${state} word`});const src=new XMLSerializer().serializeToString(svg);const img=new Image();img.src='data:image/svg+xml;base64,'+btoa(unescape(encodeURIComponent(src)));await img.decode();const canvas=document.createElement('canvas');canvas.width=24;canvas.height=24;const ctx=canvas.getContext('2d');ctx.drawImage(img,0,0,24,24);const data=ctx.getImageData(0,0,24,24).data; masks.push({state,path:[...svg.querySelectorAll('path,circle,rect,polygon,line')].map(e=>e.outerHTML).join(''),pixels:Array.from({length:576},(_,i)=>data[i*4+3]>127)});}
  for(let i=0;i<masks.length;i++)for(let j=i+1;j<masks.length;j++){const a=masks[i],b=masks[j];const intersection=a.pixels.filter((p,k)=>p&&b.pixels[k]).length,union=a.pixels.filter((p,k)=>p||b.pixels[k]).length;if(a.path===b.path||union&&intersection/union>.85)findings.push({check:'C08',message:`Indistinct ${a.state}/${b.state}`});}
  document.documentElement.style.filter='';return findings;
 });reports.push({screen:'styleguide-glyphs',findings:result});return result;
}
export function finishAudit(){
 mkdirSync(resolve(root,'out/visual'),{recursive:true});const findings=reports.flatMap(r=>r.findings.map(f=>({...f,screen:r.screen,viewport:r.width,theme:r.theme})));writeFileSync(resolve(root,'out/visual/report.json'),JSON.stringify({status:findings.length?'FAIL':'PASS',thresholds:THRESHOLDS,skipped_checks:0,reports,findings},null,2));writeFileSync(resolve(root,'out/visual/manifest.json'),JSON.stringify(manifest,null,2));writeFileSync(resolve(root,'out/visual/screens.md'),'# Visual review catalog\n\n| File | Screen | Viewport | Theme | Density |\n|---|---|---|---|---|\n'+manifest.map(x=>`| ${x.file} | ${x.screen} | ${x.width}×${x.height} | ${x.theme} | ${x.density} |`).join('\n')+'\n');return findings;
}
export function auditProduction(){
 const dist=resolve(root,'apps/web/dist');const findings=[];const urls=new Set();
 const files=[];const visit=directory=>{for(const entry of readdirSync(directory,{withFileTypes:true})){const filename=resolve(directory,entry.name);if(entry.isDirectory())visit(filename);else files.push(filename);}};visit(dist);
 const permitted=[
  ['XML/MathML/SVG namespace',/^http:\/\/www\.w3\.org\//],
  ['local URL-parser base',/^http:\/\/localhost$/],
  ['JSON Schema identifier',/^https?:\/\/json-schema\.org\//],
  ['AJV embedded schema identifier',/^https:\/\/raw\.githubusercontent\.com\/ajv-validator\/ajv\/master\/lib\/refs\/data\.json#/],
  ['library documentation',/^https:\/\/(?:react\.dev\/errors\/|reactrouter\.com\/en\/main\/routers\/|radix-ui\.com\/primitives\/docs\/|maplibre\.org\/|github\.com\/mapbox\/mapbox-gl-js\/issues\/|github\.com\/ungap\/url-search-params)/],
 ];
 const classified=[];
 for(const filename of files){
  if(!/\.(?:js|css|html)$/.test(filename))continue;const content=readFileSync(filename,'utf8');
  if(/mockServiceWorker|setupWorker|MOCK PREVIEW|__styleguide/.test(content))findings.push({check:'C19',file:filename,message:'Development-only code in production output'});
  const resources=filename.endsWith('.html')?[...content.matchAll(/<(?:script|link)\b[^>]*(?:src|href)=["']([^"']+)/g)].map(m=>m[1]):filename.endsWith('.css')?[...content.matchAll(/url\(["']?([^)'"\s]+)/g)].map(m=>m[1]):[];
  for(const resource of resources)if(/^https?:|^\/\//.test(resource))findings.push({check:'C19',file:filename,message:'External resource '+resource});
  if(filename.endsWith('.js'))for(const match of content.matchAll(/https?:\/\/[^\s"'`<>\\]+/g))urls.add(match[0]);
 }
 for(const url of urls){const category=permitted.find(([,rule])=>rule.test(url))?.[0];if(!category)findings.push({check:'C19',message:'Unclassified literal URL '+url});classified.push({url,category:category||'unclassified'});}
 if(existsSync(resolve(dist,'mockServiceWorker.js')))findings.push({check:'C19',message:'Mock service worker copied into production'});
 mkdirSync(resolve(root,'out'),{recursive:true});writeFileSync(resolve(root,'out/production-audit.json'),JSON.stringify({status:findings.length?'FAIL':'PASS',findings,literal_identifiers_and_documentation:classified},null,2));return findings;
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const scan=spawnSync('python3',['scripts/ui/forbidden_scan.py'],{cwd:root,encoding:'utf8'});if(scan.status!==0){console.error(scan.stdout);process.exit(scan.status||1);}
 const build=spawnSync('pnpm',['run','build'],{cwd:root,stdio:'inherit'});if(build.status!==0)process.exit(build.status||1);
 const production=auditProduction();if(production.length){console.error(JSON.stringify(production));process.exit(1);}
 const suites=process.argv.includes('--all')?[]:['visual-audit.spec.ts'];
 const result=spawnSync('pnpm',['--filter','@analogforge/web','exec','playwright','test',...suites],{cwd:root,env:{...process.env,E2E_TARGET:'mock'},stdio:'inherit'});process.exit(typeof result.status==='number'?result.status:1);
}
