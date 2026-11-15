import { expect, it } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ContractConditions } from './ContractConditions';

it('makes the exact proposed assumptions, exclusions and interpretation available before acceptance', () => {
  const contract = {
    assumptions: ['Declared energy model is ASSUMED, not calibrated.', '<script>untrusted source text</script>'],
    requirements: [{ id: 'operator-specific-rule', label: 'Optional steep terrain', acceptance_note: 'Failure of this optional check alone does not reject a site.' }],
    forbidden_actions: ['NO_PHYSICAL_SUCCESS_CLAIM'],
  };
  const before = JSON.stringify(contract);
  render(<ContractConditions contract={contract}/>);
  const details = screen.getByTestId('contract-conditions');
  expect(details).not.toHaveAttribute('open');
  fireEvent.click(screen.getByText('Assumptions and test conditions', { exact: true }));
  expect(details).toHaveAttribute('open');
  for (const value of [...contract.assumptions, contract.requirements[0]!.acceptance_note, ...contract.forbidden_actions]) expect(screen.getByText(value, { exact: true })).toBeVisible();
  expect(details.querySelector('script')).toBeNull();
  expect(JSON.stringify(contract)).toBe(before);
});
