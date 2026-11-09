/** Keep generated verification artifacts out of source control without editing the frozen kit ignore file. */
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'../..');
let filename;
try{filename=execFileSync('git',['rev-parse','--path-format=absolute','--git-path','info/exclude'],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','ignore']}).trim();}catch{process.exit(0);}
let content='';try{content=readFileSync(filename,'utf8');}catch(error){if(error.code!=='ENOENT')throw error;}
const pattern='/analogforge/out/';
if(!content.split(/\r?\n/).includes(pattern)){mkdirSync(dirname(filename),{recursive:true});writeFileSync(filename,content+(content.endsWith('\n')?'':'\n')+pattern+'\n');}
