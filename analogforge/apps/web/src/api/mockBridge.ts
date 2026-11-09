/** Development transport for the Python renderer; imported exclusively by the explicit MSW preview. */
import { bypass } from 'msw';
export async function renderMockExport(bundle:Record<string,unknown>,format:string):Promise<Response> {
 const response=await fetch(bypass('/__mock/render-passport',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({bundle,format})}));
 if(!response.ok)throw new Error(`Mock renderer bridge failed: ${await response.text()}`);
 return response;
}
