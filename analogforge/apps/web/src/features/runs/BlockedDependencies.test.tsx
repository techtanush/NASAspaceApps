import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { BlockedDependencies } from './RunShell';

describe('BlockedDependencies', () => {
  it('offers a retry for a retryable dependency', async () => {
    const onRetry = vi.fn();
    render(<BlockedDependencies dependencies={['NO_COVERAGE']} pending={false} onRetry={onRetry} />);
    await userEvent.click(screen.getByTestId('btn-retry-dependency'));
    expect(onRetry).toHaveBeenCalledWith('NO_COVERAGE');
  });

  it('explains a refused scientific claim and offers no retry', () => {
    const { container } = render(<BlockedDependencies dependencies={['SCIENTIFIC_CLAIM_REJECTED']} pending={false} onRetry={vi.fn()} />);
    expect(screen.queryByTestId('btn-retry-dependency')).toBeNull();
    expect(container.querySelector('[data-stop-reason=SCIENTIFIC_CLAIM_REJECTED]')).not.toBeNull();
    expect(screen.getByText(/scientific audit refused an unsupported claim/)).toBeTruthy();
    expect(screen.getByText(/No passport was published/)).toBeTruthy();
  });
});
