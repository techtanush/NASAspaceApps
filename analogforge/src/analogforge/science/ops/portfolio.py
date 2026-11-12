"""``OPTIMIZE_PORTFOLIO`` (guide 08 section 4.13): wraps :mod:`analogforge.science.portfolio`."""

from __future__ import annotations

from analogforge.ports import catalog
from analogforge.ports.common import EvidenceRef
from analogforge.ports.science import ComputationStatus
from analogforge.ports.science_payloads import OptimizePortfolioInput
from analogforge.science.ops.base import OpEnv, OpOutcome, derived_evidence, json_artifact
from analogforge.science.portfolio import optimize_portfolio


def run_portfolio(env: OpEnv) -> OpOutcome:
    inp = env.request.inputs
    assert isinstance(inp, OptimizePortfolioInput)
    algo = catalog.ALGORITHM_IDS["OPTIMIZE_PORTFOLIO"]
    payload = optimize_portfolio(
        inp,
        portfolio_evidence=EvidenceRef(local_key="portfolio"),
        mode=env.request.mode,
        evidence_modes=[h.mode for h in env.request.input_evidence],
        check_cancelled=env.check,
    )
    params = env.params_hash(algo, env.operation_params())
    art = json_artifact(env, params_sha=params, key="portfolio-json", name="portfolio.json", payload=payload)
    ev = derived_evidence(
        env,
        key="portfolio",
        kind="DERIVED",
        body="EARTH",
        algorithm_id=algo,
        params_sha=params,
        artifact=art,
        parent_evidence_ids=[h.evidence_id for h in env.request.input_evidence],
        limitations=list(payload.limitations),
    )
    return OpOutcome(ComputationStatus.SUCCEEDED, payload, algo, params, [art], [ev])
