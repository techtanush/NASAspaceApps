# Credentials and external services

Only obtain credentials for a feature that actually uses them. Keep secrets in local ignored environment files or a deployment secret store. This blueprint contains names and setup procedures, never real key values. Creating accounts, accepting data terms, and choosing a funded model account are user/operator prerequisites; an implementation agent cannot manufacture them.

## Dependency matrix

| Service | Environment settings | Needed when | Setup and verification |
| --- | --- | --- | --- |
| OpenAI API | OPENAI_API_KEY, OPENAI_MODEL | Live mission interpretation and Agent Council | User creates a project-scoped server key in their OpenAI API account. Configure a model available to that project with Responses, function calling, and structured output support. Run the small capability probe described below. |
| NASA Earthdata Login | EARTHDATA_TOKEN | Protected downloads from compatible Earthdata DAAC endpoints | User registers/logs in at Earthdata Login, creates a user token, authorizes the applicable data application where needed, and verifies one chosen product download. Token support is endpoint-specific. |
| NASA/PDS public archives | None by default | Public MOLA/LOLA/Diviner products selected in dataset lock | Verify exact product URL, label, checksum, content type and access response. Public access does not imply every NASA endpoint uses the same protocol. |
| CMR metadata search | None for public metadata; token only if selected access requires it | Product/granule discovery | Query official CMR search; metadata results are not permission to assume download success. |
| PostgreSQL | DATABASE_URL; local POSTGRES_* settings | Every normal application mode | Generate a local development password. Hosted deployment uses a dedicated application role and separate migration credential. |
| OIDC identity provider | OIDC_ISSUER_URL, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, SESSION_SECRET | Hosted multiuser mode | Register callback and logout URLs with chosen provider; validate issuer, audience, signature, state, nonce and PKCE. |
| Basemap vendor | Optional MAP_TILE_URL and vendor public browser token | Optional licensed background map | Default app uses local neutral outline/raster layers. If enabled, restrict browser token by origin and preserve attribution. No Mapbox key is intrinsically required for MapLibre. |
| Object storage | Optional S3 settings for a later storage adapter | Hosted storage migration | Version one can use persistent local volume. Do not require AWS just to run the app. |
| Sponsors and weather vendors | None | Only a separately justified future requirement | Google, Microsoft, GoDaddy, Meteomatics are not required dependencies. No sponsor integration should be added merely for a logo. |

No `NASA_API_KEY` is required for the selected CMR/PDS/DAAC design. The general NASA API portal key is not a replacement for Earthdata Login credentials. Neither GitHub, Google Maps, Google Earth Engine, nor a vector database is required.

## OpenAI capability probe

Use the official server SDK and Responses API. Send one minimal strict function schema with one harmless field, require the test tool, disable parallel calls for this probe, and verify the returned call can be parsed. Then test a minimal structured final result with the configured model. Reject missing model, unsupported capability, refusal, incomplete result, invalid tool name, 401/403, or exhausted budget with an actionable capability report. Do not select a different model silently.

Set `store=false` where supported by the configured Responses path; maintain explicit continuation items or documented response state in the adapter. Pass tool results tied to actual provider call IDs. Persist provider request IDs, configured model, usage and a sanitized response summary; do not persist hidden reasoning as an activity feed. Strict schemas limit shape, not scientific correctness; backend evidence and policy validation remain mandatory. See [function calling](https://developers.openai.com/api/docs/guides/function-calling) and [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).

## Earthdata procedure

1. Register a user account at [Earthdata Login](https://urs.earthdata.nasa.gov/).
2. Use the account's token-management page to create a token; enter it only into the ignored server environment or secret store. Do not paste it into architecture files, chat prompts, committed examples, or browser localStorage.
3. Resolve an actual collection and granule in CMR. Inspect its advertised data URL and the provider's access instructions.
4. Test metadata access separately from an authenticated small download. Validate response bytes rather than accepting an HTTP 200 HTML login page as a raster.
5. If bearer authentication is unsupported by that endpoint, mark DOWNLOAD_AUTH_UNSUPPORTED and document the DAAC-supported alternative/manual import. Do not forward a bearer token to an unrelated redirect host.
6. On expiry/revocation mark the protected dependency blocked and preserve cached valid data. Refresh credentials outside the running agent's scientific context, rerun preflight, then retry.

Earthdata's current token documentation describes user-managed tokens and a limited lifetime; record expiry in the operator's secret manager and check it during preflight. See [user token documentation](https://urs.earthdata.nasa.gov/documentation/for_users/user_token). Public CMR collection/granule discovery and supported metadata formats are documented in the [CMR API](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html).

## Credential behavior

Synthetic mode ignores external keys and makes no external calls. Replay uses locked local artifacts/recorded operations; it does not contact a model to decorate an old run as live. Live mode requires a working model key and the selected source data; optional source failures produce UNKNOWN for affected dimensions. Preflight displays only configured/missing/valid/expired/unsupported state, never a secret fragment.

Do not scan the user's broader filesystem or other projects looking for keys. Check only the explicitly configured environment and documented secret files. If credentials are absent during implementation, finish the offline system and report exact unmet live gates; do not label live integration tested.

## Acceptance

Browser bundles, error reports, exports, traces and git history contain no keys. Redirection tests prove provider auth headers do not leak. A missing OpenAI model produces a useful blocked capability, not a default invented model. One metadata query and one checksummed source download are recorded for each live protected adapter before its live acceptance test can pass.
