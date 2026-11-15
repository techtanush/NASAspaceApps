import {describe,it,expect} from 'vitest';
import {parseGlobeCatalog} from './globeCatalog';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
const asset={body:'MARS',surface_path:'globe/deliveries/v1/mars.jpg',relief_path:null,placeholder:false,attribution:'Source credit',source_uri:'source record',source_product:'global mosaic',usage_terms:'public domain',sha256:'a'.repeat(64),bytes:200,width:4096,height:2048,longitude_convention:'NEG180_180',north_up:true,purpose:'VISUAL_CONTEXT_ONLY',relief_sha256:null,relief_bytes:null};
describe('optional visual catalog boundary',()=>{
 it('accepts versioned same-origin imagery and retains its placeholder declaration',()=>{expect(parseGlobeCatalog({schema_version:'1.0',assets:[asset]})[0]?.placeholder).toBe(false);});
 it('rejects foreign paths, traversal, duplicate bodies and unknown schema versions',()=>{for(const surface_path of ['https://example.com/a.jpg','globe/deliveries/../secret','globe/deliveries/./a.jpg'])expect(()=>parseGlobeCatalog({schema_version:'1.0',assets:[{...asset,surface_path}]})).toThrow();expect(()=>parseGlobeCatalog({schema_version:'2.0',assets:[asset]})).toThrow();expect(()=>parseGlobeCatalog({schema_version:'1.0',assets:[asset,asset]})).toThrow();});
 it('rejects wrong aspect ratios and excessive resource declarations',()=>{expect(()=>parseGlobeCatalog({schema_version:'1.0',assets:[{...asset,width:1024}]})).toThrow();expect(()=>parseGlobeCatalog({schema_version:'1.0',assets:[{...asset,bytes:40*1024*1024}]})).toThrow();});
 it('consumes all three real delivered NASA surfaces with matching bytes, digests and no synthetic relief',()=>{const catalog=JSON.parse(readFileSync(resolve('public/globe/data/catalog.v1.json'),'utf8'));const assets=parseGlobeCatalog(catalog);expect(assets.map(item=>item.body)).toEqual(['EARTH','MARS','MOON']);for(const item of assets){expect(item.placeholder).toBe(false);expect(item.relief_path).toBeNull();const bytes=readFileSync(resolve('public',item.surface_path));expect(bytes.byteLength).toBe(item.bytes);expect(createHash('sha256').update(bytes).digest('hex')).toBe(item.sha256);}});
});
