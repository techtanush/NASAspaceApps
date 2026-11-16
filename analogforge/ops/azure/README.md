# Azure production package

This package runs the actual API, CPU science worker and PDF renderer from one locked source revision, with a persistent PostGIS 16 database and content-addressed evidence storage. Caddy serves the production frontend and HTTPS; SSE progress responses are flushed immediately. There is no Vite server, browser mock worker, public PostgreSQL port or shared local Owner account. `AUTH_MODE=public` gives each visitor a private anonymous workspace without a login screen.

## VM preparation

1. Confirm the existing Azure subscription is the intended credit-backed trial, its spending limit remains enabled, and credits are available. This package never upgrades a subscription or edits billing settings. VM/disks/IPs consume those credits; a budget notification is not a hard spending cap. Do not create resources if those conditions cannot be verified.
2. Provision Ubuntu 24.04 LTS, x86-64, at least **4 vCPU / 8 GiB RAM / 64 GiB persistent disk**, with the supplied `cloud-init.yaml`. Assign a static public IPv4 address and an actual Azure DNS label. Resource availability and price depend on the subscription/region; no price or free VM entitlement is assumed here.
3. In the Azure network security group allow TCP 80/443 publicly and TCP 22 only from the operator's current IP. Do not open 5432 or 8000. Use SSH keys and disable password authentication. Caddy can use UDP 443 for HTTP/3 when permitted, but TCP HTTPS works without it.
4. Wait for `sudo cloud-init status --wait`. The file installs Docker Engine and Compose from [Docker's signed Ubuntu apt repository](https://docs.docker.com/engine/install/ubuntu/); it does not pipe a downloaded script into a shell. Azure supports [cloud-init for Linux VM setup](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/tutorial-automate-vm-deployment).

## First deployment

Commit/push the reviewed application and this package first. On the VM, clone the public repo into `/srv/analogforge/repository` if not already present, then run the package at that reviewed full 40-character commit:

```bash
sudo git clone https://github.com/techtanush/NASAspaceApps.git /srv/analogforge/repository
sudo git -C /srv/analogforge/repository checkout --detach FULL_40_CHARACTER_COMMIT
sudo /srv/analogforge/repository/analogforge/ops/azure/bootstrap.sh ACTUAL_AZURE_DNS_HOST FULL_40_CHARACTER_COMMIT
```

Replace both uppercase arguments with verified values. Do not run the clone command over an existing directory. `bootstrap.sh` refuses to replace existing credentials. It creates `/etc/analogforge/runtime.env` and a separate `/etc/analogforge/database.env`, both mode 0600, with random database/session secrets, exact HTTPS origin and public anonymous access. The bootstrap database administrator is used only for migrations and role provisioning. API/worker receive a non-superuser runtime table-owner credential; they do not receive the administrator password or URL. Secrets never enter the image or repository. The initial mode is honestly labelled **synthetic practice**; no paid AI API call is configured automatically. Real orbital/satellite context imagery is separate from synthetic quantitative terrain evidence.

The deploy script builds exact source-tagged images before stopping the old app, backs up the old database and evidence, drains the worker, applies migrations, provisions the non-superuser runtime table owner, seeds the immutable practice lock idempotently, starts all services, and checks database/API/worker/public HTTPS readiness. It writes a credential-free receipt to `/srv/analogforge/receipts/COMMIT.json`. Base image digests and Python/pnpm lockfiles are fixed in the build. Container build and VM runtime still need verification on Linux; a Compose syntax check alone is not a deployment.

Caddy obtains a public certificate for `APP_HOST` after DNS resolves to this VM and ports 80/443 are reachable. It provides [unbuffered reverse proxy streaming](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy). Domain registration is independent of this deployment.

## Activation checks

- Open the actual HTTPS URL in a fresh browser: detailed landing → enter without an account → Mars or Moon selection → mission/context → custom rover or explicit preset → review → research log → all Earth pins → selected site satellite map → report → PDF → rover proof and passport.
- Open an independent private window: it must receive a different workspace and must not read the first window's missions, rover uploads or results. Repeated readiness checks must not create visitor sessions.
- Verify deep-link reload returns the SPA, assets return JavaScript/CSS rather than `index.html`, and progress events arrive during the run. Verify a failed scientific benchmark is displayed honestly, independently of infrastructure health.
- Confirm `worker_healthy=true`, a real per-site PDF downloads, DB has no public host binding, and source receipt matches the deployed commit. No "live global search" claim is justified by synthetic or one-region data.

The current shared runtime role owns application tables so the worker can scan durable job queues across workspaces. PostgreSQL table owners bypass ordinary RLS, even though this role is explicitly `NOBYPASSRLS` and `NOSUPERUSER`; isolation therefore relies on the existing transaction-scoped Store predicates and verified anonymous sessions. Distinct API and queue-worker database roles would require a separately validated worker/auth refactor and are not claimed here. The role cannot create databases/roles, replicate, or act as a superuser.

## Updates and rollback

Routine code updates only require GitHub and Azure access. Aradhya does not need to touch registrar DNS unless the hostname/IP changes. After checks pass and the new commit is pushed:

```bash
sudo /srv/analogforge/current/analogforge/ops/azure/deploy.sh NEW_FULL_40_CHARACTER_COMMIT
```

This is a repeatable manual deployment, **not an already-configured GitHub Actions auto-deploy**. Keep the latest known-good image and receipt. For application-only rollback, run the same command with the previous source commit **only after checking migration backward compatibility**. Never automatically downgrade a schema, reset the database, remove named volumes, or run `docker compose down -v`. Deployment briefly pauses research submissions while draining/migrating; this single VM is not a high-availability cluster.

## Backup and restore

```bash
sudo env RELEASE_ID=ACTIVE_FULL_COMMIT /srv/analogforge/current/analogforge/ops/azure/backup.sh
sudo env RELEASE_ID=ACTIVE_FULL_COMMIT /srv/analogforge/current/analogforge/ops/azure/restore-check.sh /srv/analogforge/backups/ACTUAL_TIMESTAMP
```

A backup pauses only this stack's writers and stores the database dump, complete evidence/locks/source cache, both private runtime/database configurations and checksums under a mode-0700 directory. It restarts the previously existing containers, preserving their exact source. The restore check uses a disposable database and verifies every archived CAS blob's SHA-256 without changing active data. Backups contain private documents and credentials: encrypt before copying off the VM and keep an independent copy. A backup on the same disk does not protect against VM/disk loss. Nightly scheduling/off-machine encryption and a full application-level passport-lineage restore rehearsal remain operator tasks; these are not silently claimed complete.

## Real data and provider configuration

To enable live research, securely copy the existing permitted dataset files and checksum locks into the persistent `analogforge_evidence` volume, preserving `/data` paths. Prepare `/srv/analogforge/operator-config` from the same release's config, retaining normal directory traversal/read permissions for UID 10001. Bind `live-hackathon-v1` to those real products with the existing dataset CLI before mounting the directory read-only. Set `AF_OPERATOR_CONFIG_DIR=/srv/analogforge/operator-config` and `CONFIG_DIR=/app/config` in the private runtime env. For the [Gale/Flagstaff rehearsal](../../LOCAL-LIVE-RUNBOOK.md), set `live_terrain_support_m: 500` in the operator copy of `algorithms.yaml` and use 12 km generated windows at 500 m. Leave the base grid and measurement support unchanged so that the shared service still supports synthetic practice. Activate the configuration after runs using the previous science hash have finished; prepare fresh coverage indexes under the new configuration. Use the supplied `compose.live.yaml` with `sudo env AF_COMPOSE_OVERRIDE=/srv/analogforge/current/analogforge/ops/azure/compose.live.yaml .../deploy.sh COMMIT`; the deploy/backup/restore helpers all accept this explicit override. The mounted directory is never baked into an image or overwritten by a code update. Add only the desired text/weather credentials privately to `/etc/analogforge/runtime.env`; pin explicit models and fallback order. Run the existing preflight in the live container and inspect provenance, coverage, support scale and network allowlists before offering a live run. Never rename synthetic fixtures as real data or put API keys into frontend `VITE_*` variables. A new machine does not inherit the operator laptop's private dataset cache or credentials.

## DNS handoff

Only after Azure returns its actual static IPv4/hostname, give the domain owner public records: apex `A` → that IPv4 and `www` `CNAME` → the canonical hostname (or apex). Never invent an address, and remove conflicting apex/`www` records only after review. No registrar password, API key, client secret or database password is needed. After DNS propagates, change `APP_HOST`, `PUBLIC_BASE_URL` and exact `ALLOWED_ORIGINS` together. Set `APP_HOSTS` to a comma-separated list of the canonical hostname and verified aliases (including `www` and the old Azure hostname if retained); Caddy obtains certificates for these real names and redirects aliases to `APP_HOST`. Recreate API/worker/proxy and verify public HTTPS and anonymous-session isolation again. Existing Azure hostname cookies are not transferable to a different domain; visitors begin a new anonymous workspace there unless a deliberate migration is implemented.

## Current verification boundary

Run `python3 ops/azure/check-package.py` from the app directory for repeatable credential-safety and production-topology checks. It uses only the Docker Compose CLI and temporary test credentials, so no daemon, live account or cloud calls are needed. The deployment script separately runs Linux native-library imports and validates the built Caddy configuration before stopping an existing release.

The repository workflow `.github/workflows/azure-container-check.yml` uses a standard GitHub-hosted Ubuntu runner and no account secrets. On relevant pull requests or manual dispatch it builds both Linux images from locks, imports native science/PDF libraries as UID 10001, validates Caddy and production assets, then runs a disposable private PostGIS/API/worker stack through migration, non-superuser provisioning, anonymous-session isolation, CSRF checks and worker heartbeat. It neither deploys to Azure nor changes billing. A successful hosted run is required evidence; adding the workflow does not itself mean that run has passed.

Locally verified: shell/Python syntax, Compose interpolation/topology, private service ports, shared persistent evidence volume, source-tagged images, no overwrite of private credentials, and mode-0600 runtime creation. Docker Desktop's daemon was unavailable, so no local container build/runtime/restore is claimed. The deployment operator must record the Linux build, live HTTPS browser journey and restore check before marking the hosted release complete.
