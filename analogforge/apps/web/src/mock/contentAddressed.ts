/** Canonical storage belongs to the simulated backend, never the production UI. */
import { sha256 } from '@noble/hashes/sha2.js';
import { bytesToHex } from '@noble/hashes/utils.js';
export function canonicalMockJson(value:unknown):string {
 if(value===null||typeof value==='boolean'||typeof value==='string')return JSON.stringify(value);
 if(typeof value==='number'){if(!Number.isFinite(value))throw new Error('Non-finite JSON artifact value');return JSON.stringify(value);}
 if(Array.isArray(value))return `[${value.map(canonicalMockJson).join(',')}]`;
 if(typeof value==='object')return `{${Object.keys(value as object).sort().map(key=>`${JSON.stringify(key)}:${canonicalMockJson((value as Record<string,unknown>)[key])}`).join(',')}}`;
 throw new Error('Non-JSON mock artifact value');
}
export function mockArtifactHash(value:unknown):string {return bytesToHex(sha256(new TextEncoder().encode(canonicalMockJson(value))));}
