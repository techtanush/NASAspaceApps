import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import spec from '../../../../../contracts/openapi.bundled.json';
import type { components } from '../../generated/schema';
const ajv=new Ajv2020({allErrors:true,strict:false});addFormats(ajv);
ajv.addSchema({...spec,$id:'analogforge-openapi'});
const validate=ajv.compile<components['schemas']['RoverInput']>({$ref:'analogforge-openapi#/components/schemas/RoverInput'});
export type RoverValidationIssue={field:string;message:string;rejectedValue?:unknown;instancePath?:string};
export function parseRoverImport(text:string):{ok:true;value:components['schemas']['RoverInput']}|{ok:false;errors:RoverValidationIssue[]}{
  if(text.length>1048576)return {ok:false,errors:[{field:'file',message:'Rover JSON exceeds the 1 MiB import limit.'}]};
  let value:unknown;try{value=JSON.parse(text);}catch{return {ok:false,errors:[{field:'file',message:'Invalid JSON. The existing rover profile was retained.'}]};}
  if(!validate(value))return {ok:false,errors:(validate.errors??[]).map(error=>{const rejectedValue=error.instancePath.split('/').slice(1).reduce<unknown>((current,key)=>{const field=key.replaceAll('~1','/').replaceAll('~0','~');return current!==null&&typeof current==='object'&&Object.hasOwn(current,field)?(current as Record<string,unknown>)[field]:undefined;},value);return {field:error.instancePath.split('/')[1]??'file',message:error.message??'Invalid value',instancePath:error.instancePath,rejectedValue};})};
  return {ok:true,value};
}
