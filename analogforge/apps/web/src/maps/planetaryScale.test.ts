import {expect,it} from 'vitest';
import fixtures from '../mock/fixtures/display-assets.json';
import {planetaryGroundScale} from './planetaryScale';
it('uses the supplied spherical projection scale, independently of analysis support',()=>{
 const mars=fixtures.layers.MARS.display_crs_wkt;
 expect(planetaryGroundScale(mars,0,.0015)).toEqual({metres:50000,svgWidth:75,latitude:0});
 const latitude60=planetaryGroundScale(mars,60,.0015)!;expect(latitude60.metres).toBe(20000);expect(latitude60.svgWidth).toBeCloseTo(60,10);
 const moon=fixtures.layers.MOON.display_crs_wkt;
 expect(planetaryGroundScale(moon,-90,.0015)).toEqual({metres:50000,svgWidth:75,latitude:-90});
 expect(planetaryGroundScale(moon,0,.0015)?.svgWidth).toBeCloseTo(60,10);
});
it('does not invent a ground scale for unknown metadata, units or degenerate geometry',()=>{
 const wkt=fixtures.layers.MARS.display_crs_wkt;
 for(const input of [wkt.replaceAll('"metre",1','"foot",0.3048'),wkt.replace('3396190,0,','3396190,298.257,'),wkt.replace('Equidistant Cylindrical (Spherical)','Unknown'),wkt.replaceAll('ANGLEUNIT["degree",0.0174532925199433','ANGLEUNIT["radian",1')])expect(planetaryGroundScale(input,0,.0015)).toBeNull();
 expect(planetaryGroundScale(wkt,90,.0015)).toBeNull();expect(planetaryGroundScale(wkt,0,0)).toBeNull();expect(planetaryGroundScale(wkt,NaN,.0015)).toBeNull();
});
