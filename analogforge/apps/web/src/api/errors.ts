import type { components } from '../generated/schema';
export type ErrorEnvelope = components['schemas']['ErrorEnvelope'];
export class ApiError extends Error {
  readonly code: string; readonly details: Record<string, unknown>; readonly requestId: string; readonly retryable: boolean;
  constructor(readonly status: number, envelope: ErrorEnvelope) {
    super(envelope.error.message); this.name = 'ApiError'; this.code = envelope.error.code; this.details = envelope.error.details; this.requestId = envelope.error.request_id; this.retryable = envelope.error.retryable;
  }
}
