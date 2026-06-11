import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable):
        correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response


def get_correlation_id(request: Request) -> str:
    return request.state.correlation_id
