# Public judging release

AnalogForge opens through a detailed, scrollable landing page and a direct **Enter AnalogForge** link. Judges do not create an account or navigate login/logout screens. The landing remains readable when the session service is unavailable; an existing-session probe never allocates visitor storage. Entry into the investigation establishes a private browser workspace with opaque HttpOnly cookies, exact-origin CSRF checks and EDITOR permissions. Returning browsers recover their own recent investigations.

The existing scientific workflow remains intact: Mars/Moon selection, mission/context and rover input, accepted requirements, asynchronous research, Earth location directory and geographic pins, individual satellite context, benchmarks, downloadable evidence briefs, modeled rover verification and the bounded Analog Passport. Imagery is visual context and is not substituted for quantitative terrain data. Synthetic practice remains explicitly labeled.

## Verification

- Frontend: 339 tests; TypeScript, ESLint and production Vite build pass.
- Platform: 1,269 unit/integration/contract tests pass. The final non-allocating probe and malformed-CSRF hardening also pass 42 focused identity/settings/HTTP tests.
- Frozen contract kit: 20 tests pass; materialization verification finds no problems.
- Real local backend, worker, science and PDF renderer: five complete browser journeys pass, including site reports, PDF, rover proof/passport, mobile accessibility, no-WebGL access and explicit lunar data gaps. Two additional browser tests verify unavailable-session landing access, deliberate anonymous entry and existing-session recovery.
- Ruff, scoped Mypy, forbidden-pattern and credential-pattern checks pass.

These local journeys used synthetic quantitative data with the real execution stack. They do not claim a new live model-provider or global NASA research run. Public sessions add privacy and access controls, not scientific evidence.

## Hosting

`ops/azure/` provides the production runtime, persistent PostGIS/evidence, static frontend, HTTPS/SSE proxy, separate migration/runtime credentials, explicit live-data configuration override and backup/deployment commands. `.github/workflows/azure-container-check.yml` builds and smoke-tests a disposable Linux stack without Azure credentials. Its result and the actual hosted HTTPS journey must pass before the deployment is declared complete.

The Azure trial spending limit must remain enabled. Do not upgrade the subscription or remove that limit. DNS values come from the actual reserved public IP/hostname; domain owners need no model keys, database credentials or Azure account secrets. Routine application updates use GitHub and the repeatable deployment script; automatic deployment is not configured by the container verification workflow.
