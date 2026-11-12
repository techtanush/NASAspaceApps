import {it,expect} from 'vitest';
import {readFileSync} from 'node:fs';
it('C20 locks all visual thresholds to the supplied standard',()=>{
 const script=readFileSync('../../scripts/ui/visual_audit.mjs','utf8');
 for(const exact of ['minText:12','bodyText:13','contrast:4.5','largeContrast:3','grid:4','cls:0.02','target:24','touchTarget:44','radius:6','glyphIoU:0.85','[[1920,1080],[1440,900],[1280,800],[1024,768],[768,1024],[390,844]]']) expect(script).toContain(exact);
});
