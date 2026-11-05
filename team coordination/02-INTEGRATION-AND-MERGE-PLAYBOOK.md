# Integration and merge playbook

Tanush is the integrator. Ayan and Aradhya deliver tested owned modules; they do not independently merge or force-update main. All operations here are the future implementation workflow. This planning setup creates the shared baseline and worktrees only, with no application features claimed complete.

## Checkpoints

| Checkpoint | Producer | Must be present before consumers depend on it |
| --- | --- | --- |
| F0 Platform foundation | Tanush | Locks/native imports, domain/OpenAPI, ports, healthy DB/API/worker, local commands, safe mode/identity/artifact context. |
| S0 Scientific core | Ayan | Pure analytic terrain/comparison/energy/graph fixtures, typed facade, independent verifier, deterministic expected arithmetic. |
| U0 Functional interface shell | Aradhya | Generated C0/F0 client, accessible navigation/forms/matrix, visible mock preview, snapshot/SSE/error handling scaffolding. |
| I1 First combined slice | Tanush with all modules | Actual API persists mission/rover, invokes Ayan facade, serves Aradhya UI, produces first real synthetic evidence. |
| S1 Sources and full modeled science | Ayan | Earth/Mars/Moon source paths, honest optional-layer states, discovery controls, portfolio, raster-route verification. |
| U1 Complete experience/export | Aradhya | Test lab/history/critic/review/portfolio/passport, pure renderer, responsive/browser/negative-state tests. |
| P1 Live agent and recovery | Tanush | Ten roles, strict tool loop, policy commits, job recovery/cancellation, actual credential preflight or explicit blocked gate. |
| RC Combined release candidate | Tanush | Whole-system tests, integrity/source reports, browser journey, restart/reconnect, exports and final ledger. |

Submit a **specific tested commit SHA**, not just "latest branch". A feature branch can continue after submitting a checkpoint. Its new head is not automatically the tested version. Small early checkpoints reduce the chance of a giant final conflict.

## Contributor preflight before handoff

1. Confirm current branch/worktree is yours. Record `git rev-parse HEAD` and the main checkpoint merged into it.
2. Ensure no unresolved merge markers, staged surprises, secrets, downloaded large products, local database files or ignored-data additions.
3. Run your owned test suite, shared schema/client/port checks, type checks and applicable build. Record actual exit codes/counts and tool versions.
4. Run changed-path ownership checker against accepted main. Resolve any unauthorized edits by moving the request to the owner, not by hiding the file from the report.
5. Populate `team handoffs/<person>/<checkpoint>/handoff-report.json` and a short explanation. Include positive, negative and unknown outcomes; exact missing external inputs; commands to reproduce from a clean checkout.
6. Commit your handoff and implementation. A clean status plus failing tests is not merge ready. A passing test suite against hardcoded collaborator responses is not integrated acceptance.

Branch-specific tests are detailed in each person's05 file. The shared architecture utility validates specification integrity only; it cannot replace app tests.

## Same-computer integration

Because local worktrees share refs, Tanush can inspect the other feature branches without copying files or changing their checkout. The merge source is the submitted commit. Do not run `git switch main` inside Ayan's or Aradhya's worktree: main is already checked out at the root and their files must remain isolated.

Use a temporary integration branch/checkout rooted at the latest accepted main for each candidate merge. Suggested location: `.local-team/verify/<checkpoint>`, ignored by Git. Merge the tested producer commit there with `--no-ff`. Run the required combined checks on that exact resulting commit. If successful and main has not advanced, advance the root main with `--ff-only` to the tested integration commit. If main advanced, rebuild the candidate from the new main and rerun affected checks. Do not claim a merge was tested when only its source branch was tested.

Example command shapes; replace placeholders with verified paths/SHAs before use:

```bash
rtk proxy git -C "/path/to/root" worktree add -b "integration/verify-I1" "/path/to/root/.local-team/verify/I1" main
rtk proxy git -C "/path/to/root/.local-team/verify/I1" merge --no-ff "TESTED_COMMIT_SHA"
```

Run integration checks in that candidate's `analogforge/`, using its own runtime profile. On success:

```bash
rtk proxy git -C "/path/to/root" merge --ff-only "integration/verify-I1"
```

These examples are a procedure, not instructions to merge placeholder SHAs or start concurrent integration candidates that update main without coordination. Tanush serializes advancement of main. Retain a checkpoint tag/commit record and handoff report after a successful gate.

## Importing from another computer

The contributor creates an offline bundle from their committed feature branch:

```bash
rtk proxy git bundle create "ayan-handoff.bundle" ayan/science-data-verification
```

Aradhya uses her matching branch. A full-branch bundle includes necessary ancestors, avoiding missing-prerequisite surprises for a small source repository. Ignored secrets/data are not included, but verify tracked content before bundling. Tanush receives the file, verifies it, and fetches into an import reference rather than overwriting an active local branch:

```bash
rtk proxy git -C "/path/to/root" bundle verify "/path/to/ayan-handoff.bundle"
rtk proxy git -C "/path/to/root" fetch "/path/to/ayan-handoff.bundle" "ayan/science-data-verification:refs/remotes/import-ayan/science-data-verification"
```

Check the submitted SHA resolves to the fetched history and contains the expected accepted-base checkpoint. Then run the same isolated integration process. Do not merge an unknown bundle tip blindly. File transfer itself is a human/team action; no email/chat tool is authorized by this guide.

To send an accepted main checkpoint back offline, Tanush creates a new bundle containing main. The recipient fetches it into `refs/remotes/integration/main`, then merges that reference into their own feature branch. Do not assume the initial bundle or its origin reference updates automatically. Once a GitHub remote is explicitly created later, the same commit/ownership/test discipline applies through normal fetch/PR workflows; no GitHub setup is required now.

## Integration order and checks

Integrate F0 first. S0 and U0 can then be imported in either order if each builds with typed collaborator doubles and exposes limitations. I1 must replace doubles with the real facade/API and run one cross-boundary case. Merge later S1/U1/P1 checkpoints incrementally, not three entire untested final apps at hour47.

Before accepting each candidate run: database migration up on empty and previous seeded schema; generated contract diff/client compilation; Python imports and owned+integration tests; frontend type/build/tests; mode and source-policy integrity; no new ownership conflicts. When a checkpoint touches routes or report/UI behavior also run the full synthetic browser journey, export digest check and reload/reconnect/cancel paths. Native-library changes require rebuilding the actual worker image.

Final RC requires:

- One immutable accepted mission/rover, computed synthetic initial route FAIL then repaired route PASS, unchanged input hashes, persisted receipts/attempts.
- Both target-body paths, no-rover site-only investigation, negative control, missing mineral/thermal evidence, scale mismatch, portfolio co-location and bounded search INCONCLUSIVE.
- Real source and live AI gates exercised where credentials/data exist; otherwise exact blocked gates remain visible and no live-success claim is made.
- Clean rebuild from committed locks, private local DB profiles, restart/fenced worker recovery, authoritative SSE resync, safe exports and all required58 product rows traced.

## Conflict policy

Classify a conflict before resolving: shared contract (Tanush decides with both consumer changes), scientific meaning (Ayan proposes evidence-supported correction), UI rendering/client (Aradhya reconciles with exported contract), dependency/native runtime (Tanush resolves lock with Ayan import tests). Never keep both conflicting enum definitions or fix a test by weakening the accepted requirement.

Resolve on the integration candidate or producer branch according to ownership, record the fix, rerun affected and combined tests, then submit a new tested SHA. Never `reset --hard`, force-push or delete someone else's work to get a green merge. No deployment or external publication happens automatically after a local merge.
