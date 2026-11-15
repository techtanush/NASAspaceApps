import type { components } from '../../generated/schema';

type Contract = components['schemas']['MissionTestContract'];
type Conditions = Pick<Contract, 'assumptions' | 'forbidden_actions'> & {
  requirements: Pick<Contract['requirements'][number], 'id' | 'label' | 'acceptance_note'>[];
};

export function ContractConditions({ contract }: { contract: Conditions }) {
  return <details className="mc-source" data-testid="contract-conditions">
    <summary>Assumptions and test conditions</summary>
    <p>These belong to the proposed contract you are accepting. Review them alongside the benchmark rules above.</p>
    <section className="mc-requirements" aria-label="Contract assumptions and limits">
      <h2>Assumptions and limits</h2>
      {contract.assumptions.length ? <ul>{contract.assumptions.map((value, index) => <li key={index}>{value}</li>)}</ul> : <p>No additional assumptions recorded.</p>}
      <h2>Benchmark interpretation</h2>
      <ul>{contract.requirements.map(requirement => <li key={requirement.id}><strong>{requirement.label}</strong><span>{requirement.acceptance_note || 'No additional interpretation note recorded.'}</span></li>)}</ul>
      {!!contract.forbidden_actions.length && <><h2>Excluded actions</h2><ul>{contract.forbidden_actions.map(value => <li key={value}>{value}</li>)}</ul></>}
    </section>
  </details>;
}
