import { describe, expect, it,vi } from 'vitest';
import { render, screen,waitFor } from '@testing-library/react';
import {useState} from 'react';
import userEvent from '@testing-library/user-event';
import { StatusBadge, Quantity, Dialog, Drawer, Button, Select } from '../components/ui';

describe('FE-002, FE-009: truthful presentation', () => {
  it('distinguishes missing measurements from a measured zero', () => {
    render(<><Quantity value={null} unit="m"/><Quantity value={0} unit="m"/></>);
    expect(screen.getByTestId('unknown-value')).toHaveTextContent('Unknown');
    expect(screen.getByText('0')).toBeVisible();
  });
  it('preserves six distinct states without relying on colour', () => {
    const states = ['PASS', 'PARTIAL', 'FAIL', 'GAP', 'UNKNOWN', 'PENDING'] as const;
    const { container } = render(<>{states.map(status => <StatusBadge key={status} status={status}/>)}</>);
    const paths = [...container.querySelectorAll('svg')].map(svg => svg.innerHTML);
    expect(new Set(paths).size).toBe(6);
    states.forEach(status => expect(screen.getByText(status)).toBeVisible());
  });
  it('dialog supports keyboard close and returns focus to its trigger', async () => {
    const user = userEvent.setup();
    render(<Dialog title="Review contract" trigger={<Button>Review</Button>}><p>Frozen revision</p></Dialog>);
    await user.click(screen.getByText('Review'));
    expect(screen.getByRole('dialog', {name:'Review contract'})).toBeVisible();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByText('Review')).toHaveFocus();
  });
  it('nonmodal evidence closes when focus moves outside, preserving the new keyboard target',async()=>{
    function Harness(){const [open,setOpen]=useState(false);return <><Button onClick={()=>setOpen(true)}>Inspect evidence</Button><Button>Continue working</Button><Drawer title="Evidence scope" open={open} onOpenChange={setOpen}><p>Frozen receipt.</p></Drawer></>;}
    const user=userEvent.setup();render(<Harness/>);await user.click(screen.getByText('Inspect evidence'));expect(screen.getByRole('dialog',{name:'Evidence scope'})).toBeVisible();screen.getByText('Continue working').focus();await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument());expect(screen.getByText('Continue working')).toHaveFocus();await user.click(screen.getByText('Inspect evidence'));await user.keyboard('{Escape}');expect(screen.getByText('Inspect evidence')).toHaveFocus();
  });
});

it('retains an explicit scenario while asynchronously loaded choices replace the placeholder',async()=>{
 const changed=vi.fn();
 const {rerender}=render(<Select label="Scenario" value="live-hackathon-v1" onValueChange={changed} options={[{value:'loading',label:'Retrieving scenarios',disabled:true}]}/>);
 rerender(<Select label="Scenario" value="live-hackathon-v1" onValueChange={changed} options={[{value:'synthetic-mars-mobility-v1',label:'Mars mobility'},{value:'live-hackathon-v1',label:'NASA dataset slot',disabled:true}]}/>);
 await waitFor(()=>expect(screen.getByRole('combobox',{name:'Scenario'})).toHaveTextContent('NASA dataset slot'));
 expect(changed).not.toHaveBeenCalled();
});
