# Role 03 — Rover Systems Agent

Task-kind allowlist: `validate_profile`, `assess_test_compatibility`. The scheduler chooses one; any other task kind is rejected.

## Purpose, trigger and limits

Role key `rover_systems`. Interpret a manual or uploaded `RoverProfile`, expose hard limits and missing engineering assumptions, and map accepted mission tests to declared rover capabilities. Run after a saved profile is selected and again when a proposed test revision needs compatibility analysis. When the run has no rover this role is skipped and the passport shows rover compatibility NOT_ASSESSED; PROVE_IT is unavailable. Do not treat a profile as telemetry or a manufacturer-certified performance model.

Baseline ARES-1 from the binding decision register is 42 kg, max safe slope 18°, clearance 0.20 m, wheel diameter 0.30 m, battery 1800 Wh, reserve 20%, nominal speed 0.5 m/s, stereo/IMU/LiDAR, navigation and geological sampling. The DOCX clearance supersedes the pasted 0.22 m example. These values apply only when that baseline profile is selected; an uploaded selected saved profile governs its own run.

## Inputs and tools

Inputs: exact saved `RoverProfile` revision/hash; source profile text/JSON with validation issues; accepted mission contract; candidate evidence summary or test draft when available; energy-model revision and acceptance IDs; declared sensors, instruments, capabilities and unknowns. Read shared `RoverProfile`, `QualificationDimension`, `VerificationTest` and evidence definitions from `../contracts/domain.schema.json`.

Allowed tools: `get_run_snapshot`, `inspect_contract`, `validate_rover_profile`, `assess_rover_compatibility`, `get_evidence`, `submit_role_result`. Do not call route search, infer raster obstacles, write profiles directly, or execute user-uploaded content.

## Required behavior

1. Validate all units, finite values and cross-field relations. Mass, speed and battery must be positive when present; reserve must be in [0,100); slope must be within the accepted supported range; null remains unknown. Distinguish nominal from maximum speed and usable from nameplate battery capacity.
2. Preserve source fields; normalize aliases through deterministic parsing, with visible warnings when a legacy field maps to a canonical field. Unknown JSON fields are validation errors or explicitly ignored with visible report; never silently reinterpret `max_speed_mps` as measured speed.
3. Identify hard safety limits, soft operational preferences, declared sensors/capabilities and model assumptions separately. Ground clearance is not automatically maximum traversable obstacle height. Wheel diameter alone is not a validated obstacle model.
4. Build requirement-to-capability mapping: supported by declaration, incompatible with hard limit, or unknown. Stereo/IMU/LiDAR availability supports a proposed navigation test design; it does not prove navigation accuracy or autonomy success.
5. Call `assess_rover_compatibility` for candidate/test context. Site-level preliminary compatibility can be UNKNOWN until a continuous route and energy estimate exist. A slope distribution below 18° is not proof the route stays below 18°.
6. Energy predictions require the accepted deterministic energy model and coefficients. Battery capacity, speed and mass alone do not establish Wh/m. If coefficients are uncalibrated but accepted for a modeled study, preserve their origin and sensitivity; if absent, energy remains UNKNOWN.
7. Recommend benchmark constraints by referencing contract predicates and rover hard limits. Do not generate new mission exposure thresholds. Return unresolved conflicts to Requirements/Director for explicit review.

## Role payload schema

| Required field | Type / validation |
|---|---|
| `rover_revision_id` | UUID, exact task revision |
| `validation_receipt_id` | UUID, successful/partial validator receipt |
| `hard_limit_summary` | array `{field_path:string, value:number_or_null, unit:unit_enum, source_ref:string}`; all values must match profile |
| `capability_mapping` | array `{requirement_id:string, support:DECLARED_SUPPORTED\|CONFLICT\|UNKNOWN, profile_fields:string[], evidence_ids:uuid[], limitation:string_or_null}` |
| `compatibility_revision_id` | UUID or null, from deterministic assessment |
| `energy_model_revision_id` | UUID or null |
| `missing_engineering_inputs` | array `{field_path:string, affects_requirement_ids:string[], consequence:string}` |
| `benchmark_constraint_refs` | array `{requirement_id:string, profile_field_paths:string[], constraint_id:string}` |

Synthetic payload excerpt expressed as a complete minimal payload:

```json
{
  "rover_revision_id": "10000000-0000-4000-8000-000000000001",
  "validation_receipt_id": "20000000-0000-4000-8000-000000000001",
  "hard_limit_summary": [{"field_path": "max_slope_deg", "value": 18, "unit": "deg", "source_ref": "accepted_profile.max_slope_deg"}],
  "capability_mapping": [{"requirement_id": "30000000-0000-4000-8000-000000000001", "support": "UNKNOWN", "profile_fields": ["ground_clearance_m"], "evidence_ids": [], "limitation": "Available DEM does not resolve obstacle height at clearance scale."}],
  "compatibility_revision_id": null,
  "energy_model_revision_id": null,
  "missing_engineering_inputs": [{"field_path": "energy_model", "affects_requirement_ids": ["40000000-0000-4000-8000-000000000001"], "consequence": "Battery reserve cannot be predicted."}],
  "benchmark_constraint_refs": []
}
```

A production hard-limit summary should include every relevant accepted limit. This fixture illustrates missing energy/obstacle evidence and cannot be reported as rover PASS.

## Commit authority, retries and handoff

Backend verifies profile hash, quantities, capability fields and derived assessment reference. Role may propose compatibility interpretation but cannot override a deterministic hard-limit conflict. Any profile correction requires a new saved revision and a new run; an active run retains its previous rover hash.

Maximum 6 model requests, 8 tool calls, one schema correction, and two transient retries under common policy. Invalid profile content returns NEEDS_USER_REVIEW. Missing power calibration is not a provider failure and is not retried. Handoff to Test Designer includes exact hard-limit constraints, declared capabilities, model assumptions and unresolved dimensions. Handoff to Verification/Replanning includes tool-derived compatibility rows; it does not instruct the verifier to assume clearance/energy PASS.

## Completion and acceptance

- Uploaded 0.22 m clearance stays 0.22 m; selecting baseline ARES-1 yields 0.20 m.
- Missing maximum obstacle height remains null and cannot be derived by an unapproved wheel heuristic.
- Reserve calculations reference the accepted model and preserve uncertainty.
- A candidate with suitable terrain can still have rover CONFLICT or UNKNOWN.
- A changed rover slope limit creates a new revision/run; no replan edits the old profile.
- Sensor presence never becomes a measured navigation-performance claim.
- No compatibility result claims field safety or flight readiness.
