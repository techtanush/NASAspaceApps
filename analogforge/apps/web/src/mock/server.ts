import { setupWorker } from 'msw/browser';
import { handlers,advanceRun } from './handlers';
import { db,loadDatabase,resetDatabase,saveDatabase } from './state';
let timer:ReturnType<typeof setInterval>|undefined;
export const worker=setupWorker(...handlers);
export async function startMock():Promise<void> {
 if(import.meta.env.VITE_API_MOCK!=='1')throw new Error('Mock transport is unavailable outside explicit preview mode');
 await loadDatabase();
 const params=new URLSearchParams(location.search);if(params.has('resetMock')){resetDatabase();saveDatabase();}
 const latency=params.get('mockLatency');if(latency!==null){const value=Number(latency);if(!Number.isFinite(value)||value<0||value>2000)throw new Error('Mock latency must be between 0 and 2000 milliseconds');db.settings.latencyMs=value;saveDatabase();}
 const preview=params.get('mockScenario');if(preview&&['review-proxy','blocked-worker','searchLimit'].includes(preview)){db.settings.previewScenario=preview;saveDatabase();}
 await worker.start({onUnhandledRequest:'bypass',quiet:true,serviceWorker:{url:'/mockServiceWorker.js'}});
 Object.assign(window,{__MSW__:true});
 clearInterval(timer);const speed=Number(new URLSearchParams(location.search).get('mockSpeed')||200);
 timer=setInterval(()=>Object.values(db.runs).forEach(advanceRun),Math.max(20,speed));
}
