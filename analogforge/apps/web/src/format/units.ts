const units: Record<string, string> = { deg: '°', percent: '%', fraction: 'fraction', m: 'm', Wh: 'Wh', K: 'K', count: 'count' };
export function unitLabel(unit: string): string { return units[unit] ?? unit; }
