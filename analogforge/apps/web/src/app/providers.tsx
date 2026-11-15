import { useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WorkspaceProvider, type WorkspaceSession } from './WorkspaceContext';
export function Providers({children,workspaceId,session}:{children:ReactNode;workspaceId?:string;session?:WorkspaceSession}) { const [client]=useState(()=>new QueryClient({defaultOptions:{queries:{retry:false,staleTime:300,refetchOnWindowFocus:true}}}));return <QueryClientProvider client={client}><WorkspaceProvider workspaceId={workspaceId} session={session}>{children}</WorkspaceProvider></QueryClientProvider>; }
