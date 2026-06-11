from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware import Middleware

from .api.routes import router
from .db import get_session
from .exceptions import ApiError, api_error_handler, generic_exception_handler, http_exception_handler, validation_exception_handler
from .middleware import CorrelationIdMiddleware

middleware = [Middleware(CorrelationIdMiddleware)]
app = FastAPI(title="Asanbar Pricing Service", version="0.1.0", middleware=middleware)
app.include_router(router)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute("SELECT 1")
    return {"status": "ready"}
