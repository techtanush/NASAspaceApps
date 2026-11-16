import { expect, test } from '@playwright/test';

test('public introduction survives an unavailable session service without allocating a workspace', async ({ page }) => {
  const sessions: string[] = [];
  const privateReads: string[] = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.pathname === '/auth/session') sessions.push(url.pathname + url.search);
    if (url.pathname.startsWith('/api/v1/')) privateReads.push(url.pathname);
  });
  await page.route('**/auth/session**', async route => {
    if (new URL(route.request().url()).searchParams.get('create') === 'false') {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ authenticated: false }) });
    } else await route.continue();
  });
  const probe = page.waitForResponse(response => new URL(response.url()).pathname === '/auth/session');
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'A world away. Tested closer to home.' })).toBeVisible();
  await probe;
  expect(sessions).toEqual(['/auth/session?create=false']);
  expect(privateReads).toEqual([]);
  await expect(page.getByTestId('recent-investigations')).toHaveCount(0);
  await expect(page.getByTestId('error-panel')).toHaveCount(0);

  // A deliberate entry reloads the app and establishes a private visitor session.
  await page.getByRole('link', { name: 'Enter AnalogForge', exact: true }).click();
  await expect(page).toHaveURL(/\/start\/place$/);
  await expect(page.getByRole('heading', { name: 'Where is the mission?' })).toBeVisible();
  expect(sessions).toEqual(['/auth/session?create=false', '/auth/session']);
});

test('returning to the public introduction recovers the existing workspace with a nonallocating probe', async ({ page }) => {
  const sessions: string[] = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.pathname === '/auth/session') sessions.push(url.pathname + url.search);
  });
  const created = page.waitForResponse(response => new URL(response.url()).pathname === '/auth/session');
  await page.goto('/start/place');
  const initial = await (await created).json() as { workspace_id: string };
  await expect(page.getByRole('heading', { name: 'Where is the mission?' })).toBeVisible();
  const probe = page.waitForResponse(response => new URL(response.url()).pathname === '/auth/session' && new URL(response.url()).searchParams.get('create') === 'false');
  const recent = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/workspace/recent-runs');
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'A world away. Tested closer to home.' })).toBeVisible();
  expect((await (await probe).json() as { workspace_id: string }).workspace_id).toBe(initial.workspace_id);
  expect((await recent).status()).toBe(200);
  expect(sessions).toEqual(['/auth/session', '/auth/session?create=false']);
});
