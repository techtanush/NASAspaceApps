import { expect, it } from 'vitest';
import { execFileSync, spawnSync } from 'node:child_process';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
it('UIX-10 rejects a production mock and excludes dev/mock modules', () => {
 const command = resolve('node_modules/vite/bin/vite.js');
 const denied = spawnSync(process.execPath, [command, 'build'], { env: { ...process.env, NODE_ENV: 'production', VITE_API_MOCK: '1' }, encoding: 'utf8' });
 expect(denied.status).not.toBe(0); expect(denied.stderr).toContain('MOCK_BUILD_FORBIDDEN');
 execFileSync(process.execPath, [command, 'build'], { env: { ...process.env, NODE_ENV: 'production', VITE_API_MOCK: '0' }, stdio: 'pipe' });
 expect(existsSync('dist/mockServiceWorker.js')).toBe(false);
 expect(existsSync('dist/theme-init.js')).toBe(true);
 const js = readdirSync('dist/assets').filter(n=>n.endsWith('.js')).map(n=>readFileSync(`dist/assets/${n}`,'utf8')).join('\n');
 expect(js).not.toMatch(/MOCK PREVIEW|setupWorker|mockServiceWorker|__styleguide/);
}, 60000);
