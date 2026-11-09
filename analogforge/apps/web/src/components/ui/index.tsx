import { Children,cloneElement,isValidElement,useId,useRef,useState,type ReactElement,type ReactNode,type ButtonHTMLAttributes,type InputHTMLAttributes } from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import * as TooltipPrimitive from '@radix-ui/react-tooltip';
import * as PopoverPrimitive from '@radix-ui/react-popover';
import * as SelectPrimitive from '@radix-ui/react-select';
import { Copy, X, ChevronDown, Info } from 'lucide-react';
import type { components } from '../../generated/schema';
import { quantity as formatQuantity } from '../../format/quantity';
import { scaleBand, scaleLinear } from 'd3-scale';

type Status = components['schemas']['QualificationStatus'] | 'PENDING';
const glyphs: Record<Status, string> = {
  PASS: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20ZM7 12l3 3 7-7',
  PARTIAL: 'M12 2a10 10 0 1 0 0 20V2Zm0 0a10 10 0 0 1 0 20',
  FAIL: 'M2 2h20v20H2V2Zm5 5 10 10m0-10L7 17',
  GAP: 'M12 1 23 12 12 23 1 12 12 1ZM7 12h10',
  UNKNOWN: 'M6 2h12l6 10-6 10H6L0 12 6 2Zm3 6a3 3 0 0 1 6 0c0 3-3 2-3 5m0 3v1',
  PENDING: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm0 4v7h5',
};
export function StatusGlyph({ status }: { status: Status }) {
  if(status==='PARTIAL')return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d="M12 2a10 10 0 1 0 0 20V2Z" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="10"/></svg>;
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><path d={glyphs[status]}/></svg>;
}
export function StatusBadge({ status, children }: {status: Status; children?: ReactNode}) {
  return <span className={`status status-${status.toLowerCase()}`} data-status={status} aria-label={`Status: ${children??status}`}><StatusGlyph status={status}/><span>{children ?? status}</span></span>;
}
export function ModeBadge({ mode }: { mode: components['schemas']['RuntimeMode'] }) {
  return <span className="mode-badge" data-testid="mode-badge" data-mode={mode}><svg width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">{mode==='live'?<circle cx="4" cy="4" r="3" fill="currentColor"/>:mode==='replay'?<path d="M4 1 1 4l3 3V1Zm3 0L4 4l3 3V1Z" fill="currentColor"/>:<rect x="1" y="1" width="6" height="6" stroke="currentColor" fill="none"/>}</svg>{mode.toUpperCase()}</span>;
}
export function ResultBadge({outcome}:{outcome:components['schemas']['VerificationOutcome']}) {if(outcome!=='INCONCLUSIVE')return <StatusBadge status={outcome}/>;return <span className="status status-partial" data-status={outcome} aria-label="Status: Inconclusive"><svg width="16" height="16" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5" fill="none" aria-hidden="true"><path d="M12 2 23 22H1L12 2ZM7 16h10"/></svg>INCONCLUSIVE</span>;}
export function PublicationBadge({publication}:{publication:string}) {return <span className={`status status-${publication==='ALLOWED'?'pass':publication==='BLOCKED'?'fail':publication==='LIMITED'?'partial':'unknown'}`} data-testid="assurance-badge" data-publication={publication}><svg width="16" height="16" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5" fill="none" aria-hidden="true"><path d={publication==='ALLOWED'?'M12 2 22 6v6c0 5-10 10-10 10S2 17 2 12V6l10-4Zm-5 10 3 3 7-7':publication==='BLOCKED'?'M12 2 22 6v6c0 5-10 10-10 10S2 17 2 12V6l10-4Zm-5 6 10 10m0-10L7 18':'M12 2 22 6v6c0 5-10 10-10 10S2 17 2 12V6l10-4Zm0 0v20'}/></svg>{publication==='INCOMPLETE'?'Assurance incomplete':publication}</span>;}
export function Button({ variant = 'secondary', size, className = '',disabledReason, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & {variant?: 'primary'|'secondary'|'danger'|'ghost';size?: 'xl';disabledReason?:string}) {
  const reasonId=useId();const button=<button type="button" className={`button ${className}`} data-variant={variant} data-size={size} {...props} aria-describedby={[props['aria-describedby'],props.disabled&&disabledReason?reasonId:undefined].filter(Boolean).join(' ')||undefined}/>;
  return props.disabled&&disabledReason?<span className="disabled-action">{button}<span id={reasonId} className="helper">{disabledReason}</span></span>:button;
}
export function IconButton({ label, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & {label:string}) {
  return <Button className="icon-button" aria-label={label} title={label} {...props}>{children}</Button>;
}
export function Input(props: InputHTMLAttributes<HTMLInputElement>) { return <input {...props}/>; }
export function NumberInput(props: InputHTMLAttributes<HTMLInputElement>) { return <Input type="number" step="any" {...props}/>; }
export function Select({value,onValueChange,options,label,disabled,...props}:{value:string;onValueChange:(value:string)=>void;options:{value:string;label:string;disabled?:boolean}[];label:string;disabled?:boolean;'data-testid'?:string}) { return <SelectPrimitive.Root value={value} onValueChange={onValueChange} disabled={disabled}><SelectPrimitive.Trigger className="select-trigger" aria-label={label} {...props}><SelectPrimitive.Value/><SelectPrimitive.Icon><ChevronDown size={16}/></SelectPrimitive.Icon></SelectPrimitive.Trigger><SelectPrimitive.Portal><SelectPrimitive.Content className="select-content" position="popper"><SelectPrimitive.Viewport>{options.map(option=><SelectPrimitive.Item className="select-option" key={option.value} value={option.value} disabled={option.disabled} data-value={option.value}><SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText></SelectPrimitive.Item>)}</SelectPrimitive.Viewport></SelectPrimitive.Content></SelectPrimitive.Portal></SelectPrimitive.Root>; }
export function FormField({ label, children, hint, error }: {label:string;children:ReactNode;hint?:string;error?:string}) {
  const id=useId();let labelled=false;const controls=Children.map(children,child=>{if(labelled||!isValidElement(child))return child;labelled=true;return cloneElement(child as ReactElement<{id?:string;'aria-describedby'?:string;'aria-invalid'?:boolean}>,{id, 'aria-describedby':error?`${id}-error`:hint?`${id}-hint`:undefined,'aria-invalid':error?true:undefined});});
  return <div className="form-field"><label className="field-label" htmlFor={id}>{label}</label>{controls}{hint && <span className="helper" id={`${id}-hint`}>{hint}</span>}{error && <span role="alert" className="field-error" id={`${id}-error`}>{error}</span>}</div>;
}
export function Segmented<T extends string>({label, options, value, onChange}:{label:string;options:readonly T[];value:T;onChange:(value:T)=>void}) {
  return <div className="segmented" role="group" aria-label={label}>{options.map(option => <Button key={option} aria-pressed={value===option} onClick={()=>onChange(option)}>{option}</Button>)}</div>;
}
export function Table({caption, children, className=''}:{caption:string;children:ReactNode;className?:string}) {
  return <div className={`table-scroll ${className}`} tabIndex={0} role="region" aria-label={caption}><table><caption>{caption}</caption>{children}</table></div>;
}
export function Banner({title,children,status='PENDING'}:{title:string;children?:ReactNode;status?:Status}) {
  return <section className={`banner status-edge-${status.toLowerCase()}`}><strong>{title}</strong>{children && <div>{children}</div>}</section>;
}
const reasons: Record<string,string> = {
  NO_COVERAGE:'No data covers this window for this dimension.',NOT_REQUESTED:'This dimension is not part of the accepted contract.',
  AWAITING_DATASETS:'Scenario unavailable until datasets are installed.',SEARCH_LIMIT:'Search limit reached. This is not proof that no route exists.',
  ROUTE_NOT_VERIFIED:'Depends on a verified route. Run PROVE IT.',ROVER_REQUIRED:'Rover verification unavailable: no rover profile selected.',
  NO_CANDIDATES:'No candidates are available in the selected search bounds.',NO_PORTFOLIO:'No candidate covers any remaining requirement.',
  PENDING:'This evidence has not committed yet.',NO_MISSIONS:'Create a mission to define the test and target region.',
};
export function EmptyState({reason,children}:{reason:string;children?:ReactNode}) {
  return <div className="empty-state" data-testid="empty-state" data-reason={reason}><Info size={16} aria-hidden="true"/><div><strong>{reason.replaceAll('_',' ')}</strong><p>{children ?? reasons[reason] ?? 'No committed records are available for this view.'}</p></div></div>;
}
export function ErrorPanel({error,onRetry}:{error:unknown;onRetry?:()=>void}) {
  const data = error as {code?:string;message?:string;request_id?:string;details?:Record<string,unknown>};
  const dependency = typeof data?.details?.dependency === 'string' ? data.details.dependency : undefined;
  return <div className="error-panel" role="alert" data-testid="error-panel" data-error-code={data?.code ?? 'TRANSPORT_ERROR'}><strong>{data?.code ?? 'TRANSPORT_ERROR'}</strong><p>{data?.message ?? 'The request could not complete. Your entered values are retained.'}</p>{data?.request_id && <p className="mono">Request {data.request_id}</p>}{dependency && <p data-testid="remediation-hint" data-dependency={dependency}>Configure {dependency} on the server, then retry. No fallback run was created.</p>}{onRetry && <Button onClick={onRetry}>Retry request</Button>}</div>;
}
export function Skeleton({label='Retrieving committed evidence'}:{label?:string}) { return <div className="skeleton" role="status" aria-label={label}>{label}</div>; }
export function Quantity({value,unit,support}:{value:number|null|undefined;unit?:string;support?:number|null}) {
  if (value == null || !Number.isFinite(value)) return <span data-testid="unknown-value" className="unknown">Unknown</span>;
  const formatted=formatQuantity(value,unit);const [number,label]=formatted.split('\u00a0');
  return <span className="quantity" data-numeric><span>{number}</span>{label && <span className="unit">{'\u00a0'}{label}</span>}{support != null && <small className="support">{formatQuantity(support,'m')} support</small>}</span>;
}
export function Timestamp({value}:{value:string}) { return <time className="mono" dateTime={value} title={value}>{value.replace('T',' ').replace('.000','')}</time>; }
export function Mono({children}:{children:ReactNode}) { return <span className="mono">{children}</span>; }
export function Hash({value,testid,format}:{value:string;testid?:string;format?:string}) { return <code className="hash" data-testid={testid} data-format={format}>{value}</code>; }
export function CopyHash({value,kind='evidence',testid,format}:{value:string;kind?:string;testid?:string;format?:string}) {
  const [copied,setCopied] = useState(false);const [unavailable,setUnavailable]=useState(false);
  const copy=async()=>{try{if(!navigator.clipboard)throw new Error('Clipboard unavailable');await navigator.clipboard.writeText(value);setCopied(true);setUnavailable(false);}catch{setUnavailable(true);}};
  return <span className="hash-group"><Hash value={value} testid={testid} format={format}/><IconButton label={copied?'Hash copied':'Copy full hash'} data-testid="copy-hash" data-hash-kind={kind} onClick={()=>{void copy();}}><Copy size={16}/></IconButton><span className={unavailable?'helper':'sr-only'} role="status">{unavailable?'Clipboard unavailable. Select and copy the full digest.':copied?'Hash copied':''}</span></span>;
}
export function RevisionBadge({label,revision}:{label:string;revision:number|string}) { return <span className="revision-badge">{label} rev <Mono>{revision}</Mono></span>; }
export function ConnectionIndicator({connection}:{connection:string}) { return <span className="connection" data-testid="connection-indicator" data-connection={connection}><span className="connection-dot" aria-hidden="true"/>{connection==='paused'?'Updates paused':connection}</span>; }
export function Dialog({title,description,trigger,children,open,onOpenChange,testid}:{title:string;description?:string;trigger?:ReactNode;children:ReactNode;open?:boolean;onOpenChange?:(open:boolean)=>void;testid?:string}) {
  const opener=useRef<HTMLElement|null>(null);const wasOpen=useRef(false);if(open&&!wasOpen.current)opener.current=document.activeElement as HTMLElement|null;wasOpen.current=!!open;
  return <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>{trigger && <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>}<DialogPrimitive.Portal><DialogPrimitive.Overlay className="overlay"/><DialogPrimitive.Content onCloseAutoFocus={event=>{if(!trigger&&opener.current){event.preventDefault();opener.current.focus();}}} className="dialog" aria-describedby={description?undefined:undefined} data-testid={testid}><div className="section-heading"><DialogPrimitive.Title>{title}</DialogPrimitive.Title><DialogPrimitive.Close asChild><IconButton label="Close dialog"><X size={16}/></IconButton></DialogPrimitive.Close></div><DialogPrimitive.Description className={description?'helper':'sr-only'}>{description ?? title}</DialogPrimitive.Description>{children}</DialogPrimitive.Content></DialogPrimitive.Portal></DialogPrimitive.Root>;
}
export function Drawer({title,children,open,onOpenChange,testid,side='right'}:{title:string;children:ReactNode;open:boolean;onOpenChange:(open:boolean)=>void;testid?:string;side?:'right'|'bottom'}) {
  const opener=useRef<HTMLElement|null>(null);const closingFromOutside=useRef(false);const wasOpen=useRef(false);if(open&&!wasOpen.current)opener.current=document.activeElement as HTMLElement|null;wasOpen.current=open;
  return <DialogPrimitive.Root modal={false} open={open} onOpenChange={onOpenChange}><DialogPrimitive.Portal><DialogPrimitive.Content className={`drawer drawer-${side}`} data-testid={testid} onCloseAutoFocus={event=>{event.preventDefault();if(closingFromOutside.current){closingFromOutside.current=false;return;}opener.current?.focus();}} onFocusOutside={()=>{closingFromOutside.current=true;onOpenChange(false);}} onInteractOutside={event=>event.preventDefault()}><div className="section-heading"><DialogPrimitive.Title>{title}</DialogPrimitive.Title><DialogPrimitive.Close asChild><IconButton label="Close drawer"><X size={16}/></IconButton></DialogPrimitive.Close></div><DialogPrimitive.Description className="helper">Committed evidence and provenance for the current investigation.</DialogPrimitive.Description>{children}</DialogPrimitive.Content></DialogPrimitive.Portal></DialogPrimitive.Root>;
}
export function Tooltip({label,children}:{label:string;children:ReactNode}) { return <TooltipPrimitive.Provider><TooltipPrimitive.Root><TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger><TooltipPrimitive.Portal><TooltipPrimitive.Content className="popover" data-overlay>{label}</TooltipPrimitive.Content></TooltipPrimitive.Portal></TooltipPrimitive.Root></TooltipPrimitive.Provider>; }
export function Popover({title,trigger,children}:{title:string;trigger:ReactNode;children:ReactNode}) { return <PopoverPrimitive.Root><PopoverPrimitive.Trigger asChild>{trigger}</PopoverPrimitive.Trigger><PopoverPrimitive.Portal><PopoverPrimitive.Content className="popover" data-overlay aria-label={title}>{children}<PopoverPrimitive.Close asChild><Button>Close</Button></PopoverPrimitive.Close></PopoverPrimitive.Content></PopoverPrimitive.Portal></PopoverPrimitive.Root>; }
export function Tabs({label,items,value,onChange}:{label:string;items:string[];value:string;onChange:(value:string)=>void}) { return <div className="tabs" role="group" aria-label={label}>{items.map(item=><Button key={item} aria-pressed={value===item} onClick={()=>onChange(item)}>{item}</Button>)}</div>; }
export function Stepper({steps,current}:{steps:string[];current:number}) { return <ol className="stepper" aria-label="Investigation steps">{steps.map((step,i)=><li key={step} aria-current={i===current?'step':undefined}><span className="step-number">{i+1}</span>{step}</li>)}</ol>; }
export function Timeline({children}:{children:ReactNode}) { return <ol className="timeline">{children}</ol>; }
export function SortHeader({children,ascending,onClick}:{children:ReactNode;ascending:boolean;onClick:()=>void}) { return <Button onClick={onClick} aria-label={`Sort ${String(children)} ${ascending?'descending':'ascending'}`}>{children}<ChevronDown size={16} aria-hidden="true"/></Button>; }
export function MatrixCell({status,children}:{status:Status;children?:ReactNode}) { return <div className="matrix-cell"><StatusBadge status={status}/>{children}</div>; }
export function FileDrop(props:InputHTMLAttributes<HTMLInputElement>) { return <Input type="file" accept="application/json,.json" {...props}/>; }
export function Toast({children}:{children:ReactNode}) { return <div className="toast" role="status">{children}</div>; }
export function DataTableToggle({value,onChange}:{value:string;onChange:(value:string)=>void}) { return <Tabs label="Chart display" items={['Chart','Table']} value={value} onChange={onChange}/>; }
export function KbdHint({children}:{children:ReactNode}) { return <kbd>{children}</kbd>; }
export function VisuallyHidden({children}:{children:ReactNode}) { return <span className="sr-only">{children}</span>; }
export function ScaleBar({text}:{text:string}) { return <div className="scale-bar mono">{text}</div>; }
export function CoordinateReadout({text}:{text:string}) { return <div className="coordinate-readout mono">{text}</div>; }
export function Attribution({children}:{children:ReactNode}) { return <small className="attribution">{children}</small>; }
export function Legend({items}:{items:{label:string}[]}) { return <ul className="legend" aria-label="Layer legend">{items.map(item=><li key={item.label}>{item.label}</li>)}</ul>; }
export function LayerPanel({layers,onChange}:{layers:{id:string;name:string;visible:boolean}[];onChange:(id:string,visible:boolean)=>void}) { return <fieldset className="layer-panel"><legend>Display layers</legend>{layers.map(layer=><label key={layer.id}><input type="checkbox" checked={layer.visible} onChange={event=>onChange(layer.id,event.target.checked)}/>{layer.name}</label>)}</fieldset>; }
export function Chart({title,values,unit,kind='histogram'}:{title:string;values:{label:string;value:number|null}[];unit:string;kind?:'histogram'|'line'|'bar'}) {
  const [view,setView]=useState('Chart');
  // Display-only scales convert received values into SVG coordinates; they do not compute measurements.
  const maximum=Math.max(1,...values.map(item=>item.value??0));const y=scaleLinear().domain([0,maximum]).range([184,24]);const x=scaleBand<string>().domain(values.map(item=>item.label)).range([56,464]).paddingInner(0.12);
  return <section className="chart"><div className="section-heading"><h3>{title}</h3><DataTableToggle value={view} onChange={setView}/></div><p className="helper">{values.length} supplied bins · {unit}. Exact values are retained in the data table.</p>{view==='Chart' && <svg viewBox="0 0 480 240" role="img" aria-label={`${title}; values available in the adjacent table`}>{y.ticks(4).map(tick=><g key={tick}><line x1="56" x2="464" y1={y(tick)} y2={y(tick)} stroke="var(--border-subtle)"/><text x="48" y={y(tick)+4} textAnchor="end">{tick}</text></g>)}{kind==='line'&&<path d={values.filter(item=>item.value!==null).map((item,index)=>`${index?'L':'M'} ${(x(item.label)??56)+x.bandwidth()/2} ${y(item.value!)}`).join(' ')} fill="none" stroke="var(--accent)" strokeWidth="2"/>}{values.map(item=><g key={item.label} tabIndex={0} role="img" aria-label={`${item.label}: ${item.value??'Unknown'} ${unit}`}><title>{item.label}: {item.value??'Unknown'} {unit}</title>{item.value!==null&&(kind==='line'?<circle cx={(x(item.label)??56)+x.bandwidth()/2} cy={y(item.value)} r="4" fill="var(--accent)"/>:<rect x={x(item.label)} y={y(item.value)} width={x.bandwidth()} height={184-y(item.value)} fill="var(--accent)"/>)}<text x={(x(item.label)??56)+x.bandwidth()/2} y="208" textAnchor="middle" fontSize="12">{item.label}</text></g>)}<text x="56" y="232">{unit}</text></svg>}<Table caption={`${title} data (${unit})`}><thead><tr><th scope="col">Bin</th><th scope="col" data-numeric>Value ({unit})</th></tr></thead><tbody>{values.map(item=><tr key={item.label}><th scope="row">{item.label}</th><td data-numeric><Quantity value={item.value}/></td></tr>)}</tbody></Table></section>;
}
