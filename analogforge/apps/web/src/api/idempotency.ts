/** A command key belongs to a logical action, including uncertain transport retries. */
export function commandKey(): string { return crypto.randomUUID(); }
export async function retryUncertain<T>(send: () => Promise<T>, recover: () => Promise<unknown>): Promise<T> {
  try { return await send(); } catch (error) {
    if (!(error instanceof TypeError)) throw error;
    await recover();
    return send();
  }
}
