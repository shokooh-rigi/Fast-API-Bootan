from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.status import HTTP_409_CONFLICT, HTTP_404_NOT_FOUND, HTTP_422_UNPROCESSABLE_ENTITY


class ApiError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code


class NotFoundError(ApiError):
    def __init__(self, code: str = "NOT_FOUND", message: str = "Resource not found") -> None:
        super().__init__(code, message, HTTP_404_NOT_FOUND)


class ConflictError(ApiError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, HTTP_409_CONFLICT)


class ValidationError(ApiError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, HTTP_422_UNPROCESSABLE_ENTITY)


class UnknownRateCardError(ValidationError):
    def __init__(self, message: str) -> None:
        super().__init__("UNKNOWN", message)


class QuoteNotFoundError(NotFoundError):
    def __init__(self, message: str = "QUOTE_NOT_FOUND") -> None:
        super().__init__("QUOTE_NOT_FOUND", message)


class SnapshotNotFoundError(NotFoundError):
    def __init__(self, message: str = "SNAPSHOT_NOT_FOUND") -> None:
        super().__init__("SNAPSHOT_NOT_FOUND", message)


class SnapshotAlreadyExistsError(ConflictError):
    def __init__(self, message: str = "A snapshot already exists for this shipment") -> None:
        super().__init__("SNAPSHOT_ALREADY_EXISTS", message)


class IdempotencyConflictError(ConflictError):
    def __init__(self, message: str = "Idempotency key conflict") -> None:
        super().__init__("IDEMPOTENCY_CONFLICT", message)


def make_error_response(code: str, message: str, correlation_id: str | None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "correlation_id": correlation_id}}


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=make_error_response(exc.code, exc.message, getattr(request.state, "correlation_id", None)),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = exc.detail if isinstance(exc.detail, str) else "HTTP_ERROR"
    return JSONResponse(
        status_code=exc.status_code,
        content=make_error_response(code, str(exc.detail), getattr(request.state, "correlation_id", None)),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    message = "; ".join(error.get("msg", "invalid") for error in errors)
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content=make_error_response("VALIDATION_ERROR", message, getattr(request.state, "correlation_id", None)),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=make_error_response("INTERNAL_SERVER_ERROR", "Unexpected server error", getattr(request.state, "correlation_id", None)),
    )
