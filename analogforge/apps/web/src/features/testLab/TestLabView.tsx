import {useLayoutEffect,useState} from 'react';
import {createPortal} from 'react-dom';
import {SquarePlay} from 'lucide-react';
import { Button,EmptyState,Quantity,Table } from '../../components/ui';
import { useRun } from '../runs/RunContext';
import { Attempts,describeRunResults,useRunResults } from './Attempts';
export function TestLabView(){
 const {snapshot,contract,candidates,action,pending}=useRun();const results=useRunResults();
 const [actionMount,setActionMount]=useState<HTMLElement|null>(null);useLayoutEffect(()=>setActionMount(document.getElementById('run-primary-action')),[]);
 const terminal=['COMPLETED','CANCELLED','FAILED'].includes(snapshot.state);
 const allowed=snapshot.pending_review?.allowed_actions.includes('PROVE_IT')??false;
 const enabled=!terminal&&!!snapshot.rover_revision_id&&!!snapshot.selected_candidate_id&&allowed&&!pending;
 const reason=!snapshot.rover_revision_id?'Rover verification unavailable: no rover profile selected.':terminal?`Run ${snapshot.state.toLowerCase()}. Further PROVE IT actions are unavailable; committed attempts remain below.`:!snapshot.selected_candidate_id?'Select a candidate before starting modeled verification.':!allowed?'Waiting for committed evidence and an allowed PROVE IT action.':'Submitting the selected test.';
 const prove=<Button variant={terminal?'secondary':'primary'} size={terminal?undefined:'xl'} data-testid="btn-prove-it" data-enabled={enabled} disabled={!enabled} aria-describedby={!enabled?'prove-disabled':undefined} onClick={()=>{if(snapshot.selected_candidate_id)void action({action_type:'PROVE_IT',expected_revision:snapshot.revision,payload:{candidate_id:snapshot.selected_candidate_id}});}}><SquarePlay size={16} strokeWidth={1.5}/>PROVE IT</Button>;
 return <section className="page-stack" data-testid="test-lab"><div className="page-heading"><div><h1 tabIndex={-1}>Test lab</h1><p>Modeled terrain-feasibility verification — not physical rover execution.</p><p className="test-result-headline" data-testid="test-result-headline" role="status">{results.isError?'Committed modeled results could not be retrieved.':snapshot.test_result_ids.length&&results.isPending?'Retrieving committed modeled results.':describeRunResults(results.data??[])}</p></div></div>
 <section className="panel" data-region="experiment" data-testid="benchmark-preview"><div className="section-heading"><h2>Accepted experiment</h2><span className="revision-badge">Contract rev {contract.revision}</span></div><p>Candidate: {candidates.find(c=>c.id===snapshot.selected_candidate_id)?.name??'Select a candidate'}</p>
 <details className="accepted-benchmarks" open={!terminal}><summary>Accepted benchmark requirements ({contract.requirements.filter(req=>req.mandatory).length})</summary><Table caption="Frozen benchmark preview"><thead><tr><th scope="col">Requirement</th><th scope="col">Rule</th><th scope="col">Accepted value</th><th scope="col">Route</th></tr></thead><tbody>{contract.requirements.filter(req=>req.mandatory).map(req=><tr key={req.id}><th scope="row">{req.id}</th><td>{req.operator} · {req.observable}</td><td data-numeric><Quantity value={req.lower??req.upper} unit={req.unit}/></td><td>{snapshot.test_ids.length?'Committed test artifact':'To be designed'}</td></tr>)}</tbody></Table></details>
 {actionMount?createPortal(prove,actionMount):prove}{!enabled&&<p id="prove-disabled" data-testid="prove-it-disabled-reason" className="helper">{reason}</p>}
 </section><section className="page-stack"><h2>Immutable attempts</h2>{snapshot.test_ids.length===0?<EmptyState reason="ROUTE_NOT_VERIFIED">No route or attempt has committed. PROVE IT starts test design and modeled verification within the accepted contract.</EmptyState>:<Attempts/>}</section></section>;
}
