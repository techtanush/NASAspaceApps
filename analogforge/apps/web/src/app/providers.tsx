import { useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WorkspaceProvider } from './WorkspaceContext';
export function Providers({children,workspaceId}:{children:ReactNode;workspaceId?:string}) { const [client]=useState(()=>new QueryClient({defaultOptions:{queries:{retry:false,staleTime:300,refetchOnWindowFocus:true}}}));return <QueryClientProvider client={client}><WorkspaceProvider workspaceId={workspaceId}>{children}</WorkspaceProvider></QueryClientProvider>; }
