# Implementation decisions

- Development mock previews use Vite mode `mock` on the dev server; every build rejects VITE_API_MOCK=1. The visual audit uses this explicitly bannered dev server because a production mock build conflicts with UIX-10. No runtime fallback.
- Renderer CSV evaluation_stage stays empty where the frozen QualificationDimension has no such field; no inference from prose.

- Frozen kit import itself loads `socket` via Pydantic typed schema internals. Renderer purity tests compare imports against a preloaded kit baseline and prohibit any additional network/DB/model imports, environment reads, or file writes.
- Supplied token verification/generator scripts must remain byte-identical. An owned nested Ruff config excludes only those upstream copies from style lint; authored scripts retain all project lint rules.

- Production audit distinguishes non-fetching XML/JSON-Schema identifiers and dependency documentation literals from resource URLs. Their explicit prefixes are classified in `out/production-audit.json`; HTML/CSS resources must remain local, browser requests must remain on the app origin. Production omits the development service worker entirely, including public-directory copies.

- The frozen kit ignore file omits `out/`, while the gates generate reports there and forbid committing build output. A workspace postinstall adds only `/analogforge/out/` to local `.git/info/exclude` so clean clones pass ownership checks after verification without changing the kit or tracking reports.

- Authentication is bootstrapped from the server’s `/auth/session` before any workspace query or mutation. The session adapter accepts `workspace_id` or `workspace.id`, and primary `csrf_token` plus compatible `csrfToken` spelling because architecture24 defines semantics without a frozen auth-response schema. Conflicting aliases/invalid IDs fail; no fixed workspace UUID is used by real startup.

- Layout-shift cohorts measure real reload/data-arrival at each required viewport/theme/density before audit-induced focus, resize, theme, or text-spacing changes. C12 records cancellations separately only when the test observes the actual AbortSignal or explicitly initiates a navigation; other failed requests remain failures. This reconciles required request-abort cleanup with the audit’s no-transport-failures rule.

- Overlay audit states (`Evidence-open-*`, `Operations-open-*`, `Shortcuts-open-*`) preserve the open dialog and measure its controls. C05 compares controls within the same overlay layer, since an intentionally layered drawer necessarily covers the underlying workspace; C07 walks the open overlay until focus leaves it. Ordinary screen cohorts still inspect the entire workspace. Drawer focus-out and Escape behavior are tested separately. Text and contrast checks continue across the visible document.
