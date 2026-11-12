import { expect,it } from 'vitest';
import { earthCorners,pixelToWorld,worldToPixel,screenToWorld,worldToScreen,type Affine } from './affine';
import { validateEarthLayer,validatePlanetaryLayer } from './layerRegistry';
import type { components } from '../generated/schema';
it.each<Affine>([[100,60,0,500,0,-60],[100,60,12,500,8,-60]])('SCN-17 four corners and interior survive rotated GDAL transforms %j',(...transform)=>{for(const p of [[0,0],[64,0],[64,64],[0,64],[27.25,31.75]] as const){const result=worldToPixel(transform,pixelToWorld(transform,p));expect(result[0]).toBeCloseTo(p[0],10);expect(result[1]).toBeCloseTo(p[1],10);const screen=worldToScreen(transform,pixelToWorld(transform,p),{x:15,y:25,scale:3});expect(screenToWorld(transform,screen,{x:15,y:25,scale:3})).toEqual(pixelToWorld(transform,p));}});
it('Earth corner order is NW NE SE SW',()=>expect(earthCorners([-120,30,-119,31])).toEqual([[-120,31],[-119,31],[-119,30],[-120,30]]));
it('rejects Earth/body/CRS mismatches rather than drawing false planetary geography',()=>{const layer={body:'MARS',rendering:'PLANETARY_PLANAR_IMAGE',display_crs_wkt:'Mars Equirectangular',earth_corners:null} as components['schemas']['DisplayLayerManifest'];expect(validatePlanetaryLayer(layer)).toBe(layer);expect(()=>validateEarthLayer(layer)).toThrow();expect(()=>validatePlanetaryLayer({...layer,display_crs_wkt:'EPSG:3857'})).toThrow();});
