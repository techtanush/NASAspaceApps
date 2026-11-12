import { QueryClient } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import type { Schema } from './RunContext';
import { fetchPinnedQualifications } from './pinnedQualifications';

vi.mock('../../api/client', () => ({ api: { get: vi.fn() } }));
const workspace = crypto.randomUUID();
const run = crypto.randomUUID();
const row = (id: string, extra = {}) => ({ id, workspace_id: workspace, run_id: run, ...extra }) as Schema['QualificationDimension'];
beforeEach(() => vi.resetAllMocks());

describe('current qualification projection', () => {
  it('loads every pinned row even beyond the historical collection page limit', async () => {
    const ids = Array.from({ length: 225 }, () => crypto.randomUUID());
    vi.mocked(api.get).mockImplementation(async path => row(path.split('/').at(-1)!));
    const result = await fetchPinnedQualifications(new QueryClient(), workspace, run, ids);
    expect(result.items.map(value => value.id)).toEqual(ids);
    expect(api.get).toHaveBeenCalledTimes(225);
    expect(vi.mocked(api.get).mock.calls.every(([path]) => !path.includes('?'))).toBe(true);
  });

  it('drops superseded Unknown rows and reuses unchanged immutable records', async () => {
    const common = crypto.randomUUID(), old = crypto.randomUUID(), current = crypto.randomUUID();
    vi.mocked(api.get).mockImplementation(async path => row(path.split('/').at(-1)!, {
      status: path.endsWith(old) ? 'UNKNOWN' : 'PASS',
    }));
    const cache = new QueryClient();
    await fetchPinnedQualifications(cache, workspace, run, [common, old]);
    const next = await fetchPinnedQualifications(cache, workspace, run, [common, current]);
    expect(next.items.map(value => value.id)).toEqual([common, current]);
    expect(next.items.every(value => value.status === 'PASS')).toBe(true);
    expect(api.get).toHaveBeenCalledTimes(3);
  });

  it.each(['workspace_id', 'run_id', 'id'])('rejects a foreign %s before displaying it', async key => {
    const id = crypto.randomUUID();
    vi.mocked(api.get).mockResolvedValue(row(id, { [key]: crypto.randomUUID() }));
    await expect(fetchPinnedQualifications(new QueryClient(), workspace, run, [id])).rejects.toThrow('pinned run');
  });
});
