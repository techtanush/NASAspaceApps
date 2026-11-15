import Ajv2020 from 'ajv/dist/2020.js';
import schema from './globeCatalog.schema.json';
import { GLOBE_ASSETS, type GlobeAsset, type GlobeBody } from '../maps/globeAssets';
// Planning-v1's negated path pattern also rejects null under JSON Schema.
// Apply the path prohibition to strings only, preserving the documented nullable relief.
const consumerSchema = structuredClone(schema);
Object.assign(consumerSchema.properties.assets.items.properties.relief_path.not, {type:'string'});
const validate = new Ajv2020({ strict: false, allErrors: true }).compile(consumerSchema);
interface CatalogAsset {body:GlobeBody;surface_path:string;relief_path:string|null;placeholder:boolean;attribution:string;sha256:string;bytes:number;width:number;height:number;relief_sha256:string|null;relief_bytes:number|null;source_product:string;source_uri:string;usage_terms:string}
export function parseGlobeCatalog(value: unknown): CatalogAsset[] {
  if (!validate(value)) throw new Error('Unsupported imagery catalog');
  const assets = (value as {assets:CatalogAsset[]}).assets;
  for (const asset of assets) {
    if (asset.width !== asset.height * 2 || asset.bytes > 32 * 1024 * 1024 || (asset.relief_bytes ?? 0) > 32 * 1024 * 1024) throw new Error('Imagery dimensions or resource budget invalid');
    for (const path of [asset.surface_path, asset.relief_path]) if (path && (!/^globe\/deliveries\/[A-Za-z0-9_./-]+$/.test(path) || path.split('/').some(part => !part || part === '.' || part === '..'))) throw new Error('Unsafe imagery path');
  }
  return assets;
}
async function verifiedImage(path:string, hash:string, bytes:number, signal:AbortSignal):Promise<string> {
  const response = await fetch(`${import.meta.env.BASE_URL}${path}`, {signal, credentials:'same-origin', integrity:`sha256-${btoa(String.fromCharCode(...hash.match(/../g)!.map(byte => parseInt(byte,16))))}`});
  if (!response.ok || (Number(response.headers.get('content-length')) || 0) > 32 * 1024 * 1024) throw new Error('Imagery unavailable');
  const blob = await response.blob(); if (blob.size !== bytes) throw new Error('Imagery byte count mismatch');
  // Browser Subresource Integrity verifies delivery bytes; no scientific manifest is generated here.
  return URL.createObjectURL(blob);
}
/** Optional visual context only. Missing catalog keeps the bundled, labelled fallback. */
export async function loadGlobeCatalog(signal:AbortSignal, remember:(url:string)=>void):Promise<Record<GlobeBody,GlobeAsset>> {
  const response = await fetch(`${import.meta.env.BASE_URL}globe/data/catalog.v1.json`, {signal,credentials:'same-origin'});
  if (!response.ok) return GLOBE_ASSETS;
  const result = {...GLOBE_ASSETS};
  for (const asset of parseGlobeCatalog(await response.json())) {
    try {
      const surface = await verifiedImage(asset.surface_path,asset.sha256,asset.bytes,signal); remember(surface);
      const relief = asset.relief_path ? await verifiedImage(asset.relief_path,asset.relief_sha256!,asset.relief_bytes!,signal) : null; if (relief) remember(relief);
      result[asset.body] = {...GLOBE_ASSETS[asset.body],surface,relief,placeholder:asset.placeholder,attribution:asset.attribution,context:{sourceProduct:asset.source_product,sourceUri:asset.source_uri,usageTerms:asset.usage_terms,width:asset.width,height:asset.height}};
    }catch(error){if(signal.aborted)throw error;/* A failed body retains its labelled fallback; other verified bodies can still load. */}
  }
  return result;
}
