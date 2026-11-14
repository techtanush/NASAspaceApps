"""One mapping from approved tool names to typed science operations."""

from analogforge.ports.science import ScienceOperation

TOOL_OPERATIONS = {
    "resolve_dataset_coverage": ScienceOperation.RESOLVE_COVERAGE,
    "fetch_dataset": ScienceOperation.FETCH_SOURCE,
    "characterize_target": ScienceOperation.CHARACTERIZE_TARGET,
    "screen_earth_candidates": ScienceOperation.SCREEN_CANDIDATES,
    "analyze_earth_candidate": ScienceOperation.ANALYZE_CANDIDATE,
    "compare_requirement": ScienceOperation.COMPARE_REQUIREMENT,
    "assess_rover_compatibility": ScienceOperation.ASSESS_COMPATIBILITY,
    "design_test": ScienceOperation.DESIGN_BENCHMARK,
    "search_route": ScienceOperation.SEARCH_ROUTE,
    "verify_route": ScienceOperation.VERIFY_ROUTE,
    "diagnose_verification": ScienceOperation.DIAGNOSE_RESULT,
    "optimize_portfolio": ScienceOperation.OPTIMIZE_PORTFOLIO,
}
OPERATION_TO_TOOL = {v: k for k, v in TOOL_OPERATIONS.items()}
OPERATION_TO_TOOL.update(
    {
        ScienceOperation.INGEST_LOCAL_DATASET: "fetch_dataset",
        ScienceOperation.BUILD_DISPLAY_LAYERS: "characterize_target",
        ScienceOperation.AUDIT_EVIDENCE: "review_evidence_bundle",
    }
)
