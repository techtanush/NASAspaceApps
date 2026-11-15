import { createHash, randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { writeFile } from 'node:fs/promises';
import { basename, resolve } from 'node:path';
import { expect, test, type Locator, type Page } from '@playwright/test';
import type { ContextBinding, OperatorContext, OperatorDocument } from '../../apps/web/src/api/operatorContext';
import type { components } from '../../apps/web/src/generated/schema';

type S = components['schemas'];
const missionFixture = JSON.parse(readFileSync(resolve(import.meta.dirname, '../fixtures/kit/missions/mission-mars-mobility.json'), 'utf8')) as S['MissionDraftInput'];
const roverFixture = JSON.parse(readFileSync(resolve(import.meta.dirname, '../fixtures/kit/rovers/ares-1.json'), 'utf8')) as S['RoverInput'];

// The optional extension is deliberately outside the frozen 43-operation mutation audit in support/workbench.
// Use that harness's real session/CSRF flow, without mocking or intercepting any local API response.
async function browserJSON<T>(page: Page, path: string, body?: unknown) {
  return page.evaluate(async ({ path, body }) => {
    let csrf: string | undefined;
    if (body !== undefined) {
      const session = await fetch('/auth/session', { credentials: 'same-origin' });
      if (session.ok) { const value = await session.json(); csrf = value.csrf_token ?? value.csrfToken; }
    }
    const response = await fetch(`/api/v1${path}`, { method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...(csrf ? { 'X-CSRF-Token': csrf } : {}), ...(body === undefined ? {} : { 'Idempotency-Key': crypto.randomUUID() }) }, body: body === undefined ? undefined : JSON.stringify(body) });
    return { status: response.status, cache: response.headers.get('Cache-Control'), body: await response.json() as T };
  }, { path, body });
}

function responseFor(page: Page, path: string) {
  return page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === `/api/v1${path}`, { timeout: 15000 });
}

async function upload(page: Page, editor: Locator, path: string, source: string): Promise<OperatorDocument> {
  const stored = responseFor(page, '/operator-documents');
  await editor.getByLabel('Upload a supporting document', { exact: true }).setInputFiles(path);
  const response = await stored;
  expect(response.status()).toBe(201); expect(response.headers()['cache-control']).toBe('no-store');
  // Read back the exact identity exposed by the successful upload. Chromium may evict
  // a consumed POST body from its inspector cache; the authorized GET is authoritative.
  const original = editor.getByRole('link', { name: `Download original ${basename(path)}`, exact: true });
  await expect(original).toBeVisible();
  const href = await original.getAttribute('href');
  expect(href).toMatch(/^\/api\/v1\/operator-documents\/[a-f0-9-]{36}\/content$/i);
  const documentId = href!.split('/')[4];
  const readback = await browserJSON<OperatorDocument>(page, `/operator-documents/${documentId}`);
  expect(readback.status).toBe(200); expect(readback.cache).toBe('no-store');
  const document = readback.body; expect(document.id).toBe(documentId);
  expect(document.id).toMatch(/^[a-f0-9-]{36}$/i);
  expect(document.original_sha256).toBe(createHash('sha256').update(source).digest('hex'));
  expect(document.extracted_text).toBe(source);
  expect(document.extracted_text_sha256).toBe(createHash('sha256').update(source).digest('hex'));
  expect(document).toMatchObject({ extraction_status: 'EXTRACTED', trust: 'UNTRUSTED_CONTEXT', source_kind: 'OPERATOR_UPLOAD', text_truncated: false });
  await expect(editor.getByRole('heading', { name: document.filename, exact: true })).toBeVisible();
  await editor.getByText('Source identity and extracted text', { exact: true }).click();
  await expect(editor.getByRole('region', { name: `Extracted source text from ${document.filename}`, exact: true })).toHaveText(source);
  await expect(editor.locator('script')).toHaveCount(0);
  await expect(editor.getByRole('link', { name: `Download original ${document.filename}`, exact: true })).toHaveAttribute('href', `/api/v1/operator-documents/${document.id}/content`);
  return document;
}

async function saveAndBind(page: Page, editor: Locator, bindingPath: string) {
  await editor.getByRole('checkbox', { name: 'I reviewed these source excerpts and informational declarations.', exact: true }).check();
  const created = responseFor(page, '/operator-contexts'); const associated = responseFor(page, bindingPath);
  await editor.getByRole('button', { name: 'Save reviewed context', exact: true }).click();
  const contextResponse = await created; expect(contextResponse.status()).toBe(201);
  const context = await contextResponse.json() as OperatorContext;
  const bindingResponse = await associated; expect(bindingResponse.status()).toBe(201);
  const binding = await bindingResponse.json() as ContextBinding;
  expect(binding).toMatchObject({ context_id: context.id, context_sha256: context.context_sha256 });
  await expect(editor.getByText(`Context ${context.id}`, { exact: false })).toBeVisible();
  return { context, binding };
}

