# Recent investigation projection v1

`GET /api/v1/workspace/recent-runs?limit=4` is an authenticated, read-only UI projection. `limit` is an integer from 1 through 20; its default is 4. The response is `{items: RunSnapshot[], next_cursor: null}`. It is a bounded recent window, not a paginated inventory. The core `GET /runs` endpoint retains its existing ascending order and cursor semantics.

The server takes workspace identity exclusively from the established principal. It orders records by creation time descending and ID descending as a stable tie breaker, trims in PostgreSQL, drops internal runtime/audit payloads before loading and projects through the existing public `RunSnapshot` contract. It sends `Cache-Control: no-store`. The client does not cache run history in browser storage or load the entire workspace to find recent records.

Every state remains eligible: failed, blocked and cancelled investigations are not hidden or relabelled. No scientific results, accepted criteria, rover limits, provider routing or run budgets change. The optional endpoint is registered alongside the work-log UI projection and does not modify the frozen core OpenAPI.

Found during the final computer journey: the landing page previously requested the first four entries from the core ascending list and consequently showed the oldest runs. The landing page now requests this explicit recent window. Tests cover tied timestamps, workspace isolation, internal-data exclusion, bounded SQL, descending continuation, unchanged core ordering, invalid limits, authentication and the browser preview.
