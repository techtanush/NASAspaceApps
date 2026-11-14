import { createRoot } from 'react-dom/client';
import { loadSession } from './api/session';
import '@fontsource/inter/latin-400.css';
import '@fontsource/inter/latin-500.css';
import '@fontsource/inter/latin-600.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import './styles/tokens.css';
import './styles/reset.css';
import './styles/base.css';
import './styles/layout.css';
import './styles/review-maps.css';
import './styles/review-evidence.css';
import './styles/authoring.css';
import './styles/print.css';
import './styles/polish.css';
import './styles/glass.css';
async function boot() {
  if (import.meta.env.VITE_API_MOCK === '1') {
    const { startMock } = await import('./mock/server');
    await startMock();
  }
  const session=await loadSession();
  await Promise.all([document.fonts.load('14px Inter'), document.fonts.load('13px "IBM Plex Mono"')]);
  const { default: App } = await import('./app/App');
  const root = document.getElementById('root');
  if (!root) throw new Error('Application root is missing');
  createRoot(root).render(<App workspaceId={session.workspaceId}/>);
}
void boot().catch((error: unknown) => {
  const root = document.getElementById('root');
  if(root){const detail=error as {code?:string;message?:string};createRoot(root).render(<main className="workspace-main"><section className="error-panel" role="alert" data-testid="error-panel" data-error-code={detail.code||'STARTUP_FAILED'}><h1>Workspace unavailable</h1><p>{detail.message||'The authenticated workspace could not be retrieved.'}</p><p>Check the backend connection and sign-in session, then retry.</p><button onClick={()=>location.reload()}>Retry workspace</button></section></main>);}
});
