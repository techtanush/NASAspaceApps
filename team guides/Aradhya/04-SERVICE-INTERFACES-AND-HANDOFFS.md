# Aradhya interfaces and handoffs

Use the exact accepted API/domain contract. Shared03 fixes the frontend/platform/science-renderer seams. The interface's job is to present persisted evidence and request valid user actions, not infer hidden measurements.

## From Tanush

Exported OpenAPI/contract version/hash, safe scenario/capability IDs, actual local profile URL, draft read/autosave/fingerprint/accept endpoints, rover/run creation/actions, snapshot selection/version/cursor, candidate/target/qualification/test/portfolio evidence reads, operations/receipts/critiques/reviews, display-layer manifests and async exports.

Generated client and MSW fixtures must agree with those shapes. Report missing input/read fields or nullability immediately using a concrete request/response and architecture requirement ID. Do not create a parallel production API or assume unlisted endpoints persist your changes. Safe capabilities show credential presence, never credentials.

SSE data is a committed RunEvent with seq/mode/state/evidence references. Deduplicate by run_id+seq; refetch snapshot after gaps/expiry/reconnect; display server-confirmed scientific states. A pending event or animation does not grant a scientific verdict.

## From Ayan through the platform

Registered display-layer manifests and image/artifact URLs; metric names/units/support/classes; target body/frame; source valid fractions; route geometry/telemetry and exact violations; concise scientific captions. Only the platform supplies authorized artifact access and real persisted evidence IDs. Ask for missing affine/corners/legend rather than guessing from image aspect ratio or treating every coordinate pair as Earth.

Scientific values are read-only in the UI except clearly labeled user-owned input editing that creates accepted revisions. Keep unavailable physical clearance/sample chemistry/navigation proof visible. A colored thermal/mineral overlay is not automatically a validated match.

## To Tanush

Provide U0/U1 tested commits, frontend package scripts/lock, accepted schema hash/client generation instructions, mock-development switch and fixture cases, real API integration report, accessible UI assets and browser tests. Avoid modifying backend startup scripts: supply exact expected frontend commands and ports for Tanush's Compose/Make wrapper.

Your renderer implements the F0 pure port under `rendering/passport/`. Accept frozen PassportExportBundle+provided validated image assets+format, return bytes/MIME/safe filename/file hash/renderer version. No SQL/model/network or current mutable run lookup. Supply independent fixture tests so Tanush can call it without a browser. Python dependency additions go through Tanush's lock owner.

## Requests and blockers

Use `team handoffs/aradhya/` for schema/dependency requests and reproducible defects. Include field path, expected semantic/unit/state, actual behavior, effect on user flow, test case and proposed nonbreaking fix. Continue component/renderer work against visible fixtures while a backend dependency is pending. Do not silently ship a screen whose button has no real eventual action.

## C1 scientific assurance seam

Follow your [scientific credibility implementation requirements](07-SCIENTIFIC-CREDIBILITY-REQUIREMENTS.md) and [shared gate06](../../team%20coordination/06-SCIENTIFIC-CREDIBILITY-AND-RELEASE-GATE.md). Include actual SC gate/SCI test evidence, policy/algorithm/source hashes, validated claim scope and visible unknowns in your checkpoint. The required C1 audit must cross the real science→backend→UI/export boundary before combined acceptance. Missing/unrun external validation remains explicit; it cannot be called passed.
