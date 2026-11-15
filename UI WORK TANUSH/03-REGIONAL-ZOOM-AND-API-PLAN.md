# Tanush regional drill-down and read projections

Required user experience: every target/candidate is inspectable at its actual registered location, including several adjacent windows that share a globe marker. Supply correct detailed assets; Aradhya owns fly-to, cluster expansion and the viewer. This is required scope, not a later optional idea.

## T2 regional delivery steps

1. From an authorized run snapshot, resolve immutable target/candidate evidence and lock. Reject foreign run/workspace/candidate IDs. Use exact candidate bbox/ID and existing display manifest references; no nearest-centre substitution.
2. Reuse existing display artifacts if complete. If a new derivative is needed, create it through existing jobs/registrar/storage outside a read transaction and publish only after success. A GET must never silently download provider data or mutate a locked artifact.
3. Build authorized display manifest/image/mask with exact body/CRS/height reference/affine/extent, units, source resolution and comparison support. Preserve real zeros and masked voids. Expose metadata rather than color-derived pseudo-measurements.
4. Return existing artifact references, not absolute disk paths or signed/provider tokens. The proposed detail envelope lists DisplayLayerManifest IDs; frontend resolves them with existing authenticated transport. No duplicate schema for the scientific manifest.
5. Large-region displays use bounded overviews/tiles via existing infrastructure or a reviewed additive contract. A local viewport may show prepared raster context without photogrammetric 3D. Do not require buildings/mesh/streetview for a complete detail view.
6. On missing/uncomputed/outside data return explicit UNAVAILABLE/PARTIAL and reason, valid footprint/mask where known and metadata. Never fill missing elevations to make the view look continuous.

## T3 proposed API implementation

Paths and schemas are reserved in the shared contract. Implement them only if existing reads are insufficient. Readonly coverage is scoped by body+bbox+scenario+lock+workspace; validate finite ordered bounds/area and supported seam/pole behavior. Include version and coverage basis. Cache by all those keys plus source/config revision, not bbox alone. Do not expose arbitrary local dataset files or unvalidated products.

Before adding routes, inspect api/router.py registration/dependencies and current error envelope; keep authentication, workspace binding, request limits, JSON/media types and error semantics consistent. Amend versioned OpenAPI/kit by the architecture35 process, then test actual router against schema. Publish exact fixture responses. Aradhya must not turn on the adapter until you report the schema/capability delivered.

Coverage availability differs from qualification and display availability. A footprint-only indication must state its basis; it cannot imply sufficient valid cells. Scenario input area eligibility must be enforced authoritatively; reject unsupported10–80km choices with an actionable reason rather than silently swapping regions. If exposing allowed extents/sizes, make it additive and sourced from actual scenario policy.

## T4 benchmark data

Join accepted requirement → candidate qualification → exact comparison/route artifact and evidence receipt. Return values/margins only where observable/operator/unit/support and ancestry agree. Preserve nulls and recorded precision. Never subtract arbitrary lower/upper bounds to invent a margin for PRESENT/GAP or incomparable quantities. Failures remain available; route results from another selected candidate cannot be borrowed. Do not auto-build a portfolio or run multiple rover tests for presentation convenience.

No new endpoint is a prerequisite for Aradhya to build mock UI. Your completed integration note must identify actual available endpoints, schema commit, feature enablement, artifact source and unavailable response. Proposed fields stay proposed until tests prove delivery.