test.beforeEach(async ({ page }) => {
  expect(process.env.E2E_TARGET, 'This extension must exercise the real backend; mock mode excludes this exact spec.').toBe('real');
  // Orbital imagery is covered separately. This document test permits local traffic only, and never supplies fake responses.
  const origin = new URL(process.env.E2E_BASE_URL || 'http://127.0.0.1:5176').origin;
  await page.route('**/*', route => { const url = new URL(route.request().url()); return /^https?:$/.test(url.protocol) && url.origin !== origin ? route.abort('blockedbyclient') : route.continue(); });
  await page.goto('/about');
  await expect(page.getByTestId('app-shell')).toBeVisible();
});

test('actual documents, reviewed excerpts and exact rover declarations survive reload as immutable context versions', async ({ page }, info) => {
  test.setTimeout(90000);
  const suffix = randomUUID(); const mutations: string[] = [];
  page.on('request', request => { if (request.method() === 'POST') mutations.push(new URL(request.url()).pathname); });
  const mission = await browserJSON<S['MissionHeader']>(page, '/missions', { objective: missionFixture.objective, target: missionFixture.target, name: `Operator context roundtrip ${suffix}` });
  expect(mission.status).toBe(201);
  const rover = await browserJSON<S['RoverProfile']>(page, '/rovers', { ...roverFixture, name: `Context rover ${suffix}`, mass_kg: 57, max_slope_deg: 13 });
  expect(rover.status).toBe(201);
  const missionSource = '# Operator background\nCompare terrain for a rover rehearsal.\nDrill reach is unknown.\nLiteral <script>source text</script> stays plain text.\n';
  const missionPath = info.outputPath('operator-background.md'); await writeFile(missionPath, missionSource);
  await page.goto(`/missions/${mission.body.id}/edit`);
  let missionEditor = page.getByRole('region', { name: 'Mission background documents', exact: true });
  const document = await upload(page, missionEditor, missionPath, missionSource);
  const excerpt = 'Compare terrain for a rover rehearsal.\nDrill reach is unknown.';
  await missionEditor.getByLabel(`Reviewed excerpt from ${document.filename}`, { exact: true }).fill(excerpt);
  const original = await saveAndBind(page, missionEditor, `/missions/${mission.body.id}/operator-context`);
  expect(original.context).toMatchObject({ kind: 'MISSION', rover_revision_id: null, reviewed: true, trust: 'UNTRUSTED_CONTEXT', features: [] });
  expect(original.context.documents).toEqual([expect.objectContaining({ document_id: document.id, reviewed_excerpt: excerpt, original_sha256: document.original_sha256 })]);
  expect(original.binding).toMatchObject({ target_kind: 'MISSION_DRAFT', target_id: mission.body.current_draft_id, context_revision: 1, mission_revision: mission.body.revision + 1 });
  await page.reload(); missionEditor = page.getByRole('region', { name: 'Mission background documents', exact: true });
  await expect(missionEditor.getByLabel(`Reviewed excerpt from ${document.filename}`, { exact: true })).toHaveValue(excerpt);
  await expect(missionEditor.getByText(`Context ${original.context.id}`, { exact: false })).toBeVisible();
  const replacementExcerpt = 'Drill reach is unknown.';
  await missionEditor.getByLabel(`Reviewed excerpt from ${document.filename}`, { exact: true }).fill(replacementExcerpt);
  const replacement = await saveAndBind(page, missionEditor, `/missions/${mission.body.id}/operator-context`);
  expect(replacement.context.id).not.toBe(original.context.id); expect(replacement.context.context_sha256).not.toBe(original.context.context_sha256);
  expect(replacement.binding.context_revision).toBe(original.binding.context_revision + 1);
  const historical = await browserJSON<OperatorContext>(page, `/operator-contexts/${original.context.id}`);
  expect(historical.status).toBe(200); expect(historical.cache).toBe('no-store'); expect(historical.body).toEqual(original.context);
  const current = await browserJSON<ContextBinding>(page, `/missions/${mission.body.id}/operator-context`);
  expect(current.body.context_id).toBe(replacement.context.id);
  const roverSource = 'Operator supporting note.\nInstrument data rate is declared separately from numeric mobility limits.\n';
  const roverPath = info.outputPath('rover-supporting.txt'); await writeFile(roverPath, roverSource);
  await page.goto(`/rovers/${rover.body.rover_id}`);
  const roverEditor = page.getByRole('region', { name: 'Rover supporting documents and features', exact: true });
  const roverDocument = await upload(page, roverEditor, roverPath, roverSource);
  await roverEditor.getByLabel(`Reviewed excerpt from ${roverDocument.filename}`, { exact: true }).fill('Operator supporting note.');
  await roverEditor.getByRole('button', { name: 'Add custom feature', exact: true }).click();
  const first = roverEditor.getByRole('group', { name: 'Feature 1', exact: true });
  await first.getByLabel('Feature name', { exact: true }).fill('Drill reach');
  await expect(first.getByRole('checkbox', { name: 'Value unknown', exact: true })).toBeChecked();
  await roverEditor.getByRole('button', { name: 'Add custom feature', exact: true }).click();
  const second = roverEditor.getByRole('group', { name: 'Feature 2', exact: true });
  await second.getByLabel('Feature name', { exact: true }).fill('Instrument data rate');
  await second.getByRole('checkbox', { name: 'Value unknown', exact: true }).uncheck();
  await second.getByLabel('Declared value', { exact: true }).fill('0'); await second.getByLabel('Unit (optional)', { exact: true }).fill('kb/s');
  const supporting = await saveAndBind(page, roverEditor, `/rover-revisions/${rover.body.id}/operator-context`);
  expect(supporting.context).toMatchObject({ kind: 'ROVER', rover_revision_id: rover.body.id, features: [{ name: 'Drill reach', value: null, unit: null, unknown: true }, { name: 'Instrument data rate', value: '0', unit: 'kb/s', unknown: false }] });
  expect(supporting.binding).toMatchObject({ target_kind: 'ROVER_REVISION', target_id: rover.body.id, context_revision: 1, mission_revision: null });
  await page.reload();
  await expect(roverEditor.getByRole('group', { name: 'Feature 1', exact: true }).getByLabel('Feature name', { exact: true })).toHaveValue('Drill reach');
  await expect(roverEditor.getByRole('group', { name: 'Feature 1', exact: true }).getByRole('checkbox', { name: 'Value unknown', exact: true })).toBeChecked();
  await expect(roverEditor.getByRole('group', { name: 'Feature 2', exact: true }).getByLabel('Declared value', { exact: true })).toHaveValue('0');
  const savedRover = await browserJSON<S['RoverProfile']>(page, `/rover-revisions/${rover.body.id}`);
  expect(savedRover.body).toEqual(rover.body); expect(savedRover.body).toMatchObject({ mass_kg: 57, max_slope_deg: 13 });
  const roverBinding = await browserJSON<ContextBinding>(page, `/rover-revisions/${rover.body.id}/operator-context`);
  expect(roverBinding.body.context).toEqual(supporting.context);
  expect(mutations.filter(path => path.endsWith('/fingerprint') || path === '/api/v1/runs' || path === '/api/v1/operator-context/runs')).toEqual([]);
});

