import {expect,it} from 'vitest';
import {chartSummary} from './chartSummary';
it('describes the ordered pattern and preserves the measurement unit',()=>{
 expect(chartSummary([{label:'A',value:.4},{label:'B',value:.3},{label:'C',value:.2}],'fraction')).toBe('Values decrease from A (0.4\u00a0fraction) to C (0.2\u00a0fraction).');
 expect(chartSummary([{label:'0–2 deg',value:.1},{label:'2–5 deg',value:.4},{label:'5–12 deg',value:.2}],'fraction of valid area')).toContain('Highest supplied value: 2–5 deg at 0.4\u00a0fraction of valid area; lowest: 0–2 deg');
});
it('does not infer a continuous trend through missing values',()=>{
 const description=chartSummary([{label:'A',value:.4},{label:'B',value:null},{label:'C',value:.2}],'fraction');
 expect(description).toContain('1 of 3 bins are unknown; a complete trend cannot be determined.');expect(description).not.toContain('Values decrease');
});
it('handles empty, equal, tied, increasing and singleton patterns honestly',()=>{
 expect(chartSummary([],'m')).toContain('pattern is unknown');
 expect(chartSummary([{label:'A',value:null}],'m')).toContain('pattern is unknown');
 expect(chartSummary([{label:'A',value:0},{label:'B',value:0}],'m')).toContain('All 2 known values are equal');
 expect(chartSummary([{label:'A',value:1},{label:'B',value:2}],'m')).toContain('Values increase');
 expect(chartSummary([{label:'A',value:1}],'m')).toContain('Only one known value');
 expect(chartSummary([{label:'A',value:2},{label:'B',value:1},{label:'C',value:2}],'m')).toContain('Highest supplied value: A, C');
});
