# File ownership and interface freeze

Build one `analogforge/` application per checkout. The final merge combines complementary modules. It must not combine three separately scaffolded whole apps, three databases, three sets of statuses or three implementations of the same scientific calculation.

## Ownership

| Owner | Owned production paths relative to repository root |
| --- | --- |
| Tanush | `analogforge/src/analogforge/{api,domain,db,jobs,application,agents,tools,ports}/`; main/settings/CLI/package root; `adapters/{openai,storage,identity}/`; backend Docker/migrations; Compose/Make/Python dependency files; `config/scenarios.yaml`; implementation contracts; integration/operations. |
| Ayan | `analogforge/src/analogforge/science/`; `adapters/{earthdata,pds,emit,diviner,user_survey,source_http}/`; `rendering/tiles/`; `config/{datasets,algorithms,candidates}.yaml`; scientific tests/fixtures/preflight helpers. |
| Aradhya | `analogforge/apps/web/`; root frontend package/lock/workspace files; `src/analogforge/rendering/passport/`; renderer tests; browser end-to-end/accessibility tests. |

The machine-readable longest-prefix registry in `contracts/ownership.json` resolves exact paths. A longer specific rule overrides a broader prefix; unknown paths are not automatically free to edit. The common package root `src/analogforge/__init__.py`, `adapters/__init__.py`, `rendering/__init__.py` belongs to Tanush. Science/passport-owned package initializers belong to their respective owners. Use leaf modules rather than editing a shared barrel file for every new export.

Application-service wrappers belong to Tanush; scientific algorithms belong to Ayan. For example Tanush's `application/verification` loads records, authorizes and persists; Ayan's `science/routing` computes and independently checks the route. Aradhya's `rendering/passport` turns an already assembled snapshot into escaped HTML/CSV/JSON; Tanush's `application/passports` assembles/authorizes/freezes that snapshot. No duplicate policy/calculation should be hidden in either wrapper or browser.

## Shared files

Tanush is the single writer for `pyproject.toml`, `uv.lock`, Compose, backend migrations, global Make targets and published Python/domain/API contracts. Aradhya is the single writer for frontend package files, pnpm lock and generated TypeScript client. Ayan requests scientific packages by recording a dependency request in his handoff directory; he does not independently rewrite the shared Python lock. Tanush's initial dependency set includes the architecture's native-science packages so Ayan can begin immediately.

Original `architecture files/` documents/contracts remain read-only for Ayan and Aradhya. Tanush may reconcile them through a recorded contract-change decision with affected tests/consumers, not casual edits to make an implementation easier. Each person can maintain only their own `team handoffs/<person>/` and `team guides/<Person>/` files. Common coordination rules and root README/ignore belong to Tanush.

Generated clients are regenerated from Tanush's accepted exported OpenAPI. Aradhya checks in generated files under her frontend path. Tanush does not edit them by hand. Database migrations are created only on Tanush's branch, preventing competing migration heads.

## Initial authority and F0 freeze

The existing architecture schema/OpenAPI is contract C0. Before integration, Tanush publishes foundation checkpoint F0 containing:

1. Installed/locked Python dependencies and real Postgres/worker/API boot commands.
2. Pydantic/domain types and existing public status enums/units matching C0.
3. `ports/science.py` and `ports/passport_renderer.py` implementing the call boundaries in03.
4. Exported OpenAPI and a deterministic export command; public shape diff must match C0 or have an approved change record.
5. Structured errors, mode guard, workspace/job/run context, artifact I/O ports and cancellation token interface.
6. Stable scenario IDs and safe capabilities response so frontend run creation does not guess IDs.
7. Foundation test report and exact commit SHA. This is a real commit once implemented; do not invent a SHA in a template.

Ayan and Aradhya can build pure modules, fixtures and interface components against C0 while F0 is prepared. They import F0 when available and replace temporary **test doubles** with the accepted ports. A missing port is a dependency to report, not permission to create a competing production API.

## Change process

Use `templates/contract-change-request.json`. Record current contract hash/version, exact before/after fields, reason, consumers affected, compatibility, tests and required migration. Ayan or Aradhya proposes from their own handoff directory. Tanush implements the approved shared change, commits it, integrates it into main and identifies the checkpoint. Consumers merge that main commit, regenerate/retest, then continue. Human coordination is through the team's chosen conversation; this guide does not authorize sending messages from tools automatically.

An additive private helper in an owned module needs no contract-change process. A public response field, enum, nullability, unit, source/verification meaning, protocol signature or dependency lock does. No one silently changes PASS semantics, loosens rover limits, invents a model ID or substitutes a different data product.

## Completion versus build order

First deliver a terrain-first vertical slice; then complete remaining full-scope features. Hosted OIDC/deployment readiness is a later phase because this work is local, but do not replace workspace isolation and safe local binding with an unrestricted public server. Optional scientific source absence must have tested UNKNOWN/no-coverage behavior. A feature is not complete merely because its tab exists or a mock response has the right colors.

## Branch discipline

Own branch, own worktree, own runtime profile. Commit only owned files plus an explicitly approved shared patch. Merge accepted main checkpoints into feature branches; use merge commits rather than rewriting branches while teammates depend on them. Do not rebase/force-update another person's branch, reset worktrees, auto-resolve conflicts by choosing one entire side, or let an agent edit the root main checkout to fix its branch tests.

The ownership checker is an aid, not a security boundary. It checks changed paths against this registry; it cannot certify scientific behavior. A special shared patch must still be reviewed/tested even when its author is the owner.
