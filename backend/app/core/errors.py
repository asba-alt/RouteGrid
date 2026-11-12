"""Centralised exception handling with a single, consistent error envelope.

Rules enforced here:
- clients never see stack traces, SQL, credentials or driver internals;
- every error carries a stable machine-readable ``code`` plus the request id,
  so a user-visible failure can be correlated with the server log;
- database connectivity failures become 503 (retryable) rather than 500.
"""
import logging
from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import current_request_id

logger = logging.getLogger("routegrid.error")

_CONNECTIVITY_MARKERS = (
    "connection refused",
    "could not connect",
    "connection reset",
    "server closed the connection",
    "terminating connection",
    "the database system is starting up",
    "timeout expired",
)

_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    408: "request_timeout",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    503: "service_unavailable",
}


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_response(
    status_code: int,
    message: str,
    *,
    code: Optional[str] = None,
    details: Any = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=code or _STATUS_CODES.get(status_code, "error"),
            message=message,
            request_id=current_request_id(),
            details=details,
        )
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


def _is_connectivity_error(exc: DBAPIError) -> bool:
    text = str(getattr(exc, "orig", exc)).lower()
    return any(marker in text for marker in _CONNECTIVITY_MARKERS)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # HTTPException.detail may be a string or a structured object.
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        details = None if isinstance(exc.detail, str) else exc.detail
        return error_response(exc.status_code, message, details=details)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Field-level messages are safe and useful; request bodies are not echoed.
        problems = [
            {
                "field": ".".join(str(part) for part in err.get("loc", [])[1:]),
                "message": err.get("msg", "invalid value"),
                "type": err.get("type", "value_error"),
            }
            for err in exc.errors()
        ]
        return error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Request validation failed",
            details=problems,
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        logger.warning("integrity error on %s: %s", request.url.path, type(exc).__name__)
        return error_response(
            status.HTTP_409_CONFLICT,
            "Conflict: the request collides with existing data",
        )

    @app.exception_handler(OperationalError)
    async def operational_error_handler(
        request: Request, exc: OperationalError
    ) -> JSONResponse:
        logger.error("database unavailable on %s: %s", request.url.path, type(exc).__name__)
        return error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Database is unavailable. Please retry shortly.",
        )

    @app.exception_handler(DBAPIError)
    async def dbapi_error_handler(request: Request, exc: DBAPIError) -> JSONResponse:
        if _is_connectivity_error(exc):
            logger.error("database connectivity failure on %s", request.url.path)
            return error_response(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Database is unavailable. Please retry shortly.",
            )
        logger.error("database error on %s: %s", request.url.path, type(exc).__name__)
        return error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "A database error occurred"
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # Full detail to the log, nothing but a safe message to the caller.
        logger.exception("unhandled error on %s", request.url.path)
        return error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "An unexpected internal error occurred",
        )
