"""``DIAGNOSE_RESULT``: failure-to-action policy (architecture 12 section 8, 08 section 4.12, 40 section 6).

* verified ``FAIL`` / ``ROUTE`` -> ``NEW_ROUTE`` with the next untried registered strategy (``WAYPOINT_RETURN`` ->
  ``EXPOSURE_COVERAGE``), else ``NEW_CANDIDATE`` while candidate switches remain, else no repair;
* ``EXHAUSTIVE_INFEASIBLE`` -> the **ANALOG vs ROVER rule**: the optimistic certificate is re-run with rover-dependent
  constraints removed (slope cap -> 90 deg, battery unbounded) but every terrain mask kept.  Feasible -> ``ROVER``
  (``NEW_CONTRACT_REQUIRED`` only; never an automatic action); still infeasible -> ``ANALOG`` (``NEW_CANDIDATE`` while
  switches remain, else ``COMPOSITE_PORTFOLIO``);
* ``BUDGET_EXHAUSTED`` -> ``SEARCH_LIMIT`` with a different untried strategy, else nothing;
* missing energy model -> ``DATA`` / ``DATA_REPAIR``.

No thresholds, rover limits or reserves are ever changed by a repair.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from analogforge.ports import catalog
from analogforge.ports.common import EvidenceRef, FailureCategory, RuntimeMode, ScienceIssue
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science_payloads import (
    AttemptSummary,
    ConstraintsArtifact,
    DiagnoseResultInput,
    DiagnoseResultPayload,
    RouteStrategy,
    RouteViolation,
)
from analogforge.science.routing import GridArrays
from analogforge.science.routing.certificate import Certificate, compute_certificate
from analogforge.science.routing.search import Problem, prepare_problem, search_route

_REMOVED_CAP_DEG: Final = 89.999999
_UNBOUNDED_WH: Final = 1.0e12

BUDGET_ALTERNATIVES: Final[tuple[RouteStrategy, ...]] = (
    "EXPOSURE_COVERAGE",
    "MINIMUM_FEASIBLE_ROUTE",
    "WAYPOINT_RETURN",
)


@dataclass(frozen=True)
class DiagnoseOutput:
    payload: DiagnoseResultPayload
    issues: list[ScienceIssue]


def _tried_strategies(constraints: ConstraintsArtifact, history: Sequence[AttemptSummary]) -> set[str]:
    tried: set[str] = {a.strategy for a in history if a.candidate_window_id == constraints.candidate_window_id}
    tried.add(constraints.strategy)
    return tried


def _route_strategy(
    constraints: ConstraintsArtifact, tried: set[str], violations: Sequence[RouteViolation]
) -> RouteStrategy | None:
    """Next untried strategy that addresses the observed violations without relaxing any constraint."""
    codes = {v.code for v in violations}
    failed = constraints.strategy
    candidates: list[RouteStrategy] = []
    if failed == "WAYPOINT_RETURN":
        candidates.append("EXPOSURE_COVERAGE")
    if codes and codes <= {"ENERGY_RESERVE_SHORTFALL", "MAX_DISTANCE_EXCEEDED", "MAX_DURATION_EXCEEDED"}:
        candidates.append("MINIMUM_FEASIBLE_ROUTE")
    if codes & {"FORBIDDEN_INTERSECTION", "UNKNOWN_TERRAIN", "MAX_SLOPE_EXCEEDED", "DISCONTINUOUS_ROUTE"}:
        candidates.append("RECOVERY_ALTERNATIVE")
    for strategy in candidates:
        if strategy not in tried:
            return strategy
    return None


def _repairs_for_new_route(
    strategy: RouteStrategy | None, inp: DiagnoseResultInput
) -> tuple[list[str], str | None, RouteStrategy | None]:
    if strategy is not None and inp.remaining_route_repairs > 0:
        return ["NEW_ROUTE"], "NEW_ROUTE", strategy
    if inp.remaining_candidate_switches > 0:
        return ["NEW_CANDIDATE"], "NEW_CANDIDATE", None
    return [], None, None


def _relaxed_constraints(constraints: ConstraintsArtifact) -> ConstraintsArtifact:
    """Rover-dependent limits removed; terrain masks, tasks, exposures and route-domain bounds untouched."""
    return constraints.model_copy(
        update={
            "surface_slope_cap_deg": _REMOVED_CAP_DEG,
            "energy": constraints.energy.model_copy(update={"battery_wh": _UNBOUNDED_WH, "min_reserve_pct": 0.0}),
        }
    )


def _certificate_of(
    constraints: ConstraintsArtifact,
    grid: GridArrays | None,
    mode: RuntimeMode,
    cancel: Callable[[], None] | None,
    *,
    relaxed: bool,
) -> tuple[Certificate, Problem]:
    problem = prepare_problem(
        constraints, grid, mode=mode, slope_cap_deg=_REMOVED_CAP_DEG if relaxed else None, check_cancelled=cancel
    )
    cert = compute_certificate(
        problem.graph,
        constraints,
        problem.provider,
        problem.costs,
        problem.start,
        problem.task_nodes,
        unbounded_battery=relaxed,
    )
    return cert, problem


def analog_vs_rover(
    constraints: ConstraintsArtifact,
    grid: GridArrays | None,
    mode: RuntimeMode,
    cancel: Callable[[], None] | None = None,
) -> tuple[FailureCategory, Certificate, Certificate, str]:
    """Return ``(category, original certificate, relaxed certificate, method)`` for an exhaustive-infeasible search."""
    original, _ = _certificate_of(constraints, grid, mode, cancel, relaxed=False)
    relaxed, _ = _certificate_of(constraints, grid, mode, cancel, relaxed=True)
    if original.infeasible:
        return ("ANALOG" if relaxed.infeasible else "ROVER"), original, relaxed, "certificate re-run"
    # infeasibility came from exhaustive enumeration: decide with the relaxed problem searched under the same budgets
    relaxed_constraints = _relaxed_constraints(constraints)
    outcome = search_route(
        relaxed_constraints,
        canonical_sha256(relaxed_constraints),
        grid=grid,
        mode=mode,
        check_cancelled=cancel,
    )
    status = outcome.payload.search_status
    if status == "FOUND":
        return "ROVER", original, relaxed, "relaxed search found a route"
    if status == "EXHAUSTIVE_INFEASIBLE":
        return "ANALOG", original, relaxed, "relaxed search exhausted"
    return "SEARCH_LIMIT", original, relaxed, "relaxed search hit its budget"


def diagnose_result(
    inp: DiagnoseResultInput,
    *,
    grid: GridArrays | None = None,
    mode: RuntimeMode,
    diagnosis_evidence_key: str = "diagnosis",
    check_cancelled: Callable[[], None] | None = None,
) -> DiagnoseOutput:
    constraints = inp.constraints
    tried = _tried_strategies(constraints, inp.attempt_history)
    evidence = EvidenceRef(local_key=diagnosis_evidence_key)
    violated = sorted({v.constraint_id for v in inp.violations})
    verification = inp.verification

    def payload(
        primary: FailureCategory | None,
        repairs: list[str],
        recommended: str | None,
        strategy: RouteStrategy | None,
        scope: str,
        explanation: str,
        *,
        violated_ids: list[str] | None = None,
        secondary: list[FailureCategory] | None = None,
    ) -> DiagnoseOutput:
        return DiagnoseOutput(
            DiagnoseResultPayload.model_validate(
                {
                    "primary_category": primary,
                    "secondary_categories": secondary or [],
                    "violated_constraint_ids": violated if violated_ids is None else violated_ids,
                    "permitted_repairs": repairs,
                    "recommended_repair": recommended,
                    "recommended_strategy": strategy,
                    "proof_scope": scope,
                    "explanation": explanation,
                    "diagnosis_evidence": evidence,
                }
            ),
            [],
        )

    status = inp.search_status
    if status == "EXHAUSTIVE_INFEASIBLE":
        cause, original, relaxed, method = analog_vs_rover(constraints, grid, mode, check_cancelled)
        ids = original.violated_constraint_ids
        if not ids and constraints.strategy != "WAYPOINT_RETURN":
            ids = sorted(catalog.constraint_exposure(s.requirement_id) for s in constraints.exposures)
        domain = any(r.domain_bound for r in original.reasons)
        scope = (
            "domain-bounded certificate: the route-domain bound (maximum distance / usable energy) of the "
            "frozen constraints "
            "makes the requirement unreachable; not proof that no longer route exists"
            if domain
            else "discrete graph of this zone under the frozen constraints (no lossy pruning)"
        )
        if cause == "ROVER":
            return payload(
                "ROVER",
                ["NEW_CONTRACT_REQUIRED"],
                None,
                None,
                scope,
                f"Infeasible under the rover limits but feasible with the slope cap removed and the battery "
                f"unbounded ({method}); "
                "the rover limit is the binding cause. Only a new, user-approved contract or rover revision "
                "can change this.",
                violated_ids=ids,
            )
        if cause == "ANALOG":
            analog_repair = "NEW_CANDIDATE" if inp.remaining_candidate_switches > 0 else "COMPOSITE_PORTFOLIO"
            return payload(
                "ANALOG",
                [analog_repair],
                analog_repair,
                None,
                scope,
                f"Infeasible even with rover limits removed ({method}): the terrain of this zone cannot host the test.",
                violated_ids=ids,
            )
        alt = [s for s in BUDGET_ALTERNATIVES if s not in tried]
        limit_repairs, limit_rec, limit_strategy = _repairs_for_new_route(alt[0] if alt else None, inp)
        return payload(
            "SEARCH_LIMIT",
            limit_repairs if limit_rec == "NEW_ROUTE" else [],
            limit_rec if limit_rec == "NEW_ROUTE" else None,
            limit_strategy,
            "bounded search; the ANALOG/ROVER classification could not be decided within the search budget",
            "The relaxed problem could not be decided within the search budget; no cause is claimed.",
            violated_ids=ids,
        )

    if status == "BUDGET_EXHAUSTED":
        alt = [s for s in BUDGET_ALTERNATIVES if s not in tried]
        if alt and inp.remaining_route_repairs > 0:
            return payload(
                "SEARCH_LIMIT",
                ["NEW_ROUTE"],
                "NEW_ROUTE",
                alt[0],
                "bounded search; not proof that no route exists",
                f"The search budget was exhausted before a verified route was found; "
                f"a different registered strategy ({alt[0]}) is untried.",
                violated_ids=[],
            )
        return payload(
            "SEARCH_LIMIT",
            [],
            None,
            None,
            "bounded search; not proof that no route exists",
            "The search budget was exhausted and no different registered strategy remains or no route repair is left.",
            violated_ids=[],
        )

    if status == "ERROR":
        return payload(
            "SYSTEM",
            [],
            None,
            None,
            "engine error; no scientific claim",
            "The route engine reported an error.",
            violated_ids=[],
        )

    if verification.outcome == "PASS":
        return payload(
            None,
            [],
            None,
            None,
            "evaluated route only",
            "The verified route meets every included mandatory criterion; nothing to repair.",
            violated_ids=[],
        )

    if verification.outcome == "FAIL":
        strategy = _route_strategy(constraints, tried, inp.violations)
        repairs, recommended, rec_strategy = _repairs_for_new_route(strategy, inp)
        return payload(
            "ROUTE",
            repairs,
            recommended,
            rec_strategy,
            "evaluated route only",
            "The evaluated route missed "
            + (", ".join(violated) if violated else "a criterion")
            + "; this does not show that no other route exists.",
        )

    inconclusive = verification.failure_category
    if inconclusive == "DATA":
        return payload(
            "DATA",
            ["DATA_REPAIR"],
            "DATA_REPAIR",
            None,
            "evaluated route only",
            "Required evidence (for example the energy model) is missing, so the criterion cannot be "
            "evaluated; supply it in a new run input.",
            violated_ids=violated,
        )
    if inconclusive == "SEARCH_LIMIT":
        alt = [s for s in BUDGET_ALTERNATIVES if s not in tried]
        if alt and inp.remaining_route_repairs > 0:
            return payload(
                "SEARCH_LIMIT",
                ["NEW_ROUTE"],
                "NEW_ROUTE",
                alt[0],
                "bounded search; not proof that no route exists",
                "Search limit reached.",
                violated_ids=[],
            )
        return payload(
            "SEARCH_LIMIT",
            [],
            None,
            None,
            "bounded search; not proof that no route exists",
            "Search limit reached; no untried strategy.",
            violated_ids=[],
        )
    if inconclusive == "REQUIREMENT":
        return payload(
            "REQUIREMENT",
            [],
            None,
            None,
            "requirement as stated",
            "The requirement is underspecified or cannot be met by moving a route.",
            violated_ids=violated,
        )
    return payload(
        "SYSTEM",
        [],
        None,
        None,
        "no scientific claim",
        "Verification was inconclusive for a system reason (for example a stale input hash).",
        violated_ids=violated,
    )
