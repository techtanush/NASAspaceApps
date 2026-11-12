import { afterEach, expect, it, vi } from 'vitest';

afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });

it('does not acknowledge preview persistence before the transaction commits, and retains the newest queued state', async () => {
  const writes: { snapshot?: unknown; oncomplete?: () => void; onerror?: () => void; onabort?: () => void }[] = [];
  const persisted: unknown[] = [];
  const database = {
    transaction: (_name: string, mode?: string) => {
      if (mode !== 'readwrite') return { objectStore: () => ({ get: () => {
        const request: { result?: unknown; onsuccess?: () => void } = {};
        queueMicrotask(() => request.onsuccess?.()); return request;
      } }) };
      const transaction: typeof writes[number] = {};
      writes.push(transaction);
      return Object.assign(transaction, { objectStore: () => ({ put: (state: unknown) => { transaction.snapshot = state; } }) });
    },
  };
  vi.stubGlobal('indexedDB', { open: () => {
    const request: { result: typeof database; onsuccess?: () => void } = { result: database };
    queueMicrotask(() => request.onsuccess?.()); return request;
  } });
  const state = await import('./state');
  await state.loadDatabase();
  state.db.settings.previewScenario = 'older state'; state.saveDatabase();
  state.db.settings.previewScenario = 'completed passport'; state.saveDatabase();
  let acknowledged = false;
  const completion = state.flushDatabase().then(() => { acknowledged = true; });
  await Promise.resolve();
  expect(acknowledged).toBe(false);
  expect(writes).toHaveLength(1);
  persisted.push(writes[0]!.snapshot); writes[0]!.oncomplete!();
  await Promise.resolve(); await Promise.resolve();
  expect(acknowledged).toBe(false);
  expect(writes).toHaveLength(2);
  persisted.push(writes[1]!.snapshot); writes[1]!.oncomplete!();
  await completion;
  expect(acknowledged).toBe(true);
  expect((persisted.at(-1) as { settings: { previewScenario: string } }).settings.previewScenario).toBe('completed passport');
});
