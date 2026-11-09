import Ajv2020 from 'ajv/dist/2020';
import spec from '../../../../contracts/openapi.bundled.json';
const validator=new Ajv2020({strict:false,allErrors:true,validateFormats:false});validator.addSchema(spec,'contract');
const requests=Object.entries(spec.paths).flatMap(([path,methods])=>{
 const post=(methods as {post?:{requestBody?:{content:Record<string,{schema:unknown}>}}}).post;
 return post?.requestBody?[{path,match:new RegExp('^'+path.replace(/\{[^}]+\}/g,'[^/]+')+'$'),validate:validator.compile({$ref:'contract#/paths/'+path.replace(/~/g,'~0').replace(/\//g,'~1')+'/post/requestBody/content/application~1json/schema'})}]:[];
});
export function validateMutation(path:string,input:unknown):{valid:boolean;errors:unknown} {const request=requests.find(item=>item.match.test(path));if(!request)return {valid:false,errors:['No frozen request schema']};return {valid:Boolean(request.validate(input)),errors:request.validate.errors};}
