"""Code-owned transition graph. Roles can only propose issued actions."""

from typing import Any

TERMINAL = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"VALIDATING"}),
    "VALIDATING": frozenset({"CHARACTERIZING"}),
    "CHARACTERIZING": frozenset({"DISCOVERING"}),
    "DISCOVERING": frozenset({"QUALIFYING", "BUILDING_PASSPORT"}),
    "QUALIFYING": frozenset({"CRITIQUING"}),
    "CRITIQUING": frozenset({"AWAITING_REVIEW", "BUILDING_PASSPORT", "CHARACTERIZING", "DISCOVERING", "QUALIFYING"}),
    "AWAITING_REVIEW": frozenset({"CRITIQUING", "DESIGNING_TEST", "QUALIFYING"}),
    "DESIGNING_TEST": frozenset({"VERIFYING", "BUILDING_PASSPORT"}),
    "VERIFYING": frozenset({"DIAGNOSING", "BUILDING_PASSPORT"}),
    "DIAGNOSING": frozenset({"REPLANNING", "BUILDING_PASSPORT"}),
    "REPLANNING": frozenset({"DESIGNING_TEST", "DISCOVERING", "BUILDING_PASSPORT"}),
    "BUILDING_PASSPORT": frozenset({"COMPLETED"}),
    "BLOCKED": frozenset(),
    "COMPLETED": frozenset(),
    "FAILED": frozenset(),
    "CANCELLED": frozenset(),
}


class TransitionError(ValueError):
    code = "INVALID_TRANSITION"


def validate_transition(current: str, target: str, *, resume_state: str | None = None) -> None:
    if target == current:
        return
    if current not in TERMINAL and target in {"CANCELLED", "BLOCKED", "FAILED"}:
        return
    if current == "BLOCKED" and target == resume_state:
        return
    if target not in TRANSITIONS.get(current, frozenset()):
        raise TransitionError(f"Transition {current} to {target} is not allowed")


def allowed_actions(snapshot: dict[str, Any]) -> frozenset[str]:
    state = snapshot["state"]
    if state in TERMINAL:
        return frozenset({"CANCEL"})
    actions = {"CANCEL"}
    if state == "BLOCKED":
        actions.add("RETRY")
    if state == "AWAITING_REVIEW":
        actions.update({"SELECT_CANDIDATE", "NOMINATE_CANDIDATE", "BUILD_PORTFOLIO", "SELECT_PORTFOLIO"})
        review = snapshot.get("pending_review")
        if review and review.get("kind") != "EVIDENCE_READY" and review.get("status") == "PENDING":
            actions.update(review["allowed_actions"])
        elif snapshot.get("rover_revision_id") and snapshot.get("selected_candidate_id"):
            actions.add("PROVE_IT")
    return frozenset(actions)
