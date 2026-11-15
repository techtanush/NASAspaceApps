import {describe,it,expect} from 'vitest';
import {parseGlobeCatalog} from './globeCatalog';
const asset={body:'MARS',surface_path:'globe/deliveries/v1/mars.jpg',relief_path:null,placeholder:false,attribution:'Source credit',source_uri:'source record',source_product:'global mosaic',usage_terms:'public domain',sha256:'a'.repeat(64),bytes:200,width:4096,height:2048,longitude_convention:'NEG180_180',north_up:true,purpose:'VISUAL_CONTEXT_ONLY',relief_sha256:null,relief_bytes:null};
describe('optional visual catalog boundary',()=>{
 it('accepts versioned same-origin imagery and retains its placeholder declaration',()=>{expect(parseGlobeCatalog({schema_version:'1.0',assets:[asset]})[0]?.placeholder).toBe(false);});
 it('rejects foreign paths, traversal, duplicate bodies and unknown schema versions',()=>{for(const surface_path of ['https://example.com/a.jpg','globe/deliveries/../secret','globe/deliveries/./a.jpg'])expect(()=>parseGlobeCatalog({schema_version:'1.0',assets:[{...asset,surface_path}]})).toThrow();expect(()=>parseGlobeCatalog({schema_version:'2.0',assets:[asset]})).toThrow();expect(()=>parseGlobeCatalog({schema_version:'1.0',assets:[asset,asset]})).toThrow();});
 it('rejects wrong aspect ratios and excessive resource declarations',()=>{expect(()=>parseGlobeCatalog({schema_version:'1.0',assets:[{...asset,width:1024}]})).toThrow();expect(()=>parseGlobeCatalog({schema_version:'1.0',assets:[{...asset,bytes:40*1024*1024}]})).toThrow();});
});
