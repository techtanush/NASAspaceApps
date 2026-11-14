import { createContext, useContext, type ReactNode } from 'react';
const WorkspaceContext = createContext('00000000-0000-4000-8000-000000000001');
export function WorkspaceProvider({children,workspaceId='00000000-0000-4000-8000-000000000001'}:{children:ReactNode;workspaceId?:string}) { return <WorkspaceContext.Provider value={workspaceId}>{children}</WorkspaceContext.Provider>; }
export function useWorkspace() { return useContext(WorkspaceContext); }