test('a forged reviewed excerpt is rejected by the browser and real server without creating a binding', async ({ page }, info) => {
  test.setTimeout(90000);
  const mission = await browserJSON<S['MissionHeader']>(page, '/missions', { objective: missionFixture.objective, target: missionFixture.target, name: `Rejected excerpt ${randomUUID()}` }); expect(mission.status).toBe(201);
  const source = 'This source declares no thermal operating limit.\n'; const file = info.outputPath('source-without-limits.txt'); await writeFile(file, source);
  await page.goto(`/missions/${mission.body.id}/edit`);
  const editor = page.getByRole('region', { name: 'Mission background documents', exact: true }); const document = await upload(page, editor, file, source);
  const excerpt = 'Certified operating temperature is 1000 K.';
  await editor.getByLabel(`Reviewed excerpt from ${document.filename}`, { exact: true }).fill(excerpt);
  await editor.getByRole('checkbox', { name: 'I reviewed these source excerpts and informational declarations.', exact: true }).check();
  await expect(editor.getByRole('button', { name: 'Save reviewed context', exact: true })).toBeDisabled(); await expect(editor.getByRole('alert')).toHaveText('Use an exact passage from the extracted text.');
  const rejected = await browserJSON<{ error: { code: string } }>(page, '/operator-contexts', { schema_version: 'operator-context.v1', kind: 'MISSION', rover_revision_id: null, documents: [{ document_id: document.id, reviewed_excerpt: excerpt }], features: [], reviewed: true });
  expect(rejected.status).toBe(422); expect(rejected.body.error.code).toBe('INPUT_INVALID');
  const unchanged = await browserJSON<ContextBinding>(page, `/missions/${mission.body.id}/operator-context`); expect(unchanged.status).toBe(200); expect(unchanged.body).toMatchObject({ context_revision: 0, context_id: null, context_sha256: null, context: null, mission_revision: mission.body.revision });
  await page.reload(); await expect(editor).toBeVisible(); await expect(editor.getByRole('heading', { name: document.filename, exact: true })).toHaveCount(0);
  const stored = await browserJSON<OperatorDocument>(page, `/operator-documents/${document.id}`); expect(stored.status).toBe(200); expect(stored.body.original_sha256).toBe(createHash('sha256').update(source).digest('hex'));
});
