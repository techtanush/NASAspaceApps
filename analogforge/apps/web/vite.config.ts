import { defineConfig, loadEnv, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { spawn } from 'node:child_process';
import { resolve, relative, sep } from 'node:path';
import { readdirSync, readFileSync } from 'node:fs';
function productionStaticAssets(): Plugin {
 return { name: 'production-static-assets', apply: 'build', generateBundle() {
  const publicRoot=resolve(process.cwd(),'public');
  const visit=(directory:string)=>{for(const entry of readdirSync(directory,{withFileTypes:true})){
   const filename=resolve(directory,entry.name);
   if(entry.isDirectory())visit(filename);
   else if(entry.name!=='mockServiceWorker.js')this.emitFile({type:'asset',fileName:relative(publicRoot,filename).split(sep).join('/'),source:readFileSync(filename)});
  }};visit(publicRoot);
 }};
}
function mockRendererBridge(): Plugin {
 return { name: 'development-passport-renderer', apply: 'serve', configureServer(server) {
  server.middlewares.use('/__mock/render-passport', (request, response) => {
   if(request.method!=='POST'){response.statusCode=405;response.end('POST required');return;}
   const origin=request.headers.origin;
   if(origin){let allowed=false;try{const from=new URL(origin);const destination=new URL(`http://${request.headers.host}`);allowed=from.protocol==='http:'&&['127.0.0.1','localhost'].includes(from.hostname)&&from.port===destination.port;}catch{allowed=false;}if(!allowed){response.statusCode=403;response.end('Preview origin rejected');return;}}
   let body='';request.on('data',(chunk:Buffer)=>{body+=chunk.toString();if(body.length>5*1024*1024)request.destroy(new Error('Preview bundle exceeds 5 MiB'));});
   request.on('end',()=>{
    const root=resolve(process.cwd(),'../..');
    const child=spawn(resolve(root,'.venv/bin/python'),['scripts/ui/mock_render.py'],{cwd:root,stdio:['pipe','pipe','pipe']});
    let output='',error='';child.stdout.on('data',(chunk:Buffer)=>{output+=chunk.toString();});child.stderr.on('data',(chunk:Buffer)=>{error+=chunk.toString();});
    child.on('error',cause=>{response.statusCode=503;response.setHeader('Content-Type','application/json');response.end(JSON.stringify({error:{code:'MOCK_RENDERER_UNAVAILABLE',message:cause.message}}));});
    child.on('close',code=>{
     if(response.writableEnded)return;
     if(code!==0){response.statusCode=422;response.setHeader('Content-Type','application/json');response.end(JSON.stringify({error:{code:'MOCK_BUNDLE_REJECTED',message:error.trim()}}));return;}
     try{
      const data=JSON.parse(output) as {content:string;media_type:string;filename:string;sha256:string;manifest_sha256:string};
      response.statusCode=200;response.setHeader('Content-Type',data.media_type);response.setHeader('Content-Disposition',`attachment; filename="${data.filename}"`);response.setHeader('X-Artifact-SHA256',data.sha256);response.setHeader('X-Manifest-SHA256',data.manifest_sha256);response.setHeader('ETag',`"${data.sha256}"`);response.setHeader('X-Content-Type-Options','nosniff');response.end(Buffer.from(data.content,'base64'));
     }catch(cause){response.statusCode=500;response.end(cause instanceof Error?cause.message:'Invalid renderer output');}
    });
    child.stdin.end(body);
   });
  });
 }};
}
export default defineConfig(({ command, mode }) => {
 const env = loadEnv(mode, process.cwd(), '');
 const mock=env.VITE_API_MOCK==='1'||process.env.VITE_API_MOCK==='1';
 if (command === 'build' && mock) throw new Error('MOCK_BUILD_FORBIDDEN: mock preview cannot be built for production');
 return { publicDir: command==='build' ? false : 'public', plugins: [react(), productionStaticAssets(), ...(mock?[mockRendererBridge()]:[])], server: { strictPort: true, host: '127.0.0.1', port: Number(env.WEB_PORT || 5176), proxy: { '/auth': { target: `http://127.0.0.1:${env.API_PORT || 8003}`, changeOrigin: true }, '/api': { target: `http://127.0.0.1:${env.API_PORT || 8003}`, changeOrigin: true }, '/artifacts': { target: `http://127.0.0.1:${env.API_PORT || 8003}`, changeOrigin: true } } }, build: { sourcemap: false } };
});
