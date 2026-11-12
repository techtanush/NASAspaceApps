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
  it('finds 225 pinned rows across historical collection pages', async () => {
    const ids = Array.from({ length: 225 }, () => crypto.randomUUID());
    const records = [...Array.from({ length: 100 }, () => row(crypto.randomUUID())), ...ids.map(id => row(id))];
    vi.mocked(api.get).mockImplementation(async path => {
      const start = Number(new URL(path, 'http://localhost').searchParams.get('cursor') || 0);
      return { items: records.slice(start, start + 100), next_cursor: start + 100 < records.length ? String(start + 100) : null };
    });
    const result = await fetchPinnedQualifications(workspace, run, ids);
    expect(result.items.map(value => value.id)).toEqual(ids);
    expect(api.get).toHaveBeenCalledTimes(4);
  });

  it('drops superseded Unknown rows and refreshes review annotations on unchanged IDs', async () => {
    const common = crypto.randomUUID(), old = crypto.randomUUID(), current = crypto.randomUUID();
    vi.mocked(api.get).mockResolvedValueOnce({ items: [row(common), row(old, { status: 'UNKNOWN' })], next_cursor: null });
    vi.mocked(api.get).mockResolvedValueOnce({ items: [row(old), row(common, { critic_status: 'RESOLVED' }), row(current, { status: 'PASS' })], next_cursor: null });
    await fetchPinnedQualifications(workspace, run, [common, old]);
    const next = await fetchPinnedQualifications(workspace, run, [common, current]);
    expect(next.items.map(value => value.id)).toEqual([common, current]);
    expect(next.items[0]!.critic_status).toBe('RESOLVED');
    expect(next.items[1]!.status).toBe('PASS');
  });

  it.each(['workspace_id', 'run_id'])('rejects a foreign %s before displaying it', async key => {
    const id = crypto.randomUUID();
    vi.mocked(api.get).mockResolvedValue({ items: [row(id, { [key]: crypto.randomUUID() })], next_cursor: null });
    await expect(fetchPinnedQualifications(workspace, run, [id])).rejects.toThrow('pinned run');
  });

  it('fails explicitly when pinned evidence is missing instead of showing a historical verdict', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [row(crypto.randomUUID(), { status: 'PASS' })], next_cursor: null });
    await expect(fetchPinnedQualifications(workspace, run, [crypto.randomUUID()])).rejects.toThrow('incomplete');
  });

  it('terminates a broken cursor loop', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], next_cursor: 'repeated' });
    await expect(fetchPinnedQualifications(workspace, run, [crypto.randomUUID()])).rejects.toThrow('incomplete');
    expect(api.get).toHaveBeenCalledTimes(2);
  });
});
