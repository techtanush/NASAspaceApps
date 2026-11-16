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
import './styles/mission-control.css';
import './styles/operator-context.css';
import './styles/run-overview.css';
import './styles/landing.css';
const container=document.getElementById('root');
const appRoot=container?createRoot(container):null;
appRoot?.render(<main className="workspace-main workspace-bootstrap" role="status" aria-live="polite"><section className="empty-state"><p className="context-label">AnalogForge</p><h1>Preparing your investigation</h1><p>Opening your workspace. No account is needed for public exploration.</p></section></main>);
async function boot() {
  if (import.meta.env.VITE_API_MOCK === '1') {
    const { startMock } = await import('./mock/server');
    await startMock();
  }
  // Local fonts use CSS font-display:swap. Their download must never block the workspace.
  const { default: App } = await import('./app/App');
  if (!appRoot) throw new Error('Application root is missing');
  if (location.pathname === '/') {
    // Reading the introduction never allocates a visitor workspace or waits for
    // its service. A returning visitor can still recover their private history.
    appRoot.render(<App/>);
    void loadSession(false).then(session => {
      appRoot.render(<App workspaceId={session.workspaceId} session={{workspaceId:session.workspaceId,role:session.role,authMode:session.authMode}}/>);
    }).catch(() => { /* The public introduction remains usable when session checks fail. */ });
    return;
  }
  const session=await loadSession();
  appRoot.render(<App workspaceId={session.workspaceId} session={{workspaceId:session.workspaceId,role:session.role,authMode:session.authMode}}/>);
}
void boot().catch((error: unknown) => {
  if(appRoot){const detail=error as {code?:string;message?:string};appRoot.render(<main className="workspace-main"><section className="error-panel" role="alert" data-testid="error-panel" data-error-code={detail.code||'STARTUP_FAILED'}><h1>Workspace unavailable</h1><p>{detail.message||'The investigation workspace could not be opened.'}</p><p>Check the connection, then retry.</p><button onClick={()=>location.reload()}>Retry workspace</button></section></main>);}
});
