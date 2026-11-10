"""``analogforge.science.facade:create_science_service`` - the ScienceService implementation (architecture 35 s3.5).

``execute`` validates the request, dispatches on the operation and wraps the operation outcome into a kit-valid
``ScienceComputationResult``.  Expected data problems become ``BLOCKED`` (never an exception); unexpected engine
errors become ``FAILED``; ``ScienceCancelled`` / ``ScienceDeadlineExceeded`` always propagate.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from analogforge.ports import catalog
from analogforge.ports.common import ScienceIssue
from analogforge.ports.hashing import canonical_sha256
from analogforge.ports.science import (
    ComputationStatus,
    ScienceCancelled,
    ScienceComputationResult,
    ScienceContext,
    ScienceDeadlineExceeded,
    ScienceOperation,
    ScienceRequest,
    ScienceService,
)
from analogforge.science.config import ScienceConfig, config_for_hash, load_config
from analogforge.science.errors import ScienceError
from analogforge.science.ops.base import OpBlocked, OpEnv, OpOutcome

OpFn = Callable[[OpEnv], OpOutcome]

# operation -> (module, function, algorithm id used for BLOCKED/FAILED envelopes)
_TABLE: dict[ScienceOperation, tuple[str, str, str]] = {
    ScienceOperation.RESOLVE_COVERAGE: ("analogforge.science.ops.coverage", "run_resolve_coverage", "resolve-coverage"),
    ScienceOperation.FETCH_SOURCE: ("analogforge.science.ops.coverage", "run_fetch_source", "fetch-source"),
    ScienceOperation.INGEST_LOCAL_DATASET: ("analogforge.science.ops.ingest", "run_ingest", "ingest-local-dataset"),
    ScienceOperation.CHARACTERIZE_TARGET: (
        "analogforge.science.ops.characterize",
        "run_characterize",
        "characterize-target",
    ),
    ScienceOperation.SCREEN_CANDIDATES: ("analogforge.science.ops.screen", "run_screen", "screen-candidates"),
    ScienceOperation.ANALYZE_CANDIDATE: ("analogforge.science.ops.analyze", "run_analyze", "analyze-candidate"),
    ScienceOperation.COMPARE_REQUIREMENT: ("analogforge.science.ops.compare", "run_compare", "compare-requirement"),
    ScienceOperation.ASSESS_COMPATIBILITY: ("analogforge.science.ops.compare", "run_compat", "assess-compatibility"),
    ScienceOperation.DESIGN_BENCHMARK: ("analogforge.science.ops.route", "run_design", "design-benchmark"),
    ScienceOperation.SEARCH_ROUTE: ("analogforge.science.ops.route", "run_search", "search-route"),
    ScienceOperation.VERIFY_ROUTE: ("analogforge.science.ops.route", "run_verify", "verify-route"),
    ScienceOperation.DIAGNOSE_RESULT: ("analogforge.science.ops.route", "run_diagnose", "diagnose-result"),
    ScienceOperation.OPTIMIZE_PORTFOLIO: ("analogforge.science.ops.portfolio", "run_portfolio", "optimize-portfolio"),
    ScienceOperation.BUILD_DISPLAY_LAYERS: ("analogforge.science.ops.display", "run_display", "build-display-layers"),
    ScienceOperation.AUDIT_EVIDENCE: ("analogforge.science.ops.audit", "run_audit", "audit-evidence"),
}


class ScienceFacade:
    """Implements :class:`~analogforge.ports.science.ScienceService` for all fifteen operations."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._config_dir = config_dir
        self._cfg: ScienceConfig | None = None

    @property
    def cfg(self) -> ScienceConfig:
        if self._cfg is None:
            self._cfg = load_config(self._config_dir)
        return self._cfg

    def supported_operations(self) -> frozenset[ScienceOperation]:
        return frozenset(_TABLE)

    # ------------------------------------------------------------------ envelope helpers
    def _envelope(
        self,
        request: ScienceRequest,
        cfg: ScienceConfig,
        algo: str,
        status: ComputationStatus,
        issues: list[ScienceIssue],
    ) -> ScienceComputationResult:
        version = cfg.algorithms.algorithm_lock.get(algo, "1.0.0")
        params = canonical_sha256(
            {
                "operation": request.operation.value,
                "algorithm_id": algo,
                "algorithm_version": version,
                "parameters": request.inputs.model_dump(mode="json"),
                "seed": request.options.seed,
                "algorithm_config_sha256": cfg.algorithm_config_sha256,
            }
        )
        return ScienceComputationResult(
            request_id=request.request_id,
            operation=request.operation,
            mode=request.mode,
            status=status,
            algorithm_id=algo,
            algorithm_version=version,
            parameters_sha256=params,
            input_sha256=canonical_sha256(request),
            payload=None,
            issues=issues,
        )

    def execute(self, request: ScienceRequest, context: ScienceContext) -> ScienceComputationResult:
        module_name, fn_name, algo = _TABLE[request.operation]
        cfg = self.cfg
        pin = request.options.algorithm_config_sha256
        if not cfg.verify_pin(pin):
            pinned = config_for_hash(pin) if pin is not None else None
            if pinned is None:
                return self._envelope(
                    request,
                    cfg,
                    algo,
                    ComputationStatus.BLOCKED,
                    [
                        ScienceIssue(
                            code="INPUT_INVALID",
                            detail_code="ALGORITHM_CONFIG_MISMATCH",
                            message="the pinned algorithm_config_sha256 does not match the loaded configuration",
                        )
                    ],
                )
            cfg = pinned
        if request.mode != context.mode:
            return self._envelope(
                request,
                cfg,
                algo,
                ComputationStatus.BLOCKED,
                [
                    ScienceIssue(
                        code="INPUT_INVALID",
                        detail_code="MODE_MISMATCH",
                        message=f"request mode {request.mode} differs from context mode {context.mode}",
                    )
                ],
            )
        env = OpEnv(request=request, context=context, cfg=cfg)
        try:
            fn: OpFn = getattr(importlib.import_module(module_name), fn_name)
            outcome = fn(env)
            return self._finish(request, cfg, outcome)
        except (ScienceCancelled, ScienceDeadlineExceeded):
            raise
        except OpBlocked as exc:
            return self._envelope(request, cfg, algo, ComputationStatus.BLOCKED, [exc.to_issue()])
        except ScienceError as exc:
            issue = ScienceIssue(code=exc.code, detail_code=exc.detail_code, message=exc.message)
            return self._envelope(request, cfg, algo, ComputationStatus.BLOCKED, [issue])
        except ValidationError as exc:
            issue = ScienceIssue(code="INPUT_INVALID", detail_code="MODEL_VALIDATION", message=str(exc)[:500])
            return self._envelope(request, cfg, algo, ComputationStatus.BLOCKED, [issue])
        except Exception as exc:  # noqa: BLE001 - unexpected engine errors are FAILED results, never verdicts
            issue = ScienceIssue(
                code="SYSTEM", detail_code=type(exc).__name__, message=f"unexpected engine error: {exc}"[:500]
            )
            return self._envelope(request, cfg, algo, ComputationStatus.FAILED, [issue])

    def _finish(self, request: ScienceRequest, cfg: ScienceConfig, outcome: OpOutcome) -> ScienceComputationResult:
        return ScienceComputationResult(
            request_id=request.request_id,
            operation=request.operation,
            mode=request.mode,
            status=outcome.status,
            algorithm_id=outcome.algorithm_id,
            algorithm_version=cfg.algorithm_version(outcome.algorithm_id),
            parameters_sha256=outcome.parameters_sha256,
            input_sha256=canonical_sha256(request),
            counters=outcome.counters,
            artifacts=outcome.artifacts,
            evidence_drafts=outcome.evidence,
            payload=outcome.payload,
            issues=outcome.issues,
        )


def create_science_service(config_dir: Path | None = None) -> ScienceService:
    """Production entry point (``SCIENCE_FACADE_ENTRY_POINT``)."""
    return ScienceFacade(config_dir)


__all__ = ["ScienceFacade", "create_science_service", "catalog"]
