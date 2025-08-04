"""
Structured logging, standardized exception handlers, and FastAPI request tracing utilities.
Provides middleware for request logging, adds request IDs to logs and responses,
and installs global exception handlers for error transparency and traceability.
"""

import logging
import uuid
import time
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# PUBLIC_INTERFACE
def configure_logging():
    """
    Configure root logger for structured (JSON-like) logging.
    Ensures all logs have the same base format with level, module, request_id if present.
    """
    import sys

    class RequestIdFilter(logging.Filter):
        def filter(self, record):
            # Add a default request_id attribute to each record even if missing
            if not hasattr(record, "request_id"):
                record.request_id = "-"
            return True

    log_format = (
        "[%(asctime)s] %(levelname)s %(name)s "
        "request_id=%(request_id)s %(message)s"
    )
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        stream=sys.stdout
    )
    # Add the filter to root handler(s) to inject request_id
    for handler in logging.root.handlers:
        handler.addFilter(RequestIdFilter())


# PUBLIC_INTERFACE
class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware to assign a unique request_id to every incoming request.
    Adds 'X-Request-Id' header to responses; makes request_id available in logs and context.
    """
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable):
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request.state.request_id = request_id
        # Attach request_id to root logger context
        logger = logging.getLogger("event_engagement_backend.request")
        # Collect request info for structured log
        logger.info(f"REQUEST {request.method} {request.url.path}", extra={"request_id": request_id})
        start_time = time.time()
        try:
            # Make request_id available in response headers
            response: Response = await call_next(request)
            response.headers["X-Request-Id"] = request_id
        except Exception:
            logger.exception(f"Unhandled exception for {request.method} {request.url.path}", extra={"request_id": request_id})
            raise
        finally:
            process_time = (time.time() - start_time) * 1000.0
            logger.info(
                f"RESPONSE {request.method} {request.url.path} status={getattr(response, 'status_code', '-')}, time_ms={process_time:.2f}",
                extra={"request_id": request_id}
            )
        return response


# PUBLIC_INTERFACE
def install_exception_handlers(app):
    """
    Installs standardized exception handlers into the FastAPI app for:
      - HTTPException
      - RequestValidationError
      - Exception (catch-all)
    All error responses include a consistent JSON structure, log with request_id.
    """
    from fastapi import HTTPException

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        req_id = getattr(request.state, "request_id", "-")
        logging.getLogger("event_engagement_backend.errors").warning(
            f"HTTPException: {exc.status_code} - {exc.detail!r}", extra={"request_id": req_id}
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"type": "HTTPException", "detail": exc.detail, "request_id": req_id}},
            headers={"X-Request-Id": req_id}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        req_id = getattr(request.state, "request_id", "-")
        logging.getLogger("event_engagement_backend.errors").warning(
            f"Validation error: {exc.errors()}", extra={"request_id": req_id}
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"type": "ValidationError", "detail": exc.errors(), "request_id": req_id}},
            headers={"X-Request-Id": req_id}
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", "-")
        logging.getLogger("event_engagement_backend.errors").error(
            f"Unhandled exception: {exc!r}", extra={"request_id": req_id}
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"type": "InternalServerError", "detail": "Internal server error", "request_id": req_id}},
            headers={"X-Request-Id": req_id}
        )
