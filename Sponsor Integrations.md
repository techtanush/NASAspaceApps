# Sponsor Integrations

Verified in the participant's native Comet window on 15 November 2026 against the [2026 Global Offers page](https://www.spaceappschallenge.org/2026/global-offers/). That page displayed the ten offer cards below. Availability and redemption terms remain the provider's responsibility. This document is an integration plan, not a claim that every offer has been redeemed.

## Priorities and current state

1. **Scientific inputs:** Planetary Computer terrain and Meteomatics Earth weather context are connected locally. Current numeric coverage is the acquired Gale/Flagstaff region. Broader catalog access is not equivalent to global scientific coverage.
2. **Delivery:** the requested `analog-forge.earth` domain has not been registered. Hosting, DNS and cloud migration remain separate from the local application.
3. **Optional infrastructure:** choose Azure or Google Cloud for the next deployment; preserve the same scientific operations, locks and receipts. Do not deploy both merely to display sponsor logos.
4. **Team tools:** Copilot, Teams and Miro support development and explanation. They are not scientific evidence or required runtime dependencies.

No billing, paid upgrade, trial activation or cloud provisioning is authorized by this document. Keep the user's existing instruction against billing changes in force. Never put credentials in this file, Git, frontend variables, screenshots or exported reports.

## Microsoft Azure

**Role:** future compute and hosting. Containerize the API, durable worker and PDF renderer separately. Use managed PostgreSQL with PostGIS and private blob storage only after validating the required extensions, worker leases, transaction semantics and object authorization. An implementation option is Container Apps Jobs for bounded scientific tasks; do not assume an HTTP request will keep a background worker alive.

**Handoff:** Tanush owns worker/storage deployment and private credentials; Aradhya owns only the public API origin and loading/error experience. Use workload identity and narrowly scoped service access. Preserve deterministic operation hashes, pinned dataset/policy versions and idempotency across job retries. Validate cancellation, killed-worker recovery, duplicate delivery and local/cloud numerical parity before switching traffic. This deployment is **not implemented or provisioned**.

## Microsoft Planetary Computer

