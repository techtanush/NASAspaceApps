export function normalizedFilters(filters: Record<string, unknown>): Record<string, unknown> { return Object.fromEntries(Object.keys(filters).sort().map(key => [key, filters[key]])); }
export const queryKeys = { workspace: (workspaceId: string, ...parts: unknown[]) => ['workspace', workspaceId, ...parts] as const };
