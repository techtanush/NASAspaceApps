import type { paths } from '../generated/schema';
import { ApiError, type ErrorEnvelope } from './errors';
import { commandKey, retryUncertain } from './idempotency';
export type ApiPath = keyof paths;
export const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
let csrfToken: string | undefined;
export function setSessionCsrf(token?: string): void { csrfToken = token; }
export interface RequestOptions { signal?: AbortSignal; key?: string; recover?: () => Promise<unknown> }
export async function raw(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set('Accept', headers.get('Accept') || 'application/json');
  if (init.body) headers.set('Content-Type', 'application/json');
  if (csrfToken && init.method && init.method !== 'GET') headers.set('X-CSRF-Token', csrfToken);
  const response = await fetch(`${API_BASE}${path}`, { ...init, credentials: 'same-origin', headers });
  if (!response.ok && response.status !== 202) {
    const payload = await response.json().catch(() => ({ error: { code: 'INVALID_RESPONSE', message: `HTTP ${response.status}`, request_id: '', retryable: false, details: {} } })) as ErrorEnvelope;
    throw new ApiError(response.status, payload);
  }
  return response;
}
export async function request<T>(path: string, init: RequestInit = {}): Promise<T> { return (await raw(path, init)).json() as Promise<T>; }
export function get<T>(path: string, options: RequestOptions = {}): Promise<T> { return request<T>(path, { signal: options.signal }); }
export function post<T>(path: string, body: unknown, options: RequestOptions = {}): Promise<T> {
  const key = options.key || commandKey();
  const serialized = JSON.stringify(body);
  const send = () => request<T>(path, { method: 'POST', body: serialized, signal: options.signal, headers: { 'Idempotency-Key': key } });
  return options.recover ? retryUncertain(send, options.recover) : send();
}
export const api = { get, post, request, raw };
