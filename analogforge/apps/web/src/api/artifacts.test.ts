import { afterEach, expect, it, vi } from 'vitest';
import { ALGORITHM_IDS, findEvidenceByAlgorithm } from './artifacts';

afterEach(() => { vi.unstubAllGlobals(); });

it('picks the JSON payload record, never an accepted-assumption record or a binary grid sharing the algorithm id', async () => {
  const records: Record<string, object> = {
    a: { id: 'a', kind: 'ASSUMPTION', algorithm_id: ALGORITHM_IDS.COMPARE_REQUIREMENT, artifact_media_type: 'application/json', artifact_sha256: '1'.repeat(64) },
    b: { id: 'b', kind: 'DERIVED', algorithm_id: ALGORITHM_IDS.COMPARE_REQUIREMENT, artifact_media_type: 'application/x-npz', artifact_sha256: '2'.repeat(64) },
    c: { id: 'c', kind: 'COMPARISON', algorithm_id: ALGORITHM_IDS.COMPARE_REQUIREMENT, artifact_media_type: 'application/json', artifact_sha256: '3'.repeat(64) },
  };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => Response.json(records[String(url).split('/').pop()!])));
  const found = await findEvidenceByAlgorithm(['a', 'b', 'c'], 'COMPARE_REQUIREMENT');
  expect(found?.id).toBe('c');
});
