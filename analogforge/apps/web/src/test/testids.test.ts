import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import hooks from '../../../../contracts/ui-testids.json';
const walk = (dir: string): string[] => readdirSync(dir, { withFileTypes: true }).flatMap(x => x.isDirectory() ? walk(resolve(dir, x.name)) : /\.(tsx?|css)$/.test(x.name) && !/\.test\./.test(x.name) ? [resolve(dir, x.name)] : []);
describe('UIX-04 frozen test hooks', () => {
 it('implements all stable hooks without shrinking the contract', () => {
  expect(hooks.testids.length).toBe(81);
  const source = walk(resolve('src')).filter(p => !p.includes('/generated/')).map(p => readFileSync(p, 'utf8')).join('\n');
  for (const hook of hooks.testids) expect(source, hook.id).toContain(`"${hook.id}"`);
 });
});
