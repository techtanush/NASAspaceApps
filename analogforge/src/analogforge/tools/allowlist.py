"""Allowlist authority; source text can never expand a role's tools."""

from analogforge.ports.catalog import ROLE_KEYS, TOOL_NAMES

READ = {"get_run_snapshot", "inspect_contract", "get_evidence", "submit_role_result"}
ALLOWLISTS = {
    "mission_director": READ | {"optimize_portfolio"},
    "requirements": READ,
    "rover_systems": READ | {"validate_rover_profile", "assess_rover_compatibility"},
    "planetary_target": READ | {"resolve_dataset_coverage", "fetch_dataset", "characterize_target", "compare_evidence"},
    "earth_scout": READ
    | {
        "resolve_dataset_coverage",
        "fetch_dataset",
        "screen_earth_candidates",
        "analyze_earth_candidate",
        "compare_evidence",
        "optimize_portfolio",
    },
    "qualification": READ | {"compare_requirement", "compare_evidence", "optimize_portfolio"},
    "scientific_critic": READ
    | {"review_evidence_bundle", "compare_evidence", "compare_requirement", "resolve_dataset_coverage"},
    "test_designer": READ | {"assess_rover_compatibility", "design_test", "search_route"},
    "verification_replanning": READ
    | {"assess_rover_compatibility", "verify_route", "diagnose_verification", "search_route"},
    "evidence_passport": READ | {"review_evidence_bundle", "build_passport_manifest"},
}
assert set(ALLOWLISTS) == set(ROLE_KEYS)
assert set().union(*ALLOWLISTS.values()) | {"validate_mission_draft"} == set(TOOL_NAMES)


def allowed_tools(role: str, preparation: bool = False) -> frozenset[str]:
    if preparation:
        if role != "requirements":
            raise ValueError("Preparation permits only Requirements")
        return frozenset({"validate_mission_draft", "submit_role_result"})
    return frozenset(ALLOWLISTS[role])
