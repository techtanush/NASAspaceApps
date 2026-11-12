"""FastAPI entry point; import never starts jobs, contacts providers or runs science."""

from __future__ import annotations

import logging
from functools import cached_property
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from analogforge.api.contracts import specification
from analogforge.api.errors import ApiError
from analogforge.api.router import build_router
from analogforge.api.security import origin_allowed, response_headers

logger = logging.getLogger("analogforge.api")


class PlatformRuntime:
    def __init__(self, settings: Any, store: Any, science: Any = None, renderer: Any = None) -> None:
        from analogforge.adapters.storage.cas import ContentAddressedStore

        self.settings, self.store = settings, store
        self.science, self.renderer = science, renderer
        self.blobs = ContentAddressedStore(settings.data_root)

    @cached_property
    def engine(self) -> Any:
        from analogforge.application.scheduler import WorkflowEngine

        return WorkflowEngine(
            self.store, self.settings, science=self.science, renderer=self.renderer, blob_store=self.blobs
        )

    def scenarios(self) -> dict[str, Any]:
        from analogforge.application.capabilities import get_scenarios

        return dict(get_scenarios(self.settings))

    def handle_job(self, job: dict[str, Any]) -> None:
        """Durable worker dispatch. HTTP handlers only enqueue commands."""
        from analogforge.jobs.handlers import advance_run, export_passport, prepare_fingerprint

        handlers = {
            "ADVANCE_RUN": advance_run.handle,
            "EXPORT_PASSPORT": export_passport.handle,
            "PREPARE_FINGERPRINT": prepare_fingerprint.handle,
        }
        handler = handlers.get(job["kind"])
        if handler is None:
            raise ApiError("INPUT_INVALID", "The worker received an unknown job kind.")
        handler(self, job)


class ContractFastAPI(FastAPI):
    def openapi(self) -> dict[str, Any]:
        return specification()


def create_app(
    settings: Any = None, store: Any = None, science: Any = None, renderer: Any = None, identity_provider: Any = None
) -> FastAPI:
    from analogforge.application.scheduler import WorkflowError
    from analogforge.db.store import PersistenceError, Store
    from analogforge.domain.budgets import BudgetExceeded
    from analogforge.domain.policy import PolicyViolation
    from analogforge.settings import get_settings

    settings = settings or get_settings()
    store = store or Store(settings.database_url)
    application = ContractFastAPI(title="AnalogForge", version="0.1.0")
    application.state.settings = settings
    application.state.runtime = PlatformRuntime(settings, store, science, renderer)
    application.state.identity_provider = identity_provider
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key", "Last-Event-ID", "X-CSRF-Token"],
        expose_headers=["ETag", "X-Artifact-SHA256", "Retry-After", "Content-Disposition"],
    )

    @application.middleware("http")
    async def boundary(request: Request, call_next: Any) -> Any:
        request.state.request_id = str(uuid4())
        origin = request.headers.get("origin")
        if request.method == "POST" and not origin_allowed(origin, settings.allowed_origins):
            error = ApiError("FORBIDDEN", "This origin is not authorized to submit commands.", 403)
            return JSONResponse(
                error.envelope(request.state.request_id),
                status_code=403,
                headers=response_headers(request.state.request_id),
            )
        response = await call_next(request)
        response.headers.update(response_headers(request.state.request_id))
        logger.info(
            "request_complete",
            extra={"request_id": request.state.request_id, "method": request.method, "status": response.status_code},
        )
        return response

    @application.exception_handler(ApiError)
    async def application_error(request: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(error.envelope(getattr(request.state, "request_id", None)), status_code=error.status)

    @application.exception_handler(PersistenceError)
    async def persistence_error(request: Request, error: PersistenceError) -> JSONResponse:
        code = error.code
        statuses = {
            "NOT_FOUND": 404,
            "REVISION_CONFLICT": 409,
            "IDEMPOTENCY_CONFLICT": 409,
            "LEASE_LOST": 409,
            "EVENT_CURSOR_EXPIRED": 410,
            "INVALID_TRANSITION": 409,
            "AUTHENTICATION_REQUIRED": 401,
            "AUTHORIZATION_FAILED": 403,
            "CSRF_INVALID": 403,
            "SOURCE_UNAVAILABLE": 503,
            "IDENTITY_PROVIDER_UNAVAILABLE": 503,
            "OIDC_CONFIGURATION_INVALID": 503,
        }
        status = statuses.get(code, 422)
        safe = ApiError(code, "The operation could not be applied to this workspace record.", status)
        if code == "SCIENTIFIC_CLAIM_REJECTED":
            from analogforge.application.assurance import ScientificClaimRejected

            if isinstance(error, ScientificClaimRejected):
                safe = ApiError(
                    code,
                    "The scientific claim failed publication checks.",
                    status,
                    details={"issue_codes": error.issue_codes},
                )
        return JSONResponse(safe.envelope(getattr(request.state, "request_id", None)), status_code=status)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        safe = ApiError("INPUT_INVALID", "The request does not satisfy the public contract.")
        return JSONResponse(safe.envelope(getattr(request.state, "request_id", None)), status_code=422)

    async def workflow_error(request: Request, error: Exception) -> JSONResponse:
        code = getattr(error, "code", "MODEL_OUTPUT_INVALID")
        status = {
            "REVISION_CONFLICT": 409,
            "INVALID_TRANSITION": 409,
            "NOT_FOUND": 404,
            "BUDGET_EXHAUSTED": 429,
            "PROVIDER_AUTH_FAILED": 503,
            "SOURCE_UNAVAILABLE": 503,
        }.get(code, 422)
        safe = ApiError(code, "The workflow command cannot be applied to the current run.", status)
        return JSONResponse(safe.envelope(getattr(request.state, "request_id", None)), status_code=status)

    for error_type in (WorkflowError, BudgetExceeded, PolicyViolation):
        application.add_exception_handler(error_type, workflow_error)

    @application.exception_handler(SQLAlchemyError)
    async def unavailable_database(request: Request, error: SQLAlchemyError) -> JSONResponse:
        safe = ApiError("DATABASE_UNAVAILABLE", "The database operation is temporarily unavailable.", 503)
        return JSONResponse(safe.envelope(getattr(request.state, "request_id", None)), status_code=503)

    application.include_router(build_router())
    from analogforge.api.routers.auth import router as auth_router

    application.include_router(auth_router)
    return application


app = create_app()
