# Security identity and data policy

Protect workspace data, provider secrets and expensive computation without turning a scientific prototype into an enterprise platform. Local mode supports a trusted single user on loopback; any public deployment must enable the hosted identity and authorization controls below.

## Identity and authorization

`AUTH_MODE=local` seeds one local workspace/member and is allowed only on 127.0.0.1/localhost. Reject a local-mode public bind unless a separately documented development tunnel requires its own access control. Hosted `AUTH_MODE=oidc` uses Authorization Code + PKCE with validated issuer, audience, signature, expiration, state and nonce. Backend exchanges code, creates an opaque session, and places it in a Secure/HttpOnly/SameSite=Lax cookie. Session contents are server-side or authenticated encryption; do not trust client-supplied workspace IDs.

Implement `/auth/login`, `/auth/callback`, `/auth/logout`, and `/auth/session` outside the scientific `/api/v1` contract. Session response includes authenticated user/workspace/role and a CSRF token. Roles OWNER, EDITOR, VIEWER: viewers read permitted results/exports, editors create missions/runs/actions, owners manage membership and retention. Version one may configure membership administratively; it must not grant ownership to every valid OIDC user.

All state-changing cookie requests require CSRF token and exact allowed Origin. EventSource uses same-origin session cookies. GET downloads verify authorization through evidence/export ownership; content hashes are not bearer permissions. Every database repository scopes by workspace, with composite foreign keys and hosted RLS as defense in depth.

## Secrets

OPENAI_API_KEY, EARTHDATA_TOKEN, OIDC secrets, session secret and DB password are server-only. Redact authorization headers, DSNs, signed query parameters and tokens in logs/errors/exports. Frontend `VITE_*` variables are public; permit only API/base-map configuration there. Never give agents a tool to read environment variables, arbitrary files, credential stores or shell commands.

## Source retrieval

The downloader accepts registered dataset identities, not arbitrary user URLs. Resolve HTTPS links from known metadata and validate host/port/redirect chain. Block localhost, private/link-local IPs, cloud metadata endpoints, DNS rebinding, non-HTTPS schemes and redirect auth leakage. Allow source hosts explicitly by adapter and never forward auth across hosts without a documented provider requirement. A manual data import is a bounded uploaded product with label/metadata validation, not a general filesystem path.

Enforce compressed and decompressed byte limits, archive member count, extension/MIME checks, no path traversal and no symlink extraction. Decode rasters in a resource-limited worker subprocess. Do not execute code embedded in notebooks, labels, URLs, uploaded JSON or metadata descriptions. Scientific text is untrusted data.

## Agent safety and scientific integrity

Mission descriptions, source metadata and uploaded files cannot override common system policy. Separate quoted source content from instructions. Tools are allowlisted per role and validated by backend schemas/workspace scopes. Quantitative claims require receipts/evidence; a string saying "verified" cannot update state. The Scientific Critic can challenge; only the deterministic policy commits a status. No tool may lower a frozen threshold, change rover limits, execute motors, contact third parties, or publish externally.

Provider prompts contain only the minimum relevant mission and derived evidence summary. Do not upload raw large rasters, credentials or unrelated user documents. Source retention/license restrictions apply to cached products and exports. Do not claim NASA endorsement or certification. Dataset product citation and attribution are distinct from permission to redistribute the original bytes.

## Output handling

Render user/model text as escaped text. Sanitized Markdown, if supported, must disable raw HTML. Self-contained passport HTML has escaped values, restrictive CSP and no executable remote scripts. CSV fields beginning `=`, `+`, `-`, or `@` are safely escaped when textual; preserve numeric fields through typed serialization. Download headers use safe filenames, correct MIME and nosniff. Evidence source links strip credentials and transient query strings.

## Quotas

Initial per-workspace caps: 2 concurrent active runs, 25 detailed candidates per run, 2500 km² detailed AOI, 4 million processed raster cells, 2 GiB per source asset, 40 model calls per run, 3 replans and 15 minutes active compute. These are configurable operator limits; exceeding them produces RESOURCE_LIMIT/INCONCLUSIVE where appropriate. Queue fairness prevents one workspace monopolizing workers. Quotas never change accepted scientific requirements.

## Acceptance

Test ID enumeration across workspaces, stale sessions, CSRF, invalid OIDC issuer/audience, malicious product redirects, archive traversal, oversized raster, prompt injection in source metadata, fabricated evidence IDs, unescaped HTML and CSV formulas. Confirm logs and browser assets contain no secret values. A malicious mission prompt cannot add a new tool or override a mandatory constraint.
