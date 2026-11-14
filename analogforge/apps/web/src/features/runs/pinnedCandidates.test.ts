import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import type { Schema } from './RunContext';
import { fetchPinnedCandidates, orderCandidates } from './pinnedCandidates';

vi.mock('../../api/client', () => ({ api: { get: vi.fn() } }));
const workspace = crypto.randomUUID();
const run = crypto.randomUUID();
const row = (id: string, extra = {}) => ({ id, workspace_id: workspace, run_id: run, ...extra }) as Schema['EarthAnalogCandidate'];
beforeEach(() => vi.resetAllMocks());

describe('pinned candidate projection', () => {
  it('follows the science shortlist across chronological collection pages', async () => {
    const ids = Array.from({ length: 225 }, () => crypto.randomUUID());
    const records = [...ids].reverse().map(id => row(id));
    vi.mocked(api.get).mockImplementation(async path => {
      const start = Number(new URL(path, 'http://localhost').searchParams.get('cursor') || 0);
      return { items: records.slice(start, start + 100), next_cursor: start + 100 < records.length ? String(start + 100) : null };
    });
    const result = await fetchPinnedCandidates(workspace, run, ids);
    expect(result.items.map(value => value.id)).toEqual(ids);
    expect(api.get).toHaveBeenCalledTimes(3);
  });

  it('preserves appended nominations and stable unknown order without sorting by qualification or origin', () => {
    const records = [row('unknown-b'), row('nominated', { origin: 'USER_SUPPLIED' }), row('second'), row('unknown-a'), row('first')];
    const original = [...records];
    expect(orderCandidates(records, ['first', 'second', 'nominated']).map(value => value.id))
      .toEqual(['first', 'second', 'nominated', 'unknown-b', 'unknown-a']);
    expect(orderCandidates(records, [])).toEqual(original);
    expect(records).toEqual(original);
  });

  it.each(['workspace_id', 'run_id'])('rejects a foreign %s before displaying it', async key => {
    const id = crypto.randomUUID();
    vi.mocked(api.get).mockResolvedValue({ items: [row(id, { [key]: crypto.randomUUID() })], next_cursor: null });
    await expect(fetchPinnedCandidates(workspace, run, [id])).rejects.toThrow('pinned run');
  });

  it('fails explicitly when a pinned candidate is absent', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [row('other')], next_cursor: null });
    await expect(fetchPinnedCandidates(workspace, run, ['missing'])).rejects.toThrow('incomplete');
  });

  it('terminates a broken cursor loop', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], next_cursor: 'repeated' });
    await expect(fetchPinnedCandidates(workspace, run, ['missing'])).rejects.toThrow('incomplete');
    expect(api.get).toHaveBeenCalledTimes(2);
  });
});
