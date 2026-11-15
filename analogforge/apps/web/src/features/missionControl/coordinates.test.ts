import { describe,it,expect } from 'vitest';
import {parseAngle,normalizeLongitude,areaBox} from './coordinates';
describe('body-aware coordinate entry',()=>{
 it('rejects intermediate and nonfinite input without silently moving the pin',()=>{for(const value of ['', ' ', '-', '.', '1e2','Infinity','NaN'])expect(Number.isNaN(parseAngle(value))).toBe(true);expect(parseAngle(' -4.80 ')).toBe(-4.8);});
 it('normalizes the accepted longitude conventions at their seams',()=>{expect(normalizeLongitude(360)).toBe(0);expect(normalizeLongitude(180)).toBe(180);expect(normalizeLongitude(181)).toBe(-179);expect(Number.isNaN(normalizeLongitude(361))).toBe(true);});
 it('does not expand a seam or polar region into nearly a whole globe',()=>{expect(areaBox('MARS',0,179.99,80).ok).toBe(false);expect(areaBox('MOON',89.99,0,80).ok).toBe(false);expect(areaBox('MARS',0,0,Infinity).ok).toBe(false);expect(areaBox('MARS',-4.8,137.4,40).ok).toBe(true);});
});
