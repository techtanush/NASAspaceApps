import { Component, type ReactNode } from 'react';
import { ErrorPanel } from '../components/ui';
export class ErrorBoundary extends Component<{children:ReactNode},{failed:boolean}> { state={failed:false};static getDerivedStateFromError(){return {failed:true};}render(){return this.state.failed?<section className="workspace-main"><h1>View unavailable</h1><ErrorPanel error={{code:'VIEW_FAILED',message:'This view could not render. Reload to retrieve the current server state.'}} onRetry={()=>window.location.reload()}/></section>:this.props.children;} }
