"""Safe errors: request data, environment values and credentials are never echoed."""

from __future__ import annotations

from typing import Any
from uuid import uuid4


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 422, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.details = details or {}

    def envelope(self, request_id: str | None = None) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": request_id or str(uuid4()),
                "retryable": False,
                "details": self.details,
            }
        }
