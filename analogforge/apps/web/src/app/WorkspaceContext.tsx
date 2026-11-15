import { createContext, useContext, type ReactNode } from 'react';
import type { Session } from '../api/session';
export type WorkspaceSession=Pick<Session,'workspaceId'|'role'|'authMode'>;
const WorkspaceContext = createContext('00000000-0000-4000-8000-000000000001');
const SessionContext=createContext<WorkspaceSession|undefined>(undefined);
export function WorkspaceProvider({children,workspaceId='00000000-0000-4000-8000-000000000001',session}:{children:ReactNode;workspaceId?:string;session?:WorkspaceSession}) { return <WorkspaceContext.Provider value={workspaceId}><SessionContext.Provider value={session?.workspaceId===workspaceId?session:undefined}>{children}</SessionContext.Provider></WorkspaceContext.Provider>; }
export function useWorkspace() { return useContext(WorkspaceContext); }
export function useWorkspaceSession(){return useContext(SessionContext);}
