"""``OPTIMIZE_PORTFOLIO``: deterministic exhaustive subset enumeration (architecture 13, guide 08 section 4.13).

Pure function over the kit input model.  Rules implemented here:

* Coverage is binary and conservative.  A row covers a requirement at a window only when it is ``PASS``, has no open
  blocking critic issue and, for route-dependent observables (``catalog.ROUTE_DEPENDENT_OBSERVABLES``), is ``FINAL``
  (and the window's verification, when supplied, is ``PASS``).  UNKNOWN / FAIL / GAP / PARTIAL rows never cover.
* Requirements sharing ``parameters.co_location_group`` form one *coupled* item: covered by a window only when every
  member row there is ``PASS`` + ``FINAL`` with no blocking critic issue **and** ``verification_by_window_id[window]``
  is ``PASS``.  Rows of different windows never combine.  Each member weight is counted once.
* ``NOT_NATURALLY_REPRODUCIBLE`` requirements are physical gaps: never optimised, always ``GAP`` and residual.
* Lexicographic objective (maximised componentwise): mandatory covered weight, optional covered weight, negative site
  count, evidence-strength rank; remaining ties go to the lexicographically smallest sorted ``window_id`` tuple.
  Evidence strength per covered item: 3 = verified (verification PASS), 2 = FINAL PASS, 1 = PRELIMINARY PASS.
* More than :data:`MAX_ELIGIBLE` eligible windows (windows that cover at least one item) is ``RESOURCE_LIMIT``.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Final

from analogforge.ports import catalog
from analogforge.ports.common import EvidenceRef, RuntimeMode
from analogforge.ports.domain_models import Requirement
from analogforge.ports.science_payloads import (
    OptimizePortfolioInput,
    OptimizePortfolioPayload,
    PortfolioAssignment,
    QualificationRowInput,
)
from analogforge.science.errors import ScienceError

MAX_ELIGIBLE: Final = 12
ALGORITHM_ID: Final = "exhaustive-subset-v1"
_GAP_OPERATOR: Final = "NOT_NATURALLY_REPRODUCIBLE"


@dataclass(frozen=True)
class _Item:
    """An independently coverable requirement or a coupled group (members share one verified route)."""

    item_id: str
    members: tuple[Requirement, ...]
    coupled: bool


def check_single_scope(
    *, mode: RuntimeMode, evidence_modes: Iterable[RuntimeMode] = (), mission_revisions: Iterable[int] = ()
) -> None:
    """Reject synthetic/live mixing and mixed mission revisions before any optimisation (fixture 7)."""
    modes = set(evidence_modes)
    if modes - {mode}:
        raise ScienceError(
            f"portfolio inputs mix modes {sorted(modes | {mode})}", code="INPUT_INVALID", detail_code="MODE_MISMATCH"
        )
    revisions = set(mission_revisions)
    if len(revisions) > 1:
        raise ScienceError(
            f"portfolio inputs mix mission revisions {sorted(revisions)}",
            code="INPUT_INVALID",
            detail_code="REVISION_MISMATCH",
        )


def _route_dependent(req: Requirement) -> bool:
    return req.observable in catalog.ROUTE_DEPENDENT_OBSERVABLES


def _is_gap(req: Requirement) -> bool:
    return req.operator == _GAP_OPERATOR


def optimize_portfolio(
    inputs: OptimizePortfolioInput,
    *,
    portfolio_evidence: EvidenceRef,
    mode: RuntimeMode | None = None,
    evidence_modes: Iterable[RuntimeMode] = (),
    mission_revisions: Iterable[int] = (),
    check_cancelled: Callable[[], None] | None = None,
) -> OptimizePortfolioPayload:
    """Select the smallest, strongest set of candidate windows covering the most reproducible requirement weight."""
    if mode is not None:
        check_single_scope(mode=mode, evidence_modes=evidence_modes, mission_revisions=mission_revisions)

    reqs = sorted(inputs.requirements, key=lambda r: r.id)
    req_ids = [r.id for r in reqs]
    if len(set(req_ids)) != len(req_ids):
        raise ScienceError("duplicate requirement ids", code="INPUT_INVALID")
    windows = sorted(c.window_id for c in inputs.candidates)
    if len(set(windows)) != len(windows):
        raise ScienceError("duplicate candidate window ids", code="INPUT_INVALID")
    rows: dict[tuple[str, str], QualificationRowInput] = {}
    for row in inputs.qualification_rows:
        if row.candidate_window_id not in windows or row.requirement_id not in req_ids:
            raise ScienceError(
                f"qualification row ({row.candidate_window_id}, {row.requirement_id}) names an unknown "
                "candidate or requirement",
                code="INPUT_INVALID",
            )
        key = (row.candidate_window_id, row.requirement_id)
        if key in rows:
            raise ScienceError(f"duplicate qualification row {key}", code="INPUT_INVALID")
        rows[key] = row
    for window in inputs.verification_by_window_id:
        if window not in windows:
            raise ScienceError(f"verification supplied for unknown window {window!r}", code="INPUT_INVALID")

    # ---- items: coupled groups once, other reproducible requirements individually, gaps excluded
    items: list[_Item] = []
    groups: dict[str, list[Requirement]] = {}
    for req in reqs:
        if _is_gap(req):
            continue
        group = req.parameters.co_location_group
        if group is not None:
            groups.setdefault(group, []).append(req)
        else:
            items.append(_Item(f"req:{req.id}", (req,), False))
    for group, members in sorted(groups.items()):
        items.append(_Item(f"group:{group}", tuple(members), True))
    items.sort(key=lambda i: i.item_id)

    def row_ok(window: str, req: Requirement, *, need_final: bool) -> QualificationRowInput | None:
        row = rows.get((window, req.id))
        if row is None or row.status != "PASS" or row.critic_blocking_open:
            return None
        if need_final and row.evaluation_stage != "FINAL":
            return None
        return row

    def strength(window: str, item: _Item) -> int:
        """0 = not covered; otherwise the evidence-strength rank (1..3)."""
        verification = inputs.verification_by_window_id.get(window)
        if item.coupled:
            if verification is None or verification.outcome != "PASS":
                return 0
            return 3 if all(row_ok(window, m, need_final=True) for m in item.members) else 0
        req = item.members[0]
        if _route_dependent(req):
            if row_ok(window, req, need_final=True) is None:
                return 0
            if verification is not None and verification.outcome != "PASS":
                return 0
            return 3 if verification is not None else 2
        row = row_ok(window, req, need_final=False)
        if row is None:
            return 0
        return 2 if row.evaluation_stage == "FINAL" else 1

    strengths = {(w, i.item_id): strength(w, i) for w in windows for i in items}
    eligible = [w for w in windows if any(strengths[(w, i.item_id)] > 0 for i in items)]
    if len(eligible) > MAX_ELIGIBLE:
        raise ScienceError(
            f"{len(eligible)} eligible candidates exceed the exhaustive-enumeration limit of {MAX_ELIGIBLE}",
            code="RESOURCE_LIMIT",
        )

    def tiers(subset: tuple[str, ...]) -> tuple[float, float, int, int]:
        mandatory = optional = 0.0
        rank = 0
        for item in items:
            best = max((strengths[(w, item.item_id)] for w in subset), default=0)
            if best == 0:
                continue
            rank += best
            for member in item.members:
                if member.mandatory:
                    mandatory += float(member.weight)
                else:
                    optional += float(member.weight)
        return mandatory, optional, -len(subset), rank

    best_subset: tuple[str, ...] = ()
    best_tiers = tiers(())
    for size in range(1, min(inputs.max_sites, len(eligible)) + 1):
        for subset in itertools.combinations(eligible, size):
            if check_cancelled is not None:
                check_cancelled()
            t = tiers(subset)
            if t > best_tiers or (t == best_tiers and subset < best_subset):
                best_subset, best_tiers = subset, t

    selected = best_subset
    covering: dict[str, list[str]] = {}
    for item in items:
        sites = [w for w in selected if strengths[(w, item.item_id)] > 0]
        for member in item.members:
            covering[member.id] = sites

    assignments: list[PortfolioAssignment] = []
    for req in reqs:
        if _is_gap(req):
            assignments.append(
                PortfolioAssignment(
                    requirement_id=req.id,
                    window_ids=[],
                    coverage="GAP",
                    responsibility="Natural Earth sites cannot reproduce this condition; recommend a facility or "
                    "simulation test outside the site portfolio.",
                )
            )
            continue
        sites = covering.get(req.id, [])
        item = next(i for i in items if any(m.id == req.id for m in i.members))
        if sites:
            label = f"joint group {req.parameters.co_location_group}: " if item.coupled else ""
            assignments.append(
                PortfolioAssignment(
                    requirement_id=req.id,
                    window_ids=sites,
                    coverage="FULL",
                    responsibility=f"{label}{req.label} covered at {', '.join(sites)}",
                )
            )
            continue
        partial = [
            w
            for w in selected
            if (r := rows.get((w, req.id))) is not None
            and r.status in ("PARTIAL", "PASS")
            and not r.critic_blocking_open
        ]
        # NONE / GAP assert that every evaluated candidate says so: a window with no row for this requirement is
        # unevaluated (unknown), never a failure, so one missing row keeps the requirement UNKNOWN.
        pool_rows = [rows[(w, req.id)] for w in windows if (w, req.id) in rows]
        evaluated_everywhere = len(pool_rows) == len(windows) and bool(windows)
        if partial:
            assignments.append(
                PortfolioAssignment(
                    requirement_id=req.id,
                    window_ids=partial,
                    coverage="PARTIAL",
                    responsibility=f"{req.label}: only a supported subcondition at {', '.join(partial)}; "
                    "residual remains",
                )
            )
        elif evaluated_everywhere and all(r.status == "GAP" for r in pool_rows):
            assignments.append(PortfolioAssignment(requirement_id=req.id, window_ids=[], coverage="GAP"))
        elif evaluated_everywhere and all(r.status == "FAIL" and not r.critic_blocking_open for r in pool_rows):
            assignments.append(PortfolioAssignment(requirement_id=req.id, window_ids=[], coverage="NONE"))
        else:
            assignments.append(PortfolioAssignment(requirement_id=req.id, window_ids=[], coverage="UNKNOWN"))

    residual = sorted(a.requirement_id for a in assignments if a.coverage != "FULL")
    limitations = [
        "Smallest set among the evaluated candidates; not a globally minimal Earth campaign.",
        "Exhaustive subset enumeration does not imply exhaustive route-search optimality; source and verification "
        "limitations are inherited.",
        "Access permissions, protected land, current hazards and travel cost are unassessed planning factors; "
        "no field deployment is approved.",
    ]
    if not selected:
        limitations.append("Empty portfolio: no candidate has adequate relevant evidence for a coverable requirement.")
    if any(a.coverage == "GAP" for a in assignments):
        limitations.append("Physical gaps (e.g. gravity, atmosphere) remain; recommend a facility or simulation test.")
    if any(a.coverage == "PARTIAL" for a in assignments):
        limitations.append("PARTIAL coverage is not summed across sites; residual requirements are listed.")
    if not inputs.verification_by_window_id:
        limitations.append("Qualification-only portfolio: no rover compatibility or verified route is claimed.")
    unverified = sorted(
        w for w in selected if (v := inputs.verification_by_window_id.get(w)) is not None and v.outcome != "PASS"
    )
    if unverified:
        limitations.append(f"Planned or partially verified: verification is not PASS at {', '.join(unverified)}.")
    mandatory, optional, neg_sites, rank = best_tiers
    return OptimizePortfolioPayload(
        selected_window_ids=list(selected),
        assignments=assignments,
        objective_value=mandatory + optional,
        lexicographic_objective=[mandatory, optional, float(neg_sites), float(rank)],
        algorithm_id=ALGORITHM_ID,
        residual_requirement_ids=residual,
        limitations=limitations,
        portfolio_evidence=portfolio_evidence,
    )


__all__ = ["ALGORITHM_ID", "MAX_ELIGIBLE", "check_single_scope", "optimize_portfolio"]