**Role:** discover and acquire Earth environmental data. The current local source includes genuine NASADEM terrain; it is not a global search service. The [public catalog and API documentation](https://planetarycomputer.microsoft.com/docs/) describe anonymous STAC access. Some asset downloads require expiring [SAS signing](https://planetarycomputer.microsoft.com/docs/concepts/sas/).

**Next implementation:** Tanush should search STAC by the operator's Earth search region and supported mission dimensions, select a bounded set of product items, acquire crops, register source identifiers/time/CRS/vertical datum/native posting/checksums, and create a new immutable dataset lock. Only then may the deterministic science engine screen candidates. Refresh expired download tokens without changing source identity; never persist signed URLs as public provenance. Missing products, nodata and unsupported dimensions stay Unknown.

**Frontend contract:** Aradhya displays real registered footprints, source dates, support scale and candidate-specific measurements. USGS/EOX visual basemaps remain distinct from measured NASADEM layers. Imagery does not establish roughness, wheel-scale safety or global optimality. Validate actual source acquisition, changed-input candidate behavior, coverage failures and provider outages. See [local live runbook](analogforge/LOCAL-LIVE-RUNBOOK.md).

## Microsoft Copilot

**Role:** optional team brainstorming and documentation review. Use public architecture or deliberately approved excerpts to critique explanations, terminology and the pitch. Review generated text against registered evidence before incorporating it. No Copilot consumer login is a product API credential, and no consumer subscription is an OpenAI fallback transport. No integration is required.

## GitHub Copilot

**Role:** optional coding and review assistance against the repository. Assign one isolated branch and bounded task, require the same tests and ownership rules, and review the resulting diff. It must not invent source data, modify frozen contracts to silence tests, or access local private keys. Pull requests and passing receipts remain the integration boundary. The application does not require a Copilot key.

## Microsoft Teams

**Role:** team coordination and demonstration rehearsal. Share repository links, public reports and meeting notes intentionally. Private uploaded mission/rover documents remain in the application unless the operator separately authorizes sharing them. No automatic meeting, chat or file export is implemented. A future notification integration would require explicit destination approval and a dedicated server-side identity; it is unnecessary for the demo.

## Google Cloud

**Role:** alternative future deployment and expanded raster computation. Use an API service separately from [Cloud Run Jobs](https://docs.cloud.google.com/run/docs/create-jobs) for bounded batch work. A job executes a container to completion; partition independent candidate windows by explicit task index, then commit results through the same operation/receipt boundary. Use private object storage and a validated PostgreSQL/PostGIS service.

**Acceptance:** compute parity with local source locks, durable activity after browser reload, bounded concurrency, scoped object access, retry/cancellation correctness and resource measurement. Avoid multiplying work when platform retries and application retries overlap. Do not send uploaded mission documents to an additional AI service without a deliberate product decision. Google Maps is not required by the existing MapLibre/USGS/EOX visual path. No cloud account or billing settings were changed for this plan.

## Meteomatics Weather API

**Role:** actual Earth forecast/context observations around each selected candidate. The implemented server adapter uses `METEOMATICS_USERNAME` and `METEOMATICS_PASSWORD` with Basic authentication; there is no extra weather API-key acquisition step. `ANALOGFORGE_ENVIRONMENT_CONTEXT=true` enables the optional context path. Credentials and their expiry stay private.

**Current boundary:** retrieved Earth weather is supporting context, not a terrain suitability score or a Mars weather measurement. Preserve coordinates, requested/returned UTC times, parameters, units, retrieval time and provenance. Distinguish forecast, historical observations and climatology. An expired account, unavailable parameter or failed request must show unavailable context and retain valid terrain results.

**Future weather qualification:** first obtain applicable planetary observations/models with season, local solar time, uncertainty and spatial support. Define reviewed, feature-specific transfer criteria and Earth test procedures. Atmospheric pressure, gravity and lunar vacuum require explicit non-reproducibility gaps or controlled facilities; ordinary Earth weather cannot reproduce them. Only an implemented and verified comparator may affect ranking. See [environment contract](team%20handoffs/ui-split/INTEGRATED-OPERATIONS.md).

## Miro Business Plan

**Role:** optional team workshop for the requirement-to-evidence graph and test-site portfolio. The current app needs no paid Miro tier. Do not activate a payment-backed trial or change a subscription. Use the existing/free workspace if available; keep Miro's planning diagrams separate from authoritative accepted contracts and qualification records.

## Miro Board Templates

**Role:** optional hackathon planning and project explanation using the [Space Apps templates](https://miro.com/templates/profile/nasa-space-apps-challenge/). A useful board has mission goals → rover features → planetary conditions → Earth site → accepted benchmark → evidence/gaps. Populate it manually from approved public reports. Future board export can use the [Miro REST API](https://developers.miro.com/docs/miro-rest-api-introduction), but requires explicit user-directed sharing and server-side authorization. There is no current Miro API dependency.

## GoDaddy Registry: free domain and website hosting

**Role:** public project address. The offer's [redemption entry point](https://www.spaceapps.earth/) leads to Porkbun. The redemption site displayed **available** for the selected `analog-forge.earth` on 2026-11-15. Availability is a point-in-time observation, not a reservation. Registration is **not complete**. The claim form requires an adult registrant, eligibility confirmation, registration terms, CAPTCHA and email verification; registrant eligibility/contact confirmation is pending. Confirm the actual zero-cost cart before any final registration.

After registration, choose the actual hosting target, configure the required DNS records and HTTPS, then verify apex/`www`, deep links, API origin/CORS, report downloads and cookie security. Static hosting alone cannot run the Python worker, PostgreSQL or scientific jobs. Preserve registrant privacy and keep renewal dates/terms in the owner's private account. Stop for user completion of new-password or binding-agreement steps as required; do not add paid extras or alter billing.

## Evidence and deployment checklist

For any enabled integration record the adapter version, intended purpose, credential variable names, real success/failure receipts and limitations. Show attribution only where its data or service is actually used. Keep model-provider fallbacks separate from sponsor tools: supported text-provider configuration is documented in [text-provider-fallbacks.v1.md](analogforge/docs/text-provider-fallbacks.v1.md).

Before claiming a sponsor-powered capability in the demo, verify that the selected run actually used it. A displayed globe, an available cloud credit, an unredeemed offer or a planning board is not proof of a completed scientific investigation. Current operational and data boundaries are in the [integrated operations handoff](team%20handoffs/ui-split/INTEGRATED-OPERATIONS.md).
