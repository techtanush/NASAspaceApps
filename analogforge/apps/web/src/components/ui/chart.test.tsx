import {render} from '@testing-library/react';
import {expect,it} from 'vitest';
import {Chart} from './index';
it('registers accepted slope boundaries to the same categorical intervals as supplied bars',()=>{
 const {container}=render(<Chart title="Slope distribution" unit="fraction" values={[{label:'0–2',lower:0,upper:2,value:.4},{label:'2–5',lower:2,upper:5,value:.3},{label:'5–12',lower:5,upper:12,value:.1},{label:'12–18',lower:12,upper:18,value:.2},{label:'18–90',lower:18,upper:90,value:0}]} thresholds={[{value:12,label:'Lower bound'},{value:18,label:'Upper bound'}]}/>);
 const lines=container.querySelectorAll('line[stroke-dasharray]');const bars=container.querySelectorAll('svg g[role="img"] rect');
 expect(lines).toHaveLength(2);expect(lines[0].getAttribute('x1')).toBe(bars[3].getAttribute('x'));expect(lines[1].getAttribute('x1')).toBe(bars[4].getAttribute('x'));
});
