import { describe,it,expect } from 'vitest';
import { parseRoverImport } from './validation';
import rover from '../../../../../tests/fixtures/kit/rovers/ares-1.json';
describe('FE-008 rover import validation',()=>{
 it('rejects malformed files without modifying profile data',()=>{expect(parseRoverImport('{')).toMatchObject({ok:false});expect(rover.mass_kg).toBe(42);});
 it('identifies negative mass and preserves field errors',()=>{const result=parseRoverImport(JSON.stringify({...rover,mass_kg:-3}));expect(result.ok).toBe(false);if(!result.ok)expect(result.errors.some(error=>error.field==='mass_kg')).toBe(true);});
 it('accepts and preserves optional unknown values and perturbations',()=>{const result=parseRoverImport(JSON.stringify({...rover,name:'Changed',mass_kg:44}));expect(result.ok).toBe(true);if(result.ok){expect(result.value.mass_kg).toBe(44);expect(result.value.max_route_m).toBeNull();}});
});
